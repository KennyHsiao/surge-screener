"""美股 · 暴漲股篩選器 — the original 6-tab dashboard, unchanged behavior.

Moved out of app.py into a render() function so it can be a page under
st.navigation. Page-specific controls (data source / report date / pipeline
status) render in the sidebar below the nav, only while this page is active.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

DATA_DIR = _shared.DATA_DIR
REPORTS_DIR = _shared.REPORTS_DIR


def _render_analyst_section(ticker: str) -> None:
    """賣方分析師評級 — live yfinance consensus, reusing the shared design system."""
    with st.expander("📊 賣方分析師評級", expanded=False):
        # Fetch inside the expander + spinner so a cold-cache yfinance round-trip
        # shows feedback instead of looking hung (matches analyst_views' grid).
        with st.spinner("讀取分析師共識中…"):
            data = _shared.load_analyst_views(ticker)
        if not data:
            st.caption("無分析師資料(覆蓋不足或來源暫時無回應)。")
            return

        # ── Consensus + rating distribution chips ──
        cons = data.get("consensus") or {}
        dist = data.get("rating_distribution") or {}
        chips = []
        rec = cons.get("recommendation")
        if rec:
            chips.append((rec.replace("_", " ").upper(), _shared.rating_color(rec)))
        n = cons.get("num_analysts")
        if n is not None:
            chips.append((f"{int(n)} 位分析師", _shared.MUTED))
        for label, key, color in [
            ("強力買進", "strong_buy", _shared.GREEN), ("買進", "buy", _shared.GREEN),
            ("持有", "hold", _shared.AMBER),
            ("賣出", "sell", _shared.RED), ("強力賣出", "strong_sell", _shared.RED),
        ]:
            v = dist.get(key)
            if v:
                chips.append((f"{label} {int(v)}", color))
        if chips:
            _shared.chips_row(chips)

        # ── Price targets vs spot ──
        pt = data.get("price_targets") or {}
        if any(pt.get(k) is not None for k in ("spot", "mean", "high", "low")):
            c1, c2, c3, c4 = st.columns(4)
            spot = pt.get("spot")
            mean = pt.get("mean")
            up = pt.get("upside_pct")
            _shared.metric_card(c1, "現價", f"${spot:,.2f}" if spot else "—")
            _shared.metric_card(
                c2, "目標均價", f"${mean:,.2f}" if mean else "—",
                delta=(f"{up:+.1f}%" if up is not None else None),
                delta_color="normal")
            _shared.metric_card(c3, "目標高", f"${pt['high']:,.2f}" if pt.get("high") else "—")
            _shared.metric_card(c4, "目標低", f"${pt['low']:,.2f}" if pt.get("low") else "—")

        # ── Recent rating actions (dated) ──
        actions = data.get("recent_actions") or []
        if actions:
            adf = pd.DataFrame([{
                "日期": a.get("date", ""),
                "機構": a.get("firm", ""),
                "動作": a.get("pt_action") or a.get("action") or "",
                "評等": (f"{a.get('from_grade','')} → {a.get('to_grade','')}"
                       if a.get("from_grade") and a.get("from_grade") != a.get("to_grade")
                       else a.get("to_grade", "")),
                "目標價": a.get("pt_current"),
            } for a in actions])
            st.dataframe(
                adf, hide_index=True, use_container_width=True,
                column_config={
                    "日期": st.column_config.TextColumn("日期", width="small"),
                    "機構": st.column_config.TextColumn("機構", width="medium"),
                    "動作": st.column_config.TextColumn("動作", width="small"),
                    "評等": st.column_config.TextColumn("評等", width="medium"),
                    "目標價": st.column_config.NumberColumn("目標價", format="$%.0f"),
                },
            )

        # ── Forward estimate revisions ──
        rev = data.get("estimate_revisions") or {}
        rchips = []
        for label, key in [("本季EPS", "eps_curr_q"), ("次季EPS", "eps_next_q"),
                           ("今年EPS", "eps_curr_year"), ("明年EPS", "eps_next_year")]:
            r = rev.get(key)
            if not r:
                continue
            up = r.get("up_last_30d")
            down = r.get("down_last_30d")
            if up is None and down is None:
                continue
            up, down = int(up or 0), int(down or 0)
            color = _shared.GREEN if up > down else _shared.RED if down > up else _shared.AMBER
            rchips.append((f"{label} 近30天 ↑{up}/↓{down}", color))
        if rchips:
            st.caption("預估修正(分析師上修/下修家數):")
            _shared.chips_row(rchips)


def render() -> None:
    # ----------------------------------------------------------------- Sidebar
    st.sidebar.title("📈 暴漲股篩選器 v3.2")
    st.sidebar.markdown("DEoT 多層分析")
    st.sidebar.markdown("---")
    st.sidebar.subheader("資料來源")

    filtered_path = DATA_DIR / "filtered_universe.json"
    filtered_nasdaq_path = DATA_DIR / "filtered_nasdaq.json"
    scored_path = DATA_DIR / "scored_candidates.json"
    layer2_path = DATA_DIR / "layer2_results.json"
    dd_path = DATA_DIR / "dd_results.json"

    if filtered_nasdaq_path.exists():
        filtered_path = filtered_nasdaq_path

    report_dates = _shared.find_report_dates()
    selected_date = None
    if report_dates:
        selected_date = st.sidebar.selectbox("報告日期", report_dates)

    st.sidebar.markdown("---")
    st.sidebar.subheader("管線檔案")
    files_status = {
        "硬篩選": filtered_path.exists(),
        "LLM 評分": scored_path.exists(),
        "引擎控制器": layer2_path.exists(),
        "深度盡調": dd_path.exists(),
        "報告": selected_date is not None,
        "績效帳本": (REPORTS_DIR / "performance_ledger.csv").exists(),
    }
    for name, exists in files_status.items():
        icon = "✅" if exists else "⬜"
        st.sidebar.text(f"{icon} {name}")

    # -------------------------------------------------------------- Load data
    filtered_data = _shared.load_json(str(filtered_path))
    scored_data = _shared.load_json(str(scored_path))
    layer2_data = _shared.load_json(str(layer2_path))
    dd_data = _shared.load_json(str(dd_path))
    report_data = None
    if selected_date:
        report_data = _shared.load_json(str(REPORTS_DIR / selected_date / "summary.json"))
    ledger_df = _shared.load_ledger()

    # ===================== TAB LAYOUT =====================
    tabs = st.tabs([
        "🌡 大盤環境", "🔽 篩選管線", "📊 候選股",
        "🧠 Layer 2 分析", "🔍 盡調結果", "📈 績效",
    ])

    # ===================== TAB 0: REGIME =====================
    with tabs[0]:
        st.header("Layer 0 — 大盤環境")

        regime = None
        if scored_data:
            regime = scored_data.get("regime_context", {})
        elif layer2_data:
            regime = layer2_data.get("regime_context", {})

        if regime:
            if selected_date:
                st.caption(f"資料日期 {selected_date}")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                spy_status = str(regime.get("spy_vs_50dma") or "?")
                bull50 = spy_status == "above"
                with st.container(border=True):
                    # above/below is genuinely directional, so colour it:
                    # bullish green, bearish red.
                    st.metric("SPY vs 50DMA", spy_status.upper(),
                              delta="偏多" if bull50 else "偏空",
                              delta_color="normal" if bull50 else "inverse")

            with col2:
                spy200 = str(regime.get("spy_vs_200dma") or "?")
                bull200 = spy200 == "above"
                with st.container(border=True):
                    st.metric("SPY vs 200DMA", spy200.upper(),
                              delta="偏多" if bull200 else "偏空",
                              delta_color="normal" if bull200 else "inverse")

            with col3:
                vix = regime.get("vix_level")
                vix = vix if isinstance(vix, (int, float)) else None
                vix_regime = regime.get("vix_regime", "?")
                with st.container(border=True):
                    # vix_regime is a state label, not an up/down move — "off"
                    # renders it grey instead of a misleading green ↑.
                    st.metric("VIX", f"{vix:.1f}" if vix is not None else "—",
                              delta=vix_regime, delta_color="off")

            with col4:
                mult = regime.get("global_score_multiplier", 1.0)
                color = "normal" if mult >= 0.85 else "inverse"
                with st.container(border=True):
                    st.metric("分數乘數", f"{mult:.2f}x",
                              delta="完整" if mult == 1.0 else "降權",
                              delta_color=color)

            st.markdown("### 當日主題")
            themes = regime.get("active_themes", [])
            if themes:
                cols = st.columns(len(themes))
                for i, theme in enumerate(themes):
                    with cols[i]:
                        st.info(f"🔥 {theme}")
            else:
                st.text("未偵測到主題")

            warnings = regime.get("regime_warnings", [])
            if warnings:
                with st.expander(f"⚠️ 市場警告 ({len(warnings)})", expanded=False):
                    for w in warnings:
                        st.markdown(f"- {w}")
        else:
            st.info("尚無大盤環境資料,請先執行管線。")

    # ===================== TAB 1: PIPELINE =====================
    with tabs[1]:
        st.header("篩選管線")

        funnel_labels = []
        funnel_values = []

        if filtered_data:
            funnel_labels.append("股票池")
            funnel_values.append(filtered_data.get("total_universe", 0))
            funnel_labels.append("通過硬篩選")
            funnel_values.append(filtered_data.get("passed_hard_filters", 0))

        if scored_data:
            funnel_labels.append("Layer 1 通過 (≥65)")
            funnel_values.append(scored_data.get("needs_layer2_count", 0))
            wl = scored_data.get("watchlist_count", 0)
            if wl:
                funnel_labels.append("Layer 1 觀察名單")
                funnel_values.append(wl)

        if layer2_data:
            funnel_labels.append("Layer 2 → 盡調")
            funnel_values.append(layer2_data.get("continue_to_dd_count", 0))

        if dd_data:
            funnel_labels.append("盡調確認")
            funnel_values.append(dd_data.get("confirmed_count", 0))

        if funnel_labels:
            fig = go.Figure(go.Funnel(
                y=funnel_labels,
                x=funnel_values,
                textinfo="value+percent initial",
                # Colour progression: blue (universe) → cyan → green → amber → purple
                # for pass-through stages — RED is reserved for genuine fail/shrink bars
                # and is intentionally absent from this all-pass funnel.
                marker=dict(color=[_shared.BLUE, _shared.CYAN, _shared.GREEN,
                                   _shared.GREEN, _shared.AMBER, _shared.PURPLE][:len(funnel_labels)]),
            ))
            fig.update_layout(
                title="篩選漏斗",
                height=400,
                margin=dict(l=200),
            )
            st.plotly_chart(fig, use_container_width=True)

            if filtered_data:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("股票池大小", filtered_data.get("total_universe", 0))
                with col2:
                    st.metric("通過篩選", filtered_data.get("passed_hard_filters", 0))
                with col3:
                    total = filtered_data.get("total_universe", 1)
                    passed = filtered_data.get("passed_hard_filters", 0)
                    st.metric("通過率", f"{passed/total*100:.1f}%")
        else:
            st.info("尚無管線資料,請先執行 `01_hard_filter.py`。")

    # ===================== TAB 2: CANDIDATES =====================
    with tabs[2]:
        st.header("候選股評分")

        all_candidates = []
        if scored_data:
            for group in ["needs_layer2", "watchlist"]:
                for c in scored_data.get(group, []):
                    c["_group"] = group.replace("needs_layer2", "NEEDS_LAYER_2").upper()
                    all_candidates.append(c)

        if all_candidates:
            all_candidates.sort(
                key=lambda x: x.get("regime_adjusted_score", 0), reverse=True
            )

            for cand in all_candidates:
                ticker = cand.get("ticker", "?")
                score = cand.get("regime_adjusted_score", 0)
                verdict = cand.get("verdict", "?")

                with st.container(border=True):
                    col_header, col_score = st.columns([3, 1])
                    with col_header:
                        # verdict signal carried by the colour-coded chip (the
                        # bordered container can't take a per-verdict colour)
                        st.markdown(f"### ${ticker}")
                        st.markdown(_shared.verdict_chip(verdict), unsafe_allow_html=True)
                    with col_score:
                        st.metric("分數", f"{score:.0f}/100")

                    scores = cand.get("scores", {})
                    if scores:
                        dims = ["技術", "催化", "情緒",
                                "籌碼", "板塊", "選擇權", "分析師"]
                        maxes = [30, 16, 13, 10, 3, 20, 8]
                        # `or 0` (not get-default) so an explicit JSON null from the
                        # LLM coerces to 0 instead of crashing the v/m division below.
                        vals = [
                            scores.get("technical") or 0,
                            scores.get("catalyst") or 0,
                            scores.get("sentiment") or 0,
                            scores.get("institutional") or 0,
                            scores.get("sector_market") or 0,
                            scores.get("options_flow") or 0,
                            scores.get("analyst") or 0,
                        ]
                        norm_vals = [v / m if m > 0 else 0 for v, m in zip(vals, maxes)]
                        norm_vals.append(norm_vals[0])
                        dims_closed = dims + [dims[0]]

                        col_radar, col_details = st.columns([1, 1])

                        with col_radar:
                            fig = go.Figure()
                            fig.add_trace(go.Scatterpolar(
                                r=norm_vals,
                                theta=dims_closed,
                                fill="toself",
                                fillcolor="rgba(99,110,250,0.2)",  # BLUE @ 20% — plotly rejects 8-digit hex
                                line=dict(color=_shared.BLUE, width=2),
                                name=ticker,
                            ))
                            fig.update_layout(
                                polar=dict(
                                    radialaxis=dict(visible=True, range=[0, 1],
                                                    showticklabels=False),
                                ),
                                showlegend=False,
                                height=280,
                                margin=dict(l=60, r=60, t=30, b=30),
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with col_details:
                            breakdown = pd.DataFrame({
                                "維度": dims,
                                "分數": vals,
                                "滿分": maxes,
                                "百分比": [f"{v/m*100:.0f}%" if m > 0 else "—"
                                        for v, m in zip(vals, maxes)],
                            })
                            st.dataframe(breakdown, hide_index=True, use_container_width=True)

                            tb = cand.get("technical_breakdown", {})
                            if tb:
                                st.caption(
                                    f"型態:**{tb.get('pattern_type', '?')}** | "
                                    f"MACD:{tb.get('macd_state', '?')}"
                                )

                    _render_analyst_section(ticker)

                    col_sig, col_risk = st.columns(2)
                    with col_sig:
                        signals = cand.get("key_signals", [])
                        if signals:
                            st.markdown("**訊號**")
                            for s in signals:
                                st.markdown(f"- 🟢 {s}")

                    with col_risk:
                        risks = cand.get("key_risks", [])
                        if risks:
                            st.markdown("**風險**")
                            for r in risks:
                                st.markdown(f"- 🔴 {r}")

                    entry = cand.get("suggested_entry_zone")
                    stop = cand.get("suggested_stop")
                    size = cand.get("suggested_size_pct")
                    if entry:
                        st.markdown(
                            f"📍 進場:**{entry}** | "
                            f"停損:**{stop}** | "
                            f"倉位:**{size}%**"
                        )

                    anti = cand.get("anti_example_warning")
                    if anti:
                        st.warning(f"反例警告:{anti}")

                    missing = cand.get("data_missing", [])
                    if missing:
                        st.caption(f"資料缺口:{', '.join(missing)}")
        else:
            st.info("尚無評分候選股,請先執行管線。")
            st.caption("執行 `scripts/02_llm_score.py` 以產生評分結果。")

    # ===================== TAB 3: LAYER 2 =====================
    with tabs[3]:
        st.header("Layer 2 — 引擎控制器分析")

        if layer2_data:
            all_l2 = (layer2_data.get("continue_to_dd", [])
                      + layer2_data.get("watchlist", [])
                      + layer2_data.get("rejected", []))

            for result in all_l2:
                ticker = result.get("ticker", "?")
                verdict = result.get("final_verdict", "?")
                path = result.get("layer2_path", "?")
                orig = result.get("original_adjusted_score", 0)
                final = result.get("final_adjusted_score", 0)
                delta = final - orig

                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"### ${ticker}")
                        # verdict shown by the colour-coded chip (no raw token metric)
                        st.markdown(_shared.verdict_chip(verdict), unsafe_allow_html=True)
                        st.caption(f"路徑:{path}")
                    with col2:
                        st.metric("分數", f"{final:.0f}",
                                  delta=f"{delta:+.0f}" if delta != 0 else None)

                    tree = result.get("analysis_tree", [])
                    if tree:
                        st.markdown("#### 分析樹")
                        for node in tree:
                            layer = node.get("layer", "?")
                            decision = node.get("decision", "?")
                            reasoning = node.get("reasoning", "")
                            term_reason = node.get("termination_reason")

                            if decision == "TERMINATE":
                                st.markdown(
                                    f"**Layer {layer}** → ⏹ 終止 "
                                    f"({term_reason})"
                                )
                                if reasoning:
                                    st.caption(reasoning)
                            else:
                                st.markdown(
                                    f"**Layer {layer}** → "
                                    f"{'🔍' if decision == 'DEPTH' else '🌐'} "
                                    f"{decision}"
                                )
                                if reasoning:
                                    st.caption(reasoning)

                            ar = node.get("action_result", {})
                            findings = ar.get("findings", [])
                            if findings:
                                for f in findings:
                                    impact = f.get("impact_on_verdict", "NEUTRAL")
                                    impact_icon = {"POSITIVE": "✅",
                                                   "NEGATIVE": "❌",
                                                   "NEUTRAL": "➖"}.get(impact, "➖")
                                    st.markdown(
                                        f"  {impact_icon} **{f.get('question', '?')}**"
                                    )
                                    st.markdown(f"  {f.get('answer', '')}")

                            summary = ar.get("summary")
                            if summary:
                                st.info(f"摘要:{summary}")
        else:
            st.info("尚無 Layer 2 資料,請先執行 `025_engine_controller.py`。")

    # ===================== TAB 4: DD RESULTS =====================
    with tabs[4]:
        st.header("Layer 3 — 深度盡調")

        if dd_data:
            for group, group_name in [("confirmed", "已確認"),
                                       ("downgraded", "已下修"),
                                       ("rejected", "已拒絕")]:
                items = dd_data.get(group, [])
                if not items:
                    continue

                st.subheader(f"{'✅' if group == 'confirmed' else '⚠️' if group == 'downgraded' else '❌'} {group_name} ({len(items)})")

                for item in items:
                    ticker = item.get("ticker", "?")
                    # Map DD group → verdict token so verdict_chip uses the shared
                    # colour map (confirmed→CONTINUE_TO_DD=green, downgraded→WATCHLIST=amber,
                    # rejected→REJECT=red).
                    _group_verdict = {
                        "confirmed": "CONTINUE_TO_DD",
                        "downgraded": "WATCHLIST",
                        "rejected": "REJECT",
                    }.get(group, group.upper())
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"### ${ticker}")
                            st.markdown(_shared.verdict_chip(_group_verdict), unsafe_allow_html=True)
                        with col2:
                            st.metric("盡調分數", item.get("final_score", "?"),
                                      delta=item.get("dd_score_adjustment"))
                        with col3:
                            st.metric("10-Q 健康度",
                                      item.get("filings_review", {}).get("10q_health", "?"))

                        filings = item.get("filings_review", {})
                        findings = filings.get("key_findings", [])
                        red_flags = filings.get("red_flags", [])

                        col_good, col_bad = st.columns(2)
                        with col_good:
                            if findings:
                                st.markdown("**關鍵發現**")
                                for f in findings:
                                    st.markdown(f"- ✅ {f}")
                        with col_bad:
                            if red_flags:
                                st.markdown("**警訊**")
                                for r in red_flags:
                                    st.markdown(f"- 🚩 {r}")

                        eight_k = item.get("8k_findings", {})
                        if eight_k.get("biggest_catalyst"):
                            st.markdown(f"**催化:** {eight_k['biggest_catalyst']}")

                        short_thesis = item.get("short_thesis_summary", "")
                        short_strength = item.get("short_thesis_strength", "?")
                        if short_thesis:
                            st.markdown("---")
                            st.markdown(f"**🐻 做空論點 ({short_strength}):**")
                            st.warning(short_thesis)

                        rec = item.get("final_recommendation", "")
                        if rec:
                            st.success(f"**建議:** {rec}")

                        gaps = item.get("data_gaps", [])
                        if gaps:
                            st.caption(f"資料缺口:{', '.join(gaps)}")
        else:
            st.info("尚無盡調資料,請先執行 `03_deep_dd.py`。")

    # ===================== TAB 5: PERFORMANCE =====================
    with tabs[5]:
        st.header("績效帳本")

        if ledger_df is not None and not ledger_df.empty:
            st.subheader("總覽")
            # Compute each value first, then render uniform bordered cards — keeps
            # the conditional logic out of the layout and matches the card style
            # used on the other pages. fwd30 stays in scope for the box plot below.
            fwd30 = ledger_df["fwd_30d_return"].dropna()
            if "hit_15pct_within_30d" in ledger_df.columns:
                # A pick is "pending" only while its outcome is unknown (NaN/blank).
                # A computed False is a real miss, not pending — so an all-miss set
                # must read 0%, never 待計算. Rate is over computed rows only.
                def _hit(x):
                    s = str(x).strip().lower()
                    if s in ("true", "1", "1.0", "yes"):
                        return True
                    if s in ("false", "0", "0.0", "no"):
                        return False
                    return None  # nan / blank -> not yet computed
                computed = [v for v in ledger_df["hit_15pct_within_30d"].map(_hit)
                            if v is not None]
                hit_val = (f"{sum(computed) / len(computed) * 100:.0f}%"
                           if computed else "待計算")
            else:
                hit_val = "—"
            dd = ledger_df["max_drawdown_30d"].dropna()
            cards = [
                ("總選股數", str(len(ledger_df))),
                ("平均30日報酬", f"{fwd30.mean():.1f}%" if not fwd30.empty else "待計算"),
                ("30日內達+15%", hit_val),
                ("平均最大回撤", f"{dd.mean():.1f}%" if not dd.empty else "待計算"),
            ]
            for col, (label, value) in zip(st.columns(4), cards):
                with col:
                    with st.container(border=True):
                        st.metric(label, value)

            st.subheader("所有選股")
            display_cols = ["scan_date", "ticker", "verdict", "composite_score",
                            "suggested_entry_low", "suggested_stop",
                            "fwd_3d_return", "fwd_7d_return", "fwd_30d_return",
                            "hit_15pct_within_30d", "notes"]
            col_labels = {
                "scan_date": "掃描日期", "ticker": "代號", "verdict": "判定",
                "composite_score": "綜合分數", "suggested_entry_low": "建議進場(低)",
                "suggested_stop": "停損", "fwd_3d_return": "3日報酬",
                "fwd_7d_return": "7日報酬", "fwd_30d_return": "30日報酬",
                "hit_15pct_within_30d": "30日內+15%", "notes": "備註",
            }
            available_cols = [c for c in display_cols if c in ledger_df.columns]
            st.dataframe(
                ledger_df[available_cols].sort_values("scan_date", ascending=False)
                .rename(columns=col_labels),
                hide_index=True,
                use_container_width=True,
            )

            if not fwd30.empty:
                st.subheader("前瞻報酬分布")
                fig = go.Figure()
                for col, name in [("fwd_3d_return", "3日"),
                                  ("fwd_7d_return", "7日"),
                                  ("fwd_14d_return", "14日"),
                                  ("fwd_30d_return", "30日")]:
                    if col in ledger_df.columns:
                        vals = ledger_df[col].dropna()
                        if not vals.empty:
                            fig.add_trace(go.Box(y=vals, name=name))
                fig.update_layout(
                    title="各期間前瞻報酬分布",
                    yaxis_title="報酬 (%)",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("尚無帳本資料。第一次掃描後選股會出現在這裡。")

        if report_data:
            st.markdown("---")
            st.subheader(f"報告:{report_data.get('report_date', '?')}")

            commentary = report_data.get("cross_candidate_commentary", "")
            if commentary:
                st.markdown(f"**評論:** {commentary}")

            notes = report_data.get("portfolio_notes", "")
            if notes:
                st.markdown(f"**投組備註:** {notes}")
