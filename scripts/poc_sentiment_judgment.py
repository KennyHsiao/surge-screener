#!/usr/bin/env python3
"""POC — AI judgment layer over free sentiment (Dimension 3).

Gathers free StockTwits + ApeWisdom data for a ticker, then asks an LLM to produce
the Dimension-3 judgment (organic vs coordinated, smart money, 0-15 score), applying
the StockTwits bullish-bias calibration — i.e. the exact "judgment layer" wired into
02_llm_score.py, run in isolation so you can preview it.

With an LLM key set it prints the AI verdict. Without one it prints the EXACT prompt
the AI would receive (populated with real data), so the input is visible either way.

Usage:
    python scripts/poc_sentiment_judgment.py MU
Provider via env: ANTHROPIC_API_KEY (default) | DEEPSEEK_API_KEY | OPENAI_API_KEY | XAI_API_KEY
"""

import importlib.util
import json
import os
import pathlib
import sys

SYSTEM = (
    "You are an equities social-sentiment analyst scoring Dimension 3 (Sentiment, "
    "0-15) of a surge-stock screener. You are given free StockTwits + Reddit/ApeWisdom "
    "data. HEED the calibration_note: StockTwits skews structurally bullish, so reward "
    "RELATIVE signals (high message volume, a real bearish share, Reddit mention "
    "momentum) — NOT default bullishness. Judge whether buzz looks organic or "
    "coordinated and whether high-follower / smart-money accounts are involved. "
    'Return ONLY a JSON object: {"dimension3_score": <int 0-15>, "net_read": '
    '"bullish|neutral|bearish", "organic_vs_coordinated": <str>, "smart_money": <str>, '
    '"reasoning": <str>}'
)


def _gather():
    spec = importlib.util.spec_from_file_location(
        "sentiment_free", pathlib.Path(__file__).parent / "sentiment_free.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.gather_free_sentiment


def call_llm(system: str, user: str):
    """Returns (provider_label, text) or (None, None) if no key is available."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model="claude-opus-4-8", max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}])
        return "anthropic/claude-opus-4-8", msg.content[0].text

    import httpx
    for env, base, model in (
        ("DEEPSEEK_API_KEY", "https://api.deepseek.com", "deepseek-chat"),
        ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o"),
        ("XAI_API_KEY", "https://api.x.ai/v1", "grok-4.3"),
    ):
        key = os.environ.get(env)
        if not key:
            continue
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "max_tokens": 1024,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]},
            timeout=120)
        r.raise_for_status()
        return f"{env.split('_')[0].lower()}/{model}", \
            r.json()["choices"][0]["message"]["content"]
    return None, None


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "MU").upper().lstrip("$")
    data = _gather()(ticker)
    user = (f"## Free social sentiment for ${ticker}\n"
            f"{json.dumps(data, indent=2, ensure_ascii=False)}\n\n"
            f"Score Dimension 3 for ${ticker} now.")

    print(f"=== Free sentiment gathered for ${ticker} "
          f"(sources: {data['sources_available']}) ===")
    provider, out = call_llm(SYSTEM, user)
    if out is None:
        print("\n⚠ No LLM key set — showing the EXACT prompt the AI judgment "
              "layer would receive (real data):\n")
        print("----- SYSTEM -----\n" + SYSTEM)
        print("\n----- USER -----\n" + user)
        print("\n→ Set ANTHROPIC_API_KEY (or DEEPSEEK_API_KEY) and re-run to get "
              "the actual AI verdict.")
        return 0
    print(f"\n=== AI judgment ({provider}) ===\n{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
