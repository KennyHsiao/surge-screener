# Frontend/Backend Separation — Analytics / Data Health Plan

## Document Info

| Field | Value |
|---|---|
| Version | v0.1 |
| Status | `READY FOR MAINTAINER ACCEPTANCE — IMPLEMENTATION NOT STARTED` |
| Baseline | `main@8e5e37ab1a252080f5066e4104cb5c5ce99d0fe3` |
| Owner / approver | Repository maintainer |
| Audience | Maintainers, API/UI engineers, security reviewers, and 7F operators |
| Parent audit | `docs/api/frontend-backend-separation-current-main-residual-audit-2026-08-29.md` |
| Traceability | `2026-08-29-frontend-backend-analytics-data-health.traceability.yaml` |

## Decision

Select Analytics/Data Health as the next frontend/backend separation family and
implement only the first bounded slice: a protected Analytics health/readiness
summary. Risk Guard is explicitly excluded.

The intended additive route is
`GET /api/v1/private/analytics/health-summary`. It reads only the fixed
`reports/analytics_checks/latest.json` slot through a strict pure projector,
reuses the existing private bearer plus loopback peer/Host perimeter, and emits
a bounded no-store admin DTO. It does not expose a path argument and cannot run
SQL, refresh data, start a process, repair state, or call a provider.

Data Health terminal status is a separately gated second slice. It MUST NOT be
added until the existing UI read-side status write is removed or assigned to a
producer/status owner.

## Goal and Success Metrics

Move the Analytics page's top-level health/readiness summary behind a strict
private API boundary while preserving every other page capability and failing
closed without a local summary fallback.

Success requires:

- the private route, checked-in OpenAPI, generated OpenAPI, endpoint inventory,
  server model, client model, and UI projection describe one exact schema;
- unauthorized, non-loopback, disabled-token, missing, malformed, oversized,
  shape-invalid, or forbidden-field inputs never disclose the source payload;
- the UI performs exactly one summary request per rerun and never rebuilds the
  migrated summary from local JSON after unavailable or client failure;
- DB/catalog/table/SQL, detailed local checks, refresh buttons, Data Health
  status, providers, producers, reports, picks, ledger and schedules retain
  existing behavior;
- public `/healthz` and all 54 accepted public presentation slices remain
  compatible;
- focused tests, full relevant tests, PR checks, deployment, and 7F private-route
  plus API/Streamlit smoke checks pass.

## Contract Boundary

### Allowed DTO

The route returns a closed versioned envelope containing only:

- fixed source ID `private.analytics.health-summary`;
- generated timestamp and as-of date;
- overall status and recommended action from closed allowlists;
- exact non-negative PASS, WARN, and BLOCK counts;
- derived review-required and watch-candidate counts;
- today-signal readiness status, publication boolean, recommended action,
  bounded safe message/category, and bounded warning/block identifiers or
  counts;
- bounded allowlisted warning codes.

The projector calculates derived counts server-side. The UI must not receive
raw signal or action records merely to reproduce the existing four cards.

### Denied Fields and Capabilities

The response MUST omit and schema validation MUST reject accidental projection
of:

- `analytics_root`, `duckdb_path`, filesystem paths, environment variables,
  credentials, tokens, commands, PIDs, logs, prompts, and stack traces;
- raw SQL, catalog/table contents, data downloads, refresh/rebuild controls;
- raw checks/messages/values/thresholds, ticker signal/evidence rows,
  performance return rows, provider payloads, and detailed next-action reasons;
- source file names supplied by the browser or any arbitrary query parameter;
- GET-time writes, reconciliation, provider work, subprocesses, or mutation.

### Existing Siblings

The first slice migrates only `_health_summary` input/presentation. The
`連線與原始檢查` expander, local DB/catalog/table/SQL views, local detailed
checks, observations and next-action tables, refresh controls, and Data Health
terminal status remain explicitly local/admin siblings. They MUST NOT be used
to reconstruct or mask an unavailable migrated summary.

This is therefore an API-backed presentation slice, not a claim that the whole
Analytics page is API-only. The 61 direct-binding ceiling need not shrink in
this first implementation.

## Scope

### In Scope

- strict source resolver/projector and immutable API models;
- protected private GET route, existing bearer/loopback checks, no-store, fixed
  media type, deterministic errors, and OpenAPI version bump from
  `1.23.0-draft` to `1.24.0-draft`;
- bounded endpoint-specific client validation using the existing private
  workload credential and transport controls;
- one-request UI integration for only the health/readiness summary;
- focused contract/route/client/UI/security/boundary/non-interference tests;
- documentation, PR, deployment, and 7F verification.

### Out of Scope

- Risk Guard, positions, Trade State, reconciliation, watchlists, IBKR or ledger;
- Analytics DB files, Parquet, SQL, table/catalog APIs or download endpoints;
- detailed checks, signal candidates, performance rows or next-action APIs;
- Data Health status/commands in this first slice;
- refresh/rebuild/provider/scheduler endpoints or any new mutation;
- public or internet-facing Analytics access, browser-supplied paths, CORS, or a
  new human identity system;
- changing Analytics check counts, schemas, producer semantics, last-known-good
  transactions, or natural schedules.

## Requirements

- `REQ-ADH-001` — The server MUST resolve one fixed Analytics checks slot and
  project one closed health-summary DTO without accepting a path or query.
- `REQ-ADH-002` — The route MUST require the existing private bearer credential
  and loopback peer/Host perimeter and MUST be disabled fail-closed when private
  token configuration is unavailable.
- `REQ-ADH-003` — The projection MUST expose only allowlisted bounded summary
  fields and MUST omit operational, path, credential, raw-check, ticker,
  performance, provider, and action-detail data.
- `REQ-ADH-004` — The Analytics UI MUST request the summary exactly once per
  rerun and MUST NOT fall back to the local checks artifact for the migrated
  summary after unavailable or failure.
- `REQ-ADH-005` — Existing local detail, DB, SQL, refresh, provider and Data
  Health behaviors MUST remain independent and unchanged.
- `REQ-ADH-006` — Data Health status API work MUST remain blocked until its
  read-side persistence is removed or moved to an explicit status owner.
- `CFR-ADH-001` — The projector and GET route MUST be deterministic and
  side-effect free for valid, missing, malformed, oversized, or invalid input.
- `CFR-ADH-002` — Server and client MUST enforce documented byte/field/list
  bounds, strict media/cache headers, no redirects, environment-independent
  transport, and a bounded deadline.
- `CFR-ADH-003` — Public routes and Industry Roles private routes MUST remain
  backward compatible; the additive API/OpenAPI version MUST advance once.
- `CFR-ADH-004` — Rollback MUST use the prior deployed application version and
  MUST NOT mutate or backfill the source checks artifact.

## Acceptance Criteria

- `AC-ADH-001`: Given a valid fixed checks artifact, when an authorized
  loopback client calls the route, then one strict no-store envelope returns the
  exact allowlisted summary and no denied field.
- `AC-ADH-002`: Given a missing/malformed/oversized/shape-invalid artifact, when
  the route is called, then it returns the documented unavailable or problem
  state without a traceback, partial payload, repair, write, or provider call.
- `AC-ADH-003`: Given a missing/invalid bearer, disabled token, non-loopback
  peer, or invalid Host, when the route is called, then access fails closed and
  no artifact content is read into the response.
- `AC-ADH-004`: Given available, unavailable, timeout, HTTP, media, cache,
  oversize, or invalid-envelope responses, when the UI renders, then the client
  performs one bounded request and the top summary never falls back locally.
- `AC-ADH-005`: Given the migrated summary fails, when the remainder of the
  Analytics page renders, then manual DB/catalog/table/SQL/detail and refresh
  siblings keep their documented independent behavior and do not impersonate a
  successful summary.
- `AC-ADH-006`: Given source fields contain paths, credentials, raw messages,
  tickers, evidence, performance rows, or action reasons, when the DTO is
  serialized and logs/errors are inspected, then none appears in the response
  or error detail.
- `AC-ADH-007`: Given the GET is exercised repeatedly and under concurrent
  requests, when source and runtime trees are compared, then their bytes,
  mtimes, subprocess/provider counters, and run status remain unchanged.
- `AC-ADH-008`: Given the current Data Health loader can persist a reconciliation,
  when first-slice scope is checked, then no Data Health status route/model/client
  or GET-time persistence has been added.
- `AC-ADH-009`: Given implementation and deployment complete, when generated
  and checked-in OpenAPI, focused/full tests, 7F private auth cases, API health,
  Streamlit health, and source hashes are checked, then all pass without a data
  refresh, producer run, report rewrite, pick, or ledger change.

## Expected Affected Files

The implementation review must confirm this list before editing:

- server: `api/analytics_health.py` (new pure projector), `api/models.py`,
  `api/main.py`;
- client/UI: `clients/private_api.py`, `ui/analytics_db.py`;
- tests: a new focused projector/client/UI suite plus `scripts/test_api.py`,
  `scripts/test_ui_backend_boundary.py`, and
  `scripts/test_ui_separation_convergence.py` as needed;
- contract/docs: `docs/api/quant-radar-v1.openapi.yaml`, endpoint inventory,
  API user/security guidance, this plan and traceability ledger.

Do not add `ui/sys_schedules.py`, Data Health producers/status writers, Risk
Guard, deployment units, or report artifacts without returning to plan review.

## Implementation Plan

### Phase 0 — Entry Review and Failing Contracts

- `IMPL-ADH-001` — Rebase an isolated branch on then-current main; record route
  surface, source schema sample, bounds, affected files, auth behavior, and
  current focused/full baseline.
- Add fail-first tests for the exact projector schema, denied-field containment,
  invalid/oversized inputs, and zero side effects.
- Confirm the UI slice can remain distinct from its local detail siblings. If
  the same local read would silently reconstruct the summary, stop and revise
  the UI boundary before implementation.

### Phase 1 — Pure Projector and Models

- `IMPL-ADH-002` — Implement the fixed resolver and pure strict projector with
  closed enums, numeric/list/string bounds, deterministic unavailable reasons,
  and no path-bearing output.
- Validate source invariants before projection; never return raw Pydantic/source
  validation detail to the client.

### Phase 2 — Protected Route and Client

- `IMPL-ADH-003` — Add the private GET behind the existing bearer and loopback
  dependencies, `Cache-Control: no-store`, exact media type, and additive
  `1.24.0-draft` OpenAPI contract.
- Add an immutable endpoint-specific client result union while reusing existing
  private credential/transport protections. Preserve Industry Roles behavior.
- Cover missing token, wrong token, peer/Host rejection, unavailable, timeout,
  redirects, HTTP/media/cache/size/envelope failures, and secret-safe errors.

### Phase 3 — One-Slice UI Migration

- `IMPL-ADH-004` — Load the private health summary once per Analytics rerun and
  render only the existing top summary from the validated DTO.
- Render a bounded unavailable/service message for unavailable/failure. Never
  derive migrated summary cards from `_load_checks` in those states.
- Keep the explicitly local detail/DB/SQL/refresh siblings behaviorally and
  visually separate; add tests proving neither side masks the other's state.

### Phase 4 — Boundary, Documentation, and Regression

- `IMPL-ADH-005` — Update checked-in OpenAPI and endpoint/security guidance;
  keep the route absent from the public whitelist and mark it protected/admin.
- Add AST/static guards for fixed route/no browser path/no provider or writer
  reachability/no Data Health status scope creep.
- Re-run API, private Industry Roles, Analytics UI, separation, deployment, and
  complete relevant test gates; inspect diff for unexplained scope drift.

### Phase 5 — Release and 7F Verification

- `IMPL-ADH-006` — Complete independent review, PR checks, merge authorization,
  deployment, byte/hash receipt, authorized/unauthorized private route probes,
  and API/Streamlit health checks on 7F.
- Confirm no producer, Data Health refresh, Analytics transaction, report,
  pick, ledger, schedule, score, weight, or threshold changed.
- Record first-slice closure. Open a separate reviewed plan before the Data
  Health status slice.

## Verification Matrix

| Test ID | Verification |
|---|---|
| `TEST-ADH-001` | Positive projector and exact envelope parity. |
| `TEST-ADH-002` | Missing, malformed, oversized, invalid and forbidden-field inputs fail safely. |
| `TEST-ADH-003` | Bearer, disabled-token, peer, Host and secret-redaction cases fail closed. |
| `TEST-ADH-004` | Client deadline, redirect, HTTP, media, cache, size and envelope bounds. |
| `TEST-ADH-005` | UI requests once, distinguishes unavailable/failure, and never locally reconstructs summary. |
| `TEST-ADH-006` | Local DB/detail/SQL/refresh siblings and all 54 public slices remain compatible. |
| `TEST-ADH-007` | Repeated/concurrent GETs produce zero source/runtime/provider/write changes. |
| `TEST-ADH-008` | Data Health status and Risk Guard stay absent from first-slice diff. |
| `TEST-ADH-009` | Generated/checked-in OpenAPI, version, inventory and deployment receipts agree. |
| `TEST-ADH-010` | 7F authorized/unauthorized private probes and API/Streamlit health pass without data mutation. |

## Rollout and Rollback

Roll out as one additive private route plus one bounded UI slice. The endpoint
is disabled when the existing private token is unavailable; public health and
other pages remain independent. A failure before deployment leaves production
unchanged. A failure after deployment rolls back by deploying the prior main
artifact. Do not implement a hidden local-summary runtime fallback and do not
rewrite the Analytics checks source during rollback.

## Blocking Review

- **Iteration 1:** rejected Risk Guard as the first target because position
  redaction, ownership, freshness and reconciliation are not closed.
- **Iteration 2:** rejected the documented `/api/v1/system/analytics-health`
  claim; current main contains no such public route or contract.
- **Iteration 3:** rejected combining Data Health status with the first GET
  because the present Analytics read path can reconcile and persist status.
  The first slice is now pure Analytics summary only.

No blocker remains for maintainer acceptance of this first-slice plan.
Implementation is not authorized by this documentation batch.

## Reviewers and Change History

Required reviewers: repository maintainer, API/security reviewer, Analytics UI
reviewer, independent verification reviewer, and 7F operator at release.

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-29 | Selected protected Analytics health summary; separated side-effectful Data Health status follow-up. |

## Glossary

- **Health summary:** the bounded top-level PASS/WARN/BLOCK and publish-readiness
  presentation, not the raw checks or Analytics database.
- **Local sibling:** an intentionally unmigrated admin capability that remains
  independently usable but cannot serve as fallback for the migrated slice.
- **Unavailable:** a valid inspection result for a missing or invalid fixed
  source slot; it is not a partial source payload or an implicit local fallback.
