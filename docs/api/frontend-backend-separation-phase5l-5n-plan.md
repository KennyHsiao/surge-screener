# Phase 5L-5N Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5i-5k-plan.md`

## Objective

Continue with three narrow, independently reversible validation-presentation
slices:

1. **Phase 5L:** make only Today Decision's Market Thesis trust card reuse the
   existing strict Market Thesis validation client.
2. **Phase 5M:** add a fixed, strict, summary-only Oversold Reversal forward-
   validation API over the existing persisted validation artifact.
3. **Phase 5N:** make only the standalone/embedded Oversold Reversal forward-
   validation presentation consume that fixed API result.

Phase 5L is the thirty-sixth API-only slice. Phase 5M establishes a contract but
does not itself count as a UI slice; Phase 5N is the thirty-seventh. These phases
do not make Today Decision, Radar, or the Oversold lane fully backend-owned.

## Entry evidence and boundaries

- Today Decision currently reads all three trust-card summaries locally through
  one generic helper. Only the Market Thesis card has an existing strict public
  client. Reversal and Oversold trust-card summaries therefore remain explicit
  local siblings in Phase 5L.
- The Oversold lane's latest coiled-base snapshot is already API-only, while its
  forward-validation section still reads
  `reports/oversold_reversal/validation_summary.json` locally.
- The current validation artifact is about 105 KiB and contains a small rendered
  scoreboard inside a much richer private analytics source, including EV,
  equity curves, survivorship, S&P 500 cohort, cost assumptions, verdict detail,
  and notes. The public contract must validate the complete exact producer root
  but project only the fields rendered by the selected UI.
- `reports/continuation_strength.json` and
  `reports/playbook_validation/latest.json` are not currently present. They are
  deferred rather than inventing an ungrounded public contract or fixture.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

### Phase 5L

- Proposed disposition: **GO, risk 4.2/10**.
- Call `load_market_thesis_validation()` exactly once inside the trust-boundary
  render and derive only the Market Thesis maturity/detail copy from its typed
  available result.
- Treat valid unavailable and every bounded client failure as authoritative:
  show fixed safe partial-state copy and never reread the Market Thesis
  validation artifact locally.
- Rename or narrow the remaining local helper so repository search proves it is
  used only for Reversal and Oversold. Preserve those cards, Market Thesis
  forecast/daily summary, candidate clients, controls, providers, navigation,
  Trade State, and all writers.

### Phase 5M

- Proposed disposition: **GO, risk 5.8/10**.
- Advance the additive draft API/OpenAPI version from `1.14.0-draft` to
  `1.15.0-draft` and keep the existing path surface unchanged except for the
  one fixed route below.
- Add parameter-free
  `GET /api/v1/signals/oversold-reversal/validation` with source ID
  `signals.oversold-reversal.validation`. Clients control no path, filename,
  tier, or field selection.
- Validate the complete exact current producer root and its exact three tier
  keys. Enforce timestamp, count arithmetic, tier count/rate/Wilson interval
  invariants, finite values, and conservative bounds. Accept only the exact
  producer verdicts `PROVISIONAL — sample below threshold, indicative only`
  and `MATURE`, and require the chosen verdict to agree with the conservative
  minimum-resolved threshold.
- Project only `entries_accumulated`, `min_resolved_across_tiers`,
  `min_resolved_for_verdict`, `verdict`, and ordered `by_tier` rows containing
  `resolved`, `hits`, nullable `hit_rate`, and the two-value `wilson90` interval.
  Put the timezone-aware source timestamp only in envelope `generatedAt`.
- Keep `price_resolvable`, dropped metrics, `verdict_by_tier`, survivorship,
  S&P 500 cohort, cost assumptions, caveats, notes, maturity flags, EV fields,
  beta/excess diagnostics, and every equity-curve point private.
- Use the standard no-store HTTP 200 available/unavailable envelope and an
  exact 32 KiB decoded client response cap. Missing, unreadable, malformed, or
  shape-invalid sources fail soft; an oversized client response is a bounded
  client failure. Neither path invokes a scan, forward harness, provider, or
  writer.

### Phase 5N

- Proposed disposition: **GO, risk 4.6/10**.
- Replace only `_render_forward_validation()`'s local artifact read with one
  typed fixed-client result. Preserve current render ordering: the validation
  request occurs only when the already-API-backed latest snapshot reaches that
  section.
- An available projection renders the existing verdict banner and tier table.
  Unavailable and each bounded client failure show fixed safe copy without
  exposing raw reasons and without falling back to local JSON.
- Preserve the latest-snapshot API, scan instructions, lane framing, local scan
  and forward writers, caveat copy, Radar embedding, providers, session state,
  navigation, and every other Radar lane. Today Decision's Oversold trust card
  remains local for a later separately reviewed adoption.

## Affected files and implementation order

### Phase 5L

- Extend a focused Today Decision test for available, available-empty,
  unavailable, every bounded client failure, exactly one request, no selected
  local fallback, and unchanged Reversal/Oversold cards.
- Change only the selected trust-card read/state in `ui/today_decision.py` and
  synchronize measured boundary/navigation/fixture expectations.

### Phase 5M

- Add fail-first real-artifact, malformed-source, closed-projection, invariant,
  route/OpenAPI, provenance, cap, failure, and recovery tests.
- Add strict DTOs in `api/models.py`; source validation/projector/registry in
  `api/artifacts.py`; route/envelope in `api/main.py`; static OpenAPI parity in
  `docs/api/quant-radar-v1.openapi.yaml`; and an immutable fixed client in
  `ui/_read_api.py`.

### Phase 5N

- Extend the Oversold/Reversal focused suite for all typed states, exact request
  count, local-read absence, preserved latest-snapshot behavior, and embedded
  Radar isolation.
- Replace only the validation reader in `ui/oversold_reversal_lane.py`.

For all phases, update Makefile coverage, backend-boundary and navigation
contracts, deterministic fixture counters, UX successor receipt only if the
measured diagnostic inventory changes, user guide, endpoint inventory,
implementation receipt, and relevant skill journals.

## Verification gates

Run fail-first focused suites, current Market Thesis and Reversal/Oversold
regressions, API/OpenAPI parity, fixed-client tests, backend-boundary,
navigation, deterministic fixtures, UX contract, deploy and Docker contracts,
Python 3.10 AST, compile/tabnanny, whitespace, source-hash, and no-local-fallback
searches. Finish with complete `make test`, compare the actual diff to this
plan, and fix every blocking review finding before claiming completion.

## Frozen entry artifacts

- Market Thesis validation summary:
  `b1fd5426006048869ff1bd6d01e0d461d9b75488e44f95f24d006eb519604f62`
- Oversold Reversal validation summary:
  `d072d4a9e973a7a6f8fe4ac2c776159016fba9e995af2a8158611ffdfe62b1d9`

## Review record

- **Iteration 1:** no scope or runtime blocker found. Tightened the additive
  draft version, exact client cap, closed verdict derivation, and the distinction
  between server-source validation and client response-size failure.
- **Iteration 2:** verified both frozen hashes, the real producer's exact root,
  tier order, count arithmetic, verdict literals, current client/page seams,
  absent deferred artifacts, and the existing `1.14.0-draft` route surface.
  The affected files, failure semantics, retained siblings, request counts, and
  verification gates cover the full user request. Final verdict: **GO** for a
  separate Phase 5L-5N implementation instruction.

## Implementation receipt

- **Phase 5L:** Today Decision now resolves its Market Thesis trust card from
  exactly one strict validation-client result. Reversal and Oversold remained
  local siblings in this phase, and unavailable/failure states show stable safe
  copy without selected fallback.
- **Phase 5M:** draft API/OpenAPI `1.15.0-draft` adds fixed no-store
  `GET /api/v1/signals/oversold-reversal/validation`, source ID
  `signals.oversold-reversal.validation`, a complete-source validator, bounded
  public projection, strict envelope, immutable client outcomes, and a 32 KiB
  decoded response cap.
- **Phase 5N:** the standalone and Radar-embedded Oversold forward-validation
  presentation now uses exactly one typed API result, only after an available
  latest snapshot reaches the section. It has no local validation fallback;
  scan instructions, writers, providers, latest-snapshot API, and all other
  Radar lanes remain unchanged.
- **Measured inventory:** thirty-seven API-only slices. The selected Oversold UI
  diagnostic removal was bound to exact successor receipt
  `(1, 141, d2ce2dded2e652f87af2afad8293b82c85ad6f474cc3938c62d81f944c52e984)`,
  reducing the measured diagnostic inventory from 166 to 165.
- **Review fixes:** corrected an initially over-strict source validator so valid
  provisional artifacts follow the Oversold producer's actual maturity gates;
  added embedded/latest-unavailable request-isolation tests; removed an
  unreachable DTO fallback; and advanced two stale pre-existing feature-test
  expectations from draft `1.14.0` to `1.15.0` after complete-suite parity found
  them. These are necessary contract/test synchronizations; no unexplained
  scope drift remains.
- **Verification:** focused candidate feeds 9/9, Reversal/Oversold 8/8, Market
  Thesis summaries 5/5, API 47/47, fixed client 12/12, boundary 19/19,
  navigation 63/63, UX contract 19/19, deterministic fixtures 26/26, deploy
  18/18, Docker 11/11, Money Flow 6/6, Sector Rotation 5/5, static/compile/hash
  gates, and complete `make test` pass.
- **Artifact integrity:** both frozen entry artifacts remained byte-identical.
  The audited successor is
  `docs/api/frontend-backend-separation-phase5o-5q-plan.md`.
