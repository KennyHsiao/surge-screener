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
| Maturity-table row count | Tracks whether candidate/outcome/risk-review history has started | Every run | `table:candidate_scores:row_count`, `table:candidate_rankings:row_count`, `table:risk_guard_rows:row_count`, `table:signal_outcomes:row_count` | `REVIEW_REQUIRED` when zero |
| Latest date freshness | Finds stale sources | Every run | `table:<name>:latest_date` | `REVIEW_REQUIRED` when stale/future-dated |
| `latest.json` duplicate guard | Ensures dated signal history is not double-counted | Every run | `table:<signal>:no_latest_source` | Block today signals on duplicates |
| Repeated options flow | Promotes tickers with repeated unusual flow | Every run | `signals[].category == options_flow_repeats` | `WATCHLIST_UPGRADE` |
| Repeated reversal radar | Flags repeated exploratory reversal candidates | Every run | `signals[].category == reversal_radar_repeats` | `REVIEW_REQUIRED` |
| Repeated oversold reversal | Flags repeated exploratory oversold candidates | Every run | `signals[].category == oversold_reversal_repeats` | `REVIEW_REQUIRED` |
| Repeated Risk Guard warnings | Flags tickers repeatedly marked REDUCE/EXIT | Every run | `signals[].category == risk_guard_repeats` | `REVIEW_REQUIRED` |
| Performance sample size | Prevents over-trusting immature hit-rate stats | Every run | `performance.status` | `REVIEW_REQUIRED` until sample threshold is met |
| Candidate ranking history | Confirms deterministic ranking snapshots are being retained | Every run | `table:candidate_rankings:row_count`, `table:candidate_rankings:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Run status history | Confirms local/test candidate refresh history is being retained | Every run | `table:run_status_history:row_count`, `table:run_status_history:latest_date` | `REVIEW_REQUIRED` when empty or stale |

`signal_outcomes` now includes the options-flow forward validator in addition
to reversal radar and oversold reversal. Options-flow outcome rows are useful
for review as soon as they appear, but strategy-weight changes remain gated
until the tier has at least 100 resolved entries.

`run_status_history` is observability data, not a signal source. Empty or stale
history produces `REVIEW_REQUIRED` instead of blocking today signals.

`candidate_rankings` is ranking-history data, not an independently validated
signal source. Empty or stale history produces `REVIEW_REQUIRED`; strategy
weight changes still depend on forward outcomes and performance-ledger samples.

`risk_guard_rows` is exposure-review data. Empty or stale history produces
`REVIEW_REQUIRED`, and repeated REDUCE/EXIT rows surface as manual risk-review
actions before adding new exposure.

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
