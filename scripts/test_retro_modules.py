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
         write_lift: bool = True, events_gen: str = "E1", events_pit: bool = True) -> dict:
    """Write fixtures, run retro_modules.py, return the module_lift payload."""
    feat = {"generated_at": "G1", "source": {"events_generated_at": "E1"}, "features": [
        {"ticker": "AAA", "thresholds_hit": ["+30%/20d"], "flags": _flags(True)},
        {"ticker": "BBB", "thresholds_hit": ["+40%/40d"], "flags": _flags(False)},
    ]}
    # Factor lift NOT blocked by coverage + matching provenance (features AND events), so the
    # only gate under test is the module one (unless a scenario overrides `lift`).
    if lift is None:
        lift = {"source": {"features_generated_at": "G1", "events_generated_at": "E1"},
                "coverage": {"sample_experiment": False, "survivorship_bias": False,
                             "membership_stale": False, "delisted_data_gap": False,
                             # liquidity floor PRESENT + numeric (Codex r14) — matches control floor
                             "liquidity_filter": {"enabled": False, "min_dollar_vol": 0.0}},
                "low_confidence": False, "recommendations_blocked": False, "tables": {}}
    modules = {"modules": [{"name": "M", "factors": {"rvol_ge_2": True}}]}

    (tmp / "surge_features.json").write_text(json.dumps(feat))
    # authoritative surge_events for the same-run anchor (Codex r15) — generated_at == the
    # events fingerprint surge_features self-reports (E1), unless a scenario overrides events_gen.
    # Gate fields = an unblocked point-in-time run (Codex r18 authoritative gate): events must PROVE
    # PIT + not stale + no delisted gap, else events_implied_block force-blocks every consumer.
    (tmp / "surge_events.json").write_text(json.dumps({
        "generated_at": events_gen,
        # events_pit=False ⇒ NOT point-in-time ⇒ events_implied_block True ⇒ force-block (forge test)
        "point_in_time_membership": bool(events_pit),
        "membership_stale": False, "delisted_data_gap": False}))
    (tmp / "control_features.json").write_text(json.dumps(control_features))
    if write_lift:
        (tmp / "factor_lift.json").write_text(json.dumps(lift))
    (tmp / "modules.json").write_text(json.dumps(modules))
    out = tmp / "module_lift.json"
    r = subprocess.run(
        [sys.executable, str(HERE / "retro_modules.py"),
         "--features", str(tmp / "surge_features.json"),
         "--events", str(tmp / "surge_events.json"),
         "--controls", str(tmp / "control_features.json"),
         "--lift", str(tmp / "factor_lift.json"),
         "--modules", str(tmp / "modules.json"),
         "--output", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, f"retro_modules failed: {r.stderr}"
    return json.loads(out.read_text())


def _controls(n: int, rvol: bool) -> list:
    return [{"ticker": f"C{i}", "date": "2025-01-01", "flags": _flags(rvol)} for i in range(n)]


def _full_control_file(features_gen: str = "G1", events_gen: str = "E1",
                       min_dollar_vol: float = 0.0) -> dict:
    return {
        "source": {"features_generated_at": features_gen, "events_generated_at": events_gen,
                   # liquidity floor PRESENT + numeric (Codex r14) — matches factor_lift floor
                   "min_dollar_vol": min_dollar_vol},
        "controls": _controls(10, False),
        "by_threshold": {
            "+30%/20d": {"controls": _controls(10, False)},
            "+40%/40d": {"controls": _controls(10, False)},
        },
    }


def test_ohlcv_cache_roundtrip():
    """The OHLCV cache blob must round-trip to a usable frame (pandas 3.0 StringIO)."""
    import io
    import pandas as pd
    df = pd.DataFrame({"Open": [1.0, 2.0], "High": [1.1, 2.1], "Low": [0.9, 1.9],
                       "Close": [1.5, 2.5], "Volume": [100, 200]},
                      index=pd.to_datetime(["2025-01-01", "2025-01-02"]))
    blob = df.reset_index().to_json(orient="split", date_format="iso")  # like _fetch
    got = pd.read_json(io.StringIO(blob), orient="split")               # like read path
    got = got.set_index(got.columns[0])
    got.index = pd.to_datetime(got.index)
    assert list(got["Close"]) == [1.5, 2.5] and "Open" in got.columns and len(got) == 2


def test_fdr_p_value_is_two_sided():
    """The FDR p-value must be two-sided so CONTRARIAN (depletion) factors are
    significant too — a one-sided enrichment test hands every contrarian factor q=1.
    mt_verdict must demote a contrarian that fails FDR, symmetric with positive calls."""
    sys.path.insert(0, str(HERE))
    import retro_validation_stats as v
    # strong depletion (p_s 26% vs p_c 58%, large n) → tiny two-sided p
    assert v.two_proportion_p(487, 1849, 1300, 2241) < 0.001
    # strong enrichment → tiny p as well
    assert v.two_proportion_p(389, 1849, 290, 2241) < 0.001
    # identical rates → no evidence
    assert v.two_proportion_p(100, 1000, 100, 1000) == 1.0
    # symmetric MT demotion: significant contrarian stays, non-surviving one → NOISE
    assert v.mt_verdict("CONTRARIAN", 0.0) == "CONTRARIAN"
    assert v.mt_verdict("CONTRARIAN", 0.5) == "NOISE"
    assert v.mt_verdict("VALIDATED", 0.5) == "WEAK"


def test_point_in_time_unblocks_when_powered():
    """Point-in-time S&P 500 membership flips survivorship_bias off and UNBLOCKS a powered run
    ONLY when there is no delisted-data gap and the snapshot isn't stale; current-member runs,
    a delisted gap, a stale snapshot, or an underpowered run all still block (C-1 hard-block)."""
    sys.path.insert(0, str(HERE))
    import retro_factor_lift as rfl
    # powered, point-in-time, NO delisted gap, NOT stale → unblocks
    cov, low, blocked, _ = rfl.coverage_gate(
        "sp500_pit", scanned=480, unique_surgers=200, surge_event_count=600,
        control_ticker_count=300, point_in_time=True,
        delisted_data_gap=False, membership_stale=False)
    assert cov["survivorship_bias"] is False and cov["point_in_time_membership"] is True
    assert blocked is False and low is False
    assert rfl.is_recommendations_blocked(
        {"recommendations_blocked": blocked, "low_confidence": low, "coverage": cov}) is False
    # delisted_data_gap HARD-BLOCKS even when powered + point-in-time (C-1 free-data wall)
    _, _, blocked_d, _ = rfl.coverage_gate(
        "sp500_pit", 480, 200, 600, 300, point_in_time=True, delisted_data_gap=True)
    assert blocked_d is True
    # current-member run still always blocks
    cov2, _, blocked2, _ = rfl.coverage_gate("sp1500", 1500, 800, 1800, 600)
    assert cov2["survivorship_bias"] is True and blocked2 is True
    # point-in-time but underpowered (few events) → still blocked on low_confidence
    _, _, blocked3, _ = rfl.coverage_gate(
        "sp500_pit", 480, 5, 10, 300, point_in_time=True)
    assert blocked3 is True
    # point-in-time + powered but STALE membership snapshot → still blocked
    cov4, _, blocked4, _ = rfl.coverage_gate(
        "sp500_pit", 480, 200, 600, 300, point_in_time=True, membership_stale=True)
    assert blocked4 is True and cov4["membership_stale"] is True


def test_validate_modules_catches_config_errors():
    """Unknown factor keys, dup names, and bad min_factors are reported (not silent)."""
    sys.path.insert(0, str(HERE))
    import retro_modules as rm
    factor_defs = {"rvol_ge_2": {}, "price_above_ma200": {}}
    mods = [
        {"name": "Good", "factors": {"rvol_ge_2": True}},
        {"name": "Typo", "factors": {"rvol_ge2": True}},                 # unknown key
        {"name": "Good", "factors": {"price_above_ma200": True}},        # dup name
        {"name": "Bad min", "factors": {"rvol_ge_2": True}, "min_factors": 5},  # out of range
    ]
    probs = rm.validate_modules(mods, factor_defs)
    joined = " | ".join(probs)
    assert "unknown factor" in joined and "rvol_ge2" in joined
    assert "duplicate module name" in joined
    assert "min_factors" in joined
    # A clean config returns no problems.
    assert rm.validate_modules([{"name": "OK", "factors": {"rvol_ge_2": True}}], factor_defs) == []


def test_ui_block_reasons_specific():
    """_block_reasons names the SPECIFIC cause (not a generic 'sample experiment')."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent))
    from ui.retro_analysis import _block_reasons
    r = _block_reasons({"control_match": "partial-fallback", "provenance_ok": False,
                        "coverage": {"survivorship_bias": True, "sample_experiment": False}})
    j = "、".join(r)
    assert "倖存者偏差" in j and "對照基線回退" in j and "stale" in j


def test_ui_provenance_reanchor_blocks_stale():
    """ui re-anchor (Codex r15): a cross-run / floor-less derived artifact is flagged stale, and
    the _stale_provenance marker surfaces in _block_reasons; a same-run floored one stays fresh."""
    sys.path.insert(0, str(HERE.parent))
    from ui.retro_analysis import _provenance_stale, _block_reasons
    fresh = {"source": {"events_generated_at": "E", "features_generated_at": "F"},
             "coverage": {"liquidity_filter": {"min_dollar_vol": 0.0}}}
    assert _provenance_stale(fresh, "E", "F", kind="lift") is False
    assert _provenance_stale(fresh, "E2", "F", kind="lift") is True          # refreshed events
    assert _provenance_stale(fresh, "E", "F2", kind="lift") is True          # refreshed features
    assert _provenance_stale({"source": {"events_generated_at": "E", "features_generated_at": "F"},
                              "coverage": {}}, "E", "F", kind="lift") is True  # floor-less
    mod = {"source": {"events_generated_at": "E", "features_generated_at": "F", "min_dollar_vol": 0.0}}
    assert _provenance_stale(mod, "E", "F", kind="module") is False
    assert _provenance_stale({"source": {"events_generated_at": "E", "features_generated_at": "F"}},
                             "E", "F", kind="module") is True                 # module floor absent
    lat = {"source": {"events_generated_at": "E", "factor_lift_generated_at": "L",
                      "features_generated_at": "F"},
           "coverage": {"liquidity_filter": {"min_dollar_vol": 0.0}}}
    assert _provenance_stale(lat, "E", "F", kind="latest", lift_gen="L") is False
    assert _provenance_stale(lat, "E", "F", kind="latest", lift_gen="OTHER") is True  # lift chain
    # Codex r18 authoritative gate mirror + reason
    from ui.retro_analysis import _events_implied_block
    assert _events_implied_block({"point_in_time_membership": True, "membership_stale": False,
                                  "delisted_data_gap": False}) is False
    assert _events_implied_block({"point_in_time_membership": False}) is True
    assert _events_implied_block({}) is True
    assert any("surge_events 矛盾" in r for r in _block_reasons({"_events_gate_violation": True}))
    # Codex r19: forward re-anchor — FRESHNESS only (no floor, no events-survivorship gate)
    fwd_fresh = {"source": {"events_generated_at": "E", "features_generated_at": "F"}}
    assert _provenance_stale(fwd_fresh, "E", "F", kind="forward") is False
    assert _provenance_stale(fwd_fresh, "E2", "F", kind="forward") is True   # cross-run events
    assert _provenance_stale(fwd_fresh, "E", "F2", kind="forward") is True   # rebuilt features
    assert _provenance_stale({"status": "ready"}, "E", "F", kind="forward") is True  # no source
    # Codex r16: events same, surge_features rebuilt F→F2, latest still on F → stale even though it
    # chains to the (also-stale) lift. The features token must be re-anchored, not just the chain.
    assert _provenance_stale(lat, "E", "F2", kind="latest", lift_gen="L") is True
    # latest without the features token at all → fail closed
    nolatfeat = {"source": {"events_generated_at": "E", "factor_lift_generated_at": "L"},
                 "coverage": {"liquidity_filter": {"min_dollar_vol": 0.0}}}
    assert _provenance_stale(nolatfeat, "E", "F", kind="latest", lift_gen="L") is True
    assert any("不同跑次" in r for r in _block_reasons({"_stale_provenance": True}))


def test_ui_tabs_hard_hide_on_stale_provenance():
    """Codex r20 round-4: _lift_tab/_modules_tab must HARD-HIDE (return before any table/chart) a
    _stale_provenance/_events_gate_violation artifact — banner-then-render leaked lift/verdict —
    and _forward_lift_section must block BEFORE the accumulating branch (no progress-count leak)."""
    sys.path.insert(0, str(HERE.parent))
    from unittest.mock import MagicMock
    from ui import retro_analysis as R
    real_st = R.st
    try:
        # stale lift → error shown, the table picker (radio) is never reached
        R.st = MagicMock()
        R._lift_tab({"tables": {"ALL": {"factors": [{"factor": "x", "lift": 9.9}]}},
                     "_stale_provenance": True}, {}, forward={})
        assert R.st.error.called and not R.st.radio.called
        # forge-blocked module_lift → error shown, no table
        R.st = MagicMock()
        R._modules_tab({"tables": {"ALL": {"modules": [{"factor": "M", "lift": 9.9}]}},
                        "_events_gate_violation": True})
        assert R.st.error.called and not R.st.radio.called
        # stale ACCUMULATING forward → blocked error, NOT the 累積中 info with counts
        R.st = MagicMock()
        R._forward_lift_section({"status": "accumulating", "resolved_snapshots": 42,
                                 "_stale_provenance": True,
                                 "source": {"events_generated_at": "E", "snapshots_sha256": "S"}})
        assert R.st.error.called and not R.st.info.called
    finally:
        R.st = real_st


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
          "coverage": {"sample_experiment": False, "survivorship_bias": False,
                       "membership_stale": False, "delisted_data_gap": False}}
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


def test_module_blocks_on_liquidity_floor_mismatch():
    """factor_lift filtered at floor>0 paired with a floor=0 control pool (same events/features)
    → blocked: module tables were computed on a different liquidity cohort than the gate (r13)."""
    cf = _full_control_file("G1")   # control source has no min_dollar_vol → floor 0
    lift = {"source": {"features_generated_at": "G1", "events_generated_at": "E1"},
            "coverage": {"sample_experiment": False, "survivorship_bias": False,
                         "membership_stale": False, "delisted_data_gap": False,
                         "liquidity_filter": {"min_dollar_vol": 1_000_000.0}},   # gate floor 1M
            "low_confidence": False, "recommendations_blocked": False, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, lift=lift)
    assert out["recommendations_blocked"] is True   # 1M != 0 → lift_ok False → blocked


def test_module_blocks_when_factor_lift_floor_absent():
    """Codex r14 fail-open: factor_lift WITHOUT coverage.liquidity_filter.min_dollar_vol must
    NOT be accepted as 'floor 0'. Provenance + gate fields all match and the control floor is 0,
    but the missing gate floor is unknown → strict_floor None → block (no default-to-zero)."""
    cf = _full_control_file("G1", min_dollar_vol=0.0)
    lift = {"source": {"features_generated_at": "G1", "events_generated_at": "E1"},
            "coverage": {"sample_experiment": False, "survivorship_bias": False,
                         "membership_stale": False, "delisted_data_gap": False},  # NO liquidity_filter
            "low_confidence": False, "recommendations_blocked": False, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, lift=lift)
    assert out["recommendations_blocked"] is True


def test_module_blocks_when_control_floor_absent():
    """Symmetric Codex r14 case: factor_lift records floor 0 but the control pool's source omits
    min_dollar_vol → control floor unknown → strict_floor None → block (no default-to-zero)."""
    cf = _full_control_file("G1")
    cf["source"].pop("min_dollar_vol", None)   # control floor absent
    lift = {"source": {"features_generated_at": "G1", "events_generated_at": "E1"},
            "coverage": {"sample_experiment": False, "survivorship_bias": False,
                         "membership_stale": False, "delisted_data_gap": False,
                         "liquidity_filter": {"min_dollar_vol": 0.0}},
            "low_confidence": False, "recommendations_blocked": False, "tables": {}}
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, lift=lift)
    assert out["recommendations_blocked"] is True


def test_module_blocks_on_refreshed_events_stale_chain():
    """Codex r15 same-run gap: surge_events.json REFRESHED (E2) but the surge_features/control/lift
    triple is internally consistent on the OLD fingerprint (E1). The chain agrees with itself, so
    the self-reported anchor passes — but it no longer descends from the current events. Must BLOCK
    (retro_modules must read the authoritative surge_events.json, not trust the self-report)."""
    cf = _full_control_file("G1", events_gen="E1")     # control on OLD events E1
    with tempfile.TemporaryDirectory() as d:
        # surge_features self-reports E1, lift+control on E1 — but authoritative events = E2.
        out = _run(Path(d), cf, events_gen="E2")
    assert out["provenance_ok"] is False, out["provenance_ok"]
    assert out["recommendations_blocked"] is True


def test_module_blocks_on_forged_coverage_vs_events():
    """Codex r18 forge: an unblocked-coverage factor_lift (same-run, floors match) must STILL block
    when the authoritative surge_events imply blocked (not point-in-time) — the gate can't be
    unblocked by self-reported coverage alone."""
    cf = _full_control_file("G1")
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf, events_pit=False)   # default lift = unblocked coverage
    assert out["recommendations_blocked"] is True


def test_module_blocks_when_surge_events_absent():
    """No authoritative surge_events.json beside the features → no same-run anchor → block."""
    cf = _full_control_file("G1")
    with tempfile.TemporaryDirectory() as d:
        dd = Path(d)
        # build fixtures via _run but then we need surge_events ABSENT — run a bespoke invocation.
        feat = {"generated_at": "G1", "source": {"events_generated_at": "E1"}, "features": [
            {"ticker": "AAA", "thresholds_hit": ["+30%/20d"], "flags": _flags(True)}]}
        (dd / "surge_features.json").write_text(json.dumps(feat))
        (dd / "control_features.json").write_text(json.dumps(cf))
        (dd / "factor_lift.json").write_text(json.dumps(
            {"source": {"features_generated_at": "G1", "events_generated_at": "E1"},
             "coverage": {"sample_experiment": False, "survivorship_bias": False,
                          "membership_stale": False, "delisted_data_gap": False,
                          "liquidity_filter": {"min_dollar_vol": 0.0}},
             "low_confidence": False, "recommendations_blocked": False, "tables": {}}))
        (dd / "modules.json").write_text(json.dumps(
            {"modules": [{"name": "M", "factors": {"rvol_ge_2": True}}]}))
        out_p = dd / "module_lift.json"
        r = subprocess.run(
            [sys.executable, str(HERE / "retro_modules.py"),
             "--features", str(dd / "surge_features.json"),
             "--events", str(dd / "surge_events.json"),   # does NOT exist
             "--controls", str(dd / "control_features.json"),
             "--lift", str(dd / "factor_lift.json"),
             "--modules", str(dd / "modules.json"),
             "--output", str(out_p)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        out = json.loads(out_p.read_text())
    assert out["provenance_ok"] is False
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
          "coverage": {"sample_experiment": False, "survivorship_bias": False,
                       "membership_stale": False, "delisted_data_gap": False}}
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


def test_forward_lift_verbose_data_missing():
    """Free-form data_missing strings (verbose) still mark a dimension None (substring)."""
    sys.path.insert(0, str(HERE))
    import retro_forward_lift as fl
    medians = {c: 5.0 for c in fl.DIM_FACTORS}
    row = {"sentiment": 8, "options_flow": 9, "technical": 8,
           "data_missing": "options_flow — Dimension 6 free data unavailable|"
                           "x_twitter_mention_velocity_48h — no social"}
    flags = fl.dim_flags(row, medians)
    assert flags["options_flow_high"] is None, "verbose options_flow → None"
    assert flags["sentiment_high"] is None, "verbose x_twitter velocity → sentiment None"
    assert flags["technical_high"] is True


def _snapshot_rows(scored: dict) -> list:
    import csv as _csv
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "scored.json").write_text(json.dumps(scored))
        out = tmp / "snap.csv"
        r = subprocess.run(
            [sys.executable, str(HERE / "retro_snapshot.py"),
             "--input", str(tmp / "scored.json"), "--output", str(out)],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return list(_csv.DictReader(open(out))) if out.exists() else []


def test_snapshot_refuses_incomplete_cohort():
    """Partial OR missing-completeness-metadata scans must NOT be snapshotted."""
    cands = [{"ticker": "AAA", "scores": {}}, {"ticker": "BBB", "scores": {}}]
    # explicit partial
    assert _snapshot_rows({"scan_date": "2026-06-03", "total_candidates": 6,
                           "scored_candidates_count": 2, "remaining_unscored": 4,
                           "all_scored": cands}) == []
    # completeness metadata OMITTED → fail closed (refuse)
    assert _snapshot_rows({"scan_date": "2026-06-03", "all_scored": cands}) == []
    # provably complete → snapshotted
    rows = _snapshot_rows({"scan_date": "2026-06-03", "total_candidates": 2,
                           "scored_candidates_count": 2, "remaining_unscored": 0,
                           "all_scored": cands})
    assert len(rows) == 2


def test_parse_coverage_gate_marks_insufficient():
    """A factor known in <50% of an arm is overridden to INSUFFICIENT."""
    sys.path.insert(0, str(HERE))
    import retro_forward_lift as fl
    table = [
        {"factor": "sentiment_high", "verdict": "VALIDATED", "n_surge": 3, "n_control": 30},
        {"factor": "technical_high", "verdict": "WEAK", "n_surge": 28, "n_control": 27},
    ]
    fl.apply_parse_coverage_gate(table, n_pos=30, n_neg=30)
    assert table[0]["verdict"] == "INSUFFICIENT" and table[0]["low_parse_coverage"] is True
    assert table[1]["verdict"] == "WEAK", "well-covered factor unchanged"


def test_snapshot_status_artifact_on_refusal():
    """A refused snapshot writes an observable snapshot_status.json (refused=True)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "scored.json").write_text(json.dumps(
            {"scan_date": "2026-06-03", "all_scored": [{"ticker": "AAA", "scores": {}}]}))
        out = tmp / "snap.csv"
        subprocess.run(
            [sys.executable, str(HERE / "retro_snapshot.py"),
             "--input", str(tmp / "scored.json"), "--output", str(out)],
            capture_output=True, text=True)
        status = json.loads((tmp / "snapshot_status.json").read_text())
        assert status["refused"] is True and status["appended"] == 0


def test_forward_median_excludes_missing():
    """A data_missing placeholder must NOT drag a dimension's cohort median."""
    sys.path.insert(0, str(HERE))
    import retro_forward_lift as fl
    # two rows with real sentiment=8,10 (median 9); one placeholder sentiment=0 marked missing.
    scored = [
        {"row": {"sentiment": 8, "data_missing": ""}},
        {"row": {"sentiment": 10, "data_missing": ""}},
        {"row": {"sentiment": 0, "data_missing": "sentiment — unavailable"}},
    ]
    assert fl.dim_median(scored, "sentiment") == 9.0, "placeholder 0 must be excluded"


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
    tests = [test_validate_modules_catches_config_errors,
             test_ohlcv_cache_roundtrip,
             test_fdr_p_value_is_two_sided,
             test_point_in_time_unblocks_when_powered,
             test_ui_block_reasons_specific,
             test_ui_provenance_reanchor_blocks_stale,
             test_ui_tabs_hard_hide_on_stale_provenance,
             test_matched_is_not_blocked, test_missing_by_threshold_blocks,
             test_missing_one_label_blocks, test_stale_provenance_blocks,
             test_missing_lift_file_blocks, test_stale_lift_provenance_blocks,
             test_coverage_gate_survivorship_always_blocks,
             test_verdict_zero_controls_is_insufficient,
             test_report_is_blocked_failclosed,
             test_module_blocks_on_provenance_match_but_missing_gate,
             test_module_blocks_on_liquidity_floor_mismatch,
             test_module_blocks_when_factor_lift_floor_absent,
             test_module_blocks_when_control_floor_absent,
             test_module_blocks_on_refreshed_events_stale_chain,
             test_module_blocks_on_forged_coverage_vs_events,
             test_module_blocks_when_surge_events_absent,
             test_verdict_wilson_significance,
             test_sanitize_blocked_handles_raw_and_malformed,
             test_verdict_zero_cell_via_wilson,
             test_blocked_report_text_is_deterministic,
             test_exploratory_rejects_inconsistent_metadata,
             test_ui_gate_blocked_failclosed,
             test_forward_lift_missing_dim_is_none,
             test_forward_lift_verbose_data_missing,
             test_snapshot_refuses_incomplete_cohort,
             test_parse_coverage_gate_marks_insufficient,
             test_snapshot_status_artifact_on_refusal,
             test_forward_median_excludes_missing,
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
