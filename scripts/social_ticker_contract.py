"""Pure provenance and eligibility rules for social-intelligence tickers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DATED_JSON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
EVIDENCE_BOOL_KEYS = (
    "explicit_cashtag",
    "known_universe_symbol",
    "trusted_curated_source",
)


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper().lstrip("$")


def load_known_tickers(universe_dir: str | Path) -> set[str]:
    """Return the union of locally observed securities from dated snapshots."""
    root = Path(universe_dir)
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for path in sorted(root.glob("*.json")):
        if not DATED_JSON_RE.match(path.name):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = data.get("securities") if isinstance(data, dict) else None
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            ticker = normalize_ticker(row.get("ticker") or row.get("symbol"))
            if ticker:
                out.add(ticker)
    return out


def normalize_evidence(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    sources: list[str] = []
    for item in source.get("sources") if isinstance(source.get("sources"), list) else []:
        text = str(item or "").strip()
        if text and text not in sources:
            sources.append(text)
    return {
        **{key: bool(source.get(key)) for key in EVIDENCE_BOOL_KEYS},
        "sources": sources,
    }


def merge_evidence(
    current: Any,
    incoming: Any,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    left = normalize_evidence(current)
    right = normalize_evidence(incoming)
    sources = list(left["sources"])
    for item in [*right["sources"], source]:
        text = str(item or "").strip()
        if text and text not in sources:
            sources.append(text)
    return {
        **{key: bool(left[key] or right[key]) for key in EVIDENCE_BOOL_KEYS},
        "sources": sources,
    }


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def outcome_eligibility(
    social: dict[str, Any],
    *,
    known_tickers: set[str],
    prior_outcome: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Fail closed unless a symbol has evidence independent of uppercase prose."""
    ticker = normalize_ticker(social.get("ticker"))
    if not ticker:
        return False, "missing_ticker"
    evidence = normalize_evidence(social.get("ticker_evidence"))
    if ticker in known_tickers or evidence["known_universe_symbol"]:
        return True, "known_universe_symbol"
    validation = social.get("platform_validation")
    if isinstance(validation, dict) and (
        validation.get("in_ranked_candidates") is True
        or _positive_number(validation.get("options_flow_score"))
    ):
        return True, "platform_validation"
    heat = social.get("heat_baseline")
    if isinstance(heat, dict):
        stocktwits = heat.get("stocktwits")
        apewisdom = heat.get("apewisdom")
        if isinstance(stocktwits, dict) and stocktwits.get("status") == "available":
            return True, "retail_platform_validation"
        if isinstance(apewisdom, dict) and apewisdom.get("in_top_mentions") is True:
            return True, "retail_platform_validation"
    if isinstance(prior_outcome, dict) and _positive_number(prior_outcome.get("entry_price")):
        return True, "prior_market_data"
    if evidence["explicit_cashtag"]:
        return False, "cashtag_unverified"
    if (
        evidence["trusted_curated_source"]
        or "x_influencer_picks" in (social.get("discovery_sources") or [])
    ):
        return False, "curated_ticker_unverified"
    return False, "unverified_ticker"
