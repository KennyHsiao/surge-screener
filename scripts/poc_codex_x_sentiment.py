#!/usr/bin/env python3
"""Standalone Codex SDK web-research probe for one ticker's X sentiment."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

try:
    from scripts.llm_client import LLMClient
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from llm_client import LLMClient  # type: ignore

MODEL = os.environ.get("SOCIAL_X_CODEX_MODEL") or os.environ.get("CODEX_MODEL")

INSTRUCTIONS = (
    "You are a precise equities X/Twitter sentiment analyst for a surge-stock "
    "screener. Use Codex web search to find publicly indexed, recent X posts "
    "about the ticker. Do not invent posts, URLs, counts, or authors. If evidence "
    "is sparse, say so and lower confidence. Return one strict JSON object with "
    "ticker, window, mention_volume, net_sentiment, organic_vs_coordinated, "
    "smart_money_signals, notable_posts, risk_flags, confidence, and "
    "one_line_summary."
)


def _parse_json(text: str) -> dict | None:
    try:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1]) if start >= 0 and end >= 0 else None
    except json.JSONDecodeError:
        return None


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "MU").upper().lstrip("$")
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=3)).isoformat()
    prompt = (
        f"Research current X/Twitter sentiment for ${ticker} from {from_date} "
        f"through {to_date}. Prioritize site:x.com URLs, cite every notable post, "
        "and distinguish measured evidence from inference."
    )

    try:
        text = LLMClient(
            provider="codex",
            model=MODEL,
            timeout=180,
            retry_max_attempts=1,
        ).chat_agentic(
            INSTRUCTIONS,
            prompt,
            allowed_tools=("WebSearch", "WebFetch"),
            max_turns=4,
            max_tokens=3000,
        )
    except Exception as exc:  # noqa: BLE001 - standalone diagnostic boundary
        print(f"Codex research failed ({type(exc).__name__})", file=sys.stderr)
        return 1

    parsed = _parse_json(text)
    print(json.dumps(parsed, indent=2, ensure_ascii=False) if parsed else text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
