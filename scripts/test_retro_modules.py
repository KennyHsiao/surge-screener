#!/usr/bin/env python3
"""Self-contained tests for retro_modules' fail-closed control gating (no network).

Covers the round-3 adversarial-review finding: module lift must NOT present
per-threshold tables from a fallback or stale control baseline as valid
threshold-specific evidence. Each scenario asserts recommendations_blocked.

Run:  .venv/bin/python scripts/test_retro_modules.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _flags(rvol: bool) -> dict:
    return {"rvol_ge_2": rvol}


def _run(tmp: Path, control_features: dict, lift: dict | None = None,
         write_lift: bool = True) -> dict:
    """Write fixtures, run retro_modules.py, return the module_lift payload."""
    feat = {"generated_at": "G1", "features": [
        {"ticker": "AAA", "thresholds_hit": ["+30%/20d"], "flags": _flags(True)},
        {"ticker": "BBB", "thresholds_hit": ["+40%/40d"], "flags": _flags(False)},
    ]}
    # Factor lift NOT blocked by coverage + matching provenance, so the only gate
    # under test is the module one (unless a scenario overrides `lift`).
    if lift is None:
        lift = {"source": {"features_generated_at": "G1"},
                "coverage": {"sample_experiment": False, "survivorship_bias": False},
                "low_confidence": False, "recommendations_blocked": False, "tables": {}}
    modules = {"modules": [{"name": "M", "factors": {"rvol_ge_2": True}}]}

    (tmp / "surge_features.json").write_text(json.dumps(feat))
    (tmp / "control_features.json").write_text(json.dumps(control_features))
    if write_lift:
        (tmp / "factor_lift.json").write_text(json.dumps(lift))
    (tmp / "modules.json").write_text(json.dumps(modules))
    out = tmp / "module_lift.json"
    r = subprocess.run(
        [sys.executable, str(HERE / "retro_modules.py"),
         "--features", str(tmp / "surge_features.json"),
         "--controls", str(tmp / "control_features.json"),
         "--lift", str(tmp / "factor_lift.json"),
         "--modules", str(tmp / "modules.json"),
         "--output", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, f"retro_modules failed: {r.stderr}"
    return json.loads(out.read_text())


def _controls(n: int, rvol: bool) -> list:
    return [{"ticker": f"C{i}", "date": "2025-01-01", "flags": _flags(rvol)} for i in range(n)]


def _full_control_file(features_gen: str = "G1") -> dict:
    return {
        "source": {"features_generated_at": features_gen},
        "controls": _controls(10, False),
        "by_threshold": {
            "+30%/20d": {"controls": _controls(10, False)},
            "+40%/40d": {"controls": _controls(10, False)},
        },
    }


def test_matched_is_not_blocked():
    """Provenance matches + every label has its own set → threshold-specific, unblocked."""
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G1"))
    assert out["control_match"] == "threshold-specific", out["control_match"]
    assert out["provenance_ok"] is True
    assert out["recommendations_blocked"] is False


def test_missing_by_threshold_blocks():
    """No by_threshold map → all-fallback baseline → blocked."""
    cf = _full_control_file("G1")
    cf.pop("by_threshold")
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf)
    assert out["control_match"] == "all-fallback", out["control_match"]
    assert out["recommendations_blocked"] is True


def test_missing_one_label_blocks():
    """Map present but missing a needed label → partial-fallback → blocked."""
    cf = _full_control_file("G1")
    cf["by_threshold"].pop("+40%/40d")
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf)
    assert out["control_match"] == "partial-fallback", out["control_match"]
    assert out["recommendations_blocked"] is True


def test_stale_provenance_blocks():
    """Control file from a DIFFERENT surge run (generated_at mismatch) → blocked."""
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G2-STALE"))
    assert out["provenance_ok"] is False
    assert out["recommendations_blocked"] is True


def test_missing_lift_file_blocks():
    """No factor_lift.json → can't confirm coverage → fail closed."""
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G1"), write_lift=False)
    assert out["recommendations_blocked"] is True


def test_stale_lift_provenance_blocks():
    """factor_lift.json from a different run (source mismatch) → fail closed."""
    stale_lift = {"source": {"features_generated_at": "G9-OTHER"},
                  "coverage": {"sample_experiment": False},
                  "recommendations_blocked": False, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G1"), lift=stale_lift)
    assert out["recommendations_blocked"] is True


def test_coverage_gate_survivorship_always_blocks():
    """recommendations_blocked is ALWAYS true; the opt-in only sets exploratory_override."""
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    # underpowered → blocked, no exploratory override (gated on power).
    cov, low, blocked, expl = rfl.coverage_gate("sp1500", 1500, 8, 10, 1500)
    assert low is True and blocked is True and expl is False
    # powered full run: STILL blocked (survivorship); opt-in does not unblock.
    cov2, low2, blocked2, expl2 = rfl.coverage_gate("sp1500", 1500, 200, 500, 1400)
    assert low2 is False and blocked2 is True and expl2 is False
    cov3, low3, blocked3, expl3 = rfl.coverage_gate(
        "sp1500", 1500, 200, 500, 1400, allow_exploratory=True)
    assert blocked3 is True, "opt-in must NOT unblock actionable recommendations"
    assert expl3 is True, "opt-in only enables exploratory synthesis"


def test_verdict_zero_controls_is_insufficient():
    """20 surgers with a factor True but ZERO known controls must NOT be VALIDATED."""
    sys.path.insert(0, str(HERE))
    import numpy as np
    import retro_factor_lift as rfl
    surgers = [{"flags": {"f": True}} for _ in range(20)]
    controls = [{"flags": {"f": None}} for _ in range(20)]   # all unknown
    defs = {"f": {"dimension": "D", "subfactor": "s", "desc": "d"}}
    row = rfl.compute_lift(surgers, controls, defs, np.random.default_rng(0))[0]
    assert row["n_control"] == 0
    assert row["verdict"] == "INSUFFICIENT", row["verdict"]


def test_report_is_blocked_failclosed():
    """retro_report._is_blocked fails closed on missing/inconsistent gate metadata."""
    sys.path.insert(0, str(HERE))
    import retro_report as rr
    assert rr._is_blocked({}) is True                         # missing → blocked
    assert rr._is_blocked({"recommendations_blocked": False}) is True  # partial → blocked
    ok = {"recommendations_blocked": False, "low_confidence": False,
          "coverage": {"sample_experiment": False, "survivorship_bias": False}}
    assert rr._is_blocked(ok) is False                        # explicit + consistent + unbiased
    assert rr._is_blocked({**ok, "low_confidence": True}) is True
    # survivorship bias (or its absence) must block even if the other fields say unblocked.
    assert rr._is_blocked({**ok, "coverage": {"sample_experiment": False,
                                              "survivorship_bias": True}}) is True
    assert rr._is_blocked({**ok, "coverage": {"sample_experiment": False}}) is True  # missing


def test_module_blocks_on_provenance_match_but_missing_gate():
    """Lift file matches provenance but lacks gate fields → still blocked (no fail-open)."""
    cf = _full_control_file("G1")
    # provenance matches (G1) but no recommendations_blocked / low_confidence keys.
    lift = {"source": {"features_generated_at": "G1"},
            "coverage": {"sample_experiment": False}, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, lift=lift)
    assert out["recommendations_blocked"] is True


def test_verdict_wilson_significance():
    """Verdict uses NON-OVERLAPPING Wilson intervals, not a passed CI.

    Signature: _verdict(lift, n_surge_known, surge_true, n_control_known, control_true).
    """
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    # strong separation (25/30 vs 1/30), lift high, surge_true>=20 → VALIDATED
    assert rfl._verdict(25.0, 30, 25, 30, 1) == "VALIDATED"
    # moderate separation (18/30 vs 6/30) but surge_true<20 → WEAK
    assert rfl._verdict(3.0, 30, 18, 30, 6) == "WEAK"
    # overlapping intervals (15/30 vs 12/30) → NOISE
    assert rfl._verdict(1.25, 30, 15, 30, 12) == "NOISE"
    # absent before surge (3/30 vs 18/30), non-overlapping below → CONTRARIAN
    assert rfl._verdict(0.17, 30, 3, 30, 18) == "CONTRARIAN"


def test_sanitize_blocked_handles_raw_and_malformed():
    """proposed_changes emptied for raw/unfenced JSON; malformed → None (gate summary)."""
    sys.path.insert(0, str(HERE))
    import json as _json
    import retro_report as rr
    raw = '{"narrative_summary": "x", "proposed_changes": [{"file": "p"}]}'
    out = rr._sanitize_blocked(raw + "\n\nsome advice narrative")
    assert out is not None and "```json" in out
    obj = _json.loads(out.split("```json")[1].split("```")[0])
    assert obj["proposed_changes"] == []
    assert rr._sanitize_blocked("no json here at all") is None


def test_verdict_zero_cell_via_wilson():
    """Zero-cells resolve via sample-size-aware Wilson bounds (0/5 ≠ 0/200), and a
    strong absent-before-surge filter (0/44) is CONTRARIAN, not suppressed."""
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    # control all-FALSE, n=25: Wilson upper ≈ 0.10 (tight), strong separation → VALIDATED
    # (Codex permits a zero-cell IF the bounded rate still supports the lift).
    assert rfl._verdict(50.0, 30, 25, 25, 0) == "VALIDATED"
    # control all-FALSE, large (0/200): even tighter → VALIDATED.
    assert rfl._verdict(50.0, 30, 25, 200, 0) == "VALIDATED"
    # small samples with WIDE, overlapping Wilson intervals (6/10 vs 4/10) → NOISE.
    assert rfl._verdict(1.5, 10, 6, 10, 4) == "NOISE"
    # surge arm all-FALSE over a large sample (0/44) vs decent controls → CONTRARIAN.
    assert rfl._verdict(0.0, 44, 0, 60, 30) == "CONTRARIAN"


def test_blocked_report_text_is_deterministic():
    """A blocked run NEVER calls the LLM and persists the deterministic gate summary."""
    sys.path.insert(0, str(HERE))
    import retro_report as rr
    called = {"n": 0}

    def synth():
        called["n"] += 1
        return '```json\n{"narrative_summary":"BUY everything","proposed_changes":[{"x":1}]}\n```'

    blocked_lift = {"recommendations_blocked": True, "low_confidence": True,
                    "coverage": {"sample_experiment": True}}
    out = rr.build_report_text(blocked_lift, synth)
    assert called["n"] == 0, "LLM must not be called without a validated override"
    assert "BUY everything" not in out and out == rr._BLOCKED_SUMMARY
    # override BIT alone is NOT enough: low_confidence True → still no LLM.
    assert rr.build_report_text(
        {"exploratory_override": True, "low_confidence": True,
         "coverage": {"sample_experiment": True, "survivorship_bias": True}}, synth) \
        == rr._BLOCKED_SUMMARY
    assert called["n"] == 0
    # validated exploratory run DOES synthesize — but proposed_changes still stripped.
    expl_lift = {"recommendations_blocked": True, "exploratory_override": True,
                 "low_confidence": False,
                 "coverage": {"sample_experiment": False, "survivorship_bias": True}}
    out2 = rr.build_report_text(expl_lift, synth)
    assert called["n"] == 1 and "narrative_summary" in out2
    import json as _json
    obj = _json.loads(out2.split("```json")[1].split("```")[0])
    assert obj["proposed_changes"] == [], "proposed_changes stripped even when exploratory"


def test_exploratory_rejects_inconsistent_metadata():
    """exploratory_override:true + recommendations_blocked:false (canonically blocked
    by survivorship) is INCONSISTENT → no LLM synthesis."""
    sys.path.insert(0, str(HERE))
    import retro_report as rr
    called = {"n": 0}
    synth = lambda: (called.__setitem__("n", called["n"] + 1) or '{"proposed_changes":[]}')
    bad = {"exploratory_override": True, "recommendations_blocked": False,
           "low_confidence": False,
           "coverage": {"sample_experiment": False, "survivorship_bias": True}}
    assert rr.build_report_text(bad, synth) == rr._BLOCKED_SUMMARY
    assert called["n"] == 0


def test_ui_gate_blocked_failclosed():
    """The UI canonical gate blocks unless ALL fields are explicitly consistent+unbiased."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent))
    from ui.retro_analysis import _gate_blocked
    ok = {"recommendations_blocked": False, "low_confidence": False,
          "coverage": {"sample_experiment": False, "survivorship_bias": False}}
    assert _gate_blocked(ok) is False
    assert _gate_blocked({**ok, "coverage": {"sample_experiment": False}}) is True  # missing surv
    assert _gate_blocked({**ok, "coverage": {"sample_experiment": False,
                                            "survivorship_bias": True}}) is True
    assert _gate_blocked({}) is True


def test_forward_lift_missing_dim_is_none():
    """A dimension marked missing in data_missing is None (not binarized placeholder)."""
    sys.path.insert(0, str(HERE))
    import retro_forward_lift as fl
    medians = {c: 5.0 for c in fl.DIM_FACTORS}
    row = {"sentiment": 8, "options_flow": 9, "technical": 8,
           "data_missing": "sentiment|options_flow"}
    flags = fl.dim_flags(row, medians)
    assert flags["sentiment_high"] is None, "missing sentiment must be None"
    assert flags["options_flow_high"] is None, "missing options_flow must be None"
    assert flags["technical_high"] is True, "present technical binarizes"


def test_display_ci_not_degenerate_on_zero_cell():
    """lift_ci90 is Wilson-derived: a zero-true-control cell is one-sided, not [cap,cap]."""
    sys.path.insert(0, str(HERE))
    import numpy as np
    import retro_factor_lift as rfl
    surgers = [{"flags": {"f": True}} for _ in range(25)]
    controls = [{"flags": {"f": False}} for _ in range(30)]   # zero true controls
    defs = {"f": {"dimension": "D", "subfactor": "s", "desc": "d"}}
    row = rfl.compute_lift(surgers, controls, defs, np.random.default_rng(0))[0]
    assert row["lift_ci90_method"] == "wilson"
    assert row["ci_one_sided"] is True
    assert row["lift_ci90"][0] < row["lift_ci90"][1], "not a collapsed [cap,cap]"


def main() -> int:
    tests = [test_matched_is_not_blocked, test_missing_by_threshold_blocks,
             test_missing_one_label_blocks, test_stale_provenance_blocks,
             test_missing_lift_file_blocks, test_stale_lift_provenance_blocks,
             test_coverage_gate_survivorship_always_blocks,
             test_verdict_zero_controls_is_insufficient,
             test_report_is_blocked_failclosed,
             test_module_blocks_on_provenance_match_but_missing_gate,
             test_verdict_wilson_significance,
             test_sanitize_blocked_handles_raw_and_malformed,
             test_verdict_zero_cell_via_wilson,
             test_blocked_report_text_is_deterministic,
             test_exploratory_rejects_inconsistent_metadata,
             test_ui_gate_blocked_failclosed,
             test_forward_lift_missing_dim_is_none,
             test_display_ci_not_degenerate_on_zero_cell]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"retro_modules tests: {passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
