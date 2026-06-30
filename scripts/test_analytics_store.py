#!/usr/bin/env python3
"""Self-contained tests for the DuckDB/Parquet analytics store."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_store():
    spec = importlib.util.spec_from_file_location(
        "analytics_store_under_test",
        ROOT / "scripts" / "analytics_store.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _rows_by_ticker(rows: list[dict]) -> dict:
    return {r["ticker"]: r for r in rows}


def test_exports_performance_ledger_to_parquet_and_duckdb_table() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        ledger = tmp / "performance_ledger.csv"
        ledger.write_text(
            "scan_date,ticker,verdict,composite_score,fwd_30d_return\n"
            "2026-06-01,NVDA,BUY,92.5,18.2\n"
            "2026-06-01,AMD,WATCH,81.0,-2.0\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.export_performance_ledger(ledger, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, composite_score from performance_ledger order by ticker",
            analytics_root=analytics_root,
        )

        if meta["rows"] != 2:
            raise AssertionError(meta)
        if not (analytics_root / "parquet" / "performance_ledger.parquet").is_file():
            raise AssertionError("performance parquet was not written")
        by = _rows_by_ticker(rows)
        if float(by["NVDA"]["composite_score"]) != 92.5:
            raise AssertionError(rows)


def test_exports_iv_history_to_flat_parquet_and_duckdb_table() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        iv_dir = tmp / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"ticker": "NVDA", "series": {"2026-06-01": 0.55, "2026-06-02": 0.60}}),
            encoding="utf-8",
        )
        (iv_dir / "AMD.json").write_text(
            json.dumps({"ticker": "AMD", "series": {"2026-06-01": 0.48}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.export_iv_history(iv_dir, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, as_of_date, atm_iv from iv_history order by ticker, as_of_date",
            analytics_root=analytics_root,
        )

        if meta["rows"] != 3:
            raise AssertionError(meta)
        if not (analytics_root / "parquet" / "iv_history.parquet").is_file():
            raise AssertionError("iv_history parquet was not written")
        if rows[0]["ticker"] != "AMD" or float(rows[0]["atm_iv"]) != 0.48:
            raise AssertionError(rows)


def test_refresh_all_exports_known_sources_from_reports_root() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select (select count(*) from performance_ledger) as ledger_rows,"
            "       (select count(*) from iv_history) as iv_rows",
            analytics_root=analytics_root,
        )[0]

        if meta["performance_ledger"]["rows"] != 1 or meta["iv_history"]["rows"] != 1:
            raise AssertionError(meta)
        if counts["ledger_rows"] != 1 or counts["iv_rows"] != 1:
            raise AssertionError(counts)


def test_refresh_all_exports_candidate_rankings() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        rankings_dir = reports / "candidate_rankings"
        rankings_dir.mkdir()
        (rankings_dir / "2026-06-24.json").write_text(json.dumps({
            "scan_date": "2026-06-24",
            "as_of_date": "2026-06-24",
            "universe": "sp1500",
            "markets": "US",
            "scoring_model": "deterministic_rank_v1",
            "total_universe": 1500,
            "passed_hard_filters": 500,
            "total_candidates": 500,
            "all_ranked_count": 500,
            "rank_limit": 2,
            "ranked_candidates_count": 2,
            "rank_buckets": {"priority": 1, "watch": 1},
            "options_gate": {"checked": 1, "usable": 1},
            "ranked_candidates": [
                {
                    "ticker": "NVDA",
                    "rank_score": 91.4,
                    "rank_bucket": "priority",
                    "last_price": 150.0,
                    "ma50": 140.0,
                    "ma200": 120.0,
                    "ret_5d": 5.0,
                    "ret_20d": 18.0,
                    "avg_dollar_vol_20d": 500000000,
                    "market_cap": 3500000000000,
                    "macd_current": 2.5,
                    "macd_zero_cross_10d": True,
                    "macd_golden_cross_10d": True,
                    "rsi_bullish_divergence": False,
                    "has_reversal_pattern": True,
                    "score_components": {"technical_trend": 25, "momentum_strength": 18},
                    "data_quality": {"status": "complete", "missing_fields": []},
                    "options_tradability": {
                        "status": "usable",
                        "momentum_verdict": "GO",
                        "spread_pct": 5.0,
                        "open_interest": 500,
                        "volume": 120,
                        "iv_percentile": 42.0,
                        "iv_percentile_real": True,
                        "earnings_status": "clear",
                        "earnings_days_away": 30,
                        "flow_score": 7,
                        "data_missing": [],
                        "warnings": [],
                    },
                    "warnings": [],
                },
                {
                    "ticker": "AMD",
                    "rank_score": 72.2,
                    "rank_bucket": "watch",
                    "score_components": {},
                    "data_quality": {"status": "partial", "missing_fields": ["ma200"]},
                    "warnings": ["missing ma200"],
                },
            ],
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, scan_date, rank_position, rank_score, rank_bucket, "
            "options_status, technical_trend from candidate_rankings order by rank_position",
            analytics_root=analytics_root,
        )

        if meta["candidate_rankings"]["rows"] != 2:
            raise AssertionError(meta)
        if rows[0]["ticker"] != "NVDA" or rows[0]["rank_position"] != 1:
            raise AssertionError(rows)
        if rows[0]["options_status"] != "usable":
            raise AssertionError(rows)
        if float(rows[0]["technical_trend"]) != 25.0:
            raise AssertionError(rows)


def test_candidate_rankings_can_fallback_to_latest_ranked_file() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (tmp / "ranked_candidates.json").write_text(json.dumps({
            "scan_date": "2026-06-25",
            "as_of_date": "2026-06-25",
            "rank_limit": 1,
            "ranked_candidates_count": 1,
            "ranked_candidates": [{
                "ticker": "FALL",
                "rank_score": 80.0,
                "rank_bucket": "priority",
                "score_components": {"launch_signal": 20},
            }],
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select source_file, ticker, scan_date, launch_signal from candidate_rankings",
            analytics_root=analytics_root,
        )

        if meta["candidate_rankings"]["rows"] != 1:
            raise AssertionError(meta)
        if rows[0]["source_file"] != "ranked_candidates.json" or rows[0]["ticker"] != "FALL":
            raise AssertionError(rows)
        if float(rows[0]["launch_signal"]) != 20.0:
            raise AssertionError(rows)


def test_refresh_all_exports_signal_and_forecast_tables() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )

        options_dir = reports / "options_flow"
        options_dir.mkdir()
        option_payload = {
            "as_of": "2026-06-01",
            "generated_at": "2026-06-01T21:00:00Z",
            "provider": "fixture",
            "min_notional": 1000000,
            "universe_size": 2,
            "signal_count": 1,
            "signals": [{
                "ticker": "NVDA",
                "direction": "bullish",
                "flow_score": 88.5,
                "est_notional_usd": 1200000,
                "expiry": "2026-07-17",
                "max_voi": 12.3,
                "high_voi_strikes": 3,
                "call_put_ratio": 2.4,
                "put_call_ratio": 0.42,
                "total_call_vol": 2400,
                "total_put_vol": 1000,
                "otm_call_vol": 1400,
                "spot": 150.25,
                "tags": ["fixture"],
                "biggest": {"strike": 155, "notional": 900000},
            }],
        }
        (options_dir / "2026-06-01.json").write_text(json.dumps(option_payload), encoding="utf-8")
        (options_dir / "latest.json").write_text(json.dumps(option_payload), encoding="utf-8")

        reversal_dir = reports / "reversal_radar"
        reversal_dir.mkdir()
        (reversal_dir / "scan_2026-06-01.json").write_text(json.dumps({
            "as_of_date": "2026-06-01",
            "generated_at": "2026-06-01T22:00:00Z",
            "universe": "fixture",
            "universe_size": 2,
            "scanned": 2,
            "match_count": 1,
            "lane_id": "coiled-base",
            "exploratory": True,
            "runway_independent": False,
            "candidates": [{
                "ticker": "AMD",
                "signal_date": "2026-06-01",
                "status": "TURNING",
                "reversal_score": 64,
                "data_confidence": 95,
                "structure_score": 11,
                "momentum_score": 19,
                "options_score": 8,
                "sector_score": 4,
                "insider_score": 12,
                "analyst_score": 10,
                "primary_signals": ["fixture"],
                "data_gaps": [],
                "sector": {"etf": "XLK"},
            }],
        }), encoding="utf-8")

        oversold_dir = reports / "oversold_reversal"
        oversold_dir.mkdir()
        (oversold_dir / "scan_2026-06-01.json").write_text(json.dumps({
            "as_of_date": "2026-06-01",
            "generated_at": "2026-06-01T22:30:00Z",
            "universe": "fixture",
            "scanned": 2,
            "attempted": 2,
            "match_count": 1,
            "lane_id": "coiled-base",
            "exploratory": True,
            "runway_independent": False,
            "fetch_failed": [],
            "candidates": [{
                "ticker": "TSLA",
                "as_of": "2026-06-01",
                "signal_date": "2026-06-01",
                "avg_dollar_vol_m": 950.5,
                "last_price": 190.25,
                "rsi14": 44.2,
                "bb_width_pct": 1.2,
                "ma200": 180.1,
                "pct_vs_ma200": 5.6,
                "pct_from_52w_high": -24.5,
            }],
        }), encoding="utf-8")

        thesis_dir = reports / "market_thesis"
        thesis_dir.mkdir()
        (thesis_dir / "regime_only_forecast_2026-06-01.json").write_text(json.dumps({
            "as_of": "2026-06-01",
            "generated_at": "2026-06-02T00:00:00Z",
            "tier": 1,
            "method": "deterministic_baseline",
            "benchmark": "^GSPC",
            "direction": "看多",
            "bucket": "mid",
            "support_class": "regime_only",
            "manifest_status": "ready",
            "regime": "rally",
            "vix_bucket": "normal",
            "rationale": {"resolved": 100},
            "label": "fixture",
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select"
            " (select count(*) from options_flow_signals) as options_rows,"
            " (select count(*) from reversal_radar_signals) as reversal_rows,"
            " (select count(*) from oversold_reversal_signals) as oversold_rows,"
            " (select count(*) from market_thesis_forecasts) as thesis_rows",
            analytics_root=analytics_root,
        )[0]
        option_rows = store.query(
            "select ticker, source_file, tags_json from options_flow_signals",
            analytics_root=analytics_root,
        )

        expected_counts = {
            "options_rows": 1,
            "reversal_rows": 1,
            "oversold_rows": 1,
            "thesis_rows": 1,
        }
        if counts != expected_counts:
            raise AssertionError(counts)
        if meta["options_flow_signals"]["rows"] != 1:
            raise AssertionError(meta)
        if option_rows[0]["source_file"] != "2026-06-01.json":
            raise AssertionError(option_rows)
        if json.loads(option_rows[0]["tags_json"]) != ["fixture"]:
            raise AssertionError(option_rows)


def test_refresh_all_exports_candidate_scores_and_signal_outcomes() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )

        scores_dir = reports / "candidate_scores"
        scores_dir.mkdir()
        (scores_dir / "2026-06-02.json").write_text(json.dumps({
            "scan_date": "2026-06-02",
            "generated_at": "2026-06-02T22:30:00Z",
            "total_candidates": 2,
            "scored_candidates_count": 2,
            "remaining_unscored": 0,
            "needs_layer2_count": 1,
            "watchlist_count": 1,
            "min_score_threshold": 65,
            "all_scored": [{
                "ticker": "NVDA",
                "verdict": "NEEDS_LAYER_2",
                "composite_score": 88,
                "regime_adjusted_score": 88.0,
                "scoring_mode": "full",
                "due_diligence_required": True,
                "scores": {
                    "technical": 25,
                    "catalyst": 11,
                    "sentiment": 9,
                    "institutional": 7,
                    "sector_market": 2,
                    "options_flow": 18,
                    "analyst": 6,
                },
                "technical_breakdown": {"pattern_type": "breakout"},
                "data_missing": ["sentiment"],
            }, {
                "ticker": "AMD",
                "verdict": "WATCHLIST",
                "composite_score": 71,
                "regime_adjusted_score": 71.0,
                "scores": {"technical": 21, "options_flow": 12},
                "technical_breakdown": {"pattern_type": "pullback"},
                "data_missing": [],
            }],
        }), encoding="utf-8")
        (scores_dir / "latest.json").write_text(json.dumps({
            "scan_date": "2026-06-02",
            "all_scored": [{"ticker": "SHOULD_NOT_LOAD"}],
        }), encoding="utf-8")

        reversal_dir = reports / "reversal_radar"
        reversal_dir.mkdir()
        (reversal_dir / "validation_summary.json").write_text(json.dumps({
            "generated_at": "2026-06-03T01:00:00Z",
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
            "min_resolved_for_verdict": 100,
            "by_tier": {
                "+10%/20d": {
                    "resolved": 12,
                    "hits": 3,
                    "hit_rate": 0.25,
                    "wilson90": [0.12, 0.44],
                    "ev_horizon": 2.1,
                    "median_horizon": 1.0,
                    "win_rate_horizon": 0.5,
                    "ev_excess_vs_spy": 0.7,
                },
            },
        }), encoding="utf-8")

        oversold_dir = reports / "oversold_reversal"
        oversold_dir.mkdir()
        (oversold_dir / "validation_summary.json").write_text(json.dumps({
            "generated_at": "2026-06-03T01:30:00Z",
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
            "min_resolved_for_verdict": 100,
            "by_tier": {
                "+30%/20d": {
                    "resolved": 10,
                    "hits": 2,
                    "hit_rate": 0.2,
                    "wilson90": [0.08, 0.41],
                    "mature": False,
                    "ev_horizon": 1.4,
                    "median_horizon": -0.5,
                    "win_rate_horizon": 0.4,
                    "ev_excess_vs_spy": 0.2,
                },
            },
        }), encoding="utf-8")

        options_dir = reports / "options_flow"
        options_dir.mkdir()
        (options_dir / "validation_summary.json").write_text(json.dumps({
            "generated_at": "2026-06-03T02:00:00Z",
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
            "min_resolved_for_verdict": 100,
            "by_tier": {
                "+5%/10d": {
                    "resolved": 8,
                    "hits": 5,
                    "hit_rate": 0.625,
                    "wilson90": [0.34, 0.84],
                    "mature": False,
                    "ev_horizon": 0.03,
                    "median_horizon": 0.02,
                    "win_rate_horizon": 0.625,
                },
            },
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select"
            " (select count(*) from candidate_scores) as candidate_rows,"
            " (select count(*) from signal_outcomes) as outcome_rows",
            analytics_root=analytics_root,
        )[0]
        candidates = store.query(
            "select ticker, source_file, technical, options_flow, pattern_type, data_missing_json "
            "from candidate_scores order by ticker",
            analytics_root=analytics_root,
        )
        outcomes = store.query(
            "select signal_source, tier, resolved, hits, hit_rate, mature "
            "from signal_outcomes order by signal_source",
            analytics_root=analytics_root,
        )

        if meta["candidate_scores"]["rows"] != 2 or meta["signal_outcomes"]["rows"] != 3:
            raise AssertionError(meta)
        if counts != {"candidate_rows": 2, "outcome_rows": 3}:
            raise AssertionError(counts)
        if candidates[0]["ticker"] != "AMD" or candidates[1]["ticker"] != "NVDA":
            raise AssertionError(candidates)
        if candidates[1]["source_file"] != "2026-06-02.json":
            raise AssertionError(candidates)
        if json.loads(candidates[1]["data_missing_json"]) != ["sentiment"]:
            raise AssertionError(candidates)
        if outcomes[0]["signal_source"] != "options_flow":
            raise AssertionError(outcomes)
        if outcomes[1]["signal_source"] != "oversold_reversal":
            raise AssertionError(outcomes)
        if outcomes[2]["signal_source"] != "reversal_radar":
            raise AssertionError(outcomes)
        if outcomes[2]["tier"] != "+10%/20d" or int(outcomes[2]["resolved"]) != 12:
            raise AssertionError(outcomes)


def test_refresh_all_exports_risk_guard_rows_with_latest_fallback() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        risk_dir = reports / "risk_guard"
        risk_dir.mkdir()
        dated_payload = {
            "as_of": "2026-06-04",
            "generated_at": "2026-06-04T22:00:00Z",
            "market": {
                "status": "WATCH",
                "score": 34,
                "reasons": ["VIX rising"],
                "data_gaps": [],
            },
            "summary": {"count": 2, "high_risk": 1, "data_gaps": 0, "systemic_gaps": 0},
            "rows": [{
                "ticker": "NVDA",
                "status": "REDUCE",
                "risk_score": 55,
                "market_score": 8,
                "price_score": 18,
                "options_score": 12,
                "sector_score": 10,
                "position_score": 4,
                "cot_score": 1,
                "data_quality_score": 2,
                "primary_reasons": ["跌破 MA20", "IV elevated"],
                "data_gaps": [],
                "technical": {
                    "price": 150.0,
                    "ma20": 154.0,
                    "ma50": 145.0,
                    "ma200": 121.0,
                    "vwap": 153.5,
                    "atr14": 5.1,
                    "rsi14": 42.0,
                    "price_above_vwap": False,
                    "resistance_20d": 165.0,
                },
                "options": {"put_call_ratio": 1.4, "iv_percentile": 82.0},
                "sector": {
                    "etf": "XLK",
                    "name_zh": "科技",
                    "quadrant": "Weakening",
                    "quadrant_zh": "轉弱",
                    "heat_score": 74.7,
                    "excess_20d": -2.5,
                    "rs_ratio": 101.0,
                    "rs_momentum": 97.5,
                },
                "position": {
                    "total_unrealized_pnl": -420.0,
                    "worst_leg_return_pct": -12.5,
                    "min_option_dte": 9,
                    "leg_count": 2,
                    "held_not_in_ledger": False,
                },
            }, {
                "ticker": "AMD",
                "status": "WATCH",
                "risk_score": 31,
                "primary_reasons": [],
                "data_gaps": ["選擇權資料"],
            }],
        }
        (risk_dir / "2026-06-04.json").write_text(json.dumps(dated_payload), encoding="utf-8")
        latest_payload = {
            **dated_payload,
            "as_of": "2026-06-05",
            "generated_at": "2026-06-05T22:00:00Z",
            "summary": {"count": 1, "high_risk": 1, "data_gaps": 0, "systemic_gaps": 0},
            "rows": [{
                **dated_payload["rows"][0],
                "ticker": "NVDA",
                "status": "EXIT",
                "risk_score": 78,
            }],
        }
        (risk_dir / "latest.json").write_text(json.dumps(latest_payload), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        counts = store.query(
            "select count(*) as rows from risk_guard_rows",
            analytics_root=analytics_root,
        )[0]
        rows = store.query(
            "select source_file, ticker, as_of_date, status, risk_score, "
            "market_status, market_score_total, sector_quadrant, "
            "position_worst_leg_return_pct, primary_reasons_json "
            "from risk_guard_rows order by as_of_date, ticker",
            analytics_root=analytics_root,
        )

        if meta["risk_guard_rows"]["rows"] != 3 or counts["rows"] != 3:
            raise AssertionError((meta, counts))
        if rows[0]["ticker"] != "AMD" or rows[0]["status"] != "WATCH":
            raise AssertionError(rows)
        if rows[1]["ticker"] != "NVDA" or rows[1]["market_status"] != "WATCH":
            raise AssertionError(rows)
        if rows[1]["sector_quadrant"] != "Weakening":
            raise AssertionError(rows)
        if float(rows[1]["position_worst_leg_return_pct"]) != -12.5:
            raise AssertionError(rows)
        if json.loads(rows[1]["primary_reasons_json"]) != ["跌破 MA20", "IV elevated"]:
            raise AssertionError(rows)
        if rows[2]["source_file"] != "latest.json" or rows[2]["status"] != "EXIT":
            raise AssertionError(rows)


def test_refresh_all_exports_portfolio_positions_without_leg_details() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        (reports / "reconciliation.json").write_text(json.dumps({
            "as_of_date": "2026-06-05",
            "generated_at": "2026-06-05T21:30:00Z",
            "reachable": True,
            "matched": [{
                "ticker": "NVDA",
                "verdict": "BUY",
                "scan_date": "2026-06-01",
                "suggested_entry_low": 140.0,
                "suggested_entry_high": 145.0,
                "fwd_30d_return": 18.2,
                "total_unrealized_pnl": -420.0,
                "legs": [{
                    "label": "NVDA 20260717 C 150",
                    "secType": "OPT",
                    "qty": 1,
                    "avg_cost": 10.0,
                    "market_price": 6.0,
                    "return_pct": -40.0,
                    "unrealized_pnl": -400.0,
                    "expiry": "20260717",
                    "right": "C",
                    "strike": 150.0,
                }, {
                    "label": "NVDA stock",
                    "secType": "STK",
                    "qty": 10,
                    "return_pct": -2.0,
                    "unrealized_pnl": -20.0,
                }],
            }],
            "ledger_not_held": [{
                "ticker": "AMD",
                "verdict": "WATCH",
                "scan_date": "2026-06-02",
                "suggested_entry_low": 110.0,
                "suggested_entry_high": 115.0,
            }],
            "held_not_in_ledger": [{
                "ticker": "SOXX",
                "total_unrealized_pnl": 125.0,
                "legs": [{
                    "label": "SOXX stock",
                    "secType": "STK",
                    "qty": 3,
                    "return_pct": 4.2,
                    "unrealized_pnl": 125.0,
                }],
            }],
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select ticker, position_status, held, ranked, leg_count, option_leg_count, "
            "stock_leg_count, total_unrealized_pnl, worst_leg_return_pct, "
            "min_option_dte, verdict, raw_position_json "
            "from portfolio_positions order by ticker",
            analytics_root=analytics_root,
        )
        cols = store.table_columns("portfolio_positions", analytics_root=analytics_root)

        if meta["portfolio_positions"]["rows"] != 3:
            raise AssertionError(meta)
        if "leg_labels_json" in cols or "account" in cols:
            raise AssertionError(cols)
        by = _rows_by_ticker(rows)
        if by["AMD"]["position_status"] != "ledger_not_held" or by["AMD"]["held"]:
            raise AssertionError(rows)
        if by["NVDA"]["position_status"] != "matched" or not by["NVDA"]["ranked"]:
            raise AssertionError(rows)
        if by["NVDA"]["leg_count"] != 2 or by["NVDA"]["option_leg_count"] != 1:
            raise AssertionError(rows)
        if by["NVDA"]["stock_leg_count"] != 1 or float(by["NVDA"]["worst_leg_return_pct"]) != -40.0:
            raise AssertionError(rows)
        if by["NVDA"]["min_option_dte"] != 42:
            raise AssertionError(rows)
        if "NVDA 20260717 C 150" in str(by["NVDA"]["raw_position_json"]):
            raise AssertionError(rows)
        if by["SOXX"]["position_status"] != "held_not_in_ledger" or by["SOXX"]["ranked"]:
            raise AssertionError(rows)


def test_empty_portfolio_positions_keeps_string_schema() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select count(*) as raw_detail_rows "
            "from portfolio_positions "
            "where raw_position_json like '%legs%' or raw_position_json like '%label%'",
            analytics_root=analytics_root,
        )

        if meta["portfolio_positions"]["rows"] != 0:
            raise AssertionError(meta)
        if rows[0]["raw_detail_rows"] != 0:
            raise AssertionError(rows)


def test_refresh_all_exports_theme_flow_snapshots_with_latest_fallback() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        snapshots = reports / "theme_flow_snapshots"
        snapshots.mkdir()
        (snapshots / "2026-06-04.json").write_text(json.dumps({
            "as_of": "2026-06-04",
            "generated_at": "2026-06-04T21:00:00Z",
            "benchmark": "SPY",
            "n_failed_download": 1,
            "themes": [{
                "theme": "AI Infra",
                "desc": "AI infrastructure",
                "capital_state": "加速流入(推估)",
                "heat_score": 82.5,
                "flow_5d": 1250000.0,
                "flow_20d": 4200000.0,
                "accel": 0.42,
                "ret_5d": 3.2,
                "rvol": 1.6,
                "top_share": 0.34,
                "high_concentration": False,
                "n_total": 4,
                "n_used": 4,
                "n_failed": 0,
                "parent_sector_etfs": ["XLK"],
                "reps": [{"ticker": "NVDA", "flow_5d": 120.0}],
                "bottom_fishing": {"score": 0},
            }],
        }), encoding="utf-8")
        (reports / "theme_flow_snapshot.json").write_text(json.dumps({
            "as_of": "2026-06-05",
            "generated_at": "2026-06-05T21:00:00Z",
            "benchmark": "SPY",
            "themes": [{
                "theme": "Robotics",
                "capital_state": "中性",
                "heat_score": 55.0,
                "flow_5d": 500000.0,
                "parent_sector_etfs": ["XLI"],
                "reps": [{"ticker": "ROBO"}],
            }],
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select source_file, as_of_date, theme, capital_state, heat_score, "
            "parent_sector_etfs_json, reps_json "
            "from theme_flow_snapshots order by as_of_date, theme",
            analytics_root=analytics_root,
        )

        if meta["theme_flow_snapshots"]["rows"] != 2:
            raise AssertionError(meta)
        if rows[0]["source_file"] != "2026-06-04.json" or rows[0]["theme"] != "AI Infra":
            raise AssertionError(rows)
        if json.loads(rows[0]["parent_sector_etfs_json"]) != ["XLK"]:
            raise AssertionError(rows)
        if json.loads(rows[0]["reps_json"])[0]["ticker"] != "NVDA":
            raise AssertionError(rows)
        if rows[1]["source_file"] != "theme_flow_snapshot.json" or rows[1]["theme"] != "Robotics":
            raise AssertionError(rows)


def test_refresh_all_exports_sector_rotation_snapshots_with_latest_fallback() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        snapshots = reports / "sector_rotation_snapshots"
        snapshots.mkdir()
        (snapshots / "2026-06-04.json").write_text(json.dumps({
            "status": "ready",
            "as_of": "2026-06-04",
            "generated_at": "2026-06-04T21:00:00Z",
            "benchmark": "SPY",
            "leaders": ["XLK"],
            "improving": ["XLI"],
            "macro": {
                "spy_price": 610.25,
                "spy_vs_50dma": "above",
                "spy_vs_200dma": "above",
                "vix_level": 13.5,
            },
            "read": {
                "headline": "科技領漲，工業轉強",
                "confidence": "medium",
                "hot_now": [{"etf": "XLK", "why": "heat"}],
                "rotating_into": [{"etf": "XLI", "why": "momentum"}],
                "next_rotation_thesis": "工業可能接棒。",
                "cycle_read": "risk-on",
                "caveats": ["樣本短"],
            },
            "sectors": [
                {
                    "etf": "XLK",
                    "name_zh": "科技",
                    "group": "主板塊",
                    "theme": None,
                    "quadrant": "Leading",
                    "quadrant_zh": "領漲",
                    "rs_ratio": 104.2,
                    "rs_momentum": 101.8,
                    "heat_score": 92.5,
                    "ret_5d": 2.1,
                    "ret_20d": 8.3,
                    "ret_60d": 14.2,
                    "excess_20d": 3.4,
                    "pct_vs_ma50": 5.1,
                    "pct_vs_ma200": 18.0,
                    "rvol": 1.4,
                    "pct_from_52w_high": -2.0,
                    "tail": [{"date": "2026-06-04", "rs_ratio": 104.2, "rs_momentum": 101.8}],
                },
                {
                    "etf": "XLI",
                    "name_zh": "工業",
                    "group": "主板塊",
                    "theme": None,
                    "quadrant": "Improving",
                    "quadrant_zh": "醞釀",
                    "rs_ratio": 98.5,
                    "rs_momentum": 102.4,
                    "heat_score": 68.0,
                    "excess_20d": 1.2,
                },
            ],
        }), encoding="utf-8")
        (reports / "sector_rotation.json").write_text(json.dumps({
            "status": "ready",
            "as_of": "2026-06-05",
            "generated_at": "2026-06-05T21:00:00Z",
            "leaders": ["SMH"],
            "improving": ["ITB"],
            "macro": {"spy_price": 611.0},
            "read": {"headline": "半導體強，建商轉強", "confidence": "low"},
        }), encoding="utf-8")
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select source_file, as_of_date, etf, quadrant, is_leader, is_improving, "
            "leader_rank, improving_rank, heat_score, spy_price, read_headline, tail_json "
            "from sector_rotation_snapshots order by as_of_date, etf",
            analytics_root=analytics_root,
        )

        if meta["sector_rotation_snapshots"]["rows"] != 4:
            raise AssertionError(meta)
        by_key = {(row["as_of_date"], row["etf"]): row for row in rows}
        xlk = by_key[("2026-06-04", "XLK")]
        if xlk["source_file"] != "2026-06-04.json" or xlk["quadrant"] != "Leading":
            raise AssertionError(rows)
        if not xlk["is_leader"] or xlk["leader_rank"] != 1:
            raise AssertionError(rows)
        if abs(float(xlk["heat_score"]) - 92.5) > 0.001:
            raise AssertionError(rows)
        if json.loads(xlk["tail_json"])[0]["date"] != "2026-06-04":
            raise AssertionError(rows)
        itb = by_key[("2026-06-05", "ITB")]
        if itb["source_file"] != "sector_rotation.json" or not itb["is_improving"]:
            raise AssertionError(rows)
        if itb["improving_rank"] != 1 or itb["read_headline"] != "半導體強，建商轉強":
            raise AssertionError(rows)


def test_refresh_all_exports_run_status_history() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n",
            encoding="utf-8",
        )
        run_dir = reports / "run_status"
        run_dir.mkdir()
        history = run_dir / "candidates-local-history.jsonl"
        history.write_text(
            "\n".join([
                json.dumps({
                    "run_id": "run-1",
                    "job": "candidates-local",
                    "status": "succeeded",
                    "started_at": "2026-06-25T07:03:10Z",
                    "finished_at": "2026-06-25T07:21:43Z",
                    "stage": {"id": "done", "label": "完成", "message": "Ranked top 50"},
                    "metrics": {
                        "rank_source_candidates": 884,
                        "ranked_candidates": 50,
                        "options_gate_checked": 10,
                        "options_watch": 10,
                        "scored_candidates": 24,
                    },
                    "outputs": {"ranked_candidates": {"path": "ranked_candidates.json", "exists": True}},
                    "warnings": [],
                    "errors": [],
                }),
                "not json",
                json.dumps({
                    "run_id": "run-2",
                    "job": "candidates-local",
                    "status": "failed",
                    "started_at": "2026-06-26T08:00:00Z",
                    "finished_at": "2026-06-26T08:05:00Z",
                    "stage": {"id": "hard_filter.fetch_ohlcv", "label": "抓取 yfinance OHLCV"},
                    "metrics": {"ranked_candidates": 0},
                    "warnings": ["rate limited"],
                    "errors": [{"stage": "hard_filter.fetch_ohlcv", "message": "YFRateLimitError"}],
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        meta = store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        rows = store.query(
            "select run_id, status, stage_id, ranked_candidates, options_watch, "
            "duration_seconds, warnings_count, errors_count "
            "from run_status_history order by started_at",
            analytics_root=analytics_root,
        )

        if meta["run_status_history"]["rows"] != 2:
            raise AssertionError(meta)
        if rows[0]["run_id"] != "run-1" or rows[0]["ranked_candidates"] != 50:
            raise AssertionError(rows)
        if int(rows[0]["duration_seconds"]) != 1113:
            raise AssertionError(rows)
        if rows[1]["status"] != "failed" or rows[1]["errors_count"] != 1:
            raise AssertionError(rows)


def test_tables_work_from_other_working_directories() -> None:
    store = _load_store()
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        other_cwd = tmp / "other"
        other_cwd.mkdir()
        try:
            os.chdir(tmp)
            store.refresh_all(reports_root=Path("reports"), analytics_root=Path("analytics"))
            db_path = tmp / "analytics" / "analytics.duckdb"

            os.chdir(other_cwd)
            con = store.duckdb.connect(str(db_path), read_only=True)
            try:
                counts = con.execute(
                    "select (select count(*) from performance_ledger) as ledger_rows,"
                    "       (select count(*) from iv_history) as iv_rows"
                ).fetchone()
            finally:
                con.close()
        finally:
            os.chdir(old_cwd)

        if counts != (1, 1):
            raise AssertionError(counts)


def test_duckdb_tables_are_readable_without_parquet_files() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        (analytics_root / "parquet").rename(analytics_root / "parquet.off")

        con = store.duckdb.connect(str(analytics_root / "analytics.duckdb"), read_only=True)
        try:
            counts = con.execute(
                "select (select count(*) from performance_ledger) as ledger_rows,"
                "       (select count(*) from iv_history) as iv_rows"
            ).fetchone()
        finally:
            con.close()

        if counts != (1, 1):
            raise AssertionError(counts)


def test_readonly_catalog_reports_tables_and_counts() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        iv_dir = reports / "iv_history"
        iv_dir.mkdir()
        (iv_dir / "NVDA.json").write_text(
            json.dumps({"series": {"2026-06-01": 0.5}}),
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.refresh_all(reports_root=reports, analytics_root=analytics_root)
        catalog = {r["table_name"]: r for r in store.readonly_catalog(analytics_root)}

        if catalog["performance_ledger"]["row_count"] != 1:
            raise AssertionError(catalog)
        if catalog["iv_history"]["table_type"] != "BASE TABLE":
            raise AssertionError(catalog)


def test_readonly_fetch_table_filters_ticker_and_clamps_limit() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n"
            "2026-06-01,NVDA,BUY,90\n"
            "2026-06-02,AMD,WATCH,75\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"

        store.export_performance_ledger(
            reports / "performance_ledger.csv",
            analytics_root=analytics_root,
        )
        df = store.fetch_table(
            "performance_ledger",
            analytics_root=analytics_root,
            tickers=["nvda"],
            limit=50000,
        )

        if list(df["ticker"]) != ["NVDA"]:
            raise AssertionError(df)


def test_run_safe_select_rejects_non_select_sql() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        analytics_root = Path(d) / "analytics"
        store.refresh_all(reports_root=Path(d) / "missing", analytics_root=analytics_root)

        try:
            store.run_safe_select("drop table iv_history", analytics_root=analytics_root)
        except ValueError as e:
            if "Only SELECT" not in str(e):
                raise AssertionError(e)
        else:
            raise AssertionError("non-select SQL was accepted")


def test_query_does_not_refresh_tables_from_parquet() -> None:
    store = _load_store()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        ledger = tmp / "performance_ledger.csv"
        ledger.write_text(
            "scan_date,ticker,verdict,composite_score\n"
            "2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"
        store.export_performance_ledger(ledger, analytics_root=analytics_root)

        replacement = store.pd.DataFrame([{
            "scan_date": "2026-06-01",
            "ticker": "NVDA",
            "verdict": "BUY",
            "composite_score": 90,
        }, {
            "scan_date": "2026-06-02",
            "ticker": "AMD",
            "verdict": "WATCH",
            "composite_score": 75,
        }])
        store._write_parquet(  # noqa: SLF001 - intentional white-box regression guard.
            replacement,
            analytics_root / "parquet" / "performance_ledger.parquet",
        )

        rows = store.query(
            "select count(*) as rows from performance_ledger",
            analytics_root=analytics_root,
        )

        if rows[0]["rows"] != 1:
            raise AssertionError(rows)


def test_refresh_all_failure_does_not_partially_replace_tables() -> None:
    store = _load_store()
    original_export_iv_history = store.export_iv_history
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        reports.mkdir()
        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n"
            "2026-06-01,NVDA,BUY,90\n",
            encoding="utf-8",
        )
        analytics_root = tmp / "analytics"
        store.refresh_all(reports_root=reports, analytics_root=analytics_root)

        (reports / "performance_ledger.csv").write_text(
            "scan_date,ticker,verdict,composite_score\n"
            "2026-06-01,NVDA,BUY,90\n"
            "2026-06-02,AMD,WATCH,75\n",
            encoding="utf-8",
        )

        def fail_export(*args, **kwargs):
            raise RuntimeError("simulated iv export failure")

        store.export_iv_history = fail_export
        try:
            try:
                store.refresh_all(reports_root=reports, analytics_root=analytics_root)
            except RuntimeError as e:
                if "simulated iv export failure" not in str(e):
                    raise AssertionError(e)
            else:
                raise AssertionError("refresh_all did not surface exporter failure")
        finally:
            store.export_iv_history = original_export_iv_history

        con = store.duckdb.connect(str(analytics_root / "analytics.duckdb"), read_only=True)
        try:
            count = con.execute("select count(*) from performance_ledger").fetchone()[0]
        finally:
            con.close()

        if count != 1:
            raise AssertionError(count)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
