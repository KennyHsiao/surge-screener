#!/usr/bin/env python3
"""Runway-NEUTRAL check for COMBINED signals (not just single factors).

retro_runway_neutral_check.py shows which SINGLE factors survive an ATR-normalized
surge target. This extends it to the COMBINED predicates a lane actually trades —
so we can ask "does the volume-ignition lane's full rule (oversold position + rvol)
keep its edge once the %-runway advantage of cheap stocks is removed?".

Reuses retro_runway_neutral_check's pool + ATR-move labeling. Read-only; optional
--json persists the comparison. CLI:
    python scripts/lane_runway_check.py [reports/retrospective/sp500_pit] [--window 60] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import retro_runway_neutral_check as rnc  # pool loader + ATR fwd-gain + OHLCV cache

REPO = Path(__file__).resolve().parent.parent

# Combined signals to test. Each is a list of (flag_key, want_bool); the predicate is
# the AND of all of them, tri-state aware (any required flag None → row skipped).
SIGNALS = {
    "rvol_ge_2 (alone)":            [("rvol_ge_2", True)],
    "bb_squeeze (alone)":           [("bb_squeeze", True)],
    "LANE: !ma200 & !25%high & rvol": [("price_above_ma200", False),
                                       ("within_25pct_of_high", False), ("rvol_ge_2", True)],
    "oversold position only":       [("price_above_ma200", False), ("within_25pct_of_high", False)],
    "rvol & bb_squeeze":            [("rvol_ge_2", True), ("bb_squeeze", True)],
    "bb_squeeze & rsi_40_65":       [("bb_squeeze", True), ("rsi_40_65", True)],
    "rvol & !ma200":                [("price_above_ma200", False), ("rvol_ge_2", True)],
}


def _pred(spec):
    def p(flags):
        for k, want in spec:
            v = flags.get(k)
            if v is None:
                return None          # unknown component → unknown combined (skip)
            if bool(v) != want:
                return False
        return True
    return p


def _label_pool(run_dir: Path, window: int):
    pool = rnc._load_pool(run_dir)
    by: dict = {}
    for r in pool:
        by.setdefault(r["ticker"], []).append(r)
    resolved = []
    for t, rows in by.items():
        df = rnc.rr._hist_auto_adjust_false(t, "4y")
        if df is None:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        for r in rows:
            atr_pct, fwd = rnc._atr_pct_and_fwd(df, pd.Timestamp(r["t0"]).normalize(), window)
            if atr_pct is None:
                continue
            r["atr_move"] = fwd / atr_pct
            resolved.append(r)
    n = sum(1 for r in resolved if r["orig_surge"])
    resolved.sort(key=lambda r: r["atr_move"], reverse=True)
    for i, r in enumerate(resolved):
        r["neutral_surge"] = i < n
    return resolved, n


def _lift(rows, pred, label_key):
    def rate(group):
        v = [pred(r["flags"]) for r in group]
        v = [x for x in v if x is not None]
        if not v:
            return None, 0, 0
        t = sum(bool(x) for x in v)
        return t / len(v), len(v), t
    pos = [r for r in rows if r[label_key]]
    neg = [r for r in rows if not r[label_key]]
    ps, ns, ts = rate(pos)
    pc, nc, _ = rate(neg)
    if ps is None or pc in (None, 0) or ns < 20 or nc < 20:
        return None, ts
    return ps / pc, ts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?", default=str(REPO / "reports" / "retrospective" / "sp500_pit"))
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--json")
    args = ap.parse_args()

    resolved, n = _label_pool(Path(args.run_dir), args.window)
    thr = resolved[n - 1]["atr_move"] if 0 < n <= len(resolved) else None
    out = {}
    for name, spec in SIGNALS.items():
        pred = _pred(spec)
        ol, ts = _lift(resolved, pred, "orig_surge")
        nl, _ = _lift(resolved, pred, "neutral_surge")
        out[name] = {"pct_lift": ol, "atr_neutral_lift": nl, "support": ts}

    res = {"run_dir": str(args.run_dir), "window": args.window, "resolved": len(resolved),
           "n_surge": n, "atr_move_threshold": thr, "signals": out}
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"resolved={len(resolved)} surge={n} (ATR target ≥ {thr:.1f} ATR)\n")
    print(f"{'signal':<40}{'%-lift':>8}{'ATR-lift':>10}{'support':>9}")
    for name, r in out.items():
        f = lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else "—"
        print(f"{name:<40}{f(r['pct_lift']):>8}{f(r['atr_neutral_lift']):>10}{r['support']:>9}")
    print("\nA signal whose ATR-lift stays >1 with real support is runway-independent and "
          "tradeable; one that collapses to ≤1 was a %-runway artifact regardless of its %-lift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
