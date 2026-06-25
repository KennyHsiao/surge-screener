#!/usr/bin/env python3
"""Self-contained tests for LLMClient.chat_agentic's web-only boundary (no network).

chat_agentic is the ONE scoped exception to the verified-data-to-AI tools=[]
guarantee, so its boundary must be fail-closed at every layer (the market-thesis
hard gate, docs/market_thesis_plan.md "Tier 2"): caller whitelist, structural
tool surface (tools=web list + strict_mcp_config), non-prompting permission mode,
and a deny-by-default can_use_tool gate. These tests intercept the Agent SDK
query() call to verify each layer without ever reaching the network.

Run:  .venv/bin/python scripts/test_llm_client_agentic.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import llm_client  # noqa: E402


def _client() -> "llm_client.LLMClient":
    c = llm_client.LLMClient.__new__(llm_client.LLMClient)
    c.provider = "claude_agent"
    c.model = "claude-opus-4-8"
    c.timeout = 10
    return c


def _run_agentic_capturing_options(c):
    """Call chat_agentic with the SDK's query() replaced by a recorder.

    The fake query yields nothing → chat_agentic returns "" — we only care about
    the ClaudeAgentOptions it was constructed with."""
    import claude_agent_sdk as sdk
    captured = {}
    orig = sdk.query

    async def fake_query(*, prompt, options):
        captured["options"] = options
        if False:  # pragma: no cover — make this an async generator
            yield None

    sdk.query = fake_query
    try:
        out = c.chat_agentic("system", "user")
    finally:
        sdk.query = orig
    return out, captured["options"]


def test_non_web_allowed_tools_rejected():
    """Caller-supplied non-web tools must be rejected BEFORE any SDK call —
    the whitelist is enforced, not a default."""
    c = _client()
    for bad in [("Bash",), ("WebSearch", "Skill"), ("Read", "WebFetch")]:
        try:
            c.chat_agentic("s", "u", allowed_tools=bad)
            raise AssertionError(f"non-web allowed_tools accepted: {bad}")
        except ValueError as e:
            assert "web-only" in str(e), e


def test_requires_claude_agent_backend():
    """API/CI providers keep the strict tools=[] completion — agentic is local-only."""
    c = _client()
    c.provider = "anthropic"
    try:
        c.chat_agentic("s", "u")
        raise AssertionError("non-claude_agent provider accepted")
    except RuntimeError as e:
        assert "claude_agent" in str(e), e


def test_retry_max_attempts_is_configurable():
    """Layer-1 local scoring can choose one attempt per ticker, so a slow ticker
    can be deferred instead of blocking the whole batch through three long waits."""
    c = _client()
    c.retry_max_attempts = 1
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise RuntimeError("timeout")

    try:
        c._with_retry(fail)
        raise AssertionError("expected retry exhaustion")
    except RuntimeError:
        pass
    assert calls["n"] == 1, calls


def test_options_are_structurally_web_only():
    """The registered tool surface itself must be the web list (not just
    auto-permission), MCP config locked, permission mode non-prompting."""
    c = _client()
    out, opts = _run_agentic_capturing_options(c)
    assert out == "", out
    assert list(opts.tools) == ["WebSearch", "WebFetch"], opts.tools
    assert opts.strict_mcp_config is True
    assert opts.permission_mode == "dontAsk", opts.permission_mode
    assert opts.can_use_tool is not None


def test_permission_gate_denies_non_web_tool():
    """The can_use_tool callback is deny-by-default: any tool name outside the
    web whitelist is denied by name; the web tools are allowed."""
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
    c = _client()
    _, opts = _run_agentic_capturing_options(c)
    gate = opts.can_use_tool
    for tool in ["Bash", "Edit", "Write", "Read", "Glob", "Task", "mcp__ibkr__authenticate",
                 "SomeFutureSdkTool"]:
        res = asyncio.run(gate(tool, {}, None))
        assert isinstance(res, PermissionResultDeny), (tool, res)
    for tool in ["WebSearch", "WebFetch"]:
        res = asyncio.run(gate(tool, {}, None))
        assert isinstance(res, PermissionResultAllow), (tool, res)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            t()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
