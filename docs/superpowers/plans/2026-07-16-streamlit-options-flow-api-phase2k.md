# Streamlit Options Flow API Consumer Phase 2K Implementation Plan

## Document Info

| Field | Value |
| --- | --- |
| Type | Test-first implementation checklist |
| Version | v0.7 |
| Status | Implemented and verified; independent implementation reviews passed |
| Author | Codex |
| Reviewer | Repository maintainer plus independent plan and implementation reviewers |
| Audience | Streamlit, API-client, test, security, and operations maintainers |
| Related endpoint phase | `2026-07-15-fastapi-options-flow-feed-phase2j.md` |
| Separate design plan | `2026-07-15-quant-radar-ui-ux-redesign.md` |

## Goal

Make only the standalone **選擇權異常流** page consume the completed
`GET /api/v1/signals/options-flow/feed` endpoint for its persisted ranked feed.
The page must remain fail-soft when the artifact is missing, partially written,
malformed, unreadable, shape-invalid, or when the loopback client fails.

Success means the persisted feed is API-first, a valid unavailable envelope is
authoritative, six bounded client failures use one visible strict local fallback,
an oversized response cannot bypass its cap locally, and the existing ranking,
detail metrics, ticker handoff, and live-chain drill-down remain behaviorally
unchanged. This phase does not execute the separate UI/UX redesign.

## Why This Is the Next Slice

Phase 2J passed a fresh current-worktree closure review with zero findings. Its
strict endpoint already provides every persisted field used by
`ui/options_flow.py`, validates the fixed artifact, projects out source-only
fields, and maps expected file failures to safe HTTP 200 unavailable envelopes.

The current page still reads `reports/options_flow/latest.json` through the loose
Streamlit compatibility loader. It has one persisted-feed entry point and one
separate direct provider boundary. Migrating the fixed feed therefore closes one
complete consumer boundary without touching provider, writer, aggregate, or
navigation behavior.

## Architecture and State Contract

### Fixed client

Extend `ui/_read_api.py` with one endpoint-specific adapter over the existing
fixed response reader:

- exact request: `GET http://127.0.0.1:8000/api/v1/signals/options-flow/feed`;
- no caller-controlled URL, host, port, path, query, source ID, timeout, cap, or
  fallback;
- retain `trust_env=False`, `follow_redirects=False`, the exact 0.25-second
  connect/read/write/pool inactivity timeouts, `Accept: application/json`, and a
  Python-3.10-compatible cancellable 1.0-second whole-request deadline;
- accept only HTTP 200, `application/json`, and a case-insensitive `no-store`
  cache directive;
- retain at most `8 * 1024 * 1024` decoded response-body bytes before returning
  `response_too_large`;
- parse strictly as
  `ArtifactAvailable[OptionsFlowFeedData] | ArtifactUnavailable`.

The 8 MiB retained-body limit accommodates the bounded public contract: at most 200 signals,
20 tags per signal, and 100 characters per tag. Even ASCII-escaped astral tags
use about 4.8 MiB before envelope and field overhead. The limit bounds only bytes
retained by the shared reader and its `response_too_large` classification. HTTPX
decodes each transport chunk before the helper can inspect it, so compressed/wire
decoder transient memory is explicitly outside this guarantee. It is also not a
global local-file bound because the inherited artifact loader reads the full
source before projection.

The client returns exactly one of:

- `OptionsFlowApiAvailable(feed=OptionsFlowFeedData)`;
- `OptionsFlowApiUnavailable(reason=<artifact reason>)`;
- `OptionsFlowApiFailure(reason=<stable client reason>)`.

The failure union remains exactly the existing seven reasons:
`transport_error`, `deadline_exceeded`, `http_status`, `invalid_media_type`,
`invalid_cache_control`, `response_too_large`, and `invalid_envelope`.

Every accepted envelope must use
`meta.sourceId=signals.options-flow.feed`. Available `meta.asOf` must equal
`data.as_of`, and available `meta.generatedAt` must represent the same instant as
`data.generated_at`. Unavailable metadata must have null `asOf` and
`generatedAt`. The client preserves source signal order and public values.

### Page resolution

Add a frozen page state in `ui/options_flow.py` with these statuses:

- `api_available`;
- `api_unavailable`;
- `local_fallback`;
- `response_too_large`;
- `all_unavailable`.

A valid API `available=false` response is authoritative and never reads the local
artifact. Six client failures—transport, deadline, HTTP status, media type,
cache-control, and envelope failure—perform exactly one local read through
`read_artifact(ARTIFACTS["signals.options-flow.feed"])`, followed by strict
`OptionsFlowFeedData` parsing. They must not call `_shared.load_json()`, duplicate
the source projector, expose source-only fields, or cache a failure.

`response_too_large` is a dedicated safe state and MUST NOT read locally. Although
the public DTO is bounded, the source permits unallowlisted nested fields and the
inherited loader reads the complete file before projection. Re-reading it would
defeat the HTTP cap and could allocate the oversized source twice. A later bounded
pre-parse local loader may revisit this policy; Phase 2K must not claim that the
8 MiB HTTP cap bounds local artifact memory.

Unexpected fallback defects may log only a fixed event plus exception class. Raw
exception messages, response/source bodies, URLs, paths, environment values,
tracebacks, and source-only data must not enter logs, state, or UI.

### Preserved provider boundary

`_live_chain()` remains the existing cached direct yfinance-backed drill-down.
The persisted-feed resolver must never call it. Existing populated rendering may
still call it through `_render_detail()` because Streamlit executes tab bodies;
focused UI tests must stub that call. This phase claims only that the persisted
feed is API-first, not that the entire page is provider-free.

### Complexity decision

This is a simple fixed read integration with no new business invariant. Reuse the
existing DTO, result union, and page-state patterns. Do not introduce a repository,
aggregate, event, retry framework, circuit breaker, or new abstraction layer.
Each rerun is the bounded retry opportunity; no in-request retry is added.

## Requirements

- `REQ-2K-001`: The persisted feed request MUST use the exact fixed loopback URL
  and MUST expose no production URL/path/cap override.
- `CFR-2K-001`: The client MUST retain the existing fixed transport, header,
  timeout, deadline, redirect, and proxy-trust controls and use an exact 8 MiB
  retained decoded-body limit. It MUST NOT be described as a hard process-memory,
  wire-byte, or per-decoder-allocation bound.
- `REQ-2K-002`: Available responses MUST pass the strict Phase 2J DTO and metadata
  parity checks and preserve source order and all public values.
- `REQ-2K-003`: All four valid unavailable reasons MUST be authoritative safe UI
  states and MUST perform zero local reads.
- `REQ-2K-004`: All seven stable client failures MUST remain typed, sanitized,
  fail-soft outcomes. The six non-size failures MUST perform at most one strict
  local fallback read; `response_too_large` MUST perform zero local reads.
- `REQ-2K-005`: The local fallback MUST use the exact feed registry spec and strict
  public DTO. Missing, partial/malformed, unreadable, invalid, or unexpectedly
  defective fallback reads MUST not crash the page.
- `CFR-2K-002`: No API failure or fallback outcome may be negatively cached.
  The next Streamlit rerun MUST reattempt the API and observe repairs immediately.
- `REQ-2K-006`: Valid empty feeds, including `signal_count > 0` with no returned
  top signals, MUST remain available, render the validated provenance caption,
  show `目前沒有可顯示的異常流訊號。`, and skip chips, tabs, and live-chain work.
- `REQ-2K-007`: Existing ranking columns, source order, stale-selection guard,
  metrics, tabs, ticker selection, action buttons, chart, and live-chain behavior
  MUST remain intact.
- `CFR-2K-003`: Safe Traditional Chinese notices MUST not include raw diagnostics.
  Fallback use MUST be visible.
- `CFR-2K-004`: Phase 2K MUST NOT modify API/OpenAPI, artifact schema/writer,
  providers, other artifact consumers, navigation, dependencies, deployment,
  Docker topology, or the UI/UX redesign plan.
- `CFR-2K-005`: Changed Python MUST parse with Python 3.10 grammar and the current
  pinned dependencies; no package change is allowed.

## Given/When/Then Acceptance Criteria

- `AC-2K-001`: Given a populated valid API envelope and a stubbed live chain, when
  the page renders, then it shows the provenance caption, source-ordered ranked
  feed, detail data, and no fallback warning.
- `AC-2K-002`: Given either `signal_count=0/signals=[]` or a valid positive
  `signal_count/signals=[]` API envelope, when the page renders, then it shows the
  exact provenance caption plus `目前沒有可顯示的異常流訊號。`, emits no chips
  or tabs, and calls `_live_chain()` zero times.
- `AC-2K-003`: Given each valid unavailable reason, when the page loads, then it
  shows reason-specific safe copy and never invokes the local reader.
- `AC-2K-004`: Given each of the six non-size client failures and a valid local
  feed, when the page loads, then it reads the exact strict fallback once, shows a
  generic warning, and renders the same public feed.
- `AC-2K-005`: Given a non-size client failure and a missing,
  partial/malformed, unreadable, invalid, or defective local source, when the page
  loads, then it shows a safe all-sources-unavailable state without an exception
  or raw diagnostic.
- `AC-2K-006`: Given a failed or unavailable read followed by a repaired API
  response, when the next uncached load runs, then it becomes API-available
  immediately.
- `AC-2K-007`: Given wrong source metadata, date mismatch, extra or missing
  envelope/data fields, malformed JSON, coercion-only values, or invalid
  signal/biggest data, when read, then the result is `invalid_envelope`.
  Timestamp parity is instant-based, not lexical: data
  `2026-07-15t06:30:00z` with metadata `2026-07-15T08:30:00+02:00` MUST be
  accepted, equivalent `Z`/offset forms with 1-6 fractional digits MUST be
  accepted, and a one-microsecond or offset-adjusted different instant MUST be
  rejected.
- `AC-2K-008`: Given a maximum public envelope, exact-cap valid whitespace padding,
  cap-plus-one decoded bytes, or gzip-expanded cap-plus-one bytes, when read, then
  the first two are accepted and the latter two return `response_too_large` while
  closing the response stream. Page resolution for both oversized cases performs
  zero local reads and shows only sanitized copy.
- `AC-2K-009`: Given a populated API or fallback state and a stubbed live-chain
  result, when the page renders, then tabs are exactly `🔥 異常流排行` and
  `🔎 個股明細`; feed columns are exactly `方向`, `代號`, `估權利金`, `熱度`,
  `V/OI峰值`, `最活躍履約`, `skew`, and `標籤`; detail metrics retain
  `估權利金`, `最活躍履約價`, `V/OI 峰值`, and the direction-specific ratio;
  the live-chain stub is called once for the selected first ticker; a non-empty
  chain renders exactly one Plotly chart and its expiration caption; clicking
  `🔍 個股總覽` writes that ticker to both `checkup_ticker` and
  `checkup_handoff`; and AppTest emits no exception.
- `AC-2K-009A`: Given only `_load_options_flow()` is invoked, when it resolves any
  API or fallback outcome, then `_live_chain()` is never called.
- `AC-2K-009B`: Given a stale selected row index beyond a shortened feed, when the
  feed rerenders, then no ticker action is emitted and no exception occurs.
- `AC-2K-010`: Given the phase diff, then only listed files change and all API,
  provider, writer, other-consumer, deployment, Docker, dependency, navigation,
  and UI/UX-plan surfaces remain unchanged.

## Safe UI States

| State | Feed source | UI behavior |
| --- | --- | --- |
| API available, populated | API | Existing metadata, chips, feed, detail, and live chain |
| API available, empty | API | Provenance caption plus exact empty-feed information; no chips, tabs, fallback, or live call |
| API valid unavailable | None | Reason-specific safe information; no local bypass |
| Non-size client failure + valid local | Local | Generic fallback warning, then normal rendering |
| Non-size client failure + valid empty local | Local | Warning plus valid-empty information |
| Non-size client failure + bad local | None | Generic API warning plus all-sources-unavailable information |
| API response too large | None | Dedicated safe size warning; no local read or live-chain call |

Authoritative unavailable details:

| Reason | Safe detail |
| --- | --- |
| `missing` | 找不到異常流資料。 |
| `invalid_json` | 異常流資料尚未完整寫入或 JSON 格式無效。 |
| `invalid_shape` | 異常流資料格式不符合預期。 |
| `unreadable` | 異常流資料目前無法讀取。 |

The authoritative wrapper is exactly
`異常流資料目前無法使用：{detail}`. Other fixed copy is:

| State | Exact copy |
| --- | --- |
| Local fallback | warning: `異常流 API 暫時無法使用，已改用本機資料。` |
| All sources unavailable | warning: `異常流 API 暫時無法使用。`; info: `異常流 API 與本機資料目前皆無法使用。` |
| Response too large | warning: `異常流 API 回應超過安全讀取上限。`; info: `異常流資料暫時無法使用；請稍後重試。` |
| Valid empty feed | info: `目前沒有可顯示的異常流訊號。` |

No notice may contain a failure reason token, exception text, URL, path, response
body, traceback, source-only field, or environment value.

## Scope and Affected Files

### Create

- This plan document.
- `scripts/test_ui_options_flow_api.py` — focused client, fallback, recovery,
  rendering, and source-boundary tests.

### Modify

- `ui/_read_api.py` — fixed URL, cap, strict adapter, metadata checks, typed
  outcomes, deadline wrapper, and sync loader.
- `ui/options_flow.py` — typed API-first page state, strict fallback, safe notices,
  and conversion into the existing renderer.
- `scripts/test_dashboard_navigation.py` — static contract for the new consumer
  and preserved live-chain/ticker-handoff behavior.
- `Makefile` — register the focused suite in `make test`.
- `docs/USER_GUIDE.md` — update the API-first consumer count and accurately
  document Options Flow, fixed port, fallback, Compose, and live-chain boundaries.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — mark the standalone page
  adopted in Phase 2K while keeping all other Options Flow consumers local.
- `.agents/builder.md`, `.agents/lens.md`, `.agents/scribe.md`, and
  `.agents/PROJECT.md` — append plan and verification evidence.

### Regression-only; do not edit without a demonstrated blocker

- `api/**`, `docs/api/quant-radar-v1.openapi.yaml`, and `scripts/test_api.py`.
- `scripts/artifact_loader.py`, `scripts/options_flow_scan.py`, and their tests.
- Existing UI client focused suites.

### Explicitly unchanged

- `ui/options_cockpit.py`, `ui/today_decision.py`, `ui/trade_state.py`, and all
  other Options Flow artifact consumers.
- `_live_chain()`, `scripts/options_free.py`, writer behavior, caches, and provider
  calls.
- `app.py`, route names, navigation order, session-state ticker handoff, visual
  design, responsive behavior, and the UI/UX redesign plan.
- Dependencies, CORS/auth/bind policy, deployment/systemd, Docker, and source data.

The cumulative worktree is dirty. Existing affected files were copied before
Phase 2K edits to `/tmp/surge-phase2k-baseline-20260716-cwOdoh/`. Final review
must use baseline-to-current diffs for existing files and `/dev/null`-to-current
diffs for new files; repository `HEAD` alone is not a valid phase boundary.

## Test-First Implementation Tasks

1. Create the focused suite and register red tests for the exact public/private
   signatures, fixed request/configuration, strict available/empty/unavailable
   envelopes, metadata parity, source order, and seven-value client failure union.
   The metadata test MUST include accepted lowercase `t/z`, equivalent non-zero
   offsets, and 1-6 digit fractional forms, plus a different-instant rejection;
   fixtures that only use lexically identical timestamps are insufficient.
2. Build the maximum-public envelope with maximum lengths and counts, astral
   Unicode tags, and `json.dumps(..., ensure_ascii=True)`. Add exact-cap,
   cap-plus-one, gzip-expanded, deadline, stream-cleanup, malformed-envelope, and
   Python 3.10 tests. Prove the shared response reader returns raw bytes and the
   Options Flow adapter owns DTO/metadata checks. The gzip test proves result
   classification and retained-body cleanup only; it must not claim a hard bound
   on HTTPX decoder transient allocation.
3. Add page-resolution tests for authoritative unavailable, exactly-once strict
   fallback for the exact six reasons, zero fallback for oversized responses, all
   expected local file failures, class-only unexpected logging, no negative
   caching, and API/local public-data parity.
4. Add AppTest and static tests for populated/empty/unavailable/fallback/all-down
   rendering, ranking columns, stale selection, detail metrics, ticker handoff, and
   the unchanged direct live-chain boundary. Stub live calls in every populated
   fixture. A non-empty stubbed chain MUST produce one Plotly chart and expiration
   caption; clicking `🔍 個股總覽` MUST populate `checkup_ticker` and
   `checkup_handoff` with the selected ticker.
5. Run the focused suite and record the expected red failure before runtime code.
6. Implement the smallest client and page-state changes that make the focused
   suite green. Do not add retries, a configurable endpoint, new caching, or a new
   domain layer.
7. Update Makefile, inventory, guide, and journals. Run focused and full gates.
8. Compare the actual phase diff with this list and perform fresh correctness,
   regression, privacy, maintainability, and scope reviews. Fix all blockers.

## Verification Gates

Run, in order:

1. `.venv/bin/python scripts/test_ui_options_flow_api.py`
2. `.venv/bin/python scripts/test_ui_read_api.py`
3. `.venv/bin/python scripts/test_ui_ai_updates_api.py`
4. `.venv/bin/python scripts/test_ui_fund_catalog_api.py`
5. `.venv/bin/python scripts/test_ui_iv_history_api.py`
6. `.venv/bin/python scripts/test_dashboard_navigation.py`
7. `.venv/bin/python scripts/test_artifact_loader.py`
8. `.venv/bin/python scripts/test_options_flow_scan.py`
9. `.venv/bin/python scripts/test_api.py`
10. `.venv/bin/python -m compileall -q api ui scripts`
11. Parse every changed Python file with `ast.parse(..., feature_version=(3, 10))`.
12. `.venv/bin/python -m pip check`
13. `make test`
14. `git diff --check`
15. Baseline-to-current/new-file scope and untouched-surface audit.
16. Collision-safe real-Uvicorn plus Streamlit AppTest smoke on fixed port 8000.
    Start and stop only an owned process. If the port is occupied, record a skip;
    never treat an unknown responder as owned evidence.
17. Independent post-implementation correctness, test-strength, privacy,
    maintainability, and scope reviews.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| API outage makes the page more fragile | Typed failures, one strict visible fallback for six bounded reasons, and no negative cache |
| Valid unavailable is silently bypassed | Separate unavailable/failure types and zero-local-read tests |
| Metadata or schema drift reaches rendering | Strict Phase 2J DTO plus exact source/date/timestamp parity |
| Oversized response exceeds retained-body policy | Exact retained decoded-body limit, zero local bypass, cap-plus-one/gzip classification, cleanup proof, and no hard transient-memory claim |
| Local fallback is mistaken for globally bounded | Document inherited full-file pre-read; make no global-bound claim |
| Source-only fields leak | Reuse the exact feed registry projector and strict DTO |
| Raw errors or paths leak | Stable reasons and class-only fallback log sentinel tests |
| A failure becomes sticky | No Streamlit/API-result cache; consecutive recovery test |
| Live provider is called during resolver tests | Keep it outside resolver and stub it in populated AppTest fixtures |
| Scope becomes an implicit UI redesign | Preserve render helpers/layout and enforce explicit unchanged surfaces |
| Other Options Flow consumers are accidentally migrated | Static and baseline audits for Today Decision, Cockpit, and Trade State |
| Dirty worktree hides drift | Captured baseline plus exact phase-only diff review |

## Rollback

Reverse only the Phase 2K-owned hunks identified by baseline-to-current and
three-way comparison. Never restore an entire shared dirty file from the baseline.
If any affected hunk independently diverged after capture, preserve that work and
stop for an explicit merge instead of overwriting it. Remove the focused test or
this plan only after confirming the file remains wholly Phase 2K-owned and has no
later edits. Do not modify the Phase 2J endpoint, OpenAPI, source artifact, writer,
provider, other pages, deployment, Docker, dependencies, or UI/UX plan. Re-run all
focused regressions, API/writer/loader tests, `make test`, compile/AST, dependency,
and diff gates.

## Traceability

| Requirement / AC | Implementation target | Named verification |
| --- | --- | --- |
| `REQ-2K-001`, `CFR-2K-001` | Fixed URL and endpoint adapter | `test_fixed_request_signature_configuration_and_raw_reader_boundary` |
| `REQ-2K-002`, `AC-2K-007` | Strict TypeAdapter and instant-based metadata parity | `test_available_values_order_metadata_and_invalid_envelope_matrix` with equivalent-spelling acceptance and different-instant rejection mutations |
| `REQ-2K-003`, `AC-2K-003` | Typed authoritative unavailable branch | `test_authoritative_unavailable_messages_never_read_local` |
| `REQ-2K-004`, `AC-2K-004`, `008` | Seven typed failures, six-reason fallback, oversize no-bypass | `test_complete_failure_matrix_fallback_rules_and_size_stream_cleanup` |
| `REQ-2K-005`, `AC-2K-005`, `CFR-2K-003` | Strict registry fallback and sanitized logger | `test_local_fallback_file_states_and_logging_remain_fail_soft` |
| `CFR-2K-002`, `AC-2K-006` | Uncached public loader/page resolver | `test_failed_and_unavailable_reads_recover_on_next_call` |
| `REQ-2K-006`, `AC-2K-002` | Valid-empty page branch | `test_both_valid_empty_semantics_keep_provenance_and_skip_live_chain` |
| `REQ-2K-007`, `AC-2K-001`, `009`, `009A`, `009B` | Existing renderer fed by strict DTO data | `test_populated_render_preserves_feed_detail_chart_handoff_and_provider_boundary`; `test_stale_selection_remains_safe` |
| `CFR-2K-004`, `005`, `AC-2K-010` | Explicit phase boundary | `test_sources_are_python310_fixed_and_scoped`; baseline/dependency/untouched-surface gates |

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | FAIL | Oversize wording still implied local fallback; whole-file rollback could clobber dirty/concurrent work; empty and degradation states were not exact; behavior and traceability tests were too vague. | v0.3 narrows oversize to zero local reads, requires hunk-only three-way rollback, fixes exact copy/empty provenance/provider behavior, pins columns/tabs/metrics, and maps every AC to named tests. |
| 2 | FAIL | Metadata acceptance was described as same-instant, but the named test did not require equivalent lowercase/offset/fractional spellings, so a lexical-equality bug could pass. | v0.4 adds explicit equivalent-instant acceptance and different-instant rejection mutation oracles. |
| 3 | FAIL | The 8 MiB wording overclaimed a hard client memory cap even though HTTPX decodes a chunk before the helper sees it; chart and positive ticker-handoff promises lacked direct UI oracles. | v0.5 limits the guarantee to retained decoded-body/result semantics and adds exact non-empty chart plus session-state handoff tests. |
| 4 | PASS | Two independent reviewers found no remaining BLOCKER, HIGH, MEDIUM, or LOW finding. Retained-body, instant metadata, fallback, chart/handoff, rollback, and scope gates are executable. | Plan accepted for test-first implementation. |

If the same blocker remains after three review iterations, stop and report it
instead of implementing.

## Implementation Record

- **Red-first baseline:** The focused runner failed on the absent
  `ui._read_api.load_options_flow` symbol before either production file was
  changed. The completed focused suite passes 10/10.
- **Actual scope:** Existing-file changes are limited to `ui/_read_api.py`,
  `ui/options_flow.py`, `scripts/test_dashboard_navigation.py`, `Makefile`,
  `docs/USER_GUIDE.md`, the endpoint/artifact inventory, and the four required
  project journals. This plan and `scripts/test_ui_options_flow_api.py` are the
  only new Phase 2K files. Baseline-to-current review found no phase-owned change
  to API/OpenAPI, models/artifacts, writers/providers, other consumers,
  navigation, deployment, Docker, dependencies, or the UI/UX redesign plan.
- **Focused evidence:** 10/10 covers the fixed client/configuration, same-instant
  metadata with lowercase and every 1–6 digit fractional spelling, rejection of
  lossy 7-plus-digit metadata before Pydantic datetime conversion, strict
  available/unavailable/invalid envelopes, maximum public contract dimensions,
  exact/gzip-expanded retained-body limits and stream cleanup, all fallback and
  recovery states, class-only logging, valid-empty provenance, populated ranking
  and detail rendering, chart, ticker handoff, and stale selection.
- **Regression evidence:** shared read API 12/12, AI Updates 17/17, fund catalog
  16/16, IV History 15/15, dashboard 50/50, artifact loader 14/14, Options Flow
  writer 9/9, API 44/44, and full `make test` passed.
- **Compatibility/quality evidence:** `compileall`, Python 3.10 AST parsing for
  every changed Python file, `pip check`, `git diff --check`, stale-document
  scans, and the phase-only baseline/scope audit passed.
- **Live verification:** Fixed ports 8000 and 8501 were already occupied by
  processes started before this phase and not owned by this run. The
  collision-safe owned Uvicorn/AppTest smoke was therefore skipped; neither
  process was stopped or counted as implementation evidence.
- **Independent review:** Correctness/security/test-strength review passed with
  no finding. Scope/maintainability review found an ineffective `api.main`
  import guard, missing journal evidence, and this stale plan status; all three
  low findings were fixed. Final scope closure passed with zero remaining
  blocker, high, medium, or low finding and exact 12-file intent alignment.
- **Continuation review:** A fresh Codex CLI review found one medium timestamp
  precision defect and one low documentation overstatement. The client now
  validates the raw metadata spelling before Pydantic can truncate sub-microsecond
  precision, the focused suite rejects two 7-plus-digit different-instant
  mutations, and the guide limits direct-provider wording to the live chain.
  Claude Code produced no usable verdict because its Playwright MCP child hung;
  that runtime failure is recorded as `NOT_CHECKED`, not as a clean review.
- **Remaining blocking issues:** none.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.7 | 2026-07-16 | Closed fresh-review timestamp precision and Options Flow direct-provider documentation findings with red-first mutations and focused regression evidence. |
| v0.6 | 2026-07-16 | Recorded red-first implementation, actual scope, full verification, collision-safe live-smoke skip, and independent post-implementation review closure. |
| v0.5 | 2026-07-16 | Scoped the size guarantee to retained decoded bytes and added positive chart/ticker-handoff UI oracles. |
| v0.4 | 2026-07-16 | Made timestamp metadata verification explicitly instant-based with equivalent-spelling and different-instant mutation oracles. |
| v0.3 | 2026-07-16 | Made rollback non-destructive and empty/degradation/UI/traceability acceptance criteria exact and executable. |
| v0.2 | 2026-07-16 | Prevent oversized API responses from bypassing the cap through the pre-parse-unbounded local source. |
| v0.1 | 2026-07-16 | Initial test-first standalone Options Flow API consumer plan. |
