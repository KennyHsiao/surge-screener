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
    import time

    import yfinance as yf

    out: dict[str, pd.Series] = {}
    for i in range(0, len(tickers), 50):
        batch = tickers[i:i + 50]
        # RETRY a transient batch failure before dropping 50 tickers — a single network
        # blip would otherwise silently shrink the scanned universe (see the shrink
        # alert in main()).
        data = None
        for attempt in range(3):
            try:
                data = yf.download(batch, period=period, auto_adjust=True,
                                   threads=True, progress=False)
                if data is not None and not data.empty:
                    break
            except Exception as e:  # noqa: BLE001 — never abort the whole scan
                print(f"[label] batch download error (attempt {attempt + 1}): {e}",
                      file=sys.stderr)
            time.sleep(0.5 * (attempt + 1))
        if data is None or data.empty:
            print(f"[label] batch {i//50} ({len(batch)} tickers) failed all retries",
                  file=sys.stderr)
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

    # ONE event per physical run-up (episode), tagged with every threshold it hits —
    # not one row per threshold. Detect with the loosest qualifying condition
    # (min pct within max window), which is implied by EVERY tier, so it's a strict
    # superset; then per-tier window checks give thresholds_hit. This stops a single
    # surge being triple-counted across +30/+40/+50 and inflating ALL-table support.
    min_pct = min(p for _, p, _ in thresholds)
    max_window = max(w for _, _, w in thresholds)
    i = 0
    while i < n - 1:
        hi = min(i + max_window, n - 1)
        seg = px[i + 1:hi + 1]
        if seg.size == 0:
            break
        peak_idx = i + 1 + int(np.argmax(seg))
        if not (px[i] > 0 and px[peak_idx] / px[i] - 1.0 >= min_pct):
            i += 1
            continue
        # Refine T0 to the true launch base, then recompute the peak after it.
        trough_idx = i + int(np.argmin(px[i:peak_idx + 1]))
        hi2 = min(trough_idx + max_window, n - 1)
        seg2 = px[trough_idx + 1:hi2 + 1]
        if not seg2.size:
            i += 1
            continue
        peak_idx = trough_idx + 1 + int(np.argmax(seg2))
        base = px[trough_idx]
        # thresholds_hit: each tier checked against ITS OWN window from the trough.
        hits = []
        for label, pct, win in thresholds:
            w_hi = min(trough_idx + win, n - 1)
            wseg = px[trough_idx + 1:w_hi + 1]
            if wseg.size and base > 0 and float(wseg.max()) / base - 1.0 >= pct:
                hits.append(label)
        if not hits:
            i += 1  # qualified loosely but no specific tier — not a real surge
            continue
        events.append({
            "ticker": ticker,
            "thresholds_hit": hits,
            "surge_start": dates[trough_idx].strftime("%Y-%m-%d"),
            "peak_date": dates[peak_idx].strftime("%Y-%m-%d"),
            "trough_price": round(float(base), 2),
            "peak_price": round(float(px[peak_idx]), 2),
            "magnitude_pct": round((float(px[peak_idx]) / base - 1.0) * 100, 1),
            "sessions_to_peak": int(peak_idx - trough_idx),
        })
        i = peak_idx + 1  # de-overlap: one episode per run-up
    return events


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — label events")
    ap.add_argument("--universe", default="sp1500",
                    choices=["sp1500", "russell3000", "nasdaq_only", "custom",
                             "sp500_pit"])
    ap.add_argument("--lookback-days", type=int, default=730)
    ap.add_argument("--limit", type=int, default=0,
                    help="cap ticker count (0 = all) — for quick tests")
    ap.add_argument("--output", default=str(OUT_DIR / "surge_events.json"))
    args = ap.parse_args()

    # yfinance period strings; round up to whole years for the lookback.
    years = max(1, (args.lookback_days + 364) // 365)
    period = f"{years}y"
    cutoff = (datetime.now(timezone.utc).date()
              - pd.Timedelta(days=args.lookback_days))

    # Point-in-time S&P 500 (free survivorship correction, S&P 500 only). The scanned
    # population is EVERY ticker that was a member at any point in the window (so no
    # member is missed); events are filtered per-ticker to its actual membership on the
    # surge day below. See scripts/sp500_membership.py.
    pit = args.universe == "sp500_pit"
    if pit:
        import sp500_membership as sp500_pit_mod
        cutoff_str, today_str = str(cutoff), str(datetime.now(timezone.utc).date())
        tickers = sorted(sp500_pit_mod.universe_in_window(cutoff_str, today_str))
        if today_str > sp500_pit_mod.SNAPSHOT_THROUGH:
            print(f"[label] WARNING: today {today_str} is past the membership snapshot "
                  f"({sp500_pit_mod.SNAPSHOT_THROUGH}); recent index changes may be "
                  f"missing — refresh data/sp500_ticker_start_end.csv.", file=sys.stderr)
    else:
        hf = _load_hard_filter()
        tickers = hf.load_universe(args.universe, "US")
    if args.limit:
        tickers = tickers[:args.limit]
    print(f"[label] universe={args.universe} tickers={len(tickers)} "
          f"lookback={args.lookback_days}d")

    history = _adj_close_history(tickers, period)
    fetch_ratio = len(history) / len(tickers) if tickers else 1.0
    print(f"[label] fetched history for {len(history)}/{len(tickers)} tickers "
          f"({fetch_ratio:.0%})")
    # SHRINK ALERT: if a large fraction of the requested universe failed to fetch, the
    # scanned universe silently shrank — downstream coverage would over-state
    # representativeness. Warn loudly (the coverage gate also reads tickers_scanned).
    if fetch_ratio < 0.9:
        print(f"[label] WARNING: only {fetch_ratio:.0%} of requested tickers fetched — "
              f"{len(tickers) - len(history)} dropped (network/delisting). The scanned "
              f"universe shrank; coverage may be over-stated.", file=sys.stderr)

    all_events: list[dict] = []
    scanned_tickers: list[str] = []
    pit_dropped = 0
    for t, close in history.items():
        close = close[close.index.date >= cutoff]
        # A ticker counts as "scanned" only if it has enough in-window history to
        # detect an episode — that's the population controls must be drawn from too.
        if len(close) >= 30:
            scanned_tickers.append(t)
        evs = label_ticker(t, close, DEFAULT_THRESHOLDS)
        if pit:
            # Keep an episode only if the ticker was ACTUALLY an index member on the
            # surge day — this removes the "joined the index AFTER surging" inflation
            # (e.g. APP/HOOD/SNDK/CVNA surged before joining S&P 500).
            kept = [e for e in evs if sp500_pit_mod.was_member(t, e["surge_start"])]
            pit_dropped += len(evs) - len(kept)
            evs = kept
        all_events.extend(evs)

    # Episode-level counts: how many DISTINCT run-ups hit each threshold.
    per_threshold: dict[str, int] = {}
    for e in all_events:
        for lab in e["thresholds_hit"]:
            per_threshold[lab] = per_threshold.get(lab, 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe": args.universe,
        "lookback_days": args.lookback_days,
        "thresholds": [{"label": l, "pct": p, "window": w}
                       for l, p, w in DEFAULT_THRESHOLDS],
        # tickers_scanned is the ANALYZABLE population (>=30 in-window closes = the
        # universe events+controls are built from), NOT every fetched ticker. The
        # coverage gate must judge representativeness on what was actually analyzed.
        "tickers_scanned": len(scanned_tickers),
        "fetched_history_count": len(history),
        "unscannable_count": len(history) - len(scanned_tickers),
        "scanned_tickers": sorted(scanned_tickers),
        "event_count": len(all_events),
        "event_count_by_threshold": per_threshold,
        # Point-in-time membership provenance (sp500_pit only). When True the
        # "joined-after-surging" bias is removed; downstream gates may relax the
        # survivorship block but MUST keep delisted_data_gap visible.
        "point_in_time_membership": pit,
        "membership_index": "sp500" if pit else None,
        "membership_snapshot_through": (sp500_pit_mod.SNAPSHOT_THROUGH if pit else None),
        "membership_snapshot_age_days": (
            sp500_pit_mod.snapshot_age_days(str(datetime.now(timezone.utc).date()))
            if pit else None),
        # A stale snapshot misses index changes after SNAPSHOT_THROUGH → not actionable.
        "membership_stale": (
            sp500_pit_mod.is_stale(str(datetime.now(timezone.utc).date())) if pit else False),
        "delisted_data_gap": pit,
        "pit_events_dropped": pit_dropped,
        "caveats": ([
            "Point-in-time S&P 500 membership applied: episodes are kept only if the "
            "ticker was an actual index member on the surge day, so the "
            "'joined-after-surging' bias is removed.",
            "RESIDUAL: fully-delisted past members have no free yfinance price history, "
            "so deeply-delisted surgers are still absent (delisted_data_gap).",
            "Magnitude uses adjusted Close; reconstruction re-fetches "
            "auto_adjust=False to match the live engine.",
        ] if pit else [
            "Survivorship bias: index lists are CURRENT members only; delisted "
            "surgers are absent and some names joined AFTER surging.",
            "Magnitude uses adjusted Close; reconstruction re-fetches "
            "auto_adjust=False to match the live engine.",
        ]),
        "events": all_events,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[label] {len(all_events)} events ({per_threshold}) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
