"""美股 · 選擇權異常流 (Unusual Options Flow feed).

Reads the EOD scan (reports/options_flow/latest.json from scripts/options_flow_scan.py)
and shows a bullflow-style ranked feed: direction, est premium $, biggest strike/
expiry, V/OI spike, skew, tags — plus a per-ticker live chain drill-down. Free
yfinance = unusual VOLUME; true sweeps/dark-pool need a paid feed (shown in caption).
Verified-data-to-AI: the scan computes; this page displays.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

_FLOW = _shared.REPORTS_DIR / "options_flow"


@st.cache_data(ttl=900, show_spinner=False)
def _live_chain(ticker: str) -> dict | None:
    """Live options chain summary (yfinance, 15min cache) for the drill-down. Never raises."""
    if not ticker:
        return None
    try:
        from scripts import options_free
        return options_free.analyze_options(ticker)
    except Exception:
        return None


def _fmt_notional(n) -> str:
    if not n:
        return "—"
    n = float(n)
    return f"${n / 1e6:.1f}M" if n >= 1e6 else f"${n / 1e3:.0f}K"


def _dir_zh(d: str) -> str:
    return "偏多" if d == "bullish" else "偏空" if d == "bearish" else "中性"


def _biggest_str(s: dict) -> str:
    b = s.get("biggest") or {}
    if b.get("strike") is None:
        return "—"
    exp = s.get("expiry") or ""
    exp_short = f"{int(exp[5:7])}/{int(exp[8:10])}" if len(exp) >= 10 else exp
    kind = "C" if s.get("direction") == "bullish" else "P"
    return f"{b['strike']:g}{kind} {exp_short}".strip()


def _style_dir(col: pd.Series) -> list[str]:
    return [f"color:{_shared.GREEN if v == '偏多' else _shared.RED if v == '偏空' else _shared.MUTED}"
            for v in col]


def _jump_buttons(ticker: str, key_prefix: str) -> None:
    """跨頁跳轉:寫入目標頁 ticker 後 st.switch_page 同 session 一鍵切頁。
    (markdown 相對連結是 target=_blank — 開新分頁=新 session,handoff 會遺失。)"""
    c1, c2, _sp = st.columns([1, 1, 3])
    if c1.button("🔍 個股總覽", key=f"{key_prefix}_chk_{ticker}",
                 help=f"帶 {ticker} 到個股總覽"):
        st.session_state["checkup_ticker"] = ticker
        st.session_state["checkup_handoff"] = ticker  # 一次性,目標頁 pop
        if not _shared.switch_page("stock-checkup"):
            st.caption("請由側欄開啟「個股總覽」。")
    if c2.button("🎯 期權作戰台", key=f"{key_prefix}_ckpt_{ticker}",
                 help=f"帶 {ticker} 到期權作戰台"):
        st.session_state["cockpit_ticker"] = ticker
        if not _shared.switch_page("options-cockpit"):
            st.caption("請由側欄開啟「期權作戰台」。")


def _render_feed(signals: list[dict]) -> None:
    df = pd.DataFrame([{
        "方向": _dir_zh(s.get("direction", "")),
        "代號": s.get("ticker", ""),
        "估權利金": _fmt_notional(s.get("est_notional_usd")),
        "熱度": s.get("flow_score"),
        "V/OI峰值": s.get("max_voi"),
        "最活躍履約": _biggest_str(s),
        "skew": (s.get("call_put_ratio") if s.get("direction") == "bullish"
                 else s.get("put_call_ratio")),
        "標籤": " · ".join(s.get("tags", [])),
    } for s in signals])
    ev = st.dataframe(
        df.style.apply(_style_dir, subset=["方向"]),
        hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row", key="flow_feed_sel",
        column_config={
            "方向": st.column_config.TextColumn("方向", width="small",
                                              help="買權量偏重=偏多;賣權量偏重=偏空(量能偏斜,非買賣方主動性)"),
            "代號": st.column_config.TextColumn("代號", width="small"),
            "估權利金": st.column_config.TextColumn("估權利金$", width="small",
                                                 help="Σ 最活躍履約價 volume × mid × 100(全日估算,非真實成交額)"),
            "熱度": st.column_config.ProgressColumn("熱度", min_value=0, max_value=100,
                                                  format="%d", help="名目金額+V/OI+偏斜 綜合排序"),
            "V/OI峰值": st.column_config.NumberColumn("V/OI峰值", format="%.1f",
                                                    help="單一履約價 全日volume/前一日結算openInterest 峰值;>2 = 異常"),
            "最活躍履約": st.column_config.TextColumn("最活躍履約價", width="small",
                                                  help="該到期鏈成交量最大的履約價(全日彙總,非單一大單/sweep)"),
            "skew": st.column_config.NumberColumn("skew", format="%.1f×",
                                                  help="偏多=call/put 量比;偏空=put/call 量比"),
            "標籤": st.column_config.TextColumn("標籤", width="large"),
        },
    )
    st.caption("🟢偏多=買權量偏重 · 🔴偏空=賣權量偏重。依熱度排序。各筆為單一近月(~30DTE)到期鏈;"
               "免費 yfinance · 15 分快取 · 異常**大量**(非逐筆 sweep)。點選任一列可跳轉分析。")

    try:
        rows_sel = list(ev.selection.rows)
    except Exception:
        rows_sel = []
    if rows_sel:
        tkr = df.iloc[rows_sel[0]]["代號"]
        st.markdown(f"**已選 ${tkr}**")
        _jump_buttons(tkr, "flow_feed")


def _render_detail(signals: list[dict]) -> None:
    if not signals:
        return
    tickers = [s.get("ticker", "") for s in signals if s.get("ticker")]
    if not tickers:
        return
    pick = st.selectbox("個股明細", tickers, index=0)
    s = next((x for x in signals if x.get("ticker") == pick), None)
    if not s:
        return

    bullish = s.get("direction") == "bullish"
    chips = [(_dir_zh(s.get("direction", "")), _shared.GREEN if bullish else _shared.RED)]
    chips += [(t, _shared.AMBER) for t in s.get("tags", [])]
    _shared.chips_row(chips)

    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "估權利金", _fmt_notional(s.get("est_notional_usd")))
    _shared.metric_card(c2, "最活躍履約價", _biggest_str(s),
                        help=f"該履約價全日估算 ~{_fmt_notional((s.get('biggest') or {}).get('notional'))}(非單一大單)")
    mv = s.get("max_voi")
    _shared.metric_card(c3, "V/OI 峰值", f"{mv:g}" if mv is not None else "—",
                        help=f"{s.get('high_voi_strikes', 0)} 檔 V/OI≥2(對比前一日結算 OI)")
    ratio = s.get("call_put_ratio") if bullish else s.get("put_call_ratio")
    _shared.metric_card(c4, "call/put 量比" if bullish else "put/call 量比",
                        f"{ratio:g}×" if ratio else "—")

    _jump_buttons(pick, "flow_det")

    # Live chain: call vs put VOLUME by strike around spot (drill-down).
    with st.spinner("讀取選擇權鏈中…"):
        chain = _live_chain(pick)
    rows = (chain or {}).get("chain_summary") or []
    if not rows:
        st.caption("無即時鏈資料。")
        return
    strikes = [r["strike"] for r in rows]
    spot = (chain or {}).get("spot_price")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=[r["call_vol"] for r in rows], name="Call 量",
                         marker_color=_shared.GREEN))
    fig.add_trace(go.Bar(x=strikes, y=[-r["put_vol"] for r in rows], name="Put 量",
                         marker_color=_shared.RED))
    if spot:
        fig.add_vline(x=spot, line_dash="dash", line_color=_shared.MUTED,
                      annotation_text=f"現價 {spot:g}", annotation_position="top")
    fig.update_layout(
        height=340, barmode="relative", margin=dict(l=20, r=20, t=30, b=30),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.PANEL, font=dict(color="#d6dae3"),
        legend=dict(orientation="h", y=1.1), xaxis_title="履約價",
        yaxis_title="成交量 (Call 上 / Put 下)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"到期 {(chain or {}).get('expiration_analyzed', '?')} 的鏈成交量分布。")


def render() -> None:
    st.title("🚨 選擇權異常流")
    st.caption("異常大量選擇權(bullflow 風格):量能偏斜方向 · 估權利金 · 最活躍履約價 · V/OI 暴量。"
               "免費 yfinance 偵測「異常**大量**」(量能,非買賣方主動性);真正的逐筆 sweep/暗池需付費源"
               "(Unusual Whales)。決策參考,非投資建議。")

    data = _shared.load_json(str(_FLOW / "latest.json"))
    if not data or not data.get("signals"):
        st.info("尚無異常流資料 — CI 於美股收盤後產生;或本機執行 "
                "`python scripts/options_flow_scan.py`。")
        return

    signals = data["signals"]
    bull = sum(1 for s in signals if s.get("direction") == "bullish")
    bear = sum(1 for s in signals if s.get("direction") == "bearish")
    st.caption(f"資料 {data.get('as_of')} · 來源 {data.get('provider')} · "
               f"掃描 {data.get('universe_size')} 檔 · 偵測 {data.get('signal_count')} 筆 · "
               f"門檻 {_fmt_notional(data.get('min_notional'))}")
    _shared.chips_row([(f"🟢 偏多 {bull}", _shared.GREEN), (f"🔴 偏空 {bear}", _shared.RED)])

    t1, t2 = st.tabs(["🔥 異常流排行", "🔎 個股明細"])
    with t1:
        _render_feed(signals)
    with t2:
        _render_detail(signals)
