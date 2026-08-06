"""幣圈 · 幣種清單 — strict API-only Binance USDT perpetual universe."""

from __future__ import annotations

from datetime import date

import streamlit as st

from api.models import CryptoUniverseData, UnavailableReason

from . import _components, _read_api


def _safe_reason(
    reason: UnavailableReason | _read_api.ClientFailureReason,
) -> str:
    allowed = (
        _components.ARTIFACT_REASON_CODES
        | _components.CLIENT_FAILURE_REASON_CODES
    )
    return str(reason) if reason in allowed else "read_failure"


def _data_state(
    result: _read_api.CryptoUniverseApiResult,
) -> _components.DataState:
    if isinstance(result, _read_api.CryptoUniverseApiAvailable):
        snapshot = result.snapshot
        return _components.DataState(
            source="authoritative",
            content="populated" if snapshot.universe else "empty",
            freshness="stale" if snapshot.stale else "fresh",
            operation="idle",
            source_id="crypto.universe",
            as_of=date.fromisoformat(snapshot.date),
        )
    return _components.DataState(
        source="unavailable",
        content="unknown",
        freshness="unknown",
        operation="idle",
        source_id="crypto.universe",
        reason_code=_safe_reason(result.reason),
        recovery_key="open-data-health",
    )


def _tradingview_export(snapshot: CryptoUniverseData) -> str:
    rows = [item.tv_symbol for item in snapshot.universe]
    return "\n".join(rows) + ("\n" if rows else "")


def _render_diff(snapshot: CryptoUniverseData) -> None:
    if snapshot.added or snapshot.removed:
        added_column, removed_column = st.columns(2)
        with added_column:
            st.markdown("**➕ 今日新增**")
            for symbol in snapshot.added:
                st.markdown(f"- 🟢 `{symbol}`")
            if not snapshot.added:
                st.caption("無")
        with removed_column:
            st.markdown("**➖ 今日下架**")
            for symbol in snapshot.removed:
                st.markdown(f"- 🔴 `{symbol}`")
            if not snapshot.removed:
                st.caption("無")
    elif snapshot.compared_to:
        st.success(f"與 {snapshot.compared_to} 相同，無增減。")
    else:
        st.info("首次建立清單，尚無比對基準（下一份快照起會顯示增減）。")


def render() -> None:
    st.header("🪙 幣種清單 — 幣安 USDT 永續 (USDT.P)")
    result = _read_api.load_crypto_universe()
    state = _data_state(result)
    if not isinstance(result, _read_api.CryptoUniverseApiAvailable):
        _components.render_state_banner(state)
        return

    snapshot = result.snapshot
    if state.content == "empty" or state.freshness == "stale":
        _components.render_state_banner(state)
    else:
        _components.render_source_meta(state)

    first, second, third = st.columns(3)
    with first:
        st.metric("目前合約數", snapshot.count)
    with second:
        st.metric("➕ 今日新增", len(snapshot.added))
    with third:
        st.metric("➖ 今日下架", len(snapshot.removed))

    compared = snapshot.compared_to or "（無前一份）"
    st.caption(
        f"資料日期：{snapshot.date} · 來源：`{snapshot.source}` · "
        f"狀態：{snapshot.source_status} · 與 {compared} 比對"
    )
    _render_diff(snapshot)

    if not snapshot.universe:
        return

    heading, download = st.columns([5, 1])
    heading.subheader(f"完整清單 ({snapshot.count} 合約)")
    with download:
        st.download_button(
            "⬇️ 匯出 TV",
            _tradingview_export(snapshot),
            file_name="binance_usdtperp_tradingview.txt",
            help="在 TradingView 的 Watchlist → Import list 匯入",
            width="stretch",
        )

    rows = [
        {
            "symbol": item.symbol,
            "base": item.base,
            "onboard_date": item.onboard_date,
        }
        for item in snapshot.universe
    ]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        height=360,
    )
