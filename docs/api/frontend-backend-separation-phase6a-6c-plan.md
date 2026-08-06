# Phase 6A-6C Frontend/Backend Separation Plan

- **Status:** audited and ready for a separate implementation instruction
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5x-5z-plan.md`

## Objective

Move only the fixed Continuation Validation presentation boundary behind the
loopback read API:

1. **Phase 6A:** define and implement a strict latest Continuation Validation
   source contract, public DTO, fixed registry projection, route, and static
   OpenAPI operation.
2. **Phase 6B:** add an immutable fixed client with a retained decoded-response
   cap and the complete shared fail-soft result matrix.
3. **Phase 6C:** consume the result exactly once in
   `ui/continuation_validation.py`. This becomes the forty-seventh API-only
   slice.

This plan does not make all of Retro Analysis API-only. Retrospective datasets,
Playbook's already-migrated sibling, page navigation, forward-data production,
Parquet reads, providers, refresh/deploy jobs, writers, and mutations keep their
accepted boundaries.

## Entry evidence and source decisions

- `ui/continuation_validation.py` directly reads the one fixed
  `reports/retrospective/continuation_strength.json` artifact and renders its
  status, maturity metrics, summary counts, and row table. The artifact is not
  present in this checkout, so missing-source behavior is a first-class state.
- `scripts/continuation_strength.py` defines two closed root families: blocked
  output with a private diagnostic reason and empty summary/rows, or active
  `accumulating | ready` output with an exact summary, bounded rows, and a
  producer note.
- The active summary contains four mutually exclusive continuation counts,
  `rows_total`, `resolved`, and `min_resolved`. Counts, row labels, resolution
  flags, forward return/drawdown nullability, chosen horizon, and trade value
  must agree exactly with the top-level maturity state.
- The current table intentionally presents ticker-level continuation outcomes.
  The public DTO may preserve only the exact displayed row fields with strict
  ticker/date/enumeration/number/text/container bounds. It must omit the blocked
  reason and producer note and must not expose source paths, feature flags,
  Parquet rows, provider details, or arbitrary fields.
- The current 1,849-row feature corpus establishes that a tiny summary cap is
  inappropriate. The client should use a reviewed retained decoded-response cap
  sized for the bounded table (proposed 4 MiB), with an explicit maximum row
  count and no local fallback.

## Blocking-issue review

No unresolved blocking issue remains after two review iterations.

### Phase 6A

- **GO, risk 6.1/10.** Add fixed
  `GET /api/v1/reports/continuation-validation/latest` with source ID
  `reports.continuation-validation.latest` and no parameters.
- Validate the complete blocked or active source before projection. Require a
  strict RFC 3339 timestamp, closed status, positive minimum, maturity parity,
  exact root/summary/row fields, bounded unique source-ordered rows, count
  partitions, date/ticker normalization, finite return/drawdown bounds, exact
  null pairs for unresolved horizons, and coherent label/horizon/trade-value
  semantics.
- Missing, unreadable, malformed, partial, oversized-container, shape-invalid,
  or invariant-invalid source becomes HTTP 200 unavailable. Do not expose raw
  blocked reason, producer note, paths, flags, Parquet data, provider calls,
  refresh operations, or writer operations.

### Phase 6B

- **GO, risk 4.8/10.** Add one frozen `available | unavailable | failure`
  outcome family and a fixed loopback URL with the reviewed 4 MiB retained-body
  cap and existing whole-request deadline.
- Enforce source ID, `asOf=null`, generated-time parity, JSON media type,
  `Cache-Control: no-store`, response cap, strict envelope validation, and the
  complete existing client-failure vocabulary. Failures are retryable on the
  next call and never fall through to local JSON.

### Phase 6C

- **GO, risk 4.6/10.** Resolve the fixed client once per Continuation lane
  render and preserve the current status treatment, timestamp, three maturity
  metrics, three resolved-class metrics, empty state, and row table.
- Blocked state uses fixed safe copy because its raw source reason is private.
  Authoritative unavailable and every bounded failure show safe partial output
  without reading `continuation_strength.json` or displaying raw reason.
- Remove `json`, `Path`, `REPORT`, and `_shared` from the renderer only after
  zero-use proof. Preserve `ui/retro_analysis.py`, Playbook Validation, producer
  scripts/tests, data-health refresh, deployment publication, and all writers.

## Affected files and implementation order

1. Add fail-first focused tests for both exact source families, complete
   projection and privacy, count/maturity/row invariants, missing/unreadable/
   malformed/partial/oversized-container states, and recovery.
2. Implement Phase 6A in `api/models.py`, `api/artifacts.py`, `api/main.py`, and
   `docs/api/quant-radar-v1.openapi.yaml`; advance the draft version once and
   synchronize every exact version assertion.
3. Add fail-first fixed-client tests for URL/provenance/header/deadline/cap/
   envelope failures, all unavailable reasons, retry after failure, immutable
   outcomes, and Python 3.10 compatibility; implement Phase 6B in
   `ui/_read_api.py`.
4. Add fail-first Streamlit tests for ready, accumulating, blocked, unavailable,
   every client failure, empty rows, exact one request, table/metric parity, and
   no local fallback; implement Phase 6C in
   `ui/continuation_validation.py`.
5. Synchronize API/global read tests, backend-boundary/navigation tests,
   deterministic fixtures, Makefile, user guide, endpoint inventory, receipts,
   frozen producer/source gates, and skill journals.
6. Compare the actual diff to this plan, fix every blocking review finding,
   and run focused plus complete verification before completion.

No authentication, deployment topology, service, Compose, dependency,
provider, Parquet, producer, refresh, job, schedule, writer, or mutation change
is planned.

## Verification gates

- Focused Continuation source/route/OpenAPI/client/renderer red-to-green suite.
- Existing continuation producer tests and data-source refresh/deploy publication
  contracts unchanged.
- API/OpenAPI, shared read client, backend boundary, navigation, deterministic
  fixture, UX contract/inventory, deploy, and Docker regression suites.
- Exact root/summary/row family tests, blocked-reason/note projection tests,
  counter partitions, maturity and resolution/horizon/value invariants, bounds,
  invalid timestamps/dates/tickers/numbers, no private-field projection, and
  missing/invalid/recovery behavior.
- Python 3.10 AST, compile/tabnanny, YAML/static contract, whitespace, exact
  request/local-fallback searches, frozen producer bytes, and complete
  `make test`.

## Review record

- **Iteration 1:** ranked the remaining direct UI reads. Continuation is one
  fixed read-only display source with an existing producer/test oracle; COT
  combines catalog, Markdown, verified sidecars, and generation, while Knowledge
  Graph is a multi-file compiled aggregate. Continuation is therefore the
  narrowest safe next slice.
- **Iteration 2:** traced both producer root families and all current display
  fields, preserved ticker-level presentation while excluding diagnostics and
  producer internals, selected bounded exact-once client semantics, and verified
  that Playbook, Retro datasets, refresh/deploy, Parquet/provider, and writer
  siblings remain outside scope. Final verdict: **GO** for a separate Phase
  6A-6C implementation instruction.

## Following queue

Phase 6D-6F should separately design and review the COT persisted-read boundary:
an exact report catalog/detail contract, Schedules latest metadata reuse, and
the COT page's Markdown plus verified sidecar presentation. COT generation,
Codex authentication, provider calls, and writes must remain local/Deferred.

This planning receipt does not authorize Phase 6A-6C implementation without a
separate user instruction.
