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

# Shared options math — one Black-Scholes source for engine + UI (no drift).
# Prefer the package module so the engine and the cockpit bind to the SAME
# instance in-app; fall back to a flat/importlib load for CLI & test contexts.
try:
    from scripts import options_analytics as _ana    # app / package context
except ImportError:
    try:
        import options_analytics as _ana              # scripts/ on sys.path (CLI/tests)
    except ImportError:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "options_analytics", Path(__file__).parent / "options_analytics.py")
        _ana = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_ana)

R_FREE = _ana.R_FREE    # risk-free rate proxy for Greeks (single source)
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
# Black-Scholes Greeks — single shared source (scripts/options_analytics.py)
# --------------------------------------------------------------------------- #
bs_call_greeks = _ana.bs_call_greeks


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def _daily(ticker: str):
    import yfinance as yf
    df = yf.Ticker(ticker).history(period="1y", auto_adjust=False)
    return df if df is not None and not df.empty else None


def _technical(df) -> dict:
    """Manual momentum indicators on underlying 1y daily OHLCV."""
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
    support = float(np.min(low[-21:-1])) if n >= 21 else None
    highest_high_22d = float(np.max(high[-22:])) if n >= 22 else None
    lowest_low_22d = float(np.min(low[-22:])) if n >= 22 else None
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
        "support_20d": round(support, 2) if support else None,
        "highest_high_22d": round(highest_high_22d, 2) if highest_high_22d else None,
        "lowest_low_22d": round(lowest_low_22d, 2) if lowest_low_22d else None,
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
    # Liquidity = EXECUTABLE market. "Liquid" requires a real two-sided quote
    # (positive bid AND ask) with an acceptable spread; that is the only state a
    # GO verdict may rely on, because it's the only one with a tradeable premium
    # and a verifiable slippage cost. Volume/OI alone (e.g. market closed, so
    # bid/ask=0) is INDICATIVE only — the premium/breakeven shown are stale and
    # there's no spread to trade against, so it must NOT count as liquid.
    if best["spread_pct"] is not None:   # positive bid & ask were present
        best["liquid"] = bool(best["spread_pct"] <= MAX_SPREAD_PCT
                              and (best["open_interest"] >= 100 or best["volume"] >= 100))
        best["executable"] = True
        best["liquidity_basis"] = "two-sided quote (spread)"
    else:
        best["liquid"] = False
        best["executable"] = False
        best["premium_indicative"] = True
        best["liquidity_basis"] = "indicative — no bid/ask (market likely closed); premium is last-trade, not executable"
    return best


def _earnings_within(tk, dte_days: int) -> dict:
    """Next earnings date relative to the DTE window.

    Returns an explicit state: status is "clear" (known, outside DTE),
    "within_dte" (known, inside DTE → IV-crush risk), or "unknown" (no data).
    UNKNOWN is NOT treated as clear by callers — a missing earnings date must not
    silently pass the IV-crush gate.
    """
    def _to_days(ed):
        return (datetime(ed.year, ed.month, ed.day) - datetime.now()).days

    # Source 1: calendar
    try:
        cal = tk.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            ed = dates[0] if isinstance(dates, (list, tuple)) else dates
            days = _to_days(ed)
            within = 0 <= days <= dte_days
            return {"available": True, "date": str(ed), "days_away": days,
                    "within_dte": within, "status": "within_dte" if within else "clear"}
    except Exception:
        pass

    # Source 2: earnings_dates (next future date in the index)
    try:
        ed_df = tk.earnings_dates
        if ed_df is not None and not ed_df.empty:
            now = datetime.now()
            future = [d for d in ed_df.index.to_pydatetime() if d.replace(tzinfo=None) >= now]
            if future:
                nxt = min(future).replace(tzinfo=None)
                days = (nxt - now).days
                within = 0 <= days <= dte_days
                return {"available": True, "date": nxt.strftime("%Y-%m-%d"),
                        "days_away": days, "within_dte": within,
                        "status": "within_dte" if within else "clear"}
    except Exception:
        pass

    return {"available": False, "date": None, "days_away": None,
            "within_dte": None, "status": "unknown"}


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
        earnings = {"available": False, "date": None, "days_away": None,
                    "within_dte": None, "status": "unknown", "error": str(e)}

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

    # Only a REAL IV-history percentile may drive volatility gates; the
    # realized-vol proxy is informational and must not produce GO or a high-IV
    # AVOID (it isn't option-implied vol).
    iv_real = iv_pct_source.startswith("iv_history")
    earnings_known = bool(earnings and earnings.get("available"))
    contract_executable = bool(contract and contract.get("executable"))

    # ---- Entry checklist (the strategy's hard gates) ----
    checks = {
        "bollinger_squeeze": tech["bb_squeeze"],
        "breakout_on_volume": tech["breakout_above_resistance"],
        "rvol_ge_2": bool(tech["rvol"] and tech["rvol"] >= 2.0),
        "price_above_vwap": tech["price_above_vwap"],
        # credible only with a REAL IV-history percentile, not the RV proxy
        "iv_low_base": bool(iv_real and iv_pct is not None and iv_pct < IVP_LOW),
        "contract_in_sweet_spot": bool(contract and contract.get("in_delta_sweet_spot")),
        # liquid == executable two-sided quote (see _select_contract)
        "contract_liquid": contract_executable and bool(contract.get("liquid")),
        # clear only when KNOWN and outside the DTE window; unknown ≠ clear
        "earnings_clear": bool(earnings and earnings.get("status") == "clear"),
        "breakeven_reachable": bool(breakeven_reachable),
        "regime_risk_on": regime.get("risk_on") is True,
    }

    # Data-quality blockers: unknown/proxy/stale inputs that must prevent a GO
    # (the review's core point — don't manufacture confidence from missing data).
    data_blockers = []
    if not iv_real:
        data_blockers.append("IV percentile is a realized-vol PROXY (no real IV history yet) — wire/await daily IV snapshots")
    if not earnings_known:
        data_blockers.append("next earnings date unknown — cannot rule out an IV-crush window")
    if not contract_executable:
        data_blockers.append("no executable two-sided quote (market closed?) — premium/breakeven are indicative only")

    reasons = []
    # ---- Verdict ----
    # Hard AVOID only on genuine, KNOWN negative signals.
    if earnings and earnings.get("status") == "within_dte":
        verdict = "AVOID"
        reasons.append(f"earnings in {earnings.get('days_away')}d (inside DTE) → IV-crush risk")
    elif iv_real and iv_pct is not None and iv_pct >= IVP_HIGH:
        verdict = "AVOID"
        reasons.append(f"real IV percentile {iv_pct} ≥ {IVP_HIGH:.0f} — expensive premium / IV-crush risk")
    elif regime.get("risk_on") is False:
        verdict = "AVOID"
        reasons.append("market regime risk-off — momentum longs unfavorable")
    elif data_blockers:
        # Insufficient/proxy data → cannot be GO. Cap at WAIT (data-missing).
        verdict = "WAIT"
        reasons.append("data insufficient for a GO decision: " + "; ".join(data_blockers))
    else:
        core = (checks["breakout_on_volume"] and checks["price_above_vwap"]
                and checks["contract_in_sweet_spot"] and checks["contract_liquid"]
                and checks["iv_low_base"] and checks["earnings_clear"]
                and checks["breakeven_reachable"])
        if core and checks["regime_risk_on"]:
            verdict = "GO"
            reasons.append("breakout on volume + above VWAP + real low-IV base + executable Δ0.3-0.4 contract + earnings clear + risk-on")
        elif checks["bollinger_squeeze"] and not checks["breakout_on_volume"]:
            verdict = "WAIT"
            reasons.append("coiling (Bollinger squeeze) but no volume breakout yet — watch for the trigger")
        else:
            verdict = "WAIT"
            reasons.append("partial setup — not all entry gates met")
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
        "data_quality": {
            "iv_percentile_real": iv_real,
            "earnings_known": earnings_known,
            "contract_executable": contract_executable,
            "go_blocked_by": data_blockers,
            "go_eligible": not data_blockers,
        },
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
            "iv_percentile_real": iv_real,
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
