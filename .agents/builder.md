# Builder Journal

## 2026-08-12 - Retire Automatic Industry Roles Legacy Reads in Two Stages

**Implementation pattern:** Make the canonical store own a side-effect-free
empty revision-zero seed. Remove legacy payload arguments from the store,
engine, and protected API instead of retaining unused path injection. Preserve
the exact injected canonical state path for both API reads and mutations.

**Verification insight:** A static filename-owner oracle catches accidental
legacy fallback more reliably than behavior tests alone. Pair it with negative
fixtures where valid-looking legacy files exist beside a missing or invalid
canonical state, and prove they are ignored.

**Authority boundary:** Keep the explicit emergency export through the natural
R2 observation window, but do not apply it. Removing that surface is R3 and
requires a successful R2 result plus separate deployment-owner authorization.

**Apply when:** A compatibility source is absent in production and automatic
reads can be retired independently from the last explicit recovery projection.

## 2026-08-15 - Retire the Explicit Industry Roles Export Surface

**Implementation pattern:** Once the natural producer window and second owner
authorization pass, delete the export command, manifest codec/writer, and
inspection fields as one bounded slice. Keep canonical inspection and guarded
backup restore byte-for-byte on their existing transaction path.

**Verification insight:** The durable oracle is negative: reject the retired
CLI command, recursively require zero production filename/export-symbol owners,
and prove restore preview, wrong-ETag rejection, apply, revision, and backup
rotation still work. A one-time runtime exact-path preflight must replace the
removed permanent manifest inspection during rollout.

**Review correction:** Do not replace a retired phase-gate field with a
hard-coded `PASS`; remove it. Also search the whole current contract document
for stale R1/R2 present-tense claims, not only the paragraph being edited.

**Baseline note:** `make test` still exposes four detached-main fixture/artifact
failures; each reproduced on `origin/main`, while every R3-focused and remaining
non-baseline entry passed.

## 2026-08-15 - Recover the Clean-Clone Full-Test Baseline

**Implementation pattern:** Keep runtime reports optional and move deterministic
test inputs into temporary resolvers. Track only the exact hash-bound historical
rollback bundle, with nested ignore rules that reject every extra snapshot file.

**Validator correction:** Compounded equity is non-negative and finite but not
artificially capped. Integer values remain exact, float values retain the
existing tolerance, and curve-tail mismatches fail closed without overflow.

**Verification insight:** Test both producer-realistic large floats and legal
JSON integers beyond float range. The latter exposed an `OverflowError`, while
an additional `10**20 + 1` probe caught precision collapse above `2**53`.

**Result:** Four formerly failing entries, related API/UX/deployment suites,
compileall, whitespace and complete `make test` pass in the isolated worktree.

## 2026-08-16 - Add a Bounded Money Flow Transport Fallback

**Implementation pattern:** Keep the normalized provider identity and request
shape stable while trying an exact ordered pair of compatible transport routes.
Return immediately on the primary route's first non-empty result; try the
delayed route only after a transport/HTTP failure or an empty parsed response.

**Verification insight:** Fail-soft adapters can make a scheduler look healthy
while coverage is zero. Test primary preference, transport failure, empty data,
and total outage separately, then retain the existing publication threshold so
the fallback cannot invent usable coverage.

**Result:** The new cases failed 9/12 before implementation and passed 12/12
afterward. Focused downstream suites, Python compatibility/compile checks,
whitespace checks, complete `make test`, and a second closure review passed.

## 2026-08-16 - Preserve Analytics Operational Provenance

**Implementation pattern:** Model producer availability separately from output
cardinality. A configured source that successfully emits zero rows is distinct
from an absent, invalid, or unreachable source. Persist that observation so the
checker and UI do not guess from an empty data table.

**Provenance pattern:** Candidate scores carry explicit bounded-cohort metadata,
and Risk Guard keeps source date separate from observation date. A malformed
higher-priority provenance field fails closed instead of falling through to a
newer but semantically weaker timestamp.

**Recovery boundary:** Restore only absent dated report files whose retained
workflow artifact, source SHA, report date, and payload agree. Never promote
root runtime files or infer picks, ledger rows, or weights.

## 2026-08-17 - Guard the Analytics Natural Validation Window

**Implementation pattern:** Run a deploy-stable, read-only observer outside the
mutable `current/` tree and bind it to exact reviewed runtime hashes. Discover
the natural EOD run by its non-skipped job identity and terminal lifecycle, not
its nominal cron minute, while keeping Data Health, EOD, and Theme Flow as
independent fail-closed gates.

**Evidence pattern:** Persist atomic latest/final JSON plus an append-only
timeline under `shared/`. Cache only successfully verified immutable GitHub
evidence, retry transient API failures, and require explicit unknown states
instead of inferring missing, failed, or unpublished runs.

**Five-axis impact:** Direct changes are limited to the observer, one-time units,
Telegram step isolation, test wiring, and documentation. Callers are the
one-time user-systemd timer and standard `make test`; persistent writes are only
the dedicated evidence directory. No producer, pick, weight, ledger, IBKR,
threshold, API, database schema, or deployment topology changed.

**Result:** Focused observer/deployment/publisher/Risk Guard/Analytics suites,
compile/YAML/whitespace gates, and the complete test suite passed. The final
observer also passed exact-hash preflight and Linux systemd verification on 7F.
At that preflight checkpoint the natural 2026-08-18 producer verdict was
intentionally pending; the 2026-08-21 reconciliation records its terminal PASS.

## 2026-08-18 - Transactional Post-producer Analytics

**Five-axis impact:** Direct changes add one transaction helper, one producer
observer, two systemd units, Data Health/deploy wiring, evidence, tests, and an
operator guide. Callers are the 7F timer, scheduled Data Health, optional deploy
refresh, and `make test`. Persistent writes are limited to
`shared/published_reports`, `shared/post_ingestion`, `shared/run_status`, the
shared Analytics root, and one lock file. No public API, database schema,
scoring, picks, weights, ledger rows, provider contracts, or IBKR behavior
changed. Operational impact is one staged Analytics generation per producer
window; rollback is a code revert/redeploy while shared generations remain.

**Maintainability result:** Report overlay, locking, staged promotion, producer
discovery, artifact contracts, and evidence have separate callable seams. The
same transaction helper is reused by Data Health and the post-producer path so
last-known-good behavior does not diverge.

## 2026-08-18 - Overlay Sibling Compatibility Hotfix

**Five-axis impact:** The direct change is limited to overlay construction and
its regression test. Existing Analytics importers remain the callers and keep
their unchanged `reports.parent` lookup contract. The only runtime effect is
that the staged build can again read the release's manual watchlist and ranked
candidate fallback; there is no API, schema, scoring, producer, picks, weights,
ledger, credential, or persistent-state change.

## 2026-08-18 - Close the Post-producer Atomic Boundary

**Implementation pattern:** Finalize report downloads as an immutable prepared
generation without moving `current`. Hold the one shared writer lock while the
strict Analytics build and semantic gate read that prepared generation, then
promote the report pointer as a rollback-capable companion immediately before
Parquet/checks/DuckDB promotion. Make DuckDB the last commit point and compute
return evidence before durable state changes.

**Five-axis impact:** Direct changes are limited to report preparation,
Analytics transaction promotion, terminal evidence, regressions, and the
operator guide. Callers remain the post-producer observer and the unchanged
lock-owning Data Health/deploy API. Types add one internal prepared-generation
record; no public API or database schema changes. Deployment units and runtime
configuration are unchanged. Documentation now defines the single-lock and
four-output rollback contract. No scoring, picks, weights, ledger rows,
providers, IBKR behavior, credentials, or schedules changed.

**Maintainability result:** The locked core and lock-owning wrapper make lock
ownership explicit without a boolean mode. Companion promotion returns one
exact rollback closure, while the Analytics promoter owns DB, Parquet, and
checks rollback. Unreferenced failed preparations remain immutable evidence.
## 2026-08-18 - Extend the Transaction Through Terminal Evidence

**Implementation pattern:** Treat report and Analytics promotion as provisional.
Return an explicit lifecycle that retains old DuckDB, Parquet, checks, and the
companion pointer rollback until the caller durably publishes both PASS
evidence files and calls `commit()`.

**Compatibility:** Existing Data Health callers retain the immediate-commit
mapping API. Only the post-producer observer uses the provisional already-locked
seam, and its exception path rolls back before the shared lock is released.

## 2026-08-18 - Make Terminal Transactions Recoverable Across Process Death

**Implementation pattern:** Persist a validated journal after durable rollback
copies and before report-pointer or Analytics mutation. Restore DB, Parquet,
checks, and the pointer from non-consuming backups, publish canonical FAIL
evidence, then durably mark rolled back before atomically renaming cleanup
residue out of the recovery namespace. A committed marker performs cleanup
only.

**Compatibility:** Every existing Analytics writer recovers under the same
lock before building. The observer additionally recovers before network
polling and systemd restarts only abnormal signal/timeout exits. Public APIs,
Analytics schema, scoring, picks, weights, ledger data, and schedules are
unchanged.

## 2026-08-19 - Confirmed Picks and Ledger Integrity

**Implementation pattern:** Derive versioned technical facts once in Stage 1,
reapply the existing rubric deterministically in Stage 2, project final picks
only from DD-confirmed source rows, and give every local CSV writer one advisory
lock plus fsynced atomic replacement.

**Safety boundary:** Explicitly missing evidence scores zero; zero picks leave
the ledger byte-identical; concurrent return calculation merges into a fresh
locked read; no threshold, weight, DD rule, or historical pick is changed.

## 2026-08-19 - Enforce Existing Score Caps Without Changing Weights

**Root cause:** Stage 2 replaced the LLM technical score and then unconditionally
set composite to the seven-score sum, erasing the rubric's no-volume,
sentiment/technical, options/technical, incomplete-dimension, and risk-veto
constraints.

**Implementation pattern:** One pure scoring-contract module now owns technical
cap arithmetic, composite caps, verdict ordering, original LLM provenance,
closed risk-veto IDs, and fail-closed validation. Both Stage 2 and the Actions
gate execute it; every applied adjustment records exact before/after values.

**Five-axis impact:** Direct changes are limited to Stage 2 scoring, one shared
validator, the EOD gate, tests, plan, and operator documentation. Callers are
full candidate scoring and its workflow validator. Types add persisted scoring
provenance only; no API or database schema changes. Runtime impact is local
arithmetic only. No weights, thresholds, picks, ledger data, schedules,
credentials, or provider calls changed.

## 2026-08-19 - Enforce Social Ticker Provenance

**Implementation pattern:** Parse only successful tweet stdout, accept plain
uppercase tokens only from accumulated local universe snapshots, propagate
cashtag/source evidence through schema v2, and gate outcome price loads through
one pure eligibility contract.

**Compatibility:** Curated picks and explicit cashtags remain visible discovery
evidence; platform-validated rows and prior positive market outcomes remain
outcome-eligible. Unverified legacy prose is skipped with receipts; transient
quote failure preserves last-known-good rows.
No scoring, picks, performance ledger, API, database, credential, or schedule
behavior changes.

**7F amendment:** Explicit cashtag and curated-source flags remain persisted but
are no longer sufficient for outcome price loading. The shared contract now
returns `cashtag_unverified` or `curated_ticker_unverified` unless independent
market identity is present.

## 2026-08-20 - Harden Stage 7 Natural Validation

Bound the scheduled job, capture run-head ledger/receipt evidence, gate exact
append-only mutations before a race-safe allowlisted publish, and persist an
explicit PASS_NOOP/PASS_UPDATED/failure verdict. Job-local Analytics is labeled
non-authoritative for 7F. A post-merge hotfix replaced a job-level runner context
that GitHub rejects; no run, pick, ledger row, or threshold was manufactured.

## 2026-08-21 - Add Promotion Reachability as a Shadow Contract

**Implementation pattern:** Derive a per-source capability manifest only from
already-fetched Layer 1 evidence, then attach the diagnostic after all existing
score, cap, verdict, and DD calculations. Reuse the production technical and
composite contracts, including one-decimal verdict rounding, instead of
reimplementing near-equivalent arithmetic.

**Fail-closed boundary:** Distinguish unavailable evidence (a supported maximum
of zero) from malformed or incomplete evidence (an unknown maximum). Rebuild
each candidate diagnostic during run summarization so a tampered modern payload
cannot promote a known reachability state.

**Five-axis impact:** Callers are full Stage 2 scoring, the existing candidate
snapshot path, Analytics export, and one independent Analytics check. Types add
versioned shadow fields only. No score, threshold, weight, verdict, Layer 2,
pick, ledger, provider, schedule, API, or Stage 7 authority changed.

## 2026-08-23 - Harden Natural Validation Recovery Boundaries

**Implementation pattern:** Reuse the authoritative full-score contract at the
fixed-SHA ingestion boundary, recompute the complete promotion-reachability
receipt from every candidate, and preserve an exact Analytics defence-in-depth
contract. Pin the first immutable main SHA across all artifact retries. Treat
only idempotent GitHub transport/publication lag, typed writer-lock contention,
and missing Yahoo batch tickers as retryable; bound them by attempt count or the
existing validation deadline.

**Recovery:** Local Data Health, Theme, and post-ingestion oneshots have two
delayed recovery starts within a 16-hour limit window that blocks a fourth
maximum-duration start. Theme failure remains pending while recovery is
possible. A lock-holding parent bounds Analytics in a killable child, recovers
its journal, and rejects lock wait or PASS evidence after the deadline. GitHub
producer, immutable artifact-contract, Analytics, promotion, and evidence-write
failures retain exact last-known-good behavior. The report pointer's containing
directory is fsynced after promotion and rollback, and a post-commit recovery
regression proves durable success cannot be mistaken for an abandoned pending
promotion.

**Five-axis impact:** Callers are post-producer ingestion, Stage 1 Yahoo batch
fetching, and three local service templates. Tests, service configuration,
operator documentation, and skill journals are updated. Candidate JSON and
terminal evidence contracts become stricter; no API/DB schema, dependency,
secret, pick, ledger, weight, threshold, or natural schedule changes.
