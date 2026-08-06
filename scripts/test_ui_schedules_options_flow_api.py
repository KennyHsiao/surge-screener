#!/usr/bin/env python3
"""Focused contracts for Phase 5A Schedules Options Flow adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import OptionsFlowFeedData, ScheduleEntry  # noqa: E402
from ui import _components, _read_api, sys_schedules  # noqa: E402


def _feed(*rows: tuple[str, str, float]) -> OptionsFlowFeedData:
    return OptionsFlowFeedData.model_validate(
        {
            "generated_at": "2026-08-02T02:03:04+00:00",
            "as_of": "2026-08-02",
            "provider": "fixture",
            "universe_size": max(len(rows), 1),
            "min_notional": 250_000,
            "signal_count": len(rows),
            "signals": [
                {
                    "ticker": ticker,
                    "direction": direction,
                    "flow_score": score,
                    "est_notional_usd": 1_000_000,
                    "biggest": None,
                    "expiry": None,
                    "max_voi": 2.0,
                    "high_voi_strikes": 1,
                    "call_put_ratio": 2.0,
                    "put_call_ratio": 0.5,
                    "tags": [],
                }
                for ticker, direction, score in rows
            ],
        },
        strict=True,
    )


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"異常流 {identifier}",
            "category": "系統",
            "cron": "0 22 * * 1-5",
            "cron_note": "交易日",
            "description": "異常流摘要",
            "result_type": "options_flow",
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
    populated = _read_api.OptionsFlowApiAvailable(
        _feed(
            ("NVDA", "bullish", 90.0),
            ("AMD", "bearish", 80.0),
            ("META", "bullish", 70.0),
        )
    )
    with patch("ui.sys_schedules._read_api.load_options_flow", return_value=populated) as loader:
        content, reason = sys_schedules._latest_options_flow_result()
    if loader.call_count != 1 or reason is not None or content is None:
        raise AssertionError((loader.call_count, content, reason))
    for expected in ("2026-08-02", "偵測 **3** 筆", "🟢2 / 🔴1", "前 5:NVDA, AMD, META"):
        if expected not in content:
            raise AssertionError(content)

    empty = _read_api.OptionsFlowApiAvailable(_feed())
    with patch("ui.sys_schedules._read_api.load_options_flow", return_value=empty):
        content, reason = sys_schedules._latest_options_flow_result()
    if reason is not None or content is None or "偵測 **0** 筆" not in content:
        raise AssertionError((content, reason))
    if "前 5:" in content:
        raise AssertionError(content)


def test_unavailable_and_failures_have_safe_distinct_partial_output() -> None:
    outcomes: tuple[_read_api.OptionsFlowApiResult, ...] = (
        *(
            _read_api.OptionsFlowApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.OptionsFlowApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with patch("ui.sys_schedules._read_api.load_options_flow", return_value=outcome):
            content, reason = sys_schedules._latest_options_flow_result()
        if reason != outcome.reason or content is None:
            raise AssertionError((outcome, content, reason))
        expected = (
            "異常流資料目前無法使用"
            if isinstance(outcome, _read_api.OptionsFlowApiUnavailable)
            else "異常流服務目前無法使用"
        )
        if expected not in content or outcome.reason in content:
            raise AssertionError((outcome, content))


def test_duplicate_visible_cards_reuse_one_options_flow_result() -> None:
    state = sys_schedules.ScheduleRegistryState(
        "api_available",
        (_schedule("flow_a"), _schedule("flow_b")),
        None,
    )
    outcome = _read_api.OptionsFlowApiAvailable(
        _feed(("NVDA", "bullish", 90.0))
    )
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch("ui.sys_schedules._read_api.load_options_flow", return_value=outcome) as loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if loader.call_count != 1:
        raise AssertionError(f"Options Flow request count: {loader.call_count}")
    if _app_text(app).count("偵測 **1** 筆") != 2:
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
    result = functions["_latest_options_flow_result"]
    if result.count("load_options_flow()") != 1:
        raise AssertionError("Schedules must load one fixed Options Flow feed")
    if 'REPORTS_DIR / "options_flow" / "latest.json"' in result:
        raise AssertionError("Schedules retained the local Options Flow read")
    if "result_cache" not in functions["render"]:
        raise AssertionError("Schedules render does not reuse results by result type")


def main() -> None:
    tests = (
        test_available_and_available_empty_are_authoritative,
        test_unavailable_and_failures_have_safe_distinct_partial_output,
        test_duplicate_visible_cards_reuse_one_options_flow_result,
        test_source_has_one_fixed_client_no_local_fallback_and_python310_ast,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
