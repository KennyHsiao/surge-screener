"""研究驗證 · Analytics DB — read-only DuckDB browser."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts import analytics_store

from . import _shared


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
    "BLOCK": "今日訊號暫停使用",
}
_SIGNAL_LABEL = {
    "options_flow_repeats": "期權流重複",
    "reversal_radar_repeats": "反轉雷達重複",
    "risk_guard_repeats": "風險雷達重複",
    "oversold_reversal_repeats": "蓄勢反轉重複",
}


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
            "candidate_outcomes": "候選驗證結果",
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
        return f"績效樣本 {current} 筆，未達 {target} 筆；20 筆前僅做人工檢查，100 筆以上才適合檢討權重。"
    if "required analytics tables failed hard checks" in text:
        return "必要資料表有阻擋項目，今日訊號先暫停使用。"
    if text == "candidate_scores has 0 rows.":
        return "候選分數尚未開始累積；下一次完整 daily scan 成功後會寫入。"
    if text == "candidate_rankings has 0 rows.":
        return "候選排序尚未累積；下一次本機/測試機候選刷新後會寫入。"
    if text == "candidate_outcomes has 0 rows.":
        return "候選驗證結果尚未累積；no-LLM 候選 outcome 排程成功後會寫入。"
    if text == "signal_outcomes has 0 rows.":
        return "訊號結果尚未有 forward validation 摘要；先維持人工檢查。"
    if text == "run_status_history has 0 rows.":
        return "本機/測試機執行紀錄尚未累積；下一次候選刷新後會寫入。"
    if text == "risk_guard_rows has 0 rows.":
        return "風險雷達尚未累積；下一次風險掃描或排程後會寫入。"
    if text.startswith("portfolio_positions has 0 rows."):
        return "持倉快照尚未累積；請先啟動 IB Gateway/TWS 並啟用 API，再執行 IBKR 對帳。"
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

    st.subheader("今日 Analytics 狀態")
    with st.container(border=True):
        _shared.chips_row([(status_label, color), (action_label, _shared.BLUE)])
        if status == "BLOCK":
            st.markdown("**今日資料不可直接使用。** 請先處理阻擋項目，再回到訊號頁。")
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


def _table_browser(root: str, catalog: list[dict]) -> None:
    tables = [r["table_name"] for r in catalog]
    if not tables:
        st.info("找不到可瀏覽的資料表。")
        return
    table = st.segmented_control("資料表", tables, default=tables[0], key="adb_table")
    table = str(table or tables[0])
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
    st.header("📊 Analytics DB")
    root = _analytics_root()
    root_s = str(root)
    try:
        catalog = _catalog(root_s)
    except Exception as e:  # noqa: BLE001
        st.error(f"Analytics DB 讀取失敗:{e}")
        st.caption(f"`{analytics_store.duckdb_path(root)}`")
        _render_checks(root)
        return

    _render_checks(root)
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
