#!/usr/bin/env python3
"""Unit tests for the Claude auth helper flow."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "claude_auth_flow_under_test",
        ROOT / "scripts" / "claude_auth_flow.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeStdin:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flushed = False

    def write(self, text: str) -> None:
        self.writes.append(text)

    def flush(self) -> None:
        self.flushed = True


class FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.stdin = FakeStdin()
        self._returncode = None

    def poll(self):
        return self._returncode


def _use_temp_paths(mod, d: str) -> None:
    run_dir = Path(d) / "run_status"
    mod.RUN_STATUS_DIR = run_dir
    mod.AUTH_STATUS_PATH = run_dir / "claude-auth.json"
    mod.AUTH_LOG_PATH = run_dir / "claude-auth.log"
    mod.PENDING_REQUEST_PATH = run_dir / "claude-auth-pending.json"


def test_start_login_keeps_stdin_pipe_for_auth_code_submit() -> None:
    mod = _load_module()
    proc = FakeProc()
    calls = []

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return proc

    with tempfile.TemporaryDirectory() as d:
        _use_temp_paths(mod, d)
        meta = mod.start_login(popen=fake_popen)
        result = mod.submit_login_code("abc-123", pid=meta["pid"])

    if calls[0][1].get("stdin") is not subprocess.PIPE:
        raise AssertionError(calls)
    if proc.stdin.writes != ["abc-123\n"] or not proc.stdin.flushed:
        raise AssertionError(proc.stdin.writes)
    if result["state"] != "login_code_submitted":
        raise AssertionError(result)


def test_submit_login_code_reports_missing_session() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _use_temp_paths(mod, d)
        result = mod.submit_login_code("abc-123", pid=9999)

    if result["state"] != "login_session_missing":
        raise AssertionError(result)


def test_runtime_env_uses_deployed_claude_cli_paths() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "surge-screener"
        env = mod._runtime_env({
            "SURGE_APP_ROOT": str(root),
            "PATH": os.defpath,
        })

        expected = [
            str(root / "node-global" / "bin"),
            str(root / "node" / "bin"),
        ]
        actual = env["PATH"].split(os.pathsep)[:2]
        if actual != expected:
            raise AssertionError(actual)
        if env.get("CLAUDE_CONFIG_DIR") != str(root / ".claude"):
            raise AssertionError(env.get("CLAUDE_CONFIG_DIR"))
        if not (root / ".claude").is_dir():
            raise AssertionError("CLAUDE_CONFIG_DIR was not created")


def test_refresh_status_summarizes_unauthenticated_json() -> None:
    mod = _load_module()
    import scripts.llm_client as llm_client

    original = llm_client.check_auth

    def fake_check_auth(provider: str):
        return False, "missing credentials"

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout='{\n  "loggedIn": false,\n  "authMethod": "none"\n}',
            stderr="",
        )

    try:
        llm_client.check_auth = fake_check_auth
        with tempfile.TemporaryDirectory() as d:
            _use_temp_paths(mod, d)
            result = mod.refresh_status(runner=fake_runner)
    finally:
        llm_client.check_auth = original

    if result["state"] != "unauthenticated":
        raise AssertionError(result)
    if result["message"] == "}" or "not logged in" not in result["message"]:
        raise AssertionError(result)


def main() -> None:
    tests = [
        test_start_login_keeps_stdin_pipe_for_auth_code_submit,
        test_submit_login_code_reports_missing_session,
        test_runtime_env_uses_deployed_claude_cli_paths,
        test_refresh_status_summarizes_unauthenticated_json,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
