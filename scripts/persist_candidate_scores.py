#!/usr/bin/env python3
"""Persist scored candidates with explicit full-vs-bounded cohort provenance."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def _read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def persist_snapshot(
    ranked_path: str | Path,
    scored_path: str | Path,
    output_dir: str | Path,
) -> Path:
    ranked = _read_object(Path(ranked_path))
    scored = _read_object(Path(scored_path))
    ranked_rows = ranked.get("tickers")
    if not isinstance(ranked_rows, list):
        ranked_rows = ranked.get("ranked_candidates")
    scored_rows = scored.get("all_scored")
    if not isinstance(ranked_rows, list) or not isinstance(scored_rows, list):
        raise ValueError("ranked and scored candidate arrays are required")
    ranked_tickers = [str(row.get("ticker") or "").upper() for row in ranked_rows
                      if isinstance(row, dict)]
    scored_tickers = [str(row.get("ticker") or "").upper() for row in scored_rows
                      if isinstance(row, dict)]
    complete_same_cohort = (
        len(scored_tickers) == len(ranked_tickers)
        and all(ranked_tickers)
        and len(set(scored_tickers)) == len(scored_tickers)
        and len(set(ranked_tickers)) == len(ranked_tickers)
        and set(scored_tickers) == set(ranked_tickers)
    )
    if scored.get("remaining_unscored") != 0 or not complete_same_cohort:
        raise ValueError("scored cohort is incomplete or differs from ranked membership")
    cohort_count = len(ranked_tickers)
    declared_cohort_count = ranked.get("ranked_candidates_count")
    if isinstance(declared_cohort_count, int) and declared_cohort_count != cohort_count:
        raise ValueError("ranked_candidates_count differs from ranked membership")
    universe_count = ranked.get("all_ranked_count")
    if not isinstance(universe_count, int) or universe_count < cohort_count:
        raise ValueError("all_ranked_count must cover the scored cohort")
    ranked_scan_date = str(ranked.get("scan_date") or "")[:10]
    scored_scan_date = str(scored.get("scan_date") or "")[:10]
    date.fromisoformat(ranked_scan_date)
    date.fromisoformat(scored_scan_date)
    if scored_scan_date != ranked_scan_date:
        raise ValueError("ranked and scored scan_date values must match")
    scan_date = scored_scan_date
    bounded = universe_count != cohort_count
    snapshot = dict(scored)
    snapshot.update({
        "cohort_type": "bounded_top_n" if bounded else "full_ranked_universe",
        "ranked_universe_count": universe_count,
        "scored_cohort_count": cohort_count,
        "selection_method": "deterministic_top_n" if bounded else "all_ranked",
        "rank_limit": ranked.get("rank_limit") or cohort_count,
        "ranking_model": ranked.get("scoring_model"),
    })
    target = Path(output_dir) / f"{scan_date}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")
    tmp.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist candidate score snapshot")
    parser.add_argument("--ranked", default="ranked_candidates.json")
    parser.add_argument("--scored", default="scored_candidates.json")
    parser.add_argument("--output-dir", default="reports/candidate_scores")
    args = parser.parse_args(argv)
    print(persist_snapshot(args.ranked, args.scored, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
