# UX-1B Focused AX Evidence Remediation Plan

**Status:** ACCEPTED EXECUTION AMENDMENT — blocking Task 7

**Parent plan:** `2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md`

## Why this amendment exists

The canonical Task 6 manifests are internally sound: 117 captures and all 234
PNG/render-sidecar artifacts passed descriptor authentication, source closure,
counter closure, and namespace checks. A Task 7 readiness review nevertheless
found that the frozen focused browser stack records DOM roles, names, state,
and geometry without enforcing the parent plan's post-control replacement AX
contract for the eleven production roots.

In particular, the current focused stack does not execute or fail closed on:

- exact production radio/combobox accessible names and option labels;
- exactly one checked radio and one effective tab stop;
- ArrowLeft, ArrowRight, and Space behavior for every radio group;
- keyboard selection and restoration for the Analytics selectbox; or
- a 24 by 24 CSS-pixel minimum target for every focused radio option and the
  selectbox trigger.

The migration comparator already rejects root/subtree overflow, overlap, and
clipping, but it deliberately permits semantic changes below the eleven roots.
Without a separate replacement AX oracle, Task 7 would fail for a capture-stack
defect rather than only for the eleven legacy segmented widgets. That violates
the parent Task 7 gate, so selector migration remains blocked.

## Scope and invariants

This amendment may modify only the capture stack, its focused counter contract,
associated tests, Make/recovery metadata needed to re-freeze, and new immutable
evidence. It must not modify any of the nine production selector files or any
API/artifact loader behavior before the replacement Task 6 gate passes.

The existing `20260718T172855Z` pages/controls namespaces remain immutable.
They will be classified as superseded-by-contract-gap, never overwritten,
renamed, or deleted. A new capture-stack digest and a new recovery ID are
required.

## Implementation

### 1. Freeze an exact focused selection oracle

Add an exact, closed catalog for all eleven roots to both the browser worker and
trusted evidence validator. Each row binds case, session key, root selector,
replacement widget, accessible name, exact ordered options, and expected final
selection. Tests must prove both catalogs are identical and contain ten
horizontal radios plus the Analytics selectbox.

The catalog also binds the complete auxiliary-button projection. Exactly one
root, `ai_chat_mode`, may contain the existing `Help for 模式` Streamlit tooltip
button; the other ten roots permit none. Its role/name, tooltip ancestry,
widget-label ancestry, SVG semantics, and position before the option control
are exact capture-stack data, not a general exception for non-option buttons.

### 2. Collect real browser evidence without changing final business state

After the existing focused setup interaction, the worker must classify every
root as either the complete legacy segmented projection or the complete
replacement projection; mixed or unknown projections fail closed.
Every descendant role-button must belong disjointly to the exact legacy option
set or the exact auxiliary set, and those sets must exhaust all descendant
buttons. An extra, duplicate, forged, renamed, or misplaced button fails closed
in either phase.

The primary projection is equally closed: legacy requires one inner BaseWeb
button-group/radiogroup containing every ordered option; radio requires one
radiogroup containing every radio; selectbox requires one combobox and no
radiogroup. Empty forged groups, missing primary containers, or options moved
outside the primary fail closed. The one AI help button is additionally bound
to the unique widget label whose normalized visible text is exactly `模式`.

For a post-control radio, use real role locators and keyboard input to prove:

- one radiogroup with the exact accessible name;
- exact ordered radio labels and exactly one checked option;
- Tab returns to the selected option and a second Tab does not expose another
  tab stop in that group;
- ArrowRight selects the next option, ArrowLeft restores the contracted option,
  and Space preserves the selected required option;
- the application render generation does not change during the isolated native
  keyboard check and the final checked state is restored; and
- each clickable label target is at least 24 by 24, contained by its root and
  viewport, non-overlapping, and free of horizontal overflow.

The native radio check may stop propagation of the audited input's keyboard,
input, change, and click events without preventing their browser default action.
This keeps the real native semantics under test while preventing a temporary
audit selection from invoking a different production branch or changing the
final fixture state.

For the post-control Analytics combobox, use ArrowDown/Enter to select the exact
second table, then ArrowUp/Enter to restore the exact first table. Wait for the
owned selection-render generation after each committed selection. The legacy
Analytics segmented control must perform the equivalent second/first transition
so pre/post provider counters remain equal. Update its focused counter contract
and AppTest accordingly; no counter may be synthesized or ignored. The
combobox trigger is the production selector target and must meet the same 24 by
24, containment, and overflow checks.

Choice synchronization must use a bounded, unique button-or-radio role locator,
not a global text locator: Analytics tables legitimately contain hidden cells
whose text equals a control option. The legacy transition reopens the root and
reauthenticates its primary group and local selected state after each rerender.

### 3. Authenticate and enforce the observation

Add the focused observation as a canonical semantic field of the render
sidecar. The evidence API must validate exact keys, types, labels, ordering,
selection results, geometry, viewport containment, and phase projection before
accepting a staged sidecar.

Baseline validation must require a legacy observation for focused
`precontrol`. Migration comparison must require the exact accessible
radio/selectbox observation for focused `postcontrol`. The field is an allowed
control-root migration delta only after both phase-specific oracles pass.
Full-page and theme profiles must reject an unexpected focused observation.

### 4. Tests

Add focused tests that reject at least:

- a missing/extra root, option, or accessible name;
- any unknown auxiliary button or any drift in the one contracted help button;
- zero or two checked radios;
- a second tab stop;
- wrong ArrowLeft, ArrowRight, Space, or selectbox restore result;
- a target smaller than 24 by 24;
- target/root overflow, clipping, or overlap;
- mixed legacy/replacement widgets in one capture;
- a post-control manifest carrying legacy evidence; and
- any observation/counter mutation after descriptor authentication.

Run the existing isolation, evidence, fixture, snapshot, theme, contract, and
navigation suites plus Python 3.10 AST, `py_compile`, `tabnanny`, `compileall`,
`pip check`, and `git diff --check`.

### 5. Re-freeze and replacement Task 6 gate

Run control discovery and the real 390x844 smoke with the changed stack. After
they pass, atomically replace the canonical capture-stack contract, record its
new member hashes/digests, and classify `20260718T172855Z` separately as
superseded-by-contract-gap.

Choose one new immutable recovery ID and rerun the complete Task 6 command.
Require pages 81/81, controls 36/36, 234/234 authenticated artifacts, exact
source start/end equality, clean child exits, and zero prohibited access.
Independently reopen both manifests and all artifacts before freezing the new
hashes and nine unchanged production selector-file hashes in the recovery
document.

## Gates

Task 7 may resume only when all of the following are true:

1. the focused oracle has executable positive and adversarial coverage;
2. discovery and real smoke pass with the new capture stack;
3. the replacement Task 6 manifests pass 81/81 and 36/36 under one new digest;
4. all 234 artifacts are descriptor-reauthenticated;
5. the nine production selector files still equal their prechange hashes; and
6. an independent review finds no blocking diff, contract, or scope issue.

If the same remediation blocker survives three implementation/review
iterations, stop and report it instead of weakening the oracle.
