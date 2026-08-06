# UX-1B Sequence 12 Multi-Root Capture Cardinality Amendment

## Document info

| Field | Value |
| --- | --- |
| Type | Implementation-plan amendment |
| Version | `1.0-reviewed` |
| Status | `REVIEWED` |
| Author | Quant Radar implementation session |
| Reviewer | Repository maintainer and implementation reviewer |
| Approver | Repository maintainer; exact-byte acceptance pending |
| Audience | Maintainer, implementer, evidence reviewer |
| Date | 2026-07-28 |
| Sequence | `12` |
| Correction ID | `20260728T000000Z` |
| Parent plan | `docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.md` |
| Parent ledger | `docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.traceability.yaml` |
| Sibling ledger | `docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-multi-root-capture-cardinality-amendment.traceability.yaml` |

## Authority and purpose

This amendment resolves one blocking contradiction discovered during the
reviewed Sequence 12 implementation.

The exact retained parent authorities are:

| Authority | SHA-256 | Size | Mode |
| --- | --- | ---: | ---: |
| Parent plan | `6f836a45e6d0d88d960ef2d3e0f073e0b70918440eaf66c9406ef9d44c2a7de0` | `41964` | `0644` |
| Parent ledger | `18d45c965711d03bfd0a8e76b58d5669a7bb063f4228f66d2d2849c6cca351f6` | `8487` | `0644` |

The parent plan requires every root in a multi-root case to fit one unchanged
catalog viewport. It also requires the worker to fail when the complete root
union does not fit. A disposable authenticated Chromium run observed:

```text
case: radar-controls
viewport: mobile, 390x844
union: left=16, top=312.359375, right=374, bottom=1200.734375
union height: 888.375
vertical excess: 44.375
```

The failed worker retained no accepted screenshot, sidecar, stack contract, or
formal Sequence 12 artifact. The historical stack remains exact at SHA-256
`8b354ec6d7f84e4bfbd96c098ffd1dae2db0d90f7f9cf86d168bc8a9298df820`.

No scroll-only algorithm can reduce the fixed distance between these two
document-flow roots. Solving the contradiction by zooming, reflowing, hiding,
moving, or restyling production content would make the evidence synthetic.
Changing the viewport would break historical catalog equivalence. Combining
tiles would no longer prove one screenshot-time viewport state.

This amendment therefore changes the evidence unit from one case/viewport to
one catalog root/case/viewport. It retains one logical fixture request for each
of the original `36` case/viewport identities and emits one independently
bound evidence unit for each of the `44` root/viewport identities.

This document does not authorize implementation until the maintainer accepts
its final exact SHA-256, size, and mode. The parent authorization candidate,
Sequence 12 capture stack, Tier, preflight, corrected capture, report, and
packet remain absent until that acceptance.

## Target audience

- The maintainer decides whether the evidence cardinality change is accepted.
- The implementer uses the closed identity and lifecycle rules.
- The independent reviewer receives `125` review items with no composite or
  off-viewport focused screenshot.

## Scope

### In scope

- Preserve the original `36` logical fixture requests and counter identities.
- Expand the eleven focused root identities across four viewports into `44`
  independently captured root evidence units.
- Allow one logical worker request to stage one or two ordered root artifact
  pairs.
- Bind every root PNG to one root-only render v2 sidecar containing focused
  evidence v3.
- Preserve exact pre/post screenshot binding and full node projection equality
  for each root evidence unit.
- Publish `88` root artifacts and one `89`-leaf corrected manifest bundle.
- Compare `81` historical page identities and `44` root-level control
  identities, for `125` comparison items.
- Produce a `125`-item independent-review packet.
- Update Sequence 12 code, tests, stack contract, coordinator authority, and
  final authorization candidate consistently.

### Out of scope

- No production `ui/`, `api/`, provider, selector, or theme-source change.
- No `scripts/ui_ux_selection_fixture_app.py` change.
- No viewport name, width, height, route, callable, session key, option, or
  control-root catalog change.
- No zoom, CSS transform, reflow, content hiding, tile stitching, image
  compositing, or synthetic root relocation.
- No historical manifest, PNG, sidecar, report, packet, intake, review, Tier,
  preflight, authorization, or stack rewrite.
- No reuse of the rejected Sequence 11 after-controls manifest as corrected
  evidence.
- No arbitrary capture-stack path or generic workflow engine.
- No formal Sequence 12 execution beyond the later packet pause.

## Non-goals

- This amendment does not redesign UI/UX.
- It does not reduce the number of focused roots under review.
- It does not turn multiple scroll states into one image.
- It does not change the historical semantic migration oracle.
- It does not approve its own evidence or external review.

## Glossary

| Term | Meaning |
| --- | --- |
| Logical request | One original case/viewport fixture load and counter identity. There are `36`. |
| Root capture | One viewport PNG and one sidecar for one catalog root. There are `44`. |
| Root ordinal | One-based position of a root within its case's frozen catalog order. |
| Root capture ID | `<case>/<viewport>/root-<two digits>`. |
| Root artifact pair | One PNG plus its canonical render sidecar. |
| Root expansion map | The closed derivation from `36` logical requests and eleven roots to `44` root captures. |
| Historical control identity | One of the original `36` before-control case/viewport captures. |
| Repeated historical pairing | Use of one authenticated historical control identity as the before input for each of its one or two root captures. |

## Requirements

| ID | Requirement |
| --- | --- |
| `REQ-013` | Recover every focused root with independently reviewable, target-visible viewport evidence. |
| `CFR-058` | Preserve exactly `36` logical fixture requests while emitting exactly `44` root captures. |
| `CFR-059` | Derive every root capture ID and root selector from the frozen catalog without an arbitrary selector input. |
| `CFR-060` | Preserve production UI, selection fixture, viewport catalog, historical artifacts, runtime isolation, and fail-soft behavior. |
| `CFR-061` | Compare exactly `81` historical page items and `44` root-level control items while preserving the legacy semantic oracle. |

`CFR-058`, `CFR-059`, and `CFR-061` supersede the parent plan's `CFR-055`.
The parent requirements `REQ-012` and `CFR-051..054,CFR-056,CFR-057` remain
active and are imported without reinterpretation.

## Closed root expansion contract

The frozen case order remains the exact current
`worker_capture_profile_rows("scripts/ui_ux_selection_fixture_app.py")`
order:

```text
ai-chat-settings-controls
analytics-controls
institutions-controls
knowledge-graph-controls
options-cockpit-controls
radar-controls
retro-controls
risk-guard-controls
stock-checkup-controls
```

Each case expands over the exact current viewport order
`desktop,mobile,narrow,tablet`. Each logical row then expands over its case's
catalog roots in ordinal order:

| Case | Root ordinal | Root selector | Root captures |
| --- | ---: | --- | ---: |
| `ai-chat-settings-controls` | `01` | `.st-key-ai_chat_mode` | `4` |
| `analytics-controls` | `01` | `.st-key-adb_table` | `4` |
| `institutions-controls` | `01` | `.st-key-inst_view` | `4` |
| `knowledge-graph-controls` | `01` | `.st-key-kg_view_mode` | `4` |
| `knowledge-graph-controls` | `02` | `.st-key-kg_label_mode` | `4` |
| `options-cockpit-controls` | `01` | `.st-key-cockpit_price_view_NVDA` | `4` |
| `radar-controls` | `01` | `.st-key-radar_source` | `4` |
| `radar-controls` | `02` | `.st-key-radar_view` | `4` |
| `retro-controls` | `01` | `.st-key-retro_validation_lane` | `4` |
| `risk-guard-controls` | `01` | `.st-key-rg_source` | `4` |
| `stock-checkup-controls` | `01` | `.st-key-checkup_mode` | `4` |

The exact totals are:

| Quantity | Exact value |
| --- | ---: |
| Logical cases | `9` |
| Catalog roots | `11` |
| Viewports | `4` |
| Logical fixture requests | `36` |
| Root captures | `44` |
| Root artifact pairs | `44` |
| Root artifacts | `88` |
| Corrected manifest leaves | `89` |
| Historical page comparison items | `81` |
| Root-level control comparison items | `44` |
| Total comparison/review items | `125` |
| Screenshot-binding passes | `44` |
| Exact pre/post projections | `88` |

Every root capture ID has the exact form:

```text
<case>/<viewport>/root-<ordinal>
```

Examples:

```text
analytics-controls/mobile/root-01
radar-controls/mobile/root-01
radar-controls/mobile/root-02
knowledge-graph-controls/desktop/root-02
```

The mapper MUST reject:

- a case, viewport, route, callable, or selector not in the authenticated
  Sequence 12 catalog;
- a missing, duplicate, reordered, zero, or out-of-range root ordinal;
- a caller-supplied selector that is not derived from the authenticated row;
- any cardinality other than `36/44/88/89`;
- a duplicate logical request, root capture ID, staging path, or manifest path.

### Canonical root-expansion projection

The derived projection is an ordered JSON array with one row per root
capture. Each row has exactly these keys:

```text
callable,case,fixtureEntrypoint,logicalCaptureId,rootCaptureId,
rootOrdinal,rootSelector,route,viewport
```

`viewport` has exactly `height,name,width`. Rows follow the frozen logical
request order above and then ascending root ordinal. Canonical bytes are
UTF-8 JSON with object keys sorted lexicographically, compact separators,
no insignificant whitespace, no trailing newline, and no Unicode escaping
unless required by JSON.

For the exact currently authenticated catalog, the projection is:

```text
rows: 44
bytes: 16576
sha256: 13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca
```

Its first row is:

```json
{"callable":"today_decision.render","case":"ai-chat-settings-controls","fixtureEntrypoint":"scripts/ui_ux_selection_fixture_app.py","logicalCaptureId":"ai-chat-settings-controls/desktop","rootCaptureId":"ai-chat-settings-controls/desktop/root-01","rootOrdinal":1,"rootSelector":".st-key-ai_chat_mode","route":"/__selection__/ai-chat-settings","viewport":{"height":900,"name":"desktop","width":1440}}
```

Its last row is:

```json
{"callable":"stock_checkup.render","case":"stock-checkup-controls","fixtureEntrypoint":"scripts/ui_ux_selection_fixture_app.py","logicalCaptureId":"stock-checkup-controls/tablet","rootCaptureId":"stock-checkup-controls/tablet/root-01","rootOrdinal":1,"rootSelector":".st-key-checkup_mode","route":"/__selection__/stock-checkup","viewport":{"height":1024,"name":"tablet","width":768}}
```

The runner and worker independently derive these bytes from their
descriptor-authenticated catalog authority and require the exact digest and
size. The digest is stored directly in the amended intent, checkpoint,
manifest, report, and stack contract; no component may accept a caller-
supplied projection or digest.

## Worker and artifact contract amendment

### Logical request boundary

The runner still launches exactly one browser worker per original
case/viewport identity. The selection fixture, readiness marker, render
generation, provider/mutator counters, route, and callable remain bound to
that logical identity.

Legacy/full-page workers retain request schema
`quant-radar-ui-ux-browser-request/v1`. The corrected root worker uses
`quant-radar-ui-ux-browser-request/v2` with the exact top-level keys:

```text
schemaVersion,requestId,fixtureEntrypoint,case,route,viewport,appOrigin,rootOutputs
```

`requestId` remains the logical `<case>/<viewport>` identity. `rootOutputs`
is an ordered list of length one or two. Each row has exactly:

```text
rootCaptureId,rootOrdinal,rootSelector,staging
```

`staging` has exactly `png,renderSidecar`. The path pattern is:

```text
<owned-stage>/<case>/<viewport>/root-<ordinal>/capture.png
<owned-stage>/<case>/<viewport>/root-<ordinal>/render.json
```

The runner derives the complete request from the authenticated catalog. The
worker independently derives the expected root rows from its own frozen
catalog and requires byte-equivalent scalar values, order, and staging
cardinality. Public CLI input cannot provide a selector, ordinal, root count,
or staging path. The launch command repeats `--allow-staging-path` exactly
twice per expected root and binds the exact logical request ID.

### Ordered root capture loop

After the existing semantic, keyboard, selection-restoration, and temporary
scroll audit succeeds for every case control, the worker MUST process roots
in frozen catalog order:

1. Select exactly one audited control row by its catalog root ordinal.
2. Re-resolve that one root and its exact targets.
3. Position that root and targets into one unchanged catalog viewport.
4. Wait for fonts, app readiness, root geometry, and the complete DOM
   projection to satisfy the bounded quiet window.
5. Snapshot the root-only focused binding and complete node projection.
6. Take one viewport screenshot with animations disabled and caret hidden.
7. Snapshot the same binding and node projection again.
8. Require exact pre/post equality.
9. Canonicalize one root-only render v2 sidecar with focused evidence v3.
10. Stage the catalog-derived PNG/sidecar pair create-once.
11. Continue to the next root without restoring the previous scroll
    position. The next root is independently positioned and rebound.

No screenshot or sidecar from a failed root loop may enter a passed manifest.
Failure of either root in a multi-root request fails that complete logical
request and the corrected capture lifecycle.

### Sidecar identity

Parent focused evidence v2 requires every case root in one screenshot binding.
It cannot truthfully represent this amendment. Corrected root sidecars
therefore use:

```text
render schema: quant-radar-ui-ux-render/v2
focused schema: quant-radar-ui-ux-focused-controls/v3
screenshot binding: quant-radar-ui-ux-focused-screenshot-binding/v1
```

Historical render v1 and focused v1 remain historical inputs. Parent focused
v2 remains readable for implementation fixtures but is not minted into the
amended passed manifest. The amended worker may mint only render v2 plus
focused v3.

Each corrected root sidecar contains:

- the original `case`, route, callable, viewport, stable state, counters, and
  logical fixture identity;
- exact identity fields `logicalCaptureId,rootCaptureId,rootOrdinal,rootSelector`;
- exactly one `capturedControl` focused row;
- exactly one `screenshotBinding.roots` row;
- only scroll entries for that root;
- the complete screenshot-time DOM projection;
- exact binding-to-node equality for that root.

Render v2 has the exact top-level keys:

```text
schemaVersion,identity,viewport,readiness,nodes,stableState,
providerCounters,mutatorCounters,runtimeProjection,counterProvenance,
rootCapture,controlEvidence,caseSemanticProjection
```

`identity`, `viewport`, `readiness`, `nodes`, `stableState`,
`providerCounters`, `mutatorCounters`, `runtimeProjection`, and
`counterProvenance` retain the parent render contract. In the worker-staged
form `providerCounters` and `mutatorCounters` are empty and
`counterProvenance` is `null`; the descriptor-authenticated coordinator
replaces all three fields before a final sidecar can be published.
`rootCapture` has exactly:

```text
logicalCaptureId,rootCaptureId,rootOrdinal,rootSelector,
rootExpansionSha256
```

Focused evidence v3 retains the v2 control row and screenshot-binding
validators but contains exactly one catalog control. It has the exact keys
`schemaVersion,case,projection,controls,screenshotBinding`; `controls` and
`screenshotBinding.roots` each have length one and carry the same root
selector as `rootCapture`.

Before the first root-positioning step, the worker also captures one closed
`caseSemanticProjection` after the existing audit has restored selection and
scroll state. It includes the logical case/viewport identity, all case
controls in catalog order, the complete semantic node projection, stable
state, provider/mutator counters, readiness, and normalized runtime
projection. It has no PNG reference or screenshot-binding claim. Every root
sidecar for one logical request embeds byte-identical canonical
`caseSemanticProjection` bytes.

`caseSemanticProjection` uses schema
`quant-radar-ui-ux-case-semantic-projection/v1` and has the exact keys:

```text
schemaVersion,identity,readiness,nodes,stableState,providerCounters,
mutatorCounters,runtimeProjection,counterProvenance,controlEvidence
```

Its `identity` has exactly
`fixtureEntrypoint,logicalCaptureId,case,route,callable,viewport`.
`controlEvidence` is the complete case-level
`quant-radar-ui-ux-focused-controls/v1` semantic projection with all catalog
controls and without `screenshotBinding`. The worker stages empty counter
maps and `counterProvenance:null` in both sibling copies; the coordinator
authenticates the one logical counter document, enriches the projection once,
then inserts the same canonical enriched projection into every final sibling
sidecar. Equality is over the compact canonical JSON serialization of that
nested value. A worker-authored nonempty counter or non-null provenance claim
fails.

The counter provenance binds the logical request identity. Both root
sidecars in a multi-root request repeat the same authenticated logical
counter projection. Aggregation MUST deduplicate by logical request ID and
require repeated values to be exactly equal; it MUST NOT sum them twice or
claim a duplicate provider call. The finalizer authenticates the one-to-one
logical counter bundle and the one-to-many logical-to-root mapping
separately.

The render-v2 sidecar and worker-response maximum byte bounds MUST be measured
against the largest two-root case before stack publication. A bound may
increase only to one fixed documented integer that passes over-limit and
truncation mutation tests; it cannot be calculated from untrusted input.

### Worker response and staging

The corrected worker response uses schema
`quant-radar-ui-ux-browser-response/v2`. A staged response has the exact keys
`schemaVersion,requestId,status,rootArtifacts`. It contains
an ordered `rootArtifacts` list of length one or two. Each row has exactly:

```text
rootCaptureId,logicalCaptureId,rootOrdinal,rootSelector,png,renderSidecar
```

The response decoder requires exact catalog order, safe distinct staging
paths, exact request ownership, and complete path equality with the
coordinator's predeclared output plan. Historical request/response v1 remains
readable only for legacy workflows and cannot describe corrected root
artifacts. After a v2 request is parsed, a failed v2 response retains the
existing closed `requestId,status,error` failure shape under response schema
v2; it never exposes internal paths, selectors, exception text, or partial
artifact rows.

## Capture and reconcile lifecycle amendment

The public corrected capture command remains restricted to:

```text
profile: ux1b-selection-controls
phase: postcontrol
browser: chromium
logical requests: 36
root captures: 44
artifacts: 88
manifest leaves: 89
capture stack: seq12
```

It reuses the parent plan's descriptor ownership, isolation, network denial,
bounded process supervision, runtime reauthentication, intent/checkpoint,
exclusive publication, reconcile, and process-quiescence contracts.

The intent and checkpoint distinguish:

- `plannedLogicalRequests:36`;
- `plannedRootCaptures:44`;
- `completedLogicalRequests`;
- `completedRootCaptures`;
- the exact ordered root expansion digest.

A logical request is complete only when all of its root artifact pairs reopen
and authenticate. Reconcile may resume only the exact active prefix already
authorized by the parent lifecycle. It cannot split, skip, reorder, or
implicitly retry one root from a failed logical request.

The finalizer authenticates all `88` artifact leaves before publishing the
create-once `89`-leaf manifest bundle. Partial root output remains
nonterminal and cannot be represented as a passed capture.

## Comparator amendment

### Input roles

The comparator keeps the parent plan's exact historical and corrected input
roles:

| Input | Stack |
| --- | --- |
| Historical before pages | Historical |
| Historical accepted after pages | Historical |
| Historical before controls | Historical |
| Corrected root after controls | Sequence 12 |
| Historical catalog | Historical |
| Sequence 12 catalog | Sequence 12 |

### Root-level historical pairing

The `36` historical before-control identities are immutable. The comparator
derives the same root expansion map from the authenticated historical and
Sequence 12 catalogs. For a single-root case it creates one control comparison
item. For `radar-controls` and `knowledge-graph-controls` it creates two
control comparison items per viewport.

Each root-level review/geometry item:

- reuses the exact authenticated historical before PNG reference for its
  logical case/viewport;
- uses one distinct corrected root PNG and sidecar;
- records `logicalCaptureId`, `rootCaptureId`, `rootOrdinal`, and
  `rootSelector`;
- never mutates, rewrites, copies, or republishes the historical artifact.

Repeated historical pairing is a comparison relation, not a new historical
artifact or counter claim.

### Frozen semantic-oracle preservation

The frozen legacy semantic oracle MUST NOT be called once per root. That would
change its historical case-level input contract and falsely turn `36` logical
control comparisons into `44` semantic comparisons.

For each logical corrected request, the comparator:

1. Authenticates every root sidecar in exact catalog order.
2. Requires their embedded `caseSemanticProjection` values to be
   byte-identical.
3. Requires the projection to contain the complete one- or two-control
   catalog row and the original logical case/viewport identity.
4. Converts that closed projection to the frozen oracle's existing
   in-memory semantic input without consulting a PNG, path, or untrusted
   selector.
5. Calls the frozen semantic oracle exactly once for the logical identity.

The nested legacy semantic result therefore remains exactly `117` logical
comparisons: `81` pages plus `36` controls. Root screenshot geometry,
binding, and reviewer-image comparison is a separate `44`-item audit. The
outer amended report has `125` reviewer comparison items.

Tests freeze the source spans, signatures, and byte outputs of the legacy
catalog validation, canonical semantic projection, selection/accessibility
comparison, volatility validation, and layout-safety callables. The adapter
may translate the closed `caseSemanticProjection` into their existing input
shape, but it cannot alter those callables or their outputs.

### Report totals and audits

The amended outer report uses schema
`quant-radar-ui-ux-control-migration-root-report/v1`. Its exact top-level keys
are:

```text
schemaVersion,status,kind,coveredProfiles,comparedCaptures,
pageComparisons,controlRootComparisons,captureStackTransition,
sourceTransition,rootExpansion,allowedBoundaryTranslations,
migrationGeometryContract,legacySemanticOracle,screenshotBindingAudit,
excludedArtifacts
```

`status` is `passed`, `kind` is `control-migration`, `rootExpansion` is the
exact `{rows,size,sha256}` projection reference above, and
`excludedArtifacts` contains the exact rejected Sequence 11 after-control
manifest reference. Historical schema-less reports remain immutable readable
inputs; they are not emitted by the amended comparator.

The corrected report MUST contain:

```text
comparedCaptures: 125
pageComparisons: 81
controlRootComparisons: 44
legacySemanticOracle.comparedCaptures: 117
legacySemanticOracle.pageComparisons: 81
legacySemanticOracle.controlComparisons: 36
screenshotBindingAudit.passedRootCaptures: 44
screenshotBindingAudit.unboundRootCaptures: 0
screenshotBindingAudit.exactPrePostProjections: 88
```

It also records:

- the exact historical-to-Sequence-12 stack transition;
- the exact parent-plan-to-amendment authority chain;
- the unchanged catalog semantics plus exact root expansion digest;
- the exact historical/current source transition;
- the unchanged legacy semantic-oracle source spans and outputs;
- the newly authenticated root-level geometry/volatility profile;
- exclusion of the rejected Sequence 11 after-controls manifest.

The comparator MUST reject:

- `117`, `124`, `126`, or any count other than `125`;
- a nested legacy semantic count other than `117`;
- an unexpanded multi-root case;
- a missing or duplicate root capture;
- a corrected sidecar containing both multi-root controls;
- one corrected PNG reused for two root captures;
- non-identical case semantic projections within one logical request;
- logical counters aggregated once per root rather than once per request;
- historical pairing to the wrong case or viewport;
- same-stack substitution or a third stack;
- catalog, fixture, viewport, production source, or semantic-oracle drift;
- any missing binding, off-viewport target, or pre/post mismatch.

## Review packet amendment

`prepare-review` creates exactly `125` items:

- `81` unchanged page comparison items;
- `44` root-level control comparison items.

For the two multi-root cases, the same authenticated historical before PNG is
intentionally referenced by two distinct review items. Each item has a unique
root capture ID, selector, corrected PNG, and corrected sidecar authority.

The packet summary explains repeated historical pairing. The packet does not
present two corrected root screenshots as one composite image. Formal
execution still stops at the parent plan's `R3_PACKET` state with new intake,
review, candidate, and root absent.

The amended packet uses
`quant-radar-ui-ux-review-packet/v2`; review packet v1 remains immutable and
readable for historical workflows. Packet v2 retains the exact v1 top-level
keys and requires exactly five authenticated inputs and `125` items.

Every page item has exactly:

```text
kind,id,before,after,dimensions,changed
```

with `kind:"page"`. Every root-level control item has exactly:

```text
kind,id,logicalCaptureId,rootCaptureId,rootOrdinal,rootSelector,
before,after,afterSidecar,dimensions,changed
```

with `kind:"control-root"` and `id == rootCaptureId`. Both PNG artifact refs
use the existing exact `path,sha256,size` contract, as does
`afterSidecar`. `dimensions` has exact positive integer `width,height`; the
historical before PNG and corrected after PNG must both equal the catalog
viewport dimensions. The authenticated historical manifests confirm this
property, including Radar mobile `390x844`; unequal dimensions fail before
packet publication.

The `itemSetSha256` remains the SHA-256 of canonical compact JSON over the
lexicographically sorted item IDs. Packet v2 rejects v1 item shapes, `117`
items, root metadata on a page item, missing root metadata on a control item,
or two root items that reuse one corrected PNG or corrected sidecar.
Manual-review v2 may bind a packet v2 by exact packet ref without changing its
decision-item shape.

## Authority, stack, and source rules

- The parent plan and ledger remain immutable imported authorities.
- This amendment and its sibling ledger join the Sequence 12 authorization
  package and supplemental source projection.
- The final Sequence 12 authorization marker binds both parent and amendment
  refs.
- The historical capture-stack contract remains byte-identical.
- The Sequence 12 stack is published only after all nine member bytes pass
  discovery and root-capture real smoke.
- The logical control catalog remains unchanged. The root expansion map is a
  derived, digest-bound execution projection.
- `scripts/ui_ux_selection_fixture_app.py`, production `ui/`, production
  `api/`, configuration, dependencies, providers, and theme sources MUST
  remain byte-identical to the parent preimage.
- The cleaned current runtime authority and all before/after runtime checks
  remain exactly as specified by the parent plan.

## Acceptance criteria

### `AC-SEQ12A-001` — closed root expansion

Given the authenticated nine-case, eleven-root, four-viewport catalog, when
the root mapper runs, then it returns exactly `36` logical requests and `44`
ordered unique root capture IDs with no caller-selected root.

### `AC-SEQ12A-002` — independently bound root screenshots

Given any logical request, when its corrected worker runs, then it emits one
artifact pair per catalog root, and every pair binds exactly one root and all
of that root's targets to one stable viewport state while every sibling
sidecar repeats the exact same case semantic projection.

### `AC-SEQ12A-003` — complete corrected capture

Given an accepted Sequence 12 preflight, when capture or reconcile completes,
then `36` logical requests produce exactly `44` root captures, `88` artifacts,
and one `89`-leaf passed manifest with all child processes quiescent.

### `AC-SEQ12A-004` — complete root-level comparison

Given the exact historical manifests and corrected root manifest, when the
cross-stack comparator runs, then it compares `81` page items and `44`
root-level control items, reports `125`, and preserves the frozen `117`
logical-comparison semantic oracle.

### `AC-SEQ12A-005` — independent `125`-item review

Given a passed `125`-item report, when `prepare-review` runs, then one
create-once `125`-item packet is reopened exactly and execution stops before
external intake.

### `AC-SEQ12A-006` — protected source and legacy compatibility

Given the complete diff and formal inputs, when scope, legacy, fail-soft,
runtime, syntax, and dependency gates run, then the parent plan/ledger,
historical stack/artifacts, selection fixture, production UI/API/theme, and
legacy v1 behavior remain exact.

These acceptance criteria supersede parent criteria
`AC-SEQ12-002,AC-SEQ12-006,AC-SEQ12-007,AC-SEQ12-008` only where their
cardinality or multi-root unit differs. Parent criteria
`AC-SEQ12-001,AC-SEQ12-003..005,AC-SEQ12-009,AC-SEQ12-010` remain active.

## Implementation map

| ID | Planned implementation |
| --- | --- |
| `IMPL-091` | Closed catalog-derived `36` logical to `44` root capture expansion mapper and digest. |
| `IMPL-092` | Corrected request v2, response v2, render v2, focused v3, and catalog-derived staging contracts. |
| `IMPL-093` | Case semantic projection plus root-only positioning, quiet-window binding, screenshot, sidecar, and pre/post equality loop. |
| `IMPL-094` | Capture intent/checkpoint/reconcile/finalizer accounting for `36/44/88/89`. |
| `IMPL-095` | Historical-to-root review pairing plus deduplicated case-level frozen semantic comparator adapter. |
| `IMPL-096` | `125`-item report, review packet, summaries, and packet-pause validation. |
| `IMPL-097` | Amendment authority, source projection, stack binding, coordinator, CLI, and Make contract updates. |
| `IMPL-098` | Red-first, Chromium, mutation, lifecycle, compatibility, and protected-source verification. |

Parent implementation nodes remain active except that
`IMPL-080,IMPL-081,IMPL-086,IMPL-087,IMPL-089` consume the amended root-level
contracts above.

## Test map

| ID | Test obligation |
| --- | --- |
| `TEST-120` | Reproduce the real Radar mobile union overflow and prove composite multi-root viewport capture fails before publication. |
| `TEST-121` | Prove the closed expansion has nine cases, eleven roots, four viewports, `36` logical requests, and `44` ordered unique root IDs. |
| `TEST-122` | Unit-test request/response/render/focused schemas, one-root/two-root plans, staging order, bounds, duplicates, omissions, failure privacy, and arbitrary-selector rejection. |
| `TEST-123` | Real Chromium proves all `44` root captures are target-visible, sibling case-semantic projections are exact, and pre/post binding plus complete nodes are equal. |
| `TEST-124` | Capture/reconcile lifecycle verifies `36/44/88/89`, partial second-root failure, collisions, busy state, crash, runtime drift, and process quiescence. |
| `TEST-125` | Comparator accepts only `81+44=125` review items, runs exactly `81+36=117` legacy semantic comparisons, and preserves byte-identical oracle outputs. |
| `TEST-126` | Mutation tests reject wrong historical pairing, reused PNG, dual-root sidecar, semantic-sibling drift, double-counted counters, missing root, wrong ordinal, source drift, and count drift. |
| `TEST-127` | Public report/packet fixtures reach exactly `R3_PACKET` with `125` unique items and no intake/review/candidate/root. |
| `TEST-128` | Parent plan/ledger, Sequence 11 chain, historical stack, legacy commands, v1 readers, and fixture/catalog bytes remain exact. |
| `TEST-129` | Full recovery, fail-soft, source-scope, Python 3.10, dependency, dirty-worktree, static, and diff gates pass. |

Parent tests remain active. `TEST-120..129` supersede the cardinality portions
of `TEST-109,TEST-113,TEST-115,TEST-118`; all other parent test obligations
remain unchanged.

## Given-When-Then scenario matrix

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| `SC-AC-SEQ12A-001-HP-001` | Exact authenticated catalog | Mapper expands it | Exact `36/44` ordered mapping |
| `SC-AC-SEQ12A-001-NP-001` | Duplicate or external selector | Mapper expands it | Fail before staging |
| `SC-AC-SEQ12A-002-HP-001` | Single-root request | Worker captures it | One exact artifact pair |
| `SC-AC-SEQ12A-002-HP-002` | Multi-root request | Worker captures it | Two ordered independent pairs |
| `SC-AC-SEQ12A-002-NP-001` | Root or node changes across screenshot | Worker captures it | Complete logical request fails |
| `SC-AC-SEQ12A-003-HP-001` | Exact active capture prefix | Capture completes | `36/44/88/89`, quiescent |
| `SC-AC-SEQ12A-003-NP-001` | Second root fails | Finalizer evaluates output | No passed manifest |
| `SC-AC-SEQ12A-003-EP-001` | Exact nonterminal prefix | Reconcile runs | Resume only authorized prefix |
| `SC-AC-SEQ12A-004-HP-001` | Exact old/new artifacts | Comparator runs | `125` review items and exact nested `117` semantic result |
| `SC-AC-SEQ12A-004-NP-001` | Wrong old-to-root pairing | Comparator runs | No report publication |
| `SC-AC-SEQ12A-004-NP-002` | Semantic oracle changes | Compatibility gate runs | Fail closed |
| `SC-AC-SEQ12A-005-HP-001` | Passed `125` report | Packet prepares | Exact `125`, state `R3_PACKET` |
| `SC-AC-SEQ12A-005-NP-001` | Packet count or root identity differs | Packet reopens | Fail before intake |
| `SC-AC-SEQ12A-006-HP-001` | Complete planned diff | Protected-source gate runs | No protected byte changed |
| `SC-AC-SEQ12A-006-NP-001` | Fixture, UI, API, stack, or parent drift | Any amended command runs | Fail before later leaf |

## Affected files

### Planned implementation edits

```text
Makefile
scripts/ui_ux_browser_worker.py
scripts/ui_ux_evidence.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_evidence.py
scripts/test_ui_ux_snapshot_matrix.py
scripts/test_ui_ux_theme_handoff.py
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-multi-root-capture-cardinality-amendment.md
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-multi-root-capture-cardinality-amendment.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-seq12.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

### Read-only protected paths

```text
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.md
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
scripts/ui_ux_selection_fixture_app.py
all production ui/, api/, provider, selector, configuration, dependency, and theme-source files
all Sequence 8/9/10/11 authorization, Tier, preflight, capture, report, packet, intake, and review artifacts
all accepted 81-page and historical before-control capture artifacts
```

## Implementation sequence

### Phase A0 — amendment authority gate

- Reopen the exact parent plan/ledger and rejected Sequence 11 chain.
- Reconfirm the Radar mobile blocker with disposable evidence.
- Require the Sequence 12 stack, authorization candidate, Tier, preflight,
  corrected manifest, report, and packet to remain absent.
- Bind this amendment and ledger only after exact-byte maintainer acceptance.

**Gate:** any parent, predecessor, runtime, protected-source, or formal
namespace drift blocks execution.

### Phase A1 — red root-expansion tests

- Add `TEST-120..129` as fail-first tests.
- Freeze the exact eleven-root/four-viewport map.
- Freeze the legacy semantic-oracle spans and existing worker v1 behavior.
- Require failures to point to missing root expansion, multi-artifact staging,
  cardinalities, comparison pairing, or packet mapping.

**Gate:** tests cannot patch the real review-intake namespace, write into
`.venv`, or modify a protected fixture/source file.

### Phase A2 — root evidence units

- Implement `IMPL-091..093`.
- Keep one logical fixture load and audit all controls once.
- Freeze one complete post-audit case semantic projection before root
  positioning and require sibling copies to remain byte-identical.
- Stage one root artifact pair at a time in catalog order.
- Require render v2, root-only focused v3 binding, and complete node pre/post
  equality.
- Fail the logical request if any root pair fails.

**Gate:** all `44` real Chromium root captures pass; composite Radar mobile
still fails as a negative oracle.

### Phase A3 — capture lifecycle

- Implement `IMPL-094`.
- Extend intent, checkpoint, reconcile, response, counter, and final manifest
  validation with the exact root expansion digest.
- Prove `36/44/88/89` and child quiescence.

**Gate:** partial, duplicate, reordered, collision, crash, busy, and runtime
drift matrices publish no passed manifest.

### Phase A4 — comparator and review

- Implement `IMPL-095..097`.
- Run the frozen semantic oracle exactly once per logical control identity
  from the deduplicated case semantic projection.
- Pair historical PNG refs to root captures only for geometry and review.
- Produce `81+44=125` report items and packet items.
- Preserve exact source/stack transitions and formal `R3_PACKET` pause.

**Gate:** all mapping, reuse, stack, source, binding, count, and semantic
mutants fail before later publication.

### Phase A5 — stack, authorization, and verification

- Stabilize all nine stack members.
- Pass discovery plus disposable root-capture real smoke.
- Publish/reopen the distinct Sequence 12 stack create-once.
- Embed its exact hash only in the non-member coordinator.
- Run complete parent and amendment verification.
- Generate the amended Sequence 12 authorization candidate last.

**Gate:** all available checks pass, protected bytes remain exact, no
temporary namespace remains, and no blocking review finding remains.

### Phase A6 — later formal execution

- Report the amended authorization candidate SHA-256, size, and mode.
- Obtain maintainer acceptance of those exact bytes.
- Bootstrap and freshly verify Tier/preflight.
- Run corrected root capture and reopen `88/88` artifacts.
- Publish/reopen the `125`-item report and packet.
- Stop exactly at `R3_PACKET`.

**Gate:** intake, manual review, candidate, and root remain absent.

## Verification commands

At minimum:

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

Additional mandatory gates:

- Python 3.10 AST parse for every changed Python file;
- `py_compile` and `tabnanny`;
- whitespace and diff checks;
- exact parent plan/ledger and historical stack hashes;
- exact protected selection fixture, production UI/API/theme, dependency, and
  configuration preimages;
- current runtime-tree digest before and after every write-capable child;
- `44/44` real Chromium root matrix;
- `36/44/88/89` production-shaped capture/reconcile fixture;
- `81/44/125` comparator and review packet fixture;
- nested legacy semantic result remains exactly `81/36/117`;
- multi-root sibling semantic projections and counters are identical and
  deduplicated once per logical request;
- no Sequence 12 formal artifact during implementation verification.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A second root causes duplicate provider calls | One logical fixture request audits once and emits multiple root pairs. |
| Root outputs are reordered or omitted | Closed ordinal map, exact response order, expansion digest, and finalizer cardinality. |
| Historical artifact appears duplicated | Repeat only its immutable reference in comparison relations; never copy or republish bytes. |
| Comparator semantics weaken when sliced by root | Do not slice the oracle; deduplicate one complete case semantic projection and retain exact `117` logical calls. |
| One root passes while its sibling fails | Logical request is atomic for lifecycle completion; no partial passed manifest. |
| Worker response becomes an arbitrary output API | Output rows are predeclared from the authenticated catalog; no public selector/path input. |
| Review packet hides context | Each item records logical ID, root ID, ordinal, selector, before ref, after ref, and dimensions. |
| Stack is frozen before member bytes stabilize | Root real smoke precedes create-once publication; coordinator hash edit occurs afterward. |

## Rollback

Before Sequence 12 Tier publication:

- remove only create-once amendment implementation outputs that were produced
  by the current session and are still descriptor-authenticated;
- retain this reviewed amendment, its ledger, the parent plan/ledger, and all
  historical evidence;
- never modify production UI/fixture files to restore a green capture.

After Sequence 12 Tier publication:

- do not overwrite or delete the Tier, preflight, stack, capture, report, or
  packet;
- stop and prepare a new reviewed correction that imports the retained failed
  state.

No Git reset, checkout, destructive cleanup, historical artifact rewrite, or
runtime-tree mutation is authorized.

## Success metrics

| Metric | Target | Measurement |
| --- | ---: | --- |
| Catalog roots represented | `11/11` | Authenticated root expansion map |
| Viewport/root evidence | `44/44` | Corrected passed manifest |
| Root artifacts reopened | `88/88` | Descriptor-authenticated finalizer |
| Unbound focused screenshots | `0` | Report binding audit |
| Exact pre/post projections | `88/88` | Report binding audit |
| Review comparisons | `125/125` | Report and packet validation |
| Protected source drift | `0` | Exact preimage scope gate |
| Traceability coverage | `10000` basis points | Sibling ledger |

## Dependencies

- Exact parent plan and ledger.
- Exact rejected Sequence 11 report, packet, intake, and manual review.
- Historical page and before-control manifests/artifacts.
- Exact historical capture-stack contract.
- Cleaned current runtime authority from the parent plan.
- Playwright Chromium and existing Darwin isolation primitives.
- Maintainer acceptance of this amendment's final exact bytes.

## Review checklist

- [x] The observed geometry contradiction is reproducible.
- [x] No protected UI, fixture, viewport, or historical artifact change is
  authorized.
- [x] `36` logical requests and `44` root captures are distinguished
  consistently.
- [x] Worker staging remains catalog-derived and bounded.
- [x] Counters remain one-to-one with logical requests.
- [x] Every corrected sidecar binds exactly one root.
- [x] Multi-root logical requests fail atomically.
- [x] Comparator repeated historical pairing is explicit and immutable.
- [x] Report and packet totals are exactly `125`.
- [x] Parent requirements/tests not superseded here remain active.
- [x] Stack publication order has no hash fixed point.
- [x] Formal execution stops before external intake.
- [x] Requirements, acceptance criteria, implementation, tests, and scenarios
  are bidirectionally traceable with no gaps or orphans.

## Review findings

Review findings are recorded here before finalization. Any blocker, High, or
Medium finding must be resolved before status changes to `REVIEWED`.

| Iteration | Finding | Severity | Resolution |
| ---: | --- | --- | --- |
| `1` | Declared viewport and case order differed from the frozen worker profile order. | High | Bound the exact existing case and viewport order and reordered the expansion table. |
| `1` | Parent focused v2 requires all case roots and cannot represent one root truthfully. | Blocker | Added corrected render v2 and focused v3; parent v2 is readable but not minted into the amended manifest. |
| `1` | Calling the frozen semantic oracle once per root would change its case-level input and output cardinality. | Blocker | Added a byte-identical case semantic projection, exact once-per-logical deduplication, nested `117` oracle result, and separate `44` root geometry/review audit. |
| `1` | Corrected request, staging, response, and failure shapes were not closed. | High | Defined request v2, response v2, exact keys, row lengths, staging paths, launch binding, and privacy-preserving failures. |
| `1` | Repeating logical counters in sibling sidecars could cause double aggregation. | Medium | Required byte-identical repeated projections, deduplication by logical ID, and explicit double-count mutations. |
| `2` | The root-expansion digest was named but its canonical row shape, encoding, size, and expected digest were not frozen. | High | Closed the nine-key row, order, encoding, first/last rows, exact `16576` bytes, and SHA-256 `13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca`. |
| `2` | Existing review-packet v1 accepts only the old five-key item shape and exactly `117` items, so it cannot carry root identity or `125` items. | Blocker | Added a distinct review-packet v2 with discriminated page/root item shapes, exact `5/125` cardinality, preserved v1 history, and unchanged manual-review decision rows. |
| `2` | The outer amended report and render/case-semantic payloads were not closed schemas. | High | Added distinct exact report v1, render v2, focused v3, root identity, and case-semantic projection contracts. |
| `2` | The review dimensions relation between one historical case PNG and each corrected root PNG was implicit. | Medium | Required both artifacts to equal the authenticated catalog viewport dimensions and recorded the observed Radar mobile `390x844` historical authority. |
| `2` | The dedicated snapshot-runner protocol test file was missing from planned edits and commands. | Medium | Added `scripts/test_ui_ux_snapshot_matrix.py` to the planned surface and mandatory verification. |

Review iteration 3 rechecked the parent authority, exact expansion bytes,
request/response and sidecar closure, counter ownership, report/packet item
shapes, historical dimensions, file scope, lifecycle pause, test surface, and
bidirectional trace structure. No unresolved Blocker, High, or Medium finding
remains. This review does not authorize implementation or formal publication.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `0.1-review-candidate` | 2026-07-28 | Initial Sequence 12 amendment for root-level captures and corrected cardinalities. |
| `0.2-review-candidate` | 2026-07-28 | Closed ordering, schema, semantic-oracle, worker protocol, and counter-deduplication findings. |
| `0.3-review-candidate` | 2026-07-28 | Closed canonical expansion bytes, report/packet item schemas, sidecar projection shapes, dimensions, and snapshot-runner tests. |
| `1.0-reviewed` | 2026-07-28 | Third review found no unresolved Blocker, High, or Medium issue; frozen for exact-byte maintainer acceptance. |

## Next handoff

After a clean blocking review:

1. Freeze this document and its sibling ledger.
2. Report exact SHA-256, size, and mode.
3. Wait for maintainer acceptance of those exact bytes.
4. Hand the accepted amendment to Builder for parent-plan continuation.
