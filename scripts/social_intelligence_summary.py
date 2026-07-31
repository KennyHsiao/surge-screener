#!/usr/bin/env python3
"""Optional AI summary layer for free-first social intelligence snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
SOCIAL_DIR_NAME = "social_intelligence"
SUMMARY_MODEL = os.environ.get("SOCIAL_AI_SUMMARY_MODEL") or os.environ.get("CODEX_MODEL")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _market_key(market: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", str(market or "US").upper())
    return cleaned or "US"


def ai_summary_path(
    *,
    reports_dir: str | Path = REPORTS_DIR,
    market: str | None = "US",
) -> Path:
    return Path(reports_dir) / SOCIAL_DIR_NAME / f"ai_summary_{_market_key(market)}.json"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _compact(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _ticker_rows(snapshot: dict[str, Any], *, max_tickers: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _as_list(snapshot.get("tickers")):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper().lstrip("$")
        if not ticker:
            continue
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        validation = (
            row.get("platform_validation")
            if isinstance(row.get("platform_validation"), dict)
            else {}
        )
        rows.append({
            "ticker": ticker,
            "mentioned_by": [str(x).lstrip("@") for x in _as_list(row.get("mentioned_by")) if x],
            "skew": row.get("skew") or "neutral",
            "conviction": row.get("conviction") or "",
            "note": _compact(row.get("note"), 180),
            "labels": {str(k): bool(v) for k, v in labels.items()},
            "platform_validation": validation,
            "citations": [str(x) for x in _as_list(row.get("citations"))[:5] if x],
        })
    rows.sort(
        key=lambda r: (
            not bool(r["labels"].get("early_signal")),
            not bool(r["labels"].get("agent_reach")),
            bool(r["labels"].get("crowded")),
            -len(r["mentioned_by"]),
            r["ticker"],
        )
    )
    return rows[:max_tickers]


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    """Stable digest for detecting whether a saved AI summary matches a snapshot."""
    payload = {
        "market": snapshot.get("market"),
        "generated_at": snapshot.get("generated_at"),
        "as_of_date": snapshot.get("as_of_date"),
        "tickers": _ticker_rows(snapshot, max_tickers=24),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_summary_prompt(snapshot: dict[str, Any], *, max_tickers: int = 8) -> str:
    rows = _ticker_rows(snapshot, max_tickers=max_tickers)
    return (
        "你是交易研究助理，只能根據下列已驗證的社群快照做摘要，不可自行補資料、查新聞或杜撰引用。\n"
        "任務：把博主雷達候選整理成交易前檢查用的繁中摘要，重點是是否值得帶到作戰台繼續驗證。\n"
        "請只輸出 JSON，不要 markdown，不要 code fence。\n\n"
        "JSON schema:\n"
        "{\n"
        '  "headline": "一句話總結",\n'
        '  "takeaways": ["最多 4 點"],\n'
        '  "candidates": [\n'
        "    {\n"
        '      "ticker": "NVDA",\n'
        '      "stance": "bullish|bearish|mixed|neutral",\n'
        '      "priority": "watch|wait|avoid",\n'
        '      "summary": "為什麼值得/不值得追蹤",\n'
        '      "key_risk": "最主要反證或風險",\n'
        '      "evidence": ["原始 citation URL，沒有就空陣列"]\n'
        "    }\n"
        "  ],\n"
        '  "risks": ["最多 4 點"],\n'
        '  "next_steps": ["最多 4 點"]\n'
        "}\n\n"
        "判斷規則：\n"
        "- Agent Reach 代表從關注博主貼文抓到 ticker。\n"
        "- Retail Heat 代表 StockTwits/ApeWisdom 已有散戶熱度。\n"
        "- Crowded 代表熱度偏擁擠，不能當乾淨早期訊號。\n"
        "- Early Signal 代表博主發現 + 平台驗證且尚未過度擁擠。\n"
        "- 沒有 citation 時要降低信心，不能編造 URL。\n\n"
        "社群快照：\n"
        + json.dumps({
            "market": snapshot.get("market"),
            "generated_at": snapshot.get("generated_at"),
            "as_of_date": snapshot.get("as_of_date"),
            "tickers": rows,
        }, ensure_ascii=False, indent=2, default=str)
    )


def _extract_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("AI summary response must be a JSON object")
    return parsed


def _string_list(value: Any, *, limit: int = 4) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        text = _compact(item, 260)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _candidate_list(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or item.get("symbol") or "").strip().upper().lstrip("$")
        if not ticker:
            continue
        out.append({
            "ticker": ticker,
            "stance": str(item.get("stance") or "neutral").strip() or "neutral",
            "priority": str(item.get("priority") or "watch").strip() or "watch",
            "summary": _compact(item.get("summary"), 360),
            "key_risk": _compact(item.get("key_risk"), 260),
            "evidence": [str(x) for x in _as_list(item.get("evidence"))[:5] if x],
        })
        if len(out) >= limit:
            break
    return out


def generate_ai_summary(
    snapshot: dict[str, Any],
    *,
    llm_factory: Callable[..., Any] | None = None,
    provider: str = "codex",
    model: str | None = SUMMARY_MODEL,
) -> dict[str, Any]:
    rows = _ticker_rows(snapshot, max_tickers=8)
    digest = snapshot_digest(snapshot)
    base = {
        "source": "social_intelligence_ai_summary",
        "market": _market_key(str(snapshot.get("market") or "US")),
        "generated_at": _utc_timestamp(),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "snapshot_digest": digest,
        "model": model,
    }
    if not rows:
        return {
            **base,
            "llm": False,
            "headline": "這次博主雷達沒有可摘要的 ticker。",
            "takeaways": [],
            "candidates": [],
            "risks": ["候選清單為空，請先更新 free-first 社群快照。"],
            "next_steps": ["更新博主雷達後再產生 AI 摘要。"],
        }

    if llm_factory is None:
        from scripts.llm_client import LLMClient

        llm_factory = LLMClient

    client = llm_factory(provider=provider, model=model)
    raw = client.chat(
        "你是嚴格的交易研究摘要器。只根據使用者提供的 JSON 做歸納，禁止補資料。",
        build_summary_prompt(snapshot),
        max_tokens=1800,
    )
    parsed = _extract_json(raw)
    return {
        **base,
        "llm": True,
        "headline": _compact(parsed.get("headline"), 220) or "AI 摘要已產生。",
        "takeaways": _string_list(parsed.get("takeaways"), limit=4),
        "candidates": _candidate_list(parsed.get("candidates"), limit=8),
        "risks": _string_list(parsed.get("risks"), limit=4),
        "next_steps": _string_list(parsed.get("next_steps"), limit=4),
    }


def write_ai_summary(
    payload: dict[str, Any],
    *,
    reports_dir: str | Path = REPORTS_DIR,
    market: str | None = None,
) -> Path:
    key = market or payload.get("market") or "US"
    path = ai_summary_path(reports_dir=reports_dir, market=str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def load_ai_summary(
    *,
    reports_dir: str | Path = REPORTS_DIR,
    market: str | None = "US",
) -> dict[str, Any] | None:
    path = ai_summary_path(reports_dir=reports_dir, market=market)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
