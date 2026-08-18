#!/usr/bin/env python3
"""Regression tests for serialized, staged Analytics refreshes."""

from __future__ import annotations

import importlib.util
import json
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
            except TimeoutError:
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


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"analytics refresh transaction tests: {len(tests)} passed")
