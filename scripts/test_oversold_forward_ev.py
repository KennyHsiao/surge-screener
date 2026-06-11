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
import pandas as pd

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
              "ev_horizon_net", "win_rate_net", "ev_horizon_net_ci90", "equity_multiple_net",
              "ev_excess_vs_spy", "excess_win_rate", "ev_excess_ci90", "equity_multiple",
              "ev_excess_beta_adj", "excess_beta_adj_win_rate", "ev_excess_beta_adj_ci90"):
        assert prov[f] is None, f"provisional tier leaked {f}={prov[f]}"
    assert prov["equity_curve"] == []
    # at the explicit threshold the strategy fields publish
    mat = ofw._aggregate_tier(_rows(5), T30, min_resolved=5)
    assert mat["mature"] is True and mat["ev_horizon"] is not None
    assert mat["equity_multiple"] is not None and len(mat["equity_curve"]) == 5


def test_excess_gates_on_baseline_sample():
    """Codex C-8 round-3: excess is computed over the baseline-OK subset (excess_n ≤ resolved),
    so a tier that is stock-MATURE but has too few valid SPY rows must NOT publish excess EV/CI —
    excess fields gate on excess_n >= min_resolved (excess_mature), independently of `mature`."""
    rows = []
    for i in range(5):                                   # 5 stock-resolved, only 1 baseline-OK
        rows.append({"entry_date": f"2026-01-{i + 1:02d}",
                     "tiers": {T30: {"resolved": True, "baseline_ok": i == 0, "hit": True,
                                     "horizon_return": 0.10,
                                     "excess_return": 0.05 if i == 0 else None}}})
    agg = ofw._aggregate_tier(rows, T30, min_resolved=5)
    assert agg["mature"] is True and agg["ev_horizon"] is not None      # stock side publishes
    assert agg["excess_mature"] is False and agg["excess_n"] == 1
    for f in ("ev_excess_vs_spy", "excess_win_rate", "ev_excess_ci90"):
        assert agg[f] is None, f"underpowered excess leaked {f}={agg[f]}"
    # with a full baseline the excess side publishes too
    for r in rows:
        r["tiers"][T30]["baseline_ok"] = True
        r["tiers"][T30]["excess_return"] = 0.05
    agg2 = ofw._aggregate_tier(rows, T30, min_resolved=5)
    assert agg2["excess_mature"] is True and agg2["ev_excess_vs_spy"] is not None


def test_bootstrap_ci_is_seeded_and_deterministic():
    """C-8 deferred (iii): ci90 is now a SEEDED bootstrap percentile CI — two calls on the
    same data must agree (per-call fresh rng → order-independent), the CI must bracket the
    mean, and a single observation degenerates to a point CI (never None/crash)."""
    xs = [0.10, -0.10, 0.60, 0.05, -0.02]
    b1, b2 = ofw._mean_block(xs), ofw._mean_block(list(xs))
    assert b1["ci90"] == b2["ci90"], "bootstrap CI not deterministic across calls"
    lo, hi = b1["ci90"]
    assert lo <= b1["ev"] <= hi
    assert ofw._mean_block([0.07])["ci90"] == [0.07, 0.07]


def test_net_of_cost_published_beside_gross():
    """C-8 deferred (iv): net-of-cost EV uses the DISCLOSED round-trip assumption — a
    +0.4% gross winner flips to a net loser at the 0.5% assumption; equity compounds net."""
    rows = [{"entry_date": f"2026-01-{i + 1:02d}",
             "tiers": {T30: {"resolved": True, "baseline_ok": True, "hit": False,
                             "horizon_return": 0.004, "excess_return": 0.001}}}
            for i in range(5)]
    agg = ofw._aggregate_tier(rows, T30, min_resolved=5)
    assert abs(agg["ev_horizon"] - 0.004) < 1e-9
    assert abs(agg["ev_horizon_net"] - (0.004 - ofw.COST_ROUND_TRIP)) < 1e-9
    assert agg["win_rate_horizon"] == 1.0 and agg["win_rate_net"] == 0.0   # win flips net
    # published value is rounded to 4dp — compare against the rounded expectation
    assert agg["equity_multiple_net"] == round((1 + 0.004 - ofw.COST_ROUND_TRIP) ** 5, 4)
    assert agg["equity_multiple"] > agg["equity_multiple_net"]


def test_beta_adjusted_excess():
    """C-8 deferred (ii): with a pre-entry beta supplied, each tier publishes
    horizon - beta*spy_horizon; without one the field is None while the β=1 excess
    stays published; a blocked baseline blocks the beta-adjusted leg too."""
    close, spy = _path()
    out = ofw.evaluate_entry(close, spy, beta=2.0)
    assert abs(out[T30]["excess_return_beta_adj"] - 0.0) < 1e-9        # 0.10 - 2*0.05
    assert abs(out[T50]["excess_return_beta_adj"] - 0.40) < 1e-9       # 0.60 - 2*0.10
    out2 = ofw.evaluate_entry(close, spy)                              # no beta
    assert out2[T30]["excess_return_beta_adj"] is None
    assert out2[T30]["excess_return"] is not None
    out3 = ofw.evaluate_entry(close, np.array([], dtype=float), beta=2.0)
    assert out3[T30]["excess_return_beta_adj"] is None                 # no baseline


def test_realized_beta():
    """Pure beta: stock returns exactly 2x SPY's -> beta 2.0; too-short / zero-variance /
    NaN-degraded inputs fail to None (no noisy beta), NaN pairs drop without bias."""
    spy_px, stk_px = [400.0], [100.0]
    for i in range(120):
        r = 0.01 if i % 2 == 0 else -0.005
        spy_px.append(spy_px[-1] * (1 + r))
        stk_px.append(stk_px[-1] * (1 + 2 * r))
    s, m = np.asarray(stk_px), np.asarray(spy_px)
    assert abs(ofw.realized_beta(s, m) - 2.0) < 1e-9
    assert ofw.realized_beta(s[:30], m[:30]) is None                   # < min_obs
    assert ofw.realized_beta(np.linspace(100, 110, 121), np.full(121, 400.0)) is None  # var 0
    m2 = m.copy(); m2[10:15] = np.nan                                   # holes drop in pairs
    assert abs(ofw.realized_beta(s, m2) - 2.0) < 1e-9


def test_pit_membership_gate():
    """C-8 deferred (i): three-state fail-closed membership — True/False inside the
    vendored snapshot's range, None (excluded) beyond it or on a malformed date."""
    import sp500_membership as spm
    g = ofw._pit_membership
    assert g("NVDA", "2025-08-01") is True
    assert g("ZZZZNOTATICKER", "2025-08-01") is False
    beyond = "2099-01-01"
    assert beyond > spm.SNAPSHOT_THROUGH
    assert g("NVDA", beyond) is None         # post-snapshot: UNKNOWN, never assumed
    assert g("NVDA", None) is None


def test_resolve_real_pandas_reindex_integration():
    """C-8 deferred (v): drive _resolve through the REAL pandas DatetimeIndex/reindex
    machinery (the unit tests use hand-built arrays) — a short SPY tail must arrive as
    NaN (no ffill) and block ONLY the baseline of the tiers it can't cover, the
    pre-entry beta must come out exact (stock built as 2x SPY's daily returns), and
    entry-day alignment must hold."""
    dates = pd.bdate_range("2025-01-06", periods=161)
    e = 100                                                  # entry at index 100
    spy_px, stk_px = [400.0], [100.0]
    for i in range(e):
        r = 0.01 if i % 2 == 0 else -0.005
        spy_px.append(spy_px[-1] * (1 + r))
        stk_px.append(stk_px[-1] * (1 + 2 * r))
    X, S = stk_px[-1], spy_px[-1]                            # entry-day closes
    stk = stk_px + [X] * 60
    stk[e + 20], stk[e + 40], stk[e + 60] = X * 1.10, X * 1.20, X * 1.30
    spy = spy_px + [S] * 25                                  # SPY tail ends at entry+25
    spy[e + 20] = S * 1.05
    df_stock = pd.DataFrame({"Close": stk}, index=dates)
    df_spy = pd.DataFrame({"Close": spy}, index=dates[:e + 26])
    orig_fetch = ofw.rr._hist_auto_adjust_false
    orig_cache = dict(ofw._SPY_CACHE)
    ofw._SPY_CACHE.clear()
    ofw.rr._hist_auto_adjust_false = lambda t, period="2y": (df_spy if t == "SPY" else df_stock)
    try:
        r = ofw._resolve({"ticker": "TEST", "entry_date": str(dates[e].date())})
    finally:
        ofw.rr._hist_auto_adjust_false = orig_fetch
        ofw._SPY_CACHE.clear()
        ofw._SPY_CACHE.update(orig_cache)
    assert r is not None
    assert abs(r["beta"] - 2.0) < 1e-3                       # pre-entry-only, exact by design
    t30 = r["tiers"][T30]
    assert t30["resolved"] is True and t30["baseline_ok"] is True
    assert abs(t30["horizon_return"] - 0.10) < 1e-9
    assert abs(t30["spy_horizon_return"] - 0.05) < 1e-9
    assert abs(t30["excess_return"] - 0.05) < 1e-9
    assert abs(t30["excess_return_beta_adj"] - 0.0) < 1e-9   # 0.10 - 2.0*0.05
    for lbl, hz in ((T40, 0.20), (T50, 0.30)):               # SPY NaN tail: stock leg only
        tt = r["tiers"][lbl]
        assert tt["resolved"] is True and tt["baseline_ok"] is False
        assert abs(tt["horizon_return"] - hz) < 1e-9
        assert tt["excess_return"] is None and tt["excess_return_beta_adj"] is None


def test_publish_guard_blocks_hollow_summary():
    """Codex stop-time review + C-8b adversarial round 1: the publish guard must refuse
    (a) entries>0 but zero resolved, (b) any collapse below 90% of the committed count —
    including the EXACT-half and just-over-half cases the old /2 rule passed, (c) a
    partial outage when NO prior artifact exists (the entry-coverage floor); while
    allowing the bootstrap empty state, normal attrition, and small populations."""
    g = ofw._publish_guard
    # zero-resolve rule
    assert g(96, 0, 90) is not None           # wholesale outage
    assert g(96, 0, None) is not None         # outage with no prior artifact
    # prev-ratchet at 90% (round-1: /2 was too loose)
    assert g(96, 4, 90) is not None           # severe collapse
    assert g(96, 45, 90) is not None          # EXACT half — old rule passed this
    assert g(96, 52, 90) is not None          # just over half — old rule passed this
    assert g(96, 80, 90) is not None          # 89% of prev — still below the 90% ratchet
    assert g(100, 95, 90) is None             # >= 90% of prev AND >= 70% coverage
    # entry-coverage floor (round-1: no-prior-artifact escape)
    assert g(150, 80, None) is not None       # 53% coverage, no prior — now blocks
    assert g(100, 69, None) is not None       # just under the 70% floor
    assert g(100, 71, None) is None           # just over the floor
    assert g(150, 150, None) is None          # first real run, full coverage
    # bootstrap / small populations
    assert g(0, 0, None) is None              # no scans yet -> 0-entry summary ok
    assert g(8, 2, 5) is None                 # prev<10, entries<20: only zero-rule applies
    assert g(19, 3, None) is None             # below PUBLISH_BOOTSTRAP_ENTRIES: floor off


def test_scan_coverage_guard():
    """Codex C-8b rounds 1+2 [HIGH]: the scan publish gate is COVERAGE-based — every
    outage shape must block regardless of cause: mid-scan throttle, truncated-history
    degradation (fetch_failed=0, short_history high), an 'almost 20%' failure day, and
    zero-scanned for ANY reason; while clean/normal-attrition days and full-coverage
    smoke runs pass."""
    import oversold_reversal_scan as osc
    g = osc._coverage_guard         # (scanned, fetch_failed, short_history, stale_history, attempted)
    assert g(0, 5, 0, 0, 1500) is not None       # wholesale rate-limit
    assert g(0, 0, 1500, 0, 1500) is not None    # round-2: truncated frames, fetch_failed=0
    assert g(0, 0, 0, 0, 1500) is not None       # zero scanned, no counted cause — still blocks
    assert g(50, 1450, 0, 0, 1500) is not None   # round-1: throttle after 50 good fetches
    assert g(1280, 220, 0, 0, 1500) is not None  # round-2: ~15% missing slipped the old rate ceiling
    assert g(1100, 0, 400, 0, 1500) is not None  # 27% short-history degradation
    assert g(900, 0, 0, 600, 1500) is not None   # round-5: long-but-STALE histories en masse
    assert g(1340, 80, 40, 40, 1500) is not None # mixed causes, 89% coverage — below the floor
    assert g(1450, 30, 10, 10, 1500) is None     # normal attrition (96.7%)
    assert g(1500, 0, 0, 0, 1500) is None        # clean day
    assert g(0, 0, 0, 0, 0) is None              # empty universe (degenerate, nothing to write)
    assert g(6, 0, 0, 0, 6) is None              # full-coverage smoke run passes
    assert g(4, 2, 0, 0, 6) is not None          # tiny smoke run with failures fails loud too


def test_scan_output_path_guard():
    """Codex C-8b round 6 [HIGH]: requiring --output for backtests left an escape — the
    caller could point --output AT the canonical files. Any test run (--date or --limit)
    must use an explicit NON-canonical path; full live runs are unaffected."""
    import oversold_reversal_scan as osc
    g = osc._output_path_guard
    can_dated = str(osc.OUT_DIR / "scan_2026-03-01.json")
    can_latest = str(osc.OUT_DIR / "latest.json")
    assert g("2026-03-01", 0, None) is not None          # backtest, no output
    assert g(None, 6, None) is not None                  # limit smoke, no output (round-6 next-step)
    assert g("2026-03-01", 0, can_dated) is not None     # the exact round-6 escape
    assert g("2026-03-01", 0, can_latest) is not None    # pointed at latest.json
    assert g(None, 6, can_latest) is not None            # smoke pointed at latest.json
    assert g("2026-03-01", 0, "/tmp/backtest.json") is None   # proper redirected backtest
    assert g(None, 6, "/tmp/smoke.json") is None              # proper redirected smoke
    assert g(None, 0, None) is None                      # full live run — canonical writes ok


def test_scan_freshness_guard():
    """Codex C-8b round 5 [HIGH]: a stale required leg (SPY/VIX) would backdate the
    authoritative market date and overwrite a HISTORICAL scan_<date>.json — live mode
    refuses legs older than the calendar tolerance (weekend+holiday cushion)."""
    import oversold_reversal_scan as osc
    g = osc._freshness_guard
    today = pd.Timestamp("2026-06-11")
    assert g("SPY", pd.Timestamp("2026-06-10"), today) is None    # normal T+1 lag
    assert g("SPY", pd.Timestamp("2026-06-06"), today) is None    # long weekend, 5 days ok
    assert g("SPY", pd.Timestamp("2026-06-04"), today) is not None  # 7 days — stale source
    assert g("^VIX", pd.Timestamp("2026-01-14"), today) is not None  # months stale


def test_tier_ratchet_guard():
    """Codex C-8b round 3 [HIGH]: horizon-TRUNCATED histories keep price_resolvable flat
    (base close usable) while per-tier resolved counts collapse — the per-tier ratchet
    must block a >10% collapse of ANY counter (resolved / excess_n / excess_beta_adj_n,
    so a SPY-leg outage can't silently None-out published excess stats either)."""
    g = ofw._tier_ratchet_guard
    prev = {T30: {"resolved": 50, "excess_n": 40, "excess_beta_adj_n": 30, "hits": 20}}
    ok = {T30: {"resolved": 50, "excess_n": 40, "excess_beta_adj_n": 30, "hits": 20}}
    assert g(prev, ok) is None                                          # flat is fine
    assert g(prev, {T30: {**ok[T30], "resolved": 3}}) is not None       # stock-leg collapse
    assert g(prev, {T30: {**ok[T30], "excess_n": 2}}) is not None       # SPY-leg collapse
    assert g(prev, {T30: {**ok[T30], "excess_beta_adj_n": 0}}) is not None  # beta-leg collapse
    # round-4: hits collapse while ALL sample counters stay flat (intra-window NaN shape;
    # Codex confirmed prev hits 50 -> 0 passed the old three-counter guard)
    assert g(prev, {T30: {**ok[T30], "hits": 0}}) is not None
    assert g(prev, {T30: {**ok[T30], "hits": 17}}) is not None          # 85% — below 90%
    assert g(prev, {T30: {**ok[T30], "hits": 18}}) is None              # 90% holds
    assert g(prev, {T30: {**ok[T30], "resolved": 44}}) is not None      # 88% — below 90%
    assert g(prev, {T30: {"resolved": 46, "excess_n": 38,
                          "excess_beta_adj_n": 28, "hits": 19}}) is None  # >=90% everywhere
    assert g({T30: {"resolved": 5, "hits": 5}},
             {T30: {"resolved": 0, "hits": 0}}) is None                 # prior <10: no ratchet
    assert g(None, ok) is None                                          # no prior artifact
    assert g({}, ok) is None                                            # prior lacks the tier


def test_scan_universe_guard():
    """Codex C-8b round 3 [HIGH]: the sp1500 loader can silently degrade to just the
    S&P 500 — a named universe loading below its floor must abort BEFORE scanning, so the
    coverage guard's denominator can't lie."""
    import oversold_reversal_scan as osc
    g = osc._universe_guard
    assert g("sp1500", 1506) is None
    assert g("sp1500", 500) is not None        # the exact round-3 shape
    assert g("sp1500", 1399) is not None       # just under the floor
    assert g("sp500", 200) is not None
    assert g("custom", 5) is None              # no floor for unnamed/custom universes


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
    def _check_tiers(tiers, where):
        for label, t in tiers.items():
            tag = f"{where}/{label}"
            assert "mature" in t, f"{tag}: committed artifact predates the maturity-gate schema"
            assert t["mature"] == (t["resolved"] >= thresh), f"{tag}: mature flag inconsistent"
            if not t["mature"]:
                for f in ("ev_horizon", "median_horizon", "win_rate_horizon", "ev_horizon_ci90",
                          "ev_horizon_net", "win_rate_net", "ev_horizon_net_ci90",
                          "equity_multiple", "equity_multiple_net"):
                    assert t.get(f) is None, f"{tag}: provisional tier leaks {f}={t.get(f)}"
                assert t.get("equity_curve") == [], f"{tag}: provisional tier leaks equity_curve"
            # excess gates SEPARATELY on the baseline sample (Codex C-8 round-3)
            assert "excess_mature" in t, f"{tag}: artifact predates the excess_mature schema"
            assert t["excess_mature"] == (t["excess_n"] >= thresh), f"{tag}: excess_mature inconsistent"
            if not t["excess_mature"]:
                for f in ("ev_excess_vs_spy", "excess_win_rate", "ev_excess_ci90"):
                    assert t.get(f) is None, f"{tag}: underpowered excess leaks {f}={t.get(f)}"
            # beta-adjusted excess gates on ITS OWN (smaller) sample (C-8 deferred (ii))
            assert "excess_beta_adj_mature" in t, f"{tag}: predates the beta-adj schema"
            assert t["excess_beta_adj_mature"] == (t["excess_beta_adj_n"] >= thresh), \
                f"{tag}: excess_beta_adj_mature inconsistent"
            if not t["excess_beta_adj_mature"]:
                for f in ("ev_excess_beta_adj", "excess_beta_adj_win_rate",
                          "ev_excess_beta_adj_ci90"):
                    assert t.get(f) is None, f"{tag}: underpowered beta-adj leaks {f}={t.get(f)}"

    _check_tiers(tiers, "by_tier")
    # the universe-matched point-in-time cohort obeys the SAME gates (C-8 deferred (i))
    cohort = d.get("sp500_pit_cohort")
    assert cohort, "committed summary lacks the sp500_pit_cohort block"
    assert cohort.get("universe_match") is True
    assert cohort.get("membership_snapshot_through"), "cohort lacks the snapshot bound"
    mem = cohort.get("membership") or {}
    assert all(k in mem for k in ("member", "non_member", "unknown")), mem
    assert set(cohort.get("by_tier") or {}) == set(tiers), "cohort tiers mismatch headline tiers"
    _check_tiers(cohort["by_tier"], "sp500_pit_cohort")
    assert isinstance(d.get("cost_assumption_round_trip"), float), "cost assumption undisclosed"


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all forward-EV tests passed")
