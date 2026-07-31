#!/usr/bin/env python3
"""Offline contracts for Codex-backed X influencer research."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import x_influencers


class FakeClient:
    init_kwargs: dict | None = None
    call_kwargs: dict | None = None

    def __init__(self, **kwargs) -> None:
        type(self).init_kwargs = kwargs

    def chat_agentic(self, system: str, user: str, **kwargs) -> str:
        type(self).call_kwargs = {"system": system, "user": user, **kwargs}
        return """{
          "window": "2026-07-27..2026-07-30",
          "handles_requested": ["alpha"],
          "by_influencer": [{
            "handle": "alpha",
            "active": true,
            "tickers": [{"symbol": "NVDA", "stance": "bullish",
              "conviction": "high", "note": "AI demand"}],
            "setups": [],
            "substance_vs_hype": "substance",
            "summary": "Evidence-backed",
            "citations": ["https://x.com/alpha/status/1"]
          }],
          "trending_tickers": [],
          "confidence": 0.8,
          "notes": ""
        }"""


def test_analysis_routes_web_research_through_codex() -> None:
    result = x_influencers.analyze(
        ["alpha"],
        "2026-07-27",
        "2026-07-30",
        llm_factory=FakeClient,
    )

    if result.get("parsed", {}).get("confidence") != 0.8:
        raise AssertionError(result)
    if result.get("citations") != ["https://x.com/alpha/status/1"]:
        raise AssertionError(result)
    if FakeClient.init_kwargs is None or FakeClient.init_kwargs.get("provider") != "codex":
        raise AssertionError(FakeClient.init_kwargs)
    call = FakeClient.call_kwargs or {}
    if call.get("allowed_tools") != ("WebSearch", "WebFetch"):
        raise AssertionError(call)
    if "site:x.com/alpha" not in call.get("user", ""):
        raise AssertionError(call)


def test_dry_run_payload_contains_no_direct_xai_contract() -> None:
    payload = x_influencers.build_payload(
        ["alpha"],
        "2026-07-27",
        "2026-07-30",
    )
    text = str(payload).lower()
    if payload.get("provider") != "codex":
        raise AssertionError(payload)
    for forbidden in ("xai", "x_search", "api_key"):
        if forbidden in text:
            raise AssertionError(f"legacy direct-provider field remains: {forbidden}")


def main() -> None:
    tests = [
        test_analysis_routes_web_research_through_codex,
        test_dry_run_payload_contains_no_direct_xai_contract,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    main()
