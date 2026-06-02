#!/usr/bin/env python3
"""Shared options math — ONE Black-Scholes source for the whole app.

Both the momentum-options engine (scripts/momentum_options.py, scalar Greeks for
the checklist) and the cockpit UI (ui/options_cockpit.py, vectorized payoff / POP
/ expected-move) import from here, so the P/L diagram is provably consistent with
the Greeks the verdict relies on — they can no longer drift.

Pure math: stdlib ``math`` + numpy only (NO scipy, NO matplotlib). ``ncdf`` is
polymorphic — scalar in → float out (engine), array-like in → np.ndarray out
(payoff) — so both paths share the exact same normal CDF and d1/d2 convention.
"""

from __future__ import annotations

import math

import numpy as np

R_FREE = 0.045  # annualized risk-free proxy used across the app's Greeks/pricing.


def ncdf(x):
    """Standard-normal CDF (scipy-free, via ``math.erf``).

    Scalar in → float out (engine Greeks); array-like in → np.ndarray out
    (vectorized payoff). Keeping both shapes lets the two callers share one CDF.
    """
    if np.isscalar(x):
        return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))
    arr = np.asarray(x, dtype=float)
    flat = np.array([0.5 * (1.0 + math.erf(v / math.sqrt(2.0))) for v in arr.ravel()])
    return flat.reshape(arr.shape)


def npdf(x: float) -> float:
    """Standard-normal PDF (scalar)."""
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def bs_call_greeks(S: float, K: float, T: float, r: float, sigma: float) -> dict:
    """Black-Scholes call greeks. T in years. theta per calendar day, vega per 1% IV.

    Returns rounded floats, or all-None when inputs are degenerate (T/sigma<=0).
    """
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}
    d1 = (math.log(S / K) + (r + sigma * sigma / 2.0) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    delta = ncdf(d1)
    gamma = npdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-S * npdf(d1) * sigma / (2.0 * math.sqrt(T))
             - r * K * math.exp(-r * T) * ncdf(d2)) / 365.0
    vega = S * npdf(d1) * math.sqrt(T) / 100.0
    return {"delta": round(delta, 3), "gamma": round(gamma, 5),
            "theta": round(theta, 4), "vega": round(vega, 4)}


def bs_call_value(S, K: float, T: float, sigma: float, r: float = R_FREE) -> np.ndarray:
    """Vectorized Black-Scholes call value. T in years. Intrinsic at/over expiry."""
    S = np.asarray(S, dtype=float)
    if T <= 0 or sigma <= 0:
        return np.maximum(S - K, 0.0)
    vol_t = sigma * math.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / vol_t
    d2 = d1 - vol_t
    return S * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)


def prob_of_profit(spot: float, breakeven: float, sigma: float, dte: int) -> float:
    """P(S_T > breakeven) under a zero-drift lognormal (the retail convention). 0–100."""
    T = max(dte, 0) / 365.0
    if T <= 0 or sigma <= 0 or spot <= 0:
        return 100.0 if spot > breakeven else 0.0
    vol_t = sigma * math.sqrt(T)
    d2 = (math.log(spot / breakeven) - 0.5 * sigma ** 2 * T) / vol_t
    return float(round(ncdf(np.array([d2]))[0] * 100, 1))


def expected_move(spot: float, sigma: float, dte: int) -> float:
    """1σ expected move ($) over the horizon: spot * IV * sqrt(T)."""
    return spot * sigma * math.sqrt(max(dte, 0) / 365.0)


def implied_vol_call(price, S: float, K: float, T: float, r: float = R_FREE,
                     tol: float = 1e-4, iters: int = 80) -> float | None:
    """Implied vol from a CALL price by bisecting bs_call_value (free-feed IV
    columns are often garbage — invert the price instead). None if the price is
    below intrinsic, ≥ spot, or richer than 500% vol."""
    if price is None or T <= 0 or S <= 0 or K <= 0:
        return None
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if px <= 0:
        return None
    intrinsic = max(S - K * math.exp(-r * T), 0.0)
    if px < intrinsic - 1e-6 or px >= S:
        return None
    lo, hi = 1e-4, 5.0
    if float(bs_call_value(S, K, T, hi, r)) < px:
        return None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        diff = float(bs_call_value(S, K, T, mid, r)) - px
        if abs(diff) < tol:
            return round(mid, 4)
        if diff < 0:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 4)


def implied_vol_put(price, S: float, K: float, T: float, r: float = R_FREE) -> float | None:
    """Implied vol from a PUT price via put-call parity → call inversion."""
    if price is None or T <= 0:
        return None
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    return implied_vol_call(px + S - K * math.exp(-r * T), S, K, T, r)


if __name__ == "__main__":
    # Quick self-check: FD-delta of the value matches the analytic Greek delta.
    S, K, T, sig = 100.0, 105.0, 30 / 365, 0.4
    h = 0.01
    fd = (float(bs_call_value(S + h, K, T, sig)) - float(bs_call_value(S - h, K, T, sig))) / (2 * h)
    g = bs_call_greeks(S, K, T, R_FREE, sig)
    print(f"value FD-delta={fd:.4f}  greeks delta={g['delta']}  POP@BE="
          f"{prob_of_profit(S, K + float(bs_call_value(S, K, T, sig)), sig, 30)}  "
          f"EM={expected_move(S, sig, 30):.2f}")
