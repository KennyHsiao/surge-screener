# Fail-Soft FastAPI Read API Implementation Plan

**Status:** Implemented and independently reviewed; historical task checklist retained as the execution record

**Goal:** Add a local, read-only FastAPI boundary for the first six non-private artifacts while preserving Streamlit's existing fail-soft behavior and keeping private/runtime data inaccessible.

**Architecture:** Extract JSON reading into a configurable framework-neutral loader. Keep `ui._shared.load_json()` as the cached compatibility wrapper, including Python's existing JSON acceptance behavior, its `None` fallback, and its `.clear()` interface. FastAPI calls the same pure loader in strict object mode without negative caching through a fixed artifact registry and explicit routes. Expected artifact failures return an HTTP 200 unavailable envelope; unexpected application defects remain HTTP 500.

**Tech stack:** Python, FastAPI, Pydantic, Uvicorn, existing standalone Python test style.

**Planning artifacts:**

- `docs/api/fastapi-endpoint-artifact-inventory.md`
- `docs/api/quant-radar-v1.openapi.yaml`

The repository instructions request `superpowers:writing-plans` and an execution skill where available. Those skills are not installed in this environment; this plan follows the same test-first, task-by-task structure and must be executed only after acceptance.

## API Design Decisions

- Use URL versioning under `/api/v1`; health remains unversioned at `/healthz`.
- Use OpenAPI 3.1 because it matches FastAPI's generated schema and current tooling. A 3.2 document would create avoidable drift without adding a needed feature.
- The API is additive: there are no existing HTTP consumers to break, while Streamlit keeps its current loader surface.
- All batch-1 operations are safe, idempotent `GET` requests with no parameters, pagination, or idempotency keys.
- HTTP 200 unavailable envelopes represent the domain state of an expected scheduled-artifact slot. RFC 9457 problem responses are reserved for unexpected server defects, not missing optional outputs.
- Authentication, rate limiting, and CORS are intentionally absent only because the accepted runtime is loopback. They become mandatory design gates before non-loopback exposure.

## Scope

### Implementation batch 1

- `GET /healthz`
- `GET /api/v1/candidates/ranked`
- `GET /api/v1/candidates/scored`
- `GET /api/v1/signals/options-flow/latest`
- `GET /api/v1/signals/reversal-radar/latest`
- `GET /api/v1/signals/oversold-reversal/latest`
- `GET /api/v1/market-context/market-thesis/latest`

The complete inventory contains more endpoints that are eligible for the same Phase 1 architecture. They are deliberately not part of the first implementation batch, so the failure contract and security boundary can be verified before widening the registry.

### Out of scope

- Replacing or removing Streamlit.
- A React frontend or migration of page state.
- LAN/public exposure, TLS, API auth, reverse proxy, or a new systemd/Compose API service.
- Live yfinance, EDGAR, X, IBKR, LLM, or TradingView proxy calls.
- Refresh, reconcile, trade, approve, launch-job, upload, or other write endpoints.
- Reconciliation, portfolio positions, Risk Guard position details, watchlists, AI chats, reflections, logs, raw DuckDB/Parquet, arbitrary SQL, or arbitrary filesystem paths.
- Dated archives, ticker endpoints, aggregate endpoints, and DuckDB queries; these are later bounded batches.

## Requirements and Acceptance Criteria

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-1 | Fixed endpoint registry | Every artifact route maps to a server-owned `ArtifactSpec`; OpenAPI contains no generic file/path route. |
| FR-2 | Fail-soft artifact reads | Missing, malformed/half-written, invalid UTF-8, invalid root shape, and unreadable artifacts return HTTP 200 with `available=false`, `data=null`, and a stable reason. |
| FR-3 | Strict success definition | `available=true` requires valid finite JSON, an object root, and every registry-declared anchor with its declared container/item types. |
| FR-4 | Preserve domain flags | The API returns the complete source object, including flags such as `publishable`; API availability does not reinterpret domain readiness. |
| FR-5 | Preserve Streamlit behavior | `ui._shared.load_json(path)` retains the current `json.load()` acceptance semantics, returns parsed data or `None`, retains `@st.cache_data(ttl=60)`, and its `.clear()` remains callable. |
| FR-6 | No negative API cache | Once a missing or half-written artifact becomes valid, the next API request succeeds without waiting for Streamlit's 60-second cache. |
| FR-7 | Correct latest resolver | Market Thesis latest preserves the current date ordering and ready-over-regime-only precedence. No client filename or glob is accepted. |
| FR-8 | Independent health | `/healthz` reports process readiness even when every optional artifact is absent. |
| API-1 | Stable envelope | Success is `{available:true, reason:"ok", data:{...}, meta:{...}}`; expected unavailability is `{available:false, reason, data:null, meta:{...}}`. |
| API-2 | Stable reasons | Batch 1 reasons are exactly `missing`, `invalid_json`, `invalid_shape`, and `unreadable`. |
| API-3 | Correct status separation | Expected artifact states use 200. Unknown routes use 404. Unexpected bugs use 500 `application/problem+json`; they are not swallowed by the loader. |
| API-4 | Cache safety | Artifact responses include `Cache-Control: no-store`. |
| SEC-1 | No path traversal surface | No endpoint declares or reads a filesystem path, filename, glob, URL, SQL, or dynamic registry key. Extra query strings have no path-selection effect; traversal path probes return 404. |
| SEC-2 | Sensitive sources excluded | No route or registry item references reconciliation, watchlist, chat, position, auth, or log sources. |
| SEC-3 | Loopback boundary | The documented and Makefile start command binds Uvicorn to `127.0.0.1`; request middleware also rejects non-loopback peers/hosts; no CORS middleware is enabled. |
| SEC-4 | No internal path disclosure | Envelopes and warnings use a stable `sourceId`; responses never contain an absolute path, environment value, traceback, or raw OS error. |
| SEC-5 | Docker context hardened | Sensitive runtime files are excluded before a future image can include the new API dependencies. |
| OPS-1 | Local-only execution | Artifact GETs perform local resolver/read/validation work only; they do not call a network provider, spawn a subprocess, query IBKR/LLM, or write/refresh artifacts. |

## Fail-Soft Contract

| Source state | Loader result | HTTP result |
| --- | --- | --- |
| Valid JSON object with required anchors | available + object | 200, `available=true`, `reason=ok` |
| File absent, including read-time deletion race | unavailable | 200, `reason=missing` |
| Empty, truncated, malformed, invalid UTF-8, `NaN`, or `Infinity` | unavailable | 200, `reason=invalid_json` |
| Valid JSON list, scalar, `null`, or object missing a required anchor | unavailable | 200, `reason=invalid_shape` |
| Permission or other expected read `OSError` | unavailable | 200, `reason=unreadable` |
| Programmer defect such as an unexpected `RuntimeError` | propagate | 500 problem response |

FastAPI's strict loader mode must reject every non-finite number because Python's default JSON parser accepts named constants and can turn exponent overflow such as `1e999` into `inf`, which may fail later during response serialization. Streamlit compatibility mode continues to accept whatever the current `json.load()` accepts. Both modes catch only expected read/parse/shape failures.

## Affected Files

### Create

- `scripts/artifact_loader.py` — pure `LoadResult`, compatibility/strict JSON modes, shape validation.
- `api/__init__.py` — API package marker.
- `api/models.py` — Pydantic envelope, metadata, health, and problem models.
- `api/artifacts.py` — `ArtifactSpec` registry, source resolvers, envelope conversion.
- `api/main.py` — FastAPI app, loopback middleware, explicit routes, health, cache header, unexpected-error handler.
- `scripts/test_artifact_loader.py` — loader and Streamlit-wrapper compatibility matrix.
- `scripts/test_api.py` — route, response, recovery, security, OpenAPI, and CORS tests.

### Modify

- `ui/_shared.py` — delegate JSON parsing to the pure loader while retaining the existing decorator, name, return type, and `.clear()`.
- `requirements.txt` — declare FastAPI, Uvicorn, Pydantic, and PyYAML as direct dependencies.
- `Makefile` — add loopback `api` command and the two focused tests to `make test`.
- `.dockerignore` — exclude private reconciliation, watchlist, Risk Guard, AI-chat session, `.env*`, and local credential-setting files.
- `scripts/test_docker_runtime_contract.py` — assert the sensitive Docker exclusions.
- `.agents/PROJECT.md`, `.agents/lens.md`, `.agents/gateway.md`, and `.agents/scribe.md` — record the accepted architecture and reusable findings.

### Do not modify in batch 1

- `Dockerfile`, `docker-compose.yml`, `deploy/surge-screener.service`, or `scripts/deploy_test_server.sh`.
- Existing artifact writers or artifact payload schemas.
- Private artifact files themselves.

## Task 1: Lock the Docker Build-Context Boundary

**Files:** `scripts/test_docker_runtime_contract.py`, `.dockerignore`

- [ ] Add a failing contract test requiring exclusions for `reports/reconciliation.json`, `reports/watchlist.json`, `reports/risk_guard/`, `reports/ai_chat_sessions/`, `.env`, `.env.*`, and `.claude/settings.local.json`. If an `.env.example` is later added, explicitly re-include it.
- [ ] Run `.venv/bin/python scripts/test_docker_runtime_contract.py` and confirm the new assertion fails for the missing entries.
- [ ] Add the tested sensitive/runtime exclusions to `.dockerignore` without excluding committed application source or public artifact fixtures.
- [ ] Rerun the test and confirm all Docker runtime contract tests pass.

This task is a prerequisite even though batch 1 does not add a Docker API service: `Dockerfile` currently uses `COPY . .`, and dependency changes can trigger normal image rebuilds.

## Task 2: Build the Pure Configurable Loader

**Files:** `scripts/test_artifact_loader.py`, `scripts/artifact_loader.py`

- [ ] Write failing table-driven tests for valid object, missing file, empty/truncated JSON, invalid UTF-8, strict-mode `NaN`/`Infinity`, exponent overflow such as `1e999`/`-1e999`, strict object-mode list/scalar/null roots, `PermissionError`, and an unexpected exception.
- [ ] Add a recovery test: request while the file is malformed, replace it with valid JSON, then read successfully on the next call.
- [ ] Run `.venv/bin/python scripts/test_artifact_loader.py`; confirm failure because the module does not exist.
- [ ] Implement immutable `LoadResult` with `available`, `data`, and `reason`.
- [ ] Implement `load_json_artifact(path, require_object=True, reject_non_finite=True)` using UTF-8 and configurable constant/root validation. Strict mode must reject named constants and use a checked `parse_float` (or an equivalent recursive finite-number check) so exponent overflow cannot produce `inf`. The strict defaults are for API use; endpoint-specific field validation belongs to the registry layer.
- [ ] Map `FileNotFoundError` to `missing`, other expected `OSError` to `unreadable`, and decode/parse failures to `invalid_json`. Do not catch unexpected exceptions.
- [ ] Rerun the focused test; all loader cases must pass.

## Task 3: Preserve the Streamlit Compatibility Surface

**Files:** `scripts/test_artifact_loader.py`, `ui/_shared.py`

- [ ] Add failing compatibility assertions that `load_json()` returns ordinary objects, lists/scalars, and Python-compatible non-finite values exactly as before; returns `None` for missing/read/parse failures; and exposes callable `.clear()`.
- [ ] Prove `.clear()` clears the real cache: read value A, change the fixture to B, observe cached A, call `.clear()`, then observe B.
- [ ] Keep `@st.cache_data(ttl=60)` on `ui._shared.load_json()` and delegate to `load_json_artifact(..., require_object=False, reject_non_finite=False)`.
- [ ] Do not import Streamlit from the pure loader or make FastAPI import `ui._shared`.
- [ ] Rerun `.venv/bin/python scripts/test_artifact_loader.py`.
- [ ] Run `.venv/bin/python scripts/test_dashboard_navigation.py` to catch import/navigation regressions.

Existing callers that invoke `load_json.clear()` must continue to work; moving the decorator to the pure loader would be a blocking regression.

## Task 4: Define Models, Registry, and Resolvers

**Files:** `scripts/test_api.py`, `api/models.py`, `api/artifacts.py`

- [ ] Write failing tests for exact available/unavailable envelopes and stable `sourceId` values.
- [ ] Write registry tests proving the only batch-1 IDs and anchors are:

  | Source ID | Resolver | Required shape |
  | --- | --- | --- |
  | `candidates.ranked` | `candidate_output_path("ranked_candidates.json")` | `ranked_candidates: list[object]` |
  | `candidates.scored` | `candidate_output_path("scored_candidates.json")` | `all_scored: list[object]` |
  | `signals.options-flow.latest` | fixed reports path | `signals: list[object]` |
  | `signals.reversal-radar.latest` | fixed reports path | `candidates: list[object]` |
  | `signals.oversold-reversal.latest` | fixed reports path | `candidates: list[object]` |
  | `market-context.market-thesis.latest` | server-side latest resolver | `as_of: ISO date string`; `direction: string`; `manifest_status: string` |

- [ ] Implement Pydantic models matching `docs/api/quant-radar-v1.openapi.yaml`, including nullable unavailable `data` and explicit camelCase serialization aliases for `apiVersion`, `sourceId`, `asOf`, and `generatedAt`.
- [ ] Preserve every source field after registry validation: endpoint data models must use `ConfigDict(extra="allow")` (including nested public compatibility records) or return the already validated raw `dict[str, Any]` without model projection.
- [ ] Add a sentinel-field test at both registry and HTTP levels proving undeclared top-level and nested fields survive unchanged; this is required by FR-4 and prevents Pydantic v2's default `extra="ignore"` from silently dropping data.
- [ ] Add failing shape tests for a missing anchor, an anchor with the wrong container type, a list containing any non-object item, missing/wrong Market Thesis scalar fields, and an invalid Market Thesis ISO date.
- [ ] Implement an immutable registry with typed shape declarations (`object_list_fields`, `string_fields`, and `date_fields`) and validate them after parsing. It may be keyed internally by source ID, but no generic registry-key route is permitted.
- [ ] Convert every registry shape failure to `available=false`, `reason=invalid_shape`; do not let Pydantic response validation discover it later as a 500.
- [ ] Use `scripts.runtime_paths.candidate_output_path()` for candidate files.
- [ ] Test Market Thesis resolution across dates, same-day ready-over-regime-only, empty directory, directory enumeration `OSError`, and a selected file disappearing before read.
- [ ] Implement the Market Thesis latest resolver with fail-soft directory enumeration and existing ready-first ordering.
- [ ] Populate `meta.asOf` and `meta.generatedAt` only from validated payload fields or the selected archive identity; otherwise return `null`. Never expose the resolved path.

## Task 5: Add Explicit FastAPI Routes

**Files:** `scripts/test_api.py`, `api/main.py`, `api/__init__.py`

- [ ] Write failing `TestClient` tests for every route in the OpenAPI draft.
- [ ] Test the full failure matrix through HTTP, not only at loader level.
- [ ] Test that unavailable response model validation does not turn `data=null` into a 500.
- [ ] Test health with every artifact missing.
- [ ] Test immediate malformed-to-valid recovery.
- [ ] Test that an unexpected injected `RuntimeError` produces a sanitized 500 problem response using `TestClient(..., raise_server_exceptions=False)`.
- [ ] Test `Cache-Control: no-store`, absent wildcard CORS headers, 404 traversal path probes, ignored `?path=/etc/passwd` having no source-selection effect, and absence of generic/sensitive paths from `/openapi.json`.
- [ ] Test loopback peer/Host acceptance and non-loopback rejection independently of the Uvicorn CLI bind.
- [ ] Implement loopback peer/Host middleware, `/healthz`, and six explicit artifact route functions. Each route passes a constant registry entry to a shared internal read helper.
- [ ] Add only sanitized, structured warnings with `sourceId` and reason for unavailable reads; no absolute path or raw exception string.
- [ ] Add the cache header to all artifact responses.
- [ ] Rerun `.venv/bin/python scripts/test_api.py` until the entire matrix passes.

## Task 6: Wire Dependencies and Local Commands

**Files:** `requirements.txt`, `Makefile`

- [ ] Add direct FastAPI, Uvicorn, Pydantic, and PyYAML requirements in the repository's existing dependency style; do not rely on transitive parser installation.
- [ ] Install/update the local environment only if dependency installation is authorized.
- [ ] Add `api` to `.PHONY`, then add `make api` using `.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000`.
- [ ] Add both new focused test scripts to `make test`.
- [ ] Verify dependency compatibility with `.venv/bin/python -m pip check`.
- [ ] Start the server locally and verify `curl -fsS http://127.0.0.1:8000/healthz` returns the health contract.
- [ ] Run `make -n api` and verify the Uvicorn command is emitted even though the `api/` directory exists.
- [ ] Confirm no documented command binds `0.0.0.0`.

## Task 7: Contract and Regression Verification

- [ ] Parse `docs/api/quant-radar-v1.openapi.yaml` with the declared PyYAML dependency and compare its path set against `/openapi.json`; explain FastAPI-generated documentation-only differences, but allow no route drift.
- [ ] Contract-test the 200/500 media types, `Cache-Control` header, endpoint-specific anchor schemas, and nullable unavailable `data`; a path-only comparison is insufficient.
- [ ] Run:

  ```bash
  .venv/bin/python scripts/test_artifact_loader.py
  .venv/bin/python scripts/test_api.py
  .venv/bin/python scripts/test_docker_runtime_contract.py
  .venv/bin/python scripts/test_dashboard_navigation.py
  .venv/bin/python -m pip check
  make test
  git diff --check
  ```

- [ ] Compare the actual changed-file list and endpoint list against this accepted plan.
- [ ] Review changed code for swallowed exceptions, path injection, sensitive registry entries, response validation 500s, cache regressions, and unnecessary abstractions.
- [ ] Fix every blocking finding and rerun the affected checks.
- [ ] Record checks that cannot run and why; do not claim completion without the relevant focused tests.

## Security and Failure Review

- **Path traversal:** Eliminated structurally by explicit routes and a fixed registry. Symlinked deployment storage remains valid because callers never choose a path.
- **Sensitive data:** Private artifacts are denylisted and absent from the first registry. Docker-context exclusions prevent current local private files from entering an image layer.
- **Fail-soft masking defects:** The loader handles only expected I/O, decode, parse, and shape states. Unexpected exceptions propagate to a sanitized 500 and remain visible in server logs.
- **Stale unavailable response:** The API does not reuse Streamlit caching and sends `no-store`, so the next request observes repaired output.
- **Concurrent writer:** A half-written file becomes `invalid_json` without crashing. A later request retries. Atomic writer changes are beneficial but outside this API scope.
- **Contract boundary:** Batch 1 exposes only local non-private source files and validates endpoint-specific root anchors and item types. It preserves remaining artifact fields for Streamlit parity. A field-level public DTO allowlist is mandatory before non-loopback exposure so future artifact fields cannot become public accidentally.
- **Network exposure:** Loopback is safe for the local migration boundary. CORS is not authentication. Any non-loopback deployment is blocked until access control and perimeter decisions are accepted.

## Deployment Phase 2 Gate

Do not add systemd, Docker/Compose ports, or a `0.0.0.0` bind in batch 1. Before network deployment, a separate accepted plan must define:

- Intended clients and exact origins.
- TLS termination and VPN/firewall/reverse-proxy boundary.
- Identity, authorization, and ownership rules for any private endpoints.
- Rate limiting and abuse monitoring.
- Exact CORS allowlist; never wildcard with credentials.
- API service health checks that validate `/healthz` exactly, without treating a root-page response as healthy.
- Container/service secret handling and a build-context contract test.

## Rollback

- Stop the optional local Uvicorn process; Streamlit continues to read the same artifacts.
- Revert the new `api/` package, tests, requirements, and Makefile target.
- Restore the original body of `ui._shared.load_json()` if the delegation causes an unexpected compatibility issue; no artifact writer or schema migration is involved.
- Keep the `.dockerignore` sensitive-file exclusions even if the API feature is rolled back.

## Traceability

| Goal | Tasks | Verification |
| --- | --- | --- |
| Preserve fail-soft behavior | 2, 3, 5 | Loader matrix, HTTP matrix, immediate recovery |
| Keep existing Streamlit stable | 3 | Wrapper compatibility and navigation tests |
| Establish a safe API boundary | 1, 4, 5 | Registry tests, traversal/OpenAPI checks, Docker exclusions |
| Make the contract executable | 4, 5, 6 | Pydantic validation, `TestClient`, local health smoke |
| Prevent unreviewed deployment | 6 and Phase 2 gate | Loopback command inspection and no deployment-file changes |

## Pre-Implementation Plan Review

- Covers the requested fail-soft FastAPI behavior: **yes**.
- Affected files and ownership boundaries known: **yes**.
- Verification and recovery cases known: **yes**.
- Existing Streamlit cache compatibility covered: **yes**.
- Sensitive artifact and traversal risks addressed: **yes**.
- Unexplained scope expansion: **none**; Docker exclusions are a prerequisite because the existing image copies the working tree.
- Blocking issue for local loopback batch 1: **none after this plan is accepted**.
- Blocking issue for LAN/Docker/systemd API deployment: **yes**; authentication/perimeter/origin decisions remain unresolved, so that work is explicitly excluded.

### Review record

- Iteration 1 corrected Streamlit any-JSON-value compatibility, typed anchor/item validation, Makefile `.PHONY`, Risk Guard and credential build-context exclusions, direct YAML parser dependency, and an unverifiable latency claim.
- Iteration 2 added endpoint-specific OpenAPI schemas, loopback peer/Host enforcement, Market Thesis shape/resolver cases, exact cache-clear verification, and full artifact-field preservation through Pydantic.
- Iteration 3 added exponent-overflow rejection (`1e999`/`-1e999`) so strict parsing cannot emit a non-finite response value.
- Final independent verdicts: OpenAPI/API review **PASS**; implementation gate review **CERTIFIED**. No unresolved local batch-1 blocker remains.
