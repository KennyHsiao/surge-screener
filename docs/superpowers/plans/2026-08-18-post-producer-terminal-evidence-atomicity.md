# Implementation checklist: post-producer terminal evidence atomicity

## Document info

| Field | Value |
| --- | --- |
| Version | v1.0 |
| Status | Release verified on 7F on 2026-08-18; re-audited 2026-08-21 |
| Author | Codex |
| Audience | Analytics maintainers and 7F operators |
| Related design | `2026-08-18-post-producer-atomic-boundary-remediation.md` |

## Scope

Extend the post-producer last-known-good transaction through durable PASS
verdict and terminal-status publication. A failure in either evidence write
must restore the prior report generation, DuckDB, Parquet, and Analytics
checks before the shared writer lock is released.

Non-goals: changing Analytics schemas, creating picks or ledger rows, relaxing
weights or gates, changing producer schedules, or beginning confirmed-picks /
ledger work before the 7F acceptance gate passes.

## Glossary

- **Provisional promotion**: new report and Analytics state visible only while
  rollback backups remain available under the shared writer lock.
- **Commit**: disposal of rollback backups after both PASS evidence files are
  durably replaced.
- **Terminal evidence**: `shared/post_ingestion/latest.json` and
  `shared/run_status/post-producer-analytics.json`.

## Requirements and acceptance criteria

- **AC-ATE-001 (CRITICAL)**: The shared transaction MUST remain open until the
  PASS verdict and succeeded status are durably replaced.
  - Given a successful strict Analytics gate, when both evidence writes finish,
    then the new generation and Analytics outputs remain current and rollback
    backups are finalized.
- **AC-ATE-002 (CRITICAL)**: Rollback material MUST remain available between
  Analytics promotion and terminal evidence commit.
  - Given provisional promotion, when the caller has not committed, then an
    explicit rollback restores the exact previous DB, Parquet, checks, and
    companion report pointer.
- **AC-ATE-003 (CRITICAL)**: PASS-verdict persistence failure MUST restore the
  complete last-known-good state before releasing the shared lock.
  - Given old generation/DB/Parquet/checks bytes, when the PASS verdict write
    fails once, then the observer returns failure, emits a canonical FAIL
    verdict, and all four old states are exact.
- **AC-ATE-004 (CRITICAL)**: succeeded-status persistence failure MUST have the
  same rollback result and terminal schema as AC-ATE-003.
  - Given the PASS verdict was replaced, when the succeeded status write fails
    once, then the provisional promotion rolls back and the PASS verdict is
    replaced by a canonical FAIL verdict.
- **AC-ATE-005 (CRITICAL)**: confirmed-picks / ledger work MUST remain blocked
  until the merged deployment produces exactly 72 PASS / 2 WARN / 0 BLOCK on
  7F with aligned generation, database, and terminal evidence.

## Affected files and callers

- `scripts/analytics_refresh_transaction.py`: add an explicit provisional
  promotion lifecycle with commit and rollback; preserve immediate-commit
  behavior for existing Data Health and deployment callers.
- `scripts/post_producer_analytics.py`: write PASS verdict and status inside the
  shared lock while the provisional lifecycle is active; make JSON replacement
  durable at the containing-directory boundary.
- `scripts/test_analytics_refresh_transaction.py`: verify deferred backup
  retention, explicit commit, and exact rollback.
- `scripts/test_post_producer_analytics.py`: add fail-first PASS-verdict and
  succeeded-status persistence fault injections with exact state assertions.
- `docs/post-producer-analytics.md`: document the extended commit point and
  evidence-failure recovery.
- Skill journals and `.agents/PROJECT.md`: record implementation and evidence.

Existing `staged_analytics_refresh` callers keep an immediate-commit mapping
result. Only the post-producer observer uses the new explicit provisional seam.

## Implementation sequence

1. Add the two observer fault-injection regressions and prove they fail on
   `c6ca216` for the expected non-restoration reason.
2. Refactor Analytics promotion so successful replacement returns a lifecycle
   retaining old DB, Parquet, and checks until `commit()`; make `rollback()`
   exact and idempotence-guarded.
3. Add an already-locked provisional refresh API that combines Analytics
   rollback with the report-pointer rollback. Keep the existing API as an
   immediate-commit wrapper.
4. Move PASS verdict and succeeded-status writes inside the shared lock and
   lifecycle. Commit only after both replacements and their parent directories
   are fsynced. On either exception, roll back before the lock exits, then emit
   the canonical FAIL terminal evidence.
5. Run focused tests, compile/diff gates, the relevant deploy contract suite,
   a real isolated Analytics build, and complete `make test`.
6. Review the actual diff against this checklist, fix blocking findings, open
   a draft PR, make it review-ready after checks pass, merge, and deploy main.
7. Rerun post-producer ingestion on 7F and require 72/2/0 plus exact generation,
   DB, Parquet/checks, API/UI, service, and timer evidence before unblocking the
   confirmed-picks / ledger plan.

## Verification commands

- `python3 scripts/test_analytics_refresh_transaction.py`
- `python3 scripts/test_post_producer_analytics.py`
- `python3 scripts/test_deploy_artifacts.py`
- `python3 -m compileall scripts/analytics_refresh_transaction.py scripts/post_producer_analytics.py scripts/test_analytics_refresh_transaction.py scripts/test_post_producer_analytics.py`
- `git diff --check`
- `make test`
- Existing isolated real-build command from the prior transaction plan
- GitHub PR checks and standard test-server deployment
- 7F post-producer service rerun and exact `72 / 2 / 0` evidence inspection

## Risks and rollback

- A caller could forget to settle a provisional promotion. The explicit
  lifecycle context rolls back on exception or uncommitted exit.
- A rollback step could itself fail. Aggregate every rollback error, retain the
  backup directory, fail closed, and expose the path in the service journal.
- Two JSON files cannot be replaced by one filesystem rename. Treat their
  publication as provisional: any second-write failure rolls back data and
  overwrites the first PASS evidence with the canonical FAIL payload.
- Directory fsync support can vary. Use the existing Linux/macOS-compatible
  directory descriptor pattern and propagate failures inside the transaction.
- Operational rollback is a normal PR revert and redeploy. Never delete
  `shared/published_reports`, `shared/data`, or retained failure backups.

## Pre-implementation blocking review

- User intent coverage: PASS; all five requested outcomes map to ACs and tests.
- Affected files, callers, verification, and rollback are known: PASS.
- Backward compatibility for Data Health callers: PASS through the unchanged
  immediate-commit public API.
- Data loss, credentials, destructive behavior, or scope expansion: PASS; none
  is required.
- Unresolved blocking issues: 0.

The explicit user request accepts this plan for execution.

## Release closure

- PR [#26](https://github.com/KennyHsiao/surge-screener/pull/26) merged as
  `9e07c7edd2328a0b1c7f936497f587484c2b8677`; deployment run
  [32112857402](https://github.com/KennyHsiao/surge-screener/actions/runs/32112857402)
  succeeded.
- The 7F post-producer history contains the immutable generation
  `2026-08-17-9e07c7edd232-08364dfc` and a matching PASS terminal with exactly
  `72 PASS / 2 WARN / 0 BLOCK` after durable verdict/status publication.
- The later crash-recovery release extended, rather than replaced, this commit
  boundary. Consolidated evidence is in
  `docs/validation-release-state-evidence-2026-08-21.md`.
