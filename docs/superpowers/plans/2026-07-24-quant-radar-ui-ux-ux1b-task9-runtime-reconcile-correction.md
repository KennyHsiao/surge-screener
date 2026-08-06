# Quant Radar UX-1B Task 9 Runtime and Reconcile Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | 1.0 |
| Status | Accepted |
| Authorization | Maintainer approval in the active 2026-07-24 session |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `4` |
| Recovery ID | `20260724T081000Z` |
| Tier ID | `20260724T082000Z` |
| Superseded active package | `2026-07-24-quant-radar-ui-ux-ux1b-task9-production-enablement-amendment.md` |
| Imported predecessor | Sequence 3 plan, ledger, preflight, and intent |

## Context

Sequence 3 passed its implementation, regression, fail-soft, and preflight
gates. Its one authorized formal `capture-task9` invocation published the
intent for recovery ID `20260724T063336Z`, then returned exit `5` before a
runner was created.

The failed attempt is immutable evidence:

| Artifact | SHA-256 | Size | Inode |
| --- | --- | ---: | ---: |
| Sequence 3 preflight | `9ffba7edcbaf935add3090de8907b8e40229f4ea4d0d3aac490af79e98fe74a5` | 113610 | 12363609 |
| Sequence 3 intent | `e65b7a624b578e73f2d9b9779bf9d5c062362e5f63bc9b9b1a9514e926e29e64` | 58458 | 12364805 |

The control checkpoint, pretheme gate, pretheme checkpoint, terminal, and both
capture output directories for Sequence 3 remain absent. No runner or browser
process remains. Recovery ID `20260724T063336Z` is burned and MUST NOT be
retried.

## Root-cause record

### `RC-001` — missing production temporary-root parent

`_Task9ProductionDriver._execute()` derives the stage directory below
`runtimeReceipt.tempRootParent`, then calls `Path.mkdir()` only for that stage.
The fixed production parent
`/private/tmp/quant-radar-ux1b-runtime` did not exist. The stage creation
therefore raised `ENOENT`, which the public handler correctly sanitized to
exit `5`.

The existing process test used `TemporaryDirectory()` itself as
`tempRootParent`. That directory already existed, so the test could not
reproduce the production precondition.

### `RC-002` — fresh-preflight validation reused during reconciliation

`_build_task9_production_context()` calls `_validate_preflight_complete()`.
That validator reconstructs the preflight through
`_build_preflight_value()`, which requires every future destination to remain
absent. Once an intent is committed, the valid active lifecycle is therefore
misclassified as a preflight destination collision before
`_task9_transition()` can validate or reconcile it.

Existing reconciliation tests called `_task9_transition()` with an injected
context and did not pass through the public production context builder.

### `RC-003` — latent mid-capture reauthentication collision

The production driver calls the same fresh-preflight validator after the
control checkpoint. Even if `RC-001` had not occurred, that reauthentication
would reject the valid committed intent, control checkpoint, and output
directory before publishing the pretheme gate.

## Scope

### In scope

- Authorize Sequence 4 and recovery ID `20260724T081000Z`.
- Import and reauthenticate the immutable Sequence 3 plan, ledger, preflight,
  and intent as failed-attempt authority.
- Preserve Sequence 1, Sequence 2, Task 6, capture-stack, global-lock, and
  compatibility authority.
- Create a new Sequence 4 capture lease, Tier 0 package, preflight, lifecycle,
  and capture namespaces.
- Create the production temporary root securely when absent.
- Add an epoch component to every private runner environment:
  `/private/tmp/quant-radar-ux1b-runtime/20260724T081000Z/{stage}`.
- Separate fresh-preflight destination validation from active-Task-9
  authority validation.
- Exercise the real production context builder in capture and reconcile
  regression tests.
- Run one formal Sequence 4 Task 9 capture only after all gates pass.

### Non-goals

- Do not edit, delete, rename, relink, truncate, reconcile, or retry any
  Sequence 3 evidence path.
- Do not claim that Sequence 3 passed or publish a Sequence 3 terminal.
- Do not change API or Streamlit fail-soft behavior.
- Do not change UI, selectors, theme files, Task 6 artifacts, capture
  manifests, capture-stack authority, or compatibility postimages.
- Do not continue to migration, review publication, root publication, or
  theme application in this correction.
- Do not weaken `verify-preflight` or the pre-intent freshness requirement.

## Authority and precedence

The recovery authorization document MUST contain exactly one canonical V2
marker pair. Its body MUST authorize:

- integer `sequence:4`;
- recovery ID `20260724T081000Z`;
- this final plan and its sibling traceability ledger;
- the unchanged four-level precedence array.

The Sequence 4 authorization package MUST reauthenticate:

1. the parent Sequence 1 replacement plan and ledger;
2. the Sequence 2 amendment, ledger, and preflight;
3. the Sequence 3 amendment and ledger;
4. the exact Sequence 3 preflight and intent listed above;
5. the Task 6 page and control manifests and all 234 artifacts;
6. the capture-stack contract and runtime authorities;
7. the imported global lock.

The resulting Tier 0 input set MUST contain exactly `296` live records and
`31` authority records. Both arrays are sorted, unique by path, and every
authority record is the identical record at the same path in the live set.

Sequence 3 preflight and intent are historical failure evidence only. They
MUST NOT authorize Sequence 4 runners or appear in the Sequence 4 eligible
destination set.

## Fixed Sequence 4 namespace

The following destinations were verified absent before this plan was frozen:

```text
.claude/ui_snapshots/ux1b/recovery/.capture-20260724T081000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq4.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq4.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260724T082000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260724T081000Z.json
.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260724T081000Z/
.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260724T081000Z/
```

Migration, review, candidate, and root destinations retain the Sequence 3
shape with the new recovery ID. The canonical root contract remains absent.

## Requirements

### `REQ-003` — production private environment creation

The production driver MUST create an absent authenticated temporary-root leaf,
an exclusive recovery-epoch directory, an exclusive stage directory, and the
five private child directories before spawning a runner.

### `REQ-004` — lifecycle-aware authority reauthentication

The production capture and reconcile handlers MUST validate the immutable
preflight authority while applying a destination policy appropriate to the
current lifecycle phase.

### `CFR-006` — descriptor-safe temporary path handling

Temporary-root creation MUST use descriptor-relative operations. The retained
parent, created root, epoch, stage, and child directories MUST be identity
checked with no symlink following. The created directories MUST be owned by
the current UID/GID and mode `0700`.

The immediate parent MAY be either:

- a current-UID/GID directory satisfying the existing safe-directory policy;
  or
- the exact root-owned sticky directory `/private/tmp` with mode `1777`.

Any other parent, symlink, non-directory, unsafe mode, owner drift, identity
race, unauthorized existing epoch, existing stage, or child collision MUST
fail closed before `Popen`.

### `CFR-007` — closed destination policies

Exactly two validation policies are permitted:

- `fresh`: every destination in `TIER0_DESTINATIONS[11:]` is absent;
- `task9-active`: existing leaves are permitted only in the five Task 9
  lifecycle paths and two direct output paths. Every later migration, review,
  candidate, intake, and root destination remains absent.

Both policies MUST reconstruct the same stored `eligibleDestinations` array
with `exists:false`; active paths do not rewrite preflight bytes. Unknown
policy values or allowlists MUST be rejected.

### `CFR-008` — exact active-chain validation

The active policy only permits the production context to be built. It MUST NOT
declare the lifecycle valid. `_task9_transition()` remains the sole validator
of contiguous lifecycle prefixes, exact references, bundle identity,
at-most-once execution, terminal status, and reconcile outcomes.

### `CFR-009` — predecessor immutability and fail-soft regression

Sequence 3 evidence and all protected API/Streamlit fail-soft files MUST retain
their exact content. Existing missing, partial, malformed, and unreadable
artifact reads MUST continue to return the existing unavailable behavior
rather than crash.

## Corrected production design

### Private environment layout

For stage `postcontrol` or `pretheme`, runner plans MUST bind:

```text
tempRootParent = /private/tmp/quant-radar-ux1b-runtime
epochRoot      = /private/tmp/quant-radar-ux1b-runtime/20260724T081000Z
stageRoot      = /private/tmp/quant-radar-ux1b-runtime/20260724T081000Z/{stage}
HOME           = {stageRoot}/home
TMPDIR         = {stageRoot}/tmp
TMP            = {stageRoot}/tmp
TEMP           = {stageRoot}/tmp
XDG_CACHE_HOME = {stageRoot}/cache
XDG_CONFIG_HOME= {stageRoot}/config
XDG_DATA_HOME  = {stageRoot}/data
```

The shared `tempRootParent` may be created when absent. The postcontrol setup
MUST create the epoch root exclusively and retain its device/inode identity in
the production-driver instance. The pretheme setup MUST reopen that same
identity from the same instance. It MUST reject a missing epoch, an epoch that
predates the instance, or identity drift. Each stage and child leaf remains
exclusive.

### Preflight validation modes

`_validate_preflight_complete()` gains a closed
`destination_policy: Literal["fresh","task9-active"]` parameter.

- Preflight publication, preflight reopen, and `verify-preflight` use `fresh`.
- A public `capture-task9` context uses `fresh`.
- A public `reconcile-task9` context uses `task9-active`.
- Driver reauthentication after intent publication uses `task9-active`.

The active policy permits only the current Sequence 4 Task 9 lifecycle and
direct output names. It still reauthenticates the plan, ledger, predecessor
authority, source projection, capture stack, runtime receipt, Task 6 evidence,
selector delta, descriptor budget, lock, lease, and preflight artifact
identity.

### Public reconciliation

The public handler MUST pass its event to the production context builder.
The filesystem-bound core MUST be exposed as one internal
`_run_task9_with_descriptors(workspace_fd, source_root_fd, event)` seam. The
public handler opens the production descriptors and delegates to this seam;
tests invoke the same seam with owned scratch descriptors.
Given an intent-only chain, `reconcile-task9` MUST build its authenticated
context, launch no runner, and publish only the declared revoked terminal with
reason `control_nested_quiescence_unverified`. Invalid, gapped, mutated, or
unrelated-collision states remain nonzero and launch-free.

## Acceptance criteria

### `AC-SEQ4-001` — new immutable epoch

Given the new authorization body, when the package is parsed and Tier 0 is
built, then Sequence 4 paths are new, Sequence 3 failure evidence is imported
at exact bytes, and no predecessor inode, mtime, size, or digest changes.

### `AC-SEQ4-002` — absent temporary parent

Given a safe immediate parent and an absent `tempRootParent`, when the real
production driver executes a no-op child plan, then the root, epoch, stage, and
five child directories are created with exact identities and mode `0700`, and
the child exits successfully.

### `AC-SEQ4-003` — temporary path attacks

Given symlink, non-directory, unsafe-mode, foreign-owner where testable,
existing-epoch, existing-stage, and child-collision fixtures, when setup runs,
then it fails before runner launch with a closed contract or collision result.

### `AC-SEQ4-004` — fresh policy remains strict

Given any committed active or later destination, when preflight verification
or a fresh capture context is built, then validation fails and no runner
launches.

### `AC-SEQ4-005` — active policy is narrow

Given a valid Task 9 prefix, when active validation runs, then the immutable
preflight reauthenticates successfully. Given any later destination or unknown
policy, validation fails.

### `AC-SEQ4-006` — public reconcile reaches transition

Given an intent-only production lifecycle, when the public reconcile seam runs,
then no runner launches and the exact revoked terminal is published. The
context builder does not reject the intent as a preflight collision.

### `AC-SEQ4-007` — mid-capture reauthentication

Given a valid control checkpoint and postcontrol output, when the production
driver reauthenticates before the pretheme gate, then authority validation
passes without weakening exact chain or bundle validation.

### `AC-SEQ4-008` — formal one-shot

Given package, red-to-green regression, full recovery, fail-soft, syntax,
static, scope, process-cleanup, and changed-code review gates all pass, when
the new preflight is independently reopened and the formal command runs once,
then both runner stages launch at most once and a passed terminal is published.
Otherwise no formal capture starts.

## Implementation checklist

- [ ] `IMPL-011`: Freeze this plan and canonical traceability ledger, then
  publish the Sequence 4 authorization body.
- [ ] `IMPL-012`: Add Sequence 4 constants, namespaces, and imported Sequence
  3 failure references.
- [ ] `IMPL-013`: Add red-first absent-parent and path-attack production-driver
  regression tests.
- [ ] `IMPL-014`: Add red-first fresh/active policy and public-reconcile
  regression tests.
- [ ] `IMPL-015`: Implement descriptor-safe temporary root, epoch, stage, and
  private-child creation.
- [ ] `IMPL-016`: Implement closed destination policies and event-aware
  production context/reauthentication.
- [ ] `IMPL-017`: Run focused/full/static/fail-soft gates, compare the diff to
  this plan, and fix all blocking review findings.
- [ ] `IMPL-018`: Bootstrap Sequence 4, publish and independently reopen its
  preflight, then invoke formal Task 9 exactly once.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-030` | Sequence 4 package authenticates all exact Sequence 3 failure references and rejects mutations. |
| `TEST-031` | Real production driver succeeds when its fixed temp root is absent. |
| `TEST-032` | Symlink, unsafe parent/root, existing epoch/stage, and child collisions fail before `Popen`. |
| `TEST-033` | Fresh and active destination policies accept only their declared namespace states. |
| `TEST-034` | Public reconcile of an intent-only chain reaches transition, launches zero runners, and publishes revoked terminal. |
| `TEST-035` | Mid-capture production reauthentication accepts exact active state and rejects later collisions or authority drift. |
| `TEST-036` | Complete recovery and API/Streamlit fail-soft regression suites pass; Sequence 3 evidence stats remain exact. |
| `TEST-037` | Sequence 4 bootstrap/preflight reopen and the one formal Task 9 invocation satisfy the terminal and launch-count gate. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-003` | `AC-SEQ4-002`, `AC-SEQ4-003` | `IMPL-013`, `IMPL-015` | `TEST-031`, `TEST-032` |
| `REQ-004` | `AC-SEQ4-004`, `AC-SEQ4-005`, `AC-SEQ4-006`, `AC-SEQ4-007` | `IMPL-014`, `IMPL-016` | `TEST-033`, `TEST-034`, `TEST-035` |
| `CFR-006` | `AC-SEQ4-002`, `AC-SEQ4-003` | `IMPL-013`, `IMPL-015` | `TEST-031`, `TEST-032` |
| `CFR-007` | `AC-SEQ4-004`, `AC-SEQ4-005` | `IMPL-014`, `IMPL-016` | `TEST-033`, `TEST-035` |
| `CFR-008` | `AC-SEQ4-005`, `AC-SEQ4-006`, `AC-SEQ4-007` | `IMPL-014`, `IMPL-016` | `TEST-033`, `TEST-034`, `TEST-035` |
| `CFR-009` | `AC-SEQ4-001`, `AC-SEQ4-008` | `IMPL-011`, `IMPL-012`, `IMPL-017`, `IMPL-018` | `TEST-030`, `TEST-036`, `TEST-037` |

## Commands and gates

Before Tier 0 or formal publication:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run the repository's relevant API fail-soft, Streamlit fail-soft,
snapshot, fixture, theme, navigation, compile, Python 3.10 AST, tabnanny,
dependency, whitespace, diff, descriptor, and process-quiescence checks.

The formal order is:

```bash
make ui-ux1b-theme-handoff-bootstrap \
  UX1B_RECOVERY_ID=20260724T081000Z
make ui-ux1b-theme-handoff-preflight \
  UX1B_RECOVERY_ID=20260724T081000Z
make ui-ux1b-recovery-postcontrol \
  UX1B_RECOVERY_ID=20260724T081000Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T081000Z.json
```

The final command is the only authorized formal Task 9 capture invocation for
Sequence 4. It MUST NOT run until the preflight succeeds and a separate fresh
process verifies it.

## Risks and rollback

- Any committed Sequence 4 intent burns recovery ID `20260724T081000Z`.
- A partial private environment is never silently reused. Existing epoch or
  stage state fails closed.
- An active validation policy that is too broad could conceal unrelated
  collisions. The fixed seven-path allowlist and later-destination negative
  tests are blocking gates.
- Before Sequence 4 Tier 0 publication, rollback removes only this correction's
  uncommitted code and authorization changes. Unrelated dirty worktree files
  are preserved.
- After Sequence 4 Tier 0 publication, its evidence is immutable. Another
  correction requires a new accepted plan and recovery epoch.
- Sequence 3 evidence is never part of rollback cleanup.

## Review checklist

- [x] User request, scope, non-goals, audience, authority, dependencies, and
  success metrics are explicit.
- [x] Both observed production root causes and the latent third collision are
  covered by binary acceptance criteria.
- [x] New paths are absent and disjoint from Sequence 3 paths.
- [x] Fresh preflight validation remains strict.
- [x] Active validation has a fixed seven-path allowlist and delegates chain
  correctness to the existing transition.
- [x] The absent-parent regression exercises the real production driver.
- [x] Public reconcile regression includes the production context builder.
- [x] API and Streamlit fail-soft behavior remain mandatory regression gates.
- [ ] Final plan and ledger hashes are frozen in code and authorization.
- [ ] Red-first tests fail for the two original defects and pass after fixes.
- [ ] Changed-code review reports no blocking issue.
- [ ] Sequence 4 preflight reopens in a fresh process before formal capture.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-07-24 | Authorized a new epoch to correct missing temp-root creation and lifecycle-unaware preflight validation. |
