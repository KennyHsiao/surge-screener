# Phase 7B-7D Industry Roles Convergence and Recovery Plan

Status: implemented and verified on 2026-08-06 after three blocker reviews.

## Prior-phase review

Phase 6Y-7A remains consistent with its accepted scope. The store, engine,
Trade State, protected API, private client/UI, and ranked UI suites pass 47/47,
and `git diff --check` is clean. No canonical runtime state was created in the
workspace. The only observed output is the pre-existing Streamlit bare-mode and
`use_container_width` deprecation warnings.

## Objective and phase boundaries

- **Phase 7B — canonical reader convergence:** move the two remaining direct
  non-UI legacy override consumers onto a canonical-first engine projection and
  add an explicit locked legacy export/reconciliation command.
- **Phase 7C — recovery operations:** add side-effect-free status and restore
  previews, bounded backup inspection, explicit apply gates, and documented
  deployment-health evidence.
- **Phase 7D — legacy retirement gate:** enforce zero unapproved direct readers,
  inventory the remaining compatibility owners, and produce a no-delete
  `READY`/`HOLD` decision. This phase does not delete or archive data.

Out of scope: public/private API expansion, UI changes, automatic dual-write,
credential changes, deployment execution, legacy deletion, and claiming an
operating window that has not been observed.

## Impact analysis

### Vertical map

- L0: `scripts/industry_role_store.py`, `scripts/industry_roles.py`, new
  `scripts/industry_role_admin.py`.
- L1: `scripts/eastmoney_money_flow.py`, `scripts/universe_refresh.py`, their
  focused tests, store/admin tests, and the static retirement gate.
- L2: `scripts/run_candidate_pipeline.py`, the deployment operator workflow,
  `Makefile`, the endpoint inventory, and the user guide.
- L3: scheduled candidate refreshes and analytics artifacts that consume Money
  Flow or Universe outputs. Their schemas and provider behavior remain fixed.

The shared filesystem resource has API, scheduler, admin, and rollback users,
so lock and crash-order behavior receive explicit tests. No public symbol is
removed and no API contract changes. The initial estimate was 12-15 files and
roughly 350-500 changed lines including tests and docs. The completed surface
is 17 functional files because deployment-health evidence and the no-delete
admin/static gates each required an independently reviewable test owner.

### Horizontal consistency

- Python modules keep injectable `content_dir`/`reports_dir` paths and
  self-contained `scripts/test_*.py` tests.
- Canonical parsing remains strict and fail-closed in the store. The two ticker
  collectors preserve their historical supplemental fail-soft behavior by
  omitting Industry Roles tickers on a canonical state error; they never read
  stale legacy data when canonical state exists.
- Mutating admin operations require an explicit `--apply`; status and previews
  must not create the state directory, lock, canonical state, backup, manifest,
  or legacy files.

### Risk score

`scope 8*0.30 + breaking 3*0.25 + pattern 2*0.20 + coverage 3*0.15 +
reversibility 2*0.10 = 4.2/10`, medium. Mitigations are focused
tests, a detectable export manifest, no automatic writer, no deletion, and a
full regression run. Verdict: **GO**.

## Persistence and recovery design

Actual legacy export takes the existing review-state lock and requires a valid
canonical revision (`revision >= 1`). It writes a `pending` manifest first,
then atomically replaces the legacy overrides and suggestions files, verifies
their SHA-256 values, and atomically changes the manifest to `committed` last.
An interruption therefore cannot be mistaken for a complete export. Because
all repository runtime consumers have converged before this command is used,
the legacy pair is rollback material, not a live consistency boundary.

`status` validates canonical and backup files independently and compares a
committed export manifest with current canonical business bytes. It reports
bounded machine-readable evidence without mutating the filesystem. Restore
preview validates the backup and reports the proposed new revision/ETag.
Restore and export apply paths remain explicit and are exercised only against
temporary test directories in repository verification.

## Verification matrix

1. Consumer tests prove canonical values win, invalid canonical never falls
   back to legacy, and unrelated ticker sources remain available.
2. Store/admin tests prove dry-run side-effect freedom, locked export,
   pending-manifest crash detection, idempotent rerun, backup status, restore
   preview/apply, and bounded/symlink failure behavior.
3. Static retirement tests allow legacy filenames only in declared seed,
   compatibility export, API wiring, and tests; they forbid deletion code and
   require the current verdict to remain `HOLD` without operating evidence.
4. Run Industry Roles, Money Flow, Universe, Trade State, deployment,
   convergence, API/boundary, compile, Python 3.10 AST, shell/whitespace, and
   complete `make test` gates.

## Rollback

Revert the two consumer call sites and remove the admin/static-gate additions.
Canonical state is never deleted. If an export is interrupted, leave the
`pending` manifest as evidence and rerun the explicit export from the validated
canonical source. Application rollback may consume the last committed export;
it must not enable automatic dual-write.

## Blocking-issue review

- **Iteration 1:** direct strict loading could make optional ticker enrichment
  fail the whole Money Flow/Universe refresh. Resolution: one engine projection
  returns no Industry Roles tickers on review-state errors while preserving all
  other sources and forbidding stale fallback.
- **Iteration 2:** two destination files cannot be truthfully described as one
  atomic filesystem transaction. Resolution: converge live readers first, hold
  the canonical lock, use atomic per-file replacement, and make completion
  detectable with a pending/committed hash manifest.
- **Iteration 3:** repository evidence cannot establish an elapsed production
  operating window or unknown external consumers. Resolution: Phase 7D is a
  no-delete decision gate whose current honest verdict is `HOLD` until explicit
  deployment and external-consumer evidence exists.

No unresolved blocker remains. Final pre-implementation verdict: **GO**.

## Implementation closure

The actual diff matches the accepted Phase 7B-7D boundaries. The two remaining
batch consumers use the canonical-first approved-ticker projection; export is
explicit, locked, hash-verifiable, and rerunnable; status and restore previews
are side-effect free; restore apply is bound to the exact current ETag and
preserves the previous valid current state as rollback material. Deployment
runs the read-only state inspection after shared storage is linked and before
service activation. No endpoint, UI, credential, dependency, provider, or
automatic writer was added, and no legacy file was deleted or archived.

The 17-file surface is a documented estimate adjustment, not product scope
drift. If published, it should be split into Phase 7B reader/export, Phase 7C
recovery/deployment-health, and Phase 7D gate commits so each concern remains
independently reversible.

Verification completed with store 10/10, admin 4/4, retirement 3/3, Money Flow
9/9, Universe 6/6, engine 8/8, Trade State 15/15, candidate pipeline 18/18,
private API 8/8, private client/UI 6/6, ranked UI 4/4, boundary 23/23,
convergence 4/4, deployment 18/18, and Docker contract 11/11. Python 3.10 AST,
shell syntax, compile, and whitespace gates pass, and complete `make test`
exits 0. The repository status command is side-effect free and currently
reports a valid taxonomy with canonical, backup, and export all missing, which
is legal for this undeployed workspace. The only observed output is the known
Streamlit bare-mode and `use_container_width` deprecation warnings.

Post-implementation verdict: **READY** for code review and a separately
authorized deployment. Phase 7D itself remains **HOLD** for retirement because
the operating window and external-consumer evidence do not yet exist.

## Following queue

- **Phase 7E — operating-window evidence:** deploy the already-reviewed build
  under explicit authorization, capture status/export/restore-drill evidence,
  and observe at least one agreed operating window.
- **Phase 7F — external-consumer attestation:** record every out-of-repository
  reader and owner, then obtain an explicit keep/archive decision.
- **Phase 7G — archive proposal only:** if 7E/7F pass, prepare a separately
  reviewed, recoverable archive plan; deletion still requires new authority.
