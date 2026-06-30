"""美股 · 產業鏈分類 — platform review queue for supply-chain roles."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import _shared
from scripts import industry_roles as engine


_STATUS_ZH = {
    "suggested": "待審核",
    "approved": "已核准",
    "rejected": "已拒絕",
    "deferred": "延後",
    "unclassified": "缺分類",
}


def _candidate_tickers() -> list[str]:
    tickers: set[str] = set()
    ranked = _shared.load_json(str(_shared.candidate_output_path("ranked_candidates.json"))) or {}
    for row in (ranked.get("tickers") or ranked.get("ranked_candidates") or []):
        if isinstance(row, dict) and row.get("ticker"):
            tickers.add(str(row["ticker"]).upper())
    picks = _shared.load_json(str(_shared.REPORTS_DIR / "x_influencer_picks.json")) or {}
    for row in (picks.get("tickers") or picks.get("picks") or []):
        if isinstance(row, dict):
            sym = str(row.get("ticker") or row.get("symbol") or "").upper().lstrip("$")
            if sym:
                tickers.add(sym)
    return sorted(tickers)


def _status_label(status: str | None) -> str:
    return _STATUS_ZH.get(status or "", status or "-")


@st.cache_data(ttl=30, show_spinner=False)
def _load_state() -> tuple[dict, dict, dict]:
    return engine.load_taxonomy(), engine.load_overrides(), engine.load_suggestions()


def _suggestions_df(suggestions: list[dict]) -> pd.DataFrame:
    rows = []
    for item in suggestions:
        rows.append({
            "Ticker": item.get("ticker"),
            "建議角色": item.get("suggested_primary_role_name") or item.get("suggested_primary_role"),
            "信心": item.get("confidence"),
            "狀態": _status_label(item.get("status", "suggested")),
            "證據": " | ".join(str(x) for x in item.get("evidence", [])[:3]),
        })
    return pd.DataFrame(rows)


def _approved_df(taxonomy: dict, overrides: dict) -> pd.DataFrame:
    return pd.DataFrame(engine.approved_rows(taxonomy=taxonomy, overrides=overrides))


def _matches_query(item: dict, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join([
        str(item.get("ticker") or ""),
        str(item.get("suggested_primary_role") or ""),
        str(item.get("suggested_primary_role_name") or ""),
        " ".join(str(x) for x in item.get("evidence", [])),
    ]).lower()
    return q in haystack


def _filter_suggestions(suggestions: list[dict], *, status: str, query: str) -> list[dict]:
    rows = suggestions
    if status != "全部":
        rows = [s for s in rows if s.get("status", "suggested") == status]
    return [s for s in rows if _matches_query(s, query)]


def _missing_df(tickers: list[str], taxonomy: dict, overrides: dict, suggestions: dict) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        role = engine.resolve_role(
            ticker,
            taxonomy=taxonomy,
            overrides=overrides,
            suggestions=suggestions,
        )
        if role.get("source") != "unclassified":
            continue
        rows.append({
            "Ticker": ticker,
            "分類tag": role.get("display_role") or "未分類",
            "狀態": _status_label(role.get("status")),
        })
    return pd.DataFrame(rows)


def _clear_state() -> None:
    _load_state.clear()


def render() -> None:
    st.header("產業鏈分類")
    st.caption("AI 產生分類建議；平台內審核後才會成為交易頁使用的正式產業鏈角色。")

    taxonomy, overrides, suggestion_payload = _load_state()
    suggestions = suggestion_payload.get("suggestions", [])
    pending = [s for s in suggestions if s.get("status", "suggested") == "suggested"]
    approved_rows = engine.approved_rows(taxonomy=taxonomy, overrides=overrides)
    candidate_tickers = _candidate_tickers()
    missing_df = _missing_df(candidate_tickers, taxonomy, overrides, suggestion_payload)
    deferred_count = sum(1 for s in suggestions if s.get("status") == "deferred")

    c1, c2, c3, c4, c5 = st.columns(5)
    _shared.metric_card(c1, "待審核", len(pending))
    _shared.metric_card(c2, "已核准", len(approved_rows))
    _shared.metric_card(c3, "缺分類", len(missing_df))
    _shared.metric_card(c4, "延後", deferred_count)
    _shared.metric_card(c5, "角色數", len(taxonomy.get("roles", {})))

    with st.container(border=True):
        left, right = st.columns([2, 1])
        with left:
            st.markdown("##### 產生建議")
            st.caption("來源：ranked candidates + X picks，依 taxonomy 與 theme_baskets 產生待審核建議。")
        with right:
            if st.button("重新產生建議", use_container_width=True):
                engine.generate_suggestions(candidate_tickers)
                _clear_state()
                st.rerun()

    tab_pending, tab_all, tab_missing, tab_approved = st.tabs(["待審核", "全部建議", "缺分類", "已核准"])
    with tab_pending:
        query = st.text_input("搜尋", placeholder="Ticker / 角色 / 證據", key="industry_roles_pending_search")
        visible_pending = _filter_suggestions(pending, status="全部", query=query)
        if not pending:
            st.info("目前沒有待審核分類。")
        elif not visible_pending:
            st.info("沒有符合搜尋條件的待審核分類。")
        else:
            st.dataframe(_suggestions_df(visible_pending), use_container_width=True, hide_index=True, height=260)
            options = [s["ticker"] for s in visible_pending if s.get("ticker")]
            selected = st.selectbox("審核標的", options, index=0)
            item = next(s for s in visible_pending if s.get("ticker") == selected)
            roles = taxonomy.get("roles", {})
            role_ids = list(roles)
            if not role_ids:
                st.warning("尚未建立 taxonomy role，無法核准分類。請先補 content/industry_roles.json。")
            else:
                default_role = item.get("suggested_primary_role")
                default_idx = role_ids.index(default_role) if default_role in role_ids else 0

                with st.container(border=True):
                    st.markdown(f"##### {selected}")
                    st.caption("證據：" + "；".join(str(x) for x in item.get("evidence", [])))
                    chosen = st.selectbox(
                        "主分類",
                        role_ids,
                        index=default_idx,
                        format_func=lambda rid: roles.get(rid, {}).get("name", rid),
                    )
                    a1, a2, a3 = st.columns(3)
                    if a1.button("核准", type="primary", use_container_width=True):
                        engine.review_suggestion(selected, "approve", primary_role=chosen)
                        _clear_state()
                        st.rerun()
                    if a2.button("拒絕", use_container_width=True):
                        engine.review_suggestion(selected, "reject")
                        _clear_state()
                        st.rerun()
                    if a3.button("延後", use_container_width=True):
                        engine.review_suggestion(selected, "defer")
                        _clear_state()
                        st.rerun()

    with tab_all:
        f1, f2 = st.columns([1, 2])
        status_options = ["全部", "suggested", "approved", "rejected", "deferred"]
        with f1:
            status = st.selectbox("狀態", status_options, format_func=_status_label)
        with f2:
            query = st.text_input("搜尋", placeholder="Ticker / 角色 / 證據", key="industry_roles_all_search")
        visible = _filter_suggestions(suggestions, status=status, query=query)
        if visible:
            st.dataframe(_suggestions_df(visible), use_container_width=True, hide_index=True, height=420)
        else:
            st.info("沒有符合條件的分類建議。")

    with tab_missing:
        if missing_df.empty:
            st.info("目前候選 ticker 都已有正式或待審核的分類 tag。")
        else:
            st.dataframe(missing_df, use_container_width=True, hide_index=True, height=360)

    with tab_approved:
        df = _approved_df(taxonomy, overrides)
        if df.empty:
            st.info("尚無已核准角色。")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, height=420)
