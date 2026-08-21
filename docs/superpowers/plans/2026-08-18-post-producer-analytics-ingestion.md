# Post-producer Analytics ingestion plan

Status: RELEASE VERIFIED — PRs #23-#24 deployed and accepted on 7F; re-audited 2026-08-21

## Goal

Restore the 7F environment to the correct 2026-08-17 producer state first, then make report ingestion and Analytics refresh run from producer terminal states on 7F without depending on a later application deployment, this laptop, or the 7F VPN remaining connected.

## Required order

1. Phase A: recover today's correct state and record evidence.
2. Phase B: add the permanent producer-terminal ingestion path and regression tests.
3. Deploy the permanent fix, rerun the gates on 7F, remove the one-time observer timer, and record the final verdict.

Phase B must not start unless Phase A has either passed or has a concrete blocker recorded. Final completion requires both phases and the post-deployment revalidation to pass.

## Scope and non-goals

In scope:

- Safely synchronize the current remote `main` to 7F.
- Rebuild Analytics after the 2026-08-17 report artifacts are present.
- Synchronize allowlisted Git-published report artifacts into durable 7F shared storage.
- Trigger the synchronization and refresh from actual producer terminal states.
- Serialize Analytics writers and preserve the last known-good Analytics state on failure.
- Publish detailed post-ingestion evidence and regression tests.
- Clean up the one-time validation timer after final acceptance.

Explicit non-goals:

- Do not invent or backfill picks.
- Do not change scoring weights or relax any gate.
- Do not fabricate ledger history or Market Thesis provenance.
- Do not broaden the report allowlist without a contract and test.
- Do not modify the user's original dirty worktree.

## Phase A — restore the 2026-08-17 state

### Preflight

- Confirm the remote `main` SHA and verify the expected report artifacts exist there.
- Confirm there is no active deploy or overlapping Analytics writer.
- Confirm 7F clock, disk, runner, API, Streamlit, GitHub access, and the deployment freeze state.
- Capture the currently deployed SHA and the pre-recovery Analytics status.

### Recovery

- Dispatch the existing formal deployment workflow for remote `main` with source refresh disabled.
- Verify the deployment completed successfully and 7F files match the deployed SHA.
- Start the existing Data Health service on 7F and wait for its real terminal state.

### Acceptance gates

The recovered 7F state must satisfy all of the following:

- `candidate_scores >= 25` for 2026-08-17.
- latest Market Thesis date is 2026-08-17 with correct provenance.
- latest daily report date is 2026-08-17.
- `no-picks` is 15 or a later truthful count, with no regression.
- portfolio is `not_configured`.
- Risk Guard date/provenance checks pass.
- Analytics has zero BLOCK findings.
- Remaining WARN findings, if any, are evidence-backed and unrelated to missing ingestion.

## Phase B — permanent fix

### Design

- Add a 7F-local post-producer service and timer. The timer only starts observation; readiness is determined from actual terminal producer runs, not nominal schedule times.
- Resolve one immutable remote `main` SHA after the required producer jobs finish.
- Download only allowlisted report families for the report date into a staging directory, validate JSON contracts and hashes, then atomically promote them into durable `shared/published_reports` storage with a manifest.
- Layer the durable published-report root over the release report root for Analytics imports, with the published artifact winning for the same logical report.
- Use one exclusive Analytics refresh lock for Data Health and post-producer refreshes.
- Before an in-place Analytics refresh, preserve a recoverable last-known-good snapshot; restore it if refresh or checks fail.
- Write a `post_ingestion` verdict containing producer run IDs/conclusions, fixed main SHA, artifact paths and SHA-256 values, selected Analytics check details, DB identity, timestamps, and failure reason.
- Fail closed when a required producer fails, is unpublished, exceeds the observation deadline, or an artifact does not match its contract.

### Expected affected areas

- `.github/workflows/` only if a contract or deployment hook is required.
- `deploy/` systemd service/timer definitions.
- `scripts/deploy_test_server.sh` for durable directories, installed units, and environment wiring.
- `scripts/data_source_refresh.py` and `scripts/analytics_store.py` for shared layering and writer serialization.
- A new post-producer orchestration/synchronization module under `scripts/`.
- `scripts/natural_validation_observer.py` for complete ingestion evidence.
- Focused unit/contract tests plus `Makefile` test registration.
- Operations and validation documentation.

The exact diff may be narrowed after fail-first tests expose the smallest valid seam. Any wider change requires an explicit reason in the final diff review.

### Required regression matrix

- producer completes late but succeeds;
- producer fails;
- producer succeeds but required artifact is not published;
- remote `main` advances during synchronization while the fixed SHA remains stable;
- concurrent Data Health/post-ingestion writers serialize on the same lock;
- Analytics refresh/check failure restores the last known-good state;
- a producer `GITHUB_TOKEN` push does not have to trigger deployment for ingestion to work;
- verdict evidence contains exact producer IDs, source SHA, artifact hashes, check values, and DB identity;
- successful zero-pick, missing run, failed run, and unpublished report remain distinct states.

## Verification

1. Run new tests fail-first before implementation.
2. Run the focused post-producer, Analytics, observer, and deployment contract tests.
3. Run the repository's relevant full test target and static/syntax checks.
4. Compare the final diff with this plan and inspect it for runtime errors, unsafe file replacement, credential leakage, regression risk, and maintainability.
5. Deploy through the repository's formal workflow.
6. On 7F, exercise or observe the new post-ingestion path and rerun the Phase A acceptance gates.
7. Remove/disable the one-time observer timer and record a formal PASS/FAIL artifact.

## Rollback

- Phase A rollback: redeploy the previously recorded known-good SHA if the formal deployment fails health checks.
- Phase B rollback: revert the permanent-fix commit and redeploy; durable published reports and the last-known-good Analytics snapshot remain recoverable.
- Never delete shared data until the replacement has passed validation and its backup is identifiable.

## Blocking review

Review 1:

- User request coverage: complete; A precedes B and final revalidation is mandatory.
- Affected files and checks: known at the subsystem level; Phase B exact seams will be pinned by fail-first tests.
- Risk areas: concurrent writers, partial artifact promotion, stale SHA selection, large Analytics state rollback, and false-positive terminal detection are explicitly covered.
- Unresolved blocker: none. The existing formal deploy and Data Health service provide a reversible Phase A path.

Review 2 (after Phase A, before Phase B):

- Phase A deployment: PASS, workflow run `32090430868`, fixed SHA `bc2f0b4eeb35b43ba853156d96aa66b0662e91c5`; deployed report and code hashes matched the Git tree.
- Phase A Data Health: PASS, 2026-08-18 10:04:12–10:50:22 Asia/Taipei, systemd result `success/0`.
- Phase A Analytics: `72 PASS / 2 WARN / 0 BLOCK`; candidate scores 25 at 2026-08-17, Market Thesis 2026-08-17, daily report 2026-08-17, truthful zero-pick scans 15, portfolio `not_configured`.
- Risk Guard: generated during this run, observed on 2026-08-18 from `live_yfinance`; the absent scored-regime date is explicitly classified as `stale_scored_regime` rather than silently reused.
- Expected remaining warnings: stale performance ledger and 15 successful published zero-pick scans. No picks or ledger rows were fabricated.
- Separate non-blocking lane: playbook validation remains blocked because its decision corpus is not configured; it does not block Analytics publication or this ingestion fix.
- Newly observed non-blocking data-quality debt: the core source refresh attempted several prose-like symbols. Source status and all acceptance gates still passed; correcting ticker extraction is outside the accepted post-ingestion scope.
- Permanent-fix seams confirmed: a shared lock can serialize writers; an overlay tree can layer the durable mirror without copying the release; a same-filesystem staging Analytics root can be checked before atomically replacing the materialized DuckDB.
- Unresolved blocker: none. Proceed to fail-first tests and Phase B implementation.

Review 3 is required immediately before final deployment. A repeated unresolved blocker on all three reviews stops execution.

Review 3 (before final deployment):

- Plan/diff alignment: all changes map to durable report synchronization, writer serialization, staged Analytics promotion, evidence, deployment, tests, or operations documentation. No unexplained scope drift remains.
- Runtime safety: both Data Health and post-producer refresh now build/check in staging; injected refresh, checks, and semantic-gate failures preserve exact last-known-good DB and Parquet bytes.
- Concurrency: report-generation switching and Analytics promotion use the same 7F flock as Data Health; a real contention regression passes.
- Producer correctness: readiness uses actual non-skipped job identities and Theme terminal evidence; delayed, failed, missing/unpublished, fixed-SHA, and zero-pick cases are covered.
- Security: the service uses the public GitHub read API, records no environment secrets, constrains paths to a fixed allowlist/generation root, and repository secret-pattern scan is clean.
- Verification: focused suites pass; shell/Python/diff gates pass; a real 25-table staged refresh passes; complete `make test` exits zero. `ruff` and local `systemd-analyze` are unavailable, so Linux unit verification is required on 7F before final acceptance.
- Unresolved blocker: none. Proceed with commit, PR, merge, formal deployment, Linux systemd verification, post-ingestion execution, final 7F gates, and one-time timer cleanup.

Review 4 (hotfix review before final redeployment):

- First Phase B runtime review found one blocking regression: the report overlay
  changed `reports.parent`, hiding the release's sibling manual watchlist and
  ranked-candidate fallback from existing Analytics importers.
- The hotfix preserves those two immutable siblings beside the temporary report
  union without changing importer contracts or durable data.
- The regression failed before the fix and now passes. All focused suites and
  complete `make test` pass; a real isolated staged build produces eight
  `watchlist_sources` rows and PASS for its existence, row-count, and
  manual-freshness checks.
- Actual hotfix scope is only overlay construction, its test, this review, and
  engineering journals. Diff, Python syntax, and secret-pattern gates pass.
- At this historical checkpoint the unresolved blocker was none locally; the
  remaining acceptance actions were formal deployment, restoration of the 7F
  whole-Analytics baseline to exactly `72 PASS / 2 WARN / 0 BLOCK`, timer
  cleanup, and closure. The release-closure section below records their result.

## Release closure

- PR [#23](https://github.com/KennyHsiao/surge-screener/pull/23) merged as
  `24d972ede32e24857f7bb9d9d90d9192eede2732`; deployment run
  [32094624511](https://github.com/KennyHsiao/surge-screener/actions/runs/32094624511)
  succeeded.
- The overlay compatibility hotfix PR
  [#24](https://github.com/KennyHsiao/surge-screener/pull/24) merged as
  `ac1192d2d1afaa05a5ebd6da1e87f2e8cbf5ce43`; deployment run
  [32095197024](https://github.com/KennyHsiao/surge-screener/actions/runs/32095197024)
  succeeded.
- The 7F terminal history then recorded `72 PASS / 2 WARN / 0 BLOCK`, 25
  candidate rows for `2026-08-17`, current daily/Market Thesis artifacts,
  `portfolio_positions=not_configured`, truthful no-picks count 15, and a PASS
  promotion for fixed source `ac1192d`.
- Later atomic-boundary and crash-recovery changes strengthened this path
  without reopening the ingestion acceptance. Consolidated evidence is in
  `docs/validation-release-state-evidence-2026-08-21.md`.
