# UX-1B Focused Semantic Readiness Remediation

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.0 |
| Status | ACCEPTED FOR EXECUTION |
| Author | Codex / Scribe-equivalent local gate |
| Reviewer | Independent post-change reviewer required |
| Audience | Capture-stack implementer and reviewer |
| Parent | `2026-07-18-quant-radar-ui-ux-ux1b-focused-ax-remediation.md` |

## Objective

Remove the intermittent false rejection in sequential Analytics focused
captures without weakening the terminal focused-control oracle. After this
amendment, discovery, real smoke, and refreeze may resume under the parent
plan.

## Scope

In scope:

- semantic readiness classification in `scripts/ui_ux_browser_worker.py`;
- focused Chromium regression coverage in `scripts/test_ui_ux_evidence.py`;
- the existing focused verification suites and disposable discovery/smoke;
- recovery documentation and capture-stack refreeze only after every gate
  below passes.

Out of scope:

- all nine production selector files;
- API, artifact-loader, Streamlit fail-soft, and business-provider behavior;
- mutation, replacement, deletion, or reuse of recovery ID
  `20260718T172855Z` or either Attempt 4 namespace;
- publishing a new canonical capture-stack contract before discovery and real
  smoke pass.

## Root-cause review

Observed timeline:

1. Unit and synthetic coverage passed, including a zero-projection root that
   later became complete.
2. A real Analytics desktop capture passed, but a later viewport in the same
   app group intermittently returned a generic `WorkerBootstrapError`.
3. A fresh audit passed the exact desktop-to-tablet runner path and repeated
   fresh sessions, so the symptom is timing-dependent rather than a permanent
   Analytics contract mismatch.
4. Code inspection found a deterministic readiness gap: lines 2113-2205 of
   `scripts/ui_ux_browser_worker.py` classify a projection from broad
   role/count shape, while lines 1632-1700 immediately require the BaseWeb
   primary, exact option order, and selected state. A DOM can therefore be
   classified as complete during a Streamlit patch and be rejected before the
   exact semantics settle.

Three hypotheses were reviewed:

- H1 — broad shape becomes visible before exact primary/selection semantics.
  Supported by the split readiness/validation code paths and the missing
  partial-semantic test. This is the remediation target.
- H2 — the tablet geometry oracle is intrinsically invalid. Not supported:
  the same exact tablet path passed during the fresh audit, and no geometry
  contract mismatch was observed.
- H3 — state or counter leakage persists between viewport workers. Not
  supported: fresh browser sessions and the exact desktop-to-tablet runner
  passed, and disposable cleanup left no fixture or worker process.

Severity is Medium for the application and blocking for the evidence pipeline.
Confidence is Medium until the new deterministic regression is red against the
current worker and green after the fix.

## Requirements and acceptance criteria

### REQ-001 — Wait for exact semantic readiness

The worker MUST classify a focused root only after its non-mutating primary
structure, ordered options, and contracted selected state are present.

- `AC-UX1B-READINESS-001`: Given a legacy root whose role/button counts are
  complete before its BaseWeb primary metadata, when the metadata becomes
  exact within the deadline, then collection succeeds with
  `legacy-segmented` evidence.
- `AC-UX1B-READINESS-002`: Given a legacy root whose selected `kind` state is
  temporarily incomplete, when the exact one-active state appears within the
  deadline, then collection succeeds without changing business state.
- `AC-UX1B-READINESS-003`: Given a radio root whose count projection is
  complete before its exact ordered labels and one checked state, when the
  semantic projection becomes exact within the deadline, then collection
  proceeds to the unchanged native keyboard oracle.
- `AC-UX1B-READINESS-004`: Given a selectbox root whose combobox exists before
  the contracted selected text, when the selected text becomes exact within
  the deadline, then collection proceeds to the unchanged keyboard/restore
  oracle.
- `AC-UX1B-READINESS-010`: Given an owned Analytics alternate or restore
  interaction whose render generation has advanced, when the replacement DOM
  is still patching, then the worker waits for two consecutive identical
  semantic snapshots of the expected new selection before validating layout
  or starting the next interaction. Each alternate and restore interaction is
  committed exactly once; no interaction is retried.
- `AC-UX1B-READINESS-011`: A projection that is exact for only one observation
  and then becomes partial, reordered, or wrongly selected is not ready. Two
  time-separated, atomically collected, identical full semantic snapshots are
  required.

### CFR-001 — Remain fail closed

No partial, mixed, forged, duplicate, misordered, wrongly selected, or
unexpected auxiliary projection may be accepted.

- `AC-UX1B-READINESS-005`: Stable malformed versions of every new delayed
  fixture fail with `WorkerBootstrapError` by the bounded deadline.
- `AC-UX1B-READINESS-006`: Final phase classification and the trusted
  `controlEvidence` validator remain byte-for-byte strict; readiness may delay
  rejection but may not convert invalid evidence into accepted evidence.
- `AC-UX1B-READINESS-007`: Worker responses retain the existing generic safe
  failure boundary; no internal DOM or filesystem detail is exposed.

### CFR-002 — Preserve evidence and scope

- `AC-UX1B-READINESS-008`: The existing canonical contract retains SHA-256
  `197fb7ab9dd030f63a73c83aac30a3ef1f73daee69a5c71fdfe8fd265ab76424`
  until the final refreeze transaction.
- `AC-UX1B-READINESS-009`: The two `20260718T172855Z` Attempt 4 namespaces and
  all nine production selector hashes remain unchanged.

## Implementation checklist

### Pre-implementation

- [x] Existing plan covers the requested continuation and identifies this
  blocker before refreeze.
- [x] Affected files, verification commands, preservation boundaries, and
  failure risks are known.
- [x] Current 45/45 evidence and 5/5 selection-fixture suites pass.
- [x] No unresolved destructive, credential, production-data, or scope blocker
  remains.

### Tests first

- [ ] `TEST-001`: Add a real Chromium legacy fixture with complete broad counts
  and delayed BaseWeb primary metadata; prove it fails before the fix.
- [ ] `TEST-002`: Add delayed legacy selected-state coverage.
- [ ] `TEST-003`: Add delayed checked-radio and delayed selectbox-selection
  coverage, including radio ordered-label stabilization, without bypassing
  their final interaction oracles.
- [ ] `TEST-004`: Pair each delayed-positive case with a stable malformed
  bounded rejection.
- [ ] `TEST-005`: Add a one-observation exact flicker followed by partial,
  reordered, or wrongly selected semantics; prove the worker does not accept
  it and waits for two identical exact snapshots.
- [ ] `TEST-006`: Delay the exact semantic state after each Analytics
  alternate and restore generation advance for both legacy and selectbox
  fixtures. Assert each interaction is dispatched exactly once and the final
  generation/state is restored.

### Implementation

- [ ] `IMPL-001`: Replace broad count-only readiness with an exact,
  non-mutating semantic snapshot for legacy, radio, and selectbox projections.
- [ ] `IMPL-002`: Add one non-mutating semantic-stability helper that requires
  two time-separated, atomically collected, identical full snapshots for an
  expected phase and selected label. Use it before the first collector and
  after every owned Analytics generation advance, before strict
  alternate/restore validation or the next interaction.
- [ ] `IMPL-003`: Treat incomplete or contradictory snapshots as not ready
  until the deadline, then reject. Do not catch-and-ignore collector failures,
  alter expected labels/state, or loosen trusted validation.
- [ ] `IMPL-004`: Keep interaction dispatch outside the readiness retry loop.
  The helper may re-observe DOM state only; it must never repeat a click,
  Arrow/Enter commit, provider call, or render-generation advance.

### Verification

- [ ] Run the targeted semantic-readiness regression and prove the pre-fix red
  case is green.
- [ ] Run `scripts/test_ui_ux_evidence.py` (expected 45/45 or higher).
- [ ] Run `scripts/test_ui_ux_selection_fixture.py` (expected 5/5).
- [ ] Run isolation, fixtures, snapshot, theme, theme-matrix, contract, and
  dashboard-navigation suites.
- [ ] Run Python 3.10 AST parsing, `py_compile`, `compileall`, `tabnanny`,
  `pip check`, and `git diff --check`.
- [ ] Run the real Analytics desktop/tablet/mobile/narrow sequence at least
  twice in disposable runtimes.
- [ ] Run exact 57-row control discovery and exact 10-row real mobile smoke.
- [ ] Verify no disposable fixture/worker remains and the canonical/Attempt 4
  hashes still match.
- [ ] Obtain an independent focused review with zero blocking High/Medium
  findings.

### Refreeze and continuation

- [ ] Only after every verification gate passes, atomically refreeze the
  capture-stack contract under a new digest.
- [ ] Execute the replacement Task 6 baseline under one new immutable recovery
  ID; require pages 81/81, controls 36/36, and all 234 artifacts reopened and
  authenticated.
- [ ] Continue parent Task 7 only after the replacement Task 6 gate passes.

## Risks and rollback

- Risk: waiting on every invalid projection could lengthen negative paths.
  Unit tests use short explicit deadlines; production capture keeps its bounded
  deadline and still rejects.
- Risk: a second non-atomic locator read can observe another transient state.
  The semantic snapshot should be collected atomically where practical and
  must be stable across consecutive observations.
- Risk: a retry after a business-state interaction could repeat side effects.
  Readiness is strictly non-mutating. It runs before the first interaction and
  after each observed generation advance, while the click or keyboard commit
  remains outside the observation loop and occurs exactly once.
- Rollback: revert only the new worker/test hunks. The prior canonical contract
  and Attempt 4 evidence remain untouched and separately classified.

## Traceability

| Requirement | Implementation | Tests | Gate |
| --- | --- | --- | --- |
| REQ-001 | IMPL-001, IMPL-002, IMPL-004 | TEST-001, TEST-002, TEST-003, TEST-006 | 45+ focused evidence tests |
| CFR-001 | IMPL-001, IMPL-003 | TEST-004, TEST-005 plus existing mutation suite | 57 discovery + 10 smoke |
| CFR-002 | No pre-gate canonical write | hash/process/scope checks | refreeze transaction only after PASS |

## Plan review verdict

`READY`: the plan satisfies the requested continuation, keeps final acceptance
strict, names all affected files and checks, and has no unresolved blocking
issue. Any implementation divergence requires a new recorded review before
refreeze.
