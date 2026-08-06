# Phase 4W-4Y Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-03
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4t-4v-plan.md`

## Objective

Execute three independently reversible Money Flow read-boundary slices without
calling either composite page fully separated:

1. Phase 4W adds a strict public projection for the fixed Money Flow snapshot
   and a bounded loopback client.
2. Phase 4X replaces only Schedules' candidate-refresh Money Flow summary read
   with that client.
3. Phase 4Y replaces only the standalone Options Cockpit external-confirmation
   Money Flow read with that client.

The Eastmoney provider/writer, ranked feed, other Schedules result fetchers,
live options chain, EDGAR action, quick-pick sources, mutations, Trade State,
and embedded `render_for()` remain on their existing boundaries. No pull,
commit, push, deployment, service action, authentication change, dependency
change, artifact rewrite, or unrelated UI work is authorized.

## Entry baseline and frozen bytes

The Phase 4T-4V receipt has no unresolved regression. Fresh entry suites pass
X/Social 7/7, Theme Flow 7/7, backend boundary 14/14, and navigation 58/58.
The prior full receipt records API/OpenAPI 47/47 and complete `make test` exit 0.

Exact pre-change target hashes are:

- `api/models.py`: `ea83a2c5b26b0ee1f3b346e120a0b05f8a9737b6ab6dddc810fe3fe7d7b164c9`
- `api/artifacts.py`: `b291a3661a776adc338fc64055e7f8fc698e6a7496467b4c5cafba32ba3c9f79`
- `api/main.py`: `3b19f1bf9618fe738ada2fa7468d6c8179970e537e9fd7d92b7e94ada223796d`
- `ui/_read_api.py`: `a455348656a229e9acac99a0df49bb02a49693729e648e223f0e73d5f7d19b08`
- `ui/sys_schedules.py`: `63abb1941999d1e41bb2c85eb5861f562189943a93949bd8b529deab4e47fda1`
- `ui/options_cockpit.py`: `e7aa18d38cb648d1701daae46f9b52f595790da679197edc12aa07e95e208c4d`
- static OpenAPI: `679fd2b2346adcd9b5dc03afa8f14f7a651303b039439fec3eb55d09dacb2f21`
- `scripts/test_api.py`: `a828f8192e2f80c0f391c6601b0538e4de747c746b170135d7404825e2f5ba46`
- Schedules focused suite: `25149c0d921d142f95defcd32ce2e0857c947ad37c1543851f7c79a00370a481`
- Options display suite: `c1da9675fa86c41f401bc6e7c77d99adceb68433dbc8fa1af0455d5aa29eb970`
- backend boundary: `1e0c35b61c562af5769654845dc19687f0110b111e72a9524ee141aa8819ebbf`
- navigation: `01ba9e4834440539237db607415835d7ac2bcd58f2182ce67497f78b3e37cd43`
- `Makefile`: `23a764fc0b18e103d6197e898a3196f9ee0f8f85896d78dff70ef0afaea7768a`

The Money Flow artifact remains frozen at
`96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`.
Re-hash a shared target immediately before its first edit; changed bytes require
re-review rather than overwrite.

## Source and impact trace

`scripts/eastmoney_money_flow.py::build_money_flow_snapshot()` is the sole
producer. It writes the exact root keys `as_of_date`, `generated_at`, `source`,
`publishable`, `coverage`, and `rows`; exact coverage keys `requested`,
`resolved`, `unavailable`, `coverage_ratio`, and `min_coverage`; and exact row
keys `ticker`, `secid`, `date`, `close`, `change_pct`, `main_net`, `main_pct`,
`super_big_net`, `big_net`, `mid_net`, `small_net`, `source`, and `raw_row`.

The selected presentation consumers are:

- `ui/sys_schedules.py::_latest_candidate_refresh_result()`, which needs the
  root date, publishable state, and coverage ratio beside an independent ranked
  result;
- `ui/options_cockpit.py::_render_external_confirmation()`, whose existing
  signal needs the root date/source/publishable state and row ticker/date,
  `main_net`, `main_pct`, `small_net`, and source.

`scripts/trade_state.py` is an unselected backend aggregate consumer. Analytics,
ranking, Theme Flow, writers, provider adapters, deployment persistence, and
the current artifact are also unselected. The public row projection therefore
omits `secid`, `raw_row`, close/change diagnostics, and the unused detailed flow
breakdown.

## Blocking-issue review

No unresolved blocker remains after one review iteration.

- **4W — GO, risk 5.9/10:** the producer has a stable exact shape and the
  selected consumers need a closed subset. The server must validate root,
  coverage arithmetic, publishability, unique/resolved tickers, dates,
  timestamps, finite numbers, and source identity before projection. The
  response and client are bounded; expected source failures stay HTTP 200
  unavailable.
- **4X — GO, risk 4.2/10:** the current candidate result already snapshots one
  ranked read across duplicate visible cards. Loading Money Flow in the same
  function preserves that one-result reuse. Ranked and Money Flow outcomes must
  remain independently visible, and neither may fall back to local selected
  bytes.
- **4Y — GO after clarification, risk 5.1/10:**
  `_render_external_confirmation()` is shared by standalone `render()` and
  embedded `render_for()`. The accepted scope says standalone only, so
  `render()` will load and inject one typed API state while `render_for()` keeps
  the existing default local behavior. This resolves the shared-call-site
  ambiguity without silently expanding the Stock Checkup embedded path.
  Standalone unavailable and client failure use distinct fixed copy and never
  call the local loader.

No breaking route, data-loss path, credential exposure, provider migration, or
new mutation is part of the accepted scope. Overall weighted risk is 5.1/10.

## Contract-first design

Phase 4W adds parameter-free
`GET /api/v1/market-context/money-flow/latest`, operation
`getLatestMoneyFlow`, source ID `market-context.money-flow.latest`, using the
existing loopback-only, no-store, discriminated fail-soft envelope. Expected
artifact failures remain HTTP 200 unavailable; unexpected defects remain
sanitized RFC 9457 HTTP 500 responses. The API draft becomes
`1.12.0-draft`.

The strict public data contains:

- exact source provenance: real calendar `as_of_date`, timezone-aware bounded
  `generated_at`, source literal `eastmoney_push2his`, and `publishable`;
- closed coverage counts and ratios with `requested = resolved + unavailable`,
  ratio/count consistency, and publishable exactly matching the producer gate;
- at most 50,000 rows containing only ticker, real date, nullable finite
  `main_net`, `main_pct`, `small_net`, and source;
- unique `(ticker, date)` rows and a unique ticker count equal to `resolved`.

Metadata date/time must match the projected root exactly. The fixed client uses
one URL, no redirects, JSON/no-store checks, the existing one-second deadline,
an 8 MiB decoded-body cap, strict envelope/model validation, and immutable
available/unavailable/failure outcomes. It has no local fallback.

## UI state behavior

### Phase 4X — Schedules

`_latest_candidate_refresh_result()` makes one ranked request and one Money Flow
request. Its result is still cached once by `render()` and reused for duplicate
visible `candidate_refresh` cards.

- both available: preserve date, ranked count/top-five, publishability, and
  coverage rendering;
- Money Flow available-empty: render the authoritative not-publishable/zero-row
  summary without inventing a missing artifact;
- ranked unavailable/failure: preserve valid Money Flow output and the ranked
  state banner;
- Money Flow unavailable/failure: preserve valid ranked output and show fixed
  Money Flow unavailable/service copy;
- neither source usable: keep the safe result state and expose no raw reason.

The local `reports/money_flow/latest.json` read is removed only from this result
function. No other Schedules result fetcher moves.

### Phase 4Y — standalone Options Cockpit

Standalone `render()` loads one typed Money Flow state and injects it into the
external-confirmation panel.

- available data reuses the existing future-row rejection, latest-row choice,
  three-day staleness rule, and positive/negative/neutral signal formatting;
- available-empty keeps the existing publishability/data-gap semantics;
- authoritative unavailable and client failure render distinct fixed safe
  signals without raw diagnostics;
- no standalone state calls `_load_money_flow_artifact()` as fallback;
- EDGAR loading, live chain, chart, quick picks, navigation, session writes,
  mutations, and all other panels remain unchanged.

`render_for()` retains its current external-confirmation behavior and local
reader for this phase; that retained boundary is explicit debt, not a fallback
from the standalone API request.

## Execution steps

1. Add fail-first contract/client tests plus focused Schedules and standalone
   Options Cockpit tests for projection privacy, caps, metadata, fail-soft
   recovery, one-request reuse, partial states, no local fallback, future rows,
   and stale rows.
2. Phase 4W: add strict DTOs, exact validator/projector, fixed registry spec,
   route/envelope, client outcomes, and OpenAPI 1.12 contract.
3. Phase 4X: replace the selected Schedules local read and preserve cached
   duplicate-card and independent partial-state behavior.
4. Phase 4Y: add a typed standalone state injection while leaving the embedded
   default path and every sibling operation intact.
5. Update route/registry/version expectations, exact backend boundary and
   navigation/source guards, Make test inventory, endpoint inventory, user
   guide, and required skill/project receipts.
6. Compare the actual diff to this plan, review for bugs/regressions/missing
   tests, fix all blocking findings, and run focused plus complete verification.
7. Audit the remaining direct reads and record the concrete successor queue in
   the implementation receipt; completion reporting must include that next plan.

## Allowed implementation surfaces

- UI/client: `ui/_read_api.py`, `ui/sys_schedules.py`,
  `ui/options_cockpit.py`
- API/contract: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`, `scripts/test_api.py`
- Focused suites: `scripts/test_ui_schedules_candidate_api.py`,
  `scripts/test_options_cockpit_display.py`, and one new strict Money Flow API
  client suite if separation keeps the tests clearer
- Exact contracts: `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `scripts/test_ui_ux_fixtures.py`,
  `Makefile`
- Documentation/receipts: this plan, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, and the required
  Lens/Ripple/Gateway/Builder/Artisan/project journals

Any provider, writer, Trade State, analytics/ranking pipeline, deployment,
dependency, credential, embedded-path migration, unrelated page,
compatibility-route shape, or existing endpoint change is unexplained scope
drift and stops execution.

## Verification and rollback

Run new tests red-first and green after each phase, then API/OpenAPI, fixed read
client, Schedules candidate, Options Cockpit display/scored feed, backend
boundary, navigation, deterministic UI fixtures, producer tests, deployment,
Docker, compileall, tabnanny, Python 3.10 AST, YAML/reference parity,
whitespace, frozen-artifact integrity, and complete `make test` gates. Report
any check that cannot run.

Each phase rolls back through only its named UI/client/API/test/doc hunks. The
producer, current artifact, embedded path, compatibility routes, and mutations
remain intact, so rollback requires no data migration or artifact rewrite.

## Subsequent queue to review after 4Y

The post-4Y direct-read audit found one retained Money Flow presentation path
and two narrow Options Flow consumers that can reuse already strict public
contracts. They remain separate review units; this receipt does not authorize
their implementation.

1. **Phase 4Z — embedded Options Cockpit Money Flow:** inject the existing
   typed Money Flow API state into `render_for()` and then remove the final
   local `_load_money_flow_artifact()` presentation reader. Preserve Stock
   Checkup's lazy tab, one request per rendered embedded cockpit, EDGAR, live
   chain, and every sibling action.
2. **Phase 5A — Schedules Options Flow summary:** replace only
   `_latest_options_flow_result()`'s local latest-file read with the existing
   strict Options Flow feed, cache one result across duplicate visible cards,
   and preserve all other schedule result readers.
3. **Phase 5B — standalone Options Cockpit Options Flow quick picks:** replace
   only the local persisted Options Flow quick-pick source with one existing
   strict feed request, preserving watchlist/social/scored quick picks, live
   chain, embedded mode, and mutations.

Trade State remains deferred because its aggregate joins several private and
public sources and needs a separate privacy, ownership, and mutation review.

## Implementation and verification receipt

Phase 4W-4Y matches the accepted production scope. The API draft is now
`1.12.0-draft` with a closed Money Flow projection and fixed bounded client.
Schedules reads ranked candidates and Money Flow independently through strict
API clients, reusing one result for duplicate candidate-refresh cards.
Standalone Options Cockpit injects one typed Money Flow state into the existing
external-confirmation presentation; embedded `render_for()` intentionally keeps
the accepted local boundary for this phase.

Red-first focused suites failed on the absent `MoneyFlowData` contract, then
passed after implementation. Actual-diff review found and fixed one blocking
verification regression: the deterministic route matrix still required the old
`options.money_flow.execute` local counter after the standalone path moved. It
now requires `options.money_flow_api.execute`. The corresponding fixture-helper
edit in `scripts/ui_ux_fixtures.py` is an explained verification-harness
addition beyond the initially enumerated paths; it supplies a fixed typed API
result and does not change production behavior. No other scope drift remains.

Final gates pass: Money Flow 6/6, Schedules candidate 5/5, Options display
19/19, Options scored 4/4, API/OpenAPI 47/47 with real Uvicorn, fixed read client
12/12, backend boundary 15/15, navigation 59/59, deterministic fixtures 26/26,
Money Flow producer 8/8, deployment 18/18, Docker 11/11, and complete
`make test` with exit 0. Compileall, tabnanny, Python 3.10 AST, YAML parse and
reference parity, whitespace, and real-artifact validation also pass. The
ranked, scored, and Money Flow artifacts remain exactly:

- `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea`
- `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99`
- `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`

The current Money Flow snapshot is an authoritative available-empty state:
0 of 219 requested tickers resolved, so it is correctly non-publishable. No
pull, commit, push, deploy, service action, authentication, dependency, provider,
writer, or artifact rewrite was performed.
