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
- Unresolved next-modeling candidates are documented in
  `docs/analytics-store-data-inventory.md`.
