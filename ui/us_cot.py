"""美股 · COT / ES 週報.

Renders the weekly report produced by scripts/cot_es.py
(reports/cot/YYYY-MM-DD.md). The .json sibling holds the verified data the
report was built from, shown as an audit panel.
"""

import streamlit as st

from . import _shared

_COT_DIR = _shared.REPORTS_DIR / "cot"


def render() -> None:
    st.header("📑 COT / ES 週報")
    st.caption("資料由系統抓取(CFTC 官方 + yfinance ES=F),AI 只做分析,不自行查價。")

    if not _COT_DIR.exists():
        st.info("尚無 COT 週報。請先執行 `python scripts/cot_es.py`。")
        return

    reports = sorted((p for p in _COT_DIR.glob("*.md")), reverse=True)
    if not reports:
        st.info("尚無 COT 週報(目錄存在但無 .md)。")
        return

    names = [p.stem for p in reports]
    chosen = st.selectbox("報告(週五日期)", names)
    md_path = _COT_DIR / f"{chosen}.md"

    # Audit panel: the verified data the report was built from.
    verified = _shared.load_json(str(_COT_DIR / f"{chosen}.verified.json"))
    if verified:
        price = verified.get("price", {})
        cot = verified.get("cot", {})
        if price.get("cot_stale_warning"):
            st.warning(
                f"⚠️ COT 報告偏舊({price.get('cot_report_age_days', '?')} 天前的 as-of),"
                "可能逢假期延後發布,解讀請留意時效。"
            )
        # Headline verified numbers, always visible — they're the point of the
        # report, so don't bury them in a collapsed expander above a wall of text.
        tvf = verified.get("tuesday_vs_friday", {})
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.container(border=True):
                st.metric("ES 週五收盤", price.get("friday_close", "?"),
                          help=f"{price.get('symbol','')} · {price.get('source','')}")
        with c2:
            with st.container(border=True):
                st.metric("COT as-of(週二)", cot.get("as_of", "?"))
        with c3:
            with st.container(border=True):
                st.metric("週二→週五", f"{tvf.get('delta_points', '?')} 點")
        with st.expander("🔍 已驗證資料明細(報告的數據來源 JSON)", expanded=False):
            st.caption(f"價格取得時間:{price.get('retrieved_at', '?')}")
            st.json(verified, expanded=False)

    st.markdown("---")
    st.markdown(md_path.read_text(encoding="utf-8"))
