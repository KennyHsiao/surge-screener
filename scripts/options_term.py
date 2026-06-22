#!/usr/bin/env python3
"""Free options term-structure / skew helper for Risk Guard V3 (Options Risk Pro).

Pulls a couple of yfinance option-chain expiries to derive the downside-risk signals
the plan (§4.6 / §V3) wants but a single chain call can't give:
  - near-term IV backwardation: nearest-expiry ATM IV vs a ~1-month expiry ATM IV.
    Near > far ⇒ event/fear priced into the front (a classic pre-drop tell).
  - put skew: OTM-put (~10% below spot) IV minus ATM IV. Steep ⇒ downside hedging bid.

Pure data fetch (verified-data-to-AI); NEVER raises — returns None on any failure so a
flaky free source can't break a risk scan. Cached 15 min (chains move intraday).

Also exposes OptionsRiskProvider, a stub for a future PAID options-risk feed (Unusual
Whales sweeps/blocks, dealer gamma/GEX, dark pool) so Risk Guard can swap it in later
without touching the scorer.

CLI:  python scripts/options_term.py NVDA AMD
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _cached(namespace: str, params, ttl: float, compute):
    """Best-effort disk cache; falls back to plain compute() if unavailable."""
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
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def _num(x):
    try:
        if x is None:
            return None
        f = float(x)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _dte(expiry: str) -> int | None:
    try:
        d = datetime.strptime(str(expiry), "%Y-%m-%d").date()
        return (d - datetime.now(timezone.utc).date()).days
    except Exception:
        return None


def _atm_iv(chain, spot: float):
    """ATM implied vol: avg of the call & put IV at the strike nearest spot."""
    ivs = []
    for df in (getattr(chain, "calls", None), getattr(chain, "puts", None)):
        if df is None or df.empty:
            continue
        d = df.dropna(subset=["impliedVolatility", "strike"])
        d = d[d["impliedVolatility"] > 0]
        if d.empty:
            continue
        idx = (d["strike"] - spot).abs().idxmin()
        ivs.append(float(d.loc[idx, "impliedVolatility"]))
    return (sum(ivs) / len(ivs)) if ivs else None


def _otm_put_iv(chain, spot: float):
    """IV of the put nearest ~10% below spot (downside-hedge strike)."""
    puts = getattr(chain, "puts", None)
    if puts is None or puts.empty:
        return None
    d = puts.dropna(subset=["impliedVolatility", "strike"])
    d = d[(d["impliedVolatility"] > 0) & (d["strike"] < spot)]
    if d.empty:
        return None
    idx = (d["strike"] - spot * 0.9).abs().idxmin()
    return float(d.loc[idx, "impliedVolatility"])


def _compute_term(ticker: str, spot):
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        tk = yf.Ticker(ticker)
        exps = list(tk.options or [])
        if not exps:
            return None
        if spot is None:
            try:
                spot = float(tk.fast_info.last_price)
            except Exception:
                spot = None
        if not spot or spot <= 0:
            return None
        near_e = exps[0]
        far_e = min(exps, key=lambda e: abs((_dte(e) or 0) - 35))  # ~1-month expiry
        near = tk.option_chain(near_e)
        near_iv = _atm_iv(near, spot)
        far = near if far_e == near_e else tk.option_chain(far_e)
        far_iv = _atm_iv(far, spot)
        # Measure put skew on the ~1-month tenor, NOT the front expiry: ultra-short-dated
        # OTM-put IV is artifactually inflated, which would overstate skew on the near chain.
        otm_put = _otm_put_iv(far, spot)
        skew = (otm_put - far_iv) if (otm_put is not None and far_iv) else None
        backwardation = bool(near_iv and far_iv and near_iv > far_iv * 1.05)
        return {
            "spot": round(spot, 2),
            "near_expiry": near_e, "near_dte": _dte(near_e), "near_atm_iv": near_iv,
            "far_expiry": far_e, "far_dte": _dte(far_e), "far_atm_iv": far_iv,
            "backwardation": backwardation,
            "skew_tenor_dte": _dte(far_e), "otm_put_iv": otm_put,
            "put_skew": (round(skew, 4) if skew is not None else None),
        }
    except Exception:
        return None


def term_structure(ticker: str, spot: float | None = None) -> dict | None:
    """Near/far ATM IV + backwardation + put skew for a ticker (cached 15m). None on failure."""
    if not ticker:
        return None
    spot_val = _num(spot)
    # v3: cache key includes the supplied spot because ATM / OTM strike selection depends on it.
    return _cached("options_term", {"ticker": ticker.upper(), "spot": (
        round(spot_val, 2) if spot_val is not None else None), "v": 3}, 900,
        lambda: _compute_term(ticker, spot_val))


class OptionsRiskProvider:
    """Interface for an options-risk feed. The free build returns None for the
    paid-only signals (sweeps/blocks, dealer gamma/GEX, dark pool, bid/ask aggressor);
    wire a paid implementation (e.g. Unusual Whales) here later without touching the
    Risk Guard scorer (plan §V3)."""

    def get_options_risk(self, ticker: str) -> dict | None:  # noqa: ARG002
        return None


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(term_structure(t), indent=2, ensure_ascii=False))
