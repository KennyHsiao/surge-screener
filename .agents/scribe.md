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

**Acceptance gate:** Two fail-first persistence injections must restore the
exact old generation, DuckDB, Parquet, and checks. PR deployment and a fresh 7F
72 PASS / 2 WARN / 0 BLOCK result remain mandatory before confirmed-picks /
ledger work can begin.

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
