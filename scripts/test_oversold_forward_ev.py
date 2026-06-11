#!/usr/bin/env python3
"""Offline unit tests for the coiled-base forward EV harness (no network).

Pins the strategy-level math so a refactor can't silently reintroduce look-ahead:
  * evaluate_entry — TOUCH (sold-the-top, optimistic) must NOT equal the REALIZED
    hold-to-window-end horizon return; excess is measured vs SPY over the SAME span;
    a half-formed window stays unresolved (no EV counted).
  * _mean_block / _aggregate_tier — EV = mean realized return, equity curve compounds
    in entry-date order, hit-rate is touch-based, excess uses the SPY-aligned leg.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oversold_reversal_forward as ofw

T30, T40, T50 = "+30%/20d", "+40%/40d", "+50%/60d"


def _path():
    """Length-61 stock + SPY paths with KNOWN tier outcomes.
    stock: 100 base, a +40% spike at session 5 (touches every tier), then horizons
    110 / 90 / 160 at sessions 20 / 40 / 60. SPY: 400 base, 420 / 400 / 440 at 20/40/60."""
    close = np.full(61, 100.0)
    close[5] = 140.0          # +40% touch, inside all three windows
    close[20] = 110.0         # +30 tier horizon = +10%
    close[40] = 90.0          # +40 tier horizon = -10%
    close[60] = 160.0         # +50 tier horizon = +60%
    spy = np.full(61, 400.0)
    spy[20] = 420.0           # +5%
    spy[40] = 400.0           # 0%
    spy[60] = 440.0           # +10%
    return close, spy


def test_touch_is_not_horizon():
    """The whole point of EV: a Close that TOUCHED +30% but ended the window at +10% must
    report hit=True yet horizon_return=+0.10 — not +0.30 (no selling-the-top)."""
    close, spy = _path()
    out = ofw.evaluate_entry(close, spy)
    assert out[T30]["hit"] is True
    assert abs(out[T30]["horizon_return"] - 0.10) < 1e-9, out[T30]
    assert out[T30]["horizon_return"] < 0.30   # realized < the touched peak


def test_excess_vs_spy_same_span():
    close, spy = _path()
    out = ofw.evaluate_entry(close, spy)
    # +30 tier: stock +10%, SPY +5% -> excess +5%
    assert abs(out[T30]["spy_horizon_return"] - 0.05) < 1e-9
    assert abs(out[T30]["excess_return"] - 0.05) < 1e-9
    # +40 tier: stock -10%, SPY 0% -> excess -10% (a losing trade vs a flat market)
    assert abs(out[T40]["horizon_return"] + 0.10) < 1e-9
    assert abs(out[T40]["excess_return"] + 0.10) < 1e-9
    # +50 tier: stock +60%, SPY +10% -> excess +50%
    assert abs(out[T50]["excess_return"] - 0.50) < 1e-9


def test_unresolved_window_yields_no_ev():
    """A 10-session path can't resolve the 20d tier -> resolved False, horizon None, so EV
    never counts a half-formed window (touch may already be visible though)."""
    close = np.full(10, 100.0)
    spy = np.full(10, 400.0)
    out = ofw.evaluate_entry(close, spy)
    assert out[T30]["resolved"] is False
    assert out[T30]["horizon_return"] is None
    assert out[T30]["excess_return"] is None


def test_missing_baseline_nulls_excess_but_keeps_horizon():
    """A missing/short SPY leg must NOT throw away the real realized return — the tier still
    RESOLVES (horizon_return is real) but baseline_ok is False so excess/spy_hz are None
    (no stale/zero baseline silently inflating the edge). Covers both the short-array and the
    NaN-tail (real reindex output) shapes."""
    close, _ = _path()                       # close[20] = 110 -> +10% horizon is real
    for spy in (np.full(15, 400.0),                                   # short array
                np.concatenate([np.full(15, 400.0), np.full(46, np.nan)])):  # NaN tail
        out = ofw.evaluate_entry(close, spy)
        assert out[T30]["resolved"] is True
        assert out[T30]["baseline_ok"] is False
        assert abs(out[T30]["horizon_return"] - 0.10) < 1e-9
        assert out[T30]["excess_return"] is None
        assert out[T30]["spy_horizon_return"] is None


def test_nan_horizon_close_unresolves():
    """A NaN at the win-th stock Close (mid-window data gap) must un-resolve the tier so a
    NaN never poisons EV (adversarial review: 'NaN at win-th resolves True')."""
    close, spy = _path()
    close[20] = np.nan
    out = ofw.evaluate_entry(close, spy)
    assert out[T30]["resolved"] is False
    assert out[T30]["horizon_return"] is None


def test_midwindow_nan_does_not_mask_earlier_touch():
    """A NaN partway through the window must NOT hide a +pct touch that already happened
    before it — nanmax, not max (ultrareview). Horizon at win is finite so the tier resolves."""
    close, spy = _path()
    close[3] = 135.0      # +35% touch early in the window
    close[5] = np.nan     # later data gap — must not propagate into the touch test
    out = ofw.evaluate_entry(close, spy)
    assert out[T30]["hit"] is True
    assert out[T30]["resolved"] is True


def test_empty_spy_blocks_baseline_not_resolution():
    """Empty SPY (spy_base NaN) blocks the baseline but not resolution; pins the NaN guard so
    a refactor of `spy_base > 0` to `!= 0` can't silently reintroduce the look-ahead."""
    close, _ = _path()
    out = ofw.evaluate_entry(close, np.array([], dtype=float))
    assert out[T30]["resolved"] is True
    assert out[T30]["baseline_ok"] is False
    assert out[T30]["excess_return"] is None


def test_mean_block():
    b = ofw._mean_block([0.10, -0.10, 0.60])
    assert b["n"] == 3
    assert abs(b["ev"] - 0.20) < 1e-9
    assert abs(b["median"] - 0.10) < 1e-9
    assert abs(b["win_rate"] - (2 / 3)) < 1e-3
    assert ofw._mean_block([])["ev"] is None


def test_aggregate_tier_equity_and_hitrate():
    rows = [
        {"entry_date": "2026-01-01",
         "tiers": {T30: {"resolved": True, "baseline_ok": True, "hit": True,
                         "horizon_return": 0.10, "excess_return": 0.05}}},
        {"entry_date": "2026-01-03",
         "tiers": {T30: {"resolved": True, "baseline_ok": True, "hit": False,
                         "horizon_return": -0.10, "excess_return": -0.12}}},
        # resolved horizon but NO baseline (SPY gap) -> counts toward EV, NOT excess:
        {"entry_date": "2026-01-04",
         "tiers": {T30: {"resolved": True, "baseline_ok": False, "hit": True,
                         "horizon_return": 0.30, "excess_return": None}}},
        {"entry_date": "2026-01-02",
         "tiers": {T30: {"resolved": False, "baseline_ok": False, "hit": False,
                         "horizon_return": None, "excess_return": None}}},
    ]
    agg = ofw._aggregate_tier(rows, T30, min_resolved=1)   # math test: bypass the maturity gate
    assert agg["resolved"] == 3 and agg["hits"] == 2
    assert agg["hit_rate"] == round(2 / 3, 4)           # 0.6667 (rounded 4dp)
    assert abs(agg["ev_horizon"] - 0.10) < 1e-9         # mean(0.10, -0.10, 0.30) = 0.10
    # excess only over the 2 baseline_ok rows; the SPY-gap row is excluded:
    assert agg["excess_n"] == 2
    assert abs(agg["ev_excess_vs_spy"] - (-0.035)) < 1e-9  # mean(0.05, -0.12)
    # equity compounds ALL resolved in ENTRY-DATE order: 1.10 * 0.90 * 1.30
    assert abs(agg["equity_multiple"] - (1.10 * 0.90 * 1.30)) < 1e-9
    assert agg["equity_curve"][0][0] == "2026-01-01"
    assert agg["equity_curve"][-1][0] == "2026-01-04"


def test_provisional_tier_suppresses_ev():
    """Codex C-8 review: below MIN_RESOLVED the maturity gate must be REAL, not a verdict label —
    a 1-99-trade tier publishes NO strategy fields (EV/median/win-rate/CI/excess/equity all None or
    empty) while counts + touch hit-rate stay visible; at the threshold the fields publish."""
    def _rows(k):
        return [{"entry_date": f"2026-01-{i % 28 + 1:02d}",
                 "tiers": {T30: {"resolved": True, "baseline_ok": True, "hit": True,
                                 "horizon_return": 0.10, "excess_return": 0.05}}}
                for i in range(k)]
    # 3 resolved < default MIN_RESOLVED (100) → PROVISIONAL ⇒ strategy fields suppressed
    prov = ofw._aggregate_tier(_rows(3), T30)
    assert prov["mature"] is False and prov["resolved"] == 3
    assert prov["hit_rate"] is not None and prov["wilson90"] is not None   # progress stays visible
    for f in ("ev_horizon", "median_horizon", "win_rate_horizon", "ev_horizon_ci90",
              "ev_excess_vs_spy", "excess_win_rate", "ev_excess_ci90", "equity_multiple"):
        assert prov[f] is None, f"provisional tier leaked {f}={prov[f]}"
    assert prov["equity_curve"] == []
    # at the explicit threshold the strategy fields publish
    mat = ofw._aggregate_tier(_rows(5), T30, min_resolved=5)
    assert mat["mature"] is True and mat["ev_horizon"] is not None
    assert mat["equity_multiple"] is not None and len(mat["equity_curve"]) == 5


def test_committed_summary_obeys_maturity_schema():
    """Codex C-8 round-2: the SHIPPED reports/oversold_reversal/validation_summary.json must carry
    the maturity-gate schema — every tier has a `mature` key, and a provisional tier (resolved <
    min_resolved_for_verdict) exposes NO strategy fields (the generator fix is useless if a stale
    pre-fix artifact stays committed). Skips cleanly if the artifact is absent."""
    import json
    p = Path(__file__).resolve().parent.parent / "reports" / "oversold_reversal" / "validation_summary.json"
    if not p.exists():
        print("  (skip — no committed validation_summary.json)")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    thresh = d.get("min_resolved_for_verdict")
    assert isinstance(thresh, int) and thresh > 0, d.get("min_resolved_for_verdict")
    tiers = d.get("by_tier") or {}
    assert tiers, "committed summary has no by_tier section"
    for label, t in tiers.items():
        assert "mature" in t, f"{label}: committed artifact predates the maturity-gate schema"
        assert t["mature"] == (t["resolved"] >= thresh), f"{label}: mature flag inconsistent"
        if not t["mature"]:
            for f in ("ev_horizon", "median_horizon", "win_rate_horizon", "ev_horizon_ci90",
                      "ev_excess_vs_spy", "excess_win_rate", "ev_excess_ci90", "equity_multiple"):
                assert t.get(f) is None, f"{label}: provisional tier leaks {f}={t.get(f)}"
            assert t.get("equity_curve") == [], f"{label}: provisional tier leaks equity_curve"


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all forward-EV tests passed")
