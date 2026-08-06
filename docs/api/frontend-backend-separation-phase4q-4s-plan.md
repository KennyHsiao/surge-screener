# Phase 4Q-4S Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-03
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4m-4p-plan.md`

## Objective

Execute three independently reversible source slices without calling the
composite pages fully separated:

1. Phase 4Q moves only Analyst Views' scored candidate grid to the existing
   strict scored feed.
2. Phase 4R moves only Sector Rotation's candidate-to-sector mapping seed to
   the existing strict scored feed.
3. Phase 4S adds a strict US Screener projection and moves only
   `scored_candidates.json`-backed regime, counts, and candidate cards to it.

All analyst/sector providers, AI rotation generation, filtered universe,
Layer 2, DD, reports, ledger, sidebar date discovery, and every writer remain
on their current boundaries. No pull, commit, push, deployment, service action,
authentication change, dependency change, or unrelated UI work is authorized.

## Entry baseline and frozen bytes

The accepted Phase 4M-4P receipt has no blocking regression. Entry suites pass
candidate feeds 8/8, backend boundary 13/13, navigation 56/56, UX fixtures
26/26, UX contract 19/19, API/OpenAPI 44/44, analyst provider 7/7, and sector
flow 6/6. UX fixtures require their existing authorized local-socket path; the
identical authorized run passes.

Exact pre-change target hashes are:

- `ui/analyst_views.py`: `c0438c475bed682b468b02e1ad25f26e4b75f2ba1869b9f58ddf254e54a94cc0`
- `ui/sector_rotation.py`: `b5c36337bb366264d63227a8673eaaa4f9ed5959d7e067ae19fedca9a84d9a4b`
- `ui/us_screener.py`: `8013bbcb5f8b882a430ed0a81d2705a08b3a9cf41d5baffff80209c7ac23f513`
- `ui/_read_api.py`: `6e4e586d60bde00998dfdda5636f53b9882d9708dbd93565ada7bc76891edeb8`
- `api/models.py`: `680dc4e1ff15ee8f8bba82e1beac712eb077aaca24c59e6ad1ce0bce9fe8ec64`
- `api/artifacts.py`: `1b4f4f939b144eb4f6288c1781dfd07ea00282daf691bf1b6f592e88e39ac5a4`
- `api/main.py`: `5c5bd5f29cdb49b2cbe7681e9de40b9a6e9ead21e6e9fe4f160e6e312760e194`
- static OpenAPI: `17512c51f11b68406d1c78dcf799e0120daec54a422d01c3d61ff1205757c73e`

Ranked, scored, and Money Flow artifacts are frozen at
`ca85c803...b5ea8b5ea`, `6af37543...1cff57b99`, and
`96ed8334...b3961731`. Re-hash each production target immediately before its
first edit; changed bytes require re-review instead of overwrite.

## Blocking-issue review

### Closed prerequisite: scored-source producer drift

Review found one real blocker before Phase 4Q: the current producer
`build_scored_output()` writes an additive root `generated_at`, while the
existing strict feed validator accepts only the older exact root shape. The
current checked artifact predates that producer field, so the bug would appear
only after the next pipeline run and would make every scored-feed consumer
fail soft as `invalid_shape`.

The reviewed correction is narrow and backwards compatible: both scored
projections accept exactly either the legacy root or that root plus the single
producer-owned `generated_at`; when present it must be a valid timezone-aware
RFC 3339 timestamp. It remains projected out, so the existing scored-feed DTO,
metadata, clients, and OpenAPI response do not change. A fail-first regression
must prove legacy, producer-current, invalid timestamp, and extra-field cases.

### Phase decisions

- **4Q — GO, risk 4.1/10 (medium):** one strict feed request replaces one
  local scored JSON read. Per-candidate `load_analyst_views()` fan-out and the
  default first-ticker detail call remain local and unchanged. Valid empty,
  unavailable, and client failure are distinct; ad-hoc detail remains usable.
- **4R — GO, risk 4.4/10 (medium):** one strict feed request replaces only the
  candidate seed. Cached `ticker_sector_etf()` fan-out, sector-flow provider,
  local AI read/generation, theme drill, selections, and jumps remain local.
  Candidate-source failure cannot suppress valid sector or AI-read content.
- **4S — CONDITIONAL GO resolved by the contract below, residual risk 6.0/10
  (medium):** the existing strict feed is insufficient and must not be widened.
  A new additive, closed projection exposes only fields already rendered by US
  Screener and preserves compatibility routes and existing feed clients.

No breaking API, data-loss path, credential surface, or unverified mutation is
part of the accepted scope. The previous 4S NO-GO applied specifically to
reusing the insufficient feed; it is resolved by designing a separate strict
projection before implementation.

### Impact map and consistency review

- **L0 production:** three selected page reads, one fixed client, and the
  additive model/projector/route contract; 7 files.
- **L1 direct contracts:** API, client/page focused suites, static OpenAPI,
  boundary/navigation, fixture counters, and Make inventory; 9 files.
- **L2 consumers:** app navigation and UX capture execute the same page entry
  points but require no production change; docs/journals record the boundary.
- **Estimated implementation:** 650-900 changed lines including tests and the
  static contract. It is split into prerequisite, 4Q, 4R, and 4S reviewable
  units rather than one undifferentiated patch.
- **Breaking classification:** none; one new GET and one new source ID are
  additive, while the existing feed accepts one producer-owned private root
  field without changing its public bytes.
- **Horizontal consistency:** fixed URLs, discriminated result unions,
  Pydantic `extra="forbid"`, fail-soft envelopes, exact provenance, one request
  per page, sanitized UI copy, and no local fallback follow the existing Phase
  4F-4O patterns.

Overall weighted risk is 5.0/10: scope 8, breaking potential 3, pattern
deviation 4, verification exposure 5, and reversibility 3 under the repository
weights. The API change remains below the high-risk threshold because it is
additive and independently reversible, but requires full API/OpenAPI and
shared-fixture verification before completion.

## Phase 4S contract first

Add parameter-free
`GET /api/v1/candidates/scored/screener` with operation
`getScoredCandidatesScreener`, source ID `candidates.scored.screener`, and the
existing discriminated fail-soft envelope:

- `200 available=true`: `reason=ok`, strict data below, `meta.asOf` equals
  `scan_date`, `meta.generatedAt=null`, `Cache-Control: no-store`.
- `200 available=false`: one existing unavailable reason, null data/as-of/time.
- `500`: the existing sanitized RFC 9457 problem response for unexpected code
  defects only.

The closed data object contains exactly:

- `scan_date`, `needs_layer2_count`, `watchlist_count`;
- `regime_context` with `spy_vs_50dma`, `spy_vs_200dma`, `vix_level`,
  `vix_regime`, `global_score_multiplier`, `active_themes`, and
  `regime_warnings`;
- at most 100 bucket-priority/deduplicated `candidates`, sourced only from
  `needs_layer2` then `watchlist` and ordered by `regime_adjusted_score`.

Each candidate contains exactly the US Screener-rendered `ticker`, canonical
`verdict`, `regime_adjusted_score`, seven bounded score dimensions,
`key_signals`, `key_risks`, `suggested_entry_zone`, bounded string/number/null
`suggested_stop`, bounded nullable `suggested_size_pct`, nullable
`anti_example_warning`, `data_missing`, and a nullable technical summary with
only `pattern_type` and `macd_state`. Raw technical factors, `all_scored`
REJECT rows, `similar_to_case`, `novel_pattern`, `scoring_mode`, source
diagnostics, and unused root fields remain private.

This is an additive v1 read endpoint, so the draft version becomes
`1.10.0-draft`; no deprecation is needed. It inherits the existing loopback
host/CORS boundary and fixed UI request cadence. There is no request body,
query, object identifier, mutation, retry, idempotency, or new auth/rate-limit
surface. Response validation, the server artifact loader, and the fixed client
cap bound resource use.

## Execution steps

### Phase 4Q — Analyst Views scored grid

1. Add a fail-first focused suite for available, available-empty,
   unavailable, all bounded failures, one request, no local scored fallback,
   feed-to-provider fan-out, default-detail behavior, and embedded
   `render_for()` isolation.
2. Introduce a typed grid state and convert validated feed candidates in
   memory. Retain one local analyst lookup per candidate and the existing local
   detail lookup/default.
3. Show fixed sanitized empty/unavailable/failure copy while keeping arbitrary
   ticker lookup usable. Do not expose client reason strings.

### Phase 4R — Sector Rotation candidate mapping

1. Add a fail-first focused suite covering available mapping, available-empty,
   unavailable, all bounded failures, one request, no local scored fallback,
   cached sector fan-out, and preserved AI generation/read and selection paths.
2. Replace only the scored candidate seed with the strict feed. Keep feed order
   into the existing mapping/sort logic and retain cached local sector lookup.
3. Render fixed sanitized partial-state copy only in the candidate-mapping
   section; valid sector charts, heat table, AI read, and theme drill remain.

### Phase 4S — strict US Screener projection and consumer

1. Add fail-first API/model/projector/OpenAPI tests for exact root/item
   allowlists, legacy/current producer roots, invalid shapes/types/counts,
   bucket-only projection, ordering/deduplication/caps, metadata, fail-soft
   recovery, compatibility-route preservation, loopback security, and static /
   generated OpenAPI parity.
2. Add the strict DTO, artifact spec, route, static OpenAPI 3.1 contract, fixed
   8 MiB client, typed result union, provenance checks, and deadline handling.
3. Add a fail-first page/client suite for one request, available/empty,
   unavailable, all bounded failures, no local scored read/status check, Layer
   2 regime fallback, and preservation of every unselected local source.
4. Load the projection once per page render. Use it only for the sidebar LLM
   status, scored regime/count contribution, and candidate cards. Retain
   filtered universe, Layer 2, DD, reports, ledger, analyst detail, and actions.

## Allowed implementation surfaces

- UI/client: `ui/analyst_views.py`, `ui/sector_rotation.py`,
  `ui/us_screener.py`, `ui/_read_api.py`
- API/contract: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`, `scripts/test_api.py`,
  `scripts/test_ui_candidate_feeds_api.py`
- New focused suites: `scripts/test_ui_analyst_views_scored_api.py`,
  `scripts/test_ui_sector_rotation_scored_api.py`,
  `scripts/test_ui_us_screener_api.py`
- Exact contracts: `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `scripts/ui_ux_fixtures.py`,
  `scripts/test_ui_ux_fixtures.py`, `Makefile`
- Documentation/receipts: this plan, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, required
  Lens/Ripple/Gateway/Builder/project journals

Any provider, writer, workflow, deployment, systemd, Compose, dependency,
credential, unrelated page, filtered/Layer2/DD/report/ledger migration, or
existing response-shape change is unexplained scope drift and stops execution.

## Verification and rollback

Run every new test red-first and green after its phase, then candidate-client,
API/OpenAPI, boundary, navigation, UX fixture/contract, analyst, sector,
deployment, Docker, compile, tabnanny, Python 3.10 AST, shell, whitespace, and
complete `make test` gates. Re-hash target production files and the three
frozen artifacts, review the actual diff against this allowed list, and fix all
blocking correctness, regression, test, or maintainability findings.

Each phase rolls back by restoring only its named UI/test/doc hunks. Phase 4S
also removes its additive route/client/spec/DTO/projector; no migration or
external state rollback exists. The separate accessibility authority remains
at the known shared-worktree 24/27 baseline and must not be weakened.

## Implementation receipt

Phase 4Q-4S was implemented on the accepted branch and matches the reviewed
source-slice boundary. Analyst Views and Sector Rotation each use one existing
strict scored-feed request for their selected candidate slice. US Screener uses
one new strict `candidates.scored.screener` request for only regime, counts, and
candidate cards. Analyst/sector providers, AI rotation generation, filtered
universe, Layer 2, DD, reports, ledger, actions, and every writer remain on their
pre-existing boundaries. The repository now records nineteen narrow API-only
slices; this is not a claim of whole-page or whole-process separation.

Red-first evidence failed for the intended reasons: the current scored producer
root was initially rejected, Analyst Views and Sector Rotation had no fixed
client dependency, and the screener DTO did not yet exist. The prerequisite now
accepts exactly the legacy scored root or that root plus one valid producer-owned
`generated_at`, while preserving existing scored-feed public bytes. Final code
review found and fixed one blocking 4S count-invariant omission before completion:
both projected counts must equal their source bucket lengths and booleans are
rejected.

Verification is green:

- candidate feeds 8/8; Phase 4Q 4/4; Phase 4R 4/4; Phase 4S 5/5;
- API/OpenAPI 47/47; fixed read client 12/12; boundary 14/14; navigation 57/57;
- analyst provider 7/7; sector flow 6/6; UX contract 19/19; fixtures 26/26;
- deployment 18/18; Docker 11/11; the final complete `make test` exited 0;
- compileall, tabnanny, Python 3.10 AST for 16 affected Python files, OpenAPI
  YAML parsing, shell syntax, whitespace, and scoped local-fallback scans pass.

Post-change production hashes are:

- `ui/analyst_views.py`: `2b24868096c790180fe37bac4b4ea8385cbcfb3a9a62c1182b7c83787a75553e`
- `ui/sector_rotation.py`: `e73e5680e3f66d985befe5a5782d7e9ef1cb0a6005344d0c486ec3ab9d13aa05`
- `ui/us_screener.py`: `8a18f3aef2f9ae8158e959a7bf2a2b72cadbe570546d4a3bb6ad6b86f5db9e82`
- `ui/_read_api.py`: `1d9dd323daab0438ec3aa5cc09265e4edbea3285a1c6d67837f6faba8f89b39e`
- `api/models.py`: `85ba08154a9ffc74a350a429df012bb07431da06e4d26b9b67f4bf17e0f565be`
- `api/artifacts.py`: `d3a92e71abe74a2025765ec5be8846e8bd259626545b2c6f85f11fa00734d60f`
- `api/main.py`: `0bcdfa126acbd52c19c654b1850ef55c1327a75c0a728f6d9100161dcfdff3aa`
- static OpenAPI: `1983c6cf2c2728ad5c7cbbad42841c2dd1a1545c7fa725a156602f26e24bd16f`

Ranked, scored, and Money Flow artifacts remain byte-identical at the three
entry hashes. The actual Phase diff was compared against the allowed surfaces;
there is no unexplained scope drift. The shared worktree still contains earlier
unrelated changes, which were preserved. No pull, commit, push, deployment,
service action, authentication change, or dependency change ran.

## Subsequent queue

After 4Q-4S, review before execution:

1. **Phase 4T:** X Sentiment ranked-candidate fallback, the last direct UI
   candidate-artifact seed after this batch; preserve social snapshots, roster,
   network/LLM refresh, and market filtering.
2. **Phase 4U:** strict persisted social-intelligence read projection and
   page-slice selection; live/network/LLM refresh remains Deferred.
3. **Phase 4V:** Theme Flow read-side decomposition for analysis/snapshot
   presentation only; refresh/status mutations remain local/Internal.
