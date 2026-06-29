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
