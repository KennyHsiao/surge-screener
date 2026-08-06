#!/usr/bin/env python3
"""Runtime helper tests for Today Decision candidate controls."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import _candidate_controls as cc  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_candidate_status_is_inactive_when_pid_is_gone() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-03T06:00:00Z",
    }

    active = cc._status_is_active(
        data,
        now=datetime(2026, 7, 3, 6, 1, tzinfo=timezone.utc),
        process_checker=lambda pid: False,
    )

    require(active is False, "missing PID must not keep candidate controls disabled")


def test_interrupted_candidate_status_records_failed_stage() -> None:
    data = {
        "status": "running",
        "stage": {"id": "rank_candidates", "label": "程式排序候選", "progress_pct": 50},
        "stages": [
            {"id": "rank_candidates", "label": "程式排序候選", "status": "running", "progress_pct": 50},
        ],
        "errors": [],
    }

    fixed = cc._interrupted_candidate_status(
        data,
        "背景程序已不存在，這次本機候選刷新已中斷。",
        now=datetime(2026, 7, 3, 6, 10, tzinfo=timezone.utc),
    )

    require(fixed["status"] == "failed", str(fixed))
    require(fixed["stage"]["status"] == "failed", str(fixed["stage"]))
    require(fixed["finished_at"] == "2026-07-03T06:10:00Z", str(fixed))
    require(fixed["errors"][-1]["stage"] == "rank_candidates", str(fixed["errors"]))


def test_long_analytics_refresh_remains_active_before_one_hour() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-13T14:30:00Z",
        "stage": {
            "id": "analytics_refresh",
            "label": "更新資料與 Analytics",
            "progress_pct": 92,
        },
    }
    now = datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc)

    reason = cc._candidate_interrupt_reason(
        data,
        now=now,
        process_checker=lambda pid: True,
    )
    active = cc._status_is_active(
        data,
        now=now,
        process_checker=lambda pid: True,
    )

    require(reason is None, f"30-minute Analytics refresh was interrupted: {reason}")
    require(active is True, "30-minute Analytics refresh must remain active")


def test_status_message_translates_llm_progress() -> None:
    message = cc._status_message_zh("7 candidates scored; 2 remaining")
    require(message == "LLM 已累積 7 檔；尚有 2 檔未深檢", message)

    unsafe = cc._status_message_zh("tail=/Users/demo/secret.log token=secret")
    require(unsafe is None, f"arbitrary stage text survived: {unsafe!r}")


def test_history_flow_classifies_refresh_modes() -> None:
    require(
        cc._history_flow({"metrics": {"passed_hard_filters": 20}, "stage": {}}) == "完整刷新 + 排名",
        "full refresh history label mismatch",
    )
    require(
        cc._history_flow({"metrics": {"scored_candidates": 3}, "stage": {}}) == "少量 LLM",
        "LLM history label mismatch",
    )
    require(
        cc._history_flow({"metrics": {"ranked_candidates": 50}, "stage": {}}) == "只重排",
        "rank-only history label mismatch",
    )


def test_launch_session_projection_drops_runtime_diagnostics() -> None:
    raw = {
        "pid": 31337,
        "mode": "llm_deep_check",
        "mode_label": "attacker-controlled",
        "command": ["python", "/Users/demo/private.py", "--token=secret"],
        "launcher": ["systemd-run"],
        "log_path": "/Users/demo/private.log",
        "unit": "private.service",
        "profile": "secret-profile",
        "auth_status": {"message": "Bearer secret"},
        "pending_path": "/tmp/private.json",
    }

    projected = cc._safe_launch_projection(raw)

    require(projected == {
        "mode": "llm_deep_check",
        "mode_label": "少量 LLM",
        "operation": "loading",
        "event_code": None,
    }, str(projected))
    raw_text = json.dumps(projected, ensure_ascii=False)
    for sentinel in ("31337", "/Users/", "secret", "systemd", "private.service"):
        require(sentinel not in raw_text, f"unsafe launch metadata survived: {sentinel}")


def test_preupgrade_launch_session_is_normalized_in_place() -> None:
    original_state = cc.st.session_state
    fake_state = {
        "candidate_pipeline_last_launch": {
            "mode": "codex_auth_login",
            "pid": 42,
            "log_path": "/tmp/auth.log",
            "message": "open http://127.0.0.1:9999/?token=secret",
        }
    }
    try:
        cc.st.session_state = fake_state
        cc._normalize_launch_session()
        require(fake_state["candidate_pipeline_last_launch"] == {
            "mode": "codex_auth_login",
            "mode_label": "登入中",
            "operation": "loading",
            "event_code": None,
        }, str(fake_state))
    finally:
        cc.st.session_state = original_state


def test_history_write_projection_keeps_metrics_not_diagnostics() -> None:
    raw = {
        "run_id": "candidates-local-2026-07-16T00:00:00Z",
        "job": "candidates-local",
        "status": "failed",
        "started_at": "2026-07-16T00:00:00Z",
        "finished_at": "2026-07-16T00:10:00Z",
        "stage": {
            "id": "rank_candidates",
            "label": "/Users/demo/private.log",
            "message": "Bearer secret response body",
            "progress_pct": 75,
        },
        "metrics": {
            "ranked_candidates": 25,
            "rank_limit": 50,
            "unsafe": "/Users/demo/private.log",
        },
        "outputs": {
            "ranked_candidates": {
                "path": "/Users/demo/ranked_candidates.json",
                "exists": True,
            }
        },
        "warnings": ["profile=private"],
        "errors": [{"message": "curl http://127.0.0.1:9999 --token secret"}],
    }

    safe = cc._safe_history_record(raw)
    text = json.dumps(safe, ensure_ascii=False, sort_keys=True)

    require(safe["metrics"]["ranked_candidates"] == 25, text)
    require(safe["metrics"]["rank_limit"] == 50, text)
    require(safe["warning_count"] == 1 and safe["error_count"] == 1, text)
    require(safe["event_code"] == "QR-CANDIDATE-STATUS-001", text)
    for sentinel in ("/Users/", "Bearer", "secret", "127.0.0.1", "profile=", "response body"):
        require(sentinel not in text, f"unsafe history field survived: {sentinel}")


def test_candidate_labels_fail_closed() -> None:
    require(cc._status_zh("private-status /tmp/x") == "未知", "status must fail closed")
    require(cc._safe_stage_label({"id": "private", "label": "/tmp/x"}) == "本機候選刷新",
            "stage label must fail closed")
    require(cc._safe_stage_label({"id": "rank_candidates", "label": "/tmp/x"}) == "程式排序候選",
            "known stage id must use fixed copy")


def _launch_kwargs() -> dict:
    return {
        "rank_limit": 50,
        "options_gate_limit": 10,
        "candidate_limit": 3,
        "universe": "sp1500",
        "yf_batch_size": 25,
        "min_data_coverage": 0.70,
        "min_avg_dollar_vol": 5_000_000,
        "min_market_cap": 300_000_000,
        "min_price": 5.0,
        "max_ret_5d": 30.0,
        "max_ret_20d": 60.0,
        "earnings_exclude_days": 2,
    }


def test_launch_failure_session_and_log_are_class_only() -> None:
    secret = "TOP-SECRET /Users/demo/private.log http://127.0.0.1:9999"
    fake_state: dict = {}
    logged: list[str] = []

    class LaunchFailure(RuntimeError):
        pass

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logged.append(record.getMessage())

    original_state = cc.st.session_state
    handler = Capture()
    old_level = cc._LOGGER.level
    old_propagate = cc._LOGGER.propagate
    cc._LOGGER.addHandler(handler)
    cc._LOGGER.setLevel(logging.WARNING)
    cc._LOGGER.propagate = False
    try:
        cc.st.session_state = fake_state
        with patch.object(cc, "launch_background", side_effect=LaunchFailure(secret)):
            cc._launch_candidate_run("full_refresh", **_launch_kwargs())
    finally:
        cc._LOGGER.removeHandler(handler)
        cc._LOGGER.setLevel(old_level)
        cc._LOGGER.propagate = old_propagate
        cc.st.session_state = original_state

    require(fake_state[cc._LAST_LAUNCH_KEY] == {
        "mode": "full_refresh",
        "mode_label": "完整刷新",
        "operation": "failure",
        "event_code": "QR-CANDIDATE-LAUNCH-001",
    }, str(fake_state))
    require(logged == ["event_code=QR-CANDIDATE-LAUNCH-001 error_type=LaunchFailure"], str(logged))
    exposed = json.dumps(fake_state, ensure_ascii=False) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999"):
        require(sentinel not in exposed, f"launch diagnostic leaked: {sentinel}")


def test_auth_failure_session_and_log_are_class_only() -> None:
    secret = "Bearer TOP-SECRET from /tmp/auth.log profile=private"
    fake_state: dict = {}
    logged: list[str] = []

    class AuthFailure(RuntimeError):
        pass

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logged.append(record.getMessage())

    original_state = cc.st.session_state
    handler = Capture()
    old_level = cc._LOGGER.level
    old_propagate = cc._LOGGER.propagate
    cc._LOGGER.addHandler(handler)
    cc._LOGGER.setLevel(logging.WARNING)
    cc._LOGGER.propagate = False
    try:
        cc.st.session_state = fake_state
        with patch.object(cc, "read_pending_codex_request", side_effect=AuthFailure(secret)):
            require(cc._read_pending_request_safe() is None, "auth failure must fail soft")
    finally:
        cc._LOGGER.removeHandler(handler)
        cc._LOGGER.setLevel(old_level)
        cc._LOGGER.propagate = old_propagate
        cc.st.session_state = original_state

    require(fake_state[cc._LAST_LAUNCH_KEY] == {
        "mode": "codex_auth_login",
        "mode_label": "登入中",
        "operation": "failure",
        "event_code": "QR-CANDIDATE-AUTH-001",
    }, str(fake_state))
    require(logged == ["event_code=QR-CANDIDATE-AUTH-001 error_type=AuthFailure"], str(logged))
    exposed = json.dumps(fake_state, ensure_ascii=False) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/tmp/auth.log", "profile=", "Bearer"):
        require(sentinel not in exposed, f"auth diagnostic leaked: {sentinel}")


def test_auth_resume_failure_session_and_log_are_class_only() -> None:
    secret = "Bearer TOP-SECRET from /tmp/resume.log http://127.0.0.1:9999"
    fake_state: dict = {}
    logged: list[str] = []

    class ResumeFailure(RuntimeError):
        pass

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logged.append(record.getMessage())

    original_state = cc.st.session_state
    handler = Capture()
    old_level = cc._LOGGER.level
    old_propagate = cc._LOGGER.propagate
    cc._LOGGER.addHandler(handler)
    cc._LOGGER.setLevel(logging.WARNING)
    cc._LOGGER.propagate = False
    try:
        cc.st.session_state = fake_state
        with (
            patch.object(cc, "_read_pending_request_safe", return_value={"mode": "llm_deep_check"}),
            patch.object(cc, "refresh_codex_auth_status", return_value={"ok": True, "state": "authenticated"}),
            patch.object(cc, "resume_pending_codex_run", side_effect=ResumeFailure(secret)),
            patch.object(cc.st, "container", return_value=nullcontext()),
            patch.object(cc.st, "markdown"),
            patch.object(cc.st, "caption"),
            patch.object(cc.st, "success"),
            patch.object(cc.st, "error"),
            patch.object(cc._shared, "chips_row"),
            patch.object(cc._components, "render_state_banner"),
        ):
            cc._render_codex_auth_status.__wrapped__()
    finally:
        cc._LOGGER.removeHandler(handler)
        cc._LOGGER.setLevel(old_level)
        cc._LOGGER.propagate = old_propagate
        cc.st.session_state = original_state

    require(fake_state[cc._LAST_LAUNCH_KEY] == {
        "mode": "codex_auth_login",
        "mode_label": "登入中",
        "operation": "failure",
        "event_code": "QR-CANDIDATE-AUTH-001",
    }, str(fake_state))
    require(logged == ["event_code=QR-CANDIDATE-AUTH-001 error_type=ResumeFailure"], str(logged))
    exposed = json.dumps(fake_state, ensure_ascii=False) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/tmp/resume.log", "127.0.0.1", "9999", "Bearer"):
        require(sentinel not in exposed, f"resume diagnostic leaked: {sentinel}")


def test_append_history_writes_only_safe_projection() -> None:
    raw = {
        "run_id": "candidates-local-2026-07-16T00:00:00Z",
        "job": "candidates-local",
        "status": "failed",
        "started_at": "2026-07-16T00:00:00Z",
        "finished_at": "2026-07-16T00:01:00Z",
        "stage": {
            "id": "rank_candidates",
            "label": "/Users/demo/private.log",
            "message": "response body token=TOP-SECRET",
            "progress_pct": 50,
        },
        "metrics": {"ranked_candidates": 12, "unsafe": "Bearer TOP-SECRET"},
        "outputs": {"ranked_candidates": {"path": "/tmp/private.json", "exists": True}},
        "warnings": ["profile=private"],
        "errors": [{"message": "curl http://127.0.0.1:9999"}],
    }
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "history.jsonl"
        with patch.object(cc, "_RUN_HISTORY_PATH", path):
            cc._append_candidate_history(raw)
        text = path.read_text(encoding="utf-8")
        row = json.loads(text)

    require(row["metrics"]["ranked_candidates"] == 12, text)
    require(row["error_count"] == 1 and row["warning_count"] == 1, text)
    for sentinel in ("/Users/", "/tmp/", "TOP-SECRET", "Bearer", "profile=", "127.0.0.1"):
        require(sentinel not in text, f"history diagnostic leaked: {sentinel}")


def test_candidate_source_has_no_log_tail_or_raw_debug_renderer() -> None:
    source = (ROOT / "ui" / "_candidate_controls.py").read_text(encoding="utf-8")
    for forbidden in (
        "def _tail_text",
        "st.code(",
        "meta.get(\"log_path\")",
        "meta.get('pid'",
        "errors[-1].get(\"message\"",
    ):
        require(forbidden not in source, f"raw candidate debug surface remains: {forbidden}")


def main() -> None:
    tests = [
        test_candidate_status_is_inactive_when_pid_is_gone,
        test_interrupted_candidate_status_records_failed_stage,
        test_long_analytics_refresh_remains_active_before_one_hour,
        test_status_message_translates_llm_progress,
        test_history_flow_classifies_refresh_modes,
        test_launch_session_projection_drops_runtime_diagnostics,
        test_preupgrade_launch_session_is_normalized_in_place,
        test_history_write_projection_keeps_metrics_not_diagnostics,
        test_candidate_labels_fail_closed,
        test_launch_failure_session_and_log_are_class_only,
        test_auth_failure_session_and_log_are_class_only,
        test_auth_resume_failure_session_and_log_are_class_only,
        test_append_history_writes_only_safe_projection,
        test_candidate_source_has_no_log_tail_or_raw_debug_renderer,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
