#!/usr/bin/env python3
"""Offline tests for schedules-page reflection helpers."""

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


def test_extract_llm_reflection_json_from_markdown_block() -> None:
    from ui import sys_schedules

    markdown = """# Monthly Self-Reflection

## Pre-computed Metrics

```json
{"total_picks": 1}
```

## LLM Reflection

{
  "sample_size_warning": {"message": "Only one pick."},
  "narrative_summary": "This is a status check.",
  "data_quality_flags": ["pattern_type missing"],
  "proposed_prompt_changes": [
    {"suggested_change": "Fix ledger logging", "user_action_required": true}
  ]
}

"""

    data = sys_schedules._extract_llm_reflection_json(markdown)

    require(isinstance(data, dict), "reflection JSON should parse")
    require(data["sample_size_warning"]["message"] == "Only one pick.",
            "sample warning should be preserved")
    require(data["data_quality_flags"] == ["pattern_type missing"],
            "data quality flags should be preserved")
    require(data["proposed_prompt_changes"][0]["user_action_required"] is True,
            "proposed actions should be preserved")


def test_extract_llm_reflection_json_returns_none_for_missing_block() -> None:
    from ui import sys_schedules

    require(sys_schedules._extract_llm_reflection_json("# No reflection") is None,
            "missing reflection section should return None")


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.caption,
        app.warning,
        app.info,
        app.error,
        app.markdown,
    ):
        values.extend(str(element.value) for element in elements)
    return "\n".join(values)


def test_reflection_detail_keeps_only_the_structured_human_summary() -> None:
    from ui import sys_schedules

    markdown = """# Monthly Self-Reflection

## LLM Reflection

{
  "sample_size_warning": {"message": "樣本仍少，結論僅供觀察。"},
  "narrative_summary": "目前訊號尚未累積足夠樣本。",
  "data_quality_flags": ["缺少一週後績效"],
  "proposed_prompt_changes": [
    {
      "suggested_change": "補齊觀察期",
      "rationale": "等待更多已結案樣本。",
      "user_action_required": true
    }
  ]
}

RAW-SOURCE-SENTINEL
"""
    detail = {
        "name": "monthly-2026-07.md",
        "summary": "safe summary",
        "text": markdown,
    }
    wrapper = (
        "from ui.sys_schedules import _render_reflection_detail\n"
        "_render_reflection_detail(__import__('ui.sys_schedules', "
        "fromlist=['_'])._UX1A_TEST_DETAIL)\n"
    )
    with patch.object(sys_schedules, "_UX1A_TEST_DETAIL", detail, create=True):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    require(not app.exception, f"reflection render raised: {app.exception}")
    rendered = _app_text(app)
    for expected in (
        "樣本仍少，結論僅供觀察。",
        "目前訊號尚未累積足夠樣本。",
        "缺少一週後績效",
        "補齊觀察期",
        "等待更多已結案樣本。",
    ):
        require(expected in rendered, f"missing safe field: {expected!r}")
    require("RAW-SOURCE-SENTINEL" not in rendered, "raw Markdown leaked")
    require(not app.tabs, "raw reflection tabs must be removed")
    require(not app.json, "raw reflection JSON must be removed")
    require(not app.get("download_button"), "raw reflection download must be removed")


def test_reflection_diagnostic_fields_are_suppressed_with_stable_event() -> None:
    from ui import sys_schedules

    sentinels = (
        "/Users/ken/private.json",
        "http://127.0.0.1:8000/internal",
        "docker exec private-container",
        "AWS_SECRET_ACCESS_KEY=do-not-render",
    )
    data = {
        "sample_size_warning": {"message": sentinels[0]},
        "narrative_summary": sentinels[1],
        "data_quality_flags": [sentinels[2]],
        "proposed_prompt_changes": [
            {"suggested_change": sentinels[3], "rationale": "safe rationale"},
            {"suggested_change": "SAFE-SIBLING-SHOULD-NOT-RENDER"},
        ],
    }
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
    try:
        with patch.object(sys_schedules, "_UX1A_TEST_DATA", data, create=True):
            app = AppTest.from_string(
                "from ui.sys_schedules import _render_reflection_summary, _UX1A_TEST_DATA\n"
                "_render_reflection_summary(_UX1A_TEST_DATA)\n",
                default_timeout=10,
            ).run()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate

    require(not app.exception, f"diagnostic suppression raised: {app.exception}")
    exposed = "\n".join([_app_text(app), *messages])
    for sentinel in sentinels:
        require(sentinel not in exposed, f"diagnostic leaked: {sentinel!r}")
    require(
        messages
        and set(messages)
        == {"event_code=QR-SCHEDULES-REFLECTION-001 error_type=SuppressedDiagnostic"},
        f"unexpected suppression logs: {messages!r}",
    )
    require(
        "SAFE-SIBLING-SHOULD-NOT-RENDER" not in exposed,
        "a diagnostic reflection must suppress the entire summary, not echo safe siblings",
    )


def test_prohibited_diagnostic_detector_covers_private_network_and_runtime_shapes() -> None:
    from ui import sys_schedules

    prohibited = (
        "/opt/surge/private.json",
        r"C:\Users\ken\private.json",
        r"\\fileserver\private\secret.txt",
        "http://10.0.0.5:5432/internal",
        "https://192.168.1.22/admin",
        "http://172.16.3.4:8080/x",
        "http://169.254.169.254/latest/meta-data",
        "http://[fd00::1]:8000/private",
        "db.internal:5432",
        "port=5432",
        "profile_name=trading-prod",
        "command: python scripts/private.py",
        "RuntimeError: private detail",
        "Error: private detail",
        "Exception: private detail",
        "ValueError('private detail')",
        "stderr: private detail",
        "Bearer abc.def.ghi",
        "{'token': 'private-token'}",
        "file:///opt/surge/private.json",
        "private IPv6 fd00::1",
        "private loopback ::1",
        "private loopback ::1:8501",
        "runtime port 5432",
        "credential=abc123",
        "authorization=abc123",
        "api_key=abc123",
        "access_key=abc123",
        "secret_key=abc123",
        "AWS_ACCESS_KEY_ID=abc123",
        "cmd=python scripts/private.py",
        "argv=['python', 'scripts/private.py']",
        "python scripts/private.py",
        "python3 -m private.module",
        "uv run scripts/private.py",
        "docker exec private-container",
        "kubectl logs private-pod",
        "systemctl restart private.service",
    )
    for sentinel in prohibited:
        require(
            sys_schedules._contains_prohibited_diagnostic(sentinel),
            f"diagnostic shape was not suppressed: {sentinel!r}",
        )

    allowed = (
        "https://example.com/research",
        "樣本於 15:30 完成",
        "Call/Put 比為 1.45",
        "profile coverage improved",
        "error rate declined",
    )
    for text in allowed:
        require(
            not sys_schedules._contains_prohibited_diagnostic(text),
            f"ordinary summary was over-suppressed: {text!r}",
        )


def main() -> None:
    tests = [
        test_extract_llm_reflection_json_from_markdown_block,
        test_extract_llm_reflection_json_returns_none_for_missing_block,
        test_reflection_detail_keeps_only_the_structured_human_summary,
        test_reflection_diagnostic_fields_are_suppressed_with_stable_event,
        test_prohibited_diagnostic_detector_covers_private_network_and_runtime_shapes,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
