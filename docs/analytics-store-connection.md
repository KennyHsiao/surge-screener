# Analytics Store Connection

DuckDB is embedded. It is a database file, not a TCP database server like
PostgreSQL. There is no host/port connection string to open directly from a
local SQL client.

The refresh step still writes Parquet files as portable exports, but the query
tables are materialized inside `analytics.duckdb`. This keeps DataGrip/SSHFS
connections from depending on machine-specific Parquet paths.

## Test Server Location

- SSH alias: `antigravity`
- SSH target: `kenny@172.16.204.117`
- Analytics root: `/home/kenny/apps/surge-screener/shared/data`
- DuckDB file: `/home/kenny/apps/surge-screener/shared/data/analytics.duckdb`
- Parquet directory: `/home/kenny/apps/surge-screener/shared/data/parquet`
- Candidate artifact root: `/home/kenny/apps/surge-screener/shared/candidates`
- Candidate ranking snapshots: `/home/kenny/apps/surge-screener/shared/candidate_rankings`

## Refresh On Test Server

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py refresh --reports-dir /home/kenny/apps/surge-screener/current/reports --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

The deploy script runs this refresh automatically after installing dependencies.

## Automated Checks Report

After refresh, deployment runs `scripts/analytics_checks.py run` and writes:

```text
reports/analytics_checks/latest.json
```

On the test server the full path is:

```text
/home/kenny/apps/surge-screener/current/reports/analytics_checks/latest.json
```

Manual test-server run:

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_checks.py run --analytics-dir /home/kenny/apps/surge-screener/shared/data --output /home/kenny/apps/surge-screener/current/reports/analytics_checks/latest.json --allow-block'
```

The JSON reports `PASS`, `WARN`, or `BLOCK`, plus the recommended follow-up
action. The Streamlit `Analytics DB` page reads the same file.

## Query From Local Through SSH

`query` is read-only. It does not refresh Parquet or rebuild DuckDB tables; run
the refresh command first when the source reports have changed.

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py query "select count(*) as rows from iv_history" --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

## Platform UI

The Streamlit app has a read-only `Analytics DB` page under `研究驗證`. It reads
`analytics.duckdb` directly on the server, so it does not need DataGrip, SSHFS,
macFUSE, or a local DB copy.

Expected tables:

- `performance_ledger`
- `iv_history`
- `options_flow_signals`
- `reversal_radar_signals`
- `oversold_reversal_signals`
- `market_thesis_forecasts`
- `candidate_scores`
- `candidate_rankings`
- `signal_outcomes`
- `run_status_history`

The table inventory and next candidates are tracked in
`docs/analytics-store-data-inventory.md`.
Automated validation rules are tracked in
`docs/analytics-checks-automation.md`.

## DataGrip Through SSHFS

Mount the test-server analytics directory first, then point DataGrip at the
mounted local path:

```bash
sshfs -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3,ro \
  antigravity:/home/kenny/apps/surge-screener/shared/data \
  /Users/ken/Workspace/AI/surge-screener/reports/analytics-remote
```

Use this DataGrip JDBC URL:

```text
jdbc:duckdb:/Users/ken/Workspace/AI/surge-screener/reports/analytics-remote/analytics.duckdb
```

Do not use the server path in DataGrip on macOS:

```text
jdbc:duckdb:/home/kenny/apps/surge-screener/shared/data/analytics.duckdb
```

That path only exists on the test server.

Example cross-table count:

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py query "select (select count(*) from performance_ledger) as ledger_rows, (select count(*) from iv_history) as iv_rows" --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

## If A Real Remote SQL Connection Is Required

DuckDB is the wrong shape for that requirement. Use PostgreSQL on the test server
and connect through an SSH tunnel, or expose a small read-only API. For this
platform's current analytics workload, SSH-executed DuckDB queries keep the data
local to the test server and avoid running another database service.
