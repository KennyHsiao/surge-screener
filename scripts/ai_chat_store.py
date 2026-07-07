#!/usr/bin/env python3
"""Saved AI chat session storage.

Only conversations explicitly marked for saving are written here. The default
local path is ignored by git; deployed services can point SURGE_AI_CHAT_DIR at a
shared volume.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
CHAT_SCHEMA_VERSION = 1
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def default_chat_root(repo: str | Path | None = None) -> Path:
    """Return the directory used for saved AI chat sessions."""
    explicit = os.environ.get("SURGE_AI_CHAT_DIR")
    if explicit:
        return Path(explicit).expanduser()
    app_root = os.environ.get("SURGE_APP_ROOT")
    if app_root:
        return Path(app_root).expanduser() / "shared" / "ai_chat_sessions"
    base = Path(repo) if repo is not None else REPO
    return base / "reports" / "ai_chat_sessions"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return uuid.uuid4().hex


def _safe_id(chat_id: str) -> str:
    value = str(chat_id or "").strip()
    if not _ID_RE.match(value):
        raise ValueError(f"invalid chat id: {chat_id!r}")
    return value


def _path(root: str | Path, chat_id: str) -> Path:
    return Path(root).expanduser() / f"{_safe_id(chat_id)}.json"


def _messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant", "system"} or not content:
            continue
        out.append({"role": role, "content": content})
    return out


def _title_from_messages(messages: list[dict[str, str]]) -> str:
    for msg in messages:
        if msg["role"] == "user":
            title = re.sub(r"\s+", " ", msg["content"]).strip()
            return title[:48] or "未命名對話"
    return "未命名對話"


def _read_chat(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    messages = _messages(data.get("messages"))
    if not messages:
        return None
    chat_id = data.get("id") or path.stem
    try:
        chat_id = _safe_id(str(chat_id))
    except ValueError:
        return None
    return {
        "schema_version": int(data.get("schema_version") or CHAT_SCHEMA_VERSION),
        "id": chat_id,
        "title": str(data.get("title") or _title_from_messages(messages)),
        "mode": str(data.get("mode") or "快速問答"),
        "created_at": str(data.get("created_at") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "messages": messages,
        "context_attachment": data.get("context_attachment")
        if isinstance(data.get("context_attachment"), dict) else None,
    }


def list_saved_chats(root: str | Path | None = None) -> list[dict[str, Any]]:
    """List saved chat metadata, newest first. Malformed files are ignored."""
    base = Path(root).expanduser() if root is not None else default_chat_root()
    rows: list[dict[str, Any]] = []
    if not base.exists():
        return rows
    for path in base.glob("*.json"):
        data = _read_chat(path)
        if not data:
            continue
        rows.append({
            "id": data["id"],
            "title": data["title"],
            "mode": data["mode"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "message_count": len(data["messages"]),
        })
    rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return rows


def save_chat(chat: dict[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    """Persist a chat and return the normalized payload."""
    base = Path(root).expanduser() if root is not None else default_chat_root()
    base.mkdir(parents=True, exist_ok=True)
    messages = _messages(chat.get("messages"))
    if not messages:
        raise ValueError("cannot save an empty chat")
    raw_id = str(chat.get("id") or "").strip()
    try:
        chat_id = _safe_id(raw_id) if raw_id else _new_id()
    except ValueError:
        chat_id = _new_id()
    now = _now()
    payload = {
        "schema_version": CHAT_SCHEMA_VERSION,
        "id": chat_id,
        "title": str(chat.get("title") or _title_from_messages(messages)),
        "mode": str(chat.get("mode") or "快速問答"),
        "created_at": str(chat.get("created_at") or now),
        "updated_at": now,
        "messages": messages,
        "context_attachment": chat.get("context_attachment")
        if isinstance(chat.get("context_attachment"), dict) else None,
    }
    dest = _path(base, chat_id)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(dest)
    return payload


def load_chat(chat_id: str, root: str | Path | None = None) -> dict[str, Any]:
    """Load a saved chat by id."""
    base = Path(root).expanduser() if root is not None else default_chat_root()
    data = _read_chat(_path(base, chat_id))
    if not data:
        raise FileNotFoundError(chat_id)
    return data


def delete_chat(chat_id: str, root: str | Path | None = None) -> bool:
    """Delete a saved chat. Returns False when it was already absent."""
    base = Path(root).expanduser() if root is not None else default_chat_root()
    path = _path(base, chat_id)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
