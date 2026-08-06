# Phase 4G/4H/4I Candidate Consumer Decomposition Plan

- **Status:** Implemented and verified
- **Date:** 2026-08-02
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** verified Phase 4F in
  `docs/api/frontend-backend-separation-phase4f-plan.md`

## Objective

Adopt the two strict Phase 4F candidate feeds in three additional narrow,
read-only consumers without widening the API, serializing compatibility
artifacts, introducing per-ticker HTTP N+1, or moving adjacent provider,
status, write, or mutation behavior.

The prerequisite review reran the Phase 4F focused, API/OpenAPI, boundary,
navigation, and UX fixture baselines and froze the target files plus current
real artifacts. The review found two correctable plan gaps: Phase 4G needed an
explicit partial-state rendering contract, and Phase 4I was only a provisional
candidate. Both are resolved below. No changed source shape, new route, new
field, or unresolved blocking issue remains.

## Prerequisite review and accepted constraints

### Baseline evidence

| Gate | Result |
|---|---|
| Phase 4F candidate feed suite | 8/8 passed |
| Backend boundary | 11/11 passed |
| Dashboard/navigation | 54/54 passed |
| API/OpenAPI | 44/44 passed in the authorized loopback environment |
| UX fixture contracts | 26/26 passed in the authorized low-level environment |

The first API/fixture attempts stopped only because the workspace sandbox
forbids loopback binding and low-level descriptor operations. The identical
authorized commands passed; this is an environment limitation, not a product
baseline failure.

### Frozen pre-change sources and real artifacts

| File/artifact | SHA-256 |
|---|---|
| `ui/sys_schedules.py` | `4afea23017dac016ef04ea1360b7b8c560a0a5c95f1abe9689e4e1589ecf06ee` |
| `ui/institutional_holdings.py` | `6d97275caacf9833dbc6052abbad985ce8a42ece8658d7d6f3cb03ffdc91db18` |
| `ui/analytics_db.py` | `70c2f2fb22fd5ee7bd2e0da406946ca06168faf0b6f575246aac964c6e4dd067` |
| `ranked_candidates.json` | `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea` |
| `scored_candidates.json` | `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99` |
| `reports/money_flow/latest.json` | `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731` |

### Ripple impact review

- Level 0 is three UI modules. Level 1 consumers are `app.py`,
  `ui/institutions.py`, and `ui/stock_checkup.py`; Level 2 covers navigation,
  deterministic fixtures, backend-boundary contracts, and the existing fixed
  client/public DTO pair. The API projector, routes, OpenAPI, providers,
  writers, and deployment remain outside the change.
- Planned production impact is three files and approximately 65–95 changed
  lines. Verification/documentation impact is three new focused tests plus
  four existing gate/doc files, approximately 300–450 test lines and 50–80
  gate/doc lines. Journals and this receipt are operational evidence only.
- Risk score is **3.0/10 (low)**:
  `(impact 5×0.30) + (breaking 1×0.25) + (pattern 2×0.20) +`
  `(coverage 4×0.15) + (reversibility 2×0.10) = 2.95`, rounded to 3.0.
  There are no breaking changes and rollback is the removal of three narrow
  client-adoption edits plus their tests/docs.

### Gateway contract review

- Continue using the fixed, loopback-only, read-only GETs
  `/api/v1/candidates/ranked/feed` and `/api/v1/candidates/scored/feed`.
- Ranked already exposes `scan_date` and ordered unique `ticker` rows; scored
  already exposes `ticker`, `verdict`, `scores.institutional`, and
  `key_signals`. No consumer needs a source-private field.
- This is consumer adoption only: no request, response, status, auth, rate
  limit, route, compatibility endpoint, or OpenAPI surface changes. Breaking
  change classification is **none**.

## Phase 4G — Schedules candidate-refresh ranked summary

### Accepted provisional boundary

- Migrate only the ranked-candidate portion of
  `ui/sys_schedules.py::_latest_candidate_refresh_result` to the existing
  `GET /api/v1/candidates/ranked/feed` fixed client.
- Preserve the independently persisted Money Flow sibling read and its current
  publishable/coverage presentation. Do not migrate other schedule result
  fetchers, logs, reflection, operational status, or schedule mutations.
- Make the ranked result authoritative: unavailable/client failure produces no
  local ranked fallback. A valid empty ranked feed remains available and must
  not be confused with transport failure.
- Load ranked data at most once per Streamlit rerun and only when a visible
  `candidate_refresh` result card needs it. The same result must be reused if a
  malformed registry contains duplicate result-type cards.
- Preserve partial composition: a Money Flow result may still render when the
  ranked feed is unavailable. The card must surface a fixed sanitized ranked
  unavailable state without suppressing valid Money Flow data.
- Represent those two facts independently: render the safe unavailable banner
  when ranked is unavailable/failed, then render valid Money Flow markdown if
  present. Do not label ranked as a valid zero-row response when the request
  failed. A valid available-empty feed remains the ordinary no-result state.

### Expected files and gates

- `ui/sys_schedules.py`, existing fixed-client types in `ui/_read_api.py` only
  if a presentation adapter is necessary, a new focused Phase 4G test,
  backend-boundary/navigation/fixture contracts, inventory/user guide, Make
  test inventory, and receipts/journals.
- No API DTO, registry, route, OpenAPI version, deployment, dependency,
  provider, writer, or other result fetcher should change.
- Fail-first tests in `scripts/test_ui_schedules_candidate_api.py` must cover
  one-request reuse, empty/unavailable/failure
  distinctions, no `candidate_output_path("ranked_candidates.json")` read in
  this result fetcher, preserved Money Flow partial output, duplicate result
  types, and unchanged Schedules registry API-only behavior.

Provisional risk is low-to-medium. The main risk is representing partial
ranked failure without incorrectly converting valid Money Flow content into a
whole-card failure. That state contract must be reviewed before code changes.

## Phase 4H — Institutional Holdings scored context

### Accepted provisional boundary

- Migrate only `ui/institutional_holdings.py::_render_score_context` from local
  `scored_candidates.json` to the existing strict
  `GET /api/v1/candidates/scored/feed` client.
- Preserve manual/MAG7 ticker input, the cached yfinance institutional/Form-4
  provider, holder/insider presentation, the parent Institutions Fund Catalog
  slice, and embedded `render_for()` behavior.
- Use one scored feed request per rendered institutional detail, never one
  request per candidate or holder. Filter the validated feed in memory by the
  normalized ticker.
- An unavailable/failed scored feed hides or safely marks only the optional
  candidate-score context. It must not block the live institutional provider
  result or manual ticker lookup, and it must never trigger a local artifact
  fallback.
- Reuse the Phase 4F allowlist (`institutional`, `verdict`, `key_signals`);
  adding another scored field or a ticker-specific endpoint requires a plan
  amendment.

### Expected files and gates

- `ui/institutional_holdings.py`, a new focused Phase 4H test,
  backend-boundary/navigation/fixture contracts, inventory/user guide, Make
  test inventory, and receipts/journals.
- No API/OpenAPI/model/client transport change is expected. No SEC EDGAR,
  yfinance, Fund Catalog, provider cache, auth, mutation, or other scored
  consumer is in scope.
- Fail-first tests in `scripts/test_ui_institutional_score_api.py` must cover
  available match/no-match, empty, authoritative
  unavailable, every fixed-client failure class, no local scored read, exactly
  one request, manual/provider continuity, and embedded rendering.

Provisional risk is low. The primary cascade risk is accidentally loading the
feed from a per-holder loop or making optional score context a prerequisite for
the provider view; AST/request-count and render-state tests must close both.

## Phase 4I — Analytics DB ranked fundamental defaults

### Accepted boundary

- Migrate only the ranked-candidate source used by
  `ui/analytics_db.py::_ranked_tickers` to the existing strict ranked feed.
  Its only consumer is the default value for the manual fundamental-ticker
  refresh field in `_render_refresh_center`.
- Load the ranked feed exactly once per Analytics DB rerun, including the
  database-read-error branch, and derive at most ten already validated,
  ordered, unique tickers in memory. Do not call once per ticker.
- The API result is authoritative. Available-empty produces an empty default;
  unavailable and every client failure also produce no default but display
  only fixed sanitized guidance that manual ticker entry remains available.
  Never read local `ranked_candidates.json` as fallback.
- Preserve every maintenance operation and its current boundary: core-source
  refresh, Analytics DB rebuild, fundamental refresh, status/log reads,
  DuckDB/Parquet access, subprocess execution, session state, validation, and
  error handling remain unchanged. This phase does not make the Analytics DB
  page as a whole API-only.

### Expected files and gates

- `ui/analytics_db.py`, a new focused
  `scripts/test_ui_analytics_ranked_api.py`, backend-boundary/navigation/
  fixture contracts, inventory/user guide, Make test inventory, and this
  receipt/journals.
- No API/OpenAPI/model/client transport, analytics schema, refresh command,
  environment variable, provider, writer, deployment, or other ranked
  consumer changes.
- Fail-first tests must cover ordered truncation, available-empty,
  authoritative unavailable, every fixed-client failure class, no local
  ranked read, exactly one request in both render branches, and continued
  manual fundamental refresh behavior.

Risk is low-to-medium because this page still owns intentionally local
maintenance/write boundaries. The mitigation is to inject only the validated
ranked result into the pure default-selection helper and leave every button
handler and refresh function byte-stable.

## Planned order and continuation

1. Review this plan and the fresh baseline for blocking issues.
2. Execute and fully verify Phase 4G before starting Phase 4H.
3. Re-review the Phase 4H boundary against the post-4G diff, then execute only
   if no blocker remains.
4. Re-review the Phase 4I boundary against the post-4H diff, then execute only
   if no blocker remains.
5. After each phase run its focused test plus shared candidate, boundary,
   navigation, and fixture gates as relevant. At the end compare the actual
   diff to this accepted scope, verify real artifact hashes were not modified,
   run compilation/Python 3.10 AST/whitespace checks and complete `make test`.
6. Queue Phase 4J as an Industry Roles read/write-boundary audit before any
   migration. Queue Phase 4K as prioritization of remaining scored-candidate
   consumers; neither is authorized for implementation by this plan.

## Implementation receipt

### Actual scope

| Surface | Implemented change |
|---|---|
| Phase 4G | `ui/sys_schedules.py` now reads the ranked portion of the candidate-refresh result through the fixed ranked-feed client, reuses one result for duplicate visible cards, preserves the independent Money Flow artifact, and renders ranked failure plus valid Money Flow as a safe partial state. |
| Phase 4H | `ui/institutional_holdings.py` now loads the scored feed once, filters the validated snapshot in memory, and exposes only `institutional`, `verdict`, and `key_signals`; provider/manual/embedded behavior remains independent. |
| Phase 4I | `ui/analytics_db.py` now loads the ranked feed once per page execution and derives the first ten validated tickers for the manual fundamental-refresh default; every local maintenance, database, writer, and subprocess boundary is preserved. |
| Focused tests | Added `scripts/test_ui_schedules_candidate_api.py`, `scripts/test_ui_institutional_score_api.py`, and `scripts/test_ui_analytics_ranked_api.py`, all fail-first before their respective implementation. |
| Shared contracts | Updated Make inventory, backend-boundary/navigation coverage, the exact Phase 4H UX diagnostic successor receipt, and the Institutions/Analytics fixture counters from local JSON reads to fixed candidate-feed calls. |
| Documentation | Updated the operator guide and endpoint/artifact inventory to identify 13 API-only consumers and to describe all three changes as narrow slices rather than whole-page separation. |

No API DTO, projector, route, OpenAPI, fixed-client transport, dependency,
deployment, provider, writer, or compatibility endpoint changed. The planned
`ui/_read_api.py` adapter contingency was not needed.

### Verification evidence

| Gate | Result |
|---|---|
| Schedules candidate focused suite | 4/4 passed |
| Institutional scored-context focused suite | 4/4 passed |
| Analytics ranked-default focused suite | 5/5 passed |
| Candidate feed, fixed-client, Fund Catalog, Analytics runtime, Schedules reflection, and UX safety focused regressions | 8/8, 12/12, 16/16, 4/4, 5/5, and 5/5 passed |
| Backend boundary | 12/12 passed |
| Dashboard/navigation | 55/55 passed |
| UX exact source contract | 19/19 passed after registering the Phase 4H one-for-one `st.expander` fingerprint replacement |
| UX fixture matrix | 26/26 passed after replacing the Institutions/Analytics local-read counters with one scored/ranked fixed-client call |
| Deployment artifact contract | 18/18 passed |
| Complete repository suite | `make test` passed with exit code 0 |
| Static gates | `compileall`, `tabnanny`, Python 3.10 AST (8/8), and scoped whitespace checks passed |
| Persisted artifact integrity | Ranked `ca85c803...b5ea`, scored `6af37543...7f99`, and Money Flow `96ed8334...1731` remained byte-identical |

An additional selector-authority suite that is not part of `make test` remains
24/27 in the shared worktree. One failure requires a separate frozen
capture-stack reauthorization after legitimate `scripts/ui_ux_fixtures.py`
changes; two are the already-present unknown whole-file state for
`ui/radar.py`. These are not runtime failures in the three migrated consumers,
and changing that independent UX authority is outside this accepted plan.

### Diff-to-plan and five-axis review

- **Callers:** only the three planned internal candidate consumers changed;
  `app.py`, `ui/institutions.py`, and `ui/stock_checkup.py` keep their entry
  points and adjacent providers.
- **Tests:** all three fail-first suites plus the planned L2 boundary,
  navigation, UX inventory, and fixture ownership gates were updated. The two
  full-suite failures found during verification were stale exact authorities
  caused by this change and were corrected without weakening their contracts.
- **Types/contracts:** existing fixed result unions and public DTOs were
  sufficient; compatibility and OpenAPI contracts are unchanged.
- **Configs:** only the Make test inventory changed. Environment, Compose,
  deployment, dependency, and runtime settings are unchanged.
- **Docs:** operator, inventory, plan/receipt, and skill/project records are
  synchronized. No unexplained scope drift remains.

Verdict: **ready**. Phase 4G, 4H, and 4I are the eleventh through thirteenth
API-only consumer slices; this does not claim that the three composite pages,
or the frontend and backend as a whole, are fully separated.

## Next plan queue

1. **Phase 4J — Industry Roles read/write-boundary audit:** inventory the
   state read, role catalog reads, edit/save mutations, fixture counters, and
   ownership before deciding whether any read-only sub-slice can move. Review
   and accept a separate plan before implementation.
2. **Phase 4K — Remaining scored-consumer prioritization:** compare
   `us_screener`, `us_options`/Options surfaces, analyst views, and sector or
   checkup consumers by field fit, N+1 risk, provider coupling, and mutation
   boundaries; select only the next narrow slice.
3. **Phase 4L — Global separation re-audit:** after 4J/4K, recalculate direct
   UI-to-artifact/provider bindings, API-only consumer count, shared-helper
   fan-out, and deployment/process gaps, then produce the next ordered plan.
