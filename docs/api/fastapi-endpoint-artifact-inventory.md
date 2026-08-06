# FastAPI Endpoint / Artifact Inventory

**Status:** Active inventory through the Phase 6Y-7A protected mutation pilot

**Date:** 2026-08-06

**Scope:** All 27 Streamlit navigation pages registered in `app.py`, plus the global AI chat entry point

## Terms

- An **endpoint** is a stable HTTP address the frontend calls, such as `GET /api/v1/candidates/ranked`.
- An **artifact** is an already-produced file or named DuckDB dataset behind that endpoint, such as `ranked_candidates.json`.
- The browser never supplies an artifact path. It supplies only bounded business identifiers such as a ticker, ISO date, or fixed dataset name.
- Public Phase 1 remains read-only and loopback-only. Phase 6Y-7A adds one
  separately authenticated private Industry Roles action resource. It mutates
  only the canonical review aggregate; public reads still never refresh data,
  call providers, launch jobs, reconcile IBKR, call an LLM, or write files.

## Classification

| Class | Meaning |
| --- | --- |
| P1 | Fixed, persisted, non-sensitive artifact suitable for the first local API. |
| P2 | Useful bounded read endpoint, but not required to establish the first contract. |
| Internal | Contains operational or private data and requires authentication/authorization before exposure. |
| Deferred | Live, mutating, unstable, or underspecified behavior that is outside the read-only API. |

## Phase 1-Eligible Endpoint Whitelist

All endpoints below return the same fail-soft artifact envelope. A missing, unreadable, half-written, malformed, or shape-invalid expected artifact is a successful inspection of an unavailable artifact slot, not a server crash.

Eligibility does not mean they all ship in the first commit. The accepted implementation plan starts with ranked/scored candidates, three signal snapshots, and Market Thesis latest; the remaining eligible entries are later batches behind the same registry and envelope.

| Endpoint | Registry source | Expected root / anchor | Main consumers |
| --- | --- | --- | --- |
| `GET /healthz` | Process health only; does not inspect all artifacts | `status` | Deployment and frontend boot |
| `GET /api/v1/candidates/filtered` | `candidate_output_path("filtered_universe.json")` | object | 美股篩選 |
| `GET /api/v1/candidates/ranked` | `candidate_output_path("ranked_candidates.json")` | object + `ranked_candidates` | Compatibility; Trade State, industry roles, and other system status consumers remain local |
| `GET /api/v1/candidates/scored` | `candidate_output_path("scored_candidates.json")` | object + `all_scored` | Open compatibility route for legacy/non-UI consumers; migrated UI slices use strict sibling projections |
| `GET /api/v1/candidates/ranked/feed` | `candidate_output_path("ranked_candidates.json")` | strict bounded normalized ranked presentation rows | Today Decision candidate presentation (Phase 4F), Schedules candidate summary (4G), and Analytics DB fundamental defaults (4I); `/ranked` remains compatibility |
| `GET /api/v1/candidates/scored/feed` | `candidate_output_path("scored_candidates.json")` | strict bounded bucket-priority/deduplicated scored presentation rows | Today Decision LLM/candidate presentation (Phase 4F), Institutional Holdings optional score context (4H), Analyst Views grid (4Q), and Sector Rotation mapping seed (4R); `/scored` remains compatibility |
| `GET /api/v1/candidates/scored/screener` | `candidate_output_path("scored_candidates.json")` | exact bounded regime/count/candidate-card projection | US Screener scored slice (Phase 4S); filtered universe, Layer 2, DD, reports, ledger, analyst provider, and actions remain local siblings |
| `GET /api/v1/signals/options-flow/latest` | `reports/options_flow/latest.json` | object + `signals` | Compatibility endpoint; migrated Streamlit consumers use the strict `/feed` projection |
| `GET /api/v1/signals/options-flow/feed` | `reports/options_flow/latest.json` | exact bounded feed projection | Standalone Options Flow persisted feed; Phase 5A Schedules summary; Phase 5B standalone Options Cockpit quick picks |
| `GET /api/v1/signals/options-flow/validation` | `reports/options_flow/validation_summary.json` | object | 今日決策, validation views |
| `GET /api/v1/signals/reversal-radar/latest` | `reports/reversal_radar/latest.json` | strict snapshot provenance + unique ticker references | Radar discovery source API-only; Phase 5R reuses the strict `match_count` for Today Decision's latest candidate card |
| `GET /api/v1/signals/reversal-radar/validation` | `reports/reversal_radar/validation_summary.json` | strict conservative headline + three ordered hit-rate rows | Phase 5P strict contract; Phase 5Q Today Decision Reversal trust card; EV/excess statistics, curves, survivorship, caveats, and notes remain private |
| `GET /api/v1/signals/oversold-reversal/latest` | `reports/oversold_reversal/latest.json` | strict coiled-base display/validation projection | Radar coiled-base latest API-only; Phase 5S reuses the strict `match_count` for Today Decision's latest candidate card |
| `GET /api/v1/signals/oversold-reversal/validation` | `reports/oversold_reversal/validation_summary.json` | strict conservative headline + three ordered hit-rate rows | Phase 5M strict contract; Phase 5N standalone/embedded presentation; Phase 5O Today Decision Oversold trust card; EV, curves, survivorship/cohort, cost, caveats, and notes remain private |
| `GET /api/v1/market-context/money-flow/latest` | `reports/money_flow/latest.json` | strict coverage/provenance + allowlisted flow rows | Phase 4W contract; Phase 4X Schedules candidate summary; Phase 4Y/4Z standalone and embedded Options Cockpit external confirmation; Trade State remains local |
| `GET /api/v1/market-context/market-thesis/latest` | latest `reports/market_thesis/*forecast_*.json` | exact strict latest presentation/provenance projection | Market Thesis latest API-only page resolver; Phase 5U reuses it once for the Today Decision gate |
| `GET /api/v1/market-context/market-thesis/validation` | `reports/market_thesis/validation_summary.json` | strict counters + at most 27 full-key validation rows | Phase 5G Market Thesis forward-validation presentation and Phase 5L Today Decision trust card API-only; private invalid/rejected records and configuration omitted |
| `GET /api/v1/market-context/market-thesis/regime-history` | `reports/market_thesis/regime_history.json` | exact three-regime × three-window summary projection | Phase 5H Market Thesis regime-reference presentation API-only; raw daily/runs/episodes/rules/VIX omitted |
| `GET /api/v1/market-context/sector-rotation/latest` | latest exact `reports/sector_rotation_snapshots/YYYY-MM-DD.json` | strict `as_of`/`benchmark` + ordered allowlisted sector rows | Phase 5I contract; Phase 5J standalone quantitative board; Phase 5K Stock Checkup sector board; macro/leader lists/AI read/status stay private |
| `GET /api/v1/market-context/theme-drill` | fixed `content/theme_baskets.json` | maximum-11 sorted parent SPDR sector rows with maximum-100 source-ordered unique theme names | Phase 6P/6Q strict contract/client and Phase 6R Sector Rotation drill; tickers/descriptions/reps/root note/providers stay private |
| `GET /api/v1/knowledge/graph` | bounded compile of fixed `knowledge/**/*.md` vault | at most 500 path-free nodes, 5,000 coherent edges, and 1,000 unresolved pairs | Phase 6G–6I strict contract/client and fiftieth API-only Knowledge Graph slice; Markdown writers and Obsidian stay local |
| `GET /api/v1/watchlists/theme-taxonomy` | fixed `content/themes.json` | ordered maximum-100 name/description projection | Phase 6J/6K strict contract and fifty-first Watchlist taxonomy slice; private watchlists/IBKR/reconciliation and classification providers stay local |
| `GET /api/v1/social/influencers` | fixed runtime `SURGE_INFLUENCERS_PATH` without seeding | ordered categories plus maximum-1,000 allowlisted public roster rows | Phase 6J/6L strict contract; fifty-second Influencer page read and fifty-third X quick-pick; edits/lookups/providers stay local |
| `GET /api/v1/reports/daily-summary/latest` | newest exact `reports/YYYY-MM-DD/summary.json` | strict date/regime + ordered ticker/verdict references | Phase 5V contract; selected folder/source dates must match and never fall back; Phase 5W reuses one result for Today Decision gate/opportunities and Phase 5X for the Schedules report card while rank/prose/risk fields stay private |
| `GET /api/v1/reports/playbook-validation/latest` | `reports/playbook_validation/latest.json` | exact blocked or active source family projected to bounded summary rows | Phase 5Y strict contract; Phase 5Z Playbook Validation presentation in Retro Analysis; blocked reason, outcome count, decision/outcome rows, paths, providers, and writers remain private |
| `GET /api/v1/reports/continuation-validation/latest` | `reports/retrospective/continuation_strength.json` | exact blocked or active source family projected to bounded classification/forward-return rows | Phase 6A strict contract; Phase 6B/6C fixed client and Retro Analysis presentation; blocked reason, producer note, paths, providers, and writers remain private |
| `GET /api/v1/reports/cot` | server-owned `reports/cot/*.md` publication names | newest-first exact-date catalog, maximum 520 | Phase 6D strict catalog; Phase 6E Schedules latest-report card and duplicate-card cache |
| `GET /api/v1/reports/cot/{report_date}` | exact Markdown plus `.verified.json` sidecar | bounded sanitized-presentation pair with closed verified audit DTO | Phase 6D strict detail contract; Phase 6F COT persisted presentation; generation, auth, providers, logs, and writes remain local |
| `GET /api/v1/market-context/theme-flow/latest` | `reports/theme_flow_snapshot.json` | strict schema-v5 board presentation + coherence fingerprint | Phase 4V Theme Flow presentation; Phase 5D Schedules summary; refresh/status remains Internal |
| `GET /api/v1/market-context/theme-flow/analysis` | `reports/theme_flow.json` | strict ready validation-v8 rendered read | Phase 4V Theme Flow analysis API-only with client board-fingerprint match |
| `GET /api/v1/social/intelligence/latest` | `reports/social_intelligence/latest.json` | strict bounded radar/summary projection | Phase 4U X Sentiment persisted snapshot API-only; live refresh and legacy X-picks remain siblings |
| `GET /api/v1/institutions/funds` | `content/funds.json` | object + `funds` | 機構持倉的投資大戶快選目錄 |
| `GET /api/v1/system/schedules` | `content/schedules.json` | object + `schedules` | 系統排程 |
| `GET /api/v1/system/ai-updates` | `content/ai_updates.json` | object + `updates` | AI 更新 |
| `GET /api/v1/system/analytics-health` | `reports/analytics_checks/latest.json` | object | Analytics DB, 系統排程 |
| `GET /api/v1/crypto/universe` | `reports/crypto/universe_latest.json` | exact strict universe/diff/provenance projection | Crypto Universe API-only page; Phase 5C Schedules summary |

`candidate_output_path()` must preserve the existing `SURGE_RUNTIME_DIR` and `SURGE_CANDIDATE_OUTPUT_DIR` resolution in `scripts/runtime_paths.py`. Archive resolvers must preserve existing ordering semantics; for Market Thesis, a ready forecast wins over a regime-only forecast for the same day. Candidate run status is operational data and remains Internal until its error/output fields are redacted through a dedicated DTO.

## Protected Private Read / Mutation Pilot

| Endpoint | Fixed sources | Protected projection | Consumer |
| --- | --- | --- | --- |
| `GET /api/v1/private/industry-roles/review-board` | `content/industry_roles.json`; canonical `reports/industry_roles/review-state.json`, or optional legacy revision-zero seed | Singleton `operator`, taxonomy version, bounded role id/name rows, approved assignments, suggestions, and a strong ETag. Root notes, taxonomy descriptions/keywords/examples, audit/receipts, approved evidence/reviewer, paths, providers, and credentials are omitted. | Industry Roles initial/reload state; protected bearer plus loopback peer/Host checks. |
| `POST /api/v1/private/industry-roles/review-board/actions` | Same canonical Industry Roles aggregate and fixed taxonomy/theme inputs | Strict generate/approve/reject/defer union; requires bearer, strong `If-Match`, and `Idempotency-Key`. State, receipt, and audit commit in one atomic revision; stale writes and key reuse return RFC 9457 problems. | Industry Roles UI mutation pilot. No automatic client retry or local writer fallback. |

The private host's outer access perimeter owns the single human operator. The
bearer credential identifies only the Streamlit workload to FastAPI and is not
Codex/X authentication. Missing or malformed credential configuration disables
only the protected routes; missing optional initial override/suggestion files
are valid revision-zero state, while an existing corrupt canonical file remains
fail-closed and requires explicit recovery.

## Complete UI Inventory

| Streamlit page | Persisted inputs | API disposition | Evidence |
| --- | --- | --- | --- |
| 今日決策 | Market Thesis forecast; daily summary; scored/ranked candidates; options flow; validation summaries; reconciliation; performance ledger; reversal/oversold; candidate run status/history | Phase 4F makes ranked/scored candidate presentation API-only through two strict `/feed` projections. Phase 5L, 5O, and 5Q make the three Market Thesis/Reversal/Oversold validation trust cards API-only. Phase 5R, 5S, and 5T move only the Reversal/Oversold latest counts and Options Flow table to existing strict clients. Phase 5U reuses Market Thesis latest for the gate; Phase 5V/5W add and reuse one strict Daily Summary result for gate/opportunity references. Each selected read is fixed, exact-once, and has no local fallback. Quote fallback, candidate controls/writers/status, reconciliation, ledger, Trade State, providers, private daily prose, and mutations retain their prior boundaries. | `ui/today_decision.py`; `ui/_candidate_controls.py`; `ui/_read_api.py`; `api/models.py` |
| Trade State | Ranked candidates; X picks; options flow; Risk Guard; money flow; theme baskets; industry roles/overrides/suggestions | P2 aggregate. Exclude position-bearing Risk Guard rows until authenticated. | `ui/trade_state.py:114-117`; `scripts/trade_state.py:305-395,448-468` |
| 美股篩選 | Filtered universe; scored candidates; layer-2 and due-diligence results; dated summary; performance ledger | Phase 4S makes only the scored regime/count/card slice API-only through the strict `/candidates/scored/screener` projection. It exposes no `all_scored` REJECT rows or private technical/pipeline fields. Available-empty, unavailable, and client failure remain distinct; Layer 2 remains the regime fallback when the scored API is unavailable. Filtered universe, Layer 2, DD, dated reports, ledger, analyst detail, and actions remain local/provider siblings. | `ui/us_screener.py`; `ui/_read_api.py`; `api/models.py` |
| Options Flow | Latest options-flow snapshot | Phase 2J adds `GET /api/v1/signals/options-flow/feed`, an exact bounded projection that omits the source note, provider/raw-volume fields, spot, and unused biggest-contract fields while preserving fail-soft behavior. Phase 2K makes the standalone page's persisted ranked feed API-first, and Phase 3E makes it the fifth API-only UI slice. Phase 5A reuses the same strict feed for only the Schedules summary; Phase 5B reuses it for only standalone Options Cockpit quick picks; Phase 5T reuses it for the Today Decision table. Valid unavailable responses and every bounded client failure remain fail-soft without an in-process selected-source fallback. `response_too_large` preserves the 8 MiB retained decoded-body limit; this is not a hard process-memory, wire-byte, or HTTPX-decoder bound. The page's live ticker drill-down remains a direct provider; Trade State remains local. | `ui/options_flow.py`; `ui/sys_schedules.py`; `ui/options_cockpit.py`; `ui/today_decision.py`; `ui/_read_api.py`; `api/models.py` |
| 個股健檢 | Sector snapshots; retrospective factor/event/feature JSON | Phase 5K makes only the single-ticker sector-board presentation API-only. One typed board result is shared by the header chip and sector panel; unavailable/failure omits or explains only sector content. Batch mode, ticker-to-sector lookup, retrospective factors, live fundamentals/options, and every other tab remain local/provider siblings. | `ui/stock_checkup.py`; `ui/_read_api.py`; `api/models.py`; `scripts/live_factors.py` |
| Options Cockpit | IV history; money flow; watchlist; social/X picks; scored candidates; options flow; reconciliation; trade state | Phase 4O makes only the scored-candidate quick-pick source API-only. Phase 4Y/4Z make standalone/embedded Money Flow confirmation API-only, Phase 5B makes only standalone Options Flow quick picks API-only, and Phase 5E makes only the Cockpit-owned IV-history series and displayed Rank/Percentile projection API-only through one strict per-ticker read inside the existing 15-minute live-provider cache. Phase 5F makes only standalone Social quick picks API-only through one fixed Social read; it accepts US snapshots, never rereads Social latest locally, and preserves private IBKR plus legacy X picks as independent siblings. Valid empty/unavailable/failure states never fall back to migrated presentation JSON. `momentum_options` strategy verdict/checklist and recording, live chain, EDGAR, reconciliation, Trade State, demo fallback, session handoffs, and mutations remain independent local/private/provider siblings; embedded mode still does not load quick picks. | `ui/options_cockpit.py`; `ui/_read_api.py`; `api/models.py`; `scripts/iv_history.py` |
| 雷達 | Reversal, oversold, Risk Guard, COT, options-flow snapshots | Phase 4E makes Reversal persisted discovery and Oversold latest display API-only. Phase 5M adds the strict summary-only Oversold validation contract; Phase 5N makes its standalone/embedded forward-validation section API-only, requested only after an available latest snapshot reaches that section. Live Reversal/Risk Guard computation, position-bearing Risk Guard data, IBKR/provider work, session-state results, and Reversal forward validation remain outside these public slices. | `ui/radar.py`; `ui/oversold_reversal_lane.py`; `ui/_read_api.py`; `api/models.py` |
| IBKR 對帳 | `reports/reconciliation.json` | Internal only after identity and authorization. Reconcile/write actions are Deferred. | `ui/ibkr_reconcile.py:31-59,95-102,176-185,248-267` |
| 產業輪動 | AI analysis; dated sector snapshot; scored candidates; fixed sector-to-theme drill | Phase 4R makes the candidate-mapping seed API-only. Phase 5J makes the quantitative board API-only through one fixed strict Sector Rotation request with no local or live board fallback. Phase 6R makes only the fixed sector-to-theme drill API-only through one strict no-fallback request. The separate local AI read/generation mutation, ticker-to-sector provider, selection, and jumps remain siblings. | `ui/sector_rotation.py`; `ui/_read_api.py`; `api/models.py` |
| 題材資金流 | Theme analysis; theme snapshot; refresh status | Phase 4V makes only snapshot and current-validation analysis presentation API-only through two strict fixed clients. The snapshot projection excludes cache params, Eastmoney/source diagnostics, and unused computation fields; it adds the exact server board fingerprint. Analysis v8 must match that fingerprint or fails closed as stale. Background refresh/status, AI generation, insider overlay, sector mapping, and every mutation remain local/Internal siblings. | `ui/theme_flow.py`; `ui/_read_api.py`; `api/models.py`; `scripts/theme_flow_controls.py` |
| 美股 COT | Dated Markdown plus sibling verified JSON | Phase 6D adds strict server-enumerated catalog/detail GETs; Phase 6F makes persisted presentation API-only with one catalog and one selected detail read, bounded verified arithmetic/date/timestamp checks, and frontend Markdown sanitization. Codex auth, CFTC/yfinance retrieval, generation, logs, and atomic writes remain local/Deferred. | `ui/us_cot.py`; `ui/_read_api.py`; `api/models.py` |
| 市場展望 | Forecast archive; validation; regime history | Phase 4D makes the latest-forecast resolver API-only. Phase 5G adds a strict validation projection; Phase 5H adds an exact summary-only regime projection. Phase 5L reuses the validation result for only Today Decision's Market Thesis trust card. The 2.3 MiB daily corpus, runs, episodes, rules, VIX/benchmark telemetry, validation invalid/rejected records, configuration, and notes never enter public responses. Missing/invalid/oversized/client failures fail soft without local fallback. Writers and notifications remain unchanged. | `ui/market_thesis.py`; `ui/today_decision.py`; `ui/_read_api.py`; `api/models.py` |
| X 情緒－美股 | Persisted social intelligence or X-picks fallback; influencer roster | Phase 4T replaces only the refresh producer's ranked-candidate seed with one existing strict ranked-feed request. Phase 4U makes only the selected-market persisted Social snapshot presentation API-only; no local Social-latest fallback is allowed. Phase 6L moves the single-handle roster quick-pick to one strict roster API read and preserves manual entry when unavailable. Same-rerun refresh output and the separately persisted legacy X-picks compatibility source remain usable. Network, Codex/auth, AI-summary reads/writes, Options Flow, and every refresh mutation stay local/Deferred. | `ui/x_sentiment.py`; `ui/_read_api.py`; `api/models.py` |
| X 情緒－Crypto | Same social artifact filtered to Crypto | Same Phase 4T/4U contract; a latest snapshot for the other market is not rendered and may degrade to the independent legacy compatibility source. | Same as above |
| 復盤分析 | Fixed retrospective dataset bundles; continuation; playbook validation | Phase 5Y/5Z make Playbook Validation API-only; Phase 6A–6C make Continuation Validation API-only through a fixed strict request. Both project blocked states to safe public copy and never reread local latest after unavailable/failure. Other retrospective bundles, raw decision/outcome data, reasons, providers, and writers stay private. | `ui/retro_analysis.py`; `ui/playbook_validation.py`; `ui/continuation_validation.py`; `ui/_read_api.py`; `api/models.py` |
| Analytics DB | Read-only DuckDB tables; analytics health; data-health status | Phase 4I makes only the fundamental-refresh ranked ticker defaults API-only through the existing strict ranked feed, one request per rerun. Available-empty yields an empty default; unavailable/failure leaves manual ticker entry usable without local ranked fallback. DuckDB/Parquet reads, raw SQL, health/status, refresh commands, subprocesses, and all maintenance mutations remain local/Internal. | `ui/analytics_db.py`; `ui/_read_api.py`; `scripts/analytics_store.py` |
| Knowledge Graph | `knowledge/**/*.md` compiled into nodes/edges/diagnostics | Phase 6G–6I make the aggregate the fiftieth API-only slice. One bounded server traversal invokes the pure parser core; Streamlit receives a strict path/URL/body-free graph and never scans the vault after unavailable/client failure. Obsidian and writers remain local. | `ui/knowledge_graph.py`; `ui/_read_api.py`; `api/artifacts.py`; `scripts/knowledge_graph.py` |
| 美股期權 | Scored candidates; per-ticker IV history | Bounded IV history is implemented in Phase 2B. Phase 2I makes only the active single-ticker IV Rank chip API-first, and Phase 3D makes that the fourth API-only UI slice. Phase 4M additionally makes only the standalone candidate grid's scored-universe read API-only through one strict scored-feed request and corrects the canonical `WATCHLIST` / `NEEDS_LAYER_2` presentation. Every row's IV Rank/sparkline remains local, avoiding HTTP N+1; embedded `render_for()` and the live option chain remain unchanged. Both slices fail soft without local fallback to their migrated source. | `ui/us_options.py`; `ui/_read_api.py`; `scripts/iv_history.py` |
| 分析師觀點 | Scored candidates; live analyst provider data | Phase 4Q makes only the candidate grid seed API-only through one strict scored-feed request. The per-row and default-detail analyst provider calls remain local and cached; ad-hoc ticker detail stays usable for empty/unavailable/failure candidate states and embedded `render_for()` remains provider-only. | `ui/analyst_views.py`; `ui/_read_api.py`; `ui/_shared.py` |
| 機構持倉 | Static fund catalog; scored candidates; live EDGAR/yfinance holdings | Phase 2C/2H/3C make only the curated quick-pick catalog API-only. Phase 4H additionally makes the inverse holdings view's optional `institutional`/`verdict`/`key_signals` scored context API-only through one strict scored-feed request per rendered detail. Missing/failed score context never blocks yfinance/Form-4 provider results, manual/MAG7 lookup, embedded rendering, or SEC EDGAR 13F; the page as a whole is not API-backed. | `ui/institution_portfolio.py`; `ui/institutional_holdings.py`; `ui/_read_api.py`; `scripts/edgar_13f.py`; `scripts/institutional_free.py` |
| 產業角色 | Ranked candidates; protected review-board state/action; X picks | Phase 4N makes the ranked half of candidate seeding API-only. Phase 6V-6X moves board reads behind the protected API. Phase 6Y-7A adds ETag/If-Match, one atomic canonical aggregate, durable receipt/audit/backup, and API-only UI generate/review actions. Phase 7B converges Trade State, Money Flow, Universe Refresh, the scheduler, and compatibility commands on the canonical-first engine projection; invalid canonical state never falls back to stale legacy. Phase 7C adds explicit status/export/restore operations, and Phase 7D retains a no-delete `HOLD` gate pending operating-window and external-consumer evidence. X picks and ranked candidate partial-state behavior remain. | `ui/industry_roles.py`; `clients/private_api.py`; `api/industry_roles.py`; `scripts/industry_role_store.py`; `scripts/industry_roles.py`; `scripts/industry_role_admin.py`; `scripts/trade_state.py` |
| Watchlist 分類 | Static TradingView list; theme taxonomy; private IBKR/watchlist/reconciliation data | Phase 6J/6K make only the ordered public taxonomy the fifty-first API-only slice. Unavailable disables theme classification but leaves sector/list/IBKR siblings usable; no local taxonomy fallback. Private lists and all mutations remain Internal/Deferred. | `ui/watchlist_categorize.py`; `ui/_read_api.py`; `api/models.py` |
| Influencers | Runtime-resolved influencer roster | Phase 6J/6L publish a bounded allowlisted roster without GET-time seeding. The editor's initial read is the fifty-second slice and X quick-pick is the fifty-third; unavailable stops stale editor writes or falls back to manual handle input. Explicit roster writes, live lookup, providers, and approvals remain local. | `ui/influencers.py`; `ui/x_sentiment.py`; `ui/_read_api.py`; `scripts/influencer_roster_runtime.py` |
| 系統排程 | Schedules; report/ledger/reflection metadata; crypto/COT/options/candidates/money-flow/health/theme status | Phase 2E/2F/3B make the registry the second API-only slice. Later phases migrate selected result summaries; Phase 5X reuses Daily Summary for `report_dir`, and Phase 6E reuses the strict COT catalog for `cot`. Selected results are loaded once per result type and reused across duplicate visible cards; available-empty is authoritative where allowed, and unavailable/failure never invokes a selected local fallback. Ledger, reflection, Data Health, COT generation, Theme analysis/refresh/status, and other results/logs remain local/Internal. | `ui/sys_schedules.py`; `ui/_read_api.py`; `api/models.py` |
| AI 更新 | Static AI updates | P1 — implemented in Phase 2D as `GET /api/v1/system/ai-updates` with an exact public `updates` DTO. Phase 2G made the Streamlit consumer API-first. Phase 3A makes this the first API-only UI slice: valid unavailable responses and every bounded client failure remain fail-soft but never read the source artifact in-process. Phase 4B removes its transitive `_shared` dependency and freezes an L2 closure containing only the page, presentation module, fixed client, and public models. Source maintainer guidance remains validated and projected out; card layout, newest-first order, tag filtering, and optional links remain frontend behavior. | `ui/sys_ai_updates.py`; `ui/_components.py`; `ui/_read_api.py` |
| Crypto Universe | Universe JSON; TradingView TXT derived from validated DTO | P1 — implemented in Phase 4C as fixed `GET /api/v1/crypto/universe` with strict date, source/status, count, sorted/unique universe, diff, comparison, stale provenance, and `tv_symbol` invariants. The public DTO projects out `fetch_error` and duplicate raw `symbols`. The whole page is the sixth API-only slice: valid unavailable responses and bounded client failures never read local JSON/TXT, while the download is derived from validated `tv_symbol` rows. The writer remains unchanged. | `ui/crypto_universe.py`; `ui/_read_api.py`; `api/models.py` |
| Crypto Screener | `crypto_scored.json`, page still scaffolded | Deferred until the writer and schema are stable. | `ui/crypto_screener.py:13-24` |
| Global AI chat | Dynamic private sessions plus candidate/options/trade/risk context; LLM and web calls | Internal/Deferred until identity, ownership, retention, and model-call policies exist. | `app.py:157`; `ui/ai_chat.py:15-114,331-365`; `scripts/ai_chat_store.py:25-34,107-126` |

The fifty-four migrated API-only Streamlit slices—schedule registry, AI updates feed,
institutional fund quick-pick catalog, the active single-ticker IV Rank chip,
the standalone Options Flow persisted feed, and the complete Crypto Universe
page, Market Thesis latest, Reversal discovery, Oversold latest, and Today
Decision candidate presentation, plus the Schedules candidate ranked summary,
Institutional Holdings optional scored context, Analytics DB ranked
fundamental defaults, US Options scored grid, Industry Roles ranked seed, and
Options Cockpit scored quick picks, Analyst Views scored grid, Sector Rotation
candidate mapping, US Screener scored regime/count/cards, Schedules Money Flow
summary, standalone and embedded Options Cockpit Money Flow confirmation,
Schedules Options Flow summary, standalone Options Cockpit Options Flow quick
picks, Schedules Crypto Universe and Theme Flow summaries, Options Cockpit
IV-history and Social quick-pick presentation, Market Thesis validation/regime
summaries, standalone/Stock Checkup Sector Rotation boards, Today Decision's
Market Thesis trust card, the standalone/embedded Oversold validation
presentation, the Today Decision Oversold/Reversal validation trust cards,
the two Today Decision latest candidate-count cards, its Options Flow table,
Market Thesis gate, Daily Summary gate/opportunity presentation and Schedules
report card, the Playbook and Continuation Validation presentations in Retro
Analysis, the Schedules COT latest card, the COT persisted presentation,
Knowledge Graph, Watchlist taxonomy, the Influencer editor's initial roster,
X Sentiment's roster quick-pick, and the Sector Rotation theme drill—
intentionally call fixed
`127.0.0.1:8000` endpoints. They do not discover or trust an alternate port.
Phase 3A Docker Compose starts separate API and Streamlit services in one shared
network namespace. The API stays bound to loopback and port 8000 is not published,
so the existing loopback peer and Host checks remain unchanged. Streamlit starts
only after API health succeeds. Phase 3A made AI Updates API-only, Phase 3B made
the Schedules registry the second API-only slice, Phase 3C made Fund Catalog the
third, Phase 3D made the single-ticker IV Rank chip the fourth, Phase 3E made the
standalone Options Flow feed the fifth, Phase 4B removed AI Updates' transitive
backend coupling, and Phase 4C makes Crypto Universe the sixth and a complete
API-only page. Phase 4D makes Market Thesis latest the seventh **API-only**
slice. Phase 4E
makes Reversal discovery and Oversold latest the eighth and ninth API-only
slices while preserving live Radar, private Risk Guard, and local forward
validation. Phase 4F makes Today Decision ranked/scored presentation the tenth
slice through two additive strict feeds while retaining the two open
compatibility routes. None reads its migrated source artifact locally after a
client failure. Phase 4G, 4H, and 4I make the three additional narrow candidate
consumers the eleventh through thirteenth slices without changing the existing
routes, public DTOs, OpenAPI contract, providers, or maintenance/write paths.
Phase 4M, 4N, and 4O make the three additional narrow candidate consumers the
fourteenth through sixteenth slices without changing those API contracts or
absorbing their local IV, X, role-state, Options Flow, provider, or mutation
siblings. Phase 4Q and 4R make Analyst Views and Sector Rotation the seventeenth
and eighteenth slices through the existing strict scored feed while retaining
analyst and sector-provider fan-out. Phase 4S adds the closed screener projection
and makes its scored regime/count/card read the nineteenth slice; its other five
tabs and all mutations remain local. Phase 4T makes the X refresh ranked seed
the twentieth slice, Phase 4U makes persisted Social presentation the
twenty-first, and Phase 4V makes Theme Flow snapshot/analysis presentation the
twenty-second. Phase 4W adds the strict Money Flow contract; Phase 4X makes the
Schedules Money Flow summary the twenty-third slice, Phase 4Y makes standalone
Options Cockpit external confirmation the twenty-fourth, and Phase 4Z makes the
embedded confirmation the twenty-fifth. Phase 5A makes the Schedules Options
Flow summary the twenty-sixth; Phase 5B makes standalone Options Cockpit Options
Flow quick picks the twenty-seventh. Phase 5C and Phase 5D make the Schedules
Crypto Universe and Theme Flow summaries the twenty-eighth and twenty-ninth;
Phase 5E makes the Cockpit-owned IV-history presentation the thirtieth. Phase
5F makes standalone Cockpit Social quick picks the thirty-first; Phase 5G and
Phase 5H make Market Thesis validation and regime summaries the thirty-second
and thirty-third. Phase 5I adds the strict Sector Rotation contract; Phase 5J
and Phase 5K make the standalone and Stock Checkup quantitative boards the
thirty-fourth and thirty-fifth slices. Phase 5L makes Today Decision's Market
Thesis trust card the thirty-sixth slice; Phase 5M adds the strict Oversold
validation contract and Phase 5N makes its standalone/embedded presentation the
thirty-seventh. Phase 5O reuses the Oversold contract for Today Decision's
thirty-eighth slice; Phase 5P adds the strict Reversal validation contract and
Phase 5Q makes its Today Decision trust card the thirty-ninth. Phase 5R and
Phase 5S reuse the strict latest snapshots for Today Decision's
fortieth and forty-first candidate-count cards; Phase 5T reuses the strict
Options Flow feed for its forty-second table slice. Phase 5U reuses Market
Thesis latest for Today Decision's forty-third gate slice; Phase 5V adds the
strict Daily Summary contract and Phase 5W makes its one-result gate/opportunity
consumer the forty-fourth slice. Phase 5X reuses that result for the Schedules
report card as the forty-fifth slice; Phase 5Y adds the strict Playbook
Validation contract and Phase 5Z makes its Retro Analysis presentation the
forty-sixth slice. Phase 6A–6C add the strict Continuation contract/client/page
as the forty-seventh slice; Phase 6D adds the strict COT catalog/detail
contracts, Phase 6E makes the Schedules COT card the forty-eighth slice, and
Phase 6F makes the COT persisted presentation the forty-ninth. Phase 6G–6I add
the bounded path-free `GET /api/v1/knowledge/graph` contract
and make Knowledge Graph the fiftieth API-only slice. Phase 6J–6L add fixed
public theme-taxonomy and Influencer-roster projections; Watchlist taxonomy is
the fifty-first slice, the Influencer editor's initial read is the fifty-second,
and X Sentiment's single-handle quick-pick is the fifty-third. The public roster
GET never seeds or writes; systemd gives API and Streamlit the same shared
runtime roster path, while explicit edits and every live/provider path remain
local. Phase 6M–6O audit the remaining bindings and accept only the fixed
sector-to-theme reverse map; Phase 6P–6R add its strict projection/client and
make the Sector Rotation drill the fifty-fourth slice. Basket tickers,
descriptions, representative hints, Theme Flow providers, and the source stay
server-owned. Trade State, the
`momentum_options` strategy provider, other live providers,
compatibility sources, refresh/status/actions, and writers remain local/Internal. Phase 4P closes the
user-systemd startup gap: Streamlit now declares
both `After=... surge-screener-api.service` and
`Requires=surge-screener-api.service`, while the existing deploy gate still
health-checks API before restarting Streamlit and the loopback trust boundary
is unchanged.
The IV, Options Flow, and Crypto Universe response-too-large states stay
fail-soft and do not re-read the same unbounded local source. Manual CIK, direct
SEC EDGAR/yfinance providers, and the live options chain remain independent of
these read boundaries.

For Options Flow, the standalone page, Schedules summary, standalone Options
Cockpit quick picks, and Today Decision table reuse the same strict persisted
feed boundary. A valid
unavailable envelope is authoritative; transport, deadline,
HTTP status, media type, cache-control, size, and envelope failures remain
unavailable without an in-process artifact read. The live-chain drill-down
remains a cached direct provider call. Trade State and any unselected Options
Flow artifact consumers remain local.

## Phase 2 Bounded Reads

These remain compatible with the same envelope and registry model, but should be implemented only after the Phase 1 contract is stable:

- Dated daily-report list/detail.
- Strict COT catalog/detail — implemented in Phase 6D as
  `GET /api/v1/reports/cot` and `GET /api/v1/reports/cot/{report_date}`. The
  catalog returns at most 520 exact dates; detail requires one complete bounded
  Markdown/verified pair and validates position arithmetic, OHLC/ranges,
  report/as-of dates, stale parity, Tuesday/Friday delta, and audit timestamp.
  Phase 6E reuses the catalog once for duplicate Schedules cards; Phase 6F uses
  one catalog and one detail request for persisted presentation and sanitizes
  Markdown before rendering. Auth, provider retrieval, generation, logs, and
  atomic writes remain local.
- Per-ticker IV history with a strict ticker validator — implemented in Phase 2B
  as `GET /api/v1/options/iv-history/{ticker}` with a `ticker`/`series` public DTO.
  Phase 2I makes only the active single-ticker IV Rank chip API-first, and Phase
  3D makes it the fourth API-only slice: failures never trigger an in-process
  artifact read. Phase 5E reuses the same fixed endpoint for only the
  Cockpit-owned IV-history presentation and applies the shared pure calculation
  to validated points inside the existing 15-minute cache. Candidate grid rows,
  `momentum_options` strategy/provider behavior, the shared pure calculation,
  and IV writers remain unchanged.
- Strict Options Flow feed projection — implemented in Phase 2J as
  `GET /api/v1/signals/options-flow/feed`. It shares the fixed source file with
  the source-preserving `/latest` compatibility route, but returns an exact
  bounded DTO and treats missing, partial, malformed, unreadable, or invalid
  source data as HTTP 200 unavailable. Phase 2K makes the standalone page's
  persisted feed API-first. Phase 3E makes it the fifth API-only slice; Phase 5A
  reuses it for the Schedules summary, Phase 5B for standalone Cockpit quick
  picks, and Phase 5T for the Today Decision table. All unavailable and bounded
  client-failure outcomes remain fail-soft
  without an in-process selected-source read. The live chain, Trade State, and
  unselected consumers remain local or direct-provider reads.
- Strict Crypto Universe projection — implemented in Phase 4C as fixed
  `GET /api/v1/crypto/universe`. The registry validates the exact raw source
  shape, then publishes only the bounded universe/diff/provenance DTO. Streamlit
  treats valid unavailable and every bounded client failure as authoritative;
  it never reads the local JSON or prebuilt TXT, and derives the TradingView
  export from validated `tv_symbol` rows. The existing writer is unchanged.
- Strict Market Thesis projections — latest was implemented in Phase 4D on the
  existing fixed `GET /api/v1/market-context/market-thesis/latest`. It preserves
  date-first and ready-over-regime-only same-day resolution, publishes only the
  bounded presentation/provenance DTO. Phase 5G adds fixed validation with only
  counters and at most 27 full-key hit-rate rows. Phase 5H adds fixed summary-only
  regime history with exactly nine forward windows and a 128 KiB client cap;
  raw daily/runs/episodes/rules/VIX data never crosses the boundary. All three
  page resolvers are API-only without local fallback. Writers, notification
  gates remain local; Phase 5L reuses validation only for Today Decision's
  Market Thesis trust card, and Phase 5U reuses latest once for its market gate.
- Strict Daily Summary latest projection — implemented in Phase 5V as fixed
  `GET /api/v1/reports/daily-summary/latest` with a 128 KiB client cap. It
  selects only the newest exact real-date report directory, validates the full
  canonical or known watchlist source root, binds `report_date` to the selected
  folder, and publishes only date, bounded regime text, and ordered unique
  ticker/verdict references. A missing, malformed, mismatched, or symlinked
  selected source is authoritative unavailable with no older fallback. Phase
  5W resolves it once per Today Decision rerun and reuses the same result for
  gate and opportunities; Phase 5X reuses the contract once for the Schedules
  `report_dir` card and its duplicate-card cache. Private thesis/entry/stop/size/risk/watchlist/prose,
  report writers, reconciliation, ledger, Trade State, and controls remain on
  their prior boundaries.
- Strict Playbook Validation latest projection — implemented in Phase 5Y as
  fixed `GET /api/v1/reports/playbook-validation/latest` with a 128 KiB client
  cap. The registry validates the complete exact blocked or active producer
  family, maturity/count partitions, sorted unique labels, finite statistic
  pairs, and row verdicts before publishing only timestamp, status, displayed
  counts, and bounded playbook/factor rows. Phase 5Z resolves it once in the
  Retro Analysis Playbook lane. Raw blocked reason, outcome count, decisions,
  outcomes, paths, providers, and writers remain private. Phase 6A adds the
  parallel fixed `GET /api/v1/reports/continuation-validation/latest` contract
  with a 4 MiB client cap; Phase 6C resolves it once in Retro Analysis while
  projecting blocked diagnostics and producer notes out. Other retrospective
  datasets stay local.
- Strict Reversal/Oversold projections — latest snapshots were implemented in Phase 4E on the
  existing fixed signal GETs. Reversal publishes only snapshot provenance and
  source-ordered unique ticker references used to seed the live dual read.
  Oversold publishes only the bounded coiled-base headline, validation summary,
  caveats, and table fields. Their `latest.json` reads are API-only; live Radar,
  position-bearing Risk Guard, providers, session state, and writers remain
  unchanged. Phase 5R and Phase 5S reuse only the strict `match_count` fields for
  Today Decision's latest cards. Phase 5M adds fixed
  `GET /api/v1/signals/oversold-reversal/validation`: it validates the complete
  producer root but publishes only conservative counts, verdict, and three
  ordered hit-rate/Wilson rows with a 32 KiB client cap. Phase 5N moves only the
  Oversold standalone/embedded forward-validation presentation to that client;
  private EV/equity/survivorship/cohort data, and all forward writers stay
  local/Internal. Phase 5P adds the parallel fixed
  `GET /api/v1/signals/reversal-radar/validation` contract using Reversal's
  legacy resolved-row publication semantics and a 32 KiB client cap; Phase 5O
  and Phase 5Q move the two Today Decision validation trust cards to their
  strict clients.
- Strict Money Flow latest projection — implemented in Phase 4W as fixed
  `GET /api/v1/market-context/money-flow/latest`. The registry validates exact
  producer roots, coverage arithmetic, publishability, resolved ticker counts,
  unique dates, timestamp/date provenance, source identity, and finite values,
  while projecting out `secid`, `raw_row`, close/change diagnostics, and unused
  detailed flow fields. Phase 4X adopts it only in the Schedules candidate
  summary, Phase 4Y in standalone Options Cockpit external confirmation, and
  Phase 4Z in the embedded confirmation. Trade State remains local for separate
  review.
- Strict Sector Rotation latest projection — implemented in Phase 5I as fixed
  `GET /api/v1/market-context/sector-rotation/latest`. It selects only the
  lexicographically newest exact calendar-dated archive and fails soft on that
  selected file instead of falling back to an older snapshot or live provider.
  Phase 5J and Phase 5K adopt the allowlisted quantitative board in standalone
  Sector Rotation and single-ticker Stock Checkup. Macro/leader lists, producer
  status, local AI read/generation, ticker mapping provider, and mutations stay
  private or on their existing boundaries.
- Fixed sector-to-theme drill — implemented in Phase 6P–6R as
  `GET /api/v1/market-context/theme-drill`. It projects only the sorted parent
  SPDR sectors and source-ordered theme names needed by the Sector Rotation
  jump UI. Root notes, descriptions, ticker membership, representative hints,
  paths, provider/cache behavior, and writes stay private/local; unavailable or
  client failure hides only the optional drill and never triggers a local read.
- Retrospective bundle with a fixed dataset enum.
- Today Decision and Trade State server-side aggregates.
- Knowledge Graph compiled snapshot — implemented in Phase 6G–6I as fixed
  `GET /api/v1/knowledge/graph`. The server performs one symlink-rejecting,
  entry/directory/card/byte-capped vault traversal, calls a pure parser core,
  and publishes at most 500 nodes, 5,000 edges, and 1,000 unresolved links.
  Paths, URLs, bodies, frontmatter, tags, filenames, and duplicate-ID graphs do
  not cross the boundary. The Streamlit page performs one bounded client read
  with no local compiler fallback.
- DuckDB catalog and selected public tables through `fetch_table()` only, with explicit column/filter/limit contracts.
- Static fund catalog — implemented in Phase 2C as
  `GET /api/v1/institutions/funds` with an exact public `funds` DTO; the source
  `_note` is validated and projected out. Phase 2H makes the Streamlit quick-pick
  consumer API-first, and Phase 3C makes it the third API-only slice: unavailable
  envelopes and every bounded client failure remain fail-soft without a local
  catalog read. Manual CIK remains available. This does not migrate SEC EDGAR or
  yfinance holdings reads.
- Public theme taxonomy and Influencer roster — implemented in Phase 6J–6L as
  fixed `GET /api/v1/watchlists/theme-taxonomy` and
  `GET /api/v1/social/influencers`. Both publish strict bounded projections and
  omit root notes/paths. Watchlist/IBKR/reconciliation/classification-provider
  reads, roster lookup/edit/approval/writers, live social providers, and
  credentials remain local/Internal. Industry-role state now uses its separate
  protected read/action contract; other fixed text downloads remain deferred
  pending a later reviewed contract.

## Explicit Denylist

The API must not expose or accept any of the following without a separately reviewed authenticated design:

- `reports/reconciliation.json`, `reports/watchlist.json`, portfolio positions, or position-bearing Risk Guard rows.
- AI chat sessions, reflections, authentication logs, job logs, command lines, absolute paths, or environment values.
- Arbitrary filesystem paths, filename fragments, glob expressions, URLs, SQL, table names outside an allowlist, raw DuckDB files, or raw Parquet files.
- Provider credentials, IBKR sessions, order actions, or unreviewed refresh/generation/approval/file-write surfaces. The exact protected Industry Roles action route is the sole current reviewed exception.
- Streamlit `session_state`; ticker/filter state belongs in frontend URL or client state.

## Known Source Gaps

- `ui/_shared.load_ledger()` calls `pandas.read_csv()` without fail-soft handling (`ui/_shared.py:291-305`). A future ledger endpoint must catch missing, parser, encoding, and shape errors.
- Knowledge Markdown writers and local tooling still use the compatibility
  `build_graph(vault)` entry point, but the public API no longer delegates to
  it: the bounded adapter selects and reads cards once before invoking the pure
  parser/build core.
- `scripts/risk_guard.py:47-52` reads repo-root `scored_candidates.json`, while most consumers use `candidate_output_dir()`. This inconsistency must be resolved before exposing a Risk Guard aggregate.
- Money Flow and Universe Refresh have converged on the Industry Roles engine's
  canonical-first approved-ticker projection. The only legacy filename owners
  are the legal revision-zero seed/API wiring and the explicit compatibility
  export. Retirement remains `HOLD` until a real operating window and an
  out-of-repository consumer attestation are recorded.
- Deployment symlinks report/content paths to shared storage (`scripts/deploy_test_server.sh:230-271`). Containment must use a fixed registry plus configured allowed roots, not a blanket requirement that the resolved path remain inside the release directory.

## Decision

The public endpoint inventory remains loopback-only and accepts no
client-controlled paths. The selected deployment is a single-user private host;
Phase 6V-6X adds one route-scoped internal service credential without treating
provider login as application identity or publishing the API port.

Phase 6S-6U freezes the post-6R convergence ceiling at 61 direct backend
bindings across 20 UI modules, 30 `_shared` importers, 14 modules / 20
`load_json` calls, 10 modules / 19 direct filesystem/database-style calls, and
54 API-only presentation slices. The static guard permits those residual counts
to shrink and rejects growth. No further public artifact GET is selected.

Phase 6Y-7A implements the protected Industry Roles mutation pilot. The UI now
uses one fixed action endpoint with no local fallback. Revision/ETag,
`If-Match`, durable idempotency, atomic commit, bounded audit, backup/explicit
restore, crash tests, and release-independent persistence are implemented.
Phase 7B-7D implement canonical reader convergence, locked detectable legacy
export, machine-readable status, conditional restore preview/apply, and a
static no-delete retirement gate. Repository direct readers are converged, but
the honest retirement verdict remains `HOLD`: deployment operating-window and
external-consumer evidence require later authorized operational work.
