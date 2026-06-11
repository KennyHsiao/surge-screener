#!/usr/bin/env python3
"""Forward validation for the 大盤行情研判 forecast (design v7 §1c, P2). Scores LOCKED predictions only.

Reads the dated forecast ledgers, resolves each prediction against the realized ^GSPC path via the frozen
`market_thesis_contract`, and reports — per the FULL key `(direction, bucket, support_class)` — the
hit-rate with a Wilson CI over **non-overlapping** matured forecasts. This is the ONLY number ever called
"accuracy"; until it matures every forecast stays labelled 探索性.

Anti-inflation (v7): the non-overlap walk, counted_N, Wilson and readiness ALL use the same full key; a
counted forecast in one direction can never drop an independent forecast in another; support classes
(analog_supported / event_only / regime_only) are separate denominators, never pooled; the event-driven and
regime-only ledgers are schema-separated and scored independently.

CLI:  python scripts/market_thesis_forward.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import market_thesis_contract as C        # noqa: E402 — frozen contract (classify/keys/constants)
import retro_factor_lift as rfl           # noqa: E402 — Wilson interval (shared)
import retro_reconstruct as rr            # noqa: E402 — cached OHLCV fetch

OUT_DIR = REPO / "reports" / "market_thesis"
LEDGERS = ("forecast_*.json", "regime_only_forecast_*.json")  # event-driven + degraded, scored separately


def gspc_close(period: str = "20y") -> pd.Series | None:
    df = rr._hist_auto_adjust_false(C.BENCHMARK, period)
    if df is None:
        return None
    # Do NOT dropna (Codex P2r2): stripping a mid-window NaN silently SHIFTS the H-session path and scores
    # a corrupted window as a normal hit/miss. NaNs stay visible so resolve_one/classify mark the affected
    # windows invalid (non_finite_path) instead.
    s = df["Close"]
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s


def resolve_one(rec: dict, gspc: pd.Series) -> dict:
    """Attach (t0_pos, matured, realized, hit) to a forecast via the frozen contract. PURE (gspc injected).
    FAIL-CLOSED (Codex P2r1): as_of must be EXACTLY a ^GSPC session — a weekend/holiday/edited date would
    otherwise silently map to the NEXT session's close (future information relative to the forecast).
    A non-finite path is surfaced as a data error, never scored as a resolved OTHER."""
    H = C.BUCKETS[rec["bucket"]]
    out = {**rec, "t0_pos": None, "matured": False, "realized": None, "hit": None, "invalid": None}
    pos = int(gspc.index.searchsorted(pd.Timestamp(rec["as_of"])))
    if pos >= len(gspc) or gspc.index[pos].date().isoformat() != rec["as_of"]:
        out["invalid"] = "as_of_not_a_session"
        return out
    out["t0_pos"] = pos
    if pos + H >= len(gspc):                                          # window hasn't fully elapsed
        return out
    path = gspc.to_numpy(float)[pos:pos + H + 1]
    try:
        realized = C.classify(path)
    except ValueError:
        out["invalid"] = "non_finite_path"                            # data failure, surfaced — not a miss
        return out
    out["matured"] = True
    out["realized"] = realized
    out["hit"] = bool(realized == rec["direction"])                  # OTHER / wrong-direction ⇒ miss
    return out


def _count_nonoverlap(recs: list[dict], H: int) -> list[dict]:
    """Greedy oldest→newest: count a forecast only if its t0_pos is ≥ H sessions after the previously COUNTED
    one. Tie-break = earliest as_of then lexical id. Per (direction,bucket,support_class) — caller groups."""
    ordered = sorted(recs, key=lambda r: (r["as_of"], str(r.get("id", "")), r["t0_pos"]))
    counted, last = [], None
    for r in ordered:
        if last is None or (r["t0_pos"] - last) >= H:
            counted.append(r); last = r["t0_pos"]
    return counted


def score(records: list[dict], gspc: pd.Series) -> dict:
    """Per-key hit-rate over NON-OVERLAPPING matured forecasts. PURE (gspc injected). Invalid records
    (non-session as_of, non-finite path) are EXCLUDED from scoring but REPORTED — never silent."""
    resolved = [resolve_one(r, gspc) for r in records]
    invalid = [{"as_of": r.get("as_of"), "id": r.get("id"), "reason": r["invalid"]}
               for r in resolved if r.get("invalid")]
    matured = [r for r in resolved if r["matured"]]
    keys = {C.forecast_key(r) for r in matured}
    by_key = {}
    for direction, bucket, sclass in sorted(keys):
        grp = [r for r in matured if C.forecast_key(r) == (direction, bucket, sclass)]
        counted = _count_nonoverlap(grp, C.BUCKETS[bucket])
        hits = sum(1 for r in counted if r["hit"])
        n = len(counted)
        lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)
        by_key[f"{direction}|{bucket}|{sclass}"] = {
            "direction": direction, "bucket": bucket, "support_class": sclass,
            "raw_N": len(grp), "counted_N": n, "hits": hits,
            "hit_rate": round(hits / n, 4) if n else None, "wilson90": [round(lo, 4), round(hi, 4)],
            "verdict": "MATURE" if n >= C.MIN_RESOLVED else "PROVISIONAL"}
    return {"resolved": len(resolved), "matured": len(matured),
            "invalid_records": invalid, "invalid_count": len(invalid),
            "min_resolved_for_verdict": C.MIN_RESOLVED, "by_key": by_key}


# Per-family ledger invariants (Codex P2r1): an edited degraded record must NOT be able to enter the
# event-driven namespace. Families are schema-separated and the loader enforces it, not just the writer.
LEDGER_RULES = {
    "forecast_": {"manifest_status": ("ready",),
                  "support_class": ("analog_supported", "event_only")},
    "regime_only_forecast_": {"manifest_status": ("degraded",),
                              "support_class": ("regime_only",)},
}


def validate_ledger_record(rec: dict, fname: str) -> list[str]:
    """Contract + family invariants for one ledger file. Empty list == valid."""
    errs = list(C.validate_forecast(rec))
    family = "regime_only_forecast_" if fname.startswith("regime_only_forecast_") else "forecast_"
    rules = LEDGER_RULES[family]
    if rec.get("manifest_status") not in rules["manifest_status"]:
        errs.append(f"manifest_status {rec.get('manifest_status')!r} invalid for {family}* ledger")
    if rec.get("support_class") not in rules["support_class"]:
        errs.append(f"support_class {rec.get('support_class')!r} invalid for {family}* ledger")
    if rec.get("benchmark") != C.BENCHMARK:
        errs.append(f"benchmark {rec.get('benchmark')!r} != {C.BENCHMARK}")
    expected_as_of = fname[len(family):-len(".json")]
    if rec.get("as_of") != expected_as_of:
        errs.append(f"as_of {rec.get('as_of')!r} != filename date {expected_as_of!r}")
    return errs


def _load_ledgers() -> list[dict]:
    """FAIL-CLOSED loader: a record only enters scoring if it passes contract + family invariants, is the
    single record in its file, and is the only record for its (family, as_of). Rejects are loud."""
    recs: list[dict] = []
    seen: set[tuple] = set()
    for pat in LEDGERS:
        for f in sorted(OUT_DIR.glob(pat)):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print(f"[mkt-fwd] REJECT {f.name}: unreadable ({e})", file=sys.stderr)
                continue
            items = d if isinstance(d, list) else [d]
            if len(items) != 1:
                print(f"[mkt-fwd] REJECT {f.name}: {len(items)} records (one primary per as_of)",
                      file=sys.stderr)
                continue
            rec = items[0]
            errs = validate_ledger_record(rec, f.name)
            family = "regime_only_forecast_" if f.name.startswith("regime_only_forecast_") else "forecast_"
            key = (family, rec.get("as_of"))
            if key in seen:
                errs.append("duplicate (family, as_of)")
            if errs:
                print(f"[mkt-fwd] REJECT {f.name}: {errs}", file=sys.stderr)
                continue
            seen.add(key)
            rec["id"] = f.name                       # stable unique id (tie-break in the non-overlap walk)
            recs.append(rec)
    return recs


def main() -> int:
    records = _load_ledgers()
    gspc = gspc_close()
    if gspc is None:
        print("[mkt-fwd] no ^GSPC history fetched", file=sys.stderr)
        return 1
    summ = score(records, gspc)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "benchmark": C.BENCHMARK, "theta_dir": C.THETA_DIR, "buckets": C.BUCKETS,
               "note": "Hit-rate over NON-OVERLAPPING matured, locked forecasts; keyed on the full "
                       "(direction,bucket,support_class). PROVISIONAL until counted_N≥MIN_RESOLVED. "
                       "探索性,未驗證,非投資建議.",
               **summ}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")
    print(f"[mkt-fwd] {summ['resolved']} forecasts, {summ['matured']} matured → {len(summ['by_key'])} keys")
    for k, v in summ["by_key"].items():
        print(f"  {k}: {v['hits']}/{v['counted_N']} (raw {v['raw_N']}) rate {v['hit_rate']} "
              f"CI {v['wilson90']} [{v['verdict']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
