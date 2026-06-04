#!/usr/bin/env python3
"""Volume-Ignition lane scanner (was "oversold-reversal" — see the runway caveat below).

The retro's 超賣反轉 module scored lift 4.17, but the runway-matched confound check
(scripts/retro_confound_check.py) showed most of that is a %-RUNWAY ARTIFACT: the retro
scores a surge as "+X% off the trough", a target a cheap/beaten-down stock reaches more
easily, so "below 200DMA / far off the high" looks predictive without a real edge — within
a price-position-matched stratum that apparent edge collapses or flips. The ONLY factor that
holds its lift across strata is rvol_ge_2 (volume ignition). So this lane is really a
VOLUME-IGNITION scan: rvol>=2 on names that happen to be beaten-down (the oversold position
is kept as context, NOT marketed as a validated reversal edge). It still scans the FULL
pre-filter universe — the screener's 200DMA hard filter (01_hard_filter.py:312) rejects these
names, so they are its blind spot.

Lane definition (the 超賣反轉 module + the one VALIDATED single factor, all required):
    price_above_ma200  == False   (steep pullback — below the 200DMA)
    within_25pct_of_high == False (oversold depth — >25% off the 52-week high)
    rvol >= 2 within the last RVOL_LOOKBACK sessions   (a recent volume ignition)

The retro measured rvol AT the +7% confirmation (a selected ignition day); a live daily
scan rarely lands on a name's exact ignition bar, so the ignition is checked over a short
RECENT window (default 5 sessions) instead of only the last bar — faithful to "oversold +
volume ignition", but usable day-to-day. RVOL_LOOKBACK=1 reproduces the strict same-day rule.

It reuses retro_reconstruct.reconstruct_flags (the SAME flag engine as the retro) and the
cached OHLCV fetch, so the live signal matches what was validated. EXPLORATORY: forward-
validated via the snapshot accumulator (oversold_reversal_forward.py), never auto-scored.

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
VALIDATED_LIFT = 4.17  # from reports/retrospective/module_lift.json (超賣反轉, ALL)

import retro_reconstruct as rr  # noqa: E402 — reuse the validated flag engine


def _load_hard_filter():
    spec = importlib.util.spec_from_file_location(
        "hard_filter", REPO / "scripts" / "01_hard_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _recent_rvol(df: pd.DataFrame, t0: pd.Timestamp, k: int) -> tuple:
    """(max rvol over the last k sessions ≤ t0, the date it occurred). rvol_d =
    volume_d / mean(prior-20-session volume). None if not enough history/volume."""
    d = df[df.index <= t0]
    if "Volume" not in d or len(d) < 21 + 1:
        return None, None
    vol = d["Volume"].to_numpy(dtype=float)
    dates = d.index
    best, best_date = None, None
    for i in range(len(vol) - k, len(vol)):
        if i < 20:
            continue
        base = float(np.mean(vol[i - 20:i]))
        if base <= 0:
            continue
        rv = float(vol[i] / base)
        if best is None or rv > best:
            best, best_date = rv, dates[i]
    return best, best_date


def _display_metrics(df: pd.DataFrame, t0: pd.Timestamp) -> dict:
    """Raw numbers for the table (the flags decide membership; these explain why)."""
    d = df[df.index <= t0]
    close = d["Close"].to_numpy(dtype=float)
    vol = d["Volume"].to_numpy(dtype=float) if "Volume" in d else np.array([])
    last = float(close[-1])
    ma200 = float(np.mean(close[-200:])) if len(close) >= 200 else None
    hi52 = float(np.max(close[-252:])) if len(close) >= 1 else None
    rvol = None
    if vol.size >= 21 and float(np.mean(vol[-21:-1])) > 0:
        rvol = float(vol[-1] / np.mean(vol[-21:-1]))
    return {
        "last_price": round(last, 2),
        "ma200": round(ma200, 2) if ma200 else None,
        "pct_below_ma200": round((last / ma200 - 1.0) * 100, 1) if ma200 else None,
        "pct_from_52w_high": round((last / hi52 - 1.0) * 100, 1) if hi52 else None,
        "rvol": round(rvol, 2) if rvol is not None else None,
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


def scan(universe: str, as_of: str | None, limit: int,
         rvol_lookback: int = 5, period: str = "2y",
         min_price: float = 5.0, min_dollar_vol: float = 5e6) -> dict:
    import yfinance as yf
    hf = _load_hard_filter()
    tickers = hf.load_universe(universe, "US")
    if limit:
        tickers = tickers[:limit]

    spy = yf.Ticker("SPY").history(period=period, auto_adjust=False)["Close"].dropna()
    vix = yf.Ticker("^VIX").history(period=period)["Close"].dropna()
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()

    cutoff = pd.Timestamp(as_of).normalize() if as_of else None
    scanned = 0
    illiquid_dropped = 0
    matches: list[dict] = []
    for t in tickers:
        df = rr._hist_auto_adjust_false(t, period)
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        if cutoff is not None:
            df = df[df.index <= cutoff]
        if len(df) < 200:
            continue
        scanned += 1
        t0 = df.index[-1]
        flags = rr.reconstruct_flags(df, spy, vix, t0)
        if not flags:
            continue
        # The lane: oversold (below MA200, far from 52w-high) with a RECENT volume
        # ignition (rvol≥2 in the last rvol_lookback sessions).
        if (flags.get("price_above_ma200") is False
                and flags.get("within_25pct_of_high") is False):
            max_rvol, ig_date = _recent_rvol(df, t0, rvol_lookback)
            if max_rvol is not None and max_rvol >= 2.0:
                # Tradeability floor — a forward hit-rate on names a position can't enter
                # is not meaningful (review finding).
                last = float(df[df.index <= t0]["Close"].iloc[-1])
                adv = _avg_dollar_vol(df, t0)
                if last < min_price or adv is None or adv < min_dollar_vol:
                    illiquid_dropped += 1
                    continue
                row = {"ticker": t, "as_of": t0.strftime("%Y-%m-%d"),
                       "ignition_rvol": round(max_rvol, 2),
                       "ignition_date": ig_date.strftime("%Y-%m-%d") if ig_date else None,
                       "avg_dollar_vol_m": round(adv / 1e6, 1)}
                row.update(_display_metrics(df, t0))
                matches.append(row)

    matches.sort(key=lambda r: (r.get("ignition_rvol") or 0), reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": (cutoff.strftime("%Y-%m-%d") if cutoff is not None
                       else datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "universe": universe,
        "scanned": scanned,
        "match_count": len(matches),
        "rvol_lookback": rvol_lookback,
        "liquidity_filter": {"min_price": min_price, "min_dollar_vol": min_dollar_vol,
                             "illiquid_dropped": illiquid_dropped},
        "module": "volume_ignition",
        "definition": f"volume ignition (rvol>=2 within last {rvol_lookback} sessions) on a "
                      f"beaten-down base (below 200DMA AND >25% off 52w-high)",
        # The ONLY runway-independent validated signal here is the volume ignition.
        "primary_signal": "rvol_ge_2 (volume ignition)",
        "runway_confound": True,
        "module_lift_runway_inflated": VALIDATED_LIFT,
        "runway_note": "The 超賣反轉 module's 4.17x retro lift is LARGELY a %-runway artifact: "
                       "a cheap, beaten-down stock reaches a fixed +30/40/50% target more "
                       "easily than one near its highs, so 'below 200DMA / far off high' "
                       "looks predictive without a real edge. The runway-matched confound "
                       "check (scripts/retro_confound_check.py) shows the only factor that "
                       "HOLDS its lift across price-position strata is rvol_ge_2. So the "
                       "volume ignition is the signal; the oversold/position columns are "
                       "context, not a proven reversal edge.",
        "exploratory": True,
        "note": "EXPLORATORY — forward-validated, never auto-scored. Position/oversold "
                "factors are runway-confounded; only the volume ignition is validated.",
        "candidates": matches,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Oversold-Reversal lane scanner")
    ap.add_argument("--universe", default="sp1500")
    ap.add_argument("--date", default=None, help="as-of YYYY-MM-DD (default: latest)")
    ap.add_argument("--limit", type=int, default=0, help="cap tickers (0 = all)")
    ap.add_argument("--rvol-lookback", type=int, default=5,
                    help="rvol≥2 must occur within this many recent sessions (1 = strict same-day)")
    ap.add_argument("--min-price", type=float, default=5.0,
                    help="tradeability floor: drop candidates under this price")
    ap.add_argument("--min-dollar-vol", type=float, default=5e6,
                    help="tradeability floor: drop candidates under this 20d avg $ volume")
    ap.add_argument("--output", default=None, help="explicit output path")
    args = ap.parse_args()

    payload = scan(args.universe, args.date, args.limit, rvol_lookback=args.rvol_lookback,
                   min_price=args.min_price, min_dollar_vol=args.min_dollar_vol)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUT_DIR / f"scan_{payload['as_of_date']}.json"
    out = Path(args.output) if args.output else dated
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[oversold] {payload['match_count']}/{payload['scanned']} matched "
          f"(as of {payload['as_of_date']}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
