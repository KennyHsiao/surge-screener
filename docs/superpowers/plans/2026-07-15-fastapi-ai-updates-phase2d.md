# FastAPI AI Updates Phase 2D Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.3 |
| Status | Implemented, verified, and independently reviewed |
| Author | Codex |
| Reviewer | Repository maintainer |
| Audience | Maintainers of the loopback FastAPI boundary |
| Related inventory | `docs/api/fastapi-endpoint-artifact-inventory.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |
| Prior phase | `docs/superpowers/plans/2026-07-14-fastapi-fund-catalog-phase2c.md` |

## Goal

Add `GET /api/v1/system/ai-updates` as the next smallest fixed public read. The
endpoint exposes the manually maintained update feed in `content/ai_updates.json`
without exposing its maintainer `_note`, calling a provider, or weakening the
existing fail-soft and loopback-only behavior.

Success means the checked-in contract, runtime schema, implementation, and tests
agree on one strict public DTO. Missing, half-written, malformed, unreadable, or
shape-invalid feed files remain HTTP 200 unavailable artifact states.

## Architecture Decision

The source is a tracked 1 KB file with one read-only Streamlit consumer and no
runtime writer or path override. The server owns the path; the client supplies no
identifier, path, URL, query, or filter.

The source root contains exactly:

- `_note`: maintainer guidance, validated but never public.
- `updates`: the public ordered update list.

The existing raw-validator -> projector -> strict public DTO pipeline is reused.
The projector returns only `{"updates": source["updates"]}` and preserves list and
tag order. `meta.asOf` is the latest valid update date, or null for an empty feed;
`meta.generatedAt` remains null.

The DTO deliberately keeps dates, links, and tags as their original JSON strings
and lists. A date is a strict string plus a calendar validator, not a Pydantic
`date`; tags remain a list plus a uniqueness validator, not a set. Link validation
uses a string-preserving standard-library parser and never a normalizing URL type.

## Scope

In scope:

- One additive route: `GET /api/v1/system/ai-updates`.
- Exact operation ID: `getAiUpdates`.
- Stable source ID: `system.ai-updates`.
- Fixed source path: `content/ai_updates.json`.
- Exact internal source validation and explicit `_note` projection.
- Strict public update-item DTO, HTTPS-or-empty links, and bounded unique tags.
- Existing HTTP 200 unavailable envelopes and sanitized HTTP 500 problems.
- Immediate recovery after source repair.
- API draft version bump from `1.2.0-draft` to `1.3.0-draft`.
- Contract, unit, HTTP, recovery, metadata, and regression tests.

Out of scope:

- Migrating the Streamlit consumer to FastAPI.
- Editing or generating `content/ai_updates.json`.
- Tag filtering, pagination, sorting, or accepting URLs from clients.
- Schedules, daily-report, COT, retrospective, DuckDB, or aggregate endpoints.
- Closing the inherited global middleware-403 OpenAPI documentation gap.
- Authentication, CORS, rate limiting, TLS, or non-loopback exposure.
- Deployment, Docker, dependency, Makefile, systemd, or CI changes.

## Requirements

- `REQ-001`: The route MUST read only server-owned `content/ai_updates.json` and
  MUST NOT call a provider or select a client-controlled path.
- `REQ-002`: Missing, empty, half-written, malformed, invalid-UTF-8, non-object,
  unreadable, or shape-invalid source data MUST return HTTP 200 with
  `available=false` and MUST NOT affect `/healthz`.
- `REQ-003`: Available data MUST contain exactly one root field, `updates`, and
  each item MUST contain exactly `date`, `title`, `summary`, `link`, and `tags`.
- `REQ-004`: Repairing an unavailable source MUST be visible on the next request
  without waiting for an API cache.
- `CFR-001`: The source root MUST contain exactly `_note` and `updates`; `_note`
  MUST be a string no longer than 2,000 characters and MUST never be returned.
- `CFR-002`: `updates` MUST be an array with at most 200 object items. An empty
  array is valid. A non-array value or non-object item is `invalid_shape`, never a
  projector defect. Source order MUST be preserved.
- `CFR-003`: Each `date` MUST remain a strict JSON string matching
  `^\d{4}-\d{2}-\d{2}$`, pass calendar validation, and be documented as OpenAPI
  `type=string`, `format=date`. It MUST NOT be coerced from another type or date
  notation. `title` MUST be 1-200 characters and `summary` MUST be 1-2,000
  characters.
- `CFR-004`: `link` MUST remain an exact source string no longer than 2,048
  characters. Empty is valid. A non-empty link MUST start with lowercase
  `https://`, contain a non-empty authority and hostname, contain no whitespace,
  C0/DEL control character, or userinfo, and parse without an invalid port or
  authority. Path, query, fragment, port, IPv4, IPv6, and IDN hosts remain
  allowed. Host validation is syntactic only: it performs no DNS lookup or host
  allowlisting. Runtime validation MUST return the original string without URL
  normalization. OpenAPI MUST expose an outer bounded string with `anyOf` branches
  for `const: ""` and an HTTPS IRI matching
  `^https://[^/@?#\s\x00-\x1f\x7f]+(?:[/?#][^\s\x00-\x1f\x7f]*)?$`.
  The non-empty branch uses `format: iri`, not `uri`, because raw IDN hosts are
  allowed. Its description MUST state that parser-enforced authority, hostname,
  userinfo, and port checks are intentionally stricter than the schema pattern.
- `CFR-005`: `tags` MUST be an array of at most 20 unique strings. Each tag MUST
  be 1-50 characters with no leading or trailing whitespace. Numbers, booleans,
  nulls, missing fields, and extra item fields are invalid shapes.
- `CFR-006`: Available metadata MUST use `sourceId=system.ai-updates`, the maximum
  update date as `asOf`, and null `generatedAt`; an empty feed has null `asOf`.
- `CFR-007`: Responses MUST retain `Cache-Control: no-store`, loopback peer/Host
  enforcement, and the absence of CORS.
- `CFR-008`: Resolver, validator, projector, or metadata-extractor programming
  defects and invalid callback return types MUST reach the sanitized RFC 9457
  HTTP 500 handler, not be mislabeled as expected artifact unavailability. A
  validator's exact built-in `False` and a projected object that fails the DTO
  remain HTTP 200 `invalid_shape`. An as-of callback's `None` is a valid shared
  return type needed by empty feeds; the built-in AI-updates extractor MUST return
  it only for an empty `updates` list.
- `CFR-009`: The route MUST add no provider/network I/O and no API response cache.
  The inherited loopback target (P95 <= 500 ms, P99 <= 1,000 ms) remains an
  operational objective, not a benchmark claim or completion gate for this
  additive phase.
- `CFR-010`: Checked-in OpenAPI and FastAPI app version MUST be
  `1.3.0-draft`; the URL and health major remain `v1`.

## Acceptance Criteria

- `AC-AIUPDATES-001`: Given the checked-in source, when requested, then HTTP 200
  returns all current updates in source order, exact values, latest-date metadata,
  and no `_note`.
- `AC-AIUPDATES-002`: Given `{"_note":"","updates":[]}`, when requested, then
  HTTP 200 returns an available empty feed with null timestamps and no-store.
- `AC-AIUPDATES-003`: Given missing source keys, an unknown root key, or an
  invalid `_note`, when requested, then HTTP 200 returns `invalid_shape` without
  reflecting source values.
- `AC-AIUPDATES-004`: Given an invalid item date, field type, missing/extra field,
  zero/over-limit length, non-HTTPS/relative/hostless/userinfo link,
  whitespace/control-bearing link, invalid/duplicate tag, non-list `updates`,
  non-object item, or too many tags/updates, then HTTP 200 returns
  `invalid_shape`.
- `AC-AIUPDATES-005`: Given a missing file, then HTTP 200 reason is `missing`;
  empty/truncated/malformed/invalid-UTF-8/non-finite JSON maps to `invalid_json`;
  a non-object or DTO-invalid value maps to `invalid_shape`; and a read `OSError`
  maps to `unreadable`. `/healthz` remains healthy in every case.
- `AC-AIUPDATES-006`: Given a half-written source followed by a valid replacement,
  when two requests use one app instance, then the first is unavailable and the
  second is available without `_note`.
- `AC-AIUPDATES-007`: Given valid update dates in any source order, metadata
  `asOf` equals the maximum date without reordering the public list.
- `AC-AIUPDATES-008`: Given a raising resolver/validator/projector/as-of callback,
  a resolver returning the wrong result type, validator returning `None` or `1`,
  projector returning list/scalar/null, or as-of returning a non-string or
  impossible/non-ISO date, then the exact sanitized HTTP 500 problem is returned
  with `application/problem+json`, no-store, and no callback/source detail in the
  response or structured log. Validator `False` remains HTTP 200 `invalid_shape`.
- `AC-AIUPDATES-009`: Given an object projector result that violates the public
  DTO, then HTTP 200 returns `invalid_shape`, distinct from non-object projector
  defects.
- `AC-AIUPDATES-010`: Generated and checked-in OpenAPI MUST agree on route,
  operation ID, zero parameters, 200/500 responses, schema constraints, examples,
  `_note` absence, and version `1.3.0-draft`.
- `AC-AIUPDATES-011`: Existing API, loader, dashboard, deployment, and Docker
  contract tests MUST remain green.
- `AC-AIUPDATES-012`: Supplying ignored `path`, `url`, or `tag` query keys MUST
  not change the fixed source or response; the new route itself MUST retain
  loopback peer/Host rejection and no CORS headers.

## Response Contract

```json
{
  "available": true,
  "reason": "ok",
  "data": {
    "updates": [
      {
        "date": "2026-05-23",
        "title": "DEoT / P1Agent 架構回顧",
        "summary": "公開摘要",
        "link": "https://arxiv.org/abs/2504.07872",
        "tags": ["DEoT", "架構"]
      }
    ]
  },
  "meta": {
    "sourceId": "system.ai-updates",
    "asOf": "2026-05-23",
    "generatedAt": null
  }
}
```

Expected source failures use the existing HTTP 200 unavailable envelope. The
route has no parameters and adds no 422 contract. Unexpected implementation
defects use the existing sanitized HTTP 500 problem. All responses are no-store.

## Affected Files

Create:

- `docs/superpowers/plans/2026-07-15-fastapi-ai-updates-phase2d.md`

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

- `content/ai_updates.json`, Streamlit UI, artifact loader, provider code,
  dependencies, Makefile, Docker files, deployment/systemd files, or CI.

The inventory edit retains the existing P1 whitelist row and changes only the AI
Updates disposition text to record implementation in Phase 2D.

## Dependencies and Feasibility

- Existing Pydantic v2 `field_validator` and JSON Schema extras provide strict
  calendar/list validation and `format`/`uniqueItems`/`anyOf` annotations.
- `urllib.parse.urlsplit` plus an explicit full-match validator checks the URL
  without transforming it. Pydantic `HttpUrl`/`AnyUrl` are intentionally not used.
- The raw validator checks exact root keys and `updates` list/item container types
  before the projector, so expected source shapes cannot become projector 500s.
- No package, provider, writer, migration, or deployment change is required.

## Implementation Checklist

### 1. Contract and Red Tests

- [x] Add the System tag, parameterless route, response components, strict public
  schemas, realistic available/empty examples, and version `1.3.0-draft`.
- [x] Add independent generated-vs-static OpenAPI assertions for field sets,
  constraints, strict-string date format/pattern, link `anyOf`, tag pattern and
  `uniqueItems`, no 422, and `_note` absence.
- [x] Deep-equal the real public data to `{"updates": source["updates"]}` and
  assert exact latest-date metadata without list reordering.
- [x] Add paired boundaries: 0/200/201 updates; title 0/1/200/201; summary
  0/1/2,000/2,001; valid-host link empty/HTTPS/2,048/2,049; tags 0/20/21 and tag
  length 0/1/50/51.
- [x] Accept a leap date and reject impossible/non-leap, datetime, unpadded,
  compact/basic, week-date, full-width, numeric, boolean, and null date values.
- [x] Accept representative HTTPS host/path/query/fragment values without
  normalization. Reject relative/HTTP/uppercase-scheme, bare `https://`, hostless,
  userinfo, whitespace, C0/DEL, and wrong-type links. Named malformed cases MUST
  include unmatched IPv6 brackets, nonnumeric and out-of-range ports, and empty or
  trailing-colon authority.
- [x] Reject missing/extra item fields, wrong types, duplicate tags, `updates` as
  object/scalar/null or with a non-object item, invalid source keys, and `_note`
  2,000/2,001.
- [x] Add HTTP failure matrix, health independence, no-store, secret omission,
  same-app recovery, source-order preservation, and maximum-date metadata tests.
- [x] Execute the full callback matrix from `AC-AIUPDATES-008`, including exact
  500 body/media/no-store/log assertions; separately prove validator `False` and
  invalid projected objects (root extra, nested wrong type/extra) are 200
  `invalid_shape`.
- [x] Update `EXPECTED_REGISTRY`, `EXPECTED_PATHS`, `SOURCE_PATHS`, and
  `_http_registry()` together, including a fixed-resolver-path assertion and
  endpoint-specific ignored-query/loopback/Host/no-CORS probes.
- [x] Register every new test in the manual `main()` list.
- [x] Run API tests and record a red failure caused by absent Phase 2D runtime code.

### 2. Models and Functional Core

- [x] Add strict `AiUpdateItem` and `AiUpdatesData` DTOs with no extra fields.
- [x] Keep `date` as strict `str` with regex/calendar validation and schema
  `format=date`; keep `tags` as `list[str]` with a uniqueness validator and schema
  `uniqueItems=true`; keep `link` as a source-preserving string validator.
- [x] Add fixed constants, source validator, public projector, and latest-date
  extractor for `system.ai-updates`.
- [x] Reuse the shared exact-bool/projector/DTO pipeline without changing existing
  artifact behavior.

### 3. HTTP Route

- [x] Add `AiUpdatesEnvelope` and `GET /api/v1/system/ai-updates` using the fixed
  registry entry and existing no-store/200/500 behavior.
- [x] Add the source ID to the required fixed registry set.
- [x] Keep the route parameterless and retain loopback/CORS behavior.

### 4. Verification and Review

- [x] Run API, loader, deployment artifact, dashboard navigation, and Docker
  runtime contract tests.
- [x] Run `pip check`, Python compilation, full `make test`, whitespace checks,
  and `git diff --check`.
- [x] Start Uvicorn on temporary loopback ports and verify real available,
  injected missing, recovery metadata, no-store, and `/healthz` behavior.
- [x] Compare the actual diff with the affected-file list and resolve drift.
- [x] Independently review implementation correctness, API/security projection,
  and adversarial test coverage; fix every blocker before completion.
- [x] Record the Lens endpoint-selection evidence, Scribe/Gateway contract
  decisions, Builder implementation outcome, and Judge review result in their
  existing journals and `.agents/PROJECT.md`.

## Post-Implementation Verification

- The red API run failed for the intended missing `AI_UPDATES_SOURCE_ID` before
  any Phase 2D runtime code was added.
- API tests pass `30/30`; loader tests pass `14/14`; deployment artifact tests
  pass `18/18`; dashboard navigation tests pass `45/45`; Docker runtime contract
  tests pass `10/10`; the full `make test` suite passes.
- `pip check`, Python compilation, checked-in YAML/JSON Schema validation,
  whitespace checks, and `git diff --check` pass. Static and generated schemas
  both accept valid envelopes and reject an extra available-envelope field.
- A real Uvicorn same-app probe returned HTTP 200 `missing` on the injected first
  read and the exact checked-in feed on the next read; `/healthz` stayed healthy,
  metadata recovered to `2026-05-23`, and every response used no-store.
- Independent runtime/API, scope, and adversarial-test reviewers returned PASS
  after closing false-positive 21-tag and max-date oracles, the composed static
  envelope closure gap, and the missing one-character-tag positive boundary.
- The Phase 2D changes match the affected-file list. No source artifact,
  Streamlit UI/loader, provider, dependency, Makefile, Docker, deployment,
  systemd, or CI behavior changed; pre-existing user knowledge and sector
  snapshot files were left untouched.
- `openapi-spec-validator` was not installed, so that optional extra validator
  could not run; PyYAML parsing, Draft 2020-12 schema checks, independent schema
  validation, generated/static parity tests, and HTTP probes passed instead.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Maintainer `_note` leaks | Exact raw keys, explicit projector, deep-equality and secret-sentinel tests |
| Unsafe future link scheme reaches frontend | Empty-or-HTTPS strict pattern and negative scheme/whitespace tests |
| Invalid/coerced dates corrupt metadata | Preserved strict string, regex/calendar validator, schema parity, then max-date extraction |
| URL type normalizes or accepts hostless links | Raw-string regex + `urlsplit` authority/host/control/userinfo checks; exact-value tests |
| Projector weakens item checks | Strict projected DTO and invalid-object projector oracle |
| Missing state becomes sticky | No API cache, no-store, same-app recovery test |
| Source order changes unexpectedly | Projector preserves the list; test compares exact ordered values |
| API is mistaken for live news | Description states manually maintained file and no provider call |

## Rollback

1. Remove the route, envelope, DTOs, registry entry, validators, projector,
   metadata extractor, and Phase 2D tests/docs.
2. Restore app/static contract version `1.2.0-draft`.
3. Run the Phase 1/2A/2B/2C API and deployment verification suites.

No data migration or writer rollback is required because the phase is read-only.

## Traceability Matrix

| Requirement | Acceptance criteria | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-001` | `AC-AIUPDATES-001`, `010`, `012` | Fixed registry resolver and explicit route | Registry path, ignored-query, OpenAPI tests |
| `REQ-002` | `AC-AIUPDATES-005` | Shared strict loader and unavailable envelope | Exact failure-reason HTTP matrix and health |
| `REQ-003`, `CFR-001`, `CFR-002` | `AC-AIUPDATES-001`-`004` | Exact raw validator and one-field projector | Root/list/item boundaries and secret omission |
| `REQ-004`, `CFR-009` | `AC-AIUPDATES-006`, `012` | Uncached fixed-file resolver; no provider | Same-app repair and fixed-source inspection |
| `CFR-003`, `CFR-004`, `CFR-005` | `AC-AIUPDATES-004` | Strict string/list DTO validators | Date/link/tag positive-negative oracles |
| `CFR-006` | `AC-AIUPDATES-002`, `007` | Latest-date extractor after DTO validation | Empty/max-date/order tests |
| `CFR-007` | `AC-AIUPDATES-001`, `002`, `012` | Existing middleware and no-store routes | Header/CORS/peer/Host tests |
| `CFR-008` | `AC-AIUPDATES-008`, `009` | Existing fail-soft/exception boundary | Executable callback and projector matrix |
| `CFR-010` | `AC-AIUPDATES-010`, `011` | Static/runtime version and route schema | OpenAPI parity and full regressions |

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | FAIL | Date/set representation unsafe; URL authority and preservation underspecified; root-shape, zero/date, callback, registry-fixture, latency, and traceability oracles incomplete. | Resolved in v1.1 with strict preserved strings/lists, deterministic URL rules, exact matrices, synchronized fixtures, non-gating latency wording, and complete traceability. |
| 2 | PASS | Contract/security, implementation-feasibility, and adversarial-test reviewers found no blockers. | Plan accepted; nonblocking IRI/schema-description and test-specimen clarifications incorporated in v1.2. |

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-07-15 | Initial contract-first Phase 2D plan |
| v1.1 | 2026-07-15 | Resolve first-round contract, feasibility, and adversarial test blockers. |
| v1.2 | 2026-07-15 | Accept plan after second review; clarify IRI schema, syntactic host validation, inventory edit, and named URL cases. |
| v1.3 | 2026-07-15 | Record implementation, verification, scope audit, and independent blocker closure. |
