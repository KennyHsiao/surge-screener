# Phase 5I-5K Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5f-5h-plan.md`

## Objective

Move the shared persisted Sector Rotation board across one strict public
boundary in three independently reviewable steps:

1. **Phase 5I:** add a fixed, strict, summary-only Sector Rotation latest API
   contract over the dated archive.
2. **Phase 5J:** make only the standalone Sector Rotation quantitative board
   consume that fixed API result.
3. **Phase 5K:** make only Stock Checkup's sector-board lookup consume the same
   fixed result once per single-ticker render.

These phases do not make either composite page fully backend-owned. The local
`reports/sector_rotation.json` AI read, AI generation button/writer, theme
baskets, scored-candidate client, ticker-to-sector provider, live quote and
fundamental providers, Analytics DB export, session state, navigation, and all
mutations remain on their current boundaries.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

- **5I — GO, risk 5.5/10.** The persisted archive has a stable dated filename,
  exact provenance, 19 unique sector rows, and a small response surface. Resolve
  only the lexicographically latest `YYYY-MM-DD.json`, fail soft if that selected
  file is missing or invalid, and never fall back to an older file or invoke
  yfinance from the request. Validate the complete accepted source variant, but
  project only `as_of`, `benchmark`, and bounded presentation sector rows.
  Private `macro`, `leaders`, `improving`, status, AI `read`, and producer
  diagnostics remain server-side. Preserve source order and require unique ETF
  identities, closed quadrant/Chinese-label pairs, finite bounded metrics, and
  non-increasing heat order.
  The complete-source validator accepts only the exact archived
  `verified_only` root or the exact current `ready` root with its private
  bounded `read`; both variants project to the same closed public board.
- **5J — GO, risk 4.8/10.** The standalone page can issue one fixed board request
  per rerun and keep its already-migrated scored candidate state independent.
  An available board is authoritative. Unavailable or client failure shows
  fixed safe copy and never calls `_shared.load_sector_flow()` or the live
  `gather_sector_flow()` fallback. The separate AI analysis read and its
  generation mutation stay local and retain their current timing.
- **5K — GO, risk 5.3/10.** Stock Checkup currently asks the cached shared board
  from both its header and sector tab. Resolve one typed board state at the
  single-ticker entry and inject it into both consumers so no N+1 request is
  introduced. Keep `ticker_sector_etf()` as an independent cached provider.
  Board unavailable/failure omits the header sector chip and gives the sector
  panel fixed safe copy; it must not suppress factor, Cockpit, quote,
  fundamentals, analyst, or institutional content. Batch mode remains unchanged.

The deliberate behavior change is that a missing archive no longer triggers a
frontend live market-data fetch. The existing scheduled writer, shared deploy
archive, and server-side producer remain responsible for producing the snapshot.
This is required for a real process boundary and is covered by explicit
unavailable/failure tests.

## Public contract for Phase 5I

- Add parameter-free
  `GET /api/v1/market-context/sector-rotation/latest` with source ID
  `market-context.sector-rotation.latest`.
- Resolve only the fixed server archive root
  `reports/sector_rotation_snapshots`; clients control no path or filename.
- Return the standard no-store HTTP 200 available/unavailable envelope with
  `asOf` from the strict calendar date and `generatedAt` from the selected
  timezone-aware source timestamp.
- Public root fields: `as_of`, `benchmark`, `sectors`.
- Each sector row may contain only the fields rendered by the two consumers:
  `etf`, `name_zh`, `group`, nullable `theme`, `quadrant`, `quadrant_zh`,
  `rs_ratio`, `rs_momentum`, `heat_score`, `ret_5d`, `ret_20d`, `ret_60d`,
  `excess_20d`, `pct_vs_ma50`, `pct_vs_ma200`, `pct_from_52w_high`, and `rvol`.
- Use exact closed enums, finite numeric bounds, a conservative row maximum,
  unique normalized ETF symbols, exact quadrant-label mapping, and a small
  decoded response cap. Do not expose or synthesize tails that are absent from
  the persisted verified archive.

## Affected files and implementation order

### Phase 5I

- Add fail-first real-artifact, malformed-source, latest-selection, projection,
  route/OpenAPI, provenance, failure, recovery, and client-cap tests.
- Add strict DTOs and invariants in `api/models.py`.
- Add the fixed archive resolver, complete source validation, allowlist
  projector, and registry entry in `api/artifacts.py`.
- Add the route in `api/main.py`, static OpenAPI parity, and a fixed immutable
  result/client in `ui/_read_api.py`.

### Phase 5J

- Add focused standalone page tests for available, unavailable, every bounded
  client failure, exactly one request, preserved candidate partial states, and
  no local/live board fallback.
- Replace only `ui/sector_rotation.py`'s quantitative-board loader. Preserve
  the local AI read/generation, scored feed, theme drill, controls, jumps, and
  display ordering.

### Phase 5K

- Add focused Stock Checkup tests for one request shared by header/panel,
  available/unavailable/failure states, batch isolation, and preserved sibling
  provider calls.
- Inject the typed board state through the single-ticker render path in
  `ui/stock_checkup.py`. Remove `_shared.load_sector_flow()` only after repository
  search proves it has no remaining consumer.

For all three phases, synchronize backend-boundary, navigation, deterministic
fixture counters, UX successor receipts, Makefile, user guide, endpoint
inventory, implementation receipt, and skill journals only where measured.

## Verification gates

Run the new fail-first suite, Sector Rotation archive/producer regressions,
current scored-sector and Stock Checkup tests, API/OpenAPI parity, fixed-client,
backend-boundary, navigation, deterministic fixtures, deployment, Docker, UX,
Python 3.10 AST, compile/tabnanny, whitespace, and frozen-artifact checks.
Finish with complete `make test`. Compare the actual diff to this plan and fix
every blocking review finding before claiming completion.

## Frozen entry artifacts

- Sector Rotation verified archive:
  `3f187e31f3a57d13f5977f9c34e37d5d1d13d028d4b1969518199a1920a988ef`
- Separate AI rotation read:
  `596b107a16a6aeb01e477eb0630f0dc2f481c2d51411e002ff361ad6d1e7e6cf`

## Implementation receipt

- Phase 5I shipped draft API version `1.14.0-draft`, the fixed
  `GET /api/v1/market-context/sector-rotation/latest` route, strict source and
  public DTO validation, latest-dated resolver, OpenAPI parity, and a 512 KiB
  immutable fixed client.
- Phase 5J moved only the standalone quantitative board to that client. The
  local AI read/generator, scored-candidate mapping, theme drill, providers,
  controls, navigation, and mutations remain independent.
- Phase 5K resolves one typed board state per single-ticker Stock Checkup render
  and injects it into the header and sector panel. Batch mode, ticker-to-sector,
  retrospective, quote, fundamental, options, analyst, and institutional
  siblings remain unchanged. Repository search proved the retired shared board
  loader had no remaining production consumer before it was removed.
- Actual scope matches the accepted plan. Review caught and corrected one
  generic metadata regression by making source-derived metadata opt-in for this
  route only; existing routes retain their prior projected-data metadata
  behavior. No unexplained scope drift remains.
- Verification passed: focused Sector Rotation `5/5`, scored-sector `4/4`, API
  `47/47`, Money Flow `6/6`, backend boundary `19/19`, navigation `63/63`, UX
  contract `19/19`, deterministic fixtures `26/26`, Docker runtime `11/11`,
  compile/tabnanny, whitespace, frozen-artifact checks, and complete
  `make test` (exit 0).
- No pull, commit, push, deployment, service mutation, dependency change, or
  runtime artifact rewrite was performed by Phase 5I-5K.
