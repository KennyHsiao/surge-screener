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
