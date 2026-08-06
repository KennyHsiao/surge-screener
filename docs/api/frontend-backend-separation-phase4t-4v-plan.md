# Phase 4T-4V Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-03
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4q-4s-plan.md`

## Objective

Execute three independently reversible read-boundary slices without calling the
two composite pages fully separated:

1. Phase 4T replaces X Sentiment's direct `ranked_candidates.json` refresh seed
   with the existing strict ranked feed.
2. Phase 4U adds a strict Social Intelligence latest projection and moves only
   persisted social-snapshot presentation to it.
3. Phase 4V adds strict Theme Flow snapshot and analysis projections and moves
   only those two persisted presentation reads to them.

X/Agent Reach/Codex/provider refresh, roster reads, legacy X-picks compatibility,
AI-summary persistence, Theme Flow refresh/status/AI mutations, insider data,
sector mapping, and all writers remain on their existing local/Internal
boundaries. No pull, commit, push, deployment, service action, authentication
change, dependency change, or unrelated UI work is authorized.

## Entry baseline and frozen bytes

The Phase 4Q-4S receipt has no blocking regression. Entry suites pass candidate
feeds 8/8, Phase 4Q 4/4, Phase 4R 4/4, Phase 4S 5/5, backend boundary 14/14, and
navigation 57/57. The sandboxed real-Uvicorn check reaches the expected local
port-bind denial; the prior authorized API run passed 47/47.

Exact pre-change target hashes are:

- `ui/x_sentiment.py`: `fd5c4dea3bc7ccbbfbc320df2939980339edc9b5d9d2841575057940e20a7ec0`
- `ui/theme_flow.py`: `c749e2cd60b184aafccee5f0791874ea8c5b5978b772b2992aad5fc34dc7ca7b`
- `ui/_read_api.py`: `1d9dd323daab0438ec3aa5cc09265e4edbea3285a1c6d67837f6faba8f89b39e`
- `api/models.py`: `85ba08154a9ffc74a350a429df012bb07431da06e4d26b9b67f4bf17e0f565be`
- `api/artifacts.py`: `d3a92e71abe74a2025765ec5be8846e8bd259626545b2c6f85f11fa00734d60f`
- `api/main.py`: `0bcdfa126acbd52c19c654b1850ef55c1327a75c0a728f6d9100161dcfdff3aa`
- static OpenAPI: `1983c6cf2c2728ad5c7cbbad42841c2dd1a1545c7fa725a156602f26e24bd16f`
- `scripts/test_api.py`: `c8a8c116b5d5e8ef6dae1f2396cbe67453b72bedfe3305ad2ec4f0ba355b0d5c`
- backend boundary: `6f9809fdf8f26c3334a66b04f363a942321c8160d3b107604891ba006d578fa0`
- navigation: `0069901b14e61622568080d06af52f2095596f0b4e2e6e0592e45cb1ad3affa3`
- `Makefile`: `4db459383f361bf6259b794f5fcd9312836c8d9987976c396fd05048fe81e9ae`

Ranked, scored, and Money Flow artifacts remain frozen at
`ca85c803...b5ea`, `6af37543...57b99`, and `96ed8334...61731`. Re-hash every
production target immediately before its first edit; changed bytes require
re-review instead of overwrite.

## Blocking-issue review

No unresolved blocker remains.

- **4T — GO, risk 3.8/10:** the existing ranked feed already carries every
  field consumed by `social_intelligence._platform_validation`. Available-empty,
  unavailable, and client failure all remain valid partial refreshes; none may
  fall back to local ranked bytes.
- **4U — GO, risk 5.8/10:** the latest social artifact is currently absent, so
  the new endpoint must prove missing-file fail-soft behavior with synthetic
  contract fixtures. The public projection includes only fields used by radar
  rendering and the existing AI-summary digest/prompt. The separately persisted
  legacy X-picks compatibility read remains local P2 and must not become a
  social-latest fallback.
- **4V — GO, risk 6.6/10:** the checked Theme Flow snapshot is current schema v5,
  while the checked analysis is old validation v7 and belongs to an older board.
  The snapshot remains renderable; the analysis must fail closed until the
  existing local AI action writes current validation v8 for the exact board.
  Cross-endpoint coherence is enforced by a server-computed board fingerprint
  in the snapshot projection and a client comparison against the analysis
  fingerprint.

No breaking route, data-loss path, credential exposure, provider migration, or
new mutation is part of the accepted scope. Overall weighted risk is 5.6/10:
the API is additive and rollback is file-local, but Theme Flow has a wide
presentation DTO and two-request coherence boundary.

## Contract-first design

All three new operations are parameter-free additive v1 GETs using the existing
loopback-only, no-store, discriminated fail-soft envelope. Expected artifact
failures remain HTTP 200 unavailable; unexpected defects remain sanitized RFC
9457 HTTP 500 responses. The draft version becomes `1.11.0-draft`.

### Social Intelligence latest

`GET /api/v1/social/intelligence/latest`, operation
`getLatestSocialIntelligence`, source ID `social.intelligence.latest`:

- fixed source `reports/social_intelligence/latest.json`;
- exact producer root/schema identity is validated, but public data contains
  only `as_of_date`, `generated_at`, `market`, bounded Agent Reach status, and
  at most 200 ticker rows;
- each row exposes only normalized ticker, bounded mentioned-by/citations,
  skew/conviction/note, six closed label booleans, and the platform-validation
  subset required by the existing local AI-summary prompt;
- discovery internals, cost modes, heat-provider payloads, other source statuses,
  limitations, and private source fields are omitted;
- metadata date/time must exactly match the projected date/time.

The page issues one request only when no same-rerun refresh result is already in
memory, renders only a snapshot matching the selected US/CRYPTO market, and
uses fixed sanitized unavailable/failure copy. No local read of the selected
social latest path is allowed.

### Theme Flow snapshot

`GET /api/v1/market-context/theme-flow/latest`, operation
`getLatestThemeFlow`, source ID `market-context.theme-flow.latest`:

- fixed source `reports/theme_flow_snapshot.json`, exact current schema v5;
- public root contains `as_of`, `generated_at`, benchmark, failure count, four
  capital-state buckets, shared mega-cap counts, at most 100 projected themes,
  and a server-computed 16-hex board fingerprint;
- each theme contains only fields used by the existing bubble, leaderboard,
  bottom-fishing, focus, and detail views; representative stocks are bounded;
- cache parameters, duplicate bottom-fishing root data, Eastmoney fields,
  money-flow diagnostics, and unused computation fields are omitted;
- metadata date/time exactly matches the projection.

The page uses one snapshot request, never reads a local snapshot/cache fallback,
and retains local refresh/status control. Missing or stale data may still launch
the existing background refresh, but the UI only presents the next result after
it becomes available through the API.

### Theme Flow analysis

`GET /api/v1/market-context/theme-flow/analysis`, operation
`getThemeFlowAnalysis`, source ID `market-context.theme-flow.analysis`:

- fixed source `reports/theme_flow.json`;
- only ready reports produced under current validation v8 are accepted;
- public data contains `status`, `as_of`, `generated_at`, board fingerprint,
  and the closed rendered read: headline, confidence, four bounded theme-item
  lists, next thesis, and caveats;
- prompt inputs, macro/bucket copies, and validation internals are omitted;
- metadata date/time exactly matches the projection.

The page requests analysis once in the AI-read panel, renders it only when its
fingerprint equals the already-rendered snapshot fingerprint, and otherwise
shows fixed stale/unavailable/service copy. Existing status and AI-generation
actions remain local/Internal.

## Execution steps

1. Add fail-first focused Social/X and Theme Flow suites covering strict
   projections, metadata, missing/invalid artifacts, bounded clients, one-request
   behavior, market selection, empty/unavailable/failure states, no selected-path
   local fallback, refresh preservation, and fingerprint mismatch rejection.
2. Phase 4T: convert the existing ranked feed into the producer's expected
   in-memory seed and remove only the direct local ranked read from the UI refresh
   function.
3. Phase 4U: add the Social DTO/projector/spec/route/client and adopt it in the
   persisted radar read while preserving in-memory refresh output and legacy
   X-picks as an independent compatibility sibling.
4. Phase 4V: add Theme snapshot/analysis DTOs/projectors/specs/routes/clients,
   adopt both reads, and remove only the old local snapshot/read imports.
5. Update static OpenAPI, route/registry/version expectations, exact backend
   import inventory, navigation/source guards, Make test inventory, endpoint
   inventory, user guide, and skill/project receipts.
6. Compare actual diff to this plan, review for bugs/regressions/missing tests,
   fix all blocking findings, and run focused plus complete verification.

## Allowed implementation surfaces

- UI/client: `ui/x_sentiment.py`, `ui/theme_flow.py`, `ui/_read_api.py`
- API/contract: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`, `scripts/test_api.py`
- New focused suites: `scripts/test_ui_x_sentiment_api.py`,
  `scripts/test_ui_theme_flow_api.py`
- Exact contracts: `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `Makefile`
- Documentation/receipts: this plan, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, required
  Lens/Ripple/Gateway/Builder/Artisan/project journals

Any provider, writer, roster, refresh implementation, deployment, dependency,
credential, unrelated page, compatibility-route shape, or existing endpoint
change is unexplained scope drift and stops execution.

## Verification and rollback

Run new tests red-first and green after each phase, then ranked/candidate, API /
OpenAPI, backend boundary, navigation, social producer/summary, Theme Flow /
background/UI-label, UX fixture/contract, deployment, Docker, compileall,
tabnanny, Python 3.10 AST, YAML, shell, whitespace, frozen-artifact integrity,
and complete `make test` gates. The real-Uvicorn check may need its already
authorized local-socket execution; report any check that cannot run.

Each phase rolls back through only its named UI/client/API/test/doc hunks. The
three existing compatibility routes and every local mutation path remain intact,
so rollback requires no artifact migration or data rewrite.

## Subsequent queue to review after 4V

The post-4V audit selected Money Flow as the next bounded shared artifact. Its
fixed root has exact producer provenance and a small public subset, while its
`secid`, `raw_row`, and unused flow-breakdown fields can stay private.

1. **Phase 4W — strict Money Flow contract:** add a closed projection, fixed
   `GET /api/v1/market-context/money-flow/latest`, bounded client, OpenAPI, and
   fail-soft real/fixture tests. Public rows should contain only the fields used
   by approved presentation consumers; the Eastmoney writer/provider stays
   local and the current frozen artifact is not rewritten.
2. **Phase 4X — Schedules Money Flow summary:** replace only
   `_latest_candidate_refresh_result()`'s local Money Flow read, preserving its
   independent ranked-feed request and partial-state behavior. One Money Flow
   request may be reused across duplicate visible schedule cards; no other
   result fetcher moves.
3. **Phase 4Y — Options Cockpit external confirmation:** replace only
   `_load_money_flow_artifact()` in the standalone external-confirmation panel,
   preserving the live options chain, EDGAR action, watchlist/social/options
   quick picks, embedded `render_for()`, and every mutation. Available-empty,
   unavailable, client failure, future rows, and stale ticker rows need explicit
   tests with no local Money Flow fallback.

Trade State remains outside 4W-4Y because its backend aggregate combines
ranked, social, Options Flow, Risk Guard, Money Flow, taxonomy, and review state;
moving that composite builder needs a separate impact and privacy review.

## Implementation and verification receipt

Phase 4T-4V matches the accepted source-level scope. X refresh validation now
uses the strict ranked feed and persisted Social presentation uses one fixed
Social client. Theme Flow board and analysis presentation use two fixed clients
joined by the server-computed board fingerprint. X/Agent Reach/Codex/provider
work, legacy X-picks, Theme refresh/status/AI/insider/sector behavior, and every
writer remain local/Internal.

Actual-diff review found and fixed four blocking regressions before completion:

- a Theme API client failure could auto-launch an expensive background refresh;
  only authoritative artifact-unavailable now auto-launches;
- Social `last_price` accepted negative values; it now matches the ranked-feed
  positive-price-or-null contract;
- the condensed user guide dropped existing route/port migration assertions;
  the prior guidance and ordinal receipts were restored;
- the deterministic UX fixture still patched the deleted local Theme analysis
  loader; it now patches the typed Theme state boundaries. This required the
  explained verification-only edit to `scripts/ui_ux_fixtures.py` beyond the
  initially enumerated files and did not change production behavior.

Final gates pass: X/Social 7/7, Theme Flow 7/7, candidate feeds 8/8, API/OpenAPI
47/47 with real Uvicorn, fixed read client 12/12, boundary 14/14, navigation
58/58, Social producer/summary 15/15 + 2/2, Theme producer/background/labels
26/26 + 7/7 + 3/3, UX contract 19/19, deterministic fixtures 26/26, deploy
18/18, Docker 11/11, and complete `make test` with exit 0. Compileall, tabnanny,
Python 3.10 AST, YAML parse/reference parity, whitespace, and frozen-artifact
checks also pass. The ranked, scored, and Money Flow artifacts remain exactly:

- `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea`
- `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99`
- `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`

The real Social slot remains intentionally unavailable because its latest file
is absent. The real Theme board validates with 34 themes; the existing Theme
analysis remains intentionally unavailable because it is validation v7 rather
than the required v8. No pull, commit, push, deploy, service action,
authentication, dependency, or artifact rewrite was performed.
