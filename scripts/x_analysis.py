#!/usr/bin/env python3
"""X (Twitter) sentiment / influencer analysis backend.

Two responsibilities, both lazy so the module imports cleanly without keys:
  1. fetch posts from X API v2 (needs X_BEARER_TOKEN) — by handle or keyword.
  2. analyze posts with Claude (needs ANTHROPIC_API_KEY) — sentiment + themes.

If ANTHROPIC_API_KEY is missing, analyze() degrades to a no-LLM summary so the
UI can still show raw posts.

⚠️ Cost note (as of 2026-02-06): the X API moved to pay-per-use as the default
for new developers — there is no $0 read tier; third-party post reads bill
~$0.005 each (a call returning 100 posts bills 100x). For low-cost influencer /
sentiment work prefer the xAI x_search path (scripts/x_influencers.py /
poc_grok_x_sentiment.py), which is server-side and cited; keep this X-API path for
raw-post retrieval. Callers must handle XApiError (includes HTTP 429 rate-limit).
"""

import json
import os

import httpx

X_API_BASE = "https://api.twitter.com/2"
_ANALYSIS_MODEL = "claude-sonnet-4-6"  # cheaper than Opus; fine for summarization


class XApiError(RuntimeError):
    """Raised when the X API is unavailable, unauthorized, or rate-limited."""


def get_status() -> dict:
    """What's wired up — used by the UI to show capability/degradation."""
    return {
        "x_token": bool(os.getenv("X_BEARER_TOKEN")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


def _headers() -> dict:
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        raise XApiError("缺少 X_BEARER_TOKEN，無法抓取 X 資料。")
    return {"Authorization": f"Bearer {token}"}


def _get(path: str, params: dict) -> dict:
    try:
        resp = httpx.get(f"{X_API_BASE}{path}", headers=_headers(),
                         params=params, timeout=20.0)
    except httpx.HTTPError as e:
        raise XApiError(f"X API 連線失敗:{e}") from e
    if resp.status_code == 429:
        raise XApiError("X API 速率限制 (HTTP 429)。2026 起新帳號為 pay-per-use "
                        "(讀取約 $0.005/則,無免費層),請稍後再試或改用 x_search 路徑。")
    if resp.status_code == 401:
        raise XApiError("X API 認證失敗 (HTTP 401)，請檢查 X_BEARER_TOKEN。")
    if resp.status_code >= 400:
        raise XApiError(f"X API 錯誤 (HTTP {resp.status_code}): {resp.text[:200]}")
    return resp.json()


def fetch_user_posts(handle: str, limit: int = 20) -> list[dict]:
    """Recent original posts for a handle (excludes retweets/replies)."""
    handle = handle.lstrip("@").strip()
    if not handle:
        raise XApiError("請輸入有效的帳號。")
    user = _get(f"/users/by/username/{handle}", {})
    uid = user.get("data", {}).get("id")
    if not uid:
        raise XApiError(f"找不到帳號 @{handle}。")
    data = _get(f"/users/{uid}/tweets", {
        "max_results": max(5, min(limit, 100)),
        "tweet.fields": "created_at,public_metrics",
        "exclude": "retweets,replies",
    })
    return _normalize(data, author=f"@{handle}")


def fetch_keyword_posts(query: str, limit: int = 20) -> list[dict]:
    """Recent posts matching a keyword/cashtag query (English, no retweets)."""
    query = query.strip()
    if not query:
        raise XApiError("請輸入查詢關鍵字。")
    data = _get("/tweets/search/recent", {
        "query": f"{query} -is:retweet lang:en",
        "max_results": max(10, min(limit, 100)),
        "tweet.fields": "created_at,public_metrics",
    })
    return _normalize(data, author=None)


def _normalize(data: dict, author: str | None) -> list[dict]:
    out = []
    for t in data.get("data", []):
        m = t.get("public_metrics", {})
        out.append({
            "text": t.get("text", ""),
            "created_at": t.get("created_at", ""),
            "author": author or "",
            "likes": m.get("like_count", 0),
            "retweets": m.get("retweet_count", 0),
        })
    return out


def analyze(posts: list[dict], context: str = "") -> dict:
    """Sentiment + themes via Claude. Degrades to no-LLM summary without a key."""
    if not posts:
        return {"llm": False, "note": "沒有可分析的貼文。"}

    # Shared client: uses ANTHROPIC_API_KEY if set, else the logged-in Claude
    # subscription (claude_agent). Degrade gracefully if neither is available.
    try:
        from llm_client import LLMClient
    except ImportError:
        from scripts.llm_client import LLMClient

    joined = "\n".join(
        f"- ({p['created_at']}) [{p['likes']}♥/{p['retweets']}↻] {p['text']}"
        for p in posts[:40]
    )
    prompt = (
        f"你是金融社群情緒分析助手。以下是 X 上關於「{context}」的貼文。\n"
        f"請只輸出 JSON,鍵為:overall_sentiment(bullish/bearish/neutral)、"
        f"sentiment_score(-1.0~1.0)、summary(中文 2-3 句重點)、"
        f"key_themes(字串陣列)、highlights(陣列,每項 {{text, why}})、"
        f"stance(若內容像單一博主,描述其近期觀點傾向;否則空字串)。\n\n"
        f"貼文:\n{joined}"
    )
    try:
        client = LLMClient(provider="auto", model=_ANALYSIS_MODEL)
        raw = client.chat(
            "你是金融社群情緒分析助手,只輸出 JSON,不要加任何說明文字。",
            prompt, max_tokens=1200,
        ).strip()
    except Exception as e:
        return {
            "llm": False,
            "note": ("未設定可用的 LLM 後端(需 ANTHROPIC_API_KEY,"
                     f"或已登入的 claude / CLAUDE_CODE_OAUTH_TOKEN):{e}"),
            "post_count": len(posts),
        }
    # tolerate fenced code blocks
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    try:
        parsed = json.loads(raw)
        parsed["llm"] = True
        parsed["post_count"] = len(posts)
        return parsed
    except json.JSONDecodeError:
        return {"llm": True, "note": "LLM 回傳無法解析為 JSON。", "raw": raw[:500]}


if __name__ == "__main__":
    import sys
    print("status:", get_status())
    if len(sys.argv) > 1:
        ps = fetch_user_posts(sys.argv[1])
        print(json.dumps(analyze(ps, context=sys.argv[1]), ensure_ascii=False, indent=2))
