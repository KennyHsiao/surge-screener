# Quant Radar UX-1B Sequence 18 O1 Lifecycle-Test Correction Continuation

## Document Control

| Field | Value |
|---|---|
| Version | 1.0 |
| Status | Reviewed — ready for maintainer implementation decision |
| Date | 2026-07-30 |
| Author | Scribe |
| Reviewer | Judge, then repository maintainer |
| Audience | Maintainer, implementation agent, formal reviewer, release gate |
| Parent state | Exact retained Sequence 17 `O1_INTAKE` |
| Intended handoff | Builder after separate implementation acceptance |
| Related plan | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.md` |
| Traceability | Same basename with `.traceability.yaml` |

## Purpose

Sequence 17 correctly brokered the independently accepted 125-item review
candidate into an exact `O1_INTAKE`. The formal verifier reopens that state,
the intake is byte-identical to the accepted candidate, and the retained
material transaction is exact at `628/944`.

The mandatory full lifecycle coordinator then returned `142/148`. Six
permanent tests still apply creation-time shared-leaf assumptions after the
successor lifecycle has legitimately created the intake. Sequence 18 must
correct those tests and their disposable fixture geometry without weakening
historical exactness, create-once semantics, or forbidden candidate/root
guards.

Because Sequence 17 preflight freezes current source projections, any source
or test edit after `O0_PACKET` invalidates its live authority. Sequence 18
therefore also needs a distinct authority that imports the exact retained
Sequence 17 `O1_INTAKE` as immutable history, binds corrected current source,
and may publish only the already-accepted intake as a byte-identical
different-inode manual review.

## Current Exact State

### Formal state

| Property | Exact value |
|---|---|
| Workspace state | `O1_INTAKE` |
| Intake decision | `accepted` |
| Intake SHA-256 | `cf95412e50f6dc7b6608752010d9bb791c77168e3fc913ecb9843d1e1d427081` |
| Intake size | `33070` |
| Intake mode | `0600` |
| Intake link count | `1` |
| Retained materials | `628` |
| Required soft descriptor floor | `944` |
| Manual review | absent |
| Handoff candidate | absent |
| Theme root | absent |
| Last full coordinator | `142/148`, six unexpected failures |

### Exact Sequence 17 O1 parent references

Sequence 18 must pin all thirteen references by path, whole-file SHA-256,
byte size, and mode. It must read the retained PAX archive by descriptor and
must not rebuild the frozen Sequence 17 source projection.

| # | Path | SHA-256 | Size | Mode |
|---:|---|---|---:|---:|
| 1 | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.md` | `87c857a0ddb0aa7936a8cc626bbb28cadc05f980ac9adea9d8149421c9ab2829` | 36044 | `0644` |
| 2 | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.traceability.yaml` | `7fd0d6ed1b7eff4dd2e604c6944c282cfee6aeca6f3783775eac8719c17e74b9` | 23032 | `0644` |
| 3 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-seq17.md` | `69d569dfb6b1bb74079bfc9ece189971816ff7adf62831277b3c490d104466d6` | 8156 | `0644` |
| 4 | `.claude/ui_snapshots/ux1b/recovery/.external-review-formal-state-oracle-correction-20260730T010000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 | `0600` |
| 5 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-prechange-seq17.json` | `ac6844d517bc0cf780d0e7b2bd2ee1a3b2a63538b0d54098c728e76ba20edc76` | 6038 | `0600` |
| 6 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-rollback-seq17.json` | `b634d28b29ed6ff30200310fe1d160444e368d84b666e6afd57a551ab28e1c61` | 2593 | `0600` |
| 7 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-prechange-20260730T011000Z/.quant-radar-theme-handoff-external-review-formal-state-oracle-correction-owner` | `3687245645a5dcd8cbd3aa8d52095257c1da126c037bf2f6df43c90604e59d36` | 189 | `0600` |
| 8 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-prechange-20260730T011000Z/prechange-files.tar` | `bccca840886f22b2c576f6082031a6c2661c6338a2a9987146a56a83dbb05bf5` | 3092480 | `0600` |
| 9 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-prechange-20260730T011000Z/bundle-manifest.json` | `1620a9eeb48914051376ff57b62b203cfbeab75d7db82f67744dd0fc11b01e7e` | 1274 | `0600` |
| 10 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-preflight-20260730T010000Z.json` | `77d22454739d31db37553f06fd8fac0af085998432f882c4f292dda98b243568` | 67964 | `0600` |
| 11 | `.claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json` | `97a37c01a7fefbaf20386a6bb732e87993e8f282ba3216885ad92f2530a7f553` | 12444 | `0600` |
| 12 | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json` | `1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd` | 89295 | `0600` |
| 13 | `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json` | `cf95412e50f6dc7b6608752010d9bb791c77168e3fc913ecb9843d1e1d427081` | 33070 | `0600` |

### Current implementation baseline

These records are the pre-Sequence-18 implementation baseline, not new
parent references. Phase S18-0 must recheck them before the first source edit
so the eventual diff can be explained exactly.

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `Makefile` | `97dd7ac3b19fe72aff6362abdac4385ad661faf52a30cd1f404ec58b545bc5bd` | 63809 | `0644` |
| `scripts/ui_ux_theme_handoff.py` | `c0892b6e48004d6ef7d77c8aa1b5c3d948c85ee8ee64f8a8bc3c548ef32bc81a` | 1739114 | `0644` |
| `scripts/test_ui_ux_theme_handoff.py` | `9d8bb6b7e1364683f7c21c29bdb52d4e46e8c7c40240a78ec818770c1fd8186f` | 1212958 | `0644` |

## Failure Reproduction

| Test | Current failure | Root cause | Required correction |
|---|---|---|---|
| `TEST-162` | `Sequence 16 parent forward boundary differs` | Historical Sequence 15 import is called with `require_initial=True` after a valid successor intake exists. | Exercise immutable history with `require_initial=False`; retain a separate creation-time rejection test. |
| `TEST-164` | Same | Disposable Sequence 16 Tier patches do not isolate all shared predecessor forward aliases. | Patch exact report/packet plus fixture-local later leaves for every predecessor alias family used by the fixture. |
| `TEST-169` | Same | Historical-open test hard-codes creation-time absence. | Import historical E0 without an initial-absence assertion; continue proving old live reauthentication fails closed. |
| `TEST-172` | `Sequence 17 parent C0 has a later shared leaf` | Exact Sequence 16 C0 historical import is called with `require_initial=True` at active O1. | Use historical mode and separately test creation-time absence. |
| `TEST-178` | `Sequence 17 parent C0 handoff differs` | Disposable Sequence 17 flow reads the permanent shared intake through unpatched predecessor aliases. | Isolate Sequence 15, 16, and 17 forward aliases in one fixture namespace. |
| `TEST-179` | `Sequence 17 parent C0 has a later shared leaf` | Historical-open test hard-codes creation-time absence. | Use historical mode while retaining the explicit old-live fail-closed assertion. |

Two currently passing permanent tests also need migration before source edits:

- `TEST-170` must classify through the Sequence 18 wrapper. The old Sequence
  17 live validator must fail closed after corrected source changes.
- `TEST-180` must validate the Sequence 18 permanent workspace classifier and
  partial-Tier rejection. It must still assert candidate/root absence.

## Scope

### In scope

- Exact whole-file import of retained Sequence 17 `O1_INTAKE`.
- Lifecycle-aware repair of the six failing tests.
- Migration of `TEST-170` and `TEST-180` to the successor wrapper.
- Complete disposable-fixture isolation across all shared forward aliases.
- Distinct Sequence 18 authorization, Tier, preflight, package, PAX, CLI,
  Make, descriptor, namespace, and publication contracts.
- Exact publication of the retained accepted intake to the manual-review path.
- Permanent lifecycle verification at implementation boundary,
  `V0_BOOTSTRAPPED`, `V1_INTAKE`, and `V2_REVIEW`.
- Traceability, Builder/Scribe/Judge journals, and project activity.

### Non-goals

- No new reviewer or reviewer candidate.
- No mutation, replacement, or deletion of the retained intake.
- No capture, recapture, comparison, report, or packet regeneration.
- No candidate or theme-root authority.
- No UI, API, provider, data, fixture, selector, image, sidecar, or theme edit.
- No rollback from PAX over the live worktree.
- No publication under Sequence 17 after source changes.
- No attempt to make old live validators accept changed source.

## Requirements

### `REQ-019` — Resume the accepted O1 handoff

The system must preserve the exact accepted Sequence 17 intake and, after a
separately accepted Sequence 18 authority, publish only those bytes as the
manual review.

### `CFR-091` — Exact O1 historical import

The importer must validate all thirteen parent references, their semantic
cross-links, the accepted review truth, and the deterministic PAX package
without rebuilding frozen source.

### `CFR-092` — Permanent lifecycle tests

All permanent tests must pass at the Sequence 18 implementation boundary,
`V0_BOOTSTRAPPED`, `V1_INTAKE`, and `V2_REVIEW`. Creation-time absence must
remain separately testable and fail closed.

### `CFR-093` — Disposable fixture isolation

Every disposable lifecycle fixture must isolate all later shared leaves for
each predecessor alias family it exercises. Permanent intake/review leaves
must be unreadable as fixture state.

### `CFR-094` — Distinct current authority

Corrected current source must be bound by a distinct Sequence 18
authorization, Tier, preflight, runtime, package, namespace, and descriptor
profile. Old Sequence 17 live verification must fail closed.

### `CFR-095` — Atomic exact publication

Publication must create or reconcile a byte-identical, different-inode review
from the retained intake with create-once, no-replace, fsync, owner, mode,
link-count, and retained-material guarantees.

### `CFR-096` — Scope and evidence preservation

All Sequence 17 parent bytes, report, packet, intake, images, sidecars,
runtime, and earlier history must remain exact. Candidate/root and all
capture/theme paths must remain forbidden.

## Acceptance Criteria

### `AC-SEQ18-001` — Exact parent O1 import

Given the thirteen pinned Sequence 17 O1 references,
when the historical importer runs,
then it returns the exact O1 report, packet, intake, decision, projections,
runtime, Tier, and preflight without invoking Sequence 17 live builders or
validators.

### `AC-SEQ18-002` — Lifecycle-aware permanent suite

Given the real workspace at exact O1 or a valid Sequence 18 state,
when the full coordinator runs,
then all existing 148 tests and all new Sequence 18 tests pass; creation-time
absence mutations still fail.

### `AC-SEQ18-003` — Complete fixture isolation

Given permanent shared intake bytes,
when Sequence 16 or Sequence 17 disposable flows run,
then every predecessor and active forward alias resolves only to the
fixture-local later leaves while the exact retained report/packet remain
read-only inputs.

### `AC-SEQ18-004` — Distinct V0/V1 authority

Given separately accepted Sequence 18 authorization bytes,
when bootstrap and preflight run,
then only Sequence 18 Tier/preflight are created, bootstrap reopens as
`V0_BOOTSTRAPPED`, and preflight reopens as `V1_INTAKE`.

### `AC-SEQ18-005` — Exact material geometry

Given authenticated current source, the retained packet/intake, and both
authority stacks,
when preflight or publication opens the commit transaction,
then it derives exactly 631 unique content materials plus 16 non-overlapping
authority leaves, retains exactly 647 descriptors under a required soft floor
of 963, restores the original soft limit, and rejects any cardinality or
digest drift.

### `AC-SEQ18-006` — Exact V2 publication

Given exact `V1_INTAKE`,
when publication runs,
then the manual review is a byte-identical, different-inode copy of the
accepted intake, decision remains `accepted`, and the workspace reopens as
`V2_REVIEW`.

### `AC-SEQ18-007` — Compatibility and fail-closed behavior

Given corrected current source,
when old Sequence 17 live verification runs,
then it fails closed; the Sequence 18 historical importer and live validator
remain valid.

### `AC-SEQ18-008` — Formal pause and scope

Given any Sequence 18 formal state,
when namespace and source scope are checked,
then candidate/root remain absent, capture/compare/theme commands remain
unauthorized, and execution stops at `V2_REVIEW`.

## Lifecycle and Authority Model

### State machine

```text
exact retained O1_INTAKE
        |
        | corrected source + no Sequence 18 Tier
        v
IMPLEMENTATION_BOUNDARY
        |
        | accepted Sequence 18 bootstrap
        v
V0_BOOTSTRAPPED
        |
        | accepted Sequence 18 preflight
        v
V1_INTAKE
        |
        | exact create-once publication
        v
V2_REVIEW  [mandatory stop]
```

### Forward namespace

| State | Tier | Preflight | Report | Packet | Intake | Review | Candidate | Root |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `IMPLEMENTATION_BOUNDARY` | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| `V0_BOOTSTRAPPED` | complete | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| `V1_INTAKE` | complete | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `V2_REVIEW` | complete | 1 | 1 | 1 | 1 | 1 | 0 | 0 |

All four states preserve the parent report/packet/intake prefix.
`IMPLEMENTATION_BOUNDARY`, `V0_BOOTSTRAPPED`, and `V1_INTAKE` differ by
Sequence 18 Tier/preflight presence. Exact proper prefixes created by a
crashed bootstrap are recoverable transport substates, not active lifecycle
states; non-prefix or different-byte shapes are contract violations.

### Identity

| Field | Value |
|---|---|
| Sequence | `18` |
| Parent state | `O1_INTAKE` |
| Parent correction ID | `20260730T010000Z` |
| O1 lifecycle correction ID | `20260730T030000Z` |
| O1 lifecycle Tier ID | `20260730T031000Z` |
| Initial post-bootstrap state | `V0_BOOTSTRAPPED` |
| Initial preflight-active state | `V1_INTAKE` |
| Formal pause | `V2_REVIEW` |

### Allowed public commands

```text
bootstrap-external-review-o1-lifecycle-test-correction
preflight-external-review-o1-lifecycle-test-correction
verify-external-review-o1-lifecycle-test-correction-preflight
publish-o1-lifecycle-test-corrected-review
```

There is no submit command. Sequence 18 consumes only the already-accepted,
already-committed intake.

### Make routes

```text
ui-ux1b-external-review-o1-lifecycle-test-bootstrap
ui-ux1b-external-review-o1-lifecycle-test-preflight
ui-ux1b-external-review-o1-lifecycle-test-verify
ui-ux1b-external-review-o1-lifecycle-test-publish
```

All routes require the exact parent correction ID, correction ID, Tier ID,
packet continuation ID, and capture ID. Publish accepts no stdin and no
candidate digest argument.

## Historical Import Contract

Implement `_import_sequence17_o1_intake(...)` with two explicit modes:

- `require_initial=True` is legal at `IMPLEMENTATION_BOUNDARY` and during an
  exact bootstrap prefix, and requires review/candidate/root absence.
- `require_initial=False` imports exact O1 history while allowing only the
  Sequence 18-owned review leaf when the Sequence 18 Tier/preflight is exact.

The importer must never call:

```text
_build_formal_state_oracle_correction_source_projections
_build_formal_state_oracle_correction_preflight_value
_validate_formal_state_oracle_correction_preflight_value
_reauthenticate_formal_state_oracle_correction_preflight
_validate_formal_state_oracle_correction_tier_complete
```

It must validate:

- exact thirteen-reference metadata and whole-file hashes;
- canonical JSON and authorization marker grammar;
- deterministic Sequence 17 PAX order, metadata, member sizes, and member
  hashes without extraction;
- exact O1 report/packet/intake path and digest bindings;
- reviewer ID, packet binding, reviewed timestamp, 125 accepted items, zero
  rejected items, zero unresolved High/Medium findings, and accepted decision;
- exact frozen source/supplemental projections and runtime receipt;
- candidate/root absence and permitted successor review ownership.

The accepted O1 appointment and review window are frozen history. Every
Sequence 18 import, bootstrap, preflight, V1 verification, publication, and
V2 reconciliation must validate `reviewedAt` only against the pinned parent
`createdAt`, clock-skew allowance, and `reviewDeadline`. No path may compare
that accepted review to ambient current time.

### Parent-state handoff and lock

The exact thirteen-reference O1 state plus review/candidate/root absence must
be checked at four checkpoints:

1. Phase S18-0 before the first source edit.
2. After implementation stabilizes and before generating the authorization
   candidate.
3. Immediately before accepted authorization bytes are consumed.
4. Under the global lifecycle lock immediately before the first Sequence 18
   create-once Tier commit.

Checkpoint 4 and the first Tier commit must occur in one uninterrupted global
lock scope. Any parent drift or newly present shared review at any checkpoint
stales the continuation: Sequence 18 must not delete, adopt, or reinterpret
the leaf and must stop for a new plan.

### Bootstrap and preflight prefix recovery

Bootstrap uses this fixed create order under the global lock:

```text
lease -> prechange -> rollback -> tier-directory -> owner -> archive -> bundle
```

Preflight is the eighth and final create-once step in a separate locked
command. Every file uses same-directory temporary creation, file fsync,
no-replace publication, and parent-directory fsync. The Tier directory uses
no-follow exact-owner/mode creation and parent fsync. On entry, the command
must scan the eight-step presence/inventory vector and authenticate every
present byte and directory identity:

- all absent starts bootstrap;
- an exact proper prefix, including an exact empty Tier directory, resumes at
  the first absent step;
- the exact seven-step Tier is `V0_BOOTSTRAPPED`;
- all eight exact steps are `V1_INTAKE` or `V2_REVIEW` according to the
  forward namespace;
- any gap, out-of-order leaf, unexpected directory member, different bytes,
  alias, or metadata drift is a contract violation.

No crash prefix is deleted. Fault injection must cover Tier-directory
creation/fsync plus temporary creation, file fsync, no-replace publication,
and parent fsync for every file, followed by an exact rerun to V0 or V1.
Parent O1 and forbidden-leaf checks repeat before every resumed commit while
the same global lock remains held.

## Permanent-Test Correction Contract

### Historical versus creation-time intent

Historical-import tests must use historical mode. They must not silently
convert creation-time absence into a permanent invariant.

Creation-time absence remains covered in a disposable namespace:

- `require_initial=True` rejects any pre-existing later shared leaf.
- `require_initial=False` accepts only a closed valid predecessor/successor
  prefix.
- Candidate/root remain forbidden in every mode.

### Fixture alias closure

Each disposable flow must construct one exact forward tuple per authority:

```text
(retained_report, retained_packet,
 fixture_intake, fixture_review, fixture_candidate, fixture_root)
```

It must patch every alias family read by that flow, including:

```text
EXTERNAL_REVIEW_FORWARD_PATHS
LIFECYCLE_TEST_CORRECTION_FORWARD_PATHS
FORMAL_STATE_ORACLE_CORRECTION_FORWARD_PATHS
```

The corresponding review-path tuples and derived preflight paths must also be
patched when used. Patch scopes must restore all constants after the fixture.
No fixture may hide or delete the permanent O1 intake.

### Permanent classifier migration

`TEST-170` and `TEST-180` must use the Sequence 18 wrapper to classify the
real workspace. A separate test must prove the old Sequence 17 live
reauthenticator fails after corrected source changes.

## Current Source Authority

### Package paths

```text
Makefile
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

The PAX package must be deterministic:

- package paths in exact declared order;
- regular files only;
- UID/GID zero, empty uname/gname;
- mtime zero;
- mode `0644`;
- exact size and SHA-256 for every member;
- no extraction during validation.

### Material and descriptor arithmetic

```text
sourceProjection       = 270
supplementalProjection = 67 + 3 = 70
contentMaterials       = 628 + 3 = 631
parentAuthorityOnly    = 9
currentAuthorityOnly   = 7
commitRetainedLeaves   = 631 + 9 + 7 = 647
protocolAdditional     = 252
reserve                = 64
requiredSoftFloor      = 647 + 252 + 64 = 963
raiseCeiling           = 1536
```

The three new content materials are this plan, its ledger, and the Sequence
18 authorization. The nine parent-authority-only leaves are the Sequence 17
lease, prechange, rollback, owner, archive, bundle, preflight, packet, and
intake not already present in the 631-content set. The seven
current-authority-only leaves are the Sequence 18 lease, prechange, rollback,
owner, archive, bundle, and preflight.

Implementation must build one unique union, retain all 647 descriptors
through commit, and derive every value from authenticated records. The
`protocolAdditional` allowance covers only transient lock, directory,
temporary-file, and validator work; it is not a substitute for retaining
commit-critical authority descriptors. If the derived set is not exactly
`270/70/631/16/647/963`, implementation must stop and amend this plan instead
of changing constants to fit ambient state.

## Atomic Publication Contract

Publication must:

1. Acquire the existing global lifecycle lock.
2. Acquire the distinct Sequence 18 lease.
3. Reauthenticate Sequence 18 preflight, classify the namespace, and allow
   only exact `V1_INTAKE` or exact `V2_REVIEW`.
4. Open the exact 631-content plus 16-authority, 647-descriptor transaction.
5. Open the intake by retained descriptor and read its exact accepted bytes.
6. If initial state is `V2_REVIEW`, verify the existing review is the exact
   byte-identical, different-inode result, perform pre/post descriptor
   reauthentication, create no temporary file, and return read-only
   reconciliation.
7. If initial state is `V1_INTAKE`, publish to the shared manual-review path
   using same-directory temporary creation, file fsync, no-replace rename,
   and parent-directory fsync.
8. Reauthenticate all 647 retained descriptors immediately before rename,
   after rename but before parent fsync, and after parent fsync.
9. Require mode `0600`, current UID/GID, link count one, exact hash/size, and
   a different inode from intake.
10. Reopen exact `V2_REVIEW` without consulting ambient reviewer time.
11. Return decision `accepted`.

A fault at any atomic boundary may leave the review absent or at exact
`V2_REVIEW`, never partial or different. Every exact V2 retry must reconcile
read-only; every other initial or recovered shape is a contract violation.

## Implementation Checklist

| ID | Deliverable | Requirements | Tests |
|---|---|---|---|
| `IMPL-143` | Exact 13-reference O1 importer and PAX validator | `REQ-019`, `CFR-091`, `CFR-096` | `TEST-182`, `TEST-188`, `TEST-190`, `TEST-191` |
| `IMPL-144` | Sequence 18 permanent workspace classifier | `REQ-019`, `CFR-092`, `CFR-094` | `TEST-170`, `TEST-180`, `TEST-183`, `TEST-188`, `TEST-189` |
| `IMPL-145` | Historical-mode corrections for TEST-162/169/172/179 | `REQ-019`, `CFR-092` | `TEST-162`, `TEST-169`, `TEST-172`, `TEST-179`, `TEST-189` |
| `IMPL-146` | Complete alias isolation for TEST-164/178 fixtures | `REQ-019`, `CFR-093` | `TEST-164`, `TEST-178`, `TEST-184`, `TEST-189` |
| `IMPL-147` | Sequence 18 IDs, parser, namespace, CLI, Make, package, PAX | `REQ-019`, `CFR-094`, `CFR-096` | `TEST-185`, `TEST-190`, `TEST-191` |
| `IMPL-148` | Tier, preflight, runtime, source and descriptor binding | `REQ-019`, `CFR-094` | `TEST-185`, `TEST-186`, `TEST-188` |
| `IMPL-149` | Exact 631-content/647-retained/963-floor transaction | `REQ-019`, `CFR-094`, `CFR-095` | `TEST-186`, `TEST-187` |
| `IMPL-150` | Atomic exact intake-to-review publication | `REQ-019`, `CFR-095` | `TEST-187`, `TEST-189` |
| `IMPL-151` | Compatibility, scope, rollback, forbidden-leaf gates | `REQ-019`, `CFR-091`, `CFR-092`, `CFR-096` | `TEST-188`, `TEST-190`, `TEST-191` |
| `IMPL-152` | Full verification, authorization candidate, journals | all | `TEST-162`, `164`, `169`, `170`, `172`, `178`–`180`, `182`–`191` |

## Test Plan

### Existing tests that must change

```text
TEST-162
TEST-164
TEST-169
TEST-170
TEST-172
TEST-178
TEST-179
TEST-180
```

### New Sequence 18 tests

| Test | Proof |
|---|---|
| `TEST-182` | Exact Sequence 17 O1 import; no live-source rebuild |
| `TEST-183` | Parent O1 and active boundary/V0/V1/V2 truth tables are closed |
| `TEST-184` | All disposable predecessor forward aliases are isolated |
| `TEST-185` | IDs, parser, public registry, Make routes, package, PAX are distinct |
| `TEST-186` | Source/content/authority/retained/floor counts are exactly `270/70/631/16/647/963` |
| `TEST-187` | V1 publication and V2 reconciliation are crash-safe, byte-identical, and different-inode |
| `TEST-188` | Historical importer stays open while Sequence 17 live validation fails closed |
| `TEST-189` | Full permanent coordinator passes at implementation boundary, V0, V1, and V2 |
| `TEST-190` | Scope, protected refs, exact prefixes, invalid Tier shapes, and candidate/root absence are exact |
| `TEST-191` | Traceability, authorization body, formal pause, rollback, and command scope are exact |

Expected coordinator after implementation: `158/158`.

### BDD scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| `SC-AC-SEQ18-001-HP-001` | Exact 13 O1 refs | Import history | Exact O1 returned |
| `SC-AC-SEQ18-001-NP-001` | Mutated outer hash/size/mode | Import history | Contract violation |
| `SC-AC-SEQ18-001-NP-002` | Mutated PAX member | Import history | Contract violation |
| `SC-AC-SEQ18-001-NP-003` | Mutated intake semantics | Import history | Contract violation |
| `SC-AC-SEQ18-002-HP-001` | Corrected source, no Tier | Full coordinator | `158/158` |
| `SC-AC-SEQ18-002-HP-004` | Exact `V0_BOOTSTRAPPED` | Full coordinator | `158/158` |
| `SC-AC-SEQ18-002-HP-002` | Exact `V1_INTAKE` | Full coordinator | `158/158` |
| `SC-AC-SEQ18-002-HP-003` | Exact `V2_REVIEW` | Full coordinator | `158/158` |
| `SC-AC-SEQ18-002-NP-001` | Historical test uses initial absence at O1 | Run test | Mutation oracle fails |
| `SC-AC-SEQ18-002-BP-001` | Old Sequence 17 live verifier | Verify changed source | Fails closed |
| `SC-AC-SEQ18-003-HP-001` | Permanent intake exists | Sequence 16 fixture | Fixture reaches local preflight |
| `SC-AC-SEQ18-003-HP-002` | Permanent intake exists | Sequence 17 fixture | Fixture reaches local O2 |
| `SC-AC-SEQ18-003-NP-001` | One predecessor alias unpatched | Run fixture | Contract violation |
| `SC-AC-SEQ18-003-EP-001` | Fixture exits or raises | Leave patch scope | Constants and temp paths restored |
| `SC-AC-SEQ18-004-HP-001` | Accepted authority | Bootstrap twice | Created, then exact V0 reconciliation |
| `SC-AC-SEQ18-004-HP-002` | Complete Tier | Preflight twice | Created, then verified V1 |
| `SC-AC-SEQ18-004-NP-001` | Non-prefix/different-byte Tier or collision | Bootstrap/verify | Contract violation |
| `SC-AC-SEQ18-004-EP-001` | Parent O1 drifts before commit | Bootstrap | No Sequence 18 leaf committed |
| `SC-AC-SEQ18-004-EP-002` | Crash after any Tier/preflight create boundary | Rerun | Exact prefix resumes to V0/V1 |
| `SC-AC-SEQ18-005-BP-001` | 631 content plus 16 authority leaves | Transaction | Retains and reauthenticates 647 |
| `SC-AC-SEQ18-005-NP-001` | Content 630/632 or retained 646/648 | Transaction | Contract violation |
| `SC-AC-SEQ18-005-NP-002` | Soft floor below 963 | Transaction | Contract violation |
| `SC-AC-SEQ18-005-NP-003` | Material changes before commit | Publication | No commit |
| `SC-AC-SEQ18-006-HP-001` | Exact V1 | Publish | Exact V2 accepted |
| `SC-AC-SEQ18-006-HP-002` | Exact V2 | Publish again | Read-only reconciliation |
| `SC-AC-SEQ18-006-NP-001` | Review exists with different bytes | Publish | Contract violation |
| `SC-AC-SEQ18-006-EP-001` | Crash at every atomic boundary | Publish | Absent or exact V2 only |
| `SC-AC-SEQ18-007-HP-001` | Corrected source | Import O1 history | Exact historical values returned |
| `SC-AC-SEQ18-007-NP-001` | Corrected source | Sequence 17 live reopen | Contract violation |
| `SC-AC-SEQ18-008-HP-001` | Implementation/V0/V1/V2 | Scope gate | Only allowed paths present |
| `SC-AC-SEQ18-008-NP-001` | Candidate or root appears | Classify | Contract violation |
| `SC-AC-SEQ18-008-NP-002` | Capture/compare/theme command claimed | Parse authority | Contract violation |

## Implementation Phases and Gates

### Phase S18-0 — exact O1 freeze and red baseline

- Recheck all thirteen parent refs and forbidden leaves.
- Record the exact Make/coordinator/test baseline table above.
- Record `O1_INTAKE`, accepted decision, `628/944`, and `142/148`.
- Prove all six failures arise from shared-leaf test geometry.

**Gate:** no formal or source mutation.

### Phase S18-1 — exact O1 historical importer

- Add thirteen-ref whole-file importer.
- Validate PAX, frozen projections, runtime, report, packet, intake, and
  accepted review truth without live-source rebuild.
- Add outer, semantic, PAX, and forbidden-leaf mutation tests.

**Gate:** exact parent bytes remain unchanged.

### Phase S18-2 — permanent lifecycle and fixture correction

- Correct historical-mode tests.
- Isolate every predecessor alias family in disposable fixtures.
- Migrate permanent workspace tests to the Sequence 18 wrapper.
- Retain explicit creation-time absence and old-live fail-closed tests.

**Gate:** the original 148 tests pass in the real retained O1 workspace.

### Phase S18-3 — distinct current authority

- Add IDs, commands, Make routes, parser, package, PAX, Tier, preflight,
  namespace, runtime, source, material, and descriptor contracts.
- Add `IMPLEMENTATION_BOUNDARY -> V0_BOOTSTRAPPED -> V1_INTAKE ->
  V2_REVIEW`.
- Make every exact bootstrap/preflight create prefix resumable under one
  global lock; reject non-prefix or different-byte shapes without cleanup.

**Gate:** disposable production-shaped execution reaches V2 with candidate
and root absent.

### Phase S18-4 — atomic publication

- Publish exact intake bytes to review with existing atomic primitives.
- Retain the exact 631-content plus 16-authority, 647-descriptor union across
  validation and commit.
- Verify different inode, exact accepted decision, V1 write behavior, and V2
  read-only reconcile.

**Gate:** every crash boundary yields review absent or exact V2.

### Phase S18-5 — authority freeze and implementation verification

- After implementation logic and focused tests stabilize, recheck exact O1
  and generate the Sequence 18 authorization candidate.
- Freeze source, plan, ledger, and authorization bytes.
- Run coordinator twice only after the candidate exists.
- Run complete repository and recovery regressions.
- Run syntax, Python 3.10 AST, tabnanny, dependency, diff, PAX, protected-ref,
  cleanup, namespace, and no-theme/no-candidate gates.
- Compare actual diff with this plan.
- Reprove exact `270/70/631/16/647/963` geometry and deterministic PAX.
- Any later source, plan, ledger, or authorization edit invalidates the
  candidate and restarts this entire phase with newly reported metadata.

**Gate:** zero implementation-caused failure and zero unexplained drift.

### Phase S18-6 — authorization handoff

- Report exact authorization SHA-256, byte size, and mode.
- Require separate maintainer acceptance.
- Recheck exact O1 and all thirteen parent refs immediately before bootstrap.

**Gate:** no Sequence 18 Tier or preflight without exact acceptance.

### Phase S18-7 — bootstrap and V1 pause

- Perform the fourth exact O1 check and first Tier commit under one
  uninterrupted global lock.
- Bootstrap by resuming only exact create-order prefixes to
  `V0_BOOTSTRAPPED`.
- Preflight by exact create/reconcile to `V1_INTAKE`.
- Reopen exact `V1_INTAKE`.
- Run the full permanent coordinator.

**Gate:** review, candidate, and root remain absent.

### Phase S18-8 — publish and mandatory stop

- Publish exact intake bytes.
- Reopen exact `V2_REVIEW`.
- Run the full permanent coordinator and final protected-ref checks.
- Stop.

**Gate:** candidate/root remain absent; no later command is authorized.

## Affected Files

### Planning outputs in this turn

```text
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.traceability.yaml
.agents/scribe.md
.agents/judge.md
.agents/PROJECT.md
```

### Planned implementation edits after separate acceptance

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

### Later formal outputs after exact authorization acceptance

```text
.claude/ui_snapshots/ux1b/recovery/.external-review-o1-lifecycle-test-correction-20260730T030000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-prechange-seq18.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-rollback-seq18.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

### Protected paths

```text
all thirteen Sequence 17 O1 parent references
all Sequence 8-17 plans, ledgers, authorizations, Tier, preflights, captures,
stacks, manifests, reports, packets, intakes, reviews, candidates, and roots
all packet-referenced images and sidecars
all production UI, API, provider, data, fixture, selector, and theme files
requirements.txt
.venv/
```

## Verification Commands

```bash
.venv/bin/python scripts/test_ui_ux_theme_handoff.py
make test
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Python 3.10 compatibility must use an actual 3.10 interpreter when available.
Otherwise parse both Python files with
`ast.parse(..., feature_version=(3, 10))` and report the limitation.

Formal verification must additionally prove:

- all thirteen parent refs exact after every implementation phase;
- deterministic PAX byte reproduction;
- exact `270/70/631/16/647/963` profiles;
- original coordinator failures reproduce before the correction;
- coordinator passes at implementation boundary, V0, V1, and V2;
- exact bootstrap/preflight prefixes resume after every atomic fault;
- accepted O1 history remains valid after the frozen review deadline;
- no temp paths or owned process remain;
- review absent before publish and exact after publish;
- candidate/root always absent;
- no capture, compare, UI, API, or theme mutation.

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---:|---|
| Fixing only assertions while invalidating current source authority | High | Exact O1 importer plus distinct Sequence 18 live authority |
| Repeating the permanent absence bug | High | Full coordinator at implementation, V0, V1, and V2; separate creation-time tests |
| Disposable fixture consumes permanent intake | High | Patch every predecessor alias family and assert fixture-local inodes |
| Weakening old fail-closed behavior | High | Explicit old-live rejection and historical-open tests |
| Publishing modified reviewer bytes | High | Exact retained descriptor, hash/size, byte equality, no stdin |
| Review aliases intake inode | High | Different-inode postcondition |
| Material TOCTOU | High | Retain and reauthenticate the exact 631-content set before/after commit |
| Authority TOCTOU | High | Retain 16 non-overlapping parent/current authority descriptors with the content set through commit |
| Candidate/root authority leak | High | Closed namespace, grammar, command registry, absence gates |
| Bootstrap crash strands a partial Tier | High | Resume only exact create-order prefixes under the global lock; reject all other shapes |
| Accepted O1 expires under ambient time | High | Validate frozen parent timestamps only; post-deadline lifecycle tests |
| Descriptor estimate drifts | Medium | Derive authenticated set; stop and amend if not `270/70/631/16/647/963` |
| Planning mistaken for execution authority | Medium | Separate reviewed plan, implementation acceptance, authorization acceptance |

## Rollback and Recovery

### Before implementation acceptance

- Preserve exact O1.
- Planning files may be revised through review.
- Do not remove or rewrite any formal artifact.

### During implementation

- Revert only explained Sequence 18 source edits through the normal worktree
  workflow.
- Never restore Sequence 17 PAX over the live worktree.
- Never hide or delete the retained intake to make tests pass.
- If exact parent O1 drifts, stop and re-plan.

### After Sequence 18 Tier

- Follow only the Sequence 18 rollback contract.
- Preserve every exact create-order prefix and resume it under the global
  lock; no cleanup is authorized.
- Stop on a non-prefix or different-byte shape and require a new correction
  authority.

### After `V1_INTAKE`

- Treat Sequence 18 preflight as immutable.
- Any new source defect requires a new correction authority.

### After `V2_REVIEW`

- Stop. Sequence 18 grants no candidate, root, capture, comparison, or theme
  authority.

## Traceability Matrix

| Requirement | Acceptance | Implementation | Tests |
|---|---|---|---|
| `REQ-019` | `AC-SEQ18-001`–`008` | `IMPL-143`–`152` | `TEST-162`, `164`, `169`, `170`, `172`, `178`–`180`, `182`–`191` |
| `CFR-091` | `AC-SEQ18-001`, `007` | `IMPL-143`, `151`, `152` | `TEST-182`, `188`, `190`, `191` |
| `CFR-092` | `AC-SEQ18-002`, `007`, `008` | `IMPL-144`, `145`, `151`, `152` | `TEST-162`, `169`, `170`, `172`, `179`, `180`, `183`, `188`, `189` |
| `CFR-093` | `AC-SEQ18-003` | `IMPL-146`, `152` | `TEST-164`, `178`, `184`, `189` |
| `CFR-094` | `AC-SEQ18-004`, `005`, `007` | `IMPL-144`, `147`, `148`, `149`, `152` | `TEST-183`, `185`, `186`, `188`, `190`, `191` |
| `CFR-095` | `AC-SEQ18-005`, `006` | `IMPL-149`, `150`, `152` | `TEST-186`, `187`, `189` |
| `CFR-096` | `AC-SEQ18-001`, `008` | `IMPL-143`, `147`, `151`, `152` | `TEST-182`, `188`, `190`, `191` |

## Success Metrics

| Metric | Target | Measurement |
|---|---:|---|
| Parent evidence drift | `0` | 13 exact hash/size/mode checks |
| Existing coordinator failures | `0` | All original 148 tests pass |
| Total coordinator failures | `0` | `158/158` after new tests |
| Content/authority retained descriptors | `631/16/647` | Unique retained-descriptor transaction |
| Required soft descriptor floor | `963` | `647 + 252 + 64` |
| Traceability coverage | `10000` basis points | Canonical ledger validator |
| Unexplained diff paths | `0` | Accepted plan versus actual diff |
| Reviewer bytes changed | `0` | Intake/review byte equality |
| Candidate/root leaves | `0` | Namespace gate |
| Capture/UI/theme mutations | `0` | Protected-path and diff gates |

## Dependencies

- Exact retained Sequence 17 O1 bytes listed above.
- Existing global lock, lease, retained-descriptor, atomic-publisher, canonical
  JSON, public dispatcher, PAX, and source-projection primitives.
- Current Python virtual environment and macOS file semantics.
- Separate maintainer acceptance before implementation.
- Separate exact authorization-byte acceptance before formal bootstrap.

## Glossary

| Term | Meaning |
|---|---|
| Historical mode | Validates frozen predecessor bytes while allowing a valid successor-owned later prefix |
| Creation-time mode | Requires all later leaves absent before the first successor commit |
| Shared leaf | A report, packet, intake, or review path reused by compatible authorities |
| Alias family | Authority-specific constant tuple that points to shared forward paths |
| `O1_INTAKE` | Exact retained Sequence 17 accepted intake |
| `V0_BOOTSTRAPPED` | Exact Sequence 18 Tier exists and preflight is absent |
| `V1_INTAKE` | Sequence 18 active source authority with exact retained intake |
| `V2_REVIEW` | Sequence 18 published exact manual review and mandatory stop |
| Permanent test | Test valid at implementation and every authorized later formal state |

## Review Checklist

- [x] Exact parent O1 and six failures reproduced.
- [x] All post-source-edit permanent tests are identified.
- [x] Historical and creation-time semantics are separate.
- [x] Every disposable predecessor alias is isolated.
- [x] New authority is disjoint and has no submit command.
- [x] Material/descriptor arithmetic is authenticated and bounded.
- [x] Publication preserves exact intake bytes and accepted decision.
- [x] Candidate/root and capture/theme authority remain forbidden.
- [x] Affected files and later formal outputs are explicit.
- [x] Rollback never mutates retained O1.
- [x] Requirements, ACs, scenarios, implementation, and tests are
      bidirectionally traceable.
- [x] Independent blocker review has no unresolved High/Medium finding.
- [ ] Maintainer separately accepts implementation.

## Review Provenance and Result

Review mode: Judge engine preflight plus two-round independent local
adversarial plan/ledger review and deterministic grounding.

Engine status:

- Codex CLI `0.145.0`: runtime-broken for this review. It returned no review
  payload after 12 minutes and was stopped; it is not counted as a pass.
- Claude Code `2.1.199`: runtime-broken because the local CLI was not logged
  in; it returned no findings and is not counted as a pass.
- Antigravity: unavailable; this is the normal optional-engine path.
- Independent local reviewer: completed both rounds read-only.

Round 1 grounded three High and three Medium blockers:

| Finding | Severity | Resolution |
|---|---:|---|
| Authorization candidate was generated after tests that require it | High | Candidate now precedes the final freeze, double coordinator run, PAX, and geometry gates |
| V1-only publication contradicted V2 lost-response reconciliation | High | Locked state split now writes only from V1 and reconciles V2 read-only |
| 631 content leaves omitted commit-critical authority descriptors | High | Exact union is now 631 content + 16 authority = 647 retained, floor 963 |
| Accepted O1 could accidentally expire under ambient time | Medium | Every Sequence 18 path uses only frozen parent timestamps |
| Bootstrap crash prefixes had no closed recovery state | Medium | Added V0, fixed create order, exact-prefix resume, fault injection, and locked handoff |
| Plan/checklist/matrix and ledger mappings differed | Medium | Rebuilt one direct reciprocal graph and canonical ledger |

Round 2 independently verified all six findings closed and found no new High
or Medium blocker. Direct grounding additionally confirms:

- all thirteen O1 parent references and three implementation baselines remain
  exact;
- review, candidate, and root are absent;
- the ledger is canonical compact key-sorted JSON with 7 requirements, 8
  acceptance criteria, 32 scenarios, 10 implementation nodes, and 18 tests;
- all direct edges resolve both ways at 10000 basis points with zero gaps or
  orphans.

```text
intent_alignment: PASS
CRITICAL: 0 unresolved
HIGH:     0 unresolved
MEDIUM:   0 unresolved
LOW:      0 actionable
INFO:     2 runtime-broken engines, not counted as passes
verdict:  APPROVE FOR SEPARATE IMPLEMENTATION ACCEPTANCE
```

## Change History

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-07-30 | Initial Sequence 18 O1 lifecycle-test correction plan |
| 0.2 | 2026-07-30 | Closed three High and three Medium lifecycle, ordering, TOCTOU, time, recovery, and traceability blockers |
| 1.0 | 2026-07-30 | Independent round-2 review approved the corrected plan with no unresolved blocker |
