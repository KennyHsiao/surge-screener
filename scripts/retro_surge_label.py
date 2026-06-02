#!/usr/bin/env python3
"""Surge Retrospective — Stage A: label surge events.

The INVERSE of the daily screener. Instead of looking forward from a pick, this
scans daily history for the ground-truth set of stocks that ACTUALLY surged, so
we can later reconstruct what their pre-surge setup looked like (retro_reconstruct)
and measure which factors actually predicted the move (retro_factor_lift).

For each ticker we scan adjusted daily Close over the lookback window and emit
NON-OVERLAPPING surge events under several thresholds (run "多門檻一起跑"):
    +30% within 20 sessions, +40% within 40, +50% within 60 (defaults, tunable).
Each event is one record tagged with the single threshold that produced it, so the
downstream lift analysis can compute one table PER threshold and compare which
factors stay predictive as the bar for "surge" rises.

T0 (surge_start) = the TROUGH (lowest close) just before lift-off — that is the
moment the live screener would have scored, so features must be measured there.
Magnitude uses adjusted Close (split/div-clean). Reconstruction (next stage)
re-fetches auto_adjust=False to match the live engine's _daily frame.

Survivorship-bias caveat: index membership lists are CURRENT members only —
delisted surgers are absent and many names joined the index AFTER surging. The
output records this so downstream stages and the UI can surface it.

CLI:
    python scripts/retro_surge_label.py --universe sp1500 --lookback-days 730
    STOCKS=NVDA,AMD,SMCI python scripts/retro_surge_label.py --universe custom
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
OUT_DIR = REPO / "reports" / "retrospective"

# (label, pct_gain, window_sessions) — an event qualifies if Close rises >= pct
# within <= window trading sessions of the trough. "多門檻一起跑".
DEFAULT_THRESHOLDS = [
    ("+30%/20d", 0.30, 20),
    ("+40%/40d", 0.40, 40),
    ("+50%/60d", 0.50, 60),
]


def _load_hard_filter():
    """Import scripts/01_hard_filter.py (leading digit blocks a plain import)."""
    spec = importlib.util.spec_from_file_location(
        "hard_filter", REPO / "scripts" / "01_hard_filter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _adj_close_history(tickers: list[str], period: str) -> dict[str, pd.Series]:
    """Adjusted daily Close per ticker (auto_adjust=True → split/div clean).

    Batches like hard_filter.fetch_batch_data but keeps the DatetimeIndex and only
    the Close we need for magnitude. yfinance auto_adjust=True folds splits/divs in.
    """
    import yfinance as yf

    out: dict[str, pd.Series] = {}
    for i in range(0, len(tickers), 50):
        batch = tickers[i:i + 50]
        try:
            data = yf.download(batch, period=period, auto_adjust=True,
                               threads=True, progress=False)
        except Exception as e:  # noqa: BLE001 — never abort the whole scan
            print(f"[label] batch download error: {e}", file=sys.stderr)
            continue
        if data is None or data.empty:
            continue
        if len(batch) == 1:
            df = data.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if "Close" in df and not df.empty:
                out[batch[0]] = df["Close"].dropna()
        else:
            for t in batch:
                try:
                    s = data["Close"][t].dropna()
                    if not s.empty:
                        out[t] = s
                except (KeyError, TypeError):
                    pass
    return out


def label_ticker(ticker: str, close: pd.Series,
                 thresholds: list[tuple]) -> list[dict]:
    """Emit non-overlapping surge events for one ticker, one record per threshold.

    Per threshold: scan left→right; at the first day whose forward `window` peak is
    >= pct above it, refine T0 to the trough (lowest close) within [i, peak], then
    skip past the peak so one run-up yields one event. Magnitude = peak/trough-1.
    """
    px = close.to_numpy(dtype=float)
    dates = close.index
    n = len(px)
    events: list[dict] = []
    if n < 30:
        return events

    for label, pct, window in thresholds:
        i = 0
        while i < n - 1:
            hi = min(i + window, n - 1)
            seg = px[i + 1:hi + 1]
            if seg.size == 0:
                break
            peak_rel = int(np.argmax(seg))
            peak_idx = i + 1 + peak_rel
            if px[i] > 0 and px[peak_idx] / px[i] - 1.0 >= pct:
                # Refine T0 to the true launch base: lowest close in [i, peak_idx].
                trough_idx = i + int(np.argmin(px[i:peak_idx + 1]))
                # Recompute the peak AFTER the trough (the actual run).
                seg2 = px[trough_idx + 1:hi + 1] if hi > trough_idx else px[peak_idx:peak_idx + 1]
                if seg2.size:
                    peak_idx = trough_idx + 1 + int(np.argmax(seg2))
                mag = px[peak_idx] / px[trough_idx] - 1.0
                events.append({
                    "ticker": ticker,
                    "threshold": label,
                    "surge_start": dates[trough_idx].strftime("%Y-%m-%d"),
                    "peak_date": dates[peak_idx].strftime("%Y-%m-%d"),
                    "trough_price": round(float(px[trough_idx]), 2),
                    "peak_price": round(float(px[peak_idx]), 2),
                    "magnitude_pct": round(float(mag) * 100, 1),
                    "sessions_to_peak": int(peak_idx - trough_idx),
                })
                i = peak_idx + 1  # de-overlap: skip past this run-up
            else:
                i += 1
    return events


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — label events")
    ap.add_argument("--universe", default="sp1500",
                    choices=["sp1500", "russell3000", "nasdaq_only", "custom"])
    ap.add_argument("--lookback-days", type=int, default=730)
    ap.add_argument("--limit", type=int, default=0,
                    help="cap ticker count (0 = all) — for quick tests")
    ap.add_argument("--output", default=str(OUT_DIR / "surge_events.json"))
    args = ap.parse_args()

    hf = _load_hard_filter()
    tickers = hf.load_universe(args.universe, "US")
    if args.limit:
        tickers = tickers[:args.limit]
    print(f"[label] universe={args.universe} tickers={len(tickers)} "
          f"lookback={args.lookback_days}d")

    # yfinance period strings; round up to whole years for the lookback.
    years = max(1, (args.lookback_days + 364) // 365)
    period = f"{years}y"
    cutoff = (datetime.now(timezone.utc).date()
              - pd.Timedelta(days=args.lookback_days))

    history = _adj_close_history(tickers, period)
    print(f"[label] fetched history for {len(history)}/{len(tickers)} tickers")

    all_events: list[dict] = []
    for t, close in history.items():
        close = close[close.index.date >= cutoff]
        all_events.extend(label_ticker(t, close, DEFAULT_THRESHOLDS))

    per_threshold: dict[str, int] = {}
    for e in all_events:
        per_threshold[e["threshold"]] = per_threshold.get(e["threshold"], 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe": args.universe,
        "lookback_days": args.lookback_days,
        "thresholds": [{"label": l, "pct": p, "window": w}
                       for l, p, w in DEFAULT_THRESHOLDS],
        "tickers_scanned": len(history),
        "event_count": len(all_events),
        "event_count_by_threshold": per_threshold,
        "caveats": [
            "Survivorship bias: index lists are CURRENT members only; delisted "
            "surgers are absent and some names joined AFTER surging.",
            "Magnitude uses adjusted Close; reconstruction re-fetches "
            "auto_adjust=False to match the live engine.",
        ],
        "events": all_events,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[label] {len(all_events)} events ({per_threshold}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
