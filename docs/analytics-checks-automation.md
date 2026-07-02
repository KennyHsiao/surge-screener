# Analytics Checks Automation

`scripts/analytics_checks.py` runs after `scripts/analytics_store.py refresh`.
Deployment first runs `scripts/data_source_refresh.py` to refresh the core
source artifacts, then rebuilds the Analytics store and checks. The
`scripts/run_candidate_pipeline.py` local/test candidate pipeline runs the same
source refresh after a successful candidate refresh, and Risk Guard UI scans
refresh their table/checks after writing a snapshot. The daily `verify_returns`
workflow also refreshes a temporary Analytics store, writes
`reports/analytics_checks/latest.json`, and runs
`scripts/analytics_action_notify.py` to send no-picks Telegram alerts when the
streak thresholds are crossed. The checker reads the materialized DuckDB file
in read-only mode, writes `latest.json`, and the `Analytics DB` page renders
that report.

## Workflow

| State | Event | Guard | Action | Next |
| --- | --- | --- | --- | --- |
| `refreshed` | checks start | DuckDB file exists | run read-only checks | `checked` |
| `refreshed` | checks start | DuckDB file missing | publish BLOCK report | `published` |
| `checked` | hard failure found | any required table missing, empty, unreadable, or `latest.json` duplicated | set `BLOCK_TODAY_SIGNALS` | `published` |
| `checked` | warning found | stale date or insufficient sample | set `REVIEW_REQUIRED` | `published` |
| `checked` | repeat signal found | repeated ticker in lookback window | add ticker action | `published` |
| `checked` | no issue found | all checks pass | set `NO_ACTION` | `published` |
| `published` | no-picks alert found | 5 or 10 weekday threshold and receipt missing | send Telegram and write receipt | final |
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
| Maturity-table row count | Tracks whether candidate/outcome/risk/position/trade-state/market-context/report/watchlist history has started | Every run | `table:candidate_scores:row_count`, `table:candidate_rankings:row_count`, `table:candidate_outcomes:row_count`, `table:risk_guard_rows:row_count`, `table:portfolio_positions:row_count`, `table:trade_state_snapshots:row_count`, `table:theme_flow_snapshots:row_count`, `table:sector_rotation_snapshots:row_count`, `table:validation_summaries:row_count`, `table:daily_reports:row_count`, `table:watchlist_sources:row_count`, `table:signal_outcomes:row_count` | `REVIEW_REQUIRED` when zero |
| Latest date freshness | Finds stale sources | Every run | `table:<name>:latest_date` | `REVIEW_REQUIRED` when stale/future-dated |
| Universe refresh freshness | Confirms current/near-current tradable universe identifiers are available | Every run | `data:universe_snapshots:freshness` | `UNIVERSE_REFRESH_FAILED` / `REVIEW_REQUIRED` when stale |
| Daily bars freshness | Confirms daily OHLCV history is current enough for Cycle/CE/Risk Guard | Every run | `data:daily_bars:freshness` | `DATA_SOURCE_STALE` / `REVIEW_REQUIRED` when stale |
| Money-flow coverage | Confirms latest Eastmoney money-flow snapshot met publishable coverage | Every run | `data:daily_money_flow:coverage` | `MONEY_FLOW_UNPUBLISHABLE` / `REVIEW_REQUIRED` when below 70% or unpublishable |
| Trade-state role tags | Confirms ticker rows have displayable industry-role tags | Every run | `data:trade_state_snapshots:role_tags` | `ROLE_TAG_MISSING` / `REVIEW_REQUIRED` when any latest row is unclassified |
| `latest.json` duplicate guard | Ensures dated signal history is not double-counted | Every run | `table:<signal>:no_latest_source` | Block today signals on duplicates |
| Repeated options flow | Promotes tickers with repeated unusual flow | Every run | `signals[].category == options_flow_repeats` | `WATCHLIST_UPGRADE` |
| Repeated reversal radar | Flags repeated exploratory reversal candidates | Every run | `signals[].category == reversal_radar_repeats` | `REVIEW_REQUIRED` |
| Repeated oversold reversal | Flags repeated exploratory oversold candidates | Every run | `signals[].category == oversold_reversal_repeats` | `REVIEW_REQUIRED` |
| Repeated Risk Guard warnings | Flags tickers repeatedly marked REDUCE/EXIT | Every run | `signals[].category == risk_guard_repeats` | `REVIEW_REQUIRED` |
| Performance sample size | Prevents over-trusting immature hit-rate stats | Every run | `performance.status` | `REVIEW_REQUIRED` until sample threshold is met |
| No confirmed picks streak | Detects consecutive trading weekdays without confirmed picks | Every run | `performance:no_confirmed_picks_streak` | `TG_WARN` at 5 trading days; `REVIEW_REQUIRED` at 10 trading days |
| Candidate ranking history | Confirms deterministic ranking snapshots are being retained | Every run | `table:candidate_rankings:row_count`, `table:candidate_rankings:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Candidate paper outcomes | Confirms no-LLM ranked-candidate forward validation is accumulating | Every run | `table:candidate_outcomes:row_count`, `table:candidate_outcomes:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Run status history | Confirms local/test candidate refresh history is being retained | Every run | `table:run_status_history:row_count`, `table:run_status_history:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Portfolio positions | Confirms IBKR reconciliation snapshots are being retained | Every run | `table:portfolio_positions:row_count`, `table:portfolio_positions:latest_date` | `REVIEW_REQUIRED` when empty or stale |
| Trade State snapshots | Confirms Cycle/CE/verdict/role-tag review snapshots are being retained | Every run | `table:trade_state_snapshots:row_count`, `table:trade_state_snapshots:latest_date` | `REVIEW_REQUIRED` when empty or stale |
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

The data-source warning codes are intentionally stable for UI routing:
`DATA_SOURCE_STALE`, `MONEY_FLOW_UNPUBLISHABLE`,
`UNIVERSE_REFRESH_FAILED`, and `ROLE_TAG_MISSING` are emitted in
`warning_codes` when their related checks are non-pass. `QUOTE_FALLBACK_ACTIVE`
is reserved for UI quote-source chips because quote fallback is cache-only and
not a first-class DuckDB table.

`candidate_rankings` is ranking-history data, not an independently validated
signal source. Empty or stale history produces `REVIEW_REQUIRED`; strategy
weight changes still depend on forward outcomes and performance-ledger samples.

`candidate_outcomes` is no-LLM paper validation data for deterministic rankings.
The scheduled `candidate_outcomes` workflow creates top-20 ranking snapshots and
updates 7/14/30/60D forward returns when windows mature. Empty or stale rows
produce `REVIEW_REQUIRED`; these rows are review evidence and do not promote a
candidate to a formal pick by themselves. This belongs to Analytics / DB
validation, not order placement or trading execution.

`performance_ledger` is the validated-pick performance record. New rows are
created only when a daily report contains confirmed/ranked picks and Stage 6
appends them with `python scripts/06_append_ledger.py`; forward returns are then
filled by `python scripts/07_verify_returns.py` as the 7/14/30/60D windows
mature. Stale or low-sample ledger data should keep signal weighting
review-only: 20+ rows is the minimum for manual review. At 100+ raw rows,
review only preliminary trends; scoring-weight changes should wait for 100+
resolved 30D outcomes. Do not draw strong medium-term conclusions before 60D
outcomes mature.

The no-picks streak check is also ledger-based. Consecutive trading days are
counted with a weekday proxy from the latest `performance_ledger.scan_date`.
At 5 trading days without confirmed picks, the action is `TG_WARN`; at 10
trading days, the action is `REVIEW_REQUIRED`. The daily `verify_returns`
workflow sends these through Telegram with the existing `TELEGRAM_BOT_TOKEN` /
`TELEGRAM_CHAT_ID` environment. Successful sends are recorded in
`reports/analytics_checks/no_picks_alerts.json` using
`check_id + latest_pick_date + action` as the receipt key, so the same streak
level is not resent every day. When a new confirmed pick appears, the latest
pick date changes and a future streak can alert again.

`risk_guard_rows` is exposure-review data. Empty or stale history produces
`REVIEW_REQUIRED`, and repeated REDUCE/EXIT rows surface as manual risk-review
actions before adding new exposure.

`portfolio_positions` is position-review data. It is derived from local/test
IBKR reconciliation and stores underlying-level aggregates only, so empty or
stale rows require review but do not block signal generation. When it is empty,
the UI should say the page needs an active IBKR Gateway or TWS login, API
enabled, and a current connection before `portfolio_positions` can update. Then run
`python scripts/ibkr_client.py reconcile` so `reports/reconciliation.json` can
be exported into DuckDB.

`trade_state_snapshots` is trading-review state data. It stores the Cycle,
CE/Proxy source, verdict, risk level, industry-role tag, money-flow evidence,
options-flow score, social mentions, and raw provenance used to explain a
ticker's status on a specific date. Empty or stale rows require review because
the UI would otherwise be latest-only, but they do not block signal generation.

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
.venv/bin/python scripts/analytics_action_notify.py
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
