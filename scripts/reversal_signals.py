#!/usr/bin/env python3
"""Reversal Radar V1 — leading bottoming/reversal detectors over daily OHLCV.

Pure functions on a 1y/2y daily OHLCV DataFrame (the df from momentum_options._daily).
NO streamlit, NO network; each detector NEVER raises — on too-little/bad data it returns
{"available": False, "reason": ...}.

Consistency contract (the lane warns that a second hand-rolled RSI once contradicted the
validated rsi_40_65 gate): the RSI here uses the SAME simple-mean(14) formula as
momentum_options._technical (so _rsi_series(close)[-1] == tech['rsi14']), and MACD reuses
retro_reconstruct._ema / _macd_flags (so golden_cross agrees with the validated
macd_golden_cross_10d flag). We only ADD what those engines don't compute: RSI/MACD
bullish DIVERGENCE, capitulation/long-lower-wick/hammer, volume dry-up→expansion,
MA-reclaim, and lower-Bollinger snap-back.

CLI:  python scripts/reversal_signals.py NVDA
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

# Reuse the validated EMA/MACD engine so divergence + golden-cross share one definition.
from retro_reconstruct import _ema, _macd_flags  # noqa: E402

RSI_DIV_LOOKBACK = 40      # sessions to search for the two price swing-lows
PIVOT_WINDOW = 3           # local-extreme half-window (a confirmed swing-low needs this many bars each side)
CAPIT_RVOL = 2.0           # capitulation relative-volume floor
WICK_FRAC = 0.6            # lower-wick / close-in-upper-range fraction for hammer/climax
DRYUP_LOOKBACK = 20        # baseline window for volume dry-up
RECLAIM_LOOKBACK = 10      # "was below MA within N sessions, now back above"
MIN_BARS = 60              # below this we can't judge reversal structure


def _ohlcv(df):
    """(open, high, low, close, vol) float arrays, or None if df unusable."""
    try:
        if df is None or len(df) < MIN_BARS:
            return None
        return (df["Open"].to_numpy(float), df["High"].to_numpy(float),
                df["Low"].to_numpy(float), df["Close"].to_numpy(float),
                df["Volume"].to_numpy(float))
    except Exception:  # noqa: BLE001
        return None


def _rsi_series(close: np.ndarray) -> np.ndarray:
    """Rolling RSI(14) whose ENDPOINT equals momentum_options._technical['rsi14']
    (same simple-mean gain/loss over the last 14 diffs)."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < 15:
        return out
    d = np.diff(close)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    for i in range(14, n):                 # rsi at close[i] uses diffs gain[i-14:i]
        ag, al = gain[i - 14:i].mean(), loss[i - 14:i].mean()
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _swing_lows(series: np.ndarray, pivot: int = PIVOT_WINDOW) -> list[int]:
    """Indices of CONFIRMED local minima (lowest within ±pivot). Most-recent first."""
    n = len(series)
    out = []
    for i in range(pivot, n - pivot):
        w = series[i - pivot:i + pivot + 1]
        if np.isnan(w).any():
            continue
        if series[i] == w.min() and series[i] <= w[0] and series[i] <= w[-1]:
            out.append(i)
    return out[::-1]


def _bullish_divergence(price_lows: list[int], price: np.ndarray, ind: np.ndarray):
    """Two most-recent confirmed price lows: price makes a LOWER low while the indicator
    makes a HIGHER low → bullish divergence. Returns (bool, (i1, i2)) or (False, None)."""
    if len(price_lows) < 2:
        return False, None
    i1, i2 = sorted(price_lows[:2])        # i1 = earlier low, i2 = later low
    if np.isnan(ind[i1]) or np.isnan(ind[i2]):
        return False, None
    # bullish divergence: the LATER low is a lower price but a HIGHER indicator reading
    div = bool(price[i2] < price[i1] and ind[i2] > ind[i1])
    return div, (i1, i2)


def macd(df) -> dict:
    """MACD(12/26/9) via the validated _ema; line/signal/hist + positive + golden_cross_10d
    (agrees with retro_reconstruct.macd_golden_cross_10d) + histogram bullish divergence."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    close = o[3]
    if len(close) < 35:
        return {"available": False, "reason": "macd_needs_35_bars"}
    line = _ema(close, 12) - _ema(close, 26)
    signal = _ema(line, 9)
    hist = line - signal
    positive, golden = _macd_flags(close)
    plows = _swing_lows(close[-RSI_DIV_LOOKBACK:]) if len(close) >= RSI_DIV_LOOKBACK else _swing_lows(close)
    base = max(0, len(close) - RSI_DIV_LOOKBACK)
    plows_abs = [base + i for i in plows]
    div, lows = _bullish_divergence(plows_abs, close, hist)
    return {"available": True, "line": round(float(line[-1]), 4),
            "signal": round(float(signal[-1]), 4), "hist": round(float(hist[-1]), 4),
            "positive": bool(positive), "golden_cross_10d": bool(golden),
            "bullish_divergence": div, "reason": None}


def rsi_divergence(df, lookback: int = RSI_DIV_LOOKBACK, pivot: int = PIVOT_WINDOW) -> dict:
    """Price lower-low while RSI(14) makes a higher-low (classic bottoming divergence)."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    close = o[3]
    rsi = _rsi_series(close)
    seg = close[-lookback:]
    base = max(0, len(close) - lookback)
    plows = [base + i for i in _swing_lows(seg, pivot)]
    div, lows = _bullish_divergence(plows, close, rsi)
    rsi_now = rsi[-1]
    return {"available": True, "bullish_divergence": div,
            "rsi": (round(float(rsi_now), 1) if not np.isnan(rsi_now) else None),
            "price_lows": ([int(lows[0]), int(lows[1])] if lows else None),
            "rsi_at_lows": ([round(float(rsi[lows[0]]), 1), round(float(rsi[lows[1]]), 1)]
                            if lows else None),
            "reason": None}


def capitulation(df, rvol_floor: float = CAPIT_RVOL, wick_frac: float = WICK_FRAC,
                 window: int = 5) -> dict:
    """Selling-exhaustion in the last `window` sessions: a high-volume down-day then an
    up reversal, OR a long-lower-wick / hammer / close-in-top-third climax bar."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    op, hi, lo, close, vol = o
    n = len(close)
    avg20 = np.array([(vol[i - 20:i].mean() if i >= 20 else np.nan) for i in range(n)])
    for j in range(n - 1, max(n - 1 - window, 0), -1):
        rng = hi[j] - lo[j]
        if rng <= 0:
            continue
        rv = (vol[j] / avg20[j]) if (avg20[j] and not np.isnan(avg20[j])) else None
        bars_ago = n - 1 - j
        # 1) volume-spike down-day immediately followed by an up reversal day
        if (rv and rv >= rvol_floor and close[j] < op[j]
                and j + 1 < n and close[j + 1] > close[j]):
            return {"available": True, "capitulation": True, "kind": "spike_reversal",
                    "rvol": round(rv, 2), "wick_frac": None, "bars_ago": bars_ago, "reason": None}
        lower_wick = (min(op[j], close[j]) - lo[j]) / rng
        body = abs(close[j] - op[j]) / rng
        # 2) hammer / long lower wick (small body, long lower shadow)
        if lower_wick >= wick_frac and body <= (1 - wick_frac):
            return {"available": True, "capitulation": True, "kind": "hammer",
                    "rvol": (round(rv, 2) if rv else None), "wick_frac": round(lower_wick, 2),
                    "bars_ago": bars_ago, "reason": None}
        # 3) selling climax: heavy volume but close recovers into the TOP third of range
        if rv and rv >= rvol_floor and (close[j] - lo[j]) / rng >= wick_frac:
            return {"available": True, "capitulation": True, "kind": "climax",
                    "rvol": round(rv, 2), "wick_frac": round((close[j] - lo[j]) / rng, 2),
                    "bars_ago": bars_ago, "reason": None}
    return {"available": True, "capitulation": False, "kind": None,
            "rvol": None, "wick_frac": None, "bars_ago": None, "reason": None}


def volume_dryup_then_expansion(df, lookback: int = DRYUP_LOOKBACK) -> dict:
    """Quiet sellers exhausted (recent 5d vol << prior baseline) then demand returns
    (latest vol >= ~1.5x baseline on an up day)."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    op, _hi, _lo, close, vol = o
    n = len(close)
    if n < lookback + 6:
        return {"available": False, "reason": "insufficient_bars"}
    baseline = vol[-(lookback + 5):-5].mean()
    recent5 = vol[-6:-1].mean()
    if not baseline or baseline <= 0:
        return {"available": True, "dryup": False, "expansion": False,
                "dryup_ratio": None, "expansion_rvol": None, "reason": None}
    dryup_ratio = recent5 / baseline
    expansion_rvol = vol[-1] / baseline
    dryup = bool(dryup_ratio <= 0.6)
    expansion = bool(expansion_rvol >= 1.5 and close[-1] > op[-1])
    return {"available": True, "dryup": dryup, "expansion": expansion,
            "dryup_ratio": round(float(dryup_ratio), 2),
            "expansion_rvol": round(float(expansion_rvol), 2), "reason": None}


def _sma_at(close: np.ndarray, w: int, j: int):
    return float(close[j - w + 1:j + 1].mean()) if j + 1 >= w else None


def ma_reclaim(df, lookback: int = RECLAIM_LOOKBACK) -> dict:
    """Price back above MA20/MA50 having been below it within the last `lookback` sessions."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    close = o[3]
    n = len(close)
    px = close[-1]

    def _reclaim(w):
        ma_now = _sma_at(close, w, n - 1)
        if ma_now is None or px <= ma_now:
            return False
        for j in range(max(w - 1, n - 1 - lookback), n - 1):
            ma_j = _sma_at(close, w, j)
            if ma_j is not None and close[j] < ma_j:
                return True
        return False
    return {"available": True, "reclaim_ma20": bool(_reclaim(20)),
            "reclaim_ma50": bool(_reclaim(50)), "reason": None}


def lower_band_snapback(df, window: int = 3) -> dict:
    """Close pierced below the lower Bollinger band within `window` sessions, now back inside."""
    o = _ohlcv(df)
    if o is None:
        return {"available": False, "reason": "insufficient_bars"}
    close = o[3]
    n = len(close)
    if n < 21:
        return {"available": False, "reason": "insufficient_bars"}

    def _bb_lower(j):
        seg = close[j - 19:j + 1]
        return seg.mean() - 2 * seg.std(ddof=0)
    if close[-1] < _bb_lower(n - 1):       # still below the band → not a snap-back yet
        return {"available": True, "snapback": False, "pierced_bars_ago": None, "reason": None}
    for j in range(n - 2, max(n - 1 - window, 19), -1):
        if close[j] < _bb_lower(j):
            return {"available": True, "snapback": True, "pierced_bars_ago": n - 1 - j, "reason": None}
    return {"available": True, "snapback": False, "pierced_bars_ago": None, "reason": None}


def all_signals(df) -> dict:
    """Run every detector once on the same df."""
    return {"macd": macd(df), "rsi_divergence": rsi_divergence(df),
            "capitulation": capitulation(df), "volume": volume_dryup_then_expansion(df),
            "ma_reclaim": ma_reclaim(df), "snapback": lower_band_snapback(df)}


if __name__ == "__main__":
    import json
    import momentum_options as mo
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(all_signals(mo._daily(t)), indent=2, ensure_ascii=False))
