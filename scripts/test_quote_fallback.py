#!/usr/bin/env python3
"""Self-contained tests for quote fallback routing.

Run:  .venv/bin/python scripts/test_quote_fallback.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

import quote_fallback as qf  # noqa: E402


class FakeYFTicker:
    fast_info = {
        "last_price": 123.45,
        "market_cap": 1_000_000_000,
        "year_high": 150.0,
        "year_low": 90.0,
    }


def _unavailable(source: str):
    return {"status": "unavailable", "source": source}


def test_fetch_quote_prefers_current_yfinance_object():
    calls: list[str] = []

    def sina(_ticker):
        calls.append("sina")
        return {"status": "ok", "source": "sina_us_quote", "price": 10.0}

    out = qf.fetch_quote(
        "aapl",
        yf_ticker=FakeYFTicker(),
        providers={"sina": sina},
    )

    assert out["ticker"] == "AAPL", out
    assert out["price"] == 123.45, out
    assert out["source"] == "yfinance"
    assert out["fields"]["market_cap"] == 1_000_000_000
    assert calls == [], calls


def test_fetch_quote_falls_through_sina_then_tencent():
    calls: list[str] = []

    def sina(_ticker):
        calls.append("sina")
        return _unavailable("sina_us_quote")

    def tencent(_ticker):
        calls.append("tencent")
        return {
            "status": "ok",
            "source": "tencent_us_quote",
            "price": 88.0,
            "market_cap": 2_000_000,
            "pe": 24.0,
            "pb": 4.0,
            "high_52w": 100.0,
            "low_52w": 50.0,
            "timestamp": "2026-07-01 10:00:00",
        }

    out = qf.fetch_quote("MSFT", providers={"sina": sina, "tencent": tencent})

    assert calls == ["sina", "tencent"], calls
    assert out["source"] == "tencent_us_quote", out
    assert out["price"] == 88.0, out
    assert out["fields"]["week_52_high"] == 100.0, out
    assert out["stale"] is False, out


def test_fetch_quote_uses_eastmoney_last():
    calls: list[str] = []

    def eastmoney(_ticker):
        calls.append("eastmoney")
        return {"status": "ok", "source": "eastmoney_push2_quote", "price": 77.0}

    out = qf.fetch_quote(
        "TSLA",
        providers={
            "sina": lambda _ticker: _unavailable("sina_us_quote"),
            "tencent": lambda _ticker: _unavailable("tencent_us_quote"),
            "eastmoney": eastmoney,
        },
    )

    assert calls == ["eastmoney"], calls
    assert out["source"] == "eastmoney_push2_quote", out
    assert out["price"] == 77.0, out


def test_quote_ttl_uses_market_hours():
    ny = ZoneInfo("America/New_York")
    assert qf.quote_ttl(datetime(2026, 7, 1, 10, 0, tzinfo=ny)) == 60
    assert qf.quote_ttl(datetime(2026, 7, 1, 18, 0, tzinfo=ny)) == 900
    assert qf.quote_ttl(datetime(2026, 7, 4, 10, 0, tzinfo=ny)) == 900


def test_get_quote_uses_cache_without_db_table():
    recorded: dict = {}

    def fake_cache(namespace, params, ttl, compute, should_cache=None):
        recorded.update({"namespace": namespace, "params": params, "ttl": ttl})
        value = compute()
        assert should_cache(value) is True
        return value

    out = qf.get_quote(
        "NVDA",
        now=datetime(2026, 7, 1, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        cache_get_or_compute=fake_cache,
        providers={
            "sina": lambda _ticker: {"status": "ok", "source": "sina_us_quote", "price": 500.0},
        },
    )

    assert out["price"] == 500.0, out
    assert recorded["namespace"] == "quote_fallback", recorded
    assert recorded["params"] == {"ticker": "NVDA", "include_yfinance": False}, recorded
    assert recorded["ttl"] == 60, recorded
    assert "daily_quotes" not in qf.__dict__, "quote fallback must stay cache-only"


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
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
        print("quote fallback tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
