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


# The page can show >1 retro dataset (e.g. the point-in-time S&P500 run that
# clears survivorship bias, vs the older current-member sp1500 exploratory run).
# render() picks one and sets _CUR_BASE before any _load; _load (incl. the one
# inside _lift_tab) reads from it. Default = the actionable point-in-time set.
_CUR_BASE: "object | None" = None
_DATASET_LABELS = {
    "sp500_pit": "S&P500 point-in-time(可行動)",
    "": "S&P1500 現役成員(探索)",
}


def _load(name: str) -> dict | None:
    base = _CUR_BASE if _CUR_BASE is not None else RETRO_DIR
    return _shared.load_json(str(base / name))


def _dataset_options() -> list:
    """(label, base_dir) for each retro dataset that has a factor_lift.json.
    Point-in-time (survivorship-corrected, can unblock) first → it's the default."""
    opts = []
    pit = RETRO_DIR / "sp500_pit"
    if (pit / "factor_lift.json").exists():
        opts.append((_DATASET_LABELS["sp500_pit"], pit))
    if (RETRO_DIR / "factor_lift.json").exists():
        opts.append((_DATASET_LABELS[""], RETRO_DIR))
    return opts


def _gate_blocked(meta: dict) -> bool:
    """Canonical FAIL-CLOSED gate, mirrored from retro_factor_lift.is_recommendations_blocked.
    Unblocked ONLY when recommendations_blocked, low_confidence, sample_experiment,
    survivorship_bias, membership_stale AND delisted_data_gap are ALL explicitly False
    (re-derived, not trusting the stored flag). Missing/biased/stale/delisted → blocked."""
    cov = meta.get("coverage", {}) or {}
    return not (meta.get("recommendations_blocked") is False
                and meta.get("low_confidence") is False
                and cov.get("sample_experiment") is False
                and cov.get("survivorship_bias") is False
                and cov.get("membership_stale") is False
                and cov.get("delisted_data_gap") is False)


def _events_implied_block(events: dict | None) -> bool:
    """Mirror of retro_factor_lift.events_implied_block — the MINIMUM blocked state the AUTHORITATIVE
    surge_events implies, independent of the (forgeable) factor_lift.coverage. Blocked unless events
    PROVE point-in-time membership AND are not stale AND have no delisted gap. Missing events ⇒
    block. Lets the page catch a forged/drifted coverage that self-reports unblocked."""
    # FAIL-CLOSED on MISSING fields (Codex r18 stop-review): each safety field must be EXPLICITLY
    # the safe value — a forged events omitting membership_stale/delisted_data_gap must not pass.
    ev = events or {}
    if not ev:
        return True
    return not (ev.get("point_in_time_membership") is True
                and ev.get("membership_stale") is False
                and ev.get("delisted_data_gap") is False)


def _strict_floor(art: dict, *keys):
    """Mirror of retro_factor_lift.strict_floor — return the float ONLY if the nested key is
    present + numeric (not bool/None/missing); else None. Fail-closed (no default-to-zero)."""
    cur = art
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        return None
    return float(cur)


def _provenance_stale(art: dict | None, ev_gen, sf_gen, *, kind: str, lift_gen=None) -> bool:
    """Page-level fail-closed RE-ANCHOR (Codex r15): True if `art` does NOT descend from the
    surge_events / surge_features currently shown on this page, or lacks a present+numeric
    liquidity floor. The page previously gated ONLY on each artifact's own stored bit, so a stale /
    cross-run / floor-less factor_lift, module_lift or latest.json (e.g. a dataset dir whose events
    were refreshed but whose lift is stale) would render as if current. `kind` picks the per-
    artifact source schema. Empty art ⇒ not stale (the tab shows its own 'run me first' note)."""
    if not art:
        return False
    src = art.get("source") or {}
    if not ev_gen or src.get("events_generated_at") != ev_gen:
        return True
    if kind in ("lift", "module"):
        if not sf_gen or src.get("features_generated_at") != sf_gen:
            return True
    if kind == "latest":
        # latest must descend from the CURRENT surge_features (Codex r16): chaining to factor_lift
        # ALONE is not enough — if surge_features is rebuilt (EDGAR) under the same events while the
        # lift/latest stay stale, latest still points at that stale lift and would render as fresh.
        # Require BOTH the features token and the loaded-lift chain.
        if not sf_gen or src.get("features_generated_at") != sf_gen:
            return True
        if not lift_gen or src.get("factor_lift_generated_at") != lift_gen:
            return True
    floor_keys = (("source", "min_dollar_vol") if kind == "module"
                  else ("coverage", "liquidity_filter", "min_dollar_vol"))
    return _strict_floor(art, *floor_keys) is None


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
    # Back-compat: older snapshots stored a singular `threshold`; normalize to a
    # `thresholds_hit` list so a clean HEAD checkout renders against either schema.
    if "thresholds_hit" not in df.columns:
        src = df["threshold"] if "threshold" in df.columns else pd.Series([None] * len(df))
        df["thresholds_hit"] = src.apply(lambda t: [t] if isinstance(t, str) and t else [])
    # Each event is ONE physical episode tagged with every threshold it hit.
    df["命中門檻"] = df["thresholds_hit"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else str(x))
    all_thr = sorted({t for x in df["thresholds_hit"] if isinstance(x, list) for t in x})
    thresholds = ["全部", *all_thr]
    pick = st.radio("門檻", thresholds, horizontal=True, key="retro_evt_thr")
    view = df if pick == "全部" else df[df["thresholds_hit"].apply(
        lambda x: isinstance(x, list) and pick in x)]
    view = view.drop(columns=["thresholds_hit"]).sort_values("magnitude_pct", ascending=False)

    st.dataframe(
        view, hide_index=True, use_container_width=True,
        column_config={
            "ticker": "代號",
            "命中門檻": "命中門檻",
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
    # Fail-closed block banner on the factor tab too: a survivorship-blocked or
    # underpowered run must not show VALIDATED/WEAK as actionable here either.
    blocked = _coverage_banner(lift)
    if blocked:
        st.caption("🔒 封鎖中:以下判定僅為**探索性**,不可作為調整權重/prompt 的依據。")
    elif lift.get("low_confidence"):
        st.warning("⚠️ 樣本偏小(暴漲事件 < 30)— 判定僅供參考方向,非結論。")

    # Runway-confound caveat — the position/trend factors' CONTRARIAN verdicts are largely
    # a %-runway artifact (a cheap stock hits a fixed +X% target more easily). Verified by
    # scripts/retro_confound_check.py: within a price-position-matched stratum, price_above_ma200
    # FLIPS to positive while only rvol_ge_2 holds its lift. Do not read "fade momentum".
    st.warning(
        "⚠️ **漲幅(runway)假象**:位置/趨勢因子(`price_above_ma200`、`within_25pct_of_high`、"
        "`macd_positive` 等)的 CONTRARIAN 判定**大部分是 %-漲幅量測假象** —— 便宜/跌深的股票要漲到固定的"
        "「+30/40/50%」本來就比較容易。在「距高點相近」同組內,`price_above_ma200` 會翻為正向;**唯一跨組站得住的"
        "真訊號是 `rvol_ge_2`(放量)**。請勿據此解讀為「動能無效 / 該做反向」。(檢定:`retro_confound_check.py`)")

    labels = ["ALL", *[l for l in tables if l != "ALL"]]
    pick = st.radio("門檻", labels, horizontal=True, key="retro_lift_thr")
    factors = tables[pick].get("factors", [])
    if not factors:
        st.info("此門檻無資料。")
        return

    fdf = pd.DataFrame(factors)
    fdf["ci_low"] = fdf["lift_ci90"].apply(lambda x: x[0] if isinstance(x, list) else None)
    fdf["ci_high"] = fdf["lift_ci90"].apply(lambda x: x[1] if isinstance(x, list) else None)

    # Optional horizon filter (short/mid/long) — match factor to holding window.
    _HZ_LABEL = {"short": "短(數日~2週)", "mid": "中(2週~3月)", "long": "長(3月+)"}
    if "horizon" in fdf.columns and fdf["horizon"].notna().any():
        hz_opts = [h for h in ("short", "mid", "long") if (fdf["horizon"] == h).any()]
        sel = st.multiselect("持有視窗(短/中/長)", hz_opts, default=hz_opts,
                             format_func=lambda h: _HZ_LABEL.get(h, h), key="retro_lift_hz")
        if sel:
            fdf = fdf[fdf["horizon"].isin(sel)]
        if fdf.empty:
            st.info("此視窗無因子。")
            return

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

    has_ev = "expected_value" in fdf.columns
    has_mt = "verdict_mt" in fdf.columns
    fdf = fdf.copy()
    if has_ev:
        fdf["ev_pct"] = fdf["expected_value"] * 100.0

    cols = ["factor", "dimension"]
    if "horizon" in fdf.columns:
        cols.append("horizon")
    cols += ["subfactor", "p_surge", "p_control", "lift"]
    if has_ev:
        cols.append("ev_pct")
    cols += ["support", "verdict"]
    if has_mt:
        cols += ["verdict_mt", "q_value"]

    st.dataframe(
        fdf[cols], hide_index=True, use_container_width=True,
        column_config={
            "factor": "因子",
            "dimension": "維度",
            "horizon": st.column_config.TextColumn(
                "視窗", help="該因子 edge 的持有視窗:short 數日~2週 / mid 2週~3月 / long 3月+"),
            "subfactor": "子項",
            "p_surge": st.column_config.NumberColumn("暴漲前出現率", format="%.2f"),
            "p_control": st.column_config.NumberColumn("隨機出現率", format="%.2f"),
            "lift": st.column_config.NumberColumn(
                "lift", format="%.2f", help="P(因子|暴漲)/P(因子|隨機);與樣本比例無關,是最穩健的 edge 指標。"),
            "ev_pct": st.column_config.NumberColumn(
                "樣本內命中率", format="%.0f%%",
                help="P(暴漲|此因子出現),僅在驗證樣本(暴漲:控制≈1:1)內成立 —— 非真實世界基率(真實暴漲基率低很多)。要比較因子強弱請看 lift。"),
            "support": st.column_config.NumberColumn("樣本"),
            "verdict": "判定(原始)",
            "verdict_mt": st.column_config.TextColumn(
                "判定(FDR)", help="多重檢定(Benjamini-Hochberg)校正後的判定;沒撐過家族 FDR 的正向判定會降一級,避免因子動物園的假發現。"),
            "q_value": st.column_config.NumberColumn(
                "q值", format="%.3f", help="FDR q 值;≤0.10 視為通過家族多重檢定。"),
        })
    st.caption(f"方法:{lift.get('method', '')}")
    if has_mt:
        st.caption("ℹ️ **判定(FDR)** 對整張表所有因子做多重檢定校正:樣本大時顯著因子多能撐過(q≈0);"
                   "樣本小(分門檻/前瞻表)時才會明顯降級。**命中率**是樣本內 P(暴漲|訊號),"
                   "受暴漲:控制比例影響,**不是**真實世界機率 —— 跨因子比較請以 lift 為準。")
    _forward_lift_section(_load("forward_factor_lift.json"))


def _forward_lift_section(fwd: dict | None) -> None:
    """Phase 2 — six-dimension forward lift (incl. Dim3 sentiment / Dim6 options)."""
    st.divider()
    st.subheader("Phase 2 · 六維前向驗證")
    st.caption("每日快照所有過濾倖存者,60-90 天後用實際報酬驗證全六維(含唯二無免費歷史的 "
               "Dim3 情緒 / Dim6 選擇權流)。surger vs 非 surger 為內建對照組。")
    if not fwd or fwd.get("status") == "accumulating":
        n = (fwd or {}).get("resolved_snapshots", 0)
        st.info(f"📈 累積中 — 目前可解析快照 {n} 筆,需累積數週每日掃描才能算前向 lift。")
        return
    if fwd.get("low_confidence"):
        st.warning(f"⚠️ surger 樣本偏小({fwd.get('surgers')}),判定僅供參考。")
    st.caption(f"命中定義 {fwd.get('hit_metric')} · surger {fwd.get('surgers')} / "
               f"非 surger {fwd.get('non_surgers')}(共 {fwd.get('resolved_snapshots')} 筆已解析)")
    fdf = pd.DataFrame(fwd.get("factors", []))
    if fdf.empty:
        return
    st.dataframe(
        fdf[["factor", "dimension", "subfactor", "p_surge", "p_control",
             "lift", "support", "verdict"]],
        hide_index=True, use_container_width=True,
        column_config={
            "factor": "因子", "dimension": "維度", "subfactor": "說明",
            "p_surge": st.column_config.NumberColumn("surger 高分率", format="%.2f"),
            "p_control": st.column_config.NumberColumn("非surger 高分率", format="%.2f"),
            "lift": st.column_config.NumberColumn("lift", format="%.2f"),
            "support": st.column_config.NumberColumn("樣本"),
            "verdict": "判定",
        })


def _modules_tab(mod: dict | None) -> None:
    """Module (factor-combination) lift — which trader archetype precedes surges."""
    st.caption("把因子組成幾套**模組(策略原型)**,驗證暴漲股吻合哪一套。每套模組吻合 = 一個合成"
               "因子,用同一套 lift 引擎對照隨機。定義在 `config/retro_modules.json`,可自行增修。")
    if not mod or not mod.get("tables"):
        st.info("尚無模組驗證。先跑 `scripts/retro_factor_lift.py` 再跑 "
                "`scripts/retro_modules.py`。")
        return
    # Full canonical fail-closed gate (missing/biased metadata on a stale/legacy
    # module_lift → blocked).
    if _gate_blocked(mod):
        st.error(f"⛔ **已封鎖,不可作決策** — 真實原因:{'、'.join(_block_reasons(mod))}。"
                 "模組判定僅供探索。")
    elif mod.get("low_confidence"):
        st.warning(f"⚠️ 樣本偏小(暴漲事件 {mod.get('surger_count')}),判定僅供參考。")
    for w in mod.get("config_warnings", []) or []:
        st.warning(f"⚙️ config:{w}")

    labels = ["ALL", *[l for l in mod["tables"] if l != "ALL"]]
    pick = st.radio("門檻", labels, horizontal=True, key="retro_mod_thr")
    rows = mod["tables"][pick].get("modules", [])
    if not rows:
        st.info("此門檻無資料。")
        return

    mdf = pd.DataFrame(rows)
    bar = mdf.sort_values("lift")
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
        height=320, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=_shared.BG, plot_bgcolor=_shared.PANEL,
        xaxis_title="lift = P(吻合此模組|暴漲) / P(吻合|隨機)", font=dict(color="#d6dae3"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        mdf[["factor", "subfactor", "p_surge", "p_control", "lift", "support", "verdict"]],
        hide_index=True, use_container_width=True,
        column_config={
            "factor": "模組",
            "subfactor": "門檻",
            "p_surge": st.column_config.NumberColumn("暴漲前吻合率", format="%.2f"),
            "p_control": st.column_config.NumberColumn("隨機吻合率", format="%.2f"),
            "lift": st.column_config.NumberColumn("lift", format="%.2f"),
            "support": st.column_config.NumberColumn("吻合數"),
            "verdict": "判定",
        })

    # Each module's constituent factors + how often each condition holds among surgers
    # — shows which factor is the bottleneck dragging a module's match rate down.
    with st.expander("模組組成與因子達成率"):
        for m in mod.get("modules", []):
            st.markdown(f"**{m['name']}** — {m.get('description','')} "
                        f"_(門檻 {m.get('min_factors')}/{m.get('factor_count')})_")
            fd = pd.DataFrame(m.get("factors_detail", []))
            if not fd.empty:
                fd["條件"] = fd.apply(lambda r: f"{r['factor']} = {r['want']}", axis=1)
                st.dataframe(
                    fd[["條件", "p_surge_meets", "n_known"]], hide_index=True,
                    use_container_width=True,
                    column_config={
                        "p_surge_meets": st.column_config.NumberColumn("暴漲前達成率", format="%.2f"),
                        "n_known": st.column_config.NumberColumn("有效樣本"),
                    })


def _block_reasons(meta: dict) -> list:
    """The SPECIFIC reasons a run is blocked (not a generic 'sample experiment'), so the
    banner matches the true cause — survivorship vs coverage vs stale/fallback controls."""
    cov = meta.get("coverage", {}) or {}
    r = []
    if cov.get("survivorship_bias") is not False:
        r.append("倖存者偏差(僅含現役指數成員)")
    if cov.get("sample_experiment") is True:
        r.append(f"宇宙覆蓋不足({cov.get('tickers_scanned')}/{cov.get('intended_universe_size')} 檔)")
    if meta.get("low_confidence") is True:
        r.append(f"樣本偏小(事件 {cov.get('surge_event_count')}、標的 {cov.get('unique_surger_tickers')})")
    if cov.get("membership_stale") is True:
        r.append("會員快照過期(可能漏掉指數加入/剔除,point-in-time 不完整 → 需更新會員資料)")
    if cov.get("delisted_data_gap") is True:
        r.append("下市股資料缺口(完全下市的暴漲股無免費價格 → 殘餘倖存者偏差,需付費資料才解鎖)")
    cm = meta.get("control_match")
    if cm and cm != "threshold-specific":
        r.append(f"對照基線回退({cm})")
    if meta.get("provenance_ok") is False:
        r.append("對照來源與本次跑不符(stale/mismatched)")
    if meta.get("_stale_provenance") is True:
        r.append("與本頁暴漲事件/特徵不同跑次或缺流動性門檻(stale / 缺 floor → fail-closed)")
    if meta.get("_events_gate_violation") is True:
        r.append("自報 coverage 與權威 surge_events 矛盾(宣稱未封鎖但 events 為偏差/過期/下市缺口 → fail-closed)")
    return r or ["閘門 metadata 不完整或不一致(fail-closed)"]


def _coverage_banner(latest: dict) -> bool:
    """Show the coverage/survivorship status; return True if recommendations are blocked."""
    cov = latest.get("coverage", {}) or {}
    # Full canonical fail-closed gate (not just recommendations_blocked): a stale/
    # hand-edited artifact missing or biased on any field renders as blocked.
    blocked = _gate_blocked(latest)
    scanned = cov.get("tickers_scanned")
    intended = cov.get("intended_universe_size")
    cov_txt = (f"{scanned}/{intended} 檔" if intended else f"{scanned} 檔(宇宙未知)")
    if blocked:
        reasons = "、".join(_block_reasons(latest))
        st.error(f"⛔ **已封鎖,不可作決策** — 真實原因:{reasons}。"
                 "**權重/prompt 變更建議不予顯示。** 需 point-in-time 成分 + 跑滿宇宙才解鎖。")
    else:
        st.caption(f"覆蓋:{cov_txt} · 標的 {cov.get('unique_surger_tickers')} · "
                   f"survivorship_bias={cov.get('survivorship_bias')}")
    return blocked


def _recommendations_tab(latest: dict) -> None:
    if not latest:
        st.info("尚無 AI 建議。先跑 `scripts/retro_report.py --provider auto`。")
        return
    blocked = _coverage_banner(latest)
    # Exploratory prose is shown ONLY on a validated override run (not the bit alone),
    # mirroring retro_report._exploratory_ok — a stale artifact can't surface LLM text.
    _cov = latest.get("coverage", {}) or {}
    exploratory = (latest.get("exploratory_override") is True
                   and latest.get("_stale_provenance") is not True   # Codex r18: stale ⇒ no prose
                   and _gate_blocked(latest) is True
                   and latest.get("recommendations_blocked") is True
                   and latest.get("low_confidence") is False
                   and _cov.get("sample_experiment") is False
                   and _cov.get("survivorship_bias") is True)
    if blocked and not exploratory:
        # Untrusted LLM: on a fully-blocked run NONE of its prose is rendered — only
        # the deterministic gate banner + a pointer to the exploratory lift.
        st.info("🔒 此跑次已封鎖,不顯示任何 LLM 生成的敘述/建議。"
                "探索性 lift 請看「因子驗證」分頁(已標示僅供探索)。")
        return
    if exploratory:
        st.warning("🔬 **探索性(偏差樣本)** — 以下為 LLM 探索性敘述;"
                   "權重/prompt 變更建議**永不顯示、不可作決策**(倖存者偏差未消除)。")
    else:
        st.error("⚠️ 以下內容**僅供人工審查,非自動套用**。")

    rep = _extract_report_json(latest.get("llm_report", ""))
    if not rep:
        # When blocked, NEVER fall back to rendering raw LLM output — it could carry
        # actionable advice that bypasses the proposed_changes suppression.
        if blocked:
            st.warning("LLM 回應無法解析;封鎖狀態下不顯示原始輸出。請看「因子驗證」分頁的探索性 lift。")
        else:
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
    if blocked:
        # Hard gate: never present weight/prompt changes as actionable from a
        # sample experiment, even if the model emitted some.
        st.subheader("📝 建議變更")
        st.warning("樣本實驗 — 權重/prompt 變更建議已封鎖,不予顯示。跑完整宇宙後才會出現。")
    elif changes:
        st.subheader("📝 建議變更(供審查)")
        st.dataframe(
            pd.DataFrame(changes), hide_index=True, use_container_width=True)


def render() -> None:
    st.title("🔁 復盤分析 — 暴漲股因子驗證")
    st.caption("挖出真正暴漲過的股票,反推哪些指標在暴漲前真的出現、哪些失效、哪些反向。"
               "本頁只驗證 **Dim1 技術面 + Dim5 板塊/regime**(其餘維度的歷史資料免費源無法回填)。")

    global _CUR_BASE
    opts = _dataset_options()
    if len(opts) > 1:
        labels = [o[0] for o in opts]
        pick = st.radio("資料集", labels, horizontal=True, key="retro_dataset",
                        help="point-in-time = 用『當時』的指數成份股(無倖存者偏差,可作決策);"
                             "現役成員 = 舊探索集(僅含現役成員 → 封鎖)。")
        _CUR_BASE = dict(opts).get(pick, RETRO_DIR)
    else:
        _CUR_BASE = opts[0][1] if opts else RETRO_DIR

    events = _load("surge_events.json")
    features = _load("surge_features.json")
    lift = _load("factor_lift.json")
    latest = _load("latest.json")
    module = _load("module_lift.json")

    if not any([events, lift, latest]):
        st.info("尚未產生復盤資料。依序執行:\n\n"
                "```\npython scripts/retro_surge_label.py --universe sp1500 --lookback-days 730\n"
                "python scripts/retro_reconstruct.py\n"
                "python scripts/retro_factor_lift.py\n"
                "python scripts/retro_report.py --provider auto\n```")
        return

    # FAIL-CLOSED page-level re-anchor (Codex r15): force-block any derived artifact that does not
    # descend from THIS page's surge_events / surge_features, or that lacks a liquidity floor — the
    # tab gates (which read each dict's stored bits) then render the blocked state, so a stale /
    # cross-run / floor-less artifact can never be shown as actionable. Mutating the loaded copies
    # is safe (re-read from disk each render).
    ev_gen = (events or {}).get("generated_at")
    sf_gen = (features or {}).get("generated_at")
    lift_gen = (lift or {}).get("generated_at")
    # If the loaded factor_lift is itself stale, latest (which descends from it) is transitively
    # stale even if its own tokens line up with that stale lift (Codex r16 belt-and-suspenders).
    _lift_stale = bool(lift and _provenance_stale(lift, ev_gen, sf_gen, kind="lift"))
    # AUTHORITATIVE gate (Codex r18): what the surge_events independently imply (survivorship/stale/
    # delisted) — a forged/drifted artifact coverage can't unblock past it.
    _ev_block = _events_implied_block(events)
    _stale = []
    for art, kind, name in ((lift, "lift", "因子驗證"), (module, "module", "模組驗證"),
                            (latest, "latest", "AI 建議")):
        stale = _provenance_stale(art, ev_gen, sf_gen, kind=kind, lift_gen=lift_gen)
        if kind == "latest" and _lift_stale:
            stale = True
        # forged/inconsistent gate: events say blocked but the artifact's self-reported coverage
        # claims unblocked → force-block (Codex r18 forge-tamper).
        forged_gate = bool(_ev_block and art and not _gate_blocked(art))
        if art and (stale or forged_gate):
            art["recommendations_blocked"] = True
            if stale:
                art["_stale_provenance"] = True
            if forged_gate:
                art["_events_gate_violation"] = True
            # also revoke any actionable opt-in (Codex r18): a force-blocked artifact must not keep
            # its exploratory_override and leak LLM prose through the exploratory branch.
            art["exploratory_override"] = False
            _stale.append(name)
    if _stale:
        st.error("⛔ 下列分頁的資料與本頁的暴漲事件/特徵 **不一致**(不同跑次／缺流動性門檻／gate 與 "
                 f"events 矛盾),已封鎖:**{'、'.join(_stale)}**。請重跑 retro pipeline 讓 "
                 "事件→特徵→lift 同源後再看。")

    t1, t2, t3, t4 = st.tabs(["暴漲事件", "因子驗證", "模組驗證", "AI 建議"])
    with t1:
        _events_tab(events or {})
    with t2:
        _lift_tab(lift or {}, features or {})
    with t3:
        _modules_tab(module)
    with t4:
        _recommendations_tab(latest or {})
