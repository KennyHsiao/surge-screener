#!/usr/bin/env python3
"""Offline contract tests for the subscription-only Codex LLM adapter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import llm_client  # noqa: E402


class FakeApprovalMode:
    deny_all = "deny_all"


class FakeSandbox:
    read_only = "read_only"


@dataclass
class FakeResult:
    final_response: str


class FakeTurn:
    def __init__(self, outcome):
        self.outcome = outcome
        self.interrupted = False

    def run(self):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return FakeResult(self.outcome)

    def interrupt(self):
        self.interrupted = True


class FakeThread:
    def __init__(self, codex):
        self.codex = codex

    def turn(self, user):
        self.codex.user = user
        turn = FakeTurn(self.codex.outcome)
        self.codex.turn_handle = turn
        return turn


class FakeCodex:
    def __init__(self, outcome="OK", account_type="chatgpt", plan="plus"):
        self.outcome = outcome
        self.account_type = account_type
        self.plan = plan
        self.thread_kwargs = None
        self.user = None
        self.turn_handle = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()

    def close(self):
        self.closed = True

    def account(self):
        plan_type = SimpleNamespace(value=self.plan)
        root = SimpleNamespace(type=self.account_type, plan_type=plan_type)
        return SimpleNamespace(account=SimpleNamespace(root=root))

    def thread_start(self, **kwargs):
        self.thread_kwargs = kwargs
        return FakeThread(self)


def _client(codex: FakeCodex, **kwargs) -> llm_client.LLMClient:
    return llm_client.LLMClient(
        provider="codex",
        codex_factory=lambda: codex,
        retry_max_attempts=kwargs.pop("retry_max_attempts", 1),
        **kwargs,
    )


def _fake_sdk():
    return object(), object(), FakeApprovalMode, FakeSandbox


def test_plain_chat_uses_subscription_safe_thread_options() -> None:
    codex = FakeCodex("answer")
    with patch.object(llm_client, "_sdk", side_effect=_fake_sdk):
        answer = _client(codex).chat("system rules", "question", max_tokens=20)

    if answer != "answer" or codex.user != "question":
        raise AssertionError((answer, codex.user))
    options = codex.thread_kwargs
    if options["approval_mode"] != "deny_all" or options["sandbox"] != "read_only":
        raise AssertionError(options)
    if options["config"]["web_search"] != "disabled":
        raise AssertionError(options)
    expected_disabled_features = {
        "apps",
        "goals",
        "hooks",
        "multi_agent",
        "remote_plugin",
        "shell_snapshot",
        "shell_tool",
    }
    features = options["config"]["features"]
    if set(features) != expected_disabled_features or any(features.values()):
        raise AssertionError(options)
    if Path(options["cwd"]) == ROOT or not Path(options["cwd"]).name.startswith("surge-codex-"):
        raise AssertionError(options)
    if options["ephemeral"] is not True or options["model"] is not None:
        raise AssertionError(options)
    instructions = options["developer_instructions"]
    if "Do not use web search" not in instructions or "system rules" not in instructions:
        raise AssertionError(instructions)


def test_agentic_chat_enables_only_codex_web_search_mode() -> None:
    codex = FakeCodex("researched")
    with patch.object(llm_client, "_sdk", side_effect=_fake_sdk):
        answer = _client(codex).chat_agentic("system", "current question")

    if answer != "researched":
        raise AssertionError(answer)
    options = codex.thread_kwargs
    if options["config"]["web_search"] != "cached":
        raise AssertionError(options)
    if options["sandbox"] != "read_only" or options["approval_mode"] != "deny_all":
        raise AssertionError(options)


def test_non_web_agentic_tool_is_rejected_before_sdk_call() -> None:
    codex = FakeCodex()
    client = _client(codex)
    try:
        client.chat_agentic("s", "u", allowed_tools=("Bash",))
    except ValueError as exc:
        if "web-only" not in str(exc):
            raise
    else:
        raise AssertionError("accepted a non-web tool")
    if codex.thread_kwargs is not None:
        raise AssertionError("Codex was called before tool validation")


def test_api_key_account_is_rejected_without_model_turn() -> None:
    codex = FakeCodex(account_type="apiKey")
    with patch.object(llm_client, "_sdk", side_effect=_fake_sdk):
        try:
            _client(codex).chat("s", "u")
        except llm_client.LLMAuthenticationError as exc:
            if "ChatGPT subscription" not in str(exc):
                raise
        else:
            raise AssertionError("API-key account was accepted")
    if codex.thread_kwargs is not None:
        raise AssertionError("model turn started before account validation")


def test_output_character_cap_is_enforced() -> None:
    codex = FakeCodex("x" * 4097)
    with patch.object(llm_client, "_sdk", side_effect=_fake_sdk):
        try:
            _client(codex).chat("s", "u", max_tokens=1)
        except llm_client.LLMOutputLimitError:
            pass
        else:
            raise AssertionError("oversized Codex output was accepted")


def test_check_auth_accepts_chatgpt_and_rejects_api_key() -> None:
    ok, detail = llm_client.check_auth(
        codex_factory=lambda: FakeCodex(account_type="chatgpt", plan="pro")
    )
    if not ok or "pro" not in detail:
        raise AssertionError((ok, detail))

    ok, detail = llm_client.check_auth(
        codex_factory=lambda: FakeCodex(account_type="apiKey")
    )
    if ok or "ChatGPT subscription" not in detail:
        raise AssertionError((ok, detail))


def test_legacy_provider_names_fail_closed() -> None:
    for provider in ("anthropic", "claude_agent", "openai", "deepseek"):
        try:
            llm_client.resolve_provider(provider)
        except ValueError as exc:
            if "all platform LLM calls use 'codex'" not in str(exc):
                raise
        else:
            raise AssertionError(f"legacy provider accepted: {provider}")


def main() -> None:
    tests = [
        test_plain_chat_uses_subscription_safe_thread_options,
        test_agentic_chat_enables_only_codex_web_search_mode,
        test_non_web_agentic_tool_is_rejected_before_sdk_call,
        test_api_key_account_is_rejected_without_model_turn,
        test_output_character_cap_is_enforced,
        test_check_auth_accepts_chatgpt_and_rejects_api_key,
        test_legacy_provider_names_fail_closed,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    main()
