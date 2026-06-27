"""美股 · 分析師評級 (Analyst Consensus).

Dedicated surface for Dimension 7 (分析師共識): sell-side ratings, price targets,
dated upgrades/downgrades, and forward estimate revisions — all free yfinance data
via scripts/analyst_free.py. Verified-data-to-AI principle: code fetches, the page
displays; nothing is guessed.

Two parts: a multi-ticker triage grid over the day's scored universe (verdict +
consensus + upside + revision momentum), and a per-ticker detail view (rating
distribution bar, price-target range, recent actions, estimate revisions). The
detail box also accepts any ad-hoc ticker — analyst views are useful standalone.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

# verdict → emoji / sort order, matching us_options.py so "colour == meaning"
# stays consistent across the 美股 pages.
_VERDICT_EMOJI = {
    "STRONG_BUY": "🟢", "BUY": "🟢", "NEEDS_LAYER_2": "🟢",
    "WATCHLIST": "🟡", "WATCH": "🟡", "HOLD": "🟡",
    "REJECT": "🔴", "AVOID": "🔴",
}
_VERDICT_ORDER = {
    "STRONG_BUY": 0, "BUY": 1, "NEEDS_LAYER_2": 1, "WATCHLIST": 2,
    "WATCH": 2, "HOLD": 3, "REJECT": 5, "AVOID": 5,
}

_DIST_LABELS = [("強力買進", "strong_buy"), ("買進", "buy"), ("持有", "hold"),
                ("賣出", "sell"), ("強力賣出", "strong_sell")]
_DIST_COLORS = [_shared.GREEN, _shared.GREEN, _shared.AMBER, _shared.RED, _shared.RED]

# Human-readable action labels for yfinance raw action strings.
# Colour semantics: up/init → GREEN, down → RED, others → neutral.
_ACTION_LABEL = {
    "up": "↑ 升評",
    "down": "↓ 降評",
    "main": "維持",
    "init": "首評",
    "reit": "重申",
}
_ACTION_BG = {
    "↑ 升評": _shared.GREEN,
    "首評": _shared.GREEN,
    "↓ 降評": _shared.RED,
}


def _net_revision(data: dict) -> int | None:
    """Net EPS estimate revisions (Σ up_last_30d − down_last_30d) across periods.

    The leading sub-signal of Dimension 7 — analysts moving estimates UP ahead of
    a move. None when no revision data is present (so the grid shows blank)."""
    rev = (data or {}).get("estimate_revisions") or {}
    up = down = 0
    seen = False
    for r in rev.values():
        u, d = r.get("up_last_30d"), r.get("down_last_30d")
        if u is not None or d is not None:
            seen = True
            up += int(u or 0)
            down += int(d or 0)
    return (up - down) if seen else None


def _verdict_bg_color(verdict_str: str) -> str:
    """Map a verdict string (potentially with leading emoji) to a background hex."""
    for key, color in [
        ("STRONG_BUY", _shared.GREEN), ("BUY", _shared.GREEN),
        ("NEEDS_LAYER_2", _shared.GREEN),
        ("WATCHLIST", _shared.AMBER), ("WATCH", _shared.AMBER), ("HOLD", _shared.AMBER),
        ("REJECT", _shared.RED), ("AVOID", _shared.RED),
    ]:
        if key in verdict_str:
            return color
    return _shared.MUTED


def _style_verdict(col: pd.Series) -> list[str]:
    """Pandas Styler apply function: colour 判定 cells by verdict semantics."""
    return [f"color:{_verdict_bg_color(v)}" for v in col]


def _style_action(col: pd.Series) -> list[str]:
    """Pandas Styler apply function: colour 動作 cells green/red by action type."""
    styles = []
    for v in col:
        c = _ACTION_BG.get(str(v), "")
        styles.append(f"color:{c}" if c else "")
    return styles


def _grid_rows(cands: list[dict]) -> list[dict]:
    """Build triage-grid rows from scored candidates, one live analyst fetch each."""
    rows = []
    for c in cands:
        t = c.get("ticker")
        if not t:
            continue
        data = _shared.load_analyst_views(t)
        cons = (data or {}).get("consensus") or {}
        pt = (data or {}).get("price_targets") or {}
        verdict = c.get("verdict", "?")
        rec = cons.get("recommendation")
        net = _net_revision(data)
        rows.append({
            "判定": f"{_VERDICT_EMOJI.get(verdict, '⚪')} {verdict}",
            "代號": t,
            "共識": (rec.replace("_", " ").title() if rec else "—"),
            "分析師": int(cons["num_analysts"]) if cons.get("num_analysts") is not None else None,
            "上行%": pt.get("upside_pct"),
            "近30天淨上修": net,
            "_o": _VERDICT_ORDER.get(verdict, 4),
            "_u": pt.get("upside_pct") if pt.get("upside_pct") is not None else -999.0,
        })
    return rows


def _render_grid(scored: dict | None) -> list[str]:
    """Render the multi-ticker ranking grid; return the ticker list (for the detail default)."""
    st.subheader("📋 候選股分析師排行")
    if not scored:
        st.info("尚無評分候選股清單(管線尚未產生);可直接在下方輸入代號查詢個股分析師共識。")
        return []
    cands = scored.get("all_scored") or (
        (scored.get("needs_layer2") or []) + (scored.get("watchlist") or []))
    if not cands:
        st.info("尚無評分候選股清單(管線尚未產生);可直接在下方輸入代號查詢個股分析師共識。")
        return []

    with st.spinner("讀取分析師共識中…"):
        rows = _grid_rows(cands)
    if not rows:
        st.info("候選股皆無分析師資料。")
        return [c.get("ticker") for c in cands if c.get("ticker")]

    df = (pd.DataFrame(rows)
          .sort_values(["_o", "_u"], ascending=[True, False])
          .drop(columns=["_o", "_u"])
          .reset_index(drop=True))

    styled = df.style.apply(_style_verdict, subset=["判定"])

    st.dataframe(
        styled, hide_index=True, use_container_width=True,
        column_config={
            "判定": st.column_config.TextColumn("判定", width="small"),
            "代號": st.column_config.TextColumn("代號", width="small"),
            "共識": st.column_config.TextColumn("共識評等", width="small"),
            "分析師": st.column_config.NumberColumn("分析師數", format="%d", width="small"),
            "上行%": st.column_config.NumberColumn(
                "目標上行%", format="%.1f%%",
                help="分析師目標均價相對現價的上行空間"),
            "近30天淨上修": st.column_config.NumberColumn(
                "近30天淨上修", format="%d",
                help="EPS 預估上修家數 − 下修家數(各期合計);正值=分析師調升動能"),
        },
    )
    st.caption("排序:判定優先,其次目標上行空間。🟢 買進系列  🟡 觀察  🔴 迴避。免費 yfinance 資料,6 小時快取。")
    return df["代號"].tolist()


def _render_distribution(dist: dict) -> None:
    """Horizontal rating-distribution bar (colour = bullish→bearish)."""
    vals = [dist.get(k) or 0 for _, k in _DIST_LABELS]
    if not any(vals):
        return
    labels = [lbl for lbl, _ in _DIST_LABELS]
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=_DIST_COLORS,
        text=[int(v) if v else "" for v in vals], textposition="outside",
        hovertemplate="%{y}: %{x} 位<extra></extra>",
    ))
    fig.update_layout(
        height=220, margin=dict(l=70, r=20, t=10, b=10),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.BG,
        font=dict(color="#d6dae3"),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_target_range(pt: dict) -> None:
    """Price-target range bar: low→high spine with spot & mean markers."""
    low, high = pt.get("low"), pt.get("high")
    spot, mean, median = pt.get("spot"), pt.get("mean"), pt.get("median")
    if low is None or high is None or high <= low:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[low, high], y=[0, 0], mode="lines",
        line=dict(color=_shared.MUTED, width=6), hoverinfo="skip", showlegend=False))
    pts = [(low, "低", _shared.MUTED), (high, "高", _shared.MUTED)]
    if median is not None:
        pts.append((median, "中位", _shared.BLUE))
    if mean is not None:
        pts.append((mean, "均價", _shared.AMBER))
    if spot is not None:
        pts.append((spot, "現價", _shared.GREEN))
    # Alternate text positions top/bottom to reduce label collisions when
    # values cluster (e.g. mean ≈ median ≈ spot).
    for i, (x, name, color) in enumerate(pts):
        tpos = "top center" if i % 2 == 0 else "bottom center"
        fig.add_trace(go.Scatter(
            x=[x], y=[0], mode="markers+text", text=[f"{name}<br>${x:,.0f}"],
            textposition=tpos, marker=dict(size=12, color=color),
            textfont=dict(color=color, size=11),
            hovertemplate=f"{name}: ${x:,.2f}<extra></extra>", showlegend=False))
    fig.update_layout(
        height=180, margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.BG,
        xaxis=dict(showgrid=False, zeroline=False, title=None),
        yaxis=dict(visible=False, range=[-1.0, 1.5]))
    st.plotly_chart(fig, use_container_width=True)


def _render_detail(ticker: str) -> None:
    """Per-ticker analyst detail: targets, distribution, actions, revisions."""
    data = _shared.load_analyst_views(ticker)
    if not data:
        st.warning(f"{ticker}:無分析師資料(覆蓋不足或來源暫時無回應)。")
        return

    cons = data.get("consensus") or {}
    rec = cons.get("recommendation")
    chips = []
    if rec:
        chips.append((rec.replace("_", " ").upper(), _shared.rating_color(rec)))
    if cons.get("num_analysts") is not None:
        chips.append((f"{int(cons['num_analysts'])} 位分析師", _shared.MUTED))
    if cons.get("mean_rating_score") is not None:
        chips.append((f"平均評等 {cons['mean_rating_score']:.2f}/5", _shared.MUTED))
    if chips:
        _shared.chips_row(chips)

    # Price targets
    pt = data.get("price_targets") or {}
    if any(pt.get(k) is not None for k in ("spot", "mean", "high", "low")):
        c1, c2, c3, c4, c5 = st.columns(5)
        up = pt.get("upside_pct")
        _shared.metric_card(c1, "現價", f"${pt['spot']:,.2f}" if pt.get("spot") else "—")
        # upside% is signed: target above spot (bullish) → green, below → red = 'normal'
        _shared.metric_card(
            c2, "目標均價", f"${pt['mean']:,.2f}" if pt.get("mean") else "—",
            delta=(f"{up:+.1f}%" if up is not None else None), delta_color="normal")
        _shared.metric_card(c3, "目標中位", f"${pt['median']:,.2f}" if pt.get("median") else "—")
        _shared.metric_card(c4, "目標高", f"${pt['high']:,.2f}" if pt.get("high") else "—")
        _shared.metric_card(c5, "目標低", f"${pt['low']:,.2f}" if pt.get("low") else "—")
        _render_target_range(pt)

    # Rating distribution + recent actions, side by side
    dist = data.get("rating_distribution") or {}
    actions = data.get("recent_actions") or []
    col_dist, col_act = st.columns([1, 1.3])
    with col_dist:
        if any((dist.get(k) or 0) for _, k in _DIST_LABELS):
            st.markdown("#### 評等分布")
            _render_distribution(dist)
    with col_act:
        if actions:
            st.markdown("#### 近期評等動作")
            adf = pd.DataFrame([{
                "日期": a.get("date", ""),
                "機構": a.get("firm", ""),
                "動作": _ACTION_LABEL.get(
                    a.get("pt_action") or a.get("action") or "",
                    a.get("pt_action") or a.get("action") or ""),
                "評等": (f"{a.get('from_grade', '')} → {a.get('to_grade', '')}"
                       if a.get("from_grade") and a.get("from_grade") != a.get("to_grade")
                       else a.get("to_grade", "")),
                "目標價": a.get("pt_current"),
            } for a in actions])
            styled_adf = adf.style.apply(_style_action, subset=["動作"])
            st.dataframe(
                styled_adf, hide_index=True, use_container_width=True,
                column_config={
                    "日期": st.column_config.TextColumn("日期", width="small"),
                    "機構": st.column_config.TextColumn("機構", width="medium"),
                    "動作": st.column_config.TextColumn("動作", width="small"),
                    "評等": st.column_config.TextColumn("評等", width="medium"),
                    "目標價": st.column_config.NumberColumn("目標價", format="$%.0f"),
                },
            )

    # Forward estimate revisions
    rev = data.get("estimate_revisions") or {}
    rev_rows = []
    for label, key in [("本季 EPS", "eps_curr_q"), ("次季 EPS", "eps_next_q"),
                       ("今年 EPS", "eps_curr_year"), ("明年 EPS", "eps_next_year")]:
        r = rev.get(key)
        if not r:
            continue
        rev_rows.append({
            "期別": label,
            "預估均值": r.get("avg"),
            "年增率%": r.get("growth_pct"),
            "近30天上修": r.get("up_last_30d"),
            "近30天下修": r.get("down_last_30d"),
        })
    if rev_rows:
        st.markdown("#### 預估與修正")
        st.dataframe(
            pd.DataFrame(rev_rows), hide_index=True, use_container_width=True,
            column_config={
                "期別": st.column_config.TextColumn("期別", width="small"),
                "預估均值": st.column_config.NumberColumn("預估均值(EPS)", format="%.2f"),
                "年增率%": st.column_config.NumberColumn("年增率", format="%.1f%%"),
                "近30天上修": st.column_config.NumberColumn("↑ 上修", format="%d"),
                "近30天下修": st.column_config.NumberColumn("↓ 下修", format="%d"),
            },
        )
        st.caption("上修家數 > 下修家數 = 分析師調升預估的動能(Dimension 7c 的領先子訊號)。")


# _render_detail is already self-contained (takes a ticker, fetches its own data),
# so it doubles as the embeddable entry for 個股總覽's 分析師評級 tab.
render_for = _render_detail


def render() -> None:
    st.header("📊 分析師評級")
    st.caption("賣方分析師共識 — 評等、目標價、升降評、預估修正(免費 yfinance,Dimension 7)。"
               "決策參考,非投資建議。")

    scored = _shared.load_json(str(_shared.candidate_output_path("scored_candidates.json")))
    grid_tickers = _render_grid(scored)

    st.divider()
    st.subheader("🔎 個股明細")

    # When no grid data, default to blank so user isn't confused by a pre-loaded ticker.
    default = grid_tickers[0] if grid_tickers else ""
    c1, c2 = st.columns([3, 1])
    ticker_input = c1.text_input(
        "輸入代號", value=default,
        label_visibility="collapsed",
        placeholder="美股代號,如 NVDA",
        help="可查任意美股代號,不限候選股。").strip().upper()
    query = c2.button("查詢", type="primary")

    # Fire on explicit button press OR on direct value change (e.g. grid default).
    ticker = ticker_input if (query or (ticker_input and not query)) else ""

    if ticker:
        with st.container(border=True):
            _render_detail(ticker)
