#!/usr/bin/env python3
"""Oversold-Reversal lane scanner — the surge retrospective's one VALIDATED archetype.

The retrospective (reports/retrospective/module_lift.json) found the 超賣反轉 module at
lift 4.17 (VALIDATED across all thresholds) while the screener's own momentum-continuation
template (延續型趨勢 / Minervini) is CONTRARIAN at 0.47 — and the live hard filter
(01_hard_filter.py:312, "Below 200DMA without reversal pattern") STRUCTURALLY rejects this
exact setup. So this lane scans the FULL pre-filter universe for the blind-spot the
screener throws away.

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


def scan(universe: str, as_of: str | None, limit: int,
         rvol_lookback: int = 5, period: str = "2y") -> dict:
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
                row = {"ticker": t, "as_of": t0.strftime("%Y-%m-%d"),
                       "ignition_rvol": round(max_rvol, 2),
                       "ignition_date": ig_date.strftime("%Y-%m-%d") if ig_date else None}
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
        "module": "oversold_reversal",
        "definition": f"below 200DMA AND >25% off 52w-high AND rvol>=2 within last "
                      f"{rvol_lookback} sessions (超賣反轉 module + rvol; retro lift 4.17, VALIDATED)",
        "validated_lift": VALIDATED_LIFT,
        "exploratory": True,
        "note": "EXPLORATORY — these are setups the screener's 200DMA hard filter "
                "rejects; survivorship-blocked retro can't make them actionable, so they "
                "are forward-validated, never auto-scored.",
        "candidates": matches,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Oversold-Reversal lane scanner")
    ap.add_argument("--universe", default="sp1500")
    ap.add_argument("--date", default=None, help="as-of YYYY-MM-DD (default: latest)")
    ap.add_argument("--limit", type=int, default=0, help="cap tickers (0 = all)")
    ap.add_argument("--rvol-lookback", type=int, default=5,
                    help="rvol≥2 must occur within this many recent sessions (1 = strict same-day)")
    ap.add_argument("--output", default=None, help="explicit output path")
    args = ap.parse_args()

    payload = scan(args.universe, args.date, args.limit, rvol_lookback=args.rvol_lookback)
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
