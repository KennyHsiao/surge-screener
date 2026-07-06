#!/usr/bin/env python3
"""Self-contained tests for the Agent Reach social bridge."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "agent_reach_social_bridge_under_test",
        ROOT / "scripts" / "agent_reach_social_bridge.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_load_credentials_reads_agent_reach_config_without_env_flags() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        config = Path(d) / "config.yaml"
        config.write_text(
            "twitter_auth_token: auth-secret\n"
            "twitter_ct0: csrf-secret\n",
            encoding="utf-8",
        )

        creds = mod.load_credentials(config_path=config, env={})

        if creds != {"auth_token": "auth-secret", "ct0": "csrf-secret"}:
            raise AssertionError(creds)


def test_run_twitter_injects_saved_credentials_into_child_env() -> None:
    mod = _load_module()
    seen: dict[str, str] = {}

    def fake_runner(argv, **kwargs):  # noqa: ANN001
        seen["argv"] = " ".join(argv)
        seen["auth"] = kwargs["env"].get("TWITTER_AUTH_TOKEN", "")
        seen["ct0"] = kwargs["env"].get("TWITTER_CT0", "")
        return subprocess.CompletedProcess(argv, 0, stdout="ok: true\n", stderr="")

    result = mod.run_twitter(
        ["status"],
        credentials={"auth_token": "auth-secret", "ct0": "csrf-secret"},
        twitter_bin="twitter",
        runner=fake_runner,
        env={},
        timeout=3,
    )

    if result.returncode != 0:
        raise AssertionError(result)
    if seen != {"argv": "twitter status", "auth": "auth-secret", "ct0": "csrf-secret"}:
        raise AssertionError(seen)


def test_collect_tickers_parses_twitter_output_as_agent_reach_json() -> None:
    mod = _load_module()

    def fake_runner(argv, **kwargs):  # noqa: ANN001
        if argv[1] != "user-posts":
            raise AssertionError(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="Watching $NVDA and AMD. https://x.com/alpha/status/1\n",
            stderr="",
        )

    payload = mod.build_agent_reach_payload(
        handles=["alpha"],
        credentials={"auth_token": "auth-secret", "ct0": "csrf-secret"},
        twitter_bin="twitter",
        runner=fake_runner,
        env={},
        limit_per_handle=5,
    )

    if payload["status"] != "available":
        raise AssertionError(payload)
    by_ticker = {row["ticker"]: row for row in payload["tickers"]}
    if set(by_ticker) != {"AMD", "NVDA"}:
        raise AssertionError(payload)
    if by_ticker["NVDA"]["mentioned_by"] != ["alpha"]:
        raise AssertionError(payload)
    if by_ticker["NVDA"]["citations"] != ["https://x.com/alpha/status/1"]:
        raise AssertionError(payload)


def test_missing_credentials_degrades_without_running_twitter() -> None:
    mod = _load_module()

    def fake_runner(argv, **kwargs):  # noqa: ANN001
        raise AssertionError("twitter must not run without credentials")

    payload = mod.build_agent_reach_payload(
        handles=["alpha"],
        credentials={},
        twitter_bin="twitter",
        runner=fake_runner,
        env={},
    )

    if payload["status"] != "degraded":
        raise AssertionError(payload)
    if payload["tickers"] != []:
        raise AssertionError(payload)


def test_fetch_user_posts_payload_degrades_when_twitter_cli_missing() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        missing_bin = str(Path(d) / "missing-twitter")

        payload = mod.fetch_user_posts_payload(
            "alpha",
            credentials={"auth_token": "auth-secret", "ct0": "csrf-secret"},
            twitter_bin=missing_bin,
            env={},
        )

    if payload["status"] != "degraded":
        raise AssertionError(payload)
    if payload.get("auth_status") != "configured":
        raise AssertionError(payload)
    if payload.get("tool_status") != "missing":
        raise AssertionError(payload)
    if "twitter-cli" not in payload.get("note", ""):
        raise AssertionError(payload)


def test_fetch_user_posts_payload_parses_json_output() -> None:
    mod = _load_module()

    def fake_runner(argv, **kwargs):  # noqa: ANN001
        if argv[1:3] != ["user-posts", "@alpha"]:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({
                "posts": [
                    {
                        "text": "Watching $NVDA",
                        "created_at": "2026-07-06T01:00:00Z",
                        "url": "https://x.com/alpha/status/1",
                        "likes": 12,
                        "retweets": 3,
                    }
                ]
            }),
            stderr="",
        )

    payload = mod.fetch_user_posts_payload(
        "alpha",
        credentials={"auth_token": "auth-secret", "ct0": "csrf-secret"},
        twitter_bin="twitter",
        runner=fake_runner,
        env={},
        limit=5,
    )

    if payload["status"] != "available" or payload["source"] != "agent_reach":
        raise AssertionError(payload)
    post = payload["posts"][0]
    if post["text"] != "Watching $NVDA" or post["url"] != "https://x.com/alpha/status/1":
        raise AssertionError(payload)
    if post["likes"] != 12 or post["retweets"] != 3:
        raise AssertionError(payload)


def test_fetch_user_posts_payload_degrades_without_credentials() -> None:
    mod = _load_module()

    def fake_runner(argv, **kwargs):  # noqa: ANN001
        raise AssertionError("twitter must not run without credentials")

    payload = mod.fetch_user_posts_payload(
        "alpha",
        credentials={},
        twitter_bin="twitter",
        runner=fake_runner,
        env={},
    )

    if payload["status"] != "degraded":
        raise AssertionError(payload)
    if payload["posts"] != []:
        raise AssertionError(payload)


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
