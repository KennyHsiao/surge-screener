#!/usr/bin/env python3
"""Self-contained tests for normalized fundamental metrics snapshots.

Run:  .venv/bin/python scripts/test_fundamental_metrics_store.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "fundamental_metrics_store_under_test",
        ROOT / "scripts" / "fundamental_metrics_store.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _sec_companyfacts() -> dict:
    base_fact = {
        "end": "2026-03-28",
        "fy": 2026,
        "fp": "Q2",
        "form": "10-Q",
        "filed": "2026-05-02",
        "accn": "0000320193-26-000050",
    }

    def concept(label: str, unit: str, value: float) -> dict:
        return {"label": label, "units": {unit: [{**base_fact, "val": value}]}}

    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": concept("Revenue", "USD", 95359000000),
                "NetIncomeLoss": concept("Net Income", "USD", 24780000000),
                "EarningsPerShareDiluted": concept("Diluted EPS", "USD/shares", 1.65),
                "Assets": concept("Assets", "USD", 331233000000),
                "Liabilities": concept("Liabilities", "USD", 264904000000),
                "StockholdersEquity": concept("Stockholders' Equity", "USD", 66329000000),
                "NetCashProvidedByUsedInOperatingActivities": concept("Operating Cash Flow", "USD", 29935000000),
                "ResearchAndDevelopmentExpense": concept("Research and Development", "USD", 7903000000),
                "PaymentsForRepurchaseOfCommonStock": concept("Share Repurchases", "USD", 23456000000),
            },
        },
    }


def _eastmoney_gmainindicator() -> dict:
    return {
        "result": {
            "data": [{
                "SECURITY_CODE": "AAPL",
                "REPORT_DATE": "2026-03-31 00:00:00",
                "REPORT_YEAR": "2026",
                "REPORT_PERIOD": "Q1",
                "REPORT_TYPE": "一季报",
                "BASIC_EPS": "1.52",
                "ROEJQ": "18.5",
                "ROA": "7.1",
                "GROSS_PROFIT_RATIO": "45.6",
                "ASSET_LIAB_RATIO": "31.4",
            }],
        },
    }


def test_sec_companyfacts_rows_are_long_form_official_metrics() -> None:
    mod = _load_module()

    rows = mod.rows_from_sec_companyfacts(
        "AAPL",
        "0000320193",
        _sec_companyfacts(),
        as_of_date="2026-07-01",
    )
    metrics = {row["metric"] for row in rows}

    expected = {
        "revenue",
        "net_income",
        "diluted_eps",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "operating_cash_flow",
        "research_and_development",
        "share_repurchases",
    }
    if metrics != expected:
        raise AssertionError(metrics)

    revenue = next(row for row in rows if row["metric"] == "revenue")
    if revenue["ticker"] != "AAPL" or revenue["cik"] != "0000320193":
        raise AssertionError(revenue)
    if revenue["source"] != "sec_companyfacts" or revenue["confidence"] < 90:
        raise AssertionError(revenue)
    if revenue["period_end"] != "2026-03-28" or revenue["value"] != 95359000000:
        raise AssertionError(revenue)


def test_eastmoney_gmainindicator_rows_are_secondary_metrics() -> None:
    mod = _load_module()

    rows = mod.rows_from_eastmoney_gmainindicator(
        "AAPL",
        _eastmoney_gmainindicator(),
        as_of_date="2026-07-01",
    )
    by_metric = {row["metric"]: row for row in rows}

    expected = {"eps", "return_on_equity", "return_on_assets", "gross_margin", "asset_liability_ratio"}
    if set(by_metric) != expected:
        raise AssertionError(by_metric)
    if by_metric["gross_margin"]["value"] != 45.6:
        raise AssertionError(by_metric["gross_margin"])
    if by_metric["gross_margin"]["source"] != "eastmoney_gmainindicator":
        raise AssertionError(by_metric["gross_margin"])
    if by_metric["gross_margin"]["confidence"] >= 90:
        raise AssertionError(by_metric["gross_margin"])


def test_build_and_write_fundamental_metrics_snapshot() -> None:
    mod = _load_module()
    snapshot = mod.build_fundamental_metrics_snapshot(
        {"AAPL": "0000320193"},
        sec_fetcher=lambda cik: _sec_companyfacts(),
        eastmoney_fetcher=lambda ticker: _eastmoney_gmainindicator(),
        as_of_date="2026-07-01",
    )

    if snapshot["row_count"] != 14:
        raise AssertionError(snapshot)
    if {row["source"] for row in snapshot["rows"]} != {"sec_companyfacts", "eastmoney_gmainindicator"}:
        raise AssertionError(snapshot["rows"])

    with tempfile.TemporaryDirectory() as d:
        out = mod.write_fundamental_metrics_snapshot(snapshot, reports_dir=Path(d) / "reports")
        latest = out.parent / "latest.json"
        if out.name != "2026-07-01.json" or not out.is_file() or not latest.is_file():
            raise AssertionError((out, latest))
        loaded = json.loads(out.read_text(encoding="utf-8"))
        if loaded["row_count"] != 14 or loaded["rows"][0]["as_of_date"] != "2026-07-01":
            raise AssertionError(loaded)


def test_refresh_fundamental_metrics_passes_universe_secid_to_eastmoney() -> None:
    mod = _load_module()
    seen = {}

    def fake_sec(_cik):
        return _sec_companyfacts()

    def fake_eastmoney(ticker, *, secid=None):
        seen[ticker] = secid
        return _eastmoney_gmainindicator()

    with tempfile.TemporaryDirectory() as d:
        reports = Path(d) / "reports"
        universe = reports / "universe"
        universe.mkdir(parents=True)
        (universe / "2026-07-01.json").write_text(json.dumps({
            "as_of_date": "2026-07-01",
            "securities": [{
                "ticker": "DELL",
                "cik": "0001571996",
                "eastmoney_secid": "106.DELL",
            }],
        }), encoding="utf-8")

        mod.refresh_fundamental_metrics(
            tickers=["DELL"],
            reports_dir=reports,
            as_of_date="2026-07-01",
            sec_fetcher=fake_sec,
            eastmoney_fetcher=fake_eastmoney,
        )

    if seen.get("DELL") != "106.DELL":
        raise AssertionError(seen)


def main() -> int:
    tests = [
        test_sec_companyfacts_rows_are_long_form_official_metrics,
        test_eastmoney_gmainindicator_rows_are_secondary_metrics,
        test_build_and_write_fundamental_metrics_snapshot,
        test_refresh_fundamental_metrics_passes_universe_secid_to_eastmoney,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - self-contained test runner
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failures:
        print(f"\n{failures}/{len(tests)} failed")
        return 1
    print(f"\n{len(tests)}/{len(tests)} passed")
    print("fundamental metrics store tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
