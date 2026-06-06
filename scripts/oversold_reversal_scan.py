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
# Runway-INDEPENDENT validation of the lane's triple (lane_runway_check.py, sp500_pit).
# %-lift == ATR-neutral lift == 3.19 → ZERO runway inflation (the cleanest signal found).
PCT_LIFT = 3.19          # bb_squeeze & rsi_40_65 & above_30pct_of_low, %-target
ATR_NEUTRAL_LIFT = 3.19  # ...identical under the ATR-normalized target (no confound at all)
RUNWAY_SUPPORT = 35      # surgers matching the triple

import retro_reconstruct as rr  # noqa: E402 — reuse the validated flag engine


def _load_hard_filter():
    spec = importlib.util.spec_from_file_location(
        "hard_filter", REPO / "scripts" / "01_hard_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rsi14(close: np.ndarray, n: int = 14) -> float | None:
    """Wilder RSI(14) at the last bar — display context for the rsi_40_65 flag."""
    if close.size < n + 1:
        return None
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag, al = float(np.mean(gain[:n])), float(np.mean(loss[:n]))
    for i in range(n, delta.size):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def _bb_width_pct(close: np.ndarray, n: int = 20, k: float = 2.0) -> float | None:
    """Bollinger band width as % of the mid — lower = tighter coil (squeeze context)."""
    if close.size < n:
        return None
    w = close[-n:]
    mid = float(np.mean(w))
    if mid <= 0:
        return None
    return (2.0 * k * float(np.std(w))) / mid * 100.0


def _display_metrics(df: pd.DataFrame, t0: pd.Timestamp) -> dict:
    """Raw numbers for the table (the flags decide membership; these explain why)."""
    d = df[df.index <= t0]
    close = d["Close"].to_numpy(dtype=float)
    last = float(close[-1])
    ma200 = float(np.mean(close[-200:])) if len(close) >= 200 else None
    hi52 = float(np.max(close[-252:])) if len(close) >= 1 else None
    return {
        "last_price": round(last, 2),
        "rsi14": round(_rsi14(close), 1) if _rsi14(close) is not None else None,
        "bb_width_pct": round(_bb_width_pct(close), 1) if _bb_width_pct(close) is not None else None,
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


def scan(universe: str, as_of: str | None, limit: int, period: str = "2y",
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
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": (cutoff.strftime("%Y-%m-%d") if cutoff is not None
                       else datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "universe": universe,
        "scanned": scanned,
        "match_count": len(matches),
        "liquidity_filter": {"min_price": min_price, "min_dollar_vol": min_dollar_vol,
                             "illiquid_dropped": illiquid_dropped},
        "module": "coiled_base",
        "definition": "壓縮基底 + 健康動能 + 不在低點:bb_squeeze(布林壓縮)且 RSI 40–65 "
                      "且距 52 週低 ≥30%。%-目標與 ATR-中性目標 lift 完全相同(3.19),零漲幅膨脹。",
        "primary_signal": "bb_squeeze & rsi_40_65 & above_30pct_of_low (runway-independent, off-the-lows coiled base)",
        "runway_independent": True,
        "validation": {
            "source": "lane_runway_check.py (sp500_pit, ATR-neutral target)",
            "pct_lift": PCT_LIFT, "atr_neutral_lift": ATR_NEUTRAL_LIFT, "support": RUNWAY_SUPPORT,
        },
        "runway_note": "歷史的『放量+超跌』lane 在 ATR-中性目標下垮掉(%-lift 6.31 → "
                       "ATR-lift 0.84,無 edge);單獨放量也垮(1.36 → 0.67)。本 lane 改抓的"
                       f"三條件 bb_squeeze & rsi_40_65 & above_30pct_of_low,%-lift 與 ATR-中性"
                       f"lift 完全相同({PCT_LIFT}),代表毫無漲幅假象;support {RUNWAY_SUPPORT}。"
                       "加『不在低點』可剔除盤在谷底的價值陷阱、並把符合率砍半。",
        "exploratory": True,
        "note": "EXPLORATORY — 前向驗證、不自動評分。掃全量宇宙(未經 200DMA 硬濾網),"
                "是篩選器的盲區補充。",
        "candidates": matches,
    }


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
    args = ap.parse_args()

    payload = scan(args.universe, args.date, args.limit,
                   min_price=args.min_price, min_dollar_vol=args.min_dollar_vol)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUT_DIR / f"scan_{payload['as_of_date']}.json"
    out = Path(args.output) if args.output else dated
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[coiled-base] {payload['match_count']}/{payload['scanned']} matched "
          f"(as of {payload['as_of_date']}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
