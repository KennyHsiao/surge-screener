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


def validate_modules(modules: list[dict], factor_defs: dict) -> list[str]:
    """Return human-readable config problems (empty list = clean). Catches unknown
    factor keys (typos → a module that is silently always-None), duplicate module
    names (silent overwrite), and out-of-range min_factors."""
    known = set(factor_defs or {})
    problems, seen = [], set()
    for m in modules:
        name = m.get("name", "<unnamed>")
        if name in seen:
            problems.append(f"duplicate module name: {name!r}")
        seen.add(name)
        facs = m.get("factors") or {}
        if not facs:
            problems.append(f"{name}: has no factors")
        for fk in facs:
            if known and fk not in known:
                problems.append(f"{name}: unknown factor key {fk!r} (not in factor_defs)")
        mf = m.get("min_factors")
        if mf is not None and (not isinstance(mf, int) or mf < 1 or mf > len(facs)):
            problems.append(f"{name}: min_factors {mf!r} out of range [1, {len(facs)}]")
    return problems


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
    _events_fp = (feat.get("source") or {}).get("events_generated_at")
    # SYMMETRY (integration review S2): if retro_factor_lift filtered the control pool at a
    # $-volume floor, apply the IDENTICAL floor to the surgers here — else module lift pairs
    # UNfiltered surgers against a filtered control pool (biased up). The floor is recorded in
    # control_features.source.min_dollar_vol; surge_features carry avg_dollar_vol_20d.
    _min_dv = (cdata.get("source") or {}).get("min_dollar_vol") or 0.0
    if _min_dv and _min_dv > 0:
        surgers, _dropped = rfl._filter_by_liquidity(surgers, _min_dv)
        print(f"[modules] liquidity floor {_min_dv:,.0f} → dropped {_dropped} surgers "
              "(symmetric with the filtered control pool)", file=sys.stderr)
        if not surgers:
            print("[modules] liquidity filter dropped ALL surgers — nothing to score.",
                  file=sys.stderr)
            return 1
    src = cdata.get("source", {})
    # Full-chain provenance, GRACEFUL fail-closed (BLOCK, don't crash — matches retro_modules'
    # native design): the controls must share BOTH features_generated_at AND events_generated_at
    # with the surge_features, so a stale / cross-run control set blocks recommendations
    # (Codex + integration review). Missing events fingerprint ⇒ not provenance_ok ⇒ blocked.
    provenance_ok = (bool(src) and bool(_events_fp)
                     and src.get("features_generated_at") == feat.get("generated_at")
                     and src.get("events_generated_at") == _events_fp)
    modules = json.loads(Path(args.modules).read_text(encoding="utf-8"))["modules"]
    if not modules:
        print("[modules] no modules defined", file=sys.stderr)
        return 1

    # Validate the module config so a typo / dup / bad threshold doesn't SILENTLY make
    # a module always-None and skip it without warning. Known factors = the reconstructed
    # factor_defs (incl. EDGAR). Surface problems loudly + in the payload.
    config_warnings = validate_modules(modules, feat.get("factor_defs", {}))
    if config_warnings:
        print("[modules] CONFIG WARNINGS:\n  " + "\n  ".join(config_warnings), file=sys.stderr)

    # Inherit the SAME coverage gate as factor lift — module verdicts must not read
    # as validated when the underlying run is a non-representative / underpowered one.
    # FAIL CLOSED: a missing, unparseable, or mismatched lift file → block (we can't
    # confirm coverage, so we must not present module verdicts as actionable).
    lift_meta = {"coverage": {}, "recommendations_blocked": True}
    lift_ok = False
    lpath = Path(args.lift)
    try:
        lp = json.loads(lpath.read_text(encoding="utf-8"))
        lsrc = lp.get("source", {})
        if (lsrc.get("features_generated_at") == feat.get("generated_at")
                and lsrc.get("events_generated_at") == _events_fp):
            # Fail-closed predicate (same as retro_report): missing/inconsistent gate
            # metadata on a provenance-matched lift file still blocks.
            lift_meta = {"coverage": lp.get("coverage", {}),
                         "recommendations_blocked": rfl.is_recommendations_blocked(lp)}
            lift_ok = True
        else:
            print("[modules] WARNING: factor_lift.json provenance does not match this "
                  "surge_features run — blocking.", file=sys.stderr)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"[modules] WARNING: factor_lift.json missing/unreadable ({e}) — blocking.",
              file=sys.stderr)

    # Module match → synthetic boolean factor per row, fed through the lift engine.
    factor_defs = {
        m["name"]: {
            "dimension": "Module",
            "subfactor": (f"{m.get('min_factors', len(m['factors']))}/{len(m['factors'])} 因子"),
            "desc": m.get("description", ""),
        } for m in modules
    }

    rng = np.random.default_rng(rfl.SEED)
    thresholds = sorted({lab for r in surgers for lab in rfl._hits(r)})
    have_map = bool(controls_by_thr)
    fell_back: list = []   # labels that have a map overall but no entry of their OWN
    tables = {}
    for label in ["ALL", *thresholds]:
        sub = surgers if label == "ALL" else [r for r in surgers if label in rfl._hits(r)]
        surger_rows = [{"flags": _module_flags(r["flags"], modules)} for r in sub]
        # ALL uses the top-level `controls` (which IS the matched ALL baseline from
        # factor lift); only the per-threshold labels look up by_threshold and may
        # fall back. Track fallback PER LABEL so a partial map can't masquerade as
        # fully matched.
        if label == "ALL":
            cs, baseline = controls, "all"   # any-surge baseline (top-level controls)
        else:
            entry = controls_by_thr.get(label)
            if entry is not None:
                cs, baseline = entry["controls"], "threshold-specific"
            else:
                cs, baseline = controls, "all-fallback"
                if have_map:                   # map exists but is missing THIS label
                    fell_back.append(label)    # → stale/mismatched control file
        ctrl_rows = [{"flags": _module_flags(c["flags"], modules)} for c in cs]
        tables[label] = {
            "n_surge_events": len(sub),
            "n_controls": len(ctrl_rows),
            "control_baseline": baseline,
            "modules": rfl.compute_lift(surger_rows, ctrl_rows, factor_defs, rng),
        }

    if fell_back:
        print(f"[modules] WARNING: control_features.json has by_threshold but is "
              f"missing {fell_back}; those tables fell back to the ALL baseline. "
              f"Regenerate retro_factor_lift against THIS surge_features.json.",
              file=sys.stderr)
    if not provenance_ok:
        print("[modules] WARNING: control_features.json does not match this "
              "surge_features run (stale/mismatched controls). Blocking.", file=sys.stderr)
    # Honest aggregate: fully matched only when a map exists AND no label fell back.
    control_match = ("all-fallback" if not have_map
                     else "partial-fallback" if fell_back
                     else "threshold-specific")
    # FAIL CLOSED: any non-exact baseline OR stale controls blocks recommendations,
    # so a fallback/mismatched baseline can never read as valid threshold-specific
    # evidence (the lift may look fine but uses the wrong negatives).
    gate_blocked = (lift_meta.get("recommendations_blocked", False)
                    or not lift_ok
                    or control_match != "threshold-specific"
                    or not provenance_ok)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # Same-run fingerprint (Codex re-review): so a later consumer can verify this
        # module_lift was built from the SAME surge_events run as the factor_lift / cards it
        # is shown beside, and fail closed on a stale one — `provenance_ok` alone is not a
        # comparable fingerprint.
        "source": {
            "events_generated_at": _events_fp,
            "features_generated_at": feat.get("generated_at"),
            "min_dollar_vol": _min_dv,
        },
        "surger_count": len(surgers),
        "control_count": len(controls),
        # Which control baseline the per-threshold tables used: "threshold-specific"
        # matches factor lift exactly; "partial-fallback" = a map was present but
        # missing some labels (they reused ALL); "all-fallback" = no by_threshold map.
        "control_match": control_match,
        "provenance_ok": provenance_ok,
        "config_warnings": config_warnings,
        # Carry the factor-lift coverage gate so the UI gates module verdicts too.
        "coverage": lift_meta.get("coverage", {}),
        # Blocked by coverage OR non-exact baseline OR stale/mismatched controls.
        "recommendations_blocked": gate_blocked,
        "low_confidence": (len(surgers) < 30 or gate_blocked),
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
