#!/usr/bin/env python3
"""Regression tests for producer-terminal report ingestion."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import sys
import tempfile
import time
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "post_producer_analytics_under_test",
    ROOT / "scripts" / "post_producer_analytics.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _valid_score_row(ticker: str) -> dict:
    limits = {
        "technical": 30,
        "catalyst": 16,
        "sentiment": 13,
        "institutional": 10,
        "sector_market": 3,
        "options_flow": 20,
        "analyst": 8,
    }
    zero_scores = {name: 0 for name in limits}
    row = {
        "ticker": ticker,
        "verdict": "REJECT",
        "llm_verdict": "REJECT",
        "llm_composite_score": 0,
        "llm_risk_vetoes": [],
        "llm_scores": dict(zero_scores),
        "evidence_capabilities": {
            "schema_version": "evidence_capabilities_v1",
            "mode": "enforced",
            "authoritative_for_scoring": True,
            "dimensions": {
                name: {
                    "limit": limit,
                    "max_supported_score": limit,
                    "sources": ["test_fixture:available"],
                    "missing_reasons": [],
                }
                for name, limit in limits.items()
            },
        },
        "composite_score": 0,
        "uncapped_composite_score": 0,
        "regime_adjusted_score": 0,
        "scores": dict(zero_scores),
        "data_missing": [],
        "scoring_mode": "full",
        "technical_breakdown": {
            "trend_template": 0,
            "volume": 0,
            "pattern": 0,
            "macd_confirmation": 0,
            "raw_total": 0,
            "applied_cap": None,
        },
        "technical_score_method": "technical_evidence_v1_rubric_v1",
        "score_adjustments": [],
        "due_diligence_required": False,
    }
    row["promotion_reachability"] = MOD.promotion_reachability.build_candidate_diagnostic(
        row,
        row["evidence_capabilities"],
        1.0,
    )
    return row


def _artifact_payloads() -> dict[str, dict]:
    report_date = "2026-08-17"
    cohort = [_valid_score_row(f"T{i}") for i in range(25)]
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
            "regime_context": {"global_score_multiplier": 1.0},
            "promotion_reachability_v1": MOD.promotion_reachability.summarize_run(
                cohort,
                multiplier=1.0,
                total_candidates=25,
            ),
            "all_scored": cohort,
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


def test_job_discovery_refreshes_an_initially_empty_job_cache() -> None:
    class JobsClient:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, path: str, params: dict[str, str] | None = None):
            assert path == "actions/runs/42/jobs"
            assert params == {"per_page": "100"}
            self.calls += 1
            if self.calls == 1:
                return {"jobs": []}
            return {"jobs": [{
                "name": "surge_scan",
                "status": "completed",
                "conclusion": "success",
            }]}

    client = JobsClient()
    run = {
        "id": 42,
        "created_at": "2026-08-24T22:31:00Z",
        "status": "in_progress",
    }
    cache: dict[int, list[dict]] = {}
    bounds = {
        "job_name": "surge_scan",
        "lower": datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
        "upper": datetime(2026, 8, 25, 2, 30, tzinfo=timezone.utc),
    }
    first = MOD._discover_job(
        client=client,
        runs=[run],
        job_cache=cache,
        refreshed_run_ids=set(),
        **bounds,
    )
    second = MOD._discover_job(
        client=client,
        runs=[run],
        job_cache=cache,
        refreshed_run_ids=set(),
        **bounds,
    )
    assert first == (None, None)
    assert second[0] == run
    assert second[1]["conclusion"] == "success"
    assert client.calls == 2


def test_validation_window_preserves_sla_and_adds_bounded_late_recovery() -> None:
    window = MOD.validation_window(date(2026, 8, 27))
    assert window.report_date == date(2026, 8, 26)
    assert window.deadline.isoformat() == "2026-08-27T10:30:00+08:00"
    assert window.recovery_deadline.isoformat() == "2026-08-27T16:30:00+08:00"


def test_late_eod_run_is_discovered_inside_the_recovery_window() -> None:
    class LateRunClient:
        def get(self, path: str, params: dict[str, str] | None = None):
            if path == "actions/workflows/surge_screener.yml/runs":
                assert params == {"event": "schedule", "per_page": "30"}
                return {"workflow_runs": [{
                    "id": 33036289036,
                    "created_at": "2026-08-27T03:24:00Z",
                    "status": "completed",
                    "conclusion": "success",
                }]}
            if path == "actions/runs/33036289036/jobs":
                assert params == {"per_page": "100"}
                return {"jobs": [{
                    "id": 9901,
                    "name": "surge_scan",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2026-08-27T03:24:00Z",
                    "completed_at": "2026-08-27T03:44:00Z",
                }]}
            raise AssertionError((path, params))

    original_theme = MOD.evaluate_theme
    MOD.evaluate_theme = lambda *_args, **_kwargs: {
        "state": "PASS", "reasons": [], "evidence": {},
    }
    try:
        with tempfile.TemporaryDirectory() as tmp:
            producers = MOD.capture_producer_states(
                client=LateRunClient(),
                window=MOD.validation_window(date(2026, 8, 27)),
                app_root=Path(tmp),
                job_cache={},
            )
    finally:
        MOD.evaluate_theme = original_theme

    assert producers["eod"]["run"]["id"] == 33036289036
    assert producers["eod"]["job"]["conclusion"] == "success"


def test_observation_timing_distinguishes_late_recovery_from_on_time_pass() -> None:
    window = MOD.validation_window(date(2026, 8, 27))
    before_sla = datetime(2026, 8, 27, 2, 29, tzinfo=timezone.utc)
    after_sla = datetime(2026, 8, 27, 3, 24, tzinfo=timezone.utc)
    after_recovery = datetime(2026, 8, 27, 8, 31, tzinfo=timezone.utc)

    on_time = MOD.observation_timing(window, now=before_sla, producer_state="PASS")
    waiting = MOD.observation_timing(window, now=after_sla, producer_state="PENDING")
    recovered = MOD.observation_timing(window, now=after_sla, producer_state="PASS")
    exhausted = MOD.observation_timing(window, now=after_recovery, producer_state="PENDING")

    assert on_time["action"] == "PROCEED"
    assert on_time["evidence"]["state"] == "ON_TIME"
    assert waiting["action"] == "WAIT"
    assert waiting["evidence"]["state"] == "WAITING_LATE"
    assert waiting["evidence"]["deadline_missed_at"] == "2026-08-27T02:30:00Z"
    assert recovered["action"] == "PROCEED"
    assert recovered["evidence"]["state"] == "RECOVERED_LATE"
    assert recovered["evidence"]["deadline_missed_at"] == "2026-08-27T02:30:00Z"
    assert exhausted["action"] == "FAIL"
    assert exhausted["evidence"]["state"] == "FAILED"


def _expect_candidate_contract_failure(payload: dict, expected: str) -> None:
    try:
        MOD.validate_candidate_scores(payload, date(2026, 8, 17))
    except MOD.ArtifactContractError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError(f"candidate contract must reject {expected}")


def test_candidate_contract_requires_authoritative_evidence_for_every_row() -> None:
    payload = copy.deepcopy(
        _artifact_payloads()["reports/candidate_scores/2026-08-17.json"]
    )
    payload["all_scored"][7]["evidence_capabilities"]["mode"] = "shadow"
    payload["all_scored"][7]["evidence_capabilities"][
        "authoritative_for_scoring"
    ] = False
    _expect_candidate_contract_failure(payload, "full-score contract")


def test_candidate_contract_rejects_tampered_deterministic_score() -> None:
    payload = copy.deepcopy(
        _artifact_payloads()["reports/candidate_scores/2026-08-17.json"]
    )
    payload["all_scored"][3]["composite_score"] = 1
    _expect_candidate_contract_failure(payload, "full-score contract")


def test_candidate_contract_requires_exact_zero_unsupported_credit() -> None:
    payload = copy.deepcopy(
        _artifact_payloads()["reports/candidate_scores/2026-08-17.json"]
    )
    payload["promotion_reachability_v1"].update({
        "unsupported_credit_count": 1,
        "unsupported_credit_tickers": ["T4"],
    })
    _expect_candidate_contract_failure(payload, "unsupported credit")

    payload["promotion_reachability_v1"]["unsupported_credit_count"] = 0
    _expect_candidate_contract_failure(payload, "unsupported credit")


def test_candidate_contract_recomputes_complete_promotion_reachability() -> None:
    payload = copy.deepcopy(
        _artifact_payloads()["reports/candidate_scores/2026-08-17.json"]
    )
    payload["promotion_reachability_v1"]["mode"] = "advisory"
    _expect_candidate_contract_failure(payload, "reachability contract")

    payload = copy.deepcopy(
        _artifact_payloads()["reports/candidate_scores/2026-08-17.json"]
    )
    payload["all_scored"][9]["promotion_reachability"]["adjusted_ceiling"] = 99
    _expect_candidate_contract_failure(payload, "reachability contract")


def test_prepare_and_promote_pin_every_download_to_one_main_sha_and_record_hashes() -> None:
    fixed_sha = "a" * 40
    client = FakeClient(_artifact_payloads(), fixed_sha=fixed_sha)
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        prepared = MOD.prepare_published_reports(
            client=client,
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )
        manifest = prepared.manifest
        assert not (store / "current").exists()
        MOD.promote_prepared_generation(prepared)
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


def test_prepare_generation_does_not_switch_current() -> None:
    fixed_sha = "f" * 40
    client = FakeClient(_artifact_payloads(), fixed_sha=fixed_sha)
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        existing = store / "generations/known-good"
        existing.mkdir(parents=True)
        (existing / "manifest.json").write_text('{"state":"known-good"}\n')
        (store / "current").symlink_to(Path("generations/known-good"))

        prepared = MOD.prepare_published_reports(
            client=client,
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )

        assert (store / "current").resolve() == existing.resolve()
        assert prepared.previous_generation == existing.resolve()
        assert prepared.generation.is_dir()
        assert prepared.generation != existing.resolve()
        assert prepared.manifest["source_sha"] == fixed_sha
        assert json.loads((prepared.generation / "manifest.json").read_text())["source_sha"] == fixed_sha


def test_prepared_generation_promotion_returns_exact_pointer_rollback() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        existing = store / "generations/known-good"
        existing.mkdir(parents=True)
        (store / "current").symlink_to(Path("generations/known-good"))
        prepared = MOD.prepare_published_reports(
            client=FakeClient(_artifact_payloads(), fixed_sha="9" * 40),
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )

        rollback = MOD.promote_prepared_generation(prepared)
        assert (store / "current").resolve() == prepared.generation
        rollback()
        assert (store / "current").resolve() == existing.resolve()

    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "published_reports"
        prepared = MOD.prepare_published_reports(
            client=FakeClient(_artifact_payloads(), fixed_sha="8" * 40),
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )

        rollback = MOD.promote_prepared_generation(prepared)
        assert (store / "current").resolve() == prepared.generation
        rollback()
        assert not (store / "current").exists()


def test_generation_pointer_promotion_and_rollback_fsync_the_store() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = (Path(directory) / "published_reports").resolve()
        existing = store / "generations/known-good"
        existing.mkdir(parents=True)
        (store / "current").symlink_to(Path("generations/known-good"))
        prepared = MOD.prepare_published_reports(
            client=FakeClient(_artifact_payloads(), fixed_sha="e" * 40),
            store_root=store,
            report_date=date(2026, 8, 17),
            producer_evidence=_producers(),
        )
        original_fsync = MOD._fsync_directory
        fsynced: list[Path] = []

        def record_fsync(path: Path) -> None:
            fsynced.append(Path(path).resolve())
            original_fsync(path)

        MOD._fsync_directory = record_fsync
        try:
            rollback = MOD.promote_prepared_generation(prepared)
            assert store in fsynced
            fsynced.clear()
            rollback()
            assert store in fsynced
        finally:
            MOD._fsync_directory = original_fsync


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
            MOD.prepare_published_reports(
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
    producers["theme_flow"]["gate"] = {
        "state": "FAIL",
        "reasons": ["injected transient Theme failure"],
        "evidence": {},
    }
    assert MOD.evaluate_producer_readiness(window, producers)["state"] == "PENDING"
    producers["theme_flow"]["gate"] = {
        "state": "PASS", "reasons": [], "evidence": {},
    }
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
            {
                "id": "candidate_scores:promotion_reachability",
                "status": "WARN",
                "code": "PROMOTION_EVIDENCE_UNREACHABLE",
                "latest_scan_date": "2026-08-17",
                "reachability_state": "not_reachable",
                "candidate_rows": 25,
                "contract_rows": 25,
                "scored_cohort_count": 25,
                "diagnostic_schema": "promotion_reachability_v1",
                "diagnostic_mode": "shadow",
                "authoritative_for_promotion": False,
                "unsupported_credit_count": 0,
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

    checks["checks"][5]["value"] = "2026-08-18"
    checks["checks"][-1]["unsupported_credit_count"] = 1
    try:
        MOD.validate_post_ingestion_checks(
            checks, {}, report_date=date(2026, 8, 17), candidate_count=25,
            daily_outcome="successful_zero_pick",
        )
    except MOD.analytics_refresh_transaction.AnalyticsGateError as exc:
        assert "unsupported credit" in str(exc)
    else:
        raise AssertionError("unsupported promotion credit must block promotion")

    checks["checks"][-1]["unsupported_credit_count"] = 0
    checks["checks"][-1]["contract_rows"] = 24
    try:
        MOD.validate_post_ingestion_checks(
            checks, {}, report_date=date(2026, 8, 17), candidate_count=25,
            daily_outcome="successful_zero_pick",
        )
    except MOD.analytics_refresh_transaction.AnalyticsGateError as exc:
        assert "reachability contract" in str(exc)
    else:
        raise AssertionError("partial Analytics reachability contract must block promotion")


CANONICAL_TERMINAL_KEYS = {
    "schema_version",
    "captured_at",
    "state",
    "reasons",
    "report_date",
    "source_sha",
    "producers",
    "artifacts",
    "analytics_summary",
    "analytics_status",
    "analytics_checks",
    "database",
    "promoted_at",
    "timeliness",
}


def _observer_args(root: Path) -> Namespace:
    return Namespace(
        window_date="2026-08-18",
        app_root=str(root),
        repository="KennyHsiao/surge-screener",
        published_store=str(root / "shared/published_reports"),
        status_file=str(root / "shared/run_status/post-producer-analytics.json"),
        verdict_file=str(root / "shared/post_ingestion/latest.json"),
        poll_seconds=30,
        artifact_retry_seconds=30,
        lock_timeout_seconds=1,
    )


def test_deadline_budget_caps_lock_wait_and_rejects_late_persistence() -> None:
    now = datetime(2026, 8, 25, 2, 29, 30, tzinfo=timezone.utc)
    deadline = now + timedelta(seconds=30)
    assert MOD.remaining_window_seconds(deadline, now=now) == 30
    assert MOD.bounded_lock_timeout(deadline, 3600, now=now) == 30
    try:
        MOD.bounded_lock_timeout(deadline, 3600, now=deadline)
    except MOD.ValidationDeadlineExceeded as exc:
        assert "lock acquisition" in str(exc)
    else:
        raise AssertionError("deadline-expired lock acquisition must fail closed")
    try:
        MOD.require_before_deadline(
            datetime.now(timezone.utc) - timedelta(seconds=1),
            stage="PASS verdict persistence",
        )
    except MOD.ValidationDeadlineExceeded as exc:
        assert "PASS verdict persistence" in str(exc)
    else:
        raise AssertionError("late PASS persistence must fail closed")


def test_terminal_pass_retains_late_recovery_evidence() -> None:
    window = MOD.validation_window(date(2026, 8, 27))
    timing = MOD.observation_timing(
        window,
        now=datetime(2026, 8, 27, 4, 34, tzinfo=timezone.utc),
        producer_state="PASS",
    )["evidence"]
    verdict = MOD.build_post_ingestion_verdict(
        state="PASS",
        report_date=window.report_date,
        manifest={},
        refresh={},
        timeliness=timing,
    )
    assert verdict["state"] == "PASS"
    assert verdict["timeliness"] == timing
    assert verdict["timeliness"]["state"] == "RECOVERED_LATE"


def _run_terminal_scenario(
    *,
    root: Path,
    readiness: dict,
    client,
    deadline: datetime,
    analytics_failure: bool = False,
) -> dict:
    original_client = MOD.GitHubClient
    original_capture = MOD.capture_producer_states
    original_evaluate = MOD.evaluate_producer_readiness
    original_window = MOD.validation_window
    original_refresh = getattr(
        MOD.analytics_refresh_transaction,
        "staged_analytics_refresh_locked",
        None,
    )
    original_transaction = getattr(
        MOD.analytics_refresh_transaction,
        "staged_analytics_refresh_transaction_locked",
        None,
    )
    MOD.GitHubClient = lambda _repository: client
    MOD.capture_producer_states = lambda **_kwargs: {}
    MOD.evaluate_producer_readiness = lambda _window, _producers: readiness
    MOD.validation_window = lambda _date: SimpleNamespace(
        report_date=date(2026, 8, 17),
        deadline=deadline,
        recovery_deadline=deadline,
    )
    if analytics_failure:
        def fail_analytics(**_kwargs):
            raise MOD.analytics_refresh_transaction.AnalyticsGateError("injected Analytics failure")

        MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = fail_analytics
        MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = fail_analytics
    try:
        assert MOD.run_observer(_observer_args(root)) == 1
    finally:
        MOD.GitHubClient = original_client
        MOD.capture_producer_states = original_capture
        MOD.evaluate_producer_readiness = original_evaluate
        MOD.validation_window = original_window
        if original_refresh is None:
            try:
                delattr(MOD.analytics_refresh_transaction, "staged_analytics_refresh_locked")
            except AttributeError:
                pass
        else:
            MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = original_refresh
        if original_transaction is None:
            try:
                delattr(MOD.analytics_refresh_transaction, "staged_analytics_refresh_transaction_locked")
            except AttributeError:
                pass
        else:
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                original_transaction
            )
    return json.loads((root / "shared/post_ingestion/latest.json").read_text())


def test_all_terminal_failures_use_one_verdict_schema() -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    scenarios: list[dict] = []

    with tempfile.TemporaryDirectory() as directory:
        scenarios.append(_run_terminal_scenario(
            root=Path(directory),
            readiness={"state": "FAIL", "reasons": ["eod producer failed"], "evidence": {}},
            client=object(),
            deadline=future,
        ))
    with tempfile.TemporaryDirectory() as directory:
        scenarios.append(_run_terminal_scenario(
            root=Path(directory),
            readiness={"state": "PENDING", "reasons": ["eod producer is running"], "evidence": {}},
            client=object(),
            deadline=past,
        ))
    with tempfile.TemporaryDirectory() as directory:
        payloads = _artifact_payloads()
        payloads.pop("reports/candidate_scores/2026-08-17.json")
        scenarios.append(_run_terminal_scenario(
            root=Path(directory),
            readiness={"state": "PASS", "reasons": [], "evidence": {}},
            client=FakeClient(payloads, fixed_sha="1" * 40),
            deadline=past,
        ))
    with tempfile.TemporaryDirectory() as directory:
        scenarios.append(_run_terminal_scenario(
            root=Path(directory),
            readiness={"state": "PASS", "reasons": [], "evidence": {}},
            client=FakeClient(_artifact_payloads(), fixed_sha="2" * 40),
            deadline=future,
            analytics_failure=True,
        ))

    assert [set(item) for item in scenarios] == [CANONICAL_TERMINAL_KEYS] * 4
    assert all(item["state"] == "FAIL" for item in scenarios)
    assert all(item["reasons"] for item in scenarios)
    assert all(item["analytics_checks"] == [] for item in scenarios)


class _SuccessfulAnalyticsStore:
    @staticmethod
    def refresh_all(*, reports_root, analytics_root):
        target = Path(analytics_root)
        (target / "parquet").mkdir(parents=True)
        (target / "parquet/daily_reports.parquet").write_bytes(b"new-parquet")
        (target / "analytics.duckdb").write_bytes(b"new-db")
        return {"daily_reports": {"rows": 16, "source": str(reports_root)}}


class _StalledAnalyticsStore:
    @staticmethod
    def refresh_all(*, reports_root, analytics_root):  # noqa: ARG004
        time.sleep(30)
        raise AssertionError("stalled Analytics worker was not terminated")


class _SuccessfulAnalyticsChecks:
    @staticmethod
    def run_checks(*, analytics_root, output_path):
        payload = {
            "status": "WARN",
            "summary": {"pass": 72, "warn": 2, "block": 0},
            "checks": [
                {"id": "table:candidate_scores:row_count", "status": "PASS", "value": 25},
                {"id": "table:candidate_scores:latest_date", "status": "PASS", "value": "2026-08-17"},
                {"id": "table:market_thesis_forecasts:latest_date", "status": "PASS", "value": "2026-08-17"},
                {"id": "table:daily_reports:latest_date", "status": "PASS", "value": "2026-08-17"},
                {"id": "table:portfolio_positions:row_count", "status": "PASS", "value": 0},
                {"id": "table:risk_guard_rows:latest_date", "status": "PASS", "value": "2026-08-18"},
                {
                    "id": "performance:no_confirmed_picks_streak",
                    "status": "WARN",
                    "latest_report_date": "2026-08-17",
                    "scan_state_counts": {"successful_zero_pick": 15, "published_unclassified": 0},
                },
                {
                    "id": "candidate_scores:promotion_reachability",
                    "status": "WARN",
                    "code": "PROMOTION_EVIDENCE_UNREACHABLE",
                    "latest_scan_date": "2026-08-17",
                    "reachability_state": "not_reachable",
                    "candidate_rows": 25,
                    "contract_rows": 25,
                    "scored_cohort_count": 25,
                    "diagnostic_schema": "promotion_reachability_v1",
                    "diagnostic_mode": "shadow",
                    "authoritative_for_promotion": False,
                    "unsupported_credit_count": 0,
                },
            ],
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(payload))
        return payload


def _with_fake_analytics(function):
    def wrapped(**kwargs):
        return function(
            **kwargs,
            analytics_store_module=_SuccessfulAnalyticsStore,
            analytics_checks_module=_SuccessfulAnalyticsChecks,
        )

    return wrapped


def _run_successful_observer(root: Path, client) -> tuple[list[float], dict, dict]:
    (root / "current/reports").mkdir(parents=True)
    analytics = root / "shared/data"
    (analytics / "parquet").mkdir(parents=True)
    (analytics / "analytics.duckdb").write_bytes(b"old-db")
    checks = root / "shared/analytics_checks/latest.json"
    checks.parent.mkdir(parents=True)
    checks.write_bytes(b"old-checks")

    original_client = MOD.GitHubClient
    original_capture = MOD.capture_producer_states
    original_evaluate = MOD.evaluate_producer_readiness
    original_window = MOD.validation_window
    original_sleep = MOD.observer_sleep
    original_locked = MOD.analytics_refresh_transaction.staged_analytics_refresh_locked
    original_transaction = (
        MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked
    )
    sleeps: list[float] = []
    MOD.GitHubClient = lambda _repository: client
    MOD.capture_producer_states = lambda **_kwargs: {}
    MOD.evaluate_producer_readiness = lambda _window, _producers: {
        "state": "PASS", "reasons": [], "evidence": {},
    }
    MOD.validation_window = lambda _date: SimpleNamespace(
        report_date=date(2026, 8, 17),
        deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        recovery_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    MOD.observer_sleep = sleeps.append
    MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = (
        _with_fake_analytics(original_locked)
    )
    MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
        _with_fake_analytics(original_transaction)
    )
    try:
        assert MOD.run_observer(_observer_args(root)) == 0
    finally:
        MOD.GitHubClient = original_client
        MOD.capture_producer_states = original_capture
        MOD.evaluate_producer_readiness = original_evaluate
        MOD.validation_window = original_window
        MOD.observer_sleep = original_sleep
        MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = original_locked
        MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
            original_transaction
        )
    verdict = json.loads((root / "shared/post_ingestion/latest.json").read_text())
    status = json.loads(
        (root / "shared/run_status/post-producer-analytics.json").read_text()
    )
    return sleeps, verdict, status


def test_transient_artifact_api_failure_retries_without_terminal_fail() -> None:
    class FlakyClient(FakeClient):
        def __init__(self) -> None:
            super().__init__(_artifact_payloads(), fixed_sha="6" * 40)
            self.commit_attempts = 0

        def get(self, path: str, params: dict[str, str] | None = None):
            if path == "commits/main":
                self.commit_attempts += 1
                if self.commit_attempts == 1:
                    raise MOD.GitHubApiError("injected transient GitHub timeout")
            return super().get(path, params)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        client = FlakyClient()
        sleeps, verdict, status = _run_successful_observer(root, client)
        assert client.commit_attempts == 2
        assert sleeps and sleeps[0] == 30
        assert verdict["state"] == "PASS"
        assert status["status"] == "succeeded"


def test_artifact_retry_pins_the_first_resolved_main_sha() -> None:
    class AdvancingClient(FakeClient):
        def __init__(self) -> None:
            super().__init__(_artifact_payloads(), fixed_sha="a" * 40)
            self.main_calls = 0
            self.failed_content = False

        def get(self, path: str, params: dict[str, str] | None = None):
            if path == "commits/main":
                self.main_calls += 1
                return {"sha": ("a" if self.main_calls == 1 else "b") * 40}
            if (
                path == "contents/reports/candidate_scores/2026-08-17.json"
                and not self.failed_content
            ):
                self.failed_content = True
                raise MOD.GitHubApiError("injected mid-download timeout")
            return super().get(path, params)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        client = AdvancingClient()
        sleeps, verdict, status = _run_successful_observer(root, client)
        assert client.main_calls == 1
        assert client.refs and set(client.refs) == {"a" * 40}
        assert sleeps and sleeps[0] == 30
        assert verdict["source_sha"] == "a" * 40
        assert verdict["state"] == "PASS"
        assert status["status"] == "succeeded"


def test_successful_observer_commits_exact_promotion_before_recovery() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        _sleeps, verdict, status = _run_successful_observer(
            root,
            FakeClient(_artifact_payloads(), fixed_sha="f" * 40),
        )
        analytics = root / "shared/data"
        store = root / "shared/published_reports"
        checks = root / "shared/analytics_checks/latest.json"
        durable_state = {
            "current": (store / "current").resolve(),
            "database": (analytics / "analytics.duckdb").read_bytes(),
            "parquet": (analytics / "parquet/daily_reports.parquet").read_bytes(),
            "checks": checks.read_bytes(),
        }
        assert verdict["state"] == "PASS"
        assert status["status"] == "succeeded"
        assert list(analytics.parent.glob(".analytics-backup-*")) == []

        with MOD.analytics_refresh_transaction.analytics_writer_lock(
            root / "shared/locks/analytics-refresh.lock"
        ):
            recovered = (
                MOD.analytics_refresh_transaction.recover_pending_analytics_promotions_locked(
                    analytics
                )
            )
        assert recovered == []
        assert (store / "current").resolve() == durable_state["current"]
        assert (analytics / "analytics.duckdb").read_bytes() == durable_state["database"]
        assert (
            analytics / "parquet/daily_reports.parquet"
        ).read_bytes() == durable_state["parquet"]
        assert checks.read_bytes() == durable_state["checks"]


def test_artifact_retry_status_write_failure_uses_terminal_schema() -> None:
    class FlakyClient(FakeClient):
        def __init__(self) -> None:
            super().__init__(_artifact_payloads(), fixed_sha="9" * 40)
            self.commit_attempts = 0

        def get(self, path: str, params: dict[str, str] | None = None):
            if path == "commits/main":
                self.commit_attempts += 1
                if self.commit_attempts == 1:
                    raise MOD.GitHubApiError("injected transient GitHub timeout")
            return super().get(path, params)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        original_client = MOD.GitHubClient
        original_capture = MOD.capture_producer_states
        original_evaluate = MOD.evaluate_producer_readiness
        original_window = MOD.validation_window
        original_write = MOD.atomic_write_json
        injected = {"raised": False}

        def fail_pending_status_once(path: Path, payload: dict) -> None:
            if payload.get("artifact_gate", {}).get("state") == "PENDING" and not injected["raised"]:
                injected["raised"] = True
                raise OSError("injected retry-status persistence failure")
            original_write(path, payload)

        MOD.GitHubClient = lambda _repository: FlakyClient()
        MOD.capture_producer_states = lambda **_kwargs: {}
        MOD.evaluate_producer_readiness = lambda _window, _producers: {
            "state": "PASS", "reasons": [], "evidence": {},
        }
        MOD.validation_window = lambda _date: SimpleNamespace(
            report_date=date(2026, 8, 17),
            deadline=datetime.now(timezone.utc) + timedelta(hours=1),
            recovery_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        MOD.atomic_write_json = fail_pending_status_once
        try:
            assert MOD.run_observer(_observer_args(root)) == 1
        finally:
            MOD.GitHubClient = original_client
            MOD.capture_producer_states = original_capture
            MOD.evaluate_producer_readiness = original_evaluate
            MOD.validation_window = original_window
            MOD.atomic_write_json = original_write

        verdict = json.loads((root / "shared/post_ingestion/latest.json").read_text())
        status = json.loads(
            (root / "shared/run_status/post-producer-analytics.json").read_text()
        )
        assert injected["raised"]
        assert set(verdict) == CANONICAL_TERMINAL_KEYS
        assert verdict["state"] == "FAIL"
        assert "retry status persistence failed" in verdict["reasons"][0]
        assert status["status"] == "failed"


def test_analytics_timeout_error_is_terminal_and_not_artifact_retried() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / "current/reports").mkdir(parents=True)
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")
        attempts = root / "analytics-attempts.txt"

        original_client = MOD.GitHubClient
        original_capture = MOD.capture_producer_states
        original_evaluate = MOD.evaluate_producer_readiness
        original_window = MOD.validation_window
        original_transaction = (
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked
        )

        def fail_with_timeout(**_kwargs):
            count = int(attempts.read_text()) + 1 if attempts.exists() else 1
            attempts.write_text(str(count))
            raise TimeoutError("injected Analytics timeout")

        MOD.GitHubClient = lambda _repository: FakeClient(
            _artifact_payloads(), fixed_sha="c" * 40
        )
        MOD.capture_producer_states = lambda **_kwargs: {}
        MOD.evaluate_producer_readiness = lambda _window, _producers: {
            "state": "PASS", "reasons": [], "evidence": {},
        }
        MOD.validation_window = lambda _date: SimpleNamespace(
            report_date=date(2026, 8, 17),
            deadline=datetime.now(timezone.utc) + timedelta(hours=1),
            recovery_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
            fail_with_timeout
        )
        try:
            assert MOD.run_observer(_observer_args(root)) == 1
        finally:
            MOD.GitHubClient = original_client
            MOD.capture_producer_states = original_capture
            MOD.evaluate_producer_readiness = original_evaluate
            MOD.validation_window = original_window
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                original_transaction
            )

        verdict = json.loads((root / "shared/post_ingestion/latest.json").read_text())
        assert attempts.read_text() == "1"
        assert verdict["state"] == "FAIL"
        assert "TimeoutError: injected Analytics timeout" in verdict["reasons"][0]
        assert (analytics / "analytics.duckdb").read_bytes() == b"old-db"
        assert checks.read_bytes() == b"old-checks"


def test_stalled_analytics_worker_is_killed_and_recovered_at_deadline() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / "current/reports").mkdir(parents=True)
        store = root / "shared/published_reports"
        old_generation = store / "generations/known-good"
        old_generation.mkdir(parents=True)
        (old_generation / "manifest.json").write_text('{"state":"known-good"}\n')
        (store / "current").symlink_to(Path("generations/known-good"))
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")

        original_client = MOD.GitHubClient
        original_capture = MOD.capture_producer_states
        original_evaluate = MOD.evaluate_producer_readiness
        original_window = MOD.validation_window
        original_transaction = (
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked
        )
        MOD.GitHubClient = lambda _repository: FakeClient(
            _artifact_payloads(), fixed_sha="d" * 40
        )
        MOD.capture_producer_states = lambda **_kwargs: {}
        MOD.evaluate_producer_readiness = lambda _window, _producers: {
            "state": "PASS", "reasons": [], "evidence": {},
        }
        MOD.validation_window = lambda _date: SimpleNamespace(
            report_date=date(2026, 8, 17),
            deadline=datetime.now(timezone.utc) + timedelta(seconds=1),
            recovery_deadline=datetime.now(timezone.utc) + timedelta(seconds=1),
        )

        def stalled_transaction(**kwargs):
            return original_transaction(
                **kwargs,
                analytics_store_module=_StalledAnalyticsStore,
                analytics_checks_module=_SuccessfulAnalyticsChecks,
            )

        MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
            stalled_transaction
        )
        started = time.monotonic()
        try:
            assert MOD.run_observer(_observer_args(root)) == 1
        finally:
            MOD.GitHubClient = original_client
            MOD.capture_producer_states = original_capture
            MOD.evaluate_producer_readiness = original_evaluate
            MOD.validation_window = original_window
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                original_transaction
            )
        elapsed = time.monotonic() - started

        verdict = json.loads((root / "shared/post_ingestion/latest.json").read_text())
        status = json.loads(
            (root / "shared/run_status/post-producer-analytics.json").read_text()
        )
        assert elapsed < 5
        assert verdict["state"] == "FAIL"
        assert "deadline passed during Analytics build" in verdict["reasons"][0]
        assert status["status"] == "failed"
        assert (store / "current").resolve() == old_generation.resolve()
        assert (analytics / "analytics.duckdb").read_bytes() == b"old-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert checks.read_bytes() == b"old-checks"
        assert list(analytics.parent.glob(".analytics-*")) == []


def _assert_success_evidence_failure_rolls_back(failure: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / "current/reports").mkdir(parents=True)
        store = root / "shared/published_reports"
        old_generation = store / "generations/known-good"
        old_generation.mkdir(parents=True)
        (old_generation / "manifest.json").write_text('{"state":"known-good"}\n')
        (store / "current").symlink_to(Path("generations/known-good"))
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")

        original_client = MOD.GitHubClient
        original_capture = MOD.capture_producer_states
        original_evaluate = MOD.evaluate_producer_readiness
        original_window = MOD.validation_window
        original_write = MOD.atomic_write_json
        original_locked = MOD.analytics_refresh_transaction.staged_analytics_refresh_locked
        original_transaction = getattr(
            MOD.analytics_refresh_transaction,
            "staged_analytics_refresh_transaction_locked",
            None,
        )

        verdict_path = root / "shared/post_ingestion/latest.json"
        status_path = root / "shared/run_status/post-producer-analytics.json"
        injected = {"raised": False}

        def fail_once(path: Path, payload: dict) -> None:
            is_target = (
                failure == "verdict"
                and Path(path).resolve() == verdict_path.resolve()
                and payload.get("state") == "PASS"
            ) or (
                failure == "status"
                and Path(path).resolve() == status_path.resolve()
                and payload.get("status") == "succeeded"
            )
            if is_target and not injected["raised"]:
                injected["raised"] = True
                raise OSError(f"injected {failure} persistence failure")
            original_write(path, payload)

        MOD.GitHubClient = lambda _repository: FakeClient(_artifact_payloads(), fixed_sha="7" * 40)
        MOD.capture_producer_states = lambda **_kwargs: {}
        MOD.evaluate_producer_readiness = lambda _window, _producers: {
            "state": "PASS", "reasons": [], "evidence": {},
        }
        MOD.validation_window = lambda _date: SimpleNamespace(
            report_date=date(2026, 8, 17),
            deadline=datetime.now(timezone.utc) + timedelta(hours=1),
            recovery_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        MOD.atomic_write_json = fail_once
        MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = _with_fake_analytics(
            original_locked
        )
        if original_transaction is not None:
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                _with_fake_analytics(original_transaction)
            )
        try:
            assert MOD.run_observer(_observer_args(root)) == 1
        finally:
            MOD.GitHubClient = original_client
            MOD.capture_producer_states = original_capture
            MOD.evaluate_producer_readiness = original_evaluate
            MOD.validation_window = original_window
            MOD.atomic_write_json = original_write
            MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = original_locked
            if original_transaction is not None:
                MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                    original_transaction
                )

        verdict = json.loads(verdict_path.read_text())
        status = json.loads(status_path.read_text())
        assert injected["raised"]
        assert verdict["state"] == "FAIL"
        assert set(verdict) == CANONICAL_TERMINAL_KEYS
        assert status["status"] == "failed"
        assert (store / "current").resolve() == old_generation.resolve()
        assert (analytics / "analytics.duckdb").read_bytes() == b"old-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert checks.read_bytes() == b"old-checks"


def test_pass_verdict_persistence_failure_restores_complete_last_known_good() -> None:
    _assert_success_evidence_failure_rolls_back("verdict")


def test_succeeded_status_persistence_failure_restores_complete_last_known_good() -> None:
    _assert_success_evidence_failure_rolls_back("status")


def test_observer_startup_recovers_abandoned_transaction_before_network_polling() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / "current/reports").mkdir(parents=True)
        store = root / "shared/published_reports"
        old_generation = store / "generations/known-good"
        new_generation = store / "generations/candidate"
        old_generation.mkdir(parents=True)
        new_generation.mkdir()
        (store / "current").symlink_to(Path("generations/known-good"))
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")
        verdict_path = root / "shared/post_ingestion/latest.json"
        status_path = root / "shared/run_status/post-producer-analytics.json"
        prepared = MOD.PreparedReportGeneration(
            store=store,
            generation=new_generation,
            previous_generation=old_generation,
            manifest={
                "source_sha": "8" * 40,
                "producers": {},
                "artifacts": [],
            },
        )

        with MOD.analytics_refresh_transaction.analytics_writer_lock(
            root / "shared/locks/analytics-refresh.lock"
        ):
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked(
                reports_root=root / "current/reports",
                published_reports_root=None,
                analytics_root=analytics,
                checks_output=checks,
                analytics_store_module=_SuccessfulAnalyticsStore,
                analytics_checks_module=_SuccessfulAnalyticsChecks,
                promote_companion=lambda: MOD.promote_prepared_generation(prepared),
                recovery_context=MOD.build_transaction_recovery_context(
                    prepared=prepared,
                    report_date=date(2026, 8, 17),
                    verdict_path=verdict_path,
                    status_path=status_path,
                ),
            )

        original_client = MOD.GitHubClient
        MOD.GitHubClient = lambda _repository: (_ for _ in ()).throw(
            AssertionError("network polling must not precede crash recovery")
        )
        try:
            assert MOD.run_observer(_observer_args(root)) == 1
        finally:
            MOD.GitHubClient = original_client

        verdict = json.loads(verdict_path.read_text())
        status = json.loads(status_path.read_text())
        assert set(verdict) == CANONICAL_TERMINAL_KEYS
        assert verdict["state"] == "FAIL"
        assert "abandoned Analytics transaction" in verdict["reasons"][0]
        assert verdict["timeliness"]["state"] == "FAILED"
        assert verdict["timeliness"]["sla_deadline"] == "2026-08-18T02:30:00Z"
        assert verdict["timeliness"]["recovery_deadline"] == "2026-08-18T08:30:00Z"
        assert status["status"] == "failed"
        assert (store / "current").resolve() == old_generation.resolve()
        assert (analytics / "analytics.duckdb").read_bytes() == b"old-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert checks.read_bytes() == b"old-checks"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"post-producer analytics tests: {len(tests)} passed")
