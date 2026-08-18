# Post-producer Analytics ingestion

The 7F host owns report ingestion after deployment. The laptop and VPN are not
part of the runtime path.

## Lifecycle

`surge-post-producer-analytics.timer` starts the observer at 06:35 Asia/Taipei
on Tuesday through Saturday. The start time is not a success assumption. The
service waits for these actual terminal producers:

- the scheduled GitHub `surge_scan` job;
- the scheduled `market_thesis` job when the report date is Monday;
- the local 7F Theme Flow service and its fresh snapshot.

After all required producers succeed, the service resolves `main` once. Every
GitHub Contents request then uses that full 40-character SHA. Only the daily
summary, candidate-score snapshot, and calendar-required Market Thesis file are
allowlisted. Their JSON contracts and SHA-256 values are validated before a
new durable generation becomes `shared/published_reports/current`.

Analytics reads an overlay: durable published files win over the same paths in
the deployed release, while release history and 7F runtime sources remain
visible. Data Health uses the same overlay on its next full run, so it cannot
regress the post-producer ingestion.

## Transaction and failure behavior

Data Health and post-producer ingestion share:

`/home/kenny/apps/surge-screener/shared/locks/analytics-refresh.lock`

Post-producer ingestion builds Parquet and DuckDB in a sibling staging
directory. Analytics checks and the strict latest-date/cohort gate run against
that staging generation. DuckDB is promoted only after those gates pass. A
producer failure, missing artifact, malformed contract, non-zero BLOCK count,
or stale post-ingestion check fails closed and leaves the previous DuckDB in
place.

The service does not create picks, relax weights, or synthesize ledger rows.
A successful zero-pick report stays distinct from missing, failed, and
unpublished producer states.

## Evidence and operations

The terminal verdict is:

`/home/kenny/apps/surge-screener/shared/post_ingestion/latest.json`

It contains producer run/job IDs, the fixed source SHA, artifact paths and
hashes, selected Analytics values, and the promoted database identity.
Runtime status and logs are under `shared/run_status`.

```bash
ssh antigravity 'systemctl --user status surge-post-producer-analytics.service --no-pager'
ssh antigravity 'systemctl --user list-timers surge-post-producer-analytics.timer --no-pager'
ssh antigravity 'journalctl --user -u surge-post-producer-analytics.service -n 100 --no-pager'
ssh antigravity 'python3 -m json.tool /home/kenny/apps/surge-screener/shared/post_ingestion/latest.json'
```

To rerun the current Taipei window after resolving a transient external issue:

```bash
ssh antigravity 'systemctl --user start surge-post-producer-analytics.service'
```

Rollback is a normal code revert and redeploy. Existing durable generations
are retained; do not delete `shared/published_reports` or `shared/data` during
rollback.
