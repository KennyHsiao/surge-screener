# Phase 6P-6R Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6m-6o-audit.md`

## Objective

Move only Sector Rotation's fixed sector-to-theme drill read behind the
loopback read API:

1. **Phase 6P:** add the strict bounded theme-drill contract and fixed endpoint.
2. **Phase 6Q:** add the immutable bounded client.
3. **Phase 6R:** make `_render_sector_themes_drill()` use exactly one typed API
   result and remove its direct `scripts.theme_flow.load_baskets` binding.

The Theme Flow board/provider, basket tickers and descriptions, sector lookup,
local AI read/generation, candidate mapping, selection/jump state, content
source, and every writer remain unchanged.

## API design

- **Method/path:** `GET /api/v1/market-context/theme-drill`
- **Source ID:** `market-context.theme-drill`
- **Source:** fixed release-owned `content/theme_baskets.json`; no request path,
  query, discovery, provider, cache refresh, or write.
- **Data:** `sectors`, maximum 11, sorted by SPDR ETF. Each item contains one
  exact ETF from `XLB | XLC | XLE | XLF | XLI | XLK | XLP | XLRE | XLU | XLV |
  XLY` and one to 100 unique source-ordered bounded theme names. Across the
  response, at most 100 unique themes are allowed.
- **Projection:** omit root note, descriptions, tickers, representative hints,
  paths, cache fingerprint, and all unknown source fields.
- **Source validation:** regular fixed file only, no symlink, maximum 64 KiB,
  strict UTF-8/JSON/object shape, root keys restricted to `_note` and `themes`,
  bounded unique names, record object shape, parent list type, supported ETF
  enum, non-empty parent lists, and duplicate rejection.
- **Failure:** existing `available | unavailable` envelope. Missing is
  `missing`; filesystem/symlink is `unreadable`; byte/UTF-8/JSON/schema errors
  are `invalid_shape`. Expected source failures remain HTTP 200.
- **Metadata/cache:** `asOf=null`, `generatedAt=null`, `Cache-Control: no-store`.
- **Client:** fixed `127.0.0.1:8000` URL, 256 KiB decoded-body cap, one-second
  whole-request deadline, strict media/no-store/source/metadata/model checks,
  frozen outcomes, no cache, immediate recovery, and no local fallback.

The additive route advances static and generated OpenAPI together from
`1.20.0-draft` to `1.21.0-draft`. Existing loopback peer/Host enforcement and
no-CORS behavior are unchanged. No authentication, rate-limit, service,
dependency, deployment, or storage topology change is needed.

## Phase execution

### Phase 6P — contract and server

1. Add fail-first tests for valid/empty/missing/unreadable/symlink/invalid
   UTF-8/JSON/root/record/parent shapes, caps, unsupported/duplicate ETFs,
   duplicate themes, ordering, privacy projection, no-store, metadata,
   OpenAPI examples, and immediate recovery.
2. Add strict theme-drill DTOs in `api/models.py` and the fixed projection
   reader in `api/artifacts.py`; inject only its server-owned path into
   `create_app()` for tests.
3. Add the fixed GET to `api/main.py`, the exact static OpenAPI operation,
   examples and schemas, and bump both versions once to `1.21.0-draft`.

### Phase 6Q — immutable client

1. Add frozen available/unavailable/failure outcomes and
   `load_theme_drill()` to `ui/_read_api.py`.
2. Reuse the established bounded fixed-read transport. Validate the complete
   failure vocabulary, fixed source metadata, response cap, deadline,
   available-empty authority, and recovery after a prior failure.

### Phase 6R — API-only consumer

1. Replace the lazy backend import and local reverse-map construction in
   `_render_sector_themes_drill()` with exactly one client call.
2. Preserve current ETF sort, source theme order, selectbox key, labels,
   session-state focus, jump behavior, and fail-soft optional rendering.
   Unavailable/failure hides only this bonus drill and never falls back locally.
3. Remove only the migrated `scripts.theme_flow.load_baskets` allowlist entry;
   retain the separate local `scripts.sector_rotation` AI generator and all
   other provider/private siblings.

## Affected files

- Contract/server: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`
- Client/consumer: `ui/_read_api.py`, `ui/sector_rotation.py`
- Tests: new focused theme-drill API/client/consumer suite,
  `scripts/test_ui_backend_boundary.py`, navigation/API parity where required
- Documentation/receipts: `Makefile`, `docs/USER_GUIDE.md`, endpoint inventory,
  Gateway/Builder/Artisan journals, and exactly one combined PROJECT receipt

No source content, producer, writer, provider, credential, prompt, dependency,
Compose/systemd/deploy file, schedule, other page, or mutation is planned to
change.

## Verification gates

- Focused source/model/route/OpenAPI/client/consumer/privacy suite.
- API, shared-client, backend-boundary, Sector Rotation, navigation, fixture,
  deployment, and Docker contract regressions.
- Python 3.10 AST, compileall, tabnanny, YAML/static-generated OpenAPI parity,
  `git diff --check`, source/provider/writer hash preservation, and full
  `make test`.
- Post-implementation diff-to-plan review for privacy, unbounded reads, local
  fallback, call count, failure isolation, missing tests, and scope drift.

## Blocking-issue review

No unresolved blocker remains after two review iterations.

- **Iteration 1:** rejected publishing the full basket source. Reduced the
  response to the exact sector/theme reverse map and capped every dimension.
- **Iteration 2:** closed source-shape drift, invalid/duplicate parents,
  deterministic ordering, cap, metadata, OpenAPI parity, exact-one-load,
  failure isolation, and local-fallback risks. Existing source and producer
  behavior are protected by regression/hash checks.

Final verdict: **GO** for Phase 6P-6R.

## Implementation closure

- Added the strict fixed `market-context.theme-drill` projection, route,
  OpenAPI `1.21.0-draft` contract, immutable bounded client, and one-result
  Sector Rotation consumer.
- Removed the selected UI `scripts.theme_flow.load_baskets` binding without
  changing the source content, producer, Theme Flow board/provider, Sector
  Rotation AI generator, selection state, or any mutation.
- The accepted inventory advances from 53 to 54 API-only slices. Reproducible
  residual counts shrink from 62 to 61 direct `scripts.*` bindings while the
  20 direct-binding modules, 30 `_shared` importers, and 14 `load_json` modules
  remain unchanged.
- Post-implementation review found no unexplained scope drift, privacy leak,
  unbounded read, local fallback, duplicated request, or missing failure-state
  coverage. Existing unrelated deployment/dependency edits in the dirty
  worktree were preserved and were not part of this phase.

Verification passed: focused theme drill 6/6, API 47/47, shared client 12/12,
backend boundary 23/23, Sector Rotation 5/5, navigation 66/66, UX contract
19/19, fixtures 26/26, public resources 8/8, deploy 18/18, Docker 11/11,
Python 3.10 AST/compileall/tabnanny, YAML/OpenAPI/static gates,
`git diff --check`, source/producer integrity checks, and complete `make test`
with exit code 0.

## Following queue

Phase 6S-6U should perform post-migration convergence closure: prove the
remaining direct/import/transitive counts, freeze the public-read completion
baseline, and write the reviewed architecture entry criteria for identity,
authorization, revisioned mutation, and atomic recovery. It must not implement
private or writable APIs without a separate accepted plan.
