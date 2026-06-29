# Stream Notes

## 2026-06-30 Analytics Candidate/Outcome Pipeline

- Pipeline mode: BATCH. The analytics store refresh is deploy/manual-time ETL
  from committed `reports/` artifacts into Parquet and materialized DuckDB
  tables. Sub-minute latency is not required.
- Source of truth remains `reports/`; DuckDB is a derived read model.
- New daily candidate-score source:
  `reports/candidate_scores/YYYY-MM-DD.json`, persisted from
  `scored_candidates.json` by the GitHub Actions screener workflow.
- New outcome source:
  forward validator `validation_summary.json` files for reversal radar and
  oversold reversal. These provide tier-level maturity metrics without network
  calls during analytics refresh.
- Idempotency: analytics refresh rewrites Parquet snapshots and materializes
  DuckDB tables from the current reports tree. Re-running with the same reports
  tree produces the same tables.
- Quality gate: `analytics_checks.py` treats candidate/outcome row-count gaps as
  `WARN/REVIEW_REQUIRED`, not hard signal blocks, because these are maturity
  tables and need initial accumulation time.

## 2026-06-30 Options-Flow Forward Outcome Pipeline

- Pipeline mode remains BATCH. The options-flow job writes a dated scan snapshot,
  then runs `scripts/options_flow_forward.py` to refresh
  `reports/options_flow/validation_summary.json`.
- Source contract: only `reports/options_flow/YYYY-MM-DD.json` participates in
  validation; `latest.json` is ignored to keep the source append-only.
- Transform: bullish signals validate upward underlying follow-through; bearish
  signals validate downward follow-through with direction-adjusted horizon
  returns.
- Sink: the existing `signal_outcomes` DuckDB table now includes
  `signal_source = 'options_flow'`. No new DuckDB table is needed until
  per-ticker realized outcomes become a UI requirement.
- Quality gate: tier rows remain `PROVISIONAL` until 100 resolved entries.
  Re-runs are idempotent over the committed reports tree.
