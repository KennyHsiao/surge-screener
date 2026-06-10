#!/usr/bin/env python3
"""Offline, deterministic tests for market_regime_history.py (design v7, P1).

No network: exercises the correction-episode labeller, forward-MDD, and the episode-based bearish
fail-closed gate on synthetic series. The REAL multi-cycle coverage (GFC/2018-Q4/2020/2022) is verified by
running `python scripts/market_regime_history.py --period 20y` (logged in the P1 commit message); here we
prove the labeller SEGMENTS multiple distinct bears + that the bearish analog gate fails closed.

Run:  .venv/bin/python scripts/test_market_regime_history.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import market_regime_history as m  # noqa: E402


def _series(vals):
    return pd.Series(list(map(float, vals)),
                     index=pd.date_range("2010-01-01", periods=len(vals), freq="D"))


def _synthetic_gspc():
    """Minimized monthly ^GSPC-like series preserving the REAL peaks/troughs/reclaims of the four required
    bears (deterministic, offline). Linear-interpolated between waypoints so the ONLY ≥10% drawdown-and-reclaim
    episodes are GFC / 2018-Q4 / 2020 / 2022."""
    waypts = [("2007-06", 1503), ("2007-10", 1549), ("2008-11", 896), ("2009-03", 760),
              ("2013-03", 1569), ("2018-09", 2914), ("2018-12", 2507), ("2019-04", 2946),
              ("2020-02", 3386), ("2020-03", 2585), ("2020-08", 3500), ("2022-01", 4516),
              ("2022-09", 3586), ("2024-01", 4846), ("2024-06", 5460)]
    pts = [(pd.Timestamp(d + "-01"), float(v)) for d, v in waypts]
    months = pd.date_range(pts[0][0], pts[-1][0], freq="MS")
    yv = np.interp([mdt.value for mdt in months], [p[0].value for p in pts], [p[1] for p in pts])
    return pd.Series(yv, index=months)


def test_episode_drawdown_then_reclaim():
    eps = m.label_episodes(_series([100, 105, 110, 100, 95, 100, 108, 111]))
    assert len(eps) == 1 and eps[0]["ongoing"] is False
    assert eps[0]["drawdown_pct"] <= -0.10 and eps[0]["episode_id"] == eps[0]["trough"]


def test_shallow_dip_is_not_an_episode():
    assert m.label_episodes(_series([100, 105, 110, 103, 108, 112])) == []


def test_ongoing_trailing_bear():
    eps = m.label_episodes(_series([100, 105, 110, 100, 90, 85]))
    assert len(eps) == 1 and eps[0]["ongoing"] is True


def test_four_distinct_episodes_segmented():
    # four ≥10% drops each fully reclaimed before the next → FOUR distinct episodes (anti-merge proof,
    # the deterministic offline proxy for the GFC/2018Q4/2020/2022 fixture coverage).
    leg = [100, 110, 96, 112]  # peak 110 → -12.7% → reclaim >110
    eps = m.label_episodes(_series(leg * 4))
    assert len(eps) == 4, [e["episode_id"] for e in eps]
    assert len({e["episode_id"] for e in eps}) == 4


def test_real_cycle_fixture_episodes():
    # pinned fixtures: the labeller MUST find exactly the four real bears, with stable trough-date ids,
    # all ≥10% drawdown, non-overlapping (end_i strictly ordered).
    eps = m.label_episodes(_synthetic_gspc())
    years = sorted({e["trough"][:4] for e in eps})
    assert years == ["2009", "2018", "2020", "2022"], [(e["episode_id"], e["drawdown_pct"]) for e in eps]
    assert len(eps) == 4 and len({e["episode_id"] for e in eps}) == 4
    assert all(e["drawdown_pct"] <= -0.10 for e in eps)
    ends = [e["end_i"] for e in eps]
    assert ends == sorted(ends), ends  # non-overlapping in time order
    assert eps[0]["episode_id"] == eps[0]["trough"]  # stable id == trough date


def test_fwd_mdd():
    cl = np.array([100, 100, 90, 95, 100], dtype=float)  # -10% dip inside the window
    assert abs(m._fwd_mdd(cl, 0, 4) - (-0.10)) < 1e-9
    assert m._fwd_mdd(cl, 3, 4) is None  # window runs off the end → unresolved


def test_bearish_floor_fail_closed():
    thin = [{"date": f"2020-03-{d:02d}", "sess_i": d, "regime": "correction", "vix": 40,
             "vix_bucket": "panic", "episode_id": "2020-03-23",
             "fwd_20d": -0.05, "fwd_40d": -0.02, "fwd_60d": 0.03,
             "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.12, "fwd_mdd_60d": -0.12} for d in range(1, 9)]
    r = m.retrieve_regime_analogs(thin, "correction", "panic")
    assert r["fwd_60d"]["status"] == "insufficient_bearish_analogs"
    assert r["bearish_analog_suppressed"] is True
    assert r["bear_telemetry"]["distinct_episodes"] == 1
    # examples must ALSO be suppressed (no dated 歷史前例 leakage when the floor fails)
    assert r["examples"] == [] and r.get("examples_suppressed") == "insufficient_bearish_analogs"


def test_vix_bucket_filter_fails_closed():
    # a thin 'panic' bucket must NOT borrow 'elevated' rows to unlock — the matched key is VIX-bucket-strict.
    panic = [{"date": f"2020-03-{d:02d}", "sess_i": d, "regime": "correction", "vix": 40,
              "vix_bucket": "panic", "episode_id": "2020-03-23",
              "fwd_20d": -0.05, "fwd_40d": -0.02, "fwd_60d": 0.03,
              "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.12, "fwd_mdd_60d": -0.12} for d in range(1, 6)]
    elevated = [{"date": f"20{12 + (j // 4) * 2:02d}-01-{(j % 28) + 1:02d}", "sess_i": 100 + j * 60,
                 "regime": "correction", "vix": 30, "vix_bucket": "elevated", "episode_id": f"ep{j % 4}",
                 "fwd_20d": -0.04, "fwd_40d": -0.06, "fwd_60d": -0.08,
                 "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.15, "fwd_mdd_60d": -0.2} for j in range(11)]
    r = m.retrieve_regime_analogs(panic + elevated, "correction", "panic")
    assert r["n_sessions"] == 5 and r["fwd_60d"]["status"] == "insufficient_bearish_analogs", r
    assert r["all_bucket_sessions"] == 16  # all-bucket count is telemetry only, never the unlock


def test_bearish_floor_pass():
    amp = [{"date": f"20{12 + (j // 4) * 2:02d}-01-{(j % 28) + 1:02d}", "sess_i": j * 60,
            "regime": "correction", "vix": 30, "vix_bucket": "elevated", "episode_id": f"ep{j % 4}",
            "fwd_20d": -0.04, "fwd_40d": -0.06, "fwd_60d": -0.08,
            "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.15, "fwd_mdd_60d": -0.2} for j in range(11)]
    r = m.retrieve_regime_analogs(amp, "correction", "elevated")
    assert "status" not in r["fwd_60d"] and r["fwd_60d"]["mean"] == -0.08
    assert r["bearish_analog_suppressed"] is False
    assert r["fwd_60d"]["worst_mdd"] == -0.2  # tail metric surfaced


def test_non_correction_regime_has_no_bearish_gate():
    pool = [{"date": f"2021-01-{(j % 28) + 1:02d}", "sess_i": j, "regime": "rally", "vix": 14,
             "vix_bucket": "low", "episode_id": None, "fwd_20d": 0.02, "fwd_40d": 0.03, "fwd_60d": 0.05,
             "fwd_mdd_20d": -0.02, "fwd_mdd_40d": -0.03, "fwd_mdd_60d": -0.03} for j in range(8)]
    r = m.retrieve_regime_analogs(pool, "rally", "low")
    assert "status" not in r["fwd_60d"] and "bearish_analog_suppressed" not in r


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"PASS — {len(tests)} offline tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
