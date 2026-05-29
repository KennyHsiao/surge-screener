#!/usr/bin/env python3
"""
Free options flow analysis using yfinance options chains.
Covers Dimension 6a (call/put ratio, V/OI) and partial 6d (GEX proxy).
Sweeps (6b) and dark pool (6c) require paid data — scored 0 here.

Max possible score: ~11/20 (vs 20/20 with Unusual Whales).
"""

import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path


def _cached(namespace: str, params, ttl: float, compute, should_cache=None):
    """Best-effort disk cache; falls back to plain compute() if unavailable."""
    try:
        try:
            from cache import get_or_compute
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cache", Path(__file__).parent / "cache.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            get_or_compute = mod.get_or_compute
        return get_or_compute(namespace, params, ttl, compute,
                              should_cache=should_cache)
    except Exception:
        return compute()


def analyze_options(ticker: str) -> dict:
    """Analyze options chain (free yfinance). Cached 15min — chains change
    intraday but not by the second; avoids re-fetch per pipeline pass / dashboard
    click. Only successful (available=True) results are cached."""
    return _cached("options", {"ticker": ticker.upper()}, 900,
                   lambda: _analyze_options(ticker),
                   should_cache=lambda v: isinstance(v, dict) and v.get("available"))


def _analyze_options(ticker: str) -> dict:
    """
    Analyze options chain for a ticker using free yfinance data.
    Returns a dict with scores and supporting data for Dimension 6.
    """
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
    except Exception as e:
        return _no_data(str(e))

    if not expirations:
        return _no_data("No options available")

    # Pick expiration closest to 30 DTE (most relevant for surge prediction)
    today = datetime.now()
    target_dte = 30
    best_exp = None
    best_diff = 999
    for exp in expirations:
        exp_dt = datetime.strptime(exp, "%Y-%m-%d")
        diff = abs((exp_dt - today).days - target_dte)
        if diff < best_diff:
            best_diff = diff
            best_exp = exp

    # Also grab nearest weekly for short-term signal
    nearest_exp = expirations[0]

    try:
        chain_30d = tk.option_chain(best_exp)
        chain_near = tk.option_chain(nearest_exp)
    except Exception as e:
        return _no_data(str(e))

    calls_30d = chain_30d.calls
    puts_30d = chain_30d.puts
    calls_near = chain_near.calls
    puts_near = chain_near.puts

    # Current stock price
    try:
        spot = tk.fast_info.last_price
    except Exception:
        spot = float(calls_30d["lastPrice"].iloc[0]) if not calls_30d.empty else 0

    if not spot or spot <= 0:
        return _no_data("Cannot determine spot price")

    # ── 6a: Unusual Call Activity (max 8 pts) ──
    score_6a, detail_6a = _score_6a(calls_30d, puts_30d, calls_near, puts_near, spot)

    # ── 6b: Sweeps & Blocks (max 6 pts) — NOT available free ──
    score_6b = 0
    detail_6b = "Sweep/block data requires paid feed (Unusual Whales). Scored 0."

    # ── 6c: Dark Pool (max 3 pts) — NOT available free ──
    score_6c = 0
    detail_6c = "Dark pool data requires paid feed. Scored 0."

    # ── 6d: GEX / Gamma Proxy (max 3 pts) ──
    score_6d, detail_6d = _score_6d(calls_30d, puts_30d, spot)

    total = score_6a + score_6b + score_6c + score_6d

    # Objective chain views for the UI (no extra fetch — reuse the chains above).
    chain_summary = _chain_summary(calls_30d, puts_30d, spot)
    top_active_calls = _top_active_calls(calls_30d)
    # yfinance's free feed often returns openInterest=0 intraday (OCC updates it
    # once daily after close), while volume is live. Flag it so the UI leads with
    # volume and only shows OI/walls when they're actually present.
    oi_available = any(r["call_oi"] or r["put_oi"] for r in chain_summary)

    return {
        "available": True,
        "source": "yfinance_free",
        "ticker": ticker,
        "spot_price": round(spot, 2),
        "expiration_analyzed": best_exp,
        "nearest_expiration": nearest_exp,
        "total_score": total,
        "max_possible": 11,
        "scores": {
            "6a_unusual_call": score_6a,
            "6b_sweeps_blocks": score_6b,
            "6c_dark_pool": score_6c,
            "6d_gex_gamma": score_6d,
        },
        "details": {
            "6a": detail_6a,
            "6b": detail_6b,
            "6c": detail_6c,
            "6d": detail_6d,
        },
        # Objective, verifiable chain data (volumes, OI, V/OI) for display —
        # not derived scores. The UI leads with these.
        "chain_summary": chain_summary,
        "top_active_calls": top_active_calls,
        "oi_available": oi_available,
        "data_missing": ["sweeps", "blocks", "dark_pool", "bid_ask_side"],
    }


def _chain_summary(calls_30d, puts_30d, spot) -> list[dict]:
    """Per-strike call/put OI + volume for strikes within ±25% of spot.

    Objective data straight from the chain — used to chart the OI distribution
    (call wall vs put wall) around spot.
    """
    lo, hi = spot * 0.75, spot * 1.25

    def _by_strike(df, oi_key, vol_key):
        out = {}
        if df is None or df.empty or "strike" not in df.columns:
            return out
        sub = df[(df["strike"] >= lo) & (df["strike"] <= hi)]
        for _, row in sub.iterrows():
            k = round(float(row["strike"]), 2)
            out[k] = {
                oi_key: int(row["openInterest"]) if "openInterest" in df.columns
                and not np.isnan(row["openInterest"]) else 0,
                vol_key: int(row["volume"]) if "volume" in df.columns
                and not np.isnan(row["volume"]) else 0,
            }
        return out

    calls = _by_strike(calls_30d, "call_oi", "call_vol")
    puts = _by_strike(puts_30d, "put_oi", "put_vol")
    rows = []
    for strike in sorted(set(calls) | set(puts)):
        c = calls.get(strike, {})
        p = puts.get(strike, {})
        rows.append({
            "strike": strike,
            "call_oi": c.get("call_oi", 0),
            "put_oi": p.get("put_oi", 0),
            "call_vol": c.get("call_vol", 0),
            "put_vol": p.get("put_vol", 0),
        })
    return rows


def _top_active_calls(calls_30d, limit: int = 8) -> list[dict]:
    """Most active call strikes ranked by VOLUME (always available on the free
    feed). open_interest / voi are included when present, else None — volume is
    the reliable objective signal; V/OI is a bonus when OI has settled.
    """
    if (calls_30d is None or calls_30d.empty
            or "volume" not in calls_30d.columns):
        return []
    df = calls_30d[calls_30d["volume"] > 0].copy()
    if df.empty:
        return []
    df = df.sort_values("volume", ascending=False).head(limit)
    has_oi = "openInterest" in df.columns
    rows = []
    for _, r in df.iterrows():
        vol = int(r["volume"]) if not np.isnan(r["volume"]) else 0
        oi = int(r["openInterest"]) if has_oi and not np.isnan(r["openInterest"]) else 0
        rows.append({
            "strike": round(float(r["strike"]), 2),
            "volume": vol,
            "open_interest": oi,
            "voi": round(vol / oi, 2) if oi > 0 else None,
        })
    return rows


def _score_6a(calls_30d, puts_30d, calls_near, puts_near, spot) -> tuple[int, dict]:
    """Score unusual call activity from options chain."""
    detail = {}

    # Call vs Put volume ratio (30 DTE)
    total_call_vol = calls_30d["volume"].sum() if "volume" in calls_30d.columns else 0
    total_put_vol = puts_30d["volume"].sum() if "volume" in puts_30d.columns else 0

    if total_put_vol > 0:
        cp_ratio = total_call_vol / total_put_vol
    else:
        cp_ratio = total_call_vol if total_call_vol > 0 else 0

    detail["call_put_volume_ratio"] = round(float(cp_ratio), 2)
    detail["total_call_volume"] = int(total_call_vol)
    detail["total_put_volume"] = int(total_put_vol)

    # V/OI ratio on calls (volume / open interest) — high = unusual activity
    calls_with_oi = calls_30d[calls_30d["openInterest"] > 0].copy()
    if not calls_with_oi.empty and "volume" in calls_with_oi.columns:
        calls_with_oi["voi"] = calls_with_oi["volume"] / calls_with_oi["openInterest"]
        high_voi_strikes = calls_with_oi[calls_with_oi["voi"] >= 2.0]
        max_voi = float(calls_with_oi["voi"].max())
    else:
        high_voi_strikes = None
        max_voi = 0

    detail["max_call_voi"] = round(max_voi, 2)
    detail["high_voi_strike_count"] = len(high_voi_strikes) if high_voi_strikes is not None else 0

    # OTM call activity (strikes 5-20% above spot)
    otm_low = spot * 1.05
    otm_high = spot * 1.20
    otm_calls = calls_30d[
        (calls_30d["strike"] >= otm_low) & (calls_30d["strike"] <= otm_high)
    ]
    otm_volume = otm_calls["volume"].sum() if not otm_calls.empty else 0
    detail["otm_call_volume_5_20pct"] = int(otm_volume)

    # Check for heavy put buying (negative signal)
    if total_put_vol > 0 and total_call_vol > 0:
        put_call_ratio = total_put_vol / total_call_vol
    else:
        put_call_ratio = 0
    detail["put_call_ratio"] = round(float(put_call_ratio), 2)

    # Scoring logic
    score = 0

    # Negative: heavy put buying
    if put_call_ratio > 1.8:
        score = -3
        detail["signal"] = "BEARISH — heavy put buying"
        return score, detail

    # Positive scoring
    if high_voi_strikes is not None and len(high_voi_strikes) >= 3 and cp_ratio >= 2.0:
        score = 8  # Multiple strikes with V/OI >= 2, bullish skew
        detail["signal"] = "STRONG_BULLISH — multiple high V/OI strikes + call skew"
    elif (high_voi_strikes is not None and len(high_voi_strikes) >= 1
          and cp_ratio >= 1.5):
        score = 5
        detail["signal"] = "MODERATE_BULLISH — elevated V/OI + call skew"
    elif cp_ratio >= 1.5 or max_voi >= 1.5:
        score = 2
        detail["signal"] = "MILD_BULLISH — slight call skew"
    else:
        score = 0
        detail["signal"] = "NEUTRAL"

    return score, detail


def _score_6d(calls_30d, puts_30d, spot) -> tuple[int, dict]:
    """Estimate GEX regime from open interest distribution."""
    detail = {}

    if calls_30d.empty or "openInterest" not in calls_30d.columns:
        return 0, {"signal": "NO_DATA"}

    # Call OI above spot (call wall)
    calls_above = calls_30d[calls_30d["strike"] > spot]
    call_oi_above = calls_above["openInterest"].sum() if not calls_above.empty else 0

    # Put OI below spot (put wall)
    puts_below = puts_30d[puts_30d["strike"] < spot] if not puts_30d.empty else puts_30d
    put_oi_below = puts_below["openInterest"].sum() if not puts_below.empty else 0

    detail["call_oi_above_spot"] = int(call_oi_above)
    detail["put_oi_below_spot"] = int(put_oi_below)

    # Find biggest call wall (strike with most OI above spot)
    if not calls_above.empty:
        max_oi_idx = calls_above["openInterest"].idxmax()
        call_wall_strike = float(calls_above.loc[max_oi_idx, "strike"])
        call_wall_oi = int(calls_above.loc[max_oi_idx, "openInterest"])
        detail["call_wall_strike"] = call_wall_strike
        detail["call_wall_oi"] = call_wall_oi
        detail["call_wall_pct_above"] = round((call_wall_strike / spot - 1) * 100, 1)

    # GEX proxy: if put OI > call OI near spot, dealers are likely short gamma
    # (simplified — real GEX needs Greeks computation)
    near_strikes = calls_30d[
        (calls_30d["strike"] >= spot * 0.95) & (calls_30d["strike"] <= spot * 1.05)
    ]
    near_call_oi = near_strikes["openInterest"].sum()
    near_puts = puts_30d[
        (puts_30d["strike"] >= spot * 0.95) & (puts_30d["strike"] <= spot * 1.05)
    ] if not puts_30d.empty else puts_30d
    near_put_oi = near_puts["openInterest"].sum() if not near_puts.empty else 0

    if near_put_oi > near_call_oi * 1.5:
        gex_regime = "negative_proxy"
    elif near_call_oi > near_put_oi * 1.5:
        gex_regime = "positive_proxy"
    else:
        gex_regime = "neutral_proxy"
    detail["gex_regime"] = gex_regime

    # Scoring
    if gex_regime == "negative_proxy" and call_oi_above > put_oi_below:
        score = 3  # Negative GEX + call wall = squeeze setup
        detail["signal"] = "SQUEEZE_SETUP — negative GEX proxy + call wall above"
    elif call_oi_above > put_oi_below * 1.5:
        score = 2  # Strong call positioning
        detail["signal"] = "CALL_POSITIONING — significant call OI above spot"
    elif call_oi_above > put_oi_below:
        score = 1
        detail["signal"] = "MILD — some call structure"
    else:
        score = 0
        detail["signal"] = "NEUTRAL_OR_BEARISH"

    return score, detail


def _no_data(reason: str) -> dict:
    return {
        "available": False,
        "source": "yfinance_free",
        "reason": reason,
        "total_score": 0,
        "max_possible": 11,
        "scores": {"6a_unusual_call": 0, "6b_sweeps_blocks": 0,
                   "6c_dark_pool": 0, "6d_gex_gamma": 0},
        "data_missing": ["all_options_data"],
    }


# ---------------------------------------------------------------------------
# CLI for standalone testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["NVDA", "MU", "AAPL"]
    for t in tickers:
        print(f"=== {t} ===")
        result = analyze_options(t)
        print(json.dumps(result, indent=2, default=str))
        print()
