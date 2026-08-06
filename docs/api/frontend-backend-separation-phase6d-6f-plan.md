# Phase 6D-6F Frontend/Backend Separation Plan

- **Status:** audited and accepted for implementation with Phase 6A-6C
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parents:**
  - `docs/api/frontend-backend-separation-phase5x-5z-plan.md`
  - `docs/api/frontend-backend-separation-phase6a-6c-plan.md`

## Objective

Move only the persisted COT report reads behind the loopback read API while
preserving on-demand report generation as a local authenticated mutation:

1. **Phase 6D:** add a strict server-enumerated COT report catalog and strict
   date-selected report-detail contract for the Markdown/verified JSON pair.
2. **Phase 6E:** add immutable bounded clients and reuse the catalog's latest
   report date for the Schedules `cot` result card. This becomes the
   forty-eighth API-only slice after Continuation Validation.
3. **Phase 6F:** consume the catalog once and the selected detail once in
   `ui/us_cot.py`, preserving the verified audit panel and report sections.
   This becomes the forty-ninth API-only slice.

Phase 6A-6C remains the forty-seventh slice and is implemented in the same
verified batch. CFTC/yfinance retrieval, Codex authentication, LLM analysis,
manual generation, atomic writes, `_last_error.txt`, and every provider or
mutation remain outside the read API.

## Entry evidence and contract decisions

- `ui/us_cot.py` currently enumerates `reports/cot/*.md`, reads the selected
  Markdown directly, and reads the sibling `<date>.verified.json` through
  `_shared.load_json`. `ui/sys_schedules.py::_latest_cot_result()` separately
  enumerates the same Markdown directory for only the newest filename.
- `scripts/cot_es.py` writes the verified sidecar before the Markdown and uses
  the Markdown file as the publication gate. Dry-run and failed generation do
  not publish a partial selectable report.
- The catalog therefore enumerates only exact real-date Markdown publication
  names, newest first, with a bounded count. An absent directory is
  `available=false, reason=missing`; an existing empty directory is an
  authoritative available-empty catalog. Non-date files such as
  `_last_error.txt` are ignored and never exposed.
- The detail route accepts only an exact real calendar date and requires both
  `<date>.md` and `<date>.verified.json`. Missing, unreadable, malformed,
  partial, oversized, or invariant-invalid pairs fail soft without another
  date fallback.
- The public detail preserves the selected report date, bounded Markdown, and
  the complete currently displayed verified audit shape. The verified shape is
  closed and enforces COT position arithmetic, OHLC/range coherence, report/
  COT date binding, retrieved timestamp validity, stale-flag parity, and
  Tuesday-to-Friday price/delta parity.
- `_last_error.txt`, filesystem paths and metadata, prompt/model/auth data,
  provider responses beyond the verified sidecar, and arbitrary sidecar fields
  never cross the contract.
- Markdown remains text data. Before any `st.markdown` call, the frontend strips
  control characters, escapes raw HTML, and removes inline link/image targets;
  `unsafe_allow_html` is never enabled.

## API design

### Catalog

- **Method/path:** `GET /api/v1/reports/cot`
- **Source ID:** `reports.cot.catalog`
- **Data:** `{reports: [{report_date: YYYY-MM-DD}, ...]}` in unique descending
  order, maximum 520 reports.
- **Metadata:** `asOf` equals the newest date or `null` for available-empty;
  `generatedAt` is always `null`.
- **Errors:** expected collection failures use the existing HTTP 200 unavailable
  envelope. No query parameters, filesystem paths, or pagination are accepted.

### Detail

- **Method/path:** `GET /api/v1/reports/cot/{report_date}`
- **Source ID:** `reports.cot.detail`
- **Identifier:** exact ISO calendar date; invalid dates return the existing
  sanitized RFC 9457-compatible 422 response before filesystem selection.
- **Data:** strict `{report_date, markdown, verified}`; Markdown is non-empty and
  at most 256 KiB, and the verified JSON source is capped at 64 KiB.
- **Metadata:** `asOf` equals both the selected path date and
  `data.report_date`; `generatedAt` equals the verified `price.retrieved_at`
  instant. Unavailable metadata retains the selected `asOf` but has
  `generatedAt=null`.
- **Caching:** `Cache-Control: no-store`; no redirect and no alternate port.

Both operations are additive under `/api/v1`. The batch advances the draft
document once from `1.18.0-draft` to `1.19.0-draft`; it introduces no breaking
response change to existing operations. The loopback Host/peer and CORS policy
remains the authorization boundary. No new auth, rate-limit, dependency, or
deployment-topology change is needed; bounded directory/item/body limits are
the resource-consumption controls for these local GETs.

## Phase execution

### Phase 6D — strict contract and server reads

1. Add fail-first source/model/route/OpenAPI tests for catalog ordering, empty,
   missing, cap, ignored non-date files, strict detail pair projection, both
   missing sides, unreadable/invalid JSON, exact fields, bounds, arithmetic,
   date/timestamp parity, recovery, privacy, 422, no-store, and examples.
2. Define strict DTOs/envelopes in `api/models.py`.
3. Add bounded catalog and pair readers in `api/artifacts.py` without adding
   the dynamic detail to the fixed `ARTIFACTS` registry.
4. Add both explicit routes and exact generated examples in `api/main.py`.
5. Define the static operations, parameters, schemas, envelopes, responses,
   and `available`/`empty`/`unavailable` examples in
   `docs/api/quant-radar-v1.openapi.yaml` before implementation completion.

### Phase 6E — clients and Schedules latest metadata

1. Add frozen `available | unavailable | failure` catalog outcomes and frozen
   `available | unavailable | failure | invalid_date` detail outcomes in
   `ui/_read_api.py`.
2. Use the fixed catalog URL, validated date-derived detail URL, the existing
   one-second whole-request deadline, a 64 KiB catalog response cap, and a
   512 KiB detail response cap. Enforce JSON media type, no-store, source ID,
   strict envelopes, metadata parity, and the complete shared failure
   vocabulary. The next call must recover after a failure.
3. Replace only `_latest_cot_result()` with one catalog call. Available-empty is
   authoritative; unavailable/failure uses fixed safe text and never enumerates
   `reports/cot` locally.
4. Add `cot` to the existing per-render result cache so duplicate visible COT
   schedule cards reuse one catalog result.

### Phase 6F — COT persisted presentation

1. Keep `_render_generate()`, Codex auth/session flow, provider imports, error
   messages, and rerun behavior local and unchanged except removing the obsolete
   local verified-JSON cache clear.
2. Load the catalog exactly once. On available-empty show the existing no-report
   guidance; on unavailable/failure show fixed safe retry guidance and return
   without local enumeration.
3. Populate the selectbox only from the server-enumerated dates and load the
   selected detail exactly once. Preserve verified stale warning, three metrics,
   audit JSON, preamble filtering, four tabs, and single-block fallback.
4. Render only sanitized API Markdown. Remove `_COT_DIR`, selected Markdown
   `Path.read_text`, selected `_shared.load_json`, and all persisted-read local
   fallback while preserving auth-log reads as a separate private operational
   boundary.

## Affected files

- Contract/server: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`
- Clients/consumers: `ui/_read_api.py`, `ui/sys_schedules.py`, `ui/us_cot.py`
- Focused tests: new Continuation and COT API/client/renderer/Schedules tests
- Global synchronization: `scripts/test_api.py`,
  `scripts/test_ui_backend_boundary.py`, `scripts/test_dashboard_navigation.py`,
  `scripts/test_ui_ux_contract.py` only if an exact diagnostic receipt changes,
  `scripts/test_ui_ux_fixtures.py`, `scripts/ui_ux_fixtures.py`, `Makefile`,
  `docs/USER_GUIDE.md`, and
  `docs/api/fastapi-endpoint-artifact-inventory.md`
- Durable receipts: `.agents/gateway.md`, `.agents/builder.md`, and exactly one
  combined activity row in `.agents/PROJECT.md`

No producer, provider, prompt, LLM/Codex auth, report writer, report artifact,
dependency, service, Compose, deployment, schedule registry, or mutation file is
planned to change.

## Verification gates

- Focused Continuation and COT source/route/OpenAPI/client/renderer/Schedules
  suites, including red-to-green evidence.
- Existing `scripts/test_continuation_strength.py`, COT generation/auth,
  data-refresh, and deploy-publication contracts unchanged.
- API/OpenAPI, shared client, backend boundary, navigation, deterministic UX
  fixtures/inventory, deploy, and Docker contract suites.
- Exact catalog/date/pair/privacy/model invariants; invalid/oversized/recovery
  matrices; client URL/header/deadline/cap/metadata/frozen-outcome checks;
  sanitized Markdown and no-local-fallback checks.
- Python 3.10 AST, compileall, tabnanny, YAML/static-version parity,
  `git diff --check`, frozen producer hashes, and complete `make test`.

## Blocking-issue review

No unresolved blocking issue remains after two iterations.

- **Iteration 1:** separated persisted reads from generation/auth/provider/write
  paths, selected a server-enumerated ISO-date catalog plus bounded detail route,
  and rejected exposing paths, `_last_error.txt`, prompts, or provider internals.
- **Iteration 2:** closed partial-pair, path traversal, calendar-date, unbounded
  Markdown, response-size, sidecar arithmetic, raw-HTML/link, empty-catalog,
  duplicate Schedules request, and transient recovery gaps. The two endpoints
  are additive, the selected date is a bounded business identifier, and all
  retained mutations remain local.

Final verdict: **GO** for Phase 6A-6F in one contract-first implementation batch.

## Following queue

Phase 6G-6I should audit and migrate only the persisted Knowledge Graph
compiled-graph/catalog/detail presentation. Course source Markdown, image-derived
notes, refresh/compile actions, filesystem discovery, and all writers remain
local/Internal until that plan is separately reviewed and authorized.
