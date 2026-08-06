"""Pydantic boundary models for the fail-soft read API."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from math import isclose
from typing import Annotated, Generic, Literal, TypeAlias, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DataT = TypeVar("DataT")
UnavailableReason: TypeAlias = Literal[
    "missing",
    "invalid_json",
    "invalid_shape",
    "unreadable",
]
_FUND_NAME_RE = re.compile(r"^\S(?:.*\S)?$")
_TICKER_RE = re.compile(r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*$")
_AI_UPDATE_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_AI_UPDATE_LINK_PATTERN = (
    r"^https://[^/@?#\s\x00-\x1f\x7f]+(?:[/?#][^\s\x00-\x1f\x7f]*)?$"
)
_AI_UPDATE_LINK_RE = re.compile(_AI_UPDATE_LINK_PATTERN)
_AI_UPDATE_TAG_PATTERN = r"^\S(?:[\s\S]*\S)?$"
_CRYPTO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_CRYPTO_SYMBOL_PATTERN = r"^[^\s\x00-\x1f\x7f:./\\]{2,30}$"
_CRYPTO_BASE_PATTERN = r"^[^\s\x00-\x1f\x7f:./\\]{1,30}$"
_SCHEDULE_IDENTIFIER_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
_SCHEDULE_REQUIRED_TEXT_PATTERN = r"^\S(?:[\s\S]*\S)?$"
_SCHEDULE_OPTIONAL_TEXT_PATTERN = r"^(?:|\S(?:[\s\S]*\S)?)$"
_OPTIONS_FLOW_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_OPTIONS_FLOW_DATE_SCHEMA_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
_OPTIONS_FLOW_PROVIDER_PATTERN = r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$"
_OPTIONS_FLOW_PROVIDER_SCHEMA_PATTERN = (
    r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*(?![\s\S])"
)
_OPTIONS_FLOW_TICKER_PATTERN = r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$"
_OPTIONS_FLOW_TICKER_SCHEMA_PATTERN = (
    r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*(?![\s\S])"
)
_OPTIONS_FLOW_TAG_PATTERN = r"^\S(?:[\s\S]*\S)?$"
_OPTIONS_FLOW_TAG_SCHEMA_PATTERN = r"^\S(?:[\s\S]*\S)?(?![\s\S])"
_OPTIONS_FLOW_RFC3339_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
_OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)"
    r"(?![\s\S])"
)
_OPTIONS_FLOW_RFC3339_RE = re.compile(_OPTIONS_FLOW_RFC3339_PATTERN)
_MARKET_THESIS_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_MARKET_THESIS_DATE_SCHEMA_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
_MARKET_THESIS_RFC3339_PATTERN = _OPTIONS_FLOW_RFC3339_PATTERN
_MARKET_THESIS_RFC3339_SCHEMA_PATTERN = _OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN
_MARKET_THESIS_RFC3339_RE = re.compile(_MARKET_THESIS_RFC3339_PATTERN)
_MARKET_THESIS_TEXT_PATTERN = r"^\S(?:[\s\S]*\S)?$"
_MARKET_THESIS_TEXT_SCHEMA_PATTERN = r"^\S(?:[\s\S]*\S)?(?![\s\S])"
_MARKET_THESIS_SOURCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9:._^\-]*$"
_MARKET_THESIS_SOURCE_SCHEMA_PATTERN = (
    r"^[A-Za-z0-9][A-Za-z0-9:._^\-]*(?![\s\S])"
)
_DAILY_SUMMARY_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_DAILY_SUMMARY_DATE_SCHEMA_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
_DAILY_SUMMARY_TEXT_PATTERN = r"^\S(?:[\s\S]*\S)?$"
_DAILY_SUMMARY_TEXT_SCHEMA_PATTERN = r"^\S(?:[\s\S]*\S)?(?![\s\S])"
_SIGNAL_SNAPSHOT_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_SIGNAL_SNAPSHOT_DATE_SCHEMA_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
_SIGNAL_SNAPSHOT_RFC3339_PATTERN = _OPTIONS_FLOW_RFC3339_PATTERN
_SIGNAL_SNAPSHOT_RFC3339_SCHEMA_PATTERN = _OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN
_SIGNAL_SNAPSHOT_RFC3339_RE = re.compile(_SIGNAL_SNAPSHOT_RFC3339_PATTERN)
_SIGNAL_SNAPSHOT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+\-:]*$"
_SIGNAL_SNAPSHOT_ID_SCHEMA_PATTERN = (
    r"^[A-Za-z0-9][A-Za-z0-9._+\-:]*(?![\s\S])"
)
_SIGNAL_TICKER_PATTERN = r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$"
_SIGNAL_TICKER_SCHEMA_PATTERN = r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*(?![\s\S])"
_CANDIDATE_FEED_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_CANDIDATE_FEED_DATE_SCHEMA_PATTERN = r"^\d{4}-\d{2}-\d{2}(?![\s\S])"
_CANDIDATE_FEED_RFC3339_PATTERN = _OPTIONS_FLOW_RFC3339_PATTERN
_CANDIDATE_FEED_RFC3339_SCHEMA_PATTERN = _OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN
_CANDIDATE_FEED_RFC3339_RE = re.compile(_CANDIDATE_FEED_RFC3339_PATTERN)


def normalize_ticker(ticker: str) -> str | None:
    """Return an uppercase bounded ticker without sanitizing invalid input."""

    if not isinstance(ticker, str) or not (1 <= len(ticker) <= 15):
        return None
    if not _TICKER_RE.fullmatch(ticker):
        return None
    return ticker.upper()


class ArtifactMeta(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    source_id: str = Field(
        alias="sourceId",
        pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$",
    )
    as_of: date | None = Field(alias="asOf")
    generated_at: datetime | None = Field(alias="generatedAt")


class ArtifactAvailable(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    available: Literal[True]
    reason: Literal["ok"]
    data: DataT
    meta: ArtifactMeta


class ArtifactUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: Literal[False]
    reason: UnavailableReason
    data: None
    meta: ArtifactMeta


class ArtifactDataModel(BaseModel):
    """Compatibility DTO: validate anchors while preserving source fields."""

    model_config = ConfigDict(extra="allow")


class RankedCandidatesData(ArtifactDataModel):
    ranked_candidates: list[dict[str, object]]


class ScoredCandidatesData(ArtifactDataModel):
    all_scored: list[dict[str, object]]


CandidateFeedDate = Annotated[
    str,
    Field(
        pattern=_CANDIDATE_FEED_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _CANDIDATE_FEED_DATE_SCHEMA_PATTERN,
        },
    ),
]
CandidateFeedTimestamp = Annotated[
    str,
    Field(
        min_length=20,
        max_length=32,
        pattern=_CANDIDATE_FEED_RFC3339_PATTERN,
        json_schema_extra={
            "format": "date-time",
            "pattern": _CANDIDATE_FEED_RFC3339_SCHEMA_PATTERN,
        },
    ),
]
CandidateFeedTicker = Annotated[
    str,
    Field(
        min_length=1,
        max_length=15,
        pattern=_SIGNAL_TICKER_PATTERN,
        json_schema_extra={"pattern": _SIGNAL_TICKER_SCHEMA_PATTERN},
    ),
]
CandidateFeedScore = Annotated[
    float,
    Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False),
]
CandidateFeedText = Annotated[str, Field(max_length=1_000)]
CandidateFeedWarningList = Annotated[
    list[CandidateFeedText],
    Field(max_length=20),
]


def _validate_candidate_feed_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("scan_date must be a valid calendar date") from exc
    return value


def _validate_candidate_feed_timestamp(value: str) -> str:
    if _CANDIDATE_FEED_RFC3339_RE.fullmatch(value) is None:
        raise ValueError("generated_at must be a timezone-aware RFC 3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "generated_at must be a timezone-aware RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("generated_at must include a UTC offset")
    return value


class RankedCandidateScoreComponents(BaseModel):
    """Allowlisted ranking components rendered by Today Decision."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    technical_trend: CandidateFeedScore
    momentum_strength: CandidateFeedScore
    launch_signal: CandidateFeedScore
    liquidity_tradability: CandidateFeedScore
    overheat_risk_control: CandidateFeedScore


class RankedCandidateOptionsTradability(BaseModel):
    """Allowlisted options-gate summary rendered by Today Decision."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    status: Annotated[str, Field(min_length=1, max_length=100)] | None
    iv_percentile: (
        Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None
    )
    spread_pct: (
        Annotated[float, Field(ge=0, le=1_000_000, allow_inf_nan=False)] | None
    )
    flow_score: CandidateFeedScore | None
    warnings: CandidateFeedWarningList


class RankedCandidateFeedItem(BaseModel):
    """One exact ranked presentation row."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    rank_score: CandidateFeedScore
    last_price: (
        Annotated[float, Field(gt=0, le=10_000_000, allow_inf_nan=False)] | None
    )
    rank_bucket: Annotated[str, Field(min_length=1, max_length=100)]
    ret_5d: CandidateFeedScore | None
    ret_20d: CandidateFeedScore | None
    score_components: RankedCandidateScoreComponents
    options_tradability: RankedCandidateOptionsTradability | None
    warnings: CandidateFeedWarningList


class RankedCandidatesFeedData(ArtifactDataModel):
    """Strict bounded ranked presentation feed."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    scan_date: CandidateFeedDate
    generated_at: CandidateFeedTimestamp
    candidates: Annotated[list[RankedCandidateFeedItem], Field(max_length=100)]

    @field_validator("scan_date")
    @classmethod
    def validate_scan_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_candidates(self) -> "RankedCandidatesFeedData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("ranked candidate tickers must be unique")
        scores = [candidate.rank_score for candidate in self.candidates]
        if scores != sorted(scores, reverse=True):
            raise ValueError("ranked candidates must be ordered by rank_score")
        return self


class ScoredCandidateScores(BaseModel):
    """Seven allowlisted LLM scoring dimensions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    technical: CandidateFeedScore
    catalyst: CandidateFeedScore
    sentiment: CandidateFeedScore
    institutional: CandidateFeedScore
    sector_market: CandidateFeedScore
    options_flow: CandidateFeedScore
    analyst: CandidateFeedScore | None


class ScoredCandidateFeedItem(BaseModel):
    """One exact scored presentation row."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    verdict: Literal["REJECT", "WATCHLIST", "NEEDS_LAYER_2"]
    composite_score: CandidateFeedScore
    regime_adjusted_score: CandidateFeedScore
    scores: ScoredCandidateScores
    data_missing: CandidateFeedWarningList
    due_diligence_required: bool
    key_signals: CandidateFeedWarningList
    key_risks: CandidateFeedWarningList
    suggested_entry_zone: CandidateFeedText


class ScoredCandidatesFeedData(ArtifactDataModel):
    """Strict bounded scored presentation feed."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    scan_date: CandidateFeedDate
    candidates: Annotated[list[ScoredCandidateFeedItem], Field(max_length=100)]

    @field_validator("scan_date")
    @classmethod
    def validate_scan_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @model_validator(mode="after")
    def validate_candidates(self) -> "ScoredCandidatesFeedData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("scored candidate tickers must be unique")
        scores = [candidate.regime_adjusted_score for candidate in self.candidates]
        if scores != sorted(scores, reverse=True):
            raise ValueError(
                "scored candidates must be ordered by regime_adjusted_score"
            )
        return self


class ScoredScreenerRegimeContext(BaseModel):
    """Closed market-regime subset rendered by US Screener."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    spy_vs_50dma: CandidateFeedText | None
    spy_vs_200dma: CandidateFeedText | None
    vix_level: CandidateFeedScore | None
    vix_regime: CandidateFeedText | None
    global_score_multiplier: CandidateFeedScore
    active_themes: CandidateFeedWarningList
    regime_warnings: CandidateFeedWarningList


class ScoredScreenerTechnicalBreakdown(BaseModel):
    """Closed technical summary rendered below a screener score radar."""

    model_config = ConfigDict(extra="forbid", strict=True)

    pattern_type: CandidateFeedText | None
    macd_state: CandidateFeedText | None


class ScoredScreenerCandidateItem(BaseModel):
    """One exact candidate card for US Screener."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    verdict: Literal["WATCHLIST", "NEEDS_LAYER_2"]
    regime_adjusted_score: CandidateFeedScore
    scores: ScoredCandidateScores
    key_signals: CandidateFeedWarningList
    key_risks: CandidateFeedWarningList
    suggested_entry_zone: CandidateFeedText
    suggested_stop: CandidateFeedText | CandidateFeedScore | None
    suggested_size_pct: (
        Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None
    )
    anti_example_warning: CandidateFeedText | None
    data_missing: CandidateFeedWarningList
    technical_breakdown: ScoredScreenerTechnicalBreakdown | None


class ScoredCandidatesScreenerData(ArtifactDataModel):
    """Strict scored projection for the US Screener page slice."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    scan_date: CandidateFeedDate
    needs_layer2_count: Annotated[int, Field(ge=0, le=500)]
    watchlist_count: Annotated[int, Field(ge=0, le=500)]
    regime_context: ScoredScreenerRegimeContext
    candidates: Annotated[list[ScoredScreenerCandidateItem], Field(max_length=100)]

    @field_validator("scan_date")
    @classmethod
    def validate_scan_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @model_validator(mode="after")
    def validate_candidates(self) -> "ScoredCandidatesScreenerData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("screener candidate tickers must be unique")
        scores = [candidate.regime_adjusted_score for candidate in self.candidates]
        if scores != sorted(scores, reverse=True):
            raise ValueError(
                "screener candidates must be ordered by regime_adjusted_score"
            )
        return self


class OptionsFlowData(ArtifactDataModel):
    signals: list[dict[str, object]]


OptionsFlowDate = Annotated[
    str,
    Field(
        pattern=_OPTIONS_FLOW_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _OPTIONS_FLOW_DATE_SCHEMA_PATTERN,
        },
    ),
]
OptionsFlowTag = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=_OPTIONS_FLOW_TAG_PATTERN,
        json_schema_extra={"pattern": _OPTIONS_FLOW_TAG_SCHEMA_PATTERN},
    ),
]


class OptionsFlowFeedBiggest(BaseModel):
    """Strict public projection of the largest observed contract."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strike: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None
    notional: (
        Annotated[
            float,
            Field(
                gt=0,
                le=1_000_000_000_000_000,
                allow_inf_nan=False,
            ),
        ]
        | None
    )


class OptionsFlowFeedSignal(BaseModel):
    """One exact, source-ordered public Options Flow signal."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: Annotated[
        str,
        Field(
            min_length=1,
            max_length=15,
            pattern=_OPTIONS_FLOW_TICKER_PATTERN,
            json_schema_extra={"pattern": _OPTIONS_FLOW_TICKER_SCHEMA_PATTERN},
        ),
    ]
    direction: Literal["bullish", "bearish"]
    flow_score: Annotated[
        float,
        Field(ge=0, le=100, allow_inf_nan=False),
    ]
    est_notional_usd: Annotated[
        int,
        Field(ge=1, le=1_000_000_000_000_000),
    ]
    biggest: OptionsFlowFeedBiggest | None
    expiry: OptionsFlowDate | None
    max_voi: Annotated[
        float,
        Field(ge=0, le=1_000_000_000, allow_inf_nan=False),
    ]
    high_voi_strikes: Annotated[int, Field(ge=0, le=100_000)]
    call_put_ratio: (
        Annotated[
            float,
            Field(ge=0, le=1_000_000_000, allow_inf_nan=False),
        ]
        | None
    )
    put_call_ratio: (
        Annotated[
            float,
            Field(ge=0, le=1_000_000_000, allow_inf_nan=False),
        ]
        | None
    )
    tags: Annotated[
        list[OptionsFlowTag],
        Field(max_length=20, json_schema_extra={"uniqueItems": True}),
    ]

    @field_validator("expiry")
    @classmethod
    def validate_expiry(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("expiry must be a valid calendar date") from exc
        return value

    @field_validator("tags")
    @classmethod
    def validate_unique_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("tags must be unique")
        return value


class OptionsFlowFeedData(ArtifactDataModel):
    """Strict public Options Flow feed with runtime cross-field invariants."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    generated_at: Annotated[
        str,
        Field(
            min_length=20,
            max_length=32,
            pattern=_OPTIONS_FLOW_RFC3339_PATTERN,
            description="Timezone-aware RFC 3339 timestamp validated at runtime.",
            json_schema_extra={
                "format": "date-time",
                "pattern": _OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN,
            },
        ),
    ]
    as_of: Annotated[
        OptionsFlowDate,
        Field(description="Real calendar date validated at runtime."),
    ]
    provider: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            pattern=_OPTIONS_FLOW_PROVIDER_PATTERN,
            json_schema_extra={"pattern": _OPTIONS_FLOW_PROVIDER_SCHEMA_PATTERN},
        ),
    ]
    universe_size: Annotated[int, Field(ge=0, le=10_000)]
    min_notional: Annotated[int, Field(ge=1, le=1_000_000_000_000)]
    signal_count: Annotated[int, Field(ge=0, le=10_000)]
    signals: Annotated[
        list[OptionsFlowFeedSignal],
        Field(
            max_length=200,
            description=(
                "Source-ordered signals. Runtime validation requires unique ticker "
                "values, non-increasing flow_score order, and "
                "len(signals) <= signal_count <= universe_size; JSON Schema cannot "
                "express those property-based and cross-field invariants."
            ),
        ),
    ]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        if _OPTIONS_FLOW_RFC3339_RE.fullmatch(value) is None:
            raise ValueError("generated_at must be a timezone-aware RFC 3339 timestamp")
        normalized = (
            value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
        )
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                "generated_at must be a timezone-aware RFC 3339 timestamp"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("generated_at must include a UTC offset")
        return value

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("as_of must be a valid calendar date") from exc
        return value

    @model_validator(mode="after")
    def validate_feed_invariants(self) -> "OptionsFlowFeedData":
        tickers = [signal.ticker for signal in self.signals]
        if len(tickers) != len(set(tickers)):
            raise ValueError("signal tickers must be unique")
        if any(
            earlier.flow_score < later.flow_score
            for earlier, later in zip(self.signals, self.signals[1:])
        ):
            raise ValueError("signals must be ordered by non-increasing flow_score")
        if not len(self.signals) <= self.signal_count <= self.universe_size:
            raise ValueError(
                "feed counts must satisfy len(signals) <= signal_count <= universe_size"
            )
        return self


SignalSnapshotDate = Annotated[
    str,
    Field(
        pattern=_SIGNAL_SNAPSHOT_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _SIGNAL_SNAPSHOT_DATE_SCHEMA_PATTERN,
        },
    ),
]
SignalSnapshotTimestamp = Annotated[
    str,
    Field(
        min_length=20,
        max_length=32,
        pattern=_SIGNAL_SNAPSHOT_RFC3339_PATTERN,
        json_schema_extra={
            "format": "date-time",
            "pattern": _SIGNAL_SNAPSHOT_RFC3339_SCHEMA_PATTERN,
        },
    ),
]
SignalSnapshotIdentifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        pattern=_SIGNAL_SNAPSHOT_ID_PATTERN,
        json_schema_extra={"pattern": _SIGNAL_SNAPSHOT_ID_SCHEMA_PATTERN},
    ),
]
SignalTicker = Annotated[
    str,
    Field(
        min_length=1,
        max_length=15,
        pattern=_SIGNAL_TICKER_PATTERN,
        json_schema_extra={"pattern": _SIGNAL_TICKER_SCHEMA_PATTERN},
    ),
]


def _validate_signal_snapshot_date(value: str, field: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid calendar date") from exc
    return value


def _validate_signal_snapshot_timestamp(value: str) -> str:
    if _SIGNAL_SNAPSHOT_RFC3339_RE.fullmatch(value) is None:
        raise ValueError("generated_at must be a timezone-aware RFC 3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "generated_at must be a timezone-aware RFC 3339 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("generated_at must include a UTC offset")
    return value


class ReversalRadarCandidateRef(BaseModel):
    """Minimal persisted discovery reference; live detail is recomputed."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ticker: SignalTicker


class ReversalRadarData(ArtifactDataModel):
    """Strict public projection for the persisted Reversal discovery universe."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_date: SignalSnapshotDate
    generated_at: SignalSnapshotTimestamp
    lane_id: SignalSnapshotIdentifier
    universe: SignalSnapshotIdentifier
    match_count: Annotated[int, Field(ge=0, le=500)]
    candidates: Annotated[list[ReversalRadarCandidateRef], Field(max_length=500)]

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, value: str) -> str:
        return _validate_signal_snapshot_date(value, "as_of_date")

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_signal_snapshot_timestamp(value)

    @model_validator(mode="after")
    def validate_candidates(self) -> "ReversalRadarData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Reversal candidate tickers must be unique")
        if self.match_count != len(self.candidates):
            raise ValueError("match_count must equal the Reversal candidate count")
        return self


class OversoldReversalValidation(BaseModel):
    """Allowlisted validation headline rendered by the coiled-base page."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    pct_lift: Annotated[float, Field(ge=0, le=1_000, allow_inf_nan=False)]
    atr_neutral_lift: Annotated[
        float,
        Field(ge=0, le=1_000, allow_inf_nan=False),
    ]
    support: Annotated[int, Field(ge=0, le=1_000_000)]


class OversoldReversalCandidate(BaseModel):
    """Exact table row used by the coiled-base latest view."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: SignalTicker
    last_price: Annotated[float, Field(gt=0, le=10_000_000, allow_inf_nan=False)]
    rsi14: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    bb_width_pct: Annotated[float, Field(ge=0, le=10_000, allow_inf_nan=False)]
    pct_vs_ma200: Annotated[
        float,
        Field(ge=-100, le=100_000, allow_inf_nan=False),
    ]
    pct_from_52w_high: Annotated[
        float,
        Field(ge=-100, le=100_000, allow_inf_nan=False),
    ]
    avg_dollar_vol_m: Annotated[
        float,
        Field(ge=0, le=1_000_000_000, allow_inf_nan=False),
    ]


class OversoldReversalData(ArtifactDataModel):
    """Strict latest-display projection for the coiled-base lane."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_date: SignalSnapshotDate
    generated_at: SignalSnapshotTimestamp
    lane_id: SignalSnapshotIdentifier
    universe: SignalSnapshotIdentifier
    runway_independent: bool
    match_count: Annotated[int, Field(ge=0, le=2_000)]
    scanned: Annotated[int, Field(ge=0, le=100_000)]
    definition: Annotated[str, Field(min_length=1, max_length=2_000)]
    validation: OversoldReversalValidation
    validation_caveats: Annotated[
        list[Annotated[str, Field(max_length=1_000)]],
        Field(max_length=20),
    ]
    candidates: Annotated[list[OversoldReversalCandidate], Field(max_length=2_000)]
    note: Annotated[str, Field(max_length=2_000)]

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, value: str) -> str:
        return _validate_signal_snapshot_date(value, "as_of_date")

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_signal_snapshot_timestamp(value)

    @model_validator(mode="after")
    def validate_candidates(self) -> "OversoldReversalData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Oversold candidate tickers must be unique")
        if self.match_count != len(self.candidates):
            raise ValueError("match_count must equal the Oversold candidate count")
        if self.match_count > self.scanned:
            raise ValueError("match_count cannot exceed scanned")
        widths = [candidate.bb_width_pct for candidate in self.candidates]
        if widths != sorted(widths):
            raise ValueError("Oversold candidates must be ordered by bb_width_pct")
        return self


OversoldReversalValidationTierName = Literal[
    "+30%/20d",
    "+40%/40d",
    "+50%/60d",
]
OversoldReversalValidationVerdict = Literal[
    "PROVISIONAL — sample below threshold, indicative only",
    "MATURE",
]
OversoldReversalValidationProbability = Annotated[
    float,
    Field(ge=0, le=1, allow_inf_nan=False),
]


class OversoldReversalValidationTier(BaseModel):
    """One bounded public forward-validation tier."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    resolved: Annotated[int, Field(ge=0, le=10_000_000)]
    hits: Annotated[int, Field(ge=0, le=10_000_000)]
    hit_rate: OversoldReversalValidationProbability | None
    wilson90: Annotated[
        list[OversoldReversalValidationProbability],
        Field(min_length=2, max_length=2),
    ]

    @model_validator(mode="after")
    def validate_counts_and_rate(self) -> "OversoldReversalValidationTier":
        if self.hits > self.resolved:
            raise ValueError("validation hits cannot exceed resolved")
        expected_rate = None if self.resolved == 0 else self.hits / self.resolved
        if expected_rate is None:
            if self.hit_rate is not None:
                raise ValueError("zero resolved rows must have a null hit_rate")
        elif self.hit_rate is None or not isclose(
            self.hit_rate,
            expected_rate,
            rel_tol=0,
            abs_tol=0.00005,
        ):
            raise ValueError("validation hit_rate must match hits/resolved")
        if self.wilson90[0] > self.wilson90[1]:
            raise ValueError("validation wilson90 must be ordered")
        return self


class OversoldReversalValidationData(ArtifactDataModel):
    """Strict public projection of the coiled-base forward scoreboard."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    entries_accumulated: Annotated[int, Field(ge=0, le=10_000_000)]
    min_resolved_across_tiers: Annotated[int, Field(ge=0, le=10_000_000)]
    min_resolved_for_verdict: Annotated[int, Field(ge=1, le=10_000_000)]
    verdict: OversoldReversalValidationVerdict
    by_tier: Annotated[
        dict[OversoldReversalValidationTierName, OversoldReversalValidationTier],
        Field(min_length=3, max_length=3),
    ]

    @field_validator("by_tier")
    @classmethod
    def validate_tier_order(
        cls,
        value: dict[
            OversoldReversalValidationTierName,
            OversoldReversalValidationTier,
        ],
    ) -> dict[
        OversoldReversalValidationTierName,
        OversoldReversalValidationTier,
    ]:
        if tuple(value) != ("+30%/20d", "+40%/40d", "+50%/60d"):
            raise ValueError("validation tiers must use the fixed producer order")
        return value

    @model_validator(mode="after")
    def validate_conservative_verdict(self) -> "OversoldReversalValidationData":
        minimum = min(row.resolved for row in self.by_tier.values())
        if self.min_resolved_across_tiers != minimum:
            raise ValueError("minimum resolved count must match the tier rows")
        expected = (
            "MATURE"
            if minimum >= self.min_resolved_for_verdict
            else "PROVISIONAL — sample below threshold, indicative only"
        )
        if self.verdict != expected:
            raise ValueError("validation verdict must match the conservative threshold")
        return self


ReversalRadarValidationTierName = Literal[
    "+10%/20d",
    "+15%/40d",
    "+20%/60d",
]
ReversalRadarValidationVerdict = Literal[
    "PROVISIONAL — sample below threshold, indicative only",
    "MATURE",
]
ReversalRadarValidationProbability = Annotated[
    float,
    Field(ge=0, le=1, allow_inf_nan=False),
]


class ReversalRadarValidationTier(BaseModel):
    """One bounded public Reversal Radar forward-validation tier."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    resolved: Annotated[int, Field(ge=0, le=10_000_000)]
    hits: Annotated[int, Field(ge=0, le=10_000_000)]
    hit_rate: ReversalRadarValidationProbability | None
    wilson90: Annotated[
        list[ReversalRadarValidationProbability],
        Field(min_length=2, max_length=2),
    ]

    @model_validator(mode="after")
    def validate_counts_and_rate(self) -> "ReversalRadarValidationTier":
        if self.hits > self.resolved:
            raise ValueError("validation hits cannot exceed resolved")
        expected_rate = None if self.resolved == 0 else self.hits / self.resolved
        if expected_rate is None:
            if self.hit_rate is not None:
                raise ValueError("zero resolved rows must have a null hit_rate")
        elif self.hit_rate is None or not isclose(
            self.hit_rate,
            expected_rate,
            rel_tol=0,
            abs_tol=0.00005,
        ):
            raise ValueError("validation hit_rate must match hits/resolved")
        if self.wilson90[0] > self.wilson90[1]:
            raise ValueError("validation wilson90 must be ordered")
        return self


class ReversalRadarValidationData(ArtifactDataModel):
    """Strict public projection of the Reversal Radar forward scoreboard."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    entries_accumulated: Annotated[int, Field(ge=0, le=10_000_000)]
    min_resolved_across_tiers: Annotated[int, Field(ge=0, le=10_000_000)]
    min_resolved_for_verdict: Annotated[int, Field(ge=1, le=10_000_000)]
    verdict: ReversalRadarValidationVerdict
    by_tier: Annotated[
        dict[ReversalRadarValidationTierName, ReversalRadarValidationTier],
        Field(min_length=3, max_length=3),
    ]

    @field_validator("by_tier")
    @classmethod
    def validate_tier_order(
        cls,
        value: dict[
            ReversalRadarValidationTierName,
            ReversalRadarValidationTier,
        ],
    ) -> dict[
        ReversalRadarValidationTierName,
        ReversalRadarValidationTier,
    ]:
        if tuple(value) != ("+10%/20d", "+15%/40d", "+20%/60d"):
            raise ValueError("validation tiers must use the fixed producer order")
        return value

    @model_validator(mode="after")
    def validate_conservative_verdict(self) -> "ReversalRadarValidationData":
        minimum = min(row.resolved for row in self.by_tier.values())
        if self.min_resolved_across_tiers != minimum:
            raise ValueError("minimum resolved count must match the tier rows")
        expected = (
            "MATURE"
            if minimum >= self.min_resolved_for_verdict
            else "PROVISIONAL — sample below threshold, indicative only"
        )
        if self.verdict != expected:
            raise ValueError("validation verdict must match the conservative threshold")
        return self


MarketThesisDate = Annotated[
    str,
    Field(
        pattern=_MARKET_THESIS_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _MARKET_THESIS_DATE_SCHEMA_PATTERN,
        },
    ),
]
MarketThesisEventType = Literal["CPI", "JOBS", "FOMC", "UST10Y", "DXY"]
MarketThesisFiniteReturn = Annotated[
    float,
    Field(ge=-100, le=100, allow_inf_nan=False),
]


class MarketThesisAnalog(BaseModel):
    """Bounded public analog metrics rendered by the latest-forecast page."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    status: (
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=100,
                pattern=_MARKET_THESIS_TEXT_PATTERN,
                json_schema_extra={"pattern": _MARKET_THESIS_TEXT_SCHEMA_PATTERN},
            ),
        ]
        | None
    ) = None
    resolved: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    mean: MarketThesisFiniteReturn | None = None
    up_rate: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None
    ci90: Annotated[list[MarketThesisFiniteReturn], Field(min_length=2, max_length=2)] | None = None
    p10: MarketThesisFiniteReturn | None = None
    worst_mdd: MarketThesisFiniteReturn | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> "MarketThesisAnalog":
        if self.ci90 is not None and self.ci90[0] > self.ci90[1]:
            raise ValueError("analog ci90 must be ordered")
        return self


class MarketThesisEvent(BaseModel):
    """One allowlisted macro-event freshness row."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    type: MarketThesisEventType
    source_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=_MARKET_THESIS_SOURCE_PATTERN,
            json_schema_extra={"pattern": _MARKET_THESIS_SOURCE_SCHEMA_PATTERN},
        ),
    ]
    present: bool
    fresh: bool
    stale_reason: (
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=100,
                pattern=_MARKET_THESIS_TEXT_PATTERN,
                json_schema_extra={"pattern": _MARKET_THESIS_TEXT_SCHEMA_PATTERN},
            ),
        ]
        | None
    )
    value: Annotated[float, Field(ge=-1_000_000_000, le=1_000_000_000, allow_inf_nan=False)] | None
    delta_1d: Annotated[float, Field(ge=-1_000_000_000, le=1_000_000_000, allow_inf_nan=False)] | None
    last_rate: Annotated[str, Field(max_length=100)] | None
    next_meeting_at: MarketThesisDate | None

    @field_validator("next_meeting_at")
    @classmethod
    def validate_next_meeting_at(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("next_meeting_at must be a valid calendar date") from exc
        return value


class MarketThesisRationale(BaseModel):
    """Strict nested projection used by the Market Thesis presentation."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    analog: MarketThesisAnalog | None
    manifest_missing: Annotated[
        list[MarketThesisEventType],
        Field(max_length=5, json_schema_extra={"uniqueItems": True}),
    ]
    manifest_stale: Annotated[
        list[MarketThesisEventType],
        Field(max_length=5, json_schema_extra={"uniqueItems": True}),
    ]
    manifest_events: Annotated[list[MarketThesisEvent], Field(max_length=5)]

    @model_validator(mode="after")
    def validate_event_sets(self) -> "MarketThesisRationale":
        if len(self.manifest_missing) != len(set(self.manifest_missing)):
            raise ValueError("manifest_missing must be unique")
        if len(self.manifest_stale) != len(set(self.manifest_stale)):
            raise ValueError("manifest_stale must be unique")
        event_types = [event.type for event in self.manifest_events]
        if len(event_types) != len(set(event_types)):
            raise ValueError("manifest event types must be unique")
        return self


class MarketThesisData(ArtifactDataModel):
    """Strict latest-forecast projection for the public read API."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of: Annotated[
        MarketThesisDate,
        Field(description="Forecast date, validated as a real calendar date."),
    ]
    generated_at: Annotated[
        str,
        Field(
            min_length=20,
            max_length=32,
            pattern=_MARKET_THESIS_RFC3339_PATTERN,
            json_schema_extra={
                "format": "date-time",
                "pattern": _MARKET_THESIS_RFC3339_SCHEMA_PATTERN,
            },
        ),
    ]
    direction: Literal["看多", "看空", "盤整"]
    bucket: Literal["short", "mid", "long"]
    support_class: Literal["analog_supported", "event_only", "regime_only"]
    manifest_status: Literal["ready", "degraded"]
    regime: Literal["rally", "correction", "range"]
    vix_bucket: Literal["low", "normal", "elevated", "panic"]
    rationale: MarketThesisRationale
    label: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            pattern=_MARKET_THESIS_TEXT_PATTERN,
            json_schema_extra={"pattern": _MARKET_THESIS_TEXT_SCHEMA_PATTERN},
        ),
    ]

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("as_of must be a valid calendar date") from exc
        return value

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        if _MARKET_THESIS_RFC3339_RE.fullmatch(value) is None:
            raise ValueError("generated_at must be a timezone-aware RFC 3339 timestamp")
        normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                "generated_at must be a timezone-aware RFC 3339 timestamp"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("generated_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_support_status(self) -> "MarketThesisData":
        if self.manifest_status == "degraded" and self.support_class != "regime_only":
            raise ValueError("degraded forecasts must use regime_only support")
        if self.manifest_status == "ready" and self.support_class == "regime_only":
            raise ValueError("ready forecasts cannot use regime_only support")
        return self


DailySummaryDate = Annotated[
    str,
    Field(
        pattern=_DAILY_SUMMARY_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _DAILY_SUMMARY_DATE_SCHEMA_PATTERN,
        },
    ),
]


class DailySummaryCandidateRef(BaseModel):
    """Minimal ranked-candidate reference required by the Today page."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ticker: SignalTicker
    verdict: Literal["STRONG_BUY", "BUY", "WATCHLIST"]


class DailySummaryData(ArtifactDataModel):
    """Strict minimal projection of the newest dated report summary."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_date: DailySummaryDate
    regime_summary: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1_000,
            pattern=_DAILY_SUMMARY_TEXT_PATTERN,
            json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
        ),
    ]
    candidates: Annotated[
        list[DailySummaryCandidateRef],
        Field(max_length=100),
    ]

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("as_of_date must be a valid calendar date") from exc
        return value

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> "DailySummaryData":
        tickers = [candidate.ticker for candidate in self.candidates]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Daily Summary candidate tickers must be unique")
        return self


PlaybookValidationLabel = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        pattern=_DAILY_SUMMARY_TEXT_PATTERN,
        json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
    ),
]
PlaybookValidationReturn = Annotated[
    float,
    Field(
        ge=-1,
        le=1_000_000_000_000_000_000,
        allow_inf_nan=False,
    ),
]
PlaybookValidationHitRate = Annotated[
    float,
    Field(ge=0, le=1, allow_inf_nan=False),
]


class PlaybookValidationPlaybookRow(BaseModel):
    """One bounded Playbook-level forward-validation presentation row."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    playbook: PlaybookValidationLabel
    resolved: Annotated[int, Field(ge=0, le=1_000_000)]
    mean_fwd_7d_return: PlaybookValidationReturn | None
    hit_rate_7d: PlaybookValidationHitRate | None
    verdict: Literal["exploratory", "validated"]

    @model_validator(mode="after")
    def validate_statistics(self) -> "PlaybookValidationPlaybookRow":
        has_mean = self.mean_fwd_7d_return is not None
        has_hit_rate = self.hit_rate_7d is not None
        if has_mean != has_hit_rate or has_mean != (self.resolved > 0):
            raise ValueError("Playbook statistics must match the resolved population")
        return self


class PlaybookValidationFactorRow(BaseModel):
    """One bounded factor-level forward-validation presentation row."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    factor_id: PlaybookValidationLabel
    resolved: Annotated[int, Field(ge=0, le=1_000_000)]
    mean_fwd_7d_return: PlaybookValidationReturn | None
    hit_rate_7d: PlaybookValidationHitRate | None
    verdict: Literal["exploratory", "validated"]

    @model_validator(mode="after")
    def validate_statistics(self) -> "PlaybookValidationFactorRow":
        has_mean = self.mean_fwd_7d_return is not None
        has_hit_rate = self.hit_rate_7d is not None
        if has_mean != has_hit_rate or has_mean != (self.resolved > 0):
            raise ValueError("Factor statistics must match the resolved population")
        return self


class PlaybookValidationData(ArtifactDataModel):
    """Strict summary-only projection of automated Playbook validation."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    generated_at: CandidateFeedTimestamp
    status: Literal["blocked", "accumulating", "ready"]
    decision_count: Annotated[int, Field(ge=0, le=1_000_000)]
    resolved: Annotated[int, Field(ge=0, le=1_000_000)]
    min_resolved: Annotated[int, Field(ge=1, le=1_000_000)]
    playbooks: Annotated[
        list[PlaybookValidationPlaybookRow],
        Field(max_length=200),
    ]
    factors: Annotated[
        list[PlaybookValidationFactorRow],
        Field(max_length=500),
    ]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_summary(self) -> "PlaybookValidationData":
        if self.resolved > self.decision_count:
            raise ValueError("resolved cannot exceed decision_count")
        if self.status == "blocked":
            if (
                self.decision_count != 0
                or self.resolved != 0
                or self.playbooks
                or self.factors
            ):
                raise ValueError("blocked Playbook validation must be empty")
        elif self.status == "accumulating" and self.resolved >= self.min_resolved:
            raise ValueError("accumulating status requires an immature sample")
        elif self.status == "ready" and self.resolved < self.min_resolved:
            raise ValueError("ready status requires a mature sample")

        playbook_names = [row.playbook for row in self.playbooks]
        factor_ids = [row.factor_id for row in self.factors]
        if playbook_names != sorted(playbook_names) or len(playbook_names) != len(
            set(playbook_names)
        ):
            raise ValueError("Playbook labels must be unique and sorted")
        if factor_ids != sorted(factor_ids) or len(factor_ids) != len(set(factor_ids)):
            raise ValueError("factor IDs must be unique and sorted")
        if sum(row.resolved for row in self.playbooks) != self.resolved:
            raise ValueError("Playbook resolved rows must partition resolved decisions")
        for row in (*self.playbooks, *self.factors):
            if row.resolved > self.resolved:
                raise ValueError("row resolved cannot exceed total resolved")
            expected = (
                "validated"
                if row.resolved >= self.min_resolved
                else "exploratory"
            )
            if row.verdict != expected:
                raise ValueError("row verdict must match its maturity")
        return self


ContinuationValidationCause = Literal[
    "technical_volume_expansion",
    "relative_strength_leadership",
    "technical_compression_base",
    "technical_momentum_confirm",
    "trend_quality",
    "market_regime_support",
    "unknown",
]
ContinuationValidationReturn = Annotated[
    float,
    Field(ge=-1, le=1_000_000_000, allow_inf_nan=False),
]
ContinuationValidationMagnitude = Annotated[
    float,
    Field(ge=-100, le=1_000_000_000, allow_inf_nan=False),
]
ContinuationValidationThreshold = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=_DAILY_SUMMARY_TEXT_PATTERN,
        json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
    ),
]


class ContinuationValidationSummary(BaseModel):
    """Exact public continuation label partition and maturity counters."""

    model_config = ConfigDict(extra="forbid", strict=True)

    strong_continuation: Annotated[int, Field(ge=0, le=5_000)]
    normal_continuation: Annotated[int, Field(ge=0, le=5_000)]
    failed_breakout: Annotated[int, Field(ge=0, le=5_000)]
    unresolved: Annotated[int, Field(ge=0, le=5_000)]
    rows_total: Annotated[int, Field(ge=0, le=5_000)]
    resolved: Annotated[int, Field(ge=0, le=5_000)]
    min_resolved: Annotated[int, Field(ge=1, le=1_000_000)]

    @model_validator(mode="after")
    def validate_partition(self) -> "ContinuationValidationSummary":
        if (
            self.strong_continuation
            + self.normal_continuation
            + self.failed_breakout
            + self.unresolved
            != self.rows_total
        ):
            raise ValueError("continuation counts must partition rows_total")
        if self.rows_total - self.unresolved != self.resolved:
            raise ValueError("resolved must equal the non-unresolved population")
        return self


class ContinuationValidationRow(BaseModel):
    """One strict ticker-level continuation outcome shown in the table."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: SignalTicker
    setup_date: DailySummaryDate
    surge_start: DailySummaryDate | None
    thresholds_hit: Annotated[
        list[ContinuationValidationThreshold],
        Field(max_length=100),
    ]
    magnitude_pct: ContinuationValidationMagnitude | None
    candidate_causes: Annotated[
        list[ContinuationValidationCause],
        Field(min_length=1, max_length=7),
    ]
    cause_certainty: Literal["candidate_only"]
    measurement_source: Literal["daily_bars"]
    resolved_30d: bool
    fwd_30d_return: ContinuationValidationReturn | None
    fwd_30d_max_drawdown: ContinuationValidationReturn | None
    resolved_60d: bool
    fwd_60d_return: ContinuationValidationReturn | None
    fwd_60d_max_drawdown: ContinuationValidationReturn | None
    continuation_label: Literal[
        "strong_continuation",
        "normal_continuation",
        "failed_breakout",
        "unresolved",
    ]
    primary_horizon: Literal["30d", "60d"] | None
    trade_value: Literal["high", "medium", "low", "unknown"]

    @field_validator("setup_date", "surge_start")
    @classmethod
    def validate_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("continuation dates must be real calendar dates") from exc
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> "ContinuationValidationRow":
        if len(self.thresholds_hit) != len(set(self.thresholds_hit)):
            raise ValueError("threshold labels must be unique")
        if len(self.candidate_causes) != len(set(self.candidate_causes)):
            raise ValueError("candidate causes must be unique")
        for resolved, forward_return, drawdown in (
            (
                self.resolved_30d,
                self.fwd_30d_return,
                self.fwd_30d_max_drawdown,
            ),
            (
                self.resolved_60d,
                self.fwd_60d_return,
                self.fwd_60d_max_drawdown,
            ),
        ):
            if (
                resolved
                and (forward_return is None or drawdown is None)
            ) or (
                not resolved
                and (forward_return is not None or drawdown is not None)
            ):
                raise ValueError("resolved windows require an exact return/drawdown pair")

        strong_30 = (
            self.resolved_30d
            and self.fwd_30d_return is not None
            and self.fwd_30d_max_drawdown is not None
            and self.fwd_30d_return >= 0.15
            and self.fwd_30d_max_drawdown >= -0.10
        )
        strong_60 = (
            self.resolved_60d
            and self.fwd_60d_return is not None
            and self.fwd_60d_max_drawdown is not None
            and self.fwd_60d_return >= 0.30
            and self.fwd_60d_max_drawdown >= -0.15
        )
        if not self.resolved_30d and not self.resolved_60d:
            expected = ("unresolved", None, "unknown")
        elif strong_30:
            expected = ("strong_continuation", "30d", "high")
        elif strong_60:
            expected = ("strong_continuation", "60d", "high")
        elif (
            self.resolved_30d
            and self.fwd_30d_return is not None
            and self.fwd_30d_return > 0
        ):
            expected = ("normal_continuation", "30d", "medium")
        else:
            expected = (
                "failed_breakout",
                "30d" if self.resolved_30d else "60d",
                "low",
            )
        actual = (
            self.continuation_label,
            self.primary_horizon,
            self.trade_value,
        )
        if actual != expected:
            raise ValueError("continuation label, horizon, and trade value disagree")
        return self


class ContinuationValidationData(ArtifactDataModel):
    """Strict public projection of Continuation Validation outcomes."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    generated_at: CandidateFeedTimestamp
    status: Literal["blocked", "accumulating", "ready"]
    resolved: Annotated[int, Field(ge=0, le=5_000)]
    min_resolved: Annotated[int, Field(ge=1, le=1_000_000)]
    summary: ContinuationValidationSummary
    rows: Annotated[list[ContinuationValidationRow], Field(max_length=5_000)]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_report(self) -> "ContinuationValidationData":
        if (
            self.summary.rows_total != len(self.rows)
            or self.summary.resolved != self.resolved
            or self.summary.min_resolved != self.min_resolved
        ):
            raise ValueError("continuation summary must match report counters")
        if self.resolved != sum(
            row.continuation_label != "unresolved" for row in self.rows
        ):
            raise ValueError("continuation rows must match resolved")
        identities = [(row.ticker, row.setup_date) for row in self.rows]
        if len(identities) != len(set(identities)):
            raise ValueError("continuation ticker/setup-date rows must be unique")
        if self.status == "blocked":
            if self.resolved != 0 or self.rows or self.summary.rows_total != 0:
                raise ValueError("blocked Continuation Validation must be empty")
        elif self.status == "accumulating" and self.resolved >= self.min_resolved:
            raise ValueError("accumulating status requires an immature sample")
        elif self.status == "ready" and self.resolved < self.min_resolved:
            raise ValueError("ready status requires a mature sample")
        return self


CotReportDate = Annotated[
    str,
    Field(
        min_length=10,
        max_length=10,
        pattern=_DAILY_SUMMARY_DATE_PATTERN,
        json_schema_extra={
            "format": "date",
            "pattern": _DAILY_SUMMARY_DATE_SCHEMA_PATTERN,
        },
    ),
]
CotText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=500,
        pattern=_DAILY_SUMMARY_TEXT_PATTERN,
        json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
    ),
]
CotPositionCount = Annotated[int, Field(ge=-1_000_000_000_000, le=1_000_000_000_000)]
CotPositivePrice = Annotated[
    float,
    Field(gt=0, le=1_000_000_000, allow_inf_nan=False),
]
CotDelta = Annotated[
    float,
    Field(ge=-1_000_000_000, le=1_000_000_000, allow_inf_nan=False),
]


def _validate_cot_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("COT dates must be real calendar dates") from exc
    return value


class CotCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    report_date: CotReportDate

    @field_validator("report_date")
    @classmethod
    def validate_report_date(cls, value: str) -> str:
        return _validate_cot_date(value)


class CotCatalogData(ArtifactDataModel):
    """Bounded newest-first catalog of published COT Markdown reports."""

    model_config = ConfigDict(extra="forbid", strict=True)

    reports: Annotated[list[CotCatalogEntry], Field(max_length=520)]

    @model_validator(mode="after")
    def validate_catalog(self) -> "CotCatalogData":
        dates = [row.report_date for row in self.reports]
        if dates != sorted(dates, reverse=True) or len(dates) != len(set(dates)):
            raise ValueError("COT catalog dates must be unique and newest first")
        return self


class CotPositionGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    long: Annotated[int, Field(ge=0, le=1_000_000_000_000)]
    short: Annotated[int, Field(ge=0, le=1_000_000_000_000)]
    net: CotPositionCount
    chg_long: CotPositionCount
    chg_short: CotPositionCount
    chg_net: CotPositionCount

    @model_validator(mode="after")
    def validate_arithmetic(self) -> "CotPositionGroup":
        if self.net != self.long - self.short:
            raise ValueError("COT net must equal long minus short")
        if self.chg_net != self.chg_long - self.chg_short:
            raise ValueError("COT change net must equal change long minus short")
        return self


class CotPositioning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    as_of: CotReportDate
    market: Annotated[
        str,
        Field(
            min_length=1,
            max_length=300,
            pattern=_DAILY_SUMMARY_TEXT_PATTERN,
            json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
        ),
    ]
    open_interest: Annotated[int, Field(ge=0, le=1_000_000_000_000)]
    asset_manager: CotPositionGroup
    leveraged_funds: CotPositionGroup
    source: CotText

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        return _validate_cot_date(value)


class CotPrice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    symbol: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            pattern=_DAILY_SUMMARY_TEXT_PATTERN,
            json_schema_extra={"pattern": _DAILY_SUMMARY_TEXT_SCHEMA_PATTERN},
        ),
    ]
    friday_date: CotReportDate
    friday_open: CotPositivePrice
    friday_high: CotPositivePrice
    friday_low: CotPositivePrice
    friday_close: CotPositivePrice
    week_high: CotPositivePrice
    week_low: CotPositivePrice
    as_of_date: CotReportDate
    as_of_close: CotPositivePrice | None
    cot_report_age_days: Annotated[int, Field(ge=0, le=36_500)]
    cot_stale_warning: bool
    source: CotText
    retrieved_at: CandidateFeedTimestamp

    @field_validator("friday_date", "as_of_date")
    @classmethod
    def validate_dates(cls, value: str) -> str:
        return _validate_cot_date(value)

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_range(self) -> "CotPrice":
        if self.friday_high < max(
            self.friday_open,
            self.friday_low,
            self.friday_close,
        ) or self.friday_low > min(
            self.friday_open,
            self.friday_high,
            self.friday_close,
        ):
            raise ValueError("Friday OHLC range is incoherent")
        if self.week_high < self.friday_high or self.week_low > self.friday_low:
            raise ValueError("weekly range must contain the Friday range")
        if self.cot_stale_warning != (self.cot_report_age_days > 9):
            raise ValueError("COT stale warning must match report age")
        return self


class CotTuesdayFriday(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_tuesday_close: CotPositivePrice | None
    friday_close: CotPositivePrice
    delta_points: CotDelta | None


class CotVerifiedData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    cot: CotPositioning
    price: CotPrice
    tuesday_vs_friday: CotTuesdayFriday

    @model_validator(mode="after")
    def validate_pair(self) -> "CotVerifiedData":
        if self.cot.as_of != self.price.as_of_date:
            raise ValueError("COT and price as-of dates must agree")
        as_of_date = date.fromisoformat(self.cot.as_of)
        friday_date = date.fromisoformat(self.price.friday_date)
        if (
            as_of_date.weekday() != 1
            or friday_date.weekday() != 4
            or (friday_date - as_of_date).days != 3
        ):
            raise ValueError("COT comparison must bind Tuesday to the same-week Friday")
        retrieved_at = self.price.retrieved_at
        normalized_retrieved_at = (
            retrieved_at[:-1] + "+00:00"
            if retrieved_at.endswith(("Z", "z"))
            else retrieved_at
        )
        retrieved_date = datetime.fromisoformat(normalized_retrieved_at).astimezone(
            timezone.utc
        ).date()
        if self.price.cot_report_age_days != (retrieved_date - as_of_date).days:
            raise ValueError("COT report age must match the retrieval timestamp")
        comparison = self.tuesday_vs_friday
        if not isclose(
            comparison.friday_close,
            self.price.friday_close,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError("Friday close must agree across verified sections")
        if self.price.as_of_close is None:
            if comparison.as_of_tuesday_close is not None or comparison.delta_points is not None:
                raise ValueError("missing Tuesday close requires a null comparison")
        else:
            if (
                comparison.as_of_tuesday_close is None
                or comparison.delta_points is None
                or not isclose(
                    comparison.as_of_tuesday_close,
                    self.price.as_of_close,
                    rel_tol=0,
                    abs_tol=1e-9,
                )
                or not isclose(
                    comparison.delta_points,
                    round(self.price.friday_close - self.price.as_of_close, 2),
                    rel_tol=0,
                    abs_tol=1e-9,
                )
            ):
                raise ValueError("Tuesday-to-Friday comparison is incoherent")
        return self


class CotReportData(ArtifactDataModel):
    """Strict selected COT Markdown plus verified audit projection."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    report_date: CotReportDate
    markdown: Annotated[str, Field(min_length=1, max_length=256 * 1024)]
    verified: CotVerifiedData

    @field_validator("report_date")
    @classmethod
    def validate_report_date(cls, value: str) -> str:
        return _validate_cot_date(value)

    @field_validator("markdown")
    @classmethod
    def validate_markdown(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("COT Markdown cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_report_pair(self) -> "CotReportData":
        if self.report_date != self.verified.price.friday_date:
            raise ValueError("COT report date must match the verified Friday")
        return self


MarketThesisValidationKey = Annotated[
    str,
    Field(
        min_length=18,
        max_length=44,
        pattern=(
            r"^(?:看多|看空|盤整)\|(?:short|mid|long)\|"
            r"(?:analog_supported|event_only|regime_only)$"
        ),
    ),
]
MarketThesisProbability = Annotated[
    float,
    Field(ge=0, le=1, allow_inf_nan=False),
]


class MarketThesisValidationRow(BaseModel):
    """One bounded full-key forward-validation result."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    counted_N: Annotated[int, Field(ge=1, le=1_000_000)]
    hits: Annotated[int, Field(ge=0, le=1_000_000)]
    hit_rate: MarketThesisProbability
    wilson90: Annotated[
        list[MarketThesisProbability],
        Field(min_length=2, max_length=2),
    ]
    verdict: Literal["PROVISIONAL", "MATURE"]

    @model_validator(mode="after")
    def validate_counts_and_rate(self) -> "MarketThesisValidationRow":
        if self.hits > self.counted_N:
            raise ValueError("validation hits cannot exceed counted_N")
        if not isclose(
            self.hit_rate,
            self.hits / self.counted_N,
            rel_tol=0,
            abs_tol=0.00005,
        ):
            raise ValueError("validation hit_rate must match hits/counted_N")
        if self.wilson90[0] > self.wilson90[1]:
            raise ValueError("validation wilson90 must be ordered")
        return self


class MarketThesisValidationData(ArtifactDataModel):
    """Strict public projection of the Market Thesis validation scoreboard."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    validation_status: Annotated[
        str,
        Field(
            min_length=2,
            max_length=100,
            pattern=r"^(?:ok|non_publishable_[a-z0-9_]+)$",
        ),
    ]
    resolved: Annotated[int, Field(ge=0, le=1_000_000)]
    matured: Annotated[int, Field(ge=0, le=1_000_000)]
    min_resolved_for_verdict: Annotated[int, Field(ge=1, le=1_000_000)]
    reject_count: Annotated[int, Field(ge=0, le=1_000_000)]
    invalid_count: Annotated[int, Field(ge=0, le=1_000_000)]
    by_key: Annotated[
        dict[MarketThesisValidationKey, MarketThesisValidationRow],
        Field(max_length=27),
    ]

    @model_validator(mode="after")
    def validate_summary_counts(self) -> "MarketThesisValidationData":
        if self.matured > self.resolved:
            raise ValueError("validation matured cannot exceed resolved")
        if sum(row.counted_N for row in self.by_key.values()) > self.matured:
            raise ValueError("validation counted rows cannot exceed matured")
        if self.validation_status == "ok" and (
            self.reject_count or self.invalid_count
        ):
            raise ValueError("ok validation cannot contain rejected or invalid rows")
        for row in self.by_key.values():
            expected = (
                "MATURE"
                if row.counted_N >= self.min_resolved_for_verdict
                else "PROVISIONAL"
            )
            if row.verdict != expected:
                raise ValueError("validation verdict must match the maturity threshold")
        return self


class MarketThesisRegimeWindow(BaseModel):
    """Allowlisted return distribution for one fixed forward window."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    mean: MarketThesisFiniteReturn
    up_rate: MarketThesisProbability
    p10: MarketThesisFiniteReturn
    worst: MarketThesisFiniteReturn

    @model_validator(mode="after")
    def validate_tail_order(self) -> "MarketThesisRegimeWindow":
        if self.worst > self.p10:
            raise ValueError("regime worst return cannot exceed p10")
        return self


class MarketThesisRegime(BaseModel):
    """Exactly three fixed forward windows for one market regime."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    days: Annotated[int, Field(ge=1, le=100_000)]
    fwd_20d: MarketThesisRegimeWindow
    fwd_40d: MarketThesisRegimeWindow
    fwd_60d: MarketThesisRegimeWindow


class MarketThesisRegimeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    rally: MarketThesisRegime
    correction: MarketThesisRegime
    range: MarketThesisRegime


class MarketThesisRegimeHistoryData(ArtifactDataModel):
    """Summary-only projection that excludes the multi-megabyte raw corpus."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    regime_summary: MarketThesisRegimeSummary


class IvHistoryData(ArtifactDataModel):
    """Strict public DTO for one normalized ticker's IV history."""

    model_config = ConfigDict(extra="forbid")

    ticker: Annotated[
        str,
        Field(
            max_length=15,
            pattern=r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$",
        ),
    ]
    series: dict[date, Annotated[float, Field(gt=0, lt=10)]]


FundDisplayName = Annotated[str, Field(min_length=1, max_length=120)]


class FundCatalogEntry(BaseModel):
    """One public curated fund selector entry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cik: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10,
            pattern=r"^0*[1-9][0-9]*$",
        ),
    ]
    note: Annotated[str, Field(max_length=200)]


class FundCatalogData(ArtifactDataModel):
    """Strict public projection of the curated institutional fund catalog."""

    model_config = ConfigDict(extra="forbid", strict=True)

    funds: Annotated[
        dict[FundDisplayName, FundCatalogEntry],
        Field(
            max_length=100,
            json_schema_extra={
                "propertyNames": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 120,
                    "pattern": r"^\S(?:.*\S)?$",
                }
            },
        ),
    ]

    @field_validator("funds")
    @classmethod
    def validate_display_names(
        cls,
        value: dict[str, FundCatalogEntry],
    ) -> dict[str, FundCatalogEntry]:
        if any(_FUND_NAME_RE.fullmatch(name) is None for name in value):
            raise ValueError("fund display names must not have surrounding whitespace")
        return value


CryptoDate = Annotated[
    str,
    Field(
        pattern=_CRYPTO_DATE_PATTERN,
        json_schema_extra={"format": "date"},
    ),
]
CryptoSymbol = Annotated[
    str,
    Field(min_length=2, max_length=30, pattern=_CRYPTO_SYMBOL_PATTERN),
]


class CryptoUniverseItem(BaseModel):
    """One source-ordered Binance USDT perpetual contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    symbol: CryptoSymbol
    base: Annotated[
        str,
        Field(min_length=1, max_length=30, pattern=_CRYPTO_BASE_PATTERN),
    ]
    tv_symbol: Annotated[
        str,
        Field(
            min_length=12,
            max_length=40,
            pattern=(
                r"^BINANCE:[^\s\x00-\x1f\x7f:./\\]{2,30}\.P$"
            ),
        ),
    ]
    onboard_date: CryptoDate | None

    @field_validator("onboard_date")
    @classmethod
    def validate_onboard_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("onboard_date must be a real calendar date") from exc
        return value

    @model_validator(mode="after")
    def validate_tv_symbol(self) -> "CryptoUniverseItem":
        if self.tv_symbol != f"BINANCE:{self.symbol}.P":
            raise ValueError("tv_symbol must be derived from symbol")
        return self


class CryptoUniverseData(ArtifactDataModel):
    """Strict public projection of the Binance USDT perpetual universe."""

    model_config = ConfigDict(extra="forbid", strict=True)

    date: CryptoDate
    source: Literal["binance_fapi_exchangeInfo"]
    source_status: Literal["live", "stale_fallback", "unavailable"]
    stale: bool
    stale_source_date: CryptoDate | None
    count: Annotated[int, Field(ge=0, le=2000)]
    universe: Annotated[list[CryptoUniverseItem], Field(max_length=2000)]
    added: Annotated[
        list[CryptoSymbol],
        Field(max_length=2000, json_schema_extra={"uniqueItems": True}),
    ]
    removed: Annotated[
        list[CryptoSymbol],
        Field(max_length=2000, json_schema_extra={"uniqueItems": True}),
    ]
    compared_to: CryptoDate | None

    @field_validator("date", "stale_source_date", "compared_to")
    @classmethod
    def validate_calendar_dates(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("snapshot dates must be real calendar dates") from exc
        return value

    @model_validator(mode="after")
    def validate_snapshot_invariants(self) -> "CryptoUniverseData":
        symbols = [item.symbol for item in self.universe]
        if self.count != len(symbols):
            raise ValueError("count must match the public universe")
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ValueError("universe symbols must be unique and sorted")
        if self.added != sorted(self.added) or len(self.added) != len(set(self.added)):
            raise ValueError("added symbols must be unique and sorted")
        if self.removed != sorted(self.removed) or len(self.removed) != len(set(self.removed)):
            raise ValueError("removed symbols must be unique and sorted")
        current = set(symbols)
        if not set(self.added).issubset(current) or set(self.removed) & current:
            raise ValueError("diff symbols are inconsistent with the universe")
        if self.compared_to is not None and self.compared_to >= self.date:
            raise ValueError("compared_to must precede the snapshot date")
        if self.stale_source_date is not None and self.stale_source_date >= self.date:
            raise ValueError("stale_source_date must precede the snapshot date")

        if self.source_status == "live":
            if self.stale or self.stale_source_date is not None:
                raise ValueError("live data cannot be stale")
        elif self.source_status == "stale_fallback":
            if (
                not self.stale
                or self.stale_source_date is None
                or self.stale_source_date != self.compared_to
                or self.added
                or self.removed
            ):
                raise ValueError("stale fallback provenance is inconsistent")
        elif (
            not self.stale
            or self.stale_source_date is not None
            or self.count != 0
            or self.universe
            or self.added
            or self.removed
            or self.compared_to is not None
        ):
            raise ValueError("unavailable snapshots must be empty and stale")

        if self.compared_to is None and (self.added or self.removed):
            raise ValueError("diffs require a comparison date")
        return self


AiUpdateTag = Annotated[
    str,
    Field(
        min_length=1,
        max_length=50,
        pattern=_AI_UPDATE_TAG_PATTERN,
    ),
]


class AiUpdateItem(BaseModel):
    """One source-ordered public AI update entry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    date: Annotated[
        str,
        Field(
            pattern=_AI_UPDATE_DATE_PATTERN,
            description=(
                "Real calendar date preserved as the original YYYY-MM-DD string."
            ),
            json_schema_extra={"format": "date"},
        ),
    ]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    summary: Annotated[str, Field(min_length=1, max_length=2000)]
    link: Annotated[
        str,
        Field(
            max_length=2048,
            description=(
                "Empty or a lowercase-HTTPS IRI preserved exactly as stored. Runtime "
                "parsing additionally requires a valid non-empty authority and "
                "hostname, rejects userinfo and invalid ports, and performs no "
                "normalization. Those parser-enforced checks are intentionally "
                "stricter than this schema pattern."
            ),
            json_schema_extra={
                "anyOf": [
                    {"const": ""},
                    {
                        "type": "string",
                        "format": "iri",
                        "pattern": _AI_UPDATE_LINK_PATTERN,
                    },
                ]
            },
        ),
    ]
    tags: Annotated[
        list[AiUpdateTag],
        Field(
            max_length=20,
            json_schema_extra={"uniqueItems": True},
        ),
    ]

    @field_validator("date")
    @classmethod
    def validate_calendar_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be a valid calendar date") from exc
        return value

    @field_validator("link")
    @classmethod
    def validate_link(cls, value: str) -> str:
        if value == "":
            return value
        if _AI_UPDATE_LINK_RE.fullmatch(value) is None:
            raise ValueError("link must be empty or a lowercase HTTPS IRI")
        if any(
            character.isspace()
            or ord(character) < 0x20
            or ord(character) == 0x7F
            for character in value
        ):
            raise ValueError("link must not contain whitespace or control characters")
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("link has an invalid authority or port") from exc
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.netloc.endswith(":")
        ):
            raise ValueError("link has an invalid HTTPS authority")
        return value

    @field_validator("tags")
    @classmethod
    def validate_unique_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("tags must be unique")
        return value


class AiUpdatesData(ArtifactDataModel):
    """Strict public projection of the manually maintained update feed."""

    model_config = ConfigDict(extra="forbid", strict=True)

    updates: Annotated[list[AiUpdateItem], Field(max_length=200)]


ScheduleIdentifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=_SCHEDULE_IDENTIFIER_PATTERN,
    ),
]


class ScheduleEntry(BaseModel):
    """One source-ordered public schedule-registry entry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[
        ScheduleIdentifier,
        Field(description="Identifier that is unique within the artifact at runtime."),
    ]
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=_SCHEDULE_REQUIRED_TEXT_PATTERN,
        ),
    ]
    category: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50,
            pattern=_SCHEDULE_REQUIRED_TEXT_PATTERN,
        ),
    ]
    cron: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=_SCHEDULE_REQUIRED_TEXT_PATTERN,
            description="Opaque source string; the API does not parse cron semantics.",
        ),
    ]
    cron_note: Annotated[
        str,
        Field(
            max_length=500,
            pattern=_SCHEDULE_OPTIONAL_TEXT_PATTERN,
        ),
    ]
    description: Annotated[
        str,
        Field(
            max_length=2000,
            pattern=_SCHEDULE_OPTIONAL_TEXT_PATTERN,
        ),
    ]
    result_type: Annotated[
        ScheduleIdentifier,
        Field(
            description=(
                "Opaque result identifier that this endpoint never dereferences."
            )
        ),
    ]


class SchedulesData(ArtifactDataModel):
    """Strict public projection of the manually maintained schedule registry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schedules: Annotated[
        list[ScheduleEntry],
        Field(
            max_length=100,
            description=(
                "Source-ordered schedule entries. Schedule IDs must be unique at "
                "runtime; JSON Schema cannot enforce uniqueness by one object "
                "property."
            ),
        ),
    ]

    @field_validator("schedules")
    @classmethod
    def validate_unique_schedule_ids(
        cls,
        value: list[ScheduleEntry],
    ) -> list[ScheduleEntry]:
        identifiers = [item.id for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("schedule IDs must be unique")
        return value


BoundedPublicText = Annotated[str, Field(max_length=2_000)]
BoundedPublicName = Annotated[str, Field(min_length=1, max_length=200)]
BoundedPublicNumber = Annotated[
    float,
    Field(ge=-1_000_000_000_000_000_000, le=1_000_000_000_000_000_000),
]


class SocialIntelligenceAgentReachStatus(BaseModel):
    """Allowlisted persisted Agent Reach status rendered by the radar."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Annotated[str, Field(min_length=1, max_length=100)]
    note: BoundedPublicText


class SocialIntelligenceSourceStatuses(BaseModel):
    """Only the persisted status used by the selected radar slice."""

    model_config = ConfigDict(extra="forbid", strict=True)

    agent_reach: SocialIntelligenceAgentReachStatus


class SocialIntelligenceLabels(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x_mentioned: bool
    agent_reach: bool
    retail_heat: bool
    crowded: bool
    early_signal: bool
    paid_data_needed: bool


class SocialIntelligencePlatformValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    in_ranked_candidates: bool
    rank_score: CandidateFeedScore | None
    rank_bucket: Annotated[str, Field(max_length=100)] | None
    last_price: (
        Annotated[float, Field(gt=0, le=10_000_000, allow_inf_nan=False)] | None
    )
    options_flow_score: CandidateFeedScore | None
    options_direction: Annotated[str, Field(max_length=100)] | None


class SocialIntelligenceTicker(BaseModel):
    """Strict social row used by radar rendering and its local AI summary."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    mentioned_by: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=200)]],
        Field(max_length=100),
    ]
    citations: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=2_048)]],
        Field(max_length=100),
    ]
    skew: Annotated[str, Field(max_length=100)] | None
    conviction: Annotated[str, Field(max_length=100)] | None
    note: BoundedPublicText
    platform_validation: SocialIntelligencePlatformValidation
    labels: SocialIntelligenceLabels


class SocialIntelligenceData(ArtifactDataModel):
    """Strict persisted Social Intelligence presentation projection."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_date: CandidateFeedDate
    generated_at: CandidateFeedTimestamp
    market: Literal["US", "CRYPTO"]
    source_statuses: SocialIntelligenceSourceStatuses
    tickers: Annotated[list[SocialIntelligenceTicker], Field(max_length=200)]

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @field_validator("tickers")
    @classmethod
    def validate_unique_tickers(
        cls,
        value: list[SocialIntelligenceTicker],
    ) -> list[SocialIntelligenceTicker]:
        tickers = [item.ticker for item in value]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Social Intelligence tickers must be unique")
        return value


SectorRotationQuadrant = Literal[
    "Leading",
    "Improving",
    "Lagging",
    "Weakening",
]
SectorRotationQuadrantLabel = Literal["領漲", "醞釀", "落後", "轉弱"]


class SectorRotationSector(BaseModel):
    """One closed quantitative row from the persisted Sector Rotation board."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    etf: CandidateFeedTicker
    name_zh: Annotated[str, Field(min_length=1, max_length=100)]
    group: Literal["主板塊", "主題"]
    theme: Annotated[str, Field(min_length=1, max_length=200)] | None
    quadrant: SectorRotationQuadrant
    quadrant_zh: SectorRotationQuadrantLabel
    rs_ratio: Annotated[float, Field(ge=0, le=500, allow_inf_nan=False)]
    rs_momentum: Annotated[float, Field(ge=0, le=500, allow_inf_nan=False)]
    heat_score: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    ret_5d: Annotated[float, Field(ge=-100, le=1_000, allow_inf_nan=False)]
    ret_20d: Annotated[float, Field(ge=-100, le=1_000, allow_inf_nan=False)]
    ret_60d: Annotated[float, Field(ge=-100, le=1_000, allow_inf_nan=False)]
    excess_20d: Annotated[float, Field(ge=-1_000, le=1_000, allow_inf_nan=False)]
    pct_vs_ma50: Annotated[float, Field(ge=-100, le=1_000, allow_inf_nan=False)]
    pct_vs_ma200: Annotated[float, Field(ge=-100, le=1_000, allow_inf_nan=False)]
    pct_from_52w_high: Annotated[
        float,
        Field(ge=-100, le=1_000, allow_inf_nan=False),
    ]
    rvol: Annotated[float, Field(ge=0, le=1_000, allow_inf_nan=False)]

    @model_validator(mode="after")
    def validate_quadrant_label(self) -> "SectorRotationSector":
        labels = {
            "Leading": "領漲",
            "Improving": "醞釀",
            "Lagging": "落後",
            "Weakening": "轉弱",
        }
        if self.quadrant_zh != labels[self.quadrant]:
            raise ValueError("quadrant_zh must match quadrant")
        return self


class SectorRotationData(ArtifactDataModel):
    """Strict summary-only Sector Rotation board projection."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of: CandidateFeedDate
    benchmark: Literal["SPY"]
    sectors: Annotated[
        list[SectorRotationSector],
        Field(min_length=1, max_length=100),
    ]

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @model_validator(mode="after")
    def validate_board(self) -> "SectorRotationData":
        tickers = [sector.etf for sector in self.sectors]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Sector Rotation ETF rows must be unique")
        heat = [sector.heat_score for sector in self.sectors]
        if any(current < following for current, following in zip(heat, heat[1:])):
            raise ValueError("Sector Rotation rows must be sorted by heat descending")
        return self


ThemeFlowCapitalState = Literal[
    "加速流入(推估)",
    "流入趨緩",
    "中性",
    "流出(推估)",
]


class ThemeFlowRepresentative(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    flow_20d: BoundedPublicNumber
    flow_5d: BoundedPublicNumber
    ret_5d: CandidateFeedScore


class ThemeFlowTheme(BaseModel):
    """Allowlisted fields consumed by the existing Theme Flow presentation."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    theme: BoundedPublicName
    desc: Annotated[str, Field(max_length=2_000)]
    parent_sector_etfs: Annotated[list[CandidateFeedTicker], Field(max_length=20)]
    flow_5d: BoundedPublicNumber
    flow_20d: BoundedPublicNumber
    accel: BoundedPublicNumber
    flow_5d_norm: CandidateFeedScore
    flow_20d_norm: CandidateFeedScore
    accel_norm: CandidateFeedScore
    ret_5d: CandidateFeedScore
    top_share: Annotated[float, Field(ge=0, le=1)]
    high_concentration: bool
    breadth_inflow_ratio: Annotated[float, Field(ge=0, le=1)]
    positive_flow_count: Annotated[int, Field(ge=0, le=10_000)]
    negative_flow_count: Annotated[int, Field(ge=0, le=10_000)]
    n_used: Annotated[int, Field(ge=0, le=10_000)]
    n_total: Annotated[int, Field(ge=0, le=10_000)]
    reps: Annotated[list[ThemeFlowRepresentative], Field(max_length=10)]
    raw_heat_score: Annotated[float, Field(ge=0, le=100)]
    signal_quality: Annotated[float, Field(ge=0, le=1)]
    heat_score: Annotated[float, Field(ge=0, le=100)]
    capital_state: ThemeFlowCapitalState
    bottom_fishing: bool


class ThemeFlowSharedMegaCap(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ticker: CandidateFeedTicker
    themes: Annotated[int, Field(ge=2, le=100)]


class ThemeFlowData(ArtifactDataModel):
    """Strict current Theme Flow board projection."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of: CandidateFeedDate
    generated_at: CandidateFeedTimestamp
    benchmark: CandidateFeedTicker
    n_failed_download: Annotated[int, Field(ge=0, le=100_000)]
    buckets: dict[
        ThemeFlowCapitalState,
        Annotated[list[BoundedPublicName], Field(max_length=100)],
    ]
    shared_mega_caps: Annotated[list[ThemeFlowSharedMegaCap], Field(max_length=100)]
    themes: Annotated[list[ThemeFlowTheme], Field(min_length=1, max_length=100)]
    board_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_board_consistency(self) -> "ThemeFlowData":
        expected_states = {
            "加速流入(推估)",
            "流入趨緩",
            "中性",
            "流出(推估)",
        }
        if set(self.buckets) != expected_states:
            raise ValueError("Theme Flow buckets must contain all capital states")
        theme_names = [item.theme for item in self.themes]
        if len(theme_names) != len(set(theme_names)):
            raise ValueError("Theme Flow themes must be unique")
        bucket_names = [name for names in self.buckets.values() for name in names]
        if len(bucket_names) != len(set(bucket_names)) or set(bucket_names) != set(theme_names):
            raise ValueError("Theme Flow buckets must partition the projected themes")
        shared = [item.ticker for item in self.shared_mega_caps]
        if len(shared) != len(set(shared)):
            raise ValueError("Theme Flow shared mega-cap tickers must be unique")
        return self


class ThemeFlowReadItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    theme: BoundedPublicName
    name: Annotated[str, Field(max_length=500)]
    why: BoundedPublicText


class ThemeFlowRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    headline: BoundedPublicText
    confidence: Literal["high", "medium", "low"]
    accelerating_in: Annotated[list[ThemeFlowReadItem], Field(max_length=20)]
    rotating_out: Annotated[list[ThemeFlowReadItem], Field(max_length=20)]
    bottom_fishing: Annotated[list[ThemeFlowReadItem], Field(max_length=20)]
    insider_divergence: Annotated[list[ThemeFlowReadItem], Field(max_length=20)]
    next_thesis: BoundedPublicText
    caveats: Annotated[list[BoundedPublicText], Field(max_length=20)]


class ThemeFlowAnalysisData(ArtifactDataModel):
    """Strict current-validation Theme Flow AI presentation read."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ready"]
    as_of: CandidateFeedDate
    generated_at: CandidateFeedTimestamp
    board_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    read: ThemeFlowRead

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)


class MoneyFlowCoverage(BaseModel):
    """Closed producer coverage accounting for one Money Flow snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    requested: Annotated[int, Field(ge=0, le=100_000)]
    resolved: Annotated[int, Field(ge=0, le=100_000)]
    unavailable: Annotated[int, Field(ge=0, le=100_000)]
    coverage_ratio: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    min_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

    @model_validator(mode="after")
    def validate_accounting(self) -> "MoneyFlowCoverage":
        if self.requested != self.resolved + self.unavailable:
            raise ValueError("requested must equal resolved plus unavailable")
        expected_ratio = self.resolved / self.requested if self.requested else 0.0
        if not isclose(self.coverage_ratio, expected_ratio, rel_tol=0, abs_tol=1e-12):
            raise ValueError("coverage_ratio must equal resolved divided by requested")
        return self


class MoneyFlowRow(BaseModel):
    """Allowlisted daily flow fields used by approved presentation consumers."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: CandidateFeedTicker
    date: CandidateFeedDate
    main_net: (
        Annotated[float, Field(ge=-1e15, le=1e15, allow_inf_nan=False)] | None
    )
    main_pct: (
        Annotated[float, Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)]
        | None
    )
    small_net: (
        Annotated[float, Field(ge=-1e15, le=1e15, allow_inf_nan=False)] | None
    )
    source: Literal["eastmoney_push2his"]

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)


class MoneyFlowData(ArtifactDataModel):
    """Strict Money Flow presentation projection."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    as_of_date: CandidateFeedDate
    generated_at: CandidateFeedTimestamp
    source: Literal["eastmoney_push2his"]
    publishable: bool
    coverage: MoneyFlowCoverage
    rows: Annotated[list[MoneyFlowRow], Field(max_length=50_000)]

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date(cls, value: str) -> str:
        return _validate_candidate_feed_date(value)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_snapshot_consistency(self) -> "MoneyFlowData":
        expected_publishable = bool(
            self.coverage.requested
            and self.coverage.coverage_ratio >= self.coverage.min_coverage
        )
        if self.publishable is not expected_publishable:
            raise ValueError("publishable must match the producer coverage gate")
        row_keys = [(row.ticker, row.date) for row in self.rows]
        if len(row_keys) != len(set(row_keys)):
            raise ValueError("Money Flow ticker/date rows must be unique")
        resolved_tickers = {row.ticker for row in self.rows}
        if len(resolved_tickers) != self.coverage.resolved:
            raise ValueError("resolved must equal the number of tickers with rows")
        return self


_PUBLIC_TEXT_RE = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$")
_PUBLIC_NONEMPTY_TEXT_RE = re.compile(
    r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+$"
)
KnowledgeGraphId = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
]
KnowledgeGraphOptionalText = Annotated[
    str,
    Field(max_length=200, pattern=_PUBLIC_TEXT_RE.pattern),
]


class KnowledgeGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: KnowledgeGraphId
    label: KnowledgeGraphId
    type: Literal["dimension", "factor", "paper", "moc", "note"]
    dimension: Literal["", "Dim1", "Dim2", "Dim3", "Dim4", "Dim5", "Dim6", "Dim7", "meta", "framework"]
    horizon: Literal["", "short", "mid", "long", "na"]
    status: Literal["validated", "exploratory", "weak", "noise", "contrarian", "seed", "index"]
    blocked: bool
    lift_exploratory: Annotated[
        float,
        Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False),
    ] | None
    runway_verdict: Literal["", "exploratory"]
    verdict_raw: Literal["", "VALIDATED", "WEAK", "NOISE", "CONTRARIAN"]

    @field_validator("id", "label")
    @classmethod
    def validate_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Knowledge Graph text must be trimmed")
        return value

    @model_validator(mode="after")
    def validate_blocked_status(self) -> "KnowledgeGraphNode":
        if self.blocked and (self.type != "factor" or self.status != "exploratory"):
            raise ValueError("blocked nodes must be exploratory factors")
        return self


class KnowledgeGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: KnowledgeGraphId
    target: KnowledgeGraphId
    type: Literal["belongs_to_dimension", "evidence", "references", "index_link"]

    @field_validator("source", "target")
    @classmethod
    def validate_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Knowledge Graph ids must be trimmed")
        return value

    @model_validator(mode="after")
    def validate_not_self_edge(self) -> "KnowledgeGraphEdge":
        if self.source == self.target:
            raise ValueError("self edges are not publishable")
        return self


class KnowledgeGraphUnresolvedLink(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: KnowledgeGraphId
    target: KnowledgeGraphId

    @field_validator("source", "target")
    @classmethod
    def validate_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Knowledge Graph ids must be trimmed")
        return value


class KnowledgeGraphDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    unresolved_links: Annotated[
        list[KnowledgeGraphUnresolvedLink],
        Field(max_length=1_000),
    ]
    duplicate_ids: Annotated[list[KnowledgeGraphId], Field(max_length=0)]

    @model_validator(mode="after")
    def validate_unique_unresolved(self) -> "KnowledgeGraphDiagnostics":
        pairs = [(item.source, item.target) for item in self.unresolved_links]
        if len(pairs) != len(set(pairs)):
            raise ValueError("unresolved links must be unique")
        return self


class KnowledgeGraphData(ArtifactDataModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    nodes: Annotated[list[KnowledgeGraphNode], Field(max_length=500)]
    edges: Annotated[list[KnowledgeGraphEdge], Field(max_length=5_000)]
    diagnostics: KnowledgeGraphDiagnostics

    @model_validator(mode="after")
    def validate_graph_consistency(self) -> "KnowledgeGraphData":
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        node_ids = set(ids)
        edge_keys = [(edge.source, edge.target, edge.type) for edge in self.edges]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("edges must be unique")
        if any(edge.source not in node_ids or edge.target not in node_ids for edge in self.edges):
            raise ValueError("edge endpoints must exist")
        if any(item.source not in node_ids for item in self.diagnostics.unresolved_links):
            raise ValueError("unresolved link sources must exist")
        return self


class ThemeTaxonomyItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[
        str,
        Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
    ]
    description: Annotated[
        str,
        Field(max_length=2_000, pattern=_PUBLIC_TEXT_RE.pattern),
    ]

    @field_validator("name")
    @classmethod
    def validate_trimmed_name(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("theme names must be trimmed")
        return value


class ThemeTaxonomyData(ArtifactDataModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    themes: Annotated[list[ThemeTaxonomyItem], Field(max_length=100)]

    @model_validator(mode="after")
    def validate_unique_names(self) -> "ThemeTaxonomyData":
        names = [theme.name.casefold() for theme in self.themes]
        if len(names) != len(set(names)):
            raise ValueError("theme names must be unique")
        return self


class ThemeDrillSector(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    etf: Literal[
        "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
        "XLP", "XLRE", "XLU", "XLV", "XLY",
    ]
    themes: Annotated[
        list[
            Annotated[
                str,
                Field(
                    min_length=1,
                    max_length=200,
                    pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern,
                ),
            ]
        ],
        Field(min_length=1, max_length=100),
    ]

    @model_validator(mode="after")
    def validate_themes(self) -> "ThemeDrillSector":
        if any(theme != theme.strip() for theme in self.themes):
            raise ValueError("theme names must be trimmed")
        folded = [theme.casefold() for theme in self.themes]
        if len(folded) != len(set(folded)):
            raise ValueError("sector theme names must be unique")
        return self


class ThemeDrillData(ArtifactDataModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sectors: Annotated[list[ThemeDrillSector], Field(max_length=11)]

    @model_validator(mode="after")
    def validate_drill(self) -> "ThemeDrillData":
        etfs = [sector.etf for sector in self.sectors]
        if etfs != sorted(etfs) or len(etfs) != len(set(etfs)):
            raise ValueError("sectors must be unique and sorted by ETF")
        unique_themes = {
            theme.casefold()
            for sector in self.sectors
            for theme in sector.themes
        }
        if len(unique_themes) > 100:
            raise ValueError("theme drill supports at most 100 unique themes")
        return self


class InfluencerRosterItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    handle: Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{1,15}$")]
    name: Annotated[str, Field(max_length=200, pattern=_PUBLIC_TEXT_RE.pattern)] | None = None
    category: Annotated[
        str,
        Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
    ]
    market: Literal["US", "CRYPTO"]
    note: Annotated[str, Field(max_length=2_000, pattern=_PUBLIC_TEXT_RE.pattern)] | None = None
    url: Annotated[str, Field(max_length=500, pattern=r"^https://[^\s\x00-\x1f\x7f]+$")] | None = None
    category_source: Annotated[str, Field(max_length=200, pattern=_PUBLIC_TEXT_RE.pattern)] | None = None
    category_reason: Annotated[str, Field(max_length=2_000, pattern=_PUBLIC_TEXT_RE.pattern)] | None = None
    category_confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None
    placeholder: bool = False

    @field_validator("category")
    @classmethod
    def validate_trimmed_category(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("influencer categories must be trimmed")
        return value

    @model_validator(mode="after")
    def validate_url_handle_parity(self) -> "InfluencerRosterItem":
        if self.url is None:
            return self
        parsed = urlsplit(self.url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("influencer URL port is invalid") from exc
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or (parsed.hostname or "").casefold() not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
            or parsed.query
            or parsed.fragment
            or parsed.path.strip("/").casefold() != self.handle.casefold()
        ):
            raise ValueError("influencer URL must be a matching X/Twitter profile")
        return self


class InfluencerRosterData(ArtifactDataModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    categories: Annotated[
        list[
            Annotated[
                str,
                Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
            ]
        ],
        Field(max_length=1_000),
    ]
    influencers: Annotated[list[InfluencerRosterItem], Field(max_length=1_000)]

    @model_validator(mode="after")
    def validate_roster_consistency(self) -> "InfluencerRosterData":
        if any(category != category.strip() for category in self.categories):
            raise ValueError("roster categories must be trimmed")
        category_keys = [category.casefold() for category in self.categories]
        if len(category_keys) != len(set(category_keys)):
            raise ValueError("roster categories must be unique")
        row_keys = [(row.market, row.handle.casefold()) for row in self.influencers]
        if len(row_keys) != len(set(row_keys)):
            raise ValueError("roster handles must be unique per market")
        if any(row.category.casefold() not in set(category_keys) for row in self.influencers):
            raise ValueError("every roster category must be declared")
        return self


IndustryRoleId = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
IndustryRoleTicker = Annotated[
    str,
    Field(min_length=1, max_length=15, pattern=r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$"),
]
IndustryRoleTimestamp = Annotated[
    str,
    Field(
        min_length=20,
        max_length=32,
        pattern=_OPTIONS_FLOW_RFC3339_PATTERN,
        json_schema_extra={
            "format": "date-time",
            "pattern": _OPTIONS_FLOW_RFC3339_SCHEMA_PATTERN,
        },
    ),
]
IndustryRoleText = Annotated[
    str,
    Field(min_length=1, max_length=1_000, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
]


class IndustryRoleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: IndustryRoleId
    name: Annotated[
        str,
        Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
    ]


class IndustryRoleApprovedAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: IndustryRoleTicker
    primary_role: IndustryRoleId
    secondary_roles: Annotated[list[IndustryRoleId], Field(max_length=20)]
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None
    reviewed_at: IndustryRoleTimestamp | None

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: str | None) -> str | None:
        return None if value is None else _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_secondary_roles(self) -> "IndustryRoleApprovedAssignment":
        if self.primary_role in self.secondary_roles:
            raise ValueError("primary role cannot also be secondary")
        if len(self.secondary_roles) != len(set(self.secondary_roles)):
            raise ValueError("secondary roles must be unique")
        return self


class IndustryRoleSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    ticker: IndustryRoleTicker
    suggested_primary_role: IndustryRoleId
    suggested_primary_role_name: Annotated[
        str,
        Field(min_length=1, max_length=200, pattern=_PUBLIC_NONEMPTY_TEXT_RE.pattern),
    ] | None
    suggested_secondary_roles: Annotated[list[IndustryRoleId], Field(max_length=20)]
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    evidence: Annotated[list[IndustryRoleText], Field(max_length=20)]
    status: Literal["suggested", "approved", "rejected", "deferred"]
    reviewed_at: IndustryRoleTimestamp | None

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: str | None) -> str | None:
        return None if value is None else _validate_candidate_feed_timestamp(value)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: list[str]) -> list[str]:
        allowed_fixed = {
            "social_heat: mentioned in current social sources",
            "fallback: no taxonomy/theme match yet",
        }
        if any(
            item not in allowed_fixed and not item.startswith("theme_baskets: ")
            for item in value
        ):
            raise ValueError("suggestion evidence must use an allowlisted source label")
        return value

    @model_validator(mode="after")
    def validate_secondary_roles(self) -> "IndustryRoleSuggestion":
        if self.suggested_primary_role in self.suggested_secondary_roles:
            raise ValueError("suggested primary role cannot also be secondary")
        if len(self.suggested_secondary_roles) != len(
            set(self.suggested_secondary_roles)
        ):
            raise ValueError("suggested secondary roles must be unique")
        return self


class IndustryRoleGenerateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["generate"]
    tickers: Annotated[list[IndustryRoleTicker], Field(min_length=1, max_length=1_000)]

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("generation tickers must be unique")
        return value


class IndustryRoleApproveAction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    action: Literal["approve"]
    ticker: IndustryRoleTicker
    primary_role: IndustryRoleId = Field(alias="primaryRole")
    secondary_roles: Annotated[
        list[IndustryRoleId],
        Field(max_length=20),
    ] = Field(alias="secondaryRoles")

    @model_validator(mode="after")
    def validate_roles(self) -> "IndustryRoleApproveAction":
        if self.primary_role in self.secondary_roles:
            raise ValueError("primary role cannot also be secondary")
        if len(self.secondary_roles) != len(set(self.secondary_roles)):
            raise ValueError("secondary roles must be unique")
        return self


class IndustryRoleRejectAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["reject"]
    ticker: IndustryRoleTicker


class IndustryRoleDeferAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["defer"]
    ticker: IndustryRoleTicker


IndustryRoleActionRequest = Annotated[
    IndustryRoleGenerateAction
    | IndustryRoleApproveAction
    | IndustryRoleRejectAction
    | IndustryRoleDeferAction,
    Field(discriminator="action"),
]


class IndustryRoleMutationResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    operator: Literal["operator"]
    action: Literal["generate", "approve", "reject", "defer"]
    ticker: IndustryRoleTicker | None
    transaction_id: Annotated[str, Field(min_length=36, max_length=36)] = Field(
        alias="transactionId"
    )
    revision: Annotated[int, Field(ge=1)]
    replayed: bool


class IndustryRoleReviewBoardData(ArtifactDataModel):
    """Strict protected projection for the singleton operator's review board."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    operator: Literal["operator"]
    taxonomy_version: Annotated[int, Field(ge=1, le=1_000_000)]
    generated_at: IndustryRoleTimestamp | None
    roles: Annotated[list[IndustryRoleDefinition], Field(max_length=200)]
    approved: Annotated[
        list[IndustryRoleApprovedAssignment],
        Field(max_length=5_000),
    ]
    suggestions: Annotated[list[IndustryRoleSuggestion], Field(max_length=5_000)]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str | None) -> str | None:
        return None if value is None else _validate_candidate_feed_timestamp(value)

    @model_validator(mode="after")
    def validate_review_board(self) -> "IndustryRoleReviewBoardData":
        role_names = {role.id: role.name for role in self.roles}
        if len(role_names) != len(self.roles):
            raise ValueError("industry role ids must be unique")
        approved_tickers = [row.ticker for row in self.approved]
        if len(approved_tickers) != len(set(approved_tickers)):
            raise ValueError("approved tickers must be unique")
        suggestion_keys = [
            (row.ticker, row.suggested_primary_role) for row in self.suggestions
        ]
        if len(suggestion_keys) != len(set(suggestion_keys)):
            raise ValueError("industry role suggestions must be unique")
        for row in self.approved:
            if row.primary_role not in role_names or any(
                role not in role_names for role in row.secondary_roles
            ):
                raise ValueError("approved assignments must reference declared roles")
        for row in self.suggestions:
            pending = row.suggested_primary_role == "classification_pending"
            if not pending and row.suggested_primary_role not in role_names:
                raise ValueError("suggestions must reference declared roles")
            if any(role not in role_names for role in row.suggested_secondary_roles):
                raise ValueError("suggested secondary roles must be declared")
            expected_name = "待分類" if pending else role_names[row.suggested_primary_role]
            if row.suggested_primary_role_name != expected_name:
                raise ValueError("suggested role name must match the taxonomy")
        return self


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    status: Literal["ok"]
    api_version: Literal["v1"] = Field(alias="apiVersion")


class Problem(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(json_schema_extra={"format": "uri-reference"})
    title: str
    status: int = Field(ge=400, le=599)
    detail: str = Field(default_factory=str)
    instance: str = Field(
        default_factory=str,
        json_schema_extra={"format": "uri-reference"},
    )
