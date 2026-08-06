# Phase 5O-5Q Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5l-5n-plan.md`

## Objective

Continue with three narrow, independently reversible trust-card and validation
slices:

1. **Phase 5O:** make only Today Decision's Oversold trust card reuse the strict
   Oversold Reversal validation client added in Phase 5M.
2. **Phase 5P:** add a fixed, strict, summary-only Reversal Radar forward-
   validation API over the existing persisted validation artifact.
3. **Phase 5Q:** make only Today Decision's Reversal trust card consume that new
   fixed API result.

Phase 5O is the thirty-eighth API-only slice. Phase 5P establishes a contract
but does not itself count as a UI slice; Phase 5Q is the thirty-ninth. Completing
these phases removes the final local `validation_summary.json` reads from Today
Decision's trust cards, but does not make the composite page, Radar, or either
signal producer fully backend-owned.

## Entry evidence and boundaries

- After Phase 5L, Today Decision's Market Thesis trust card uses its strict API
  client. Its generic local validation helper now has exactly two selected
  consumers: Reversal and Oversold.
- Phase 5M already provides a strict Oversold validation projection and a 32 KiB
  fixed client. Phase 5O can reuse it without changing the API surface.
- The current Reversal validation artifact is 106,780 bytes with SHA-256
  `1f673068e637b6947336b81f41e0f7399c63493c7572623082dd0e57b8edcd45`.
  Its only writer is `scripts/reversal_radar_forward.py`; the artifact has exact
  root fields, exact tier order `+10%/20d`, `+15%/40d`, `+20%/60d`, and large
  private equity curves and EV analytics.
- Reversal imports a shared mean-statistics helper but has its own legacy
  publication semantics: strategy fields and curves are based on resolved-row
  availability rather than Oversold's newer per-tier maturity gates. The new
  source validator must follow the Reversal producer exactly; it must not copy
  Oversold-only `mature`, beta-adjusted, net-cost, cohort, or publication rules.
- Today Decision's separate local Reversal/Oversold `latest.json` cards in
  `_render_risk_and_research`, local Options Flow read, reconciliation/ledger,
  controls, Trade State, and all providers/writers remain outside this plan.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

### Phase 5O

- Proposed disposition: **GO, risk 3.8/10**.
- Call `load_oversold_reversal_validation()` exactly once inside the trust-
  boundary render and derive only the Oversold card maturity/detail from the
  typed available result.
- Treat valid unavailable and every bounded client failure as authoritative:
  show fixed safe partial-state copy, do not expose raw reasons, and never
  reread the Oversold validation artifact locally.
- Narrow the remaining helper usage to Reversal only. Preserve the Market
  Thesis client call, every other Today Decision source, render order, controls,
  providers, navigation, and writers.

### Phase 5P

- Proposed disposition: **GO, risk 5.7/10**.
- Advance the additive draft API/OpenAPI version from `1.15.0-draft` to
  `1.16.0-draft` and add only parameter-free
  `GET /api/v1/signals/reversal-radar/validation` with source ID
  `signals.reversal-radar.validation`.
- Validate the complete exact Reversal producer root, exact three tier keys,
  timezone-aware timestamp, lane/module identity, count arithmetic, exact
  verdict and per-tier verdict derivation, Wilson bounds, nullable finite
  statistics, equity-curve cardinality/order, and survivorship/caveat shapes.
  Accept zero/provisional/mature sources exactly as the Reversal writer can
  produce; do not impose the distinct Oversold maturity-publication rules.
- Project only `entries_accumulated`, `min_resolved_across_tiers`,
  `min_resolved_for_verdict`, `verdict`, and ordered `by_tier` rows containing
  `resolved`, `hits`, nullable `hit_rate`, and two-value `wilson90`. Put the
  timezone-aware source timestamp only in envelope `generatedAt`.
- Keep `price_resolvable`, dropped metrics, `verdict_by_tier`, lane/module,
  survivorship, caveats, notes, all EV/excess statistics, and every equity-curve
  point private.
- Use the standard no-store HTTP 200 available/unavailable envelope and an exact
  32 KiB decoded client response cap. Missing, unreadable, malformed, or
  shape-invalid sources fail soft. No route/client path invokes a scan, forward
  harness, market-data provider, or writer.

### Phase 5Q

- Proposed disposition: **GO, risk 4.0/10**.
- Call the new Reversal validation client exactly once in Today Decision's
  trust-boundary render and derive only the Reversal card from its typed state.
- Available-empty, unavailable, and every bounded client failure render stable
  safe copy without local fallback or raw reason leakage.
- Remove the now-unused generic local validation helper only after repository
  search proves it has zero consumers. Do not remove `_REVERSAL_DIR` or
  `_OVERSOLD_DIR`: the explicitly retained local latest-snapshot cards still use
  them.
- Preserve the Phase 5L Market Thesis call, Phase 5O Oversold call, exact one-
  request-per-card behavior, all other Today Decision reads, and the complete
  Reversal/Oversold standalone and embedded pages.

## Affected files and implementation order

### Phase 5O

- Add fail-first Today Decision tests for available, available-empty,
  unavailable, every bounded failure, exactly one request, no Oversold local
  fallback, and unchanged Market Thesis/Reversal cards.
- Change only the Oversold trust-card state in `ui/today_decision.py` and
  synchronize measured boundary/navigation/fixture expectations.

### Phase 5P

- Add fail-first real-artifact, zero/provisional/mature-source, malformed-source,
  closed-projection, invariant, route/OpenAPI, provenance, cap, failure, and
  recovery tests.
- Add separate strict Reversal DTOs in `api/models.py`; source validator,
  projector, and registry entry in `api/artifacts.py`; route/envelope in
  `api/main.py`; static OpenAPI parity in
  `docs/api/quant-radar-v1.openapi.yaml`; and an immutable fixed client in
  `ui/_read_api.py`.

### Phase 5Q

- Extend focused Today Decision tests for the new typed states, exact request
  counts for all three trust cards, zero selected local validation reads, and
  preservation of the separate local latest-snapshot cards.
- Replace only the Reversal trust-card validation read and remove the helper if
  zero-consumer proof succeeds.

For all phases, update Makefile coverage only if a new test command is needed,
backend-boundary and navigation contracts, deterministic fixture counters, an
exact UX successor receipt only if the measured diagnostic inventory changes,
the user guide, endpoint inventory, implementation receipt, and relevant skill
journals.

## Verification gates

Run fail-first focused suites, current Market Thesis and Reversal/Oversold
regressions, API/OpenAPI parity, fixed-client tests, backend-boundary,
navigation, deterministic fixtures, UX contract, deploy and Docker contracts,
Python 3.10 AST, compile/tabnanny, whitespace, source-hash, and no-local-fallback
searches. Exercise the real Reversal artifact plus synthetic zero, provisional,
and mature variants. Finish with complete `make test`, compare the actual diff
to this plan, and fix every blocking review finding before completion.

## Frozen entry artifacts

- Oversold Reversal validation summary:
  `d072d4a9e973a7a6f8fe4ac2c776159016fba9e995af2a8158611ffdfe62b1d9`
- Reversal Radar validation summary:
  `1f673068e637b6947336b81f41e0f7399c63493c7572623082dd0e57b8edcd45`

This planning receipt does not authorize Phase 5O-5Q implementation without a
separate user instruction.

## Review record

- **Iteration 1:** confirmed the two remaining Today Decision local validation
  consumers, the existing Oversold client seam, the proposed fixed path/source
  ID/version/cap, the exact retained local latest reads, and the full affected
  file and verification surface. No scope or runtime blocker found.
- **Iteration 2:** verified both frozen hashes, the Reversal writer and exact
  current root/tier shapes, the crucial Reversal-versus-Oversold publication-
  semantics difference, conservative public projection, exact request counts,
  failure behavior, and zero-consumer helper-removal gate. Final verdict:
  **GO** for a separate Phase 5O-5Q implementation instruction.
- **Iteration 3:** rechecked the shared worktree, current producer output, all
  selected and retained consumers, response caps, request counts, UX inventory,
  and Reversal's large finite equity values. Confirmed that the Reversal source
  validator must not inherit Oversold's maturity-publication gates or 1e9 curve
  bound. No unresolved blocker remained; final implementation verdict: **GO**.

## Implementation receipt

- **Phase 5O:** Today Decision's Oversold trust card now resolves exactly one
  strict Oversold validation-client result. Valid unavailable and every bounded
  client failure render fixed safe partial-state copy without local fallback or
  raw reason leakage.
- **Phase 5P:** draft API/OpenAPI `1.16.0-draft` adds fixed no-store
  `GET /api/v1/signals/reversal-radar/validation`, source ID
  `signals.reversal-radar.validation`, separate strict DTOs, complete exact
  producer-source validation, a closed headline/tier projection, immutable
  client outcomes, and a 32 KiB decoded response cap. Private EV/excess,
  equity-curve, survivorship, caveat, note, lane, and drop data stay server-side.
- **Phase 5Q:** Today Decision's Reversal trust card now resolves exactly one
  strict Reversal validation-client result. The generic local validation helper
  and every Today `validation_summary.json` read were removed after zero-consumer
  proof; the separate local Reversal/Oversold latest cards remain intact.
- **Measured inventory:** thirty-nine API-only slices. The UX diagnostic
  inventory stayed byte-identical at 165 sites, including the same two Today
  Decision site IDs, so no successor receipt was required.
- **Review fixes:** tightened zero-resolved and zero-excess Reversal intervals to
  the producer's exact `[null, null]` shape, while preserving valid large finite
  equity values above `4.7e23`; synchronized the two stale Money Flow/Sector
  Rotation global draft-version expectations to `1.16.0-draft`.
- **Verification:** candidate feeds 9/9, Reversal/Oversold 9/9, API/OpenAPI
  47/47, shared client 12/12, boundary 19/19, navigation 63/63, UX contract
  19/19 with 165 exact diagnostics, fixtures 26/26, deploy 18/18, Docker 11/11,
  Money Flow 6/6, Sector Rotation 5/5, Python 3.10 AST, compile/tabnanny, YAML,
  whitespace, frozen-artifact gates, and complete `make test` all pass.
- **Artifact integrity:** both frozen entry artifacts remain byte-identical at
  107,337 and 106,780 bytes. The audited successor is
  `docs/api/frontend-backend-separation-phase5r-5t-plan.md`.
