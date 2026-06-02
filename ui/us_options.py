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


def _candidate_ranking() -> pd.DataFrame | None:
    scored = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json"))
    if not scored:
        return None
    rows = []
    for group in ("needs_layer2", "watchlist"):
        for c in scored.get(group, []):
            rows.append({
                "代號": c.get("ticker", "?"),
                "選擇權分數": c.get("scores", {}).get("options_flow", 0),
                "綜合分數": c.get("regime_adjusted_score", c.get("composite_score", 0)),
                "判定": c.get("verdict", "?"),
            })
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("選擇權分數", ascending=False)


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


def _render_per_ticker() -> None:
    from scripts import options_free  # lazy

    ticker = st.text_input("代號", value="NVDA").strip().upper()
    if not st.button("分析期權", type="primary"):
        return
    if not ticker:
        st.info("請輸入代號。")
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

    # ── Objective chart: call vs put VOLUME by strike (always reliable) ──
    chain = res.get("chain_summary", [])
    if chain:
        df = pd.DataFrame(chain)
        st.markdown("#### 成交量分佈(依履約價)")
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
        fig.update_layout(barmode="group", height=360,
                          margin=dict(l=10, r=10, t=10, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0))
        st.plotly_chart(fig, use_container_width=True)
        if not oi_ok:
            st.caption("ℹ️ 未平倉量 (OI) 暫無:免費 yfinance 盤中常回傳 0(OCC 每日收盤後才更新),故以成交量為準。")

    # ── Most active call strikes (objective, volume-ranked) ──
    top = res.get("top_active_calls", [])
    if top:
        st.markdown("#### 最活躍 call 履約價(依成交量)")
        tdf = pd.DataFrame(top).rename(columns={
            "strike": "履約價", "volume": "成交量",
            "open_interest": "未平倉", "voi": "V/OI",
        })
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
        df = _candidate_ranking()
        if df is None:
            st.info("尚無 `scored_candidates.json`,請先執行管線。")
        else:
            st.markdown("依當日 Layer 1 的選擇權維度分數排序:")
            st.dataframe(df, hide_index=True, use_container_width=True)
