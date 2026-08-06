# Quant Radar UX-1B Task 9 Descriptor-Budget Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.1-reviewed` |
| Status | Descriptor and migration-geometry blocking review passed; implementation in progress |
| Authorization | Repository maintainer authorized reviewed Sequence 10 implementation and requested the migration-geometry correction be solved in the same sequence |
| Author / plan reviewer | Codex |
| Approver | Repository maintainer |
| Audience | Maintainers, implementers, code reviewers, and evidence reviewers |
| Sequence | `10` |
| Capture recovery ID | `20260725T080000Z` (immutable Sequence 8 lineage) |
| Continuation ID | `20260726T210000Z` (immutable Sequence 9 lineage) |
| Correction ID | `20260727T030000Z` |
| Correction Tier ID | `20260727T031000Z` |
| Imported predecessor | Exact Sequence 9 authorization, Tier, preflight, failed public comparator observation, and its complete Sequence 8 / Task 6 chain |
| Parent correction plan | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-postcapture-continuation-correction.md` |
| Related ledger | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-descriptor-budget-correction.traceability.yaml` |

## Executive summary

Sequence 9 implementation and formal continuation preflight succeeded, but
the first public downstream command failed before writing its migration
report:

```text
theme-handoff contract error: continuation preflight differs
exit 3
```

The preflight was created and verified while the continuation global lock and
lease descriptors were open. It therefore serialized
`baselineOpenCount:7`, `baselineMaxFd:6`, and `requiredSoft:259`. The public
comparator reopens the same preflight from the normal production dispatcher,
where those two lock descriptors are no longer incidental inputs. The current
validator recalculates `baselineOpenCount:5`, `baselineMaxFd:4`, and
`requiredSoft:257`, then demands byte-for-byte equality with the historical
snapshot. The valid immutable preflight is consequently rejected because the
verifier confuses creation-time telemetry with current runtime authority.

Sequence 10 fixes that semantic error. The exact Sequence 9 budget remains
closed creation-time provenance protected by the known whole-preflight hash;
it is no longer recalculated as an ambient equality oracle. The new Sequence
10 preflight serializes a context-free descriptor profile, not baseline FD
telemetry. Each command independently plans, applies, verifies, and restores
the descriptor capacity needed by its current process. A new correction
authority freezes the corrected source and imports Sequence 9 without
modifying it. The migration/root chain consumes the correction preflight and
traverses it back through Sequence 9 and Sequence 8.

The same review also found one adjacent public-dispatch defect:
downstream `publish-review` calculates its destination by performing a second
root read before checking the first operation's nonzero result. That can mask
busy, collision, or unavailable exits. `init-theme-batch` also performs an
unnecessary second root read after success. Sequence 10 makes committed
transitions return their own destination and requires immediate nonzero
propagation.

This is intended to be the final correction confidence gate, not a promise
that no unknown later defect can exist. Formal work may resume only after
production-dispatch tests exercise the real transition chain without
monkeypatching the budget validator, reauthentication, dispatcher, or
transition functions.

The first such production-shaped comparator canary proved the descriptor
correction and then exposed a second, previously hidden contract mismatch.
All `57` catalog-affected captures reach the frozen migration comparator, but
the comparator requires control roots and shared boundaries to retain exact
`x/y/width`, forbids any height shrink, and permits ordinary content to move
only by positive boundary-height growth. The authenticated native-radio to
segmented/radio migration legitimately changes responsive width, wrapping
height, root position, and downstream flow. Across the `57` affected captures
there are `71` catalog roots, `3,338` common nodes with changed bounds, `530`
removed native-control descendants, and `324` added migrated-control
descendants. The complete canonical changed-geometry projection is `552863`
bytes with SHA-256
`500ddca716dc4eace0cbcdeade8ad18a0a0166988db82edd9c64657f8f99b996`.

Sequence 10 therefore also adds a coordinator-owned migration-geometry
adapter. It authenticates the same immutable manifests/catalog and exact
frozen evidence module, requires that exact closed geometry profile, audits
the actual responsive geometry for containment/viewport/overlap safety, and
uses an in-memory-only canonical geometry view when invoking the frozen
semantic comparator. It never edits, republishes, or weakens
`scripts/ui_ux_evidence.py` or any capture-stack member. Any geometry,
membership, catalog, stable semantic, or evidence-module mutation still
fails before report publication.

## Verified starting state

### Exact Sequence 9 authority

| Artifact | SHA-256 | Size | Mode |
| --- | --- | ---: | --- |
| Sequence 9 plan | `d6647eea506f5b333125f529702492a0df83f0a6dafbe5ac0bb3300d537bad8e` | `44271` | `0644` |
| Sequence 9 ledger | `038750130ad2b81ffc2de7b3e4248b07ac61ded9ca88326b52caf052b90be4ae` | `9077` | `0644` |
| Sequence 9 authorization | `0fc147ce3d461c4379ee84878969ae60c54cd594063bfa08e4dba1c06a5b3b7e` | `4972` | `0644` |
| Sequence 9 Tier prechange | `343a1772a3a985e5e89d5439126037df10de077b5cbe0b6ff0c7ff10e2b22826` | `3095` | `0600` |
| Sequence 9 Tier rollback | `3a4bb734269913ed0a6a5fe48a3c1de903c65bd59ef1491f0543091fbddc7380` | `1554` | `0600` |
| Sequence 9 Tier owner | `0b301b1c3fdb99e4a89c9f3ac13509301b9491e057bece15db69ff46f1c373f8` | `138` | `0600` |
| Sequence 9 Tier archive | `0e53cb8f213ceeb7623d87d621deed47d6c569dd777584d81f6796da39526f5d` | `2027520` | `0600` |
| Sequence 9 Tier bundle manifest | `ee85cda88106fb885c73ed47de85afdf8de0081366a340a0186bce910c658668` | `1018` | `0600` |
| Sequence 9 continuation preflight | `d7086ddb27d702772bfa821e61bd2069aadbf5c450a04a13c505b6328fc2e483` | `117405` | `0600` |
| Sequence 9 lease | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |

All owner-only records have current owner `uid 501`, `gid 20`, `nlink 1`.
The retained Tier directory is owner-only. The preflight remains at inode
`14038845`, device `16777229`; the lease remains at inode `14038450`, device
`16777229`. These identities are observations to reopen, not values to
recreate in a fixture.

The Sequence 9 Tier freezes this exact package:

| Path | SHA-256 | Size |
| --- | --- | ---: |
| `Makefile` | `3176ec03637ce1da50c28a87af039f0f0b8a09c1dca72377e804387a66c6a7be` | `22587` |
| Sequence 9 authorization | `0fc147ce3d461c4379ee84878969ae60c54cd594063bfa08e4dba1c06a5b3b7e` | `4972` |
| `scripts/test_ui_ux_theme_handoff.py` | `808d3d8e84ff8f7f520a01e2068d03250a11c30579271f3c8ed52ae6b25789c1` | `981192` |
| `scripts/ui_ux_theme_handoff.py` | `b47c35f9a05f4d144279f6b110ee987129ce8c9fe8c47275450cddbe9ca7fcc9` | `1009847` |

### Exact descriptor mismatch

The serialized Sequence 9 descriptor budget is:

```json
{
  "baselineMaxFd": 6,
  "baselineOpenCount": 7,
  "hardLimit": 9223372036854775807,
  "peakOpenCount": 259,
  "protocolAdditional": 252,
  "requiredSoft": 259,
  "reserve": 64,
  "softApplied": 259
}
```

Its internal equations are valid:

```text
protocolAdditional = 164 + (2 × 12) + 64 = 252
peakOpenCount       = 7 + 252 = 259
requiredSoft        = max(6 + 1, 259) = 259
```

The public comparator's normal descriptor context observes five baseline
descriptors with maximum FD four, yielding `peakOpenCount` and
`requiredSoft` 257. Only these five descriptor-derived fields differ:
`baselineOpenCount`, `baselineMaxFd`, `peakOpenCount`, `requiredSoft`, and
`softApplied`. The hard limit, protocol envelope, reserve, predecessor,
source, Make contract, namespaces, lease, and every other preflight field
remain equal.

`verify-continuation-preflight` passes because it acquires the same global
lock and lease descriptors before rebuilding. `compare-control-migration`
does not acquire them and fails inside
`_reauthenticate_continuation_preflight` before its output collision check or
publication. This confirms context-dependent recomputation as the root cause.

### Forward namespace

The following formal downstream outputs remain absent:

```text
.claude/ui_snapshots/ux1b/recovery/control-migration-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260725T080000Z.json
.claude/ui_snapshots/ux1b/review-intake/control-migration-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260725T080000Z.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

No capture, migration report, packet, intake, manual review, root candidate,
root, theme batch, theme-state, posttheme, or closure was created by the
failed command.

## Problem statement

The Sequence 9 preflight is immutable evidence of the process that created
it. Its descriptor budget answers:

> What descriptor envelope was planned and applied when this record was
> created?

The validator currently treats it as if it answered:

> Does this later process happen to have the same incidental open
> descriptors?

That second interpretation is invalid. Locks, test harness pipes, log files,
shell launchers, and the public dispatcher can change baseline descriptor
count without changing source, authority, hard limit, protocol complexity, or
available capacity. Requiring equality makes valid evidence dependent on call
stack shape. Opening dummy descriptors to reproduce the old count would hide
the defect and make the next launcher variation fail again.

Directly editing Sequence 9 source and treating its old preflight as current
would also create false provenance. Sequence 10 therefore needs both:

1. corrected descriptor semantics; and
2. a new correction authority over the changed source.

The intended authority graph is:

```text
Sequence 8 capture authority and passed terminal
        │
Sequence 9 continuation Tier + immutable preflight
        │
        ├── historical creation descriptor snapshot (7 / 6 / 259)
        │
Sequence 10 correction Tier + correction preflight
        │
        ├── current runtime descriptor planning per command
        │
        └── migration review → immutable v2 root → parent theme lifecycle
```

Capture recovery, continuation, and correction IDs are distinct identities.
None is an alias or permission to repeat capture.

## Goals and success metrics

- The exact Sequence 9 preflight reopens without byte or filesystem mutation.
- Historical Sequence 9 descriptor validation and current Sequence 10
  profile validation succeed with zero, two, and several additional unrelated
  retained descriptors, provided the current hard limit and protocol capacity
  remain sufficient.
- Every runtime descriptor raise is bounded, verified, and restored to the
  caller's exact original soft/hard pair.
- The real production dispatcher, not an injected handler registry, executes
  `compare-control-migration` successfully and publishes exactly one report
  with `comparedCaptures:117`.
- The comparator authenticates all `117` captures, requires the exact
  `57`-capture / `71`-root geometry-transition profile, audits actual
  responsive geometry, and preserves the frozen semantic comparator as the
  non-geometry oracle.
- Mutation of any affected node bound, control-descendant membership,
  catalog root/boundary, stable semantic, capture-stack digest, or frozen
  evidence-module byte fails before report publication.
- Busy, collision, unavailable, contract, uncertain, interrupted, exhausted,
  and manual exits propagate without a second root read or success envelope.
- All correction-authorized public commands reach their real transition in
  owned success/fault/reconcile fixtures; no transition or validator
  monkeypatch can satisfy this gate.
- Sequence 8/9 artifacts and capture-stack hashes remain exact; API,
  Streamlit, and artifact fail-soft tests continue to pass.
- The formal execution stops after the 117-item packet until an independently
  authored accepted intake exists.

## Scope

### In scope

- Add a separate Sequence 10 descriptor-budget correction authorization
  document, parser, Tier, lease, preflight, and verifier.
- Import the exact Sequence 9 plan, ledger, authorization, complete Tier,
  preflight, package archive, and Sequence 8 chain without modifying them.
- Refactor legacy continuation reconstruction so the builder receives the
  exact stored Sequence 9 descriptor budget and never replans it implicitly.
- Protect the legacy budget with the known exact Sequence 9 preflight hash,
  then validate its closed keys, integer types, bounds, equations, and
  hard-limit compatibility without requiring the verifier's incidental
  baseline FD count to equal the creator's.
- Serialize a new context-free Sequence 10 descriptor profile derived only
  from fixed protocol constants and the current hard limit; do not serialize
  current baseline/open-count/max-FD/required-soft telemetry.
- Plan and apply a fresh bounded runtime descriptor budget around each
  descriptor-heavy reauthentication; restore limits on success and every
  exception path.
- Add explicit correction identity to correction lifecycle, comparator,
  control-review, and pre-root commands.
- Make the root v2 candidate consume the Sequence 10 correction preflight,
  which imports Sequence 9 and Sequence 8.
- Propagate downstream review failures before destination calculation.
- Reuse the committed artifact returned by downstream review and theme-batch
  init instead of reopening the root in a second descriptor context.
- Add production-dispatch tests that exercise real handlers/transitions under
  multiple FD baselines, success, collision, busy, unavailable, interruption,
  uncertain, and reconciliation states.
- Add a coordinator-owned geometry-transition projection with exact expected
  SHA-256 `500ddca7...996`, counts `57/71/3338/530/324`, and a closed
  in-memory semantic-canonicalization path.
- Audit both historical and migrated actual geometry for root/boundary
  containment, horizontal viewport containment, distinct-root/subtree
  non-overlap, descendant ownership, and declared boundary ancestry before
  any canonicalization.
- Run the unchanged frozen comparator against an in-memory canonical geometry
  copy to retain stable identity, counter, state, DOM-order, catalog, capture
  profile, and unaffected-capture enforcement.
- Add a production-shaped owned-workspace canary covering comparator, review,
  root, theme-batch, theme-state, posttheme, and closure mechanics. Test-owned
  review intakes are allowed only inside this isolated canary and are never
  formal review evidence.
- Wire Make to the correction commands and preserve exact nonzero exits.
- After implementation acceptance and formal authority acceptance, resume
  formal execution through the migration packet and stop for external review.

### Non-goals

- Do not edit, regenerate, chmod, relink, truncate, delete, or replace any
  Sequence 8 or Sequence 9 formal artifact.
- Do not change the accepted Sequence 9 authorization document.
- Do not make the old Sequence 9 preflight claim current Sequence 10 source.
- Do not open dummy descriptors, hold unrelated locks, or pad the process to
  reproduce a historical baseline.
- Do not weaken descriptor schema equations, the `1536` safety ceiling, hard
  limit checks, no-follow checks, ownership, mode, link-count, or collision
  rules.
- Do not edit `scripts/ui_ux_evidence.py`, alter its frozen
  `3ae2a02b...09a` bytes, rotate the capture-stack digest, or replace the
  frozen semantic comparator with an allow-all result.
- Do not accept arbitrary responsive geometry. Only the exact authenticated
  `500ddca7...996` transition projection may enter semantic
  canonicalization; every other geometry profile fails closed.
- Do not write normalized manifests, sidecars, captures, or catalog bytes.
  Canonicalization exists only as a defensive in-memory copy.
- Do not rerun `capture-task9` or `reconcile-task9`.
- Do not create a new Task 9 capture recovery ID.
- Do not fabricate or self-approve a formal control, theme-batch,
  theme-state, or posttheme review.
- Do not apply the real semantic UI theme in this correction.
- Do not redesign UI/UX, alter API contracts, or change Streamlit behavior.
- Do not add caller-supplied artifact paths or a general workspace-root
  override to production CLI grammar.
- Do not reset, clean, overwrite, or absorb unrelated dirty-worktree changes.

## Terminology

| Term | Meaning |
| --- | --- |
| Stored descriptor budget | Legacy Sequence 9 creation-time provenance protected by the exact whole-preflight hash. |
| Descriptor profile | Sequence 10 context-free protocol constants and hard-limit policy; it contains no ambient FD telemetry. |
| Runtime descriptor budget | Fresh per-process capacity plan used operationally and never compared to stored baseline telemetry. |
| Historical import validation | Exact hash/schema/link validation of Sequence 9 without asserting its frozen source projection equals Sequence 10 live source. |
| Active correction validation | Validation of current Sequence 10 source, authority, namespace, deterministic descriptor profile, and runtime capacity. |
| Production dispatcher | `_execute_public_command` with `_production_public_handlers()`; no injected `handlers` or `command_handlers`. |
| Test-owned intake | Synthetic accepted review input confined to an owned temporary fixture; never copied to or represented as formal review. |
| Formal namespace | The retained `.claude/ui_snapshots/ux1b` and `docs/ui-ux` paths used by the actual Task 9 lineage. |

## Fixed Sequence 10 namespace

```text
Capture recovery ID:  20260725T080000Z
Continuation ID:      20260726T210000Z
Correction ID:        20260727T030000Z
Correction Tier ID:   20260727T031000Z
Correction lease:     .claude/ui_snapshots/ux1b/recovery/.descriptor-budget-correction-20260727T030000Z.lease
Correction preflight: .claude/ui_snapshots/ux1b/recovery/theme-handoff-descriptor-budget-correction-preflight-20260727T030000Z.json
Correction bundle:    .claude/ui_snapshots/ux1b/recovery/theme-handoff-descriptor-budget-correction-prechange-20260727T031000Z/
```

Create these plan-owned Tier documents:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-descriptor-budget-correction-prechange-seq10.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-descriptor-budget-correction-rollback-seq10.json
```

Create the authorization candidate only during implementation:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-descriptor-budget-correction-seq10.md
```

It must contain exactly one closed
`UX1B_FORMAL_HANDOFF_DESCRIPTOR_BUDGET_CORRECTION_V1` marker. Its exact keys
are `schemaVersion,sequence,correctionId,continuationId,captureRecoveryId,
tierId,plan,traceability,predecessor,allowedCommands,forbiddenCommands,
cardinalities,precedence`. `predecessor` binds the exact Sequence 9
authorization, Tier, lease, and preflight set. The marker also binds the final
closed package membership. Its whole-document SHA-256, size, and mode require
separate maintainer acceptance before formal bootstrap.

The correction lifecycle commands are:

```text
bootstrap-descriptor-budget-correction
preflight-descriptor-budget-correction
verify-descriptor-budget-correction-preflight
```

They require exact `--capture-recovery-id`, `--continuation-id`, and
`--correction-id` arguments. The comparator, control-review, and pre-root
command families also require the correction ID. Published-root consumers
derive correction provenance from the root and retain their existing
batch/run arguments.

`allowedCommands` is the exact sorted set of these 22 commands:

```text
apply-theme-batch
bootstrap-descriptor-budget-correction
capture-posttheme
capture-theme-states
close-theme-states
compare-control-migration
finalize-theme
init-theme-batch
preflight-descriptor-budget-correction
prepare-handoff
prepare-review
publish-handoff
publish-review
reconcile-posttheme
reconcile-theme-batch
reconcile-theme-states
seal-theme-batch
verify-descriptor-budget-correction-preflight
verify-handoff
verify-handoff-candidate
verify-theme-batch-applied
verify-theme-batch-ready
```

`forbiddenCommands` is exactly
`bootstrap,bootstrap-continuation,capture-task9,preflight,
preflight-continuation,reconcile-task9,verify-preflight`. The read-only
historical `verify-continuation-preflight` and syntax verifier grant no
Sequence 10 lifecycle authority and belong to neither set.

## Descriptor-budget correction design

### Historical budget and active profile

`_build_continuation_preflight_value` accepts a required
`descriptor_budget` mapping for reconstruction of the existing Sequence 9
record. It must not call `_plan_preflight_descriptor_budget` or inspect
ambient FD state. Historical import first requires the exact known preflight
SHA `d7086ddb...e483`, size `117405`, mode `0600`, owner, and `nlink 1`;
therefore a coherent rewrite of the legacy budget is still rejected. It then
validates the budget's exact keys, integer types, equations, bounds, and hard
limit and passes the normalized stored value back to the builder unchanged.

The new correction preflight does not copy that legacy shape. Its
`descriptorProfile` has exactly these keys and values/policies:

```json
{
  "hardLimit": 9223372036854775807,
  "maxPathDepth": 12,
  "protocolAdditional": 252,
  "raiseCeiling": 1536,
  "reserve": 64,
  "schemaVersion": "quant-radar-ui-ux-descriptor-profile/v1",
  "worstCaseUniqueRetainedLeaves": 164
}
```

`protocolAdditional` must equal
`164 + (2 × 12) + 64`. The correction builder recomputes this context-free
profile from closed constants and the current hard limit on every validation;
it never samples open count or maximum open FD. A coherent profile mutation
therefore differs from the deterministic expected value and fails.
`raiseCeiling` limits only a soft-limit increase; an already-higher inherited
soft limit is retained and later restored rather than lowered before work.

Validation performs this order:

1. reopen and exact-hash validate the historical Sequence 9 preflight;
2. validate its stored legacy budget without ambient recomputation;
3. deterministically rebuild the active Sequence 10 descriptor profile;
4. require the profile hard limit to equal the current process hard limit;
5. calculate and apply a fresh runtime budget for the verifier's current FD
   state;
6. rebuild every other active authority field and compare the complete
   correction preflight; and
7. restore the caller's original limits in `finally`.

The historical snapshot may therefore retain `7 / 6 / 259`, while a later
verifier may operationally use `5 / 4 / 257`. Runtime planning does not become
part of canonical correction-preflight bytes.

Unknown profile keys, booleans masquerading as integers, negative values,
wrong reserve, wrong protocol additional, changed leaf/depth/ceiling,
hard-limit drift, malformed historical budget math, source drift, lease
drift, or any other preflight change still fails.

### Runtime capacity and restoration

The operational context must:

- sample the exact original `(soft, hard)` pair;
- run inside `_run_continuation_descriptor_command` after the workspace and
  source-root descriptors are open and before the selected transition begins;
- call the existing bounded planner using current descriptors;
- reject unavailable or above-ceiling capacity before authority publication;
- raise soft only when needed;
- verify the applied pair;
- run the descriptor-heavy operation;
- restore the original pair after success, contract error, collision, busy,
  unavailable, interruption, and unexpected `OSError`; and
- verify restoration before returning.

Tests retain zero, two, and at least eight unrelated regular-file/pipe
descriptors around the same immutable preflight. They also cover a lower
sufficient soft limit, insufficient hard limit, setrlimit failure, apply
mismatch, and restore failure. Tests must not close descriptors owned by the
test runner.

### Historical Sequence 9 import

Sequence 10 adds a historical importer distinct from active current-source
validation. It reopens:

- the exact Sequence 9 plan, ledger, and authorization;
- Tier prechange, rollback, owner, archive, and bundle manifest;
- the archive's four exact package members;
- the continuation lease and preflight;
- the preflight's exact Sequence 8 / Task 6 references; and
- the stored descriptor budget and internal schema/link relationships.

It must not compare Sequence 9's source projection to Sequence 10 live bytes;
the Tier archive is the authority for historical Sequence 9 source. The old
public `verify-continuation-preflight` continues to reject live source drift
after Sequence 10 edits. That rejection is expected and is not used as the
Sequence 10 import path.

## Correction preflight and root provenance

The correction preflight schema is
`quant-radar-ui-ux-formal-handoff-descriptor-budget-correction-preflight/v1`.
Its exact top-level keys are:

```text
schemaVersion
status
correctionId
continuationId
captureRecoveryId
authorizationRecord
replacementPlan
traceability
predecessor
sourceProjection
supplementalProjection
runtimeReceipt
makeContract
namespaceInventory
eligibleDestinations
descriptorProfile
lease
```

`predecessor` is a closed object with exactly
`replacementPlan,traceability,authorization,tierPrechange,tierRollback,
tierOwner,tierArchive,tierBundleManifest,lease,preflight,preflightValue`.
These fields contain exact Sequence 9 artifact references plus the imported
preflight value needed for chain validation; unknown or duplicate fields
fail.

The correction Tier freezes the final corrected `Makefile`, correction
authorization, coordinator, and coordinator test. Final package
cardinalities and membership digest are calculated from explicit closed path
sets after implementation and reviewed before authorization acceptance; no
count is guessed from Sequence 9 or an open glob.

The root remains
`quant-radar-ui-ux-formal-theme-handoff/v2`; no top-level root schema fork is
allowed. Because the root does not yet exist, its provenance fields may
correctly identify Sequence 10:

- `authorizationRecord`, `replacementPlan`, and `traceability` point to
  Sequence 10;
- `preflight` points to the correction preflight;
- the correction preflight imports the exact Sequence 9 preflight;
- Sequence 9 imports the Sequence 8 capture preflight and passed terminal;
- `recoveryId` remains `20260725T080000Z`; and
- Task 6, Task 9, migration, runtime receipt, and historical selector content
  remain derived from the immutable predecessors.

Candidate and every root consumer traverse the complete chain. Directly
substituting the Sequence 8 or Sequence 9 preflight for the correction
preflight fails.

## Public exit and destination propagation

Every descriptor-bound operation returns its committed artifact reference on
success. The public handler:

1. checks `exitCode` immediately;
2. returns the exact nonzero code with no further root/source read; or
3. on success, derives the public destination from the returned artifact and
   reopens that destination for the normal success envelope.

Specific corrections:

- `_publish_downstream_review` returns the published review artifact.
  `_handle_publish_review` checks its result before touching destination data
  and uses `result["review"]["path"]`; it does not call
  `_read_root_contract_production`.
- `_theme_init_transition` already returns the prechange artifact.
  `_handle_init_theme_batch` uses `result["prechange"]["path"]`; it does not
  perform a second root traversal.
- Remove `_read_root_contract_production` if no production caller remains.
- Static and behavioral tests reject any handler that performs a second
  descriptor command before propagating a nonzero result.

This correction does not change the documented public success envelope or
exit set `0/3/4/5/6/7/8/9/130`.

## Test integrity and production-shaped coverage

Sequence 9 tests proved parser/registry identity and result envelopes but did
not execute the formal comparator success path through the production
dispatcher. Sequence 10 closes that gap.

Allowed test seams:

- an owner-only temporary `WORKSPACE_ROOT` / `SOURCE_WORKSPACE_ROOT`;
- internally consistent test-owned historical artifacts and runtime roots;
- extra retained FDs used to vary the ambient baseline;
- deterministic failure injection at operating-system boundaries such as
  `setrlimit`, `flock`, file creation, or runner process results; and
- test-owned external review intake created only after the real packet.

The production-success and production-failure dispatcher tests must not patch
or replace:

```text
_production_public_handlers
_execute_public_command
_run_continuation_descriptor_command
_plan_preflight_descriptor_budget
_validate_descriptor_budget
_validate_continuation_preflight_complete
_reauthenticate_continuation_preflight
the Sequence 10 correction preflight validator/reauthenticator
_compare_control_migration_transition
_verify_root_continuation_chain
_publish_downstream_review
_theme_init_transition
_theme_batch_ready
_capture_transition
_public_success
```

They may not pass an injected `handlers` or `command_handlers` mapping.
Function-name, parser-only, mock-return, or success-envelope tests cannot
satisfy the production path gate.

The owned-fixture canary uses actual public parsing/dispatch and real
transition publishers. A canonical success fixture runs correction bootstrap
and preflight, comparator, 117-item control review, root candidate/publication
and fresh verification, theme batch seal/review/apply, real production-driver
theme-state capture/review/attestation, real production-driver posttheme
capture/review/finalization, and exact closure reopen. Separate fresh fixtures
exercise capture reconciliation and theme-batch forward/rollback/refusal
branches; capture and reconcile never run as two attempts against one
one-shot lineage.

Synthetic accepted intakes in these fixtures must be visibly tagged
`test-owned`, remain under the temporary root, and be destroyed with the
fixture. They prove transition mechanics only and grant no formal authority.

## Migration-geometry contract correction design

### Authenticated inputs and frozen oracle

The adapter remains inside `scripts/ui_ux_theme_handoff.py`, the Sequence 10
coordinator already authorized to consume the migration artifacts. Before
using private frozen parsing/comparison primitives it must:

1. reauthenticate the Sequence 10 correction preflight;
2. reopen all four fixed manifest bundles by their immutable manifest hashes;
3. authenticate the catalog derived from the immutable capture-stack record;
4. require `scripts/ui_ux_evidence.py` to have exact SHA-256
   `3ae2a02b519a70f4e8ef146c486f0ad4cd306718ad5429ec20dd8ccf951f009a`,
   size `363635`, regular-file ownership/mode/link safety, and the expected
   module origin;
5. parse both profiles with the frozen authenticated-bundle functions;
6. require all four manifest digests and the catalog digest to be identical;
   and
7. validate the exact frozen full-page/focused capture profiles and catalog
   case coverage.

Failure of any step is a contract failure and publishes no comparator report.
The adapter may rely on frozen private primitives only after the exact source
record check; a future evidence-module change requires a new reviewed
authority, not best-effort compatibility.

### Closed geometry-transition projection

For every catalog-affected capture, sort by section, capture ID, and node ID.
Include only nodes whose bounds or membership differ, using exactly:

```json
{
  "section": "fullPageCases|focusedCases",
  "captureId": "case/viewport",
  "nodes": [
    {
      "id": "stable DOM identity",
      "before": {"x": 0, "y": 0, "width": 0, "height": 0},
      "after": {"x": 0, "y": 0, "width": 0, "height": 0}
    }
  ]
}
```

`before` is `null` only for a newly added migrated-control descendant;
`after` is `null` only for a removed native-control descendant. No root,
boundary, or ordinary stable node may be membership-only. Canonical JSON uses
sorted keys, no insignificant whitespace, UTF-8, and no final newline.

The exact projection contract is:

| Field | Exact value |
| --- | ---: |
| Affected captures | `57` |
| Catalog roots | `71` |
| Changed common nodes | `3338` |
| Removed control descendants | `530` |
| Added control descendants | `324` |
| Changed or membership rows | `4192` |
| Canonical bytes | `552863` |
| SHA-256 | `500ddca716dc4eace0cbcdeade8ad18a0a0166988db82edd9c64657f8f99b996` |

The other `60` captures must remain byte-equivalent at parsed-capture level.
Any count, order, ID, membership class, bound, byte size, or digest mismatch
fails. This is a closed authorization of the already authenticated migration,
not a general tolerance.

### Actual-geometry safety audit

Before semantic canonicalization, both before and after captures must satisfy:

- every catalog root has the exact catalog `flowScope` and `boundaryId`, and
  its boundary is an ancestor;
- every visible root and boundary fits horizontally inside its viewport;
- every root fits inside its declared boundary;
- every visible control descendant fits inside its owning root and viewport;
- visible roots do not overlap one another;
- descendants owned by different roots do not overlap;
- each ordinary node's declared catalog boundary is its nearest actual
  boundary ancestor when applicable; and
- every focused control layout reports exact
  `documentHorizontalOverflow:false`, `rootHorizontalOverflow:false`,
  `rootClipping:false`, `targetClipping:false`, and
  `targetOverlap:false`, with each full-page root mapped to the same selector
  and viewport's authenticated focused evidence.

Height shrink, width growth, responsive wrapping, and root/downstream
translation are permitted only because their complete exact profile is
authenticated above. Negative dimensions, clipping, viewport escape,
cross-root overlap, wrong ancestry, or a coherent geometry mutation with a
different profile digest remains rejected.

Generic ordinary-node/control-root rectangle overlap is not a valid safety
oracle in these captures: sidebar links, grid inputs, and nested Streamlit
containers intentionally share rectangle area despite separate interaction
layers. The adapter therefore does not reproduce the frozen comparator's
ordinary-sibling rectangle rule on actual layout. Target clipping/overlap and
horizontal overflow come from the purpose-built authenticated focused
`controlEvidence`; the zero-box semantic plane retains the frozen rule only
as a structural semantic oracle.

The captured DOM uses integer boxes while focused browser evidence retains
subpixel boxes. Exact immutable captures contain `7` historical descendants
with a one-pixel right-edge overhang and `30` migrated descendants with a
one- or two-pixel bottom-edge overhang. Descendant-to-root and
descendant-to-stable-ancestor containment therefore uses an exact inclusive
`2` CSS-pixel quantization envelope; `3` pixels fails. Root-to-boundary,
boundary-to-ancestor, viewport, ownership, and overlap checks receive no
added tolerance. The complete profile digest still makes even a one-pixel
artifact mutation fail before this audit.

### In-memory semantic canonicalization

After the actual audit and exact profile check, the adapter deep-copies both
the `before` and `after` capture. It never mutates authenticated bundle
objects or on-disk bytes. Every copied node receives the same zero-size
canonical box at `(0,0)`. This creates a semantic-only plane that satisfies
the frozen comparator's internal geometry assumptions without pretending
those assumptions describe the actual responsive layout.

Before comparison, only the separately authenticated `21` non-control
volatility fields described below are restored on the copied `after` capture
to their authenticated `before` values. The unchanged frozen
`_compare_capture_migration` then compares the two canonical copies. It
remains responsible for capture identity,
provider/mutator counters, stable state outside allowed subtrees, catalog
identity, stable DOM order, stable semantics, unaffected captures, and
canonical containment. Actual geometry has already been independently
authenticated and audited; canonical boxes are never reported as layout
evidence.

### Closed non-control volatility projection

The semantic-only pass also exposes two authenticated capture-time
volatilities that are neither application-semantic changes nor control
descendants:

- `14` `name`/`text` fields contain the same
  `/app/fixture-root/reports/analytics_checks/latest.json` suffix under
  different owned temporary roots; and
- `7` Analytics control-root aggregate names change from
  `資料表 candidate_rankings iv_history` to
  `資料表 candidate_rankings` because the migrated selectbox DOM renders only
  its selected option while focused `controlEvidence` still requires the
  exact two-option set, selected label, and accessible name.

Sort all such non-control stable-field transitions by section, capture ID,
node ID, and field. Their canonical projection has exactly `21` rows, `8498`
bytes, and SHA-256
`9bad8fb8a777b61ad4ec9669abcd6b810b4bddeaa12fc3a5088baf8830cb5882`.
Only those exact copied fields are set to their authenticated `before` value
for the frozen semantic pass. The adapter separately requires the four
focused Analytics controls to preserve
`accessibleName:"資料表"`,
`optionLabels:["candidate_rankings","iv_history"]`, and
`selectedLabel:"candidate_rankings"` before and after. Any other root,
boundary, ordinary-node, runtime-suffix, option, selection, or stable-field
transition fails.

The final registered report retains `status:"passed"`,
`kind:"control-migration"`, both covered profiles,
`comparedCaptures:117`, and the exact capture-stack digest. It adds a closed
`migrationGeometryContract` summary containing the schema version, exact
geometry and volatility profiles, two-pixel descendant quantization envelope,
actual-audit status, and frozen evidence-module reference.

## Requirements

### `REQ-010` — resume the passed continuation without recapture

The parent flow must resume from the exact Sequence 9 preflight through
migration review and root publication without changing historical evidence or
launching Task 9 capture.

### `CFR-034` — immutable Sequence 9 failed prefix

Every Sequence 9 authority, Tier member, archive member, preflight byte,
filesystem safety property, and absent downstream destination remains exact.

### `CFR-035` — context-invariant descriptor semantics

Exact-hash-protected legacy creation provenance is validated without
ambient-baseline equality; the active correction uses a deterministic
context-free profile, and fresh bounded runtime capacity is independently
applied/restored for each process.

### `CFR-036` — separate triple-identity correction authority

Capture recovery, continuation, and correction IDs are fixed and distinct.
The correction Tier/preflight freezes current source and imports both earlier
authorities without granting capture.

### `CFR-037` — real production-dispatch proof

Success, failure, and reconciliation coverage enters through the real public
dispatcher and real transition functions. Prohibited monkeypatches cannot
produce a passing gate.

### `CFR-038` — exact exit and destination propagation

Nonzero exits return before any second authority read. Successful handlers
derive destinations from their committed transition artifacts.

### `CFR-039` — root and downstream provenance closure

The unchanged root v2 schema binds Sequence 10 and traverses Sequence 9/8;
all downstream families consume that exact chain.

### `CFR-040` — compatibility and fail-closed preservation

Capture, fail-soft API/Streamlit/artifact loading, sandbox, filesystem,
schema, Make, process, path, and public result contracts remain unchanged.

### `CFR-041` — scope, confidence gate, and traceability

Only planned files and new owned namespaces change. Full bidirectional
traceability, actual-diff review, production-shaped tests, and the formal
external-review pause are mandatory.

### `CFR-042` — frozen migration oracle preservation

The exact evidence module and capture-stack bytes remain unchanged. The
coordinator authenticates their exact source and reuses the frozen parser and
semantic comparator; it does not weaken or replace them.

### `CFR-043` — closed responsive-geometry authority

Only the exact `57`-capture / `71`-root geometry-transition projection with
SHA-256 `500ddca7...996` is accepted. Actual before/after geometry must pass
containment, viewport, overlap, ownership, and ancestry audits.

### `CFR-044` — semantic preservation through canonicalization

Geometry canonicalization is in-memory, zero-box, and defensive-copy based.
Only the separately authenticated `CFR-045` fields may also be restored on
the copied semantic plane. The frozen comparator must still reject every
other unauthorized identity, counter, state, DOM-order, catalog,
unaffected-capture, and stable-semantic mutation.

### `CFR-045` — closed capture-volatility authority

Only the exact `21` non-control stable-field transitions with canonical size
`8498` and SHA-256 `9bad8fb8...882` may be canonicalized. Runtime paths must
retain their exact fixture suffix, and the seven Analytics aggregate-name
changes require exact two-option focused control evidence.

## Acceptance criteria

### `AC-SEQ10-001` — predecessor immutability (CRITICAL)

Given the exact Sequence 9 authority and failed no-output observation, when
Sequence 10 imports it, then every byte/hash/size/mode/owner/link/archive
relationship and absence reopens unchanged, and no Task 9 process launches.

### `AC-SEQ10-002` — descriptor context independence (CRITICAL)

Given one immutable internally valid preflight, when it is verified with
different unrelated FD baselines and sufficient current capacity, then every
verification succeeds without changing stored bytes, and each process's
original limits are restored. A legacy whole-file hash mismatch, active
profile mutation, invalid math, hard drift, insufficient capacity, or restore
failure fails closed.

### `AC-SEQ10-003` — correction authority (CRITICAL)

Given accepted Sequence 10 plan/ledger/authorization and absent Tier paths,
when correction bootstrap/preflight/verify run with all three IDs, then one
canonical correction chain freezes current source and exact Sequence 9
history. Any ID, marker, package, predecessor, lease, source, descriptor, or
future-destination mutation publishes nothing.

### `AC-SEQ10-004` — real comparator success (CRITICAL)

Given the correction preflight and exact four manifests, when the real public
dispatcher runs the comparator from its normal descriptor context, then it
publishes one canonical report with `comparedCaptures:117`. Reopen,
collision, and stale-authority behavior remains fail closed.

### `AC-SEQ10-005` — exit propagation (CRITICAL)

Given downstream review/init success and each documented nonzero result, when
their real handlers run, then nonzero exits are returned before any second
root read, while success uses the artifact path committed by the same
descriptor operation.

### `AC-SEQ10-006` — complete production-shaped lifecycle (CRITICAL)

Given owned internally consistent fixtures, when all correction-authorized
command families run through actual parsing, production dispatch, real
transitions, review boundaries, capture drivers, and reconciliation branches,
then each reaches its contracted state and exact destination with no
prohibited patch or formal workspace write.

### `AC-SEQ10-007` — root provenance (HIGH)

Given passed comparator and accepted test/formal review at the appropriate
boundary, when root candidate/publication/consumer verification runs, then
root v2 binds Sequence 10 and traverses exact Sequence 9/8. Any direct
preflight substitution fails.

### `AC-SEQ10-008` — compatibility (HIGH)

Given the Sequence 10 diff, when complete relevant regressions run, then
capture-stack, fail-soft API/UI/artifact behavior, source projections,
schemas, Make exits, and historical selectors remain exact.

### `AC-SEQ10-009` — scope and closure (HIGH)

Given the pre-change dirty snapshot and reviewed plan, when implementation and
formal gates are audited, then only explained planned changes exist, ledger
coverage is 10000 basis points with no gaps/orphans, all blockers are closed,
and missing external review remains an explicit pause.

### `AC-SEQ10-010` — frozen oracle authentication (CRITICAL)

Given the exact four manifests, catalog, and evidence module, when the
coordinator enters migration comparison, then it authenticates every fixed
hash/origin/profile before using frozen private primitives. Any source,
manifest, catalog, digest, profile, ownership, mode, link, or origin mutation
publishes no report.

### `AC-SEQ10-011` — exact responsive geometry (CRITICAL)

Given the authenticated native-to-migrated captures, when the geometry
adapter projects and audits them, then it observes exactly `57` affected
captures, `71` roots, `3338` changed common nodes, `530` removed and `324`
added control descendants, `4192` changed/membership rows, `552863` canonical
bytes, and SHA-256 `500ddca7...996`. Every actual root, boundary, descendant,
ordinary node, and viewport relationship passes the closed safety audit; any
mutation fails before canonicalization.

### `AC-SEQ10-012` — frozen semantic comparison after geometry correction (CRITICAL)

Given a passing exact geometry audit, when the adapter creates its zero-box
defensive copies, restores only the exact `AC-SEQ10-013` volatility fields,
and invokes the unchanged frozen comparator, then all `117` captures pass
and the registered report records the closed geometry contract.
Any non-bounds mutation outside the separately exact `AC-SEQ10-013`
volatility projection, ordinary membership mutation, non-control
membership-only row, after-only non-descendant, or mutation of an unaffected
capture remains rejected.

### `AC-SEQ10-013` — exact capture volatility (CRITICAL)

Given exact authenticated Analytics captures, when non-control stable-field
differences are projected, then exactly `21` rows / `8498` bytes /
`9bad8fb8...882` are observed. The `14` runtime-path fields retain the exact
fixture suffix, the `7` root names match the fixed transition, and all four
focused viewports preserve exact accessible name, two-option order, and
selection before/after. Any additional or changed stable-field transition
fails before the frozen semantic pass.

## BDD scenario specification

Each CRITICAL criterion has at least five adversarial scenarios and each HIGH
criterion has at least three.

| Scenario | Given / When / Then |
| --- | --- |
| `SC-SEQ10-001A` | Given exact Sequence 9 records / import / then all records and links reopen exact. |
| `SC-SEQ10-001B` | Given one changed preflight byte / import / then contract failure and zero writes. |
| `SC-SEQ10-001C` | Given changed Tier archive member / import / then reject before correction Tier creation. |
| `SC-SEQ10-001D` | Given passed Sequence 8 terminal / call capture or reconcile / then reject before runner launch. |
| `SC-SEQ10-001E` | Given absent forward paths / failed import / then all remain absent. |
| `SC-SEQ10-002A` | Given baseline 5/max 4 / verify stored 7/max 6 budget / then pass and preserve bytes. |
| `SC-SEQ10-002B` | Given two or eight extra retained FDs / verify / then pass with restored limits. |
| `SC-SEQ10-002C` | Given internally broken budget equation / verify / then contract failure. |
| `SC-SEQ10-002D` | Given insufficient hard limit or apply mismatch / verify / then unavailable/contract with no publication. |
| `SC-SEQ10-002E` | Given operation exception / unwind / then original soft/hard pair is restored or restore failure is explicit. |
| `SC-SEQ10-003A` | Given absent correction Tier / bootstrap then preflight / then publish one reopened canonical chain. |
| `SC-SEQ10-003B` | Given substituted capture, continuation, or correction ID / bootstrap / then publish nothing. |
| `SC-SEQ10-003C` | Given malformed/duplicate/future marker / parse / then reject. |
| `SC-SEQ10-003D` | Given Sequence 10 source drift after freeze / verify / then reject without downstream writes. |
| `SC-SEQ10-003E` | Given concurrent bootstrap / run twice / then one owner wins and no overwrite occurs. |
| `SC-SEQ10-004A` | Given exact authorities / real public compare / then publish `comparedCaptures:117`. |
| `SC-SEQ10-004B` | Given normal dispatcher with fewer baseline FDs / compare / then descriptor context does not alter evidence equality. |
| `SC-SEQ10-004C` | Given changed Task 6 or Sequence 8 manifest / compare / then reject before output. |
| `SC-SEQ10-004D` | Given existing report / compare / then preserve original inode and bytes with collision exit. |
| `SC-SEQ10-004E` | Given caller artifact path or extra flag / parse / then grammar failure and no output. |
| `SC-SEQ10-005A` | Given busy downstream review / dispatch / then return busy without second root read. |
| `SC-SEQ10-005B` | Given collision/unavailable review / dispatch / then preserve exact exit and write nothing new. |
| `SC-SEQ10-005C` | Given successful review / dispatch / then public path equals returned review artifact path. |
| `SC-SEQ10-005D` | Given failed theme init / dispatch / then no destination calculation or success reopen occurs. |
| `SC-SEQ10-005E` | Given successful theme init / dispatch / then public path equals returned prechange artifact path. |
| `SC-SEQ10-006A` | Given success fixture / run correction through root / then every real transition commits/reopens once. |
| `SC-SEQ10-006B` | Given theme success fixture / run batch/state/posttheme / then exact attestation and closure reopen. |
| `SC-SEQ10-006C` | Given interrupted batch prefix / reconcile / then only documented forward/rollback/refusal branch occurs. |
| `SC-SEQ10-006D` | Given interrupted capture prefix / reconcile / then no second one-shot runner launch occurs. |
| `SC-SEQ10-006E` | Given a prohibited transition/validator/dispatcher patch / test self-check / then the gate rejects the fixture. |
| `SC-SEQ10-007A` | Given accepted inputs / publish root / then v2 root traverses correction → continuation → capture. |
| `SC-SEQ10-007B` | Given root with direct Sequence 9 preflight / verify / then reject substitution. |
| `SC-SEQ10-007C` | Given current source drift / downstream consume / then reject before mutation. |
| `SC-SEQ10-008A` | Given correction diff / run fail-soft suites / then missing/corrupt/partial artifacts remain non-crashing. |
| `SC-SEQ10-008B` | Given capture-stack/package hashes / compare / then historical members remain exact. |
| `SC-SEQ10-008C` | Given Make targets and public results / fault / then exact nonzero exits propagate. |
| `SC-SEQ10-009A` | Given dirty-worktree fingerprint / compare actual diff / then unrelated paths are unchanged. |
| `SC-SEQ10-009B` | Given plan and ledger / validate edges / then reciprocal coverage is 10000 bps with no gaps/orphans. |
| `SC-SEQ10-009C` | Given formal packet but no external intake / continue / then stop and report the external gate. |
| `SC-SEQ10-010A` | Given exact evidence module / compare / then exact hash, size, origin, ownership, mode, and link checks pass before private use. |
| `SC-SEQ10-010B` | Given one evidence-module byte changed / compare / then reject before manifest parsing or output. |
| `SC-SEQ10-010C` | Given one manifest/catalog hash or capture-stack digest changed / compare / then reject before geometry projection. |
| `SC-SEQ10-010D` | Given a substituted module origin or private primitive / compare / then reject before report registration. |
| `SC-SEQ10-010E` | Given a missing or extra frozen capture profile row / compare / then reject with zero output. |
| `SC-SEQ10-011A` | Given exact authenticated captures / project / then exact `57/71/3338/530/324/4192/552863/500ddca7...996` profile passes. |
| `SC-SEQ10-011B` | Given one root, boundary, ordinary, or descendant bound changed / project / then digest mismatch rejects. |
| `SC-SEQ10-011C` | Given clipping, viewport escape, or cross-root overlap / audit / then reject even if other fields are valid. |
| `SC-SEQ10-011D` | Given wrong root owner, flow scope, boundary ancestry, or ordinary boundary declaration / audit / then reject. |
| `SC-SEQ10-011E` | Given a membership-only root/boundary/ordinary row / classify / then reject before canonicalization. |
| `SC-SEQ10-012A` | Given passing actual geometry / canonicalize / then only a defensive copy's `bounds` change and authenticated inputs remain equal. |
| `SC-SEQ10-012B` | Given after-only control descendants / canonicalize / then each maps to one catalog owner and its canonical root bounds. |
| `SC-SEQ10-012C` | Given stable name/text/state/counter/identity mutation / frozen compare / then reject after geometry passes. |
| `SC-SEQ10-012D` | Given stable DOM-order or unaffected-capture mutation / frozen compare / then reject. |
| `SC-SEQ10-012E` | Given exact migration / real public compare / then publish one registered report with `117` captures and exact geometry summary. |
| `SC-SEQ10-013A` | Given exact captures / project non-control stable differences / then exact `21/8498/9bad8fb8...882` passes. |
| `SC-SEQ10-013B` | Given runtime path with wrong suffix, traversal, or unrelated leaf / project / then reject. |
| `SC-SEQ10-013C` | Given one additional root/boundary/ordinary stable-field change / project / then reject. |
| `SC-SEQ10-013D` | Given changed Analytics option order, selected label, or accessible name / validate focused evidence / then reject. |
| `SC-SEQ10-013E` | Given exact volatility / canonicalize copies / then authenticated captures remain byte-equivalent in memory and on disk. |

## Affected files

### Planned implementation changes

- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `Makefile`
- new Sequence 10 authorization candidate under `docs/ui-ux/`

### Plan, traceability, and journals

- this plan;
- its sibling traceability ledger;
- `.agents/scribe.md`;
- `.agents/builder.md`; and
- `.agents/PROJECT.md`.

### Explicitly unchanged

- every Sequence 8 and Sequence 9 formal record listed above;
- `scripts/ui_ux_evidence.py` and every other capture-stack member;
- FastAPI, Streamlit, artifact-loader, design/theme, and application source;
- parent UI/UX specifications and visual acceptance criteria;
- `.streamlit/config.toml`, `app.py`, `ui/_design.py`, `requirements.txt`, and
  classification; and
- unrelated current worktree changes.

## Implementation checklist

- [ ] `IMPL-057`: Add fixed Sequence 10 IDs, paths, correction authorization
  parser, closed command sets, schemas, exact Sequence 9 refs, and historical
  importer without editing Sequence 9.
- [ ] `IMPL-058`: Refactor descriptor construction/validation into
  exact-hash-protected legacy provenance, deterministic active profile, and
  fresh runtime capacity; add bounded apply/restore and remove ambient
  replanning from builders.
- [ ] `IMPL-059`: Add descriptor-bound correction bootstrap, Tier,
  preflight, verification, lock/lease, archive, source projections,
  namespace inventory, and triple-ID validation.
- [ ] `IMPL-060`: Route comparator, control review, root candidate,
  publication, and consumers through correction provenance while preserving
  root v2 and exact Sequence 8/9 content.
- [ ] `IMPL-061`: Fix downstream review and theme-init exit/destination
  propagation; remove the redundant production root-reader path if unused.
- [ ] `IMPL-062`: Add red-first FD-baseline, budget mutation, limit
  restoration, historical import, dispatcher success/fault, transition,
  review, root, capture-driver, and reconciliation tests with anti-mock
  self-checks.
- [ ] `IMPL-063`: Add correction Make variables/targets/argument order and
  update the coordinator's exact Make contract without direct runner calls.
- [ ] `IMPL-064`: Run focused, production-shaped, compatibility, fail-soft,
  scope, static, and actual-diff reviews; fix blocking findings before any
  formal Sequence 10 record.
- [ ] `IMPL-065`: After separate acceptance of the final authorization
  document, publish/reopen correction Tier/preflight, run the real comparator,
  publish/reopen the 117-item packet, and stop for independent intake.
- [ ] `IMPL-066`: Add exact frozen-evidence authentication, authenticated
  manifest/catalog parsing, and the closed `500ddca7...996`
  geometry-transition projection in the coordinator without editing the
  evidence module.
- [ ] `IMPL-067`: Add actual before/after geometry audits and zero-box
  defensive-copy canonicalization; invoke the unchanged frozen semantic
  comparator after the exact `IMPL-069` volatility restoration and register
  the exact geometry-contract report.
- [ ] `IMPL-068`: Add real-evidence census, geometry mutation,
  semantic-mutation, immutability, and production-dispatch canary tests; bind
  the reviewed plan/ledger and regenerated authorization candidate only after
  these checks pass.
- [ ] `IMPL-069`: Add the exact `21/8498/9bad8fb8...882` non-control
  volatility projection, fixture-suffix and focused Analytics option
  validation, semantic zero-box copies, and mutation tests.

## Test specification

| Test | Verifies |
| --- | --- |
| `TEST-080` | Exact Sequence 9 plan/ledger/authorization/Tier/archive/preflight/lease and forward absences. |
| `TEST-081` | Stored budget schema/equations/tamper rejection and zero/two/eight-extra-FD context independence. |
| `TEST-082` | Runtime budget plan/apply/verify/restore under success, exception, insufficient hard, set failure, and restore failure. |
| `TEST-083` | Correction marker/parser, triple IDs, Tier/preflight schema, collision, concurrency, source drift, and historical traversal. |
| `TEST-084` | Real public comparator success at 117 captures, exact inputs, path injection refusal, collision, and stale authority. |
| `TEST-085` | Immediate nonzero exit propagation and same-operation review/init destination use; no redundant root read. |
| `TEST-086` | Root v2 candidate/publication/fresh consumer traversal through Sequence 10 → 9 → 8 and substitution rejection. |
| `TEST-087` | Actual production dispatcher success chain through migration, review, root, theme batch, state, posttheme, and closure in owned fixtures. |
| `TEST-088` | Actual dispatcher busy/collision/unavailable/interrupted/uncertain/manual and batch/capture reconciliation branches. |
| `TEST-089` | Capture-stack, fail-soft API/Streamlit/artifact-loader, schema, Make, Python, dependency, and historical compatibility. |
| `TEST-090` | Plan/diff scope, immutable predecessor hashes, BDD inventory, reciprocal ledger, formal namespace, and external pause. |
| `TEST-091` | Exact frozen evidence source/origin and private-primitive substitution rejection. |
| `TEST-092` | Four real manifest/catalog authorities, capture profiles/common digest, exact geometry census/profile `57/71/3338/530/324/4192/552863/500ddca7...996`, exact semantic-volatility summary, and registered `117`-capture report. |
| `TEST-093` | Actual-geometry 2-pixel acceptance, 3-pixel rejection, viewport/overlap/ancestry attacks, and defensive-copy immutability. |
| `TEST-094` | All `57` affected semantic-plane pairs pass the unchanged frozen comparator; a non-authorized ordinary-node semantic mutation is rejected. |
| `TEST-095` | Exact 21-row runtime-path/root-name volatility and authenticated focused-layout evidence; volatility or clipping-flag mutation fails closed. |

## Implementation sequence and gates

### Phase 0 — reopen and snapshot

- Reopen every exact Sequence 9 record and archive member in this plan.
- Reopen Sequence 8 terminal, postcontrol, pretheme, canary, Task 6 manifests,
  and empty runtime root through the Sequence 9 chain.
- Capture a read-only fingerprint of dirty paths and planned source preimages.
- Reconfirm all six forward destinations and all Sequence 10 paths absent.
- Reproduce the stored/current descriptor difference read-only; do not rerun
  capture or create the comparator output.

**Gate:** any predecessor drift, unexpected forward leaf, unsafe ownership,
active lifecycle-owned process, or unexplained dirty-path change blocks
implementation.

### Phase 1 — red tests

- Add `TEST-080..090` as red-first tests.
- Prove the existing code fails the normal-dispatch comparator because it
  replans stored descriptor fields.
- Prove existing Sequence 9 tests are false-green for the production success
  path by requiring actual transition artifacts, not only handler identity.
- Add anti-mock assertions before implementing correction behavior.

**Gate:** red failures must identify the descriptor mismatch, early second
root read, missing correction authority, or absent production-path proof; a
fixture/setup failure is not an acceptable red.

### Phase 2 — descriptor and authority implementation

- Complete `IMPL-057..061`.
- Create the Sequence 10 authorization candidate during implementation, bind
  its final marker body in code, and keep it unaccepted/unpublished.
- Preserve the old Sequence 9 preflight validator's current-source semantics
  for its old public verify command; use a distinct exact historical importer.
- Keep every formal Sequence 10 path absent while source is changing.

**Gate:** all focused budget, mutation, restoration, import, root, exit, and
dispatcher tests pass; exact Sequence 9 hashes still match Phase 0.

### Phase 2B — migration-geometry correction

- Add `TEST-091..095` against the exact real authenticated capture artifacts.
- Require the frozen evidence source hash before any private primitive call.
- Implement the closed projection/census and actual-geometry safety audit.
- Implement in-memory zero-box canonicalization, restore only the exact
  separately authenticated volatility fields on the copy, and pass the
  result to the unchanged frozen semantic comparator.
- Implement exact non-control volatility validation/canonicalization and the
  semantic zero-box plane; reject every transition outside its exact profile.
- Prove authenticated inputs and on-disk evidence are unchanged before/after.
- Re-run `TEST-084` through the real parser, production registry, public
  dispatcher, descriptor wrapper, transition, and publisher.

**Gate:** exact geometry counts/bytes/digest match; all mutation attacks fail;
the frozen module/capture stack remain exact; the real canary publishes and
reopens one test-owned `comparedCaptures:117` report with the exact geometry
summary, then removes the entire test namespace.

### Phase 3 — Make, complete tests, and production-shaped canary

- Run the pre-Sequence8 awake-gate test in a test-owned temporary source root
  because its explicit contract requires all future Sequence 8 paths to be
  absent. Deny that test-only process visibility of the retained formal
  `/private/tmp/qr-ux1b-s8` runtime root with the root-owned macOS sandbox
  tool. Keep the frozen awake-gate source unchanged; run every later recovery
  test against the real workspace where formal Sequence 8 evidence is
  required and authenticated.
- Keep legacy Chromium coverage for UX-0 and the four unmigrated UX-1A cases.
  Route the intentionally migrated institution selector to the exact
  accessible-selection suite rather than asking the legacy button-name
  interaction to operate a radio/segmented control.
- Complete `IMPL-062..064` and `IMPL-066..069`.
- Exercise the real production dispatcher with no injected handler registry.
- Run the canonical success fixture and separate reconciliation/fault
  fixtures; retain no test process, port, runtime root, intake, or temporary
  workspace afterward.
- Run selected full recovery, fail-soft, UI, static, dependency, and Make
  suites.
- Compare actual diff to this plan and Phase 0 fingerprints.
- Review for runtime errors, data loss, source/evidence mutation, missing
  tests, false-green seams, scope drift, and maintainability.

**Gate:** every relevant check passes, all test-owned roots are removed, no
formal Sequence 10 path exists, and no blocking review finding remains. If
the production-shaped canary cannot run on the host, formal bootstrap is
blocked rather than waived.

### Phase 4 — freeze correction authority

- Report the final authorization document's exact whole-document SHA-256,
  size, and mode.
- Obtain explicit maintainer acceptance of those exact bytes.
- Reopen the accepted document without editing.
- Run correction bootstrap once, reopen the complete Tier, and verify its
  exact closed package.
- Run correction preflight once, then verify it from a fresh process with the
  normal public dispatcher and a different incidental FD context.
- Reopen all Sequence 9 records again and prove them unchanged.

**Gate:** accepted correction preflight freezes final code and exact history.
Any source edit after this point requires another reviewed correction; do not
regenerate or overwrite the preflight.

### Phase 5 — definitive formal comparator

- Run `compare-control-migration` through Make with all three fixed IDs.
- Reopen the report and require `comparedCaptures:117`.
- Run control-migration packet preparation.
- Reopen the exact 117-item packet.
- Stop without creating or editing the formal review intake.

**Gate:** the report and packet exist exactly once. Missing independent intake
is the expected next pause.

### Phase 6 — root only after external acceptance

- Reopen an independently authored accepted intake.
- Publish and reopen the exact manual review.
- Prepare/verify/publish the root v2 candidate.
- Run a fresh pristine root verification.
- Prove no real theme source changed.

**Gate:** root v2 traverses Sequence 10 → 9 → 8 and remains pristine before
the parent theme plan resumes.

### Phase 7 — parent lifecycle

- Select new theme batch/run IDs only after root publication.
- Resume the parent UI/UX theme plan using the now-tested handlers.
- Keep each real visual review as an independent external pause.

**Gate:** Sequence 10 closes coordinator infrastructure only; it does not
approve UI design or visual evidence.

## Verification commands

Implementation must run at least:

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_ui_ux1a_safety.py
.venv/bin/python -B scripts/test_ui_ux_components.py
.venv/bin/python -B scripts/test_ui_ux_contract.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
make ui-ux1b-legacy
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Changed Python must pass `ast.parse(..., feature_version=(3, 10))`. The
implementation handoff must name any unavailable command; an unavailable
production-shaped canary blocks formal execution.

The future formal correction command shape is:

```bash
make ui-ux1b-theme-handoff-descriptor-budget-correction-bootstrap \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z

make ui-ux1b-theme-handoff-descriptor-budget-correction-preflight \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z

.venv/bin/python -B scripts/ui_ux_theme_handoff.py \
  verify-descriptor-budget-correction-preflight \
  --capture-recovery-id 20260725T080000Z \
  --continuation-id 20260726T210000Z \
  --correction-id 20260727T030000Z --json

make ui-ux1b-recovery-verify-migration \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z
```

There is no Sequence 10 Task 9 capture command.

## Failure and pause policy

- Any Sequence 8/9 mismatch blocks all Sequence 10 work.
- Sequence 9's existing preflight and Tier are never reopened for write.
- A Sequence 10 bootstrap/preflight collision is retained and never deleted
  or overwritten.
- A descriptor hard-limit drift or inability to restore exact limits is a
  contract/availability failure, never permission to continue.
- Runtime budget values are not serialized back into an existing preflight.
- Every nonzero transition result is returned before another authority read.
- Comparator, packet, review, candidate, and root publishers remain
  create-once.
- Test-owned intake never crosses into the formal workspace.
- Missing formal review pauses execution; rejected review is not edited to
  accepted.
- Unknown, partial, wrong-owner, wrong-mode, hardlinked, symlink, stale, or
  changed evidence grants no cleanup, retry, or forward authority.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Fix merely pads FD count | Prohibit dummy descriptors; separate stored provenance from fresh runtime capacity. |
| Removing ambient equality accepts malformed budgets | Retain exact closed keys, integer typing, equations, bounds, hard-limit and full-authority comparison. |
| Sequence 9 is silently rewritten | Import exact bytes/Tier archive under a new correction authority; old public verification remains historical/current-source strict. |
| Runtime soft limit leaks to caller | Apply in a verified context manager and test success plus every exception/restore branch. |
| Unit mocks miss another production-only failure | Require real public dispatcher and real transition artifacts; prohibit validator/dispatcher/transition patches. |
| Failure exit is masked by second root read | Check result immediately and derive destination from the committed artifact returned by the same operation. |
| Test approval is mistaken for human approval | Confine tagged test-owned intake to temporary roots; formal packet remains a mandatory stop. |
| New correction is called “final” prematurely | Treat complete canary/formal comparator as confidence evidence, not certainty; report any new blocker honestly. |
| Frozen comparator rejects intended responsive geometry | Keep it as the semantic oracle, authenticate a closed exact geometry profile, audit actual geometry separately, zero copied bounds, and restore only the separately authenticated 21 volatility fields in memory. |
| Geometry adapter becomes an allow-all bypass | Require exact `500ddca7...996` profile/counts, exact frozen-module source, mutation tests, and unchanged non-bounds comparison. |
| Canonicalization hides semantic drift | Change copied `bounds` plus only the separately exact 21 volatility fields; let the frozen comparator inspect all other identities, counters, stable state, DOM order, catalog semantics, and unaffected captures. |
| Integer boxes falsely report descendant clipping | Permit only the observed 2 px descendant edge envelope after exact profile authentication; reject 3 px and keep root/boundary/viewport checks exact. |
| Runtime paths or aggregate root names look semantic | Bind the only 21 transitions by exact digest, suffix grammar, and focused two-option evidence; reject every extra stable-field change. |
| Private frozen primitive changes silently | Exact-hash the evidence module before private use; any byte or origin change requires a new reviewed authority. |
| Pre-Sequence8 awake test runs after formal evidence exists | Run its unchanged source in a test-owned temporary source root and deny only test-process visibility of retained `/private/tmp/qr-ux1b-s8`; keep later recovery tests on the real authenticated workspace. |
| Legacy institution interaction expects the removed button role | Retain UX-0 and unmigrated UX-1A Chromium captures, and run the exact 27-test accessible-selection suite for the intentionally migrated control in the same legacy target. |
| API or Streamlit becomes more brittle | No API/UI source in scope; run explicit fail-soft regressions. |
| Dirty worktree is damaged | Fingerprint, edit only planned files, compare diff, never reset/clean. |

## Rollback

- Before formal correction Tier publication, revert only planned Sequence 10
  implementation files and new Sequence 10 documents; preserve unrelated
  dirty state and every historical record.
- After Tier publication, the correction Tier/lease/preflight are retained
  evidence. No destructive Git or namespace deletion is authorized.
- Before root publication, no real theme source changes, so rollback is
  refusing forward work and preserving exact evidence.
- After root publication, parent theme-batch rollback rules apply; Sequence
  8/9/10 authorities and root remain immutable.

## Blocking-issue review

### Review iteration 1 — ambient FD equality is not evidence integrity

- **Finding:** Recomputing creation-time baseline fields makes validation
  depend on whether lock/lease descriptors happen to be open.
- **Resolution:** Pass the stored budget explicitly through reconstruction and
  plan fresh runtime capacity separately.
- **Status:** Closed.

### Review iteration 2 — opening dummy FDs would repeat the failure

- **Finding:** Acquiring the old locks or padding FDs would make the current
  comparator pass but fail under another launcher/context.
- **Resolution:** Explicitly prohibit descriptor padding and test several
  ambient baselines.
- **Status:** Closed.

### Review iteration 3 — Sequence 9 cannot authorize changed code

- **Finding:** Editing its frozen coordinator and continuing from its old
  preflight would break provenance.
- **Resolution:** Add a distinct triple-ID Sequence 10 Tier/preflight that
  imports Sequence 9 historically and freezes current source.
- **Status:** Closed.

### Review iteration 4 — historical validation cannot demand current source

- **Finding:** The imported Sequence 9 source projection intentionally differs
  after Sequence 10 code edits.
- **Resolution:** Validate the exact Sequence 9 Tier archive/preflight as
  historical authority; active source equality belongs to the correction
  preflight. Preserve old public verify's source-drift rejection.
- **Status:** Closed.

### Review iteration 5 — Sequence 9 tests did not execute production success

- **Finding:** Handler identity, parser, and envelope tests allowed the public
  comparator blocker to escape.
- **Resolution:** Require actual public parsing/production dispatch,
  transition artifacts, anti-mock self-checks, and normal-context comparator
  success.
- **Status:** Closed.

### Review iteration 6 — a full canary must not fabricate formal review

- **Finding:** Exercising root and later handlers needs accepted reviews, but
  the implementer cannot author formal human decisions.
- **Resolution:** Permit clearly tagged test-owned intake only in temporary
  fixtures; retain the formal 117-item packet as an external stop.
- **Status:** Closed.

### Review iteration 7 — downstream nonzero exits can be masked

- **Finding:** `publish-review` performs a second root read before checking
  its first nonzero result; `init-theme-batch` redundantly reopens root after
  success.
- **Resolution:** Return committed artifacts from the descriptor operation,
  check exits immediately, and use those exact artifact paths.
- **Status:** Closed.

### Review iteration 8 — “last sequence” cannot be guaranteed

- **Finding:** Calling Sequence 10 definitively final would exceed available
  evidence and repeat earlier overconfidence.
- **Resolution:** Make production-shaped dispatch/canary and the definitive
  formal comparator mandatory confidence gates, while explicitly avoiding a
  guarantee about unknown later defects.
- **Status:** Closed.

### Review iteration 9 — correction namespace and authorization timing

- **Finding:** Reusing Sequence 9 paths or accepting an authorization before
  final package/cardinalities would create collisions or unreviewed bytes.
- **Resolution:** Fix disjoint Sequence 10 IDs/paths now; create and review the
  final authorization candidate during implementation, then require separate
  exact-byte maintainer acceptance before bootstrap.
- **Status:** Closed.

### Review iteration 10 — frozen geometry contract contradicts real migration

- **Finding:** The real production-shaped canary reached the comparator after
  the descriptor fix, then all `57` affected captures failed because the
  frozen contract forbids responsive width/height/root/downstream changes.
- **Resolution:** Add a Sequence 10 coordinator-owned geometry adapter and
  keep the evidence/capture stack immutable.
- **Status:** Closed.

### Review iteration 11 — generalized tolerance would create a bypass

- **Finding:** Merely allowing shrink/growth/translation could accept a
  coherent but unauthorized layout mutation.
- **Resolution:** Require the exact complete geometry-transition projection,
  counts, canonical byte size, and SHA-256 before any normalization, then
  audit actual containment/viewport/overlap/ancestry.
- **Status:** Closed.

### Review iteration 12 — normalization could hide semantic regressions

- **Finding:** A replacement comparator or broad after-document rewrite could
  turn the correction into self-approval.
- **Resolution:** Authenticate the exact frozen evidence module; mutate only
  a defensive copy's `bounds`; invoke the unchanged frozen semantic
  comparator; test semantic, DOM-order, stable-state, catalog, and unaffected
  capture attacks.
- **Status:** Closed.

### Review iteration 13 — real captures contain bounded edge quantization

- **Finding:** Exact integer DOM boxes contain `7` one-pixel historical
  right-edge and `30` one/two-pixel migrated bottom-edge descendant
  overhangs, so exact descendant containment rejects the authenticated
  captures before semantic comparison.
- **Resolution:** Keep the exact full-profile hash and add only an inclusive
  `2` CSS-pixel descendant/ancestor containment envelope; root, boundary,
  viewport, ownership, and overlap checks remain exact, and `3` pixels fails.
- **Status:** Closed.

### Review iteration 14 — capture-time text volatility is not app semantics

- **Finding:** After geometry isolation the frozen semantic pass found `14`
  owned temporary-root path fields and `7` control-root aggregate names that
  differ despite stable fixture suffix and exact focused option semantics.
- **Resolution:** Add a separate exact `21/8498/9bad8fb8...882` volatility
  projection, validate runtime suffix and Analytics control evidence, and
  canonicalize only those copied fields before the unchanged frozen semantic
  comparator.
- **Status:** Closed.

### Review iteration 15 — generic DOM rectangles are not interaction layers

- **Finding:** Actual captures contain hundreds of ordinary/control rectangle
  intersections from sidebar, grid, and nested-container layout even though
  focused browser evidence records no target overlap or clipping. Reusing the
  frozen ordinary-sibling rectangle rule as an actual-layout audit repeats
  the false rejection.
- **Resolution:** Keep exact root/boundary/viewport/ownership and cross-root
  checks, but source target overlap/clipping/overflow from authenticated
  focused `controlEvidence`, mapped by selector and viewport for full-page
  captures. Use the frozen ordinary rule only on the semantic zero-box plane.
- **Status:** Closed.

### Review iteration 16 — legacy awake-gate precondition conflicts with formal evidence

- **Finding:** required `make ui-ux1b-recovery-tests` invoked the
  pre-Sequence8 awake-gate test in the real workspace, where the exact formal
  Sequence 8 namespace is intentionally present. Its future-namespace
  absence assertion therefore failed even though the formal artifacts were
  correct.
- **Resolution:** keep `scripts/ui_ux_awake_gate.py` and
  `scripts/test_ui_ux_awake_gate.py` byte-for-byte unchanged, execute that
  legacy pre-capture test from a test-owned temporary source root under a
  sandbox that denies only read visibility of retained
  `/private/tmp/qr-ux1b-s8`, remove the temporary root with a shell trap, and
  continue every other recovery test against the real workspace.
- **Status:** Closed.

### Review iteration 17 — legacy interaction role conflicts with accepted migration

- **Finding:** `make ui-ux1b-legacy` passed UX-0 `21/21` and four unmigrated
  UX-1A cases, but its old institution interaction still searched for a
  button whose accessible name includes both choices. The accepted migration
  intentionally replaced that control with radio/segmented semantics, so all
  four institution viewports timed out before metrics collection.
- **Resolution:** keep the frozen snapshot harness unchanged, retain Chromium
  legacy captures for UX-0 and the four unmigrated UX-1A cases, and run
  `scripts/test_ui_accessible_selection_controls.py` in the same target to
  validate the migrated institution selector and all other migrated controls
  by their exact role, labels, state, layout, and fail-soft contracts.
- **Status:** Closed.

No unresolved blocking issue remains in the revised plan. The maintainer's
request to review and solve the migration-geometry contract authorizes this
Sequence 10 implementation amendment. Formal execution remains separately
blocked until the maintainer accepts the regenerated final Sequence 10
authorization document's exact bytes.

## Review checklist

- [x] The exact observed descriptor mismatch has a causal correction.
- [x] Dummy-FD and incidental-lock workarounds are prohibited.
- [x] Sequence 8/9 evidence remains immutable.
- [x] Current source receives a separate correction authority.
- [x] Stored provenance and runtime capacity have distinct semantics.
- [x] Hard-limit, equations, ceiling, apply, and restore remain fail closed.
- [x] Real public dispatcher/transition tests replace identity-only proof.
- [x] Review publication and theme init propagate exact exits/destinations.
- [x] Root v2 schema and capture recovery identity are preserved.
- [x] Formal external review remains independent.
- [x] API/Streamlit/artifact fail-soft behavior is protected.
- [x] Exact real geometry census and profile are specified.
- [x] Frozen evidence/capture-stack bytes remain unchanged.
- [x] Actual geometry audit and semantic comparison have separate owners.
- [x] Geometry mutation and semantic mutation attacks are specified.
- [x] Integer descendant quantization is bounded at 2 px with 3 px rejection.
- [x] Capture-time runtime/root-name volatility is exact and option-bound.
- [x] Affected files, verification, risks, rollback, and scope are known.
- [x] BDD scenario counts meet priority rules.
- [x] Revised implementation is authorized.
- [ ] Red-first implementation tests pass.
- [ ] Final authorization candidate is accepted.
- [ ] Correction Tier/preflight is published and freshly verified.
- [ ] Formal comparator/report/packet pass.
- [ ] Independent 117-item intake is accepted.

## Traceability summary

The sibling ledger is authoritative canonical JSON. It contains closed,
bidirectional links among `REQ-010`, `CFR-034..045`,
`AC-SEQ10-001..013`, `IMPL-057..069`, and `TEST-080..095`, with structural
coverage `10000` basis points, no gaps, and no orphans. Planning status is
`NOT_TESTED`, implementation status `IN_PROGRESS`, and test execution records
only verified implementation checks after they run.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `1.1-reviewed` | 2026-07-27 | Integrated and closed the real-canary migration-geometry blocker with exact profile authentication, bounded capture quantization, exact non-control volatility, actual safety audit, semantic-plane canonicalization, frozen comparison, and adversarial tests. |
| `1.0-reviewed` | 2026-07-27 | Closed nine planning findings covering descriptor semantics, historical authority, production-path proof, external review, exit propagation, confidence language, and correction namespace timing. |
| `0.9-review-candidate` | 2026-07-27 | Initial Sequence 10 descriptor-budget correction draft. |

## Next handoff

Continue the already authorized implementation at Phase 2B, then complete
Phase 3 and regenerate the authorization candidate from the final reviewed
plan, ledger, code, tests, and Makefile. Formal execution is still separately
gated by acceptance of that final Sequence 10 authorization document and must
stop again after the formal 117-item packet until independent review exists.
