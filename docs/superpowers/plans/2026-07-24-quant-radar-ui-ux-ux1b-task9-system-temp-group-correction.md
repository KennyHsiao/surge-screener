# Quant Radar UX-1B Task 9 System Temp Group Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | 1.1 |
| Status | Accepted |
| Authorization | Maintainer instruction to continue the corrective workflow |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `5` |
| Recovery ID | `20260724T090000Z` |
| Tier ID | `20260724T091000Z` |
| Superseded active package | Sequence 4 runtime/reconcile correction |
| Imported predecessor | Sequence 4 plan, ledger, preflight, intent, and revoked terminal |

## Context

Sequence 4 fixed the two observed lifecycle defects and passed its complete
implementation, recovery, fail-soft, syntax, static, and fresh-preflight
gates. Its single authorized formal `capture-task9` invocation committed an
intent for recovery ID `20260724T081000Z`, created the previously absent
shared runtime root, and then failed closed before `Popen` with:

```text
Task 9 directory identity/metadata differs
```

The public reconcile path subsequently launched no runner and published the
declared revoked terminal with reason
`control_nested_quiescence_unverified`.

The failed Sequence 4 evidence is immutable:

| Artifact | SHA-256 | Size | Inode |
| --- | --- | ---: | ---: |
| Plan | `71da7b6f263e767c2c46821e3d84d18b980816ebf9adb0bf0e8efa002282cf6a` | 19473 | retained by source authority |
| Ledger | `cfbe561fa6f9b5a947cc915fd0a8c1f7e4c54166a813f360a9ddea5e18c43c4e` | 4400 | retained by source authority |
| Preflight | `945670b327c44fdcb7fe4ba2974d304907efef0740e8783ad9510cb722c3d38f` | 115848 | 12680803 |
| Intent | `2bc8aa38123c0f11edd85eb583d54a3f98c7edec959ce36a0ada4ff179e0d0d4` | 58696 | 12681955 |
| Revoked terminal | `1f89e14e53371221d496a9cbe0b173793842df587fb11753e2e7aeab705ace92` | 11067 | 12682369 |

Recovery ID `20260724T081000Z` is burned and MUST NOT be retried. Its
preflight, intent, and terminal MUST NOT be edited, deleted, renamed,
relinked, truncated, or reconciled again.

## Root-cause record

### `RC-004` — Darwin system-temp group inheritance

On this macOS host, `mkdirat(..., 0700)` below the root-owned sticky
`/private/tmp` creates a directory owned by the current UID but with group
`wheel` (GID `0`). The Sequence 4 helper immediately required the current
primary GID (`20`) and therefore rejected the newly created shared root:

```text
/private/tmp/quant-radar-ux1b-runtime
uid=501 gid=0 mode=0700
```

Every Sequence 4 regression used a current-UID/GID `TemporaryDirectory` as the
immediate parent. Those fixtures correctly tested absence, symlinks, unsafe
modes, existing epochs/stages, and child collisions, but did not exercise the
exact root-owned `/private/tmp` parent and therefore could not observe BSD
group inheritance.

A bounded production-like probe established the remediation primitive:

```text
mkdir below /private/tmp: gid 0
fchown(retained_fd, -1, current_gid): gid 20
final uid=501 mode=0700
```

The probe directory was removed after verification.

## Scope

### In scope

- Authorize Sequence 5 and recovery ID `20260724T090000Z`.
- Import and reauthenticate the exact Sequence 4 plan, ledger, preflight,
  intent, and revoked terminal as failed-attempt authority.
- Preserve all Sequence 1–3, Task 6, capture-stack, compatibility,
  global-lock, and fail-soft authority already imported by Sequence 4.
- Normalize only the retained shared runtime-root descriptor when the exact
  immediate parent is `/private/tmp`, the root is owned by the current UID,
  mode is `0700`, and its group is either root (`0`) or the current primary
  GID.
- Permit the exact empty Sequence 4 shared-root residue to be normalized and
  reused as the shared parent for a new, exclusive Sequence 5 epoch.
- Add a production-like regression whose immediate parent is the real
  root-owned `/private/tmp`.
- Create new Sequence 5 Tier 0, preflight, lifecycle, and capture namespaces.
- Run one formal Sequence 5 Task 9 capture only after all gates pass.

### Non-goals

- Do not retry, rewrite, or claim success for Sequence 4.
- Do not loosen UID, mode, path, no-follow, identity, epoch, stage, child, or
  collision checks.
- Do not normalize group metadata below any current-user scratch parent.
- Do not accept arbitrary inherited groups or path-based `chown`.
- Do not change API or Streamlit fail-soft behavior.
- Do not change UI, selectors, theme files, Task 6 artifacts, capture
  manifests, capture-stack authority, or compatibility postimages.
- Do not continue to migration, manual review, root publication, or theme
  application.

## Authority and precedence

The recovery authorization document MUST contain exactly one canonical V2
marker pair. Its body MUST authorize:

- integer `sequence:5`;
- recovery ID `20260724T090000Z`;
- this plan and its canonical sibling traceability ledger;
- the unchanged four-level precedence array.

The Sequence 5 package MUST reauthenticate:

1. this Sequence 5 plan and ledger;
2. the exact Sequence 4 plan and ledger;
3. the exact Sequence 4 passed preflight, intent, and revoked terminal;
4. the exact Sequence 3 plan, ledger, passed preflight, and intent-only
   failure;
5. the Sequence 2 amendment, ledger, and preflight;
6. the Sequence 1 parent plan and ledger;
7. the Task 6 manifests and all 234 artifacts;
8. capture-stack, runtime, selector-delta, compatibility, lock, and lease
   authority.

The resulting Tier 0 input set MUST contain exactly `301` live records and
`36` authority records. Both arrays are sorted and unique by path. Every
authority record is byte-for-byte the identical record in the live set.

Sequence 4 failure evidence is historical authority only. It MUST NOT
authorize Sequence 5 runners or appear in Sequence 5 eligible destinations.

## Fixed Sequence 5 namespace

The following destinations were verified absent before this plan was frozen:

```text
.claude/ui_snapshots/ux1b/recovery/.capture-20260724T090000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq5.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq5.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260724T091000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260724T090000Z.json
.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260724T090000Z/
.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260724T090000Z/
```

Later migration, review, candidate, intake, and root destinations retain the
Sequence 4 shape with the new recovery ID. The canonical root contract remains
absent.

## Requirements

### `REQ-005` — exact system-temp group normalization

The Task 9 shared runtime root MUST be retained with descriptor-relative,
no-follow operations. If and only if its immediate retained parent is the
exact root-owned `/private/tmp` with mode `1777`, the shared root is owned by
the current UID with mode `0700`, and its GID is exactly `0`, the coordinator
MAY call `fchown(root_fd, -1, os.getgid())`.

It MUST then re-`fstat` the same descriptor and require unchanged device/inode,
current UID/GID, and mode `0700` before creating an epoch or calling `Popen`.
Before initial postcontrol normalization or reuse, the coordinator MUST
enumerate that retained descriptor and require it to be empty. A newly created
shared root is subject to the same check. A pretheme reopen MUST instead
require the root to contain exactly the current recovery-epoch name; it MUST
not normalize group metadata during that active reopen.

### `CFR-010` — no normalization privilege broadening

An existing shared root with current GID is accepted unchanged. A shared root
with any other GID, wrong UID, unsafe mode, non-directory kind, symlink, or
identity drift is rejected. Below a current-user safe parent, every retained
directory continues to require the current UID/GID directly; no group
normalization is permitted.

Epoch, stage, and child creation remain exclusive. The Sequence 4 shared-root
residue confers no runner authority and no Sequence 4 epoch is accepted. Any
entry present during initial postcontrol setup is a collision. During
pretheme, any entry set other than the sole current Sequence 5 epoch is a
collision, and that epoch must still match the driver-retained device/inode.

### `CFR-011` — production-parent regression

At least one red-first regression MUST create a unique absent shared root
directly below the real `/private/tmp`, observe the host's inherited GID,
exercise the production helper, require the final current GID and mode `0700`,
and securely remove only that unique empty test leaf.

### `CFR-012` — predecessor immutability and compatibility

Sequence 4 evidence, earlier authority, API fail-soft behavior, Streamlit
fail-soft behavior, fresh/active destination policies, and intent-only
reconciliation semantics MUST remain exact.

## Corrected production design

`_task9_retain_directory_at()` gains a closed, default-false capability used
only by `_task9_open_temp_root()` after the latter has authenticated the exact
system parent. `_task9_open_temp_root()` also gains a closed
`Literal["initial","active"]` root policy. The capability permits one
transition:

```text
retained shared root:
  uid == current_uid
  mode == 0700
  gid in {0, current_gid}

if gid == 0:
  fchown(retained_fd, -1, current_gid)

reopen metadata on the same fd:
  identity unchanged
  uid == current_uid
  gid == current_gid
  mode == 0700
```

The capability MUST NOT be exposed to epoch, stage, child, or ordinary
current-user-parent retention. No pathname is used for the metadata change.
The `initial` policy requires an empty root and is used only for postcontrol.
The `active` policy requires the sole current recovery-epoch entry, performs no
normalization, and is used only for pretheme before the driver reopens its
retained epoch identity.

The existing Sequence 4 shared root is an operational directory, not a
published evidence artifact. Sequence 5 may normalize that exact safe retained
descriptor. It may not remove, replace, or trust any predecessor lifecycle
leaf. The new Sequence 5 epoch remains an exclusive `mkdirat`.

## Acceptance criteria

### `AC-SEQ5-001` — immutable predecessor import

Given the Sequence 5 package, package validation imports the exact five
Sequence 4 records and leaves their bytes, inode, mtime, size, and digest
unchanged.

### `AC-SEQ5-002` — production-like inherited group

Given a unique absent leaf directly below `/private/tmp`, creation initially
inherits GID `0` on this host; the retained-FD normalization produces the same
directory identity with current UID/GID and mode `0700`.

### `AC-SEQ5-003` — closed normalization

Wrong group outside the exact system-parent case, wrong owner, unsafe mode,
symlink, non-directory, and identity mutations fail before `Popen`.

### `AC-SEQ5-004` — existing shared root

Given the exact empty, current-owned, mode-`0700` Sequence 4 shared root with
GID `0`, Sequence 5 normalizes and reauthenticates it, then exclusively
creates only the new Sequence 5 epoch. A non-empty initial root is rejected.
The same driver then reopens the root under the active policy, requires exactly
that epoch entry, and reopens the retained epoch inode.

### `AC-SEQ5-005` — compatibility gates

All 39 handoff tests, complete recovery target, API/Streamlit fail-soft suites,
Python 3.10 AST, tabnanny, dependency, whitespace, source-cardinality,
predecessor-stat, and process-quiescence gates pass.

### `AC-SEQ5-006` — formal one-shot

After Tier 0 and preflight publish, a fresh process reopens the preflight.
Exactly one formal Sequence 5 capture invocation launches each runner stage at
most once and publishes a passed terminal. Otherwise no retry occurs.

## Implementation checklist

- [ ] `IMPL-019`: Freeze this plan and ledger; publish Sequence 5 authorization.
- [ ] `IMPL-020`: Add Sequence 5 namespaces and exact Sequence 4 authority.
- [ ] `IMPL-021`: Add red-first real-`/private/tmp` and closed-normalization
  regressions.
- [ ] `IMPL-022`: Implement retained-FD GID normalization only for the exact
  authenticated system-temp parent.
- [ ] `IMPL-023`: Run full recovery, fail-soft, static, scope, predecessor,
  and process-cleanup gates; fix all blocking review findings.
- [ ] `IMPL-024`: Bootstrap, preflight, fresh-process reopen, then invoke
  formal Task 9 exactly once.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-036` | Sequence 5 package imports exact Sequence 4 plan/ledger/preflight/intent/terminal and rejects mutations. |
| `TEST-037` | A unique absent leaf under real `/private/tmp` is FD-normalized from inherited GID 0 to current GID without identity change. |
| `TEST-038` | Normalization remains unavailable for ordinary parents and rejects wrong metadata before `Popen`. |
| `TEST-039` | The exact existing safe shared root is normalized, a new exclusive Sequence 5 epoch succeeds, and active reopen accepts only that retained epoch. |
| `TEST-040` | Complete recovery, fail-soft, static, source, predecessor, and process gates pass. |
| `TEST-041` | Sequence 5 bootstrap/preflight reopen and one formal Task 9 run satisfy the passed-terminal and at-most-once gate. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-005` | `AC-SEQ5-002`, `AC-SEQ5-004` | `IMPL-021`, `IMPL-022` | `TEST-037`, `TEST-039` |
| `CFR-010` | `AC-SEQ5-003`, `AC-SEQ5-004` | `IMPL-021`, `IMPL-022` | `TEST-038`, `TEST-039` |
| `CFR-011` | `AC-SEQ5-002` | `IMPL-021`, `IMPL-022` | `TEST-037` |
| `CFR-012` | `AC-SEQ5-001`, `AC-SEQ5-005`, `AC-SEQ5-006` | `IMPL-019`, `IMPL-020`, `IMPL-023`, `IMPL-024` | `TEST-036`, `TEST-040`, `TEST-041` |

## Commands and gates

Before Tier 0 or formal publication:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run the relevant API and Streamlit fail-soft suites, Python 3.10 AST,
tabnanny, dependency, whitespace, authorization-marker, source-cardinality,
predecessor-stat, new-namespace, temp-root, descriptor, and process-quiescence
checks.

The formal order is:

```bash
make ui-ux1b-theme-handoff-bootstrap \
  UX1B_RECOVERY_ID=20260724T090000Z
make ui-ux1b-theme-handoff-preflight \
  UX1B_RECOVERY_ID=20260724T090000Z
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-preflight \
  --recovery-id 20260724T090000Z --json
make ui-ux1b-recovery-postcontrol \
  UX1B_RECOVERY_ID=20260724T090000Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T090000Z.json
```

The final command is the only authorized formal Task 9 capture invocation for
Sequence 5.

## Risks and rollback

- Any committed Sequence 5 intent burns recovery ID `20260724T090000Z`.
- A failed `fchown` or post-change metadata mismatch fails before epoch
  creation or `Popen`.
- The metadata change is limited to the retained shared runtime-root
  descriptor. Published evidence and predecessor lifecycle paths are never
  changed.
- Before Sequence 5 Tier 0 publication, rollback removes only uncommitted
  Sequence 5 code and authorization changes while preserving unrelated dirty
  worktree files.
- After Tier 0 publication, Sequence 5 evidence is immutable; any further
  correction requires a new accepted plan and recovery epoch.

## Review checklist

- [x] The production failure and its exact immutable evidence are recorded.
- [x] The host-specific inherited GID was reproduced with a bounded probe.
- [x] The primitive was proven available on the retained descriptor.
- [x] Normalization is limited to the exact authenticated `/private/tmp`
  parent and GID `0`.
- [x] UID, mode, no-follow, identity, and exclusive-child checks remain strict.
- [x] Sequence 4 cannot be retried or mistaken for success.
- [x] New namespaces are absent and disjoint.
- [ ] Plan/ledger hashes and authorization body are frozen.
- [ ] Red-first tests fail before implementation and pass after.
- [ ] Changed-code review reports no blocking issue.
- [ ] Fresh-process preflight reopen passes before the formal one-shot.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.1 | 2026-07-24 | Split initial-empty normalization from active exact-epoch reopen so pretheme cannot reject the coordinator's own epoch. |
| 1.0 | 2026-07-24 | Added a new immutable epoch to correct Darwin `/private/tmp` GID inheritance without weakening directory authority. |
