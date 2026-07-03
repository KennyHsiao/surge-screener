#!/usr/bin/env python3
"""Tests for deterministic candidate ranking."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_ranker():
    spec = importlib.util.spec_from_file_location(
        "rank_candidates_under_test", ROOT / "scripts" / "03_rank_candidates.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _base_candidate(ticker: str, **overrides) -> dict:
    row = {
        "ticker": ticker,
        "last_price": 100.0,
        "ma50": 90.0,
        "ma200": 80.0,
        "ret_5d": 4.0,
        "ret_20d": 14.0,
        "avg_dollar_vol_20d": 150_000_000,
        "market_cap": 12_000_000_000,
        "macd_current": 1.2,
        "macd_zero_cross_10d": True,
        "macd_golden_cross_10d": True,
        "rsi_bullish_divergence": False,
        "has_reversal_pattern": False,
        "gap_down_8pct_5d": False,
    }
    row.update(overrides)
    return row


def test_rank_score_components_are_bounded_and_sorted() -> None:
    mod = _load_ranker()
    universe = {
        "scan_date": "2026-06-24",
        "universe": "sp1500",
        "markets": "US",
        "total_universe": 2,
        "passed_hard_filters": 2,
        "tickers": [
            _base_candidate("GOOD"),
            _base_candidate(
                "WEAK",
                last_price=95.0,
                ma50=100.0,
                ma200=110.0,
                ret_5d=-6.0,
                ret_20d=-12.0,
                avg_dollar_vol_20d=8_000_000,
                market_cap=700_000_000,
                macd_current=-0.2,
                macd_zero_cross_10d=False,
                macd_golden_cross_10d=False,
            ),
        ],
    }

    output = mod.build_ranked_output(universe, limit=2, options_gate_limit=0)
    rows = output["ranked_candidates"]

    if [r["ticker"] for r in rows] != ["GOOD", "WEAK"]:
        raise AssertionError(rows)
    for row in rows:
        score = row["rank_score"]
        if not 0 <= score <= 100:
            raise AssertionError(row)
        component_total = round(sum(row["score_components"].values()), 1)
        if component_total != score:
            raise AssertionError(row)
    if output["scoring_model"] != "deterministic_rank_v2_money_flow":
        raise AssertionError(output)


def test_missing_fields_mark_partial_data_without_crashing() -> None:
    mod = _load_ranker()
    row = _base_candidate("MISS")
    row.pop("ma200")
    row.pop("market_cap")

    ranked = mod.rank_candidate(row, as_of_date="2026-06-24")

    if ranked["ticker"] != "MISS":
        raise AssertionError(ranked)
    if ranked["data_quality"]["status"] != "partial":
        raise AssertionError(ranked["data_quality"])
    for field in ("ma200", "market_cap"):
        if field not in ranked["data_quality"]["missing_fields"]:
            raise AssertionError(ranked["data_quality"])
    if not ranked["warnings"]:
        raise AssertionError(ranked)


def test_tie_breaker_prefers_higher_dollar_volume_then_ticker() -> None:
    mod = _load_ranker()
    universe = {
        "scan_date": "2026-06-24",
        "tickers": [
            _base_candidate("BBB", avg_dollar_vol_20d=150_000_000),
            _base_candidate("AAA", avg_dollar_vol_20d=150_000_000),
            _base_candidate("CCC", avg_dollar_vol_20d=300_000_000),
        ],
    }

    output = mod.build_ranked_output(universe, limit=3, options_gate_limit=0)
    tickers = [r["ticker"] for r in output["ranked_candidates"]]

    if tickers != ["CCC", "AAA", "BBB"]:
        raise AssertionError(tickers)


def test_options_gate_adds_tradeability_fields_for_top_pool() -> None:
    mod = _load_ranker()
    universe = {
        "scan_date": "2026-06-24",
        "tickers": [
            _base_candidate("TRADE"),
            _base_candidate(
                "SKIP",
                last_price=92.0,
                ma50=100.0,
                ret_5d=-4.0,
                ret_20d=-8.0,
                macd_zero_cross_10d=False,
                macd_golden_cross_10d=False,
            ),
        ],
    }

    def fake_momentum(ticker: str) -> dict:
        if ticker != "TRADE":
            raise AssertionError(f"unexpected momentum call: {ticker}")
        return {
            "available": True,
            "verdict": "WAIT",
            "data_quality": {
                "contract_executable": True,
                "iv_percentile_real": True,
                "earnings_known": True,
            },
            "options": {
                "suggested_contract": {
                    "spread_pct": 8.0,
                    "open_interest": 250,
                    "volume": 80,
                    "liquid": True,
                    "executable": True,
                }
            },
            "iv": {"iv_percentile": 42.0, "iv_percentile_real": True},
            "earnings": {"status": "clear", "days_away": 35},
            "reasons": ["partial setup"],
        }

    def fake_flow(ticker: str) -> dict:
        if ticker != "TRADE":
            raise AssertionError(f"unexpected flow call: {ticker}")
        return {
            "available": True,
            "total_score": 7,
            "details": {
                "6a": {
                    "max_call_voi": 2.4,
                    "call_put_volume_ratio": 1.9,
                    "total_call_volume": 12_000,
                    "total_put_volume": 6_000,
                }
            },
            "data_missing": ["sweeps", "blocks", "dark_pool", "bid_ask_side"],
        }

    output = mod.build_ranked_output(
        universe,
        limit=2,
        options_gate_limit=1,
        momentum_analyzer=fake_momentum,
        flow_analyzer=fake_flow,
    )
    first, second = output["ranked_candidates"]

    if first["ticker"] != "TRADE":
        raise AssertionError(output)
    gate = first["options_tradability"]
    if gate["status"] != "usable":
        raise AssertionError(gate)
    if gate["spread_pct"] != 8.0 or gate["open_interest"] != 250:
        raise AssertionError(gate)
    if gate["max_call_voi"] != 2.4:
        raise AssertionError(gate)
    if "options_tradability" in second:
        raise AssertionError(second)
    if output["options_gate"]["checked"] != 1:
        raise AssertionError(output["options_gate"])


def test_options_gate_marks_proxy_iv_as_watch_not_usable() -> None:
    mod = _load_ranker()
    momentum = {
        "available": True,
        "verdict": "WAIT",
        "data_quality": {
            "contract_executable": True,
            "iv_percentile_real": False,
            "earnings_known": True,
        },
        "options": {
            "suggested_contract": {
                "spread_pct": 6.0,
                "open_interest": 500,
                "volume": 120,
                "liquid": True,
                "executable": True,
            }
        },
        "iv": {"iv_percentile": 28.0, "iv_percentile_real": False},
        "earnings": {"status": "clear", "days_away": 40},
    }
    flow = {"available": True, "details": {"6a": {}}, "data_missing": []}

    gate = mod.classify_options_tradability(momentum, flow)

    if gate["status"] != "watch":
        raise AssertionError(gate)
    if "IV percentile is proxy or unavailable" not in gate["warnings"]:
        raise AssertionError(gate)


def test_write_ranked_output_is_atomic_json() -> None:
    mod = _load_ranker()
    universe = {"scan_date": "2026-06-24", "tickers": [_base_candidate("SAVE")]}
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "ranked_candidates.json"
        output = mod.write_ranked_output(path, universe, limit=1, options_gate_limit=0)
        data = json.loads(path.read_text(encoding="utf-8"))

    if data != output:
        raise AssertionError(data)
    if data["ranked_candidates"][0]["ticker"] != "SAVE":
        raise AssertionError(data)


def test_write_ranking_snapshot_uses_scan_date() -> None:
    mod = _load_ranker()
    universe = {"scan_date": "2026-06-24", "tickers": [_base_candidate("HIST")]}
    output = mod.build_ranked_output(universe, limit=1, options_gate_limit=0)

    with tempfile.TemporaryDirectory() as d:
        snapshot_dir = Path(d) / "reports" / "candidate_rankings"
        path = mod.write_ranking_snapshot(output, snapshot_dir)
        data = json.loads(path.read_text(encoding="utf-8"))

    if path.name != "2026-06-24.json":
        raise AssertionError(path)
    if data != output:
        raise AssertionError(data)
    if data["ranked_candidates"][0]["ticker"] != "HIST":
        raise AssertionError(data)


def test_money_flow_component_rewards_publishable_large_order_inflow() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-01", "main_net": 500_000.0, "main_pct": 2.5, "small_net": -50_000.0, "source": "eastmoney_push2his"},
            {"ticker": "AAPL", "date": "2026-07-02", "main_net": 600_000.0, "main_pct": 3.0, "small_net": -60_000.0, "source": "eastmoney_push2his"},
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 700_000.0, "main_pct": 3.4, "small_net": -70_000.0, "source": "eastmoney_push2his"},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-03")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-03", money_flow_context=context)

    component = ranked["score_components"]["large_order_flow_confirmation"]
    if component <= 0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["source"] != "eastmoney_push2his":
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["main_net_5d"] != 1_800_000.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["label"] != "主力流入確認":
        raise AssertionError(ranked)


def test_money_flow_component_fails_closed_when_artifact_not_publishable() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": False,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 10_000_000.0, "main_pct": 9.9},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-03")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-03", money_flow_context=context)

    if ranked["score_components"]["large_order_flow_confirmation"] != 0.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["publishable"] is not False:
        raise AssertionError(ranked)
    if "資料缺口" not in ranked["money_flow_evidence"]["label"]:
        raise AssertionError(ranked)


def test_money_flow_component_scores_zero_when_artifact_is_stale() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-10",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 10_000_000.0, "main_pct": 9.9},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-10")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-10", money_flow_context=context)

    if ranked["score_components"]["large_order_flow_confirmation"] != 0.0:
        raise AssertionError(ranked)
    if "過期" not in ranked["money_flow_evidence"]["label"]:
        raise AssertionError(ranked)


def test_money_flow_component_ignores_future_only_rows() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-04", "main_net": 10_000_000.0, "main_pct": 9.9},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-03")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-03", money_flow_context=context)

    if ranked["score_components"]["large_order_flow_confirmation"] != 0.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["publishable"] is not False:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["date"] is not None:
        raise AssertionError(ranked)
    if "資料缺口" not in ranked["money_flow_evidence"]["label"]:
        raise AssertionError(ranked)


def test_money_flow_component_fails_closed_when_artifact_missing() -> None:
    mod = _load_ranker()
    universe = {"scan_date": "2026-07-03", "tickers": [_base_candidate("AAPL")]}

    output = mod.build_ranked_output(universe, limit=1, money_flow_artifact=None)
    ranked = output["ranked_candidates"][0]

    if ranked["score_components"]["large_order_flow_confirmation"] != 0.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["publishable"] is not False:
        raise AssertionError(ranked)
    if "資料缺口" not in ranked["money_flow_evidence"]["label"]:
        raise AssertionError(ranked)
    if output["money_flow_scoring"]["publishable"] is not False:
        raise AssertionError(output)


def test_disable_money_flow_preserves_legacy_scoring_semantics() -> None:
    mod = _load_ranker()
    universe = {"scan_date": "2026-07-03", "tickers": [_base_candidate("AAPL")]}
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 10_000_000.0, "main_pct": 9.9},
        ],
    }

    output = mod.build_ranked_output(
        universe,
        limit=1,
        money_flow_artifact=artifact,
        money_flow_enabled=False,
    )
    ranked = output["ranked_candidates"][0]

    if output["scoring_model"] != "deterministic_rank_v1":
        raise AssertionError(output)
    if output["score_weights"] != {
        "technical_trend": 25,
        "momentum_strength": 20,
        "launch_signal": 20,
        "liquidity_tradability": 20,
        "overheat_risk_control": 15,
    }:
        raise AssertionError(output)
    if "large_order_flow_confirmation" in ranked["score_components"]:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["source"] != "disabled":
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["label"] != "資金流評分停用":
        raise AssertionError(ranked)


def main() -> None:
    tests = [
        test_rank_score_components_are_bounded_and_sorted,
        test_missing_fields_mark_partial_data_without_crashing,
        test_tie_breaker_prefers_higher_dollar_volume_then_ticker,
        test_options_gate_adds_tradeability_fields_for_top_pool,
        test_options_gate_marks_proxy_iv_as_watch_not_usable,
        test_write_ranked_output_is_atomic_json,
        test_write_ranking_snapshot_uses_scan_date,
        test_money_flow_component_rewards_publishable_large_order_inflow,
        test_money_flow_component_fails_closed_when_artifact_not_publishable,
        test_money_flow_component_scores_zero_when_artifact_is_stale,
        test_money_flow_component_ignores_future_only_rows,
        test_money_flow_component_fails_closed_when_artifact_missing,
        test_disable_money_flow_preserves_legacy_scoring_semantics,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
