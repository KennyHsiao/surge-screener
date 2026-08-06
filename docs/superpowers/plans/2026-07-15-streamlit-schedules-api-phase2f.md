# Streamlit Schedules API Consumer Phase 2F Plan

**Status:** Completed and verified on 2026-07-15

**Goal:** Make the existing Streamlit schedules page consume the completed
`GET /api/v1/system/schedules` boundary without making the page less resilient
when the loopback API is starting, stopped, or returning a defective response.

**Architecture:** Add a small framework-neutral client under `ui/` that performs
one fixed server-side loopback GET, validates the response with the shared Pydantic
API models, and returns a typed available/unavailable/client-failure union. The
schedules page is API-first. A valid API unavailable envelope is authoritative and
does not bypass strict validation. Transport, HTTP, or response-contract failures
fall back to the same fixed in-process `ArtifactSpec`/`read_artifact()` pipeline
with a visible sanitized warning, so raw-source validation is not duplicated or
weakened. Existing result readers remain local and unchanged.

## Why This Is the Next Slice

The prior roadmap did not name a phase after Phase 2E; every backend phase kept
Streamlit migration out of scope. The recent user request and the completed
schedules endpoint make the registry consumer the smallest end-to-end slice:
only `ui/sys_schedules.py::_load_schedules()` currently reads the same fixed source
directly. Moving report, ledger, reflection, status, or other result artifacts
would require separate public DTOs and is not part of this phase.

## Requirements

- `REQ-2F-001`: The schedules registry request MUST be exactly
  `GET http://127.0.0.1:8000/api/v1/system/schedules`; callers cannot supply a
  path, URL, query, source ID, host, or port.
- `REQ-2F-002`: The client MUST use `trust_env=False`,
  `follow_redirects=False`, and exact connect/read/write/pool inactivity timeouts
  of 0.25 seconds each. Python-3.10-compatible
  `asyncio.wait_for(private_request_coroutine(), timeout=1.0)` MUST cancel the
  complete `httpx.AsyncClient` request lifecycle from before connect through header
  acquisition, decoded body streaming, and envelope validation. The client and
  response stream live inside the canceled coroutine; the synchronous
  Streamlit-facing function runs the deadline wrapper with `asyncio.run()` and maps
  `asyncio.TimeoutError` to `deadline_exceeded`.
- `REQ-2F-003`: The client MUST request JSON and cap the decoded response at exactly
  2,097,152 bytes. HTTP 200 is accepted only with an `application/json` media type
  (case-insensitive, parameters allowed), a case-insensitive `no-store`
  `Cache-Control` directive, the shared strict schedules envelope, exact
  `meta.sourceId=system.schedules`, and null `asOf`/`generatedAt`.
- `REQ-2F-004`: `available=true` MUST preserve schedule order and public values,
  including a valid empty list. `_note` or any other unknown response field MUST
  fail the strict envelope contract; the client does not silently strip it.
- `REQ-2F-005`: A valid `available=false` envelope for `missing`, `invalid_json`,
  `invalid_shape`, or `unreadable` is authoritative. The UI shows a stable safe
  empty/unavailable state and MUST NOT read the local registry as a bypass.
- `REQ-2F-006`: Connect/read failures, non-200 responses, redirects, wrong media or
  cache headers, oversized bodies, malformed JSON, or invalid envelopes MUST NOT
  crash the page. They produce only a stable client-failure reason.
- `REQ-2F-007`: Only client failures trigger local fallback. The fallback MUST call
  `read_artifact(ARTIFACTS["system.schedules"])`, then parse available data through
  `SchedulesData`; it MUST NOT reimplement or bypass the authoritative exact-root,
  `_note`, projection, or public DTO rules. Local unavailable or unexpected fallback
  defects are an empty safe state and expose no raw diagnostic.
- `REQ-2F-008`: Client failure fallback MUST be visible through a generic warning
  that contains no exception, traceback, environment value, or absolute path.
- `REQ-2F-009`: API failures MUST NOT be negatively cached. Every Streamlit rerun
  performs a fresh API request; a following healthy response wins immediately over
  any cached local fallback value.
- `REQ-2F-010`: Schedule result fetchers, reflection UI, filters, and card rendering
  remain behaviorally unchanged except that strict `ScheduleEntry` attributes
  replace untyped dictionary access.

## Client Contract

`ui/_read_api.py` defines three immutable outcomes and composes its
`TypeAdapter` directly from `ArtifactAvailable[SchedulesData] |
ArtifactUnavailable` in `api.models`; it MUST NOT import `api.main` or initialize a
FastAPI app:

- `SchedulesApiAvailable(schedules=tuple[ScheduleEntry, ...])`
- `SchedulesApiUnavailable(reason=<artifact reason>)`
- `SchedulesApiFailure(reason=<stable client reason>)`

Stable client reasons are exactly `transport_error`, `deadline_exceeded`,
`http_status`, `invalid_media_type`, `invalid_cache_control`,
`response_too_large`, and `invalid_envelope`. No outcome stores raw exception text,
response bodies, environment data, status codes, or URLs beyond the fixed module
constant.

The client makes one attempt per call. This is an internal loopback read with a
local compatibility fallback; retries or a circuit breaker would add page latency
without improving the next-rerun recovery contract.

## UI States

| State | Registry source | UI behavior |
| --- | --- | --- |
| API available, non-empty | API | Render ordered schedule cards. |
| API available, empty | API | Show “目前沒有已登錄的排程”. |
| API valid unavailable | None | Show a stable reason-specific unavailable message; no local bypass. |
| API client failure + valid local registry | Local fallback | Show a sanitized degradation warning, then render local schedules. |
| API client failure + valid empty local registry | Local fallback | Show degradation warning plus the valid-empty message. |
| API client failure + bad/missing local registry | None | Show degradation warning plus an all-sources-unavailable message. |

## Affected Files

### Create

- `ui/_read_api.py` — fixed schedules HTTP client and typed result union.
- `scripts/test_ui_read_api.py` — framework-neutral client and page-resolution
  behavior tests.

### Modify

- `ui/sys_schedules.py` — API-first registry resolution, guarded local fallback,
  safe notices, and typed `ScheduleEntry` rendering.
- `scripts/test_dashboard_navigation.py` — static guard that the schedules page
  uses the fixed client while retaining result/reflection UI and that Docker's
  compatibility limitation is disclosed.
- `Makefile` — add the focused UI API and existing schedules-reflection tests to
  `make test`.
- `docs/USER_GUIDE.md` — document two-terminal API-backed local verification,
  correct the schedule count/table, and describe the partial API migration.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — mark the registry consumer as
  API-first while keeping result/status artifacts local/P2/Internal.
- `.agents/PROJECT.md`, `.agents/lens.md`, `.agents/scribe.md`, and
  `.agents/builder.md` — record scope and completion evidence.

### Do not modify

- `api/**`, checked-in OpenAPI, `content/schedules.json`, result artifacts or
  writers, `requirements.txt`, deployment/systemd files, CORS/auth/bind settings,
  Docker topology, or any other Streamlit page.

## Test-First Tasks

### Task 1: Lock the client boundary

- Add failing tests for exact method/URL, absent query, `Accept: application/json`,
  and one request. Use a client-construction recorder—not MockTransport alone—to
  assert `httpx.AsyncClient`, `trust_env=False`, `follow_redirects=False`, and all
  four exact 0.25-second timeout phases. Assert timeout request extensions are
  finite and a redirect handler sees exactly one request.
- Add exact available and valid-empty response tests proving order/value retention,
  strict shared-model parsing, source ID, and null metadata. Injected `_note` or
  other extra response fields MUST produce `invalid_envelope`.
- Add all four valid unavailable reasons and prove they remain typed unavailable
  results rather than client failures.

### Task 2: Lock fail-soft client failures

- Add table-driven tests for connect/read exceptions, 3xx/4xx/5xx, missing or wrong
  content type, missing or wrong no-store, malformed JSON, wrong envelope fields,
  wrong source ID, non-null schedule timestamps, and a body over the configured cap.
- Add a real random-port loopback slow-header server and patch only the client's
  private URL constant inside the test. Send header bytes often enough to stay below
  the 0.25-second inactivity timeout; assert the outer async deadline still returns
  `deadline_exceeded` in the cleanup-tolerant interval `0.75 <= elapsed < 2.5`
  seconds, closes the connection, and leaves no thread or socket behind. The
  independent fixed-URL test continues to pin production to `127.0.0.1:8000`.
- Prove the size limit against decoded bytes with a small gzip body that expands
  past 2,097,152 bytes; assert reading stops, the response closes, and the result is
  `response_too_large`. Separately generate and accept a maximum schema-valid
  schedules envelope below the cap.
- Assert every case returns only a stable client reason and never raw response or
  exception detail.
- Track async-stream closure for deadline, invalid-header, and oversized-body
  branches so early returns cannot leak connections.
- Add failure-then-success and unavailable-then-success calls through one transport
  to prove the client itself has no negative cache.

### Task 3: Integrate the schedules page

- Add failing behavior tests for API success and authoritative API unavailable with
  a raising-sentinel local reader and exact zero-call assertion. Cover client
  failure with valid/empty/missing/invalid local artifact results and an unexpected
  local-reader sentinel exception.
- Prove failure → local fallback → API success across two page-resolution calls:
  assert two API calls, exactly one local read, and that the second call immediately
  returns the API value rather than fallback data.
- Implement the fixed client and the page resolution state.
- Keep every `_RESULT_FETCHERS` mapping and reflection control unchanged.
- Render stable available/unavailable/degraded messages without raw diagnostics.

### Task 4: Update executable and user contracts

- Add the focused test to `make test` and a small dashboard static contract.
- Update the guide and inventory without claiming the whole page or frontend is
  API-backed.

## Verification

Run at minimum:

```bash
.venv/bin/python scripts/test_ui_read_api.py
.venv/bin/python scripts/test_sys_schedules_reflection.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_artifact_loader.py
.venv/bin/python scripts/test_api.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python scripts/test_docker_runtime_contract.py
.venv/bin/python -m py_compile ui/_read_api.py ui/sys_schedules.py scripts/test_ui_read_api.py
.venv/bin/python -c 'import ast, pathlib; ast.parse(pathlib.Path("ui/_read_api.py").read_text(), feature_version=(3, 10))'
.venv/bin/python -m pip check
make test
git diff --check
```

Use `streamlit.testing.v1.AppTest.from_string()` with a package-aware wrapper that
imports and calls `ui.sys_schedules.render()`. Assert actual cards/notices and zero
`at.exception` entries for API available, API unavailable, client-failure fallback,
and all-sources-unavailable states; a plain HTTP GET of Streamlit bootstrap HTML is
not evidence.

An additional real-Uvicorn integration may run only on fixed
`127.0.0.1:8000`. First pre-bind that exact address without killing or replacing an
existing listener. If the bind succeeds, pass the owned descriptor to Uvicorn, run
AppTest for the API-backed path, stop only the owned process, and rerun AppTest for
the fallback path. If port 8000 is already occupied, skip this optional integration
and report it explicitly; deterministic client/page/AppTest tests remain the
completion gate.

## Risks and Mitigations

- **API boot race or local developer starts only Streamlit:** client failure uses
  the validated local fallback and visibly reports degradation.
- **Fallback hides API outage:** warning is mandatory; fallback is never silent.
- **Fallback bypasses strict server rejection:** only transport/protocol/contract
  failure falls back; a valid API unavailable envelope is authoritative.
- **Proxy or redirect escapes loopback:** fixed URL, `trust_env=False`, and
  `follow_redirects=False` are executable test requirements.
- **Broken server returns a huge body:** streaming byte cap is enforced before
  Pydantic parsing. The exact 2 MiB cap exceeds the measured worst-case currently
  schema-valid serialized envelope (~1.66 MiB); maximum-valid and gzip-expansion
  tests keep that assumption executable.
- **Frontend scope balloons into status APIs:** all `_RESULT_FETCHERS` stay local;
  composed status remains P2 and reflection/logs remain Internal.
- **Known remaining page fragility:** `load_ledger()` and some direct Markdown/file
  readers are not fully fail-soft. This phase does not claim complete page migration
  or complete result-reader hardening.
- **Docker Compose topology:** Compose currently starts only Streamlit, so the
  schedules registry intentionally uses local fallback there and is not API-backed.
  `docs/USER_GUIDE.md` and a static contract MUST disclose this; adding an API
  container requires a separately reviewed non-loopback/container-network design.
- **Makefile port override:** the consumer supports only the deployment-default
  port 8000. `make api API_PORT=<other>` intentionally causes visible fallback and
  MUST be documented.

## Rollback

Revert the new client/test and restore the prior guarded local `_load_schedules()`.
No API, source artifact, data migration, writer, or deployment rollback is needed.

## Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| `REQ-2F-001`-`003` | Fixed client constants, Python-3.10-compatible cancellable async deadline, response gate | Exact request/config/slow-header/contract matrix |
| `REQ-2F-004`, `005` | Shared envelope and typed results | Available/empty/unavailable tests |
| `REQ-2F-006`, `008` | Stable failure union and safe copy | Failure matrix and sentinel assertions |
| `REQ-2F-007`, `009` | Page resolver plus guarded local loader | Fallback and immediate-recovery tests |
| `REQ-2F-010` | Typed page rendering; unchanged result map | Dashboard/static and regression suites |

## Implementation Evidence

Phase 2F is implemented and its focused, repository-wide, and real-process gates
all pass.

- `ui/_read_api.py` performs the fixed
  `GET http://127.0.0.1:8000/api/v1/system/schedules` with environment proxy and
  redirect following disabled, explicit HTTPX inactivity timeouts, a cancellable
  whole-request deadline, an exact 2 MiB decoded-body cap, and strict validation
  through the shared schedules envelope DTO.
- `ui/sys_schedules.py` treats a valid unavailable envelope as authoritative. Only
  client transport/HTTP/contract failures invoke the strict in-process
  `read_artifact(ARTIFACTS["system.schedules"])` fallback, and that degradation is
  visible to the user. Existing result fetchers remain local and unchanged.
- The user guide discloses that Docker Compose starts only Streamlit, so the
  schedules registry uses the visible local fallback and is not API-backed in that
  topology.
- Passing evidence: focused UI/API client `12/12`, reflection `2/2`,
  dashboard `46/46`, artifact loader `14/14`, API `36/36`, deploy artifact `18`,
  and Docker runtime contract `10/10`.
- The complete `make test` gate, Python compilation, Python 3.10 AST parsing,
  `git diff --check`, and `pip check` all pass.
- A collision-safe real-Uvicorn/AppTest smoke owned port 8000, rendered all ten
  schedules through the API, stopped only that owned process, and then proved the
  next page run rendered the visible strict local-fallback path.
- Two independent post-implementation reviews found no blocking or medium issues.
  Their low test-coverage and documentation findings were fixed before closure.

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | FAIL | Plain Streamlit HTTP smoke was a false oracle; `httpx` total timeout and MockTransport proxy/timeout claims were not executable; fixed port 8000 conflicted with arbitrary-port smoke; local fallback validation could drift from the API; gzip/deadline/rerun/reflection/Docker cases were incomplete. | v0.2 uses AppTest, exact four-phase timeouts plus monotonic budget, constructor recording, optional collision-safe fixed-port integration, authoritative `read_artifact()` fallback, maximum/gzip/slow-stream tests, cross-page-rerun recovery, reflection regression, and explicit Docker/port limitations. |
| 2 | FAIL | The body-loop monotonic check still could not cancel a header that dripped bytes forever below each inactivity timeout. Test feasibility otherwise passed. | v0.3 wraps connect, headers, body, and validation in one cancellable async deadline and requires a real slow-header loopback cancellation/cleanup oracle. |
| 3 | FAIL | `asyncio.timeout()` would fail on the deployed Python 3.10.12 runtime even though it works in the local Python 3.11 environment. | v0.4 uses `asyncio.wait_for()`/`asyncio.TimeoutError`, keeps all HTTP resources inside the canceled coroutine, and retains the slow-header cleanup oracle without changing deployment Python. |
| 4 | PASS | Independent contract and test-feasibility reviewers confirmed Python 3.10 compatibility, whole-I/O cancellation, cleanup, AppTest execution, strict fallback, and the full test matrix with no remaining blocker. | Plan accepted for implementation. |

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-07-15 | Initial API-first schedules consumer plan. |
| v0.2 | 2026-07-15 | Resolve first-round timeout, fallback, Streamlit execution, fixed-port, response-size, no-cache, reflection, and Docker blockers. |
| v0.3 | 2026-07-15 | Replace the incomplete body-only deadline with a cancellable async whole-request boundary and slow-header integration oracle. |
| v0.4 | 2026-07-15 | Make the whole-request deadline compatible with the deployed Python 3.10 runtime. |
| v0.5 | 2026-07-15 | Accept the plan after runtime-compatibility and test-feasibility reviews passed. |
| v0.6 | 2026-07-15 | Record the implemented API-first consumer and focused passing evidence while keeping final repository-wide gates pending. |
| v0.7 | 2026-07-15 | Close Phase 2F after full regression, real-Uvicorn/AppTest smoke, two independent reviews, and all low findings were resolved. |
