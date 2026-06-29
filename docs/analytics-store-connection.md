# Analytics Store Connection

DuckDB is embedded. It is a database file plus Parquet files, not a TCP database
server like PostgreSQL. There is no host/port connection string to open directly
from a local SQL client.

## Test Server Location

- SSH alias: `antigravity`
- SSH target: `kenny@172.16.204.117`
- Analytics root: `/home/kenny/apps/surge-screener/shared/data`
- DuckDB file: `/home/kenny/apps/surge-screener/shared/data/analytics.duckdb`
- Parquet directory: `/home/kenny/apps/surge-screener/shared/data/parquet`

## Refresh On Test Server

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py refresh --reports-dir /home/kenny/apps/surge-screener/current/reports --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

The deploy script runs this refresh automatically after installing dependencies.

## Query From Local Through SSH

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py query "select count(*) as rows from iv_history" --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

Example cross-table count:

```bash
ssh antigravity 'SURGE_ANALYTICS_DIR=/home/kenny/apps/surge-screener/shared/data /home/kenny/apps/surge-screener/.venv/bin/python /home/kenny/apps/surge-screener/current/scripts/analytics_store.py query "select (select count(*) from performance_ledger) as ledger_rows, (select count(*) from iv_history) as iv_rows" --analytics-dir /home/kenny/apps/surge-screener/shared/data'
```

## If A Real Remote SQL Connection Is Required

DuckDB is the wrong shape for that requirement. Use PostgreSQL on the test server
and connect through an SSH tunnel, or expose a small read-only API. For this
platform's current analytics workload, SSH-executed DuckDB queries keep the data
local to the test server and avoid running another database service.
