# Phase 5X-5Z Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5u-5w-plan.md`

## Objective

Continue with one existing-client adoption and one contract/consumer pair:

1. **Phase 5X:** reuse the strict Daily Summary latest client for only the
   Schedules `report_dir` result card. This is the forty-fifth API-only slice.
2. **Phase 5Y:** add a strict latest Playbook Validation presentation contract,
   registry projection, fixed route, static OpenAPI definition, and bounded
   client.
3. **Phase 5Z:** consume that contract exactly once in the Playbook Validation
   renderer embedded by Retro Analysis. This is the forty-sixth API-only slice.

This plan does not make Schedules or Retro Analysis backend-owned. Schedule
registry, ledger, reflection, COT, Data Health, other result readers, the
Continuation Validation sibling, retrospective corpora, decision/outcome
generation, yfinance resolution, providers, writers, and mutations keep their
accepted boundaries.

## Entry evidence and source decisions

- After Phase 5W, `_latest_report_result()` still reads the same newest
  `reports/YYYY-MM-DD/summary.json` source now covered by
  `load_daily_summary()`. Its rendered report date, confirmed count, and first
  five tickers are exactly derivable from `as_of_date` and the ordered candidate
  references; no API expansion is needed.
- Schedules already caches selected duplicated result types per render. Adding
  `report_dir` to that same cache prevents duplicate Daily Summary requests if
  the registry later contains more than one visible report card.
- `ui/playbook_validation.py` directly reads
  `reports/playbook_validation/latest.json`. The artifact is not present in the
  current checkout, so missing-source behavior must be tested explicitly; its
  producer and producer tests define two closed source families:
  `blocked` with a private diagnostic reason, or `accumulating | ready` with
  decision/outcome counts and ordered playbook/factor summary rows.
- The public Playbook projection needs only generated time, status, resolved and
  minimum counts, displayed decision count, and bounded playbook/factor rows.
  The producer's raw missing-path reason, outcome count, decision snapshots,
  ticker-level outcomes, provider details, and source paths remain private.
- Each public row contains a bounded label, resolved count, nullable finite mean
  7-day return, nullable hit rate, and closed `exploratory | validated` verdict.
  Labels must be unique and source-sorted. Null pairs, row verdicts, top-level
  maturity status, and counts must agree with `min_resolved`.

## Blocking-issue review

No unresolved blocking issue remains after two review iterations.

### Phase 5X

- **GO, risk 3.9/10.** Replace only `_latest_report_result()` with one typed
  `load_daily_summary()` result and derive the existing short markdown summary
  from the validated DTO.
- Available-empty is an authoritative zero. Unavailable and every bounded
  failure render safe partial state without a local summary read or raw reason.
- Add `report_dir` to the per-render result cache and remove the local helper's
  report enumeration/read only after zero-consumer proof. Preserve every other
  result fetcher, registry behavior, reflection detail, logs, and actions.

### Phase 5Y

- **GO, risk 5.9/10.** Add fixed
  `GET /api/v1/reports/playbook-validation/latest` with source ID
  `reports.playbook-validation.latest`, a strict summary-only DTO, fixed-file
  registry entry, no-store envelope, static OpenAPI examples, and a 128 KiB
  retained decoded-response client cap.
- Validate the complete selected source against the exact blocked or mature
  root family before projection. Require strict RFC 3339 time, closed status and
  verdicts, bounded containers/text/counts, finite statistics, unique sorted
  labels, null/statistic parity, count coherence, and exact maturity semantics.
- Missing, unreadable, partial, malformed, oversized, shape-invalid, or
  invariant-invalid source becomes HTTP 200 unavailable. Never expose the raw
  blocked reason, arbitrary path input, decision/outcome rows, provider data, or
  writer operations; never add an alternate file or provider fallback.

### Phase 5Z

- **GO, risk 4.5/10.** Resolve the new client exactly once per Playbook
  Validation render and preserve the current status, metrics, playbook table,
  factor table, and empty-state structure from the typed projection.
- Valid blocked state uses fixed safe copy rather than the projected-out source
  reason. Authoritative unavailable and every bounded failure show stable safe
  partial output and never reread `latest.json` locally or display raw reason.
- Remove the local `REPORT` constant and `_shared` import only after repository
  search proves zero use. Preserve `ui/retro_analysis.py` navigation, the
  Continuation Validation tab, producer scripts, refresh/deploy jobs, and all
  retrospective artifacts.

## Affected files and implementation order

1. Add fail-first Schedules tests for Daily Summary available, available-empty,
   unavailable, complete client-failure matrix, exact one-request cache behavior,
   field parity, retained sibling fetchers, and no local summary fallback.
2. Implement Phase 5X in `ui/sys_schedules.py` and synchronize deterministic
   fixture counters plus focused boundary/navigation tests.
3. Add fail-first Playbook source-family, invariant, projection, route, OpenAPI,
   client, size/deadline/failure, immutability, and Python 3.10 tests.
4. Implement Phase 5Y in `api/models.py`, `api/artifacts.py`, `api/main.py`,
   `docs/api/quant-radar-v1.openapi.yaml`, and `ui/_read_api.py`; advance the
   draft API version once and move all exact version assertions together.
5. Add fail-first renderer tests, implement Phase 5Z in
   `ui/playbook_validation.py`, and retire only proven zero-consumer local
   symbols/imports.
6. Synchronize Make targets, global API/read-client tests, backend-boundary and
   navigation contracts, deterministic fixtures, user guide, endpoint
   inventory, receipt, frozen source hashes, and skill journals.
7. Run focused and complete verification, compare the actual diff to this plan,
   and fix every blocking review finding before completion.

No authentication, deployment, service, Compose, dependency, provider, writer,
job, schedule, yfinance, decision/outcome corpus, or mutation change is planned.

## Verification gates

- Red-to-green Schedules Daily Summary and Playbook Validation focused suites.
- Existing Daily Summary producer/route/client tests; API/OpenAPI; shared read
  client; backend boundary; navigation; deterministic fixture; UX contract and
  inventory; deploy; and Docker suites.
- Exact Playbook source tests for missing/unreadable/oversized sources, both root
  families, blocked-reason projection, maturity/count/verdict/null/statistic
  invariants, unique sorted bounded rows, invalid timestamps/numbers, and no
  private-field projection.
- Complete client matrix: transport, deadline, HTTP status, media type,
  cache-control, retained response size, envelope/provenance mismatch, every
  unavailable reason, and recovery after a failure.
- Python 3.10 AST, compile/tabnanny, YAML/static contract, whitespace, exact
  request/local-fallback searches, frozen artifact hashes, and complete
  `make test`.

## Review record

- **Iteration 1:** traced the remaining Schedules report read to the completed
  Daily Summary DTO and audited both Playbook producer branches. This removed an
  unnecessary new report contract and excluded private source reasons,
  outcome-level data, providers, writers, and Continuation Validation from the
  proposed public surface.
- **Iteration 2:** verified exact one-request placement, available-empty and
  blocked semantics, source-family/count/statistic invariants, bounded client
  behavior, helper-removal gates, fixture impacts, retained sibling behavior,
  and all affected verification surfaces. Final verdict: **GO** for a separate
  Phase 5X-5Z implementation instruction.

## Implementation and verification receipt

- **Phase 5X:** `ui/sys_schedules.py` now resolves one strict Daily Summary
  result for `report_dir`, treats available-empty as authoritative, returns safe
  unavailable/failure copy, and caches the result per type for duplicate cards.
- **Phase 5Y:** draft API `1.18.0-draft` adds the fixed strict Playbook Validation
  source/model/projection/route/OpenAPI/client boundary with complete blocked and
  active family validation, private-field omission, exact provenance, and a 128
  KiB retained-response cap.
- **Phase 5Z:** `ui/playbook_validation.py` resolves that client once and
  preserves status, timestamp, metrics, tables, blocked, unavailable, and
  failure presentation without local fallback. Retro navigation and
  Continuation Validation remain unchanged.
- **Review:** actual callers, types, tests, test configuration, and docs match
  this plan. Review added oversized-container and retry-after-failure oracles and
  synchronized the exact Phase 5X UX diagnostic removal receipt (164 current
  diagnostics). No unexplained runtime config, dependency, provider, writer,
  deployment, service, Compose, or mutation change exists.
- **Verification:** Schedules focused 4/4, Playbook focused 6/6, API 47/47,
  shared client 12/12, backend boundary 21/21, navigation 65/65, UX contract
  19/19, fixtures 26/26, deploy 18/18, Docker 11/11, Daily Summary 6/6, Money
  Flow 6/6, Sector Rotation 5/5, compile/tabnanny/YAML/whitespace/frozen-source
  gates, and a final complete `make test` pass.
- **Next:** `docs/api/frontend-backend-separation-phase6a-6c-plan.md` is
  blocker-reviewed for the strict Continuation Validation contract, client, and
  forty-seventh API-only consumer. COT remains the following Phase 6D-6F queue.
