# FastAPI Options Flow Feed Phase 2J Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Type | Implementation checklist and API contract plan |
| Version | v0.11 |
| Status | Implemented; verified; independent post-implementation reviews PASS |
| Author | Codex |
| Reviewer | Repository maintainer plus independent contract/test reviewers |
| Audience | API, frontend, test, security, and operations maintainers |
| Prior phase | `2026-07-15-streamlit-iv-history-api-phase2i.md` |
| Future consumer | A separate Phase 2K may migrate only `ui/options_flow.py` |

## Outcome

Add one strict, read-only projection of the current Options Flow feed at
`GET /api/v1/signals/options-flow/feed`. The endpoint reads the same fixed
`reports/options_flow/latest.json` artifact as the compatibility route, but
returns only a bounded, frontend-safe feed contract. It includes every field the
standalone Options Flow page needs plus source provenance fields required to
derive and audit the shared response metadata.

The existing `GET /api/v1/signals/options-flow/latest` route remains byte-shape
compatible with its current source-preserving contract. Phase 2J changes no
Streamlit consumer. This resolves the contract blocker found after Phase 2I
without combining API design and frontend migration in one batch.

## Context and Selection

Phase 2I passed a fresh independent review with zero findings and its focused
suite remains 15/15. The remaining six original artifact routes use
`ArtifactDataModel(extra="allow")` and nested `list[dict[str, object]]` records.
They do not guarantee the fields their Streamlit pages consume. Directly moving
an entire page onto one of those compatibility DTOs would make the frontend
depend on undocumented source shape.

Options Flow is the smallest useful strict projection because its source is one
fixed, read-only artifact; its writer defines one centralized root and signal
shape; its standalone page has one artifact entry; and the API read performs no
provider call, refresh, write, or per-ticker fan-out.

## Glossary

- **compatibility route:** the existing `/latest` route that preserves source
  fields and permits additional properties.
- **feed projection:** the new allowlisted response shape for frontend use.
- **authoritative unavailable:** HTTP 200 with `available=false`; the expected
  source slot was inspected safely and is not a server failure.
- **source validation:** checks applied before projecting a stored artifact.
- **public DTO:** the exact response data model after projection.

## Scope

### In scope

- Additive `/api/v1/signals/options-flow/feed` GET route under the existing `v1`
  URL strategy.
- Exact source-root validation, bounded signal count, and allowlist projection.
- Strict public root, signal, nested-strike, date, ticker, text, numeric, count,
  order, and uniqueness constraints.
- Existing fail-soft `available=false` behavior for missing, partial/malformed,
  unreadable, and shape-invalid artifacts.
- `Cache-Control: no-store`, loopback/Host enforcement, sanitized 500 behavior,
  and immediate recovery on the next request.
- Checked-in and generated OpenAPI parity, realistic available/empty/unavailable
  examples, and additive draft version `1.5.0-draft`.

### Non-goals

- No change to `/api/v1/signals/options-flow/latest` or its loose DTO.
- No `ui/_read_api.py` or `ui/options_flow.py` change; Phase 2K owns adoption.
- No migration of Today Decision, Options Cockpit, Trade State, or Radar.
- No provider, writer, Telegram, artifact, cache, job, deployment, Docker,
  dependency, navigation, or UI/UX redesign change.
- No authentication, non-loopback bind, CORS expansion, rate limiter, pagination,
  refresh action, paid-feed integration, or new client-controlled parameter.

## Contract Design

### Operation

`GET /api/v1/signals/options-flow/feed`

- Parameters: none.
- Operation ID: `getOptionsFlowFeed`.
- Envelope/data source ID: `signals.options-flow.feed`.
- Success and expected artifact failures: HTTP 200 JSON.
- Unexpected implementation defects: sanitized RFC 9457 HTTP 500.
- Headers: `Cache-Control: no-store` on every response.
- Security tier: unchanged loopback peer plus loopback Host allowlist; no CORS
  middleware and no authentication because non-loopback exposure remains denied.
- Latency objective: local fixed-file read P95 <= 500 ms and P99 <= 1000 ms;
  verification must prove no provider/network callback is reachable.
- Rate limiting: unchanged and intentionally absent for the loopback-only,
  parameter-free read. Non-loopback deployment requires a separate design.

### Public data fields

The response data contains exactly:

- `generated_at`, `as_of`, `provider`, `universe_size`, `min_notional`,
  `signal_count`, and source-ordered `signals`;
- each signal contains exactly `ticker`, `direction`, `flow_score`,
  `est_notional_usd`, `biggest`, `expiry`, `max_voi`, `high_voi_strikes`,
  `call_put_ratio`, `put_call_ratio`, and `tags`;
- `biggest`, when present, contains exactly the two page-consumed fields
  `strike` and `notional`.

`generated_at` and `as_of` are retained in data because the shared artifact
reader derives envelope metadata from validated public data and parity is
checked explicitly. Source `note`, biggest premium/volume/VOI, per-signal
provider, raw volume totals, spot, and any future unallowlisted signal fields are
never returned. The public data/envelope schemas use `additionalProperties:
false` (or generated equivalent). The compatibility route continues using
`additionalProperties: true`.

### Exact field constraints

| Field | Public type and boundary |
| --- | --- |
| `generated_at` | required string, 20-32 chars, timezone-aware RFC 3339 with 0-6 fractional-second digits so shared datetime metadata preserves the exact instant |
| `as_of` | required `YYYY-MM-DD` string and real calendar date |
| `provider` | required 1-64 char ASCII identifier matching the full-string grammar `^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`; trailing newlines are forbidden |
| `universe_size` | strict integer, `0..10000` |
| `min_notional` | strict integer, `1..1000000000000` |
| `signal_count` | strict integer, `0..10000` |
| `signals` | required source-ordered array, `0..200` items; more than 200 makes the source `invalid_shape`, with no truncation |
| `ticker` | required uppercase ASCII ticker, 1-15 chars, matching the full-string grammar `^[A-Z0-9]+(?:[.-][A-Z0-9]+)*`; trailing newlines are forbidden |
| `direction` | required enum `bullish` or `bearish` |
| `flow_score` | required finite JSON number (integer or fractional), `0..100` |
| `est_notional_usd` | required strict integer, `1..1000000000000000` |
| `biggest` | required object or null; when an object, both `strike` and `notional` keys are required and are its only public keys |
| `biggest.strike` | required finite JSON number (integer or fractional) or null; when present, `> 0` |
| `biggest.notional` | required finite JSON number (integer or fractional) or null; when present, `> 0` and `<= 1000000000000000` |
| `expiry` | required real `YYYY-MM-DD` string or null |
| `max_voi` | required finite JSON number (integer or fractional), `0..1000000000` |
| `high_voi_strikes` | required strict integer, `0..100000` |
| `call_put_ratio` / `put_call_ratio` | required finite JSON number (integer or fractional) in `0..1000000000`, or null |
| `tags` | required array, `0..20` unique strings; each 1-100 chars with no surrounding whitespace |

### Runtime invariants

- Source root keys are exactly `generated_at`, `as_of`, `provider`,
  `universe_size`, `min_notional`, `signal_count`, `note`, and `signals`.
  Source `note` accepts any JSON string, including whitespace, of `0..2000`
  characters and is then omitted. Any extra/missing root key is `invalid_shape`.
- The source `signals` list itself MUST have at most 200 entries. The API never
  silently truncates it. Exactly 200 is valid and 201 is `invalid_shape`.
- Every source signal MUST contain all eleven public signal keys listed above.
  Nullable values remain required keys and may explicitly be null only where the
  field table permits it. A non-null source `biggest` object MUST contain
  `strike` and `notional`; missing required source keys are `invalid_shape`.
- Signal dictionaries and non-null `biggest` objects may additionally contain
  writer/source-only keys. Those values are deliberately not interpreted or
  validated, are dropped before strict DTO validation, and are never returned or
  logged. This is the only nested extra-field allowance; public DTOs remain
  exact.
- At most 20 unique bounded tags are accepted per signal.
- Tickers are uppercase ASCII symbols using the shared 15-character grammar and
  are unique within one feed.
- Every field satisfies the exact type, nullability, length, pattern, and numeric
  boundary table above. Runtime validation performs no string/number/container
  coercion; booleans never satisfy integer/number fields. JSON integer values are
  accepted by fields described as JSON numbers, while strict-integer fields
  reject fractional values.
- `as_of` and optional expiry strings are real ISO calendar dates.
- `generated_at` is timezone-aware RFC 3339.
- Signals remain in non-increasing `flow_score` order.
- `len(signals) <= signal_count <= universe_size`.
- An empty returned list with `signal_count > 0` is valid (for example, a writer
  run with `--top 0`) provided the count invariant holds; it is distinct from the
  canonical empty example where both counts are zero.
- Available `meta.asOf` serializes to the same `YYYY-MM-DD` value as data
  `as_of`. `meta.generatedAt` and data `generated_at` MUST parse to the same
  timestamp instant; lexical spellings may differ because Pydantic serializes a
  UTC metadata datetime with `Z` while the stored data string may use `+00:00`.
  Unavailable metadata is null because no validated source data was accepted.
- OpenAPI enforces field types, nullability, local bounds, patterns, exact public
  properties, list sizes, and tag uniqueness. Cross-field count consistency,
  ticker-key uniqueness, score ordering, and timestamp-instant equivalence are
  explicitly runtime-only invariants and MUST be covered by executable tests;
  the schema MUST NOT claim `uniqueItems` enforces ticker uniqueness.

## Requirements

- `REQ-2J-001`: The new route MUST be additive and MUST leave `/latest`
  behavior and schema unchanged.
- `REQ-2J-002`: The endpoint MUST read only the fixed registered artifact and
  MUST never call a provider, refresh job, writer, notifier, or client URL.
- `REQ-2J-003`: Expected missing, partial/malformed, unreadable, or invalid-shape
  sources MUST return HTTP 200 unavailable envelopes and MUST recover on the
  next request without negative caching.
- `REQ-2J-004`: Available responses MUST expose only the exact public fields and
  satisfy every runtime invariant above.
- `REQ-2J-005`: Empty `signals` with consistent zero counts MUST remain an
  available feed, not an unavailable state.
- `CFR-2J-001`: Loopback/Host, no-CORS, no-store, and sanitized 500 behavior MUST
  remain identical to the existing API.
- `CFR-2J-002`: Static and generated OpenAPI MUST agree on route, operation ID,
  schemas, examples, errors, and version `1.5.0-draft`.
- `CFR-2J-003`: No response or log may expose the source note, unallowlisted
  signal fields, paths, raw data, callback details, or exception messages.
- `CFR-2J-004`: Python 3.10 grammar and current pinned dependencies MUST remain
  sufficient; no package change is allowed.

## Given/When/Then Acceptance Criteria

- `AC-2J-001`: Given a valid source, when `/feed` is read, then HTTP 200 returns
  exact projected data, matching metadata, no-store, and no private/source-only
  fields.
- `AC-2J-002`: Given a valid empty source, when `/feed` is read, then it returns
  `available=true`, `signal_count=0`, and an empty signal list.
- `AC-2J-003`: Given each expected file failure, when `/feed` is read, then it
  returns the matching unavailable reason and API health remains `ok`.
- `AC-2J-004`: Given invalid roots, fields, dates, numbers, counts, order,
  duplicate tickers/tags, or nested shapes, when read, then the result is
  `invalid_shape` without raw detail.
- `AC-2J-004A`: Given 200 valid source signals, the feed is available and
  preserves their order; given 201, it is `invalid_shape` with no truncation.
  Given zero stored signals and a positive consistent `signal_count`, the feed
  remains available and preserves that count.
- `AC-2J-005`: Given one unavailable read followed by repaired data, when read
  again, then the second response is immediately available.
- `AC-2J-006`: Given a valid exact-root source containing the writer's current
  source-only signal fields, when `/latest` is read, then its current
  source-preserving output remains unchanged; `/feed` omits those fields. Given
  an extra root field, `/feed` returns `invalid_shape`.
- `AC-2J-007`: Given static and generated OpenAPI, when validated, then both
  accept all documented examples, reject extra/missing fields, and expose the
  same route/version/operation contract.
- `AC-2J-008`: Given injected resolver/validator/projector/callback defects,
  when the route is read, then the response is sanitized HTTP 500 and logs hold
  only fixed context plus exception class.
- `AC-2J-009`: A validator returning exactly `False` yields fail-soft HTTP 200
  `invalid_shape`; a validator returning `None`, an integer, or throwing, a
  resolver returning the wrong type or throwing, and a projector returning any
  non-object (`None`, `False`, scalar, or list) or throwing yield sanitized HTTP
  500. A projected object that fails the strict DTO yields HTTP 200
  `invalid_shape`. No injected sentinel may reach response or logs.

## Affected Files

### Create

- this plan document.

### Modify

- `docs/api/quant-radar-v1.openapi.yaml` — contract first: additive path,
  responses, examples, strict schemas, and version.
- `api/models.py` — strict public Options Flow feed DTOs and invariants.
- `api/artifacts.py` — fixed source constants, validator, projector, and registry
  entry.
- `api/main.py` — typed envelope, examples, route, registry requirement, and
  version.
- `scripts/test_api.py` — red contract/HTTP/fail-soft/security/OpenAPI tests.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — record the strict endpoint
  and keep every frontend consumer local.
- `.agents/gateway.md`, `.agents/scribe.md`, `.agents/builder.md`, `.agents/lens.md`,
  and `.agents/PROJECT.md` — append design and verification evidence only.

`.agents/judge.md` is intentionally not modified: the Judge skill is not used in
this phase, and independent review evidence is recorded in this plan and the
four participating skill journals above. The newly created plan is reviewed as
a `/dev/null`-to-current diff; it has no pre-existing baseline copy.

### Regression-only

- `ui/**`, `scripts/options_flow_scan.py`, existing provider/writer tests,
  deployment and Docker files, dependencies, and the separate UI/UX plan.

The dirty-worktree baseline for pre-existing affected files is
`/tmp/surge-phase2j-baseline-20260715-4voLxo/`. Phase-only review uses
baseline-to-current diffs, not repository `HEAD` alone.

## Test-First Tasks

1. Update the checked-in OpenAPI contract before runtime implementation.
2. Add red tests for the new registry key, route, version, exact schema, examples,
   source projection, old-route compatibility, invalid boundaries, fail-soft
   recovery, callback sanitization, dependency-free fixed read, strict
   no-coercion behavior, required nullable keys, 200/201 list boundaries, and the
   valid `signals=[]`/positive-count case.
   The matrix MUST also assert each reason mapping: absent path -> `missing`;
   truncated or syntactically malformed JSON -> `invalid_json`; a real read
   permission failure -> `unreadable`; non-object/root/field/invariant failures
   -> `invalid_shape`; and every expected unavailable state -> immediate recovery
   after repairing the same path.
3. Run `scripts/test_api.py` and record the expected red failure before code.
4. Add strict DTOs, source validation/projection, typed route, and examples with
   the smallest implementation that turns the focused suite green.
5. Run API and related regressions, contract validators, compatibility gates,
   mutation oracles, and independent reviews.
6. Compare the final baseline diff to this affected-file list; fix or explain
   every divergence before marking the plan implemented.

## Verification Gates

1. `.venv/bin/python scripts/test_api.py`
2. `.venv/bin/python scripts/test_artifact_loader.py`
3. `.venv/bin/python scripts/test_ui_read_api.py`
4. `.venv/bin/python scripts/test_ui_ai_updates_api.py`
5. `.venv/bin/python scripts/test_ui_fund_catalog_api.py`
6. `.venv/bin/python scripts/test_ui_iv_history_api.py`
7. `.venv/bin/python scripts/test_options_flow_scan.py`
8. `.venv/bin/python scripts/test_dashboard_navigation.py`
9. `make test`
10. `.venv/bin/python -m compileall -q api scripts ui`
11. Parse every changed Python file with `ast.parse(..., feature_version=(3, 10))`.
12. `.venv/bin/python -m pip check`
13. Validate checked-in OpenAPI with Draft 2020-12 `$ref` resolution and compare
    its path/schema/examples to `create_app().openapi()`.
14. `git diff --check`
15. Baseline-to-current affected-file and untouched-UI/provider/writer audit.
16. Deliberate mutation oracles for projection privacy, count/order/uniqueness,
    old-route compatibility, unavailable recovery, and no-store.
17. Collision-safe real-Uvicorn smoke on an owned free port; never stop an
    unowned process. Verify `/feed`, `/latest`, `/healthz`, no-store, fail-soft
    recovery, and sanitized logs without calling a provider.
18. Independent correctness/security, contract, test-strength, maintainability,
    and scope reviews; fix all blocking findings before completion.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Tightening breaks old clients | New additive route and explicit `/latest` parity oracle |
| Extra source fields leak | Exact root validation plus allowlist projection and strict public DTO |
| Invalid nested values crash response serialization | Validate complete projected DTO before returning available |
| A valid empty feed becomes unavailable | Dedicated zero-count example and runtime test |
| Metadata drifts from payload | Extract both from projected fields; assert exact date equality and parse timestamps to the same instant |
| Hidden provider/network work | Fixed resolver plus import/callback/static and runtime no-call tests |
| Source can be large before validation | Bound public list to 200 and document that global pre-parse file-size bounds remain separate work |
| Dirty worktree hides drift | Captured baseline and exact phase-only review |

## Rollback

Rollback is code-only and data-preserving: remove the new `/feed` path and its
route examples, DTOs, validator/projector and registry key; remove only the new
static OpenAPI path/components/examples and restore `1.4.0-draft` in static and
runtime documents; remove only Phase 2J tests and inventory/journal entries; and
delete this newly created plan. Do not alter `/latest`, the artifact file, the
writer, providers, Streamlit, deployment, dependencies, or any unrelated dirty
worktree change. Re-run the API, artifact-loader, UI client, Options Flow writer,
dashboard, full `make test`, compile/AST, dependency, OpenAPI, and diff gates to
prove the prior surface is restored.

## Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| `REQ-2J-001`, `AC-2J-006` | additive registry/route | old/new route parity and OpenAPI diff |
| `REQ-2J-002` | fixed resolver | no provider/writer/dependency tests |
| `REQ-2J-003`, `AC-2J-003`, `005` | shared fail-soft reader | file-state and recovery matrix |
| `REQ-2J-004`, `005`, `AC-2J-001`, `002`, `004` | validator, projector, strict DTO | boundary and schema tests |
| `CFR-2J-001`, `003`, `AC-2J-008` | existing middleware and typed route | loopback/no-store/sanitized defect tests |
| `CFR-2J-002`, `AC-2J-007` | checked-in/generated OpenAPI | parity and example validators |
| `CFR-2J-004` | Python-only implementation | compile, 3.10 AST, dependency gates |

## Pre-Implementation Review

- User authorization: review the prior phase and continue the next safe phase.
- Prior phase closure: PASS with no current finding.
- Direct loose-DTO consumer migration: blocked; this additive projection resolves
  that blocker without weakening the compatibility route.
- Breaking-change assessment: additive endpoint and draft minor version only;
  existing request/response contracts are unchanged.
- Security: loopback-only, read-only, parameter-free, public allowlist, no new
  credentials or non-loopback authority.
- Rollback: fully specified above across runtime, contract, tests, inventory,
  journals, and regression gates; no data, provider, frontend, or deployment
  rollback.
- Review 1 reported one blocking formulation plus overlapping HIGH/MEDIUM/LOW
  contract findings. v0.2 resolved field constraints, 200-item semantics,
  stable identifiers, and root/projection ambiguity. v0.3 additionally makes
  source required-key behavior, numeric no-coercion rules, positive-count empty
  lists, provenance-field rationale, journal scope, and full rollback executable.
- v0.4 defines timestamp equivalence, distinguishes schema-expressible from
  runtime-only invariants, and makes the file-state/callback mutation matrix
  normative rather than leaving test categories implicit.
- Post-implementation schema review found that JSON Schema `$` may match before
  a final newline even though Pydantic rejects that value. v0.8 gives generated
  and static schemas absolute-end patterns for feed dates, timestamps, provider,
  ticker, and tags, plus newline mutation oracles, without passing unsupported
  lookahead syntax to Pydantic's runtime regex engine.
- v0.9 closes the remaining timestamp mutation gap with regex-valid but
  calendar-invalid and hour-invalid runtime cases plus a static/generated
  clock-range rejection oracle. Real calendar-date semantics remain a runtime
  validator rule because JSON Schema format implementations are not uniformly
  assertion-capable.
- v0.10 adds an explicit valid equal-score ordering case, preventing a future
  mutation from tightening non-increasing order into strict decrease and making
  the current tied-score artifact unavailable.
- Independent closure review: PASS from contract/scope and implementation/scope
  reviewers with zero remaining BLOCKER, HIGH, or MEDIUM findings.
- Test-feasibility closure review also passed with zero BLOCKER/HIGH. Its sole
  non-blocking MEDIUM wording finding (timestamp lexical equality) is fixed in
  v0.6; new tests must also be registered in the script's manual `main()` list.
- Post-implementation adversarial review found that the earlier 64-character
  timestamp bound allowed precision beyond Python metadata's microseconds. v0.7
  closes that contract bug with an explicit 0-6 fractional-digit pattern and a
  32-character maximum; the current writer remains valid and exact-instant
  parity is now representable.

## Post-Implementation Closure

- Actual functional changes match the accepted affected-file list: strict DTOs,
  fixed registry validator/projector, typed route/examples, static OpenAPI,
  tests, inventory, this plan, and the five evidence journals. No Streamlit,
  provider, writer, dependency, deployment, Docker, or UI/UX-plan file changed
  in Phase 2J.
- The `/latest` route/model/static components and source-preserving behavior were
  compared with the captured baseline and remain unchanged; both routes resolve
  the same fixed server-owned file.
- Test-first evidence: the new suite first failed because the registry lacked
  `signals.options-flow.feed`; after implementation, API tests pass 44/44.
- Related evidence: artifact loader 14/14, Options Flow writer 9/9, UI client
  suites 12/12, 17/17, 16/16, and 15/15, dashboard navigation 49/49, and final
  `make test` all pass.
- Contract/quality evidence: checked-in/generated OpenAPI and examples match;
  duplicate YAML keys are rejected; compileall, Python 3.10 AST, `pip check`,
  current-artifact projection, `git diff --check`, and baseline scope audit pass.
- Owned pre-bound Uvicorn evidence covers missing -> available -> partial
  `invalid_json` -> recovered, `/latest` parity, health/no-store, and a defective
  resolver returning a sanitized 500 without a secret or traceback in logs.
- Three independent post-implementation reviews close with zero BLOCKER, HIGH,
  MEDIUM, or LOW findings. The justified contract refinements from v0.7-v0.10
  fix exact-instant precision and mutation-oracle gaps without expanding the
  endpoint, frontend, provider, writer, or deployment scope.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.11 | 2026-07-15 | Recorded implemented scope, complete verification evidence, and zero-finding post-implementation closure |
| v0.10 | 2026-07-15 | Added a valid equal-score mutation oracle for non-increasing ordering |
| v0.9 | 2026-07-15 | Added semantic date-time mutation oracles beyond regex-only failures |
| v0.8 | 2026-07-15 | Closed JSON Schema final-newline acceptance with schema-only absolute-end patterns and mutation tests |
| v0.7 | 2026-07-15 | Restricted feed timestamps to microsecond precision so data and metadata represent the exact same instant |
| v0.6 | 2026-07-15 | Replaced ambiguous timestamp string equality with same-instant verification after test-feasibility review |
| v0.5 | 2026-07-15 | Accepted after two independent closure reviews passed with no material findings |
| v0.4 | 2026-07-15 | Defined metadata equivalence, runtime-only invariants, and exact fail-soft/callback matrices |
| v0.3 | 2026-07-15 | Closed source-key, numeric coercion, provenance, journal, and rollback review gaps |
| v0.2 | 2026-07-15 | Resolved first-review DTO, 200-item, metadata naming, and exact-root/projection ambiguities |
| v0.1 | 2026-07-15 | Initial additive strict Options Flow feed projection plan |
