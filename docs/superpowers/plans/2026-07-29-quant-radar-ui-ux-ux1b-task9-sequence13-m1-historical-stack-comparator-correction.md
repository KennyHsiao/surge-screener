# UX-1B Sequence 14 Historical-Stack Comparator Correction

## Document info

| Field | Value |
| --- | --- |
| Status | `REVIEWED — IMPLEMENTATION NOT STARTED` |
| Version | `1.0-reviewed` |
| Date | `2026-07-29` |
| Owner | Maintainer |
| Author | Scribe |
| Reviewers | Scribe blocking review; Maintainer approval pending |
| Audience | Maintainer, Builder, test/review agents |
| Plan path | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence13-m1-historical-stack-comparator-correction.md` |
| Traceability path | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence13-m1-historical-stack-comparator-correction.traceability.yaml` |
| Correction ID | `20260729T050000Z` |
| Tier ID | `20260729T051000Z` |
| Retained capture ID | `20260729T040000Z` |
| Continuation ID | `20260729T060000Z` |
| Formal stop | `H2_PACKET` |

This document is a correction plan. It is not implementation or formal
execution authority. It authorizes no source edit until blocking review is
clean and the maintainer explicitly accepts this plan for implementation.
Formal publication later requires separate acceptance of an exact Sequence 14
authorization document by SHA-256, byte size, and mode.

## Purpose

Sequence 13 has a complete, immutable, and repeatedly reopened
`M1_CAPTURE`. Its sole formal Chromium run produced:

```text
logical requests = 36
root captures     = 44
artifact leaves   = 88
manifest leaves   = 89
```

The Sequence 13 comparator failed before report publication. The immutable
legacy capture-stack file is exact, but the comparator passed it to
`authenticate_capture_stack_contract()`. That function correctly rehashes
member paths against current live source. Four legacy member declarations
differ from current source because later reviewed sequences changed those
files. A historical contract therefore cannot pass a live-member check.

Sequence 14 will:

- retain and import the exact Sequence 13 `M1_CAPTURE`;
- authenticate the legacy stack as exact whole-file historical authority;
- validate its embedded member records and control catalog without reading
  current member paths;
- continue comparison using the current Sequence 13 stack as live authority;
- publish a distinct `125`-comparison report and `125`-item packet;
- stop at `H2_PACKET` before independent intake;
- perform no capture, recapture, retry, UI change, or evidence rewrite.

## Scope

### In scope

- Exact historical import of the Sequence 13 authorization, Tier, preflight,
  capture stack, passed manifest, and all `88` referenced artifacts.
- Exact descriptor-safe inventory of the retained `89`-file capture tree.
- A legacy capture-stack whole-file importer with embedded-record validation.
- Minting an authenticated historical catalog only after semantic validation.
- Current live-member authentication of the Sequence 13 stack.
- A distinct Sequence 14 Tier, preflight, source package, runtime receipt,
  command set, forward namespace, and lifecycle.
- A continuation comparator producing `81 + 44 = 125` comparisons.
- Preservation of the nested `81 + 36 = 117` semantic oracle.
- A distinct `125`-item review packet and mandatory `H2_PACKET` pause.
- Lifecycle-aware updates to tests that previously assumed permanent
  Sequence 13 absence.
- Complete recovery, fail-soft API/UI, runtime, syntax, dependency, scope,
  whitespace, and protected-artifact gates.

### Out of scope

- Any new Chromium, Streamlit, Playwright, full-page, or focused capture.
- Editing or deleting the Sequence 13 capture root.
- Publishing into any Sequence 13 report, packet, intake, review, candidate,
  or root path.
- Editing production `ui/`, `api/`, providers, selectors, fixtures, browser
  worker, evidence schemas, root expansion, theme source, or dependencies.
- Editing legacy, Sequence 8–13 plans, ledgers, authorizations, stacks, Tier,
  preflights, captures, reports, packets, reviews, or runtime evidence.
- Recomputing the historical stack from current member files.
- Treating historical member drift as permission to update the legacy stack.
- External review intake, manual review, candidate, root, or theme
  publication.

## Non-goals

- Sequence 14 does not prove later external review acceptance.
- Sequence 14 does not change comparison geometry or semantic tolerances.
- Sequence 14 does not create a replacement capture stack.
- Sequence 14 does not alter the accepted v1/v2 render contracts.
- Sequence 14 does not weaken current-stack live reauthentication.
- Sequence 14 does not repair Sequence 13 in place.

## Glossary

| Term | Meaning |
| --- | --- |
| Historical stack | Exact immutable stack document interpreted from its own embedded records. |
| Live stack | Current stack document whose member records must equal current files. |
| M1 import | Exact retained Sequence 13 Tier, preflight, manifest, and `88` capture artifacts. |
| Continuation namespace | New Sequence 14 report/packet paths derived from `20260729T060000Z`. |
| Whole-file authority | SHA-256, size, mode, owner, group, nlink, safe ancestors, canonical bytes, and internal semantics of one immutable file. |
| Frozen source | Source records archived by a create-once preflight and no longer compared with later current source. |

## Retained Sequence 13 authority

### Reviewed planning authority

| Role | Path | SHA-256 | Bytes | Mode |
| --- | --- | --- | ---: | --- |
| Plan | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.md` | `c06f83b3722beedd5907cb9b9b3c688a723012321de6d6d74c095eeab4914559` | `53660` | `0644` |
| Traceability | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.traceability.yaml` | `5a6657a57eb411d80442ac93f98ee02385b0a1e97f25c8da03823c3b086390f1` | `7074` | `0644` |
| Authorization | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-seq13.md` | `9cc56179d6f96a50972cc51a44bc343249d1c206a042093eada2509fa70dbf3c` | `6439` | `0644` |

### Exact Tier, preflight, and capture

Every file below must reopen through safe descriptors with exact bytes,
metadata, ownership, group, nlink, and ancestor identity.

| Role | Path | SHA-256 | Bytes | Mode |
| --- | --- | --- | ---: | --- |
| Lease | `.claude/ui_snapshots/ux1b/recovery/.render-manifest-correction-20260729T030000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-prechange-seq13.json` | `c58993ed849f9a2ab79b854a254b6c159eec841d62cac68e3e659d825cead8db` | `12925` | `0600` |
| Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-rollback-seq13.json` | `8ffa55ad8aa00699735e2d6472ed090b6436d51808e3e342dad79c6195f12851` | `5448` | `0600` |
| Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-prechange-20260729T031000Z/.quant-radar-theme-handoff-render-manifest-correction-owner` | `e2ba195f1552d27f8a0452d69ab34aa7000991e9f4e7137c8e723022e23b8401` | `135` | `0600` |
| Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-prechange-20260729T031000Z/prechange-files.tar` | `de99717bbdb98e0f29379a9fb86b7593c2f86a2e0bd383e3123aff77569eef8c` | `4997120` | `0600` |
| Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-prechange-20260729T031000Z/bundle-manifest.json` | `17f82d0637021ea162d6b75b19632d523b3d2954d04fb7831ac893bb7a7a88d0` | `1612` | `0600` |
| Preflight | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-preflight-20260729T030000Z.json` | `16b575ebe0908d97c806233bf6028333816df0b44d383cc04a55cc33e3bc4171` | `69240` | `0600` |
| Sequence 13 stack | `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json` | `a6dc1f4b97e727f7b641b845004e61b0a773b8a247af7ae6ddc38bac6c5b95c7` | `5429` | `0600` |
| Passed manifest | `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260729T040000Z/manifest.json` | `714fdc9efa8ec3047ee0a053eaeb0408f443e6bebecd8e74b3e043ab17e8ea7f` | `40036` | `0600` |

The retained preflight must remain compact canonical JSON with:

```text
schemaVersion       = quant-radar-ui-ux-render-manifest-correction-preflight/v1
status              = passed
correctionId        = 20260729T030000Z
tierId              = 20260729T031000Z
captureId           = 20260729T040000Z
sourceDigest        = b182aa60ca712ceeca05cbd158652c7189206fdc2c702f222c136b242afa253c
runtimeTreeSha256   = 9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75
namespaceInventory.initialState = M0_READY
```

The passed manifest must retain exactly one terminal LF and:

```text
status                   = passed
plannedLogicalRequests   = 36
completedLogicalRequests = 36
plannedRootCaptures      = 44
completedRootCaptures    = 44
expectedCaptureCount     = 44
captures                 = 44
childrenQuiescent        = true
sourceDigestStart/End    = b182aa60ca712ceeca05cbd158652c7189206fdc2c702f222c136b242afa253c
captureStackDigest       = 1a10bf5015073a1a31bff470145484227f88f6b2f3a90903c1451ac845c5bb1b
rootExpansionSha256      = 13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca
```

The capture root contains exactly `89` regular files and `91` directories.
Directory modes are exactly:

```text
0700 = 45 directories: capture root plus 44 root-capture leaf directories
0755 = 46 directories: captures plus case and viewport directories
```

The importer derives the complete allowed directory/leaf set from the exact
manifest and root expansion, then descriptor-walks the retained root. It must
reopen all artifact references, validate every v2 claim against actual
sidecar bytes, validate PNG dimensions and hashes, and reject every extra,
missing, linked, replaced, mode-changed, or unsafe descendant.

### Historical import classification

Add `_import_sequence13_m1_capture()` in
`scripts/ui_ux_theme_handoff.py`. It returns `S13_M1_CAPTURED` only after:

1. exact plan, ledger, authorization, Tier, stack, preflight, and manifest
   identities pass;
2. the retained PAX archive and bundle reopen as the exact frozen Sequence 13
   source package without comparison to current source; archive inspection is
   descriptor-based and never extracts a member to the filesystem;
3. the preflight's creation-time source, runtime, namespace, descriptor, and
   stack claims agree internally;
4. `_authenticate_sequence13_capture_manifest()` reopens all `89` leaves
   using the exact historical preflight value;
5. the `36/44/88/89` closure and process quiescence agree;
6. all Sequence 13 report, packet, intake, review, candidate, and shared root
   paths remain absent.

The importer must not call
`_reauthenticate_render_manifest_preflight()` or
`_validate_render_manifest_preflight_complete()` against current source.
Those functions rebuild current source/runtime authority and are valid only
inside the frozen Sequence 13 lifecycle.

The retained archive contains exactly `19` ordered regular members. The
compact bundle must remain:

```text
schemaVersion      = quant-radar-ui-ux-render-manifest-correction-bundle/v1
status             = sealed
archivedPaths      = 19
namespaceLeafCount = 3
```

## Legacy capture-stack historical importer

### Exact immutable document

```text
path: docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
sha256: 8b354ec6d7f84e4bfbd96c098ffd1dae2db0d90f7f9cf86d168bc8a9298df820
size: 5340
mode: 0600
baseCaptureStackDigest:
  6c1f08266d479d3e3e3e77f35dc06b6b5cd81c5160c9a1df91ed0e7b7dcdbfe7
captureStackDigest:
  69eeec0dcdffdab16d5696896cb4fc5ddb27071591953d04b4c907ea5b78055e
workerCatalogSha256:
  800973597bfce14fb21f7b6b63851f5c100dc833b32b961c6036fb1ee52303cf
```

The file is compact canonical JSON with exactly nine sorted member records.
Its embedded control catalog contains `9` focused cases, `7` full-page cases,
and `4` viewports.

### Observed legitimate live drift

The document is exact. These historical member declarations differ from
current source:

| Path | Historical SHA-256 / bytes | Current SHA-256 / bytes |
| --- | --- | --- |
| `scripts/ui_ux_browser_worker.py` | `b8a70dc1...b82b` / `221501` | `2d4c2656...aac5` / `259187` |
| `scripts/ui_ux_evidence.py` | `3ae2a02b...009a` / `363635` | `4835c2e7...39c9` / `417548` |
| `scripts/ui_ux_isolation.py` | `cec1c7b6...3497` / `202716` | `11d52334...af98` / `203019` |
| `scripts/ui_ux_snapshot_matrix.py` | `2184fdc8...ced2` / `264020` | `e7eff4f2...702f` / `289637` |

This drift is expected lineage. Updating the legacy document is forbidden.

### Import algorithm

Add `_reauthenticate_legacy_capture_stack_history()`. It must:

1. open the exact file through a safe descriptor;
2. verify SHA-256, size, mode, uid, gid, nlink, and canonical compact bytes;
3. require the exact top-level schema and key set;
4. require nine unique sorted member records with safe paths and exact
   embedded metadata types;
5. recompute `baseCaptureStackDigest` only from the embedded member records;
6. validate the embedded control catalog against the frozen catalog,
   viewports, embedded base digest, and its own capture-stack digest;
7. validate the exact embedded worker-catalog summary;
8. mint an `AuthenticatedControlCatalog` only after steps 1–7 pass;
9. return the exact contract record, embedded members, digests, and minted
   catalog.

The historical importer must not open, stat, hash, or compare any legacy
member path through the workspace descriptor. It may use the current
`scripts.ui_ux_evidence` module only after that module is independently
authenticated as a Sequence 14 source dependency and only for pure embedded
catalog validation/minting. Its current bytes never satisfy or replace a
legacy member record. Tests preload the current module, replace every
workspace member path, and use a descriptor workspace that contains only the
contract file.

Only the legacy importer receives this historical behavior.
`docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json` remains the
current live stack and must rehash all nine current member files.
The implementation uses the existing private `_mint_control_catalog()` only
after validation and does not weaken `AuthenticatedControlCatalog`,
`_registered_control_catalog()`, or their provenance registry.

## Sequence 14 authority

### Fixed IDs

```text
correctionId   = 20260729T050000Z
tierId         = 20260729T051000Z
retainedCaptureId = 20260729T040000Z
continuationId = 20260729T060000Z
```

### Planned authorization candidate

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-historical-stack-comparator-correction-seq14.md
```

The exact candidate will bind:

- this reviewed plan and traceability ledger;
- every retained Sequence 13 row above;
- the exact `S13_M1_CAPTURED` import and absence of later Sequence 13 leaves;
- the exact legacy whole-file stack authority;
- the exact current Sequence 13 live stack;
- the Sequence 14 source package and five commands;
- all four fixed IDs;
- the mandatory `H2_PACKET` stop;
- an explicit absence of capture or retry authority.

The candidate is generated last. Formal bootstrap requires separate
maintainer acceptance of its whole-document SHA-256, byte size, and mode.

### Tier and preflight

```text
.claude/ui_snapshots/ux1b/recovery/.historical-stack-comparator-correction-20260729T050000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-historical-stack-comparator-correction-prechange-seq14.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-historical-stack-comparator-correction-rollback-seq14.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-comparator-correction-prechange-20260729T051000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-comparator-correction-preflight-20260729T050000Z.json
```

The Tier uses the existing global lock and create-or-exact-reopen
primitives. The preflight binds:

- exact authorization, plan, ledger, Tier, and lease;
- exact `S13_M1_CAPTURED` historical import;
- exact historical legacy stack and validated catalog;
- exact current Sequence 13 live stack, members, and catalog;
- current Sequence 14 source/supplemental projections;
- current runtime identity and tree;
- exact command/Make contract;
- initial Sequence 14 namespace absence;
- deterministic descriptor profile.

After an authorized Sequence 14 source transition, the old Sequence 13 public
verify command is expected to reject current-source drift. It must not be
relaxed or patched to accept changed source. Sequence 14 commands verify the
retained M1 state through `_import_sequence13_m1_capture()` and separately
verify current source through the Sequence 14 preflight.

The source archive uses deterministic `tarfile.PAX_FORMAT`. It must preserve
exact member paths, uid/gid `0`, empty names, mtime `0`, member modes, and
stable ordering. A USTAR archive is forbidden because the plan and ledger
basenames exceed USTAR's name field.

### Source package

The closed package contains exactly:

```text
Makefile
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence13-m1-historical-stack-comparator-correction.md
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence13-m1-historical-stack-comparator-correction.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-historical-stack-comparator-correction-seq14.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_evidence.py
scripts/ui_ux_theme_handoff.py
```

No `.venv`, cache, capture artifact, UI, API, fixture, provider, secret, or
unlisted worktree file enters the package.

## Forward namespace and lifecycle

### New paths

```text
0 .claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json
1 .claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json
2 .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
3 .claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
4 .claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T060000Z.json
5 docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

The first five paths are new and disjoint. The root path is shared product
authority and is not writable by this correction.

### States

| State | New leaves | Meaning | Allowed action |
| --- | ---: | --- | --- |
| `H0_READY` | `0` | Accepted preflight plus exact imported M1 capture | compare or verify |
| `H1_REPORT` | `1` | Exact `125`-comparison report | prepare packet or verify |
| `H2_PACKET` | `2` | Exact `125`-item packet | mandatory stop |
| `H3_INTAKE` | `3` | Future external intake | forbidden |
| `H4_REVIEW` | `4` | Future manual review | forbidden |
| `H5_CANDIDATE` | `5` | Future candidate | forbidden |
| `H6_ROOT` | `6` | Future root | forbidden |

Only a no-gap prefix is valid. Every present leaf must pass exact metadata,
canonical bytes, schema, lineage, cardinality, and cross-leaf semantics.

### Comparator

The comparator requires `H0_READY` and uses exactly:

1. historical before-pages manifest;
2. historical accepted after-pages manifest;
3. historical before-controls manifest;
4. retained Sequence 13 after-root-controls manifest;
5. the new machine-report reference when building the later packet.

The machine report itself compares the first four evidence inputs and records
the exact Sequence 12 failed manifest only as
`excludedPredecessorFailure.usedAsInput=false`.

It must produce:

```text
pageComparisons            = 81
controlRootComparisons     = 44
comparedCaptures           = 125
legacySemanticComparisons  = 117
passedRootCaptures         = 44
unboundRootCaptures        = 0
exactPrePostProjections    = 88
```

The historical catalog comes only from the whole-file importer. The corrected
catalog comes only from live Sequence 13 stack authentication. The report
must preserve the exact legacy-to-Sequence13 stack transition and source
transition already specified by Sequence 13.

The report publishes only to the Sequence 14 report path with create-once
semantics. It must never backfill the absent Sequence 13 report path.

### Review packet

`prepare-review` requires `H1_REPORT`. It publishes a review-packet v2 with:

```text
inputs = 5
items = 125
unique ordered item IDs = 125
machineReport = exact Sequence 14 report reference
```

The input list contains the report reference plus the four evidence manifest
references. Packet semantics and item ordering remain unchanged.

After publication and reopen, the lifecycle must equal `H2_PACKET`.
Intake, review, candidate, and root remain absent.

## Public commands and Make targets

Exactly five commands are allowed:

```text
bootstrap-historical-stack-comparator-correction
preflight-historical-stack-comparator-correction
verify-historical-stack-comparator-correction-preflight
compare-historical-stack-migration
prepare-historical-stack-review
```

Each command requires:

```text
--correction-id 20260729T050000Z
--tier-id 20260729T051000Z
--capture-id 20260729T040000Z
--continuation-id 20260729T060000Z
--json
```

No command exposes an output path, stack path, schema, catalog, source,
capture, retry, resume, or deletion flag. No Sequence 14 capture or reconcile
command exists.

Exactly five Make targets route only to those commands:

```text
ui-ux1b-historical-stack-bootstrap
ui-ux1b-historical-stack-preflight
ui-ux1b-historical-stack-verify
ui-ux1b-historical-stack-compare
ui-ux1b-historical-stack-prepare-review
```

## Requirements

| ID | Requirement |
| --- | --- |
| `REQ-015` | Continue UX-1B handoff from the exact retained Sequence 13 `M1_CAPTURE` without recapture or historical mutation. |
| `CFR-067` | Import the complete Sequence 13 authority, Tier, preflight, stack, and `89`-file capture tree as immutable historical authority. |
| `CFR-068` | Authenticate the legacy stack from exact whole-file bytes and embedded records while keeping the Sequence 13 stack live-member bound. |
| `CFR-069` | Use distinct Sequence 14 IDs, Tier, preflight, source/runtime authority, commands, and forward paths with no capture capability. |
| `CFR-070` | Preserve `81/44/125`, nested `81/36/117`, five packet inputs, and exact excluded-failure semantics. |
| `CFR-071` | Stop at `H2_PACKET` with all later paths absent and all protected historical/product bytes unchanged. |
| `CFR-072` | Archive the exact Sequence 14 source package deterministically despite long authority filenames. |

## Acceptance criteria

### `AC-SEQ14-001` — exact retained M1 import

Given the retained Sequence 13 authority and capture tree, when any Sequence
14 command runs, then all frozen source/Tier/preflight facts reopen as
historical data, all `89` capture files reauthenticate, and the importer
returns exactly `S13_M1_CAPTURED`.

### `AC-SEQ14-002` — historical legacy stack

Given the exact legacy stack document and legitimately changed current member
files, when the historical importer runs, then the embedded stack/catalog
validates without member-path reads; any document or embedded-record mutation
is rejected.

### `AC-SEQ14-003` — disjoint no-capture authority

Given accepted exact Sequence 14 authorization bytes, when bootstrap and
preflight run, then the create-once authority reaches `H0_READY`, binds the
retained M1 capture, and exposes no capture, retry, resume, or old-output
permission.

### `AC-SEQ14-004` — corrected comparison

Given exact `H0_READY`, when compare runs, then one create-once report reaches
`H1_REPORT` with `81/44/125`, nested `117`, exact stack/source transitions,
and the Sequence 12 terminal failure excluded from inputs.

### `AC-SEQ14-005` — packet pause

Given exact `H1_REPORT`, when prepare-review runs, then one create-once
`125`-item packet with five inputs reaches `H2_PACKET`, and every later path
remains absent.

### `AC-SEQ14-006` — compatibility and protected scope

Given the complete implementation diff, when all targeted, full recovery,
fail-soft, runtime, syntax, dependency, scope, and protected-artifact gates
run, then no unexplained failure or unplanned source/evidence change remains.

### `AC-SEQ14-007` — deterministic long-path source authority

Given the closed source package containing long plan/ledger filenames, when
the archive is built twice, then both PAX byte streams are identical, reopen
to the exact ordered package, and reject USTAR or path substitution.

## Implementation map

| ID | Planned implementation |
| --- | --- |
| `IMPL-109` | Exact `S13_M1_CAPTURED` historical importer and retained-tree inventory. |
| `IMPL-110` | Exact legacy stack whole-file parser, embedded digest/catalog validation, and authenticated catalog minting. |
| `IMPL-111` | Distinct Sequence 14 authorization, deterministic PAX Tier, preflight, source/runtime, and namespace authority. |
| `IMPL-112` | Sequence 14 prefix classifier, five CLI handlers, argument validation, production registry, and Make routes. |
| `IMPL-113` | Continuation comparator using historical legacy catalog and live Sequence 13 catalog. |
| `IMPL-114` | Distinct review-packet publication and `H2_PACKET` pause. |
| `IMPL-115` | Lifecycle-aware permanent tests plus mutation, production-shaped, compatibility, and scope gates. |
| `IMPL-116` | Exact authorization-candidate generation and pre-formal verification. |

## Test map

| ID | Test obligation |
| --- | --- |
| `TEST-142` | Reproduce the exact legacy live-member false failure and prove the corrected comparator does not call live authentication for the legacy path. |
| `TEST-143` | Validate the exact legacy document, embedded member digest, catalog, worker summary, zero workspace member reads, separately authenticated current validator module, and every document/metadata/catalog mutation. |
| `TEST-144` | Reopen exact Sequence 13 authorization/Tier/preflight/stack/manifest, all `19` source members, `89` files, and `91` directories; reject every mutation, extra descendant, mode drift, later Sequence 13 leaf, or current-source rebuild. |
| `TEST-145` | Prove Sequence 13 creation-time source/runtime facts remain historical while Sequence 14 current source/runtime are independently bound. |
| `TEST-146` | Verify Sequence 14 IDs, paths, command grammar, handler registry, Make routes, no-capture surface, and old-command non-authority. |
| `TEST-147` | Build the PAX archive twice, require byte equality and exact ordered reopen, and reproduce USTAR rejection for the long filename. |
| `TEST-148` | Production-shaped disposable compare proves `81/44/125`, nested `117`, exact transitions, exact exclusion, collision safety, and read-only reopen. |
| `TEST-149` | Production-shaped packet proves five inputs, `125` unique ordered items, exact report binding, `H2_PACKET`, and later absences. |
| `TEST-150` | Existing Sequence 8–13 and formal-state tests remain green with Sequence 13 represented through the exact historical M1 importer; old public verify remains fail-closed after current-source transition. |
| `TEST-151` | Full recovery, fail-soft API/UI, Python 3.10 AST, compile, tabnanny, dependency, whitespace, dirty-worktree, source-scope, runtime, process, diff, and protected-hash gates pass. |

## Given-When-Then scenarios

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| `SC-AC-SEQ14-001-HP-001` | Exact Sequence 13 M1 | Importer runs | `S13_M1_CAPTURED` |
| `SC-AC-SEQ14-001-NP-001` | One Tier/preflight byte differs | Importer runs | Fail before Seq14 write |
| `SC-AC-SEQ14-001-NP-002` | One capture leaf differs | Importer runs | Reject whole bundle |
| `SC-AC-SEQ14-001-NP-003` | A Seq13 report or later leaf exists | Importer runs | Reject predecessor state |
| `SC-AC-SEQ14-001-EP-001` | Current coordinator differs from frozen source | Importer runs | Historical import still exact |
| `SC-AC-SEQ14-002-HP-001` | Exact legacy file, changed live members | Historical importer runs | Accept embedded authority |
| `SC-AC-SEQ14-002-NP-001` | Legacy whole-file byte differs | Importer runs | Reject |
| `SC-AC-SEQ14-002-NP-002` | Embedded member/catalog digest differs | Importer runs | Reject |
| `SC-AC-SEQ14-002-NP-003` | Importer reads a member path | Zero-read oracle runs | Fail test |
| `SC-AC-SEQ14-003-HP-001` | Accepted auth, absent Seq14 paths | Bootstrap/preflight run | `H0_READY` |
| `SC-AC-SEQ14-003-NP-001` | ID/path/command/source/runtime drift | Any command runs | Fail before publication |
| `SC-AC-SEQ14-003-NP-002` | Capture/retry flag is supplied | CLI parses | Reject |
| `SC-AC-SEQ14-003-EP-001` | Exact Tier/preflight exists | Command reruns | Read-only exact reopen |
| `SC-AC-SEQ14-004-HP-001` | Exact `H0_READY` | Compare runs | `H1_REPORT`, `125` |
| `SC-AC-SEQ14-004-NP-001` | Historical catalog is live-rehashed | Compare runs | Regression test fails |
| `SC-AC-SEQ14-004-NP-002` | Partial/excluded artifact enters inputs | Compare runs | Reject |
| `SC-AC-SEQ14-004-NP-003` | Sequence 13 report path is targeted | Scope guard runs | Reject |
| `SC-AC-SEQ14-004-EP-001` | Exact report exists | Compare reruns | Read-only `H1_REPORT` |
| `SC-AC-SEQ14-005-HP-001` | Exact `H1_REPORT` | Prepare runs | `H2_PACKET` |
| `SC-AC-SEQ14-005-NP-001` | Packet input/item count differs | Verify runs | Reject |
| `SC-AC-SEQ14-005-NP-002` | Intake/review/candidate/root exists | Verify runs | Reject boundary |
| `SC-AC-SEQ14-005-EP-001` | Exact packet exists | Prepare reruns | Read-only `H2_PACKET` |
| `SC-AC-SEQ14-006-HP-001` | Complete planned diff | All gates run | Green exact scope |
| `SC-AC-SEQ14-006-NP-001` | UI/API/fixture/evidence drift | Scope gate runs | Fail |
| `SC-AC-SEQ14-006-NP-002` | Owned process remains | Process gate runs | Fail |
| `SC-AC-SEQ14-007-HP-001` | Same closed package twice | PAX build runs | Identical bytes |
| `SC-AC-SEQ14-007-NP-001` | USTAR or path substitution | Archive test runs | Reject |

## Affected files

### Planned implementation edits

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-historical-stack-comparator-correction-seq14.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

### Current source preimages

| Path | SHA-256 | Bytes | Mode |
| --- | --- | ---: | --- |
| `Makefile` | `58f3817cf13ee36a543bb5aab1bb5c7b82efeedfa8faa2168ab7e602b132ff80` | `39542` | `0644` |
| `scripts/ui_ux_theme_handoff.py` | `0cb183ccbbe60e44a9d01a7126b410cad684d78319c66e1cc5006bb697357b9e` | `1354217` | `0644` |
| `scripts/test_ui_ux_theme_handoff.py` | `c2bbc3551f198e4496cb37278656eee6fc09d6141e2676efb9af0182b40b099a` | `1103777` | `0644` |
| `scripts/ui_ux_evidence.py` | `4835c2e73c46274c77c232166d2e48ec0ccef49542a9a9dd2811b0d5b6ed39c9` | `417548` | `0644` |

This plan, ledger, and Scribe logs are the only planning-stage edits.
Implementation must compare its actual diff against the planned list.

### Protected paths

```text
all Sequence 8–13 plans, ledgers, authorizations, Tier, preflights,
captures, reports, packets, intake, reviews, stacks, and runtime evidence
the exact Sequence 13 89-file capture tree
the legacy and Sequence 13 capture-stack contracts
all production ui/, api/, providers, fixtures, selectors, and theme source
scripts/ui_ux_browser_worker.py
scripts/ui_ux_isolation.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_fixtures.py
scripts/ui_ux_fixture_app.py
scripts/ui_ux_selection_fixture_app.py
scripts/ui_ux_theme_fixture_app.py
scripts/ui_ux_theme_matrix.py
requirements and environment configuration
```

## Implementation sequence

### Phase S14-0 — reviewed authority gate

- Freeze the reviewed plan and traceability ledger.
- Reopen exact Sequence 13 M1 and new path absences.
- Confirm all current preimages and protected hashes.
- Generate no authorization candidate.
- Obtain explicit maintainer implementation approval.

**Gate:** any predecessor drift, ID collision, unclear scope, or unresolved
review finding blocks source edits.

### Phase S14-1 — red historical/live tests

- Extend `TEST-140` lifecycle facts for retained M1.
- Replace `TEST-141`'s permanent real-workspace absence assertion with exact
  retained Sequence 13 M1 facts in the real workspace and separate
  creation-time absence assertions in a disposable Sequence 14 fixture.
- Add `TEST-142..147`.
- Reproduce the exact comparator failure from the production path.
- Prove the failure disappears only when legacy member reads are removed.
- Freeze PAX long-path behavior before Tier implementation.

**Gate:** red failures must map only to the known historical/live and archive
gaps. Tests use disposable namespaces and never mutate formal evidence.

### Phase S14-2 — importers

- Implement `IMPL-109..110`.
- Validate Sequence 13 frozen source from retained PAX archive/bundle.
- Reopen all `89` capture files.
- Validate legacy embedded records/catalog without member-path access.
- Keep Sequence 13 stack live-member validation unchanged.

**Gate:** every whole-file, embedded-record, tree, path-read, source-rebuild,
and later-leaf mutant fails closed.

### Phase S14-3 — authority and lifecycle

- Implement `IMPL-111..112`.
- Add fixed IDs, distinct paths, PAX Tier, preflight, classifier, commands,
  registry handlers, and Make targets.
- Bind current source/runtime independently from historical M1.
- Keep creation-time absence tests in disposable fixtures.

**Gate:** create-once fixtures reach only `H0_READY`; no capture surface or
real Sequence 14 artifact exists.

### Phase S14-4 — comparator and packet

- Implement `IMPL-113..114`.
- Run production-shaped compare and packet fixtures.
- Preserve geometry, semantic oracle, ordering, five inputs, exclusions, and
  `H2_PACKET` pause.

**Gate:** exact `H1_REPORT` and `H2_PACKET` reopen in disposable workspaces;
old paths and later paths remain absent.

### Phase S14-5 — complete review and gates

- Implement `IMPL-115`.
- Compare actual diff against this plan.
- Review code for bugs, regressions, missing tests, and maintainability.
- Run complete verification.
- Fix every blocking finding.

**Gate:** every relevant check passes; formal Sequence 14 paths remain absent.

### Phase S14-6 — authorization candidate

- Implement `IMPL-116`.
- Generate the candidate last.
- Verify markers, exact package, commands, IDs, paths, predecessor, stop, and
  explicit no-capture authority.
- Report SHA-256, byte size, and mode.
- Stop for maintainer acceptance.

### Phase S14-7 — later formal execution

Only after exact authorization acceptance:

1. bootstrap and reopen Sequence 14 Tier;
2. publish and reopen preflight at `H0_READY`;
3. publish and reopen report at `H1_REPORT`;
4. publish and reopen packet at `H2_PACKET`;
5. stop before intake.

No capture command is run. Any failure after Tier publication is retained and
requires another reviewed correction.

## Verification commands

At minimum:

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/test_ui_ux_evidence.py
.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python -B scripts/test_ui_accessible_selection_controls.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_ui_ux1a_safety.py
.venv/bin/python -B scripts/test_ui_ux_components.py
.venv/bin/python -B -m pip check
```

Mandatory targeted gates:

- exact production comparator failure reproduction;
- zero legacy member-path reads;
- exact embedded member base-digest recomputation;
- exact control-catalog semantic validation before minting;
- exact Sequence 13 PAX archive/bundle historical reopen;
- `89/89` capture-tree reopen with `44` v2 claims;
- exact current Sequence 13 live stack reauthentication;
- current source/runtime bound only by Sequence 14 preflight;
- deterministic PAX twice-byte-equal archive;
- no Sequence 14 capture/reconcile command or flag;
- `81/44/125`, nested `117`, exact exclusion and stack/source transitions;
- five-input, `125`-item packet and `H2_PACKET` stop;
- Python 3.10 AST for changed Python files;
- `py_compile`, `tabnanny`, dependency, whitespace, and diff checks;
- exact protected predecessor hashes and later-path absences;
- no owned process or temporary runtime remains.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The importer rebuilds Sequence 13 preflight against changed source. | Parse exact historical preflight and retained archive; never call its current-source validator. |
| Historical relaxation leaks to the current stack. | Use a legacy-path-specific helper; keep Sequence 13 stack on live authentication. |
| A forged catalog is minted as authenticated. | Validate exact file, embedded base digest, catalog semantics, and catalog digest before minting. |
| Current code reads legacy member paths indirectly. | Zero-read test workspace contains only the legacy contract file. |
| Sequence 13 capture is accidentally retried. | Authorization and CLI contain no capture or reconcile command. |
| Report backfills Sequence 13 path. | New continuation ID and source-scope assertions forbid old output paths. |
| Source edits invalidate retained M1. | Historical importer uses frozen archive facts; Sequence 14 preflight binds current source separately. |
| USTAR fails again on long filenames. | Require deterministic PAX and an exact twice-build test. |
| Permanent absence tests fail after valid formal progress. | Separate creation-time disposable absence from current exact M1 lifecycle facts. |
| Old Sequence 13 verify is weakened to tolerate changed source. | Keep it fail-closed; use only the new historical importer for retained M1. |
| Packet advances without review. | Mandatory stop is `H2_PACKET`; all later paths are forbidden. |
| Dirty worktree obscures scope. | Record preimages and compare only planned paths; preserve unrelated changes. |

## Rollback

Before Sequence 14 Tier publication:

- remove only disposable test namespaces created by this implementation;
- keep planning documents and every historical/formal artifact;
- do not reset or overwrite user changes.

After Sequence 14 Tier publication:

- never delete or overwrite Sequence 14 authorization, Tier, preflight,
  report, packet, or partial output;
- never modify Sequence 13 M1 or legacy stack authority;
- stop and create another reviewed correction after any failure.

Rollback never authorizes capture, UI, fixture, or historical evidence edits.

## Success metrics

| Metric | Target |
| --- | ---: |
| Sequence 13 authority/Tier/preflight/stack/manifest files | `10/10` exact |
| Sequence 13 frozen source archive members | `19/19` |
| Retained capture files/directories reopened | `89/89`, `91/91` |
| Retained logical/root/artifact counts | `36/44/88` |
| Legacy contract workspace member-path reads | `0` |
| Legacy embedded members validated | `9/9` |
| Current Sequence 13 stack members rehashed | `9/9` |
| New capture commands or runs | `0` |
| Report comparisons | `125/125` |
| Nested semantic comparisons | `117/117` |
| Packet inputs/items | `5/125` |
| Later artifacts at stop | `0` |
| Protected drift | `0` |
| Traceability coverage | `10000` basis points |

## Dependencies

- Exact Sequence 13 plan, ledger, authorization, Tier, preflight, stack, and
  retained `M1_CAPTURE`.
- Exact Sequence 12 terminal failure imported by Sequence 13.
- Exact historical before/after page and before-control manifests.
- Exact legacy stack whole-file authority.
- Existing descriptor, canonical JSON, PAX archive, current stack,
  comparator, packet, runtime, and create-once primitives.
- Maintainer approval of this reviewed plan, followed later by exact-byte
  acceptance of the Sequence 14 authorization candidate.

## Review checklist

- [x] Retained Sequence 13 M1 is imported without current-source rebuilding.
- [x] All `89` capture files, `91` directories, and later Sequence 13
  absences are closed.
- [x] Legacy whole-file and embedded catalog validation are complete.
- [x] Legacy member paths are never read.
- [x] Sequence 13 current stack remains live-member bound.
- [x] Sequence 14 IDs, Tier, preflight, paths, commands, and states are
  disjoint.
- [x] No capture, retry, resume, delete, or old-output authority exists.
- [x] PAX archive behavior and long-name regression are explicit.
- [x] Report and packet cardinalities, inputs, exclusions, and pause are exact.
- [x] Lifecycle-aware tests distinguish creation-time absence from retained
  M1.
- [x] Protected scope and complete verification are explicit.
- [x] Traceability is bidirectional with no gaps or orphans.
- [x] No unresolved Blocker, High, or Medium finding remains.

## Review findings

Any unresolved Blocker, High, or Medium finding prevents `REVIEWED`.

| Iteration | Finding | Severity | Resolution |
| ---: | --- | --- | --- |
| `1` | The draft counted `89` files but did not close the directory set or modes, so an extra empty directory could survive the importer. | Blocker | Added an exact manifest-derived `91`-directory inventory with `45` mode-`0700` and `46` mode-`0755` directories plus extra-descendant mutation tests. |
| `1` | The draft implied existing Sequence 13 verification should remain green after Sequence 14 changes current source, which would require weakening its frozen-source contract. | Blocker | Kept the old public verifier fail-closed and made the new `S13_M1_CAPTURED` importer the only post-transition historical verifier. |
| `1` | `TEST-141` currently treats Sequence 13 formal paths as permanently absent, so valid M1 progress would fail the full suite. | High | Split real-workspace retained-M1 assertions from disposable creation-time Sequence 14 absence assertions. |
| `1` | The preflight field was described as top-level `initialState`, while the actual canonical field is `namespaceInventory.initialState`. | Medium | Corrected the exact field path. |
| `1` | Minting a plain embedded catalog without preserving opaque provenance could weaken downstream `_registered_control_catalog()` checks. | High | Required full semantic validation before the existing private mint primitive and explicitly forbade changes to opaque catalog registration/provenance. |
| `2` | The zero-read language also forbade importing the separately authenticated current evidence module needed to validate and mint the opaque catalog, making the design internally contradictory. | High | Narrowed the prohibition to workspace legacy-member reads and bound the current validator module independently in Sequence 14 source authority. |
| `2` | The retained-M1 importer listed absent report through candidate paths but omitted the shared root path. | Medium | Required the exact Sequence 13 shared root absence as part of `S13_M1_CAPTURED`. |
| `2` | Retained PAX validation did not explicitly prohibit filesystem extraction, leaving an unnecessary path-traversal/write surface. | Medium | Required descriptor-only archive inspection with no extraction. |
| `3` | The retained Sequence 13 PAX archive and bundle were called exact but their member and namespace cardinalities were not stated. | Medium | Required `19` ordered archive members, `archivedPaths=19`, `namespaceLeafCount=3`, and the exact sealed bundle schema. |
| `4` | Rechecked the complete authority chain, lifecycle, namespace, command surface, package closure, acceptance criteria, tests, rollback, and protected scope. | None | No unresolved Blocker, High, or Medium finding remains. |

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `0.1-review-candidate` | 2026-07-29 | Initial Sequence 14 historical-stack comparator correction draft. |
| `0.2-review-candidate` | 2026-07-29 | Closed M1 directory inventory, historical verifier, lifecycle-aware test, exact field-path, and catalog-provenance findings. |
| `0.3-review-candidate` | 2026-07-29 | Closed validator-module authority, shared-root absence, and no-extraction findings. |
| `0.4-review-candidate` | 2026-07-29 | Closed retained source-archive and bundle cardinality findings. |
| `1.0-reviewed` | 2026-07-29 | Completed the fourth blocking review with no unresolved Blocker, High, or Medium finding. |

## Next handoff

With blocking review complete:

1. freeze this plan and canonical traceability ledger;
2. report exact SHA-256, size, and mode for both files;
3. wait for explicit maintainer approval before implementation.
