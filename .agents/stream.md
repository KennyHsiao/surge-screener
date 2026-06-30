# Stream Notes

## 2026-06-30 Analytics Candidate/Outcome Pipeline

- Pipeline mode: BATCH. The analytics store refresh is deploy/manual-time ETL
  from committed `reports/` artifacts into Parquet and materialized DuckDB
  tables; local/test candidate pipeline runs also refresh it after successful
  artifact generation so the UI can see new snapshots without waiting for the
  next deploy.
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

## 2026-06-30 Run Status History Pipeline

- Pipeline mode remains BATCH. `run_status_history` exports terminal local
  candidate refresh JSONL rows from `reports/run_status/candidates-local-history.jsonl`
  into Parquet and materialized DuckDB.
- Source contract: `RunStatus.succeed()` / `RunStatus.fail()` append one JSONL
  row per terminal run. The exporter skips malformed lines and preserves the
  original record in `raw_run_json`.
- Sink: `run_status_history` powers operational review: duration, failed stage,
  ranked/scored counts, options-gate counts, warnings, and errors.
- Test-server release directories now symlink `reports/run_status` to shared
  storage, so history is retained across deployments before analytics refresh.
- Quality gate: empty/stale history is `REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`, because it does not determine signal validity.

## 2026-06-30 Candidate Ranking History Pipeline

- Pipeline mode remains BATCH. `scripts/03_rank_candidates.py` writes
  `ranked_candidates.json` for the UI and a dated
  `reports/candidate_rankings/YYYY-MM-DD.json` snapshot for analytics.
- Source contract: one snapshot per scan date, rewritten atomically when ranking
  reruns for the same date. The exporter skips malformed JSON, reads
  `ranked_candidates` first with `tickers` as a backward-compatible fallback,
  and can use root `ranked_candidates.json` when no same-date snapshot exists.
- Sink: `candidate_rankings` powers Today Decision history, rank-bucket drift,
  and later score/outcome attribution by ticker/date.
- Test-server release directories symlink `reports/candidate_rankings` to
  shared storage so UI-generated snapshots survive deployments before analytics
  refresh.
- `scripts/run_candidate_pipeline.py` refreshes the analytics store and
  republishes `reports/analytics_checks/latest.json` after a successful
  candidate run, so `candidate_rankings` and `run_status_history` are visible in
  DuckDB immediately after UI-triggered refreshes.
- Quality gate: empty/stale ranking history is `REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`, because it is ranking evidence rather than validated
  signal performance.

## 2026-06-30 Risk Guard Analytics Pipeline

- Pipeline mode is UI-triggered plus batch-refresh compatible. Risk Guard scans
  write `reports/risk_guard/latest.json` and a dated
  `reports/risk_guard/YYYY-MM-DD.json` snapshot.
- Source contract: one snapshot per `as_of` date, rewritten atomically when the
  same scan date reruns. The exporter skips malformed JSON and reads
  `latest.json` only when no same-date snapshot exists.
- Sink: `risk_guard_rows` powers exposure review: repeated REDUCE/EXIT warnings,
  component score attribution, sector context, and position-risk drill-down.
- Test-server release directories symlink `reports/risk_guard` to shared
  storage so UI-generated risk snapshots survive deployments before analytics
  refresh.
- The Risk Guard/Radar UI path calls `refresh_analytics_for_report()` after a
  scan, so the DuckDB table and `reports/analytics_checks/latest.json` update
  immediately without waiting for a deploy.
- Quality gate: empty/stale Risk Guard history is `REVIEW_REQUIRED`, not
  `BLOCK_TODAY_SIGNALS`, because it is risk-review evidence rather than a
  standalone signal-validity gate.
