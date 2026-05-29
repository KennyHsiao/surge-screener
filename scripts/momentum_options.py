#!/usr/bin/env python3
"""Momentum-options decision-support engine (free data).

Turns a ticker into the indicators a momentum-options trader needs as a DECISION
REFERENCE (not execution): the entry-filter checklist (RVOL / Bollinger squeeze /
VWAP / breakout), a suggested OTM call contract (Δ 0.3-0.4, DTE 2-3wk) with
Black-Scholes Greeks, IV context (current ATM IV + an IV-percentile proxy), an
earnings/IV-crush flag, a liquidity gate, an expected-move reachability check, the
market regime, and a combined GO / WAIT / AVOID verdict.

Design notes:
- Technical indicators are computed MANUALLY (numpy/pandas), matching the codebase
  and avoiding pandas-ta (which breaks on numpy 2.x).
- Greeks use Black-Scholes with the stdlib `math` only (no scipy dependency).
- Verified-data-to-AI: this fetches/derives numbers; it does not ask an LLM to
  guess them. yfinance is delayed ~15min, so this screens EOD swing-momentum
  setups, not 0DTE intraday triggers.
- Never raises: returns a dict with ``available: False`` + ``reason`` on failure.

CLI:  python scripts/momentum_options.py NVDA
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

R_FREE = 0.045          # risk-free rate proxy for Greeks
DTE_MIN, DTE_MAX = 10, 25   # target 2-3 trading weeks
DELTA_LO, DELTA_HI = 0.30, 0.40
MAX_SPREAD_PCT = 12.0   # liquidity gate: (ask-bid)/mid
IVP_LOW = 30.0          # "low IV base" threshold (percentile)
IVP_HIGH = 80.0         # IV-crush danger zone


# --------------------------------------------------------------------------- #
# Cache shim (best-effort; falls back to plain compute)
# --------------------------------------------------------------------------- #
def _cached(namespace, params, ttl, compute, should_cache=None):
    try:
        try:
            from cache import get_or_compute
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cache", Path(__file__).parent / "cache.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            get_or_compute = mod.get_or_compute
        return get_or_compute(namespace, params, ttl, compute, should_cache=should_cache)
    except Exception:
        return compute()


# --------------------------------------------------------------------------- #
# Black-Scholes Greeks (stdlib math only)
# --------------------------------------------------------------------------- #
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def bs_call_greeks(S: float, K: float, T: float, r: float, sigma: float) -> dict:
    """Black-Scholes call greeks. T in years. theta per calendar day, vega per 1% IV."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}
    d1 = (math.log(S / K) + (r + sigma * sigma / 2.0) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    delta = _ncdf(d1)
    gamma = _npdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-S * _npdf(d1) * sigma / (2.0 * math.sqrt(T))
             - r * K * math.exp(-r * T) * _ncdf(d2)) / 365.0
    vega = S * _npdf(d1) * math.sqrt(T) / 100.0
    return {"delta": round(delta, 3), "gamma": round(gamma, 5),
            "theta": round(theta, 4), "vega": round(vega, 4)}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def _daily(ticker: str):
    import yfinance as yf
    df = yf.Ticker(ticker).history(period="1y", auto_adjust=False)
    return df if df is not None and not df.empty else None


def _technical(df) -> dict:
    """Manual momentum indicators on 1y daily OHLCV."""
    import numpy as np
    close = df["Close"].to_numpy(dtype=float)
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    vol = df["Volume"].to_numpy(dtype=float)
    n = len(close)
    px = float(close[-1])

    def _sma(a, w):
        return float(np.mean(a[-w:])) if len(a) >= w else None

    ma20, ma50, ma200 = _sma(close, 20), _sma(close, 50), _sma(close, 200)

    # Relative volume = today vs prior-20d average
    rvol = (float(vol[-1]) / float(np.mean(vol[-21:-1]))
            if n >= 21 and np.mean(vol[-21:-1]) > 0 else None)

    # Bollinger Bands (20, 2) + squeeze vs last 6mo bandwidth distribution
    bb_up = bb_lo = bb_bw = None
    squeeze = False
    if n >= 20:
        std20 = float(np.std(close[-20:], ddof=0))
        bb_up, bb_lo = ma20 + 2 * std20, ma20 - 2 * std20
        bb_bw = (bb_up - bb_lo) / ma20 if ma20 else None
        # bandwidth series over last 126 sessions
        bws = []
        for i in range(max(20, n - 126), n + 1):
            seg = close[i - 20:i]
            if len(seg) == 20:
                m = seg.mean()
                if m:
                    bws.append((m + 2 * seg.std() - (m - 2 * seg.std())) / m)
        if bws and bb_bw is not None:
            squeeze = bb_bw <= float(np.percentile(bws, 25))

    # Anchored ~20d VWAP (daily proxy)
    vwap = None
    if n >= 20:
        typ = (high[-20:] + low[-20:] + close[-20:]) / 3.0
        vol20 = vol[-20:]
        vwap = float(np.sum(typ * vol20) / np.sum(vol20)) if np.sum(vol20) > 0 else None

    # ATR(14)
    atr = None
    if n >= 15:
        tr = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
        atr = float(np.mean(tr[-14:]))

    # RSI(14)
    rsi = None
    if n >= 15:
        d = np.diff(close)
        gain = np.where(d > 0, d, 0.0)
        loss = np.where(d < 0, -d, 0.0)
        ag, al = np.mean(gain[-14:]), np.mean(loss[-14:])
        rsi = 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 1)

    # Breakout above prior-20d resistance with volume confirmation
    resistance = float(np.max(high[-21:-1])) if n >= 21 else None
    breakout = bool(resistance and px > resistance and (rvol or 0) >= 2.0)

    return {
        "price": round(px, 2),
        "ma20": round(ma20, 2) if ma20 else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "rvol": round(rvol, 2) if rvol else None,
        "bb_upper": round(bb_up, 2) if bb_up else None,
        "bb_lower": round(bb_lo, 2) if bb_lo else None,
        "bb_bandwidth": round(bb_bw, 4) if bb_bw else None,
        "bb_squeeze": squeeze,
        "vwap": round(vwap, 2) if vwap else None,
        "price_above_vwap": bool(vwap and px > vwap),
        "atr14": round(atr, 2) if atr else None,
        "rsi14": rsi,
        "resistance_20d": round(resistance, 2) if resistance else None,
        "breakout_above_resistance": breakout,
    }


def _realized_vol_percentile(df) -> tuple:
    """Annualized 20d realized vol + its percentile within the last year.
    Serves as the IV-percentile PROXY until real IV history accumulates."""
    import numpy as np
    close = df["Close"].to_numpy(dtype=float)
    if len(close) < 60:
        return None, None
    rets = np.diff(np.log(close))
    rv = []
    for i in range(20, len(rets) + 1):
        rv.append(float(np.std(rets[i - 20:i], ddof=0) * math.sqrt(252)))
    if not rv:
        return None, None
    cur = rv[-1]
    pct = float(np.mean([1.0 if x <= cur else 0.0 for x in rv]) * 100)
    return round(cur, 4), round(pct, 1)


def _pick_expiry(expirations) -> tuple:
    """Choose the expiry closest to the 2-3wk DTE window."""
    best, best_dte, best_diff = None, None, 1e9
    now = datetime.now()
    for e in expirations:
        try:
            dte = (datetime.strptime(e, "%Y-%m-%d") - now).days
        except ValueError:
            continue
        if dte < 5:
            continue
        target = 18
        diff = abs(dte - target) + (0 if DTE_MIN <= dte <= DTE_MAX else 100)
        if diff < best_diff:
            best, best_dte, best_diff = e, dte, diff
    return best, best_dte


def _fnum(x) -> float:
    """float or 0.0, NaN-safe (yfinance leaves NaN in bid/ask/volume when closed)."""
    try:
        v = float(x)
        return 0.0 if v != v else v
    except (TypeError, ValueError):
        return 0.0


def _inum(x) -> int:
    return int(_fnum(x))


def _sane_iv(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if 0.05 <= v <= 3.0 else None


def _atm_iv(calls, spot, fallback: float | None = None) -> tuple:
    """(iv, estimated). Uses the chain ATM IV when sane, else the realized-vol
    fallback (yfinance frequently returns near-zero/garbage IV on the free feed)."""
    if calls is None or calls.empty:
        return (fallback, fallback is not None)
    idx = (calls["strike"] - spot).abs().idxmin()
    iv = _sane_iv(calls.loc[idx, "impliedVolatility"])
    if iv is not None:
        return (iv, False)
    return (fallback, fallback is not None)


def _select_contract(calls, spot, dte_days, fallback_sigma: float | None = None) -> dict | None:
    """Pick the OTM call in the Δ0.3-0.4 sweet spot with acceptable liquidity.

    Per-strike chain IV is used when sane; otherwise we fall back to realized vol
    (fallback_sigma) so Greeks/delta stay meaningful when yfinance IV is broken.
    """
    if calls is None or calls.empty:
        return None
    T = max(dte_days, 1) / 365.0
    otm = calls[calls["strike"] > spot]
    cands = []
    for _, r in otm.iterrows():
        chain_iv = _sane_iv(r.get("impliedVolatility"))
        iv = chain_iv if chain_iv is not None else fallback_sigma
        if iv is None:
            continue
        g = bs_call_greeks(spot, float(r["strike"]), T, R_FREE, iv)
        if g["delta"] is None:
            continue
        bid, ask = _fnum(r.get("bid")), _fnum(r.get("ask"))
        last = _fnum(r.get("lastPrice"))
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last
        spread_pct = round((ask - bid) / mid * 100, 1) if mid > 0 and ask > 0 else None
        vol_i, oi_i = _inum(r.get("volume")), _inum(r.get("openInterest"))
        cands.append({
            "strike": round(float(r["strike"]), 2),
            "dte_days": dte_days,
            "iv": round(iv, 3),
            "iv_estimated": chain_iv is None,
            "mid_premium": round(mid, 2) if mid else None,
            "spread_pct": spread_pct,
            "volume": vol_i,
            "open_interest": oi_i,
            "breakeven": round(float(r["strike"]) + mid, 2) if mid else None,
            **g,
        })
    if not cands:
        return None
    sweet = [c for c in cands if c["delta"] is not None and DELTA_LO <= c["delta"] <= DELTA_HI]
    pool = sweet or cands
    # prefer in-sweet-spot, then a usable spread, then closest to Δ0.35
    pool.sort(key=lambda c: (
        0 if (c["spread_pct"] is not None and c["spread_pct"] <= MAX_SPREAD_PCT) else 1,
        abs((c["delta"] or 0) - 0.35),
        c["spread_pct"] if c["spread_pct"] is not None else 999,
    ))
    best = pool[0]
    best["in_delta_sweet_spot"] = bool(sweet) and best in sweet
    # Liquidity: tight spread when bid/ask exist; otherwise (market closed →
    # bid/ask=0) fall back to volume/OI like the options page does.
    if best["spread_pct"] is not None:
        best["liquid"] = bool(best["spread_pct"] <= MAX_SPREAD_PCT
                              and (best["open_interest"] >= 100 or best["volume"] >= 100))
        best["liquidity_basis"] = "spread"
    else:
        best["liquid"] = bool(best["open_interest"] >= 500 or best["volume"] >= 500)
        best["liquidity_basis"] = "volume_only (no bid/ask — market likely closed)"
    return best


def _earnings_within(tk, dte_days: int) -> dict:
    try:
        cal = tk.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            ed = dates[0] if isinstance(dates, (list, tuple)) else dates
            days = (datetime(ed.year, ed.month, ed.day) - datetime.now()).days
            return {"date": str(ed), "days_away": days,
                    "within_dte": 0 <= days <= dte_days}
    except Exception:
        pass
    return {"date": None, "days_away": None, "within_dte": False}


def _iv_history_mod():
    """Load scripts/iv_history.py robustly (works as script or package import)."""
    try:
        try:
            import iv_history as m
            return m
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "iv_history", Path(__file__).parent / "iv_history.py")
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    except Exception:
        return None


def _regime() -> dict:
    """Read regime_context from the latest scored_candidates.json if present."""
    try:
        from pathlib import Path as _P
        import json
        p = _P(__file__).parent.parent / "scored_candidates.json"
        if p.is_file():
            rc = json.loads(p.read_text()).get("regime_context", {})
            spy200 = rc.get("spy_vs_200dma")
            vix = rc.get("vix_level")
            risk_on = (spy200 == "above" and (vix is None or vix < 25))
            return {"available": True, "spy_vs_200dma": spy200, "vix": vix,
                    "risk_on": bool(risk_on),
                    "multiplier": rc.get("global_score_multiplier")}
    except Exception:
        pass
    return {"available": False, "risk_on": None}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def analyze(ticker: str) -> dict:
    """Full momentum-options analysis. Cached 15min. Never raises."""
    return _cached("momentum_options", {"ticker": ticker.upper()}, 900,
                   lambda: _analyze(ticker),
                   should_cache=lambda v: isinstance(v, dict) and v.get("available"))


def _analyze(ticker: str) -> dict:
    ticker = ticker.upper().lstrip("$")
    try:
        import yfinance as yf
    except ImportError:
        return {"available": False, "reason": "yfinance not installed", "ticker": ticker}

    df = _daily(ticker)
    if df is None:
        return {"available": False, "reason": "no price history", "ticker": ticker}

    tech = _technical(df)
    rv, rv_pct = _realized_vol_percentile(df)
    spot = tech["price"]

    tk = yf.Ticker(ticker)
    contract, atm_iv, atm_iv_est, earnings, expiry, dte = None, None, False, None, None, None
    try:
        exps = tk.options
        expiry, dte = _pick_expiry(exps) if exps else (None, None)
        if expiry:
            calls = tk.option_chain(expiry).calls
            atm_iv, atm_iv_est = _atm_iv(calls, spot, fallback=rv)
            contract = _select_contract(calls, spot, dte, fallback_sigma=rv)
            earnings = _earnings_within(tk, dte)
    except Exception as e:
        earnings = {"date": None, "days_away": None, "within_dte": False, "error": str(e)}

    # IV percentile: prefer real IV history (Phase 2), else realized-vol proxy.
    iv_pct, iv_pct_source = rv_pct, "realized_vol_proxy"
    ivh = _iv_history_mod()
    if ivh is not None:
        try:
            # Record today's REAL chain ATM IV (not the RV fallback) so the
            # 52-week base accumulates just by using the tool during market hours.
            if atm_iv and not atm_iv_est:
                ivh.record_iv(ticker, atm_iv)
            real = ivh.iv_percentile(ticker, atm_iv)
            if real and real.get("percentile") is not None and not real.get("accumulating"):
                iv_pct, iv_pct_source = real["percentile"], f"iv_history ({real['n_days']}d)"
        except Exception:
            pass

    # Expected-move reachability of the breakeven
    exp_move = None
    breakeven_reachable = None
    if atm_iv and dte and contract and contract.get("breakeven"):
        exp_move = round(spot * atm_iv * math.sqrt(max(dte, 1) / 365.0), 2)
        breakeven_reachable = (contract["breakeven"] - spot) <= exp_move

    regime = _regime()

    # ---- Entry checklist (the strategy's hard gates) ----
    checks = {
        "bollinger_squeeze": tech["bb_squeeze"],
        "breakout_on_volume": tech["breakout_above_resistance"],
        "rvol_ge_2": bool(tech["rvol"] and tech["rvol"] >= 2.0),
        "price_above_vwap": tech["price_above_vwap"],
        "iv_low_base": bool(iv_pct is not None and iv_pct < IVP_LOW),
        "contract_in_sweet_spot": bool(contract and contract.get("in_delta_sweet_spot")),
        "contract_liquid": bool(contract and contract.get("liquid")),
        "earnings_clear": bool(earnings and not earnings.get("within_dte")),
        "breakeven_reachable": bool(breakeven_reachable),
        "regime_risk_on": regime.get("risk_on") is True,
    }
    reasons = []

    # ---- Verdict ----
    # Hard AVOIDs first.
    if earnings and earnings.get("within_dte"):
        verdict = "AVOID"
        reasons.append(f"earnings in {earnings.get('days_away')}d (inside DTE) → IV-crush risk")
    elif iv_pct is not None and iv_pct >= IVP_HIGH:
        verdict = "AVOID"
        reasons.append(f"IV percentile {iv_pct} ≥ {IVP_HIGH:.0f} — expensive premium / IV-crush risk")
    elif contract and not contract.get("liquid"):
        verdict = "AVOID"
        reasons.append("no liquid Δ0.3-0.4 contract (wide spread / thin OI) — slippage kills the edge")
    elif regime.get("risk_on") is False:
        verdict = "AVOID"
        reasons.append("market regime risk-off — momentum longs unfavorable")
    else:
        core = (checks["breakout_on_volume"] and checks["price_above_vwap"]
                and checks["contract_in_sweet_spot"] and checks["contract_liquid"]
                and checks["iv_low_base"] and checks["earnings_clear"])
        if core and checks["regime_risk_on"]:
            verdict = "GO"
            reasons.append("breakout on volume + above VWAP + low-IV + liquid Δ0.3-0.4 contract + risk-on")
        elif (checks["bollinger_squeeze"] or checks["iv_low_base"]) and not checks["breakout_on_volume"]:
            verdict = "WAIT"
            reasons.append("coiling (squeeze / low IV) but no volume breakout yet — watch for the trigger")
        else:
            verdict = "WAIT"
            reasons.append("partial setup — not all entry gates met")
    # annotate which gates failed
    failed = [k for k, v in checks.items() if not v]
    if failed:
        reasons.append("gates not met: " + ", ".join(failed))

    return {
        "available": True,
        "ticker": ticker,
        "source": "yfinance_free",
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "spot": spot,
        "verdict": verdict,
        "reasons": reasons,
        "checklist": checks,
        "technical": tech,
        "options": {
            "expiry": expiry,
            "dte_days": dte,
            "atm_iv": round(atm_iv, 3) if atm_iv else None,
            "suggested_contract": contract,
            "expected_move": exp_move,
            "breakeven_reachable": breakeven_reachable,
        },
        "iv": {
            "atm_iv": round(atm_iv, 3) if atm_iv else None,
            "atm_iv_estimated": atm_iv_est,
            "realized_vol": rv,
            "iv_percentile": iv_pct,
            "iv_percentile_source": iv_pct_source,
        },
        "earnings": earnings,
        "regime": regime,
        "notes": "Delayed ~15min data — EOD swing-momentum screening, not 0DTE intraday. "
                 "Decision reference only, not execution/advice.",
    }


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(analyze(t), indent=2, ensure_ascii=False, default=str))
