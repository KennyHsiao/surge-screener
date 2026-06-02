"""美股 · COT / ES 週報.

Renders the weekly report produced by scripts/cot_es.py
(reports/cot/YYYY-MM-DD.md). The .json sibling holds the verified data the
report was built from, shown as an audit panel.
"""

import re

import streamlit as st

from . import _shared

_COT_DIR = _shared.REPORTS_DIR / "cot"

# Section header patterns that delimit the four logical sections of the report.
# Each pattern matches the markdown H2 that starts the section.
_SECTION_RE = re.compile(
    r"(?=^## Section [1-4])", re.MULTILINE
)


def _split_sections(md: str) -> dict[str, str]:
    """Split report markdown into named section blobs.

    Strips the leading H1 (the page already has its own header) and returns a
    dict keyed by tab label. Falls back to the full body under '全文' if the
    four-section pattern is not found.
    """
    # Strip the first H1 line (e.g. "# 📑 E-MINI S&P 500 …\n")
    body = re.sub(r"^#[^\n]+\n", "", md, count=1)

    parts = _SECTION_RE.split(body)
    # parts[0] is the preamble (date/price block before Section 1)
    preamble = parts[0].strip()
    section_blobs = parts[1:]  # each starts with "## Section N …"

    if len(section_blobs) < 4:
        # Report doesn't match expected structure — render as single block
        return {"全文": body}

    labels = ["籌碼結構", "機構博弈", "交易策略", "風險提示"]
    result = {}
    if preamble:
        result["__preamble__"] = preamble
    for label, blob in zip(labels, section_blobs):
        # Remove the "## Section N — XYZ\n" heading line since the tab label
        # already communicates the section name.
        blob_body = re.sub(r"^##[^\n]+\n", "", blob, count=1).strip()
        result[label] = blob_body
    return result


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

    # ── Audit panel: verified numbers the report was built from ────────────
    verified = _shared.load_json(str(_COT_DIR / f"{chosen}.verified.json"))
    if verified:
        price = verified.get("price", {}) or {}
        cot = verified.get("cot", {}) or {}
        tvf = verified.get("tuesday_vs_friday", {}) or {}

        if price.get("cot_stale_warning"):
            st.warning(
                f"⚠️ COT 報告偏舊({price.get('cot_report_age_days', '?')} 天前的 as-of),"
                "可能逢假期延後發布,解讀請留意時效。"
            )

        # Headline verified numbers — always visible, never buried.
        c1, c2, c3 = st.columns(3)

        # delta_points: numeric or string; convert to int/float for st.metric
        raw_delta = tvf.get("delta_points")
        try:
            delta_val = float(raw_delta) if raw_delta is not None else None
            delta_str = f"{delta_val:+.0f} 點" if delta_val is not None else None
            # delta_color='normal' → green when positive, red when negative
            delta_color = "normal"
        except (TypeError, ValueError):
            delta_str = str(raw_delta) if raw_delta is not None else None
            delta_color = "off"

        _shared.metric_card(
            c1, "ES 週五收盤", price.get("friday_close", "?"),
            help=f"{price.get('symbol','')} · {price.get('source','')}",
        )
        _shared.metric_card(
            c2, "COT as-of(週二)", cot.get("as_of", "?"),
        )
        # 週二→週五 point change: coloured metric so gain/loss is immediately legible
        fri_close = tvf.get("friday_close") or price.get("friday_close", "?")
        with c3:
            with st.container(border=True):
                st.metric(
                    "週二→週五 收盤",
                    fri_close,
                    delta=delta_str,
                    delta_color=delta_color,
                    help="週五收盤 − 週二(COT as-of)收盤;綠色 = 期間上漲,紅色 = 下跌",
                )

        with st.expander("🔍 已驗證資料明細(報告的數據來源 JSON)", expanded=False):
            st.caption(f"價格取得時間:{price.get('retrieved_at', '?')}")
            st.json(verified, expanded=False)

    st.markdown("---")

    # ── Split report into tabs ─────────────────────────────────────────────
    raw_md = md_path.read_text(encoding="utf-8")
    sections = _split_sections(raw_md)

    # Preamble (price/date block) outside tabs so it's always visible
    preamble = sections.pop("__preamble__", None)
    if preamble:
        with st.container(border=True):
            st.markdown(preamble)

    tab_labels = list(sections.keys())
    if len(tab_labels) == 1 and tab_labels[0] == "全文":
        # Fallback: unsplit report
        st.markdown(sections["全文"])
    else:
        tabs = st.tabs(tab_labels)
        for tab, label in zip(tabs, tab_labels):
            with tab:
                with st.container(border=True):
                    st.markdown(sections[label])
