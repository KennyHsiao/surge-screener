"""美股 · 動能期權 — momentum-options decision support (signals, not execution).

Per-ticker entry checklist + suggested OTM call (Δ0.3-0.4) with Greeks + IV context
+ a GO/WAIT/AVOID verdict, plus a ranking of the day's candidates. Engine lives in
scripts/momentum_options.py. Delayed ~15min data → EOD swing screening, not 0DTE.
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

_VERDICT_STYLE = {
    "GO": ("🟢 GO — 進場條件成立", st.success),
    "WAIT": ("🟡 WAIT — 蓄勢中,等觸發", st.warning),
    "AVOID": ("🔴 AVOID — 別進", st.error),
}

_CHECK_LABELS = {
    "bollinger_squeeze": "布林通道壓縮 (蓄勢)",
    "breakout_on_volume": "帶量突破壓力位",
    "rvol_ge_2": "相對量 RVOL ≥ 2×",
    "price_above_vwap": "價格站上 VWAP",
    "iv_low_base": "IV 處於低基期 (IVP<30)",
    "contract_in_sweet_spot": "Δ0.3–0.4 甜蜜點合約",
    "contract_liquid": "合約流動性足夠",
    "earnings_clear": "DTE 內無財報 (避 IV crush)",
    "breakeven_reachable": "預期波動可達損益兩平",
    "regime_risk_on": "大盤 risk-on",
}


@st.cache_data(ttl=900, show_spinner=False)
def _chart_data(ticker: str):
    """~4mo daily OHLCV + Bollinger(20,2) + 20d VWAP for the chart. Cached 15min."""
    import yfinance as yf
    df = yf.Ticker(ticker).history(period="4mo", auto_adjust=False)
    if df is None or df.empty:
        return None
    df = df.tail(80).copy()
    ma = df["Close"].rolling(20).mean()
    sd = df["Close"].rolling(20).std(ddof=0)
    df["bb_up"], df["bb_mid"], df["bb_lo"] = ma + 2 * sd, ma, ma - 2 * sd
    typ = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"] = (typ * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
    return df


def _render_checklist(checks: dict) -> None:
    items = list(checks.items())
    cols = st.columns(2)
    for i, (key, ok) in enumerate(items):
        label = _CHECK_LABELS.get(key, key)
        cols[i % 2].markdown(f"{'✅' if ok else '❌'} {label}")


def _render_contract(c: dict, opts: dict) -> None:
    if not c:
        st.info("找不到合適的 OTM 合約(可能無 2–3 週到期、流動性不足或資料缺失)。")
        return
    st.markdown(f"#### 建議合約 — ${c.get('strike')} Call · {opts.get('expiry')} ({opts.get('dte_days')} DTE)")
    g = st.columns(4)
    g[0].metric("Delta", c.get("delta"), help="0.3–0.4 為高槓桿且具勝率的甜蜜點")
    g[1].metric("Gamma", c.get("gamma"), help="加速度;OTM→ATM 時最大")
    g[2].metric("Theta/日", c.get("theta"), help="每日時間價值耗損")
    g[3].metric("Vega", c.get("vega"), help="IV 每變動 1% 的影響")
    m = st.columns(4)
    m[0].metric("權利金(中價)", c.get("mid_premium"))
    m[1].metric("損益兩平", c.get("breakeven"))
    m[2].metric("預期波動", opts.get("expected_move"))
    m[3].metric("成交量/OI", f"{c.get('volume')} / {c.get('open_interest')}")
    flags = []
    if c.get("in_delta_sweet_spot"):
        flags.append("✅ 在 Δ0.3–0.4 甜蜜點")
    else:
        flags.append(f"⚠️ Δ={c.get('delta')} 不在甜蜜點(已取最接近)")
    flags.append(("✅ 流動性 OK" if c.get("liquid") else "⚠️ 流動性偏弱")
                 + f"(依據:{c.get('liquidity_basis', '?')})")
    if c.get("iv_estimated"):
        flags.append("⚠️ 鏈上 IV 異常,Greeks 以實現波動率估算")
    st.caption(" · ".join(flags))


def _render_chart(ticker: str, tech: dict) -> None:
    df = _chart_data(ticker)
    if df is None:
        return
    st.markdown("#### 價格 / 布林通道 / VWAP / 量")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                 low=df["Low"], close=df["Close"], name="價格",
                                 increasing_line_color="#00CC96",
                                 decreasing_line_color="#EF553B"))
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_up"], name="BB 上軌",
                             line=dict(color="#888", width=1)))
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_lo"], name="BB 下軌",
                             line=dict(color="#888", width=1), fill="tonexty",
                             fillcolor="rgba(136,136,136,0.08)"))
    fig.add_trace(go.Scatter(x=df.index, y=df["vwap"], name="VWAP",
                             line=dict(color="#FFA15A", width=1.5, dash="dot")))
    res = tech.get("resistance_20d")
    if res:
        fig.add_hline(y=res, line_dash="dash", line_color="#AB63FA",
                      annotation_text=f"20d 壓力 {res}")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0))
    st.plotly_chart(fig, use_container_width=True)


def _per_ticker(mo) -> None:
    ticker = st.text_input("代號", value="NVDA").strip().upper().lstrip("$")
    if not st.button("分析動能期權", type="primary"):
        return
    if not ticker:
        st.info("請輸入代號。")
        return
    with st.spinner(f"分析 {ticker} 中…"):
        res = mo.analyze(ticker)
    if not res.get("available"):
        st.warning(f"無法分析 {ticker}:{res.get('reason', '未知原因')}")
        return

    label, fn = _VERDICT_STYLE.get(res["verdict"], (res["verdict"], st.info))
    fn(f"**{label}**")
    for r in res.get("reasons", []):
        st.caption("· " + r)

    iv = res["iv"]
    h = st.columns(4)
    h[0].metric("現價", res.get("spot"))
    h[1].metric("ATM IV", iv.get("atm_iv"),
                help="盤中鏈上 IV;若異常則以實現波動率估算" if iv.get("atm_iv_estimated") else None)
    h[2].metric("IV 百分位", iv.get("iv_percentile"),
                help=f"來源:{iv.get('iv_percentile_source')}。<30 為低基期,適合埋伏;>80 慎防 IV crush")
    h[3].metric("實現波動率", iv.get("realized_vol"))
    if iv.get("iv_percentile_source", "").startswith("realized_vol"):
        st.caption("ℹ️ IV 百分位目前以**實現波動率**代理;每日快照累積滿後會切換為真實 IV Rank/Percentile。")

    st.markdown("#### 進場檢查清單")
    _render_checklist(res["checklist"])

    _render_contract(res["options"].get("suggested_contract"), res["options"])
    _render_chart(ticker, res["technical"])

    earn = res.get("earnings") or {}
    if earn.get("date"):
        warn = " ⚠️ 在 DTE 內!" if earn.get("within_dte") else ""
        st.caption(f"下次財報:{earn.get('date')}(還有 {earn.get('days_away')} 天){warn}")

    _render_playbook()
    st.caption("⚠️ " + res.get("notes", ""))


def _render_playbook() -> None:
    pb = _ROOT / "content" / "momentum_options_playbook.md"
    if pb.is_file():
        with st.expander("📖 playbook — 進出場 / 轉倉 紀律", expanded=False):
            st.markdown(pb.read_text(encoding="utf-8"))


def _render_ranking(mo) -> None:
    scored = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json"))
    tickers = [c.get("ticker") for c in (scored or {}).get("all_scored", []) if c.get("ticker")]
    if not tickers:
        st.info("尚無 `scored_candidates.json`,請先執行管線以取得當日候選股清單。")
        return
    st.caption(f"對當日 {len(tickers)} 檔候選股跑動能期權判斷(用快取,首次較慢):")
    if not st.button("掃描排行", type="primary"):
        return
    rows = []
    order = {"GO": 0, "WAIT": 1, "AVOID": 2}
    prog = st.progress(0.0)
    for i, t in enumerate(tickers):
        try:
            r = mo.analyze(t)
            if r.get("available"):
                c = r["options"].get("suggested_contract") or {}
                rows.append({
                    "代號": t, "判斷": r["verdict"],
                    "通過閘": sum(1 for v in r["checklist"].values() if v),
                    "IV百分位": r["iv"].get("iv_percentile"),
                    "Δ": c.get("delta"), "履約價": c.get("strike"),
                    "突破": "✅" if r["checklist"]["breakout_on_volume"] else "",
                })
        except Exception:
            pass
        prog.progress((i + 1) / len(tickers))
    prog.empty()
    if not rows:
        st.info("沒有可用結果。")
        return
    df = pd.DataFrame(rows).sort_values(
        ["判斷", "通過閘"], key=lambda s: s.map(order) if s.name == "判斷" else s,
        ascending=[True, False])
    st.dataframe(df, hide_index=True, use_container_width=True)


def render() -> None:
    st.header("🚀 美股動能期權")
    st.caption("動能突破 + OTM Call(Δ0.3–0.4)決策參考。免費 yfinance(延遲~15分),"
               "EOD 波段訊號,非即時/非投資建議。")
    from scripts import momentum_options as mo  # lazy

    tab_ticker, tab_rank = st.tabs(["個股分析", "當日候選排行"])
    with tab_ticker:
        _per_ticker(mo)
    with tab_rank:
        _render_ranking(mo)
