"""美股 · COT / ES 週報.

Renders the weekly report produced by scripts/cot_es.py
(reports/cot/YYYY-MM-DD.md). The .json sibling holds the verified data the
report was built from, shown as an audit panel.
"""

import re
import sys
from pathlib import Path

import streamlit as st

from . import _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_COT_DIR = _shared.REPORTS_DIR / "cot"


def _render_generate() -> None:
    """On-demand 'generate this week's report' button (local Claude subscription).

    Calls scripts/cot_es.generate_report(), which fetches CFTC COT + ES=F and
    lets Claude write the analysis (anti-hallucination: code fetches, LLM only
    analyses). ~30-60s. Works locally (logged-in Claude / Max); a headless cloud
    instance with no auth will error — surfaced, not silent."""
    c1, c2 = st.columns([1, 3])
    run = c1.button("🔄 產生本週報告", type="primary",
                    help="抓 CFTC COT + ES=F 收盤 → Claude 產生週報(本機訂閱,約 30–60 秒)")
    c2.caption("手動更新:即時抓最新一週資料並產出報告(平常每週五 CI 自動跑)。需本機登入 Claude。")
    if not run:
        return
    with st.spinner("抓取 CFTC COT + ES=F 收盤,呼叫 Claude 產生週報中…(約 30–60 秒)"):
        try:
            from scripts import cot_es  # lazy
            res = cot_es.generate_report(model="claude-opus-4-8")
        except Exception as e:  # noqa: BLE001 — surface any failure to the user
            if type(e).__name__ == "PriceUnverified":
                st.error(f"⚠️ ES=F 價格無法驗證,未產生報告(反幻覺保護):{e}")
            else:
                st.error(f"產生報告失敗({type(e).__name__}):{e}")
            return
    _shared.load_json.clear()  # bust the cached verified.json reads
    st.success(f"✅ 已產生 {res['stamp']} 週報(COT as-of {res['cot_as_of']} · "
               f"ES 週五收 {res['friday_close']})")
    st.rerun()

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

    _render_generate()
    st.divider()

    reports = sorted(_COT_DIR.glob("*.md"), reverse=True) if _COT_DIR.exists() else []
    if not reports:
        st.info("尚無 COT 週報。點上方「🔄 產生本週報告」即可生成。")
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

    # ── Split report into tabs ─────────────────────────────────────────────
    raw_md = md_path.read_text(encoding="utf-8")
    sections = _split_sections(raw_md)

    # Preamble (price/date block) outside tabs so it's always visible.
    # When verified data is present the metric cards already surface ES close,
    # COT as-of date and week change, so we strip those duplicate lines from
    # the preamble and only render the remainder (OHLC detail etc.).
    preamble = sections.pop("__preamble__", None)
    if preamble:
        # Remove lines that duplicate the metric-card values already shown:
        # • lines containing the COT as-of date pattern (e.g. "**As of** …")
        # • lines containing the ES closing price / symbol reference
        # • blockquote lines that restate the disclaimer caption
        filtered_lines = []
        for line in preamble.splitlines():
            stripped = line.strip()
            # Skip blockquote disclaimer lines (restate the top caption). Match the
            # shared suffix so it catches both 資料/數據 由系統抓取 wording.
            if stripped.startswith(">") and "由系統抓取" in stripped:
                continue
            if stripped == "---":          # drop the report's own trailing rule
                continue
            filtered_lines.append(line)

        filtered_preamble = "\n".join(filtered_lines).strip()

        # If verified data is available, also suppress lines that echo the
        # values already shown in the metric cards (friday close / COT as-of).
        if verified and filtered_preamble:
            cot_asof = (verified.get("cot") or {}).get("as_of", "")
            fri_close_str = str((verified.get("price") or {}).get("friday_close", ""))
            suppressed = []
            for line in filtered_preamble.splitlines():
                # Drop lines whose sole content is to restate COT as-of or
                # the Friday close already visible in the metric cards.
                if cot_asof and cot_asof in line:
                    continue
                if fri_close_str and fri_close_str in line and "收盤" in line:
                    continue
                suppressed.append(line)
            filtered_preamble = "\n".join(suppressed).strip()

        if filtered_preamble:
            st.divider()
            with st.container(border=True):
                st.markdown(filtered_preamble)

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
