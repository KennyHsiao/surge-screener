#!/usr/bin/env python3
"""Self-contained tests for daily bars artifacts.

Run:  .venv/bin/python scripts/test_daily_bars_store.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

import daily_bars_store as dbs  # noqa: E402


YAHOO_BARS = [
    {
        "date": "2026-06-30",
        "open": 100.0,
        "high": 111.0,
        "low": 99.0,
        "close": 110.0,
        "adj_close": 109.5,
        "volume": 1000,
    },
    {
        "date": "2026-07-01",
        "open": 110.0,
        "high": 113.0,
        "low": 108.0,
        "close": 112.0,
        "adj_close": 111.5,
        "volume": 1200,
    },
]

SINA_MATCHING_BARS = [
    {"date": "2026-07-01", "open": 110.0, "high": 113.0, "low": 108.0, "close": 112.5, "volume": 1200}
]


def test_build_rows_prefers_yahoo_adjusted_when_sources_match():
    rows = dbs.build_daily_bars_rows(
        ["AAPL"],
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        yahoo_fetcher=lambda ticker: YAHOO_BARS,
        sina_fetcher=lambda ticker: SINA_MATCHING_BARS,
    )

    assert len(rows) == 2, rows
    assert {r["source"] for r in rows} == {"yfinance"}
    assert {r["is_adjusted"] for r in rows} == {True}
    assert {r["data_quality_status"] for r in rows} == {"ok"}, rows
    assert rows[-1]["adj_close"] == 111.5, rows
    assert rows[-1]["source_priority"] == 1, rows


def test_build_rows_uses_sina_fallback_when_yahoo_unavailable():
    rows = dbs.build_daily_bars_rows(
        ["AAPL"],
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        yahoo_fetcher=lambda ticker: [],
        sina_fetcher=lambda ticker: SINA_MATCHING_BARS,
    )

    assert len(rows) == 1, rows
    assert rows[0]["source"] == "sina_us_daily_bars", rows
    assert rows[0]["is_adjusted"] is False, rows
    assert rows[0]["data_quality_status"] == "fallback", rows
    assert rows[0]["adj_close"] is None, rows


def test_build_rows_blocks_yahoo_primary_on_large_sina_mismatch():
    rows = dbs.build_daily_bars_rows(
        ["AAPL"],
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        yahoo_fetcher=lambda ticker: YAHOO_BARS,
        sina_fetcher=lambda ticker: [
            {"date": "2026-07-01", "open": 90.0, "high": 95.0, "low": 85.0, "close": 90.0, "volume": 1200}
        ],
    )

    assert len(rows) == 1, rows
    assert rows[0]["source"] == "sina_us_daily_bars", rows
    assert rows[0]["data_quality_status"] == "mismatch_blocked", rows
    assert rows[0]["source_priority"] == 2, rows


def test_write_daily_bars_snapshot_writes_parquet():
    with TemporaryDirectory() as td:
        out = dbs.write_daily_bars_snapshot(
            [
                {
                    "as_of_date": "2026-07-01",
                    "generated_at": "2026-07-01T00:00:00Z",
                    "ticker": "AAPL",
                    "bar_date": "2026-07-01",
                    "open": 110.0,
                    "high": 113.0,
                    "low": 108.0,
                    "close": 112.0,
                    "adj_close": 111.5,
                    "volume": 1200,
                    "source": "yfinance",
                    "is_adjusted": True,
                    "source_priority": 1,
                    "data_quality_status": "ok",
                }
            ],
            reports_dir=Path(td) / "reports",
            as_of_date="2026-07-01",
        )
        df = pd.read_parquet(out)

    assert out.name == "2026-07-01.parquet", out
    assert out.parent.name == "daily_bars", out
    assert df.iloc[0]["ticker"] == "AAPL", df


def main() -> int:
    tests = [
        test_build_rows_prefers_yahoo_adjusted_when_sources_match,
        test_build_rows_uses_sina_fallback_when_yahoo_unavailable,
        test_build_rows_blocks_yahoo_primary_on_large_sina_mismatch,
        test_write_daily_bars_snapshot_writes_parquet,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    if not failed:
        print("daily bars store tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
