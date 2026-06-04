#!/usr/bin/env python3
"""Runway-confound test for the surge retrospective — is the CONTRARIAN momentum / "oversold
reversal" finding a real edge, or a %-runway measurement artifact?

The retro labels a surge as "+X% gain from the trough" (seg.max()/base − 1 ≥ pct). That
target is mechanically easier for a beaten-down stock: a name 25% below its 52-week high
needs a small partial recovery to gain +30%, while a name near its high needs a fresh ATH.
The control is matched on firing the same +7% trigger but NOT on price-position — so a
"distance-below-anchor" factor can look CONTRARIAN purely because cheap stocks have more
%-runway to a fixed target, with no real predictive content.

This stratifies the SAME surgers/controls by price-position (within_25pct_of_high) and
recomputes each factor's lift inside each runway-matched stratum. A position/momentum factor
whose contrarian lift drifts toward ~1.0 (or flips) within strata was a runway artifact; a
factor that holds its lift across strata (notably rvol_ge_2) is a genuine, runway-independent
signal. Reads the committed surge_features.json + the local control_features.json.

CLI:
    python scripts/retro_confound_check.py                         # default sp1500 dir
    python scripts/retro_confound_check.py reports/retrospective/sp500_pit
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Factors split by whether they encode price-position (runway-suspect) or not.
POSITION_FACTORS = ["price_above_ma200", "price_above_ma50", "within_25pct_of_high",
                    "macd_positive", "rel_strength_vs_spy", "price_above_vwap",
                    "above_30pct_of_low"]
NEUTRAL_FACTORS = ["rvol_ge_2", "bb_squeeze", "rsi_40_65"]  # not pure distance-to-anchor


def _lift(S, C, fac):
    s = [f["flags"].get(fac) for f in S]; s = [x for x in s if x is not None]
    c = [f["flags"].get(fac) for f in C]; c = [x for x in c if x is not None]
    if len(s) < 20 or len(c) < 20:
        return None
    ps = sum(bool(x) for x in s) / len(s)
    pc = sum(bool(x) for x in c) / len(c)
    return (ps / pc) if pc > 0 else float("inf")


def run(run_dir: Path) -> dict:
    sf = json.loads((run_dir / "surge_features.json").read_text(encoding="utf-8"))
    cf = json.loads((run_dir / "control_features.json").read_text(encoding="utf-8"))
    surgers = sf["features"]
    controls = cf.get("controls") or cf["by_threshold"]["ALL"]["controls"]

    def strat(val):
        return ([f for f in surgers if f["flags"].get("within_25pct_of_high") is val],
                [f for f in controls if f["flags"].get("within_25pct_of_high") is val])

    Sfar, Cfar = strat(False)   # far from high (deep runway)
    Snear, Cnear = strat(True)  # near high (little runway)
    rows = {}
    for fac in POSITION_FACTORS + NEUTRAL_FACTORS:
        rows[fac] = {"overall": _lift(surgers, controls, fac),
                     "far_from_high": _lift(Sfar, Cfar, fac),
                     "near_high": _lift(Snear, Cnear, fac)}
    return {"run_dir": str(run_dir), "n_surgers": len(surgers),
            "n_controls": len(controls),
            "strata": {"far_from_high": [len(Sfar), len(Cfar)],
                       "near_high": [len(Snear), len(Cnear)]},
            "lift_by_stratum": rows}


def main() -> int:
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "reports" / "retrospective"
    res = run(rd)
    print(f"=== runway-confound check: {res['run_dir']} "
          f"(surgers={res['n_surgers']} controls={res['n_controls']}) ===")
    print(f"strata far/near = {res['strata']['far_from_high']} / {res['strata']['near_high']}")
    print(f"\n{'factor':<22}{'overall':>9}{'far-from-high':>15}{'near-high':>12}")
    for fac, r in res["lift_by_stratum"].items():
        def f(x): return f"{x:.2f}" if isinstance(x, (int, float)) else "—"
        tag = "" if fac in NEUTRAL_FACTORS else "  (position)"
        print(f"{fac:<22}{f(r['overall']):>9}{f(r['far_from_high']):>15}"
              f"{f(r['near_high']):>12}{tag}")
    print("\nReading: a POSITION factor whose lift moves toward 1.0 (or flips) within a "
          "runway-matched stratum\nwas a %-runway artifact; rvol_ge_2 holding its lift "
          "across strata is a genuine signal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
