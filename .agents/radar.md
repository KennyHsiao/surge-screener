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

## 2026-08-18 - Atomic Report and Analytics Failure Regressions

**Fail-first coverage:** The new tests first failed because preparation still
moved `current`, there was no already-locked Analytics seam, and producer/deadline
verdicts used a different payload. The repaired matrix covers strict gate
failure, DB commit failure after report-pointer promotion, prior and first-time
pointer rollback, producer failure, deadline, artifact failure, and Analytics
failure.

**Concurrency evidence:** A real `flock` contender models parallel Data Health
after the companion-promotion boundary and times out until the outer transaction
releases the shared lock. Byte assertions prove old DuckDB, Parquet, and checks
survive injected promotion failure together with the old report generation.

**Verification:** Transaction 8/8, observer 11/11, Data Health 9/9, deployment
contract 22/22, compile/whitespace gates, the complete `make test`, and a real
25-table/27-Parquet isolated Analytics build passed. Ruff was unavailable in
the project environment and was not counted.
## 2026-08-18 - Terminal-evidence Persistence Regressions

**Fail-first coverage:** PASS-verdict and succeeded-status single-write failures
both reproduced the old `current` non-restoration bug before implementation.
After the repair, each returns a canonical FAIL terminal, replaces any
provisional PASS, and restores exact old generation, DuckDB, Parquet, and checks
bytes.

**Verification:** Provisional backup retention is tested through explicit
commit. Focused transaction 9/9, observer 13/13, deployment 22/22, compile and
whitespace gates, complete `make test`, and a real 25-table/27-Parquet isolated
build pass. Ruff is unavailable and is not counted.

## 2026-08-18 - Process-crash and Restart Regressions

**Fail-first coverage:** A forked child exits without cleanup after provisional
promotion, separately after PASS verdict and after succeeded status. The next
lock owner restores exact old DB, Parquet, checks, and report pointer, replaces
partial success evidence with canonical FAIL, and leaves no backup residue.

**Edge coverage:** Tests prove the pending journal and complete backups precede
companion mutation, Data Health recovers before its next build, committed
cleanup never rolls back, pointer conflict leaves new state and backups
untouched, and a missing journal is retained fail-closed. Observer startup
recovers before constructing its GitHub client; systemd uses bounded
`Restart=on-abnormal`.

## 2026-08-19 - Confirmed-Picks Edge Coverage

Regression coverage now includes partial yfinance rows, missing-volume
fail-closed liquidity, malformed evidence, unsupported-pattern zero credit,
invented/duplicate report tickers, parallel ledger appends, schema migration,
injected replace failure, and a return update racing a new append.

**Verification:** Transaction 16/16, observer 14/14, deployment 23/23, complete
`make test`, compile/whitespace gates, and a real 25-table/27-Parquet isolated
build with zero BLOCK and zero residue pass locally.

## 2026-08-19 - Score-Cap and Veto Regressions

**Fail-first evidence:** The prior implementation failed on missing raw/cap
provenance, sentiment/options composite caps, two-dimension downgrade, stale DD
flags, ordinary low-score verdict classification, structured bearish-options
veto retention, and workflow contract presence.

**Mutation coverage:** The shared validator accepts a real finalized row, then
rejects altered composite, DD flag, original LLM score, unsupported veto ID, and
adjustment before-value. Tests are isolated, deterministic, network-free, and
clock-free. Focused scoring is 19/19, deployment contracts 25/25, compile/diff
gates pass, and the complete repository `make test` exits 0.

## 2026-08-19 - Social Ticker Eligibility Regressions

**Fail-first evidence:** Old code accepted arbitrary `THAT/TO/WHY`, scanned
successful stderr, lost cashtag provenance, and called yfinance for unverified
legacy rows. Review then reproduced loss of a prior positive entry when the
next quote was transiently unavailable.

**Coverage:** Tests prove universe-qualified plain tokens, off-universe
cashtags, stderr isolation, bounded skip receipts, no invalid price-loader call,
and exact prior-market-data retention. Focused suites are 14/14, 16/16, and 3/3;
deploy artifacts 25/25, compile/diff gates, and two complete test runs pass.
