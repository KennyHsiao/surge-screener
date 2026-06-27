"""美股 · 機構持股 — per-stock institutional ownership + insider activity.

Surfaces scripts/institutional_free.gather_institutional (free yfinance aggregation
of 13F holdings + Form-4 insider transactions, cached 6h) — data that until now
only fed the LLM's Dimension-4 (籌碼) score and was never shown. Magnificent-7
quick-pick + any-ticker lookup. Read-only, decision reference (not advice).

Free feed gives the top ~5 institutional holders (not a full 13F). Per-fund 13F
portfolios (free via SEC EDGAR) are a planned Phase 2, not here.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
_NET_LABEL = {"buying": "買超", "selling": "賣超", "neutral": "中性"}


@st.cache_data(ttl=21600, show_spinner=False)
def _load(ticker: str) -> dict | None:
    from scripts import institutional_free
    return institutional_free.gather_institutional(ticker)


def _pct(x) -> str:
    return f"{x:.1f}%" if isinstance(x, (int, float)) else "—"


def _shares(x) -> str:
    if not isinstance(x, (int, float)):
        return "—"
    a = abs(x)
    if a >= 1e6:
        return f"{x / 1e6:.2f}M"
    if a >= 1e3:
        return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"


def _int(x) -> str:
    return f"{int(x)}" if isinstance(x, (int, float)) else "—"


def _render_holders(holders: list) -> None:
    st.markdown("#### 前大機構股東")
    disp = pd.DataFrame([{
        "機構": h.get("holder") or "?",
        "持股%": h.get("pct_held"),
        "市值($B)": (h["value"] / 1e9) if isinstance(h.get("value"), (int, float)) else None,
        "季變化%": h.get("pct_change"),
    } for h in holders])
    st.dataframe(
        disp, hide_index=True, use_container_width=True,
        column_config={
            "機構": st.column_config.TextColumn(width="large"),
            "持股%": st.column_config.NumberColumn(format="%.2f%%", help="占已發行股比例"),
            "市值($B)": st.column_config.NumberColumn(format="$%.1f"),
            "季變化%": st.column_config.NumberColumn(format="%+.2f%%", help="較上一季的持股變動"),
        },
    )
    st.caption("ℹ️ 免費源約前 5 大機構,非完整 13F;季變化反映上一季申報。")


def _render_score_context(ticker: str) -> None:
    scored = _shared.load_json(str(_shared.candidate_output_path("scored_candidates.json"))) or {}
    for c in scored.get("all_scored", []) or []:
        if (c.get("ticker") or "").upper() != ticker:
            continue
        score = (c.get("scores") or {}).get("institutional")
        if score is None:
            return
        with st.expander(f"📊 篩選器籌碼評分(Dim 4):{score}/10 · 判定 {c.get('verdict', '?')}",
                         expanded=False):
            sigs = [s for s in (c.get("key_signals") or [])
                    if any(k in s for k in ("機構", "內部", "籌碼", "institution", "insider"))]
            for s in (sigs or (c.get("key_signals") or [])[:3]):
                st.caption("· " + s)
        return


def _render_detail(ticker: str, data: dict) -> None:
    own = data.get("ownership_pct") or {}
    ins = data.get("insider_6m") or {}

    st.markdown(f"#### {ticker} 持股結構")
    cols = st.columns(4)
    _shared.metric_card(cols[0], "機構持股%", _pct(own.get("institutions_held")),
                        help="機構持有占已發行股的比例")
    _shared.metric_card(cols[1], "機構/流通股%", _pct(own.get("institutions_float_held")),
                        help="機構持有占流通股的比例")
    _shared.metric_card(cols[2], "內部人持股%", _pct(own.get("insiders_held")))
    with cols[3]:
        with st.container(border=True):
            nd = ins.get("net_direction")
            net = ins.get("net_shares")
            # Signed net shares → st.metric colours by the delta's leading sign:
            # 淨買進(+)=綠、淨賣出(−)=紅. No delta when neutral / unknown.
            st.metric("內部人 6 月", _NET_LABEL.get(nd, "—"),
                      delta=_shares(net) if isinstance(net, (int, float)) and net != 0 else None,
                      delta_color="normal",
                      help="6 個月內部人淨買賣方向 + 淨股數(Form-4);綠=淨買進、紅=淨賣出")

    if data.get("top_institutional_holders"):
        _render_holders(data["top_institutional_holders"])

    if ins:
        st.markdown("#### 6 個月內部人買賣")
        ic = st.columns(3)
        _shared.metric_card(ic[0], "買進(股 / 筆)",
                            f"{_shares(ins.get('purchase_shares'))} / {_int(ins.get('purchase_trans'))}")
        _shared.metric_card(ic[1], "賣出(股 / 筆)",
                            f"{_shares(ins.get('sale_shares'))} / {_int(ins.get('sale_trans'))}")
        _shared.metric_card(ic[2], "淨股數", _shares(ins.get("net_shares")))

    txns = data.get("recent_insider_transactions")
    if txns:
        st.markdown("#### 最近內部人交易")
        disp = pd.DataFrame([{
            "日期": t.get("date") or "",
            "人名": t.get("insider") or "",
            "職位": t.get("position") or "",
            "交易": t.get("transaction") or "",
            "股數": t.get("shares"),
        } for t in txns])
        st.dataframe(disp, hide_index=True, use_container_width=True,
                     column_config={"股數": st.column_config.NumberColumn(format="%d")})

    _render_score_context(ticker)
    st.caption(f"來源:`{data.get('source', 'yfinance_free')}` · 機構=聚合 13F、內部人=Form-4。"
               "資料有延遲,作為籌碼脈絡參考、非投資建議。")


def render_for(ticker: str) -> None:
    """Embeddable per-ticker institutional view (no MAG7 quick-pick / input widget) —
    used by 個股總覽's 機構 tab. _load + guard + _render_detail."""
    ticker = (ticker or "").strip().upper().lstrip("$")
    if not ticker:
        return
    with st.spinner(f"抓取 {ticker} 機構持股…"):
        data = _load(ticker)
    if not data:
        st.warning(f"免費源此檔({ticker})暫無機構 / 內部人資料(常見於小型股 / ETF)。")
        return
    _render_detail(ticker, data)


def render(embedded: bool = False) -> None:
    if not embedded:
        st.header("🏢 機構持股")
    st.caption("某股票 → **誰持有它**:機構 / 內部人持股明細(免費 yfinance 聚合 13F + Form-4,"
               "快取 6 小時,對應 Dimension 4 籌碼)。唯讀、決策參考,非投資建議。")

    if "inst_ticker" not in st.session_state:
        st.session_state["inst_ticker"] = "NVDA"

    st.markdown("**七大巨頭快選**")
    for col, t in zip(st.columns(len(MAG7)), MAG7):
        if col.button(t, key=f"mag7_{t}", use_container_width=True):
            st.session_state["inst_ticker"] = t

    c1, c2 = st.columns([3, 1])
    c1.text_input("代號", key="inst_ticker", label_visibility="collapsed",
                  placeholder="美股代號,如 NVDA")
    c2.button("查詢", type="primary", use_container_width=True)

    ticker = (st.session_state.get("inst_ticker") or "").strip().upper().lstrip("$")
    if not ticker:
        st.info("輸入代號,或點上方七大巨頭快選。")
        return

    with st.spinner(f"抓取 {ticker} 機構持股…"):
        data = _load(ticker)
    if not data:
        st.warning(f"免費源此檔({ticker})暫無機構 / 內部人資料(常見於小型股 / ETF)。")
        return
    with st.container(border=True):
        _render_detail(ticker, data)
