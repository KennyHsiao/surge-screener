"""美股 · 機構面板 — institutional views behind one selector.

Combines the two complementary institutional pages into one nav entry:
  • 機構持股 — 股票 → 誰持有它 (institutional_holdings, yfinance)
  • 機構持倉 — 機構 → 它持有什麼 (institution_portfolio, SEC EDGAR 13F)

NOTE on st.tabs vs a required-choice radio: st.tabs runs *every* tab body on each
rerun (the inactive tab is only hidden client-side), so hosting both pages in
tabs would eagerly fetch BOTH data sources — including the slow / rate-limited
SEC EDGAR 13F — on every visit, even when the user only wants the stock view.
A required-choice horizontal radio renders ONLY the chosen view, so just that
view's data source is fetched. The first choice is normalized before rendering,
so the active view still auto-loads.
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
    if st.session_state.get("inst_view") not in labels:
        st.session_state["inst_view"] = labels[0]
    choice = st.radio(
        "檢視", labels, index=None,
        label_visibility="collapsed", key="inst_view", horizontal=True,
    )
    _VIEWS[choice or labels[0]](embedded=True)
