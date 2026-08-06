"""系統 · AI Agent 重點更新.

Reads the manually maintained feed only through the loopback API, then renders
newest-first cards with optional "深化連結" buttons.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

import streamlit as st

from api.models import AiUpdateItem, UnavailableReason

from . import _components, _read_api


AiUpdatesFeedStatus: TypeAlias = Literal[
    "api_available",
    "api_unavailable",
    "api_failure",
]
AiUpdatesFeedReason: TypeAlias = (
    UnavailableReason | _read_api.ClientFailureReason | None
)


@dataclass(frozen=True, slots=True)
class AiUpdatesFeedState:
    status: AiUpdatesFeedStatus
    updates: tuple[AiUpdateItem, ...]
    reason: AiUpdatesFeedReason


def _newest_first(
    updates: tuple[AiUpdateItem, ...],
) -> tuple[AiUpdateItem, ...]:
    return tuple(sorted(updates, key=lambda update: update.date, reverse=True))


def _load_updates() -> AiUpdatesFeedState:
    result = _read_api.load_ai_updates()
    if isinstance(result, _read_api.AiUpdatesApiAvailable):
        return AiUpdatesFeedState(
            "api_available",
            _newest_first(result.updates),
            None,
        )
    if isinstance(result, _read_api.AiUpdatesApiUnavailable):
        return AiUpdatesFeedState("api_unavailable", (), result.reason)
    return AiUpdatesFeedState("api_failure", (), result.reason)


def _unavailable_message(reason: AiUpdatesFeedReason) -> str:
    detail = {
        "missing": "找不到 AI 更新資料。",
        "invalid_json": "AI 更新資料尚未完整寫入或 JSON 格式無效。",
        "invalid_shape": "AI 更新資料格式不符合預期。",
        "unreadable": "AI 更新資料目前無法讀取。",
    }.get(reason, "AI 更新資料目前無法讀取。")
    return f"AI 更新資料目前無法使用：{detail}"


def _safe_reason(
    reason: AiUpdatesFeedReason,
) -> str:
    if reason in (
        _components.ARTIFACT_REASON_CODES
        | _components.CLIENT_FAILURE_REASON_CODES
        | _components.UI_REASON_CODES
    ):
        return str(reason)
    return "read_failure"


def _data_state(feed: AiUpdatesFeedState) -> _components.DataState:
    content = "populated" if feed.updates else "empty"
    as_of = None
    if feed.updates:
        try:
            as_of = date.fromisoformat(max(update.date for update in feed.updates))
        except (TypeError, ValueError):
            as_of = None

    if feed.status == "api_available":
        return _components.DataState(
            source="authoritative",
            content=content,
            freshness="unknown",
            operation="idle",
            source_id="system.ai-updates",
            as_of=as_of,
        )
    return _components.DataState(
        source="unavailable",
        content="unknown",
        freshness="unknown",
        operation="idle",
        source_id="system.ai-updates",
        reason_code=_safe_reason(feed.reason),
        recovery_key="open-data-health",
    )


def render() -> None:
    st.header("🤖 AI Agent 重點更新")
    st.caption("手動維護的更新摘要 feed，僅由本機 loopback API 讀取；要深化的項目附上連結。")

    feed = _load_updates()
    state = _data_state(feed)
    if feed.status in {"api_unavailable", "api_failure"}:
        _components.render_state_banner(state)
        return
    if state.content == "empty":
        _components.render_state_banner(state)
    else:
        _components.render_source_meta(state)

    updates = feed.updates
    if not updates:
        return

    all_tags = sorted({tag for update in updates for tag in update.tags})
    if len(all_tags) > 3:
        picked = st.multiselect("依標籤篩選", all_tags, default=[])
    else:
        picked = []

    shown = 0
    for update in updates:
        tags = update.tags
        if picked and not set(picked) & set(tags):
            continue
        shown += 1
        with st.container(border=True):
            col_title, col_date = st.columns([4, 1], vertical_alignment="center")
            with col_title:
                st.markdown(f"**{update.title}**")
            with col_date:
                st.caption(update.date)
            st.markdown(update.summary)
            if tags:
                _components.render_tag_row(tags)
            if update.link:
                st.link_button("深化連結", update.link)

    if shown == 0:
        st.info("沒有符合所選標籤的更新。")
