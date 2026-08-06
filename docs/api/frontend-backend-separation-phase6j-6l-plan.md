# Phase 6J-6L Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase6g-6i-plan.md`

## Objective

Move only two fixed public configuration reads behind the loopback read API:

1. **Phase 6J:** define strict, bounded contracts and endpoints for the public
   Watchlist theme taxonomy and Influencer roster projection.
2. **Phase 6K:** make `ui/watchlist_categorize.py` consume the taxonomy through
   one immutable API result per rerun. This is the fifty-first API-only slice.
3. **Phase 6L:** make the Influencer editor page and X Sentiment single-handle
   quick-pick consume the public roster projection through the API. These are
   the fifty-second and fifty-third API-only slices.

The watchlist itself, IBKR/reconciliation data, TradingView upload/save,
taxonomy classification provider calls, live social lookup, roster edits,
approvals, normalization, seeding, and every writer remain local/Internal.

## Entry evidence and boundary decisions

- `ui/watchlist_categorize.py` currently reads `content/themes.json` directly.
  It also owns private/live watchlist, reconciliation, classification, and save
  paths; only `_load_taxonomy()` is in scope.
- `ui/influencers.py::render()` currently reads the editable roster locally and
  then performs editor mutations. The page may use the API snapshot as its
  initial read, but all explicit save/category/edit operations stay local. An
  unavailable API must stop the mutation UI rather than fall back to a second
  local read or risk overwriting a newer roster.
- `ui/x_sentiment.py` uses the same roster only to populate a public handle
  quick-pick. Live provider calls, Codex analysis, credentials, and result
  storage remain unchanged.
- `content/themes.json` currently contains ten ordered public theme entries.
  `content/influencers.json` currently contains five public roster rows and
  four ordered categories. Root notes, source paths, environment settings, and
  any provider/auth details are not part of either public contract.
- Docker already gives API and Streamlit the same configured roster path and
  shared volume. The systemd API unit does not yet receive
  `SURGE_INFLUENCERS_PATH`; Phase 6J adds that read-only environment mapping so
  both processes resolve the same editable source. This changes configuration,
  not deployment topology or ownership.

## API design

### Theme taxonomy

- **Method/path:** `GET /api/v1/watchlists/theme-taxonomy`
- **Source ID:** `watchlists.theme-taxonomy`
- **Data:** ordered `themes`, maximum 100, each with unique bounded `name` and
  bounded `description`. The root `_note` and unknown fields are omitted.
- **Source bounds:** fixed configured/repository source only, no symlink,
  maximum 64 KiB, strict UTF-8/JSON/root shape, unique names, and no control
  characters.
- **Client bound:** maximum 128 KiB decoded body.

### Influencer roster

- **Method/path:** `GET /api/v1/social/influencers`
- **Source ID:** `social.influencers.roster`
- **Data:** ordered unique `categories` plus at most 1,000 source-ordered rows.
  Each row exposes only `handle`, `name`, `category`, `market`, `note`, `url`,
  `category_source`, `category_reason`, `category_confidence`, and
  `placeholder`. Handles are valid X handles and unique case-insensitively per
  market; market is `US | CRYPTO`; confidence is finite in `[0, 1]`; any URL is
  strict HTTPS on `x.com` or `twitter.com` and agrees with the handle. Missing
  row categories are appended deterministically to the public order.
- **Source bounds:** fixed path resolved without seeding or writing, no
  symlink, maximum 1 MiB, strict UTF-8/JSON/root shape, bounded strings and
  arrays, and no control characters.
- **Client bound:** maximum 2 MiB decoded body.

Both operations use the existing `available | unavailable` envelope, return
expected source failures as HTTP 200, set `Cache-Control: no-store`, and use
`asOf=null` / `generatedAt=null`. Missing is `missing`; filesystem/symlink
failure is `unreadable`; malformed UTF-8/JSON/schema or exceeded source bounds
is `invalid_shape`. Clients use the fixed loopback host, one-second
whole-request deadline, strict source/metadata/model validation, immutable
outcomes, immediate recovery, and no fallback or negative cache.

The operations are additive under `/api/v1` and ship in the same contract batch
as Phase 6G-6I, so static and generated OpenAPI advance only once from
`1.19.0-draft` to `1.20.0-draft`. Loopback peer/Host enforcement and no-CORS
remain unchanged; no new authentication or rate-limit mechanism is introduced.

## Phase execution

### Phase 6J — fail-first contracts, server, and deployment parity

1. Add fail-first model/source/route/OpenAPI tests for valid, empty, missing,
   unreadable, invalid UTF-8/JSON/shape, symlink, byte/item/string limits,
   duplicates, invalid handle/market/URL/confidence, privacy projection,
   metadata, no-store, and immediate recovery.
2. Add strict DTOs in `api/models.py` and bounded fixed readers/projections in
   `api/artifacts.py`. Resolve the roster path without `seed=True`; GET must
   never create, normalize, or write a file.
3. Add both fixed GET operations in `api/main.py` and the exact static OpenAPI
   operations/schemas/examples. Add injectable source paths to `create_app()`
   for deterministic tests without exposing request path parameters.
4. Add `SURGE_INFLUENCERS_PATH` to the API systemd unit and verify systemd,
   deploy-script, Docker, and process-path parity. Do not change the existing
   volume, writer ownership, or service topology.

### Phase 6K — taxonomy API-only presentation

1. Add frozen taxonomy outcomes and `load_theme_taxonomy()` to
   `ui/_read_api.py` with the full bounded failure vocabulary.
2. Replace the direct taxonomy file load with exactly one client call per page
   rerun. Available-empty is authoritative; unavailable/failure shows fixed
   safe guidance, leaves the independent sector view usable, and disables
   taxonomy-dependent classification without local fallback.
3. Remove the taxonomy path constant/import only after boundary and runtime
   tests prove no frontend file discovery remains. Keep uploads, watchlist
   state, reconciliation, classification providers, and saves unchanged.

### Phase 6L — roster API-only presentation

1. Add frozen roster outcomes and `load_influencer_roster()` to
   `ui/_read_api.py`, plus a pure UI conversion helper that omits absent
   optional values so a later explicit save does not rewrite the roster with
   synthetic null/default fields.
2. Replace `ui/influencers.py::render()` initial local load with exactly one API
   result. Available-empty remains editable as an intentional empty roster;
   unavailable/failure stops editor mutations and never calls `load_roster()`.
   Keep local loader/writer/normalizers for explicit internal mutation paths.
3. Replace the X Sentiment single-handle quick-pick local roster call with one
   API result and a pure market filter. On failure, keep manual handle entry
   usable with safe guidance; never fall back to the local roster.
4. Update deterministic fixtures and focused page tests to inject typed API
   outcomes and assert exact one-load behavior, recovery, no fallback, and no
   provider/writer drift.

## Affected files

- Contract/server: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`
- Client/consumers: `ui/_read_api.py`, `ui/watchlist_categorize.py`,
  `ui/influencers.py`, `ui/x_sentiment.py`
- Runtime parity: `deploy/surge-screener-api.service`
- Focused/global tests: new taxonomy/roster API-client-page suites,
  `scripts/test_api.py`, influencer-roster tests, X Sentiment API tests,
  backend-boundary/navigation/fixture/deploy/Docker contract suites, and UX
  contracts only where exact fixture injection changes
- Documentation/receipts: `Makefile`, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, `.agents/gateway.md`,
  `.agents/builder.md`, `.agents/artisan.md`, and the same single combined
  `.agents/PROJECT.md` row used for the Phase 6G-6L batch

No theme or influencer source JSON, watchlist file, classification/provider
logic, credential, prompt, local roster writer/normalizer, approval flow,
dependency, Compose file, schedule, or unrelated UI is planned to change.

## Verification gates

- Focused red-to-green model/source/route/OpenAPI/client/renderer/privacy tests
  for all three consumers and both resources.
- Existing influencer roster mutation, X Sentiment provider/Codex, watchlist
  categorization/reconciliation, backend-boundary, navigation, deterministic
  fixture, deployment, Docker, API/OpenAPI, and shared-client suites.
- Python 3.10 AST, compileall, tabnanny, YAML/static-version parity,
  `git diff --check`, source/writer hash preservation, and complete `make test`.
- Post-implementation diff-to-plan comparison and review for runtime defects,
  privacy leaks, filesystem fallback, accidental writes, missing tests, and
  unexplained scope drift before completion is claimed.

## Blocking-issue review

No unresolved blocking issue remains after two review iterations.

- **Iteration 1:** rejected moving private watchlist/IBKR/reconciliation data,
  live social lookups, provider credentials, arbitrary roster paths, or any
  writer behind these public GETs. Selected two fixed projections with strict
  field and resource bounds.
- **Iteration 2:** closed roster path parity, GET-time seeding/write,
  case-insensitive duplicate, URL/handle parity, category ordering, optional
  field rewrite, empty-state mutation, response cap, unavailable recovery, and
  Streamlit local-fallback gaps. Added the API systemd environment mapping and
  explicit writer/provider regression gates.

Final verdict: **GO** for Phase 6J-6L together with the amended Phase 6G-6I.

## Implementation closure

- Added strict bounded public taxonomy/roster projections and fixed endpoints;
  the roster path resolves without GET-time seeding and the API systemd unit
  now uses the same configured source as Streamlit.
- Watchlist taxonomy, Influencer initial roster, and X single-handle quick-pick
  each use one typed API read without local fallback. Independent sector,
  manual-handle, provider, approval, and explicit writer paths remain usable
  within their accepted local boundaries.
- Focused public-resource coverage passed 8/8; roster 30/30, X 7/7, API 47/47,
  shared client 12/12, boundary 23/23, navigation 66/66, UX 19/19, fixtures
  26/26, deploy 18/18, Docker 11/11, Python/static gates, and complete
  `make test` all passed. Static and generated OpenAPI examples are exact.
- Actual scope matches the plan, including the documented fixture-only
  `_THEMES_FILE` compatibility seam. Source JSON, writers, providers,
  credentials, dependencies, Compose topology, and schedules did not change.

## Following queue

Phase 6M-6O should perform a fresh residual-boundary audit after the first 53
API-only slices, classify any remaining frontend filesystem/provider reads,
and propose only the next fixed public read surfaces. Private mutations,
credentialed providers, arbitrary-detail/file endpoints, and deployment remain
out of scope unless a new reviewed plan explicitly accepts them.
