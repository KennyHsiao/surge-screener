#!/usr/bin/env python3
"""Self-contained tests for options_flow_scan (no network).

`options_free.analyze_options` is monkeypatched (via options_flow_scan._load) with
canned chain analyses so the real detection logic runs without the network.
Covers: bullish/bearish detection, the notional gate, V/OI / skew direction, the
notional+biggest aggregation, flow_score monotonicity, the bullflow post format,
never-raises, and unavailable → None.

Run:  .venv/bin/python scripts/test_options_flow_scan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import options_flow_scan as ofs  # noqa: E402


def _bullish(ticker):
    return {
        "available": True, "source": "yfinance_free", "ticker": ticker,
        "spot_price": 150.0, "expiration_analyzed": "2026-07-02",
        "details": {"6a": {
            "call_put_volume_ratio": 4.0, "put_call_ratio": 0.25,
            "max_call_voi": 13.0, "high_voi_strike_count": 4,
            "total_call_volume": 8000, "total_put_volume": 2000,
            "otm_call_volume_5_20pct": 5000}},
        "top_active_calls": [
            {"strike": 165.0, "volume": 1365, "open_interest": 1200, "voi": 1.1,
             "premium": 4.89, "notional": 667485},
            {"strike": 160.0, "volume": 900, "open_interest": 800, "voi": 1.1,
             "premium": 6.0, "notional": 540000},
            {"strike": 170.0, "volume": 50, "open_interest": 40, "voi": 1.2,
             "premium": 3.0, "notional": 15000},  # < MIN_STRIKE_VOL → excluded
        ],
        "top_active_puts": [],
    }


def _bearish(ticker):
    return {
        "available": True, "source": "yfinance_free", "ticker": ticker,
        "spot_price": 100.0, "expiration_analyzed": "2026-06-20",
        "details": {"6a": {
            "call_put_volume_ratio": 0.4, "put_call_ratio": 2.5,
            "max_call_voi": 2.0, "high_voi_strike_count": 1,
            "total_call_volume": 1000, "total_put_volume": 2500,
            "otm_call_volume_5_20pct": 200}},
        "top_active_calls": [],
        "top_active_puts": [
            {"strike": 95.0, "volume": 2000, "open_interest": 900, "voi": 2.2,
             "premium": 3.0, "notional": 600000}],
    }


def _weak(ticker):  # qualifies as bullish path but below the notional gate
    return {
        "available": True, "source": "yfinance_free", "ticker": ticker,
        "spot_price": 50.0, "expiration_analyzed": "2026-06-20",
        "details": {"6a": {
            "call_put_volume_ratio": 1.6, "put_call_ratio": 0.6,
            "max_call_voi": 2.0, "high_voi_strike_count": 1,
            "total_call_volume": 500, "total_put_volume": 300,
            "otm_call_volume_5_20pct": 100}},
        "top_active_calls": [
            {"strike": 52.0, "volume": 300, "open_interest": 250, "voi": 1.2,
             "premium": 0.3, "notional": 9000}],  # ~$9k ≪ gate
        "top_active_puts": [],
    }


def _patch(analyze_fn):
    """Route options_flow_scan._load('options_free','analyze_options') to a fake."""
    orig = ofs._load

    def _fake_load(mod, func):
        if (mod, func) == ("options_free", "analyze_options"):
            return analyze_fn
        return orig(mod, func)
    ofs._load = _fake_load


# ── Tests ────────────────────────────────────────────────────────────────────
def test_notional_and_biggest():
    rows = [{"notional": 100, "volume": 50}, {"notional": 600000, "volume": 2000},
            {"notional": 540000, "volume": 900}]
    total, biggest = ofs._notional_and_biggest(rows)
    assert total == 1_140_000, total      # the volume-50 row excluded (< MIN_STRIKE_VOL)
    assert biggest["notional"] == 600000


def test_flow_score_monotonic():
    lo = ofs._flow_score(300_000, 2, 2)
    hi = ofs._flow_score(5_000_000, 2, 2)
    assert 0 <= lo <= hi <= 100, (lo, hi)


def test_bullish_detection():
    _patch(_bullish)
    s = ofs._free_flow("NVDA")
    assert s and s["direction"] == "bullish"
    assert s["est_notional_usd"] == 1_207_485, s["est_notional_usd"]  # excludes the tiny strike
    assert s["biggest"]["strike"] == 165.0
    assert "多檔V/OI暴量" in s["tags"] and "峰值V/OI 13" in s["tags"]
    assert s["max_voi"] == 13.0 and s["call_put_ratio"] == 4.0


def test_bearish_detection():
    _patch(_bearish)
    s = ofs._free_flow("XYZ")
    assert s and s["direction"] == "bearish"
    assert s["est_notional_usd"] == 600000
    assert s["biggest"]["strike"] == 95.0


def test_below_gate_returns_none():
    _patch(_weak)
    assert ofs._free_flow("TINY", min_notional=250_000) is None


def test_unavailable_returns_none():
    _patch(lambda t: {"available": False, "reason": "no options"})
    assert ofs._free_flow("NOPE") is None


def test_never_raises_on_source_error():
    def _boom(t):
        raise RuntimeError("yfinance down")
    _patch(_boom)
    assert ofs._free_flow("BOOM") is None


def test_format_post_bullflow_style():
    _patch(_bullish)
    post = ofs.format_post(ofs._free_flow("NVDA"))
    assert post.startswith("🟢 *$NVDA*")
    assert "$1.2M" in post              # est notional
    assert "165C 7/2" in post           # biggest strike + expiry (M/D)
    assert "V/OI 13" in post
    assert "標籤:" in post

    _patch(_bearish)
    bear = ofs.format_post(ofs._free_flow("XYZ"))
    assert bear.startswith("🔴 *$XYZ*") and "95P 6/20" in bear, bear


def test_scan_ranks_by_score():
    # Two tickers via a fake that varies by ticker → ranked desc by flow_score.
    def _by_ticker(t):
        return _bullish(t) if t == "BIG" else _weak(t)
    _patch(_by_ticker)
    sigs = ofs.scan(["TINY", "BIG"], min_notional=250_000)
    assert [s["ticker"] for s in sigs] == ["BIG"]  # TINY filtered by gate


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
