"""Today Decision local candidate refresh controls."""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _components, _shared, _run_status_view as run_status_view
from scripts.candidate_pipeline_controls import (
    CandidateRunParams,
    RUN_MODE_LABELS,
    launch_background,
    read_pending_codex_request,
    refresh_codex_auth_status,
    resume_pending_codex_run,
)


_RUN_STATUS_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local.json"
_RUN_HISTORY_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local-history.jsonl"
_RANK_STAGE_ID = "rank_candidates"
_CANDIDATE_RUNNING_TTL_SECONDS = 60 * 60
_LAST_LAUNCH_KEY = "candidate_pipeline_last_launch"

_LOGGER = logging.getLogger(__name__)
_CANDIDATE_EVENTS = frozenset({
    "QR-CANDIDATE-LAUNCH-001",
    "QR-CANDIDATE-AUTH-001",
    "QR-CANDIDATE-STATUS-001",
})
_MODE_LABELS = {
    **RUN_MODE_LABELS,
    "codex_auth_login": "登入中",
    "unknown": "本機篩選",
}
_OPERATIONS = frozenset({"loading", "success", "failure"})
_STATUS_LABELS = {
    "running": "執行中",
    "succeeded": "成功",
    "failed": "失敗",
    "unknown": "未知",
}
_STAGE_LABELS = {
    "preflight": "本機流程初始化",
    "hard_filter.fetch_ohlcv": "抓取市場資料",
    "hard_filter.info": "補充公司資料",
    "hard_filter.apply_filters": "套用基礎篩選",
    "rank_candidates": "程式排序候選",
    "options_gate": "檢查期權可交易性",
    "llm_score.regime": "計算大盤環境",
    "llm_score.candidates": "AI 評分候選",
    "analytics_refresh": "更新資料與分析",
    "done": "完成",
    "interrupted": "本機候選刷新中斷",
}
_SAFE_METRIC_KEYS = frozenset({
    "total_tickers",
    "batch_size",
    "total_batches",
    "completed_batches",
    "downloaded_tickers",
    "data_available",
    "info_tickers",
    "filter_tickers",
    "passed_hard_filters",
    "rejected",
    "ranked_candidates",
    "rank_limit",
    "rank_source_candidates",
    "options_gate_requested",
    "options_gate_checked",
    "options_usable",
    "options_watch",
    "options_unusable",
    "options_unknown",
    "candidate_limit",
    "total_candidates",
    "already_scored",
    "scored_candidates",
    "remaining_candidates",
    "errored_candidates",
    "deferred_candidates",
    "analytics_candidate_rankings",
    "analytics_candidate_scores",
})
_SAFE_OUTPUT_KEYS = frozenset({
    "filtered_universe",
    "ranked_candidates",
    "scored_candidates",
})
_SAFE_RUN_ID_RE = re.compile(
    r"^candidates-local-\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


def _log_failure(event_code: str, exc: BaseException) -> None:
    _LOGGER.warning(
        "event_code=%s error_type=%s",
        event_code,
        type(exc).__name__,
    )


def _safe_launch_projection(
    value: object,
    *,
    operation: str | None = None,
    event_code: str | None = None,
) -> dict:
    """Return the only launch metadata allowed in Streamlit session state."""
    raw = value if isinstance(value, dict) else {}
    mode = str(raw.get("mode") or "unknown")
    if mode not in _MODE_LABELS:
        mode = "unknown"
    projected_operation = operation or str(raw.get("operation") or "loading")
    if projected_operation not in _OPERATIONS:
        projected_operation = "loading"
    projected_event = (
        event_code
        if isinstance(event_code, str) and event_code in _CANDIDATE_EVENTS
        else raw.get("event_code")
    )
    if not isinstance(projected_event, str):
        projected_event = None
    if projected_event not in _CANDIDATE_EVENTS:
        projected_event = None
    if projected_event:
        projected_operation = "failure"
    return {
        "mode": mode,
        "mode_label": _MODE_LABELS[mode],
        "operation": projected_operation,
        "event_code": projected_event,
    }


def _normalize_launch_session() -> None:
    if _LAST_LAUNCH_KEY in st.session_state:
        st.session_state[_LAST_LAUNCH_KEY] = _safe_launch_projection(
            st.session_state.get(_LAST_LAUNCH_KEY)
        )


def _set_launch_state(
    value: object,
    *,
    operation: str | None = None,
    event_code: str | None = None,
) -> dict:
    projected = _safe_launch_projection(
        value,
        operation=operation,
        event_code=event_code,
    )
    st.session_state[_LAST_LAUNCH_KEY] = projected
    return projected


def _safe_number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _metric_display(value: object) -> int | float | str:
    safe = _safe_number(value)
    return safe if safe is not None else "-"


def _safe_timestamp(value: object) -> str | None:
    parsed = run_status_view.parse_utc(value)
    if parsed is None:
        return None
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_stage_id(value: object) -> str | None:
    stage_id = str(value or "")
    return stage_id if stage_id in _STAGE_LABELS else None


def _safe_stage_label(stage: object) -> str:
    if not isinstance(stage, dict):
        return "本機候選刷新"
    stage_id = _safe_stage_id(stage.get("id"))
    return _STAGE_LABELS.get(stage_id, "本機候選刷新")


def _safe_metrics(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in _SAFE_METRIC_KEYS:
        safe = _safe_number(value.get(key))
        if safe is not None:
            out[key] = safe
    return out


def _safe_history_record(data: object) -> dict:
    """Project a new UI-owned history row without raw diagnostic fields."""
    raw = data if isinstance(data, dict) else {}
    run_id = str(raw.get("run_id") or "")
    if not _SAFE_RUN_ID_RE.fullmatch(run_id):
        run_id = ""
    status = str(raw.get("status") or "unknown")
    if status not in _STATUS_LABELS:
        status = "unknown"
    stage = raw.get("stage") if isinstance(raw.get("stage"), dict) else {}
    stage_id = _safe_stage_id(stage.get("id")) or "interrupted"
    pct = _safe_number(stage.get("progress_pct"))
    pct = max(0.0, min(100.0, float(pct))) if pct is not None else 0.0
    stage_status = str(stage.get("status") or status)
    if stage_status not in _STATUS_LABELS:
        stage_status = "unknown"

    outputs = {}
    raw_outputs = raw.get("outputs") if isinstance(raw.get("outputs"), dict) else {}
    for key in _SAFE_OUTPUT_KEYS:
        item = raw_outputs.get(key)
        if isinstance(item, dict):
            outputs[key] = {
                "exists": bool(item.get("exists")),
                "stale": bool(item.get("stale")),
            }

    warnings = raw.get("warnings") if isinstance(raw.get("warnings"), list) else []
    errors = raw.get("errors") if isinstance(raw.get("errors"), list) else []
    event_code = "QR-CANDIDATE-STATUS-001" if errors or status == "failed" else None
    return {
        "run_id": run_id,
        "job": "candidates-local" if raw.get("job") == "candidates-local" else "",
        "status": status,
        "started_at": _safe_timestamp(raw.get("started_at")),
        "updated_at": _safe_timestamp(raw.get("updated_at")),
        "finished_at": _safe_timestamp(raw.get("finished_at")),
        "stage": {
            "id": stage_id,
            "label": _STAGE_LABELS[stage_id],
            "status": stage_status,
            "progress_pct": pct,
        },
        "metrics": _safe_metrics(raw.get("metrics")),
        "outputs": outputs,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "event_code": event_code,
    }


def _candidate_interrupt_reason(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> str | None:
    return run_status_view.running_interrupt_reason(
        data,
        stale_after_seconds=_CANDIDATE_RUNNING_TTL_SECONDS,
        stale_message="本機候選刷新已超過 60 分鐘未更新，可能已中斷。",
        pid_gone_message="背景程序已不存在，這次本機候選刷新已中斷。",
        now=now,
        process_checker=process_checker,
    )


def _interrupted_candidate_status(
    data: dict,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict:
    return run_status_view.interrupted_status(
        data,
        reason,
        default_label="本機候選刷新中斷",
        now=now,
    )


def _write_candidate_status(data: dict) -> None:
    _RUN_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _RUN_STATUS_PATH.with_name(f"{_RUN_STATUS_PATH.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_RUN_STATUS_PATH)


def _append_candidate_history(data: dict) -> None:
    _RUN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = _safe_history_record(data)
    with _RUN_HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _load_candidate_status() -> dict | None:
    data = _shared.load_json(str(_RUN_STATUS_PATH))
    if not isinstance(data, dict):
        return None
    reason = _candidate_interrupt_reason(data)
    if not reason:
        return data
    fixed = _interrupted_candidate_status(data, reason)
    try:
        _write_candidate_status(fixed)
        _append_candidate_history(fixed)
    except OSError:
        return fixed
    return fixed


def _status_is_active(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> bool:
    return run_status_view.running_status_is_active(
        data,
        stale_after_seconds=_CANDIDATE_RUNNING_TTL_SECONDS,
        stale_message="本機候選刷新已超過 60 分鐘未更新，可能已中斷。",
        pid_gone_message="背景程序已不存在，這次本機候選刷新已中斷。",
        now=now,
        process_checker=process_checker,
    )


def _candidate_run_history(limit: int = 8) -> list[dict]:
    # History is JSONL: reports/run_status/candidates-local-history.jsonl
    if not _RUN_HISTORY_PATH.exists():
        return []
    rows = []
    try:
        lines = _RUN_HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _history_flow(row: dict) -> str:
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}

    if (
        metrics.get("passed_hard_filters") is not None
        or metrics.get("completed_batches") is not None
        or metrics.get("filter_rules") is not None
    ):
        return "完整刷新 + 排名"
    if metrics.get("scored_candidates") is not None:
        return "少量 LLM"
    if (
        metrics.get("ranked_candidates") is not None
        or metrics.get("rank_source_candidates") is not None
    ):
        return "只重排"
    return "-"


def _status_zh(value) -> str:
    return _STATUS_LABELS.get(str(value or "unknown"), "未知")


def _scored_progress_label(metrics: dict) -> str | None:
    scored = _safe_number(metrics.get("scored_candidates"))
    if scored is None:
        return None
    limit = _safe_number(metrics.get("candidate_limit"))
    if isinstance(scored, int) and isinstance(limit, int) and limit > 0:
        if scored <= limit:
            return f"LLM 深檢 {scored}/{limit}"
        return f"LLM 深檢累積 {scored}（本次上限 {limit}）"
    return f"LLM 深檢 {scored}"


def _status_message_zh(message: str) -> str | None:
    match = re.fullmatch(r"(\d+) candidates scored;\s*(\d+) remaining", str(message).strip())
    if match:
        scored, remaining = match.groups()
        return f"LLM 已累積 {scored} 檔；尚有 {remaining} 檔未深檢"
    return None


def _history_df(rows: list[dict]) -> pd.DataFrame:
    out = []
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        out.append({
            "完成時間": _safe_timestamp(row.get("finished_at") or row.get("started_at")) or "-",
            "狀態": _status_zh(row.get("status")),
            "流程": _history_flow(row),
            "通過基礎篩選": _metric_display(
                metrics.get("passed_hard_filters", metrics.get("rank_source_candidates"))
            ),
            "排名產出": _metric_display(metrics.get("ranked_candidates")),
            "Top N 上限": _metric_display(metrics.get("rank_limit")),
            "期權檢查數": _metric_display(metrics.get("options_gate_checked")),
        })
    return pd.DataFrame(out)


def _render_launch_tracking(status_data: dict | None) -> None:
    meta = st.session_state.get(_LAST_LAUNCH_KEY)
    if not isinstance(meta, dict):
        return

    mode = meta.get("mode")
    mode_label = _MODE_LABELS.get(str(mode), "本機篩選")
    stage = status_data.get("stage") if isinstance(status_data, dict) and isinstance(status_data.get("stage"), dict) else {}
    status = status_data.get("status") if isinstance(status_data, dict) else "unknown"
    status_label = _status_zh(status)
    stage_label = _safe_stage_label(stage)

    st.caption(
        f"最近啟動：{mode_label} · "
        f"目前 {status_label} / {stage_label}。下方「本機候選刷新」每 8 秒更新。"
    )
    if meta.get("operation") == "failure":
        _components.render_state_banner(_components.DataState(
            source="authoritative",
            content="unknown",
            freshness="unknown",
            operation="failure",
            source_id="candidate.pipeline",
            reason_code="operation_failure",
            event_code=meta.get("event_code") or "QR-CANDIDATE-LAUNCH-001",
            recovery_key="retry",
        ))


def _read_pending_request_safe() -> dict | None:
    try:
        pending = read_pending_codex_request()
    except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
        _log_failure("QR-CANDIDATE-AUTH-001", exc)
        _set_launch_state(
            {"mode": "codex_auth_login"},
            operation="failure",
            event_code="QR-CANDIDATE-AUTH-001",
        )
        return None
    return pending if isinstance(pending, dict) else None


@st.fragment(run_every="8s")
def _render_codex_auth_status() -> None:
    pending = _read_pending_request_safe()
    meta = st.session_state.get(_LAST_LAUNCH_KEY)
    meta_dict = meta if isinstance(meta, dict) else {}
    auth_launching = isinstance(meta, dict) and meta.get("mode") == "codex_auth_login"
    if not pending and not auth_launching:
        return

    try:
        auth = refresh_codex_auth_status()
        if not isinstance(auth, dict):
            raise TypeError("invalid auth state")
    except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
        _log_failure("QR-CANDIDATE-AUTH-001", exc)
        _set_launch_state(
            {"mode": "codex_auth_login"},
            operation="failure",
            event_code="QR-CANDIDATE-AUTH-001",
        )
        auth = {"ok": False, "state": "failure"}
    resumed = None
    if auth.get("ok") is True and pending:
        try:
            resumed = resume_pending_codex_run()
            if resumed:
                _set_launch_state(resumed, operation="loading")
                pending = None
        except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
            _log_failure("QR-CANDIDATE-AUTH-001", exc)
            _set_launch_state(
                {"mode": "codex_auth_login"},
                operation="failure",
                event_code="QR-CANDIDATE-AUTH-001",
            )
            auth = {"ok": False, "state": "failure"}

    state = str(auth.get("state") or "unknown")
    ok = auth.get("ok") is True
    failed = state in {"missing_cli", "failed", "failure", "error"}
    operation = "success" if ok else ("failure" if failed else "loading")
    color = _shared.GREEN if ok else _shared.AMBER
    label = "Codex 已登入" if ok else "Codex 登入中"

    with st.container(border=True):
        st.markdown("##### 登入中" if not ok else "##### 認證狀態")
        _shared.chips_row([(label, color)])
        _components.render_state_banner(_components.DataState(
            source="authoritative",
            content="unknown",
            freshness="unknown",
            operation=operation,
            source_id="candidate.pipeline",
            reason_code="operation_failure" if failed else None,
            event_code="QR-CANDIDATE-AUTH-001" if failed else None,
            recovery_key="retry" if failed else None,
        ))
        st.caption("登入完成後會自動接續少量 LLM。")
        if resumed:
            st.success("已登入，並自動接續少量 LLM。")
        elif failed:
            st.error("目前無法完成登入，請稍後再試；若持續發生，請聯絡系統管理者。")
        elif not ok:
            st.info("請完成 Codex ChatGPT device login；完成後會自動接續。")
            auth_url = auth.get("auth_url") or meta_dict.get("auth_url")
            user_code = auth.get("user_code") or meta_dict.get("user_code")
            if auth_url:
                st.link_button("前往 Codex 登入", auth_url, type="primary",
                               use_container_width=True)
            if user_code:
                st.caption(f"一次性代碼：`{user_code}`")
        if pending:
            raw = pending.get("params") if isinstance(pending, dict) else {}
            limit = _safe_number(raw.get("candidate_limit")) if isinstance(raw, dict) else None
            limit = limit if limit is not None else "-"
            st.caption(f"等待登入後自動接續：少量 LLM · {limit} 檔")


def _launch_candidate_run(mode: str, *, rank_limit: int, options_gate_limit: int,
                          candidate_limit: int, universe: str, yf_batch_size: int,
                          min_data_coverage: float, min_avg_dollar_vol: int,
                          min_market_cap: int, min_price: float,
                          max_ret_5d: float, max_ret_20d: float,
                          earnings_exclude_days: int) -> None:
    params = CandidateRunParams(
        mode=mode,
        rank_limit=rank_limit,
        options_gate_limit=options_gate_limit,
        candidate_limit=candidate_limit,
        universe=universe,
        yf_batch_size=yf_batch_size,
        min_data_coverage=min_data_coverage,
        min_avg_dollar_vol=min_avg_dollar_vol,
        min_market_cap=min_market_cap,
        min_price=min_price,
        max_ret_5d=max_ret_5d,
        max_ret_20d=max_ret_20d,
        earnings_exclude_days=earnings_exclude_days,
    )
    try:
        meta = launch_background(params)
        if not isinstance(meta, dict):
            raise TypeError("invalid launch metadata")
    except Exception as exc:  # noqa: BLE001 - fixed fail-soft UI boundary
        _log_failure("QR-CANDIDATE-LAUNCH-001", exc)
        _set_launch_state(
            {"mode": mode},
            operation="failure",
            event_code="QR-CANDIDATE-LAUNCH-001",
        )
        return
    _set_launch_state(meta, operation="loading")


def _render_candidate_pipeline_controls() -> None:
    status_data = _load_candidate_status()
    running = _status_is_active(status_data)
    codex_pending = bool(_read_pending_request_safe())

    with st.container(border=True):
        st.markdown("##### 本機篩選控制台")
        st.caption("日常先跑完整刷新產生今日排名；LLM 深檢只補少量標的的敘事與風險摘要。")
        top1, top2, top3 = st.columns(3)
        with top1:
            rank_limit = int(st.number_input(
                "排名 Top N",
                min_value=5,
                max_value=200,
                value=50,
                step=5,
                help="RANK_LIMIT：從基礎篩選後保留多少檔進入今日排名。",
            ))
        with top2:
            options_gate_limit = int(st.number_input(
                "期權檢查數",
                min_value=0,
                max_value=50,
                value=10,
                step=1,
                help="OPTIONS_GATE_LIMIT：只對排名前 N 檔做免費期權可交易性初篩；0 代表關閉。",
            ))
        with top3:
            candidate_limit = int(st.number_input(
                "LLM 深檢數",
                min_value=1,
                max_value=25,
                value=3,
                step=1,
                help="CANDIDATE_LIMIT：每次少量 LLM 要檢查的 ranked pool 標的數。",
            ))

        advanced = st.expander("過篩參數", expanded=False)
        with advanced:
            a1, a2, a3 = st.columns(3)
            with a1:
                universe = st.selectbox("UNIVERSE", ["sp1500", "nasdaq_only", "russell3000", "custom"],
                                        index=0)
                yf_batch_size = int(st.number_input("YF_BATCH_SIZE", min_value=1,
                                                    max_value=100, value=25, step=1))
                min_data_coverage = float(st.number_input("MIN_DATA_COVERAGE", min_value=0.1,
                                                          max_value=1.0, value=0.70,
                                                          step=0.05, format="%.2f"))
            with a2:
                min_avg_dollar_vol = int(st.number_input("MIN_AVG_DOLLAR_VOL", min_value=0,
                                                         max_value=1_000_000_000,
                                                         value=5_000_000,
                                                         step=1_000_000))
                min_market_cap = int(st.number_input("MIN_MARKET_CAP", min_value=0,
                                                     max_value=50_000_000_000,
                                                     value=300_000_000,
                                                     step=100_000_000))
                min_price = float(st.number_input("MIN_PRICE", min_value=0.0,
                                                  max_value=500.0, value=5.0,
                                                  step=1.0))
            with a3:
                max_ret_5d = float(st.number_input("MAX_RET_5D", min_value=1.0,
                                                   max_value=200.0, value=30.0,
                                                   step=1.0))
                max_ret_20d = float(st.number_input("MAX_RET_20D", min_value=1.0,
                                                    max_value=300.0, value=60.0,
                                                    step=1.0))
                earnings_exclude_days = int(st.number_input("EARNINGS_EXCLUDE_DAYS",
                                                            min_value=0, max_value=30,
                                                            value=2, step=1))
            st.divider()
            if st.button("只重排（進階）", key="candidate_rank_existing",
                         disabled=running, use_container_width=True):
                _launch_candidate_run(
                    "rank_existing",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )

        if running:
            st.caption("已有本機篩選在執行;完成或超過 60 分鐘未更新後才能再啟動。")
        if codex_pending:
            st.caption("Codex 登入中；登入後自動接續少量 LLM。")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("完整刷新", key="candidate_full_refresh",
                         disabled=running, use_container_width=True):
                _launch_candidate_run(
                    "full_refresh",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )
        with b2:
            if st.button("少量 LLM", key="candidate_llm_deep_check",
                         disabled=running or codex_pending, use_container_width=True):
                _launch_candidate_run(
                    "llm_deep_check",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )

        latest_status = _load_candidate_status()
        _render_launch_tracking(latest_status)

        history = _candidate_run_history()
        if history:
            st.markdown("##### 篩選紀錄")
            st.dataframe(_history_df(history), hide_index=True, use_container_width=True,
                         height=220)


@st.fragment(run_every="8s")
def _render_local_refresh_status() -> None:
    # Single latest status file: reports/run_status/candidates-local.json
    # UI reads only allowlisted stage/status fields and numeric progress metrics.
    # ranked_candidates.json progress comes from the rank_candidates stage metrics.
    data = _load_candidate_status()
    if not isinstance(data, dict) or data.get("job") != "candidates-local":
        return

    status = str(data.get("status") or "unknown")
    if status not in _STATUS_LABELS:
        status = "unknown"
    status_label = _status_zh(status)
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    pct = _safe_number(stage.get("progress_pct"))
    pct = float(pct) if pct is not None else 0.0
    pct = max(0.0, min(100.0, pct))
    updated_at = _safe_timestamp(data.get("updated_at"))
    updated_dt = run_status_view.parse_utc(updated_at)
    stale = status == "running" and updated_dt and (
        datetime.now(timezone.utc) - updated_dt
    ).total_seconds() > _CANDIDATE_RUNNING_TTL_SECONDS

    color = {
        "running": _shared.BLUE,
        "succeeded": _shared.GREEN,
        "failed": _shared.RED,
    }.get(status, _shared.MUTED)
    label = _safe_stage_label(stage)
    message = stage.get("message") or ""
    safe_message = _status_message_zh(str(message)) if message else None
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
    operation = {
        "running": "loading",
        "succeeded": "success",
        "failed": "failure",
    }.get(status, "idle")
    if errors:
        operation = "failure"

    with st.container(border=True):
        head, meta = st.columns([2, 3])
        with head:
            st.markdown("##### 本機候選刷新")
            _shared.chips_row([(status_label, color)])
        with meta:
            parts = []
            completed_batches = _safe_number(metrics.get("completed_batches"))
            total_batches = _safe_number(metrics.get("total_batches"))
            if completed_batches is not None and total_batches is not None:
                parts.append(f"抓取行情 {completed_batches}/{total_batches}")
            scored_label = _scored_progress_label(metrics)
            if scored_label:
                parts.append(scored_label)
            ranked_candidates = _safe_number(metrics.get("ranked_candidates"))
            rank_limit = _safe_number(metrics.get("rank_limit"))
            if stage.get("id") == _RANK_STAGE_ID or ranked_candidates is not None:
                ranked_value = ranked_candidates if ranked_candidates is not None else "-"
                limit_value = rank_limit if rank_limit is not None else "-"
                parts.append(f"排名完成 {ranked_value}/{limit_value}")
            options_checked = _safe_number(metrics.get("options_gate_checked"))
            if options_checked is not None:
                parts.append(f"期權檢查 {options_checked}")
            st.caption(" · ".join([label, *parts]) if parts else label)
            if updated_at:
                st.caption(f"更新時間 {updated_at}" + (" · 可能已中斷" if stale else ""))

        st.progress(pct / 100, text=f"{label} · {pct:.1f}%")
        if safe_message:
            st.caption(safe_message)
        if operation != "idle":
            failed = operation == "failure"
            _components.render_state_banner(_components.DataState(
                source="authoritative",
                content="populated",
                freshness="unknown",
                operation=operation,
                source_id="candidate.pipeline",
                reason_code="operation_failure" if failed else None,
                event_code="QR-CANDIDATE-STATUS-001" if failed else None,
                recovery_key="retry" if failed else None,
            ))


def render() -> None:
    _normalize_launch_session()
    _render_candidate_pipeline_controls()
    _render_codex_auth_status()
    _render_local_refresh_status()
