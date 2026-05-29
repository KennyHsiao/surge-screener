"""X 社群情緒/博主分析 — shared page, used by both 美股 and 幣圈.

render(market) parameterizes only the labels and preset suggestions; the fetch
+ analyze logic is identical. Backend lives in scripts/x_analysis.py.
"""

import sys
from pathlib import Path

import streamlit as st

from . import influencers as influencers_mod

# Make repo-root `scripts` importable when run via `streamlit run app.py`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_PRESETS = {
    "US": {
        "label": "美股",
        "handles": ["DeItaone", "unusual_whales", "Stocktwits"],
        "keyword": "$NVDA",
    },
    "CRYPTO": {
        "label": "幣圈",
        "handles": ["WatcherGuru", "CryptoHayes", "documentingbtc"],
        "keyword": "$BTC",
    },
}


def render(market: str = "US") -> None:
    cfg = _PRESETS.get(market, _PRESETS["US"])
    st.header(f"🐦 X 社群情緒 — {cfg['label']}")

    from scripts import x_analysis  # lazy so the page loads even if import fails

    status = x_analysis.get_status()
    # Don't hide the UI when the token is missing — let users browse/select the
    # curated roster; only the fetch action below is gated on the token.
    if not status["x_token"]:
        st.warning("尚未設定 `X_BEARER_TOKEN`:可瀏覽/選擇下方清單,但**抓取與分析**需設定後才能使用。")
    elif not status["anthropic"]:
        st.info("未設定 `ANTHROPIC_API_KEY`:可抓貼文,但不會做 LLM 情緒分析。")

    mode = st.radio("分析模式", ["博主帳號", "關鍵字/代號"], horizontal=True)
    limit = st.slider("抓取貼文數", 5, 50, 20, step=5)

    if mode == "博主帳號":
        roster = influencers_mod.for_market(market)
        if roster:
            labels = [f"{i.get('category', '?')} · @{i['handle']}"
                      + (f" — {i['name']}" if i.get('name') else "")
                      for i in roster] + ["➕ 自訂輸入"]
            pick = st.selectbox("選擇博主(來自關注清單)", labels)
            if pick == "➕ 自訂輸入":
                handle = st.text_input("X 帳號(不含 @)", value="").strip()
            else:
                handle = roster[labels.index(pick)]["handle"]
        else:
            handle = st.text_input(
                "X 帳號(不含 @)", value=cfg["handles"][0],
                help=f"建議:{', '.join('@' + h for h in cfg['handles'])}",
            ).strip()
        target, context = handle, f"@{handle}"
    else:
        kw = st.text_input("關鍵字 / 代號", value=cfg["keyword"])
        target, context = kw, kw

    run = st.button("分析", type="primary", disabled=not status["x_token"])
    if not status["x_token"]:
        st.caption("⚠️ 需設定 `X_BEARER_TOKEN` 才能抓取分析;以上選單可先瀏覽。")
    if not run:
        return

    try:
        with st.spinner("抓取貼文中…"):
            if mode == "博主帳號":
                posts = x_analysis.fetch_user_posts(target, limit=limit)
            else:
                posts = x_analysis.fetch_keyword_posts(target, limit=limit)
    except x_analysis.XApiError as e:
        st.error(str(e))
        return

    if not posts:
        st.info("沒有抓到貼文。")
        return

    with st.spinner("分析情緒中…"):
        result = x_analysis.analyze(posts, context=context)

    if result.get("llm"):
        sentiment = result.get("overall_sentiment", "?")
        score = result.get("sentiment_score", 0.0)
        icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(sentiment, "⚪")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("整體情緒", f"{icon} {sentiment}", delta=f"{score:+.2f}")
        with c2:
            if result.get("summary"):
                st.markdown(f"**重點:** {result['summary']}")

        themes = result.get("key_themes", [])
        if themes:
            st.markdown("**主題:** " + " ".join(f"`{t}`" for t in themes))

        if result.get("stance"):
            st.info(f"📌 該帳號近期傾向:{result['stance']}")

        highlights = result.get("highlights", [])
        if highlights:
            st.markdown("**代表貼文**")
            for h in highlights:
                st.markdown(f"- 「{h.get('text', '')}」 — *{h.get('why', '')}*")
    else:
        st.caption(result.get("note", ""))
        if result.get("raw"):
            st.code(result["raw"])

    with st.expander(f"原始貼文 ({len(posts)})"):
        for p in posts:
            meta = f"{p.get('created_at', '')} · ♥{p.get('likes', 0)} ↻{p.get('retweets', 0)}"
            st.markdown(f"**{p.get('author', '')}** · {meta}\n\n{p.get('text', '')}")
            st.markdown("---")
