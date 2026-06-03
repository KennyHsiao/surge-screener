#!/usr/bin/env python3
"""Surge Retrospective — module (factor-combination) validation.

The single-factor lift (retro_factor_lift) answers "does factor X precede surges?".
This answers the next question you actually trade on: "does this COMBINATION of
factors — a named trader archetype like 延續型 / 超賣反轉 / 帶量突破 — precede
surges?". Each module from config/retro_modules.json becomes a synthetic boolean
factor (the event matches the module or not) and is fed through the SAME lift
engine (retro_factor_lift.compute_lift), so module lift / bootstrap CI / verdicts
are computed identically to single factors — no second statistics path.

Match is the same tri-state the rest of the pipeline uses, so missing factor data
never fakes a match:
    satisfied ≥ min_factors                         → True  (matches)
    satisfied < min_factors but satisfied+unknown ≥  → None  (insufficient — skipped)
    otherwise                                        → False (doesn't match)
min_factors defaults to "all conditions" (hard conjunction); set it in the config
to make a module soft (e.g. 3-of-4).

Reuses the control set persisted by retro_factor_lift (control_features.json) so it
re-runs instantly without re-fetching SPY/VIX/EDGAR.

CLI:
    python scripts/retro_modules.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

import retro_factor_lift as rfl  # noqa: E402 — reuse the lift engine


def module_match(flags: dict, module: dict):
    """Tri-state: does a row's factor flags match this module? (True/False/None)."""
    conds = module["factors"]
    min_f = module.get("min_factors", len(conds))
    satisfied = unknown = 0
    for fk, want in conds.items():
        v = flags.get(fk)
        if v is None:
            unknown += 1
        elif bool(v) == bool(want):
            satisfied += 1
    if satisfied >= min_f:
        return True
    if satisfied + unknown >= min_f:
        return None  # unresolved — unknowns could push it over the threshold
    return False


def _factor_breakdown(surgers: list[dict], module: dict) -> list[dict]:
    """Per-condition presence rate among surgers — shows which factor gates a module."""
    out = []
    for fk, want in module["factors"].items():
        vals = [r["flags"].get(fk) for r in surgers if r["flags"].get(fk) is not None]
        hit = sum(1 for v in vals if bool(v) == bool(want))
        out.append({
            "factor": fk,
            "want": want,
            "p_surge_meets": round(hit / len(vals), 3) if vals else None,
            "n_known": len(vals),
        })
    return out


def _module_flags(row_flags: dict, modules: list[dict]) -> dict:
    return {m["name"]: module_match(row_flags, m) for m in modules}


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — module validation")
    ap.add_argument("--features", default=str(OUT_DIR / "surge_features.json"))
    ap.add_argument("--controls", default=str(OUT_DIR / "control_features.json"))
    ap.add_argument("--lift", default=str(OUT_DIR / "factor_lift.json"))
    ap.add_argument("--modules", default=str(REPO / "config" / "retro_modules.json"))
    ap.add_argument("--output", default=str(OUT_DIR / "module_lift.json"))
    args = ap.parse_args()

    feat = json.loads(Path(args.features).read_text(encoding="utf-8"))
    surgers = feat["features"]
    if not surgers:
        print("[modules] no surge features", file=sys.stderr)
        return 1
    cpath = Path(args.controls)
    if not cpath.exists():
        print(f"[modules] {cpath} missing — run retro_factor_lift first "
              f"(it persists the control set).", file=sys.stderr)
        return 1
    cdata = json.loads(cpath.read_text(encoding="utf-8"))
    controls = cdata["controls"]                      # ALL set (fallback / back-compat)
    controls_by_thr = cdata.get("by_threshold", {})   # per-threshold sets (match factor lift)
    modules = json.loads(Path(args.modules).read_text(encoding="utf-8"))["modules"]
    if not modules:
        print("[modules] no modules defined", file=sys.stderr)
        return 1

    # Inherit the SAME coverage gate as factor lift — module verdicts must not read
    # as validated when the underlying run is a non-representative sample experiment.
    lift_meta = {}
    lpath = Path(args.lift)
    if lpath.exists():
        lp = json.loads(lpath.read_text(encoding="utf-8"))
        lift_meta = {"coverage": lp.get("coverage", {}),
                     "recommendations_blocked": lp.get("recommendations_blocked", False)}

    # Module match → synthetic boolean factor per row, fed through the lift engine.
    factor_defs = {
        m["name"]: {
            "dimension": "Module",
            "subfactor": (f"{m.get('min_factors', len(m['factors']))}/{len(m['factors'])} 因子"),
            "desc": m.get("description", ""),
        } for m in modules
    }

    def _ctrl_rows(label: str) -> list:
        """Controls for one threshold — the SAME set factor lift used, falling back
        to the ALL set if an older control_features.json lacks by_threshold."""
        entry = controls_by_thr.get(label)
        cs = entry["controls"] if entry else controls
        return [{"flags": _module_flags(c["flags"], modules)} for c in cs]

    rng = np.random.default_rng(rfl.SEED)
    thresholds = sorted({lab for r in surgers for lab in rfl._hits(r)})
    # True only when factor lift supplied per-threshold controls; otherwise every
    # threshold table reuses the ALL baseline and we say so in the metadata.
    threshold_matched_controls = bool(controls_by_thr)
    tables = {}
    for label in ["ALL", *thresholds]:
        sub = surgers if label == "ALL" else [r for r in surgers if label in rfl._hits(r)]
        surger_rows = [{"flags": _module_flags(r["flags"], modules)} for r in sub]
        ctrl_rows = _ctrl_rows(label)
        tables[label] = {
            "n_surge_events": len(sub),
            "n_controls": len(ctrl_rows),
            "modules": rfl.compute_lift(surger_rows, ctrl_rows, factor_defs, rng),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "surger_count": len(surgers),
        "control_count": len(controls),
        # Which control baseline the per-threshold tables used: "threshold-specific"
        # matches factor lift exactly; "all-fallback" means an older control file
        # without by_threshold, so every threshold reused the ALL baseline.
        "control_match": "threshold-specific" if threshold_matched_controls else "all-fallback",
        # Carry the factor-lift coverage gate so the UI gates module verdicts too.
        "coverage": lift_meta.get("coverage", {}),
        "recommendations_blocked": lift_meta.get("recommendations_blocked", False),
        "low_confidence": (len(surgers) < 30
                           or lift_meta.get("recommendations_blocked", False)),
        "thresholds": thresholds,
        "modules": [{
            "name": m["name"],
            "description": m.get("description", ""),
            "min_factors": m.get("min_factors", len(m["factors"])),
            "factor_count": len(m["factors"]),
            "factors_detail": _factor_breakdown(surgers, m),
        } for m in modules],
        "method": "Each module = a synthetic boolean factor (tri-state match); lift "
                  "vs the shared control group via retro_factor_lift.compute_lift.",
        "tables": tables,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[modules] {len(modules)} modules × {len(tables)} tables → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
