"""美股 · 期權分析.

Per-ticker options view built on scripts/options_free.py::analyze_options
(free yfinance data — covers Dim 6a/6d; 6b sweeps & 6c dark pool need
Unusual Whales). Also surfaces the options_flow dimension across the day's
scored candidates as a ranking.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


_VERDICT_EMOJI = {
    "STRONG_BUY": "🟢", "BUY": "🟢", "ACCUMULATE": "🟢",
    "WATCH": "🟡", "MONITOR": "🟡", "NEEDS_LAYER2": "🟡", "HOLD": "🟡",
    "REJECT": "🔴", "AVOID": "🔴",
}
_VERDICT_ORDER = {
    "STRONG_BUY": 0, "BUY": 1, "ACCUMULATE": 1, "WATCH": 2, "MONITOR": 2,
    "NEEDS_LAYER2": 2, "HOLD": 3, "REJECT": 5, "AVOID": 5,
}


def _iv_rank_spark(ticker: str):
    """(rank|None, accumulating, n_days, spark[IV% floats]|None) — all from local
    iv_history (no network), so the triage grid stays fast."""
    try:
        from scripts import iv_history as ivh  # lazy
        ivp = ivh.iv_percentile(ticker)
    except Exception:
        ivp = {"rank": None, "accumulating": True, "n_days": 0}
    safe = "".join(c for c in ticker.upper() if c.isalnum() or c in "-._")
    raw = _shared.load_json(str(_shared.REPORTS_DIR / "iv_history" / f"{safe}.json"))
    series = (raw or {}).get("series", {})
    spark = None
    if series:
        spark = [round(float(v) * 100, 1) for _, v in sorted(series.items())][-30:] or None
    rank = None if ivp.get("accumulating") else ivp.get("rank")
    return rank, bool(ivp.get("accumulating")), int(ivp.get("n_days") or 0), spark


def _candidate_grid() -> pd.DataFrame | None:
    """Day's scored universe as a triage grid: verdict + flow + IV-Rank + sparkline."""
    scored = _shared.load_json(str(_shared.candidate_output_path("scored_candidates.json")))
    if not scored:
        return None
    cands = scored.get("all_scored") or (
        (scored.get("needs_layer2") or []) + (scored.get("watchlist") or []))
    rows = []
    for c in cands:
        t = c.get("ticker")
        if not t:
            continue
        rank, _accum, _n, spark = _iv_rank_spark(t)
        verdict = c.get("verdict", "?")
        rows.append({
            "判定": f"{_VERDICT_EMOJI.get(verdict, '⚪')} {verdict}",
            "代號": t,
            "綜合": c.get("regime_adjusted_score", c.get("composite_score", 0)),
            "選擇權流": (c.get("scores") or {}).get("options_flow", 0),
            "IV-Rank": rank,
            "IV(近30)": spark,
            "_o": _VERDICT_ORDER.get(verdict, 4),
            "_r": rank if rank is not None else 999.0,  # accumulating sorts last
        })
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values(["_o", "_r"], ascending=[True, True])
    return df.drop(columns=["_o", "_r"]).reset_index(drop=True)


def _num(x):
    try:
        v = float(x)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _render_bias_iv_chips(ticker: str, d6a: dict) -> None:
    """Top-of-page decision anchor: directional-flow bias + IV-Rank regime —
    a pro reads bias and whether premium is rich/cheap BEFORE scanning the chain."""
    cpv, pcr = _num(d6a.get("call_put_volume_ratio")), _num(d6a.get("put_call_ratio"))
    if cpv is not None and cpv >= 1.2 and (pcr is None or pcr < 1.0):
        bias = ("流向偏多", _shared.GREEN)
    elif (cpv is not None and cpv < 0.8) or (pcr is not None and pcr > 1.5):
        bias = ("流向偏空", _shared.RED)
    else:
        bias = ("流向中性", _shared.MUTED)
    try:
        from scripts import iv_history as ivh  # lazy
        ivp = ivh.iv_percentile(ticker)
    except Exception:
        ivp = {"accumulating": True, "n_days": 0}
    if ivp.get("accumulating") or ivp.get("rank") is None:
        iv_chip = (f"IV Rank 累積中 n={ivp.get('n_days', 0)}", _shared.MUTED)
    else:
        rank = ivp["rank"]
        col = _shared.GREEN if rank < 30 else _shared.RED if rank > 60 else _shared.AMBER
        iv_chip = (f"IV Rank {rank:.0f}", col)
    _shared.chips_row([bias, iv_chip])
    st.caption("流向偏好由當日 call/put 量比推導(非方向預測);IV Rank 來自 iv_history 每日快照。")


def _chain_bar(df, spot, oi_ok) -> go.Figure:
    """Grouped call/put volume by strike (+ optional OI line) — the default view."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["strike"], y=df["call_vol"], name="Call 量",
                         marker_color=_shared.GREEN))
    fig.add_trace(go.Bar(x=df["strike"], y=df["put_vol"], name="Put 量",
                         marker_color=_shared.RED))
    if oi_ok:
        fig.add_trace(go.Scatter(x=df["strike"], y=df["call_oi"], name="Call OI",
                                 mode="lines", line=dict(color=_shared.BLUE, width=1)))
    if spot:
        fig.add_vline(x=spot, line_dash="dash", line_color=_shared.AMBER,
                      annotation_text=f"現價 {spot}", annotation_position="top")
    fig.update_layout(barmode="group", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0))
    return fig


def _chain_heatmap(df, spot, oi_ok) -> go.Figure:
    """Concentration heatmap: metric rows × strike columns, per-row normalized so
    each row's brightest cell is its wall/pin. Colorblind-safe HEAT_SEQ (no matplotlib)."""
    rows = [("Call 量", "call_vol"), ("Put 量", "put_vol")]
    if oi_ok:
        rows = [("Call OI", "call_oi"), ("Put OI", "put_oi")] + rows
    strikes = df["strike"].tolist()
    z, text, ylabels = [], [], []
    for label, key in rows:
        if key not in df:
            continue
        vals = [float(v) for v in df[key].tolist()]
        mx = max(vals) or 1.0
        z.append([v / mx for v in vals])
        text.append([f"{int(v):,}" for v in vals])
        ylabels.append(label)
    fig = go.Figure(go.Heatmap(
        x=strikes, y=ylabels, z=z, text=text, xgap=1, ygap=2,
        colorscale=_shared.HEAT_SEQ, showscale=False, zmin=0, zmax=1,
        hovertemplate="%{y} @ %{x}: %{text}<extra></extra>"))
    if spot:
        fig.add_vline(x=spot, line_dash="dash", line_color=_shared.AMBER,
                      annotation_text=f"現價 {spot}", annotation_position="top")
    fig.update_layout(height=240, margin=dict(l=10, r=10, t=20, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e6e9ef"})
    return fig


@st.cache_data(ttl=900, show_spinner=False)
def _vol_surface(ticker: str, spot: float, n_expiries: int = 3) -> dict | None:
    """Front-expiry IV-by-strike (smile) + ATM IV per expiry (term structure).

    IV is computed by INVERTING each option's mid price with the shared BS solver
    (the free-feed impliedVolatility column is quantized garbage). Multi-expiry
    network pull (slow) → cached 15min, fired on-demand. None if no usable IV.
    """
    import yfinance as yf
    from datetime import datetime

    tk = yf.Ticker(ticker)
    try:
        exps = list(tk.options or [])
    except Exception:
        return None
    now = datetime.now()
    chosen = []
    for e in exps:
        try:
            dte = (datetime.strptime(e, "%Y-%m-%d") - now).days
        except ValueError:
            continue
        if dte >= 3:
            chosen.append((e, dte))
        if len(chosen) >= n_expiries:
            break
    if not chosen:
        return None

    from scripts import options_analytics as _ana  # IV solver (invert mid price)

    lo, hi = spot * 0.75, spot * 1.25

    def _mid(r):
        """Executable mid (bid/ask), else last trade. None if no price."""
        try:
            b, a = float(r.get("bid")), float(r.get("ask"))
        except (TypeError, ValueError):
            b = a = 0.0
        if b > 0 and a > 0:
            return (b + a) / 2
        try:
            last = float(r.get("lastPrice"))
        except (TypeError, ValueError):
            return None
        return last if last > 0 else None

    def _smile(df, side, T):
        """IV-by-strike from inverting each option's mid PRICE. Keep ATM + the OTM
        wing, drop the deep-ITM tail (mid prices are widest/least reliable there)."""
        out = []
        if df is None or df.empty or "strike" not in df:
            return out
        klo = spot * 0.92 if side == "call" else lo
        khi = hi if side == "call" else spot * 1.08
        sub = df[(df["strike"] >= klo) & (df["strike"] <= khi)]
        for _, r in sub.iterrows():
            mid = _mid(r)
            if mid is None:
                continue
            K = float(r["strike"])
            iv = (_ana.implied_vol_call(mid, spot, K, T) if side == "call"
                  else _ana.implied_vol_put(mid, spot, K, T))
            if iv is not None and 0.05 <= iv <= 3.0:
                out.append((K, iv))
        return sorted(out)

    def _atm_from_smile(cs, ps):
        """ATM IV from the already-sane smile points — the raw ATM-strike IV from
        the free feed is often 0/garbage; the OTM wings carry the usable IVs."""
        near = sorted(iv for k, iv in (cs + ps) if abs(k - spot) <= spot * 0.05)
        if near:
            return near[len(near) // 2]
        pts = cs + ps
        return min(pts, key=lambda p: abs(p[0] - spot))[1] if pts else None

    front, term = None, []
    for idx, (e, dte) in enumerate(chosen):
        try:
            oc = tk.option_chain(e)
        except Exception:
            continue
        T = dte / 365.0
        cs, ps = _smile(oc.calls, "call", T), _smile(oc.puts, "put", T)
        atm = _atm_from_smile(cs, ps)
        if atm is not None:
            term.append({"expiry": e, "dte": dte, "atm_iv": atm})
        if idx == 0:
            front = {"expiry": e, "dte": dte, "calls": cs, "puts": ps}
    if not term and not (front and (front["calls"] or front["puts"])):
        return None
    return {"front": front, "term": term}


def _render_vol_surface(ticker: str, spot: float) -> None:
    """On-demand vol smile (front-expiry skew) + ATM term structure."""
    key = f"vs_show_{ticker}"
    if st.button("📐 載入 波動率微笑 / 期限結構(多到期,較慢)", key=f"vs_btn_{ticker}"):
        st.session_state[key] = True
    if not st.session_state.get(key):
        return
    with st.spinner("抓取多到期波動率中…"):
        vs = _vol_surface(ticker, spot)
    if not vs:
        st.info("無法取得多到期波動率資料(免費源可能無此鏈)。")
        return

    t_smile, t_term = st.tabs(["波動率微笑", "期限結構"])
    with t_smile:
        front = vs.get("front")
        if not front or not (front["calls"] or front["puts"]):
            st.info("前月無足夠 IV 資料。")
        else:
            fig = go.Figure()
            if front["calls"]:
                xs, ys = zip(*front["calls"])
                fig.add_trace(go.Scatter(x=xs, y=[v * 100 for v in ys], name="Call IV",
                                         mode="lines+markers", line=dict(color=_shared.GREEN)))
            if front["puts"]:
                xs, ys = zip(*front["puts"])
                fig.add_trace(go.Scatter(x=xs, y=[v * 100 for v in ys], name="Put IV",
                                         mode="lines+markers", line=dict(color=_shared.RED)))
            fig.add_vline(x=spot, line_dash="dash", line_color=_shared.AMBER,
                          annotation_text=f"現價 {spot}")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10),
                              xaxis_title="履約價", yaxis_title="隱含波動率 %",
                              legend=dict(orientation="h", yanchor="bottom", y=1.0),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font={"color": "#e6e9ef"})
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"前月到期 {front['expiry']}({front['dte']}d)。"
                       "價外 put(左側)IV 翹起 = 下檔避險需求/恐懼(skew)。")
    with t_term:
        term = vs.get("term")
        if not term:
            st.info("無足夠到期可建期限結構。")
        else:
            xs = [t["dte"] for t in term]
            ys = [t["atm_iv"] * 100 for t in term]
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers",
                                       line=dict(color=_shared.BLUE, width=2)))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10),
                              xaxis_title="距到期天數 (DTE)", yaxis_title="ATM IV %",
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font={"color": "#e6e9ef"})
            st.plotly_chart(fig, use_container_width=True)
            shape = ("近月 > 遠月 → backwardation(事件/恐慌被定價)"
                     if len(ys) >= 2 and ys[0] > ys[-1] + 1
                     else "遠月 ≥ 近月 → 正常 contango")
            st.caption("期限結構:" + shape + "。到期 "
                       + " · ".join(f"{t['expiry']}({t['dte']}d {t['atm_iv'] * 100:.0f}%)" for t in term))


def _render_per_ticker() -> None:
    # Persist the analyzed ticker so in-page widgets (the chart view radio) survive
    # reruns — otherwise the button is False on rerun and the whole view vanishes.
    entered = st.text_input("代號", value=st.session_state.get("opt_ticker", "NVDA")).strip().upper()
    if st.button("分析期權", type="primary") and entered:
        st.session_state["opt_ticker"] = entered
    ticker = st.session_state.get("opt_ticker")
    if not ticker:
        st.info("請輸入代號並按「分析期權」。")
        return
    render_for(ticker)


def render_for(ticker: str) -> None:
    """Embeddable per-ticker options analysis (no input widget) — used by 個股總覽's
    期權分析 tab. Body of the former _render_per_ticker, parameterised on the ticker
    (its in-page widgets are already key-suffixed by ticker, so it's tab-safe)."""
    from scripts import options_free  # lazy
    ticker = (ticker or "").strip().upper().lstrip("$")
    if not ticker:
        return

    with st.spinner(f"抓取 {ticker} 期權鏈中…"):
        res = options_free.analyze_options(ticker)

    if not res.get("available"):
        st.warning(f"無法取得期權資料:{res.get('reason', '未知原因')}")
        return

    spot = res.get("spot_price", 0) or 0
    d6a = res.get("details", {}).get("6a", {})
    d6d = res.get("details", {}).get("6d", {})
    oi_ok = res.get("oi_available", False)

    # ── Decision anchor FIRST: directional bias + IV regime, then the detail ──
    _render_bias_iv_chips(ticker, d6a)
    st.caption(
        f"{ticker} · 現價 {spot} · 分析到期日 {res.get('expiration_analyzed', '?')} "
        f"· 來源 `{res.get('source', 'yfinance_free')}`"
    )
    st.divider()

    # ── Objective metrics (volume-led; OI shown only when the feed has it) ──
    r1 = st.columns(4)
    _shared.metric_card(r1[0], "Call/Put 量比", d6a.get("call_put_volume_ratio", "—"),
                        help="當日 call 成交量 ÷ put 成交量,>1 偏多")
    _shared.metric_card(r1[1], "Put/Call 比", d6a.get("put_call_ratio", "—"),
                        help=">1.8 視為偏空(大量買 put)")
    _shared.metric_card(r1[2], "OTM call 量 (5–20%)", f"{d6a.get('otm_call_volume_5_20pct', 0):,}",
                        help="價外 5–20% call 的成交量,投機性買盤指標")
    _shared.metric_card(r1[3], "總 call / put 量",
                        f"{d6a.get('total_call_volume', 0):,} / {d6a.get('total_put_volume', 0):,}")

    # OI-dependent metrics: only meaningful when the feed returned open interest.
    if oi_ok:
        r2 = st.columns(3)
        _shared.metric_card(r2[0], "Call wall 履約價", d6d.get("call_wall_strike", "—"),
                            help="現價上方 OI 最大的履約價(壓力/磁吸位)")
        _shared.metric_card(r2[1], "Call wall 距現價", f"{d6d.get('call_wall_pct_above', '—')}%")
        _shared.metric_card(r2[2], "最大 call V/OI", d6a.get("max_call_voi", "—"),
                            help="單一履約價成交量/未平倉,>2 視為異常活躍")

    # ── Objective chart: call/put distribution by strike (bar or heatmap) ──
    chain = res.get("chain_summary", [])
    if chain:
        df = pd.DataFrame(chain)
        st.markdown("#### 期權鏈分佈(依履約價)")
        view = st.radio("檢視", ["長條", "熱圖"], horizontal=True,
                        label_visibility="collapsed", key=f"chainview_{ticker}")
        fig = _chain_heatmap(df, spot, oi_ok) if view == "熱圖" else _chain_bar(df, spot, oi_ok)
        st.plotly_chart(fig, use_container_width=True)
        if view == "熱圖":
            st.caption("每列各自正規化:亮 = 該指標的牆/釘(集中度)。懸停看原始數值。")
        if not oi_ok:
            st.caption("ℹ️ 未平倉量 (OI) 暫無:免費 yfinance 盤中常回傳 0(OCC 每日收盤後才更新),故以成交量為準。")

    # ── Vol smile / term structure (on-demand: multi-expiry pull is slow) ──
    st.markdown("#### 波動率結構")
    _render_vol_surface(ticker, spot)

    # ── Most active call strikes (objective, volume-ranked) ──
    top = res.get("top_active_calls", [])
    if top:
        st.markdown("#### 最活躍 call 履約價(依成交量)")
        cols = {"strike": "履約價", "volume": "成交量", "open_interest": "未平倉",
                "voi": "V/OI", "premium": "權利金", "notional": "估金額$"}
        # Select only known columns (top_active_calls now also carries premium/
        # notional) so no raw English headers leak into the table.
        tdf = pd.DataFrame(top)
        tdf = tdf[[c for c in cols if c in tdf.columns]].rename(columns=cols)
        st.dataframe(tdf, hide_index=True, use_container_width=True)

    # Signals (derived read of the objective data) — kept but secondary.
    sig_bits = [s for s in (d6a.get("signal"), d6d.get("signal")) if s]
    if sig_bits:
        st.markdown("**訊號讀解:** " + " · ".join(f"`{s}`" for s in sig_bits))

    # ── Score demoted into an expander (no longer the headline) ──
    scores = res.get("scores", {})
    with st.expander(
        f"維度分數 Dim 6:{res.get('total_score', 0)} / {res.get('max_possible', 11)}(免費上限)",
        expanded=False,
    ):
        score_rows = [
            ("6a 異常 call 活動", scores.get("6a_unusual_call", 0), 8),
            ("6b Sweeps/Blocks", scores.get("6b_sweeps_blocks", 0), 6),
            ("6c 暗池", scores.get("6c_dark_pool", 0), 3),
            ("6d GEX/Gamma", scores.get("6d_gex_gamma", 0), 3),
        ]
        st.dataframe(
            pd.DataFrame(score_rows, columns=["子維度", "分數", "滿分(免費上限)"]),
            hide_index=True, use_container_width=True,
        )
        st.caption(f"GEX regime proxy:`{d6d.get('gex_regime', '?')}`")

    missing = res.get("data_missing", [])
    if missing:
        st.caption(
            f"⚠️ 免費資料缺口:{', '.join(missing)}。"
            f"Sweeps / 暗池 / 買賣方向需 Unusual Whales 付費資料。"
        )


def render() -> None:
    st.header("🧮 美股期權分析")
    st.caption(
        "免費 yfinance 期權鏈,涵蓋 Dim 6a(異常 call)+ 6d(GEX proxy);"
        "上限約 11/20 分,Sweeps/暗池需 Unusual Whales。"
    )

    tab_ticker, tab_rank = st.tabs(["個股期權", "當日候選排行"])

    with tab_ticker:
        _render_per_ticker()

    with tab_rank:
        df = _candidate_grid()
        if df is None:
            st.info("尚無 `scored_candidates.json`,請先執行管線。")
        else:
            st.caption("當日候選分流:依 判定 → IV-Rank 排序(可點欄位重排)。"
                       "IV-Rank / 走勢來自 iv_history(僅種子代號 NVDA/AMD/TSLA/ARM/MU 有真值,其餘累積中、留空)。")
            st.dataframe(
                df, hide_index=True, use_container_width=True,
                column_config={
                    "判定": st.column_config.TextColumn("判定", width="small"),
                    "代號": st.column_config.TextColumn("代號", width="small"),
                    "綜合": st.column_config.NumberColumn("綜合", format="%d"),
                    "選擇權流": st.column_config.NumberColumn(
                        "選擇權流", format="%d", help="Dim 6 options_flow 分數"),
                    "IV-Rank": st.column_config.ProgressColumn(
                        "IV-Rank", min_value=0, max_value=100, format="%d",
                        help="iv_history 52週 IV Rank;留空 = 快照累積中"),
                    "IV(近30)": st.column_config.LineChartColumn(
                        "IV(近30)", y_min=0, help="近 30 日 ATM IV(%)走勢"),
                },
            )
