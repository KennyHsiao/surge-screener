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
    _shared,
    analyst_views,
    crypto_screener,
    crypto_universe,
    ibkr_reconcile,
    influencers,
    knowledge_graph,
    institutions,
    market_thesis,
    options_cockpit,
    options_flow,
    radar,
    retro_analysis,
    risk_guard,
    sector_rotation,
    stock_checkup,
    sys_ai_updates,
    sys_schedules,
    theme_flow,
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


# Global metric polish: Streamlit's default st.metric value is 2.25rem and is set
# to nowrap+ellipsis, so in dense multi-column panels (期權作戰台 etc.) numbers
# clip to "0..." / "$32...". Shrink the value and let value+label wrap so nothing
# truncates. Applies app-wide (one source of truth for the metric look).
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        line-height: 1.25;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    [data-testid="stMetricValue"] > div { overflow: visible; }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] p {
        white-space: normal;
        overflow-wrap: anywhere;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


nav = {
    "美股": [
        st.Page(us_screener.render, title="暴漲股篩選器", icon="🌡",
                default=True, url_path="us-screener"),
        st.Page(options_cockpit.render, title="期權作戰台", icon="🎯",
                url_path="options-cockpit"),
        st.Page(radar.render, title="雷達 (風險＋反轉)", icon="📡",
                url_path="radar"),
        st.Page(stock_checkup.render, title="個股總覽", icon="🔍",
                url_path="stock-checkup"),
        st.Page(us_options.render, title="期權分析", icon="🧮",
                url_path="us-options"),
        st.Page(options_flow.render, title="選擇權異常流", icon="🚨",
                url_path="options-flow"),
        st.Page(analyst_views.render, title="分析師評級", icon="🎲",
                url_path="analyst-views"),
        st.Page(institutions.render, title="機構面板", icon="🏢",
                url_path="institutions"),
        st.Page(sector_rotation.render, title="熱錢板塊輪動", icon="🔄",
                url_path="sector-rotation"),
        st.Page(theme_flow.render, title="主題資金流", icon="💧",
                url_path="theme-flow"),
        st.Page(retro_analysis.render, title="復盤分析", icon="🔁",
                url_path="retro-analysis"),
        st.Page(knowledge_graph.render, title="知識網路", icon="🔗",
                url_path="knowledge-graph"),
        # 壓縮基底(⚡蓄勢)獨立頁已退役 → 併入「雷達」第三 tab(ui/radar.py);
        # 後端 scripts/oversold_reversal_*.py + cron + forward 驗證完全不動。
        st.Page(ibkr_reconcile.render, title="IBKR 對帳", icon="🧾",
                url_path="ibkr-reconcile"),
        st.Page(watchlist_categorize.render, title="自選股分類", icon="🗂",
                url_path="watchlist-categorize"),
        st.Page(us_cot.render, title="COT / ES 週報", icon="📑",
                url_path="us-cot"),
        st.Page(market_thesis.render, title="大盤行情研判", icon="🧭",
                url_path="market-thesis"),
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
}

# One-click cross-page jumps (🔍/🎯 buttons) st.switch_page() via this registry;
# markdown links can't do it (target=_blank → new tab → new session).
_shared.PAGE_REGISTRY.update(
    {p.url_path: p for pages in nav.values() for p in pages})

pg = st.navigation(nav)
pg.run()

st.sidebar.markdown("---")
st.sidebar.caption("僅供訊號生成,非投資建議。Quant Radar — DEoT 多層分析")
