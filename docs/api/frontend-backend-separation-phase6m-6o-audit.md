# Phase 6M-6O Residual Separation Audit and Decision

- **Status:** complete; one successor slice accepted
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6m-6o-plan.md`

## Phase 6M — reproducible inventory

The audit parsed every `ui/*.py` module and reconciled the result with the
shrinking allowlist in `scripts/test_ui_backend_boundary.py:42`, the shared
reader/provider surface in `ui/_shared.py:216`, the endpoint inventory, and the
deployed release/runtime paths.

Entry counts before Phase 6P-6R implementation:

| Measure | Reproduced count | Evidence |
| --- | ---: | --- |
| Direct `scripts.*` bindings | 62 across 20 UI modules | `scripts/test_ui_backend_boundary.py:42` |
| UI modules importing `_shared` | 30 | AST scan of all `ui/*.py` |
| UI modules calling `load_json` | 14 modules / 20 calls | `ui/_shared.py:216` plus AST call scan |
| UI modules with direct filesystem/database-style calls | 10 modules / 19 calls | AST call scan for open/read/write/glob/connect families |

The earlier plan entry said 15 `load_json` modules. The reproducible source
count is 14; this was stale documentation, not a runtime or boundary change.

### Direct backend binding map

The count column is the number of unique allowlisted symbols, not call sites.
It totals exactly 62.

| UI module | Count | Dominant role | Decision |
| --- | ---: | --- | --- |
| `_candidate_controls.py` | 6 | job launch/auth/status mutation | Operational/Deferred |
| `_shared.py` | 7 | generic artifact/runtime compatibility plus live analyst/sector/theme providers | Mixed; keep local and trace consumers |
| `ai_chat.py` | 2 | private session store and LLM assistant | Internal/Deferred |
| `analytics_db.py` | 7 | DuckDB/store, health, provider refresh, and controls | Internal/Deferred |
| `ibkr_reconcile.py` | 1 | credentialed private broker provider plus persistence | Internal/Deferred |
| `industry_roles.py` | 1 | multi-file review state and mutations | Mutation-coupled/Deferred |
| `influencers.py` | 3 | live lookup, runtime roster ownership, analysis | Provider/mutation; public initial read already migrated |
| `institution_portfolio.py` | 1 | live SEC EDGAR provider | Provider/Deferred |
| `institutional_holdings.py` | 1 | live holdings provider | Provider/Deferred |
| `momentum_options.py` | 1 | provider cache policy | Provider/Deferred |
| `options_cockpit.py` | 8 | live options/quote/EDGAR providers, private trade state, strategy recording | Mixed private/provider/mutation |
| `options_flow.py` | 1 | live ticker drill provider | Provider/Deferred |
| `sector_rotation.py` | 2 | local AI generation plus fixed theme drill | Split: AI stays local; theme drill accepted |
| `theme_flow.py` | 3 | live sector/rotation providers and refresh control | Provider/mutation |
| `today_decision.py` | 2 | live quote and private Trade State aggregate | Mixed private/provider |
| `trade_state.py` | 1 | private cross-source aggregate | Internal |
| `us_cot.py` | 2 | Codex auth plus COT provider/generator | Operational/provider/mutation |
| `us_options.py` | 3 | live option/IV providers | Provider/Deferred |
| `watchlist_categorize.py` | 3 | private IBKR plus classification providers | Mixed private/provider/mutation |
| `x_sentiment.py` | 7 | auth, live social providers, analysis, summaries, writers | Operational/provider/mutation |

### Transitive `_shared` map

Thirty modules import `_shared`, but presentation tokens are not backend gaps.
The remaining boundary-bearing families are:

- generic local JSON compatibility: 14 modules / 20 calls
  (`ui/_shared.py:216`);
- private reconciliation: IBKR Reconcile, Options Cockpit, Today Decision, and
  Watchlist (`ui/_shared.py:308`);
- performance ledger: Schedules, Today Decision, and US Screener
  (`ui/_shared.py:314`);
- live analyst/theme/insider/sector providers (`ui/_shared.py:232-305`);
- runtime candidate paths and report-folder discovery used by US Screener
  (`ui/_shared.py:337` and `scripts/runtime_paths.py`); and
- styling, navigation, and display-only helpers, which are frontend concerns
  and are not migration defects.

## Phase 6N — sensitivity, concurrency, and risk matrix

| Residual source family | Sensitivity / capability | Concurrency and recovery | Public-read verdict |
| --- | --- | --- | --- |
| `content/theme_baskets.json` sector drill | Fixed public curation; consumer needs only theme name and parent SPDR ETF | Release-owned read; no UI write-back; fail-soft projection is reversible | **Accept one narrow projection** |
| Crypto Screener `crypto_scored.json` | Intended public data but producer/schema do not exist | No supported writer or publication contract | Defer |
| Candidate run status/history | commands, PIDs, auth state, errors, logs | background mutation and interruption repair | Operational; reject |
| Reconciliation, positions, watchlist, ledger, Risk Guard, Trade State | account-, position-, and decision-bearing private data | concurrent provider/writer activity; stale snapshots affect decisions | Internal; require identity/authorization |
| Industry Roles taxonomy/overrides/suggestions | review state that can be written back | direct final-path writes and multi-file partial-commit risk; no revision/ETag | Defer pending revisioned atomic mutation |
| Analytics DB and Data Health | arbitrary SQL/table/file capability plus operational diagnostics | refresh/rebuild subprocesses and mutable DB/files | Internal; fixed allowlist plus auth required |
| AI chat, reflections, AI reads, prompts and logs | user sessions, prompts, model output, diagnostics | retention/ownership and concurrent session mutation | Internal; reject |
| Analyst, quote, options, EDGAR, yfinance, IBKR, COT and social calls | live network/provider execution and possible credentials | rate limits, latency, cache freshness, provider side effects | Provider; not an artifact GET |
| Retrospective raw bundles | potentially publishable research but multiple datasets and broad raw evidence | schema/selection/size contract not yet fixed | Defer; no generic file/detail API |
| Local IV-grid series and compatibility X picks | bounded files but N+1 or compatibility-only siblings | existing caches/writers and newer strict APIs already cover presentation slices | Retain intentionally |

Explicitly denied: client paths or globs, SQL/table names outside a fixed
allowlist, positions/account rows, credentials/environment, logs/prompts/chat
sessions, provider execution, job controls, approval/reconcile/refresh actions,
and writes.

## Phase 6O — convergence decision

The public read audit has nearly converged, but one fixed presentation read
remains: `ui/sector_rotation.py:368-395` imports
`scripts.theme_flow.load_baskets()` only to reverse 35 curated themes into
their parent SPDR sectors. The 8.5 KiB source is shipped with the release and
has one stable `themes` object; all 35 current entries have one or more valid
parent sectors. The consumer never uses ticker membership, descriptions, or
representative hints.

Accepted successor contract:

- fixed `GET /api/v1/market-context/theme-drill`;
- fixed source ID `market-context.theme-drill`;
- maximum 11 unique sector rows, sorted by ETF;
- each row contains one SPDR ETF enum and source-ordered unique theme names;
- maximum 100 themes overall; strict bounded UTF-8/JSON source read;
- omit `_note`, descriptions, tickers, representative hints, paths, and
  producer/cache details;
- existing no-store envelope, loopback peer/Host enforcement, one-second
  client deadline, strict metadata, available-empty authority, immediate
  recovery, and no local fallback.

### Ripple blast radius and risk score

- Vertical L0 contract: model, reader, route, static OpenAPI.
- Vertical L1 client: one fixed typed loader.
- Vertical L2 consumer: only `_render_sector_themes_drill()`.
- Horizontal: focused API/client/UI tests, shrinking boundary receipt,
  navigation regression, Makefile, endpoint inventory, and journals.
- Planned production/contract files: 6; planned consumer files: 1; planned
  focused/global test files: 3; no source JSON, writer, provider, dependency,
  Compose, systemd, schedule, or deployment file.
- Estimated implementation delta: roughly +350 / -10 lines, dominated by
  strict DTO/OpenAPI/test declarations.

Ripple score: scope 8/30 + breaking change 0/25 + pattern novelty 2/20 +
coverage gap 2/15 + reversibility 1/10 = **13/100 (low)**. The route is additive,
uses the established fixed-read pattern, removes one frontend backend import,
and can be rolled back without data migration.

### Blocking review

- Iteration 1 rejected exposing the full basket records because tickers,
  descriptions, and representative hints are unused by the UI. The accepted
  DTO is the exact reverse-map presentation aggregate.
- Iteration 2 closed malformed-parent, duplicate, ordering, source/response
  cap, metadata, unavailable/failure, exact-one-load, local-fallback, and
  producer/writer drift risks. No blocker remains.

Final verdict: **GO** for the reviewed Phase 6P-6R plan.

## What I did not find

- No second safe residual public read with a stable producer, exact bounded
  consumer projection, and no identity/concurrency prerequisite.
- No reason to add authentication or a mutation endpoint in Phase 6P-6R.
- No deployment path mismatch: both API and Streamlit read immutable release
  `content/theme_baskets.json`; the shared writable roster mapping is unrelated.

## Post-6R receipt

The accepted projection is now implemented and verified. Sector Rotation uses
one `load_theme_drill()` result and has no local basket fallback. The inventory
is 54 API-only slices with 61 direct `scripts.*` bindings across 20 UI modules,
30 `_shared` importers, and 14 `load_json` modules. The fixed basket source and
its producer remain unchanged.
