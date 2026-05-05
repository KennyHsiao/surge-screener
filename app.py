#!/usr/bin/env python3
"""
Surge Screener Dashboard — Streamlit UI
Reads JSON outputs from the screening pipeline and displays results.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Surge Screener v3.2",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent
REPORTS_DIR = DATA_DIR / "reports"


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_json(path: str) -> dict | None:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None


@st.cache_data(ttl=60)
def load_ledger() -> pd.DataFrame | None:
    path = REPORTS_DIR / "performance_ledger.csv"
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            df["scan_date"] = pd.to_datetime(df["scan_date"], errors="coerce")
            numeric = ["composite_score", "fwd_3d_return", "fwd_7d_return",
                       "fwd_14d_return", "fwd_30d_return", "fwd_60d_return",
                       "max_drawdown_30d", "suggested_size_pct"]
            for col in numeric:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
    return None


def find_report_dates() -> list[str]:
    """Find all available report dates."""
    dates = []
    if REPORTS_DIR.exists():
        for d in sorted(REPORTS_DIR.iterdir(), reverse=True):
            if d.is_dir() and d.name not in ("reflections",):
                dates.append(d.name)
    return dates


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("📈 Surge Screener v3.2")
st.sidebar.markdown("DEoT Multi-Layer Analysis")

# Data source selection
st.sidebar.markdown("---")
st.sidebar.subheader("Data Sources")

# Try to find latest data files
filtered_path = DATA_DIR / "filtered_universe.json"
filtered_nasdaq_path = DATA_DIR / "filtered_nasdaq.json"
scored_path = DATA_DIR / "scored_candidates.json"
layer2_path = DATA_DIR / "layer2_results.json"
dd_path = DATA_DIR / "dd_results.json"

# Use whichever filtered file exists
if filtered_nasdaq_path.exists():
    filtered_path = filtered_nasdaq_path

report_dates = find_report_dates()
selected_date = None
if report_dates:
    selected_date = st.sidebar.selectbox("Report Date", report_dates)

# Status indicators
st.sidebar.markdown("---")
st.sidebar.subheader("Pipeline Files")
files_status = {
    "Hard Filter": filtered_path.exists(),
    "LLM Scored": scored_path.exists(),
    "Engine Controller": layer2_path.exists(),
    "Deep DD": dd_path.exists(),
    "Report": selected_date is not None,
    "Ledger": (REPORTS_DIR / "performance_ledger.csv").exists(),
}
for name, exists in files_status.items():
    icon = "✅" if exists else "⬜"
    st.sidebar.text(f"{icon} {name}")


# ---------------------------------------------------------------------------
# Main Content
# ---------------------------------------------------------------------------

# Load all available data
filtered_data = load_json(str(filtered_path))
scored_data = load_json(str(scored_path))
layer2_data = load_json(str(layer2_path))
dd_data = load_json(str(dd_path))
report_data = None
if selected_date:
    report_data = load_json(str(REPORTS_DIR / selected_date / "summary.json"))
ledger_df = load_ledger()


# ===================== TAB LAYOUT =====================
tabs = st.tabs([
    "🌡 Regime", "🔽 Pipeline", "📊 Candidates",
    "🧠 Layer 2 Analysis", "🔍 DD Results", "📈 Performance",
])


# ===================== TAB 0: REGIME =====================
with tabs[0]:
    st.header("Layer 0 — Market Regime")

    regime = None
    if scored_data:
        regime = scored_data.get("regime_context", {})
    elif layer2_data:
        regime = layer2_data.get("regime_context", {})

    if regime:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            spy_status = regime.get("spy_vs_50dma", "?")
            st.metric("SPY vs 50DMA", spy_status.upper(),
                      delta="Bullish" if spy_status == "above" else "Bearish")

        with col2:
            spy200 = regime.get("spy_vs_200dma", "?")
            st.metric("SPY vs 200DMA", spy200.upper(),
                      delta="Bullish" if spy200 == "above" else "Bearish")

        with col3:
            vix = regime.get("vix_level", 0)
            vix_regime = regime.get("vix_regime", "?")
            st.metric("VIX", f"{vix:.1f}", delta=vix_regime)

        with col4:
            mult = regime.get("global_score_multiplier", 1.0)
            color = "normal" if mult >= 0.85 else "inverse"
            st.metric("Score Multiplier", f"{mult:.2f}x",
                      delta="Full" if mult == 1.0 else f"Reduced",
                      delta_color=color)

        st.markdown("### Active Themes")
        themes = regime.get("active_themes", [])
        if themes:
            cols = st.columns(len(themes))
            for i, theme in enumerate(themes):
                with cols[i]:
                    st.info(f"🔥 {theme}")
        else:
            st.text("No themes detected")

        warnings = regime.get("regime_warnings", [])
        if warnings:
            st.markdown("### Warnings")
            for w in warnings:
                st.warning(w)
    else:
        st.info("No regime data available. Run the pipeline first.")


# ===================== TAB 1: PIPELINE =====================
with tabs[1]:
    st.header("Screening Pipeline")

    # Funnel data
    funnel_labels = []
    funnel_values = []

    if filtered_data:
        funnel_labels.append("Universe")
        funnel_values.append(filtered_data.get("total_universe", 0))
        funnel_labels.append("Hard Filter Passed")
        funnel_values.append(filtered_data.get("passed_hard_filters", 0))

    if scored_data:
        funnel_labels.append("Layer 1 Passed (≥65)")
        funnel_values.append(scored_data.get("needs_layer2_count", 0))
        wl = scored_data.get("watchlist_count", 0)
        if wl:
            funnel_labels.append("Layer 1 Watchlist")
            funnel_values.append(wl)

    if layer2_data:
        funnel_labels.append("Layer 2 → DD")
        funnel_values.append(layer2_data.get("continue_to_dd_count", 0))

    if dd_data:
        funnel_labels.append("DD Confirmed")
        funnel_values.append(dd_data.get("confirmed_count", 0))

    if funnel_labels:
        fig = go.Figure(go.Funnel(
            y=funnel_labels,
            x=funnel_values,
            textinfo="value+percent initial",
            marker=dict(color=["#636EFA", "#EF553B", "#00CC96",
                               "#AB63FA", "#FFA15A", "#19D3F3"][:len(funnel_labels)]),
        ))
        fig.update_layout(
            title="Screening Funnel",
            height=400,
            margin=dict(l=200),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Stats
        if filtered_data:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Universe Size", filtered_data.get("total_universe", 0))
            with col2:
                st.metric("Passed Filters", filtered_data.get("passed_hard_filters", 0))
            with col3:
                total = filtered_data.get("total_universe", 1)
                passed = filtered_data.get("passed_hard_filters", 0)
                st.metric("Pass Rate", f"{passed/total*100:.1f}%")
    else:
        st.info("No pipeline data. Run `01_hard_filter.py` first.")


# ===================== TAB 2: CANDIDATES =====================
with tabs[2]:
    st.header("Candidate Scores")

    all_candidates = []
    if scored_data:
        for group in ["needs_layer2", "watchlist"]:
            for c in scored_data.get(group, []):
                c["_group"] = group.replace("needs_layer2", "NEEDS_LAYER_2").upper()
                all_candidates.append(c)

    if all_candidates:
        # Sort by score
        all_candidates.sort(
            key=lambda x: x.get("regime_adjusted_score", 0), reverse=True
        )

        for cand in all_candidates:
            ticker = cand.get("ticker", "?")
            score = cand.get("regime_adjusted_score", 0)
            verdict = cand.get("verdict", "?")

            # Color based on verdict
            if verdict == "NEEDS_LAYER_2":
                border_color = "#00CC96"
            elif verdict == "WATCHLIST":
                border_color = "#FFA15A"
            else:
                border_color = "#EF553B"

            with st.container(border=True):
                col_header, col_score = st.columns([3, 1])
                with col_header:
                    st.subheader(f"${ticker}")
                    st.caption(f"{verdict}")
                with col_score:
                    st.metric("Score", f"{score:.0f}/100")

                # Radar chart for 6 dimensions
                scores = cand.get("scores", {})
                if scores:
                    dims = ["Technical", "Catalyst", "Sentiment",
                            "Institutional", "Sector", "Options"]
                    maxes = [30, 20, 15, 10, 5, 20]
                    vals = [
                        scores.get("technical", 0),
                        scores.get("catalyst", 0),
                        scores.get("sentiment", 0),
                        scores.get("institutional", 0),
                        scores.get("sector_market", 0),
                        scores.get("options_flow", 0),
                    ]
                    # Normalize to 0-1
                    norm_vals = [v / m if m > 0 else 0 for v, m in zip(vals, maxes)]
                    norm_vals.append(norm_vals[0])  # close the polygon
                    dims_closed = dims + [dims[0]]

                    col_radar, col_details = st.columns([1, 1])

                    with col_radar:
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(
                            r=norm_vals,
                            theta=dims_closed,
                            fill="toself",
                            fillcolor="rgba(99, 110, 250, 0.2)",
                            line=dict(color="#636EFA", width=2),
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
                        # Score breakdown table
                        breakdown = pd.DataFrame({
                            "Dimension": dims,
                            "Score": vals,
                            "Max": maxes,
                            "Pct": [f"{v/m*100:.0f}%" if m > 0 else "—"
                                    for v, m in zip(vals, maxes)],
                        })
                        st.dataframe(breakdown, hide_index=True, use_container_width=True)

                        # Technical breakdown
                        tb = cand.get("technical_breakdown", {})
                        if tb:
                            st.caption(
                                f"Pattern: **{tb.get('pattern_type', '?')}** | "
                                f"MACD: {tb.get('macd_state', '?')}"
                            )

                # Key signals and risks
                col_sig, col_risk = st.columns(2)
                with col_sig:
                    signals = cand.get("key_signals", [])
                    if signals:
                        st.markdown("**Signals**")
                        for s in signals:
                            st.markdown(f"- 🟢 {s}")

                with col_risk:
                    risks = cand.get("key_risks", [])
                    if risks:
                        st.markdown("**Risks**")
                        for r in risks:
                            st.markdown(f"- 🔴 {r}")

                # Entry zone
                entry = cand.get("suggested_entry_zone")
                stop = cand.get("suggested_stop")
                size = cand.get("suggested_size_pct")
                if entry:
                    st.markdown(
                        f"📍 Entry: **{entry}** | "
                        f"Stop: **{stop}** | "
                        f"Size: **{size}%**"
                    )

                # Warnings
                anti = cand.get("anti_example_warning")
                if anti:
                    st.warning(f"Anti-Example Warning: {anti}")

                missing = cand.get("data_missing", [])
                if missing:
                    st.caption(f"Data gaps: {', '.join(missing)}")
    else:
        st.info("No scored candidates. Run the pipeline first.")


# ===================== TAB 3: LAYER 2 =====================
with tabs[3]:
    st.header("Layer 2 — Engine Controller Analysis")

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

            # Verdict color
            if verdict == "CONTINUE_TO_DD":
                icon = "🟢"
            elif verdict == "WATCHLIST":
                icon = "🟡"
            else:
                icon = "🔴"

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.subheader(f"{icon} ${ticker}")
                    st.caption(f"Path: {path}")
                with col2:
                    st.metric("Score", f"{final:.0f}",
                              delta=f"{delta:+.0f}" if delta != 0 else None)
                with col3:
                    st.metric("Verdict", verdict)

                # Analysis tree
                tree = result.get("analysis_tree", [])
                if tree:
                    st.markdown("#### Analysis Tree")
                    for node in tree:
                        layer = node.get("layer", "?")
                        decision = node.get("decision", "?")
                        reasoning = node.get("reasoning", "")
                        term_reason = node.get("termination_reason")

                        if decision == "TERMINATE":
                            st.markdown(
                                f"**Layer {layer}** → ⏹ TERMINATE "
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

                        # Show action results
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
                            st.info(f"Summary: {summary}")
    else:
        st.info("No Layer 2 data. Run `025_engine_controller.py` first.")


# ===================== TAB 4: DD RESULTS =====================
with tabs[4]:
    st.header("Layer 3 — Deep Due Diligence")

    if dd_data:
        for group, group_name in [("confirmed", "Confirmed"),
                                   ("downgraded", "Downgraded"),
                                   ("rejected", "Rejected")]:
            items = dd_data.get(group, [])
            if not items:
                continue

            st.subheader(f"{'✅' if group == 'confirmed' else '⚠️' if group == 'downgraded' else '❌'} {group_name} ({len(items)})")

            for item in items:
                ticker = item.get("ticker", "?")
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.subheader(f"${ticker}")
                    with col2:
                        st.metric("DD Score", item.get("final_score", "?"),
                                  delta=item.get("dd_score_adjustment"))
                    with col3:
                        st.metric("10-Q Health",
                                  item.get("filings_review", {}).get("10q_health", "?"))

                    # Filings
                    filings = item.get("filings_review", {})
                    findings = filings.get("key_findings", [])
                    red_flags = filings.get("red_flags", [])

                    col_good, col_bad = st.columns(2)
                    with col_good:
                        if findings:
                            st.markdown("**Key Findings**")
                            for f in findings:
                                st.markdown(f"- ✅ {f}")
                    with col_bad:
                        if red_flags:
                            st.markdown("**Red Flags**")
                            for r in red_flags:
                                st.markdown(f"- 🚩 {r}")

                    # 8-K
                    eight_k = item.get("8k_findings", {})
                    if eight_k.get("biggest_catalyst"):
                        st.markdown(f"**Catalyst:** {eight_k['biggest_catalyst']}")

                    # Short thesis (mandatory)
                    short_thesis = item.get("short_thesis_summary", "")
                    short_strength = item.get("short_thesis_strength", "?")
                    if short_thesis:
                        st.markdown("---")
                        st.markdown(f"**🐻 Short Thesis ({short_strength}):**")
                        st.warning(short_thesis)

                    # Final recommendation
                    rec = item.get("final_recommendation", "")
                    if rec:
                        st.success(f"**Recommendation:** {rec}")

                    # Data gaps
                    gaps = item.get("data_gaps", [])
                    if gaps:
                        st.caption(f"Data gaps: {', '.join(gaps)}")
    else:
        st.info("No DD data. Run `03_deep_dd.py` first.")


# ===================== TAB 5: PERFORMANCE =====================
with tabs[5]:
    st.header("Performance Ledger")

    if ledger_df is not None and not ledger_df.empty:
        # Summary metrics
        st.subheader("Overview")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Picks", len(ledger_df))

        fwd30 = ledger_df["fwd_30d_return"].dropna()
        with col2:
            if not fwd30.empty:
                st.metric("Avg 30d Return", f"{fwd30.mean():.1f}%")
            else:
                st.metric("Avg 30d Return", "Pending")

        with col3:
            if "hit_15pct_within_30d" in ledger_df.columns:
                hits = ledger_df["hit_15pct_within_30d"].apply(
                    lambda x: str(x).lower() == "true"
                )
                if hits.any():
                    st.metric("Hit +15% in 30d", f"{hits.mean()*100:.0f}%")
                else:
                    st.metric("Hit +15% in 30d", "Pending")
            else:
                st.metric("Hit +15% in 30d", "—")

        with col4:
            dd = ledger_df["max_drawdown_30d"].dropna()
            if not dd.empty:
                st.metric("Avg Max DD", f"{dd.mean():.1f}%")
            else:
                st.metric("Avg Max DD", "Pending")

        # Picks table
        st.subheader("All Picks")
        display_cols = ["scan_date", "ticker", "verdict", "composite_score",
                        "suggested_entry_low", "suggested_stop",
                        "fwd_3d_return", "fwd_7d_return", "fwd_30d_return",
                        "hit_15pct_within_30d", "notes"]
        available_cols = [c for c in display_cols if c in ledger_df.columns]
        st.dataframe(
            ledger_df[available_cols].sort_values("scan_date", ascending=False),
            hide_index=True,
            use_container_width=True,
        )

        # Forward return chart (if data available)
        if not fwd30.empty:
            st.subheader("Forward Returns Distribution")
            fig = go.Figure()
            for col, name in [("fwd_3d_return", "3d"),
                              ("fwd_7d_return", "7d"),
                              ("fwd_14d_return", "14d"),
                              ("fwd_30d_return", "30d")]:
                if col in ledger_df.columns:
                    vals = ledger_df[col].dropna()
                    if not vals.empty:
                        fig.add_trace(go.Box(y=vals, name=name))
            fig.update_layout(
                title="Forward Return Distribution by Horizon",
                yaxis_title="Return (%)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ledger data yet. Picks will appear here after the first scan.")

    # Final report section
    if report_data:
        st.markdown("---")
        st.subheader(f"Report: {report_data.get('report_date', '?')}")

        commentary = report_data.get("cross_candidate_commentary", "")
        if commentary:
            st.markdown(f"**Commentary:** {commentary}")

        notes = report_data.get("portfolio_notes", "")
        if notes:
            st.markdown(f"**Portfolio Notes:** {notes}")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "Signal generation only. Not investment advice. "
    "Surge Screener v3.2 — DEoT Multi-Layer Analysis"
)
