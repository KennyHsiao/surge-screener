#!/usr/bin/env python3
"""Contract tests for provenance-safe bounded candidate score snapshots."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "candidate_score_snapshot_under_test",
        ROOT / "scripts" / "persist_candidate_scores.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("scripts/persist_candidate_scores.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bounded_snapshot_carries_selection_provenance() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked = root / "ranked.json"
        scored = root / "scored.json"
        output = root / "reports" / "candidate_scores"
        ranked.write_text(json.dumps({
            "scan_date": "2026-08-15",
            "all_ranked_count": 864,
            "ranked_candidates_count": 2,
            "rank_limit": 2,
            "scoring_model": "deterministic-v1",
            "tickers": [{"ticker": "AAA"}, {"ticker": "BBB"}],
        }), encoding="utf-8")
        scored.write_text(json.dumps({
            "scan_date": "2026-08-15",
            "remaining_unscored": 0,
            "promotion_reachability_v1": {
                "schema_version": "promotion_reachability_v1",
                "mode": "shadow",
                "authoritative_for_promotion": False,
                "state": "not_reachable",
                "threshold": 65,
                "candidate_adjusted_ceiling_max": 61,
            },
            "all_scored": [{
                "ticker": "AAA",
                "evidence_capabilities": {"schema_version": "evidence_capabilities_v1"},
            }, {"ticker": "BBB"}],
        }), encoding="utf-8")

        path = module.persist_snapshot(ranked, scored, output)
        data = json.loads(path.read_text(encoding="utf-8"))

        expected = {
            "cohort_type": "bounded_top_n",
            "ranked_universe_count": 864,
            "scored_cohort_count": 2,
            "selection_method": "deterministic_top_n",
            "rank_limit": 2,
        }
        actual = {key: data.get(key) for key in expected}
        if actual != expected:
            raise AssertionError(actual)
        if [row.get("ticker") for row in data["all_scored"]] != ["AAA", "BBB"]:
            raise AssertionError(data["all_scored"])
        if data["promotion_reachability_v1"]["candidate_adjusted_ceiling_max"] != 61:
            raise AssertionError(data["promotion_reachability_v1"])
        if data["all_scored"][0]["evidence_capabilities"]["schema_version"] != "evidence_capabilities_v1":
            raise AssertionError(data["all_scored"][0])


def test_complete_scored_cohort_may_finish_out_of_rank_order() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked = root / "ranked.json"
        scored = root / "scored.json"
        ranked.write_text(json.dumps({
            "scan_date": "2026-08-15",
            "all_ranked_count": 2,
            "ranked_candidates_count": 2,
            "tickers": [{"ticker": "AAA"}, {"ticker": "BBB"}],
        }), encoding="utf-8")
        scored.write_text(json.dumps({
            "scan_date": "2026-08-15",
            "remaining_unscored": 0,
            "all_scored": [{"ticker": "BBB"}, {"ticker": "AAA"}],
        }), encoding="utf-8")

        path = module.persist_snapshot(ranked, scored, root / "out")
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("cohort_type") != "full_ranked_universe":
            raise AssertionError(data)
        if {row.get("ticker") for row in data["all_scored"]} != {"AAA", "BBB"}:
            raise AssertionError(data["all_scored"])


def test_snapshot_rejects_mixed_scan_dates() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked = root / "ranked.json"
        scored = root / "scored.json"
        ranked.write_text(json.dumps({
            "scan_date": "2026-08-15",
            "all_ranked_count": 1,
            "ranked_candidates_count": 1,
            "tickers": [{"ticker": "AAA"}],
        }), encoding="utf-8")
        scored.write_text(json.dumps({
            "scan_date": "2026-08-14",
            "remaining_unscored": 0,
            "all_scored": [{"ticker": "AAA"}],
        }), encoding="utf-8")

        try:
            module.persist_snapshot(ranked, scored, root / "out")
        except ValueError as exc:
            if "scan_date values must match" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("snapshot accepted mixed ranked/scored scan dates")


if __name__ == "__main__":
    tests = [
        test_bounded_snapshot_carries_selection_provenance,
        test_complete_scored_cohort_may_finish_out_of_rank_order,
        test_snapshot_rejects_mixed_scan_dates,
    ]
    for test in tests:
        test()
    print(f"candidate score snapshot tests: {len(tests)} passed")
