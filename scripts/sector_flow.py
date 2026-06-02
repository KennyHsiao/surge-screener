#!/usr/bin/env python3
"""Sector money-flow / rotation via free sector-ETF relative strength (RRG).

Answers two questions with verified free data (yfinance), no guessing:
  1. WHERE is hot money now  → sectors in the Leading quadrant + a heat ranking.
  2. WHERE does it rotate NEXT → sectors in the Improving quadrant + their
     rotation tail (trajectory), the early-rotation-in signal.

The engine is the industry-standard **Relative Rotation Graph (RRG)** built on
two axes, both centred at 100 (pure numpy — the .venv has NO scipy):
  • RS-Ratio    = 100 * (ETF/SPY) / SMA(ETF/SPY, 200) → the relative-strength LINE
                  vs its own long (~10-month) baseline. >100 = trading above its
                  trailing relative strength = a durable outperformer; <100 = laggard.
  • RS-Momentum = 100 * RS-Ratio / SMA(RS-Ratio, 20) → is that relative strength
                  rising (>100) or fading (<100). Smoothed multi-day, not a 1-day diff.
Quadrants: Leading (≥100,≥100) → Weakening (≥100,<100) → Lagging (<100,<100)
→ Improving (<100,≥100) → back to Leading (clockwise). The normalisation windows
and heat weights are tunable constants below.

`gather_sector_flow()` NEVER raises — returns None on total failure; each ETF is
isolated so one bad symbol can't lose the rest (matches the other *_free.py
gatherers). Cached 1h. Pure data → fed to the LLM read (scripts/sector_rotation.py).

CLI:  python scripts/sector_flow.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Sector ETF universe. group "主板塊" = the 11 SPDR sectors; "主題" = thematic /
# industry slices. theme tags a thematic ETF's narrative (shown in the UI). ──────
SECTOR_ETFS = [
    {"etf": "XLK",  "name_zh": "科技",        "group": "主板塊", "theme": None},
    {"etf": "XLF",  "name_zh": "金融",        "group": "主板塊", "theme": None},
    {"etf": "XLE",  "name_zh": "能源",        "group": "主板塊", "theme": None},
    {"etf": "XLV",  "name_zh": "醫療保健",    "group": "主板塊", "theme": None},
    {"etf": "XLY",  "name_zh": "非必需消費",  "group": "主板塊", "theme": None},
    {"etf": "XLP",  "name_zh": "必需消費",    "group": "主板塊", "theme": None},
    {"etf": "XLI",  "name_zh": "工業",        "group": "主板塊", "theme": None},
    {"etf": "XLB",  "name_zh": "原物料",      "group": "主板塊", "theme": None},
    {"etf": "XLU",  "name_zh": "公用事業",    "group": "主板塊", "theme": None},
    {"etf": "XLRE", "name_zh": "房地產",      "group": "主板塊", "theme": None},
    {"etf": "XLC",  "name_zh": "通訊服務",    "group": "主板塊", "theme": None},
    {"etf": "SMH",  "name_zh": "半導體",      "group": "主題",   "theme": "AI 超級循環"},
    {"etf": "SOXX", "name_zh": "半導體(SOXX)", "group": "主題",  "theme": "AI 超級循環"},
    {"etf": "IGV",  "name_zh": "軟體",        "group": "主題",   "theme": "AI 超級循環"},
    {"etf": "XBI",  "name_zh": "生技",        "group": "主題",   "theme": None},
    {"etf": "KRE",  "name_zh": "區域銀行",    "group": "主題",   "theme": None},
    {"etf": "ITB",  "name_zh": "房屋建商",    "group": "主題",   "theme": None},
    {"etf": "GLD",  "name_zh": "黃金避險",    "group": "主題",   "theme": None},
    {"etf": "IWM",  "name_zh": "小型股(R2000)", "group": "主題", "theme": None},
]

BENCHMARK = "SPY"
RS_WINDOW = 200         # long baseline → RS-Ratio reflects durable LEVEL of out/under-performance
MOM_WINDOW = 20         # window for RS-Momentum (RS-Ratio vs its own recent mean)
PERIOD = "3y"           # ample warmup for the 200d baseline + the rotation tail
TAIL_POINTS = 8         # rotation-tail points
TAIL_STEP = 5           # ~weekly sampling (trading days) for the tail
# heat_score = weighted blend of cross-sectional percentile ranks (0-100). Tunable.
# rs_ratio & excess_20d both measure recent relative strength (correlated), so their
# combined weight is held to 0.50 to avoid double-counting; rvol (volume surge) carries
# the genuine "money flowing in" signal.
HEAT_WEIGHTS = {"rs_ratio": 0.30, "rs_momentum": 0.30, "excess_20d": 0.20, "rvol": 0.20}


def _cached(namespace: str, params, ttl: float, compute):
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
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def _quadrant(rs_ratio: float, rs_mom: float) -> str:
    if rs_ratio >= 100 and rs_mom >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_mom < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_mom < 100:
        return "Lagging"
    return "Improving"  # rs_ratio < 100 and rs_mom >= 100


QUADRANT_ZH = {
    "Leading": "領漲", "Weakening": "轉弱", "Lagging": "落後", "Improving": "醞釀",
}


def gather_sector_flow() -> dict | None:
    """Sector relative-strength / RRG snapshot, or None on failure. Cached 1h."""
    return _cached("sector_flow", {"v": 2}, 3600, _compute_sector_flow)  # v2: level-based RS-Ratio + smoothed momentum


def _rrg_series(ratio):
    """(RS-Ratio series, RS-Momentum series) — both pandas Series centred at 100.

    RS-Ratio = 100 * ratio / SMA(ratio, RS_WINDOW): the ETF/SPY relative-strength
    line measured against its OWN long (~10-month) baseline, so a sector trading
    ABOVE its trailing relative-strength average reads >100 (a durable outperformer
    stays >100; a persistent laggard reads <100) — a LEVEL of out/under-performance,
    not a short-window mean-reversion wobble.

    RS-Momentum = 100 * RS-Ratio / SMA(RS-Ratio, MOM_WINDOW): whether that relative
    strength is currently rising (>100) or fading (<100). Using a smoothed
    multi-day baseline (not a 1-day diff) so the momentum axis reflects genuine
    multi-week rotation rather than day-to-day noise."""
    base = ratio.rolling(RS_WINDOW).mean()
    rs_ratio = (100.0 * ratio / base.where(base > 0)).dropna()
    mbase = rs_ratio.rolling(MOM_WINDOW).mean()
    rs_mom = (100.0 * rs_ratio / mbase.where(mbase > 0)).dropna()
    return rs_ratio, rs_mom


def _compute_sector_flow() -> dict | None:
    try:
        import numpy as np
        import pandas as pd
        import yfinance as yf
    except ImportError:
        return None

    tickers = [s["etf"] for s in SECTOR_ETFS] + [BENCHMARK]
    try:
        data = yf.download(tickers, period=PERIOD, auto_adjust=True,
                           threads=True, progress=False)
    except Exception as e:  # noqa: BLE001
        print(f"[sector_flow] download error: {e}", file=sys.stderr)
        return None
    if data is None or data.empty or "Close" not in data:
        return None

    close = data["Close"]
    volume = data["Volume"] if "Volume" in data else None
    if isinstance(close, pd.Series):  # single-ticker safety (shouldn't happen here)
        return None
    if BENCHMARK not in close.columns:
        return None
    spy = close[BENCHMARK].dropna()
    if len(spy) < RS_WINDOW + MOM_WINDOW + 10:
        return None

    def _ret(s, n):
        s = s.dropna()
        if len(s) <= n:
            return None
        prev = float(s.iloc[-(n + 1)])
        if prev <= 0:  # guard a 0/negative adjusted-close bar → no inf/garbage
            return None
        r = (float(s.iloc[-1]) / prev - 1.0) * 100
        return r if r == r and abs(r) != float("inf") else None

    spy_ret20 = _ret(spy, 20)
    rows: list[dict] = []
    for meta in SECTOR_ETFS:
        etf = meta["etf"]
        try:
            if etf not in close.columns:
                continue
            etf_close = close[etf].dropna()
            if len(etf_close) < RS_WINDOW + MOM_WINDOW + 10:
                continue
            ratio = (close[etf] / spy).dropna()
            rs_ratio_s, rs_mom_s = _rrg_series(ratio)
            if rs_ratio_s.empty or rs_mom_s.empty:
                continue
            rs_ratio = float(rs_ratio_s.iloc[-1])
            rs_mom = float(rs_mom_s.iloc[-1])

            # Rotation tail: ~weekly samples of the joint (rs_ratio, rs_momentum),
            # anchored on the LATEST point so the tail ends exactly at the dot
            # (sample newest→back every TAIL_STEP days, then re-order oldest→newest).
            joint = pd.DataFrame({"rs": rs_ratio_s, "mom": rs_mom_s}).dropna()
            sampled = joint.iloc[::-1].iloc[::TAIL_STEP].iloc[:TAIL_POINTS].iloc[::-1]
            tail = [{"date": d.strftime("%Y-%m-%d"),
                     "rs_ratio": round(float(r.rs), 2),
                     "rs_momentum": round(float(r.mom), 2)}
                    for d, r in sampled.iterrows()]

            px = float(etf_close.iloc[-1])
            ma50 = float(etf_close.iloc[-50:].mean()) if len(etf_close) >= 50 else None
            ma200 = float(etf_close.iloc[-200:].mean()) if len(etf_close) >= 200 else None
            ret20 = _ret(etf_close, 20)
            rvol = None
            if volume is not None and etf in volume.columns:
                vol = volume[etf].dropna()
                if len(vol) >= 21 and float(vol.iloc[-21:-1].mean()) > 0:
                    rvol = float(vol.iloc[-1] / vol.iloc[-21:-1].mean())
            hi52 = float(etf_close.iloc[-252:].max()) if len(etf_close) >= 60 else None

            rows.append({
                "etf": etf,
                "name_zh": meta["name_zh"],
                "group": meta["group"],
                "theme": meta["theme"],
                "rs_ratio": round(rs_ratio, 2),
                "rs_momentum": round(rs_mom, 2),
                "quadrant": _quadrant(rs_ratio, rs_mom),
                "quadrant_zh": QUADRANT_ZH[_quadrant(rs_ratio, rs_mom)],
                "ret_5d": round(_ret(etf_close, 5), 1) if _ret(etf_close, 5) is not None else None,
                "ret_20d": round(ret20, 1) if ret20 is not None else None,
                "ret_60d": round(_ret(etf_close, 60), 1) if _ret(etf_close, 60) is not None else None,
                "excess_20d": round(ret20 - spy_ret20, 1)
                if (ret20 is not None and spy_ret20 is not None) else None,
                "pct_vs_ma50": round((px / ma50 - 1) * 100, 1) if ma50 else None,
                "pct_vs_ma200": round((px / ma200 - 1) * 100, 1) if ma200 else None,
                "rvol": round(rvol, 2) if rvol is not None else None,
                "pct_from_52w_high": round((px / hi52 - 1) * 100, 1) if hi52 else None,
                "tail": tail,
            })
        except Exception:  # noqa: BLE001 — one ETF failing never aborts the rest
            continue

    if not rows:
        return None

    # Cross-sectional heat: weighted blend of within-set percentile ranks (0-100).
    def _rank(values):
        arr = np.array([v if v is not None else np.nan for v in values], dtype=float)
        order = pd.Series(arr).rank(pct=True) * 100  # NaN stays NaN
        return order.to_numpy()

    ranks = {k: _rank([r.get(k) for r in rows]) for k in HEAT_WEIGHTS}
    for i, r in enumerate(rows):
        num = den = 0.0
        for k, w in HEAT_WEIGHTS.items():
            v = ranks[k][i]
            if v == v:  # not NaN
                num += w * float(v)
                den += w
        r["heat_score"] = round(num / den, 1) if den else None

    rows.sort(key=lambda r: (r["heat_score"] if r["heat_score"] is not None else -1),
              reverse=True)

    from datetime import datetime, timezone
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": BENCHMARK,
        "params": {"rs_window": RS_WINDOW, "mom_window": MOM_WINDOW,
                   "heat_weights": HEAT_WEIGHTS},
        "as_of": str(spy.index[-1].date()),
        "sectors": rows,
        "leaders": [r["etf"] for r in rows if r["quadrant"] == "Leading"],
        "improving": [r["etf"] for r in rows if r["quadrant"] == "Improving"],
    }


if __name__ == "__main__":
    import json
    out = gather_sector_flow()
    if not out:
        print("no data"); sys.exit(1)
    print(f"as_of={out['as_of']}  benchmark={out['benchmark']}")
    print(f"  Leading(領漲):   {out['leaders']}")
    print(f"  Improving(醞釀): {out['improving']}")
    print(f"{'ETF':6}{'板塊':10}{'象限':10}{'RS-Ratio':>9}{'RS-Mom':>8}{'熱度':>6}{'20d%':>7}{'excess':>8}")
    for r in out["sectors"]:
        print(f"{r['etf']:6}{r['name_zh']:<10}{r['quadrant_zh']:<8}"
              f"{r['rs_ratio']:>9}{r['rs_momentum']:>8}{r['heat_score']:>6}"
              f"{r['ret_20d'] if r['ret_20d'] is not None else '—':>7}"
              f"{r['excess_20d'] if r['excess_20d'] is not None else '—':>8}")
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2, ensure_ascii=False))
