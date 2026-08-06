# UX-1B Sequence 13 Terminal Import and Render/Manifest Contract Correction

## Document info

| Field | Value |
| --- | --- |
| Status | `REVIEWED — IMPLEMENTATION NOT STARTED` |
| Version | `1.0-reviewed` |
| Date | `2026-07-29` |
| Owner | Maintainer |
| Plan path | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.md` |
| Traceability path | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.traceability.yaml` |
| Correction ID | `20260729T030000Z` |
| Tier ID | `20260729T031000Z` |
| Capture ID | `20260729T040000Z` |
| Formal stop | `M3_PACKET` |

This document is a correction plan, not implementation or formal execution
authority. No source edit, capture retry, report, packet, intake, review,
candidate, root, or theme mutation is authorized until this plan and its
sibling traceability ledger pass blocking review and the maintainer later
accepts a separate Sequence 13 authorization document by exact SHA-256,
byte size, and mode.

## Authority and purpose

Sequence 12 was implemented and locally gate-verified, then formally
authorized by the exact authorization document:

```text
path: docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-seq12.md
sha256: cdf41d4e905e89fa8a34f6e33a0d780fdcecf7c1c81de1bec9c4f1b586cbdb95
size: 6252
mode: 0644
```

Its Tier and preflight were published successfully. The first formal focused
capture then failed safely after publishing one partial PNG/render pair. The
failure was retained under the Sequence 12 capture namespace; it MUST NOT be
deleted, overwritten, repaired in place, or treated as a passed capture.

The two directly observed causes are:

1. `scripts/ui_ux_evidence.py::publish_finalized_capture()` finalizes the
   authenticated root render sidecar as
   `quant-radar-ui-ux-render/v2`, but its returned artifact record always
   claims `quant-radar-ui-ux-render/v1`. The immediately following
   `verify_capture_artifacts()` correctly rejects the mismatch.
2. `scripts/ui_ux_evidence.py::_manifest_bytes()` intentionally writes
   canonical manifests with exactly one terminal LF, while
   `scripts/ui_ux_theme_handoff.py::_classify_capture_binding_forward_prefix()`
   routes every forward leaf through `_strict_json_bytes()`, which accepts
   only compact canonical JSON without that LF. A real passed Sequence 12
   manifest would therefore fail the coordinator even after the render claim
   is fixed.

Review of the reopen path found a third occurrence of the first contract
error: `_validate_open_capture_bytes()` reopens a v2 render correctly but
materializes its normalized `renderSidecar.schemaVersion` as v1. Sequence 13
must fix both artifact-record projection sites, while leaving deliberate
v2-to-v1 legacy semantic projections unchanged.

The purpose of Sequence 13 is to:

- import the exact terminal Sequence 12 failure and partial pair as immutable
  predecessor evidence;
- correct render artifact-record schema fidelity at publication and manifest
  reauthentication;
- accept the evidence module's exact canonical manifest envelope without
  weakening JSON strictness for other forward artifacts;
- publish a distinct Sequence 13 capture-stack and source authority;
- perform one new, disjoint `36` logical / `44` root capture;
- preserve the reviewed `81 + 44 = 125` comparison and packet-only pause.

## Scope

### In scope

- Exact import and descriptor-safe inventory of the Sequence 12 authorization,
  Tier, preflight, failed manifest, and retained partial artifact pair.
- A schema-fidelity helper derived from the authenticated finalized render
  sidecar document, not from a caller-provided schema string.
- Correct v1/v2 artifact claims from `publish_finalized_capture()`.
- Correct v1/v2 normalized claims from `_validate_open_capture_bytes()` and
  manifest-bundle reauthentication.
- A path-specific canonical manifest parser that permits exactly the evidence
  module's one terminal LF and no other whitespace relaxation.
- A distinct Sequence 13 capture-stack contract and snapshot-runner selection.
- A new Sequence 13 Tier, preflight, forward namespace, coordinator handlers,
  CLI arguments, and Make targets.
- Capture, reconcile, comparison, and review-packet fixture coverage through
  the mandatory `M3_PACKET` stop.
- Fail-soft API/UI, legacy v1, runtime, source-scope, descriptor, syntax,
  dependency, and dirty-worktree regression gates.

### Out of scope

- Any production `ui/` or `api/` behavior, styling, layout, control, selector,
  provider, data, configuration, dependency, or theme-source change.
- Editing the selection fixture, browser worker, isolation layer, control
  catalog, viewport catalog, root expansion, historical capture stack, or any
  Sequence 8–12 evidence.
- Reusing, resuming, or retrying the burned
  `postcontrol-controls-20260728T010000Z` namespace.
- Promoting the retained Sequence 12 partial PNG/render pair into a new
  manifest or comparison.
- External review intake, manual review, handoff candidate, root publication,
  semantic-theme batches, or post-theme work.
- Broadening `_strict_json_bytes()` for ordinary JSON artifacts.
- Replacing every `RENDER_SCHEMA` occurrence. Intentional legacy semantic
  projections remain v1.

## Non-goals

- Sequence 13 does not prove that no later environmental failure can occur.
- Sequence 13 does not alter the `36/44/88/89`, `81/44/125`, or nested
  `81/36/117` contracts accepted in Sequence 12.
- Sequence 13 does not reinterpret a failed manifest as a forward-state leaf.
- Sequence 13 does not make malformed, partial, duplicate-key, non-finite,
  whitespace-padded, or unsafe JSON acceptable.
- Sequence 13 does not claim completion before a later formal capture and
  independent review actually pass.

## Imported immutable predecessor

### Sequence 12 accepted authority and Tier

Every row below is reopened by descriptor, exact SHA-256, size, mode, owner,
group, link count, and safe ancestor identity. A missing, extra, linked,
replaced, or changed row is a blocker.

| Role | Path | SHA-256 | Bytes | Mode |
| --- | --- | --- | ---: | --- |
| Authorization | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-seq12.md` | `cdf41d4e905e89fa8a34f6e33a0d780fdcecf7c1c81de1bec9c4f1b586cbdb95` | `6252` | `0644` |
| Lease | `.claude/ui_snapshots/ux1b/recovery/.capture-binding-correction-20260728T000000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-prechange-seq12.json` | `e5610ac0a68ddfa63f5ace5390df500356ba250285350c547ebcf395e76c35f9` | `6638` | `0600` |
| Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-rollback-seq12.json` | `b41880e39be024a1a8080fe14e45326aec871d29720520b33bad934f496772d8` | `3278` | `0600` |
| Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-prechange-20260728T001000Z/.quant-radar-theme-handoff-capture-binding-correction-owner` | `19d334792c0c0919e6abf5e82522d5e8f2c384419a19010188448b799d2f7f54` | `135` | `0600` |
| Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-prechange-20260728T001000Z/prechange-files.tar` | `a44fede42c87493568a397e2eaea5cd5c515a858c5125a8959194296fc29ea39` | `4167680` | `0600` |
| Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-prechange-20260728T001000Z/bundle-manifest.json` | `246a4c66e7cefcb8a4e8d9c4c568e8b71a5530e8dc2d87c72b15eb7d3a5833d9` | `1311` | `0600` |
| Preflight | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-preflight-20260728T000000Z.json` | `595779fdb9ef91274aa0580dc37ccf5f2a94d82daf8de600ab0909c4e75b32b6` | `69318` | `0600` |
| Capture stack | `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json` | `6e625cbb4d3e9b14e24dfc10a359d3047dbda59f00ff441e5449c5169ac6bf90` | `5429` | `0600` |

The preflight must reopen as `status=passed`, correction
`20260728T000000Z`, tier `20260728T001000Z`, capture
`20260728T010000Z`, initial state `R0_READY`, root expansion
`13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca`,
capture-stack digest
`5cc960797587028ea31388c6556c569ffe75455b1d852bbf6d3e733849f5af9d`,
and runtime tree
`9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75`.

### Sequence 12 terminal failure tree

The retained root has the exact closed inventory below. No other descendant,
symlink, hardlink, socket, device, or non-regular leaf is allowed.

```text
postcontrol-controls-20260728T010000Z/                  directory 0700
  captures/                                             directory 0755
    ai-chat-settings-controls/                          directory 0755
      desktop/                                          directory 0755
        root-01/                                        directory 0700
          capture.png                                   regular 0600
          render.json                                   regular 0600
  manifest.json                                         regular 0600
```

| Role | Path | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| Failed manifest | `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260728T010000Z/manifest.json` | `dd1c5e49bce89ded07a2e86a8922ccee14f4cc8549c1edbb6bafcb0107ad1f25` | `546` |
| Partial PNG | `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260728T010000Z/captures/ai-chat-settings-controls/desktop/root-01/capture.png` | `6a5324dc6d26e7f41f1f0e60eea3adcdddd0d3cef26900077bbc07dde881edef` | `134813` |
| Partial render | `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260728T010000Z/captures/ai-chat-settings-controls/desktop/root-01/render.json` | `5d5486479ebaf738a94fa858107ad8ddea02b02af10131d598fdc1bdf2928112` | `181743` |

The failed manifest is parsed with the evidence manifest envelope and must
equal its exact bytes, including exactly one terminal LF. It must have exactly:

```text
schemaVersion = quant-radar-ui-ux-evidence/v1
status = failed
plannedLogicalRequests = 36
plannedRootCaptures = 44
expectedCaptureCount = 44
completedLogicalRequests = 0
completedRootCaptures = 0
rootExpansionSha256 = 13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca
error.type = EvidenceContractError
error.message = capture render schema differs from its record
```

The partial render must reopen as canonical
`quant-radar-ui-ux-render/v2`, bind logical capture
`ai-chat-settings-controls/desktop`, root capture
`ai-chat-settings-controls/desktop/root-01`, ordinal `1`, selector
`.st-key-ai_chat_mode`, viewport `desktop/1440x900`, and the exact root
expansion digest. Its PNG digest and `1440x900` dimensions must be checked
directly. These two leaves are diagnostic predecessor evidence only: the
failed manifest has no passed `captures` row and reports zero completed roots,
so neither leaf may satisfy any Sequence 13 capture or report cardinality.

### Terminal import classification

The importer returns a typed `S12_TERMINAL_FAILED` record only after all
authority, Tier, preflight, directory inventory, failed-manifest semantics,
partial-pair hashes, render v2 identity, PNG dimensions, and later-namespace
absences agree.

Historical and live validation are deliberately separate:

- the importer authenticates the exact known Sequence 12 file hashes and
  internal cross-references as historical facts;
- it authenticates the archived Sequence 12 source package from the retained
  tar/bundle, not by rebuilding that package from current source;
- it validates the preflight's recorded source/runtime/namespace as immutable
  creation-time values, not as claims about the current worktree;
- it MUST NOT call
  `_validate_capture_binding_tier_complete()`,
  `_validate_capture_binding_preflight_complete()`, or
  `_reauthenticate_capture_binding_preflight()` in a mode that rebuilds
  Sequence 12 authority from current source or routes the failed manifest
  through the old `R0..R7` forward classifier;
- current Sequence 13 source, runtime, stack, and namespace are measured
  independently and bound only in the new Sequence 13 preflight.

The exact whole-file hashes make the historical import fail closed without
requiring old source bytes to remain the current source. This separation is
mandatory: the planned evidence/coordinator changes necessarily differ from
the source projection frozen by the passed Sequence 12 preflight.

It must reject:

- an ordinary `R1_CAPTURE` or any Sequence 12 forward state;
- a manifest altered from `failed` to `passed`;
- a partial pair referenced as a passed capture;
- missing or additional descendants;
- inode, owner, group, mode, nlink, ancestor, byte, or digest drift;
- any Sequence 12 report, packet, intake, manual review, candidate, or root.

## Render schema-fidelity correction

### Accepted render schemas

The evidence module continues to accept exactly:

```text
quant-radar-ui-ux-render/v1
quant-radar-ui-ux-render/v2
```

No caller may supply or override the artifact claim schema. The claim is
derived from the descriptor-authenticated, canonical finalized sidecar that
is actually published or reopened.

### Single authoritative derivation

Add one closed helper in `scripts/ui_ux_evidence.py` whose input is the
already validated finalized render document and whose output is exactly its
accepted `schemaVersion`. The helper:

- requires a mapping with an exact supported schema;
- never defaults to v1;
- never accepts a separate expected-schema argument;
- fails before a record is returned if the schema is absent or unsupported.

Use that helper in both record-projection sites:

1. `publish_finalized_capture()` after `finalize_render_sidecar()` has produced
   canonical bytes and those exact bytes have been decoded/validated;
2. `_validate_open_capture_bytes()` after
   `_require_finalized_render_sidecar()` has validated the reopened bytes.

Both sites must compare the derived actual schema with any existing artifact
claim. Publication mints the claim from the actual document.
`_validate_open_capture_bytes()` must reject a persisted claim that differs
from the actual document before it materializes a normalized record; it
cannot silently repair or normalize a false claim.

The returned/materialized `renderSidecar.schemaVersion` must equal the actual
sidecar document in all three stages:

```text
publish record -> immediate verify -> manifest freeze/reauthenticate
```

### Deliberate legacy projections remain v1

The following v1 constructions are semantic adapters, not artifact records,
and must remain byte-compatible:

- the base document used while validating a root render;
- the case-semantic projection converted for the frozen legacy comparator;
- the general canonical v1 render projection;
- root migration semantic documents;
- root discovery semantic documents.

Tests must identify these roles structurally. A mechanical replacement of
every `"schemaVersion": RENDER_SCHEMA` is forbidden.

## Canonical manifest-envelope correction

### Path-specific parser

Add a manifest-only parser in `scripts/ui_ux_theme_handoff.py`. It is used
only for forward paths whose artifact contract is an evidence manifest.
It must:

1. require bytes below the existing manifest maximum;
2. require exactly one LF byte and require it to be the final byte;
3. reject CRLF, no LF, two LFs, interior LF, BOM, leading/trailing spaces,
   duplicate keys, invalid UTF-8, non-finite numbers, and unsupported values;
4. decode the JSON payload before the LF with duplicate-key rejection;
5. require a mapping;
6. reserialize with `scripts.ui_ux_evidence._manifest_bytes(document)` and
   require exact byte equality;
7. apply the path's expected evidence schema, status, IDs, cardinalities, and
   later semantic validation.

Ordinary report, packet, intake, review, candidate, root, preflight, Tier, and
authorization JSON continue to use compact `_strict_json_bytes()` with no LF.

### Classifier grammar

The Sequence 13 forward classifier uses a declared artifact-kind table:

| Index | State after presence | Kind | Parser |
| ---: | --- | --- | --- |
| `0` | `M1_CAPTURE` | passed evidence manifest | manifest-only canonical LF parser |
| `1` | `M2_REPORT` | migration report | compact strict JSON |
| `2` | `M3_PACKET` | review packet | compact strict JSON |
| `3` | `M4_INTAKE` | external intake | compact strict JSON |
| `4` | `M5_REVIEW` | manual review | compact strict JSON |
| `5` | `M6_CANDIDATE` | handoff candidate | compact strict JSON |
| `6` | `M7_ROOT` | handoff root | compact strict JSON |

The classifier first proves a no-gap prefix and safe leaf metadata, then
parses each present leaf according to its declared kind, then validates every
present artifact semantically in order. Parser selection may not be inferred
from attacker-controlled document fields.

The failed Sequence 12 manifest is authenticated by the predecessor importer,
not passed through this Sequence 13 forward classifier.

## Sequence 13 authority

### Fixed IDs

```text
correctionId = 20260729T030000Z
tierId       = 20260729T031000Z
captureId    = 20260729T040000Z
```

These IDs and all paths derived from them are fixed plan data. Runtime
timestamps cannot replace them.

### Planned authorization candidate

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-seq13.md
```

It will use distinct Sequence 13 start/end markers and bind:

- this reviewed plan and its reviewed traceability ledger;
- the exact imported Sequence 12 authorization, Tier, preflight, capture
  stack, terminal failed manifest, and partial pair;
- the exact Sequence 13 source package;
- the exact distinct Sequence 13 capture stack;
- only the seven Sequence 13 coordinator commands;
- the three fixed IDs and formal `M3_PACKET` stop.

The candidate is generated only after implementation, test, stack, scope, and
diff gates pass. Its SHA-256, size, and mode are reported to the maintainer.
No formal bootstrap may run before the maintainer accepts those exact bytes.

### Planned Sequence 13 capture stack

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json
```

The contract is create-once, mode `0600`, and uses:

```text
rootExpansionSha256 =
  13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca
focusedRows = 36
fullPageRows = 81
themeRows = 3
totalRows = 120
```

`baseCaptureStackDigest` is not the predecessor stack digest. It is computed
only after implementation member bytes stabilize as:

```text
SHA-256(canonical JSON of the exact nine sorted member records)
```

The Sequence 13 control catalog binds that newly computed member digest, and
its resulting `captureStackDigest` is computed by the existing
`control_catalog_digest()` contract. The exact Sequence 12 stack contract
SHA, its member base digest, and its capture-stack digest remain separate
predecessor/transition authority and are never copied into either new digest
field.

It binds the same nine closed member paths as Sequence 12. Only
`scripts/ui_ux_evidence.py` and `scripts/ui_ux_snapshot_matrix.py` are
expected to receive production changes; all other member bytes must remain
exact. Every non-digest control-catalog field and the complete root expansion
remain exactly equal to Sequence 12. Only the base/new stack digest fields
change as required by the distinct stack contract.

Stack publication order prevents a hash fixed point:

1. finish evidence and snapshot-runner source;
2. run unit and production-shaped disposable tests;
3. discover and freeze all nine exact member records;
4. publish/reopen the Sequence 13 stack;
5. bind its exact contract hash/digest only in the non-member coordinator;
6. finish coordinator tests and then generate the authorization candidate.

`scripts/ui_ux_theme_handoff.py`, tests, Makefile, the plan, ledger, and
authorization are not capture-stack members.

The trusted-accessibility preflight must also move its live-member check to
the Sequence 13 stack:

- legacy and Sequence 12 stack files remain protected and are checked by
  their exact whole-file historical hashes;
- their old member records are not compared with current source after an
  authorized source transition;
- the new Sequence 13 stack is checked by its exact whole-file hash and all
  nine member records are compared with current live files;
- the trusted AX catalog/selector equality checks remain unchanged.

### Tier and preflight destinations

```text
.claude/ui_snapshots/ux1b/recovery/.render-manifest-correction-20260729T030000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-prechange-seq13.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-rollback-seq13.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-prechange-20260729T031000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-render-manifest-correction-preflight-20260729T030000Z.json
```

The Tier uses the existing global handoff lock and descriptor-safe
create-or-exact-reopen primitives. Its archive contains only the closed
Sequence 13 source package. Publication/reopen must reauthenticate the
immutable Sequence 12 predecessor before and after each write.

The preflight is compact canonical JSON, create-once mode `0600`, and binds:

- exact authorization, plan, ledger, source package, Tier, and lease;
- `S12_TERMINAL_FAILED` imported predecessor record;
- distinct Sequence 13 capture-stack contract, digest, members, catalog, and
  root expansion;
- exact source and supplemental projections;
- current runtime identity/tree, reauthenticated live;
- Make target/command contract;
- initial Sequence 13 namespace inventory;
- deterministic descriptor profile.

The Sequence 12 runtime receipt is historical authority. Sequence 13 also
measures the live runtime before preflight publication and before/after every
write-capable child. Any difference from the reviewed accepted runtime
identity/tree blocks execution; it is never silently refreshed.

### Source package

The planned formal archive contains exactly:

```text
Makefile
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.md
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence12-terminal-import-render-manifest-correction.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-seq13.md
scripts/test_ui_ux_evidence.py
scripts/test_ui_ux_snapshot_matrix.py
scripts/test_ui_ux_theme_handoff.py
scripts/test_ui_accessible_selection_controls.py
scripts/ui_ux_browser_worker.py
scripts/ui_ux_evidence.py
scripts/ui_ux_fixture_app.py
scripts/ui_ux_fixtures.py
scripts/ui_ux_isolation.py
scripts/ui_ux_selection_fixture_app.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_theme_fixture_app.py
scripts/ui_ux_theme_handoff.py
scripts/ui_ux_theme_matrix.py
```

Unchanged stack members are archived because they are part of the formal
runtime source authority. Tests are archived because they define the reviewed
regression gate. No `.venv`, cache, screenshot, UI, API, provider, secret, or
unlisted worktree file enters the archive.

## Forward namespace and lifecycle

### New forward paths

```text
0 .claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260729T040000Z/manifest.json
1 .claude/ui_snapshots/ux1b/recovery/control-migration-20260729T040000Z.json
2 .claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T040000Z.json
3 .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T040000Z.json
4 .claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T040000Z.json
5 .claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T040000Z.json
6 docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

The first six paths are disjoint from all Sequence 8–12 namespaces. The final
root path is shared historical product authority and must remain absent
through this plan's formal stop.

### States

| State | Existing new forward leaves | Meaning | Allowed action |
| --- | ---: | --- | --- |
| `M0_READY` | `0` | Accepted preflight, no Sequence 13 capture | capture or read-only reconcile |
| `M1_CAPTURE` | `1` | Passed `36/44/88/89` capture | compare |
| `M2_REPORT` | `2` | Passed `81/44/125` report | prepare packet |
| `M3_PACKET` | `3` | Exact `125`-item packet | mandatory stop |
| `M4_INTAKE` | `4` | Future external intake | forbidden in this plan |
| `M5_REVIEW` | `5` | Future manual review | forbidden in this plan |
| `M6_CANDIDATE` | `6` | Future handoff candidate | forbidden in this plan |
| `M7_ROOT` | `7` | Future handoff root | forbidden in this plan |

Only a contiguous prefix is valid. Every existing leaf must pass its metadata,
canonical-envelope, schema, authority, identity, cardinality, predecessor,
source, stack, and cross-leaf semantic checks. Prefix shape alone never
authorizes a state.

### Capture and reconcile

The formal capture command:

- requires exact accepted Sequence 13 Tier/preflight and `M0_READY`;
- reimports `S12_TERMINAL_FAILED`;
- reauthenticates runtime, source projections, stack, root expansion, and all
  new forward absences;
- invokes `.venv/bin/python -B scripts/ui_ux_snapshot_matrix.py` with
  `--capture-stack seq13`, profile `ux1b-selection-controls`, phase
  `postcontrol`, Chromium, no prompt, and the new capture root;
- uses the existing bounded, process-group-owned, awake-gated child protocol;
- requires exit `0`, quiescence, and exact JSON summary;
- reauthenticates runtime, source, stack, and the entire passed bundle after
  child exit;
- accepts exactly `36` logical requests, `44` root captures, `88` artifact
  leaves, and one `89`-leaf canonical passed manifest.

No Sequence 12 partial bytes are copied, linked, adapted, or counted.

Reconcile:

- at `M0_READY` returns read-only success only if the entire new capture root
  is absent;
- if any new partial capture root exists without an authenticated passed
  manifest, retains it and fails closed without retry;
- at `M1_CAPTURE..M3_PACKET`, reopens the existing prefix and performs no
  capture;
- never deletes or retries either the Sequence 12 or Sequence 13 failed
  namespace.

### Comparator and review packet

The comparator uses:

- exact historical before/after page authority already accepted;
- exact historical before-control authority;
- only the passed Sequence 13 root capture as the corrected after-control
  input;
- the unchanged root expansion and historical pairing;
- the unchanged frozen legacy semantic adapter.

It must publish/reopen one report containing exactly:

```text
pageComparisons = 81
controlRootComparisons = 44
comparedCaptures = 125
legacySemanticOracle = 81 page + 36 logical control = 117
passedRootCaptures = 44
unboundRootCaptures = 0
exactPrePostProjections = 88
```

The report records the transition from the historical capture-stack authority
to the exact Sequence 13 stack and the exact Sequence 12-to-13 source
transition. The failed Sequence 12 manifest and partial pair appear only in an
`excludedPredecessorFailure` record; they are never report inputs or review
items.

`prepare-review` publishes/reopens one review-packet v2 with exactly five
inputs and `125` unique ordered items, then returns `M3_PACKET`. Intake,
manual review, candidate, and root must remain absent.

## Public commands and Make targets

Exactly seven new coordinator commands are allowed:

```text
bootstrap-render-manifest-correction
preflight-render-manifest-correction
verify-render-manifest-correction-preflight
capture-render-manifest-controls
reconcile-render-manifest-controls
compare-render-manifest-migration
prepare-render-manifest-review
```

Each requires `--correction-id`, `--tier-id`, `--capture-id`, and `--json`
with the exact fixed values. Capture additionally binds the exact preflight
path internally. No generic output path, stack path, manifest path, selector,
schema, or retry flag is exposed.

Exactly seven matching Make targets are added:

```text
ui-ux1b-render-manifest-bootstrap
ui-ux1b-render-manifest-preflight
ui-ux1b-render-manifest-verify
ui-ux1b-render-manifest-capture
ui-ux1b-render-manifest-reconcile
ui-ux1b-render-manifest-compare
ui-ux1b-render-manifest-prepare-review
```

The existing Sequence 12 commands and targets remain available only for
historical verification. Their capture/reconcile calls must fail closed
against the retained terminal failure and cannot mint Sequence 13 artifacts.

## Requirements

| ID | Requirement |
| --- | --- |
| `REQ-014` | Continue the corrected UX-1B focused-control handoff from the exact retained Sequence 12 terminal failure without historical mutation or namespace reuse. |
| `CFR-062` | Authenticate the complete Sequence 12 authority and failed capture tree as one immutable, excluded predecessor. |
| `CFR-063` | Preserve the actual accepted render schema through publication, immediate verification, manifest freeze, and reauthentication. |
| `CFR-064` | Accept exactly the evidence module's canonical one-LF manifest envelope while keeping every other JSON artifact compact and strict. |
| `CFR-065` | Use distinct Sequence 13 IDs, Tier, preflight, forward paths, source projection, runtime receipt, and capture stack. |
| `CFR-066` | Preserve `36/44/88/89`, `81/44/125`, nested `81/36/117`, packet-only pause, process containment, and fail-soft/protected-source behavior. |

## Acceptance criteria

### `AC-SEQ13-001` — exact terminal predecessor import

Given the retained Sequence 12 authority and failed capture tree, when any
Sequence 13 bootstrap, preflight, verify, capture, reconcile, compare, or
packet command runs, then the complete predecessor reopens exactly as
`S12_TERMINAL_FAILED`, the partial pair remains excluded, and any drift blocks
before a Sequence 13 write.

### `AC-SEQ13-002` — publication schema fidelity

Given an authenticated finalized v1 or v2 render sidecar, when
`publish_finalized_capture()` publishes its pair, then the returned artifact
claim exactly matches the actual sidecar schema and
`verify_capture_artifacts()` accepts the unmodified record.

### `AC-SEQ13-003` — reopen schema fidelity

Given a canonical passed manifest containing v1 and/or v2 capture records,
when the bundle is frozen and reauthenticated, then each materialized capture
claim preserves its actual render schema and cannot be downgraded, upgraded,
or caller-overridden.

### `AC-SEQ13-004` — exact manifest envelope

Given a forward evidence manifest produced by `_manifest_bytes()`, when the
Sequence 13 classifier opens it, then the exact one-terminal-LF form is
accepted and every alternative whitespace, duplicate-key, encoding, number,
schema, status, and artifact-kind mutant is rejected.

### `AC-SEQ13-005` — disjoint Sequence 13 authority

Given accepted exact Sequence 13 authorization bytes, when bootstrap and
preflight run, then a create-once Tier/preflight binds the imported terminal,
new stack/source/runtime, new absent namespace, exact commands, and state
`M0_READY` without changing Sequence 12.

### `AC-SEQ13-006` — corrected complete capture

Given an accepted verified `M0_READY` preflight, when the formal capture runs,
then the new namespace alone reaches `M1_CAPTURE` with `36/44/88/89`,
v2 artifact claims equal v2 sidecars, all children quiescent, and runtime,
source, and stack unchanged.

### `AC-SEQ13-007` — comparison and packet pause

Given the exact passed Sequence 13 capture, when compare and prepare-review
run, then the lifecycle reaches exactly `M3_PACKET` with `81/44/125` review
items and nested `81/36/117` semantic comparisons, while all later paths
remain absent.

### `AC-SEQ13-008` — compatibility and protected scope

Given the complete implementation diff, when all unit, lifecycle, real
Chromium, fail-soft API/UI, legacy v1, runtime, syntax, dependency, source,
scope, and protected-artifact gates run, then no unplanned production or
historical byte changes and no unexplained test failure remain.

## Implementation map

| ID | Planned implementation |
| --- | --- |
| `IMPL-099` | Descriptor-safe Sequence 12 terminal-failure importer and exact closed-tree inventory. |
| `IMPL-100` | Single actual-render-schema derivation helper for validated finalized documents. |
| `IMPL-101` | Schema-correct `publish_finalized_capture()` artifact record. |
| `IMPL-102` | Schema-correct `_validate_open_capture_bytes()` and manifest-bundle materialization. |
| `IMPL-103` | Manifest-only one-LF parser plus declared-kind Sequence 13 prefix classifier. |
| `IMPL-104` | Distinct Sequence 13 capture-stack selection/publication, root-capture runner binding, and current-stack trusted-AX preflight. |
| `IMPL-105` | Sequence 13 authorization, Tier, preflight, source/runtime/namespace authority, CLI validation, and Make targets. |
| `IMPL-106` | New capture/reconcile lifecycle with retained-partial fail-closed behavior and exact cardinalities. |
| `IMPL-107` | Sequence 13 comparator, excluded predecessor record, `125`-item packet, and `M3_PACKET` pause. |
| `IMPL-108` | Red-first, mutation, production-shaped, Chromium, compatibility, source-scope, and completion verification. |

## Test map

| ID | Test obligation |
| --- | --- |
| `TEST-130` | Reproduce the exact v2 publication failure and turn the production-shaped `finalize -> publish -> verify` path green without patching schema claims. |
| `TEST-131` | Verify v1 and v2 artifact schema fidelity across publication, passed-manifest freeze, and cross-process reauthentication. |
| `TEST-132` | Reject wrong, missing, unsupported, or caller-forced schema claims and prove intentional legacy semantic projections remain exact v1. |
| `TEST-133` | Accept only `_manifest_bytes()` output for manifest-kind leaves; reject no-LF, double-LF, CRLF, interior-LF, whitespace, BOM, duplicate, non-finite, wrong-kind, wrong-schema, and wrong-status mutants. |
| `TEST-134` | Reopen the exact Sequence 12 authority, Tier, preflight, failed manifest, directory inventory, v2 partial render, and PNG; reject every mutation and later-leaf presence. |
| `TEST-135` | Verify Sequence 13 ID/path collision freedom, authorization grammar, source package, Tier/preflight, initial absences, no-gap prefix states, and old-command non-authority. |
| `TEST-136` | Verify snapshot-runner `seq13` selection binds only the distinct new stack, retains the `36/44` root plan, and rejects legacy/seq12/new-stack substitution. |
| `TEST-137` | Production-shaped capture/reconcile fixtures prove `36/44/88/89`, v2 claim equality, process quiescence, runtime/source/stack closure, partial retention, collision, timeout, and no retry. |
| `TEST-138` | Comparator and packet fixtures prove `81/44/125`, nested `81/36/117`, exact excluded predecessor, exact five inputs, ordered uniqueness, and stop at `M3_PACKET`. |
| `TEST-139` | Real disposable Chromium root capture verifies all `44` v2 pairs and reopens the `89`-leaf manifest through the coordinator's manifest parser. |
| `TEST-140` | Existing Sequence 8–12, legacy v1, fixture/catalog, trusted-AX, full recovery, and historical verification tests remain green; old stacks use whole-file history while the new stack binds live members. |
| `TEST-141` | Fail-soft artifact loader/API/UI, Python 3.10 AST, compile, tabnanny, dependency, whitespace, dirty-worktree, source-scope, diff, runtime, and absence gates pass. |

## Given-When-Then scenario matrix

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| `SC-AC-SEQ13-001-HP-001` | Exact retained Sequence 12 terminal | Importer runs | Typed `S12_TERMINAL_FAILED` |
| `SC-AC-SEQ13-001-NP-001` | One predecessor byte or inode differs | Importer runs | Fail before new write |
| `SC-AC-SEQ13-001-NP-002` | Extra descendant or later Sequence 12 leaf exists | Importer runs | Fail closed |
| `SC-AC-SEQ13-001-EP-001` | Exact partial v2 pair, zero completed manifest | Importer runs | Authenticate diagnostics, count neither |
| `SC-AC-SEQ13-002-HP-001` | Finalized v1 sidecar | Publish and verify | Record claims v1 |
| `SC-AC-SEQ13-002-HP-002` | Finalized v2 sidecar | Publish and verify | Record claims v2 |
| `SC-AC-SEQ13-002-NP-001` | Record claim differs from actual sidecar | Verify runs | Reject |
| `SC-AC-SEQ13-003-HP-001` | Passed manifest with v2 root pair | Freeze/reauth runs | Materialized claim remains v2 |
| `SC-AC-SEQ13-003-HP-002` | Passed manifest with legacy v1 pair | Freeze/reauth runs | Materialized claim remains v1 |
| `SC-AC-SEQ13-003-NP-001` | Reopen helper defaults schema | Equality test runs | Fail |
| `SC-AC-SEQ13-004-HP-001` | Exact canonical one-LF manifest | Classifier runs | Accept manifest kind |
| `SC-AC-SEQ13-004-NP-001` | No LF, extra LF, CRLF, or padding | Classifier runs | Reject |
| `SC-AC-SEQ13-004-NP-002` | Packet bytes placed in manifest slot | Classifier runs | Reject by declared kind |
| `SC-AC-SEQ13-004-NP-003` | Manifest bytes placed in report slot | Classifier runs | Reject compact parser |
| `SC-AC-SEQ13-005-HP-001` | Accepted auth and absent new namespace | Bootstrap/preflight run | Exact `M0_READY` |
| `SC-AC-SEQ13-005-NP-001` | Seq13 ID/path/stack/source/runtime drift | Any command runs | Fail before publication |
| `SC-AC-SEQ13-005-EP-001` | Exact Tier/preflight already exist | Bootstrap/preflight rerun | Read-only exact reopen |
| `SC-AC-SEQ13-006-HP-001` | Exact verified `M0_READY` | Capture runs | `M1_CAPTURE`, `36/44/88/89` |
| `SC-AC-SEQ13-006-NP-001` | Any v2 record is labeled v1 | Immediate verify runs | No passed manifest |
| `SC-AC-SEQ13-006-NP-002` | Child fails after a partial pair | Reconcile runs | Retain root, reject retry |
| `SC-AC-SEQ13-006-EP-001` | Exact passed manifest exists | Reconcile runs | Read-only `M1_CAPTURE` |
| `SC-AC-SEQ13-007-HP-001` | Exact `M1_CAPTURE` | Compare runs | `M2_REPORT`, `125` |
| `SC-AC-SEQ13-007-HP-002` | Exact `M2_REPORT` | Prepare packet runs | `M3_PACKET`, stop |
| `SC-AC-SEQ13-007-NP-001` | Partial pair enters comparison | Comparator runs | Reject |
| `SC-AC-SEQ13-007-NP-002` | Intake/review/candidate/root exists | Verify runs | Reject plan boundary |
| `SC-AC-SEQ13-008-HP-001` | Complete planned diff | All gates run | Green with exact protected scope |
| `SC-AC-SEQ13-008-NP-001` | UI/API/fixture/runtime/historical drift | Scope gate runs | Fail |
| `SC-AC-SEQ13-008-NP-002` | Intentional legacy v1 projection changed | Compatibility gate runs | Fail |

## Affected files

### Planned implementation edits

```text
Makefile
scripts/ui_ux_evidence.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_theme_handoff.py
scripts/test_ui_accessible_selection_controls.py
scripts/test_ui_ux_evidence.py
scripts/test_ui_ux_snapshot_matrix.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-render-manifest-correction-seq13.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

This plan and its sibling ledger are the current planning deliverables. After
they are reviewed and frozen, implementation must treat their bytes as
read-only authority.

### Read-only but archived stack members

```text
scripts/ui_ux_browser_worker.py
scripts/ui_ux_fixture_app.py
scripts/ui_ux_fixtures.py
scripts/ui_ux_isolation.py
scripts/ui_ux_selection_fixture_app.py
scripts/ui_ux_theme_fixture_app.py
scripts/ui_ux_theme_matrix.py
```

### Protected paths

```text
all Sequence 8/9/10/11/12 plans, ledgers, authorization, Tier, preflight,
capture, report, packet, intake, review, stack, and runtime evidence
all production ui/ and api/
all provider, data, configuration, dependency, selector, and theme-source files
the legacy and Sequence 12 capture-stack contracts
the exact retained Sequence 12 failure tree
```

## Implementation sequence

### Phase S13-0 — reviewed authority gate

- Freeze this reviewed plan and canonical traceability ledger.
- Confirm all exact predecessor rows and new path absences.
- Generate no authorization candidate yet.
- Obtain explicit maintainer approval to begin implementation.

**Gate:** unresolved review blocker, predecessor drift, ID collision, missing
verification surface, or unclear file scope stops before source edits.

### Phase S13-1 — red schema and envelope tests

- Add `TEST-130..134` as focused fail-first tests.
- Reproduce the exact production call chain, not a hand-authored record.
- Freeze v1/v2 positive and mutation matrices.
- Freeze evidence manifest bytes with exactly one LF and ordinary compact JSON
  bytes without LF.
- Freeze the Sequence 12 terminal tree and exclusion semantics.

**Gate:** failures must point to the three known contract gaps; tests cannot
edit real predecessor evidence, formal namespaces, `.venv`, UI, API, or
fixture source.

### Phase S13-2 — evidence schema fidelity

- Implement `IMPL-100..102`.
- Derive the schema from validated final bytes/document at both artifact-record
  projection sites.
- Keep the closed accepted set `{v1,v2}`.
- Preserve all deliberate legacy semantic projections.

**Gate:** focused v1/v2 publication, immediate verify, manifest freeze,
reauthentication, and mutation tests pass. No snapshot/coordinator workaround
or record patch is allowed.

### Phase S13-3 — manifest parser and stack

- Implement `IMPL-103..104`.
- Add the declared artifact-kind parser table.
- Add snapshot-runner `seq13` selection and exact path binding.
- Run production-shaped disposable root capture and exact `44`-pair reopen.
- Freeze/publish/reopen the distinct Sequence 13 stack.

**Gate:** real manifest bytes pass both evidence and coordinator parsers;
every whitespace/kind mutant fails; all nine stack members and the unchanged
catalog/root expansion reopen exactly.

### Phase S13-4 — terminal import and lifecycle

- Implement `IMPL-099,IMPL-105,IMPL-106`.
- Import the exact Sequence 12 terminal without routing it through new forward
  logic.
- Add distinct authority, Tier/preflight, source/runtime, commands, Make
  targets, prefix classification, capture, and reconcile.
- Run lifecycle fixtures only in disposable namespaces.

**Gate:** all terminal mutations, path collisions, old-command substitutions,
partial failures, timeouts, runtime/source/stack drift, and retries fail
closed; no real Sequence 13 Tier or forward artifact exists.

### Phase S13-5 — comparator, packet, and complete gates

- Implement `IMPL-107..108`.
- Preserve exact historical inputs, semantic adapter, geometry, cardinalities,
  exclusions, and packet pause.
- Compare actual diff against this reviewed plan.
- Review changed code for bugs, regressions, missing tests, and maintainability.
- Fix all blocking findings.
- Run the complete verification matrix.

**Gate:** every relevant check passes; any unavailable check is reported;
protected source/evidence remains exact; no formal Sequence 13 artifact has
been created.

### Phase S13-6 — authorization candidate handoff

- Generate the Sequence 13 authorization candidate last.
- Verify marker grammar, body digest, exact package, commands, IDs, paths,
  stop state, and no unplanned permission.
- Report candidate SHA-256, byte size, and mode.
- Stop for exact maintainer acceptance.

**Gate:** acceptance of an earlier draft, filename alone, body hash alone, or
different bytes does not authorize formal work.

### Phase S13-7 — later formal execution

Only after exact authorization acceptance:

1. bootstrap/reopen the Sequence 13 Tier;
2. publish/reopen the Sequence 13 preflight at `M0_READY`;
3. run the one new formal capture;
4. reopen the complete `89`-leaf bundle at `M1_CAPTURE`;
5. publish/reopen the `125` comparison at `M2_REPORT`;
6. publish/reopen the `125`-item packet at `M3_PACKET`;
7. stop before intake.

Any new partial capture is retained and requires another reviewed correction.

## Verification commands

At minimum during implementation:

```bash
.venv/bin/python -B scripts/test_ui_ux_evidence.py
.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_ui_ux1a_safety.py
.venv/bin/python -B scripts/test_ui_ux_components.py
.venv/bin/python -B -m pip check
```

Mandatory targeted gates:

- exact production-shaped v2 `finalize -> publish -> verify`;
- exact v1 and v2 passed-manifest freeze/reauthentication;
- manifest-envelope/kind mutation matrix;
- exact Sequence 12 terminal importer mutation matrix;
- Sequence 13 CLI/Make/ID/path/source/stack mutation matrix;
- `36/44/88/89` capture/reconcile fixture;
- `81/44/125` report/packet fixture;
- nested legacy `81/36/117` semantic equality;
- one disposable `44/44` Chromium root run and `89`-leaf reopen;
- no owned capture process or temporary runtime remains;
- Python 3.10 AST parse for every changed Python file;
- `py_compile`, `tabnanny`, dependency, whitespace, and diff checks;
- exact before/after runtime tree;
- exact imported predecessor and protected-file hashes;
- later Sequence 13 formal paths absent during implementation verification.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Fixing only the first v1 hardcode causes a later reopen failure | Cover both artifact-record projection sites and the full publish-to-reauth path. |
| Replacing all v1 constants breaks the legacy semantic oracle | Classify artifact claims versus deliberate semantic adapters; freeze adapter bytes. |
| Relaxing the global JSON parser admits whitespace or kind confusion | Add a manifest-only parser and a declared path-kind table; keep ordinary strict parser unchanged. |
| Treating the failed manifest as a forward leaf creates a false state | Authenticate it only inside the exact terminal predecessor importer. |
| Partial Sequence 12 bytes contaminate the new evidence | Closed-tree import marks them diagnostic/excluded; new capture requires a disjoint root and complete cardinality. |
| New stack is frozen before members stabilize | Run unit/production-shaped tests before stack publication; bind stack hash into non-member coordinator afterward. |
| New source uses an old preflight | Sequence 13 publishes a distinct source/runtime/stack preflight and never amends Sequence 12. |
| Formal capture is accidentally retried | One fixed new capture namespace; retained-partial reconcile fails closed and requires another reviewed correction. |
| Downstream work skips independent review | Mandatory formal stop remains `M3_PACKET`; intake and later paths are forbidden. |
| Dirty worktree scope is mistaken for this change | Record exact preimages and compare only planned paths; preserve all unrelated user changes. |

## Rollback

Before Sequence 13 Tier publication:

- remove only disposable test namespaces and create-once implementation
  outputs produced by the current implementation session when their identity
  is independently authenticated;
- keep this reviewed plan/ledger and every historical artifact;
- do not use Git reset, checkout, or destructive cleanup.

After Sequence 13 Tier publication:

- never overwrite or delete the Sequence 13 authorization, Tier, preflight,
  stack, capture, report, packet, or partial namespace;
- never modify Sequence 12 evidence;
- stop and prepare a new reviewed correction for any failure.

Rollback never authorizes UI/fixture changes to make capture evidence pass.

## Success metrics

| Metric | Target |
| --- | ---: |
| Exact Sequence 12 terminal rows reopened | `12/12` files plus `5/5` directories |
| Partial predecessor artifacts counted in new capture/report | `0` |
| v1 publication/reopen schema matches | `100%` |
| v2 publication/reopen schema matches | `100%` |
| Manifest envelope mutants accepted | `0` |
| New logical requests | `36/36` |
| New root captures | `44/44` |
| New artifact leaves | `88/88` |
| New manifest leaves | `89/89` |
| Review comparisons/items | `125/125` |
| Nested legacy comparisons | `117/117` |
| Unbound root captures | `0` |
| Later artifacts at formal stop | `0` |
| Protected source/evidence drift | `0` |
| Traceability coverage | `10000` basis points |

## Dependencies

- Exact reviewed Sequence 12 plan, amendment, ledgers, implementation, and
  authorization.
- Exact published Sequence 12 Tier, preflight, stack, failed manifest, and
  partial artifact pair listed above.
- Exact historical Sequence 8–11 page/control/report/review authorities.
- Existing Darwin descriptor, process-group, awake, runtime-isolation, and
  create-once primitives.
- Playwright Chromium for one disposable real matrix.
- Maintainer acceptance of this plan for implementation, followed later by
  separate exact-byte acceptance of the generated Sequence 13 authorization.

## Review checklist

- [x] Both schema-misprojection sites are in scope.
- [x] Intentional legacy v1 semantic projections are protected.
- [x] Exact evidence-manifest LF grammar is closed.
- [x] Ordinary JSON grammar remains unchanged.
- [x] The Sequence 12 failed root is a terminal predecessor, not a forward
  prefix.
- [x] The complete failed tree inventory and partial-pair exclusion are
  explicit.
- [x] Sequence 13 IDs, Tier, preflight, stack, forward paths, commands, and
  Make targets are distinct and collision-free.
- [x] Capture, reconcile, report, and packet cardinalities are closed.
- [x] Runtime, source, stack, process, fail-soft, and protected-scope gates are
  present.
- [x] Formal execution stops at `M3_PACKET`.
- [x] Requirements, acceptance criteria, implementation nodes, tests, and
  scenarios are bidirectionally traceable with no gaps or orphans.
- [x] No unresolved Blocker, High, or Medium review finding remains.

## Review findings

Review findings are appended here before finalization. Report every issue that
could cause incorrect behavior, a test failure, misleading evidence, unsafe
mutation, or scope drift; severity/confidence filtering happens after
enumeration. Any unresolved Blocker, High, or Medium finding prevents
`REVIEWED`.

| Iteration | Finding | Severity | Resolution |
| ---: | --- | --- | --- |
| `1` | Reusing the Sequence 12 Tier/preflight validator would rebuild its frozen source projection from changed Sequence 13 source and would also route the retained failed manifest through the obsolete `R0..R7` classifier. | Blocker | Added an exact-hash historical importer that validates retained archive/preflight facts without current-source recomputation; current source/runtime/namespace are bound only in the new preflight. |
| `1` | Cross-process bundle reopen materialized v2 sidecars as v1 and did not first require the persisted claim to equal the actual sidecar schema. | High | Required actual-schema derivation at both record sites plus explicit persisted-claim equality before normalized materialization. |
| `1` | The formal source package omitted the trusted-accessibility regression file used by the complete recovery gate. | Medium | Added `scripts/test_ui_accessible_selection_controls.py` to the formal source package and planned verification surface. |
| `2` | The draft incorrectly set the new `baseCaptureStackDigest` to the Sequence 12 `captureStackDigest`; production defines base as the digest of the current nine member records. | Blocker | Removed the false fixed value and specified post-stabilization member-record derivation, new control-catalog digest computation, and separate predecessor transition authority. |
| `3` | The trusted-AX preflight compares Sequence 12 member records to live files, so authorized evidence/snapshot changes would make the complete recovery suite fail. | Blocker | Made the test a planned edit: old stack files keep exact historical whole-file checks, while only the Sequence 13 stack validates current live members. |
| `4` | Rechecked authority separation, actual-schema flow, manifest grammar/kind dispatch, stack construction, trusted AX, path collisions, lifecycle/cardinalities, test surface, protected scope, and bidirectional traceability. | None | No unresolved Blocker, High, or Medium finding remains. |

The three blocking findings were distinct and each was closed in the
iteration that found it. No single blocker remained across three review
iterations. Review iteration 4 was a clean blocking review. This status
authorizes neither implementation nor formal publication.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `0.1-review-candidate` | 2026-07-29 | Initial Sequence 13 terminal-import and render/manifest correction candidate. |
| `0.2-review-candidate` | 2026-07-29 | Separated historical import from live validation and closed publication/reopen schema equality. |
| `0.3-review-candidate` | 2026-07-29 | Corrected capture-stack base-digest semantics. |
| `0.4-review-candidate` | 2026-07-29 | Corrected the trusted-AX current-stack transition and formal test package. |
| `1.0-reviewed` | 2026-07-29 | Fourth blocking review found no unresolved Blocker, High, or Medium issue. |

## Next handoff

After a clean blocking review:

1. freeze this plan;
2. generate and validate the canonical sibling traceability ledger;
3. report both exact SHA-256 values, sizes, and modes;
4. wait for explicit maintainer approval before implementation.
