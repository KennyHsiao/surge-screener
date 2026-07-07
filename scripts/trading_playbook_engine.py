#!/usr/bin/env python3
"""Course playbook overlay for the options cockpit.

This module translates existing platform context into a small set of course
playbooks. It does not fetch market data and it does not override the canonical
Options Cockpit verdict. Hard blocks are reserved for platform risk gates or
prohibited structures; course guardrails are warnings unless explicitly unsafe.
"""

from __future__ import annotations

from typing import Any


PLAYBOOK_SWING_LONG_CALL = "Swing Long Call"
PLAYBOOK_JUMP_LONG_CALL = "Jump Trade Long Call"
PLAYBOOK_BULL_CALL_SPREAD = "Bull Call Spread"
PLAYBOOK_PROTECTIVE_HEDGE = "Protective Put / Swing Hedge"
PLAYBOOK_SKIP_WAIT = "Skip / Wait"

ACTIONABLE = "actionable"
WATCH = "watch"
HEDGE_ONLY = "hedge_only"
SKIP = "skip"

IV_ELEVATED = 60.0

_BULLISH_CYCLES = {"Cycle1", "Cycle5", "Cycle6"}
_HEDGE_CYCLES = {"Cycle2/3", "Cycle4", "Cycle5", "Cycle6"}
_RISK_NEW_LONG_BLOCK = {"REDUCE", "EXIT"}
_RISK_HEDGE = {"WATCH", "REDUCE", "EXIT"}

_COURSE = "Notion trading course"
_PLATFORM = "Platform risk policy"

_SOURCES = {
    PLAYBOOK_SWING_LONG_CALL: ["Swing Trade", "Greeks", "波動率與時間", "風控"],
    PLAYBOOK_JUMP_LONG_CALL: ["Jump Trade", "Swing Trade", "波動率與時間", "風控"],
    PLAYBOOK_BULL_CALL_SPREAD: ["策略庫", "波動率與時間", "Greeks"],
    PLAYBOOK_PROTECTIVE_HEDGE: ["策略庫", "風控"],
    PLAYBOOK_SKIP_WAIT: ["風控", "高風險限制"],
}


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        return None if out != out else out
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
        return None
    return bool(value)


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _condition(
    cid: str,
    label: str,
    severity: str,
    source: str = _COURSE,
    short_label: str | None = None,
) -> dict:
    return {
        "id": cid,
        "label": label,
        "severity": severity,
        "source": source,
        "short_label": short_label or label,
    }


def _append_once(items: list[dict], item: dict) -> None:
    if not any(existing.get("id") == item.get("id") for existing in items):
        items.append(item)


def _iv_value(ctx: dict[str, Any]) -> float | None:
    return _num(ctx.get("iv_rank")) if _num(ctx.get("iv_rank")) is not None else _num(ctx.get("iv_percentile"))


def _is_proxy_iv(ctx: dict[str, Any]) -> bool:
    source = _text(ctx.get("iv_rank_source")).lower()
    if not source:
        return False
    return not source.startswith("iv_history")


def _is_bullish_context(ctx: dict[str, Any]) -> bool:
    bias = _text(ctx.get("direction_bias")).lower()
    trend = _text(ctx.get("trend"))
    ce_trend = _text(ctx.get("ce_trend")).lower()
    above_vwap = _bool_or_none(ctx.get("above_vwap"))
    breakout = _bool_or_none(ctx.get("breakout"))

    if bias in {"bullish", "long", "看多", "偏多"}:
        return True
    if "上升" in trend or "偏多" in trend:
        return True
    if ce_trend == "bullish" and above_vwap is True:
        return True
    if above_vwap is True and breakout is True:
        return True
    return False


def _warnings(ctx: dict[str, Any]) -> list[dict]:
    warnings: list[dict] = []
    dte = _num(ctx.get("dte"))
    iv = _iv_value(ctx)
    earnings = _bool_or_none(ctx.get("earnings_within_dte"))
    cycle = _text(ctx.get("cycle"))
    contract_payoffable = _bool_or_none(ctx.get("contract_payoffable"))
    contract_executable = _bool_or_none(ctx.get("contract_executable"))
    spread_pct = _num(ctx.get("contract_spread_pct"))

    if dte is None:
        _append_once(warnings, _condition("dte_missing", "DTE 資料不足，不能判斷 3 週時間緩衝。", "warn", short_label="DTE缺口"))
    elif dte < 21:
        _append_once(warnings, _condition("dte_under_21", "DTE < 21；Notion 建議至少 3 週，先警示不封鎖。", "warn", short_label="DTE<21"))

    if iv is None:
        _append_once(warnings, _condition("iv_missing", "IV Rank / Percentile 資料不足。", "warn", short_label="IV缺口"))
    elif iv >= IV_ELEVATED:
        _append_once(warnings, _condition("iv_elevated", "IV 偏高；單買 Call 需注意 IV crush，優先考慮價差。", "warn", short_label="IV偏高"))

    if _is_proxy_iv(ctx):
        _append_once(warnings, _condition("iv_source_proxy", "IV Rank 尚非完整歷史 percentile，目前含 proxy。", "warn", _PLATFORM, "IV proxy"))

    if earnings is None:
        _append_once(warnings, _condition("earnings_unknown", "財報日期未知，需人工確認事件風險。", "warn", _PLATFORM, "財報未知"))

    if not cycle:
        _append_once(warnings, _condition("cycle_missing", "Cycle 資料不足；若 cockpit 已偏多，只能作較低信心判斷。", "warn", short_label="Cycle缺口"))

    if contract_payoffable is False:
        _append_once(warnings, _condition("contract_not_payoffable", "合約權利金/IV 不完整，無法完整估算 payoff。", "warn", _PLATFORM, "Payoff缺口"))
    if contract_executable is False:
        _append_once(warnings, _condition("contract_not_executable", "候選合約缺雙邊報價或流動性不足。", "warn", _PLATFORM, "不可成交"))
    if spread_pct is not None and spread_pct > 12:
        _append_once(warnings, _condition("spread_wide", "Bid/Ask 價差偏寬，需人工看深度。", "warn", _PLATFORM, "價差偏寬"))

    return warnings


def _global_blocks(ctx: dict[str, Any]) -> tuple[list[dict], set[str]]:
    blocks: list[dict] = []
    fatal: set[str] = set()

    ticker = _text(ctx.get("ticker"))
    verdict = _upper(ctx.get("cockpit_verdict"))
    risk_status = _upper(ctx.get("risk_status"))
    earnings = _bool_or_none(ctx.get("earnings_within_dte"))
    requested = _text(ctx.get("requested_structure")).lower().replace("-", " ")

    if not ticker:
        _append_once(blocks, _condition("ticker_missing", "缺 ticker，無法建立 playbook context。", "block", _PLATFORM, "缺ticker"))
        fatal.add("ticker_missing")

    if verdict == "AVOID":
        _append_once(blocks, _condition("cockpit_avoid", "Options Cockpit 已判定 AVOID；課程 playbook 不覆蓋平台風控。", "block", _PLATFORM, "AVOID"))
        fatal.add("cockpit_avoid")

    if requested in {"naked call", "nakedcall", "裸賣 call", "裸賣call", "裸 call", "裸call"}:
        _append_once(blocks, _condition("naked_call_prohibited", "Naked Call 風險未定義，平台不推薦。", "block", _COURSE, "Naked Call"))
        fatal.add("naked_call_prohibited")

    if risk_status in _RISK_NEW_LONG_BLOCK:
        _append_once(blocks, _condition("risk_reduce_exit_new_long", "Risk Guard 為 REDUCE/EXIT；禁止新增 Long Call 風險。", "block", _PLATFORM, "Risk REDUCE/EXIT"))

    if earnings is True:
        _append_once(blocks, _condition("earnings_within_dte", "財報落在合約 DTE 內；long premium 受 IV crush 風險阻擋。", "block", _PLATFORM, "財報DTE內"))

    return blocks, fatal


def _is_swing_eligible(ctx: dict[str, Any], warnings: list[dict]) -> bool:
    verdict = _upper(ctx.get("cockpit_verdict"))
    cycle = _text(ctx.get("cycle"))
    bullish = _is_bullish_context(ctx)

    if cycle in _BULLISH_CYCLES and bullish:
        return True
    if not cycle and verdict == "GO" and bullish:
        return True
    return False


def _needs_hedge(ctx: dict[str, Any]) -> bool:
    has_holding = bool(_bool_or_none(ctx.get("has_long_holding")))
    if not has_holding:
        return False
    risk_status = _upper(ctx.get("risk_status"))
    cycle = _text(ctx.get("cycle"))
    return risk_status in _RISK_HEDGE or cycle in _HEDGE_CYCLES


def _actionability(ctx: dict[str, Any], default: str) -> str:
    if default in {SKIP, HEDGE_ONLY}:
        return default
    return ACTIONABLE if _upper(ctx.get("cockpit_verdict")) == "GO" else WATCH


def _result(
    *,
    playbook: str,
    actionability: str,
    structure: str,
    required: list[dict],
    warnings: list[dict],
    blocks: list[dict],
    info: list[dict] | None = None,
) -> dict:
    return {
        "primary_playbook": playbook,
        "actionability": actionability,
        "structure": structure,
        "required_conditions": required,
        "warnings": warnings,
        "blocks": blocks,
        "info": info or [],
        "course_sources": _SOURCES.get(playbook, []),
    }


def evaluate_context(ctx: dict[str, Any] | None) -> dict:
    """Evaluate one ticker context into a V1 course playbook decision."""
    context = dict(ctx or {})
    warnings = _warnings(context)
    blocks, fatal_blocks = _global_blocks(context)

    has_new_long_block = any(item.get("id") in {"risk_reduce_exit_new_long", "earnings_within_dte"} for item in blocks)
    if fatal_blocks:
        return _result(
            playbook=PLAYBOOK_SKIP_WAIT,
            actionability=SKIP,
            structure="不交易",
            required=[],
            warnings=warnings,
            blocks=blocks,
        )

    if _needs_hedge(context):
        required = [
            _condition("has_long_holding", "已有多頭持倉。", "required", _PLATFORM),
            _condition("risk_or_cycle_hedge", "Risk Guard 或 Cycle 進入需要保護的區間。", "required"),
        ]
        return _result(
            playbook=PLAYBOOK_PROTECTIVE_HEDGE,
            actionability=HEDGE_ONLY,
            structure="Protective Put / Swing Hedge",
            required=required,
            warnings=warnings,
            blocks=blocks,
        )

    if has_new_long_block:
        return _result(
            playbook=PLAYBOOK_SKIP_WAIT,
            actionability=SKIP,
            structure="不交易",
            required=[],
            warnings=warnings,
            blocks=blocks,
        )

    swing_eligible = _is_swing_eligible(context, warnings)
    iv = _iv_value(context)
    iv_elevated = iv is not None and iv >= IV_ELEVATED
    jump_ready = _bool_or_none(context.get("bollinger_1sd_to_2sd")) is True and _bool_or_none(context.get("beyond_2sd")) is not True

    if not swing_eligible:
        _append_once(warnings, _condition("trend_not_confirmed", "趨勢 / Cycle 尚未滿足 V1 多頭 playbook。", "warn", short_label="趨勢未確認"))
        return _result(
            playbook=PLAYBOOK_SKIP_WAIT,
            actionability=WATCH,
            structure="不交易",
            required=[],
            warnings=warnings,
            blocks=blocks,
        )

    base_required = [
        _condition("no_platform_block", "無 cockpit AVOID / 新開倉硬風控。", "required", _PLATFORM),
        _condition("bullish_context", "方向偏多，且 Cycle 或 cockpit 支持多方。", "required"),
    ]

    if iv_elevated:
        return _result(
            playbook=PLAYBOOK_BULL_CALL_SPREAD,
            actionability=_actionability(context, ACTIONABLE),
            structure="Bull Call Spread",
            required=base_required + [
                _condition("iv_elevated_structure", "IV 偏高，使用價差降低 vega / 權利金風險。", "required"),
            ],
            warnings=warnings,
            blocks=blocks,
        )

    if jump_ready:
        return _result(
            playbook=PLAYBOOK_JUMP_LONG_CALL,
            actionability=_actionability(context, ACTIONABLE),
            structure="單買 Call",
            required=base_required + [
                _condition("bollinger_jump_1sd_to_2sd", "價格由 1σ 進入 2σ 加速段。", "required"),
            ],
            warnings=warnings,
            blocks=blocks,
        )

    _append_once(warnings, _condition("jump_signal_missing", "尚未看到 1σ -> 2σ Jump 加速訊號；先以 Swing 判斷。", "warn", short_label="Jump未觸發"))
    return _result(
        playbook=PLAYBOOK_SWING_LONG_CALL,
        actionability=_actionability(context, ACTIONABLE),
        structure="單買 Call",
        required=base_required,
        warnings=warnings,
        blocks=blocks,
    )
