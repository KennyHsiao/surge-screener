# Phase 4F Ranked/Scored Candidate Feed Plan

- **Status:** Implemented and verified
- **Date:** 2026-08-02
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Accepted parent:** Phase 4F in
  `docs/api/frontend-backend-separation-phase4d-4e-plan.md`
- **Planning note:** the repository-requested Superpowers skills are not
  installed in this session. The same plan-review, fail-first, staged
  execution, diff-review, and verification gates are applied directly with
  Ripple, Gateway, and Builder guidance.

## Entry review

Phase 4D/4E has no blocking regression at this entry gate:

| Gate | Result |
| --- | --- |
| Market Thesis focused suite | 7/7 passed |
| Reversal/Oversold focused suite | 7/7 passed |
| Backend boundary | 10/10 passed |
| Dashboard/navigation contracts | 54/54 passed |
| Loopback API/OpenAPI baseline | 44/44 passed |

The first API run was stopped only by the sandbox denying a random loopback
test-port bind. The identical authorized run passed 44/44.

## Consumer and field-use matrix

The current candidate runtime path is resolved by
`SURGE_CANDIDATE_OUTPUT_DIR`, falling back to `SURGE_RUNTIME_DIR` and then the
repository root. Phase 4F preserves that server-side resolver and does not
expose or mutate any path.

| Consumer | Artifact | Fields/semantics used | Phase 4F disposition |
| --- | --- | --- | --- |
| Today Decision | ranked | ordered candidates; `ticker`, `rank_score`, `last_price`, `rank_bucket`, `ret_5d`, `ret_20d`; five rendered score components; options `status`, `iv_percentile`, `spread_pct`, `flow_score`, `warnings`; row `warnings` | migrate |
| Today Decision | scored | bucket priority `needs_layer2`, `watchlist`, `all_scored`; unique ticker, adjusted/composite sort; verdict, seven scores, data gaps, due-diligence flag, signals, risks, entry zone | migrate |
| Analytics DB | ranked | source-order top tickers/symbol fallback | later phase |
| Industry Roles | ranked | ticker set union with influencer picks | later phase |
| Schedules results | ranked | `scan_date`, count, first five tickers | later phase |
| X Sentiment refresh | ranked | ticker/symbol, rank score/bucket, last price/price; passed into a write-producing refresh | excluded mutation slice |
| Analyst Views | scored | bucket candidates, ticker, verdict; then one live analyst read per ticker | later provider-coupled slice |
| Institutional Holdings | scored | all-scored ticker, institutional score, verdict, signals | later phase |
| Options Cockpit | scored | bucket priority/fallback, scan date, ticker, verdict, adjusted score | explicitly excluded |
| Sector Rotation | scored | candidates, ticker, verdict; then per-ticker sector provider calls | later provider-coupled slice |
| US Options | scored | candidates, ticker, verdict, adjusted/composite score, options-flow score; per-ticker IV reads | later N+1-sensitive slice |
| US Screener | scored | regime/counts, two selected buckets, all candidate detail and pipeline file state | excluded pipeline/control surface |

`_candidate_controls`, candidate writers, pipeline scripts, Trade State,
positions, quote providers, and compatibility-route clients are separate
dependency surfaces and remain unchanged.

## Blocker review and accepted amendment

No unresolved blocking issue remains:

1. **Duplicated scored buckets:** the strict projection preserves current
   bucket priority, deduplicates by ticker before sorting, and emits one bounded
   normalized candidate list.
2. **Runtime path overrides:** both new registry entries reuse
   `candidate_output_path()` on the API side. No client path input is added.
3. **Stale/empty semantics:** ranked and scored feeds retain independent
   `scan_date` provenance. They are not required to share a date because the
   current real files are independently generated. Empty valid lists remain
   available; missing/invalid files remain authoritative unavailable results.
4. **Ordering:** ranked rows sort by non-increasing `rank_score`; scored rows use
   current bucket priority, stable ticker deduplication, then non-increasing
   adjusted/composite score.
5. **Quote fallback:** the existing quote fallback is preserved only for a
   ranked row without a positive persisted price. Phase 4F introduces no
   per-ticker candidate API request.
6. **LLM detail:** only Today Decision-rendered reasons, risks, data gaps, and
   entry-zone text cross the boundary. Suggested stop/size, technical
   breakdown, anti-example, provenance prompts, and other source detail stay
   server-side.
7. **Repeated reads:** `render()` obtains exactly one ranked and one scored
   result and shares their rows across candidate tabs and opportunity fallback.
8. **Mutation controls:** refresh/LLM controls and their status/writer paths
   remain local and are not imported by the new read client.

## Gateway contract

- Add fixed, parameter-free, loopback-only reads:
  `GET /api/v1/candidates/ranked/feed` and
  `GET /api/v1/candidates/scored/feed`.
- Keep `/api/v1/candidates/ranked` and `/api/v1/candidates/scored` unchanged as
  open compatibility routes. No breaking narrowing is authorized.
- Add strict `extra=forbid`, no-coercion, finite, bounded presentation DTOs.
  Projection is an explicit field allowlist; source objects are never reflected
  into the response.
- Keep HTTP 200 unavailable envelopes for expected artifact states, sanitized
  RFC 9457-style 500 responses for unexpected defects, `Cache-Control:
  no-store`, one-second client deadline, no redirects/proxy, and closed reason
  codes.
- Bind `meta.asOf` to each feed `scan_date`. Ranked `meta.generatedAt` is bound
  to the projected source timestamp; scored has no generated timestamp and
  keeps `meta.generatedAt=null`.
- Response caps are 512 KiB for ranked and 1 MiB for scored, above the frozen
  real public projections but below the compatibility artifacts.
- Authentication and rate limiting are not added to these fixed internal
  loopback reads. Any non-loopback deployment remains blocked on a separate
  perimeter/auth/rate-limit review.

## Ripple risk assessment

| Dimension | Score | Weight | Evidence |
| --- | ---: | ---: | --- |
| Impact scope | 5 | 30% | shared API/model/client files plus one page and tests/docs |
| Breaking potential | 2 | 25% | additive routes; compatibility routes retained |
| Pattern deviation | 1 | 20% | follows the existing strict `/feed` and fixed-client pattern |
| Test-coverage risk | 2 | 15% | fail-first API/client/page/request-count plus full regressions |
| Reversibility | 2 | 10% | additive endpoints and one isolated consumer adoption |

Weighted risk: `(5×0.30)+(2×0.25)+(1×0.20)+(2×0.15)+(2×0.10) = 2.7/10`,
low. The main cascade risk is unintentionally migrating another candidate
consumer through a shared helper; the dependency and diff gates explicitly
forbid that.

## Affected files and execution order

Expected implementation scope:

- API/contracts: `api/models.py`, `api/artifacts.py`, `api/main.py`
- fixed client and first consumer: `ui/_read_api.py`, `ui/today_decision.py`
- tests: `scripts/test_api.py`, a new focused Phase 4F test,
  `scripts/test_ui_backend_boundary.py`, `scripts/test_dashboard_navigation.py`,
  and `Makefile`
- contract/docs: `docs/api/quant-radar-v1.openapi.yaml`, endpoint inventory,
  user guide, this receipt, and required engineering journals/activity log

Fixture sources change only if the candidate page's observable fixture contract
requires it. No dependency, Compose, deployment, environment, provider, writer,
database, authentication, mutation, other UI consumer, or unrelated page is in
scope.

Execution order:

1. Add focused fail-first registry/projection/route/client/page/request-count
   and dependency tests; confirm absence of the new contract fails.
2. Implement ranked feed DTO/projector/route/client, then scored feed equivalents.
3. Convert only Today Decision's ranked/scored presentation reads to one shared
   result each; retain quote fallback and all controls.
4. Update static OpenAPI/docs and generated/static parity assertions.
5. Run real-artifact validation, focused suites, API, boundary, navigation,
   fixtures, compilation/Python 3.10 AST, whitespace, full `make test`, exact
   diff-to-plan review, and post-change bug/maintainability review.

## Pre-change exact-byte receipt

These hashes freeze shared dirty-worktree inputs before the first code/test
edit. They are evidence only and must not be used to restore over concurrent
work.

| File | SHA-256 |
| --- | --- |
| `ranked_candidates.json` | `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea` |
| `scored_candidates.json` | `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99` |
| `api/models.py` | `593d18c821a3a831b231cb3829b71d6f12676e4135c4c17570f0b42b36813d0b` |
| `api/artifacts.py` | `1c3b77bd4eacee0b981e478d59283bbeb625a48d41498d5bc3debf68a9b07741` |
| `api/main.py` | `7dbe8a0ab763b7fc4ad7242dc4d33a383448442423659a34057d96461657c2e7` |
| `ui/_read_api.py` | `ad881c1c1531cda88b19c3781a7ffc24fa91da95eb077498d9d16c02074f20f3` |
| `ui/today_decision.py` | `939bdca5ec086484c24312cd6f295f23358d5184ef678fdf9fe3ba7d3f256eb0` |
| `scripts/test_api.py` | `4822048b77c0932115088d457e55984c7362a933403ce6d1738c97d0bf7e14ce` |
| `scripts/test_ui_backend_boundary.py` | `dd8d00ef2af7653df2dad044f52bf5f7c4f54f6f68fe34dbbfceebc7e255d56a` |
| `scripts/test_dashboard_navigation.py` | `ef1c4229da143016b0bd8a95501ddb6a8a81a11be77653ba16f42d9545414afd` |
| `Makefile` | `0d7ed4f5a41dbb91ff24f3d134397d81194d9ef39b65a25070dcb51a06220fd8` |
| `docs/api/quant-radar-v1.openapi.yaml` | `b50de844335b51fcb5b1251d1b643c05433159226605b0f246eec5a584042636` |
| `docs/api/fastapi-endpoint-artifact-inventory.md` | `a42fbc57943f4efb081916aa43082930313e16b7c61260c869cf6728e197c54a` |
| `docs/USER_GUIDE.md` | `f00c7a075c677c8714232935630085dc40d58297aa2f1e48e74959d610a16025` |

Frozen real artifacts are 146,794 and 148,823 bytes. Ranked has 50 rows dated
2026-07-30; scored has 36 all-scored rows dated 2026-05-29 and empty priority
buckets. The independent dates are an observed state, not an instruction to
rewrite either artifact.

## Execution receipt

Phase 4F was implemented with the accepted additive boundary:

- Added strict, bounded, non-reflective ranked/scored public DTOs and registry
  projections at `/api/v1/candidates/ranked/feed` and
  `/api/v1/candidates/scored/feed`. The open `/ranked` and `/scored`
  compatibility routes remain unchanged.
- Both feeds retain independent scan dates, server-side runtime-path
  resolution, stable priority/deduplication/sorting, finite typed scores,
  closed nested objects, fail-soft artifact states, and no-store responses.
- Today Decision now obtains exactly one ranked and one scored result per rerun,
  converts each validated snapshot once, and reuses the same rows in its result
  tabs and opportunity fallback. Candidate controls/writers/status, quote
  fallback, Trade State, Market Thesis/daily summary, Options Flow,
  reconciliation, validation, ledger, Reversal/Oversold, and providers remain
  on their original boundaries.
- API and checked-in OpenAPI are `1.9.0-draft`. Ranked and scored clients retain
  fixed loopback URLs, one-second deadlines, no redirects/proxy, and 512 KiB /
  1 MiB retained decoded-body caps.

The first fail-first run failed on the absent ranked feed DTO as intended. The
current exact ranked and scored artifacts then validated through the strict
registry with 50 and 36 projected rows despite their independent 2026-07-30
and 2026-05-29 dates.

### Diff-to-plan and review

The planned API, client, Today Decision, OpenAPI, fixture, focused/regression,
Makefile, inventory, guide, and receipt files changed. Three additional test
contracts changed for explained scope only:

- `scripts/test_ui_ux1a_safety.py` now proves injected API rows do not read
  local candidate JSON instead of calling the removed zero-argument readers.
- `scripts/test_docker_runtime_contract.py` now binds candidate runtime paths
  between the pipeline and API registry and forbids a Today Decision local
  path, replacing the obsolete pipeline-to-UI invariant.
- `scripts/ui_ux_fixtures.py` patches typed API outcomes and records one ranked
  plus one scored call rather than patching local row helpers.

Post-change review fixed three findings before completion: explicit finite
number validation, exact required/optional scored dimension keys, and an
English-detail indentation regression introduced while excluding private
`suggested_stop`. The same review also separated a valid empty feed from an
unavailable/failed API in the user-facing state without exposing internal
reason detail. Focused regressions now prove public `key_signals`, the
private-field exclusion, and the empty/unavailable distinction. No dependency,
Compose, deployment,
environment, database, writer, provider, authentication, mutation, other UI
consumer, or unrelated page change was made for Phase 4F.

### Verification

| Gate | Result |
| --- | --- |
| Phase 4F focused DTO/route/client/page/real artifacts | 8/8 passed |
| Backend separation boundary | 11/11 passed |
| Fixed-client transport/deadline/failure suite | 12/12 passed |
| API and generated/static OpenAPI | 44/44 passed |
| Market Thesis Phase 4D regression | 7/7 passed |
| Reversal/Oversold Phase 4E regression | 7/7 passed |
| Dashboard/navigation contracts | 54/54 passed |
| UX1A safety | 5/5 passed |
| UX full-route fixtures | 26/26 passed |
| Docker runtime/separation contract | 11/11 passed |
| Complete repository target | final `make test` passed |
| Static gates | Python compile, tabnanny, Python 3.10 AST, scoped tracked/untracked whitespace passed |

The loopback API, fixed-client deadline, fixtures, and complete test target
needed local socket access; sandboxed socket attempts were denied by policy,
while identical authorized runs passed. Existing Streamlit bare-mode and
`use_container_width` deprecation warnings are non-blocking and come from
unchanged presentation surfaces.

## Next queued plan

Phase 4G and Phase 4H are specified in
`docs/api/frontend-backend-separation-phase4g-4h-plan.md`. They are deliberately
queued for a fresh prerequisite review, not executed as part of Phase 4F.
