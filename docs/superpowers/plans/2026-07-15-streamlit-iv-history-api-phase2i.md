# Streamlit Single-Ticker IV History API Consumer Phase 2I Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v0.5 |
| Status | Implemented and verified; independent implementation reviews passed |
| Author | Codex |
| Reviewer | Repository maintainer / independent implementation reviewers |
| Audience | Maintainers of the Streamlit-to-loopback read boundary |
| Related endpoint phase | `2026-07-14-fastapi-iv-history-phase2b.md` |
| Prior consumer phase | `2026-07-15-streamlit-fund-catalog-api-phase2h.md` |
| Separate UI/UX plan | `2026-07-15-quant-radar-ui-ux-redesign.md` |

## Goal

Make only the active single-ticker IV Rank chip in `ui/us_options.py` consume
`GET /api/v1/options/iv-history/{ticker}` API-first while preserving the current
options-chain page, rank calculation, fail-soft behavior, and immediate recovery.

This is deliberately a partial consumer slice. It does not make the full options
page, candidate grid, whole Stock Checkup page, or Options Cockpit API-backed.
Stock Checkup's lazy full-options tab already delegates to
`ui.us_options.render_for()` and therefore inherits this one chip call only when
that tab is rendered.

## Why This Is the Next Slice

Phase 2H is closed after independent review, a final non-empty local-fallback
AppTest, focused 16/16, dashboard 48/48, and full `make test`.

IV history is the smallest remaining endpoint with an exact-key source validator
and an `extra="forbid"` public DTO. Other existing candidate and signal routes
retain compatibility DTOs with `extra="allow"` and nested `dict` values that do
not yet cover all UI-consumed fields.

The safe sub-slice is the single selected ticker rendered by
`render_for()` -> `_render_bias_iv_chips()`. Migrating `_candidate_grid()` would
create one dynamic HTTP call per candidate, and both Streamlit tab bodies execute
during a render. Migrating Options Cockpit would place unavailable/client-failure
state inside a 15-minute cached provider that also calls logic which records and
re-reads IV history. Both are explicitly deferred.

## Architecture

### Client boundary

Extend `ui/_read_api.py` with a parameterized but bounded client:

```text
raw ticker
  -> exact shared normalization/validation
  -> http://127.0.0.1:8000/api/v1/options/iv-history/<NORMALIZED>
  -> existing safe response reader
  -> strict IV envelope/source/ticker/metadata validation
  -> frozen typed result
```

The caller supplies only a ticker business identifier. It cannot supply a host,
port, scheme, path, query, registry key, directory, filename, or URL. The client
reuses the endpoint's shared `api.artifacts.normalize_ticker()` normalizer so
its grammar cannot drift from the server contract:

```text
^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$
```

Length is 1-15 decoded characters and the client normalizes to uppercase. Invalid
input returns its own typed result before any IV-history HTTP or local artifact
read. The typed invalid result does not retain or reflect the raw input, and it
is not added to the shared seven-value `ClientFailureReason` union. Other
options-page provider work is outside this history-only no-call guarantee.

The direct client signature is exactly
`load_iv_history(ticker, *, transport=None)`. No caller-controlled base URL,
scheme, host, port, path, query, cap, timeout, or registry argument is exposed.
The existing page boundary remains backward-compatible: `render_for()` strips
outer whitespace, uppercases, and removes one-or-more leading `$` characters
before invoking both the options provider and the strict client. The direct
client accepts lowercase under the shared normalizer but intentionally rejects
raw whitespace and `$` aliases. Tests lock both layers so the strict trust
boundary does not silently remove the legacy page behavior.

### Response cap

IV `series` currently has no schema `maxProperties`. Therefore this plan does not
claim a cap that contains every schema-valid JSON serialization.

Use an exact **2 MiB decoded-body operational cap**. It is a client safety
boundary, not an API schema maximum. Existing producer files are tiny relative to
that budget; the cap allows decades of normally serialized daily values.

The 2 MiB limit bounds only decoded HTTP response accumulation. A transport,
deadline, status, media-type, cache-control, or below-cap envelope failure may
still enter the inherited unbounded local fallback. Phase 2I does not worsen that
existing local behavior, but it does not claim a global memory bound. A global
bound requires a separately reviewed bounded local loader or later API series
limit.

Unlike the three fixed-registry consumers, `response_too_large` MUST NOT trigger
the local fallback. The local artifact represents the same unbounded source, so
re-reading it without a bounded loader would defeat the cap and could allocate
the oversized body twice. Oversize therefore becomes a visible safe unavailable
chip state. The other six stable client failures may use the strict local
fallback.

This intentional exception is executable and documented; Phase 2I does not add
an arbitrary history limit to the API or change its OpenAPI contract.

### Rank calculation

Extract a pure `iv_percentile_from_series(series, current_iv=None)` from
`scripts/iv_history.py`. Existing `iv_percentile(ticker, current_iv=None)` reads
the same local artifact and delegates to the pure function. The API consumer
passes the validated API/fallback series to the same function.

The refactor MUST preserve:

- `MIN_DAYS = 40` and `WINDOW_DAYS = 252`;
- lexicographic ISO-date sorting and the most recent 252 points;
- current-value selection and explicit `current_iv` override;
- percentile/rank rounding;
- accumulating state below 40 points;
- `rank=None` when all in-window values are equal;
- the exact result dictionary fields and existing writer behavior.

`record_iv()`, `_path()`, `_load()`, artifact contents, and writer cache/atomic
replace behavior do not change.

### Canonical series representation

API and local inputs MUST converge on the same immutable representation before
calculation:

```text
tuple[IvHistoryPoint(as_of: str, iv: float), ...]
```

`IvHistoryPoint` and every public client/page outcome are frozen dataclasses.
API date keys are converted to ISO strings after strict envelope validation.
Local fallback continues through `read_artifact(iv_history_spec(normalized))`,
then revalidates the returned raw JSON-compatible value in JSON mode with
`IvHistoryData.model_validate_json(..., strict=True)` before applying the same
conversion. It MUST NOT use Python-mode `model_validate(..., strict=True)`, which
would reject the valid ISO-string date keys returned by the artifact boundary.

The tuple preserves the validated source iteration order; the existing pure
calculator remains responsible for ISO-date sorting. The page constructs the
calculator input from `{point.as_of: point.iv for point in points}`. A real
temporary valid artifact test MUST prove that API and fallback data produce the
same rank, not merely that a mocked fallback result is accepted.

### Page boundary

Add a small uncached page resolver that distinguishes:

- API available, including valid empty history;
- authoritative API unavailable for all four artifact reasons;
- visible local fallback for the six recoverable client failures;
- all sources unavailable after a failed/invalid local fallback;
- oversized response without local bypass;
- invalid ticker without HTTP or local read.

The page continues rendering the live options-chain evidence even when IV
history is absent. The existing directional-flow chip is unchanged. The IV chip
uses the same rank/accumulating labels; a short safe caption discloses fallback,
unavailable, oversize, or invalid-ticker state. No raw exception, path, response
body, URL, or ticker input is logged or reflected through diagnostics.

## Requirements

- `REQ-2I-001`: The single-ticker IV Rank chip MUST be API-first and call only the
  fixed loopback IV endpoint constructed from an exact normalized ticker.
- `REQ-2I-002`: Available API data MUST use the same pure 40/252-day calculation
  as the existing local `iv_percentile()` path.
- `REQ-2I-003`: A valid unavailable envelope MUST be authoritative and MUST NOT
  read the local artifact.
- `REQ-2I-004`: Each of the six recoverable client failures—transport, deadline,
  HTTP status, invalid media type, invalid cache control, and invalid envelope—
  MUST attempt exactly one read of the exact dynamic
  `iv_history_spec(normalized)` local fallback. Fallback status MUST be visible.
- `REQ-2I-005`: `response_too_large` MUST remain fail-soft but MUST NOT read the
  unbounded local source.
- `REQ-2I-006`: Missing, half-written, malformed, unreadable, or shape-invalid
  local fallback data MUST not crash the page. Unexpected fallback exceptions
  MUST log only fixed event text plus exception class.
- `REQ-2I-007`: API unavailable/failure results MUST not be negatively cached;
  the next rerun MUST retry and observe a repaired service/artifact.
- `REQ-2I-008`: A valid empty series MUST remain an available accumulating state
  with `n=0`, not an unavailable state.
- `REQ-2I-009`: Invalid ticker input MUST issue no HTTP request and no local read,
  while the rest of the options page remains usable.
- `REQ-2I-010`: API and fallback data MUST normalize to the same frozen tuple of
  ISO-date/value points; valid local JSON date keys MUST pass JSON-mode strict
  DTO validation and produce rank parity with the API source.
- `CFR-2I-001`: The client MUST use `trust_env=False`,
  `follow_redirects=False`, explicit 0.25-second connect/read/write/pool timeouts,
  and the existing cancellable 1.0-second whole-I/O deadline.
- `CFR-2I-002`: Successful responses MUST be HTTP 200 JSON with a case-insensitive
  `no-store` directive and at most 2 MiB decoded bytes.
- `CFR-2I-003`: The client MUST strictly validate the existing available or
  unavailable envelope, `sourceId=options.iv-history`, exact payload/request
  ticker equality, `generatedAt=null`, and `asOf=max(series dates)` or null for an
  empty/unavailable response.
- `CFR-2I-004`: `_candidate_grid()` and `_iv_rank_spark()` MUST remain local in
  this phase and MUST issue no IV API request.
- `CFR-2I-005`: `ui/options_cockpit.py`, `scripts/momentum_options.py`,
  Stock Checkup orchestration, options/yfinance providers, and all IV writers and
  caches MUST remain unchanged.
- `CFR-2I-006`: This phase MUST NOT implement the separate UI/UX redesign.
  Existing layout, navigation, page order, and chip styling remain except for
  accurate IV source-state captions.

## State Copy

The exact copy is finalized in focused tests and remains user-safe:

| State | Copy |
| --- | --- |
| local fallback | `IV 歷史服務暫時無法使用，已改用本機資料。` |
| authoritative unavailable | `IV 歷史資料目前無法使用；即時期權分析仍可繼續。` |
| all sources unavailable | `IV 歷史資料目前無法讀取；即時期權分析仍可繼續。` |
| response too large | `IV 歷史資料超過安全讀取上限；即時期權分析仍可繼續。` |
| invalid ticker | `此代號無法讀取 IV 歷史；即時期權分析仍可繼續。` |

Expected unavailable reasons are not errors and do not expose filenames. The IV
chip itself remains `IV Rank 累積中 n=0` whenever no safe series is available.

## Scope and Affected Files

### Create

- `scripts/test_ui_iv_history_api.py`
- this plan document

### Modify

- `ui/_read_api.py` — normalized bounded IV client, strict adapter, frozen result
  types, and deadline wrapper.
- `ui/us_options.py` — uncached resolver, strict local fallback, safe state copy,
  and API-backed single-ticker chip only.
- `scripts/iv_history.py` — pure calculation extraction only.
- `scripts/test_dashboard_navigation.py` — static partial-boundary/N+1 and
  preserved-page assertions.
- `Makefile` — register the focused suite.
- `docs/USER_GUIDE.md` — document the partial single-ticker boundary, fixed port,
  fail-soft states, and still-local candidate/Cockpit reads.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — mark only this chip API-first.
- `.agents/PROJECT.md`, `.agents/lens.md`, `.agents/scribe.md`, and
  `.agents/builder.md` — record decisions and verification evidence.

### Regression-only; do not edit unless a current-change failure proves necessary

- `api/**`
- `docs/api/quant-radar-v1.openapi.yaml`
- `ui/options_cockpit.py`
- `ui/stock_checkup.py`
- `scripts/momentum_options.py`
- `reports/iv_history/*.json`
- existing API, prior consumer, momentum-options, and cockpit-display tests

### Do not modify

- options/yfinance providers, candidate/scored readers, IV writer semantics,
  artifacts, navigation, session keys, dependencies, deployment/systemd, Docker,
  CI, API bind/host/CORS behavior, or the separate UI/UX plan.

The worktree contains cumulative Phase 1-2H and unrelated user work. The
pre-implementation baseline is
`/tmp/surge-phase2i-baseline-20260715-2028/`. Hashes were captured for every
existing affected file; this plan and focused test were absent. Final scope
review MUST use baseline-to-current diffs for overlapping files and
`/dev/null`-to-current diffs for new files.

## Test-First Tasks

### 1. Lock the pure calculation

- Add red parity tests for 0, 39, 40, 252, and 253 points; unsorted ISO dates;
  explicit current override; and equal low/high values.
- Prove `iv_percentile()` delegates to the pure helper and its public dictionary
  shape/rounding remains unchanged.
- Prove `record_iv()` and `_path()` source behavior are unchanged through existing
  tests/static guards; do not rewrite artifact fixtures.

### 2. Lock the parameterized client

- Assert exact method and normalized URL for `nvda`, `BRK.B`, and `BF-B`; no
  query; JSON accept header; one request; explicit timeouts; proxy and redirect
  controls.
- Lock the exact public signature to one ticker positional-or-keyword parameter
  plus one keyword-only test transport. Reject any caller-controlled URL, path,
  cap, timeout, or registry parameter.
- Assert invalid, underscore, Unicode, whitespace, traversal, adjacent/leading
  separators, and overlength tickers return the typed invalid result without a
  transport call.
- Assert available non-empty and empty data, all four unavailable reasons, and
  the complete seven-value client failure union.
- Reject request/payload ticker mismatch, wrong source, wrong metadata, extra
  fields, invalid dates/IVs, malformed JSON, and envelope drift.
- Assert exact 2 MiB whitespace-padded valid JSON is accepted; cap-plus-one is
  rejected and the response stream closes. This proves the operational byte
  boundary, not a schema maximum.
- Prove slow headers/body cancellation closes resources and maps to deadline or
  transport failure without raw detail.
- Register every focused `test_*` in a manual runner, compare discovered and
  registered test names, and print the exact pass count.

### 3. Lock page resolution and rendering

- Prove authoritative unavailable never calls `read_artifact()`.
- Parameterize all six named recoverable client failures and prove each attempts
  exactly one `read_artifact(iv_history_spec(normalized))` call while preserving
  exact ticker grammar.
- Prove `response_too_large` and invalid ticker never call local fallback.
- Cover local available, valid empty, all four unavailable artifact reasons,
  invalid model, and two unexpected exception paths. Unexpected logs contain
  only fixed copy plus class name and never the exception message.
- Write a real valid IV artifact under a temporary report root, read it through
  the production artifact boundary, and prove its canonical points and computed
  rank exactly match the equivalent strict API payload.
- Prove failure/unavailable followed by available data recovers immediately on
  the next direct call and next page resolution.
- AppTest API available/empty, authoritative unavailable, local fallback,
  all-unavailable, oversize, and invalid-ticker states. The local-fallback case
  MUST use known non-empty points and assert the exact resulting `IV Rank` and
  `n_days`; a separate valid-empty fallback case MUST assert accumulating
  `n=0`. Stub
  `options_free.analyze_options`; no test may call yfinance or another provider.
- Lock the existing directional chip, IV Rank/accumulating labels, surrounding
  captions, and continued chain rendering when history is absent.
- Assert `_candidate_grid()` and the default unsubmitted single-ticker tab never
  call `load_iv_history()`. Keep candidate IV rank/spark behavior local.
- Prove an embedded `render_for()` request makes exactly one IV API call for the
  active valid ticker and no call for an invalid ticker.
- Prove the page preserves legacy alias normalization for outer whitespace,
  lowercase, and one-or-more leading `$` characters; prove the direct client
  normalizes lowercase but rejects raw whitespace and `$` aliases without an IV
  request or local read.

### 4. Documentation and regression contracts

- Register the focused suite in `make test`.
- Update the dashboard static contract without claiming the entire options page
  or Cockpit is API-backed.
- Update the guide and inventory with the fixed port, Docker fallback behavior,
  authoritative unavailable rule, oversized no-bypass exception, and partial
  consumer boundary.
- Append skill/project evidence only after verification.

## Verification Gates

1. `.venv/bin/python scripts/test_ui_iv_history_api.py`
2. `.venv/bin/python scripts/test_ui_read_api.py`
3. `.venv/bin/python scripts/test_ui_ai_updates_api.py`
4. `.venv/bin/python scripts/test_ui_fund_catalog_api.py`
5. `.venv/bin/python scripts/test_api.py`
6. `.venv/bin/python scripts/test_momentum_options.py`
7. `.venv/bin/python scripts/test_options_cockpit_display.py`
8. `.venv/bin/python scripts/test_dashboard_navigation.py`
9. `make test`
10. `.venv/bin/python -m compileall -q ui scripts api`
11. Exact Python 3.10 grammar gate:

    ```bash
    .venv/bin/python - <<'PY'
    import ast
    from pathlib import Path
    paths = [
        Path("ui/_read_api.py"),
        Path("ui/us_options.py"),
        Path("scripts/iv_history.py"),
        Path("scripts/test_ui_iv_history_api.py"),
        Path("scripts/test_dashboard_navigation.py"),
    ]
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))
    print(f"Python 3.10 AST PASS ({len(paths)} files)")
    PY
    ```
12. `.venv/bin/python -m pip check`
13. `git diff --check`
14. Baseline-to-current affected-file audit and repository scope review.
15. Mutation checks that the exact cap, no-oversize-fallback rule, invalid-ticker
    no-request rule, and candidate-grid no-API rule fail when production behavior
    is deliberately weakened.
16. Collision-safe real-Uvicorn/AppTest smoke on fixed port 8000. Start and stop
    only a process owned by the test. The acceptance oracle MUST first call
    `load_iv_history()` directly and observe `IvHistoryApiAvailable`, then render
    the expected API-derived rank while forbidding both `read_artifact()` and the
    legacy `scripts.iv_history._load()` path, then prove every
    fallback/unavailable/oversize/invalid caption is absent. A valid checked-in
    local artifact MUST NOT be able to make this smoke pass. If an
    unowned listener exists, use it only after exact route/source/no-store
    matching as supplementary evidence and report the owned lifecycle smoke as
    skipped. The options provider remains stubbed; no live yfinance request is
    part of the smoke.
17. Independent correctness/security, test-strength, maintainability,
    diagnostic-leak, and scope-drift reviews. Fix all blocking findings and rerun
    affected gates.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Candidate grid causes N+1 HTTP | explicit non-goal, static/runtime no-call oracle |
| Cached Cockpit pins unavailable state | Cockpit and its provider remain regression-only |
| Invalid UI ticker aliases a different file | exact shared grammar; typed invalid result before request/read |
| Oversized API response is re-read locally | response-too-large explicitly bypasses fallback |
| Rank algorithm drifts | one pure helper and 39/40/252/253/equal-range parity tests |
| API unavailable breaks entire chain page | history-only safe state; provider evidence continues |
| Fallback hides degradation | exact visible fallback caption |
| Raw failures leak | typed reasons and class-only unexpected logging |
| Dirty worktree hides scope drift | captured baseline and exact affected-file audit |
| Fixed-port smoke stops another process | owned-process-only lifecycle rule |

## Traceability

| Requirement | Implementation target | Verification |
| --- | --- | --- |
| `REQ-2I-001`, `CFR-2I-001`, `CFR-2I-002` | normalized parameterized client | exact request/config/deadline/cap tests |
| `REQ-2I-002`, `REQ-2I-008`, `REQ-2I-010` | pure IV calculator and canonical frozen points | calculation boundary, API/local parity, and real-temp-artifact tests |
| `REQ-2I-003`, `CFR-2I-003` | strict IV envelope adapter | metadata/ticker/as-of and no-fallback matrices |
| `REQ-2I-004`, `REQ-2I-006` | strict local page resolver | six-reason fallback, artifact-state, log sentinel tests |
| `REQ-2I-005` | oversize no-bypass branch | exact cap and local no-call mutation oracle |
| `REQ-2I-007` | uncached client/resolver | consecutive recovery tests |
| `REQ-2I-009` | typed invalid ticker | no-request/no-local-read page/client tests |
| `CFR-2I-004`, `CFR-2I-005`, `CFR-2I-006` | bounded `us_options` edit | N+1/Cockpit/provider/static scope regressions |

## Pre-Implementation Review

- User authorization: continue after reviewing the prior phase.
- Phase 2H closure: complete; no unresolved blocking current-change finding.
- UI/UX redesign: separately planned and explicitly excluded.
- Exact affected files, baseline, verification, rollback, and major risks: defined.
- API/OpenAPI change: none.
- Live provider/network mutation: none in tests or implementation.
- Known design exception: the 2 MiB cap bounds HTTP accumulation only.
  Response-too-large is the only client failure that cannot enter the inherited
  unbounded local fallback; a global memory bound is deferred to a bounded local
  loader or a separately reviewed API series limit.
- First independent correctness review: no blocking/high finding; one medium
  canonicalization gap and two low scope/guarantee wording findings were fixed
  in v0.2.
- Independent test/scope review: no blocker/high finding; three medium and three
  low oracle/reproducibility findings were fixed in v0.3.
- Closure reviews: PASS for correctness/security and test-strength/scope.
- Blocking issues: none; implementation may begin test-first.

## Rollback

Remove the IV client/result types from `ui/_read_api.py`, restore
`_render_bias_iv_chips()` to call `iv_percentile(ticker)` directly, inline the
unchanged pure calculation body back into `iv_percentile()`, remove the focused
test and Makefile entry, and revert only Phase 2I documentation/journal changes.
No API, OpenAPI, artifact, provider, cache, writer, deployment, dependency, or
data migration rollback is required.

## Plan Review Record

- **Review 1 — independent correctness/security:** REQUEST_CHANGES with no
  blocker/high. Required one canonical API/fallback representation, a real
  local-artifact parity test, narrower HTTP-cap wording, and precise Stock
  Checkup scope. All findings are addressed in v0.2.
- **Review 2 — test-strength/scope:** REQUEST_CHANGES with no blocker/high.
  Required an API-only live-smoke oracle, normative exactly-once six-reason
  fallback, non-empty fallback Rank rendering, a public signature lock, explicit
  legacy page alias behavior, and reproducible compile/3.10 commands. All are
  addressed in v0.3.
- **Review 3 — closure correctness/security:** PASS with no remaining severity
  finding.
- **Review 4 — closure test-strength/scope:** PASS with no remaining severity
  finding; every v0.3 oracle is explicit and feasible.

## Implementation Record

- Test-first red baseline: the focused runner failed on the absent
  `iv_percentile_from_series()` symbol before production edits.
- Production scope: only `ui/_read_api.py`, `ui/us_options.py`, and
  `scripts/iv_history.py`; tests, Makefile, documentation, and skill journals
  changed exactly as listed. API/OpenAPI, providers, writers, caches, candidate
  grid, Options Cockpit, Stock Checkup orchestration, navigation, artifacts, and
  UI/UX implementation remained unchanged.
- Focused verification: 15/15, including exact and gzip-expanded 2 MiB caps,
  real slow-header cancellation/cleanup, all six exactly-once fallbacks,
  authoritative/oversize/invalid no-local states, real-artifact parity,
  recovery, AppTest state copy, alias behavior, and N+1 isolation.
- Regression verification: read API 12/12, AI Updates 17/17, fund catalog 16/16,
  API 36/36, momentum 12/12, Options Cockpit 19/19, dashboard 49/49, and full
  `make test` all passed.
- Compatibility/quality gates: compileall, exact Python 3.10 AST for five files,
  `pip check`, `git diff --check`, baseline-to-current scope audit, and four
  deliberate mutation oracles all passed.
- Live verification: fixed port 8000 had an unowned Uvicorn listener, so the
  owned-lifecycle smoke was correctly skipped and that process was not stopped.
  A supplementary responder check matched the exact route, source and
  `no-store`; the strengthened AppTest rendered the API-derived Rank while both
  strict fallback and legacy local-read paths were forbidden and all degraded
  captions were absent.
- Independent implementation review: correctness/security PASS with no finding;
  test review found one medium weakness in the original live-smoke evidence,
  which was fixed by forbidding the legacy local loader and re-running PASS;
  maintainability/scope review PASS with no drift.
- Remaining blocking issues: none.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.5 | 2026-07-15 | Recorded implementation, full verification, strengthened API-only live smoke, and independent correctness/test/scope review closure |
| v0.4 | 2026-07-15 | Recorded independent correctness/security and test/scope closure PASS; accepted for test-first implementation |
| v0.3 | 2026-07-15 | Strengthened exactly-once fallback, non-empty Rank, API-only smoke, signature, page-alias, and reproducible compatibility oracles after test/scope review |
| v0.2 | 2026-07-15 | Added immutable canonical points, JSON-mode strict local validation, real-artifact parity coverage, bounded guarantee wording, and precise embedded Stock Checkup scope after independent review |
| v0.1 | 2026-07-15 | Initial single-ticker IV Rank consumer plan with explicit N+1/Cockpit exclusions and an oversize no-local-bypass safety boundary |
