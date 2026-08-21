#!/usr/bin/env python3
"""Regression tests for Stage 1 yfinance stability guards."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
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

    def download(tickers, period, threads, progress, auto_adjust):  # noqa: ARG001
        if isinstance(tickers, str):
            tickers = [tickers]
        calls.append({
            "tickers": list(tickers),
            "threads": threads,
            "period": period,
            "auto_adjust": auto_adjust,
        })
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


def test_gap_down_is_warning_not_hard_reject() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    ind = {
        "ret_5d": 12.0,
        "ret_20d": 20.0,
        "avg_dollar_vol_20d": 8_000_000,
        "last_price": 12.0,
        "ma200": None,
        "gap_down_8pct_5d": True,
        "macd_current": 0.5,
        "macd_zero_cross_10d": False,
        "rsi_bullish_divergence": False,
        "has_reversal_pattern": False,
    }
    info = {"marketCap": 900_000_000}

    ok, reason = mod.apply_hard_filters("TEST", ind, info)
    if not ok:
        raise AssertionError(f"gap-down risk should warn, not reject: {reason}")

    warnings = mod.build_filter_warnings(ind)
    if "Recent gap-down >8% in last 5 days" not in warnings:
        raise AssertionError(warnings)


def test_compute_indicators_emits_chandelier_inputs_from_underlying_ohlcv() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    rows = []
    for i in range(60):
        rows.append({
            "Open": 100 + i,
            "High": 110 + i,
            "Low": 80 + i,
            "Close": 100 + i,
            "Volume": 1_000_000 + i,
        })
    df = pd.DataFrame(rows, index=pd.date_range("2026-01-01", periods=60, freq="B"))

    ind = mod.compute_indicators(df)

    if ind["atr14"] != 30.0:
        raise AssertionError(ind)
    if ind["highest_high_22d"] != 169.0:
        raise AssertionError(ind)
    if ind["lowest_low_22d"] != 118.0:
        raise AssertionError(ind)
    if ind["support_20d"] != 119.0:
        raise AssertionError(ind)


def _technical_frame(*, periods: int = 230, slope: float = 0.35) -> pd.DataFrame:
    index = pd.date_range("2025-09-01", periods=periods, freq="B")
    close = 80.0 + np.arange(periods) * slope + np.sin(np.arange(periods) / 8.0)
    return pd.DataFrame({
        "Open": close - 0.4,
        "High": close + 1.2,
        "Low": close - 1.0,
        "Close": close,
        "Volume": 1_000_000 + np.arange(periods) * 5_000,
    }, index=index)


def test_compute_indicators_emits_versioned_technical_evidence() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    ind = mod.compute_indicators(_technical_frame())
    evidence = ind["technical_evidence"]

    if evidence["schema_version"] != "technical_evidence_v1":
        raise AssertionError(evidence)
    if evidence["source"]["provider"] != "yfinance":
        raise AssertionError(evidence)
    if evidence["history_sessions"] != 230 or not evidence.get("as_of_date"):
        raise AssertionError(evidence)

    inputs = evidence["inputs"]
    for key in (
        "price", "ma50", "ma150", "ma200", "ma200_1m_ago",
        "low_52w", "high_52w", "rs_trailing_return_pct",
        "today_volume", "avg_volume_20d", "volume_ratio_20d",
        "close_position", "price_change_1d", "daily_macd",
        "daily_macd_signal", "daily_macd_golden_cross_10d",
        "daily_macd_zero_cross_10d",
        "weekly_macd_histogram", "weekly_macd_histogram_previous",
        "w_bottom_shape",
    ):
        if inputs.get(key, {}).get("status") != "available":
            raise AssertionError((key, inputs.get(key)))

    for unsupported in (
        "weekly_rsi_bullish_divergence", "w_bottom_neckline_breakout",
        "vcp", "cup_with_handle", "flat_base", "bull_flag",
        "higher_highs_lows_4w", "inverse_head_shoulders",
    ):
        item = inputs.get(unsupported, {})
        if item.get("status") != "missing" or not item.get("reason"):
            raise AssertionError((unsupported, item))

    if inputs["rs_rating"]["status"] != "missing":
        raise AssertionError("RS must be assigned from the complete same-scan universe")

    frame = _technical_frame()
    close = frame["Close"].to_numpy()
    volume = frame["Volume"].to_numpy()
    expected = {
        "ma150": float(np.mean(close[-150:])),
        "ma200": float(np.mean(close[-200:])),
        "ma200_1m_ago": float(np.mean(close[-221:-21])),
        "low_52w": float(frame["Low"].iloc[-230:].min()),
        "high_52w": float(frame["High"].iloc[-230:].max()),
        "avg_volume_20d": float(np.mean(volume[-21:-1])),
        "volume_ratio_20d": float(volume[-1] / np.mean(volume[-21:-1])),
        "close_position": float(
            (frame["Close"].iloc[-1] - frame["Low"].iloc[-1])
            / (frame["High"].iloc[-1] - frame["Low"].iloc[-1])
        ),
    }
    for key, value in expected.items():
        if not np.isclose(inputs[key]["value"], value):
            raise AssertionError((key, inputs[key], value))


def test_same_scan_relative_strength_rating_has_provenance() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    indicators = {
        "SLOW": mod.compute_indicators(_technical_frame(slope=0.05)),
        "MID": mod.compute_indicators(_technical_frame(slope=0.20)),
        "FAST": mod.compute_indicators(_technical_frame(slope=0.50)),
        "SHORT": mod.compute_indicators(_technical_frame(periods=80, slope=0.80)),
    }

    mod.assign_relative_strength_ratings(indicators)

    ratings = {
        ticker: row["technical_evidence"]["inputs"]["rs_rating"]
        for ticker, row in indicators.items()
    }
    if not (ratings["SLOW"]["value"] < ratings["MID"]["value"]
            < ratings["FAST"]["value"]):
        raise AssertionError(ratings)
    for ticker in ("SLOW", "MID", "FAST"):
        item = ratings[ticker]
        if item.get("status") != "available":
            raise AssertionError(item)
        if item.get("sample_size") != 3:
            raise AssertionError(item)
        if item.get("method") != "same_scan_trailing_return_percentile":
            raise AssertionError(item)
    if ratings["SHORT"].get("status") != "missing" or not ratings["SHORT"].get("reason"):
        raise AssertionError(ratings["SHORT"])


def test_short_history_uses_explicit_missing_reasons() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    ind = mod.compute_indicators(_technical_frame(periods=80))
    inputs = ind["technical_evidence"]["inputs"]

    for key in ("ma150", "ma200", "ma200_1m_ago", "low_52w", "high_52w"):
        item = inputs[key]
        if item.get("status") != "missing" or not item.get("reason"):
            raise AssertionError((key, item))

    missing_volume = _technical_frame()
    missing_volume.loc[missing_volume.index[-1], "Volume"] = np.nan
    ind = mod.compute_indicators(missing_volume)
    if ind["technical_evidence"]["inputs"]["today_volume"]["status"] != "missing":
        raise AssertionError(ind["technical_evidence"]["inputs"]["today_volume"])
    if ind["avg_dollar_vol_20d"] is not None:
        raise AssertionError("incomplete 20-session volume must not produce liquidity evidence")
    ok, reason = mod.apply_hard_filters(
        "TEST", ind, {"marketCap": 900_000_000}
    )
    if ok or "Liquidity unavailable" not in reason:
        raise AssertionError((ok, reason))

    missing_column = _technical_frame().drop(columns=["Volume"])
    if mod.compute_indicators(missing_column) is not None:
        raise AssertionError("missing Volume column must fail closed")


def test_trailing_partial_yfinance_row_is_ignored() -> None:
    mod, _fake, _calls, _cache_locations = _load_hard_filter_with_fake_yfinance()
    complete = _technical_frame()
    partial_date = complete.index[-1] + pd.offsets.BDay(1)
    with_partial = pd.concat([
        complete,
        pd.DataFrame([{
            "Open": np.nan,
            "High": np.nan,
            "Low": np.nan,
            "Close": np.nan,
            "Volume": 9_999_999,
        }], index=[partial_date]),
    ])

    expected = mod.compute_indicators(complete)
    actual = mod.compute_indicators(with_partial)

    if actual is None:
        raise AssertionError("a trailing partial quote must not discard valid history")
    if actual["technical_evidence"]["history_sessions"] != len(complete):
        raise AssertionError(actual["technical_evidence"])
    if actual["technical_evidence"]["as_of_date"] != complete.index[-1].date().isoformat():
        raise AssertionError(actual["technical_evidence"])
    if actual["last_price"] != expected["last_price"]:
        raise AssertionError((actual["last_price"], expected["last_price"]))


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
        test_gap_down_is_warning_not_hard_reject,
        test_compute_indicators_emits_chandelier_inputs_from_underlying_ohlcv,
        test_compute_indicators_emits_versioned_technical_evidence,
        test_same_scan_relative_strength_rating_has_provenance,
        test_short_history_uses_explicit_missing_reasons,
        test_trailing_partial_yfinance_row_is_ignored,
        test_make_candidates_local_exposes_yfinance_guards,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
