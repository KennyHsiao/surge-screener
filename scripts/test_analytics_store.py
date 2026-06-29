#!/usr/bin/env python3
"""Self-contained tests for the DuckDB/Parquet analytics store."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_store():
    spec = importlib.util.spec_from_file_location(
        "analytics_store_under_test",
        ROOT / "scripts" / "analytics_store.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _rows_by_ticker(rows: list[dict]) -> dict:
    return {r["ticker"]: r for r in rows}


def test_exports_performance_ledger_to_parquet_and_duckdb_table() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        ledger = tmp / "performance_ledger.csv"
        ledger.write_text(
            "scan_date,ticker,verdict,composite_score,fwd_30d_return\n"
            "2026-06-01,NVDA,BUY,92.5,18.2\n"
            "2026-06-01,AMD,WATCH,81.0,-2.0\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.export_performance_ledger(ledger, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, composite_score from performance_ledger order by ticker",
            analytics_root=analytics_root,
        )

        if meta["rows"] != 2:
            raise AssertionError(meta)
        if not (analytics_root / "parquet" / "performance_ledger.parquet").is_file():
            raise AssertionError("performance parquet was not written")
        by = _rows_by_ticker(rows)
        if float(by["NVDA"]["composite_score"]) != 92.5:
            raise AssertionError(rows)


def test_exports_iv_history_to_flat_parquet_and_duckdb_table() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        iv_dir = tmp / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"ticker": "NVDA", "series": {"2026-06-01": 0.55, "2026-06-02": 0.60}}),
            encoding="utf-8",
        )
        (iv_dir / "AMD.json").write_text(
            json.dumps({"ticker": "AMD", "series": {"2026-06-01": 0.48}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.export_iv_history(iv_dir, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, as_of_date, atm_iv from iv_history order by ticker, as_of_date",
            analytics_root=analytics_root,
        )

        if meta["rows"] != 3:
            raise AssertionError(meta)
        if not (analytics_root / "parquet" / "iv_history.parquet").is_file():
            raise AssertionError("iv_history parquet was not written")
        if rows[0]["ticker"] != "AMD" or float(rows[0]["atm_iv"]) != 0.48:
            raise AssertionError(rows)


def test_refresh_all_exports_known_sources_from_reports_root() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select (select count(*) from performance_ledger) as ledger_rows,"
            "       (select count(*) from iv_history) as iv_rows",
            analytics_root=analytics_root,
        )[0]

        if meta["performance_ledger"]["rows"] != 1 or meta["iv_history"]["rows"] != 1:
            raise AssertionError(meta)
        if counts["ledger_rows"] != 1 or counts["iv_rows"] != 1:
            raise AssertionError(counts)


def test_tables_work_from_other_working_directories() -> None:
    store = _load_store()
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        other_cwd = tmp / "other"
        other_cwd.mkdir()
        try:
            os.chdir(tmp)
            store.refresh_all(reports_root=Path("reports"), analytics_root=Path("analytics"))
            db_path = tmp / "analytics" / "analytics.duckdb"

            os.chdir(other_cwd)
            con = store.duckdb.connect(str(db_path), read_only=True)
            try:
                counts = con.execute(
                    "select (select count(*) from performance_ledger) as ledger_rows,"
                    "       (select count(*) from iv_history) as iv_rows"
                ).fetchone()
            finally:
                con.close()
        finally:
            os.chdir(old_cwd)

        if counts != (1, 1):
            raise AssertionError(counts)


def test_duckdb_tables_are_readable_without_parquet_files() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        (analytics_root / "parquet").rename(analytics_root / "parquet.off")

        con = store.duckdb.connect(str(analytics_root / "analytics.duckdb"), read_only=True)
        try:
            counts = con.execute(
                "select (select count(*) from performance_ledger) as ledger_rows,"
                "       (select count(*) from iv_history) as iv_rows"
            ).fetchone()
        finally:
            con.close()

        if counts != (1, 1):
            raise AssertionError(counts)


def test_readonly_catalog_reports_tables_and_counts() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        catalog = {r["table_name"]: r for r in store.readonly_catalog(analytics_root)}

        if catalog["performance_ledger"]["row_count"] != 1:
            raise AssertionError(catalog)
        if catalog["iv_history"]["table_type"] != "BASE TABLE":
            raise AssertionError(catalog)


def test_readonly_fetch_table_filters_ticker_and_clamps_limit() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n"
            "2026-06-01,NVDA,BUY,90\n"
            "2026-06-02,AMD,WATCH,75\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.export_performance_ledger(
            reports / "performance_ledger.csv",
            analytics_root=analytics_root,
        )
        df = store.fetch_table(
            "performance_ledger",
            analytics_root=analytics_root,
            tickers=["nvda"],
            limit=50000,
        )

        if list(df["ticker"]) != ["NVDA"]:
            raise AssertionError(df)


def test_run_safe_select_rejects_non_select_sql() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        analytics_root = Path(d) / "analytics"
        store.refresh_all(reports_root=Path(d) / "missing", analytics_root=analytics_root)

        try:
            store.run_safe_select("drop table iv_history", analytics_root=analytics_root)
        except ValueError as e:
            if "Only SELECT" not in str(e):
                raise AssertionError(e)
        else:
            raise AssertionError("non-select SQL was accepted")


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
