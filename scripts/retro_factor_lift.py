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


def is_recommendations_blocked(meta: dict) -> bool:
    """Canonical FAIL-CLOSED gate (shared by report + modules + UI): a run is
    unblocked ONLY when recommendations_blocked is explicitly False AND it is
    self-consistent (low_confidence False AND coverage.sample_experiment False).
    Missing/null/inconsistent metadata → blocked."""
    return not (meta.get("recommendations_blocked") is False
                and meta.get("low_confidence") is False
                and (meta.get("coverage") or {}).get("sample_experiment") is False)


def coverage_gate(universe: str, scanned: int, unique_surgers: int,
                  surge_event_count: int, control_ticker_count: int,
                  allow_survivorship_biased: bool = False) -> tuple:
    """(coverage dict, low_confidence, recommendations_blocked).

    recommendations_blocked is True whenever the run is low_confidence (not
    representative / underpowered) OR survivorship-biased. The labeler only sees
    CURRENT index members — delisted surgers and post-surge joiners are absent — so
    survivorship_bias is ALWAYS True and, by default, blocks recommendations: a
    known-biased sample must not auto-propose weight/prompt changes. Unblocking
    requires point-in-time-constituent data OR the explicit allow_survivorship_biased
    opt-in (which acknowledges the findings are non-actionable evidence, not a fix).
    """
    intended = _UNIVERSE_SIZE.get(universe)  # None for custom / unknown
    coverage_ratio = round(scanned / intended, 3) if intended else None
    control_coverage = round(control_ticker_count / scanned, 3) if scanned else None
    sample_experiment = ((intended is None)
                         or (coverage_ratio is not None and coverage_ratio < 0.5)
                         or (control_coverage is not None and control_coverage < 0.5))
    low_confidence = (surge_event_count < 30 or sample_experiment or unique_surgers < 10)
    survivorship_blocks = not allow_survivorship_biased
    recommendations_blocked = low_confidence or survivorship_blocks
    coverage = {
        "universe": universe,
        "tickers_scanned": scanned,
        "intended_universe_size": intended,
        "coverage_ratio": coverage_ratio,
        "unique_surger_tickers": unique_surgers,
        "control_ticker_count": control_ticker_count,
        "control_coverage": control_coverage,
        "surge_event_count": surge_event_count,
        # Index lists are CURRENT members only — survivorship bias is ALWAYS present.
        "survivorship_bias": True,
        "survivorship_blocks_recommendations": survivorship_blocks,
        "sample_experiment": sample_experiment,
        "low_confidence": low_confidence,
    }
    return coverage, low_confidence, recommendations_blocked


def _hits(rec: dict) -> list:
    """Threshold labels a record cleared. Accepts the current `thresholds_hit`
    list and falls back to the legacy singular `threshold`, so older snapshots
    (one row per threshold) still load without a KeyError during the migration."""
    h = rec.get("thresholds_hit")
    if isinstance(h, list):
        return h
    t = rec.get("threshold")
    return [t] if t else []


def _build_control_pool(scanned_tickers, rng, per_ticker: int, period: str,
                        spy_close: pd.Series, vix_close: pd.Series,
                        edgar_factors: list[str], thresholds: list[tuple],
                        lookback_start: pd.Timestamp | None = None,
                        lookback_end: pd.Timestamp | None = None,
                        confirm_pct: float = 0.07, max_offset: int = 12) -> list[dict]:
    """Pool of confirmation-trigger controls from the FULL scanned universe.

    Each entry is a +confirm_pct confirmation day, with — for EVERY threshold tier
    (label, pct, win) — whether it reached pct within THAT tier's OWN window stored
    in `hits`. A confirmation is kept iff it did NOT hit every tier (a confirmation
    that surges on all tiers is a positive, never a control). The caller then derives
    each table's hard negatives by tier: a control for tier T is a pooled confirmation
    with hits[T] == False (it fired the same +7% trigger but did not become a T-surge
    in T's window) and outside T's surge windows. Using each tier's own window is the
    point — a move that reaches +30% only on day 40 is NOT a +30%/20d surge, so it is
    a valid +30%/20d hard negative.

    Drawn from scanned_tickers (not only surger tickers), bounded to
    [lookback_start, lookback_end] (4y fetch is warmup only). EDGAR flags when backfilled.
    """
    edgar_fn = None
    if edgar_factors:
        import retro_edgar_backfill as reb
        edgar_fn = reb.edgar_flags
    max_window = max((w for _, _, w in thresholds), default=60)

    pool: list[dict] = []
    for t in sorted(scanned_tickers):
        df = rr._hist_auto_adjust_false(t, period)
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        if lookback_end is not None:
            df = df[df.index <= lookback_end]
        if len(df) < 300:
            continue
        close = df["Close"].to_numpy(dtype=float)
        pos = {d: k for k, d in enumerate(df.index)}
        cand = []  # (date, hits, fwd_max_gain)
        for cd in rr.confirmation_days(df, confirm_pct, max_offset):
            k = pos.get(cd)
            if k is None or k < 252:
                continue
            if lookback_start is not None and cd < lookback_start:
                continue
            # Need the full lookahead for the LARGEST tier window, else unresolved.
            if k + max_window >= len(close):
                continue
            base = close[k]
            hits = {}
            for label, pct, win in thresholds:
                seg = close[k + 1:k + 1 + win]
                hits[label] = bool(seg.size and float(seg.max()) / base - 1.0 >= pct)
            if hits and all(hits.values()):
                continue  # surges on every tier → a positive, never a control
            fwd_max_gain = float(close[k + 1:k + 1 + max_window].max()) / base - 1.0
            cand.append((cd, hits, round(fwd_max_gain, 4)))
        if not cand:
            continue
        kpick = min(per_ticker, len(cand))
        picks = rng.choice(len(cand), size=kpick, replace=False)
        for idx in picks:
            d, hits, gain = cand[int(idx)]
            flags = rr.reconstruct_flags(df, spy_close, vix_close, d)
            if flags is not None:
                if edgar_fn is not None:
                    flags.update(edgar_fn(t, d.strftime("%Y-%m-%d")))
                pool.append({"ticker": t, "date": d.strftime("%Y-%m-%d"),
                             "flags": flags, "hits": hits,
                             "fwd_max_gain": gain, "kind": "confirmation"})
    return pool


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


MIN_KNOWN = 5       # minimum known (non-None) observations required in EACH arm
MIN_ZERO_CELL = 25  # a 0%/100% arm needs this many obs before its rate is trustworthy


def _verdict(lift: float, support: int, n_control_known: int, ci,
             control_true: int = 0) -> str:
    # Power gate on BOTH arms: a factor present in 20 surgers but with ZERO known
    # controls otherwise computes p_control=0 → lift=cap → "VALIDATED" off one-sided
    # evidence. Require enough known observations on each side AND a real CI.
    if support < MIN_KNOWN or n_control_known < MIN_KNOWN:
        return "INSUFFICIENT"
    if not isinstance(ci, list) or ci[0] is None or ci[1] is None:
        return "INSUFFICIENT"
    # Zero-cell guard: if the control arm is all-False (0%) or all-True (100%), the
    # bootstrap CI collapses to the cap and reads as certainty. A degenerate rate
    # needs a much larger sample before it can bound the ratio (e.g. 0/5 ≠ 0/200).
    if (control_true == 0 or control_true == n_control_known) \
            and n_control_known < MIN_ZERO_CELL:
        return "INSUFFICIENT"
    lo, hi = ci
    # Significance: a positive verdict needs the whole 90% CI ABOVE the no-edge line
    # (lo > 1.0); a CONTRARIAN needs it entirely BELOW (hi < 1.0). A CI straddling
    # 1.0 is statistically unresolved → NOISE, never VALIDATED/WEAK.
    if lift >= 1.5 and support >= 20 and lo > 1.0:
        return "VALIDATED"
    if lift >= 1.1 and lo > 1.0:
        return "WEAK"
    if lift < 0.9 and hi < 1.0:
        return "CONTRARIAN"
    return "NOISE"


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
        ci = _bootstrap_lift_ci(s_vals, c_vals, rng)
        out.append({
            "factor": factor,
            "dimension": meta["dimension"],
            "subfactor": meta["subfactor"],
            "desc": meta["desc"],
            "p_surge": round(p_s, 3),
            "p_control": round(p_c, 3),
            "lift": round(lift, 2),
            "lift_ci90": ci,
            "precision": round(precision, 3),
            "precision_lift": round(precision_lift, 2),
            "woe": round(woe, 3),
            "information_value": round(iv, 4),
            "support": t_s,           # # surgers with the factor present
            "n_surge": n_s,
            "n_control": n_c,
            "verdict": _verdict(lift, t_s, n_c, ci, control_true=t_c),
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
    ap.add_argument("--allow-survivorship-biased", action="store_true",
                    help="opt in to unblock recommendations despite current-member-only "
                         "survivorship bias (findings stay non-actionable evidence)")
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

    # Per-THRESHOLD surge run-up windows (episode hit that tier) + the union. Used
    # to exclude confirmations inside a real surge — threshold-specific so the +50%
    # table can still use sub-50% movers (which ARE +30/+40 episodes) as hard negatives.
    from collections import defaultdict
    thr_list = [(t["label"], t["pct"], t["window"])
                for t in events_payload.get("thresholds", [])]
    thr_pct = {lab: p for lab, p, _ in thr_list}
    min_pct = min(thr_pct.values()) if thr_pct else 0.30
    windows_by_thr: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    windows_all: dict[str, list] = defaultdict(list)
    for ev in events_payload.get("events", []):
        s, p = ev.get("surge_start"), ev.get("peak_date")
        if not (s and p):
            continue
        win = (pd.Timestamp(s).normalize(), pd.Timestamp(p).normalize())
        windows_all[ev["ticker"]].append(win)
        for lab in _hits(ev):
            windows_by_thr[lab][ev["ticker"]].append(win)

    # Controls live in the SAME labeled window as the positives (see _build_control_pool).
    lookback_days = events_payload.get("lookback_days", 730)
    gen = events_payload.get("generated_at")
    try:
        gen_date = pd.Timestamp(gen).tz_localize(None).normalize() if gen else pd.Timestamp.utcnow().normalize()
    except (ValueError, TypeError):
        gen_date = pd.Timestamp.utcnow().normalize()
    lookback_start = gen_date - pd.Timedelta(days=lookback_days)

    # Build the pool from the FULL scanned universe (not only surger tickers).
    scanned_tickers = events_payload.get("scanned_tickers") or sorted(tickers)
    target_controls = int(len(features) * args.control_multiple)
    per_ticker = max(2, target_controls // max(1, len(scanned_tickers)) + 1)
    pool = _build_control_pool(scanned_tickers, rng, per_ticker, args.period,
                               spy_close, vix_close, edgar_factors, thr_list,
                               lookback_start=lookback_start, lookback_end=gen_date)
    control_ticker_count = len({c["ticker"] for c in pool})
    print(f"[lift] surgers={len(features)} pool={len(pool)} "
          f"control_tickers={control_ticker_count}/{len(scanned_tickers)}")

    def _controls_for(label_or_all: str, wmap: dict) -> list[dict]:
        """Threshold-matched hard negatives, evaluated against EACH tier's OWN window.
        For a tier label: a pooled confirmation that did NOT hit that tier (within its
        window) and is outside that tier's surge windows. For "ALL": a confirmation
        that hit NO tier (a genuine non-surger) outside any surge window."""
        out = []
        for c in pool:
            h = c.get("hits", {})
            if label_or_all == "ALL":
                if h and any(h.values()):   # hit some tier → it is a surge, not a control
                    continue
            elif h.get(label_or_all):       # hit THIS tier → not a control for it
                continue
            cd = pd.Timestamp(c["date"])
            if any(ws <= cd <= we for ws, we in wmap.get(c["ticker"], [])):
                continue
            out.append(c)
        return out

    # ALL = any-surge baseline: controls that hit NO tier.
    all_controls = _controls_for("ALL", windows_all)

    # One lift table per threshold (episode-level; ALL is unique episodes), each
    # vs its OWN threshold-specific control set. Keep every set so retro_modules
    # can reuse the identical per-threshold baseline (not just the ALL set).
    thresholds = sorted({lab for r in features for lab in _hits(r)})
    controls_by_thr = {"ALL": all_controls}
    tables = {}
    for label in ["ALL", *thresholds]:
        if label == "ALL":
            sub, ctrls = features, all_controls
        else:
            sub = [r for r in features if label in _hits(r)]
            ctrls = _controls_for(label, windows_by_thr.get(label, {}))
            controls_by_thr[label] = ctrls
        tables[label] = {
            "n_surge_events": len(sub),
            "n_controls": len(ctrls),
            "factors": compute_lift(sub, ctrls, factor_defs, rng),
        }

    # Persist for retro_modules: the ALL set under `controls` (back-compat) PLUS
    # each threshold's own set under `by_threshold`, so module lift uses the SAME
    # per-threshold baseline as the factor lift above. `source` stamps which surge
    # run these controls belong to, so retro_modules can refuse to pair them with a
    # different surge_features (stale/mismatched controls → wrong baseline).
    (OUT_DIR / "control_features.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "source": {
                        "features_generated_at": feat.get("generated_at"),
                        "events_generated_at": events_payload.get("generated_at"),
                        "universe": events_payload.get("universe"),
                        "lookback_days": events_payload.get("lookback_days"),
                        "thresholds": sorted(thr_pct.keys()),
                    },
                    "control_count": len(all_controls),
                    "controls": all_controls,
                    "by_threshold": {lab: {"control_count": len(cs), "controls": cs}
                                     for lab, cs in controls_by_thr.items()}}, indent=2),
        encoding="utf-8")

    # Coverage / power gate — small, partial-universe, OR underpowered runs must NOT
    # feed AI weight/prompt recommendations. recommendations_blocked == low_confidence.
    coverage, low_confidence, recommendations_blocked = coverage_gate(
        events_payload.get("universe", ""),
        events_payload.get("tickers_scanned", len(tickers)),
        len(tickers), len(features), control_ticker_count,
        allow_survivorship_biased=args.allow_survivorship_biased)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # Provenance fingerprint so retro_modules can confirm THIS lift's coverage
        # gate belongs to the surge/control run it is pairing with.
        "source": {
            "features_generated_at": feat.get("generated_at"),
            "events_generated_at": events_payload.get("generated_at"),
            "universe": events_payload.get("universe"),
            "lookback_days": events_payload.get("lookback_days"),
        },
        "control_count": len(all_controls),
        "control_pool_size": len(pool),
        "control_multiple": args.control_multiple,
        "control_design": "confirmation-trigger-matched from the FULL scanned "
                          "universe; per-threshold hard negatives = confirmed movers "
                          "below that tier's % and outside that tier's surge windows.",
        "thresholds": thresholds,
        "method": "lift = P(factor|surger)/P(factor|threshold-matched-fizzler); "
                  "pure-numpy; 90% CI via 1000-sample bootstrap; verdicts gated on support.",
        "coverage": coverage,
        "low_confidence": low_confidence,
        # HARD gate: when true, downstream (retro_report / UI) must NOT present
        # weight/prompt changes as actionable — unrepresentative OR underpowered.
        "recommendations_blocked": recommendations_blocked,
        "tables": tables,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[lift] {len(thresholds)+1} tables → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
