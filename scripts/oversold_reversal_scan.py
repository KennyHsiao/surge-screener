#!/usr/bin/env python3
"""Coiled-Base lane scanner (was the "volume-ignition / oversold-reversal" lane).

WHY THE REWRITE — the runway saga, settled:
  * retro_confound_check.py showed the 超賣反轉 module's 4.17x lift is largely a
    %-RUNWAY ARTIFACT (a cheap/beaten-down stock reaches a flat "+X%" target more
    easily). The earlier price-position stratification suggested rvol_ge_2 (volume
    ignition) was the one survivor, so this lane gated on rvol + oversold position.
  * retro_runway_neutral_check.py + lane_runway_check.py then re-scored every signal
    under an ATR-NORMALIZED target (forward move in ATR-multiples, not %). Under that
    runway-free target the old lane COLLAPSES:
        LANE !ma200 & !25%high & rvol : %-lift 6.31 -> ATR-lift 0.84  (no edge)
        rvol_ge_2 alone               : 1.36       -> 0.67           (also an artifact)
    The ONLY signals that hold across BOTH the %-target and the ATR-neutral target,
    with real support, are bb_squeeze and rsi_40_65:
        bb_squeeze & rsi_40_65        : %-lift 2.47 -> ATR-lift 2.39  (support 51)
  So the genuine, runway-INDEPENDENT setup is a QUIET COILED BASE with healthy (not
  overbought) momentum — not "already down / already pumping on volume".

Lane definition (both required — the runway-independent pair):
    bb_squeeze   == True   (Bollinger squeeze — a low-volatility coil / base)
    rsi_40_65    == True   (RSI 40–65 — healthy momentum, not overbought, not broken)

It reuses retro_reconstruct.reconstruct_flags (the SAME flag engine as the retro) and
the cached OHLCV fetch, so the live signal matches what was validated. A tradeability
floor (price + 20d $-volume) keeps it enterable. EXPLORATORY: forward-validated via the
snapshot accumulator (oversold_reversal_forward.py), never auto-scored.

NOTE: filenames/dir keep the legacy "oversold_reversal" name to avoid breaking the
workflow + the accumulated forward data; the lane is now a coiled-base scan.

CLI:
    python scripts/oversold_reversal_scan.py --universe sp1500
    python scripts/oversold_reversal_scan.py --date 2026-03-01 --limit 200   # as-of a past day
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "oversold_reversal"
# Stable lane identity (definition hash) so forward validation never mixes this lane's
# snapshots with a different rule's. Bump when the gate predicate changes.
LANE_ID = "coiled_base.v1.bb_squeeze+rsi_40_65+above_30pct_of_low"
_TRIPLE_KEY = "bb_squeeze & rsi_40_65 & above_30pct_of_low"   # key in lane_runway.json
_VAL_DIR = REPO / "reports" / "retrospective" / "sp500_pit"
MIN_SUPPORT = 20         # below this the runway-neutral lift is too thin to call "validated"
# Fail-closed publish gate for the scan artifacts (Codex C-8b rounds 1+2). Round-1 [HIGH]:
# a throttle kicking in AFTER a few successful fetches passed the old zero-scan guard and
# wrote a degraded day as real. Round-2 [HIGH]: a fetch-failure-RATE-only gate still missed
# (a) truncated-history outages — the provider returns non-empty frames under 200 rows, so
# fetch_failed stays 0 while scanned collapses — and (b) "almost 20%" failure days (~300 of
# sp1500 missing) publishing as complete. The gate is therefore COVERAGE-based: whatever
# the cause (fetch failure, truncation, cutoff filtering), the day publishes only if
# scanned/attempted stays at or above this floor. A normal day scans 97-99% of the
# universe (a handful of delistings + a few thin recent listings); 90% leaves headroom
# for gradual churn while blocking every outage shape seen so far.
MIN_SCAN_COVERAGE = 0.9
# Named-universe load floors (Codex C-8b round-3 [HIGH]: "scan coverage denominator trusts
# a partially loaded universe" — the sp1500 loader can silently return ONLY the S&P 500
# when the MidCap 400 / SmallCap 600 component fetches fail, so attempted=500 and the
# coverage guard sees a perfect 500/500 while two-thirds of the intended universe is
# missing). A named universe that loads below its floor ABORTS before scanning; universes
# without a known floor are not gated here.
UNIVERSE_FLOORS = {"sp1500": 1400, "sp500": 480}

import retro_reconstruct as rr  # noqa: E402 — reuse the validated flag engine
import momentum_options as mo  # noqa: E402 — SAME engine that computes the rsi14/bollinger flags


def _load_hard_filter():
    spec = importlib.util.spec_from_file_location(
        "hard_filter", REPO / "scripts" / "01_hard_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_validation(live_universe: str) -> dict:
    """Read the triple's runway-neutral lift from the committed lane_runway.json (so every
    published number is REPRODUCIBLE, not hardcoded) AND the source sample's fail-closed gate
    from factor_lift.json. Blocked / membership-stale source → the lane stays EXPLORATORY
    (runway_independent_actionable=False); it never presents blocked-sample lift as actionable.
    Never raises."""
    out = {"source": f"lane_runway_check.py · {_VAL_DIR.name}", "signal": _TRIPLE_KEY,
           "pct_lift": None, "atr_neutral_lift": None, "support": None, "neutral_support": None,
           "atr_move_threshold": None, "min_support": MIN_SUPPORT,
           "source_blocked": True, "source_membership_stale": True, "source_snapshot_age_days": None,
           "validated_universe": "sp500_pit",
           "live_universe_matches_validation": live_universe in ("sp500", "sp500_pit")}
    _lr_fp = _fl_fp = None       # events fingerprints for the cross-artifact provenance check
    _lr_feat = _fl_feat = None   # features fingerprints (Codex r8 — events alone is not enough)
    _lr_floor = None             # lane_runway's liquidity floor (Codex r12)
    _fl_floor = None             # factor_lift's effective floor (Codex r14: strict — None if absent)
    try:
        lr = json.loads((_VAL_DIR / "lane_runway.json").read_text(encoding="utf-8"))
        s = (lr.get("signals") or {}).get(_TRIPLE_KEY) or {}
        for k in ("pct_lift", "atr_neutral_lift", "support", "neutral_support"):
            out[k] = s.get(k)
        out["atr_move_threshold"] = lr.get("atr_move_threshold")
        _lr_fp = (lr.get("source") or {}).get("events_generated_at")
        _lr_feat = (lr.get("source") or {}).get("features_generated_at")
        _lr_floor = (lr.get("source") or {}).get("min_dollar_vol")
    except Exception:
        pass
    try:
        fl = json.loads((_VAL_DIR / "factor_lift.json").read_text(encoding="utf-8"))
        cov = fl.get("coverage") or {}
        # Canonical fail-closed gate, NOT the stored bit — a stale/forged artifact
        # (recommendations_blocked=false but membership_stale/delisted_data_gap=true) must
        # still count as blocked so the lane never presents it as actionable (Codex #1).
        import retro_factor_lift as _rfl
        out["source_blocked"] = _rfl.is_recommendations_blocked(fl)
        out["source_membership_stale"] = bool(cov.get("membership_stale"))
        out["source_snapshot_age_days"] = cov.get("snapshot_age_days")
        _fl_fp = (fl.get("source") or {}).get("events_generated_at")
        _fl_feat = (fl.get("source") or {}).get("features_generated_at")
        _fl_floor = (cov.get("liquidity_filter") or {}).get("min_dollar_vol")   # raw (strict below)
    except Exception:
        pass
    # Cross-artifact provenance, ANCHORED to the current surge_features (Codex r8 + r10): the lane
    # NUMBERS (lane_runway) and the GATE (factor_lift) must both descend from the SAME events AND
    # the SAME, CURRENT surge_features generation. Matching only each other lets two stale
    # downstream artifacts (both rebuilt-features-OLD) pass after surge_features is rebuilt. On
    # mismatch / missing fingerprint, stay BLOCKED (fail-closed).
    # Anchor to BOTH the current surge_events AND surge_features (Codex r10 + r11): matching only
    # downstream tokens lets a refreshed-events / stale-downstream trio pass. Require every
    # artifact's events_generated_at == surge_events.generated_at AND features == surge_features.
    _ev_gen = _sf_gen = _sf_events = None
    _ev_art = {}
    try:
        _ev_art = json.loads((_VAL_DIR / "surge_events.json").read_text(encoding="utf-8"))
        _ev_gen = _ev_art.get("generated_at")
    except Exception:
        pass
    # AUTHORITATIVE gate (Codex r18): the surge_events independently imply blocked
    # (survivorship/stale/delisted); a forged lift coverage that flips those safe must not
    # set source_blocked=False. OR it in (missing events ⇒ block).
    try:
        import retro_factor_lift as _rfl2
        if _rfl2.events_implied_block(_ev_art):
            out["source_blocked"] = True
    except Exception:
        out["source_blocked"] = True
    try:
        _sf = json.loads((_VAL_DIR / "surge_features.json").read_text(encoding="utf-8"))
        _sf_gen = _sf.get("generated_at")
        _sf_events = (_sf.get("source") or {}).get("events_generated_at")
    except Exception:
        pass
    out["source_provenance_ok"] = bool(
        _ev_gen and _sf_gen
        # EVENTS anchor: surge_features + factor_lift + lane_runway all descend from current events
        and _sf_events == _ev_gen and _lr_fp == _ev_gen and _fl_fp == _ev_gen
        # FEATURES anchor: gate + lane numbers from the current surge_features
        and _lr_feat == _sf_gen and _fl_feat == _sf_gen
        # LIQUIDITY-FLOOR anchor (Codex r12+r14): the lane numbers must come from the SAME
        # liquidity cohort as the gate. STRICT — both floors must be PRESENT + numeric (a missing
        # floor must not default to 0, else a floor-less artifact passes as unfiltered).
        and isinstance(_lr_floor, (int, float)) and not isinstance(_lr_floor, bool)
        and isinstance(_fl_floor, (int, float)) and not isinstance(_fl_floor, bool)
        and float(_lr_floor) == float(_fl_floor))
    if not out["source_provenance_ok"]:
        out["source_blocked"] = True
    if out["source_snapshot_age_days"] is None:  # factor_lift lacks it → use the audit's age
        try:
            ma = json.loads((_VAL_DIR / "membership_audit.json").read_text(encoding="utf-8"))
            out["source_snapshot_age_days"] = ma.get("snapshot_age_days")
        except Exception:
            pass
    sup = out.get("support") or 0
    atr = out.get("atr_neutral_lift")
    out["meets_min_support"] = sup >= MIN_SUPPORT
    # ACTIONABLE only if a real runway-independent lift, enough support, AND an unblocked,
    # non-stale, SAME-universe source. Otherwise exploratory (fail-closed honesty).
    out["runway_independent_actionable"] = bool(
        atr is not None and atr >= 1.0 and sup >= MIN_SUPPORT
        and not out["source_blocked"] and not out["source_membership_stale"]
        and out["live_universe_matches_validation"])
    return out


def _display_metrics(df: pd.DataFrame, t0: pd.Timestamp) -> dict:
    """Raw numbers for the table (the flags decide membership; these explain why).
    RSI + Bollinger width come from the SAME engine (momentum_options._technical) that
    computes the rsi_40_65 / bb_squeeze gate, so the displayed values can never
    contradict membership (an earlier hand-rolled RSI did — e.g. showed 75 on a name
    the 40–65 gate accepted)."""
    d = df[df.index <= t0]
    close = d["Close"].to_numpy(dtype=float)
    last = float(close[-1])
    ma200 = float(np.mean(close[-200:])) if len(close) >= 200 else None
    hi52 = float(np.max(close[-252:])) if len(close) >= 1 else None
    tech = mo._technical(d) or {}
    rsi = tech.get("rsi14")
    bbw = tech.get("bb_bandwidth")  # (upper-lower)/mid, a fraction
    return {
        "last_price": round(last, 2),
        "rsi14": round(rsi, 1) if isinstance(rsi, (int, float)) else None,
        "bb_width_pct": round(bbw * 100, 1) if isinstance(bbw, (int, float)) else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "pct_vs_ma200": round((last / ma200 - 1.0) * 100, 1) if ma200 else None,
        "pct_from_52w_high": round((last / hi52 - 1.0) * 100, 1) if hi52 else None,
    }


def _avg_dollar_vol(df: pd.DataFrame, t0: pd.Timestamp, n: int = 20) -> float | None:
    """Mean close*volume over the last n sessions ≤ t0 — a tradeability floor so the lane
    (which scans the RAW universe) doesn't surface names a real position couldn't enter."""
    d = df[df.index <= t0]
    if "Volume" not in d or len(d) < n:
        return None
    c = d["Close"].to_numpy(dtype=float)[-n:]
    v = d["Volume"].to_numpy(dtype=float)[-n:]
    return float(np.mean(c * v))


def _required_close(symbol: str, period: str, tries: int = 4, base_sleep: float = 30.0,
                    **history_kwargs) -> pd.Series:
    """Close series for a REQUIRED market leg (SPY/^VIX) with a rate-limit-scale backoff.

    The shared rr._hist_auto_adjust_false retry sleeps 0.4–1.2s — jitter scale, useless
    against Yahoo's tens-of-seconds IP throttle, which killed this scan on its FIRST call
    three consecutive CI days (YFRateLimitError → no scan_*.json → forward accumulation
    stalled). Sleeps 30/60/90s between tries and FAILS LOUD (SystemExit) if the leg never
    arrives: reconstruct_flags can't run without SPY/VIX, and a silently hollow scan that
    still writes latest.json would be worse than a red step."""
    import time
    import yfinance as yf
    last_exc: Exception | None = None
    for attempt in range(tries):
        if attempt:
            time.sleep(base_sleep * attempt)
        try:
            s = yf.Ticker(symbol).history(period=period, **history_kwargs)["Close"].dropna()
            if len(s):
                return s
            last_exc = ValueError(f"empty history for {symbol}")
        except Exception as e:  # noqa: BLE001 — yfinance raises library-specific errors
            last_exc = e
    raise SystemExit(f"[coiled-base] required {symbol} series unavailable "
                     f"after {tries} tries: {last_exc}")


def _universe_guard(universe: str, loaded: int) -> str | None:
    """PURE pre-scan gate: a NAMED universe that loads far below its expected size means a
    partial loader failure (e.g. sp1500 silently degrading to just the S&P 500) — the
    coverage guard's denominator would then lie, so abort BEFORE scanning."""
    floor = UNIVERSE_FLOORS.get(universe)
    if floor and loaded < floor:
        return (f"universe '{universe}' loaded only {loaded} tickers (floor {floor}) — "
                "partial component-loader failure? aborting before scan")
    return None


def scan(universe: str, as_of: str | None, limit: int, period: str = "2y",
         min_price: float = 5.0, min_dollar_vol: float = 5e6,
         throttle: float = 0.1) -> dict:
    import time
    hf = _load_hard_filter()
    tickers = hf.load_universe(universe, "US")
    ureason = _universe_guard(universe, len(tickers))
    if ureason:
        raise SystemExit(f"[coiled-base] ABORT (fail-closed): {ureason}")
    if limit:
        tickers = tickers[:limit]   # deliberate smoke/test truncation — AFTER the floor check

    spy = _required_close("SPY", period, auto_adjust=False)
    vix = _required_close("^VIX", period)
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()

    cutoff = pd.Timestamp(as_of).normalize() if as_of else None
    attempted = len(tickers)
    scanned = 0
    fetch_failed = 0
    short_history = 0
    illiquid_dropped = 0
    matches: list[dict] = []
    for t in tickers:
        if throttle:
            time.sleep(throttle)   # gentle pacing — ~1500 bare calls is what gets IP-throttled
        df = rr._hist_auto_adjust_false(t, period)
        if df is None:
            fetch_failed += 1      # rate-limit / delisted / network — visible, never silent
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        if cutoff is not None:
            df = df[df.index <= cutoff]
        if len(df) < 200:
            short_history += 1     # fetched fine, too little history to flag — not a failure
            continue
        scanned += 1
        t0 = df.index[-1]
        flags = rr.reconstruct_flags(df, spy, vix, t0)
        if not flags:
            continue
        # The lane: a coiled base (Bollinger squeeze) + healthy momentum (RSI 40–65) +
        # off the lows (≥30% above the 52w-low) — the runway-INDEPENDENT triple
        # (lift 3.19 under BOTH the %- and ATR-neutral targets; the old rvol+oversold
        # rule collapsed to 0.84). The off-the-lows term drops value-trap bases at the
        # bottom and roughly halves the match rate vs the bare pair.
        if (flags.get("bb_squeeze") is True and flags.get("rsi_40_65") is True
                and flags.get("above_30pct_of_low") is True):
            # Tradeability floor — a forward hit-rate on names a position can't enter
            # is not meaningful (review finding).
            last = float(df[df.index <= t0]["Close"].iloc[-1])
            adv = _avg_dollar_vol(df, t0)
            if last < min_price or adv is None or adv < min_dollar_vol:
                illiquid_dropped += 1
                continue
            row = {"ticker": t, "as_of": t0.strftime("%Y-%m-%d"),
                   "signal_date": t0.strftime("%Y-%m-%d"),  # forward de-dupe key
                   "avg_dollar_vol_m": round(adv / 1e6, 1)}
            row.update(_display_metrics(df, t0))
            matches.append(row)

    # Tightest coil first (lowest Bollinger width) — the most-compressed bases.
    matches.sort(key=lambda r: (r.get("bb_width_pct") if r.get("bb_width_pct") is not None else 1e9))
    val = _load_validation(universe)
    # as_of_date = the actual MARKET date of the scan (NOT wall-clock now) so the forward
    # validator enters at the signal close, not the next session after a weekend/holiday run.
    market_date = cutoff if cutoff is not None else (
        spy.index[-1] if len(spy) else pd.Timestamp.utcnow().normalize())
    caveats = []
    if val.get("source_blocked") or val.get("source_membership_stale"):
        _age = val.get("source_snapshot_age_days")
        _age_s = f"快照 {_age} 天" if _age is not None else "membership-stale"
        caveats.append(f"驗證來源 sp500_pit 本身 blocked/stale({_age_s})→ lift 僅探索性,以前向驗證為準")
    if not val.get("live_universe_matches_validation"):
        caveats.append(f"驗證宇宙=sp500_pit,本次掃描宇宙={universe}(較廣)→ 尚無同宇宙驗證")
    if not val.get("meets_min_support"):
        caveats.append(f"support {val.get('support')} < 最低門檻 {MIN_SUPPORT}")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": market_date.strftime("%Y-%m-%d"),
        "lane_id": LANE_ID,
        "universe": universe,
        "attempted": attempted,
        "scanned": scanned,
        "fetch_failed": fetch_failed,
        "short_history": short_history,
        "match_count": len(matches),
        "liquidity_filter": {"min_price": min_price, "min_dollar_vol": min_dollar_vol,
                             "illiquid_dropped": illiquid_dropped},
        "module": "coiled_base",
        "definition": "壓縮基底 + 健康動能 + 不在低點:bb_squeeze(布林壓縮)且 RSI 40–65 "
                      "且距 52 週低 ≥30%。%-目標與 ATR-中性目標 lift 在驗證樣本上相同,零漲幅膨脹。",
        "primary_signal": "bb_squeeze & rsi_40_65 & above_30pct_of_low (runway-independent, off-the-lows coiled base)",
        # ACTIONABLE only on an unblocked, non-stale, same-universe, well-supported source;
        # otherwise EXPLORATORY (fail-closed) — never present blocked-sample lift as actionable.
        "runway_independent": bool(val.get("runway_independent_actionable")),
        "validation": val,                 # read from lane_runway.json + factor_lift.json gate
        "validation_caveats": caveats,
        "runway_note": "歷史的『放量+超跌』lane 在 ATR-中性目標下垮掉(6.31 → 0.84;單獨放量 1.36 → "
                       "0.67)。本 lane 三條件的 %-lift 與 ATR-中性 lift 在驗證樣本上相同"
                       f"({val.get('atr_neutral_lift')}),support {val.get('support')}"
                       "(數字讀自 lane_runway.json,可由 lane_runway_check.py 重現)。"
                       + ("⚠ 驗證來源已封鎖/過期或非同宇宙,故僅探索性,以前向命中率為準。" if caveats else ""),
        "exploratory": True,
        "note": "EXPLORATORY — 前向驗證、不自動評分。掃全量宇宙(未經 200DMA 硬濾網),"
                "是篩選器的盲區補充。",
        "candidates": matches,
    }


def _coverage_guard(scanned: int, fetch_failed: int, short_history: int,
                    attempted: int) -> str | None:
    """PURE publish gate for the scan artifacts — refusal reason, or None when safe.

    COVERAGE-based (Codex C-8b round-2): the day publishes only if scanned/attempted
    holds the MIN_SCAN_COVERAGE floor, so EVERY outage shape blocks regardless of cause —
    wholesale rate-limit (fetch_failed high), mid-scan throttle (scanned>0 but low),
    truncated-history degradation (provider returns non-empty frames under 200 rows:
    fetch_failed stays 0, short_history balloons), or any mix. Zero scanned with a
    non-empty universe blocks unconditionally. A refused day writes NOTHING — neither the
    dated forward snapshot nor latest.json — so a degraded scan can never present an
    under-sampled universe as a real day. NOTE: a deep historical --date backtest can
    legitimately trip the floor (older cutoffs leave fewer 200-row histories) — that run
    fails LOUD with this reason rather than silently publishing; rerun with --output.
    """
    if attempted == 0:
        return None                      # degenerate empty universe — nothing to publish
    if scanned == 0:
        return (f"0 of {attempted} tickers scanned "
                f"({fetch_failed} fetch-failed, {short_history} short-history) — outage")
    cov = scanned / attempted
    if cov < MIN_SCAN_COVERAGE:
        return (f"universe coverage {scanned}/{attempted} ({cov:.0%}) below the "
                f"{MIN_SCAN_COVERAGE:.0%} floor ({fetch_failed} fetch-failed, "
                f"{short_history} short-history) — not writing a degraded snapshot")
    return None


def _write_json_atomic(path: Path, payload: dict) -> None:
    """Write via a temp file + os.replace so a crash mid-write can never leave a
    truncated scan_<date>.json / latest.json behind (Codex C-8b round-1)."""
    import os
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Coiled-Base lane scanner (bb_squeeze & rsi_40_65)")
    ap.add_argument("--universe", default="sp1500")
    ap.add_argument("--date", default=None, help="as-of YYYY-MM-DD (default: latest)")
    ap.add_argument("--limit", type=int, default=0, help="cap tickers (0 = all)")
    ap.add_argument("--min-price", type=float, default=5.0,
                    help="tradeability floor: drop candidates under this price")
    ap.add_argument("--min-dollar-vol", type=float, default=5e6,
                    help="tradeability floor: drop candidates under this 20d avg $ volume")
    ap.add_argument("--output", default=None, help="explicit output path")
    ap.add_argument("--throttle", type=float, default=0.1,
                    help="seconds to sleep between per-ticker fetches (rate-limit insurance)")
    args = ap.parse_args()

    payload = scan(args.universe, args.date, args.limit,
                   min_price=args.min_price, min_dollar_vol=args.min_dollar_vol,
                   throttle=args.throttle)
    reason = _coverage_guard(payload["scanned"], payload["fetch_failed"],
                             payload["short_history"], payload["attempted"])
    if reason:
        # A degraded day must FAIL LOUD and write NOTHING (dated scan, latest.json) —
        # the forward snapshots are append-only history; better a missing day than a
        # corrupted one presented as real (Codex C-8b round-1).
        print(f"[coiled-base] ABORT (fail-closed, nothing written): {reason}",
              file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUT_DIR / f"scan_{payload['as_of_date']}.json"
    out = Path(args.output) if args.output else dated
    _write_json_atomic(out, payload)
    if out != dated:
        # An explicit --output (smoke/test run) must NOT promote itself to latest.json —
        # a --limit 6 smoke once clobbered the committed latest with a 6-ticker scan.
        print(f"[coiled-base] note: --output given, latest.json NOT updated")
    else:
        _write_json_atomic(OUT_DIR / "latest.json", payload)
    print(f"[coiled-base] {payload['match_count']}/{payload['scanned']} matched, "
          f"{payload['fetch_failed']} fetch-failed / {payload['attempted']} attempted "
          f"(as of {payload['as_of_date']}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
