# Quant Radar UX-1B Task 9 Forward-Lifecycle Reauthentication Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.0-reviewed` |
| Status | Blocking review passed; implementation not started |
| Authorization | Repository maintainer authorized creation and review of a Sequence 11 correction plan |
| Author / plan reviewer | Codex |
| Approver | Repository maintainer |
| Audience | Maintainers, implementers, code reviewers, and evidence reviewers |
| Sequence | `11` |
| Capture recovery ID | `20260725T080000Z` |
| Continuation ID | `20260726T210000Z` |
| Descriptor/geometry correction ID | `20260727T030000Z` |
| Forward-lifecycle correction ID | `20260727T060000Z` |
| Forward-lifecycle Tier ID | `20260727T061000Z` |
| Imported predecessor | Exact Sequence 10 authorization, Tier, preflight, passed 117-capture migration report, and its complete Sequence 9/8 chain |
| Parent correction plan | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-descriptor-budget-correction.md` |
| Related ledger | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-forward-lifecycle-reauthentication-correction.traceability.yaml` |

## Executive summary

Sequence 10 successfully fixed descriptor planning and migration geometry.
Its formal Tier and preflight were published and freshly verified. The real
comparator then authenticated all `117` captures and created one passed report:

```text
.claude/ui_snapshots/ux1b/recovery/control-migration-20260725T080000Z.json
SHA-256 512bef01319a87aee1ec16c9d687232b92c518ab1ce4b76c443633304027e5cc
10236 bytes, mode 0600
```

The next command, `prepare-review`, failed before creating its packet:

```text
theme-handoff contract error: correction forward destination already exists
exit 3
```

The Sequence 10 preflight builder correctly requires every forward
destination to be absent at creation. Its reauthentication validator,
however, reconstructs the complete preflight from the current workspace.
That reconstruction repeats the creation-only absence check. The passed
migration report therefore invalidates the preflight that authorized its own
creation. `verify-descriptor-budget-correction-preflight` and
`prepare-review` become impossible immediately after the first successful
forward transition.

Sequence 11 separates two different facts:

1. **Initial namespace fact:** at Sequence 11 preflight creation, the exact
   Sequence 10 report exists and the remaining five forward destinations are
   absent.
2. **Current lifecycle fact:** later commands may observe one of six exact,
   monotonic forward-prefix states.

The immutable preflight stores only the initial fact. Reauthentication
reopens that stored value, verifies current source and exact predecessors,
then validates the current workspace against the closed prefix state machine.
It never rebuilds the initial snapshot from evolving output existence.

Sequence 11 does not rerun capture or comparison. It imports the exact passed
report as predecessor evidence, freezes corrected current source under a new
authority, creates the `117`-item review packet exactly once, and stops before
independent review intake.

## Problem statement

The current validator calls `_build_correction_preflight_value(...)` from
`_validate_correction_preflight_complete(...)`. The builder executes:

```python
eligible = _continuation_eligible_destinations(workspace_fd)
if any(item["exists"] for item in eligible):
    raise ContractViolation(
        "correction forward destination already exists"
    )
```

This check has valid creation semantics but invalid reauthentication
semantics. A preflight is an immutable record of creation conditions; it is
not a demand that authorized outputs remain absent forever.

The failure is distinct from the earlier Sequence 10 blockers:

- descriptor capacity is correct;
- the geometry adapter and frozen semantic comparator passed;
- the migration report exists exactly once and is valid;
- no review packet or later artifact exists.

Deleting the report, rewriting the Sequence 10 preflight, bypassing the
public dispatcher, or constructing a packet manually would erase or evade
formal evidence. None is authorized.

## Goals and success metrics

- Reopen the exact Sequence 10 Tier, preflight, and report without modifying
  their bytes or filesystem identity.
- Publish a separate Sequence 11 Tier/preflight over changed coordinator,
  tests, Make contract, and final authorization bytes.
- Require the exact passed report and the absence of the other five forward
  leaves when Sequence 11 preflight is created.
- Accept exactly six monotonic forward-prefix states after Sequence 11
  preflight; reject every hole, unsafe leaf, report substitution, or
  out-of-order artifact.
- Execute the real public `prepare-review` command and create/reopen exactly
  one packet with `117` items.
- Leave the external review intake, manual review, root candidate, and root
  absent after formal Sequence 11 execution.
- Preserve API, Streamlit, artifact-loader, selector, capture-stack,
  fail-soft, and theme-source behavior.

## Scope

### In scope

- Sequence 11 authorization parser and fixed four-ID authority chain.
- Sequence 11 bootstrap, preflight, and fresh verification.
- Exact historical import of Sequence 10 Tier/preflight/report.
- Static initial-forward snapshot validation.
- Closed current forward-prefix validation.
- Rebinding control-migration review and root-candidate handlers to
  Sequence 11.
- Rotating stale `TEST-080`/`TEST-090` construction-time absence assertions
  into historical-authority and lifecycle-aware checks without renumbering
  their stable test IDs.
- Root v2 binding through Sequence 11 → 10 → 9 → 8.
- Make targets and production-dispatch tests.
- Formal execution only through creation/reopen of the `117`-item packet.

### Non-goals

- No capture, recapture, or comparator rerun.
- No edit, delete, chmod, replacement, or regeneration of Sequence 8/9/10
  formal evidence.
- No manual review decision or external intake authored by the implementer.
- No root publication during Sequence 11 implementation or initial formal
  execution.
- No theme batch, production theme source, UI layout, API, provider, or
  artifact-loader behavior change.
- No general-purpose workflow engine or migration of unrelated lifecycle
  state machines.

## Glossary

| Term | Definition |
| --- | --- |
| Initial forward snapshot | Immutable preflight-time record: exact report present, five later leaves absent. |
| Current forward prefix | Current existence pattern of report, packet, intake, manual review, candidate, and root. |
| Hole | A later forward leaf exists while any required earlier leaf is absent. |
| Historical import | Exact byte/schema/link validation without asserting predecessor source projection equals current source. |
| Active source authority | Sequence 11 preflight source projections over the implementation that will execute later commands. |
| External intake | Independently authored manual-review JSON consumed by `publish-review`; never authored by the implementer. |

## Verified starting state

### Exact Sequence 10 predecessor

| Artifact | SHA-256 | Size | Mode |
| --- | --- | ---: | --- |
| Sequence 10 plan | `e18e56b80085313c63e5c33a4062055c444c21e88a0b7a17776cd3f79ad863cb` | `85406` | `0644` |
| Sequence 10 ledger | `9c81c3d9c0ae0c5e8eadaec8aaa60e4f1811838852cf042d8cb7076eff66b75b` | `10650` | `0644` |
| Sequence 10 authorization | `196690fbdb8fda9bb4ad9a279cbc5c00ece983409923de2679cfddf56a6c388e` | `4366` | `0644` |
| Sequence 10 Tier prechange | `d33497ff1bbf1c925d6179cff41e20ff5ee5d8d99c0eb2c21b1d9de0dd886eb2` | `3209` | `0600` |
| Sequence 10 Tier rollback | `09266a0f3cf1f000ec1f64c7c6f5c1f25c35367ed8c618009ae3c1fcb5e0ebfe` | `1636` | `0600` |
| Sequence 10 Tier owner | `d1da15b0d7b8c161e0b75341a94174c7350b1470f917ce0c940a56133b8e75cf` | `152` | `0600` |
| Sequence 10 Tier archive | `42f78c2779d12cdef7d0352aac9da0176eb74f34f39834248597a13cd10cb49a` | `2150400` | `0600` |
| Sequence 10 bundle manifest | `42287dc28400390d4dda7b347de017b85d07403decf2d4d731c2c29c73da0f99` | `1097` | `0600` |
| Sequence 10 lease | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Sequence 10 preflight | `032806f6b549d2b2a2bc89dbd04475be91afbcd9c11e38446b60853df64b585c` | `191041` | `0600` |
| Passed migration report | `512bef01319a87aee1ec16c9d687232b92c518ab1ce4b76c443633304027e5cc` | `10236` | `0600` |

Every owner-only record is a one-link regular file owned by current
`uid 501`, `gid 20`. The Sequence 10 preflight has `status:"passed"`. The
report has `status:"passed"`, `kind:"control-migration"`,
`comparedCaptures:117`, and
`migrationGeometryContract.actualGeometryAudit:"passed"`.

The Sequence 10 active package recorded by its preflight is:

| Path | SHA-256 | Size |
| --- | --- | ---: |
| `Makefile` | `25ca7124a51ba4b26726a2f193a978c6675f7503ac972012e059fcd5aca0d571` | `26069` |
| Sequence 10 authorization | `196690fbdb8fda9bb4ad9a279cbc5c00ece983409923de2679cfddf56a6c388e` | `4366` |
| `scripts/test_ui_ux_theme_handoff.py` | `0819feacbc00ee396d15ca05f92e5c9567a613036c9af8c3d0d97408248c83fc` | `1019459` |
| `scripts/ui_ux_theme_handoff.py` | `95d250a7bd2ac115052757c047e745c5a405bffad2f0bada80bd0f0295370945` | `1089487` |

These are historical source records after Sequence 11 implementation begins.
They must be validated against the exact Sequence 10 preflight and archive,
not compared to current Sequence 11 source.

### Exact forward namespace

| Index | Artifact | Starting state |
| ---: | --- | --- |
| `0` | Migration report | Exact predecessor above |
| `1` | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260725T080000Z.json` | Absent |
| `2` | `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260725T080000Z.json` | Absent |
| `3` | `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260725T080000Z.json` | Absent |
| `4` | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260725T080000Z.json` | Absent |
| `5` | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` | Absent |

No Sequence 11 path exists.

Two retained Sequence 10 tests now fail for a historical reason rather than
a source regression:

- `TEST-080` still requires all six forward paths to remain absent forever;
- `TEST-090` still requires the Sequence 10 Tier/preflight to remain absent.

Those assertions were valid before formal execution and became stale after
their own authorized artifacts were published. Sequence 11 must keep the test
IDs but remove only the expired current-workspace absence claims. Exact
Sequence 9/10 hashes, schemas, links, source projections, and external-review
rules remain mandatory.

The permanent suite recognizes exactly two Sequence 11 authority phases:

| Authority phase | Sequence 11 Tier/preflight | Forward state |
| --- | --- | --- |
| `S11_UNPUBLISHED` | Every Tier/preflight leaf absent | Exact `F0_REPORT` |
| `S11_PUBLISHED` | Complete exact Tier and valid preflight present | Any fully validated `F0..F5` |

A partial Sequence 11 Tier/preflight namespace always fails. `TEST-080`
validates only exact Sequence 9 history. `TEST-090` validates exact Sequence
10 history including its now-present Tier/preflight/report. `TEST-096`
validates the two-phase Sequence 11 authority/lifecycle contract.

## Authority and namespace design

### Fixed Sequence 11 namespace

```text
Correction ID:
  20260727T060000Z

Tier ID:
  20260727T061000Z

Lease:
  .claude/ui_snapshots/ux1b/recovery/.forward-lifecycle-correction-20260727T060000Z.lease

Preflight:
  .claude/ui_snapshots/ux1b/recovery/theme-handoff-forward-lifecycle-correction-preflight-20260727T060000Z.json

Tier bundle:
  .claude/ui_snapshots/ux1b/recovery/theme-handoff-forward-lifecycle-correction-prechange-20260727T061000Z/

Prechange:
  docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-forward-lifecycle-correction-prechange-seq11.json

Rollback:
  docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-forward-lifecycle-correction-rollback-seq11.json

Final authorization candidate:
  docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-forward-lifecycle-correction-seq11.md
```

All paths are currently absent. Bootstrap and preflight are create-once. A
collision is retained and reported; it is never deleted or overwritten.
Bootstrap may resume only a deterministic prefix of fully written,
byte-exact Tier leaves and create the missing suffix. A partial-byte,
out-of-order, or semantically different existing leaf blocks with no write.
An exact complete preflight may be reopened; an incomplete or different
preflight is retained and burns this correction ID rather than being repaired
or replaced.

### Authority precedence

```text
Sequence 11 forward-lifecycle authorization
        │
Sequence 10 descriptor/geometry authorization + Tier + preflight + report
        │
Sequence 9 continuation authorization + Tier + preflight
        │
Sequence 8 capture authority and passed terminal
        │
Accepted parent UX-1B plan
```

Sequence 11 imports predecessor source projections historically. Only its own
preflight may assert equality with current source.

### Package boundary

The Sequence 11 Tier freezes exactly:

```text
Makefile
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-forward-lifecycle-correction-seq11.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

The final authorization document is generated only after implementation and
verification stabilize these package bytes. Formal bootstrap remains blocked
until the maintainer accepts its exact whole-document SHA-256, size, and mode.
The authorization body is finalized before its body-digest constant is
embedded in the coordinator. Updating that constant is the last planned
source edit; all tests and source projections rerun afterward. The
authorization body must not contain current coordinator/test whole-file
hashes, avoiding an impossible self-referential fixed point.

## Lifecycle contract

### Initial snapshot

The Sequence 11 preflight stores a closed `initialForwardState`. Its report
field is an authority record with exactly `path`, `sha256`, `size`, and
`mode`. Creation and every historical reopen additionally require current
owner `uid`, current group `gid`, and `nlink:1`; inode/device values are
observations and are not portable authorization constants.

```json
{
  "schemaVersion": "quant-radar-ui-ux-forward-lifecycle-initial-state/v1",
  "report": {
    "path": ".claude/ui_snapshots/ux1b/recovery/control-migration-20260725T080000Z.json",
    "sha256": "512bef01319a87aee1ec16c9d687232b92c518ab1ce4b76c443633304027e5cc",
    "size": 10236,
    "mode": "0600"
  },
  "remainingDestinations": [
    {
      "path": ".claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260725T080000Z.json",
      "exists": false
    },
    {
      "path": ".claude/ui_snapshots/ux1b/review-intake/control-migration-20260725T080000Z.json",
      "exists": false
    },
    {
      "path": ".claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260725T080000Z.json",
      "exists": false
    },
    {
      "path": ".claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260725T080000Z.json",
      "exists": false
    },
    {
      "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json",
      "exists": false
    }
  ]
}
```

At creation:

- the report must match the exact FileRecord, canonical JSON, schema fields,
  geometry contract, and capture count;
- all remaining paths must be absent;
- source and predecessor projections must pass before publication.
- bootstrap must perform those checks after acquiring the already-existing
  global lock but before creating the Sequence 11 lease or any Tier leaf;
- preflight must repeat the checks before its first publication. A race or
  later-leaf appearance between bootstrap and preflight retains the Tier and
  blocks preflight without cleanup.

At reauthentication:

- validate stored `initialForwardState` against the exact expected constant;
- never replace it with a fresh existence snapshot;
- independently validate the current prefix described below.

### Current forward-prefix states

Let `1` mean an existing safe one-link regular file and `0` mean absent. Only
these patterns are valid:

| State | Report | Packet | Intake | Manual review | Candidate | Root | Permitted next action |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `F0_REPORT` | 1 | 0 | 0 | 0 | 0 | 0 | Prepare packet |
| `F1_PACKET` | 1 | 1 | 0 | 0 | 0 | 0 | Await external intake |
| `F2_INTAKE` | 1 | 1 | 1 | 0 | 0 | 0 | Publish review |
| `F3_REVIEW` | 1 | 1 | 1 | 1 | 0 | 0 | Prepare candidate if accepted |
| `F4_CANDIDATE` | 1 | 1 | 1 | 1 | 1 | 0 | Verify/publish root |
| `F5_ROOT` | 1 | 1 | 1 | 1 | 1 | 1 | Parent theme lifecycle |

Every other pattern is a contract failure. In particular:

- report absence or substitution always fails;
- an intake without a packet fails;
- a manual review without its retained intake fails;
- a candidate without manual review fails;
- a root without its candidate fails;
- every existing forward leaf must be a canonical-JSON, one-link regular file
  with exact mode `0600`, current `uid`, and current `gid`;
- symlink, directory, wrong owner/group, wrong mode, hardlink, or noncanonical
  JSON at an existing forward path fails.

Reauthentication has two explicit, nonrecursive layers:

1. `_classify_current_forward_prefix` proves the existence pattern,
   filesystem metadata, and canonical-JSON envelope.
2. `_validate_current_forward_semantics` validates every existing leaf in
   order:
   - report equals the exact imported Sequence 10 authority;
   - packet equals the pure packet reconstruction from the report and four
     immutable manifests;
   - intake is a valid exact manual-review value bound to that packet;
   - published manual review is byte-identical to intake, has a different
     inode, and remains accepted or rejected exactly as authored;
   - candidate equals a pure candidate reconstruction using the already
     authenticated Sequence 11 preflight context;
   - root equals the candidate's proposed contract and its pristine source
     boundary remains exact when required.

Candidate/root pure helpers accept the already authenticated preflight
record/value. They must not call preflight reauthentication recursively.
Every public Sequence 11 verifier therefore rejects a canonical but
semantically false newest leaf. Consuming commands retain their existing
command-specific checks as defense in depth.

Each command also has a closed start/postcondition:

| Command | Allowed start | Required postcondition |
| --- | --- | --- |
| `prepare-review` | `F0_REPORT` or exact-reopen `F1_PACKET` | `F1_PACKET` |
| external reviewer write | `F1_PACKET` | `F2_INTAKE` |
| control-migration `publish-review` | `F2_INTAKE` | `F3_REVIEW` |
| `prepare-handoff` | accepted `F3_REVIEW` or exact-reopen `F4_CANDIDATE` | `F4_CANDIDATE` |
| `verify-handoff-candidate` | `F4_CANDIDATE` or `F5_ROOT` | Same state |
| `publish-handoff` | `F4_CANDIDATE` or exact-reopen `F5_ROOT` | `F5_ROOT` |
| `verify-handoff` and parent theme lifecycle | `F5_ROOT` | `F5_ROOT` plus command-specific derived state |

Every coordinator-owned publication reclassifies the prefix after its
create-or-reopen operation and before reporting success. If an external actor
creates an out-of-order leaf during the transition, the newly written
create-once leaf is retained, the command returns a contract failure, and no
later authority is granted. No rollback/deletion attempts to repair the race.

### Command binding

New public commands:

```text
bootstrap-forward-lifecycle-correction
preflight-forward-lifecycle-correction
verify-forward-lifecycle-correction-preflight
```

They require all four IDs:

```text
--capture-recovery-id 20260725T080000Z
--continuation-id 20260726T210000Z
--correction-id 20260727T030000Z
--lifecycle-correction-id 20260727T060000Z
```

The same fourth ID becomes mandatory for the control-migration variants of:

```text
prepare-review
publish-review
prepare-handoff
verify-handoff-candidate
publish-handoff
```

Theme-batch/state/posttheme commands continue to consume the immutable root
without lineage flags. Their root verifier must require the Sequence 11
authorization, plan, ledger, preflight, and full predecessor chain.

`compare-control-migration` remains a Sequence 10 command and is not rerun.
Sequence 11 authorization must not grant capture or comparison authority.

The closed Sequence 11 allowed-command set is:

```text
apply-theme-batch
bootstrap-forward-lifecycle-correction
capture-posttheme
capture-theme-states
close-theme-states
finalize-theme
init-theme-batch
prepare-handoff
prepare-review
preflight-forward-lifecycle-correction
publish-handoff
publish-review
reconcile-posttheme
reconcile-theme-batch
reconcile-theme-states
seal-theme-batch
verify-forward-lifecycle-correction-preflight
verify-handoff
verify-handoff-candidate
verify-theme-batch-applied
verify-theme-batch-ready
```

The closed forbidden-command set is:

```text
bootstrap
bootstrap-continuation
bootstrap-descriptor-budget-correction
capture-task9
compare-control-migration
preflight
preflight-continuation
preflight-descriptor-budget-correction
reconcile-task9
verify-continuation-preflight
verify-descriptor-budget-correction-preflight
verify-preflight
```

Old commands remain available only under their historical authority and
collision/source-drift behavior. They are not granted by Sequence 11.

Argument presence is closed:

| Command family | Recovery | Continuation | S10 correction | S11 lifecycle correction | Batch/run |
| --- | --- | --- | --- | --- | --- |
| S11 bootstrap/preflight/verify | Required as `capture-recovery-id` | Required | Required | Required | Forbidden |
| Control-migration prepare/publish review | Required as `recovery-id` | Required | Required | Required | Forbidden |
| Prepare/verify/publish handoff | Required as `recovery-id` | Required | Required | Required | Forbidden |
| Theme-batch/state/posttheme review | Forbidden | Forbidden | Forbidden | Forbidden | Existing batch/run fields only |
| Theme lifecycle after root | Forbidden | Forbidden | Forbidden | Forbidden | Existing batch/run fields only |

Any duplicate, omitted, extra, or cross-kind flag is rejected before a
workspace operation.

## Dependencies and non-functional constraints

- The existing Sequence 10 global lock, descriptor wrapper, safe relative
  filesystem primitives, canonical JSON parser, exact review validators, and
  root v2 schema remain dependencies.
- The current host must retain the exact Sequence 8 runtime/capture evidence
  and current owner identity required by the imported chain.
- Forward-prefix work is bounded to the six fixed paths and performs no
  namespace scan. Bootstrap/preflight may reuse the existing bounded source
  projection traversal, but no network request, browser launch, capture, or
  child process is permitted.
- Existing descriptor-capacity planning and exact soft/hard-limit restoration
  remain unchanged.
- Every authority/forward read is descriptor-relative, no-follow,
  regular-file checked, size-bounded, and canonicalized before semantic use.

## Requirements and acceptance criteria

### Requirements

| ID | Requirement |
| --- | --- |
| `REQ-011` | Resume formal UX-1B handoff from the exact passed Sequence 10 report and reach the independent-review pause. |
| `CFR-046` | Keep preflight creation facts immutable and separate from evolving lifecycle facts. |
| `CFR-047` | Accept only the six exact monotonic forward-prefix states and reject every hole or unsafe leaf. |
| `CFR-048` | Preserve Sequence 8/9/10 evidence and give changed current source a separate Sequence 11 authority. |
| `CFR-049` | Keep manual review external, independent, exact, and mandatory before root preparation. |
| `CFR-050` | Preserve fail-soft API/UI/artifact behavior and existing theme/capture semantics. |

### Acceptance criteria

#### `AC-SEQ11-001` — exact predecessor import

Given the retained Sequence 10 authority, Tier, preflight, and report, when
Sequence 11 bootstrap/preflight runs, then every exact hash, size, mode,
schema, link, report count, geometry status, and historical source member is
reopened without modification.

#### `AC-SEQ11-002` — creation-only initial state

Given the exact report exists and the other five forward leaves are absent,
when Sequence 11 preflight is created, then it stores the exact closed initial
snapshot once. Later valid prefix growth does not rewrite or invalidate it.

#### `AC-SEQ11-003` — closed current prefix

Given any current forward-path existence pattern, when Sequence 11 preflight
is reauthenticated, then exactly `F0..F5` pass and every other pattern fails
before downstream publication.

#### `AC-SEQ11-004` — real packet transition

Given `F0_REPORT` and a valid Sequence 11 preflight, when the real public
`prepare-review` handler runs through the production parser, dispatcher,
descriptor wrapper, and publisher, then it creates or exactly reopens one
`117`-item packet and reaches `F1_PACKET`.

#### `AC-SEQ11-005` — independent review boundary

Given `F1_PACKET`, when formal Sequence 11 execution reaches its planned
pause, then intake, manual review, candidate, and root remain absent.
`publish-review` cannot succeed without an independently authored exact
intake.

#### `AC-SEQ11-006` — root lineage

Given an independently accepted intake and exact `F3_REVIEW`, when candidate
and root operations run in test-owned fixtures, then root v2 binds Sequence
11 → 10 → 9 → 8, current source projections, the exact report/packet/review,
and the unchanged parent theme boundary.

#### `AC-SEQ11-007` — failure propagation

Given busy, collision, unavailable, unsafe, out-of-order, rejected-review,
source-drift, or predecessor-drift conditions, when any Sequence 11 command
runs, then its exact nonzero exit propagates and no later leaf is written.

#### `AC-SEQ11-008` — compatibility and scope

Given the complete implementation diff, when regression and scope gates run,
then API/Streamlit/artifact fail-soft behavior, capture evidence, selectors,
theme source, and unrelated dirty worktree bytes remain unchanged.

## BDD scenario inventory

| ID | Priority | Given / When / Then |
| --- | --- | --- |
| `SC-SEQ11-001A` | HP | Exact S10 chain/report and no later leaves / bootstrap+preflight / S11 preflight passes. |
| `SC-SEQ11-001B` | NP | Any S10 predecessor byte or metadata differs / bootstrap or preflight / fail before write. |
| `SC-SEQ11-001C` | NP | Report count, kind, status, geometry audit, or digest differs / preflight / fail before write. |
| `SC-SEQ11-002A` | HP | Valid initial state / preflight creation / exact initial snapshot stored. |
| `SC-SEQ11-002B` | BP | Packet later exists exactly / reauthenticate / stored initial snapshot remains valid and unchanged. |
| `SC-SEQ11-002C` | NP | Any later leaf exists before preflight creation / preflight / reject collision. |
| `SC-SEQ11-003A` | HP | Each `F0..F5` pattern / reauthenticate / pass prefix safety. |
| `SC-SEQ11-003B` | NP | Any non-prefix pattern / reauthenticate / fail before command-specific write. |
| `SC-SEQ11-003C` | EP | Existing leaf is symlink, directory, hardlink, wrong-owner, or permissive / reauthenticate / fail closed. |
| `SC-SEQ11-003D` | NP | Exact report disappears or changes / any command / fail without recreation. |
| `SC-SEQ11-004A` | HP | `F0` and valid source / real prepare-review / exact 117-item packet created. |
| `SC-SEQ11-004B` | BP | Exact packet already exists / prepare-review / reconcile exact bytes without overwrite. |
| `SC-SEQ11-004C` | NP | Existing packet bytes differ / prepare-review / collision/contract exit and no later write. |
| `SC-SEQ11-004D` | NP | Parser lacks/wrong fourth ID / prepare-review / reject before operation. |
| `SC-SEQ11-005A` | HP | Packet created / formal execution / stop at missing intake. |
| `SC-SEQ11-005B` | NP | Intake absent / publish-review / fail without manual review. |
| `SC-SEQ11-005C` | NP | Intake does not exactly bind packet/items/prompt / publish-review / reject. |
| `SC-SEQ11-005D` | BP | Exact rejected intake / publish-review then prepare-handoff / retain rejection and refuse candidate. |
| `SC-SEQ11-006A` | HP | Accepted exact review chain in test root / candidate+root / root v2 exact. |
| `SC-SEQ11-006B` | NP | Root substitutes S10 directly for S11 / verify / reject. |
| `SC-SEQ11-006C` | NP | Current theme preimage differs / pristine root verify / reject. |
| `SC-SEQ11-007A` | EP | Lock/lease busy / public command / exact busy exit, zero forward writes. |
| `SC-SEQ11-007B` | EP | Descriptor capacity unavailable or restore fails / public command / exact unavailable or contract exit. |
| `SC-SEQ11-007C` | NP | S11 source projection drifts after preflight / any downstream command / reject. |
| `SC-SEQ11-008A` | HP | Complete diff / fail-soft and UI regression suites / all pass. |
| `SC-SEQ11-008B` | NP | Diff touches production UI/API/provider/evidence source / scope gate / block completion. |
| `SC-SEQ11-008C` | BP | Permanent suite runs before or after valid prefix growth / lifecycle-aware historical tests / pass without weakening exact predecessor checks. |

## Implementation map

| ID | Planned implementation |
| --- | --- |
| `IMPL-070` | Sequence 11 constants, fixed IDs, authorization grammar, exact predecessor refs, package/cardinality declarations, and disjoint paths. |
| `IMPL-071` | Historical Sequence 10 importer for authorization, Tier archive/manifest/owner/rollback/lease, preflight, and passed report. |
| `IMPL-072` | Sequence 11 Tier bootstrap, owner-only archive, rollback record, lock/lease, and create-once publication. |
| `IMPL-073` | Sequence 11 preflight builder/validator with exact initial snapshot and active current-source projections. |
| `IMPL-074` | Nonrecursive current forward-prefix classifier and unsafe/hole rejection. |
| `IMPL-075` | Public parser/dispatcher and four-ID argument validation for Sequence 11 and control-migration/root commands. |
| `IMPL-076` | Review packet transition and root v2 builders/verifiers rebound to Sequence 11 authority; control-migration publication returns the exact accepted/rejected decision from the same descriptor operation. |
| `IMPL-077` | Make variable/targets/guards with exact nonzero propagation and no comparator rerun. |
| `IMPL-078` | Red-first, production-path, mutation, root-chain, compatibility, scope, and formal-pause tests. |

## Test map

| ID | Test obligation |
| --- | --- |
| `TEST-096` | Reopen exact Sequence 10 authority/Tier/preflight/report; validate only `S11_UNPUBLISHED` or complete `S11_PUBLISHED`, never a partial authority namespace. |
| `TEST-097` | Sequence 11 authorization grammar, four-ID parsing, namespace disjointness, package set, and cardinality closure. |
| `TEST-098` | Bootstrap/preflight crash/collision matrix, initial snapshot exactness, source freeze, and historical import. |
| `TEST-099` | Reauthentication after each valid prefix growth without rebuilding initial state; current-source drift rejection. |
| `TEST-100` | Exhaustive 64-pattern prefix truth table plus symlink/directory/hardlink/owner/mode/report and canonical-but-semantic leaf mutations. |
| `TEST-101` | Real production `prepare-review` creates/reopens the exact 117-item packet from the formal-shaped report. |
| `TEST-102` | External intake separation, exact accepted/rejected intake and public-status behavior, same-operation result propagation, and no self-approval. |
| `TEST-103` | Candidate/root v2 chain through Sequence 11 → 10 → 9 → 8 and pristine-source rejection. |
| `TEST-104` | Public registry, parser, Make target, fourth-ID guards, forbidden comparator/capture authority, and exact formal pause. |
| `TEST-105` | Full recovery, fail-soft API/UI/artifact, syntax, Python 3.10, dependency, dirty-scope, and immutable-evidence regressions. |

## Affected files

### Planned edits

```text
Makefile
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-forward-lifecycle-reauthentication-correction.md
docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-forward-lifecycle-reauthentication-correction.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-forward-lifecycle-correction-seq11.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

The final authorization document is an implementation output and remains
unaccepted until separately reviewed by the maintainer. Journal/activity
changes are administrative and must not enter formal source projections.

### Read-only protected paths

```text
scripts/ui_ux_evidence.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_browser_worker.py
scripts/ui_ux_isolation.py
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
all Sequence 8/9/10 authorization, Tier, preflight, lifecycle, capture, and report artifacts
all production UI/API/provider/theme-source files
```

## Implementation sequence and gates

### Phase 0 — reopen exact starting state

- Reopen every Sequence 10 artifact and archive member listed above.
- Reopen the report and verify its exact semantic/geometry registration.
- Verify packet, intake, manual review, candidate, root, and all Sequence 11
  paths are absent using a one-time pre-implementation gate, not a permanent
  real-workspace test.
- Fingerprint planned source preimages and unrelated dirty paths.
- Reproduce the current `prepare-review` and old verify failure read-only.
- Reproduce the stale `TEST-080`/`TEST-090` failures and classify only their
  construction-time absence assertions as superseded.

**Gate:** any predecessor drift, report mismatch, unexpected later leaf,
unsafe metadata, or unexplained dirty-path change blocks implementation.

### Phase 1 — red tests

- Add `TEST-096..105`.
- Retain stable IDs `TEST-080` and `TEST-090`, but make them validate exact
  historical authority plus the active lifecycle state instead of permanent
  construction-time absence.
- Prove packet preparation fails because reauthentication repeats the
  creation-only absence check.
- Prove a naive removal of the absence check would accept holes and unsafe
  current leaves.
- Prove the real parser/dispatcher lacks Sequence 11 authority.

**Gate:** failures must identify missing Sequence 11 behavior. Fixture/setup
failure is not acceptable red evidence.

### Phase 2 — authority and historical import

- Implement `IMPL-070..073`.
- Import Sequence 10 exact bytes and source archive historically.
- Require exact report present and five later leaves absent at Sequence 11
  preflight creation.
- Acquire the existing global lock, authenticate all preconditions, and only
  then create the Sequence 11 lease/Tier. Do not let a lock helper create a
  lease before predecessor/forward validation.
- Freeze current Sequence 11 source separately.
- Keep all formal Sequence 11 paths absent while source changes.

**Gate:** predecessor mutation, current-source mutation, wrong IDs, namespace
collision, and every Tier/preflight crash boundary fail closed.

### Phase 3 — lifecycle and downstream binding

- Implement `IMPL-074..077`.
- Validate all `64` existence patterns: six pass, `58` fail.
- Keep both prefix classification and full current-state semantic validation
  nonrecursive.
- Reject canonical but semantically invalid packet, intake, manual review,
  candidate, and root values in the public preflight verifier itself.
- Enforce the command start/postcondition table and reclassify after every
  coordinator-owned publication.
- Rebind packet, control-migration review, candidate, root, and pristine root
  verification to Sequence 11.
- Make control-migration `publish-review` return the validated manual-review
  decision from the same descriptor operation. Public status must be
  `accepted` or `rejected` exactly; a rejected publication is retained but
  cannot authorize a candidate. Do not perform a second root/review read to
  derive that status.
- Preserve command-specific exact artifact validation.
- Do not alter comparator, captures, evidence module, or report.

**Gate:** production-shaped test flow reaches the packet and separately
exercises accepted/rejected review and root in test-owned namespaces only.

### Phase 4 — complete verification and review

- Complete `IMPL-078`.
- Run focused and complete recovery/fail-soft/static gates.
- Compare actual diff to this plan and preimages.
- Review all findings for runtime errors, lifecycle holes, self-approval,
  evidence mutation, source drift, missing tests, and maintainability.
- Generate the final Sequence 11 authorization candidate only after source
  and tests stabilize.

**Gate:** all checks pass, test-owned namespaces are removed, report remains
exact, later formal leaves remain absent, and no blocking review finding
remains.

### Phase 5 — freeze Sequence 11 authority

- Report final authorization whole-document SHA-256, size, and mode.
- Obtain explicit maintainer acceptance of those exact bytes.
- Bootstrap the Sequence 11 Tier exactly once.
- Publish and freshly verify the Sequence 11 preflight.
- Reopen Sequence 10 artifacts and report again.

**Gate:** accepted Sequence 11 preflight freezes final source. Any later
source edit requires a new reviewed correction.

### Phase 6 — formal packet and mandatory pause

- Run real `prepare-review` with all four fixed IDs.
- Reopen the exact packet and require `117` items.
- Reauthenticate Sequence 11 again in state `F1_PACKET`.
- Stop without creating or editing external intake.

**Gate:** report and packet exist exactly once. Intake, manual review,
candidate, and root remain absent.

### Phase 7 — later external/root work

- Only an independent reviewer may create the exact intake.
- Publish/reopen the manual review.
- Continue only if every item is accepted and no blocking finding remains.
- Prepare/verify/publish root v2 and run pristine verification.
- Resume parent theme lifecycle under separate batch/run IDs.

**Gate:** this phase is outside initial Sequence 11 execution and requires
external evidence.

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
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Changed Python must pass
`ast.parse(source, feature_version=(3, 10))`. Tests must assert the frozen
`scripts/ui_ux_evidence.py` SHA remains
`3ae2a02b519a70f4e8ef146c486f0ad4cd306718ad5429ec20dd8ccf951f009a`.

Future formal command shape:

```bash
make ui-ux1b-theme-handoff-forward-lifecycle-correction-bootstrap \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z \
  UX1B_LIFECYCLE_CORRECTION_ID=20260727T060000Z

make ui-ux1b-theme-handoff-forward-lifecycle-correction-preflight \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z \
  UX1B_LIFECYCLE_CORRECTION_ID=20260727T060000Z

make ui-ux1b-theme-handoff-forward-lifecycle-correction-verify \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z \
  UX1B_LIFECYCLE_CORRECTION_ID=20260727T060000Z

make ui-ux1b-control-migration-review-prepare \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z \
  UX1B_CORRECTION_ID=20260727T030000Z \
  UX1B_LIFECYCLE_CORRECTION_ID=20260727T060000Z
```

The comparator Make target is intentionally absent from this formal sequence.

## Failure and pause policy

- Never remove or replace the passed report to make an absence check pass.
- Never rewrite Sequence 10 preflight or treat its source projection as
  current after Sequence 11 edits.
- Never accept a non-prefix current forward state.
- Never let generic prefix checking substitute for command-specific schema,
  hash, lineage, or decision validation.
- Never place a transitional real-workspace absence assertion in the
  permanent suite. Test absence matrices in test-owned roots and enforce
  formal initial absence once before bootstrap.
- Never author formal external intake in implementation or test code.
- Never promote a rejected review to accepted.
- Never report a rejected control-migration review as public status
  `accepted`; publication success and reviewer decision are distinct facts.
- Every namespace collision and unknown/unsafe artifact is retained for
  diagnosis; no cleanup authority is implied.
- Every nonzero operation result is checked before another authority read or
  downstream write.
- Formal work stops after the packet until independent intake exists.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Removing the absence check permits arbitrary future files | Replace it with the exhaustive six-state prefix validator and command-specific exact validators. |
| Rebuilding initial state repeats the bug | Store and validate a fixed initial snapshot; classify current state separately. |
| Generic validation recurses through candidate/root builders | Validate prefix ordering/metadata generically; keep exact newest-leaf semantics in the consuming command. |
| Sequence 10 source is silently treated as current | Import exact S10 preflight/archive historically; freeze changed source only under S11. |
| Report is rerun or overwritten | Exclude comparator from S11 allowed commands and require the exact existing report as predecessor. |
| Early or fabricated review self-approves the flow | Require packet before intake, exact intake-to-packet binding, independent reviewer type, and mandatory formal pause. |
| New fourth ID is omitted from one public path | Close parser, Make, registry, handler, and root tests over every control-migration/root command. |
| Valid rejected review is publicly mislabeled accepted | Return the exact validated decision from the same descriptor operation and test rejected publication plus candidate refusal. |
| Root still binds S10 directly | Require root v2 authority/plan/ledger/preflight fields to bind S11 and traverse S10 historically. |
| Permanent tests fail after authorized lifecycle progress | Keep stable historical test IDs but replace construction-time absence with lifecycle-aware validation; use test-owned roots for absence matrices. |
| Dirty worktree is damaged | Edit only planned paths, fingerprint before/after, never reset/clean, and preserve unrelated changes. |
| API/UI becomes more brittle | Keep production API/UI files read-only and run explicit fail-soft regressions. |

## Rollback

- Before Sequence 11 Tier publication, revert only planned Sequence 11 source
  and new documents if explicitly authorized; preserve unrelated dirty work.
- After Sequence 11 Tier/preflight publication, retain all evidence. Do not
  delete, overwrite, or regenerate it.
- Before root publication, rollback is refusing forward work. No production
  theme source has changed.
- Sequence 8/9/10 authorities and the passed report are never rollback
  targets.

## Blocking-issue review

### Review iteration 1 — authority and command surface

- **Finding:** The first candidate did not list the exact Sequence 10
  plan/ledger, did not close the Sequence 11 allowed/forbidden command sets,
  and left forward-leaf metadata plus cross-kind fourth-ID presence
  ambiguous.
- **Resolution:** Add exact plan/ledger refs, fixed command sets, exact
  `0600`/owner/group/one-link/canonical-JSON rules, and the complete
  command-family argument matrix.
- **Status:** Closed.

### Review iteration 2 — transition order and namespace races

- **Finding:** A valid prefix alone did not state which lifecycle phases each
  command may consume, bootstrap could create its lease before validating the
  report/absences, and an out-of-order leaf could race a create-once
  publication.
- **Resolution:** Require predecessor/forward validation before the first
  Sequence 11 write, add the exact command start/postcondition table, and
  reclassify the prefix after every coordinator-owned publication. Raced
  evidence is retained but grants no forward authority.
- **Status:** Closed.

### Review iteration 3 — semantic false-green and authorization fixed point

- **Finding:** Metadata/prefix validation alone could let the public
  preflight verifier report success for canonical but semantically false
  packet/intake/candidate bytes. Authorization finalization order also needed
  to avoid a source/document self-reference.
- **Resolution:** Split nonrecursive prefix classification from ordered exact
  semantic validation of every existing leaf. Pass the already authenticated
  preflight into pure candidate/root builders. Finalize the authorization
  body first, embed only its body digest as the last source edit, then rerun
  every gate; prohibit current coordinator/test hashes in the body.
- **Status:** Closed.

### Review iteration 4 — stale construction-time tests

- **Finding:** `TEST-080` and `TEST-090` permanently assert namespaces that
  were supposed to be absent only before Sequence 10 formal execution. Both
  now fail after the valid preflight/report publications, and repeating that
  pattern in `TEST-096` would make the suite fail again after the packet.
- **Resolution:** Preserve stable IDs and exact historical checks, replace
  only expired absence assertions with Sequence 11 lifecycle validation, and
  confine exhaustive absence tests to test-owned roots plus one-time
  pre-bootstrap gates.
- **Status:** Closed.

### Review iteration 5 — permanent phases and rejected-review truth

- **Finding:** Lifecycle-aware permanent tests still needed a closed
  unpublished/published authority model. The existing control-migration
  publisher also reports public status `accepted` even for a valid rejected
  review, and the first NFR wording incorrectly prohibited the existing
  bounded source projection traversal.
- **Resolution:** Define exactly `S11_UNPUBLISHED` and complete
  `S11_PUBLISHED`, reject partial authority namespaces, require public review
  status to equal the same-operation validated decision, and bound only the
  six-path forward classifier while retaining existing source projection.
- **Status:** Closed.

### Review iteration 6 — crash recovery, traceability, and execution boundary

- **Finding:** Tier crash recovery and incomplete-preflight disposition were
  implied rather than binary. The initial-state JSON omitted its report mode,
  and final review still needed to prove traceability and formal-pause
  closure.
- **Resolution:** Permit only deterministic exact Tier-prefix completion;
  retain/block partial-byte or wrong leaves; treat an incomplete preflight as
  a burned ID; serialize the exact report mode/full destination paths; verify
  all reciprocal ledger edges, `6/8/9/10` node counts, `27` BDD scenarios,
  `10000` basis-point coverage, zero gaps/orphans, and the packet-only formal
  stop.
- **Status:** Closed.

No unresolved blocking issue remains in the reviewed plan. This review
authorizes neither implementation nor formal publication.

## Review checklist

- [x] Exact S10 predecessor and report are sufficient to start S11.
- [x] Initial snapshot and current prefix have separate semantics.
- [x] All 64 existence patterns have a binary oracle.
- [x] Generic validation cannot recurse or self-approve.
- [x] Current source receives distinct S11 authority.
- [x] Every downstream public command binds the fourth ID or immutable root.
- [x] Comparator/capture authority is absent.
- [x] External review remains independent.
- [x] Affected files, tests, risks, rollback, and formal pause are explicit.
- [x] Traceability is closed and bidirectional.
- [x] No unresolved blocker remains.

## Traceability summary

The sibling ledger must bind `REQ-011`, `CFR-046..050`,
`AC-SEQ11-001..008`, `IMPL-070..078`, and `TEST-096..105` bidirectionally,
with `10000` basis-point structural coverage, no gaps, and no orphans.
Planning verdicts remain `NOT_TESTED`; implementation/test execution is not
claimed by this document.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `1.0-reviewed` | 2026-07-27 | Closed six distinct review findings covering authority surface, transition/race ordering, semantic false-greens, stale permanent tests, rejected-review truth, and crash/traceability boundaries. |
| `0.1-review-candidate` | 2026-07-27 | Initial Sequence 11 plan separating immutable initial namespace facts from monotonic current forward lifecycle. |

## Next handoff

Review this plan for blocking issues. If it passes, implementation still
requires a separate explicit maintainer instruction. Formal bootstrap later
requires acceptance of the final authorization candidate's exact bytes.
