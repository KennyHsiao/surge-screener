# Quant Radar UI/UX UX-0 Baseline and Guardrails Plan

## Document Info

| Field | Value |
| --- | --- |
| Type | Executable phase plan |
| Version | v0.9 |
| Status | Technical repository baseline implemented and verified; Safari and human evidence pending |
| Date | 2026-07-16 |
| Parent | `2026-07-15-quant-radar-ui-ux-redesign.md` v0.3 |
| Phase | UX-0 — Baseline and Guardrails |
| Production UI impact | None |

## Authorization and Gate

The user asked to review the preceding phase and, if no remaining issue exists,
continue to the next phase. Phase 2K received two independent remediation
PASSes after its timestamp-parity and documentation findings were fixed. This
authorizes the evidence-only UX-0 phase; it does not authorize UX-1A or a visual
redesign.

The requested `superpowers:writing-plans`, `superpowers:executing-plans`, and
`superpowers:verification-before-completion` skills are not available in this
session. This plan applies the repository's equivalent Scribe, Lens, Voyager,
Anvil, Judge, test-first, scope-audit, and verification gates. Implementation
MUST NOT begin until independent plan review has no unresolved blocking issue.

## Goal

Create deterministic, reviewable evidence of the current real Streamlit UI at
desktop, tablet, and mobile sizes before production UI code changes. Preserve
all current routes, same-session handoffs, data/fail-soft behavior, and runtime
dependencies.

## Requirements

| ID | Requirement |
| --- | --- |
| UX0-REQ-001 | Enumerate all 27 `st.Page` definitions, `/` default behavior, 26 bookmark paths, the `today-decision` registry key, same-session route targets, and handoff keys. |
| UX0-REQ-002 | Inventory every `unsafe_allow_html=True` call and multiple raw-diagnostic presentation forms without claiming they are fixed in UX-0. |
| UX0-REQ-003 | Run the real app and critical page render functions against deterministic server-side fixtures without external provider/API calls. |
| UX0-REQ-004 | Own a collision-resistant loopback Streamlit process, wait for health/readiness, and stop only that process group on success, failure, or interrupt. |
| UX0-REQ-005 | Capture seven critical pages at 1440×900, 768×1024, and 390×844 in Chromium and WebKit where locally supported. |
| UX0-REQ-006 | Record structural measurements, console/page errors, fixture/provider call counts, tool versions, browser capability, and screenshot paths in a machine-readable manifest. |
| UX0-REQ-007 | Keep screenshots as ignored human-review artifacts; do not use screenshot hashes or pixel equality as a pass/fail oracle. |
| UX0-REQ-008 | Keep Playwright optional and local; do not add it to runtime `requirements.txt`. Missing browsers must be reported, never silently called a pass. |
| UX0-REQ-009 | Document human SUS/SEQ/task and real Safari checks as pending unless actual human/manual evidence is supplied; never synthesize participants or Safari parity. |

## Scope

### Critical routes

| Page | URL used by runner | Readiness heading |
| --- | --- | --- |
| Today Decision | `/` | 今日決策 |
| Trade State | `/trade-state` | 交易狀態 |
| Stock Checkup | `/stock-checkup` | 個股總覽 |
| Options Cockpit | `/options-cockpit` | 期權作戰台 |
| Institutions | `/institutions` | 機構面板 |
| Schedules | `/schedules` | 排程與執行結果 |
| AI Updates | `/ai-updates` | AI Agent 重點更新 |

### Viewports

- desktop: 1440×900;
- tablet: 768×1024;
- mobile: 390×844.

### Affected files

Create:

- `scripts/ui_ux_inventory.py`
- `scripts/ui_ux_fixtures.py`
- `scripts/ui_ux_fixture_app.py`
- `scripts/ui_ux_snapshot_matrix.py`
- `scripts/test_ui_ux_contract.py`
- `scripts/test_ui_ux_fixtures.py`
- `scripts/test_ui_ux_snapshot_matrix.py`
- `docs/ui-ux/quant-radar-ui-v2-baseline.md`
- `docs/ui-ux/quant-radar-ui-v2-baseline.json`
- `.agents/anvil.md`
- `.agents/voyager.md`

Modify:

- `Makefile`
- `.agents/PROJECT.md`
- `.agents/lens.md`
- `.agents/scribe.md`

This phase deliberately leaves `app.py`, `.streamlit/config.toml`, all `ui/*.py`
production modules, API code, artifacts, providers, and `requirements.txt`
unchanged. The legacy single-page `scripts/ui_snapshot.py` contract also stays
unchanged; UX-0 adds a focused owned-process runner instead.

### Generated, ignored evidence

- `.claude/ui_snapshots/ux0/<run-id>/manifest.json`
- `.claude/ui_snapshots/ux0/<run-id>/<browser>/<page>/<viewport>.png`
- `.claude/ui_snapshots/ux0/<run-id>/fixture-calls.json`
- `.claude/ui_snapshots/ux0/<run-id>/streamlit.log`

### Non-goals

- no visual, layout, navigation, copy, semantic-color, accessibility, or
  component redesign;
- no production startup hook or fixture flag in `app.py`;
- no API/provider migration, production cache change, trading logic change,
  candidate reorder, production artifact/data write, or fail-soft change;
- no pixel-golden tests and no full WCAG/Safari-conformance claim;
- no automated SUS, SEQ, task-success, or invented human research results;
- no stopping/restarting a dashboard or API process not created by the runner.

## Design

### 1. Static inventory

`scripts/ui_ux_inventory.py` will use Python `ast` and repository-relative paths
to inspect `app.py` and `ui/**/*.py` and produce stable JSON and Markdown-ready
data. UI sinks are inventoried even when their value originates in an imported
helper; test/generated/vendor modules are not silently added to the scope. It
will:

1. parse `app.py` and identify group, callable, title, icon, `url_path`, and
   `default=True` for every `st.Page` call;
2. model the default page as route `/` while retaining `today-decision` as its
   registry key; the other 26 `url_path` values are bookmark routes;
3. validate the complete load-bearing wiring in `app.py`: the comprehension
   passed to `_shared.PAGE_REGISTRY.update` maps every `p.url_path` to that same
   `p`, both loops derive from `nav.values()`, `st.navigation` receives that
   exact `nav`, and the selected result is invoked through `.run()`;
4. resolve all three current same-session routing forms: direct
   `_shared.switch_page("literal")`, `today_decision._jump(..., "literal")`,
   and `_shared.ticker_action_buttons()`' tuple table as expanded by its callers;
   the reviewed current target set is exactly `analytics-db`,
   `ibkr-reconcile`, `knowledge-graph`, `market-thesis`, `options-cockpit`,
   `options-flow`, `radar`, `retro-analysis`, `stock-checkup`, `theme-flow`,
   `trade-state`, `us-cot`, and `us-screener`;
   any unsupported/dynamic target expression fails inventory generation instead
   of being silently omitted;
5. relate the reviewed handoff contracts: `checkup_ticker` plus one-shot
   `checkup_handoff` -> Stock Checkup, sticky `cockpit_ticker` -> Options
   Cockpit, one-shot `radar_handoff` -> Radar, one-shot `validation_lane` ->
   `retro_validation_lane` on Retro Analysis, and sticky
   `theme_flow_focus_sector` -> Theme Flow. Producer, consumer, write/get/pop
   semantics are retained instead of reducing this to a name-only list;
6. find AST calls whose `unsafe_allow_html` keyword is literal `True`, retaining
   file, review-only line, called function, and whether the rendered expression
   is static or dynamic. Equality uses a normalized semantic site ID (relative
   file, enclosing function, call kind, and expression category), never a line
   number or a hard-coded aggregate count. The semantic ID includes a normalized
   location-free AST expression fingerprint plus an occurrence ordinal among
   identical fingerprints in the same enclosing function, so two same-category
   calls cannot collapse;
7. find raw-diagnostic candidates across `st.error`, `st.warning`, `st.info`,
   `st.write`, `st.markdown`, captions, expanders, and session/persisted payload
   construction. Detection covers exception names/`str(exception)`, f-strings,
   payload error fields, path values, internal URL/host/port/profile values, and
   secret-like sentinels. It is an inventory, not a zero-findings gate;
8. use lightweight intra-function name-flow tracking so indirect assignments
   such as exception -> local variable -> UI/session/persisted message remain
   visible; representative reviewed sources include Today Decision load errors,
   AI Chat persisted error messages, analytics session results, Theme Flow
   PID/log/error values, candidate command/log tails, social profile/port/token/
   path values, and knowledge/database paths;
9. sort every collection by repository-relative path, line, and stable key;
10. omit absolute paths and source payload contents from the report.

The contract test supplies synthetic AST snippets for every diagnostic category
so the scanner cannot pass merely by searching one spelling.

### 2. Fixture-only entrypoint

`scripts/ui_ux_fixture_app.py` is the only entrypoint used by the matrix runner.
Before importing Streamlit or executing production app code, a stdlib-only
bootstrap validates opt-in, root/call paths, owner marker, and run token, then
installs the fixture-only DNS/socket guard. Only after that succeeds does the
entrypoint import Streamlit, install a narrow `st.navigation` proxy, and execute
the repository's real `app.py` with `runpy.run_path`. The proxy
delegates selection to real Streamlit and returns a transparent page wrapper;
the wrapper installs data-boundary fixtures inside its `run()` immediately
before delegating to the real selected `StreamlitPage.run()`. At that point
`app.py` has already called `set_page_config`, imported all page modules, and
populated `PAGE_REGISTRY`. This avoids importing page modules before
Streamlit's required page-config command and preserves real page identity.
Production `make run` continues to execute `app.py` directly.

The runner sets this exact owned fixture environment:

```text
QUANT_RADAR_UX0_FIXTURES=1
QUANT_RADAR_UX0_FIXTURE_ROOT=<owned temporary directory>
QUANT_RADAR_UX0_CALLS_PATH=<owned output>/fixture-calls.json
QUANT_RADAR_UX0_RUN_TOKEN=<256-bit URL-safe random token>
QUANT_RADAR_UX0_FIXED_NOW=2026-07-15T06:30:00Z
SURGE_RUNTIME_DIR=<owned temporary directory>
SURGE_CANDIDATE_OUTPUT_DIR=<owned temporary directory>/candidates
SURGE_AI_CHAT_DIR=<owned temporary directory>/ai-chat
TZ=UTC
```

`scripts/ui_ux_fixtures.py` will:

- require `QUANT_RADAR_UX0_FIXTURES=1`; otherwise terminate before importing or
  patching UI modules;
- require fixture root and call output paths under runner-owned directories;
  their common run directory must contain an ownership marker with the same
  random token created by the runner invocation, validated with
  `hmac.compare_digest`, and must not resolve to the workspace/repository. The
  token is never written to logs, manifests, docs, or user-facing output;
- install deterministic high-level loaders/providers for only the seven target
  pages while preserving their actual `render()` functions and layout code;
- use fixed dates, tickers, ordering, labels, and data frames; no `datetime.now`,
  random seed based on process hash, current market data, or repository artifact
  freshness determines visible fixture values;
- increment named call counters and atomically replace `fixture-calls.json` on
  every boundary invocation;
- distinguish `attempt` at a page/cached-wrapper boundary from `execute` at an
  underlying provider when both are observable;
- redirect `_shared.DATA_DIR`, `REPORTS_DIR`, `CONTENT_DIR`, import-time Today
  Decision/candidate-control paths, runtime status, and AI Chat persistence to
  the owned root;
- reject and record non-loopback DNS resolution and socket connection attempts.
  Loopback remains allowed for Streamlit itself; a blocked external attempt
  fails the matrix even when page fail-soft logic hides the provider error;
- expose a fixture schema/revision in the counter file and manifest;
- contain no credential, user portfolio, real report, or raw exception value.

Rerun/session behavior is explicit:

- bootstrap validation and the DNS/socket guard are process-global and
  idempotent;
- the navigation proxy has a process-global sentinel and retains exactly one
  original delegate, so Streamlit script reruns cannot recursively wrap it;
- provider patches are verified/install-once by a wrapper identity marker; if a
  reloaded target loses its patch, it is restored without wrapping a wrapper;
- every browser URL carries a unique validated `ux0_capture` query value. The
  page wrapper performs session setup once for that value: cache clear, fixed
  state seed, and capture registration. Same-session Streamlit reruns do not
  clear/reset it again;
- the process-global counter uses a thread lock plus atomic replace and stores
  counts under the capture ID. The runner closes sequential contexts and waits
  for that capture bucket to become quiescent before computing its delta, so a
  closed-but-lingering prior session cannot bleed into the next capture;
- AppTests install/restore the proxy through a context manager and keep provider
  patches active for all reruns inside the test.

The reviewed patch boundaries are:

- Trade State: `scripts.trade_state.build_trade_state_rows` or the page's
  `_load_rows` cache wrapper with the underlying call counted;
- Stock Checkup: `live_factor_flags`, `score_surge`, `_fundamentals.load`,
  Options Cockpit provider, ticker-sector and sector-flow loaders, with the
  quote fallback protected and the gated full-chain/analyst/institution tabs
  asserted not to call providers;
- Options Cockpit: provider boundary with its deterministic demo DTO plus fixed
  trade-state/money-flow local inputs;
- Institutions default view: `institutional_holdings._load`; the alternate
  portfolio view additionally receives typed `load_fund_catalog` and fixed 13F
  `_load` data so AppTest can cover both data sources;
- Schedules: typed `load_schedules` state plus fixed `_RESULT_FETCHERS` results;
- AI Updates: typed `load_ai_updates` state;
- Today Decision: its persisted high-level loaders, trade-state summary, and
  candidate-control status/auth boundaries receive fixed values. Import-time
  path constants are rebound to the owned root after module import.

The implementation MAY move one level up or down only when an executable test
proves the listed seam is cached or bypassed, and the divergence is recorded in
the plan. It MUST never replace a page `render()` function. Any page that still
attempts external network is a test failure, not a reason to loosen the guard.

### 3. Owned-process matrix CLI

`scripts/ui_ux_snapshot_matrix.py` will use `argparse` and expose:

```text
--out-dir PATH
--browser {chromium,webkit}       repeatable
--page ROUTE                      repeatable
--viewport NAME|WIDTHxHEIGHT      repeatable
--json
--no-prompt
--verbose
--quiet
--version
```

Defaults are the seven pages, three named viewports, mandatory Chromium, and
WebKit when its local executable is supported. Missing mandatory/default
Chromium exits 127; missing unrequested WebKit is recorded as unsupported.
An explicitly requested unavailable browser also exits 127. `--json` writes one
JSON summary to stdout; diagnostics go to stderr. `--no-prompt` is accepted and
is the default behavior;
the command never reads stdin.

Exit codes:

| Code | Meaning |
| ---: | --- |
| 0 | all requested, supported captures and structural checks succeeded |
| 1 | owned server, readiness, render/page exception, external-call, or structural failure |
| 2 | argument/usage error |
| 3 | invalid inventory, fixture, or manifest data |
| 127 | requested Playwright package/browser executable unavailable |
| 130 | interrupted; owned process group was cleaned up |

Process lifecycle:

1. validate paths/options before starting a child;
2. bind loopback port `0` to obtain an ephemeral candidate, close the probe, and
   retry with a new candidate if the owned Streamlit child reports a bind race;
3. launch `sys.executable -m streamlit run scripts/ui_ux_fixture_app.py` on
   `127.0.0.1`, headless, with usage stats disabled and a new process session;
4. poll `/_stcore/health` with a bounded deadline while also checking child exit;
5. never inspect, signal, or kill a pre-existing PID by port/name;
6. on normal exit, exception, SIGINT, or SIGTERM, terminate then bounded-wait and
   kill only the owned process group if required;
7. preserve the log and partial manifest on failure.

Browser behavior:

- use a fresh browser context for every page/viewport capture;
- navigate with `domcontentloaded`, then wait for the supported Streamlit nav
  hook and the page's accessible heading; do not use `networkidle` for the
  persistent websocket;
- disable animation/reduced-motion and enforce a 30-second per-capture readiness
  deadline. Readiness requires the nav and expected accessible heading visible,
  no Streamlit exception element, `document.fonts.ready`, no visible loading
  skeleton/status marked running, and two consecutive animation frames with
  stable document scroll dimensions. If a visible `.js-plotly-plot` exists, its
  bounding box must be non-zero and Plotly `_fullLayout` initialized. No
  arbitrary wall-clock settle sleep is permitted;
- abort and record every browser HTTP(S) request whose destination is not
  loopback; a blocked request fails the run even when the page still paints;
- record browser console errors, uncaught page errors, failed requests,
  document/body scroll width, viewport width, horizontal overflow, sidebar and
  main-content rectangles, heading presence, and screenshot relative path;
- treat ordinary console warnings/errors and loopback request failures as
  baseline evidence unless they correspond to an uncaught page exception,
  prohibited external request, missing readiness/render result, or explicit
  security sentinel. The latter categories fail; the manifest retains both the
  raw category and pass/fail classification;
- close each context before the next capture so fixture-call deltas are
  attributable and sequential;
- clear Streamlit data caches at the start of each new fixture page session and
  pre-seed fixed session values including `cockpit_ticker=NVDA`, Stock Checkup
  single mode/ticker, and the default institution ticker;
- write `manifest.json` atomically, including failures and capability skips;
- treat unrequested missing WebKit capability as recorded `unsupported`, but
  treat missing mandatory Chromium or any explicitly requested browser as exit
  127;
- never treat a screenshot's existence or hash as visual approval.

### 4. Versioned baseline

`docs/ui-ux/quant-radar-ui-v2-baseline.json` will have two explicitly different
sections:

- `contract`: canonically sorted route/group/default/registry, same-session
  target, handoff-semantics, unsafe-HTML semantic-site, and reviewed diagnostic
  inventory data. Routine tests compare this section exactly and require an
  intentional baseline review for additions or removals;
- `evidence`: sanitized browser/tool results, viewports, structural
  measurements, call-count baseline, and capture outcomes. Routine tests check
  its schema and relationships but do not equality-pin local browser support,
  tool versions, line numbers, timestamps, ignored screenshot existence, or
  environment measurements.

It contains relative paths only and no machine username, absolute path,
credential, raw exception, response body, or current portfolio data.

`docs/ui-ux/quant-radar-ui-v2-baseline.md` will explain:

- what was automatically measured and what was visually reviewed;
- current sidebar/overflow/chat/state observations without calling them fixed;
- Chromium/WebKit capability and why WebKit is not Safari proof;
- the exact manual Safari and human usability protocol still pending;
- the UX-1A gates: approve Option A, review inventory, freeze affected files,
  and keep Playwright optional unless a later dependency review changes that.

## Acceptance Criteria

### Automated

- **AC-UX0-001:** inventory reports exactly 27 unique pages in five groups, one
  default page, `today-decision` registry key, `/`, and 26 non-default bookmark
  paths; the exact registry-comprehension -> `st.navigation(nav)` -> selected
  page `.run()` wiring is present.
- **AC-UX0-002:** every literal same-session route target resolves to a current
  page; the exact reviewed 13-target set and producer/consumer read/write/pop
  semantics remain present.
- **AC-UX0-003:** unsafe-HTML and diagnostic inventories are non-empty,
  deterministic, repository-relative, and scanner mutation fixtures pass;
  normalized semantic sites match the reviewed `contract` section without
  hard-coding an aggregate count or source line numbers.
- **AC-UX0-004:** importing/running the fixture entrypoint without the explicit
  fixture environment fails closed; production `app.py` has no fixture import;
  no page module is imported before the real app's `set_page_config` call.
- **AC-UX0-005:** a test-mode smoke proves the runner chooses a free loopback
  port, observes health, and cleans up only its child on success, startup failure,
  render failure, and simulated interrupt.
- **AC-UX0-006:** all 21 page×viewport Chromium captures render the real app with
  zero unexpected external connections, zero page exceptions, recorded call
  counts, and a manifest; WebKit repeats the 21 captures when installed.
- **AC-UX0-007:** each capture records overflow/sidebar/main measurements and
  console/request diagnostics; current UX problems are evidence, not automatic
  failures unless the page cannot render or the measurement is missing.
- **AC-UX0-008:** generated screenshots and logs are ignored; no PNG or runtime
  log is added to the tracked diff.
- **AC-UX0-009:** `requirements.txt`, production UI/API/provider files, routes,
  handoffs, and fail-soft behavior are byte-identical to the pre-phase baseline.
- **AC-UX0-010:** focused, navigation, API-consumer, full test, compile,
  Python-3.10 AST, dependency, diff, and scope-audit gates pass.
- **AC-UX0-011:** fixed-fixture AppTests execute the real `render()` function for
  each of the seven critical pages, plus both Institutions subviews, assert no
  uncaught exception, expected fixture identity, and named boundary call counts.

### Human/manual

- **AC-UX0-H01:** a human reviews every generated screenshot and records visible
  sidebar obstruction, page overflow, content overlap, clipping, and unexpected
  dynamic content. Codex may perform this visual review with image inspection,
  but cannot count it as participant SUS/SEQ evidence.
- **AC-UX0-H02:** a maintainer opens the owned fixture/default shell in real
  macOS Safari at desktop and mobile widths. Until this occurs, Safari is
  `NOT_CHECKED`; WebKit is not substituted as proof.
- **AC-UX0-H03:** the 8-participant/5-task SUS/SEQ protocol remains `NOT_RUN`
  unless real participant attempts are supplied. This does not block building
  the technical baseline, but blocks claiming the UX-0 human study complete.

## Given / When / Then Scenarios

1. **Routing:** Given current `app.py`, when inventory runs, then it returns 27
   unique definitions, `/` for the one default, 26 bookmarks, and all registry
   and same-session targets resolve.
2. **Missing fixture opt-in:** Given the fixture entrypoint without its exact
   environment, when launched, then it exits without patching or starting the
   production app.
3. **External provider attempt:** Given a target page tries a non-loopback
   DNS lookup, socket, or browser request, when fixture capture runs, then the
   attempt is recorded, the real destination is not contacted, and the matrix
   exits 1 even if application fail-soft handling still renders a page.
4. **Occupied-port race:** Given the ephemeral candidate is taken before child
   bind, when startup fails for bind conflict, then the runner retries another
   candidate without signaling the occupying process.
5. **Interrupt:** Given a running owned child, when SIGINT is simulated, then
   only its process group is stopped, a partial manifest remains, and exit is
   130.
6. **Browser capability:** Given WebKit is not installed and no explicit browser
   was requested, when matrix runs, then mandatory Chromium runs and WebKit is
   recorded as unsupported; when Chromium is missing or unavailable WebKit is
   explicit, exit is 127.
7. **Mobile evidence:** Given 390×844, when a critical page renders, then the
   manifest records actual sidebar/main rectangles and overflow even if they
   reveal the current design defect.
8. **Malformed inventory source:** Given an invalid Python or unsupported dynamic
   route declaration, when inventory runs, then it reports a stable validation
   failure and never guesses a passing contract.

## Test-First Implementation Tasks

### Task 0 — Freeze baseline and review the plan

- copy every pre-existing affected file to a unique `/tmp/surge-ux0-baseline-*`
  directory; record SHA-256 values. Also record a protected-scope hash manifest
  for `app.py`, `.streamlit/`, `requirements.txt`, `api/`, and `ui/` so the
  evidence-only phase can prove those production files stayed unchanged;
- obtain at least two independent plan reviews for scope, process lifecycle,
  fixture fidelity, CLI behavior, and executable acceptance;
- resolve all blockers before Task 1. If the same blocker survives three review
  iterations, stop and report it.

### Task 1 — Red focused tests

- create three small no-pytest harnesses matching existing repository tests:
  `test_ui_ux_contract.py` for inventory, `test_ui_ux_fixtures.py` for fixture
  safety/AppTest, and `test_ui_ux_snapshot_matrix.py` for CLI/process/manifest;
- first add route/default/registry/handoff/scanner, fixture/AppTest, and
  CLI/cleanup tests and run them red because the new modules do not yet exist;
- include mutation fixtures for duplicate route, lost default, unresolved jump,
  removed/misdirected registry update, wrong navigation source, missing selected
  page `.run()`, unsupported dynamic route expression, and two identical
  same-category unsafe calls in one function,
  dynamic unsafe HTML, exception f-string, payload error, path, URL/port/profile,
  and secret-like diagnostic patterns.

### Task 2 — Static inventory

- implement `scripts/ui_ux_inventory.py` until only inventory tests pass;
- generate and manually inspect the stable route, handoff, unsafe-HTML, and raw
  diagnostic inventory;
- do not fix production findings in this phase.

### Task 3 — Deterministic server fixtures

- add fixture module and wrapper;
- patch only high-level provider/API/artifact boundaries, never render functions;
- add typed fixture data, atomic counters, external-network guard, and fail-closed
  environment checks;
- validate the ownership marker/root boundary/run token before real app code,
  install the network guard during bootstrap, and rebind every import-time path;
- implement process-global idempotent proxy/provider setup separately from
  capture/session setup-once, locked per-capture counters, and AppTest restore;
- record `attempt`/`execute` counters where caching makes the distinction
  meaningful, and clear data caches between independent fixture sessions;
- run fixed-fixture AppTests over all seven critical real render functions and
  both Institutions subviews; keep patches active across every AppTest rerun;
- prove production `app.py` does not import or activate fixtures.

### Task 4 — Owned-process/browser runner

- implement the CLI and process manager with injectable seams for unit tests;
- pass lifecycle, exit-code, JSON-output, signal, and capability tests;
- perform one Chromium smoke on the root/mobile route before expanding matrix;
- expand sequentially to all seven pages and three viewports;
- run WebKit only after capability detection; installation is a separate local
  tool action, not a repository dependency change.

### Task 5 — Baseline evidence and documentation

- run the full matrix, inspect every screenshot, and promote a sanitized
  baseline JSON plus narrative Markdown using `apply_patch`;
- record current defects neutrally; do not claim UX improvements;
- add focused `Makefile` targets:
  - `test` invokes the fast contract test;
  - `ui-ux-baseline` invokes the optional browser matrix;
- update Anvil/Voyager/Lens/Scribe/project journals.

### Task 6 — Scope and regression review

- compare the actual diff against this affected-file list and baseline hashes;
- restore/fix unexplained scope drift;
- perform independent implementation review for bugs, child-process leakage,
  provider leaks, brittle tests, misleading browser claims, and diagnostics;
- resolve blocking findings, then rerun the full verification matrix.

## Verification Commands

```bash
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/ui_ux_inventory.py --json
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_ui_read_api.py
.venv/bin/python scripts/test_ui_ai_updates_api.py
.venv/bin/python scripts/test_ui_fund_catalog_api.py
.venv/bin/python scripts/test_ui_iv_history_api.py
.venv/bin/python scripts/test_ui_options_flow_api.py
.venv/bin/python scripts/ui_ux_snapshot_matrix.py --no-prompt
make test
.venv/bin/python -m py_compile scripts/ui_ux_inventory.py scripts/ui_ux_fixtures.py scripts/ui_ux_fixture_app.py scripts/ui_ux_snapshot_matrix.py scripts/test_ui_ux_contract.py scripts/test_ui_ux_fixtures.py scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python -m pip check
git diff --check
git status --short
```

If a Python 3.10 executable is unavailable, parse every changed Python file with
`ast.parse(..., feature_version=(3, 10))` and report that as a syntax-grammar
check, not as a Python 3.10 runtime test.

Additional runtime probes:

- confirm no Streamlit child/process group remains after success, failure, and
  interrupt tests;
- confirm a deliberately occupied unrelated port/PID survives unchanged;
- confirm fixture call counts stabilize and `external_connection_attempts=0`;
- confirm PNG/log evidence remains ignored;
- compare SHA-256 for every pre-existing out-of-scope production file against
  the Task 0 baseline.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Fixture replaces rather than exercises real UI | prohibit patching `render`; patch only high-level data boundaries and assert source identity |
| Page modules import before `set_page_config` | proxy only `st.navigation`; install page fixtures after real app imports and immediately before real page run |
| A provider escapes the fixture | non-loopback socket guard, named counters, zero-attempt acceptance |
| Fail-soft hides an attempted provider call | DNS/socket/browser guards record the attempt out-of-band and fail the matrix |
| Streamlit rerun recursively wraps fixtures | process-global proxy/provider sentinels plus capture/session setup-once and AppTest restoration |
| Runner kills the user's dashboard | new process session, owned PID/group only, no `pkill`, no fixed-port stop logic |
| Port probe race | bounded ephemeral retry on child bind failure; never reclaim a port |
| Websocket makes readiness hang | health poll + DOMContentLoaded + explicit nav/heading readiness, no networkidle |
| Snapshot flakiness | fixed server data, reduced motion, explicit DOM/chart readiness, structural assertions, human visual review |
| Scanner misses diagnostic forms | AST categories plus synthetic mutation fixtures; inventory is reviewed, not accepted by count alone |
| Two unsafe sites collapse to one ID | normalized expression fingerprint plus same-function occurrence ordinal and duplicate-site mutation |
| Page declarations pass while registry wiring is broken | AST-mutate registry update, navigation source, and selected-page run wiring |
| Baseline becomes machine/line-number brittle | exact equality only for normalized `contract`; validate `evidence` by schema and relationships |
| Test tooling leaks into runtime | separate runner, no `requirements.txt` change, optional Make target |
| Existing console noise prevents a baseline | record console/request evidence; fail only uncaught render, external network, readiness, structural, or security categories |
| Baseline leaks local data | fixture-only data, relative paths, sanitizer and sentinel tests |
| Automated evidence is overstated | explicit `NOT_CHECKED`/`NOT_RUN` for Safari and human study |

## Rollback

UX-0 has no production UI/data migration. Rollback removes the newly created
UX-0 scripts/tests/docs/journals and reverts every UX-0 Makefile and existing
journal change. Ignored evidence can be deleted independently. No route,
session, API, provider, artifact, or data rollback is required.

## Traceability

| Requirement | Design/Task | Primary evidence |
| --- | --- | --- |
| UX0-REQ-001 | inventory; Tasks 1–2 | route/registry/handoff contract tests and baseline JSON |
| UX0-REQ-002 | inventory; Tasks 1–2 | scanner mutations and reviewed findings list |
| UX0-REQ-003 | fixtures; Task 3 | real-render smoke, fixture counters, zero external attempts |
| UX0-REQ-004 | process manager; Task 4 | lifecycle/port/signal tests and process audit |
| UX0-REQ-005 | browser matrix; Task 4 | 21 captures per supported browser |
| UX0-REQ-006 | manifest; Tasks 4–5 | generated and promoted sanitized JSON |
| UX0-REQ-007 | output policy; Task 5 | ignore check and human screenshot review |
| UX0-REQ-008 | capability/dependency policy | explicit unavailable probe, unchanged requirements |
| UX0-REQ-009 | baseline narrative | Safari/human status fields and no synthetic results |

## Implementation and Verification Record

- The protected pre-phase scope contains 47 files across `app.py`,
  `.streamlit/`, `requirements.txt`, `api/`, and `ui/`; every recorded SHA-256
  value remained unchanged after UX-0.
- The static contract reports 27 pages in five groups, one `/` default, 26
  bookmark routes, 13 same-session targets across 32 sites, five handoff
  contracts using seven state keys, 31 unsafe-HTML semantic sites, and 177
  diagnostic candidates.
- Focused verification passed 12/12 contract tests, 8/8 fixture/AppTest groups,
  and 15/15 browser-runner tests. The final owned Chromium matrix passed all
  21 page-by-viewport captures; all 21 capture counters became quiescent, with
  zero page exceptions, external requests, blocked server network attempts, or
  failed browser requests. WebKit was recorded as unsupported.
- Response-level evidence retains 36 route-relative Streamlit 404 probes for
  `/<page>/_stcore/health` and `/<page>/_stcore/host-config`; they are not
  hidden or misreported as provider/API failures.
- Codex inspected all 21 generated PNGs. The existing mobile sidebar
  obstruction, tablet compression, navigation disclosure, floating AI-control
  crowding, and inconsistent desktop hierarchy are documented as findings, not
  as successful UX outcomes.
- Real macOS Safari remains `NOT_CHECKED`, and the participant SUS/SEQ/task
  protocol remains `NOT_RUN`. They do not block the technical repository
  baseline, but they block any claim that manual UX research is complete.
- Implementation review initially returned `REQUEST CHANGES` for lifecycle,
  network-boundary, WebSocket/service-worker, counter-quiescence, test-coverage,
  sanitization, contract-ordering, evidence-schema, and attribution gaps. The
  implementation added response-level HTTP evidence, reverse-DNS and datagram
  guards, explicit WebSocket/service-worker interception, bounded quiescence,
  strict child environments, stronger sanitization, fail-closed routing
  inventory, and exact evidence relationships. These changes were required to
  make the planned evidence trustworthy and did not expand production scope.
- Independent runtime and contract closure reviews passed with no blocker,
  high, or medium finding after remediation. The remaining schema/path and
  plan-status lows were also fixed before this record was finalized.

## Review Record

- **Review 1 — fixture/process/runtime:** FAIL with four medium and one low.
  v0.7 added early fail-closed/network bootstrap, same-run ownership token,
  rerun-safe process/session layers, locked per-capture counters, mandatory
  Chromium, and bounded readiness.
- **Review 1 — contract/inventory:** FAIL with two medium. v0.7 added unique
  unsafe-site fingerprints/ordinals and exact registry/navigation/run wiring
  plus mutations.
- **Review 2 — contract closure:** PASS with no finding.
- **Review 2 — fixture/runtime closure:** PASS with no blocker/high/medium and
  one rollback-wording low; v0.8 fixed the low before implementation.
- **Implementation review — runtime/evidence:** REQUEST CHANGES with six medium
  findings. Startup-interrupt ownership, DNS/datagram coverage, browser
  WebSocket/service-worker interception, counter quiescence, lifecycle/AppTest
  coverage, and evidence sanitization were remediated; closure PASS had no
  blocker, high, or medium finding.
- **Implementation review — contract/scope:** REQUEST CHANGES with four medium
  findings. Unsupported routing forms now fail closed, location-free set-like
  contract data is canonicalized, evidence fields and aggregates are validated
  exactly, and Codex image inspection is no longer labeled as human evidence.
  Closure PASS had no blocker, high, or medium finding. Its two defense-in-depth
  lows were subsequently closed by exact evidence-key/path allowlists and this
  completed-status update.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-07-16 | Initial executable UX-0 plan with evidence-only scope, owned-process CLI, deterministic server fixtures, static inventories, browser capability policy, and explicit manual/human limitations |
| v0.2 | 2026-07-16 | Closed investigation findings by deferring fixture imports until after page config, freezing all routing forms/13 targets/handoff semantics, adding indirect diagnostic taint categories, exact provider seams, protected-scope hashes, and seven-page plus Institutions-subview AppTests |
| v0.3 | 2026-07-16 | Separated exact static contract from environment evidence, made dynamic route expressions fail closed, and replaced line/count equality with reviewed semantic-site IDs |
| v0.4 | 2026-07-16 | Froze the post-page-config navigation wrapper, owned-root environment/marker, import-time path rebinding, exact page seams, attempt/execute counters, cache reset, fixed session state, and server/browser external-network guards |
| v0.5 | 2026-07-16 | Corrected actual readiness headings, froze inventory roots, distinguished temporary from production writes/caches, used `sys.executable`, and reconciled console evidence with runtime-failure exit semantics |
| v0.6 | 2026-07-16 | Split inventory, fixture/AppTest, and runner lifecycle verification into three independently owned focused test scripts |
| v0.7 | 2026-07-16 | Closed first plan review findings with early fail-closed/network bootstrap, same-run token ownership, rerun-safe global/session layers, locked per-capture counters, mandatory Chromium, bounded chart readiness, collision-free unsafe site IDs, and exact registry/navigation/run wiring mutations |
| v0.8 | 2026-07-16 | Recorded two independent closure PASSes, corrected complete journal rollback wording, and accepted UX-0 for implementation |
| v0.9 | 2026-07-16 | Recorded the implemented technical baseline, final 12/8/15 focused and 21/21 Chromium evidence, independent remediation closure, exact evidence-schema/path hardening, unchanged protected scope, and explicit pending Safari/human evidence |
