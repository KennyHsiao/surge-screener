"""Shared data-loading helpers used across UI pages.

Extracted verbatim from the original single-file app.py so every page reads
pipeline outputs the same way. `_shared` lives in ui/, one level below the repo
root where the pipeline JSON files and reports/ live — hence parent.parent.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# reports/ holds date-named report folders (YYYY-MM-DD) alongside non-date
# artifact folders (reflections/, crypto/, cot/). Only the former are reports.
_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DATA_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = DATA_DIR / "reports"
CONTENT_DIR = DATA_DIR / "content"

# Pages that fetch live data import pipeline modules from scripts/; make the repo
# root importable once here so any page using _shared loaders gets it for free.
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

from scripts.runtime_paths import CANDIDATE_OUTPUT_DIR, candidate_output_path


# ── Cross-page one-click navigation ─────────────────────────────────────────
# app.py registers its st.Page objects here (url_path → StreamlitPage) so
# feature pages can st.switch_page() without importing app.py (circular).
# Plain markdown links are NOT a substitute: Streamlit renders external-style
# links with target=_blank, so "/stock-checkup" opens a NEW TAB = a NEW
# session and any checkup_ticker/cockpit_ticker handoff is lost.
PAGE_REGISTRY: dict[str, object] = {}


def switch_page(url_path: str) -> bool:
    """Jump to a registered page in the SAME session (one click, state kept).
    Returns False when the registry is empty — the module is being rendered
    outside app.py — so callers can fall back to a sidebar hint."""
    page = PAGE_REGISTRY.get(url_path.strip("/"))
    if page is None:
        return False
    st.switch_page(page)
    return True


def ticker_action_buttons(ticker: str, key_prefix: str, *, include_checkup: bool = True,
                          include_cockpit: bool = True, include_radar: bool = True) -> None:
    """Standard candidate actions: single-name overview, options cockpit, radar.

    Uses st.switch_page() through PAGE_REGISTRY so the target opens in the same
    Streamlit session and receives the ticker handoff. Candidate tables should use
    this helper instead of hand-written page links.
    """
    sym = (ticker or "").upper().strip()
    if not sym:
        return

    actions = []
    if include_checkup:
        actions.append(("🔍 個股總覽", "stock-checkup", "checkup_ticker",
                        f"{key_prefix}_chk_{sym}", f"帶 {sym} 到個股總覽"))
    if include_cockpit:
        actions.append(("🎯 期權作戰台", "options-cockpit", "cockpit_ticker",
                        f"{key_prefix}_ckpt_{sym}", f"帶 {sym} 到期權作戰台"))
    if include_radar:
        actions.append(("📡 雷達", "radar", "radar_handoff",
                        f"{key_prefix}_radar_{sym}", f"帶 {sym} 到雷達"))
    if not actions:
        return

    cols = st.columns([1] * len(actions) + [max(0, 4 - len(actions))])
    for col, (label, page, state_key, key, help_text) in zip(cols, actions):
        if col.button(label, key=key, help=help_text, use_container_width=True):
            st.session_state[state_key] = sym
            if state_key == "checkup_ticker":
                st.session_state["checkup_handoff"] = sym
            if not switch_page(page):
                st.caption(f"請由側欄開啟「{label.split(' ', 1)[-1]}」。")


# ── Design tokens (single source; Plotly traces + chips share these) ───────
# Reserve ACCENT (#ef4444) for AVOID / primary alarms ONLY; P/L-negative
# shading uses a distinct LOSS red so "alarm" and "loss" never collide.
GREEN = "#00CC96"     # bullish / pass
RED = "#EF553B"       # bearish / fail
LOSS = "#f87171"      # P/L-negative shading (distinct from ACCENT)
ACCENT = "#ef4444"    # AVOID / primary accent ONLY
AMBER = "#FFA15A"     # neutral / caution
BLUE = "#636EFA"      # informational overlay
PURPLE = "#AB63FA"    # secondary categorical (e.g. resistance, funnel)
CYAN = "#19D3F3"      # secondary categorical (e.g. funnel)
MUTED = "#8b93a7"     # secondary / unknown
PANEL = "#1a1f2b"     # bordered-panel background
BG = "#0e1117"        # app background

# verdict / signal string → semantic colour, shared across pages so "colour ==
# meaning" is consistent (us_screener / us_options / options_cockpit / x pages).
VERDICT_COLOR_MAP = {
    "STRONG_BUY": GREEN, "BUY": GREEN, "GO": GREEN, "CONTINUE_TO_DD": GREEN,
    "NEEDS_LAYER_2": GREEN, "bullish": GREEN, "看多": GREEN,
    "WAIT": AMBER, "HOLD": AMBER, "NEUTRAL": AMBER, "neutral": AMBER, "中性": AMBER,
    "WATCHLIST": AMBER,
    "AVOID": RED, "REJECT": RED, "SELL": RED, "bearish": RED, "看空": RED,
}


def verdict_color(verdict: str) -> str:
    """Semantic colour for a verdict/signal string (case-insensitive); MUTED if unknown."""
    if not verdict:
        return MUTED
    v = str(verdict).strip()
    return VERDICT_COLOR_MAP.get(v, VERDICT_COLOR_MAP.get(v.upper(), MUTED))


def verdict_chip(verdict: str) -> str:
    """A chip coloured by verdict semantics. Render via chips_row or unsafe markdown."""
    return chip(str(verdict), verdict_color(verdict))


def rating_color(grade: str) -> str:
    """Colour an analyst recommendation / grade string by bullish→bearish semantics.

    Handles consensus keys (strong_buy/buy/hold/sell) AND per-firm grade strings
    (Outperform/Overweight/Neutral/Underperform/…). MUTED if unrecognised."""
    g = (grade or "").lower()
    if "strong" in g and "buy" in g:
        return GREEN
    if any(s in g for s in ("buy", "outperform", "overweight", "accumulate")):
        return GREEN
    if any(s in g for s in ("hold", "neutral", "equal", "market perform",
                            "sector perform", "in-line", "in line")):
        return AMBER
    if any(s in g for s in ("sell", "underperform", "underweight", "reduce")):
        return RED
    return MUTED

# Colorblind-safe single-hue sequential (dark→cyan) for heatmaps — magnitude by
# brightness, NOT green↔red. The low end blends into the app bg so concentration pops.
HEAT_SEQ = [
    [0.0, "#0e1117"], [0.25, "#15314b"], [0.5, "#1f6f8b"],
    [0.75, "#2bb0c9"], [1.0, "#7fe3f0"],
]


def chip(text: str, color: str = MUTED) -> str:
    """Inline pill badge (HTML). Render via st.markdown(..., unsafe_allow_html=True)."""
    return (f"<span style='background:{color}22;color:{color};border:1px solid {color}55;"
            f"padding:2px 10px;border-radius:999px;font-size:0.82rem;font-weight:600'>{text}</span>")


def chips_row(items) -> None:
    """Render a horizontal row of (text, color) chip tuples."""
    html = "".join(chip(t, c) for t, c in items)
    st.markdown(
        f"<div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap;"
        f"margin:.2rem 0 .6rem'>{html}</div>", unsafe_allow_html=True)


def metric_card(col, label, value, help=None, delta=None, delta_color="off") -> None:
    """The app's standard bordered st.metric card."""
    with col:
        with st.container(border=True):
            st.metric(label, value, delta=delta, delta_color=delta_color, help=help)


@st.cache_data(ttl=60)
def load_json(path: str):
    """Fail-soft JSON read (cached 60s). Returns the parsed value, or None on ANY
    problem — missing file, a partial/corrupt write (JSONDecodeError), a TOCTOU
    delete, or an unreadable path. Pages read live artifacts that a backend may be
    mid-writing, so a read must NEVER raise; callers already treat None as
    "no data". (Returns whatever JSON holds — usually a dict, sometimes a list —
    so callers needing a dict should isinstance-check.)"""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):  # FileNotFoundError/PermissionError + JSONDecodeError(⊂ValueError)
        return None


@st.cache_data(ttl=21600, show_spinner=False)
def load_analyst_views(ticker: str) -> dict | None:
    """Live sell-side analyst consensus (yfinance, Dim 7). Never raises.

    Scored JSON doesn't persist the raw analyst fetch, so pages pull it on
    demand. analyst_free already disk-caches 6h; this st.cache_data layer just
    avoids a re-fetch per Streamlit rerun. Mirrors the options-cockpit live
    pattern. Returns None when coverage is thin or the source is unavailable."""
    if not ticker:
        return None
    try:
        from scripts import analyst_free
        return analyst_free.gather_analyst_views(ticker)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_sector_flow() -> dict | None:
    """Live sector relative-strength / RRG snapshot (yfinance). Never raises.

    Computed by scripts/sector_flow.py (RS-Ratio / RS-Momentum / quadrants /
    heat). 1h st.cache_data over the module's own 1h disk cache. None if the
    source is unavailable."""
    try:
        from scripts import sector_flow
        return sector_flow.gather_sector_flow()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_theme_flow() -> dict | None:
    """Live theme money-flow board (yfinance price×volume PROXY). Never raises.

    Computed by scripts/theme_flow.py (Chaikin-$ money-flow proxy per narrow theme
    basket — NOT real institutional net-buy). 1h st.cache_data over the module's own
    1h disk cache. None if the source is unavailable."""
    try:
        from scripts import theme_flow
        return theme_flow.gather_theme_flow()
    except Exception:
        return None


@st.cache_data(ttl=21600, show_spinner="載入內部人資料…(首次較慢)")
def _load_theme_insider_yf(days: int = 30) -> dict | None:
    try:
        from scripts import theme_flow
        return theme_flow.gather_theme_insider("yfinance", days)
    except Exception:
        return None


def load_theme_insider(source: str = "yfinance", days: int = 30) -> dict | None:
    """Per-theme insider net-buy ($) overlay — REAL Form-4 money (not a proxy).

    source='yfinance' → 6-month aggregate (fast, smoothed), 6h-cached. source=
    'edgar' → SEC EDGAR open-market Form-4 over `days` (daily-fresh, precise, but
    SLOW cold). Never raises. None if unavailable.

    EDGAR is NOT cached at this Streamlit layer either: a 6h cache here would sit
    above the per-ticker submissions-freshness/amendment guard and could render a
    pre-Form-4/A net for hours (Codex TF-1 r14). The EDGAR path recomputes each
    call (the per-ticker cache absorbs the heavy XML work); it is the opt-in slow
    source, so the spinner cost is the price of never showing stale Form-4
    evidence."""
    if source == "edgar":
        with st.spinner("載入 EDGAR Form-4…(逐檔核實,較慢)"):
            try:
                from scripts import theme_flow
                return theme_flow.gather_theme_insider("edgar", days)
            except Exception:
                return None
    return _load_theme_insider_yf(days)


@st.cache_data(ttl=21600, show_spinner=False)
def ticker_sector_etf(ticker: str) -> str | None:
    """Map a ticker to its SPDR sector ETF (yfinance .info['sector']). Never raises.

    Delegates to scripts.sector_flow (single source of the GICS→ETF map, shared
    with the scoring pipeline's Dimension 5)."""
    try:
        from scripts import sector_flow
        return sector_flow.sector_etf_for(ticker)
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_reconciliation() -> dict | None:
    """Read reports/reconciliation.json (gitignored local IBKR data; absent → None)."""
    return load_json(str(REPORTS_DIR / "reconciliation.json"))


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
    """Find all available report DATE folders (YYYY-MM-DD), newest first.

    Only date-named folders are daily reports; sibling artifact folders such as
    reports/reflections, reports/crypto, reports/cot are excluded.
    """
    dates = []
    if REPORTS_DIR.exists():
        for d in sorted(REPORTS_DIR.iterdir(), reverse=True):
            if d.is_dir() and _DATE_DIR_RE.match(d.name):
                dates.append(d.name)
    return dates


def tradingview_chart(ticker: str, height: int = 640, interval: str = "D",
                      studies: list[str] | None = None, default_range: str = "6M") -> None:
    """Embed TradingView's official Advanced Chart widget for ``ticker``.

    Display-only: the widget renders client-side using TradingView's own licensed
    data, so it pulls nothing through our pipeline and stays within TradingView's
    terms (unlike scraping). Complements the plotly chart for an interactive,
    drawing-capable view. No-op on a blank ticker.

    ``default_range`` ("1M"/"3M"/"6M"/"12M"/"YTD"/"ALL") sets the initial visible
    window — without it the widget fits ALL history, which on reverse-split names
    (e.g. SPCE) blows the y-axis out so recent action collapses to a flat line.
    """
    from urllib.parse import quote

    sym = "".join(c for c in (ticker or "").upper() if c.isalnum() or c in ".:-")
    if not sym:
        return
    # Default overlay = Bollinger Bands. VWAP is a *session/intraday* indicator —
    # on a daily/weekly chart TradingView renders it as a meaningless flat line, so
    # only attach it on intraday intervals. The plotly snapshot keeps its own 20d
    # VWAP proxy for the daily view.
    if studies is not None:
        study_list = studies
    else:
        study_list = ["STD;Bollinger_Bands"]
        if interval not in ("D", "W", "M", "1D", "1W", "1M"):
            study_list.append("STD;VWAP")
    widget_config = {
        "symbol": sym,
        "interval": interval,
        "range": default_range,
        "timezone": "America/New_York",
        "theme": "dark",
        "backgroundColor": "#0e1117",
        "gridColor": "rgba(240,243,250,0.06)",
        "style": "1",
        "locale": "zh_TW",
        "autosize": True,
        "hide_side_toolbar": False,
        "allow_symbol_change": True,
        "studies": study_list,
    }
    src = (
        "https://www.tradingview-widget.com/embed-widget/advanced-chart/"
        "?locale=zh_TW#"
        + quote(json.dumps(widget_config, separators=(",", ":")))
    )
    if hasattr(st, "iframe"):
        st.iframe(
            src,
            width="stretch",
            height=height,
        )
    else:  # Streamlit < st.iframe; keep requirements' older lower bound usable.
        import streamlit.components.v1 as components
        components.iframe(src, height=height, scrolling=False)
