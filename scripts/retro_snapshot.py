#!/usr/bin/env python3
"""Surge Retrospective — Phase 2: forward snapshot of ALL hard-filter survivors.

Dim3 (sentiment) and Dim6 (options flow) have NO free historical source — the only
free way to ever validate them is to start recording their values today and label
the outcome later. This appends, once per scan, a row for EVERY scored candidate
(not just the ≥65 BUY picks) into an append-only ledger. Two reasons it captures
ALL survivors, not just picks:

  1. It's the only free path to historical Dim3/Dim6 (see retro_edgar_backfill for
     why Dim2/Dim4 can be backfilled but these can't).
  2. It breaks the selection bias of performance_ledger.csv — by also recording the
     stocks the screener scored LOW, we can later find the ones that surged anyway
     and learn which signals we under-weighted.

After ~60-90 days, retro_forward_lift.py joins these snapshots to realized forward
returns + surge labels and runs the SAME lift algorithm over all seven dimensions.

Idempotent: re-running for a scan_date already present is a no-op (dedup on
scan_date+ticker), so it's safe to wire straight after Stage 2 in the daily pipeline.

CLI:
    python scripts/retro_snapshot.py --input scored_candidates.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "reports" / "retrospective" / "forward_snapshots.csv"

# One row per scored candidate. Dim scores are what retro_forward_lift binarizes;
# the rest is context for the join (entry price is fetched later from scan_date).
FIELDS = [
    "scan_date", "ticker", "verdict", "composite_score", "regime_adjusted_score",
    "technical", "catalyst", "sentiment", "institutional", "sector_market",
    "options_flow", "analyst", "pattern_type", "data_missing",
]


def _row(c: dict, scan_date: str) -> dict:
    scores = c.get("scores", {}) or {}
    tb = c.get("technical_breakdown", {}) or {}
    dm = c.get("data_missing", []) or []
    return {
        "scan_date": scan_date,
        "ticker": c.get("ticker", ""),
        "verdict": c.get("verdict", ""),
        "composite_score": c.get("composite_score", ""),
        "regime_adjusted_score": c.get("regime_adjusted_score", ""),
        "technical": scores.get("technical", ""),
        "catalyst": scores.get("catalyst", ""),
        "sentiment": scores.get("sentiment", ""),
        "institutional": scores.get("institutional", ""),
        "sector_market": scores.get("sector_market", ""),
        "options_flow": scores.get("options_flow", ""),
        "analyst": scores.get("analyst", ""),
        "pattern_type": tb.get("pattern_type", ""),
        "data_missing": "|".join(dm) if isinstance(dm, list) else str(dm),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — forward snapshot")
    ap.add_argument("--input", default="scored_candidates.json")
    ap.add_argument("--output", default=str(OUT))
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[snapshot] no scored file at {src} — nothing to snapshot", file=sys.stderr)
        return 0
    data = json.loads(src.read_text(encoding="utf-8"))
    scan_date = data.get("scan_date", "")
    candidates = data.get("all_scored", []) or []
    if not scan_date or not candidates:
        print("[snapshot] empty scored set — skipping")
        return 0
    # Refuse to snapshot unless the scan is PROVABLY complete: a forward control set
    # built from only some hard-filter survivors biases surger/non-surger lift. Require
    # ALL completeness fields present AND consistent (fail closed on missing metadata —
    # a legacy/producer-skewed file that omits the fields must NOT slip through).
    remaining = data.get("remaining_unscored")
    scored_n = data.get("scored_candidates_count")
    total_n = data.get("total_candidates")
    complete = (remaining == 0 and scored_n is not None and total_n is not None
                and scored_n == total_n and len(candidates) == total_n)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not complete:
        reason = (f"cohort not provably complete (scored={scored_n} total={total_n} "
                  f"remaining={remaining} rows={len(candidates)})")
        print(f"[snapshot] {reason} — refusing to snapshot.", file=sys.stderr)
        # Make the refusal OBSERVABLE (committed) so Phase-2 can't silently stay at
        # zero samples for months behind a continue-on-error workflow step.
        _write_status(out.parent, scan_date, appended=0, refused=True, reason=reason)
        return 0

    # Dedup on (scan_date, ticker) so re-runs are no-ops.
    seen = set()
    if out.exists():
        with open(out, newline="") as f:
            for r in csv.DictReader(f):
                seen.add((r.get("scan_date"), r.get("ticker")))

    new_rows = [_row(c, scan_date) for c in candidates
                if (scan_date, c.get("ticker", "")) not in seen]

    write_header = not out.exists()
    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(new_rows)

    print(f"[snapshot] appended {len(new_rows)} rows for {scan_date} "
          f"({len(candidates) - len(new_rows)} already present) → {out}")
    _write_status(out.parent, scan_date, appended=len(new_rows), refused=False, reason="")
    return 0


def _write_status(out_dir: Path, scan_date: str, appended: int,
                  refused: bool, reason: str) -> None:
    """Write a committed status artifact so a refusal / no-op is observable in git."""
    try:
        (out_dir / "snapshot_status.json").write_text(json.dumps({
            "scan_date": scan_date, "appended": appended,
            "refused": refused, "reason": reason,
        }, indent=2), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
