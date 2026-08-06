# Streamlit Fund Catalog API Consumer Phase 2H Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v0.7 |
| Status | Implemented and verified; post-implementation findings closed |
| Author | Codex |
| Reviewer | Repository maintainer / independent implementation reviewers |
| Audience | Maintainers of the Streamlit-to-loopback read boundary |
| Related endpoint phase | `2026-07-14-fastapi-fund-catalog-phase2c.md` |
| Prior consumer phase | `2026-07-15-streamlit-ai-updates-api-phase2g.md` |

## Goal

Make the existing **機構持倉 · 機構 → 它持有什麼** view consume the
completed `GET /api/v1/institutions/funds` endpoint for its curated quick-pick
catalog without making the page less resilient.

Success means the catalog is API-first, expected artifact failures remain safe
UI states, client failures use a visible strict local fallback, manual CIK lookup
always remains usable, and existing SEC EDGAR fetch/cache, lag warnings, metrics,
and holdings table behavior remain unchanged.

## Why This Is the Next Slice

Phase 2G is independently reviewed and has no remaining blocking, HIGH, or
MEDIUM issue. The fund catalog is the smallest remaining end-to-end consumer
slice:

- Phase 2C already provides a fixed, parameterless, strict public endpoint.
- `ui/institution_portfolio.py` is the only direct Streamlit consumer of the
  curated catalog.
- The source has no runtime writer, provider call, path override, private field,
  or mutation.
- IV history has multiple consumers and mismatched ticker sanitization; signal
  artifacts have multiple consumers and DTOs that do not yet cover all fields
  used by the UI.

This phase migrates only the quick-pick catalog. Live 13F holdings remain a
direct SEC EDGAR provider read, and the inverse stock-to-holders view remains a
separate yfinance-backed consumer.

## Architecture

Extend `ui/_read_api.py` with a fixed fund-catalog client while retaining the
Phase 2F/2G transport boundary. The existing private response reader continues
to own only client construction, response-stream lifecycle, HTTP/header gates,
and decoded-body cap. The fund adapter owns strict DTO, source ID, and metadata
validation.

The request is bounded by an endpoint-specific exact 512 KiB decoded-body cap.
A maximum compact schema-valid 100-entry envelope using 100 unique 120-codepoint
all-astral names, 200-codepoint all-astral notes, and 10-digit CIKs serializes to
387,523 bytes with ASCII JSON escaping, leaving 136,765 bytes for permitted JSON
whitespace. The test MUST strict-validate that fixture before
serialization and prove the entry count, unique keys, and maximum field lengths;
exact-cap and cap-plus-one behavior are also locked by tests.

The public fund client returns exactly one of:

- `FundCatalogApiAvailable(options=tuple[FundCatalogOption, ...])`
- `FundCatalogApiUnavailable(reason=<artifact reason>)`
- `FundCatalogApiFailure(reason=<stable client reason>)`

`FundCatalogOption` is a frozen value object containing `display_name`, `cik`,
and `note`. The tuple preserves JSON object insertion order without exposing a
mutable dictionary or a mutable DTO. `FundCatalogApiFailure` reuses the exact
Phase 2F/2G `ClientFailureReason` union:
`transport_error`, `deadline_exceeded`, `http_status`,
`invalid_media_type`, `invalid_cache_control`, `response_too_large`, or
`invalid_envelope`.

The page resolver distinguishes four states: API available, authoritative API
unavailable, local fallback, and all catalog sources unavailable. A valid API
`available=false` envelope is authoritative. Only a typed client failure invokes
`read_artifact(ARTIFACTS["institutions.funds"])`, followed by strict
`FundCatalogData` parsing. No raw exception, body, URL, absolute path, or source
diagnostic enters state or UI.

For a quick pick, the page sends the API/fallback entry's digit-string CIK to
`_load()` exactly as received—including leading zeroes—while keeping the display
name in the spinner and user-facing failure copy. `scripts/edgar_13f.py` still
performs its fail-soft local catalog read before branching, but numeric input no
longer depends on that catalog's contents. Manual CIK takes precedence and
continues to call `_load()` directly in every catalog state.

The SEC response normally supplies an institution name. For the existing
fail-soft edge case where that name is absent and the provider echoes the query
CIK into `data["fund"]`, the page copies the returned dictionary and substitutes
the selected quick-pick display name for presentation only. It never mutates a
cached provider object and never substitutes a catalog name for a manual CIK.

The browser does not call FastAPI. This remains a server-side
Streamlit-to-loopback request and adds no CORS or non-loopback exposure.

## Requirements

- `REQ-2H-001`: The client MUST issue exactly
  `GET http://127.0.0.1:8000/api/v1/institutions/funds`, with no caller-supplied
  host, port, path, query, source ID, cap, timeout, or CIK.
- `CFR-2H-001`: The client MUST retain `trust_env=False`,
  `follow_redirects=False`, exact 0.25-second connect/read/write/pool inactivity
  timeouts, `Accept: application/json`, and a Python-3.10-compatible cancellable
  1.0-second whole-request deadline.
- `CFR-2H-002`: HTTP 200 is accepted only with an `application/json` media type,
  a case-insensitive `no-store` cache directive, a decoded body no larger than
  exactly 512 KiB, and strict validation through
  `ArtifactAvailable[FundCatalogData] | ArtifactUnavailable`.
- `CFR-2H-003`: Every accepted envelope MUST use
  `meta.sourceId=institutions.funds`, null `meta.asOf`, and null
  `meta.generatedAt`.
- `REQ-2H-002`: Available options MUST preserve source order and all public
  display-name, CIK, and note values. `_note`, unknown fields, invalid names,
  invalid CIKs, or invalid notes MUST become `invalid_envelope`, never partial UI.
- `REQ-2H-003`: A valid API `available=false` response for `missing`,
  `invalid_json`, `invalid_shape`, or `unreadable` is authoritative. The page MUST
  NOT bypass it locally, and MUST still render a usable manual CIK input.
- `REQ-2H-004`: Connect/read failures, deadline expiry, non-200 responses,
  redirects, invalid headers, oversized bodies, malformed JSON, or contract drift
  MUST NOT crash the page and MUST map to the existing seven stable client reasons.
- `REQ-2H-005`: Only client failures trigger local fallback. The fallback MUST use
  `read_artifact(ARTIFACTS["institutions.funds"])` and strict
  `FundCatalogData` parsing; it MUST NOT duplicate or weaken source validation.
- `CFR-2H-004`: Client-failure fallback MUST be visible through generic
  Traditional Chinese copy containing no raw diagnostic. If both catalog sources
  fail, the page MUST state that quick pick is unavailable while leaving manual
  CIK lookup usable.
- `CFR-2H-005`: The fallback logger MAY emit only a fixed event string and the
  exception class name. Exception messages, response/source bodies, tracebacks,
  paths, environment values, and URLs MUST NOT be logged.
- `CFR-2H-006`: Fund catalog API failures and fallback results MUST NOT be
  negatively cached. Every render/rerun performs a fresh catalog request. Existing
  EDGAR success-only one-day caching and failure retry behavior remain untouched.
- `REQ-2H-006`: Quick picks MUST pass their catalog-provided numeric CIK to
  `_load()` as the exact string, including leading zeroes. Manual CIK MUST take
  precedence. Source order, note formatting, first option auto-selection, spinner
  label, lag banner, four metrics, holdings table, and empty/failure holdings
  behavior MUST remain. If a quick-pick result has a missing `fund` or merely
  echoes the queried CIK, a copied result MUST use the friendly selected display
  name; a manual-CIK result MUST remain untouched.
- `REQ-2H-007`: Rendering the default inverse **機構持股 · 股票 → 誰持有它**
  child view MUST NOT eagerly call the fund catalog API.
- `CFR-2H-007`: This phase MUST NOT redesign the UI/UX or fix unrelated inherited
  UI issues. Navigation, information architecture, styling, responsive behavior,
  and unrelated copy remain unchanged except for accurate catalog state notices.

## Catalog UI States

| State | Quick-pick source | UI behavior |
| --- | --- | --- |
| API available, non-empty | API | Existing source-ordered selector; selected entry queries its CIK |
| API available, empty | API | Empty selector plus usable manual CIK input |
| API valid unavailable | None | Safe reason-specific catalog notice; no local bypass; manual CIK remains usable |
| API client failure + valid local catalog | Local fallback | Sanitized warning plus normal selector and manual CIK |
| API client failure + valid empty local catalog | Local fallback | Warning, empty selector, and usable manual CIK |
| API client failure + invalid/missing local catalog | None | Warning plus all-catalog-sources-unavailable notice; manual CIK remains usable |

Authoritative unavailable copy is fixed and tested for every reason:

| Reason | Safe detail |
| --- | --- |
| `missing` | 找不到投資大戶快選資料。 |
| `invalid_json` | 投資大戶快選資料尚未完整寫入或 JSON 格式無效。 |
| `invalid_shape` | 投資大戶快選資料格式不符合預期。 |
| `unreadable` | 投資大戶快選資料目前無法讀取。 |

## Scope and Affected Files

### Create

- `scripts/test_ui_fund_catalog_api.py` — focused client, resolver, recovery,
  selector-to-CIK mapping, AppTest behavior, and child-view isolation tests.
- This plan document.

### Modify

- `ui/_read_api.py` — strict fixed fund-catalog adapter, cap, immutable outcomes,
  deadline wrapper, and sync entry point.
- `ui/institution_portfolio.py` — API-first catalog state, strict local fallback,
  safe notices, manual-CIK-preserving rendering, and display-name-to-CIK mapping.
- `scripts/test_dashboard_navigation.py` — static data-flow and preserved behavior
  contract.
- `Makefile` — add the focused Phase 2H test to `make test`.
- `docs/USER_GUIDE.md` — document three API-first consumers, fixed-port/fallback
  behavior, and the partial institutional-page boundary.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — mark only the catalog
  Streamlit consumer API-first.
- `.agents/PROJECT.md`, `.agents/lens.md`, `.agents/scribe.md`, and
  `.agents/builder.md` — record decisions and verification evidence.

### Regression-only; do not edit unless a failing test proves it necessary

- `scripts/test_ui_read_api.py`
- `scripts/test_ui_ai_updates_api.py`
- `scripts/test_api.py`
- `scripts/edgar_13f.py`
- `ui/institutions.py`

### Do not modify

- `api/**`, checked-in OpenAPI, `content/funds.json`,
  `ui/institutional_holdings.py`, app navigation, providers, dependencies,
  deployment/systemd, CORS/auth/bind settings, Docker, or CI topology.

The working tree contains cumulative Phase 1-2G changes and unrelated user work.
The pre-implementation baseline is
`/tmp/surge-phase2h-baseline-20260715/`. SHA-256 values were captured for every
existing affected file; this plan and the focused test were initially absent.
Final review MUST use baseline-to-current diffs for overlapping files and
`/dev/null`-to-current diffs for new files. Repository `git diff` alone is not
sufficient because several affected files were already modified or untracked.

## Test-First Implementation Tasks

### 1. Lock the fixed client contract

- Add red tests for exact method/URL, absent query, JSON accept header, one request,
  timeout configuration, available source-order/value preservation, and valid
  empty data.
- Lock `load_schedules`, `load_ai_updates`, and `load_fund_catalog` to exactly one
  keyword-only optional `transport` parameter. Keep `_read_fixed_json` at exactly
  its existing three required keyword-only parameters.
- Assert exact source ID and null metadata; reject wrong metadata, `_note`, unknown
  fields, malformed models, or wrong source IDs.
- Assert all four unavailable reasons and the complete seven-value client failure
  mapping.
- Prove the maximum escaped 100-entry schema-valid compact envelope fits and is
  accepted. Strict-validate the generated fixture before serialization and assert
  100 unique maximum-length keys, 200-codepoint notes, and 10-digit CIKs. Then
  prove an exact 512 KiB valid body is accepted and cap-plus-one is rejected with
  response-stream cleanup.
- Mirror immutable-result and immediate-recovery checks from prior consumer phases.
- Register every `test_*` function explicitly in the focused script's manual
  `main()` runner, assert the discovered test-name set equals the executed set, and
  print the exact pass count so neither Gate 1 nor `make test` can silently omit a
  focused case.

### 2. Lock page resolution and behavior

- Prove authoritative unavailable never reads locally.
- Prove only client failure uses the exact registry fallback, with strict model
  validation for available, valid empty, unavailable, invalid model, and unexpected
  fallback exception outcomes.
- Capture fallback logging for a secret-bearing exception and prove only fixed copy
  plus the class name reaches logs; prove the secret does not reach state or UI.
- AppTest all six catalog states and prove the CIK text input remains present and
  callable in empty/unavailable states. Every portfolio AppTest MUST patch
  `ui.institution_portfolio._load`; the default inverse-view test MUST patch
  `ui.institutional_holdings._load`. No focused test may call SEC EDGAR, yfinance,
  or any other external provider.
- Prove API/fallback display names and notes retain source order and formatting,
  the first option remains selected, quick picks call `_load()` with the exact
  matching CIK including leading zeroes, manual CIK takes precedence, and the
  spinner/failure copy uses the friendly label. Because spinner output is
  transient, record its context label through a patched `st.spinner` or test a
  pure target/label helper instead of inspecting the final AppTest tree.
- Prove no target avoids EDGAR. Add deterministic provider stubs for `_load() ->
  None`, a successful filing with `holdings=[]`, and a successful non-empty filing;
  assert the existing warning/info copy, lag severity, exactly four recorded
  `_shared.metric_card` calls, and one holdings dataframe. Do not rely on
  `app.metric`, because the shared cards render custom markup.
- Prove the friendly quick-pick name is restored on a copied provider result when
  `fund` is missing or equals the queried CIK, while a real SEC name and every
  manual-CIK result remain unchanged. Also prove numeric provider execution still
  works when its internal `load_funds()` returns an empty mapping.
- Prove the default inverse child view does not call `load_fund_catalog`.
- Exercise both unexpected local-fallback paths—`read_artifact` raising and strict
  `FundCatalogData.model_validate` raising—and prove only the fixed event plus
  exception class reaches logs. Sentinel secrets MUST be absent from logs, state,
  and rendered UI.
- For every state test, assert exact notices and provider calls rather than only an
  empty `AppTest.exception`. Use `text_input.set_value(...).run()` to prove manual
  CIK execution after empty/unavailable catalog states, and prove a subsequent
  rerun re-requests and recovers from an earlier client failure.

### 3. Implement the client and page

- Add the endpoint-specific adapter and immutable result types without weakening
  the shared response reader or changing existing consumer contracts.
- Add the page catalog-state union, strict local fallback, safe notices, and
  separate query-target/display-label resolution.
- Do not modify `scripts/edgar_13f.py`; passing a numeric CIK is sufficient to
  decouple quick-pick execution from its local name lookup.

### 4. Update static contracts and documentation

- Register the focused suite in `make test` and add static assertions for the
  fixed URL, strict fallback, CIK mapping, manual input, and partial migration.
- Update the guide's startup section, consumer count, architecture diagram, page
  behavior, fixed-port fallback, and Compose limitation.
- Mark only the curated selector catalog API-first; do not claim that EDGAR,
  yfinance, or the whole institutional page is API-backed.

## Verification Gates

Run, in order:

1. `.venv/bin/python scripts/test_ui_fund_catalog_api.py`
2. `.venv/bin/python scripts/test_ui_read_api.py`
3. `.venv/bin/python scripts/test_ui_ai_updates_api.py`
4. `.venv/bin/python scripts/test_dashboard_navigation.py`
5. `.venv/bin/python scripts/test_artifact_loader.py`
6. `.venv/bin/python scripts/test_api.py`
7. `.venv/bin/python -m compileall -q ui api scripts/test_ui_fund_catalog_api.py`
8. Python 3.10 grammar gate for all Phase 2H Python files.
9. `make test`
10. `.venv/bin/python -m pip check`
11. `git diff --check`
12. Collision-safe real-Uvicorn/AppTest smoke on fixed port 8000. Keep only the
    fund catalog API live and stub both holdings providers. The positive oracle
    MUST directly prove `load_fund_catalog()` returns `FundCatalogApiAvailable`,
    the expected API selector/options render, and both the local-fallback and
    all-catalog-sources-unavailable notices are absent. Keep the patched local
    `read_artifact` mock and explicitly call `assert_not_called()` after render;
    do not rely on a raising side effect because the page's fail-soft exception
    boundary intentionally catches it. Start and stop only an owned process. If 8000 is occupied,
    use it only when a direct route/source-ID/`no-store` probe matches this app;
    otherwise record an explicit optional skip. A local-fallback render never
    counts as a live-API PASS.

Before completion, compare actual baseline-to-current and new-file diffs against
the affected-file list, then perform fresh correctness, regression, test-scope,
maintainability, diagnostic-leak, and scope-drift reviews. Blocking findings MUST
be fixed.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Catalog unavailable disables the entire page | Render state notice before controls; always keep manual CIK input active |
| API quick pick still depends on local catalog name lookup | Resolve selected display name to its API-provided CIK before `_load()` |
| Shared client changes regress schedules/AI Updates | Keep helper signature/behavior fixed and run both focused regression suites |
| Legal maximum catalog exceeds cap | 512 KiB derived from maximum-valid escaped payload and locked at boundary tests |
| API unavailable is incorrectly bypassed | Separate unavailable from failure; assert no local read for all four reasons |
| Invalid local data becomes partially visible | Exact registry loader plus strict public DTO; no permissive dict rendering |
| Raw diagnostic leaks through logs/state/UI | Stable reasons, class-only logger, secret sentinel tests |
| Outage becomes sticky | No Streamlit or response cache; consecutive-result recovery test |
| Default inverse view adds an unnecessary API request | Child-view AppTest asserts lazy view dispatch |
| Phase is mistaken for full holdings migration | Explicit partial-boundary copy in plan, guide, inventory, and static tests |
| Docker fixed-port behavior surprises users | Preserve visible strict fallback and document Streamlit-only Compose topology |
| Dirty tree loses or misattributes prior work | Baseline copies/hashes and per-file final diff; never reset unrelated changes |
| UI redesign scope leaks into migration | Exact affected files and `CFR-2H-007`; separate UI/UX backlog |
| AppTests accidentally call live holdings providers | Patch portfolio and inverse-view `_load` functions in every render test; smoke keeps only catalog API live |
| Numeric CIK weakens friendly metric label | Copy provider result and restore selected name only when the provider name is missing/echoed CIK |

## Rollback

Remove the fund-catalog additions in `ui/_read_api.py`, restore the prior guarded
local `_funds()` in `ui/institution_portfolio.py`, remove the focused test and
Makefile entry, and revert only the Phase 2H documentation updates. No API,
OpenAPI, source artifact, writer, provider, cache, deployment, dependency, or data
migration rollback is required.

## Traceability

| Requirement | Implementation target | Verification |
| --- | --- | --- |
| `REQ-2H-001`, `CFR-2H-001`, `CFR-2H-002` | Fixed client and shared response reader | Exact request/config/signature and cap tests |
| `CFR-2H-003`, `REQ-2H-002` | Strict fund adapter and ordered frozen options | Metadata/invalid-envelope/order/value/immutability tests |
| `REQ-2H-003`, `REQ-2H-004` | Typed unavailable/failure outcomes | Four-reason no-fallback and seven-reason mapping matrices |
| `REQ-2H-005`, `CFR-2H-004`, `CFR-2H-005`, `CFR-2H-006` | Strict uncached page resolver | Fallback, recovery, logging, state, and UI sentinel tests |
| `REQ-2H-006` | Query-target/display-label separation and copied display normalization | Exact/leading-zero CIK, manual precedence, friendly-name, and preserved-render AppTests |
| `REQ-2H-007`, `CFR-2H-007` | Existing lazy child-view dispatch and bounded page edit | Default-view isolation and static scope tests |

## Plan Review Record

### Review 1 — v0.1

- Correctness/security review: no BLOCKING or HIGH finding; corrected the maximum
  escaped envelope calculation and added friendly-name preservation for the rare
  provider-name-missing path.
- Test/feasibility review: found one BLOCKING issue—render tests could call live
  SEC EDGAR/yfinance providers. v0.2 requires provider stubs in every AppTest and
  narrows the live smoke to the local fund endpoint.
- Also added manual-runner completeness, exact leading-zero CIK preservation,
  deterministic empty/failure/success holdings oracles, two fallback-exception
  paths, and a positive live-API oracle.

### Review 2 — v0.2

- Correctness/security re-review: PASS.
- Test/feasibility re-review: no BLOCKING or HIGH finding. Tightened the live
  smoke so it explicitly asserts the local artifact mock was not called, the API
  selector/options rendered, and neither degraded catalog notice appeared; a
  raising mock alone could otherwise be swallowed by the intentional fail-soft
  exception boundary.

### Review 3 — v0.3

- Test/feasibility final re-review: PASS. No unresolved BLOCKING, HIGH, or MEDIUM
  finding remains.

## Implementation Evidence

- `ui/_read_api.py` now performs one fixed, uncached fund-catalog request with the
  existing proxy/redirect/time/deadline/header controls, an exact 512 KiB decoded
  cap, strict `FundCatalogData` envelope/source/metadata parsing, and frozen
  source-ordered option/outcome values.
- `ui/institution_portfolio.py` now distinguishes API available, authoritative
  unavailable, visible strict local fallback, and all-catalog-sources-unavailable.
  Manual CIK remains active in every catalog state. Quick picks pass the exact
  catalog CIK—including leading zeroes—to EDGAR while preserving a friendly name
  without mutating cached provider results.
- The existing selector order/note formatting, first auto-selection, spinner and
  failure labels, lag warning, four metrics, empty-holdings state, and holdings
  table remain. The default inverse institutional child does not call the catalog
  API. SEC EDGAR/yfinance providers and their caches were not modified.
- The focused suite was created test-first: it failed on the missing public loader,
  then passed 16/16 after implementation and closure hardening. It covers the four unavailable reasons,
  seven stable client failures, maximum/exact-cap/true-cap-plus-one bodies, strict
  DTO/metadata drift, direct client recovery, strict registry fallback, class-only
  logs, leading-zero/manual CIK behavior, all catalog states, holdings rendering,
  provider isolation, a non-empty local-fallback selector-to-CIK integration,
  lazy child dispatch, immutability, and Python 3.10 grammar.
  A targeted mutation changing the production cap to `512 KiB + 1` is killed by
  the cap test.
- Final regression evidence: `make test` PASS; focused fund catalog 16/16,
  schedules consumer 12/12, AI Updates consumer 17/17, dashboard 48/48, artifact
  loader 14/14, and API 36/36. `compileall`, the Python 3.10 AST gate,
  `pip check`, and `git diff --check` also pass.
- Port 8000 was already occupied by an unowned Python listener, so no process was
  stopped and the owned-listener lifecycle subtest was skipped. A direct probe
  independently confirmed HTTP 200, `Cache-Control: no-store`, and
  `sourceId=institutions.funds`; a supplementary live client/AppTest smoke then
  rendered the expected selector, asserted the local artifact fallback was never
  called, and kept the holdings provider stubbed offline.
- Baseline-to-current review uses
  `/tmp/surge-phase2h-baseline-20260715/`; every code, test, documentation, and
  journal change is in the accepted affected-file list. No API/OpenAPI, source
  catalog, EDGAR/yfinance provider, navigation, deployment, Docker, dependency,
  or unrelated UI file changed in Phase 2H.
- Independent correctness/security post-review: PASS. Test/scope review found no
  BLOCKING or HIGH issue; its cap-boundary, client-recovery, strict-matrix, and
  evidence-record findings were fixed before closure. The focused finding-closure
  re-review returned PASS. A final baseline audit then found one LOW evidence gap
  for the non-empty local-fallback AppTest; that exact integration test was added
  and the focused 16/16, dashboard 48/48, and diff gates passed.
