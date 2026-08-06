# FastAPI IV History Phase 2B Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.4 |
| Status | Implemented, verified, and independently reviewed |
| Author | Codex |
| Audience | Maintainers of the loopback FastAPI boundary |
| Related inventory | `docs/api/fastapi-endpoint-artifact-inventory.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |
| Prior phase | `docs/superpowers/plans/2026-07-14-fastapi-test-server-phase2a.md` |

## Goal

Add the first Phase 2 bounded read endpoint,
`GET /api/v1/options/iv-history/{ticker}`, without widening the network boundary or
weakening the existing fail-soft artifact contract.

## Architecture Decision

This is a small read-only slice, not a new domain or service layer. The route
parses one bounded business identifier, normalizes it to uppercase, constructs a
server-owned `ArtifactSpec`, and reuses the existing strict loader and envelope
orchestration. The client never supplies a path or registry key.

The endpoint uses a strict ASCII ticker grammar:

```text
^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$
```

The decoded path value must be 1–15 characters. Lowercase is accepted and
normalized to uppercase. Underscores, Unicode, leading/trailing separators,
adjacent separators without an alphanumeric group, whitespace, traversal
fragments, and overlength values are
invalid. FastAPI request-validation failures return exactly
`{"type":"about:blank","title":"Unprocessable Entity","status":422}` as an
HTTP 422 RFC 9457 response with `Content-Type: application/problem+json` and
`Cache-Control: no-store`. This handler standardizes request-validation errors
API-wide; the existing parameterless routes have no validation-error behavior to
change, and future parameterized routes inherit the same non-leaking contract.

The API must not reuse `scripts.iv_history._path()`: that writer removes invalid
characters and continues, which is suitable for its historical fail-soft write
path but would let distinct HTTP inputs select the same file.

## Scope

In scope:

- One loopback-only route: `GET /api/v1/options/iv-history/{ticker}`.
- Exact operation ID: `getIvHistory`.
- One API-wide sanitized request-validation error format used by that route.
- Contract-first OpenAPI and Pydantic models.
- Strict ticker parsing and uppercase normalization.
- Fixed resolution under `reports/iv_history/<NORMALIZED_TICKER>.json`.
- Exact payload validation for `ticker` and `series` anchors.
- Existing HTTP 200 unavailable envelopes for expected file failures.
- Immediate recovery after a missing, malformed, or half-written file is repaired.
- Unit, HTTP, traversal, OpenAPI, and regression tests.

Out of scope:

- Migrating either Streamlit consumer to call FastAPI.
- Changing `scripts/iv_history.py`, its writer, or existing artifact files.
- Adding writes, refreshes, live option-chain/provider calls, or caching.
- Adding more Phase 2 endpoints, aggregates, daily-report/COT lists, or DuckDB reads.
- Changing systemd, deployment scripts, ports, dependencies, Docker, or Makefile.
- LAN/public exposure, authentication, authorization, TLS, CORS, or rate limiting.

## Requirements

- `REQ-2B-001`: A valid ticker request MUST read only the corresponding
  server-owned IV history filename and return the existing artifact envelope.
- `REQ-2B-002`: Missing, unreadable, malformed, half-written, non-object, or
  shape-invalid IV history MUST return HTTP 200 with `available=false` and MUST
  NOT affect `/healthz`.
- `REQ-2B-003`: A repaired artifact MUST be visible on the next request; the API
  MUST NOT negatively cache unavailable results.
- `REQ-2B-004`: Available data MUST contain only the explicitly public `ticker`
  and `series` fields. Any extra source field makes the artifact `invalid_shape`
  so a future writer field cannot silently disclose a path, token, or private data.
- `CFR-2B-001`: The decoded ticker MUST match the strict grammar and length before
  any file selection. Invalid input MUST NOT be sanitized into another ticker.
- `CFR-2B-002`: Every series key MUST be a real ISO calendar date and every value
  MUST be a finite JSON number other than `bool` in the writer's domain
  `0 < iv < 10`.
- `CFR-2B-003`: Payload `ticker` MUST exactly equal the normalized path ticker.
  A mismatch is `invalid_shape`, not an alternate lookup.
- `CFR-2B-004`: `meta.sourceId` MUST remain the stable constant
  `options.iv-history`; responses MUST NOT expose a filename or absolute path.
- `CFR-2B-005`: The route MUST retain loopback peer/Host enforcement and the
  existing absence of CORS. Non-loopback exposure remains blocked.
- `CFR-2B-006`: Empty `series` MUST be a valid available artifact with
  `meta.asOf=null`. For non-empty series, `meta.asOf` MUST be the greatest
  validated series date. `meta.generatedAt` MUST remain null because the public
  payload allowlist has no generated timestamp field.
- `CFR-2B-007`: The checked-in contract and FastAPI app version MUST advance from
  `1.0.0-draft` to additive minor `1.1.0-draft`; the URL and health major remain
  `v1`.

## Acceptance Criteria

- `AC-2B-001`: Given `nvda`, `BRK.B`, or `BF-B`, when requested, then the route
  selects only `NVDA.json`, `BRK.B.json`, or `BF-B.json` respectively and returns
  the normalized ticker in available data.
- `AC-2B-002`: Given invalid inputs such as `A_B`, `.AAPL`, `AA..BB`, Unicode,
  whitespace, or more than 15 characters, when requested, then the response is a
  422 problem with the exact body/media type/header above and no filesystem detail.
- `AC-2B-003`: Given encoded traversal or slash probes, when requested, then no IV
  history artifact is selected. A route-matching invalid segment is the exact 422
  problem; a decoded slash that changes route shape is FastAPI's router-level 404.
  Either response contains no path, environment, or traceback detail. The 422
  requires `no-store`; the unmatched router 404 does not establish artifact state
  and is not required to carry that header.
- `AC-2B-004`: Given a valid missing, empty, truncated, malformed, invalid-UTF-8,
  non-object, or unreadable file, when requested, then the response is HTTP 200
  with the corresponding existing unavailable reason.
- `AC-2B-005`: Given invalid `ticker`/`series` anchors, a payload/path ticker
  mismatch, an impossible date, a string/bool/non-finite/out-of-domain IV, or any
  extra top-level field (including `absolute_path`, `token`, or `as_of`), when
  requested, then the response is HTTP 200 with `reason=invalid_shape` (or
  `invalid_json` when strict JSON parsing rejects the token itself) and no extra
  value is reflected.
  A successfully parsed 1000-digit JSON integer is also an out-of-domain
  `invalid_shape`, never an `OverflowError`/500. An integer rejected earlier by
  Python's parser digit-safety limit remains `invalid_json`.
- `AC-2B-006`: Given a half-written file followed by a valid replacement, when two
  consecutive requests are made, then the first is unavailable and the second is
  available without waiting for a cache.
- `AC-2B-007`: Given an unexpected resolver defect, when requested, then the API
  returns the existing sanitized HTTP 500 problem and no secret detail.
- `AC-2B-008`: Given the generated and checked-in OpenAPI documents, when compared,
  then both contain exactly the same route surface and document the ticker
  parameter, 200 envelope, 422 problem, 500 problem, and `no-store` headers.
- `AC-2B-009`: Given all existing API and deployment tests, when run after this
  slice, then Phase 1/2A fail-soft, health, loopback, and service-gate behavior
  remains unchanged.
- `AC-2B-010`: Given an empty series, then it is available with `asOf=null`; given
  an unsorted non-empty series, then `asOf` is its greatest real ISO date and
  `generatedAt` remains null.
- `AC-2B-011`: Given extra query values such as `?path=/etc/passwd&ticker=AMD`,
  then they cannot change the path-derived normalized ticker or selected file.

## Response Contract

Available example:

```json
{
  "available": true,
  "reason": "ok",
  "data": {
    "ticker": "NVDA",
    "series": {"2026-07-14": 0.49}
  },
  "meta": {
    "sourceId": "options.iv-history",
    "asOf": "2026-07-14",
    "generatedAt": null
  }
}
```

Expected artifact failures keep the existing unavailable shape with HTTP 200.
Invalid ticker input is a caller error and therefore is not fail-soft HTTP 200;
it is the exact HTTP 422 `application/problem+json` response above. Unexpected
implementation defects remain HTTP 500 `application/problem+json`.

The response schema must describe every machine-expressible success constraint:

- `ticker` is uppercase ASCII with pattern
  `^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$` and `maxLength: 15`.
- `series` uses date-formatted property names and numeric values with
  `exclusiveMinimum: 0` and `exclusiveMaximum: 10`.
- A description records that keys must also be real calendar dates; runtime
  validation and contract tests enforce this semantic rule.
- `additionalProperties: false` limits available data to `ticker` and `series`.

## Affected Files

Create:

- `docs/superpowers/plans/2026-07-14-fastapi-iv-history-phase2b.md`

Modify:

- `docs/api/quant-radar-v1.openapi.yaml`
- `docs/api/fastapi-endpoint-artifact-inventory.md`
- `api/models.py`
- `api/artifacts.py`
- `api/main.py`
- `scripts/test_api.py`
- `docs/superpowers/plans/2026-07-14-fastapi-read-api.md` (status only)
- `.agents/gateway.md`
- `.agents/scribe.md`
- `.agents/builder.md`
- `.agents/PROJECT.md`

Do not modify:

- `scripts/iv_history.py`, existing `reports/iv_history/*.json`, Streamlit UI,
  writers, dependencies, Makefile, Docker files, deployment/systemd files, or CI.

## Implementation Checklist

### 1. Contract and Failing Tests

- [x] Add the OpenAPI path, bounded ticker parameter, Options tag, typed IV history
  data/envelope, exact 422 validation problem, 500 problem, and `no-store`
  headers. Advance checked-in and generated API versions to `1.1.0-draft` while
  leaving URL/health major `v1`.
- [x] Set `operationId: getIvHistory` and update the contract introduction so it
  describes the current Phase 1 plus Phase 2B surface rather than only the first
  implementation batch.
- [x] Express and assert uppercase ticker, max length, date-formatted series
  property names, exclusive IV bounds, and `additionalProperties: false` in both
  static and generated success schemas.
- [x] Add failing pure tests for normalization, exact path construction, and
  invalid ticker rejection without sanitize-and-continue behavior.
- [x] Add failing shape tests for every `CFR-2B-002` and `CFR-2B-003` boundary.
- [x] Add failing HTTP tests for lowercase normalization, available/unavailable
  envelopes, traversal/encoding probes, immediate recovery, and sanitized errors.
- [x] Use a factory/resolver spy to prove a valid ticker constructs exactly its
  normalized path and every invalid/traversal/slash probe performs zero IV file
  selections, independent of filesystem case sensitivity.
- [x] On the same app instance with missing and malformed IV files, assert
  `/healthz` remains the exact healthy response.
- [x] Prove extra query strings cannot alter the path-selected ticker/file and
  distinguish route-matching 422 probes from decoded-slash router 404 probes.
- [x] Prove malicious extra payload fields produce a fail-soft `invalid_shape`
  envelope and are never reflected in the response.
- [x] Extend generated-vs-checked-in OpenAPI assertions to cover the parameter and
  200/422/500 contracts.
- [x] Run `.venv/bin/python scripts/test_api.py` and record the expected pre-code
  failure. Failure must be caused by the absent implementation, not broken tests.
- [x] Add every new test function to `scripts/test_api.py`'s manual `main()` list;
  assert the printed test names/count so OpenAPI's expected red failure cannot
  conceal unexecuted IV tests.

### 2. Models and Functional Core

- [x] Add strict `IvHistoryData` with an uppercase bounded `ticker` and
  `series: dict[date, Annotated[float, Field(gt=0, lt=10)]]`; forbid extra
  fields and verify the generated schema exposes these constraints.
- [x] Add a pure `normalize_ticker()` function and a defensive IV history spec
  factory. Invalid values fail construction; valid values produce one fixed
  normalized filename under the injected IV history directory.
- [x] Extend `ArtifactSpec` with the narrow custom data-validator hook needed for
  this parameterized payload; existing fixed registry behavior must remain
  unchanged.
- [x] Define hook semantics exactly: it receives the raw JSON object, runs before
  Pydantic coercion, `False` maps to `invalid_shape`, and any raised unexpected
  exception propagates to the sanitized HTTP 500 handler.
- [x] Validate raw values before Pydantic coercion so strings and booleans cannot
  masquerade as IV numbers. Treat an empty series as valid and reject every extra
  top-level field. Compare the numeric range without coercing an arbitrary-size
  JSON integer to float; cover a 1000-digit integer and require `invalid_shape`.
- [x] Add an optional `as_of_extractor` callback to `ArtifactSpec`. It receives
  only an already raw-validated object, returns an ISO date string or null, and
  runs only for available data. The IV extractor returns the greatest series
  date; existing fixed specs retain their current metadata behavior. Unexpected
  extractor exceptions propagate to the sanitized HTTP 500 handler.

### 3. HTTP Route

- [x] Inject the IV history directory into `create_app()` for isolated tests while
  defaulting to the repository's deployed `reports/iv_history` path.
- [x] Add an `IvHistoryEnvelope` and explicit route using the bounded FastAPI path
  parameter. Normalize only case; do not delete or replace characters.
- [x] Add a `RequestValidationError` handler returning sanitized HTTP 422 RFC 9457
  problems with the exact body/media type/header contract, and make the generated
  route schema explicitly document that response. Record this as the intentional
  API-wide validation-error standard.
- [x] Refactor the internal artifact read/logging helper to accept an
  `ArtifactSpec` rather than looking up only `registry[source_id]`. Existing six
  routes must still pass their injected registry specs; the IV route passes only
  its request-built spec. Add a regression test that catches a dynamic
  `registry["options.iv-history"]` lookup/`KeyError`.
- [x] Include only the validated normalized ticker as structured warning context
  for this route; never log raw input or the resolved path.
- [x] Inject a `RuntimeError` from the new raw data-validator and from the
  IV-series metadata extractor independently; each must reach the existing
  sanitized HTTP 500 response rather than being mislabeled unavailable.

### 4. Verification and Review

- [x] Run `.venv/bin/python scripts/test_api.py`.
- [x] Run `.venv/bin/python scripts/test_artifact_loader.py`.
- [x] Run `.venv/bin/python scripts/test_deploy_artifacts.py`.
- [x] Run `.venv/bin/python scripts/test_dashboard_navigation.py`.
- [x] Run `.venv/bin/python scripts/test_docker_runtime_contract.py`.
- [x] Run `.venv/bin/python -m pip check`.
- [x] Run `make test`.
- [x] Start Uvicorn locally on a temporary loopback port and verify one real
  available ticker plus one missing ticker and `/healthz`.
- [x] Run `git diff --check`.
- [x] Compare the actual diff and route surface against this affected-file list.
- [x] Review for path aliasing, Pydantic coercion, response-validation 500s,
  swallowed unexpected exceptions, source-field projection, cache changes, and
  accidental deployment/UI scope drift.
- [x] Fix every blocking finding and rerun affected checks.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Traversal or filename aliasing | Strict decoded grammar, uppercase-only normalization, fixed directory, adversarial HTTP tests |
| Valid JSON becomes response-validation 500 | Validate raw anchors/domain before returning `available=true`; test every invalid shape through HTTP |
| Artifact/payload mismatch | Require exact normalized payload ticker |
| Future source-field leakage | Forbid every top-level field except `ticker` and `series`; adversarial path/token fixture |
| Stale unavailable response | No API cache plus `Cache-Control: no-store`; repair-on-next-request test |
| Contract drift | Update checked-in OpenAPI first and compare parameter/responses against generated OpenAPI |
| Accidental network widening | No deployment changes; retain loopback middleware and service bind tests |
| Scope creep into frontend/writer | Explicit do-not-modify list and final changed-file comparison |

## Rollback

Remove the one route, IV history model/spec factory, validation handler, related
tests, and OpenAPI additions. No writer, artifact, dependency, deployment, or
data migration changes are involved. Existing six artifact endpoints and
Streamlit readers continue unchanged.

## Traceability

| Requirement | Acceptance | Verification |
| --- | --- | --- |
| `REQ-2B-001`, `CFR-2B-001` | `AC-2B-001`–`003`, `011` | Normalization/path unit tests and adversarial HTTP/query matrix |
| `REQ-2B-002` | `AC-2B-004`, `005`, `009` | Fail-soft HTTP matrix and regressions |
| `REQ-2B-003` | `AC-2B-006` | Immediate repair test |
| `REQ-2B-004`, `CFR-2B-002`, `003`, `006` | `AC-2B-005`, `010` | Raw-shape, leakage, and metadata tests |
| `CFR-2B-004` | `AC-2B-001`, `007` | Envelope and sanitized-error assertions |
| `CFR-2B-005` | `AC-2B-003`, `009` | Loopback/CORS and deploy-contract regressions |
| Contract consistency | `AC-2B-008` | Static/generated OpenAPI assertions |
| `CFR-2B-007` | `AC-2B-008`, `009` | Static/generated version assertions |

## Pre-Implementation Review

- User authorization: **continue the next phase**.
- Phase choice: **single bounded IV history read**, explicitly listed in the
  accepted inventory and smaller than list/detail, aggregate, or DuckDB work.
- Affected files, verification, rollback, and risks: **defined**.
- Additive API change: **yes; no existing route path or existing
  success/fail-soft response contract changes**. The app version and API-wide
  request-validation error format intentionally advance as documented.
- Live deployment or network mutation: **none**.
- Unauthenticated local-host loopback security model: **unchanged**; it does not
  provide operating-system user identity and must not be widened.
- Blocking issues: **none after three review iterations**.
- Independent scope/contract review: **PASS**.
- Independent security review: **PASS**.
- Independent executable-test review: **PASS**.
- Review corrections: constrained the public DTO, aligned dynamic-spec helper and
  callback semantics, standardized exact 422 handling, locked metadata/version,
  proved test registration/health/path selection, and distinguished parser-limit
  `invalid_json` from successfully parsed out-of-domain `invalid_shape`.

## Post-Implementation Review

- Tests-first evidence: the first API run failed on the absent
  `IV_HISTORY_SOURCE_ID` import; after implementation, all 21 registered API tests
  pass.
- Actual files match the affected-file list. No writer, artifact, Streamlit,
  dependency, Makefile, Docker, deployment/systemd, CI, or unrelated knowledge
  file changed for Phase 2B.
- All 11 existing `reports/iv_history/*.json` files satisfy the strict public DTO.
- Real loopback Uvicorn smoke passed for exact health, lowercase NVDA available,
  a valid missing ticker unavailable, and an invalid ticker 422.
- Final checks: `make test`, deploy artifact tests (18), API tests (21), loader
  tests (14), dashboard tests (45), Docker contract tests (10), `pip check`,
  `compileall`, and `git diff --check` all pass.
- Independent implementation, security, and mutation/test-strength re-reviews:
  **PASS**. Review-discovered raw-input logging and weak metadata/static-OpenAPI
  oracles were fixed and re-reviewed.
- The external Codex and Claude CLI review engines were degraded by a stuck
  runtime and produced no code verdict; no PASS was inferred from those failures.
  Deterministic checks and three scoped independent reviewers supplied the final
  evidence.
- `ruff` and `mypy` were unavailable in the existing environment; Python
  compilation and the repository's executable test suites passed instead.
- Live deployment, frontend migration, and non-loopback exposure were not run and
  remain outside this phase.

### Impact Scope Report

| Axis | Verdict | Evidence |
| --- | --- | --- |
| Callers | OK | `create_app()` keeps its default call; all fixed routes still use injected registry specs; only tests inject the IV directory. |
| Tests | Updated | 21/21 API tests plus full `make test`, deployment, dashboard, and Docker regressions pass. |
| Types/contracts | Updated | Pydantic DTO, generated OpenAPI, and checked-in OpenAPI 1.1.0-draft agree. |
| Configs | N/A | No env variable, feature flag, dependency, service, port, or deployment change. |
| Docs | Updated | Inventory, implementation plan, original plan status, contract, and journals reflect Phase 2B. |

Overall verdict: **Ready; no unresolved blocking finding.**

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-07-14 | Initial contract-first Phase 2B plan |
| v1.1 | 2026-07-14 | Resolved first-review blockers for output allowlisting, schema constraints, dynamic specs, exact 422 handling, metadata, and executable coverage |
| v1.2 | 2026-07-14 | Aligned large-integer parser classification and locked callback error, operation ID, and contract-description coverage |
| v1.3 | 2026-07-14 | Recorded blocker-free scope, security, and executable-test reviews |
| v1.4 | 2026-07-14 | Recorded implementation, verification, mutation review, and final PASS verdicts |
