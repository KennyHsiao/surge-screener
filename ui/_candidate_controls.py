"""Today Decision local candidate refresh controls."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared, _run_status_view as run_status_view
from scripts.candidate_pipeline_controls import (
    CandidateRunParams,
    RUN_MODE_LABELS,
    launch_background,
    read_pending_claude_request,
    refresh_claude_auth_status,
    resume_pending_claude_run,
)


_RUN_STATUS_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local.json"
_RUN_HISTORY_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local-history.jsonl"
_RANK_STAGE_ID = "rank_candidates"
_CANDIDATE_RUNNING_TTL_SECONDS = 60 * 60


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
    record = {
        "run_id": data.get("run_id"),
        "job": data.get("job"),
        "status": data.get("status"),
        "started_at": data.get("started_at"),
        "updated_at": data.get("updated_at"),
        "finished_at": data.get("finished_at"),
        "stage": data.get("stage") or {},
        "metrics": data.get("metrics") or {},
        "outputs": data.get("outputs") or {},
        "warnings": data.get("warnings") or [],
        "errors": data.get("errors") or [],
    }
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
    stage = row.get("stage") if isinstance(row.get("stage"), dict) else {}

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
        or "ranked" in str(stage.get("message") or "").lower()
    ):
        return "只重排"
    return "-"


def _status_zh(value) -> str:
    return {
        "running": "執行中",
        "succeeded": "成功",
        "failed": "失敗",
        "unknown": "未知",
    }.get(str(value or "unknown"), str(value or "未知"))


def _scored_progress_label(metrics: dict) -> str | None:
    scored = metrics.get("scored_candidates")
    if scored is None:
        return None
    limit = metrics.get("candidate_limit")
    if isinstance(scored, int) and isinstance(limit, int) and limit > 0:
        if scored <= limit:
            return f"LLM 深檢 {scored}/{limit}"
        return f"LLM 深檢累積 {scored}（本次上限 {limit}）"
    return f"LLM 深檢 {scored}"


def _status_message_zh(message: str) -> str:
    match = re.fullmatch(r"(\d+) candidates scored;\s*(\d+) remaining", message.strip())
    if match:
        scored, remaining = match.groups()
        return f"LLM 已累積 {scored} 檔；尚有 {remaining} 檔未深檢"
    return message


def _history_df(rows: list[dict]) -> pd.DataFrame:
    out = []
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        out.append({
            "完成時間": row.get("finished_at") or row.get("started_at"),
            "狀態": _status_zh(row.get("status")),
            "流程": _history_flow(row),
            "通過基礎篩選": metrics.get("passed_hard_filters", metrics.get("rank_source_candidates", "-")),
            "排名產出": metrics.get("ranked_candidates", "-"),
            "Top N 上限": metrics.get("rank_limit", "-"),
            "期權檢查數": metrics.get("options_gate_checked", "-"),
        })
    return pd.DataFrame(out)


def _tail_text(path: str | Path | None, limit: int = 8) -> str:
    if not path:
        return ""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-limit:])


def _render_launch_tracking(status_data: dict | None) -> None:
    meta = st.session_state.get("candidate_pipeline_last_launch")
    if not isinstance(meta, dict):
        return

    mode = meta.get("mode")
    mode_label = meta.get("mode_label") or RUN_MODE_LABELS.get(mode, "本機篩選")
    command = meta.get("command") if isinstance(meta.get("command"), list) else []
    log_path = meta.get("log_path")
    stage = status_data.get("stage") if isinstance(status_data, dict) and isinstance(status_data.get("stage"), dict) else {}
    status = status_data.get("status") if isinstance(status_data, dict) else "unknown"
    status_label = _status_zh(status)
    stage_label = stage.get("label") or "-"

    st.caption(
        f"最近啟動：{mode_label} · pid={meta.get('pid', '-')} · "
        f"目前 {status_label} / {stage_label}。下方「本機候選刷新」每 8 秒更新。"
    )
    with st.expander("追蹤細節", expanded=False):
        st.caption(f"狀態檔：{_RUN_STATUS_PATH}")
        if log_path:
            st.caption(f"log：{log_path}")
        if command:
            st.code(" ".join(str(part) for part in command), language="bash")
        tail = _tail_text(log_path)
        if tail:
            st.code(tail, language="text")


@st.fragment(run_every="8s")
def _render_claude_auth_status() -> None:
    pending = read_pending_claude_request()
    meta = st.session_state.get("candidate_pipeline_last_launch")
    auth_launching = isinstance(meta, dict) and meta.get("mode") == "claude_auth_login"
    if not pending and not auth_launching:
        return

    auth = refresh_claude_auth_status()
    resumed = None
    if auth.get("ok") and pending:
        resumed = resume_pending_claude_run()
        if resumed:
            st.session_state["candidate_pipeline_last_launch"] = resumed
            pending = None

    state = str(auth.get("state") or "unknown")
    ok = bool(auth.get("ok"))
    color = _shared.GREEN if ok else _shared.AMBER
    label = "Claude 已登入" if ok else "Claude 登入中"
    log_path = (
        (meta or {}).get("log_path")
        if isinstance(meta, dict)
        else None
    ) or auth.get("log_path")

    with st.container(border=True):
        st.markdown("##### Claude 登入中" if not ok else "##### Claude 認證")
        _shared.chips_row([(label, color)])
        st.caption("登入後自動接續少量 LLM；Docker 會透過 CLAUDE_CONFIG_DIR 將認證資料寫入持久化 volume。")
        if resumed:
            st.success("Claude 已登入，已自動接續少量 LLM。")
        elif state == "missing_cli":
            st.error("container 內找不到 `claude` CLI，需先在 image 內安裝或改用 CLAUDE_CODE_OAUTH_TOKEN。")
        elif not ok:
            st.info("請依下方登入輸出操作；若出現 URL 或驗證碼，請在本機瀏覽器開啟或貼回 CLI 流程。")
        if pending:
            raw = pending.get("params") if isinstance(pending, dict) else {}
            limit = raw.get("candidate_limit") if isinstance(raw, dict) else "-"
            st.caption(f"等待登入後自動接續：少量 LLM · {limit} 檔")
        message = auth.get("message")
        if message:
            st.caption(str(message))
        tail = _tail_text(log_path, limit=12)
        if tail:
            st.code(tail, language="text")


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
    meta = launch_background(params)
    st.session_state["candidate_pipeline_last_launch"] = meta


def _render_candidate_pipeline_controls() -> None:
    status_data = _load_candidate_status()
    running = _status_is_active(status_data)
    claude_pending = bool(read_pending_claude_request())

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
        if claude_pending:
            st.caption("Claude 登入中；登入後自動接續少量 LLM。")

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
                         disabled=running or claude_pending, use_container_width=True):
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
    # UI reads stage.progress_pct; it never parses CLI logs.
    # ranked_candidates.json progress comes from the rank_candidates stage metrics.
    data = _load_candidate_status()
    if not isinstance(data, dict) or data.get("job") != "candidates-local":
        return

    status = str(data.get("status") or "unknown")
    status_label = _status_zh(status)
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    pct = stage.get("progress_pct")
    pct = float(pct) if isinstance(pct, (int, float)) else 0.0
    pct = max(0.0, min(100.0, pct))
    updated_at = data.get("updated_at")
    updated_dt = run_status_view.parse_utc(updated_at)
    stale = status == "running" and updated_dt and (
        datetime.now(timezone.utc) - updated_dt
    ).total_seconds() > _CANDIDATE_RUNNING_TTL_SECONDS

    color = {
        "running": _shared.BLUE,
        "succeeded": _shared.GREEN,
        "failed": _shared.RED,
    }.get(status, _shared.MUTED)
    label = stage.get("label") or "本機候選刷新"
    message = stage.get("message") or ""

    with st.container(border=True):
        head, meta = st.columns([2, 3])
        with head:
            st.markdown("##### 本機候選刷新")
            _shared.chips_row([(status_label, color)])
        with meta:
            parts = []
            if metrics.get("completed_batches") and metrics.get("total_batches"):
                parts.append(f"抓取行情 {metrics['completed_batches']}/{metrics['total_batches']}")
            scored_label = _scored_progress_label(metrics)
            if scored_label:
                parts.append(scored_label)
            if stage.get("id") == _RANK_STAGE_ID or metrics.get("ranked_candidates") is not None:
                parts.append(f"排名完成 {metrics.get('ranked_candidates', '-')}/{metrics.get('rank_limit', '-')}")
            if metrics.get("options_gate_checked"):
                parts.append(f"期權檢查 {metrics['options_gate_checked']}")
            st.caption(" · ".join([label, *parts]) if parts else label)
            if updated_at:
                st.caption(f"更新時間 {updated_at}" + (" · 可能已中斷" if stale else ""))

        st.progress(pct / 100, text=f"{label} · {pct:.1f}%")
        if message:
            st.caption(_status_message_zh(str(message)))
        errors = data.get("errors") if isinstance(data.get("errors"), list) else []
        if errors:
            st.error(errors[-1].get("message", "本機候選刷新失敗"))


def render() -> None:
    _render_candidate_pipeline_controls()
    _render_claude_auth_status()
    _render_local_refresh_status()
