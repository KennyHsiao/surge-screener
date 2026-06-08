#!/usr/bin/env python3
"""History Analysis corpus for the 大盤行情研判 agent — labelled past SPY/VIX regimes.

This is the DEoT "History Analysis (主動檢索)" source for the market-thesis agent (market_thesis.py).
It is PURE, deterministic, VERIFIED data (no LLM): fetch ~5y of SPY + ^VIX, label each session
rally / correction / range from price-vs-MA + VIX zone, attach the REALIZED forward SPY return at
20/40/60 sessions, and expose retrieve_regime_analogs() so the agent can ask "in the N past sessions
that looked like today (same regime + VIX bucket), what did SPY actually do next?" — real precedent,
never LLM-invented. This is what makes the 看空/盤整 read honest at market level (the bearish/range
side is just the correction/range episodes — no per-stock decline corpus is needed).

Heuristic labels (EXPLORATORY — a coarse regime tag, NOT a signal):
  rally       SPY > 50DMA AND > 200DMA AND VIX < 20      (uptrend, calm)
  correction  SPY < 200DMA AND VIX >= 22                  (downtrend + fear)
  range       everything else                              (mixed / choppy)

CLI:  python scripts/market_regime_history.py [--period 5y]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import retro_reconstruct as rr                      # noqa: E402 — cached OHLCV fetch
from oversold_reversal_forward import _mean_block   # noqa: E402 — pure forward-return stat block

OUT_DIR = REPO / "reports" / "market_thesis"
FWD = [20, 40, 60]  # forward session windows (short / mid / long), aligned with the thesis 期程 buckets
REGIMES = ("rally", "correction", "range")


def _vix_bucket(vix: float | None) -> str:
    if vix is None or not np.isfinite(vix):
        return "unknown"
    if vix < 15:
        return "low"
    if vix < 20:
        return "normal"
    if vix < 30:
        return "elevated"
    return "panic"


def label_regime(close: float, ma50: float | None, ma200: float | None, vix: float | None) -> str:
    """Coarse 3-state market regime (deterministic, exploratory)."""
    above50 = bool(ma50 is not None and np.isfinite(ma50) and close > ma50)
    above200 = bool(ma200 is not None and np.isfinite(ma200) and close > ma200)
    v = vix if (vix is not None and np.isfinite(vix)) else None
    if (ma200 is not None and np.isfinite(ma200) and close < ma200) and (v is not None and v >= 22):
        return "correction"
    if above50 and above200 and (v is not None and v < 20):
        return "rally"
    return "range"


def _spy_vix(period: str) -> tuple[pd.Series, pd.Series] | None:
    spy = rr._hist_auto_adjust_false("SPY", period)
    vixdf = rr._hist_auto_adjust_false("^VIX", period)
    if spy is None or vixdf is None:
        return None
    sc = spy["Close"].dropna()
    vc = vixdf["Close"].dropna()
    sc.index = pd.to_datetime(sc.index).tz_localize(None).normalize()
    vc.index = pd.to_datetime(vc.index).tz_localize(None).normalize()
    return sc, vc


def build_daily(period: str = "5y") -> list[dict]:
    """One record per SPY session: regime + VIX bucket + realized forward returns (None until elapsed)."""
    sv = _spy_vix(period)
    if sv is None:
        return []
    spy, vix = sv
    vix = vix.reindex(spy.index).ffill()  # VIX onto SPY's calendar (a missing VIX day uses the last print)
    ma50 = spy.rolling(50).mean()
    ma200 = spy.rolling(200).mean()
    close = spy.to_numpy(float)
    n = len(close)
    rows: list[dict] = []
    for i in range(n):
        if i < 200:  # need a full 200DMA warmup before the label means anything
            continue
        c = float(close[i])
        v = float(vix.iloc[i]) if np.isfinite(vix.iloc[i]) else None
        regime = label_regime(c, float(ma50.iloc[i]), float(ma200.iloc[i]), v)
        fwd = {}
        for w in FWD:
            fwd[f"fwd_{w}d"] = (float(close[i + w]) / c - 1.0) if (i + w) < n and c > 0 else None
        rows.append({
            "date": spy.index[i].date().isoformat(), "close": round(c, 2),
            "vix": round(v, 2) if v is not None else None, "vix_bucket": _vix_bucket(v),
            "regime": regime,
            "spy_vs_50dma": "above" if c > float(ma50.iloc[i]) else "below",
            "spy_vs_200dma": "above" if c > float(ma200.iloc[i]) else "below",
            **fwd,
        })
    return rows


def _regime_block(rows: list[dict], window: int) -> dict:
    vals = [r[f"fwd_{window}d"] for r in rows if r.get(f"fwd_{window}d") is not None]
    blk = _mean_block(vals)
    return {"resolved": blk["n"], "mean": blk["ev"], "median": blk["median"],
            "up_rate": blk["win_rate"], "ci90": blk["ci90"]}


def summarize(daily: list[dict]) -> dict:
    out = {}
    for reg in REGIMES:
        rrows = [r for r in daily if r["regime"] == reg]
        out[reg] = {"days": len(rrows),
                    **{f"fwd_{w}d": _regime_block(rrows, w) for w in FWD}}
    return out


def episodes(daily: list[dict]) -> list[dict]:
    """Collapse consecutive same-regime sessions into episodes (for human-readable context)."""
    eps: list[dict] = []
    for r in daily:
        if eps and eps[-1]["regime"] == r["regime"]:
            eps[-1]["end"] = r["date"]
            eps[-1]["sessions"] += 1
            eps[-1]["end_close"] = r["close"]
        else:
            eps.append({"regime": r["regime"], "start": r["date"], "end": r["date"],
                        "sessions": 1, "start_close": r["close"], "end_close": r["close"]})
    for e in eps:
        e["ret_pct"] = round(e["end_close"] / e["start_close"] - 1.0, 4) if e["start_close"] else None
    return eps


def retrieve_regime_analogs(daily: list[dict], regime: str, vix_bucket: str | None = None,
                            k: int = 5) -> dict:
    """REAL historical precedent for today's regime: among past sessions in the SAME regime (and, if
    given, the SAME VIX bucket), the distribution of realized forward SPY returns + a few examples.
    Deterministic, verified — this is what the agent cites under 歷史類比 (it may NOT invent analogs)."""
    pool = [r for r in daily if r["regime"] == regime]
    if vix_bucket:
        narrowed = [r for r in pool if r["vix_bucket"] == vix_bucket]
        if len(narrowed) >= 20:  # only narrow when the bucket still has a usable sample
            pool = narrowed
    out = {"regime": regime, "vix_bucket": vix_bucket, "n_sessions": len(pool),
           **{f"fwd_{w}d": _regime_block(pool, w) for w in FWD}}
    # a few concrete dated precedents (most recent first), with their realized 60d path
    examples = [r for r in pool if r.get("fwd_60d") is not None]
    examples.sort(key=lambda r: r["date"], reverse=True)
    out["examples"] = [{"date": r["date"], "vix": r["vix"], "fwd_20d": r["fwd_20d"],
                        "fwd_60d": r["fwd_60d"]} for r in examples[:k]]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Label past SPY/VIX market regimes (History Analysis corpus)")
    ap.add_argument("--period", default="5y", help="yfinance lookback (needs >1y warmup for 200DMA)")
    ap.add_argument("--output", default=str(OUT_DIR / "regime_history.json"))
    args = ap.parse_args()

    daily = build_daily(args.period)
    if not daily:
        print("[regime-hist] no SPY/VIX history fetched", file=sys.stderr)
        return 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "SPY + ^VIX (yfinance, auto_adjust=False)", "lookback_period": args.period,
        "rules": {"rally": "SPY>50DMA & >200DMA & VIX<20", "correction": "SPY<200DMA & VIX>=22",
                  "range": "otherwise", "vix_buckets": "low<15 normal<20 elevated<30 panic>=30"},
        "forward_windows_sessions": FWD,
        "note": "EXPLORATORY regime tags for History-Analysis retrieval; not a signal. Forward returns "
                "are realized SPY paths (None until the window elapsed).",
        "regime_summary": summarize(daily),
        "episodes": episodes(daily),
        "daily": daily,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[regime-hist] {len(daily)} sessions, {len(payload['episodes'])} episodes → {args.output}")
    for reg in REGIMES:
        s = payload["regime_summary"][reg]
        b = s["fwd_60d"]
        print(f"  {reg:11s}: {s['days']:4d} days | 60d fwd mean {b['mean']} up-rate {b['up_rate']} (n={b['resolved']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
