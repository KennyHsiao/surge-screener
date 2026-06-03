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
                "coverage": {"sample_experiment": False}, "low_confidence": False,
                "recommendations_blocked": False, "tables": {}}
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


def test_coverage_gate_blocks_underpowered():
    """Full coverage but too few events / surgers → low_confidence → blocked."""
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    cov, low, blocked = rfl.coverage_gate("sp1500", 1500, 8, 10, 1500)
    assert cov["sample_experiment"] is False, "coverage is full"
    assert low is True and blocked is True, "underpowered must block"
    # Properly-powered full run is NOT low_confidence, but survivorship still blocks
    # unless explicitly opted in.
    cov2, low2, blocked2 = rfl.coverage_gate("sp1500", 1500, 200, 500, 1400)
    assert low2 is False and blocked2 is True, "survivorship blocks by default"
    _, _, blocked3 = rfl.coverage_gate("sp1500", 1500, 200, 500, 1400,
                                       allow_survivorship_biased=True)
    assert blocked3 is False, "explicit opt-in unblocks a powered full run"


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
          "coverage": {"sample_experiment": False}}
    assert rr._is_blocked(ok) is False                        # explicit + consistent
    assert rr._is_blocked({**ok, "low_confidence": True}) is True


def test_module_blocks_on_provenance_match_but_missing_gate():
    """Lift file matches provenance but lacks gate fields → still blocked (no fail-open)."""
    cf = _full_control_file("G1")
    # provenance matches (G1) but no recommendations_blocked / low_confidence keys.
    lift = {"source": {"features_generated_at": "G1"},
            "coverage": {"sample_experiment": False}, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, lift=lift)
    assert out["recommendations_blocked"] is True


def test_verdict_requires_ci_above_one():
    """A CI straddling 1.0 is unresolved → NOISE, never VALIDATED/WEAK."""
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    assert rfl._verdict(1.5, 20, 20, [0.2, 10.0]) == "NOISE"   # straddles 1.0
    assert rfl._verdict(2.0, 20, 20, [1.2, 3.0]) == "VALIDATED"  # CI above 1
    assert rfl._verdict(1.3, 25, 25, [1.05, 1.8]) == "WEAK"      # CI above 1, mild
    assert rfl._verdict(0.5, 20, 20, [0.2, 0.8]) == "CONTRARIAN"  # CI below 1
    assert rfl._verdict(0.5, 20, 20, [0.2, 1.3]) == "NOISE"       # straddles → not contrarian


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


def main() -> int:
    tests = [test_matched_is_not_blocked, test_missing_by_threshold_blocks,
             test_missing_one_label_blocks, test_stale_provenance_blocks,
             test_missing_lift_file_blocks, test_stale_lift_provenance_blocks,
             test_coverage_gate_blocks_underpowered,
             test_verdict_zero_controls_is_insufficient,
             test_report_is_blocked_failclosed,
             test_module_blocks_on_provenance_match_but_missing_gate,
             test_verdict_requires_ci_above_one,
             test_sanitize_blocked_handles_raw_and_malformed]
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
