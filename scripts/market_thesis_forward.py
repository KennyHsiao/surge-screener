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

import market_events as ME                # noqa: E402 — NYSE session calendar (lock bounds + gaps)
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
    try:  # defence in depth for direct score() callers — the loader already rejects non-canonical dates
        asof_ts = pd.Timestamp(rec["as_of"])
    except Exception:  # noqa: BLE001
        out["invalid"] = "unparsable_as_of"
        return out
    pos = int(gspc.index.searchsorted(asof_ts))
    if pos >= len(gspc) or gspc.index[pos].date().isoformat() != rec["as_of"]:
        out["invalid"] = "as_of_not_a_session"
        return out
    out["t0_pos"] = pos
    if pos + H >= len(gspc):                                          # window hasn't fully elapsed
        return out
    # SESSION-COMPLETENESS (Codex P2r9): a provider/cache gap that DROPS a trading date (no NaN row left
    # behind) would silently shift the window endpoint later — t0+H must be H REAL NYSE sessions after t0.
    # Verify the slice's index matches the expected NYSE session sequence; a gap (incl. an unlisted special
    # closure) marks the window invalid, never a shifted hit/miss.
    seg_idx = gspc.index[pos:pos + H + 1]
    expected = pd.date_range(start=seg_idx[0], periods=H + 1, freq=ME.nyse_cbd())
    if not seg_idx.equals(expected):
        out["invalid"] = "benchmark_session_gap"
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
    if not (gspc.index.is_monotonic_increasing and gspc.index.is_unique):
        # a corrupt benchmark index (duplicate/unsorted sessions) taints EVERYTHING — no window is trustable
        resolved = [{**r, "t0_pos": None, "matured": False, "realized": None, "hit": None,
                     "invalid": "benchmark_index_corrupt"} for r in records]
    else:
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
    # strict canonical YYYY-MM-DD (Codex P2r7): 'not-a-date' matched its own filename suffix, passed here,
    # then crashed pd.Timestamp in the scorer BEFORE the tainted summary could be persisted.
    try:
        canonical = pd.Timestamp(rec.get("as_of")).strftime("%Y-%m-%d") == rec.get("as_of")
    except Exception:  # noqa: BLE001
        canonical = False
    if not canonical:
        errs.append(f"as_of {rec.get('as_of')!r} is not a canonical YYYY-MM-DD date")
        return errs
    # LOCK-TIME proof (Codex P2r8): t0 = the as_of session CLOSE, so a forecast generated BEFORE that close
    # could exploit intraday information (or be backfilled) and still be scored against the final close.
    # generated_at must be timezone-aware and ≥ the NYSE close (16:00 America/New_York, DST-correct).
    gen = rec.get("generated_at")
    if not gen:
        errs.append("missing generated_at (lock-time proof required)")
        return errs
    try:
        gen_ts = pd.Timestamp(gen)
        if gen_ts.tzinfo is None:
            errs.append("generated_at must be timezone-aware (UTC)")
            return errs
        close_utc = pd.Timestamp(f"{rec['as_of']} 16:00", tz="America/New_York").tz_convert("UTC")
        if gen_ts.tz_convert("UTC") < close_utc:
            errs.append(f"generated_before_close: {gen} < {close_utc.isoformat()} (ex-ante t0 contract)")
        else:
            # UPPER bound (stop-gate): a forecast generated at/after the NEXT session's open had access to
            # post-t0 trading information — a late backfill with hindsight must never enter the ledger.
            nxt_open = ME.next_session_open_utc(rec["as_of"])
            if gen_ts.tz_convert("UTC") >= nxt_open:
                errs.append(f"late_backfilled: {gen} >= next session open {nxt_open.isoformat()}")
    except Exception:  # noqa: BLE001
        errs.append(f"unparsable generated_at {gen!r}")
    return errs


def _github_runs_in_window(repo_slug: str, start_iso: str, end_iso: str) -> list[dict]:
    """GitHub Actions runs created in [start, end] — SERVER-side created_at, not forgeable locally.
    Retains head_branch/event so the caller can restrict to TRUSTED runs (Codex P2r14).
    Separated for testability (monkeypatched in offline tests)."""
    import subprocess
    out = subprocess.run(
        ["gh", "api", f"/repos/{repo_slug}/actions/runs?created={start_iso}..{end_iso}&per_page=100",
         "--jq", "[.workflow_runs[] | {id, head_sha, created_at, head_branch, event}]"],
        capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh api runs failed")
    return json.loads(out.stdout or "[]")


def _github_blob_at(repo_slug: str, rel: str, ref: str) -> str | None:
    """The blob sha of `rel` in the tree of `ref` per the GitHub API (None if absent there)."""
    import subprocess
    out = subprocess.run(["gh", "api", f"/repos/{repo_slug}/contents/{rel}?ref={ref}", "--jq", ".sha"],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def _git_lock_error(path: Path, as_of: str, now: pd.Timestamp, repo: Path = REPO,
                    repo_slug: str | None = None) -> str | None:
    """EXTERNAL immutability proof (Codex P2r12+r13). Local git metadata (committer dates) is FORGEABLE
    (GIT_COMMITTER_DATE), so the time anchor is GitHub's SERVER-side record instead: once the lock window
    [as_of close, next session open) has closed, there must exist a GitHub Actions run whose created_at
    (recorded by GitHub, not the committer) falls inside that window AND whose head tree already contains
    this ledger at EXACTLY the current blob. Scheduled runs (crypto 00:30 UTC daily, verify_returns 13:00
    UTC weekdays — both pre-open) attest every evening's ledgers in normal operation. Forging this proof
    requires forging GitHub's run records. While the window is open the check is waived (nothing post-t0 is
    knowable; the same-evening CI commit + later runs provide the attestation). Any API/git failure fails
    CLOSED. CI must pass GH_TOKEN; checkout fetch-depth:0 is no longer load-bearing but stays for context."""
    import subprocess
    nxt = ME.next_session_open_utc(as_of)
    if now.tz_convert("UTC") < nxt:
        return None                                   # lock window still open — no proof required yet
    rel = str(path.relative_to(repo))
    try:
        blob_now = subprocess.run(["git", "hash-object", rel],
                                  capture_output=True, text=True, cwd=repo, timeout=30).stdout.strip()
        if not blob_now:
            return "lock_unverifiable: cannot hash working blob"
        if repo_slug is None:
            url = subprocess.run(["git", "remote", "get-url", "origin"],
                                 capture_output=True, text=True, cwd=repo, timeout=30).stdout.strip()
            repo_slug = url.split("github.com/")[-1].removesuffix(".git").strip("/")
            if "/" not in repo_slug:
                return "lock_unverifiable: cannot derive repo slug"
        close_utc = pd.Timestamp(f"{as_of} 16:00", tz="America/New_York").tz_convert("UTC")
        runs = _github_runs_in_window(repo_slug,
                                      close_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                      (nxt - pd.Timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        # TRUSTED attesters only (Codex P2r14): timer-driven SCHEDULE runs on the DEFAULT branch. A
        # workflow_dispatch or side-branch run could pre-attest multiple alternate blobs to cherry-pick later.
        trusted = [r for r in runs if r.get("event") == "schedule" and r.get("head_branch") == "main"]
        attested: set[str] = set()
        for run in sorted(trusted, key=lambda r: r.get("created_at", "")):
            b = _github_blob_at(repo_slug, rel, run.get("head_sha", ""))
            if b:
                attested.add(b)
        # UNIQUENESS: every trusted in-window attestation of this path must equal the CURRENT blob — two
        # different attested blobs means alternate ledgers coexisted inside the lock window (ambiguous,
        # cherry-pickable after outcomes), so the whole claim is rejected, not just the mismatch.
        if attested == {blob_now}:
            return None
        if len(attested) > 1:
            return "lock_ambiguous_multiple_attested_blobs"
        return "lock_not_proven_no_attesting_run"
    except Exception as e:  # noqa: BLE001 — a broken git/API environment must fail CLOSED, never skip
        return f"lock_unverifiable: {e}"


def _load_ledgers() -> tuple[list[dict], list[dict]]:
    """FAIL-CLOSED loader → (accepted, rejected). A record only enters scoring if it passes contract +
    family invariants, is the single record in its file, and is the only record for its (family, as_of).
    Rejects are RETURNED (persisted into the summary by main — a corrupted/edited losing ledger must never
    silently vanish from the official denominator; stderr alone is ephemeral, Codex P2r5)."""
    recs: list[dict] = []
    rejects: list[dict] = []
    seen: set[tuple] = set()
    for pat in LEDGERS:
        for f in sorted(OUT_DIR.glob(pat)):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                rejects.append({"file": f.name, "errors": [f"unreadable: {e}"]})
                continue
            items = d if isinstance(d, list) else [d]
            if len(items) != 1:
                rejects.append({"file": f.name, "errors": [f"{len(items)} records (one primary per as_of)"]})
                continue
            rec = items[0]
            if not isinstance(rec, dict):
                # a null/scalar payload must become a PERSISTED reject, not an AttributeError that leaves the
                # previous summary as the last visible artifact (Codex P2r6)
                rejects.append({"file": f.name, "errors": ["record_not_object"]})
                continue
            errs = validate_ledger_record(rec, f.name)
            if not errs:                                 # schema-valid → require the EXTERNAL git lock proof
                lock_err = _git_lock_error(f, rec["as_of"], pd.Timestamp.now(tz="UTC"))
                if lock_err:
                    errs.append(lock_err)
            family = "regime_only_forecast_" if f.name.startswith("regime_only_forecast_") else "forecast_"
            key = (family, rec.get("as_of"))
            if key in seen:
                errs.append("duplicate (family, as_of)")
            if errs:
                rejects.append({"file": f.name, "errors": errs})
                continue
            seen.add(key)
            rec["id"] = f.name                       # stable unique id (tie-break in the non-overlap walk)
            recs.append(rec)
    for r in rejects:
        print(f"[mkt-fwd] REJECT {r['file']}: {r['errors']}", file=sys.stderr)
    return recs, rejects


def main() -> int:
    records, rejects = _load_ledgers()
    gspc = gspc_close()
    if gspc is None:
        print("[mkt-fwd] no ^GSPC history fetched", file=sys.stderr)
        return 1
    summ = score(records, gspc)
    # ANY taint fails publishability (Codex P2r6): loader rejects AND invalid accepted records (non-session
    # as_of, non-finite benchmark window) both shrink the denominator — neither may hide behind status=ok.
    if rejects:
        status = "non_publishable_ledger_rejects"
    elif summ["invalid_count"]:
        status = "non_publishable_invalid_records"
    else:
        status = "ok"
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "benchmark": C.BENCHMARK, "theta_dir": C.THETA_DIR, "buckets": C.BUCKETS,
               "validation_status": status,
               "reject_count": len(rejects), "rejected_ledgers": rejects,
               "note": "Hit-rate over NON-OVERLAPPING matured, locked forecasts; keyed on the full "
                       "(direction,bucket,support_class). PROVISIONAL until counted_N≥MIN_RESOLVED. "
                       "探索性,未驗證,非投資建議.",
               **summ}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")
    print(f"[mkt-fwd] {summ['resolved']} forecasts, {summ['matured']} matured → {len(summ['by_key'])} keys"
          f" | rejects={len(rejects)} invalid={summ['invalid_count']} status={status}")
    for k, v in summ["by_key"].items():
        print(f"  {k}: {v['hits']}/{v['counted_N']} (raw {v['raw_N']}) rate {v['hit_rate']} "
              f"CI {v['wilson90']} [{v['verdict']}]")
    return 0 if status == "ok" else 1   # ANY taint fails the job — no clean-looking summary


if __name__ == "__main__":
    raise SystemExit(main())
