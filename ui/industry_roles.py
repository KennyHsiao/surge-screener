"""美股 · 產業鏈分類 — platform review queue for supply-chain roles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, TypeAlias

import pandas as pd
import streamlit as st

from clients import private_api as _private_api

from . import _read_api, _shared
from scripts import industry_roles as engine


_STATUS_ZH = {
    "suggested": "待審核",
    "approved": "已核准",
    "rejected": "已拒絕",
    "deferred": "延後",
    "unclassified": "缺分類",
}
CandidateSeedStatus: TypeAlias = Literal[
    "api_available",
    "api_unavailable",
    "api_failure",
]


@dataclass(frozen=True, slots=True)
class CandidateSeedState:
    status: CandidateSeedStatus
    tickers: tuple[str, ...]
    reason: str | None = None


def _candidate_tickers() -> CandidateSeedState:
    tickers: set[str] = set()
    ranked = _read_api.load_ranked_candidates()
    if isinstance(ranked, _read_api.RankedCandidatesApiAvailable):
        status: CandidateSeedStatus = "api_available"
        reason = None
        tickers.update(candidate.ticker for candidate in ranked.feed.candidates)
    elif isinstance(ranked, _read_api.RankedCandidatesApiUnavailable):
        status = "api_unavailable"
        reason = ranked.reason
    elif isinstance(ranked, _read_api.RankedCandidatesApiFailure):
        status = "api_failure"
        reason = ranked.reason
    else:
        status = "api_failure"
        reason = "invalid_envelope"

    picks = _shared.load_json(str(_shared.REPORTS_DIR / "x_influencer_picks.json")) or {}
    for row in (picks.get("tickers") or picks.get("picks") or []):
        if isinstance(row, dict):
            sym = str(row.get("ticker") or row.get("symbol") or "").upper().lstrip("$")
            if sym:
                tickers.add(sym)
    return CandidateSeedState(status, tuple(sorted(tickers)), reason)


def _status_label(status: str | None) -> str:
    return _STATUS_ZH.get(status or "", status or "-")


@st.cache_data(ttl=30, show_spinner=False)
def _load_state() -> _private_api.IndustryRoleReviewBoardApiResult:
    return _private_api.load_industry_role_review_board()


def _review_state_dicts(
    state: _private_api.IndustryRoleReviewBoardApiAvailable,
) -> tuple[dict, dict, dict]:
    board = state.board
    taxonomy = {
        "version": board.taxonomy_version,
        "roles": {role.id: {"name": role.name} for role in board.roles},
    }
    overrides = {
        "version": board.taxonomy_version,
        "tickers": {
            row.ticker: {
                "primary_role": row.primary_role,
                "secondary_roles": list(row.secondary_roles),
                "confidence": row.confidence,
                "reviewed_at": row.reviewed_at,
            }
            for row in board.approved
        },
    }
    suggestions = {
        "generated_at": board.generated_at,
        "suggestions": [
            suggestion.model_dump(mode="json") for suggestion in board.suggestions
        ],
    }
    return taxonomy, overrides, suggestions


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
        if (
            role.get("source") != "classification_pending"
            and role.get("primary_role") != "classification_pending"
        ):
            continue
        rows.append({
            "Ticker": ticker,
            "分類tag": role.get("display_role") or "未分類",
            "狀態": _status_label(role.get("status")),
        })
    return pd.DataFrame(rows)


def _clear_state() -> None:
    _load_state.clear()


def _submit_action(
    state: _private_api.IndustryRoleReviewBoardApiAvailable,
    request: dict[str, object],
) -> bool:
    outcome = _private_api.mutate_industry_role_review_board(
        request,
        etag=state.etag,
        idempotency_key=str(uuid.uuid4()),
    )
    _clear_state()
    if isinstance(outcome, _private_api.IndustryRoleMutationApiSuccess):
        st.rerun()
        return True
    if outcome.reason == "precondition_failed":
        st.warning("分類狀態已更新，請重新整理後再操作。")
    elif outcome.reason == "conflict":
        st.warning("這個分類操作與目前狀態衝突，請重新整理後再確認。")
    else:
        st.error("分類操作未完成；狀態將重新載入，請確認後再試。")
    return False


def render() -> None:
    st.header("產業鏈分類")
    review_state = _load_state()
    caption = (
        "AI 產生分類建議；平台內審核後才會成為交易頁使用的正式產業鏈角色。"
        if isinstance(review_state, _private_api.IndustryRoleReviewBoardApiAvailable)
        else "私有分類服務目前無法使用，審核與產生操作已停用。"
    )
    st.caption(caption)
    if not isinstance(review_state, _private_api.IndustryRoleReviewBoardApiAvailable):
        return
    taxonomy, overrides, suggestion_payload = _review_state_dicts(review_state)
    suggestions = suggestion_payload.get("suggestions", [])
    pending = [s for s in suggestions if s.get("status", "suggested") == "suggested"]
    approved_rows = engine.approved_rows(taxonomy=taxonomy, overrides=overrides)
    candidate_seed = _candidate_tickers()
    candidate_tickers = list(candidate_seed.tickers)
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
            if candidate_seed.status == "api_unavailable":
                st.caption("排名候選資料目前無法使用；仍可使用 X picks 產生建議。")
            elif candidate_seed.status == "api_failure":
                st.caption("排名候選服務目前無法使用；仍可使用 X picks 產生建議。")
        with right:
            if not candidate_tickers:
                st.caption("目前沒有可產生建議的候選標的。")
            if st.button(
                "重新產生建議",
                use_container_width=True,
                disabled=not candidate_tickers,
            ):
                _submit_action(
                    review_state,
                    {"action": "generate", "tickers": candidate_tickers},
                )

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
                        _submit_action(
                            review_state,
                            {
                                "action": "approve",
                                "ticker": selected,
                                "primaryRole": chosen,
                                "secondaryRoles": [],
                            },
                        )
                    if a2.button("拒絕", use_container_width=True):
                        _submit_action(
                            review_state,
                            {"action": "reject", "ticker": selected},
                        )
                    if a3.button("延後", use_container_width=True):
                        _submit_action(
                            review_state,
                            {"action": "defer", "ticker": selected},
                        )

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
