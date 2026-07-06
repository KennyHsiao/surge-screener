#!/usr/bin/env python3
"""Self-contained tests for Agent Reach X login/cookie update helpers."""

from __future__ import annotations

import importlib.util
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "agent_reach_auth_under_test",
        ROOT / "scripts" / "agent_reach_auth.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_extract_x_credentials_accepts_x_and_twitter_domains() -> None:
    mod = _load_module()

    creds = mod.extract_x_credentials([
        {"name": "auth_token", "value": "auth-secret", "domain": ".twitter.com"},
        {"name": "ct0", "value": "csrf-secret", "domain": ".x.com"},
        {"name": "auth_token", "value": "evil", "domain": "example.com"},
    ])

    if creds != {"auth_token": "auth-secret", "ct0": "csrf-secret"}:
        raise AssertionError(creds)


def test_write_agent_reach_config_updates_tokens_atomically_and_private() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        config = Path(d) / ".agent-reach" / "config.yaml"
        config.parent.mkdir()
        config.write_text("other_key: keep-me\n", encoding="utf-8")

        result = mod.write_agent_reach_config(
            {"auth_token": "auth-secret", "ct0": "csrf-secret"},
            config_path=config,
        )

        text = config.read_text(encoding="utf-8")
        if "other_key: keep-me" not in text:
            raise AssertionError(text)
        if "twitter_auth_token: auth-secret" not in text:
            raise AssertionError(text)
        if "twitter_ct0: csrf-secret" not in text:
            raise AssertionError(text)
        mode = stat.S_IMODE(config.stat().st_mode)
        if mode != 0o600:
            raise AssertionError(oct(mode))
        if "auth-secret" in str(result) or "csrf-secret" in str(result):
            raise AssertionError(result)


def test_config_status_redacts_existing_credentials() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        config = Path(d) / "config.yaml"
        config.write_text(
            "twitter_auth_token: auth-secret\n"
            "twitter_ct0: csrf-secret\n",
            encoding="utf-8",
        )

        status = mod.agent_reach_config_status(config_path=config)

        if not status["configured"]:
            raise AssertionError(status)
        if status["auth_token"] != "au...et" or status["ct0"] != "cs...et":
            raise AssertionError(status)
        if "auth-secret" in str(status) or "csrf-secret" in str(status):
            raise AssertionError(status)


def test_build_browser_command_uses_dedicated_profile_and_local_debugging() -> None:
    mod = _load_module()
    cmd = mod.build_browser_command(
        "/usr/bin/chromium",
        profile_dir=Path("/tmp/agent-reach-x-profile"),
        port=9229,
    )
    joined = " ".join(cmd)

    for needle in [
        "/usr/bin/chromium",
        "--user-data-dir=/tmp/agent-reach-x-profile",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=9229",
        "https://x.com/login",
    ]:
        if needle not in joined:
            raise AssertionError(cmd)


def test_select_cdp_ws_url_prefers_x_page_target() -> None:
    mod = _load_module()

    ws_url = mod.select_cdp_ws_url(
        [
            {
                "type": "page",
                "url": "https://example.com",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/page/1",
            },
            {
                "type": "page",
                "url": "https://x.com/login",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/page/2",
            },
        ],
        {"webSocketDebuggerUrl": "ws://127.0.0.1:9229/devtools/browser/1"},
    )

    if ws_url != "ws://127.0.0.1:9229/devtools/page/2":
        raise AssertionError(ws_url)


def test_start_login_session_degrades_without_browser() -> None:
    mod = _load_module()

    result = mod.start_login_session(
        env={},
        which=lambda _name: None,
        popen=lambda *_args, **_kwargs: None,
    )

    if result["status"] != "unavailable":
        raise AssertionError(result)
    if "auth_token" in str(result) or "ct0" in str(result):
        raise AssertionError(result)


def test_start_login_session_launches_browser_without_exposing_secrets() -> None:
    mod = _load_module()
    seen: dict[str, object] = {}

    class FakeProc:
        pid = 12345

    def fake_popen(argv, **kwargs):  # noqa: ANN001
        seen["argv"] = argv
        seen["env"] = kwargs.get("env", {})
        return FakeProc()

    with tempfile.TemporaryDirectory() as d:
        result = mod.start_login_session(
            profile_dir=Path(d) / "profile",
            state_path=Path(d) / "state.json",
            env={"DISPLAY": ":1", "TWITTER_AUTH_TOKEN": "must-not-leak"},
            which=lambda name: "/usr/bin/chromium" if name == "chromium" else None,
            popen=fake_popen,
        )

    if result["status"] != "running" or result["pid"] != 12345:
        raise AssertionError(result)
    if "TWITTER_AUTH_TOKEN" in seen.get("env", {}):
        raise AssertionError(seen)
    if "must-not-leak" in str(result) or "must-not-leak" in str(seen):
        raise AssertionError((result, seen))


def test_update_config_from_cookies_writes_config_without_returning_secrets() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        config = Path(d) / "config.yaml"

        result = mod.update_config_from_cookies(
            [
                {"name": "auth_token", "value": "auth-secret", "domain": ".x.com"},
                {"name": "ct0", "value": "csrf-secret", "domain": ".x.com"},
            ],
            config_path=config,
        )

        if result["status"] != "updated" or not result["configured"]:
            raise AssertionError(result)
        if "auth-secret" in str(result) or "csrf-secret" in str(result):
            raise AssertionError(result)
        written = config.read_text(encoding="utf-8")
        if "auth-secret" not in written or "csrf-secret" not in written:
            raise AssertionError(written)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
