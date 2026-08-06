# FastAPI Fund Catalog Phase 2C Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.4 |
| Status | Implemented, verified, and independently reviewed |
| Author | Codex |
| Reviewer | Repository maintainer |
| Audience | Maintainers of the loopback FastAPI boundary |
| Related inventory | `docs/api/fastapi-endpoint-artifact-inventory.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |
| Prior phase | `docs/superpowers/plans/2026-07-14-fastapi-iv-history-phase2b.md` |

## Goal

Add `GET /api/v1/institutions/funds` as the next smallest bounded read. The
endpoint exposes the curated public SEC CIK catalog from `content/funds.json`
without calling EDGAR, exposing holdings, or weakening the existing fail-soft
and loopback-only API behavior.

Success means the checked-in contract, runtime schema, implementation, and tests
agree on one exact public DTO. Missing, half-written, malformed, unreadable, or
shape-invalid catalog files remain HTTP 200 unavailable artifact states.

## Architecture Decision

This slice is a fixed artifact read, not a live institutional-holdings API. The
server owns the path and the client supplies no identifier, filename, query,
URL, or CIK.

The source file currently contains two root fields:

- `_note`: repository-maintainer guidance; validated but not public.
- `funds`: the public display-name-to-CIK catalog.

Phase 2C introduces one optional `ArtifactSpec.data_projector` hook. The strict
load order is:

1. Strictly parse the source JSON.
2. Run the raw source validator against the original object.
3. Run the projector to create the public object.
4. Validate the projected object with the endpoint's strict Pydantic DTO.
5. Return only the projected object.

The raw validator MUST return the exact built-in `bool` type. `False` is
`invalid_shape`; `None`, integers, containers, or other non-boolean returns are
programming defects and reach the existing sanitized HTTP 500 handler. A
projector exception or a list, scalar, or null projector return is also an
unexpected programming defect and reaches the same handler. Existing specs have
no projector and retain their current behavior.

The public response contains only `funds`. `_note`, future source fields,
absolute paths, environment values, EDGAR request headers, and holdings are not
serialized.

## Scope

In scope:

- One additive route: `GET /api/v1/institutions/funds`.
- Exact operation ID: `getInstitutionFunds`.
- Stable source ID: `institutions.funds`.
- Fixed source path: `content/funds.json`.
- Strict source validation and explicit public projection.
- Strict nested public DTOs for display names, CIKs, and notes.
- Existing HTTP 200 unavailable envelopes and sanitized HTTP 500 problems.
- Immediate recovery after the source file is repaired.
- API draft version bump from `1.1.0-draft` to `1.2.0-draft`.
- Contract, unit, HTTP, recovery, projection, and regression tests.

Out of scope:

- Migrating Streamlit consumers to FastAPI.
- Calling SEC EDGAR or returning live 13F holdings.
- Accepting a CIK, fund name, path, URL, query, or filter from the client.
- Modifying `content/funds.json`, `scripts/edgar_13f.py`, or artifact writers.
- Daily-report, COT, retrospective, DuckDB, or aggregate endpoints.
- Authentication, CORS, rate limiting, TLS, or non-loopback exposure.
- Deployment, systemd, Docker, dependency, Makefile, or CI changes.

## Requirements

- `REQ-001`: The route MUST read only the server-owned `content/funds.json`
  artifact and MUST NOT call a provider or select a client-controlled path.
- `REQ-002`: Missing, empty, half-written, malformed, invalid-UTF-8,
  non-object, unreadable, or shape-invalid source data MUST return HTTP 200 with
  `available=false` and MUST NOT affect `/healthz`.
- `REQ-003`: Available data MUST contain exactly one root field, `funds`, and
  every fund entry MUST contain exactly `cik` and `note`.
- `REQ-004`: Repairing an unavailable source MUST be visible on the next request
  without waiting for an API cache.
- `CFR-001`: The source root MUST contain exactly `_note` and `funds`; `_note`
  MUST be a string no longer than 2,000 characters and MUST never be returned.
- `CFR-002`: `funds` MUST be an object with at most 100 entries. Every display
  name MUST be a non-empty string of at most 120 characters with no leading or
  trailing whitespace. Runtime validation and both OpenAPI schemas MUST apply
  `propertyNames` with `minLength: 1`, `maxLength: 120`, and pattern
  `^\S(?:.*\S)?$`.
- `CFR-003`: Every `cik` MUST remain a 1-10 character ASCII digit string,
  contain at least one non-zero digit, and match `^0*[1-9][0-9]*$`. Every
  `note` MUST be a string no longer than 200 characters. Booleans, numbers,
  nulls, missing fields, and nested extra fields are invalid shapes.
- `CFR-004`: The response MUST retain `Cache-Control: no-store`, loopback peer
  and Host enforcement, and the absence of CORS. Non-loopback exposure remains
  blocked.
- `CFR-005`: `meta.sourceId` MUST be `institutions.funds`; `meta.asOf` and
  `meta.generatedAt` MUST be null because the curated file provides neither
  public timestamp.
- `CFR-006`: Projector, validator, or resolver programming defects MUST propagate
  to the existing sanitized RFC 9457 HTTP 500 response. A validator returning
  anything other than exact `True` or `False`, and a projector returning anything
  other than an object, are programming defects. They MUST NOT be mislabeled as
  expected artifact unavailability.
- `CFR-007`: The endpoint's user-facing latency target remains P95 <= 500 ms and
  P99 <= 1,000 ms on the loopback deployment. This phase adds no network I/O.
- `CFR-008`: The checked-in OpenAPI contract and FastAPI app version MUST advance
  to additive version `1.2.0-draft`; the URL and health major remain `v1`.

## Acceptance Criteria

- `AC-FUNDS-001`: Given the checked-in catalog, when the endpoint is requested,
  then it returns HTTP 200, `available=true`, all 10 current funds, exact CIK
  strings, and no `_note` field.
- `AC-FUNDS-002`: Given a valid empty `funds` object, when requested, then the
  artifact is available with an empty public catalog and null timestamps.
- `AC-FUNDS-003`: Given an unknown root field or `_note` with the wrong type,
  when requested, then the response is HTTP 200 with `reason=invalid_shape` and
  no source value is reflected.
- `AC-FUNDS-004`: Given an empty/trimmed-invalid/overlength display name, a bad
  CIK, a missing/wrong/overlength note, more than 100 funds, or a nested extra
  field, when requested, then the response is HTTP 200 with
  `reason=invalid_shape`.
- `AC-FUNDS-005`: Given a missing, empty, truncated, malformed, invalid-UTF-8,
  non-finite, non-object, or unreadable file, when requested, then the response
  is the corresponding existing HTTP 200 unavailable envelope and `/healthz`
  remains healthy.
- `AC-FUNDS-006`: Given a half-written file followed by a valid replacement,
  when two consecutive requests use the same app instance, then the first is
  unavailable and the second is available.
- `AC-FUNDS-007`: Given a source `_note`, injected secret sentinel, or future
  root field, when requested, then none is serialized in an available response;
  unknown root fields make the artifact unavailable.
- `AC-FUNDS-008`: Given a projector, validator, or resolver that raises, a
  validator returning `None` or `1`, or a projector returning a list, scalar, or
  null, when requested, then the API returns the exact sanitized HTTP 500 problem
  with no callback detail.
- `AC-FUNDS-011`: Given a valid raw source and a projector that returns an object
  whose fund CIK has the wrong type or whose public root has an extra field, when
  requested, then the API returns HTTP 200 with `reason=invalid_shape`. This is
  distinct from a non-object projector return, which is an HTTP 500 defect.
- `AC-FUNDS-009`: Given generated and checked-in OpenAPI documents, when
  compared, then both include the exact route, operation ID, 200/500 contracts,
  public nested constraints, no-store headers, and version `1.2.0-draft`.
- `AC-FUNDS-010`: Given all existing API, loader, dashboard, deployment, and
  Docker contract tests, when run after this slice, then Phase 1/2A/2B behavior
  remains unchanged.

## Dependencies

- The Phase 1 strict loader and artifact envelope in `scripts/artifact_loader.py`
  and `api/artifacts.py`.
- FastAPI/Pydantic versions already pinned in `requirements.txt`; no new package.
- The checked-in curated source `content/funds.json`.
- The accepted Phase 2B loopback/no-store/error contract.

## Response Contract

Available example:

```json
{
  "available": true,
  "reason": "ok",
  "data": {
    "funds": {
      "Berkshire Hathaway (Buffett)": {
        "cik": "1067983",
        "note": "波克夏"
      }
    }
  },
  "meta": {
    "sourceId": "institutions.funds",
    "asOf": null,
    "generatedAt": null
  }
}
```

Expected source failures use the existing unavailable envelope with HTTP 200.
There is no request parameter, so this route adds no 422 contract. Unexpected
implementation defects use the existing HTTP 500 `application/problem+json`
response. All 200 and 500 responses include `Cache-Control: no-store`.

## Affected Files

Create:

- `docs/superpowers/plans/2026-07-14-fastapi-fund-catalog-phase2c.md`

Modify:

- `docs/api/quant-radar-v1.openapi.yaml`
- `docs/api/fastapi-endpoint-artifact-inventory.md`
- `api/models.py`
- `api/artifacts.py`
- `api/main.py`
- `scripts/test_api.py`
- `.agents/gateway.md`
- `.agents/scribe.md`
- `.agents/builder.md`
- `.agents/judge.md`
- `.agents/PROJECT.md`

Do not modify:

- `content/funds.json`, Streamlit UI, EDGAR/provider code, artifact loader,
  dependencies, Makefile, Docker files, deployment/systemd files, or CI.

## Implementation Checklist

### 1. Contract and Red Tests

- [x] Add the Institutions tag, route, response component, strict public data
  schemas, realistic example, and API version `1.2.0-draft` to OpenAPI.
- [x] Add the route/source to explicit expected registries and route surfaces.
- [x] Add a real-catalog test deep-equaling public data to
  `{"funds": source["funds"]}` and proving `_note` is projected out.
- [x] Add explicit paired boundary tests: 100/101 funds; Unicode display names at
  120/121 characters; empty, whitespace-only, leading/trailing-space names;
  200/201-character notes; 2,000/2,001-character `_note`; and CIKs at 1/10/11
  characters plus empty, zero-only, whitespace, full-width, number, bool, null.
- [x] Reject missing `_note`, missing `funds`, non-object `funds`, unknown root
  fields, and nested extra fields.
- [x] Add HTTP tests for exact available output, no-store, fail-soft failures,
  health independence, immediate recovery, a secret-sentinel `_note` that stays
  available but is omitted, and sanitized callback failures.
- [x] Inject validators returning `None`/`1` and projectors returning list/scalar/
  null; require the exact sanitized 500 response for each.
- [x] Inject an object-returning projector whose projected public DTO is invalid;
  require HTTP 200 `invalid_shape` to prove DTO validation runs after projection.
- [x] Add generated-vs-checked-in OpenAPI assertions with independent expected
  constants for route, operation, zero parameters, absence of 422, public fields,
  `additionalProperties: false`, `maxProperties: 100`, `propertyNames`, bounds,
  CIK pattern, `_note` absence, and version.
- [x] Add every new test to `scripts/test_api.py`'s manual `main()` list.
- [x] Run `.venv/bin/python scripts/test_api.py` and record a failure caused by
  the absent Phase 2C implementation, not by a broken test.

### 2. Models and Functional Core

- [x] Add strict `FundCatalogEntry` and `FundCatalogData` DTOs with no extra
  public fields and machine-expressible length/pattern/property constraints.
- [x] Add an optional `data_projector` callback to `ArtifactSpec`.
- [x] Refactor validation into one explicit raw-validator -> projector -> public
  DTO pipeline. Existing specs with no projector MUST return the same data.
- [x] Treat exact raw-validator `False` and Pydantic public validation errors as
  `invalid_shape`; reject non-boolean validator returns with `TypeError`; propagate
  callback exceptions and wrong projector return types.
- [x] Add the fixed `institutions.funds` registry entry and source validator.
- [x] Project only `{"funds": source["funds"]}`; never mutate the source object.
- [x] Derive `meta` only from projected public data so internal source fields can
  never influence public metadata implicitly.

### 3. HTTP Route

- [x] Add `FundCatalogEnvelope` and `GET /api/v1/institutions/funds` using the
  registry entry, existing read helper, no-store header, and 200/500 docs.
- [x] Add the source ID to the required fixed registry set so incomplete injected
  registries fail at app creation.
- [x] Keep the route parameterless and retain existing loopback/CORS behavior.

### 4. Verification and Review

- [x] Run `.venv/bin/python scripts/test_api.py`.
- [x] Run `.venv/bin/python scripts/test_artifact_loader.py`.
- [x] Run `.venv/bin/python scripts/test_deploy_artifacts.py`.
- [x] Run `.venv/bin/python scripts/test_dashboard_navigation.py`.
- [x] Run `.venv/bin/python scripts/test_docker_runtime_contract.py`.
- [x] Run `.venv/bin/python -m pip check` and compile changed Python files.
- [x] Run `make test` and `git diff --check`.
- [x] Start Uvicorn on a temporary loopback port and verify real available,
  injected missing, and `/healthz` responses.
- [x] Compare the actual diff with this affected-file list and resolve unexplained
  scope drift.
- [x] Independently review correctness, security/output projection, and test
  mutation strength. Fix all blocking findings before completion.

## Post-Implementation Verification

- The red test failed for the intended missing Phase 2C symbol before runtime
  implementation was added.
- API tests pass `24/24`; loader tests pass `14/14`; deployment artifact tests
  pass `18/18`; dashboard navigation tests pass `45/45`; Docker runtime contract
  tests pass `10/10`.
- `pip check`, Python compilation, the full `make test` suite, whitespace checks,
  and `git diff --check` pass.
- Real Uvicorn probes confirmed 10 projected funds with no `_note`; an injected
  missing file returned HTTP 200 unavailable while `/healthz` stayed healthy.
  Both responses used `Cache-Control: no-store`.
- Independent implementation and API/security reviews passed. The adversarial
  test review initially blocked on the missing valid-empty-catalog HTTP oracle;
  after adding its exact envelope, null metadata, health, and no-store checks,
  the same reviewer returned PASS.
- The Phase 2C diff matches the affected-file list. Two Phase 2B test assertions
  were deliberately strengthened during the requested pre-phase review. No
  source artifact, provider, Streamlit, dependency, deployment, Docker, or CI
  behavior was changed by Phase 2C.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| `_note` or a future source field leaks | Raw exact-key validator, explicit projector, strict public DTO, adversarial HTTP test |
| CIK is coerced from a number | Strict raw/Pydantic string pattern and number/bool fixtures |
| Projector changes existing endpoints | Optional hook defaults to identity; all existing HTTP and loader regressions run |
| Expected bad source becomes HTTP 500 | Shape matrix covers raw and projected validation failures |
| Programming defects are swallowed as unavailable | Inject raising validator/projector/resolver and require sanitized 500 |
| Stale missing response | No API cache, no-store, repair-on-next-request test |
| API is mistaken for live holdings | Route/description explicitly expose only curated fund metadata; no EDGAR call |
| Network boundary widens | No deployment changes; loopback and no-CORS tests remain required |

## Rollback

1. Remove the fund route, envelope, DTOs, registry entry, projector hook, and
   Phase 2C tests/docs.
2. Restore app/static contract version `1.1.0-draft`.
3. Run the Phase 1/2A/2B API and deployment verification suites.

No data migration or writer rollback is required because Phase 2C is read-only
and does not modify `content/funds.json`.

## Traceability Matrix

| Requirement | Acceptance criteria | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-001` | `AC-FUNDS-001`, `AC-FUNDS-009` | `IMPL-001` fixed spec and route | `TEST-001` registry/HTTP/OpenAPI |
| `REQ-002` | `AC-FUNDS-005` | `IMPL-002` shared fail-soft reader | `TEST-002` failure matrix/health |
| `REQ-003` | `AC-FUNDS-003`, `AC-FUNDS-004`, `AC-FUNDS-007` | `IMPL-003` validator/projector/DTO | `TEST-003` shape/projection matrix |
| `REQ-004` | `AC-FUNDS-006` | `IMPL-004` uncached read | `TEST-004` same-app repair |
| `CFR-004`, `CFR-005`, `CFR-006`, `CFR-008` | `AC-FUNDS-008`, `AC-FUNDS-009`, `AC-FUNDS-010` | `IMPL-005` boundary/version/error contract | `TEST-005` regression/500/OpenAPI |

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | BLOCK | Exact-bool validator semantics, `propertyNames` enforcement, paired boundary oracles, and non-object projector tests were underspecified. | Closed in v1.1; iteration 2 required |
| 2 | BLOCK | No independent oracle proved that an object returned by the projector still passes through public DTO validation. | Closed in v1.2; iteration 3 required |
| 3 | PASS | Contract, implementation, and adversarial test reviewers found no remaining blocker. | Implementation authorized |

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-07-14 | Initial contract-first Phase 2C plan |
| v1.1 | 2026-07-14 | Closed first-review validation, schema, and test-oracle blockers |
| v1.2 | 2026-07-14 | Added projected-object public DTO validation oracle |
| v1.3 | 2026-07-14 | Accepted after contract, implementation, and test reviews passed |
| v1.4 | 2026-07-14 | Recorded implementation, verification, scope audit, and blocker closure |
