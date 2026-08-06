# Quant Radar UX-1B Sequence 20 Post-W0 Lifecycle-Test Correction Continuation

## Document Control

| Field | Value |
|---|---|
| Type | Implementation plan and formal-state continuation |
| Version | `1.0-review-blocked` |
| Status | `REVIEWED DESIGN — implementation blocked by overlapping live-worktree drift` |
| Date | 2026-07-30 |
| Author | Scribe |
| Reviewer | Judge, then repository maintainer |
| Audience | Maintainer, implementation agent, formal reviewer, release gate |
| Sequence | `20` |
| Parent sequence | `19`, exact permanent state `W0_BOOTSTRAPPED` |
| Parent plan | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.md` |
| Parent ledger | Same Sequence 19 basename with `.traceability.yaml` |
| Parent authorization | `docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md` |
| Continuation ledger | Same Sequence 20 basename with `.traceability.yaml` |
| Intended handoff | Maintainer drift decision; no Builder handoff yet |

## Authority and Purpose

The separately accepted Sequence 19 authorization created an exact seven-
destination bootstrap prefix. The permanent classifier reopens:

```text
W0_BOOTSTRAPPED
```

The Sequence 19 preflight, manual-review publication, handoff candidate, and
theme root remain absent. The mandatory W0 coordinator, however, reports:

```text
169/176 passed
```

The seven unexpected failures are:

```text
TEST-200
TEST-202
TEST-203
TEST-206
TEST-207
TEST-208
TEST-209
```

These tests were green only while the permanent Sequence 19 namespace was
`0/7`. Five disposable tests still call an importer with
`require_initial=True`; two tests require the permanent namespace to remain
at `IMPLEMENTATION_BOUNDARY` or entirely absent. Those expectations reject
the now-valid W0 state.

The accepted Sequence 19 W0 historical package is immutable: its
authorization, six permanent file leaves, private Tier directory, and twelve
archived member bytes cannot be edited, deleted, or regenerated. The current
working-tree `Makefile`, source, and test files are protected incident
baseline inputs until this reviewed plan and ledger are accepted; after that
acceptance, only the narrow Sequence 20 edits described here are authorized.
The historical importer must authenticate their archived W0 bytes
independently of the later edited live paths.

This continuation makes all seven failing tests lifecycle-aware, adds a
distinct successor authority, and provides a new W0-to-W1 path without
reopening live Sequence 19 builders. It preserves eventual exact-copy
publication behavior but formally stops after the corrected W1 preflight
unless the maintainer later gives a separate publication instruction.

This plan and ledger authorize nothing by themselves. Because the overlapping
live-worktree blocker documented below is unresolved, their current exact
bytes are not an implementation-acceptance candidate. After the maintainer
chooses a drift disposition, the plan/ledger must be amended, re-reviewed,
and only then accepted by exact SHA-256, byte size, and mode before source
implementation. Implementation may later produce a distinct Sequence 20
authorization candidate. That candidate requires a second exact-byte
acceptance before any Sequence 20 formal write.

## Exact Incident State

### Frozen incident baseline and authority transition

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `Makefile` | `bee398efc0ac533352701915945e3798921ad7ec8cf0eb2dfa55bb797f1e719c` | 73798 | `0644` |
| `scripts/ui_ux_theme_handoff.py` | `aebb4b50b1e8204ab83254e998d80c0167dde995581a50afcbf4f239b5a4ca8a` | 1930717 | `0644` |
| `scripts/test_ui_ux_theme_handoff.py` | `925c639526c0ffe2d538bd2b3e989cf7e49cf66f919efd6962739e06fac71af4` | 1290500 | `0644` |
| Sequence 19 plan | `fc31a65bccf7f1681e2a0d2e61dffe8d0c38794e0351f86fd22842a14085d4e9` | 59164 | `0644` |
| Sequence 19 ledger | `c922ecaa4e600fe732bdf7d9af6cc8d87478bca2717c274712e64dece3d12110` | 33663 | `0644` |
| Sequence 19 authorization | `7c8a42b7fd45a1aa203c377390cffd0f51b9acff5b6429017724aab188abca92` | 11596 | `0644` |

The six rows above describe the exact W0/incident baseline. The three live
implementation paths have since drifted as disclosed below; the plan does
not authorize or revert that drift. After a separately amended and accepted
baseline, only `Makefile`, `scripts/ui_ux_theme_handoff.py`, and
`scripts/test_ui_ux_theme_handoff.py` may change for Sequence 20. The three
Sequence 19 planning/authorization records and every permanent W0 artifact
remain immutable. The W0 archive remains the authority for historical
working-tree bytes after any authorized live-file change.

### Exact permanent Sequence 19 W0

| Role | Path | SHA-256 | Size | Mode |
|---|---|---|---:|---:|
| Lease | `.claude/ui_snapshots/ux1b/recovery/external-review-v1-lifecycle-test-correction-20260730T050000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 | `0600` |
| Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-prechange-seq19.json` | `80b52aa482ea4484a06452c698659a127d1c372e4bcec2850a51d6c503cd7698` | 8898 | `0600` |
| Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-rollback-seq19.json` | `1b1575affed96b0db4485364e53bef8546c8643f585025ec167e05c998463d91` | 4880 | `0600` |
| Tier directory | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z` | directory | n/a | `0700` |
| Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/quant-radar-theme-handoff-external-review-v1-lifecycle-test-correction-owner` | `756f0d8d49834bd5086f2cead1394c6562d01cc38c3f6dc1434f79d9da207bd5` | 183 | `0600` |
| Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/prechange-files.tar` | `f59016fcce0366e55eafdfd49b0271516e727db05f6a9ee11952ec8888222a2e` | 3573760 | `0600` |
| Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/bundle-manifest.json` | `1f149a80f4202e979ae7d4718c1063056aebc0482f76a523b10cf338b7a1f007` | 1939 | `0600` |

The old preflight path is absent:

```text
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-preflight-20260730T050000Z.json
```

The manual-review path, downstream handoff candidate, theme root, and both
rejected dot-leading Sequence 19 components are absent. The W0 archive
contains exactly twelve sorted members. The historical `270/76` projection
is derived by replaying the accepted Sequence 19 builder semantics over
retained Sequence 18 V1 `270/73`: keep the source-mirror 270 exact, then
overlay every W0 package member outside the mirror into supplemental records.
This replaces the retained Makefile record and adds the Sequence 19 plan,
ledger, and authorization, while revalidating the other non-mirror members.
It is not falsely treated as a field stored by the absent Sequence 19
preflight.

### Baseline verification

The exact post-W0 baseline was previously reproduced with
`.venv/bin/python` as:

```text
169/176 passed
0 controlled missing-behavior failures
7 unexpected failures
```

No additional failure may be reclassified as part of this correction.
Fail-soft loader tests remain `14/14`; API tests remain `44/44`.

### Concurrent live-worktree blocker discovered during review

During the long-running Round 2 diagnostic, the shared workspace acquired
coherent overlapping Codex-provider migration edits outside this plan. The
three planned live inputs no longer match the frozen W0/incident bytes:

| Live path | Current SHA-256 | Current size | Frozen W0 SHA-256 | Frozen size |
|---|---|---:|---|---:|
| `Makefile` | `b8aebb969a1fe869a83e9193228f0e7aabb1b63a53616c59000ff4b973b61736` | 73790 | `bee398efc0ac533352701915945e3798921ad7ec8cf0eb2dfa55bb797f1e719c` | 73798 |
| `scripts/ui_ux_theme_handoff.py` | `6619c9e436f861c3507605e586e7225232c9f2250044496839a743884c250371` | 1930716 | `aebb4b50b1e8204ab83254e998d80c0167dde995581a50afcbf4f239b5a4ca8a` | 1930717 |
| `scripts/test_ui_ux_theme_handoff.py` | `61897c377422e6bcf9b50f513ff6afe8db9e3882ee1f10b8a4a2845e9d382142` | 1290498 | `925c639526c0ffe2d538bd2b3e989cf7e49cf66f919efd6962739e06fac71af4` | 1290500 |

The content is a coherent Claude-to-Codex provider migration, not test
fixture residue: Make routes and timeout/provider variables changed, and the
source/test POST-036 contract changed from Claude auth to Codex auth. Other
concurrent protected changes also affect `requirements.txt`,
`scripts/ui_ux_fixtures.py`, and retained capture-stack authentication.
Because the workspace is shared and no syscall trace exists, this plan does
not assign ownership, revert, incorporate, or authorize those edits.

The first diagnostic that overlapped those writes returned:

```text
155/176 passed
0 controlled missing-behavior failures
21 unexpected test failures
1 unexpected WORKSPACE-GUARD failure
```

The seven Sequence 20 targets remain among those failures. The other failures
are TEST-005/006/013/017/021/026/033/034/035/136/148/149/150/151 plus the
workspace guard. This is not an acceptable replacement baseline.

After the overlapping file mtimes stabilized, a fresh coordinator run
returned:

```text
135/176 passed
0 controlled missing-behavior failures
41 unexpected failures
```

The original seven Sequence 20 failures are still present. The other 34
failures include the previously named requirements/fixture/capture-stack
groups plus Sequence 8 runtime-root and Sequence 12 runtime-authority
failures. This clean run confirms that rebasing only the three overlapping
Codex-migration files cannot restore the seven-only entry condition.

**Blocking decision:** before exact plan/ledger acceptance or implementation,
the maintainer must choose one of two separately verified paths:

1. preserve the concurrent migration and finish its separately owned
   requirements/fixture/runtime-authority corrections until a clean
   seven-only baseline can be reproduced, then amend Sequence 20 with the
   final overlapping bytes; or
2. explicitly declare the concurrent changes disposable and separately
   restore the live inputs to the exact frozen W0 baseline.

No Sequence 20 implementation, candidate generation, bootstrap, or preflight
may start while this decision is unresolved.

## Root Cause

1. `_sequence19_lifecycle_fixture()` calls
   `_import_sequence18_v1_intake(..., require_initial=True)` before it patches
   disposable aliases. A valid permanent Sequence 19 W0 therefore blocks
   TEST-203/206/207/208 and contributes to TEST-200.
2. TEST-202 hard-codes the permanent classifier result as
   `IMPLEMENTATION_BOUNDARY`.
3. TEST-209 hard-codes complete Sequence 19 formal absence.
4. The Sequence 19 plan required checkpoint-complete testing, but the
   implementation only made predecessor tests lifecycle-aware. The
   successor's own new tests were not exercised after permanent bootstrap.
5. Editing the frozen test file directly would invalidate the accepted W0
   source authority. Deleting exact W0 leaves would destroy formal history.

## Decision Summary

- Treat exact Sequence 19 W0 as immutable historical input.
- Never call live Sequence 19 projection, archive, Tier, preflight, or
  workspace-classifier builders to authenticate that history.
- Correct exactly TEST-200/202/203/206/207/208/209.
- Keep TEST-201/205 as exact Sequence 19 authorization/parser history checks.
- Keep TEST-204 as a non-authoritative live-builder compatibility test; it
  cannot prove immutable W0 history, which is the sole responsibility of
  TEST-210.
- Add TEST-210..213 for the new importer, successor authority, geometry, and
  permanent-checkpoint matrix.
- Add a distinct Sequence 20 authorization, Tier, preflight, CLI grammar,
  Make routes, and read-only classifier.
- Close all four Sequence 19 public routes before their operation bodies once
  the corrected source is active.
- Preserve create-once publication behavior in disposable tests and the
  successor engine, but stop formal execution at corrected `W1_READY`.
- Require the complete coordinator at implementation, candidate, formal
  bootstrap, formal preflight, and any later publication checkpoint.

## Scope

### In scope

- `Makefile`
- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- this plan and sibling ledger
- one later Sequence 20 authorization candidate
- later Sequence 20 Tier/preflight artifacts after separate acceptance
- exact W0 historical importer
- lifecycle-aware correction of the seven failing tests
- TEST-210..213
- Builder, Radar, Scribe, Judge, and project journals

### Out of scope

- modifying or deleting any Sequence 19 W0 artifact
- creating the old Sequence 19 preflight
- editing Sequence 17/18/19 accepted plans, ledgers, or authorizations
- changing the accepted review intake
- capture, comparison, reviewer submission, image, sidecar, UI, API, provider,
  data-pipeline, or theme work
- manual-review publication during this plan-authoring task
- handoff candidate or theme-root creation
- dependency changes
- global publisher-policy changes
- git cleanup, reset, checkout, or unrelated worktree edits

## Requirements

### `REQ-022` — Correct post-W0 tests and restore a safe W1 path

The system must retain exact Sequence 19 W0, correct the seven stale tests,
and provide a distinct authorized continuation that reaches a verified
corrected W1 without deleting or disguising formal history.

### `CFR-109` — Immutable Sequence 19 W0 import

A standalone importer must authenticate the exact authorization, six W0 file
leaves, W0 directory contract, twelve-member PAX, retained Sequence 18
`270/73` projections, deterministically derived W0 `270/76` projections,
nested exact Sequence 18 V1 authority, and absence of the old preflight. It
must not call mutable Sequence 19 live builders.

### `CFR-110` — Lifecycle-aware permanent and disposable tests

The seven corrected tests must distinguish permanent authenticated state from
disposable creation state. Permanent assertions must accept only exact
states from the closed Sequence 20 state table. Disposable aliases must cover
creation, crash, mutation, and cleanup without requiring permanent absence.

### `CFR-111` — Successor authorization and old-route interlock

Sequence 20 must use a distinct marker, schema, IDs, paths, and commands. All
four Sequence 19 public routes must fail as superseded before any old
operation body after corrected source activation. Historical reads remain
available only through the immutable importer.

### `CFR-112` — Exact successor package and geometry

The successor package must contain fifteen unique sorted members. Projection,
content, authority, retained-leaf, descriptor-floor, and PAX counts must be
derived from unique exact paths and must equal the arithmetic in this plan.

### `CFR-113` — Create-once successor lifecycle

Bootstrap, preflight, verify, and later publication must be idempotent,
fail-closed on partial or mixed prefixes, preserve committed exact leaves,
and use atomic no-replace publication with read-only lost-response
reconciliation.

### `CFR-114` — Checkpoint-complete coordinator verification

The complete coordinator must pass at all five permanent checkpoints:
implementation before candidate, after candidate, successor bootstrap,
successor preflight, and any later publication. A test that requires a
permanent create-once namespace to remain absent is prohibited.

### `CFR-115` — Protected scope and fail-soft compatibility

All retained formal history, unrelated worktree state, fail-soft loader
behavior, API behavior, Python syntax, dependency integrity, descriptor
limits, and downstream absence must remain exact.

### `CFR-116` — Separate acceptance and W1 stop

Exact plan/ledger acceptance authorizes implementation only. Exact
authorization-candidate acceptance is separately required before formal
bootstrap or preflight. Formal execution must stop after corrected
`W1_READY`; publication requires a later explicit maintainer instruction.

## Sequence 20 Authority Contract

### Exact identities

| Field | Exact value |
|---|---|
| Capture ID | `20260729T040000Z` |
| Packet continuation ID | `20260729T060000Z` |
| Parent Sequence 19 correction ID | `20260730T050000Z` |
| Sequence 20 correction ID | `20260730T070000Z` |
| Sequence 20 Tier ID | `20260730T071000Z` |
| Marker | `UX1B_FORMAL_HANDOFF_EXTERNAL_REVIEW_W0_LIFECYCLE_TEST_CORRECTION_CONTINUATION_V1` |
| Schema | `quant-radar-ui-ux-formal-handoff-external-review-w0-lifecycle-test-correction-continuation-authorization/v1` |
| Authorization path | `docs/ui-ux/quant-radar-ui-v2-ux1b-sequence20-post-w0-lifecycle-test-correction-continuation-authorization.md` |
| Current formal stop | `W1_READY` |
| Eventual publication state | `W2_REVIEW` |

### Exact commands

```text
bootstrap-external-review-w0-lifecycle-test-correction
preflight-external-review-w0-lifecycle-test-correction
verify-external-review-w0-lifecycle-test-correction-preflight
publish-w0-lifecycle-test-corrected-review
```

No submit command exists. The exact accepted intake already exists. No
reconcile command exists; publication performs read-only exact-output
reconciliation when its destination already exists.

The exact Make variables are:

```text
UX1B_W0_LIFECYCLE_CAPTURE_ID
UX1B_W0_LIFECYCLE_PACKET_CONTINUATION_ID
UX1B_W0_LIFECYCLE_PARENT_CORRECTION_ID
UX1B_W0_LIFECYCLE_CORRECTION_ID
UX1B_W0_LIFECYCLE_TIER_ID
```

The exact Make targets, in command order, are:

```text
ui-ux1b-external-review-w0-lifecycle-test-bootstrap
ui-ux1b-external-review-w0-lifecycle-test-preflight
ui-ux1b-external-review-w0-lifecycle-test-verify
ui-ux1b-external-review-w0-lifecycle-test-publish
```

Every target requires all five variables before invoking its matching
command with these exact common arguments and terminal `--json`:

```text
--capture-id
--packet-continuation-id
--parent-v1-lifecycle-test-correction-id
--w0-lifecycle-test-correction-id
--w0-lifecycle-test-tier-id
--json
```

### Exact inherited forward paths

The successor binds this ordered six-path inventory without acquiring
capture, compare, submit, downstream-candidate, root, or theme authority:

| Order | Role | Exact relative path |
|---:|---|---|
| 1 | Report | `.claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json` |
| 2 | Packet | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json` |
| 3 | Accepted intake / publication source | `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json` |
| 4 | Manual review / publication destination | `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json` |
| 5 | Downstream handoff candidate | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T060000Z.json` |
| 6 | Theme root | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` |

The report, packet, and intake are existing exact historical inputs. The
manual-review destination remains absent through W1. The downstream handoff
candidate and theme root remain absent and forbidden in every state. The
Sequence 20 authorization candidate is a different record at the
authorization path named above.

### Exact lifecycle states

| Checkpoint | State | Authorization record | Parent Sequence 19 | Current bootstrap | Current preflight | Manual review | Handoff candidate / theme root |
|---|---|---|---|---:|---|---|---|
| Pre-candidate implementation | `IMPLEMENTATION_BOUNDARY` | absent | exact W0 | `0/7` | absent | absent | absent |
| Post-candidate, pre-acceptance | `IMPLEMENTATION_BOUNDARY` | exact candidate bytes | exact W0 | `0/7` | absent | absent | absent |
| Accepted bootstrap | `X0_BOOTSTRAPPED` | exact accepted bytes | exact W0 | `7/7` | absent | absent | absent |
| Accepted preflight | `W1_READY` | exact accepted bytes | exact W0 | `7/7` | exact | absent | absent |
| Later publication | `W2_REVIEW` | exact accepted bytes | exact W0 | `7/7` | exact | exact-copy | absent |

The read-only classifier reports formal state and authorization-record status
as separate values. It may return `IMPLEMENTATION_BOUNDARY` with the
authorization record either absent or byte-exact, and must reject a partial
or drifted authorization record. Every write route additionally requires the
byte-exact authorization and the applicable external maintainer acceptance.
Any other formal prefix, any old Sequence 19 preflight, mixed old/current
leaf, downstream handoff-candidate/theme-root presence, or drifted exact
record is a contract error.

### Exact new Tier destinations

| Order | Role | Relative path |
|---:|---|---|
| 1 | Lease | `.claude/ui_snapshots/ux1b/recovery/external-review-w0-lifecycle-test-correction-20260730T070000Z.lease` |
| 2 | Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-w0-lifecycle-test-correction-prechange-seq20.json` |
| 3 | Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-w0-lifecycle-test-correction-rollback-seq20.json` |
| 4 | Tier directory | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-w0-lifecycle-test-correction-prechange-20260730T071000Z` |
| 5 | Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-w0-lifecycle-test-correction-prechange-20260730T071000Z/quant-radar-theme-handoff-external-review-w0-lifecycle-test-correction-owner` |
| 6 | Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-w0-lifecycle-test-correction-prechange-20260730T071000Z/prechange-files.tar` |
| 7 | Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-w0-lifecycle-test-correction-prechange-20260730T071000Z/bundle-manifest.json` |
| 8 | Preflight | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-w0-lifecycle-test-correction-preflight-20260730T070000Z.json` |

The two corresponding dot-leading lease/owner aliases are permanently
rejected. The unchanged component predicate is
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. Tier directory mode is `0700`; file
leaves are regular current-uid/gid, mode `0600`, nlink `1`.

### Authorization body

The canonical authorization must bind:

- marker, schema, sequence, five IDs, four commands, Make/CLI interface,
  state table, exact six forward paths, Tier paths, rejected paths, and W1
  formal stop;
- this reviewed plan and ledger;
- exact Sequence 17/18/19 planning and authorization history;
- all sixteen immutable Sequence 18 V1 authority leaves;
- all six exact Sequence 19 W0 file leaves and directory contract;
- old Sequence 19 preflight absence;
- exact report, packet, and accepted intake;
- exact fifteen-member package and all geometry counts;
- supersession of all four Sequence 19 public commands;
- no submit, capture, compare, downstream handoff-candidate, root, UI, or
  theme authority;
- the exact publication source/destination, create-once no-replace operation,
  byte identity, different inode, mode `0600`, and read-only reconciliation;
- separate `authorizationRecordStatus` and formal-state classification;
- no publication before a later explicit maintainer instruction;
- `status: AUTHORIZED`.

The Markdown envelope must be canonical and reject duplicate keys, unknown
fields, wrong Unicode spelling, non-canonical JSON, replayed Sequence 19
authorization, trailing bytes, wrong mode, or mismatched digest.

## Historical W0 Import Contract

The importer must:

1. open the workspace and source root by retained directory descriptors;
2. authenticate exact Sequence 19 plan, ledger, and authorization;
3. authenticate the six W0 files and `0700` Tier directory without following
   symlinks;
4. require the Tier directory to contain exactly owner, archive, and bundle;
5. authenticate the twelve-member archive as one exact PAX file;
6. validate stored prechange/rollback/bundle relationships;
7. authenticate the embedded exact Sequence 18 V1 preflight projections:
   source `270` with digest
   `2e5c77d67a7c2383c0618252076b74ae805661b4c7acef0a82db1439d1e91a4a`
   and supplemental `73` with digest
   `98b1ca4f879a978644a532a023faefb5beba5c311ea54cf5145a7d901e4aa125`;
8. replay exact Sequence 19 projection semantics over all twelve archived
   package members: retain the Sequence 18 source-mirror 270 unchanged and
   skip package paths already in that mirror; for every non-mirror package
   path, overlay its archived record into supplemental 73 with projection
   mode `0444`; this reauthenticates existing records, replaces the Makefile
   record, and adds the Sequence 19 plan, ledger, and authorization;
9. deduplicate and exact-path sort the supplemental records, require count
   `76`, and require derived digest
   `dab6ca9cb8043d657b3b6c21efd0eda6516aad57323ec9d63face15f49ef0fb8`;
10. validate the embedded exact Sequence 18 V1 and its sixteen authorities;
11. require old preflight, manual review, downstream handoff candidate, theme
    root, and rejected paths absent at the parent boundary;
12. return a pure `S19_W0_BOOTSTRAPPED` historical value with derived
    `270/76` projections and twenty-two historical authority leaves;
13. never invoke current Sequence 19 projection, PAX, Tier, preflight,
    classifier, bootstrap, verify, or publish helpers.

Mutation tests must independently cover authorization, each W0 leaf,
directory membership, nested parent authority, archive digest, projection
count, and old-preflight insertion.

## Current Source Authority

### Exact ordered package

The successor package has these fifteen lexicographically sorted unique
paths:

```text
Makefile
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence20-post-w0-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence20-post-w0-lifecycle-test-correction-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence20-post-w0-lifecycle-test-correction-continuation-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

The candidate is generated only after final implementation verification. A
virtual exact record may solve its self-binding, but candidate bytes must not
be written before the full pre-candidate gate.

### Projection and descriptor arithmetic

| Quantity | Exact value | Derivation |
|---|---:|---|
| Source projection | 270 | unchanged product/runtime projection |
| Supplemental projection | 79 | prior 76 + Sequence 20 plan/ledger/auth |
| Content leaves | 640 | prior 637 + three unique package paths |
| Parent authority leaves | 22 | exact Sequence 18 V1 sixteen + Sequence 19 W0 six |
| Current authority leaves | 7 | new lease, prechange, rollback, owner, archive, bundle, preflight |
| Authority leaves | 29 | 22 + 7 |
| Retained leaves | 669 | 640 + 29 |
| Protocol allowance | 252 | unchanged parent contract |
| Descriptor reserve | 64 | unchanged parent contract |
| Required soft floor | 985 | 669 + 252 + 64 |
| Raise ceiling | 1536 | unchanged |
| PAX members | 15 | sorted package |

Every set is deduplicated by exact relative path before counting. Authority
partitions must be disjoint from content. Descriptor checks must retain every
leaf through commit and restore the caller's original soft limit.

## Lifecycle-Aware Test Contract

### Seven existing tests to correct

| Test | Required correction |
|---|---|
| TEST-200 | Import permanent Sequence 18 V1 with successor presence allowed, and separately assert exact Sequence 19 W0 history without live builders. |
| TEST-202 | Replace hard-coded permanent `IMPLEMENTATION_BOUNDARY` with the closed Sequence 20 permanent state oracle; keep a disposable full-state walk. |
| TEST-203 | Build disposable aliases from immutable W0 inputs and preserve partial/mixed-prefix rejection. |
| TEST-206 | Exercise create-once successor bootstrap/preflight with permanent W0 left untouched. |
| TEST-207 | Exercise atomic successor publication only in disposable scope; permanent W1 remains the formal stop. |
| TEST-208 | Exercise `640/29/669/985` descriptor boundaries and exact limit restoration. |
| TEST-209 | Replace total-absence assertion with the exact permanent-state presence matrix; the authorization record follows its separate absent/exact column while downstream handoff candidate/theme root remain absent in every state. |

TEST-201 and TEST-205 remain exact historical authorization/parser checks.
TEST-204 remains a non-authoritative live-builder compatibility test: it may
prove deterministic builder shape and cardinality, but it must not be cited
as proof of accepted W0 bytes or projections. TEST-210 is the sole immutable
W0 package/projection proof. Any edit to TEST-201/204/205 requires a reviewed
explanation and unchanged coverage.

### New tests

| Test | Purpose |
|---|---|
| TEST-210 | Immutable Sequence 19 W0 importer rejects every live-builder call and every exact-ref mutation; it authenticates retained Sequence 18 `270/73`, replays the twelve-member non-mirror overlay, and derives the exact W0 `270/76` digest. |
| TEST-211 | Sequence 20 marker/schema/IDs/commands are distinct; all four Sequence 19 public routes are closed. |
| TEST-212 | Fifteen-member deterministic PAX and `270/79/640/29/669/985` geometry are exact. |
| TEST-213 | Registry, Make, traceability, protected refs, and the permanent five-checkpoint matrix remain exact. |

### Test-quality requirements

- No test may infer permanent lifecycle state from absence alone.
- Every disposable fixture patches all Tier, preflight, forward, review, and
  rejected-path alias families before creation.
- No disposable test may delete, chmod, rename, or shadow permanent W0.
- Permanent-state assertions use the read-only Sequence 20 classifier.
- Each of the seven corrected tests must call at least one newly registered
  Sequence 20 seam. Combined with TEST-210..213, fail-first therefore has
  exactly eleven controlled missing-behavior results; a corrected test that
  passes without reaching a new seam is a test-design failure.
- TEST-201/204/205 must stay green during fail-first and are not counted among
  the eleven controlled results.
- The complete coordinator target is `180/180`.
- The full suite must run before candidate, after candidate, after successor
  bootstrap, after successor preflight, and after any later publication.
- Fail-first after test registration must produce exactly eleven controlled
  missing-behavior results and zero unexpected failures.

### Given-When-Then scenarios

| ID | Scenario |
|---|---|
| `SC-SEQ20-001-HP` | Given exact parent W0, when the historical importer runs, then it returns `S19_W0_BOOTSTRAPPED` without live builders. |
| `SC-SEQ20-001-NP` | Given any W0 byte or directory drift, when import runs, then it fails closed without writes. |
| `SC-SEQ20-002-HP` | Given any exact permanent successor state, when the coordinator runs, then all 180 tests pass. |
| `SC-SEQ20-002-BP` | Given implementation/candidate/X0/W1/W2 checkpoints, when state is classified, then only the closed table is accepted. |
| `SC-SEQ20-002-NP` | Given a permanent total-absence assertion, when W0 exists, then the test design is rejected. |
| `SC-SEQ20-003-HP` | Given corrected source, when an old Sequence 19 route is called, then it fails as superseded before its body. |
| `SC-SEQ20-003-NP` | Given absent, malformed, replayed, or drifted Sequence 20 authority, when a new command runs, then no write occurs. |
| `SC-SEQ20-004-HP` | Given the fifteen package paths, when PAX is generated twice, then bytes and order are identical. |
| `SC-SEQ20-004-BP` | Given 984/985/1536 descriptor limits, when retained materials are opened, then boundary behavior is exact and limits restore. |
| `SC-SEQ20-004-NP` | Given duplicate or overlapping material paths, when geometry is built, then it fails before publication. |
| `SC-SEQ20-005-HP` | Given exact parent W0 and authority, when bootstrap/preflight run, then X0 and W1 are create-once and reopen exactly. |
| `SC-SEQ20-005-EP` | Given a fault after any rename/fsync boundary, when retried, then exact committed prefixes reconcile without deletion. |
| `SC-SEQ20-005-NP` | Given a partial, mixed, symlinked, or wrong-mode prefix, when classified, then it fails closed. |
| `SC-SEQ20-006-HP` | Given W1 and a later explicit publication instruction, when exact intake is copied, then review is byte-identical and a different inode. |
| `SC-SEQ20-006-NP` | Given no later publication instruction, when formal W1 verification completes, then manual review remains absent. |
| `SC-SEQ20-007-HP` | Given accepted plan bytes, when implementation completes, then only the candidate is generated and formal paths remain absent. |
| `SC-SEQ20-007-NP` | Given unaccepted or changed plan/candidate bytes, when formal commands are attempted, then they fail before writes. |
| `SC-SEQ20-008-HP` | Given any checkpoint, when fail-soft/API/static gates run, then existing behavior and protected history remain exact. |
| `SC-SEQ20-008-NP` | Given unexplained source, config, dependency, UI, or formal drift, when scope review runs, then completion is blocked. |

## Acceptance Criteria

### `AC-SEQ20-001` — exact immutable W0 import

Given exact permanent Sequence 19 W0, when the historical importer runs with
all live Sequence 19 builders patched to raise, then it authenticates twelve
package members, retained Sequence 18 digests `270/73`, production-parity
non-mirror overlay and derived historical W0 digest `270/76`, twenty-two
historical authority leaves, and no old preflight without writes.

### `AC-SEQ20-002` — seven lifecycle-aware corrections

Given any exact permanent state in the closed table, when
TEST-200/202/203/206/207/208/209 run, then they preserve permanent history,
exercise creation in disposable scope, and pass without total-absence
assumptions.

### `AC-SEQ20-003` — fail-closed successor boundary

Given corrected source, when old routes or invalid successor authority are
invoked, then old routes fail as superseded and new routes fail before writes.

### `AC-SEQ20-004` — exact package and descriptor geometry

Given the final candidate, when package, projection, material, and descriptor
profiles are built twice, then they are deterministic and equal
`15`, `270/79`, and `640/29/669/985`.

### `AC-SEQ20-005` — create-once lifecycle and publication

Given exact authority and parent W0, when disposable or later authorized
formal transitions run, then X0/W1/W2 are atomic, idempotent, exact-prefix,
and recover safely after every injected boundary.

### `AC-SEQ20-006` — checkpoint-complete verification

Given implementation, candidate, X0, W1, or W2 permanent state, when the full
coordinator runs, then it passes `180/180` with zero controlled or unexpected
failures.

### `AC-SEQ20-007` — protected scope and compatibility

Given the correction, when repository gates run, then parent W0, accepted
history, fail-soft `14/14`, API `44/44`, syntax, dependencies, cleanup,
descriptor restoration, and downstream absence all pass.

### `AC-SEQ20-008` — acceptance boundaries and W1 stop

Given plan and candidate acceptance boundaries, when each phase completes,
then implementation precedes candidate acceptance, formal writes follow
candidate acceptance, and the current execution stops at W1 without
publication.

## Implementation Checklist

- [ ] `IMPL-171` Freeze exact W0 refs and baseline `169/176`.
- [ ] `IMPL-172` Add standalone immutable Sequence 19 W0 importer.
- [ ] `IMPL-173` Add old-route supersession interlock before old bodies.
- [ ] `IMPL-174` Correct TEST-200/202/203/206/207/208/209.
- [ ] `IMPL-175` Add lifecycle-aware disposable fixture and TEST-210..213.
- [ ] `IMPL-176` Add Sequence 20 constants, parser, marker, and body.
- [ ] `IMPL-177` Add exact package, projection, geometry, and PAX builders.
- [ ] `IMPL-178` Add X0/W1/W2 classifier and create-once engines.
- [ ] `IMPL-179` Add four CLI handlers, registry entries, and Make targets.
- [ ] `IMPL-180` Run five-checkpoint, compatibility, static, and scope gates.
- [ ] `IMPL-181` Generate exact candidate and stop for acceptance.

## Implementation Phases and Gates

### Phase S20-0 — resolve overlapping drift, amend, and re-review

1. Obtain the maintainer's explicit preserve-or-restore decision for the
   concurrent overlapping changes.
2. Do not edit those changes under Sequence 20 authority.
3. After the chosen external state is stable, freeze its exact live refs and
   reproduce a valid coordinator baseline.
4. Amend this plan and ledger with the resolved baseline and any necessary
   scope-preservation rules.
5. Re-run blocking review and reciprocal validation.
6. Only then report final SHA-256, size, and mode and stop for exact
   maintainer acceptance.

**Gate:** current `1.0-review-blocked` bytes must not be accepted for
implementation; no source/test/Make edit may occur under Sequence 20.

### Phase S20-1 — exact baseline and fail-first tests

1. Reauthenticate parent W0 and all protected refs against the resolved
   amended live baseline.
2. Reproduce the amended exact baseline with only the seven Sequence 20
   target failures.
3. Correct the seven tests and register TEST-210..213 before production seams.
4. Require every corrected test and every new test to reach at least one new
   Sequence 20 seam.
5. Require exactly eleven controlled missing-behavior results, unchanged
   TEST-201/204/205 green, and zero unexpected results.

**Gate:** any extra failure or permanent write stops implementation.

### Phase S20-2 — immutable importer and supersession

1. Implement exact W0 importer without live Sequence 19 builders.
2. Close all four Sequence 19 public routes before their bodies.
3. Keep historical reads open only through the new importer.
4. Re-run focused mutation and no-write tests.

**Gate:** parent W0 must reopen exact after source activation.

### Phase S20-3 — successor authority and lifecycle

1. Implement marker/schema/body/parser and distinct IDs.
2. Implement fifteen-member PAX and exact geometry.
3. Implement X0/W1/W2 classifier and create-once transitions.
4. Add CLI/registry/Make routes.

**Gate:** disposable lifecycle, faults, cleanup, modes, and descriptors pass.

### Phase S20-4 — pre-candidate verification

1. Run full coordinator and require `180/180`.
2. Run fail-soft loader `14/14` and API `44/44`.
3. Run Python syntax, Python 3.10 AST, tabnanny, dependency, Make dry-run,
   whitespace, protected-ref, PAX, descriptor, cleanup, and absence gates.
4. Compare actual diff with this plan and fix unexplained drift.

**Gate:** all tests green while candidate and every new formal path are absent.

### Phase S20-5 — candidate generation and second checkpoint

1. Generate canonical authorization candidate atomically at mode `0644`.
2. Parse it through production parser.
3. Generate PAX twice and require byte identity.
4. Re-run full `180/180` coordinator after candidate presence.
5. Report exact candidate/source/test/Make hashes and stop.

**Gate:** no formal command before separate exact candidate acceptance.

### Phase S20-6 — formal bootstrap and X0 checkpoint

1. Reauthenticate exact candidate, package, parent W0, and empty successor
   namespace.
2. Run bootstrap once.
3. Require `X0_BOOTSTRAPPED`, exact `7/7`, and preflight absent.
4. Run full `180/180` coordinator and protected gates.
5. Stop if any check fails; never delete committed exact leaves.

### Phase S20-7 — formal preflight and mandatory W1 stop

1. Run preflight once.
2. Require `W1_READY` and exact preflight.
3. Run public verify and full `180/180` coordinator.
4. Confirm the exact accepted authorization remains present while manual
   review, downstream handoff candidate, and theme root remain absent.
5. Stop and report W1 exact evidence.

**Gate:** do not publish manual review in this execution phase.

### Phase S20-8 — later publication only by separate instruction

1. Reauthenticate exact W1 and all retained materials.
2. Require an explicit maintainer publication instruction.
3. Copy accepted intake atomically to manual review.
4. Require byte identity, different inode, exact mode, and `W2_REVIEW`.
5. Run full `180/180` and stop.

## Affected Files

### Planning outputs in this task

- this plan
- sibling `.traceability.yaml`
- `.agents/scribe.md`
- `.agents/judge.md`
- `.agents/PROJECT.md`

### Planned implementation edits after exact acceptance

- `Makefile`
- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- skill/project journals

### Later candidate after implementation gates

- `docs/ui-ux/quant-radar-ui-v2-ux1b-sequence20-post-w0-lifecycle-test-correction-continuation-authorization.md`

### Later formal outputs after candidate acceptance

- seven Sequence 20 bootstrap destinations
- one Sequence 20 preflight
- manual review only after a later separate instruction

## Verification Commands

Use `.venv/bin/python` for all Python commands.

```text
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B -m py_compile scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Implementation must also run:

- focused TEST-200..213, including unchanged TEST-201/204/205 and corrected
  TEST-200/202/203/206/207/208/209;
- deterministic double-PAX generation;
- exact parent W0 classifier/importer verification;
- protected SHA/mode verification;
- Make dry-runs for all four new targets;
- Python 3.10 feature parse;
- descriptor boundary and limit restoration;
- temporary-file, lease, and disposable-fixture cleanup;
- new formal-path presence matrix for the current state;
- actual-diff versus accepted-plan review.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Repeat the same lifecycle-test blocker after X0/W1 | Mandatory full coordinator at five permanent checkpoints; permanent tests use a closed state oracle. |
| Live source rebuild invalidates historical W0 | Standalone exact importer; live Sequence 19 builders patched to raise in TEST-210. |
| Old route writes with drifted source | Supersession guard runs before every old operation body. |
| Authority undercount | Retain exact sixteen Sequence 18 plus six Sequence 19 W0 plus seven current leaves. |
| Descriptor exhaustion | Exact 985 floor, 1536 ceiling, retained-FD transaction, and restoration tests. |
| Partial create-once prefix | Closed prefix classifier and every-boundary fault matrix. |
| Unintended W2 publication | Mandatory W1 stop and later explicit maintainer instruction. |
| Scope drift into UI/API/theme | Protected hashes, affected-file allowlist, fail-soft/API regression gates. |
| Candidate changes package after tests | Run full coordinator both before and after candidate generation. |
| Plan/ledger asymmetry | Canonical reciprocal ledger validation with no gaps or orphans. |

## Rollback and Recovery

### Before plan acceptance

Delete only the unaccepted Sequence 20 plan/ledger draft if directed.
Permanent W0 is untouched.

### During implementation

Do not delete W0. Revert only unaccepted source/test/Make changes while the
new formal namespace is empty. Preserve unrelated dirty state.

### After candidate generation

If candidate or source bytes change, invalidate the candidate, rerun all
gates, and obtain a new exact acceptance. Do not run formal commands.

### After successor bootstrap or preflight

Never delete committed exact leaves. Reopen or resume only through the
classifier. A failing full coordinator blocks the next transition and
requires a separately reviewed continuation.

### After publication

Do not overwrite review. Reconcile exact output read-only. Drift requires a
new reviewed correction.

## Reciprocal Traceability Projection

The sibling canonical ledger is normative. This table is its exhaustive
requirement-level projection; acceptance, scenario, implementation, and test
edges must match the ledger exactly in both directions.

| Requirement | Acceptance | Scenarios | Implementation | Tests |
|---|---|---|---|---|
| `CFR-109` | `AC-SEQ20-001` | `SC-SEQ20-001-HP`, `SC-SEQ20-001-NP` | `IMPL-171`, `IMPL-172` | `TEST-200`, `TEST-210` |
| `CFR-110` | `AC-SEQ20-002`, `AC-SEQ20-006` | `SC-SEQ20-002-BP`, `SC-SEQ20-002-HP`, `SC-SEQ20-002-NP`, `SC-SEQ20-006-NP`, `SC-SEQ20-008-HP`, `SC-SEQ20-008-NP` | `IMPL-174`, `IMPL-175`, `IMPL-180` | `TEST-200`, `TEST-202`, `TEST-203`, `TEST-206`, `TEST-207`, `TEST-208`, `TEST-209`, `TEST-210`, `TEST-211`, `TEST-212`, `TEST-213` |
| `CFR-111` | `AC-SEQ20-003` | `SC-SEQ20-003-HP`, `SC-SEQ20-003-NP`, `SC-SEQ20-007-NP` | `IMPL-173`, `IMPL-176`, `IMPL-179`, `IMPL-181` | `TEST-201`, `TEST-205`, `TEST-211`, `TEST-213` |
| `CFR-112` | `AC-SEQ20-004` | `SC-SEQ20-004-BP`, `SC-SEQ20-004-HP`, `SC-SEQ20-004-NP`, `SC-SEQ20-008-HP` | `IMPL-177`, `IMPL-180` | `TEST-204`, `TEST-208`, `TEST-212`, `TEST-213` |
| `CFR-113` | `AC-SEQ20-005` | `SC-SEQ20-005-EP`, `SC-SEQ20-005-HP`, `SC-SEQ20-005-NP`, `SC-SEQ20-006-HP`, `SC-SEQ20-006-NP` | `IMPL-178`, `IMPL-179`, `IMPL-180` | `TEST-202`, `TEST-203`, `TEST-206`, `TEST-207`, `TEST-213` |
| `CFR-114` | `AC-SEQ20-002`, `AC-SEQ20-006` | `SC-SEQ20-002-BP`, `SC-SEQ20-002-HP`, `SC-SEQ20-002-NP`, `SC-SEQ20-006-NP`, `SC-SEQ20-008-HP`, `SC-SEQ20-008-NP` | `IMPL-174`, `IMPL-175`, `IMPL-180` | `TEST-200`, `TEST-202`, `TEST-203`, `TEST-206`, `TEST-207`, `TEST-208`, `TEST-209`, `TEST-210`, `TEST-211`, `TEST-212`, `TEST-213` |
| `CFR-115` | `AC-SEQ20-004`, `AC-SEQ20-006`, `AC-SEQ20-007` | `SC-SEQ20-002-BP`, `SC-SEQ20-002-HP`, `SC-SEQ20-004-BP`, `SC-SEQ20-004-HP`, `SC-SEQ20-004-NP`, `SC-SEQ20-006-NP`, `SC-SEQ20-008-HP`, `SC-SEQ20-008-NP` | `IMPL-171`, `IMPL-174`, `IMPL-175`, `IMPL-177`, `IMPL-180` | `TEST-200`, `TEST-202`, `TEST-203`, `TEST-204`, `TEST-206`, `TEST-207`, `TEST-208`, `TEST-209`, `TEST-210`, `TEST-211`, `TEST-212`, `TEST-213` |
| `CFR-116` | `AC-SEQ20-003`, `AC-SEQ20-005`, `AC-SEQ20-008` | `SC-SEQ20-003-HP`, `SC-SEQ20-003-NP`, `SC-SEQ20-005-EP`, `SC-SEQ20-005-HP`, `SC-SEQ20-005-NP`, `SC-SEQ20-006-HP`, `SC-SEQ20-006-NP`, `SC-SEQ20-007-HP`, `SC-SEQ20-007-NP` | `IMPL-173`, `IMPL-176`, `IMPL-178`, `IMPL-179`, `IMPL-180`, `IMPL-181` | `TEST-201`, `TEST-202`, `TEST-203`, `TEST-205`, `TEST-206`, `TEST-207`, `TEST-211`, `TEST-213` |
| `REQ-022` | `AC-SEQ20-001`, `AC-SEQ20-002`, `AC-SEQ20-008` | `SC-SEQ20-001-HP`, `SC-SEQ20-001-NP`, `SC-SEQ20-002-BP`, `SC-SEQ20-002-HP`, `SC-SEQ20-002-NP`, `SC-SEQ20-006-NP`, `SC-SEQ20-007-HP`, `SC-SEQ20-007-NP` | `IMPL-171`, `IMPL-172`, `IMPL-174`, `IMPL-175`, `IMPL-176`, `IMPL-179`, `IMPL-180`, `IMPL-181` | `TEST-200`, `TEST-202`, `TEST-203`, `TEST-206`, `TEST-207`, `TEST-208`, `TEST-209`, `TEST-210`, `TEST-211`, `TEST-213` |

## Success Metrics

- Historical post-W0 baseline remains evidenced as `169/176` with only seven
  named failures.
- The resolved amended live baseline has no failure outside those same seven
  IDs before Sequence 20 implementation begins.
- Fail-first is eleven controlled missing-behavior failures and zero
  unexpected failures.
- Final coordinator is `180/180` at every required checkpoint.
- Parent W0 remains byte-exact and old preflight remains absent until
  successor authority is accepted.
- Package and geometry are `15`, `270/79`, and `640/29/669/985`.
- Fail-soft loader remains `14/14`; API remains `44/44`.
- No source, dependency, UI, API, provider, or theme scope drift.
- No formal Sequence 20 write before exact candidate acceptance.
- Current formal execution stops at W1.

## Dependencies

- Exact current repository and permanent W0 state described above.
- Explicit maintainer disposition and stabilization of the overlapping
  concurrent live-worktree changes.
- A reviewed amendment that binds the resolved live baseline.
- `.venv/bin/python` and current locked dependencies.
- Existing create-once publisher, retained-material transaction, and public
  exit-code contracts.
- Maintainer exact-byte acceptance of plan/ledger.
- Later maintainer exact-byte acceptance of authorization candidate.
- Later explicit instruction before W2 publication.

## Review Checklist

- [x] Exact W0 refs and seven-failure baseline are grounded.
- [x] User request and W1 stop are fully covered.
- [x] Seven tests are corrected without permanent-history mutation.
- [x] Parent importer is independent of live Sequence 19 builders.
- [x] Old public routes close before their bodies.
- [x] New IDs, commands, paths, and state table are disjoint.
- [x] Fifteen-member package and geometry arithmetic close.
- [x] Test plan covers implementation/candidate/X0/W1/W2 checkpoints.
- [x] Positive, negative, boundary, exception, concurrency, and cleanup
      scenarios are present.
- [x] Acceptance boundaries are explicit.
- [x] Affected files and verification commands are explicit.
- [x] Rollback never deletes committed formal leaves.
- [x] Traceability is canonical, reciprocal, gap-free, and orphan-free.
- [ ] No unresolved blocking issue remains: overlapping live-worktree drift
      requires a maintainer preserve-or-restore decision and re-reviewed
      baseline amendment.

## Review Findings

### Round 1 findings and closure

| ID | Severity | Finding | Closure |
|---|---|---|---|
| `S20-R1-001` | High | The draft both froze and planned to edit live Make/source/test paths. | Made archived W0 bytes and permanent leaves immutable; protected live incident bytes only until exact plan acceptance, then authorized only the three scoped edits. |
| `S20-R1-002` | High | The draft required a stored W0 `270/76` projection that does not exist because the old preflight is absent. | Bound retained Sequence 18 `270/73` digests and production-parity replay of all twelve package records: source-mirror paths stay exact, non-mirror records overlay supplemental state, Makefile is replaced, three Sequence 19 records are added, and exact W0 digest is `dab6ca9cb8043d657b3b6c21efd0eda6516aad57323ec9d63face15f49ef0fb8`. |
| `S20-R1-003` | High | Descriptor allowance/reserve were written as `128/188` while the accepted parent contract is `252/64`. | Restored the exact semantic split and derivation `669 + 252 + 64 = 985`. |
| `S20-R1-004` | High | Forward paths and publication identities were not exact, and “candidate” was ambiguous. | Added the ordered six-path inventory, exact publication source/destination, and separate authorization-record versus downstream handoff-candidate semantics. |
| `S20-R1-005` | Medium | TEST-204 was called historical proof although it rebuilds from mutable live files. | Classified TEST-204 only as non-authoritative live-builder compatibility and made TEST-210 the sole immutable W0 package/projection proof. |
| `S20-R1-006` | Medium | The Markdown traceability summary omitted reciprocal ledger edges. | Replaced it with an exhaustive requirement-level ledger projection including acceptance, scenarios, implementation, and tests. |
| `S20-R1-007` | Major | Exact Tier leaves and fifteen package members still used descriptive shorthand; the Make interface was incomplete. | Expanded all paths and fixed the five variables, four targets, six CLI arguments, exact package order, and protected modes. |
| `S20-R1-008` | Major | TEST-205 was absent from the ledger and fail-first did not prove all eleven tests reached new seams. | Added TEST-205 to authorization/parser traceability and required each corrected/new test to reach a new Sequence 20 seam, yielding exactly eleven controlled failures. |
| `S20-R2-001` | High | The first derivation replay added only three Sequence 19 records and failed to overlay the archived Makefile into retained supplemental state. | Replayed all twelve package paths with production semantics, retained mirror paths unchanged, overlaid every non-mirror record, and fixed derived supplemental digest at `dab6ca9cb8043d657b3b6c21efd0eda6516aad57323ec9d63face15f49ef0fb8`. |
| `S20-R2-002` | Blocking — open | Concurrent work changed the three overlapping live inputs and other protected material, invalidating the seven-only entry baseline. | No unsafe restore or scope absorption was performed. Implementation stays blocked pending an explicit preserve-or-restore decision, stable exact refs, amended baseline, and fresh review. |

### Review method and limitation

- Exact W0 hashes, modes, directory membership, old-preflight absence,
  twelve-member PAX, and retained Sequence 18 projection records were
  grounded against the permanent workspace artifacts.
- Geometry closes at `15`, `270/79`, `640/29/669/985`, with protocol
  allowance `252`, reserve `64`, and raise ceiling `1536`.
- The canonical sibling ledger is required to bind the final plan hash and
  pass reciprocal closure at `10000` basis points with zero gaps/orphans.
- An independent local read-only reviewer produced the six Round 1 findings
  and the Round 2 projection-replay finding; deterministic main-thread review
  added two exactness findings. Those nine issues are closed. The separate
  live-worktree blocker remains open. The Claude review engine could not
  authenticate. The Codex CLI completed repository probes but did not emit a
  bounded final verdict and was terminated. No external-engine finding or
  consensus is claimed.
- The maintainer exact-byte acceptance boundary remains mandatory.

## Change History

| Date | Version | Change |
|---|---|---|
| 2026-07-30 | `0.9-draft` | Initial post-W0 lifecycle-test correction and W1 continuation plan. |
| 2026-07-30 | `1.0-review-blocked` | Closed nine design findings, then recorded the unresolved overlapping live-worktree blocker without reverting or absorbing concurrent work. |

## Next Handoff

Stop and obtain the maintainer's preserve-or-restore decision for the
overlapping concurrent work. Do not present these blocked bytes as an
implementation authorization candidate. Do not modify frozen or live source,
tests, or Makefile; do not generate the authorization candidate; and do not
create Sequence 20 formal artifacts. After the external state stabilizes,
amend and re-review the plan/ledger before any exact-byte acceptance handoff.
