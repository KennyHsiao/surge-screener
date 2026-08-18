#!/usr/bin/env python3
"""Regression tests for producer-terminal report ingestion."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "post_producer_analytics_under_test",
    ROOT / "scripts" / "post_producer_analytics.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _artifact_payloads() -> dict[str, dict]:
    report_date = "2026-08-17"
    return {
        f"reports/{report_date}/summary.json": {
            "report_date": report_date,
            "total_confirmed": 0,
            "ranked_picks": [],
        },
        f"reports/candidate_scores/{report_date}.json": {
            "scan_date": report_date,
            "cohort_type": "bounded_top_n",
            "ranked_universe_count": 864,
            "scored_cohort_count": 25,
            "selection_method": "deterministic_top_n",
            "rank_limit": 25,
            "remaining_unscored": 0,
            "all_scored": [{"ticker": f"T{i}"} for i in range(25)],
        },
        f"reports/market_thesis/regime_only_forecast_{report_date}.json": {
            "as_of": report_date,
            "generated_at": "2026-08-17T23:26:40Z",
            "tier": "tier_1",
            "method": "deterministic",
        },
    }


class FakeClient:
    def __init__(self, payloads: dict[str, dict], *, fixed_sha: str) -> None:
        self.payloads = payloads
        self.fixed_sha = fixed_sha
        self.refs: list[str] = []

    def get(self, path: str, params: dict[str, str] | None = None):
        if path == "commits/main":
            return {"sha": self.fixed_sha}
        prefix = "contents/"
        if path.startswith(prefix):
            assert params and "ref" in params
            self.refs.append(params["ref"])
            payload = self.payloads[path[len(prefix):]]
            raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
            return {
                "encoding": "base64",
                "content": base64.encodebytes(raw).decode(),
                "sha": "git-blob-sha",
            }
        raise AssertionError((path, params))


def _producers() -> dict[str, dict]:
    return {
        "eod": {"run_id": 10, "job_id": 11, "conclusion": "success"},
        "market_thesis": {"run_id": 12, "job_id": 13, "conclusion": "success"},
        "theme_flow": {"unit": "surge-theme-flow-refresh.service", "result": "success"},
    }


def test_required_artifacts_are_allowlisted_and_market_thesis_is_calendar_driven() -> None:
    monday = MOD.required_artifacts(date(2026, 8, 17))
    tuesday = MOD.required_artifacts(date(2026, 8, 18))
    assert [item.relative_path for item in monday] == [
        "reports/2026-08-17/summary.json",
        "reports/candidate_scores/2026-08-17.json",
        "reports/market_thesis/regime_only_forecast_2026-08-17.json",
    ]
    assert [item.relative_path for item in tuesday] == [
        "reports/2026-08-18/summary.json",
        "reports/candidate_scores/2026-08-18.json",
    ]


def test_sync_pins_every_download_to_one_main_sha_and_records_hashes() -> None:
    fixed_sha = "a" * 40
    client = FakeClient(_artifact_payloads(), fixed_sha=fixed_sha)
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        manifest = MOD.synchronize_published_reports(
            client=client,
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )
        current = (store / "current").resolve()
        assert current.is_dir()
        assert manifest["source_sha"] == fixed_sha
        assert client.refs == [fixed_sha, fixed_sha, fixed_sha]
        for item in manifest["artifacts"]:
            path = current / item["relative_path"]
            assert path.is_file()
            assert item["sha256"] == MOD.sha256_file(path)
            assert item["size"] == path.stat().st_size
        assert json.loads((current / "manifest.json").read_text())["source_sha"] == fixed_sha


def test_unpublished_artifact_fails_closed_and_does_not_replace_current() -> None:
    payloads = _artifact_payloads()
    payloads.pop("reports/candidate_scores/2026-08-17.json")
    client = FakeClient(payloads, fixed_sha="b" * 40)
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        existing = store / "generations/known-good"
        existing.mkdir(parents=True)
        (existing / "manifest.json").write_text('{"state":"known-good"}\n')
        (store / "current").symlink_to(Path("generations/known-good"))
        before = (store / "current").resolve()

        try:
            MOD.synchronize_published_reports(
                client=client,
                store_root=store,
                report_date=date(2026, 8, 17),
                producer_evidence=_producers(),
            )
        except MOD.UnpublishedArtifactError:
            pass
        else:
            raise AssertionError("missing required artifact must fail closed")
        assert (store / "current").resolve() == before
        assert json.loads((before / "manifest.json").read_text())["state"] == "known-good"


def test_producer_states_distinguish_missing_failed_unpublished_and_zero_pick_success() -> None:
    assert MOD.classify_producer_state(run=None, job=None, artifact_present=False) == "missing"
    assert MOD.classify_producer_state(
        run={"status": "completed", "conclusion": "failure"},
        job={"status": "completed", "conclusion": "failure"},
        artifact_present=False,
    ) == "failed"
    assert MOD.classify_producer_state(
        run={"status": "completed", "conclusion": "success"},
        job={"status": "completed", "conclusion": "success"},
        artifact_present=False,
    ) == "unpublished"
    assert MOD.classify_producer_state(
        run={"status": "completed", "conclusion": "success"},
        job={"status": "completed", "conclusion": "success"},
        artifact_present=True,
    ) == "succeeded"
    assert MOD.validate_daily_summary(
        {"report_date": "2026-08-17", "total_confirmed": 0, "ranked_picks": []},
        date(2026, 8, 17),
    )["outcome"] == "successful_zero_pick"


def test_post_ingestion_verdict_embeds_exact_sources_checks_and_database_identity() -> None:
    manifest = {
        "source_sha": "c" * 40,
        "artifacts": [{"relative_path": "reports/2026-08-17/summary.json", "sha256": "d" * 64}],
        "producers": _producers(),
    }
    refresh = {
        "checks": {
            "status": "WARN",
            "summary": {"pass": 72, "warn": 2, "block": 0},
            "checks": [
                {"id": "table:candidate_scores:row_count", "value": 25},
                {"id": "table:daily_reports:latest_date", "value": "2026-08-17"},
            ],
        },
        "database": {"path": "/shared/data/analytics.duckdb", "sha256": "e" * 64, "size": 123},
    }
    verdict = MOD.build_post_ingestion_verdict(
        state="PASS", report_date=date(2026, 8, 17), manifest=manifest, refresh=refresh,
    )
    assert verdict["state"] == "PASS"
    assert verdict["source_sha"] == "c" * 40
    assert verdict["producers"]["eod"]["run_id"] == 10
    assert verdict["artifacts"][0]["sha256"] == "d" * 64
    assert verdict["database"]["sha256"] == "e" * 64
    assert verdict["analytics_checks"] == [
        {"id": "table:candidate_scores:row_count", "value": 25},
        {"id": "table:daily_reports:latest_date", "value": "2026-08-17"},
    ]


def test_producer_gate_waits_for_late_terminal_and_fails_on_real_failure() -> None:
    window = MOD.validation_window(date(2026, 8, 18))
    success_run = {"id": 1, "status": "completed", "conclusion": "success"}
    success_job = {"id": 2, "name": "market_thesis", "status": "completed", "conclusion": "success"}
    producers = {
        "eod": {
            "run": {"id": 3, "status": "in_progress", "conclusion": None},
            "job": {"id": 4, "name": "surge_scan", "status": "in_progress", "conclusion": None},
        },
        "market_thesis": {"run": success_run, "job": success_job},
        "theme_flow": {"gate": {"state": "PASS", "reasons": [], "evidence": {}}},
    }
    assert MOD.evaluate_producer_readiness(window, producers)["state"] == "PENDING"
    producers["eod"] = {
        "run": {"id": 3, "status": "completed", "conclusion": "success"},
        "job": {"id": 4, "name": "surge_scan", "status": "completed", "conclusion": "success"},
    }
    assert MOD.evaluate_producer_readiness(window, producers)["state"] == "PASS"
    producers["eod"]["job"]["conclusion"] = "failure"
    assert MOD.evaluate_producer_readiness(window, producers)["state"] == "FAIL"


def test_ingestion_does_not_depend_on_github_token_push_triggering_deploy() -> None:
    service = (ROOT / "deploy/surge-post-producer-analytics.service").read_text()
    implementation = (ROOT / "scripts/post_producer_analytics.py").read_text()
    assert "scripts/post_producer_analytics.py" in service
    assert "contents/" in implementation and 'client.get("commits/main")' in implementation
    assert "workflow dispatch" not in implementation.lower()
    assert "deploy_test_server" not in implementation


def test_strict_post_ingestion_gate_requires_latest_risk_and_classified_zero_pick() -> None:
    checks = {
        "summary": {"pass": 72, "warn": 2, "block": 0},
        "checks": [
            {"id": "table:candidate_scores:row_count", "status": "PASS", "value": 25},
            {"id": "table:candidate_scores:latest_date", "status": "PASS", "value": "2026-08-17"},
            {"id": "table:daily_reports:latest_date", "status": "PASS", "value": "2026-08-17"},
            {"id": "table:market_thesis_forecasts:latest_date", "status": "PASS", "value": "2026-08-17"},
            {
                "id": "table:portfolio_positions:row_count",
                "status": "PASS",
                "availability": "not_configured",
                "value": 0,
            },
            {"id": "table:risk_guard_rows:latest_date", "status": "PASS", "value": "2026-08-18"},
            {
                "id": "performance:no_confirmed_picks_streak",
                "latest_report_date": "2026-08-17",
                "scan_state_counts": {"successful_zero_pick": 15, "published_unclassified": 0},
            },
        ],
    }
    MOD.validate_post_ingestion_checks(
        checks, {}, report_date=date(2026, 8, 17), candidate_count=25,
        daily_outcome="successful_zero_pick",
    )
    checks["checks"][5]["value"] = "2026-08-16"
    try:
        MOD.validate_post_ingestion_checks(
            checks, {}, report_date=date(2026, 8, 17), candidate_count=25,
            daily_outcome="successful_zero_pick",
        )
    except MOD.analytics_refresh_transaction.AnalyticsGateError as exc:
        assert "Risk Guard" in str(exc)
    else:
        raise AssertionError("stale Risk Guard must block promotion")


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"post-producer analytics tests: {len(tests)} passed")
