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
    assert r["bear_telemetry"]["all_pool_distinct_episodes"] == 1
    # examples must ALSO be suppressed (no dated 歷史前例 leakage when the floor fails)
    assert r["examples"] == [] and r.get("examples_suppressed") == "insufficient_bearish_analogs"


def test_unresolved_episode_does_not_unlock_floor():
    # 2 RESOLVED episodes (10 non-overlapping 60d windows, >2yr span) + 1 UNRESOLVED 3rd episode (fwd=None).
    # all-pool episode count = 3, but the per-horizon MATURED count = 2 → must FAIL CLOSED (Codex fail-open fix).
    resolved = []
    for ep, base, yr in [("epA", 0, 2010), ("epB", 1000, 2013)]:
        for j in range(5):
            resolved.append({"date": f"{yr}-0{1 + j}-15", "sess_i": base + j * 60, "regime": "correction",
                             "vix": 30, "vix_bucket": "elevated", "episode_id": ep,
                             "fwd_20d": -0.04, "fwd_40d": -0.06, "fwd_60d": -0.08,
                             "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.15, "fwd_mdd_60d": -0.2})
    unresolved = [{"date": "2016-01-15", "sess_i": 2000, "regime": "correction", "vix": 30,
                   "vix_bucket": "elevated", "episode_id": "epC", "fwd_20d": None, "fwd_40d": None,
                   "fwd_60d": None, "fwd_mdd_20d": None, "fwd_mdd_40d": None, "fwd_mdd_60d": None}]
    r = m.retrieve_regime_analogs(resolved + unresolved, "correction", "elevated")
    assert r["bear_telemetry"]["all_pool_distinct_episodes"] == 3      # telemetry sees all 3
    assert r["fwd_60d"]["status"] == "insufficient_bearish_analogs"    # matured gate sees only 2 → fail closed
    assert r["fwd_60d"]["matured_episodes"] == 2, r["fwd_60d"]


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


def test_missing_vix_bucket_fails_closed():
    # an ample pool that WOULD pass with a concrete bucket must FAIL CLOSED when vix_bucket is omitted
    # (a 看空 query without a VIX bucket can never read the full correction pool — v7 §1b).
    amp = [{"date": f"20{12 + (j // 4) * 2:02d}-01-{(j % 28) + 1:02d}", "sess_i": j * 60,
            "regime": "correction", "vix": 30, "vix_bucket": "elevated", "episode_id": f"ep{j % 4}",
            "fwd_20d": -0.04, "fwd_40d": -0.06, "fwd_60d": -0.08,
            "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.15, "fwd_mdd_60d": -0.2} for j in range(11)]
    r = m.retrieve_regime_analogs(amp, "correction", None)
    assert r["fwd_60d"]["status"] == "insufficient_bearish_analogs"
    assert r["fwd_60d"]["reason"] == "missing_vix_bucket"
    assert r["bearish_analog_suppressed"] is True and r["examples"] == []


def test_corpus_inadequacy_gate():
    eps4 = [{"episode_id": t, "trough": t, "ongoing": False}
            for t in ("2009-03-09", "2018-12-24", "2020-03-23", "2022-10-12")]
    ok_daily = [{"date": "2008-01-02", "vix_bucket": "normal"},   # ~18y span, concrete VIX
                {"date": "2026-06-01", "vix_bucket": "elevated"}]
    assert m.corpus_inadequacy(ok_daily, eps4) is None
    assert m.corpus_inadequacy([], eps4) == "empty_daily"
    short = [{"date": "2021-01-02", "vix_bucket": "normal"},       # ~5y bull-only window
             {"date": "2026-06-01", "vix_bucket": "normal"}]
    assert m.corpus_inadequacy(short, eps4).startswith("span_")
    few = eps4[:2] + [{"episode_id": "x", "ongoing": True}]        # ongoing doesn't count as closed
    assert m.corpus_inadequacy(ok_daily, few).startswith("closed_correction_episodes_")
    # a degraded VIX leg (sessions stuck in the "unknown" bucket) must refuse — here the LATEST-row check
    # fires first (it precedes the run/rate checks by design: today's read is what the forecaster uses)
    dead_vix = [{"date": "2008-01-02", "vix_bucket": "unknown"},
                {"date": "2026-06-01", "vix_bucket": "unknown"}]
    assert m.corpus_inadequacy(dead_vix, eps4) == "latest_vix_unknown_or_stale"


def test_vix_tail_and_concentrated_outage_gates():
    eps4 = [{"episode_id": t, "trough": t, "ongoing": False}
            for t in ("2009-03-09", "2018-12-24", "2020-03-23", "2022-10-12")]

    def mk(n, unknown_at=()):
        rows = []
        for i in range(n):
            d = (pd.Timestamp("2008-01-01") + pd.Timedelta(days=i)).date().isoformat()
            rows.append({"date": d, "vix_bucket": "unknown" if i in unknown_at else "normal"})
        rows[-1]["date"] = "2026-06-01"  # keep the ≥15y span
        return rows

    # latest row unknown (current outage) refuses even though aggregate rate is tiny (1/5000)
    tail = mk(5000, unknown_at={4999})
    assert m.corpus_inadequacy(tail, eps4) == "latest_vix_unknown_or_stale"
    # concentrated 25-session dead window mid-series (0.5% < 1% aggregate) must still refuse via the run cap
    mid = mk(5000, unknown_at=set(range(2000, 2025)))
    assert m.corpus_inadequacy(mid, eps4).startswith("unknown_vix_run_")
    # scattered unknowns above the aggregate threshold (latest concrete, runs short) → rate reason
    scattered = mk(300, unknown_at=set(range(10, 300, 50)))   # 6/300 = 2% in singletons
    assert m.corpus_inadequacy(scattered, eps4).startswith("unknown_vix_rate_")
    # clean corpus still passes
    assert m.corpus_inadequacy(mk(5000), eps4) is None


def test_main_refuses_tail_vix_outage(tmp_path=None):
    # full VIX history EXCEPT the last 8 sessions (feed died this week) → main() exits 1, writes nothing (r8)
    import tempfile, os
    close = _synthetic_gspc().resample("B").interpolate()
    vix = pd.Series(18.0, index=close.index)[:-8]
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: (close, vix)
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_main_refuses_to_publish_empty_vix(tmp_path=None):
    # valid 18y close series with 4 real drawdown episodes BUT an empty VIX series → every session lands in
    # vix_bucket="unknown" / regime="range" → main() must exit 1 and write NOTHING (Codex r6).
    import tempfile, os
    close = _synthetic_gspc().resample("B").interpolate()          # business-daily, 2007→2024, real bears
    empty_vix = pd.Series(dtype=float)
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: (close, empty_vix)
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_missing_required_bear_refused():
    # a 2011→present corpus: ≥15y span, 3+ closed episodes (2018/2020/2022), concrete VIX — but NO GFC.
    # span+count alone would pass; the named-cycle check must refuse (Codex r9).
    daily = [{"date": "2011-01-03", "vix_bucket": "normal"}, {"date": "2026-06-01", "vix_bucket": "normal"}]
    eps_no_gfc = [{"episode_id": t, "trough": t, "ongoing": False}
                  for t in ("2018-12-24", "2020-03-23", "2022-10-12")]
    r = m.corpus_inadequacy(daily, eps_no_gfc)
    assert r == "missing_required_bears:GFC_2008", r
    # all four present → passes
    eps_full = eps_no_gfc + [{"episode_id": "2009-03-09", "trough": "2009-03-09", "ongoing": False}]
    assert m.corpus_inadequacy([{"date": "2008-01-02", "vix_bucket": "normal"},
                                {"date": "2026-06-01", "vix_bucket": "normal"}], eps_full) is None


def test_warmup_clipped_trough_does_not_count():
    # eps holds a GFC trough (2009-03-09) but the published daily starts AFTER it (200DMA warmup ate it) —
    # the named-cycle check must NOT count a trough that no published row covers (Codex r10).
    daily = [{"date": "2009-06-08", "vix_bucket": "normal"}, {"date": "2026-06-01", "vix_bucket": "normal"}]
    eps = [{"episode_id": t, "trough": t, "ongoing": False}
           for t in ("2009-03-09", "2018-12-24", "2020-03-23", "2022-10-12")]
    r = m.corpus_inadequacy(daily, eps)
    assert r == "missing_required_bears:GFC_2008", r


def test_main_refuses_warmup_clipped_gfc(tmp_path=None):
    # CLI regression: a late-2008 fetch — the GFC trough sits inside the 200-session warmup, so the
    # published corpus has no GFC row even though eps claims one ⇒ main() exits 1, writes nothing.
    import tempfile, os
    close = _synthetic_gspc().resample("B").interpolate()
    close = close[close.index >= "2008-09-01"]
    vix = pd.Series(18.0, index=close.index)
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: (close, vix)
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_main_refuses_to_publish_short_fetch(tmp_path=None):
    # monkeypatch the fetch to a short bull-only series → main() must exit 1 and write NOTHING (Codex r5).
    import tempfile, os
    vals = list(np.linspace(100, 130, 320))                        # ~15 months, no 10% drawdown
    idx = pd.bdate_range("2025-01-01", periods=len(vals))
    short = (pd.Series(vals, index=idx), pd.Series(15.0, index=idx))
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: short
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_main_refuses_single_early_vix_print(tmp_path=None):
    # one valid VIX print at the start then nothing: ffill would coat every later session with a stale value,
    # so staleness must be measured on RAW coverage → main() exits 1 and writes nothing (Codex r7).
    import tempfile, os
    close = _synthetic_gspc().resample("B").interpolate()
    one_print = pd.Series([15.0], index=close.index[:1])
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: (close, one_print)
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_main_refuses_large_mid_series_vix_gap(tmp_path=None):
    # a multi-year hole in the middle of an otherwise-full VIX series must also refuse (stale window >1%).
    import tempfile, os
    close = _synthetic_gspc().resample("B").interpolate()
    full_vix = pd.Series(18.0, index=close.index)
    gappy = full_vix.copy()
    gappy.loc["2015-01-01":"2018-01-01"] = np.nan          # ~3y dead window
    gappy = gappy.dropna()
    saved_fetch, saved_argv = m._gspc_vix, sys.argv
    out = os.path.join(tempfile.mkdtemp(), "regime_history.json")
    try:
        m._gspc_vix = lambda period: (close, gappy)
        sys.argv = ["market_regime_history.py", "--output", out]
        rc = m.main()
    finally:
        m._gspc_vix, sys.argv = saved_fetch, saved_argv
    assert rc == 1 and not os.path.exists(out)


def test_small_vix_gap_tolerated():
    # a ≤MAX_VIX_STALE_SESSIONS holiday-sized gap stays ffilled — daily rows keep concrete buckets.
    idx = pd.bdate_range("2020-01-01", periods=300)
    close = pd.Series(np.linspace(100, 110, 300), index=idx)
    vix = pd.Series(16.0, index=idx).drop(idx[250:253])     # 3-session gap
    daily = m.build_daily(sv=(close, vix))
    assert daily and all(r["vix_bucket"] == "normal" for r in daily)


def test_unknown_vix_bucket_fails_closed():
    # the truthy "unknown" sentinel (_vix_bucket when VIX is missing/non-finite) must NOT act as a matched
    # key: an otherwise-ample 'unknown' correction pool stays suppressed (Codex r4 fail-open).
    amp = [{"date": f"20{12 + (j // 4) * 2:02d}-01-{(j % 28) + 1:02d}", "sess_i": j * 60,
            "regime": "correction", "vix": None, "vix_bucket": "unknown", "episode_id": f"ep{j % 4}",
            "fwd_20d": -0.04, "fwd_40d": -0.06, "fwd_60d": -0.08,
            "fwd_mdd_20d": -0.1, "fwd_mdd_40d": -0.15, "fwd_mdd_60d": -0.2} for j in range(11)]
    r = m.retrieve_regime_analogs(amp, "correction", "unknown")
    assert r["fwd_60d"]["status"] == "insufficient_bearish_analogs"
    assert r["fwd_60d"]["reason"] == "missing_vix_bucket"
    assert r["bearish_analog_suppressed"] is True and r["examples"] == []


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
