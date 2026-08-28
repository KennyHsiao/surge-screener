# Natural Validation Recovery Plan

Status: COMPLETE — CERTIFIED ON 2026-08-28

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

## Closure Evidence (2026-08-28)

Final verdict: `CERTIFIED`. All acceptance criteria and blocking release gates
in this plan are complete.

- PR [#48](https://github.com/KennyHsiao/surge-screener/pull/48) was squash
  merged as `c0826de74209fa1e8e391ce3787551383df50b81`. Deployment run
  [33056997054](https://github.com/KennyHsiao/surge-screener/actions/runs/33056997054)
  completed successfully.
- The delayed scheduled EOD run
  [33147141016](https://github.com/KennyHsiao/surge-screener/actions/runs/33147141016)
  retained logical report date `2026-08-27`, completed successfully at
  `2026-08-28T07:02:06Z`, and published source SHA
  `6095073a3178dcca6f49d4ee3d42a2d61e577645`.
- The 7F post-ingestion transaction promoted generation
  `2026-08-27-6095073a3178-3267723b` and persisted terminal
  `PASS/succeeded` with `timeliness.state=RECOVERED_LATE`. The original
  `2026-08-28T02:30:00Z` SLA miss remains recorded; completion occurred at
  `2026-08-28T07:03:14Z`, before the `2026-08-28T08:30:00Z` recovery
  deadline.
- Authoritative Analytics is `72 PASS / 3 WARN / 0 BLOCK`. Its root and
  DuckDB path are canonical under `shared/data`, the verdict DB hash
  `f6cc554d0ea024424e4aca44758cd2ee697418dd5a2ae9ba4cd9c914318f8fbd`
  matches the live database, and no transaction residue remains.
- The EOD publisher encountered a real concurrent main update and recovered
  with `attempts=2`, `push_race_observed=true`, and
  `runtime_stashed=true`. Scheduled candidate-outcomes run
  [33149988804](https://github.com/KennyHsiao/surge-screener/actions/runs/33149988804)
  independently exercised the same live retry path and published only
  `reports/candidate_outcomes/` and `reports/candidate_rankings/` with
  `attempts=2`, `push_race_observed=true`, and `runtime_stashed=true`.
- API `/healthz`, Streamlit `/_stcore/health`, the four scheduled timers,
  deployed runtime hashes, and the final post-ingestion state were healthy
  after the candidate-outcomes deployment.

### Stage 7 Live-Race Disposition

Scheduled Stage 7 run
[33123632019](https://github.com/KennyHsiao/surge-screener/actions/runs/33123632019)
is an authoritative `PASS_NOOP`: it had no eligible ledger or receipt change,
so publication correctly recorded `attempts=0`,
`push_race_observed=false`, and `status=nothing_to_commit`. This is not
presented as a Stage 7 live-race PASS.

The repository owner authorizes a formal waiver of a Stage 7-specific live
collision as a blocking release criterion. It remains a non-blocking,
opportunistic production observation because:

1. deterministic Stage 7 concurrency and failure regressions already cover the
   exact publication contract;
2. the shared publisher's live retry path is now demonstrated by both EOD and
   candidate-outcomes scheduled producers; and
3. forcing a Stage 7 update or mutating the ledger to manufacture a collision
   would invalidate the natural-evidence boundary.

A future non-noop Stage 7 run must continue recording its normal terminal
evidence. Its absence does not reopen this completed plan; only a future
contract or safety failure does. This documentation reconciliation changes no
runtime code, workflow, report, pick, ledger row, score, weight, threshold,
provider, credential, API/DB schema, or schedule. The ordinary deployment
triggered by merging this docs-only reconciliation must preserve the terminal
generation, database, and Analytics evidence recorded above.
