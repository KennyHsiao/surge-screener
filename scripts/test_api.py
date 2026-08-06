#!/usr/bin/env python3
"""Contract and HTTP tests for the loopback fail-soft read API."""

from __future__ import annotations

import ast
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api.artifacts as artifact_module  # noqa: E402
import api.models as model_module  # noqa: E402
from api.artifacts import (  # noqa: E402
    AI_UPDATES_SOURCE_ID,
    ARTIFACTS,
    CRYPTO_UNIVERSE_SOURCE_ID,
    CONTINUATION_VALIDATION_SOURCE_ID,
    DAILY_SUMMARY_SOURCE_ID,
    FUND_CATALOG_SOURCE_ID,
    IV_HISTORY_SOURCE_ID,
    MARKET_THESIS_REGIME_HISTORY_SOURCE_ID,
    MARKET_THESIS_SOURCE_ID,
    MARKET_THESIS_VALIDATION_SOURCE_ID,
    MONEY_FLOW_SOURCE_ID,
    OVERSOLD_REVERSAL_SOURCE_ID,
    OVERSOLD_REVERSAL_VALIDATION_SOURCE_ID,
    PLAYBOOK_VALIDATION_SOURCE_ID,
    REVERSAL_RADAR_SOURCE_ID,
    SCHEDULES_SOURCE_ID,
    SCORED_CANDIDATES_SCREENER_SOURCE_ID,
    SECTOR_ROTATION_SOURCE_ID,
    SOCIAL_INTELLIGENCE_SOURCE_ID,
    THEME_FLOW_ANALYSIS_SOURCE_ID,
    THEME_FLOW_SOURCE_ID,
    ArtifactPathUnavailable,
    ArtifactSpec,
    ResolvedArtifactPath,
    iv_history_spec,
    normalize_ticker,
    read_artifact,
    resolve_latest_market_thesis,
)
from api.models import (  # noqa: E402
    AiUpdatesData,
    ArtifactAvailable,
    ArtifactUnavailable,
    CryptoUniverseData,
    ContinuationValidationData,
    DailySummaryData,
    FundCatalogData,
    IvHistoryData,
    MarketThesisData,
    MarketThesisRegimeHistoryData,
    MarketThesisValidationData,
    MoneyFlowData,
    OversoldReversalValidationData,
    PlaybookValidationData,
    RankedCandidatesData,
    SchedulesData,
    ScoredCandidatesScreenerData,
    SectorRotationData,
    SocialIntelligenceData,
    ThemeFlowAnalysisData,
    ThemeFlowData,
)
from api.main import create_app  # noqa: E402
from scripts.artifact_loader import load_json_artifact  # noqa: E402


EXPECTED_REGISTRY = {
    "candidates.ranked": ("ranked_candidates",),
    "candidates.ranked.feed": (),
    "candidates.scored": ("all_scored",),
    "candidates.scored.feed": (),
    "candidates.scored.screener": (),
    "crypto.universe": (),
    "signals.options-flow.latest": ("signals",),
    "signals.options-flow.feed": (),
    "signals.reversal-radar.latest": (),
    "signals.reversal-radar.validation": (),
    "signals.oversold-reversal.latest": (),
    "signals.oversold-reversal.validation": (),
    "market-context.market-thesis.latest": (),
    "market-context.market-thesis.validation": (),
    "market-context.market-thesis.regime-history": (),
    "reports.daily-summary.latest": (),
    "reports.playbook-validation.latest": (),
    "reports.continuation-validation.latest": (),
    "market-context.money-flow.latest": (),
    "market-context.sector-rotation.latest": (),
    "market-context.theme-flow.latest": (),
    "market-context.theme-flow.analysis": (),
    "social.intelligence.latest": (),
    "institutions.funds": (),
    "system.ai-updates": (),
    "system.schedules": (),
}
EXPECTED_PATHS = {
    "/healthz",
    "/api/v1/private/industry-roles/review-board",
    "/api/v1/private/industry-roles/review-board/actions",
    "/api/v1/candidates/ranked",
    "/api/v1/candidates/ranked/feed",
    "/api/v1/candidates/scored",
    "/api/v1/candidates/scored/feed",
    "/api/v1/candidates/scored/screener",
    "/api/v1/crypto/universe",
    "/api/v1/signals/options-flow/latest",
    "/api/v1/signals/options-flow/feed",
    "/api/v1/signals/reversal-radar/latest",
    "/api/v1/signals/reversal-radar/validation",
    "/api/v1/signals/oversold-reversal/latest",
    "/api/v1/signals/oversold-reversal/validation",
    "/api/v1/market-context/market-thesis/latest",
    "/api/v1/market-context/market-thesis/validation",
    "/api/v1/market-context/market-thesis/regime-history",
    "/api/v1/reports/daily-summary/latest",
    "/api/v1/reports/playbook-validation/latest",
    "/api/v1/reports/continuation-validation/latest",
    "/api/v1/reports/cot",
    "/api/v1/reports/cot/{report_date}",
    "/api/v1/market-context/money-flow/latest",
    "/api/v1/market-context/sector-rotation/latest",
    "/api/v1/market-context/theme-drill",
    "/api/v1/knowledge/graph",
    "/api/v1/watchlists/theme-taxonomy",
    "/api/v1/social/influencers",
    "/api/v1/market-context/theme-flow/latest",
    "/api/v1/market-context/theme-flow/analysis",
    "/api/v1/social/intelligence/latest",
    "/api/v1/options/iv-history/{ticker}",
    "/api/v1/institutions/funds",
    "/api/v1/system/ai-updates",
    "/api/v1/system/schedules",
}
SOURCE_PATHS = {
    "candidates.ranked": "/api/v1/candidates/ranked",
    "candidates.ranked.feed": "/api/v1/candidates/ranked/feed",
    "candidates.scored": "/api/v1/candidates/scored",
    "candidates.scored.feed": "/api/v1/candidates/scored/feed",
    "candidates.scored.screener": "/api/v1/candidates/scored/screener",
    "crypto.universe": "/api/v1/crypto/universe",
    "signals.options-flow.latest": "/api/v1/signals/options-flow/latest",
    "signals.options-flow.feed": "/api/v1/signals/options-flow/feed",
    "signals.reversal-radar.latest": "/api/v1/signals/reversal-radar/latest",
    "signals.reversal-radar.validation": "/api/v1/signals/reversal-radar/validation",
    "signals.oversold-reversal.latest": "/api/v1/signals/oversold-reversal/latest",
    "signals.oversold-reversal.validation": "/api/v1/signals/oversold-reversal/validation",
    "market-context.market-thesis.latest": "/api/v1/market-context/market-thesis/latest",
    "market-context.market-thesis.validation": "/api/v1/market-context/market-thesis/validation",
    "market-context.market-thesis.regime-history": "/api/v1/market-context/market-thesis/regime-history",
    "reports.daily-summary.latest": "/api/v1/reports/daily-summary/latest",
    "reports.playbook-validation.latest": "/api/v1/reports/playbook-validation/latest",
    "reports.continuation-validation.latest": "/api/v1/reports/continuation-validation/latest",
    "market-context.money-flow.latest": "/api/v1/market-context/money-flow/latest",
    "market-context.sector-rotation.latest": "/api/v1/market-context/sector-rotation/latest",
    "market-context.theme-flow.latest": "/api/v1/market-context/theme-flow/latest",
    "market-context.theme-flow.analysis": "/api/v1/market-context/theme-flow/analysis",
    "social.intelligence.latest": "/api/v1/social/intelligence/latest",
    "institutions.funds": "/api/v1/institutions/funds",
    "system.ai-updates": "/api/v1/system/ai-updates",
    "system.schedules": "/api/v1/system/schedules",
}

AI_UPDATES_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
AI_UPDATES_LINK_PATTERN = (
    r"^https://[^/@?#\s\x00-\x1f\x7f]+(?:[/?#][^\s\x00-\x1f\x7f]*)?$"
)
AI_UPDATES_TAG_PATTERN = r"^\S(?:[\s\S]*\S)?$"
SCHEDULE_IDENTIFIER_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
SCHEDULE_REQUIRED_TEXT_PATTERN = r"^\S(?:[\s\S]*\S)?$"
SCHEDULE_OPTIONAL_TEXT_PATTERN = r"^(?:|\S(?:[\s\S]*\S)?)$"
SCHEDULE_FIELDS = (
    "id",
    "name",
    "category",
    "cron",
    "cron_note",
    "description",
    "result_type",
)
OPTIONS_FLOW_FEED_SOURCE_ID = "signals.options-flow.feed"
OPTIONS_FLOW_FEED_ROUTE = "/api/v1/signals/options-flow/feed"
OPTIONS_FLOW_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
OPTIONS_FLOW_PROVIDER_PATTERN = (
    r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*(?![\s\S])"
)
OPTIONS_FLOW_TICKER_PATTERN = r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*(?![\s\S])"
OPTIONS_FLOW_TAG_PATTERN = r"^\S(?:[\s\S]*\S)?(?![\s\S])"
OPTIONS_FLOW_RFC3339_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)"
    r"(?![\s\S])"
)
OPTIONS_FLOW_FEED_FIELDS = (
    "generated_at",
    "as_of",
    "provider",
    "universe_size",
    "min_notional",
    "signal_count",
    "signals",
)
OPTIONS_FLOW_SIGNAL_FIELDS = (
    "ticker",
    "direction",
    "flow_score",
    "est_notional_usd",
    "biggest",
    "expiry",
    "max_voi",
    "high_voi_strikes",
    "call_put_ratio",
    "put_call_ratio",
    "tags",
)
OPTIONS_FLOW_BIGGEST_FIELDS = ("strike", "notional")
CRYPTO_UNIVERSE_FIELDS = (
    "date",
    "source",
    "source_status",
    "stale",
    "stale_source_date",
    "count",
    "universe",
    "added",
    "removed",
    "compared_to",
)


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _ai_update(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "date": "2026-07-15",
        "title": "AI update",
        "summary": "Public summary",
        "link": "https://example.com/update",
        "tags": ["AI"],
    }
    item.update(overrides)
    return item


def _schedule(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "daily_screen",
        "name": "Daily screen",
        "category": "System",
        "cron": "15 6 * * 2-6",
        "cron_note": "Weekdays 06:15 Asia/Taipei",
        "description": "Refresh the public schedule fixture.",
        "result_type": "report_dir",
    }
    item.update(overrides)
    return item


def _options_flow_signal(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "ticker": "NVDA",
        "direction": "bullish",
        "flow_score": 91.5,
        "est_notional_usd": 12_500_000,
        "biggest": {
            "strike": 150.0,
            "notional": 4_250_000.5,
            "premium": 12.75,
            "volume": 4000,
            "voi": 8.5,
            "nested_private_sentinel": "drop-biggest-secret",
        },
        "expiry": "2026-08-21",
        "max_voi": 8.5,
        "high_voi_strikes": 3,
        "call_put_ratio": 2.4,
        "put_call_ratio": 0.42,
        "tags": ["unusual", "sweep"],
        "provider": "writer-private-provider",
        "total_call_vol": 9000,
        "total_put_vol": 3750,
        "otm_call_vol": 6000,
        "spot": 146.25,
        "signal_private_sentinel": "drop-signal-secret",
    }
    item.update(overrides)
    return item


def _options_flow_source(
    signals: list[object] | None = None,
    *,
    generated_at: object = "2026-07-15T06:30:00+00:00",
    as_of: object = "2026-07-15",
    provider: object = "yfinance.options-v2",
    universe_size: object | None = None,
    min_notional: object = 250_000,
    signal_count: object | None = None,
    note: object = "writer-private-note-sentinel",
) -> dict[str, object]:
    selected = [_options_flow_signal()] if signals is None else signals
    return {
        "generated_at": generated_at,
        "as_of": as_of,
        "provider": provider,
        "universe_size": len(selected) if universe_size is None else universe_size,
        "min_notional": min_notional,
        "signal_count": len(selected) if signal_count is None else signal_count,
        "note": note,
        "signals": selected,
    }


def _options_flow_feed_spec(path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[OPTIONS_FLOW_FEED_SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _options_flow_unavailable(reason: str = "invalid_shape") -> dict[str, object]:
    return {
        "available": False,
        "reason": reason,
        "data": None,
        "meta": {
            "sourceId": OPTIONS_FLOW_FEED_SOURCE_ID,
            "asOf": None,
            "generatedAt": None,
        },
    }


def _public_options_flow(source: dict[str, object]) -> dict[str, object]:
    signals = source["signals"]
    if not isinstance(signals, list):
        raise TypeError("fixture signals must be an array")
    public_signals: list[dict[str, object]] = []
    for raw_signal in signals:
        if not isinstance(raw_signal, dict):
            raise TypeError("fixture signal must be an object")
        public_signal = {
            field: deepcopy(raw_signal[field]) for field in OPTIONS_FLOW_SIGNAL_FIELDS
        }
        biggest = public_signal["biggest"]
        if isinstance(biggest, dict):
            public_signal["biggest"] = {
                field: deepcopy(biggest[field]) for field in OPTIONS_FLOW_BIGGEST_FIELDS
            }
        public_signals.append(public_signal)
    return {
        **{
            field: deepcopy(source[field])
            for field in OPTIONS_FLOW_FEED_FIELDS
            if field != "signals"
        },
        "signals": public_signals,
    }


def _parse_rfc3339(value: str) -> datetime:
    normalized = f"{value[:-1]}+00:00" if value.endswith(("Z", "z")) else value
    return datetime.fromisoformat(normalized)


def _schedules_source(
    schedules: list[object] | None = None,
    *,
    note: object = "fixture maintainer guidance",
) -> dict[str, object]:
    return {
        "_note": note,
        "schedules": [_schedule()] if schedules is None else schedules,
    }


def _schedules_unavailable(reason: str = "invalid_shape") -> dict[str, object]:
    return {
        "available": False,
        "reason": reason,
        "data": None,
        "meta": {
            "sourceId": "system.schedules",
            "asOf": None,
            "generatedAt": None,
        },
    }


def _crypto_universe_source() -> dict[str, object]:
    return {
        "date": "2026-07-15",
        "source": "binance_fapi_exchangeInfo",
        "source_status": "live",
        "stale": False,
        "stale_source_date": None,
        "fetch_error": None,
        "count": 1,
        "symbols": ["BTCUSDT"],
        "universe": [
            {
                "symbol": "BTCUSDT",
                "base": "BTC",
                "tv_symbol": "BINANCE:BTCUSDT.P",
                "onboard_date": "2019-09-25",
            }
        ],
        "added": [],
        "removed": [],
        "compared_to": None,
    }


def _market_thesis_source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of": "2026-07-14",
        "generated_at": "2026-07-14T12:00:00+00:00",
        "tier": 1,
        "method": "deterministic_baseline",
        "benchmark": "^GSPC",
        "direction": "盤整",
        "bucket": "mid",
        "support_class": "regime_only",
        "manifest_status": "degraded",
        "regime": "range",
        "vix_bucket": "normal",
        "rationale": {
            "analog": {
                "resolved": 12,
                "mean": 0.01,
                "median": 0.02,
                "up_rate": 0.6,
                "ci90": [-0.01, 0.03],
                "p10": -0.08,
                "worst": -0.2,
                "mean_mdd": -0.04,
                "worst_mdd": -0.2,
            },
            "bear_telemetry": None,
            "manifest_missing": ["CPI"],
            "manifest_stale": ["FOMC"],
            "macro": {},
            "manifest_events": [
                {
                    "type": "CPI",
                    "source_id": "fred:CPIAUCSL",
                    "present": False,
                    "fresh": False,
                    "stale_reason": "missing",
                }
            ],
        },
        "label": "探索性,未驗證,非投資建議",
    }
    payload.update(overrides)
    return payload


def _market_thesis_validation_source() -> dict[str, object]:
    return {
        "generated_at": "2026-08-04T02:03:04+00:00",
        "benchmark": "^GSPC",
        "theta_dir": 0.03,
        "buckets": {"short": 20, "mid": 40, "long": 60},
        "validation_status": "ok",
        "reject_count": 0,
        "rejected_ledgers": [],
        "note": "private validation note",
        "resolved": 2,
        "matured": 2,
        "invalid_records": [],
        "invalid_count": 0,
        "min_resolved_for_verdict": 100,
        "by_key": {
            "盤整|short|regime_only": {
                "direction": "盤整",
                "bucket": "short",
                "support_class": "regime_only",
                "raw_N": 2,
                "counted_N": 1,
                "hits": 1,
                "hit_rate": 1.0,
                "wilson90": [0.2699, 1.0],
                "verdict": "PROVISIONAL",
            }
        },
    }


def _market_thesis_regime_source() -> dict[str, object]:
    window = {
        "resolved": 10,
        "mean": 0.02,
        "median": 0.01,
        "up_rate": 0.6,
        "ci90": [0.01, 0.03],
        "p10": -0.05,
        "worst": -0.2,
        "mean_mdd": -0.03,
        "worst_mdd": -0.25,
    }
    regime = {
        "days": 10,
        "fwd_20d": deepcopy(window),
        "fwd_40d": deepcopy(window),
        "fwd_60d": deepcopy(window),
    }
    return {
        "generated_at": "2026-08-04T02:03:04+00:00",
        "benchmark": "^GSPC",
        "vix": "^VIX",
        "lookback_period": "20y",
        "rules": {"private": True},
        "forward_windows_sessions": [20, 40, 60],
        "note": "private regime note",
        "regime_summary": {
            "rally": deepcopy(regime),
            "correction": deepcopy(regime),
            "range": deepcopy(regime),
        },
        "correction_episodes": [],
        "regime_runs": [],
        "daily": [],
    }


def _reversal_radar_source() -> dict[str, object]:
    return {
        "as_of_date": "2026-07-15",
        "generated_at": "2026-07-15T12:00:00+00:00",
        "lane_id": "reversal_radar.v1.structure+momentum",
        "universe": "beaten_down_prescreen",
        "universe_size": 1500,
        "scanned": 1,
        "match_count": 1,
        "improving_sectors": [],
        "prescreen": {},
        "candidates": [{"ticker": "NVDA", "reversal_score": 70}],
        "exploratory": True,
        "runway_independent": False,
        "exploratory_gate": {},
        "cot_confirmation": {},
        "disclaimer": "not investment advice",
        "note": "private source detail",
    }


def _reversal_validation_source() -> dict[str, object]:
    def tier() -> dict[str, object]:
        return {
            "resolved": 0,
            "hits": 0,
            "hit_rate": None,
            "wilson90": [0.0, 1.0],
            "ev_horizon": None,
            "median_horizon": None,
            "win_rate_horizon": None,
            "ev_horizon_ci90": [None, None],
            "ev_excess_vs_spy": None,
            "excess_n": 0,
            "excess_win_rate": None,
            "ev_excess_ci90": [None, None],
            "equity_multiple": None,
            "equity_curve": [],
        }

    tiers = ("+10%/20d", "+15%/40d", "+20%/60d")
    return {
        "generated_at": "2026-07-15T12:00:00+00:00",
        "module": "reversal_radar",
        "lane_id": (
            "reversal_radar.v1.structure+momentum_div+options_fear_receding+"
            "sector_improving+insider+analyst"
        ),
        "entries_accumulated": 0,
        "price_resolvable": 0,
        "dropped_count": 0,
        "dropped_pct": None,
        "min_resolved_across_tiers": 0,
        "min_resolved_for_verdict": 100,
        "verdict": "PROVISIONAL — sample below threshold, indicative only",
        "verdict_by_tier": {name: "PROVISIONAL" for name in tiers},
        "survivorship": {
            "survivorship_free": False,
            "forward_universe": "current membership fixture",
            "caveats": [],
        },
        "ev_caveats": [],
        "note": "fixture",
        "by_tier": {name: tier() for name in tiers},
    }


def _oversold_reversal_source() -> dict[str, object]:
    return {
        "module": "oversold_reversal",
        "lane_id": "coiled_base.v1.bb_squeeze+rsi_40_65",
        "definition": "coiled base",
        "primary_signal": "bb_squeeze+rsi_40_65",
        "runway_independent": False,
        "runway_note": "private source detail",
        "exploratory": True,
        "as_of_date": "2026-07-15",
        "generated_at": "2026-07-15T12:00:00+00:00",
        "universe": "sp1500",
        "liquidity_filter": {},
        "attempted": 1,
        "scanned": 1,
        "fetch_failed": 0,
        "short_history": 0,
        "stale_history": 0,
        "match_count": 1,
        "validation": {
            "pct_lift": 3.19,
            "atr_neutral_lift": 3.19,
            "support": 35,
            "source": "lane_runway.json",
        },
        "validation_caveats": [],
        "candidates": [
            {
                "ticker": "NVDA",
                "as_of": "2026-07-15",
                "signal_date": "2026-07-15",
                "last_price": 100.0,
                "rsi14": 50.0,
                "bb_width_pct": 1.2,
                "ma200": 90.0,
                "pct_vs_ma200": 11.1,
                "pct_from_52w_high": -10.0,
                "avg_dollar_vol_m": 2500.0,
            }
        ],
        "note": "EXPLORATORY",
    }


def _oversold_validation_source() -> dict[str, object]:
    def tier() -> dict[str, object]:
        return {
            "resolved": 0,
            "hits": 0,
            "hit_rate": None,
            "wilson90": [0.0, 1.0],
            "mature": False,
            "excess_mature": False,
            "excess_beta_adj_mature": False,
            "ev_horizon": None,
            "median_horizon": None,
            "win_rate_horizon": None,
            "ev_horizon_ci90": None,
            "ev_horizon_net": None,
            "win_rate_net": None,
            "ev_horizon_net_ci90": None,
            "ev_excess_vs_spy": None,
            "excess_n": 0,
            "excess_win_rate": None,
            "ev_excess_ci90": None,
            "ev_excess_beta_adj": None,
            "excess_beta_adj_n": 0,
            "excess_beta_adj_win_rate": None,
            "ev_excess_beta_adj_ci90": None,
            "equity_multiple": None,
            "equity_multiple_net": None,
            "equity_curve": [],
        }

    tiers = ("+30%/20d", "+40%/40d", "+50%/60d")
    return {
        "generated_at": "2026-07-15T12:00:00+00:00",
        "module": "coiled_base",
        "lane_id": "coiled_base.v1.bb_squeeze+rsi_40_65+above_30pct_of_low",
        "entries_accumulated": 0,
        "price_resolvable": 0,
        "dropped_count": 0,
        "dropped_pct": None,
        "min_resolved_across_tiers": 0,
        "min_resolved_for_verdict": 100,
        "verdict": "PROVISIONAL — sample below threshold, indicative only",
        "verdict_by_tier": {name: "PROVISIONAL" for name in tiers},
        "survivorship": {
            "survivorship_free": False,
            "forward_universe": "current index membership",
            "validated_universe": "sp500_pit",
            "universe_match": False,
            "caveats": [],
        },
        "sp500_pit_cohort": {
            "validated_universe": "sp500_pit",
            "universe_match": True,
            "membership": {"member": 0, "non_member": 0, "unknown": 0},
            "membership_snapshot_through": "2026-01-14",
            "gate": "point-in-time membership only",
            "by_tier": {name: tier() for name in tiers},
        },
        "cost_assumption_round_trip": 0.005,
        "ev_caveats": [],
        "note": "private producer note",
        "by_tier": {name: tier() for name in tiers},
    }


def _schema_validator(
    document: dict[str, object],
    response_schema: dict[str, object],
) -> Draft202012Validator:
    validation_root = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": deepcopy(document["components"]),
        "allOf": [deepcopy(response_schema)],
    }
    Draft202012Validator.check_schema(validation_root)
    return Draft202012Validator(
        validation_root,
        format_checker=FormatChecker(),
    )


def _example_values(content: dict[str, object]) -> list[object]:
    examples = content.get("examples", {})
    if not isinstance(examples, dict):
        return []
    return [
        example.get("value") if isinstance(example, dict) else example
        for example in examples.values()
    ]


def _ranked_spec(path: Path) -> ArtifactSpec:
    return ArtifactSpec(
        source_id="test.ranked",
        resolver=lambda: ResolvedArtifactPath(path),
        data_model=RankedCandidatesData,
        object_list_fields=("ranked_candidates",),
    )


def _market_spec(path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[MARKET_THESIS_SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _ranked_candidates_feed_source() -> dict[str, object]:
    row = {
        "ticker": "AAPL",
        "rank_score": 80.0,
        "last_price": 200.0,
        "rank_bucket": "priority",
        "ret_5d": 3.0,
        "ret_20d": 8.0,
        "score_components": {
            "technical_trend": 20.0,
            "momentum_strength": 15.0,
            "launch_signal": 10.0,
            "liquidity_tradability": 17.0,
            "overheat_risk_control": 15.0,
            "large_order_flow_confirmation": 0.0,
        },
        "options_tradability": None,
        "warnings": [],
        "private_source_field": True,
    }
    return {
        "all_ranked_count": 1,
        "as_of_date": "2026-07-14",
        "generated_at": "2026-07-14T12:00:00Z",
        "markets": ["US"],
        "money_flow_scoring": {},
        "options_gate": {},
        "passed_hard_filters": 1,
        "rank_buckets": {"priority": 1},
        "rank_limit": 50,
        "ranked_candidates": [row],
        "ranked_candidates_count": 1,
        "scan_date": "2026-07-14",
        "score_weights": {},
        "scoring_model": "deterministic",
        "source": "fixture",
        "tickers": [row],
        "total_candidates": 1,
        "total_universe": 1,
        "universe": "US",
    }


def _scored_candidates_feed_source() -> dict[str, object]:
    row = {
        "ticker": "AAPL",
        "verdict": "WATCHLIST",
        "composite_score": 70.0,
        "regime_adjusted_score": 70.0,
        "scores": {
            "technical": 25.0,
            "catalyst": 7.0,
            "sentiment": 4.0,
            "institutional": 3.0,
            "sector_market": 5.0,
            "options_flow": 8.0,
        },
        "data_missing": ["analyst"],
        "due_diligence_required": True,
        "key_signals": ["fixture signal"],
        "key_risks": ["fixture risk"],
        "suggested_entry_zone": "$195-$200",
        "suggested_stop": "$190",
    }
    return {
        "all_scored": [row],
        "min_score_threshold": 65,
        "needs_layer2": [],
        "needs_layer2_count": 0,
        "passed_hard_filters": 1,
        "regime_context": {},
        "rejected_count": 0,
        "remaining_unscored": 0,
        "scan_date": "2026-07-14",
        "scored_candidates_count": 1,
        "total_candidates": 1,
        "universe_size": 1,
        "watchlist": [row],
        "watchlist_count": 1,
    }


def _social_intelligence_source() -> dict[str, object]:
    statuses = {
        key: {
            "label": key,
            "cost_mode": "free",
            "status": "available",
            "note": "fixture",
        }
        for key in (
            "codex_web_research",
            "x_official_api",
            "agent_reach",
            "stocktwits",
            "apewisdom",
        )
    }
    return {
        "as_of_date": "2026-07-14",
        "generated_at": "2026-07-14T12:00:00Z",
        "source": "social_intelligence",
        "schema_version": 1,
        "market": "US",
        "source_statuses": statuses,
        "tickers": [],
        "limitations": [],
    }


def _theme_flow_source() -> dict[str, object]:
    theme = {
        "theme": "AI",
        "desc": "fixture",
        "parent_sector_etfs": ["XLK"],
        "flow_5d": 1.0,
        "flow_20d": 2.0,
        "accel": 0.5,
        "flow_5d_norm": 1.0,
        "flow_20d_norm": 2.0,
        "accel_norm": 0.5,
        "rvol": 1.0,
        "ret_5d": 1.0,
        "excess_5d": 0.5,
        "top_share": 0.5,
        "high_concentration": False,
        "breadth_inflow_ratio": 1.0,
        "positive_flow_count": 1,
        "negative_flow_count": 0,
        "n_used": 1,
        "n_total": 1,
        "n_failed": 0,
        "reps": [
            {"ticker": "NVDA", "flow_20d": 2.0, "flow_5d": 1.0, "ret_5d": 1.0}
        ],
        "raw_heat_score": 80.0,
        "signal_quality": 1.0,
        "heat_score": 80.0,
        "capital_state": "加速流入(推估)",
        "bottom_fishing": False,
        "eastmoney_main_net_5d": None,
        "eastmoney_main_net_20d": None,
        "eastmoney_main_pct_latest": None,
        "money_flow_source": "proxy",
        "money_flow_caveat": "private",
    }
    return {
        "as_of": "2026-07-14",
        "generated_at": "2026-07-14T12:00:00Z",
        "benchmark": "SPY",
        "schema_version": 5,
        "n_failed_download": 0,
        "params": {},
        "themes": [theme],
        "buckets": {
            "加速流入(推估)": ["AI"],
            "流入趨緩": [],
            "中性": [],
            "流出(推估)": [],
        },
        "bottom_fishing": [],
        "shared_mega_caps": [],
    }


def _theme_flow_analysis_source() -> dict[str, object]:
    return {
        "status": "ready",
        "generated_at": "2026-07-14T12:00:00Z",
        "as_of": "2026-07-14",
        "board_fingerprint": "0123456789abcdef",
        "validation_version": 8,
        "read": {
            "headline": "fixture",
            "confidence": "medium",
            "accelerating_in": [],
            "rotating_out": [],
            "bottom_fishing": [],
            "insider_divergence": [],
            "next_thesis": "fixture",
            "caveats": [],
        },
        "bottom_fishing": [],
        "buckets": {},
        "macro": {},
    }


def _money_flow_source() -> dict[str, object]:
    return {
        "as_of_date": "2026-07-14",
        "generated_at": "2026-07-14T12:00:00Z",
        "source": "eastmoney_push2his",
        "publishable": True,
        "coverage": {
            "requested": 1,
            "resolved": 1,
            "unavailable": 0,
            "coverage_ratio": 1.0,
            "min_coverage": 0.7,
        },
        "rows": [
            {
                "ticker": "NVDA",
                "secid": "105.NVDA",
                "date": "2026-07-14",
                "close": 125.0,
                "change_pct": 2.0,
                "main_net": 1_000_000.0,
                "main_pct": 3.2,
                "super_big_net": 600_000.0,
                "big_net": 400_000.0,
                "mid_net": -200_000.0,
                "small_net": -800_000.0,
                "source": "eastmoney_push2his",
                "raw_row": {"private": True},
            }
        ],
    }


def _sector_rotation_source() -> dict[str, object]:
    def row(
        etf: str,
        name: str,
        quadrant: str,
        quadrant_zh: str,
        heat: float,
    ) -> dict[str, object]:
        return {
            "etf": etf,
            "name_zh": name,
            "group": "主板塊",
            "theme": None,
            "rs_ratio": 101.0,
            "rs_momentum": 101.0,
            "quadrant": quadrant,
            "quadrant_zh": quadrant_zh,
            "ret_5d": 2.0,
            "ret_20d": 5.0,
            "ret_60d": 8.0,
            "excess_20d": 3.0,
            "pct_vs_ma50": 4.0,
            "pct_vs_ma200": 6.0,
            "rvol": 1.2,
            "pct_from_52w_high": -2.0,
            "heat_score": heat,
        }

    return {
        "status": "verified_only",
        "generated_at": "2026-07-15T12:00:00Z",
        "as_of": "2026-07-14",
        "benchmark": "SPY",
        "leaders": ["XLK"],
        "improving": ["XLF"],
        "macro": {},
        "sectors": [
            row("XLK", "科技", "Leading", "領漲", 90.0),
            row("XLF", "金融", "Improving", "醞釀", 80.0),
        ],
    }


def _daily_summary_source() -> dict[str, object]:
    return {
        "report_date": "2026-07-14",
        "regime_summary": "Constructive but selective risk-on regime.",
        "total_confirmed": 1,
        "ranked_picks": [
            {
                "rank": 1,
                "ticker": "NVDA",
                "final_score": 87,
                "verdict": "STRONG_BUY",
                "thesis": "AI demand remains resilient.",
                "entry_zone": "165-170",
                "stop_loss": "158",
                "position_size_pct": 2.5,
                "key_risk": "Crowded positioning.",
            }
        ],
        "cross_candidate_commentary": "Avoid excess concentration.",
        "portfolio_notes": "Scale only after confirmation.",
    }


def _playbook_validation_source() -> dict[str, object]:
    return {
        "generated_at": "2026-07-15T12:00:00Z",
        "status": "accumulating",
        "resolved": 1,
        "min_resolved": 100,
        "decision_count": 1,
        "outcome_count": 1,
        "playbooks": [
            {
                "playbook": "Momentum",
                "resolved": 1,
                "mean_fwd_7d_return": 0.03,
                "hit_rate_7d": 1.0,
                "verdict": "exploratory",
            }
        ],
        "factors": [
            {
                "factor_id": "technical_breakout",
                "resolved": 1,
                "mean_fwd_7d_return": 0.03,
                "hit_rate_7d": 1.0,
                "verdict": "exploratory",
            }
        ],
    }


def _continuation_validation_source() -> dict[str, object]:
    return {
        "generated_at": "2026-07-15T12:00:00Z",
        "status": "blocked",
        "reason": "fixture source is intentionally blocked",
        "resolved": 0,
        "min_resolved": 30,
        "summary": {},
        "rows": [],
    }


def _http_registry(root: Path) -> dict[str, ArtifactSpec]:
    payloads = {
        "candidates.ranked": {
            "ranked_candidates": [
                {"ticker": "AAPL", "nested_sentinel": {"keep": [1, "two"]}}
            ],
            "top_level_sentinel": {"preserve": True},
            "scan_date": "2026-07-14",
            "generated_at": "2026-07-14T12:00:00Z",
        },
        "candidates.scored": {"all_scored": []},
        "candidates.ranked.feed": _ranked_candidates_feed_source(),
        "candidates.scored.feed": _scored_candidates_feed_source(),
        "candidates.scored.screener": _scored_candidates_feed_source(),
        "crypto.universe": _crypto_universe_source(),
        "signals.options-flow.latest": {"signals": []},
        "signals.options-flow.feed": _options_flow_source(),
        "signals.reversal-radar.latest": _reversal_radar_source(),
        "signals.reversal-radar.validation": _reversal_validation_source(),
        "signals.oversold-reversal.latest": _oversold_reversal_source(),
        "signals.oversold-reversal.validation": _oversold_validation_source(),
        "market-context.market-thesis.latest": _market_thesis_source(),
        "market-context.market-thesis.validation": _market_thesis_validation_source(),
        "market-context.market-thesis.regime-history": _market_thesis_regime_source(),
        "reports.daily-summary.latest": _daily_summary_source(),
        "reports.playbook-validation.latest": _playbook_validation_source(),
        "reports.continuation-validation.latest": _continuation_validation_source(),
        "market-context.money-flow.latest": _money_flow_source(),
        "market-context.sector-rotation.latest": _sector_rotation_source(),
        "market-context.theme-flow.latest": _theme_flow_source(),
        "market-context.theme-flow.analysis": _theme_flow_analysis_source(),
        "social.intelligence.latest": _social_intelligence_source(),
        "institutions.funds": {
            "_note": "fixture maintainer guidance",
            "funds": {
                "Berkshire Hathaway (Buffett)": {
                    "cik": "1067983",
                    "note": "波克夏",
                }
            },
        },
        "system.ai-updates": {
            "_note": "fixture maintainer guidance",
            "updates": [
                _ai_update(
                    date="2026-07-13",
                    title="Older update",
                    link="",
                    tags=[],
                ),
                _ai_update(
                    date="2026-07-15",
                    title="Latest update",
                    link="https://example.com/path?q=value#fragment",
                    tags=["AI", "Radar"],
                ),
            ],
        },
        "system.schedules": _schedules_source(
            [
                _schedule(
                    id="older_job",
                    name="Older job",
                    result_type="report_dir",
                ),
                _schedule(
                    id="newer_job",
                    name="Newer job",
                    category="Operations",
                    cron="30 7 * * 1-5",
                    cron_note="Weekdays 07:30 Asia/Taipei",
                    description="Second source-ordered fixture.",
                    result_type="future_public_result",
                ),
            ]
        ),
    }
    registry: dict[str, ArtifactSpec] = {}
    for index, (source_id, payload) in enumerate(payloads.items()):
        path = _write(root / f"artifact-{index}.json", payload)
        as_of = (
            "2026-07-14"
            if source_id
            in {
                "market-context.market-thesis.latest",
                "reports.daily-summary.latest",
            }
            else None
        )
        registry[source_id] = replace(
            ARTIFACTS[source_id],
            resolver=lambda path=path, as_of=as_of: ResolvedArtifactPath(path, as_of),
        )
    return registry


def _client(
    registry: dict[str, ArtifactSpec],
    *,
    iv_history_directory: Path | None = None,
    client_address: tuple[str, int] = ("127.0.0.1", 50000),
    base_url: str = "http://127.0.0.1",
    raise_server_exceptions: bool = True,
) -> TestClient:
    app_kwargs = {}
    if iv_history_directory is not None:
        app_kwargs["iv_history_directory"] = iv_history_directory
    target = create_app(registry, **app_kwargs)

    async def with_client_address(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": client_address}
        await target(scope, receive, send)

    return TestClient(
        with_client_address,
        base_url=base_url,
        raise_server_exceptions=raise_server_exceptions,
    )


def test_registry_is_explicit_and_typed() -> None:
    if set(ARTIFACTS) != set(EXPECTED_REGISTRY):
        raise AssertionError(set(ARTIFACTS))
    for source_id, object_lists in EXPECTED_REGISTRY.items():
        spec = ARTIFACTS[source_id]
        if spec.source_id != source_id:
            raise AssertionError(spec)
        if spec.object_list_fields != object_lists:
            raise AssertionError((source_id, spec.object_list_fields))

    market = ARTIFACTS["market-context.market-thesis.latest"]
    if market.source_id != MARKET_THESIS_SOURCE_ID:
        raise AssertionError(market)

    for source_id, data_model in (
        (REVERSAL_RADAR_SOURCE_ID, model_module.ReversalRadarData),
        (OVERSOLD_REVERSAL_SOURCE_ID, model_module.OversoldReversalData),
        (SOCIAL_INTELLIGENCE_SOURCE_ID, SocialIntelligenceData),
        (THEME_FLOW_SOURCE_ID, ThemeFlowData),
        (THEME_FLOW_ANALYSIS_SOURCE_ID, ThemeFlowAnalysisData),
        (MONEY_FLOW_SOURCE_ID, MoneyFlowData),
        (SECTOR_ROTATION_SOURCE_ID, SectorRotationData),
        (DAILY_SUMMARY_SOURCE_ID, DailySummaryData),
    ):
        signal = ARTIFACTS[source_id]
        if (
            signal.data_model is not data_model
            or signal.data_validator is None
            or signal.data_projector is None
            or signal.as_of_extractor is None
            or signal.object_list_fields
        ):
            raise AssertionError(signal)
    if (
        market.data_model is not MarketThesisData
        or market.data_validator is None
        or market.data_projector is None
        or market.as_of_extractor is None
        or market.object_list_fields
        or market.string_fields
        or market.date_fields
    ):
        raise AssertionError(market)
    for source_id, data_model in (
        (MARKET_THESIS_VALIDATION_SOURCE_ID, MarketThesisValidationData),
        (MARKET_THESIS_REGIME_HISTORY_SOURCE_ID, MarketThesisRegimeHistoryData),
    ):
        summary = ARTIFACTS[source_id]
        if (
            summary.data_model is not data_model
            or summary.data_validator is None
            or summary.data_projector is None
            or summary.as_of_extractor is not None
            or summary.object_list_fields
            or summary.string_fields
            or summary.date_fields
        ):
            raise AssertionError(summary)
    oversold_validation = ARTIFACTS[OVERSOLD_REVERSAL_VALIDATION_SOURCE_ID]
    if (
        oversold_validation.data_model is not OversoldReversalValidationData
        or oversold_validation.data_validator is None
        or oversold_validation.data_projector is None
        or oversold_validation.as_of_extractor is not None
        or oversold_validation.generated_at_extractor is None
        or oversold_validation.object_list_fields
    ):
        raise AssertionError(oversold_validation)

    playbook_validation = ARTIFACTS[PLAYBOOK_VALIDATION_SOURCE_ID]
    if (
        playbook_validation.data_model is not PlaybookValidationData
        or playbook_validation.data_validator is None
        or playbook_validation.data_projector is None
        or playbook_validation.as_of_extractor is not None
        or playbook_validation.generated_at_extractor is None
        or playbook_validation.object_list_fields
    ):
        raise AssertionError(playbook_validation)

    continuation_validation = ARTIFACTS[CONTINUATION_VALIDATION_SOURCE_ID]
    if (
        continuation_validation.data_model is not ContinuationValidationData
        or continuation_validation.data_validator is None
        or continuation_validation.data_projector is None
        or continuation_validation.as_of_extractor is not None
        or continuation_validation.generated_at_extractor is None
        or continuation_validation.object_list_fields
    ):
        raise AssertionError(continuation_validation)

    funds = ARTIFACTS["institutions.funds"]
    if funds.source_id != FUND_CATALOG_SOURCE_ID:
        raise AssertionError(funds)
    if funds.data_model is not FundCatalogData or funds.data_projector is None:
        raise AssertionError(funds)

    crypto = ARTIFACTS[CRYPTO_UNIVERSE_SOURCE_ID]
    if crypto.data_model is not CryptoUniverseData:
        raise AssertionError(crypto.data_model)
    if any(
        callback is None
        for callback in (
            crypto.data_validator,
            crypto.data_projector,
            crypto.as_of_extractor,
        )
    ):
        raise AssertionError(crypto)
    resolved = crypto.resolver()
    if not isinstance(resolved, ResolvedArtifactPath):
        raise AssertionError(resolved)
    if resolved.path != ROOT / "reports" / "crypto" / "universe_latest.json":
        raise AssertionError(resolved.path)

    ai_updates = ARTIFACTS["system.ai-updates"]
    if ai_updates.source_id != AI_UPDATES_SOURCE_ID:
        raise AssertionError(ai_updates)
    if ai_updates.data_model is not AiUpdatesData:
        raise AssertionError(ai_updates.data_model)
    if any(
        callback is None
        for callback in (
            ai_updates.data_validator,
            ai_updates.data_projector,
            ai_updates.as_of_extractor,
        )
    ):
        raise AssertionError(ai_updates)
    resolved = ai_updates.resolver()
    if not isinstance(resolved, ResolvedArtifactPath):
        raise AssertionError(resolved)
    if resolved.path != ROOT / "content" / "ai_updates.json":
        raise AssertionError(resolved.path)

    schedules = ARTIFACTS["system.schedules"]
    if schedules.source_id != SCHEDULES_SOURCE_ID:
        raise AssertionError(schedules)
    if schedules.data_model is not SchedulesData:
        raise AssertionError(schedules.data_model)
    if schedules.data_validator is None or schedules.data_projector is None:
        raise AssertionError(schedules)
    if schedules.as_of_extractor is not None:
        raise AssertionError(schedules.as_of_extractor)
    resolved = schedules.resolver()
    if not isinstance(resolved, ResolvedArtifactPath):
        raise AssertionError(resolved)
    if resolved.path != ROOT / "content" / "schedules.json":
        raise AssertionError(resolved.path)

    feed_source_id = getattr(artifact_module, "OPTIONS_FLOW_FEED_SOURCE_ID")
    feed_model = getattr(model_module, "OptionsFlowFeedData")
    feed = ARTIFACTS[OPTIONS_FLOW_FEED_SOURCE_ID]
    if feed.source_id != feed_source_id or feed_source_id != OPTIONS_FLOW_FEED_SOURCE_ID:
        raise AssertionError(feed)
    if feed.data_model is not feed_model:
        raise AssertionError(feed.data_model)
    if feed.data_validator is None or feed.data_projector is None:
        raise AssertionError(feed)
    if feed.as_of_extractor is not None or feed.object_list_fields:
        raise AssertionError(feed)
    resolved = feed.resolver()
    if not isinstance(resolved, ResolvedArtifactPath):
        raise AssertionError(resolved)
    if resolved.path != ROOT / "reports" / "options_flow" / "latest.json":
        raise AssertionError(resolved.path)

    screener = ARTIFACTS[SCORED_CANDIDATES_SCREENER_SOURCE_ID]
    if screener.data_model is not ScoredCandidatesScreenerData:
        raise AssertionError(screener.data_model)
    if screener.data_validator is None or screener.data_projector is None:
        raise AssertionError(screener)
    if screener.as_of_extractor is not None or screener.object_list_fields:
        raise AssertionError(screener)
    resolved = screener.resolver()
    if not isinstance(resolved, ResolvedArtifactPath):
        raise AssertionError(resolved)
    if resolved.path != artifact_module.candidate_output_path(
        "scored_candidates.json"
    ):
        raise AssertionError(resolved.path)


def test_available_envelope_preserves_source_fields() -> None:
    payload = {
        "ranked_candidates": [
            {"ticker": "AAPL", "nested_sentinel": {"keep": [1, "two"]}}
        ],
        "top_level_sentinel": {"preserve": True},
    }
    with tempfile.TemporaryDirectory() as tmp:
        result = read_artifact(_ranked_spec(_write(Path(tmp) / "ranked.json", payload)))

    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if result.data != payload:
        raise AssertionError(result.data)
    if result.model_dump(mode="json", by_alias=True)["data"] != payload:
        raise AssertionError(result.model_dump(mode="json", by_alias=True))

    parsed = RankedCandidatesData.model_validate(payload)
    if parsed.model_dump(mode="json") != payload:
        raise AssertionError(parsed.model_dump(mode="json"))


def test_scored_screener_projection_is_closed_bucket_only_and_ordered() -> None:
    source = _scored_candidates_feed_source()
    base = deepcopy(source["watchlist"][0])
    needs = {**base, "ticker": "NVDA", "verdict": "NEEDS_LAYER_2"}
    needs.update(
        {
            "regime_adjusted_score": 80.0,
            "suggested_size_pct": 5.0,
            "anti_example_warning": "fixture anti",
            "technical_breakdown": {
                "pattern_type": "breakout",
                "macd_state": "bullish",
                "private_factor": 999,
            },
            "private_candidate_field": "hidden",
        }
    )
    watch = {**base, "ticker": "AMD", "regime_adjusted_score": 90.0}
    rejected = {
        **base,
        "ticker": "TSLA",
        "verdict": "REJECT",
        "regime_adjusted_score": 99.0,
    }
    source.update(
        {
            "generated_at": "2026-08-03T01:02:03Z",
            "needs_layer2": [needs],
            "needs_layer2_count": 1,
            "watchlist": [watch, needs],
            "watchlist_count": 2,
            "all_scored": [rejected, watch, needs],
            "regime_context": {
                "spy_vs_50dma": "above",
                "spy_vs_200dma": "below",
                "vix_level": 18.5,
                "vix_regime": "normal",
                "global_score_multiplier": 0.9,
                "active_themes": ["AI"],
                "regime_warnings": ["fixture warning"],
                "private_regime_field": "hidden",
            },
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "scored.json", source)
        spec = replace(
            ARTIFACTS[SCORED_CANDIDATES_SCREENER_SOURCE_ID],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        result = read_artifact(spec)

    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if result.meta.as_of is None or result.meta.as_of.isoformat() != source["scan_date"]:
        raise AssertionError(result.meta)
    if result.meta.generated_at is not None:
        raise AssertionError(result.meta)
    data = result.data
    if set(data) != {
        "scan_date",
        "needs_layer2_count",
        "watchlist_count",
        "regime_context",
        "candidates",
    }:
        raise AssertionError(data)
    if [row["ticker"] for row in data["candidates"]] != ["AMD", "NVDA"]:
        raise AssertionError(data["candidates"])
    if "TSLA" in json.dumps(data) or "private" in json.dumps(data):
        raise AssertionError(data)
    candidate_fields = {
        "ticker",
        "verdict",
        "regime_adjusted_score",
        "scores",
        "key_signals",
        "key_risks",
        "suggested_entry_zone",
        "suggested_stop",
        "suggested_size_pct",
        "anti_example_warning",
        "data_missing",
        "technical_breakdown",
    }
    if any(set(row) != candidate_fields for row in data["candidates"]):
        raise AssertionError(data["candidates"])
    parsed = ScoredCandidatesScreenerData.model_validate(data, strict=True)
    if parsed.model_dump(mode="json") != data:
        raise AssertionError(parsed)


def test_scored_screener_invalid_sources_fail_soft_and_recover() -> None:
    valid = _scored_candidates_feed_source()
    invalid_sources = []
    extra_root = deepcopy(valid)
    extra_root["private"] = True
    invalid_sources.append(extra_root)
    invalid_timestamp = deepcopy(valid)
    invalid_timestamp["generated_at"] = "2026-08-03T01:02:03"
    invalid_sources.append(invalid_timestamp)
    invalid_count = deepcopy(valid)
    invalid_count["watchlist_count"] = True
    invalid_sources.append(invalid_count)
    mismatched_count = deepcopy(valid)
    mismatched_count["watchlist_count"] = 0
    invalid_sources.append(mismatched_count)
    invalid_technical = deepcopy(valid)
    invalid_technical["watchlist"][0]["technical_breakdown"] = "private"
    invalid_sources.append(invalid_technical)
    invalid_size = deepcopy(valid)
    invalid_size["watchlist"][0]["suggested_size_pct"] = 101.0
    invalid_sources.append(invalid_size)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec_base = ARTIFACTS[SCORED_CANDIDATES_SCREENER_SOURCE_ID]
        for index, payload in enumerate(invalid_sources):
            path = _write(root / f"invalid-{index}.json", payload)
            result = read_artifact(
                replace(spec_base, resolver=lambda path=path: ResolvedArtifactPath(path))
            )
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((index, result))

        recovered_path = _write(root / "recovered.json", valid)
        recovered = read_artifact(
            replace(
                spec_base,
                resolver=lambda: ResolvedArtifactPath(recovered_path),
            )
        )
    if not isinstance(recovered, ArtifactAvailable):
        raise AssertionError(recovered)


def test_scored_screener_http_route_is_additive_and_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with _client(_http_registry(Path(tmp))) as client:
            response = client.get("/api/v1/candidates/scored/screener")
            compatibility = client.get("/api/v1/candidates/scored/feed")
            schema = client.get("/openapi.json").json()
    if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
        raise AssertionError((response.status_code, response.text, response.headers))
    body = response.json()
    if body["meta"] != {
        "sourceId": "candidates.scored.screener",
        "asOf": "2026-07-14",
        "generatedAt": None,
    }:
        raise AssertionError(body)
    if compatibility.json()["meta"]["sourceId"] != "candidates.scored.feed":
        raise AssertionError(compatibility.json())
    operation = schema["paths"]["/api/v1/candidates/scored/screener"]["get"]
    if operation.get("operationId") != "getScoredCandidatesScreener":
        raise AssertionError(operation)
    if operation.get("parameters") not in (None, []):
        raise AssertionError(operation)


def test_expected_file_states_return_unavailable_envelopes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        missing = read_artifact(_ranked_spec(root / "missing.json"))
        malformed_path = root / "malformed.json"
        malformed_path.write_text('{"ranked_candidates":', encoding="utf-8")
        malformed = read_artifact(_ranked_spec(malformed_path))

    if not isinstance(missing, ArtifactUnavailable) or missing.reason != "missing":
        raise AssertionError(missing)
    if not isinstance(malformed, ArtifactUnavailable) or malformed.reason != "invalid_json":
        raise AssertionError(malformed)
    for result in (missing, malformed):
        dumped = result.model_dump(mode="json", by_alias=True)
        if dumped["available"] is not False or dumped["data"] is not None:
            raise AssertionError(dumped)


def test_wrong_anchor_shapes_are_invalid_shape() -> None:
    fixtures = [
        {},
        {"ranked_candidates": "broken"},
        {"ranked_candidates": [1]},
        {"ranked_candidates": [{"ticker": "AAPL"}, "broken"]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for index, payload in enumerate(fixtures):
            result = read_artifact(
                _ranked_spec(_write(Path(tmp) / f"shape-{index}.json", payload))
            )
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((payload, result))


def test_market_thesis_requires_strict_projected_fields() -> None:
    valid = _market_thesis_source()
    fixtures = [
        {},
        {**valid, "direction": "neutral"},
        {**valid, "manifest_status": None},
        {**valid, "as_of": "2026-02-30"},
        {**valid, "as_of": "14-07-2026"},
        {**valid, "private": "must not reflect"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for index, payload in enumerate(fixtures):
            result = read_artifact(
                _market_spec(_write(Path(tmp) / f"market-{index}.json", payload))
            )
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((payload, result))


def test_market_thesis_resolver_orders_date_then_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory / "forecast_2026-07-13.json", {"as_of": "2026-07-13"})
        _write(directory / "regime_only_forecast_2026-07-14.json", {"as_of": "2026-07-14"})
        ready = _write(directory / "forecast_2026-07-14.json", {"as_of": "2026-07-14"})
        resolved = resolve_latest_market_thesis(directory)

    if not isinstance(resolved, ResolvedArtifactPath) or resolved.path != ready:
        raise AssertionError(resolved)
    if resolved.as_of != "2026-07-14":
        raise AssertionError(resolved)

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory / "forecast_2026-07-13.json", {"as_of": "2026-07-13"})
        newest = _write(
            directory / "regime_only_forecast_2026-07-14.json",
            {"as_of": "2026-07-14"},
        )
        date_first = resolve_latest_market_thesis(directory)
    if not isinstance(date_first, ResolvedArtifactPath) or date_first.path != newest:
        raise AssertionError(date_first)


def test_market_thesis_resolver_is_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty = resolve_latest_market_thesis(Path(tmp))
    if not isinstance(empty, ArtifactPathUnavailable) or empty.reason != "missing":
        raise AssertionError(empty)

    with patch("api.artifacts.Path.glob", side_effect=OSError("private path")):
        unreadable = resolve_latest_market_thesis(Path("ignored"))
    if not isinstance(unreadable, ArtifactPathUnavailable) or unreadable.reason != "unreadable":
        raise AssertionError(unreadable)


def test_selected_market_thesis_can_disappear_before_read() -> None:
    payload = _market_thesis_source()
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "forecast_2026-07-14.json", payload)
        resolved = ResolvedArtifactPath(path, as_of="2026-07-14")
        path.unlink()
        spec = replace(
            ARTIFACTS[MARKET_THESIS_SOURCE_ID],
            resolver=lambda: resolved,
        )
        result = read_artifact(spec)

    if not isinstance(result, ArtifactUnavailable) or result.reason != "missing":
        raise AssertionError(result)


def test_iv_ticker_normalization_and_spec_path_are_strict() -> None:
    accepted = {
        "nvda": "NVDA",
        "BRK.B": "BRK.B",
        "bf-b": "BF-B",
        "A1": "A1",
        "ABCDEFGHIJKLMNO": "ABCDEFGHIJKLMNO",
    }
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for raw, expected in accepted.items():
            if normalize_ticker(raw) != expected:
                raise AssertionError((raw, normalize_ticker(raw)))
            spec = iv_history_spec(raw, directory)
            resolved = spec.resolver()
            if not isinstance(resolved, ResolvedArtifactPath):
                raise AssertionError((raw, resolved))
            if resolved.path != directory / f"{expected}.json":
                raise AssertionError((raw, resolved.path))
            if IV_HISTORY_SOURCE_ID != "options.iv-history":
                raise AssertionError(IV_HISTORY_SOURCE_ID)
            if spec.source_id != "options.iv-history":
                raise AssertionError(spec)
            if spec.data_model is not IvHistoryData:
                raise AssertionError(spec.data_model)

    invalid = [
        "",
        ".AAPL",
        "AAPL.",
        "AA..BB",
        "AA.-BB",
        "A_B",
        "A B",
        "../AAPL",
        r"..\AAPL",
        "ß",
        "台積電",
        "ＡＡＰＬ",
        "ABCDEFGHIJKLMNOP",
    ]
    for raw in invalid:
        if normalize_ticker(raw) is not None:
            raise AssertionError((raw, normalize_ticker(raw)))
        try:
            iv_history_spec(raw, Path("ignored"))
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid ticker constructed a spec: {raw!r}")


def test_iv_history_shape_metadata_and_public_dto_are_strict() -> None:
    valid = {
        "ticker": "NVDA",
        "series": {
            "2026-07-12": 0.41,
            "2026-07-14": 1,
            "2026-07-13": 0.47,
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = _write(root / "NVDA.json", valid)
        spec = iv_history_spec("nvda", root)
        result = read_artifact(spec)
        if not isinstance(result, ArtifactAvailable):
            raise AssertionError(result)
        if result.data != valid:
            raise AssertionError(result.data)
        if result.meta.as_of is None or result.meta.as_of.isoformat() != "2026-07-14":
            raise AssertionError(result.meta)
        if result.meta.generated_at is not None:
            raise AssertionError(result.meta)

        _write(path, {"ticker": "NVDA", "series": {}})
        empty = read_artifact(spec)
        if not isinstance(empty, ArtifactAvailable) or empty.meta.as_of is not None:
            raise AssertionError(empty)

        invalid_payloads = [
            {},
            {"ticker": "NVDA"},
            {"series": {}},
            {"ticker": "nvda", "series": {}},
            {"ticker": "AMD", "series": {}},
            {"ticker": "NVDA", "series": []},
            {"ticker": "NVDA", "series": {"2026-02-30": 0.4}},
            {"ticker": "NVDA", "series": {"14-07-2026": 0.4}},
            {"ticker": "NVDA", "series": {"2026-07-14": "0.4"}},
            {"ticker": "NVDA", "series": {"2026-07-14": True}},
            {"ticker": "NVDA", "series": {"2026-07-14": None}},
            {"ticker": "NVDA", "series": {"2026-07-14": 0}},
            {"ticker": "NVDA", "series": {"2026-07-14": -0.1}},
            {"ticker": "NVDA", "series": {"2026-07-14": 10}},
            {"ticker": "NVDA", "series": {"2026-07-14": 10**999}},
            {"ticker": "NVDA", "series": {}, "absolute_path": "/private/secret"},
            {"ticker": "NVDA", "series": {}, "token": "do-not-reflect"},
            {"ticker": "NVDA", "series": {}, "as_of": "2026-07-14"},
        ]
        for index, payload in enumerate(invalid_payloads):
            _write(path, payload)
            invalid = read_artifact(spec)
            if not isinstance(invalid, ArtifactUnavailable) or invalid.reason != "invalid_shape":
                raise AssertionError((index, payload, invalid))


def test_iv_history_http_fail_soft_matrix_keeps_health_independent() -> None:
    fixtures: list[tuple[str, bytes | None, str, bool]] = [
        ("missing", None, "missing", False),
        ("empty", b"", "invalid_json", False),
        ("truncated", b'{"ticker":"NVDA","series":', "invalid_json", False),
        ("invalid-utf8", b"\xff\xfe", "invalid_json", False),
        ("nan", b'{"ticker":"NVDA","series":{"2026-07-14":NaN}}', "invalid_json", False),
        ("list-root", b"[]", "invalid_shape", False),
        (
            "extra-field",
            b'{"ticker":"NVDA","series":{},"absolute_path":"/private/secret"}',
            "invalid_shape",
            False,
        ),
        ("directory", None, "unreadable", True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = _http_registry(root / "base")
        for name, raw, reason, make_directory in fixtures:
            directory = root / name
            directory.mkdir()
            path = directory / "NVDA.json"
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            with _client(registry, iv_history_directory=directory) as client:
                response = client.get("/api/v1/options/iv-history/NVDA")
                health = client.get("/healthz")
            if response.status_code != 200 or response.json()["reason"] != reason:
                raise AssertionError((name, response.status_code, response.text))
            expected_meta = {
                "sourceId": "options.iv-history",
                "asOf": None,
                "generatedAt": None,
            }
            if response.json().get("meta") != expected_meta:
                raise AssertionError((name, response.json()))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError((name, response.headers))
            if "private" in response.text or "secret" in response.text:
                raise AssertionError((name, response.text))
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((name, health.status_code, health.text))


def test_iv_history_http_validation_precedes_file_selection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(
            root / "NVDA.json",
            {"ticker": "NVDA", "series": {"2026-07-14": 0.49}},
        )
        registry = _http_registry(root / "base")
        real_factory = iv_history_spec
        selections: list[tuple[str, Path]] = []

        def selecting_factory(ticker: str, directory: Path) -> ArtifactSpec:
            selections.append((ticker, directory))
            return real_factory(ticker, directory)

        with patch("api.main.iv_history_spec", side_effect=selecting_factory):
            with _client(registry, iv_history_directory=root) as client:
                available = client.get(
                    "/api/v1/options/iv-history/nvda",
                    params={"path": "/etc/passwd", "ticker": "AMD"},
                )
                invalid_responses = [
                    client.get(f"/api/v1/options/iv-history/{ticker}")
                    for ticker in (
                        "A_B",
                        ".AAPL",
                        "AA..BB",
                        "A%20B",
                        "%C3%9F",
                        "ABCDEFGHIJKLMNOP",
                        "%252e%252e",
                    )
                ]
                slash_probe = client.get("/api/v1/options/iv-history/NVDA%2Fetc")
                traversal_probe = client.get("/api/v1/options/iv-history/%2E%2E")

    expected_available = {
        "available": True,
        "reason": "ok",
        "data": {"ticker": "NVDA", "series": {"2026-07-14": 0.49}},
        "meta": {
            "sourceId": "options.iv-history",
            "asOf": "2026-07-14",
            "generatedAt": None,
        },
    }
    if available.status_code != 200 or available.json() != expected_available:
        raise AssertionError((available.status_code, available.text))
    if available.headers.get("cache-control") != "no-store":
        raise AssertionError(available.headers)
    if selections != [("NVDA", root)]:
        raise AssertionError(selections)
    expected_problem = {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": 422,
    }
    for response in invalid_responses:
        if response.status_code != 422 or response.json() != expected_problem:
            raise AssertionError((response.status_code, response.text))
        if response.headers.get("content-type", "").split(";", 1)[0] != "application/problem+json":
            raise AssertionError(response.headers)
        if response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.headers)
    for response in (slash_probe, traversal_probe):
        if response.status_code not in {404, 422}:
            raise AssertionError((response.status_code, response.text))
        if any(secret in response.text.lower() for secret in ("private", "traceback", "environment")):
            raise AssertionError(response.text)


def test_iv_history_recovers_and_callback_defects_are_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "NVDA.json"
        path.write_text('{"ticker":"NVDA","series":', encoding="utf-8")
        registry = _http_registry(root / "base")
        with _client(registry, iv_history_directory=root) as client:
            first = client.get("/api/v1/options/iv-history/NVDA")
            _write(path, {"ticker": "NVDA", "series": {"2026-07-14": 0.49}})
            second = client.get("/api/v1/options/iv-history/NVDA")
        if first.json()["reason"] != "invalid_json" or second.json()["available"] is not True:
            raise AssertionError((first.text, second.text))

        base_spec = iv_history_spec("NVDA", root)

        def broken_validator(_data: dict[str, object]) -> bool:
            raise RuntimeError("secret validator detail")

        def broken_as_of(_data: dict[str, object]) -> str | None:
            raise RuntimeError("secret metadata detail")

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("secret resolver detail")

        defective_specs = [
            replace(base_spec, data_validator=broken_validator),
            replace(base_spec, as_of_extractor=broken_as_of),
            replace(base_spec, resolver=broken_resolver),
        ]
        for spec in defective_specs:
            with patch("api.main.iv_history_spec", return_value=spec), patch(
                "api.main.LOGGER.error"
            ) as error_log:
                with _client(
                    registry,
                    iv_history_directory=root,
                    raise_server_exceptions=False,
                ) as client:
                    response = client.get("/api/v1/options/iv-history/nvda")
            if response.status_code != 500 or response.json() != {
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
            }:
                raise AssertionError((response.status_code, response.text))
            if any(secret in response.text for secret in ("validator", "metadata", "resolver")):
                raise AssertionError(response.text)
            error_log.assert_called_once()
            logged_extra = error_log.call_args.kwargs.get("extra", {})
            if logged_extra != {
                "route": "/api/v1/options/iv-history/{ticker}",
                "error_type": "RuntimeError",
            }:
                raise AssertionError(logged_extra)
            if "nvda" in str(error_log.call_args).lower():
                raise AssertionError(error_log.call_args)


def test_fund_catalog_projection_and_boundary_shape_are_strict() -> None:
    source = json.loads((ROOT / "content" / "funds.json").read_text(encoding="utf-8"))
    real = read_artifact(ARTIFACTS["institutions.funds"])
    if len(source.get("funds", {})) != 10:
        raise AssertionError(source)
    if not isinstance(real, ArtifactAvailable):
        raise AssertionError(real)
    expected_real = {"funds": source["funds"]}
    if real.data != expected_real or "_note" in real.data:
        raise AssertionError(real.data)
    parsed = FundCatalogData.model_validate(real.data)
    if parsed.model_dump(mode="json") != expected_real:
        raise AssertionError(parsed.model_dump(mode="json"))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "funds.json"
        spec = replace(
            ARTIFACTS["institutions.funds"],
            resolver=lambda: ResolvedArtifactPath(path),
        )

        boundary_funds = {
            f"Fund {index:03d}": {"cik": str(index + 1), "note": ""}
            for index in range(98)
        }
        boundary_funds["台" * 120] = {"cik": "1", "note": "n" * 200}
        boundary_funds["Unicode 基金"] = {
            "cik": "1234567890",
            "note": "公開註記",
        }
        valid_boundary = {"_note": "m" * 2000, "funds": boundary_funds}
        _write(path, valid_boundary)
        valid = read_artifact(spec)
        if not isinstance(valid, ArtifactAvailable):
            raise AssertionError(valid)
        if valid.data != {"funds": boundary_funds}:
            raise AssertionError(valid.data)

        too_many = dict(boundary_funds)
        too_many["Overflow Fund"] = {"cik": "1", "note": ""}
        invalid_payloads = [
            {"funds": {}},
            {"_note": ""},
            {"_note": "", "funds": []},
            {"_note": 1, "funds": {}},
            {"_note": "m" * 2001, "funds": {}},
            {"_note": "", "funds": {}, "secret": "do-not-reflect"},
            {"_note": "", "funds": {"": {"cik": "1", "note": ""}}},
            {"_note": "", "funds": {"   ": {"cik": "1", "note": ""}}},
            {"_note": "", "funds": {" Leading": {"cik": "1", "note": ""}}},
            {"_note": "", "funds": {"Trailing ": {"cik": "1", "note": ""}}},
            {"_note": "", "funds": {"界" * 121: {"cik": "1", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "0", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "0000000000", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "12345678901", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": " 1", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "１２３", "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": 1, "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": True, "note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": None, "note": ""}}},
            {"_note": "", "funds": {"Fund": {"note": ""}}},
            {"_note": "", "funds": {"Fund": {"cik": "1"}}},
            {"_note": "", "funds": {"Fund": {"cik": "1", "note": 1}}},
            {"_note": "", "funds": {"Fund": {"cik": "1", "note": "n" * 201}}},
            {
                "_note": "",
                "funds": {"Fund": {"cik": "1", "note": "", "token": "secret"}},
            },
            {"_note": "", "funds": too_many},
        ]
        for index, payload in enumerate(invalid_payloads):
            _write(path, payload)
            invalid = read_artifact(spec)
            if not isinstance(invalid, ArtifactUnavailable) or invalid.reason != "invalid_shape":
                raise AssertionError((index, payload, invalid))


def test_fund_catalog_http_fail_soft_projection_and_recovery() -> None:
    fixtures: list[tuple[str, bytes | None, str, bool]] = [
        ("missing", None, "missing", False),
        ("empty", b"", "invalid_json", False),
        ("truncated", b'{"_note":"","funds":', "invalid_json", False),
        ("invalid-utf8", b"\xff\xfe", "invalid_json", False),
        ("nan", b'{"_note":"","funds":{},"value":NaN}', "invalid_json", False),
        ("list-root", b"[]", "invalid_shape", False),
        (
            "bad-cik",
            b'{"_note":"","funds":{"Fund":{"cik":1,"note":""}}}',
            "invalid_shape",
            False,
        ),
        (
            "nested-extra",
            b'{"_note":"","funds":{"Fund":{"cik":"1","note":"","token":"secret"}}}',
            "invalid_shape",
            False,
        ),
        (
            "root-extra",
            b'{"_note":"","funds":{},"secret":"do-not-reflect"}',
            "invalid_shape",
            False,
        ),
        ("directory", None, "unreadable", True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_registry = _http_registry(root / "base")

        empty_catalog_path = root / "valid-empty" / "funds.json"
        _write(empty_catalog_path, {"_note": "", "funds": {}})
        empty_catalog_registry = dict(base_registry)
        empty_catalog_registry["institutions.funds"] = replace(
            ARTIFACTS["institutions.funds"],
            resolver=lambda: ResolvedArtifactPath(empty_catalog_path),
        )
        with _client(empty_catalog_registry) as client:
            empty_catalog = client.get(SOURCE_PATHS["institutions.funds"])
            empty_catalog_health = client.get("/healthz")
        expected_empty_catalog = {
            "available": True,
            "reason": "ok",
            "data": {"funds": {}},
            "meta": {
                "sourceId": "institutions.funds",
                "asOf": None,
                "generatedAt": None,
            },
        }
        if empty_catalog.status_code != 200 or empty_catalog.json() != expected_empty_catalog:
            raise AssertionError((empty_catalog.status_code, empty_catalog.text))
        if empty_catalog.headers.get("cache-control") != "no-store":
            raise AssertionError(empty_catalog.headers)
        if empty_catalog_health.status_code != 200 or empty_catalog_health.json() != {
            "status": "ok",
            "apiVersion": "v1",
        }:
            raise AssertionError(
                (empty_catalog_health.status_code, empty_catalog_health.text)
            )

        for name, raw, expected_reason, make_directory in fixtures:
            path = root / name / "funds.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            registry = dict(base_registry)
            registry["institutions.funds"] = replace(
                ARTIFACTS["institutions.funds"],
                resolver=lambda path=path: ResolvedArtifactPath(path),
            )
            with _client(registry) as client:
                response = client.get(SOURCE_PATHS["institutions.funds"])
                health = client.get("/healthz")
            expected = {
                "available": False,
                "reason": expected_reason,
                "data": None,
                "meta": {
                    "sourceId": "institutions.funds",
                    "asOf": None,
                    "generatedAt": None,
                },
            }
            if response.status_code != 200 or response.json() != expected:
                raise AssertionError((name, response.status_code, response.text))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError((name, response.headers))
            if any(secret in response.text for secret in ("do-not-reflect", "token", "secret")):
                raise AssertionError((name, response.text))
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((name, health.status_code, health.text))

        path = root / "recovery" / "funds.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"_note":"","funds":', encoding="utf-8")
        registry = dict(base_registry)
        registry["institutions.funds"] = replace(
            ARTIFACTS["institutions.funds"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        public_funds = {"Secret-safe Fund": {"cik": "0001", "note": "公開"}}
        with _client(registry) as client:
            first = client.get(SOURCE_PATHS["institutions.funds"])
            _write(
                path,
                {"_note": "secret-source-sentinel", "funds": public_funds},
            )
            second = client.get(SOURCE_PATHS["institutions.funds"])
        expected_available = {
            "available": True,
            "reason": "ok",
            "data": {"funds": public_funds},
            "meta": {
                "sourceId": "institutions.funds",
                "asOf": None,
                "generatedAt": None,
            },
        }
        if first.json()["reason"] != "invalid_json":
            raise AssertionError(first.text)
        if second.status_code != 200 or second.json() != expected_available:
            raise AssertionError((second.status_code, second.text))
        if second.headers.get("cache-control") != "no-store":
            raise AssertionError(second.headers)
        if "secret-source-sentinel" in second.text or "_note" in second.text:
            raise AssertionError(second.text)


def test_fund_catalog_callback_and_projection_contracts_are_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = _http_registry(root / "base")
        resolved = registry["institutions.funds"].resolver()
        if not isinstance(resolved, ResolvedArtifactPath):
            raise AssertionError(resolved)
        base_spec = registry["institutions.funds"]

        def broken_validator(_data: dict[str, object]) -> bool:
            raise RuntimeError("secret validator detail")

        def broken_projector(_data: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("secret projector detail")

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("secret resolver detail")

        defective_specs = [
            replace(base_spec, data_validator=broken_validator),
            replace(base_spec, data_validator=lambda _data: None),
            replace(base_spec, data_validator=lambda _data: 1),
            replace(base_spec, data_projector=broken_projector),
            replace(base_spec, data_projector=lambda _data: []),
            replace(base_spec, data_projector=lambda _data: "not-an-object"),
            replace(base_spec, data_projector=lambda _data: None),
            replace(base_spec, resolver=broken_resolver),
        ]
        for spec in defective_specs:
            defective_registry = dict(registry)
            defective_registry["institutions.funds"] = spec
            with patch("api.main.LOGGER.error") as error_log:
                with _client(defective_registry, raise_server_exceptions=False) as client:
                    response = client.get(SOURCE_PATHS["institutions.funds"])
            if response.status_code != 500 or response.json() != {
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
            }:
                raise AssertionError((response.status_code, response.text))
            if any(secret in response.text for secret in ("validator", "projector", "resolver")):
                raise AssertionError(response.text)
            error_log.assert_called_once()
            if error_log.call_args.kwargs.get("extra") != {
                "route": "/api/v1/institutions/funds",
                "error_type": "RuntimeError"
                if spec in (defective_specs[0], defective_specs[3], defective_specs[7])
                else "TypeError",
            }:
                raise AssertionError(error_log.call_args)

        invalid_projectors = [
            lambda _data: {"funds": {"Valid Name": {"cik": 1, "note": ""}}},
            lambda _data: {"funds": {}, "secret": "do-not-reflect"},
        ]
        for projector in invalid_projectors:
            invalid_registry = dict(registry)
            invalid_registry["institutions.funds"] = replace(
                base_spec,
                data_projector=projector,
            )
            with _client(invalid_registry) as client:
                response = client.get(SOURCE_PATHS["institutions.funds"])
            if response.status_code != 200 or response.json()["reason"] != "invalid_shape":
                raise AssertionError((response.status_code, response.text))
            if "do-not-reflect" in response.text:
                raise AssertionError(response.text)


def test_ai_updates_projection_and_valid_boundaries_are_strict() -> None:
    source = json.loads(
        (ROOT / "content" / "ai_updates.json").read_text(encoding="utf-8")
    )
    real = read_artifact(ARTIFACTS["system.ai-updates"])
    if not isinstance(real, ArtifactAvailable):
        raise AssertionError(real)
    expected_real = {"updates": source["updates"]}
    if real.data != expected_real or "_note" in real.data:
        raise AssertionError(real.data)
    expected_as_of = max(
        (item["date"] for item in source["updates"]),
        default=None,
    )
    actual_as_of = real.meta.as_of.isoformat() if real.meta.as_of else None
    if actual_as_of != expected_as_of:
        raise AssertionError(real.meta)
    if real.meta.generated_at is not None:
        raise AssertionError(real.meta)
    parsed = AiUpdatesData.model_validate(real.data)
    if parsed.model_dump(mode="json") != expected_real:
        raise AssertionError(parsed.model_dump(mode="json"))

    exact_link = "https://example.com/" + "a" * (2048 - len("https://example.com/"))
    exact_tags = [f"{index:02d}" + "x" * 48 for index in range(20)]
    maximum_item = _ai_update(
        date="2024-02-29",
        title="t" * 200,
        summary="s" * 2000,
        link=exact_link,
        tags=exact_tags,
    )
    valid_sources = [
        {"_note": "n" * 2000, "updates": []},
        {
            "_note": "",
            "updates": [_ai_update(title="t", summary="s", link="", tags=[])],
        },
        {"_note": "", "updates": [_ai_update(tags=["x"])]},
        {"_note": "", "updates": [maximum_item.copy() for _ in range(200)]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ai_updates.json"
        spec = replace(
            ARTIFACTS["system.ai-updates"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        for payload in valid_sources:
            _write(path, payload)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactAvailable):
                raise AssertionError((payload, result))
            if result.data != {"updates": payload["updates"]}:
                raise AssertionError(result.data)
            expected = max(
                (item["date"] for item in payload["updates"]),
                default=None,
            )
            actual = result.meta.as_of.isoformat() if result.meta.as_of else None
            if actual != expected or result.meta.generated_at is not None:
                raise AssertionError((actual, result.meta))


def test_ai_updates_reject_invalid_roots_items_and_boundaries() -> None:
    base = _ai_update()
    missing_date = dict(base)
    missing_date.pop("date")
    too_long_link = "https://example.com/" + "a" * (
        2049 - len("https://example.com/")
    )
    invalid_sources: list[object] = [
        [],
        None,
        {},
        {"_note": ""},
        {"updates": []},
        {"_note": 1, "updates": []},
        {"_note": "n" * 2001, "updates": []},
        {"_note": "", "updates": [], "secret": "root-secret-sentinel"},
        {"_note": "", "updates": {}},
        {"_note": "", "updates": "broken"},
        {"_note": "", "updates": None},
        {"_note": "", "updates": [1]},
        {"_note": "", "updates": [base.copy() for _ in range(201)]},
        {"_note": "", "updates": [missing_date]},
        {"_note": "", "updates": [{**base, "secret": "item-secret-sentinel"}]},
        {"_note": "", "updates": [_ai_update(title="")]},
        {"_note": "", "updates": [_ai_update(title="t" * 201)]},
        {"_note": "", "updates": [_ai_update(title=1)]},
        {"_note": "", "updates": [_ai_update(summary="")]},
        {"_note": "", "updates": [_ai_update(summary="s" * 2001)]},
        {"_note": "", "updates": [_ai_update(summary=True)]},
        {"_note": "", "updates": [_ai_update(link=too_long_link)]},
        {"_note": "", "updates": [_ai_update(tags="AI")]},
        {
            "_note": "",
            "updates": [
                _ai_update(tags=[f"tag-{index:02d}" for index in range(21)])
            ],
        },
        {"_note": "", "updates": [_ai_update(tags=[""])]},
        {"_note": "", "updates": [_ai_update(tags=["x" * 51])]},
        {"_note": "", "updates": [_ai_update(tags=["AI", "AI"])]},
        {"_note": "", "updates": [_ai_update(tags=[" leading"])]},
        {"_note": "", "updates": [_ai_update(tags=["trailing "])]},
        {"_note": "", "updates": [_ai_update(tags=[1])]},
        {"_note": "", "updates": [_ai_update(tags=[True])]},
        {"_note": "", "updates": [_ai_update(tags=[None])]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ai_updates.json"
        spec = replace(
            ARTIFACTS["system.ai-updates"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        for index, payload in enumerate(invalid_sources):
            _write(path, payload)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((index, payload, result))


def test_ai_updates_date_link_and_tag_oracles_are_exact() -> None:
    exact_link = "https://example.com/" + "a" * (2048 - len("https://example.com/"))
    valid_links = [
        "",
        "https://example.com",
        "https://example.com/path?q=value#fragment",
        "https://127.0.0.1:8443/path",
        "https://[::1]:8443/path",
        "https://例え.テスト/路徑?q=值#片",
        exact_link,
    ]
    invalid_dates: list[object] = [
        "2023-02-29",
        "2024-02-30",
        "2026-07-15T00:00:00Z",
        "2026-7-5",
        "20260715",
        "2026-W29-3",
        "２０２６-０７-１５",
        20260715,
        True,
        None,
    ]
    invalid_links: list[object] = [
        "/relative",
        "http://example.com/path",
        "HTTPS://example.com/path",
        "https://",
        "https:///path",
        "https://?q=value",
        "https://#fragment",
        "https://user@example.com/path",
        "https://:443/path",
        "https://example.com:",
        "https://[::1/path",
        "https://example.com:not-a-port/path",
        "https://example.com:65536/path",
        "https://exa mple.com/path",
        "https://example.com/white space",
        "https://example.com/\tpath",
        "https://example.com/\npath",
        "https://example.com/\x00path",
        "https://example.com/\x7fpath",
        1,
        True,
        None,
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ai_updates.json"
        spec = replace(
            ARTIFACTS["system.ai-updates"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        for link in valid_links:
            payload = {"_note": "", "updates": [_ai_update(date="2024-02-29", link=link)]}
            _write(path, payload)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactAvailable) or result.data != {
                "updates": payload["updates"]
            }:
                raise AssertionError((link, result))
        for field, values in (("date", invalid_dates), ("link", invalid_links)):
            for value in values:
                _write(
                    path,
                    {"_note": "", "updates": [_ai_update(**{field: value})]},
                )
                result = read_artifact(spec)
                if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                    raise AssertionError((field, value, result))


def test_ai_updates_http_fail_soft_recovery_order_and_metadata() -> None:
    fixtures: list[tuple[str, bytes | None, str, bool]] = [
        ("missing", None, "missing", False),
        ("empty", b"", "invalid_json", False),
        ("truncated", b'{"_note":"","updates":', "invalid_json", False),
        ("invalid-utf8", b"\xff\xfe", "invalid_json", False),
        ("nan", b'{"_note":"","updates":[],"value":NaN}', "invalid_json", False),
        ("list-root", b"[]", "invalid_shape", False),
        (
            "bad-item",
            b'{"_note":"","updates":[{"date":"2026-07-15","title":1}]}',
            "invalid_shape",
            False,
        ),
        (
            "root-extra",
            b'{"_note":"source-secret-sentinel","updates":[],"secret":"root-secret-sentinel"}',
            "invalid_shape",
            False,
        ),
        ("directory", None, "unreadable", True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_registry = _http_registry(root / "base")
        for name, raw, expected_reason, make_directory in fixtures:
            path = root / name / "ai_updates.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            registry = dict(base_registry)
            registry["system.ai-updates"] = replace(
                ARTIFACTS["system.ai-updates"],
                resolver=lambda path=path: ResolvedArtifactPath(path),
            )
            with _client(registry) as client:
                response = client.get(SOURCE_PATHS["system.ai-updates"])
                health = client.get("/healthz")
            expected = {
                "available": False,
                "reason": expected_reason,
                "data": None,
                "meta": {
                    "sourceId": "system.ai-updates",
                    "asOf": None,
                    "generatedAt": None,
                },
            }
            if response.status_code != 200 or response.json() != expected:
                raise AssertionError((name, response.status_code, response.text))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError((name, response.headers))
            if any(secret in response.text for secret in ("source-secret", "root-secret", "_note")):
                raise AssertionError((name, response.text))
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((name, health.status_code, health.text))

        path = root / "recovery" / "ai_updates.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"_note":"","updates":', encoding="utf-8")
        registry = dict(base_registry)
        registry["system.ai-updates"] = replace(
            ARTIFACTS["system.ai-updates"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        ordered = [
            _ai_update(date="2026-07-14", title="middle"),
            _ai_update(date="2026-07-15", title="newest"),
            _ai_update(date="2026-07-12", title="oldest", link=""),
        ]
        with _client(registry) as client:
            first = client.get(SOURCE_PATHS["system.ai-updates"])
            _write(
                path,
                {"_note": "recovery-source-secret-sentinel", "updates": ordered},
            )
            second = client.get(SOURCE_PATHS["system.ai-updates"])
            queried = client.get(
                SOURCE_PATHS["system.ai-updates"],
                params={"path": "/etc/passwd", "url": "http://evil.invalid", "tag": "secret"},
            )
            _write(path, {"_note": "", "updates": []})
            empty = client.get(SOURCE_PATHS["system.ai-updates"])
        if first.json()["reason"] != "invalid_json":
            raise AssertionError(first.text)
        expected_available = {
            "available": True,
            "reason": "ok",
            "data": {"updates": ordered},
            "meta": {
                "sourceId": "system.ai-updates",
                "asOf": "2026-07-15",
                "generatedAt": None,
            },
        }
        if second.status_code != 200 or second.json() != expected_available:
            raise AssertionError((second.status_code, second.text))
        if queried.json() != expected_available or "recovery-source-secret" in queried.text:
            raise AssertionError(queried.text)
        if second.headers.get("cache-control") != "no-store":
            raise AssertionError(second.headers)
        expected_empty = {
            "available": True,
            "reason": "ok",
            "data": {"updates": []},
            "meta": {
                "sourceId": "system.ai-updates",
                "asOf": None,
                "generatedAt": None,
            },
        }
        if empty.status_code != 200 or empty.json() != expected_empty:
            raise AssertionError((empty.status_code, empty.text))


def test_ai_updates_callback_matrix_is_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = _http_registry(root / "base")
        base_spec = registry["system.ai-updates"]

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("callback-secret-resolver")

        def broken_validator(_data: dict[str, object]) -> bool:
            raise RuntimeError("callback-secret-validator")

        def broken_projector(_data: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("callback-secret-projector")

        def broken_as_of(_data: dict[str, object]) -> str | None:
            raise RuntimeError("callback-secret-as-of")

        defective_specs = [
            (replace(base_spec, resolver=broken_resolver), "RuntimeError"),
            (replace(base_spec, resolver=lambda: "callback-secret-wrong-result"), "AttributeError"),
            (replace(base_spec, data_validator=broken_validator), "RuntimeError"),
            (replace(base_spec, data_validator=lambda _data: None), "TypeError"),
            (replace(base_spec, data_validator=lambda _data: 1), "TypeError"),
            (replace(base_spec, data_projector=broken_projector), "RuntimeError"),
            (replace(base_spec, data_projector=lambda _data: []), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: "scalar"), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: None), "TypeError"),
            (replace(base_spec, as_of_extractor=broken_as_of), "RuntimeError"),
            (replace(base_spec, as_of_extractor=lambda _data: 1), "ValueError"),
            (replace(base_spec, as_of_extractor=lambda _data: "2026-02-30"), "ValueError"),
            (replace(base_spec, as_of_extractor=lambda _data: "20260715"), "ValueError"),
        ]
        for spec, error_type in defective_specs:
            defective_registry = dict(registry)
            defective_registry["system.ai-updates"] = spec
            with patch("api.main.LOGGER.error") as error_log:
                with _client(defective_registry, raise_server_exceptions=False) as client:
                    response = client.get(SOURCE_PATHS["system.ai-updates"])
            if response.status_code != 500 or response.json() != {
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
            }:
                raise AssertionError((response.status_code, response.text))
            if response.headers.get("content-type", "").split(";", 1)[0] != (
                "application/problem+json"
            ):
                raise AssertionError(response.headers)
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            if "callback-secret" in response.text:
                raise AssertionError(response.text)
            error_log.assert_called_once()
            if error_log.call_args.kwargs.get("extra") != {
                "route": "/api/v1/system/ai-updates",
                "error_type": error_type,
            }:
                raise AssertionError(error_log.call_args)
            if "callback-secret" in str(error_log.call_args):
                raise AssertionError(error_log.call_args)

        expected_unavailable = {
            "available": False,
            "reason": "invalid_shape",
            "data": None,
            "meta": {
                "sourceId": "system.ai-updates",
                "asOf": None,
                "generatedAt": None,
            },
        }
        false_registry = dict(registry)
        false_registry["system.ai-updates"] = replace(
            base_spec,
            data_validator=lambda _data: False,
        )
        with _client(false_registry) as client:
            false_response = client.get(SOURCE_PATHS["system.ai-updates"])
        if false_response.status_code != 200 or false_response.json() != expected_unavailable:
            raise AssertionError((false_response.status_code, false_response.text))

        invalid_projectors = [
            lambda _data: {"updates": [], "secret": "projector-root-secret"},
            lambda _data: {"updates": [_ai_update(title=1)]},
            lambda _data: {
                "updates": [{**_ai_update(), "secret": "projector-item-secret"}]
            },
        ]
        for projector in invalid_projectors:
            invalid_registry = dict(registry)
            invalid_registry["system.ai-updates"] = replace(
                base_spec,
                data_projector=projector,
            )
            with _client(invalid_registry) as client:
                response = client.get(SOURCE_PATHS["system.ai-updates"])
            if response.status_code != 200 or response.json() != expected_unavailable:
                raise AssertionError((response.status_code, response.text))
            if "projector-" in response.text:
                raise AssertionError(response.text)

        null_as_of_registry = dict(registry)
        null_as_of_registry["system.ai-updates"] = replace(
            base_spec,
            as_of_extractor=lambda _data: None,
        )
        with _client(null_as_of_registry) as client:
            null_as_of = client.get(SOURCE_PATHS["system.ai-updates"])
        if null_as_of.status_code != 200 or null_as_of.json()["meta"]["asOf"] is not None:
            raise AssertionError((null_as_of.status_code, null_as_of.text))


def test_ai_updates_route_retains_loopback_host_and_cors_boundaries() -> None:
    route = SOURCE_PATHS["system.ai-updates"]
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        with _client(registry) as client:
            baseline = client.get(route)
            queried = client.get(
                route,
                params={"path": "/private/secret", "url": "http://evil.invalid", "tag": "AI"},
            )
            origin = client.get(route, headers={"Origin": "https://example.com"})
            preflight = client.options(
                route,
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        with _client(registry, client_address=("198.51.100.20", 50000)) as client:
            remote = client.get(route)
        with _client(registry, base_url="http://example.com") as client:
            wrong_host = client.get(route)

    if baseline.status_code != 200 or queried.json() != baseline.json():
        raise AssertionError((baseline.status_code, queried.text))
    for response in (baseline, queried, origin):
        if response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.headers)
        if any(name.lower().startswith("access-control-") for name in response.headers):
            raise AssertionError(response.headers)
    if any(name.lower().startswith("access-control-") for name in preflight.headers):
        raise AssertionError(preflight.headers)
    expected_problem = {"type": "about:blank", "title": "Forbidden", "status": 403}
    for response in (remote, wrong_host):
        if response.status_code != 403 or response.json() != expected_problem:
            raise AssertionError((response.status_code, response.text))
        if response.headers.get("content-type", "").split(";", 1)[0] != (
            "application/problem+json"
        ):
            raise AssertionError(response.headers)
        if response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.headers)


def test_schedules_projection_and_boundaries_are_strict() -> None:
    source = json.loads(
        (ROOT / "content" / "schedules.json").read_text(encoding="utf-8")
    )
    real = read_artifact(ARTIFACTS["system.schedules"])
    expected_real = {"schedules": source["schedules"]}
    if len(source["schedules"]) != 10 or not isinstance(real, ArtifactAvailable):
        raise AssertionError((len(source["schedules"]), real))
    if real.data != expected_real or "_note" in real.data:
        raise AssertionError(real.data)
    if real.meta.source_id != "system.schedules":
        raise AssertionError(real.meta)
    if real.meta.as_of is not None or real.meta.generated_at is not None:
        raise AssertionError(real.meta)
    parsed = SchedulesData.model_validate(real.data)
    if parsed.model_dump(mode="json") != expected_real:
        raise AssertionError(parsed.model_dump(mode="json"))

    valid_overrides = [
        {"id": "a"},
        {"id": "a" * 64},
        {"result_type": "x"},
        {"result_type": "future_public_result_type"},
        {"result_type": "r" * 64},
        {"name": "n"},
        {"name": "名" * 100},
        {"category": "c"},
        {"category": "類" * 50},
        {"cron": "*"},
        {"cron": "c" * 100},
        {"cron_note": ""},
        {"cron_note": "n" * 500},
        {"description": ""},
        {"description": "d" * 2000},
    ]
    hundred = [_schedule(id=f"job_{index:03d}") for index in range(100)]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "schedules.json"
        spec = replace(
            ARTIFACTS["system.schedules"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        valid_sources = [
            _schedules_source([], note=""),
            _schedules_source(hundred, note="n" * 2000),
            *[_schedules_source([_schedule(**values)]) for values in valid_overrides],
        ]
        for payload in valid_sources:
            _write(path, payload)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactAvailable):
                raise AssertionError((payload, result))
            if result.data != {"schedules": payload["schedules"]}:
                raise AssertionError(result.data)


def test_schedules_reject_invalid_roots_items_types_and_boundaries() -> None:
    base = _schedule()
    invalid_sources: list[object] = [
        [],
        1,
        None,
        {},
        {"_note": ""},
        {"schedules": []},
        _schedules_source([], note=1),
        _schedules_source([], note=True),
        _schedules_source([], note=None),
        _schedules_source([], note="n" * 2001),
        {"_note": "source-secret", "schedules": [], "secret": "root-secret"},
        {"_note": "", "schedules": {}},
        {"_note": "", "schedules": "broken"},
        {"_note": "", "schedules": None},
        _schedules_source([1]),
        _schedules_source([True]),
        _schedules_source([None]),
        _schedules_source([_schedule(id=f"job_{index:03d}") for index in range(101)]),
    ]
    for field in SCHEDULE_FIELDS:
        missing = dict(base)
        missing.pop(field)
        invalid_sources.append(_schedules_source([missing]))
    invalid_sources.append(
        _schedules_source([{**base, "secret": "item-secret-sentinel"}])
    )

    over_limit = {
        "id": "i" * 65,
        "result_type": "r" * 65,
        "name": "n" * 101,
        "category": "c" * 51,
        "cron": "c" * 101,
        "cron_note": "n" * 501,
        "description": "d" * 2001,
    }
    empty_required = ("id", "result_type", "name", "category", "cron")
    for field in empty_required:
        invalid_sources.append(_schedules_source([_schedule(**{field: ""})]))
    for field, value in over_limit.items():
        invalid_sources.append(_schedules_source([_schedule(**{field: value})]))
    for field in SCHEDULE_FIELDS:
        for wrong_type in (1, True, None):
            invalid_sources.append(
                _schedules_source([_schedule(**{field: wrong_type})])
            )
        original = str(base[field])
        invalid_sources.extend(
            [
                _schedules_source([_schedule(**{field: f" {original}"})]),
                _schedules_source([_schedule(**{field: f"{original} "})]),
            ]
        )
    for field in ("id", "result_type"):
        for identifier in (
            "Uppercase",
            "has-hyphen",
            "_leading",
            "trailing_",
            "double__underscore",
            "全形",
        ):
            invalid_sources.append(
                _schedules_source([_schedule(**{field: identifier})])
            )
    invalid_sources.append(
        _schedules_source(
            [
                _schedule(id="duplicate", name="First", result_type="first_type"),
                _schedule(
                    id="duplicate",
                    name="Second",
                    category="Other",
                    cron="0 0 * * *",
                    cron_note="Different note",
                    description="Different object with the same ID.",
                    result_type="second_type",
                ),
            ]
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "schedules.json"
        spec = replace(
            ARTIFACTS["system.schedules"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        for index, payload in enumerate(invalid_sources):
            _write(path, payload)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((index, payload, result))


def test_schedules_http_fail_soft_recovery_order_and_metadata() -> None:
    fixtures: list[tuple[str, bytes | None, str, bool]] = [
        ("missing", None, "missing", False),
        ("empty", b"", "invalid_json", False),
        ("truncated", b'{"_note":"","schedules":', "invalid_json", False),
        ("malformed", b'{"_note":"","schedules":]}', "invalid_json", False),
        ("invalid-utf8", b"\xff\xfe", "invalid_json", False),
        ("nan", b'{"_note":"","schedules":[],"value":NaN}', "invalid_json", False),
        ("infinity", b'{"_note":"","schedules":[],"value":Infinity}', "invalid_json", False),
        ("overflow", b'{"_note":"","schedules":[],"value":1e999}', "invalid_json", False),
        ("list-root", b"[]", "invalid_shape", False),
        ("scalar-root", b"42", "invalid_shape", False),
        ("null-root", b"null", "invalid_shape", False),
        (
            "dto-invalid",
            b'{"_note":"","schedules":[{"id":"job","name":1}]}',
            "invalid_shape",
            False,
        ),
        (
            "root-secret",
            b'{"_note":"source-secret","schedules":[],"secret":"root-secret"}',
            "invalid_shape",
            False,
        ),
        ("directory", None, "unreadable", True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_registry = _http_registry(root / "base")
        for name, raw, reason, make_directory in fixtures:
            path = root / name / "schedules.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            registry = dict(base_registry)
            registry["system.schedules"] = replace(
                ARTIFACTS["system.schedules"],
                resolver=lambda path=path: ResolvedArtifactPath(path),
            )
            with patch("api.main.LOGGER.warning") as warning_log:
                with _client(registry) as client:
                    response = client.get(SOURCE_PATHS["system.schedules"])
                    health = client.get("/healthz")
            if response.status_code != 200 or response.json() != _schedules_unavailable(reason):
                raise AssertionError((name, response.status_code, response.text))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError((name, response.headers))
            if any(value in response.text for value in ("source-secret", "root-secret", "_note")):
                raise AssertionError((name, response.text))
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((name, health.status_code, health.text))
            warning_log.assert_called_once()
            if warning_log.call_args.kwargs.get("extra") != {
                "source_id": "system.schedules",
                "reason": reason,
            }:
                raise AssertionError((name, warning_log.call_args))
            if "secret" in str(warning_log.call_args).lower():
                raise AssertionError((name, warning_log.call_args))

        path = root / "recovery" / "schedules.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"_note":"","schedules":', encoding="utf-8")
        registry = dict(base_registry)
        registry["system.schedules"] = replace(
            ARTIFACTS["system.schedules"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        ordered = [
            _schedule(id="second", name="Second source row"),
            _schedule(id="first", name="First-looking ID remains second"),
        ]
        with _client(registry) as client:
            first = client.get(SOURCE_PATHS["system.schedules"])
            _write(path, _schedules_source(ordered, note="recovery-source-secret"))
            second = client.get(SOURCE_PATHS["system.schedules"])
            _write(path, _schedules_source([], note=""))
            empty = client.get(SOURCE_PATHS["system.schedules"])
        expected = {
            "available": True,
            "reason": "ok",
            "data": {"schedules": ordered},
            "meta": {
                "sourceId": "system.schedules",
                "asOf": None,
                "generatedAt": None,
            },
        }
        if first.json() != _schedules_unavailable("invalid_json"):
            raise AssertionError(first.text)
        if second.status_code != 200 or second.json() != expected:
            raise AssertionError((second.status_code, second.text))
        if second.headers.get("cache-control") != "no-store":
            raise AssertionError(second.headers)
        if (
            "recovery-source-secret" in second.text
            or "_note" in second.json()["data"]
        ):
            raise AssertionError(second.text)
        if empty.status_code != 200 or empty.json() != {
            **expected,
            "data": {"schedules": []},
        }:
            raise AssertionError((empty.status_code, empty.text))
        if empty.headers.get("cache-control") != "no-store":
            raise AssertionError(empty.headers)


def test_schedules_callback_and_projection_matrix_is_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        base_spec = registry["system.schedules"]

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("callback-secret-resolver")

        def broken_validator(_data: dict[str, object]) -> bool:
            raise RuntimeError("callback-secret-validator")

        def broken_projector(_data: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("callback-secret-projector")

        def broken_as_of(_data: dict[str, object]) -> str | None:
            raise RuntimeError("callback-secret-as-of")

        defective_specs = [
            (replace(base_spec, resolver=broken_resolver), "RuntimeError"),
            (replace(base_spec, resolver=lambda: "callback-secret-wrong-result"), "AttributeError"),
            (replace(base_spec, data_validator=broken_validator), "RuntimeError"),
            (replace(base_spec, data_validator=lambda _data: None), "TypeError"),
            (replace(base_spec, data_validator=lambda _data: 1), "TypeError"),
            (replace(base_spec, data_projector=broken_projector), "RuntimeError"),
            (replace(base_spec, data_projector=lambda _data: []), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: "scalar"), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: None), "TypeError"),
            (replace(base_spec, as_of_extractor=broken_as_of), "RuntimeError"),
            (replace(base_spec, as_of_extractor=lambda _data: 1), "ValueError"),
            (replace(base_spec, as_of_extractor=lambda _data: "2026-02-30"), "ValueError"),
            (replace(base_spec, as_of_extractor=lambda _data: "20260715"), "ValueError"),
        ]
        expected_problem = {
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
        }
        for spec, error_type in defective_specs:
            defective_registry = dict(registry)
            defective_registry["system.schedules"] = spec
            with patch("api.main.LOGGER.error") as error_log:
                with _client(
                    defective_registry,
                    raise_server_exceptions=False,
                ) as client:
                    response = client.get(SOURCE_PATHS["system.schedules"])
            if response.status_code != 500 or response.json() != expected_problem:
                raise AssertionError((response.status_code, response.text))
            if response.headers.get("content-type", "").split(";", 1)[0] != (
                "application/problem+json"
            ):
                raise AssertionError(response.headers)
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            if "callback-secret" in response.text:
                raise AssertionError(response.text)
            error_log.assert_called_once()
            if error_log.call_args.kwargs.get("extra") != {
                "route": "/api/v1/system/schedules",
                "error_type": error_type,
            }:
                raise AssertionError(error_log.call_args)
            if "callback-secret" in str(error_log.call_args):
                raise AssertionError(error_log.call_args)

        false_registry = dict(registry)
        false_registry["system.schedules"] = replace(
            base_spec,
            data_validator=lambda _data: False,
        )
        with _client(false_registry) as client:
            false_response = client.get(SOURCE_PATHS["system.schedules"])
        if false_response.status_code != 200 or false_response.json() != (
            _schedules_unavailable()
        ):
            raise AssertionError((false_response.status_code, false_response.text))
        if false_response.headers.get("cache-control") != "no-store":
            raise AssertionError(false_response.headers)

        invalid_projectors = [
            lambda _data: {"schedules": [], "secret": "projector-root-secret"},
            lambda _data: {"schedules": [_schedule(name=1)]},
            lambda _data: {"schedules": [{**_schedule(), "secret": "item-secret"}]},
            lambda _data: {
                "schedules": [
                    _schedule(id="duplicate", name="One"),
                    _schedule(id="duplicate", name="Two", result_type="other"),
                ]
            },
        ]
        for projector in invalid_projectors:
            invalid_registry = dict(registry)
            invalid_registry["system.schedules"] = replace(
                base_spec,
                data_projector=projector,
            )
            with _client(invalid_registry) as client:
                response = client.get(SOURCE_PATHS["system.schedules"])
            if response.status_code != 200 or response.json() != _schedules_unavailable():
                raise AssertionError((response.status_code, response.text))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            if "secret" in response.text:
                raise AssertionError(response.text)

        null_registry = dict(registry)
        null_registry["system.schedules"] = replace(
            base_spec,
            as_of_extractor=lambda _data: None,
        )
        with _client(null_registry) as client:
            null_as_of = client.get(SOURCE_PATHS["system.schedules"])
        resolved = base_spec.resolver()
        if not isinstance(resolved, ResolvedArtifactPath):
            raise AssertionError(resolved)
        source = json.loads(resolved.path.read_text(encoding="utf-8"))
        expected_null_as_of = {
            "available": True,
            "reason": "ok",
            "data": {"schedules": source["schedules"]},
            "meta": {
                "sourceId": "system.schedules",
                "asOf": None,
                "generatedAt": None,
            },
        }
        if null_as_of.status_code != 200 or null_as_of.json() != expected_null_as_of:
            raise AssertionError((null_as_of.status_code, null_as_of.text))
        if null_as_of.headers.get("cache-control") != "no-store":
            raise AssertionError(null_as_of.headers)


def test_schedules_pre_response_defect_is_sanitized_in_real_uvicorn_logs() -> None:
    sentinel = "UVICORN_CALLBACK_SECRET_SENTINEL"
    with tempfile.TemporaryDirectory() as tmp:
        app_module = Path(tmp) / "phase2e_runtime_app.py"
        app_module.write_text(
            "\n".join(
                [
                    "from dataclasses import replace",
                    "from api.artifacts import ARTIFACTS",
                    "from api.main import create_app",
                    "",
                    "def broken_resolver():",
                    f'    raise RuntimeError("{sentinel}")',
                    "",
                    "registry = dict(ARTIFACTS)",
                    'registry["system.schedules"] = replace(',
                    '    registry["system.schedules"], resolver=broken_resolver',
                    ")",
                    "app = create_app(registry)",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "phase2e_runtime_app:app",
                "--app-dir",
                tmp,
                "--fd",
                str(listener.fileno()),
                "--no-access-log",
                "--no-server-header",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            pass_fds=(listener.fileno(),),
        )
        listener.close()

        opener = build_opener(ProxyHandler({}))
        base_url = f"http://127.0.0.1:{port}"
        server_log = ""
        try:
            for _ in range(50):
                if process.poll() is not None:
                    raise AssertionError("spawned Uvicorn exited before readiness")
                try:
                    with opener.open(f"{base_url}/healthz", timeout=1) as response:
                        if response.status != 200:
                            raise AssertionError(response.status)
                        if json.load(response) != {"status": "ok", "apiVersion": "v1"}:
                            raise AssertionError("unexpected health response")
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Uvicorn did not become ready")

            try:
                opener.open(
                    Request(f"{base_url}{SOURCE_PATHS['system.schedules']}"),
                    timeout=2,
                )
            except HTTPError as response:
                response_body = json.load(response)
                response_status = response.code
                response_headers = response.headers
            else:
                raise AssertionError("defective schedules resolver unexpectedly succeeded")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                server_log, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                server_log, _ = process.communicate(timeout=5)

        if response_status != 500 or response_body != {
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
        }:
            raise AssertionError((response_status, response_body))
        if response_headers.get_content_type() != "application/problem+json":
            raise AssertionError(response_headers)
        if response_headers.get("Cache-Control") != "no-store":
            raise AssertionError(response_headers)
        if "unhandled API error" not in server_log:
            raise AssertionError(server_log)
        if sentinel in server_log or "Traceback (most recent call last)" in server_log:
            raise AssertionError(server_log)


def test_schedules_route_is_fixed_loopback_only_and_dependency_free() -> None:
    route = SOURCE_PATHS["system.schedules"]
    expected_path = ROOT / "content" / "schedules.json"
    source = json.loads(expected_path.read_text(encoding="utf-8"))
    expected_body = {
        "available": True,
        "reason": "ok",
        "data": {"schedules": source["schedules"]},
        "meta": {
            "sourceId": "system.schedules",
            "asOf": None,
            "generatedAt": None,
        },
    }
    query_cases = {
        "path": "/private/result-secret.json",
        "url": "https://evil.invalid/result.json",
        "id": "local_data_health_refresh",
        "result_type": "data_health",
    }
    audit_state = {"active": False}
    opened_paths: list[Path] = []

    def record_file_reads(event: str, arguments: tuple[object, ...]) -> None:
        if not audit_state["active"] or event != "open" or not arguments:
            return
        target = arguments[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            opened_paths.append(Path(os.fsdecode(target)).resolve())

    sys.addaudithook(record_file_reads)
    baseline_body: dict[str, object] | None = None
    for query in ({}, *({key: value} for key, value in query_cases.items())):
        opened_paths.clear()
        with patch(
            "api.artifacts.load_json_artifact",
            wraps=load_json_artifact,
        ) as loader:
            with _client(dict(ARTIFACTS)) as client:
                audit_state["active"] = True
                try:
                    response = client.get(route, params=query)
                finally:
                    audit_state["active"] = False
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise AssertionError((query, response.status_code, response.text))
        if loader.call_count != 1 or loader.call_args.args != (expected_path,):
            raise AssertionError((query, loader.call_args_list))
        if response.json() != expected_body:
            raise AssertionError((query, response.json(), expected_body))
        unexpected_reads = [
            path
            for path in opened_paths
            if path != expected_path and not path.is_relative_to(ROOT / "api")
        ]
        if opened_paths.count(expected_path) != 1 or unexpected_reads:
            raise AssertionError((query, opened_paths, unexpected_reads))
        if baseline_body is None:
            baseline_body = response.json()
        elif response.json() != baseline_body:
            raise AssertionError((query, response.json(), baseline_body))

    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        with _client(registry) as client:
            normal = client.get(route)
            origin = client.get(route, headers={"Origin": "https://example.com"})
            preflight = client.options(
                route,
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        with _client(registry, client_address=("198.51.100.20", 50000)) as client:
            remote = client.get(route)
        with _client(registry, base_url="http://example.com") as client:
            wrong_host = client.get(route)
    if origin.status_code != 200 or origin.json() != normal.json():
        raise AssertionError((origin.status_code, origin.text, normal.text))
    for response in (origin, preflight):
        if any(name.lower().startswith("access-control-") for name in response.headers):
            raise AssertionError(response.headers)
    expected_forbidden = {"type": "about:blank", "title": "Forbidden", "status": 403}
    for response in (remote, wrong_host):
        if response.status_code != 403 or response.json() != expected_forbidden:
            raise AssertionError((response.status_code, response.text))
        if response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.headers)

    forbidden_imports = {
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "yfinance",
        "anthropic",
        "openai",
    }
    for relative in ("api/main.py", "api/artifacts.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(text, filename=relative)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(
                    f"{module}.{alias.name}" if module else alias.name
                    for alias in node.names
                )
        if any(name == "ui" or name.startswith("ui.") for name in imported):
            raise AssertionError((relative, imported))
        if forbidden_imports.intersection(imported):
            raise AssertionError((relative, forbidden_imports.intersection(imported)))
        if "ui.sys_schedules" in text or "_RESULT_FETCHERS" in text:
            raise AssertionError(relative)


def test_options_flow_feed_projection_and_valid_boundaries_are_strict() -> None:
    maximum_tags = [f"{index:02d}" + "x" * 98 for index in range(20)]
    boundary_sources = [
        _options_flow_source(
            [
                _options_flow_signal(
                    ticker="A",
                    direction="bearish",
                    flow_score=0,
                    est_notional_usd=1,
                    biggest=None,
                    expiry=None,
                    max_voi=0,
                    high_voi_strikes=0,
                    call_put_ratio=None,
                    put_call_ratio=None,
                    tags=[],
                )
            ],
            generated_at="2026-07-15t06:30:00z",
            provider="x",
            universe_size=1,
            min_notional=1,
            signal_count=1,
            note="",
        ),
        _options_flow_source(
            [
                _options_flow_signal(
                    ticker="A" * 15,
                    flow_score=100,
                    est_notional_usd=1_000_000_000_000_000,
                    biggest={
                        "strike": 1,
                        "notional": 1_000_000_000_000_000,
                        "private": "drop-boundary-secret",
                    },
                    expiry="2024-02-29",
                    max_voi=1_000_000_000,
                    high_voi_strikes=100_000,
                    call_put_ratio=1_000_000_000,
                    put_call_ratio=1_000_000_000,
                    tags=maximum_tags,
                )
            ],
            generated_at="2026-07-15T06:30:00.111111+14:00",
            provider="A" * 64,
            universe_size=10_000,
            min_notional=1_000_000_000_000,
            signal_count=10_000,
            note=" " * 2000,
        ),
        _options_flow_source(
            [
                _options_flow_signal(ticker="A", flow_score=50),
                _options_flow_signal(ticker="B", flow_score=50),
            ],
            universe_size=2,
            signal_count=2,
        ),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        spec = _options_flow_feed_spec(path)
        for source in boundary_sources:
            _write(path, source)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactAvailable):
                raise AssertionError((source, result))
            expected = _public_options_flow(source)
            if result.data != expected:
                raise AssertionError((result.data, expected))
            if set(result.data) != set(OPTIONS_FLOW_FEED_FIELDS):
                raise AssertionError(result.data)
            for signal in result.data["signals"]:
                if set(signal) != set(OPTIONS_FLOW_SIGNAL_FIELDS):
                    raise AssertionError(signal)
                biggest = signal["biggest"]
                if biggest is not None and set(biggest) != set(OPTIONS_FLOW_BIGGEST_FIELDS):
                    raise AssertionError(biggest)
            serialized = json.dumps(result.data, ensure_ascii=False)
            for sentinel in (
                "writer-private-note",
                "writer-private-provider",
                "drop-biggest-secret",
                "drop-signal-secret",
                "drop-boundary-secret",
                "total_call_vol",
                "total_put_vol",
                "otm_call_vol",
                "spot",
            ):
                if sentinel in serialized:
                    raise AssertionError((sentinel, serialized))
            actual_as_of = result.meta.as_of.isoformat() if result.meta.as_of else None
            if actual_as_of != source["as_of"] or result.meta.generated_at is None:
                raise AssertionError(result.meta)
            if result.meta.generated_at != _parse_rfc3339(str(source["generated_at"])):
                raise AssertionError((result.meta, source["generated_at"]))
            feed_model = getattr(model_module, "OptionsFlowFeedData")
            parsed = feed_model.model_validate(result.data)
            if parsed.model_dump(mode="json") != expected:
                raise AssertionError(parsed.model_dump(mode="json"))


def test_options_flow_feed_rejects_invalid_roots_fields_and_invariants() -> None:
    missing_root = _options_flow_source()
    missing_root.pop("provider")
    extra_root = {**_options_flow_source(), "root_secret": "do-not-reflect"}
    missing_signal = _options_flow_source()
    missing_signal["signals"][0].pop("expiry")
    missing_nullable_biggest = _options_flow_source()
    missing_nullable_biggest["signals"][0].pop("biggest")
    missing_nested = _options_flow_source()
    missing_nested["signals"][0]["biggest"].pop("notional")

    def root(**overrides: object) -> dict[str, object]:
        value = _options_flow_source()
        value.update(overrides)
        return value

    def signal(**overrides: object) -> dict[str, object]:
        return _options_flow_source([_options_flow_signal(**overrides)])

    invalid_sources: list[object] = [
        [],
        None,
        {},
        missing_root,
        extra_root,
        root(note=1),
        root(note="n" * 2001),
        root(generated_at="2026-07-15T06:30:00"),
        root(generated_at="2026-07-15 06:30:00Z"),
        root(generated_at="2023-02-29T06:30:00Z"),
        root(generated_at="2026-07-15T25:00:00Z"),
        root(generated_at="2026-07-15T06:30:00.1111111Z"),
        root(generated_at="2026-07-15T06:30:00." + "1" * 44 + "Z"),
        root(generated_at=True),
        root(as_of="2023-02-29"),
        root(as_of="2026-7-5"),
        root(as_of=20260715),
        root(provider=""),
        root(provider="bad provider"),
        root(provider="x\n"),
        root(provider="A" * 65),
        root(provider=True),
        root(universe_size=-1),
        root(universe_size=10_001),
        root(universe_size=1.0),
        root(universe_size=True),
        root(min_notional=0),
        root(min_notional=1_000_000_000_001),
        root(min_notional=1.0),
        root(min_notional=False),
        root(signal_count=-1),
        root(signal_count=10_001),
        root(signal_count=1.0),
        root(signal_count=True),
        root(signals={}),
        root(signals=[1]),
        missing_signal,
        missing_nullable_biggest,
        signal(ticker=""),
        signal(ticker="nvda"),
        signal(ticker="A" * 16),
        signal(ticker="A_B"),
        signal(ticker="NVDA\n"),
        signal(ticker=True),
        signal(direction="neutral"),
        signal(direction=True),
        signal(flow_score=-0.1),
        signal(flow_score=100.1),
        signal(flow_score="91.5"),
        signal(flow_score=True),
        signal(est_notional_usd=0),
        signal(est_notional_usd=1_000_000_000_000_001),
        signal(est_notional_usd=1.0),
        signal(est_notional_usd=True),
        signal(biggest=[]),
        signal(biggest={}),
        signal(biggest={"strike": 1}),
        signal(biggest={"notional": 1}),
        missing_nested,
        signal(biggest={"strike": 0, "notional": 1}),
        signal(biggest={"strike": True, "notional": 1}),
        signal(biggest={"strike": 1, "notional": 0}),
        signal(biggest={"strike": 1, "notional": 1_000_000_000_000_001}),
        signal(biggest={"strike": 1, "notional": True}),
        signal(expiry="2023-02-29"),
        signal(expiry="20260715"),
        signal(expiry=True),
        signal(max_voi=-0.1),
        signal(max_voi=1_000_000_000.1),
        signal(max_voi="8.5"),
        signal(max_voi=True),
        signal(high_voi_strikes=-1),
        signal(high_voi_strikes=100_001),
        signal(high_voi_strikes=1.0),
        signal(high_voi_strikes=True),
        signal(call_put_ratio=-0.1),
        signal(call_put_ratio=1_000_000_000.1),
        signal(call_put_ratio="2.4"),
        signal(call_put_ratio=True),
        signal(put_call_ratio=-0.1),
        signal(put_call_ratio=1_000_000_000.1),
        signal(put_call_ratio="0.42"),
        signal(put_call_ratio=False),
        signal(tags="unusual"),
        signal(tags=[f"tag-{index}" for index in range(21)]),
        signal(tags=["duplicate", "duplicate"]),
        signal(tags=[""]),
        signal(tags=["x" * 101]),
        signal(tags=[" leading"]),
        signal(tags=["trailing "]),
        signal(tags=["trailing-newline\n"]),
        signal(tags=[1]),
        signal(tags=[True]),
        _options_flow_source(
            [_options_flow_signal(ticker="A"), _options_flow_signal(ticker="A")],
            universe_size=2,
            signal_count=2,
        ),
        _options_flow_source(
            [
                _options_flow_signal(ticker="A", flow_score=80),
                _options_flow_signal(ticker="B", flow_score=81),
            ],
            universe_size=2,
            signal_count=2,
        ),
        _options_flow_source([_options_flow_signal()], universe_size=1, signal_count=0),
        _options_flow_source([_options_flow_signal()], universe_size=0, signal_count=1),
        _options_flow_source([], universe_size=4, signal_count=5),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        spec = _options_flow_feed_spec(path)
        for index, source in enumerate(invalid_sources):
            _write(path, source)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((index, source, result))


def test_options_flow_feed_200_201_and_positive_count_empty_semantics() -> None:
    def signals(count: int) -> list[object]:
        return [
            _options_flow_signal(
                ticker=f"T{index:03d}",
                flow_score=max(0, 100 - index / 2),
            )
            for index in range(count)
        ]

    exact_200 = _options_flow_source(
        signals(200),
        universe_size=200,
        signal_count=200,
    )
    over_200 = _options_flow_source(
        signals(201),
        universe_size=201,
        signal_count=201,
    )
    positive_count_empty = _options_flow_source(
        [],
        universe_size=10,
        signal_count=5,
    )
    canonical_empty = _options_flow_source([], universe_size=0, signal_count=0)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        spec = _options_flow_feed_spec(path)
        for source in (exact_200, positive_count_empty, canonical_empty):
            _write(path, source)
            result = read_artifact(spec)
            if not isinstance(result, ArtifactAvailable):
                raise AssertionError((source["signal_count"], result))
            if result.data != _public_options_flow(source):
                raise AssertionError(result.data)
        _write(path, over_200)
        rejected = read_artifact(spec)
        if not isinstance(rejected, ArtifactUnavailable) or rejected.reason != "invalid_shape":
            raise AssertionError(rejected)


def test_options_flow_feed_http_projection_and_latest_compatibility() -> None:
    source = _options_flow_source(
        [
            _options_flow_signal(ticker="NVDA", flow_score=95),
            _options_flow_signal(
                ticker="AAPL",
                direction="bearish",
                flow_score=80,
                biggest=None,
                expiry=None,
                call_put_ratio=None,
                put_call_ratio=None,
                tags=[],
            ),
        ],
        universe_size=5,
        signal_count=2,
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = _write(root / "latest.json", source)
        registry = _http_registry(root / "base")
        registry["signals.options-flow.latest"] = replace(
            ARTIFACTS["signals.options-flow.latest"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        registry[OPTIONS_FLOW_FEED_SOURCE_ID] = _options_flow_feed_spec(path)
        with _client(registry) as client:
            latest = client.get(SOURCE_PATHS["signals.options-flow.latest"])
            feed = client.get(OPTIONS_FLOW_FEED_ROUTE)
            with patch(
                "api.artifacts.load_json_artifact",
                wraps=load_json_artifact,
            ) as loader:
                queried = client.get(
                    OPTIONS_FLOW_FEED_ROUTE,
                    params={
                        "path": "/private/secret.json",
                        "url": "https://evil.invalid/feed",
                        "provider": "evil",
                    },
                )
        if latest.status_code != 200 or latest.json()["data"] != source:
            raise AssertionError((latest.status_code, latest.text))
        if latest.json()["meta"]["sourceId"] != "signals.options-flow.latest":
            raise AssertionError(latest.json())
        if feed.status_code != 200 or feed.headers.get("cache-control") != "no-store":
            raise AssertionError((feed.status_code, feed.text, feed.headers))
        body = feed.json()
        if body["data"] != _public_options_flow(source):
            raise AssertionError(body)
        if body["meta"]["sourceId"] != OPTIONS_FLOW_FEED_SOURCE_ID:
            raise AssertionError(body["meta"])
        if body["meta"]["asOf"] != source["as_of"]:
            raise AssertionError(body["meta"])
        if _parse_rfc3339(body["meta"]["generatedAt"]) != _parse_rfc3339(
            str(source["generated_at"])
        ):
            raise AssertionError(body["meta"])
        if queried.json() != body or loader.call_args_list != [((path,), {})]:
            raise AssertionError((queried.text, loader.call_args_list))
        for response in (latest, feed, queried):
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
        forbidden = (
            "writer-private-note",
            "writer-private-provider",
            "signal_private_sentinel",
            "nested_private_sentinel",
            "private/secret",
            "evil.invalid",
        )
        if any(value in feed.text or value in queried.text for value in forbidden):
            raise AssertionError((feed.text, queried.text))


def test_options_flow_feed_fail_soft_reason_mapping_and_recovery() -> None:
    valid_source = _options_flow_source([], universe_size=3, signal_count=2)
    fixtures: list[tuple[str, bytes | None, str, bool, bool]] = [
        ("missing", None, "missing", False, False),
        ("truncated", b'{"generated_at":', "invalid_json", False, False),
        ("malformed", b'{] not-json', "invalid_json", False, False),
        ("permission", json.dumps(valid_source).encode(), "unreadable", False, True),
        ("non-object", b"[]", "invalid_shape", False, False),
        ("directory", None, "unreadable", True, False),
        (
            "invariant",
            json.dumps(
                _options_flow_source(
                    [_options_flow_signal()],
                    universe_size=0,
                    signal_count=1,
                )
            ).encode(),
            "invalid_shape",
            False,
            False,
        ),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_registry = _http_registry(root / "base")
        for name, raw, reason, make_directory, deny_read in fixtures:
            path = root / name / "latest.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            if deny_read:
                path.chmod(0)
            registry = dict(base_registry)
            registry[OPTIONS_FLOW_FEED_SOURCE_ID] = _options_flow_feed_spec(path)
            try:
                with patch("api.main.LOGGER.warning") as warning_log:
                    with _client(registry) as client:
                        failed = client.get(OPTIONS_FLOW_FEED_ROUTE)
                        health = client.get("/healthz")
                        if deny_read:
                            path.chmod(0o600)
                        if make_directory:
                            path.rmdir()
                        _write(path, valid_source)
                        recovered = client.get(OPTIONS_FLOW_FEED_ROUTE)
            finally:
                if deny_read and path.exists():
                    path.chmod(0o600)
            if failed.status_code != 200 or failed.json() != _options_flow_unavailable(reason):
                raise AssertionError((name, failed.status_code, failed.text))
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((name, health.status_code, health.text))
            expected_data = _public_options_flow(valid_source)
            if (
                recovered.status_code != 200
                or recovered.json().get("available") is not True
                or recovered.json().get("data") != expected_data
            ):
                raise AssertionError((name, recovered.status_code, recovered.text))
            for response in (failed, recovered):
                if response.headers.get("cache-control") != "no-store":
                    raise AssertionError((name, response.headers))
                if "secret" in response.text or "latest.json" in response.text:
                    raise AssertionError((name, response.text))
            if warning_log.call_count != 1 or warning_log.call_args.kwargs.get("extra") != {
                "source_id": OPTIONS_FLOW_FEED_SOURCE_ID,
                "reason": reason,
            }:
                raise AssertionError((name, warning_log.call_args_list))


def test_options_flow_feed_callback_matrix_is_sanitized() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        base_spec = registry[OPTIONS_FLOW_FEED_SOURCE_ID]

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("callback-secret-resolver")

        def broken_validator(_data: dict[str, object]) -> bool:
            raise RuntimeError("callback-secret-validator")

        def broken_projector(_data: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("callback-secret-projector")

        defective_specs = [
            (replace(base_spec, resolver=broken_resolver), "RuntimeError"),
            (replace(base_spec, resolver=lambda: "callback-secret-wrong-type"), "AttributeError"),
            (replace(base_spec, data_validator=broken_validator), "RuntimeError"),
            (replace(base_spec, data_validator=lambda _data: None), "TypeError"),
            (replace(base_spec, data_validator=lambda _data: 1), "TypeError"),
            (replace(base_spec, data_projector=broken_projector), "RuntimeError"),
            (replace(base_spec, data_projector=lambda _data: None), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: False), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: 7), "TypeError"),
            (replace(base_spec, data_projector=lambda _data: []), "TypeError"),
        ]
        expected_problem = {
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
        }
        for spec, error_type in defective_specs:
            defective_registry = dict(registry)
            defective_registry[OPTIONS_FLOW_FEED_SOURCE_ID] = spec
            with patch("api.main.LOGGER.error") as error_log:
                with _client(defective_registry, raise_server_exceptions=False) as client:
                    response = client.get(OPTIONS_FLOW_FEED_ROUTE)
            if response.status_code != 500 or response.json() != expected_problem:
                raise AssertionError((response.status_code, response.text))
            if response.headers.get("content-type", "").split(";", 1)[0] != (
                "application/problem+json"
            ):
                raise AssertionError(response.headers)
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            error_log.assert_called_once()
            if error_log.call_args.kwargs.get("extra") != {
                "route": OPTIONS_FLOW_FEED_ROUTE,
                "error_type": error_type,
            }:
                raise AssertionError(error_log.call_args)
            if "callback-secret" in response.text or "callback-secret" in str(
                error_log.call_args
            ):
                raise AssertionError((response.text, error_log.call_args))

        false_registry = dict(registry)
        false_registry[OPTIONS_FLOW_FEED_SOURCE_ID] = replace(
            base_spec,
            data_validator=lambda _data: False,
        )
        with _client(false_registry) as client:
            false_response = client.get(OPTIONS_FLOW_FEED_ROUTE)
        if false_response.status_code != 200 or false_response.json() != (
            _options_flow_unavailable()
        ):
            raise AssertionError((false_response.status_code, false_response.text))

        public = _public_options_flow(_options_flow_source())
        extra_root = {**public, "projector_secret": "do-not-reflect"}
        missing_required = deepcopy(public)
        missing_required["signals"][0].pop("expiry")
        non_finite = deepcopy(public)
        non_finite["signals"][0]["flow_score"] = float("inf")
        for projected in (extra_root, missing_required, non_finite):
            invalid_registry = dict(registry)
            invalid_registry[OPTIONS_FLOW_FEED_SOURCE_ID] = replace(
                base_spec,
                data_projector=lambda _data, projected=projected: projected,
            )
            with patch("api.main.LOGGER.error") as error_log:
                with _client(invalid_registry) as client:
                    response = client.get(OPTIONS_FLOW_FEED_ROUTE)
            if response.status_code != 200 or response.json() != _options_flow_unavailable():
                raise AssertionError((response.status_code, response.text))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            if "projector_secret" in response.text:
                raise AssertionError(response.text)
            error_log.assert_not_called()


def test_options_flow_feed_is_fixed_and_dependency_free() -> None:
    expected_path = ROOT / "reports" / "options_flow" / "latest.json"
    spec = ARTIFACTS[OPTIONS_FLOW_FEED_SOURCE_ID]
    resolved = spec.resolver()
    if not isinstance(resolved, ResolvedArtifactPath) or resolved.path != expected_path:
        raise AssertionError(resolved)
    forbidden_imports = {
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "yfinance",
        "anthropic",
        "openai",
        "scripts.options_flow_scan",
    }
    for relative in ("api/main.py", "api/artifacts.py", "api/models.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(
                    f"{module}.{alias.name}" if module else alias.name
                    for alias in node.names
                )
        disallowed = forbidden_imports.intersection(imported)
        if disallowed:
            raise AssertionError((relative, disallowed))
        if any(name == "ui" or name.startswith("ui.") for name in imported):
            raise AssertionError((relative, imported))
        for forbidden_text in (
            "options_flow_scan",
            "ui.us_options",
            "ui.options_flow",
            "get_option_chain",
            "send_telegram",
        ):
            if forbidden_text in source:
                raise AssertionError((relative, forbidden_text))


def test_http_routes_return_typed_available_envelopes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        with _client(registry) as client:
            health = client.get("/healthz")
            if health.status_code != 200 or health.json() != {
                "status": "ok",
                "apiVersion": "v1",
            }:
                raise AssertionError((health.status_code, health.text))
            if health.headers.get("cache-control") != "no-store":
                raise AssertionError(health.headers)

            for source_id, route in SOURCE_PATHS.items():
                response = client.get(route)
                if response.status_code != 200:
                    raise AssertionError((route, response.status_code, response.text))
                body = response.json()
                if body["available"] is not True or body["reason"] != "ok":
                    raise AssertionError((route, body))
                if body["meta"]["sourceId"] != source_id:
                    raise AssertionError((route, body["meta"]))
                if response.headers.get("cache-control") != "no-store":
                    raise AssertionError((route, response.headers))

            ranked = client.get(SOURCE_PATHS["candidates.ranked"]).json()["data"]
            if ranked["top_level_sentinel"] != {"preserve": True}:
                raise AssertionError(ranked)
            if ranked["ranked_candidates"][0]["nested_sentinel"] != {"keep": [1, "two"]}:
                raise AssertionError(ranked)
            funds = client.get(SOURCE_PATHS["institutions.funds"]).json()["data"]
            if set(funds) != {"funds"} or "_note" in funds:
                raise AssertionError(funds)


def test_health_is_independent_when_every_artifact_is_missing() -> None:
    missing_registry = {
        source_id: replace(
            spec,
            resolver=lambda: ArtifactPathUnavailable("missing"),
        )
        for source_id, spec in ARTIFACTS.items()
    }
    with _client(missing_registry) as client:
        response = client.get("/healthz")
    if response.status_code != 200 or response.json() != {
        "status": "ok",
        "apiVersion": "v1",
    }:
        raise AssertionError((response.status_code, response.text))
    if response.headers.get("cache-control") != "no-store":
        raise AssertionError(response.headers)


def test_http_failure_matrix_is_fail_soft() -> None:
    fixtures: list[tuple[str, bytes | None, str, bool]] = [
        ("missing", None, "missing", False),
        ("empty", b"", "invalid_json", False),
        ("truncated", b'{"ranked_candidates":', "invalid_json", False),
        ("invalid-utf8", b"\xff\xfe", "invalid_json", False),
        ("nan", b'{"ranked_candidates": [], "value": NaN}', "invalid_json", False),
        ("infinity", b'{"ranked_candidates": [], "value": Infinity}', "invalid_json", False),
        ("overflow", b'{"ranked_candidates": [], "value": 1e999}', "invalid_json", False),
        (
            "lone-surrogate",
            br'{"ranked_candidates": [], "value": "\ud800"}',
            "invalid_json",
            False,
        ),
        ("list-root", b"[]", "invalid_shape", False),
        ("scalar-root", b"42", "invalid_shape", False),
        ("null-root", b"null", "invalid_shape", False),
        ("wrong-anchor", b'{"ranked_candidates": "broken"}', "invalid_shape", False),
        ("wrong-item", b'{"ranked_candidates": [1]}', "invalid_shape", False),
        ("directory", None, "unreadable", True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_registry = _http_registry(root / "base")
        for name, raw, expected_reason, make_directory in fixtures:
            path = root / name / "ranked.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            if make_directory:
                path.mkdir()
            elif raw is not None:
                path.write_bytes(raw)
            registry = dict(base_registry)
            registry["candidates.ranked"] = replace(
                ARTIFACTS["candidates.ranked"],
                resolver=lambda path=path: ResolvedArtifactPath(path),
            )
            with _client(registry) as client:
                response = client.get(SOURCE_PATHS["candidates.ranked"])
            if response.status_code != 200:
                raise AssertionError((name, response.status_code, response.text))
            body = response.json()
            expected = {
                "available": False,
                "reason": expected_reason,
                "data": None,
                "meta": {
                    "sourceId": "candidates.ranked",
                    "asOf": None,
                    "generatedAt": None,
                },
            }
            if body != expected:
                raise AssertionError((name, body))
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError((name, response.headers))


def test_http_recovers_on_the_next_request_without_negative_cache() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = _http_registry(root / "base")
        path = root / "ranked.json"
        path.write_text('{"ranked_candidates":', encoding="utf-8")
        registry["candidates.ranked"] = replace(
            ARTIFACTS["candidates.ranked"],
            resolver=lambda: ResolvedArtifactPath(path),
        )
        with _client(registry) as client:
            first = client.get(SOURCE_PATHS["candidates.ranked"])
            path.write_text('{"ranked_candidates": [{"ticker": "AAPL"}]}', encoding="utf-8")
            second = client.get(SOURCE_PATHS["candidates.ranked"])

    if first.json()["reason"] != "invalid_json":
        raise AssertionError(first.json())
    if second.json()["available"] is not True:
        raise AssertionError(second.json())


def test_invalid_generated_at_metadata_is_omitted_without_failing() -> None:
    invalid_values = [
        "20260714T120000",
        "2026-W29-2T12:00:00+00:00",
        "2026-07-14T12:00:00",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = _http_registry(root / "base")
        resolved = registry["candidates.ranked"].resolver()
        if not isinstance(resolved, ResolvedArtifactPath):
            raise AssertionError(resolved)
        with _client(registry) as client:
            for value in invalid_values:
                _write(
                    resolved.path,
                    {
                        "ranked_candidates": [],
                        "generated_at": value,
                    },
                )
                response = client.get(SOURCE_PATHS["candidates.ranked"])
                if response.status_code != 200:
                    raise AssertionError((value, response.status_code, response.text))
                body = response.json()
                if body["available"] is not True or body["meta"]["generatedAt"] is not None:
                    raise AssertionError((value, body))

            _write(
                resolved.path,
                {
                    "ranked_candidates": [],
                    "generated_at": "2026-07-14T12:00:00Z",
                },
            )
            valid = client.get(SOURCE_PATHS["candidates.ranked"]).json()
    if valid["meta"]["generatedAt"] != "2026-07-14T12:00:00Z":
        raise AssertionError(valid)


def test_unexpected_error_returns_sanitized_problem() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))

        def broken_resolver() -> ResolvedArtifactPath:
            raise RuntimeError("secret /private/path should not leak")

        registry["candidates.ranked"] = replace(
            ARTIFACTS["candidates.ranked"],
            resolver=broken_resolver,
        )
        with _client(registry, raise_server_exceptions=False) as client:
            response = client.get(SOURCE_PATHS["candidates.ranked"])

    if response.status_code != 500:
        raise AssertionError((response.status_code, response.text))
    if response.headers.get("content-type", "").split(";", 1)[0] != "application/problem+json":
        raise AssertionError(response.headers)
    if response.headers.get("cache-control") != "no-store":
        raise AssertionError(response.headers)
    body = response.json()
    if body != {"type": "about:blank", "title": "Internal Server Error", "status": 500}:
        raise AssertionError(body)
    if "private" in response.text or "secret" in response.text:
        raise AssertionError(response.text)


def test_loopback_boundary_and_cors_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        with _client(registry) as local:
            response = local.get("/healthz", headers={"Origin": "https://evil.example"})
            preflight = local.options(
                "/healthz",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
        if "access-control-allow-origin" in response.headers:
            raise AssertionError(response.headers)
        if "access-control-allow-origin" in preflight.headers:
            raise AssertionError(preflight.headers)

        with _client(
            registry,
            client_address=("203.0.113.10", 50000),
        ) as remote:
            remote_response = remote.get("/healthz")
        if remote_response.status_code != 403:
            raise AssertionError((remote_response.status_code, remote_response.text))

        with _client(
            registry,
            base_url="http://evil.example",
        ) as wrong_host:
            host_response = wrong_host.get("/healthz")
        with _client(registry) as malformed_ipv6_host:
            malformed_host_response = malformed_ipv6_host.get(
                "/healthz",
                headers={"Host": "[::1]evil"},
            )
            valid_ipv6_host_response = malformed_ipv6_host.get(
                "/healthz",
                headers={"Host": "[::1]:8000"},
            )
        if host_response.status_code != 403:
            raise AssertionError((host_response.status_code, host_response.text))
        if malformed_host_response.status_code != 403:
            raise AssertionError(
                (malformed_host_response.status_code, malformed_host_response.text)
            )
        if valid_ipv6_host_response.status_code != 200:
            raise AssertionError(
                (valid_ipv6_host_response.status_code, valid_ipv6_host_response.text)
            )
        for rejected in (remote_response, host_response, malformed_host_response):
            if rejected.headers.get("content-type", "").split(";", 1)[0] != "application/problem+json":
                raise AssertionError(rejected.headers)
            if rejected.headers.get("cache-control") != "no-store":
                raise AssertionError(rejected.headers)


def test_options_flow_feed_openapi_contract_is_strict_and_in_parity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with _client(_http_registry(Path(tmp))) as client:
            generated = client.get("/openapi.json").json()
    static = yaml.safe_load(
        (ROOT / "docs" / "api" / "quant-radar-v1.openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    if generated["info"]["version"] != "1.23.0-draft":
        raise AssertionError(generated["info"])
    if static["info"]["version"] != generated["info"]["version"]:
        raise AssertionError((static["info"], generated["info"]))

    generated_operation = generated["paths"][OPTIONS_FLOW_FEED_ROUTE]["get"]
    static_operation = static["paths"][OPTIONS_FLOW_FEED_ROUTE]["get"]
    for label, operation in (
        ("generated", generated_operation),
        ("static", static_operation),
    ):
        if operation.get("operationId") != "getOptionsFlowFeed":
            raise AssertionError((label, operation))
        if operation.get("tags") != ["Signals"]:
            raise AssertionError((label, operation.get("tags")))
        if operation.get("parameters") not in (None, []):
            raise AssertionError((label, operation.get("parameters")))
        if set(operation["responses"]) != {"200", "500"}:
            raise AssertionError((label, operation["responses"]))
    if static_operation["responses"] != {
        "200": {"$ref": "#/components/responses/OptionsFlowFeedResponse"},
        "500": {"$ref": "#/components/responses/InternalProblem"},
    }:
        raise AssertionError(static_operation["responses"])

    static_response = static["components"]["responses"]["OptionsFlowFeedResponse"]
    if static_response.get("headers", {}).get("Cache-Control") != {
        "$ref": "#/components/headers/NoStore"
    }:
        raise AssertionError(static_response)
    static_content = static_response["content"]["application/json"]
    generated_content = generated_operation["responses"]["200"]["content"][
        "application/json"
    ]
    static_envelope = static["components"]["schemas"]["OptionsFlowFeedEnvelope"]
    if static_envelope.get("oneOf") != [
        {"$ref": "#/components/schemas/AvailableOptionsFlowFeed"},
        {"$ref": "#/components/schemas/UnavailableArtifact"},
    ]:
        raise AssertionError(static_envelope)
    static_available = static["components"]["schemas"]["AvailableOptionsFlowFeed"]
    if static_available.get("unevaluatedProperties") is not False:
        raise AssertionError(static_available)
    if static_available.get("allOf") != [
        {"$ref": "#/components/schemas/AvailableArtifactBase"},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"$ref": "#/components/schemas/OptionsFlowFeedData"}
            },
        },
    ]:
        raise AssertionError(static_available)

    generated_examples = _example_values(generated_content)
    static_examples = _example_values(static_content)
    if len(generated_examples) != 3 or len(static_examples) != 3:
        raise AssertionError((generated_examples, static_examples))
    generated_canonical = {
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        for value in generated_examples
    }
    static_canonical = {
        json.dumps(value, ensure_ascii=False, sort_keys=True) for value in static_examples
    }
    if generated_canonical != static_canonical:
        raise AssertionError((generated_examples, static_examples))
    available_examples = [
        value
        for value in static_examples
        if isinstance(value, dict) and value.get("available") is True
    ]
    unavailable_examples = [
        value
        for value in static_examples
        if isinstance(value, dict) and value.get("available") is False
    ]
    if (
        len(available_examples) != 2
        or len(unavailable_examples) != 1
        or not any(value["data"]["signals"] for value in available_examples)
        or not any(value["data"]["signals"] == [] for value in available_examples)
        or unavailable_examples[0] != _options_flow_unavailable("missing")
    ):
        raise AssertionError(static_examples)
    for example in available_examples:
        if set(example["data"]) != set(OPTIONS_FLOW_FEED_FIELDS):
            raise AssertionError(example)
        if example["meta"]["sourceId"] != OPTIONS_FLOW_FEED_SOURCE_ID:
            raise AssertionError(example["meta"])
        if example["meta"]["asOf"] != example["data"]["as_of"]:
            raise AssertionError(example)
        if _parse_rfc3339(example["meta"]["generatedAt"]) != _parse_rfc3339(
            example["data"]["generated_at"]
        ):
            raise AssertionError(example)
        serialized = json.dumps(example, ensure_ascii=False)
        for private in ("note", "premium", "volume", "voi", "spot", "total_call"):
            if f'"{private}"' in serialized:
                raise AssertionError((private, example))

    def nullable_branch(
        value: dict[str, object],
        *,
        expected_ref: str | None = None,
        expected_type: str | None = None,
    ) -> dict[str, object]:
        branches = value.get("anyOf")
        if not isinstance(branches, list) or {branch.get("type") for branch in branches} & {
            "null"
        } != {"null"}:
            raise AssertionError(value)
        non_null = [branch for branch in branches if branch.get("type") != "null"]
        if len(non_null) != 1:
            raise AssertionError(value)
        branch = non_null[0]
        if expected_ref is not None and branch.get("$ref") != expected_ref:
            raise AssertionError(value)
        if expected_type is not None and branch.get("type") != expected_type:
            raise AssertionError(value)
        return branch

    for label, schemas in (
        ("generated", generated["components"]["schemas"]),
        ("static", static["components"]["schemas"]),
    ):
        data = schemas["OptionsFlowFeedData"]
        if data.get("additionalProperties") is not False:
            raise AssertionError((label, data))
        if set(data.get("required", [])) != set(OPTIONS_FLOW_FEED_FIELDS):
            raise AssertionError((label, data))
        if set(data.get("properties", {})) != set(OPTIONS_FLOW_FEED_FIELDS):
            raise AssertionError((label, data))
        properties = data["properties"]
        generated_at = properties["generated_at"]
        if (
            generated_at.get("type") != "string"
            or generated_at.get("format") != "date-time"
            or generated_at.get("minLength") != 20
            or generated_at.get("maxLength") != 32
            or generated_at.get("pattern") != OPTIONS_FLOW_RFC3339_PATTERN
        ):
            raise AssertionError((label, generated_at))
        as_of = properties["as_of"]
        if as_of.get("type") != "string" or as_of.get("format") != "date":
            raise AssertionError((label, as_of))
        if as_of.get("pattern") != OPTIONS_FLOW_DATE_PATTERN:
            raise AssertionError((label, as_of))
        provider = properties["provider"]
        if (
            provider.get("type") != "string"
            or provider.get("minLength") != 1
            or provider.get("maxLength") != 64
            or provider.get("pattern") != OPTIONS_FLOW_PROVIDER_PATTERN
        ):
            raise AssertionError((label, provider))
        for field, minimum, maximum in (
            ("universe_size", 0, 10_000),
            ("min_notional", 1, 1_000_000_000_000),
            ("signal_count", 0, 10_000),
        ):
            count = properties[field]
            if count.get("type") != "integer" or count.get("minimum") != minimum:
                raise AssertionError((label, field, count))
            if count.get("maximum") != maximum:
                raise AssertionError((label, field, count))
        signals = properties["signals"]
        if (
            signals.get("type") != "array"
            or signals.get("minItems") not in (None, 0)
            or signals.get("maxItems") != 200
            or signals.get("items")
            != {"$ref": "#/components/schemas/OptionsFlowFeedSignal"}
            or "uniqueItems" in signals
        ):
            raise AssertionError((label, signals))

        signal = schemas["OptionsFlowFeedSignal"]
        if signal.get("additionalProperties") is not False:
            raise AssertionError((label, signal))
        if set(signal.get("required", [])) != set(OPTIONS_FLOW_SIGNAL_FIELDS):
            raise AssertionError((label, signal))
        if set(signal.get("properties", {})) != set(OPTIONS_FLOW_SIGNAL_FIELDS):
            raise AssertionError((label, signal))
        fields = signal["properties"]
        ticker = fields["ticker"]
        if (
            ticker.get("type") != "string"
            or ticker.get("minLength") != 1
            or ticker.get("maxLength") != 15
            or ticker.get("pattern") != OPTIONS_FLOW_TICKER_PATTERN
        ):
            raise AssertionError((label, ticker))
        if fields["direction"].get("enum") != ["bullish", "bearish"]:
            raise AssertionError((label, fields["direction"]))
        for field, field_type, minimum, maximum in (
            ("flow_score", "number", 0, 100),
            ("est_notional_usd", "integer", 1, 1_000_000_000_000_000),
            ("max_voi", "number", 0, 1_000_000_000),
            ("high_voi_strikes", "integer", 0, 100_000),
        ):
            numeric = fields[field]
            if (
                numeric.get("type") != field_type
                or numeric.get("minimum") != minimum
                or numeric.get("maximum") != maximum
            ):
                raise AssertionError((label, field, numeric))
        nullable_branch(
            fields["biggest"],
            expected_ref="#/components/schemas/OptionsFlowFeedBiggest",
        )
        expiry = nullable_branch(fields["expiry"], expected_type="string")
        if expiry.get("format") != "date" or expiry.get("pattern") != (
            OPTIONS_FLOW_DATE_PATTERN
        ):
            raise AssertionError((label, expiry))
        for field in ("call_put_ratio", "put_call_ratio"):
            ratio = nullable_branch(fields[field], expected_type="number")
            if ratio.get("minimum") != 0 or ratio.get("maximum") != 1_000_000_000:
                raise AssertionError((label, field, ratio))
        tags = fields["tags"]
        tag = tags.get("items", {})
        if (
            tags.get("type") != "array"
            or tags.get("minItems") not in (None, 0)
            or tags.get("maxItems") != 20
            or tags.get("uniqueItems") is not True
            or tag.get("type") != "string"
            or tag.get("minLength") != 1
            or tag.get("maxLength") != 100
            or tag.get("pattern") != OPTIONS_FLOW_TAG_PATTERN
        ):
            raise AssertionError((label, tags))

        biggest = schemas["OptionsFlowFeedBiggest"]
        if biggest.get("additionalProperties") is not False:
            raise AssertionError((label, biggest))
        if set(biggest.get("required", [])) != set(OPTIONS_FLOW_BIGGEST_FIELDS):
            raise AssertionError((label, biggest))
        if set(biggest.get("properties", {})) != set(OPTIONS_FLOW_BIGGEST_FIELDS):
            raise AssertionError((label, biggest))
        strike = nullable_branch(biggest["properties"]["strike"], expected_type="number")
        notional = nullable_branch(
            biggest["properties"]["notional"], expected_type="number"
        )
        if strike.get("exclusiveMinimum") != 0:
            raise AssertionError((label, strike))
        if notional.get("exclusiveMinimum") != 0 or notional.get("maximum") != (
            1_000_000_000_000_000
        ):
            raise AssertionError((label, notional))

    for label, document, response_schema, examples in (
        ("generated", generated, generated_content["schema"], generated_examples),
        (
            "static",
            static,
            {"$ref": "#/components/schemas/OptionsFlowFeedEnvelope"},
            static_examples,
        ),
    ):
        validator = _schema_validator(document, response_schema)
        for example in examples:
            validator.validate(example)
        available = next(
            example
            for example in examples
            if isinstance(example, dict)
            and example.get("available") is True
            and example["data"]["signals"]
        )
        invalid_examples: list[dict[str, object]] = []
        for location, secret in (
            ((), "envelope-secret"),
            (("data",), "data-secret"),
            (("data", "signals", 0), "signal-secret"),
            (("data", "signals", 0, "biggest"), "biggest-secret"),
        ):
            invalid = deepcopy(available)
            target: object = invalid
            for key in location:
                target = target[key]
            target["secret"] = secret
            invalid_examples.append(invalid)
        missing_nullable = deepcopy(available)
        del missing_nullable["data"]["signals"][0]["expiry"]
        invalid_examples.append(missing_nullable)
        missing_biggest_key = deepcopy(available)
        del missing_biggest_key["data"]["signals"][0]["biggest"]["notional"]
        invalid_examples.append(missing_biggest_key)
        duplicate_tags = deepcopy(available)
        duplicate_tags["data"]["signals"][0]["tags"] = ["same", "same"]
        invalid_examples.append(duplicate_tags)
        invalid_ticker = deepcopy(available)
        invalid_ticker["data"]["signals"][0]["ticker"] = "lowercase"
        invalid_examples.append(invalid_ticker)
        newline_provider = deepcopy(available)
        newline_provider["data"]["provider"] = "provider\n"
        invalid_examples.append(newline_provider)
        newline_ticker = deepcopy(available)
        newline_ticker["data"]["signals"][0]["ticker"] = "NVDA\n"
        invalid_examples.append(newline_ticker)
        newline_tag = deepcopy(available)
        newline_tag["data"]["signals"][0]["tags"] = ["tag\n"]
        invalid_examples.append(newline_tag)
        invalid_timestamp = deepcopy(available)
        invalid_timestamp["data"]["generated_at"] = "2026-07-15T25:00:00Z"
        invalid_examples.append(invalid_timestamp)
        too_many = deepcopy(available)
        too_many["data"]["signals"] = [
            deepcopy(available["data"]["signals"][0]) for _ in range(201)
        ]
        invalid_examples.append(too_many)
        for invalid in invalid_examples:
            try:
                validator.validate(invalid)
            except JsonSchemaValidationError:
                continue
            raise AssertionError((label, invalid))


def test_openapi_and_path_surface_match_the_draft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = _http_registry(Path(tmp))
        with _client(registry) as client:
            schema = client.get("/openapi.json").json()
            traversal = client.get("/api/v1/artifacts/%2e%2e/%2e%2e/etc/passwd")
            generic = client.get("/api/v1/file", params={"path": "/etc/passwd"})
            with_query = client.get(
                SOURCE_PATHS["candidates.ranked"],
                params={"path": "/etc/passwd", "sql": "select * from secrets"},
            )

    draft = yaml.safe_load((ROOT / "docs" / "api" / "quant-radar-v1.openapi.yaml").read_text())
    if schema["openapi"] != "3.1.0" or set(schema["paths"]) != EXPECTED_PATHS:
        raise AssertionError(schema["paths"])
    if schema["info"]["version"] != "1.23.0-draft":
        raise AssertionError(schema["info"])
    if draft["info"]["version"] != schema["info"]["version"]:
        raise AssertionError((draft["info"], schema["info"]))
    if set(draft["paths"]) != set(schema["paths"]):
        raise AssertionError((set(draft["paths"]), set(schema["paths"])))
    if traversal.status_code != 404 or generic.status_code != 404:
        raise AssertionError((traversal.status_code, generic.status_code))
    if with_query.json()["meta"]["sourceId"] != "candidates.ranked":
        raise AssertionError(with_query.json())

    serialized = json.dumps(schema).lower()
    for forbidden in ("reconciliation", "risk_guard", "ai_chat", "{path}", "{source_id}"):
        if forbidden in serialized:
            raise AssertionError(f"unexpected OpenAPI surface: {forbidden}")
    for route, path_item in schema["paths"].items():
        operation = path_item.get("get") or path_item.get("post")
        if operation is None:
            raise AssertionError((route, path_item))
        if route == "/healthz":
            continue
        responses = operation["responses"]
        if "application/json" not in responses["200"]["content"]:
            raise AssertionError((route, responses["200"]))
        if "Cache-Control" not in responses["200"].get("headers", {}):
            raise AssertionError((route, responses["200"]))
        if "application/problem+json" not in responses["500"]["content"]:
            raise AssertionError((route, responses["500"]))

    iv_operation = schema["paths"]["/api/v1/options/iv-history/{ticker}"]["get"]
    if iv_operation.get("operationId") != "getIvHistory":
        raise AssertionError(iv_operation)
    parameters = iv_operation.get("parameters", [])
    if len(parameters) != 1:
        raise AssertionError(parameters)
    ticker_parameter = parameters[0]
    if (
        ticker_parameter.get("name") != "ticker"
        or ticker_parameter.get("in") != "path"
        or ticker_parameter.get("required") is not True
    ):
        raise AssertionError(ticker_parameter)
    ticker_input = ticker_parameter.get("schema", {})
    if ticker_input.get("minLength") != 1 or ticker_input.get("maxLength") != 15:
        raise AssertionError(ticker_input)
    if ticker_input.get("pattern") != r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$":
        raise AssertionError(ticker_input)
    validation_response = iv_operation["responses"].get("422", {})
    if "application/problem+json" not in validation_response.get("content", {}):
        raise AssertionError(validation_response)
    if "Cache-Control" not in validation_response.get("headers", {}):
        raise AssertionError(validation_response)

    static_iv = draft["paths"]["/api/v1/options/iv-history/{ticker}"]["get"]
    if static_iv.get("operationId") != "getIvHistory":
        raise AssertionError(static_iv)
    static_parameter = static_iv["parameters"][0]["schema"]
    for key in ("minLength", "maxLength", "pattern"):
        if static_parameter.get(key) != ticker_input.get(key):
            raise AssertionError((key, static_parameter, ticker_input))
    expected_static_responses = {
        "200": {"$ref": "#/components/responses/IvHistoryResponse"},
        "422": {"$ref": "#/components/responses/ValidationProblem"},
        "500": {"$ref": "#/components/responses/InternalProblem"},
    }
    if static_iv["responses"] != expected_static_responses:
        raise AssertionError(static_iv["responses"])

    fund_operation = schema["paths"]["/api/v1/institutions/funds"]["get"]
    if fund_operation.get("operationId") != "getInstitutionFunds":
        raise AssertionError(fund_operation)
    if fund_operation.get("parameters") not in (None, []):
        raise AssertionError(fund_operation.get("parameters"))
    if set(fund_operation["responses"]) != {"200", "500"}:
        raise AssertionError(fund_operation["responses"])
    static_funds = draft["paths"]["/api/v1/institutions/funds"]["get"]
    if static_funds.get("operationId") != "getInstitutionFunds":
        raise AssertionError(static_funds)
    if static_funds.get("parameters") not in (None, []):
        raise AssertionError(static_funds.get("parameters"))
    if static_funds["responses"] != {
        "200": {"$ref": "#/components/responses/FundCatalogResponse"},
        "500": {"$ref": "#/components/responses/InternalProblem"},
    }:
        raise AssertionError(static_funds["responses"])

    ai_operation = schema["paths"]["/api/v1/system/ai-updates"]["get"]
    if ai_operation.get("operationId") != "getAiUpdates":
        raise AssertionError(ai_operation)
    if ai_operation.get("tags") != ["System"]:
        raise AssertionError(ai_operation.get("tags"))
    if ai_operation.get("parameters") not in (None, []):
        raise AssertionError(ai_operation.get("parameters"))
    if set(ai_operation["responses"]) != {"200", "500"}:
        raise AssertionError(ai_operation["responses"])
    static_ai = draft["paths"]["/api/v1/system/ai-updates"]["get"]
    if static_ai.get("operationId") != "getAiUpdates":
        raise AssertionError(static_ai)
    if static_ai.get("tags") != ["System"]:
        raise AssertionError(static_ai.get("tags"))
    if static_ai.get("parameters") not in (None, []):
        raise AssertionError(static_ai.get("parameters"))
    if static_ai["responses"] != {
        "200": {"$ref": "#/components/responses/AiUpdatesResponse"},
        "500": {"$ref": "#/components/responses/InternalProblem"},
    }:
        raise AssertionError(static_ai["responses"])

    schedules_operation = schema["paths"]["/api/v1/system/schedules"]["get"]
    if schedules_operation.get("operationId") != "getSchedules":
        raise AssertionError(schedules_operation)
    if schedules_operation.get("tags") != ["System"]:
        raise AssertionError(schedules_operation.get("tags"))
    if schedules_operation.get("parameters") not in (None, []):
        raise AssertionError(schedules_operation.get("parameters"))
    if set(schedules_operation["responses"]) != {"200", "500"}:
        raise AssertionError(schedules_operation["responses"])
    static_schedules = draft["paths"]["/api/v1/system/schedules"]["get"]
    if static_schedules.get("operationId") != "getSchedules":
        raise AssertionError(static_schedules)
    if static_schedules.get("tags") != ["System"]:
        raise AssertionError(static_schedules.get("tags"))
    if static_schedules.get("parameters") not in (None, []):
        raise AssertionError(static_schedules.get("parameters"))
    if static_schedules["responses"] != {
        "200": {"$ref": "#/components/responses/SchedulesResponse"},
        "500": {"$ref": "#/components/responses/InternalProblem"},
    }:
        raise AssertionError(static_schedules["responses"])
    if not any(tag.get("name") == "System" for tag in draft.get("tags", [])):
        raise AssertionError(draft.get("tags"))

    static_response_contracts = {
        "IvHistoryResponse": (
            "application/json",
            "#/components/schemas/IvHistoryEnvelope",
        ),
        "ValidationProblem": (
            "application/problem+json",
            "#/components/schemas/Problem",
        ),
        "InternalProblem": (
            "application/problem+json",
            "#/components/schemas/Problem",
        ),
        "FundCatalogResponse": (
            "application/json",
            "#/components/schemas/FundCatalogEnvelope",
        ),
        "AiUpdatesResponse": (
            "application/json",
            "#/components/schemas/AiUpdatesEnvelope",
        ),
        "SchedulesResponse": (
            "application/json",
            "#/components/schemas/SchedulesEnvelope",
        ),
        "OptionsFlowFeedResponse": (
            "application/json",
            "#/components/schemas/OptionsFlowFeedEnvelope",
        ),
        "MoneyFlowResponse": (
            "application/json",
            "#/components/schemas/MoneyFlowEnvelope",
        ),
    }
    for response_name, (media_type, schema_ref) in static_response_contracts.items():
        response_contract = draft["components"]["responses"][response_name]
        cache_header = response_contract.get("headers", {}).get("Cache-Control")
        if cache_header != {"$ref": "#/components/headers/NoStore"}:
            raise AssertionError((response_name, response_contract))
        content = response_contract.get("content", {})
        if set(content) != {media_type}:
            raise AssertionError((response_name, content))
        if content[media_type].get("schema") != {"$ref": schema_ref}:
            raise AssertionError((response_name, content[media_type]))

    static_iv_envelope = draft["components"]["schemas"]["IvHistoryEnvelope"]
    if static_iv_envelope.get("oneOf") != [
        {"$ref": "#/components/schemas/AvailableIvHistory"},
        {"$ref": "#/components/schemas/UnavailableArtifact"},
    ]:
        raise AssertionError(static_iv_envelope)
    static_available_iv = draft["components"]["schemas"]["AvailableIvHistory"]
    if static_available_iv.get("allOf") != [
        {"$ref": "#/components/schemas/AvailableArtifactBase"},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"$ref": "#/components/schemas/IvHistoryData"}
            },
        },
    ]:
        raise AssertionError(static_available_iv)

    static_fund_envelope = draft["components"]["schemas"]["FundCatalogEnvelope"]
    if static_fund_envelope.get("oneOf") != [
        {"$ref": "#/components/schemas/AvailableFundCatalog"},
        {"$ref": "#/components/schemas/UnavailableArtifact"},
    ]:
        raise AssertionError(static_fund_envelope)
    static_available_funds = draft["components"]["schemas"]["AvailableFundCatalog"]
    if static_available_funds.get("allOf") != [
        {"$ref": "#/components/schemas/AvailableArtifactBase"},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"$ref": "#/components/schemas/FundCatalogData"}
            },
        },
    ]:
        raise AssertionError(static_available_funds)

    static_ai_envelope = draft["components"]["schemas"]["AiUpdatesEnvelope"]
    if static_ai_envelope.get("oneOf") != [
        {"$ref": "#/components/schemas/AvailableAiUpdates"},
        {"$ref": "#/components/schemas/UnavailableArtifact"},
    ]:
        raise AssertionError(static_ai_envelope)
    static_available_ai = draft["components"]["schemas"]["AvailableAiUpdates"]
    if static_available_ai.get("unevaluatedProperties") is not False:
        raise AssertionError(static_available_ai)
    if static_available_ai.get("allOf") != [
        {"$ref": "#/components/schemas/AvailableArtifactBase"},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"$ref": "#/components/schemas/AiUpdatesData"}
            },
        },
    ]:
        raise AssertionError(static_available_ai)

    static_schedules_envelope = draft["components"]["schemas"]["SchedulesEnvelope"]
    if static_schedules_envelope.get("oneOf") != [
        {"$ref": "#/components/schemas/AvailableSchedules"},
        {"$ref": "#/components/schemas/UnavailableArtifact"},
    ]:
        raise AssertionError(static_schedules_envelope)
    static_available_schedules = draft["components"]["schemas"]["AvailableSchedules"]
    if static_available_schedules.get("unevaluatedProperties") is not False:
        raise AssertionError(static_available_schedules)
    if static_available_schedules.get("allOf") != [
        {"$ref": "#/components/schemas/AvailableArtifactBase"},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"$ref": "#/components/schemas/SchedulesData"}
            },
        },
    ]:
        raise AssertionError(static_available_schedules)

    generated_ai_response = schema["paths"]["/api/v1/system/ai-updates"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    generated_ai_available_refs = [
        branch["$ref"]
        for branch in generated_ai_response.get("oneOf", [])
        if branch.get("$ref") != "#/components/schemas/ArtifactUnavailable"
    ]
    if len(generated_ai_available_refs) != 1:
        raise AssertionError(generated_ai_response)
    generated_available_ai = schema["components"]["schemas"][
        generated_ai_available_refs[0].rsplit("/", 1)[-1]
    ]
    if generated_available_ai.get("additionalProperties") is not False:
        raise AssertionError(generated_available_ai)

    generated_schedules_response = schedules_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    generated_schedules_available_refs = [
        branch["$ref"]
        for branch in generated_schedules_response.get("oneOf", [])
        if branch.get("$ref") != "#/components/schemas/ArtifactUnavailable"
    ]
    if len(generated_schedules_available_refs) != 1:
        raise AssertionError(generated_schedules_response)
    generated_available_schedules = schema["components"]["schemas"][
        generated_schedules_available_refs[0].rsplit("/", 1)[-1]
    ]
    if generated_available_schedules.get("additionalProperties") is not False:
        raise AssertionError(generated_available_schedules)

    components = schema["components"]["schemas"]
    if set(components["HealthResponse"].get("required", [])) != {
        "status",
        "apiVersion",
    }:
        raise AssertionError(components["HealthResponse"])
    meta = components["ArtifactMeta"]
    if set(meta.get("required", [])) != {"sourceId", "asOf", "generatedAt"}:
        raise AssertionError(meta)
    if set(meta["properties"]) != {"sourceId", "asOf", "generatedAt"}:
        raise AssertionError(meta["properties"])

    unavailable = components["ArtifactUnavailable"]
    envelope_fields = {"available", "reason", "data", "meta"}
    if set(unavailable.get("required", [])) != envelope_fields:
        raise AssertionError(unavailable)
    if unavailable["properties"]["data"].get("type") != "null":
        raise AssertionError(unavailable["properties"]["data"])

    data_contracts = {
        "/api/v1/candidates/ranked": (
            "RankedCandidatesData",
            {"ranked_candidates"},
            "ranked_candidates",
        ),
        "/api/v1/candidates/scored": (
            "ScoredCandidatesData",
            {"all_scored"},
            "all_scored",
        ),
        "/api/v1/candidates/ranked/feed": (
            "RankedCandidatesFeedData",
            {"scan_date", "generated_at", "candidates"},
            None,
        ),
        "/api/v1/candidates/scored/feed": (
            "ScoredCandidatesFeedData",
            {"scan_date", "candidates"},
            None,
        ),
        "/api/v1/candidates/scored/screener": (
            "ScoredCandidatesScreenerData",
            {
                "scan_date",
                "needs_layer2_count",
                "watchlist_count",
                "regime_context",
                "candidates",
            },
            None,
        ),
        "/api/v1/crypto/universe": (
            "CryptoUniverseData",
            set(CRYPTO_UNIVERSE_FIELDS),
            None,
        ),
        "/api/v1/signals/options-flow/latest": (
            "OptionsFlowData",
            {"signals"},
            "signals",
        ),
        "/api/v1/signals/options-flow/feed": (
            "OptionsFlowFeedData",
            set(OPTIONS_FLOW_FEED_FIELDS),
            None,
        ),
        "/api/v1/signals/reversal-radar/latest": (
            "ReversalRadarData",
            {
                "as_of_date",
                "generated_at",
                "lane_id",
                "universe",
                "match_count",
                "candidates",
            },
            None,
        ),
        "/api/v1/signals/reversal-radar/validation": (
            "ReversalRadarValidationData",
            {
                "entries_accumulated",
                "min_resolved_across_tiers",
                "min_resolved_for_verdict",
                "verdict",
                "by_tier",
            },
            None,
        ),
        "/api/v1/signals/oversold-reversal/latest": (
            "OversoldReversalData",
            {
                "as_of_date",
                "generated_at",
                "lane_id",
                "universe",
                "runway_independent",
                "match_count",
                "scanned",
                "definition",
                "validation",
                "validation_caveats",
                "candidates",
                "note",
            },
            None,
        ),
        "/api/v1/signals/oversold-reversal/validation": (
            "OversoldReversalValidationData",
            {
                "entries_accumulated",
                "min_resolved_across_tiers",
                "min_resolved_for_verdict",
                "verdict",
                "by_tier",
            },
            None,
        ),
        "/api/v1/market-context/market-thesis/latest": (
            "MarketThesisData",
            {
                "as_of",
                "generated_at",
                "direction",
                "bucket",
                "support_class",
                "manifest_status",
                "regime",
                "vix_bucket",
                "rationale",
                "label",
            },
            None,
        ),
        "/api/v1/market-context/market-thesis/validation": (
            "MarketThesisValidationData",
            {
                "validation_status",
                "resolved",
                "matured",
                "min_resolved_for_verdict",
                "reject_count",
                "invalid_count",
                "by_key",
            },
            None,
        ),
        "/api/v1/market-context/market-thesis/regime-history": (
            "MarketThesisRegimeHistoryData",
            {"regime_summary"},
            None,
        ),
        "/api/v1/reports/daily-summary/latest": (
            "DailySummaryData",
            {"as_of_date", "regime_summary", "candidates"},
            None,
        ),
        "/api/v1/market-context/money-flow/latest": (
            "MoneyFlowData",
            {
                "as_of_date",
                "generated_at",
                "source",
                "publishable",
                "coverage",
                "rows",
            },
            None,
        ),
        "/api/v1/market-context/sector-rotation/latest": (
            "SectorRotationData",
            {"as_of", "benchmark", "sectors"},
            None,
        ),
        "/api/v1/options/iv-history/{ticker}": (
            "IvHistoryData",
            {"ticker", "series"},
            None,
        ),
        "/api/v1/institutions/funds": (
            "FundCatalogData",
            {"funds"},
            None,
        ),
        "/api/v1/system/ai-updates": (
            "AiUpdatesData",
            {"updates"},
            None,
        ),
        "/api/v1/system/schedules": (
            "SchedulesData",
            {"schedules"},
            None,
        ),
    }
    for route, (data_name, required_fields, list_anchor) in data_contracts.items():
        response_schema = schema["paths"][route]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        branches = response_schema.get("oneOf", [])
        refs = [branch.get("$ref", "") for branch in branches]
        if "#/components/schemas/ArtifactUnavailable" not in refs:
            raise AssertionError((route, response_schema))
        available_refs = [ref for ref in refs if ref != "#/components/schemas/ArtifactUnavailable"]
        if len(available_refs) != 1:
            raise AssertionError((route, response_schema))
        discriminator = response_schema.get("discriminator", {})
        if discriminator.get("propertyName") != "reason":
            raise AssertionError((route, discriminator))
        if set(discriminator.get("mapping", {})) != {
            "ok",
            "missing",
            "invalid_json",
            "invalid_shape",
            "unreadable",
        }:
            raise AssertionError((route, discriminator))
        available = components[available_refs[0].rsplit("/", 1)[-1]]
        if set(available.get("required", [])) != envelope_fields:
            raise AssertionError((route, available))
        if available["properties"]["data"].get("$ref") != (
            f"#/components/schemas/{data_name}"
        ):
            raise AssertionError((route, available["properties"]["data"]))

        data_schema = components[data_name]
        if set(data_schema.get("required", [])) != required_fields:
            raise AssertionError((route, data_schema))
        if list_anchor is not None:
            anchor_schema = data_schema["properties"][list_anchor]
            if anchor_schema.get("type") != "array":
                raise AssertionError((route, anchor_schema))
            if anchor_schema.get("items", {}).get("type") != "object":
                raise AssertionError((route, anchor_schema))

    strict_successor_shapes = {
        "MarketThesisValidationData": {
            "validation_status",
            "resolved",
            "matured",
            "min_resolved_for_verdict",
            "reject_count",
            "invalid_count",
            "by_key",
        },
        "MarketThesisValidationRow": {
            "counted_N",
            "hits",
            "hit_rate",
            "wilson90",
            "verdict",
        },
        "MarketThesisRegimeHistoryData": {"regime_summary"},
        "MarketThesisRegimeSummary": {"rally", "correction", "range"},
        "MarketThesisRegime": {"days", "fwd_20d", "fwd_40d", "fwd_60d"},
        "MarketThesisRegimeWindow": {"mean", "up_rate", "p10", "worst"},
        "MarketThesisData": {
            "as_of",
            "generated_at",
            "direction",
            "bucket",
            "support_class",
            "manifest_status",
            "regime",
            "vix_bucket",
            "rationale",
            "label",
        },
        "MarketThesisRationale": {
            "analog",
            "manifest_missing",
            "manifest_stale",
            "manifest_events",
        },
        "MarketThesisAnalog": set(),
        "MarketThesisEvent": {
            "type",
            "source_id",
            "present",
            "fresh",
            "stale_reason",
            "value",
            "delta_1d",
            "last_rate",
            "next_meeting_at",
        },
        "MoneyFlowData": {
            "as_of_date",
            "generated_at",
            "source",
            "publishable",
            "coverage",
            "rows",
        },
        "MoneyFlowCoverage": {
            "requested",
            "resolved",
            "unavailable",
            "coverage_ratio",
            "min_coverage",
        },
        "MoneyFlowRow": {
            "ticker",
            "date",
            "main_net",
            "main_pct",
            "small_net",
            "source",
        },
        "ReversalRadarData": {
            "as_of_date",
            "generated_at",
            "lane_id",
            "universe",
            "match_count",
            "candidates",
        },
        "ReversalRadarCandidateRef": {"ticker"},
        "OversoldReversalData": {
            "as_of_date",
            "generated_at",
            "lane_id",
            "universe",
            "runway_independent",
            "match_count",
            "scanned",
            "definition",
            "validation",
            "validation_caveats",
            "candidates",
            "note",
        },
        "OversoldReversalValidation": {
            "pct_lift",
            "atr_neutral_lift",
            "support",
        },
        "OversoldReversalCandidate": {
            "ticker",
            "last_price",
            "rsi14",
            "bb_width_pct",
            "pct_vs_ma200",
            "pct_from_52w_high",
            "avg_dollar_vol_m",
        },
        "RankedCandidatesFeedData": {
            "scan_date",
            "generated_at",
            "candidates",
        },
        "RankedCandidateFeedItem": {
            "ticker",
            "rank_score",
            "last_price",
            "rank_bucket",
            "ret_5d",
            "ret_20d",
            "score_components",
            "options_tradability",
            "warnings",
        },
        "RankedCandidateScoreComponents": {
            "technical_trend",
            "momentum_strength",
            "launch_signal",
            "liquidity_tradability",
            "overheat_risk_control",
        },
        "RankedCandidateOptionsTradability": {
            "status",
            "iv_percentile",
            "spread_pct",
            "flow_score",
            "warnings",
        },
        "ScoredCandidatesFeedData": {"scan_date", "candidates"},
        "ScoredCandidateFeedItem": {
            "ticker",
            "verdict",
            "composite_score",
            "regime_adjusted_score",
            "scores",
            "data_missing",
            "due_diligence_required",
            "key_signals",
            "key_risks",
            "suggested_entry_zone",
        },
        "ScoredCandidateScores": {
            "technical",
            "catalyst",
            "sentiment",
            "institutional",
            "sector_market",
            "options_flow",
            "analyst",
        },
        "ScoredCandidatesScreenerData": {
            "scan_date",
            "needs_layer2_count",
            "watchlist_count",
            "regime_context",
            "candidates",
        },
        "ScoredScreenerRegimeContext": {
            "spy_vs_50dma",
            "spy_vs_200dma",
            "vix_level",
            "vix_regime",
            "global_score_multiplier",
            "active_themes",
            "regime_warnings",
        },
        "ScoredScreenerCandidateItem": {
            "ticker",
            "verdict",
            "regime_adjusted_score",
            "scores",
            "key_signals",
            "key_risks",
            "suggested_entry_zone",
            "suggested_stop",
            "suggested_size_pct",
            "anti_example_warning",
            "data_missing",
            "technical_breakdown",
        },
        "ScoredScreenerTechnicalBreakdown": {
            "pattern_type",
            "macd_state",
        },
    }
    static_components = draft["components"]["schemas"]
    for label, schemas in (
        ("generated", components),
        ("static", static_components),
    ):
        for data_name, required_fields in strict_successor_shapes.items():
            data_schema = schemas[data_name]
            if data_schema.get("additionalProperties") is not False:
                raise AssertionError((label, data_name, data_schema))
            expected_properties = required_fields
            if data_name == "MarketThesisAnalog":
                expected_properties = {
                    "status",
                    "resolved",
                    "mean",
                    "up_rate",
                    "ci90",
                    "p10",
                    "worst_mdd",
                }
            if set(data_schema.get("properties", {})) != expected_properties:
                raise AssertionError((label, data_name, data_schema))
            if set(data_schema.get("required", [])) != required_fields:
                raise AssertionError((label, data_name, data_schema))

        if schemas["ReversalRadarData"]["properties"]["candidates"].get(
            "maxItems"
        ) != 500:
            raise AssertionError((label, schemas["ReversalRadarData"]))
        oversold_data = schemas["OversoldReversalData"]
        if oversold_data["properties"]["candidates"].get("maxItems") != 2_000:
            raise AssertionError((label, oversold_data))
        caveats = oversold_data["properties"]["validation_caveats"]
        if caveats.get("maxItems") != 20 or caveats.get("items", {}).get(
            "maxLength"
        ) != 1_000:
            raise AssertionError((label, caveats))
        market_data = schemas["MarketThesisData"]
        generated_at = market_data["properties"]["generated_at"]
        if (
            generated_at.get("format") != "date-time"
            or generated_at.get("minLength") != 20
            or generated_at.get("maxLength") != 32
        ):
            raise AssertionError((label, generated_at))
        if market_data["properties"]["label"].get("maxLength") != 200:
            raise AssertionError((label, market_data["properties"]["label"]))
        rationale = schemas["MarketThesisRationale"]
        for field in ("manifest_missing", "manifest_stale", "manifest_events"):
            if rationale["properties"][field].get("maxItems") != 5:
                raise AssertionError((label, field, rationale["properties"][field]))

    iv_data = components["IvHistoryData"]
    if iv_data.get("additionalProperties") is not False:
        raise AssertionError(iv_data)
    ticker_output = iv_data["properties"]["ticker"]
    if ticker_output.get("maxLength") != 15:
        raise AssertionError(ticker_output)
    if ticker_output.get("pattern") != r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$":
        raise AssertionError(ticker_output)
    series = iv_data["properties"]["series"]
    if series.get("propertyNames", {}).get("format") != "date":
        raise AssertionError(series)
    values = series.get("additionalProperties", {})
    if values.get("exclusiveMinimum") != 0 or values.get("exclusiveMaximum") != 10:
        raise AssertionError(values)

    static_iv_data = draft["components"]["schemas"]["IvHistoryData"]
    if static_iv_data.get("additionalProperties") is not False:
        raise AssertionError(static_iv_data)
    if static_iv_data["properties"]["ticker"].get("maxLength") != 15:
        raise AssertionError(static_iv_data["properties"]["ticker"])
    if static_iv_data["properties"]["ticker"].get("pattern") != ticker_output.get("pattern"):
        raise AssertionError((static_iv_data, iv_data))
    static_series = static_iv_data["properties"]["series"]
    if static_series.get("propertyNames", {}).get("format") != "date":
        raise AssertionError(static_series)
    static_values = static_series.get("additionalProperties", {})
    if static_values.get("exclusiveMinimum") != 0 or static_values.get("exclusiveMaximum") != 10:
        raise AssertionError(static_values)

    fund_data = components["FundCatalogData"]
    if fund_data.get("additionalProperties") is not False:
        raise AssertionError(fund_data)
    if set(fund_data.get("required", [])) != {"funds"}:
        raise AssertionError(fund_data)
    if set(fund_data.get("properties", {})) != {"funds"}:
        raise AssertionError(fund_data)
    fund_map = fund_data["properties"]["funds"]
    if fund_map.get("maxProperties") != 100:
        raise AssertionError(fund_map)
    expected_property_names = {
        "type": "string",
        "minLength": 1,
        "maxLength": 120,
        "pattern": r"^\S(?:.*\S)?$",
    }
    if fund_map.get("propertyNames") != expected_property_names:
        raise AssertionError(fund_map)
    if fund_map.get("additionalProperties") != {
        "$ref": "#/components/schemas/FundCatalogEntry"
    }:
        raise AssertionError(fund_map)

    fund_entry = components["FundCatalogEntry"]
    if fund_entry.get("additionalProperties") is not False:
        raise AssertionError(fund_entry)
    if set(fund_entry.get("required", [])) != {"cik", "note"}:
        raise AssertionError(fund_entry)
    if set(fund_entry.get("properties", {})) != {"cik", "note"}:
        raise AssertionError(fund_entry)
    cik = fund_entry["properties"]["cik"]
    if (
        cik.get("minLength") != 1
        or cik.get("maxLength") != 10
        or cik.get("pattern") != r"^0*[1-9][0-9]*$"
    ):
        raise AssertionError(cik)
    if fund_entry["properties"]["note"].get("maxLength") != 200:
        raise AssertionError(fund_entry["properties"]["note"])

    static_fund_data = draft["components"]["schemas"]["FundCatalogData"]
    if static_fund_data.get("additionalProperties") is not False:
        raise AssertionError(static_fund_data)
    if set(static_fund_data.get("properties", {})) != {"funds"}:
        raise AssertionError(static_fund_data)
    static_fund_map = static_fund_data["properties"]["funds"]
    if static_fund_map.get("maxProperties") != 100:
        raise AssertionError(static_fund_map)
    if static_fund_map.get("propertyNames") != expected_property_names:
        raise AssertionError(static_fund_map)
    if static_fund_map.get("additionalProperties") != {
        "$ref": "#/components/schemas/FundCatalogEntry"
    }:
        raise AssertionError(static_fund_map)
    static_fund_entry = draft["components"]["schemas"]["FundCatalogEntry"]
    if static_fund_entry.get("additionalProperties") is not False:
        raise AssertionError(static_fund_entry)
    if set(static_fund_entry.get("properties", {})) != {"cik", "note"}:
        raise AssertionError(static_fund_entry)
    static_cik = static_fund_entry["properties"]["cik"]
    if (
        static_cik.get("minLength") != 1
        or static_cik.get("maxLength") != 10
        or static_cik.get("pattern") != r"^0*[1-9][0-9]*$"
    ):
        raise AssertionError(static_cik)
    if static_fund_entry["properties"]["note"].get("maxLength") != 200:
        raise AssertionError(static_fund_entry["properties"]["note"])

    fund_example = draft["components"]["responses"]["FundCatalogResponse"]["content"][
        "application/json"
    ]["example"]
    if "_note" in json.dumps(fund_example) or set(fund_example["data"]) != {"funds"}:
        raise AssertionError(fund_example)

    expected_link_any_of = [
        {"const": ""},
        {
            "type": "string",
            "format": "iri",
            "pattern": AI_UPDATES_LINK_PATTERN,
        },
    ]
    for label, schemas in (
        ("generated", components),
        ("static", draft["components"]["schemas"]),
    ):
        ai_data = schemas["AiUpdatesData"]
        if ai_data.get("additionalProperties") is not False:
            raise AssertionError((label, ai_data))
        if set(ai_data.get("required", [])) != {"updates"}:
            raise AssertionError((label, ai_data))
        if set(ai_data.get("properties", {})) != {"updates"}:
            raise AssertionError((label, ai_data))
        updates = ai_data["properties"]["updates"]
        if updates.get("type") != "array" or updates.get("maxItems") != 200:
            raise AssertionError((label, updates))
        if updates.get("items") != {"$ref": "#/components/schemas/AiUpdateItem"}:
            raise AssertionError((label, updates))

        item = schemas["AiUpdateItem"]
        item_fields = {"date", "title", "summary", "link", "tags"}
        if item.get("additionalProperties") is not False:
            raise AssertionError((label, item))
        if set(item.get("required", [])) != item_fields:
            raise AssertionError((label, item))
        if set(item.get("properties", {})) != item_fields:
            raise AssertionError((label, item))
        date_schema = item["properties"]["date"]
        if date_schema.get("type") != "string":
            raise AssertionError((label, date_schema))
        if date_schema.get("format") != "date" or date_schema.get("pattern") != (
            AI_UPDATES_DATE_PATTERN
        ):
            raise AssertionError((label, date_schema))
        title = item["properties"]["title"]
        if title.get("minLength") != 1 or title.get("maxLength") != 200:
            raise AssertionError((label, title))
        summary = item["properties"]["summary"]
        if summary.get("minLength") != 1 or summary.get("maxLength") != 2000:
            raise AssertionError((label, summary))
        link = item["properties"]["link"]
        if link.get("type") != "string" or link.get("maxLength") != 2048:
            raise AssertionError((label, link))
        if link.get("anyOf") != expected_link_any_of:
            raise AssertionError((label, link))
        description = link.get("description", "").lower()
        if not all(
            term in description
            for term in ("authority", "hostname", "userinfo", "port", "stricter")
        ):
            raise AssertionError((label, description))
        tags = item["properties"]["tags"]
        if tags.get("type") != "array" or tags.get("maxItems") != 20:
            raise AssertionError((label, tags))
        if tags.get("uniqueItems") is not True:
            raise AssertionError((label, tags))
        tag = tags.get("items", {})
        if (
            tag.get("type") != "string"
            or tag.get("minLength") != 1
            or tag.get("maxLength") != 50
            or tag.get("pattern") != AI_UPDATES_TAG_PATTERN
        ):
            raise AssertionError((label, tag))

    generated_ai_content = ai_operation["responses"]["200"]["content"][
        "application/json"
    ]
    static_ai_content = draft["components"]["responses"]["AiUpdatesResponse"][
        "content"
    ]["application/json"]

    def example_values(content: dict[str, object]) -> list[object]:
        examples = content.get("examples", {})
        if not isinstance(examples, dict):
            return []
        return [
            example.get("value") if isinstance(example, dict) else example
            for example in examples.values()
        ]

    generated_examples = example_values(generated_ai_content)
    static_examples = example_values(static_ai_content)
    if len(generated_examples) != 2 or {
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        for value in generated_examples
    } != {
        json.dumps(value, ensure_ascii=False, sort_keys=True) for value in static_examples
    }:
        raise AssertionError((generated_examples, static_examples))
    if any("_note" in json.dumps(value, ensure_ascii=False) for value in static_examples):
        raise AssertionError(static_examples)
    example_updates = [
        value["data"]["updates"]
        for value in static_examples
        if isinstance(value, dict) and value.get("available") is True
    ]
    if not any(updates for updates in example_updates) or [] not in example_updates:
        raise AssertionError(static_examples)

    for label, schemas in (
        ("generated", components),
        ("static", draft["components"]["schemas"]),
    ):
        schedules_data = schemas["SchedulesData"]
        if schedules_data.get("additionalProperties") is not False:
            raise AssertionError((label, schedules_data))
        if set(schedules_data.get("required", [])) != {"schedules"}:
            raise AssertionError((label, schedules_data))
        if set(schedules_data.get("properties", {})) != {"schedules"}:
            raise AssertionError((label, schedules_data))
        schedules = schedules_data["properties"]["schedules"]
        if schedules.get("type") != "array" or schedules.get("maxItems") != 100:
            raise AssertionError((label, schedules))
        if schedules.get("items") != {"$ref": "#/components/schemas/ScheduleEntry"}:
            raise AssertionError((label, schedules))
        if "uniqueItems" in schedules:
            raise AssertionError((label, schedules))
        uniqueness_description = schedules.get("description", "").lower()
        if not all(
            term in uniqueness_description for term in ("unique", "runtime", "json schema")
        ):
            raise AssertionError((label, uniqueness_description))

        schedule_entry = schemas["ScheduleEntry"]
        if schedule_entry.get("additionalProperties") is not False:
            raise AssertionError((label, schedule_entry))
        if set(schedule_entry.get("required", [])) != set(SCHEDULE_FIELDS):
            raise AssertionError((label, schedule_entry))
        if set(schedule_entry.get("properties", {})) != set(SCHEDULE_FIELDS):
            raise AssertionError((label, schedule_entry))
        properties = schedule_entry["properties"]
        for field in ("id", "result_type"):
            identifier = properties[field]
            if (
                identifier.get("type") != "string"
                or identifier.get("minLength") != 1
                or identifier.get("maxLength") != 64
                or identifier.get("pattern") != SCHEDULE_IDENTIFIER_PATTERN
            ):
                raise AssertionError((label, field, identifier))
        for field, maximum in (("name", 100), ("category", 50), ("cron", 100)):
            required_text = properties[field]
            if (
                required_text.get("type") != "string"
                or required_text.get("minLength") != 1
                or required_text.get("maxLength") != maximum
                or required_text.get("pattern") != SCHEDULE_REQUIRED_TEXT_PATTERN
            ):
                raise AssertionError((label, field, required_text))
        for field, maximum in (("cron_note", 500), ("description", 2000)):
            optional_text = properties[field]
            if (
                optional_text.get("type") != "string"
                or optional_text.get("maxLength") != maximum
                or optional_text.get("pattern") != SCHEDULE_OPTIONAL_TEXT_PATTERN
                or "minLength" in optional_text
            ):
                raise AssertionError((label, field, optional_text))
        if "opaque" not in properties["cron"].get("description", "").lower():
            raise AssertionError((label, properties["cron"]))
        result_description = properties["result_type"].get("description", "").lower()
        if "opaque" not in result_description or "never dereferences" not in result_description:
            raise AssertionError((label, result_description))

    generated_schedules_content = schedules_operation["responses"]["200"]["content"][
        "application/json"
    ]
    static_schedules_content = draft["components"]["responses"]["SchedulesResponse"][
        "content"
    ]["application/json"]
    generated_schedules_examples = _example_values(generated_schedules_content)
    static_schedules_examples = _example_values(static_schedules_content)
    if (
        len(generated_schedules_examples) != 2
        or len(static_schedules_examples) != 2
        or {
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            for value in generated_schedules_examples
        }
        != {
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            for value in static_schedules_examples
        }
    ):
        raise AssertionError(
            (generated_schedules_examples, static_schedules_examples)
        )
    for example in generated_schedules_examples + static_schedules_examples:
        if not isinstance(example, dict):
            raise AssertionError(example)
        meta = example.get("meta")
        if not isinstance(meta, dict) or set(meta) != {
            "sourceId",
            "asOf",
            "generatedAt",
        }:
            raise AssertionError(example)
        if meta["asOf"] is not None or meta["generatedAt"] is not None:
            raise AssertionError(meta)
        if meta["sourceId"] != "system.schedules":
            raise AssertionError(meta)
        data = example.get("data")
        if not isinstance(data, dict) or "_note" in data:
            raise AssertionError(example)
    available_schedule_examples = [
        value
        for value in static_schedules_examples
        if isinstance(value, dict) and value.get("available") is True
    ]
    schedule_lists = [value["data"]["schedules"] for value in available_schedule_examples]
    if not any(schedule_lists) or [] not in schedule_lists:
        raise AssertionError(static_schedules_examples)

    for label, document, response_schema, examples in (
        (
            "generated",
            schema,
            generated_schedules_response,
            generated_schedules_examples,
        ),
        (
            "static",
            draft,
            {"$ref": "#/components/schemas/SchedulesEnvelope"},
            static_schedules_examples,
        ),
    ):
        validator = _schema_validator(document, response_schema)
        for example in examples:
            validator.validate(example)
        available_example = next(
            example
            for example in examples
            if isinstance(example, dict)
            and example.get("available") is True
            and example["data"]["schedules"]
        )
        invalid_examples = []
        extra_envelope = deepcopy(available_example)
        extra_envelope["secret"] = "envelope-secret"
        invalid_examples.append(extra_envelope)
        extra_data = deepcopy(available_example)
        extra_data["data"]["secret"] = "data-secret"
        invalid_examples.append(extra_data)
        extra_item = deepcopy(available_example)
        extra_item["data"]["schedules"][0]["secret"] = "item-secret"
        invalid_examples.append(extra_item)
        missing_item_field = deepcopy(available_example)
        del missing_item_field["data"]["schedules"][0]["result_type"]
        invalid_examples.append(missing_item_field)
        for invalid_example in invalid_examples:
            try:
                validator.validate(invalid_example)
            except JsonSchemaValidationError:
                continue
            raise AssertionError((label, invalid_example))

    problem = schema["paths"][SOURCE_PATHS["candidates.ranked"]]["get"][
        "responses"
    ]["500"]["content"]["application/problem+json"]["schema"]
    if set(problem.get("required", [])) != {"type", "title", "status"}:
        raise AssertionError(problem)
    if problem["properties"]["type"].get("format") != "uri-reference":
        raise AssertionError(problem["properties"]["type"])
    if problem["properties"]["detail"].get("type") != "string":
        raise AssertionError(problem["properties"]["detail"])
    if problem["properties"]["instance"].get("format") != "uri-reference":
        raise AssertionError(problem["properties"]["instance"])


def main() -> None:
    tests = [
        test_registry_is_explicit_and_typed,
        test_available_envelope_preserves_source_fields,
        test_scored_screener_projection_is_closed_bucket_only_and_ordered,
        test_scored_screener_invalid_sources_fail_soft_and_recover,
        test_scored_screener_http_route_is_additive_and_exact,
        test_expected_file_states_return_unavailable_envelopes,
        test_wrong_anchor_shapes_are_invalid_shape,
        test_market_thesis_requires_strict_projected_fields,
        test_market_thesis_resolver_orders_date_then_ready,
        test_market_thesis_resolver_is_fail_soft,
        test_selected_market_thesis_can_disappear_before_read,
        test_iv_ticker_normalization_and_spec_path_are_strict,
        test_iv_history_shape_metadata_and_public_dto_are_strict,
        test_iv_history_http_fail_soft_matrix_keeps_health_independent,
        test_iv_history_http_validation_precedes_file_selection,
        test_iv_history_recovers_and_callback_defects_are_sanitized,
        test_fund_catalog_projection_and_boundary_shape_are_strict,
        test_fund_catalog_http_fail_soft_projection_and_recovery,
        test_fund_catalog_callback_and_projection_contracts_are_sanitized,
        test_ai_updates_projection_and_valid_boundaries_are_strict,
        test_ai_updates_reject_invalid_roots_items_and_boundaries,
        test_ai_updates_date_link_and_tag_oracles_are_exact,
        test_ai_updates_http_fail_soft_recovery_order_and_metadata,
        test_ai_updates_callback_matrix_is_sanitized,
        test_ai_updates_route_retains_loopback_host_and_cors_boundaries,
        test_schedules_projection_and_boundaries_are_strict,
        test_schedules_reject_invalid_roots_items_types_and_boundaries,
        test_schedules_http_fail_soft_recovery_order_and_metadata,
        test_schedules_callback_and_projection_matrix_is_sanitized,
        test_schedules_pre_response_defect_is_sanitized_in_real_uvicorn_logs,
        test_schedules_route_is_fixed_loopback_only_and_dependency_free,
        test_options_flow_feed_projection_and_valid_boundaries_are_strict,
        test_options_flow_feed_rejects_invalid_roots_fields_and_invariants,
        test_options_flow_feed_200_201_and_positive_count_empty_semantics,
        test_options_flow_feed_http_projection_and_latest_compatibility,
        test_options_flow_feed_fail_soft_reason_mapping_and_recovery,
        test_options_flow_feed_callback_matrix_is_sanitized,
        test_options_flow_feed_is_fixed_and_dependency_free,
        test_http_routes_return_typed_available_envelopes,
        test_health_is_independent_when_every_artifact_is_missing,
        test_http_failure_matrix_is_fail_soft,
        test_http_recovers_on_the_next_request_without_negative_cache,
        test_invalid_generated_at_metadata_is_omitted_without_failing,
        test_unexpected_error_returns_sanitized_problem,
        test_loopback_boundary_and_cors_defaults,
        test_options_flow_feed_openapi_contract_is_strict_and_in_parity,
        test_openapi_and_path_surface_match_the_draft,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
