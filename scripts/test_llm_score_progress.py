#!/usr/bin/env python3
"""Regression tests for Layer-1 scoring progress persistence."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_llm_score():
    spec = importlib.util.spec_from_file_location(
        "llm_score_under_test", ROOT / "scripts" / "02_llm_score.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_partial_scoring_output_is_written_after_each_success() -> None:
    mod = _load_llm_score()
    universe = {
        "total_universe": 1503,
        "passed_hard_filters": 834,
        "tickers": [{"ticker": "AAL"}, {"ticker": "AAON"}, {"ticker": "AAPL"}],
    }
    regime = {"scan_date": "2026-06-24", "global_score_multiplier": 1.0}
    scored = [
        {"ticker": "AAL", "verdict": "WATCHLIST", "regime_adjusted_score": 61},
        {"ticker": "AAPL", "verdict": "NEEDS_LAYER_2", "regime_adjusted_score": 72},
    ]

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "scored_candidates.json"
        mod.write_scored_output(out, universe, regime, scored, min_score=65)
        data = json.loads(out.read_text(encoding="utf-8"))

    if data["scored_candidates_count"] != 2:
        raise AssertionError(data)
    if data["remaining_unscored"] != 1:
        raise AssertionError(data)
    if data["needs_layer2_count"] != 1 or data["watchlist_count"] != 1:
        raise AssertionError(data)
    if [r["ticker"] for r in data["all_scored"]] != ["AAPL", "AAL"]:
        raise AssertionError(data["all_scored"])


def test_scored_snapshot_is_written_for_analytics_history() -> None:
    mod = _load_llm_score()
    universe = {
        "scan_date": "2026-06-24",
        "total_universe": 1503,
        "passed_hard_filters": 834,
        "tickers": [{"ticker": "AAL"}, {"ticker": "AAPL"}],
    }
    regime = {"scan_date": "2026-06-24", "global_score_multiplier": 1.0}
    scored = [
        {"ticker": "AAPL", "verdict": "NEEDS_LAYER_2", "regime_adjusted_score": 72},
    ]

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "scored_candidates.json"
        history_dir = Path(d) / "reports" / "candidate_scores"
        output = mod.write_scored_output(out, universe, regime, scored, min_score=65)
        snapshot = mod.write_scored_snapshot(output, history_dir)
        data = json.loads(snapshot.read_text(encoding="utf-8"))

    if snapshot.name != "2026-06-24.json":
        raise AssertionError(snapshot)
    if data["scan_date"] != "2026-06-24":
        raise AssertionError(data)
    if data["all_scored"][0]["ticker"] != "AAPL":
        raise AssertionError(data)


def test_timeout_errors_are_deferred_for_resume_or_retry() -> None:
    mod = _load_llm_score()
    if not mod.should_defer_candidate_error(
        "claude_agent call timed out after 360.0s (model=claude-sonnet-4-6)"
    ):
        raise AssertionError("timeout should be deferred")
    if mod.should_defer_candidate_error("Malformed JSON in response"):
        raise AssertionError("bad response JSON should not be deferred")


def test_progress_message_counts_processed_not_scored() -> None:
    mod = _load_llm_score()
    if mod.progress_message(2, 3) != "Processed 2/3":
        raise AssertionError(mod.progress_message(2, 3))


def test_deferred_retries_can_be_disabled_for_local_resume() -> None:
    mod = _load_llm_score()
    if mod.normalized_deferred_retries(0) != 0:
        raise AssertionError("zero should disable same-run deferred retry")
    if mod.normalized_deferred_retries(-2) != 0:
        raise AssertionError("negative retry counts should clamp to zero")
    if mod.normalized_deferred_retries(2) != 2:
        raise AssertionError("positive retry counts should be preserved")


def test_fast_score_prompt_is_compact_and_hard_filter_only() -> None:
    mod = _load_llm_score()
    candidate = {
        "ticker": "AAPL",
        "last_price": 200.0,
        "ma50": 190.0,
        "ma200": 170.0,
        "ret_5d": 4.2,
        "ret_20d": 12.5,
        "avg_dollar_vol_20d": 1_000_000_000,
        "market_cap": 3_000_000_000_000,
        "macd_zero_cross_10d": True,
        "macd_golden_cross_10d": False,
        "rsi_bullish_divergence": True,
        "has_reversal_pattern": True,
    }
    regime = {
        "scan_date": "2026-06-24",
        "vix_level": 15.5,
        "vix_regime": "normal",
        "global_score_multiplier": 1.0,
        "spy_vs_50dma": "above",
        "spy_vs_200dma": "above",
        "active_themes": ["AI infrastructure"],
    }

    system, user = mod.build_fast_score_messages(candidate, regime)

    if len(system) > 1800:
        raise AssertionError(f"fast system prompt too long: {len(system)}")
    if len(user) > 2500:
        raise AssertionError(f"fast user prompt too long: {len(user)}")
    for needle in ("AAPL", "ret_20d", "macd_zero_cross_10d", "global_score_multiplier"):
        if needle not in user:
            raise AssertionError(f"missing fast prompt field: {needle}")
    for forbidden in ("Options Flow Data", "Social Sentiment", "Institutional & Insider"):
        if forbidden in user:
            raise AssertionError(f"fast prompt should not include enrichment block: {forbidden}")


def test_fast_score_prompt_requires_traditional_chinese_human_text() -> None:
    mod = _load_llm_score()
    system, user = mod.build_fast_score_messages(
        {"ticker": "AAPL", "ret_20d": 12.5},
        {"scan_date": "2026-06-24", "global_score_multiplier": 1.0},
    )
    for needle in (
        "Traditional Chinese",
        "嚴格使用繁體中文",
        "不要輸出英文句子",
        "key_signals",
        "key_risks",
        "suggested_entry_zone",
        "suggested_stop",
    ):
        if needle not in system + user:
            raise AssertionError(f"missing zh output instruction: {needle}")


def test_resume_can_rescore_existing_english_human_text() -> None:
    mod = _load_llm_score()
    prior = [
        {
            "ticker": "AGX",
            "verdict": "REJECT",
            "key_signals": ["MACD zero-cross + golden cross both fired within 10 days"],
            "key_risks": ["Price 67% above MA200 is historically elevated"],
        },
        {
            "ticker": "BALL",
            "verdict": "REJECT",
            "key_signals": ["突破後仍需等待回測確認"],
            "key_risks": ["短線漲幅偏大"],
        },
    ]

    kept, done, rescore_rows = mod.prepare_resume_scores(prior, rescore_stale_language=True)

    if [r["ticker"] for r in kept] != ["BALL"]:
        raise AssertionError(kept)
    if done != {"BALL"}:
        raise AssertionError(done)
    if [r["ticker"] for r in rescore_rows] != ["AGX"]:
        raise AssertionError(rescore_rows)


def test_resume_keeps_old_english_if_rescore_fails() -> None:
    mod = _load_llm_score()
    old = {"ticker": "AGX", "key_signals": ["MACD zero-cross"], "regime_adjusted_score": 48}
    merged = mod.merge_rescore_fallbacks([old], newly=[{"ticker": "BALL"}])
    if [r["ticker"] for r in merged] != ["AGX"]:
        raise AssertionError(merged)


def test_fast_score_skips_enrichment_fetches() -> None:
    mod = _load_llm_score()

    class FakeLLM:
        provider = "claude_agent"

        def __init__(self):
            self.calls = []

        def chat(self, system, user, max_tokens=8192, cache_system=False):
            self.calls.append({
                "system": system,
                "user": user,
                "max_tokens": max_tokens,
                "cache_system": cache_system,
            })
            return json.dumps({
                "ticker": "AAPL",
                "composite_score": 67,
                "scores": {
                    "technical": 24,
                    "catalyst": 6,
                    "sentiment": 0,
                    "institutional": 0,
                    "sector_market": 2,
                    "options_flow": 0,
                    "analyst": 0,
                },
                "technical_breakdown": {},
                "key_signals": ["above 50DMA"],
                "key_risks": ["fast mode omits enrichment"],
                "data_missing": [],
            })

    def fail_fetch(*args, **kwargs):
        raise AssertionError("fast mode must not call enrichment fetchers")

    for name in (
        "fetch_polygon_news",
        "fetch_options_flow_summary",
        "fetch_free_sentiment",
        "fetch_fundamentals",
        "fetch_institutional",
        "fetch_analyst_views",
        "fetch_sector_rotation",
    ):
        setattr(mod, name, fail_fetch)

    llm = FakeLLM()
    result = mod.score_candidate(
        llm,
        "full prompt should not be used",
        {"scan_date": "2026-06-24", "global_score_multiplier": 1.0},
        {"ticker": "AAPL", "ret_20d": 12.5},
        scoring_mode="fast",
    )

    if result["ticker"] != "AAPL" or result["verdict"] != "NEEDS_LAYER_2":
        raise AssertionError(result)
    if result.get("scoring_mode") != "fast":
        raise AssertionError(result)
    for missing in ("options_flow", "sentiment", "institutional", "analyst"):
        if missing not in result.get("data_missing", []):
            raise AssertionError(result.get("data_missing"))
    if llm.calls[0]["cache_system"] is not False:
        raise AssertionError(llm.calls[0])
    if llm.calls[0]["max_tokens"] > 2048:
        raise AssertionError(llm.calls[0])


def main() -> None:
    tests = [
        test_partial_scoring_output_is_written_after_each_success,
        test_scored_snapshot_is_written_for_analytics_history,
        test_timeout_errors_are_deferred_for_resume_or_retry,
        test_progress_message_counts_processed_not_scored,
        test_deferred_retries_can_be_disabled_for_local_resume,
        test_fast_score_prompt_is_compact_and_hard_filter_only,
        test_fast_score_prompt_requires_traditional_chinese_human_text,
        test_resume_can_rescore_existing_english_human_text,
        test_resume_keeps_old_english_if_rescore_fails,
        test_fast_score_skips_enrichment_fetches,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
