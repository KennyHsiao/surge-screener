"""美股 · 交易狀態 — Cycle / CE / Risk composite board.

This page is a decision layer, not a new data source. It reads existing local
artifacts and compresses them into trader-facing action states.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import _shared
from scripts import trade_state as engine


_SIGNAL_ZH = {
    "holding": "持有",
    "take_profit": "停利/降倉",
    "stop_loss": "停損/出場",
    "none": "等待",
}

_CE_ZH = {
    "bullish": "偏多",
    "bearish": "偏空",
    "neutral": "中性",
}

_SOURCE_ZH = {
    "chandelier": "CE",
    "trend_proxy": "Proxy",
}

_ROLE_STATUS_ZH = {
    "approved": "已核准",
    "suggested": "待審核",
    "unclassified": "未分類",
    "rejected": "已拒絕",
    "deferred": "延後",
}

_STORY_TEMPLATE_OPTIONS = {
    "全部": "all",
    "半導體 / AI infra": "ai_infra",
    "機器人 / Physical AI": "robotics",
    "Space": "space",
    "自訂主題": "custom_theme",
}


def _pct(value) -> str:
    return "-" if value is None else f"{float(value):.1f}%"


def _num(value, pattern: str = "{:.1f}") -> str:
    return "-" if value is None else pattern.format(float(value))


def _signal_color(signal: str) -> str:
    return {
        "holding": _shared.GREEN,
        "take_profit": _shared.AMBER,
        "stop_loss": _shared.RED,
        "none": _shared.MUTED,
    }.get(signal, _shared.MUTED)


def _ce_color(trend: str) -> str:
    return {
        "bullish": _shared.GREEN,
        "bearish": _shared.RED,
        "neutral": _shared.MUTED,
    }.get(trend, _shared.MUTED)


def _cycle_color(cycle: str) -> str:
    if cycle == "Cycle1":
        return _shared.GREEN
    if cycle == "Cycle4":
        return _shared.RED
    if cycle in {"Cycle5", "Cycle6"}:
        return _shared.AMBER
    return _shared.MUTED


def _role_color(status: str) -> str:
    return {
        "approved": _shared.GREEN,
        "suggested": _shared.AMBER,
        "deferred": _shared.BLUE,
        "rejected": _shared.MUTED,
        "unclassified": _shared.MUTED,
    }.get(status, _shared.MUTED)


def _quality_color(label: str) -> str:
    if label == "完整":
        return _shared.GREEN
    if "未分類" in label:
        return _shared.MUTED
    if "缺" in label or "Proxy" in label:
        return _shared.AMBER
    return _shared.BLUE


def _trend_source_label(row) -> str:
    trend = _CE_ZH.get(row["ce_trend"], row["ce_trend"])
    source = _SOURCE_ZH.get(row["ce_source"], row["ce_source"])
    return f"{trend} · {source}"


@st.cache_data(ttl=60, show_spinner=False)
def _load_rows(limit: int) -> list[dict]:
    return engine.build_trade_state_rows(limit=limit)


def _filter_rows(rows: list[dict], signal: str, cycle: str, ce: str, theme: str, role: str) -> list[dict]:
    out = rows
    if signal != "全部":
        out = [r for r in out if r.get("signal") == signal]
    if cycle != "全部":
        out = [r for r in out if r.get("cycle") == cycle]
    if ce != "全部":
        out = [r for r in out if r.get("ce_trend") == ce]
    if theme != "全部":
        out = [r for r in out if r.get("theme") == theme]
    if role != "全部":
        out = [r for r in out if r.get("industry_role") == role]
    return out


def _render_summary(rows: list[dict]) -> None:
    s = engine.summarize(rows)
    cols = st.columns(5)
    _shared.metric_card(cols[0], "標的", s["count"], help="目前交易狀態表中的標的數")
    _shared.metric_card(cols[1], "C1 持續", s["cycle1"], help="Notion Cycle1：穩定上升期")
    _shared.metric_card(cols[2], "CE/Proxy 偏多/偏空", f"{s['ce_bullish']} / {s['ce_bearish']}",
                        help="有標的日線 high/low/ATR 時為 Chandelier Exit；資料不足時為 proxy")
    _shared.metric_card(cols[3], "Holding", s["holding"], help="Cycle + CE + risk 同向偏多")
    _shared.metric_card(cols[4], "出場/停利", s["stop_loss"] + s["take_profit"],
                        help="stop_loss + take_profit")


def _display_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    view = pd.DataFrame({
        "Ticker": df["ticker"],
        "主題": df["theme"],
        "產業鏈角色": df["industry_role"],
        "角色狀態": df["industry_role_status"].map(lambda v: _ROLE_STATUS_ZH.get(v, v)),
        "資料狀態": df["data_quality_label"],
        "提及": df["mentions"],
        "Rank": df["rank_score"].map(lambda v: _num(v)),
        "價格": df["price"].map(lambda v: _num(v, "{:.2f}")),
        "ATR%": df["atr_pct"].map(_pct),
        "Cycle": df["cycle_label"],
        "CE/Proxy": df.apply(_trend_source_label, axis=1),
        "Risk": df["risk_status"],
        "訊號": df["signal"].map(lambda v: _SIGNAL_ZH.get(v, v)),
        "失效點": df["invalidation"],
    })
    return view


def _render_detail_header(row: dict) -> None:
    st.subheader(row["ticker"])
    st.caption(f"主題：{row.get('theme') or '未分類'}")
    st.caption("分類tag")
    role = row.get("industry_role") or "未分類"
    role_status = row.get("industry_role_status") or row.get("industry_role_source") or "unclassified"
    chips = [
        (role, _role_color(role_status)),
        (_ROLE_STATUS_ZH.get(role_status, role_status), _role_color(role_status)),
    ]
    chips.extend((label, _quality_color(label)) for label in (row.get("data_quality") or ["完整"]))
    _shared.chips_row(chips)


def _render_decision_strip(row: dict) -> None:
    top = st.columns([1, 1, 1])
    with top[0]:
        st.markdown(_shared.chip(row["cycle_label"], _cycle_color(row["cycle"])),
                    unsafe_allow_html=True)
        st.caption(row["cycle_note"])
    with top[1]:
        ce_text = f"CE/Proxy {_trend_source_label(row)}"
        st.markdown(_shared.chip(ce_text, _ce_color(row["ce_trend"])),
                    unsafe_allow_html=True)
        st.caption(f"失效點: {row['invalidation']} · 距離 {_pct(row.get('ce_distance_pct'))}")
    with top[2]:
        st.markdown(_shared.chip(_SIGNAL_ZH.get(row["signal"], row["signal"]),
                                 _signal_color(row["signal"])),
                    unsafe_allow_html=True)
        st.caption(row["signal_reason"])


def _render_compact_facts(row: dict) -> None:
    facts = pd.DataFrame([
        {"項目": "價格", "值": _num(row.get("price"), "{:.2f}")},
        {"項目": "ATR%", "值": _pct(row.get("atr_pct"))},
        {"項目": "Risk", "值": str(row.get("risk_status") or "-")},
        {"項目": "Options Flow", "值": str(row.get("flow_direction") or "-")},
        {"項目": "Flow Score", "值": _num(row.get("flow_score"))},
        {"項目": "社群提及", "值": str(row.get("mentions", 0))},
        {"項目": "資料狀態", "值": str(row.get("data_quality_label") or "完整")},
    ])
    st.dataframe(facts, width="stretch", hide_index=True, height=280)


def _render_detail(rows: list[dict]) -> None:
    if not rows:
        return
    options = [r["ticker"] for r in rows]
    selected = st.selectbox("單檔詳情", options, index=0)
    row = next(r for r in rows if r["ticker"] == selected)

    with st.container(border=True):
        _render_detail_header(row)
        _render_decision_strip(row)
        _render_compact_facts(row)

        mentioned_by = row.get("mentioned_by") or []
        if mentioned_by:
            st.caption("提及來源：" + ", ".join(f"@{h}" for h in mentioned_by[:8]))


def _story_preview_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Ticker": r.get("ticker"),
        "主題": r.get("theme"),
        "產業鏈角色": r.get("industry_role"),
        "提及": r.get("mentions"),
        "ATR%": _pct(r.get("atr_pct")),
        "Cycle": r.get("cycle"),
        "趨勢來源": r.get("trend_source"),
        "訊號": r.get("signal"),
        "資料狀態": r.get("data_quality"),
    } for r in rows])


def _render_story(rows: list[dict]) -> None:
    with st.container(border=True):
        st.caption("社群 / Story 文案預覽")
        controls = st.columns([1.2, 1.2, 1])
        with controls[0]:
            story_template = st.selectbox("版型", list(_STORY_TEMPLATE_OPTIONS))
        template_key = _STORY_TEMPLATE_OPTIONS[story_template]
        custom_theme = None
        if template_key == "custom_theme":
            with controls[1]:
                themes = sorted({r.get("theme") for r in rows if r.get("theme")})
                custom_theme = st.selectbox("自訂主題", themes or ["未分類"])
        with controls[2]:
            story_limit = st.slider("輸出檔數", 5, 50, 12, step=1)

        story_rows = engine.story_rows(
            rows,
            template=template_key,
            custom_theme=custom_theme,
            limit=story_limit,
        )
        st.markdown("##### 預覽")
        if story_rows:
            st.dataframe(_story_preview_df(story_rows), width="stretch", hide_index=True, height=320)
        else:
            st.info("目前沒有符合此版型的標的。")

        st.markdown("##### 複製文字")
        st.text_area(
            "可複製文字",
            value=engine.story_copy(
                rows,
                template=template_key,
                custom_theme=custom_theme,
                limit=story_limit,
            ),
            height=280,
            label_visibility="collapsed",
        )


def render() -> None:
    st.header("交易狀態")
    st.caption(
        "Cycle 來自 Notion 課程語意映射；CE/Proxy 有標的日線 high/low/ATR 時為 Chandelier Exit，資料不足時才用 proxy。"
    )

    with st.container(border=True):
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 1.2])
        with c1:
            limit = st.slider("標的上限", 10, 100, 50, step=10)

    rows = _load_rows(limit)
    if not rows:
        st.warning("目前沒有可用交易狀態資料。請先產生 ranked candidates 或 X influencer picks。")
        return

    with c2:
        signal_options = ["全部"] + sorted({r.get("signal") for r in rows if r.get("signal")})
        signal = st.selectbox("訊號", signal_options, format_func=lambda x: _SIGNAL_ZH.get(x, x))
    with c3:
        cycle = st.selectbox("Cycle", ["全部"] + sorted({r.get("cycle") for r in rows if r.get("cycle")}))
    with c4:
        ce = st.selectbox("CE/Proxy", ["全部"] + sorted({r.get("ce_trend") for r in rows if r.get("ce_trend")}),
                          format_func=lambda x: _CE_ZH.get(x, x))
    with c5:
        theme = st.selectbox("主題", ["全部"] + sorted({r.get("theme") for r in rows if r.get("theme")}))
    with c6:
        role = st.selectbox("產業鏈角色", ["全部"] + sorted({
            r.get("industry_role") for r in rows if r.get("industry_role")
        }))

    filtered = _filter_rows(rows, signal, cycle, ce, theme, role)
    _render_summary(filtered)

    tab_board, tab_detail, tab_story = st.tabs(["狀態表", "單檔詳情", "Story 文案"])
    with tab_board:
        st.dataframe(_display_df(filtered), width="stretch", hide_index=True)
        proxy_count = sum(1 for r in filtered if r.get("ce_source") == "trend_proxy")
        if proxy_count:
            st.caption(f"CE/Proxy 注意：{proxy_count} 檔因缺少完整標的 high/low/ATR 區間資料，以 Proxy 顯示。")
    with tab_detail:
        _render_detail(filtered)
    with tab_story:
        _render_story(filtered)
