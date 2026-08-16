"""研究驗證 · 資料健康 / Analytics DB."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts import analytics_store

from . import _read_api, _shared, _run_status_view as run_status_view


_DATE_COLUMN = {
    "candidate_outcomes": "scan_date",
    "candidate_scores": "scan_date",
    "candidate_rankings": "scan_date",
    "daily_reports": "report_date",
    "iv_history": "as_of_date",
    "market_thesis_forecasts": "as_of_date",
    "options_flow_signals": "as_of_date",
    "oversold_reversal_signals": "as_of_date",
    "performance_ledger": "scan_date",
    "portfolio_positions": "as_of_date",
    "reversal_radar_signals": "as_of_date",
    "risk_guard_rows": "as_of_date",
    "run_status_history": "started_at",
    "sector_rotation_snapshots": "as_of_date",
    "signal_outcomes": "as_of_date",
    "source_observations": "source_date",
    "theme_flow_snapshots": "as_of_date",
    "validation_summaries": "as_of_date",
    "watchlist_sources": "scan_date",
}
_STATUS_COLOR = {
    "PASS": _shared.GREEN,
    "WARN": _shared.AMBER,
    "BLOCK": _shared.RED,
}
_ACTION_LABEL = {
    "NO_ACTION": "無需處理",
    "WATCHLIST_UPGRADE": "加入觀察",
    "REVIEW_REQUIRED": "人工檢查",
    "DOWNGRADE_SIGNAL": "訊號降級",
    "BLOCK_TODAY_SIGNALS": "暫停今日訊號",
}
_STATUS_LABEL = {
    "PASS": "資料可用",
    "WARN": "資料可用，需人工檢查",
    "BLOCK": "資料健康阻擋",
}
_READINESS_LABEL = {
    "PASS": "可發布",
    "WARN": "可發布，需檢查",
    "BLOCK": "暫停發布",
}
_READINESS_CHECK_LABEL = {
    "db:exists": "Analytics DB",
    "db:readable": "Analytics DB 可讀性",
    "table:candidate_rankings:exists": "核心候選排序",
    "table:candidate_rankings:row_count": "核心候選排序",
}
_SIGNAL_LABEL = {
    "options_flow_repeats": "期權流重複",
    "reversal_radar_repeats": "反轉雷達重複",
    "risk_guard_repeats": "風險雷達重複",
    "oversold_reversal_repeats": "蓄勢反轉重複",
}
_DATA_HEALTH_STATUS_PATH = _shared.REPORTS_DIR / "run_status" / "data-health-refresh.json"
_DATA_HEALTH_LOG_PATH = _shared.REPORTS_DIR / "run_status" / "data-health-refresh.log"
_DATA_HEALTH_RUNNING_TTL_SECONDS = 3 * 60 * 60
_AUTO_SYSTEMD_RUN = object()
_RUNTIME_ENV_KEYS = (
    "SURGE_APP_ROOT",
    "SURGE_RUNTIME_DIR",
    "SURGE_ANALYTICS_DIR",
    "SURGE_CANDIDATE_OUTPUT_DIR",
    "CODEX_HOME",
    "PATH",
    "PYTHONPATH",
)


def _fmt_size(path: Path) -> str:
    if not path.is_file():
        return "missing"
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _analytics_root() -> Path:
    return analytics_store.analytics_dir()


def _checks_path() -> Path:
    return _shared.REPORTS_DIR / "analytics_checks" / "latest.json"


def _ranked_tickers(
    result: _read_api.RankedCandidatesApiResult,
    limit: int = 10,
) -> list[str]:
    if limit <= 0 or not isinstance(
        result,
        _read_api.RankedCandidatesApiAvailable,
    ):
        return []
    return [candidate.ticker for candidate in result.feed.candidates[:limit]]


def _parse_tickers(raw: str) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\s,，]+", raw or ""):
        ticker = part.upper().lstrip("$").strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


@st.cache_data(ttl=30, show_spinner=False)
def _catalog(root: str) -> list[dict]:
    return analytics_store.readonly_catalog(root)


@st.cache_data(ttl=30, show_spinner=False)
def _columns(root: str, table: str) -> list[str]:
    return analytics_store.table_columns(table, analytics_root=root)


@st.cache_data(ttl=30, show_spinner=False)
def _tickers(root: str, table: str) -> list[str]:
    return analytics_store.distinct_values(table, "ticker", analytics_root=root, limit=1000)


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_table(
    root: str,
    table: str,
    tickers: tuple[str, ...],
    start_date: str,
    end_date: str,
    order_by: str,
    limit: int,
) -> pd.DataFrame:
    return analytics_store.fetch_table(
        table,
        analytics_root=root,
        tickers=tickers,
        date_column=_DATE_COLUMN.get(table),
        start_date=start_date or None,
        end_date=end_date or None,
        order_by=order_by or None,
        limit=limit,
    )


@st.cache_data(ttl=30, show_spinner=False)
def _run_sql(root: str, sql: str, limit: int) -> pd.DataFrame:
    return analytics_store.run_safe_select(sql, analytics_root=root, limit=limit)


@st.cache_data(ttl=30, show_spinner=False)
def _load_checks(path: str) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _load_data_health_status() -> dict | None:
    try:
        data = json.loads(_DATA_HEALTH_STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return _reconcile_data_health_status(data)


def _parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _data_health_interrupt_reason(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> str | None:
    return run_status_view.running_interrupt_reason(
        data,
        stale_after_seconds=_DATA_HEALTH_RUNNING_TTL_SECONDS,
        stale_message="這次刷新狀態已超過 3 小時未更新，可能已中斷；可重新啟動。",
        pid_gone_message="背景程序已不存在，這次資料刷新已中斷；可重新啟動。",
        now=now,
        process_checker=process_checker,
    )


def _interrupted_data_health_status(
    data: dict,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict:
    return run_status_view.interrupted_status(
        data,
        reason,
        default_label="資料刷新中斷",
        now=now,
    )


def _write_data_health_status(data: dict) -> None:
    _DATA_HEALTH_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DATA_HEALTH_STATUS_PATH.with_name(f"{_DATA_HEALTH_STATUS_PATH.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_DATA_HEALTH_STATUS_PATH)


def _reconcile_data_health_status(data: dict) -> dict:
    reason = _data_health_interrupt_reason(data)
    if not reason:
        return data
    fixed = _interrupted_data_health_status(data, reason)
    try:
        _write_data_health_status(fixed)
    except OSError:
        return fixed
    return fixed


def _data_health_refresh_is_active(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> bool:
    return run_status_view.running_status_is_active(
        data,
        stale_after_seconds=_DATA_HEALTH_RUNNING_TTL_SECONDS,
        stale_message="這次刷新狀態已超過 3 小時未更新，可能已中斷；可重新啟動。",
        pid_gone_message="背景程序已不存在，這次資料刷新已中斷；可重新啟動。",
        now=now,
        process_checker=process_checker,
    )


def _service_managed_runtime() -> bool:
    return bool(
        os.environ.get("INVOCATION_ID")
        or os.environ.get("SYSTEMD_EXEC_PID")
        or os.environ.get("SURGE_FORCE_SYSTEMD_RUN") == "1"
    )


def _runtime_env_args() -> list[str]:
    env = ["PYTHONUNBUFFERED=1"]
    for key in _RUNTIME_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env.append(f"{key}={value}")
    return env


def _build_refresh_launcher(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    platform: str | None = None,
    systemd_run_path: str | None | object = _AUTO_SYSTEMD_RUN,
    unit_name: str | None = None,
) -> tuple[list[str], dict]:
    current_platform = platform or sys.platform
    explicit_systemd_path = systemd_run_path is not _AUTO_SYSTEMD_RUN
    resolved_systemd_path = (
        shutil.which("systemd-run")
        if systemd_run_path is _AUTO_SYSTEMD_RUN
        else systemd_run_path
    )
    use_systemd = (
        current_platform.startswith("linux")
        and bool(resolved_systemd_path)
        and (explicit_systemd_path or _service_managed_runtime())
    )
    if not use_systemd:
        return command, {"launch_mode": "popen"}

    unit = unit_name or f"surge-data-health-refresh-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    unit_display = unit if unit.endswith(".service") else f"{unit}.service"
    script = (
        f"cd {shlex.quote(str(cwd))} || exit; "
        f"exec >>{shlex.quote(str(log_path))} 2>&1; "
        f"exec {shlex.join(command)}"
    )
    launcher = [
        str(resolved_systemd_path),
        "--user",
        f"--unit={unit.removesuffix('.service')}",
        "--collect",
        "/usr/bin/env",
        *_runtime_env_args(),
        "bash",
        "-lc",
        script,
    ]
    return launcher, {"launch_mode": "systemd-run", "unit": unit_display}


def _run_status_zh(value: object) -> str:
    return {
        "running": "執行中",
        "succeeded": "完成",
        "failed": "失敗",
    }.get(str(value or ""), str(value or "-"))


def _run_duration_text(data: dict) -> str:
    started = _parse_utc(data.get("started_at"))
    finished = _parse_utc(data.get("finished_at")) or _parse_utc(data.get("updated_at"))
    if not started or not finished:
        return "-"
    seconds = max(0, int((finished - started).total_seconds()))
    minutes, sec = divmod(seconds, 60)
    if minutes <= 0:
        return f"{sec} 秒"
    return f"{minutes} 分 {sec:02d} 秒"


def _display_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _display_frame(df: pd.DataFrame, cols: list[str], *, bool_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    out = df[cols].copy()
    for col in out.columns:
        if col not in bool_cols:
            out[col] = out[col].map(_display_value)
    return out


def _human_reason(reason: object) -> str:
    text = str(reason or "")
    stale = re.search(r"^([a-z_]+) latest date is stale: ([0-9-]+) \((\d+) days old\)\.", text)
    if stale:
        table, day, days = stale.groups()
        table_name = {
            "candidate_outcomes": "候選 paper validation",
            "candidate_scores": "候選分數",
            "candidate_rankings": "候選排序",
            "daily_reports": "每日報告",
            "performance_ledger": "績效 ledger",
            "market_thesis_forecasts": "大盤研判",
            "portfolio_positions": "持倉快照",
            "risk_guard_rows": "風險雷達",
            "run_status_history": "執行紀錄",
            "sector_rotation_snapshots": "板塊輪動",
            "signal_outcomes": "訊號結果",
            "theme_flow_snapshots": "主題資金流",
            "validation_summaries": "驗證摘要",
            "watchlist_sources": "自選清單來源",
        }.get(table, table)
        if table == "performance_ledger":
            return (
                f"{table_name} 最新日期是 {day}，已 {days} 天未更新；"
                "新資料只會在每日報告有 confirmed/ranked picks 時自動寫入，"
                "7/14/30/60D 報酬到期後再回填。"
            )
        return f"{table_name} 最新日期是 {day}，已 {days} 天未更新。"
    sample = re.search(r"Performance sample has ([0-9,]+) rows.*until ([0-9,]+)\+ rows\.", text)
    if sample:
        current, target = sample.groups()
        return (
            f"績效樣本 {current} 筆，未達 {target} 筆；20 筆前僅做人工檢查，"
            "100 筆 raw rows 只能看初步趨勢，100 筆以上已成熟 30D outcome 才適合討論權重。"
            "60D 樣本成熟前，不對中期策略下強結論。"
        )
    no_picks = re.search(
        r"No confirmed picks across (\d+) successful published scans since ([0-9-]+)\.",
        text,
    )
    if no_picks:
        scans, latest = no_picks.groups()
        if int(scans) >= 10:
            return (
                f"自 {latest} 後已有 {scans} 次成功發布的 scan 沒有 confirmed picks；"
                "TG 需標記 REVIEW_REQUIRED，人工檢查篩選嚴格度、資料新鮮度與市場 regime。"
            )
        return (
            f"自 {latest} 後已有 {scans} 次成功發布的 scan 沒有 confirmed picks；"
            "TG 發 WARN，先觀察，不直接調整 scoring weight。"
        )
    if "required analytics tables failed hard checks" in text:
        return "今日訊號核心資料缺失，暫停發布；請先重新產生候選排序或重建 Analytics DB。"
    if text == "candidate_scores has 0 rows.":
        return "候選分數尚未開始累積；下一次完整 daily scan 成功後會寫入。"
    if text == "candidate_rankings has 0 rows.":
        return "候選排序尚未累積；下一次本機/測試機候選刷新後會寫入。"
    if text == "candidate_outcomes has 0 rows.":
        return (
            "候選 paper validation 尚未累積；這是 Analytics / DB 驗證資料，"
            "不是交易下單功能。no-LLM 候選 outcome 排程成功後會寫入。"
        )
    if text == "signal_outcomes has 0 rows.":
        return "訊號結果尚未有 forward validation 摘要；先維持人工檢查。"
    if text == "run_status_history has 0 rows.":
        return "本機/測試機執行紀錄尚未累積；下一次候選刷新後會寫入。"
    if text == "risk_guard_rows has 0 rows.":
        return "風險雷達尚未累積；下一次風險掃描或排程後會寫入。"
    if text.startswith("portfolio_positions is optional and not configured"):
        return (
            "持倉分析目前未設定；只有需要持倉分析時，才需啟動 IBKR Gateway/TWS "
            "並執行對帳。這不代表零持倉，也不影響訊號發布。"
        )
    if text.startswith("portfolio reconciliation is configured and contains zero position rows"):
        return "持倉對帳來源已設定，本次觀測為零持倉；這不是資料來源缺失。"
    if text == "sector_rotation_snapshots has 0 rows.":
        return "板塊輪動尚未累積；下一次 Sector Rotation 背景刷新後會寫入。"
    if text == "theme_flow_snapshots has 0 rows.":
        return "主題資金流尚未累積；下一次 Theme Flow 背景刷新後會寫入。"
    if text == "validation_summaries has 0 rows.":
        return "驗證摘要尚未累積；下一次 forward validation 或大盤驗證後會寫入。"
    if text == "daily_reports has 0 rows.":
        return "每日報告尚未累積；下一次 daily report 產生後會寫入。"
    if text == "watchlist_sources has 0 rows.":
        return "自選清單來源尚未累積；下一次 IBKR watchlist 或手動清單更新後會寫入。"
    if "Options flow repeated" in text:
        return "期權流重複出現，可加入觀察名單。"
    if "Risk Guard reduce/exit warning repeated" in text:
        return "同一檔連續出現 REDUCE/EXIT 風險警示，先人工確認曝險。"
    return text


def _status(root: Path, catalog: list[dict]) -> None:
    db = analytics_store.duckdb_path(root)
    total_rows = sum(int(r.get("row_count") or 0) for r in catalog)
    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "DB", _fmt_size(db))
    _shared.metric_card(c2, "Tables", str(len(catalog)))
    _shared.metric_card(c3, "Rows", f"{total_rows:,}")
    mtime = "-"
    if db.is_file():
        mtime = pd.to_datetime(db.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M")
    _shared.metric_card(c4, "Updated", mtime)


def _catalog_table(catalog: list[dict]) -> None:
    if not catalog:
        st.info("尚無 analytics tables。")
        return
    df = pd.DataFrame(catalog).rename(columns={
        "table_name": "table",
        "table_type": "type",
        "row_count": "rows",
        "column_count": "columns",
    })
    st.dataframe(df, hide_index=True, width="stretch")


def _health_summary(
    status: str,
    recommended_action: str,
    *,
    today_signal_readiness: dict,
    summary: dict,
    signals: list,
    next_actions: list,
    performance: dict,
    generated_at: str,
) -> tuple[int, int, int]:
    block_count = int(summary.get("block") or 0)
    review_count = sum(1 for item in next_actions if item.get("action") == "REVIEW_REQUIRED")
    if performance.get("status") == "WARN" and review_count == 0:
        review_count = 1
    watch_count = sum(1 for item in signals if item.get("recommended_action") == "WATCHLIST_UPGRADE")
    status_label = _STATUS_LABEL.get(status, status)
    action_label = _ACTION_LABEL.get(recommended_action, recommended_action)
    color = _STATUS_COLOR.get(status, _shared.MUTED)
    readiness = today_signal_readiness if isinstance(today_signal_readiness, dict) else {}
    readiness_status = str(readiness.get("status") or status)
    readiness_label = _READINESS_LABEL.get(readiness_status, readiness_status)
    readiness_action = str(readiness.get("recommended_action") or recommended_action)
    readiness_action_label = _ACTION_LABEL.get(readiness_action, readiness_action)
    readiness_color = _STATUS_COLOR.get(readiness_status, _shared.MUTED)
    can_publish = readiness.get("can_publish")
    readiness_message = str(readiness.get("message") or "")
    if not readiness_message:
        if can_publish is False or readiness_status == "BLOCK":
            readiness_message = "今日訊號核心資料缺失，暫停發布。"
        elif readiness_status == "WARN":
            readiness_message = "今日訊號可發布，但部分增強資料或驗證資料需人工檢查。"
        else:
            readiness_message = "今日訊號可發布。"
    blocking_ids = [
        _READINESS_CHECK_LABEL.get(str(item), str(item))
        for item in readiness.get("blocking_check_ids", [])
    ]
    warning_ids = readiness.get("warning_check_ids", [])

    st.subheader("今日訊號發布狀態")
    with st.container(border=True):
        _shared.chips_row([(readiness_label, readiness_color), (readiness_action_label, _shared.BLUE)])
        st.markdown(f"**{readiness_message}**")
        if blocking_ids:
            st.caption("阻擋來源：" + "、".join(blocking_ids[:4]))
        elif warning_ids:
            st.caption(f"需檢查項目：{len(warning_ids)} 項；不直接暫停今日訊號。")

    st.subheader("今日 Analytics 狀態")
    st.markdown("**資料健康摘要**")
    with st.container(border=True):
        _shared.chips_row([(status_label, color), (action_label, _shared.BLUE)])
        if status == "BLOCK":
            st.markdown("**資料健康有阻擋。** 請看原始檢查；今日訊號是否暫停以上方發布狀態為準。")
        elif status == "WARN":
            st.markdown("**資料可用，但需人工檢查。** DB 可查詢；自動訊號先維持人工檢查。")
        else:
            st.markdown("**資料可用。** 沒有阻擋或需檢查項目。")

        c1, c2, c3, c4 = st.columns(4)
        _shared.metric_card(c1, "阻擋", f"{block_count}")
        _shared.metric_card(c2, "需檢查", f"{review_count}")
        _shared.metric_card(c3, "觀察候選", f"{watch_count}")
        _shared.metric_card(c4, "產生時間", generated_at)
    return block_count, review_count, watch_count


def _action_frame(next_actions: list[dict]) -> pd.DataFrame:
    rows = []
    for item in next_actions:
        action = str(item.get("action") or "NO_ACTION")
        if action == "WATCHLIST_UPGRADE":
            continue
        rows.append({
            "類型": _ACTION_LABEL.get(action, action),
            "內容": _human_reason(item.get("reason")),
            "處理": "人工確認" if item.get("requires_human") else "系統阻擋",
        })
    return pd.DataFrame(rows)


def _signals_frame(signals: list[dict]) -> pd.DataFrame:
    rows = []
    for item in signals:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        notional = evidence.get("total_notional_usd")
        if isinstance(notional, (int, float)):
            notional_text = f"${notional / 1_000_000:,.1f}M"
        else:
            notional_text = ""
        rows.append({
            "Ticker": item.get("ticker") or "",
            "類型": _SIGNAL_LABEL.get(str(item.get("category") or ""), str(item.get("category") or "")),
            "出現天數": evidence.get("days_seen") or "",
            "最高分": evidence.get("max_score") or "",
            "金額": notional_text,
            "最後出現": evidence.get("last_seen") or "",
            "建議": _ACTION_LABEL.get(str(item.get("recommended_action") or ""), item.get("recommended_action") or ""),
        })
    return pd.DataFrame(rows)


def _raw_checks_frame(checks: list[dict]) -> pd.DataFrame:
    check_df = pd.DataFrame(checks)
    if check_df.empty:
        return check_df
    cols = [
        c for c in (
            "status", "id", "table", "message", "recommended_action", "value", "threshold"
        )
        if c in check_df.columns
    ]
    return _display_frame(check_df, cols)


def _clear_cached_reads() -> None:
    try:
        st.cache_data.clear()
    except Exception:  # noqa: BLE001 - cache clearing should not hide refresh results.
        pass


def _launch_core_source_refresh(root: Path) -> dict:
    command = [
        sys.executable,
        str(_shared.DATA_DIR / "scripts" / "data_source_refresh.py"),
        "--reports-dir",
        str(_shared.REPORTS_DIR),
        "--content-dir",
        str(_shared.CONTENT_DIR),
        "--analytics-dir",
        str(root),
        "--checks-output",
        str(_checks_path()),
        "--status-file",
        str(_DATA_HEALTH_STATUS_PATH),
        "--include-supplemental",
        "--supplemental-limit",
        "10",
        "--json",
    ]
    _DATA_HEALTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    launcher, launch_meta = _build_refresh_launcher(
        command,
        cwd=_shared.DATA_DIR,
        log_path=_DATA_HEALTH_LOG_PATH,
    )
    with _DATA_HEALTH_LOG_PATH.open("ab") as log:
        proc = subprocess.Popen(
            launcher,
            cwd=str(_shared.DATA_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return {
        "pid": proc.pid,
        "command": command,
        "launcher": launcher,
        "status_path": str(_DATA_HEALTH_STATUS_PATH),
        "log_path": str(_DATA_HEALTH_LOG_PATH),
        **launch_meta,
    }


def _refresh_analytics_db(root: Path) -> dict:
    from scripts import analytics_checks

    tables = analytics_store.refresh_all(
        reports_root=_shared.REPORTS_DIR,
        analytics_root=root,
    )
    checks = analytics_checks.run_checks(
        analytics_root=root,
        output_path=_checks_path(),
    )
    _clear_cached_reads()
    return {
        "tables": {
            name: meta.get("rows", 0) if isinstance(meta, dict) else 0
            for name, meta in tables.items()
        },
        "checks": {
            "status": checks.get("status"),
            "recommended_action": checks.get("recommended_action"),
            "warning_codes": checks.get("warning_codes", []),
        },
    }


def _refresh_core_sources(root: Path) -> dict:
    from scripts import data_source_refresh

    result = data_source_refresh.refresh_core_sources_and_analytics(
        reports_root=_shared.REPORTS_DIR,
        content_root=_shared.CONTENT_DIR,
        analytics_root=root,
        checks_output=_checks_path(),
        status_file=_DATA_HEALTH_STATUS_PATH,
        include_supplemental=True,
        supplemental_limit=10,
    )
    _clear_cached_reads()
    return result


def _refresh_fundamentals(root: Path, tickers: list[str]) -> dict:
    from scripts import fundamental_metrics_store

    result = fundamental_metrics_store.refresh_fundamental_metrics(
        tickers=tickers,
        reports_dir=_shared.REPORTS_DIR,
    )
    analytics = _refresh_analytics_db(root)
    return {
        "fundamentals": {
            "tickers": tickers,
            "rows": len(result.get("rows", [])) if isinstance(result, dict) else 0,
            "path": result.get("path") if isinstance(result, dict) else None,
        },
        "analytics": analytics,
    }


def _refresh_theme_flow(root: Path) -> dict:
    from scripts import theme_flow
    from scripts import theme_flow_controls

    flow = theme_flow.gather_theme_flow()
    if not flow or not flow.get("themes"):
        raise RuntimeError("theme flow refresh returned no usable themes")
    theme_flow_controls.write_snapshot(flow)
    analytics = _refresh_analytics_db(root)
    return {
        "theme_flow": {
            "as_of": flow.get("as_of"),
            "themes": len(flow.get("themes") or []),
            "snapshot_path": str(theme_flow_controls.SNAPSHOT_PATH),
        },
        "analytics": analytics,
    }


def _refresh_sector_rotation_snapshot(root: Path) -> dict:
    from scripts import sector_rotation

    result = sector_rotation.write_verified_rotation_snapshot()
    if result.get("status") == "no_data":
        raise RuntimeError("sector rotation refresh returned no usable sectors")
    analytics = _refresh_analytics_db(root)
    return {
        "sector_rotation": {
            "status": result.get("status"),
            "as_of": result.get("as_of"),
            "sectors": len(result.get("sectors") or []),
        },
        "analytics": analytics,
    }


def _render_refresh_result() -> None:
    result = st.session_state.get("analytics_db_refresh_result")
    if not isinstance(result, dict):
        return
    if result.get("status") == "error":
        st.error(result.get("message", "資料刷新失敗"))
        return
    st.success(result.get("message", "資料刷新完成"))
    details = result.get("details")
    if isinstance(details, dict):
        with st.expander("刷新結果", expanded=False):
            st.json(details)


@st.fragment(run_every="8s")
def _render_data_health_refresh_status() -> None:
    data = _load_data_health_status()
    st.markdown("##### 最近一次資料刷新")
    st.caption(f"狀態檔：`{_DATA_HEALTH_STATUS_PATH.name}` · log：`{_DATA_HEALTH_LOG_PATH.name}`")
    if not isinstance(data, dict):
        st.info("尚無核心資料源刷新紀錄。")
        return

    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    status = str(data.get("status") or "")
    status_color = {
        "running": _shared.BLUE,
        "succeeded": _shared.GREEN,
        "failed": _shared.RED,
    }.get(status, _shared.MUTED)
    stage_label = str(stage.get("label") or "-")
    stage_message = str(stage.get("message") or "")
    pct = float(stage.get("progress_pct") or 0)  # stage.progress_pct
    active = _data_health_refresh_is_active(data)

    with st.container(border=True):
        _shared.chips_row([(_run_status_zh(status), status_color), (stage_label, _shared.MUTED)])
        if status == "running":
            st.progress(min(max(pct, 0.0), 100.0) / 100, text=f"{stage_label} · {pct:.1f}%")
            if not active:
                st.warning("這次刷新狀態已超過 3 小時未更新，可能已中斷；可以重新啟動。")
        elif status == "succeeded":
            st.progress(1.0, text="完成 · 100%")
        elif status == "failed":
            st.progress(min(max(pct, 0.0), 100.0) / 100, text=f"失敗 · {stage_label}")
        if stage_message:
            st.caption(stage_message)

        c1, c2, c3, c4 = st.columns(4)
        _shared.metric_card(c1, "耗時", _run_duration_text(data))
        _shared.metric_card(c2, "Tickers", str(metrics.get("tickers") or "-"))
        publishable = metrics.get("today_signal_can_publish")
        publish_text = "可發布" if publishable is True else ("暫停" if publishable is False else "-")
        _shared.metric_card(c3, "今日訊號", publish_text)
        _shared.metric_card(
            c4,
            "Warnings / Blockers",
            f"{metrics.get('warnings', '-')}/{metrics.get('blockers', '-')}",
        )

        stages = data.get("stages") if isinstance(data.get("stages"), list) else []
        if stages:
            rows = []
            for item in stages:
                if not isinstance(item, dict):
                    continue
                rows.append({
                    "階段": item.get("label") or item.get("id"),
                    "狀態": _run_status_zh(item.get("status")),
                    "進度": f"{float(item.get('progress_pct') or 0):.1f}%",
                    "訊息": item.get("message") or "",
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=210)


def _render_refresh_center(root: Path) -> None:
    ranked_result = _read_api.load_ranked_candidates()
    default_tickers = ", ".join(_ranked_tickers(ranked_result, limit=10))
    status_data = _load_data_health_status()
    core_refresh_active = _data_health_refresh_is_active(status_data)
    with st.container(border=True):
        st.markdown("##### 資料刷新中心")
        st.caption(
            "測試機會依排程自動刷新核心行情、基本面、板塊、社群、IV、Risk Guard、"
            "Analytics DB 與資料健康檢查；下列按鈕只保留作立即重跑。"
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption(
                "重任務：抓 universe / daily bars / money flow 與其他自動資料，"
                "約 250 檔，完成後重建 Analytics DB。"
            )
            if st.button(
                "完整刷新核心資料源（約 10-25 分鐘）",
                key="analytics_refresh_core_sources",
                use_container_width=True,
                disabled=core_refresh_active,
            ):
                try:
                    details = _launch_core_source_refresh(root)
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "ok",
                        "message": "完整資料刷新已在背景啟動。可在下方查看最近一次資料刷新進度。",
                        "details": details,
                    }
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "error",
                        "message": f"核心 source 刷新失敗：{e}",
                    }
            if core_refresh_active:
                st.caption("目前已有核心資料源刷新執行中，避免重複啟動。")
        with c2:
            st.caption("快任務：只重建 Analytics DB + 檢查，不抓外部資料，通常 10-60 秒。")
            if st.button("只重建 Analytics DB + 檢查", key="analytics_refresh_db", use_container_width=True):
                try:
                    with st.spinner("重建 Analytics DB 並重新產生檢查結果..."):
                        details = _refresh_analytics_db(root)
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "ok",
                        "message": "Analytics DB 與資料健康檢查已更新。",
                        "details": details,
                    }
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "error",
                        "message": f"Analytics DB 刷新失敗：{e}",
                    }
        with c3:
            if not isinstance(
                ranked_result,
                _read_api.RankedCandidatesApiAvailable,
            ):
                st.caption("候選排名預設清單暫時無法使用；仍可手動輸入 ticker。")
            ticker_text = st.text_input(
                "基本面 tickers",
                value=default_tickers,
                key="analytics_fundamental_tickers",
                help="低頻研究資料每日排程會更新前 10 檔；此欄位用於立即補跑指定 ticker。",
            )
            if st.button("刷新基本面", key="analytics_refresh_fundamentals", use_container_width=True):
                tickers = _parse_tickers(ticker_text)
                if not tickers:
                    st.warning("請先輸入至少一個 ticker。")
                else:
                    try:
                        with st.spinner("抓取 SEC/Eastmoney 基本面並更新 Analytics DB..."):
                            details = _refresh_fundamentals(root, tickers)
                        st.session_state["analytics_db_refresh_result"] = {
                            "status": "ok",
                            "message": "基本面與 Analytics DB 已更新。",
                            "details": details,
                        }
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.session_state["analytics_db_refresh_result"] = {
                            "status": "error",
                            "message": f"基本面刷新失敗：{e}",
                        }
        l1, l2, l3 = st.columns(3)
        with l1:
            if st.button("刷新主題資金流", key="analytics_refresh_theme_flow", use_container_width=True):
                try:
                    with st.spinner("刷新 Theme Flow verified snapshot 並更新 Analytics DB..."):
                        details = _refresh_theme_flow(root)
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "ok",
                        "message": "主題資金流快照與 Analytics DB 已更新。",
                        "details": details,
                    }
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "error",
                        "message": f"主題資金流刷新失敗：{e}",
                    }
        with l2:
            if st.button("刷新板塊輪動快照", key="analytics_refresh_sector_rotation", use_container_width=True):
                try:
                    with st.spinner("刷新 Sector Rotation verified snapshot 並更新 Analytics DB..."):
                        details = _refresh_sector_rotation_snapshot(root)
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "ok",
                        "message": "板塊輪動快照與 Analytics DB 已更新。",
                        "details": details,
                    }
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "error",
                        "message": f"板塊輪動刷新失敗：{e}",
                    }
        with l3:
            st.caption("IBKR 持倉需在本機對帳；請到「IBKR 對帳」執行。")
        _render_refresh_result()
        _render_data_health_refresh_status()


def _render_checks(root: Path) -> None:
    path = _checks_path()
    data = _load_checks(str(path))
    if not data:
        st.info("尚無 analytics checks。")
        st.caption(f"`{path}`")
        return

    status = str(data.get("status") or "WARN")
    action = str(data.get("recommended_action") or "REVIEW_REQUIRED")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    checks = data.get("checks") if isinstance(data.get("checks"), list) else []
    signals = data.get("signals") if isinstance(data.get("signals"), list) else []
    next_actions = data.get("next_actions") if isinstance(data.get("next_actions"), list) else []
    generated_at = str(data.get("generated_at") or "-").replace("T", " ")[:16]

    _health_summary(
        status,
        action,
        today_signal_readiness=data.get("today_signal_readiness") if isinstance(data.get("today_signal_readiness"), dict) else {},
        summary=summary,
        signals=signals,
        next_actions=next_actions,
        performance=data.get("performance") if isinstance(data.get("performance"), dict) else {},
        generated_at=generated_at,
    )

    if next_actions:
        action_df = _action_frame(next_actions)
        if not action_df.empty:
            st.markdown("**待處理事項**")
            st.dataframe(action_df, hide_index=True, width="stretch", height=150)
    if signals:
        st.markdown("**觀察候選**")
        st.dataframe(_signals_frame(signals), hide_index=True, width="stretch", height=260)

    with st.expander("連線與原始檢查"):
        c1, c2, c3 = st.columns(3)
        _shared.metric_card(c1, "檢查", f"{summary.get('pass', 0)}P / {summary.get('warn', 0)}W / {summary.get('block', 0)}B")
        _shared.metric_card(c2, "資料日期", str(data.get("as_of_date") or "-"))
        _shared.metric_card(c3, "產生時間", generated_at)
        st.caption(f"DB: `{analytics_store.duckdb_path(root)}`")
        st.caption(f"Checks: `{path}`")
        raw_df = _raw_checks_frame(checks)
        if not raw_df.empty:
            st.dataframe(raw_df, hide_index=True, width="stretch", height=360)
        else:
            st.info("沒有檢查明細。")


def _table_browser(root: str, catalog: object) -> None:
    if not isinstance(catalog, list) or not catalog:
        st.info("找不到可瀏覽的資料表。")
        return

    tables: list[str] = []
    for row in catalog:
        if not isinstance(row, dict):
            st.info("找不到可瀏覽的資料表。")
            return
        table_name = row.get("table_name")
        if not isinstance(table_name, str) or not table_name:
            st.info("找不到可瀏覽的資料表。")
            return
        tables.append(table_name)

    if st.session_state.get("adb_table") not in tables:
        st.session_state["adb_table"] = tables[0]
    table = st.selectbox("資料表", tables, index=None, key="adb_table")
    columns = _columns(root, table)
    date_col = _DATE_COLUMN.get(table)

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        options = _tickers(root, table) if "ticker" in columns else []
        selected = st.multiselect("Ticker", options, default=[], key=f"adb_tickers_{table}")
    with c2:
        start = st.text_input("Start", "", placeholder="YYYY-MM-DD", key=f"adb_start_{table}")
    with c3:
        end = st.text_input("End", "", placeholder="YYYY-MM-DD", key=f"adb_end_{table}")
    with c4:
        limit = st.selectbox("Rows", [100, 500, 1000, 5000], index=1, key=f"adb_limit_{table}")

    order_by = date_col or (columns[0] if columns else "")
    try:
        df = _fetch_table(root, table, tuple(selected), start.strip(), end.strip(), order_by, int(limit))
    except Exception as e:  # noqa: BLE001
        st.error(f"讀取失敗:{e}")
        return

    st.dataframe(df, hide_index=True, width="stretch", height=520)
    if not df.empty:
        st.download_button(
            "下載 CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{table}.csv",
            mime="text/csv",
            width="stretch",
        )


def _iv_chart(root: str) -> None:
    tickers = _tickers(root, "iv_history")
    if not tickers:
        st.info("iv_history 尚無 ticker。")
        return
    default = tickers[: min(3, len(tickers))]
    selected = st.multiselect("Ticker", tickers, default=default, key="adb_iv_chart_tickers")
    if not selected:
        st.info("請選擇 ticker。")
        return
    df = _fetch_table(root, "iv_history", tuple(selected), "", "", "as_of_date", 5000)
    if df.empty:
        st.info("沒有符合條件的 IV 資料。")
        return
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], errors="coerce")
    fig = px.line(
        df.sort_values(["ticker", "as_of_date"]),
        x="as_of_date",
        y="atm_iv",
        color="ticker",
        markers=False,
    )
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e6e9ef"},
    )
    st.plotly_chart(fig, width="stretch")


def _performance(root: str) -> None:
    df = _fetch_table(root, "performance_ledger", tuple(), "", "", "scan_date", 1000)
    if df.empty:
        st.info("performance_ledger 尚無資料。")
        return
    numeric_cols = [
        "composite_score", "fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
        "fwd_30d_return", "fwd_60d_return", "max_drawdown_30d",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    c1, c2, c3 = st.columns(3)
    if "fwd_30d_return" in df.columns:
        _shared.metric_card(c1, "Avg 30D", f"{df['fwd_30d_return'].mean():.1f}%")
    if "hit_15pct_within_30d" in df.columns:
        hit = df["hit_15pct_within_30d"].fillna(False).astype(bool).mean() * 100
        _shared.metric_card(c2, "Hit 15% / 30D", f"{hit:.0f}%")
    _shared.metric_card(c3, "Ledger Rows", f"{len(df):,}")

    cols = [c for c in ("ticker", "scan_date", "verdict", "composite_score",
                       "fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
                       "fwd_30d_return", "max_drawdown_30d") if c in df.columns]
    st.dataframe(df[cols], hide_index=True, width="stretch", height=360)


def _sql_console(root: str) -> None:
    default_sql = "select * from iv_history order by as_of_date desc limit 100"
    sql = st.text_area("SQL", value=default_sql, height=140, key="adb_sql")
    limit = st.selectbox("Max rows", [100, 500, 1000, 5000], index=1, key="adb_sql_limit")
    if not st.button("Run SELECT", width="stretch"):
        return
    try:
        df = _run_sql(root, sql, int(limit))
    except Exception as e:  # noqa: BLE001
        st.error(str(e))
        return
    st.dataframe(df, hide_index=True, width="stretch", height=520)
    if not df.empty:
        st.download_button(
            "下載 SQL 結果",
            df.to_csv(index=False).encode("utf-8"),
            file_name="analytics_query.csv",
            mime="text/csv",
            width="stretch",
        )


def render() -> None:
    st.header("資料健康 / Analytics DB")
    st.caption("排程會自動刷新來源資料、重建 DB 並執行檢查；本頁顯示最新狀態與立即重跑工具。")
    root = _analytics_root()
    root_s = str(root)
    try:
        catalog = _catalog(root_s)
    except Exception as e:  # noqa: BLE001
        st.error(f"Analytics DB 讀取失敗:{e}")
        st.caption(f"`{analytics_store.duckdb_path(root)}`")
        _render_checks(root)
        _render_refresh_center(root)
        return

    _render_checks(root)
    _render_refresh_center(root)
    _status(root, catalog)
    tab_tables, tab_iv, tab_perf, tab_sql = st.tabs(["Tables", "IV History", "Performance", "SQL"])
    with tab_tables:
        _catalog_table(catalog)
        _table_browser(root_s, catalog)
    with tab_iv:
        _iv_chart(root_s)
    with tab_perf:
        _performance(root_s)
    with tab_sql:
        _sql_console(root_s)
