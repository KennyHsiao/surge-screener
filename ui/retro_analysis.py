"""美股 · 復盤分析 — surge-stock retrospective / factor validation.

Reads the retro pipeline outputs (reports/retrospective/) and shows, in trader
reading order: the ground-truth surge events, the per-factor LIFT table (how much
more often each scoring sub-factor appears before a real surge than at random),
and the LLM's human-review recommendations.

The complement to the screener's own pick-ledger: this mines ALL stocks that
actually surged, not just the ones the filter let through — so it can tell which
of the rubric's indicators are validated, noise, or contrarian. Display-only;
recommendations are never auto-applied (matches the read-only philosophy).
"""

import json
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

RETRO_DIR = _shared.REPORTS_DIR / "retrospective"

# Verdict → design token (greens validated, amber contrarian, muted noise).
_VERDICT_COLOR = {
    "VALIDATED": _shared.GREEN,
    "WEAK": _shared.BLUE,
    "NOISE": _shared.MUTED,
    "CONTRARIAN": _shared.AMBER,
    "INSUFFICIENT": _shared.MUTED,
}


def _load(name: str) -> dict | None:
    return _shared.load_json(str(RETRO_DIR / name))


def _extract_report_json(text: str) -> dict | None:
    """Pull the leading ```json fenced object out of the LLM report string."""
    if not text:
        return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    blob = m.group(1) if m else text
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return None


def _events_tab(events: dict) -> None:
    rows = events.get("events", [])
    if not rows:
        st.info("尚無暴漲事件。先跑 `scripts/retro_surge_label.py`。")
        return
    st.caption(
        f"宇宙 {events.get('universe')} · 回看 {events.get('lookback_days')} 天 · "
        f"掃描 {events.get('tickers_scanned')} 檔 · 事件 {events.get('event_count')} 個 "
        f"({events.get('event_count_by_threshold', {})})")

    df = pd.DataFrame(rows)
    thresholds = ["全部", *sorted(df["threshold"].unique())]
    pick = st.radio("門檻", thresholds, horizontal=True, key="retro_evt_thr")
    view = df if pick == "全部" else df[df["threshold"] == pick]
    view = view.sort_values("magnitude_pct", ascending=False)

    st.dataframe(
        view, hide_index=True, use_container_width=True,
        column_config={
            "ticker": "代號",
            "threshold": "門檻",
            "surge_start": "起漲(谷底)",
            "peak_date": "峰值日",
            "trough_price": st.column_config.NumberColumn("谷底價", format="%.2f"),
            "peak_price": st.column_config.NumberColumn("峰值價", format="%.2f"),
            "magnitude_pct": st.column_config.NumberColumn("漲幅 %", format="%.1f%%"),
            "sessions_to_peak": st.column_config.NumberColumn("天數"),
        })

    tickers = sorted(view["ticker"].unique())
    if tickers:
        sel = st.selectbox("看圖", tickers, key="retro_evt_chart")
        _shared.tradingview_chart(sel, height=420)

    for c in events.get("caveats", []):
        st.caption(f"⚠️ {c}")


def _lift_tab(lift: dict, features: dict) -> None:
    tables = lift.get("tables", {})
    if not tables:
        st.info("尚無因子 lift。先跑 `scripts/retro_factor_lift.py`。")
        return
    if lift.get("low_confidence"):
        st.warning("⚠️ 樣本偏小(暴漲事件 < 30)— 判定僅供參考方向,非結論。")

    labels = ["ALL", *[l for l in tables if l != "ALL"]]
    pick = st.radio("門檻", labels, horizontal=True, key="retro_lift_thr")
    factors = tables[pick].get("factors", [])
    if not factors:
        st.info("此門檻無資料。")
        return

    fdf = pd.DataFrame(factors)
    fdf["ci_low"] = fdf["lift_ci90"].apply(lambda x: x[0] if isinstance(x, list) else None)
    fdf["ci_high"] = fdf["lift_ci90"].apply(lambda x: x[1] if isinstance(x, list) else None)

    # Horizontal lift bar, coloured by verdict, reference line at 1.0 (no edge).
    bar = fdf.sort_values("lift")
    fig = go.Figure(go.Bar(
        x=bar["lift"], y=bar["factor"], orientation="h",
        marker_color=[_VERDICT_COLOR.get(v, _shared.MUTED) for v in bar["verdict"]],
        text=[f"{v:.2f}× ({vd})" for v, vd in zip(bar["lift"], bar["verdict"])],
        textposition="outside",
        hovertemplate="%{y}: lift %{x:.2f}<extra></extra>",
    ))
    fig.add_vline(x=1.0, line_dash="dash", line_color=_shared.MUTED,
                  annotation_text="無預測力 (1.0)", annotation_position="top")
    fig.update_layout(
        height=460, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.PANEL,
        xaxis_title="lift = P(因子|暴漲) / P(因子|隨機)", font=dict(color="#d6dae3"))
    st.plotly_chart(fig, use_container_width=True)

    show = fdf[["factor", "dimension", "subfactor", "desc", "p_surge",
                "p_control", "lift", "precision_lift", "support", "verdict"]]
    st.dataframe(
        show, hide_index=True, use_container_width=True,
        column_config={
            "factor": "因子",
            "dimension": "維度",
            "subfactor": "子項",
            "desc": "說明",
            "p_surge": st.column_config.NumberColumn("暴漲前出現率", format="%.2f"),
            "p_control": st.column_config.NumberColumn("隨機出現率", format="%.2f"),
            "lift": st.column_config.NumberColumn("lift", format="%.2f"),
            "precision_lift": st.column_config.NumberColumn("精準 lift", format="%.2f"),
            "support": st.column_config.NumberColumn("樣本"),
            "verdict": "判定",
        })
    st.caption(f"方法:{lift.get('method', '')}")


def _recommendations_tab(latest: dict) -> None:
    if not latest:
        st.info("尚無 AI 建議。先跑 `scripts/retro_report.py --provider auto`。")
        return
    st.error("⚠️ 以下建議**僅供人工審查,非自動套用**。權重/prompt 由你決定是否調整。")

    rep = _extract_report_json(latest.get("llm_report", ""))
    if not rep:
        st.markdown(latest.get("llm_report", "") or "_(無內容)_")
        return

    if rep.get("narrative_summary"):
        st.markdown(f"**總結:** {rep['narrative_summary']}")

    groups = [
        ("✅ 已驗證 (validated)", rep.get("validated_factors", []), _shared.GREEN),
        ("➖ 雜訊 (noise)", rep.get("noise_factors", []), _shared.MUTED),
        ("🔄 反向 (contrarian)", rep.get("contrarian_factors", []), _shared.AMBER),
    ]
    cols = st.columns(len(groups))
    for col, (title, items, color) in zip(cols, groups):
        with col:
            st.markdown(f"<span style='color:{color};font-weight:600'>{title}</span>",
                        unsafe_allow_html=True)
            for it in items:
                lift = it.get("lift")
                st.markdown(f"**{it.get('factor')}** · {it.get('subfactor', '')} "
                            f"· lift {lift}")
                st.caption(it.get("reading", ""))

    gaps = rep.get("coverage_gaps", [])
    if gaps:
        st.subheader("🕳 覆蓋缺口")
        for g in gaps:
            st.markdown(f"- {g}")

    changes = rep.get("proposed_changes", [])
    if changes:
        st.subheader("📝 建議變更(供審查)")
        st.dataframe(
            pd.DataFrame(changes), hide_index=True, use_container_width=True)


def render() -> None:
    st.title("🔁 復盤分析 — 暴漲股因子驗證")
    st.caption("挖出真正暴漲過的股票,反推哪些指標在暴漲前真的出現、哪些失效、哪些反向。"
               "本頁只驗證 **Dim1 技術面 + Dim5 板塊/regime**(其餘維度的歷史資料免費源無法回填)。")

    events = _load("surge_events.json")
    features = _load("surge_features.json")
    lift = _load("factor_lift.json")
    latest = _load("latest.json")

    if not any([events, lift, latest]):
        st.info("尚未產生復盤資料。依序執行:\n\n"
                "```\npython scripts/retro_surge_label.py --universe sp1500 --lookback-days 730\n"
                "python scripts/retro_reconstruct.py\n"
                "python scripts/retro_factor_lift.py\n"
                "python scripts/retro_report.py --provider auto\n```")
        return

    t1, t2, t3 = st.tabs(["暴漲事件", "因子驗證", "AI 建議"])
    with t1:
        _events_tab(events or {})
    with t2:
        _lift_tab(lift or {}, features or {})
    with t3:
        _recommendations_tab(latest or {})
