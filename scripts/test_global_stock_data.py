#!/usr/bin/env python3
"""Self-contained tests for global_stock_data adapters.

The tests exercise parser/normalizer behavior only and never hit the network.
Run:  .venv/bin/python scripts/test_global_stock_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import global_stock_data as gsd  # noqa: E402


def test_eastmoney_market_list_accepts_list_diff():
    payload = {
        "data": {
            "total": 1,
            "diff": [{
                "f12": "AAPL",
                "f14": "Apple",
                "f2": 210.12,
                "f3": 123,
                "f4": 2.54,
                "f5": 1000,
                "f6": 210120,
                "f7": 456,
                "f15": 211.0,
                "f16": 208.0,
                "f17": 209.0,
                "f18": 207.58,
            }],
        }
    }

    out = gsd.parse_eastmoney_market_list_payload(payload, market="us_nasdaq")

    assert out["status"] == "ok", out
    assert out["total"] == 1, out
    assert out["stocks"][0]["ticker"] == "AAPL", out
    assert out["stocks"][0]["secid"] == "105.AAPL", out
    assert out["stocks"][0]["change_pct"] == 1.23, out
    assert out["stocks"][0]["amplitude"] == 4.56, out


def test_eastmoney_market_list_accepts_dict_diff():
    payload = {
        "data": {
            "total": 2,
            "diff": {
                "0": {"f12": "MSFT", "f14": "Microsoft", "f2": 510, "f3": -50},
                "1": {"f12": "NVDA", "f14": "NVIDIA", "f2": 160, "f3": 250},
            },
        }
    }

    out = gsd.parse_eastmoney_market_list_payload(payload, market="us_nyse")

    assert [s["ticker"] for s in out["stocks"]] == ["MSFT", "NVDA"], out
    assert out["stocks"][0]["secid"] == "106.MSFT", out
    assert out["stocks"][1]["change_pct"] == 2.5, out


def test_eastmoney_search_filters_supported_markets_and_adds_secid():
    payload = {
        "QuotationCodeTable": {
            "Data": [
                {"Code": "AAPL", "Name": "Apple", "MktNum": "105", "SecurityTypeName": "美股"},
                {"Code": "0700", "Name": "Tencent", "MktNum": "116", "SecurityTypeName": "港股"},
                {"Code": "000001", "Name": "Ping An", "MktNum": "90", "SecurityTypeName": "A股"},
            ]
        }
    }

    out = gsd.parse_eastmoney_search_payload(payload)

    assert out["count"] == 2, out
    assert out["securities"][0]["secid"] == "105.AAPL", out
    assert out["securities"][1]["market_name"] == "HK", out


def test_money_flow_parses_main_big_mid_small_fields():
    payload = {
        "data": {
            "klines": [
                "2026-06-30,1000000,-200000,300000,400000,600000,3.21",
                "2026-07-01,-500000,100000,-200000,-150000,-350000,-1.12",
            ]
        }
    }

    out = gsd.parse_eastmoney_money_flow_payload(payload)

    assert out["status"] == "ok", out
    assert out["count"] == 2, out
    first = out["rows"][0]
    assert first["date"] == "2026-06-30", first
    assert first["main_net"] == 1000000.0, first
    assert first["small_net"] == -200000.0, first
    assert first["mid_net"] == 300000.0, first
    assert first["big_net"] == 400000.0, first
    assert first["super_big_net"] == 600000.0, first
    assert first["main_pct"] == 3.21, first


def test_sina_quote_normalizes_core_fields():
    fields = ["Apple Inc.", "210.12", "1.23", "2026-07-01 16:00:00"]
    fields += [""] * 40
    fields[5] = "209.00"
    fields[6] = "211.00"
    fields[7] = "208.00"
    fields[8] = "260.00"
    fields[9] = "150.00"
    fields[10] = "1234567"
    fields[12] = "3200000000000"
    fields[13] = "6.42"
    fields[14] = "32.7"
    fields[26] = "207.58"
    text = 'var hq_str_gb_aapl="' + ",".join(fields) + '";'

    out = gsd.parse_sina_us_quote_text(text)

    assert out["status"] == "ok", out
    assert out["name"] == "Apple Inc.", out
    assert out["price"] == 210.12, out
    assert out["market_cap"] == 3200000000000.0, out
    assert out["eps"] == 6.42, out
    assert out["pe"] == 32.7, out


def test_tencent_quote_normalizes_core_fields():
    fields = [""] * 72
    fields[1] = "Apple"
    fields[3] = "210.12"
    fields[4] = "207.58"
    fields[5] = "209.00"
    fields[6] = "1234567"
    fields[27] = "Apple Inc."
    fields[30] = "20260701160000"
    fields[32] = "1.23"
    fields[33] = "211.00"
    fields[34] = "208.00"
    fields[35] = "260.00"
    fields[36] = "150.00"
    fields[44] = "3200000000000"
    fields[53] = "32.7"
    fields[56] = "45.1"
    text = 'v_usAAPL="' + "~".join(fields) + '";'

    out = gsd.parse_tencent_us_quote_text(text)

    assert out["status"] == "ok", out
    assert out["name"] == "Apple", out
    assert out["name_en"] == "Apple Inc.", out
    assert out["price"] == 210.12, out
    assert out["pb"] == 45.1, out


def test_sina_daily_bars_parses_jsonp_payload():
    text = 'var US_MinKService.getDailyK=([{"d":"2026-06-30","o":"100","h":"110","l":"95","c":"108","v":"1234"}]);'

    out = gsd.parse_sina_us_daily_bars_text(text)

    assert out["status"] == "ok", out
    assert out["count"] == 1, out
    assert out["bars"][0]["date"] == "2026-06-30", out
    assert out["bars"][0]["close"] == 108.0, out
    assert out["bars"][0]["volume"] == 1234, out


def test_malformed_payloads_fail_closed():
    assert gsd.parse_eastmoney_money_flow_payload({"data": {"klines": ["bad"]}})["count"] == 0
    assert gsd.parse_sina_us_quote_text("bad")["status"] == "unavailable"
    assert gsd.parse_tencent_us_quote_text("bad")["status"] == "unavailable"
    assert gsd.parse_sina_us_daily_bars_text("bad")["status"] == "unavailable"


def main() -> int:
    tests = [
        test_eastmoney_market_list_accepts_list_diff,
        test_eastmoney_market_list_accepts_dict_diff,
        test_eastmoney_search_filters_supported_markets_and_adds_secid,
        test_money_flow_parses_main_big_mid_small_fields,
        test_sina_quote_normalizes_core_fields,
        test_tencent_quote_normalizes_core_fields,
        test_sina_daily_bars_parses_jsonp_payload,
        test_malformed_payloads_fail_closed,
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
        print("global stock data adapter tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
