#!/usr/bin/env python3
"""Self-contained tests for the Trade State board logic.

Run:  .venv/bin/python scripts/test_trade_state.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import trade_state as ts  # noqa: E402


def test_ce_trend_exact_from_chandelier_inputs():
    bull = ts.compute_ce_trend(
        price=121.0,
        atr=5.0,
        highest_high=130.0,
        lowest_low=100.0,
    )
    assert bull["trend"] == "bullish", bull
    assert bull["source"] == "chandelier"
    assert bull["long_stop"] == 115.0
    assert bull["short_stop"] == 115.0

    bear = ts.compute_ce_trend(
        price=112.0,
        atr=5.0,
        highest_high=130.0,
        lowest_low=100.0,
    )
    assert bear["trend"] == "bearish", bear
    assert bear["stop"] == 115.0


def test_ce_trend_proxy_is_labeled_when_chandelier_inputs_missing():
    bull = ts.compute_ce_trend(
        price=110.0,
        ma50=100.0,
        ma200=90.0,
        price_above_vwap=True,
    )
    assert bull["trend"] == "bullish", bull
    assert bull["source"] == "trend_proxy"

    bear = ts.compute_ce_trend(
        price=88.0,
        ma50=100.0,
        ma200=92.0,
        price_above_vwap=False,
    )
    assert bear["trend"] == "bearish", bear
    assert bear["source"] == "trend_proxy"


def test_ce_trend_exact_does_not_call_below_long_stop_bullish():
    ce = ts.compute_ce_trend(
        price=115.0,
        atr=4.0,
        highest_high=130.0,
        lowest_low=100.0,
    )
    assert ce["long_stop"] == 118.0
    assert ce["short_stop"] == 112.0
    assert ce["trend"] == "neutral", ce
    assert ce["stop"] == 118.0


def test_cycle_mapping_from_ranked_candidate_fields():
    c1 = ts.classify_cycle({
        "last_price": 120.0,
        "ma50": 100.0,
        "ma200": 90.0,
        "macd_current": 1.2,
    })
    assert c1["cycle"] == "Cycle1", c1
    assert "趨勢延續" in c1["label"]

    c4 = ts.classify_cycle({
        "last_price": 80.0,
        "ma50": 100.0,
        "ma200": 92.0,
        "macd_current": -1.2,
    })
    assert c4["cycle"] == "Cycle4", c4
    assert "下跌" in c4["label"]

    c5 = ts.classify_cycle({
        "last_price": 96.0,
        "ma50": 100.0,
        "ma200": 90.0,
        "macd_current": -0.1,
        "macd_golden_cross_10d": True,
    })
    assert c5["cycle"] == "Cycle5", c5
    assert "反轉測試" in c5["label"]


def test_cycle1_wins_when_breakout_is_above_mas_and_macd_positive():
    cycle = ts.classify_cycle({
        "last_price": 120.0,
        "ma50": 100.0,
        "ma200": 90.0,
        "macd_current": 0.2,
        "macd_zero_cross_10d": True,
    })
    assert cycle["cycle"] == "Cycle1", cycle


def test_build_rows_uses_chandelier_inputs_when_available():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({
            "tickers": [{
                "ticker": "CEOK",
                "last_price": 125.0,
                "ma50": 100.0,
                "ma200": 90.0,
                "atr14": 4.0,
                "highest_high_22d": 130.0,
                "lowest_low_22d": 100.0,
                "macd_current": 1.2,
            }]
        }), encoding="utf-8")

        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )
    assert rows[0]["ce_source"] == "chandelier", rows
    assert rows[0]["ce_stop"] == 118.0, rows


def test_build_rows_includes_approved_industry_role():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({
            "tickers": [{
                "ticker": "DELL",
                "last_price": 100.0,
                "ma50": 90.0,
                "ma200": 80.0,
                "macd_current": 1.0,
            }]
        }), encoding="utf-8")
        (content / "industry_roles.json").write_text(json.dumps({
            "roles": {"ai_server_odm": {"name": "AI Server / ODM"}}
        }), encoding="utf-8")
        (content / "industry_role_overrides.json").write_text(json.dumps({
            "tickers": {
                "DELL": {
                    "primary_role": "ai_server_odm",
                    "secondary_roles": [],
                    "confidence": 0.95,
                }
            }
        }), encoding="utf-8")

        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )
    assert rows[0]["industry_role"] == "AI Server / ODM", rows
    assert rows[0]["industry_role_source"] == "approved", rows
    assert rows[0]["industry_role_status"] == "approved", rows


def test_build_rows_always_includes_role_tag_for_unclassified_ticker():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({
            "tickers": [{
                "ticker": "XYZ",
                "last_price": 100.0,
                "ma50": 90.0,
                "ma200": 80.0,
                "macd_current": 1.0,
            }]
        }), encoding="utf-8")

        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )

    assert rows[0]["industry_role"] == "未分類", rows
    assert rows[0]["industry_role_source"] == "unclassified", rows
    assert rows[0]["industry_role_status"] == "unclassified", rows


def test_signal_mapping_prioritizes_risk_and_not_chasing_transition():
    hold = ts.map_trade_signal({
        "cycle": "Cycle1",
        "ce_trend": "bullish",
        "risk_status": "NORMAL",
        "atr_pct": 4.2,
    })
    assert hold["signal"] == "holding", hold

    take_profit = ts.map_trade_signal({
        "cycle": "Cycle5",
        "ce_trend": "bearish",
        "risk_status": "WATCH",
        "atr_pct": 8.8,
    })
    assert take_profit["signal"] == "take_profit", take_profit

    stop_loss = ts.map_trade_signal({
        "cycle": "Cycle4",
        "ce_trend": "bearish",
        "risk_status": "EXIT",
        "atr_pct": 10.5,
    })
    assert stop_loss["signal"] == "stop_loss", stop_loss


def test_story_copy_uses_markdown_table_and_source_label():
    story = ts.story_copy([{
        "ticker": "MU",
        "theme": "MEMORY",
        "mentions": 2,
        "atr_pct": 8.15,
        "cycle": "Cycle1",
        "ce_trend": "bullish",
        "ce_source": "trend_proxy",
        "signal": "holding",
    }])
    assert "| Ticker | 主題 | 提及 | ATR% | Cycle | 趨勢來源 | 訊號 |" in story
    assert "| MU | MEMORY | 2 | 8.2 | Cycle1 | bullish / proxy | holding |" in story


def test_build_rows_without_social_mentions_still_uses_ranked_candidates():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({
            "tickers": [{
                "ticker": "MU",
                "last_price": 120.0,
                "ma50": 100.0,
                "ma200": 90.0,
                "macd_current": 1.2,
                "rank_score": 88.0,
            }]
        }), encoding="utf-8")
        (content / "theme_baskets.json").write_text(json.dumps({
            "baskets": [{
                "theme": "DRAM / NAND 記憶體",
                "tickers": ["MU", "WDC"],
            }]
        }), encoding="utf-8")

        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )
    assert len(rows) == 1, rows
    assert rows[0]["ticker"] == "MU", rows
    assert rows[0]["mentions"] == 0, rows
    assert rows[0]["theme"] == "DRAM / NAND 記憶體", rows
    assert rows[0]["cycle"] == "Cycle1", rows
    assert rows[0]["signal"] == "holding", rows


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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
