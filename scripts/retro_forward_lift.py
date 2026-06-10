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

# Tokens in a snapshot's data_missing that mean a dimension's RAW source was absent
# (so its score is a conservative default, not real signal). A dimension is treated
# as unknown (None) — never binarized — when any of its tokens appear.
_DIM_MISSING_TOKENS = {
    "technical":     ["technical"],
    "catalyst":      ["catalyst", "8k_recent_news_catalyst", "news"],
    "sentiment":     ["sentiment", "x_twitter_velocity", "social"],
    "institutional": ["institutional", "13f", "insider"],
    "sector_market": ["sector_market", "sector"],
    "options_flow":  ["options_flow", "options"],
    "analyst":       ["analyst"],
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


def _dim_missing(row: dict, col: str) -> bool:
    """True if dimension `col`'s RAW source was absent for this row. data_missing is
    free-form (e.g. "options_flow — Dimension 6 ..."), so match tokens as SUBSTRINGS."""
    entries = [m.strip().lower() for m in str(row.get("data_missing", "")).split("|") if m.strip()]
    return any(tok in e for e in entries for tok in _DIM_MISSING_TOKENS.get(col, [col]))


def dim_median(scored: list, col: str):
    """Median of a dimension over rows that are parseable AND not data_missing — so a
    placeholder/default score for a missing source can't drag the cohort median (which
    would distort the high/low flags for the rows that DID have data)."""
    import numpy as _np
    vals = [_f(s["row"].get(col)) for s in scored
            if _f(s["row"].get(col)) is not None and not _dim_missing(s["row"], col)]
    return float(_np.median(vals)) if vals else None


def apply_parse_coverage_gate(table: list, n_pos: int, n_neg: int,
                              min_cov: float = 0.5) -> None:
    """Override a factor to INSUFFICIENT when the dimension is known in too small a
    FRACTION of either arm (esp. Dim3/Dim6 where source availability is the main risk):
    enough total rows doesn't help if a factor's verdict rests on a tiny parsed subset.
    Mutates each row in place, recording parse_coverage [surge, control]."""
    for row in table:
        cov_s = row["n_surge"] / n_pos if n_pos else 0.0
        cov_c = row["n_control"] / n_neg if n_neg else 0.0
        row["parse_coverage"] = [round(cov_s, 3), round(cov_c, 3)]
        if min(cov_s, cov_c) < min_cov:
            row["verdict"] = "INSUFFICIENT"
            row["low_parse_coverage"] = True


def dim_flags(row: dict, medians: dict) -> dict:
    """Binarize each dimension at its cohort median, BUT treat a dimension whose RAW
    source was missing as None — its score is a conservative default, not real signal,
    so binarizing it would validate missingness. None is ignored by compute_lift."""
    out = {}
    for col in DIM_FACTORS:
        v, med = _f(row.get(col)), medians.get(col)
        unknown = (v is None or med is None or _dim_missing(row, col))
        out[f"{col}_high"] = None if unknown else (v >= med)
    return out


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

    # 1) Realized outcome per snapshot old enough to have the forward window. Track
    # eligible/resolved so a degraded price-fetch path can't emit "ready" off a tiny,
    # non-representative resolved subset.
    eligible = 0
    scored = []
    for r in rows:
        sd = r.get("scan_date", "")
        try:
            scan_dt = datetime.strptime(sd, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - scan_dt).days < args.min_age_days:
            continue
        eligible += 1
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
        # The hit key is only present when the FULL forward window resolved. A missing
        # key (truncated data, delisting, short series) means UNRESOLVED — it must NOT
        # be coerced to False and contaminate the non-surger control arm.
        if args.hit not in fwd:
            continue
        scored.append({"row": r, "surged": bool(fwd[args.hit])})

    resolved = len(scored)
    resolution_ratio = round(resolved / eligible, 3) if eligible else None
    surger_n = sum(1 for s in scored if s["surged"])
    n_pos, n_neg = surger_n, resolved - surger_n

    # FRESHNESS anchor (Codex r19): forward is UI-only and was structurally invisible to every
    # provenance check (no source block) — a stale/forged forward_factor_lift.json with status=
    # 'ready' + a VALIDATED row rendered ungated beside the (correctly blocked) retro tabs. Stamp
    # the surge_events / surge_features generation CURRENT at compute time so the page can detect a
    # cross-run / stale forward artifact and fail closed. (This is a "computed-against" anchor — the
    # forward lift derives from forward_snapshots.csv, not these — but it ties the artifact to the
    # retro run it is displayed beside.)
    _out_dir = Path(args.output).parent

    def _sibling_gen(name: str):
        try:
            return json.loads((_out_dir / name).read_text(encoding="utf-8")).get("generated_at")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    _source = {"events_generated_at": _sibling_gen("surge_events.json"),
               "features_generated_at": _sibling_gen("surge_features.json")}
    # READY only with enough resolved rows, a high resolution ratio (no degraded fetch),
    # AND both arms populated. Otherwise persist an accumulating stub with the counts.
    MIN_RESOLVED, MIN_RATIO, MIN_ARM = 10, 0.7, 5
    if (resolved < MIN_RESOLVED or (resolution_ratio is not None and resolution_ratio < MIN_RATIO)
            or n_pos < MIN_ARM or n_neg < MIN_ARM):
        print(f"[fwd-lift] not ready: eligible={eligible} resolved={resolved} "
              f"ratio={resolution_ratio} surgers={n_pos} non={n_neg}", file=sys.stderr)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "accumulating",
            "source": _source,
            "hit_metric": args.hit,
            "eligible_snapshots": eligible,
            "resolved_snapshots": resolved,
            "unresolved_snapshots": eligible - resolved,
            "resolution_ratio": resolution_ratio,
            "surgers": n_pos, "non_surgers": n_neg,
        }, indent=2), encoding="utf-8")
        return 0

    # 2) Binarize each dimension at its cohort median (computed over present rows only).
    medians = {col: dim_median(scored, col) for col in DIM_FACTORS}

    surgers = [{"flags": dim_flags(s["row"], medians)} for s in scored if s["surged"]]
    controls = [{"flags": dim_flags(s["row"], medians)} for s in scored if not s["surged"]]

    factor_defs = {f"{col}_high": {"dimension": d, "subfactor": lbl, "desc": desc}
                   for col, (d, lbl, desc) in DIM_FACTORS.items()}

    rng = np.random.default_rng(rfl.SEED)
    table = rfl.compute_lift(surgers, controls, factor_defs, rng)

    apply_parse_coverage_gate(table, len(surgers), len(controls))

    # Per-dimension KNOWN support (rows where the dim was present & not data_missing).
    dim_known = {col: sum(1 for s in scored
                          if _f(s["row"].get(col)) is not None and not _dim_missing(s["row"], col))
                 for col in DIM_FACTORS}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "source": _source,
        "hit_metric": args.hit,
        "eligible_snapshots": eligible,
        "resolved_snapshots": resolved,
        "unresolved_snapshots": eligible - resolved,
        "resolution_ratio": resolution_ratio,
        "surgers": len(surgers),
        "non_surgers": len(controls),
        "low_confidence": len(surgers) < 20,
        "dim_known_counts": dim_known,
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
