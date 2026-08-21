# Full Test Baseline Recovery Plan

Status: **RELEASE VERIFIED — PR #18 merged and deployed 2026-08-15; re-audited 2026-08-21**

## Document control

- Type: implementation plan and verification checklist
- Owner: repository maintainer
- Implementer/reviewer: Codex, followed by independent code/spec gates
- Audience: maintainers and release reviewers
- Baseline: `origin/main` at `c43ef10ee58a168c58919f5a755bc9c8d185cfcd`
- Related evidence: `docs/api/industry-role-retirement-r3-evidence-2026-08-15.md`

## Goal

Restore a clean-clone `make test` pass without hiding failures or depending on
ignored runtime files. Preserve the current public API, UI behavior, producers,
deployment topology, and historical UX rollback contract.

## Observed baseline

The four failing entries were reproduced independently in a clean worktree:

1. `test_ui_reversal_snapshots_api.py`: the current finite Oversold validation
   artifact is rejected because private compounded equity exceeds an arbitrary
   validator ceiling.
2. `test_ui_sector_rotation_api.py`: the pinned `2026-07-01` archive expected by
   the test is absent from Git.
3. `test_ui_ux_contract.py`: the declared six-file rollback source is ignored
   and absent from a clean clone.
4. `test_ui_ux_fixtures.py`: the test requires two intentionally ignored root
   runtime artifacts to exist.

## Scope

- Correct the private Oversold source validator so every non-negative finite
  compounded equity value can be validated, while negative and non-finite
  values remain rejected.
- Retain strict consistency between the final gross equity-curve point and the
  declared gross equity multiple.
- Replace the Sector Rotation test's untracked runtime dependency with a
  deterministic source built inside the focused test.
- Publish the exact six-file UX-1B rollback source already bound by hashes in
  the accepted UX contract, with narrow `.gitignore` allowances only.
- Make the candidate artifact inventory test require only committed root
  fixtures while continuing to reject unknown candidate-like JSON files.
- Mark the historical Phase 7E-7F plan as superseded by the completed R2/R3
  evidence, without rewriting its historical body.

## Non-goals

- No API schema, endpoint, UI, producer, timer, service, credential, or workflow
  redesign.
- No regeneration or modification of live runtime data.
- No test skip, xfail, broad assertion removal, or blanket `.gitignore` change.
- No UX Sequence-20 implementation or historical rollback mutation.
- No deployment-state or freeze-variable mutation before release approval.

## Requirements and acceptance criteria

- `REQ-BLR-001`: clean-clone tests must not require ignored runtime files.
- `REQ-BLR-002`: the current valid Oversold artifact must remain readable while
  malformed numeric and curve states fail closed.
- `CFR-BLR-001`: tracked fixtures must be deterministic, non-secret, bounded,
  and confined to the exact paths declared below.

### `AC-BLR-001` — Oversold finite compounded equity

Given a strict Oversold validation source with non-negative finite compounded
equity above the previous ceiling, when the artifact is read, then its bounded
public projection is available. Given negative or curve-mismatched equity, the
same read returns `invalid_shape`; a non-finite JSON number fails earlier at
strict parsing with `invalid_json`.

### `AC-BLR-002` — tracked historical fixtures

Given a clean Git worktree, when Sector Rotation and UX rollback contract tests
run, then Sector Rotation uses an in-test deterministic source and UX uses
tracked hash-stable inputs. Neither test copies runtime data from another
workspace.

### `AC-BLR-003` — runtime candidate artifacts remain optional

Given a clean Git worktree containing only committed root candidate fixtures,
when the inventory test runs, then it passes. Given an unknown candidate-like
root JSON filename, the allowlist assertion still fails.

### `AC-BLR-004` — full baseline and documentation converge

Given the completed implementation, when all focused entries and `make test`
run, then every test exits zero. The Phase 7E-7F header points readers to the
terminal R2/R3 evidence and no longer claims current work is in progress.

## Exact implementation tasks

### Task 1 — fail-first Oversold contract correction (`IMPL-001`)

- Modify `scripts/test_ui_reversal_snapshots_api.py` with valid large-finite,
  negative, non-finite, and final-curve mismatch cases.
- Modify `api/artifacts.py` to separate bounded return metrics from unbounded
  finite non-negative compounded equity and to bind the curve tail.
- `TEST-001`: run `scripts/test_ui_reversal_snapshots_api.py` and require the
  current artifact plus large-finite/negative/non-finite/mismatch cases to pass.

### Task 2 — clean-clone deterministic inputs (`IMPL-002`)

- Modify `scripts/test_ui_sector_rotation_api.py` so `_source()` returns a
  deterministic strict source without reading `reports/`.
- Remove the fixed `ARCHIVE` dependency. Every happy-path projection and route
  read must write the deterministic source under `TemporaryDirectory` and
  inject `_spec(path)` (or an equivalent temporary resolver). Keep latest-file
  selection and fail-closed malformed-latest coverage inside a temporary
  archive.
- Add only `.claude/ui_snapshots/ux1b/rollback-source/{manifest.json,
  .quant-radar-ux1b-owner,config.toml,app.py,requirements.txt,_design.py}`.
- Modify `.gitignore` with exact nested unignore rules; keep all other UI
  snapshots ignored.
- Verify every published byte against the hashes already declared by the UX
  manifest and contract before commit.
- `TEST-002`: run `scripts/test_ui_sector_rotation_api.py` and
  `scripts/test_ui_ux_contract.py` in the isolated worktree.

### Task 3 — candidate inventory and historical status (`IMPL-003`)

- Modify `scripts/test_ui_ux_fixtures.py` so only committed root fixtures are
  required; retain the complete production/legacy allowlist and unknown-file
  rejection.
- Add a superseded banner to
  `docs/api/frontend-backend-separation-phase7e-7f-plan.md`, linking the dated
  R2 and R3 evidence. Preserve the historical execution text below it.
- `TEST-003`: run `scripts/test_ui_ux_fixtures.py` and a mutation probe that
  proves an unknown candidate-like root JSON remains rejected.

### Task 4 — verification, review, and release (`IMPL-004`)

- Run all four previously failing test entries, related API/UX/static suites,
  `python -m compileall -q api scripts ui`, and `git diff --check`.
- Run complete `make test` with the project Python interpreter.
- Confirm required fixtures are tracked and no unexpected ignored file is added.
- Compare the actual diff to Tasks 1-3; reject unexplained scope drift.
- Complete independent code review and acceptance traceability before publish.
- Publish through a feature branch/PR; deploy only after merge and normal release
  gates pass.
- `TEST-004`: run complete `make test`, compileall, whitespace, tracked-path,
  ignored-path, credential-scan, and post-merge deployment-health gates.

## Traceability

| Requirement | Acceptance criterion | Implementation | Tests |
|---|---|---|---|
| `REQ-BLR-001` | `AC-BLR-002`, `AC-BLR-003` | `IMPL-002`, `IMPL-003` | `TEST-002`, `TEST-003` |
| `REQ-BLR-002` | `AC-BLR-001` | `IMPL-001` | `TEST-001` |
| `CFR-BLR-001` | `AC-BLR-002`, `AC-BLR-004` | `IMPL-002`, `IMPL-004` | `TEST-002`, `TEST-004` |

## Risk and rollback

- Risk: medium. One production validator changes, but only for private fields
  projected out of the public response; strict finite, sign, count, ordering,
  and curve consistency checks remain.
- Fixture risk is bounded by exact paths, hashes, and credential scans. No file
  is added below deployable `reports/` or another persistent runtime path.
- Rollback is the feature commit revert and normal redeploy. Do not delete or
  rewrite runtime files on the host.

## Blocking review gate

Implementation must not begin unless all are true:

- [x] The four failures reproduce on exact `origin/main`.
- [x] Affected files, negative tests, full verification, and rollback are known.
- [x] Fixture sources match existing contract hashes and contain no credentials.
- [x] The plan contains no test skips, runtime mutation, or unrelated UX work.
- [x] No unresolved blocking/high-risk review finding remains.

## Success metrics

- Four previously failing entries: `4/4` pass.
- Complete `make test`: exit `0` in an isolated clean worktree.
- Required fixture hash checks: `100%` match.
- Unexplained files or behavior changes: `0`.

## Release closure

- PR [#18](https://github.com/KennyHsiao/surge-screener/pull/18) merged as
  `21a459d7c50c51d24927e7fdcbfbd95558a37145`.
- Deployment run
  [31891775411](https://github.com/KennyHsiao/surge-screener/actions/runs/31891775411)
  completed successfully.
- The focused baseline suites and complete `make test` passed before merge. The
  2026-08-21 release-state audit found no later regression or open release gate.
- Consolidated evidence is recorded in
  `docs/validation-release-state-evidence-2026-08-21.md`.
