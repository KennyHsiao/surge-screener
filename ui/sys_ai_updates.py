"""系統 · AI Agent 重點更新.

Reads content/ai_updates.json — a manually maintained feed. Each entry:
{date, title, summary, link, tags}. Rendered newest-first as cards, each with
an optional "深化連結".
"""

import streamlit as st

from . import _shared


def _load_updates() -> list[dict]:
    data = _shared.load_json(str(_shared.CONTENT_DIR / "ai_updates.json"))
    if not data:
        return []
    updates = data.get("updates", [])
    return sorted(updates, key=lambda u: u.get("date", ""), reverse=True)


def render() -> None:
    st.header("🤖 AI Agent 重點更新")
    st.caption("手動維護的更新摘要 feed(`content/ai_updates.json`)。要深化的項目附上連結。")

    updates = _load_updates()
    if not updates:
        st.info("找不到 `content/ai_updates.json`,或內容為空。")
        return

    all_tags = sorted({t for u in updates for t in u.get("tags", [])})
    if all_tags:
        picked = st.multiselect("依標籤篩選", all_tags, default=[])
    else:
        picked = []

    shown = 0
    for u in updates:
        tags = u.get("tags", [])
        if picked and not set(picked) & set(tags):
            continue
        shown += 1
        with st.container(border=True):
            col_title, col_date = st.columns([4, 1])
            with col_title:
                st.markdown(f"**{u.get('title', '(無標題)')}**")
            with col_date:
                st.markdown(
                    f"<div style='text-align:right;color:{_shared.MUTED};"
                    f"font-size:0.82rem'>{u.get('date', '')}</div>",
                    unsafe_allow_html=True,
                )
            if u.get("summary"):
                st.markdown(u["summary"])
            if tags:
                _shared.chips_row([(t, _shared.MUTED) for t in tags])
            link = u.get("link")
            if link:
                st.markdown(f"🔗 [深化連結]({link})")

    if shown == 0:
        st.info("沒有符合所選標籤的更新。")
