"""美股 · 風險雷達 / Risk Guard — V1 唯讀風險儀表板。

整合大盤 regime、價格結構、期權流、板塊輪動、COT 背景與 IBKR 持倉,對每檔輸出
0-100 風險分數與 NORMAL / WATCH / REDUCE / EXIT 狀態。規則式分數(scripts/risk_guard.py),
LLM 不參與評分。非投資建議。

四個分頁:總覽 / 持倉·Watchlist / 單檔明細 / 資料來源。資料來源可選 IBKR 持倉 /
Screener 候選 / Watchlist / 手動輸入;缺任一來源都能用其他來源,缺口明確列出、不藏。
"""

import sys

import pandas as pd
import streamlit as st

from . import _shared

_SCRIPTS = str(_shared.DATA_DIR / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

# escalating risk ladder, tokens only: 綠→黃(橙)→番茄紅→純紅(警報, ACCENT 保留給最高警戒)。
# DATA_GAP 是「無法評估」(灰),刻意不給綠色,且排序靠前,確保缺資料不被誤讀成低風險。
_STATUS_COLOR = {"NORMAL": _shared.GREEN, "WATCH": _shared.AMBER,
                 "REDUCE": _shared.RED, "EXIT": _shared.ACCENT, "DATA_GAP": _shared.MUTED}
_STATUS_EMOJI = {"NORMAL": "🟢", "WATCH": "🟡", "REDUCE": "🟠", "EXIT": "🔴", "DATA_GAP": "⚪"}
_STATUS_RANK = {"EXIT": 3, "REDUCE": 2, "DATA_GAP": 2, "WATCH": 1, "NORMAL": 0}
_STATUS_ZH = {"NORMAL": "正常持有", "WATCH": "降倉觀察", "REDUCE": "減碼/避開",
              "EXIT": "出場警戒", "DATA_GAP": "資料不足/無法評估"}


@st.cache_data(ttl=600, show_spinner=False)
def _analyze(tickers: tuple, include_positions: bool) -> dict:
    import risk_guard
    data = risk_guard.analyze_risk(list(tickers), include_positions=include_positions)
    try:
        paths = risk_guard.write_report(data, risk_guard.OUT_DEFAULT)
        meta = risk_guard.refresh_analytics_for_report(risk_guard.OUT_DEFAULT)
        data["persistence"] = {"paths": paths, "analytics_rows": meta.get("rows")}
    except Exception as e:  # noqa: BLE001
        data["persistence_warning"] = str(e)
    return data


def _status_chip(status: str) -> str:
    return _shared.chip(f"{_STATUS_EMOJI.get(status, '')} {status} · {_STATUS_ZH.get(status, '')}",
                        _STATUS_COLOR.get(status, _shared.MUTED))


def _money(x) -> str:
    if not isinstance(x, (int, float)):
        return "—"
    sign, a = ("-" if x < 0 else ""), abs(x)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}${a / div:.2f}{suf}"
    return f"{sign}${a:,.0f}"


# ───────────────────────── source selection ─────────────────────────
def _collect(source: str, manual_text: str) -> tuple[list[str], bool]:
    """Return (tickers, include_positions) for the chosen source."""
    import risk_guard
    if source == "IBKR 持倉":
        return risk_guard.tickers_from_positions(), True
    if source == "Screener 候選":
        return risk_guard.tickers_from_candidates(), False
    if source == "Watchlist":
        return risk_guard.tickers_from_watchlist(), False
    import re
    return [t for t in re.split(r"[\s,;]+", (manual_text or "").upper()) if t.strip()], False


# ───────────────────────── tabs ─────────────────────────
def _tab_overview(data: dict) -> None:
    m = data.get("market") or {}
    regime = m.get("regime") or {}
    cot = m.get("cot") or {}
    st.markdown("**市場風險** " + _status_chip(m.get("status", "NORMAL")), unsafe_allow_html=True)
    c = st.columns(4)
    _shared.metric_card(c[0], "市場風險分數", f"{m.get('score', 0)} / 100")
    spy = []
    if regime.get("spy_vs_50dma"):
        spy.append(f"50DMA {'⬇下' if regime['spy_vs_50dma'] == 'below' else '⬆上'}")
    if regime.get("spy_vs_200dma"):
        spy.append(f"200DMA {'⬇下' if regime['spy_vs_200dma'] == 'below' else '⬆上'}")
    _shared.metric_card(c[1], "SPY vs 均線", " · ".join(spy) or "—")
    vix = regime.get("vix_level")
    _shared.metric_card(c[2], "VIX", f"{vix:.1f}" if isinstance(vix, (int, float)) else "—")
    dp = cot.get("delta_pct")
    _shared.metric_card(c[3], "COT 週二→週五", f"{dp:+.1f}%" if isinstance(dp, (int, float)) else "—",
                        help="ES 期貨自 COT 申報日(週二)到週五收盤的變動")

    sr = regime.get("sector_rotation") or {}
    leaders = sr.get("leaders") or []
    weakening = m.get("weakening_sectors") or []
    sector_chips = []
    if leaders:
        sector_chips.append(("領漲 " + ", ".join(leaders[:4]), _shared.GREEN))
    if weakening:
        sector_chips.append(("轉弱/落後 " + ", ".join(weakening[:4]), _shared.RED))
    if sector_chips:
        st.markdown("**板塊**", unsafe_allow_html=True)
        _shared.chips_row(sector_chips)

    sys_gaps = m.get("data_gaps") or []
    if sys_gaps:
        st.markdown("**系統資料缺口**")
        _shared.chips_row([(g, _shared.MUTED) for g in sys_gaps])

    rows = data.get("rows") or []
    reasons = [r for row in sorted(rows, key=lambda x: -x.get("risk_score", 0))
               for r in row.get("primary_reasons", [])]
    seen, top = set(), []
    for r in (m.get("reasons") or []) + reasons:
        if r not in seen:
            seen.add(r)
            top.append(r)
    if top:
        st.markdown("##### 今日主要風險原因")
        for r in top[:5]:
            st.markdown(f"- {r}")
    st.caption(data.get("disclaimer", ""))


def _tab_table(data: dict) -> None:
    rows = data.get("rows") or []
    if not rows:
        st.info("沒有可顯示的標的。")
        return
    df = pd.DataFrame([{
        "狀態": f"{_STATUS_EMOJI.get(r['status'], '')} {r['status']}",
        "代號": r["ticker"], "總風險": r["risk_score"],
        "Market": r["market_score"], "Price": r["price_score"],
        "Options": r["options_score"], "Sector": r["sector_score"],
        "Position": r["position_score"], "COT": r["cot_score"], "DQ": r["data_quality_score"],
        "主要原因": " · ".join(r.get("primary_reasons", [])[:3]),
        "資料缺口": " · ".join(r.get("data_gaps", [])) or "—",
        "_rank": _STATUS_RANK.get(r["status"], 0),
        # plan §5.3 third sort key: biggest position loss first (most-negative P&L).
        "_loss": -((r.get("position") or {}).get("total_unrealized_pnl") or 0),
    } for r in rows]).sort_values(["_rank", "總風險", "_loss"], ascending=False).drop(
        columns=["_rank", "_loss"])

    def _tint(row):
        status = row["狀態"].split()[-1]
        c = _STATUS_COLOR.get(status, _shared.MUTED)
        return [f"background-color:{c}22" if col in ("狀態", "總風險") else "" for col in row.index]
    try:
        styled = df.style.apply(_tint, axis=1)
    except Exception:  # noqa: BLE001
        styled = df
    st.dataframe(
        styled, hide_index=True, use_container_width=True,
        column_config={
            "總風險": st.column_config.ProgressColumn("總風險", min_value=0, max_value=100, format="%d"),
            "主要原因": st.column_config.TextColumn("主要原因", width="large"),
        })
    st.caption("分數越高越危險。狀態:NORMAL 正常 / WATCH 降倉觀察 / REDUCE 減碼避開 / EXIT 出場警戒。"
               "缺資料計入 DQ(資料品質),不視為低風險。")


def _tab_portfolio(data: dict) -> None:
    pf = data.get("portfolio") or {}
    if not pf.get("available"):
        st.info("組合風控需 IBKR 持倉資料(reports/reconciliation.json)。請先執行 "
                "`python scripts/ibkr_client.py reconcile`,或上方來源選「IBKR 持倉」"
                "並開啟「計入 IBKR 持倉風險」。")
        return
    if not pf.get("reachable"):
        st.warning("IBKR 連線未取得(reachable=false):顯示為最後一次 reconcile 的快照或空集合。")
    dte = pf.get("dte_buckets") or {}
    n_all = sum(len(dte.get(k, [])) for k in ("le7", "le14", "le30"))
    c = st.columns(4)
    pnl = pf.get("total_unrealized_pnl")
    _shared.metric_card(c[0], "總未實現損益", _money(pnl),
                        delta=("獲利" if isinstance(pnl, (int, float)) and pnl >= 0 else "虧損"),
                        delta_color="normal")
    _shared.metric_card(c[1], "持倉數", str(pf.get("position_count", 0)))
    _shared.metric_card(c[2], "≤7 天到期選擇權", str(len(dte.get("le7", []))))
    _shared.metric_card(c[3], "≤30 天到期選擇權", str(n_all))

    warns = pf.get("concentration_warnings") or []
    if warns:
        st.markdown("##### ⚠️ 集中度 / 風控警示")
        for w in warns:
            st.markdown(f"- {w}")

    bu = pf.get("by_underlying") or []
    if bu:
        st.markdown("##### 各標的(虧損優先)")
        st.dataframe(pd.DataFrame([{
            "狀態": f"{_STATUS_EMOJI.get(r['status'], '')} {r['status']}", "代號": r["ticker"],
            "板塊": r["sector"], "未實現損益": r["unrealized_pnl"],
            "市值": r["market_value"], "腿數": r["leg_count"]} for r in bu]),
            hide_index=True, use_container_width=True, column_config={
                "未實現損益": st.column_config.NumberColumn(format="$%.0f"),
                "市值": st.column_config.NumberColumn(format="$%.0f")})

    bs = pf.get("by_sector") or []
    if bs:
        st.markdown("##### 板塊曝險集中度")
        st.dataframe(pd.DataFrame([{
            "板塊": s["sector"], "檔數": s["count"], "曝險%": s.get("exposure_pct"),
            "市值": s["market_value"], "未實現損益": s["unrealized_pnl"]} for s in bs]),
            hide_index=True, use_container_width=True, column_config={
                "曝險%": st.column_config.ProgressColumn("曝險%", min_value=0, max_value=100, format="%.0f%%"),
                "市值": st.column_config.NumberColumn(format="$%.0f"),
                "未實現損益": st.column_config.NumberColumn(format="$%.0f")})

    rows_dte = [{"到期桶": label, "代號": e["ticker"], "合約": e["label"], "DTE": e["dte"],
                 "未實現損益": e.get("unrealized_pnl")}
                for bucket, label in (("le7", "≤7"), ("le14", "8–14"), ("le30", "15–30"))
                for e in dte.get(bucket, [])]
    if rows_dte:
        st.markdown("##### 近月到期選擇權")
        st.dataframe(pd.DataFrame(rows_dte), hide_index=True, use_container_width=True,
                     column_config={"未實現損益": st.column_config.NumberColumn(format="$%.0f")})
    st.caption("僅供訊號生成,非投資建議。持倉來自本機 IBKR reconcile(唯讀)。")


def _tab_detail(data: dict) -> None:
    rows = data.get("rows") or []
    if not rows:
        st.info("沒有可顯示的標的。")
        return
    pick = st.selectbox("選擇代號", [r["ticker"] for r in rows], key="rg_detail_pick")
    r = next((x for x in rows if x["ticker"] == pick), None)
    if not r:
        return
    st.markdown(_status_chip(r["status"]) + f"　總風險 **{r['risk_score']} / 100**",
                unsafe_allow_html=True)

    comps = [("Market", r["market_score"], 20), ("Price", r["price_score"], 25),
             ("Options", r["options_score"], 20), ("Sector", r["sector_score"], 15),
             ("Position", r["position_score"], 10), ("COT", r["cot_score"], 5),
             ("DataQuality", r["data_quality_score"], 5)]
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[c for _, _, c in comps], y=[n for n, _, _ in comps],
                         orientation="h", marker_color=_shared.PANEL, name="上限",
                         hoverinfo="skip"))
    fig.add_trace(go.Bar(x=[s for _, s, _ in comps], y=[n for n, _, _ in comps],
                         orientation="h", marker_color=_STATUS_COLOR.get(r["status"], _shared.MUTED),
                         name="分數", text=[s for _, s, _ in comps], textposition="auto"))
    fig.update_layout(barmode="overlay", height=300, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e6e9ef"}, showlegend=False,
                      yaxis={"categoryorder": "array", "categoryarray": [n for n, _, _ in comps][::-1]})
    st.plotly_chart(fig, use_container_width=True)

    if r.get("primary_reasons"):
        st.markdown("**主要風險原因**")
        for x in r["primary_reasons"]:
            st.markdown(f"- {x}")
    if r.get("data_gaps"):
        _shared.chips_row([(f"缺:{g}", _shared.MUTED) for g in r["data_gaps"]])

    tech, opt, sec, pos = (r.get("technical") or {}, r.get("options") or {},
                           r.get("sector") or {}, r.get("position") or {})
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**價格 / 技術**")
        st.write({k: v for k, v in tech.items() if v is not None} or "—")
        st.markdown("**期權**")
        st.write({k: v for k, v in opt.items() if v is not None} or "—")
    with cols[1]:
        st.markdown("**板塊**")
        st.write({k: v for k, v in sec.items() if v is not None} or "—")
        st.markdown("**持倉**")
        st.write({k: v for k, v in pos.items() if v is not None} or "（無持倉資料）")
    # COT is systemic background (shared across tickers) — show the market-level read.
    cot = (data.get("market") or {}).get("cot") or {}
    st.markdown(f"**COT 背景**　(個股得分 +{r['cot_score']})")
    st.write({k: v for k, v in cot.items() if v is not None} or "（無 COT 資料）")


def _tab_sources(data: dict) -> None:
    src = data.get("data_sources") or {}
    fix = {
        "regime": "(自動;缺則即時以 yfinance 計算 SPY/VIX)",
        "cot": "make cot",
        "positions": "python scripts/ibkr_client.py reconcile",
        "options_flow": "python scripts/options_flow_scan.py",
        "sector": "python scripts/sector_flow.py",
        "options": "(即時 yfinance,無需指令)",
    }
    label = {"regime": "大盤 regime", "cot": "COT", "positions": "IBKR 持倉",
             "options_flow": "選擇權異常流", "sector": "板塊輪動", "options": "期權鏈"}
    m = data.get("market") or {}
    # best-effort per-source "last updated" (only some sources carry a timestamp)
    updated = {
        "regime": (m.get("regime") or {}).get("scan_date") or data.get("as_of"),
        "cot": (m.get("cot") or {}).get("as_of"),
        "options": data.get("generated_at"),
    }
    df = pd.DataFrame([{
        "來源": label.get(k, k),
        "狀態": "✅ 可用" if v not in ("missing", None) else "⚠️ 缺",
        "最後更新": updated.get(k) or "—",
        "路徑 / 值": v,
        "修復指令": fix.get(k, ""),
    } for k, v in src.items()])
    st.dataframe(df, hide_index=True, use_container_width=True)

    gaps = m.get("data_gaps") or []
    st.markdown("**目前缺口**")
    if gaps:
        for g in gaps:
            st.markdown(f"- ⚠️ {g}")
    else:
        st.caption("無系統層級資料缺口。")
    st.caption(f"資料時間:{data.get('as_of', '?')} · 產生於 {data.get('generated_at', '?')}")
    if data.get("persistence_warning"):
        st.warning(f"風險掃描已完成，但寫入 Analytics DB 失敗:{data.get('persistence_warning')}")
    elif data.get("persistence"):
        p = data.get("persistence") or {}
        st.caption(f"已寫入 Risk Guard 快照並刷新 Analytics DB，rows={p.get('analytics_rows', '?')}")


# ───────────────────────── entry ─────────────────────────
def render() -> None:
    st.header("🛡 風險雷達 / Risk Guard")
    st.caption("整合大盤、價格、期權、板塊、COT、持倉的唯讀風險儀表板。規則式分數,非投資建議。")

    c1, c2 = st.columns([2, 1])
    source = c1.segmented_control(
        "來源", ["手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"],
        default="手動輸入", key="rg_source")
    manual = ""
    if source == "手動輸入":
        manual = c1.text_input("代碼(逗號/空白分隔)", value="NVDA, AMD, SPY, TSLA, AAPL",
                               key="rg_manual")
    include_pos = c2.toggle("計入 IBKR 持倉風險", value=(source == "IBKR 持倉"), key="rg_inc_pos")

    tickers, src_pos = _collect(source, manual)
    include_positions = include_pos or src_pos
    if not tickers:
        st.info("此來源目前沒有標的(IBKR 需先 reconcile、Watchlist 需 content/us_watchlist.txt)。"
                "可改用「手動輸入」。")
        return

    run_key = (source, tuple(tickers), bool(include_positions))
    if st.session_state.get("rg_result") and st.session_state.get("rg_run_key") != run_key:
        for k in ("rg_result", "rg_detail_pick"):
            st.session_state.pop(k, None)
        st.session_state.pop("rg_run_key", None)

    if st.button(f"🛡 掃描風險({len(tickers)} 檔)", key="rg_run", type="primary"):
        with st.spinner(f"掃描 {len(tickers)} 檔風險中…(抓取技術/期權/板塊,首次較慢)"):
            st.session_state["rg_result"] = _analyze(tuple(tickers), include_positions)
            st.session_state["rg_run_key"] = run_key

    data = st.session_state.get("rg_result")
    if not data:
        st.caption("選好來源後按「掃描風險」。")
        return

    # top cards
    m = data.get("market") or {}
    rows = data.get("rows") or []
    summ = data.get("summary") or {}
    top = st.columns(4)
    with top[0]:
        st.caption("整體市場狀態")
        st.markdown(_status_chip(m.get("status", "NORMAL")), unsafe_allow_html=True)
    _shared.metric_card(top[1], "市場風險分數", f"{m.get('score', 0)} / 100")
    _shared.metric_card(top[2], "高風險檔數", f"{summ.get('high_risk', 0)} / {summ.get('count', len(rows))}",
                        help="狀態為 REDUCE 或 EXIT 的標的數")
    sysg = summ.get("systemic_gaps", 0)
    _shared.metric_card(top[3], "資料缺口",
                        f"{summ.get('data_gaps', 0)} 檔" + (f" · {sysg} 系統" if sysg else ""),
                        help="個股資料缺口檔數 + 系統層級缺口數(COT / 選擇權異常流 / 板塊)")
    if (m.get("data_gaps")):
        st.caption("⚠ 市場讀數含系統資料缺口(見下方「系統資料缺口」),相關背景訊號未完整納入,"
                   "市場分數已避免因缺資料而虛低。")

    t1, t2, t3, t4, t5 = st.tabs(["總覽", "持倉 / Watchlist", "組合風控", "單檔明細", "資料來源"])
    with t1:
        _tab_overview(data)
    with t2:
        _tab_table(data)
    with t3:
        _tab_portfolio(data)
    with t4:
        _tab_detail(data)
    with t5:
        _tab_sources(data)
