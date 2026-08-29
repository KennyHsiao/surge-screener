# Quant Radar UI/UX — UX-1B Current-Main Superseding Plan

## Document Info

| Field | Value |
|---|---|
| Version | v0.1 |
| Status | `READY FOR MAINTAINER ACCEPTANCE — IMPLEMENTATION NOT STARTED` |
| Baseline | `main@8e5e37ab1a252080f5066e4104cb5c5ce99d0fe3` on 2026-08-29 |
| Owner / approver | Repository maintainer |
| Audience | Maintainers, UI engineers, reviewers, and 7F operators |
| Traceability | `2026-08-29-quant-radar-ui-ux-ux1b-current-main-superseding.traceability.yaml` |

## Decision and Authority

This plan replaces the **execution authority**, but not the historical evidence,
of the 2026-07-16 UX-1B plan and its Task 9 / Sequence 1-20 amendment chain.
Those records remain immutable explanations of the earlier design and review
work. Their exact-hash entry receipts no longer describe current main and MUST
NOT authorize production changes.

This documentation batch authorizes only rebaseline and planning. Production UI
or dependency edits require maintainer acceptance of this plan followed by a
fresh execution-entry receipt against the then-current main. If main changes
after that receipt and before the production edit, regenerate and review the
receipt; do not extend another permanent hash-amendment chain.

## Current-State Reconciliation

### UX-1A

UX-1A is **complete with high confidence**. The accepted evidence records 20/20
focused and 21/21 regression Chromium captures, screenshot inspection, exact
provider parity, zero captured overflow, and passed component/contract safety
tests. Current-main focused checks also pass:

- `scripts/test_ui_ux1a_safety.py`: 5/5;
- `scripts/test_ui_ux_components.py`: 6/6;
- `scripts/test_ui_ux_contract.py`: 19/19.

Real Safari remains `NOT_CHECKED` and a participant SUS/SEQ study remains
`NOT_RUN`. Those are final redesign evidence gaps; they do not reopen UX-1A.
The mobile sidebar and floating-AI overlap remain UX-2 scope.

### UX-1B

UX-1B is **in progress, not complete**. Current main contains the historical
classification, deterministic theme tooling, selector review work, and passing
static contract/theme tests. It does not contain the approved global semantic
theme implementation:

- `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json` is still `pending`;
- `.streamlit/config.toml` still uses the red primary color;
- `ui/_design.py` still maps the global interactive primary token to red;
- `app.py` does not call the planned `build_global_theme_css()` site;
- no fresh current-main 27-page × three-viewport before/after receipt closes
  contrast, state, visual, provider, and rollback gates.

Several source hashes named by the 2026-07-31 authority amendment have changed
through later frontend/backend and Analytics work. Current static tests passing
proves compatible scaffolding, not production UX-1B completion.

## Goal and Success Metrics

Complete the approved Calm Decision Cockpit semantic interaction-color
correction without changing page information architecture, data semantics,
providers, actions, or backend behavior.

Success requires:

- all 27 registered pages captured at desktop, tablet, and mobile before and
  after the theme batch: exactly 81/81 valid captures in each matrix;
- zero unexpected page exceptions, failed external/provider calls, or component
  and page horizontal overflow introduced by the change;
- normal interaction, focus, hover, selected, disabled, warning, error, and
  destructive states remain visually distinct and meet the documented contrast
  matrix;
- UX-1A owned components and their content/order/provider counters remain
  unchanged except for approved semantic color differences;
- rollback rehearsal restores the exact pre-theme source and deterministic
  capture result;
- classification and current status documents close only after all evidence is
  reviewed.

## Scope

### In Scope

- current-main inventory of global interaction CSS, theme tokens, primary action
  sites, unsafe HTML sites, and the 27-page navigation surface;
- a fresh deterministic pre-theme 81-capture baseline;
- the smallest reviewed semantic-theme production batch, expected to be
  `.streamlit/config.toml`, `app.py`, and `ui/_design.py`;
- dependency changes only if the entry review proves the current installed and
  declared Streamlit contract cannot reproduce the matrix;
- contrast/state fixtures, automated/static guards, before/after review,
  rollback rehearsal, documentation, and classification closure;
- post-deploy 7F API/Streamlit health and non-interference smoke checks.

### Out of Scope

- UX-2 mobile shell, navigation, sidebar, or floating-AI placement;
- UX-3 Today Decision information architecture and UX-4 page migration;
- copy, ranking, scoring, candidates, reports, providers, schedules, Analytics,
  database, API, credentials, picks, ledger, or Risk Guard behavior;
- synthesizing Safari or participant evidence; those must remain truthful
  `NOT_CHECKED` / `NOT_RUN` until actually performed;
- reviving or mutating the historical Sequence 1-20 records.

## Requirements

- `REQ-UX1B-001` — Execution MUST begin from a reviewed current-main receipt;
  stale historical hashes MUST fail closed and MUST NOT trigger another
  amendment chain.
- `REQ-UX1B-002` — The global semantic theme MUST distinguish ordinary
  interaction from warning, error, and destructive meaning across all states.
- `REQ-UX1B-003` — The change MUST preserve UX-1A content, action identity,
  ordering, and provider/network behavior.
- `REQ-UX1B-004` — The complete 27-page, three-viewport matrix MUST pass before
  and after the production batch, with every final screenshot reviewed.
- `REQ-UX1B-005` — Classification and status MUST remain `pending` until the
  implementation, visual, contrast, rollback, PR, deployment, and 7F gates pass.
- `CFR-UX1B-001` — Production changes MUST be an atomic, reversible UI-only
  batch with exact rollback evidence.
- `CFR-UX1B-002` — No data/provider/write path may execute because of capture,
  inspection, theme generation, or rollback.
- `CFR-UX1B-003` — Required contrast MUST meet WCAG 2.2 AA: at least 4.5:1 for
  normal text, 3:1 for large text and meaningful UI component boundaries.
- `CFR-UX1B-004` — Credentials, private payloads, raw diagnostics, paths, and
  runtime secrets MUST NOT enter screenshots, manifests, CSS, or commits.

## Acceptance Criteria

- `AC-UX1B-001`: Given the historical amendment hashes or an execution receipt
  differ from current main, when implementation entry is evaluated, then it
  stops before a production edit and emits a fresh reviewable receipt.
- `AC-UX1B-002`: Given any ordinary primary action, when default, hover, focus,
  active, selected, or disabled state is rendered, then it is distinct from
  warning/error/destructive semantics and meets the applicable contrast rule.
- `AC-UX1B-003`: Given the unchanged UX-1A fixtures, when pre/post matrices are
  compared, then identity, order, visible copy, action count, and provider
  counters match except for allowlisted semantic style differences.
- `AC-UX1B-004`: Given all 27 registered pages at three viewports, when each
  before/after capture command completes, then exactly 81/81 captures are valid,
  quiescent, overflow-free, exception-free, and manually reviewed.
- `AC-UX1B-005`: Given a failure in static, browser, contrast, visual, or deploy
  verification, when rollback runs, then the exact pre-theme files and baseline
  result are restored and UX-1B remains `pending`.
- `AC-UX1B-006`: Given every technical and deployment gate passes, when closure
  is recorded, then the classification references the new receipt/evidence and
  UX-2 remains separately unstarted.
- `AC-UX1B-007`: Given real Safari or participant evidence was not collected,
  when UX-1B closes, then those limitations remain explicitly unverified and no
  synthetic score is substituted.
- `AC-UX1B-008`: Given deterministic fixtures, manifests, screenshots, CSS,
  logs, and the final diff, when sensitive-data inspection runs, then no
  credential, private payload, raw diagnostic, path, or runtime secret appears.

## Implementation Plan

### Phase 0 — Execution Entry and Blocker Review

- `IMPL-UX1B-001` — Record then-current main SHA, clean isolated worktree,
  installed/declared Streamlit versions, 27-page route inventory, affected-file
  inventory, and current hashes in one generated receipt.
- Re-run current UX-1A, UX contract, theme static, safety, and navigation tests.
- Confirm the accepted plan covers the current files, verification matrix, data
  non-interference, deployment, and rollback. Any unresolved blocker stops work.

### Phase 1 — Fresh Pre-Theme Baseline

- `IMPL-UX1B-002` — Run the existing no-provider deterministic fixture server
  and capture all 27 pages at desktop, tablet, and mobile.
- Inspect every screenshot and manifest. Record known UX-2 shell issues without
  misclassifying them as new UX-1B failures.
- Freeze only this execution receipt and baseline, not the historical plan chain.

### Phase 2 — Fail-First Theme Contract

- `IMPL-UX1B-003` — Add or update focused tests for semantic token separation,
  primary-site classification, trusted static CSS generation, state contrast,
  unsafe-HTML containment, and deterministic output.
- Prove the tests fail for the current red ordinary-interaction mapping before
  production edits and pass only for the reviewed semantic mapping.

### Phase 3 — Atomic Production Batch

- `IMPL-UX1B-004` — Change only the reviewed theme/token/CSS-injection files.
  Do not change page layout, copy, actions, providers, or data behavior.
- Do not pin or upgrade Streamlit unless Phase 0 produced a documented
  reproducibility blocker and the dependency change was separately reviewed.

### Phase 4 — Post-Theme Matrix and Visual Review

- `IMPL-UX1B-005` — Re-run focused/static/full UI tests and the complete 81-case
  matrix. Inspect all final screenshots and compare the deterministic manifests.
- Review default/hover/focus/active/selected/disabled/warning/error/destructive
  state fixtures at original resolution.

### Phase 5 — Rollback and Release

- `IMPL-UX1B-006` — Rehearse rollback in isolation, prove exact pre-theme file
  restoration and baseline compatibility, then reapply the reviewed batch.
- Run focused tests, relevant full tests, compile/static/diff checks, independent
  code review, PR checks, deployment, and 7F API/Streamlit smoke verification.
- Only then update the UX-1B classification and current status; do not close
  UX-2, Safari, or participant-study work.

## Verification Matrix

| Test ID | Verification |
|---|---|
| `TEST-UX1B-001` | Stale hash and post-receipt drift both block production entry. |
| `TEST-UX1B-002` | Token/site/static-CSS tests enforce semantic state separation. |
| `TEST-UX1B-003` | Contrast fixtures meet the exact AA thresholds. |
| `TEST-UX1B-004` | Pre-theme and post-theme 27×3 manifests pass exactly 81/81. |
| `TEST-UX1B-005` | UX-1A identity/order/copy/provider counters remain compatible. |
| `TEST-UX1B-006` | Capture and theme generation execute no live/provider/write path. |
| `TEST-UX1B-007` | Rollback restores exact files and deterministic baseline behavior. |
| `TEST-UX1B-008` | PR/deploy/7F API and Streamlit health pass with no data changes. |
| `TEST-UX1B-009` | Sensitive-data inspection covers fixtures, manifests, screenshots, CSS, logs, and diff. |

## Risks and Controls

- **Historical authority confusion:** the new receipt is the only executable
  authority; old plans remain evidence only.
- **Broad selector regressions:** inventory every primary site and use explicit
  state fixtures plus the full route matrix.
- **False visual PASS:** capture count alone is insufficient; every screenshot
  and every allowlisted difference needs review.
- **Provider or mutation side effects:** deterministic fixtures and counter
  quiescence are hard gates.
- **Scope expansion into UX-2:** known sidebar and floating-AI overlap remain
  recorded but do not justify shell edits in this batch.

## Blocking Review

- **Iteration 1:** rejected executing the 2026-07-31 frozen-hash amendment; its
  source receipt has materially drifted.
- **Iteration 2:** rejected treating passing static theme tests as completion;
  the production mapping, current 81-case baseline, and closure receipt are
  absent.
- **Iteration 3:** narrowed dependency scope. `requirements.txt` changes only
  for a demonstrated current reproducibility blocker, not because the old plan
  named a historical version.

No blocker remains for maintainer acceptance of this plan. Implementation is
not authorized by this documentation batch.

## Reviewers and Change History

Required reviewers: repository maintainer, UI implementation reviewer, and an
independent verification reviewer.

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-29 | Reconciled UX-1A/UX-1B on current main and replaced stale hash-chain execution authority. |

## Glossary

- **Execution receipt:** a generated current-main record of version, route,
  affected-file, and hash inputs used for one implementation attempt.
- **Semantic interaction color:** an ordinary action color whose meaning is not
  conflated with warning, error, or destructive states.
- **Provider quiescence:** deterministic evidence that the UI capture caused no
  external/provider request or writer execution.
