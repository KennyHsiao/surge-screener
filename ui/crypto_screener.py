"""幣圈 · 篩選 — scaffold placeholder.

Mirrors the US screener's information architecture so that, when a crypto
pipeline is wired up (writing crypto_scored.json in the same shape as
scored_candidates.json), this page can render it the same way. Until then it
shows the intended structure and the planned data sources.
"""

import streamlit as st

from . import _shared

# When a crypto pipeline lands, it should write this in the US screener's shape.
_CRYPTO_SCORED = "crypto_scored.json"


def render() -> None:
    st.header("🔍 幣圈篩選")

    data = _shared.load_json(str(_shared.DATA_DIR / _CRYPTO_SCORED))
    if data:
        st.success("偵測到幣圈管線輸出。(渲染邏輯待管線格式確定後接上 us_screener 共用元件。)")
        st.json(data, expanded=False)
        return

    st.info(
        "幣圈資料管線**尚未接上**。版面骨架已比照美股篩選器預留,"
        f"之後管線輸出 `{_CRYPTO_SCORED}`(沿用美股 scored 結構)即可填入。"
    )

    st.markdown("#### 規劃中的版面(鏡像美股)")
    for label, desc in [
        ("🌡 大盤環境", "BTC 主導率、Fear & Greed 指數、總市值趨勢、資金費率"),
        ("🔽 篩選管線", "硬篩(流動性/市值/已漲多)→ 多維度評分漏斗"),
        ("📊 候選幣", "技術 / 鏈上 / 社群情緒 / 資金流 維度雷達"),
        ("🔍 盡調", "鏈上數據、巨鯨動向、合約安全、敘事驗證"),
        ("📈 績效", "選幣前瞻報酬追蹤(沿用 ledger 機制)"),
    ]:
        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(desc)

    st.markdown("#### 規劃中的資料源")
    st.markdown(
        "- 價量 / 市值:CoinGecko、Binance API\n"
        "- 鏈上:Glassnode、Dune、Nansen\n"
        "- 情緒:X 社群情緒頁(已可用)、Fear & Greed\n"
        "- 衍生品:資金費率、未平倉、清算地圖"
    )
