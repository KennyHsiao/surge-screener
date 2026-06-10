#!/usr/bin/env python3
"""Locked resolution contract for the 大盤行情研判 forecast (design v7 §1c). PURE, deterministic, ex-ante.

This is the single source of truth for HOW a market forecast is scored, frozen BEFORE any forecaster exists
so a "miss" can never be re-spun after the fact. Both the forecaster (P3) and the forward scorer (P2,
market_thesis_forward.py) import these constants + `classify()` so they cannot drift.

- Benchmark: ^GSPC (S&P 500 INDEX) daily Close, UNADJUSTED (an index has no dividend/split adjustment).
- Buckets / horizons (sessions): short=20 / mid=40 / long=60. A forecast names ONE primary (direction, bucket).
- Realized state over the window (t0, t0+H], with r = ^GSPC[t0+H]/^GSPC[t0] − 1 and
  peak = max|^GSPC[t]/^GSPC[t0] − 1| over the window (θ_dir default 3%):
    看多   r ≥ +θ_dir
    看空   r ≤ −θ_dir
    盤整   whole path stayed inside ±θ_dir (peak < θ_dir) — a TRUE range
    OTHER  everything else (breached ±θ_dir intra-window but ended inside it; whipsaw) — a real state, MISS
  Exactly one of {看多,看空,盤整,OTHER}; OTHER is never a predicted direction, always a denominator miss.
"""

from __future__ import annotations

import numpy as np

BENCHMARK = "^GSPC"
THETA_DIR = 0.03
BUCKETS = {"short": 20, "mid": 40, "long": 60}          # name → forward sessions (H)
DIRECTIONS = ("看多", "看空", "盤整")                     # a forecast may predict one of these
STATES = ("看多", "看空", "盤整", "OTHER")                # realized states (OTHER is never predicted)
SUPPORT_CLASSES = ("analog_supported", "event_only", "regime_only")
MIN_RESOLVED = 100                                       # non-overlapping matured per key for a MATURE verdict


def classify(path: np.ndarray, theta: float = THETA_DIR) -> str:
    """Realized state for one entry. path = ^GSPC closes [t0, t0+1, …, t0+H] (entry close at index 0).
    Deterministic + exhaustive: returns exactly one of STATES."""
    arr = np.asarray(path, dtype=float)
    if arr.size < 2 or not np.isfinite(arr[0]) or arr[0] <= 0 or not np.isfinite(arr[-1]):
        raise ValueError("classify() needs a full, finite path with a positive entry close")
    rel = arr / arr[0] - 1.0
    r = float(rel[-1])
    peak = float(np.max(np.abs(rel)))     # includes the endpoint, so 看多/看空 ⇒ peak ≥ θ ⇒ never 盤整
    if r >= theta:
        return "看多"
    if r <= -theta:
        return "看空"
    if peak < theta:
        return "盤整"
    return "OTHER"


def forecast_key(rec: dict) -> tuple[str, str, str]:
    """The FULL scoring key — (direction, bucket, support_class). The non-overlap walk, counted_N, Wilson,
    readiness and accuracy ALL use this exact key; classes are never pooled (design v7 §1c)."""
    return (rec["direction"], rec["bucket"], rec["support_class"])


def validate_forecast(rec: dict) -> list[str]:
    """Return a list of contract violations (empty == valid). A forecaster's output must pass this."""
    errs = []
    if rec.get("direction") not in DIRECTIONS:
        errs.append(f"direction {rec.get('direction')!r} not in {DIRECTIONS}")
    if rec.get("bucket") not in BUCKETS:
        errs.append(f"bucket {rec.get('bucket')!r} not in {tuple(BUCKETS)}")
    if rec.get("support_class") not in SUPPORT_CLASSES:
        errs.append(f"support_class {rec.get('support_class')!r} not in {SUPPORT_CLASSES}")
    if not rec.get("as_of"):
        errs.append("missing as_of")
    return errs
