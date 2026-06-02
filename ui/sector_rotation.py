"""美股 · 熱錢板塊輪動 (Sector Money-Flow / Rotation).

Visualises where hot money is now and where it rotates next, from the verified
RRG data in scripts/sector_flow.py (RS-Ratio × RS-Momentum, 4 quadrants). Three
tabs: the RRG scatter (with rotation tails), a heat ranking table, and the LLM
rotation read (reports/sector_rotation.json) + which scored candidates sit in the
hot / improving sectors. Verified-data-to-AI: code computes, the page displays.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

# Quadrant → semantic colour (Leading 領漲 / Weakening 轉弱 / Lagging 落後 / Improving 醞釀).
_QUAD_COLOR = {
    "Leading": _shared.GREEN, "Weakening": _shared.AMBER,
    "Lagging": _shared.RED, "Improving": _shared.CYAN,
}
_QUAD_ZH = {"Leading": "領漲", "Weakening": "轉弱", "Lagging": "落後", "Improving": "醞釀"}

# Label colour for chart text annotations — lighter than MUTED so ticker labels
# are legible against the dark panel background without being primary-text weight.
_LABEL_COLOR = "#d6dae3"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r,g,b,a) (plotly rejects 8-digit hex for trace colours)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _render_rrg(sectors: list[dict], show_tails: bool) -> None:
    """RRG scatter: RS-Ratio (x) vs RS-Momentum (y), centred at 100, 4 quadrants."""
    if not sectors:
        st.info("無板塊資料")
        return

    # Axis ranges from all points (heads + tails), padded, centred on 100.
    xs, ys = [], []
    for s in sectors:
        xs.append(s["rs_ratio"]); ys.append(s["rs_momentum"])
        for p in s.get("tail", []):
            xs.append(p["rs_ratio"]); ys.append(p["rs_momentum"])
    xpad = max(0.5, (max(xs) - min(xs)) * 0.12)
    ypad = max(0.5, (max(ys) - min(ys)) * 0.12)
    xr = [min(xs) - xpad, max(xs) + xpad]
    yr = [min(ys) - ypad, max(ys) + ypad]

    fig = go.Figure()

    # Quadrant background tints (subtle), drawn first.
    quad_bg = [
        (100, xr[1], 100, yr[1], _shared.GREEN),   # Leading  (top-right)
        (100, xr[1], yr[0], 100, _shared.AMBER),   # Weakening(bottom-right)
        (xr[0], 100, yr[0], 100, _shared.RED),     # Lagging  (bottom-left)
        (xr[0], 100, 100, yr[1], _shared.CYAN),    # Improving(top-left)
    ]
    for x0, x1, y0, y1, color in quad_bg:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=_hex_to_rgba(color, 0.06), line=dict(width=0), layer="below")

    # Rotation tails (thin, faint, quadrant-coloured) + heads (labelled markers).
    # Use smaller font when many sectors to reduce label noise.
    label_size = 9 if len(sectors) > 14 else 10
    for s in sectors:
        color = _QUAD_COLOR.get(s["quadrant"], _shared.MUTED)
        tail = s.get("tail", [])
        if show_tails and len(tail) >= 2:
            fig.add_trace(go.Scatter(
                x=[p["rs_ratio"] for p in tail], y=[p["rs_momentum"] for p in tail],
                mode="lines", line=dict(color=_hex_to_rgba(color, 0.45), width=1.5),
                hoverinfo="skip", showlegend=False))
        symbol = "circle" if s["group"] == "主板塊" else "diamond"
        theme = f" · {s['theme']}" if s.get("theme") else ""
        # Spread labels away from quadrant corners: high RS-Ratio → left, low → right.
        textpos = "top left" if s["rs_ratio"] > 101 else "top right"
        fig.add_trace(go.Scatter(
            x=[s["rs_ratio"]], y=[s["rs_momentum"]], mode="markers+text",
            marker=dict(size=14, color=color, symbol=symbol,
                        line=dict(color="white", width=1)),
            text=[s["etf"]], textposition=textpos,
            textfont=dict(size=label_size, color=_LABEL_COLOR),
            customdata=[[s["name_zh"], s["quadrant_zh"], theme,
                         s.get("ret_20d"), s.get("excess_20d")]],
            hovertemplate=("<b>%{text}</b> %{customdata[0]}%{customdata[2]}<br>"
                           "象限: %{customdata[1]}<br>"
                           "RS-Ratio: %{x:.2f} · RS-Mom: %{y:.2f}<br>"
                           "20d: %{customdata[3]}% · 超額: %{customdata[4]}%<extra></extra>"),
            showlegend=False))

    fig.add_vline(x=100, line_dash="dash", line_color=_shared.MUTED, line_width=1, opacity=0.6)
    fig.add_hline(y=100, line_dash="dash", line_color=_shared.MUTED, line_width=1, opacity=0.6)
    # Corner quadrant labels.
    for x, y, txt, color in [
        (xr[1], yr[1], "領漲 Leading", _shared.GREEN),
        (xr[1], yr[0], "轉弱 Weakening", _shared.AMBER),
        (xr[0], yr[0], "落後 Lagging", _shared.RED),
        (xr[0], yr[1], "醞釀 Improving", _shared.CYAN)]:
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                           xanchor="right" if x == xr[1] else "left",
                           yanchor="top" if y == yr[1] else "bottom",
                           font=dict(color=color, size=12))

    # Synthetic legend traces so the chart is self-explanatory without the caption.
    for sym, label in [("circle", "主板塊"), ("diamond", "主題/產業")]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=_LABEL_COLOR, symbol=sym,
                        line=dict(color="white", width=1)),
            name=label, showlegend=True))

    fig.update_layout(
        height=560, margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.PANEL,
        font=dict(color=_LABEL_COLOR),
        showlegend=True,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)",
                    font=dict(color=_LABEL_COLOR, size=11)),
        xaxis=dict(title="RS-Ratio (相對 SPY 強度 · >100 領先)", range=xr,
                   showgrid=False, zeroline=False),
        yaxis=dict(title="RS-Momentum (動能 · >100 加速)", range=yr,
                   showgrid=False, zeroline=False))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("順時針輪動:醞釀→領漲→轉弱→落後。尾巴=近 8 個交易週軌跡。")


def _style_quadrant(col: pd.Series) -> list[str]:
    return [f"color:{_QUAD_COLOR.get(_ZH_QUAD.get(v, ''), _shared.MUTED)}" for v in col]


_ZH_QUAD = {v: k for k, v in _QUAD_ZH.items()}


def _render_heat_table(sectors: list[dict]) -> None:
    if not sectors:
        st.info("無板塊資料")
        return
    df = pd.DataFrame([{
        "板塊": s["name_zh"], "代號": s["etf"], "分組": s["group"],
        "主題": s.get("theme") or "—", "象限": s["quadrant_zh"],
        "RS-Ratio": s["rs_ratio"], "RS-Mom": s["rs_momentum"],
        "熱度": s.get("heat_score"),
        "5d%": s.get("ret_5d"), "20d%": s.get("ret_20d"),
        "超額20d%": s.get("excess_20d"), "%vs50MA": s.get("pct_vs_ma50"),
        "rvol": s.get("rvol"),
    } for s in sectors])
    styled = df.style.apply(_style_quadrant, subset=["象限"])
    st.dataframe(
        styled, hide_index=True, use_container_width=True,
        column_config={
            "板塊": st.column_config.TextColumn("板塊", width="small"),
            "代號": st.column_config.TextColumn("代號", width="small"),
            "分組": st.column_config.TextColumn("分組", width="small"),
            "主題": st.column_config.TextColumn("主題標籤", width="small"),
            "象限": st.column_config.TextColumn("象限", width="small"),
            "RS-Ratio": st.column_config.NumberColumn("RS-Ratio", format="%.1f",
                                                      help=">100 = 相對 SPY 領先"),
            "RS-Mom": st.column_config.NumberColumn("RS-Mom", format="%.1f",
                                                    help=">100 = 強度在加速"),
            "熱度": st.column_config.ProgressColumn("熱度", min_value=0, max_value=100,
                                                  format="%d", help="跨板塊相對熱度 0-100"),
            "5d%": st.column_config.NumberColumn("5d%", format="%.1f%%"),
            "20d%": st.column_config.NumberColumn("20d%", format="%.1f%%"),
            "超額20d%": st.column_config.NumberColumn("超額20d%", format="%.1f%%",
                                                    help="減 SPY 同期報酬"),
            "%vs50MA": st.column_config.NumberColumn("%vs50MA", format="%.1f%%"),
            "rvol": st.column_config.NumberColumn("rvol", format="%.2f",
                                                  help="當日量 / 20 日均量"),
        },
    )
    # Legend uses chip() swatches so colours match the chart quadrant tokens exactly.
    _shared.chips_row([
        ("領漲", _shared.GREEN), ("醞釀", _shared.CYAN),
        ("轉弱", _shared.AMBER), ("落後", _shared.RED),
    ])
    st.caption("依熱度排序。免費 yfinance,純 numpy,1 小時快取。"
               "註:主題 ETF(半導體 SMH/SOXX、軟體 IGV)與主板塊 XLK 持股重疊,"
               "同熱時視為同一筆資金,勿當成獨立訊號相加。")


def _render_read_and_candidates(flow: dict) -> None:
    read_payload = _shared.load_json(str(_shared.REPORTS_DIR / "sector_rotation.json"))

    col_btn, col_meta = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 產生 / 更新 AI 研判", help="呼叫一次 LLM,依目前板塊數據研判輪動"):
            with st.spinner("AI 研判中…(一次 LLM 呼叫)"):
                try:
                    from scripts import sector_rotation
                    # generate_rotation_read never raises — it returns a status dict;
                    # only rerun on success so failures surface instead of silently looping.
                    res = sector_rotation.generate_rotation_read()
                    if res.get("status") == "ready":
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"研判失敗:{res.get('error') or res.get('status')}")
                except Exception as e:  # noqa: BLE001
                    st.error(f"研判失敗:{e}")
    with col_meta:
        if read_payload and read_payload.get("status") == "ready":
            st.caption(f"研判時間 {str(read_payload.get('generated_at', ''))[:16]} · "
                       f"資料 {read_payload.get('as_of')}")

    if not read_payload or read_payload.get("status") != "ready":
        st.info("尚無 AI 研判 — 按上方按鈕產生(會花一次 LLM 呼叫)。下方仍可看候選股對應板塊。")
    else:
        r = read_payload.get("read") or {}
        conf = r.get("confidence", "—")
        conf_color = {"high": _shared.GREEN, "medium": _shared.AMBER,
                      "low": _shared.RED}.get(conf, _shared.MUTED)
        if r.get("headline"):
            st.markdown(f"### {r['headline']}")
        _shared.chips_row([(f"信心 {conf}", conf_color)])
        def _items(key):  # tolerate a malformed/stale payload: keep only dict rows
            v = r.get(key)
            return [h for h in v if isinstance(h, dict)] if isinstance(v, list) else []

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🟢 現在熱錢在哪**")
            for h in _items("hot_now"):
                st.markdown(f"- **{h.get('etf','')}** {h.get('name','')} — {h.get('why','')}")
        with c2:
            st.markdown("**🔵 下一波輪動進入**")
            for h in _items("rotating_into"):
                st.markdown(f"- **{h.get('etf','')}** {h.get('name','')} — {h.get('why','')}")
        if r.get("next_rotation_thesis"):
            st.markdown("**下一波研判**")
            with st.container(border=True):
                st.markdown(r["next_rotation_thesis"])
        if r.get("cycle_read"):
            st.caption(f"景氣循環研判:{r['cycle_read']}")
        caveats = r.get("caveats")
        for cav in (caveats if isinstance(caveats, list) else []):
            st.caption(f"⚠️ {cav}")

    # ── Candidate → sector mapping (highlight those in hot / improving sectors) ──
    st.markdown("---")
    st.markdown("**🎯 候選股對應板塊**")
    scored = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json"))
    cands = []
    if scored:
        all_s = scored.get("all_scored")
        cands = all_s if isinstance(all_s, list) else (
            (scored.get("needs_layer2") or []) + (scored.get("watchlist") or []))
    if not cands:
        st.info("尚無評分候選股 — 需先由「暴漲股篩選器」管線產生 scored_candidates.json。"
                "(本頁的板塊輪動圖/熱度不受影響,仍可查看。)")
        return

    by_etf = {s["etf"]: s for s in flow.get("sectors", [])}

    # Pre-build rows; ticker_sector_etf is per-ticker @st.cache_data(ttl=21600)
    # so subsequent reruns are instant. Show progress only on genuinely slow paths.
    tickers = [c.get("ticker") for c in cands if c.get("ticker")]
    unique_tickers = list(dict.fromkeys(tickers))  # deduplicate, preserve order

    with st.status("對應板塊中…", expanded=False) as status:
        rows = []
        for i, c in enumerate(cands):
            t = c.get("ticker")
            if not t:
                continue
            etf = _shared.ticker_sector_etf(t)
            sec = by_etf.get(etf) if etf else None
            rows.append({
                "代號": t,
                "判定": c.get("verdict", "?"),
                "板塊": (sec["name_zh"] if sec else "—"),
                "板塊象限": (sec["quadrant_zh"] if sec else "—"),
                "板塊熱度": (sec.get("heat_score") if sec else None),
                "_hot": bool(sec and sec["quadrant"] in ("Leading", "Improving")),
            })
        status.update(label=f"對應完成 ({len(rows)} 檔)", state="complete", expanded=False)

    if not rows:  # candidates existed but none carried a ticker
        st.caption("候選股缺少代號,無法對應板塊。")
        return
    cdf = pd.DataFrame(rows).sort_values(
        ["_hot", "板塊熱度"], ascending=[False, False], na_position="last")
    hot_n = int(cdf["_hot"].sum())
    st.caption(f"{hot_n}/{len(cdf)} 檔候選股落在領漲/醞釀板塊。")

    def _style_hot(col):  # index-aligned (not positional) so it's robust to reordering
        return ["color:" + (_shared.GREEN if cdf.loc[i, "_hot"] else _shared.MUTED)
                for i in col.index]

    def _style_verdict(col):
        return [f"color:{_shared.verdict_color(v)}" for v in col]

    show = cdf.drop(columns=["_hot"])
    st.dataframe(
        show.style.apply(_style_hot, subset=["板塊"]).apply(_style_verdict, subset=["判定"]),
        hide_index=True, use_container_width=True,
        column_config={
            "代號": st.column_config.TextColumn("代號", width="small"),
            "判定": st.column_config.TextColumn("判定", width="small"),
            "板塊": st.column_config.TextColumn("板塊", width="small"),
            "板塊象限": st.column_config.TextColumn("板塊象限", width="small"),
            "板塊熱度": st.column_config.ProgressColumn("板塊熱度", min_value=0,
                                                     max_value=100, format="%d"),
        },
    )


def render() -> None:
    st.header("🔄 熱錢板塊輪動")
    st.caption("板塊相對強度旋轉 (RRG):X=RS-Ratio 相對 SPY 強度、Y=RS-Momentum 動能。"
               "免費 yfinance,純 numpy。決策參考,非投資建議。")

    # load_sector_flow is @st.cache_data(ttl=3600, show_spinner=False) — no spinner
    # needed on rerun; it returns from memory instantly after the first call.
    flow = _shared.load_sector_flow()
    if not flow or not flow.get("sectors"):
        st.info("無法取得板塊資料(來源暫時無回應,稍後再試)。")
        return
    sectors = flow["sectors"]
    st.caption(f"資料日期 {flow.get('as_of')} · 基準 {flow.get('benchmark')} · "
               f"{len(sectors)} 個板塊/主題")

    leaders = [s for s in sectors if s["quadrant"] == "Leading"]
    improving = [s for s in sectors if s["quadrant"] == "Improving"]
    chips = [(f"領漲 {s['etf']} {s['name_zh']}", _shared.GREEN) for s in leaders[:6]]
    chips += [(f"醞釀 {s['etf']} {s['name_zh']}", _shared.CYAN) for s in improving[:6]]
    if chips:
        _shared.chips_row(chips)

    t1, t2, t3 = st.tabs(["📈 四象限旋轉圖 (RRG)", "🔥 熱度排行", "🧭 輪動研判 + 候選股"])
    with t1:
        # Controls inline (single row) to minimise vertical dead space before chart.
        ctrl1, ctrl2, ctrl3 = st.columns([1, 2, 2])
        with ctrl1:
            show_tails = st.checkbox("顯示輪動軌跡 (尾巴)", value=False,
                                     help="勾選顯示每個板塊近 8 週的旋轉軌跡;板塊多時建議搭配「只主板塊」")
        with ctrl2:
            group = st.radio("顯示", ["全部", "只主板塊", "只主題"], horizontal=True,
                             label_visibility="collapsed")
        # ctrl3 intentionally left empty — acts as right-side spacer.
        view = sectors
        if group == "只主板塊":
            view = [s for s in sectors if s["group"] == "主板塊"]
        elif group == "只主題":
            view = [s for s in sectors if s["group"] == "主題"]
        _render_rrg(view, show_tails)
    with t2:
        _render_heat_table(sectors)
    with t3:
        _render_read_and_candidates(flow)
