"""Validated native presentation components for UX-1A data states."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Iterable, Literal, Mapping, TypeAlias

import streamlit as st


SourceState: TypeAlias = Literal["authoritative", "fallback", "unavailable"]
ContentState: TypeAlias = Literal["populated", "empty", "partial", "unknown"]
FreshnessState: TypeAlias = Literal["fresh", "stale", "unknown"]
OperationState: TypeAlias = Literal["idle", "loading", "success", "failure"]

SOURCE_LABELS: Mapping[str, str] = MappingProxyType({
    "system.ai-updates": "AI 更新",
    "system.schedules": "排程登錄",
    "system.schedule-result": "排程結果",
    "system.reflection": "排程反思",
    "institutions.funds": "機構快選清單",
    "today.trade-state": "交易狀態",
    "chat.session": "AI 對話",
    "candidate.pipeline": "候選刷新",
    "crypto.universe": "幣安永續合約清單",
})

ARTIFACT_REASON_CODES = frozenset({
    "missing",
    "invalid_json",
    "invalid_shape",
    "unreadable",
})
CLIENT_FAILURE_REASON_CODES = frozenset({
    "transport_error",
    "deadline_exceeded",
    "http_status",
    "invalid_media_type",
    "invalid_cache_control",
    "response_too_large",
    "invalid_envelope",
})
UI_REASON_CODES = frozenset({
    "read_failure",
    "computation_failure",
    "operation_failure",
    "provider_failure",
    "status_failure",
    "safety_suppressed",
})
REASON_LABELS: Mapping[str, str] = MappingProxyType({
    "missing": "找不到資料",
    "invalid_json": "資料尚未完整寫入或格式無效",
    "invalid_shape": "資料格式不符合預期",
    "unreadable": "資料目前無法讀取",
    "transport_error": "連線暫時失敗",
    "deadline_exceeded": "讀取逾時",
    "http_status": "服務暫時無法回應",
    "invalid_media_type": "服務回應格式不符",
    "invalid_cache_control": "服務回應快取規則不符",
    "response_too_large": "服務回應超過安全大小",
    "invalid_envelope": "服務回應格式不符",
    "read_failure": "資料讀取失敗",
    "computation_failure": "資料計算失敗",
    "operation_failure": "操作未完成",
    "provider_failure": "回答服務暫時無法完成請求",
    "status_failure": "執行狀態目前無法確認",
    "safety_suppressed": "結果包含不適合顯示的診斷內容",
})

RECOVERY_LABELS: Mapping[str, str] = MappingProxyType({
    "retry": "請稍後重試",
    "manual-cik": "仍可手動輸入 CIK",
    "open-data-health": "可前往資料健康頁檢查來源狀態",
    "resume-after-auth": "完成登入後可接續執行",
})

EVENT_CODES = frozenset({
    "QR-CHAT-LOAD-001",
    "QR-CHAT-DELETE-001",
    "QR-CHAT-SAVE-001",
    "QR-CHAT-CONTEXT-001",
    "QR-CHAT-ANSWER-001",
    "QR-TODAY-TRADE-STATE-001",
    "QR-TODAY-ARTIFACT-001",
    "QR-CANDIDATE-LAUNCH-001",
    "QR-CANDIDATE-AUTH-001",
    "QR-CANDIDATE-STATUS-001",
    "QR-SCHEDULES-RESULT-001",
    "QR-SCHEDULES-REFLECTION-001",
})

_SOURCES = frozenset({"authoritative", "fallback", "unavailable"})
_CONTENTS = frozenset({"populated", "empty", "partial", "unknown"})
_FRESHNESS = frozenset({"fresh", "stale", "unknown"})
_OPERATIONS = frozenset({"idle", "loading", "success", "failure"})
_EVENT_CODE_RE = re.compile(r"^QR-[A-Z0-9-]+-[0-9]{3}$")


@dataclass(frozen=True, slots=True)
class DataState:
    """Closed, immutable presentation state with no free-form diagnostic field."""

    source: SourceState
    content: ContentState
    freshness: FreshnessState
    operation: OperationState
    source_id: str
    reason_code: str | None = None
    event_code: str | None = None
    as_of: date | datetime | None = None
    recovery_key: str | None = None

    def __post_init__(self) -> None:
        if self.source not in _SOURCES:
            raise ValueError("unsupported source state")
        if self.content not in _CONTENTS:
            raise ValueError("unsupported content state")
        if self.freshness not in _FRESHNESS:
            raise ValueError("unsupported freshness state")
        if self.operation not in _OPERATIONS:
            raise ValueError("unsupported operation state")
        if self.source_id not in SOURCE_LABELS:
            raise ValueError("unsupported source identifier")
        if self.reason_code is not None and self.reason_code not in REASON_LABELS:
            raise ValueError("unsupported reason code")
        if self.recovery_key is not None and self.recovery_key not in RECOVERY_LABELS:
            raise ValueError("unsupported recovery key")
        if self.event_code is not None:
            if not _EVENT_CODE_RE.fullmatch(self.event_code):
                raise ValueError("invalid event-code syntax")
            if self.event_code not in EVENT_CODES:
                raise ValueError("unsupported event code")
        if self.as_of is not None and not isinstance(self.as_of, (date, datetime)):
            raise TypeError("as_of must be a date or datetime")

        if self.source == "unavailable":
            if self.content in {"populated", "partial"}:
                raise ValueError("an unavailable source cannot contain trusted rows")
            if self.freshness != "unknown":
                raise ValueError("an unavailable source has unknown freshness")
            if self.reason_code is None:
                raise ValueError("an unavailable source requires a safe reason")
        if self.source == "fallback":
            if self.reason_code not in CLIENT_FAILURE_REASON_CODES:
                raise ValueError("fallback requires a client-failure reason")
        if self.source == "authoritative" and self.reason_code in (
            ARTIFACT_REASON_CODES | CLIENT_FAILURE_REASON_CODES
        ):
            raise ValueError("an authoritative source cannot carry a degradation reason")
        if self.freshness in {"fresh", "stale"}:
            if self.source == "unavailable" or self.as_of is None:
                raise ValueError("fresh or stale data requires an available dated source")


_SOURCE_STATE_COPY: Mapping[str, str] = MappingProxyType({
    "authoritative": "權威來源可用",
    "fallback": "正在使用備援來源",
    "unavailable": "權威來源不可用",
})
_CONTENT_COPY: Mapping[str, str] = MappingProxyType({
    "populated": "已有內容",
    "empty": "目前沒有資料",
    "partial": "僅有部分內容",
    "unknown": "內容狀態未知",
})
_FRESHNESS_COPY: Mapping[str, str] = MappingProxyType({
    "fresh": "資料為最新狀態",
    "stale": "資料已過期",
    "unknown": "新鮮度未知",
})
_OPERATION_COPY: Mapping[str, str] = MappingProxyType({
    "loading": "操作進行中",
    "success": "操作成功",
    "failure": "操作失敗",
})


def _as_of_text(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    return value.isoformat()


def _compose_state(state: DataState) -> tuple[str, str]:
    """Return native container severity and fixed compositional state copy."""
    parts: list[str] = []
    if state.operation != "idle":
        parts.append(_OPERATION_COPY[state.operation])
    parts.extend((
        _SOURCE_STATE_COPY[state.source],
        _CONTENT_COPY[state.content],
        _FRESHNESS_COPY[state.freshness],
    ))
    if state.as_of is not None:
        parts.append(f"資料時間：{_as_of_text(state.as_of)}")
    if state.reason_code is not None:
        parts.append(f"原因：{REASON_LABELS[state.reason_code]}")
    if state.recovery_key is not None:
        parts.append(RECOVERY_LABELS[state.recovery_key])
    if state.event_code is not None:
        parts.append(f"事件代碼：{state.event_code}")

    if state.operation == "failure":
        severity = "error"
    elif state.source in {"unavailable", "fallback"}:
        severity = "warning"
    elif state.content == "partial" or state.freshness == "stale":
        severity = "warning"
    elif state.content == "empty" or state.operation == "loading":
        severity = "info"
    elif state.operation == "success":
        severity = "success"
    else:
        severity = "info"
    return severity, "；".join(parts) + "。"


def _source_meta_text(state: DataState) -> str:
    parts = [
        f"資料來源：{SOURCE_LABELS[state.source_id]}",
        _SOURCE_STATE_COPY[state.source],
        _FRESHNESS_COPY[state.freshness],
    ]
    if state.as_of is not None:
        parts.append(f"資料時間：{_as_of_text(state.as_of)}")
    if state.reason_code is not None:
        parts.append(f"原因：{REASON_LABELS[state.reason_code]}")
    return " · ".join(parts)


def render_state_banner(state: DataState) -> None:
    """Render one state through a native semantic status container."""
    severity, message = _compose_state(state)
    if severity == "error":
        st.error(message)
    elif severity == "warning":
        st.warning(message)
    elif severity == "success":
        st.success(message)
    else:
        st.info(message)


def render_source_meta(state: DataState) -> None:
    """Render fixed source/freshness metadata through a native caption."""
    st.caption(_source_meta_text(state))


def render_tag_row(tags: Iterable[str]) -> None:
    """Render source-validated tags as literal native text, never HTML."""
    visible = tuple(tag for tag in tags if isinstance(tag, str) and tag)
    if visible:
        st.text(f"標籤：{' · '.join(visible)}")
