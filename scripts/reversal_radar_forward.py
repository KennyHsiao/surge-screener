#!/usr/bin/env python3
"""Forward validation for the Reversal Radar — does a TURNING+ reversal signal pay off?

The reversal factors are EXPLORATORY (not runway-validated). This harness is what can
eventually earn the actionable label: each daily reversal scan (reversal_radar_scan.py)
drops a dated scan_*.json; those ARE the forward snapshots. We read only the CURRENT
reversal lane's snapshots (matched by REVERSAL_LANE_ID), de-dupe each (ticker, signal_date),
enter at the signal close, follow every RESOLVED entry forward, and report — PER TIER —
both a TOUCH hit-rate (did a Close reach the bounce target?) and the strategy EV (enter at
signal close, hold to window end, exit there — no look-ahead), with a SPY (β=1) baseline.

Targets are BOUNCE-sized, not surge-sized: catching a low for a moderate reversal, not a
+30% rip. (+10%/20d, +15%/40d, +20%/60d.)

Honesty (same as the coiled-base forward harness, by design — see its docstring): the scan
universe is CURRENT membership (a name beaten-down before joining the index still counts),
delisted entries have no yfinance history and DROP silently (their — often worst — outcomes
never reach EV), EV is GROSS of costs, the equity curve is one-trade-at-a-time, and the CI
is a normal approximation. All of this biases the numbers OPTIMISTIC and is disclosed
(dropped_pct, survivorship, ev_caveats). This is cloned from oversold_reversal_forward.py —
keep the methodology in sync; reuses its pure _mean_block + retro_factor_lift._wilson.

CLI:  python scripts/reversal_radar_forward.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

OUT_DIR = REPO / "reports" / "reversal_radar"

import retro_factor_lift as rfl  # noqa: E402 — Wilson interval
import retro_reconstruct as rr   # noqa: E402 — cached OHLCV fetch
from oversold_reversal_forward import _mean_block  # noqa: E402 — pure EV stat block (in sync)
from reversal_radar_scan import REVERSAL_LANE_ID  # noqa: E402

# bounce-sized tiers (reversal = a moderate recovery off the low, not a surge)
TIERS = [("+10%/20d", 0.10, 20), ("+15%/40d", 0.15, 40), ("+20%/60d", 0.20, 60)]
MIN_RESOLVED = 100  # below this the verdict stays PROVISIONAL


def evaluate_entry(close: np.ndarray, spy_close: np.ndarray) -> dict:
    """PURE per-tier outcome for one entry (no I/O). close[0]/spy_close[0] = entry-day Closes;
    index i = i-th forward session (SPY date-aligned). Touch = a Close reached +pct (optimistic,
    sold-the-top); horizon = hold-to-window-end realized return; excess = horizon − SPY (β=1).
    Resolved only when the window elapsed AND both endpoints are real (non-NaN) so EV never
    counts a half-formed/NaN window; baseline_ok is a SEPARATE gate (SPY non-NaN at entry+win,
    no ffill)."""
    base = float(close[0]) if close.size else float("nan")
    spy_base = float(spy_close[0]) if spy_close.size else float("nan")
    out: dict[str, dict] = {}
    for label, pct, win in TIERS:
        seg = close[1:win + 1]
        touch = bool(seg.size and np.isfinite(base) and base > 0
                     and np.isfinite(float(seg.max())) and float(seg.max()) / base - 1.0 >= pct)
        resolved = bool((len(close) - 1) >= win and np.isfinite(base) and base > 0
                        and np.isfinite(close[win]))
        baseline_ok = bool(resolved and (len(spy_close) - 1) >= win
                           and np.isfinite(spy_base) and spy_base > 0
                           and np.isfinite(spy_close[win]))
        hz = (float(close[win]) / base - 1.0) if resolved else None
        if baseline_ok:
            spy_hz = float(spy_close[win]) / spy_base - 1.0
            excess = hz - spy_hz
        else:
            spy_hz = excess = None
        out[label] = {"resolved": resolved, "baseline_ok": baseline_ok, "hit": touch,
                      "horizon_return": hz, "spy_horizon_return": spy_hz, "excess_return": excess}
    return out


def _aggregate_tier(resolved_rows: list[dict], label: str) -> dict:
    res = [r for r in resolved_rows if r["tiers"][label]["resolved"]]
    n = len(res)
    hits = sum(1 for r in res if r["tiers"][label]["hit"])
    lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)
    hz = [r["tiers"][label]["horizon_return"] for r in res]
    ex = [r["tiers"][label]["excess_return"] for r in res if r["tiers"][label]["excess_return"] is not None]
    ev, exb = _mean_block(hz), _mean_block(ex)
    ordered = sorted(res, key=lambda r: r.get("entry_date") or "")
    equity, curve = 1.0, []
    for r in ordered:
        equity *= 1.0 + r["tiers"][label]["horizon_return"]
        curve.append([r.get("entry_date"), round(equity, 4)])
    return {"resolved": n, "hits": hits, "hit_rate": round(hits / n, 4) if n else None,
            "wilson90": [round(lo, 4), round(hi, 4)],
            "ev_horizon": ev["ev"], "median_horizon": ev["median"],
            "win_rate_horizon": ev["win_rate"], "ev_horizon_ci90": ev["ci90"],
            "ev_excess_vs_spy": exb["ev"], "excess_n": exb["n"],
            "excess_win_rate": exb["win_rate"], "ev_excess_ci90": exb["ci90"],
            "equity_multiple": round(equity, 4) if n else None, "equity_curve": curve}


def _collect_entries() -> list[dict]:
    """One entry per (ticker, signal_date), ONLY this reversal lane's snapshots (REVERSAL_LANE_ID),
    so the hit-rate never matures on a mixed/old population. Entry = the signal close date."""
    seen: dict[tuple, dict] = {}
    for f in sorted(OUT_DIR.glob("scan_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("lane_id") != REVERSAL_LANE_ID:
            continue
        for c in d.get("candidates", []):
            sdate = c.get("signal_date") or d.get("as_of_date")
            key = (c.get("ticker"), sdate)
            if not c.get("ticker"):
                continue
            entry = {"ticker": c["ticker"], "entry_date": sdate,
                     "status": c.get("status"), "reversal_score": c.get("reversal_score")}
            if key not in seen or (entry["entry_date"] or "") < (seen[key]["entry_date"] or ""):
                seen[key] = entry
    return list(seen.values())


_SPY_CACHE: dict[str, pd.Series | None] = {}


def _spy_close() -> pd.Series | None:
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
    ed = pd.to_datetime(entry.get("entry_date"), errors="coerce")
    if pd.isna(ed):
        return None
    ed = ed.normalize()
    df = rr._hist_auto_adjust_false(entry["ticker"], "2y")
    if df is None:
        return None
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    fwd = df[df.index >= ed]
    if len(fwd) < 1:
        return None
    if float(fwd["Close"].iloc[0]) <= 0:
        return None
    spy = _spy_close()
    if spy is None:
        return None
    spy_fwd = spy.reindex(fwd.index)  # NO ffill — a missing SPY tail stays NaN for the baseline gate
    return {"ticker": entry["ticker"], "entry_date": entry["entry_date"],
            "tiers": evaluate_entry(fwd["Close"].to_numpy(float), spy_fwd.to_numpy(float))}


def main() -> int:
    entries = _collect_entries()
    resolved_rows = [r for r in (_resolve(e) for e in entries) if r is not None]
    by_tier = {label: _aggregate_tier(resolved_rows, label) for label, _p, _w in TIERS}
    verdict_by_tier = {label: ("MATURE" if t["resolved"] >= MIN_RESOLVED else "PROVISIONAL")
                       for label, t in by_tier.items()}
    min_resolved = min((t["resolved"] for t in by_tier.values()), default=0)
    dropped = len(entries) - len(resolved_rows)
    dropped_pct = round(dropped / len(entries), 4) if entries else None

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "reversal_radar", "lane_id": REVERSAL_LANE_ID,
        "entries_accumulated": len(entries), "price_resolvable": len(resolved_rows),
        "dropped_count": dropped, "dropped_pct": dropped_pct,
        "min_resolved_across_tiers": min_resolved, "min_resolved_for_verdict": MIN_RESOLVED,
        "verdict": ("PROVISIONAL — sample below threshold, indicative only"
                    if min_resolved < MIN_RESOLVED else "MATURE"),
        "verdict_by_tier": verdict_by_tier,
        "survivorship": {
            "survivorship_free": False,
            "forward_universe": "current membership (beaten_down pre-screen of live sp1500 members)",
            "caveats": [
                "Current-membership scan counts a name beaten-down BEFORE it joined the index.",
                "Delisted names have no yfinance history → dropped (see dropped_pct); their "
                "outcomes (often the worst) never reach EV → EV biased optimistic.",
                "A point-in-time was_member gate is future work.",
            ],
        },
        "ev_caveats": [
            "ev_excess_vs_spy is a BETA=1 adjustment — some 'excess' is beta, not alpha.",
            "EV is GROSS of costs/slippage.",
            "ev_*_ci90 is a seeded bootstrap percentile CI (via the shared _mean_block); "
            "single-stock returns are right-skewed (exploratory).",
            "equity_curve compounds entries one-at-a-time (ignores overlap) — a sanity curve.",
        ],
        "note": "Reversal targets are BOUNCE-sized (+10/15/20%). TOUCH = a Close reached +pct "
                "(optimistic). STRATEGY EV = enter at signal close, hold to window end, exit there. "
                "Reversal factors are EXPLORATORY until this matures (MIN_RESOLVED=100 per tier).",
        "by_tier": by_tier,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    import reversal_radar as _rr
    (OUT_DIR / "validation_summary.json").write_text(
        json.dumps(payload, indent=2, default=_rr.json_default), encoding="utf-8")
    print(f"[reversal-fwd] {len(entries)} entries, {len(resolved_rows)} resolvable, "
          f"{dropped} dropped ({dropped_pct}) → {payload['verdict']}")
    for label, t in by_tier.items():
        print(f"  {label} [{verdict_by_tier[label]}]: touch {t['hits']}/{t['resolved']} "
              f"(rate {t['hit_rate']}, CI {t['wilson90']}) | EV {t['ev_horizon']} gross "
              f"(excess[β=1] {t['ev_excess_vs_spy']} n={t['excess_n']}, eq×{t['equity_multiple']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
