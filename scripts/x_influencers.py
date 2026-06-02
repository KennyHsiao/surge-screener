#!/usr/bin/env python3
"""X influencer analysis via xAI Grok ``x_search`` (scoped to specific handles).

Reads content/influencers.json and asks Grok (xAI Responses API, server-side
``x_search`` tool with ``allowed_x_handles``) what the tracked influencers are
actually posting: which tickers/assets, their stance + conviction, any concrete
momentum-options setups, and hype-vs-substance — WITH citations. Because the
search runs server-side and returns sources, it fits the project's
verified-data-to-LLM principle (the model reports cited posts, not guesses).

IMPORTANT — which Grok this uses:
  This uses the xAI DEVELOPER API (XAI_API_KEY from console.x.ai), billed
  separately (~$5 / 1,000 x_search calls + token cost). It is UNRELATED to a
  consumer X Premium subscription: that Grok is a chat UI with NO API, so it
  cannot be driven programmatically. A fresh xAI developer account (email only,
  independent of your X login) ships ~$25 starter credit — enough to run this at
  near-zero cash. See memory: x-premium-grok-not-api.

Usage:
    XAI_API_KEY=xai-...  python scripts/x_influencers.py --market US --days 3
    python scripts/x_influencers.py --dry-run      # build+print payload, no API call
    python scripts/x_influencers.py --category "Option Flow" --days 7
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

XAI_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-4.3"
_INFLUENCERS = Path(__file__).resolve().parent.parent / "content" / "influencers.json"
MAX_HANDLES = 20  # x_search allowed_x_handles hard cap

INSTRUCTIONS = (
    "You are an equities + crypto X/Twitter desk analyst for a momentum/surge "
    "screener. Use the x_search tool to read the RECENT posts of the given "
    "influencer handles ONLY (the search is already scoped to them). For each "
    "handle, report what is actionable for a swing/momentum-options trader: which "
    "tickers/assets they discussed, their directional stance, conviction, any "
    "specific entry/option setups, and whether it reads as substance or hype. "
    "NEVER invent posts, tickers, or numbers — if a handle had nothing relevant in "
    "the window, mark active=false and say so. Prefer citing the actual post. "
    "Respond with ONE strict JSON object and nothing else, matching this schema:\n"
    "{\n"
    '  "window": str,\n'
    '  "handles_requested": [str],\n'
    '  "by_influencer": [{\n'
    '    "handle": str,\n'
    '    "active": bool,\n'
    '    "tickers": [{"symbol": str, "stance": "bullish|bearish|neutral", '
    '"conviction": "low|medium|high", "note": str}],\n'
    '    "setups": [str],\n'
    '    "substance_vs_hype": "substance|mixed|hype|unclear",\n'
    '    "summary": str,\n'
    '    "citations": [str]\n'
    "  }],\n"
    '  "trending_tickers": [{"symbol": str, "mentioned_by": [str], "skew": '
    '"bullish|bearish|mixed"}],\n'
    '  "confidence": float,\n'
    '  "notes": str\n'
    "}"
)


def load_handles(market: str | None = None, category: str | None = None,
                 path: Path | None = None) -> list[dict]:
    """Load tracked influencers from content/influencers.json, optionally filtered.

    Returns a list of {handle, name, category, market} dicts. [] on any read error.
    """
    try:
        data = json.loads((path or _INFLUENCERS).read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for r in data.get("influencers", []):
        h = (r.get("handle") or "").strip().lstrip("@")
        if not h:
            continue
        if market and (r.get("market") or "").upper() != market.upper():
            continue
        if category and (r.get("category") or "") != category:
            continue
        out.append({"handle": h, "name": r.get("name"),
                    "category": r.get("category"), "market": r.get("market")})
    return out


def build_payload(handles: list[str], from_date: str, to_date: str) -> dict:
    ask = (
        f"Analyze the recent X posts ({from_date} to {to_date}) of these handles: "
        f"{', '.join('@' + h for h in handles)}. For each, extract the tickers/"
        f"assets they discussed and whether they're bullish or bearish, any concrete "
        f"trade/option setups, and flag hype vs substance. Then list tickers trending "
        f"across multiple of them."
    )
    return {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "input": [{"role": "user", "content": ask}],
        "tools": [{
            "type": "x_search",
            "from_date": from_date,
            "to_date": to_date,
            "allowed_x_handles": handles,   # server-side scope, <= MAX_HANDLES
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


def _parse_json(text: str):
    """Tolerate stray prose / code fences around the JSON object."""
    try:
        s, e = text.find("{"), text.rfind("}")
        return json.loads(text[s:e + 1]) if s != -1 and e != -1 else None
    except json.JSONDecodeError:
        return None


def analyze(handles: list[str], from_date: str, to_date: str,
            api_key: str, timeout: float = 180) -> dict:
    """Call xAI and return {parsed, citations, usage, raw_text}. Never raises."""
    payload = build_payload(handles, from_date, to_date)
    try:
        r = httpx.post(
            XAI_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=payload, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:600]}"}
    except httpx.HTTPError as e:
        return {"error": f"request failed: {e}"}
    resp = r.json()
    text = extract_text(resp)
    return {"parsed": _parse_json(text), "raw_text": text,
            "citations": extract_citations(resp), "usage": resp.get("usage")}


def main() -> int:
    ap = argparse.ArgumentParser(description="X influencer analysis via xAI x_search")
    ap.add_argument("--market", help="filter handles by market (US / CRYPTO)")
    ap.add_argument("--category", help="filter handles by category")
    ap.add_argument("--days", type=int, default=3, help="lookback window (default 3)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build + print the payload, do NOT call the API")
    args = ap.parse_args()

    rows = load_handles(args.market, args.category)
    if not rows:
        print("No matching influencers in content/influencers.json "
              "(check --market / --category).", file=sys.stderr)
        return 2
    handles = [r["handle"] for r in rows]
    if len(handles) > MAX_HANDLES:
        print(f"NOTE: {len(handles)} handles match but x_search caps "
              f"allowed_x_handles at {MAX_HANDLES}; using the first {MAX_HANDLES} "
              f"(dropping {len(handles) - MAX_HANDLES}). Narrow with --market/"
              f"--category to choose which.", file=sys.stderr)
        handles = handles[:MAX_HANDLES]

    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=args.days)).isoformat()

    if args.dry_run:
        print(f"# dry-run: would analyze {len(handles)} handles "
              f"[{from_date} .. {to_date}]\n")
        print(json.dumps(build_payload(handles, from_date, to_date),
                         indent=2, ensure_ascii=False))
        return 0

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("✗ XAI_API_KEY not set. This needs an xAI DEVELOPER key (unrelated to "
              "X Premium) from https://console.x.ai — fresh accounts get ~$25 credit.\n"
              "  export XAI_API_KEY=xai-...\n"
              "  python scripts/x_influencers.py --market US --days 3\n"
              "  (or run with --dry-run to inspect the payload without a key)",
              file=sys.stderr)
        return 2

    print(f"→ Grok ({MODEL}) analyzing {len(handles)} handles "
          f"[{from_date} .. {to_date}] via x_search: {handles}\n")
    res = analyze(handles, from_date, to_date, api_key)
    if res.get("error"):
        print(f"✗ {res['error']}", file=sys.stderr)
        return 1

    print("=== influencer analysis ===")
    if res["parsed"] is not None:
        print(json.dumps(res["parsed"], indent=2, ensure_ascii=False))
    else:
        print("(could not parse JSON — raw text below)\n" + res["raw_text"])
    if res["citations"]:
        print(f"\n=== citations ({len(res['citations'])}) ===")
        for c in res["citations"][:20]:
            print(f"- {c}")
    if res["usage"]:
        print(f"\n=== usage ===\n{json.dumps(res['usage'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
