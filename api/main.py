"""Loopback FastAPI app for public artifacts and protected private reads."""

from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import stat
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Path as PathParameter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, TypeAdapter, ValidationError

from api.artifacts import (
    ARTIFACTS,
    COT_REPORTS_DIR,
    IV_HISTORY_DIR,
    KNOWLEDGE_VAULT,
    THEME_DRILL_FILE,
    THEME_TAXONOMY_FILE,
    ArtifactReadResult,
    ArtifactSpec,
    iv_history_spec,
    normalize_ticker,
    read_artifact,
    read_cot_catalog,
    read_cot_report,
    read_influencer_roster,
    read_knowledge_graph,
    read_theme_drill,
    read_theme_taxonomy,
)
from api.industry_roles import read_industry_role_review_board_snapshot
from api.models import (
    AiUpdatesData,
    ArtifactAvailable,
    ArtifactUnavailable,
    CryptoUniverseData,
    CotCatalogData,
    CotReportData,
    DailySummaryData,
    FundCatalogData,
    HealthResponse,
    IvHistoryData,
    InfluencerRosterData,
    IndustryRoleActionRequest,
    IndustryRoleApproveAction,
    IndustryRoleDeferAction,
    IndustryRoleGenerateAction,
    IndustryRoleMutationResult,
    IndustryRoleRejectAction,
    IndustryRoleReviewBoardData,
    KnowledgeGraphData,
    MarketThesisData,
    MarketThesisRegimeHistoryData,
    MarketThesisValidationData,
    MoneyFlowData,
    OptionsFlowData,
    OptionsFlowFeedData,
    OversoldReversalData,
    OversoldReversalValidationData,
    PlaybookValidationData,
    ContinuationValidationData,
    Problem,
    RankedCandidatesData,
    RankedCandidatesFeedData,
    ReversalRadarData,
    ReversalRadarValidationData,
    SchedulesData,
    ScoredCandidatesData,
    ScoredCandidatesFeedData,
    ScoredCandidatesScreenerData,
    SectorRotationData,
    SocialIntelligenceData,
    ThemeFlowAnalysisData,
    ThemeFlowData,
    ThemeDrillData,
    ThemeTaxonomyData,
)
from scripts.influencer_roster_runtime import resolve_roster_path
from scripts import industry_role_store as industry_role_store
from scripts import industry_roles as industry_role_engine


LOGGER = logging.getLogger("surge.api")
NO_STORE = "no-store"
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_REPO_ROOT = Path(__file__).resolve().parent.parent
_INDUSTRY_ROLE_TAXONOMY_FILE = _REPO_ROOT / "content" / "industry_roles.json"
_INDUSTRY_ROLE_STATE_FILE = industry_role_store.canonical_state_path(
    _REPO_ROOT / "reports"
)
_INTERNAL_API_TOKEN_ENV = "SURGE_INTERNAL_API_TOKEN"
_INTERNAL_API_TOKEN_FILE_ENV = "SURGE_INTERNAL_API_TOKEN_FILE"
_INTERNAL_API_TOKEN_MIN_LENGTH = 32
_INTERNAL_API_TOKEN_MAX_LENGTH = 256
_INTERNAL_TOKEN_UNSET = object()
_PRIVATE_MUTATION_MAX_BYTES = 64 * 1024
_INDUSTRY_ROLE_ACTION_ADAPTER = TypeAdapter(IndustryRoleActionRequest)
_REQUIRED_SOURCE_IDS = frozenset(
    {
        "candidates.ranked",
        "candidates.ranked.feed",
        "candidates.scored",
        "candidates.scored.feed",
        "candidates.scored.screener",
        "crypto.universe",
        "signals.options-flow.latest",
        "signals.options-flow.feed",
        "signals.reversal-radar.latest",
        "signals.reversal-radar.validation",
        "signals.oversold-reversal.latest",
        "signals.oversold-reversal.validation",
        "market-context.market-thesis.latest",
        "market-context.market-thesis.validation",
        "market-context.market-thesis.regime-history",
        "reports.daily-summary.latest",
        "reports.playbook-validation.latest",
        "reports.continuation-validation.latest",
        "market-context.money-flow.latest",
        "market-context.sector-rotation.latest",
        "market-context.theme-flow.latest",
        "market-context.theme-flow.analysis",
        "social.intelligence.latest",
        "institutions.funds",
        "system.ai-updates",
        "system.schedules",
    }
)

RankedEnvelope = Annotated[
    ArtifactAvailable[RankedCandidatesData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ScoredEnvelope = Annotated[
    ArtifactAvailable[ScoredCandidatesData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
RankedFeedEnvelope = Annotated[
    ArtifactAvailable[RankedCandidatesFeedData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ScoredFeedEnvelope = Annotated[
    ArtifactAvailable[ScoredCandidatesFeedData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ScoredScreenerEnvelope = Annotated[
    ArtifactAvailable[ScoredCandidatesScreenerData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
OptionsFlowEnvelope = Annotated[
    ArtifactAvailable[OptionsFlowData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
OptionsFlowFeedEnvelope = Annotated[
    ArtifactAvailable[OptionsFlowFeedData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ReversalRadarEnvelope = Annotated[
    ArtifactAvailable[ReversalRadarData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ReversalRadarValidationEnvelope = Annotated[
    ArtifactAvailable[ReversalRadarValidationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
OversoldReversalEnvelope = Annotated[
    ArtifactAvailable[OversoldReversalData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
OversoldReversalValidationEnvelope = Annotated[
    ArtifactAvailable[OversoldReversalValidationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
MarketThesisEnvelope = Annotated[
    ArtifactAvailable[MarketThesisData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
DailySummaryEnvelope = Annotated[
    ArtifactAvailable[DailySummaryData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
PlaybookValidationEnvelope = Annotated[
    ArtifactAvailable[PlaybookValidationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ContinuationValidationEnvelope = Annotated[
    ArtifactAvailable[ContinuationValidationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
CotCatalogEnvelope = Annotated[
    ArtifactAvailable[CotCatalogData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
CotDetailEnvelope = Annotated[
    ArtifactAvailable[CotReportData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
MarketThesisValidationEnvelope = Annotated[
    ArtifactAvailable[MarketThesisValidationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
MarketThesisRegimeHistoryEnvelope = Annotated[
    ArtifactAvailable[MarketThesisRegimeHistoryData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
MoneyFlowEnvelope = Annotated[
    ArtifactAvailable[MoneyFlowData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
SectorRotationEnvelope = Annotated[
    ArtifactAvailable[SectorRotationData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
IvHistoryEnvelope = Annotated[
    ArtifactAvailable[IvHistoryData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
FundCatalogEnvelope = Annotated[
    ArtifactAvailable[FundCatalogData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
AiUpdatesEnvelope = Annotated[
    ArtifactAvailable[AiUpdatesData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
SchedulesEnvelope = Annotated[
    ArtifactAvailable[SchedulesData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
CryptoUniverseEnvelope = Annotated[
    ArtifactAvailable[CryptoUniverseData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
SocialIntelligenceEnvelope = Annotated[
    ArtifactAvailable[SocialIntelligenceData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ThemeFlowEnvelope = Annotated[
    ArtifactAvailable[ThemeFlowData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ThemeFlowAnalysisEnvelope = Annotated[
    ArtifactAvailable[ThemeFlowAnalysisData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
KnowledgeGraphEnvelope = Annotated[
    ArtifactAvailable[KnowledgeGraphData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ThemeTaxonomyEnvelope = Annotated[
    ArtifactAvailable[ThemeTaxonomyData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
ThemeDrillEnvelope = Annotated[
    ArtifactAvailable[ThemeDrillData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
InfluencerRosterEnvelope = Annotated[
    ArtifactAvailable[InfluencerRosterData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
IndustryRoleReviewBoardEnvelope = Annotated[
    ArtifactAvailable[IndustryRoleReviewBoardData] | ArtifactUnavailable,
    Field(discriminator="reason"),
]
TickerPath = Annotated[
    str,
    PathParameter(
        min_length=1,
        max_length=15,
        pattern=r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$",
        description="US ticker using ASCII alphanumeric groups separated by . or -.",
    ),
]
ReportDatePath = Annotated[
    str,
    PathParameter(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Exact published COT report date in YYYY-MM-DD form.",
    ),
]


def _no_store_header_docs() -> dict[str, object]:
    return {
        "description": "Prevent retention of current artifact state.",
        "schema": {"type": "string", "const": NO_STORE},
    }


def _strong_etag_header_docs() -> dict[str, object]:
    return {
        "description": "Strong validator for the complete Industry Roles state.",
        "schema": {"type": "string", "minLength": 68, "maxLength": 96},
    }


def _industry_role_action_request_docs() -> dict[str, object]:
    models = (
        IndustryRoleGenerateAction,
        IndustryRoleApproveAction,
        IndustryRoleRejectAction,
        IndustryRoleDeferAction,
    )
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        model.model_json_schema(by_alias=True) for model in models
                    ],
                    "discriminator": {"propertyName": "action"},
                }
            }
        },
    }


def _artifact_response_docs(
    *,
    include_validation: bool = False,
) -> dict[int, dict[str, object]]:
    responses: dict[int, dict[str, object]] = {
        200: {"headers": {"Cache-Control": _no_store_header_docs()}},
        500: {
            "description": "Unexpected programming or server failure.",
            "headers": {"Cache-Control": _no_store_header_docs()},
            "content": {
                "application/problem+json": {
                    "schema": Problem.model_json_schema(mode="serialization"),
                    "example": {
                        "type": "about:blank",
                        "title": "Internal Server Error",
                        "status": 500,
                    },
                }
            },
        },
    }
    if include_validation:
        responses[422] = {
            "description": "The decoded request parameter does not satisfy its contract.",
            "headers": {"Cache-Control": _no_store_header_docs()},
            "content": {
                "application/problem+json": {
                    "schema": Problem.model_json_schema(mode="serialization"),
                    "example": {
                        "type": "about:blank",
                        "title": "Unprocessable Entity",
                        "status": 422,
                    },
                }
            },
        }
    return responses


def _fixed_public_response_docs(
    *,
    source_id: str,
    empty_data: dict[str, object],
    available_data: dict[str, object],
) -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["content"] = {
        "application/json": {
            "examples": {
                "available": {
                    "summary": "A populated fixed public projection",
                    "value": {
                        "available": True,
                        "reason": "ok",
                        "data": available_data,
                        "meta": {
                            "sourceId": source_id,
                            "asOf": None,
                            "generatedAt": None,
                        },
                    },
                },
                "empty": {
                    "summary": "A valid empty public projection",
                    "value": {
                        "available": True,
                        "reason": "ok",
                        "data": empty_data,
                        "meta": {
                            "sourceId": source_id,
                            "asOf": None,
                            "generatedAt": None,
                        },
                    },
                },
                "unavailable": {
                    "summary": "The fixed source is missing",
                    "value": {
                        "available": False,
                        "reason": "missing",
                        "data": None,
                        "meta": {
                            "sourceId": source_id,
                            "asOf": None,
                            "generatedAt": None,
                        },
                    },
                },
            }
        }
    }
    return responses


def _options_flow_feed_examples() -> dict[str, dict[str, object]]:
    return {
        "available": {
            "summary": "A populated Options Flow feed",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": "2026-07-15T12:00:00+00:00",
                    "as_of": "2026-07-15",
                    "provider": "yfinance_free",
                    "universe_size": 150,
                    "min_notional": 250_000,
                    "signal_count": 1,
                    "signals": [
                        {
                            "ticker": "NVDA",
                            "direction": "bullish",
                            "flow_score": 87.8,
                            "est_notional_usd": 1_250_000,
                            "biggest": {
                                "strike": 190,
                                "notional": 750_000,
                            },
                            "expiry": "2026-08-21",
                            "max_voi": 5.4,
                            "high_voi_strikes": 3,
                            "call_put_ratio": 4.2,
                            "put_call_ratio": 0.24,
                            "tags": ["多檔V/OI暴量", "百萬級量"],
                        }
                    ],
                },
                "meta": {
                    "sourceId": "signals.options-flow.feed",
                    "asOf": "2026-07-15",
                    "generatedAt": "2026-07-15T12:00:00Z",
                },
            },
        },
        "empty": {
            "summary": "A valid feed with no qualifying signals",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": "2026-07-15T12:00:00+00:00",
                    "as_of": "2026-07-15",
                    "provider": "yfinance_free",
                    "universe_size": 150,
                    "min_notional": 250_000,
                    "signal_count": 0,
                    "signals": [],
                },
                "meta": {
                    "sourceId": "signals.options-flow.feed",
                    "asOf": "2026-07-15",
                    "generatedAt": "2026-07-15T12:00:00Z",
                },
            },
        },
        "unavailable": {
            "summary": "The fixed artifact is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": {
                    "sourceId": "signals.options-flow.feed",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _options_flow_feed_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Strict Options Flow feed state. Expected artifact failures still use "
        "HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _options_flow_feed_examples()}
    }
    return responses


def _daily_summary_examples() -> dict[str, dict[str, object]]:
    base_meta = {
        "sourceId": "reports.daily-summary.latest",
        "asOf": "2026-08-01",
        "generatedAt": None,
    }
    return {
        "available": {
            "summary": "A populated newest Daily Summary",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "as_of_date": "2026-08-01",
                    "regime_summary": "Constructive but selective risk-on regime.",
                    "candidates": [
                        {"ticker": "NVDA", "verdict": "STRONG_BUY"}
                    ],
                },
                "meta": base_meta,
            },
        },
        "empty": {
            "summary": "A valid summary with no confirmed candidates",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "as_of_date": "2026-08-01",
                    "regime_summary": "Constructive but selective risk-on regime.",
                    "candidates": [],
                },
                "meta": base_meta,
            },
        },
        "unavailable": {
            "summary": "The selected newest summary is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": base_meta,
            },
        },
    }


def _daily_summary_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Strict newest dated Daily Summary state. Expected artifact failures "
        "still use HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _daily_summary_examples()}
    }
    return responses


def _playbook_validation_examples() -> dict[str, dict[str, object]]:
    generated_at = "2026-08-05T01:02:03+00:00"
    available_meta = {
        "sourceId": "reports.playbook-validation.latest",
        "asOf": None,
        "generatedAt": generated_at,
    }
    return {
        "available": {
            "summary": "An accumulating Playbook Validation summary",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": generated_at,
                    "status": "accumulating",
                    "decision_count": 12,
                    "resolved": 5,
                    "min_resolved": 100,
                    "playbooks": [
                        {
                            "playbook": "Momentum",
                            "resolved": 5,
                            "mean_fwd_7d_return": 0.031,
                            "hit_rate_7d": 0.6,
                            "verdict": "exploratory",
                        }
                    ],
                    "factors": [
                        {
                            "factor_id": "technical_breakout",
                            "resolved": 3,
                            "mean_fwd_7d_return": 0.025,
                            "hit_rate_7d": 0.6667,
                            "verdict": "exploratory",
                        }
                    ],
                },
                "meta": available_meta,
            },
        },
        "blocked": {
            "summary": "A valid producer-blocked summary without its private reason",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": generated_at,
                    "status": "blocked",
                    "decision_count": 0,
                    "resolved": 0,
                    "min_resolved": 100,
                    "playbooks": [],
                    "factors": [],
                },
                "meta": available_meta,
            },
        },
        "unavailable": {
            "summary": "The fixed Playbook Validation artifact is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": {
                    "sourceId": "reports.playbook-validation.latest",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _playbook_validation_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Strict latest Playbook Validation presentation state. Expected "
        "artifact failures still use HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _playbook_validation_examples()}
    }
    return responses


def _continuation_validation_examples() -> dict[str, dict[str, object]]:
    generated_at = "2026-08-05T01:02:03+00:00"
    meta = {
        "sourceId": "reports.continuation-validation.latest",
        "asOf": None,
        "generatedAt": generated_at,
    }
    summary = {
        "strong_continuation": 1,
        "normal_continuation": 0,
        "failed_breakout": 0,
        "unresolved": 0,
        "rows_total": 1,
        "resolved": 1,
        "min_resolved": 2,
    }
    return {
        "available": {
            "summary": "An accumulating Continuation Validation report",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": generated_at,
                    "status": "accumulating",
                    "resolved": 1,
                    "min_resolved": 2,
                    "summary": summary,
                    "rows": [
                        {
                            "ticker": "NVDA",
                            "setup_date": "2026-01-05",
                            "surge_start": "2026-01-02",
                            "thresholds_hit": ["+30%/20d"],
                            "magnitude_pct": 42.0,
                            "candidate_causes": [
                                "technical_volume_expansion"
                            ],
                            "cause_certainty": "candidate_only",
                            "measurement_source": "daily_bars",
                            "resolved_30d": True,
                            "fwd_30d_return": 0.18,
                            "fwd_30d_max_drawdown": -0.05,
                            "resolved_60d": True,
                            "fwd_60d_return": 0.34,
                            "fwd_60d_max_drawdown": -0.13,
                            "continuation_label": "strong_continuation",
                            "primary_horizon": "30d",
                            "trade_value": "high",
                        }
                    ],
                },
                "meta": meta,
            },
        },
        "blocked": {
            "summary": "A blocked report without its private diagnostic reason",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "generated_at": generated_at,
                    "status": "blocked",
                    "resolved": 0,
                    "min_resolved": 2,
                    "summary": {
                        "strong_continuation": 0,
                        "normal_continuation": 0,
                        "failed_breakout": 0,
                        "unresolved": 0,
                        "rows_total": 0,
                        "resolved": 0,
                        "min_resolved": 2,
                    },
                    "rows": [],
                },
                "meta": meta,
            },
        },
        "unavailable": {
            "summary": "The fixed Continuation Validation artifact is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": {
                    "sourceId": "reports.continuation-validation.latest",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _continuation_validation_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Strict latest Continuation Validation presentation state. Expected "
        "artifact failures still use HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _continuation_validation_examples()}
    }
    return responses


def _cot_catalog_examples() -> dict[str, dict[str, object]]:
    return {
        "available": {
            "summary": "Published COT report dates in newest-first order",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "reports": [
                        {"report_date": "2026-06-12"},
                        {"report_date": "2026-06-05"},
                    ]
                },
                "meta": {
                    "sourceId": "reports.cot.catalog",
                    "asOf": "2026-06-12",
                    "generatedAt": None,
                },
            },
        },
        "empty": {
            "summary": "The publication directory exists but has no reports",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {"reports": []},
                "meta": {
                    "sourceId": "reports.cot.catalog",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
        "unavailable": {
            "summary": "The fixed COT publication directory is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": {
                    "sourceId": "reports.cot.catalog",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _cot_verified_example() -> dict[str, object]:
    return {
        "cot": {
            "as_of": "2026-06-09",
            "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "open_interest": 2_203_164,
            "asset_manager": {
                "long": 1_205_065,
                "short": 220_979,
                "net": 984_086,
                "chg_long": 5_762,
                "chg_short": 3_535,
                "chg_net": 2_227,
            },
            "leveraged_funds": {
                "long": 168_247,
                "short": 619_833,
                "net": -451_586,
                "chg_long": 8_609,
                "chg_short": -40_537,
                "chg_net": 49_146,
            },
            "source": "CFTC publicreporting.cftc.gov (TFF futures-only, gpe5-46if)",
        },
        "price": {
            "symbol": "ES=F (continuous front-month, == TradingView ES1!)",
            "friday_date": "2026-06-12",
            "friday_open": 7_397.5,
            "friday_high": 7_461.75,
            "friday_low": 7_366.5,
            "friday_close": 7_435.0,
            "week_high": 7_461.75,
            "week_low": 7_232.25,
            "as_of_date": "2026-06-09",
            "as_of_close": 7_392.75,
            "cot_report_age_days": 5,
            "cot_stale_warning": False,
            "source": "Yahoo Finance via yfinance",
            "retrieved_at": "2026-06-14T12:09:20.318228+00:00",
        },
        "tuesday_vs_friday": {
            "as_of_tuesday_close": 7_392.75,
            "friday_close": 7_435.0,
            "delta_points": 42.25,
        },
    }


def _cot_detail_examples() -> dict[str, dict[str, object]]:
    return {
        "available": {
            "summary": "One complete published COT report pair",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "report_date": "2026-06-12",
                    "markdown": (
                        "# COT weekly report\n\n"
                        "## Section 1 — Positioning\nResearch only."
                    ),
                    "verified": _cot_verified_example(),
                },
                "meta": {
                    "sourceId": "reports.cot.detail",
                    "asOf": "2026-06-12",
                    "generatedAt": "2026-06-14T12:09:20.318228+00:00",
                },
            },
        },
        "unavailable": {
            "summary": "The selected report pair is missing",
            "value": {
                "available": False,
                "reason": "missing",
                "data": None,
                "meta": {
                    "sourceId": "reports.cot.detail",
                    "asOf": "2026-06-12",
                    "generatedAt": None,
                },
            },
        },
    }


def _cot_catalog_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Bounded server-enumerated COT report catalog state."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _cot_catalog_examples()}
    }
    return responses


def _cot_detail_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs(include_validation=True)
    responses[200]["description"] = (
        "Strict selected COT Markdown and verified-audit pair state."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _cot_detail_examples()}
    }
    return responses


def _ai_updates_examples() -> dict[str, dict[str, object]]:
    return {
        "available": {
            "summary": "Available update feed",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "updates": [
                        {
                            "date": "2026-05-23",
                            "title": "DEoT / P1Agent 架構回顧",
                            "summary": "公開摘要",
                            "link": "https://arxiv.org/abs/2504.07872",
                            "tags": ["DEoT", "架構"],
                        }
                    ]
                },
                "meta": {
                    "sourceId": "system.ai-updates",
                    "asOf": "2026-05-23",
                    "generatedAt": None,
                },
            },
        },
        "empty": {
            "summary": "Valid empty update feed",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {"updates": []},
                "meta": {
                    "sourceId": "system.ai-updates",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _ai_updates_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Manually maintained AI updates artifact state. Expected source failures "
        "still use HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _ai_updates_examples()}
    }
    return responses


def _schedules_examples() -> dict[str, dict[str, object]]:
    return {
        "available": {
            "summary": "Available schedule registry",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {
                    "schedules": [
                        {
                            "id": "local_data_health_refresh",
                            "name": "資料健康完整更新",
                            "category": "系統",
                            "cron": "15 6 * * 2-6",
                            "cron_note": "週二至週六 06:15 Asia/Taipei",
                            "description": "自動更新資料健康產物。",
                            "result_type": "data_health",
                        }
                    ]
                },
                "meta": {
                    "sourceId": "system.schedules",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
        "empty": {
            "summary": "Valid empty schedule registry",
            "value": {
                "available": True,
                "reason": "ok",
                "data": {"schedules": []},
                "meta": {
                    "sourceId": "system.schedules",
                    "asOf": None,
                    "generatedAt": None,
                },
            },
        },
    }


def _schedules_response_docs() -> dict[int, dict[str, object]]:
    responses = _artifact_response_docs()
    responses[200]["description"] = (
        "Manually maintained schedule-registry artifact state. Expected source "
        "failures still use HTTP 200 with available=false."
    )
    responses[200]["content"] = {
        "application/json": {"examples": _schedules_examples()}
    }
    return responses


def _problem(
    status: int,
    title: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problem = Problem(
        type="about:blank",
        title=title,
        status=status,
    )
    response_headers = {"Cache-Control": NO_STORE}
    if headers is not None:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(exclude_unset=True),
        headers=response_headers,
        media_type="application/problem+json",
    )


def _host_without_port(value: str) -> str:
    host = value.strip().lower()
    if host.startswith("["):
        closing = host.find("]")
        if closing <= 0:
            return ""
        suffix = host[closing + 1 :]
        if suffix and not (suffix.startswith(":") and suffix[1:].isdigit()):
            return ""
        return host[1:closing]
    if host.count(":") == 1:
        return host.rsplit(":", 1)[0]
    return host


def _is_loopback_peer(value: str | None) -> bool:
    if not value:
        return False
    if value.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _valid_internal_api_token(value: object) -> bool:
    if not isinstance(value, str) or not (
        _INTERNAL_API_TOKEN_MIN_LENGTH
        <= len(value)
        <= _INTERNAL_API_TOKEN_MAX_LENGTH
    ):
        return False
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return all(0x21 <= byte <= 0x7E for byte in encoded)


def _internal_api_token_from_file(path_value: str) -> str | None:
    prefix = f"{_INTERNAL_API_TOKEN_ENV}=".encode("ascii")
    maximum = len(prefix) + _INTERNAL_API_TOKEN_MAX_LENGTH + 1
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path_value,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
            os.close(descriptor)
            descriptor = None
            return None
        handle = os.fdopen(descriptor, "rb")
        descriptor = None
        with handle:
            raw = handle.read(maximum + 1)
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        return None
    if len(raw) > maximum:
        return None
    if not raw.startswith(prefix) or not raw.endswith(b"\n"):
        return None
    try:
        token = raw[len(prefix) : -1].decode("ascii")
    except UnicodeDecodeError:
        return None
    return token if _valid_internal_api_token(token) else None


def create_app(
    registry: Mapping[str, ArtifactSpec] = ARTIFACTS,
    *,
    iv_history_directory: Path = IV_HISTORY_DIR,
    cot_reports_directory: Path = COT_REPORTS_DIR,
    knowledge_vault: Path = KNOWLEDGE_VAULT,
    theme_taxonomy_path: Path = THEME_TAXONOMY_FILE,
    theme_drill_path: Path = THEME_DRILL_FILE,
    influencer_roster_path: Path | None = None,
    industry_role_taxonomy_path: Path = _INDUSTRY_ROLE_TAXONOMY_FILE,
    industry_role_state_path: Path = _INDUSTRY_ROLE_STATE_FILE,
    internal_api_token: str | None | object = _INTERNAL_TOKEN_UNSET,
) -> FastAPI:
    missing = _REQUIRED_SOURCE_IDS.difference(registry)
    if missing:
        raise ValueError(f"artifact registry is missing {len(missing)} required entries")

    fixed_influencer_roster_path = (
        resolve_roster_path(seed=False)
        if influencer_roster_path is None
        else influencer_roster_path
    )

    app = FastAPI(
        title="Surge Screener API",
        summary=(
            "Loopback-only public artifact reads plus credential-protected "
            "private operator state."
        ),
        version="1.23.0-draft",
        openapi_version="3.1.0",
    )
    internal_bearer = HTTPBearer(
        auto_error=False,
        scheme_name="InternalServiceBearer",
        description=(
            "High-entropy Streamlit-to-FastAPI service credential for protected "
            "loopback routes; not a human login or provider token."
        ),
    )

    def configured_internal_token() -> str | None:
        if internal_api_token is not _INTERNAL_TOKEN_UNSET:
            candidate = internal_api_token
            return candidate if _valid_internal_api_token(candidate) else None
        direct = os.environ.get(_INTERNAL_API_TOKEN_ENV)
        file_path = os.environ.get(_INTERNAL_API_TOKEN_FILE_ENV)
        if direct is not None and file_path is not None:
            return None
        candidate = (
            _internal_api_token_from_file(file_path)
            if file_path is not None
            else direct
        )
        return candidate if _valid_internal_api_token(candidate) else None

    def private_auth_failure(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None,
    ) -> JSONResponse | None:
        configured = configured_internal_token()
        if configured is None:
            return _problem(503, "Service Unavailable")
        authorization_headers = request.headers.getlist("authorization")
        submitted = credentials.credentials if credentials is not None else None
        if (
            len(authorization_headers) != 1
            or credentials is None
            or credentials.scheme.casefold() != "bearer"
            or not _valid_internal_api_token(submitted)
            or not hmac.compare_digest(submitted, configured)
        ):
            return _problem(
                401,
                "Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    @app.middleware("http")
    async def enforce_loopback(request: Request, call_next):
        try:
            peer = request.client.host if request.client else None
            host = _host_without_port(request.headers.get("host", ""))
            if not _is_loopback_peer(peer) or host not in _ALLOWED_HOSTS:
                return _problem(403, "Forbidden")
            return await call_next(request)
        except Exception as exc:
            # Handle pre-response route defects inside the user middleware so
            # Starlette does not re-raise an already-sanitized exception to
            # Uvicorn, which would print its message and traceback to the journal.
            matched_route = request.scope.get("route")
            route_template = getattr(matched_route, "path", None)
            if not isinstance(route_template, str):
                route_template = "<unmatched>"
            LOGGER.error(
                "unhandled API error",
                extra={
                    "route": route_template,
                    "error_type": type(exc).__name__,
                },
            )
            return _problem(500, "Internal Server Error")

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _problem(422, "Unprocessable Entity")

    def artifact(
        spec: ArtifactSpec,
        *,
        log_context: Mapping[str, object] | None = None,
    ) -> ArtifactReadResult:
        result = read_artifact(spec)
        if isinstance(result, ArtifactUnavailable):
            context = {"source_id": spec.source_id, "reason": result.reason}
            if log_context is not None:
                context.update(log_context)
            LOGGER.warning(
                "artifact unavailable",
                extra=context,
            )
        return result

    def public_read(result: object, source_id: str) -> object:
        if isinstance(result, ArtifactUnavailable):
            LOGGER.warning(
                "public read unavailable",
                extra={"source_id": source_id, "reason": result.reason},
            )
        return result

    @app.get(
        "/api/v1/private/industry-roles/review-board",
        tags=["Private"],
        summary="Read the singleton operator's Industry Roles review board",
        description=(
            "Returns a bounded path-free projection of role names, approved "
            "assignments, and review suggestions. The bearer credential "
            "authenticates the Streamlit workload; the private-host perimeter "
            "owns the singleton human operator boundary."
        ),
        operation_id="getIndustryRoleReviewBoard",
        response_model=IndustryRoleReviewBoardEnvelope,
        responses={
            **_artifact_response_docs(),
            401: {
                "description": "Missing or invalid internal service credential.",
                "headers": {
                    "Cache-Control": _no_store_header_docs(),
                    "WWW-Authenticate": {
                        "schema": {"type": "string", "const": "Bearer"}
                    },
                },
                "content": {
                    "application/problem+json": {
                        "schema": Problem.model_json_schema(mode="serialization")
                    }
                },
            },
            503: {
                "description": "Internal service credential is not configured.",
                "headers": {"Cache-Control": _no_store_header_docs()},
                "content": {
                    "application/problem+json": {
                        "schema": Problem.model_json_schema(mode="serialization")
                    }
                },
            },
        },
        openapi_extra={
            "responses": {
                "200": {
                    "headers": {
                        "Cache-Control": _no_store_header_docs(),
                        "ETag": _strong_etag_header_docs(),
                    }
                }
            }
        },
    )
    def get_industry_role_review_board(
        request: Request,
        response: Response,
        credentials: HTTPAuthorizationCredentials | None = Depends(internal_bearer),
    ) -> object:
        failure = private_auth_failure(request, credentials)
        if failure is not None:
            return failure
        response.headers["Cache-Control"] = NO_STORE
        snapshot = read_industry_role_review_board_snapshot(
            industry_role_taxonomy_path,
            industry_role_state_path,
        )
        result = snapshot.envelope
        if snapshot.etag is not None:
            response.headers["ETag"] = snapshot.etag
        if isinstance(result, ArtifactUnavailable):
            LOGGER.warning(
                "private read unavailable",
                extra={"source_id": result.meta.source_id, "reason": result.reason},
            )
        return result

    @app.post(
        "/api/v1/private/industry-roles/review-board/actions",
        tags=["Private"],
        summary="Mutate the singleton operator's Industry Roles review board",
        operation_id="mutateIndustryRoleReviewBoard",
        response_model=IndustryRoleMutationResult,
        responses={
            200: {
                "description": "Committed or durably replayed Industry Roles action.",
                "headers": {
                    "Cache-Control": _no_store_header_docs(),
                    "ETag": _strong_etag_header_docs(),
                },
            },
            401: {
                "description": "Missing or invalid internal service credential.",
                "headers": {
                    "Cache-Control": _no_store_header_docs(),
                    "WWW-Authenticate": {
                        "schema": {"type": "string", "const": "Bearer"}
                    },
                },
                "content": {
                    "application/problem+json": {
                        "schema": Problem.model_json_schema(mode="serialization")
                    }
                },
            },
            **{
                status: {
                    "description": title,
                    "headers": {"Cache-Control": _no_store_header_docs()},
                    "content": {
                        "application/problem+json": {
                            "schema": Problem.model_json_schema(mode="serialization")
                        }
                    },
                }
                for status, title in {
                    409: "Domain or idempotency conflict.",
                    412: "Conditional validator failed.",
                    422: "Invalid action body or header value.",
                    428: "A required conditional header is missing.",
                    500: "Unexpected programming or server failure.",
                    503: "Protected mutation state is unavailable.",
                }.items()
            },
        },
        openapi_extra={
            "requestBody": _industry_role_action_request_docs(),
            "parameters": [
                {
                    "name": "If-Match",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "minLength": 68, "maxLength": 96},
                },
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "minLength": 16,
                        "maxLength": 128,
                        "pattern": r"^[\x21-\x7e]+$",
                    },
                },
            ],
        },
    )
    async def mutate_industry_role_review_board(
        request: Request,
        response: Response,
        credentials: HTTPAuthorizationCredentials | None = Depends(internal_bearer),
    ) -> object:
        failure = private_auth_failure(request, credentials)
        if failure is not None:
            return failure
        if_match_values = request.headers.getlist("if-match")
        key_values = request.headers.getlist("idempotency-key")
        if len(if_match_values) != 1 or len(key_values) != 1:
            return _problem(428, "Precondition Required")
        expected_etag = if_match_values[0]
        idempotency_key = key_values[0]
        if not industry_role_store.is_strong_etag(expected_etag):
            return _problem(412, "Precondition Failed")
        try:
            encoded_key = idempotency_key.encode("ascii")
        except UnicodeEncodeError:
            return _problem(422, "Unprocessable Entity")
        if not (
            16 <= len(idempotency_key) <= 128
            and all(0x21 <= byte <= 0x7E for byte in encoded_key)
        ):
            return _problem(422, "Unprocessable Entity")
        content_types = request.headers.getlist("content-type")
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().casefold() != "application/json":
            return _problem(422, "Unprocessable Entity")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _PRIVATE_MUTATION_MAX_BYTES:
                return _problem(422, "Unprocessable Entity")
            raw.extend(chunk)
        try:
            action_request = _INDUSTRY_ROLE_ACTION_ADAPTER.validate_json(
                bytes(raw),
                strict=True,
            )
        except (ValidationError, ValueError):
            return _problem(422, "Unprocessable Entity")
        request_payload = action_request.model_dump(mode="json", by_alias=True)
        try:
            mutation = industry_role_engine.mutate_review_board_action(
                request_payload,
                content_dir=industry_role_taxonomy_path.parent,
                state_path=industry_role_state_path,
                expected_etag=expected_etag,
                idempotency_key=idempotency_key,
            )
        except industry_role_store.RevisionConflict:
            return _problem(412, "Precondition Failed")
        except industry_role_store.IdempotencyConflict:
            return _problem(409, "Conflict")
        except (KeyError, ValueError):
            return _problem(409, "Conflict")
        except (industry_role_store.StateInvalid, industry_role_store.StateBusy):
            return _problem(503, "Service Unavailable")
        result = IndustryRoleMutationResult.model_validate(mutation.result, strict=True)
        response.headers["Cache-Control"] = NO_STORE
        response.headers["ETag"] = mutation.etag
        return result

    @app.get(
        "/healthz",
        tags=["Health"],
        summary="Check API process health",
        operation_id="getHealth",
        response_model=HealthResponse,
        responses={200: {"headers": {"Cache-Control": _no_store_header_docs()}}},
    )
    def get_health(response: Response) -> HealthResponse:
        response.headers["Cache-Control"] = NO_STORE
        return HealthResponse(status="ok", apiVersion="v1")

    @app.get(
        "/api/v1/candidates/ranked",
        tags=["Candidates"],
        summary="Read the ranked candidate artifact",
        operation_id="getRankedCandidates",
        response_model=RankedEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_ranked_candidates(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["candidates.ranked"])

    @app.get(
        "/api/v1/candidates/scored",
        tags=["Candidates"],
        summary="Read the scored candidate artifact",
        operation_id="getScoredCandidates",
        response_model=ScoredEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_scored_candidates(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["candidates.scored"])

    @app.get(
        "/api/v1/candidates/ranked/feed",
        tags=["Candidates"],
        summary="Read the strict ranked candidate presentation feed",
        operation_id="getRankedCandidatesFeed",
        response_model=RankedFeedEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_ranked_candidates_feed(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["candidates.ranked.feed"])

    @app.get(
        "/api/v1/candidates/scored/feed",
        tags=["Candidates"],
        summary="Read the strict scored candidate presentation feed",
        operation_id="getScoredCandidatesFeed",
        response_model=ScoredFeedEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_scored_candidates_feed(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["candidates.scored.feed"])

    @app.get(
        "/api/v1/candidates/scored/screener",
        tags=["Candidates"],
        summary="Read the strict US Screener scored projection",
        operation_id="getScoredCandidatesScreener",
        response_model=ScoredScreenerEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_scored_candidates_screener(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["candidates.scored.screener"])

    @app.get(
        "/api/v1/signals/options-flow/latest",
        tags=["Signals"],
        summary="Read the latest options-flow snapshot",
        operation_id="getLatestOptionsFlow",
        response_model=OptionsFlowEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_options_flow(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.options-flow.latest"])

    @app.get(
        "/api/v1/signals/options-flow/feed",
        tags=["Signals"],
        summary="Read the strict Options Flow feed projection",
        description=(
            "Reads the fixed Options Flow artifact and returns only the bounded, "
            "allowlisted frontend feed. Expected artifact failures return an "
            "HTTP 200 unavailable envelope."
        ),
        operation_id="getOptionsFlowFeed",
        response_model=OptionsFlowFeedEnvelope,
        responses=_options_flow_feed_response_docs(),
    )
    def get_options_flow_feed(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.options-flow.feed"])

    @app.get(
        "/api/v1/signals/reversal-radar/latest",
        tags=["Signals"],
        summary="Read the latest reversal-radar snapshot",
        description=(
            "Returns only bounded persisted discovery provenance and unique "
            "ticker references. Live Reversal detail is recomputed by the backend "
            "provider path and is not published by this projection."
        ),
        operation_id="getLatestReversalRadar",
        response_model=ReversalRadarEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_reversal_radar(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.reversal-radar.latest"])

    @app.get(
        "/api/v1/signals/reversal-radar/validation",
        tags=["Signals"],
        summary="Read the Reversal Radar forward-validation summary",
        description=(
            "Returns only the bounded conservative maturity headline and three "
            "fixed tier hit-rate rows. EV, excess-return statistics, equity "
            "curves, survivorship, and producer diagnostics remain server-side."
        ),
        operation_id="getReversalRadarValidation",
        response_model=ReversalRadarValidationEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_reversal_radar_validation(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.reversal-radar.validation"])

    @app.get(
        "/api/v1/signals/oversold-reversal/latest",
        tags=["Signals"],
        summary="Read the latest oversold-reversal snapshot",
        description=(
            "Returns the strict bounded coiled-base presentation projection while "
            "excluding source diagnostics and unused candidate fields."
        ),
        operation_id="getLatestOversoldReversal",
        response_model=OversoldReversalEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_oversold_reversal(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.oversold-reversal.latest"])

    @app.get(
        "/api/v1/signals/oversold-reversal/validation",
        tags=["Signals"],
        summary="Read the Oversold Reversal forward-validation summary",
        description=(
            "Returns only the bounded conservative maturity headline and three "
            "fixed tier hit-rate rows. EV, equity curves, survivorship, cohort, "
            "cost, and producer diagnostics remain server-side."
        ),
        operation_id="getOversoldReversalValidation",
        response_model=OversoldReversalValidationEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_oversold_reversal_validation(
        response: Response,
    ) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["signals.oversold-reversal.validation"])

    @app.get(
        "/api/v1/market-context/market-thesis/latest",
        tags=["Market Context"],
        summary="Read the latest Market Thesis forecast",
        description=(
            "Resolves the latest forecast by date with ready-over-regime-only "
            "same-day precedence and returns only the strict public presentation "
            "projection. Expected artifact failures return an HTTP 200 unavailable "
            "envelope."
        ),
        operation_id="getLatestMarketThesis",
        response_model=MarketThesisEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_market_thesis(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.market-thesis.latest"])

    @app.get(
        "/api/v1/reports/daily-summary/latest",
        tags=["Reports"],
        summary="Read the latest dated Daily Summary",
        description=(
            "Selects only the newest exact real-date report directory and returns "
            "a strict minimal regime and candidate-reference projection. The "
            "selected source date must match its directory; expected artifact "
            "failures return an HTTP 200 unavailable envelope without older "
            "fallback."
        ),
        operation_id="getLatestDailySummary",
        response_model=DailySummaryEnvelope,
        responses=_daily_summary_response_docs(),
    )
    def get_latest_daily_summary(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["reports.daily-summary.latest"])

    @app.get(
        "/api/v1/reports/playbook-validation/latest",
        tags=["Reports"],
        summary="Read the latest Playbook Validation presentation summary",
        description=(
            "Reads one fixed server-owned summary and returns only bounded "
            "maturity, decision-count, playbook, and factor presentation "
            "fields. Raw blocked diagnostics, outcome counts, decision "
            "snapshots, ticker outcomes, provider details, and source paths "
            "remain server-side."
        ),
        operation_id="getLatestPlaybookValidation",
        response_model=PlaybookValidationEnvelope,
        responses=_playbook_validation_response_docs(),
    )
    def get_latest_playbook_validation(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["reports.playbook-validation.latest"])

    @app.get(
        "/api/v1/reports/continuation-validation/latest",
        tags=["Reports"],
        summary="Read the latest Continuation Validation presentation state",
        description=(
            "Returns only bounded maturity counters, classifications, candidate "
            "cause labels, and forward-return rows. Private diagnostics, source "
            "paths, and producer notes remain server-side."
        ),
        operation_id="getLatestContinuationValidation",
        response_model=ContinuationValidationEnvelope,
        responses=_continuation_validation_response_docs(),
    )
    def get_latest_continuation_validation(
        response: Response,
    ) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["reports.continuation-validation.latest"])

    @app.get(
        "/api/v1/reports/cot",
        tags=["Reports"],
        summary="List published COT reports",
        description=(
            "Enumerates at most 520 exact dated Markdown publications in "
            "newest-first order without exposing server paths or provider logs."
        ),
        operation_id="getCotCatalog",
        response_model=CotCatalogEnvelope,
        responses=_cot_catalog_response_docs(),
    )
    def get_cot_catalog(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        result = read_cot_catalog(cot_reports_directory)
        if isinstance(result, ArtifactUnavailable):
            LOGGER.warning(
                "artifact unavailable",
                extra={
                    "source_id": "reports.cot.catalog",
                    "reason": result.reason,
                },
            )
        return result

    @app.get(
        "/api/v1/reports/cot/{report_date}",
        tags=["Reports"],
        summary="Read one published COT report",
        description=(
            "Reads one exact Markdown and verified-data pair. The selected date, "
            "file sizes, JSON shape, position arithmetic, price ranges, and "
            "audit metadata must all agree; there is no older-report fallback."
        ),
        operation_id="getCotReport",
        response_model=CotDetailEnvelope,
        responses=_cot_detail_response_docs(),
    )
    def get_cot_report(
        report_date: ReportDatePath,
        response: Response,
    ) -> ArtifactReadResult | JSONResponse:
        try:
            date.fromisoformat(report_date)
        except ValueError:
            return _problem(422, "Unprocessable Entity")
        response.headers["Cache-Control"] = NO_STORE
        result = read_cot_report(report_date, cot_reports_directory)
        if isinstance(result, ArtifactUnavailable):
            LOGGER.warning(
                "artifact unavailable",
                extra={
                    "source_id": "reports.cot.detail",
                    "reason": result.reason,
                    "report_date": report_date,
                },
            )
        return result

    @app.get(
        "/api/v1/reports/cot/{invalid_path:path}",
        include_in_schema=False,
    )
    def reject_invalid_cot_path(_invalid_path: str) -> JSONResponse:
        return _problem(422, "Unprocessable Entity")

    @app.get(
        "/api/v1/market-context/market-thesis/validation",
        tags=["Market Context"],
        summary="Read the Market Thesis forward-validation summary",
        description=(
            "Returns only bounded publishability counters and full-key hit-rate "
            "rows. Rejected ledgers, invalid records, benchmark configuration, "
            "and notes remain server-side."
        ),
        operation_id="getMarketThesisValidation",
        response_model=MarketThesisValidationEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_market_thesis_validation(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.market-thesis.validation"])

    @app.get(
        "/api/v1/market-context/market-thesis/regime-history",
        tags=["Market Context"],
        summary="Read the Market Thesis regime-history summary",
        description=(
            "Projects exactly three regimes and three forward windows. The raw "
            "daily corpus, runs, episodes, rules, VIX telemetry, and notes never "
            "enter the response."
        ),
        operation_id="getMarketThesisRegimeHistory",
        response_model=MarketThesisRegimeHistoryEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_market_thesis_regime_history(
        response: Response,
    ) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.market-thesis.regime-history"])

    @app.get(
        "/api/v1/market-context/money-flow/latest",
        tags=["Market Context"],
        summary="Read the latest strict Money Flow snapshot",
        description=(
            "Returns the bounded allowlisted Eastmoney presentation projection. "
            "Provider identifiers, raw rows, and unused flow breakdowns remain "
            "server-side."
        ),
        operation_id="getLatestMoneyFlow",
        response_model=MoneyFlowEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_money_flow(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.money-flow.latest"])

    @app.get(
        "/api/v1/market-context/sector-rotation/latest",
        tags=["Market Context"],
        summary="Read the latest strict Sector Rotation board",
        operation_id="getLatestSectorRotation",
        response_model=SectorRotationEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_sector_rotation(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.sector-rotation.latest"])

    @app.get(
        "/api/v1/knowledge/graph",
        tags=["Knowledge"],
        summary="Read the bounded public Knowledge Graph",
        description=(
            "Compiles the fixed server-owned Markdown vault once and returns only "
            "the bounded path-free graph projection."
        ),
        operation_id="getKnowledgeGraph",
        response_model=KnowledgeGraphEnvelope,
        responses=_fixed_public_response_docs(
            source_id="knowledge.graph",
            empty_data={
                "nodes": [],
                "edges": [],
                "diagnostics": {"unresolved_links": [], "duplicate_ids": []},
            },
            available_data={
                "nodes": [
                    {
                        "id": "Dim1",
                        "label": "Dim1",
                        "type": "dimension",
                        "dimension": "",
                        "horizon": "",
                        "status": "index",
                        "blocked": False,
                        "lift_exploratory": None,
                        "runway_verdict": "",
                        "verdict_raw": "",
                    }
                ],
                "edges": [],
                "diagnostics": {"unresolved_links": [], "duplicate_ids": []},
            },
        ),
    )
    def get_knowledge_graph(response: Response) -> object:
        response.headers["Cache-Control"] = NO_STORE
        return public_read(read_knowledge_graph(knowledge_vault), "knowledge.graph")

    @app.get(
        "/api/v1/watchlists/theme-taxonomy",
        tags=["Watchlists"],
        summary="Read the public Watchlist theme taxonomy",
        operation_id="getThemeTaxonomy",
        response_model=ThemeTaxonomyEnvelope,
        responses=_fixed_public_response_docs(
            source_id="watchlists.theme-taxonomy",
            empty_data={"themes": []},
            available_data={
                "themes": [
                    {
                        "name": "AI supercycle",
                        "description": "AI infrastructure and applications",
                    }
                ]
            },
        ),
    )
    def get_theme_taxonomy(response: Response) -> object:
        response.headers["Cache-Control"] = NO_STORE
        return public_read(
            read_theme_taxonomy(theme_taxonomy_path),
            "watchlists.theme-taxonomy",
        )

    @app.get(
        "/api/v1/market-context/theme-drill",
        tags=["Market Context"],
        summary="Read the fixed sector-to-theme drill projection",
        description=(
            "Projects only theme names and parent SPDR sector ETFs from the fixed "
            "basket curation; ticker membership and producer details are omitted."
        ),
        operation_id="getThemeDrill",
        response_model=ThemeDrillEnvelope,
        responses=_fixed_public_response_docs(
            source_id="market-context.theme-drill",
            empty_data={"sectors": []},
            available_data={
                "sectors": [
                    {"etf": "XLK", "themes": ["HBM", "Advanced packaging"]}
                ]
            },
        ),
    )
    def get_theme_drill(response: Response) -> object:
        response.headers["Cache-Control"] = NO_STORE
        return public_read(
            read_theme_drill(theme_drill_path),
            "market-context.theme-drill",
        )

    @app.get(
        "/api/v1/social/influencers",
        tags=["Social"],
        summary="Read the public Influencer roster projection",
        description=(
            "Reads the fixed editable roster without seeding or writing and omits "
            "root notes, paths, provider state, and credentials."
        ),
        operation_id="getInfluencerRoster",
        response_model=InfluencerRosterEnvelope,
        responses=_fixed_public_response_docs(
            source_id="social.influencers.roster",
            empty_data={"categories": [], "influencers": []},
            available_data={
                "categories": ["Option Flow"],
                "influencers": [
                    {
                        "handle": "unusual_whales",
                        "name": "Unusual Whales",
                        "category": "Option Flow",
                        "market": "US",
                        "note": "Options flow",
                        "url": "https://x.com/unusual_whales",
                        "category_source": None,
                        "category_reason": None,
                        "category_confidence": None,
                        "placeholder": False,
                    }
                ],
            },
        ),
    )
    def get_influencer_roster(response: Response) -> object:
        response.headers["Cache-Control"] = NO_STORE
        return public_read(
            read_influencer_roster(fixed_influencer_roster_path),
            "social.influencers.roster",
        )

    @app.get(
        "/api/v1/social/intelligence/latest",
        tags=["Social"],
        summary="Read the latest Social Intelligence snapshot",
        description=(
            "Returns only the bounded persisted radar and local-summary fields. "
            "Live X, Agent Reach, roster, and AI actions are not invoked."
        ),
        operation_id="getLatestSocialIntelligence",
        response_model=SocialIntelligenceEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_social_intelligence(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["social.intelligence.latest"])

    @app.get(
        "/api/v1/market-context/theme-flow/latest",
        tags=["Market Context"],
        summary="Read the latest Theme Flow board",
        description=(
            "Returns the strict current-schema presentation board and its "
            "server-computed coherence fingerprint without running providers."
        ),
        operation_id="getLatestThemeFlow",
        response_model=ThemeFlowEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_latest_theme_flow(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.theme-flow.latest"])

    @app.get(
        "/api/v1/market-context/theme-flow/analysis",
        tags=["Market Context"],
        summary="Read the current-validation Theme Flow analysis",
        description=(
            "Returns only a ready validation-v8 persisted read. The frontend "
            "compares its board fingerprint with the displayed Theme Flow board."
        ),
        operation_id="getThemeFlowAnalysis",
        response_model=ThemeFlowAnalysisEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_theme_flow_analysis(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["market-context.theme-flow.analysis"])

    @app.get(
        "/api/v1/institutions/funds",
        tags=["Institutions"],
        summary="Read the curated institutional fund catalog",
        operation_id="getInstitutionFunds",
        response_model=FundCatalogEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_institution_funds(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["institutions.funds"])

    @app.get(
        "/api/v1/crypto/universe",
        tags=["Crypto"],
        summary="Read the Binance USDT perpetual universe",
        description=(
            "Reads one fixed server-owned snapshot, projects out fetch diagnostics "
            "and duplicate symbol storage, and returns a strict bounded public DTO."
        ),
        operation_id="getCryptoUniverse",
        response_model=CryptoUniverseEnvelope,
        responses=_artifact_response_docs(),
    )
    def get_crypto_universe(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["crypto.universe"])

    @app.get(
        "/api/v1/system/ai-updates",
        tags=["System"],
        summary="Read the manually maintained AI updates feed",
        description=(
            "Reads only the server-owned content/ai_updates.json feed. "
            "Maintainer-only source guidance is validated but omitted from the "
            "public response. Update order and all public string values are "
            "preserved exactly. This operation has no parameters and never calls "
            "an AI or network provider."
        ),
        operation_id="getAiUpdates",
        response_model=AiUpdatesEnvelope,
        responses=_ai_updates_response_docs(),
    )
    def get_ai_updates(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["system.ai-updates"])

    @app.get(
        "/api/v1/system/schedules",
        tags=["System"],
        summary="Read the manually maintained schedule registry",
        description=(
            "Reads only the server-owned content/schedules.json registry. "
            "Maintainer guidance such as the source _note is validated but "
            "omitted. Schedule order and all public string values are preserved "
            "exactly. This operation has no parameters and never reads result "
            "artifacts or calls a provider."
        ),
        operation_id="getSchedules",
        response_model=SchedulesEnvelope,
        responses=_schedules_response_docs(),
    )
    def get_schedules(response: Response) -> ArtifactReadResult:
        response.headers["Cache-Control"] = NO_STORE
        return artifact(registry["system.schedules"])

    @app.get(
        "/api/v1/options/iv-history/{ticker}",
        tags=["Options"],
        summary="Read one ticker's IV history",
        operation_id="getIvHistory",
        response_model=IvHistoryEnvelope,
        responses=_artifact_response_docs(include_validation=True),
    )
    def get_iv_history(
        ticker: TickerPath,
        response: Response,
    ) -> ArtifactReadResult | JSONResponse:
        normalized = normalize_ticker(ticker)
        if normalized is None:
            return _problem(422, "Unprocessable Entity")
        response.headers["Cache-Control"] = NO_STORE
        spec = iv_history_spec(normalized, iv_history_directory)
        return artifact(spec, log_context={"ticker": normalized})

    default_openapi = app.openapi

    def openapi_with_exact_examples() -> dict[str, object]:
        schema = default_openapi()
        schema["paths"]["/api/v1/system/ai-updates"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["examples"] = _ai_updates_examples()
        schema["paths"]["/api/v1/system/schedules"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["examples"] = _schedules_examples()
        schema["paths"]["/api/v1/signals/options-flow/feed"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["examples"] = (
            _options_flow_feed_examples()
        )
        schema["paths"]["/api/v1/reports/daily-summary/latest"]["get"][
            "responses"
        ]["200"]["content"]["application/json"]["examples"] = (
            _daily_summary_examples()
        )
        schema["paths"]["/api/v1/reports/playbook-validation/latest"]["get"][
            "responses"
        ]["200"]["content"]["application/json"]["examples"] = (
            _playbook_validation_examples()
        )
        schema["paths"]["/api/v1/reports/continuation-validation/latest"][
            "get"
        ]["responses"]["200"]["content"]["application/json"]["examples"] = (
            _continuation_validation_examples()
        )
        schema["paths"]["/api/v1/reports/cot"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["examples"] = _cot_catalog_examples()
        schema["paths"]["/api/v1/reports/cot/{report_date}"]["get"][
            "responses"
        ]["200"]["content"]["application/json"]["examples"] = (
            _cot_detail_examples()
        )
        return schema

    app.openapi = openapi_with_exact_examples

    return app


app = create_app()
