#!/usr/bin/env python3
"""Regression tests for serialized, staged Analytics refreshes."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "analytics_refresh_transaction_under_test",
    ROOT / "scripts" / "analytics_refresh_transaction.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_report_overlay_preserves_base_history_and_published_wins() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = root / "release-reports"
        published = root / "published" / "reports"
        (base / "candidate_scores").mkdir(parents=True)
        (published / "candidate_scores").mkdir(parents=True)
        (base / "candidate_scores/2026-08-15.json").write_text("base-old\n")
        (base / "candidate_scores/2026-08-17.json").write_text("base-stale\n")
        (published / "candidate_scores/2026-08-17.json").write_text("published-fresh\n")
        (base / "risk_guard").mkdir()
        (base / "risk_guard/latest.json").write_text("runtime\n")
        (root / "content").mkdir()
        (root / "content/us_watchlist.txt").write_text("NVDA\n")
        (root / "ranked_candidates.json").write_text('{"tickers": []}\n')

        with MOD.report_overlay(base, published, temp_parent=root) as overlay:
            assert (overlay / "candidate_scores/2026-08-15.json").read_text() == "base-old\n"
            assert (overlay / "candidate_scores/2026-08-17.json").read_text() == "published-fresh\n"
            assert (overlay / "risk_guard/latest.json").read_text() == "runtime\n"
            assert (overlay.parent / "content/us_watchlist.txt").read_text() == "NVDA\n"
            assert (overlay.parent / "ranked_candidates.json").is_file()
            overlay_path = overlay
        assert not overlay_path.exists()


def test_writer_lock_serializes_competing_refreshes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        lock_path = Path(directory) / "analytics-refresh.lock"
        observed: list[str] = []

        def contender() -> None:
            try:
                with MOD.analytics_writer_lock(lock_path, timeout_seconds=0.05):
                    observed.append("acquired")
            except MOD.AnalyticsWriterLockTimeout:
                observed.append("timed_out")

        with MOD.analytics_writer_lock(lock_path, timeout_seconds=1):
            thread = threading.Thread(target=contender)
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()
        assert observed == ["timed_out"]


def _fake_store(payload: bytes):
    class FakeStore:
        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            target = Path(analytics_root)
            (target / "parquet").mkdir(parents=True)
            (target / "parquet/daily_reports.parquet").write_bytes(b"new-parquet")
            (target / "analytics.duckdb").write_bytes(payload)
            return {"daily_reports": {"rows": 16, "source": str(reports_root)}}

    return FakeStore


def test_failed_staged_checks_keep_last_known_good_database() -> None:
    class FailingChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            Path(output_path).write_text("partial\n")
            raise RuntimeError("injected check failure")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"last-known-good")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"

        try:
            MOD.staged_analytics_refresh(
                reports_root=reports,
                published_reports_root=None,
                analytics_root=analytics,
                checks_output=checks,
                lock_path=root / "shared/locks/analytics-refresh.lock",
                analytics_store_module=_fake_store(b"candidate-db"),
                analytics_checks_module=FailingChecks,
            )
        except RuntimeError as exc:
            assert "injected check failure" in str(exc)
        else:
            raise AssertionError("failed checks must fail closed")

        assert (analytics / "analytics.duckdb").read_bytes() == b"last-known-good"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert not checks.exists()


def test_successful_staged_refresh_promotes_database_last_and_exact_evidence() -> None:
    class PassingChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            payload = {
                "generated_at": "2026-08-18T00:00:00Z",
                "status": "WARN",
                "summary": {"pass": 72, "warn": 2, "block": 0},
                "checks": [{"id": "table:daily_reports:latest_date", "value": "2026-08-17"}],
            }
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(json.dumps(payload))
            return payload

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        checks = root / "shared/analytics_checks/latest.json"

        result = MOD.staged_analytics_refresh(
            reports_root=reports,
            published_reports_root=None,
            analytics_root=analytics,
            checks_output=checks,
            lock_path=root / "shared/locks/analytics-refresh.lock",
            analytics_store_module=_fake_store(b"promoted-db"),
            analytics_checks_module=PassingChecks,
        )

        assert (analytics / "analytics.duckdb").read_bytes() == b"promoted-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"new-parquet"
        assert json.loads(checks.read_text())["summary"]["block"] == 0
        assert result["database"]["sha256"] == MOD.sha256_file(analytics / "analytics.duckdb")
        assert result["checks"]["summary"] == {"pass": 72, "warn": 2, "block": 0}
        assert result["tables"]["daily_reports"]["rows"] == 16


def test_failed_post_ingestion_gate_keeps_last_known_good_database() -> None:
    class PassingChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            payload = {"status": "WARN", "summary": {"pass": 70, "warn": 2, "block": 0}}
            Path(output_path).write_text(json.dumps(payload))
            return payload

    def reject_stale_report(_checks, _tables) -> None:
        raise MOD.AnalyticsGateError("daily report latest date is stale")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"last-known-good")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        try:
            MOD.staged_analytics_refresh(
                reports_root=reports,
                published_reports_root=None,
                analytics_root=analytics,
                checks_output=root / "shared/analytics_checks/latest.json",
                lock_path=root / "shared/locks/analytics-refresh.lock",
                analytics_store_module=_fake_store(b"semantically-stale-db"),
                analytics_checks_module=PassingChecks,
                gate_validator=reject_stale_report,
            )
        except MOD.AnalyticsGateError as exc:
            assert "latest date is stale" in str(exc)
        else:
            raise AssertionError("semantic post-ingestion failure must fail closed")
        assert (analytics / "analytics.duckdb").read_bytes() == b"last-known-good"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"


def _passing_checks():
    class PassingChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            payload = {
                "status": "WARN",
                "summary": {"pass": 72, "warn": 2, "block": 0},
                "checks": [],
            }
            Path(output_path).write_text(json.dumps(payload))
            return payload

    return PassingChecks


def test_gate_failure_preserves_generation_database_parquet_and_checks() -> None:
    def reject(_checks, _tables) -> None:
        raise MOD.AnalyticsGateError("injected strict gate failure")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        published = root / "published"
        old_generation = published / "generations/old"
        new_generation = published / "generations/new"
        old_generation.mkdir(parents=True)
        new_generation.mkdir()
        current = published / "current"
        current.symlink_to(Path("generations/old"))
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")
        companion_calls: list[str] = []

        def promote_companion():
            companion_calls.append("promoted")
            current.unlink()
            current.symlink_to(Path("generations/new"))
            return lambda: companion_calls.append("rolled-back")

        try:
            with MOD.analytics_writer_lock(root / "shared/locks/analytics-refresh.lock"):
                MOD.staged_analytics_refresh_locked(
                    reports_root=reports,
                    published_reports_root=None,
                    analytics_root=analytics,
                    checks_output=checks,
                    analytics_store_module=_fake_store(b"candidate-db"),
                    analytics_checks_module=_passing_checks(),
                    gate_validator=reject,
                    promote_companion=promote_companion,
                )
        except MOD.AnalyticsGateError as exc:
            assert "strict gate failure" in str(exc)
        else:
            raise AssertionError("strict gate failure must fail closed")

        assert companion_calls == []
        assert current.resolve() == old_generation.resolve()
        assert (analytics / "analytics.duckdb").read_bytes() == b"old-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert checks.read_bytes() == b"old-checks"


def test_promotion_failure_rolls_back_generation_database_parquet_and_checks() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        published = root / "published"
        old_generation = published / "generations/old"
        new_generation = published / "generations/new"
        old_generation.mkdir(parents=True)
        new_generation.mkdir()
        current = published / "current"
        current.symlink_to(Path("generations/old"))
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        target_db = analytics / "analytics.duckdb"
        target_db.write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")

        def promote_companion():
            current.unlink()
            current.symlink_to(Path("generations/new"))

            def rollback() -> None:
                current.unlink()
                current.symlink_to(Path("generations/old"))

            return rollback

        original_replace = MOD.os.replace
        injected = {"raised": False}

        def fail_database_promotion(source, destination):
            if (
                not injected["raised"]
                and Path(source).name == "analytics.duckdb"
                and Path(destination).resolve() == target_db.resolve()
            ):
                injected["raised"] = True
                raise OSError("injected database promotion failure")
            return original_replace(source, destination)

        MOD.os.replace = fail_database_promotion
        try:
            try:
                with MOD.analytics_writer_lock(root / "shared/locks/analytics-refresh.lock"):
                    MOD.staged_analytics_refresh_locked(
                        reports_root=reports,
                        published_reports_root=None,
                        analytics_root=analytics,
                        checks_output=checks,
                        analytics_store_module=_fake_store(b"candidate-db"),
                        analytics_checks_module=_passing_checks(),
                        promote_companion=promote_companion,
                    )
            except OSError as exc:
                assert "database promotion failure" in str(exc)
            else:
                raise AssertionError("injected promotion failure must propagate")
        finally:
            MOD.os.replace = original_replace

        assert injected["raised"]
        assert current.resolve() == old_generation.resolve()
        assert target_db.read_bytes() == b"old-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert checks.read_bytes() == b"old-checks"


def test_parallel_data_health_cannot_enter_atomic_post_producer_promotion() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        lock_path = root / "shared/locks/analytics-refresh.lock"
        observed: list[str] = []

        def promote_companion():
            def contender() -> None:
                try:
                    with MOD.analytics_writer_lock(lock_path, timeout_seconds=0.05):
                        observed.append("acquired")
                except TimeoutError:
                    observed.append("timed_out")

            thread = threading.Thread(target=contender)
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()
            return None

        with MOD.analytics_writer_lock(lock_path):
            MOD.staged_analytics_refresh_locked(
                reports_root=reports,
                published_reports_root=None,
                analytics_root=analytics,
                checks_output=checks,
                analytics_store_module=_fake_store(b"new-db"),
                analytics_checks_module=_passing_checks(),
                promote_companion=promote_companion,
            )

        assert observed == ["timed_out"]
        assert (analytics / "analytics.duckdb").read_bytes() == b"new-db"


def test_provisional_transaction_retains_backups_until_explicit_commit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir()
        analytics = root / "shared/data"
        (analytics / "parquet").mkdir(parents=True)
        (analytics / "analytics.duckdb").write_bytes(b"old-db")
        (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
        checks = root / "shared/analytics_checks/latest.json"
        checks.parent.mkdir(parents=True)
        checks.write_bytes(b"old-checks")

        with MOD.analytics_writer_lock(root / "shared/locks/analytics-refresh.lock"):
            transaction = MOD.staged_analytics_refresh_transaction_locked(
                reports_root=reports,
                published_reports_root=None,
                analytics_root=analytics,
                checks_output=checks,
                analytics_store_module=_fake_store(b"new-db"),
                analytics_checks_module=_passing_checks(),
            )
            backup = transaction.analytics_promotion.backup
            assert backup.is_dir()
            assert (backup / "analytics.duckdb").read_bytes() == b"old-db"
            assert (backup / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
            assert (backup / "analytics-checks.json").read_bytes() == b"old-checks"
            transaction.commit()

        assert not backup.exists()
        assert (analytics / "analytics.duckdb").read_bytes() == b"new-db"
        assert (analytics / "parquet/daily_reports.parquet").read_bytes() == b"new-parquet"
        assert json.loads(checks.read_text())["summary"] == {"pass": 72, "warn": 2, "block": 0}


def _crash_recovery_fixture(root: Path) -> dict[str, Path]:
    reports = root / "reports"
    reports.mkdir()
    store = root / "published"
    old_generation = store / "generations/old"
    new_generation = store / "generations/new"
    old_generation.mkdir(parents=True)
    new_generation.mkdir()
    current = store / "current"
    current.symlink_to(Path("generations/old"))
    analytics = root / "shared/data"
    (analytics / "parquet").mkdir(parents=True)
    (analytics / "analytics.duckdb").write_bytes(b"old-db")
    (analytics / "parquet/daily_reports.parquet").write_bytes(b"old-parquet")
    checks = root / "shared/analytics_checks/latest.json"
    checks.parent.mkdir(parents=True)
    checks.write_bytes(b"old-checks")
    verdict = root / "shared/post_ingestion/latest.json"
    status = root / "shared/run_status/post-producer-analytics.json"
    return {
        "reports": reports,
        "store": store,
        "old_generation": old_generation,
        "new_generation": new_generation,
        "current": current,
        "analytics": analytics,
        "checks": checks,
        "verdict": verdict,
        "status": status,
        "lock": root / "shared/locks/analytics-refresh.lock",
    }


def _recovery_context(paths: dict[str, Path]) -> dict:
    failure_verdict = {
        "schema_version": 1,
        "captured_at": "2026-08-18T00:00:00Z",
        "state": "FAIL",
        "reasons": ["abandoned Analytics transaction recovered after process interruption"],
        "report_date": "2026-08-17",
        "source_sha": "7" * 40,
        "producers": {},
        "artifacts": [],
        "analytics_summary": None,
        "analytics_status": None,
        "analytics_checks": [],
        "database": {},
        "promoted_at": None,
    }
    return {
        "companion": {
            "kind": "symlink",
            "pointer": str(paths["current"]),
            "previous_target": str(paths["old_generation"]),
            "promoted_target": str(paths["new_generation"]),
        },
        "failure_writes": [
            {"path": str(paths["verdict"]), "payload": failure_verdict},
            {"path": str(paths["status"]), "payload": {**failure_verdict, "status": "failed"}},
        ],
    }


def _promote_fixture_companion(paths: dict[str, Path]):
    paths["current"].unlink()
    paths["current"].symlink_to(Path("generations/new"))

    def rollback() -> None:
        paths["current"].unlink()
        paths["current"].symlink_to(Path("generations/old"))

    return rollback


def _abandon_fixture_transaction(paths: dict[str, Path]):
    return MOD.staged_analytics_refresh_transaction_locked(
        reports_root=paths["reports"],
        published_reports_root=None,
        analytics_root=paths["analytics"],
        checks_output=paths["checks"],
        analytics_store_module=_fake_store(b"new-db"),
        analytics_checks_module=_passing_checks(),
        promote_companion=lambda: _promote_fixture_companion(paths),
        recovery_context=_recovery_context(paths),
    )


def test_pending_journal_and_complete_backups_precede_companion_mutation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))

        def inspect_then_promote():
            backups = list(paths["analytics"].parent.glob(".analytics-backup-*"))
            assert len(backups) == 1
            journal = json.loads((backups[0] / "transaction.json").read_text())
            assert journal["state"] == "pending"
            assert (backups[0] / "analytics.duckdb").read_bytes() == b"old-db"
            assert (backups[0] / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
            assert (backups[0] / "analytics-checks.json").read_bytes() == b"old-checks"
            return _promote_fixture_companion(paths)

        with MOD.analytics_writer_lock(paths["lock"]):
            transaction = MOD.staged_analytics_refresh_transaction_locked(
                reports_root=paths["reports"],
                published_reports_root=None,
                analytics_root=paths["analytics"],
                checks_output=paths["checks"],
                analytics_store_module=_fake_store(b"new-db"),
                analytics_checks_module=_passing_checks(),
                promote_companion=inspect_then_promote,
                recovery_context=_recovery_context(paths),
            )
            transaction.rollback()


def _assert_subprocess_crash_recovers_partial_success(*, write_status: bool) -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))
        child = os.fork()
        if child == 0:
            with MOD.analytics_writer_lock(paths["lock"]):
                _abandon_fixture_transaction(paths)
                paths["verdict"].parent.mkdir(parents=True, exist_ok=True)
                paths["status"].parent.mkdir(parents=True, exist_ok=True)
                paths["verdict"].write_text('{"state":"PASS"}\n')
                if write_status:
                    paths["status"].write_text('{"status":"succeeded"}\n')
                os._exit(91)

        _, wait_status = os.waitpid(child, 0)
        assert os.waitstatus_to_exitcode(wait_status) == 91
        assert paths["current"].resolve() == paths["new_generation"].resolve()
        assert (paths["analytics"] / "analytics.duckdb").read_bytes() == b"new-db"

        with MOD.analytics_writer_lock(paths["lock"]):
            recovered = MOD.recover_pending_analytics_promotions_locked(paths["analytics"])
            assert len(recovered) == 1
            assert MOD.recover_pending_analytics_promotions_locked(paths["analytics"]) == []

        assert paths["current"].resolve() == paths["old_generation"].resolve()
        assert (paths["analytics"] / "analytics.duckdb").read_bytes() == b"old-db"
        assert (paths["analytics"] / "parquet/daily_reports.parquet").read_bytes() == b"old-parquet"
        assert paths["checks"].read_bytes() == b"old-checks"
        assert json.loads(paths["verdict"].read_text())["state"] == "FAIL"
        assert json.loads(paths["status"].read_text())["status"] == "failed"
        assert list(paths["analytics"].parent.glob(".analytics-backup-*")) == []


def test_subprocess_crash_after_pass_verdict_recovers_complete_state() -> None:
    _assert_subprocess_crash_recovers_partial_success(write_status=False)


def test_subprocess_crash_after_succeeded_status_recovers_complete_state() -> None:
    _assert_subprocess_crash_recovers_partial_success(write_status=True)


def test_next_data_health_writer_recovers_abandoned_transaction_before_build() -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))
        with MOD.analytics_writer_lock(paths["lock"]):
            _abandon_fixture_transaction(paths)

        with MOD.analytics_writer_lock(paths["lock"]):
            result = MOD.staged_analytics_refresh_locked(
                reports_root=paths["reports"],
                published_reports_root=None,
                analytics_root=paths["analytics"],
                checks_output=paths["checks"],
                analytics_store_module=_fake_store(b"data-health-db"),
                analytics_checks_module=_passing_checks(),
            )

        assert paths["current"].resolve() == paths["old_generation"].resolve()
        assert (paths["analytics"] / "analytics.duckdb").read_bytes() == b"data-health-db"
        assert result["checks"]["summary"] == {"pass": 72, "warn": 2, "block": 0}
        assert json.loads(paths["verdict"].read_text())["state"] == "FAIL"
        assert list(paths["analytics"].parent.glob(".analytics-backup-*")) == []


def test_durable_commit_marker_causes_cleanup_only_after_restart() -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))
        with MOD.analytics_writer_lock(paths["lock"]):
            transaction = _abandon_fixture_transaction(paths)
            backup = transaction.analytics_promotion.backup
            original_cleanup = MOD._cleanup_backup_durable

            def interrupt_cleanup(target):
                if Path(target) == backup:
                    return None
                return original_cleanup(target)

            MOD._cleanup_backup_durable = interrupt_cleanup
            try:
                transaction.commit()
            finally:
                MOD._cleanup_backup_durable = original_cleanup
            assert json.loads((backup / "transaction.json").read_text())["state"] == "committed"
            recovered = MOD.recover_pending_analytics_promotions_locked(paths["analytics"])

        assert recovered == []
        assert not backup.exists()
        assert paths["current"].resolve() == paths["new_generation"].resolve()
        assert (paths["analytics"] / "analytics.duckdb").read_bytes() == b"new-db"


def test_recovery_pointer_conflict_fails_closed_and_retains_backup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))
        conflicting = paths["store"] / "generations/conflicting"
        conflicting.mkdir()
        with MOD.analytics_writer_lock(paths["lock"]):
            transaction = _abandon_fixture_transaction(paths)
            backup = transaction.analytics_promotion.backup
            paths["current"].unlink()
            paths["current"].symlink_to(Path("generations/conflicting"))
            try:
                MOD.recover_pending_analytics_promotions_locked(paths["analytics"])
            except RuntimeError as exc:
                assert "conflict" in str(exc).lower()
            else:
                raise AssertionError("pointer conflict must fail closed")

        assert backup.is_dir()
        assert (backup / "transaction.json").is_file()
        assert paths["current"].resolve() == conflicting.resolve()
        assert (paths["analytics"] / "analytics.duckdb").read_bytes() == b"new-db"
        assert (paths["analytics"] / "parquet/daily_reports.parquet").read_bytes() == b"new-parquet"
        assert json.loads(paths["checks"].read_text())["summary"] == {
            "pass": 72,
            "warn": 2,
            "block": 0,
        }


def test_missing_recovery_journal_fails_closed_and_retains_backup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        paths = _crash_recovery_fixture(Path(directory))
        backup = paths["analytics"].parent / ".analytics-backup-corrupt"
        backup.mkdir()
        (backup / "unknown-fragment").write_bytes(b"retain-me")
        with MOD.analytics_writer_lock(paths["lock"]):
            try:
                MOD.recover_pending_analytics_promotions_locked(paths["analytics"])
            except RuntimeError as exc:
                assert "journal is missing" in str(exc)
                assert "backup retained" in str(exc)
            else:
                raise AssertionError("missing journal must fail closed")

        assert (backup / "unknown-fragment").read_bytes() == b"retain-me"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"analytics refresh transaction tests: {len(tests)} passed")
