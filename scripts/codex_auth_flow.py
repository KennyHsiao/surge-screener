#!/usr/bin/env python3
"""Codex ChatGPT-login helpers for Streamlit-triggered LLM workflows."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
RUN_STATUS_DIR = REPO / "reports" / "run_status"
AUTH_STATUS_PATH = RUN_STATUS_DIR / "codex-auth.json"
AUTH_LOG_PATH = RUN_STATUS_DIR / "codex-auth.log"
PENDING_REQUEST_PATH = RUN_STATUS_DIR / "codex-auth-pending.json"
LOGIN_ARGS = ("login", "--device-auth")
STATUS_ARGS = ("login", "status")
_LOGIN_PROCS: dict[int, subprocess.Popen] = {}
_URL_RE = re.compile(r"https://[^\s\x1b]+")
_CODE_RE = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+\b", re.IGNORECASE)


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
    merged = dict(os.environ)
    if env:
        merged.update(env)
    app_root = merged.get("SURGE_APP_ROOT")
    if app_root:
        root = Path(app_root).expanduser()
        merged.setdefault("CODEX_HOME", str(root / ".codex"))
        venv_bin = str(root / ".venv" / "bin")
        existing = merged.get("PATH") or os.defpath
        parts = [part for part in existing.split(os.pathsep) if part]
        merged["PATH"] = os.pathsep.join(
            [venv_bin, *[part for part in parts if part != venv_bin]]
        )
    codex_home = merged.get("CODEX_HOME")
    if codex_home:
        Path(codex_home).expanduser().mkdir(parents=True, exist_ok=True)
    # Subscription-only invariant: never pass a metered Platform key to Codex.
    merged.pop("OPENAI_API_KEY", None)
    return merged


def _bundled_codex_path() -> str | None:
    try:
        from codex_cli_bin import bundled_codex_path
    except ImportError:
        return None
    path = Path(bundled_codex_path())
    return str(path) if path.is_file() else None


def _command(args: tuple[str, ...], env: dict[str, str]) -> list[str]:
    executable = shutil.which("codex", path=env.get("PATH"))
    executable = executable or _bundled_codex_path()
    if not executable:
        raise FileNotFoundError("Codex CLI runtime not found")
    return [executable, *args]


def _subscription_status_ok(result: subprocess.CompletedProcess) -> bool:
    text = f"{result.stdout or ''}\n{result.stderr or ''}".strip().lower()
    return result.returncode == 0 and "logged in using chatgpt" in text


def read_login_prompt() -> dict[str, str | None]:
    """Return the current device-login URL and one-time code from the safe log."""
    try:
        text = AUTH_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"auth_url": None, "user_code": None}
    urls = _URL_RE.findall(text)
    codes = _CODE_RE.findall(text)
    return {
        "auth_url": urls[-1].rstrip(".,)") if urls else None,
        "user_code": codes[-1].upper() if codes else None,
    }


def refresh_status(
    *,
    env: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Check SDK/CLI auth and persist a sanitized subscription status."""
    try:
        from scripts.llm_client import check_auth
    except ImportError:
        from llm_client import check_auth

    runtime_env = _runtime_env(env)
    sdk_ok, source = check_auth("codex", env=runtime_env)
    if sdk_ok:
        return _write_json(
            AUTH_STATUS_PATH,
            {
                "ok": True,
                "state": "authenticated",
                "message": source,
                "checked_at": _now(),
                "auth_mode": "chatgpt",
            },
        )

    try:
        command = _command(STATUS_ARGS, runtime_env)
        result = runner(
            command,
            cwd=str(REPO),
            env=runtime_env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        return _write_json(
            AUTH_STATUS_PATH,
            {
                "ok": False,
                "state": "missing_cli",
                "message": "Codex SDK/CLI runtime is not installed",
                "checked_at": _now(),
            },
        )
    except subprocess.TimeoutExpired:
        return _write_json(
            AUTH_STATUS_PATH,
            {
                "ok": False,
                "state": "status_timeout",
                "message": "`codex login status` timed out",
                "checked_at": _now(),
            },
        )

    ok = _subscription_status_ok(result)
    prompt = read_login_prompt()
    return _write_json(
        AUTH_STATUS_PATH,
        {
            "ok": ok,
            "state": "authenticated" if ok else "unauthenticated",
            "message": (
                "Codex ChatGPT subscription login is ready"
                if ok
                else "Codex is not logged in with ChatGPT subscription access"
            ),
            "checked_at": _now(),
            "auth_mode": "chatgpt" if ok else None,
            "returncode": result.returncode,
            **prompt,
        },
    )


def start_login(
    *,
    env: dict[str, str] | None = None,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> dict[str, Any]:
    """Start the headless-safe ChatGPT device login and stream its prompt to a log."""
    RUN_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_env = _runtime_env(env)
    try:
        command = _command(LOGIN_ARGS, runtime_env)
        with AUTH_LOG_PATH.open("ab") as log:
            log.write(f"\n[{_now()}] Codex ChatGPT device login\n".encode("utf-8"))
            log.flush()
            proc = popen(
                command,
                cwd=str(REPO),
                env=runtime_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _LOGIN_PROCS[int(proc.pid)] = proc
    except FileNotFoundError:
        return _write_json(
            AUTH_STATUS_PATH,
            {
                "ok": False,
                "state": "missing_cli",
                "message": "Codex SDK/CLI runtime is not installed",
                "checked_at": _now(),
                "log_path": str(AUTH_LOG_PATH),
            },
        )

    return _write_json(
        AUTH_STATUS_PATH,
        {
            "ok": False,
            "state": "login_started",
            "message": "Codex device login started; follow the URL and code shown below",
            "checked_at": _now(),
            "pid": proc.pid,
            "log_path": str(AUTH_LOG_PATH),
            **read_login_prompt(),
        },
    )


def write_pending_request(params: dict[str, Any]) -> dict[str, Any]:
    return _write_json(
        PENDING_REQUEST_PATH,
        {
            "created_at": _now(),
            "resume_after_auth": True,
            "params": params,
        },
    )


def read_pending_request() -> dict[str, Any] | None:
    return _read_json(PENDING_REQUEST_PATH)


def clear_pending_request() -> None:
    try:
        PENDING_REQUEST_PATH.unlink()
    except FileNotFoundError:
        pass
