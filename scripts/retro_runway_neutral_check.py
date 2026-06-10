#!/usr/bin/env python3
"""Runway-NEUTRAL re-validation — does any factor still predict a surge once the %-runway
advantage of cheap stocks is removed?

retro_confound_check.py showed the position factors' CONTRARIAN verdicts are largely a
%-runway artifact (a beaten-down stock hits a flat "+X%" target more easily). This goes
further: it re-labels every confirmation (surgers + controls) by a VOLATILITY-NORMALIZED
target — forward max gain measured in ATR-multiples, not percent — so a low-base, high-vol
stock no longer has a built-in edge to a fixed % bar. Then it recomputes each factor's lift
under the neutral target and compares to the original %-target lift.

If a factor's lift moves toward ~1.0 under the neutral target, its original verdict was a
runway artifact. If rvol_ge_2 stays >1 (and any contrarian factor stays <1), that part is a
genuine, runway-independent signal.

Reads the committed surge_features.json + the local control_features.json (with flags + T0),
re-fetches cached OHLCV to compute ATR + forward gain. CLI:
    python scripts/retro_runway_neutral_check.py [reports/retrospective] [--window 60]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
import retro_reconstruct as rr  # noqa: E402 — cached OHLCV fetch

FACTORS = ["rvol_ge_2", "bb_squeeze", "rsi_40_65", "price_above_ma200", "price_above_ma50",
           "within_25pct_of_high", "macd_positive", "rel_strength_vs_spy",
           "price_above_vwap", "above_30pct_of_low"]
POSITION = {"price_above_ma200", "price_above_ma50", "within_25pct_of_high",
            "macd_positive", "rel_strength_vs_spy", "price_above_vwap", "above_30pct_of_low"}


def _atr_pct_and_fwd(df: pd.DataFrame, t0: pd.Timestamp, window: int):
    """(ATR14 as % of price at t0, forward max %-gain over `window` sessions). None if short."""
    d = df[df.index <= t0]
    if len(d) < 15:
        return None, None
    high = d["High"].to_numpy(float); low = d["Low"].to_numpy(float)
    close = d["Close"].to_numpy(float)
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    atr = float(np.mean(tr[-14:]))
    base = float(close[-1])
    if base <= 0 or atr <= 0:
        return None, None
    fwd = df[df.index > t0]["Close"].to_numpy(float)[:window]
    if fwd.size == 0:
        return None, None
    fwd_gain = float(fwd.max()) / base - 1.0
    return atr / base, fwd_gain


def _load_pool(run_dir: Path):
    sf = json.loads((run_dir / "surge_features.json").read_text(encoding="utf-8"))
    cf = json.loads((run_dir / "control_features.json").read_text(encoding="utf-8"))
    # FAIL-CLOSED provenance (integration review): the surge + control pools must descend from
    # the SAME surge_events run, else the ATR-neutral lift mixes a positive/control snapshot
    # from two runs. The fingerprint is returned so the output (and knowledge_runway_sync) can
    # verify it against the sibling factor_lift / cards.
    import retro_factor_lift as _rfl
    fp = (sf.get("source") or {}).get("events_generated_at")
    sf_gen = sf.get("generated_at")
    if not fp:
        raise SystemExit("[runway-neutral] surge_features.json has no source.events_generated_at "
                         "— re-run retro_reconstruct (fail-closed).")
    _rfl.assert_same_run("runway-neutral", fp, control_features=cf)
    # FEATURES adjacency (Codex r8): the controls must also be built from THIS surge_features
    # generation, not just the same events — else stale control flags vs current surger flags.
    if (cf.get("source") or {}).get("features_generated_at") != sf_gen:
        raise SystemExit("[runway-neutral] control_features was built from a different "
                         "surge_features generation than the current one — re-run "
                         "retro_factor_lift (fail-closed).")
    # LIQUIDITY SYMMETRY (Codex r11): control_features may have been liquidity-filtered
    # (source.min_dollar_vol > 0). surge_features.json is NOT rewritten by that filter, so
    # appending ALL surge rows vs the FILTERED controls would compute the ATR-neutral lift on
    # unfiltered positives vs filtered controls (the #5/S2 asymmetry, in the runway path). Apply
    # the SAME floor to the surger arm so both cohorts match.
    # STRICT (Codex r18): a missing/non-numeric floor must NOT default to 0 — a filtered control
    # pool whose floor didn't serialize would skip the surger re-filter → unfiltered positives vs
    # filtered controls (the #5 asymmetry), then get stamped source.min_dollar_vol=0.0 as 'clean'.
    min_dv = _rfl.strict_floor(cf, "source", "min_dollar_vol")
    if min_dv is None:
        raise SystemExit("[runway-neutral] control_features has no recorded source.min_dollar_vol "
                         "(liquidity cohort unknown) — refusing (fail-closed).")
    sf_features = sf["features"]
    if min_dv > 0:
        if not any("avg_dollar_vol_20d" in f for f in sf_features):
            raise SystemExit("[runway-neutral] control_features was liquidity-filtered but "
                             "surge_features has no avg_dollar_vol_20d — re-run retro_reconstruct "
                             "(fail-closed).")
        sf_features, _ = _rfl._filter_by_liquidity(sf_features, min_dv)
    pool = []
    for f in sf_features:
        pool.append({"ticker": f["ticker"], "t0": f.get("observe_date") or f["surge_start"],
                     "flags": f["flags"], "orig_surge": True})
    for c in (cf.get("controls") or cf["by_threshold"]["ALL"]["controls"]):
        pool.append({"ticker": c["ticker"], "t0": c["date"], "flags": c["flags"],
                     "orig_surge": False})
    return pool, fp, sf_gen, min_dv


def _lift(rows, fac, label_key):
    pos = [r for r in rows if r[label_key]]
    neg = [r for r in rows if not r[label_key]]
    s = [r["flags"].get(fac) for r in pos]; s = [x for x in s if x is not None]
    c = [r["flags"].get(fac) for r in neg]; c = [x for x in c if x is not None]
    if len(s) < 20 or len(c) < 20:
        return None
    ps = sum(bool(x) for x in s) / len(s); pc = sum(bool(x) for x in c) / len(c)
    return (ps / pc) if pc > 0 else float("inf")


def run(run_dir: Path, window: int) -> dict:
    pool, fp, sf_gen, min_dv = _load_pool(run_dir)
    by_ticker: dict[str, list] = {}
    for r in pool:
        by_ticker.setdefault(r["ticker"], []).append(r)
    resolved = []
    for t, rows in by_ticker.items():
        df = rr._hist_auto_adjust_false(t, "4y")
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        for r in rows:
            atr_pct, fwd_gain = _atr_pct_and_fwd(df, pd.Timestamp(r["t0"]).normalize(), window)
            if atr_pct is None:
                continue
            r["atr_move"] = fwd_gain / atr_pct  # forward move in ATR-units (runway-neutral)
            resolved.append(r)
    # Neutral surge = top-N ATR-moves, N = original surger count (same base rate, comparable).
    n_orig = sum(1 for r in resolved if r["orig_surge"])
    resolved.sort(key=lambda r: r["atr_move"], reverse=True)
    for i, r in enumerate(resolved):
        r["neutral_surge"] = i < n_orig
    k_threshold = resolved[n_orig - 1]["atr_move"] if 0 < n_orig <= len(resolved) else None
    out = {}
    for fac in FACTORS:
        out[fac] = {"orig_lift": _lift(resolved, fac, "orig_surge"),
                    "neutral_lift": _lift(resolved, fac, "neutral_surge")}
    return {"run_dir": str(run_dir), "window": window, "n_resolved": len(resolved),
            "n_surge": n_orig, "atr_move_threshold": k_threshold,
            # Provenance so knowledge_runway_sync can verify this runway result matches the
            # sibling factor_lift / cards before stamping a machine-readable verdict — events AND
            # features generation (Codex r8: a stale runway rebuilt from old features must fail).
            "source": {"events_generated_at": fp, "features_generated_at": sf_gen,
                       "min_dollar_vol": min_dv}, "lift": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?", default=str(REPO / "reports" / "retrospective"))
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--json", help="also persist the result dict to this path "
                                   "(so the runway-neutral verdicts are reproducible / syncable)")
    args = ap.parse_args()
    res = run(Path(args.run_dir), args.window)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"=== runway-NEUTRAL re-validation: {res['run_dir']} "
          f"(resolved={res['n_resolved']}, surge={res['n_surge']}, "
          f"neutral target = forward move ≥ {res['atr_move_threshold']:.1f} ATR) ===")
    print(f"\n{'factor':<22}{'%-target lift':>15}{'ATR-neutral lift':>18}")
    for fac, r in res["lift"].items():
        def f(x): return f"{x:.2f}" if isinstance(x, (int, float)) else "—"
        tag = "  (position)" if fac in POSITION else ""
        print(f"{fac:<22}{f(r['orig_lift']):>15}{f(r['neutral_lift']):>18}{tag}")
    print("\nA factor whose lift moves toward 1.0 under the ATR-neutral target was a %-runway\n"
          "artifact; one that holds its direction is a genuine, runway-independent signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
