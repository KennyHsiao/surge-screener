#!/usr/bin/env python3
"""Surge Retrospective — Phase 2: forward lift over all seven dimensions.

Once retro_snapshot.py has accumulated ~60-90 days of forward_snapshots.csv, this
closes the loop: it fetches each snapshot's realized forward returns, labels which
ones actually surged (+30% within 60d — the screener's target), and runs the SAME
lift algorithm as Phase 1 — but now the positives are surgers and the negatives are
the non-surgers IN THE SAME SNAPSHOT SET (a built-in, unbiased control group, no
random sampling needed). Crucially this covers the two dimensions that have no free
history — Dim3 (sentiment) and Dim6 (options flow) — plus the other four as a
forward cross-check of the EDGAR/technical findings.

Each dimension score is binarized high/low at its cohort median, then lift =
P(high | surged) / P(high | not surged). Reuses retro_factor_lift.compute_lift for
the numpy lift / bootstrap CI / support-gated verdicts, and 07_verify_returns for
the price join — so there is one lift engine and one return-computation, shared.

CLI:
    python scripts/retro_forward_lift.py                 # default 60d min age
    python scripts/retro_forward_lift.py --min-age-days 30 --hit hit_15pct_within_30d
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

import retro_factor_lift as rfl  # noqa: E402 — reuse the lift engine

# Dimension score column → (dimension, label, description) for the lift table.
DIM_FACTORS = {
    "technical":     ("Dim1", "Technical", "技術面分數高於中位"),
    "catalyst":      ("Dim2", "Catalyst", "催化劑分數高於中位"),
    "sentiment":     ("Dim3", "Sentiment", "情緒分數高於中位"),
    "institutional": ("Dim4", "Institutional", "機構/籌碼分數高於中位"),
    "sector_market": ("Dim5", "Sector", "板塊/市場分數高於中位"),
    "options_flow":  ("Dim6", "Options Flow", "選擇權流分數高於中位"),
    "analyst":       ("Dim7", "Analyst", "分析師共識分數高於中位"),
}


def _load_verify():
    """Import scripts/07_verify_returns.py (leading digit blocks a plain import)."""
    spec = importlib.util.spec_from_file_location(
        "verify_returns", REPO / "scripts" / "07_verify_returns.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — forward lift")
    ap.add_argument("--snapshots", default=str(OUT_DIR / "forward_snapshots.csv"))
    ap.add_argument("--output", default=str(OUT_DIR / "forward_factor_lift.json"))
    ap.add_argument("--min-age-days", type=int, default=60,
                    help="only score snapshots at least this old (need the fwd window)")
    ap.add_argument("--hit", default="hit_30pct_within_60d",
                    choices=["hit_30pct_within_60d", "hit_15pct_within_30d"])
    ap.add_argument("--provider", default="yfinance", choices=["polygon", "yfinance"])
    args = ap.parse_args()

    snap = Path(args.snapshots)
    if not snap.exists():
        print(f"[fwd-lift] no snapshots at {snap} — run retro_snapshot.py first "
              f"(needs ~{args.min_age_days}d of accumulation).", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(open(snap, newline="")))
    today = datetime.now(timezone.utc).date()
    vr = _load_verify()

    # 1) Realized outcome per snapshot old enough to have the forward window.
    scored = []
    for r in rows:
        sd = r.get("scan_date", "")
        try:
            scan_dt = datetime.strptime(sd, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - scan_dt).days < args.min_age_days:
            continue
        ticker = r.get("ticker", "")
        prices = vr.get_price_data(
            ticker, sd, (scan_dt + timedelta(days=70)).strftime("%Y-%m-%d"),
            provider=args.provider)
        if prices is None or prices.empty:
            continue
        entry = float(prices.iloc[0])
        if entry <= 0:
            continue
        fwd = vr.compute_forward_returns(entry, prices, sd)
        surged = bool(fwd.get(args.hit))
        scored.append({"row": r, "surged": surged})

    if len(scored) < 10:
        print(f"[fwd-lift] only {len(scored)} resolvable snapshots — too few to lift. "
              f"Let retro_snapshot accumulate more (need weeks of daily scans).",
              file=sys.stderr)
        # Still write a stub so the dashboard can show "accumulating".
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "accumulating",
            "resolved_snapshots": len(scored),
            "hit_metric": args.hit,
        }, indent=2), encoding="utf-8")
        return 0

    # 2) Binarize each dimension at its cohort median (high vs low).
    medians = {}
    for col in DIM_FACTORS:
        vals = [v for v in (_f(s["row"].get(col)) for s in scored) if v is not None]
        medians[col] = float(np.median(vals)) if vals else None

    def _flags(row):
        out = {}
        for col in DIM_FACTORS:
            v, med = _f(row.get(col)), medians[col]
            out[f"{col}_high"] = (v >= med) if (v is not None and med is not None) else None
        return out

    surgers = [{"flags": _flags(s["row"])} for s in scored if s["surged"]]
    controls = [{"flags": _flags(s["row"])} for s in scored if not s["surged"]]

    factor_defs = {f"{col}_high": {"dimension": d, "subfactor": lbl, "desc": desc}
                   for col, (d, lbl, desc) in DIM_FACTORS.items()}

    rng = np.random.default_rng(rfl.SEED)
    table = rfl.compute_lift(surgers, controls, factor_defs, rng)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "hit_metric": args.hit,
        "resolved_snapshots": len(scored),
        "surgers": len(surgers),
        "non_surgers": len(controls),
        "low_confidence": len(surgers) < 20,
        "medians": medians,
        "note": "Forward lift over ALL seven dimensions; positives=surgers, "
                "negatives=non-surgers in the same snapshot set (built-in control). "
                "Covers Dim3/Dim6 which have no free history.",
        "factors": table,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[fwd-lift] {len(surgers)} surgers / {len(controls)} non-surgers → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
