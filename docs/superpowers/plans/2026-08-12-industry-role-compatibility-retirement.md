# Industry Roles Compatibility Retirement Implementation Plan

> **For implementation workers:** use `superpowers:executing-plans` or
> `superpowers:subagent-driven-development` when available. If those skills are
> unavailable, apply the repository's equivalent plan, blocker-review, diff,
> code-review, and verification gates. Do not treat this document as execution
> authority.

Status: **R0/R1 DEPLOYED; R2 PASS; R3 DEPLOYED AND CERTIFIED 2026-08-15**

## Goal

Retire the two legacy Industry Roles compatibility filenames without creating,
archiving, moving, rewriting, truncating, or deleting either live file. First
remove every automatic runtime read while retaining the explicit emergency
export. Remove the export surface only after a successful test-server deploy and
one complete natural producer observation window.

## Current authority and prerequisites

The Phase 7I decision was `READY` for a separately specified retirement change,
not permission to execute one. Its continuity was invalidated by later workflow
changes. The technical recheck on `2026-08-12` against deployed release
`824f5465fc97c74a5cbea8f493f427b2541df565` found:

- the 12-file local/deployed bundle matches exactly;
- the deployed no-delete gate passes `3/3`;
- the bounded host inventory reports zero external consumers and zero errors;
- the delegated sensitive-config check returns only `NO_MATCH`;
- canonical revision `8` and backup revision `7` are valid;
- both live legacy files and the export manifest are missing;
- API/UI health passes and no workflow is active.

Evidence: `docs/api/industry-role-retirement-continuity-2026-08-12.md`.

At `2026-08-12T13:23:00Z`, the deployment owner signed the dated `none found`
result and explicitly authorized the exact reviewed R0/R1 target list, tests,
rollback, merge, and test-server deployment. That approval did not authorize
R3, data deletion, legacy export apply, or freeze mutation. R3 still requires
R2 `PASS` and a second explicit authorization.

R2 passed on `2026-08-15` after the deployed R0/R1 release completed one fresh
natural Candidate, Data Health, and Theme Flow window. The dated evidence is
`docs/api/industry-role-retirement-r2-evidence-2026-08-15.md`. This closed R2
only; at that point R3 was still unauthorized pending the required second
explicit authorization against that result. The deployment owner gave
that authorization on `2026-08-15` by directing the agent to review and execute
R3. The no-delete and no-freeze-mutation boundaries remain unchanged.

## Scope

### R0 — synchronize the fresh decision boundary

Update the decision, gate, and static oracle so they bind the fresh 7F evidence
and current deployed release. This is documentation/test synchronization only.

### R1 — retire automatic legacy reads

Remove the legacy file readers and path injection from the engine and protected
API. A missing canonical aggregate remains a side-effect-free empty revision-zero
state so a new installation can generate its first canonical revision without a
legacy file. An invalid existing canonical aggregate remains fail-closed and
must never fall back.

Keep the explicit `export-legacy` admin command and its pending/committed hash
manifest during R1/R2. It is incident rollback preparation, not a live writer,
and still requires `--apply`.

### R2 — deploy and observe

Deploy R0/R1 to the test server, validate immediate health and state, then
observe the next natural Candidate, Data Health, and Theme Flow terminals. The
observation must prove that canonical mutations and downstream Trade State /
Analytics outputs remain valid while the two legacy files remain absent.

### R3 — retire the explicit export surface

Only after R2 passes and the deployment owner gives a second explicit
authorization, remove the export command, manifest implementation, legacy
inspection fields, and final filename allowances. R3 does not delete an export
manifest or compatibility file. If any such file appears, stop at `HOLD` and
prepare a separate disposition plan.

## Non-goals

- No canonical, backup, audit, receipt, taxonomy, API payload, UI, credential,
  service, timer, workflow trigger, or provider redesign.
- No production archive root and no synthetic archive payload for missing files.
- No automatic dual-write, migration-on-read, or best-effort stale fallback.
- No deletion, unlink, move, truncate, rewrite, or cleanup of a live source or
  manifest.
- No freeze-variable mutation unless separately authorized for a later release
  control decision.

## Impact analysis

### Vertical dependency map

- **L0 / high confidence:** `scripts/industry_roles.py`,
  `scripts/industry_role_store.py`, `api/industry_roles.py`, and `api/main.py`.
- **L1 / high confidence:** `scripts/eastmoney_money_flow.py`,
  `scripts/universe_refresh.py`, `scripts/trade_state.py`,
  `scripts/run_candidate_pipeline.py`, `ui/industry_roles.py`, and the focused
  Industry Roles/API/store/admin tests.
- **L2 / medium confidence:** Candidate/Data Health orchestration, protected API
  clients, Today Decision/Trade State/Options Cockpit views, role-assignment
  snapshots, Analytics ingestion/checks, deployment health, and static boundary
  gates.
- **L3 / lower confidence:** natural timers and downstream reports that consume
  Money Flow, Universe, Trade State, or Industry Role assignment snapshots.

The R0/R1 union is exactly 14 implementation/test files plus four modified
contract documents; the dated continuity record and this plan are preparation
artifacts, not runtime targets. Expected changed size is 300–450 lines in R0/R1
and 180–300 mostly deleted lines in R3. Keep R0/R1 and R3 in separate PRs. If
R0/R1 exceeds 400 changed lines, execute it as independently reviewable R1a
(store/engine plus fixtures) and R1b (API/static/docs) batches with no deploy
between them; each batch must remain below 400 changed lines.

### Direct dependents and breaking classification

- Nine Python modules import the shared engine; six are production modules.
- Fifteen test modules import `api.main.create_app`; only the private Industry
  Roles API test passes the legacy path parameters that R1 removes.
- Breaking class: **medium internal signature/behavior change**. No public HTTP
  route, JSON schema, CLI other than the later R3 `export-legacy` removal, or UI
  contract changes.

### Horizontal consistency

- Preserve injectable taxonomy/reports/state paths used by self-contained tests.
- The protected API must pass the exact injected canonical `state_path` to both
  reads and mutations. After the legacy suggestions parameter is removed, the
  mutation call must omit `reports_dir`; it must not infer canonical storage
  from a retired legacy path or from an unrelated directory.
- Preserve the existing strict canonical decoder and strong ETag transaction.
- Preserve fail-soft optional enrichment for Money Flow/Universe and fail-closed
  behavior for an invalid canonical aggregate.
- Follow the established explicit-apply admin pattern until R3; previews and
  status remain side-effect free.

### Cascade risk map

| Origin | Propagation | Risk | Mitigation |
|---|---|---:|---|
| Missing canonical | engine -> Candidate/Data Health -> Trade State/Analytics | Medium | Empty revision-zero seed; first generate commits canonical atomically |
| Invalid canonical | engine/API -> optional enrichments/UI | Medium | Preserve current fail-closed/no-stale-fallback behavior and 503/empty contracts |
| Deploy overlaps producer | state/API restart -> scheduled pipeline | Medium | Require quiescence and deploy outside the three timer boundaries |
| R3 removes emergency export too early | rollback loses compatibility projection | High | R3 blocked until R2 natural window passes and receives second authorization |

No feedback loop or new shared-resource contention is introduced. The canonical
lock, atomic replacement, backup, receipt, and audit behavior remain unchanged.

### Risk score

`scope 8*0.30 + breaking 6*0.25 + pattern 2*0.20 + coverage 3*0.15 +
reversibility 2*0.10 = 4.95/10`, **MEDIUM**.

Targeted behavioral coverage is strong, but the repository has no authoritative
per-file line-coverage report; the plan therefore does not claim `>=80%` line
coverage. Recommendation: **GO for the owner-authorized R0/R1 deployment after
the exact runtime preflight**; R3 remains held behind R2 observation and its own
authorization gate.

## Requirements

- `REQ-IRR-001`: No runtime engine, API reader, scheduled producer, UI, or
  deployment path may read either legacy filename after R1.
- `REQ-IRR-002`: Missing canonical state must produce a valid empty
  revision-zero snapshot without reading or creating a legacy file.
- `REQ-IRR-003`: Invalid canonical state must fail closed and must not consume a
  legacy file even if one exists.
- `REQ-IRR-004`: Existing valid canonical mutation, ETag, idempotency, audit,
  backup, and restore behavior must remain unchanged.
- `CFR-IRR-001`: R0/R1/R2 must not create, archive, move, rewrite, truncate, or
  delete either legacy file or the export manifest.
- `CFR-IRR-002`: R3 must stop if a legacy file or manifest exists; absence is a
  precondition, never a cleanup instruction.
- `CFR-IRR-003`: Rollback must use code revert/redeploy first. Materializing a
  legacy export remains a separately authorized incident action.

## Acceptance criteria

### `AC-IRR-001` — automatic reads are gone

Given R1 source, when production Python owners are inventoried, then neither
legacy filename appears outside the explicit admin export surface.

### `AC-IRR-002` — bootstrap remains canonical-only

Given a valid taxonomy and no canonical or legacy files, when suggestions are
generated, then an empty revision-zero state is used and revision `1` is
committed only to the canonical aggregate.

### `AC-IRR-003` — stale fallback is impossible

Given an invalid canonical aggregate and valid-looking legacy files, when the
API or a batch enrichment reads Industry Roles, then the API is unavailable or
the optional enrichment is empty, and legacy bytes are ignored.

### `AC-IRR-004` — natural production paths remain healthy

Given R1 is deployed with valid canonical state, when Candidate, Data Health,
and Theme Flow run naturally, then all reach terminal success; Candidate/Data
Health `role_suggestions`, `trade_state`, and `industry_roles` substeps have
direct or independently attributable success evidence; their canonical,
snapshot, and Analytics outputs are fresh and valid; API/UI remain healthy with
zero restarts; canonical transitions are attributable; and no legacy source or
manifest appears.

### `AC-IRR-005` — export removal is separately gated

Given R2 has passed and a second authorization exists, when R3 is applied, then
the admin/store export surface and all filename allowances are absent while
canonical backup/restore remains valid. Otherwise R3 does not start.

## Exact implementation tasks

### Task 1: R0 fresh-evidence synchronization

**Files:**

- Modify: `docs/api/industry-role-retirement-decision.md`
- Modify: `docs/api/industry-role-legacy-retirement-gate.md`
- Modify: `scripts/test_industry_role_legacy_retirement.py`
- Use: `docs/api/industry-role-retirement-continuity-2026-08-12.md`

- [x] Add a failing oracle that requires current release `824f546…`, the fresh
      evidence path, and runtime `HOLD` until code is deployed/observed.
- [x] Update the decision/gate history without rewriting the historical Phase
      7I checkpoint.
- [x] Run the static gate and `git diff --check`.

### Task 2: R1 canonical-only store and engine

**Files:**

- Modify: `scripts/industry_role_store.py`
- Modify: `scripts/industry_roles.py`
- Modify: `scripts/test_industry_role_store.py`
- Modify: `scripts/test_industry_roles.py`
- Modify: `scripts/test_industry_role_admin.py`
- Modify: `scripts/test_industry_role_analytics.py`
- Modify: `scripts/test_eastmoney_money_flow.py`
- Modify: `scripts/test_universe_refresh.py`
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/test_trade_state_snapshots.py`

- [x] Add fail-first cases for empty canonical bootstrap, ignored present legacy
      files, invalid canonical with valid-looking legacy files, and unchanged
      canonical transactions.
- [x] Remove legacy path readers/constants from the engine.
- [x] Make store read/mutate use an internal empty revision-zero seed rather
      than caller-supplied legacy payloads.
- [x] Preserve public engine call signatures needed by batch/UI callers unless
      removing an argument is required to make legacy access impossible.
- [x] Update fixtures to commit canonical state explicitly; do not make tests
      recreate production fallback behavior.

### Task 3: R1 protected API path removal

**Files:**

- Modify: `api/industry_roles.py`
- Modify: `api/main.py`
- Modify: `scripts/test_private_industry_roles_api.py`
- Modify: `scripts/test_industry_role_legacy_retirement.py`

- [x] Add fail-first API cases proving legacy path arguments no longer exist,
      missing canonical returns the bounded empty state, and invalid canonical
      never falls back.
- [x] Remove fixed legacy path constants and `create_app` injection parameters.
- [x] Reduce the projector input to taxonomy plus canonical state.
- [x] Pass the exact fixed canonical state path to mutations and omit the API's
      legacy-derived `reports_dir`; prove a non-default injected state path is
      the only file mutated.
- [x] Tighten the static owner set to the explicit admin export only.

### Task 4: R1 docs, regression, and review

**Files:**

- Modify: `docs/USER_GUIDE.md`
- Modify: `docs/api/fastapi-endpoint-artifact-inventory.md`
- Modify: the R0 decision/gate documents

- [x] State that runtime automatic fallback is retired while emergency export
      remains available but unapplied.
- [x] Run all verification commands below.
- [x] Include deployment-artifact, Docker-runtime, and UI/backend-boundary
      tests so the deployed state volume, status preflight, and API boundary
      cannot drift unnoticed.
- [x] Compare the actual diff against Tasks 1–4 and fix unexplained drift.
- [x] Review every finding that can cause incorrect behavior, a test failure, or
      a misleading result; fix all blocking findings.

### Task 5: R2 authorized test-server deployment and natural observation

- [x] Revalidate exact main/deploy SHA, no active producer/deploy workflow,
      valid canonical/backup, missing export manifest, and both legacy sources
      absent.
- [x] Stop if any preflight differs; do not delete or normalize it.
- [x] Merge/deploy only under explicit deployment authority.
- [x] Immediately verify API/UI state, restarts, listeners, HTTP health,
      canonical/backup status, static gate, and source absence.
- [x] Observe natural Candidate, Data Health, and Theme Flow terminal results.
- [x] Use the declared Asia/Taipei timer boundaries: Candidate Mon–Fri `20:30`,
      Data Health Tue–Sat `06:15`, and Theme Flow Tue–Sat `07:45`. Capture each
      service invocation ID, start/end/result, status JSON timestamp/result,
      and the applicable log tail; a pre-deploy terminal does not count.
- [x] Do not accept only the unit/process terminal. Candidate's refresh helper
      and Data Health intentionally contain best-effort rows that can preserve
      exit `0`. Require direct evidence that `role_suggestions`, `trade_state`,
      and `industry_roles` are `ok`: for Data Health, parse the emitted JSON;
      for Candidate, require the in-window canonical `generate` audit revision,
      fresh schema-valid Trade State and Industry Roles snapshots, and their
      fresh Analytics ingestion/check results. Any missing/error/stale result is
      `HOLD`, even when systemd reports `success`.
- [x] Attribute every canonical revision change and confirm no legacy file or
      manifest appeared.
- [x] Record a dated `PASS`/`HOLD` evidence document. R3 remains blocked on any
      failed, missing, mixed, or unexplained input.

### Task 6: R3 separately authorized export retirement

**Files:**

- Modify: `scripts/industry_role_store.py`
- Modify: `scripts/industry_role_admin.py`
- Modify: `scripts/test_industry_role_store.py`
- Modify: `scripts/test_industry_role_admin.py`
- Modify: `scripts/test_industry_role_legacy_retirement.py`
- Modify: `.gitignore`
- Modify: the Industry Roles decision/gate, User Guide, and API inventory docs

- [x] Require R2 `PASS`, second owner authorization, missing live sources, and
      missing export manifest.
- [x] Add fail-first tests requiring `export-legacy` rejection/absence and zero
      production filename owners.
- [x] Remove export/manifest code and legacy inspection fields; retain canonical
      status plus backup preview/apply recovery.
- [x] Remove only the obsolete `.gitignore` allowance; do not touch a runtime
      file.
- [x] Run the full verification and a second guarded deploy/observation.

R3 deployed as release `43c38a04d3de97a1d933a8207c12166b45780631`
through successful run `31867899113`. The pre-merge and two post-deploy
checkpoints are recorded in
`docs/api/industry-role-retirement-r3-evidence-2026-08-15.md`; final verdict is
`PASS` / Attest `CERTIFIED`.

Implementation-size note: the R3 diff exceeds the early 180–300-line estimate
because complete surface retirement necessarily deletes the 219-line store
implementation and roughly 210 lines of obsolete export behavior tests. The
added lines are contract updates, recursive absence oracles, and skill evidence;
no runtime feature or target outside Task 6 was added.

## Verification commands

Use the repository Python environment from the clean implementation worktree.

```bash
python scripts/test_industry_role_store.py
python scripts/test_industry_role_admin.py
python scripts/test_industry_role_legacy_retirement.py
python scripts/test_industry_roles.py
python scripts/test_industry_role_analytics.py
python scripts/test_private_industry_roles_api.py
python scripts/test_ui_industry_roles_private_api.py
python scripts/test_ui_industry_roles_ranked_api.py
python scripts/test_eastmoney_money_flow.py
python scripts/test_universe_refresh.py
python scripts/test_trade_state.py
python scripts/test_trade_state_snapshots.py
python scripts/test_candidate_pipeline_controls.py
python scripts/test_deploy_artifacts.py
python scripts/test_docker_runtime_contract.py
python scripts/test_ui_backend_boundary.py
python -m compileall -q api scripts ui
git diff --check
make test
```

Before R1 implementation, the current focused baseline passed engine `8/8`,
store `10/10`, admin `4/4`, static retirement `3/3`, private API `8/8`, Money
Flow `9/9`, Universe `6/6`, Trade State `15/15`, and candidate controls
`18/18`. No authoritative coverage percentage is available.

## Rollback and abort criteria

Abort before merge/deploy if current main differs, a producer is active,
canonical/backup is invalid, the one-time read-only exact-path preflight finds
an export manifest or either legacy source, an external consumer appears, or a
required test fails. R3 removes permanent export inspection, so this result
must be rerun immediately before merge/deploy and bound to rollout evidence.

For R1 regression, revert the R1 commit and redeploy the last known-good release.
Do not export or recreate legacy files: the old code will continue to read the
valid canonical aggregate first. If canonical state itself is damaged, use the
existing exact-ETag backup restore runbook; an export apply remains a separately
authorized incident action.

For R3 regression, revert the R3 commit and redeploy. This restores the explicit
export command without creating an export. Canonical state and backup are never
deleted by either forward or rollback path.

## Blocking-issue review

1. **Later workflow changes invalidated the old 7F carry-forward.** Resolved by
   the fresh 2026-08-12 deployed-source binding, host inventory, sensitive
   boolean check, state check, and service check.
2. **One-shot removal would discard rollback preparation before runtime proof.**
   Resolved by retaining explicit export through R2 and requiring a second R3
   authorization.
3. **Requiring canonical existence would break clean installation/bootstrap.**
   Resolved with a side-effect-free empty revision-zero seed; only an explicit
   mutation creates canonical revision `1`.
4. **Removing API legacy path injection could redirect writes accidentally.**
   Resolved by requiring reads and mutations to share the exact injected
   canonical state path and by forbidding mutation-path derivation from the
   retired suggestions filename.
5. **A producer can mask a best-effort Industry Roles substep failure behind a
   successful process terminal.** Resolved in R2 by requiring exact critical
   substep or attributable output evidence; terminal success alone never passes.

No unresolved design or evidence blocker remains for R0/R1. The deployment
owner supplied the dated `none found` attestation and exact R0/R1 authority at
`2026-08-12T13:23:00Z`. R3, deletion, export apply, and freeze mutation remain
outside that authority.

## Success metrics

- Zero automatic production readers of either legacy filename after R1.
- Zero production references to either filename after R3.
- Zero legacy file/manifest creation or deletion during implementation,
  deployment, observation, and rollback testing.
- All focused and full tests pass with no unexplained scope drift.
- Candidate, Data Health, and Theme Flow reach natural terminal success after
  R1; API/UI remain healthy with zero restarts.
- Canonical revisions, backup, audit, receipts, and ETags remain valid and
  attributable.
