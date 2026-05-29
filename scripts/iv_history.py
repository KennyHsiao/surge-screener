#!/usr/bin/env python3
"""Daily ATM-IV snapshot store + IV Rank / Percentile.

yfinance gives only the *current* IV, never 52-week history — so IV Rank/Percentile
can't be computed from a single fetch. This accumulates a daily ATM-IV snapshot per
ticker (committed under reports/iv_history/, so the daily GitHub Action builds the
52-week base over time) and computes percentile/rank once enough days exist.

Until ~MIN_DAYS accumulate, callers should fall back to a realized-volatility
percentile proxy (see scripts/momentum_options.py) and label it "accumulating".

Never raises: read/record failures return safe defaults so a flaky store can't
break a scoring run.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "reports" / "iv_history"
MIN_DAYS = 40          # ~2 months before a percentile is meaningful
WINDOW_DAYS = 252      # 52 weeks


def _path(ticker: str) -> Path:
    safe = "".join(c for c in ticker.upper() if c.isalnum() or c in "-._")
    return _DIR / f"{safe}.json"


def _load(ticker: str) -> dict:
    p = _path(ticker)
    try:
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def record_iv(ticker: str, atm_iv: float | None, day: str | None = None) -> None:
    """Append today's ATM IV (one value per day; last write wins). No-op on bad input."""
    if atm_iv is None:
        return
    try:
        iv = float(atm_iv)
        if iv != iv or not (0.0 < iv < 10.0):  # NaN / absurd guard
            return
        day = day or datetime.now().strftime("%Y-%m-%d")
        hist = _load(ticker)
        series = hist.get("series", {})
        series[day] = round(iv, 4)
        hist["series"] = series
        hist["ticker"] = ticker.upper()
        _DIR.mkdir(parents=True, exist_ok=True)
        p = _path(ticker)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(hist), encoding="utf-8")
        import os
        os.replace(tmp, p)
    except Exception:
        pass


def iv_percentile(ticker: str, current_iv: float | None = None) -> dict:
    """IV Rank + Percentile over the accumulated window.

    Returns dict: {percentile, rank, n_days, accumulating, current}. While
    n_days < MIN_DAYS, ``accumulating`` is True and percentile/rank are None
    (caller uses the realized-vol proxy instead).
    """
    hist = _load(ticker)
    series = hist.get("series", {})
    # keep the most recent WINDOW_DAYS entries
    items = sorted(series.items())[-WINDOW_DAYS:]
    vals = [v for _, v in items]
    n = len(vals)
    cur = current_iv if current_iv is not None else (vals[-1] if vals else None)
    if n < MIN_DAYS or cur is None:
        return {"percentile": None, "rank": None, "n_days": n,
                "accumulating": True, "current": cur}
    lo, hi = min(vals), max(vals)
    pct = round(sum(1 for v in vals if v <= cur) / n * 100, 1)
    rank = round((cur - lo) / (hi - lo) * 100, 1) if hi > lo else None
    return {"percentile": pct, "rank": rank, "n_days": n,
            "accumulating": False, "current": round(float(cur), 4)}


if __name__ == "__main__":
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(t, iv_percentile(t))
