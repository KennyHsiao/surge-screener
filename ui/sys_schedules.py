"""系統 · 排程與執行結果.

Reads the schedule registry only through the loopback API, then renders each
job's latest persisted result from shared report storage.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

import streamlit as st

from api.models import ScheduleEntry, UnavailableReason

from . import _components, _read_api, _shared


LOGGER = logging.getLogger("surge.ui.schedules")
_RESULT_EVENT = "QR-SCHEDULES-RESULT-001"
_REFLECTION_EVENT = "QR-SCHEDULES-REFLECTION-001"


class SuppressedDiagnostic(Exception):
    """Marker used only as a stable, payload-free log classification."""


ScheduleRegistryStatus: TypeAlias = Literal[
    "api_available",
    "api_unavailable",
    "api_failure",
]
ScheduleRegistryReason: TypeAlias = (
    UnavailableReason | _read_api.ClientFailureReason | None
)
ScheduleResultPayload: TypeAlias = (
    str | None | tuple[str | None, str | None]
)
ScheduleResultFetcher: TypeAlias = Callable[[], ScheduleResultPayload]


@dataclass(frozen=True, slots=True)
class ScheduleRegistryState:
    status: ScheduleRegistryStatus
    schedules: tuple[ScheduleEntry, ...]
    reason: ScheduleRegistryReason


def _load_schedules() -> ScheduleRegistryState:
    result = _read_api.load_schedules()
    if isinstance(result, _read_api.SchedulesApiAvailable):
        return ScheduleRegistryState("api_available", result.schedules, None)
    if isinstance(result, _read_api.SchedulesApiUnavailable):
        return ScheduleRegistryState("api_unavailable", (), result.reason)
    return ScheduleRegistryState("api_failure", (), result.reason)


def _unavailable_message(reason: ScheduleRegistryReason) -> str:
    detail = {
        "missing": "找不到排程資料。",
        "invalid_json": "排程資料尚未完整寫入或 JSON 格式無效。",
        "invalid_shape": "排程資料格式不符合預期。",
        "unreadable": "排程資料目前無法讀取。",
    }.get(reason, "排程資料目前無法讀取。")
    return f"排程資料目前無法使用：{detail}"


def _safe_reason(
    reason: object,
) -> str:
    if reason in (
        _components.ARTIFACT_REASON_CODES
        | _components.CLIENT_FAILURE_REASON_CODES
        | _components.UI_REASON_CODES
    ):
        return str(reason)
    return "read_failure"


def _registry_data_state(registry: ScheduleRegistryState) -> _components.DataState:
    content = "populated" if registry.schedules else "empty"
    if registry.status == "api_available":
        return _components.DataState(
            source="authoritative",
            content=content,
            freshness="unknown",
            operation="idle",
            source_id="system.schedules",
        )
    return _components.DataState(
        source="unavailable",
        content="unknown",
        freshness="unknown",
        operation="idle",
        source_id="system.schedules",
        reason_code=_safe_reason(registry.reason),
        recovery_key="open-data-health",
    )


def _latest_report_result() -> tuple[str | None, str | None]:
    """Return the newest strict Daily Summary as a short safe markdown blurb."""

    result = _read_api.load_daily_summary()
    if isinstance(result, _read_api.DailySummaryApiAvailable):
        summary = result.summary
        lines = [
            f"📅 報告日期:**{summary.as_of_date}**",
            f"✅ 確認檔數:**{len(summary.candidates)}**",
        ]
        if summary.candidates:
            names = [candidate.ticker for candidate in summary.candidates[:5]]
            lines.append("🔝 " + ", ".join(f"${name}" for name in names))
        return "\n\n".join(lines), None
    if isinstance(result, _read_api.DailySummaryApiUnavailable):
        return "每日報告資料目前無法使用", _safe_reason(result.reason)
    if isinstance(result, _read_api.DailySummaryApiFailure):
        return "每日報告服務目前無法使用", _safe_reason(result.reason)
    return "每日報告服務目前無法使用", "invalid_envelope"


def _latest_ledger_result() -> str | None:
    df = _shared.load_ledger()
    if df is None or df.empty:
        return None
    last_scan = df["scan_date"].max()
    last_scan_str = last_scan.date().isoformat() if last_scan is not None else "?"
    return f"📒 帳本筆數:**{len(df)}**\n\n🕒 最新掃描日期:**{last_scan_str}**"


def _latest_reflection_result() -> str | None:
    detail = _latest_reflection_detail()
    if not detail:
        return None
    return detail["summary"]


def _latest_reflection_detail() -> dict[str, str] | None:
    refl_dir = _shared.REPORTS_DIR / "reflections"
    if not refl_dir.exists():
        return None
    files = sorted(refl_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    latest = files[0]
    text = latest.read_text(encoding="utf-8")
    return {
        "name": latest.name,
        "summary": "📝 最新反思已產生，可查看人讀摘要。",
        "text": text,
    }


def _extract_llm_reflection_json(text: str) -> dict | None:
    marker = "## LLM Reflection"
    marker_at = text.find(marker)
    if marker_at < 0:
        return None

    body = text[marker_at + len(marker):].strip()
    if body.startswith("```"):
        lines = body.splitlines()
        for i, line in enumerate(lines[1:], start=1):
            if line.strip().startswith("```"):
                body = "\n".join(lines[1:i]).strip()
                break

    brace_at = body.find("{")
    if brace_at < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(body[brace_at:], start=brace_at):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(body[brace_at:i + 1])
                except Exception:
                    return None
                return data if isinstance(data, dict) else None
    return None


def _contains_prohibited_diagnostic(value: object) -> bool:
    return _shared.contains_prohibited_diagnostic(value)


def _safe_reflection_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if _contains_prohibited_diagnostic(text):
        LOGGER.warning(
            "event_code=%s error_type=%s",
            _REFLECTION_EVENT,
            SuppressedDiagnostic.__name__,
        )
        return None
    return text


def _render_reflection_summary(data: dict) -> None:
    st.markdown("### 人讀摘要")
    if _contains_prohibited_diagnostic(data):
        LOGGER.warning(
            "event_code=%s error_type=%s",
            _REFLECTION_EVENT,
            SuppressedDiagnostic.__name__,
        )
        _components.render_state_banner(
            _components.DataState(
                source="authoritative",
                content="partial",
                freshness="unknown",
                operation="idle",
                source_id="system.reflection",
                reason_code="safety_suppressed",
                event_code=_REFLECTION_EVENT,
                recovery_key="retry",
            )
        )
        return

    warning = data.get("sample_size_warning")
    if isinstance(warning, dict) and warning.get("message"):
        safe_warning = _safe_reflection_text(warning["message"])
        if safe_warning:
            st.warning(safe_warning)

    narrative = _safe_reflection_text(data.get("narrative_summary"))
    if narrative:
        st.write(narrative)

    flags = data.get("data_quality_flags")
    if isinstance(flags, list) and flags:
        safe_flags = [safe for value in flags if (safe := _safe_reflection_text(value))]
        if safe_flags:
            st.markdown("#### 資料缺口")
            for flag in safe_flags:
                st.caption(f"• {flag}")

    actions = data.get("proposed_prompt_changes")
    if isinstance(actions, list) and actions:
        safe_actions: list[tuple[str, str, bool]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            change = _safe_reflection_text(
                action.get("suggested_change") or action.get("section") or "Review"
            )
            rationale = _safe_reflection_text(action.get("rationale") or "")
            if change:
                safe_actions.append((change, rationale or "", bool(action.get("user_action_required"))))
        if safe_actions:
            st.markdown("#### 建議行動")
            for change, rationale, needs_user in safe_actions:
                suffix = "（需人工處理）" if needs_user else ""
                st.write(f"• {change}{suffix}")
                if rationale:
                    st.caption(rationale)


def _render_reflection_detail(detail: dict[str, str]) -> None:
    text = detail.get("text", "")
    data = _extract_llm_reflection_json(text)
    if data:
        _render_reflection_summary(data)
    else:
        st.caption("目前沒有可安全顯示的結構化反思摘要。")


def _fetch_result(
    fetcher: ScheduleResultFetcher | None,
) -> tuple[str | None, str | None]:
    """Run one result reader without exposing its exception or unsafe payload."""
    if fetcher is None:
        return None, None
    try:
        payload = fetcher()
        if isinstance(payload, tuple):
            result, reason = payload
        else:
            result, reason = payload, None
        if reason is not None:
            reason = _safe_reason(reason)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "event_code=%s error_type=%s",
            _RESULT_EVENT,
            type(exc).__name__,
        )
        return None, "read_failure"
    if result and _contains_prohibited_diagnostic(result):
        LOGGER.warning(
            "event_code=%s error_type=%s",
            _RESULT_EVENT,
            SuppressedDiagnostic.__name__,
        )
        return None, "safety_suppressed"
    return result, reason


def _latest_crypto_result() -> tuple[str | None, str | None]:
    result = _read_api.load_crypto_universe()
    if isinstance(result, _read_api.CryptoUniverseApiAvailable):
        snapshot = result.snapshot
        return (
            f"🪙 USDT 永續:**{snapshot.count}** 檔\n\n"
            f"📅 {snapshot.date} · ➕{len(snapshot.added)} / "
            f"➖{len(snapshot.removed)}(對比 {snapshot.compared_to or '無'})",
            None,
        )
    if isinstance(result, _read_api.CryptoUniverseApiUnavailable):
        return "🪙 幣種清單資料目前無法使用", _safe_reason(result.reason)
    if isinstance(result, _read_api.CryptoUniverseApiFailure):
        return "🪙 幣種清單服務目前無法使用", _safe_reason(result.reason)
    return "🪙 幣種清單服務目前無法使用", "invalid_envelope"


def _latest_cot_result() -> tuple[str | None, str | None]:
    result = _read_api.load_cot_catalog()
    if isinstance(result, _read_api.CotCatalogApiAvailable):
        reports = result.catalog.reports
        if not reports:
            return None, None
        return f"📑 最新週報:`{reports[0].report_date}.md`", None
    if isinstance(result, _read_api.CotCatalogApiUnavailable):
        return "📑 COT 週報資料目前無法使用", _safe_reason(result.reason)
    if isinstance(result, _read_api.CotCatalogApiFailure):
        return "📑 COT 週報服務目前無法使用", _safe_reason(result.reason)
    return "📑 COT 週報服務目前無法使用", "invalid_envelope"


def _latest_options_flow_result(
) -> tuple[str | None, str | None]:
    result = _read_api.load_options_flow()
    if isinstance(result, _read_api.OptionsFlowApiAvailable):
        sigs = result.feed.signals
        bull = sum(1 for signal in sigs if signal.direction == "bullish")
        bear = sum(1 for signal in sigs if signal.direction == "bearish")
        top = ", ".join(signal.ticker for signal in sigs[:5])
        content = (
            f"🚨 {result.feed.as_of} · 偵測 **{result.feed.signal_count}** 筆"
            f"(🟢{bull} / 🔴{bear})"
        )
        if top:
            content += f"\n\n前 5:{top}"
        return content, None
    if isinstance(result, _read_api.OptionsFlowApiUnavailable):
        return "🚨 異常流資料目前無法使用", _safe_reason(result.reason)
    return "🚨 異常流服務目前無法使用", _safe_reason(result.reason)


def _latest_candidate_refresh_result(
) -> tuple[str | None, str | None]:
    ranked_result = _read_api.load_ranked_candidates()
    money_flow_result = _read_api.load_money_flow()
    ranked_available = isinstance(
        ranked_result,
        _read_api.RankedCandidatesApiAvailable,
    )
    money_flow_available = isinstance(
        money_flow_result,
        _read_api.MoneyFlowApiAvailable,
    )
    rows = ranked_result.feed.candidates if ranked_available else ()
    ranked_reason = None if ranked_available else _safe_reason(ranked_result.reason)
    money_flow = money_flow_result.snapshot if money_flow_available else None
    money_flow_reason = (
        None if money_flow_available else _safe_reason(money_flow_result.reason)
    )

    scan_date = (
        ranked_result.feed.scan_date
        if ranked_available
        else money_flow.as_of_date if money_flow is not None else None
    ) or "?"
    top = ", ".join(candidate.ticker for candidate in rows[:5])
    if money_flow is not None:
        publishable = "可發布" if money_flow.publishable else "未達門檻"
        ratio_text = f"{money_flow.coverage.coverage_ratio * 100:.0f}%"
        money_flow_summary = f"資金流:{publishable} · 覆蓋率 **{ratio_text}**"
    elif isinstance(money_flow_result, _read_api.MoneyFlowApiUnavailable):
        money_flow_summary = "資金流:資料目前無法使用"
    else:
        money_flow_summary = "資金流:服務目前無法使用"
    ranked_summary = f" · 排名 **{len(rows)}** 檔" if ranked_available else ""
    return (
        f"📅 {scan_date}{ranked_summary}"
        f"\n\n{money_flow_summary}"
        + (f"\n\n前 5:{top}" if top else ""),
        ranked_reason or money_flow_reason,
    )


def _latest_data_health_result() -> str | None:
    data = _shared.load_json(
        str(_shared.REPORTS_DIR / "run_status" / "data-health-refresh.json")
    )
    if not isinstance(data, dict):
        return None
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    status = {
        "running": "執行中",
        "succeeded": "完成",
        "failed": "失敗",
    }.get(str(data.get("status") or ""), str(data.get("status") or "未知"))
    updated = data.get("finished_at") or data.get("updated_at") or "?"
    return (
        f"狀態：**{status}** · 更新 `{updated}`"
        f"\n\n核心 tickers **{metrics.get('tickers', '-')}** · "
        f"其他來源失敗 **{metrics.get('supplemental_failures', 0)}** · "
        f"Warnings/Blockers **{metrics.get('warnings', '-')}/{metrics.get('blockers', '-')}**"
    )


def _latest_theme_flow_result() -> tuple[str | None, str | None]:
    result = _read_api.load_theme_flow()
    if isinstance(result, _read_api.ThemeFlowApiAvailable):
        snapshot = result.snapshot
        return (
            f"資料日期 **{snapshot.as_of}** · 主題 **{len(snapshot.themes)}** 個"
            f"\n\n產生時間 `{snapshot.generated_at}`",
            None,
        )
    if isinstance(result, _read_api.ThemeFlowApiUnavailable):
        return "主題資金流資料目前無法使用", _safe_reason(result.reason)
    if isinstance(result, _read_api.ThemeFlowApiFailure):
        return "主題資金流服務目前無法使用", _safe_reason(result.reason)
    return "主題資金流服務目前無法使用", "invalid_envelope"


_RESULT_FETCHERS = {
    "report_dir": _latest_report_result,
    "ledger": _latest_ledger_result,
    "reflection": _latest_reflection_result,
    "crypto_universe": _latest_crypto_result,
    "cot": _latest_cot_result,
    "options_flow": _latest_options_flow_result,
    "candidate_refresh": _latest_candidate_refresh_result,
    "data_health": _latest_data_health_result,
    "theme_flow": _latest_theme_flow_result,
}


def _status_chip(result: str | None) -> str:
    """Return a chip indicating run status based on whether a result exists."""
    if result:
        return _shared.chip("有資料", _shared.GREEN)
    return _shared.chip("無資料", _shared.MUTED)


def render() -> None:
    st.header("⏱ 排程與執行結果")
    st.caption(
        "排程清單由本機 loopback API 讀取；"
        "清單包含測試機持久化 systemd timers 與 GitHub Actions。"
        "已遷移的摘要由 loopback API 讀取，其餘結果仍直接讀取共享產物。"
    )

    registry = _load_schedules()
    state = _registry_data_state(registry)
    if registry.status in {"api_unavailable", "api_failure"}:
        _components.render_state_banner(state)
        return
    if state.content == "empty":
        _components.render_state_banner(state)
    else:
        _components.render_source_meta(state)

    schedules = registry.schedules
    if not schedules:
        return

    _CAT_ORDER = ["美股", "系統", "幣圈"]
    raw_cats = {schedule.category for schedule in schedules}
    ordered_cats = [c for c in _CAT_ORDER if c in raw_cats] + sorted(raw_cats - set(_CAT_ORDER))
    categories = ["全部"] + ordered_cats
    chosen = st.radio("分類", categories, horizontal=True)
    result_cache: dict[str, tuple[str | None, str | None]] = {}

    for sch in schedules:
        category = sch.category
        if chosen != "全部" and category != chosen:
            continue

        if sch.result_type in {
            "candidate_refresh",
            "crypto_universe",
            "cot",
            "options_flow",
            "report_dir",
            "theme_flow",
        }:
            if sch.result_type not in result_cache:
                result_cache[sch.result_type] = _fetch_result(
                    _RESULT_FETCHERS.get(sch.result_type)
                )
            result, result_reason = result_cache[sch.result_type]
        else:
            fetcher = _RESULT_FETCHERS.get(sch.result_type)
            result, result_reason = _fetch_result(fetcher)
        reflection_detail = None
        if result and sch.result_type == "reflection":
            try:
                reflection_detail = _latest_reflection_detail()
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "event_code=%s error_type=%s",
                    _RESULT_EVENT,
                    type(exc).__name__,
                )
                result = None
                result_reason = "read_failure"

        with st.container(border=True):
            # Fix 1: two-column layout — left=meta, right=status+result
            col_left, col_right = st.columns([3, 2])

            with col_left:
                st.subheader(str(sch.name))
                _shared.chips_row([(category, _shared.BLUE)])
                st.markdown(
                    f"🗓 `{sch.cron}`  ·  {sch.cron_note}"
                )
                if sch.description:
                    st.caption(sch.description)

            with col_right:
                _shared.chips_row(
                    [("有資料", _shared.GREEN)] if result else [("無資料", _shared.MUTED)]
                )
                st.markdown("**最近一次執行結果**")
                if result_reason:
                    _components.render_state_banner(
                        _components.DataState(
                            source="unavailable",
                            content="unknown",
                            freshness="unknown",
                            operation="idle",
                            source_id="system.schedule-result",
                            reason_code=result_reason,
                            event_code=_RESULT_EVENT,
                            recovery_key="retry",
                        )
                    )
                if result:
                    # Fix 2: use st.markdown instead of st.success to avoid
                    # the green background that hurts CJK readability
                    st.markdown(result)
                elif not result_reason:
                    st.caption("尚無可顯示的產出(管線可能還沒跑過,或尚未接上)。")

            if reflection_detail:
                if reflection_detail.get("text"):
                    with st.expander("查看完整反思", expanded=False):
                        _render_reflection_detail(reflection_detail)
                else:
                    st.caption("反思檔存在,但完整內容無法讀取。")
