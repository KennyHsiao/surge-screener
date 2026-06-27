#!/usr/bin/env python3
"""Claude CLI auth helpers for the Streamlit-triggered LLM workflow."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
RUN_STATUS_DIR = REPO / "reports" / "run_status"
AUTH_STATUS_PATH = RUN_STATUS_DIR / "claude-auth.json"
AUTH_LOG_PATH = RUN_STATUS_DIR / "claude-auth.log"
PENDING_REQUEST_PATH = RUN_STATUS_DIR / "claude-auth-pending.json"
LOGIN_COMMAND = ["claude", "auth", "login"]
STATUS_COMMAND = ["claude", "auth", "status", "--json"]
_LOGIN_PROCS: dict[int, subprocess.Popen] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return payload


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _runtime_env(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = {**os.environ}
    if env:
        merged.update(env)
    config_dir = merged.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        Path(config_dir).expanduser().mkdir(parents=True, exist_ok=True)
    return merged


def _auth_json_ok(data: Any) -> bool | None:
    if not isinstance(data, dict):
        return None
    for key in ("authenticated", "loggedIn", "isLoggedIn", "logged_in", "ok"):
        if key in data:
            return bool(data[key])
    state = str(data.get("status") or data.get("state") or "").strip().lower()
    if state in {"authenticated", "logged_in", "loggedin", "ready", "ok"}:
        return True
    if state in {"unauthenticated", "not_logged_in", "not_loggedin", "missing", "failed"}:
        return False
    return None


def refresh_status(
    *,
    env: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Check Claude auth and write reports/run_status/claude-auth.json."""
    try:
        from scripts.llm_client import check_auth
    except ImportError:
        from llm_client import check_auth

    sdk_ok, source = check_auth("claude_agent")
    if sdk_ok:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": True,
            "state": "authenticated",
            "message": source,
            "checked_at": _now(),
            "command": STATUS_COMMAND,
        })

    try:
        result = runner(
            STATUS_COMMAND,
            cwd=str(REPO),
            env=_runtime_env(env),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "missing_cli",
            "message": "`claude` CLI not found in this runtime",
            "checked_at": _now(),
            "command": STATUS_COMMAND,
        })
    except subprocess.TimeoutExpired:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "status_timeout",
            "message": "`claude auth status --json` timed out",
            "checked_at": _now(),
            "command": STATUS_COMMAND,
        })

    parsed = None
    stdout = (result.stdout or "").strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    auth_ok = _auth_json_ok(parsed)
    if auth_ok is None:
        auth_ok = result.returncode == 0 and bool(stdout)

    state = "authenticated" if auth_ok else "unauthenticated"
    message = source if not auth_ok else "claude auth status is ready"
    if not auth_ok and (result.stderr or stdout):
        message = (result.stderr or stdout).strip().splitlines()[-1]
    return _write_json(AUTH_STATUS_PATH, {
        "ok": bool(auth_ok),
        "state": state,
        "message": message,
        "checked_at": _now(),
        "command": STATUS_COMMAND,
        "returncode": result.returncode,
        "raw": parsed if isinstance(parsed, dict) else None,
    })


def start_login(
    *,
    env: dict[str, str] | None = None,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> dict[str, Any]:
    """Start `claude auth login` and stream output to claude-auth.log."""
    RUN_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with AUTH_LOG_PATH.open("ab") as log:
            log.write(f"\n[{_now()}] $ {' '.join(LOGIN_COMMAND)}\n".encode("utf-8"))
            log.flush()
            proc = popen(
                LOGIN_COMMAND,
                cwd=str(REPO),
                env=_runtime_env(env),
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
            _LOGIN_PROCS[int(proc.pid)] = proc
    except FileNotFoundError:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "missing_cli",
            "message": "`claude` CLI not found in this runtime",
            "checked_at": _now(),
            "command": LOGIN_COMMAND,
            "log_path": str(AUTH_LOG_PATH),
        })

    return _write_json(AUTH_STATUS_PATH, {
        "ok": False,
        "state": "login_started",
        "message": "Claude login started; follow the URL or code in claude-auth.log",
        "checked_at": _now(),
        "pid": proc.pid,
        "command": LOGIN_COMMAND,
        "log_path": str(AUTH_LOG_PATH),
    })


def submit_login_code(code: str, *, pid: int | None = None) -> dict[str, Any]:
    """Submit the one-time browser auth code to the active Claude login process."""
    cleaned = (code or "").strip()
    if not cleaned:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "login_code_missing",
            "message": "Authentication code is required",
            "checked_at": _now(),
            "command": LOGIN_COMMAND,
        })

    if pid is None:
        current = _read_json(AUTH_STATUS_PATH) or {}
        raw_pid = current.get("pid")
        pid = int(raw_pid) if str(raw_pid or "").isdigit() else None

    proc = _LOGIN_PROCS.get(int(pid)) if pid is not None else None
    if proc is None or getattr(proc, "stdin", None) is None:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "login_session_missing",
            "message": "Login session expired; start Claude login again",
            "checked_at": _now(),
            "command": LOGIN_COMMAND,
        })

    if proc.poll() is not None:
        _LOGIN_PROCS.pop(int(pid), None)
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "login_session_closed",
            "message": "Login session closed; start Claude login again",
            "checked_at": _now(),
            "pid": pid,
            "command": LOGIN_COMMAND,
        })

    try:
        proc.stdin.write(cleaned + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError, ValueError) as e:
        return _write_json(AUTH_STATUS_PATH, {
            "ok": False,
            "state": "login_code_submit_failed",
            "message": str(e),
            "checked_at": _now(),
            "pid": pid,
            "command": LOGIN_COMMAND,
        })

    return _write_json(AUTH_STATUS_PATH, {
        "ok": False,
        "state": "login_code_submitted",
        "message": "Authentication code submitted; checking Claude login",
        "checked_at": _now(),
        "pid": pid,
        "command": LOGIN_COMMAND,
        "log_path": str(AUTH_LOG_PATH),
    })


def write_pending_request(params: dict[str, Any]) -> dict[str, Any]:
    return _write_json(PENDING_REQUEST_PATH, {
        "created_at": _now(),
        "resume_after_auth": True,
        "params": params,
    })


def read_pending_request() -> dict[str, Any] | None:
    return _read_json(PENDING_REQUEST_PATH)


def clear_pending_request() -> None:
    try:
        PENDING_REQUEST_PATH.unlink()
    except FileNotFoundError:
        pass
