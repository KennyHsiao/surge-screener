# Radar Journal

## 2026-08-16 - Analytics State and Race Regressions

**Test design:** Exercise state transitions, not only row counts. No-picks tests
separate valid zero-pick reports, reports with picks, malformed/future reports,
and calendar gaps. Optional-source tests preserve configured-but-empty runs via
source observations instead of inferring availability from data rows.

**Race design:** Use real temporary Git repositories and a bare remote to prove
both the retry success path and the rebase-conflict abort path. Include dirty
tracked and untracked runtime outputs to catch accidental publication leakage.

**TDD result:** New cases failed against the prior behavior, then passed after
implementation. Focused suites pass 152/152 and the complete repository suite
passes.
