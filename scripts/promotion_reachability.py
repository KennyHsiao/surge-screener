#!/usr/bin/env python3
"""Pure shadow diagnostics for Stage 2 evidence reachability.

This module never changes scores or verdicts and performs no I/O.  It describes
the maximum score that the evidence supplied to Layer 1 can support, flags LLM
credit above that ceiling, and summarizes complete scoring cohorts.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from scoring_contract import (
        SCORE_LIMITS,
        expected_composite_contract,
        expected_technical_contract,
    )
except ImportError:  # when imported as a package
    from scripts.scoring_contract import (
        SCORE_LIMITS,
        expected_composite_contract,
        expected_technical_contract,
    )


CAPABILITY_SCHEMA_VERSION = "evidence_capabilities_v1"
CANDIDATE_SCHEMA_VERSION = "candidate_promotion_reachability_v1"
RUN_SCHEMA_VERSION = "promotion_reachability_v1"

UNSUPPORTED_TECHNICAL_PATTERNS = (
    "vcp",
    "cup_with_handle",
    "flat_base",
    "bull_flag",
    "higher_highs_lows_4w",
    "inverse_head_shoulders",
)
TECHNICAL_INPUTS = (
    "price",
    "ma50",
    "ma150",
    "ma200",
    "ma200_1m_ago",
    "low_52w",
    "high_52w",
    "rs_trailing_return_pct",
    "rs_rating",
    "today_volume",
    "avg_volume_20d",
    "volume_ratio_20d",
    "close_position",
    "price_change_1d",
    "daily_macd",
    "daily_macd_signal",
    "daily_macd_golden_cross_10d",
    "daily_macd_zero_cross_10d",
    "weekly_macd_histogram",
    "weekly_macd_histogram_previous",
    "w_bottom_shape",
    "weekly_rsi_bullish_divergence",
    "w_bottom_neckline_breakout",
    *UNSUPPORTED_TECHNICAL_PATTERNS,
)


def _number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _clean_number(value: float) -> int | float:
    rounded = round(float(value), 2)
    return int(rounded) if rounded.is_integer() else rounded


def _contains_number(value: object) -> bool:
    if _number(value):
        return True
    if isinstance(value, dict):
        return any(_contains_number(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_number(item) for item in value)
    return False


def _source_state(name: str, available: bool) -> str:
    return f"{name}:{'available' if available else 'unavailable'}"


def _configuration_state(name: str, configured: bool) -> str:
    return f"{name}:{'configured' if configured else 'unconfigured'}"


def _dimension(
    name: str,
    maximum: float | None,
    *,
    sources: list[str],
    missing_reasons: list[str],
) -> dict[str, Any]:
    return {
        "limit": SCORE_LIMITS[name],
        "max_supported_score": (
            None if maximum is None else _clean_number(maximum)
        ),
        "sources": list(dict.fromkeys(sources)),
        "missing_reasons": list(dict.fromkeys(missing_reasons)),
    }


def _input_available(inputs: dict[str, Any], *names: str) -> bool:
    return all(
        isinstance(inputs.get(name), dict)
        and inputs[name].get("status") == "available"
        for name in names
    )


def _technical_capability(evidence: object) -> dict[str, Any]:
    if not isinstance(evidence, dict) or evidence.get("schema_version") != "technical_evidence_v1":
        return _dimension(
            "technical",
            None,
            sources=["yfinance:daily_ohlcv:unknown"],
            missing_reasons=["technical_evidence_contract_invalid"],
        )
    inputs = evidence.get("inputs")
    if not isinstance(inputs, dict) or any(key not in inputs for key in TECHNICAL_INPUTS):
        return _dimension(
            "technical",
            None,
            sources=["yfinance:daily_ohlcv:unknown"],
            missing_reasons=["technical_evidence_inputs_incomplete"],
        )
    for key in TECHNICAL_INPUTS:
        item = inputs.get(key)
        if not isinstance(item, dict):
            return _dimension(
                "technical",
                None,
                sources=["yfinance:daily_ohlcv:unknown"],
                missing_reasons=["technical_evidence_inputs_invalid"],
            )
        if item.get("status") == "available":
            value = item.get("value")
            if isinstance(value, bool) or _number(value):
                continue
        if item.get("status") == "missing" and str(item.get("reason") or "").strip():
            continue
        return _dimension(
            "technical",
            None,
            sources=["yfinance:daily_ohlcv:unknown"],
            missing_reasons=["technical_evidence_inputs_invalid"],
        )

    trend_requirements = (
        ("price", "ma150", "ma200"),
        ("ma150", "ma200"),
        ("ma200", "ma200_1m_ago"),
        ("ma50", "ma150", "ma200"),
        ("price", "ma50"),
        ("price", "low_52w"),
        ("price", "high_52w"),
        ("rs_rating",),
    )
    trend_max = sum(
        1.25 for required in trend_requirements
        if _input_available(inputs, *required)
    )

    if _input_available(inputs, "volume_ratio_20d", "close_position"):
        volume_max = 8
    elif _input_available(inputs, "volume_ratio_20d", "price_change_1d"):
        volume_max = 6
    elif _input_available(inputs, "volume_ratio_20d"):
        volume_max = 3
    else:
        volume_max = 0

    pattern_candidates = [
        points for key, points in (
            ("vcp", 9),
            ("cup_with_handle", 8),
            ("flat_base", 7),
            ("bull_flag", 6),
            ("higher_highs_lows_4w", 4),
            ("inverse_head_shoulders", 6),
        )
        if _input_available(inputs, key)
    ]
    if _input_available(
        inputs,
        "w_bottom_shape",
        "weekly_rsi_bullish_divergence",
        "w_bottom_neckline_breakout",
        "daily_macd_zero_cross_10d",
    ):
        pattern_candidates.append(7)
    pattern_max = max(pattern_candidates, default=0)

    if _input_available(
        inputs,
        "daily_macd_golden_cross_10d",
        "weekly_macd_histogram",
        "weekly_macd_histogram_previous",
    ):
        macd_max = 3
    elif _input_available(inputs, "daily_macd_golden_cross_10d", "daily_macd"):
        macd_max = 2
    elif _input_available(inputs, "daily_macd"):
        macd_max = 1
    else:
        macd_max = 0

    _, _, maximum, _ = expected_technical_contract({
        "trend_template": trend_max,
        "volume": volume_max,
        "pattern": pattern_max,
        "macd_confirmation": macd_max,
    })
    reasons = []
    if maximum < SCORE_LIMITS["technical"]:
        reasons.append("technical_subsignals_unavailable")
    if any(not _input_available(inputs, key) for key in UNSUPPORTED_TECHNICAL_PATTERNS):
        reasons.append("continuation_pattern_detectors_unavailable")
    return _dimension(
        "technical",
        maximum,
        sources=["yfinance:daily_ohlcv:available"],
        missing_reasons=reasons,
    )


def _catalyst_capability(
    news: object,
    fundamentals: object,
    configuration: dict[str, bool],
) -> dict[str, Any]:
    if news is not None and (
        not isinstance(news, list)
        or any(not isinstance(item, dict) for item in news)
    ):
        return _dimension(
            "catalyst",
            None,
            sources=["polygon_news:unknown"],
            missing_reasons=["catalyst_news_contract_invalid"],
        )
    if fundamentals is not None and not isinstance(fundamentals, dict):
        return _dimension(
            "catalyst",
            None,
            sources=["fundamentals:unknown"],
            missing_reasons=["catalyst_fundamentals_contract_invalid"],
        )
    structured_8k = (
        isinstance(news, list)
        and any(
            isinstance(item, dict)
            and item.get("form_type") == "8-K"
            and bool(item.get("event_type"))
            for item in news
        )
    )
    surprise = (
        fundamentals.get("last_quarter_surprise")
        if isinstance(fundamentals, dict) else None
    )
    if surprise is not None and not isinstance(surprise, dict):
        return _dimension(
            "catalyst",
            None,
            sources=["fundamentals:unknown"],
            missing_reasons=["last_quarter_surprise_contract_invalid"],
        )
    structured_surprise = (
        isinstance(surprise, dict)
        and _number(surprise.get("eps_surprise_pct"))
        and _number(surprise.get("revenue_surprise_pct"))
    )
    maximum = (8 if structured_8k else 0) + (8 if structured_surprise else 0)
    reasons = []
    if not structured_8k:
        reasons.append("layer1_sec_8k_contract_unavailable")
    if not structured_surprise:
        reasons.append("last_quarter_surprise_contract_unavailable")
    return _dimension(
        "catalyst",
        maximum,
        sources=[
            _configuration_state("polygon_news", bool(configuration.get("polygon_news"))),
            _source_state("fundamentals", isinstance(fundamentals, dict)),
        ],
        missing_reasons=reasons,
    )


def _sentiment_capability(sentiment: object) -> dict[str, Any]:
    if sentiment is not None and not isinstance(sentiment, dict):
        return _dimension(
            "sentiment",
            None,
            sources=["free_social:unknown"],
            missing_reasons=["sentiment_contract_invalid"],
        )
    sources = (
        sentiment.get("sources_available")
        if isinstance(sentiment, dict) else None
    )
    if isinstance(sentiment, dict) and sources is not None and (
        not isinstance(sources, list)
        or any(not isinstance(item, str) or not item.strip() for item in sources)
    ):
        return _dimension(
            "sentiment",
            None,
            sources=["free_social:unknown"],
            missing_reasons=["sentiment_sources_contract_invalid"],
        )
    free_available = isinstance(sources, list) and any(
        isinstance(item, str) and bool(item.strip()) for item in sources
    )
    names = [
        f"free_social:{item}:available"
        for item in sources or [] if isinstance(item, str)
    ]
    if not names:
        names = ["free_social:unavailable"]
    reasons = ["layer1_x_velocity_unavailable", "smart_money_chatter_unavailable"]
    if not free_available:
        reasons.append("free_social_unavailable")
    return _dimension(
        "sentiment",
        3 if free_available else 0,
        sources=names,
        missing_reasons=reasons,
    )


def _institutional_capability(institutional: object) -> dict[str, Any]:
    if institutional is not None and not isinstance(institutional, dict):
        return _dimension(
            "institutional",
            None,
            sources=["yfinance_institutional:unknown"],
            missing_reasons=["institutional_contract_invalid"],
        )
    data = institutional or {}
    holders = data.get("top_institutional_holders")
    if holders is not None and (
        not isinstance(holders, list)
        or any(not isinstance(row, dict) for row in holders)
    ):
        return _dimension(
            "institutional",
            None,
            sources=["yfinance_institutional:unknown"],
            missing_reasons=["institutional_holders_contract_invalid"],
        )
    accumulation = (
        isinstance(holders, list)
        and any(isinstance(row, dict) and _number(row.get("pct_change")) for row in holders)
    )
    short_interest = data.get("short_interest")
    if short_interest is not None and not isinstance(short_interest, dict):
        return _dimension(
            "institutional",
            None,
            sources=["yfinance_institutional:unknown"],
            missing_reasons=["short_interest_contract_invalid"],
        )
    squeeze = (
        isinstance(short_interest, dict)
        and _number(short_interest.get("float_pct"))
        and _number(short_interest.get("days_to_cover"))
    )
    maximum = (4 if accumulation else 0) + (2 if squeeze else 0)
    reasons = ["insider_purchase_value_contract_unavailable"]
    if not accumulation:
        reasons.append("quarterly_13f_accumulation_unavailable")
    if not squeeze:
        reasons.append("short_interest_contract_unavailable")
    return _dimension(
        "institutional",
        maximum,
        sources=[_source_state("yfinance_institutional", bool(data))],
        missing_reasons=reasons,
    )


def _sector_capability(sector: object, regime_context: object) -> dict[str, Any]:
    if sector is not None and not isinstance(sector, dict):
        return _dimension(
            "sector_market",
            None,
            sources=["sector_rotation:unknown"],
            missing_reasons=["sector_rotation_contract_invalid"],
        )
    if regime_context is not None and not isinstance(regime_context, dict):
        return _dimension(
            "sector_market",
            None,
            sources=["market_regime:unknown"],
            missing_reasons=["market_regime_contract_invalid"],
        )
    candidate_sector = sector.get("candidate_sector") if isinstance(sector, dict) else None
    if candidate_sector is not None and not isinstance(candidate_sector, dict):
        return _dimension(
            "sector_market",
            None,
            sources=["sector_rotation:unknown"],
            missing_reasons=["candidate_sector_contract_invalid"],
        )
    quadrant = (
        candidate_sector.get("quadrant")
        if isinstance(candidate_sector, dict) else None
    )
    if quadrant is not None and quadrant not in {"Leading", "Improving", "Weakening", "Lagging"}:
        return _dimension(
            "sector_market",
            None,
            sources=["sector_rotation:unknown"],
            missing_reasons=["candidate_sector_quadrant_invalid"],
        )
    sector_available = (
        isinstance(candidate_sector, dict)
        and quadrant in {"Leading", "Improving", "Weakening", "Lagging"}
    )
    if isinstance(regime_context, dict) and (
        (
            regime_context.get("spy_vs_50dma") is not None
            and regime_context.get("spy_vs_50dma") not in {"above", "below"}
        )
        or (
            regime_context.get("vix_level") is not None
            and not _number(regime_context.get("vix_level"))
        )
    ):
        return _dimension(
            "sector_market",
            None,
            sources=["market_regime:unknown"],
            missing_reasons=["market_regime_inputs_invalid"],
        )
    regime_available = (
        isinstance(regime_context, dict)
        and regime_context.get("spy_vs_50dma") in {"above", "below"}
        and _number(regime_context.get("vix_level"))
    )
    reasons = []
    if not sector_available:
        reasons.append("candidate_sector_rotation_unavailable")
    if not regime_available:
        reasons.append("market_regime_inputs_unavailable")
    return _dimension(
        "sector_market",
        (2 if sector_available else 0) + (1 if regime_available else 0),
        sources=[
            _source_state("sector_rotation", sector_available),
            _source_state("market_regime", regime_available),
        ],
        missing_reasons=reasons,
    )


def _options_capability(options_flow: object, configuration: dict[str, bool]) -> dict[str, Any]:
    if options_flow is not None and not isinstance(options_flow, dict):
        return _dimension(
            "options_flow",
            None,
            sources=["options_flow:unknown"],
            missing_reasons=["options_flow_contract_invalid"],
        )
    data = options_flow or {}
    analysis = data.get("options_analysis")
    if analysis is not None and not isinstance(analysis, dict):
        return _dimension(
            "options_flow",
            None,
            sources=["yfinance_options:unknown"],
            missing_reasons=["free_options_contract_invalid"],
        )
    if isinstance(analysis, dict) and analysis.get("available") is True:
        maximum = analysis.get("max_possible")
        if not _number(maximum) or not 0 <= maximum <= SCORE_LIMITS["options_flow"]:
            return _dimension(
                "options_flow",
                None,
                sources=["yfinance_options:unknown"],
                missing_reasons=["free_options_maximum_invalid"],
            )
        return _dimension(
            "options_flow",
            float(maximum),
            sources=["yfinance_options:available"],
            missing_reasons=["sweeps_blocks_dark_pool_unavailable"],
        )
    flow_data = data.get("flow_data")
    if flow_data is not None and (
        not isinstance(flow_data, list)
        or any(not isinstance(item, dict) for item in flow_data)
    ):
        return _dimension(
            "options_flow",
            None,
            sources=["unusual_whales_flow:unknown"],
            missing_reasons=["paid_options_flow_contract_invalid"],
        )
    if isinstance(flow_data, list) and flow_data:
        return _dimension(
            "options_flow",
            14,
            sources=["unusual_whales_flow:available"],
            missing_reasons=["dark_pool_and_gex_contracts_unavailable"],
        )
    return _dimension(
        "options_flow",
        0,
        sources=[
            _configuration_state("unusual_whales_flow", bool(configuration.get("unusual_whales"))),
            "yfinance_options:unavailable",
        ],
        missing_reasons=["options_flow_unavailable"],
    )


def _analyst_capability(analyst: object) -> dict[str, Any]:
    if analyst is not None and not isinstance(analyst, dict):
        return _dimension(
            "analyst",
            None,
            sources=["yfinance_analyst:unknown"],
            missing_reasons=["analyst_contract_invalid"],
        )
    data = analyst or {}
    expected_shapes = {
        "rating_distribution": dict,
        "consensus": dict,
        "price_targets": dict,
        "recent_actions": list,
        "estimate_revisions": dict,
    }
    if any(
        key in data and data[key] is not None and not isinstance(data[key], shape)
        for key, shape in expected_shapes.items()
    ):
        return _dimension(
            "analyst",
            None,
            sources=["yfinance_analyst:unknown"],
            missing_reasons=["analyst_contract_invalid"],
        )
    ratings = _contains_number(data.get("rating_distribution")) or _contains_number(data.get("consensus"))
    targets = _contains_number(data.get("price_targets"))
    actions = data.get("recent_actions")
    momentum = (
        (isinstance(actions, list) and bool(actions))
        or _contains_number(data.get("estimate_revisions"))
    )
    reasons = []
    if not ratings:
        reasons.append("analyst_ratings_unavailable")
    if not targets:
        reasons.append("analyst_targets_unavailable")
    if not momentum:
        reasons.append("analyst_momentum_unavailable")
    return _dimension(
        "analyst",
        (3 if ratings else 0) + (3 if targets else 0) + (2 if momentum else 0),
        sources=[_source_state("yfinance_analyst", bool(data))],
        missing_reasons=reasons,
    )


def build_layer1_capabilities(
    *,
    technical_evidence: object,
    news: object,
    options_flow: object,
    sentiment: object,
    fundamentals: object,
    institutional: object,
    sector: object,
    analyst: object,
    regime_context: object,
    source_configuration: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Build a non-authoritative capability manifest from already-fetched data."""
    configuration = source_configuration if isinstance(source_configuration, dict) else {}
    dimensions = {
        "technical": _technical_capability(technical_evidence),
        "catalyst": _catalyst_capability(news, fundamentals, configuration),
        "sentiment": _sentiment_capability(sentiment),
        "institutional": _institutional_capability(institutional),
        "sector_market": _sector_capability(sector, regime_context),
        "options_flow": _options_capability(options_flow, configuration),
        "analyst": _analyst_capability(analyst),
    }
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_scoring": False,
        "dimensions": dimensions,
    }


def unknown_capability_manifest(reason: str) -> dict[str, Any]:
    """Return a valid fail-closed manifest without exposing exception text."""
    stable_reason = reason if isinstance(reason, str) and reason else "shadow_capability_unknown"
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_scoring": False,
        "dimensions": {
            name: _dimension(
                name,
                None,
                sources=["shadow_diagnostic:unknown"],
                missing_reasons=[stable_reason],
            )
            for name in SCORE_LIMITS
        },
    }


def safe_build_layer1_capabilities(**kwargs: object) -> dict[str, Any]:
    try:
        return build_layer1_capabilities(**kwargs)
    except Exception:  # shadow diagnostics must never stop production scoring
        return unknown_capability_manifest("shadow_capability_builder_error")


def validate_capability_manifest(manifest: object) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return False, ["capability_manifest_missing"]
    if manifest.get("schema_version") != CAPABILITY_SCHEMA_VERSION:
        errors.append("capability_schema_invalid")
    if manifest.get("mode") != "shadow":
        errors.append("capability_mode_invalid")
    if manifest.get("authoritative_for_scoring") is not False:
        errors.append("capability_authority_invalid")
    dimensions = manifest.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(SCORE_LIMITS):
        return False, [*errors, "capability_dimensions_invalid"]
    for name, limit in SCORE_LIMITS.items():
        item = dimensions.get(name)
        if not isinstance(item, dict):
            errors.append(f"capability_{name}_invalid")
            continue
        if item.get("limit") != limit:
            errors.append(f"capability_{name}_limit_invalid")
        maximum = item.get("max_supported_score")
        if maximum is not None and (not _number(maximum) or not 0 <= maximum <= limit):
            errors.append(f"capability_{name}_maximum_invalid")
        sources = item.get("sources")
        reasons = item.get("missing_reasons")
        if not isinstance(sources, list) or not all(isinstance(value, str) and value for value in sources):
            errors.append(f"capability_{name}_sources_invalid")
        if not isinstance(reasons, list) or not all(isinstance(value, str) and value for value in reasons):
            errors.append(f"capability_{name}_reasons_invalid")
        elif (maximum is None or maximum < limit) and not reasons:
            errors.append(f"capability_{name}_missing_reason_required")
    return not errors, errors


def _threshold(multiplier: object) -> int | None:
    if not _number(multiplier) or multiplier <= 0:
        return None
    return 72 if multiplier <= 0.7 else 65


def _unknown_candidate(reasons: list[str], multiplier: object) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_promotion": False,
        "state": "unknown",
        "threshold": _threshold(multiplier),
        "global_score_multiplier": multiplier if _number(multiplier) else None,
        "evidence_ceiling": None,
        "adjusted_ceiling": None,
        "ceiling_score_vector": None,
        "ceiling_adjustments": [],
        "unsupported_credit": [],
        "unknown_reasons": list(dict.fromkeys(reasons)),
    }


def _maximum_supported_composite(
    dimensions: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, float], list[dict[str, Any]]]:
    """Maximize the existing composite contract within dimension ceilings."""
    maxima = {
        name: float(dimensions[name]["max_supported_score"])
        for name in SCORE_LIMITS
    }
    sentiment_values = [maxima["sentiment"]]
    if maxima["sentiment"] >= 12:
        sentiment_values.append(11.99)
    options_values = [maxima["options_flow"]]
    if maxima["options_flow"] >= 15:
        options_values.append(14.99)

    best: tuple[float, dict[str, float], list[dict[str, Any]]] | None = None
    for sentiment in sentiment_values:
        for options_flow in options_values:
            score_vector = {
                **maxima,
                "sentiment": sentiment,
                "options_flow": options_flow,
            }
            _, composite, adjustments = expected_composite_contract(score_vector)
            candidate = (composite, score_vector, adjustments)
            if best is None or candidate[0] > best[0]:
                best = candidate
    assert best is not None
    return best


def build_candidate_diagnostic(
    row: object,
    manifest: object,
    multiplier: object,
) -> dict[str, Any]:
    """Return a shadow diagnostic without mutating the candidate row."""
    reasons: list[str] = []
    if not isinstance(row, dict):
        reasons.append("candidate_row_invalid")
    elif row.get("scoring_mode") != "full":
        reasons.append("scoring_mode_not_full")
    scores = row.get("scores") if isinstance(row, dict) else None
    if not isinstance(scores, dict) or set(scores) != set(SCORE_LIMITS):
        reasons.append("candidate_scores_invalid")
    elif any(
        not _number(scores[name]) or not 0 <= scores[name] <= SCORE_LIMITS[name]
        for name in SCORE_LIMITS
    ):
        reasons.append("candidate_score_value_invalid")
    valid_manifest, manifest_errors = validate_capability_manifest(manifest)
    if not valid_manifest:
        reasons.extend(manifest_errors)
    threshold = _threshold(multiplier)
    if threshold is None:
        reasons.append("regime_multiplier_invalid")
    if reasons:
        return _unknown_candidate(reasons, multiplier)

    assert isinstance(scores, dict)
    assert isinstance(manifest, dict)
    dimensions = manifest["dimensions"]
    maxima = [dimensions[name]["max_supported_score"] for name in SCORE_LIMITS]
    if any(maximum is None for maximum in maxima):
        return _unknown_candidate(["capability_maximum_unknown"], multiplier)

    ceiling_raw, ceiling_vector, ceiling_adjustments = _maximum_supported_composite(
        dimensions
    )
    ceiling = _clean_number(ceiling_raw)
    adjusted = _clean_number(round(float(ceiling) * float(multiplier), 1))
    unsupported = []
    for name in SCORE_LIMITS:
        awarded = float(scores[name])
        supported = float(dimensions[name]["max_supported_score"])
        if awarded > supported:
            unsupported.append({
                "dimension": name,
                "awarded_score": _clean_number(awarded),
                "max_supported_score": _clean_number(supported),
                "delta": _clean_number(awarded - supported),
            })
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_promotion": False,
        "state": "reachable" if adjusted >= threshold else "not_reachable",
        "threshold": threshold,
        "global_score_multiplier": _clean_number(float(multiplier)),
        "evidence_ceiling": ceiling,
        "adjusted_ceiling": adjusted,
        "ceiling_score_vector": {
            name: _clean_number(value) for name, value in ceiling_vector.items()
        },
        "ceiling_adjustments": ceiling_adjustments,
        "unsupported_credit": unsupported,
        "unknown_reasons": [],
    }


def safe_build_candidate_diagnostic(
    row: object,
    manifest: object,
    multiplier: object,
) -> dict[str, Any]:
    try:
        return build_candidate_diagnostic(row, manifest, multiplier)
    except Exception:  # shadow diagnostics must never change production routing
        return _unknown_candidate(["shadow_candidate_diagnostic_error"], multiplier)


def _run_base(rows: object, multiplier: object) -> dict[str, Any]:
    candidate_rows = rows if isinstance(rows, list) else []
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_promotion": False,
        "state": "unknown",
        "threshold": _threshold(multiplier),
        "global_score_multiplier": (
            _clean_number(float(multiplier)) if _number(multiplier) else None
        ),
        "candidate_count": len(candidate_rows),
        "diagnosed_candidate_count": 0,
        "candidate_ceiling_max": None,
        "candidate_adjusted_ceiling_max": None,
        "unsupported_credit_count": 0,
        "unsupported_credit_tickers": [],
        "unknown_reasons": [],
    }


def summarize_run(
    rows: object,
    *,
    multiplier: object,
    total_candidates: object,
) -> dict[str, Any]:
    """Summarize candidate diagnostics for one complete scoring cohort."""
    candidate_rows = rows if isinstance(rows, list) else []
    threshold = _threshold(multiplier)
    base = _run_base(rows, multiplier)
    if (
        not isinstance(rows, list)
        or not isinstance(total_candidates, int)
        or isinstance(total_candidates, bool)
        or total_candidates <= 0
        or len(candidate_rows) != total_candidates
    ):
        base["unknown_reasons"] = ["incomplete_cohort"]
        return base
    if threshold is None:
        base["unknown_reasons"] = ["regime_multiplier_invalid"]
        return base

    valid_diagnostics = []
    unknown_reasons = []
    for row in candidate_rows:
        diagnostic = row.get("promotion_reachability") if isinstance(row, dict) else None
        if not isinstance(diagnostic, dict) or diagnostic.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
            unknown_reasons.append("candidate_diagnostic_missing")
            continue
        try:
            expected = build_candidate_diagnostic(
                row,
                row.get("evidence_capabilities") if isinstance(row, dict) else None,
                multiplier,
            )
        except Exception:
            unknown_reasons.append("candidate_diagnostic_rebuild_error")
            continue
        if diagnostic != expected:
            unknown_reasons.append("candidate_diagnostic_inconsistent")
            continue
        if expected.get("state") not in {"reachable", "not_reachable"}:
            unknown_reasons.extend(expected.get("unknown_reasons") or ["candidate_diagnostic_unknown"])
            continue
        valid_diagnostics.append((row, expected))

    base["diagnosed_candidate_count"] = len(valid_diagnostics)
    if unknown_reasons or len(valid_diagnostics) != total_candidates:
        base["unknown_reasons"] = list(dict.fromkeys(unknown_reasons or ["candidate_diagnostic_missing"]))
        return base

    base["candidate_ceiling_max"] = max(
        diagnostic["evidence_ceiling"] for _, diagnostic in valid_diagnostics
    )
    base["candidate_adjusted_ceiling_max"] = max(
        diagnostic["adjusted_ceiling"] for _, diagnostic in valid_diagnostics
    )
    unsupported_tickers = []
    unsupported_count = 0
    for row, diagnostic in valid_diagnostics:
        findings = diagnostic.get("unsupported_credit")
        if isinstance(findings, list) and findings:
            unsupported_count += len(findings)
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                unsupported_tickers.append(ticker)
    base["unsupported_credit_count"] = unsupported_count
    base["unsupported_credit_tickers"] = list(dict.fromkeys(unsupported_tickers))
    base["state"] = (
        "reachable"
        if any(diagnostic["state"] == "reachable" for _, diagnostic in valid_diagnostics)
        else "not_reachable"
    )
    return base


def safe_summarize_run(
    rows: object,
    *,
    multiplier: object,
    total_candidates: object,
) -> dict[str, Any]:
    try:
        return summarize_run(
            rows,
            multiplier=multiplier,
            total_candidates=total_candidates,
        )
    except Exception:  # partial output must remain writable if shadow code fails
        result = _run_base(rows, multiplier)
        result["unknown_reasons"] = ["shadow_run_summary_error"]
        return result
