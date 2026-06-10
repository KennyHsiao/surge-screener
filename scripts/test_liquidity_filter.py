#!/usr/bin/env python3
"""Offline unit tests for the Phase 1c symmetric liquidity filter (no network).

Two pieces, pinned so a refactor can't reintroduce look-ahead or make the filter asymmetric:
  * retro_reconstruct.avg_dollar_vol_20d — point-in-time mean(Close*Volume) over the window
    ENDING at k; must ignore data after k (no look-ahead) and return None on a short/NaN window.
  * retro_factor_lift._filter_by_liquidity — ONE predicate applied identically to surge events
    and controls; a None/missing value fails the floor; off (≤0) is passthrough.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_reconstruct as rr
import retro_factor_lift as rfl

advol = rr.avg_dollar_vol_20d


def test_basic_window_mean():
    close = np.full(22, 10.0)
    volume = np.full(22, 100.0)
    # k=20, window=20 -> indices 1..20, each 10*100=1000 -> mean 1000
    assert advol(close, volume, 20, window=20) == 1000.0


def test_no_lookahead_ignores_future():
    """A huge price AFTER k must not change the value at k."""
    close = np.concatenate([np.full(21, 10.0), np.array([9.99e9])])  # spike at index 21
    volume = np.full(22, 100.0)
    assert advol(close, volume, 20, window=20) == 1000.0  # uses only indices 1..20


def test_first_resolvable_index():
    close = np.full(20, 10.0)
    volume = np.full(20, 100.0)
    assert advol(close, volume, 19, window=20) == 1000.0  # lo=0, full 20-window
    assert advol(close, volume, 18, window=20) is None    # lo=-1 -> not enough history


def test_custom_window():
    close = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    volume = np.ones(5)
    # k=3, window=3 -> indices 1,2,3 -> 2,3,4 -> mean 3.0
    assert advol(close, volume, 3, window=3) == 3.0


def test_short_window_and_oob_return_none():
    close = np.full(10, 10.0)
    volume = np.full(10, 100.0)
    assert advol(close, volume, 5, window=20) is None    # not enough history
    assert advol(close, volume, 100, window=20) is None  # k out of bounds


def test_nan_in_window_returns_none():
    close = np.full(22, 10.0)
    close[10] = np.nan
    volume = np.full(22, 100.0)
    assert advol(close, volume, 20, window=20) is None


# ── symmetric filter ──────────────────────────────────────────────────────────────────
flt = rfl._filter_by_liquidity


def test_off_is_passthrough_even_with_none():
    recs = [{"avg_dollar_vol_20d": 5e6}, {"avg_dollar_vol_20d": None}, {}]
    kept, dropped = flt(recs, 0.0)
    assert dropped == 0 and len(kept) == 3      # disabled -> nothing dropped, None kept


def test_floor_drops_below_and_keeps_boundary():
    recs = [{"avg_dollar_vol_20d": 2e6}, {"avg_dollar_vol_20d": 1e6},
            {"avg_dollar_vol_20d": 9.99e5}]
    kept, dropped = flt(recs, 1e6)
    assert dropped == 1                          # only the 9.99e5 drops
    assert {r["avg_dollar_vol_20d"] for r in kept} == {2e6, 1e6}  # == floor is kept (>=)


def test_none_or_missing_or_bool_fails_floor():
    recs = [{"avg_dollar_vol_20d": None}, {}, {"avg_dollar_vol_20d": True},
            {"avg_dollar_vol_20d": 5e6}]
    kept, dropped = flt(recs, 1e6)
    assert dropped == 3 and len(kept) == 1       # None / missing / bool all fail; only 5e6 survives


def test_symmetric_same_verdict_both_arms():
    """The keep/drop decision is a pure function of (avg_dollar_vol_20d, floor) — identical
    whether the record is a surge event or a control. Same adv values -> same outcome."""
    advals = [5e6, 1.0e6, 9.0e5, 2.0e5, None]
    surge = [{"arm": "surge", "avg_dollar_vol_20d": v} for v in advals]
    ctrl = [{"arm": "ctrl", "avg_dollar_vol_20d": v} for v in advals]
    floor = 1e6
    s_kept, s_drop = flt(surge, floor)
    c_kept, c_drop = flt(ctrl, floor)
    assert s_drop == c_drop == 3                                 # 9e5, 2e5, None drop in both
    assert ([r["avg_dollar_vol_20d"] for r in s_kept]
            == [r["avg_dollar_vol_20d"] for r in c_kept] == [5e6, 1.0e6])


# ── symmetric surge windows (the adversarial-review blocker) ────────────────────────────
def _events():
    return [
        {"ticker": "AAA", "surge_start": "2025-01-02", "peak_date": "2025-01-20",
         "thresholds_hit": ["+30%/20d"]},
        {"ticker": "AAA", "surge_start": "2025-06-02", "peak_date": "2025-06-20",
         "thresholds_hit": ["+30%/20d"]},   # a SECOND AAA surge
        {"ticker": "BBB", "surge_start": "2025-03-03", "peak_date": "2025-03-15",
         "thresholds_hit": ["+50%/60d"]},
    ]


def test_windows_off_uses_all_events():
    wall, wthr = rfl._build_surge_windows(_events(), None)
    assert len(wall["AAA"]) == 2 and len(wall["BBB"]) == 1
    assert len(wthr["+30%/20d"]["AAA"]) == 2


def test_windows_on_excludes_dropped_surges():
    """When the filter survives only AAA's FIRST surge + BBB, the dropped AAA surge's window
    must NOT exclude controls — else the control arm shrinks more than the positive arm."""
    surviving = {("AAA", "2025-01-02"), ("BBB", "2025-03-03")}   # AAA 2025-06-02 dropped
    wall, wthr = rfl._build_surge_windows(_events(), surviving)
    assert len(wall["AAA"]) == 1                       # only the surviving AAA surge
    assert wall["AAA"][0][0] == pd.Timestamp("2025-01-02")
    assert len(wall["BBB"]) == 1
    assert len(wthr["+30%/20d"]["AAA"]) == 1           # the dropped surge's window is gone


def test_from_cache_rejects_filtered_cache():
    """--from-cache with NO --min-dollar-vol must REFUSE a control_features cache that WAS
    liquidity-filtered (source.min_dollar_vol > 0) — else unfiltered surgers would be scored
    against a filtered control pool (asymmetric, hidden by liquidity_filter.enabled=false).
    Codex round-5 regression."""
    import json as _json
    import subprocess
    import tempfile
    GEN = "2026-06-06T00:00:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(_json.dumps({"generated_at": GEN, "universe": "sp500_pit"}))
        (d / "surge_features.json").write_text(_json.dumps({
            "generated_at": "F1", "source": {"events_generated_at": GEN}, "factor_defs": {},
            "features": [{"ticker": "AAA", "thresholds_hit": [], "flags": {}}]}))
        # the cache was filtered at $1M — events AND features provenance MATCH (same run) so
        # ONLY the liquidity mismatch can trip the guard.
        (d / "control_features.json").write_text(_json.dumps({
            "generated_at": "C1",
            "source": {"events_generated_at": GEN, "features_generated_at": "F1",
                       "min_dollar_vol": 1_000_000.0},
            "controls": [], "by_threshold": {}}))
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_factor_lift.py"),
             "--from-cache", "--events", str(d / "surge_events.json"),
             "--features", str(d / "surge_features.json"),
             "--output", str(d / "factor_lift.json")],
            capture_output=True, text=True)
        assert r.returncode == 1, f"expected refusal, got {r.returncode}: {r.stdout}{r.stderr}"
        assert "filtered at min_dollar_vol" in r.stderr, r.stderr


def test_from_cache_rejects_missing_floor():
    """Codex r18: --from-cache must REFUSE a control cache whose source.min_dollar_vol is ABSENT /
    non-numeric — the old `or 0.0` collapse let a filtered cache with an unrecorded floor replay as
    'unfiltered' (asymmetric, biased-up lift). strict_floor must fail closed on the missing floor."""
    import json as _json
    import subprocess
    import tempfile
    GEN = "2026-06-06T00:00:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(_json.dumps({"generated_at": GEN, "universe": "sp500_pit"}))
        (d / "surge_features.json").write_text(_json.dumps({
            "generated_at": "F1", "source": {"events_generated_at": GEN}, "factor_defs": {},
            "features": [{"ticker": "AAA", "thresholds_hit": [], "flags": {}}]}))
        # events + features provenance MATCH; the floor key is simply ABSENT (legacy/partial write).
        (d / "control_features.json").write_text(_json.dumps({
            "generated_at": "C1",
            "source": {"events_generated_at": GEN, "features_generated_at": "F1"},  # NO min_dollar_vol
            "controls": [], "by_threshold": {}}))
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_factor_lift.py"),
             "--from-cache", "--events", str(d / "surge_events.json"),
             "--features", str(d / "surge_features.json"),
             "--output", str(d / "factor_lift.json")],
            capture_output=True, text=True)
        assert r.returncode == 1, f"expected refusal, got {r.returncode}: {r.stdout}{r.stderr}"
        assert "no recorded source.min_dollar_vol" in r.stderr, r.stderr


def test_from_cache_rejects_stale_features():
    """--from-cache must also fail closed when the cached controls were built from a DIFFERENT
    surge_features generation than the current one (same events, rebuilt features) — else current
    surger flags get scored against stale control flags (Codex round-6)."""
    import json as _json
    import subprocess
    import tempfile
    GEN = "2026-06-06T00:00:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(_json.dumps({"generated_at": GEN, "universe": "sp500_pit"}))
        (d / "surge_features.json").write_text(_json.dumps({
            "generated_at": "F-NEW", "source": {"events_generated_at": GEN}, "factor_defs": {},
            "features": [{"ticker": "AAA", "thresholds_hit": [], "flags": {}}]}))
        # same events, NO liquidity filter, but built from an OLDER surge_features (F-OLD).
        (d / "control_features.json").write_text(_json.dumps({
            "generated_at": "C1",
            "source": {"events_generated_at": GEN, "features_generated_at": "F-OLD",
                       "min_dollar_vol": 0.0},
            "controls": [], "by_threshold": {}}))
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_factor_lift.py"),
             "--from-cache", "--events", str(d / "surge_events.json"),
             "--features", str(d / "surge_features.json"),
             "--output", str(d / "factor_lift.json")],
            capture_output=True, text=True)
        assert r.returncode == 1, f"expected refusal, got {r.returncode}: {r.stdout}{r.stderr}"
        assert "stale vs the current surgers" in r.stderr, r.stderr


def test_from_cache_rejects_missing_threshold():
    """--from-cache must fail closed when the cache's by_threshold doesn't cover a CURRENT
    threshold label — else that tier's table silently uses the ALL baseline (Codex round-7)."""
    import json as _json
    import subprocess
    import tempfile
    GEN = "2026-06-06T00:00:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(_json.dumps({"generated_at": GEN, "universe": "sp500_pit"}))
        # current surgers cleared the +30%/20d tier ...
        (d / "surge_features.json").write_text(_json.dumps({
            "generated_at": "F1", "source": {"events_generated_at": GEN}, "factor_defs": {},
            "features": [{"ticker": "AAA", "thresholds_hit": ["+30%/20d"], "flags": {}}]}))
        # ... but the cache has NO per-threshold set for it (events/features/floor all match).
        (d / "control_features.json").write_text(_json.dumps({
            "generated_at": "C1",
            "source": {"events_generated_at": GEN, "features_generated_at": "F1", "min_dollar_vol": 0.0},
            "controls": [{"ticker": "C0", "date": "2025-01-01", "flags": {}}], "by_threshold": {}}))
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_factor_lift.py"),
             "--from-cache", "--events", str(d / "surge_events.json"),
             "--features", str(d / "surge_features.json"),
             "--output", str(d / "factor_lift.json")],
            capture_output=True, text=True)
        assert r.returncode == 1, f"expected refusal, got {r.returncode}: {r.stdout}{r.stderr}"
        assert "per-threshold control sets" in r.stderr, r.stderr


def test_runway_loader_filters_surgers_symmetrically():
    """When control_features was liquidity-filtered (source.min_dollar_vol>0), the runway loader
    must apply the SAME floor to the surger arm — else unfiltered positives vs filtered controls
    (the #5 asymmetry in the runway path, Codex r11)."""
    import json as _json
    import tempfile
    import retro_runway_neutral_check as rnc
    E, F = "2026-06-06T00:00:00+00:00", "2026-06-06T00:01:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_features.json").write_text(_json.dumps({
            "generated_at": F, "source": {"events_generated_at": E}, "features": [
                {"ticker": "AAA", "surge_start": "2025-01-02", "flags": {}, "avg_dollar_vol_20d": 5e6},
                {"ticker": "BBB", "surge_start": "2025-02-02", "flags": {}, "avg_dollar_vol_20d": 1e5},
            ]}))
        (d / "control_features.json").write_text(_json.dumps({
            "source": {"events_generated_at": E, "features_generated_at": F, "min_dollar_vol": 1e6},
            "controls": [{"ticker": "CCC", "date": "2025-01-01", "flags": {}}], "by_threshold": {}}))
        pool, fp, sf_gen, min_dv = rnc._load_pool(d)
        surgers = [r for r in pool if r["orig_surge"]]
        assert min_dv == 1e6
        assert {r["ticker"] for r in surgers} == {"AAA"}, surgers   # BBB (1e5 < 1e6) dropped


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all liquidity-filter tests passed")
