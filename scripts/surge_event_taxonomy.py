#!/usr/bin/env python3
"""Classify surge events into result labels and candidate-cause tags."""

from __future__ import annotations

from typing import Any


def _num(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        out = float(value)
        return 0.0 if out != out else out
    except (TypeError, ValueError):
        return 0.0


def classify_surge_event(event: dict[str, Any]) -> dict[str, Any]:
    thresholds = event.get("thresholds_hit") or [event.get("threshold")]
    thresholds = [str(t) for t in thresholds if t]
    result_family = "multi_threshold_surge" if len(thresholds) >= 2 else "single_threshold_surge"

    gap = _num(event.get("gap_pct"))
    sessions = int(_num(event.get("sessions_to_peak")))
    if gap >= 0.08:
        price_structure = "gap_impulse"
    elif sessions <= 10:
        price_structure = "fast_reversal"
    else:
        price_structure = "trend_continuation"

    candidate_causes: list[str] = []
    if _num(event.get("volume_ratio_20d")) >= 1.8:
        candidate_causes.append("technical_volume_expansion")
    if _num(event.get("rs_vs_spy_20d")) >= 0.10:
        candidate_causes.append("relative_strength_leadership")
    if _num(event.get("sector_rs_20d")) >= 0.05:
        candidate_causes.append("sector_support")
    if bool(event.get("earnings_within_5d")):
        candidate_causes.append("earnings_catalyst")
    if event.get("news_catalyst"):
        candidate_causes.append("sourced_event_catalyst")

    return {
        "ticker": event.get("ticker"),
        "result_family": result_family,
        "price_structure": price_structure,
        "candidate_causes": candidate_causes or ["unknown"],
        "cause_certainty": "candidate_only",
    }
