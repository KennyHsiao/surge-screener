"""美股 · 機構面板 — institutional views behind one selector.

Combines the two complementary institutional pages into one nav entry:
  • 機構持股 — 股票 → 誰持有它 (institutional_holdings, yfinance)
  • 機構持倉 — 機構 → 它持有什麼 (institution_portfolio, SEC EDGAR 13F)

NOTE on st.tabs vs segmented_control: st.tabs runs *every* tab body on each
rerun (the inactive tab is only hidden client-side), so hosting both pages in
tabs would eagerly fetch BOTH data sources — including the slow / rate-limited
SEC EDGAR 13F — on every visit, even when the user only wants the stock view.
A single-select segmented control renders ONLY the chosen view, so just that
view's data source is fetched. It reads like a tab/pill row; defaults still
auto-load within the active view.
"""

import streamlit as st

from . import institution_portfolio, institutional_holdings

_VIEWS = {
    "機構持股 · 股票 → 誰持有它": institutional_holdings.render,
    "機構持倉 · 機構 → 它持有什麼": institution_portfolio.render,
}


def render() -> None:
    st.header("🏢 機構面板")
    labels = list(_VIEWS)
    # single-select; guard the de-select (None) case → fall back to first view.
    choice = st.segmented_control(
        "檢視", labels, default=labels[0],
        label_visibility="collapsed", key="inst_view",
    )
    _VIEWS[choice or labels[0]](embedded=True)
