#!/usr/bin/env python3
"""Offline tests for Stage 6 ledger extraction."""

from __future__ import annotations

import importlib.util
import csv
import json
import multiprocessing
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "append_ledger_under_test",
        ROOT / "scripts" / "06_append_ledger.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load 06_append_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_extract_picks_enriches_confirmed_pick_from_full_report() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as d:
        report_dir = Path(d) / "reports" / "2026-07-03"
        report_dir.mkdir(parents=True)
        write_json(report_dir / "summary.json", {
            "report_date": "2026-07-03",
            "ranked_picks": [{
                "ticker": "abc",
                "verdict": "BUY",
                "final_score": 88,
                "entry_zone": "$10 – $12",
                "stop_loss": "$9 (hard stop)",
                "position_size_pct": 2.5,
                "key_risk": "earnings gap",
            }],
        })
        write_json(report_dir / "full.json", {
            "regime_context": {"global_score_multiplier": 0.85},
            "scored_data": {
                "all_scored": [{
                    "ticker": "ABC",
                    "scores": {
                        "technical": 24,
                        "catalyst": 12,
                        "sentiment": 8,
                        "institutional": 7,
                        "sector_market": 5,
                        "options_flow": 14,
                        "analyst": 6,
                    },
                    "technical_breakdown": {
                        "pattern_type": "breakout",
                        "macd_state": "bullish_cross",
                        "base_quality": "tight",
                    },
                }],
            },
            "layer2_data": {
                "all_results": [{
                    "ticker": "ABC",
                    "layer2_path": "BREADTH → DEPTH",
                    "final_verdict": "CONTINUE_TO_DD",
                }],
            },
            "dd_data": {
                "all_dd_results": [{
                    "ticker": "ABC",
                    "dd_verdict": "CONFIRMED",
                    "short_thesis_strength": "MODERATE",
                    "short_thesis_summary": "borrow risk is manageable",
                }],
            },
        })

        rows = module.extract_picks_from_report(str(report_dir / "summary.json"))

    require(len(rows) == 1, "expected one row")
    row = rows[0]
    require(row["ticker"] == "abc", "summary ticker casing should be preserved")
    require(row["regime_multiplier"] == 0.85,
            "regime multiplier should come from full.json")
    require(row["tech_score"] == 24, "technical score should be enriched")
    require(row["catalyst_score"] == 12, "catalyst score should be enriched")
    require(row["sentiment_score"] == 8, "sentiment score should be enriched")
    require(row["inst_score"] == 7, "institutional score should be enriched")
    require(row["sector_score"] == 5, "sector score should be enriched")
    require(row["options_score"] == 14, "options score should be enriched")
    require(row["analyst_score"] == 6, "analyst score should be enriched")
    require(json.loads(row["dim1_breakdown"])["base_quality"] == "tight",
            "technical breakdown should be serialized for reflection audits")
    require(row["pattern_type"] == "breakout", "pattern_type should be enriched")
    require(row["macd_state"] == "bullish_cross", "macd state should be enriched")
    require(row["layer2_path"] == "BREADTH → DEPTH", "Layer 2 path should be enriched")
    require(row["layer2_outcome"] == "CONTINUE_TO_DD", "Layer 2 verdict should be enriched")
    require(row["dd_verdict"] == "CONFIRMED", "DD verdict should come from dd_data")
    require(row["dd_short_thesis_strength"] == "MODERATE",
            "DD short thesis strength should be enriched")


def test_extract_picks_keeps_legacy_blank_fields_without_full_report() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as d:
        report_dir = Path(d) / "reports" / "2026-07-04"
        report_dir.mkdir(parents=True)
        write_json(report_dir / "summary.json", {
            "report_date": "2026-07-04",
            "ranked_picks": [{
                "ticker": "XYZ",
                "verdict": "BUY",
                "final_score": 70,
            }],
        })

        rows = module.extract_picks_from_report(str(report_dir / "summary.json"))

    row = rows[0]
    require(row["regime_multiplier"] == "", "missing full.json should keep blanks")
    require(row["tech_score"] == "", "missing full.json should keep score blank")
    require(row["pattern_type"] == "", "missing full.json should keep pattern blank")
    require(row["layer2_path"] == "", "missing full.json should keep layer2 blank")
    require(row["dd_verdict"] == "BUY", "summary verdict fallback should be preserved")


def test_extract_picks_falls_back_to_layer2_scores_when_layer1_scores_are_empty() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as d:
        report_dir = Path(d) / "reports" / "2026-07-05"
        report_dir.mkdir(parents=True)
        write_json(report_dir / "summary.json", {
            "report_date": "2026-07-05",
            "ranked_picks": [{"ticker": "FALL", "verdict": "BUY", "final_score": 81}],
        })
        write_json(report_dir / "full.json", {
            "scored_data": {
                "all_scored": [{
                    "ticker": "FALL",
                    "scores": {},
                    "technical_breakdown": {},
                }],
            },
            "layer2_data": {
                "all_results": [{
                    "ticker": "FALL",
                    "scores": {"technical": 19, "options_flow": 11},
                    "technical_breakdown": {
                        "pattern_type": "pullback",
                        "macd_state": "reset",
                    },
                }],
            },
            "dd_data": {},
        })

        rows = module.extract_picks_from_report(str(report_dir / "summary.json"))

    row = rows[0]
    require(row["tech_score"] == 19,
            "empty Layer 1 scores should fall back to Layer 2 scores")
    require(row["options_score"] == 11,
            "Layer 2 options score should be used when Layer 1 scores are empty")
    require(row["pattern_type"] == "pullback",
            "empty Layer 1 technical breakdown should fall back to Layer 2")
    require(row["macd_state"] == "reset",
            "Layer 2 MACD state should be used when Layer 1 breakdown is empty")


def _pick(scan_date: str, ticker: str) -> dict:
    return {column: "" for column in load_module().LEDGER_COLUMNS} | {
        "scan_date": scan_date,
        "ticker": ticker,
        "verdict": "BUY",
        "composite_score": 80,
    }


def _append_worker(ledger_path: str, scan_date: str, ticker: str) -> None:
    module = load_module()
    module.append_to_ledger(ledger_path, [_pick(scan_date, ticker)])


def test_parallel_writers_retain_distinct_rows_and_deduplicate_keys() -> None:
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "performance_ledger.csv"
        processes = [
            multiprocessing.Process(
                target=_append_worker,
                args=(str(ledger), "2026-08-17", ticker),
            )
            for ticker in ("AAA", "BBB", "AAA")
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            require(process.exitcode == 0, f"writer failed: {process.exitcode}")

        with ledger.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

    require(
        {(row["scan_date"], row["ticker"]) for row in rows}
        == {("2026-08-17", "AAA"), ("2026-08-17", "BBB")},
        f"parallel append lost or duplicated rows: {rows}",
    )


def test_no_picks_leaves_existing_ledger_bytes_unchanged() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "performance_ledger.csv"
        module.append_to_ledger(str(ledger), [_pick("2026-08-16", "OLD")])
        before = ledger.read_bytes()
        result = module.append_to_ledger(str(ledger), [])
        after = ledger.read_bytes()

    require(before == after, "zero-pick append must not rewrite the ledger")
    require(result["outcome"] == "successful_zero_pick", str(result))


def test_atomic_replace_failure_preserves_exact_ledger_bytes() -> None:
    module = load_module()
    store = module._ledger_store
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "performance_ledger.csv"
        module.append_to_ledger(str(ledger), [_pick("2026-08-16", "OLD")])
        before = ledger.read_bytes()
        real_replace = store.os.replace

        def fail_replace(source, target):  # noqa: ARG001
            raise OSError("injected replace failure")

        store.os.replace = fail_replace
        try:
            try:
                module.append_to_ledger(str(ledger), [_pick("2026-08-17", "NEW")])
            except OSError as exc:
                require("injected" in str(exc), str(exc))
            else:
                raise AssertionError("replace failure should propagate")
        finally:
            store.os.replace = real_replace

        require(ledger.read_bytes() == before, "replace failure changed prior bytes")
        leftovers = [path for path in ledger.parent.iterdir() if ".tmp-" in path.name]
        require(not leftovers, f"temporary files leaked: {leftovers}")


def test_legacy_header_migration_preserves_each_existing_row_once() -> None:
    module = load_module()
    legacy_columns = [column for column in module.LEDGER_COLUMNS if column != "analyst_score"]
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "performance_ledger.csv"
        with ledger.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=legacy_columns)
            writer.writeheader()
            writer.writerow({
                column: (
                    "2026-05-05" if column == "scan_date"
                    else "MU" if column == "ticker"
                    else ""
                )
                for column in legacy_columns
            })

        result = module.append_to_ledger(
            str(ledger),
            [_pick("2026-08-17", "NEW")],
        )
        with ledger.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            header = reader.fieldnames

    require(result["outcome"] == "migrated", str(result))
    require(header == module.LEDGER_COLUMNS, f"migration header mismatch: {header}")
    require(
        [(row["scan_date"], row["ticker"]) for row in rows]
        == [("2026-05-05", "MU"), ("2026-08-17", "NEW")],
        f"migration duplicated or lost rows: {rows}",
    )


def main() -> None:
    tests = [
        test_extract_picks_enriches_confirmed_pick_from_full_report,
        test_extract_picks_keeps_legacy_blank_fields_without_full_report,
        test_extract_picks_falls_back_to_layer2_scores_when_layer1_scores_are_empty,
        test_parallel_writers_retain_distinct_rows_and_deduplicate_keys,
        test_no_picks_leaves_existing_ledger_bytes_unchanged,
        test_atomic_replace_failure_preserves_exact_ledger_bytes,
        test_legacy_header_migration_preserves_each_existing_row_once,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
