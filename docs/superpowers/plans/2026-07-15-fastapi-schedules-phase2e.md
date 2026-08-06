# FastAPI Schedules Phase 2E Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.0 |
| Status | Implemented, verified, and reviewed |
| Author | Codex |
| Reviewer | Repository maintainer |
| Audience | Maintainers of the loopback FastAPI boundary |
| Related inventory | `docs/api/fastapi-endpoint-artifact-inventory.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |
| Prior phase | `docs/superpowers/plans/2026-07-15-fastapi-ai-updates-phase2d.md` |

## Goal

Add `GET /api/v1/system/schedules` as the next smallest safe fixed public read.
The endpoint exposes only the manually maintained schedule registry in
`content/schedules.json`. It does not expose the maintainer `_note`, read job
results, inspect logs, or call a provider.

Success means the checked-in contract, generated schema, runtime validation,
implementation, and tests agree on one strict public DTO. Missing, half-written,
malformed, unreadable, or shape-invalid schedule files remain HTTP 200
unavailable artifact states and never make `/healthz` fail.

## Endpoint Selection Evidence

The source is a tracked 4.6 KB file with one read-only Streamlit consumer. It has
no runtime writer, environment path override, command line, credential, absolute
path, position, or personal-data field. Deployment copies it with the release;
it is not one of the mutable shared-content symlinks.

The source currently contains ten ordered entries. Every entry has exactly seven
string fields: `id`, `name`, `category`, `cron`, `cron_note`, `description`, and
`result_type`. The UI preserves source order and uses `result_type` only to choose
a separate result reader. Those result artifacts are outside this endpoint.

Other remaining P1 candidates are less suitable for this slice: generated
artifacts have large or evolving nested schemas, runtime writers, missing
representative data, raw provider errors, absolute paths requiring projection,
or archive-ordering requirements. The inventory already classifies schedules as
P1 and status aggregation as P2/Internal.

One existing content issue is intentionally not changed here: some UTC cron
values and human timezone notes may not describe daylight-saving behavior
consistently. The API preserves both strings and makes no claim that it parses,
normalizes, or verifies cron/timezone semantics.

## Architecture Decision

The route is a parameterless fixed-file read. The server owns the path and the
client supplies no identifier, path, URL, query, filter, or schedule selector.

The source root must contain exactly:

- `_note`: maintainer guidance, validated but never public.
- `schedules`: the ordered public schedule list.

The existing raw-validator -> projector -> strict public DTO pipeline is reused.
The projector returns only `{"schedules": source["schedules"]}`. Public list and
string values are preserved exactly.

`result_type` remains a bounded snake-case identifier rather than an enum. This
keeps the API forward-compatible with a future public result type while still
rejecting malformed identifiers. The endpoint does not dereference it.

Schedule-ID uniqueness is a runtime semantic constraint enforced by the public
`SchedulesData` validator and an executable duplicate-ID oracle. JSON Schema
`uniqueItems` compares complete objects and cannot express uniqueness of one
property across different objects. Both OpenAPI documents therefore describe the
ID rule on the `schedules` field but MUST NOT claim that `uniqueItems` enforces it.

Cron is an opaque, bounded, non-blank string. The API does not parse cron fields,
translate timezones, or derive execution timestamps. The source has no artifact
date, so available metadata always has null `asOf` and null `generatedAt`.

## Scope

In scope:

- One additive route: `GET /api/v1/system/schedules`.
- Exact operation ID: `getSchedules`.
- Stable source ID: `system.schedules`.
- Fixed source path: `content/schedules.json`.
- Exact internal source validation and explicit `_note` projection.
- A strict, source-order-preserving seven-field public DTO.
- Unique schedule IDs and bounded public string fields.
- Existing HTTP 200 unavailable envelopes and sanitized HTTP 500 problems.
- Immediate recovery after source repair.
- API draft version bump from `1.3.0-draft` to `1.4.0-draft`.
- Static/generated OpenAPI, unit, HTTP, recovery, privacy, and regression tests.

Out of scope:

- Migrating `ui/sys_schedules.py` to FastAPI.
- Editing or generating `content/schedules.json`.
- Reading recent run results, reports, ledgers, reflections, logs, or status files.
- Parsing or validating cron/timezone semantics.
- Filtering, sorting, pagination, execution status, next-run calculation, or job
  control.
- Authentication, CORS, rate limiting, TLS, or non-loopback exposure.
- Closing the inherited global middleware-403 OpenAPI documentation gap.
- Deployment, Docker, dependencies, Makefile, systemd, GitHub Actions, or CI.
- Any other P1/P2 endpoint.

## Requirements

- `REQ-001`: The route MUST read only server-owned `content/schedules.json` and
  MUST NOT select a client-controlled path or read any result artifact.
- `REQ-002`: Missing, empty, half-written, malformed, invalid-UTF-8, non-object,
  unreadable, or shape-invalid source data MUST return HTTP 200 with
  `available=false` and MUST NOT affect `/healthz`.
- `REQ-003`: Available public data MUST contain exactly one root field,
  `schedules`. Each item MUST contain exactly `id`, `name`, `category`, `cron`,
  `cron_note`, `description`, and `result_type`.
- `REQ-004`: Repairing an unavailable source MUST be visible on the next request
  without waiting for an API cache.
- `CFR-001`: The source root MUST contain exactly `_note` and `schedules`.
  `_note` MUST be a strict string no longer than 2,000 characters and MUST never
  be returned.
- `CFR-002`: `schedules` MUST be an array with at most 100 object items. An empty
  array is valid. Source order MUST be preserved.
- `CFR-003`: `id` MUST be a strict 1-64 character lowercase snake-case identifier
  matching `^[a-z0-9]+(?:_[a-z0-9]+)*$`. IDs MUST be unique within the artifact.
  This cross-item constraint is enforced at runtime. Both OpenAPI schemas MUST
  describe it but MUST NOT represent it as `uniqueItems` enforcement.
- `CFR-004`: `result_type` MUST use the same strict 1-64 character identifier
  contract as `id`, but MUST NOT be restricted to the nine values currently
  present or dereferenced by the API.
- `CFR-005`: `name` MUST be a strict 1-100 character string; `category` MUST be a
  strict 1-50 character string; and `cron` MUST be a strict 1-100 character
  string. Each MUST have no leading or trailing whitespace and MUST use schema
  pattern `^\S(?:[\s\S]*\S)?$`. Cron remains opaque.
- `CFR-006`: `cron_note` MUST be a strict string no longer than 500 characters,
  and `description` MUST be a strict string no longer than 2,000 characters.
  Empty is valid; otherwise neither may have leading or trailing whitespace.
  Both MUST use schema pattern `^(?:|\S(?:[\s\S]*\S)?)$`.
- `CFR-007`: Numbers, booleans, nulls, missing item fields, extra item fields,
  duplicate IDs, non-array `schedules`, and non-object items MUST be
  `invalid_shape`.
- `CFR-008`: Available metadata MUST use `sourceId=system.schedules` with null
  `asOf` and null `generatedAt`.
- `CFR-009`: Responses MUST retain `Cache-Control: no-store`, loopback peer/Host
  enforcement, and the absence of CORS.
- `CFR-010`: Resolver, validator, projector, or metadata callback programming
  defects and invalid callback return types MUST reach the sanitized RFC 9457
  HTTP 500 handler. A validator's exact built-in `False` and an object projector
  result that fails the public DTO remain HTTP 200 `invalid_shape`.
- `CFR-011`: The route MUST add no provider/network I/O and no response cache.
  The inherited loopback P95 <= 500 ms and P99 <= 1,000 ms targets remain
  operational objectives, not benchmark completion claims.
- `CFR-012`: Checked-in OpenAPI and the FastAPI app version MUST be
  `1.4.0-draft`; the URL and health major remain `v1`.

## Acceptance Criteria

- `AC-SCHEDULES-001`: Given the checked-in source, HTTP 200 returns all ten
  schedules in exact source order and with exact public values, null timestamps,
  no `_note`, and no fields from result artifacts.
- `AC-SCHEDULES-002`: Given `{"_note":"","schedules":[]}`, HTTP 200 returns an
  available empty list with null timestamps and no-store.
- `AC-SCHEDULES-003`: Missing source keys, unknown root keys, a non-string or
  over-limit `_note`, a non-array `schedules`, or a non-object item returns HTTP
  200 `invalid_shape` without reflecting source values.
- `AC-SCHEDULES-004`: A missing/extra item field, wrong field type, invalid or
  over-limit identifier, duplicate ID, over-limit text, forbidden surrounding
  whitespace, or more than 100 items returns HTTP 200 `invalid_shape`.
- `AC-SCHEDULES-005`: Boundary values MUST be executable: 0/100/101 schedules;
  0/1/64/65 characters independently for both `id` and `result_type`; `name`
  0/1/100/101; `category` 0/1/50/51; `cron` 0/1/100/101; `cron_note`
  0/500/501; and `description` 0/2,000/2,001. Every required field MUST also have
  an independent wrong-type and leading/trailing-whitespace oracle. The 100/101
  item cases use otherwise-valid unique IDs so duplicate-ID validation cannot
  mask `maxItems`; the duplicate-ID case uses two otherwise-different objects so
  whole-object equality cannot satisfy the oracle accidentally.
- `AC-SCHEDULES-006`: Missing maps to reason `missing`; empty/truncated/malformed,
  invalid-UTF-8, or non-finite JSON maps to `invalid_json`; a non-object root or
  DTO-invalid value maps to `invalid_shape`; and read `OSError` maps to
  `unreadable`. `/healthz` remains healthy for every case.
- `AC-SCHEDULES-007`: A half-written source followed by a valid replacement is
  unavailable on the first request and available on the next request using one
  app instance.
- `AC-SCHEDULES-008`: A raising resolver/validator/projector/as-of extractor,
  resolver wrong result type, validator `None`/`1`, projector list/scalar/null,
  or as-of extractor returning `1`, an impossible date, or a non-ISO date
  produces the exact sanitized HTTP 500 problem with no-store and no
  source/callback detail in response or structured log. Every case independently
  asserts status, exact body, media type, header, and sanitized structured log.
  Validator `False` remains HTTP 200 `invalid_shape`; an as-of extractor returning
  `None` remains HTTP 200 with null `asOf`.
- `AC-SCHEDULES-009`: An object projector result with an extra root field,
  duplicate ID, wrong nested type, or extra item field returns HTTP 200
  `invalid_shape`, distinct from a non-object projector defect.
- `AC-SCHEDULES-010`: Generated and checked-in OpenAPI agree on route, operation
  ID, zero parameters, 200/500 responses, strict schema constraints, examples,
  `_note` absence, and version `1.4.0-draft`. Both describe runtime ID uniqueness
  on the `schedules` field and neither claims property-level enforcement through
  `uniqueItems`. Their available/empty example value sets MUST deep-equal, retain
  explicit null `asOf`/`generatedAt`, and every example MUST independently
  validate against its document's 200 envelope schema. Schema-validation
  negatives MUST reject an extra envelope field, extra data-root field, extra
  item field, and missing item field in both documents.
- `AC-SCHEDULES-011`: Existing API, loader, dashboard, deployment, Docker, and
  full repository tests remain green.
- `AC-SCHEDULES-012`: Ignored `path`, `url`, `id`, or `result_type` query keys do
  not change the fixed source or response. The route retains loopback peer/Host
  rejection and no CORS headers. Each query key is tested independently while a
  loader spy proves the request reads exactly `content/schedules.json` once.
  An import/dependency oracle also rejects API use of `ui.sys_schedules`,
  `_RESULT_FETCHERS`, imports rooted at `ui`, or imports of `requests`, `httpx`,
  `urllib.request`, `socket`, `yfinance`, `anthropic`, or `openai` from
  `api/main.py` and `api/artifacts.py`.

## Response Contract

```json
{
  "available": true,
  "reason": "ok",
  "data": {
    "schedules": [
      {
        "id": "local_data_health_refresh",
        "name": "資料健康完整更新",
        "category": "系統",
        "cron": "15 6 * * 2-6",
        "cron_note": "週二至週六 06:15 Asia/Taipei",
        "description": "自動更新資料健康產物。",
        "result_type": "data_health"
      }
    ]
  },
  "meta": {
    "sourceId": "system.schedules",
    "asOf": null,
    "generatedAt": null
  }
}
```

Expected source failures use the existing HTTP 200 unavailable envelope. The
route has no parameters and adds no 422 response. Unexpected application defects
use the existing sanitized HTTP 500 problem. Every response is no-store.

## Affected Files

Create:

- `docs/superpowers/plans/2026-07-15-fastapi-schedules-phase2e.md`

Modify:

- `docs/api/quant-radar-v1.openapi.yaml`
- `docs/api/fastapi-endpoint-artifact-inventory.md`
- `api/models.py`
- `api/artifacts.py`
- `api/main.py`
- `scripts/test_api.py`
- `.agents/lens.md`
- `.agents/scribe.md`
- `.agents/gateway.md`
- `.agents/builder.md`
- `.agents/judge.md`
- `.agents/PROJECT.md`

Do not modify:

- `content/schedules.json`, Streamlit UI, artifact loader, result artifacts,
  providers, dependencies, Makefile, Docker files, deployment/systemd files,
  GitHub Actions, or CI.

The inventory edit retains the existing P1 whitelist row and changes only the
schedules disposition text to record Phase 2E implementation.

## Dependencies and Feasibility

- Existing Pydantic v2 strict models and `field_validator` cover exact strings,
  bounded arrays, identifier patterns, and unique IDs.
- JSON Schema cannot express uniqueness of one property across array items.
  Runtime validation and a duplicate-ID test are authoritative; static/generated
  schema descriptions disclose the semantic constraint without misusing
  `uniqueItems`.
- The raw validator can reject invalid root/list/item containers before the
  projector, preserving expected `invalid_shape` semantics.
- The existing fixed registry, projector, DTO, unavailable envelope, no-store,
  and exception boundary require no shared-pipeline change.
- FastAPI strips null values while composing OpenAPI examples. The existing
  narrow schema post-processing hook will be generalized to restore both AI
  updates and schedules examples without altering runtime responses.
- No package, provider, writer, migration, deployment, or UI change is required.

## Implementation Checklist

### 1. Contract and Red Tests

- [x] Add the parameterless route, System tag use, response components, strict
  public schemas, realistic available/empty examples, and version
  `1.4.0-draft` to the checked-in OpenAPI document before runtime code. Update
  the top-level API description so its enumerated read surface includes schedules.
- [x] Add independent static/generated OpenAPI assertions for field sets,
  constraints, exact whitespace/identifier patterns, the runtime-only ID
  uniqueness description, absence of misleading `uniqueItems`, no 422, examples,
  envelope closure, and `_note` absence. Static `AvailableSchedules` MUST use
  `unevaluatedProperties: false`, and static/generated schema-validation tests
  MUST both reject a semantically extra available-envelope field.
- [x] Deep-equal real public data to `{"schedules": source["schedules"]}` and
  assert exact source order, string values, null metadata, and no result reads.
- [x] Add all paired list/string/identifier boundaries from
  `AC-SCHEDULES-005`, including a valid future `result_type` not present in the
  current UI fetcher map. Use unique IDs in 100/101-item fixtures, and use two
  otherwise-different rows in the duplicate-ID fixture.
- [x] Reject wrong roots, missing/extra fields, wrong strict types, bad
  identifiers, duplicate IDs, surrounding whitespace, and source secrets.
- [x] Add exact HTTP failure matrix, health independence, no-store, secret
  omission, same-app recovery, and metadata tests.
- [x] Execute the callback matrix from `AC-SCHEDULES-008`, including exact 500
  body/media/header/log assertions; separately prove validator `False` and
  invalid object projections remain 200 `invalid_shape`, and as-of `None` remains
  an available null-metadata result.
- [x] Update `EXPECTED_REGISTRY`, `EXPECTED_PATHS`, `SOURCE_PATHS`, and
  `_http_registry()` together, including fixed resolver path, ignored-query,
  loopback, Host, and no-CORS assertions.
- [x] Add a loader-path spy proving one fixed `content/schedules.json` read for
  the baseline and each ignored query. Add an import/dependency oracle that
  parses `api/main.py` and `api/artifacts.py`, rejects any `ui` import or
  `_RESULT_FETCHERS` reference, and rejects imports of `requests`, `httpx`,
  `urllib.request`, `socket`, `yfinance`, `anthropic`, or `openai`.
- [x] Register every new test in the manual `main()` list.
- [x] Run API tests and record a red failure caused by absent Phase 2E runtime
  code.

### 2. Models and Functional Core

- [x] Add strict `ScheduleEntry` and `SchedulesData` DTOs with no extra fields.
- [x] Keep all public values as source-preserving strict strings; add bounded
  identifier/text schemas and schedule-ID uniqueness validation.
- [x] Add fixed constants, exact source validator, and one-field public
  projector for `system.schedules`.
- [x] Reuse the shared callback and DTO pipeline without changing existing
  artifact behavior.

### 3. HTTP Route

- [x] Add `SchedulesEnvelope` and `GET /api/v1/system/schedules` using the fixed
  registry entry and existing no-store/200/500 behavior.
- [x] Add the source ID to the required fixed registry set.
- [x] Keep the route parameterless and retain loopback/CORS behavior.
- [x] Generalize the narrow OpenAPI-example restoration hook so null-bearing AI
  updates and schedules examples both remain complete.

### 4. Verification and Review

- [x] Run API, loader, deployment artifact, dashboard navigation, and Docker
  runtime contract tests.
- [x] Run `pip check`, Python compilation, full `make test`, YAML/JSON Schema
  validation, whitespace checks, and `git diff --check`. The YAML parse, Draft
  2020-12 schema/example checks, static/generated parity, and negative probes are
  executable inside `test_openapi_and_path_surface_match_the_draft`, so running
  `scripts/test_api.py` is the named schema-validation command.
- [x] Start Uvicorn on a temporary loopback port and verify the checked-in
  schedules response, exact projection/order, null metadata, no-store, and
  `/healthz`. Same-app repair remains covered by the injectable app test.
- [x] Compare the actual diff with this affected-file list and resolve or explain
  every difference.
- [x] Independently review implementation correctness, API/privacy projection,
  and adversarial test coverage; fix every blocker before completion.
- [x] Record Lens selection evidence, Scribe/Gateway decisions, Builder outcome,
  and Judge verdict in their journals and `.agents/PROJECT.md`.

## Post-Implementation Evidence

- Contract/tests were authored first. The recorded RED run failed at import with
  missing `SCHEDULES_SOURCE_ID`, proving Phase 2E runtime code was absent.
- API tests pass `35/35`, including strict boundaries, fail-soft recovery,
  callback defects, fixed-file audit, generated/static OpenAPI parity, and Draft
  2020-12 example and negative validation.
- Loader tests pass `14/14`; deployment artifact tests `18/18`; dashboard
  navigation `45/45`; Docker runtime contract `10/10`; full `make test` passes.
- Python compilation, `pip check`, YAML parsing, schema validation,
  `git diff --check`, and the pre-bound-socket Uvicorn smoke all pass. The smoke
  returned all ten checked-in schedules in source order with null metadata and
  `Cache-Control: no-store`.
- Plan-to-diff review found no Phase 2E scope drift and no change to the source,
  UI, loader, result artifacts, dependencies, Makefile, Docker, deployment, or
  CI. Pre-existing user knowledge/report files remain untouched.
- Independent runtime/API review passed. Adversarial-test review findings were
  closed by adding exact checked-in HTTP equality, complete `as_of=None` and
  no-store assertions, exact example source IDs/counts, structural `_note`
  checks, and a request-time file-open audit that rejects result reads.
  Adversarial-test and plan/scope re-reviews then passed.

## Verification Commands

```sh
.venv/bin/python scripts/test_api.py
.venv/bin/python scripts/test_artifact_loader.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_docker_runtime_contract.py
.venv/bin/python -m compileall -q api scripts/test_api.py scripts/artifact_loader.py
.venv/bin/python -m pip check
make test
git diff --check
```

The final Uvicorn smoke is executed from the repository root. One Python
orchestrator pre-binds a temporary loopback socket and transfers that exact file
descriptor to Uvicorn. This removes the free-port TOCTOU gap, verifies the
spawned process remains alive, and preserves assertion failures through cleanup:

```sh
.venv/bin/python - <<'PY'
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.bind(("127.0.0.1", 0))
listener.listen()
port = listener.getsockname()[1]
log = open("/tmp/surge-phase2e-uvicorn.log", "w", encoding="utf-8")
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api.main:app", "--fd", str(listener.fileno())],
    stdout=log,
    stderr=subprocess.STDOUT,
    pass_fds=(listener.fileno(),),
)
listener.close()
opener = build_opener(ProxyHandler({}))
base = f"http://127.0.0.1:{port}"
try:
    for _ in range(50):
        if process.poll() is not None:
            raise AssertionError("spawned Uvicorn exited before readiness")
        try:
            with opener.open(f"{base}/healthz", timeout=1) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ok", "apiVersion": "v1"}
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError("Uvicorn did not become ready")

    request = Request(f"{base}/api/v1/system/schedules")
    with opener.open(request, timeout=2) as response:
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        body = json.load(response)
    source = json.loads(Path("content/schedules.json").read_text(encoding="utf-8"))
    assert body == {
        "available": True,
        "reason": "ok",
        "data": {"schedules": source["schedules"]},
        "meta": {
            "sourceId": "system.schedules",
            "asOf": None,
            "generatedAt": None,
        },
    }
    assert "_note" not in body["data"]
finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log.close()
PY
```

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Maintainer `_note` leaks | Exact raw keys, explicit projector, secret-sentinel tests |
| Endpoint expands into operational/private status | One fixed source and DTO; result readers/files are explicit non-goals |
| Duplicate or malformed job IDs confuse clients | Strict identifier pattern plus runtime list-level validator; OpenAPI explicitly discloses the semantic-only uniqueness rule |
| New public result type breaks unnecessarily | Validate syntax, not the current UI fetcher enum |
| Cron note is mistaken for verified schedule semantics | Preserve opaque strings and document no parsing/timezone verification |
| Projector bypasses public checks | Strict post-projection DTO and invalid-object projector oracles |
| Missing state becomes sticky | No API cache, no-store, same-app recovery test |
| Source order changes | Exact ordered deep-equality test |
| Static/generated examples lose null metadata | Generalized narrow OpenAPI-example restoration plus parity/schema tests |

## Rollback

1. Remove the route, envelope, DTOs, registry entry, validators, projector, and
   Phase 2E tests/docs.
2. Restore app/static contract version `1.3.0-draft` and the AI-only OpenAPI
   example hook.
3. Run all Phase 1 through Phase 2D API and deployment verification suites.

No data migration or writer rollback is required because this phase is read-only.

## Traceability Matrix

| Requirement | Acceptance criteria | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-001` | `AC-SCHEDULES-001`, `010`, `012` | Fixed registry and explicit route | Path, ignored-query, OpenAPI tests |
| `REQ-002` | `AC-SCHEDULES-006` | Shared strict loader/unavailable envelope | Failure matrix and health assertions |
| `REQ-003`, `CFR-001`, `CFR-002` | `AC-SCHEDULES-001`-`004` | Exact validator and one-field projector | Root/list/item/privacy boundaries |
| `REQ-004`, `CFR-011` | `AC-SCHEDULES-007`, `012` | Uncached resolver; no provider/result read | Same-app repair and fixed-source tests |
| `CFR-003`-`CFR-007` | `AC-SCHEDULES-004`, `005` | Strict DTO and uniqueness validator | Paired boundary and duplicate-ID oracles |
| `CFR-008` | `AC-SCHEDULES-001`, `002` | Shared metadata after projection | Exact null-metadata tests |
| `CFR-009` | `AC-SCHEDULES-001`, `002`, `012` | Middleware and no-store route | Header/CORS/peer/Host tests |
| `CFR-010` | `AC-SCHEDULES-008`, `009` | Shared callback/exception boundary | Callback and projector matrices |
| `CFR-012` | `AC-SCHEDULES-010`, `011` | Runtime/static version and schema | Contract parity and full regressions |

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | FAIL | OpenAPI could misleadingly imply `uniqueItems` enforces property-level ID uniqueness; whitespace patterns were not pinned for schema parity. | Resolved in v0.2: runtime uniqueness is authoritative and documented without `uniqueItems`; required/optional trim patterns are exact. |
| 2 | FAIL | Contract/feasibility reviewers passed, but adversarial review found missing empty-required-string mutations, incomplete metadata callback cases, examples without independent schema validation, and non-executable no-result-read/schema/Uvicorn evidence. | Resolved in v0.3 with isolated boundaries, the complete as-of matrix, per-document example/negative validation, fixed-path/dependency oracles, a named schema test, and an exact Uvicorn smoke. |
| 3 | FAIL | The smoke block could hide a failed Python assertion behind successful cleanup and could connect to an unrelated process after a bind failure. | Resolved in v0.4 with fail-fast shell semantics, dynamic port selection, spawned-PID liveness checks, and cleanup that preserves failure status. |
| 4 | FAIL | One reviewer passed v0.4, but adversarial review found a remaining free-port TOCTOU window between probing and Uvicorn bind. | Resolved in v0.5 by pre-binding one socket and transferring its live descriptor to Uvicorn via `--fd`; the command was exercised successfully before acceptance review. |
| 5 | PASS | Contract, feasibility, adversarial-test, and targeted pre-bound-socket reviewers found no remaining blocker. | Plan accepted for implementation. |

## Fresh Post-Implementation Review Remediation

A fresh review after the original completion found that Starlette re-raised handled
route exceptions after sending the sanitized HTTP 500. Real Uvicorn therefore
printed the original callback message and traceback to stderr/journal even though
the structured application log and response were sanitized.

The remediation moved pre-response unexpected-exception conversion into the
existing loopback HTTP middleware. A new pre-bound-socket real-Uvicorn regression
proved the original sentinel/traceback leak red, then proved the exact sanitized
response and safe server log green. The API suite now passes 36/36. Two independent
post-fix reviews passed, including repeated runtime, cleanup, and lifespan probes.
The endpoint, DTO, OpenAPI, loopback policy, and expected HTTP 200 unavailable
contract did not change.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-07-15 | Initial contract-first Phase 2E plan. |
| v0.2 | 2026-07-15 | Clarify runtime-only ID uniqueness and pin whitespace schema patterns after first blocker review. |
| v0.3 | 2026-07-15 | Close adversarial boundary, callback, example-validation, fixed-read, and executable-verification blockers. |
| v0.4 | 2026-07-15 | Make the Uvicorn verification fail-fast and resistant to bind/cleanup false passes. |
| v0.5 | 2026-07-15 | Eliminate the smoke-test free-port race with a pre-bound socket transferred through Uvicorn `--fd`. |
| v0.6 | 2026-07-15 | Accept the plan after targeted smoke verification and final blocker review. |
| v1.0 | 2026-07-15 | Record implementation, verification, scope audit, independent review fixes, and completion evidence. |
| v1.1 | 2026-07-15 | Close the fresh-review Uvicorn traceback leak with a pre-response middleware boundary and real-server regression. |
