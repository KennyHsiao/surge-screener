#!/usr/bin/env python3
"""X influencer analysis via xAI Grok ``x_search`` (scoped to specific handles).

Reads the editable influencer roster (``SURGE_INFLUENCERS_PATH`` when set,
seeded from ``content/influencers.json``) and asks Grok (xAI Responses API,
server-side ``x_search`` tool with ``allowed_x_handles``) what the tracked
influencers are actually posting: which tickers/assets, their stance +
conviction, any concrete momentum-options setups, and hype-vs-substance — WITH
citations. Because the search runs server-side and returns sources, it fits the
project's verified-data-to-LLM principle (the model reports cited posts, not
guesses).

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

try:
    from scripts import influencer_roster_runtime
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import influencer_roster_runtime  # type: ignore

XAI_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-4.3"
_INFLUENCERS = influencer_roster_runtime.DEFAULT_ROSTER_PATH
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
    """Load tracked influencers from the editable runtime roster, optionally filtered.

    Returns a list of {handle, name, category, market} dicts. [] on any read error.
    """
    try:
        roster_path = Path(path) if path else influencer_roster_runtime.resolve_roster_path()
        data = json.loads(roster_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out, seen = [], set()
    for r in data.get("influencers", []):
        if not isinstance(r, dict):
            continue
        h = (r.get("handle") or "").strip().lstrip("@")
        if not h:
            continue
        if market and (r.get("market") or "").upper() != market.upper():
            continue
        if category and (r.get("category") or "") != category:
            continue
        if h.lower() in seen:  # X handles are case-insensitive; don't waste the cap
            continue
        seen.add(h.lower())
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


_CONV_RANK = {"high": 3, "medium": 2, "low": 1}


def _dominant(stances: list) -> str:
    """Net skew from a list of bullish/bearish/mixed/neutral labels.

    str()-coerces each item (the model may emit a number/bool) and lower-cases it,
    so it never raises and is case-insensitive. An explicit 'mixed' is preserved.
    """
    norm = [str(s or "").lower() for s in stances]
    if any("mix" in s for s in norm):
        return "mixed"
    b = sum(1 for s in norm if "bull" in s)
    r = sum(1 for s in norm if "bear" in s)
    if b and r:
        return "mixed"
    if b:
        return "bullish"
    if r:
        return "bearish"
    return "neutral"


def _max_conviction(convs: list[str]) -> str | None:
    best = max((_CONV_RANK.get(c, 0) for c in convs), default=0)
    return {3: "high", 2: "medium", 1: "low"}.get(best)


def build_picks(parsed: dict | None, handles: list[str], window: str,
                market: str | None = None) -> dict:
    """Flatten a Grok influencer analysis into a de-duped ticker candidate list.

    Aggregates by_influencer[].tickers (+ trending_tickers) by symbol into
    {symbol, mentioned_by[], count, skew, conviction, note}, sorted by how many
    influencers mentioned it. PURE (no I/O) so it's testable offline. parsed=None
    → empty tickers. This is the candidate list fed to the screener / cockpit.
    """
    # The model authors this JSON, so guard every shape: lists may be non-lists,
    # entries/tickers may be non-dicts. Skip anything that isn't the right shape
    # rather than crash (the never-raises invariant).
    def _as_list(v):
        return v if isinstance(v, list) else []

    agg: dict[str, dict] = {}
    raw_by_infl = _as_list((parsed or {}).get("by_influencer"))
    by_infl = [e for e in raw_by_infl if isinstance(e, dict)]
    for entry in by_infl:
        handle = entry.get("handle", "") or ""
        for tk in _as_list(entry.get("tickers")):
            if not isinstance(tk, dict):
                continue
            sym = str(tk.get("symbol") or "").upper().lstrip("$")
            if not sym:
                continue
            rec = agg.setdefault(sym, {"mentioned_by": [], "stances": [],
                                       "convictions": [], "notes": []})
            if handle and handle not in rec["mentioned_by"]:
                rec["mentioned_by"].append(handle)
            if tk.get("stance"):
                rec["stances"].append(tk["stance"])
            if tk.get("conviction"):
                rec["convictions"].append(tk["conviction"])
            if tk.get("note"):
                rec["notes"].append(f"@{handle}: {tk['note']}" if handle else tk["note"])
    for tr in _as_list((parsed or {}).get("trending_tickers")):
        if not isinstance(tr, dict):
            continue
        sym = str(tr.get("symbol") or "").upper().lstrip("$")
        if not sym:
            continue
        rec = agg.setdefault(sym, {"mentioned_by": [], "stances": [],
                                   "convictions": [], "notes": []})
        for h in _as_list(tr.get("mentioned_by")):
            if h and h not in rec["mentioned_by"]:
                rec["mentioned_by"].append(h)
        if tr.get("skew"):
            rec["stances"].append(tr["skew"])
    picks = [{
        "symbol": sym,
        "mentioned_by": rec["mentioned_by"],
        "count": len(rec["mentioned_by"]),
        "skew": _dominant(rec["stances"]),
        "conviction": _max_conviction(rec["convictions"]),
        "note": rec["notes"][0] if rec["notes"] else "",
    } for sym, rec in agg.items()]
    picks.sort(key=lambda p: (-p["count"], p["symbol"]))
    return {
        "source": "x_influencers", "market": market, "window": window,
        "handles": handles, "tickers": picks, "by_influencer": by_infl,
        "confidence": (parsed or {}).get("confidence"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="X influencer analysis via xAI x_search")
    ap.add_argument("--market", help="filter handles by market (US / CRYPTO)")
    ap.add_argument("--category", help="filter handles by category")
    ap.add_argument("--days", type=int, default=3, help="lookback window (default 3)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build + print the payload, do NOT call the API")
    ap.add_argument("--save", action="store_true",
                    help="write the extracted ticker picks to "
                         "reports/x_influencer_picks.json (for dashboard + cockpit)")
    args = ap.parse_args()

    rows = load_handles(args.market, args.category)
    if not rows:
        print("No matching influencers in the editable influencer roster "
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

    if args.save:
        if res["parsed"] is None:
            print("\n✗ --save skipped: could not parse a JSON result.", file=sys.stderr)
            return 1
        picks = build_picks(res["parsed"], handles, f"{from_date}..{to_date}",
                            args.market)
        from datetime import datetime, timezone
        picks["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        picks["citations"] = res["citations"]
        out = _INFLUENCERS.parent.parent / "reports" / "x_influencer_picks.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(picks, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"\nwrote {out}: {len(picks['tickers'])} ticker picks "
              f"{[p['symbol'] for p in picks['tickers'][:12]]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
