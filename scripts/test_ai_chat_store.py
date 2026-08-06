#!/usr/bin/env python3
"""Tests for saved AI chat session storage.

Run:  .venv/bin/python scripts/test_ai_chat_store.py
"""

from __future__ import annotations

from contextlib import nullcontext
import json
import hashlib
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import ai_chat_store as store  # noqa: E402


LEGACY_FAILURE = (
    "呼叫失敗 (RuntimeError): private response at /Users/demo/secret.log\n\n"
    "如果是深度研究，請確認本機 Claude Agent SDK 已登入，或改用快速問答。"
)
SAFE_FAILURE = "AI 回答暫時無法完成，請稍後再試。\n\n事件代碼：QR-CHAT-ANSWER-001"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_save_list_load_delete_chat_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        chat = {
            "id": "",
            "mode": "快速問答",
            "messages": [
                {"role": "user", "content": "請分析 NVDA 追高風險"},
                {"role": "assistant", "content": "先看大盤、量價與反方論點。"},
            ],
        }

        saved = store.save_chat(chat, root)
        if not saved.get("id"):
            raise AssertionError(saved)
        if saved["title"] != "請分析 NVDA 追高風險":
            raise AssertionError(saved)

        rows = store.list_saved_chats(root)
        if len(rows) != 1:
            raise AssertionError(rows)
        if rows[0]["id"] != saved["id"] or rows[0]["message_count"] != 2:
            raise AssertionError(rows[0])

        loaded = store.load_chat(saved["id"], root)
        if loaded["messages"][0]["content"] != "請分析 NVDA 追高風險":
            raise AssertionError(loaded)

        if not store.delete_chat(saved["id"], root):
            raise AssertionError("delete_chat returned False for an existing chat")
        if store.list_saved_chats(root):
            raise AssertionError("deleted chat still appears in history")


def test_malformed_saved_chat_files_are_ignored() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        root.mkdir(exist_ok=True)
        (root / "broken.json").write_text("{bad", encoding="utf-8")
        (root / "list.json").write_text(json.dumps([]), encoding="utf-8")
        (root / "bad-schema.json").write_text(json.dumps({
            "schema_version": {"bad": True},
            "id": "badschema01",
            "messages": [{"role": "user", "content": "hello"}],
        }), encoding="utf-8")

        if store.list_saved_chats(root) != []:
            raise AssertionError("malformed saved chats should not render in history")


def test_exact_legacy_failure_is_projected_without_rewriting_file() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        chat_id = "legacychat01"
        path = root / f"{chat_id}.json"
        payload = {
            "schema_version": 1,
            "id": chat_id,
            "mode": "快速問答",
            "messages": [
                {"role": "user", "content": "保留我的問題"},
                {"role": "assistant", "content": LEGACY_FAILURE},
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        before_hash = _digest(path)
        before_mtime = path.stat().st_mtime_ns
        time.sleep(0.002)

        loaded = store.load_chat(chat_id, root)

        if loaded["messages"] != [
            {"role": "user", "content": "保留我的問題"},
            {"role": "assistant", "content": SAFE_FAILURE},
        ]:
            raise AssertionError(loaded["messages"])
        if _digest(path) != before_hash or path.stat().st_mtime_ns != before_mtime:
            raise AssertionError("legacy projection must not rewrite the saved chat")


def test_legacy_projection_is_narrow_and_preserves_near_misses() -> None:
    near_miss = LEGACY_FAILURE + " extra"
    messages = [
        {"role": "user", "content": LEGACY_FAILURE},
        {"role": "assistant", "content": near_miss},
        {"role": "assistant", "content": "一般回答提到呼叫失敗，但不是舊格式。"},
        {"role": "assistant", "content": LEGACY_FAILURE + " "},
        {"role": "assistant", "content": " " + LEGACY_FAILURE},
        {"role": "assistant", "content": LEGACY_FAILURE},
    ]

    projected = store.project_messages(messages)

    if projected[:3] != messages[:3]:
        raise AssertionError(projected)
    if projected[3:5] != [
        {"role": "assistant", "content": LEGACY_FAILURE},
        {"role": "assistant", "content": LEGACY_FAILURE},
    ]:
        raise AssertionError(projected)
    if projected[5] != {"role": "assistant", "content": SAFE_FAILURE}:
        raise AssertionError(projected[5])


def test_save_never_persists_exact_legacy_diagnostic() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        saved = store.save_chat({
            "mode": "快速問答",
            "messages": [
                {"role": "user", "content": "問題"},
                {"role": "assistant", "content": LEGACY_FAILURE},
            ],
        }, root)
        raw = (root / f"{saved['id']}.json").read_text(encoding="utf-8")
        if "private response" in raw or "/Users/demo/secret.log" in raw:
            raise AssertionError(raw)
        persisted = json.loads(raw)
        if persisted["messages"][-1]["content"] != SAFE_FAILURE:
            raise AssertionError(raw)


def test_live_chat_state_uses_same_narrow_projection() -> None:
    from ui import ai_chat

    original_state = ai_chat.st.session_state
    fake_state: dict = {ai_chat._MESSAGES: [
        {"role": "assistant", "content": LEGACY_FAILURE},
        {"role": "assistant", "content": LEGACY_FAILURE + " near miss"},
    ]}
    try:
        ai_chat.st.session_state = fake_state
        ai_chat._init_state()
        if fake_state[ai_chat._MESSAGES][0]["content"] != SAFE_FAILURE:
            raise AssertionError(fake_state)
        if fake_state[ai_chat._MESSAGES][1]["content"] != LEGACY_FAILURE + " near miss":
            raise AssertionError(fake_state)

        ai_chat._load_payload({
            "messages": [{"role": "assistant", "content": LEGACY_FAILURE}],
            "mode": "快速問答",
        }, saved=False)
        if fake_state[ai_chat._MESSAGES] != [
            {"role": "assistant", "content": SAFE_FAILURE},
        ]:
            raise AssertionError(fake_state)
    finally:
        ai_chat.st.session_state = original_state


def test_chat_save_failure_is_safe_non_recursive_and_class_only() -> None:
    from ui import ai_chat

    secret = "TOP-SECRET /Users/demo/private.log http://127.0.0.1:9999"
    messages = [{"role": "user", "content": "保留目前對話"}]
    fake_state = {
        ai_chat._SAVE: True,
        ai_chat._MESSAGES: list(messages),
        ai_chat._LAST_SAVE_SIG: "",
        ai_chat._TITLE: "",
        ai_chat._MODE: "快速問答",
        ai_chat._CONTEXT: None,
    }
    logged: list[str] = []

    class SaveFailure(RuntimeError):
        pass

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logged.append(record.getMessage())

    original_state = ai_chat.st.session_state
    handler = Capture()
    old_level = ai_chat._LOGGER.level
    old_propagate = ai_chat._LOGGER.propagate
    ai_chat._LOGGER.addHandler(handler)
    ai_chat._LOGGER.setLevel(logging.WARNING)
    ai_chat._LOGGER.propagate = False
    try:
        ai_chat.st.session_state = fake_state
        with patch.object(store, "save_chat", side_effect=SaveFailure(secret)):
            saved = ai_chat._save_if_needed(Path("/unused"))
    finally:
        ai_chat._LOGGER.removeHandler(handler)
        ai_chat._LOGGER.setLevel(old_level)
        ai_chat._LOGGER.propagate = old_propagate
        ai_chat.st.session_state = original_state

    if saved is not False or fake_state[ai_chat._MESSAGES] != messages:
        raise AssertionError(fake_state)
    if fake_state.get(ai_chat._EVENT) != "QR-CHAT-SAVE-001":
        raise AssertionError(fake_state)
    if logged != ["event_code=QR-CHAT-SAVE-001 error_type=SaveFailure"]:
        raise AssertionError(logged)
    serialized = json.dumps(fake_state, ensure_ascii=False, default=str)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999"):
        if sentinel in serialized or any(sentinel in line for line in logged):
            raise AssertionError(f"save diagnostic leaked: {sentinel}")


def test_chat_answer_failure_stores_only_safe_copy_and_class_only_log() -> None:
    from ui import ai_chat

    secret = "Bearer TOP-SECRET from /Users/demo/private.log at http://127.0.0.1:9999"
    fake_state = {
        ai_chat._SAVE: False,
        ai_chat._MESSAGES: [],
        ai_chat._MODE: "快速問答",
        ai_chat._CONTEXT: None,
    }
    logged: list[str] = []

    class AnswerFailure(RuntimeError):
        pass

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logged.append(record.getMessage())

    original_state = ai_chat.st.session_state
    handler = Capture()
    old_level = ai_chat._LOGGER.level
    old_propagate = ai_chat._LOGGER.propagate
    ai_chat._LOGGER.addHandler(handler)
    ai_chat._LOGGER.setLevel(logging.WARNING)
    ai_chat._LOGGER.propagate = False
    try:
        ai_chat.st.session_state = fake_state
        with (
            patch.object(ai_chat.ai_chat_assistant, "answer_chat", side_effect=AnswerFailure(secret)),
            patch.object(ai_chat.st, "spinner", return_value=nullcontext()),
            patch.object(ai_chat, "_rerun_panel"),
        ):
            ai_chat._handle_submit("保留使用者問題", Path("/unused"))
    finally:
        ai_chat._LOGGER.removeHandler(handler)
        ai_chat._LOGGER.setLevel(old_level)
        ai_chat._LOGGER.propagate = old_propagate
        ai_chat.st.session_state = original_state

    if fake_state[ai_chat._MESSAGES] != [
        {"role": "user", "content": "保留使用者問題"},
        {"role": "assistant", "content": SAFE_FAILURE},
    ]:
        raise AssertionError(fake_state)
    if logged != ["event_code=QR-CHAT-ANSWER-001 error_type=AnswerFailure"]:
        raise AssertionError(logged)
    exposed = json.dumps(fake_state, ensure_ascii=False, default=str) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999", "Bearer"):
        if sentinel in exposed:
            raise AssertionError(f"answer diagnostic leaked: {sentinel}")


class _ButtonColumn:
    def __init__(self, pressed: bool) -> None:
        self.pressed = pressed

    def button(self, *args, **kwargs) -> bool:
        return self.pressed


def _capture_logger(logger: logging.Logger) -> tuple[list[str], logging.Handler, int, bool]:
    messages: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = Capture()
    old_level = logger.level
    old_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    return messages, handler, old_level, old_propagate


def _restore_logger(
    logger: logging.Logger,
    handler: logging.Handler,
    old_level: int,
    old_propagate: bool,
) -> None:
    logger.removeHandler(handler)
    logger.setLevel(old_level)
    logger.propagate = old_propagate


def test_chat_history_listing_failure_is_safe_and_class_only() -> None:
    from ui import ai_chat

    secret = "TOP-SECRET /Users/demo/private.json http://127.0.0.1:9999"
    fake_state = {ai_chat._MESSAGES: []}
    rendered_states: list[object] = []

    class ListFailure(RuntimeError):
        pass

    logged, handler, old_level, old_propagate = _capture_logger(ai_chat._LOGGER)
    original_state = ai_chat.st.session_state
    try:
        ai_chat.st.session_state = fake_state
        with (
            patch.object(ai_chat.st, "expander", return_value=nullcontext()),
            patch.object(store, "list_saved_chats", side_effect=ListFailure(secret)),
            patch.object(
                ai_chat._components,
                "render_state_banner",
                side_effect=rendered_states.append,
            ),
        ):
            ai_chat._render_history(Path("/unused"))
    finally:
        _restore_logger(ai_chat._LOGGER, handler, old_level, old_propagate)
        ai_chat.st.session_state = original_state

    if len(rendered_states) != 1 or getattr(rendered_states[0], "event_code", None) != "QR-CHAT-LOAD-001":
        raise AssertionError(rendered_states)
    if logged != ["event_code=QR-CHAT-LOAD-001 error_type=ListFailure"]:
        raise AssertionError(logged)
    exposed = json.dumps(fake_state, ensure_ascii=False, default=str) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999"):
        if sentinel in exposed:
            raise AssertionError(f"history listing diagnostic leaked: {sentinel}")


def test_chat_history_load_failure_is_safe_and_class_only() -> None:
    from ui import ai_chat

    secret = "TOP-SECRET /Users/demo/private.json http://127.0.0.1:9999"
    fake_state = {ai_chat._MESSAGES: [{"role": "user", "content": "keep"}]}
    saved = [{
        "id": "savedchat01",
        "title": "安全對話",
        "mode": ai_chat.ai_chat_assistant.QUICK_MODE,
        "updated_at": "2026-07-16T12:00:00Z",
    }]

    class LoadFailure(RuntimeError):
        pass

    logged, handler, old_level, old_propagate = _capture_logger(ai_chat._LOGGER)
    original_state = ai_chat.st.session_state
    try:
        ai_chat.st.session_state = fake_state
        with (
            patch.object(ai_chat.st, "expander", return_value=nullcontext()),
            patch.object(ai_chat.st, "selectbox", return_value="savedchat01"),
            patch.object(
                ai_chat.st,
                "columns",
                return_value=(_ButtonColumn(True), _ButtonColumn(False)),
            ),
            patch.object(store, "list_saved_chats", return_value=saved),
            patch.object(store, "load_chat", side_effect=LoadFailure(secret)),
            patch.object(ai_chat, "_rerun_panel"),
        ):
            ai_chat._render_history(Path("/unused"))
    finally:
        _restore_logger(ai_chat._LOGGER, handler, old_level, old_propagate)
        ai_chat.st.session_state = original_state

    if fake_state.get(ai_chat._EVENT) != "QR-CHAT-LOAD-001":
        raise AssertionError(fake_state)
    if fake_state[ai_chat._MESSAGES] != [{"role": "user", "content": "keep"}]:
        raise AssertionError(fake_state)
    if logged != ["event_code=QR-CHAT-LOAD-001 error_type=LoadFailure"]:
        raise AssertionError(logged)
    exposed = json.dumps(fake_state, ensure_ascii=False, default=str) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999"):
        if sentinel in exposed:
            raise AssertionError(f"history load diagnostic leaked: {sentinel}")


def test_chat_history_delete_failure_is_safe_and_class_only() -> None:
    from ui import ai_chat

    secret = "TOP-SECRET /Users/demo/private.json http://127.0.0.1:9999"
    fake_state = {
        ai_chat._MESSAGES: [{"role": "user", "content": "keep"}],
        ai_chat._CONFIRM_DELETE: "savedchat01",
    }
    saved = [{
        "id": "savedchat01",
        "title": "安全對話",
        "mode": ai_chat.ai_chat_assistant.QUICK_MODE,
        "updated_at": "2026-07-16T12:00:00Z",
    }]

    class DeleteFailure(RuntimeError):
        pass

    logged, handler, old_level, old_propagate = _capture_logger(ai_chat._LOGGER)
    original_state = ai_chat.st.session_state
    try:
        ai_chat.st.session_state = fake_state
        with (
            patch.object(ai_chat.st, "expander", return_value=nullcontext()),
            patch.object(ai_chat.st, "selectbox", return_value="savedchat01"),
            patch.object(
                ai_chat.st,
                "columns",
                return_value=(_ButtonColumn(False), _ButtonColumn(True)),
            ),
            patch.object(store, "list_saved_chats", return_value=saved),
            patch.object(store, "delete_chat", side_effect=DeleteFailure(secret)),
            patch.object(ai_chat, "_rerun_panel"),
        ):
            ai_chat._render_history(Path("/unused"))
    finally:
        _restore_logger(ai_chat._LOGGER, handler, old_level, old_propagate)
        ai_chat.st.session_state = original_state

    if fake_state.get(ai_chat._EVENT) != "QR-CHAT-DELETE-001":
        raise AssertionError(fake_state)
    if fake_state[ai_chat._MESSAGES] != [{"role": "user", "content": "keep"}]:
        raise AssertionError(fake_state)
    if logged != ["event_code=QR-CHAT-DELETE-001 error_type=DeleteFailure"]:
        raise AssertionError(logged)
    exposed = json.dumps(fake_state, ensure_ascii=False, default=str) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999"):
        if sentinel in exposed:
            raise AssertionError(f"history delete diagnostic leaked: {sentinel}")


def test_chat_context_builder_failure_is_safe_and_class_only() -> None:
    from ui import ai_chat

    secret = "Bearer TOP-SECRET /Users/demo/private.json http://127.0.0.1:9999"
    fake_state = {ai_chat._CONTEXT: None}
    context = {"page_path": "today-decision", "page_title": "今日決策", "ticker": "NVDA"}

    class ContextFailure(RuntimeError):
        pass

    logged, handler, old_level, old_propagate = _capture_logger(ai_chat._LOGGER)
    original_state = ai_chat.st.session_state
    try:
        ai_chat.st.session_state = fake_state
        with (
            patch.object(ai_chat, "_current_path", return_value="today-decision"),
            patch.object(ai_chat.ai_chat_assistant, "available_context", return_value=context),
            patch.object(
                ai_chat.ai_chat_assistant,
                "build_context_attachment",
                side_effect=ContextFailure(secret),
            ),
            patch.object(ai_chat.st, "button", return_value=True),
            patch.object(ai_chat, "_rerun_panel"),
        ):
            ai_chat._render_context_controls()
    finally:
        _restore_logger(ai_chat._LOGGER, handler, old_level, old_propagate)
        ai_chat.st.session_state = original_state

    if fake_state.get(ai_chat._EVENT) != "QR-CHAT-CONTEXT-001" or fake_state[ai_chat._CONTEXT] is not None:
        raise AssertionError(fake_state)
    if logged != ["event_code=QR-CHAT-CONTEXT-001 error_type=ContextFailure"]:
        raise AssertionError(logged)
    exposed = json.dumps(fake_state, ensure_ascii=False, default=str) + "\n" + "\n".join(logged)
    for sentinel in ("TOP-SECRET", "/Users/demo", "127.0.0.1", "9999", "Bearer"):
        if sentinel in exposed:
            raise AssertionError(f"context diagnostic leaked: {sentinel}")


def test_context_projection_drops_diagnostic_shaped_attachment() -> None:
    from ui import ai_chat

    unsafe_summaries = (
        "response body at /Users/demo/private.json token=TOP-SECRET",
        "backend at 10.0.0.5:5432",
        "private endpoint 192.168.1.22:8080",
        "private endpoint 172.16.3.4:8443",
        "metadata endpoint 169.254.169.254:80",
        "private endpoint db.internal:5432",
        "runtime port=5432",
        "profile_name=trading-prod",
        "profile_path=/private/browser-profile",
        "profile_dir=finance-agent",
        "user_data_dir=/private/browser-data",
        "RuntimeError: private detail",
        "Error: private detail",
        "Exception: private detail",
        "CustomException: private detail",
        "ValueError('private detail')",
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
    for summary in unsafe_summaries:
        unsafe = {
            "page_path": "today-decision",
            "page_title": "今日決策",
            "ticker": "NVDA",
            "summary": summary,
            "sources": ["ranked_candidates.json"],
        }
        if ai_chat._safe_context_attachment(unsafe) is not None:
            raise AssertionError(
                f"diagnostic context should be discarded as a whole: {summary!r}"
            )

    normal = {
        "page_path": "today-decision",
        "page_title": "今日決策",
        "ticker": "NVDA",
        "summary": "Ticker: NVDA\nranked_candidates.json: rank_score 82",
        "sources": ["ranked_candidates.json"],
    }
    if ai_chat._safe_context_attachment(normal) != normal:
        raise AssertionError(ai_chat._safe_context_attachment(normal))

    for allowed_summary in (
        "https://example.com/research",
        "profile coverage improved",
        "Error rate declined",
        "樣本於 15:30 完成",
    ):
        allowed = normal | {"summary": allowed_summary}
        if ai_chat._safe_context_attachment(allowed) != allowed:
            raise AssertionError(
                f"ordinary generated context was over-suppressed: {allowed_summary!r}"
            )


def test_default_chat_root_prefers_env_and_shared_runtime() -> None:
    old_ai = os.environ.pop("SURGE_AI_CHAT_DIR", None)
    old_app = os.environ.pop("SURGE_APP_ROOT", None)
    try:
        os.environ["SURGE_AI_CHAT_DIR"] = "/tmp/custom-ai-chat"
        if store.default_chat_root(ROOT) != Path("/tmp/custom-ai-chat"):
            raise AssertionError("SURGE_AI_CHAT_DIR should be the first preference")

        os.environ.pop("SURGE_AI_CHAT_DIR")
        os.environ["SURGE_APP_ROOT"] = "/srv/surge"
        if store.default_chat_root(ROOT) != Path("/srv/surge/shared/ai_chat_sessions"):
            raise AssertionError("SURGE_APP_ROOT should map to shared chat storage")

        os.environ.pop("SURGE_APP_ROOT")
        if store.default_chat_root(ROOT) != ROOT / "reports" / "ai_chat_sessions":
            raise AssertionError("local fallback should live under ignored reports runtime output")
    finally:
        if old_ai is not None:
            os.environ["SURGE_AI_CHAT_DIR"] = old_ai
        else:
            os.environ.pop("SURGE_AI_CHAT_DIR", None)
        if old_app is not None:
            os.environ["SURGE_APP_ROOT"] = old_app
        else:
            os.environ.pop("SURGE_APP_ROOT", None)


def test_gitignore_excludes_local_saved_chats() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "reports/ai_chat_sessions/" not in gitignore:
        raise AssertionError("local saved AI chat sessions must be gitignored")


def main() -> None:
    tests = [
        test_save_list_load_delete_chat_roundtrip,
        test_malformed_saved_chat_files_are_ignored,
        test_exact_legacy_failure_is_projected_without_rewriting_file,
        test_legacy_projection_is_narrow_and_preserves_near_misses,
        test_save_never_persists_exact_legacy_diagnostic,
        test_live_chat_state_uses_same_narrow_projection,
        test_chat_save_failure_is_safe_non_recursive_and_class_only,
        test_chat_answer_failure_stores_only_safe_copy_and_class_only_log,
        test_chat_history_listing_failure_is_safe_and_class_only,
        test_chat_history_load_failure_is_safe_and_class_only,
        test_chat_history_delete_failure_is_safe_and_class_only,
        test_chat_context_builder_failure_is_safe_and_class_only,
        test_context_projection_drops_diagnostic_shaped_attachment,
        test_default_chat_root_prefers_env_and_shared_runtime,
        test_gitignore_excludes_local_saved_chats,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
