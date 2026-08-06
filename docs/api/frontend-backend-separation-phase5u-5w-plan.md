# Phase 5U-5W Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-05
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase5r-5t-plan.md`

## Objective

Close the last two public persisted presentation reads in Today Decision while
keeping its private and operational siblings local:

1. **Phase 5U:** reuse the existing strict Market Thesis latest client for the
   Today Decision market-gate card. This is the forty-third API-only slice.
2. **Phase 5V:** add a strict latest daily-decision summary contract, registry
   projection, fixed route, static OpenAPI definition, and bounded client.
3. **Phase 5W:** consume that daily summary exactly once in Today Decision for
   the regime gate and confirmed-pick references. This is the forty-fourth
   API-only slice.

The plan does not make the complete page backend-owned. Reconciliation, ledger,
Trade State, quote fallback, ranked/scored feeds, candidate controls/status and
history, providers, writers, mutations, and private report prose remain on their
accepted boundaries.

## Entry evidence and source decisions

- After Phase 5T, `_latest_market_thesis()` and `_latest_daily_summary()` are the
  only remaining Today Decision helpers that enumerate/read public persisted
  presentation artifacts. `_load_object()` exists only for those helpers.
- `MarketThesisData` already contains every field rendered by `_render_gate`:
  `direction`, `manifest_status`, `support_class`, and `label`. The existing
  fixed client already owns provenance, deadline, no-store, media-type, envelope,
  and retained-body validation.
- Daily summaries are selected from exact `reports/YYYY-MM-DD/summary.json`
  paths. The twelve current artifacts are at most 1.8 KiB. Eleven use the six
  canonical root fields; one historical artifact adds `watchlist_picks`.
  `total_confirmed` equals `len(ranked_picks)` in every current source.
- Four historical folders contain a source `report_date` one day behind the
  folder. Phase 5V therefore must not infer that every historical folder is
  valid. The resolver selects only the newest exact calendar-dated folder; the
  selected source must match that folder date or become authoritative
  unavailable. It must never fall back to an older summary.
- The public daily-summary projection is intentionally narrow:
  `as_of_date`, bounded `regime_summary`, and source-ordered unique candidate
  references containing only `ticker` and the closed
  `STRONG_BUY | BUY | WATCHLIST` verdict. Rank, score, thesis, entry/stop,
  position size, key risk, watchlist rows, cross-candidate commentary, portfolio
  notes, and raw source content remain private.

## Blocking-issue review

No unresolved blocking issue remains after three review iterations.

### Phase 5U

- **GO, risk 4.1/10.** Call `load_market_thesis()` exactly once from Today
  Decision render and derive only the existing gate fields from an available
  result.
- Authoritative unavailable and every bounded client failure render the existing
  safe dash/degraded gate state without a local forecast fallback or raw reason.
- Remove `_latest_market_thesis` and `_MARKET_THESIS_DIR` only after zero-consumer
  proof. Preserve the standalone Market Thesis page, validation/regime clients,
  all forecast writers, and notifications.

### Phase 5V

- **GO, risk 5.8/10.** Add a fixed
  `GET /api/v1/reports/daily-summary/latest` route with a strict summary-only DTO,
  registry source, exact latest-folder resolver, static OpenAPI, and a 128 KiB
  retained decoded-response client cap.
- Accept only the canonical six-field source root or that root plus the known
  optional `watchlist_picks`; validate the complete selected source before
  projection. Require a real folder date, matching source `report_date`, exact
  count arithmetic, rank sequence, unique bounded tickers, closed verdicts,
  finite bounded numeric source fields, and bounded text/container sizes.
- Missing, unreadable, partial, malformed, oversized, shape-invalid, date-
  mismatched, or invariant-invalid selected sources return HTTP 200 unavailable.
  No older-file fallback, arbitrary path/date input, raw report body, private
  prose, provider call, writer, or mutation enters the API.

### Phase 5W

- **GO, risk 4.7/10.** Resolve the new daily-summary client exactly once and
  reuse that one typed result for both `_render_gate` and
  `_render_opportunities`.
- Available-empty candidates remain authoritative and still render the validated
  regime. Unavailable and every bounded failure use safe partial output and keep
  the already-resolved ranked/scored feeds available; no local summary fallback
  or raw reason is displayed.
- Remove `_latest_daily_summary`, `_load_object`, and the now-unused `Path`
  import only after repository search proves zero consumers. Preserve private
  daily-report prose, report generation/notification/ledger writers, Schedules
  local result metadata, historical report browsing, and every operational
  sibling.

## Affected files and implementation order

1. Add fail-first Today tests for the Phase 5U typed available/unavailable/full
   failure matrix, exact request count, and no local forecast read.
2. Implement Phase 5U only in `ui/today_decision.py`; update deterministic
   fixtures/counters and focused boundary tests.
3. Add fail-first Phase 5V source, resolver, projection, route, OpenAPI, client,
   size/deadline/unavailable/failure, immutability, and Python 3.10 tests.
4. Implement the strict DTO and registry projector in `api/models.py` and
   `api/artifacts.py`, the fixed route in `api/main.py`, the static contract in
   `docs/api/quant-radar-v1.openapi.yaml`, and the client in `ui/_read_api.py`.
5. Add fail-first Phase 5W consumer tests, implement one-result reuse in
   `ui/today_decision.py`, and retire zero-consumer local helpers/imports.
6. Synchronize `scripts/test_ui_candidate_feeds_api.py`, a new focused daily-
   summary suite, global API/read-client tests, backend-boundary/navigation
   contracts, deterministic fixtures, user guide, endpoint inventory, receipt,
   frozen source hashes, and journals.
7. Run focused and complete verification, compare the actual diff to this plan,
   and fix every blocking review finding before claiming completion.

No authentication, deployment, service, Compose, dependency, provider, writer,
job, or mutation change is planned. The API version should advance once with the
new Phase 5V public route and all exact version assertions must move together.

## Verification gates

- Red-to-green Today candidate and new daily-summary focused suites.
- Existing Market Thesis, API/OpenAPI, shared read-client, backend-boundary,
  navigation, deterministic fixture, UX contract/inventory, deploy, and Docker
  suites.
- Exact resolver tests for missing directory, newest selection, malformed newest
  with valid older file, date mismatch, optional historical root, symlink/root
  containment, invalid calendar dates, count/rank/ticker/verdict/text/numeric
  bounds, and private-field projection.
- Full client failure matrix: transport, deadline, HTTP status, media type,
  cache-control, retained response size, and envelope/provenance mismatch.
- Python 3.10 AST, compile/tabnanny, whitespace, exact request/local-fallback
  searches, frozen source hashes, and complete `make test`.

## Review record

- **Iteration 1:** traced the two remaining Today public artifact reads and
  confirmed Market Thesis is an existing-client adoption. Daily-summary audit
  found the optional historical `watchlist_picks` root and four folder/source
  date mismatches; the plan now uses a closed two-variant source root and rejects
  a mismatched selected latest file without older fallback.
- **Iteration 2:** verified the minimum public daily DTO, source-order/count/rank
  invariants, exact one-result reuse, complete failure matrix, helper-removal
  gate, fixture counters, and retained private/operational siblings. Final
  verdict: **GO** for a separate Phase 5U-5W implementation instruction.
- **Iteration 3:** compared the implementation against every accepted boundary,
  added the missing complete Market Thesis client-failure oracle, tightened
  Daily Summary numeric source bounds, verified opt-in folder/source-date
  binding cannot affect existing registry entries, and corrected the stale
  forty-two-slice inventory sentence. No unexplained scope drift or blocker
  remains.

## Implementation receipt

- **Phase 5U:** Today Decision resolves the existing strict Market Thesis latest
  client once and derives only its existing market-gate fields. The local latest
  forecast resolver and directory constant have no remaining consumer.
- **Phase 5V:** draft API `1.17.0-draft` adds strict fixed
  `GET /api/v1/reports/daily-summary/latest`, complete closed-variant source
  validation, exact newest real-date folder selection, opt-in selected-date
  binding, a narrow immutable DTO, static OpenAPI examples, and a 128 KiB fixed
  client. Invalid newest sources never fall back to older reports.
- **Phase 5W:** Today Decision resolves one Daily Summary result and reuses it
  for the regime gate and confirmed references. The local summary resolver,
  generic object loader, and unused `Path` import were retired; ranked/scored
  partial output and all retained siblings keep their prior behavior.
- **Verification:** Daily Summary 6/6, candidate feeds 11/11, Market Thesis 7/7,
  API/OpenAPI 47/47, read client 12/12, boundary 20/20, navigation 64/64, UX
  safety 5/5, fixtures 26/26, Money Flow 6/6, Sector Rotation 5/5, deploy 18/18,
  Docker 11/11, Python compile/tabnanny/YAML/whitespace gates, exact frozen
  report hash, and complete `make test` all pass. Only pre-existing Streamlit
  bare-mode and `use_container_width` warnings remain.
- **Scope:** no authentication, deployment, service, Compose, dependency,
  provider, writer, job, mutation, or private report-field change was made.
  Actual implementation matches the accepted plan. The audited successor is
  `docs/api/frontend-backend-separation-phase5x-5z-plan.md`.
