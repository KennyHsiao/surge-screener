#!/usr/bin/env python3
"""Forward validation for the volume-ignition lane — does the live hit-rate hold up?

The retrospective is survivorship-blocked, so the lane can't be made actionable from it.
The honest path is forward accumulation: each daily scan (oversold_reversal_scan.py)
drops a dated reports/oversold_reversal/scan_*.json. Those ARE the forward snapshots.
This script reads all of them, de-dupes each (ticker, ignition) once, follows every
RESOLVED entry forward, and reports the realized hit-rate per surge tier with a Wilson
interval — PROVISIONAL until enough entries resolve.

A hit-rate is not yet a LIFT (that needs a live non-lane baseline — future work); for now
it answers "do oversold-reversal entries keep reaching +30/+40/+50% at a rate consistent
with the retro's validated prior?". Entry = the scan-day close; forward gain = max forward
Close / entry − 1 within each tier's window. An entry is RESOLVED only once its full window
has elapsed; otherwise it is pending and excluded.

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

# (tier label, pct, window sessions) — must match retro_surge_label.DEFAULT_THRESHOLDS.
TIERS = [("+30%/20d", 0.30, 20), ("+40%/40d", 0.40, 40), ("+50%/60d", 0.50, 60)]
MIN_RESOLVED = 100  # below this the verdict stays PROVISIONAL


def _collect_entries() -> list[dict]:
    """One entry per (ticker, ignition_date) across all dated scans (earliest wins)."""
    seen: dict[tuple, dict] = {}
    for f in sorted(OUT_DIR.glob("scan_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("candidates", []):
            key = (c["ticker"], c.get("ignition_date") or d.get("as_of_date"))
            entry = {"ticker": c["ticker"],
                     "entry_date": d.get("as_of_date"),
                     "entry_price": c.get("last_price")}
            if key not in seen or entry["entry_date"] < seen[key]["entry_date"]:
                seen[key] = entry
    return list(seen.values())


def _resolve(entry: dict) -> dict | None:
    """Follow one entry forward; return per-tier hit flags + resolved/pending, or None."""
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
    close = fwd["Close"].to_numpy(dtype=float)
    out = {"ticker": entry["ticker"], "entry_date": entry["entry_date"], "tiers": {}}
    for label, pct, win in TIERS:
        seg = close[1:win + 1]
        resolved = (len(close) - 1) >= win  # full window elapsed in available data
        hit = bool(seg.size and float(seg.max()) / base - 1.0 >= pct)
        out["tiers"][label] = {"resolved": resolved, "hit": hit}
    return out


def main() -> int:
    entries = _collect_entries()
    resolved_rows = [r for r in (_resolve(e) for e in entries) if r is not None]

    by_tier = {}
    for label, pct, win in TIERS:
        res = [r for r in resolved_rows if r["tiers"][label]["resolved"]]
        hits = sum(1 for r in res if r["tiers"][label]["hit"])
        n = len(res)
        lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)
        by_tier[label] = {"resolved": n, "hits": hits,
                          "hit_rate": round(hits / n, 4) if n else None,
                          "wilson90": [round(lo, 4), round(hi, 4)]}

    total_resolved = max((t["resolved"] for t in by_tier.values()), default=0)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "oversold_reversal",
        "entries_accumulated": len(entries),
        "total_resolved": total_resolved,
        "min_resolved_for_verdict": MIN_RESOLVED,
        "verdict": ("PROVISIONAL — sample below threshold, indicative only"
                    if total_resolved < MIN_RESOLVED else "MATURE"),
        "note": "Forward realized hit-rate per surge tier — NOT a lift (no live non-lane "
                "baseline yet) and NOT comparable to the retro's 4.17x module lift, which "
                "is itself largely a %-runway artifact (see retro_confound_check.py). "
                "Entry = scan-day close; only entries whose full forward window has elapsed "
                "are counted. The runway-independent validated signal is the volume ignition.",
        "by_tier": by_tier,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[oversold-fwd] {len(entries)} entries, {total_resolved} resolved → "
          f"{payload['verdict']}")
    for label, t in by_tier.items():
        print(f"  {label}: {t['hits']}/{t['resolved']} hit "
              f"(rate {t['hit_rate']}, 90% CI {t['wilson90']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
