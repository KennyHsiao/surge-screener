# UX-1B Hidden Native-Radio Label Remediation Plan

## Document Info

| Field | Value |
| --- | --- |
| Type | Versioned executable implementation checklist |
| Version | v0.4-accepted |
| Status | ACCEPTED EXECUTION AMENDMENT |
| Date | 2026-07-19 |
| Owner | Codex |
| Reviewers | independent impact and test/lifecycle reviewers |
| Audience | UX-1B evidence, accessibility, and recovery maintainers |
| Parent plan | `docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md` |
| Prior amendment | `docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-geometry-quantization-remediation.md` |

## 1. Outcome and context

Repair the frozen browser worker's handling of Streamlit 1.57 native radios,
rotate the authenticated capture stack, replace the now-stale Task 6
pre-control baseline, and then resume the already implemented parent Task 8
selector migration.

The nine production selector files have passed focused behavior,
accessibility, fail-soft, navigation, static, and independent code review.
The remaining Task 8 real-browser smoke fails first at
`ai-chat-settings-controls/mobile` because Streamlit renders the semantic
`input[type=radio]` as a standard visually hidden control. Its associated
`label` is visible and actionable. The worker incorrectly requires the input
itself to be visible in two places:

- `scripts/ui_ux_browser_worker.py:_exact_choice_locator()` before a real
  interaction;
- `scripts/ui_ux_browser_worker.py:_radio_control_evidence()` before semantic,
  keyboard, and geometry evidence.

This is an evidence-tool compatibility defect, not a production UI defect.
The correction must preserve the semantic/action split:

- the hidden input remains the authority for role, accessible name, checked
  state, focus, roving tab stop, and native keyboard behavior;
- its unique, exact, visible wrapping label becomes the pointer action and
  geometry target;
- no force-click, JavaScript click, CSS unhide, or accessibility claim based
  only on visual styling is allowed.

No API, artifact loader, provider, route, decision, or fail-soft behavior may
change. Missing, half-written, malformed, or wrong-shaped data must continue
to degrade without crashing Streamlit or FastAPI.

## 2. Scope and non-goals

### In scope

- `scripts/ui_ux_browser_worker.py`
  - introduce one fail-closed radio input/label association boundary;
  - scope interaction choices to their contracted control root;
  - click only the visible label for native radios;
  - retain the input for checked/focus/keyboard evidence;
  - measure the validated label directly.
- `scripts/test_ui_ux_evidence.py`
  - add exact Streamlit-like visually-hidden input regressions;
  - add association, visibility, scope, interaction, rerender, keyboard, and
    geometry mutation cases;
  - keep legacy segmented-button coverage green.
- `scripts/test_ui_accessible_selection_controls.py`
  - update only the canonical capture-stack SHA after successful rotation;
  - continue authenticating every member, including the new worker hash.
- `docs/ui-ux/quant-radar-ui-v2-ux1b-task8-selector-delta.json`
  - add an exact, authenticated, bidirectional 9-file/11-span selector delta;
  - bind whole-file before/after hashes, anchors, span bytes, and span hashes.
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json`
  - replace `productionRollback.postimages: null` with the exact delta
    path/SHA/size authority after independent reopen.
- `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json`
  - rotate once through the existing expected-old-SHA compare-and-swap path.
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`
  - revoke the stale baseline before worker edits;
  - publish a new baseline only after complete authentication.
- `.agents/PROJECT.md`, `.agents/ripple.md`, and `.agents/scribe.md`
  - append-only planning and closure records.
- The nine parent Task 8 selector files, but only as a temporary, exact,
  anchored rollback/reapply operation needed to capture a new legacy
  pre-control baseline:
  - `ui/risk_guard.py`
  - `ui/institutions.py`
  - `ui/options_cockpit.py`
  - `ui/radar.py`
  - `ui/knowledge_graph.py`
  - `ui/ai_chat.py`
  - `ui/retro_analysis.py`
  - `ui/analytics_db.py`
  - `ui/stock_checkup.py`

### Out of scope

- changing radio options, defaults, session keys, help text, label visibility,
  branches, provider calls, query behavior, or page layout;
- changing the Analytics selectbox implementation or catalog validation;
- accepting an unlabeled, multiply labeled, mismatched, hidden, detached, or
  out-of-root radio;
- using `force=True`, `dispatchEvent`, `HTMLElement.click()`, script-mutated
  `checked`, or injected CSS to manufacture a pass;
- changing evidence schemas, option order, target-size thresholds, geometry
  tolerances, or semantic acceptance rules;
- overwriting, renaming, or reusing any prior evidence namespace;
- byte-reverting a published capture-stack member after rotation;
- changing the existing user-owned listener on port 8501;
- beginning theme work before the replacement Task 8 evidence gate passes.

## 3. Requirements and acceptance criteria

### REQ-RADIO-001 — separate semantic and actionable radio targets

For each contracted native radio option, the worker must identify exactly one
semantic input and exactly one associated visible action label within the same
contracted root and radiogroup.

- **AC-RADIO-001 (Given/When/Then):** Given one Streamlit-style clipped 0x0
  radio input inside one visible wrapping label, when the worker resolves the
  option, then it returns the input as semantic authority and the label as the
  action target.
- **AC-RADIO-002:** Given no label, multiple associated labels, label text that
  differs after whitespace normalization, a non-wrapping association, a label
  outside the radiogroup/root, a non-visible/zero-size label, a disabled/inert
  input, `aria-disabled`, `pointer-events:none`, or an occluding element,
  resolution/actionability fails closed.
- **AC-RADIO-003:** Given duplicate exact-name buttons/radios or mixed legacy
  and replacement choices, resolution fails closed.
- **AC-RADIO-004:** Given the legacy segmented button, its existing visible
  button action and active-`kind` semantics remain unchanged.

### REQ-RADIO-002 — native pointer and keyboard behavior

- **AC-RADIO-005:** Clicking the validated label causes a real native change,
  a strictly newer Streamlit render generation, and the contracted checked
  state; the input itself is never force-clicked.
- **AC-RADIO-006:** Focus, `Shift+Tab`/`Tab`, `ArrowRight`, `ArrowLeft`, and
  `Space` continue to operate on the semantic input and preserve the existing
  one-checked, roving-tab-stop evidence.
- **AC-RADIO-007:** The keyboard audit remains non-rerendering while the real
  pointer interaction must rerender exactly through the existing generation
  boundary.

### REQ-RADIO-003 — visible target geometry

- **AC-RADIO-008:** Evidence records the validated label rectangle directly;
  every target remains at least 24x24 CSS pixels at 320, 390, 768, and 1440
  widths.
- **AC-RADIO-009:** Existing clipping, overlap, horizontal overflow, stable
  layout, and exact scroll restoration checks remain unchanged and fail
  closed.

### CFR-RADIO-001 — immutable evidence authority

- **AC-RADIO-010:** Recovery ID `20260719T114511Z` is marked immutable
  `superseded-by-worker-contract-gap` and loses Tasks 7–9 authorization before
  worker bytes change.
- **AC-RADIO-011:** The canonical capture-stack leaf remains SHA-256
  `5122beab6ad31d8418c9808539b36b754fb0c2d2c7fb2de64edb22e1a909fe88`
  until targeted tests, 57-row discovery, 10-row real smoke, cleanup, and
  independent review pass.
- **AC-RADIO-012:** Rotation uses the existing explicit expected-old-SHA CAS,
  archives exact old bytes, reopens the new contract, and publishes no
  provisional recovery ID.
- **AC-RADIO-013:** Only a new immutable ID that passes 81/81 pages, 36/36
  focused controls, two terminal-manifest reopens, 234/234 artifact reopens,
  exact namespace/counter checks, zero prohibited access, and process
  quiescence may become canonical.

### CFR-RADIO-002 — exact Task 8 restoration

- **AC-RADIO-014:** Before temporary rollback, all nine current Task 8 file
  hashes equal the frozen postimage table in this plan, and the authenticated
  selector-delta document resolves all 11 exact spans without ambiguity.
- **AC-RADIO-015:** The temporary legacy state equals all nine canonical Task 6
  before-hashes from the recovery document; only anchored selector hunks may
  differ.
- **AC-RADIO-016:** After the new baseline is authenticated, the exact Task 8
  hunks are reapplied and all nine files equal their original postimage hashes.
- **AC-RADIO-017:** If any preimage, anchor, or postimage hash differs, stop;
  never restore a whole archived production file over unrelated dirty work.

### CFR-RADIO-003 — compatibility and cleanup

- **AC-RADIO-018:** All current recovery, selector, navigation, compile,
  Python 3.10 AST, tabnanny, dependency, and whitespace gates pass after the
  rotation and reapplication.
- **AC-RADIO-019:** API/provider/fail-soft code is untouched and the focused
  selector suite retains its missing/malformed/stale/valid data cases.
- **AC-RADIO-020:** Every spawned app/browser process and temporary listener is
  owned, bounded, and quiescent at each terminal gate; port 8501 is untouched.

## 4. Design

### 4.1 Fail-closed association boundary

Add a small private helper that receives a radio locator, its exact expected
label, and the already-scoped root/radiogroup context. It must require:

1. one native `input[type=radio]` semantic node;
2. `node.labels.length == 1`;
3. `node.labels[0] == node.closest("label")` and
   `node.labels[0].control == node`;
4. the wrapping label contains only that exact radio option;
5. both label and input belong to the same unique contracted radiogroup;
6. whitespace-normalized label text equals the contracted option exactly;
7. the input/label/root/group chain is not disabled, inert, `aria-disabled`, or
   `pointer-events:none`;
8. the label is uniquely visible and has nonzero rendered geometry.

The helper returns the wrapping label locator. The input remains unmodified.
This intentionally contracts the actual Streamlit 1.57 wrapping-label DOM;
a future framework DOM change must fail closed and trigger a new reviewed
capture-stack rotation.

### 4.2 Interaction path

`_exact_choice_locator()` must search inside the supplied contracted root, not
the whole page. It distinguishes only these exact states:

- one visible legacy button and zero radios: semantic and action target are
  the same button;
- zero buttons and one semantic radio with one validated visible label:
  semantic target is the input and action target is the label;
- every other state: bounded failure.

`_perform_capture_interaction()` clicks the returned action target but calls
`_choice_is_selected()` on the semantic target. `_assert_selected_choice()`
re-resolves the contracted root after rerender and checks only semantic state;
it must not require the hidden input to be visually visible.

Every real pointer interaction first calls Playwright `click(trial=True)` on
the validated label under the existing timeout and only then performs the real
label click. This rejects unstable, disabled, or event-occluded targets without
firing application events.

### 4.3 Evidence path

`_radio_control_evidence()` resolves each exact input plus validated label in
contract order. It uses inputs for checked/focus/tab/arrow/space assertions and
passes labels directly to `_focused_control_layout()` with
`closest_label=False`. The output schema and rectangle values remain the same
as measuring the current wrapping label through the old fallback.

The layout helper gains a radio-only `trial_click_targets` option. After it
retains the root/label handles, freezes the original scroll chain, scrolls the
root into its authenticated audit viewport, and restores horizontal offsets,
it runs `ElementHandle.click(trial=True)` on every label under the remaining
deadline before the audit snapshot. The existing outer `finally` restores and
proves the exact original document and nested-scroll state. Trial actionability
may not bypass clipping/overflow checks, fire application events, or change the
final projection. Legacy and selectbox callers keep this option disabled.

### 4.4 Frozen stack and recovery lifecycle

Changing `scripts/ui_ux_browser_worker.py` invalidates the current 9-member
capture stack. The existing CAS rotation is reused; no publisher API change is
needed. The selector test's hardcoded canonical SHA is intentionally updated
only after rotation, so the full recovery suite is expected to remain red in
the interim.

Because a valid pre-control baseline must render legacy segmented selectors,
the already-reviewed Task 8 production hunks are temporarily reversed only
after the new worker stack is frozen. The operation uses the authenticated
prechange archive only as a read oracle and a new bidirectional span-delta
document as the exact operation authority. It applies anchored hunks rather
than whole files, verifies all nine before-hashes, captures the new baseline,
then reapplies the exact accepted Task 8 hunks and verifies all nine
posthashes.

### 4.5 Authenticated Task 8 selector delta

Before worker edits, create one canonical JSON document with:

- exact schema, creation time, owner UID/GID, parent/recovery-plan hashes, and
  authenticated prechange archive/manifest hashes;
- exactly nine unique production paths and exactly eleven unique session keys;
- for each file, its canonical legacy whole-file SHA and current Task 8
  whole-file SHA;
- for each span, exact `anchorBefore`/`anchorAfter`, preimage text and SHA,
  postimage text and SHA, a stable `spanId`, and explicit `sessionKeys`, with
  no overlapping spans; the 11-span partition may map one key to multiple
  spans or one adjacent span to multiple keys, but the union must equal the
  exact 11-key control catalog;
- no whole-file replacement payload and no unrelated source bytes.

The selector suite gains a hard verifier that authenticates the delta's
constant SHA/size, owner-only regular-file identity, exact key/path/session
catalog, span hashes/anchors, and the live workspace as either all-legacy or
all-migrated. A mixed 1–8 file state fails closed. The recovery rollback
document records the reopened delta path/SHA/size under
`productionRollback.postimages`. The delta and rollback metadata receive
independent code/data review before any selector is reversed.

Both inverse and forward transitions use a two-phase operation:

1. a read-only preflight validates all nine whole-file hashes, all eleven live
   span bytes/hashes, every anchor, and the expected all-migrated or all-legacy
   state without writing;
2. one multi-file `apply_patch` transaction applies all eleven spans, followed
   by an all-nine expected-hash verification.

A failed patch transaction must leave all nine files at their preflight hashes;
this is verified immediately. Any unexpected mixed state is a blocking tool
failure and must be repaired in one forward transaction to the nine Task 8
posthashes before the run may end. Per-file sequential rollback/reapply is
forbidden.

The exact operational partition is frozen below. It is derived from the live
Task 8 versus archived legacy diff, not copied from the earlier planning
manifest's 13 predeclared spans. The unchanged AI initialization context is
omitted; the adjacent Knowledge Graph changes remain one atomic span.

| `spanId` | File | `sessionKeys` |
| --- | --- | --- |
| `rg-source-widget` | `ui/risk_guard.py` | `rg_source` |
| `inst-view-docs` | `ui/institutions.py` | `inst_view` |
| `inst-view-widget` | `ui/institutions.py` | `inst_view` |
| `cockpit-price-view-widget` | `ui/options_cockpit.py` | `cockpit_price_view_NVDA` |
| `radar-source-widget` | `ui/radar.py` | `radar_source` |
| `radar-view-widget` | `ui/radar.py` | `radar_view` |
| `knowledge-graph-widgets` | `ui/knowledge_graph.py` | `kg_view_mode`, `kg_label_mode` |
| `ai-chat-mode-widget` | `ui/ai_chat.py` | `ai_chat_mode` |
| `retro-lane-widget` | `ui/retro_analysis.py` | `retro_validation_lane` |
| `analytics-table-widget` | `ui/analytics_db.py` | `adb_table` |
| `stock-checkup-mode-widget` | `ui/stock_checkup.py` | `checkup_mode` |

## 5. Ripple impact analysis

### Dependency map

```text
L0 scripts/ui_ux_browser_worker.py
 |
 +-- L1 scripts/ui_ux_evidence.py (frozen member catalog/worker command)
 +-- L1 scripts/ui_ux_isolation.py (worker identity/process contract)
 +-- L1 scripts/ui_ux_snapshot_matrix.py (full/focused discovery and smoke)
 +-- L1 scripts/ui_ux_theme_matrix.py (theme worker session)
 +-- L1 scripts/test_ui_ux_{evidence,isolation,snapshot_matrix,theme_matrix}.py
 +-- L1 scripts/test_ui_accessible_selection_controls.py (hardcoded stack SHA)
 |
 +-- L2 docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
 +-- L2 Makefile recovery targets and manifest validators
 +-- L2 precontrol/postcontrol/pretheme manifests and recovery pointer
 `-- L3 parent Task 9 theme authorization
```

### Blast radius and consistency

| Metric | Result |
| --- | --- |
| Final implementation/evidence files | 7 code/contract/doc files plus this plan and append-only logs |
| Temporary production files | exactly 9; final hashes must equal turn-start postimages |
| Generated immutable evidence | 1 old-stack archive plus 236 new baseline leaves (234 PNG/sidecars + 2 manifests) |
| Estimated implementation delta | 160–320 LOC plus tests/docs; no product-runtime net delta |
| Service boundaries | browser worker -> isolated coordinator -> evidence contract |
| Public API breaking change | none |
| Evidence compatibility change | yes; all old manifests remain historical and cannot parent new evidence |
| Horizontal pattern | matches existing semantic-input/visible-label handling in `ui_ux_theme_matrix.py` |
| Churn | untracked recovery stack has several dated amendments; treat as high-review hotspot |
| Coverage before change | strong, but the synthetic radio fixture omitted real hidden-input CSS |
| Reversibility | easy before rotation; forward-only recovery after rotation |

### Risk score

| Dimension | Score | Weight | Weighted rationale |
| --- | ---: | ---: | --- |
| Impact scope | 8 | 30% | worker covers 120 capture rows plus transient 9-file state |
| Breaking potential | 8 | 25% | frozen member change invalidates current evidence authority |
| Pattern deviation | 2 | 20% | follows existing native radio semantic/action pattern |
| Coverage gap | 5 | 15% | diagnosed hidden-input hole; explicit red tests close it |
| Reversibility | 5 | 10% | exact selector delta; stack still requires forward repair |
| **Total** |  |  | **6.05 / 10, rounded 6.1 — MEDIUM** |

**Verdict:** CONDITIONAL GO. Proceed only in the ordered gates below. The
canonical rotation and transient production rollback are forbidden until all
preceding tests/reviews pass.

## 6. Frozen byte oracles

### Capture/evidence preimages

| File | Turn-start SHA-256 |
| --- | --- |
| `scripts/ui_ux_browser_worker.py` | `3f796f768f5199abd6355ab231a22950314bf914c0c1fe37758a10891a6ddf1c` |
| `scripts/test_ui_ux_evidence.py` | `00912568a31f1151d43981d0ab76d9db6fe98ee5effd1736367c8cffeaa4b136` |
| `scripts/test_ui_accessible_selection_controls.py` | `b724155f73923248c3e597515d35c333f2cf2f50f1ffeeb35dae068f6597b954` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json` | `5122beab6ad31d8418c9808539b36b754fb0c2d2c7fb2de64edb22e1a909fe88` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md` | `fb6fc600bcbe603aafef509bd5434348f910e8e158244167b1c6bc2cce87384b` |

### Parent Task 8 postimages that must be restored exactly

| File | Required final SHA-256 |
| --- | --- |
| `ui/risk_guard.py` | `fb90a5d352c5aa1952d10fce0c56da25e2f09769ee644be8366a2ea93a8c2bee` |
| `ui/institutions.py` | `de32f082a44c5f3428f75875cf7f2e4224d696b09b8cccb102bc46bed39edf87` |
| `ui/options_cockpit.py` | `9c8f131d6c5edd369e2f0f316a8821fc32419d405df7c29141d84624767ec9e5` |
| `ui/radar.py` | `917a329ea8a8297cc29bed1f892c2133ce5934d643469b97df36ffe9216fcd1c` |
| `ui/knowledge_graph.py` | `01a412f7287405d2f201fb6ed7a4cfc4a882170b44300ae6bfe202b2ff8e0acd` |
| `ui/ai_chat.py` | `2b1c5739d87e604da17f217b99010426b7873a83223062be4c2b5e8c151b92a2` |
| `ui/retro_analysis.py` | `5030e678eb5fbafe06b96f9ced93d53bb98908d45ffcb7384f7c8c216ccc6a5e` |
| `ui/analytics_db.py` | `9475fb3c8614ed8e102c2619c325562025768445c45d5f625f0ad54d71467fe7` |
| `ui/stock_checkup.py` | `1f38b26fd3ae137b4929bc0ac4dd8441f4a0bf38994a83696517ea66df7b4e45` |

The canonical legacy before-hashes remain the nine hashes in
`docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`. Hash equality alone does not
authorize whole-file replacement; every edit must match the recorded selector
anchors and exact accepted hunk.

## 7. Implementation checklist

### Task 0 — revoke stale recovery authority

**Files:** `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`,
`.agents/PROJECT.md`

- [ ] Mark status `BLOCKED — WORKER CONTRACT ROTATION AND REPLACEMENT BASELINE PENDING`.
- [ ] Preserve recovery ID `20260719T114511Z` and its namespaces byte-for-byte,
  classify it `superseded-by-worker-contract-gap`, and revoke Tasks 7–9.
- [ ] State that no recovery ID is canonical while remediation is pending.
- [ ] Append a corrective ledger row; do not rewrite historical rows.

**Gate:** no document may authorize old evidence after worker edits begin.

### Task 0A — freeze and authenticate the reversible Task 8 span delta

**Files:**
`docs/ui-ux/quant-radar-ui-v2-ux1b-task8-selector-delta.json`,
`docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json`,
`scripts/test_ui_accessible_selection_controls.py`

- [ ] Reverify the nine migrated whole-file posthashes in section 6.
- [ ] Descriptor-authenticate the existing prechange archive and manifest.
- [ ] Compare every archived production file to its live migrated file without
  extracting over the workspace; isolate exactly 11 accepted selector spans.
- [ ] Publish the exact bidirectional delta described in section 4.5.
- [ ] Reopen and hash the delta, then record its path/SHA/size under
  `productionRollback.postimages`.
- [ ] Add the selector-suite hard verifier and prove all-migrated passes while
  one-file/one-span/mixed/hash/anchor mutations fail.
- [ ] Obtain independent review of all 11 pre/post spans and both whole-file
  hash sets.

**Gate:** `postimages` is no longer null and no selector rollback is permitted
until the delta verifier passes.

### Task 1 — add fail-first hidden-radio regressions

**File:** `scripts/test_ui_ux_evidence.py`

- [ ] Apply Streamlit-like clipped/absolute/0x0 CSS to the existing real
  Chromium radio fixture; preserve a visible >=24px wrapping label.
- [ ] Apply the same hidden-input condition to the semantic-readiness fixture
  near the current `radioCount` coverage; do not leave a second false-green
  visible-radio fixture.
- [ ] Add a real Chromium AI interaction where visible labels drive the exact
  `Deep -> Quick` transition and rerender generations while the semantic
  inputs remain hidden. Reacquire root/group/input/label after each replaced
  subtree; no stale locator/handle may authorize the next state.
- [ ] Assert the semantic input is not Playwright-visible while its label is
  uniquely visible/actionable.
- [ ] Add mutation cases for missing, multiple, mismatched, non-wrapping,
  zero-size, disabled/inert/`aria-disabled`, `pointer-events:none`, occluded,
  out-of-group/out-of-root, and duplicate choices.
- [ ] Give disabled, inert, `aria-disabled`, `pointer-events:none`, and an
  overlapping intercepting element separate real-Chromium cases; require each
  to fail before the actionability implementation and to pass only as a
  fail-closed rejection afterward.
- [ ] Retain input focus/keyboard and label geometry assertions.
- [ ] Register every test in the direct-script `main()` list.
- [ ] Update the existing interaction fake so a radio is hidden semantic state
  and its separate label is the only pointer action; a direct input click must
  fail the fake.
- [ ] Run only the new tests and record current failure at the two diagnosed
  visibility requirements.

**Gate:** red for the diagnosed cause, not a fixture/bootstrap error.

### Task 2 — implement the minimal semantic/action split

**File:** `scripts/ui_ux_browser_worker.py`

- [ ] Add one private exact association helper with bounded visibility wait.
- [ ] Scope institution/AI choices and selected-state checks to the contracted
  roots.
- [ ] Return/use separate semantic and action locators.
- [ ] Click labels for radios and buttons for legacy controls.
- [ ] Resolve labels for all evidence options; use inputs for checked/focus/key
  checks and labels for layout.
- [ ] Require label trial-click actionability inside the existing bounded,
  exact-restoration layout audit; keep it disabled for legacy/selectbox paths.
- [ ] Keep schemas, thresholds, timeouts, render-generation rules, and legacy
  segmented/selectbox behavior unchanged.
- [ ] Run the new tests green, then the complete evidence suite.

**Gate:** every positive and fail-closed mutation passes; no forced/scripted
interaction exists in the worker.

### Task 3 — pre-publication verification and review

- [ ] Run evidence, isolation, selection-fixture, fixture, snapshot, theme,
  theme-matrix, contract, and navigation suites that do not depend on the old
  hardcoded canonical SHA.
- [ ] Run 57/57 contract-free control discovery.
- [ ] Run 10/10 contract-free real mobile smoke.
- [ ] Require exact AI/institution native-radio rows at least twice.
- [ ] Run Python compile, Python 3.10 AST, tabnanny, `pip check`, and
  `git diff --check`.
- [ ] Confirm 12/12 owned processes are quiescent and port 8501 is untouched.
- [ ] Obtain independent correctness, test, lifecycle, scope, and
  maintainability review with zero blocking/High/Medium findings.

**Gate:** canonical capture-stack SHA remains `5122...`; no production selector
rollback has occurred.

### Task 4 — rotate and reopen the capture stack

Run exactly:

```bash
.venv/bin/python scripts/ui_ux_snapshot_matrix.py \
  --freeze-capture-stack \
  --expected-capture-stack-sha256 \
  5122beab6ad31d8418c9808539b36b754fb0c2d2c7fb2de64edb22e1a909fe88 \
  --json
```

- [ ] Require the transaction's repeated 57-row discovery and 10-row smoke.
- [ ] Require exact old archive, one CAS replacement, canonical reopen, and
  reported new SHA/base digest/capture-stack digest.
- [ ] Update only the selector test's hardcoded canonical SHA after reopen.
- [ ] Run the selector test and complete recovery suite against the new stack.
- [ ] Update recovery documentation to `replacement baseline pending`; do not
  publish a new ID yet.

**Gate:** old contract is immutable in its digest-named archive, new contract
authenticates all 9/9 members, and no provisional ID is authorized.

### Task 5 — temporarily restore exact legacy selectors

- [ ] Reverify all nine Task 8 postimage hashes in section 6.
- [ ] Descriptor-authenticate the existing prechange archive and manifest.
- [ ] Reopen/authenticate the exact selector-delta path/SHA/size from the
  rollback document.
- [ ] Preflight all 9 files/11 spans together, then apply all 11 anchored
  inverse spans in one multi-file `apply_patch` transaction.
- [ ] On transaction failure, immediately prove all nine preflight hashes are
  unchanged; treat any mixed state as a blocker and restore the nine Task 8
  posthashes in one forward transaction.
- [ ] Verify all nine canonical legacy before-hashes and zero unrelated hunk
  changes.
- [ ] Run `scripts/test_ui_accessible_selection_controls.py --expect-legacy-red`
  and focused legacy discovery. Do not run the postmigration-only dashboard
  assertion or the complete Make target during this bounded interval; run
  both after exact postimages return.

**Gate:** exactly 0/9 migrated files remain; no whole-file restore occurred.

### Task 6 — capture and authenticate replacement Task 6

- [ ] Choose one fresh UTC `UX1B_RECOVERY_ID`; verify both target namespaces
  are absent and never reuse the ID after any terminal attempt.
- [ ] Run:

```bash
make ui-ux1b-recovery-precontrol UX1B_RECOVERY_ID=<fresh-id>
```

- [ ] Require 81/81 page and 36/36 focused-control captures under one source
  and capture-stack digest.
- [ ] Independently descriptor-reopen both terminal manifests and all 234/234
  PNG/sidecar artifacts.
- [ ] Require namespace counts 163 and 73, exact counters, zero prohibited
  access, clean exits, process quiescence, and all nine legacy hashes.
- [ ] Only after every check, publish the new immutable ID, manifest hashes,
  canonical stack SHA/digest, source digest, and Tasks 7–9 authorization in
  the recovery document.

**Gate:** one fully authenticated replacement baseline is canonical.

### Task 7 — reapply and close parent Task 8

- [ ] Reopen the same selector delta and apply only its 11 forward spans; this
  is the sole reapplication operation and must not be followed or preceded by
  a second copy of the accepted selector hunks. Preflight all 9 legacy files
  and execute the 11 spans as one multi-file `apply_patch` transaction.
- [ ] Verify all nine files equal the required Task 8 posthashes in section 6.
- [ ] Require `rg 'segmented_control'` across the nine files to return zero.
- [ ] Run the selector/accessibility suite: all hard gates green and no
  unexpected expected-red case.
- [ ] Run the entire `make ui-ux1b-recovery-tests` target from start to finish.
- [ ] Run `--ux1b-real-smoke --json` under the new canonical stack.
- [ ] Re-run compile, Python 3.10 AST, tabnanny, `pip check`, diff whitespace,
  and owned-process cleanup.
- [ ] Compare actual final diff to this plan and the accepted Task 8 plan.
- [ ] Obtain independent changed-code review; fix every blocking/High/Medium
  finding before closure.

**Gate:** Task 8 is complete only when the production postimages, behavior,
accessibility, full recovery suites, and real smoke all pass.

### Task 8 — handoff to the next parent stage

- [ ] Do not silently reuse the old recovery ID in Task 9 commands.
- [ ] Review Task 8 closure evidence for blockers.
- [ ] If none remain, continue parent Task 9 with the new canonical ID using
  its existing post-control/pretheme and migration-comparison gates.

## 8. Verification commands

```bash
.venv/bin/python scripts/test_ui_ux_evidence.py
.venv/bin/python scripts/test_ui_ux_isolation.py
.venv/bin/python scripts/test_ui_ux_selection_fixture.py
.venv/bin/python scripts/test_ui_accessible_selection_controls.py
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/test_ui_ux_theme.py
.venv/bin/python scripts/test_ui_ux_theme_matrix.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_dashboard_navigation.py
make ui-ux1b-recovery-tests
.venv/bin/python scripts/ui_ux_snapshot_matrix.py --ux1b-real-smoke --json
.venv/bin/python -m py_compile scripts/ui_ux_browser_worker.py scripts/test_ui_ux_evidence.py scripts/test_ui_accessible_selection_controls.py
.venv/bin/python -m tabnanny scripts/ui_ux_browser_worker.py scripts/test_ui_ux_evidence.py scripts/test_ui_accessible_selection_controls.py
.venv/bin/pip check
git diff --check
```

Python 3.10 compatibility is checked by parsing every changed Python file with
`ast.parse(..., feature_version=(3, 10))`. The complete Make target must be
rerun after the canonical SHA update and Task 8 reapplication; constituent
passes from before those mutations cannot substitute for the final run.

## 9. Rollback and abort rules

### Before canonical rotation

Revert only the exact worker/test hunks when their live hashes match the
recorded postimages. Keep recovery status blocked because the old worker gap
remains true. The canonical stack and historical evidence remain unchanged.

### After canonical rotation

Never byte-revert the worker under a contract that authenticates its new hash.
Repair forward, rerun tests/discovery/smoke, rotate again with the then-current
expected SHA, and create another fresh baseline ID. Preserve every archive and
manifest.

### During temporary selector rollback

Any anchor/hash mismatch aborts before the single multi-file transaction. A
failed transaction must prove zero partial writes across all nine files. If a
later baseline gate fails, keep the attempted ID immutable and unauthorized,
then apply the exact forward delta once and require all nine posthashes before
ending the run. Never leave the user-facing workspace unintentionally on
legacy or mixed controls.

### Abort conditions

- new or repeated product runtime failure;
- any API/provider/fail-soft diff;
- any unplanned file or selector hunk;
- canonical stack publication before required gates;
- old evidence still marked authorized after worker change;
- incomplete artifact reopen, nonzero prohibited access, or leaked process;
- failure to restore all nine Task 8 postimage hashes.

## 10. Traceability matrix

| Requirement | Implementation | Tests/evidence |
| --- | --- | --- |
| REQ-RADIO-001 | association helper + root-scoped resolver | hidden positive plus 7 fail-closed DOM mutations |
| REQ-RADIO-002 | semantic input/action label split | real label click/rerender and native keyboard audit |
| REQ-RADIO-003 | direct label layout targets | 24px, overlap, clipping, overflow, scroll restoration |
| CFR-RADIO-001 | revoke, CAS rotate, fresh recovery ID | 57 + 10, contract reopen, 81 + 36 + 234 |
| CFR-RADIO-002 | authenticated anchored inverse/forward selector delta | exact 11 spans; exact 9 before-hashes then exact 9 posthashes |
| CFR-RADIO-003 | unchanged product contracts and cleanup | selector, navigation, full recovery, static, process gates |

Forward and backward traceability are complete: every requirement maps to a
code/document target and at least one executable test or authenticated runtime
gate. This focused amendment does not require a repository-wide
`.traceability.yaml` ledger.

## 11. Review history

| Iteration | Verdict | Findings and resolution |
| --- | --- | --- |
| 1 | BLOCKED | Review found `productionRollback.postimages: null`, two additional visible-radio false-green fixtures, the hardcoded stack SHA, and a postmigration-only dashboard assertion during the legacy interval. v0.2 adds an authenticated 9-file/11-span bidirectional delta and verifier, covers every hidden-radio fixture/fake, sequences the SHA after rotation, and uses phase-appropriate legacy gates. |
| 2 | READY | Closure test/lifecycle review found no blocker/High/Medium. Its one Low asked for explicit `spanId -> sessionKeys` mapping because the archived planning manifest used a different span partition; section 4.5 now requires that mapping and exact 11-key union. |
| 3 | BLOCKED | Impact closure found missing disabled/pointer/occlusion actionability, wording that could apply the forward delta twice, an ambiguous old-13/new-11 span relationship, a file-count mismatch, and stale version metadata. v0.3 adds non-mutating trial clicks inside exact scroll restoration, makes the delta the sole forward operation, freezes the exact 11-row map, reconciles generated artifacts, and aligns the version. |
| 4 | BLOCKED | A fresh closure pass required explicit independent Chromium actionability cases and one all-files transaction rather than sequential selector edits that could leave a mixed state. v0.4 makes every actionability mutation independently red/green, adds an all-nine/all-eleven preflight, requires one multi-file `apply_patch`, and proves zero partial writes or immediate forward recovery. |
| 5 | READY | Independent impact and test/lifecycle closure reviews found no remaining blocker, High, Medium, or Low finding. The 6.1 risk, actionability, exact span map, all-files transaction, authority lifecycle, and final Task 8 gates are executable. |

## 12. Pre-implementation blocking checklist

- [x] The diagnosed runtime failure and user request are covered.
- [x] Product code already passed independent review; remediation is isolated.
- [x] Exact final files, temporary files, risks, rollback, and verification are known.
- [x] Fail-first coverage includes actual hidden-input CSS and fail-closed mutations.
- [x] The hardcoded selector-test stack SHA is sequenced after rotation.
- [x] A verified all-legacy/all-migrated selector delta replaces the null
  production postimage authority before any temporary rollback.
- [x] Old recovery authority is revoked before worker edits.
- [x] Old evidence and namespaces remain immutable.
- [x] The Task 8 rollback/reapply uses anchored hunks and exact byte hashes.
- [x] Independent plan reviewers report no unresolved blocking issue.
- [x] Status is changed to `ACCEPTED EXECUTION AMENDMENT`.

Implementation must not begin while either unchecked item remains.

## 13. Change history

| Version | Date | Change |
| --- | --- | --- |
| v0.1-review | 2026-07-19 | Initial test-first worker, stack-rotation, baseline-replacement, and Task 8 resumption amendment. |
| v0.2-review | 2026-07-19 | Added the authenticated 9-file/11-span Task 8 delta, closed all hidden-radio false-green fixtures/fakes, and made legacy-interval verification phase-aware. |
| v0.3-review | 2026-07-19 | Added fail-closed actionability, sole-application wording, the exact operational span map, generated-artifact count, and consistent review metadata. |
| v0.4-review | 2026-07-19 | Added independent actionability red/green cases and two-phase all-files atomic inverse/forward selector transitions. |
| v0.4-accepted | 2026-07-19 | Recorded two independent READY closure reviews with no remaining severity finding. |
