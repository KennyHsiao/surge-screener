#!/usr/bin/env python3
"""Focused UX-1A target-surface safety regressions.

This suite stays offline. It verifies that malformed artifacts and diagnostic
payloads become fixed UI states while preserving the existing page workflows.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.header,
        app.subheader,
        app.caption,
        app.warning,
        app.info,
        app.error,
        app.success,
        app.markdown,
    ):
        values.extend(str(element.value) for element in elements)
    return "\n".join(values)


def test_today_api_only_summary_helpers_fail_soft_without_local_reads() -> None:
    from ui import _read_api, today_decision

    with patch(
        "ui.today_decision._shared.load_json",
        side_effect=AssertionError("candidate API rows must not read local JSON"),
    ):
        require(today_decision._scored_candidates([]) == [], "empty scored rows leaked")
        require(today_decision._ranked_candidates([]) == [], "empty ranked rows leaked")

    require(
        not hasattr(today_decision, "_flow_signals"),
        "retired local Options Flow helper was restored",
    )

    for outcome in (
        _read_api.DailySummaryApiUnavailable("unreadable"),
        _read_api.DailySummaryApiFailure("invalid_envelope"),
    ):
        require(
            today_decision._daily_summary_view(outcome) == (None, None),
            "Daily Summary failure did not stay fail soft",
        )
    for retired in (
        "_latest_daily_summary",
        "_latest_market_thesis",
        "_MARKET_THESIS_DIR",
    ):
        require(
            not hasattr(today_decision, retired),
            f"retired local Today helper was restored: {retired}",
        )


def test_today_trade_state_failure_is_fixed_and_class_only() -> None:
    from ui import today_decision

    secret = "TOP-SECRET /Users/ken/private.json http://127.0.0.1:9999"
    messages: list[str] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    logger = today_decision.LOGGER
    handler = CaptureHandler()
    old_level = logger.level
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        with patch(
            "ui.today_decision.trade_state_engine.build_trade_state_rows",
            side_effect=RuntimeError(secret),
        ):
            app = AppTest.from_string(
                "from ui.today_decision import _render_trade_state_summary\n"
                "_render_trade_state_summary()\n",
                default_timeout=10,
            ).run()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate

    require(not app.exception, f"trade state failure crashed: {app.exception}")
    exposed = "\n".join([_app_text(app), *messages])
    for forbidden in ("TOP-SECRET", "/Users/ken", "127.0.0.1", "9999"):
        require(forbidden not in exposed, f"trade-state diagnostic leaked: {forbidden}")
    require(
        messages == [
            "event_code=QR-TODAY-TRADE-STATE-001 error_type=RuntimeError"
        ],
        f"unexpected trade-state logs: {messages!r}",
    )
    require("QR-TODAY-TRADE-STATE-001" in _app_text(app), "stable event missing")


def test_schedule_dynamic_heading_and_result_failure_are_safe() -> None:
    from api.models import ScheduleEntry
    from ui import sys_schedules

    schedule = ScheduleEntry.model_validate(
        {
            "id": "unsafe_label_test",
            "name": "<img src=x onerror=alert(1)>",
            "category": "</span><script>alert(1)</script>",
            "cron": "0 1 * * *",
            "cron_note": "每天",
            "description": "安全描述",
            "result_type": "report_dir",
        },
        strict=True,
    )
    state = sys_schedules.ScheduleRegistryState("api_available", (schedule,), None)
    secret = "TOP-SECRET /Users/ken/private.json http://127.0.0.1:8000"
    messages: list[str] = []

    class ResultError(RuntimeError):
        pass

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    logger = sys_schedules.LOGGER
    handler = CaptureHandler()
    old_level = logger.level
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        with (
            patch("ui.sys_schedules._load_schedules", return_value=state),
            patch.dict(
                sys_schedules._RESULT_FETCHERS,
                {"report_dir": lambda: (_ for _ in ()).throw(ResultError(secret))},
            ),
        ):
            app = AppTest.from_string(
                "from ui.sys_schedules import render\nrender()\n",
                default_timeout=10,
            ).run()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate

    require(not app.exception, f"schedule result failure crashed: {app.exception}")
    exposed = "\n".join([_app_text(app), *messages])
    for forbidden in ("TOP-SECRET", "/Users/ken", "127.0.0.1", "8000"):
        require(forbidden not in exposed, f"schedule diagnostic leaked: {forbidden}")
    require(
        messages == ["event_code=QR-SCHEDULES-RESULT-001 error_type=ResultError"],
        f"unexpected schedule logs: {messages!r}",
    )
    require("QR-SCHEDULES-RESULT-001" in _app_text(app), "schedule event missing")

    source = (ROOT / "ui" / "sys_schedules.py").read_text(encoding="utf-8")
    require(
        "f\"<h3" not in source and "cat_chip_html" not in source,
        "dynamic schedule labels must not use heading HTML",
    )


def test_schedule_result_payload_with_diagnostic_is_suppressed() -> None:
    from api.models import ScheduleEntry
    from ui import sys_schedules

    schedule = ScheduleEntry.model_validate(
        {
            "id": "unsafe_result_test",
            "name": "安全工作",
            "category": "系統",
            "cron": "0 1 * * *",
            "cron_note": "每天",
            "description": "",
            "result_type": "report_dir",
        },
        strict=True,
    )
    state = sys_schedules.ScheduleRegistryState("api_available", (schedule,), None)
    diagnostic = "command: docker exec private; log tail /Users/ken/private.log"
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch.dict(sys_schedules._RESULT_FETCHERS, {"report_dir": lambda: diagnostic}),
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    require(not app.exception, f"diagnostic result crashed: {app.exception}")
    require(diagnostic not in _app_text(app), "diagnostic result payload leaked")
    require("QR-SCHEDULES-RESULT-001" in _app_text(app), "suppression event missing")


def test_unreadable_reflection_is_a_class_only_result_failure() -> None:
    from ui import sys_schedules

    secret = "TOP-SECRET /Users/ken/private-reflection.md"
    messages: list[str] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = CaptureHandler()
    logger = sys_schedules.LOGGER
    old_level = logger.level
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    latest = Path("/Users/ken/private-reflection.md")
    try:
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "glob", return_value=[latest]),
            patch.object(Path, "read_text", side_effect=PermissionError(secret)),
        ):
            result, failure = sys_schedules._fetch_result(
                sys_schedules._latest_reflection_result
            )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate

    require(result is None and failure == "read_failure", "unreadable reflection looked populated")
    require(
        messages == ["event_code=QR-SCHEDULES-RESULT-001 error_type=PermissionError"],
        f"unexpected reflection failure log: {messages!r}",
    )
    exposed = "\n".join(messages)
    require("TOP-SECRET" not in exposed and "/Users/ken" not in exposed, "reflection path leaked")


def main() -> None:
    tests = [
        test_today_api_only_summary_helpers_fail_soft_without_local_reads,
        test_today_trade_state_failure_is_fixed_and_class_only,
        test_schedule_dynamic_heading_and_result_failure_are_safe,
        test_schedule_result_payload_with_diagnostic_is_suppressed,
        test_unreadable_reflection_is_a_class_only_result_failure,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
