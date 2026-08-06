# Quant Radar UX-1B Task 9 Production Enablement Amendment

## Document information

| Field | Value |
| --- | --- |
| Type | Implementation amendment and execution checklist |
| Version | 1.0 |
| Status | Accepted |
| Authorization | Maintainer approval in the active 2026-07-24 session |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `3` |
| Recovery ID | `20260724T063336Z` |
| Tier ID | `20260724T070000Z` |
| Parent package | `2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md` |
| Imported amendment | `2026-07-24-quant-radar-ui-ux-ux1b-regression-compatibility-amendment.md` |

## Context

Sequence 2 published a valid formal preflight for recovery ID
`20260719T211915Z`. That preflight binds the exact SHA-256 of
`scripts/ui_ux_theme_handoff.py`. The bound program still maps
`capture-task9` and `reconcile-task9` to the unavailable handler, so the
formal command returns exit `3` before creating an intent.

Editing the bound program would invalidate the sequence 2 source projection.
Overwriting its preflight or lifecycle paths is forbidden. Sequence 3
therefore creates a new recovery epoch after production Task 9 behavior is
implemented and verified.

All sequence 2 Task 9 lifecycle leaves and output namespaces were verified
absent before this amendment. The sequence 2 capture ID was not burned.

## Scope

### In scope

- Authorize sequence 3 and recovery ID `20260724T063336Z`.
- Import and reauthenticate the sequence 2 amendment, ledger, preflight,
  Task 6 manifests, and operational global lock.
- Create a new capture lease and new sequence 3 Tier 0 evidence.
- Implement production `capture-task9` and `reconcile-task9` handlers.
- Implement the exact two-stage production runner and manifest verifier.
- Apply component-walk path safety, bounded descriptors, exclusive durable
  publication, global locking, and at-most-once lifecycle rules.
- Publish a new preflight only after code, tests, and review pass.
- Execute the formal Task 9 capture once only after every pre-capture gate
  passes.

### Non-goals

- Do not overwrite, rename, remove, or relink sequence 1 or sequence 2
  evidence.
- Do not modify API fail-soft behavior, Streamlit fail-soft behavior, product
  UI, theme files, selectors, or captured Task 6 artifacts.
- Do not run a formal capture from a test, private import, injected handler,
  or test driver.
- Do not continue to migration, root publication, or theme application in
  this amendment.
- Do not treat an exit `3`, partial lifecycle, or passed manifest without a
  terminal chain as success.

## Authority and precedence

The recovery authorization document MUST contain one canonical V2 marker
pair. Its body MUST be canonical JSON with:

- `schemaVersion:"quant-radar-ui-ux-formal-handoff-authorization/v2"`;
- integer `sequence:3`;
- `status:"AUTHORIZED"`;
- `authorizedRecoveryId:"20260724T063336Z"`;
- `amendment` bound to this document after its bytes are final;
- `traceability` bound to the sibling ledger;
- the unchanged four-level precedence array.

Sequence 3 supersedes sequence 2 only as the active formal handoff execution
authority. It imports rather than replaces:

1. the parent sequence 1 replacement plan and ledger;
2. the sequence 2 compatibility amendment and ledger;
3. the exact sequence 2 formal preflight at SHA-256
   `eac3024d8a409553df74a58c78bc7a52e300652c7eac734bd445c7c72e65a82d`;
4. the exact Task 6 page and control manifests and all their authenticated
   artifacts;
5. the existing global lock
   `.claude/ui_snapshots/ux1b/.formal-theme-handoff.lock`.

The sequence 2 preflight is historical authority only. It MUST NOT authorize
sequence 3 runners.

## Sequence 3 Tier 0 ownership

Sequence 3 starts after the coordinator and its test module already exist.
They are existing implementation inputs, not bootstrap-created scratch files.
The new Tier 0 record MUST classify:

- `scripts/ui_ux_theme_handoff.py`,
  `scripts/test_ui_ux_theme_handoff.py`, this amendment, its ledger, and the
  live recovery document as retained existing inputs;
- the sequence 2 global lock as `imported_operational`, with the same inode,
  empty SHA-256, mode `0600`, owner, group, and one-link regular metadata;
- only `.capture-20260724T063336Z.lease` as a new
  `retain_operational` control whose precondition is absent;
- all sequence 3 prechange, rollback, preflight, lifecycle, output, migration,
  review, candidate, and root leaves as eligible absent destinations.

Sequence 3 rollback MUST NOT delete either Python module or the shared global
lock. Bootstrap acquires the imported global lock exactly once before it
creates the new lease or publishes any sequence 3 evidence.

## Fixed sequence 3 namespace

The following paths are fixed:

```text
.claude/ui_snapshots/ux1b/recovery/.capture-20260724T063336Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq3.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq3.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260724T070000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260724T063336Z.json
.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260724T063336Z/
.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260724T063336Z/
```

The migration, review, and root paths also use the sequence 3 recovery ID.
The final canonical root contract remains
`docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`, which is still
absent. Existing sequence 2 paths remain outside the sequence 3 eligible
destination set.

## Requirements

### `REQ-001` — executable formal coordinator

The public `capture-task9` command MUST run the exact two frozen capture plans
through a production driver. `reconcile-task9` MUST inspect and close an
existing sequence 3 chain without starting a runner.

### `REQ-002` — new immutable epoch

Sequence 3 MUST create new Tier 0, preflight, lifecycle, and output paths while
retaining sequence 2 evidence byte-for-byte.

### `CFR-001` — at-most-once execution

Each stage MUST launch no more than once. Any committed intent burns the
recovery ID. A fresh process MUST NOT continue a missing stage.

### `CFR-002` — path and publication safety

All retained paths MUST be opened by descriptor-relative component walks.
Lifecycle leaves MUST use exclusive no-replace publication, file and parent
`fsync`, inode confirmation, canonical reopen, and exact schema validation.

### `CFR-003` — bounded resources and process closure

The coordinator MUST enforce its descriptor budget, output limits, timeout,
fresh outer process group, inherited capture-lease FD only, bounded observer,
and terminal outer-family quiescence receipt.

### `CFR-004` — authority freshness

The coordinator MUST reauthenticate sequence 3 preflight, source projection,
capture stack, runtime receipt, Task 6 anchors, and imported sequence 2
authority before intent and again before the pretheme gate.

### `CFR-005` — fail-closed formal execution

Unavailable dependencies, collisions, uncertainty, active leases, exhausted
claims, interruptions, and unverified process closure MUST map to their
declared nonzero exits. No failed result may expose internal state or publish
a passed terminal.

## Production Task 9 contract

The exact runner argv arrays are:

```json
[".venv/bin/python","scripts/ui_ux_snapshot_matrix.py","--profile","ux1b-selection-controls","--phase","postcontrol","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260724T063336Z","--no-prompt","--json"]
[".venv/bin/python","scripts/ui_ux_snapshot_matrix.py","--profile","ux1b-full-pages","--phase","pretheme","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260724T063336Z","--no-prompt","--json"]
```

Both plans retain the parent `CaptureRunnerPlan` execution contract: cwd `.`,
closed capture environment, stdin `devnull`, timeout `14400`, stdout and
stderr limits `67108864`, new process group, `passFds:["lease"]`,
`capture-coordinator-v1`, and `outer_pgid`.

The transaction is:

```text
global lock
-> capture lease
-> reauthenticate sequence 3 preflight
-> publish intent
-> launch postcontrol exactly once
-> verify 36 captures / 72 artifacts / 73 leaves
-> publish control checkpoint
-> reauthenticate all current authorities
-> publish pretheme gate
-> launch pretheme exactly once
-> verify 81 captures / 162 artifacts / 163 leaves
-> publish pretheme checkpoint
-> reopen complete chain and both manifests
-> publish terminal passed
```

The runner verifier MUST require terminal manifest status `passed`, exact
mode and phase, identical expected/captured counts, source start/end digest
equal to the sequence 3 preflight source digest, exact capture-stack digest,
sorted unique capture IDs, one PNG and one render sidecar per capture, exact
namespace leaf count, and all inner process receipts quiescent.

## Acceptance criteria

### `AC-TASK9-001` — sequence 3 authorization

Given the recovery document, when authorization is parsed, then the body has
sequence `3`, the new recovery ID, exact amendment and ledger references, and
no unknown or duplicate field.

### `AC-TASK9-002` — immutable predecessor

Given the sequence 2 evidence set, when sequence 3 bootstrap and preflight
run, then every imported file has its retained size and SHA-256, and no
sequence 2 inode, content, or mtime changes.

### `AC-TASK9-003` — production handler registry

Given valid public grammar, when `capture-task9` or `reconcile-task9`
dispatches, then the production registry calls its dedicated handler rather
than the unavailable handler.

### `AC-TASK9-004` — secure lifecycle

Given scratch roots containing symlink, non-directory, collision, stale
parent, postcommit uncertainty, and FD pressure fixtures, when Task 9 runs,
then it fails with the declared exit and performs no unauthorized follow-up
write.

### `AC-TASK9-005` — exact runner and bundle

Given an authenticated sequence 3 preflight, when each production runner
returns, then its exact argv launched once, the outer family is quiescent, and
the exact `36/72/73` or `81/162/163` bundle is reopened from disk.

### `AC-TASK9-006` — reconciliation

Given each valid lifecycle prefix, when reconciliation runs without an active
lease, then prefix four closes to passed, prefixes one through three close to
revoked, and no runner launches. Invalid or gapped chains fail closed.

### `AC-TASK9-007` — formal one-shot gate

Given all implementation, package, syntax, focused, full, manifest, and
independent-review gates pass, when the Make coordinator runs once, then the
terminal is passed and both launch counts equal one. Otherwise formal capture
does not start.

## Implementation checklist

- [ ] `IMPL-001`: Freeze this amendment and canonical traceability ledger,
  then publish the sequence 3 authorization body.
- [ ] `IMPL-002`: Add sequence 3 constants, imported sequence 2 authority
  records, and new fixed paths without mutating predecessor evidence.
- [ ] `IMPL-003`: Amend Tier 0 bootstrap to reopen the shared global lock,
  classify both Python modules as retained inputs, create only the new capture
  lease, and publish new prechange/rollback evidence.
- [ ] `IMPL-004`: Build production Task 9 context and exact runner plans from
  the authenticated sequence 3 preflight.
- [ ] `IMPL-005`: Implement descriptor-safe lifecycle reads/publications,
  global lock, capture lease, FD budget, and reconciliation.
- [ ] `IMPL-006`: Implement the bounded outer process driver and strict
  manifest/bundle verifier.
- [ ] `IMPL-007`: Enable the two public handlers and preserve closed public
  success/failure output shapes.
- [ ] `IMPL-008`: Add package, epoch, path-attack, fault, process, manifest,
  dispatch, and formal-gate tests.
- [ ] `IMPL-009`: Run focused and full gates, compare diff to this amendment,
  and close all blocking review findings.
- [ ] `IMPL-010`: Bootstrap and publish sequence 3 preflight; reopen it in a
  new process before the one formal Task 9 Make invocation.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-001` | Sequence 3 package and authorization validate; sequence 2 remains imported and exact. |
| `TEST-002` | New namespace is complete, unique, absent before bootstrap, and disjoint from sequence 2 outputs. |
| `TEST-003` | Production registry dispatches both Task 9 commands to dedicated handlers. |
| `TEST-004` | Component-walk, metadata, collision, uncertainty, stale-parent, and FD-budget attacks fail closed. |
| `TEST-005` | Every crash boundary keeps each stage launch count at most one and reconciliation never launches. |
| `TEST-006` | Production process fixtures prove timeout, overflow, interruption, exit, signal, observer, and quiescence mappings. |
| `TEST-007` | Manifest mutation matrix rejects count, mode, phase, source, stack, capture, artifact, leaf, and process drift. |
| `TEST-008` | Focused Task 9 tests and the complete verifier suite pass with zero unexpected failures. |
| `TEST-009` | Sequence 3 bootstrap and preflight reopen exactly; sequence 2 stat/content records remain unchanged. |
| `TEST-010` | Formal Make invocation occurs once only after all gates, then publishes a passed terminal. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-001` | `AC-TASK9-003`, `AC-TASK9-005`, `AC-TASK9-006` | `IMPL-004`, `IMPL-006`, `IMPL-007` | `TEST-003`, `TEST-005`, `TEST-006`, `TEST-007` |
| `REQ-002` | `AC-TASK9-001`, `AC-TASK9-002`, `AC-TASK9-007` | `IMPL-001`, `IMPL-002`, `IMPL-003`, `IMPL-010` | `TEST-001`, `TEST-002`, `TEST-009`, `TEST-010` |
| `CFR-001` | `AC-TASK9-005`, `AC-TASK9-006`, `AC-TASK9-007` | `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-005`, `TEST-006`, `TEST-010` |
| `CFR-002` | `AC-TASK9-004` | `IMPL-005`, `IMPL-008` | `TEST-004`, `TEST-008` |
| `CFR-003` | `AC-TASK9-004`, `AC-TASK9-005` | `IMPL-005`, `IMPL-006`, `IMPL-008` | `TEST-004`, `TEST-006`, `TEST-008` |
| `CFR-004` | `AC-TASK9-002`, `AC-TASK9-005`, `AC-TASK9-007` | `IMPL-002`, `IMPL-004`, `IMPL-010` | `TEST-001`, `TEST-007`, `TEST-009`, `TEST-010` |
| `CFR-005` | `AC-TASK9-003`, `AC-TASK9-004`, `AC-TASK9-006` | `IMPL-005`, `IMPL-007`, `IMPL-008` | `TEST-003`, `TEST-004`, `TEST-005`, `TEST-008` |

## Commands and gates

Implementation tests MUST use owned scratch workspaces. Before formal
publication, run:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run the relevant repository, API fail-soft, Streamlit fail-soft,
snapshot-matrix, compile, AST 3.10, tabnanny, hash, scope, descriptor, and
process-cleanup gates from the parent plan. Any current-change test failure is
blocking.

Formal execution order is:

```bash
make ui-ux1b-theme-handoff-bootstrap \
  UX1B_RECOVERY_ID=20260724T063336Z
make ui-ux1b-theme-handoff-preflight \
  UX1B_RECOVERY_ID=20260724T063336Z
make ui-ux1b-recovery-postcontrol \
  UX1B_RECOVERY_ID=20260724T063336Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T063336Z.json
```

The final command MUST NOT run until the new preflight is independently
reopened and two fresh changed-code reviews have no blocker.

## Risks and rollback

- A code edit after sequence 3 preflight publication invalidates that preflight
  and blocks capture.
- A crash after intent commit burns recovery ID `20260724T063336Z`.
- A publication result with uncertain commit state exits `6`; no later write
  occurs in that process.
- A partial chain is never resumed by a fresh runner. Reconciliation may only
  publish the declared terminal classification.
- Before sequence 3 bootstrap, rollback means removing only exact uncommitted
  sequence 3 code and authorization changes. User-owned unrelated worktree
  changes are never reverted.
- After sequence 3 Tier 0 publication, its evidence is immutable. Recovery
  requires another accepted amendment and new epoch.

## Review checklist

- [x] Scope, non-goals, audience, authority, success conditions, and rollback
  are explicit.
- [x] New paths are disjoint from sequence 2 lifecycle and output paths.
- [x] The shared global lock prevents sequence 2/3 coordinator concurrency.
- [x] Requirements have measurable acceptance criteria and bidirectional
  implementation/test links.
- [x] API and Streamlit fail-soft behavior remain out of scope and mandatory
  regression gates.
- [ ] Amendment and ledger hashes are frozen in sequence 3 code and
  authorization.
- [ ] Task 9 production code and tests satisfy every mapped criterion.
- [ ] Two fresh changed-code reviews report no blocking issue.
- [ ] Sequence 3 preflight reopens before formal capture.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-07-24 | Authorized a new epoch after sequence 2 sealed an unavailable Task 9 handler. |
