#!/usr/bin/env python3
"""Focused contracts for Phase 5X Schedules Daily Summary adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import DailySummaryData, ScheduleEntry  # noqa: E402
from ui import _components, _read_api, sys_schedules  # noqa: E402


def _summary(*tickers: str) -> DailySummaryData:
    return DailySummaryData.model_validate(
        {
            "as_of_date": "2026-08-01",
            "regime_summary": "Constructive but selective risk-on regime.",
            "candidates": [
                {
                    "ticker": ticker,
                    "verdict": "STRONG_BUY" if index == 0 else "BUY",
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
    )


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"每日報告 {identifier}",
            "category": "系統",
            "cron": "0 7 * * 2-6",
            "cron_note": "交易日",
            "description": "每日報告摘要",
            "result_type": "report_dir",
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_and_available_empty_are_authoritative() -> None:
    outcome = _read_api.DailySummaryApiAvailable(_summary("NVDA", "MU"))
    with patch(
        "ui.sys_schedules._read_api.load_daily_summary",
        return_value=outcome,
    ) as loader:
        content, reason = sys_schedules._latest_report_result()
    if loader.call_count != 1 or reason is not None or content is None:
        raise AssertionError((loader.call_count, content, reason))
    for expected in (
        "報告日期:**2026-08-01**",
        "確認檔數:**2**",
        "🔝 $NVDA, $MU",
    ):
        if expected not in content:
            raise AssertionError(content)

    empty = _read_api.DailySummaryApiAvailable(_summary())
    with patch("ui.sys_schedules._read_api.load_daily_summary", return_value=empty):
        content, reason = sys_schedules._latest_report_result()
    if reason is not None or content is None or "確認檔數:**0**" not in content:
        raise AssertionError((content, reason))
    if "🔝" in content:
        raise AssertionError(content)


def test_unavailable_failures_and_unexpected_results_are_safe() -> None:
    outcomes: tuple[object, ...] = (
        *(
            _read_api.DailySummaryApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.DailySummaryApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
        object(),
    )
    for outcome in outcomes:
        with patch(
            "ui.sys_schedules._read_api.load_daily_summary",
            return_value=outcome,
        ):
            content, reason = sys_schedules._latest_report_result()
        if content is None:
            raise AssertionError((outcome, content, reason))
        if isinstance(outcome, _read_api.DailySummaryApiUnavailable):
            expected, expected_reason = "每日報告資料目前無法使用", outcome.reason
        elif isinstance(outcome, _read_api.DailySummaryApiFailure):
            expected, expected_reason = "每日報告服務目前無法使用", outcome.reason
        else:
            expected, expected_reason = "每日報告服務目前無法使用", "invalid_envelope"
        if expected not in content or reason != expected_reason:
            raise AssertionError((outcome, content, reason))
        if expected_reason in content:
            raise AssertionError(content)


def test_duplicate_visible_cards_reuse_one_daily_summary_result() -> None:
    state = sys_schedules.ScheduleRegistryState(
        "api_available",
        (_schedule("report_a"), _schedule("report_b")),
        None,
    )
    outcome = _read_api.DailySummaryApiAvailable(_summary("NVDA"))
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch(
            "ui.sys_schedules._read_api.load_daily_summary",
            return_value=outcome,
        ) as loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if loader.call_count != 1:
        raise AssertionError(f"Daily Summary request count: {loader.call_count}")
    if _app_text(app).count("確認檔數:**1**") != 2:
        raise AssertionError(_app_text(app))


def test_source_has_one_fixed_client_no_local_fallback_and_python310_ast() -> None:
    path = ROOT / "ui" / "sys_schedules.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    result = functions["_latest_report_result"]
    if result.count("load_daily_summary()") != 1:
        raise AssertionError("Schedules must load one fixed Daily Summary")
    for forbidden in (
        "find_report_dates",
        'REPORTS_DIR / latest / "summary.json"',
        "_shared.load_json",
    ):
        if forbidden in result:
            raise AssertionError(f"Schedules retained Daily fallback: {forbidden}")
    render = functions["render"]
    if '"report_dir"' not in render or "result_cache" not in render:
        raise AssertionError("Schedules does not reuse report results by result type")


def main() -> None:
    tests = (
        test_available_and_available_empty_are_authoritative,
        test_unavailable_failures_and_unexpected_results_are_safe,
        test_duplicate_visible_cards_reuse_one_daily_summary_result,
        test_source_has_one_fixed_client_no_local_fallback_and_python310_ast,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
