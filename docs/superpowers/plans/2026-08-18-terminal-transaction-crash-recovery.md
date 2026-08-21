# Terminal Transaction Crash-Recovery Implementation Checklist

## Document Info

| Field | Value |
|---|---|
| Version | v0.1 |
| Status | Implemented; release validation pending |
| Author | Codex |
| Reviewer | Post-deploy Judge gate |
| Audience | surge-screener maintainers and operators |
| Related change | PR #26 / `main@9e07c7e` |

## Scope

Close the process-crash window left after PR #26. A provisional report and
Analytics promotion must be recoverable after Python termination, SIGKILL, or
host restart until a durable commit marker exists.

In scope:

- a durable transaction journal written before the first canonical mutation;
- idempotent recovery while holding `analytics-refresh.lock`;
- exact recovery of DuckDB, Parquet, Analytics checks, and report `current`;
- fail-closed replacement of partial PASS/succeeded terminal evidence;
- cleanup-only recovery after a durable commit marker;
- deterministic crash/restart regression tests;
- systemd restart on abnormal termination, without looping terminal FAIL exits.

Out of scope:

- changing scoring weights, thresholds, or market rules;
- manufacturing or backfilling confirmed picks;
- changing performance-ledger contents;
- starting the scoring-evidence implementation before this gate passes.

## Glossary

- **Pending journal**: durable record proving a promotion may need rollback.
- **Commit marker**: journal state durably changed to `committed` after PASS
  verdict and succeeded status are durable.
- **Abandoned transaction**: pending journal found by a later lock owner.
- **Last-known-good**: canonical DB, Parquet, checks, and report pointer that
  existed before the abandoned promotion.

## Requirements

- `REQ-TCR-001`: The process MUST fsync a pending journal before changing
  `current`, DuckDB, Parquet, or checks.
- `REQ-TCR-002`: Every Analytics writer MUST recover or reject an abandoned
  journal while holding the shared writer lock and before building a new run.
- `REQ-TCR-003`: Recovery MUST be idempotent and MUST retain backups until all
  four canonical artifacts are restored.
- `REQ-TCR-004`: PASS verdict and succeeded status MUST be durable before the
  journal receives a durable `committed` marker.
- `REQ-TCR-005`: A committed journal found after restart MUST preserve the new
  state and perform cleanup only.
- `REQ-TCR-006`: Post-producer recovery MUST replace partial success evidence
  with the canonical FAIL/status schema and a crash-recovery reason.
- `CFR-TCR-001`: No test may require network access, wall-clock sleeps, or
  mutation of production reports.

## Acceptance Criteria

### AC-TCR-001 — Pending journal precedes mutation

Given old DB, Parquet, checks, and current generation, when promotion begins,
then a fsynced pending journal and complete rollback backup exist before any
canonical target changes.

### AC-TCR-002 — Abandoned provisional promotion rolls back

Given a subprocess exits without commit after provisional promotion, when the
next writer acquires the lock, then DB, Parquet, checks, and current equal the
exact old bytes/target and no pending backup remains.

### AC-TCR-003 — Partial success evidence fails closed

Given a subprocess exits after PASS verdict or succeeded status persistence but
before the commit marker, when recovery runs, then canonical data rolls back and
verdict/status use the canonical failure schema with a recovery reason.

### AC-TCR-004 — Committed cleanup never rolls back

Given the commit marker is durable but backup cleanup was interrupted, when
recovery runs, then the new canonical state remains and only residue is removed.

### AC-TCR-005 — Recovery conflict fails without clobbering

Given `current` points to neither the recorded old nor promoted generation,
when recovery runs, then it raises an actionable error and preserves every
backup for manual recovery.

### AC-TCR-006 — Operational restart

Given the observer exits from a signal or timeout, when systemd evaluates the
service, then `Restart=on-abnormal` starts recovery without looping deliberate
terminal FAIL exits or waiting for the next timer.

## Implementation Checklist

- [x] `IMPL-TCR-001`: Add a versioned, fsynced recovery journal and validated
  parser in `scripts/analytics_refresh_transaction.py`.
- [x] `IMPL-TCR-002`: Make DB/checks/Parquet rollback repeatable without
  consuming the sole backup before recovery completes.
- [x] `IMPL-TCR-003`: Persist serializable report-pointer old/new targets and
  restore them safely during abandoned-transaction recovery.
- [x] `IMPL-TCR-004`: Mark committed durably before deleting rollback assets.
- [x] `IMPL-TCR-005`: Invoke recovery under the shared lock before every
  Analytics promotion.
- [x] `IMPL-TCR-006`: Publish canonical crash-recovery FAIL evidence for an
  abandoned post-producer transaction.
- [x] `IMPL-TCR-007`: Add `Restart=on-abnormal` with a bounded restart delay to
  the post-producer systemd unit.
- [x] `IMPL-TCR-008`: Update operator documentation and agent journals; append
  release evidence after deployment.

## Test Specification

| Test ID | Requirement | Verification |
|---|---|---|
| `TEST-TCR-001` | `REQ-TCR-001` | Inspect pending journal/backups before mutation and assert exact old bytes. |
| `TEST-TCR-002` | `REQ-TCR-002/003` | Abandon provisional transaction, recover twice, assert exact old state both times. |
| `TEST-TCR-003` | `REQ-TCR-004/006` | Persist PASS only, recover, assert canonical FAIL and exact old state. |
| `TEST-TCR-004` | `REQ-TCR-004/006` | Persist PASS+succeeded without commit, recover, assert canonical FAIL and exact old state. |
| `TEST-TCR-005` | `REQ-TCR-005` | Interrupt cleanup after commit marker, recover, assert new state retained. |
| `TEST-TCR-006` | `REQ-TCR-002` | Run Data Health/post-producer contention test with abandoned journal. |
| `TEST-TCR-007` | `REQ-TCR-002` | Inject conflicting current pointer, assert fail-closed and retained backup. |
| `TEST-TCR-008` | `REQ-TCR-006` | Validate active systemd restart directives. |

## Risks and Rollback

- Journal corruption: fail closed, retain backup, and emit the journal path.
- Disk-full during recovery: do not delete backups; retry remains possible.
- Pointer conflict: never guess the previous generation.
- Rollback: revert the PR and restore the retained backup under the shared lock.

## Verification Commands

```bash
.venv/bin/python scripts/test_analytics_refresh_transaction.py
.venv/bin/python scripts/test_post_producer_analytics.py
.venv/bin/python scripts/test_deploy_artifacts.py
make PY=.venv/bin/python test
```

## Traceability Matrix

| Requirement | Acceptance | Implementation | Tests |
|---|---|---|---|
| `REQ-TCR-001` | `AC-TCR-001` | `IMPL-TCR-001` | `TEST-TCR-001` |
| `REQ-TCR-002` | `AC-TCR-002/005` | `IMPL-TCR-003/005` | `TEST-TCR-002/006/007` |
| `REQ-TCR-003` | `AC-TCR-002` | `IMPL-TCR-002` | `TEST-TCR-002` |
| `REQ-TCR-004` | `AC-TCR-003` | `IMPL-TCR-004/006` | `TEST-TCR-003/004` |
| `REQ-TCR-005` | `AC-TCR-004` | `IMPL-TCR-004` | `TEST-TCR-005` |
| `REQ-TCR-006` | `AC-TCR-003` | `IMPL-TCR-006/007` | `TEST-TCR-003/004/008` |

## Blocker Review

- Scope covers the reproduced crash window: PASS.
- Affected files and callers are known: PASS.
- Rollback and conflict behavior are explicit: PASS.
- Verification is deterministic and offline: PASS.
- Unresolved blocking questions: none.

## Change History

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-18 | Initial crash-recovery remediation plan. |
| v0.2 | 2026-08-18 | Implemented durable prepare/pending/commit/rollback states, atomic cleanup naming, startup recovery, abnormal-only restart, and deterministic crash tests; PR/7F gates remain. |

## Local Verification Evidence

- Transaction regression: `16/16` PASS, including separate process exits after
  PASS verdict and succeeded status, next-writer recovery, committed cleanup,
  pointer conflict, and corrupt-journal retention.
- Post-producer observer regression: `14/14` PASS.
- Deployment artifact regression: `23/23` PASS.
- Complete `make test`: PASS using the absolute repository virtualenv path.
- Real isolated Analytics build: 25 tables, 27 Parquet files, 0 BLOCK, and no
  backup residue after commit.
- Python compile, `git diff --check`: PASS.
