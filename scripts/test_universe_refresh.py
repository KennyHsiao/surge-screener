#!/usr/bin/env python3
"""Self-contained tests for daily universe refresh artifacts.

Run:  .venv/bin/python scripts/test_universe_refresh.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import universe_refresh as ur  # noqa: E402


def _write_canonical_roles(reports: Path, ticker: str) -> None:
    state_dir = reports / "industry_roles"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "review-state.json").write_text(json.dumps({
        "schema_version": 1,
        "revision": 1,
        "taxonomy_version": 1,
        "updated_at": "2026-08-06T02:00:00Z",
        "overrides": {
            "version": 1,
            "tickers": {ticker: {"primary_role": "ai_server_odm"}},
        },
        "suggestions": {"generated_at": None, "suggestions": []},
        "receipts": [],
        "audit": [{
            "transaction_id": "00000000-0000-4000-8000-000000000001",
            "action": "restore",
            "ticker": None,
            "revision": 1,
            "committed_at": "2026-08-06T02:00:00Z",
            "request_hash": "0" * 64,
        }],
    }), encoding="utf-8")


def _fake_market_list(market: str, page: int = 1, page_size: int = 100, **_kwargs):
    assert page == 1, "test fixture exposes one page per market"
    rows = {
        "us_nasdaq": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "NASDAQ",
                "secid": "105.AAPL",
                "security_type": "stock",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corp.",
                "market": "NASDAQ",
                "secid": "105.MSFT",
                "security_type": "stock",
            },
        ],
        "us_nyse": [
            {
                "ticker": "BABA",
                "name": "Alibaba Group",
                "market": "NYSE",
                "secid": "106.BABA",
                "security_type": "stock",
            },
        ],
        "us_etf": [
            {
                "ticker": "SOXX",
                "name": "iShares Semiconductor ETF",
                "market": "US_OTHER",
                "secid": "107.SOXX",
                "security_type": "ETF",
            },
        ],
    }[market]
    return {"status": "ok", "total": len(rows), "stocks": rows, "source": "fixture"}


def test_build_universe_snapshot_merges_eastmoney_and_sec_ids():
    cik_map = {
        "AAPL": {"cik": "0000320193", "company": "Apple Inc."},
        "MSFT": "0000789019",
    }

    snapshot = ur.build_universe_snapshot(
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        market_list_fetcher=_fake_market_list,
        cik_map=cik_map,
    )

    assert snapshot["as_of_date"] == "2026-07-01", snapshot
    assert snapshot["coverage"]["eastmoney_total"] == 4, snapshot
    assert snapshot["coverage"]["sec_mapped"] == 2, snapshot
    assert snapshot["coverage"]["missing_cik"] == 2, snapshot
    tickers = {row["ticker"]: row for row in snapshot["securities"]}
    assert tickers["AAPL"]["exchange"] == "NASDAQ", tickers
    assert tickers["AAPL"]["eastmoney_secid"] == "105.AAPL", tickers
    assert tickers["AAPL"]["cik"] == "0000320193", tickers
    assert tickers["SOXX"]["asset_type"] == "etf", tickers
    assert tickers["SOXX"]["cik"] is None, tickers


def test_us_other_market_does_not_default_everything_to_etf():
    def fake_other_market(market: str, page: int = 1, page_size: int = 100, **_kwargs):
        assert market == "us_etf"
        return {
            "status": "ok",
            "total": 1,
            "stocks": [{
                "ticker": "XYZR",
                "name": "Example Other Listing",
                "market": "US_OTHER",
                "secid": "107.XYZR",
            }],
        }

    snapshot = ur.build_universe_snapshot(
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        market_list_fetcher=fake_other_market,
        cik_map={},
        markets={"us_etf": "US_OTHER"},
    )

    assert snapshot["securities"][0]["asset_type"] == "other", snapshot


def test_build_universe_snapshot_uses_platform_fallback_when_provider_is_empty():
    def empty_market_list(market: str, page: int = 1, page_size: int = 100, **_kwargs):
        return {"status": "ok", "total": 0, "stocks": [], "source": "fixture"}

    snapshot = ur.build_universe_snapshot(
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        market_list_fetcher=empty_market_list,
        cik_map={"AAPL": {"cik": "0000320193", "company": "Apple Inc."}},
        fallback_tickers=["AAPL", "MSFT"],
    )

    tickers = {row["ticker"]: row for row in snapshot["securities"]}
    assert snapshot["coverage"]["eastmoney_total"] == 0, snapshot
    assert snapshot["coverage"]["fallback_total"] == 2, snapshot
    assert tickers["AAPL"]["cik"] == "0000320193", tickers
    assert tickers["AAPL"]["source_status"] == "platform_fallback", tickers
    assert tickers["MSFT"]["exchange"] == "US_UNKNOWN", tickers


def test_collect_platform_fallback_tickers_from_reports_and_content():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        rankings = reports / "candidate_rankings"
        rankings.mkdir(parents=True)
        content.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "version": 1,
            "roles": {"ai_server_odm": {"name": "AI Server / ODM"}},
        }), encoding="utf-8")
        (rankings / "2026-07-01.json").write_text(json.dumps({
            "ranked_candidates": [{"ticker": "AAPL"}],
        }), encoding="utf-8")
        (reports / "watchlist.json").write_text(json.dumps({
            "items": [{"ticker": "MSFT"}],
        }), encoding="utf-8")
        (content / "theme_baskets.json").write_text(json.dumps({
            "themes": {"AI Infra": {"tickers": ["NVDA"]}},
        }), encoding="utf-8")

        tickers = ur.collect_platform_fallback_tickers(reports_dir=reports, content_dir=content)

    assert tickers == ["AAPL", "MSFT", "NVDA"], tickers


def test_collect_platform_tickers_prefers_canonical_and_fails_soft_without_stale_fallback():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "version": 1,
            "roles": {"ai_server_odm": {"name": "AI Server / ODM"}},
        }), encoding="utf-8")
        (content / "industry_role_overrides.json").write_text(json.dumps({
            "version": 1,
            "tickers": {"STALE": {"primary_role": "ai_server_odm"}},
        }), encoding="utf-8")
        (reports / "watchlist.json").write_text(json.dumps({
            "items": [{"ticker": "AAPL"}],
        }), encoding="utf-8")
        _write_canonical_roles(reports, "NVDA")

        canonical = ur.collect_platform_fallback_tickers(
            reports_dir=reports,
            content_dir=content,
        )
        (reports / "industry_roles" / "review-state.json").write_text(
            "{",
            encoding="utf-8",
        )
        invalid = ur.collect_platform_fallback_tickers(
            reports_dir=reports,
            content_dir=content,
        )

    assert canonical == ["AAPL", "NVDA"], canonical
    assert invalid == ["AAPL"], invalid
    assert "STALE" not in invalid


def test_write_universe_snapshot_writes_dated_json():
    snapshot = ur.build_universe_snapshot(
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        market_list_fetcher=_fake_market_list,
        cik_map={"AAPL": "0000320193"},
    )
    with TemporaryDirectory() as td:
        out = ur.write_universe_snapshot(snapshot, reports_dir=Path(td) / "reports")
        saved = json.loads(out.read_text(encoding="utf-8"))

    assert out.name == "2026-07-01.json", out
    assert out.parent.name == "universe", out
    assert saved["securities"][0]["ticker"] == "AAPL", saved


def main() -> int:
    tests = [
        test_build_universe_snapshot_merges_eastmoney_and_sec_ids,
        test_us_other_market_does_not_default_everything_to_etf,
        test_build_universe_snapshot_uses_platform_fallback_when_provider_is_empty,
        test_collect_platform_fallback_tickers_from_reports_and_content,
        test_collect_platform_tickers_prefers_canonical_and_fails_soft_without_stale_fallback,
        test_write_universe_snapshot_writes_dated_json,
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
        print("universe refresh tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
