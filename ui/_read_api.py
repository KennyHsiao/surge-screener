"""Fixed, fail-soft loopback clients for public Streamlit reads."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, TypeAlias

import httpx
from pydantic import TypeAdapter, ValidationError

from api.models import (
    AiUpdateItem,
    AiUpdatesData,
    ArtifactAvailable,
    ArtifactUnavailable,
    CryptoUniverseData,
    CotCatalogData,
    CotReportData,
    DailySummaryData,
    FundCatalogData,
    IvHistoryData,
    InfluencerRosterData,
    KnowledgeGraphData,
    MarketThesisData,
    MarketThesisRegimeHistoryData,
    MarketThesisValidationData,
    MoneyFlowData,
    OptionsFlowFeedData,
    OversoldReversalData,
    OversoldReversalValidationData,
    PlaybookValidationData,
    ContinuationValidationData,
    RankedCandidatesFeedData,
    ReversalRadarData,
    ReversalRadarValidationData,
    ScheduleEntry,
    SchedulesData,
    ScoredCandidatesFeedData,
    ScoredCandidatesScreenerData,
    SectorRotationData,
    SocialIntelligenceData,
    ThemeFlowAnalysisData,
    ThemeFlowData,
    ThemeDrillData,
    ThemeTaxonomyData,
    ThemeTaxonomyItem,
    UnavailableReason,
    normalize_ticker,
)


_SCHEDULES_URL = "http://127.0.0.1:8000/api/v1/system/schedules"
_AI_UPDATES_URL = "http://127.0.0.1:8000/api/v1/system/ai-updates"
_FUND_CATALOG_URL = "http://127.0.0.1:8000/api/v1/institutions/funds"
_IV_HISTORY_URL_PREFIX = "http://127.0.0.1:8000/api/v1/options/iv-history/"
_OPTIONS_FLOW_FEED_URL = (
    "http://127.0.0.1:8000/api/v1/signals/options-flow/feed"
)
_CRYPTO_UNIVERSE_URL = "http://127.0.0.1:8000/api/v1/crypto/universe"
_MARKET_THESIS_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/market-thesis/latest"
)
_DAILY_SUMMARY_URL = (
    "http://127.0.0.1:8000/api/v1/reports/daily-summary/latest"
)
_PLAYBOOK_VALIDATION_URL = (
    "http://127.0.0.1:8000/api/v1/reports/playbook-validation/latest"
)
_CONTINUATION_VALIDATION_URL = (
    "http://127.0.0.1:8000/api/v1/reports/continuation-validation/latest"
)
_COT_CATALOG_URL = "http://127.0.0.1:8000/api/v1/reports/cot"
_COT_DETAIL_URL_PREFIX = "http://127.0.0.1:8000/api/v1/reports/cot/"
_MARKET_THESIS_VALIDATION_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/market-thesis/validation"
)
_MARKET_THESIS_REGIME_HISTORY_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/market-thesis/regime-history"
)
_MONEY_FLOW_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/money-flow/latest"
)
_SECTOR_ROTATION_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/sector-rotation/latest"
)
_REVERSAL_RADAR_URL = (
    "http://127.0.0.1:8000/api/v1/signals/reversal-radar/latest"
)
_REVERSAL_RADAR_VALIDATION_URL = (
    "http://127.0.0.1:8000/api/v1/signals/reversal-radar/validation"
)
_OVERSOLD_REVERSAL_URL = (
    "http://127.0.0.1:8000/api/v1/signals/oversold-reversal/latest"
)
_OVERSOLD_REVERSAL_VALIDATION_URL = (
    "http://127.0.0.1:8000/api/v1/signals/oversold-reversal/validation"
)
_RANKED_CANDIDATES_URL = (
    "http://127.0.0.1:8000/api/v1/candidates/ranked/feed"
)
_SCORED_CANDIDATES_URL = (
    "http://127.0.0.1:8000/api/v1/candidates/scored/feed"
)
_SCORED_CANDIDATES_SCREENER_URL = (
    "http://127.0.0.1:8000/api/v1/candidates/scored/screener"
)
_SOCIAL_INTELLIGENCE_URL = (
    "http://127.0.0.1:8000/api/v1/social/intelligence/latest"
)
_THEME_FLOW_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/theme-flow/latest"
)
_THEME_FLOW_ANALYSIS_URL = (
    "http://127.0.0.1:8000/api/v1/market-context/theme-flow/analysis"
)
_KNOWLEDGE_GRAPH_URL = "http://127.0.0.1:8000/api/v1/knowledge/graph"
_THEME_TAXONOMY_URL = (
    "http://127.0.0.1:8000/api/v1/watchlists/theme-taxonomy"
)
_THEME_DRILL_URL = "http://127.0.0.1:8000/api/v1/market-context/theme-drill"
_INFLUENCER_ROSTER_URL = "http://127.0.0.1:8000/api/v1/social/influencers"
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_AI_UPDATES_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_FUND_CATALOG_MAX_RESPONSE_BYTES = 512 * 1024
_IV_HISTORY_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_OPTIONS_FLOW_FEED_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_CRYPTO_UNIVERSE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MARKET_THESIS_MAX_RESPONSE_BYTES = 512 * 1024
_DAILY_SUMMARY_MAX_RESPONSE_BYTES = 128 * 1024
_PLAYBOOK_VALIDATION_MAX_RESPONSE_BYTES = 128 * 1024
_CONTINUATION_VALIDATION_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_COT_CATALOG_MAX_RESPONSE_BYTES = 64 * 1024
_COT_DETAIL_MAX_RESPONSE_BYTES = 512 * 1024
_MARKET_THESIS_VALIDATION_MAX_RESPONSE_BYTES = 128 * 1024
_MARKET_THESIS_REGIME_HISTORY_MAX_RESPONSE_BYTES = 128 * 1024
_MONEY_FLOW_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_SECTOR_ROTATION_MAX_RESPONSE_BYTES = 512 * 1024
_REVERSAL_RADAR_MAX_RESPONSE_BYTES = 512 * 1024
_REVERSAL_RADAR_VALIDATION_MAX_RESPONSE_BYTES = 32 * 1024
_OVERSOLD_REVERSAL_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_OVERSOLD_REVERSAL_VALIDATION_MAX_RESPONSE_BYTES = 32 * 1024
_RANKED_CANDIDATES_MAX_RESPONSE_BYTES = 512 * 1024
_SCORED_CANDIDATES_MAX_RESPONSE_BYTES = 1024 * 1024
_SCORED_CANDIDATES_SCREENER_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_SOCIAL_INTELLIGENCE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_THEME_FLOW_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_THEME_FLOW_ANALYSIS_MAX_RESPONSE_BYTES = 512 * 1024
_KNOWLEDGE_GRAPH_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_THEME_TAXONOMY_MAX_RESPONSE_BYTES = 128 * 1024
_THEME_DRILL_MAX_RESPONSE_BYTES = 256 * 1024
_INFLUENCER_ROSTER_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_OPTIONS_FLOW_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
_DEADLINE_SECONDS = 1.0
_TIMEOUT = httpx.Timeout(connect=0.25, read=0.25, write=0.25, pool=0.25)
_SCHEDULES_ENVELOPE = TypeAdapter(
    ArtifactAvailable[SchedulesData] | ArtifactUnavailable
)
_AI_UPDATES_ENVELOPE = TypeAdapter(
    ArtifactAvailable[AiUpdatesData] | ArtifactUnavailable
)
_FUND_CATALOG_ENVELOPE = TypeAdapter(
    ArtifactAvailable[FundCatalogData] | ArtifactUnavailable
)
_IV_HISTORY_ENVELOPE = TypeAdapter(
    ArtifactAvailable[IvHistoryData] | ArtifactUnavailable
)
_OPTIONS_FLOW_FEED_ENVELOPE = TypeAdapter(
    ArtifactAvailable[OptionsFlowFeedData] | ArtifactUnavailable
)
_CRYPTO_UNIVERSE_ENVELOPE = TypeAdapter(
    ArtifactAvailable[CryptoUniverseData] | ArtifactUnavailable
)
_MARKET_THESIS_ENVELOPE = TypeAdapter(
    ArtifactAvailable[MarketThesisData] | ArtifactUnavailable
)
_DAILY_SUMMARY_ENVELOPE = TypeAdapter(
    ArtifactAvailable[DailySummaryData] | ArtifactUnavailable
)
_PLAYBOOK_VALIDATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[PlaybookValidationData] | ArtifactUnavailable
)
_CONTINUATION_VALIDATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ContinuationValidationData] | ArtifactUnavailable
)
_COT_CATALOG_ENVELOPE = TypeAdapter(
    ArtifactAvailable[CotCatalogData] | ArtifactUnavailable
)
_COT_DETAIL_ENVELOPE = TypeAdapter(
    ArtifactAvailable[CotReportData] | ArtifactUnavailable
)
_MARKET_THESIS_VALIDATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[MarketThesisValidationData] | ArtifactUnavailable
)
_MARKET_THESIS_REGIME_HISTORY_ENVELOPE = TypeAdapter(
    ArtifactAvailable[MarketThesisRegimeHistoryData] | ArtifactUnavailable
)
_MONEY_FLOW_ENVELOPE = TypeAdapter(
    ArtifactAvailable[MoneyFlowData] | ArtifactUnavailable
)
_SECTOR_ROTATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[SectorRotationData] | ArtifactUnavailable
)
_REVERSAL_RADAR_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ReversalRadarData] | ArtifactUnavailable
)
_REVERSAL_RADAR_VALIDATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ReversalRadarValidationData] | ArtifactUnavailable
)
_OVERSOLD_REVERSAL_ENVELOPE = TypeAdapter(
    ArtifactAvailable[OversoldReversalData] | ArtifactUnavailable
)
_OVERSOLD_REVERSAL_VALIDATION_ENVELOPE = TypeAdapter(
    ArtifactAvailable[OversoldReversalValidationData] | ArtifactUnavailable
)
_RANKED_CANDIDATES_ENVELOPE = TypeAdapter(
    ArtifactAvailable[RankedCandidatesFeedData] | ArtifactUnavailable
)
_SCORED_CANDIDATES_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ScoredCandidatesFeedData] | ArtifactUnavailable
)
_SCORED_CANDIDATES_SCREENER_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ScoredCandidatesScreenerData] | ArtifactUnavailable
)
_SOCIAL_INTELLIGENCE_ENVELOPE = TypeAdapter(
    ArtifactAvailable[SocialIntelligenceData] | ArtifactUnavailable
)
_THEME_FLOW_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ThemeFlowData] | ArtifactUnavailable
)
_THEME_FLOW_ANALYSIS_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ThemeFlowAnalysisData] | ArtifactUnavailable
)
_KNOWLEDGE_GRAPH_ENVELOPE = TypeAdapter(
    ArtifactAvailable[KnowledgeGraphData] | ArtifactUnavailable
)
_THEME_TAXONOMY_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ThemeTaxonomyData] | ArtifactUnavailable
)
_THEME_DRILL_ENVELOPE = TypeAdapter(
    ArtifactAvailable[ThemeDrillData] | ArtifactUnavailable
)
_INFLUENCER_ROSTER_ENVELOPE = TypeAdapter(
    ArtifactAvailable[InfluencerRosterData] | ArtifactUnavailable
)

ClientFailureReason: TypeAlias = Literal[
    "transport_error",
    "deadline_exceeded",
    "http_status",
    "invalid_media_type",
    "invalid_cache_control",
    "response_too_large",
    "invalid_envelope",
]
FixedReadResult: TypeAlias = bytes | ClientFailureReason


@dataclass(frozen=True, slots=True)
class SchedulesApiAvailable:
    schedules: tuple[ScheduleEntry, ...]


@dataclass(frozen=True, slots=True)
class SchedulesApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class SchedulesApiFailure:
    reason: ClientFailureReason


SchedulesApiResult: TypeAlias = (
    SchedulesApiAvailable | SchedulesApiUnavailable | SchedulesApiFailure
)


@dataclass(frozen=True, slots=True)
class AiUpdatesApiAvailable:
    updates: tuple[AiUpdateItem, ...]


@dataclass(frozen=True, slots=True)
class AiUpdatesApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class AiUpdatesApiFailure:
    reason: ClientFailureReason


AiUpdatesApiResult: TypeAlias = (
    AiUpdatesApiAvailable | AiUpdatesApiUnavailable | AiUpdatesApiFailure
)


@dataclass(frozen=True, slots=True)
class FundCatalogOption:
    display_name: str
    cik: str
    note: str


@dataclass(frozen=True, slots=True)
class FundCatalogApiAvailable:
    options: tuple[FundCatalogOption, ...]


@dataclass(frozen=True, slots=True)
class FundCatalogApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class FundCatalogApiFailure:
    reason: ClientFailureReason


FundCatalogApiResult: TypeAlias = (
    FundCatalogApiAvailable | FundCatalogApiUnavailable | FundCatalogApiFailure
)


@dataclass(frozen=True, slots=True)
class IvHistoryPoint:
    as_of: str
    iv: float


@dataclass(frozen=True, slots=True)
class IvHistoryApiAvailable:
    ticker: str
    points: tuple[IvHistoryPoint, ...]


@dataclass(frozen=True, slots=True)
class IvHistoryApiUnavailable:
    ticker: str
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class IvHistoryApiFailure:
    ticker: str
    reason: ClientFailureReason


@dataclass(frozen=True, slots=True)
class IvHistoryApiInvalidTicker:
    reason: Literal["invalid_ticker"] = "invalid_ticker"


IvHistoryApiResult: TypeAlias = (
    IvHistoryApiAvailable
    | IvHistoryApiUnavailable
    | IvHistoryApiFailure
    | IvHistoryApiInvalidTicker
)


@dataclass(frozen=True, slots=True)
class OptionsFlowApiAvailable:
    feed: OptionsFlowFeedData


@dataclass(frozen=True, slots=True)
class OptionsFlowApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class OptionsFlowApiFailure:
    reason: ClientFailureReason


OptionsFlowApiResult: TypeAlias = (
    OptionsFlowApiAvailable | OptionsFlowApiUnavailable | OptionsFlowApiFailure
)


@dataclass(frozen=True, slots=True)
class CryptoUniverseApiAvailable:
    snapshot: CryptoUniverseData


@dataclass(frozen=True, slots=True)
class CryptoUniverseApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class CryptoUniverseApiFailure:
    reason: ClientFailureReason


CryptoUniverseApiResult: TypeAlias = (
    CryptoUniverseApiAvailable
    | CryptoUniverseApiUnavailable
    | CryptoUniverseApiFailure
)


@dataclass(frozen=True, slots=True)
class RankedCandidatesApiAvailable:
    feed: RankedCandidatesFeedData


@dataclass(frozen=True, slots=True)
class RankedCandidatesApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class RankedCandidatesApiFailure:
    reason: ClientFailureReason


RankedCandidatesApiResult: TypeAlias = (
    RankedCandidatesApiAvailable
    | RankedCandidatesApiUnavailable
    | RankedCandidatesApiFailure
)


@dataclass(frozen=True, slots=True)
class ScoredCandidatesApiAvailable:
    feed: ScoredCandidatesFeedData


@dataclass(frozen=True, slots=True)
class ScoredCandidatesApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ScoredCandidatesApiFailure:
    reason: ClientFailureReason


ScoredCandidatesApiResult: TypeAlias = (
    ScoredCandidatesApiAvailable
    | ScoredCandidatesApiUnavailable
    | ScoredCandidatesApiFailure
)


@dataclass(frozen=True, slots=True)
class ScoredCandidatesScreenerApiAvailable:
    snapshot: ScoredCandidatesScreenerData


@dataclass(frozen=True, slots=True)
class ScoredCandidatesScreenerApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ScoredCandidatesScreenerApiFailure:
    reason: ClientFailureReason


ScoredCandidatesScreenerApiResult: TypeAlias = (
    ScoredCandidatesScreenerApiAvailable
    | ScoredCandidatesScreenerApiUnavailable
    | ScoredCandidatesScreenerApiFailure
)


@dataclass(frozen=True, slots=True)
class MarketThesisApiAvailable:
    forecast: MarketThesisData


@dataclass(frozen=True, slots=True)
class MarketThesisApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class MarketThesisApiFailure:
    reason: ClientFailureReason


MarketThesisApiResult: TypeAlias = (
    MarketThesisApiAvailable
    | MarketThesisApiUnavailable
    | MarketThesisApiFailure
)


@dataclass(frozen=True, slots=True)
class DailySummaryApiAvailable:
    summary: DailySummaryData


@dataclass(frozen=True, slots=True)
class DailySummaryApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class DailySummaryApiFailure:
    reason: ClientFailureReason


DailySummaryApiResult: TypeAlias = (
    DailySummaryApiAvailable
    | DailySummaryApiUnavailable
    | DailySummaryApiFailure
)


@dataclass(frozen=True, slots=True)
class PlaybookValidationApiAvailable:
    summary: PlaybookValidationData


@dataclass(frozen=True, slots=True)
class PlaybookValidationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class PlaybookValidationApiFailure:
    reason: ClientFailureReason


PlaybookValidationApiResult: TypeAlias = (
    PlaybookValidationApiAvailable
    | PlaybookValidationApiUnavailable
    | PlaybookValidationApiFailure
)


@dataclass(frozen=True, slots=True)
class ContinuationValidationApiAvailable:
    report: ContinuationValidationData


@dataclass(frozen=True, slots=True)
class ContinuationValidationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ContinuationValidationApiFailure:
    reason: ClientFailureReason


ContinuationValidationApiResult: TypeAlias = (
    ContinuationValidationApiAvailable
    | ContinuationValidationApiUnavailable
    | ContinuationValidationApiFailure
)


@dataclass(frozen=True, slots=True)
class CotCatalogApiAvailable:
    catalog: CotCatalogData


@dataclass(frozen=True, slots=True)
class CotCatalogApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class CotCatalogApiFailure:
    reason: ClientFailureReason


CotCatalogApiResult: TypeAlias = (
    CotCatalogApiAvailable | CotCatalogApiUnavailable | CotCatalogApiFailure
)


@dataclass(frozen=True, slots=True)
class CotReportApiAvailable:
    report: CotReportData


@dataclass(frozen=True, slots=True)
class CotReportApiUnavailable:
    report_date: str
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class CotReportApiFailure:
    report_date: str
    reason: ClientFailureReason


@dataclass(frozen=True, slots=True)
class CotReportApiInvalidDate:
    report_date: str


CotReportApiResult: TypeAlias = (
    CotReportApiAvailable
    | CotReportApiUnavailable
    | CotReportApiFailure
    | CotReportApiInvalidDate
)


@dataclass(frozen=True, slots=True)
class MarketThesisValidationApiAvailable:
    summary: MarketThesisValidationData


@dataclass(frozen=True, slots=True)
class MarketThesisValidationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class MarketThesisValidationApiFailure:
    reason: ClientFailureReason


MarketThesisValidationApiResult: TypeAlias = (
    MarketThesisValidationApiAvailable
    | MarketThesisValidationApiUnavailable
    | MarketThesisValidationApiFailure
)


@dataclass(frozen=True, slots=True)
class MarketThesisRegimeHistoryApiAvailable:
    summary: MarketThesisRegimeHistoryData


@dataclass(frozen=True, slots=True)
class MarketThesisRegimeHistoryApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class MarketThesisRegimeHistoryApiFailure:
    reason: ClientFailureReason


MarketThesisRegimeHistoryApiResult: TypeAlias = (
    MarketThesisRegimeHistoryApiAvailable
    | MarketThesisRegimeHistoryApiUnavailable
    | MarketThesisRegimeHistoryApiFailure
)


@dataclass(frozen=True, slots=True)
class ReversalRadarApiAvailable:
    snapshot: ReversalRadarData


@dataclass(frozen=True, slots=True)
class ReversalRadarApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ReversalRadarApiFailure:
    reason: ClientFailureReason


ReversalRadarApiResult: TypeAlias = (
    ReversalRadarApiAvailable
    | ReversalRadarApiUnavailable
    | ReversalRadarApiFailure
)


@dataclass(frozen=True, slots=True)
class ReversalRadarValidationApiAvailable:
    summary: ReversalRadarValidationData


@dataclass(frozen=True, slots=True)
class ReversalRadarValidationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ReversalRadarValidationApiFailure:
    reason: ClientFailureReason


ReversalRadarValidationApiResult: TypeAlias = (
    ReversalRadarValidationApiAvailable
    | ReversalRadarValidationApiUnavailable
    | ReversalRadarValidationApiFailure
)


@dataclass(frozen=True, slots=True)
class OversoldReversalApiAvailable:
    snapshot: OversoldReversalData


@dataclass(frozen=True, slots=True)
class OversoldReversalApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class OversoldReversalApiFailure:
    reason: ClientFailureReason


OversoldReversalApiResult: TypeAlias = (
    OversoldReversalApiAvailable
    | OversoldReversalApiUnavailable
    | OversoldReversalApiFailure
)


@dataclass(frozen=True, slots=True)
class OversoldReversalValidationApiAvailable:
    summary: OversoldReversalValidationData


@dataclass(frozen=True, slots=True)
class OversoldReversalValidationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class OversoldReversalValidationApiFailure:
    reason: ClientFailureReason


OversoldReversalValidationApiResult: TypeAlias = (
    OversoldReversalValidationApiAvailable
    | OversoldReversalValidationApiUnavailable
    | OversoldReversalValidationApiFailure
)


@dataclass(frozen=True, slots=True)
class SocialIntelligenceApiAvailable:
    snapshot: SocialIntelligenceData


@dataclass(frozen=True, slots=True)
class SocialIntelligenceApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class SocialIntelligenceApiFailure:
    reason: ClientFailureReason


SocialIntelligenceApiResult: TypeAlias = (
    SocialIntelligenceApiAvailable
    | SocialIntelligenceApiUnavailable
    | SocialIntelligenceApiFailure
)


@dataclass(frozen=True, slots=True)
class MoneyFlowApiAvailable:
    snapshot: MoneyFlowData


@dataclass(frozen=True, slots=True)
class MoneyFlowApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class MoneyFlowApiFailure:
    reason: ClientFailureReason


MoneyFlowApiResult: TypeAlias = (
    MoneyFlowApiAvailable | MoneyFlowApiUnavailable | MoneyFlowApiFailure
)


@dataclass(frozen=True, slots=True)
class SectorRotationApiAvailable:
    snapshot: SectorRotationData


@dataclass(frozen=True, slots=True)
class SectorRotationApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class SectorRotationApiFailure:
    reason: ClientFailureReason


SectorRotationApiResult: TypeAlias = (
    SectorRotationApiAvailable
    | SectorRotationApiUnavailable
    | SectorRotationApiFailure
)


@dataclass(frozen=True, slots=True)
class ThemeFlowApiAvailable:
    snapshot: ThemeFlowData


@dataclass(frozen=True, slots=True)
class ThemeFlowApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ThemeFlowApiFailure:
    reason: ClientFailureReason


ThemeFlowApiResult: TypeAlias = (
    ThemeFlowApiAvailable | ThemeFlowApiUnavailable | ThemeFlowApiFailure
)


@dataclass(frozen=True, slots=True)
class ThemeFlowAnalysisApiAvailable:
    analysis: ThemeFlowAnalysisData


@dataclass(frozen=True, slots=True)
class ThemeFlowAnalysisApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ThemeFlowAnalysisApiFailure:
    reason: ClientFailureReason


ThemeFlowAnalysisApiResult: TypeAlias = (
    ThemeFlowAnalysisApiAvailable
    | ThemeFlowAnalysisApiUnavailable
    | ThemeFlowAnalysisApiFailure
)


@dataclass(frozen=True, slots=True)
class KnowledgeGraphApiAvailable:
    graph: KnowledgeGraphData


@dataclass(frozen=True, slots=True)
class KnowledgeGraphApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class KnowledgeGraphApiFailure:
    reason: ClientFailureReason


KnowledgeGraphApiResult: TypeAlias = (
    KnowledgeGraphApiAvailable
    | KnowledgeGraphApiUnavailable
    | KnowledgeGraphApiFailure
)


@dataclass(frozen=True, slots=True)
class ThemeTaxonomyApiAvailable:
    themes: tuple[ThemeTaxonomyItem, ...]


@dataclass(frozen=True, slots=True)
class ThemeTaxonomyApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ThemeTaxonomyApiFailure:
    reason: ClientFailureReason


ThemeTaxonomyApiResult: TypeAlias = (
    ThemeTaxonomyApiAvailable
    | ThemeTaxonomyApiUnavailable
    | ThemeTaxonomyApiFailure
)


@dataclass(frozen=True, slots=True)
class ThemeDrillApiAvailable:
    drill: ThemeDrillData


@dataclass(frozen=True, slots=True)
class ThemeDrillApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class ThemeDrillApiFailure:
    reason: ClientFailureReason


ThemeDrillApiResult: TypeAlias = (
    ThemeDrillApiAvailable | ThemeDrillApiUnavailable | ThemeDrillApiFailure
)


@dataclass(frozen=True, slots=True)
class InfluencerRosterApiAvailable:
    roster: InfluencerRosterData


@dataclass(frozen=True, slots=True)
class InfluencerRosterApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class InfluencerRosterApiFailure:
    reason: ClientFailureReason


InfluencerRosterApiResult: TypeAlias = (
    InfluencerRosterApiAvailable
    | InfluencerRosterApiUnavailable
    | InfluencerRosterApiFailure
)


def _is_json_media_type(value: str) -> bool:
    media_type, _, _parameters = value.partition(";")
    return media_type.strip().casefold() == "application/json"


def _has_no_store(value: str) -> bool:
    return any(
        directive.strip().casefold() == "no-store"
        for directive in value.split(",")
    )


def _parse_artifact_generated_at(value: str) -> datetime | None:
    """Parse a strict feed timestamp as an instant on Python 3.10."""

    if _OPTIONS_FLOW_RFC3339_RE.fullmatch(value) is None:
        return None
    normalized = f"{value[:10]}T{value[11:]}"
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _raw_options_flow_generated_at(body: bytes) -> str | None:
    """Retain metadata precision before Pydantic converts it to ``datetime``."""

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("generatedAt")
    return value if isinstance(value, str) else None


async def _read_fixed_json(
    *,
    url: str,
    max_response_bytes: int,
    transport: httpx.AsyncBaseTransport | None,
) -> FixedReadResult:
    client_options: dict[str, object] = {
        "trust_env": False,
        "follow_redirects": False,
        "timeout": _TIMEOUT,
    }
    if transport is not None:
        client_options["transport"] = transport

    try:
        async with httpx.AsyncClient(**client_options) as client:
            async with client.stream(
                "GET",
                url,
                headers={"Accept": "application/json"},
            ) as response:
                if response.status_code != 200:
                    return "http_status"
                if not _is_json_media_type(response.headers.get("Content-Type", "")):
                    return "invalid_media_type"
                if not _has_no_store(response.headers.get("Cache-Control", "")):
                    return "invalid_cache_control"

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > max_response_bytes:
                        return "response_too_large"
                    body.extend(chunk)
    except httpx.RequestError:
        return "transport_error"

    return bytes(body)


async def _request_schedules(
    transport: httpx.AsyncBaseTransport | None,
) -> SchedulesApiResult:
    body = await _read_fixed_json(
        url=_SCHEDULES_URL,
        max_response_bytes=_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return SchedulesApiFailure(body)

    try:
        envelope = _SCHEDULES_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return SchedulesApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "system.schedules"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return SchedulesApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return SchedulesApiAvailable(tuple(envelope.data.schedules))
    return SchedulesApiUnavailable(envelope.reason)


async def _request_ai_updates(
    transport: httpx.AsyncBaseTransport | None,
) -> AiUpdatesApiResult:
    body = await _read_fixed_json(
        url=_AI_UPDATES_URL,
        max_response_bytes=_AI_UPDATES_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return AiUpdatesApiFailure(body)

    try:
        envelope = _AI_UPDATES_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return AiUpdatesApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "system.ai-updates"
        or envelope.meta.generated_at is not None
    ):
        return AiUpdatesApiFailure("invalid_envelope")

    if isinstance(envelope, ArtifactAvailable):
        expected_as_of = max(
            (update.date for update in envelope.data.updates),
            default=None,
        )
        actual_as_of = (
            envelope.meta.as_of.isoformat()
            if envelope.meta.as_of is not None
            else None
        )
        if actual_as_of != expected_as_of:
            return AiUpdatesApiFailure("invalid_envelope")
        return AiUpdatesApiAvailable(tuple(envelope.data.updates))

    if envelope.meta.as_of is not None:
        return AiUpdatesApiFailure("invalid_envelope")
    return AiUpdatesApiUnavailable(envelope.reason)


async def _request_fund_catalog(
    transport: httpx.AsyncBaseTransport | None,
) -> FundCatalogApiResult:
    body = await _read_fixed_json(
        url=_FUND_CATALOG_URL,
        max_response_bytes=_FUND_CATALOG_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return FundCatalogApiFailure(body)

    try:
        envelope = _FUND_CATALOG_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return FundCatalogApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "institutions.funds"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return FundCatalogApiFailure("invalid_envelope")

    if isinstance(envelope, ArtifactAvailable):
        return FundCatalogApiAvailable(
            tuple(
                FundCatalogOption(display_name, entry.cik, entry.note)
                for display_name, entry in envelope.data.funds.items()
            )
        )
    return FundCatalogApiUnavailable(envelope.reason)


async def _request_iv_history(
    ticker: str,
    transport: httpx.AsyncBaseTransport | None,
) -> IvHistoryApiResult:
    body = await _read_fixed_json(
        url=f"{_IV_HISTORY_URL_PREFIX}{ticker}",
        max_response_bytes=_IV_HISTORY_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return IvHistoryApiFailure(ticker, body)

    try:
        envelope = _IV_HISTORY_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return IvHistoryApiFailure(ticker, "invalid_envelope")

    if (
        envelope.meta.source_id != "options.iv-history"
        or envelope.meta.generated_at is not None
    ):
        return IvHistoryApiFailure(ticker, "invalid_envelope")

    if isinstance(envelope, ArtifactAvailable):
        expected_as_of = max(envelope.data.series, default=None)
        if (
            envelope.data.ticker != ticker
            or envelope.meta.as_of != expected_as_of
        ):
            return IvHistoryApiFailure(ticker, "invalid_envelope")
        return IvHistoryApiAvailable(
            ticker,
            tuple(
                IvHistoryPoint(as_of.isoformat(), iv)
                for as_of, iv in envelope.data.series.items()
            ),
        )

    if envelope.meta.as_of is not None:
        return IvHistoryApiFailure(ticker, "invalid_envelope")
    return IvHistoryApiUnavailable(ticker, envelope.reason)


async def _request_options_flow(
    transport: httpx.AsyncBaseTransport | None,
) -> OptionsFlowApiResult:
    body = await _read_fixed_json(
        url=_OPTIONS_FLOW_FEED_URL,
        max_response_bytes=_OPTIONS_FLOW_FEED_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return OptionsFlowApiFailure(body)

    try:
        envelope = _OPTIONS_FLOW_FEED_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return OptionsFlowApiFailure("invalid_envelope")

    if envelope.meta.source_id != "signals.options-flow.feed":
        return OptionsFlowApiFailure("invalid_envelope")

    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(
            envelope.data.generated_at
        )
        raw_meta_generated_at = _raw_options_flow_generated_at(body)
        meta_generated_at = (
            _parse_artifact_generated_at(raw_meta_generated_at)
            if raw_meta_generated_at is not None
            else None
        )
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of
            or envelope.meta.generated_at is None
            or generated_at is None
            or meta_generated_at is None
            or envelope.meta.generated_at != meta_generated_at
            or meta_generated_at != generated_at
        ):
            return OptionsFlowApiFailure("invalid_envelope")
        return OptionsFlowApiAvailable(envelope.data)

    if (
        envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return OptionsFlowApiFailure("invalid_envelope")
    return OptionsFlowApiUnavailable(envelope.reason)


async def _request_crypto_universe(
    transport: httpx.AsyncBaseTransport | None,
) -> CryptoUniverseApiResult:
    body = await _read_fixed_json(
        url=_CRYPTO_UNIVERSE_URL,
        max_response_bytes=_CRYPTO_UNIVERSE_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return CryptoUniverseApiFailure(body)

    try:
        envelope = _CRYPTO_UNIVERSE_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return CryptoUniverseApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "crypto.universe"
        or envelope.meta.generated_at is not None
    ):
        return CryptoUniverseApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.date
        ):
            return CryptoUniverseApiFailure("invalid_envelope")
        return CryptoUniverseApiAvailable(envelope.data)
    if envelope.meta.as_of is not None:
        return CryptoUniverseApiFailure("invalid_envelope")
    return CryptoUniverseApiUnavailable(envelope.reason)


async def _request_market_thesis(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisApiResult:
    body = await _read_fixed_json(
        url=_MARKET_THESIS_URL,
        max_response_bytes=_MARKET_THESIS_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return MarketThesisApiFailure(body)

    try:
        envelope = _MARKET_THESIS_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return MarketThesisApiFailure("invalid_envelope")

    if envelope.meta.source_id != "market-context.market-thesis.latest":
        return MarketThesisApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(
            envelope.data.generated_at
        )
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return MarketThesisApiFailure("invalid_envelope")
        return MarketThesisApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return MarketThesisApiFailure("invalid_envelope")
    return MarketThesisApiUnavailable(envelope.reason)


async def _request_daily_summary(
    transport: httpx.AsyncBaseTransport | None,
) -> DailySummaryApiResult:
    body = await _read_fixed_json(
        url=_DAILY_SUMMARY_URL,
        max_response_bytes=_DAILY_SUMMARY_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return DailySummaryApiFailure(body)

    try:
        envelope = _DAILY_SUMMARY_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return DailySummaryApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "reports.daily-summary.latest"
        or envelope.meta.generated_at is not None
    ):
        return DailySummaryApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of_date
        ):
            return DailySummaryApiFailure("invalid_envelope")
        return DailySummaryApiAvailable(envelope.data)
    return DailySummaryApiUnavailable(envelope.reason)


async def _request_playbook_validation(
    transport: httpx.AsyncBaseTransport | None,
) -> PlaybookValidationApiResult:
    body = await _read_fixed_json(
        url=_PLAYBOOK_VALIDATION_URL,
        max_response_bytes=_PLAYBOOK_VALIDATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return PlaybookValidationApiFailure(body)

    try:
        envelope = _PLAYBOOK_VALIDATION_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return PlaybookValidationApiFailure("invalid_envelope")

    if (
        envelope.meta.source_id != "reports.playbook-validation.latest"
        or envelope.meta.as_of is not None
    ):
        return PlaybookValidationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return PlaybookValidationApiFailure("invalid_envelope")
        return PlaybookValidationApiAvailable(envelope.data)
    if envelope.meta.generated_at is not None:
        return PlaybookValidationApiFailure("invalid_envelope")
    return PlaybookValidationApiUnavailable(envelope.reason)


async def _request_continuation_validation(
    transport: httpx.AsyncBaseTransport | None,
) -> ContinuationValidationApiResult:
    body = await _read_fixed_json(
        url=_CONTINUATION_VALIDATION_URL,
        max_response_bytes=_CONTINUATION_VALIDATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ContinuationValidationApiFailure(body)
    try:
        envelope = _CONTINUATION_VALIDATION_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return ContinuationValidationApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id
        != "reports.continuation-validation.latest"
        or envelope.meta.as_of is not None
    ):
        return ContinuationValidationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return ContinuationValidationApiFailure("invalid_envelope")
        return ContinuationValidationApiAvailable(envelope.data)
    if envelope.meta.generated_at is not None:
        return ContinuationValidationApiFailure("invalid_envelope")
    return ContinuationValidationApiUnavailable(envelope.reason)


async def _request_cot_catalog(
    transport: httpx.AsyncBaseTransport | None,
) -> CotCatalogApiResult:
    body = await _read_fixed_json(
        url=_COT_CATALOG_URL,
        max_response_bytes=_COT_CATALOG_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return CotCatalogApiFailure(body)
    try:
        envelope = _COT_CATALOG_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return CotCatalogApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "reports.cot.catalog"
        or envelope.meta.generated_at is not None
    ):
        return CotCatalogApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        expected_as_of = (
            envelope.data.reports[0].report_date
            if envelope.data.reports
            else None
        )
        actual_as_of = (
            envelope.meta.as_of.isoformat()
            if envelope.meta.as_of is not None
            else None
        )
        if actual_as_of != expected_as_of:
            return CotCatalogApiFailure("invalid_envelope")
        return CotCatalogApiAvailable(envelope.data)
    if envelope.meta.as_of is not None:
        return CotCatalogApiFailure("invalid_envelope")
    return CotCatalogApiUnavailable(envelope.reason)


async def _request_cot_report(
    report_date: str,
    transport: httpx.AsyncBaseTransport | None,
) -> CotReportApiResult:
    body = await _read_fixed_json(
        url=f"{_COT_DETAIL_URL_PREFIX}{report_date}",
        max_response_bytes=_COT_DETAIL_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return CotReportApiFailure(report_date, body)
    try:
        envelope = _COT_DETAIL_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return CotReportApiFailure(report_date, "invalid_envelope")
    if envelope.meta.source_id != "reports.cot.detail":
        return CotReportApiFailure(report_date, "invalid_envelope")
    actual_as_of = (
        envelope.meta.as_of.isoformat()
        if envelope.meta.as_of is not None
        else None
    )
    if actual_as_of != report_date:
        return CotReportApiFailure(report_date, "invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(
            envelope.data.verified.price.retrieved_at
        )
        if (
            envelope.data.report_date != report_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return CotReportApiFailure(report_date, "invalid_envelope")
        return CotReportApiAvailable(envelope.data)
    if envelope.meta.generated_at is not None:
        return CotReportApiFailure(report_date, "invalid_envelope")
    return CotReportApiUnavailable(report_date, envelope.reason)


async def _request_market_thesis_validation(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisValidationApiResult:
    body = await _read_fixed_json(
        url=_MARKET_THESIS_VALIDATION_URL,
        max_response_bytes=_MARKET_THESIS_VALIDATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return MarketThesisValidationApiFailure(body)
    try:
        envelope = _MARKET_THESIS_VALIDATION_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return MarketThesisValidationApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "market-context.market-thesis.validation"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return MarketThesisValidationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return MarketThesisValidationApiAvailable(envelope.data)
    return MarketThesisValidationApiUnavailable(envelope.reason)


async def _request_market_thesis_regime_history(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisRegimeHistoryApiResult:
    body = await _read_fixed_json(
        url=_MARKET_THESIS_REGIME_HISTORY_URL,
        max_response_bytes=_MARKET_THESIS_REGIME_HISTORY_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return MarketThesisRegimeHistoryApiFailure(body)
    try:
        envelope = _MARKET_THESIS_REGIME_HISTORY_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return MarketThesisRegimeHistoryApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id
        != "market-context.market-thesis.regime-history"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return MarketThesisRegimeHistoryApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return MarketThesisRegimeHistoryApiAvailable(envelope.data)
    return MarketThesisRegimeHistoryApiUnavailable(envelope.reason)


async def _request_ranked_candidates(
    transport: httpx.AsyncBaseTransport | None,
) -> RankedCandidatesApiResult:
    body = await _read_fixed_json(
        url=_RANKED_CANDIDATES_URL,
        max_response_bytes=_RANKED_CANDIDATES_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return RankedCandidatesApiFailure(body)
    try:
        envelope = _RANKED_CANDIDATES_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return RankedCandidatesApiFailure("invalid_envelope")
    if envelope.meta.source_id != "candidates.ranked.feed":
        return RankedCandidatesApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.scan_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return RankedCandidatesApiFailure("invalid_envelope")
        return RankedCandidatesApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return RankedCandidatesApiFailure("invalid_envelope")
    return RankedCandidatesApiUnavailable(envelope.reason)


async def _request_scored_candidates(
    transport: httpx.AsyncBaseTransport | None,
) -> ScoredCandidatesApiResult:
    body = await _read_fixed_json(
        url=_SCORED_CANDIDATES_URL,
        max_response_bytes=_SCORED_CANDIDATES_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ScoredCandidatesApiFailure(body)
    try:
        envelope = _SCORED_CANDIDATES_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ScoredCandidatesApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "candidates.scored.feed"
        or envelope.meta.generated_at is not None
    ):
        return ScoredCandidatesApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.scan_date
        ):
            return ScoredCandidatesApiFailure("invalid_envelope")
        return ScoredCandidatesApiAvailable(envelope.data)
    if envelope.meta.as_of is not None:
        return ScoredCandidatesApiFailure("invalid_envelope")
    return ScoredCandidatesApiUnavailable(envelope.reason)


async def _request_scored_candidates_screener(
    transport: httpx.AsyncBaseTransport | None,
) -> ScoredCandidatesScreenerApiResult:
    body = await _read_fixed_json(
        url=_SCORED_CANDIDATES_SCREENER_URL,
        max_response_bytes=_SCORED_CANDIDATES_SCREENER_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ScoredCandidatesScreenerApiFailure(body)
    try:
        envelope = _SCORED_CANDIDATES_SCREENER_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return ScoredCandidatesScreenerApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "candidates.scored.screener"
        or envelope.meta.generated_at is not None
    ):
        return ScoredCandidatesScreenerApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.scan_date
        ):
            return ScoredCandidatesScreenerApiFailure("invalid_envelope")
        return ScoredCandidatesScreenerApiAvailable(envelope.data)
    if envelope.meta.as_of is not None:
        return ScoredCandidatesScreenerApiFailure("invalid_envelope")
    return ScoredCandidatesScreenerApiUnavailable(envelope.reason)


async def _request_reversal_radar(
    transport: httpx.AsyncBaseTransport | None,
) -> ReversalRadarApiResult:
    body = await _read_fixed_json(
        url=_REVERSAL_RADAR_URL,
        max_response_bytes=_REVERSAL_RADAR_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ReversalRadarApiFailure(body)
    try:
        envelope = _REVERSAL_RADAR_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ReversalRadarApiFailure("invalid_envelope")
    if envelope.meta.source_id != "signals.reversal-radar.latest":
        return ReversalRadarApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return ReversalRadarApiFailure("invalid_envelope")
        return ReversalRadarApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return ReversalRadarApiFailure("invalid_envelope")
    return ReversalRadarApiUnavailable(envelope.reason)


async def _request_reversal_radar_validation(
    transport: httpx.AsyncBaseTransport | None,
) -> ReversalRadarValidationApiResult:
    body = await _read_fixed_json(
        url=_REVERSAL_RADAR_VALIDATION_URL,
        max_response_bytes=_REVERSAL_RADAR_VALIDATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ReversalRadarValidationApiFailure(body)
    try:
        envelope = _REVERSAL_RADAR_VALIDATION_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return ReversalRadarValidationApiFailure("invalid_envelope")
    if envelope.meta.source_id != "signals.reversal-radar.validation":
        return ReversalRadarValidationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if envelope.meta.as_of is not None or envelope.meta.generated_at is None:
            return ReversalRadarValidationApiFailure("invalid_envelope")
        return ReversalRadarValidationApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return ReversalRadarValidationApiFailure("invalid_envelope")
    return ReversalRadarValidationApiUnavailable(envelope.reason)


async def _request_oversold_reversal(
    transport: httpx.AsyncBaseTransport | None,
) -> OversoldReversalApiResult:
    body = await _read_fixed_json(
        url=_OVERSOLD_REVERSAL_URL,
        max_response_bytes=_OVERSOLD_REVERSAL_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return OversoldReversalApiFailure(body)
    try:
        envelope = _OVERSOLD_REVERSAL_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return OversoldReversalApiFailure("invalid_envelope")
    if envelope.meta.source_id != "signals.oversold-reversal.latest":
        return OversoldReversalApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return OversoldReversalApiFailure("invalid_envelope")
        return OversoldReversalApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return OversoldReversalApiFailure("invalid_envelope")
    return OversoldReversalApiUnavailable(envelope.reason)


async def _request_oversold_reversal_validation(
    transport: httpx.AsyncBaseTransport | None,
) -> OversoldReversalValidationApiResult:
    body = await _read_fixed_json(
        url=_OVERSOLD_REVERSAL_VALIDATION_URL,
        max_response_bytes=_OVERSOLD_REVERSAL_VALIDATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return OversoldReversalValidationApiFailure(body)
    try:
        envelope = _OVERSOLD_REVERSAL_VALIDATION_ENVELOPE.validate_json(
            body, strict=True
        )
    except (ValidationError, ValueError):
        return OversoldReversalValidationApiFailure("invalid_envelope")
    if envelope.meta.source_id != "signals.oversold-reversal.validation":
        return OversoldReversalValidationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if envelope.meta.as_of is not None or envelope.meta.generated_at is None:
            return OversoldReversalValidationApiFailure("invalid_envelope")
        return OversoldReversalValidationApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return OversoldReversalValidationApiFailure("invalid_envelope")
    return OversoldReversalValidationApiUnavailable(envelope.reason)


async def _request_social_intelligence(
    transport: httpx.AsyncBaseTransport | None,
) -> SocialIntelligenceApiResult:
    body = await _read_fixed_json(
        url=_SOCIAL_INTELLIGENCE_URL,
        max_response_bytes=_SOCIAL_INTELLIGENCE_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return SocialIntelligenceApiFailure(body)
    try:
        envelope = _SOCIAL_INTELLIGENCE_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return SocialIntelligenceApiFailure("invalid_envelope")
    if envelope.meta.source_id != "social.intelligence.latest":
        return SocialIntelligenceApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return SocialIntelligenceApiFailure("invalid_envelope")
        return SocialIntelligenceApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return SocialIntelligenceApiFailure("invalid_envelope")
    return SocialIntelligenceApiUnavailable(envelope.reason)


async def _request_money_flow(
    transport: httpx.AsyncBaseTransport | None,
) -> MoneyFlowApiResult:
    body = await _read_fixed_json(
        url=_MONEY_FLOW_URL,
        max_response_bytes=_MONEY_FLOW_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return MoneyFlowApiFailure(body)
    try:
        envelope = _MONEY_FLOW_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return MoneyFlowApiFailure("invalid_envelope")
    if envelope.meta.source_id != "market-context.money-flow.latest":
        return MoneyFlowApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of_date
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return MoneyFlowApiFailure("invalid_envelope")
        return MoneyFlowApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return MoneyFlowApiFailure("invalid_envelope")
    return MoneyFlowApiUnavailable(envelope.reason)


async def _request_sector_rotation(
    transport: httpx.AsyncBaseTransport | None,
) -> SectorRotationApiResult:
    body = await _read_fixed_json(
        url=_SECTOR_ROTATION_URL,
        max_response_bytes=_SECTOR_ROTATION_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return SectorRotationApiFailure(body)
    try:
        envelope = _SECTOR_ROTATION_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return SectorRotationApiFailure("invalid_envelope")
    if envelope.meta.source_id != "market-context.sector-rotation.latest":
        return SectorRotationApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of
            or envelope.meta.generated_at is None
        ):
            return SectorRotationApiFailure("invalid_envelope")
        return SectorRotationApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return SectorRotationApiFailure("invalid_envelope")
    return SectorRotationApiUnavailable(envelope.reason)


async def _request_theme_flow(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeFlowApiResult:
    body = await _read_fixed_json(
        url=_THEME_FLOW_URL,
        max_response_bytes=_THEME_FLOW_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ThemeFlowApiFailure(body)
    try:
        envelope = _THEME_FLOW_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ThemeFlowApiFailure("invalid_envelope")
    if envelope.meta.source_id != "market-context.theme-flow.latest":
        return ThemeFlowApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return ThemeFlowApiFailure("invalid_envelope")
        return ThemeFlowApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return ThemeFlowApiFailure("invalid_envelope")
    return ThemeFlowApiUnavailable(envelope.reason)


async def _request_theme_flow_analysis(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeFlowAnalysisApiResult:
    body = await _read_fixed_json(
        url=_THEME_FLOW_ANALYSIS_URL,
        max_response_bytes=_THEME_FLOW_ANALYSIS_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ThemeFlowAnalysisApiFailure(body)
    try:
        envelope = _THEME_FLOW_ANALYSIS_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ThemeFlowAnalysisApiFailure("invalid_envelope")
    if envelope.meta.source_id != "market-context.theme-flow.analysis":
        return ThemeFlowAnalysisApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        generated_at = _parse_artifact_generated_at(envelope.data.generated_at)
        if (
            envelope.meta.as_of is None
            or envelope.meta.as_of.isoformat() != envelope.data.as_of
            or envelope.meta.generated_at is None
            or generated_at is None
            or envelope.meta.generated_at != generated_at
        ):
            return ThemeFlowAnalysisApiFailure("invalid_envelope")
        return ThemeFlowAnalysisApiAvailable(envelope.data)
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return ThemeFlowAnalysisApiFailure("invalid_envelope")
    return ThemeFlowAnalysisApiUnavailable(envelope.reason)


async def _request_knowledge_graph(
    transport: httpx.AsyncBaseTransport | None,
) -> KnowledgeGraphApiResult:
    body = await _read_fixed_json(
        url=_KNOWLEDGE_GRAPH_URL,
        max_response_bytes=_KNOWLEDGE_GRAPH_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return KnowledgeGraphApiFailure(body)
    try:
        envelope = _KNOWLEDGE_GRAPH_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return KnowledgeGraphApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "knowledge.graph"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return KnowledgeGraphApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return KnowledgeGraphApiAvailable(envelope.data)
    return KnowledgeGraphApiUnavailable(envelope.reason)


async def _request_theme_taxonomy(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeTaxonomyApiResult:
    body = await _read_fixed_json(
        url=_THEME_TAXONOMY_URL,
        max_response_bytes=_THEME_TAXONOMY_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ThemeTaxonomyApiFailure(body)
    try:
        envelope = _THEME_TAXONOMY_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ThemeTaxonomyApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "watchlists.theme-taxonomy"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return ThemeTaxonomyApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return ThemeTaxonomyApiAvailable(tuple(envelope.data.themes))
    return ThemeTaxonomyApiUnavailable(envelope.reason)


async def _request_theme_drill(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeDrillApiResult:
    body = await _read_fixed_json(
        url=_THEME_DRILL_URL,
        max_response_bytes=_THEME_DRILL_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return ThemeDrillApiFailure(body)
    try:
        envelope = _THEME_DRILL_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return ThemeDrillApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "market-context.theme-drill"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return ThemeDrillApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return ThemeDrillApiAvailable(envelope.data)
    return ThemeDrillApiUnavailable(envelope.reason)


async def _request_influencer_roster(
    transport: httpx.AsyncBaseTransport | None,
) -> InfluencerRosterApiResult:
    body = await _read_fixed_json(
        url=_INFLUENCER_ROSTER_URL,
        max_response_bytes=_INFLUENCER_ROSTER_MAX_RESPONSE_BYTES,
        transport=transport,
    )
    if isinstance(body, str):
        return InfluencerRosterApiFailure(body)
    try:
        envelope = _INFLUENCER_ROSTER_ENVELOPE.validate_json(body, strict=True)
    except (ValidationError, ValueError):
        return InfluencerRosterApiFailure("invalid_envelope")
    if (
        envelope.meta.source_id != "social.influencers.roster"
        or envelope.meta.as_of is not None
        or envelope.meta.generated_at is not None
    ):
        return InfluencerRosterApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        return InfluencerRosterApiAvailable(envelope.data)
    return InfluencerRosterApiUnavailable(envelope.reason)


async def _request_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> SchedulesApiResult:
    return await asyncio.wait_for(
        _request_schedules(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_ai_updates_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> AiUpdatesApiResult:
    return await asyncio.wait_for(
        _request_ai_updates(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_fund_catalog_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> FundCatalogApiResult:
    return await asyncio.wait_for(
        _request_fund_catalog(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_iv_history_with_deadline(
    ticker: str,
    transport: httpx.AsyncBaseTransport | None,
) -> IvHistoryApiResult:
    return await asyncio.wait_for(
        _request_iv_history(ticker, transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_options_flow_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> OptionsFlowApiResult:
    return await asyncio.wait_for(
        _request_options_flow(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_crypto_universe_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> CryptoUniverseApiResult:
    return await asyncio.wait_for(
        _request_crypto_universe(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_market_thesis_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisApiResult:
    return await asyncio.wait_for(
        _request_market_thesis(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_daily_summary_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> DailySummaryApiResult:
    return await asyncio.wait_for(
        _request_daily_summary(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_playbook_validation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> PlaybookValidationApiResult:
    return await asyncio.wait_for(
        _request_playbook_validation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_continuation_validation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ContinuationValidationApiResult:
    return await asyncio.wait_for(
        _request_continuation_validation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_cot_catalog_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> CotCatalogApiResult:
    return await asyncio.wait_for(
        _request_cot_catalog(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_cot_report_with_deadline(
    report_date: str,
    transport: httpx.AsyncBaseTransport | None,
) -> CotReportApiResult:
    return await asyncio.wait_for(
        _request_cot_report(report_date, transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_market_thesis_validation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisValidationApiResult:
    return await asyncio.wait_for(
        _request_market_thesis_validation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_market_thesis_regime_history_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> MarketThesisRegimeHistoryApiResult:
    return await asyncio.wait_for(
        _request_market_thesis_regime_history(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_ranked_candidates_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> RankedCandidatesApiResult:
    return await asyncio.wait_for(
        _request_ranked_candidates(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_scored_candidates_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ScoredCandidatesApiResult:
    return await asyncio.wait_for(
        _request_scored_candidates(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_scored_candidates_screener_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ScoredCandidatesScreenerApiResult:
    return await asyncio.wait_for(
        _request_scored_candidates_screener(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_reversal_radar_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ReversalRadarApiResult:
    return await asyncio.wait_for(
        _request_reversal_radar(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_reversal_radar_validation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ReversalRadarValidationApiResult:
    return await asyncio.wait_for(
        _request_reversal_radar_validation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_oversold_reversal_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> OversoldReversalApiResult:
    return await asyncio.wait_for(
        _request_oversold_reversal(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_oversold_reversal_validation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> OversoldReversalValidationApiResult:
    return await asyncio.wait_for(
        _request_oversold_reversal_validation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_social_intelligence_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> SocialIntelligenceApiResult:
    return await asyncio.wait_for(
        _request_social_intelligence(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_money_flow_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> MoneyFlowApiResult:
    return await asyncio.wait_for(
        _request_money_flow(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_sector_rotation_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> SectorRotationApiResult:
    return await asyncio.wait_for(
        _request_sector_rotation(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_theme_flow_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeFlowApiResult:
    return await asyncio.wait_for(
        _request_theme_flow(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_theme_flow_analysis_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeFlowAnalysisApiResult:
    return await asyncio.wait_for(
        _request_theme_flow_analysis(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_knowledge_graph_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> KnowledgeGraphApiResult:
    return await asyncio.wait_for(
        _request_knowledge_graph(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_theme_taxonomy_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeTaxonomyApiResult:
    return await asyncio.wait_for(
        _request_theme_taxonomy(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_theme_drill_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> ThemeDrillApiResult:
    return await asyncio.wait_for(
        _request_theme_drill(transport),
        timeout=_DEADLINE_SECONDS,
    )


async def _request_influencer_roster_with_deadline(
    transport: httpx.AsyncBaseTransport | None,
) -> InfluencerRosterApiResult:
    return await asyncio.wait_for(
        _request_influencer_roster(transport),
        timeout=_DEADLINE_SECONDS,
    )


def load_schedules(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SchedulesApiResult:
    """Read the fixed schedules endpoint once without exposing raw failures."""

    try:
        return asyncio.run(_request_with_deadline(transport))
    except asyncio.TimeoutError:
        return SchedulesApiFailure("deadline_exceeded")


def load_ai_updates(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AiUpdatesApiResult:
    """Read the fixed AI Updates endpoint once without exposing raw failures."""

    try:
        return asyncio.run(_request_ai_updates_with_deadline(transport))
    except asyncio.TimeoutError:
        return AiUpdatesApiFailure("deadline_exceeded")


def load_fund_catalog(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FundCatalogApiResult:
    """Read the fixed institutional fund catalog without raw failures."""

    try:
        return asyncio.run(_request_fund_catalog_with_deadline(transport))
    except asyncio.TimeoutError:
        return FundCatalogApiFailure("deadline_exceeded")


def load_iv_history(
    ticker: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> IvHistoryApiResult:
    """Read one normalized ticker's IV history without exposing raw failures."""

    normalized = normalize_ticker(ticker)
    if normalized is None:
        return IvHistoryApiInvalidTicker()

    try:
        return asyncio.run(
            _request_iv_history_with_deadline(normalized, transport)
        )
    except asyncio.TimeoutError:
        return IvHistoryApiFailure(normalized, "deadline_exceeded")


def load_options_flow(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OptionsFlowApiResult:
    """Read the fixed strict Options Flow feed without exposing raw failures."""

    try:
        return asyncio.run(_request_options_flow_with_deadline(transport))
    except asyncio.TimeoutError:
        return OptionsFlowApiFailure("deadline_exceeded")


def load_crypto_universe(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CryptoUniverseApiResult:
    """Read the fixed Crypto Universe endpoint without local fallback."""

    try:
        return asyncio.run(_request_crypto_universe_with_deadline(transport))
    except asyncio.TimeoutError:
        return CryptoUniverseApiFailure("deadline_exceeded")


def load_market_thesis(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MarketThesisApiResult:
    """Read the fixed strict Market Thesis latest endpoint without fallback."""

    try:
        return asyncio.run(_request_market_thesis_with_deadline(transport))
    except asyncio.TimeoutError:
        return MarketThesisApiFailure("deadline_exceeded")


def load_daily_summary(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> DailySummaryApiResult:
    """Read the strict newest Daily Summary projection without fallback."""

    try:
        return asyncio.run(_request_daily_summary_with_deadline(transport))
    except asyncio.TimeoutError:
        return DailySummaryApiFailure("deadline_exceeded")


def load_playbook_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PlaybookValidationApiResult:
    """Read the strict Playbook Validation presentation without fallback."""

    try:
        return asyncio.run(
            _request_playbook_validation_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return PlaybookValidationApiFailure("deadline_exceeded")


def load_continuation_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ContinuationValidationApiResult:
    """Read the strict Continuation Validation presentation without fallback."""

    try:
        return asyncio.run(
            _request_continuation_validation_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return ContinuationValidationApiFailure("deadline_exceeded")


def load_cot_catalog(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CotCatalogApiResult:
    """Read the bounded published COT catalog without local fallback."""

    try:
        return asyncio.run(_request_cot_catalog_with_deadline(transport))
    except asyncio.TimeoutError:
        return CotCatalogApiFailure("deadline_exceeded")


def load_cot_report(
    report_date: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CotReportApiResult:
    """Read one exact COT report pair without local fallback."""

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", report_date) is None:
        return CotReportApiInvalidDate(report_date)
    try:
        date.fromisoformat(report_date)
    except ValueError:
        return CotReportApiInvalidDate(report_date)
    try:
        return asyncio.run(
            _request_cot_report_with_deadline(report_date, transport)
        )
    except asyncio.TimeoutError:
        return CotReportApiFailure(report_date, "deadline_exceeded")


def load_market_thesis_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MarketThesisValidationApiResult:
    """Read the strict bounded Market Thesis validation summary."""

    try:
        return asyncio.run(
            _request_market_thesis_validation_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return MarketThesisValidationApiFailure("deadline_exceeded")


def load_market_thesis_regime_history(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MarketThesisRegimeHistoryApiResult:
    """Read the summary-only Market Thesis regime-history projection."""

    try:
        return asyncio.run(
            _request_market_thesis_regime_history_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return MarketThesisRegimeHistoryApiFailure("deadline_exceeded")


def load_ranked_candidates(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RankedCandidatesApiResult:
    """Read the strict ranked presentation feed without local fallback."""

    try:
        return asyncio.run(_request_ranked_candidates_with_deadline(transport))
    except asyncio.TimeoutError:
        return RankedCandidatesApiFailure("deadline_exceeded")


def load_scored_candidates(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ScoredCandidatesApiResult:
    """Read the strict scored presentation feed without local fallback."""

    try:
        return asyncio.run(_request_scored_candidates_with_deadline(transport))
    except asyncio.TimeoutError:
        return ScoredCandidatesApiFailure("deadline_exceeded")


def load_scored_candidates_screener(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ScoredCandidatesScreenerApiResult:
    """Read the strict US Screener scored projection without local fallback."""

    try:
        return asyncio.run(
            _request_scored_candidates_screener_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return ScoredCandidatesScreenerApiFailure("deadline_exceeded")


def load_reversal_radar(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ReversalRadarApiResult:
    """Read the strict persisted Reversal discovery snapshot without fallback."""

    try:
        return asyncio.run(_request_reversal_radar_with_deadline(transport))
    except asyncio.TimeoutError:
        return ReversalRadarApiFailure("deadline_exceeded")


def load_reversal_radar_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ReversalRadarValidationApiResult:
    """Read the strict bounded Reversal Radar forward-validation summary."""

    try:
        return asyncio.run(
            _request_reversal_radar_validation_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return ReversalRadarValidationApiFailure("deadline_exceeded")


def load_oversold_reversal(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OversoldReversalApiResult:
    """Read the strict persisted coiled-base snapshot without fallback."""

    try:
        return asyncio.run(_request_oversold_reversal_with_deadline(transport))
    except asyncio.TimeoutError:
        return OversoldReversalApiFailure("deadline_exceeded")


def load_oversold_reversal_validation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OversoldReversalValidationApiResult:
    """Read the strict bounded coiled-base forward-validation summary."""

    try:
        return asyncio.run(
            _request_oversold_reversal_validation_with_deadline(transport)
        )
    except asyncio.TimeoutError:
        return OversoldReversalValidationApiFailure("deadline_exceeded")


def load_social_intelligence(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SocialIntelligenceApiResult:
    """Read the strict persisted social snapshot without local fallback."""

    try:
        return asyncio.run(_request_social_intelligence_with_deadline(transport))
    except asyncio.TimeoutError:
        return SocialIntelligenceApiFailure("deadline_exceeded")


def load_money_flow(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> MoneyFlowApiResult:
    """Read the strict persisted Money Flow snapshot without local fallback."""

    try:
        return asyncio.run(_request_money_flow_with_deadline(transport))
    except asyncio.TimeoutError:
        return MoneyFlowApiFailure("deadline_exceeded")


def load_sector_rotation(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SectorRotationApiResult:
    """Read the strict latest Sector Rotation board without local fallback."""

    try:
        return asyncio.run(_request_sector_rotation_with_deadline(transport))
    except asyncio.TimeoutError:
        return SectorRotationApiFailure("deadline_exceeded")


def load_theme_flow(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ThemeFlowApiResult:
    """Read the strict current Theme Flow board without local fallback."""

    try:
        return asyncio.run(_request_theme_flow_with_deadline(transport))
    except asyncio.TimeoutError:
        return ThemeFlowApiFailure("deadline_exceeded")


def load_theme_flow_analysis(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ThemeFlowAnalysisApiResult:
    """Read the strict current-validation Theme Flow analysis."""

    try:
        return asyncio.run(_request_theme_flow_analysis_with_deadline(transport))
    except asyncio.TimeoutError:
        return ThemeFlowAnalysisApiFailure("deadline_exceeded")


def load_knowledge_graph(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> KnowledgeGraphApiResult:
    """Read the bounded public Knowledge Graph without local fallback."""

    try:
        return asyncio.run(_request_knowledge_graph_with_deadline(transport))
    except asyncio.TimeoutError:
        return KnowledgeGraphApiFailure("deadline_exceeded")


def load_theme_taxonomy(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ThemeTaxonomyApiResult:
    """Read the fixed public Watchlist taxonomy without local fallback."""

    try:
        return asyncio.run(_request_theme_taxonomy_with_deadline(transport))
    except asyncio.TimeoutError:
        return ThemeTaxonomyApiFailure("deadline_exceeded")


def load_theme_drill(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ThemeDrillApiResult:
    """Read the fixed public sector-to-theme drill without local fallback."""

    try:
        return asyncio.run(_request_theme_drill_with_deadline(transport))
    except asyncio.TimeoutError:
        return ThemeDrillApiFailure("deadline_exceeded")


def load_influencer_roster(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> InfluencerRosterApiResult:
    """Read the public roster projection without local fallback or seeding."""

    try:
        return asyncio.run(_request_influencer_roster_with_deadline(transport))
    except asyncio.TimeoutError:
        return InfluencerRosterApiFailure("deadline_exceeded")
