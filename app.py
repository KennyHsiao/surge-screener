#!/usr/bin/env python3
"""Quant Radar — multi-page Streamlit entry.

Sidebar navigation grouped into 美股 / 幣圈 / 系統. Each page is a render()
function in the ui/ package. Pipeline data-loading helpers live in ui/_shared.
"""

import streamlit as st

st.set_page_config(
    page_title="Quant Radar",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui import (  # noqa: E402  (must follow set_page_config)
    analyst_views,
    crypto_screener,
    crypto_universe,
    ibkr_reconcile,
    influencers,
    institution_portfolio,
    institutional_holdings,
    options_cockpit,
    retro_analysis,
    sector_rotation,
    sys_ai_updates,
    sys_schedules,
    us_cot,
    us_options,
    us_screener,
    watchlist_categorize,
    x_sentiment,
)


# Thin wrappers give the shared X page a distinct identity per market.
def us_x() -> None:
    x_sentiment.render("US")


def crypto_x() -> None:
    x_sentiment.render("CRYPTO")


pg = st.navigation({
    "美股": [
        st.Page(us_screener.render, title="暴漲股篩選器", icon="🌡",
                default=True, url_path="us-screener"),
        st.Page(options_cockpit.render, title="期權作戰台", icon="🎯",
                url_path="options-cockpit"),
        st.Page(us_options.render, title="期權分析", icon="🧮",
                url_path="us-options"),
        st.Page(analyst_views.render, title="分析師評級", icon="🎲",
                url_path="analyst-views"),
        st.Page(institutional_holdings.render, title="機構持股", icon="🏢",
                url_path="institutional-holdings"),
        st.Page(institution_portfolio.render, title="機構持倉", icon="🏦",
                url_path="institution-portfolio"),
        st.Page(sector_rotation.render, title="熱錢板塊輪動", icon="🔄",
                url_path="sector-rotation"),
        st.Page(retro_analysis.render, title="復盤分析", icon="🔁",
                url_path="retro-analysis"),
        st.Page(ibkr_reconcile.render, title="IBKR 對帳", icon="🧾",
                url_path="ibkr-reconcile"),
        st.Page(watchlist_categorize.render, title="自選股分類", icon="🗂",
                url_path="watchlist-categorize"),
        st.Page(us_cot.render, title="COT / ES 週報", icon="📑",
                url_path="us-cot"),
        st.Page(us_x, title="X 社群情緒", icon="🐦", url_path="us-x"),
    ],
    "幣圈": [
        st.Page(crypto_universe.render, title="幣種清單", icon="🪙",
                url_path="crypto-universe"),
        st.Page(crypto_screener.render, title="幣圈篩選", icon="🔍",
                url_path="crypto-screener"),
        st.Page(crypto_x, title="X 社群情緒", icon="🐦", url_path="crypto-x"),
    ],
    "系統": [
        st.Page(influencers.render, title="關注博主", icon="👥",
                url_path="influencers"),
        st.Page(sys_schedules.render, title="排程與結果", icon="⏱",
                url_path="schedules"),
        st.Page(sys_ai_updates.render, title="AI 重點更新", icon="🤖",
                url_path="ai-updates"),
    ],
})

pg.run()

st.sidebar.markdown("---")
st.sidebar.caption("僅供訊號生成,非投資建議。Quant Radar — DEoT 多層分析")
