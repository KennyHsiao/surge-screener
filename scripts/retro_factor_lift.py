#!/usr/bin/env python3
"""Surge Retrospective — Stage C: factor lift vs a control group.

A factor that is present in 90% of surgers but ALSO in 90% of all stocks predicts
nothing. To separate signal from base rate we build a CONTROL group — random
(ticker, date) pairs that are NOT inside (or near) any surge window — reconstruct
the exact same flags, and measure how much more often each factor shows up before
a surge than at a random moment. That ratio is the factor's lift.

All statistics are pure numpy (the .venv has NO scipy — 08_self_reflection's
scipy.stats import would crash here). Significance is conveyed with a numpy
bootstrap CI plus hard support gates rather than a p-value.

Run "多門檻一起跑": surgers are grouped by threshold and a separate lift table is
produced for each, so we can see which factors stay predictive as the bar for
"surge" rises (a factor strong only for +30% moves but flat for +50% is weaker
evidence than one that scales).

Verdicts (gated on support so a 2-sample fluke can't read as VALIDATED):
    lift ≥ 1.5 & support ≥ 20 → VALIDATED   (keep / consider up-weighting)
    1.1 ≤ lift < 1.5          → WEAK         (mild edge)
    0.9 ≤ lift < 1.1          → NOISE        (no better than random — candidate to down-weight)
    lift < 0.9                → CONTRARIAN   (present LESS before surges — investigate)
    support < 5               → INSUFFICIENT

CLI:
    python scripts/retro_factor_lift.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

import retro_reconstruct as rr  # noqa: E402 — reuse flag reconstruction + fetch

EPS = 1e-9
N_BOOTSTRAP = 1000
SEED = 42
# Cap lift so a near-zero control rate (p_ctrl≈0) can't read as an absurd ratio;
# anything at the cap means "factor is essentially exclusive to surgers".
LIFT_CAP = 50.0


def _build_controls(events: list[dict], features_tickers: set[str],
                    rng, per_ticker: int, period: str,
                    spy_close: pd.Series, vix_close: pd.Series) -> list[dict]:
    """Random non-surge (ticker, date) flag rows, ≥ window days clear of any event.

    Controls are threshold-agnostic — they exclude ALL surge windows (any
    threshold) so a control date can't leak a real surge setup.
    """
    # Per-ticker excluded date ranges: [start - window, peak + window].
    excl: dict[str, list[tuple]] = {}
    for e in events:
        start = pd.Timestamp(e["surge_start"])
        peak = pd.Timestamp(e["peak_date"])
        pad = pd.Timedelta(days=90)  # ≥ widest window, in calendar days
        excl.setdefault(e["ticker"], []).append((start - pad, peak + pad))

    controls: list[dict] = []
    for t in sorted(features_tickers):
        df = rr._hist_auto_adjust_false(t, period)
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        # Candidate dates: need ≥ 252 sessions of warmup before them.
        if len(df) < 300:
            continue
        candidates = df.index[252:]
        ranges = excl.get(t, [])
        free = [d for d in candidates
                if not any(lo <= d <= hi for lo, hi in ranges)]
        if not free:
            continue
        k = min(per_ticker, len(free))
        picks = rng.choice(len(free), size=k, replace=False)
        for idx in picks:
            d = free[int(idx)]
            flags = rr.reconstruct_flags(df, spy_close, vix_close, d)
            if flags is not None:
                controls.append({"ticker": t, "date": d.strftime("%Y-%m-%d"),
                                 "flags": flags})
    return controls


def _rate(rows: list[dict], factor: str) -> tuple:
    """(p_true, n_known, n_true) ignoring None (insufficient-data) flags."""
    vals = [r["flags"][factor] for r in rows
            if r["flags"].get(factor) is not None]
    n = len(vals)
    n_true = int(sum(1 for v in vals if v))
    return (n_true / n if n else 0.0), n, n_true


def _bootstrap_lift_ci(surge_vals: np.ndarray, ctrl_vals: np.ndarray, rng) -> list:
    """5/95 percentile CI for lift = mean(surge)/mean(ctrl) via resampling."""
    if surge_vals.size == 0 or ctrl_vals.size == 0:
        return [None, None]
    lifts = []
    for _ in range(N_BOOTSTRAP):
        s = surge_vals[rng.integers(0, surge_vals.size, surge_vals.size)].mean()
        c = ctrl_vals[rng.integers(0, ctrl_vals.size, ctrl_vals.size)].mean()
        lifts.append(min(s / (c + EPS), LIFT_CAP))
    return [round(float(np.percentile(lifts, 5)), 2),
            round(float(np.percentile(lifts, 95)), 2)]


def _verdict(lift: float, support: int) -> str:
    if support < 5:
        return "INSUFFICIENT"
    if lift >= 1.5 and support >= 20:
        return "VALIDATED"
    if lift >= 1.1:
        return "WEAK"
    if lift >= 0.9:
        return "NOISE"
    return "CONTRARIAN"


def compute_lift(surgers: list[dict], controls: list[dict],
                 factor_defs: dict, rng) -> list[dict]:
    """Per-factor lift table for one surger set vs the shared control pool."""
    out = []
    for factor, meta in factor_defs.items():
        p_s, n_s, t_s = _rate(surgers, factor)
        p_c, n_c, t_c = _rate(controls, factor)
        base = n_s / (n_s + n_c) if (n_s + n_c) else 0.0
        lift = min(p_s / (p_c + EPS), LIFT_CAP)
        # P(surge | factor present) and its lift over the base rate.
        denom = p_s * n_s + p_c * n_c
        precision = (p_s * n_s) / denom if denom else 0.0
        precision_lift = precision / (base + EPS)
        woe = float(np.log((p_s + EPS) / (p_c + EPS)))
        iv = (p_s - p_c) * woe
        s_vals = np.array([1.0 if r["flags"][factor] else 0.0 for r in surgers
                           if r["flags"].get(factor) is not None])
        c_vals = np.array([1.0 if r["flags"][factor] else 0.0 for r in controls
                           if r["flags"].get(factor) is not None])
        out.append({
            "factor": factor,
            "dimension": meta["dimension"],
            "subfactor": meta["subfactor"],
            "desc": meta["desc"],
            "p_surge": round(p_s, 3),
            "p_control": round(p_c, 3),
            "lift": round(lift, 2),
            "lift_ci90": _bootstrap_lift_ci(s_vals, c_vals, rng),
            "precision": round(precision, 3),
            "precision_lift": round(precision_lift, 2),
            "woe": round(woe, 3),
            "information_value": round(iv, 4),
            "support": t_s,           # # surgers with the factor present
            "n_surge": n_s,
            "n_control": n_c,
            "verdict": _verdict(lift, t_s),
        })
    return sorted(out, key=lambda x: x["lift"], reverse=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — factor lift")
    ap.add_argument("--events", default=str(OUT_DIR / "surge_events.json"))
    ap.add_argument("--features", default=str(OUT_DIR / "surge_features.json"))
    ap.add_argument("--output", default=str(OUT_DIR / "factor_lift.json"))
    ap.add_argument("--control-multiple", type=float, default=4.0,
                    help="control pool ≈ this × surger count")
    ap.add_argument("--period", default="4y")
    args = ap.parse_args()

    events = json.loads(Path(args.events).read_text(encoding="utf-8"))["events"]
    feat = json.loads(Path(args.features).read_text(encoding="utf-8"))
    features, factor_defs = feat["features"], feat["factor_defs"]
    if not features:
        print("[lift] no features", file=sys.stderr)
        return 1

    rng = np.random.default_rng(SEED)
    tickers = {r["ticker"] for r in features}

    # SPY / VIX once (same prep as reconstruct).
    import yfinance as yf
    spy_close = yf.Ticker("SPY").history(period=args.period,
                                          auto_adjust=False)["Close"].dropna()
    vix_close = yf.Ticker("^VIX").history(period=args.period)["Close"].dropna()
    spy_close.index = pd.to_datetime(spy_close.index).tz_localize(None).normalize()
    vix_close.index = pd.to_datetime(vix_close.index).tz_localize(None).normalize()

    # Size the control pool to ~control-multiple × surgers, spread over tickers.
    target_controls = int(len(features) * args.control_multiple)
    per_ticker = max(2, target_controls // max(1, len(tickers)) + 1)
    controls = _build_controls(events, tickers, rng, per_ticker, args.period,
                               spy_close, vix_close)
    print(f"[lift] surgers={len(features)} controls={len(controls)} "
          f"tickers={len(tickers)}")

    # One lift table per threshold (plus an "ALL" combined table).
    thresholds = sorted({r["threshold"] for r in features})
    tables = {}
    for label in ["ALL", *thresholds]:
        sub = features if label == "ALL" else [r for r in features
                                               if r["threshold"] == label]
        tables[label] = {
            "n_surge_events": len(sub),
            "factors": compute_lift(sub, controls, factor_defs, rng),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "control_count": len(controls),
        "control_multiple": args.control_multiple,
        "thresholds": thresholds,
        "method": "lift = P(factor|surge)/P(factor|control); pure-numpy; "
                  "90% CI via 1000-sample bootstrap; verdicts gated on support.",
        "low_confidence": len(features) < 30,
        "tables": tables,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[lift] {len(thresholds)+1} tables → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
