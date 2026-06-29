# Schema Notes

## 2026-06-30 DuckDB Analytics Read Model

- DuckDB remains a read model. Existing JSON/CSV files under `reports/` remain
  the write source of truth.
- Tables are materialized as DuckDB base tables from Parquet exports so remote
  readers are not dependent on local Parquet paths.
- Current analytics tables:
  - `performance_ledger`
  - `iv_history`
  - `options_flow_signals`
  - `reversal_radar_signals`
  - `oversold_reversal_signals`
  - `market_thesis_forecasts`
- Signal tables use ticker/date/source scalar columns for filtering and keep
  nested source details in `*_json` columns until query patterns justify
  normalization.
- Exporters skip `latest.json` when dated scan files are present to avoid
  double-counting the same day.
- `refresh_all()` writes all Parquet exports first, then materializes DuckDB
  tables once. `query()` is read-only and does not refresh tables.
- `scripts/analytics_checks.py` is the automated validation layer. It reads the
  DuckDB file in read-only mode, publishes
  `reports/analytics_checks/latest.json`, and classifies results as
  `PASS` / `WARN` / `BLOCK` with follow-up actions.
- Unresolved next-modeling candidates are documented in
  `docs/analytics-store-data-inventory.md`.

## 2026-06-30 Candidate Scores And Signal Outcomes

- Added `candidate_scores` as a derived DuckDB table from
  `reports/candidate_scores/YYYY-MM-DD.json`. The source snapshot is written by
  the daily screener workflow immediately after `scored_candidates.json` is
  produced, so validation can accumulate all scored candidates instead of only
  confirmed BUY ledger rows.
- Added `signal_outcomes` as a tier-level read model from published forward
  validator summaries:
  - `reports/options_flow/validation_summary.json`
  - `reports/reversal_radar/validation_summary.json`
  - `reports/oversold_reversal/validation_summary.json`
- `signal_outcomes` intentionally stores aggregate tier outcomes first
  (`resolved`, `hits`, `hit_rate`, EV, maturity) and keeps raw outcome JSON for
  later normalization. Per-ticker/per-signal realized outcomes remain a future
  model once the UI needs drill-down from aggregate outcomes to individual
  signal histories.
- `candidate_scores` and `signal_outcomes` are maturity/validation tables. Empty
  row counts produce `WARN/REVIEW_REQUIRED`, not `BLOCK_TODAY_SIGNALS`.

## 2026-06-30 Options-Flow Outcomes In Existing Signal Table

- Reused the existing `signal_outcomes` table for options-flow forward
  validation instead of adding a separate table. Query pattern is the same as
  reversal/oversold: filter by `signal_source`, then compare tier-level
  `resolved`, `hits`, `hit_rate`, and maturity fields.
- No destructive migration: `refresh_all()` rewrites derived Parquet and
  rematerializes DuckDB tables from source reports.
- Options-flow tiers are `+5%/10d`, `+10%/20d`, and `+15%/40d`; target percent
  and horizon days are parsed from the existing tier label contract.
