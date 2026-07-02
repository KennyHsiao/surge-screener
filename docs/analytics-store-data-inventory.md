# Analytics Store Data Inventory

DuckDB is the platform's read model for cross-date analytics. JSON/CSV reports
remain the write source of truth; exporters flatten stable history-shaped
artifacts into queryable tables.

## External Market Data Sources

The platform can use several free/no-key data sources, but each source must stay
behind an adapter and publish only normalized, provenance-tagged artifacts.

| Source | Intended use | Persistence rule |
| --- | --- | --- |
| Eastmoney push2 | US/HK universe lists, search/secid mapping, quote fallback | Persist curated universe/identifier snapshots; cache quote fallback only. |
| Eastmoney push2his | Daily money-flow rows: main/super-big/big/mid/small net flow | Persist only normalized daily money-flow artifacts with coverage/status fields. |
| Eastmoney datacenter/GMAIN | Chinese-friendly statement rows and key metrics | Persist selected metrics as long-form `fundamental_metrics`; do not create wide statement tables. |
| Sina Finance | US long-history daily bars and quote fallback | Persist daily bars only after adjustment/source-quality flags are explicit; cache quote fallback only. |
| Tencent Finance | Quote fallback with broad quote fields | Cache only unless the value is embedded in a formal signal snapshot. |
| Yahoo/yfinance | Options chain, analyst data, existing fundamentals, adjusted OHLCV | Continue as primary where already used; persist only snapshots/signals needed for validation. |
| SEC EDGAR | CIK mapping, filings, Form 4, XBRL companyfacts | Persist normalized official events and metrics; respect User-Agent/rate-limit etiquette. |

Raw provider responses are not first-class analytics data unless a stable query
pattern exists. Store scalar columns for common filters/sorts, keep source detail
in `*_json` fields only when it is needed for auditability, and always include
`source`, `as_of_date` or `generated_at`, and a data-quality/status field.

## Tables In DuckDB

| Table | Source | Grain | Why it helps |
| --- | --- | --- | --- |
| `security_master` | latest `reports/universe/YYYY-MM-DD.json` | one active security per ticker | Current tradable universe, exchange/asset-type metadata, and primary identifiers for ticker validation. |
| `security_identifiers` | latest `reports/universe/YYYY-MM-DD.json` | one provider identifier per ticker/provider | Maps platform tickers to Eastmoney secid and SEC CIK so data-source adapters do not duplicate mapping logic. |
| `universe_snapshots` | `reports/universe/YYYY-MM-DD.json` | one ticker per universe snapshot date | Tracks universe coverage, SEC mapping coverage, and ticker availability drift across refreshes. |
| `daily_bars` | `reports/market_data/daily_bars/*.parquet` | one OHLCV bar per ticker/date/source policy | Price-history read model for Cycle, CE, Risk Guard, backtests, and long-history cross-source validation. |
| `daily_money_flow` | `reports/money_flow/YYYY-MM-DD.json` | one Eastmoney money-flow row per ticker/flow date | Stores source-defined main/super-big/big/mid/small net-flow evidence with coverage/publishable status for theme flow and trade-state review. |
| `fundamental_metrics` | `reports/fundamentals/YYYY-MM-DD.json` | one normalized SEC/Eastmoney metric per ticker/period/source | Official SEC companyfacts plus lower-confidence Eastmoney GMAIN rows for DD, factor research, source-conflict review, and Chinese-friendly fundamentals display without a wide sparse statement table. |
| `industry_role_assignments` | `reports/industry_roles/YYYY-MM-DD.json` | one displayable approved/suggested role assignment per ticker/date | Query which role tag should appear beside a ticker, distinguish approved vs suggested tags, and audit evidence/taxonomy version without reading review JSON manually. |
| `performance_ledger` | `reports/performance_ledger.csv` | one ticker per scan date | Forward performance review, hit-rate checks, score/result attribution. |
| `iv_history` | `reports/iv_history/*.json` | one ticker per IV snapshot date | IV Rank, option cockpit trend lines, volatility regime checks. |
| `options_flow_signals` | `reports/options_flow/YYYY-MM-DD.json` | one option-flow signal per ticker/date | Track repeated unusual-flow names, notional size, call/put bias, and follow-through. |
| `reversal_radar_signals` | `reports/reversal_radar/scan_*.json` | one reversal candidate per ticker/date | Backtest and audit the validated/turning radar lane across days. |
| `oversold_reversal_signals` | `reports/oversold_reversal/scan_*.json` | one oversold/coiled-base candidate per ticker/date | Track exploratory lane candidates and later realized outcomes. |
| `market_thesis_forecasts` | `reports/market_thesis/*forecast_YYYY-MM-DD.json` | one market thesis forecast per date | Compare regime forecast direction against later market movement. |
| `candidate_scores` | `reports/candidate_scores/YYYY-MM-DD.json` | one scored candidate per ticker/date | Accumulate all scored candidates, not only confirmed BUY picks, so validation can reach useful sample sizes. |
| `candidate_rankings` | `reports/candidate_rankings/YYYY-MM-DD.json`; fallback `ranked_candidates.json` when the same date has no snapshot | one deterministic ranked candidate per ticker/date | Query why a ticker ranked high, compare rank bucket drift over time, and power Today Decision history. |
| `candidate_outcomes` | `reports/candidate_outcomes/YYYY-MM-DD.json` | one no-LLM paper outcome per deterministic ranked candidate/date | Analytics / DB paper validation for ranking quality: track top-N candidate forward returns even when no formal confirmed picks are published, without polluting `performance_ledger`. |
| `risk_guard_rows` | `reports/risk_guard/YYYY-MM-DD.json`; fallback `reports/risk_guard/latest.json` when the same date has no snapshot | one Risk Guard row per ticker/date | Compare risk actions across holdings/watchlist, detect repeated REDUCE/EXIT warnings, and review exposure before adding risk. |
| `portfolio_positions` | `reports/reconciliation.json` | one underlying per IBKR reconciliation bucket | Position-aware analytics: matched holdings, ledger picks not held, held-not-in-ledger drift, leg counts, P&L, and stale holdings. |
| `trade_state_snapshots` | `reports/trade_state/YYYY-MM-DD.json` | one ticker per trade-state snapshot date | Reconstruct why a ticker was holding/take-profit/stop-loss using Cycle, CE, risk, industry role, money-flow, options-flow, and social evidence. |
| `theme_flow_snapshots` | `reports/theme_flow_snapshots/YYYY-MM-DD.json`; fallback `reports/theme_flow_snapshot.json` when the same date has no snapshot | one theme per snapshot date | Track historical theme money-flow proxy, optional Eastmoney money-flow evidence, insider-overlay context, concentration, and parent-sector bridge instead of latest-only UI. |
| `sector_rotation_snapshots` | `reports/sector_rotation_snapshots/YYYY-MM-DD.json`; fallback `reports/sector_rotation.json` when the same date has no snapshot | one sector/theme ETF per snapshot date | Track sector quadrant, RS-Ratio, RS-Momentum, heat, macro read, and leader/improving ranks so candidates can be reviewed against broad rotation context. |
| `validation_summaries` | `reports/*/validation_summary.json` | one validator summary per signal/forecast lane | Query runway status, sample sizes, maturity gates, dropped-row provenance, survivorship caveats, and validator health without expanding every tier. |
| `daily_reports` | `reports/YYYY-MM-DD/summary.json` | one daily report per date | Searchable daily report archive, confirmed-pick counts, top tickers, market summary text, and portfolio notes without opening each report folder. |
| `watchlist_sources` | `reports/watchlist.json`, `content/us_watchlist.txt` | one ticker per additive watchlist source | Explain why a ticker is visible, dedupe manual and IBKR scanner sources, and review source provenance from Analytics DB. |
| `signal_outcomes` | `reports/options_flow/validation_summary.json`, `reports/reversal_radar/validation_summary.json`, `reports/oversold_reversal/validation_summary.json` | one validation tier per signal lane | Query resolved counts, hit rates, EV, and maturity gates from forward validators. |
| `run_status_history` | `reports/run_status/candidates-local-history.jsonl` | one terminal local candidate run per JSONL row | Operational dashboard for refresh duration, failed stages, output counts, and reliability. |

The signal exporters intentionally skip `latest.json` when dated files exist, so
the tables do not double-count the current day.

## Automated Checks

`scripts/analytics_checks.py` validates the DuckDB read model after refresh and
publishes `reports/analytics_checks/latest.json`. The report is not a DuckDB
table; it is the operational decision layer that tells the UI whether the DB is
usable today and what follow-up action is recommended.

See `docs/analytics-checks-automation.md` for the check/action matrix.

## Data Health Refresh Ownership

| Source | Automatic path | Manual path | Notes |
| --- | --- | --- | --- |
| Core source artifacts (`universe`, `daily_bars`, `money_flow`, `trade_state`, `industry_roles`) | Test-server deploy schedule + candidate pipeline post-run refresh | Data Health -> 刷新核心 Source + 重建 DB | Required for 今日訊號 unblock. |
| Fundamentals | None by default | Data Health -> 刷新基本面 | Low-frequency, ticker-scoped. |
| Theme Flow verified snapshot | Theme Flow page background refresh; optional Data Health action | Data Health -> 刷新主題資金流 | Does not run AI read. |
| Sector Rotation verified snapshot | Scheduled deploy imports existing snapshots; Data Health can write a non-LLM verified snapshot | Data Health -> 刷新板塊輪動快照 | AI read remains explicit. |
| Risk Guard | None by default | Risk Guard page -> 掃描風險 | Manual scan writes dated snapshots and refreshes analytics. |
| IBKR positions | None | IBKR 對帳 page | Requires local Gateway/TWS. |

## Next High-Value Tables

No remaining first-class table is pending from the current high-value list.
Future candidates should be added here only after there is a concrete query or
UI workflow that needs them.

## Not First-Class DuckDB Data Yet

| Source | Reason |
| --- | --- |
| `reports/.cache/**` | Cache implementation detail; TTL and partial failures should not become analytics truth. |
| `reports/retrospective/control_features.json` | Large derived feature matrix. Useful for research, but should be modeled separately after deciding feature grain and columns. |
| `reports/**/full.json` | Complete dumps are nested and unstable; keep as source files until a concrete query pattern needs them. |
| Markdown reports | Human-readable narrative. Store metadata first; full text only if search becomes a platform feature. |
| Auth/session/status secrets | Should stay out of analytics DB. |

## Modeling Rules

- Prefer append/history-shaped artifacts over single latest-state files.
- Keep scalar columns for common filters and sort keys: `ticker`, date, verdict/status, score, source.
- Preserve nested source detail in `*_json` columns until the query pattern justifies splitting it out.
- Do not import `latest.json` as a separate historical row when a dated file exists.
- Materialize DuckDB base tables so DataGrip/remote reads do not depend on Parquet relative paths.

## Options-Flow Forward Validation

`scripts/options_flow_forward.py` runs after the unusual options-flow scan. It
reads only dated `reports/options_flow/YYYY-MM-DD.json` snapshots, skips
`latest.json`, and writes `reports/options_flow/validation_summary.json`.

The validator measures underlying follow-through for three exploratory tiers:
`+5%/10d`, `+10%/20d`, and `+15%/40d`. Bullish signals require upward closes;
bearish signals require downward closes and store a direction-adjusted horizon
return. The output remains `PROVISIONAL` until each tier reaches 100 resolved
entries.

## Candidate Paper Outcomes

`scripts/candidate_outcomes.py` is the no-LLM validation path for deterministic
rankings. The scheduled `candidate_outcomes` workflow runs after the US close,
builds a fresh hard-filter + `03_rank_candidates.py` top-20 snapshot with
`--options-gate-limit 0`, then updates `reports/candidate_outcomes/YYYY-MM-DD.json`.

For each scan date, the script aligns outcomes to the current top-N ranking
snapshot instead of accumulating stale tickers from same-day reruns. It preserves
existing outcome fields for tickers still in that top-N set, records entry price
from the ranking snapshot, and only fetches price data when a 7/14/30/60D window
has matured. These rows are paper validation data and must not be merged into
`performance_ledger`, which remains reserved for formal confirmed picks.
