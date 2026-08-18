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

## 2026-08-18 - Post-producer Failure Matrix

**Fail-first coverage:** Tests began with both production modules absent, then
covered late producer success, terminal producer failure, successful but
unpublished output, a moving `main` with fixed-SHA downloads, allowlist contract
failure, exact evidence, and zero-pick classification.

**Concurrency and recovery:** Real `flock` contention proves writers serialize.
Injected refresh, check, and semantic-gate failures prove the previous DB and
Parquet bytes remain unchanged; success proves the new DB, checks, hashes, and
table evidence promote together. A real 25-table staged dry run and the complete
repository test target pass.

## 2026-08-18 - Overlay Import-Context Regression

**Fail-first coverage:** The overlay test now creates the sibling manual
watchlist and ranked-candidate fallback, then reads both through
`overlay.parent`. It failed before the hotfix and passes afterward. A real
isolated staged build additionally produces eight `watchlist_sources` rows and
PASS results for existence, row count, and manual-freshness semantics.
