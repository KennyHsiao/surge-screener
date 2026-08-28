# Scribe Journal

## 2026-08-12 - Evidence Invalidation Must Precede Retirement Scope

**Specification pattern:** Bind a retirement plan to a fresh release-continuity
record before naming destructive or compatibility-removal tasks. Separate
automatic-reader retirement, natural observation, and recovery-surface removal
with distinct authority gates.

**Insight:** A `READY` decision can remain historically correct while becoming
operationally stale. The successor plan should preserve that history, record the
fresh re-attestation, and make later authorization precise instead of silently
rewriting the original checkpoint.

**Authority boundary:** A technical `none found` inventory does not substitute
for a decision contract that requires a dated deployment-owner attestation.
Keep the verdict `HOLD` until that signer supplies the explicit result.

**Apply when:** A dated decision contains an explicit invalidation rule and the
repository or deployment surface changes before implementation.

## 2026-08-15 - Specify Full-Test Baseline Recovery as Four Traceable Gates

**Specification pattern:** Separate a baseline repair into validator semantics,
deterministic clean-clone inputs, optional runtime artifacts, and release
verification. Bind each requirement to named acceptance criteria,
implementation tasks, and tests before changing production code.

**Review correction:** A test resolver must cover every happy-path read, not
only helper calls; historical fixtures must not live below deployable runtime
directories; numeric acceptance must distinguish strict JSON parse failures
from shape failures.

**Result:** The accepted plan maps three requirements, four acceptance criteria,
four implementation units, and four verification gates with no orphan scope.

## 2026-08-16 - Gate Provider Fallbacks With a Live Bounded Sample

**Specification pattern:** Preserve the normalized data-source identity and
fail-closed publication threshold while adding only a bounded transport-route
fallback. Require primary-success, exception, empty-response, and total-outage
tests before runtime verification.

**Insight:** A successful scheduled service can still hide a complete optional
provider outage. Review both terminal status and coverage, then validate a
representative no-write sample from the actual deployment egress before
authorizing a fallback implementation.

**Apply when:** A best-effort provider is fail-soft by design but its coverage
has remained below the publication threshold across repeated successful jobs.
## 2026-08-18 - Plan Terminal-evidence Atomicity Remediation

**Plan boundary:** Extend the existing post-producer transaction only through
durable PASS verdict and succeeded-status writes. Keep Analytics schemas,
producer schedules, picks, weights, and ledger behavior out of scope.

**Acceptance gate at that implementation checkpoint:** Two fail-first
persistence injections had to restore the exact old generation, DuckDB,
Parquet, and checks. PR deployment and a fresh 7F 72 PASS / 2 WARN / 0 BLOCK
result were mandatory before confirmed-picks / ledger work could begin; the
2026-08-21 reconciliation records that closure.

## 2026-08-18 - Specify Process-crash Recovery

**Specification pattern:** Keep a durable pending journal and complete backup
before the first canonical mutation, then make PASS verdict, succeeded status,
and the committed journal marker one ordered boundary. Model prepare, pending,
committed, and rolled-back cleanup states explicitly so every restart decision
is deterministic.

**Review correction:** Restart only abnormal terminations; restarting every
exit-1 terminal FAIL would create an external polling loop. Use atomic directory
renames for prepare and cleanup so a missing journal under the formal backup
prefix is corruption and must be retained fail-closed.

## 2026-08-19 - Document Confirmed-Picks Evidence

Recorded the evidence schema, unchanged 10/8/9/3 rubric, exact DD-confirmed
allowlist, deterministic fallback, zero-pick semantics, shared ledger lock,
atomic replacement, cross-run serialization, verification commands, and the
remaining PR/deploy/natural-EOD release gates.

## 2026-08-19 - Specify Deterministic Score-Cap Enforcement

**Specification pattern:** Make the scoring order explicit as technical rubric
and cap, composite caps, regime multiplier, then verdict downgrades. Preserve
the LLM's original composite/verdict and closed risk-veto IDs so a genuine veto
is distinguishable from an ordinary low-score verdict.

**Traceability:** Seven requirements map to fail-first cap/downgrade tests, a
shared executable contract validator, workflow enforcement, full-suite checks,
and the remaining PR/deployment/7F 72/2/0 release gate. Weights, thresholds,
picks, ledger rows, and unsupported provider inferences remain out of scope.

## 2026-08-19 - Specify Social Ticker Provenance

**Specification pattern:** Replace an open-ended uppercase-word blocklist with
positive evidence: accumulated local-universe membership for plain tokens,
explicit provenance for cashtags, and independent or prior market validation
for legacy outcome tracking.

**Safety boundary:** Historical source snapshots remain immutable. Derived
outcomes record bounded skip receipts, while a transient quote failure retains
the exact last-known-good positive entry and returns.

**7F amendment:** A cashtag proves mention provenance, not market identity.
Outcome loading now requires universe, platform/retail, or prior positive-price
evidence; curated mention alone has the same fail-closed boundary.

## 2026-08-20 - Close Confirmed-Picks Release Evidence

Reconciled stale pending labels with actual PR, deployment, 7F, natural-EOD,
artifact-hash, Analytics, and ledger evidence. Added one durable release record
with requirement traceability and adversarial probes; updated confirmed-picks,
score-cap, social-ticker, and operator documents without changing runtime code
or report data.

## 2026-08-21 - Reconcile Validation Release State

Replaced six stale accepted/pending status labels with evidence-backed closure
states. Added one consolidated record that distinguishes PR #22's intentionally
skipped ordinary deploy from its real bounded 7F observer acceptance, links PRs
#18 and #23-#27 to successful deployments, and records current post-producer
continuity. The reconciliation is documentation-only and makes no runtime,
report, pick, ledger, scoring, or schedule change.

## 2026-08-21 - Close Stage 7 Natural Validation

Recorded the PR #33-#35 lineage, actual scheduled terminal, retained artifact
and file hashes, exact ledger/receipt no-op, 10/10 traceability, adversarial
probes, and current 7F continuity in one certified release record. Clarified
that the tracked Stage 7 receipt is the automatic-notifier authority while the
7F shared checks copy can lag because Data Health does not call the notifier.
The documentation-only closure does not change runtime code, workflows, data,
ledger rows, receipts, reports, picks, thresholds, weights, or schedules.

## 2026-08-21 - Specify Promotion Reachability Shadow Diagnostics

**Specification pattern:** Treat evidence reachability as a separate shadow
contract, not as an excuse to change scoring. Legacy cohorts remain unknown;
new cohorts carry per-dimension source maxima and unsupported-credit evidence.

**Review correction:** Adding a truthful Analytics warning changes the expected
check count. Record that operational delta explicitly instead of preserving a
stale 72/2/0 expectation by hiding the new condition.

**Apply when:** A natural zero-output streak may be caused by a structural
evidence ceiling below an unchanged production threshold.

## 2026-08-28 - Reconcile Natural-Validation Closure

Updated the recovery plan from stale pending language to evidence-backed
`CERTIFIED` closure. The record distinguishes an authoritative Stage 7
`PASS_NOOP` from an unobserved live collision, formally waives only the latter
as a blocking release criterion, and retains it as non-blocking operational
observation. Reusable rule: never translate a no-op into concurrency PASS;
record a bounded waiver, its evidence basis, and the condition that would reopen
the decision.
