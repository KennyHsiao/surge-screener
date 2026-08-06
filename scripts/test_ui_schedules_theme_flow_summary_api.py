#!/usr/bin/env python3
"""Focused contracts for Phase 5D Schedules Theme Flow adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScheduleEntry, ThemeFlowData  # noqa: E402
from ui import _components, _read_api, sys_schedules  # noqa: E402


def _snapshot() -> ThemeFlowData:
    theme = {
        "theme": "AI 基礎設施",
        "desc": "fixture theme",
        "parent_sector_etfs": ["XLK"],
        "flow_5d": 1_000_000.0,
        "flow_20d": 2_000_000.0,
        "accel": 500_000.0,
        "flow_5d_norm": 1.5,
        "flow_20d_norm": 2.5,
        "accel_norm": 0.5,
        "ret_5d": 3.0,
        "top_share": 0.4,
        "high_concentration": False,
        "breadth_inflow_ratio": 0.7,
        "positive_flow_count": 2,
        "negative_flow_count": 1,
        "n_used": 3,
        "n_total": 3,
        "reps": [
            {
                "ticker": "NVDA",
                "flow_20d": 1_500_000.0,
                "flow_5d": 800_000.0,
                "ret_5d": 4.0,
            }
        ],
        "raw_heat_score": 80.0,
        "signal_quality": 0.9,
        "heat_score": 72.0,
        "capital_state": "加速流入(推估)",
        "bottom_fishing": False,
    }
    return ThemeFlowData.model_validate(
        {
            "as_of": "2026-08-03",
            "generated_at": "2026-08-03T01:02:03+00:00",
            "benchmark": "SPY",
            "n_failed_download": 0,
            "buckets": {
                "加速流入(推估)": ["AI 基礎設施"],
                "流入趨緩": [],
                "中性": [],
                "流出(推估)": [],
            },
            "shared_mega_caps": [{"ticker": "NVDA", "themes": 2}],
            "themes": [theme],
            "board_fingerprint": "0123456789abcdef",
        },
        strict=True,
    )


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"主題資金流 {identifier}",
            "category": "系統",
            "cron": "45 7 * * 2-6",
            "cron_note": "交易日",
            "description": "Theme Flow 摘要",
            "result_type": "theme_flow",
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_snapshot_preserves_summary_projection() -> None:
    outcome = _read_api.ThemeFlowApiAvailable(_snapshot())
    with patch("ui.sys_schedules._read_api.load_theme_flow", return_value=outcome) as loader:
        content, reason = sys_schedules._latest_theme_flow_result()
    if loader.call_count != 1 or reason is not None or content is None:
        raise AssertionError((loader.call_count, content, reason))
    for expected in ("資料日期 **2026-08-03**", "主題 **1** 個", "2026-08-03T01:02:03+00:00"):
        if expected not in content:
            raise AssertionError(content)


def test_unavailable_failures_and_unexpected_results_are_safe() -> None:
    outcomes: tuple[object, ...] = (
        *(
            _read_api.ThemeFlowApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.ThemeFlowApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
        object(),
    )
    for outcome in outcomes:
        with (
            patch("ui.sys_schedules._read_api.load_theme_flow", return_value=outcome),
            patch("ui.sys_schedules._read_api.load_theme_flow_analysis") as analysis,
        ):
            content, reason = sys_schedules._latest_theme_flow_result()
        analysis.assert_not_called()
        if content is None:
            raise AssertionError((outcome, content, reason))
        if isinstance(outcome, _read_api.ThemeFlowApiUnavailable):
            expected, expected_reason = "主題資金流資料目前無法使用", outcome.reason
        elif isinstance(outcome, _read_api.ThemeFlowApiFailure):
            expected, expected_reason = "主題資金流服務目前無法使用", outcome.reason
        else:
            expected, expected_reason = "主題資金流服務目前無法使用", "invalid_envelope"
        if expected not in content or reason != expected_reason:
            raise AssertionError((outcome, content, reason))
        if expected_reason in content:
            raise AssertionError(content)


def test_duplicate_visible_cards_reuse_one_theme_flow_result() -> None:
    state = sys_schedules.ScheduleRegistryState(
        "api_available",
        (_schedule("theme_a"), _schedule("theme_b")),
        None,
    )
    outcome = _read_api.ThemeFlowApiAvailable(_snapshot())
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch("ui.sys_schedules._read_api.load_theme_flow", return_value=outcome) as loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if loader.call_count != 1:
        raise AssertionError(f"Theme Flow request count: {loader.call_count}")
    if _app_text(app).count("主題 **1** 個") != 2:
        raise AssertionError(_app_text(app))


def test_source_has_one_fixed_client_no_local_fallback_or_sibling_work() -> None:
    path = ROOT / "ui" / "sys_schedules.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    result = functions["_latest_theme_flow_result"]
    if result.count("load_theme_flow()") != 1:
        raise AssertionError("Schedules must load one fixed Theme Flow snapshot")
    for forbidden in (
        'REPORTS_DIR / "theme_flow_snapshot.json"',
        "_shared.load_json",
        "load_theme_flow_analysis",
        "launch_background",
        "refresh",
    ):
        if forbidden in result:
            raise AssertionError(f"Schedules crossed Theme sibling boundary: {forbidden}")
    render = functions["render"]
    if '"theme_flow"' not in render or "result_cache" not in render:
        raise AssertionError("Schedules does not reuse Theme results by result type")


def main() -> None:
    tests = (
        test_available_snapshot_preserves_summary_projection,
        test_unavailable_failures_and_unexpected_results_are_safe,
        test_duplicate_visible_cards_reuse_one_theme_flow_result,
        test_source_has_one_fixed_client_no_local_fallback_or_sibling_work,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
