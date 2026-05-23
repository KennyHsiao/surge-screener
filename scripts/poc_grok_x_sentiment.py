#!/usr/bin/env python3
"""
POC — Grok X-sentiment probe (standalone, does NOT touch the pipeline).

Asks Grok one structured question about a ticker's X/Twitter sentiment using the
xAI `x_search` server-side tool (Responses API), and prints the parsed result.

This validates the "ask Grok, use its answer as Dimension-3 feedback" idea before
wiring a `grok` provider into scripts/02_llm_score.py's LLMClient.

Usage:
    XAI_API_KEY=xai-...  python scripts/poc_grok_x_sentiment.py MU
    python scripts/poc_grok_x_sentiment.py            # defaults to MU, last 3 days

Notes:
- x_search is billed separately (~$5 / 1,000 calls) on top of token cost.
- Real-time search is non-reproducible — snapshot the raw answer if you keep it.
"""

import json
import os
import sys
from datetime import date, timedelta

import httpx

XAI_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-4.3"

INSTRUCTIONS = (
    "You are a precise equities X/Twitter sentiment analyst for a surge-stock "
    "screener. Use the x_search tool to look at real X posts about the ticker. "
    "Judge whether buzz is organic or coordinated, and whether any smart-money/"
    "informed accounts are involved. Do not invent numbers — if you cannot measure "
    "something, say so and lower confidence. Respond with ONE strict JSON object and "
    "nothing else, matching exactly this schema:\n"
    "{\n"
    '  "ticker": str,\n'
    '  "window": str,\n'
    '  "mention_volume": {"level": "low|medium|high", "rough_count_estimate": int|null},\n'
    '  "net_sentiment": float,            // -1.0 (bearish) .. +1.0 (bullish)\n'
    '  "organic_vs_coordinated": "organic|mixed|coordinated|unclear",\n'
    '  "smart_money_signals": [str],\n'
    '  "notable_posts": [{"handle": str, "url": str, "why": str}],\n'
    '  "risk_flags": [str],\n'
    '  "confidence": float,               // 0.0 .. 1.0\n'
    '  "one_line_summary": str\n'
    "}"
)


def build_payload(ticker: str, from_date: str, to_date: str) -> dict:
    ask = (
        f"What is the current X/Twitter sentiment and buzz around ${ticker} "
        f"between {from_date} and {to_date}? Quantify mention volume, net sentiment, "
        f"and flag anything that looks coordinated or like smart money."
    )
    return {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "input": [{"role": "user", "content": ask}],
        "tools": [{
            "type": "x_search",
            "from_date": from_date,
            "to_date": to_date,
        }],
    }


def extract_text(resp: dict) -> str:
    """Pull assistant text out of the Responses API shape, defensively."""
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    parts = []
    for item in resp.get("output", []):
        content = item.get("content")
        if isinstance(content, list):
            for c in content:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    parts.append(c["text"])
        elif isinstance(content, str):
            parts.append(content)
    return "\n".join(parts).strip()


def extract_citations(resp: dict) -> list:
    cites = resp.get("citations") or []
    for item in resp.get("output", []):
        if isinstance(item.get("citations"), list):
            cites.extend(item["citations"])
    return cites


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "MU").upper().lstrip("$")
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("✗ XAI_API_KEY not set. Get one at https://console.x.ai then:\n"
              "  export XAI_API_KEY=xai-...\n"
              f"  python scripts/poc_grok_x_sentiment.py {ticker}", file=sys.stderr)
        return 2

    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=3)).isoformat()
    payload = build_payload(ticker, from_date, to_date)

    print(f"→ Asking Grok ({MODEL}) about ${ticker} X sentiment "
          f"[{from_date} .. {to_date}] via x_search ...\n")
    try:
        r = httpx.post(
            XAI_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"✗ HTTP {e.response.status_code}: {e.response.text[:800]}", file=sys.stderr)
        return 1
    except httpx.HTTPError as e:
        print(f"✗ request failed: {e}", file=sys.stderr)
        return 1

    resp = r.json()
    text = extract_text(resp)
    citations = extract_citations(resp)

    print("=== Grok answer (parsed as Dimension-3 feedback) ===")
    try:
        # tolerate stray prose / code fences around the JSON
        s, e = text.find("{"), text.rfind("}")
        parsed = json.loads(text[s:e + 1]) if s != -1 and e != -1 else None
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    else:
        print("(could not parse JSON — raw text below)\n" + text)

    if citations:
        print(f"\n=== Citations ({len(citations)}) ===")
        for c in citations[:15]:
            print(f"- {c}")

    usage = resp.get("usage")
    if usage:
        print(f"\n=== Usage ===\n{json.dumps(usage, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
