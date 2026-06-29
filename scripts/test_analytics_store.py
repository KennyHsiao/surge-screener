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


def test_refresh_all_exports_signal_and_forecast_tables() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )

        options_dir = reports / "options_flow"
        options_dir.mkdir()
        option_payload = {
            "as_of": "2026-06-01",
            "generated_at": "2026-06-01T21:00:00Z",
            "provider": "fixture",
            "min_notional": 1000000,
            "universe_size": 2,
            "signal_count": 1,
            "signals": [{
                "ticker": "NVDA",
                "direction": "bullish",
                "flow_score": 88.5,
                "est_notional_usd": 1200000,
                "expiry": "2026-07-17",
                "max_voi": 12.3,
                "high_voi_strikes": 3,
                "call_put_ratio": 2.4,
                "put_call_ratio": 0.42,
                "total_call_vol": 2400,
                "total_put_vol": 1000,
                "otm_call_vol": 1400,
                "spot": 150.25,
                "tags": ["fixture"],
                "biggest": {"strike": 155, "notional": 900000},
            }],
        }
        (options_dir / "2026-06-01.json").write_text(json.dumps(option_payload), encoding="utf-8")
        (options_dir / "latest.json").write_text(json.dumps(option_payload), encoding="utf-8")

        reversal_dir = reports / "reversal_radar"
        reversal_dir.mkdir()
        (reversal_dir / "scan_2026-06-01.json").write_text(json.dumps({
            "as_of_date": "2026-06-01",
            "generated_at": "2026-06-01T22:00:00Z",
            "universe": "fixture",
            "universe_size": 2,
            "scanned": 2,
            "match_count": 1,
            "lane_id": "coiled-base",
            "exploratory": True,
            "runway_independent": False,
            "candidates": [{
                "ticker": "AMD",
                "signal_date": "2026-06-01",
                "status": "TURNING",
                "reversal_score": 64,
                "data_confidence": 95,
                "structure_score": 11,
                "momentum_score": 19,
                "options_score": 8,
                "sector_score": 4,
                "insider_score": 12,
                "analyst_score": 10,
                "primary_signals": ["fixture"],
                "data_gaps": [],
                "sector": {"etf": "XLK"},
            }],
        }), encoding="utf-8")

        oversold_dir = reports / "oversold_reversal"
        oversold_dir.mkdir()
        (oversold_dir / "scan_2026-06-01.json").write_text(json.dumps({
            "as_of_date": "2026-06-01",
            "generated_at": "2026-06-01T22:30:00Z",
            "universe": "fixture",
            "scanned": 2,
            "attempted": 2,
            "match_count": 1,
            "lane_id": "coiled-base",
            "exploratory": True,
            "runway_independent": False,
            "fetch_failed": [],
            "candidates": [{
                "ticker": "TSLA",
                "as_of": "2026-06-01",
                "signal_date": "2026-06-01",
                "avg_dollar_vol_m": 950.5,
                "last_price": 190.25,
                "rsi14": 44.2,
                "bb_width_pct": 1.2,
                "ma200": 180.1,
                "pct_vs_ma200": 5.6,
                "pct_from_52w_high": -24.5,
            }],
        }), encoding="utf-8")

        thesis_dir = reports / "market_thesis"
        thesis_dir.mkdir()
        (thesis_dir / "regime_only_forecast_2026-06-01.json").write_text(json.dumps({
            "as_of": "2026-06-01",
            "generated_at": "2026-06-02T00:00:00Z",
            "tier": 1,
            "method": "deterministic_baseline",
            "benchmark": "^GSPC",
            "direction": "看多",
            "bucket": "mid",
            "support_class": "regime_only",
            "manifest_status": "ready",
            "regime": "rally",
            "vix_bucket": "normal",
            "rationale": {"resolved": 100},
            "label": "fixture",
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select"
            " (select count(*) from options_flow_signals) as options_rows,"
            " (select count(*) from reversal_radar_signals) as reversal_rows,"
            " (select count(*) from oversold_reversal_signals) as oversold_rows,"
            " (select count(*) from market_thesis_forecasts) as thesis_rows",
            analytics_root=analytics_root,
        )[0]
        option_rows = store.query(
            "select ticker, source_file, tags_json from options_flow_signals",
            analytics_root=analytics_root,
        )

        expected_counts = {
            "options_rows": 1,
            "reversal_rows": 1,
            "oversold_rows": 1,
            "thesis_rows": 1,
        }
        if counts != expected_counts:
            raise AssertionError(counts)
        if meta["options_flow_signals"]["rows"] != 1:
            raise AssertionError(meta)
        if option_rows[0]["source_file"] != "2026-06-01.json":
            raise AssertionError(option_rows)
        if json.loads(option_rows[0]["tags_json"]) != ["fixture"]:
            raise AssertionError(option_rows)


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
