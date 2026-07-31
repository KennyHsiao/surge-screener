#!/usr/bin/env python3
"""Tests for AI chat prompt construction and LLM routing.

Run:  .venv/bin/python scripts/test_ai_chat_assistant.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import ai_chat_assistant as chat  # noqa: E402


def test_available_context_detects_page_and_ticker_without_auto_attaching() -> None:
    state = {
        "checkup_ticker": "nvda",
        "cockpit_ticker": "TSLA",
    }

    ctx = chat.available_context(state, "/stock-checkup")
    if ctx["page_path"] != "stock-checkup" or ctx["page_title"] != "個股總覽":
        raise AssertionError(ctx)
    if ctx["ticker"] != "NVDA":
        raise AssertionError(ctx)
    if ctx["attached"] is not False:
        raise AssertionError("context should be discoverable but not auto-attached")


def test_build_context_attachment_reads_compact_verified_ticker_context() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        reports = root / "reports"
        candidates = root / "candidates"
        (reports / "options_flow").mkdir(parents=True)
        candidates.mkdir()
        (candidates / "ranked_candidates.json").write_text(json.dumps({
            "ranked_candidates": [
                {"ticker": "NVDA", "rank_score": 88.2, "last_price": 123.45},
                {"ticker": "AMD", "rank_score": 72.1},
            ]
        }), encoding="utf-8")
        (reports / "options_flow" / "latest.json").write_text(json.dumps({
            "as_of": "2026-07-06",
            "signals": [
                {"ticker": "NVDA", "flow_score": 91, "verdict": "bullish"},
                {"ticker": "TSLA", "flow_score": 42},
            ],
        }), encoding="utf-8")

        attachment = chat.build_context_attachment(
            {"ticker": "NVDA", "page_path": "options-cockpit", "page_title": "期權作戰台"},
            reports_dir=reports,
            candidate_dir=candidates,
        )

    summary = attachment["summary"]
    if "NVDA" not in summary or "rank_score" not in summary or "flow_score" not in summary:
        raise AssertionError(attachment)
    if "reports/options_flow/latest.json" not in attachment["sources"]:
        raise AssertionError(attachment)


def test_build_messages_separates_context_from_plain_question() -> None:
    system, user = chat.build_messages(
        "這檔能不能追？",
        history=[{"role": "user", "content": "前面先看 NVDA"}],
        mode="快速問答",
        context_attachment=None,
    )

    if "非投資建議" not in system or "反方" not in system:
        raise AssertionError(system)
    if "已附加的本機驗證資料" in user:
        raise AssertionError("context should only appear when explicitly attached")
    if "這檔能不能追？" not in user:
        raise AssertionError(user)


def test_quick_mode_uses_plain_chat_without_tools() -> None:
    calls = []

    class FakeClient:
        def __init__(self, provider: str, model: str):
            calls.append(("init", provider, model))

        def chat(self, system: str, user: str, max_tokens: int):
            calls.append(("chat", system, user, max_tokens))
            return "quick answer"

    answer = chat.answer_chat(
        "怎麼使用期權作戰台？",
        history=[],
        mode="快速問答",
        context_attachment=None,
        client_factory=FakeClient,
    )

    if answer != "quick answer":
        raise AssertionError(answer)
    if calls[0][1] != "codex":
        raise AssertionError(calls)
    if calls[1][0] != "chat":
        raise AssertionError(calls)


def test_deep_mode_uses_codex_web_only_tools() -> None:
    calls = []

    class FakeClient:
        def __init__(self, provider: str, model: str):
            calls.append(("init", provider, model))

        def chat_agentic(self, system: str, user: str, allowed_tools, max_turns: int, max_tokens: int):
            calls.append(("agentic", tuple(allowed_tools), max_turns, max_tokens, system, user))
            return "deep answer"

    answer = chat.answer_chat(
        "查一下 NVDA 最新消息",
        history=[],
        mode="深度研究",
        context_attachment={"summary": "Ticker: NVDA", "sources": ["manual"]},
        client_factory=FakeClient,
    )

    if answer != "deep answer":
        raise AssertionError(answer)
    if calls[0][1] != "codex":
        raise AssertionError(calls)
    if calls[1][1] != ("WebSearch", "WebFetch"):
        raise AssertionError(calls)
    if "請標示來源" not in calls[1][4]:
        raise AssertionError(calls[1][4])


def main() -> None:
    tests = [
        test_available_context_detects_page_and_ticker_without_auto_attaching,
        test_build_context_attachment_reads_compact_verified_ticker_context,
        test_build_messages_separates_context_from_plain_question,
        test_quick_mode_uses_plain_chat_without_tools,
        test_deep_mode_uses_codex_web_only_tools,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
