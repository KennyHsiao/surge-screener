#!/usr/bin/env python3
"""Forward validation for the coiled-base lane — does the live edge hold up?

The retrospective is survivorship-blocked, so the lane can't be made actionable from it.
The honest path is forward accumulation: each daily scan (oversold_reversal_scan.py)
drops a dated reports/oversold_reversal/scan_*.json. Those ARE the forward snapshots.
This script reads only the CURRENT lane's snapshots (matched by lane_id), de-dupes each
(ticker, signal_date) once, enters at the signal close, follows every RESOLVED entry
forward, and reports — per surge tier — both:

  * the realized TOUCH hit-rate (did a Close ever reach +30/+40/+50% in the window?) with
    a Wilson interval — answers "do entries keep reaching the tier at the retro's prior?";
  * the strategy-level EXPECTED VALUE of actually trading the signal: enter at the signal
    close, hold to the window end, exit at that Close (a real, no-look-ahead rule — NOT the
    max, which assumes you sold the top). Mean = EV, plus median / win-rate / a simple
    equity curve, AND the EXCESS vs SPY over the same dates so EV reflects *edge*, not the
    market's drift (this is the baseline the touch hit-rate alone still lacks).

Both stay PROVISIONAL until MIN_RESOLVED entries resolve. An entry is RESOLVED only once
its full forward window has elapsed; otherwise it is pending and excluded. EV is gross of
costs/slippage and the equity curve treats entries as one-at-a-time sequential trades
(ignores overlap) — read it as a sanity curve, not a backtested P&L.

CLI:
    python scripts/oversold_reversal_forward.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "oversold_reversal"

import retro_factor_lift as rfl  # noqa: E402 — reuse the Wilson interval
import retro_reconstruct as rr   # noqa: E402 — reuse the cached OHLCV fetch
from oversold_reversal_scan import LANE_ID  # noqa: E402 — the CURRENT lane definition id

# (tier label, pct, window sessions) — must match retro_surge_label.DEFAULT_THRESHOLDS.
TIERS = [("+30%/20d", 0.30, 20), ("+40%/40d", 0.40, 40), ("+50%/60d", 0.50, 60)]
MIN_RESOLVED = 100  # below this the verdict stays PROVISIONAL


def evaluate_entry(close: np.ndarray, spy_close: np.ndarray) -> dict:
    """PURE (no I/O — unit-testable without network) per-tier outcome for one entry.

    `close[0]` / `spy_close[0]` are the entry-day Closes; index i is the i-th forward
    session, SPY date-aligned to the stock. Per tier returns:
      * resolved   — the full window has elapsed (close[win] exists),
      * hit        — TOUCH: a Close in (0, win] reached +pct (optimistic / sold-the-top),
      * horizon_return     — REALIZED: close[win]/close[0] - 1 (hold-to-window-end exit),
      * spy_horizon_return — SPY over the SAME entry→win span,
      * excess_return      — horizon_return - spy_horizon_return (the edge over the market).
    Touch is reported even when unresolved (it can only become true with more data);
    horizon/excess are None until resolved so EV never counts a half-formed window."""
    base = float(close[0])
    spy_base = float(spy_close[0]) if spy_close.size else float("nan")
    out: dict[str, dict] = {}
    for label, pct, win in TIERS:
        seg = close[1:win + 1]
        touch = bool(seg.size and float(seg.max()) / base - 1.0 >= pct)
        # Resolved needs the win-th forward Close for BOTH legs (SPY is date-aligned, so it
        # normally has it whenever the stock does; guard anyway so a short SPY tail can't
        # silently drop the baseline and inflate excess).
        resolved = (len(close) - 1) >= win and (len(spy_close) - 1) >= win and spy_base > 0
        if resolved:
            hz = float(close[win]) / base - 1.0
            spy_hz = float(spy_close[win]) / spy_base - 1.0
            excess = hz - spy_hz
        else:
            hz = spy_hz = excess = None
        out[label] = {"resolved": resolved, "hit": touch,
                      "horizon_return": hz, "spy_horizon_return": spy_hz,
                      "excess_return": excess}
    return out


def _mean_block(xs: list[float]) -> dict:
    """Mean (EV) + median + win-rate + a normal-approx 90% CI on the mean. Pure."""
    n = len(xs)
    if n == 0:
        return {"n": 0, "ev": None, "median": None, "win_rate": None,
                "ci90": [None, None], "std": None}
    arr = np.asarray(xs, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    half = 1.645 * std / (n ** 0.5) if n > 1 else 0.0   # z₀.₀₅, normal approx (labelled)
    return {"n": n, "ev": round(mean, 4), "median": round(float(np.median(arr)), 4),
            "win_rate": round(float((arr > 0).mean()), 4),
            "ci90": [round(mean - half, 4), round(mean + half, 4)],
            "std": round(std, 4)}


def _aggregate_tier(resolved_rows: list[dict], label: str) -> dict:
    """PURE aggregation for one tier over the resolved entries (each row carries
    `entry_date` + `tiers[label]`). Touch hit-rate (Wilson) + EV/excess (mean blocks) +
    a one-trade-at-a-time equity curve ordered by entry_date."""
    res = [r for r in resolved_rows if r["tiers"][label]["resolved"]]
    n = len(res)
    hits = sum(1 for r in res if r["tiers"][label]["hit"])
    lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)

    hz = [r["tiers"][label]["horizon_return"] for r in res]
    ex = [r["tiers"][label]["excess_return"] for r in res]
    ev = _mean_block(hz)
    exb = _mean_block(ex)

    ordered = sorted(res, key=lambda r: r.get("entry_date") or "")
    equity, curve = 1.0, []
    for r in ordered:
        equity *= 1.0 + r["tiers"][label]["horizon_return"]
        curve.append([r.get("entry_date"), round(equity, 4)])

    return {
        "resolved": n, "hits": hits,
        "hit_rate": round(hits / n, 4) if n else None,
        "wilson90": [round(lo, 4), round(hi, 4)],
        "ev_horizon": ev["ev"], "median_horizon": ev["median"],
        "win_rate_horizon": ev["win_rate"], "ev_horizon_ci90": ev["ci90"],
        "ev_excess_vs_spy": exb["ev"], "excess_win_rate": exb["win_rate"],
        "ev_excess_ci90": exb["ci90"],
        "equity_multiple": round(equity, 4) if n else None,
        "equity_curve": curve,
    }


def _collect_entries() -> list[dict]:
    """One entry per (ticker, signal_date) — ONLY this lane's snapshots (module=coiled_base),
    so the hit-rate never matures on a MIXED population (the dir may still hold legacy
    volume_ignition scans). Entry date = the candidate's `signal_date` (the actual signal
    close), NOT the file `as_of_date` — a weekend/holiday scan would otherwise enter a
    session late and corrupt the realized gain."""
    seen: dict[tuple, dict] = {}
    for f in sorted(OUT_DIR.glob("scan_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Isolate by the EXACT lane definition (lane_id), not the coarse `module` — so a
        # future gate change (lane_id v2) with the same module never mixes into this
        # population. Legacy scans (no lane_id) are excluded.
        if d.get("lane_id") != LANE_ID:
            continue
        for c in d.get("candidates", []):
            sdate = c.get("signal_date") or c.get("as_of") or d.get("as_of_date")
            key = (c["ticker"], sdate)
            entry = {"ticker": c["ticker"], "entry_date": sdate,   # enter at the signal close
                     "entry_price": c.get("last_price")}
            if key not in seen or (entry["entry_date"] or "") < (seen[key]["entry_date"] or ""):
                seen[key] = entry
    return list(seen.values())


_SPY_CACHE: dict[str, pd.Series | None] = {}


def _spy_close() -> pd.Series | None:
    """SPY Close indexed by normalized date, fetched once (the market baseline)."""
    if "spy" not in _SPY_CACHE:
        df = rr._hist_auto_adjust_false("SPY", "2y")
        if df is not None:
            df = df.copy()
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            _SPY_CACHE["spy"] = df["Close"]
        else:
            _SPY_CACHE["spy"] = None
    return _SPY_CACHE["spy"]


def _resolve(entry: dict) -> dict | None:
    """Follow one entry forward; return per-tier outcomes (via the pure evaluate_entry),
    or None if prices are unavailable. SPY is date-aligned to the stock's forward sessions
    so the +win horizon is the SAME calendar span for both legs."""
    df = rr._hist_auto_adjust_false(entry["ticker"], "2y")
    if df is None:
        return None
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    ed = pd.Timestamp(entry["entry_date"]).normalize()
    fwd = df[df.index >= ed]
    if len(fwd) < 1:
        return None
    base = float(fwd["Close"].iloc[0])
    if base <= 0:
        return None
    spy = _spy_close()
    if spy is None:
        return None
    spy_fwd = spy.reindex(fwd.index, method="ffill")  # SPY Close on each stock-forward date
    close = fwd["Close"].to_numpy(dtype=float)
    spy_close = spy_fwd.to_numpy(dtype=float)
    return {"ticker": entry["ticker"], "entry_date": entry["entry_date"],
            "tiers": evaluate_entry(close, spy_close)}


def main() -> int:
    entries = _collect_entries()
    resolved_rows = [r for r in (_resolve(e) for e in entries) if r is not None]

    by_tier = {label: _aggregate_tier(resolved_rows, label) for label, _p, _w in TIERS}

    total_resolved = max((t["resolved"] for t in by_tier.values()), default=0)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "coiled_base",
        "lane_id": LANE_ID,
        "entries_accumulated": len(entries),
        "total_resolved": total_resolved,
        "min_resolved_for_verdict": MIN_RESOLVED,
        "verdict": ("PROVISIONAL — sample below threshold, indicative only"
                    if total_resolved < MIN_RESOLVED else "MATURE"),
        "note": "Two readings per surge tier. (1) TOUCH hit-rate: a Close reached +pct in "
                "the window (optimistic — assumes you sold the top); Wilson 90% CI. (2) "
                "STRATEGY EV: enter at the signal close, hold to the window end, exit at "
                "that Close (real, no look-ahead) → ev_horizon (mean realized return), with "
                "ev_excess_vs_spy = the same minus SPY over the same dates = the edge over "
                "market drift (the baseline a bare hit-rate lacks). EV is GROSS of "
                "costs/slippage; equity_curve treats entries as one-at-a-time sequential "
                "trades (ignores overlap) — a sanity curve, not a backtest. The lane gates "
                "on the runway-INDEPENDENT pair bb_squeeze & rsi_40_65 (validated under the "
                "ATR-neutral target; see lane_runway_check.py). ⚠ Pre-rewrite scans were the "
                "OLD rvol+oversold lane — clear reports/oversold_reversal/scan_*.json to "
                "accumulate a clean baseline.",
        "by_tier": by_tier,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[oversold-fwd] {len(entries)} entries, {total_resolved} resolved → "
          f"{payload['verdict']}")
    for label, t in by_tier.items():
        print(f"  {label}: touch {t['hits']}/{t['resolved']} "
              f"(rate {t['hit_rate']}, 90% CI {t['wilson90']}) | "
              f"EV {t['ev_horizon']} (excess vs SPY {t['ev_excess_vs_spy']}, "
              f"win {t['win_rate_horizon']}, eq×{t['equity_multiple']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
