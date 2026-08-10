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


def _stored_bar(
    ticker: str,
    bar_date: str,
    close: float,
    *,
    as_of_date: str,
    generated_at: str,
) -> dict:
    return {
        "source_file": f"{as_of_date}.parquet",
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "ticker": ticker,
        "bar_date": bar_date,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "adj_close": close,
        "volume": 1000,
        "source": "yfinance",
        "is_adjusted": True,
        "source_priority": 1,
        "data_quality_status": "ok",
        "raw_bar_json": f'{{"close":{close}}}',
    }


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


def test_refresh_daily_bars_streams_rows_without_building_full_list():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        original_iter = dbs._iter_daily_bars_rows
        original_build = dbs.build_daily_bars_rows

        def stream_rows(*args, **kwargs):
            yield _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T00:00:00Z",
            )

        def reject_list_build(*args, **kwargs):
            raise AssertionError("refresh materialized the full incoming list")

        dbs._iter_daily_bars_rows = stream_rows
        dbs.build_daily_bars_rows = reject_list_build
        try:
            result = dbs.refresh_daily_bars(
                ["AAPL"], reports_dir=reports, as_of_date="2026-07-02"
            )
        finally:
            dbs._iter_daily_bars_rows = original_iter
            dbs.build_daily_bars_rows = original_build

        stored = pd.read_parquet(result["path"])

    assert result["rows"] == 1
    assert result["tickers"] == ["AAPL"]
    assert list(stored.columns) == dbs.DAILY_BAR_COLUMNS


def test_write_daily_bars_snapshot_seeds_canonical_without_deleting_delta():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        rows = [
            _stored_bar("AAPL", "2026-06-30", 100, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
            _stored_bar("AAPL", "2026-07-01", 101, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
        ]

        delta_path = dbs.write_daily_bars_snapshot(
            rows, reports_dir=reports, as_of_date="2026-07-01"
        )
        canonical_path = delta_path.parent / "canonical.parquet"

        assert delta_path.is_file()
        assert canonical_path.is_file()
        assert list(pd.read_parquet(canonical_path).columns) == dbs.DAILY_BAR_COLUMNS
        assert len(pd.read_parquet(delta_path)) == len(pd.read_parquet(canonical_path)) == 2


def test_first_canonical_seed_retains_tickers_missing_from_partial_refresh():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        bars_dir = reports / "market_data" / "daily_bars"
        bars_dir.mkdir(parents=True)
        legacy_rows = [
            _stored_bar("AAPL", "2026-07-01", 100, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
            _stored_bar("MSFT", "2026-07-01", 200, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
        ]
        pd.DataFrame(legacy_rows, columns=dbs.DAILY_BAR_COLUMNS).to_parquet(
            bars_dir / "2026-07-01.parquet", index=False
        )

        delta_path = dbs.write_daily_bars_snapshot(
            [_stored_bar("AAPL", "2026-07-01", 101, as_of_date="2026-07-02", generated_at="2026-07-02T00:00:00Z")],
            reports_dir=reports,
            as_of_date="2026-07-02",
        )
        canonical = pd.read_parquet(bars_dir / "canonical.parquet")
        delta = pd.read_parquet(delta_path)

        assert set(canonical["ticker"]) == {"AAPL", "MSFT"}
        assert float(canonical.query("ticker == 'AAPL'").iloc[0]["close"]) == 101
        assert float(canonical.query("ticker == 'MSFT'").iloc[0]["close"]) == 200
        assert set(delta["ticker"]) == {"AAPL"}


def test_daily_bars_canonical_merge_writes_only_business_changes_and_is_idempotent():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        first = [
            _stored_bar("AAPL", "2026-06-30", 100, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
            _stored_bar("AAPL", "2026-07-01", 101, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
            _stored_bar("MSFT", "2026-07-01", 200, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z"),
        ]
        second = [
            _stored_bar("AAPL", "2026-06-30", 100, as_of_date="2026-07-02", generated_at="2026-07-02T00:00:00Z"),
            _stored_bar("AAPL", "2026-07-01", 111, as_of_date="2026-07-02", generated_at="2026-07-02T00:00:00Z"),
            _stored_bar("AAPL", "2026-07-02", 112, as_of_date="2026-07-02", generated_at="2026-07-02T00:00:00Z"),
        ]
        dbs.write_daily_bars_snapshot(first, reports_dir=reports, as_of_date="2026-07-01")

        delta_path = dbs.write_daily_bars_snapshot(second, reports_dir=reports, as_of_date="2026-07-02")
        first_canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        dbs.write_daily_bars_snapshot(second, reports_dir=reports, as_of_date="2026-07-02")
        second_canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        delta = pd.read_parquet(delta_path)

        assert set(zip(delta["ticker"], delta["bar_date"], strict=True)) == {
            ("AAPL", "2026-07-01"), ("AAPL", "2026-07-02"),
        }
        assert set(first_canonical["ticker"]) == {"AAPL", "MSFT"}
        assert float(first_canonical.query("ticker == 'AAPL' and bar_date == '2026-07-01'").iloc[0]["close"]) == 111
        pd.testing.assert_frame_equal(first_canonical, second_canonical)


def test_stale_refresh_cannot_overwrite_newer_canonical_rows():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        newer = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                111,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T00:00:00Z",
            )
        ]
        stale = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-01",
                generated_at="2026-07-01T00:00:00Z",
            )
        ]
        dbs.write_daily_bars_snapshot(
            newer, reports_dir=reports, as_of_date="2026-07-02"
        )

        stale_delta = dbs.write_daily_bars_snapshot(
            stale, reports_dir=reports, as_of_date="2026-07-01"
        )
        canonical = pd.read_parquet(stale_delta.parent / "canonical.parquet")
        delta = pd.read_parquet(stale_delta)

        assert float(canonical.iloc[0]["close"]) == 111
        assert canonical.iloc[0]["as_of_date"] == "2026-07-02"
        assert delta.empty


def test_identical_metadata_conflicts_fail_closed():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        rows = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                close,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T00:00:00Z",
            )
            for close in (101, 102)
        ]

        try:
            dbs.write_daily_bars_snapshot(
                rows, reports_dir=reports, as_of_date="2026-07-02"
            )
        except ValueError as exc:
            assert "duplicate keys" in str(exc)
        else:
            raise AssertionError("conflicting duplicate input was accepted")


def test_delayed_refresh_repairs_from_newer_committed_delta():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        original = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-01",
                generated_at="2026-07-01T00:00:00Z",
            )
        ]
        newer = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                121,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T02:00:00Z",
            )
        ]
        delayed = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                111,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T01:00:00Z",
            )
        ]
        dbs.write_daily_bars_snapshot(
            original, reports_dir=reports, as_of_date="2026-07-01"
        )
        original_replace = dbs._replace_daily_bars_canonical

        def interrupt(*args, **kwargs):
            raise RuntimeError("simulated canonical interruption")

        dbs._replace_daily_bars_canonical = interrupt
        try:
            try:
                dbs.write_daily_bars_snapshot(
                    newer, reports_dir=reports, as_of_date="2026-07-02"
                )
            except RuntimeError as exc:
                assert "simulated canonical interruption" in str(exc)
            else:
                raise AssertionError("canonical interruption was not surfaced")
        finally:
            dbs._replace_daily_bars_canonical = original_replace

        delta_path = dbs.write_daily_bars_snapshot(
            delayed, reports_dir=reports, as_of_date="2026-07-02"
        )
        canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        delta = pd.read_parquet(delta_path)

        assert float(canonical.iloc[0]["close"]) == 121
        assert float(delta.iloc[0]["close"]) == 121


def test_newer_reversion_supersedes_interrupted_delta():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        original = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-01",
                generated_at="2026-07-01T00:00:00Z",
            )
        ]
        interrupted_change = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                121,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T02:00:00Z",
            )
        ]
        newer_reversion = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T03:00:00Z",
            )
        ]
        dbs.write_daily_bars_snapshot(
            original, reports_dir=reports, as_of_date="2026-07-01"
        )
        original_replace = dbs._replace_daily_bars_canonical

        def interrupt(*args, **kwargs):
            raise RuntimeError("simulated canonical interruption")

        dbs._replace_daily_bars_canonical = interrupt
        try:
            try:
                dbs.write_daily_bars_snapshot(
                    interrupted_change,
                    reports_dir=reports,
                    as_of_date="2026-07-02",
                )
            except RuntimeError as exc:
                assert "simulated canonical interruption" in str(exc)
            else:
                raise AssertionError("canonical interruption was not surfaced")
        finally:
            dbs._replace_daily_bars_canonical = original_replace

        delta_path = dbs.write_daily_bars_snapshot(
            newer_reversion,
            reports_dir=reports,
            as_of_date="2026-07-02",
        )
        canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        delta = pd.read_parquet(delta_path)

        assert float(canonical.iloc[0]["close"]) == 101
        assert canonical.iloc[0]["generated_at"] == "2026-07-02T03:00:00Z"
        assert delta.empty


def test_equal_version_conflict_keeps_committed_state():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        original = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                101,
                as_of_date="2026-07-01",
                generated_at="2026-07-01T00:00:00Z",
            )
        ]
        committed = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                121,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T02:00:00Z",
            )
        ]
        conflicting_retry = [
            _stored_bar(
                "AAPL",
                "2026-07-01",
                131,
                as_of_date="2026-07-02",
                generated_at="2026-07-02T02:00:00Z",
            )
        ]
        dbs.write_daily_bars_snapshot(
            original, reports_dir=reports, as_of_date="2026-07-01"
        )
        delta_path = dbs.write_daily_bars_snapshot(
            committed, reports_dir=reports, as_of_date="2026-07-02"
        )

        dbs.write_daily_bars_snapshot(
            conflicting_retry,
            reports_dir=reports,
            as_of_date="2026-07-02",
        )
        canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        delta = pd.read_parquet(delta_path)

        assert float(canonical.iloc[0]["close"]) == 121
        assert float(delta.iloc[0]["close"]) == 121


def test_daily_bars_rerun_repairs_interruption_after_delta_commit():
    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        first = [_stored_bar("AAPL", "2026-07-01", 101, as_of_date="2026-07-01", generated_at="2026-07-01T00:00:00Z")]
        second = [_stored_bar("AAPL", "2026-07-01", 111, as_of_date="2026-07-02", generated_at="2026-07-02T00:00:00Z")]
        dbs.write_daily_bars_snapshot(first, reports_dir=reports, as_of_date="2026-07-01")
        original_replace = dbs._replace_daily_bars_canonical

        def interrupt(*args, **kwargs):
            raise RuntimeError("simulated canonical interruption")

        dbs._replace_daily_bars_canonical = interrupt
        try:
            try:
                dbs.write_daily_bars_snapshot(second, reports_dir=reports, as_of_date="2026-07-02")
            except RuntimeError as exc:
                assert "simulated canonical interruption" in str(exc)
            else:
                raise AssertionError("canonical interruption was not surfaced")
        finally:
            dbs._replace_daily_bars_canonical = original_replace

        delta_path = reports / "market_data" / "daily_bars" / "2026-07-02.parquet"
        assert float(pd.read_parquet(delta_path).iloc[0]["close"]) == 111
        dbs.write_daily_bars_snapshot(second, reports_dir=reports, as_of_date="2026-07-02")
        canonical = pd.read_parquet(delta_path.parent / "canonical.parquet")
        assert float(canonical.iloc[0]["close"]) == 111
        assert float(pd.read_parquet(delta_path).iloc[0]["close"]) == 111


def main() -> int:
    tests = [
        test_build_rows_prefers_yahoo_adjusted_when_sources_match,
        test_build_rows_uses_sina_fallback_when_yahoo_unavailable,
        test_build_rows_blocks_yahoo_primary_on_large_sina_mismatch,
        test_write_daily_bars_snapshot_writes_parquet,
        test_refresh_daily_bars_streams_rows_without_building_full_list,
        test_write_daily_bars_snapshot_seeds_canonical_without_deleting_delta,
        test_first_canonical_seed_retains_tickers_missing_from_partial_refresh,
        test_daily_bars_canonical_merge_writes_only_business_changes_and_is_idempotent,
        test_stale_refresh_cannot_overwrite_newer_canonical_rows,
        test_identical_metadata_conflicts_fail_closed,
        test_delayed_refresh_repairs_from_newer_committed_delta,
        test_newer_reversion_supersedes_interrupted_delta,
        test_equal_version_conflict_keeps_committed_state,
        test_daily_bars_rerun_repairs_interruption_after_delta_commit,
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
