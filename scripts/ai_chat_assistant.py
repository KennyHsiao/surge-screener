#!/usr/bin/env python3
"""Prompting and routing for the global AI chat assistant."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from scripts.runtime_paths import CANDIDATE_OUTPUT_DIR, REPO
except ImportError:  # pragma: no cover - direct script execution fallback
    from runtime_paths import CANDIDATE_OUTPUT_DIR, REPO  # type: ignore


QUICK_MODE = "快速問答"
DEEP_MODE = "深度研究"
MODES = (QUICK_MODE, DEEP_MODE)

QUICK_MODEL = os.environ.get("AI_CHAT_QUICK_MODEL") or os.environ.get("CODEX_MODEL")
DEEP_MODEL = os.environ.get("AI_CHAT_DEEP_MODEL") or os.environ.get("CODEX_MODEL")

_PAGE_TITLES = {
    "today-decision": "今日決策",
    "trade-state": "交易狀態",
    "us-screener": "暴漲股篩選器",
    "options-flow": "選擇權異常流",
    "stock-checkup": "個股總覽",
    "options-cockpit": "期權作戰台",
    "radar": "雷達",
    "ibkr-reconcile": "IBKR 對帳",
    "sector-rotation": "熱錢板塊輪動",
    "theme-flow": "主題資金流",
    "market-thesis": "大盤行情研判",
    "us-options": "期權分析",
}

_TICKER_KEYS_BY_PAGE = {
    "stock-checkup": ("checkup_ticker", "checkup_ticker_input", "checkup_handoff"),
    "options-cockpit": ("cockpit_ticker",),
    "radar": ("radar_manual", "radar_handoff"),
    "us-options": ("opt_ticker",),
}

_FALLBACK_TICKER_KEYS = (
    "checkup_ticker",
    "cockpit_ticker",
    "opt_ticker",
    "radar_manual",
    "checkup_ticker_input",
)


def _get(mapping: Any, key: str) -> Any:
    try:
        return mapping.get(key)
    except AttributeError:
        try:
            return mapping[key]
        except Exception:
            return None


def _clean_page_path(current_path: str | None) -> str:
    path = str(current_path or "").strip()
    if "://" in path:
        from urllib.parse import urlsplit
        path = urlsplit(path).path
    path = path.split("?", 1)[0].strip("/")
    return path or "today-decision"


def _clean_ticker(value: Any) -> str | None:
    text = str(value or "").upper().strip()
    if not re.match(r"^[A-Z0-9][A-Z0-9.\-]{0,12}$", text):
        return None
    return text


def available_context(session_state: Any, current_path: str | None) -> dict[str, Any]:
    """Return discoverable page/ticker context without attaching data."""
    page_path = _clean_page_path(current_path)
    keys = _TICKER_KEYS_BY_PAGE.get(page_path, ()) + _FALLBACK_TICKER_KEYS
    ticker = None
    for key in keys:
        ticker = _clean_ticker(_get(session_state, key))
        if ticker:
            break
    return {
        "page_path": page_path,
        "page_title": _PAGE_TITLES.get(page_path, page_path),
        "ticker": ticker,
        "attached": False,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _compact(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: row[k] for k in keys if row.get(k) is not None}


def _find_ticker_row(rows: Any, ticker: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker:
            return row
    return None


def _candidate_row(candidate_dir: Path, ticker: str) -> tuple[dict[str, Any] | None, str | None]:
    ranked = _load_json(candidate_dir / "ranked_candidates.json")
    if isinstance(ranked, dict):
        row = _find_ticker_row(ranked.get("ranked_candidates") or ranked.get("tickers"), ticker)
        if row:
            return _compact(row, (
                "ticker", "rank_score", "last_price", "market_cap", "sector",
                "industry", "cycle", "verdict",
            )), "ranked_candidates.json"

    scored = _load_json(candidate_dir / "scored_candidates.json")
    if isinstance(scored, dict):
        for key in ("needs_layer2", "watchlist", "all_scored"):
            row = _find_ticker_row(scored.get(key), ticker)
            if row:
                return _compact(row, (
                    "ticker", "regime_adjusted_score", "composite_score",
                    "verdict", "last_price",
                )), "scored_candidates.json"
    return None, None


def build_context_attachment(
    context: dict[str, Any],
    reports_dir: str | Path | None = None,
    candidate_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build a compact, explicit context payload for the next chat turn."""
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    candidates = Path(candidate_dir) if candidate_dir is not None else CANDIDATE_OUTPUT_DIR
    ticker = _clean_ticker(context.get("ticker"))
    page_title = str(context.get("page_title") or context.get("page_path") or "目前頁面")
    lines = [f"目前頁面: {page_title} ({context.get('page_path') or '-'})"]
    sources: list[str] = []

    if ticker:
        lines.append(f"Ticker: {ticker}")
        row, source = _candidate_row(candidates, ticker)
        if row:
            lines.append(f"{source}: {json.dumps(row, ensure_ascii=False, sort_keys=True)}")
            sources.append(source or "candidate artifact")

        options = _load_json(reports / "options_flow" / "latest.json")
        if isinstance(options, dict):
            signal = _find_ticker_row(options.get("signals"), ticker)
            if signal:
                compact = _compact(signal, (
                    "ticker", "flow_score", "verdict", "premium", "call_put",
                    "direction", "as_of",
                ))
                if options.get("as_of") and "as_of" not in compact:
                    compact["as_of"] = options.get("as_of")
                lines.append(
                    "reports/options_flow/latest.json: "
                    + json.dumps(compact, ensure_ascii=False, sort_keys=True)
                )
                sources.append("reports/options_flow/latest.json")

        trade_state = _load_json(reports / "trade_state" / "latest.json")
        if isinstance(trade_state, dict):
            row = _find_ticker_row(trade_state.get("rows"), ticker)
            if row:
                lines.append(
                    "reports/trade_state/latest.json: "
                    + json.dumps(_compact(row, (
                        "ticker", "signal", "cycle", "ce_trend", "quality",
                        "main_net_latest", "options_flow_score",
                    )), ensure_ascii=False, sort_keys=True)
                )
                sources.append("reports/trade_state/latest.json")

        risk = _load_json(reports / "risk_guard" / "latest.json")
        if isinstance(risk, dict):
            row = _find_ticker_row(risk.get("rows") or risk.get("positions"), ticker)
            if row:
                lines.append(
                    "reports/risk_guard/latest.json: "
                    + json.dumps(_compact(row, (
                        "ticker", "risk", "risk_level", "stop", "status",
                    )), ensure_ascii=False, sort_keys=True)
                )
                sources.append("reports/risk_guard/latest.json")

    return {
        "page_path": context.get("page_path"),
        "page_title": page_title,
        "ticker": ticker,
        "summary": "\n".join(lines),
        "sources": sources,
    }


def _history_block(history: list[dict[str, str]], limit: int = 8) -> str:
    rows = []
    for msg in history[-limit:]:
        role = "使用者" if msg.get("role") == "user" else "助理"
        content = re.sub(r"\s+", " ", str(msg.get("content") or "")).strip()
        if content:
            rows.append(f"{role}: {content[:1200]}")
    return "\n".join(rows) if rows else "無"


def build_messages(
    question: str,
    history: list[dict[str, str]],
    mode: str,
    context_attachment: dict[str, Any] | None,
) -> tuple[str, str]:
    """Build system and user messages for either chat mode."""
    deep = mode == DEEP_MODE
    system = (
        "你是 Quant Radar 內建 AI 交易決策輔助。請用繁體中文回答。"
        "你可以協助釐清交易想法、整理證據、反方論點、風險、失效條件與下一步檢查，"
        "但不得給出保證獲利、不得宣稱必買/必賣，也不得替使用者下單。"
        "每次涉及交易判斷都要標示「非投資建議」。"
        "請清楚區分：本機已驗證資料、外部查詢事實、以及你的推論。"
        "如果資料不足，要直接說不足，不要補故事。"
    )
    if deep:
        system += (
            "目前是深度研究模式。可以查網路時，請標示來源、日期與資料時效；"
            "優先使用官方或一手來源，並列出反方與尚未驗證的部分。"
        )
    else:
        system += (
            "目前是快速問答模式。不要假裝查到了最新資料；若問題需要即時新聞、價格或規則，"
            "請建議切換深度研究或讓使用者提供資料。"
        )

    blocks = [
        f"模式: {mode if mode in MODES else QUICK_MODE}",
        f"最近對話:\n{_history_block(history)}",
    ]
    if context_attachment and context_attachment.get("summary"):
        blocks.append(f"已附加的本機驗證資料:\n{context_attachment['summary']}")
    blocks.append(f"使用者問題:\n{question.strip()}")
    return system, "\n\n".join(blocks)


def answer_chat(
    question: str,
    history: list[dict[str, str]],
    mode: str,
    context_attachment: dict[str, Any] | None,
    provider: str = "codex",
    client_factory: Any | None = None,
) -> str:
    """Route a chat turn through the Codex SDK."""
    if client_factory is None:
        try:
            from scripts.llm_client import LLMClient
        except ImportError:  # pragma: no cover
            from llm_client import LLMClient  # type: ignore
        client_factory = LLMClient

    selected_mode = mode if mode in MODES else QUICK_MODE
    system, user = build_messages(question, history, selected_mode, context_attachment)
    if selected_mode == DEEP_MODE:
        client = client_factory(provider="codex", model=DEEP_MODEL)
        return client.chat_agentic(
            system,
            user,
            allowed_tools=("WebSearch", "WebFetch"),
            max_turns=8,
            max_tokens=4096,
        )

    client = client_factory(provider=provider, model=QUICK_MODEL)
    return client.chat(system, user, max_tokens=2048)
