#!/usr/bin/env python3
"""Regression tests for producer-terminal report ingestion."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
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
        lock_timeout_seconds=1,
    )


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
            deadline=future,
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
            ],
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(payload))
        return payload


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

        def with_fake_analytics(function):
            def wrapped(**kwargs):
                return function(
                    **kwargs,
                    analytics_store_module=_SuccessfulAnalyticsStore,
                    analytics_checks_module=_SuccessfulAnalyticsChecks,
                )

            return wrapped

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
        )
        MOD.atomic_write_json = fail_once
        MOD.analytics_refresh_transaction.staged_analytics_refresh_locked = with_fake_analytics(
            original_locked
        )
        if original_transaction is not None:
            MOD.analytics_refresh_transaction.staged_analytics_refresh_transaction_locked = (
                with_fake_analytics(original_transaction)
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
