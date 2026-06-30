# Analytics Checks Automation

`scripts/analytics_checks.py` runs after `scripts/analytics_store.py refresh`.
Deployment runs both commands, `scripts/run_candidate_pipeline.py` runs them
after a successful local/test candidate refresh, and Risk Guard UI scans refresh
their table/checks after writing a snapshot. The checker reads the
materialized DuckDB file in read-only mode, writes
`reports/analytics_checks/latest.json`, and the `Analytics DB` page renders that
report.

## Workflow

| State | Event | Guard | Action | Next |
| --- | --- | --- | --- | --- |
| `refreshed` | checks start | DuckDB file exists | run read-only checks | `checked` |
| `refreshed` | checks start | DuckDB file missing | publish BLOCK report | `published` |
| `checked` | hard failure found | any required table missing, empty, unreadable, or `latest.json` duplicated | set `BLOCK_TODAY_SIGNALS` | `published` |
| `checked` | warning found | stale date or insufficient sample | set `REVIEW_REQUIRED` | `published` |
| `checked` | repeat signal found | repeated ticker in lookback window | add ticker action | `published` |
| `checked` | no issue found | all checks pass | set `NO_ACTION` | `published` |
| `published` | UI reads report | report JSON exists | render status/actions | final |

Validation: all states are reachable from `refreshed`, every non-final state has
an outgoing transition, and status precedence is deterministic:
`BLOCK > WARN > PASS`.

## What Runs Automatically

| Check | Purpose | Cadence | Verification | Automated action |
| --- | --- | --- | --- | --- |
| DuckDB file exists | Confirms refresh produced a readable store | Every deploy and manual checks run | `db:exists` in `latest.json` | `BLOCK_TODAY_SIGNALS` when missing |
| Table exists | Confirms all required read-model tables are present | Every run | `table:<name>:exists` | Block today signals when missing |
| Row count | Confirms required tables are populated | Every run | `table:<name>:row_count` | Block today signals when zero |
| Maturity-table row count | Tracks whether candidate/outcome/risk/position/market-context/report/watchlist history has started | Every run | `table:candidate_scores:row_count`, `table:candidate_rankings:row_count`, `table:risk_guard_rows:row_count`, `table:portfolio_positions:row_count`, `table:theme_flow_snapshots:row_count`, `table:sector_rotation_snapshots:row_count`, `table:validation_summaries:row_count`, `table:daily_reports:row_count`, `table:watchlist_sources:row_count`, `table:signal_outcomes:row_count` | `REVIEW_REQUIRED` when zero |
| Latest date freshness | Finds stale sources | Every run | `table:<name>:latest_date` | `REVIEW_REQUIRED` when stale/future-dated |
| `latest.json` duplicate guard | Ensures dated signal history is not double-counted | Every run | `table:<signal>:no_latest_source` | Block today signals on duplicates |
| Repeated options flow | Promotes tickers with repeated unusual flow | Every run | `signals[].category == options_flow_repeats` | `WATCHLIST_UPGRADE` |
| Repeated reversal radar | Flags repeated exploratory reversal candidates | Every run | `signals[].category == reversal_radar_repeats` | `REVIEW_REQUIRED` |
| Repeated oversold reversal | Flags repeated exploratory oversold candidates | Every run | `signals[].category == oversold_reversal_repeats` | `REVIEW_REQUIRED` |
| Repeated Risk Guard warnings | Flags tickers repeatedly marked REDUCE/EXIT | Every run | `signals[].category == risk_guard_repeats` | `REVIEW_REQUIRED` |
| Performance sample size | Prevents over-trusting immature hit-rate stats | Every run | `performance.status` | `REVIEW_REQUIRED` until sample threshold is met |
| Candidate ranking history | Confirms deterministic ranking snapshots are being retained | Every run | `table:candidate_rankings:row_count`, `table:candidate_rankings:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Run status history | Confirms local/test candidate refresh history is being retained | Every run | `table:run_status_history:row_count`, `table:run_status_history:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Portfolio positions | Confirms IBKR reconciliation snapshots are being retained | Every run | `table:portfolio_positions:row_count`, `table:portfolio_positions:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Theme Flow snapshots | Confirms Theme Flow refresh snapshots are being retained | Every run | `table:theme_flow_snapshots:row_count`, `table:theme_flow_snapshots:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Sector Rotation snapshots | Confirms Sector Rotation refresh snapshots are being retained | Every run | `table:sector_rotation_snapshots:row_count`, `table:sector_rotation_snapshots:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Validation summaries | Confirms forward validators are publishing lane-level status | Every run | `table:validation_summaries:row_count`, `table:validation_summaries:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Daily reports | Confirms daily report archives are queryable from DuckDB | Every run | `table:daily_reports:row_count`, `table:daily_reports:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Watchlist sources | Confirms manual and scanner watchlist provenance is queryable | Every run | `table:watchlist_sources:row_count`, `table:watchlist_sources:latest_date` | `REVIEW_REQUIRED` when empty or stale |

`signal_outcomes` now includes the options-flow forward validator in addition
to reversal radar and oversold reversal. Options-flow outcome rows are useful
for review as soon as they appear, but strategy-weight changes remain gated
until the tier has at least 100 resolved entries.

`run_status_history` is observability data, not a signal source. Empty or stale
history produces `REVIEW_REQUIRED` instead of blocking today signals.

`candidate_rankings` is ranking-history data, not an independently validated
signal source. Empty or stale history produces `REVIEW_REQUIRED`; strategy
weight changes still depend on forward outcomes and performance-ledger samples.

`performance_ledger` is the validated-pick performance record. New rows are
created only when a daily report contains confirmed/ranked picks and Stage 6
appends them with `python scripts/06_append_ledger.py`; forward returns are then
filled by `python scripts/07_verify_returns.py` as the 7/14/30/60D windows
mature. Stale or low-sample ledger data should keep signal weighting
review-only: 20+ rows is the minimum for manual review, and 100+ rows is the
minimum before changing strategy weights.

`risk_guard_rows` is exposure-review data. Empty or stale history produces
`REVIEW_REQUIRED`, and repeated REDUCE/EXIT rows surface as manual risk-review
actions before adding new exposure.

`portfolio_positions` is position-review data. It is derived from local/test
IBKR reconciliation and stores underlying-level aggregates only, so empty or
stale rows require review but do not block signal generation. When it is empty,
start IBKR Gateway/TWS with API enabled, then run
`python scripts/ibkr_client.py reconcile` so `reports/reconciliation.json` can
be exported into DuckDB.

`theme_flow_snapshots` is market-context data. Empty or stale rows require
review because the Theme Flow page would otherwise be latest-only or missing,
but it does not block signal generation.

`sector_rotation_snapshots` is broad market-context data. Empty or stale rows
require review because candidate sector context would be latest-only or missing,
but it does not block signal generation.

`validation_summaries` is validator-health data. Empty or stale rows require
review because maturity gates and dropped-row provenance would be missing, but
it does not block signal generation by itself.

`daily_reports` is archive/search data. Empty or stale rows require review
because portfolio notes and final report context would be missing from the DB,
but it does not block signal generation by itself.

`watchlist_sources` is source-provenance data. Empty or stale rows require
review because manual/scanner watchlist visibility would be unexplained, but it
does not block signal generation by itself.

## What Remains Human-Gated

The system can automate detection, warnings, UI display, and watchlist
recommendations. It should not automatically change strategy weights, promote an
exploratory lane to validated, place trades, or delete source reports. Those
remain human-gated because they change platform behavior or capital allocation.

## Manual Verification

Run locally:

```bash
.venv/bin/python scripts/analytics_store.py refresh
.venv/bin/python scripts/analytics_checks.py run
```

Run on the test server:

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_checks.py run --analytics-dir /home/kenny/apps/surge-screener/shared/data --output /home/kenny/apps/surge-screener/current/reports/analytics_checks/latest.json --allow-block'
```

Inspect:

```bash
cat reports/analytics_checks/latest.json
```

Expected top-level fields:

- `status`: `PASS`, `WARN`, or `BLOCK`
- `recommended_action`: highest-priority action for the current run
- `checks`: table/file health checks
- `signals`: repeated ticker findings
- `performance`: performance-ledger maturity metrics
- `next_actions`: actions the UI should surface after inspection
