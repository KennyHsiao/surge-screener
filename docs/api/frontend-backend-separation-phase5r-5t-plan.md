# Phase 5R-5T Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5o-5q-plan.md`

## Objective

Continue with three narrow Today Decision presentation slices that reuse
existing strict fixed clients without changing the API or OpenAPI surface:

1. **Phase 5R:** make only the Reversal latest candidate-count card consume the
   existing Reversal Radar latest client.
2. **Phase 5S:** make only the Oversold latest candidate-count card consume the
   existing Oversold Reversal latest client.
3. **Phase 5T:** make only the Today Decision Options Flow table consume the
   existing strict Options Flow feed client.

These are the fortieth through forty-second API-only slices. They do not make
Today Decision or Radar fully backend-owned.

## Entry evidence and boundaries

- After Phase 5Q, Today Decision has no local `validation_summary.json` read.
  Its remaining selected signal reads are `_flow_signals()` over
  `reports/options_flow/latest.json` and two `match_count` reads over the
  Reversal/Oversold `latest.json` files.
- `ReversalRadarData` already publishes strict `match_count` plus source-ordered
  ticker references; `OversoldReversalData` publishes strict `match_count` and
  its bounded display DTO. The two existing fixed clients already enforce
  provenance, unavailable metadata, no-store, size, deadline, and envelope
  behavior.
- `OptionsFlowFeedSignal` already includes every field used by Today Decision's
  table: `ticker`, `direction`, `flow_score`, `est_notional_usd`, `max_voi`, and
  `tags`. The existing `load_options_flow()` client preserves source order and
  caps the retained decoded response at 8 MiB.
- Daily summary, local Market Thesis forecast, ranked/scored feeds, all three
  validation cards, reconciliation, ledger, Trade State, candidate controls,
  quote fallback, navigation, providers, writers, and mutations are outside
  this plan except for regression assertions that prove they remain intact.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

### Phase 5R

- Proposed disposition: **GO, risk 4.0/10**.
- Resolve `load_reversal_radar()` exactly once in
  `_render_risk_and_research()` and derive only the `反轉候選` metric from its
  typed available result.
- Treat valid unavailable and every bounded client failure as authoritative;
  render the existing safe missing marker and never reread Reversal latest
  locally.
- Preserve the reconciliation, ledger, IBKR count, Oversold card, links, live
  Radar computation, Risk Guard, providers, and writers.

### Phase 5S

- Proposed disposition: **GO, risk 4.0/10**.
- Resolve `load_oversold_reversal()` exactly once in the same section and derive
  only the `蓄勢候選` metric from its typed available result.
- Available-empty remains a real zero; unavailable and every client failure use
  the existing safe marker without local fallback or raw reason leakage.
- Preserve the Reversal result, reconciliation/ledger siblings, standalone and
  embedded Oversold pages, scan instructions, providers, and writers.

### Phase 5T

- Proposed disposition: **GO, risk 4.8/10**.
- Resolve `load_options_flow()` exactly once only when the opportunity section
  renders. Convert at most the first eight typed source-ordered signals to the
  existing table presentation without a second request.
- Preserve the distinction among available rows, available-empty, authoritative
  unavailable, and bounded client failure. Empty/unavailable/failure states use
  stable safe copy, do not expose raw reason codes, and never read Options Flow
  latest locally.
- Preserve candidate tables, ticker handoff/actions, the standalone Options Flow
  live-chain provider, Schedules/Cockpit consumers, Trade State, producers, and
  writers.

## Affected files and implementation order

1. Add fail-first Today Decision tests for typed available, available-empty,
   unavailable, the complete client-failure matrix, exact one-request behavior,
   no selected local fallback, table field parity, and retained siblings.
2. Change only `ui/today_decision.py` to consume the three existing clients.
3. Remove `_flow_signals`, `_FLOW_DIR`, `_REVERSAL_DIR`, and `_OVERSOLD_DIR` only
   after repository search proves they have zero remaining Today consumers.
4. Synchronize `scripts/test_ui_candidate_feeds_api.py`, backend-boundary and
   navigation contracts, deterministic fixtures/counters, the user guide,
   endpoint inventory, implementation receipt, and relevant skill journals.
5. Add an exact UX successor receipt only if the measured diagnostic inventory
   changes; current evidence predicts no change because the Today diagnostic
   site IDs live in `_log_failure` and `_render_trust_boundary`, not in the
   selected helpers.

No model, artifact registry, API route, static OpenAPI, deployment, service,
Compose, dependency, provider, writer, or mutation change is planned.

## Verification gates

Run the Today candidate focused suite fail-first and passing; existing Options
Flow and Reversal/Oversold focused suites; shared read client; backend boundary;
navigation; deterministic fixtures; UX contract and measured inventory; deploy
and Docker contracts; Python 3.10 AST; compile/tabnanny; whitespace; frozen
artifact hashes; exact client-call searches; and zero-local-fallback searches.
Finish with complete `make test`, compare the actual diff against this plan, and
fix every blocking review finding before completion.

## Review record

- **Iteration 1:** traced all remaining Today signal latest reads and confirmed
  the three existing DTOs expose every selected rendered field. No API expansion
  or producer change is needed; private siblings remain separable.
- **Iteration 2:** verified request placement, available-empty semantics, safe
  failure behavior, retained reconciliation/ledger/Market Thesis/daily-summary
  boundaries, helper/constant zero-consumer gates, fixture implications, and
  the full verification surface. Final verdict: **GO** for a separate Phase
  5R-5T implementation instruction.
- **Iteration 3:** rechecked the accepted plan against the live dirty worktree,
  current branch/main ancestry, exact affected functions, fixture counters,
  verification commands, and retained risk areas before implementation. No
  unresolved blocker remained; final implementation verdict: **GO**.

## Implementation receipt

- Added fail-first coverage for typed populated/empty/unavailable results, the
  complete bounded client-failure matrix, exact one-request behavior, retained
  sibling state, table field parity, and zero selected local fallback.
- `ui/today_decision.py` now resolves the Reversal latest, Oversold latest, and
  Options Flow feed clients exactly once in their selected render sections. It
  removed `_flow_signals`, `_FLOW_DIR`, `_REVERSAL_DIR`, and `_OVERSOLD_DIR` only
  after zero-consumer proof. Daily summary, local Market Thesis forecast,
  reconciliation, ledger, Trade State, controls, providers, and writers remain
  on their prior boundaries.
- Synchronized deterministic fixtures/counters, backend-boundary/navigation/UX
  safety contracts, the user guide, and endpoint inventory. Measured UX
  diagnostics remain exactly 165, so no successor receipt was required.
- Post-implementation review found one stale user-guide statement that still
  described the Today Options Flow table as local. It was corrected; no code,
  regression, missing-test, maintainability, or unexplained scope-drift blocker
  remains.
- Verification passed: candidate feeds 11/11, Reversal/Oversold 9/9, Options
  Flow 10/10, API 47/47, read client 12/12, backend boundary 19/19, navigation
  63/63, fixtures 26/26, UX contract 19/19, deploy 18/18, Docker 11/11,
  Python compile/tabnanny, whitespace, exact-call/fallback searches, frozen
  hashes, and complete `make test`.
- API/OpenAPI/model/registry/deployment/dependency surfaces did not change. The
  API-only inventory is now 42 slices. The separately audited successor is
  `docs/api/frontend-backend-separation-phase5u-5w-plan.md`.
