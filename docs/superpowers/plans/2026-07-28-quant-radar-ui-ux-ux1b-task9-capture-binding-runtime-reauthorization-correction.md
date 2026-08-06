# Quant Radar UX-1B Task 9 Capture-Binding and Runtime Reauthorization Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.0-reviewed` |
| Status | Blocking review passed; implementation not started |
| Authorization | Repository maintainer instructed the next correction to proceed |
| Author / plan reviewer | Codex |
| Approver | Repository maintainer |
| Audience | Maintainers, implementers, capture reviewers, and code reviewers |
| Sequence | `12` |
| Historical capture recovery ID | `20260725T080000Z` |
| Historical continuation ID | `20260726T210000Z` |
| Historical descriptor correction ID | `20260727T030000Z` |
| Historical lifecycle correction ID | `20260727T060000Z` |
| Capture-binding correction ID | `20260728T000000Z` |
| Capture-binding Tier ID | `20260728T001000Z` |
| Corrected focused-capture ID | `20260728T010000Z` |
| Imported predecessor | Exact rejected Sequence 11 `F3_REVIEW` chain and its complete Sequence 10/9/8 ancestry |
| Parent correction plan | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-forward-lifecycle-reauthentication-correction.md` |
| Related ledger | `docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.traceability.yaml` |

## Executive summary

Sequence 11 reached a valid external review and preserved the reviewer
decision exactly. The review accepted `113` of `117` items and rejected these
four focused captures:

```text
analytics-controls/desktop
analytics-controls/mobile
analytics-controls/narrow
analytics-controls/tablet
```

The failure is temporal. `_focused_control_layout(...)` scrolls a focused
root into the audit viewport and records its geometry. It then restores the
original internal scroll before returning. The worker projects DOM nodes and
takes the PNG only after that restoration. For Analytics, the recorded
`controlEvidence.layout.rootRect` is inside the viewport while the
screenshot-time root is far below it:

| Viewport | Historical before root Y | Rejected after root Y | Viewport height |
| --- | ---: | ---: | ---: |
| desktop | `406` | `1318` | `900` |
| mobile | `378` | `2591` | `844` |
| narrow | `378` | `2702` | `844` |
| tablet | `468` | `1387` | `1024` |

The after PNG therefore shows the Analytics page top instead of the migrated
table selector. Its sidecar was collected at a later, target-visible scroll
position. The machine report's `deltaY=8` cannot explain this capture-state
drift.

The review also wrote one Pillow bytecode cache into the authorized `.venv`.
The cache file was removed, but the runtime digest includes directory ctime.
The old runtime digest cannot be restored:

```text
historical authorized .venv tree:
d9802d618e8665deac940e1e65520f3d5aba29b8aff28fadc6f10e7c5a27f0cf

current cleaned .venv tree:
9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75
```

Sequence 12 preserves the complete rejected Sequence 11 chain as immutable
history. It introduces a screenshot-binding evidence contract, a distinct
capture-stack contract, and a separate current-runtime authority. It
recaptures all `36` focused controls under one new stack, reuses the accepted
historical `81` after-page captures, recomputes the complete `117`-item
migration report, creates a new immutable review packet, and pauses again for
independent review.

## Goals and success metrics

- Preserve the exact Sequence 11 report, packet, intake, and rejected manual
  review without edit, replacement, deletion, chmod, or hardlink change.
- Bind every focused PNG, focused DOM projection, and serialized root
  geometry to one stable target-visible viewport state.
- Require identical focused geometry and node projections immediately before
  and after `page.screenshot(...)`.
- Use viewport screenshots for focused captures and retain full-page behavior
  for page captures.
- Reauthorize the cleaned current `.venv` under Sequence 12 without changing
  historical Sequence 8/11 runtime facts.
- Publish a distinct Sequence 12 capture-stack contract; do not replace the
  historical canonical contract referenced by existing manifests.
- Capture exactly `36/36` focused controls under one new manifest and reopen
  all `72` PNG/sidecar artifacts.
- Compare exactly `117` items using the accepted historical `81` after pages,
  the historical before matrices, and the corrected `36` after controls.
- Create exactly one new `117`-item review packet and stop before external
  intake.
- Restore the permanent coordinator suite to green in the current
  post-review workspace.
- Preserve API, Streamlit fail-soft behavior, production UI, selectors,
  providers, theme source, and unrelated dirty worktree bytes.

## Scope

### In scope

- Focused screenshot/sidecar temporal binding in the browser worker.
- Focused evidence schema evolution from v1 to a backward-readable v2.
- Exact screenshot-time root rectangles, viewport dimensions, and retained
  scroll-chain offsets.
- Pre/post screenshot equality for focused node and root geometry.
- A distinct fixed Sequence 12 capture-stack contract path.
- Explicit selection of the legacy or Sequence 12 stack by the formal runner;
  no arbitrary caller-supplied contract path.
- Separate historical and current runtime-tree authorization profiles.
- A Sequence 12 Tier, preflight, capture/reconcile lifecycle, comparator,
  review packet, and root lineage.
- A fresh `36`-capture postcontrol-controls manifest.
- Cross-stack comparison limited to the exact old baseline/page stack and
  exact new focused-after stack.
- Lifecycle-aware rotation of tests whose construction-time assumptions no
  longer hold after valid external intake.
- Formal execution only through new packet creation after explicit
  authorization-byte acceptance.

### Non-goals

- No production UI, selector, provider, API, artifact-loader, or theme-source
  behavior change.
- No recapture of the accepted `81` postcontrol page artifacts.
- No edit or replacement of any Sequence 8–11 formal artifact.
- No deletion or "retry" of the rejected Sequence 11 packet/review.
- No arbitrary evidence overlay assembled from four hand-picked PNGs.
- No acceptance authored by the implementer.
- No root publication, theme batch, or semantic-theme application during
  initial Sequence 12 execution.
- No general-purpose capture-stack selector or workflow engine.
- No weakening of runtime authentication to ignore inode, mtime, or ctime.

## Glossary

| Term | Definition |
| --- | --- |
| Screenshot binding | Machine evidence that focused root geometry, projected nodes, and scroll offsets are unchanged across the screenshot operation. |
| Target-visible viewport | A viewport state where every focused root and target is inside the viewport contract. |
| Historical runtime authority | The exact `.venv` digest retained in Sequence 8/11 evidence; it remains immutable history. |
| Current runtime authority | The cleaned `.venv` digest accepted only by Sequence 12 for new execution. |
| Cross-stack comparison | Comparison of historical captures and new captures whose stack digests differ under one exact authorized transition. |
| Corrected focused manifest | The new immutable `36`-capture postcontrol manifest produced under Sequence 12. |

## Verified starting state

### Exact rejected Sequence 11 forward chain

| Artifact | SHA-256 | Size | Mode | Links |
| --- | --- | ---: | --- | ---: |
| Migration report | `512bef01319a87aee1ec16c9d687232b92c518ab1ce4b76c443633304027e5cc` | `10236` | `0600` | `1` |
| Review packet | `f0f49b57ce3b9759101283eea87897a33f39bd0cc97e33e6dc287513eba35b34` | `64334` | `0600` | `1` |
| External intake | `2c54326ec56ecfe5449026c5c360d1e4452d6b363dfd2c590739bc7314de07ea` | `23029` | `0600` | `1` |
| Manual review | `2c54326ec56ecfe5449026c5c360d1e4452d6b363dfd2c590739bc7314de07ea` | `23029` | `0600` | `1` |

The intake and manual review are byte-identical but have distinct inodes.
Their decision is `rejected`; exactly `113` items are accepted and exactly
the four Analytics focused items are rejected. The Sequence 11 candidate and
root are absent. The active state is `S11_PUBLISHED/F3_REVIEW`.

### Frozen source and capture stack

| Path | SHA-256 |
| --- | --- |
| `Makefile` | `cf2995a5eee7a8909326099f20c5ad0a9d6962c8f8f9485410a5ae151ddce7f7` |
| `scripts/ui_ux_theme_handoff.py` | `20c1069557f5c12cd7c380d2e4f74e221992ef8f93e56ba163e8a6e160ed3af1` |
| `scripts/test_ui_ux_theme_handoff.py` | `325d08921a7ac6b979033834c6d11bae3ffc8d53bdd99c8c5df55e3071756ec0` |
| `scripts/ui_ux_browser_worker.py` | `b8a70dc1fc76c8221128dace737301cda9e8cec169baf92f125ace737450b82b` |
| `scripts/ui_ux_evidence.py` | `3ae2a02b519a70f4e8ef146c486f0ad4cd306718ad5429ec20dd8ccf951f009a` |
| `scripts/ui_ux_snapshot_matrix.py` | `2184fdc8bf1617e45500a3e16a7b87ea12e6cd1c56d4dec2ed9313ff6f1aced2` |
| `scripts/ui_ux_isolation.py` | `cec1c7b6a982d34b7f84bf958cc06ddce601847947b840d754166b1f4d753497` |
| Historical capture-stack contract | `8b354ec6d7f84e4bfbd96c098ffd1dae2db0d90f7f9cf86d168bc8a9298df820` |

The historical capture-stack digest is
`69eeec0dcdffdab16d5696896cb4fc5ddb27071591953d04b4c907ea5b78055e`.
The distinct Sequence 12 capture-stack contract does not yet exist.

### Current test classification

The post-review aggregate coordinator run is `72/84`:

- six tests reject current `.venv` against the historical ctime-bound digest;
- six Sequence 11 fixture tests inspect the real, now-existing review-intake
  directory instead of their patched fixture namespace.

These are not accepted as a permanent baseline. Sequence 12 must preserve the
exact historical runtime constant, introduce a separate current profile, and
derive fixture intake paths from the patched forward paths.

## Sequence 12 authority and namespace

### Fixed authority paths

```text
Correction ID:
  20260728T000000Z

Tier ID:
  20260728T001000Z

Corrected focused-capture ID:
  20260728T010000Z

Lease:
  .claude/ui_snapshots/ux1b/recovery/.capture-binding-correction-20260728T000000Z.lease

Preflight:
  .claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-preflight-20260728T000000Z.json

Tier bundle:
  .claude/ui_snapshots/ux1b/recovery/theme-handoff-capture-binding-correction-prechange-20260728T001000Z/

Authorization candidate:
  docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-seq12.md

Sequence 12 capture stack:
  docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json
```

All are create-once. A partial or semantically different collision is
retained and blocks execution. No Sequence 11 path is reused as a Sequence 12
destination.

The Sequence 12 initial namespace does not require the shared
`.claude/ui_snapshots/ux1b/review-intake` directory to be absent. That
directory now exists legitimately, is owned by the current user/group, has
mode `0700`, and contains the retained Sequence 11 intake. Preflight creation
requires only the new Sequence 12 intake leaf and every other new forward leaf
to be absent. Tests derive the intake directory from the patched Sequence 12
forward paths; no fixture consults the real shared directory by a hard-coded
name.

### New forward namespace

| Index | State leaf |
| ---: | --- |
| `0` | `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260728T010000Z/manifest.json` |
| `1` | `.claude/ui_snapshots/ux1b/recovery/control-migration-20260728T010000Z.json` |
| `2` | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260728T010000Z.json` |
| `3` | `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260728T010000Z.json` |
| `4` | `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260728T010000Z.json` |
| `5` | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260728T010000Z.json` |
| `6` | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` |

Only these monotonic states pass:

| State | Manifest | Report | Packet | Intake | Review | Candidate | Root |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R0_READY` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `R1_CAPTURE` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `R2_REPORT` | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| `R3_PACKET` | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| `R4_INTAKE` | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `R5_REVIEW` | 1 | 1 | 1 | 1 | 1 | 0 | 0 |
| `R6_CANDIDATE` | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| `R7_ROOT` | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

Every other existence pattern fails. Every existing leaf must satisfy its
command-specific schema and immutable predecessor bindings in addition to
generic prefix safety.

## Screenshot-binding contract

### Worker ordering

For focused captures only, the worker must perform this exact sequence:

1. Complete the existing semantic, keyboard, selection-restoration, and
   temporary-scroll audit. That audit still restores its entry scroll state.
2. Resolve every focused root from the frozen catalog again.
3. Move the focused root group into one deterministic target-visible
   viewport state.
4. Wait for fonts, app readiness, document stability, and root geometry
   stability.
5. Capture the pre-screenshot viewport binding and project DOM nodes.
6. Take `page.screenshot(full_page=False, animations="disabled",
   caret="hide")`.
7. Capture the post-screenshot viewport binding and project DOM nodes again.
8. Require pre/post binding and node projections to be exactly equal.
9. Serialize the pre-screenshot values into the sidecar and close the
   browser context. No scroll restoration is required after the evidence is
   sealed.

Full-page captures retain their existing `full_page=True` behavior.

### Deterministic root-group positioning

The positioning primitive receives retained handles for every focused root
in catalog order. It must:

1. Recompute the ordered scrollable-ancestor chain for each root using the
   existing visibility and scrollability rules.
2. Require all roots in a multi-root case to have one common writable
   scrolling ancestor. The document scrolling element is a valid common
   ancestor.
3. Compute the union rectangle of all roots and targets.
4. Compute the visible rectangle as the intersection of the browser viewport
   and the common ancestor's client rectangle.
5. If the union fits the visible rectangle, move the common ancestor by the
   exact delta between both rectangle centers, clamped to its scroll range.
6. If the union does not fit, fail; do not hide a root or choose a subset.
7. Wait for two identical full snapshots. Require every root and target
   rectangle to be inside the visible rectangle with the existing one-pixel
   geometry tolerance.

No loop may exceed the existing focused-layout deadline. The primitive must
not scroll unrelated ancestors, mutate selection state, click controls, or
trigger a Streamlit rerender. Real Chromium tests cover the two multi-root
cases (`knowledge-graph-controls` and `radar-controls`) in every cataloged
viewport.

### Focused evidence v2

`quant-radar-ui-ux-focused-controls/v2` adds one closed
`screenshotBinding` object:

```json
{
  "schemaVersion": "quant-radar-ui-ux-focused-screenshot-binding/v1",
  "mode": "viewport",
  "viewport": {"width": 1440, "height": 900},
  "roots": [
    {
      "rootSelector": ".st-key-adb_table",
      "rect": {"x": 80, "y": 416, "width": 1280, "height": 45}
    }
  ],
  "scrollEntries": [
    {
      "rootSelector": ".st-key-adb_table",
      "chainIndex": 0,
      "left": 0,
      "top": 902,
      "clientWidth": 1440,
      "clientHeight": 900,
      "scrollWidth": 1440,
      "scrollHeight": 1804
    }
  ],
  "prePostExact": true
}
```

Exact numeric values are observations, not constants. Validation requires:

- one root row for every control root and no extra row;
- unique root selectors in catalog order;
- every root rectangle and target rectangle inside the viewport;
- finite nonnegative scroll metrics and bounded chain cardinality;
- `mode:"viewport"` and `prePostExact:true`;
- every serialized root rectangle equals the corresponding projected
  screenshot-time root node;
- focused PNG dimensions equal the declared viewport exactly;
- legacy v1 sidecars remain readable only as historical inputs and cannot be
  minted by the Sequence 12 worker.

## Capture-stack and runtime transition

### Distinct stack contract

The historical
`docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json` remains byte-identical.
Sequence 12 publishes
`docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json` with the same
nine-member path set and unchanged logical control catalog, but new member
hashes and a new capture-stack digest.

The snapshot runner accepts a stack contract only through an internal exact
enum:

```text
legacy
seq12
```

The public CLI does not accept an arbitrary filesystem path. The formal
Sequence 12 runner plan selects `seq12`; historical commands remain bound to
`legacy`. Both opening paths are descriptor-relative, no-follow, exact-owner,
mode, digest, member-set, and catalog checked.

Publication order is closed:

1. Stabilize all nine capture-stack member bytes and pass discovery plus the
   disposable real-smoke gate.
2. Build the Sequence 12 contract in memory from descriptor-authenticated
   members.
3. Publish it create-once to the fixed Sequence 12 path with mode `0600`.
4. Reopen it and record its SHA-256 in the Sequence 12 coordinator authority.
5. Make the coordinator-hash edit only after contract publication. The
   coordinator is not a capture-stack member, so this creates no fixed-point
   cycle.
6. Rerun discovery, smoke, contract reopen, runtime digest, and complete
   verification.

The stack publisher cannot rotate or replace either the historical or
Sequence 12 leaf. A same-byte reopen succeeds; any different collision fails.

### Runtime profiles

Historical validators retain the old `.venv` digest as historical evidence.
Sequence 12 adds a current runtime profile with exact digest
`9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75`
and the existing root metadata.

The Sequence 12 preflight and every new capture/review/root command
reauthenticate this current profile. Formal child processes set
`PYTHONDONTWRITEBYTECODE=1`, use private HOME/TMP/XDG roots, and recheck the
runtime digest after child quiescence. A reviewer-time runtime drift makes
`publish-review` fail before manual-review publication.

## Corrected capture and comparison

### Capture scope

The new capture command runs only:

```text
profile: ux1b-selection-controls
phase: postcontrol
browser: chromium
captures: 36
artifacts: 72
manifest leaves: 73
```

It reuses the existing descriptor, isolation, network-deny, process-family,
stream, timeout, checkpoint, exclusive-publication, and reconcile machinery.
It receives a distinct runtime root and lifecycle namespace. It cannot launch
the `81`-page profile.

### Cross-stack comparator

The new report consumes exactly:

| Input | Stack |
| --- | --- |
| Historical before pages | historical |
| Historical accepted after pages | historical |
| Historical before controls | historical |
| Corrected after controls | Sequence 12 |
| Historical catalog | historical |
| Sequence 12 catalog | Sequence 12 |

The two catalogs must have identical cases, routes, callables, viewport
profiles, session keys, root selectors, boundary IDs, and flow scopes.
Only stack member hashes, stack digests, evidence schema version, and
screenshot-binding fields may differ.

The report also binds an exact source transition. Historical page/control
manifests retain their recorded source digests. The corrected manifest carries
the Sequence 12 source-mirror digest. Sequence 12 preflight stores both:

- the exact imported Sequence 11 source/archive projection as historical;
- the exact active Sequence 12 source and supplemental projections.

The comparator accepts the different corrected-manifest source digest only
when the projection delta is exactly the planned capture/coordinator/test
surface. Every production `ui/`, `api/`, provider, selector, fixture app,
theme source, configuration, and dependency file must be byte-identical.
The report serializes `sourceTransition` with both projection refs and the
ordered changed-path set.

The new `scripts/ui_ux_evidence.py` must preserve the existing semantic
migration oracle. Before implementation, tests freeze the source spans and
callable signatures of catalog validation, node canonicalization,
`_compare_capture_migration`, semantic-volatility validation, and layout
safety. Sequence 12 may add v2 parsing and screenshot-binding checks around
those functions but cannot change their legacy semantic outputs. Mutation
tests compare old v1 inputs through the prechange module and current module
and require byte-identical canonical semantic projections.

The report must contain:

- `comparedCaptures:117`;
- `captureStackTransition` with exact historical and Sequence 12 contract
  refs/digests;
- `sourceTransition` with exact historical/current projections and the
  closed changed-path set;
- `screenshotBindingAudit` with `36` passed focused captures, `0` unbound
  captures, and `72` exact pre/post projections;
- the existing semantic selection, accessibility, layout-safety, volatility,
  and actual-geometry checks;
- a newly frozen geometry/volatility profile derived from authenticated
  corrected artifacts, never guessed in advance.

The comparator must reject a same-stack substitution, an unapproved third
stack, missing screenshot binding, catalog drift, a target outside viewport,
any unplanned source-path delta, semantic-oracle drift, or any reuse of the
rejected after-controls manifest.

## Requirements and acceptance criteria

### Requirements

| ID | Requirement |
| --- | --- |
| `REQ-012` | Recover the rejected UX-1B control-migration review with corrected, independently reviewable focused evidence. |
| `CFR-051` | Bind focused screenshot bytes and sidecar geometry to one stable target-visible viewport state. |
| `CFR-052` | Preserve all Sequence 8–11 evidence and reviewer decisions as immutable history. |
| `CFR-053` | Separate historical runtime authority from the exact current runtime used for Sequence 12. |
| `CFR-054` | Permit only the exact historical-to-Sequence-12 capture-stack transition. |
| `CFR-055` | Capture only the necessary 36 focused controls while comparing all 117 migration items. |
| `CFR-056` | Preserve independent external review and rejected-review truth. |
| `CFR-057` | Preserve production UI/API/fail-soft behavior and unrelated workspace bytes. |

### Acceptance criteria

#### `AC-SEQ12-001` — exact rejected predecessor

Given the retained Sequence 11 `F3_REVIEW`, when Sequence 12 bootstrap or
preflight runs, then the report, packet, intake, review decision, four
rejected IDs, distinct intake/review inodes, candidate absence, and complete
Sequence 10/9/8 ancestry reopen exactly without modification.

#### `AC-SEQ12-002` — screenshot-time binding

Given any of the `36` focused capture identities, when the worker captures
it, then every focused root and target is visible and pre/post screenshot
scroll, root, target, and node projections are exactly equal.

#### `AC-SEQ12-003` — backward-readable evidence

Given historical focused v1 sidecars and Sequence 12 v2 sidecars, when the
comparator authenticates them, then v1 is accepted only on historical inputs,
v2 is mandatory on corrected inputs, and malformed or cross-positioned
bindings fail closed.

#### `AC-SEQ12-004` — runtime reauthorization

Given historical runtime digest `d9802d61...f0cf` and current cleaned digest
`9f697d17...b75`, when Sequence 12 preflight and commands run, then historical
evidence keeps the former while current execution requires the latter before
and after every write-capable child/review transition.

#### `AC-SEQ12-005` — distinct capture stack

Given the historical stack contract and changed worker/evidence members, when
the Sequence 12 stack is published, then it uses a distinct fixed path,
retains the same nine logical members/catalog, and neither overwrites nor
weakens the historical stack.

#### `AC-SEQ12-006` — exact focused recapture

Given an accepted Sequence 12 preflight, when the real capture command runs,
then exactly `36` captures and `72` artifacts publish once under the corrected
ID, reopen successfully, remain process-quiescent, and carry focused v2
bindings.

#### `AC-SEQ12-007` — complete cross-stack report

Given the exact three historical manifests plus corrected after-controls,
when the comparator runs, then all `117` identities are compared and the
report records the exact two-stack transition plus `36/36` screenshot-binding
passes, the exact source transition, and unchanged legacy semantic-oracle
outputs.

#### `AC-SEQ12-008` — new independent-review boundary

Given the passed corrected report, when `prepare-review` runs, then one new
`117`-item packet is created and formal execution stops with intake, review,
candidate, and root absent.

#### `AC-SEQ12-009` — failure and lifecycle closure

Given runtime drift, capture-stack drift, unsafe namespace, partial capture,
non-prefix forward state, rejected new review, or source drift, when a
Sequence 12 command runs, then its exact failure propagates and no later leaf
is written.

#### `AC-SEQ12-010` — compatibility and scope

Given the complete diff, when permanent, fail-soft, browser, syntax, source,
and dirty-worktree gates run, then all pass with no production UI/API/theme
source change.

## Implementation and test map

| ID | Planned implementation |
| --- | --- |
| `IMPL-079` | Sequence 12 IDs, authorization grammar, exact rejected predecessor refs, package, Tier, preflight, and namespace declarations. |
| `IMPL-080` | Focused target-visible viewport positioning and retained scroll-chain snapshot. |
| `IMPL-081` | Pre/post screenshot root, target, and node equality plus focused viewport screenshot mode. |
| `IMPL-082` | Focused control evidence v2 schema, historical v1 reader, v2 writer, and cross-field root/node validation. |
| `IMPL-083` | Distinct fixed Sequence 12 capture-stack contract and exact legacy/seq12 runner selection. |
| `IMPL-084` | Separate current runtime-tree profile and before/after command reauthentication. |
| `IMPL-085` | Sequence 12 bootstrap/preflight and exact rejected Sequence 11 historical importer. |
| `IMPL-086` | Focused-only capture/reconcile lifecycle reusing existing isolation and publication primitives. |
| `IMPL-087` | Cross-stack comparator, exact catalog/source equivalence gates, frozen semantic-oracle spans, new report profile, and rejected-manifest exclusion. |
| `IMPL-088` | New review/candidate/root forward-prefix semantics and Sequence 12 lineage binding. |
| `IMPL-089` | Make targets, parser/dispatcher bindings, exact public status, and formal packet pause. |
| `IMPL-090` | Red-first, Chromium, mutation, lifecycle, compatibility, and scope verification. |

| ID | Test obligation |
| --- | --- |
| `TEST-106` | Reopen exact Sequence 11 rejected chain and reject any predecessor/decision/rejected-ID mutation. |
| `TEST-107` | Unit-test focused binding schema, path selection, root/target viewport closure, and malformed scroll entries. |
| `TEST-108` | Real Chromium proves the Analytics root is visible and geometry/nodes remain exact across screenshot. |
| `TEST-109` | Real Chromium proves all nine focused cases, both multi-root cases, and all cataloged viewport profiles remain target-visible and safe. |
| `TEST-110` | Historical v1 accepted only for historical inputs; corrected v1 and malformed v2 rejected. |
| `TEST-111` | Historical/current runtime profiles remain distinct; current digest drift fails before and after child/review work. |
| `TEST-112` | Distinct create-once stack contract authenticates exact nine members/catalog, closes publication order, and leaves the legacy path byte-identical. |
| `TEST-113` | Focused-only capture plan cannot select page profile and validates `36/72/73` cardinalities. |
| `TEST-114` | Capture/reconcile crash, collision, busy, partial-output, process, and runtime-drift matrix. |
| `TEST-115` | Cross-stack comparator accepts only the exact old/new stack/source pair, preserves the frozen semantic oracle, and compares all `117` captures. |
| `TEST-116` | Screenshot-binding, unplanned source delta, semantic-oracle, and geometry-profile mutations fail without publishing a report. |
| `TEST-117` | Exhaustive Sequence 12 forward-prefix truth table and exact command start/postconditions. |
| `TEST-118` | Real public report/packet transition pauses before intake; accepted/rejected new review behavior remains exact in fixtures. |
| `TEST-119` | Full recovery, fail-soft, source-scope, Python 3.10, dependency, and dirty-worktree gates. |

## Affected files

### Planned edits

```text
Makefile
scripts/ui_ux_browser_worker.py
scripts/ui_ux_evidence.py
scripts/ui_ux_snapshot_matrix.py
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_evidence.py
scripts/test_ui_ux_theme_handoff.py
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.md
docs/superpowers/plans/2026-07-28-quant-radar-ui-ux-ux1b-task9-capture-binding-runtime-reauthorization-correction.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-capture-binding-correction-seq12.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

The distinct capture-stack contract and final authorization candidate are
implementation outputs. Journal/activity files are administrative and never
enter formal source projections.

### Read-only protected paths

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
all Sequence 8/9/10/11 authorization, Tier, preflight, capture, report,
packet, intake, and review artifacts
all production ui/, api/, provider, selector, and theme-source files
all accepted 81-page and historical before-control capture artifacts
```

## Implementation sequence and gates

### Phase 0 — reopen and fingerprint

- Reopen the exact rejected Sequence 11 chain and classify `F3_REVIEW`.
- Recompute the current cleaned runtime digest twice with bytecode disabled.
- Fingerprint every planned preimage and protected artifact.
- Reproduce the four Analytics temporal mismatches from authenticated
  sidecars and PNGs.
- Reproduce the `72/84` permanent-suite classification.

**Gate:** any unexplained predecessor, runtime, source, artifact, or dirty-path
drift blocks implementation.

### Phase 1 — red tests

- Add `TEST-106..119` without production behavior.
- Require red failures to point to missing screenshot binding, current
  runtime authority, distinct stack, recapture lifecycle, or cross-stack
  comparison.
- Repair test fixtures that derive intake existence from the real workspace;
  fixture paths must follow patched forward paths.
- Keep historical runtime constants exact while making old behavioral
  fixtures independent of the current live runtime tree.
- Freeze legacy semantic-oracle spans and compare prechange/current outputs
  over exact historical v1 fixtures.

**Gate:** setup errors, unrelated runtime imports, or tests that write into
`.venv` are invalid red evidence.

### Phase 2 — focused capture binding

- Implement `IMPL-080..082`.
- Preserve the existing temporary scroll audit and state restoration.
- Add a separate final capture-position step.
- Implement the common-scroll-ancestor/union-centering algorithm and reject a
  union that cannot fit.
- Require exact pre/post screenshot binding and node equality.
- Use focused viewport screenshots; retain page full-page screenshots.
- Add v1 historical reader and v2-only corrected writer.

**Gate:** focused real Chromium passes all nine cases and target viewport
profiles; injected scroll, node, root, screenshot-order, and schema mutations
fail closed.

### Phase 3 — stack and runtime authority

- Implement `IMPL-083..085`.
- Publish the distinct Sequence 12 stack only after its nine members and real
  smoke stabilize.
- Keep the historical stack exact and separately reopen it.
- Bind current runtime digest and exact metadata in Sequence 12.
- Add before/after runtime checks around capture and external-review
  publication.
- Build and create-once publish the distinct stack before embedding its hash
  in the non-member coordinator.

**Gate:** old stack mutation, arbitrary stack path, pycache creation, runtime
ctime drift, or partial Tier/preflight publication blocks progress.

### Phase 4 — corrected capture lifecycle

- Implement `IMPL-086`.
- Reuse the existing descriptor-safe runner, process supervision, network
  denial, checkpoints, and exclusive publication.
- Restrict the new runner to `36` focused postcontrol captures.
- Reconcile only an exact active prefix; never restart a completed or failed
  child implicitly.

**Gate:** production-shaped test capture passes `36/36`, reopens `72/72`,
records `childrenQuiescent:true`, and leaves no owned process or temp root.

### Phase 5 — comparator and forward lifecycle

- Implement `IMPL-087..089`.
- Authenticate the exact historical and new stack contracts and catalogs.
- Require catalog semantic equality and the exact two-stack role assignment.
- Require the closed source-projection transition and unchanged legacy
  semantic-oracle projection.
- Freeze the observed geometry/volatility/binding profile after authenticated
  test capture; do not relax the semantic comparator.
- Add the eight-state Sequence 12 forward classifier and exact semantic
  validation.
- Bind packet, review, candidate, and root v3 through Sequence 12 and the full
  rejected Sequence 11 history.

**Gate:** production-shaped fixtures reach a passed report and packet; all
third-stack, old-after-manifest, missing-binding, rejected-review, and prefix
mutants fail.

### Phase 6 — complete verification and authorization candidate

- Complete `IMPL-090`.
- Run all focused, permanent, fail-soft, browser, syntax, dependency, and
  scope gates.
- Compare the actual diff to this reviewed plan.
- Review for runtime errors, capture timing gaps, evidence mutation, source
  drift, self-approval, missing tests, and maintainability.
- Generate the Sequence 12 authorization candidate only after final source,
  stack contract, and tests stabilize.

**Gate:** all available checks pass, protected bytes remain exact, temporary
namespaces are removed, and no blocking finding remains.

### Phase 7 — later formal execution

- Report the authorization candidate's exact SHA-256, size, and mode.
- Obtain maintainer acceptance of those exact bytes.
- Bootstrap and freshly verify Sequence 12 Tier/preflight.
- Run the real focused-only capture and reopen all artifacts.
- Run the real cross-stack comparator.
- Prepare/reopen the new `117`-item packet.
- Stop before external intake.

**Gate:** formal state is exactly `R3_PACKET`. New intake, review, candidate,
and root remain absent until a fresh independent review.

## Verification commands

Implementation must run at least:

```bash
.venv/bin/python -B scripts/test_ui_ux_evidence.py
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
.venv/bin/python -B -m tabnanny \
  scripts/ui_ux_browser_worker.py \
  scripts/ui_ux_evidence.py \
  scripts/ui_ux_snapshot_matrix.py \
  scripts/ui_ux_theme_handoff.py \
  scripts/test_ui_ux_evidence.py \
  scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m pip check
git diff --check
```

Changed Python must parse with `feature_version=(3, 10)`. Every Python command,
including reviewer utilities, must use `-B` or
`PYTHONDONTWRITEBYTECODE=1`. Runtime-tree digest is checked before and after
the verification set.

## Failure and pause policy

- Never delete or replace the rejected Sequence 11 review chain.
- Never promote the old rejected review to accepted.
- Never patch four PNGs into the old manifest.
- Never accept a focused corrected sidecar without screenshot binding v2.
- Never let a pre-screenshot geometry value stand in for a post-screenshot
  value without exact equality.
- Never overwrite the historical capture-stack contract.
- Never compare an arbitrary stack transition.
- Never update the historical runtime constant to make old evidence look
  current.
- Never use the authorized `.venv` for ad hoc review without bytecode
  suppression.
- Never rerun the accepted `81` page captures under this correction.
- Never author external intake during implementation.
- Every collision or partial artifact is retained for diagnosis.
- Formal execution stops at the new packet.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Final capture scroll hides a second focused control | Position the catalog-ordered root group, then require every root/target inside the viewport. |
| Screenshot itself changes geometry | Compare exact pre/post root, target, scroll, and node projections. |
| v2 schema breaks historical v1 evidence | Keep an explicit historical-only v1 reader and v2-only corrected writer. |
| Cross-stack comparison hides arbitrary code changes | Require exact two contract refs, nine-member sets, catalog equality, and role-specific manifest assignments. |
| Different source digests hide a production change | Bind historical/current projections and permit only the reviewed capture/coordinator/test changed-path set. |
| Evidence v2 silently changes the semantic comparator | Freeze legacy oracle spans and require byte-identical v1 canonical projections through prechange/current modules. |
| Current runtime overwrites historical truth | Store separate named historical/current profiles and test both directions. |
| Reviewer writes another pycache | Reauthenticate current runtime before and after review publication and mandate bytecode-free tooling. |
| Narrow recapture misses page regression | Production UI is unchanged; reuse authenticated accepted pages and rerun fail-soft/UI/source gates. |
| Formal suite depends on empty intake forever | Derive fixture intake paths from patched forward namespaces and keep real lifecycle checks state-aware. |
| Dirty worktree is damaged | Edit only planned paths, fingerprint protected files, never reset/clean, and preserve unrelated changes. |

## Rollback

- Before Sequence 12 Tier publication, revert only planned Sequence 12 source
  and new documents when explicitly authorized.
- After Tier/preflight publication, retain every artifact. Do not delete,
  overwrite, or regenerate a collision.
- A failed corrected capture is terminal evidence for that capture ID; a new
  reviewed correction and ID are required.
- Before root publication, rollback is refusing forward work.
- Sequence 8–11 artifacts and the historical stack are never rollback
  targets.

## Blocking-issue review

### Review iteration 1 — target positioning and temporal proof

- **Finding:** The first draft required a target-visible screenshot but did
  not define how two focused roots share one viewport or how screenshot-time
  geometry is proven stable.
- **Resolution:** Add the common-scroll-ancestor and union-centering
  algorithm, reject non-fitting unions, require two stable snapshots, and
  require exact pre/post screenshot root, target, scroll, and node
  projections.
- **Status:** Closed.

### Review iteration 2 — cross-stack and source authority

- **Finding:** Allowing old and new capture-stack digests without an exact
  source transition could hide unrelated application changes. Changing the
  evidence module could also silently replace the legacy semantic oracle.
- **Resolution:** Bind historical/current source projections and a closed
  changed-path set, keep every production surface exact, freeze semantic
  oracle spans, and require byte-identical legacy v1 projections through the
  prechange and current modules.
- **Status:** Closed.

### Review iteration 3 — consumed namespace and publication order

- **Finding:** The shared intake directory legitimately exists after Sequence
  11, and the first draft did not close how a distinct stack contract is
  published without a hash fixed point.
- **Resolution:** Require only the new intake leaf absent, derive fixture
  directories from patched forward paths, and publish/reopen the exact stack
  before embedding its hash in the non-member coordinator.
- **Status:** Closed.

No unresolved blocking issue remains in the reviewed plan. This review
authorizes neither implementation nor formal publication.

## Traceability summary

The sibling ledger must bind `REQ-012`, `CFR-051..057`,
`AC-SEQ12-001..010`, `IMPL-079..090`, and `TEST-106..119`
bidirectionally with `10000` basis-point structural coverage, no gaps, and no
orphans. Planning verdicts remain `NOT_TESTED`.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `1.0-reviewed` | 2026-07-28 | Closed target-group positioning, screenshot-time proof, cross-stack source authority, semantic-oracle preservation, consumed intake namespace, and stack-publication ordering. |
| `0.1-review-candidate` | 2026-07-28 | Initial Sequence 12 plan for screenshot binding, focused recapture, cross-stack comparison, and runtime reauthorization. |

## Next handoff

Review this plan for blocking issues. Implementation requires a reviewed plan
with no unresolved blocker. Formal bootstrap later requires separate
acceptance of the final authorization candidate's exact bytes.
