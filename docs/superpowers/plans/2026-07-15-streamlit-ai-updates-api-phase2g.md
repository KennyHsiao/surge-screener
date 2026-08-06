# Streamlit AI Updates API Consumer Phase 2G Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v0.6 |
| Status | Implemented and verified; post-implementation findings closed |
| Author | Codex |
| Reviewer | Repository maintainer / independent implementation reviewers |
| Audience | Maintainers of the Streamlit-to-loopback read boundary |
| Related endpoint phase | `2026-07-15-fastapi-ai-updates-phase2d.md` |
| Prior consumer phase | `2026-07-15-streamlit-schedules-api-phase2f.md` |

## Goal

Make the existing Streamlit **AI Agent 重點更新** page consume the completed
`GET /api/v1/system/ai-updates` endpoint without making the page less resilient
when the loopback API is starting, stopped, or defective.

Success means the feed is API-first, expected artifact failures remain safe UI
states, client failures use a visible strict local fallback, and the existing
newest-first cards, tag filter, links, navigation, and visual layout remain
behaviorally unchanged.

## Why This Is the Next Slice

No accepted roadmap names a phase after Phase 2F. AI Updates is the smallest
remaining end-to-end consumer slice:

- Phase 2D already provides a fixed, parameterless, strict public endpoint.
- `ui/sys_ai_updates.py` is its only Streamlit consumer and still reads the fixed
  source directly.
- The source has no runtime writer, path override, provider call, private data, or
  mutation.
- Moving schedules result/status, candidate aggregates, fund holdings, or live IV
  data would cross additional DTO, privacy, or provider boundaries.

## Architecture

Extend `ui/_read_api.py` with one fixed AI Updates client while retaining the
Phase 2F transport boundary. Extract exactly one private response reader with the
internal contract
`_read_fixed_json(url, max_response_bytes, transport) -> bytes | ClientFailureReason`.
It owns client construction, the response-stream lifecycle, HTTP/header gates, and
decoded-body cap. The schedules request passes its existing 2 MiB constant; the AI
Updates request passes a separate 16 MiB constant. Public loaders expose only the
keyword-only test transport and never accept URL, host, port, path, source, cap, or
timeout overrides.

Each endpoint-specific request coroutine calls the shared reader and then validates
its own strict envelope, source ID, and metadata. Separate endpoint deadline wrappers
place the complete request coroutine—connect, headers, body, envelope, and metadata
validation—inside `asyncio.wait_for(..., timeout=1.0)`. The shared reader MUST NOT
select adapters or weaken endpoint-specific validation.

The public AI Updates client returns exactly one of:

- `AiUpdatesApiAvailable(updates=tuple[AiUpdateItem, ...])`
- `AiUpdatesApiUnavailable(reason=<artifact reason>)`
- `AiUpdatesApiFailure(reason=<stable client reason>)`

`AiUpdatesApiFailure` MUST reuse the Phase 2F `ClientFailureReason` union exactly:
`transport_error`, `deadline_exceeded`, `http_status`, `invalid_media_type`,
`invalid_cache_control`, `response_too_large`, or `invalid_envelope`.

The client preserves source order. The page resolver performs the existing stable
descending date sort before rendering. A valid API unavailable envelope is
authoritative. Only transport, HTTP, response-header, size, or envelope failures
invoke `read_artifact(ARTIFACTS["system.ai-updates"])`, followed by strict
`AiUpdatesData` parsing. No raw exception, body, URL, path, or source `_note` enters
the state or UI.

This is a server-side Streamlit-to-loopback request. The browser does not call
FastAPI directly, and this phase adds no CORS or non-loopback exposure.

## Requirements

- `REQ-2G-001`: The request MUST be exactly
  `GET http://127.0.0.1:8000/api/v1/system/ai-updates`, with no caller-supplied
  host, port, path, query, source ID, or filter.
- `CFR-2G-001`: The client MUST retain `trust_env=False`,
  `follow_redirects=False`, exact 0.25-second connect/read/write/pool inactivity
  timeouts, a Python-3.10-compatible cancellable 1.0-second whole-request deadline,
  and `Accept: application/json`. The existing schedules cap remains exactly 2 MiB;
  AI Updates uses an endpoint-specific exact 16 MiB decoded-body cap so the maximum
  schema-valid 200-item Unicode envelope remains representable even when JSON uses
  Unicode escapes.
- `CFR-2G-002`: HTTP 200 is accepted only with an `application/json` media type,
  a case-insensitive `no-store` cache directive, and strict validation through
  `ArtifactAvailable[AiUpdatesData] | ArtifactUnavailable`.
- `CFR-2G-003`: Every accepted envelope MUST use
  `meta.sourceId=system.ai-updates` and null `meta.generatedAt`. Available data MUST
  use the maximum update date as `meta.asOf`, or null for a valid empty feed.
  Unavailable data MUST use null `meta.asOf`.
- `REQ-2G-002`: Available data MUST preserve all public values and source order in
  the client result. `_note`, unknown fields, invalid dates, unsafe links, duplicate
  tags, or any other DTO defect MUST become `invalid_envelope`, never partial UI.
- `REQ-2G-003`: A valid API `available=false` response for `missing`,
  `invalid_json`, `invalid_shape`, or `unreadable` is authoritative. The page MUST
  show a stable reason-specific unavailable state and MUST NOT bypass it locally.
- `REQ-2G-004`: Connect/read failures, deadline expiry, non-200 responses,
  redirects, invalid headers, oversized bodies, malformed JSON, or contract drift
  MUST NOT crash the page. The exact mapping is: HTTPX request/read failure to
  `transport_error`; whole-request timeout to `deadline_exceeded`; every non-200
  status, including redirects, to `http_status`; missing/wrong media type to
  `invalid_media_type`; missing `no-store` to `invalid_cache_control`; decoded body
  above the endpoint-specific cap to `response_too_large`; and malformed JSON,
  strict DTO, source ID, or metadata mismatch to `invalid_envelope`.
- `REQ-2G-005`: Only client failures trigger local fallback. The fallback MUST use
  `read_artifact(ARTIFACTS["system.ai-updates"])` and strict `AiUpdatesData`
  parsing; it MUST NOT duplicate or weaken raw-source validation or projection.
- `CFR-2G-004`: Client-failure fallback MUST be visible through generic Traditional
  Chinese copy containing no raw diagnostic. If both sources fail, the page MUST
  render a safe all-sources-unavailable state.
- `CFR-2G-007`: The local fallback logger MAY emit only a fixed event string and the
  exception class name. Exception messages, response/source bodies, tracebacks,
  absolute paths, environment values, URLs, and source `_note` MUST NOT be logged.
- `CFR-2G-005`: API failures and fallback results MUST NOT be negatively cached.
  Every Streamlit rerun performs a fresh API request so repair is immediately
  observable.
- `REQ-2G-006`: The page MUST retain stable newest-first sorting, OR tag filtering,
  bordered cards, title/date/summary/tag rendering, optional HTTPS link button, and
  the no-match state. Valid empty data receives a distinct empty-feed message.
- `CFR-2G-006`: This phase MUST NOT redesign the UI/UX. Navigation, information
  architecture, component layout, styling, responsive behavior, and unrelated page
  copy remain unchanged except for accurate API/fallback/unavailable notices.

## UI States

| State | Feed source | UI behavior |
| --- | --- | --- |
| API available, non-empty | API | Stable date-descending cards and existing filters |
| API available, empty | API | Show a valid-empty feed message |
| API valid unavailable | None | Show safe reason-specific information; no local bypass |
| API client failure + valid local feed | Local fallback | Show sanitized degradation warning, then normal cards |
| API client failure + valid empty local feed | Local fallback | Show warning plus valid-empty message |
| API client failure + invalid/missing local feed | None | Show warning plus all-sources-unavailable information |

Authoritative unavailable copy is fixed and tested for every reason:

| Reason | Safe detail |
| --- | --- |
| `missing` | 找不到 AI 更新資料。 |
| `invalid_json` | AI 更新資料尚未完整寫入或 JSON 格式無效。 |
| `invalid_shape` | AI 更新資料格式不符合預期。 |
| `unreadable` | AI 更新資料目前無法讀取。 |

## Scope and Affected Files

### Create

- `scripts/test_ui_ai_updates_api.py` — focused fixed-client, resolver, recovery,
  sorting, and AppTest behavior tests.
- This plan document.

### Modify

- `ui/_read_api.py` — shared fixed loopback response mechanics plus endpoint-specific
  AI Updates adapter, metadata validation, typed results, and sync entry point.
- `ui/sys_ai_updates.py` — API-first resolver, strict local fallback, safe notices,
  stable date sorting, and typed rendering.
- `scripts/test_dashboard_navigation.py` — static contract for fixed URL, strict
  fallback, preserved UI controls, and documented topology.
- `Makefile` — add the focused Phase 2G test to `make test`.
- `docs/USER_GUIDE.md` — document two-terminal behavior, accurate AI Updates data
  flow, fail-soft states, fixed port, and Docker fallback.
- `docs/api/fastapi-endpoint-artifact-inventory.md` — mark the AI Updates Streamlit
  consumer API-first.
- `.agents/PROJECT.md`, `.agents/lens.md`, `.agents/scribe.md`, and
  `.agents/builder.md` — record decisions and verification evidence.

### Regression-only; do not edit unless a failing test proves it necessary

- `scripts/test_ui_read_api.py` — Phase 2F transport/deadline/size and schedules
  consumer regression suite.
- `scripts/test_api.py` — Phase 1-2E API contract regression suite.

### Do not modify

- `api/**`, checked-in OpenAPI, `content/ai_updates.json`, artifact loaders or
  writers, dependencies, app navigation, other Streamlit pages, deployment/systemd,
  CORS/auth/bind settings, or Docker topology.

The working tree already contains cumulative Phase 1-2F changes. All edits MUST be
applied on top of that dirty baseline without reverting or rewriting unrelated work.
Before adding red tests, create `/tmp/surge-phase2g-baseline-20260715/`, capture
`git status --short` and SHA-256 output in the execution record, and copy every
existing Phase 2G affected file there with its relative directory structure. Record
the new focused test as initially absent. At final review, use baseline-to-current
diffs for overlapping files and `/dev/null`-to-current diffs for every Phase 2G
untracked file, including this plan. Repository `git diff` alone is not sufficient.

## Test-First Implementation Tasks

### 1. Lock the endpoint-specific client contract

- Add red tests for exact method/URL, absent query, JSON accept header, one request,
  available source-order/value preservation, and valid empty data.
- Use `inspect.signature()` to prove both `load_schedules` and `load_ai_updates`
  expose exactly one keyword-only optional `transport` parameter and no
  URL/host/port/path/source/cap override. Lock `_read_fixed_json` to exactly three
  keyword-only parameters—required `url`, required `max_response_bytes`, and
  required `transport`—so the private extraction cannot silently absorb an adapter,
  source ID, metadata policy, deadline, or public override.
- Call `_read_fixed_json` with correctly headed schema-invalid JSON and prove it
  returns the raw bytes unchanged; then prove each endpoint adapter maps that same
  kind of body to `invalid_envelope`. This keeps DTO/source/metadata validation out
  of the shared transport helper and inside endpoint request/deadline flows.
- Assert exact `sourceId`, null `generatedAt`, maximum-date/empty `asOf`, and reject
  mismatched metadata, `_note`, unknown fields, malformed data, or wrong source ID.
- Assert all four unavailable reasons remain typed unavailable results.
- Exercise the complete seven-value failure mapping through the AI Updates public
  loader. Retain the Phase 2F full timeout, redirect, body-cap, gzip, slow-header,
  and Python-3.10 regression suite unchanged as shared-reader proof.
- Build a maximum schema-valid 200-item AI envelope using maximum-length astral
  Unicode strings, maximum unique tags, and a maximum HTTPS link. Serialize it with
  ASCII Unicode escaping and prove it is below the exact 16 MiB cap and accepted.
  Pad a valid body with JSON whitespace to exactly the cap and accept it; stream
  cap-plus-one bytes and require `response_too_large` plus stream cleanup. Keep the
  schedules 2 MiB boundary regression unchanged.

### 2. Lock page resolution and rendering

- Add red resolver tests proving authoritative unavailable never reads locally.
- Prove only client failures use the exact strict registry fallback.
- Cover local available, valid empty, invalid model, unavailable, and unexpected
  fallback exceptions without raw diagnostic leakage.
- Capture fallback logger output for an exception whose message contains a secret,
  URL, traceback marker, and absolute path. Assert only the fixed event and exception
  class are present; the message, traceback, path, URL, and secret are absent from
  logs, state repr, and rendered UI.
- Prove one failed rerun followed by a healthy API response recovers immediately.
- Prove stable newest-first ordering, OR tag filtering, optional link rendering,
  no-match copy, and all six UI states with no `AppTest.exception`.
- Use separate AppTest fixtures to prove the existing tag-control threshold: three
  or fewer distinct tags hides the multiselect, more than three shows it with an
  empty default, and the shown control retains intersection-based OR behavior.
- Assert same-date items retain source-relative order after the stable descending
  sort, and assert the exact safe detail for each of the four unavailable reasons.
- Mirror the Phase 2F `FrozenInstanceError` test for all three AI Updates outcomes.

### 3. Implement the client and page

- Extract the exact private response-reader contract defined above. Keep both
  endpoint DTO/metadata adapters inside their endpoint request/deadline flows.
- Add typed immutable AI Updates outcomes and the uncached sync loader.
- Add the page state union, strict fallback, safe copy, typed attribute rendering,
  and stable date sort without changing card/filter layout.

### 4. Update static contracts and documentation

- Add the focused test to `make test` and static navigation/data-flow assertions.
- Correct the guide's current direct-file/cache/UI-validation statements.
- Update the architecture diagram to show both migrated consumers and retain the
  explicit local-read branch for unmigrated pages.
- Mark only the AI Updates consumer as migrated; do not claim full frontend or full
  page migration elsewhere.

## Verification Gates

Run, in order:

1. `.venv/bin/python scripts/test_ui_ai_updates_api.py`
2. `.venv/bin/python scripts/test_ui_read_api.py`
3. `.venv/bin/python scripts/test_dashboard_navigation.py`
4. `.venv/bin/python scripts/test_artifact_loader.py`
5. `.venv/bin/python scripts/test_api.py`
6. `.venv/bin/python -m compileall -q ui api scripts/test_ui_ai_updates_api.py`
7. Run the exact Python 3.10 grammar gate:
   `.venv/bin/python -c 'import ast,pathlib; files=["ui/_read_api.py","ui/sys_ai_updates.py","scripts/test_ui_ai_updates_api.py","scripts/test_dashboard_navigation.py"]; [ast.parse(pathlib.Path(f).read_text(encoding="utf-8"), filename=f, feature_version=(3,10)) for f in files]'`.
8. `make test`
9. `.venv/bin/python -m pip check`
10. `git diff --check`
11. Collision-safe real-Uvicorn healthy AppTest smoke on fixed port 8000: pre-bind
    the port, start Uvicorn only with the owned listener/process, stop only that
    owned process, and prove cleanup. If port 8000 is already occupied, explicitly
    skip this optional process smoke; an existing/unknown responder MUST NOT count
    as passing evidence. MockTransport and AppTest failure/fallback coverage remains
    mandatory.

Before completion, compare the actual baseline-to-current and new-file diffs against
this affected-file list, including every untracked file, and run a fresh review for
bugs, regressions, missing tests, maintainability, secret/path leaks, and unexplained
scope drift. Blocking findings MUST be fixed.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Shared-client refactor regresses schedules | Fixed helper boundary, unchanged 2 MiB cap/public signature, and unchanged Phase 2F regression suite |
| Legal maximum AI envelope exceeds the schedules cap | Separate exact 16 MiB AI cap plus escaped maximum-valid/exact-cap/cap-plus-one tests |
| API unavailable is incorrectly bypassed | Separate typed unavailable from client failure; assert local reader is not called |
| `asOf` drift accepts stale/forged metadata | Recompute maximum public update date and require exact equality |
| Existing newest-first UI changes | Keep source order in client; stable-sort only in page resolver and test ties |
| Invalid local source becomes partially visible | Reuse registry loader plus strict public DTO; no permissive dictionary rendering |
| Raw diagnostics or `_note` leak | Typed reasons only; sentinel tests across repr and rendered copy |
| Fallback logging leaks raw exception/path data | Fixed event plus class-only log contract and captured-log sentinel assertions |
| API outage becomes sticky | No Streamlit or HTTP response cache; consecutive-result recovery test |
| Fixed port or Docker behavior surprises users | Document fixed 8000 and Streamlit-only Compose fallback explicitly |
| Scope is mistaken for UI redesign | Explicit non-goal and static checks for unchanged navigation/card/filter behavior |
| Dirty working tree loses prior work | Pre-implementation copies and hashes; baseline-to-current/new-file audit; never reset unrelated changes |
| Unrelated port-8000 process produces a false smoke PASS | Owned-listener protocol; occupied port is a documented skip, never evidence |
| Tag-filter visibility changes accidentally | AppTest both sides of the exact three-tag threshold plus OR filtering |
| Caller expands fixed trust boundary through a URL override | `inspect.signature` locks both public loaders to keyword-only test transport and locks the private helper boundary |

## Rollback

Revert the AI Updates additions in `ui/_read_api.py`, restore the prior guarded
local `_load_updates()`, remove the focused test and Makefile entry, and revert the
Phase 2G documentation updates. No API, OpenAPI, source artifact, writer, data
migration, dependency, deployment, or Docker rollback is required.

## Traceability

| Requirement | Implementation target | Verification |
| --- | --- | --- |
| `REQ-2G-001`, `CFR-2G-001`, `CFR-2G-002` | Fixed URL and shared response reader | Exact request/config plus Phase 2F transport regression |
| `CFR-2G-003`, `REQ-2G-002` | Strict AI Updates adapter and metadata check | Available/empty/order/value/metadata/invalid-envelope tests |
| `REQ-2G-003` | Typed authoritative unavailable branch | Four reasons and no-local-read assertions |
| `REQ-2G-004`, `CFR-2G-004`, `CFR-2G-007` | Exact shared seven-value failure union, safe notices, class-only fallback logging | Complete mapping matrix, maximum/cap tests, log sentinel, all-source AppTest states |
| `REQ-2G-005`, `CFR-2G-005` | Registry fallback and uncached rerun resolver | Strict fallback and immediate-recovery tests |
| `REQ-2G-006`, `CFR-2G-006` | Typed page renderer with existing layout | Sorting/filter/link/AppTest/static navigation regressions |

## Implementation Evidence

Phase 2G is implemented without a UI/UX redesign.

- `ui/_read_api.py` now shares only fixed response transport mechanics. The AI
  Updates adapter owns its strict DTO/source/metadata checks and exact 16 MiB cap;
  schedules keeps its public signature, endpoint behavior, and 2 MiB cap.
- `ui/sys_ai_updates.py` is API-first. A valid unavailable envelope is
  authoritative; only the exact seven stable client failures use the strict
  `ARTIFACTS["system.ai-updates"]` fallback. The complete fallback path fails soft,
  and unexpected errors log fixed event text plus exception class only.
- Existing stable newest-first cards, same-date source order, bordered layout,
  date column, summaries, tag chips, `>3` tag-control threshold, OR filtering,
  optional links, navigation, and styling remain unchanged. Tests now lock those
  behaviors explicitly.
- Passing evidence after the final fixes: AI Updates focused `17/17`, schedules
  consumer `12/12`, dashboard `47/47`, artifact loader `14/14`, API `36/36`, and
  the complete `make test` suite. Compilation, the exact Python 3.10 AST command,
  `pip check`, `git diff --check`, and trailing-whitespace checks also pass.
- Fixed port 8000 was already occupied by PID 38344, so the optional owned-process
  Uvicorn smoke was skipped exactly as specified. The existing responder returned
  a valid `system.ai-updates` envelope in a supplementary GET, but it was not
  counted as owned-process verification. Streamlit on port 8501 returned HTTP 200.
- Baseline-to-current review found only the planned files. No API/OpenAPI, source
  artifact, dependency, Docker, deployment, navigation, or unrelated page changed
  in Phase 2G.
- Two independent post-implementation reviews found two medium gaps: the strict
  fallback validation exception boundary and incomplete UI-preservation oracles.
  Both were fixed and independently re-reviewed with no regression. One inherited
  low-priority hardening observation remains outside this phase: shared tag-chip
  HTML does not escape labels; that renderer predates Phase 2G and was not changed.

Before red tests, the dirty Phase 1-2F status was captured and every existing
affected file was copied under `/tmp/surge-phase2g-baseline-20260715/`; the new
`scripts/test_ui_ai_updates_api.py` was recorded as absent. The baseline SHA-256
manifest is:

```text
b6059c6012a82f367607b774696b64c31d2bb5caabd77ecd8ceddd46ad78e3e5  .agents/PROJECT.md
b9b4f5b4511352ccc641cec5d67dbdf965b3e7f69ba59f52e1718fff1a4900e2  .agents/builder.md
e32301e53464cb8fb79655c7a693e3749f60b2013b86724b2fb230e0209ec0b9  .agents/lens.md
072817c8dd7211940c33a5c3383e9e0f700dbadcd5f721fab258bf6199710a4b  .agents/scribe.md
b1828313b6acceae7e06c6f28068930b6b0fd9f70bded99381fe60f1b421f906  Makefile
fa69b90df024b6662b01fc59ed894ec9128fdea45ec31272dc88b811050cb28f  docs/USER_GUIDE.md
81b8286f25e87bfd6ca350e1f6f0a4f9c48f9516af06e6e4a71146a30a6513a1  docs/api/fastapi-endpoint-artifact-inventory.md
7a3df061e1513503e2787f085baabb48a4c69186219d8e14176168f2fb27d18b  docs/superpowers/plans/2026-07-15-streamlit-ai-updates-api-phase2g.md
c29290a0bfb029f3cda71417313e5dee8377ebb44eb32bca74012bbf661fa187  scripts/test_dashboard_navigation.py
603ae60c7a381c63e4d6c876ffc34d38bfc59d00e3e35424680d5fa1ec9c499b  ui/_read_api.py
49e090faa478594d4b26673561f9fd7f96e2277144b85f95764bdb258bd07299  ui/sys_ai_updates.py
```

## Pre-Implementation Blocker Review

| Iteration | Verdict | Findings | Resolution |
| --- | --- | --- | --- |
| 1 | FAIL | Dirty baseline could not isolate Phase 2G changes or rollback; existing listener could be a false process-smoke oracle; tag-filter threshold and exact seven-value failure mapping were not executable; Python 3.10 gate lacked a command. | v0.2 requires pre-implementation copies/hashes and baseline/new-file diffs, owned-listener-or-skip smoke, `<=3`/`>3` AppTest fixtures, the complete failure matrix, and an exact AST command. |
| 2 | FAIL | One reviewer confirmed v0.2 closed all first-round findings. Adversarial review then found the schedules 2 MiB cap could reject a maximum-valid Unicode AI envelope; the public loader signature, fallback log output, filter default/stable ties/four reason messages, helper boundary, and outcome immutability lacked exact oracles. Its duplicate listener finding was already resolved by v0.2. | v0.3 uses a separate exact 16 MiB AI cap with escaped maximum-valid/exact/cap-plus-one tests, locks the public signature, captures class-only logs, specifies exact UI/metadata behavior, fixes the private helper/deadline boundary, and tests immutability. |
| 3 | FAIL | Both reviewers found the public/shared-helper boundary still under-tested: only the new AI loader signature was locked, not the existing schedules loader or exact private helper, and no raw-bytes specimen proved schema validation stayed endpoint-specific. | v0.4 locks all three signatures and requires shared-raw-bytes plus endpoint-invalid-envelope oracles. This is the second occurrence of the public-boundary blocker, below the three-iteration stop threshold. |
| 4 | PASS | Two independent reviewers confirmed the public/helper boundary, endpoint-specific cap, metadata, fallback, log, UI, compatibility, listener-ownership, and dirty-baseline gates are executable with no remaining blocker. | Plan accepted for implementation. |

Implementation MUST NOT begin until this table records a PASS and every blocking
finding is resolved. If the same blocker remains after three review iterations,
stop and report it rather than executing.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-07-15 | Initial test-first Phase 2G AI Updates consumer plan. |
| v0.2 | 2026-07-15 | Resolve dirty-baseline, listener-ownership, filter-threshold, failure-mapping, and Python-3.10 gate findings. |
| v0.3 | 2026-07-15 | Separate the AI response cap and close maximum-envelope, public-signature, log-leak, helper-boundary, and exact UI-oracle gaps. |
| v0.4 | 2026-07-15 | Lock both public loader signatures, the exact private helper signature, and the raw-bytes versus endpoint-validation separation. |
| v0.5 | 2026-07-15 | Accept the plan after two independent final reviews found no remaining blocker. |
| v0.6 | 2026-07-15 | Record implementation, dirty-baseline evidence, full verification, occupied-port smoke skip, and closure of both post-implementation findings. |
