#!/usr/bin/env python3
"""Self-contained tests for Eastmoney money-flow artifacts.

Run:  .venv/bin/python scripts/test_eastmoney_money_flow.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import eastmoney_money_flow as emf  # noqa: E402


def _fake_flow(secid: str, limit: int = 120, **_kwargs):
    if secid == "105.AAPL":
        return {
            "status": "ok",
            "source": "eastmoney_push2his_fflow",
            "rows": [
                {
                    "date": "2026-06-30",
                    "main_net": 1000000.0,
                    "main_pct": 3.2,
                    "super_big_net": 600000.0,
                    "big_net": 400000.0,
                    "mid_net": 100000.0,
                    "small_net": -200000.0,
                }
            ],
        }
    return {"status": "unavailable", "source": "eastmoney_push2his_fflow", "rows": []}


def test_build_money_flow_snapshot_marks_publishable_by_coverage():
    snapshot = emf.build_money_flow_snapshot(
        ["AAPL", "MSFT"],
        secid_map={"AAPL": "105.AAPL", "MSFT": "105.MSFT"},
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        flow_fetcher=_fake_flow,
    )

    assert snapshot["coverage"]["requested"] == 2, snapshot
    assert snapshot["coverage"]["resolved"] == 1, snapshot
    assert snapshot["coverage"]["unavailable"] == 1, snapshot
    assert snapshot["publishable"] is False, snapshot
    assert snapshot["rows"][0]["ticker"] == "AAPL", snapshot
    assert snapshot["rows"][0]["secid"] == "105.AAPL", snapshot
    assert snapshot["rows"][0]["main_net"] == 1000000.0, snapshot
    assert snapshot["rows"][0]["source"] == "eastmoney_push2his", snapshot


def test_build_money_flow_snapshot_is_publishable_when_coverage_passes():
    snapshot = emf.build_money_flow_snapshot(
        ["AAPL"],
        secid_map={"AAPL": "105.AAPL"},
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        flow_fetcher=_fake_flow,
    )

    assert snapshot["publishable"] is True, snapshot
    assert snapshot["coverage"]["coverage_ratio"] == 1.0, snapshot


def test_build_money_flow_snapshot_resolves_missing_secid_with_search():
    def fake_search(keyword: str, count: int = 10, **_kwargs):
        assert keyword == "AAPL"
        return {
            "status": "ok",
            "securities": [{"ticker": "AAPL", "secid": "105.AAPL"}],
        }

    snapshot = emf.build_money_flow_snapshot(
        ["AAPL"],
        secid_map={},
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        flow_fetcher=_fake_flow,
        secid_resolver=fake_search,
    )

    assert snapshot["publishable"] is True, snapshot
    assert snapshot["coverage"]["resolved"] == 1, snapshot
    assert snapshot["rows"][0]["secid"] == "105.AAPL", snapshot


def test_write_money_flow_snapshot_writes_dated_and_latest_json():
    snapshot = emf.build_money_flow_snapshot(
        ["AAPL"],
        secid_map={"AAPL": "105.AAPL"},
        as_of_date="2026-07-01",
        generated_at="2026-07-01T00:00:00Z",
        flow_fetcher=_fake_flow,
    )
    with TemporaryDirectory() as td:
        out = emf.write_money_flow_snapshot(snapshot, reports_dir=Path(td) / "reports")
        latest = out.parent / "latest.json"
        latest_exists = latest.is_file()
        saved = json.loads(out.read_text(encoding="utf-8"))
        latest_saved = json.loads(latest.read_text(encoding="utf-8"))

    assert out.name == "2026-07-01.json", out
    assert latest_exists, latest
    assert saved["rows"][0]["ticker"] == "AAPL", saved
    assert latest_saved["as_of_date"] == "2026-07-01", latest_saved


def test_collect_money_flow_tickers_from_platform_sources():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        rankings = reports / "candidate_rankings"
        rankings.mkdir(parents=True)
        content.mkdir()
        (rankings / "2026-07-01.json").write_text(json.dumps({
            "source": "candidate_rankings",
            "ranked_candidates": [{"ticker": "AAPL"}],
        }), encoding="utf-8")
        (reports / "watchlist.json").write_text(json.dumps({
            "source": "ibkr",
            "items": [{"ticker": "MSFT"}],
        }), encoding="utf-8")
        (content / "industry_role_overrides.json").write_text(json.dumps({
            "tickers": {"DELL": {"primary_role": "ai_server_odm"}},
        }), encoding="utf-8")
        (content / "theme_baskets.json").write_text(json.dumps({
            "themes": {"AI Infra": {"tickers": ["NVDA"]}},
        }), encoding="utf-8")

        tickers = emf.collect_money_flow_tickers(
            reports_dir=reports,
            content_dir=content,
            extra_tickers=["TSLA"],
        )

    assert tickers == ["TSLA", "AAPL", "MSFT", "DELL", "NVDA"], tickers


def test_collect_candidate_file_tickers_respects_rank_order_and_limit():
    with TemporaryDirectory() as td:
        path = Path(td) / "ranked_candidates.json"
        path.write_text(json.dumps({
            "ranked_candidates": [
                {"ticker": "NVDA"},
                {"ticker": "$AMD"},
                {"ticker": "NVDA"},
                {"symbol": "MU"},
            ]
        }), encoding="utf-8")

        tickers = emf.collect_candidate_file_tickers(path, limit=2)

    assert tickers == ["NVDA", "AMD"], tickers


def test_main_only_candidate_file_excludes_manual_tickers():
    with TemporaryDirectory() as td:
        root = Path(td)
        candidate_file = root / "ranked_candidates.json"
        reports = root / "reports"
        candidate_file.write_text(json.dumps({
            "ranked_candidates": [
                {"ticker": "NVDA"},
                {"ticker": "$AMD"},
            ]
        }), encoding="utf-8")
        captured: dict[str, object] = {}
        original_refresh = emf.refresh_money_flow

        def fake_refresh(tickers, **kwargs):
            captured["tickers"] = list(tickers)
            captured["kwargs"] = kwargs
            return {
                "path": str(reports / "money_flow" / "2026-07-01.json"),
                "publishable": True,
                "coverage": {
                    "requested": len(tickers),
                    "resolved": len(tickers),
                    "unavailable": 0,
                    "coverage_ratio": 1.0,
                    "min_coverage": 0.7,
                },
            }

        emf.refresh_money_flow = fake_refresh
        try:
            result = emf.main([
                "--candidate-file", str(candidate_file),
                "--only-candidate-file",
                "--tickers", "SHOULDNOT",
                "--reports-dir", str(reports),
            ])
        finally:
            emf.refresh_money_flow = original_refresh

    assert result == 0, result
    assert captured["tickers"] == ["NVDA", "AMD"], captured


def main() -> int:
    tests = [
        test_collect_money_flow_tickers_from_platform_sources,
        test_collect_candidate_file_tickers_respects_rank_order_and_limit,
        test_main_only_candidate_file_excludes_manual_tickers,
        test_build_money_flow_snapshot_marks_publishable_by_coverage,
        test_build_money_flow_snapshot_is_publishable_when_coverage_passes,
        test_build_money_flow_snapshot_resolves_missing_secid_with_search,
        test_write_money_flow_snapshot_writes_dated_and_latest_json,
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
        print("eastmoney money flow tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
