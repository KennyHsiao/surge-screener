#!/usr/bin/env python3
"""Deterministic synthetic tests for scripts/reversal_signals.py (RR-1 gate).

Self-contained (no pytest needed): builds hand-crafted OHLCV so each detector's
fire/no-fire is known, and pins the consistency contract (RSI endpoint == _technical,
MACD golden-cross == retro_reconstruct._macd_flags). Run:
    .venv/bin/python scripts/test_reversal_signals.py
Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import momentum_options as mo  # noqa: E402
import retro_reconstruct as rr  # noqa: E402
import reversal_signals as rs  # noqa: E402

_FAILED = []


def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {extra}" if extra and not cond else ""))
    if not cond:
        _FAILED.append(name)


def _df(close, open_=None, high=None, low=None, vol=None):
    close = np.asarray(close, float)
    n = len(close)
    open_ = np.asarray(open_, float) if open_ is not None else close.copy()
    high = np.asarray(high, float) if high is not None else np.maximum(open_, close) + 0.5
    low = np.asarray(low, float) if low is not None else np.minimum(open_, close) - 0.5
    vol = np.asarray(vol, float) if vol is not None else np.full(n, 1e6)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": vol}, index=idx)


print("reversal_signals tests")

# 1) RSI endpoint consistency: _rsi_series[-1] (rounded) == momentum_options._technical rsi14
rng = np.random.default_rng(42)
close = 100 + np.cumsum(rng.normal(0, 1.0, 160))
df = _df(close)
tech = mo._technical(df)
rsi_end = rs._rsi_series(df["Close"].to_numpy(float))[-1]
check("RSI endpoint == _technical['rsi14']",
      round(float(rsi_end), 1) == tech["rsi14"], f"{round(float(rsi_end),1)} vs {tech['rsi14']}")

# 2) MACD golden_cross agrees with retro_reconstruct._macd_flags
m = rs.macd(df)
pos_ref, cross_ref = rr._macd_flags(df["Close"].to_numpy(float))
check("MACD golden_cross_10d == _macd_flags", m["available"] and m["golden_cross_10d"] == bool(cross_ref))
check("MACD positive == _macd_flags", m["available"] and m["positive"] == bool(pos_ref))

# 3) _swing_lows finds the known minima
arr = np.array([10, 9, 8, 9, 10, 11, 7, 8, 9, 10, 11, 12], float)  # minima at idx 2 (8) and 6 (7)
lows = rs._swing_lows(arr, pivot=2)
check("_swing_lows finds minima", set(lows) >= {2, 6}, str(lows))

# 4) _bullish_divergence: price lower-low + indicator higher-low → True; both lower → False
price = np.array([0, 0, 80, 0, 0, 0, 0, 78, 0, 0], float)   # low1=80@2, low2=78@7 (lower)
ind_hi = np.array([0, 0, 20, 0, 0, 0, 0, 30, 0, 0], float)  # 20→30 (higher) → bullish
ind_lo = np.array([0, 0, 30, 0, 0, 0, 0, 20, 0, 0], float)  # 30→20 (lower) → no
div_t, _ = rs._bullish_divergence([7, 2], price, ind_hi)
div_f, _ = rs._bullish_divergence([7, 2], price, ind_lo)
check("_bullish_divergence True on price↓ + ind↑", div_t is True)
check("_bullish_divergence False on price↓ + ind↓", div_f is False)

# 5) capitulation spike_reversal: 3x-vol down day then up day in last 5 bars
n = 120
c = np.full(n, 100.0)
o = c.copy()
hi = c + 0.3
lo = c - 0.3
v = np.full(n, 1e6)
# bar n-2: heavy-volume down day; bar n-1: up reversal (kept a small wick so it doesn't trip hammer)
o[-2], c[-2], hi[-2], lo[-2], v[-2] = 100.0, 97.0, 100.2, 96.5, 3.2e6
o[-1], c[-1], hi[-1], lo[-1], v[-1] = 97.2, 99.5, 99.8, 97.0, 1.0e6
cap = rs.capitulation(_df(c, o, hi, lo, v))
check("capitulation spike_reversal", cap["available"] and cap["capitulation"] and cap["kind"] == "spike_reversal",
      str(cap))

# 6) capitulation hammer: last bar long lower wick, small body, up close
c2 = np.full(n, 100.0)
o2 = c2.copy()
hi2 = c2 + 0.3
lo2 = c2 - 0.3
v2 = np.full(n, 1e6)
o2[-1], c2[-1], hi2[-1], lo2[-1] = 100.0, 100.2, 100.5, 98.0   # lower_wick=(100-98)/2.5=0.8, body=0.08
cap2 = rs.capitulation(_df(c2, o2, hi2, lo2, v2))
check("capitulation hammer", cap2["available"] and cap2["capitulation"] and cap2["kind"] == "hammer", str(cap2))

# 7) quiet tape → no capitulation
cq = np.full(n, 100.0)
quiet = rs.capitulation(_df(cq, cq.copy(), cq + 0.1, cq - 0.1, np.full(n, 1e6)))
check("quiet tape → capitulation False", quiet["available"] and quiet["capitulation"] is False, str(quiet))

# 8) volume dry-up → expansion
cv = np.full(n, 100.0)
cv[-1] = 101.0                       # up day on the expansion bar
ov = cv.copy()
ov[-1] = 100.0
vv = np.full(n, 2e6)
vv[-6:-1] = 0.8e6                    # recent-5 dry-up (0.4x baseline)
vv[-1] = 4e6                         # expansion (2x baseline) on the up day
vexp = rs.volume_dryup_then_expansion(_df(cv, ov, cv + 0.3, cv - 0.3, vv))
check("volume dry-up then expansion", vexp["available"] and vexp["dryup"] and vexp["expansion"], str(vexp))

# 9) ma_reclaim: clearly below MA20 within lookback (a sharp dip), then a 2-day pop back above
cr = np.concatenate([np.full(100, 100.0),
                     np.array([99.0, 97.0, 95.0, 94.0, 93.0, 93.0, 101.0, 102.0])])
rec = rs.ma_reclaim(_df(cr))
check("ma_reclaim reclaim_ma20 True", rec["available"] and rec["reclaim_ma20"], str(rec))

# 10) clean monotonic downtrend → no RSI bullish divergence
cdown = np.linspace(160, 80, 120)
divd = rs.rsi_divergence(_df(cdown))
check("clean downtrend → no RSI divergence", divd["available"] and divd["bullish_divergence"] is False, str(divd))

# 11) too-little data → available False (never raises)
short = rs.all_signals(_df(np.full(30, 100.0)))
check("short df → macd available False", short["macd"]["available"] is False)

print()
if _FAILED:
    print(f"FAILED ({len(_FAILED)}): {_FAILED}")
    sys.exit(1)
print("ALL PASS")
