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
# Approx intended sizes per universe, for the coverage gate (a run scanning far
# fewer tickers than this is a sample experiment, not a universe-representative run).
_UNIVERSE_SIZE = {"sp1500": 1500, "russell3000": 3000, "nasdaq_only": 100}


def _build_controls(features_tickers: set[str], rng, per_ticker: int, period: str,
                    spy_close: pd.Series, vix_close: pd.Series,
                    edgar_factors: list[str],
                    surge_windows: dict[str, list] | None = None,
                    lookback_start: pd.Timestamp | None = None,
                    lookback_end: pd.Timestamp | None = None,
                    surge_min: float = 0.30,
                    confirm_pct: float = 0.07, max_offset: int = 12,
                    fwd_horizon: int = 60) -> list[dict]:
    """Confirmation-trigger-MATCHED controls: dates that fired the SAME +confirm_pct
    trigger as the surge positives but did NOT go on to surge.

    This is the crux of an unbiased lift. Positives are reconstructed at the
    confirmation day (first session ≥ confirm_pct off the trough). If controls were
    random days, the lift would just measure "already in an early winning move vs a
    random day" and inflate momentum/volume factors. Instead, for each ticker we
    enumerate ALL confirmation triggers and keep those whose forward max gain over
    fwd_horizon sessions stayed BELOW surge_min (the mildest surge threshold) — i.e.
    the move fizzled. Lift then answers the ex-ante question: given a confirmation,
    what separates future surgers from fizzlers?

    If the feature set was EDGAR-backfilled, controls get the same Dim2/Dim4 flags.
    """
    edgar_fn = None
    if edgar_factors:
        import retro_edgar_backfill as reb
        edgar_fn = reb.edgar_flags

    controls: list[dict] = []
    for t in sorted(features_tickers):
        df = rr._hist_auto_adjust_false(t, period)
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        # CAP the history at the labeled window end. The 4y fetch is only for
        # indicator warmup; if lift runs after the labeler, dates in (gen_date, now]
        # are UNLABELED, and a confirmation whose forward-fwd_horizon window reaches
        # past gen_date could sit inside a surge that peaks beyond the labeled period
        # (so surge_windows can't exclude it). Dropping post-window data makes such a
        # confirmation's forward window short → flagged unresolved → skipped, and
        # bounds controls to [lookback_start, lookback_end] = the fully-labeled period.
        if lookback_end is not None:
            df = df[df.index <= lookback_end]
        if len(df) < 300:
            continue
        close = df["Close"].to_numpy(dtype=float)
        pos = {d: k for k, d in enumerate(df.index)}
        windows = (surge_windows or {}).get(t, [])  # true surge run-up windows
        # Failed confirmations: triggered the +confirm_pct move, ≥252d warmup, but
        # forward max gain stayed below the mildest surge threshold.
        cand = []
        for cd in rr.confirmation_days(df, confirm_pct, max_offset):
            k = pos.get(cd)
            if k is None or k < 252:
                continue
            # Restrict controls to the SAME labeled window as the positives. The 4y
            # history is fetched only for indicator warmup; surge_windows is built
            # from events labeled over the lookback period, so a confirmation OLDER
            # than that window could sit inside a real-but-UNLABELED surge and slip
            # past the exclusion below. Bounding controls to [lookback_start, now]
            # keeps positives and controls in the same, fully-labeled period.
            if lookback_start is not None and cd < lookback_start:
                continue
            # Exclude confirmations INSIDE a real surge run-up: a genuine surger
            # late in its move can have small remaining upside (fwd_max_gain <
            # surge_min) yet is NOT a fizzler — counting it would seed true surgers
            # into the control group and deflate every lift ratio.
            if any(ws <= cd <= we for ws, we in windows):
                continue
            seg = close[k + 1:k + 1 + fwd_horizon]
            # Skip UNRESOLVED windows: a confirmation in the last fwd_horizon
            # sessions hasn't had the full lookahead to prove whether it surges,
            # so it must not be counted as a failed (fizzler) control.
            if seg.size < fwd_horizon:
                continue
            fwd_max_gain = float(seg.max()) / close[k] - 1.0
            if fwd_max_gain < surge_min:
                cand.append(cd)
        if not cand:
            continue
        kpick = min(per_ticker, len(cand))
        picks = rng.choice(len(cand), size=kpick, replace=False)
        for idx in picks:
            d = cand[int(idx)]
            flags = rr.reconstruct_flags(df, spy_close, vix_close, d)
            if flags is not None:
                if edgar_fn is not None:
                    flags.update(edgar_fn(t, d.strftime("%Y-%m-%d")))
                controls.append({"ticker": t, "date": d.strftime("%Y-%m-%d"),
                                 "flags": flags, "kind": "failed_confirmation"})
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

    events_payload = json.loads(Path(args.events).read_text(encoding="utf-8"))
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

    # If the feature set was EDGAR-backfilled, controls need the same Dim2/Dim4 flags.
    edgar_factors = [k for k, m in factor_defs.items()
                     if m.get("dimension") in ("Dim2", "Dim4")]

    # True surge run-up windows per ticker (surge_start → peak), so controls can
    # exclude confirmation days inside a genuine surge.
    from collections import defaultdict
    surge_windows: dict[str, list] = defaultdict(list)
    for ev in events_payload.get("events", []):
        s, p = ev.get("surge_start"), ev.get("peak_date")
        if s and p:
            surge_windows[ev["ticker"]].append(
                (pd.Timestamp(s).normalize(), pd.Timestamp(p).normalize()))

    # Controls must live in the SAME labeled window as the positives (surges were
    # only labeled over lookback_days), else an older confirmation could sit inside
    # a real-but-unlabeled surge that surge_windows doesn't cover. Derive the start
    # from the events' own generated_at minus lookback_days.
    lookback_days = events_payload.get("lookback_days", 730)
    gen = events_payload.get("generated_at")
    try:
        gen_date = pd.Timestamp(gen).tz_localize(None).normalize() if gen else pd.Timestamp.utcnow().normalize()
    except (ValueError, TypeError):
        gen_date = pd.Timestamp.utcnow().normalize()
    lookback_start = gen_date - pd.Timedelta(days=lookback_days)

    # Size the control pool to ~control-multiple × surgers, spread over tickers.
    target_controls = int(len(features) * args.control_multiple)
    per_ticker = max(2, target_controls // max(1, len(tickers)) + 1)
    controls = _build_controls(tickers, rng, per_ticker, args.period,
                               spy_close, vix_close, edgar_factors,
                               surge_windows=surge_windows,
                               lookback_start=lookback_start,
                               lookback_end=gen_date)
    print(f"[lift] surgers={len(features)} controls={len(controls)} "
          f"tickers={len(tickers)}")

    # Persist the control set (with flags, incl. EDGAR) so retro_modules can reuse
    # it — the control build is the expensive part (SPY/VIX + reconstruct + EDGAR);
    # writing it once means module validation re-runs instantly without re-fetching.
    (OUT_DIR / "control_features.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "control_count": len(controls), "controls": controls}, indent=2),
        encoding="utf-8")

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

    # Coverage / survivorship gate — small or partial-universe runs must NOT feed
    # AI weight/prompt recommendations as if they spoke for the whole universe.
    universe = events_payload.get("universe", "")
    scanned = events_payload.get("tickers_scanned", len(tickers))
    intended = _UNIVERSE_SIZE.get(universe)  # None for custom / unknown
    coverage_ratio = round(scanned / intended, 3) if intended else None
    unique_surgers = len(tickers)
    # A sample experiment: custom/unknown universe, or scanned < half the intended.
    sample_experiment = (intended is None) or (coverage_ratio is not None
                                               and coverage_ratio < 0.5)
    low_confidence = (len(features) < 30 or sample_experiment or unique_surgers < 10)
    coverage = {
        "universe": universe,
        "tickers_scanned": scanned,
        "intended_universe_size": intended,
        "coverage_ratio": coverage_ratio,
        "unique_surger_tickers": unique_surgers,
        "surge_event_count": len(features),
        # Index lists are CURRENT members only — point-in-time membership isn't
        # available, so survivorship bias is ALWAYS present (delisted surgers absent,
        # names that joined post-surge over-counted). Stated, never silently assumed away.
        "survivorship_bias": True,
        "sample_experiment": sample_experiment,
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "control_count": len(controls),
        "control_multiple": args.control_multiple,
        "control_design": "confirmation-trigger-matched (failed +7% confirmations "
                          "that did not reach +30%) — not random days",
        "thresholds": thresholds,
        "method": "lift = P(factor|surger)/P(factor|matched-failed-confirmation); "
                  "pure-numpy; 90% CI via 1000-sample bootstrap; verdicts gated on support.",
        "coverage": coverage,
        "low_confidence": low_confidence,
        # HARD gate: when true, downstream (retro_report / UI) must NOT present
        # weight/prompt changes as actionable — the evidence base is unrepresentative.
        "recommendations_blocked": sample_experiment,
        "tables": tables,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[lift] {len(thresholds)+1} tables → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
