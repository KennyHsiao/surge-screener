#!/usr/bin/env python3
"""
Free social-sentiment sources for Dimension 3 — no API key, no paid service.

- StockTwits: per-symbol stream with user-tagged Bullish/Bearish + message volume.
- ApeWisdom:  Reddit (WSB etc.) mention ranking + 24h mention momentum.

Used by 02_llm_score.py to feed Dimension-3 context to the scoring LLM, which does
the qualitative judgment (organic vs coordinated, smart money). Mirrors the role of
options_free.py for Dimension 6.

Standalone test:
    python scripts/sentiment_free.py MU
"""

import functools
import json
import sys

import httpx

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# StockTwits retail sentiment skews heavily bullish, so a default-positive stream is
# noise, not signal. This note travels with the data so the scoring LLM calibrates.
CALIBRATION_NOTE = (
    "StockTwits retail sentiment is STRUCTURALLY BULLISH — bullish-tagged messages "
    "normally far outnumber bearish. Treat net_sentiment as RELATIVE, not absolute: "
    "signal comes from unusually high message volume, a meaningful bearish share, or a "
    "sharp move in Reddit mention momentum (mention_change_pct) — NOT from a "
    "default-bullish, low-volume stream. Do not award high Dimension-3 points for that."
)


def stocktwits_sentiment(ticker: str) -> dict | None:
    """Recent StockTwits stream for a symbol → volume + bull/bear breakdown."""
    try:
        r = httpx.get(
            f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json",
            headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        # network error, rate-limit HTML, or non-JSON body → no data, never raise
        return None

    # A 200 with an error body (unknown symbol, rate limit) carries no real messages
    # list — treat as unavailable, not as neutral 0-message sentiment.
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        return None
    msgs = payload["messages"]

    bull = bear = 0
    notable = []
    for m in msgs:
        sent = ((m.get("entities") or {}).get("sentiment") or {}).get("basic")
        if sent == "Bullish":
            bull += 1
        elif sent == "Bearish":
            bear += 1
        if sent:
            user = m.get("user") or {}
            notable.append({
                "handle": user.get("username", "?"),
                "followers": user.get("followers", 0),
                "sentiment": sent,
                "body": (m.get("body") or "").replace("\n", " ")[:160],
            })

    total = len(msgs)
    tagged = bull + bear
    return {
        "total_messages": total,
        "bullish": bull,
        "bearish": bear,
        "untagged": total - tagged,
        "net_sentiment": round((bull - bear) / tagged, 2) if tagged else 0.0,
        "notable_posts": sorted(notable, key=lambda n: n["followers"],
                                reverse=True)[:5],
    }


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


@functools.lru_cache(maxsize=1)
def _apewisdom_top() -> tuple:
    """(valid_rows_by_ticker, present_but_malformed_tickers), fetched once per process.

    A row counts as valid only if it carries a numeric `mentions`. Raises if the
    payload yields NO valid rows — so a malformed/down ApeWisdom is reported as
    unavailable rather than fabricating "low buzz" for every ticker.
    """
    r = httpx.get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
                  headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    payload = r.json()
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        raise ValueError("ApeWisdom: missing/empty results list")

    valid, malformed = {}, set()
    for row in results:
        if not isinstance(row, dict):
            continue
        tk = row.get("ticker")
        if not isinstance(tk, str):
            continue
        if _is_number(row.get("mentions")):
            valid[tk] = row
        else:
            malformed.add(tk)        # present but unusable → not "absent"
    if not valid:
        raise ValueError("ApeWisdom: no rows with valid mention data")
    return valid, frozenset(malformed)


def apewisdom_mentions(ticker: str) -> dict | None:
    """Reddit mention rank + 24h momentum, or low-buzz marker if genuinely absent."""
    try:
        valid, malformed = _apewisdom_top()
    except Exception:
        # network error, rate-limit HTML, or non-JSON body → no data, never raise
        return None
    row = valid.get(ticker)
    if row is None:
        # Only fabricate "low buzz" when the ticker is genuinely absent from a payload
        # that DID carry valid data. A present-but-malformed row → unavailable.
        if ticker in malformed:
            return None
        return {"in_top_mentions": False, "rank": None, "mentions": 0,
                "note": "not in ApeWisdom top-100 by Reddit mentions (low buzz)"}
    m = row["mentions"]  # guaranteed numeric by _apewisdom_top
    m24 = row.get("mentions_24h_ago")
    m24 = m24 if _is_number(m24) else 0
    return {
        "in_top_mentions": True,
        "rank": row.get("rank"),
        "mentions": m,
        "mentions_24h_ago": m24,
        "mention_change_pct": round((m - m24) / m24 * 100, 1) if m24 else None,
        "upvotes": row.get("upvotes"),
    }


def _safe(fn, ticker: str) -> dict | None:
    """Run one source fetcher in isolation. ANY failure — including a malformed but
    HTTP-200 payload that trips the parsing logic — yields None instead of taking
    down the other source."""
    try:
        return fn(ticker)
    except Exception:
        return None


def gather_free_sentiment(ticker: str) -> dict:
    """Combined free sentiment for one ticker, ready to drop into the LLM prompt.

    Each source is fetched in isolation: one source raising never loses the other.
    """
    ticker = ticker.upper().lstrip("$")
    st = _safe(stocktwits_sentiment, ticker)
    aw = _safe(apewisdom_mentions, ticker)
    return {
        "ticker": ticker,
        "stocktwits": st,
        "reddit_apewisdom": aw,
        "calibration_note": CALIBRATION_NOTE,
        "sources_available": [n for n, v in (("stocktwits", st),
                                             ("reddit_apewisdom", aw)) if v],
    }


if __name__ == "__main__":
    tk = sys.argv[1] if len(sys.argv) > 1 else "MU"
    print(json.dumps(gather_free_sentiment(tk), indent=2, ensure_ascii=False))
