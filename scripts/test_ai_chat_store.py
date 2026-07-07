#!/usr/bin/env python3
"""Tests for saved AI chat session storage.

Run:  .venv/bin/python scripts/test_ai_chat_store.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import ai_chat_store as store  # noqa: E402


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

        if store.list_saved_chats(root) != []:
            raise AssertionError("malformed saved chats should not render in history")


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
        test_default_chat_root_prefers_env_and_shared_runtime,
        test_gitignore_excludes_local_saved_chats,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
