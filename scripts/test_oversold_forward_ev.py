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


def test_short_spy_tail_blocks_resolution():
    """If the SPY baseline leg is short, the tier must NOT resolve (else excess would be
    computed off a missing baseline and silently inflate the edge)."""
    close = np.full(61, 100.0)
    spy = np.full(15, 400.0)   # SPY too short for the 20d horizon
    out = ofw.evaluate_entry(close, spy)
    assert out[T30]["resolved"] is False


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
         "tiers": {T30: {"resolved": True, "hit": True, "horizon_return": 0.10,
                         "excess_return": 0.05}}},
        {"entry_date": "2026-01-03",
         "tiers": {T30: {"resolved": True, "hit": False, "horizon_return": -0.10,
                         "excess_return": -0.12}}},
        {"entry_date": "2026-01-02",
         "tiers": {T30: {"resolved": False, "hit": False, "horizon_return": None,
                         "excess_return": None}}},
    ]
    agg = ofw._aggregate_tier(rows, T30)
    assert agg["resolved"] == 2 and agg["hits"] == 1
    assert abs(agg["hit_rate"] - 0.5) < 1e-9
    assert abs(agg["ev_horizon"] - 0.0) < 1e-9          # mean(0.10, -0.10)
    assert abs(agg["ev_excess_vs_spy"] - (-0.035)) < 1e-9  # mean(0.05, -0.12)
    # equity compounds in ENTRY-DATE order: 1.10 then 1.10*0.90 = 0.99
    assert abs(agg["equity_multiple"] - 0.99) < 1e-9
    assert agg["equity_curve"][0][0] == "2026-01-01"
    assert agg["equity_curve"][-1][0] == "2026-01-03"


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all forward-EV tests passed")
