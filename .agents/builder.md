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

## 2026-08-27 - Recover Delayed Natural Validation and Report Publication

**Implementation pattern:** Derive the EOD report date from the immutable
scheduled slot instead of runner wall-clock time, retain the 10:30 SLA verdict
while allowing a bounded late-recovery observation, and route every ordinary
report writer through the shared race-safe publisher. Canonicalize all Analytics
provenance after staging so durable evidence names `shared/data`, never an
ephemeral staging directory.

**Recovery and evidence:** Late success is recorded as `RECOVERED_LATE`, never
rewritten as on-time. Terminal producer failures still fail immediately, and
last-known-good generations remain protected. Candidate outcome regressions
exercise a concurrent Stage 7-like push with dirty runtime output. The real
Oversold artifact also exposed a floating-point boundary error; validation now
accepts the producer's four-decimal inclusive threshold without widening the
documented contract.

**Five-axis impact:** Changes are limited to EOD date provenance, the
post-producer observer/service, report publication workflows, Analytics evidence
paths, the Oversold boundary validator, tests, plan, and operator documentation.
No pick, ledger row, score, weight, threshold, provider, credential, API schema,
database schema, or natural schedule was changed. Focused regressions and the
complete `make test` gate pass; PR, deployment, 7F verification, and the next
true natural race window remain runtime gates at this checkpoint.

## 2026-08-31 - Rebaseline the Current-Main UX-1B Capture Stack

**Root cause:** The stale capture stack could not reproduce current main in a
fresh worktree: the private recovery namespace did not exist, the authenticated
source mirror omitted `clients/`, the host-awake parser rejected a current
charging form, and multi-root Radar controls did not fit one mobile viewport.

**Implementation pattern:** Preserve the old canonical until a complete
transaction succeeds; create the fixed private archive path through validated
directory descriptors; include the private frontend client package in the
source mirror; accept only exact AC state tokens; and reuse request-v2 root
outputs for focused discovery/smoke. Root expansion is filtered to the requested
logical rows, so subsets cannot inherit the global 44-root expectation.

**Verification:** Fail-first regressions cover every correction. The real
transaction passed 21 full-page discovery rows, 36 focused logical requests,
44 root captures, 57 derived catalog sidecars, and 37 quiescent processes. The
new nine-member contract reopened at `7d84b1e...6380`; the exact old 5340-byte
contract remains archived at its digest. Current scoped suites pass, including
Snapshot 63/63 and a real Radar mobile two-root capture.

**Five-axis impact:** Callers are only UX-1B capture-stack freeze/smoke and the
local awake gate. Types change no public API or database schema; focused smoke
now exposes root capture IDs while preserving ten logical mobile identities.
Data impact is limited to local deterministic evidence and one private rollback
archive. Performance trades a composite screenshot for independent roots and
uses the already bounded 36-request/44-root path. Security retains descriptor,
owner, mode, no-follow, network-deny, credential, data, report, and environment
exclusions. No production UI, provider, dependency, score, threshold, pick,
ledger, workflow, schedule, or 7F state changed.

## 2026-08-31 - Close the UX-1B Watchlist Taxonomy Fixture Gap

**Root cause:** The first formal pre-theme run failed closed at 78/81 because
Watchlist Categorize called the real loopback Theme Taxonomy client. The
authenticated sandbox denied that undeclared dependency, Streamlit rendered an
exception, and the terminal full-page marker never appeared.

**Implementation pattern:** Patch `load_theme_taxonomy` only inside the existing
provider-fixture context, return one typed deterministic taxonomy item, and
count the call in the exact Watchlist route contract. A fail-first regression
proves the real function is replaced, the fixed payload is returned once, no
network record appears, and restoration returns the original callable.

**Verification:** The exact Watchlist desktop sandbox probe changed from the
same marker timeout to 1/1 PASS. Fixture 27/27, Snapshot 63/63, Isolation 29/29,
Selection Fixture 5/5, Theme 9/9, Theme Matrix 24/24, Contract 19/19,
Navigation 66/66, Components 6/6, and UX-1A Safety 5/5 pass. A second CAS
rotation passed 57 discovery sidecars, 44 root captures, and 37 quiescent
processes; the canonical reopened at `3784ef8...b8df` and the prior exact file
is preserved in its digest-named private archive.

**Five-axis impact:** Direct changes are limited to deterministic UX-1B fixture
data, its counter/test contract, the current capture-stack authority, and local
evidence. Callers remain the local capture harness; production UI and provider
code are unchanged. The added type is an existing public DTO instance and no
API or database schema changes. Runtime impact removes one accidental test-only
loopback attempt and adds no production work. Security keeps the exact sandbox,
network deny, timeout, descriptor, and rollback boundaries. No report, data,
score, threshold, weight, pick, ledger, workflow, schedule, dependency, or 7F
state changed.

## 2026-09-01 - Accept the Current-Main UX-1B Pre-Theme Baseline

**Root cause:** The first technically complete 81/81 matrix was not acceptable
evidence because its accessible text exposed an authenticated fixture-root path
on Analytics and a host-specific Agent Reach path on both X pages.

**Implementation pattern:** Add fail-first restoration tests, project only the
two display paths inside deterministic fixture contexts, rotate the authenticated
capture stack through the existing compare-and-swap transaction, and reject the
old matrix instead of rewriting it. The fresh matrix passes its exact manifest,
counter, quiescence, diagnostics, path, and secret gates.

**Verification:** The accepted run contains 81 PNGs and 81 render sidecars.
Every screenshot was reviewed: 71 are byte-identical to already-reviewed images
and all ten changed images were inspected at original resolution. Nine sidecars
contain only the expected Analytics/X display-path corrections; the other 72 are
semantically identical after excluding per-run provenance. Six additional PNG
hash changes are sub-pixel rendering noise with SSIM at least 0.999998.

**Five-axis impact:** Callers remain the local UX-1B fixture and capture tools;
production UI, providers, APIs, schemas, data, and 7F are untouched. Types and
dependencies do not change. Runtime impact is confined to deterministic capture
display projection. Security removes absolute host paths and confirms zero
credential-token patterns, live network, production read/write, or mutator
attempts. No report, score, threshold, weight, pick, ledger, workflow, or
schedule changed. Phase 2 fail-first tests are now authorized; production theme
edits remain blocked until main drift and semantic-failure gates pass.

## 2026-09-01 - Establish the UX-1B Production Fail-First Contract

**Implementation pattern:** Layer production-facing checks over the existing
independent palette and browser oracle. The new checks require the exact
Streamlit semantic mapping, immutable production token projection, a no-argument
deterministic scoped CSS builder, complete state/owner coverage, danger-red
exclusion, and exactly one trusted static app injection.

**Fail-first evidence:** With all three production files still byte-identical to
the execution receipt, the config check failed on the current red mapping, the
builder check failed because no production builder exists, and the app check
failed because the trusted injection count is zero. These are expected Phase 2
failures, not regressions or an implementation PASS.

**Five-axis impact:** Only the focused theme test and local receipt are added.
There is no production caller, type, runtime, data, API/schema, dependency,
security boundary, or 7F change. The production batch remains blocked on the
fresh origin/main drift check and the exact three-file prechange hashes.

## 2026-09-01 - Rebaseline the UX-1B Theme Verifier for Current Streamlit

**Root cause:** The Phase 3 browser gallery exposed four verifier assumptions
that no longer matched Streamlit 1.57: the selectbox accessible name changes
with its value, the popup has a stable Streamlit test id rather than one unique
global listbox, pseudo-element contract selectors are not DOM nodes, and the
framework scrolls `stMain` internally so document-coordinate crops were not a
real full-page projection. Alert contrast was also sampled from the icon-bearing
wrapper instead of the exact body text.

**Implementation pattern:** Keep production shell behavior untouched and repair
only the authenticated theme verifier and fixture. Bind selectbox discovery to
one owned combobox while validating its initial accessible name, scope options
to the stable dropdown, project pseudo selectors to their owned DOM nodes,
measure exact alert body text, and make only the fixture gallery a document-full
page. Freeze the changed capture members with the existing compare-and-swap
transaction before accepting any new pre-theme evidence.

**Verification:** A direct real Chromium desktop gallery passed all semantic,
contrast, focus-gap, crop, counter, and quiescence checks. The formal CAS run
passed 57 discovery sidecars, 44 root captures, and 37 quiescent processes;
canonical SHA is `e77fde3...f730`, with exact predecessor `c7f3b2d...70a5`
preserved in its digest-named private archive. Snapshot Matrix 63/63, Theme
Matrix 27/27, and Theme Contract 12/12 pass with no residual browser or
Streamlit process.

**Five-axis impact:** Callers are limited to the local UX-1B theme fixture,
verifier, and capture-stack authenticator. Public API/database types and schemas
do not change. Runtime cost is confined to deterministic evidence capture; the
production Streamlit shell receives no verifier layout rule. Security retains
the exact-origin, credential-free child environment, owned-output, network
counter, CAS archive, and fail-closed boundaries. No production theme, provider,
data, report, score, threshold, weight, pick, ledger, workflow, schedule,
dependency, deployment, or 7F state is included in this verifier checkpoint.

## 2026-09-01 - Accept the Capture-Stack-Rebased UX-1B Pre-Theme Baseline

**Execution pattern:** Run the full 27-page by three-viewport matrix from an
isolated detached `33e8f0e` worktree whose three production theme files retain
their exact entry hashes. The first transaction failed closed at
`options-cockpit/mobile`; its terminal manifest was preserved and not promoted.
Because the worker protocol intentionally collapses transient and semantic
validity failures into the same error type, no unsafe broad retry was added.
Instead, the exact case passed three independent real-browser probes before a
fresh complete transaction was allowed.

**Verification:** The accepted second transaction passed 81/81 with 81 PNGs,
81 render sidecars, 163 total files, mode 0600, equal source start/end digests,
capture-stack SHA `e77fde3...f730`, exact provider counters, zero mutators and
prohibited access, and no residual process. Relative to the previously reviewed
baseline, all 81 semantic sidecars are identical after excluding per-run
counter provenance and 77 PNGs are byte-identical. The four changed PNGs were
reviewed at original resolution; only 5-162 pixels changed and minimum global
SSIM is 0.999997782787.

**Five-axis impact:** The accepted authority is consumed only by later UX-1B
posttheme comparison and rollback gates. Types, APIs, database schemas, and
dependencies do not change. Runtime work is local deterministic capture only.
Security retains the isolated source mirror, exact-origin browser, counter,
credential, descriptor, CAS, and fail-closed publication contracts. Production
UI, providers, data, reports, scores, thresholds, weights, picks, ledger,
workflows, schedules, deployment, and 7F state remain unchanged; the historical
pretheme receipt remains intact and is superseded only as capture authority.

## 2026-09-01 - Reconcile UX-1B with Post-Receipt Current-Main Drift

**Execution pattern:** Stop continuation after `origin/main` advanced from the
accepted entry SHA, preserve the pre-drift branch on a local archive ref, merge
the three candidate-output files without conflict, and create an isolated
detached worktree at the reconciled execution head with the production theme
files restored to their exact prechange hashes. Run a completely fresh 27-page
by three-viewport pretheme transaction instead of assuming candidate-only drift
is harmless.

**Verification:** The current-main transaction passed 81/81 with 81 PNGs, 81
render sidecars, 163 mode-0600 files, exact provider counters, zero mutators and
prohibited access, equal source digests, and zero residual process. All 81
semantic sidecars match the prior accepted pretheme after excluding the
per-run counter hash. Seventy-four PNGs are byte-identical; the seven changed
images were reviewed at original resolution and differ by only 3-162 pixels,
with minimum global SSIM 0.999997782787 and no visual or semantic blocker.

**Five-axis impact:** The drift reconciliation changes execution ancestry and
private deterministic evidence only. Callers, public types, APIs, database
schemas, dependencies, provider behavior, and security boundaries are
unchanged. Runtime cost is confined to the isolated fixture matrix. No UX-1B
production edit was committed or deployed before reconciliation; no report,
pick, ledger, score, weight, threshold, workflow, schedule, credential, or 7F
state was changed by this checkpoint. The production batch may resume review,
while UX-1B classification remains pending.

## 2026-09-01 - Stabilize Full-Page Theme Geometry and Failure Evidence

**Root cause:** The formal Theme Gallery captured all semantic states correctly,
but Playwright full-page screenshots could restore a different window scroll
position. The verifier compared viewport-relative scroll and rectangle fields
byte-for-byte, so equal document-space geometry was rejected as a layout shift.
The nonzero browser exit was then reported only as a generic isolation error
because the runner waited for a clean exit before decoding the worker's bounded,
schema-validated failure response.

**Implementation pattern:** Project each surface rectangle into document space
by combining its viewport rectangle and scroll offset, while retaining the exact
authenticated crop and dimensions. Accept only inverse scroll/rectangle motion;
real crop or uncompensated layout movement still fails closed. After a nonzero
exit and process-family cleanup, decode only the owned mode-0600 response and
surface its validated error type while preserving the original exception as the
cause. Rotate the nine-member capture stack through the existing compare-and-swap
transaction before accepting replacement pre-theme evidence.

**Verification:** Theme Matrix 28/28, compileall, and diff checks pass. A direct
real Chromium desktop collector plus the post-screenshot worker tail passes.
The formal CAS transaction passed 57 discovery sidecars, 44 root captures, and
37 quiescent processes with no residual runtime. Canonical SHA is
`5d3ea011...15ff`, capture-stack digest is `004cc0e1...6d46`, and predecessor
`e77fde3...f730` is preserved byte-exactly in its digest-named private archive.

**Five-axis impact:** Callers are limited to the local UX-1B verifier, its tests,
and capture-stack authenticator; public types, APIs, and database schemas are
unchanged. Runtime work remains isolated deterministic browser capture with no
production dependency change. Security keeps exact-origin sandboxing, bounded
owned response decoding, authenticated crops, CAS replacement, and fail-closed
real-shift detection. Production theme files are excluded from this checkpoint;
providers, data, reports, scores, thresholds, weights, picks, ledger, workflows,
schedules, deployment, credentials, and 7F state are unchanged. A fresh 81/81
pre-theme matrix on this exact stack remains required before production closure.

## 2026-09-01 - Accept the Geometry-Stable UX-1B Pre-Theme Baseline

**Execution pattern:** Create an isolated detached worktree at verifier
checkpoint `48b4b99`, confirm the three production theme files retain their
exact prechange hashes, and run a new 27-page by three-viewport pre-theme
transaction against canonical capture-stack `5d3ea011...15ff`. Preserve every
earlier baseline and copy the new evidence only after terminal and content
authentication passed.

**Verification:** The transaction passed 81/81 with 81 PNGs, 81 render
sidecars, 163 mode-0600 files, manifest `61bd025d...4bec`, equal source digests,
exact provider counters, zero mutators/prohibited access, no sensitive host-path
or credential pattern, and no residual runtime. All 81 semantic sidecars match
the prior accepted current-main baseline after excluding only the per-run
counter hash. Seventy-five PNGs are byte-identical; six original-resolution
pairs differ by 3-162 pixels with minimum global SSIM 0.999997782787 and no
visible or semantic blocker.

**Five-axis impact:** This checkpoint changes only private deterministic
evidence, its review receipt, and execution authority for the later post-theme
comparison. Public callers, types, APIs, database schemas, dependencies,
providers, and security policy do not change. Runtime work remains local and
isolated. No production theme source was included; no data, report, score,
threshold, weight, pick, ledger, workflow, schedule, deployment, credential, or
7F state changed. UX-1B remains pending while production review resumes.

## 2026-09-01 - Minimize Theme Sidecars and Re-Freeze the Capture Boundary

**Root cause:** The formal gallery correctly emitted its dedicated authenticated
`themeEvidence`, but the generic full-page DOM projection also retained 271
framework nodes and 38 controls. That duplicate state did not match the
theme-gallery contract and could make unrelated Streamlit DOM churn invalidate
semantic evidence. Current Streamlit also exposes the selected selectbox value
as part of its accessible name, while the evidence validator still expected the
historical label-only name. A direct CLI regression additionally attempted to
re-authenticate the historical prechange contract against an intentionally
modified production worktree.

**Implementation pattern:** For the exact `theme-gallery` request, require an
empty generic-root declaration and publish no generic DOM nodes; all other
captures retain their existing projection. Synchronize the selectbox evidence
contract to the independently observed current accessible name and add mutation
coverage for the old value. Exercise historical prechange and scope commands in
a complete isolated contract workspace while retaining a direct real-repository
entrypoint smoke. Re-freeze all nine capture members through the existing
compare-and-swap transaction before producing replacement baseline evidence.

**Verification:** Evidence, Theme Matrix 29/29, Theme Contract 12/12, compileall,
and diff checks pass. The formal freeze passed 57 discovery sidecars, 44 smoke
captures, and 37 quiescent processes. Canonical SHA is
`ab73d5a6...04d2`, capture-stack digest is `7c78f4fa...c342`, and predecessor
`5d3ea011...15ff` is preserved byte-exactly in its digest-named private archive.
Snapshot Matrix passes 63/63 after rotation, with no residual browser or
Streamlit process.

**Five-axis impact:** Callers are limited to the local UX-1B browser worker,
evidence validator, their regressions, and capture-stack authenticator. Public
types, APIs, and database schemas do not change. Runtime cost remains local
deterministic browser capture; dependencies are unchanged. Security keeps the
exact-origin sandbox, credential-free child, bounded authenticated artifacts,
CAS archive, and fail-closed non-theme projection behavior. Production theme
files are excluded from this checkpoint; providers, data, reports, scores,
thresholds, weights, picks, ledger, workflows, schedules, deployment,
credentials, and 7F state are unchanged. A new 81/81 production-clean pretheme
on this exact stack remains required before posttheme comparison.

## 2026-09-01 - Accept the Final-Stack Current-Main Pre-Theme Baseline

**Execution pattern:** Re-run the origin/main drift gate after capture-stack
rotation. When main advanced by six natural report/candidate-output commits,
preserve `f0e6422` on a local safety ref, stash only the four production theme
files, merge main without conflict, and restore a byte-identical production diff
(`99b74f27...88f4`). Create a detached production-clean worktree at merge
checkpoint `a7bf527`, confirm the three entry hashes and final capture-stack SHA,
then run a completely fresh 27-page by three-viewport pretheme transaction.

**Verification:** The transaction passed 81/81 with 81 PNGs, 81 sidecars, 163
mode-0600 files, manifest `a8adc560...389e`, equal source start/end digests,
exact provider counters, zero mutators/prohibited access, no sensitive pattern,
and no residual process. All 81 semantic sidecars match the prior accepted
baseline after excluding only the per-run counter hash. Seventy-seven PNGs are
byte-identical; the four remaining original-resolution pairs differ by 5-184
pixels, maximum channel delta 9, minimum global SSIM 0.9999996668, and have no
visible or semantic blocker.

**Five-axis impact:** The new authority changes only private deterministic
evidence, its receipt, and current-main ancestry for the later posttheme gate.
Public callers, types, APIs, database schemas, dependencies, providers, and
security policy do not change. Runtime work remains local isolated capture. The
upstream report commits are preserved as natural main history and were not
produced or altered by UX-1B. Production theme edits remain uncommitted and
excluded; no score, threshold, weight, pick, ledger, workflow, schedule,
deployment, credential, or 7F state changed. UX-1B remains pending.

## 2026-09-01 - Gate Theme Widget Reruns Before Pixel Evidence

**Root cause:** Theme Gallery correctly excluded generic DOM nodes, but its
theme-only worker guard initially treated the already-authenticated global
affected-root catalog as if it were a requested projection. After that boundary
was corrected, the formal gallery exposed a second race: horizontal-radio and
selectbox keyboard mutations returned before Streamlit finished its server
rerun. The next checked toggle could therefore retain correct checked semantics
while an ancestor's stale opacity composited the expected `#3b82f6` paint to
`(37, 64, 110)`. Direct tracing observed 42-69 stale nodes at the old return
point.

**Implementation pattern:** Keep the theme gallery's generic node projection
empty while accepting only its frozen affected-root authority. Give the owned
theme fixture a monotonically increasing server render generation. Gate all
four state-changing keyboard commits (horizontal-radio right/left and selectbox
down/up) on a strictly newer generation, zero visible stale/busy/exception
nodes, the exact 48-owner set, and effective owner opacity of one. Do not use a
fixed sleep or relax the exact rendered-pixel token check. Re-freeze all nine
capture members through the authenticated compare-and-swap transaction.

**Verification:** Three real Chromium viewport collectors pass; repeated tablet
runs are digest-identical. Theme Matrix passes 30/30, Theme Contract 12/12,
Evidence 70/70, and Snapshot Matrix 63/63. The first freeze failed closed on one
transient `analytics-controls/narrow` worker result without publishing an
archive or changing canonical state; the isolated row and its exact seven-row
prefix then passed, and a clean no-concurrent-browser transaction completed 57
discovery sidecars, 44 root captures, and 37 quiescent processes. Canonical SHA
is `e9e8cf59...4912`, capture-stack digest is `415edb6e...8ab8`, and predecessor
`7de94718...fb6` is preserved byte-exactly in its digest-named private archive.

**Five-axis impact:** Callers are limited to the local UX-1B theme fixture,
theme evidence collector, browser worker projection seam, capture-stack
authenticator, and their regressions. Public types, APIs, and database schemas
are unchanged. Runtime cost adds only deterministic fixture rerun handshakes;
dependencies are unchanged. Security retains exact-origin sandboxing,
credential-free children, bounded authenticated artifacts, strict owner/opacity
checks, CAS rollback, and fail-closed pixel evidence. Production theme files are
excluded from this checkpoint; providers, data, reports, scores, thresholds,
weights, picks, ledger, workflows, schedules, deployment, credentials, and 7F
state are unchanged. A fresh production-clean 81/81 pretheme on this exact
stack remains required before posttheme closure.

## 2026-09-01 - Accept the Generation-Gated Current-Main Pre-Theme Baseline

**Execution pattern:** Pause again when `origin/main` advances, preserve the
generation-gated verifier checkpoint on a local safety ref, stash only the four
production-theme files, merge the report-only `f4e0adf` commit, and restore the
exact production diff SHA `99b74f27...88f4`. From detached production-clean
checkpoint `ad40bdb`, run a fresh 27-page by three-viewport transaction against
canonical capture stack `e9e8cf59...4912`, then reopen its manifest from the
execution worktree.

**Verification:** The transaction passed 81/81 with 81 PNGs, 81 semantic
sidecars, 163 mode-0600 files, manifest `5e53a892...3a48`, equal source
start/end digests, exact provider counters, zero mutators/prohibited access,
and no residual process. All 81 semantic sidecars match the prior accepted
baseline after excluding only the per-run counter-document hash. Seventy-five
PNGs are byte-identical; six original-resolution pairs differ by only 5-184
pixels, maximum changed ratio 0.00014198, maximum channel delta 9, and minimum
global SSIM 0.999999681911, with no visible difference. The generic credential
regex found six copies of the literal semantic identifier `sk-control`; exact
review confirmed zero credentials or host paths.

**Five-axis impact:** This checkpoint changes only private deterministic
evidence, its superseding receipt, and current-main ancestry for later Theme
Gallery/posttheme gates. Public callers, types, APIs, database schemas,
dependencies, providers, and security policy are unchanged. Runtime remains a
local isolated capture. The upstream crypto report is preserved as natural main
history and was not produced or altered by UX-1B. Production-theme edits remain
uncommitted and excluded; no score, threshold, weight, pick, ledger, workflow,
schedule, deployment, credential, or 7F state changed. UX-1B remains pending.

## 2026-09-01 - Close the Persisted Browser Calibration Schema Gap

**Root cause:** The first generation-gated formal Theme Gallery captured all
three viewports and nine surface crops but failed closed before finalization.
The real Darwin browser calibration intentionally includes a positive
`details.chromium` identity row in addition to one detail for each denied
probe. The persistence validator incorrectly required the detail keys to equal
only the denied-probe keys, while its synthetic test fixture omitted the real
positive row. No partial run was promoted.

**Implementation pattern:** Make the regression fixture reproduce the exact
browser calibration shape. Persist and accept only the single additional
`chromium` key for the browser role, and require its exact closure:
connected-at-launch, Playwright executable identity, one owned singleton, and
singleton ownership. Continue rejecting unknown details, missing denial
details, incomplete observations, or any false identity value. Re-freeze the
nine-member stack through its authenticated CAS transaction because the
validator is itself a frozen member.

**Verification:** The realistic fixture fails first with the production error,
then its targeted regression and Theme Matrix 30/30 pass. The formal CAS passes
57 discovery sidecars, 44 smoke captures, and 37 quiescent processes. Canonical
SHA is `1212d175...7d7`, stack digest is `ea4574ce...3bfb`, all nine member
descriptors reauthenticate, and predecessor `e9e8cf59...4912` is preserved
byte-exactly. Evidence 70/70, Snapshot Matrix 63/63, and Theme Contract 12/12
also pass with no residual runtime.

**Five-axis impact:** Callers remain limited to the private UX-1B Theme Gallery
audit finalizer and its regression. Public types, APIs, database schemas,
dependencies, providers, and security policy are unchanged; the fix tightens
the browser identity record while recognizing its real schema. Runtime cost is
unchanged outside deterministic local capture. Production-theme files remain
uncommitted and excluded; no data, report, score, threshold, weight, pick,
ledger, workflow, schedule, deployment, credential, or 7F state changed. A new
production-clean pretheme on this exact stack remains mandatory.

## 2026-09-01 - Accept the Calibration-Closed Current-Main Pre-Theme Baseline

**Execution pattern:** Recheck `origin/main` immediately after the verifier
checkpoint, confirm it remains an ancestor, and create a detached worktree at
`6c2221b` with the original production entry hashes. Run the full 27-page by
three-viewport pretheme against canonical stack `1212d175...7d7`; keep the
earlier invalid Gallery as negative evidence and never reuse its partial
captures as PASS evidence.

**Verification:** The fresh transaction passed 81/81 with 81 PNGs, 81 sidecars,
163 mode-0600 files, manifest `a12b8e6d...1045`, equal source start/end
digests, exact provider counters, zero mutators/prohibited access, and no
residual process. All 81 semantic sidecars match the prior accepted baseline
after excluding only the per-run counter hash. Seventy-seven PNGs are
byte-identical; four original-resolution pairs differ by 5-162 pixels,
maximum channel delta 19, and minimum global SSIM 0.9999966825715007, with no
visible difference. Sensitive inspection found no path or credential; six
generic matches are the reviewed semantic identifier `sk-control`.

**Five-axis impact:** The superseding authority changes only private evidence,
its receipt, and execution sequencing for the pending Theme Gallery/posttheme
gates. Public callers, types, APIs, database schemas, dependencies, providers,
and security policy are unchanged. Runtime remains isolated local capture.
Production-theme edits remain uncommitted and excluded; no data, report, score,
threshold, weight, pick, ledger, workflow, schedule, deployment, credential,
or 7F state changed. UX-1B remains pending.

## 2026-09-01 - Bind Calibration to the Private-HOME Browser Contract

**Root cause:** The second formal Gallery again captured 3/3 viewports and nine
surface crops, then failed closed because the first calibration correction
assumed `playwrightIdentityMatches=true`. The browser child intentionally has a
fresh private, credential-free `HOME`; Playwright's default cache path therefore
points inside that empty home and must not equal the coordinator-authenticated
executable path. The real worker launch already passes that authenticated path
explicitly and binds its SHA, so a true default-path match would indicate child
environment drift rather than stronger identity.

**Implementation pattern:** Reproduce the private-HOME result independently and
change the exact persisted `details.chromium` contract to require
`playwrightIdentityMatches=false`, while keeping connected launch, singleton
count one, singleton ownership, explicit worker path, and browser SHA gates.
Mutate false to true in the regression and require fail-closed behavior; do not
accept an arbitrary boolean. Preserve both invalid Gallery manifests as
negative evidence, never as reusable captures.

**Verification:** The realistic private-HOME fixture fails first, then targeted
and Theme Matrix 30/30 pass. The formal CAS passes 57 discovery sidecars, 44
smoke captures, and 37 quiescent processes. Canonical SHA is
`e3e03a4a...08ef`, stack digest is `19281e84...dee4`, all nine member
descriptors reauthenticate, and predecessor `1212d175...7d7` is preserved
byte-exactly. Evidence 70/70, Snapshot Matrix 63/63, and Theme Contract 12/12
also pass with no residual runtime.

**Five-axis impact:** Callers remain limited to the private Theme Gallery audit
finalizer and its exact regression. Public types, APIs, database schemas,
dependencies, providers, and security policy are unchanged; the correction
aligns persistence with the credential-free child contract while retaining the
explicit executable identity. Runtime cost is unchanged outside deterministic
local capture. Production-theme files remain uncommitted and excluded; no data,
report, score, threshold, weight, pick, ledger, workflow, schedule, deployment,
credential, or 7F state changed. Another exact-stack pretheme remains mandatory.

## 2026-09-01 - Accept the Private-HOME Current-Main Pre-Theme Baseline

**Execution pattern:** Preserve both failed Theme Gallery runs as negative
evidence, re-freeze all nine capture-stack members after correcting the exact
private-HOME browser calibration contract, and run the full 27-page by
three-viewport pretheme from detached production-clean checkpoint `b6accaa`.
Copy the completed evidence directory byte-for-byte into the execution
worktree, reopen its manifest there, and bind the next Gallery/posttheme gates
to this single stack and pretheme authority.

**Verification:** Canonical capture-stack SHA is `e3e03a4a...08ef`, stack
digest is `19281e84...dee4`, and its 57 discovery sidecars, 44 smoke captures,
and 37 quiescent-process checks pass. The fresh pretheme passed 81/81 with 81
PNGs, 81 semantic sidecars, 163 mode-0600 files, manifest
`8bd4e150...e933`, equal source start/end digests, exact provider counters,
zero mutators/prohibited access, and no residual process. All 81 semantic
sidecars match the prior accepted baseline after excluding only the per-run
counter-document hash. Seventy-five PNGs are byte-identical; six
original-resolution pairs differ by 3-162 pixels, maximum changed ratio
0.00020599365234375, maximum channel delta 19, and minimum global SSIM
0.9999966825715007, with no visible difference. Sensitive inspection found no
host path or credential; six generic matches are the reviewed semantic
identifier `sk-control`.

**Five-axis impact:** This checkpoint changes only private deterministic
evidence, its superseding receipt, and execution sequencing for the pending
Theme Gallery/posttheme gates. Public callers, types, APIs, database schemas,
dependencies, providers, and security policy are unchanged. Runtime remains an
isolated local capture. Production-theme edits remain uncommitted and excluded;
no data, report, score, threshold, weight, pick, ledger, workflow, schedule,
deployment, credential, or 7F state changed. UX-1B remains pending.

## 2026-09-01 - Close the Modern Post-Theme Comparator Reachability Gap

**Root cause:** The first complete Theme Gallery on the private-HOME stack
passed its own 3/3 capture and 9/9 surface checks, but the formal posttheme
dispatcher was still routed through the modern recovery function's early
return. The legacy pretheme loader and comparator below that return were
unreachable. A complete 81-capture live profile could therefore have supplied
the generic PASS attestation without proving parity with the authenticated
pretheme. Execution stopped before starting a formal posttheme transaction.

**Implementation pattern:** Descriptor-freeze and reauthenticate the externally
SHA-bound modern pretheme manifest and all 162 artifacts before runtime
preparation. At the posttheme boundary, descriptor-reopen and rehash all 81
live capture pairs, require the same stack and dimensions, compare every exact
canonical non-color semantic projection, and require a real PNG delta. Register
that report as the only posttheme comparator attestation before `finalizing`
and PASS authorization. Add fail-first coverage for missing captures, stack
drift, semantic drift, namespace/hash/phase drift, and incorrect PASS ordering.
Rotate the nine-member stack through the existing CAS transaction.

**Verification:** Evidence passes 71/71, Snapshot Matrix 64/64, Theme Matrix
30/30, Theme Contract 12/12, compileall and diff checks pass. The formal freeze
passed 57 discovery sidecars, 44 smoke captures, and 37 quiescent processes.
Canonical SHA is `07e08c0f...e0f48`, capture-stack digest is
`0190f682...cebc`, and predecessor `e3e03a4a...08ef` is preserved byte-exactly
in its digest-named private archive. The predecessor Gallery remains valid
historical evidence but is non-authoritative on the new stack. The generic UI
contract intentionally remains pending until the trusted site can be recorded
only after posttheme, rollback, release, deployment, and classification closure.

**Five-axis impact:** Callers are limited to the private UX-1B full-page
posttheme coordinator, descriptor-authenticated evidence adapter, comparator
attestation, and their regressions. Public types, external APIs, and database
schemas do not change. Runtime cost adds one bounded 81-pair descriptor reopen
and semantic comparison only during formal posttheme evidence. Dependencies are
unchanged. Security tightens fail-closed provenance and prevents a generic live
profile from masquerading as pre/post proof. Production theme files remain
uncommitted and excluded from this checkpoint; providers, data, reports,
scores, thresholds, weights, picks, ledger, workflows, schedules, deployment,
credentials, and 7F state are unchanged. A fresh production-clean 81/81
pretheme on this exact stack is mandatory before Gallery/posttheme reruns.
