#!/usr/bin/env python3
"""Pure deterministic score contract shared by Stage 2 and its workflow gate."""

from __future__ import annotations

import math


SCORE_LIMITS = {
    "technical": 30,
    "catalyst": 16,
    "sentiment": 13,
    "institutional": 10,
    "sector_market": 3,
    "options_flow": 20,
    "analyst": 8,
}
VERDICT_RANK = {"REJECT": 0, "WATCHLIST": 1, "NEEDS_LAYER_2": 2}
RISK_VETOES = {"bearish_options_flow"}
TECHNICAL_COMPONENTS = (
    "trend_template",
    "volume",
    "pattern",
    "macd_confirmation",
)


def is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_score_values(scores: object) -> list[str]:
    if not isinstance(scores, dict) or set(scores) != set(SCORE_LIMITS):
        return ["scores must contain exactly the seven scoring dimensions"]
    errors = []
    for key, limit in SCORE_LIMITS.items():
        value = scores[key]
        if not is_finite_number(value) or not 0 <= value <= limit:
            errors.append(f"scores.{key} must be numeric within 0..{limit}")
    return errors


def expected_technical_contract(breakdown: object) -> tuple[float, int | None, float, list[dict]]:
    if not isinstance(breakdown, dict):
        raise ValueError("technical_breakdown must be an object")
    if not all(is_finite_number(breakdown.get(key)) for key in TECHNICAL_COMPONENTS):
        raise ValueError("technical breakdown components must be finite numbers")
    raw_total = round(sum(breakdown[key] for key in TECHNICAL_COMPONENTS), 2)
    applied_cap = (
        10
        if breakdown["pattern"] > 0 and breakdown["volume"] == 0
        else None
    )
    score = min(raw_total, applied_cap) if applied_cap is not None else raw_total
    adjustments = []
    if score < raw_total:
        adjustments.append({
            "rule": "technical_without_volume_cap",
            "before": raw_total,
            "after": score,
        })
    return raw_total, applied_cap, score, adjustments


def expected_composite_contract(scores: object) -> tuple[float, float, list[dict]]:
    errors = validate_score_values(scores)
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(scores, dict)
    uncapped = round(sum(scores.values()), 2)
    composite = uncapped
    adjustments = []
    if scores["technical"] < 12 and scores["sentiment"] >= 12:
        capped = min(uncapped, 50)
        if capped < uncapped:
            adjustments.append({
                "rule": "sentiment_without_technical_cap",
                "before": uncapped,
                "after": capped,
            })
        composite = min(composite, capped)
    if scores["technical"] < 12 and scores["options_flow"] >= 15:
        capped = min(uncapped, 55)
        if capped < uncapped:
            adjustments.append({
                "rule": "options_without_technical_cap",
                "before": uncapped,
                "after": capped,
            })
        composite = min(composite, capped)
    return uncapped, round(composite, 2), adjustments


def score_verdict(composite: object, multiplier: object) -> str:
    if not is_finite_number(composite):
        raise ValueError("composite_score must be a finite number")
    if not is_finite_number(multiplier) or multiplier <= 0:
        raise ValueError("global_score_multiplier must be a positive finite number")
    adjusted = round(composite * multiplier, 1)
    threshold = 72 if multiplier <= 0.7 else 65
    if adjusted >= threshold:
        return "NEEDS_LAYER_2"
    if adjusted >= 50:
        return "WATCHLIST"
    return "REJECT"


def expected_verdict_contract(
    composite: object,
    multiplier: object,
    data_missing: object,
    *,
    llm_verdict: object,
    llm_composite_score: object,
    llm_risk_vetoes: object,
    scoring_mode: str,
) -> tuple[str, list[dict]]:
    if not isinstance(data_missing, list) or not all(
        isinstance(token, str) for token in data_missing
    ):
        raise ValueError("data_missing must be a list of strings")
    if llm_verdict not in VERDICT_RANK:
        raise ValueError("llm_verdict must be a recognized verdict")
    if not is_finite_number(llm_composite_score) or not 0 <= llm_composite_score <= 100:
        raise ValueError("llm_composite_score must be numeric within 0..100")
    if (
        not isinstance(llm_risk_vetoes, list)
        or not all(isinstance(veto, str) for veto in llm_risk_vetoes)
        or len(llm_risk_vetoes) != len(set(llm_risk_vetoes))
        or not set(llm_risk_vetoes) <= RISK_VETOES
    ):
        raise ValueError("llm_risk_vetoes contains an unsupported veto")

    verdict = score_verdict(composite, multiplier)
    adjustments = []
    if scoring_mode == "full" and verdict == "NEEDS_LAYER_2":
        missing_dimensions = sorted(set(data_missing) & set(SCORE_LIMITS))
        if len(missing_dimensions) >= 2:
            adjustments.append({
                "rule": "incomplete_dimensions_downgrade",
                "before": "NEEDS_LAYER_2",
                "after": "WATCHLIST",
                "missing_dimensions": missing_dimensions,
            })
            verdict = "WATCHLIST"

    downgrade_targets = []
    if llm_risk_vetoes:
        downgrade_targets.append("WATCHLIST")
    llm_score_verdict = score_verdict(llm_composite_score, multiplier)
    if VERDICT_RANK[llm_verdict] < VERDICT_RANK[llm_score_verdict]:
        downgrade_targets.append(llm_verdict)
    target = (
        min(downgrade_targets, key=VERDICT_RANK.__getitem__)
        if downgrade_targets else verdict
    )
    if VERDICT_RANK[target] < VERDICT_RANK[verdict]:
        adjustment = {
            "rule": "llm_risk_verdict_downgrade",
            "before": verdict,
            "after": target,
        }
        if llm_risk_vetoes:
            adjustment["risk_vetoes"] = sorted(llm_risk_vetoes)
        adjustments.append(adjustment)
        verdict = target
    return verdict, adjustments


def validate_full_score_contract(
    row: object,
    regime_context: object,
) -> tuple[bool, list[str]]:
    """Return a fail-closed validation result for a persisted full-score row."""
    errors: list[str] = []
    if not isinstance(row, dict):
        return False, ["score row must be an object"]
    required = {
        "ticker", "verdict", "llm_verdict", "llm_composite_score",
        "llm_risk_vetoes",
        "composite_score", "uncapped_composite_score", "regime_adjusted_score",
        "scores", "data_missing", "scoring_mode", "technical_breakdown",
        "technical_score_method", "score_adjustments", "due_diligence_required",
    }
    if not required <= row.keys():
        errors.append("score row is missing required contract fields")
    if row.get("scoring_mode") != "full":
        errors.append("scoring_mode must be full")
    errors.extend(validate_score_values(row.get("scores")))
    if row.get("technical_score_method") != "technical_evidence_v1_rubric_v1":
        errors.append("technical_score_method is not deterministic")

    technical_adjustments: list[dict] = []
    try:
        raw_technical, applied_cap, technical, technical_adjustments = (
            expected_technical_contract(row.get("technical_breakdown"))
        )
        breakdown = row["technical_breakdown"]
        if not is_finite_number(breakdown.get("raw_total")) or not math.isclose(
            breakdown["raw_total"], raw_technical
        ):
            errors.append("technical_breakdown.raw_total is inconsistent")
        if breakdown.get("applied_cap") != applied_cap:
            errors.append("technical_breakdown.applied_cap is inconsistent")
        scores = row.get("scores")
        if not isinstance(scores, dict) or not is_finite_number(scores.get("technical")) or not math.isclose(
            scores["technical"], technical
        ):
            errors.append("scores.technical is inconsistent")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))

    composite_adjustments: list[dict] = []
    try:
        uncapped, composite, composite_adjustments = expected_composite_contract(
            row.get("scores")
        )
        if not is_finite_number(row.get("uncapped_composite_score")) or not math.isclose(
            row["uncapped_composite_score"], uncapped
        ):
            errors.append("uncapped_composite_score is inconsistent")
        if not is_finite_number(row.get("composite_score")) or not math.isclose(
            row["composite_score"], composite
        ):
            errors.append("composite_score is inconsistent")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
        composite = None

    multiplier = (
        regime_context.get("global_score_multiplier", 1.0)
        if isinstance(regime_context, dict)
        else None
    )
    verdict_adjustments: list[dict] = []
    try:
        if composite is None:
            raise ValueError("composite contract is unavailable")
        verdict, verdict_adjustments = expected_verdict_contract(
            composite,
            multiplier,
            row.get("data_missing"),
            llm_verdict=row.get("llm_verdict"),
            llm_composite_score=row.get("llm_composite_score"),
            llm_risk_vetoes=row.get("llm_risk_vetoes"),
            scoring_mode="full",
        )
        adjusted = round(composite * multiplier, 1)
        if not is_finite_number(row.get("regime_adjusted_score")) or not math.isclose(
            row["regime_adjusted_score"], adjusted
        ):
            errors.append("regime_adjusted_score is inconsistent")
        if row.get("verdict") != verdict:
            errors.append("verdict is inconsistent")
        if row.get("due_diligence_required") is not (verdict == "NEEDS_LAYER_2"):
            errors.append("due_diligence_required is inconsistent")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))

    expected_adjustments = (
        technical_adjustments + composite_adjustments + verdict_adjustments
    )
    if row.get("score_adjustments") != expected_adjustments:
        errors.append("score_adjustments provenance is inconsistent")
    return not errors, errors
