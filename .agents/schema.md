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
  - `candidate_scores`
  - `candidate_rankings`
  - `risk_guard_rows`
  - `portfolio_positions`
  - `signal_outcomes`
  - `run_status_history`
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

## 2026-06-30 Run Status History Read Model

- Added `run_status_history` as a derived DuckDB table from
  `reports/run_status/candidates-local-history.jsonl`.
- The table keeps stable scalar columns for query patterns (`run_id`, `job`,
  `status`, `started_at`, `finished_at`, `duration_seconds`, stage fields, key
  candidate refresh metrics) and preserves nested source detail in
  `metrics_json`, `outputs_json`, `warnings_json`, `errors_json`, and
  `raw_run_json`.
- Empty `run_status_history` is an observability warning, not a signal block.
  It is included in analytics health checks as `WARN/REVIEW_REQUIRED`.
- Test-server deployment now maps `current/reports/run_status` to
  `$APP_ROOT/shared/run_status` so local/test run history survives rsync
  releases.

## 2026-06-30 Candidate Ranking History Read Model

- Added `candidate_rankings` as a derived DuckDB table from
  `reports/candidate_rankings/YYYY-MM-DD.json`, with root
  `ranked_candidates.json` as a same-date-missing fallback.
- `scripts/03_rank_candidates.py` now writes the latest
  `ranked_candidates.json` and a dated ranking snapshot for analytics history.
- The table keeps stable scalar columns for query patterns (`scan_date`,
  `ticker`, `rank_position`, `rank_score`, `rank_bucket`, component scores, and
  options-gate status) and preserves source detail in `*_json` columns.
- Empty/stale candidate ranking history is `WARN/REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`.
- Test-server deployment maps `current/reports/candidate_rankings` to
  `$APP_ROOT/shared/candidate_rankings` so UI-generated ranking snapshots
  survive releases before analytics refresh.
- Test-server systemd also sets `SURGE_CANDIDATE_OUTPUT_DIR` to
  `$APP_ROOT/shared/candidates`, and deploy exposes legacy root artifact
  symlinks for `ranked_candidates.json` and related candidate files.

## 2026-06-30 Risk Guard Rows Read Model

- Added `risk_guard_rows` as a derived DuckDB table from
  `reports/risk_guard/YYYY-MM-DD.json`, with `reports/risk_guard/latest.json`
  as a same-date-missing fallback.
- `scripts/risk_guard.py` now writes both latest and dated snapshots via
  `write_report()`. The Streamlit Risk Guard/Radar scan path refreshes the
  `risk_guard_rows` analytics table after writing the snapshot.
- The table keeps stable scalar columns for query patterns (`as_of_date`,
  `ticker`, `status`, `risk_score`, component scores, sector quadrant, and
  position-risk fields) and preserves source detail in JSON columns.
- Empty/stale Risk Guard history is `WARN/REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`, because it is exposure-review evidence rather than a
  validated entry signal.
- Test-server deployment maps `current/reports/risk_guard` to
  `$APP_ROOT/shared/risk_guard` so UI-generated risk snapshots survive releases.

## 2026-06-30 Portfolio Positions Read Model

- Added `portfolio_positions` as a derived DuckDB table from
  `reports/reconciliation.json`.
- The table keeps one row per underlying/bucket with scalar fields for
  `position_status`, `held`, `ranked`, `ticker`, leg counts, option DTE,
  worst leg return, and total unrealized P&L.
- Per-leg labels/account identifiers are not persisted in the analytics table;
  the preserved JSON column excludes `legs` and account fields.
- Empty/stale portfolio position rows are `WARN/REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`, because this is position-review evidence rather than a
  signal-validity gate.
- Test-server deployment maps `current/reports/reconciliation.json` to
  `$APP_ROOT/shared/reconciliation.json` so local/test IBKR reconciliation
  snapshots survive releases.
