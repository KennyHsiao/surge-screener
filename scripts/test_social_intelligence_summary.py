#!/usr/bin/env python3
"""Self-contained tests for optional AI summaries over social radar snapshots."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "social_intelligence_summary_under_test",
        ROOT / "scripts" / "social_intelligence_summary.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _snapshot() -> dict:
    return {
        "source": "social_intelligence",
        "market": "US",
        "generated_at": "2026-07-08T12:00:00Z",
        "tickers": [
            {
                "ticker": "NVDA",
                "mentioned_by": ["alpha", "beta"],
                "skew": "bullish",
                "conviction": "high",
                "note": "AI infra mention",
                "citations": ["https://x.com/alpha/status/1"],
                "labels": {"agent_reach": True, "early_signal": True},
                "platform_validation": {
                    "in_ranked_candidates": True,
                    "options_flow_direction": "bullish",
                    "options_flow_score": 78,
                },
            },
            {
                "ticker": "DELL",
                "mentioned_by": ["gamma"],
                "labels": {"agent_reach": True, "crowded": True},
                "citations": [],
            },
        ],
    }


class FakeLLM:
    def __init__(self, provider: str = "auto", model: str = "") -> None:
        self.provider = provider
        self.model = model

    def chat(self, system: str, user: str, max_tokens: int = 8192) -> str:
        if "NVDA" not in user or "DELL" not in user:
            raise AssertionError(user)
        return json.dumps({
            "headline": "NVDA 是較乾淨的早期訊號。",
            "takeaways": ["NVDA 有博主與平台雙重支持。"],
            "candidates": [
                {
                    "ticker": "NVDA",
                    "stance": "bullish",
                    "priority": "watch",
                    "summary": "博主提到 AI infra，期權流同向。",
                    "key_risk": "已接近事件風險時需降倉。",
                    "evidence": ["https://x.com/alpha/status/1"],
                }
            ],
            "risks": ["DELL 較擁擠。"],
            "next_steps": ["只把 NVDA 帶到作戰台驗證。"],
        }, ensure_ascii=False)


def test_generate_ai_summary_returns_structured_payload_with_snapshot_digest() -> None:
    mod = _load_module()

    result = mod.generate_ai_summary(_snapshot(), llm_factory=FakeLLM)

    if result["source"] != "social_intelligence_ai_summary":
        raise AssertionError(result)
    if result["market"] != "US" or not result["snapshot_digest"]:
        raise AssertionError(result)
    if result["headline"] != "NVDA 是較乾淨的早期訊號。":
        raise AssertionError(result)
    if result["candidates"][0]["ticker"] != "NVDA":
        raise AssertionError(result)


def test_write_and_load_summary_uses_market_specific_runtime_file() -> None:
    mod = _load_module()
    payload = mod.generate_ai_summary(_snapshot(), llm_factory=FakeLLM)

    with tempfile.TemporaryDirectory() as d:
        path = mod.write_ai_summary(payload, reports_dir=Path(d), market="US")
        loaded = mod.load_ai_summary(reports_dir=Path(d), market="US")

    if path.name != "ai_summary_US.json":
        raise AssertionError(path)
    if loaded["snapshot_digest"] != payload["snapshot_digest"]:
        raise AssertionError(loaded)


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
