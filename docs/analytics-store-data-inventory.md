# Analytics Store Data Inventory

DuckDB is the platform's read model for cross-date analytics. JSON/CSV reports
remain the write source of truth; exporters flatten stable history-shaped
artifacts into queryable tables.

## Tables In DuckDB

| Table | Source | Grain | Why it helps |
| --- | --- | --- | --- |
| `performance_ledger` | `reports/performance_ledger.csv` | one ticker per scan date | Forward performance review, hit-rate checks, score/result attribution. |
| `iv_history` | `reports/iv_history/*.json` | one ticker per IV snapshot date | IV Rank, option cockpit trend lines, volatility regime checks. |
| `options_flow_signals` | `reports/options_flow/YYYY-MM-DD.json` | one option-flow signal per ticker/date | Track repeated unusual-flow names, notional size, call/put bias, and follow-through. |
| `reversal_radar_signals` | `reports/reversal_radar/scan_*.json` | one reversal candidate per ticker/date | Backtest and audit the validated/turning radar lane across days. |
| `oversold_reversal_signals` | `reports/oversold_reversal/scan_*.json` | one oversold/coiled-base candidate per ticker/date | Track exploratory lane candidates and later realized outcomes. |
| `market_thesis_forecasts` | `reports/market_thesis/*forecast_YYYY-MM-DD.json` | one market thesis forecast per date | Compare regime forecast direction against later market movement. |
| `candidate_scores` | `reports/candidate_scores/YYYY-MM-DD.json` | one scored candidate per ticker/date | Accumulate all scored candidates, not only confirmed BUY picks, so validation can reach useful sample sizes. |
| `candidate_rankings` | `reports/candidate_rankings/YYYY-MM-DD.json`; fallback `ranked_candidates.json` when the same date has no snapshot | one deterministic ranked candidate per ticker/date | Query why a ticker ranked high, compare rank bucket drift over time, and power Today Decision history. |
| `risk_guard_rows` | `reports/risk_guard/YYYY-MM-DD.json`; fallback `reports/risk_guard/latest.json` when the same date has no snapshot | one Risk Guard row per ticker/date | Compare risk actions across holdings/watchlist, detect repeated REDUCE/EXIT warnings, and review exposure before adding risk. |
| `portfolio_positions` | `reports/reconciliation.json` | one underlying per IBKR reconciliation bucket | Position-aware analytics: matched holdings, ledger picks not held, held-not-in-ledger drift, leg counts, P&L, and stale holdings. |
| `theme_flow_snapshots` | `reports/theme_flow_snapshots/YYYY-MM-DD.json`; fallback `reports/theme_flow_snapshot.json` when the same date has no snapshot | one theme per snapshot date | Track historical theme money-flow proxy, insider-overlay context, concentration, and parent-sector bridge instead of latest-only UI. |
| `sector_rotation_snapshots` | `reports/sector_rotation_snapshots/YYYY-MM-DD.json`; fallback `reports/sector_rotation.json` when the same date has no snapshot | one sector/theme ETF per snapshot date | Track sector quadrant, RS-Ratio, RS-Momentum, heat, macro read, and leader/improving ranks so candidates can be reviewed against broad rotation context. |
| `validation_summaries` | `reports/*/validation_summary.json` | one validator summary per signal/forecast lane | Query runway status, sample sizes, maturity gates, dropped-row provenance, survivorship caveats, and validator health without expanding every tier. |
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

## Next High-Value Tables

| Candidate table | Source | Priority | Platform use |
| --- | --- | --- | --- |
| `daily_reports` | `reports/YYYY-MM-DD/summary.json` | Medium | Searchable daily report archive and portfolio notes. Current samples have empty ranked picks, so value depends on future report population. |
| `watchlist_sources` | `reports/watchlist.json`, `content/us_watchlist.txt` | Low | Helps dedupe and explain why a ticker is visible, but it is more operational state than analytics. |

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
