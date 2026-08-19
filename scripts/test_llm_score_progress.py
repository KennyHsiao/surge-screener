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
        "Codex SDK call timed out after 360s"
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
        provider = "codex"

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


def _complete_technical_evidence(mod):
    inputs = {
        key: {"status": "available", "value": False if key in {
            "daily_macd_golden_cross_10d", "w_bottom_shape",
        } else 1.0}
        for key in mod.TECHNICAL_EVIDENCE_REQUIRED_INPUTS
    }
    for key in (
        *mod.TECHNICAL_EVIDENCE_UNSUPPORTED_PATTERNS,
        "weekly_rsi_bullish_divergence",
        "w_bottom_neckline_breakout",
    ):
        inputs[key] = {
            "status": "missing",
            "reason": "deterministic detector not implemented",
        }
    return {
        "schema_version": "technical_evidence_v1",
        "source": {
            "provider": "yfinance",
            "dataset": "daily_ohlcv",
            "price_adjustment": "auto_adjusted",
            "requested_period": "1y",
        },
        "as_of_date": "2026-08-17",
        "history_sessions": 230,
        "inputs": inputs,
    }


def test_technical_evidence_contract_requires_value_or_missing_reason() -> None:
    mod = _load_llm_score()
    evidence = _complete_technical_evidence(mod)
    ok, errors = mod.validate_technical_evidence(evidence)
    if not ok or errors:
        raise AssertionError(errors)

    broken = json.loads(json.dumps(evidence))
    broken["inputs"]["ma150"] = {"status": "missing"}
    ok, errors = mod.validate_technical_evidence(broken)
    if ok or not any("ma150" in error for error in errors):
        raise AssertionError(errors)

    broken = json.loads(json.dumps(evidence))
    del broken["inputs"]["weekly_macd_histogram"]
    ok, errors = mod.validate_technical_evidence(broken)
    if ok or not any("weekly_macd_histogram" in error for error in errors):
        raise AssertionError(errors)


def test_full_score_attaches_evidence_and_forbids_missing_credit() -> None:
    mod = _load_llm_score()
    evidence = _complete_technical_evidence(mod)
    evidence_values = {
        "price": 120.0,
        "ma50": 110.0,
        "ma150": 100.0,
        "ma200": 90.0,
        "ma200_1m_ago": 85.0,
        "low_52w": 80.0,
        "high_52w": 130.0,
        "rs_rating": 80.0,
        "volume_ratio_20d": 2.1,
        "close_position": 0.8,
        "price_change_1d": 2.0,
        "daily_macd": 1.0,
        "daily_macd_golden_cross_10d": True,
        "weekly_macd_histogram": 2.0,
        "weekly_macd_histogram_previous": 1.0,
    }
    for key, value in evidence_values.items():
        evidence["inputs"][key] = {"status": "available", "value": value}

    class FakeLLM:
        provider = "codex"

        def __init__(self):
            self.calls = []

        def chat(self, system, user, max_tokens=8192, cache_system=False):
            self.calls.append({"system": system, "user": user})
            return json.dumps({
                "ticker": "AAPL",
                "composite_score": 30,
                "scores": {
                    "technical": 30, "catalyst": 0, "sentiment": 0,
                    "institutional": 0, "sector_market": 0,
                    "options_flow": 0, "analyst": 0,
                },
                "technical_breakdown": {},
                "data_missing": [],
            })

    for name in (
        "fetch_polygon_news", "fetch_options_flow_summary", "fetch_free_sentiment",
        "fetch_fundamentals", "fetch_institutional", "fetch_analyst_views",
        "fetch_sector_rotation",
    ):
        setattr(mod, name, lambda *_args, **_kwargs: None)

    llm = FakeLLM()
    result = mod.score_candidate(
        llm,
        "screener rubric",
        {"scan_date": "2026-08-17", "global_score_multiplier": 1.0},
        {"ticker": "AAPL", "technical_evidence": evidence},
        scoring_mode="full",
    )

    if result.get("technical_evidence") != evidence:
        raise AssertionError(result)
    if result.get("technical_score_method") != "technical_evidence_v1_rubric_v1":
        raise AssertionError(result)
    if result["technical_breakdown"]["pattern"] != 0:
        raise AssertionError("missing pattern evidence must receive zero points")
    if result["scores"]["technical"] != 21:
        raise AssertionError(
            f"existing rubric should produce 10 trend + 8 volume + 0 pattern + 3 MACD: {result}"
        )
    if result["scores"]["technical"] != sum(
        result["technical_breakdown"][key]
        for key in ("trend_template", "volume", "pattern", "macd_confirmation")
    ):
        raise AssertionError(result)
    if result["composite_score"] != sum(result["scores"].values()):
        raise AssertionError(result)
    prompt = llm.calls[0]["user"]
    for needle in (
        "technical_evidence_v1",
        "Do not infer or award points for any technical input marked missing",
        "deterministic detector not implemented",
    ):
        if needle not in prompt:
            raise AssertionError(f"missing full-score evidence instruction: {needle}")


def test_full_score_rejects_malformed_technical_evidence_before_llm() -> None:
    mod = _load_llm_score()

    class FailLLM:
        provider = "codex"

        def chat(self, **_kwargs):
            raise AssertionError("malformed evidence must fail before the LLM call")

    try:
        mod.score_candidate(
            FailLLM(),
            "screener rubric",
            {"scan_date": "2026-08-17", "global_score_multiplier": 1.0},
            {"ticker": "BAD", "technical_evidence": {"schema_version": "wrong"}},
            scoring_mode="full",
        )
    except ValueError as exc:
        if "technical evidence" not in str(exc).lower():
            raise
    else:
        raise AssertionError("malformed evidence should raise ValueError")


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
        test_technical_evidence_contract_requires_value_or_missing_reason,
        test_full_score_attaches_evidence_and_forbids_missing_credit,
        test_full_score_rejects_malformed_technical_evidence_before_llm,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
