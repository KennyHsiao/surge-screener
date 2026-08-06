# Quant Radar UI/UX UX-1B — Global Semantic Theme

## Document Info

| Field | Value |
| --- | --- |
| Type | Executable, test-first implementation plan |
| Version | v0.3-accepted |
| Status | Accepted; Task 1 tooling is authorized after Task 0, production theme edits remain gated on pre-theme 81/81 |
| Date | 2026-07-16 |
| Direction | Option A — Calm Decision Cockpit |
| Parent plan | `docs/superpowers/plans/2026-07-15-quant-radar-ui-ux-redesign.md` v0.4 |
| Predecessor | `docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1a.md` |
| Audience | Product owner, Streamlit implementer, accessibility reviewer, maintainer |

## Outcome

UX-1B separates ordinary interaction from danger, bearish, and AVOID semantics
without changing layout, routes, data, or decisions. It also closes a planning
gap in the parent roadmap: the existing UX-0 browser evidence covers seven
critical pages, not all 27 page definitions. Therefore this batch has two hard
gates:

1. build and pass a deterministic, isolated 27-page x 3-viewport pre-theme
   baseline; then
2. apply and verify the semantic theme as one maintenance-window production
   batch with compare-and-swap byte guards.

No production theme file may change before Gate 1 passes. The batch is complete
only when:

1. interactive controls no longer use the red danger/AVOID hue;
2. primary, hover, active, accent, selected-control, focus, and disabled roles
   have separate, fixed tokens and measured component contracts;
3. danger, bearish, AVOID, loss, error, success, warning, and information values
   remain semantically separate and are never inferred from color alone;
4. all 27 real page definitions pass Chromium desktop, tablet, and mobile
   capture before and after the change, for exactly 81 captures per manifest;
5. the dedicated state gallery passes computed-style and contrast oracles for
   every machine-observable state, while the privacy-protected `:visited`
   state passes an explicit static CSS contract;
6. routes, headings, render callables, provider counts, artifacts, decisions,
   session keys, layout geometry, and fail-soft behavior remain compatible;
7. the four-file runtime batch can be restored by validated staged replacement
   without reverting any UX-1A safety/state change or overwriting newer bytes.

## Entry Gate and Decisions

### Gate Result

| Gate | Evidence | Result |
| --- | --- | --- |
| Option A and next UI/UX phase authorized | Maintainer accepted the recommended separate UI/UX plan and repeatedly instructed continuation to the next phase | PASS |
| UX-1A complete | Focused 180/180, full suite, Chromium 20/20 focused plus 21/21 regression, protected/runtime hashes, and two closure reviews passed | PASS |
| Exact semantic palette selected | Local Streamlit 1.57 source and browser computed-style probes; palette frozen below | RESOLVED in this plan |
| Full 27-page pre-theme browser baseline | Existing UX-0 evidence is only 7 pages x 3 viewports | BLOCKED until Task 2 passes 81/81 |
| Deterministic fixtures for all 27 pages | Existing fixture and runner accept only seven routes; two extra routes already reproduce fixture-shape exceptions and at least one unpatched native network path | BLOCKED until Task 1 passes |
| Computed-style/state oracle | Existing runner records geometry only; `:visited` is intentionally a static contract | BLOCKED until Task 1 passes |
| Runtime-batch rollback boundary | Exact four-file set, byte compare-and-swap, owned backup, and rehearsal are specified below | RESOLVED in this plan; rehearsal pending |

The maintainer's continuation instruction delegates the reversible semantic
color choice within Option A. This plan selects the blue interaction family
below because it is conventional for action, clearly not danger red, and was
the strongest locally tested filled-button candidate. A later preference for a
different hue is a direction change and requires rerunning the complete contrast
and pre-theme gates; it must not be substituted during execution.

### Blocking-Issue Resolutions

#### Resolution R1B-01 — 27 routes are not 27 browser captures

The immutable UX-0 baseline remains historical evidence and is not expanded or
rewritten. UX-1B creates its own explicit `ux1b-full-pages` profile. The
canonical page set is **not** self-derived from whatever live `app.py` happens
to contain. It is the location-free projection
`(registry_key, route, nav_title, callable)` of
`docs/ui-ux/quant-radar-ui-v2-baseline.json::contract.pages`, with canonical
SHA-256 `539bf737382a0f35aca3daaec681aa520152e1381a442904c73d3c61d416f015`.

Before a catalog is constructed, Task 0, Task 1, and every runner start compare
the live `build_inventory()` page projection to those exact 27 frozen records.
A changed key, route, navigation title, callable, order, missing page, or extra
page fails this projection before any new digest can be accepted. The existing
exact UX-0 compatibility projection separately preserves default/group/icon and
the rest of navigation. Count and uniqueness checks remain defense-in-depth;
they are not the identity oracle.

Rendered readiness is a separate 27-record catalog. Each record declares an
actual stable role/selector plus exact text or a bounded regular expression; it
is never inferred from the navigation title. This explicitly covers pages such
as `schedules`, whose heading differs from its nav title, `us-screener`, whose
first content heading is a layer heading, and the two X pages, whose heading is
market-dependent. Every manifest records and compares all four identities:
requested route, final browser path, fixture-selected registry key, and real
render callable.

Every ready marker is scoped beneath
`[data-testid="stMainBlockContainer"]` and uses a heading role. Emoji-bearing
headings use bounded `contains` matching to avoid accessible-name variation;
the others use exact matching. A heading proves route entry only, so success
also requires Streamlit readiness, layout/Plotly stability, no exception, and
fixture quiescence.

| Registry key | Heading level | Text | Match |
| --- | ---: | --- | --- |
| `today-decision` | 2 | `今日決策` | exact |
| `trade-state` | 2 | `交易狀態` | exact |
| `us-screener` | 2 | `Layer 0 — 大盤環境` | exact |
| `options-flow` | 1 | `選擇權異常流` | contains |
| `stock-checkup` | 2 | `個股總覽` | contains |
| `options-cockpit` | 2 | `期權作戰台` | contains |
| `radar` | 2 | `雷達 / Radar` | contains |
| `ibkr-reconcile` | 2 | `IBKR 對帳` | contains |
| `sector-rotation` | 2 | `熱錢板塊輪動` | contains |
| `theme-flow` | 2 | `主題資金流` | contains |
| `us-cot` | 2 | `COT / ES 週報` | contains |
| `market-thesis` | 2 | `大盤行情研判` | contains |
| `us-x` | 2 | `X 社群情緒 — 美股` | contains |
| `retro-analysis` | 1 | `復盤分析` | contains |
| `analytics-db` | 2 | `資料健康 / Analytics DB` | exact |
| `knowledge-graph` | 1 | `知識網路` | exact |
| `us-options` | 2 | `完整期權鏈明細` | exact |
| `analyst-views` | 2 | `分析師評級` | contains |
| `institutions` | 2 | `機構面板` | contains |
| `industry-roles` | 2 | `產業鏈分類` | exact |
| `watchlist-categorize` | 2 | `自選股分類` | contains |
| `influencers` | 2 | `關注博主` | exact |
| `schedules` | 2 | `排程與執行結果` | contains |
| `ai-updates` | 2 | `AI Agent 重點更新` | contains |
| `crypto-universe` | 2 | `幣種清單 — 幣安 USDT 永續 (USDT.P)` | contains |
| `crypto-screener` | 2 | `幣圈篩選` | contains |
| `crypto-x` | 2 | `X 社群情緒 — 幣圈` | contains |

The profile captures exactly 27 pages at 1440x900, 768x1024, and 390x844 in
Chromium, producing 81 entries. The existing no-argument UX-0 seven-page profile
and UX-1A focused profile remain byte-compatible in behavior and keep their
existing manifest modes and output namespaces.

#### Resolution R1B-02 — fixture expansion is a prerequisite, not evidence by assertion

`scripts/ui_ux_fixtures.py` expands the route allowlist and provider seams only
after tests describe all 27 render contracts. It must:

- retain every real page render callable; replacing a page render is forbidden;
- rebind every runtime read/write root into the owned fixture directory;
- seed the smallest valid deterministic artifact or patch the highest-level
  provider boundary needed for the page's initial render;
- count every patched provider boundary by stable name;
- prevent subprocesses, browser launches, login flows, and background refreshes;
- make initial render independent of real repository artifacts and external
  services;
- fix the already reproduced `us-screener` ledger schema and
  `sector-rotation` sector schema inside fixtures, never in production pages;
- reject a route with no declared render identity and provider expectation.

Task 1 encodes the following minimum per-route contract as immutable test data.
Every row also contains the separate `ready_marker` record described in
R1B-01, owned fixture artifact paths/provenance, and an exact counter map. A
listed positive seam is expected exactly once for one initial render unless the
row explicitly says zero; `>= 1` is forbidden. A route with an undeclared
provider, path, counter, or artifact provenance fails closed.

| Registry key | Deterministic initial-render seam and owned path handling | Exact provider/mutator rule |
| --- | --- | --- |
| `today-decision` | Retain fixed daily summary, thesis, validation, candidate, trade-state, and flow seams; all report/candidate/chat roots owned | Existing named read seams get explicit exact counts; every action/refresh seam is zero |
| `trade-state` | Retain fixed `_load_rows`/`build_trade_state_rows` and reconciliation; roots owned | `trade_state.load.attempt=1`, fixed builder count declared exactly; action mutators zero |
| `us-screener` | Rebind `DATA_DIR`/`REPORTS_DIR`; make `load_ledger` return the complete performance schema including `fwd_30d_return` | `shared.ledger.execute=1`; quote/live/download mutators zero |
| `options-flow` | Fix `_load_options_flow`; fix `_live_chain` at the page boundary and prohibit production artifact fallback | Flow load exact once; initial no-ticker live chain exactly zero; network zero |
| `stock-checkup` | Retain fixed live factors, score, fundamentals, sector, flow, and quote seams | Each actually used named read seam has an exact count; unrelated institution seam zero |
| `options-cockpit` | Retain fixed `_live_provider` and money-flow artifact seams | Both existing named seams exact once; network zero |
| `radar` | Rebind `OVERSOLD_DIR`, seed/own all radar roots, and clear radar session state | Declared loaders exact; scan/refresh/write zero |
| `ibkr-reconcile` | Force availability false and reconcile/connect boundaries fail-closed | Availability exact; connect/reconcile/login mutators zero |
| `sector-rotation` | Complete fixed flow schema with `group`/`theme`; fix baskets; own report roots | Flow/basket reads exact; refresh/write zero |
| `theme-flow` | Seed a current fixed snapshot, force `snapshot_is_stale=False`, terminal status, fixed insider data, and patch high-level readers whose default paths are definition-bound | Snapshot/status/insider reads exact; `mutator.theme_flow.launch_background.attempt=0` and all refresh/write counters zero |
| `us-cot` | Rebind `_COT_DIR`, own artifacts, and clear `cot_claude_auth_login` | Declared load exact; auth/login/browser/write zero |
| `market-thesis` | Rebind `_DIR` and use an owned deterministic artifact or owned missing-file state | Declared owned load exact; generation/write zero |
| `us-x` | Fix US config/status/roster and single-view data; clear session triggers | Fixed reads exact; auto-refresh, AI summary, command, browser, and snapshot write zero |
| `retro-analysis` | Rebind `RETRO_DIR`, seed/own input, and force the default lane | Declared load exact; generation/write zero |
| `analytics-db` | Set analytics root before import; seed minimal DB/check/status; rebind every derived path; fix catalog/status/fetch boundaries | Fixed reads exact; `_write_data_health_status`, every refresh function, and Popen are bomb seams with `mutator.analytics.write_status.attempt=0`, refresh counters zero, and subprocess zero |
| `knowledge-graph` | Patch high-level `_load_graph` to a fixed small graph because its default path is definition-bound | `_load_graph` exact once; repository-vault reads and writes zero |
| `us-options` | Clear `opt_ticker` before render; providers remain fixed if a later data-state case is added | Initial options/yfinance/API calls exactly zero |
| `analyst-views` | Use an explicit owned empty candidate state; provider fixed only if a later data-state case is added | Initial analyst/yfinance calls exactly zero |
| `institutions` | Retain fixed stock holdings; force the initial stock view and own all roots | Stock load exact once; catalog/portfolio zero in the initial case |
| `industry-roles` | Rebind engine content/report roots and high-level loaders, including definition-bound defaults | Declared owned loaders exact; save/write zero |
| `watchlist-categorize` | Rebind TradingView/theme roots, clear `tv_text`, fix sectors, force IBKR unavailable | Owned reads/sectors exact; yfinance/connect/import/save zero |
| `influencers` | Rebind roster path; clear preview/search/undo/detail session state | Roster load exact; search/browser/save/undo zero |
| `schedules` | Retain fixed typed schedule and result fetchers | Schedule/result reads have exact counts; execute/launch zero |
| `ai-updates` | Retain fixed typed updates seam | Update load exact once; refresh/write zero |
| `crypto-universe` | Rebind latest-universe and TradingView paths to owned artifacts | Declared owned loads exact; refresh/write zero |
| `crypto-screener` | Keep dynamic `_shared.DATA_DIR` under the owned root and clear route state | Declared owned loads exact; network/write zero |
| `crypto-x` | Reuse the fixed CRYPTO config/status/roster/single-view contract | Fixed reads exact; auto-refresh, AI summary, command, browser, and snapshot write zero |

All 27 rows inherit one fail-closed initial-render sentinel set. At bootstrap and
for each capture, the exact count for every subprocess/Popen, external browser,
login/auth, background-refresh, runtime-write, unapproved network, undeclared
loopback, and production-artifact-read attempt is zero. Three known route bombs
are named rather than hidden behind a generic digest:

- `mutator.theme_flow.launch_background.attempt == 0`;
- `mutator.analytics.write_status.attempt == 0`;
- `mutator.subprocess.popen.attempt == 0`.

The X refresh/snapshot and all other route-specific mutators receive similarly
stable names in the contract. `theme_flow_controls` definition-time defaults are
replaced at their high-level caller seams; changing module constants alone is
not accepted. Analytics roots are set before import and all derived paths are
then asserted to be below the fixture root.

A process-level filesystem access audit is installed before `app.py` imports.
It permits source/package/config reads required to start the app and reads below
the owned fixture/run roots, but rejects and counts reads or writes beneath
declared production runtime roots (`data`, `reports`, candidate/chat/vault,
analytics, and every bound page-specific artifact root). Each page also reports
the resolved runtime-root projection. A runtime write digest remains useful
defense-in-depth, but cannot substitute for the zero production-read/write
audit.

The owned child keeps the Python DNS/socket guard and browser routing guard. The
allowlist is one run-scoped contract containing only the exact owned
`host:Streamlit-port` and exact owned `host:deny-proxy-port`; `localhost` or a
loopback subnet is never trusted as a category. In particular,
`127.0.0.1:8000`, every other loopback port, and every non-loopback destination
must be denied, counted, and fail the capture.

On Darwin, the UX-1B full-page child is additionally launched through a
calibrated `sandbox-exec` profile generated from the same two-port contract. The
browser route guard, Python socket/DNS guard, proxy, and kernel profile must all
agree on that contract. Focused calibration proves:

- the owned Streamlit and deny-proxy ports work as intended;
- a TEST-NET external address is denied;
- the real API address `127.0.0.1:8000` is denied; and
- an unapproved, runner-owned dummy loopback listener receives zero bytes while
  the attempted connection returns the expected guard error or `EPERM`.

HTTP(S)/ALL proxy variables point only to the owned deny endpoint so native HTTP
clients that honor them cannot reach another host. Any attempted browser,
Python, proxy, provider-level, or undeclared-loopback access fails the capture.
Unsupported kernel isolation is recorded honestly and cannot close the Darwin
acceptance gate.

#### Resolution R1B-03 — full pages and semantic states are separate matrices

The phrase "states across all 27 pages" is resolved as two complementary gates:

1. all 27 real pages render at all three viewports with the global theme, route,
   provider, layout, exception, and network oracles; and
2. one fixture-only semantic state gallery contains every required global widget
   and machine-observable state, at all three surfaces and all three viewports,
   with fail-closed computed-style oracles plus a static `:visited` CSS oracle.

A page is not required to invent an error, slider, or disabled action merely to
contain every state. Conversely, a screenshot-only 81-page run cannot replace
the state gallery's hover, active, focus-visible, disabled, alert, and contrast
checks.

#### Resolution R1B-04 — one Streamlit primary color cannot serve every role

Streamlit 1.57 uses `primaryColor` for white-on-fill primary buttons, selected
tab text/underline, selected controls, tertiary interaction, and a 50%-alpha
focus ring. No single candidate meets all text, component, and focus contrast
requirements. UX-1B therefore uses one hue family with separate semantic roles
and component-scoped CSS. It does not apply a repository-wide hex replacement.

Approved interaction tokens:

| Token | Value | Intended role |
| --- | --- | --- |
| `interactive.primary` | `#2563eb` | filled primary action |
| `interactive.hover` | `#1d4ed8` | primary hover |
| `interactive.active` | `#1e40af` | pressed/active primary action |
| `interactive.accent` | `#60a5fa` | selected tab text/underline, tertiary accent, links |
| `interactive.control` | `#3b82f6` | non-text control track/thumb/check/dot/boundary only |
| `interactive.disabled` | `#6b7280` | disabled fill/border role |
| `text.on-primary` | `#ffffff` | text on primary/hover/active fills |
| `text.disabled` | `#8b93a7` | visible disabled label; disabled semantics remain programmatic |
| `border.focus` | `#7fe3f0` | keyboard focus-visible outer outline, used only with a verified surface gap |

`.streamlit/config.toml` sets `primaryColor = "#2563eb"`,
`linkColor = "#60a5fa"`, and `linkUnderline = true`. Component-scoped CSS then
stabilizes roles that Streamlit otherwise derives from `primaryColor`.

Measured pure-color minimums before alpha composition:

| Pair | Ratio | Requirement |
| --- | ---: | ---: |
| white / primary | 5.17:1 | 4.5:1 |
| white / hover | 6.70:1 | 4.5:1 |
| white / active | 8.72:1 | 4.5:1 |
| accent / canvas, panel, elevated | 7.43 / 6.48 / 5.71:1 | 4.5:1 |
| control / canvas, panel, elevated | 5.14 / 4.48 / 3.95:1 | 3:1 |
| white control mark / control | 3.68:1 | 3:1 |
| focus / canvas, panel, elevated | 12.73 / 11.10 / 9.79:1 | 3:1 |
| focus / control | 2.48:1 | **fails**; direct adjacency is forbidden |
| disabled border / canvas, panel, elevated | 3.91 / 3.41 / 3.00:1 | informative; inactive exception retained |

All ratios are recomputed by tests from hex values. Browser gates use actual
computed foreground, background, border, outline, box-shadow, opacity, and
ancestor surface, including alpha composition; this table alone is not closure
evidence.

Selected-control styling is component-specific; `interactive.control` is never
used as a normal-text foreground and white-on-control `3.68:1` is claimed only
for a graphical check/dot/mark:

| Component part | Required role and oracle |
| --- | --- |
| Checkbox/radio/toggle mark, track, dot, boundary | `interactive.control`; each essential graphical boundary/mark >=3:1; adjacent label uses normal text and >=4.5:1 |
| Slider active track/thumb | `interactive.control`; graphical contrast >=3:1 |
| Slider value label | `interactive.accent`; text contrast >=4.5:1 on its actual composited surface |
| Selected segmented control | `interactive.primary` fill, `text.on-primary` label, `interactive.control` boundary; label >=4.5:1 and boundary >=3:1 |
| Unselected segmented label | normal text on its actual surface, >=4.5:1 |

Every visible label/value is checked separately on canvas, panel, and elevated
surfaces after alpha composition. Only non-text graphical marks use the 3:1
oracle.

The focus indicator uses a solid outer `border.focus` outline at least 3 CSS px
wide and an `outline-offset` that yields at least one full rendered CSS pixel of
the actual composited ancestor surface between the component paint/border and
the outline. This separation is mandatory because focus/control direct contrast
is only 2.48:1. The browser oracle does not trust the numeric offset alone: at
device scale 1 it samples the rendered gap and outer ring on all four sides,
requires the gap to match the resolved adjacent surface within a fixed channel
tolerance, verifies ring/surface contrast >=3:1, and rejects any side that is
missing, overwritten by a neighbor, or clipped. If an implementation cannot
produce that surface gap for a component, it must use a tested two-layer ring
whose inner/outer adjacent pairs each independently meet >=3:1; changing this
choice requires plan review.

#### Resolution R1B-05 — signal and interaction references are split

The design-system registry gains distinct reference aliases for
`interaction_primary` and `avoid_red`. `signal.avoid` remains `#ef4444` and no
longer points to a reference named `current_primary`. The following remain exact:

- `signal.avoid = #ef4444`;
- `signal.bearish = #ef553b`;
- `feedback.error = #ef553b`;
- `_shared.ACCENT = #ef4444` and all public signal/chart color values;
- UX-1A chip projection values and safety behavior.

`ui/_shared.py` is byte-protected. Its legacy comment is not worth expanding the
production scope; the UX-1B docs clarify that `ACCENT` is an alarm/AVOID signal,
not an interaction token.

#### Resolution R1B-06 — Streamlit DOM behavior is versioned

The current environment is Streamlit 1.57.0 while `requirements.txt` permits
unbounded upgrades. UX-1B pins `streamlit==1.57.0`, the version used for source
inspection and computed-style evidence. The pin is the only dependency change.
No package installation is required because the environment already uses that
version. Any later Streamlit upgrade must rerun the selector-presence and
computed-style matrix before the pin changes.

CSS may target stable semantic/test attributes such as `kind`, `role`,
`aria-selected`, `aria-checked`, and `data-testid`; generated emotion class names
are forbidden. The theme contract freezes every selector, property, state, and
allowed owner/test-case ID. The gallery requires the actual matched ID set to
equal the expected set—not merely be non-empty. Across all 27 pages, every
matched node must have the nearest permitted `data-testid`/`kind`/ARIA owner;
an orphan or cross-role match fails. Every `!important` occurrence is allowed
only by an exact `(selector, property)` entry. Focus rules use low-specificity
`:where(...)` component scopes so existing more-specific AI Chat textarea focus
behavior remains intact.

#### Resolution R1B-07 — UX-1B owns a separate evidence namespace

UX-1B output is written only beneath:

`.claude/ui_snapshots/ux1b/<pretheme|posttheme|theme-states>-<run-id>/`

Its manifest mode is explicit (`ux1b-full-pages` or `ux1b-theme-states`). A UX-1B
profile refuses an output path under `ux0` or `ux1a`. Existing UX-0 and UX-1A
documents, manifests, screenshots, and hashes remain immutable.

#### Resolution R1B-08 — rollback is owned and dirty-worktree safe

Task 0 copies the exact prechange bytes of the four-file runtime batch into
an ignored, runner-owned backup directory and records hashes. Git reset,
checkout, or restoration from `HEAD` is forbidden because the worktree contains
user and earlier-phase changes.

The runtime batch is exactly:

- `.streamlit/config.toml`;
- `app.py`;
- `ui/_design.py`;
- `requirements.txt`.

There is no claim of a cross-file filesystem transaction. Apply and rollback run
inside a maintenance window as staged, validated replacements. Immediately
before Task 3 writes any member, its live SHA-256 must equal the frozen pretheme
SHA; otherwise execution stops without writing. Immediately before operational
rollback, every live member must equal its recorded posttheme SHA; otherwise
rollback refuses to overwrite the newer bytes and requires manual
reconciliation. Verification/evidence tooling may remain because it is not
loaded by the production app. A scratch-copy rehearsal must prove all four
restored files match their prechange SHA-256 values and that UX-1A contract,
safety tests, and protected hashes still pass.

#### Resolution R1B-09 — UX-1B forward-classifies the new trusted style site

The historical UX-1A classification and contract remain byte-immutable. UX-1B
creates `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json` and modifies the
current contract test to layer the new classification forward:

- validate the frozen UX-1A evidence internally and its backward-compatible
  projection against current source after excluding only approved UX-1B deltas;
- require the current unsafe-site union to equal the UX-1A sites plus exactly
  the new trusted static theme CSS injection site;
- classify that new site by stable site ID and expression fingerprint, with a
  rationale that it accepts no arguments or runtime/artifact/session input;
- classify every current `type="primary"` action site as ordinary interaction
  or danger, require the union to be exact, and reject any danger/destructive
  site matched by ordinary-primary CSS; and
- fail on any other added/removed unsafe, diagnostic, or primary-action site.

`app.py` adds a separate trusted static CSS injection rather than changing the
existing metric CSS expression. This preserves the historical site's stable
identity and makes the one forward delta explicit.

## Scope

### Production and Runtime-Requirement Files — Frozen Set

Modify only after the 81/81 pre-theme gate:

- `.streamlit/config.toml`
- `app.py`
- `ui/_design.py`
- `requirements.txt` (only `streamlit==1.57.0`)

No page module is pre-authorized. If a full-page audit suggests a page-local
compatibility edit, stop, update this plan with the exact file and reason, and
repeat both independent plan reviews before changing it.

### Test, Fixture, and Tool Files — Frozen Set

Create:

- `scripts/ui_ux_theme_fixture_app.py`
- `scripts/ui_ux_theme_matrix.py`
- `scripts/test_ui_ux_theme.py`
- `scripts/test_ui_ux_theme_matrix.py`

Modify:

- `scripts/ui_ux_fixtures.py`
- `scripts/ui_ux_snapshot_matrix.py`
- `scripts/test_ui_ux_fixtures.py`
- `scripts/test_ui_ux_snapshot_matrix.py`
- `scripts/test_ui_ux_components.py`
- `scripts/test_ui_ux_contract.py`
- `scripts/test_dashboard_navigation.py`
- `Makefile`

The existing fixture entrypoint remains unchanged unless an implementation
review proves a concrete need. If that occurs, add `scripts/ui_ux_fixture_app.py`
to this frozen set before editing and repeat plan review.

### Evidence and Documentation Files — Frozen Set

Create:

- `docs/ui-ux/quant-radar-ui-v2-ux1b-prechange.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b.md`

Modify:

- `docs/superpowers/plans/2026-07-15-quant-radar-ui-ux-redesign.md`
- `docs/USER_GUIDE.md`
- `.agents/design-system/default.json`
- `.agents/design-system/INDEX.md`
- `.agents/PROJECT.md`
- `.agents/atelier.md`
- `.agents/palette.md`
- `.agents/scribe.md`

This plan file is planning evidence and may be revised during blocker review.

### Protected Files and Areas

Byte-protected throughout UX-1B:

- `ui/_shared.py`
- `ui/_components.py`
- every `ui/*.py` page module other than `ui/_design.py`
- `ui/_read_api.py`
- `api/**`
- provider, writer, trading, and business logic under `scripts/**`, except the
  explicitly listed fixture/test/tool files
- deployment/service files
- runtime artifacts under `reports/`, `data/`, configured shared volumes, and
  user chat/candidate directories
- all UX-0 and UX-1A evidence and snapshot directories

Pre-review reference hashes:

| File | SHA-256 |
| --- | --- |
| `.streamlit/config.toml` | `102d584059084f741addab857c98fc7fda92799fd8fc1aa112d93830c72c6dbf` |
| `app.py` | `1f0d8ec142aee605e51e126add8f867df06c81eb900475204630812acd019f85` |
| `ui/_design.py` | `0844c44dfc0b254f541ce7b9188cb71856e8549bcaaffea44db220c44a3be92d` |
| `ui/_shared.py` | `9391c5704356ac2e68547d89a76565890293f7c38ddceb6c364a0b8bcfbff184` |
| UX-0 baseline JSON | `cec8135ca49aba1859c96635865de72f88993f6aa838fca72da3301a5aff6930` |
| UX-0 baseline Markdown | `d70c49f820b6bd8bcb421b49a033dac80b11414142903515665d9dbde4cbb478` |
| UX-1A contract | `5085e9a1cce20ca0b0fd58dda623436cce48ebc0302398bb073318dfabe36a5b` |
| UX-1A classification | `364515dd67ecb82ac5ce1f0b73bd8399bdfb31e654314f143e1f9f1c03a10f9c` |
| UX-1A evidence Markdown | `c58a9a30be87d483eb7a419859e344f8ec51ce401548d3c6dfd810f5a583725e` |

Task 0 refreshes hashes for every planned existing file immediately before the
first implementation edit and records the accepted-plan SHA. Reference hashes
above are review anchors, not permission to overwrite user changes.

## Non-Goals

UX-1B does not:

- redesign the sidebar, navigation grouping, page layout, mobile shell, AI Chat
  position, typography, logo, chart palette, or information hierarchy;
- fix the known mobile expanded-sidebar obstruction or floating AI overlap;
- reorder Today Decision or introduce later shared layout components;
- change page titles, groups, routes, bookmark paths, `PAGE_REGISTRY`, render
  callables, or session handoff keys;
- change provider behavior, API/fallback rules, caching, call order, candidate
  identity/order, calculations, signals, or fail-soft reads;
- change danger, bearish, AVOID, loss, success, warning, or information meaning;
- rewrite page-local color constants, chart traces, chips, historical data, or
  runtime artifacts;
- claim full WCAG conformance, Safari parity, SUS/SEQ improvement, or completion
  of UX-2 and later phases.

## Requirements

| ID | Requirement |
| --- | --- |
| `UX1B-REQ-001` | Use the exact approved interaction token family and keep red out of ordinary link/tab/button/selected-control/focus roles. |
| `UX1B-REQ-002` | Preserve exact danger, bearish, AVOID, error, feedback, signal, chip, and `_shared` values and behavior. |
| `UX1B-REQ-003` | Apply CSS only through fixed trusted tokens and component-scoped stable selectors; generated class names and dynamic CSS inputs are forbidden, and every selector/property has an exact allowed owner set. |
| `UX1B-REQ-004` | Pass the explicit machine-observable computed-style contrast/state matrix including alpha composition, exact selector matches, rendered focus-gap/adjacency pixels, and a separate static same-token `:link`/`:visited` contract. |
| `UX1B-REQ-005` | Produce independent pre/post 27-page x 3-viewport Chromium manifests with exactly 81 unique route/viewport captures each. |
| `UX1B-REQ-006` | Make all 27 initial renders deterministic, isolated from production reads/writes, subprocesses, background mutators, undeclared loopback, and external network access without replacing page render functions. |
| `UX1B-REQ-007` | Preserve the frozen 27-record projection and exact requested/final/selected/callable, ready-marker, provider-count, session, source-root, layout, artifact, and fail-soft contracts. |
| `UX1B-REQ-008` | Keep UX-0 and UX-1A evidence immutable and write only to the UX-1B evidence namespace. |
| `UX1B-REQ-009` | Pin and report the Streamlit version whose DOM/theme behavior is verified. |
| `UX1B-REQ-010` | Rehearse an owned four-file staged rollback with compare-and-swap guards that restores old theme bytes without reverting UX-1A or overwriting newer work. |
| `UX1B-REQ-011` | Forward-classify the one trusted static theme CSS site and all primary-action sites while keeping UX-1A evidence byte-immutable. |

## Design and CSS Contract

### Pure Token Layer

`ui/_design.py` remains importable without Streamlit and retains immutable
mapping proxies plus pure contrast helpers. It adds only the approved
interaction roles and a trusted static CSS builder/constant. The builder accepts
no arguments and interpolates only values from the immutable token registry.

Existing signal and feedback maps are unchanged. `COLOR_TOKENS` exposes the new
interaction and text roles without removing old keys. Tests reject red values in
the interaction family and reject blue values in `signal.avoid`,
`signal.bearish`, and `feedback.error`.

### App Injection Boundary

`app.py` imports `_design` after `st.set_page_config` and injects the trusted
global theme CSS once, adjacent to the existing metric CSS. This is a
presentation-only static unsafe-HTML site. The current inventory is covered by
the UX-1B forward classification record; the historical UX-1A classification
and contract are not rewritten. No dynamic label, provider value, URL, session
value, or artifact content can enter the style string.

### Component-Scoped Selectors

The CSS contract covers only:

- primary button, form-submit, download, and primary link-button variants;
- tertiary interaction accent where Streamlit derives it from primary;
- selected/hovered tabs and their underline;
- checked radio/checkbox, toggle, slider, and selected segmented controls;
- markdown `:link` and `:visited` rules, both fixed to the same accent token and
  underline; runtime computed-style evidence is intentionally limited to
  unvisited/hover/focus-visible because Chromium protects visited history;
- focus-visible on real focusable controls inside the app;
- disabled primary controls.

Selectors use `data-testid`, `kind`, semantic roles, and ARIA state. They must not
target all `button`, all `a`, all SVG, all text, chips, alerts, charts, or
page-authored signal elements. `!important` is allowed only where the tested
Streamlit rule otherwise wins; every occurrence is listed in the theme contract.

### State Criteria Matrix

| State | Executable browser expectation |
| --- | --- |
| Default primary | exact white foreground, primary fill, control border; text >=4.5:1 and visible boundary >=3:1 on every surface |
| Hover | exact hover fill, white foreground, visible border; selector state changes without layout shift |
| Active/pressed | exact active fill, white foreground, visible border; mouse-down state is captured before release |
| Keyboard focus | `:focus-visible` outer outline at least 3 CSS px; at least 1 full rendered CSS px of verified composited surface separates it from the component; ring/surface and every actually adjacent color pair >=3:1; no side overwritten or clipped |
| Disabled | native `disabled`/`aria-disabled`, not tabbable/clickable, stable disabled styling, no hover/active color response; inactive contrast exception documented rather than misclaimed |
| Active tab | `aria-selected=true`, accent text >=4.5:1, underline at least 2 CSS px and >=3:1; selection is not color-only |
| Links | runtime unvisited/hover/focus use accent at >=4.5:1 with underline and visible focus; static CSS parser proves both `:link` and `:visited` use the same fixed accent token and underline |
| Checkbox/radio/toggle | checked ARIA/native state; graphical boundary/mark >=3:1; adjacent visible label >=4.5:1 |
| Slider | selected/native state; control track/thumb >=3:1; accent value label >=4.5:1 |
| Segmented control | selected ARIA state; primary fill plus white label >=4.5:1 and control boundary >=3:1; selection is not color-only |
| Info/success/warning/error | native role/icon/text remain present; text >=4.5:1 on computed composited background and state is not color-only |
| Danger/AVOID/bearish | exact protected reds remain in token/source contract and are not matched by primary CSS selectors |

Missing elements, transparent/unknown ancestor backgrounds, unparsable colors,
an actual selector-owner ID set unequal to its frozen expected set, orphan or
cross-role matches, a missing/non-surface/overwritten/clipped focus gap or ring,
duplicate fixture IDs, or an untested required state make the theme matrix fail
closed.

## Evidence Profiles

### `ux1b-full-pages`

- source: real `app.py` through the owned fixture entrypoint;
- routes: exactly the frozen 27-record projection after live equality succeeds;
- viewports: desktop 1440x900, tablet 768x1024, mobile 390x844;
- browser: Chromium mandatory; WebKit capability recorded but not a closure
  claim unless installed and explicitly run;
- output: UX-1B namespace only;
- checks: ready marker, requested route, final path, selected registry key, real
  callable identity, unique page/viewport identity, exception, browser/server
  network, production read/write audit, fixture quiescence, exact provider and
  zero-mutator counts, screenshot, geometry, component/page overflow, and
  pre/post layout parity;
- identity: record equal `sourceDigestStart`/`sourceDigestEnd` values over the
  frozen production/source/tool/fixture projection plus the accepted 27-page
  projection digest. A change while the child is running invalidates the whole
  manifest.

Known UX-2 debts (expanded mobile sidebar and floating AI overlap) are recorded
and compared for no regression; UX-1B must not relabel them fixed or fail solely
because the unchanged baseline contains them.

### `ux1b-theme-states`

- source: fixture-only state gallery; no production route is added;
- surfaces: canvas, panel, elevated;
- viewports: the same three sizes;
- widgets: primary/form/download/link/tertiary buttons, tabs, markdown link,
  checkbox, radio, toggle, slider, segmented selection, disabled control,
  info, success, warning, and error;
- interactions: hover, mouse-down active, keyboard Tab focus, selection, disabled
  click attempt; no script pretends to expose browser history state;
- checks: computed style, alpha-composited contrast, state semantics, exact
  selector-owner ID sets, static `:link`/`:visited` equality, rendered focus
  gap/ring pixels and geometry on every side, no external network, no exception,
  no overflow.

The gallery is test infrastructure, not a hidden production page and not visual
evidence that any specific business page contains a state it does not use.

## Acceptance Criteria

| ID | Acceptance criterion |
| --- | --- |
| `UX1B-AC-001` | Pre-theme `ux1b-full-pages` manifest passes exactly 81/81 before any production theme file changes. |
| `UX1B-AC-002` | Post-theme `ux1b-full-pages` manifest passes exactly 81/81 with the same unique page/viewport identities. |
| `UX1B-AC-003` | Pre/post frozen page projection, requested/final/selected/callable identity, ready marker, exact provider/zero-mutator counts, blocked-network, production read/write audit, and equal capture-start/end source contracts are exact. |
| `UX1B-AC-004` | Every machine-observable gallery state passes computed-style/contrast/owner-set and rendered focus-adjacency oracles on all surfaces/viewports, and static CSS proves same-token underlined `:link`/`:visited`. |
| `UX1B-AC-005` | `primaryColor`, link settings, runtime token maps, design registry, and CSS contract contain the exact approved values and no red interaction role. |
| `UX1B-AC-006` | `_shared`, signal, feedback, chip, UX-0, and UX-1A protected hashes remain exact. |
| `UX1B-AC-007` | No production page, provider, API, route, decision, session, runtime artifact, or layout source changes. |
| `UX1B-AC-008` | Every intentional screenshot diff is human-reviewed; unchanged geometry and known UX-2 debts are documented honestly. |
| `UX1B-AC-009` | Focused tests, all related regressions, full `make test`, compile, Python 3.10 AST, dependency, diff, and manifest/schema gates pass. |
| `UX1B-AC-010` | Scratch four-file rollback enforces compare-and-swap, restores prechange hashes, and passes UX-1A safety/contract tests without touching UX-1A files. |
| `UX1B-AC-011` | The UX-1B forward ledger covers exactly the new static CSS site plus the complete primary-action union; UX-1A evidence hashes remain exact. |

## Implementation Tasks

### Task 0 — Freeze dirty-worktree scope, accepted plan, and rollback bytes

Files:

- create `docs/ui-ux/quant-radar-ui-v2-ux1b-prechange.json`
- create ignored owned backup under `.claude/ui_snapshots/ux1b/rollback-source/`

Steps:

1. Record `git status --short`, hashes, sizes, existence, and classification for
   every planned existing, planned-created, protected, runtime, UX-0, and UX-1A
   path.
2. Require the live location-free page projection to equal the frozen 27-record
   SHA from R1B-01; record those exact records, the ready-marker catalog, the
   accepted plan SHA-256, and the exact approved palette.
3. Copy the exact bytes of `.streamlit/config.toml`, `app.py`, `ui/_design.py`,
   and `requirements.txt` into the owned backup with a hash manifest.
4. Compute source and runtime aggregate digests using repository-relative POSIX
   ordering; do not use Git as the restoration source.
5. Create the UX-1B forward-classification schema with exact UX-1A parent hashes
   and an empty/pending UX-1B delta; its final delta is populated only from the
   reviewed Task 3 source.
6. Assert no unplanned status delta occurred while freezing the gate.

Gate: manifest schema tests pass and both independent plan reviews report no
blocker/high finding. Only then may Task 1 edit tooling.

### Task 1 — Build the 27-page isolated fixture profile and state oracle test-first

Files:

- modify existing fixture/runner/tests listed in scope
- create the theme fixture app, theme matrix, and their tests
- modify `Makefile`

Red tests first:

1. Assert the current runner rejects the missing 20 routes and lacks the UX-1B
   manifest/profile.
2. Assert the exact frozen 27 projection, all 27 ready markers, and all four
   runtime identities are required once. Mutating a route, nav title, callable,
   order, ready marker, or selected key must fail even when the count stays 27.
3. Reproduce the current `us-screener` `fwd_30d_return` and
   `sector-rotation` `group` fixture failures.
4. Reproduce Theme Flow auto-launch, Analytics status reconciliation/write, X
   auto-refresh, definition-bound paths, and production artifact-read attempts;
   require the named zero-mutator/read sentinels from R1B-02.
5. Exercise native HTTP, Python socket/DNS, browser, subprocess, filesystem, and
   runtime-write sentinels. Prove the two exact owned ports work while
   `127.0.0.1:8000`, an unapproved dummy listener, and TEST-NET fail with zero
   bytes delivered.
6. Assert the theme oracle fails for a missing state, unequal selector-owner set,
   transparent unknown background, low text/UI/focus contrast, clipped focus,
   disabled hover response, low selected-control label/value contrast, or red
   interaction token. Assert the static parser fails unless `:link` and
   `:visited` use the same fixed accent token and underline. Add an explicit
   negative fixture where `#7fe3f0` directly touches `#3b82f6` with no gap; it
   must fail at 2.48:1 even though the ring contrasts with the outer surface.
7. Assert legacy UX-0/UX-1A argument preparation, modes, counts, and output
   namespaces are unchanged.

Implementation:

1. Validate the live static inventory against the frozen projection, then build
   the full-page catalog from the accepted 27 rows and keep legacy seven-page
   defaults unchanged.
2. Add the R1B-01 ready markers and R1B-02 deterministic provider/path fixtures,
   exact positive/zero counter maps, pre-import filesystem audit, and resolved
   root assertions for every route while preserving real render identities.
3. Add the owned Darwin exact-two-port process sandbox, deny proxy, dummy-port
   calibration, and explicit capability/attempt evidence for the UX-1B profile.
4. Add separate `ux1b-full-pages` mode/output validation and a pre/post manifest
   comparator, including equal launch/stop source digests.
5. Add the fixture-only semantic gallery and computed-style/contrast matrix.
6. Add static link-state, exact selector-owner, exact `!important`, selected-
   control, and forward-classification test infrastructure.
7. Add these exact Make targets without changing the existing
   `ui-ux-baseline` target: `ui-ux1b-focused-tests`, `ui-ux1b-legacy`,
   `ui-ux1b-pretheme`, `ui-ux1b-theme-states`, and `ui-ux1b-posttheme`.

Green gate:

```bash
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/test_ui_ux_theme.py
.venv/bin/python scripts/test_ui_ux_theme_matrix.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Then run `make ui-ux1b-legacy`. It executes explicit Chromium-only captures of
the unchanged no-argument UX-0 matrix (21/21) and UX-1A focused matrix (20/20),
writing beneath `.claude/ui_snapshots/ux1b/legacy-validation-<run-id>/`. Compare
legacy mode, route/case identity, exact provider projection, failure oracles,
and normalized manifest schema; the historical UX-0/UX-1A snapshot tree hashes
must remain exact. No production theme file may differ from Task 0 after this
task.

The Make target expands to the legacy runner with `--browser chromium` and no
`--profile`, `--page`, or `--case` for the 21-capture UX-0 run, followed by the
five exact `FOCUSED_CASES` and four exact viewports (`desktop`, `tablet`,
`mobile`, `320x844`) for the 20-capture UX-1A run. Both commands pass explicit
new UX-1B validation `--out-dir` paths, `--no-prompt`, and `--json`; neither can
select WebKit or write a historical namespace.

### Task 2 — Capture and close the 81/81 pre-theme baseline

Files:

- ignored `.claude/ui_snapshots/ux1b/pretheme-<run-id>/`
- create initial `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`

Steps:

1. Reassert the four runtime-batch files and frozen page projection match Task 0.
2. Run `make ui-ux1b-pretheme`, whose exact runner command is:

   ```bash
   .venv/bin/python scripts/ui_ux_snapshot_matrix.py --profile ux1b-full-pages --phase pretheme --browser chromium --no-prompt --json
   ```

   The explicit browser argument is mandatory; optional WebKit discovery cannot
   add entries to this manifest.
3. Require exactly 81 unique passed captures, 27 unique pages, three exact
   viewports per page, no exception, no external attempt, no repository runtime
   read/write, and exact quiescent provider/zero-mutator counters.
4. Verify every row's requested route, final path, selected key, real callable,
   ready marker, and fixture provider/root projection.
5. Human-review all 81 screenshots. Record known pre-existing UX-2 layout debts
   without turning them into UX-1B failures.
6. Require equal `sourceDigestStart`/`sourceDigestEnd`; freeze the manifest hash,
   normalized identity/provider/root/geometry projection, screenshots' hashes,
   source/runtime digests, accepted projection digest, and browser/tool versions
   in the theme contract.

Gate: 81/81 plus human review. If any page cannot be made deterministic without
a production page change, stop, revise scope, and repeat plan review.

### Task 3 — Apply the semantic theme in one production batch

Files:

- `.streamlit/config.toml`
- `app.py`
- `ui/_design.py`
- `requirements.txt`

Red tests first:

1. Exact config and token tests expect the approved values and fail on current
   red primary.
2. Static CSS tests require trusted, scoped selectors and reject generated class
   names, broad global selectors, dynamic inputs, missing states, and red
   interaction values.
3. Protected tests require exact signal/feedback/chip and `_shared` values.
4. Version test requires Streamlit 1.57.0 in the requirement and runtime.
5. Forward-classification tests require exactly one new trusted static CSS site,
   a complete primary-action classification, and the unchanged UX-1A backward
   projection.

Implementation:

1. Compare all four live runtime-batch SHA values with the frozen pretheme
   values; stop before any write if one differs.
2. Change only the config theme keys specified in R1B-04.
3. Extend immutable interaction/text tokens and trusted CSS in `_design.py`.
4. Add a separate trusted CSS injection once in `app.py` without changing the
   existing metric CSS, navigation, or layout CSS.
5. Pin the already-installed Streamlit 1.57.0 requirement.
6. Populate the forward ledger from the static inventory and prove its exact
   expected delta; do not edit either UX-1A evidence file.

Gate: focused token/static tests, `scripts/test_ui_ux_contract.py` under the
project virtualenv, and `git diff --check` pass; the diff contains no other
production path.

### Task 4 — Prove computed states and accessibility behavior

Files:

- ignored `.claude/ui_snapshots/ux1b/theme-states-<run-id>/`
- update theme contract

Steps:

1. Run `make ui-ux1b-theme-states`; it invokes the theme matrix with the project
   virtualenv, `--browser chromium --no-prompt --json`, across all surfaces and
   three viewports.
2. Exercise default, hover, mouse-down active, keyboard focus, disabled click,
   active/hovered tab, unvisited/hovered/focused link, and every selected
   control. Do not synthesize or claim a machine-observed visited state.
3. Parse actual CSS colors and alpha, resolve the visible ancestor background,
   and enforce the state matrix. For focused selected checkbox, radio, toggle,
   slider, and segmented control, sample all four sides at device scale 1 and
   prove a full surface-colored separation pixel plus unclipped outer ring; also
   exercise primary, tab, and link focus owners.
4. Statically parse `:link`/`:visited` for exact same-token accent and underline.
   Require exact semantic/ARIA state, per-part control text/graphical contrast,
   underline width, focus width/offset, rendered gap/ring adjacency, exact
   selector-owner sets, exact `!important` allowlist, and non-overflow geometry.
5. Confirm danger/AVOID/bearish samples remain red, contain text/icon meaning,
   and are not selected by interaction CSS.
6. Human-review the gallery screenshots at all viewports.

Gate: all gallery state/viewport/surface cases pass with no missing state.

### Task 5 — Capture post-theme 81/81 and compare exact contracts

Files:

- ignored `.claude/ui_snapshots/ux1b/posttheme-<run-id>/`
- update `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`

Steps:

1. Run `make ui-ux1b-posttheme`, which uses the same explicit Chromium-only
   command and `--phase posttheme`.
2. Require exactly 81/81 and compare to pretheme for exact route, title,
   selected key, callable, ready marker, exact fixture provider/zero-mutator
   counts, network, production reads/writes, equal start/end source digests,
   page dimensions, overflow classification, and known-debt classification.
3. Treat screenshot color differences as intentional only when they match the
   interaction-theme scope. Any typography, spacing, order, content, chart,
   signal, alert meaning, or layout diff is a blocker.
4. Human-review every changed screenshot; byte-identical screenshots may be
   recorded by hash without reopening.
5. Recompute source/runtime and protected hashes.

Gate: both manifests pass, comparator passes, and every visual diff is explained.

### Task 6 — Regression, adversarial review, and scope reconciliation

Run at minimum:

```bash
.venv/bin/python scripts/test_ui_ux_theme.py
.venv/bin/python scripts/test_ui_ux_theme_matrix.py
.venv/bin/python scripts/test_ui_ux_components.py
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_ui_ux1a_safety.py
make test
.venv/bin/python -m compileall -q app.py ui scripts
.venv/bin/python -m pip check
git diff --check
```

Also:

1. parse all changed Python files with Python 3.10 grammar;
2. compare actual diff/status delta to the frozen file set;
3. recheck exact UX-0, UX-1A, `_shared`, page, API, provider, and runtime hashes;
4. scan CSS for generated classes, broad selectors, external URLs, dynamic
   interpolation, exact selector/property/owner-set coverage, exact
   `!important` allowlist, and interaction selectors matching danger fixtures;
5. validate the UX-1B forward ledger/current union, all primary-action
   classifications, and the historical UX-1A backward projection;
6. run two independent implementation reviews: correctness/scope and
   accessibility/theme/security;
7. fix every blocker/high finding and rerun affected plus final gates.

### Task 7 — Rehearse rollback in a scratch copy

Steps:

1. Copy the post-theme four-file runtime batch plus required tests into an owned scratch
   directory outside source paths.
2. First prove compare-and-swap refusal by changing one scratch live byte away
   from the recorded posttheme hash; the rehearsal must make no replacement.
3. Restore the recorded posttheme byte, pass the guard, and stage validated
   Task 0 replacements for all four files.
4. Verify exact prechange hashes, requirement value, and config parse.
5. Run UX-1A safety/components/contracts against the restored theme projection.
6. Verify UX-1A evidence files are untouched and the rollback operation does not
   address any runtime artifact.
7. Delete only the owned scratch directory after recording the result; never
   operate rollback on the user's live worktree during rehearsal.

Gate: exact byte restoration and UX-1A compatibility pass.

### Task 8 — Close evidence and parent roadmap

Files:

- create/update UX-1B evidence docs listed in scope
- update parent plan, user guide, design registry/index, and skill journals

Record:

- approved palette and Streamlit version;
- pre/post/theme manifest paths, hashes, counts, and limitations;
- computed contrast minima and exact selector-owner match sets;
- provider/route/runtime/protected parity;
- visual review method and every known unchanged UX-2 debt;
- Chromium result, WebKit capability, Safari status, and human-study status;
- full verification results and any check not run;
- rollback rehearsal result;
- exact actual diff versus accepted plan and any reviewed divergence.

Only after both final independent reviews pass may the parent roadmap mark UX-1B
complete and move to UX-2.

## Rollback Procedure

Operational rollback uses Task 0 owned bytes, never Git reset:

1. while the maintenance window is active, compare all four live SHA-256 values
   with the recorded posttheme bundle; if one differs, refuse to overwrite it
   and require manual reconciliation;
2. stop the owned/relevant Streamlit process using the normal local service
   workflow; do not kill unknown listeners;
3. stage, hash-validate, and replace `.streamlit/config.toml`, `app.py`,
   `ui/_design.py`, and `requirements.txt`; this is a validated four-file
   sequence, not a claimed cross-file filesystem transaction;
4. restart/rebuild Streamlit as appropriate so config and requirement changes
   are loaded;
5. verify exact prechange hashes, health, root route, a primary button, active
   tab, and UX-1A safety/contract suites;
6. leave UX-1A files and runtime artifacts untouched;
7. retain UX-1B evidence/tooling with a rollback note unless a full repository
   revert is separately requested.

Partial restoration of only config or only CSS is forbidden because it can
recreate mixed, low-contrast states.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Red signal values are accidentally recolored | Byte-protect `_shared` and page files; exact signal/feedback tests; no global hex replacement |
| One primary color fails different Streamlit roles | Split semantic roles and verify actual computed styles with a dedicated gallery |
| Streamlit upgrade breaks selectors | Pin 1.57.0; forbid generated classes; exact selector-owner and version gates |
| Full-page fixture contacts real services or localhost API | High-level deterministic seams, production read/write audit, exact owned-port guards, deny proxy, Darwin kernel sandbox, zero-attempt counters |
| Fixture hides a broken render | Preserve all real render callables and assert per-route identity/provider contracts |
| Live 27-page source self-certifies a changed route | Compare the exact frozen location-free projection before catalog construction and every runner start |
| Source changes during 81 captures | Equal child-launch/child-stop source and fixture digests or fail the entire manifest |
| UX-1B rewrites historical evidence | Separate namespace and exact UX-0/UX-1A hashes |
| Global CSS overmatches unrelated UI | Exact selector/property/owner ID sets, nearest-owner checks, and exact `!important` allowlist |
| Selected-control text uses a 3:1 graphical color | Per-component parts and >=4.5:1 label/value oracles on every surface |
| Focus cyan directly touches selected-control blue | Mandatory sampled surface gap (or separately reviewed two-layer ring), all-side adjacency >=3:1, and clipping tests |
| Browser hides visited history state | Same-token static `:link`/`:visited` contract; runtime claims only observable unvisited/hover/focus states |
| Global CSS changes layout | Component-scoped selectors, pre/post geometry/overflow comparator, 81-page visual review |
| Disabled contrast is falsely claimed | Verify semantics and behavior; document the inactive-control contrast exception |
| Dirty worktree rollback loses user work | Owned byte backups and scratch rehearsal; no reset/checkout |
| 81 screenshots are mislabeled as usability evidence | Record them as visual/contract evidence only; no SUS/SEQ or Safari claim |

## Traceability Matrix

| Requirement | Design/task | Primary verification |
| --- | --- | --- |
| `UX1B-REQ-001` | approved palette, Tasks 3-5 | exact config/token tests and computed theme gallery |
| `UX1B-REQ-002` | signal split and protected set | protected hashes and danger fixture non-match |
| `UX1B-REQ-003` | CSS contract | static selector/dynamic-input tests |
| `UX1B-REQ-004` | state criteria matrix | theme matrix browser oracle |
| `UX1B-REQ-005` | full-page profile | pre/post exact 81 manifests |
| `UX1B-REQ-006` | fixture expansion/isolation | 27 real-render tests, network/write sentinels |
| `UX1B-REQ-007` | pre/post comparator | inventory, provider, runtime, layout parity |
| `UX1B-REQ-008` | evidence namespace/protection | path refusal and hash gates |
| `UX1B-REQ-009` | version decision | requirement/runtime exact-version test |
| `UX1B-REQ-010` | owned rollback | four-file compare-and-swap/refusal/restoration rehearsal |
| `UX1B-REQ-011` | forward classification | layered contract/current-union and primary-action tests |

## Review Protocol

Before implementation:

1. correctness/feasibility reviewer checks 27-page fixtures, manifest identity,
   provider parity, evidence namespace, scope, and rollback;
2. accessibility/security reviewer checks palette, actual Streamlit roles,
   computed-style criteria, selector scope, disabled claims, color independence,
   and network isolation;
3. all blocker/high findings are resolved in this document;
4. if the same unresolved blocker remains after three review iterations, stop
   and report it instead of executing.

## Plan Review Record

- **Pre-draft discovery:** BLOCKED. Found six execution blockers:
  missing 27x3 browser baseline, seven-route fixture/runner limits, no computed
  CSS oracle, unapproved/coupled palette, UX0 namespace pollution, and no
  micro-plan/rollback rehearsal.
- **Independent closure review 1:** BLOCKED. Correctness found missing forward
  unsafe classification, self-derived 27-page identity, unnamed bound-default/
  production-read/mutator seams, capture-time source identity, legacy browser
  regression, and rollback compare-and-swap. Accessibility/security found
  selected-control text-oracle errors, an impossible runtime `:visited` claim,
  all-loopback trust, the same Theme Flow/Analytics mutators, and selector
  overmatch risk. v0.2 incorporates every required correction; independent
  closure review 2 followed.
- **Independent closure review 2:** BLOCKED on one new adjacency case after all
  prior findings closed: `border.focus` is only 2.48:1 against
  `interactive.control`. v0.3 requires and pixel-verifies a real surface-colored
  separation gap on all sides for every selected-control focus case, adds the
  direct-adjacency negative test, and rejects clipping/overwriting. Independent
  closure review 3 followed.
- **Independent closure review 3:** PASS from both correctness/scope and
  accessibility/theme/security reviewers. The focus adjacency blocker is closed
  by the rendered surface-gap oracle and negative case; no blocker/high remains.
- **Local Streamlit probe:** confirmed white text on primary fills, selected-tab
  use of primary, automatic 15% hover darkening, and a 50%-alpha primary focus
  ring. Confirmed two fixture-shape failures and an unpatched native-network path
  when probing the additional routes; no production file was changed.

## Execution Record

Authorized at Task 0. No production theme file has changed under UX-1B; only
this accepted plan has changed during review.
