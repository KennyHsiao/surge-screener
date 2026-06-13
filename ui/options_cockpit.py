"""美股 · 期權作戰台 (Options Cockpit) — the canonical pre-trade options page.

A single-screen decision cockpit whose LAYOUT follows the order a discretionary
swing trader actually reads an options idea:

    判定 (verdict) → 方向 (directional bias) → 波動 (IV regime)
    → 價格圖 + 預期波動錐 → 建議合約 + 互動損益圖 → 進場檢查清單
    → 期權鏈量分佈 / IV-Rank 走勢

DESIGN INTENT (read-only decision support — never an order ticket):
  * The screen and ALL the math are real: the P/L payoff diagram, Greeks-aware
    repricing, probability-of-profit and expected-move are computed locally with
    a self-contained Black-Scholes pricer (no paid feed).
  * Everything the screen needs is declared in the ``CockpitData`` contract.
    ``_live_provider`` assembles it from the real pipeline (momentum_options +
    options_free + iv_history); ``_demo_provider`` is the deterministic mock
    fallback used only when live data can't be fetched.

This page supersedes 動能期權 (its verdict / checklist / contract now live here).
動能期權's engine (scripts/momentum_options.py) remains the data source.
"""

from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Shared options math — the SAME Black-Scholes source as the engine.
try:
    from scripts import options_analytics as _ana
except Exception:  # robust to import context
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "options_analytics", _ROOT / "scripts" / "options_analytics.py")
    _ana = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_ana)

# Design tokens — single source in ui/_shared.py (Plotly + chips share them).
_GREEN, _RED, _ACCENT = _shared.GREEN, _shared.RED, _shared.ACCENT
_AMBER, _BLUE, _MUTED, _PANEL = _shared.AMBER, _shared.BLUE, _shared.MUTED, _shared.PANEL
_RISK_FREE = _ana.R_FREE  # single source shared with the engine.


# ─────────────────────────────────────────────────────────────────────────────
# DATA CONTRACT — the seam between screen and backend.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Contract:
    strike: float | None
    expiry: str
    dte: int
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    mid_premium: float | None   # per-share; x100 = per-contract $
    iv: float | None            # decimal, e.g. 0.42
    volume: int
    open_interest: int
    spread_pct: float | None    # bid/ask width as % of mid
    executable: bool            # two-sided quote present
    in_sweet_spot: bool         # Δ in 0.3–0.4

    @property
    def breakeven(self) -> float | None:
        if self.strike is None or self.mid_premium is None:
            return None
        return round(self.strike + self.mid_premium, 2)

    @property
    def payoffable(self) -> bool:
        return all(isinstance(v, (int, float)) for v in (self.strike, self.mid_premium, self.iv)) \
            and (self.iv or 0) > 0 and self.dte > 0


@dataclass
class CockpitData:
    ticker: str
    spot: float
    day_change_pct: float
    regime: str                 # "risk_on" | "risk_off" | "neutral"
    verdict: str                # "GO" | "WAIT" | "AVOID"
    verdict_reasons: list[str]
    # 方向
    trend: str
    rvol: float | None
    above_vwap: bool
    breakout: bool
    resistance_20d: float | None
    cp_vol_ratio: float | None
    put_call_ratio: float | None
    # 波動
    atm_iv: float | None        # decimal
    iv_rank: float | None       # 0–100; None while accumulating
    iv_percentile: float | None
    realized_vol: float | None
    iv_rank_source: str         # "iv_history" | "realized_vol_proxy"
    iv_rank_accumulating: bool
    iv_rank_n_days: int
    # catalysts
    earnings_date: str | None
    earnings_days_away: int | None
    earnings_within_dte: bool
    # series
    chart: pd.DataFrame
    iv_history: pd.DataFrame
    chain: pd.DataFrame
    contract: Contract | None
    checklist: dict[str, bool] = field(default_factory=dict)
    is_demo: bool = True


_CHECK_LABELS = {
    "bollinger_squeeze": "布林通道壓縮 (蓄勢)",
    "breakout_on_volume": "帶量突破壓力位",
    "rvol_ge_2": "相對量 RVOL ≥ 2×",
    "price_above_vwap": "價格站上 VWAP",
    "iv_low_base": "IV 處於低基期 (IVR<30)",
    "contract_in_sweet_spot": "Δ0.3–0.4 甜蜜點合約",
    "contract_liquid": "合約流動性足夠",
    "earnings_clear": "DTE 內無財報 (避 IV crush)",
    "breakeven_reachable": "預期波動可達損益兩平",
    "regime_risk_on": "大盤 risk-on",
}

_VERDICT_STYLE = {
    "GO": ("🟢 GO — 進場條件成立", st.success, _GREEN),
    "WAIT": ("🟡 WAIT — 蓄勢中,等觸發", st.warning, _AMBER),
    "AVOID": ("🔴 AVOID — 別進", st.error, _RED),
}


# ─────────────────────────────────────────────────────────────────────────────
# Formatting guards (optional fields can be None on real data)
# ─────────────────────────────────────────────────────────────────────────────
def _f(x, spec="{:.2f}", dash="—") -> str:
    return spec.format(x) if isinstance(x, (int, float)) else dash


def _pct(x, dash="—") -> str:
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else dash


# ─────────────────────────────────────────────────────────────────────────────
# Black–Scholes — single shared source (scripts/options_analytics.py)
# ─────────────────────────────────────────────────────────────────────────────
_ncdf = _ana.ncdf                  # scalar→float, array→ndarray
_bs_call = _ana.bs_call_value      # vectorized call value
_prob_of_profit = _ana.prob_of_profit
_expected_move = _ana.expected_move


# ─────────────────────────────────────────────────────────────────────────────
# LIVE provider — assembles CockpitData from the real pipeline.
# ─────────────────────────────────────────────────────────────────────────────
def _to_float(x) -> float | None:
    try:
        v = float(x)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _trend_label(tech: dict) -> str:
    px, ma20, ma50 = tech.get("price"), tech.get("ma20"), tech.get("ma50")
    if px and ma20 and ma50 and px > ma20 >= ma50:
        return "上升"
    if px and ma20 and px < ma20:
        return "回檔/下行"
    return "震盪"


def _load_iv_series(ticker: str) -> pd.DataFrame:
    safe = "".join(c for c in ticker.upper() if c.isalnum() or c in "-._")
    raw = _shared.load_json(str(_shared.REPORTS_DIR / "iv_history" / f"{safe}.json"))
    series = (raw or {}).get("series", {})
    if not series:
        return pd.DataFrame(columns=["date", "iv"])
    items = sorted(series.items())
    return pd.DataFrame({"date": pd.to_datetime([d for d, _ in items]),
                         "iv": [float(v) for _, v in items]})


@st.cache_data(ttl=900, show_spinner=False)
def _live_provider(ticker: str) -> CockpitData | None:
    """Build CockpitData from real pipeline outputs. Returns None if unavailable."""
    from scripts import iv_history as ivh  # lazy
    from scripts import momentum_options as mo
    from scripts import options_free as of

    from . import momentum_options as mo_ui  # reuse the cached chart helper

    res = mo.analyze(ticker)
    if not res.get("available"):
        return None

    chart = mo_ui._chart_data(ticker)
    if chart is None or chart.empty:
        return None
    closes = chart["Close"].to_numpy(dtype=float)
    day_chg = float((closes[-1] / closes[-2] - 1) * 100) if len(closes) >= 2 else 0.0

    tech = res.get("technical", {})
    ivd = res.get("iv", {})
    opt = res.get("options", {})
    earn = res.get("earnings") or {}
    reg = res.get("regime") or {}

    # options_free: chain (vol-by-strike) + flow ratios (best-effort).
    cp_ratio = put_call = None
    chain_rows: list = []
    try:
        ofd = of.analyze_options(ticker)
        if ofd.get("available"):
            d6a = ofd.get("details", {}).get("6a", {})
            cp_ratio = _to_float(d6a.get("call_put_volume_ratio"))
            put_call = _to_float(d6a.get("put_call_ratio"))
            chain_rows = ofd.get("chain_summary", []) or []
    except Exception:
        pass
    chain = (pd.DataFrame(chain_rows) if chain_rows
             else pd.DataFrame(columns=["strike", "call_vol", "put_vol", "call_oi"]))

    ivp = ivh.iv_percentile(ticker, ivd.get("atm_iv"))
    accumulating = bool(ivp.get("accumulating"))

    sc = opt.get("suggested_contract")
    contract = None
    if sc:
        contract = Contract(
            strike=_to_float(sc.get("strike")), expiry=opt.get("expiry") or "",
            dte=int(opt.get("dte_days") or sc.get("dte_days") or 0),
            delta=sc.get("delta"), gamma=sc.get("gamma"), theta=sc.get("theta"),
            vega=sc.get("vega"), mid_premium=_to_float(sc.get("mid_premium")),
            iv=_to_float(sc.get("iv")) or _to_float(ivd.get("atm_iv")),
            volume=int(sc.get("volume") or 0), open_interest=int(sc.get("open_interest") or 0),
            spread_pct=_to_float(sc.get("spread_pct")),
            executable=bool(sc.get("executable")),
            in_sweet_spot=bool(sc.get("in_delta_sweet_spot")),
        )

    regime = ("risk_on" if reg.get("risk_on") is True
              else "risk_off" if reg.get("risk_on") is False else "neutral")

    return CockpitData(
        ticker=res["ticker"], spot=res["spot"], day_change_pct=round(day_chg, 2),
        regime=regime, verdict=res["verdict"], verdict_reasons=res.get("reasons", [])[:4],
        trend=_trend_label(tech), rvol=_to_float(tech.get("rvol")),
        above_vwap=bool(tech.get("price_above_vwap")),
        breakout=bool(tech.get("breakout_above_resistance")),
        resistance_20d=_to_float(tech.get("resistance_20d")),
        cp_vol_ratio=cp_ratio, put_call_ratio=put_call,
        atm_iv=_to_float(ivd.get("atm_iv")), iv_rank=ivp.get("rank"),
        iv_percentile=_to_float(ivd.get("iv_percentile")),
        realized_vol=_to_float(ivd.get("realized_vol")),
        iv_rank_source="iv_history" if not accumulating else "realized_vol_proxy",
        iv_rank_accumulating=accumulating, iv_rank_n_days=int(ivp.get("n_days") or 0),
        earnings_date=earn.get("date"), earnings_days_away=earn.get("days_away"),
        earnings_within_dte=bool(earn.get("within_dte")),
        chart=chart, iv_history=_load_iv_series(ticker), chain=chain, contract=contract,
        checklist=res.get("checklist", {}), is_demo=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO provider — deterministic mock so the screen runs without a feed.
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def _demo_provider(ticker: str) -> CockpitData:
    seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    spot = float(round(rng.uniform(40, 320), 2))
    iv = float(round(rng.uniform(0.28, 0.62), 4))
    rv = float(round(iv * rng.uniform(0.7, 1.05), 4))
    iv_rank = float(round(rng.uniform(8, 72), 1))

    n = 80
    drift = rng.uniform(-0.0008, 0.0018)
    rets = rng.normal(drift, iv / math.sqrt(252), n)
    close = spot * np.exp(np.cumsum(rets - rets.mean()))
    close = close * (spot / close[-1])
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    vol = rng.integers(3_000_000, 40_000_000, n).astype(float)
    idx = pd.bdate_range(end=pd.Timestamp("2026-06-01"), periods=n)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                       "Volume": vol}, index=idx)
    ma = df["Close"].rolling(20).mean()
    sd = df["Close"].rolling(20).std(ddof=0)
    df["bb_up"], df["bb_mid"], df["bb_lo"] = ma + 2 * sd, ma, ma - 2 * sd
    typ = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"] = (typ * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
    resistance = float(round(df["High"].tail(20).max(), 2))

    dte = 28
    strike = float(round(spot * rng.uniform(1.02, 1.08), 0))
    T = dte / 365.0
    prem = float(round(_bs_call(np.array([spot]), strike, T, iv)[0], 2))
    vol_t = iv * math.sqrt(T)
    d1 = (math.log(spot / strike) + (_RISK_FREE + 0.5 * iv ** 2) * T) / vol_t
    delta = float(round(_ncdf(np.array([d1]))[0], 3))
    gamma = float(round(math.exp(-0.5 * d1 ** 2) / (math.sqrt(2 * math.pi) * spot * vol_t), 4))
    vega = float(round(spot * math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi) * math.sqrt(T) / 100, 3))
    theta = float(round(-(spot * math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi) * iv)
                        / (2 * math.sqrt(T)) / 365, 3))

    strikes = np.round(np.linspace(spot * 0.85, spot * 1.15, 13))
    chain = pd.DataFrame({
        "strike": strikes,
        "call_vol": rng.integers(200, 9000, len(strikes)),
        "put_vol": rng.integers(200, 7000, len(strikes)),
        "call_oi": rng.integers(500, 25000, len(strikes)),
    })
    ivh = pd.DataFrame({
        "date": pd.bdate_range(end=pd.Timestamp("2026-06-01"), periods=120),
        "iv": np.clip(iv + rng.normal(0, 0.05, 120).cumsum() * 0.02, 0.15, 0.9),
    })

    em = _expected_move(spot, iv, dte)
    breakeven = round(strike + prem, 2)
    cp_ratio = float(round(rng.uniform(0.6, 2.2), 2))
    above_vwap = bool(close[-1] > df["vwap"].iloc[-1])
    breakout = bool(close[-1] > resistance * 0.995)
    rvol = float(round(rng.uniform(0.8, 3.2), 2))
    earn_days = int(rng.integers(3, 60))

    checklist = {
        "bollinger_squeeze": bool(sd.iloc[-1] < sd.tail(40).median()),
        "breakout_on_volume": breakout and rvol >= 1.5,
        "rvol_ge_2": rvol >= 2.0,
        "price_above_vwap": above_vwap,
        "iv_low_base": iv_rank < 30,
        "contract_in_sweet_spot": 0.30 <= delta <= 0.40,
        "contract_liquid": True,
        "earnings_clear": earn_days > dte,
        "breakeven_reachable": em >= (breakeven - spot),
        "regime_risk_on": bool(rng.random() > 0.4),
    }
    passed = sum(checklist.values())
    verdict = "GO" if passed >= 8 else "WAIT" if passed >= 5 else "AVOID"
    reasons = [
        f"通過 {passed}/10 進場閘",
        f"IV Rank {iv_rank:.0f} → {'低基期、適合買方' if iv_rank < 30 else '偏高、慎防 IV crush' if iv_rank > 60 else '中性'}",
        f"方向流 Call/Put 量比 {cp_ratio}",
    ]

    return CockpitData(
        ticker=ticker, spot=spot, day_change_pct=float(round(rng.uniform(-3, 5), 2)),
        regime="risk_on" if checklist["regime_risk_on"] else "neutral",
        verdict=verdict, verdict_reasons=reasons,
        trend="上升" if drift > 0 else "震盪/下行", rvol=rvol, above_vwap=above_vwap,
        breakout=breakout, resistance_20d=resistance, cp_vol_ratio=cp_ratio,
        put_call_ratio=float(round(1 / cp_ratio, 2)),
        atm_iv=iv, iv_rank=iv_rank, iv_percentile=float(round(min(iv_rank + rng.uniform(-8, 8), 99), 1)),
        realized_vol=rv, iv_rank_source="iv_history", iv_rank_accumulating=False, iv_rank_n_days=252,
        earnings_date=str((pd.Timestamp("2026-06-01") + pd.Timedelta(days=earn_days)).date()),
        earnings_days_away=earn_days, earnings_within_dte=earn_days <= dte,
        chart=df, iv_history=ivh, chain=chain,
        contract=Contract(
            strike=strike, expiry=str((pd.Timestamp("2026-06-01") + pd.Timedelta(days=dte)).date()),
            dte=dte, delta=delta, gamma=gamma, theta=theta, vega=vega,
            mid_premium=prem, iv=iv, volume=int(rng.integers(400, 6000)),
            open_interest=int(rng.integers(1000, 30000)),
            spread_pct=float(round(rng.uniform(1.5, 9), 1)),
            executable=bool(rng.random() > 0.25), in_sweet_spot=0.30 <= delta <= 0.40,
        ),
        checklist=checklist,
        is_demo=True,
    )


def _load_cockpit(ticker: str) -> CockpitData:
    """Prefer real pipeline data; fall back to the deterministic demo on any failure."""
    try:
        live = _live_provider(ticker)
        if live is not None:
            return live
    except Exception:
        pass
    return _demo_provider(ticker)


# ─────────────────────────────────────────────────────────────────────────────
# Presentational helpers — shared across pages (ui/_shared.py)
# ─────────────────────────────────────────────────────────────────────────────
_chip = _shared.chip
_metric = _shared.metric_card


def _compact(x) -> str:
    """Short human number (11_180 → '11.2K') so 成交量/OI fits a narrow metric cell."""
    if not isinstance(x, (int, float)):
        return "—"
    a = abs(x)
    if a >= 1e6:
        return f"{x / 1e6:.1f}M"
    if a >= 1e3:
        return f"{x / 1e3:.1f}K"
    return f"{x:.0f}"


def _status_cell(col, label: str, ok: bool, ok_text: str = "是",
                 bad_text: str = "否", help: str | None = None) -> None:
    """Compact pass/fail cell. A boolean rendered via st.metric shows a giant
    ✅/❌ at the 2.25rem value font — wrong weight for a yes/no. Render a small
    coloured chip under a caption label instead, matching the card aesthetic."""
    color = _GREEN if ok else _RED
    with col:
        with st.container(border=True):
            st.caption(label)
            st.markdown(_chip(f"{'✅' if ok else '❌'} {ok_text if ok else bad_text}", color),
                        unsafe_allow_html=True)
            if help:
                st.caption(help)


# ─────────────────────────────────────────────────────────────────────────────
# Section renderers
# ─────────────────────────────────────────────────────────────────────────────
def _render_header(d: CockpitData) -> None:
    label, alert_fn, _ = _VERDICT_STYLE.get(d.verdict, (d.verdict, st.info, _MUTED))
    regime_txt = {"risk_on": ("RISK-ON", _GREEN), "risk_off": ("RISK-OFF", _RED)}.get(
        d.regime, ("NEUTRAL", _MUTED))
    chips = [
        _chip(f"現價 ${d.spot:,.2f}", _BLUE),
        _chip(f"{d.day_change_pct:+.2f}%", _GREEN if d.day_change_pct >= 0 else _RED),
        _chip(f"大盤 {regime_txt[0]}", regime_txt[1]),
    ]
    if d.earnings_days_away is not None:
        ecol = _RED if d.earnings_within_dte else _MUTED
        warn = " ⚠️DTE內" if d.earnings_within_dte else ""
        chips.append(_chip(f"財報 {d.earnings_days_away}天{warn}", ecol))
    st.markdown(
        f"<div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:.2rem 0 .6rem'>"
        f"<span style='font-size:1.5rem;font-weight:800'>{d.ticker}</span>"
        + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )
    alert_fn(f"**{label}**  ·  " + "  ·  ".join(d.verdict_reasons))


def _render_direction_vol(d: CockpitData) -> None:
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("##### 方向偏好")
            a = st.columns(2)
            _metric(a[0], "趨勢 / RVOL", f"{d.trend} · {_f(d.rvol, '{:.1f}')}×")
            _metric(a[1], "Call/Put 量比", _f(d.cp_vol_ratio), help=">1 偏多買盤;<1 偏空")
            b = st.columns(2)
            _status_cell(b[0], "站上 VWAP", d.above_vwap)
            _status_cell(b[1], "突破 20d 壓力", d.breakout,
                         bad_text=f"壓力 {_f(d.resistance_20d)}")
    with right:
        with st.container(border=True):
            st.markdown("##### 波動環境 (IV Regime)")
            g1, g2 = st.columns([1.1, 1])
            with g1:
                gauge_val = d.iv_rank if not d.iv_rank_accumulating else d.iv_percentile
                st.plotly_chart(_iv_rank_gauge(gauge_val, d.iv_rank_accumulating, d.iv_rank_n_days),
                                use_container_width=True, config={"displayModeBar": False})
            with g2:
                _metric(st.container(), "ATM IV", _pct(d.atm_iv))
                _metric(st.container(), "已實現波動", _pct(d.realized_vol),
                        help="IV 明顯 > RV → 期權偏貴;反之偏宜")
                if isinstance(d.atm_iv, (int, float)) and isinstance(d.realized_vol, (int, float)):
                    _metric(st.container(), "IV − RV", f"{(d.atm_iv - d.realized_vol) * 100:+.1f}%",
                            help="正值 = 期權溢價(賣方友善);負值 = 便宜(買方友善)")
                else:
                    _metric(st.container(), "IV − RV", "—")
    if d.iv_rank_accumulating:
        st.caption(f"ℹ️ IV Rank 累積中(n={d.iv_rank_n_days}/40d),暫以**實現波動率百分位**代理;"
                   "每日快照累積滿後切換為真實 52 週 IV Rank。")


def _iv_rank_gauge(value, accumulating: bool, n_days: int) -> go.Figure:
    val = value if isinstance(value, (int, float)) else 0
    if accumulating:
        title, color = f"IV% (累積中 {n_days}d)", _MUTED
    else:
        title = "IV Rank"
        color = _GREEN if val < 30 else _RED if val > 60 else _AMBER
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val, number={"font": {"size": 30}},
        title={"text": title, "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "tickvals": [0, 30, 60, 100]},
            "bar": {"color": color, "thickness": 0.28}, "bgcolor": _PANEL,
            "steps": [
                {"range": [0, 30], "color": "rgba(0,204,150,0.18)"},
                {"range": [30, 60], "color": "rgba(255,161,90,0.16)"},
                {"range": [60, 100], "color": "rgba(239,85,59,0.18)"},
            ],
        },
    ))
    fig.update_layout(height=150, margin=dict(l=10, r=10, t=28, b=4),
                      paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e6e9ef"})
    return fig


def _render_price_chart(d: CockpitData) -> None:
    st.markdown("##### 價格 · 布林 · VWAP · 預期波動錐")
    tab_static, tab_tv = st.tabs(["快照圖 + 預期波動錐", "互動圖 (TradingView)"])
    with tab_tv:
        _shared.tradingview_chart(d.ticker, height=540)
    with tab_static:
        st.plotly_chart(_price_fig(d), use_container_width=True)


def _price_fig(d: CockpitData) -> go.Figure:
    df = d.chart
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                 low=df["Low"], close=df["Close"], name="價格",
                                 increasing_line_color=_GREEN, decreasing_line_color=_RED))
    if "bb_up" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_up"], name="BB 上軌", line=dict(color="#666", width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lo"], name="BB 下軌", line=dict(color="#666", width=1),
                                 fill="tonexty", fillcolor="rgba(136,136,136,0.06)"))
    if "vwap" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["vwap"], name="VWAP",
                                 line=dict(color=_AMBER, width=1.4, dash="dot")))
    if isinstance(d.resistance_20d, (int, float)):
        fig.add_hline(y=d.resistance_20d, line_dash="dash", line_color="#AB63FA",
                      annotation_text=f"20d 壓力 {d.resistance_20d}")

    c = d.contract
    iv = d.atm_iv if isinstance(d.atm_iv, (int, float)) else (c.iv if c else None)
    if c and isinstance(iv, (int, float)) and c.dte > 0:
        em = _expected_move(d.spot, iv, c.dte)
        future = pd.bdate_range(start=df.index[-1], periods=c.dte // 7 * 5 + 5)[1:]
        if len(future):
            frac = np.sqrt(np.arange(1, len(future) + 1) / len(future))
            fig.add_trace(go.Scatter(x=future, y=d.spot + em * frac, name="預期波動 +1σ",
                                     line=dict(color=_BLUE, width=1, dash="dot")))
            fig.add_trace(go.Scatter(x=future, y=d.spot - em * frac, name="預期波動 −1σ",
                                     line=dict(color=_BLUE, width=1, dash="dot"),
                                     fill="tonexty", fillcolor="rgba(99,110,250,0.12)"))
    if c and c.breakeven is not None:
        fig.add_hline(y=c.breakeven, line_dash="dot", line_color=_GREEN,
                      annotation_text=f"損益兩平 {c.breakeven:.2f}", annotation_position="bottom right")
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font={"color": "#e6e9ef"},
                      legend=dict(orientation="h", yanchor="bottom", y=1.0))
    return fig


_STRUCTURES = ["單買 Call", "牛市買權價差"]


def _short_leg_strike(d: CockpitData, long_strike: float, iv: float,
                      target_delta: float = 0.20) -> float | None:
    """Higher call strike near ~Δ0.20 for the short leg of a bull-call vertical.
    Uses real chain strikes + the shared BS delta; falls back to ~10% above."""
    T = max(d.contract.dte, 1) / 365.0
    strikes = []
    if not d.chain.empty and "strike" in d.chain:
        strikes = sorted({float(s) for s in d.chain["strike"] if float(s) > long_strike})
    best, best_diff = None, 1e9
    for K in strikes:
        g = _ana.bs_call_greeks(d.spot, K, T, _RISK_FREE, iv)
        dl = g.get("delta")
        if dl is None:
            continue
        diff = abs(dl - target_delta)
        if diff < best_diff:
            best, best_diff = K, diff
    return best if best is not None else (round(long_strike * 1.10) if long_strike else None)


def _strategy_legs(d: CockpitData, structure: str, iv: float) -> list[dict]:
    """Payoff legs: qty +1 long / -1 short, prem per share. Short leg is BS-priced
    at the same IV (the chain carries no per-strike premium)."""
    c = d.contract
    legs = [{"K": c.strike, "qty": 1, "prem": c.mid_premium, "iv": iv}]
    if structure == "牛市買權價差":
        ks = _short_leg_strike(d, c.strike, iv)
        if ks and ks > c.strike:
            short_prem = float(_bs_call(np.array([d.spot]), ks, c.dte / 365.0, iv)[0])
            legs.append({"K": ks, "qty": -1, "prem": round(short_prem, 2), "iv": iv})
    return legs


def _payoff_stats(d: CockpitData, legs: list[dict]) -> dict:
    """Breakeven / max-loss / max-profit / net-debit from the EXPIRY P/L curve."""
    S = np.linspace(d.spot * 0.5, d.spot * 2.0, 601)
    intrinsic = sum(leg["qty"] * np.maximum(S - leg["K"], 0.0) for leg in legs)
    net_debit = sum(leg["qty"] * leg["prem"] for leg in legs)
    pl = (intrinsic - net_debit) * 100.0
    net_qty = sum(leg["qty"] for leg in legs)  # >0 → unbounded upside
    be = None
    up = np.where(np.diff(np.sign(pl)) > 0)[0]
    if len(up):
        i = up[0]
        be = float(S[i] - pl[i] * (S[i + 1] - S[i]) / (pl[i + 1] - pl[i]))
    return {"net_debit": net_debit, "breakeven": be,
            "max_loss": float(np.min(pl)),
            "max_profit": None if net_qty > 0 else float(np.max(pl))}


def _render_contract_and_payoff(d: CockpitData) -> None:
    c = d.contract
    if c is None or c.strike is None:
        st.info("📭 此標的在 2–3 週到期窗內找不到 Δ0.3–0.4 甜蜜點的可成交 call"
                "(流動性不足或資料缺失)——略過損益圖。")
        return

    left, right = st.columns([1, 1.25])
    with left:
        with st.container(border=True):
            st.markdown(f"##### 建議合約 — ${_f(c.strike, '{:g}')} Call")
            st.caption(f"{c.expiry or '?'} · {c.dte} DTE")
            g = st.columns(4)
            g[0].metric("Δ Delta", _f(c.delta, "{:.3f}"), help="0.3–0.4 高槓桿且具勝率")
            g[1].metric("Γ Gamma", _f(c.gamma, "{:.4f}"))
            g[2].metric("Θ Theta/日", _f(c.theta, "{:.3f}"), help="每日時間價值耗損")
            g[3].metric("V Vega", _f(c.vega, "{:.3f}"), help="IV 每變動 1% 的影響")
            m = st.columns(3)
            m[0].metric("權利金(中價)", f"${_f(c.mid_premium)}")
            m[1].metric("損益兩平", f"${_f(c.breakeven)}")
            m[2].metric("成交量/OI", f"{_compact(c.volume)} / {_compact(c.open_interest)}")
            flags = ["✅ Δ 在甜蜜點" if c.in_sweet_spot else f"⚠️ Δ={_f(c.delta, '{:.3f}')} 不在甜蜜點"]
            flags.append(f"✅ 可成交(價差 {_f(c.spread_pct, '{:.1f}')}%)" if c.executable
                         else "⚠️ 無雙邊報價(indicative,權利金為最後成交價)")
            st.caption(" · ".join(flags))

    with right:
        with st.container(border=True):
            st.markdown("##### 損益圖 (P/L Payoff)")
            if not c.payoffable:
                st.info("缺權利金/IV,無法繪製損益曲線。")
                return
            iv = c.iv if isinstance(c.iv, (int, float)) else d.atm_iv
            structure = st.selectbox("結構", _STRUCTURES, key=f"struct_{d.ticker}",
                                     help="IV Rank 偏高時,價差比裸買 call 更抗 IV crush")
            legs = _strategy_legs(d, structure, iv)
            if structure == "牛市買權價差" and len(legs) < 2:
                st.caption("⚠️ 找不到合適的較高履約價空頭腿 — 暫以單買 Call 呈現。")
            stats = _payoff_stats(d, legs)
            if len(legs) == 2:
                st.caption(f"買 ${_f(legs[0]['K'], '{:g}')}C / 賣 ${_f(legs[1]['K'], '{:g}')}C"
                           f" · 淨權利金 ≈ ${_f(stats['net_debit'])}(空頭腿以 BS 估價)")
            days = st.slider("距到期天數(拉動看時間價值衰減)", 0, c.dte, c.dte, key=f"dte_{d.ticker}")
            st.plotly_chart(_payoff_fig(d, days, iv, legs, stats["breakeven"]),
                            use_container_width=True, config={"displayModeBar": False})
            be, mp = stats["breakeven"], stats["max_profit"]
            pop = _prob_of_profit(d.spot, be, iv, c.dte) if be is not None else None
            k = st.columns(3)
            k[0].metric("勝率 (POP)", f"{pop:.0f}%" if pop is not None else "—",
                        help="到期價 > 損益兩平的機率(零漂移估計)")
            k[1].metric("最大風險", f"−${abs(stats['max_loss']):,.0f}",
                        help="最大損失 = 淨權利金 × 100")
            k[2].metric("最大獲利", "無上限" if mp is None else f"${mp:,.0f}",
                        help="價差有上限;單買 call 理論無上限")


def _payoff_fig(d: CockpitData, days_left: int, iv: float, legs: list[dict],
                breakeven: float | None) -> go.Figure:
    S = np.linspace(d.spot * 0.80, d.spot * 1.25, 161)
    T = days_left / 365.0
    value = sum(leg["qty"] * _bs_call(S, leg["K"], T, leg["iv"]) for leg in legs)
    net_debit = sum(leg["qty"] * leg["prem"] for leg in legs)
    pl = (value - net_debit) * 100.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=S, y=np.maximum(pl, 0), mode="lines", line=dict(width=0),
                             fill="tozeroy", fillcolor="rgba(0,204,150,0.25)",
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=S, y=np.minimum(pl, 0), mode="lines", line=dict(width=0),
                             fill="tozeroy", fillcolor="rgba(239,85,59,0.22)",
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=S, y=pl, mode="lines", name="P/L", line=dict(color="#e6e9ef", width=2),
                             hovertemplate="標的 $%{x:.1f} → P/L $%{y:,.0f}<extra></extra>"))
    fig.add_hline(y=0, line_color="#555", line_width=1)
    if breakeven is not None:
        fig.add_vline(x=breakeven, line_dash="dot", line_color=_GREEN,
                      annotation_text=f"損益兩平 {breakeven:.1f}", annotation_position="top")
    for leg in legs:
        fig.add_vline(x=leg["K"], line_dash="dot", line_color="rgba(136,136,136,0.5)",
                      line_width=1)
    fig.add_vline(x=d.spot, line_dash="dash", line_color=_AMBER,
                  annotation_text=f"現價 {d.spot:.1f}", annotation_position="top left")
    em = _expected_move(d.spot, iv, d.contract.dte)
    fig.add_vrect(x0=d.spot - em, x1=d.spot + em, fillcolor="rgba(99,110,250,0.10)",
                  line_width=0, annotation_text="±1σ", annotation_position="bottom")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=24, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e6e9ef"}, showlegend=False,
                      xaxis_title="到期標的價", yaxis_title="每口損益 ($)")
    return fig


def _render_checklist(d: CockpitData) -> None:
    if not d.checklist:
        return
    with st.container(border=True):
        passed = sum(bool(v) for v in d.checklist.values())
        st.markdown(f"##### 進場檢查清單 — {passed}/{len(d.checklist)}")
        st.progress(passed / max(len(d.checklist), 1))
        cols = st.columns(2)
        for i, (key, ok) in enumerate(d.checklist.items()):
            cols[i % 2].markdown(f"{'✅' if ok else '❌'} {_CHECK_LABELS.get(key, key)}")


def _render_detail_expanders(d: CockpitData) -> None:
    if not d.chain.empty:
        with st.expander("📊 期權鏈量分佈(依履約價)", expanded=False):
            ch = d.chain
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ch["strike"], y=ch.get("call_vol", 0), name="Call 量", marker_color=_GREEN))
            fig.add_trace(go.Bar(x=ch["strike"], y=ch.get("put_vol", 0), name="Put 量", marker_color=_RED))
            if "call_oi" in ch:
                fig.add_trace(go.Scatter(x=ch["strike"], y=ch["call_oi"], name="Call OI",
                                         mode="lines", line=dict(color=_BLUE, width=1)))
            fig.add_vline(x=d.spot, line_dash="dash", line_color=_AMBER, annotation_text=f"現價 {d.spot}")
            fig.update_layout(barmode="group", height=320, margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font={"color": "#e6e9ef"},
                              legend=dict(orientation="h", yanchor="bottom", y=1.0))
            st.plotly_chart(fig, use_container_width=True)

    if not d.iv_history.empty:
        with st.expander("📈 IV 走勢(來自 iv_history 每日快照)", expanded=False):
            ivh = d.iv_history
            fig = go.Figure(go.Scatter(x=ivh["date"], y=ivh["iv"] * 100, mode="lines",
                                       line=dict(color=_ACCENT, width=1.6), name="ATM IV"))
            fig.add_hline(y=ivh["iv"].min() * 100, line_dash="dot", line_color=_GREEN, annotation_text="區間低")
            fig.add_hline(y=ivh["iv"].max() * 100, line_dash="dot", line_color=_RED, annotation_text="區間高")
            fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font={"color": "#e6e9ef"}, yaxis_title="IV %")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"IV Rank 來源:`{d.iv_rank_source}`(n={d.iv_rank_n_days}d)。"
                       "滿 40 天起算真實百分位,滿一年為完整 52 週 IV Rank。")


# ─────────────────────────────────────────────────────────────────────────────
# Page entry
# ─────────────────────────────────────────────────────────────────────────────
def _watchlist_quickpick() -> None:
    """Optional candidate quick-pick from local-only sources, so you can drop a
    surfaced name straight into the cockpit. Merges four additive sources:
      • IBKR scanner — reports/watchlist.json (`ibkr_client.py watchlist`)
      • X 博主雷達 — reports/x_influencer_picks.json (`x_influencers.py --save`)
      • 今日篩選器 — scored_candidates.json (root, EOD scan; may be stale → label
        carries scan_date; REJECT-only fallback is marked, never dressed as a pick)
      • 今日異常流 — reports/options_flow/latest.json (pre-sorted by heat)
    Each option is tagged by source. Absent files (CI / fresh clone) → nothing.
    """
    reports = _shared.DATA_DIR / "reports"
    labels: dict[str, str] = {}  # display label -> ticker

    # `or []` (not a .get default) so a present-but-null "tickers" doesn't crash.
    wl = _shared.load_json(str(reports / "watchlist.json"))
    wl_rows = (wl or {}).get("tickers") or []
    for r in wl_rows:
        t = isinstance(r, dict) and r.get("ticker")
        if t:
            labels[f"🔭 {t}  ·  IBKR {'/'.join(r.get('scan_kinds') or [])}"] = t

    picks = _shared.load_json(str(reports / "x_influencer_picks.json"))
    pick_rows = (picks or {}).get("tickers") or []
    for r in pick_rows:
        t = isinstance(r, dict) and r.get("symbol")
        if t:
            who = ", ".join("@" + str(h) for h in (r.get("mentioned_by") or [])[:3])
            labels[f"📡 {t}  ·  博主×{r.get('count', 0)} ({r.get('skew', '')}) {who}"] = t

    # 今日篩選器 — official candidates first; REJECT-only days fall back to the
    # top-scored rows but must say so (誠實原則: a ❌REJECT is not a pick).
    sc = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json")) or {}
    sc_official = (sc.get("needs_layer2") or []) + (sc.get("watchlist") or [])
    sc_rows = sc_official or (sc.get("all_scored") or [])
    sc_fallback = not sc_official and bool(sc_rows)
    n_scr = 0
    for r in sorted(sc_rows,
                    key=lambda x: (isinstance(x, dict) and x.get("regime_adjusted_score")) or 0,
                    reverse=True)[:5]:
        t = isinstance(r, dict) and r.get("ticker")
        if t:
            v = r.get("verdict") or "?"
            mark = "❌" if v == "REJECT" else ""
            labels[f"🌡 {t}  ·  篩選 {(r.get('regime_adjusted_score') or 0):.0f}分 "
                   f"{mark}{v} ({sc.get('scan_date', '?')})"] = t
            n_scr += 1

    fl = _shared.load_json(str(reports / "options_flow" / "latest.json")) or {}
    fl_rows = (fl.get("signals") or [])[:5]
    n_flow = 0
    for s in fl_rows:
        t = isinstance(s, dict) and s.get("ticker")
        if t:
            d_zh = {"bullish": "偏多", "bearish": "偏空"}.get(s.get("direction"), "中性")
            labels[f"🚨 {t}  ·  異常流{d_zh} 熱度{(s.get('flow_score') or 0):.0f}"] = t
            n_flow += 1

    if not labels:
        return
    n_ibkr, n_infl = len(wl_rows), len(pick_rows)
    with st.expander(f"🎯 候選快選  ·  IBKR {n_ibkr} / 博主 {n_infl} / "
                     f"篩選器 {n_scr} / 異常流 {n_flow}",
                     expanded=False):
        st.caption("IBKR scanner(🔭)+ X 博主雷達(📡)+ 今日篩選器(🌡)+ 異常流(🚨)"
                   "萃取的候選。選一檔直接帶入作戰台分析。"
                   + (" ⚠ 🌡 當日無正式候選,列最高分(含 ❌REJECT,**非推薦**)。"
                      if sc_fallback else ""))
        pick = st.selectbox("候選", list(labels), label_visibility="collapsed",
                            key="cockpit_wl_pick")
        if st.button("帶入此檔分析", key="cockpit_wl_go"):
            st.session_state["cockpit_ticker"] = labels[pick]
            st.rerun()


def render_for(ticker: str) -> None:
    """Embeddable per-ticker cockpit (no input widget / quick-pick / page header) —
    used by 個股總覽's 期權作戰台 tab. Mirrors render()'s body from the spinner down,
    minus the text_input/quickpick/st.header and the cockpit_ticker session write."""
    ticker = (ticker or "").strip().upper().lstrip("$")
    if not ticker:
        return
    with st.spinner(f"組裝 {ticker} 作戰台中…(抓取期權鏈,首次較慢)"):
        d = _load_cockpit(ticker)

    if d.is_demo:
        st.warning("🧪 **示範資料** — 即時資料暫時無法取得,顯示 mock(畫面與計算為真)。"
                   "盤中重試可載入真實期權鏈。")
    if d.earnings_within_dte:
        st.error("⚠️ **財報在 DTE 內 — IV crush 風險**:即使方向看對,財報後 IV 崩跌仍可能讓買權虧損。")

    _render_header(d)
    _render_direction_vol(d)
    _render_price_chart(d)
    _render_contract_and_payoff(d)
    _render_checklist(d)
    _render_detail_expanders(d)


def render() -> None:
    st.header("🎯 期權作戰台")
    st.caption("單頁決策座艙:判定 → 方向 → 波動 → 圖 → 合約/損益 → 檢查清單。"
               "免費延遲~15分資料,唯讀決策支援,非下單、非投資建議。")

    c1, c2 = st.columns([3, 1])
    ticker = c1.text_input("代號", value=st.session_state.get("cockpit_ticker", "NVDA"),
                           label_visibility="collapsed",
                           placeholder="輸入美股代號,如 NVDA").strip().upper().lstrip("$")
    if c2.button("分析", type="primary", use_container_width=True) and ticker:
        st.session_state["cockpit_ticker"] = ticker

    _watchlist_quickpick()

    active = st.session_state.get("cockpit_ticker")
    if not active:
        st.info("輸入代號並按「分析」。")
        return

    with st.spinner(f"組裝 {active} 作戰台中…(抓取期權鏈,首次較慢)"):
        d = _load_cockpit(active)

    if d.is_demo:
        st.warning("🧪 **示範資料** — 即時資料暫時無法取得,顯示 mock(畫面與計算為真)。"
                   "盤中重試可載入真實期權鏈。")

    if d.earnings_within_dte:
        st.error("⚠️ **財報在 DTE 內 — IV crush 風險**:即使方向看對,財報後 IV 崩跌仍可能讓買權虧損。")

    _render_header(d)
    # Pre-seed + link so 個股總覽 opens on the same ticker (暴漲因子 + 機構籌碼).
    # 一鍵切頁;舊 markdown 連結開新分頁=新 session,handoff 會遺失。改成按鈕
    # 也讓 checkup_ticker 只在使用者主動跳轉時寫入(不再每次 render 都覆寫)。
    if st.button("🔍 在「個股總覽」看暴漲因子 + 機構", key="cockpit_to_checkup"):
        st.session_state["checkup_ticker"] = active
        st.session_state["checkup_handoff"] = active  # 一次性,目標頁 pop
        if not _shared.switch_page("stock-checkup"):
            st.caption("請由側欄開啟「個股總覽」。")
    _render_direction_vol(d)
    _render_price_chart(d)
    _render_contract_and_payoff(d)
    _render_checklist(d)
    _render_detail_expanders(d)
