# Natural Validation Recovery Plan

Status: IMPLEMENTED AND LOCALLY VERIFIED; PR/DEPLOY/NATURAL GATES PENDING

## Goal

Close the three failures observed on 2026-08-27 without fabricating a natural
PASS: recover a late scheduled EOD generation under its logical schedule date,
remove the remaining simple dirty-worktree publishers, and persist Analytics
checks with canonical promoted paths.

## Scope

1. Derive the scheduled EOD report date from the `30 22 * * 1-5` logical slot,
   not the delayed runner wall clock. Manual EOD runs retain the current UTC
   date.
2. Keep 10:30 Asia/Taipei as the natural-validation SLA. Continue bounded,
   read-only producer observation until 16:30 so a late successful producer can
   be ingested once. The terminal schema must distinguish `ON_TIME`,
   `RECOVERED_LATE`, and `FAILED` timing; a late recovery is never presented as
   an on-time PASS.
3. Migrate the report writers (`candidate_outcomes`, reflection, retrospective,
   crypto, options flow, reversal radar, and oversold lane) to
   `scripts/publish_reports.py` with explicit paths and runtime-output stashing.
   Retrospective keeps its conditional knowledge-sync gate but delegates the
   final commit/rebase/push operation to the shared publisher. Keep only the
   Market Thesis revalidation transaction as an explicit specialized writer.
4. Rewrite only Analytics evidence path provenance from the staged root to the
   canonical promoted root before checks are copied. The staged data and gates
   remain unchanged.
5. Repair the existing four-decimal Oversold validation boundary discovered by
   the full gate: an exact half-unit rounding difference must not fail because
   of binary floating-point representation.

## Acceptance Criteria

- A scheduled EOD run delayed across UTC midnight still emits artifacts for the
  original logical report date.
- At 10:30 a pending producer is recorded as an SLA miss, observation continues
  to 16:30, and a later success produces a terminal `PASS` with
  `timeliness.state=RECOVERED_LATE` and the original missed deadline retained.
- A producer absent at the recovery deadline remains terminal `FAIL`; all
  transaction rollback guarantees remain unchanged.
- `candidate_outcomes` survives a concurrent main update with dirty runtime
  outputs, publishes only its allowlisted reports, and records
  `push_race_observed=true`.
- The seven migrated writers contain no inline `git push`/`git pull --rebase`
  loops; only the specialized Market Thesis transaction retains one.
- Persisted Analytics `analytics_root`, `duckdb_path`, and path-bearing check
  evidence reference `shared/data`, with no deleted `.analytics-staging-*`
  path.
- Focused tests, workflow/YAML checks, Python compilation, `git diff --check`,
  and the complete `make test` gate pass.

## Risks and Controls

- Late recovery must not erase the SLA miss: timing is part of the canonical
  terminal evidence.
- Logical-date calculation is schedule-specific and rejects unsupported cron
  values instead of guessing.
- Fixed-SHA artifact reads, the shared Analytics lock, provisional promotion,
  rollback backups, PASS verdict, and succeeded status remain one transaction.
- No workflow is manually dispatched and no picks, weights, thresholds, or
  ledger rows are changed during implementation or deployment verification.

## Verification

- `python scripts/test_scheduled_report_date.py`
- `python scripts/test_post_producer_analytics.py`
- `python scripts/test_analytics_refresh_transaction.py`
- `python scripts/test_publish_reports.py`
- `python scripts/test_deploy_artifacts.py`
- YAML parse and `python -m py_compile` for changed Python files
- `git diff --check`
- `make test`
