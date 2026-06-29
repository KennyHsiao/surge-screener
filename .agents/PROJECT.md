# Project Activity

| Date | Agent | Action | Files | Outcome |
| --- | --- | --- | --- | --- |
| 2026-06-30 | Schema | Expanded DuckDB analytics read model | `scripts/analytics_store.py`, `scripts/test_analytics_store.py`, `ui/analytics_db.py`, `docs/analytics-store-data-inventory.md` | Added options flow, reversal radar, oversold reversal, and market thesis forecast tables. |
| 2026-06-30 | Schema | Hardened DuckDB refresh semantics after review | `scripts/analytics_store.py`, `scripts/test_analytics_store.py`, `docs/analytics-store-connection.md` | Made query read-only and made refresh_all materialize tables only after all exports succeed. |
| 2026-06-30 | Builder | Automated analytics health checks | `scripts/analytics_checks.py`, `ui/analytics_db.py`, `scripts/deploy_test_server.sh`, `docs/analytics-checks-automation.md` | Added deploy-time checks, PASS/WARN/BLOCK actions, and UI rendering for latest analytics health. |
| 2026-06-30 | Stream/Schema | Added candidate and outcome analytics tables | `scripts/analytics_store.py`, `.github/workflows/surge_screener.yml`, `scripts/analytics_checks.py`, `ui/analytics_db.py` | Added `candidate_scores` and `signal_outcomes` to DuckDB refresh; daily workflow now persists scored candidates under `reports/candidate_scores/`. |
