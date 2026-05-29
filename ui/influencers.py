"""關注博主清單 — 依功能分類的 X 博主名單.

Cross-market reference list read from content/influencers.json. The same file
feeds the quick-pick selector on the X 社群情緒 pages, so the directory and the
analyzer never drift apart. Edit the JSON to add/remove influencers.
"""

import streamlit as st

from . import _shared


def load_influencers() -> tuple[list[dict], list[str]]:
    data = _shared.load_json(str(_shared.CONTENT_DIR / "influencers.json")) or {}
    return data.get("influencers", []), data.get("categories_order", [])


def for_market(market: str) -> list[dict]:
    """Real influencers for a market (US/CRYPTO), grouped order preserved.

    Placeholder/template rows are excluded — this feeds the live X analyzer, so
    a fake handle must never become selectable there.
    """
    influencers, order = load_influencers()
    members = [i for i in influencers
               if i.get("market") == market and not i.get("placeholder")]
    rank = {c: n for n, c in enumerate(order)}
    members.sort(key=lambda i: (rank.get(i.get("category", ""), 999),
                                i.get("category", ""), i.get("handle", "")))
    return members


def render() -> None:
    st.header("👥 關注博主清單")
    st.caption("依功能分類的 X 博主名單(`content/influencers.json`,手動維護)。"
               "「X 社群情緒」頁的快速選單會從這份清單帶入。")

    influencers, order = load_influencers()
    if not influencers:
        st.info("尚無博主。請編輯 `content/influencers.json`。")
        return

    markets = ["全部"] + sorted({i.get("market", "US") for i in influencers})
    mk = st.radio("市場", markets, horizontal=True)
    items = [i for i in influencers if mk == "全部" or i.get("market") == mk]

    # category order: explicit order first, then any extras alphabetically
    cats = list(dict.fromkeys(order + sorted({i.get("category", "未分類") for i in items})))

    shown = 0
    for cat in cats:
        members = [i for i in items if i.get("category", "未分類") == cat]
        if not members:
            continue
        real = [m for m in members if not m.get("placeholder")]
        st.subheader(f"📂 {cat}  ({len(real)})")
        cols = st.columns(2)
        for n, inf in enumerate(members):
            with cols[n % 2].container(border=True):
                if inf.get("placeholder"):
                    st.markdown(f"🧩 *{inf.get('name', '(模板)')}*")
                    if inf.get("note"):
                        st.caption(inf["note"])
                    continue
                shown += 1
                handle = inf.get("handle", "")
                url = inf.get("url") or f"https://x.com/{handle}"
                st.markdown(f"**{inf.get('name', handle)}**  ·  `{inf.get('market', '')}`")
                st.markdown(f"[@{handle}]({url})")
                if inf.get("note"):
                    st.caption(inf["note"])

    if shown == 0:
        st.info("此市場底下尚無(非模板)博主。")
