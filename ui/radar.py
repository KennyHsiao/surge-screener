"""美股 · 雷達 / Radar — 風險(下行)＋反轉(觸底)雙讀,同一清單。

把兩個雷達放進同一張清單:每檔同時顯示【風險分/狀態】(Risk Guard,該不該降風險)與
【反轉分/狀態】(Reversal Radar,下跌後是否觸底反轉)。上方頁籤只用來篩選聚焦:
全部 / 風險警示(REDUCE·EXIT) / 反轉候選(TURNING·REVERSAL) / 兩者共現。

反轉為探索性(因子尚未驗證),非投資建議;COT 為落後確認,不納入反轉領先分。
通知(TURNING 以上)由 scripts/reversal_radar_scan.py --notify 推送(Telegram)。
"""

import sys

import pandas as pd
import streamlit as st

from . import _shared
from . import risk_guard as rgui   # reuse risk status maps / _money / _collect / _analyze / _tab_portfolio

_SCRIPTS = str(_shared.DATA_DIR / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

# Reversal status ladder (escalating reversal conviction; tokens only, no alarm reds).
_REV_COLOR = {"NONE": _shared.MUTED, "STABILIZING": _shared.AMBER, "TURNING": _shared.CYAN,
              "REVERSAL": _shared.GREEN, "N/A": _shared.MUTED, "DATA_GAP": _shared.MUTED}
_REV_EMOJI = {"NONE": "⚪", "STABILIZING": "🟡", "TURNING": "🟦", "REVERSAL": "🟢",
              "N/A": "➖", "DATA_GAP": "⚪"}
_REV_ZH = {"NONE": "無明顯反轉", "STABILIZING": "止穩", "TURNING": "轉強",
           "REVERSAL": "反轉(探索)", "N/A": "非回檔中", "DATA_GAP": "資料不足"}
_REV_RANK = {"REVERSAL": 3, "TURNING": 2, "STABILIZING": 1, "DATA_GAP": 1, "NONE": 0, "N/A": 0}

_LIVE_CAP = 40   # cap live dual-compute so the page stays responsive


@st.cache_data(ttl=600, show_spinner=False)
def _rev(tickers: tuple, require_pullback: bool) -> dict:
    import reversal_radar
    return reversal_radar.analyze_reversal(list(tickers), require_pullback=require_pullback)


def _rev_chip(status: str) -> str:
    return _shared.chip(f"{_REV_EMOJI.get(status, '')} {status} · {_REV_ZH.get(status, '')}",
                        _REV_COLOR.get(status, _shared.MUTED))


def _beaten_down_tickers() -> list[str]:
    """Reversal discovery universe = the precomputed scan's candidates (read latest.json,
    no live 150-name scan)."""
    data = _shared.load_json(str(_shared.REPORTS_DIR / "reversal_radar" / "latest.json")) or {}
    return [c.get("ticker") for c in (data.get("candidates") or []) if c.get("ticker")]


def _collect(source: str, manual: str) -> tuple[list[str], bool]:
    if source == "反轉候選(掃描)":
        return _beaten_down_tickers(), False
    return rgui._collect(source, manual)


def _is_conf(rrow: dict, vrow: dict) -> bool:
    return (rrow.get("status") in ("REDUCE", "EXIT")
            and vrow.get("status") in ("TURNING", "REVERSAL"))


# ───────────────────────── dual-read table ─────────────────────────
def _dual_df(risk: dict, rev: dict) -> pd.DataFrame:
    rmap = {r["ticker"]: r for r in (risk.get("rows") or [])}
    vmap = {r["ticker"]: r for r in (rev.get("rows") or [])}
    rows = []
    for t in dict.fromkeys(list(rmap) + list(vmap)):
        rr, vr = rmap.get(t, {}), vmap.get(t, {})
        rstat, vstat = rr.get("status", "—"), vr.get("status", "—")
        lv = vr.get("lead_vs_confirm") or {}
        rows.append({
            "代號": t,
            "風險": f"{rgui._STATUS_EMOJI.get(rstat, '')} {rstat}",
            "風險分": rr.get("risk_score"),
            "反轉": f"{_REV_EMOJI.get(vstat, '')} {vstat}",
            "反轉分": vr.get("reversal_score"),
            "信心": vr.get("data_confidence"),
            "搶在COT前": "✅" if lv.get("front_run") else "",
            "共現": "🔴" if _is_conf(rr, vr) else "",
            "主要訊號": " · ".join((vr.get("primary_signals") or rr.get("primary_reasons") or [])[:3]),
            "_rrank": rgui._STATUS_RANK.get(rstat, 0), "_vrank": _REV_RANK.get(vstat, 0),
            "_conf": 1 if _is_conf(rr, vr) else 0,
        })
    return pd.DataFrame(rows)


def _render_table(df: pd.DataFrame, view: str) -> None:
    if df.empty:
        st.info("沒有可顯示的標的。")
        return
    d = df
    if view == "風險警示":
        d = df[df["風險"].str.contains("REDUCE|EXIT")]
        d = d.sort_values(["_rrank", "風險分"], ascending=False)
    elif view == "反轉候選":
        d = df[df["反轉"].str.contains("TURNING|REVERSAL")]
        d = d.sort_values(["_vrank", "反轉分"], ascending=False)
    elif view == "兩者共現":
        d = df[df["_conf"] == 1].sort_values(["反轉分"], ascending=False)
    else:
        d = df.sort_values(["_conf", "_vrank", "_rrank"], ascending=False)
    if d.empty:
        st.caption("此篩選下沒有標的。")
        return
    show = d.drop(columns=[c for c in ("_rrank", "_vrank", "_conf") if c in d.columns])

    def _tint(row):
        out = []
        for col in row.index:
            if col == "風險":
                c = rgui._STATUS_COLOR.get(row["風險"].split()[-1], _shared.MUTED)
                out.append(f"background-color:{c}22")
            elif col == "反轉":
                c = _REV_COLOR.get(row["反轉"].split()[-1], _shared.MUTED)
                out.append(f"background-color:{c}22")
            else:
                out.append("")
        return out
    try:
        styled = show.style.apply(_tint, axis=1)
    except Exception:  # noqa: BLE001
        styled = show
    st.dataframe(styled, hide_index=True, use_container_width=True, column_config={
        "風險分": st.column_config.ProgressColumn("風險分", min_value=0, max_value=100, format="%d"),
        "反轉分": st.column_config.ProgressColumn("反轉分", min_value=0, max_value=100, format="%d"),
        "主要訊號": st.column_config.TextColumn("主要訊號", width="large")})
    st.caption("風險分↑=越該降風險;反轉分↑=越像下跌後觸底反轉(探索性)。🔴共現=曾高風險下跌、現轉強。"
               "✅搶在COT前=反轉領先且 COT 尚未確認。")


def _bar(labels, scores, caps, color):
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Bar(x=caps, y=labels, orientation="h", marker_color=_shared.PANEL,
                         hoverinfo="skip"))
    fig.add_trace(go.Bar(x=scores, y=labels, orientation="h", marker_color=color,
                         text=scores, textposition="auto"))
    fig.update_layout(barmode="overlay", height=240, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e6e9ef"}, showlegend=False,
                      yaxis={"categoryorder": "array", "categoryarray": labels[::-1]})
    st.plotly_chart(fig, use_container_width=True)


def _render_detail(risk: dict, rev: dict) -> None:
    rmap = {r["ticker"]: r for r in (risk.get("rows") or [])}
    vmap = {r["ticker"]: r for r in (rev.get("rows") or [])}
    tickers = list(dict.fromkeys(list(rmap) + list(vmap)))
    if not tickers:
        st.info("沒有可顯示的標的。")
        return
    pick = st.selectbox("選擇代號", tickers, key="radar_detail_pick")
    rr, vr = rmap.get(pick, {}), vmap.get(pick, {})
    cL, cR = st.columns(2)
    with cL:
        st.markdown("**🛡 風險(下行)**　" + rgui._status_chip(rr.get("status", "—")) if rr else "**🛡 風險**　—",
                    unsafe_allow_html=True)
        if rr:
            _bar(["Market", "Price", "Options", "Sector", "Position", "COT", "DataQ"],
                 [rr.get("market_score", 0), rr.get("price_score", 0), rr.get("options_score", 0),
                  rr.get("sector_score", 0), rr.get("position_score", 0), rr.get("cot_score", 0),
                  rr.get("data_quality_score", 0)], [20, 25, 20, 15, 10, 5, 5],
                 rgui._STATUS_COLOR.get(rr.get("status"), _shared.MUTED))
            for x in (rr.get("primary_reasons") or [])[:5]:
                st.markdown(f"- {x}")
    with cR:
        st.markdown("**↩ 反轉(觸底)**　" + _rev_chip(vr.get("status", "—")) if vr else "**↩ 反轉**　—",
                    unsafe_allow_html=True)
        if vr and vr.get("status") not in ("N/A", "DATA_GAP"):
            _bar(["結構", "動能", "期權", "板塊", "內部人", "分析師"],
                 [vr.get("structure_score", 0), vr.get("momentum_score", 0), vr.get("options_score", 0),
                  vr.get("sector_score", 0), vr.get("insider_score", 0), vr.get("analyst_score", 0)],
                 [22, 22, 18, 14, 12, 12], _REV_COLOR.get(vr.get("status"), _shared.MUTED))
            for x in (vr.get("primary_signals") or [])[:5]:
                st.markdown(f"- {x}")
        elif vr:
            st.caption({"N/A": "非回檔中,不適用(僅對下跌一段的股票評反轉)。",
                        "DATA_GAP": "資料不足,無法評估反轉。"}.get(vr.get("status"), "—"))
    if _is_conf(rr, vr):
        st.warning("🔴 **兩者共現**:此檔曾被風險雷達標為高風險(下跌),現反轉雷達轉強 — 落刀見底的觀察點(探索性,非建議)。")
    lv = (vr or {}).get("lead_vs_confirm") or {}
    if lv.get("front_run"):
        st.info("✅ **搶在 COT 前**:反轉領先分已高,但 COT(慢錢)尚未確認。COT 為落後訊號,不用等它。")
    st.caption((rev.get("exploratory_gate") or {}).get("reason", "")
               + "　COT:" + ((rev.get("cot_confirmation") or {}).get("note") or ""))


def _render_sources(risk: dict, rev: dict) -> None:
    label = {"technical": "技術", "reversal_signals": "反轉訊號", "options": "期權",
             "sector": "板塊", "insider": "內部人", "analyst": "分析師", "cot": "COT",
             "regime": "大盤 regime", "positions": "IBKR 持倉", "options_flow": "異常流"}
    rows = []
    for tag, src in (("風險雷達", risk.get("data_sources") or {}), ("反轉雷達", rev.get("data_sources") or {})):
        for k, v in src.items():
            rows.append({"雷達": tag, "來源": label.get(k, k),
                         "狀態": "✅ 可用" if v not in ("missing", None) else "⚠️ 缺", "值": v})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    eg = rev.get("exploratory_gate") or {}
    st.caption(f"反轉探索 gate:blocked={eg.get('blocked')} · {eg.get('reason', '')}")
    st.caption("通知:`python scripts/reversal_radar_scan.py --notify`(TURNING 以上 → Telegram)。")


# ───────────────────────── entry ─────────────────────────
def render() -> None:
    st.header("📡 雷達 / Radar")
    st.caption("風險(下行)＋反轉(觸底)雙讀,同一清單。反轉為探索性、非投資建議;COT 為落後確認,不納入反轉領先分。")

    # 跨頁 handoff(作戰台 📡 按鈕):一次性 radar_handoff,pop 後在 widget
    # 實例化前播種「手動輸入 + 該代號」— 有 key 的 widget 會無視 default=/
    # value=,殘留狀態須直接覆寫(同 stock_checkup 的單一來源模式)。
    handoff = st.session_state.pop("radar_handoff", None)
    if "radar_source" not in st.session_state or handoff:
        st.session_state["radar_source"] = "手動輸入"
    if "radar_manual" not in st.session_state:
        st.session_state["radar_manual"] = "INTC, PYPL, NKE, NVDA, AMD"
    if handoff:
        st.session_state["radar_manual"] = handoff
        # 前次掃描結果是別組代號的,handoff 後若不清會顯示在新代號下方(stale)。
        # 清掉 → 跳轉後落在「按掃描雙讀」提示,使用者主動掃新標的。
        for k in ("radar_risk", "radar_rev", "radar_detail_pick"):
            st.session_state.pop(k, None)
    c1, c2 = st.columns([2, 1])
    source = c1.segmented_control(
        "來源", ["手動輸入", "Watchlist", "Screener 候選", "反轉候選(掃描)", "IBKR 持倉"],
        key="radar_source")
    manual = ""
    if source == "手動輸入":
        manual = c1.text_input("代碼(逗號/空白分隔)", key="radar_manual")
    include_pos = c2.toggle("計入 IBKR 持倉風險", value=(source == "IBKR 持倉"), key="radar_inc_pos")

    tickers, src_pos = _collect(source, manual)
    include_positions = include_pos or src_pos
    if not tickers:
        st.info("此來源目前沒有標的(反轉候選需先跑 reversal_radar_scan.py;IBKR 需先 reconcile)。可改用「手動輸入」。")
        return
    capped = len(tickers) > _LIVE_CAP
    if capped:
        tickers = tickers[:_LIVE_CAP]

    if st.button(f"📡 掃描雙讀({len(tickers)} 檔)" + ("（已截前 40）" if capped else ""),
                 key="radar_run", type="primary"):
        with st.spinner(f"雙讀掃描 {len(tickers)} 檔(風險＋反轉,首次較慢)…"):
            st.session_state["radar_risk"] = rgui._analyze(tuple(tickers), include_positions)
            st.session_state["radar_rev"] = _rev(tuple(tickers), True)

    risk, rev = st.session_state.get("radar_risk"), st.session_state.get("radar_rev")
    if not risk or not rev:
        st.caption("選好來源後按「掃描雙讀」。")
        return

    df = _dual_df(risk, rev)
    rsum, vsum = risk.get("summary") or {}, rev.get("summary") or {}
    conf_n = int((df["_conf"] == 1).sum()) if not df.empty else 0
    top = st.columns(4)
    _shared.metric_card(top[0], "風險警示檔數", str(rsum.get("high_risk", 0)),
                        help="REDUCE / EXIT")
    _shared.metric_card(top[1], "反轉候選檔數", str(vsum.get("reversal_or_turning", 0)),
                        help="TURNING / REVERSAL(探索性)")
    _shared.metric_card(top[2], "兩者共現", str(conf_n), help="曾高風險下跌、現轉強")
    _shared.metric_card(top[3], "搶在 COT 前", str(vsum.get("front_run", 0)))

    t1, t2, t3, t4 = st.tabs(["雙讀清單", "單檔明細", "組合風控", "資料來源"])
    with t1:
        view = st.segmented_control("顯示", ["全部", "風險警示", "反轉候選", "兩者共現"],
                                    default="全部", key="radar_view", label_visibility="collapsed")
        _render_table(df, view or "全部")
    with t2:
        _render_detail(risk, rev)
    with t3:
        rgui._tab_portfolio(risk)
    with t4:
        _render_sources(risk, rev)
