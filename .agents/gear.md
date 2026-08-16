# Gear Journal

## 2026-08-16 - Race-Safe Report Publication

**Implementation pattern:** Stage and commit only `reports/`, upload diagnostics
before cleanup, and allow runtime-output stashing only behind an explicit
discard-runtime-outputs flag. Drop only the exact publisher-owned stash on both
success and failure. Use an explicit fetch/rebase/push loop with a bounded
attempt count and fail non-zero on conflicts or exhaustion.

**Verification insight:** A temporary bare remote can deterministically model a
concurrent writer. Cover successful retry, conflicting report edits, and refusal
to stash a developer's dirty local outputs; assert that runtime files never
enter the report commit.

**Apply when:** A CI producer writes generated artifacts back to a shared branch
while sibling jobs may advance that branch.
