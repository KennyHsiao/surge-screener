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
import os
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


def _last_known_session(now: pd.Timestamp) -> pd.Timestamp:
    """The last NYSE session whose 16:00-ET close is in the PAST relative to `now` (Codex P2r20). Today's
    session does not count until its close has passed, so an intraday run never falsely demands today's bar."""
    et = now.tz_convert("America/New_York")
    ref = et.normalize()
    if et < ref.replace(hour=16, minute=0):       # before today's close → today's bar not knowable yet
        ref = ref - ME.nyse_cbd()
    return ME.last_completed_session(ref.date().isoformat())


def resolve_one(rec: dict, gspc: pd.Series, now: pd.Timestamp | None = None) -> dict:
    """Attach (t0_pos, matured, realized, hit) to a forecast via the frozen contract. PURE (gspc + now
    injected). FAIL-CLOSED (Codex P2r1): as_of must be EXACTLY a ^GSPC session — a weekend/holiday/edited
    date would otherwise silently map to the NEXT session's close (future information relative to the
    forecast). A non-finite path is surfaced as a data error, never scored as a resolved OTHER."""
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
    if pos + H >= len(gspc):                                          # window not present in the series
        # STALE-TAIL guard (Codex P2r20): "not in series" is only legitimately not-yet-matured if the
        # H-session horizon genuinely hasn't elapsed. If the expected endpoint session is on/before the
        # last session whose close is already known, the bar SHOULD exist — its absence means a stale or
        # truncated benchmark fetch, and silently leaving it matured:false would stall forward
        # accumulation behind a green summary. Mark it invalid (fail-closed), never a quiet skip.
        if now is not None:
            endpoint = asof_ts + H * ME.nyse_cbd()
            if endpoint <= _last_known_session(now):
                out["invalid"] = "benchmark_stale_or_truncated"
        return out
    # NOT-YET-CLOSED endpoint — maturity oracle must be SYMMETRIC (Codex sweep): the stale-tail guard above
    # only fires when the endpoint bar is ABSENT, but the endpoint bar can be PRESENT in the fetched series
    # yet belong to a session whose 16:00-ET close has NOT occurred relative to `now` — yfinance returns a
    # PARTIAL in-progress bar for the current session, so maturing here would score against a non-final,
    # cache-frozen intraday Close (look-ahead AND non-reproducible). Withhold until the endpoint close has
    # passed (matured=False, NOT invalid — it matures cleanly on the next run once the bar is final).
    if now is not None and (asof_ts + H * ME.nyse_cbd()) > _last_known_session(now):
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


def score(records: list[dict], gspc: pd.Series, now: pd.Timestamp | None = None) -> dict:
    """Per-key hit-rate over NON-OVERLAPPING matured forecasts. PURE (gspc + now injected). Invalid records
    (non-session as_of, non-finite path, stale/truncated benchmark tail) are EXCLUDED from scoring but
    REPORTED — never silent. `now` is the run clock used for the stale-tail maturity guard."""
    if now is None:
        now = pd.Timestamp.now(tz="UTC")
    if not (gspc.index.is_monotonic_increasing and gspc.index.is_unique):
        # a corrupt benchmark index (duplicate/unsorted sessions) taints EVERYTHING — no window is trustable
        resolved = [{**r, "t0_pos": None, "matured": False, "realized": None, "hit": None,
                     "invalid": "benchmark_index_corrupt"} for r in records]
    else:
        resolved = [resolve_one(r, gspc, now) for r in records]
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
    # GATE the entire READY (forecast_*) family (Codex P2r27 [high] analog + P2r29 [high] macro): the offline
    # validator cannot independently re-verify the live, un-committed evidence a ready ledger rests on —
    #   • the analog block comes from a LIVE-fetched, gitignored regime corpus (no deterministic recompute);
    #   • the macro manifest rows (FRED CPI/JOBS, YF UST10Y/DXY) are LIVE-fetched point-in-time data, and
    #     ME.evaluate_event over the PERSISTED row only re-checks field-shape/freshness, NOT that the values
    #     match the real source — so a forged-but-coherent allowlisted-looking row passes.
    # The self-consistency / provenance-row checks below therefore CANNOT prove a ready ledger was produced
    # by the deterministic writer from real sources. Tier-1 is degraded→regime_only until FRED is wired, so
    # NO forecast_* ledger can be produced today (none was ever committed). We FAIL CLOSED on the whole
    # ready family — it neither scores nor notifies — until a SOURCE-BACKED manifest+analog recompute is
    # built (to land together with wiring FRED). This enforces the design's "non-alerting until FRED" at the
    # validator. NOTE: appended (not early-return) so the structural/provenance/lock checks below still run
    # and stay under test; for matured records the git-lock already proves writer provenance independently.
    if family == "forecast_":
        errs.append("ready_family_gated: live macro/analog evidence not independently verifiable in the "
                    "offline validator; forecast_* is fail-closed (non-scoring, non-notifying) until a "
                    "source-backed recompute lands with FRED wiring")
    # RECOMPUTE the support-class SEMANTICS from persisted evidence (Codex P2r26): the writer fix (r24/r25)
    # alone does not protect the LOCKED scoring ledger — a legacy or hand-edited record could claim a class
    # its evidence doesn't support (e.g. a degraded rally stored as 盤整 when the regime mapping owns 看多,
    # contaminating the 盤整|regime_only denominator). Re-run the WRITER's own decide() over the persisted
    # (regime, rationale.analog, manifest_status) — the single source of truth — and require the stored
    # (direction, support_class) to match EXACTLY, else reject before scoring. This subsumes the r24
    # namespace-purity and r25 usable-analog predicates because it IS the same function.
    try:
        import market_thesis as MT
        exp_dir, exp_bkt, exp_sclass = MT.decide(
            rec.get("regime"), (rec.get("rationale") or {}).get("analog"), rec.get("manifest_status"))
    except Exception as e:  # noqa: BLE001 — an unrecomputable record is unverifiable ⇒ reject (fail-closed)
        errs.append(f"support_semantics_unrecomputable: {e}")
    else:
        if rec.get("support_class") != exp_sclass:
            errs.append(f"support_class {rec.get('support_class')!r} != recomputed {exp_sclass!r} "
                        f"(regime={rec.get('regime')!r}, manifest={rec.get('manifest_status')!r})")
        if rec.get("direction") != exp_dir:
            errs.append(f"direction {rec.get('direction')!r} != recomputed {exp_dir!r} "
                        f"(regime={rec.get('regime')!r}, class={exp_sclass!r})")
        # the bucket is part of the LOCKED writer output and the full scoring key (Codex P2r27): the baseline
        # only ever emits PRIMARY_BUCKET, so a forged short/long bucket — which validate_forecast accepts as a
        # valid contract value — would score under a different horizon key the writer never produced.
        if rec.get("bucket") != exp_bkt:
            errs.append(f"bucket {rec.get('bucket')!r} != recomputed {exp_bkt!r} (writer-owned bucket)")
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
    # EVENT PROVENANCE (Codex P2r19): a READY-family ledger must carry the full manifest evidence rows that
    # justify its readiness — every required event present+fresh with its allowlisted source_id — else the
    # ready claim is unauditable and the record is rejected before scoring or notification.
    if family == "forecast_":
        events = (rec.get("rationale") or {}).get("manifest_events")
        # only dict elements can carry a 'type'/source row — a non-dict element (e.g. a bare scalar) must be
        # skipped, not crash the comprehension on .get (Codex sweep); a missing required type then surfaces
        # as the normal 'missing manifest provenance' reject below.
        by_type = ({e.get("type"): e for e in events if isinstance(e, dict)}
                   if isinstance(events, list) else {})
        for etype in ME.REQUIRED:
            ev = by_type.get(etype)
            if not ev:
                errs.append(f"ready ledger missing manifest provenance for {etype}")
                continue
            # the STORED source_id must be allowlisted: evaluate_event sets source_id from the spec and
            # IGNORES the row's, so a spoofed/unknown source would otherwise slip through the recompute.
            if ev.get("source_id") != ME.EVENT_SPECS[etype]["source_id"]:
                errs.append(f"{etype} provenance source_id {ev.get('source_id')!r} not allowlisted")
            # RE-EVALUATE freshness from the persisted EVIDENCE (Codex P2r20 [high]) — never trust the
            # stored present/fresh booleans. A row with stale or future evidence (e.g. a 2020 release date,
            # a passed FOMC meeting, an unrefreshed rate) and fresh:true must FAIL here exactly as it would
            # have at generation; a verdict-boolean stub with no evidence fails as missing_fields.
            # MALFORMED evidence (e.g. an unparseable date) must REJECT, never crash the validator
            # (stop-gate): a raised exception would abort the whole ledger scan, not fail this record closed.
            try:
                re_eval = ME.evaluate_event(etype, ev, rec.get("as_of"))
                ok = re_eval["present"] and re_eval["fresh"]
                reason = re_eval.get("stale_reason")
            except Exception as exc:  # noqa: BLE001
                ok, reason = False, f"unparseable_evidence:{exc.__class__.__name__}"
            if not ok:
                errs.append(f"{etype} provenance not present+fresh on recompute ({reason})")
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
    """The blob sha of `rel` in the tree of `ref` per the GitHub API. Returns None ONLY when the path is
    genuinely ABSENT at that ref (HTTP 404). ANY other failure (auth, rate-limit, network, 5xx) RAISES
    (Codex P2r22): collapsing a transient lookup failure to None could let one trusted run's missing check
    masquerade as 'this run simply didn't carry the file' while another run attests the current blob — so
    `attested` would shrink to {current} and the lock would PASS instead of failing closed as
    unverifiable. The caller's outer try turns a raise into lock_unverifiable (fail-closed)."""
    import subprocess
    out = subprocess.run(["gh", "api", f"/repos/{repo_slug}/contents/{rel}?ref={ref}", "--jq", ".sha"],
                         capture_output=True, text=True, timeout=60)
    if out.returncode == 0:
        return out.stdout.strip() or None
    err = (out.stderr or "").strip()
    if "404" in err or "Not Found" in err:           # path genuinely absent at this ref — not an attestation
        return None
    raise RuntimeError(f"blob lookup failed for {rel}@{ref}: {err or 'gh api contents nonzero'}")


def _github_path_touched_at(repo_slug: str, rel: str, ref: str) -> bool:
    """True iff `rel` was modified by ANY commit reachable from `ref` (even if a later commit removed it).
    Used for the writer-bound first-appearance proof (Codex P2r33 stop-gate): a TREE check at a push head
    misses an intraday add-then-remove laundering (head = the removal commit), but the path's COMMIT HISTORY
    reachable from that server-witnessed-intraday head still exposes the add. None/empty history ⇒ the path
    never existed on main by `ref`. Raises on any non-404 failure so the caller fails CLOSED."""
    import subprocess
    out = subprocess.run(
        ["gh", "api", f"/repos/{repo_slug}/commits?sha={ref}&path={rel}&per_page=1", "--jq", "length"],
        capture_output=True, text=True, timeout=60)
    if out.returncode == 0:
        return (out.stdout.strip() or "0") != "0"
    err = (out.stderr or "").strip()
    if "404" in err or "Not Found" in err or "No commit found" in err:   # ref/path unknown ⇒ not present
        return False
    raise RuntimeError(f"path-history lookup failed for {rel}@{ref}: {err or 'gh api commits nonzero'}")


def _git_lock_error(path: Path, as_of: str, now: pd.Timestamp, repo: Path = REPO,
                    repo_slug: str | None = None) -> str | None:
    """EXTERNAL immutability proof (Codex P2r12+r13). Local git metadata (committer dates) is FORGEABLE
    (GIT_COMMITTER_DATE), so the time anchor is GitHub's SERVER-side record instead: once the lock window
    [as_of close, next session open) has closed, there must exist a GitHub Actions run whose created_at
    (recorded by GitHub, not the committer) falls inside that window AND whose head tree already contains
    this ledger at EXACTLY the current blob. Scheduled runs (crypto 00:30 UTC daily, verify_returns 13:00
    UTC weekdays — both pre-open) attest every evening's ledgers in normal operation. Forging this proof
    requires forging GitHub's run records. While the window is open the check is waived (nothing post-t0 is
    knowable; the same-evening CI commit + later runs provide the attestation). It ALSO requires (P2r32) that
    NO run created during the as_of trading session [open, close) already held the blob — a writer-bound
    first-appearance proof that the locked ledger was produced after close, not hand-committed intraday. Any
    API/git failure fails CLOSED. CI must pass GH_TOKEN; checkout fetch-depth:0 stays for context."""
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
        if attested != {blob_now}:
            return ("lock_ambiguous_multiple_attested_blobs" if len(attested) > 1
                    else "lock_not_proven_no_attesting_run")
        # WRITER-BOUND first-appearance (Codex P2r32): post-close presence proves the blob existed by then and
        # is immutable, but NOT that it was PRODUCED after close — a ledger hand-committed DURING the as_of
        # session with a forged post-close generated_at would still be attested by a later run. A push-path
        # trigger creates a SERVER-timestamped run for any commit to a ledger path EXCEPT those pushed by the
        # writer job's GITHUB_TOKEN (GitHub suppresses token-push events to prevent recursion). So a legit
        # post-close ledger creates NO in-session run, while an intraday hand-commit (via a PAT) does. If ANY
        # run created during the trading session [open, close) already contains this blob, it predates the
        # close → reject as look-ahead/revisable. Same fail-closed machinery; absence is the proof.
        open_utc = ME.session_open_utc(as_of)
        intraday = _github_runs_in_window(
            repo_slug, open_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            (close_utc - pd.Timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        # check the ledger path's COMMIT HISTORY reachable from each in-session run head, NOT just its tree at
        # head (Codex P2r33 stop-gate): a tree check would miss an intraday push that ADDS then REMOVES the
        # path before the push head. ANY intraday touch of the path ⇒ it was staged during the session ⇒
        # reject (a legit ledger is token-pushed post-close and witnesses NO in-session run).
        for run in intraday:
            if _github_path_touched_at(repo_slug, rel, run.get("head_sha", "")):
                return "lock_produced_before_close"
        return None
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
            # the ledger schema is a top-level OBJECT, one primary forecast per as_of (Codex P2r25). A
            # top-level LIST is malformed — the writer never emits one and the generation/cadence guards
            # already treat lists as malformed, so accepting [valid_record] here would let the SAME shape be
            # scored as ok in one path while refused in the other. Reject any list (incl. the 1-element case)
            # as corruption, persisted — never silently unwrapped.
            if isinstance(d, list):
                rejects.append({"file": f.name, "errors": ["top_level_list (schema is a single object)"]})
                continue
            rec = d
            if not isinstance(rec, dict):
                # a null/scalar payload must become a PERSISTED reject, not an AttributeError that leaves the
                # previous summary as the last visible artifact (Codex P2r6)
                rejects.append({"file": f.name, "errors": ["record_not_object"]})
                continue
            # ANY exception from validation/lock on an ill-typed INNER field (e.g. an unhashable `bucket`, a
            # non-dict manifest_events element) must become a NAMED per-file reject, never abort the whole
            # scan (Codex sweep): a single bad ledger would otherwise discard every other file's accept/reject
            # work AND lose the offending filename (mislabeled '<validator>'), stalling the entire track
            # record. The specific known crash sites are also hardened (contract bucket type, manifest_events
            # element type); this wrap is the generic fail-closed net for anything else.
            try:
                errs = validate_ledger_record(rec, f.name)
                if not errs:                             # schema-valid → require the EXTERNAL git lock proof
                    lock_err = _git_lock_error(f, rec["as_of"], pd.Timestamp.now(tz="UTC"))
                    if lock_err:
                        errs.append(lock_err)
            except Exception as e:  # noqa: BLE001
                rejects.append({"file": f.name, "errors": [f"validation_crashed: {e!r}"]})
                continue
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


_SUMMARY_NOTE = ("Hit-rate over NON-OVERLAPPING matured, locked forecasts; keyed on the full "
                 "(direction,bucket,support_class). PROVISIONAL until counted_N≥MIN_RESOLVED. "
                 "探索性,未驗證,非投資建議.")


def _write_summary(status: str, rejects: list[dict], summ: dict | None) -> None:
    """Persist validation_summary.json. SINGLE write path (Codex P2r23): EVERY fail-closed exit of main()
    must route through here so the committed artifact always reflects the TRUE state — a path that returns
    without rewriting it would leave CI staging the prior (possibly status=ok) summary and hide the failure.
    When scoring could not run (benchmark unavailable) summ is None → explicit zeroed counts, never stale."""
    empty = {"resolved": 0, "matured": 0, "invalid_records": [], "invalid_count": 0,
             "min_resolved_for_verdict": C.MIN_RESOLVED, "by_key": {}}
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "benchmark": C.BENCHMARK, "theta_dir": C.THETA_DIR, "buckets": C.BUCKETS,
               "validation_status": status,
               "reject_count": len(rejects), "rejected_ledgers": rejects,
               "note": _SUMMARY_NOTE, **(summ if summ is not None else empty)}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # ATOMIC write (Codex sweep): write to a temp file then os.replace, so a torn/partial write can never
    # leave a corrupt-but-parseable (or half-green) summary. os.replace is atomic on the same filesystem.
    final = OUT_DIR / "validation_summary.json"
    tmp = OUT_DIR / "validation_summary.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, final)


def main() -> int:
    # FAIL-CLOSED persistence, completed as a FAMILY (Codex P2r23 + self-sweep): the invariant is that NO
    # exit of this validator may leave a stale (possibly green) validation_summary.json for CI to stage. The
    # explicit benchmark-unavailable return is handled in _run(); this wrapper covers the other class — an
    # UNHANDLED exception (e.g. score() crash) — with a best-effort red rewrite before propagating nonzero.
    try:
        return _run()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        try:
            _write_summary("non_publishable_internal_error",
                           [{"file": "<validator>", "errors": [repr(e)]}], None)
        except Exception:  # noqa: BLE001 — even the red rewrite failed (hard FS failure: disk-full / RO FS)
            # DELETE the stale summary so a downstream reader can NEVER read a leftover green status on a red
            # run (Codex sweep): a missing summary is fail-closed (UI shows unavailable), a stale-green one is
            # not. Best-effort — if unlink also fails (RO FS) the job is still red and a human must intervene.
            try:
                (OUT_DIR / "validation_summary.json").unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
        return 1


def _run() -> int:
    records, rejects = _load_ledgers()
    gspc = gspc_close()
    if gspc is None:
        # FAIL-CLOSED persistence (Codex P2r23): a benchmark fetch/cache outage must REWRITE the summary to a
        # red state — returning early used to leave CI staging the prior (possibly status=ok) artifact,
        # hiding a dependency failure. Carry any loader rejects already found so they are not lost.
        print("[mkt-fwd] no ^GSPC history fetched — writing non_publishable_benchmark_unavailable summary",
              file=sys.stderr)
        _write_summary("non_publishable_benchmark_unavailable", rejects, None)
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
    # GENERATION-FAILURE awareness (Codex P2r27 [med]): the CI step runs this validator even when the
    # generator (market_thesis.py) failed, so a truthful summary is still persisted. But if generation
    # failed, the committed summary must NOT advertise ok — a downstream reader trusts validation_status and
    # would miss the dropped forecast / dependency outage. The CI step passes the generator rc via
    # MKT_THESIS_GEN_RC; a nonzero value forces a red status (and nonzero exit) regardless of ledger validity.
    gen_rc = os.environ.get("MKT_THESIS_GEN_RC")
    if gen_rc not in (None, "", "0"):
        status = "non_publishable_generation_failed"
    _write_summary(status, rejects, summ)
    print(f"[mkt-fwd] {summ['resolved']} forecasts, {summ['matured']} matured → {len(summ['by_key'])} keys"
          f" | rejects={len(rejects)} invalid={summ['invalid_count']} status={status}")
    for k, v in summ["by_key"].items():
        print(f"  {k}: {v['hits']}/{v['counted_N']} (raw {v['raw_N']}) rate {v['hit_rate']} "
              f"CI {v['wilson90']} [{v['verdict']}]")
    return 0 if status == "ok" else 1   # ANY taint fails the job — no clean-looking summary


if __name__ == "__main__":
    raise SystemExit(main())
