# Post-producer atomic boundary remediation

Status: release verified on 7F on 2026-08-18; re-audited 2026-08-21.

## Intent

Make a post-producer refresh preserve the complete last-known-good state unless
the prepared report generation, strict Analytics build, semantic gate, report
pointer switch, DuckDB, Parquet, and checks evidence all promote successfully.
Producer failure, deadline expiry, artifact failure, and Analytics failure must
also emit the same terminal verdict schema.

This change does not create picks, relax weights, synthesize ledger rows, change
Analytics schemas, or begin the confirmed-picks/ledger work. That follow-up is
blocked until the deployed 7F refresh returns exactly 72 PASS / 2 WARN / 0 BLOCK.

## Affected files and callers

- `scripts/post_producer_analytics.py`: prepare/promotion separation, report
  pointer rollback, canonical verdicts, and one-lock observer orchestration.
- `scripts/analytics_refresh_transaction.py`: an explicit already-locked refresh
  seam and companion promotion rollback during Analytics promotion.
- `scripts/test_post_producer_analytics.py`: generation, terminal schema, full
  transaction, and concurrency regressions.
- `scripts/test_analytics_refresh_transaction.py`: promotion rollback regression.
- `docs/post-producer-analytics.md`: atomic boundary and operations contract.
- `.agents/{builder,radar,gear}.md` and `.agents/PROJECT.md`: implementation,
  test, and deployment evidence.

Existing Data Health and deployment callers keep using the lock-owning public
`staged_analytics_refresh`; only the post-producer observer uses the explicit
already-locked seam while it holds the same shared lock.

## Implementation sequence

1. Add fail-first tests proving preparation does not move `current`; producer,
   deadline, artifact, and Analytics terminals share one schema; gate failure
   preserves generation/DB/Parquet/checks; promotion failure restores all four;
   and a concurrent Data Health contender cannot enter the transaction.
2. Split immutable report preparation from pointer promotion and add a narrowly
   scoped rollback closure for the old pointer (including the no-old-pointer
   case).
3. Split Analytics refresh into a public lock-owning wrapper and an explicit
   locked core. Let the core run a companion promotion immediately before DB
   promotion and invoke its rollback if DB/Parquet/checks promotion fails.
4. Hold one `analytics-refresh.lock` across preparation, strict build/gate,
   `current` switch, and Analytics promotion in the post-producer observer.
5. Route every terminal outcome through `build_post_ingestion_verdict`, using
   stable empty/null fields when artifacts or Analytics evidence do not exist.
6. Run focused and complete local gates, inspect the diff for scope drift and
   defects, open and merge a PR, deploy normally, rerun on 7F, and require the
   exact 72/2/0 state plus aligned generation/database evidence.

## Verification

- `python3 scripts/test_analytics_refresh_transaction.py`
- `python3 scripts/test_post_producer_analytics.py`
- related Data Health/deployment test targets discovered from `Makefile`
- `python3 -m compileall` for changed Python files
- `git diff --check`
- complete `make test`
- PR checks and standard test-server deployment
- 7F service rerun, terminal verdict schema, current-generation manifest,
  DuckDB/checks identities, API/Streamlit health, and timer state

## Risks and rollback

- Risk: nested acquisition of the non-reentrant file lock. Mitigation: the
  observer exclusively calls the explicit locked core; all other callers keep
  the lock-owning wrapper.
- Risk: companion pointer rollback itself fails. Mitigation: keep the old
  immutable generation and run rollback before releasing the shared lock; a
  combined terminal failure is durable and the old state is never deleted.
- Risk: promotion ordering exposes a mixed report/Analytics state. Mitigation:
  switch only after the strict gate, immediately before Analytics promotion,
  while every Analytics writer is excluded by the shared lock.
- Rollback: revert the PR and redeploy. Retain `shared/published_reports`,
  `shared/data`, and Analytics checks; do not delete durable generations.

## Blocking review

- User intent coverage: PASS; all six requested items have an implementation
  seam and an explicit acceptance test.
- Files/callers/verification/risk areas known: PASS.
- Data-loss, credentials, destructive behavior, or out-of-scope mutation:
  PASS; no such action is planned.
- Unresolved blocker count: 0. Implementation is authorized.

## Release closure

- PR [#25](https://github.com/KennyHsiao/surge-screener/pull/25) merged as
  `c6ca2160687b8d27ecc6be4f54b8e7fbbbb6e44f`; deployment run
  [32108430625](https://github.com/KennyHsiao/surge-screener/actions/runs/32108430625)
  succeeded.
- The 7F terminal history captured a PASS promotion at
  `2026-08-18T06:49:13Z` for fixed source `c6ca216`, with exactly
  `72 PASS / 2 WARN / 0 BLOCK`, the `2026-08-17` 25-row candidate cohort, and
  aligned generation and database evidence.
- Subsequent terminal-evidence and crash-recovery releases preserve this
  shared-lock boundary. Consolidated evidence is in
  `docs/validation-release-state-evidence-2026-08-21.md`.
