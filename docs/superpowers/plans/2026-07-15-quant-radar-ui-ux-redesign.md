# Quant Radar UI/UX Redesign Plan

## Document Info

| Field | Value |
| --- | --- |
| Type | Cross-page UI/UX redesign roadmap and implementation gate |
| Version | v0.4 |
| Status | In progress; UX-0 and UX-1A complete, later phases separately gated |
| Author | Codex |
| Reviewer | Repository maintainer plus independent UX/code reviewers |
| Audience | Product owner, UI implementers, accessibility reviewers, and maintainers |
| Scope tier | Macro, with separately shippable Micro/Meso batches |
| Related inventory | `docs/api/fastapi-endpoint-artifact-inventory.md` |

## Separation Contract

This plan is intentionally independent from the phased Streamlit-to-FastAPI
migration. API phases may continue while this document is reviewed.

UI/UX work MUST NOT:

- alter API routes, response envelopes, DTOs, provider behavior, artifact
  semantics, trading calculations, candidate ordering, or fail-soft rules;
- turn an API `available=false` result into an exception or silently bypass an
  authoritative unavailable response;
- remove or rename any existing `url_path`, session-state handoff key, provider
  cache, manual identifier input, or same-session `st.switch_page()` route;
- combine UI redesign, API migration, provider changes, and data-model changes in
  one implementation batch.

Every implementation batch requires its own accepted affected-file list,
baseline, tests, and rollback notes before code changes begin.

## Problem Statement

The current app is functionally broad but presents four cross-cutting risks:

1. Dynamic values can reach `unsafe_allow_html=True` through shared chips and
   page-local HTML, while some error paths display raw exception strings.
2. A 390 px viewport is dominated by the expanded sidebar, fixed chat launcher,
   wide layouts, dense tables, and four-to-six-column sections.
3. The default Today Decision page renders maintenance controls and execution
   history before the market/risk decision context a trader needs first.
4. Loading, empty, stale, API-unavailable, fallback, all-sources-unavailable,
   success, and failure states use inconsistent wording and visual semantics.

The objective is not a cosmetic reskin. It is a safer, decision-first,
mobile-usable interface with a small shared component and state vocabulary.

## Evidence Baseline

- `app.py` registers 27 routes across five sidebar groups and starts with
  `layout="wide"` plus an expanded sidebar.
- `ui/today_decision.py::render()` currently calls candidate controls, data
  health, trade state, and candidate result sections before market/risk context.
- `_shared.chip()` inserts the supplied label into HTML without escaping it.
- Approximately 32 `unsafe_allow_html=True` call sites need classification as
  static CSS, escaped dynamic HTML, or removable HTML.
- `.streamlit/config.toml` uses red as both the main interaction accent and a
  bearish/error/AVOID semantic color.
- API/fallback states are implemented independently on schedules, AI updates,
  and institutional pages.
- Existing `scripts/ui_snapshot.py` supports Playwright screenshots but not a
  deterministic viewport/state matrix.

These are code/static observations plus the previously supplied 390 px mobile
screenshot. They are not a substitute for a measured usability study; UX-0
creates that baseline before redesign claims are made.

## Preliminary Heuristic Evaluation

| # | Heuristic | Score | Main issue | Priority |
| --- | --- | ---: | --- | --- |
| 1 | Visibility of system status | 2/5 | Source, fallback, stale, and terminal states differ by page | High |
| 2 | Match the user's mental model | 2/5 | Technical terms and maintenance controls precede trading decisions | High |
| 3 | User control and freedom | 3/5 | Manual paths and page jumps exist, but mobile escape/wayfinding is weak | Medium |
| 4 | Consistency and standards | 2/5 | Page-local cards, chips, errors, and status patterns drift | High |
| 5 | Error prevention | 2/5 | Unsafe dynamic HTML and raw diagnostic presentation remain possible | High |
| 6 | Recognition over recall | 2/5 | 27 routes and truncated mobile navigation increase recall burden | High |
| 7 | Flexibility and efficiency | 3/5 | Expert shortcuts exist, but density is not adaptive | Medium |
| 8 | Minimalist design | 2/5 | First viewport is control-heavy and many sections have equal visual weight | High |
| 9 | Error recovery | 2/5 | Recovery exists technically but copy and next actions are inconsistent | High |
| 10 | Contextual help | 3/5 | Captions exist, but backend vocabulary leaks into user-facing copy | Medium |

**Preliminary overall score:** 2.3/5.<br>
**Critical areas:** status visibility, user language, consistency, error safety,
mobile wayfinding, information hierarchy, and recovery.<br>
**Quick wins:** escape shared chip labels, replace raw exceptions with stable
messages, unify state banners, move controls below the decision context, and
collapse the mobile sidebar by default.

## Design Principles

1. **Decision before maintenance:** the first viewport answers what needs
   attention now; refresh controls and technical detail are progressive.
2. **State is part of the product:** loading, empty, stale, degraded, fallback,
   and unavailable states receive explicit and consistent treatment.
3. **One semantic color, one meaning:** interaction, information, caution,
   success, bearish/avoid, and error tokens are distinct; icons and text always
   accompany color.
4. **Preserve expert speed:** same-session jumps and dense tables remain where
   they materially help, while narrow screens receive a usable list/card form.
5. **Fail soft without hiding degradation:** safe UI copy never turns expected
   missing/partial data into a crash and never presents fallback as primary data.
6. **No raw diagnostics in the UI:** a technical-details area may show only a
   sanitized source label, timestamp, stable reason code, and stable event code.
   Raw exceptions, absolute paths, response bodies, internal URLs, ports,
   profiles, credentials, and secret-like values remain prohibited in every
   expander, chat surface, session state, and persisted user-visible record.

## Direction Options

### Option A — Calm Decision Cockpit (Recommended)

- **Concept:** restrained dark trading workspace with one decision anchor,
  progressive detail, and stable status language.
- **Mood:** calm, precise, evidence-led, high-confidence, compact.
- **Benefits:** best fit for repeated daily use; lowers first-viewport load;
  scales from desktop to mobile without removing expert detail.
- **Trade-off:** requires shared components and deliberate page migration before
  visual consistency is complete.
- **Expected outcome:** critical-flow task success at least 95% across the defined
  human task attempts, SEQ at least 5.5/7, and lower time-to-first-decision in
  the same measured tasks.

### Option B — Dense Professional Terminal

- **Concept:** maximum information density, persistent panels, compact typography,
  and keyboard-oriented expert workflows.
- **Benefits:** fastest scanning for expert desktop users and strong comparison
  density.
- **Trade-off:** highest mobile and accessibility risk; preserves much of the
  current cognitive load; hard to use well in Streamlit's responsive shell.
- **Expected outcome:** desktop time-on-task can improve, but mobile success and
  first-use comprehension are likely worse than Option A.

### Option C — Guided Trading Workflow

- **Concept:** sequential steps from market gate to candidates, position check,
  trade setup, and review.
- **Benefits:** strongest onboarding and lowest ambiguity for occasional users.
- **Trade-off:** slows experienced users, can hide cross-signal context, and risks
  turning a dashboard into a rigid wizard.
- **Expected outcome:** first-use success improves, while repeat expert task time
  may regress unless a separate expert mode is maintained.

### Recommendation

Adopt Option A. Retain selected Option B density patterns only inside tables and
advanced expanders; do not introduce a second "expert mode" during the first
redesign. Option C is a future onboarding pattern, not the primary app shell.

This recommendation preserves the current dark Quant Radar identity. Changing
the logo, brand identity, display typeface, or overall brand palette is outside
scope. Moving the primary interaction accent away from danger red is a semantic
token correction and requires maintainer approval before UX-1B implementation.

## Target Experience and Composition

Quant Radar is an operational product dashboard, so a marketing-style hero is
not appropriate. The first viewport nevertheless follows a single-focus rule:
one decision anchor, one concise explanation, and one primary next action rather
than a grid of equally weighted controls.

For Today Decision, the intended order is:

1. existing market/risk evidence and data readiness;
2. the first candidate in the existing provider/order contract, or its existing
   empty state;
3. current position/trade-state follow-up;
4. trust, freshness, and source details;
5. collapsed data refresh, run history, and technical controls.

No new trading verdict may be inferred by design code. If a compact label such as
"可評估 / 謹慎 / 暫緩" is later desired, its business rule needs a separately
reviewed pure mapping and tests. Until then, the anchor presents existing values
and their limitations without synthesizing advice.

## Measurable Success Criteria

| Metric | Target |
| --- | --- |
| Critical-flow task success | at least 95% across the UX-0 human-study task attempts; scripted E2E is not counted |
| SUS | at least 80 after the first full core-page migration |
| SEQ | at least 5.5/7 per critical task |
| Common-flow error rate | below 5% in moderated or scripted tests |
| Desktop first decision | market/risk context visible in the initial 1440×900 viewport |
| Mobile shell | no sidebar obstruction at 390×844 and no page-level horizontal overflow except explicitly scoped data tables |
| Touch targets | 44×44 CSS px target for primary controls; never below WCAG 2.2's 24×24 minimum |
| Accessibility | pass the explicit WCAG 2.2 AA criteria matrix in this plan; do not claim full conformance without a dedicated audit |
| State recovery | every target page composes source, content, freshness, and operation state where applicable |
| Diagnostic safety | no user-visible or persisted raw exception, absolute path, response body, credential, or internal URL |
| Compatibility | preserve 27 page definitions, `/` as the default route, 26 explicit bookmark paths, the `today-decision` registry key, registered page jumps, and existing session handoff keys |
| Data behavior | no extra API/provider call caused solely by layout reordering; existing fail-soft behavior remains |

## Shared UX Vocabulary

### Semantic Tokens

Use a `Reference -> Semantic -> Component` model rather than page-local colors.
The initial semantic categories are:

- `surface.canvas`, `surface.panel`, `surface.elevated`;
- `text.primary`, `text.secondary`, `text.inverse`;
- `border.default`, `border.focus`;
- `interactive.primary`, `interactive.hover`, `interactive.disabled`;
- `feedback.info`, `feedback.success`, `feedback.warning`, `feedback.error`;
- `signal.bullish`, `signal.neutral`, `signal.bearish`, `signal.avoid`.

Components consume semantic tokens only. Red is reserved for error, bearish, or
AVOID semantics and is not the default link/tab/button accent.

### Shared Components

The first component layer should remain small:

- `PageHeader`: title, user-language subtitle, freshness/source affordance;
- `StateBanner`: typed status, concise explanation, next action, optional details;
- `MetricGrid`: intrinsic one-to-four-column layout with stable metric semantics;
- `ActionBar`: primary/secondary action hierarchy with mobile stacking;
- `EntityCard` or narrow-screen row: candidate/holding summary and same-session
  actions;
- `SourceMeta`: freshness, data source, fallback, and technical-detail disclosure.

`StateBanner` is not a flat enum. It composes three independent data dimensions
plus an orthogonal operation state:

| Dimension | Values | Rule |
| --- | --- | --- |
| Source | `authoritative`, `fallback`, `unavailable` | says where trusted data came from, or that no trusted source is usable |
| Content | `populated`, `empty`, `partial`, `unknown` | describes the returned content without changing source status |
| Freshness | `fresh`, `stale`, `unknown` | uses only an existing payload timestamp or existing domain freshness rule |
| Operation | `idle`, `loading`, `success`, `failure` | describes a user-triggered action independently of data state |

Required mappings:

- API `available=false` -> source `unavailable`; never read local fallback.
- transport/protocol failure plus valid local data -> source `fallback`.
- client failure plus failed local read -> source `unavailable` with an
  all-sources-unavailable reason code.
- a fallback can also be `empty` or `stale`; those facts must not replace its
  visible fallback label.
- authoritative data may be `partial`, or may have `freshness=unknown`, without
  being mislabeled unavailable.
- `degraded` is a presentation summary for a fallback, partial, stale, or
  unknown-freshness composition; it is not a fourth source type.
- UI code MUST NOT invent a freshness threshold. `stale` may be used only when
  an existing payload or already-reviewed domain rule establishes it.

The banner chooses severity, explanation, next action, and optional sanitized
details from the full composition. Status must always use text and an icon in
addition to color.

### Responsive Rules

- Mobile first: one content column; primary actions stack vertically and remain
  reachable without horizontal scrolling.
- Tablet: two-column grids only when each column remains legible.
- Desktop: up to four metric columns; five/six-column sections require an
  explicit comparison rationale.
- Prefer intrinsic sizing (`auto-fit`, `minmax`, container-aware behavior) where
  Streamlit/CSS permits it.
- Primary touch targets are at least 44×44 px with at least 8 px separation.
- AI Chat must not obscure focused or primary content; on mobile it becomes a
  full-width bottom sheet or another tested non-overlapping pattern.
- Wide tables may scroll inside their own bounded region; the overall page may
  not overflow horizontally.

### Accessibility Criteria Matrix

This plan targets the following WCAG 2.2 AA-relevant criteria; passing it does
not authorize a blanket full-conformance claim:

| Area | Criteria / executable expectation |
| --- | --- |
| Structure and labels | 1.3.1 and 3.3.2: headings, relationships, inputs, and controls have meaningful programmatic labels |
| Color and contrast | 1.4.1, 1.4.3, 1.4.11: status is not color-only; normal text 4.5:1; large text/UI/focus boundaries 3:1 |
| Reflow and zoom | 1.4.10: no two-dimensional page scroll at 320 CSS px equivalent; test 320 px layout and 400% zoom/reflow where applicable |
| Keyboard and focus | 2.1.1, 2.4.3, 2.4.7, 2.4.11: full keyboard path, logical order, visible and unobscured focus |
| Pointer targets | 2.5.7, 2.5.8: no drag-only critical action; at least 24×24 px minimum and 44×44 px target for primary controls |
| Consistency and errors | 3.2.4, 3.3.1, 3.3.3: consistent controls, text-identified errors, and recovery suggestion |
| Names and status | 4.1.2, 4.1.3: accessible name/role/state and announced dynamic status where the framework permits |

AI Chat specifically requires: focus moves into the panel on open; Escape and a
named close control dismiss it; modal presentation contains focus; closing
returns focus to the launcher; launcher and panel expose accessible name, role,
and expanded/open state; no overlay obscures the focused element. Screen-reader
spot checks are supporting evidence only. A dedicated conformance audit is
required before claiming the full app conforms to WCAG 2.2 AA.

## Phased Implementation

### UX-0 — Baseline and Guardrails

**Goal:** establish deterministic evidence before changing production UI.

Deliverables:

- extend `scripts/ui_snapshot.py` or add a focused runner for 1440×900,
  768×1024, and 390×844 viewport matrices;
- have that runner start a Streamlit process it owns on a collision-safe port,
  inject a test entrypoint plus temporary artifact roots/provider stubs on the
  server side, wait for readiness, and stop only its own process;
- add `scripts/test_ui_ux_contract.py` for all 27 page definitions, the `/`
  default route, 26 explicit bookmark paths, `PAGE_REGISTRY`, known
  session handoffs, unsafe-HTML inventory, raw-exception inventory, and critical
  layout sources;
- make the diagnostic inventory detect direct `str(exception)`, f-string or
  concatenated exception values, payload `error` fields, absolute paths,
  profile/port/internal-URL values, and secret-like sentinels; a simple source
  search for one spelling is not sufficient;
- cover Today Decision, Trade State, Stock Checkup, Options Cockpit,
  Institutions, Schedules, and AI Updates with fixed AppTest/provider fixtures;
- record provider/API call counts for render-order regression checks;
- capture Chromium and WebKit where supported, plus a manual macOS Safari smoke
  for the default/mobile shell because the reported local failure occurred in
  Safari; WebKit is an approximation, not proof of Safari parity;
- write a baseline manifest; store generated screenshots as review artifacts,
  not unstable source-of-truth pixel hashes.

Likely files:

- `scripts/ui_snapshot.py`
- create a fixture-only Streamlit test entrypoint or equivalent server-side
  injection harness; it must not be used by production startup
- create `scripts/test_ui_ux_contract.py`
- `scripts/test_dashboard_navigation.py`
- `Makefile`
- create `docs/ui-ux/quant-radar-ui-v2-baseline.md`

Acceptance:

- all 27 page definitions, `/`, the 26 explicit bookmark paths, the
  `today-decision` registry key, and every same-session route are enumerated;
- screenshots reproduce at all three viewports with external providers stubbed;
- browser interception is not treated as a provider stub because Streamlit
  provider/API calls occur server-side;
- dynamic time/market values are masked or fixture-controlled;
- no pixel-perfect comparison is treated as a pass without human review;
- runtime dependencies remain unchanged unless a separate test-dependency review
  explicitly pins Playwright.

### UX-0 Human Usability Protocol

Scripted tests establish behavior, not SUS or SEQ. Human measurement uses:

- **Owner:** product maintainer or assigned UX researcher.
- **Participants:** target 8 people with at least weekly use of an options,
  trading, or research dashboard. If fewer than 5 participate, results are
  qualitative and cannot close the SUS/SEQ/task-success targets.
- **Design:** the same participants complete baseline and redesigned tasks when
  possible; order is counterbalanced to reduce learning bias.
- **Tasks:** (1) identify existing market/risk readiness, (2) open the first
  candidate from the existing order in the options workflow, (3) identify a
  fallback/unavailable state and its next action, (4) find a schedule result,
  and (5) open and close AI Chat on mobile without losing place.
- **Success:** correct existing entity/state reached without moderator help,
  without changing a provider/decision value, and within the per-task limit
  recorded in the baseline manifest. The same limits apply before and after.
- **Measures:** binary success and time-on-task per attempt, one 1-7 SEQ response
  immediately after each task, and the standard 10-question SUS after the full
  session. Report participant-level values plus aggregate median; do not count
  Playwright attempts as people.
- **Timing:** baseline during UX-0, decision-first retest after UX-3, and final
  core-page retest after the relevant UX-4 wave.

With 8 participants × 5 tasks, at least 38 of 40 attempts must succeed to meet
the 95% critical-flow target. SUS must be at least 80 and median task SEQ at least
5.5/7. Recruitment shortfall is reported, not converted into synthetic data.

### UX-1A — Safety and Shared State Foundations

**Goal:** close unsafe presentation paths and establish shared state primitives
without a global palette or macro layout change.

Deliverables:

- escape every dynamic chip label with `html.escape(..., quote=True)` and accept
  colors only from an allowlisted semantic token map;
- classify every `unsafe_allow_html=True` call as static, safely escaped, or
  removable; add malicious HTML sentinels (`<script>`, `<img onerror>`, quotes,
  ampersands) to tests;
- remove user-visible and persisted raw diagnostics regardless of whether they
  arrive through `str(exception)`, f-strings, payload fields, paths, URLs,
  profiles, or ports; log only a stable event code plus exception class where
  diagnostics are required;
- introduce the smallest viable `ui/_design.py` and `ui/_components.py` layer;
- implement shared state banners and source metadata first on Today Decision,
  AI Chat, AI Updates, Schedules, and Institution Portfolio;
- define status, focus, disabled, and signal tokens without changing the global
  Streamlit `primaryColor` in this batch.

Initial likely files:

- `ui/_shared.py`
- create `ui/_design.py`, `ui/_components.py`
- `ui/today_decision.py`, `ui/ai_chat.py`
- `ui/sys_ai_updates.py`, `ui/sys_schedules.py`, `ui/institution_portfolio.py`
- focused UI/security tests and `Makefile`

Acceptance:

- malicious labels render only as text;
- no target page or chat record contains raw diagnostic details;
- source, content, freshness, and operation dimensions compose without hiding an
  authoritative-unavailable, fallback, partial, empty, stale, or unknown state;
- expected missing, half-written, malformed, or unreadable artifacts remain safe
  UI states and do not crash;
- the explicit accessibility criteria matrix passes for every target component
  changed in UX-1A;
- no API, provider, URL, session key, or decision logic changes.

### UX-1B — Global Semantic Theme

**Goal:** correct the global interaction-versus-danger color semantics only after
UX-1A safety/state primitives and a 27-page baseline exist.

Deliverables:

- apply the approved semantic interaction accent in `.streamlit/config.toml` and
  app-level CSS/tokens;
- keep bearish, AVOID, and error red distinct from primary interaction state;
- verify default, hover, active, focus, disabled, success, warning, and error
  states across all 27 pages;
- record an atomic old-theme rollback rather than treating this as a page-local
  change.

Likely files:

- `.streamlit/config.toml`, `app.py`, `ui/_design.py`
- only the page files proven by the full snapshot/contrast audit to require
  compatibility corrections
- focused theme/contrast tests and baseline manifest

Acceptance:

- all 27 page definitions pass desktop/tablet/mobile visual review;
- the explicit contrast criteria matrix passes for every global semantic state;
- no layout, provider, decision, URL, or session contract changes;
- reverting this atomic batch restores the prior global theme without reverting
  UX-1A safety fixes.

### UX-2 — App Shell, Navigation, and Mobile

**Goal:** make the shell usable at narrow widths without removing expert routes.

Deliverables:

- prototype sidebar `auto`/collapsed behavior and verify it on real Streamlit;
- preserve all 27 page definitions, `/` default routing, 26 explicit bookmark
  paths, and the `today-decision` registry key while emphasizing the core
  workflow: Today Decision, Trade State, Screener, Stock Checkup, and Options
  Cockpit;
- expose lower-frequency tools through existing groups, hub shortcuts, or a
  clearly labeled "more tools" route without hiding desktop primary navigation;
- validate `st.switch_page`, `PAGE_REGISTRY`, bookmarks, and session handoffs
  before changing group presentation;
- make AI Chat non-overlapping on mobile and implement the exact focus/open/
  Escape/close/return behavior from the accessibility matrix;
- migrate critical metric grids, action toolbars, and narrow-screen candidate
  rows to responsive patterns.

Likely files are frozen only after the UX-0 prototype. At minimum: `app.py`,
`ui/ai_chat.py`, shared design/components, `ui/us_screener.py`, core page action
areas, navigation/AppTest/E2E tests, and user guide.

Acceptance:

- 390×844 sidebar does not cover main content;
- keyboard users can reach and identify navigation/chat controls with visible
  focus;
- chat launcher/panel does not cover the final content row or primary action;
- `/`, all 26 explicit bookmarks, the registry-only default-page key, page
  jumps, and handoff keys pass;
- no page-level horizontal overflow except documented table regions.

### UX-3 — Today Decision, Decision First

**Goal:** reorder the default page around the trader's decision sequence.

Deliverables:

- move existing market/risk evidence to the first viewport;
- surface the first candidate from the existing provider/order contract and the
  existing position/trade-state follow-up next;
- show trust, freshness, fallback, and evidence limitations consistently;
- move `_candidate_controls` and operational history into a collapsed
  "資料與刷新" area while preserving every control;
- place only sanitized source label, timestamp, reason code, and event code in an
  optional technical-details disclosure; raw diagnostics remain prohibited;
- stack actions vertically on narrow screens.

Primary likely files:

- `ui/today_decision.py`
- `ui/_candidate_controls.py`
- shared design/components
- Today Decision focused/AppTest/visual tests
- possibly `ui/trade_state.py` only when a shared presentation is required

Acceptance:

- market/risk context and the exact first candidate identity from the existing
  order appear in the first desktop and mobile viewport;
- every existing refresh, rerun, status, log, and history capability still works;
- provider/API call counts match the UX-0 baseline;
- candidate IDs/tickers and their order match the UX-0 baseline exactly;
- no trading rule, risk calculation, ordering, or data source changes;
- empty, stale, fallback, and unavailable first-viewport states are explicit.

### UX-4 — Progressive Cross-Page Migration

Migrate in usage/risk order, one independently reviewed batch at a time:

1. Trade State, Stock Checkup, Options Cockpit;
2. Institutions, Schedules, AI Updates;
3. market and research pages, explicitly including `ui/theme_flow.py` and
   `ui/x_sentiment.py` raw-diagnostic paths;
4. maintenance and low-frequency pages, explicitly including
   `ui/analytics_db.py` and `ui/influencers.py` raw-diagnostic paths.

Each batch migrates only the shared page header, state banner, metric grid,
action bar, source metadata, safe chips, heading hierarchy, table captions, and
mobile fallback needed by those pages. Each wave also removes raw diagnostics
from every page in that wave, including f-string/payload/path/profile/port forms,
and replaces them with safe copy plus stable event codes. It must not refactor
business logic merely to fit the component layer.

Completion criteria:

- no remaining unescaped dynamic HTML;
- no remaining user-visible or persisted raw exception, path, internal URL,
  response body, profile, port, credential, or secret-like diagnostic;
- all page-local state messages map to the shared state vocabulary;
- every migrated page passes three-viewport, keyboard, focus, contrast, empty,
  error, fallback, and stale-state review;
- documentation no longer exposes backend terms as normal user instructions.

## Verification Strategy

Every phase runs:

1. focused unit/AppTest suites for changed components and page states;
2. `scripts/test_dashboard_navigation.py` and all API-consumer regression suites;
3. full `make test`, compilation, Python 3.10 AST where applicable, `pip check`,
   and `git diff --check`;
4. an owned Streamlit fixture process plus Playwright Chromium/WebKit at
   390×844, 768×1024, and 1440×900 for sidebar, overflow, chat collision, focus
   order, and critical actions; add a manual macOS Safari smoke for shell changes;
5. fixed-fixture screenshots with human review of every intentional visual diff;
6. keyboard-only walkthrough, 320 CSS px equivalent/400% zoom reflow, focus
   visibility, the explicit criteria matrix, and screen-reader spot checks;
7. malicious HTML and diagnostic sentinels covering exception messages,
   f-strings, payload errors, paths, internal URLs, ports, profiles, and secrets;
8. pre/post provider/API call-count and candidate identity/order comparison for
   reordered pages.

Streamlit DOM selectors are implementation details. E2E tests should prefer
stable accessible names, widget `key` values, and supported `.st-key-*` hooks.
Record the tested Streamlit version and avoid inventing `data-testid` attributes
for native widgets that the framework does not expose.

## Rollout and Rollback

- UX-0 is evidence-only.
- UX-1A security/state fixes ship in small page/component batches and can roll
  back by reverting the relevant UI-only change. UX-1B is a separate atomic
  global-theme batch with a 27-page visual/contrast gate.
- UX-2 and UX-3 require a prototype and maintainer direction approval before
  production replacement. If a temporary `QUANT_RADAR_UI_V2` flag is chosen,
  it must gate presentation only, share the same data/provider code, and have a
  dated removal criterion; parallel business logic is forbidden.
- Existing `/`/bookmark/registry routes and session keys stay stable, so rollback
  requires no data migration.
- Never stop or restart an unowned local Streamlit/API process during visual
  verification.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Global CSS changes break 27 pages | semantic tokens, component-scoped selectors, phased screenshots |
| Navigation redesign breaks bookmarks/handoffs | exact `/`, 26-bookmark, registry-key, and handoff tests before and after prototype |
| Layout reorder changes data identity or calls | fixed fixtures plus provider-call and candidate ID/order parity oracles |
| HTML escaping breaks intended markup | separate text from trusted templates; test each shared consumer |
| Visual snapshots become flaky | fixed data, masked dynamic fields, structural assertions, human diff approval |
| Mobile fixes degrade desktop density | three-viewport acceptance on every batch |
| Feature flag creates permanent dual UI | presentation-only branch and explicit removal date |
| Scope expands into business logic | per-batch affected-file plan and separation contract |
| Accessibility becomes instance-level patching | fix tokens/components first, then migrate pages |

## Traceability Matrix

| Requirement | Design target | Primary verification |
| --- | --- | --- |
| `UX-REQ-001` diagnostic and HTML safety | safe chips, stable errors, sanitized technical details | malicious labels and exception/payload/path/URL/profile/port/secret sentinels |
| `UX-REQ-002` consistent states | composable `StateBanner`, `SourceMeta` | source × content × freshness plus operation-state AppTests |
| `UX-REQ-003` mobile usability | responsive shell/grids/actions/chat | three-viewport Playwright and overflow checks |
| `UX-REQ-004` decision-first homepage | Today Decision order | structural AppTest, screenshots, call-count and candidate identity/order parity |
| `UX-REQ-005` navigation compatibility | default/bookmark registry and handoff contracts | 27 pages, `/`, 26 bookmarks, registry key, and session jumps |
| `UX-REQ-006` accessibility | semantic tokens and shared components | explicit criteria matrix, keyboard, focus, 320 px/reflow, target-size checks |
| `UX-REQ-007` data behavior preservation | separation contract | API consumer/full regressions and provider call parity |
| `UX-REQ-008` controlled rollout | per-batch plan/rollback | scope audit and rollback rehearsal |

## Pre-Implementation Gates

This macro plan is not itself authorization to change all pages.

Before UX-1A:

- approve Option A;
- complete UX-0 and freeze the exact UX-1A affected-file list;
- review the unsafe HTML and raw diagnostic inventory;
- decide whether Playwright is an optional local tool or a pinned test-only
  dependency.

Before UX-1B:

- approve the semantic interaction-color correction;
- complete UX-1A and the 27-page three-viewport baseline;
- freeze the global theme affected-file list and atomic rollback;
- pass the explicit contrast criteria matrix across all global states.

Before UX-2/UX-3:

- approve a reviewable shell/Today Decision prototype at all three viewports;
- complete an independent Value/Agency/Identity/Resilience/Echo quality review;
- confirm the rollout choice: atomic UI-only batch or temporary presentation
  flag.

The requested Warden pre-check capability is not available in this environment.
Therefore no macro implementation should be delegated on the basis of this v0.3
document alone; independent review plus maintainer approval is the explicit
substitute gate. This does not block unrelated API phases.

## Execution Status — 2026-07-16

- Maintainer approved Option A, **Calm Decision Cockpit**, as the design direction.
- UX-0 discovery/baseline is complete and its JSON/Markdown evidence remains an
  immutable historical record.
- UX-1A is complete under the accepted executable plan in
  `2026-07-16-quant-radar-ui-ux-ux1a.md`. Shared tokens, safe chips, composable
  state components, target fail-soft boundaries, chat/candidate diagnostic
  projections, and the safe reflection summary passed focused/full/static,
  protected/runtime hash, Chromium 20/20 + 21/21, exact provider parity, visual,
  and two independent implementation-review gates.
- UX-1B global theme correction, UX-2 shell/navigation redesign, UX-3 Today
  Decision redesign, and UX-4 migration have not started. UX-1A does not claim
  the visible shell or full UI/UX redesign is complete.
- The UX-0 narrow-screen sidebar/shell limitation remains known and is not
  silently counted as fixed by component-level UX-1A evidence. The fixed
  floating AI control's lower-right overlap is also deferred to UX-2.

## Quality Check Results

- Scope and non-goals: present.
- Measurable NFRs and acceptance criteria: present.
- Requirement-to-design-to-test traceability: present.
- Responsive, empty/error/loading/fallback, accessibility, security, rollout,
  and rollback coverage: present.
- Open decisions are isolated to pre-implementation gates rather than hidden in
  execution tasks.
- Independent closure review: PASS; the prior two high and six medium findings
  are resolved with no remaining severity finding.

## Plan Review Record

- **Review 1 — independent UX/security/accessibility:** CONDITIONAL; no blocker,
  two high and six medium findings. v0.2 resolved diagnostic sanitization,
  composable state semantics, human-study measurement, accessibility criteria,
  exact routing, deterministic browser fixtures, candidate parity, and atomic
  global-theme rollout.
- **Review 2 — closure review:** PASS with no remaining severity finding.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-07-15 | Initial separate UI/UX redesign plan based on static, mobile, state, security, and information-hierarchy review |
| v0.2 | 2026-07-15 | Closed first-review security/state-model issues; added human-measurement protocol, explicit accessibility criteria, owned fixtures/Safari coverage, exact default/bookmark routing, candidate identity parity, and separate global-theme rollout |
| v0.3 | 2026-07-15 | Recorded independent closure PASS; plan remains separately gated on maintainer direction approval before UI implementation |
| v0.4 | 2026-07-16 | Recorded UX-0 and UX-1A completion, exact browser/provider evidence, and the sidebar/floating-AI limitations; later phases remain separately gated |
