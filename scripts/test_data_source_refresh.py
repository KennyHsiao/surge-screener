#!/usr/bin/env python3
"""Self-contained tests for Data Health source refresh orchestration.

Run: .venv/bin/python scripts/test_data_source_refresh.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "data_source_refresh_under_test",
        ROOT / "scripts" / "data_source_refresh.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_refresh_core_sources_then_analytics_in_order() -> None:
    mod = _load_module()
    calls: list[str] = []

    class FakeStore:
        @staticmethod
        def analytics_dir():
            calls.append("analytics_dir")
            return Path("/tmp/surge-analytics")

        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {
                "universe_snapshots": {"rows": 1500},
                "daily_bars": {"rows": 120000},
                "daily_money_flow": {"rows": 500},
            }

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {
                "status": "PASS",
                "recommended_action": "USE_TODAY_SIGNALS",
                "warning_codes": [],
            }

    def fake_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("source_refresh")
        return {
            "tickers": ["NVDA", "AMD"],
            "steps": [
                {"name": "universe", "status": "ok"},
                {"name": "daily_bars", "status": "ok"},
                {"name": "money_flow", "status": "ok"},
            ],
        }

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        result = mod.refresh_core_sources_and_analytics(
            reports_root=root / "reports",
            content_root=root / "content",
            analytics_root=root / "analytics",
            checks_output=root / "reports" / "analytics_checks" / "latest.json",
            data_refresher=fake_refresher,
            analytics_store_module=FakeStore,
            analytics_checks_module=FakeChecks,
        )

    if calls != ["source_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["checks"]["status"] != "PASS":
        raise AssertionError(result)
    if result["tables"]["daily_bars"] != 120000:
        raise AssertionError(result)


def test_source_error_is_reported_without_skipping_analytics() -> None:
    mod = _load_module()
    calls: list[str] = []

    class FakeStore:
        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {"daily_bars": {"rows": 0}}

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {"status": "BLOCK", "recommended_action": "BLOCK_TODAY_SIGNALS"}

    def fake_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("source_refresh")
        return {
            "tickers": [],
            "steps": [
                {"name": "universe", "status": "error", "error": "provider unavailable"},
                {"name": "daily_bars", "status": "error", "error": "no tickers"},
            ],
        }

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        result = mod.refresh_core_sources_and_analytics(
            reports_root=root / "reports",
            content_root=root / "content",
            analytics_root=root / "analytics",
            checks_output=root / "reports" / "analytics_checks" / "latest.json",
            data_refresher=fake_refresher,
            analytics_store_module=FakeStore,
            analytics_checks_module=FakeChecks,
        )

    if calls != ["source_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["source_status"] != "error":
        raise AssertionError(result)
    if result["checks"]["status"] != "BLOCK":
        raise AssertionError(result)


def test_refresher_exception_is_reported_without_skipping_analytics() -> None:
    mod = _load_module()
    calls: list[str] = []

    class FakeStore:
        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {"universe_snapshots": {"rows": 0}}

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {"status": "BLOCK", "recommended_action": "BLOCK_TODAY_SIGNALS"}

    def failing_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("source_refresh")
        raise RuntimeError("source orchestrator crashed")

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        result = mod.refresh_core_sources_and_analytics(
            reports_root=root / "reports",
            content_root=root / "content",
            analytics_root=root / "analytics",
            checks_output=root / "reports" / "analytics_checks" / "latest.json",
            data_refresher=failing_refresher,
            analytics_store_module=FakeStore,
            analytics_checks_module=FakeChecks,
        )

    if calls != ["source_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["source_status"] != "error":
        raise AssertionError(result)
    if result["source"]["steps"][0]["error"] != "source orchestrator crashed":
        raise AssertionError(result)


if __name__ == "__main__":
    tests = [
        test_refresh_core_sources_then_analytics_in_order,
        test_source_error_is_reported_without_skipping_analytics,
        test_refresher_exception_is_reported_without_skipping_analytics,
    ]
    for test in tests:
        test()
    print(f"data source refresh tests: {len(tests)} passed")
