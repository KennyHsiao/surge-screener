"""Shared cached chart-data helper (the 動能期權 page UI is retired).

The 動能期權 page was superseded by 期權作戰台 (ui/options_cockpit.py) — its verdict /
checklist / contract / ranking now live there. All that survives here is the cached
OHLCV + Bollinger + VWAP helper, reused by options_cockpit._live_provider via
`from . import momentum_options as mo_ui; mo_ui._chart_data(...)`. Kept under this
module name so that import path stays valid.
"""

import streamlit as st

from scripts import cache_policy


@st.cache_data(ttl=cache_policy.WARM_TTL_SECONDS, show_spinner=False)
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
