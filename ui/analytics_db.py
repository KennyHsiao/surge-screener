"""研究驗證 · Analytics DB — read-only DuckDB browser."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts import analytics_store

from . import _shared


_DATE_COLUMN = {
    "iv_history": "as_of_date",
    "market_thesis_forecasts": "as_of_date",
    "options_flow_signals": "as_of_date",
    "oversold_reversal_signals": "as_of_date",
    "performance_ledger": "scan_date",
    "reversal_radar_signals": "as_of_date",
}
_STATUS_COLOR = {
    "PASS": _shared.GREEN,
    "WARN": _shared.AMBER,
    "BLOCK": _shared.RED,
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
    st.caption(f"`{db}`")


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


def _render_checks() -> None:
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
    color = _STATUS_COLOR.get(status, _shared.MUTED)

    _shared.chips_row([(status, color), (action, _shared.BLUE)])
    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "Checks", f"{summary.get('pass', 0)}P / {summary.get('warn', 0)}W / {summary.get('block', 0)}B")
    _shared.metric_card(c2, "Signals", f"{len(signals):,}")
    _shared.metric_card(c3, "Generated", str(data.get("generated_at") or "-").replace("T", " ")[:16])
    _shared.metric_card(c4, "As Of", str(data.get("as_of_date") or "-"))

    if next_actions:
        action_df = pd.DataFrame(next_actions)
        cols = [c for c in ("action", "reason", "requires_human") if c in action_df.columns]
        st.dataframe(_display_frame(action_df, cols, bool_cols=("requires_human",)),
                     hide_index=True, width="stretch", height=180)
    if signals:
        sig_df = pd.DataFrame(signals)
        cols = [c for c in ("category", "ticker", "recommended_action", "message") if c in sig_df.columns]
        st.dataframe(_display_frame(sig_df, cols), hide_index=True, width="stretch", height=220)

    with st.expander("Checks"):
        if checks:
            check_df = pd.DataFrame(checks)
            cols = [
                c for c in (
                    "status", "id", "table", "message", "recommended_action", "value", "threshold"
                )
                if c in check_df.columns
            ]
            st.dataframe(_display_frame(check_df, cols), hide_index=True, width="stretch", height=360)
        else:
            st.info("沒有檢查明細。")
        st.caption(f"`{path}`")


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
        _render_checks()
        return

    _status(root, catalog)
    _render_checks()
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
