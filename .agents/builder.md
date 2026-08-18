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
observer also passed exact-hash preflight and Linux systemd verification on 7F;
the natural 2026-08-18 producer verdict remains intentionally pending.

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
