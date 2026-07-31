#!/usr/bin/env python3
"""Offline tests for the Codex ChatGPT device-auth helper."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "codex_auth_flow_under_test",
        ROOT / "scripts" / "codex_auth_flow.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load codex_auth_flow")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _isolated(module, root: Path) -> None:
    module.REPO = root
    module.RUN_STATUS_DIR = root / "run_status"
    module.AUTH_STATUS_PATH = module.RUN_STATUS_DIR / "codex-auth.json"
    module.AUTH_LOG_PATH = module.RUN_STATUS_DIR / "codex-auth.log"
    module.PENDING_REQUEST_PATH = module.RUN_STATUS_DIR / "codex-auth-pending.json"


def test_runtime_env_persists_codex_home_and_removes_api_key() -> None:
    module = _load()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = module._runtime_env(
            {
                "SURGE_APP_ROOT": str(root),
                "PATH": "/usr/bin",
                "OPENAI_API_KEY": "must-not-reach-codex",
            }
        )
        if env.get("CODEX_HOME") != str(root / ".codex"):
            raise AssertionError(env)
        if not (root / ".codex").is_dir():
            raise AssertionError("CODEX_HOME was not created")
        if "OPENAI_API_KEY" in env:
            raise AssertionError("metered API key leaked into Codex runtime")
        if env["PATH"].split(os.pathsep)[0] != str(root / ".venv" / "bin"):
            raise AssertionError(env["PATH"])


def test_refresh_status_accepts_only_chatgpt_cli_status() -> None:
    module = _load()
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(module, Path(tmp))

        def fake_check_auth(_provider, **_kwargs):
            return False, "missing"

        good = subprocess.CompletedProcess(
            ["codex", "login", "status"],
            0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        )
        with (
            patch("scripts.llm_client.check_auth", side_effect=fake_check_auth),
            patch.object(module, "_command", return_value=["codex", "login", "status"]),
        ):
            status = module.refresh_status(runner=lambda *_args, **_kwargs: good)
        if status["ok"] is not True or status["auth_mode"] != "chatgpt":
            raise AssertionError(status)

        api_key = subprocess.CompletedProcess(
            ["codex", "login", "status"],
            0,
            stdout="Logged in using an API key\n",
            stderr="",
        )
        with (
            patch("scripts.llm_client.check_auth", side_effect=fake_check_auth),
            patch.object(module, "_command", return_value=["codex", "login", "status"]),
        ):
            status = module.refresh_status(runner=lambda *_args, **_kwargs: api_key)
        if status["ok"] is not False or status["state"] != "unauthenticated":
            raise AssertionError(status)


def test_device_login_uses_bundled_command_and_no_stdin() -> None:
    module = _load()
    captured = {}

    class FakeProc:
        pid = 321

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeProc()

    with tempfile.TemporaryDirectory() as tmp:
        _isolated(module, Path(tmp))
        with patch.object(
            module,
            "_command",
            return_value=["/runtime/codex", "login", "--device-auth"],
        ):
            status = module.start_login(popen=fake_popen)

    if captured["command"][-2:] != ["login", "--device-auth"]:
        raise AssertionError(captured)
    if captured["stdin"] is not subprocess.DEVNULL:
        raise AssertionError(captured)
    if status["state"] != "login_started" or status["pid"] != 321:
        raise AssertionError(status)


def test_login_prompt_extracts_url_and_device_code() -> None:
    module = _load()
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(module, Path(tmp))
        module.RUN_STATUS_DIR.mkdir(parents=True)
        module.AUTH_LOG_PATH.write_text(
            "Open https://auth.openai.com/codex/device\n"
            "Enter code ABCD-EFGH\n",
            encoding="utf-8",
        )
        prompt = module.read_login_prompt()
    if prompt != {
        "auth_url": "https://auth.openai.com/codex/device",
        "user_code": "ABCD-EFGH",
    }:
        raise AssertionError(prompt)


def test_pending_request_roundtrip() -> None:
    module = _load()
    with tempfile.TemporaryDirectory() as tmp:
        _isolated(module, Path(tmp))
        module.write_pending_request({"mode": "llm_deep_check", "limit": 3})
        pending = module.read_pending_request()
        if pending is None or pending["params"]["limit"] != 3:
            raise AssertionError(pending)
        module.clear_pending_request()
        if module.read_pending_request() is not None:
            raise AssertionError("pending request was not removed")


def main() -> None:
    tests = [
        test_runtime_env_persists_codex_home_and_removes_api_key,
        test_refresh_status_accepts_only_chatgpt_cli_status,
        test_device_login_uses_bundled_command_and_no_stdin,
        test_login_prompt_extracts_url_and_device_code,
        test_pending_request_roundtrip,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    main()
