#!/usr/bin/env python3
"""Trade State board data assembly.

This module keeps Streamlit rendering thin. It merges existing local artifacts
into a trader-facing state board:

- Cycle: local rule mapping from the Notion course notes.
- CE: Chandelier Exit when exact inputs exist; otherwise a labeled trend proxy.
- Signal: action-state label derived from Cycle, CE, volatility, and risk state.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from runtime_paths import REPO, candidate_output_path
    import industry_roles
except ImportError:  # imported as scripts.trade_state
    from scripts.runtime_paths import REPO, candidate_output_path
    from scripts import industry_roles


RISK_STOP = {"EXIT"}
RISK_CAUTION = {"WATCH", "REDUCE"}
TAKE_PROFIT_CYCLES = {"Cycle4", "Cycle5", "Cycle6"}

SIGNAL_ZH = {
    "holding": "持有",
    "take_profit": "停利/降倉",
    "stop_loss": "停損/出場",
    "none": "等待",
}

CE_ZH = {
    "bullish": "偏多",
    "bearish": "偏空",
    "neutral": "中性",
}

SOURCE_ZH = {
    "chandelier": "CE",
    "trend_proxy": "Proxy",
}

EASTMONEY_MONEY_FLOW_CAVEAT = "東財資金流模型；非 SEC 機構持倉、非逐筆券商真實買賣。"
MONEY_FLOW_GAP_LABEL = "東財資金流資料缺口，維持 Proxy 判讀"

STORY_TEMPLATES = {
    "all": {
        "label": "全部",
        "title": "交易狀態摘牌",
        "keywords": (),
    },
    "ai_infra": {
        "label": "半導體 / AI infra",
        "title": "半導體 / AI infra 摘牌",
        "keywords": (
            "ai", "infra", "semiconductor", "semi", "gpu", "asic", "accelerator",
            "server", "odm", "memory", "hbm", "dram", "nand", "packaging", "osat",
            "cowos", "networking", "optical", "foundry", "equipment", "eda",
            "半導體", "先進封裝", "記憶體", "伺服器", "晶圓", "設備", "矽光子",
        ),
    },
    "robotics": {
        "label": "機器人 / Physical AI",
        "title": "機器人 / Physical AI 摘牌",
        "keywords": (
            "robot", "robotics", "automation", "physical ai", "lidar", "vision",
            "surgical", "warehouse", "機器人", "自動化", "視覺", "感測",
        ),
    },
    "space": {
        "label": "Space",
        "title": "Space / Satellite 摘牌",
        "keywords": (
            "space", "satellite", "launch", "leo", "aerospace",
            "太空", "航太", "衛星", "低軌",
        ),
    },
}

CYCLE_META = {
    "Cycle1": {
        "label": "C1 趨勢延續",
        "note": "Notion: 穩定上升期，時間寬幅最大；順勢持有，不因 RSI 超買逆勢放空。",
    },
    "Cycle2/3": {
        "label": "C2/3 轉換窗口",
        "note": "Notion: 時間窗口較短，價格容易上下亂打；等趨勢確認。",
    },
    "Cycle4": {
        "label": "C4 下跌段",
        "note": "Notion: 穩定下跌期；可停利、避開，空方需趨勢確認。",
    },
    "Cycle5": {
        "label": "C5 反轉測試",
        "note": "Notion: Cycle4 轉 Cycle5 需經過多個黃金交叉；先準備，不代表立刻重倉。",
    },
    "Cycle6": {
        "label": "C6 高波動尾段",
        "note": "Notion: 屬短時間窗口；搭配風控，偏停利/觀察。",
    },
}


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _first_num(*sources: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in keys:
            value = _num(source.get(key))
            if value is not None:
                return value
    return None


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _signal_zh(signal: str | None) -> str:
    return SIGNAL_ZH.get(str(signal or ""), str(signal or "-"))


def _ce_zh(trend: str | None) -> str:
    return CE_ZH.get(str(trend or ""), str(trend or "-"))


def _source_zh(source: str | None) -> str:
    return SOURCE_ZH.get(str(source or ""), str(source or "-"))


def _story_text(value: Any) -> str:
    text = str(value if value is not None and value != "" else "-")
    return text.replace("|", "/")


def _data_quality(*, ce_source: str | None, atr_pct: float | None, industry_role_status: str | None) -> list[str]:
    quality: list[str] = []
    if ce_source == "trend_proxy":
        quality.append("Proxy 訊號")
    if atr_pct is None:
        quality.append("缺 ATR%")
    if industry_role_status == "unclassified":
        quality.append("未分類")
    elif industry_role_status == "suggested":
        quality.append("分類待審核")
    return quality or ["完整"]


def compute_ce_trend(
    *,
    price: float | None,
    atr: float | None = None,
    highest_high: float | None = None,
    lowest_low: float | None = None,
    multiplier: float = 3.0,
    ma50: float | None = None,
    ma200: float | None = None,
    price_above_vwap: bool | None = None,
) -> dict[str, Any]:
    """Return CE trend state.

    Exact mode uses the common Chandelier Exit formula:
    long stop = highest high - ATR * multiplier
    short stop = lowest low + ATR * multiplier

    When high/low history is unavailable, the result is explicitly marked
    `trend_proxy` and uses price vs MA/VWAP evidence. UI should show this source.
    """
    p = _num(price)
    a = _num(atr)
    hh = _num(highest_high)
    ll = _num(lowest_low)
    if p is not None and a is not None and hh is not None and ll is not None:
        long_stop = round(hh - a * multiplier, 2)
        short_stop = round(ll + a * multiplier, 2)
        upper_ref = max(long_stop, short_stop)
        lower_ref = min(long_stop, short_stop)
        if p > upper_ref:
            trend = "bullish"
            stop = long_stop
        elif p < lower_ref:
            trend = "bearish"
            stop = short_stop
        else:
            trend = "neutral"
            stop = long_stop if abs(p - long_stop) <= abs(p - short_stop) else short_stop
        distance_pct = round((p - stop) / p * 100, 2) if p else None
        return {
            "trend": trend,
            "source": "chandelier",
            "long_stop": long_stop,
            "short_stop": short_stop,
            "stop": stop,
            "distance_pct": distance_pct,
        }

    m50, m200 = _num(ma50), _num(ma200)
    above_vwap = price_above_vwap
    if p is None:
        trend = "neutral"
    elif m50 is not None and p >= m50 and (m200 is None or p >= m200) and above_vwap is not False:
        trend = "bullish"
    elif m50 is not None and p < m50 and above_vwap is not True:
        trend = "bearish"
    else:
        trend = "neutral"
    stop = m50
    distance_pct = round((p - stop) / p * 100, 2) if p and stop else None
    return {
        "trend": trend,
        "source": "trend_proxy",
        "long_stop": None,
        "short_stop": None,
        "stop": stop,
        "distance_pct": distance_pct,
    }


def classify_cycle(row: dict[str, Any]) -> dict[str, str]:
    """Map available technical fields into the Notion Cycle vocabulary."""
    price = _num(row.get("last_price", row.get("price")))
    ma50 = _num(row.get("ma50"))
    ma200 = _num(row.get("ma200"))
    macd = _num(row.get("macd_current"))
    risk_status = str(row.get("risk_status") or "").upper()
    golden = _bool(row.get("macd_golden_cross_10d"))
    zero_cross = _bool(row.get("macd_zero_cross_10d"))

    if risk_status in {"REDUCE", "EXIT"}:
        cycle = "Cycle4"
    elif (
        price is not None and ma50 is not None and ma200 is not None
        and price >= ma50 and price >= ma200
        and (macd is None or macd >= 0)
    ):
        cycle = "Cycle1"
    elif (
        price is not None and ma200 is not None
        and price >= ma200
        and (golden or zero_cross)
        and (macd is None or macd <= 0.25)
    ):
        cycle = "Cycle5"
    elif price is not None and ma50 is not None and price < ma50 and (macd is None or macd < 0):
        cycle = "Cycle4"
    else:
        cycle = "Cycle2/3"
    meta = CYCLE_META[cycle]
    return {"cycle": cycle, "label": meta["label"], "note": meta["note"]}


def map_trade_signal(row: dict[str, Any]) -> dict[str, str]:
    """Compress Cycle, CE and risk into a trader-facing action-state label."""
    cycle = str(row.get("cycle") or "")
    ce_trend = str(row.get("ce_trend") or "neutral").lower()
    risk_status = str(row.get("risk_status") or "NORMAL").upper()
    atr_pct = _num(row.get("atr_pct"))

    if risk_status in RISK_STOP or (cycle == "Cycle4" and ce_trend == "bearish"):
        return {
            "signal": "stop_loss",
            "reason": "風險狀態或 Cycle4 + CE bearish 已進入失效/出場區。",
        }
    if risk_status == "REDUCE" or cycle in TAKE_PROFIT_CYCLES or ce_trend == "bearish":
        return {
            "signal": "take_profit",
            "reason": "Notion 風控：Cycle4/5/6 偏停利；CE/Proxy 或 risk 已轉弱。",
        }
    if cycle == "Cycle1" and ce_trend == "bullish" and risk_status in {"NORMAL", "WATCH"}:
        suffix = "；ATR% 偏高，部位需縮小。" if atr_pct is not None and atr_pct >= 8 else ""
        return {"signal": "holding", "reason": f"Cycle1 趨勢延續且 CE/Proxy 支持多方{suffix}"}
    return {
        "signal": "none",
        "reason": "Cycle/CE/風險訊號未形成一致方向，等待確認。",
    }


def _theme_items(baskets: dict[str, Any]) -> list[tuple[str, list[str]]]:
    if isinstance(baskets.get("themes"), dict):
        return [
            (name, [str(t).upper() for t in (cfg.get("tickers") or [])])
            for name, cfg in baskets["themes"].items()
            if isinstance(cfg, dict)
        ]
    if isinstance(baskets.get("baskets"), list):
        return [
            (str(item.get("theme") or item.get("name") or ""), [str(t).upper() for t in item.get("tickers", [])])
            for item in baskets["baskets"]
            if isinstance(item, dict)
        ]
    return []


def theme_for_ticker(ticker: str, baskets: dict[str, Any] | None) -> str:
    sym = (ticker or "").upper()
    if not sym or not isinstance(baskets, dict):
        return "未分類"
    for theme, tickers in _theme_items(baskets):
        if sym in tickers:
            return theme or "未分類"
    return "未分類"


def _candidate_rows(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    rows = data.get("tickers") or data.get("ranked_candidates") or []
    return [row for row in rows if isinstance(row, dict) and row.get("ticker")]


def _social_map(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}
    rows = data.get("tickers") or data.get("picks") or []
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or row.get("ticker") or "").upper().lstrip("$")
        if not sym:
            continue
        mentioned_by = row.get("mentioned_by") or []
        out[sym] = {
            "mentions": int(row.get("count") or len(mentioned_by) or 0),
            "mentioned_by": mentioned_by,
            "social_skew": row.get("skew") or row.get("stance") or "neutral",
            "social_note": row.get("note") or "",
        }
    return out


def _options_map(data: Any) -> dict[str, dict[str, Any]]:
    rows = data.get("signals") if isinstance(data, dict) else []
    out = {}
    for row in rows or []:
        if isinstance(row, dict) and row.get("ticker"):
            out[str(row["ticker"]).upper()] = row
    return out


def _risk_map(data: Any) -> dict[str, dict[str, Any]]:
    rows = data.get("rows") if isinstance(data, dict) else []
    out = {}
    for row in rows or []:
        if isinstance(row, dict) and row.get("ticker"):
            out[str(row["ticker"]).upper()] = row
    return out


def _money_flow_context(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"publishable": False, "source": "proxy", "by_ticker": {}}
    publishable = bool(data.get("publishable"))
    source = str(data.get("source") or "eastmoney_push2his")
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("ticker") or "").upper().lstrip("$")
        if not sym:
            continue
        current = by_ticker.get(sym)
        row_date = str(row.get("date") or row.get("flow_date") or "")
        current_date = str(current.get("date") or current.get("flow_date") or "") if current else ""
        if current is None or row_date >= current_date:
            by_ticker[sym] = row
    return {"publishable": publishable, "source": source, "by_ticker": by_ticker}


def _money_flow_label(row: dict[str, Any]) -> str:
    main_net = _num(row.get("main_net"))
    small_net = _num(row.get("small_net"))
    change_pct = _num(row.get("change_pct"))
    if main_net is not None and main_net > 0:
        return "主力流入支持持有"
    if change_pct is not None and change_pct > 0 and main_net is not None and main_net < 0:
        return "上漲但主力流出，追價風險"
    if small_net is not None and small_net > 0 and main_net is not None and main_net < 0:
        return "小單流入、主力流出，偏散戶追價"
    if main_net is not None and main_net < 0:
        return "主力流出，降低追價"
    return "資金流中性"


def _money_flow_evidence(sym: str, context: dict[str, Any]) -> dict[str, Any]:
    by_ticker = context.get("by_ticker") if isinstance(context, dict) else {}
    row = by_ticker.get(sym) if isinstance(by_ticker, dict) else None
    publishable = bool(context.get("publishable")) if isinstance(context, dict) else False
    if not publishable or not isinstance(row, dict):
        return {
            "publishable": False,
            "source": "proxy",
            "date": None,
            "main_net": None,
            "main_pct": None,
            "small_net": None,
            "label": MONEY_FLOW_GAP_LABEL,
            "caveat": MONEY_FLOW_GAP_LABEL,
        }
    return {
        "publishable": True,
        "source": row.get("source") or context.get("source") or "eastmoney_push2his",
        "date": row.get("date") or row.get("flow_date"),
        "main_net": _num(row.get("main_net")),
        "main_pct": _num(row.get("main_pct")),
        "small_net": _num(row.get("small_net")),
        "label": _money_flow_label(row),
        "caveat": EASTMONEY_MONEY_FLOW_CAVEAT,
    }


def _merge_sources(candidate_rows: list[dict[str, Any]], social: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {str(row.get("ticker")).upper(): dict(row) for row in candidate_rows}
    for sym, srow in social.items():
        merged.setdefault(sym, {"ticker": sym})
        merged[sym].update({k: v for k, v in srow.items() if k not in {"ticker"}})
    return list(merged.values())


def build_trade_state_rows(
    *,
    reports_dir: Path | str | None = None,
    content_dir: Path | str | None = None,
    candidate_path: Path | str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    content = Path(content_dir) if content_dir is not None else REPO / "content"
    cpath = Path(candidate_path) if candidate_path is not None else candidate_output_path("ranked_candidates.json")

    candidates = _candidate_rows(_load_json(cpath))
    social = _social_map(_load_json(reports / "x_influencer_picks.json"))
    options = _options_map(_load_json(reports / "options_flow" / "latest.json"))
    risks = _risk_map(_load_json(reports / "risk_guard" / "latest.json"))
    money_flow = _money_flow_context(_load_json(reports / "money_flow" / "latest.json"))
    baskets = _load_json(content / "theme_baskets.json") or {}
    role_taxonomy = industry_roles.load_taxonomy(content)
    role_overrides = industry_roles.load_overrides(content, reports_dir=reports)
    role_suggestions = industry_roles.load_suggestions(reports, content_dir=content)

    rows: list[dict[str, Any]] = []
    for row in _merge_sources(candidates, social):
        sym = str(row.get("ticker") or row.get("symbol") or "").upper().lstrip("$")
        if not sym:
            continue
        risk = risks.get(sym, {})
        opt = options.get(sym, {})
        tech = risk.get("technical") if isinstance(risk.get("technical"), dict) else {}

        price = _num(tech.get("price")) or _num(row.get("last_price")) or _num(opt.get("spot"))
        ma50 = _num(tech.get("ma50")) or _num(row.get("ma50"))
        ma200 = _num(tech.get("ma200")) or _num(row.get("ma200"))
        atr = _num(tech.get("atr14")) or _num(row.get("atr14"))
        highest_high = _first_num(
            tech,
            row,
            keys=(
                "highest_high_22d",
                "highest_high_21d",
                "highest_high_20d",
                "high_22d",
                "high_21d",
                "high_20d",
                "rolling_high_22d",
                "resistance_20d",
            ),
        )
        lowest_low = _first_num(
            tech,
            row,
            keys=(
                "lowest_low_22d",
                "lowest_low_21d",
                "lowest_low_20d",
                "low_22d",
                "low_21d",
                "low_20d",
                "rolling_low_22d",
                "support_20d",
            ),
        )
        atr_pct = round(atr / price * 100, 2) if atr is not None and price else None

        enriched = dict(row)
        enriched.update({
            "ticker": sym,
            "last_price": price,
            "ma50": ma50,
            "ma200": ma200,
            "risk_status": risk.get("status") or row.get("risk_status") or "NORMAL",
        })
        cycle = classify_cycle(enriched)
        ce = compute_ce_trend(
            price=price,
            atr=atr,
            highest_high=highest_high,
            lowest_low=lowest_low,
            ma50=ma50,
            ma200=ma200,
            price_above_vwap=tech.get("price_above_vwap"),
        )
        signal = map_trade_signal({
            "cycle": cycle["cycle"],
            "ce_trend": ce["trend"],
            "risk_status": enriched["risk_status"],
            "atr_pct": atr_pct,
        })
        mf = _money_flow_evidence(sym, money_flow)
        role = industry_roles.resolve_role(
            sym,
            taxonomy=role_taxonomy,
            overrides=role_overrides,
            suggestions=role_suggestions,
        )
        role_status = role.get("status", role["source"])
        quality = _data_quality(
            ce_source=ce["source"],
            atr_pct=atr_pct,
            industry_role_status=role_status,
        )

        invalidation = "資料不足"
        if ce.get("stop"):
            stop_label = "CE" if ce.get("source") == "chandelier" else "Proxy"
            invalidation = f"{stop_label} {ce['stop']:.2f}"
        elif ma50:
            invalidation = f"MA50 {ma50:.2f}"

        srow = social.get(sym, {})
        rows.append({
            "ticker": sym,
            "theme": theme_for_ticker(sym, baskets),
            "industry_role": role["display_role"],
            "industry_role_source": role["source"],
            "industry_role_status": role_status,
            "industry_role_confidence": role["confidence"],
            "data_quality": quality,
            "data_quality_label": " / ".join(quality),
            "mentions": int(srow.get("mentions", row.get("mentions", 0)) or 0),
            "mentioned_by": srow.get("mentioned_by", row.get("mentioned_by", [])) or [],
            "social_skew": srow.get("social_skew", row.get("social_skew", "neutral")),
            "rank_score": _num(row.get("rank_score")),
            "price": price,
            "atr": atr,
            "atr_pct": atr_pct,
            "cycle": cycle["cycle"],
            "cycle_label": cycle["label"],
            "cycle_note": cycle["note"],
            "ce_trend": ce["trend"],
            "ce_source": ce["source"],
            "ce_stop": ce.get("stop"),
            "ce_distance_pct": ce.get("distance_pct"),
            "risk_status": enriched["risk_status"],
            "risk_score": _num(risk.get("risk_score")),
            "flow_direction": opt.get("direction"),
            "flow_score": _num(opt.get("flow_score")),
            "money_flow": mf,
            "money_flow_publishable": mf["publishable"],
            "money_flow_source": mf["source"],
            "money_flow_date": mf["date"],
            "money_flow_main_net": mf["main_net"],
            "money_flow_main_pct": mf["main_pct"],
            "money_flow_small_net": mf["small_net"],
            "money_flow_label": mf["label"],
            "money_flow_caveat": mf["caveat"],
            "signal": signal["signal"],
            "signal_reason": signal["reason"],
            "invalidation": invalidation,
        })

    rows.sort(key=lambda r: (
        -(r.get("mentions") or 0),
        -(r.get("rank_score") or 0),
        -(r.get("flow_score") or 0),
        r.get("ticker") or "",
    ))
    return rows[: max(0, int(limit))]


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "count": len(rows),
        "cycle1": sum(1 for r in rows if r.get("cycle") == "Cycle1"),
        "cycle4_plus": sum(1 for r in rows if r.get("cycle") in TAKE_PROFIT_CYCLES),
        "ce_bullish": sum(1 for r in rows if r.get("ce_trend") == "bullish"),
        "ce_bearish": sum(1 for r in rows if r.get("ce_trend") == "bearish"),
        "holding": sum(1 for r in rows if r.get("signal") == "holding"),
        "take_profit": sum(1 for r in rows if r.get("signal") == "take_profit"),
        "stop_loss": sum(1 for r in rows if r.get("signal") == "stop_loss"),
    }


def _matches_story_template(row: dict[str, Any], template: str, custom_theme: str | None = None) -> bool:
    if custom_theme:
        return str(row.get("theme") or "") == custom_theme
    if template == "all":
        return True
    cfg = STORY_TEMPLATES.get(template, STORY_TEMPLATES["all"])
    keywords = cfg.get("keywords") or ()
    haystack = " ".join([
        str(row.get("theme") or ""),
        str(row.get("industry_role") or ""),
        str(row.get("industry_role_source") or ""),
        str(row.get("ticker") or ""),
    ]).lower()
    return any(str(keyword).lower() in haystack for keyword in keywords)


def story_rows(
    rows: list[dict[str, Any]],
    *,
    template: str = "all",
    custom_theme: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    selected = [
        row for row in rows
        if _matches_story_template(row, template, custom_theme)
    ]
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    out = []
    for row in selected:
        source = _source_zh(row.get("ce_source"))
        out.append({
            "ticker": row.get("ticker", ""),
            "theme": row.get("theme") or "未分類",
            "industry_role": row.get("industry_role") or "未分類",
            "mentions": row.get("mentions", 0),
            "atr_pct": row.get("atr_pct"),
            "cycle": row.get("cycle", "-"),
            "trend_source": f"{_ce_zh(row.get('ce_trend'))} / {source}",
            "signal": _signal_zh(row.get("signal")),
            "data_quality": row.get("data_quality_label") or "完整",
        })
    return out


def story_copy(
    rows: list[dict[str, Any]],
    title: str | None = None,
    *,
    template: str = "all",
    custom_theme: str | None = None,
    limit: int = 30,
) -> str:
    cfg = STORY_TEMPLATES.get(template, STORY_TEMPLATES["all"])
    story_title = title or (f"{custom_theme} 摘牌" if custom_theme else str(cfg["title"]))
    header = (
        f"{story_title}\n"
        "Cycle = Notion 課程階段；CE/Proxy = 有標的日線 high/low/ATR 時用 Chandelier Exit，"
        "否則用 MA/VWAP Proxy\n"
    )
    preview = story_rows(rows, template=template, custom_theme=custom_theme, limit=limit)
    lines = [
        "| Ticker | 主題 | 產業鏈角色 | 提及 | ATR% | Cycle | 趨勢來源 | 訊號 |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for r in preview:
        atr = "-" if r.get("atr_pct") is None else f"{float(r['atr_pct']):.1f}"
        lines.append(
            f"| {_story_text(r.get('ticker'))} | {_story_text(r.get('theme'))} | "
            f"{_story_text(r.get('industry_role'))} | {r.get('mentions', 0)} | {atr} | "
            f"{_story_text(r.get('cycle'))} | {_story_text(r.get('trend_source'))} | "
            f"{_story_text(r.get('signal'))} |"
        )
    return header + "\n".join(lines)


def _today() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _snapshot_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("cycle"):
        reasons.append(f"{row.get('cycle')} {row.get('cycle_label') or ''}".strip())
    if row.get("signal_reason"):
        reasons.append(str(row.get("signal_reason")))
    if row.get("money_flow_label"):
        reasons.append(str(row.get("money_flow_label")))
    if row.get("data_quality_label"):
        reasons.append(f"資料狀態: {row.get('data_quality_label')}")
    return reasons


def _snapshot_sources(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle": "notion_rule",
        "ce": row.get("ce_source"),
        "money_flow": row.get("money_flow_source"),
        "options_flow": "options_flow/latest.json" if row.get("flow_score") is not None else None,
        "industry_role": row.get("industry_role_source"),
        "social": "x_influencer_picks" if row.get("mentions") else None,
    }


def build_trade_state_snapshot(
    rows: list[dict[str, Any]],
    *,
    as_of_date: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a stable historical snapshot from trade-state UI rows."""
    snapshot_date = str(as_of_date or _today())[:10]
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        out_rows.append({
            "as_of_date": snapshot_date,
            "ticker": ticker,
            "price": _num(row.get("price")),
            "cycle": row.get("cycle"),
            "cycle_source": "notion_rule",
            "ce_trend": row.get("ce_trend"),
            "ce_source": row.get("ce_source"),
            "verdict": row.get("signal"),
            "risk_level": row.get("risk_status"),
            "industry_role": row.get("industry_role"),
            "industry_role_status": row.get("industry_role_status"),
            "main_net_latest": _num(row.get("money_flow_main_net")),
            "main_pct_latest": _num(row.get("money_flow_main_pct")),
            "atr_pct": _num(row.get("atr_pct")),
            "options_flow_score": _num(row.get("flow_score")),
            "social_mentions": int(row.get("mentions") or 0),
            "reasons_json": _json_blob(_snapshot_reasons(row)),
            "data_sources_json": _json_blob(_snapshot_sources(row)),
            "raw_row_json": _json_blob(row),
        })
    return {
        "as_of_date": snapshot_date,
        "generated_at": generated_at or _now_iso(),
        "source": "trade_state",
        "row_count": len(out_rows),
        "rows": out_rows,
    }


def write_trade_state_snapshot(
    snapshot: dict[str, Any],
    *,
    reports_dir: str | Path | None = None,
) -> Path:
    """Write reports/trade_state/YYYY-MM-DD.json and latest.json."""
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    as_of = str(snapshot.get("as_of_date") or _today())[:10]
    out_dir = reports / "trade_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{as_of}.json"
    latest = out_dir / "latest.json"
    body = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(tmp, out)
    latest_tmp = latest.with_suffix(latest.suffix + ".tmp")
    latest_tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(latest_tmp, latest)
    return out


def refresh_trade_state_snapshot(
    *,
    reports_dir: Path | str | None = None,
    content_dir: Path | str | None = None,
    candidate_path: Path | str | None = None,
    limit: int = 50,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    rows = build_trade_state_rows(
        reports_dir=reports,
        content_dir=content_dir,
        candidate_path=candidate_path,
        limit=limit,
    )
    snapshot = build_trade_state_snapshot(rows, as_of_date=as_of_date)
    out = write_trade_state_snapshot(snapshot, reports_dir=reports)
    return {"path": str(out), **snapshot}


if __name__ == "__main__":
    print(json.dumps(build_trade_state_rows(limit=20), ensure_ascii=False, indent=2))
