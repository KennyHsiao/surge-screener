#!/usr/bin/env python3
"""Classify post-setup continuation strength from forward outcomes."""

from __future__ import annotations

from typing import Any


def classify_continuation(row: dict[str, Any]) -> dict[str, Any]:
    resolved_30 = bool(row.get("resolved_30d"))
    resolved_60 = bool(row.get("resolved_60d"))

    if not resolved_30 and not resolved_60:
        return {
            "ticker": row.get("ticker"),
            "setup_date": row.get("setup_date") or row.get("as_of_date"),
            "continuation_label": "unresolved",
            "primary_horizon": None,
            "trade_value": "unknown",
        }

    r30 = row.get("fwd_30d_return")
    dd30 = row.get("fwd_30d_max_drawdown")
    r60 = row.get("fwd_60d_return")
    dd60 = row.get("fwd_60d_max_drawdown")

    strong_30 = (
        resolved_30
        and r30 is not None
        and dd30 is not None
        and float(r30) >= 0.15
        and float(dd30) >= -0.10
    )
    strong_60 = (
        resolved_60
        and r60 is not None
        and dd60 is not None
        and float(r60) >= 0.30
        and float(dd60) >= -0.15
    )
    if strong_30:
        label, horizon, value = "strong_continuation", "30d", "high"
    elif strong_60:
        label, horizon, value = "strong_continuation", "60d", "high"
    elif resolved_30 and r30 is not None and float(r30) > 0:
        label, horizon, value = "normal_continuation", "30d", "medium"
    else:
        label, horizon, value = "failed_breakout", "30d" if resolved_30 else "60d", "low"

    return {
        "ticker": row.get("ticker"),
        "setup_date": row.get("setup_date") or row.get("as_of_date"),
        "continuation_label": label,
        "primary_horizon": horizon,
        "trade_value": value,
    }
