#!/usr/bin/env python3
"""Shared LLM client for the surge-screener pipeline.

One ``chat(system, user)`` interface, several interchangeable backends:

  claude_agent  Claude Agent SDK (``claude_agent_sdk.query``). Bills against the
                logged-in Claude Code subscription (Max/Pro) — no API key. Uses
                the OAuth credentials from `claude` login (macOS Keychain) or the
                ``CLAUDE_CODE_OAUTH_TOKEN`` env var. Each call runs as a single
                no-tool turn, so it behaves like a plain completion: same
                text-in / JSON-out contract as the old Messages-API path, which
                keeps the existing prompts and ``_extract_json`` helpers working.
  anthropic     Anthropic Messages API (``anthropic.Anthropic``). Needs
                ANTHROPIC_API_KEY; billed per token.
  openai        OpenAI-compatible chat completions.
  deepseek      DeepSeek chat completions (OpenAI-compatible).

Provider "auto" (the default) resolves the same way the Agent SDK resolves its
own auth precedence: use ``anthropic`` when ANTHROPIC_API_KEY is present (e.g. in
GitHub Actions), otherwise ``claude_agent`` (local/manual runs on a Max plan).
That way the CI workflow keeps using the API key and local runs draw on the
subscription, with no per-script or workflow changes — pass ``--provider`` only
when you want to force a specific backend.
"""

from __future__ import annotations

import os
import sys

PROVIDERS = ("auto", "claude_agent", "anthropic", "openai", "deepseek")

# Default wall-clock cap for a single claude_agent call. The Agent SDK has no
# max-output-tokens option, so a runaway/looping response could otherwise burn
# subscription quota indefinitely; this bounds it like the API backends' HTTP
# timeout did. Override per-client via LLMClient(timeout=...).
DEFAULT_AGENT_TIMEOUT = 180.0


def resolve_provider(provider: str | None) -> str:
    """Map the requested provider onto a concrete backend.

    "auto" → ``anthropic`` if an API key is set (CI), else ``claude_agent``
    (subscription). Anything explicit is honoured as-is.
    """
    if provider and provider != "auto":
        return provider
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "claude_agent"


class LLMClient:
    """Unified LLM caller. ``provider`` defaults to "auto" (see module docstring)."""

    def __init__(self, provider: str = "auto", model: str = "claude-opus-4-7",
                 timeout: float = DEFAULT_AGENT_TIMEOUT):
        self.requested_provider = provider
        self.provider = resolve_provider(provider)
        self.model = model
        self.timeout = timeout
        # Make the resolved backend explicit (auto-detection is otherwise silent —
        # this is how you confirm a run is on the subscription vs the paid API).
        print(f"[llm_client] provider={self.provider} (requested={provider}) "
              f"model={self.model}", file=sys.stderr)

        if self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic()
        elif self.provider == "claude_agent":
            try:
                import claude_agent_sdk  # noqa: F401  — fail fast if missing
            except ImportError as e:  # pragma: no cover - environment guard
                raise RuntimeError(
                    "provider 'claude_agent' requires the Claude Agent SDK. "
                    "Install it with `pip install claude-agent-sdk`, and make sure "
                    "`claude` is logged in (Max/Pro) or CLAUDE_CODE_OAUTH_TOKEN is set."
                ) from e
        elif self.provider in ("openai", "deepseek"):
            if self.provider == "deepseek":
                self._api_key = os.environ.get("DEEPSEEK_API_KEY")
                self._base_url = "https://api.deepseek.com"
            else:
                self._api_key = os.environ.get("OPENAI_API_KEY")
                self._base_url = "https://api.openai.com/v1"
        else:
            raise ValueError(f"unknown provider: {self.provider}")

    # ------------------------------------------------------------------ #
    def chat(self, system: str, user: str, max_tokens: int = 8192) -> str:
        """Single-turn completion. Returns the raw assistant text.

        ``max_tokens`` bounds the output on every backend: the API backends pass
        it through natively; the Agent SDK backend (which has no such option)
        enforces it as an output character cap, plus a wall-clock ``timeout``, so
        a runaway response can't silently drain the subscription quota.
        """
        if self.provider == "claude_agent":
            return self._chat_claude_agent(system, user, max_tokens)
        if self.provider == "anthropic":
            return self._chat_anthropic(system, user, max_tokens)
        return self._chat_openai_compatible(system, user, max_tokens)

    # -- backends ------------------------------------------------------- #
    def _chat_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    def _chat_claude_agent(self, system: str, user: str, max_tokens: int) -> str:
        import asyncio

        def runner() -> str:
            return asyncio.run(self._chat_claude_agent_async(system, user, max_tokens))

        # asyncio.run() can't be called from inside a running loop (Streamlit,
        # notebooks); fall back to a worker thread when one is already running.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return runner()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(runner).result()

    async def _chat_claude_agent_async(self, system: str, user: str,
                                       max_tokens: int) -> str:
        import asyncio
        from claude_agent_sdk import (
            query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock,
        )

        options = ClaudeAgentOptions(
            system_prompt=system,
            # tools=[] registers an EMPTY tool set, so the model literally cannot
            # see or call Bash/WebSearch/Read/etc. (allowed_tools=[] only governs
            # auto-permission — it leaves the ~30 built-in tools exposed). This is
            # what makes the call a pure completion and preserves the
            # verified-data-to-AI guarantee: the model can't fetch its own data.
            tools=[],
            max_turns=1,
            model=self.model,
        )
        # ~4 chars/token is a generous upper bound; trip well before a runaway
        # response can rack up quota. Callers wrap chat() per item, so raising
        # here fails just that candidate and preserves partial progress.
        char_cap = max(4096, max_tokens * 4)
        parts: list[str] = []
        total = 0
        result_text: str | None = None

        async def _collect() -> None:
            nonlocal result_text, total
            async for message in query(prompt=user, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                            total += len(block.text)
                            if total > char_cap:
                                raise RuntimeError(
                                    f"claude_agent output exceeded {char_cap} chars "
                                    f"(max_tokens={max_tokens}) — aborting to protect quota")
                elif isinstance(message, ResultMessage):
                    result_text = message.result
                    if message.is_error:
                        raise RuntimeError(
                            f"claude_agent run failed: {message.result or 'unknown error'}")

        try:
            await asyncio.wait_for(_collect(), timeout=self.timeout)
        except asyncio.TimeoutError as e:
            raise RuntimeError(
                f"claude_agent call timed out after {self.timeout}s "
                f"(model={self.model})") from e
        return "".join(parts) or (result_text or "")

    def _chat_openai_compatible(self, system: str, user: str, max_tokens: int) -> str:
        import httpx
        resp = httpx.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------- #
# Preflight — surface the resolved backend + validate auth before expensive runs
# --------------------------------------------------------------------------- #
def check_auth(provider: str) -> tuple[bool, str]:
    """Return (ok, detail) for whether the resolved provider has usable creds."""
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY"
    if provider == "claude_agent":
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            return False, "claude-agent-sdk not installed"
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return True, "claude-agent-sdk + CLAUDE_CODE_OAUTH_TOKEN"
        return True, ("claude-agent-sdk present; relying on `claude` login "
                      "(Keychain) — ensure you are logged in")
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY"
    if provider == "deepseek":
        return bool(os.environ.get("DEEPSEEK_API_KEY")), "DEEPSEEK_API_KEY"
    return False, f"unknown provider {provider}"


def preflight(provider: str = "auto", model: str = "claude-opus-4-7") -> bool:
    """Print the resolved provider + auth status; return True if usable.

    Use as a cheap gate before any expensive pipeline stage (locally or as a CI
    step), so a run fails fast with a clear message instead of silently billing
    the wrong backend or dying mid-pipeline:

        python scripts/llm_client.py --provider auto
    """
    resolved = resolve_provider(provider)
    ok, detail = check_auth(resolved)
    print(f"[preflight] requested={provider} resolved={resolved} model={model}")
    print(f"[preflight] auth: {'OK' if ok else 'MISSING'} — {detail}")
    return ok


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Resolve and validate the LLM backend.")
    ap.add_argument("--provider", default="auto", choices=list(PROVIDERS))
    ap.add_argument("--model", default="claude-opus-4-7")
    args = ap.parse_args()
    sys.exit(0 if preflight(args.provider, args.model) else 1)
