#!/usr/bin/env python3
"""Tests for the local pipeline run-status JSON writer."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_run_status():
    spec = importlib.util.spec_from_file_location(
        "run_status_under_test", ROOT / "scripts" / "run_status.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_status_writer_records_running_stage() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "status.json"
        writer = mod.RunStatus(path, job="candidates-local")
        writer.start(metrics={"total_tickers": 1503})
        writer.update_stage(
            "hard_filter.fetch_ohlcv",
            "抓取 yfinance OHLCV",
            progress_pct=42.6,
            message="Downloading batch 26/61",
            metrics={
                "completed_batches": 26,
                "total_batches": 61,
                "downloaded_tickers": 632,
            },
            outputs={
                "filtered_universe": {"path": "filtered_universe.json", "exists": False}
            },
        )

        data = json.loads(path.read_text(encoding="utf-8"))
        if data["job"] != "candidates-local":
            raise AssertionError(data)
        if data["status"] != "running":
            raise AssertionError(data)
        if data["stage"]["id"] != "hard_filter.fetch_ohlcv":
            raise AssertionError(data)
        if data["stage"]["progress_pct"] != 42.6:
            raise AssertionError(data)
        if data["metrics"]["total_tickers"] != 1503:
            raise AssertionError(data)
        if data["metrics"]["completed_batches"] != 26:
            raise AssertionError(data)
        if data["outputs"]["filtered_universe"]["exists"] is not False:
            raise AssertionError(data)
        if data["errors"] != []:
            raise AssertionError(data)


def test_status_writer_records_failure() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "status.json"
        writer = mod.RunStatus(path, job="candidates-local")
        writer.start(metrics={"total_tickers": 1503})
        writer.fail(
            "hard_filter.fetch_ohlcv",
            "抓取 yfinance OHLCV",
            "Coverage below floor",
            metrics={"data_available": 201, "current_coverage": 0.1337},
        )

        data = json.loads(path.read_text(encoding="utf-8"))
        if data["status"] != "failed":
            raise AssertionError(data)
        if "finished_at" not in data:
            raise AssertionError(data)
        if data["stage"]["status"] != "failed":
            raise AssertionError(data)
        if data["errors"][0]["message"] != "Coverage below floor":
            raise AssertionError(data)


def test_start_resets_previous_terminal_status() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "status.json"
        first = mod.RunStatus(path, job="candidates-local")
        first.start(metrics={"total_tickers": 1})
        first.succeed(message="old run")
        old = json.loads(path.read_text(encoding="utf-8"))

        second = mod.RunStatus(path, job="candidates-local")
        second.start(metrics={"total_tickers": 2})
        data = json.loads(path.read_text(encoding="utf-8"))

        if data["status"] != "running":
            raise AssertionError(data)
        if data["run_id"] == old["run_id"]:
            raise AssertionError(data)
        if "finished_at" in data:
            raise AssertionError(data)
        if data["metrics"]["total_tickers"] != 2:
            raise AssertionError(data)


def test_default_stages_include_deterministic_rank_and_options_gate() -> None:
    mod = _load_run_status()
    stage_ids = [stage_id for stage_id, _label in mod.DEFAULT_STAGES]
    for expected in ("rank_candidates", "options_gate"):
        if expected not in stage_ids:
            raise AssertionError(stage_ids)


def test_status_writer_accepts_custom_stages() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "data-health-refresh.json"
        writer = mod.RunStatus(
            path,
            job="data-health-refresh",
            stages=[("source_refresh", "刷新核心資料源"), ("done", "完成")],
        )
        writer.start(metrics={"estimated_tickers": 250})
        data = json.loads(path.read_text(encoding="utf-8"))
        stages = [(item["id"], item["label"]) for item in data["stages"]]

        if data["job"] != "data-health-refresh":
            raise AssertionError(data)
        if stages != [("source_refresh", "刷新核心資料源"), ("done", "完成")]:
            raise AssertionError(stages)
        if any(item["id"] == "hard_filter.fetch_ohlcv" for item in data["stages"]):
            raise AssertionError(data["stages"])


def test_terminal_status_appends_run_history() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "candidates-local.json"
        writer = mod.RunStatus(path, job="candidates-local")
        writer.start(metrics={"rank_limit": 50})
        writer.succeed(
            message="ranked top 50",
            metrics={"ranked_candidates": 50},
            outputs={"ranked_candidates": {"path": "ranked_candidates.json", "exists": True}},
        )

        history_path = Path(d) / "candidates-local-history.jsonl"
        if not history_path.exists():
            raise AssertionError("history file not written")
        records = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(records) != 1:
            raise AssertionError(records)
        rec = records[0]
        if rec["status"] != "succeeded" or rec["metrics"]["ranked_candidates"] != 50:
            raise AssertionError(rec)
        if not rec.get("updated_at"):
            raise AssertionError(rec)
        if rec["outputs"]["ranked_candidates"]["exists"] is not True:
            raise AssertionError(rec)


def test_terminal_status_replaces_latest_history_for_same_run_id() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "candidates-local.json"
        writer = mod.RunStatus(path, job="candidates-local")
        writer.start(metrics={"rank_limit": 50})
        writer.succeed(message="child step complete", metrics={"ranked_candidates": 50})
        writer.update_stage(
            "analytics_refresh",
            "更新資料與 Analytics",
            progress_pct=92,
            message="refreshing analytics",
        )
        writer.succeed(message="候選流程與 Analytics 更新完成", metrics={"analytics_checks_status": "WARN"})

        history_path = Path(d) / "candidates-local-history.jsonl"
        records = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    if len(records) != 1:
        raise AssertionError(records)
    if records[0]["stage"]["message"] != "候選流程與 Analytics 更新完成":
        raise AssertionError(records)
    if records[0]["metrics"].get("analytics_checks_status") != "WARN":
        raise AssertionError(records)


def test_start_archives_interrupted_running_status_before_reset() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "candidates-local.json"
        first = mod.RunStatus(path, job="candidates-local")
        first.start(metrics={"total_tickers": 1503})
        first.update_stage(
            "hard_filter.info",
            "補 market cap / earnings",
            progress_pct=21.3,
            message="Fetching info 320/1503",
            metrics={"info_tickers": 320},
        )
        old = json.loads(path.read_text(encoding="utf-8"))

        second = mod.RunStatus(path, job="candidates-local")
        second.start(metrics={"total_tickers": 1503})
        latest = json.loads(path.read_text(encoding="utf-8"))
        history_path = Path(d) / "candidates-local-history.jsonl"
        records = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        if len(records) != 1:
            raise AssertionError(records)
        rec = records[0]
        if rec["run_id"] != old["run_id"]:
            raise AssertionError(rec)
        if rec["status"] != "failed":
            raise AssertionError(rec)
        if rec["stage"]["id"] != "hard_filter.info":
            raise AssertionError(rec)
        if rec["stage"]["status"] != "failed":
            raise AssertionError(rec)
        if not rec.get("finished_at") or not rec.get("updated_at"):
            raise AssertionError(rec)
        if not rec["errors"] or rec["errors"][-1]["stage"] != "hard_filter.info":
            raise AssertionError(rec)
        if latest["status"] != "running" or latest["run_id"] == old["run_id"]:
            raise AssertionError(latest)


def test_status_writer_uses_process_specific_tmp_path() -> None:
    mod = _load_run_status()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "candidates-local.json"
        writer = mod.RunStatus(path, job="candidates-local")
        tmp_path = writer._tmp_path()
        if tmp_path == path.with_suffix(".json.tmp"):
            raise AssertionError(tmp_path)
        if str(os.getpid()) not in tmp_path.name:
            raise AssertionError(tmp_path)


def main() -> None:
    tests = [
        test_status_writer_records_running_stage,
        test_status_writer_records_failure,
        test_start_resets_previous_terminal_status,
        test_default_stages_include_deterministic_rank_and_options_gate,
        test_status_writer_accepts_custom_stages,
        test_terminal_status_appends_run_history,
        test_terminal_status_replaces_latest_history_for_same_run_id,
        test_start_archives_interrupted_running_status_before_reset,
        test_status_writer_uses_process_specific_tmp_path,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
