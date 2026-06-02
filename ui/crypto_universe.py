"""幣圈 · 幣種清單 — 幣安 USDT 永續 (USDT.P) 名單與每日增減.

Reads reports/crypto/universe_latest.json produced by scripts/crypto_universe.py.
The user's actual need: see on the platform which coins were added/removed —
so the diff is front and center. A TradingView-importable file is offered too.
"""

import pandas as pd
import streamlit as st

from . import _shared

_LATEST = _shared.REPORTS_DIR / "crypto" / "universe_latest.json"
_TV_FILE = _shared.REPORTS_DIR / "crypto" / "tradingview_watchlist.txt"


def render() -> None:
    st.header("🪙 幣種清單 — 幣安 USDT 永續 (USDT.P)")

    data = _shared.load_json(str(_LATEST))
    if not data:
        st.info("尚無幣種清單。請先執行 `python scripts/crypto_universe.py`。")
        return

    cmp = data.get("compared_to")
    added, removed = data.get("added", []), data.get("removed", [])
    data_date = data.get("date", "?")

    c1, c2, c3 = st.columns(3)
    _shared.metric_card(c1, "目前合約數", data.get("count", 0))
    _shared.metric_card(
        c2, "➕ 今日新增", len(added),
        delta=str(len(added)) if added else None,
        delta_color="normal",
    )
    _shared.metric_card(
        c3, "➖ 今日下架", len(removed),
        delta=str(len(removed)) if removed else None,
        delta_color="inverse",
    )
    st.caption(
        f"資料日期：{data_date} · 來源：`{data.get('source')}` · 與 {cmp or '(無前一份)'} 比對"
    )

    if added or removed:
        col_a, col_r = st.columns(2)
        with col_a:
            st.markdown("**➕ 今日新增**")
            for s in added:
                st.markdown(f"- 🟢 `{s}`")
            if not added:
                st.caption("無")
        with col_r:
            st.markdown("**➖ 今日下架**")
            for s in removed:
                st.markdown(f"- 🔴 `{s}`")
            if not removed:
                st.caption("無")
    elif cmp:
        st.success(f"與 {cmp} 相同,無增減。")
    else:
        st.info("首次建立清單,尚無比對基準(明天起會顯示增減)。")

    if _TV_FILE.exists():
        st.download_button(
            "⬇️ 匯出 TradingView 清單 (.txt)",
            _TV_FILE.read_text(encoding="utf-8"),
            file_name="binance_usdtperp_tradingview.txt",
            help="在 TradingView 的 Watchlist → Import list 匯入",
        )

    universe = data.get("universe", [])
    if universe:
        st.subheader(f"完整清單 ({len(universe)} 合約)")
        st.dataframe(pd.DataFrame(universe), hide_index=True,
                     use_container_width=True)
