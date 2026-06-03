"""美股 · 機構面板 — institutional views in two tabs.

Combines the two complementary institutional pages into one nav entry:
  • 機構持股 — 股票 → 誰持有它 (institutional_holdings, yfinance)
  • 機構持倉 — 機構 → 它持有什麼 (institution_portfolio, SEC EDGAR 13F)
Each tab embeds the existing page body (header suppressed via embedded=True).
"""

import streamlit as st

from . import institution_portfolio, institutional_holdings


def render() -> None:
    st.header("🏢 機構面板")
    tab_h, tab_p = st.tabs(["機構持股 · 股票 → 誰持有它", "機構持倉 · 機構 → 它持有什麼"])
    with tab_h:
        institutional_holdings.render(embedded=True)
    with tab_p:
        institution_portfolio.render(embedded=True)
