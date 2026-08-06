# Phase 5F-5H Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-04
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5c-5e-plan.md`

## Objective

Continue with three narrow, independently reversible presentation reads:

1. **Phase 5F:** make only the standalone Options Cockpit Social Intelligence
   quick-pick source API-only through the existing strict Social client.
2. **Phase 5G:** add a strict public Market Thesis forward-validation summary
   and make only that page section API-only.
3. **Phase 5H:** add a strict summary-only Market Thesis regime-history read
   and make only that page section API-only.

These phases do not make either composite page fully API-backed. Trade State,
private IBKR watchlists, legacy X picks, live providers, refresh/generation,
validation writers, the raw regime corpus, session state, and all mutations
remain on their current boundaries.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

- **5F — GO, risk 3.8/10.** `SocialIntelligenceData` already contains the US
  ticker, labels, and `mentioned_by` fields used by the quick-pick label. Use
  one fixed client call in standalone mode only. A CRYPTO snapshot is not a US
  result. Available-empty, unavailable, and client failure never read Social
  latest locally; the separately persisted legacy X-picks compatibility source
  remains an independent sibling, as do the private IBKR watchlist and the
  already migrated scored/Options Flow sources. Embedded mode stays isolated.
- **5G — GO, risk 5.0/10.** The real validation artifact is small (578 bytes)
  but contains non-presentation fields such as `invalid_records`,
  `rejected_ledgers`, benchmark/configuration data, and notes. The new strict
  DTO may expose only the rendered counters and bounded `by_key` rows:
  validation status, resolved/matured/minimum threshold, reject/invalid counts,
  and finite hit-rate/Wilson metrics. Missing, malformed, invalid, oversized,
  unavailable, and client failure states must fail soft without local fallback.
- **5H — GO, risk 5.4/10.** The real regime artifact is about 2.3 MiB because it
  includes daily observations, runs, correction episodes, rules, and VIX data.
  None of those raw collections may enter the response. Project exactly three
  regime summaries and three forward windows with only days, mean, up-rate,
  P10, and worst values, using finite bounded numerics and a small response cap.
  The UI's existing missing-corpus note remains the unavailable presentation.

No client-controlled path, private position, credential, command, mutation,
provider call, N+1 request, or raw diagnostic is introduced.

## Affected files and implementation order

### Phase 5F

- Add a focused fail-first Cockpit Social quick-pick suite.
- Update only `ui/options_cockpit.py::_watchlist_quickpick()` and typed helpers
  needed to consume `_read_api.load_social_intelligence()` once.
- Preserve source ordering, legacy compatibility behavior, all non-Social
  sources, and standalone/embedded isolation.

### Phase 5G

- Add exact validation-summary models/projector/spec/route to
  `api/models.py`, `api/artifacts.py`, and `api/main.py`.
- Add a fixed, bounded, strict client result to `ui/_read_api.py`.
- Replace only `_render_validation(_load(...validation_summary.json))` in
  `ui/market_thesis.py`; keep rendering semantics and fixed safe copy.

### Phase 5H

- Add exact regime-summary models/projector/spec/route over the fixed artifact.
- Add a separate fixed, bounded, strict client result.
- Replace only `_render_regime_reference()`'s selected local read. Never send
  or retain the source `daily`, `regime_runs`, `correction_episodes`, `rules`,
  `vix`, benchmark, or note fields in the public DTO.

For all three phases, extend API/OpenAPI, client, backend-boundary, navigation,
deterministic fixture, and UX successor contracts only where measured. Update
the Makefile, user guide, endpoint inventory, receipts, and skill journals.

## Verification gates

Run fail-first focused tests, real-artifact strict projection tests, all current
Social/Cockpit/Market Thesis regressions, API/OpenAPI parity, fixed-client,
backend-boundary, navigation, deterministic fixture, deployment, Docker, UX,
Python 3.10 AST, compile/tabnanny, whitespace, and frozen-artifact checks.
Finish with complete `make test`; loopback suites may use the already-reviewed
sandbox-external execution. Compare the actual diff to this plan and resolve
every blocking review finding before completion.

## Frozen entry artifacts

- Market Thesis validation summary:
  `b1fd5426006048869ff1bd6d01e0d461d9b75488e44f95f24d006eb519604f62`
- Market Thesis regime history:
  `07f7a355d912ee8516d3ea4cf40e9fe392cdb7e3e581eac9c011df7a3aad3e83`
- Social latest is currently absent, which is an intentional unavailable-state
  fixture; implementation must not create or rewrite it.

## Implementation receipt

Phase 5F reuses the existing strict Social client once in standalone Options
Cockpit quick-picks. Phase 5G and Phase 5H add two fixed, bounded Market Thesis
summary endpoints and strict clients; the page no longer reads either selected
artifact locally. Private IBKR/legacy X sources, providers, strategy logic,
writers, raw validation diagnostics, and the 2.3 MiB regime corpus remain on
their accepted boundaries.

Actual scope matches this plan. The only review-driven contract corrections
were the measured Cockpit fixture read count, the OpenAPI `1.13.0-draft`
expectation in the existing Money Flow test, and the exact removal receipt for
the retired regime-reference diagnostic. No provider, dependency, auth,
deployment, service, artifact, commit, push, or pull action was added.

Verification passed: Social 4/4, Market Thesis summaries 5/5, Market Thesis
regression 7/7, API/OpenAPI 47/47, fixed client 12/12, backend boundary 18/18,
navigation 62/62, UX contract 19/19 with 166 exact diagnostics, deterministic
fixtures 26/26, deployment 18/18, Docker 11/11, Python 3.10 AST,
compileall/tabnanny, whitespace, frozen-artifact checks, and complete
`make test`.
