# Quant Radar UI/UX v2 — UX-0 Baseline

## Status and scope

The UX-0 technical baseline was captured on 2026-07-16 with deterministic,
server-side fixtures. It inventories the current application and records how
the real Streamlit render functions behave before redesign work begins.

UX-0 makes no production UI change. `app.py`, `.streamlit/`, `ui/`, `api/`,
providers, artifacts, and `requirements.txt` remain outside this phase. The
screenshots are review evidence, not pixel-golden tests.

The versioned machine-readable record is
`docs/ui-ux/quant-radar-ui-v2-baseline.json`. Its `contract` section is compared
exactly after removing review-only source line numbers. Its `evidence` section
is schema-checked without pinning timestamps, local browser installation, tool
versions, or screenshot hashes.

## Contract inventory

| Item | Reviewed baseline |
| --- | ---: |
| Streamlit pages | 27 |
| Navigation groups | 5 |
| Default routes | 1 (`/`, registry key `today-decision`) |
| Bookmark routes | 26 |
| Same-session route targets | 13 across 32 call sites |
| Handoff contracts | 5 contracts / 7 state keys |
| `unsafe_allow_html=True` semantic sites | 31 |
| Raw-diagnostic candidates | 177 |

The unsafe-HTML and diagnostic results are candidate inventories, not proof of
an exploitable vulnerability and not a claim that every candidate is unsafe.
Their stable semantic site IDs make additions, removals, and expression changes
reviewable without failing on source line movement alone.

## Automated browser evidence

| Check | Result |
| --- | --- |
| Fixture AppTests | 8 fixture groups passed, including seven real page renderers and both Institutions views |
| Chromium matrix | 21/21 passed (7 pages × 3 viewports) |
| WebKit | `unsupported` in this local Playwright installation; it was not silently counted as passed |
| Page/Streamlit exceptions | 0 |
| Browser or server external-network attempts | 0 |
| Failed browser requests | 0 |
| Page-level horizontal-overflow measurements | 0/21 |
| Sidebar/main overlap measurements | 7/21, exactly the seven mobile captures |
| Screenshots reviewed by Codex image inspection | 21/21 |
| Real macOS Safari | `NOT_CHECKED` |
| Participant SUS/SEQ/task study | `NOT_RUN` |

The tested viewports were desktop 1440×900, tablet 768×1024, and mobile
390×844. Chromium was mandatory. WebKit was optional when locally installed;
even a WebKit pass would not establish real Safari parity.

### Recorded loopback 404 probes

The 18 non-root captures each emitted two console errors. Response-level
evidence identifies them as Streamlit route-relative `fetch` probes:

- `/<page>/_stcore/health` → 404;
- `/<page>/_stcore/host-config` → 404.

There were 36 such responses in total. They did not correspond to a missing
page asset, API/provider call, page exception, readiness failure, or blocked
external request; every affected page still completed its fixture calls and
rendered. They remain recorded as baseline noise and a future shell/deep-link
quality item rather than being hidden or treated as proof of a clean console.

## Codex image-review findings

1. **Mobile shell is obstructed.** In all seven 390×844 captures, the expanded
   300px sidebar overlays the main view and leaves only about 90px visible. The
   page may technically render, but the captured initial state is not usable.
2. **Tablet content is overly compressed.** The persistent sidebar leaves a
   468px main column. Trade State, Stock Checkup, Options Cockpit, Institutions,
   and Schedules visibly wrap or clip controls, labels, metric cards, tabs, and
   table content. No document-level overflow was measured because much of the
   damage occurs inside components.
3. **Navigation discoverability is weak.** Ten destinations are visible before
   Streamlit's generic `View 17 more` disclosure; most of the 27-page product is
   hidden behind it.
4. **The floating AI control competes with content.** It occupies the lower
   right of every viewport and overlaps or crowds dense cards/charts in several
   captures.
5. **Desktop structure renders but lacks a shared hierarchy.** All seven
   desktop captures avoid measured sidebar overlap and page-level horizontal
   overflow, while page density, emoji headings, controls, cards, tables, and
   empty space vary substantially.
6. **Fixture determinism held.** Fixed dates, tickers, labels, and source badges
   were consistent; no unexpected live or dynamic content was observed.

These are Codex image-inspection observations, not participant evidence or
fixes. A successful render is not a claim
that the layout is usable or accessible.

## Pending manual evidence

### Real Safari smoke (`NOT_CHECKED`)

The maintainer or assigned tester must use real macOS Safari, not Playwright
WebKit, and record Safari/macOS versions plus screenshots. With an owned local
dashboard or the normal local shell, test 1440×900 and responsive 390×844 for
`/`, `/trade-state`, `/stock-checkup`, `/options-cockpit`, `/institutions`,
`/schedules`, and `/ai-updates`. For every route:

1. open the bookmark directly and reload once;
2. confirm the expected heading and navigation selection;
3. open and close the sidebar at mobile width;
4. check clipping, horizontal scrolling, tables/charts, focus visibility, and
   the floating AI control;
5. record any Safari console/network error without exposing local secrets or
   artifact contents.

Until that evidence exists, Safari remains `NOT_CHECKED`.

### Human usability study (`NOT_RUN`)

Recruit eight people who use a trading, options, or research dashboard at least
weekly; fewer than five yields qualitative evidence only. Counterbalance the
current and redesigned order where possible. Each participant performs five
tasks: identify market/risk readiness, open the first candidate in the options
workflow, identify an unavailable state and next action, find a schedule
result, and open/close AI Chat on mobile without losing place.

Record task success, time-on-task, one 1–7 SEQ response after each task, and the
standard ten-question SUS after all tasks. Playwright runs are not participants.
The targets are at least 38/40 successful attempts, median SEQ ≥ 5.5/7, and SUS
≥ 80. No synthetic scores are present in this baseline.

## UX-1A entry gates

Before UX-1A changes production code:

- explicitly approve Option A, **Calm Decision Cockpit**;
- review the 31 unsafe-HTML sites and 177 diagnostic candidates;
- freeze an exact UX-1A affected-file list and rollback boundary;
- retain Playwright as optional local tooling unless a separate dependency
  review approves a pinned test-only dependency;
- preserve all routes, handoffs, provider call behavior, and fail-soft reads.

The UX-0 technical repository baseline is complete. Safari and participant
evidence remain pending and must not be represented as completed UX research.
