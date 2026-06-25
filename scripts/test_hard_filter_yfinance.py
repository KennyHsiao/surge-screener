#!/usr/bin/env python3
"""Regression tests for Stage 1 yfinance stability guards."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent


def _load_hard_filter_with_fake_yfinance():
    fake = types.ModuleType("yfinance")
    calls = []
    cache_locations = []

    class FakeCache:
        @staticmethod
        def set_cache_location(path):
            cache_locations.append(str(path))

    def download(tickers, period, threads, progress):  # noqa: ARG001
        if isinstance(tickers, str):
            tickers = [tickers]
        calls.append({"tickers": list(tickers), "threads": threads, "period": period})
        idx = pd.date_range("2026-01-01", periods=3)
        cols = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], list(tickers)]
        )
        return pd.DataFrame(1.0, index=idx, columns=cols)

    fake.cache = FakeCache()
    fake.download = download

    old_yf = sys.modules.get("yfinance")
    sys.modules["yfinance"] = fake
    try:
        spec = importlib.util.spec_from_file_location(
            "hard_filter_under_test", ROOT / "scripts" / "01_hard_filter.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod, fake, calls, cache_locations
    finally:
        if old_yf is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = old_yf


def test_yfinance_cache_is_repo_local() -> None:
    _mod, _fake, _calls, cache_locations = _load_hard_filter_with_fake_yfinance()
    expected = str(ROOT / "reports" / ".cache" / "yfinance")
    if expected not in cache_locations:
        raise AssertionError(f"expected yfinance cache location {expected}, got {cache_locations}")


def test_batch_download_defaults_to_single_threaded() -> None:
    mod, _fake, calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    rows = mod.fetch_batch_data(["AAPL", "MSFT"], period="5d")
    if not rows:
        raise AssertionError("expected fake data rows")
    if calls[0]["threads"] is not False:
        raise AssertionError(f"expected threads=False, got {calls[0]['threads']!r}")


def test_batch_download_reports_progress() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    events = []

    def progress(event):
        events.append(event)

    rows = mod.fetch_batch_data(
        ["AAPL", "MSFT", "NVDA"], period="5d", batch_size=2,
        progress_callback=progress,
    )
    if sorted(rows) != ["AAPL", "MSFT", "NVDA"]:
        raise AssertionError(rows)
    if len(events) != 2:
        raise AssertionError(events)
    if events[0]["completed_batches"] != 1 or events[0]["total_batches"] != 2:
        raise AssertionError(events)
    if events[0]["downloaded_tickers"] != 2:
        raise AssertionError(events)
    if events[1]["completed_batches"] != 2 or events[1]["downloaded_tickers"] != 3:
        raise AssertionError(events)


def test_coverage_guard_rejects_hollow_download() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    if mod._coverage_ok(total=1503, available=878, min_coverage=0.70):
        raise AssertionError("878/1503 should not satisfy a 70% data coverage floor")
    if not mod._coverage_ok(total=1503, available=1200, min_coverage=0.70):
        raise AssertionError("1200/1503 should satisfy a 70% data coverage floor")


def test_hard_filter_thresholds_are_configurable() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    ind = {
        "ret_5d": 12.0,
        "ret_20d": 20.0,
        "avg_dollar_vol_20d": 8_000_000,
        "last_price": 12.0,
        "ma200": None,
        "gap_down_8pct_5d": False,
        "macd_current": 0.5,
        "macd_zero_cross_10d": False,
        "rsi_bullish_divergence": False,
        "has_reversal_pattern": False,
    }
    info = {"marketCap": 900_000_000}

    rules = dict(mod.DEFAULT_FILTER_RULES)
    ok, reason = mod.apply_hard_filters("TEST", ind, info, rules=rules)
    if not ok:
        raise AssertionError(reason)

    rules = dict(mod.DEFAULT_FILTER_RULES)
    rules["max_ret_5d"] = 10
    ok, reason = mod.apply_hard_filters("TEST", ind, info, rules=rules)
    if ok or "5 days" not in reason:
        raise AssertionError((ok, reason))

    rules = dict(mod.DEFAULT_FILTER_RULES)
    rules["min_avg_dollar_vol"] = 10_000_000
    ok, reason = mod.apply_hard_filters("TEST", ind, info, rules=rules)
    if ok or "Low liquidity" not in reason:
        raise AssertionError((ok, reason))


def test_make_candidates_local_exposes_yfinance_guards() -> None:
    makefile = (ROOT / "Makefile").read_text()
    expected_bits = [
        "YF_BATCH_SIZE ?= 25",
        "MIN_DATA_COVERAGE ?= 0.70",
        "MIN_AVG_DOLLAR_VOL ?= 5000000",
        "MIN_MARKET_CAP ?= 300000000",
        "MIN_PRICE ?= 5",
        "MAX_RET_5D ?= 30",
        "MAX_RET_20D ?= 60",
        "EARNINGS_EXCLUDE_DAYS ?= 2",
        "CANDIDATES_STATUS ?= reports/run_status/candidates-local.json",
        "--batch-size $(YF_BATCH_SIZE)",
        "--min-data-coverage $(MIN_DATA_COVERAGE)",
        "--min-avg-dollar-vol $(MIN_AVG_DOLLAR_VOL)",
        "--min-market-cap $(MIN_MARKET_CAP)",
        "--min-price $(MIN_PRICE)",
        "--max-ret-5d $(MAX_RET_5D)",
        "--max-ret-20d $(MAX_RET_20D)",
        "--earnings-exclude-days $(EARNINGS_EXCLUDE_DAYS)",
        "--status-file $(CANDIDATES_STATUS)",
    ]
    missing = [bit for bit in expected_bits if bit not in makefile]
    if missing:
        raise AssertionError(f"Makefile candidates-local missing yfinance guards: {missing}")


def main() -> None:
    tests = [
        test_yfinance_cache_is_repo_local,
        test_batch_download_defaults_to_single_threaded,
        test_batch_download_reports_progress,
        test_coverage_guard_rejects_hollow_download,
        test_hard_filter_thresholds_are_configurable,
        test_make_candidates_local_exposes_yfinance_guards,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
