#!/usr/bin/env python3
"""Self-contained tests for trade-state snapshot artifacts.

Run:  .venv/bin/python scripts/test_trade_state_snapshots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import trade_state as ts  # noqa: E402


def _write_fixture(root: Path) -> tuple[Path, Path, Path]:
    reports = root / "reports"
    content = root / "content"
    reports.mkdir()
    content.mkdir()
    candidate_path = root / "ranked_candidates.json"
    candidate_path.write_text(json.dumps({
        "ranked_candidates": [{
            "ticker": "AAPL",
            "last_price": 120.0,
            "ma50": 100.0,
            "ma200": 90.0,
            "atr14": 4.0,
            "highest_high_22d": 130.0,
            "lowest_low_22d": 100.0,
            "macd_current": 1.2,
            "rank_score": 88.0,
        }]
    }), encoding="utf-8")
    (reports / "options_flow").mkdir()
    (reports / "options_flow" / "latest.json").write_text(json.dumps({
        "signals": [{"ticker": "AAPL", "direction": "bullish", "flow_score": 72.5}]
    }), encoding="utf-8")
    (reports / "money_flow").mkdir()
    (reports / "money_flow" / "latest.json").write_text(json.dumps({
        "publishable": True,
        "source": "eastmoney_push2his",
        "rows": [{
            "ticker": "AAPL",
            "date": "2026-06-30",
            "main_net": 1_000_000.0,
            "main_pct": 3.2,
            "source": "eastmoney_push2his",
        }],
    }), encoding="utf-8")
    (content / "industry_roles.json").write_text(json.dumps({
        "roles": {"mega_cap_platform": {"name": "Mega-cap Platform"}}
    }), encoding="utf-8")
    (content / "industry_role_overrides.json").write_text(json.dumps({
        "tickers": {"AAPL": {"primary_role": "mega_cap_platform", "confidence": 0.9}}
    }), encoding="utf-8")
    return reports, content, candidate_path


def test_build_trade_state_snapshot_normalizes_rows_for_history():
    with TemporaryDirectory() as td:
        reports, content, candidate_path = _write_fixture(Path(td))
        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )
        snapshot = ts.build_trade_state_snapshot(
            rows,
            as_of_date="2026-07-01",
            generated_at="2026-07-01T00:00:00Z",
        )

    row = snapshot["rows"][0]
    assert snapshot["as_of_date"] == "2026-07-01", snapshot
    assert snapshot["row_count"] == 1, snapshot
    assert row["ticker"] == "AAPL", row
    assert row["price"] == 120.0, row
    assert row["cycle"] == "Cycle1", row
    assert row["cycle_source"] == "notion_rule"
    assert row["ce_trend"] == "bullish", row
    assert row["ce_source"] == "chandelier", row
    assert row["verdict"] == "holding", row
    assert row["risk_level"] == "NORMAL", row
    assert row["industry_role"] == "Mega-cap Platform", row
    assert row["industry_role_status"] == "approved", row
    assert row["main_net_latest"] == 1_000_000.0, row
    assert row["main_pct_latest"] == 3.2, row
    assert row["atr_pct"] == 3.33, row
    assert row["options_flow_score"] == 72.5, row
    assert row["social_mentions"] == 0, row
    assert "Cycle1" in json.loads(row["reasons_json"])[0], row
    assert json.loads(row["data_sources_json"])["money_flow"] == "eastmoney_push2his", row
    assert json.loads(row["raw_row_json"])["ticker"] == "AAPL", row


def test_write_trade_state_snapshot_writes_dated_and_latest_json():
    snapshot = {
        "as_of_date": "2026-07-01",
        "generated_at": "2026-07-01T00:00:00Z",
        "source": "trade_state",
        "row_count": 1,
        "rows": [{"ticker": "AAPL"}],
    }
    with TemporaryDirectory() as td:
        out = ts.write_trade_state_snapshot(snapshot, reports_dir=Path(td) / "reports")
        latest = out.parent / "latest.json"
        latest_exists = latest.is_file()
        saved = json.loads(out.read_text(encoding="utf-8"))
        latest_saved = json.loads(latest.read_text(encoding="utf-8"))

    assert out.name == "2026-07-01.json", out
    assert latest_exists, latest
    assert saved["rows"][0]["ticker"] == "AAPL", saved
    assert latest_saved["as_of_date"] == "2026-07-01", latest_saved


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
        print("trade state snapshot tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
