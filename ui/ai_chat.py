"""Global right-bottom AI chat assistant."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from urllib.parse import urlsplit

import streamlit as st

from . import _components, _shared
from scripts import ai_chat_assistant, ai_chat_store


_ID = "ai_chat_id"
_MESSAGES = "ai_chat_messages"
_MODE = "ai_chat_mode"
_SAVE = "ai_chat_save_enabled"
_CONTEXT = "ai_chat_context_attachment"
_TITLE = "ai_chat_title"
_LAST_SAVE_SIG = "ai_chat_last_save_signature"
_CONFIRM_DELETE = "ai_chat_confirm_delete_id"
_CONFIRM_CLEAR = "ai_chat_confirm_clear"
_OPEN = "ai_chat_open_panel"
_EVENT = "ai_chat_event_code"

_LOGGER = logging.getLogger(__name__)
_CHAT_EVENTS = frozenset({
    "QR-CHAT-LOAD-001",
    "QR-CHAT-DELETE-001",
    "QR-CHAT-SAVE-001",
    "QR-CHAT-CONTEXT-001",
})
_SAFE_CONTEXT_PATH_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SAFE_CONTEXT_SOURCE_RE = re.compile(r"^[A-Za-z0-9_. /-]{1,100}$")


def _log_failure(event_code: str, exc: BaseException) -> None:
    """Log only a stable event and exception class, never exception details."""
    _LOGGER.warning(
        "event_code=%s error_type=%s",
        event_code,
        type(exc).__name__,
    )


def _queue_event(event_code: str) -> None:
    if event_code in _CHAT_EVENTS:
        st.session_state[_EVENT] = event_code


def _event_state(event_code: str) -> _components.DataState:
    messages = st.session_state.get(_MESSAGES)
    content = "populated" if isinstance(messages, list) and messages else "empty"
    return _components.DataState(
        source="authoritative",
        content=content,
        freshness="unknown",
        operation="failure",
        source_id="chat.session",
        reason_code="operation_failure",
        event_code=event_code,
        recovery_key="retry",
    )


def _render_queued_event() -> None:
    event_code = st.session_state.pop(_EVENT, None)
    if event_code in _CHAT_EVENTS:
        _components.render_state_banner(_event_state(event_code))


def _contains_context_diagnostic(value: object) -> bool:
    return _shared.contains_prohibited_diagnostic(value)


def _safe_context_attachment(value: object) -> dict | None:
    """Keep normal generated context while dropping diagnostic-shaped payloads."""
    if not isinstance(value, dict):
        return None
    page_path = str(value.get("page_path") or "").strip()
    if page_path and not _SAFE_CONTEXT_PATH_RE.fullmatch(page_path):
        return None
    ticker = value.get("ticker")
    if ticker is not None:
        ticker = str(ticker).upper().strip()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,12}", ticker):
            return None
    page_title = str(value.get("page_title") or "目前頁面").strip()
    summary = str(value.get("summary") or "").strip()
    if _contains_context_diagnostic(page_title) or _contains_context_diagnostic(summary):
        return None
    raw_sources = value.get("sources")
    sources: list[str] = []
    if isinstance(raw_sources, list):
        for item in raw_sources:
            source = str(item or "").strip()
            if (
                source
                and _SAFE_CONTEXT_SOURCE_RE.fullmatch(source)
                and not source.startswith("/")
                and ".." not in source
                and not _contains_context_diagnostic(source)
            ):
                sources.append(source)
    return {
        "page_path": page_path or "today-decision",
        "page_title": page_title[:80] or "目前頁面",
        "ticker": ticker,
        "summary": summary,
        "sources": sources,
    }


def _init_state() -> None:
    if _ID not in st.session_state:
        st.session_state[_ID] = ""
    if _MESSAGES not in st.session_state:
        st.session_state[_MESSAGES] = []
    if _MODE not in st.session_state:
        st.session_state[_MODE] = ai_chat_assistant.QUICK_MODE
    if _SAVE not in st.session_state:
        st.session_state[_SAVE] = False
    if _CONTEXT not in st.session_state:
        st.session_state[_CONTEXT] = None
    if _TITLE not in st.session_state:
        st.session_state[_TITLE] = ""
    if _LAST_SAVE_SIG not in st.session_state:
        st.session_state[_LAST_SAVE_SIG] = ""
    if _CONFIRM_DELETE not in st.session_state:
        st.session_state[_CONFIRM_DELETE] = ""
    if _CONFIRM_CLEAR not in st.session_state:
        st.session_state[_CONFIRM_CLEAR] = False
    if _OPEN not in st.session_state:
        st.session_state[_OPEN] = False
    # Upgrade live sessions in place.  The projection is deliberately narrow
    # and matches only the exact historical assistant failure generated here.
    st.session_state[_MESSAGES] = ai_chat_store.project_messages(
        st.session_state.get(_MESSAGES)
    )
    st.session_state[_CONTEXT] = _safe_context_attachment(
        st.session_state.get(_CONTEXT)
    )
    if st.session_state.get(_EVENT) not in _CHAT_EVENTS:
        st.session_state.pop(_EVENT, None)


def _current_path() -> str:
    try:
        url = str(getattr(st.context, "url", "") or "")
        if url:
            return urlsplit(url).path.strip("/")
    except Exception:  # noqa: BLE001
        pass
    return "today-decision"


def _chat_payload() -> dict:
    return {
        "id": st.session_state.get(_ID) or "",
        "title": st.session_state.get(_TITLE) or "",
        "mode": st.session_state.get(_MODE) or ai_chat_assistant.QUICK_MODE,
        "messages": ai_chat_store.project_messages(st.session_state.get(_MESSAGES)),
        "context_attachment": _safe_context_attachment(st.session_state.get(_CONTEXT)),
    }


def _load_payload(payload: dict, *, saved: bool) -> None:
    payload = payload if isinstance(payload, dict) else {}
    st.session_state[_ID] = payload.get("id") or ""
    st.session_state[_TITLE] = payload.get("title") or ""
    mode = payload.get("mode")
    st.session_state[_MODE] = (
        mode if mode in ai_chat_assistant.MODES else ai_chat_assistant.QUICK_MODE
    )
    st.session_state[_MESSAGES] = ai_chat_store.project_messages(payload.get("messages"))
    st.session_state[_CONTEXT] = _safe_context_attachment(payload.get("context_attachment"))
    st.session_state[_SAVE] = saved
    st.session_state[_LAST_SAVE_SIG] = _save_signature() if saved else ""
    st.session_state[_CONFIRM_DELETE] = ""
    st.session_state[_CONFIRM_CLEAR] = False


def _new_chat() -> None:
    _load_payload({
        "id": "",
        "title": "",
        "mode": st.session_state.get(_MODE) or ai_chat_assistant.QUICK_MODE,
        "messages": [],
        "context_attachment": None,
    }, saved=False)


def _save_if_needed(root) -> bool:
    if not st.session_state.get(_SAVE):
        return True
    if not st.session_state.get(_MESSAGES):
        return True
    sig = _save_signature()
    if sig == st.session_state.get(_LAST_SAVE_SIG):
        return True
    try:
        saved = ai_chat_store.save_chat(_chat_payload(), root)
    except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
        _log_failure("QR-CHAT-SAVE-001", exc)
        _queue_event("QR-CHAT-SAVE-001")
        return False
    st.session_state[_ID] = saved["id"]
    st.session_state[_TITLE] = saved["title"]
    st.session_state[_LAST_SAVE_SIG] = _save_signature()
    return True


def _save_signature() -> str:
    payload = {
        "title": st.session_state.get(_TITLE) or "",
        "mode": st.session_state.get(_MODE) or ai_chat_assistant.QUICK_MODE,
        "messages": st.session_state.get(_MESSAGES) or [],
        "context_attachment": st.session_state.get(_CONTEXT),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rerun_panel() -> None:
    st.rerun()


def _render_css() -> None:
    st.markdown(
        """
        <style>
        .st-key-ai_chat_float {
            position: fixed !important;
            right: calc(1.25rem + env(safe-area-inset-right)) !important;
            bottom: calc(1.25rem + env(safe-area-inset-bottom)) !important;
            z-index: 10000 !important;
            width: 5rem !important;
            min-width: 5rem !important;
            max-width: 5rem !important;
            height: 5rem !important;
            min-height: 5rem !important;
            max-height: 5rem !important;
            display: flex !important;
            justify-content: flex-end !important;
            align-items: flex-end !important;
            pointer-events: none !important;
        }
        .st-key-ai_chat_float > div {
            pointer-events: auto !important;
        }
        .st-key-ai_chat_float [data-testid="stLayoutWrapper"],
        .st-key-ai_chat_float [data-testid="stElementContainer"],
        .st-key-ai_chat_float [data-testid="stButton"],
        .st-key-ai_chat_open,
        .st-key-ai_chat_open > div {
            width: 5rem !important;
            height: 5rem !important;
        }
        .st-key-ai_chat_float [data-testid="stTooltipHoverTarget"] {
            width: 4.8rem !important;
            height: 4.8rem !important;
        }
        .st-key-ai_chat_float button,
        .st-key-ai_chat_float button[data-testid="stBaseButton-secondary"] {
            width: 4.6rem !important;
            min-width: 4.6rem !important;
            height: 4.6rem !important;
            min-height: 4.6rem !important;
            border-radius: 999px !important;
            padding: 0 !important;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.34);
        }
        .st-key-ai_chat_panel {
            position: fixed !important;
            right: calc(1.25rem + env(safe-area-inset-right)) !important;
            bottom: calc(1.25rem + env(safe-area-inset-bottom)) !important;
            z-index: 10000 !important;
            width: 23.5rem !important;
            max-width: calc(100vw - 2rem) !important;
            max-height: min(40rem, calc(100dvh - 2.5rem)) !important;
            overflow-y: auto !important;
            padding: 1rem !important;
            border: 1px solid rgba(148, 163, 184, 0.28) !important;
            border-radius: 8px !important;
            background: rgb(14, 17, 23) !important;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.45);
        }
        .st-key-ai_chat_panel [data-testid="stVerticalBlock"] {
            gap: .65rem !important;
        }
        .st-key-ai_chat_panel_header [data-testid="stMarkdownContainer"] p {
            margin: 0 !important;
            padding-right: 3rem !important;
            font-size: 1.05rem;
            font-weight: 800;
        }
        .st-key-ai_chat_panel_close {
            position: absolute !important;
            top: 1rem !important;
            right: 1rem !important;
            width: 2.25rem !important;
            height: 2.25rem !important;
        }
        .st-key-ai_chat_panel_close button {
            min-width: 2.25rem !important;
            width: 2.25rem !important;
            height: 2.25rem !important;
            padding: 0 !important;
        }
        .st-key-ai_chat_float [data-testid="stMarkdownContainer"] p {
            font-size: 1.18rem;
            font-weight: 800;
            line-height: 1;
        }
        .st-key-ai_chat_question [data-baseweb="textarea"]:focus-within,
        .st-key-ai_chat_question textarea:focus,
        .st-key-ai_chat_question textarea:focus-visible {
            border-color: rgba(125, 211, 252, 0.9) !important;
            box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.55) !important;
            outline: none !important;
        }
        @media (max-width: 640px) {
            .st-key-ai_chat_float {
                right: calc(.75rem + env(safe-area-inset-right)) !important;
                bottom: calc(.75rem + env(safe-area-inset-bottom)) !important;
                width: 4.5rem !important;
                min-width: 4.5rem !important;
                max-width: 4.5rem !important;
                height: 4.5rem !important;
                min-height: 4.5rem !important;
                max-height: 4.5rem !important;
            }
            .st-key-ai_chat_float [data-testid="stLayoutWrapper"],
            .st-key-ai_chat_float [data-testid="stElementContainer"],
            .st-key-ai_chat_float [data-testid="stButton"],
            .st-key-ai_chat_open,
            .st-key-ai_chat_open > div {
                width: 4.5rem !important;
                height: 4.5rem !important;
            }
            .st-key-ai_chat_float [data-testid="stTooltipHoverTarget"] {
                width: 4.2rem !important;
                height: 4.2rem !important;
            }
            .st-key-ai_chat_float button,
            .st-key-ai_chat_float button[data-testid="stBaseButton-secondary"] {
                width: 4rem !important;
                min-width: 4rem !important;
                height: 4rem !important;
                min-height: 4rem !important;
            }
            .st-key-ai_chat_panel {
                right: calc(.5rem + env(safe-area-inset-right)) !important;
                bottom: calc(.5rem + env(safe-area-inset-bottom)) !important;
                width: calc(100vw - 1rem) !important;
                max-width: calc(100vw - 1rem) !important;
                max-height: min(34rem, calc(72dvh - 1rem)) !important;
                padding: .875rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_history(root) -> None:
    with st.expander("歷史", expanded=False):
        try:
            saved = ai_chat_store.list_saved_chats(root)
        except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
            _log_failure("QR-CHAT-LOAD-001", exc)
            _queue_event("QR-CHAT-LOAD-001")
            _render_queued_event()
            return
        if not saved:
            st.caption("尚無保存的對話。開啟「保存此對話」後，這裡會列出可續聊的紀錄。")
            return
        labels = {}
        for row in saved:
            mode = row.get("mode")
            mode_label = mode if mode in ai_chat_assistant.MODES else ai_chat_assistant.QUICK_MODE
            updated = str(row.get("updated_at") or "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?", updated):
                updated = "-"
            labels[row["id"]] = f"{row['title']} · {mode_label} · {updated[:16]}"
        selected = st.selectbox(
            "已保存對話",
            options=[row["id"] for row in saved],
            format_func=lambda value: labels.get(value, value),
            key="ai_chat_saved_select",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns(2)
        if c1.button("載入", key="ai_chat_load_saved", width="stretch"):
            try:
                _load_payload(ai_chat_store.load_chat(selected, root), saved=True)
                _rerun_panel()
            except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
                _log_failure("QR-CHAT-LOAD-001", exc)
                _queue_event("QR-CHAT-LOAD-001")
                _rerun_panel()
        confirming_delete = st.session_state.get(_CONFIRM_DELETE) == selected
        delete_label = "確認刪除" if confirming_delete else "刪除"
        if c2.button(delete_label, key="ai_chat_delete_saved", width="stretch"):
            if not confirming_delete:
                st.session_state[_CONFIRM_DELETE] = selected
                st.session_state[_CONFIRM_CLEAR] = False
                _rerun_panel()
            try:
                ai_chat_store.delete_chat(selected, root)
                if st.session_state.get(_ID) == selected:
                    _new_chat()
                st.session_state[_CONFIRM_DELETE] = ""
                _rerun_panel()
            except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
                _log_failure("QR-CHAT-DELETE-001", exc)
                _queue_event("QR-CHAT-DELETE-001")
                _rerun_panel()
        elif confirming_delete:
            st.caption("再按一次「確認刪除」才會刪除保存紀錄。")


def _render_context_controls() -> None:
    context = ai_chat_assistant.available_context(st.session_state, _current_path())
    attachment = st.session_state.get(_CONTEXT)
    if attachment:
        title = attachment.get("ticker") or attachment.get("page_title") or "目前頁面"
        st.caption(f"已帶入: {title}")
        if st.button("移除帶入資料", key="ai_chat_clear_context", width="stretch"):
            st.session_state[_CONTEXT] = None
            _rerun_panel()
        return

    bits = [context.get("page_title") or context.get("page_path")]
    if context.get("ticker"):
        bits.append(context["ticker"])
    label = " / ".join([str(b) for b in bits if b])
    if st.button(f"帶入目前頁面資料: {label}", key="ai_chat_attach_context",
                 width="stretch"):
        try:
            built = ai_chat_assistant.build_context_attachment(
                context,
                reports_dir=_shared.REPORTS_DIR,
                candidate_dir=_shared.CANDIDATE_OUTPUT_DIR,
            )
            attachment = _safe_context_attachment(built)
            if attachment is None:
                _queue_event("QR-CHAT-CONTEXT-001")
                _rerun_panel()
                return
            st.session_state[_CONTEXT] = attachment
            _rerun_panel()
        except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
            _log_failure("QR-CHAT-CONTEXT-001", exc)
            _queue_event("QR-CHAT-CONTEXT-001")
            _rerun_panel()


def _render_messages() -> None:
    messages = st.session_state.get(_MESSAGES) or []
    if not messages:
        st.caption("可以問操作、交易想法、風險檢查；需要最新資料時切到深度研究。")
        return
    with st.container(height=320, border=True):
        for msg in messages:
            role = msg.get("role") if isinstance(msg, dict) else None
            content = msg.get("content") if isinstance(msg, dict) else None
            if role not in {"user", "assistant"} or not content:
                continue
            with st.chat_message(role):
                if role == "assistant" and content == ai_chat_store.SAFE_ASSISTANT_FAILURE:
                    _components.render_state_banner(_components.DataState(
                        source="unavailable",
                        content="unknown",
                        freshness="unknown",
                        operation="failure",
                        source_id="chat.session",
                        reason_code="provider_failure",
                        event_code="QR-CHAT-ANSWER-001",
                        recovery_key="retry",
                    ))
                else:
                    st.markdown(str(content))


def _handle_submit(question: str, root) -> None:
    messages = list(st.session_state.get(_MESSAGES) or [])
    messages.append({"role": "user", "content": question})
    st.session_state[_MESSAGES] = messages
    try:
        with st.spinner("AI 回答中..."):
            answer = ai_chat_assistant.answer_chat(
                question,
                history=messages[:-1],
                mode=st.session_state.get(_MODE) or ai_chat_assistant.QUICK_MODE,
                context_attachment=st.session_state.get(_CONTEXT),
            )
    except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
        _log_failure("QR-CHAT-ANSWER-001", exc)
        answer = ai_chat_store.SAFE_ASSISTANT_FAILURE
    messages.append({"role": "assistant", "content": answer})
    st.session_state[_MESSAGES] = messages
    _save_if_needed(root)
    _rerun_panel()


def _render_panel(root) -> None:
    with st.container(key="ai_chat_panel"):
        with st.container(key="ai_chat_panel_header"):
            st.markdown("**AI 對話**", unsafe_allow_html=False)
        with st.container(key="ai_chat_panel_close"):
            if st.button("×", key="ai_chat_close", help="收合 AI 對話"):
                st.session_state[_OPEN] = False
                _rerun_panel()

        _render_queued_event()

        status = [st.session_state.get(_MODE) or ai_chat_assistant.QUICK_MODE]
        if st.session_state.get(_SAVE):
            status.append("保存中")
        attachment = st.session_state.get(_CONTEXT)
        if attachment:
            status.append(f"已帶入 {attachment.get('ticker') or attachment.get('page_title') or '資料'}")
        st.caption(" · ".join(status))

        _render_messages()
        with st.form("ai_chat_send_form", clear_on_submit=True):
            question = st.text_area(
                "輸入問題",
                key="ai_chat_question",
                height=88,
                placeholder="例如: 幫我檢查 NVDA 這筆追高交易有哪些反方風險",
            )
            submitted = st.form_submit_button("送出", width="stretch")
        if submitted:
            text = (question or "").strip()
            if text:
                _handle_submit(text, root)
            else:
                st.warning("請先輸入問題。")

        with st.expander("設定與歷史", expanded=False):
            mode_options = list(ai_chat_assistant.MODES)
            if st.session_state.get(_MODE) not in mode_options:
                st.session_state[_MODE] = ai_chat_assistant.QUICK_MODE
            st.radio(
                "模式",
                options=mode_options,
                horizontal=True,
                index=None,
                key=_MODE,
                help="快速問答不查網路；深度研究可用受限 web search/fetch。",
            )
            st.checkbox("保存此對話", key=_SAVE,
                        help="開啟後會保存到本機 runtime 目錄，可從歷史載入或刪除。")
            if not _save_if_needed(root):
                _render_queued_event()
            _render_context_controls()
            c1, c2 = st.columns(2)
            if c1.button("新對話", key="ai_chat_new", width="stretch"):
                _new_chat()
                _rerun_panel()
            clear_label = "確認清空" if st.session_state.get(_CONFIRM_CLEAR) else "清空目前對話"
            if c2.button(clear_label, key="ai_chat_clear", width="stretch"):
                if not st.session_state.get(_CONFIRM_CLEAR):
                    st.session_state[_CONFIRM_CLEAR] = True
                    st.session_state[_CONFIRM_DELETE] = ""
                    _rerun_panel()
                st.session_state[_MESSAGES] = []
                st.session_state[_CONTEXT] = None
                st.session_state[_CONFIRM_CLEAR] = False
                _rerun_panel()
            elif st.session_state.get(_CONFIRM_CLEAR):
                st.caption("再按一次「確認清空」才會移除目前對話內容。")
            _render_history(root)


def render() -> None:
    """Render the global AI chat launcher."""
    _init_state()
    _render_css()
    root = ai_chat_store.default_chat_root(_shared.DATA_DIR)

    if st.session_state.get(_OPEN):
        _render_panel(root)
        return

    with st.container(key="ai_chat_float"):
        if st.button("AI", key="ai_chat_open", help="開啟 AI 對話"):
            st.session_state[_OPEN] = True
            _rerun_panel()
