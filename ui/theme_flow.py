"""美股 · 主題資金流 (Theme Money-Flow).

A US-side port of the Taiwan 法人資金流 rotation idea, over ~35 NARROW theme
baskets (HBM / CoWoS / 矽光子 / 液冷 / 客製 ASIC …). The TW market has free
per-stock institutional net-buy data; the US does NOT — so the "flow" here is a
price×volume PROXY (Chaikin money-flow dollars), labelled honestly everywhere as
such, never real 法人/主力買賣超 (the same honesty rule as 選擇權異常流).

Verified numbers come from scripts/theme_flow.py; this page only displays them.
Three tabs: the flow bubble chart ⇄ leaderboard (X=近5日淨流向, Y=流向加速, size=
近20日累計, centred at 0), the 抄底偵測 + LLM 研判 (reports/theme_flow.json), and a
per-theme detail panel with 代表股 drill-through into 個股總覽. Complements the
broad price-RRG 熱錢板塊輪動 page (each theme shows its parent SPDR-sector quadrant).
"""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

# Honest proxy capital-state → semantic colour (matches scripts/theme_flow STATES).
_STATE_COLOR = {
    "加速流入(推估)": _shared.GREEN, "流入趨緩": _shared.AMBER,
    "中性": _shared.MUTED, "流出(推估)": _shared.RED,
}
_BOTTOM_RING = _shared.PURPLE   # 抄底 outline — distinct from the 4 state colours
_LABEL_COLOR = "#d6dae3"

# Chinese quadrant names for the parent SPDR-sector bridge (mirrors sector_flow).
_QUAD_ZH = {"Leading": "領漲", "Weakening": "轉弱", "Lagging": "落後", "Improving": "醞釀"}

_PROXY_CAVEAT = (
    "資金流為「價量推斷 proxy」,非真實法人/主力買賣超。以 Chaikin 資金流向係數"
    "(收盤在當日高低區間的位置)× 成交額 估算買賣壓力;免費 OHLCV 看不到真正買賣方/大單。"
    "X=近5日淨流向、Y=流向加速、泡泡大小=近20日累計,皆為方向性參考。"
)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r,g,b,a) (plotly rejects 8-digit hex for trace colours)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_dollar(v) -> str:
    """Compact signed $M/$B for hover/detail."""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:+.1f}B"
    if a >= 1e6:
        return f"{v/1e6:+.0f}M"
    return f"{v:+.0f}"


_INFLOW_STATES = ("加速流入(推估)", "流入趨緩")
_OUTFLOW_STATE = "流出(推估)"


def _annotate_insider(themes: list[dict], insider: dict | None) -> None:
    """Merge the REAL Form-4 insider net-buy ($, 6-month) overlay onto each theme row
    and flag proxy-vs-insider divergences: insiders BUYING against an outflowing tape
    = bullish; SELLING into an inflowing one = bearish. The most informative cells."""
    by = (insider or {}).get("by_theme", {})
    for r in themes:
        ins = by.get(r["theme"]) or {}
        usd = ins.get("insider_net_usd")
        r["_ins_usd"] = usd
        r["_ins_n"] = f"{ins.get('n_buy', 0)}買/{ins.get('n_sell', 0)}賣" if ins else ""
        div = ""
        if usd is not None:
            if usd > 0 and r["capital_state"] == _OUTFLOW_STATE:
                div = "內部人逆勢買"
            elif usd < 0 and r["capital_state"] in _INFLOW_STATES:
                div = "內部人逆勢賣"
        r["_ins_div"] = div


def _parent_quadrants(themes: list[dict]) -> dict[str, str]:
    """{theme_name: '板塊 領漲, …'} — the 板塊→主題 bridge.

    Look up each basket's curated parent_sector_etfs in the existing sector RRG
    summary (rotation_summary().by_etf is 11-SPDR-only). Fail-soft: any miss → ''
    so the bridge is a bonus badge, never a crash."""
    try:
        from scripts import sector_flow
        summ = sector_flow.rotation_summary() or {}
        by_etf = summ.get("by_etf") or {}
    except Exception:
        by_etf = {}
    out = {}
    for r in themes:
        parts = []
        for etf in r.get("parent_sector_etfs") or []:
            info = by_etf.get(etf)
            if info:
                parts.append(f"{etf} {info.get('quadrant_zh', '')}".strip())
            else:
                parts.append(etf)
        out[r["theme"]] = " · ".join(parts)
    return out


def _render_bubble(themes: list[dict]) -> None:
    """Flow bubble chart: X=flow_5d_norm, Y=accel_norm, centred at 0; size=20d; colour=state."""
    pts = [r for r in themes if r.get("accel_norm") is not None]
    if not pts:
        st.info("無足夠資料繪製氣泡圖")
        return
    xs = [r["flow_5d_norm"] for r in pts]
    ys = [r["accel_norm"] for r in pts]
    xpad = max(0.05, (max(xs) - min(xs)) * 0.15)
    ypad = max(0.02, (max(ys) - min(ys)) * 0.15)
    xr = [min(xs) - xpad, max(xs) + xpad]
    yr = [min(ys) - ypad, max(ys) + ypad]

    fig = go.Figure()
    # Quadrant tints (flow on X, acceleration on Y), drawn first.
    quad_bg = [
        (0, xr[1], 0, yr[1], _shared.GREEN),   # 流入+加速 (top-right)
        (0, xr[1], yr[0], 0, _shared.AMBER),   # 流入+趨緩 (bottom-right)
        (xr[0], 0, yr[0], 0, _shared.RED),     # 流出+加速 (bottom-left)
        (xr[0], 0, 0, yr[1], _shared.LOSS),    # 流出+回升 (top-left)
    ]
    for x0, x1, y0, y1, color in quad_bg:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=_hex_to_rgba(color, 0.06), line=dict(width=0), layer="below")

    # Bubble size from |flow_20d_norm| (same normalisation as the axes → consistent).
    f20 = [abs(r["flow_20d_norm"]) for r in pts]
    fmax = max(f20) or 1.0
    label_cut = sorted((r.get("heat_score") or 0 for r in pts), reverse=True)
    cut = label_cut[min(14, len(label_cut) - 1)] if label_cut else 0  # label top ~15 by heat

    for r in pts:
        color = _STATE_COLOR.get(r["capital_state"], _shared.MUTED)
        size = 12 + 30 * math.sqrt(abs(r["flow_20d_norm"]) / fmax)
        ring = _BOTTOM_RING if r.get("bottom_fishing") else "white"
        ring_w = 2.6 if r.get("bottom_fishing") else 1
        show_label = (r.get("heat_score") or 0) >= cut
        name = r["theme"].split(" / ")[0].split(" ")[0]
        textpos = "top left" if r["flow_5d_norm"] > 0 else "top right"
        fig.add_trace(go.Scatter(
            x=[r["flow_5d_norm"]], y=[r["accel_norm"]],
            mode="markers+text" if show_label else "markers",
            marker=dict(size=size, color=_hex_to_rgba(color, 0.75),
                        line=dict(color=ring, width=ring_w)),
            text=[name] if show_label else None, textposition=textpos,
            textfont=dict(size=9, color=_LABEL_COLOR),
            customdata=[[r["theme"], r["capital_state"],
                         _fmt_dollar(r.get("flow_5d")), _fmt_dollar(r.get("accel")),
                         _fmt_dollar(r.get("flow_20d")), r.get("ret_5d"),
                         ",".join(x["ticker"] for x in r["reps"]),
                         "是" if r.get("bottom_fishing") else "否"]],
            hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                           "近5日淨流向: %{customdata[2]} · 加速: %{customdata[3]}<br>"
                           "近20日累計: %{customdata[4]} · 5日漲跌: %{customdata[5]}%<br>"
                           "代表股: %{customdata[6]} · 抄底: %{customdata[7]}<extra></extra>"),
            showlegend=False))

    fig.add_vline(x=0, line_dash="dash", line_color=_shared.MUTED, line_width=1, opacity=0.6)
    fig.add_hline(y=0, line_dash="dash", line_color=_shared.MUTED, line_width=1, opacity=0.6)
    for x, y, txt, color in [
        (xr[1], yr[1], "流入 + 加速 ⭐", _shared.GREEN),
        (xr[1], yr[0], "流入 + 趨緩", _shared.AMBER),
        (xr[0], yr[0], "流出 + 加速", _shared.RED),
        (xr[0], yr[1], "流出 + 回升", _shared.LOSS)]:
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                           xanchor="right" if x == xr[1] else "left",
                           yanchor="top" if y == yr[1] else "bottom",
                           font=dict(color=color, size=12))
    # State-colour + 抄底-ring legend via synthetic traces.
    for state, color in _STATE_COLOR.items():
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                      marker=dict(size=10, color=_hex_to_rgba(color, 0.75),
                                  line=dict(color="white", width=1)),
                      name=state, showlegend=True))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                  marker=dict(size=10, color="rgba(0,0,0,0)",
                              line=dict(color=_BOTTOM_RING, width=2.6)),
                  name="🪝 抄底(跌勢仍流入)", showlegend=True))

    fig.update_layout(
        height=580, margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.PANEL,
        font=dict(color=_LABEL_COLOR), showlegend=True,
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)",
                    font=dict(color=_LABEL_COLOR, size=10)),
        xaxis=dict(title="近5日淨流向 (×日均成交額 · >0 推估流入)", range=xr,
                   showgrid=False, zeroline=False),
        yaxis=dict(title="流向加速 (×日均成交額 · >0 加速)", range=yr,
                   showgrid=False, zeroline=False))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("泡泡位置=近5日淨流向×加速;大小=近20日累計(√面積,皆以日均成交額正規化)。"
               "顏色=資金狀態,紫圈=抄底。僅標示熱度前段主題以免擁擠。"
               "⚠ 共用龍頭的主題非獨立訊號(見下方排行)。")


def _style_state(col: pd.Series) -> list[str]:
    return [f"color:{_STATE_COLOR.get(v, _shared.MUTED)}" for v in col]


def _render_leaderboard(themes: list[dict], parents: dict[str, str]) -> None:
    if not themes:
        st.info("無主題資料")
        return
    has_ins = any(r.get("_ins_usd") is not None for r in themes)
    rows = []
    for r in themes:
        row = {
            "主題": r["theme"], "狀態": r["capital_state"], "熱度": r.get("heat_score"),
            "5d淨流向×額": r["flow_5d_norm"], "加速×額": r.get("accel_norm"),
            "20d累計×額": r["flow_20d_norm"], "5d%": r.get("ret_5d"),
            "集中度": r.get("top_share"), "覆蓋": f"{r['n_used']}/{r['n_total']}",
            "代表股": ",".join(x["ticker"] for x in r["reps"]),
            "母板塊": parents.get(r["theme"], "") or "—",
        }
        if has_ins:
            usd = r.get("_ins_usd")
            row["內部人6M淨買$M"] = round(usd / 1e6, 0) if usd is not None else None
            row["背離"] = r.get("_ins_div") or ""
        rows.append(row)
    df = pd.DataFrame(rows)
    styled = df.style.apply(_style_state, subset=["狀態"])
    col_cfg = {
        "主題": st.column_config.TextColumn("主題", width="medium"),
        "狀態": st.column_config.TextColumn("資金狀態(推估)", width="small"),
        "熱度": st.column_config.ProgressColumn("熱度", min_value=0, max_value=100,
                                              format="%d", help="跨主題相對熱度 0-100"),
        "5d淨流向×額": st.column_config.NumberColumn("5d淨流向×額", format="%.2f",
                                                 help="近5日淨流向 ÷ 籃子日均成交額(>0 推估流入)"),
        "加速×額": st.column_config.NumberColumn("加速×額", format="%.2f",
                                              help="流向加速 ÷ 日均成交額(>0 加速)"),
        "20d累計×額": st.column_config.NumberColumn("20d累計×額", format="%.2f",
                                                help="近20日累計 ÷ 日均成交額"),
        "5d%": st.column_config.NumberColumn("5d%", format="%.1f%%", help="籃子近5日漲跌(額加權)"),
        "集中度": st.column_config.NumberColumn("集中度", format="%.2f",
                                             help="最大單一成分股佔比;≥0.6 表一檔即主導該主題"),
        "覆蓋": st.column_config.TextColumn("覆蓋", width="small", help="實際採用 / 籃子總數"),
        "代表股": st.column_config.TextColumn("代表股", width="small"),
        "母板塊": st.column_config.TextColumn("母板塊(RRG象限)", width="small"),
    }
    if has_ins:
        col_cfg["內部人6M淨買$M"] = st.column_config.NumberColumn(
            "內部人6M淨買$M", format="%.0f",
            help="REAL Form-4 內部人近 6 個月淨買賣金額($M);綠正紅負。真實但平滑,非每日。")
        col_cfg["背離"] = st.column_config.TextColumn(
            "背離", width="small", help="內部人方向 vs proxy 流向相反 → 最有訊息")
    st.dataframe(styled, hide_index=True, use_container_width=True, column_config=col_cfg)
    _shared.chips_row([
        ("加速流入(推估)", _shared.GREEN), ("流入趨緩", _shared.AMBER),
        ("中性", _shared.MUTED), ("流出(推估)", _shared.RED), ("🪝 抄底", _shared.PURPLE),
    ])
    st.caption("依熱度排序。流向為價量推斷 proxy,非真實法人買賣超。"
               "集中度高/覆蓋低的主題請審慎看待。")


def _render_bottom_and_read(flow: dict) -> None:
    themes = flow["themes"]
    bf = [r for r in themes if r.get("bottom_fishing")]
    st.markdown("**🪝 抄底偵測 — 近5日下跌但資金(推估)仍流入**")
    if bf:
        with st.container(border=True):
            _shared.chips_row([(r["theme"], _shared.PURPLE) for r in bf])
            bdf = pd.DataFrame([{
                "主題": r["theme"], "5d%": r.get("ret_5d"),
                "5d淨流向×額": r["flow_5d_norm"],
                "代表股": ",".join(x["ticker"] for x in r["reps"]),
            } for r in bf])
            st.dataframe(bdf, hide_index=True, use_container_width=True,
                         column_config={
                             "5d%": st.column_config.NumberColumn("5d%", format="%.1f%%"),
                             "5d淨流向×額": st.column_config.NumberColumn("5d淨流向×額", format="%.2f"),
                         })
    else:
        st.caption("目前無符合抄底條件(跌勢中仍推估流入)的主題。")

    st.markdown("---")
    # ── LLM 研判 (reports/theme_flow.json) ──────────────────────────────────────
    read_payload = _shared.load_json(str(_shared.REPORTS_DIR / "theme_flow.json"))
    col_btn, col_meta = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 產生 / 更新 AI 研判", help="呼叫一次 LLM,依目前主題資金流研判"):
            with st.spinner("AI 研判中…(一次 LLM 呼叫)"):
                try:
                    from scripts import theme_rotation
                    res = theme_rotation.generate_theme_flow_read()
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
        st.info("尚無 AI 研判 — 按上方按鈕產生(會花一次 LLM 呼叫)。")
        return
    r = read_payload.get("read") or {}
    conf = r.get("confidence", "—")
    conf_color = {"high": _shared.GREEN, "medium": _shared.AMBER,
                  "low": _shared.RED}.get(conf, _shared.MUTED)
    if r.get("headline"):
        st.markdown(f"### {r['headline']}")
    _shared.chips_row([(f"信心 {conf}", conf_color)])

    def _items(key):
        v = r.get(key)
        return [h for h in v if isinstance(h, dict)] if isinstance(v, list) else []

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 推估資金加速流入**")
        for h in _items("accelerating_in"):
            st.markdown(f"- **{h.get('theme', '')}** {h.get('name', '')} — {h.get('why', '')}")
    with c2:
        st.markdown("**🔴 推估資金流出**")
        for h in _items("rotating_out"):
            st.markdown(f"- **{h.get('theme', '')}** {h.get('name', '')} — {h.get('why', '')}")
    bf_read = _items("bottom_fishing")
    if bf_read:
        st.markdown("**🪝 抄底候選(跌勢中推估流入)**")
        for h in bf_read:
            st.markdown(f"- **{h.get('theme', '')}** {h.get('name', '')} — {h.get('why', '')}")
    ins_div = _items("insider_divergence")
    if ins_div:
        st.markdown("**🏛 內部人 vs proxy 背離(真實 Form 4,6 個月)**")
        for h in ins_div:
            st.markdown(f"- **{h.get('theme', '')}** {h.get('name', '')} — {h.get('why', '')}")
    if r.get("next_thesis"):
        st.markdown("**下一波研判**")
        with st.container(border=True):
            st.markdown(r["next_thesis"])
    for cav in (r.get("caveats") if isinstance(r.get("caveats"), list) else []):
        st.caption(f"⚠️ {cav}")


def _render_detail(themes: list[dict], parents: dict[str, str]) -> None:
    names = [r["theme"] for r in themes]
    if not names:
        st.info("無主題資料")
        return
    picked = st.selectbox("選擇主題", names, index=0)
    r = next((x for x in themes if x["theme"] == picked), None)
    if not r:
        return
    if r.get("desc"):
        st.caption(r["desc"])
    par = parents.get(picked)
    if par:
        st.caption(f"母板塊 (RRG):{par}")
    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "資金狀態(推估)", r["capital_state"])
    _shared.metric_card(c2, "近5日淨流向", _fmt_dollar(r.get("flow_5d")),
                        help="價量推斷,非真實買賣超")
    _shared.metric_card(c3, "近20日累計", _fmt_dollar(r.get("flow_20d")))
    _shared.metric_card(c4, "近5日漲跌", f"{r.get('ret_5d')}%" if r.get("ret_5d") is not None else "—")
    if r.get("high_concentration"):
        st.caption(f"⚠ 集中度 {r.get('top_share')} — 單一成分股即主導此主題,訊號非分散。")
    if r.get("_ins_usd") is not None:
        st.caption(f"🏛 內部人 6 個月淨買(真實 Form 4):**{_fmt_dollar(r['_ins_usd'])}** "
                   f"({r.get('_ins_n', '')})"
                   + (f" · ⚠ **{r['_ins_div']}**(與 proxy 流向背離)" if r.get("_ins_div") else "")
                   + " — 真實但 6 個月平滑、非每日。")

    st.markdown("**代表股(依近20日累計流向)— 點擊看個股總覽**")
    cols = st.columns(min(3, len(r["reps"])) or 1)
    for i, rep in enumerate(r["reps"]):
        with cols[i % len(cols)]:
            tkr = rep["ticker"]
            if st.button(f"🔍 {tkr}", key=f"tf_rep_{picked}_{tkr}",
                         help=f"設為個股總覽標的 · 近20日累計 {_fmt_dollar(rep.get('flow_20d'))}"):
                st.session_state["checkup_ticker"] = tkr
            st.caption(f"20d {_fmt_dollar(rep.get('flow_20d'))} · 5d {rep.get('ret_5d')}%")
    sel = st.session_state.get("checkup_ticker")
    st.markdown(f"[→ 在個股總覽看 {sel} 的暴漲因子 + 機構](/stock-checkup)" if sel
                else "[→ 在個股總覽查個股](/stock-checkup)")


def render() -> None:
    st.header("💧 主題資金流")
    st.caption("窄主題資金流(價量推斷 proxy):X=近5日淨流向、Y=流向加速、泡泡大小=近20日累計。"
               "決策參考,非投資建議。")
    st.info("ℹ️ " + _PROXY_CAVEAT)
    st.caption("這是「熱錢板塊輪動」(寬板塊·價格 RRG)的主題層放大版 → "
               "[看板塊層級](/sector-rotation)。")

    flow = _shared.load_theme_flow()
    if not flow or not flow.get("themes"):
        st.info("無法取得主題資金流資料(來源暫時無回應,稍後再試)。")
        return
    themes = flow["themes"]
    st.caption(f"資料日期 {flow.get('as_of')} · 基準 {flow.get('benchmark')} · "
               f"{len(themes)} 個主題 · 下載失敗 {flow.get('n_failed_download', 0)} 檔")

    # 4-bucket capital-state summary cards.
    buckets = flow.get("buckets", {})
    cols = st.columns(4)
    for col, (state, color) in zip(cols, _STATE_COLOR.items()):
        names = buckets.get(state, [])
        top = names[0] if names else "—"
        _shared.metric_card(col, state, len(names), help=f"最強:{top}" if names else None)

    shared_caps = flow.get("shared_mega_caps") or []
    if shared_caps:
        st.caption("⚠ 跨主題共用龍頭(同一筆資金,勿當獨立訊號相加):"
                   + "、".join(f"{d['ticker']}×{d['themes']}" for d in shared_caps[:8]))

    parents = _parent_quadrants(themes)

    # Opt-in REAL Form-4 insider overlay (default off → core board stays fast).
    show_insider = st.toggle(
        "🏛 疊上內部人 Form 4 淨買(真實,首次載入較慢)", value=False,
        help="REAL Form-4 內部人淨買賣($),非價量推估。與 proxy 流向背離最有訊息。")
    if show_insider:
        c_src, _ = st.columns([2, 3])
        with c_src:
            src_label = st.radio(
                "內部人資料來源",
                ["yfinance 6 個月(快)", "EDGAR 開盤交易・近30日(精準,首次很慢)"],
                horizontal=False, label_visibility="collapsed")
        source = "edgar" if src_label.startswith("EDGAR") else "yfinance"
        ins = _shared.load_theme_insider(source, 30)
        _annotate_insider(themes, ins)
        if source == "edgar":
            st.caption("🏛 內部人欄=**SEC EDGAR Form-4 開盤買賣(code P/S),近 30 日**——"
                       "真實、每日新鮮(~2 天),已排除授予/選擇權行使。"
                       "**背離**=內部人方向與 proxy 流向相反。")
        else:
            st.caption("🏛 內部人欄=Form 4 **近 6 個月彙總**(真實但平滑、非每日,含授予雜訊);"
                       "要每日精準請切換 EDGAR。**背離**=內部人方向與 proxy 流向相反。")
    else:
        for r in themes:
            r["_ins_usd"] = None
            r["_ins_div"] = ""

    t1, t2, t3 = st.tabs(["💧 氣泡圖 / 排行榜", "🪝 抄底 + AI 研判", "🔎 主題詳情"])
    with t1:
        ctrl1, ctrl2 = st.columns([1, 2])
        with ctrl1:
            view = st.radio("檢視", ["氣泡圖", "排行榜"], horizontal=True,
                            label_visibility="collapsed")
        with ctrl2:
            q = st.text_input("搜尋主題或代號", "", label_visibility="collapsed",
                              placeholder="🔍 搜尋主題或成分股代號…")
        shown = themes
        if q:
            ql = q.strip().upper()
            shown = [r for r in themes
                     if ql in r["theme"].upper() or ql in (r.get("desc") or "").upper()
                     or any(ql in x["ticker"] for x in r["reps"])]
            if not shown:
                st.caption(f"找不到符合「{q}」的主題(搜尋比對主題名/說明/代表股代號)。")
        if view == "氣泡圖":
            _render_bubble(shown)
        else:
            _render_leaderboard(shown, parents)
    with t2:
        _render_bottom_and_read(flow)
    with t3:
        _render_detail(themes, parents)
