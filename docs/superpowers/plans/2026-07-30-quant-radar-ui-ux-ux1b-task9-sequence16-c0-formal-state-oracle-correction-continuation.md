# Quant Radar UX-1B Sequence 17 C0 Formal-State Oracle Correction Plan

## Document Info

| Field | Value |
|---|---|
| Type | Implementation plan with test specification |
| Version | `0.2-reviewed` |
| Status | Reviewed locally; awaiting maintainer implementation acceptance |
| Date | `2026-07-30` |
| Author | Scribe workflow |
| Reviewer | Grounded single-context review; Judge multi-engine review unavailable under the no-subagent workspace policy |
| Approver | Repository maintainer |
| Audience | Maintainer, implementation agent, formal reviewer, release gate |
| Parent state | Exact retained Sequence 16 `C0_PACKET` |
| Required next handoff | Builder implementation only after separate maintainer acceptance |

This plan is planning authority only. It does not authorize implementation,
bootstrap, preflight, intake, review, candidate, root, capture, comparison,
or theme work.

## Executive Summary

Sequence 16 safely created and reopened its Tier and preflight at
`C0_PACKET`. The formal-state coordinator then passed `137/138`. The only
failure was `TEST-170`.

`TEST-170` still requires every Sequence 16 formal path to remain absent.
That assertion is valid only before bootstrap. At `C0_PACKET`, the eight
Sequence 16 Tier/preflight paths must exist, while intake, review, candidate,
and root must remain absent.

The Sequence 16 preflight freezes the current source projection. Editing
`TEST-170` directly would invalidate Sequence 16 live source authority.
Sequence 17 therefore imports the exact Sequence 16 `C0_PACKET` checkpoint as
immutable history and creates a distinct corrected current-source authority.

Sequence 17 owns only the still-absent shared intake and manual-review leaves.
It stops at `O2_REVIEW`. It grants no capture, comparison, candidate, root,
theme, UI, API, provider, fixture, or evidence-rewrite authority.

## Problem Statement

The failing code is the final assertion in
`test_170_sequence16_pax_scope_protected_history_and_absence_are_exact()`:

```python
assert all(
    not (ROOT / path).exists()
    for path in handoff.LIFECYCLE_TEST_CORRECTION_FORMAL_PATHS
)
```

After the accepted Sequence 16 bootstrap and preflight, this assertion
rejects the valid state:

```text
Sequence 16 Tier/preflight: present and exact
shared report/packet:       present and exact
shared intake/review:       absent
candidate/root:             absent
```

The failure is deterministic and lifecycle-related. It is not source,
runtime, Tier, preflight, report, packet, or cleanup corruption.

## Goals

- Preserve the exact Sequence 16 `C0_PACKET` checkpoint without mutation.
- Stop and re-plan if that exact parent state advances before Sequence 17
  bootstrap; never adopt a concurrently created shared leaf.
- Replace the permanent total-absence oracle with a closed lifecycle oracle.
- Keep creation-time absence tests in disposable namespaces.
- Reauthorize corrected current source under a distinct Sequence 17 identity.
- Preserve the exact five-input, 125-item packet and all review semantics.
- Preserve the locked bounded-stdin broker and create-once publication model.
- Stop at `O2_REVIEW` with candidate and root absent.
- Make every permanent formal-state test valid at implementation, `O0`,
  `O1`, and `O2`.

## Non-Goals

- No recapture or migration comparison.
- No new report or packet.
- No change to the 81 page, 44 control-root, or 125 total review items.
- No rewrite, move, deletion, or temporary hiding of Sequence 16 artifacts.
- No reuse of the expired or expiring Sequence 16 reviewer freshness window.
- No candidate or root publication.
- No UI, API, provider, fixture, selector, theme, or evidence changes.
- No dependency, runtime, database, OpenAPI, or environment-default changes.
- No weakening of legacy Sequence 15 or Sequence 16 live fail-closed behavior.

## Success Metrics

| Metric | Target | Measurement |
|---|---:|---|
| Formal-state coordinator | `148/148` | Full coordinator after implementation and after later formal states |
| Current blocker | `0` failures | `TEST-170` at exact retained Sequence 16 C0 |
| Lifecycle states | exactly `3` | `O0_PACKET`, `O1_INTAKE`, `O2_REVIEW` |
| Invalid namespace shapes | `61/64` rejected | Exhaustive forward-presence table |
| Parent reference drift | `0/12` | Exact hash, size, mode, owner, group, link checks |
| Source projection | `270` records | Current mirror builder |
| Supplemental projection | `67` records | Current supplemental builder |
| Retained materials | `628` unique leaves | Descriptor-only material-set construction |
| Required descriptor floor | `944` | `628 + 252 + 64` |
| Candidate/root writes | `0` | Formal namespace inventory |
| Traceability | `10000` basis points | Canonical ledger validator |

## Grounded Parent State

### Sequence 16 fixed identities

```text
captureId:                         20260729T040000Z
packetContinuationId:              20260729T060000Z
parentExternalReviewCorrectionId:  20260729T070000Z
lifecycleTestCorrectionId:         20260729T080000Z
lifecycleTestTierId:               20260729T081000Z
state:                             C0_PACKET
```

### Sequence 16 exact C0 references

| # | Path | SHA-256 | Bytes | Mode |
|---:|---|---|---:|---:|
| 1 | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.md` | `9d6e73a40ec3f3f8e7a11ddc1198941775d065d06920e4ed505f341b64f24a4e` | 51158 | `0644` |
| 2 | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.traceability.yaml` | `8313fdcecd1b7b828b475894c3bd390f2dddda0cfe7be119e75c01c0a56632a4` | 9573 | `0644` |
| 3 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-seq16.md` | `99e417fae2859ac92747229797124e5467ab4725474fb182121e2cb51ee45f2b` | 8056 | `0644` |
| 4 | `.claude/ui_snapshots/ux1b/recovery/.external-review-lifecycle-test-correction-20260729T080000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 | `0600` |
| 5 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-prechange-seq16.json` | `d1ae2a0b72e86353053f13f823bfc8f6b95b744afb6fd5bc4a6fa25ec5b216a6` | 5948 | `0600` |
| 6 | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-rollback-seq16.json` | `4c3b53478c08cbc59dbf9bc1ee8f1ad2a79b814c25367ba66723e3002addad61` | 2539 | `0600` |
| 7 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-prechange-20260729T081000Z/.quant-radar-theme-handoff-external-review-lifecycle-test-correction-owner` | `1cc06b3720a458b41615dcb8586f75c56d7fd879e6853517dea364e5eb6e34ac` | 176 | `0600` |
| 8 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-prechange-20260729T081000Z/prechange-files.tar` | `b2573f7f3a501b02b7465356a3ce36f5f43b13c4e37db2e20e3d6582b1bc486b` | 2959360 | `0600` |
| 9 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-prechange-20260729T081000Z/bundle-manifest.json` | `51884e1b179a5d1192c160c0f98b50afed6d1cb0ad455cf93daeb5b9513e2a80` | 1231 | `0600` |
| 10 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-preflight-20260729T080000Z.json` | `bde901d616f32abdaf02c663f4ac353aca403bf0852eb8f78e57fe74949f0eb1` | 66754 | `0600` |
| 11 | `.claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json` | `97a37c01a7fefbaf20386a6bb732e87993e8f282ba3216885ad92f2530a7f553` | 12444 | `0600` |
| 12 | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json` | `1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd` | 89295 | `0600` |

All twelve files are current-owner, current-group, one-link regular files.
The retained Tier directory is mode `0700` and contains exactly the owner
marker, `prechange-files.tar`, and `bundle-manifest.json`.

### Embedded Sequence 16 preflight facts

```text
createdAt:                    2026-07-29T21:31:22Z
reviewDeadline:               2026-07-30T21:31:22Z
source projection:            270 / a44dac6c0b215f36f83fe453fe8189b4249995991172f7cf85339e9835f71766
supplemental projection:       64 / 44636911f167d4024a35e1de94fa7433758b7e8d4cb4636749e7de623588698e
runtime tree:                       9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75
retained/protocol/reserve/floor:   625 / 252 / 64 / 941
raise ceiling:                      1536
```

The Sequence 16 reviewer appointment and deadline are historical facts.
Sequence 17 must not submit under that appointment.

## Requirements

### Functional requirement

**REQ-018 — Continue review from exact Sequence 16 C0**

The system must preserve Sequence 16 C0 as immutable history and expose a
distinct corrected review-only lifecycle.

### Cross-functional requirements

**CFR-085 — Historical exactness**

The importer must authenticate every fixed Sequence 16 reference and every
embedded preflight cross-link without rebuilding frozen source.

**CFR-086 — Lifecycle completeness**

Every permanent real-workspace oracle must accept only the exact valid
implementation, `O0`, `O1`, or `O2` state applicable at execution time.

**CFR-087 — Authority isolation**

Sequence 17 must use distinct IDs, Tier, preflight, reviewer session,
commands, and authorization bytes.

**CFR-088 — Atomic review transport**

Review intake and publication must retain the existing lock, bounded stdin,
no-replace publication, fsync, exact digest, and different-inode properties.

**CFR-089 — Descriptor and runtime safety**

The active authority must bind exactly 628 retained materials, a 944
descriptor floor, the fixed runtime receipt, and exact restoration behavior.

**CFR-090 — Scope and formal-boundary safety**

Implementation may touch only the declared files. Formal execution must stop
at `O2_REVIEW` with candidate and root absent.

## Acceptance Criteria

### AC-SEQ17-001 — Exact parent import

Given the twelve fixed Sequence 16 references and exact C0 namespace,
when the historical importer runs,
then it returns the retained C0 report, packet, projections, runtime, Tier,
and preflight without opening frozen source-member paths.

### AC-SEQ17-002 — Permanent lifecycle oracle

Given the real workspace at retained C0 or an exact Sequence 17 state,
when `TEST-170` and the full coordinator run,
then valid state passes and every partial or unauthorized shape fails.

### AC-SEQ17-003 — Distinct active authority

Given an accepted Sequence 17 authorization candidate,
when bootstrap and preflight run,
then they create or reopen only the Sequence 17 Tier and preflight and report
`O0_PACKET`.

### AC-SEQ17-004 — Correct review truth

Given an exact 125-item review candidate,
when the Sequence 17 broker validates it,
then accepted and rejected outcomes follow the same four-quadrant decision
truth as Sequence 16 under the new appointment.

### AC-SEQ17-005 — Exact material transaction

Given the authenticated packet and active source projections,
when intake or review publication opens retained materials,
then exactly 628 unique leaves remain open under a 944 descriptor floor.

### AC-SEQ17-006 — Atomic forward lifecycle

Given `O0_PACKET`,
when the accepted intake bytes are submitted and published,
then the lifecycle advances monotonically to `O1_INTAKE` and `O2_REVIEW`
using byte-identical different-inode files.

### AC-SEQ17-007 — Compatibility and fail-closed behavior

Given corrected current source,
when old Sequence 16 live verification runs,
then it fails closed while the Sequence 17 historical importer and active
validator remain valid.

### AC-SEQ17-008 — Scope and pause

Given implementation or any later authorized formal state,
when scope, hash, cleanup, and absence gates run,
then protected history is unchanged and candidate/root remain absent.

## BDD Scenarios

| ID | Given | When | Then |
|---|---|---|---|
| `SC-AC-SEQ17-001-HP-001` | Exact retained C0 | Historical import | Import succeeds without live member reads |
| `SC-AC-SEQ17-001-NP-001` | One parent hash differs | Historical import | Contract violation |
| `SC-AC-SEQ17-001-NP-002` | Embedded runtime receipt differs with a matching outer hash | Historical import | Contract violation |
| `SC-AC-SEQ17-001-NP-003` | PAX member metadata or order differs | Historical import | Contract violation |
| `SC-AC-SEQ17-001-NP-004` | Shared intake/review appears before Sequence 17 bootstrap | Parent-state gate | Block and require a new continuation plan |
| `SC-AC-SEQ17-002-HP-001` | Exact retained Sequence 16 C0 | Full coordinator | `TEST-170` passes |
| `SC-AC-SEQ17-002-HP-002` | Exact `O0_PACKET` | Full coordinator | All permanent lifecycle tests pass |
| `SC-AC-SEQ17-002-HP-003` | Exact `O1_INTAKE` | Full coordinator | All permanent lifecycle tests pass |
| `SC-AC-SEQ17-002-HP-004` | Exact `O2_REVIEW` | Full coordinator | All permanent lifecycle tests pass |
| `SC-AC-SEQ17-002-NP-001` | Partial Sequence 17 Tier | Lifecycle oracle | Contract violation |
| `SC-AC-SEQ17-002-NP-002` | Intake exists without exact preflight | Lifecycle oracle | Contract violation |
| `SC-AC-SEQ17-002-NP-003` | Candidate or root exists | Lifecycle oracle | Contract violation |
| `SC-AC-SEQ17-002-BP-001` | Pre-authorization disposable fixture | Absence oracle | All Sequence 17 formal paths absent |
| `SC-AC-SEQ17-003-HP-001` | Accepted exact authorization | Bootstrap twice | Created, then verified |
| `SC-AC-SEQ17-003-HP-002` | Complete Tier | Preflight twice | Created, then verified `O0_PACKET` |
| `SC-AC-SEQ17-003-NP-001` | Wrong ID or command | Public handler | Exit contract rejects it |
| `SC-AC-SEQ17-003-EP-001` | Same package built twice | PAX builder | Byte-identical archives |
| `SC-AC-SEQ17-004-HP-001` | No rejected item or blocking finding | Review validation | Accepted |
| `SC-AC-SEQ17-004-HP-002` | Rejected item only | Review validation | Rejected |
| `SC-AC-SEQ17-004-HP-003` | Blocking finding only | Review validation | Rejected |
| `SC-AC-SEQ17-004-HP-004` | Both rejection signals | Review validation | Rejected |
| `SC-AC-SEQ17-004-NP-001` | Sequence 16 reviewer/session reused | Review validation | Contract violation |
| `SC-AC-SEQ17-005-BP-001` | 628 retained leaves | Material transaction | Accepted |
| `SC-AC-SEQ17-005-NP-001` | 627 or 629 retained leaves | Material transaction | Contract violation |
| `SC-AC-SEQ17-005-NP-002` | Required floor differs from 944 | Descriptor validation | Contract violation |
| `SC-AC-SEQ17-006-HP-001` | Exact candidate digest and size | Intake broker | `O1_INTAKE` |
| `SC-AC-SEQ17-006-HP-002` | Exact intake | Review publisher | `O2_REVIEW` |
| `SC-AC-SEQ17-006-NP-001` | Partial, oversized, or noncanonical stdin | Intake broker | No final leaf |
| `SC-AC-SEQ17-006-EP-001` | Lost response after commit | Rerun | Read-only reconciliation |
| `SC-AC-SEQ17-007-HP-001` | Current corrected source | Sequence 17 verify | Pass |
| `SC-AC-SEQ17-007-NP-001` | Current corrected source | Sequence 16 live verify | Fail closed |
| `SC-AC-SEQ17-008-HP-001` | Implementation complete | Scope audit | Only declared files changed |
| `SC-AC-SEQ17-008-NP-001` | UI/API/dependency or evidence drift | Scope audit | Block |
| `SC-AC-SEQ17-008-NP-002` | Candidate or root exists at O0/O1/O2 | Absence gate | Block |

## Architecture

### Historical and active planes

```text
exact Sequence 16 C0 bytes
        |
        v
_import_sequence16_c0_preflight()
        |
        +---- immutable parent projection
        |
corrected current source
        |
        v
Sequence 17 Tier/preflight
        |
        v
O0_PACKET -> O1_INTAKE -> O2_REVIEW
                               |
                               +-> mandatory stop
```

Historical import and active validation must remain separate. The historical
importer may trust exact whole-file bytes only after validating their
internal schemas, digests, PAX members, cross-links, cardinalities, runtime
receipt, Make contract, reviewer contract, and directory inventory.

It must not call these live Sequence 16 functions:

```text
_build_lifecycle_test_correction_source_projections
_build_lifecycle_test_correction_preflight_value
_validate_lifecycle_test_correction_preflight_value
_reauthenticate_lifecycle_test_correction_preflight
_validate_lifecycle_test_correction_tier_complete
```

### Sequence 17 identities

```text
captureId:                       20260729T040000Z
packetContinuationId:            20260729T060000Z
parentLifecycleCorrectionId:     20260729T080000Z
formalStateOracleCorrectionId:   20260730T010000Z
formalStateOracleTierId:         20260730T011000Z
reviewSessionId:                 seq17-20260730T010000Z-review-01
reviewerId:                      judge-seq17-control-migration@seq17-20260730T010000Z-review-01
```

### Sequence 17 lifecycle

| State | Report | Packet | Intake | Review | Candidate | Root |
|---|---:|---:|---:|---:|---:|---:|
| `O0_PACKET` | 1 | 1 | 0 | 0 | 0 | 0 |
| `O1_INTAKE` | 1 | 1 | 1 | 0 | 0 | 0 |
| `O2_REVIEW` | 1 | 1 | 1 | 1 | 0 | 0 |

Exactly these three of the 64 forward-presence combinations are valid.

### Lifecycle-oracle rule

No permanent test may equate safety with total formal absence.

Permanent real-workspace tests must:

1. Classify Sequence 17 Tier and preflight presence.
2. Import exact Sequence 16 C0 history.
3. Validate the applicable `O0`, `O1`, or `O2` forward state.
4. Require candidate and root absence in every state.
5. Reject all partial, mixed-authority, or unauthorized prefixes.

Total creation-time absence belongs only in disposable fixtures or a
classifier branch that proves the workflow is still at implementation
boundary.

### Parent-state drift and authority handoff

The exact Sequence 16 `C0_PACKET` namespace is a prerequisite, not merely
historical input. Intake and review must still be absent at all four
handoff checkpoints:

1. Phase S17-0 before the first source edit.
2. Immediately after implementation and before the authorization candidate
   is generated.
3. Immediately before an accepted authorization is consumed.
4. Under the coordinator lock immediately before Sequence 17 Tier creation.

At checkpoints 1-3, the gate must validate all twelve fixed references,
the exact Sequence 16 C0 namespace, and absence of Sequence 17 Tier/preflight.
Checkpoint 4 must repeat that validation while holding the same global lock
used by bootstrap. If shared intake or review appears at any checkpoint,
Sequence 17 must not claim it, delete it, or reinterpret it. The continuation
is stale and a new plan must begin from the newly observed parent state.

After the first source edit, Sequence 16 live verification remains
fail-closed. This does not replace the namespace gate: a concurrent or
out-of-band write still blocks Sequence 17.

## Source and Descriptor Geometry

### Package paths

```text
Makefile
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-seq17.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

The current Sequence 16 supplemental projection contains 64 records. The
three new plan, ledger, and authorization paths are distinct. Makefile and
both scripts are already represented.

```text
sourceProjection       = 270
supplementalProjection = 64 + 3 = 67
retainedMaterials      = 625 + 3 = 628
protocolAdditional     = 252
reserve                = 64
requiredSoftFloor      = 628 + 252 + 64 = 944
raiseCeiling           = 1536
```

Implementation must prove these counts from authenticated records. It must
not rely on comments or arithmetic alone.

## Public Commands and Make Routes

### Coordinator commands

```text
bootstrap-external-review-formal-state-oracle-correction
preflight-external-review-formal-state-oracle-correction
verify-external-review-formal-state-oracle-correction-preflight
submit-formal-state-corrected-review-intake
publish-formal-state-corrected-review
```

### Make routes

```text
ui-ux1b-external-review-formal-state-oracle-bootstrap
ui-ux1b-external-review-formal-state-oracle-preflight
ui-ux1b-external-review-formal-state-oracle-verify
ui-ux1b-external-review-formal-state-oracle-submit-intake
ui-ux1b-external-review-formal-state-oracle-publish
```

All commands require the five exact Sequence 17 identity arguments and
`--json`. Submit additionally requires bounded stdin, accepted SHA-256, and
accepted byte size.

## Implementation Checklist

| ID | Deliverable | Requirements | Tests |
|---|---|---|---|
| `IMPL-134` | Fixed Sequence 16 C0 refs and descriptor-only PAX parser | `REQ-018`, `CFR-085` | `TEST-172`, `TEST-179` |
| `IMPL-135` | `_import_sequence16_c0_preflight()` with exact internal semantics | `REQ-018`, `CFR-085`, `CFR-086` | `TEST-170`, `TEST-172`, `TEST-173` |
| `IMPL-136` | Lifecycle-aware replacement for the final TEST-170 assertion | `REQ-018`, `CFR-086`, `CFR-090` | `TEST-170`, `TEST-173`, `TEST-180` |
| `IMPL-137` | Sequence 17 IDs, authorization parser, package, PAX, Make, and grammar | `REQ-018`, `CFR-087`, `CFR-090` | `TEST-174`, `TEST-180`, `TEST-181` |
| `IMPL-138` | Sequence 17 Tier, lease, namespace, preflight, and runtime binding | `REQ-018`, `CFR-087`, `CFR-089` | `TEST-174`, `TEST-175`, `TEST-177` |
| `IMPL-139` | Parameterized reviewer validation for the new appointment | `REQ-018`, `CFR-087`, `CFR-088` | `TEST-176`, `TEST-178` |
| `IMPL-140` | Exact 628-material transaction and 944-floor profile | `REQ-018`, `CFR-088`, `CFR-089` | `TEST-177`, `TEST-178` |
| `IMPL-141` | Sequence 17 intake/review handlers and registry routes | `REQ-018`, `CFR-087`, `CFR-088`, `CFR-090` | `TEST-175`, `TEST-176`, `TEST-178`, `TEST-179` |
| `IMPL-142` | Full verification, authorization candidate, and implementation journals | `REQ-018`, `CFR-085`, `CFR-086`, `CFR-087`, `CFR-088`, `CFR-089`, `CFR-090` | `TEST-170`, `TEST-172`–`TEST-181` |

## Test Specification

| ID | Purpose | Expected result |
|---|---|---|
| `TEST-170` | Permanent PAX/scope/protected-history/lifecycle oracle | Passes at retained C0 and exact O0/O1/O2 |
| `TEST-172` | Exact Sequence 16 C0 historical import | No live reads; all semantic mutations rejected |
| `TEST-173` | Parent and active lifecycle truth table | Only implementation/C0/O0/O1/O2 applicable states accepted |
| `TEST-174` | IDs, authority, CLI, Make, package, and deterministic PAX | Exact closed contracts |
| `TEST-175` | Sequence 17 namespace truth table | Exactly 3 of 64 forward states accepted |
| `TEST-176` | Reviewer appointment and decision quadrants | Four honest outcomes under Sequence 17 identity |
| `TEST-177` | Material set and descriptor budget | Legacy 625/941 and current 628/944 both exact |
| `TEST-178` | Atomic broker/publication | Create-once, byte-identical, different inode, fsync |
| `TEST-179` | Historical/live authority separation | Old live fails; exact history and new active pass |
| `TEST-180` | PAX, scope, protected refs, and lifecycle-aware absence | No permanent total-absence assumption |
| `TEST-181` | Traceability, full gates, and formal pause | 10000 bps and stop at O2 |

The expected coordinator count after adding ten tests is `148`.

## Implementation Phases and Gates

### Phase S17-0 — exact reopen and red reproduction

- Reopen the exact Sequence 16 Tier/preflight at `C0_PACKET`.
- Re-run the complete coordinator.
- Require exactly `137/138`, with only TEST-170 failing.
- Verify intake, review, candidate, and root absence.
- Repeat the exact parent-state gate immediately before the first source
  edit; any newly created shared leaf invalidates this plan.

**Gate:** any other failure or parent drift blocks implementation.

### Phase S17-1 — historical C0 importer

- Add the twelve exact parent refs.
- Parse the six-member Sequence 16 PAX without extraction.
- Validate exact preflight schemas, keys, projections, runtime, Make,
  reviewer, descriptor, Tier, report, packet, and cross-links.
- Prohibit live Sequence 16 source/preflight/Tier validators.

**Gate:** exact retained C0 passes; every outer or semantic mutation fails.

### Phase S17-2 — lifecycle oracle correction

- Replace TEST-170 total absence with the closed classifier.
- Keep total-absence mutation coverage in disposable fixtures.
- Enumerate partial Tier, preflight, and forward shapes.
- Require candidate/root absence at all permanent states.

**Gate:** retained C0 passes without moving or hiding any artifact.

### Phase S17-3 — distinct current authority

- Add IDs, authorization body/parser, Tier, preflight, package, PAX, Make,
  namespace, reviewer, and runtime contracts.
- Freeze a fresh `createdAt` and 24-hour `reviewDeadline` at preflight.
- Do not reuse the Sequence 16 appointment or deadline.

**Gate:** production-shaped disposable execution reaches only `O0_PACKET`.

### Phase S17-4 — material and broker continuation

- Preserve Sequence 16 compatibility wrappers.
- Add exact 628/944 active profile.
- Reuse locked bounded stdin and no-replace/fsync primitives.
- Add authority-specific intake and review handlers.

**Gate:** accepted/rejected O1/O2 flows pass; candidate/root remain absent.

### Phase S17-5 — implementation verification

- Run TEST-170 and TEST-172 through TEST-181.
- Run the complete `148/148` coordinator.
- Run complete repository `make test`.
- Run complete recovery, fail-soft API/UI, isolation, evidence, selector,
  fixture, snapshot, theme, and navigation suites.
- Run compile, Python 3.10 AST, tabnanny, dependency, whitespace, diff,
  source-scope, runtime, process, cleanup, protected-hash, PAX, and lifecycle
  gates.
- Compare actual diff to the affected-file list.
- Re-run the exact parent-state gate before generating authorization bytes.
- Generate only the Sequence 17 authorization candidate.

**Gate:** zero failing test caused by the change and zero unexplained drift.

### Phase S17-6 — authorization handoff

- Report exact authorization SHA-256, byte size, and mode.
- Require separate maintainer acceptance.
- Re-run protected refs and collision/absence gates.
- Before consuming acceptance, require the parent state to remain exact C0.

**Gate:** no Sequence 17 Tier or preflight without exact acceptance.

### Phase S17-7 — bootstrap/preflight and reviewer pause

- Bootstrap and preflight Sequence 17.
- Acquire the coordinator lock before the final parent-state recheck and hold
  it through create-once Tier publication.
- Reopen exact `O0_PACKET`.
- Run the full lifecycle-aware coordinator.
- Stop for reviewer-candidate preparation.

**Gate:** intake, review, candidate, and root remain absent.

### Phase S17-8 — independent review and intake

- Appoint the exact Sequence 17 reviewer session.
- Use an OS-enforced read-only workspace sandbox.
- Produce the 125-item candidate outside the workspace.
- Require exact candidate digest and size acceptance.
- Stream the same bytes through the broker and verify `O1_INTAKE`.

**Gate:** exact appointment, fresh deadline, 628 materials, and zero reviewer
workspace writes.

### Phase S17-9 — publish review and stop

- Publish byte-identical different-inode review.
- Reopen exact `O2_REVIEW`.
- Preserve accepted or rejected truth.
- Stop with candidate and root absent.

**Gate:** Sequence 17 authorizes no further command.

## Affected Files

### Planning outputs authorized in this turn

```text
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence16-c0-formal-state-oracle-correction-continuation.traceability.yaml
.agents/scribe.md
.agents/judge.md
.agents/PROJECT.md
```

### Planned implementation edits after separate acceptance

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-seq17.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

### Later formal outputs after separate authorization acceptance

```text
.claude/ui_snapshots/ux1b/recovery/.external-review-formal-state-oracle-correction-20260730T010000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-prechange-seq17.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-formal-state-oracle-correction-rollback-seq17.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-prechange-20260730T011000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-preflight-20260730T010000Z.json
.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

### Protected paths

```text
all Sequence 8-16 plans, ledgers, authorizations, Tier, preflights, captures,
stacks, manifests, reports, packets, intakes, reviews, candidates, and roots
all production ui/, api/, provider, fixture, selector, theme, and evidence files
all packet-referenced images and sidecars
requirements.txt
.venv/
```

## Verification Commands

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
make test
make ui-ux1b-recovery-tests
.venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m pip check
git diff --check
```

Python 3.10 compatibility must use an actual Python 3.10 interpreter when
available. Otherwise use Python 3.11 or newer with
`ast.parse(..., feature_version=(3, 10))` and report the limitation.

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Repeating the permanent absence bug in a new test | High | Explicit lifecycle-oracle rule; full suite required at C0/O0/O1/O2 |
| Recomputing Sequence 16 frozen source | High | Descriptor-only historical import; prohibit five live parent functions |
| Reusing expired Sequence 16 reviewer freshness | High | Distinct reviewer/session and fresh Sequence 17 preflight deadline |
| Editing protected C0 evidence | High | Exact twelve-ref hash gate before and after every phase |
| Material count drift | High | Exact 628 set, 944 floor, boundary tests at 627/629 |
| Shared intake consumed by old authority | High | Four exact parent-state checkpoints; final recheck and first commit share the coordinator lock; drift forces re-planning |
| Candidate/root authority leakage | High | Grammar, namespace states, formal pause, and absence gates forbid both |
| Planning mistaken for execution authority | Medium | Separate plan, implementation, authorization, reviewer-candidate acceptances |

## Rollback and Recovery

### Before implementation acceptance

- Remove no formal artifact.
- Planning files may be revised only through reviewed plan changes.
- Preserve exact Sequence 16 C0.

### During implementation

- Revert only explained Sequence 17 source changes through the normal worktree
  workflow.
- Never restore source from Sequence 16 PAX over the live worktree.
- Never mutate, move, or hide Sequence 16 C0 to make tests pass.

### After Sequence 17 Tier

- Follow only the Sequence 17 rollback contract.
- Preserve partial evidence unless that contract explicitly authorizes cleanup.

### After `O0_PACKET`

- Treat Sequence 17 preflight as immutable.
- Any new source defect requires a new correction authority.

## Glossary

| Term | Meaning |
|---|---|
| Historical importer | Validates exact retained bytes without rebuilding current source |
| Live validator | Authenticates current source/runtime under the active authority |
| Permanent oracle | Test that remains valid after formal lifecycle progression |
| Creation-time absence | All formal outputs absent before bootstrap |
| `C0_PACKET` | Retained Sequence 16 report/packet state |
| `O0_PACKET` | Sequence 17 active packet state |
| `O1_INTAKE` | Sequence 17 accepted reviewer intake state |
| `O2_REVIEW` | Sequence 17 published manual-review state and mandatory pause |
| Shared leaf | Intake or review path reused across compatible correction authorities |

## Traceability Matrix

| Requirement | Acceptance | Implementation | Tests |
|---|---|---|---|
| `REQ-018` | `AC-SEQ17-001`–`008` | `IMPL-134`–`142` | `TEST-170`, `TEST-172`–`181` |
| `CFR-085` | `AC-SEQ17-001`, `007`, `008` | `IMPL-134`, `135`, `142` | `TEST-172`, `179`, `180`, `181` |
| `CFR-086` | `AC-SEQ17-002`, `007`, `008` | `IMPL-135`, `136`, `142` | `TEST-170`, `173`, `179`, `180`, `181` |
| `CFR-087` | `AC-SEQ17-003`, `004`, `006`, `007` | `IMPL-137`, `138`, `139`, `141`, `142` | `TEST-174`, `175`, `176`, `178`, `179`, `181` |
| `CFR-088` | `AC-SEQ17-004`, `005`, `006` | `IMPL-139`, `140`, `141`, `142` | `TEST-176`, `177`, `178`, `181` |
| `CFR-089` | `AC-SEQ17-003`, `005`, `007` | `IMPL-138`, `140`, `142` | `TEST-174`, `177`, `179`, `181` |
| `CFR-090` | `AC-SEQ17-002`, `003`, `006`, `008` | `IMPL-136`, `137`, `141`, `142` | `TEST-170`, `173`, `174`, `175`, `178`, `180`, `181` |

## Review Checklist

- [x] Exact parent state and blocker reproduced.
- [x] Parent-state race is fail-closed at four handoff checkpoints.
- [x] Scope and non-goals are explicit.
- [x] Historical and live authority are separated.
- [x] Permanent and creation-time absence tests are separated.
- [x] New reviewer freshness does not reuse Sequence 16.
- [x] Descriptor arithmetic and authenticated derivation are specified.
- [x] Candidate/root remain forbidden.
- [x] Affected files and formal outputs are explicit.
- [x] Rollback never mutates protected C0.
- [x] Requirements, ACs, scenarios, implementation nodes, and tests are
      bidirectionally traceable.
- [ ] Maintainer accepts implementation.

## Review Provenance and Result

Review mode: grounded single-context planning review.

Engines used: current Codex context only. Judge multi-engine fan-out was not
run because workspace policy prohibits subagent delegation unless the user
explicitly requests subagents.

```text
intent_alignment: PASS
CRITICAL: 0
HIGH:     0 open after revision
MEDIUM:   0 open after revision
LOW:      0 shipped
INFO:     0 shipped
verdict:  APPROVE FOR MAINTAINER IMPLEMENTATION DECISION
```

This verdict is not an independent multi-engine review.

### Review iterations

| Round | Finding | Severity | Resolution |
|---|---|---:|---|
| 1 | The draft did not define what happens if Sequence 16 advances from exact C0 during the implementation-to-bootstrap handoff. | High | Added four exact parent-state checkpoints, a final locked recheck, and mandatory re-planning on drift. |
| 1 | The traceability ledger was valid JSON but not canonical key-sorted JSON. | Medium | Canonicalized the ledger after the reviewed plan hash was frozen. |
| 1 | Scenario-to-requirement links lacked reverse requirement-to-scenario links. | Medium | Added reciprocal scenario arrays and validated every direct edge both ways. |
| 2 | Rechecked intent, exact parent refs, state geometry, authority isolation, descriptor arithmetic, scope, rollback, and traceability. | — | No open blocking finding. |

## Change History

| Version | Date | Change |
|---|---|---|
| `0.1-draft` | `2026-07-30` | Initial Sequence 17 plan after exact Sequence 16 C0 exposed the TEST-170 lifecycle gap |
| `0.2-reviewed` | `2026-07-30` | Added parent-state race gates and closed canonical/bidirectional traceability review findings |
