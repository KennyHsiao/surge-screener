"""Fixed artifact registry and fail-soft read orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from math import isclose, isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypeAlias

from pydantic import ValidationError

from api.models import (
    AiUpdatesData,
    ArtifactAvailable,
    ArtifactDataModel,
    ArtifactMeta,
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
    OptionsFlowData,
    OptionsFlowFeedData,
    OversoldReversalData,
    OversoldReversalValidationData,
    PlaybookValidationData,
    ContinuationValidationData,
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
    normalize_ticker,
)
from scripts.artifact_loader import (
    ArtifactAvailable as LoadedArtifact,
    ArtifactUnavailable as UnloadedArtifact,
    load_json_artifact,
)
from scripts.runtime_paths import candidate_output_path
from scripts import knowledge_graph as knowledge_graph_engine


REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
CONTENT_DIR = REPO_ROOT / "content"
KNOWLEDGE_VAULT = REPO_ROOT / "knowledge"
KNOWLEDGE_GRAPH_SOURCE_ID = "knowledge.graph"
THEME_TAXONOMY_SOURCE_ID = "watchlists.theme-taxonomy"
THEME_TAXONOMY_FILE = CONTENT_DIR / "themes.json"
THEME_DRILL_SOURCE_ID = "market-context.theme-drill"
THEME_DRILL_FILE = CONTENT_DIR / "theme_baskets.json"
INFLUENCER_ROSTER_SOURCE_ID = "social.influencers.roster"
MARKET_THESIS_DIR = REPORTS_DIR / "market_thesis"
IV_HISTORY_DIR = REPORTS_DIR / "iv_history"
IV_HISTORY_SOURCE_ID = "options.iv-history"
FUND_CATALOG_SOURCE_ID = "institutions.funds"
FUND_CATALOG_FILE = CONTENT_DIR / "funds.json"
AI_UPDATES_SOURCE_ID = "system.ai-updates"
AI_UPDATES_FILE = CONTENT_DIR / "ai_updates.json"
SCHEDULES_SOURCE_ID = "system.schedules"
SCHEDULES_FILE = CONTENT_DIR / "schedules.json"
CRYPTO_UNIVERSE_SOURCE_ID = "crypto.universe"
CRYPTO_UNIVERSE_FILE = REPORTS_DIR / "crypto" / "universe_latest.json"
OPTIONS_FLOW_FILE = REPORTS_DIR / "options_flow" / "latest.json"
OPTIONS_FLOW_FEED_SOURCE_ID = "signals.options-flow.feed"
MARKET_THESIS_SOURCE_ID = "market-context.market-thesis.latest"
DAILY_SUMMARY_SOURCE_ID = "reports.daily-summary.latest"
PLAYBOOK_VALIDATION_SOURCE_ID = "reports.playbook-validation.latest"
PLAYBOOK_VALIDATION_FILE = REPORTS_DIR / "playbook_validation" / "latest.json"
CONTINUATION_VALIDATION_SOURCE_ID = "reports.continuation-validation.latest"
CONTINUATION_VALIDATION_FILE = (
    REPORTS_DIR / "retrospective" / "continuation_strength.json"
)
COT_CATALOG_SOURCE_ID = "reports.cot.catalog"
COT_DETAIL_SOURCE_ID = "reports.cot.detail"
COT_REPORTS_DIR = REPORTS_DIR / "cot"
MARKET_THESIS_VALIDATION_SOURCE_ID = "market-context.market-thesis.validation"
MARKET_THESIS_VALIDATION_FILE = MARKET_THESIS_DIR / "validation_summary.json"
MARKET_THESIS_REGIME_HISTORY_SOURCE_ID = (
    "market-context.market-thesis.regime-history"
)
MARKET_THESIS_REGIME_HISTORY_FILE = MARKET_THESIS_DIR / "regime_history.json"
REVERSAL_RADAR_SOURCE_ID = "signals.reversal-radar.latest"
REVERSAL_RADAR_VALIDATION_SOURCE_ID = "signals.reversal-radar.validation"
REVERSAL_RADAR_VALIDATION_FILE = (
    REPORTS_DIR / "reversal_radar" / "validation_summary.json"
)
OVERSOLD_REVERSAL_SOURCE_ID = "signals.oversold-reversal.latest"
OVERSOLD_REVERSAL_VALIDATION_SOURCE_ID = "signals.oversold-reversal.validation"
OVERSOLD_REVERSAL_VALIDATION_FILE = (
    REPORTS_DIR / "oversold_reversal" / "validation_summary.json"
)
RANKED_CANDIDATES_FEED_SOURCE_ID = "candidates.ranked.feed"
SCORED_CANDIDATES_FEED_SOURCE_ID = "candidates.scored.feed"
SCORED_CANDIDATES_SCREENER_SOURCE_ID = "candidates.scored.screener"
SOCIAL_INTELLIGENCE_SOURCE_ID = "social.intelligence.latest"
SOCIAL_INTELLIGENCE_FILE = REPORTS_DIR / "social_intelligence" / "latest.json"
THEME_FLOW_SOURCE_ID = "market-context.theme-flow.latest"
THEME_FLOW_FILE = REPORTS_DIR / "theme_flow_snapshot.json"
THEME_FLOW_ANALYSIS_SOURCE_ID = "market-context.theme-flow.analysis"
THEME_FLOW_ANALYSIS_FILE = REPORTS_DIR / "theme_flow.json"
THEME_FLOW_SCHEMA_VERSION = 5
THEME_FLOW_ANALYSIS_VALIDATION_VERSION = 8
MONEY_FLOW_SOURCE_ID = "market-context.money-flow.latest"
MONEY_FLOW_FILE = REPORTS_DIR / "money_flow" / "latest.json"
SECTOR_ROTATION_SOURCE_ID = "market-context.sector-rotation.latest"
SECTOR_ROTATION_ARCHIVE_DIR = REPORTS_DIR / "sector_rotation_snapshots"
_SECTOR_ROTATION_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
_DAILY_SUMMARY_DIRECTORY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DAILY_SUMMARY_BASE_FIELDS = frozenset(
    {
        "report_date",
        "regime_summary",
        "total_confirmed",
        "ranked_picks",
        "cross_candidate_commentary",
        "portfolio_notes",
    }
)
_DAILY_SUMMARY_RANKED_FIELDS = frozenset(
    {
        "rank",
        "ticker",
        "final_score",
        "verdict",
        "thesis",
        "entry_zone",
        "stop_loss",
        "position_size_pct",
        "key_risk",
    }
)
_DAILY_SUMMARY_WATCHLIST_FIELDS = frozenset(
    {"ticker", "score", "verdict", "note"}
)
_PLAYBOOK_VALIDATION_BLOCKED_FIELDS = frozenset(
    {
        "generated_at",
        "status",
        "reason",
        "resolved",
        "min_resolved",
        "playbooks",
        "factors",
    }
)
_PLAYBOOK_VALIDATION_ACTIVE_FIELDS = frozenset(
    {
        "generated_at",
        "status",
        "resolved",
        "min_resolved",
        "decision_count",
        "outcome_count",
        "playbooks",
        "factors",
    }
)
_PLAYBOOK_VALIDATION_PLAYBOOK_FIELDS = frozenset(
    {
        "playbook",
        "resolved",
        "mean_fwd_7d_return",
        "hit_rate_7d",
        "verdict",
    }
)
_PLAYBOOK_VALIDATION_FACTOR_FIELDS = frozenset(
    {
        "factor_id",
        "resolved",
        "mean_fwd_7d_return",
        "hit_rate_7d",
        "verdict",
    }
)
_CONTINUATION_VALIDATION_BLOCKED_FIELDS = frozenset(
    {
        "generated_at",
        "status",
        "reason",
        "resolved",
        "min_resolved",
        "summary",
        "rows",
    }
)
_CONTINUATION_VALIDATION_ACTIVE_FIELDS = frozenset(
    {
        "generated_at",
        "status",
        "resolved",
        "min_resolved",
        "summary",
        "rows",
        "note",
    }
)
_CONTINUATION_VALIDATION_ROW_FIELDS = frozenset(
    {
        "ticker",
        "setup_date",
        "surge_start",
        "thresholds_hit",
        "magnitude_pct",
        "candidate_causes",
        "cause_certainty",
        "measurement_source",
        "resolved_30d",
        "fwd_30d_return",
        "fwd_30d_max_drawdown",
        "resolved_60d",
        "fwd_60d_return",
        "fwd_60d_max_drawdown",
        "continuation_label",
        "primary_horizon",
        "trade_value",
    }
)
_COT_MARKDOWN_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
_COT_CATALOG_LIMIT = 520
_COT_MARKDOWN_MAX_BYTES = 256 * 1024
_COT_VERIFIED_MAX_BYTES = 64 * 1024
_SECTOR_ROTATION_BASE_SOURCE_FIELDS = frozenset(
    {
        "status",
        "generated_at",
        "as_of",
        "benchmark",
        "leaders",
        "improving",
        "macro",
        "sectors",
    }
)
_SECTOR_ROTATION_PUBLIC_FIELDS = ("as_of", "benchmark", "sectors")
_SECTOR_ROTATION_ROW_PUBLIC_FIELDS = (
    "etf",
    "name_zh",
    "group",
    "theme",
    "quadrant",
    "quadrant_zh",
    "rs_ratio",
    "rs_momentum",
    "heat_score",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "excess_20d",
    "pct_vs_ma50",
    "pct_vs_ma200",
    "pct_from_52w_high",
    "rvol",
)
_SECTOR_ROTATION_SOURCE_ROW_FIELDS = frozenset(
    _SECTOR_ROTATION_ROW_PUBLIC_FIELDS
)
_SECTOR_ROTATION_MACRO_FIELDS = frozenset(
    {"spy_price", "spy_vs_50dma", "spy_vs_200dma", "vix_level"}
)
_SECTOR_ROTATION_READ_FIELDS = frozenset(
    {
        "headline",
        "confidence",
        "hot_now",
        "rotating_into",
        "next_rotation_thesis",
        "cycle_read",
        "caveats",
    }
)
_SECTOR_ROTATION_READ_ITEM_FIELDS = frozenset({"etf", "name", "why"})
_MONEY_FLOW_SOURCE_FIELDS = frozenset(
    {"as_of_date", "generated_at", "source", "publishable", "coverage", "rows"}
)
_MONEY_FLOW_COVERAGE_FIELDS = frozenset(
    {"requested", "resolved", "unavailable", "coverage_ratio", "min_coverage"}
)
_MONEY_FLOW_ROW_SOURCE_FIELDS = frozenset(
    {
        "ticker",
        "secid",
        "date",
        "close",
        "change_pct",
        "main_net",
        "main_pct",
        "super_big_net",
        "big_net",
        "mid_net",
        "small_net",
        "source",
        "raw_row",
    }
)
_MONEY_FLOW_ROW_PUBLIC_FIELDS = (
    "ticker",
    "date",
    "main_net",
    "main_pct",
    "small_net",
    "source",
)
_RANKED_CANDIDATES_FEED_SOURCE_FIELDS = frozenset(
    {
        "all_ranked_count",
        "as_of_date",
        "generated_at",
        "markets",
        "money_flow_scoring",
        "options_gate",
        "passed_hard_filters",
        "rank_buckets",
        "rank_limit",
        "ranked_candidates",
        "ranked_candidates_count",
        "scan_date",
        "score_weights",
        "scoring_model",
        "source",
        "tickers",
        "total_candidates",
        "total_universe",
        "universe",
    }
)
_RANKED_CANDIDATE_PUBLIC_FIELDS = (
    "ticker",
    "rank_score",
    "last_price",
    "rank_bucket",
    "ret_5d",
    "ret_20d",
    "warnings",
)
_RANKED_COMPONENT_PUBLIC_FIELDS = (
    "technical_trend",
    "momentum_strength",
    "launch_signal",
    "liquidity_tradability",
    "overheat_risk_control",
)
_RANKED_OPTIONS_PUBLIC_FIELDS = (
    "status",
    "iv_percentile",
    "spread_pct",
    "flow_score",
    "warnings",
)
_SCORED_CANDIDATES_FEED_SOURCE_FIELDS = frozenset(
    {
        "all_scored",
        "min_score_threshold",
        "needs_layer2",
        "needs_layer2_count",
        "passed_hard_filters",
        "regime_context",
        "rejected_count",
        "remaining_unscored",
        "scan_date",
        "scored_candidates_count",
        "total_candidates",
        "universe_size",
        "watchlist",
        "watchlist_count",
    }
)
_SCORED_CANDIDATE_PUBLIC_FIELDS = (
    "ticker",
    "verdict",
    "composite_score",
    "regime_adjusted_score",
    "data_missing",
    "due_diligence_required",
    "key_signals",
    "key_risks",
    "suggested_entry_zone",
)
_SCORED_SCORE_PUBLIC_FIELDS = (
    "technical",
    "catalyst",
    "sentiment",
    "institutional",
    "sector_market",
    "options_flow",
    "analyst",
)
_SCORED_SCREENER_CANDIDATE_PUBLIC_FIELDS = (
    "ticker",
    "verdict",
    "regime_adjusted_score",
    "key_signals",
    "key_risks",
    "suggested_entry_zone",
    "suggested_stop",
    "suggested_size_pct",
    "anti_example_warning",
    "data_missing",
)
_SCORED_SCREENER_REGIME_PUBLIC_FIELDS = (
    "spy_vs_50dma",
    "spy_vs_200dma",
    "vix_level",
    "vix_regime",
    "global_score_multiplier",
    "active_themes",
    "regime_warnings",
)
_SCORED_SCREENER_TECHNICAL_PUBLIC_FIELDS = (
    "pattern_type",
    "macd_state",
)
_OPTIONS_FLOW_FEED_SOURCE_FIELDS = frozenset(
    {
        "generated_at",
        "as_of",
        "provider",
        "universe_size",
        "min_notional",
        "signal_count",
        "note",
        "signals",
    }
)
_OPTIONS_FLOW_FEED_PUBLIC_FIELDS = (
    "generated_at",
    "as_of",
    "provider",
    "universe_size",
    "min_notional",
    "signal_count",
)
_OPTIONS_FLOW_SIGNAL_FIELDS = (
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
_OPTIONS_FLOW_BIGGEST_FIELDS = ("strike", "notional")
_SOCIAL_INTELLIGENCE_SOURCE_FIELDS = frozenset(
    {
        "as_of_date",
        "generated_at",
        "source",
        "schema_version",
        "market",
        "source_statuses",
        "tickers",
        "limitations",
    }
)
_SOCIAL_SOURCE_STATUS_FIELDS = frozenset(
    {"label", "cost_mode", "status", "note"}
)
_SOCIAL_SOURCE_STATUS_KEYS = frozenset(
    {
        "codex_web_research",
        "x_official_api",
        "agent_reach",
        "stocktwits",
        "apewisdom",
    }
)
_SOCIAL_TICKER_SOURCE_FIELDS = frozenset(
    {
        "ticker",
        "mentioned_by",
        "citations",
        "discovery_sources",
        "cost_modes",
        "skew",
        "conviction",
        "note",
        "heat_baseline",
        "platform_validation",
        "labels",
    }
)
_SOCIAL_TICKER_PUBLIC_FIELDS = (
    "ticker",
    "mentioned_by",
    "citations",
    "skew",
    "conviction",
    "note",
    "platform_validation",
    "labels",
)
_SOCIAL_PLATFORM_VALIDATION_FIELDS = (
    "in_ranked_candidates",
    "rank_score",
    "rank_bucket",
    "last_price",
    "options_flow_score",
    "options_direction",
)
_SOCIAL_LABEL_FIELDS = (
    "x_mentioned",
    "agent_reach",
    "retail_heat",
    "crowded",
    "early_signal",
    "paid_data_needed",
)
_THEME_FLOW_SOURCE_FIELDS = frozenset(
    {
        "as_of",
        "generated_at",
        "benchmark",
        "schema_version",
        "n_failed_download",
        "params",
        "themes",
        "buckets",
        "bottom_fishing",
        "shared_mega_caps",
    }
)
_THEME_FLOW_THEME_SOURCE_FIELDS = frozenset(
    {
        "theme",
        "desc",
        "parent_sector_etfs",
        "flow_5d",
        "flow_20d",
        "accel",
        "flow_5d_norm",
        "flow_20d_norm",
        "accel_norm",
        "rvol",
        "ret_5d",
        "excess_5d",
        "top_share",
        "high_concentration",
        "breadth_inflow_ratio",
        "positive_flow_count",
        "negative_flow_count",
        "n_used",
        "n_total",
        "n_failed",
        "reps",
        "raw_heat_score",
        "signal_quality",
        "heat_score",
        "capital_state",
        "bottom_fishing",
        "eastmoney_main_net_5d",
        "eastmoney_main_net_20d",
        "eastmoney_main_pct_latest",
        "money_flow_source",
        "money_flow_caveat",
    }
)
_THEME_FLOW_THEME_PUBLIC_FIELDS = (
    "theme",
    "desc",
    "parent_sector_etfs",
    "flow_5d",
    "flow_20d",
    "accel",
    "flow_5d_norm",
    "flow_20d_norm",
    "accel_norm",
    "ret_5d",
    "top_share",
    "high_concentration",
    "breadth_inflow_ratio",
    "positive_flow_count",
    "negative_flow_count",
    "n_used",
    "n_total",
    "reps",
    "raw_heat_score",
    "signal_quality",
    "heat_score",
    "capital_state",
    "bottom_fishing",
)
_THEME_FLOW_REP_FIELDS = ("ticker", "flow_20d", "flow_5d", "ret_5d")
_THEME_FLOW_SHARED_CAP_FIELDS = ("ticker", "themes")
_THEME_FLOW_ANALYSIS_SOURCE_FIELDS = frozenset(
    {
        "status",
        "generated_at",
        "as_of",
        "board_fingerprint",
        "validation_version",
        "read",
        "bottom_fishing",
        "buckets",
        "macro",
    }
)
_THEME_FLOW_READ_FIELDS = (
    "headline",
    "confidence",
    "accelerating_in",
    "rotating_out",
    "bottom_fishing",
    "insider_divergence",
    "next_thesis",
    "caveats",
)
_THEME_FLOW_READ_LIST_FIELDS = (
    "accelerating_in",
    "rotating_out",
    "bottom_fishing",
    "insider_divergence",
)
_THEME_FLOW_READ_ITEM_FIELDS = ("theme", "name", "why")
_CRYPTO_UNIVERSE_SOURCE_FIELDS = frozenset(
    {
        "date",
        "source",
        "source_status",
        "stale",
        "stale_source_date",
        "fetch_error",
        "count",
        "symbols",
        "universe",
        "added",
        "removed",
        "compared_to",
    }
)
_CRYPTO_UNIVERSE_PUBLIC_FIELDS = (
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
_MARKET_THESIS_SOURCE_FIELDS = frozenset(
    {
        "as_of",
        "generated_at",
        "tier",
        "method",
        "benchmark",
        "direction",
        "bucket",
        "support_class",
        "manifest_status",
        "regime",
        "vix_bucket",
        "rationale",
        "label",
    }
)
_MARKET_THESIS_RATIONALE_SOURCE_FIELDS = frozenset(
    {
        "analog",
        "bear_telemetry",
        "manifest_missing",
        "manifest_stale",
        "macro",
        "manifest_events",
    }
)
_MARKET_THESIS_PUBLIC_FIELDS = (
    "as_of",
    "generated_at",
    "direction",
    "bucket",
    "support_class",
    "manifest_status",
    "regime",
    "vix_bucket",
    "label",
)
_MARKET_THESIS_ANALOG_PUBLIC_FIELDS = (
    "status",
    "resolved",
    "mean",
    "up_rate",
    "ci90",
    "p10",
    "worst_mdd",
)
_MARKET_THESIS_EVENT_REQUIRED_FIELDS = frozenset(
    {"type", "source_id", "present", "fresh", "stale_reason"}
)
_MARKET_THESIS_EVENT_SOURCE_FIELDS = frozenset(
    {
        *_MARKET_THESIS_EVENT_REQUIRED_FIELDS,
        "value",
        "delta_1d",
        "last_rate",
        "next_meeting_at",
        "last_decision_at",
        "rate_as_of",
        "released_at",
    }
)
_MARKET_THESIS_EVENT_PUBLIC_FIELDS = (
    "type",
    "source_id",
    "present",
    "fresh",
    "stale_reason",
    "value",
    "delta_1d",
    "last_rate",
    "next_meeting_at",
)
_MARKET_THESIS_VALIDATION_SOURCE_FIELDS = frozenset(
    {
        "generated_at",
        "benchmark",
        "theta_dir",
        "buckets",
        "validation_status",
        "reject_count",
        "rejected_ledgers",
        "note",
        "resolved",
        "matured",
        "invalid_records",
        "invalid_count",
        "min_resolved_for_verdict",
        "by_key",
    }
)
_MARKET_THESIS_VALIDATION_ROW_SOURCE_FIELDS = frozenset(
    {
        "direction",
        "bucket",
        "support_class",
        "raw_N",
        "counted_N",
        "hits",
        "hit_rate",
        "wilson90",
        "verdict",
    }
)
_MARKET_THESIS_VALIDATION_ROW_PUBLIC_FIELDS = (
    "counted_N",
    "hits",
    "hit_rate",
    "wilson90",
    "verdict",
)
_MARKET_THESIS_VALIDATION_KEY_RE = re.compile(
    r"^(看多|看空|盤整)\|(short|mid|long)\|"
    r"(analog_supported|event_only|regime_only)$"
)
_MARKET_THESIS_REGIME_SOURCE_FIELDS = frozenset(
    {
        "generated_at",
        "benchmark",
        "vix",
        "lookback_period",
        "rules",
        "forward_windows_sessions",
        "note",
        "regime_summary",
        "correction_episodes",
        "regime_runs",
        "daily",
    }
)
_MARKET_THESIS_REGIME_NAMES = ("rally", "correction", "range")
_MARKET_THESIS_REGIME_WINDOWS = ("fwd_20d", "fwd_40d", "fwd_60d")
_MARKET_THESIS_REGIME_FIELDS = frozenset(
    {"days", *_MARKET_THESIS_REGIME_WINDOWS}
)
_MARKET_THESIS_REGIME_WINDOW_SOURCE_FIELDS = frozenset(
    {
        "resolved",
        "mean",
        "median",
        "up_rate",
        "ci90",
        "p10",
        "worst",
        "mean_mdd",
        "worst_mdd",
    }
)
_MARKET_THESIS_REGIME_WINDOW_PUBLIC_FIELDS = (
    "mean",
    "up_rate",
    "p10",
    "worst",
)
_REVERSAL_RADAR_SOURCE_FIELDS = frozenset(
    {
        "as_of_date",
        "generated_at",
        "lane_id",
        "universe",
        "universe_size",
        "scanned",
        "match_count",
        "improving_sectors",
        "prescreen",
        "candidates",
        "exploratory",
        "runway_independent",
        "exploratory_gate",
        "cot_confirmation",
        "disclaimer",
        "note",
    }
)
_REVERSAL_RADAR_PUBLIC_FIELDS = (
    "as_of_date",
    "generated_at",
    "lane_id",
    "universe",
    "match_count",
)
_REVERSAL_VALIDATION_TIERS = ("+10%/20d", "+15%/40d", "+20%/60d")
_REVERSAL_VALIDATION_PROVISIONAL = (
    "PROVISIONAL — sample below threshold, indicative only"
)
_REVERSAL_VALIDATION_SOURCE_FIELDS = frozenset(
    {
        "generated_at",
        "module",
        "lane_id",
        "entries_accumulated",
        "price_resolvable",
        "dropped_count",
        "dropped_pct",
        "min_resolved_across_tiers",
        "min_resolved_for_verdict",
        "verdict",
        "verdict_by_tier",
        "survivorship",
        "ev_caveats",
        "note",
        "by_tier",
    }
)
_REVERSAL_VALIDATION_TIER_SOURCE_FIELDS = frozenset(
    {
        "resolved",
        "hits",
        "hit_rate",
        "wilson90",
        "ev_horizon",
        "median_horizon",
        "win_rate_horizon",
        "ev_horizon_ci90",
        "ev_excess_vs_spy",
        "excess_n",
        "excess_win_rate",
        "ev_excess_ci90",
        "equity_multiple",
        "equity_curve",
    }
)
_REVERSAL_VALIDATION_TIER_PUBLIC_FIELDS = (
    "resolved",
    "hits",
    "hit_rate",
    "wilson90",
)
_REVERSAL_VALIDATION_SURVIVORSHIP_FIELDS = frozenset(
    {"survivorship_free", "forward_universe", "caveats"}
)
_OVERSOLD_REVERSAL_SOURCE_FIELDS = frozenset(
    {
        "module",
        "lane_id",
        "definition",
        "primary_signal",
        "runway_independent",
        "runway_note",
        "exploratory",
        "as_of_date",
        "generated_at",
        "universe",
        "liquidity_filter",
        "attempted",
        "scanned",
        "fetch_failed",
        "short_history",
        "stale_history",
        "match_count",
        "validation",
        "validation_caveats",
        "candidates",
        "note",
    }
)
_OVERSOLD_REVERSAL_PUBLIC_FIELDS = (
    "as_of_date",
    "generated_at",
    "lane_id",
    "universe",
    "runway_independent",
    "match_count",
    "scanned",
    "definition",
    "validation_caveats",
    "note",
)
_OVERSOLD_VALIDATION_PUBLIC_FIELDS = (
    "pct_lift",
    "atr_neutral_lift",
    "support",
)
_OVERSOLD_CANDIDATE_PUBLIC_FIELDS = (
    "ticker",
    "last_price",
    "rsi14",
    "bb_width_pct",
    "pct_vs_ma200",
    "pct_from_52w_high",
    "avg_dollar_vol_m",
)
_OVERSOLD_VALIDATION_TIERS = ("+30%/20d", "+40%/40d", "+50%/60d")
_OVERSOLD_VALIDATION_PROVISIONAL = (
    "PROVISIONAL — sample below threshold, indicative only"
)
_OVERSOLD_VALIDATION_SOURCE_FIELDS = frozenset(
    {
        "generated_at",
        "module",
        "lane_id",
        "entries_accumulated",
        "price_resolvable",
        "dropped_count",
        "dropped_pct",
        "min_resolved_across_tiers",
        "min_resolved_for_verdict",
        "verdict",
        "verdict_by_tier",
        "survivorship",
        "sp500_pit_cohort",
        "cost_assumption_round_trip",
        "ev_caveats",
        "note",
        "by_tier",
    }
)
_OVERSOLD_VALIDATION_TIER_SOURCE_FIELDS = frozenset(
    {
        "resolved",
        "hits",
        "hit_rate",
        "wilson90",
        "mature",
        "excess_mature",
        "excess_beta_adj_mature",
        "ev_horizon",
        "median_horizon",
        "win_rate_horizon",
        "ev_horizon_ci90",
        "ev_horizon_net",
        "win_rate_net",
        "ev_horizon_net_ci90",
        "ev_excess_vs_spy",
        "excess_n",
        "excess_win_rate",
        "ev_excess_ci90",
        "ev_excess_beta_adj",
        "excess_beta_adj_n",
        "excess_beta_adj_win_rate",
        "ev_excess_beta_adj_ci90",
        "equity_multiple",
        "equity_multiple_net",
        "equity_curve",
    }
)
_OVERSOLD_VALIDATION_TIER_PUBLIC_FIELDS = (
    "resolved",
    "hits",
    "hit_rate",
    "wilson90",
)
_OVERSOLD_VALIDATION_SURVIVORSHIP_FIELDS = frozenset(
    {
        "survivorship_free",
        "forward_universe",
        "validated_universe",
        "universe_match",
        "caveats",
    }
)
_OVERSOLD_VALIDATION_SP500_FIELDS = frozenset(
    {
        "validated_universe",
        "universe_match",
        "membership",
        "membership_snapshot_through",
        "gate",
        "by_tier",
    }
)
_OVERSOLD_VALIDATION_MEMBERSHIP_FIELDS = frozenset(
    {"member", "non_member", "unknown"}
)
_FORECAST_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RFC3339_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)

ResolutionReason: TypeAlias = Literal["missing", "unreadable"]


@dataclass(frozen=True, slots=True)
class ResolvedArtifactPath:
    path: Path
    as_of: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactPathUnavailable:
    reason: ResolutionReason


ResolutionResult: TypeAlias = ResolvedArtifactPath | ArtifactPathUnavailable
Resolver: TypeAlias = Callable[[], ResolutionResult]
DataValidator: TypeAlias = Callable[[dict[str, object]], bool]
DataProjector: TypeAlias = Callable[[dict[str, object]], dict[str, object]]
AsOfExtractor: TypeAlias = Callable[[dict[str, object]], str | None]
GeneratedAtExtractor: TypeAlias = Callable[[dict[str, object]], str | None]


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    source_id: str
    resolver: Resolver
    data_model: type[ArtifactDataModel]
    object_list_fields: tuple[str, ...] = ()
    string_fields: tuple[str, ...] = ()
    date_fields: tuple[str, ...] = ()
    data_validator: DataValidator | None = None
    data_projector: DataProjector | None = None
    as_of_extractor: AsOfExtractor | None = None
    generated_at_extractor: GeneratedAtExtractor | None = None
    require_resolved_as_of_match: bool = False


def _fixed(path: Path) -> Resolver:
    return lambda: ResolvedArtifactPath(path)


def _candidate_score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if isfinite(converted) else None


def _valid_ranked_candidates_feed_source(data: dict[str, object]) -> bool:
    if set(data) != _RANKED_CANDIDATES_FEED_SOURCE_FIELDS:
        return False
    rows = data.get("ranked_candidates")
    if not isinstance(rows, list) or len(rows) > 500:
        return False
    tickers: list[str] = []
    required = set(_RANKED_CANDIDATE_PUBLIC_FIELDS)
    for row in rows:
        if not isinstance(row, dict) or not required.issubset(row):
            return False
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or _candidate_score(row.get("rank_score")) is None:
            return False
        components = row.get("score_components")
        if not isinstance(components, dict) or not set(
            _RANKED_COMPONENT_PUBLIC_FIELDS
        ).issubset(components):
            return False
        options = row.get("options_tradability")
        if options is not None and (
            not isinstance(options, dict)
            or not set(_RANKED_OPTIONS_PUBLIC_FIELDS).issubset(options)
        ):
            return False
        tickers.append(ticker)
    return len(tickers) == len(set(tickers))


def _project_ranked_candidates_feed(data: dict[str, object]) -> dict[str, object]:
    rows = data["ranked_candidates"]
    if not isinstance(rows, list):
        raise TypeError("validated ranked candidates must be an array")
    ordered = sorted(
        rows,
        key=lambda row: float(row["rank_score"]) if isinstance(row, dict) else 0.0,
        reverse=True,
    )[:100]
    candidates: list[dict[str, object]] = []
    for row in ordered:
        if not isinstance(row, dict):
            raise TypeError("validated ranked candidates must contain objects")
        projected = {field: row[field] for field in _RANKED_CANDIDATE_PUBLIC_FIELDS}
        components = row.get("score_components")
        if not isinstance(components, dict):
            raise TypeError("validated ranked score components must be an object")
        projected["score_components"] = {
            field: components[field] for field in _RANKED_COMPONENT_PUBLIC_FIELDS
        }
        options = row.get("options_tradability")
        if options is None:
            projected["options_tradability"] = None
        elif isinstance(options, dict):
            projected["options_tradability"] = {
                field: options[field] for field in _RANKED_OPTIONS_PUBLIC_FIELDS
            }
        else:
            raise TypeError("validated ranked options summary must be an object")
        candidates.append(projected)
    return {
        "scan_date": data["scan_date"],
        "generated_at": data["generated_at"],
        "candidates": candidates,
    }


def _valid_scored_candidate_row(row: object) -> bool:
    if not isinstance(row, dict) or not set(_SCORED_CANDIDATE_PUBLIC_FIELDS).issubset(row):
        return False
    if not isinstance(row.get("ticker"), str):
        return False
    if _candidate_score(row.get("regime_adjusted_score")) is None:
        return False
    if _candidate_score(row.get("composite_score")) is None:
        return False
    scores = row.get("scores")
    if not isinstance(scores, dict):
        return False
    score_fields = set(scores)
    allowed_score_fields = set(_SCORED_SCORE_PUBLIC_FIELDS)
    required_score_fields = allowed_score_fields - {"analyst"}
    return required_score_fields.issubset(score_fields) and score_fields.issubset(
        allowed_score_fields
    )


def _valid_scored_candidates_feed_source(data: dict[str, object]) -> bool:
    source_fields = set(data)
    if source_fields not in (
        set(_SCORED_CANDIDATES_FEED_SOURCE_FIELDS),
        {*_SCORED_CANDIDATES_FEED_SOURCE_FIELDS, "generated_at"},
    ):
        return False
    if "generated_at" in data and _payload_generated_at(data) is None:
        return False
    for field in ("needs_layer2", "watchlist", "all_scored"):
        rows = data.get(field)
        if (
            not isinstance(rows, list)
            or len(rows) > 500
            or any(not _valid_scored_candidate_row(row) for row in rows)
        ):
            return False
    for bucket, count_field in (
        ("needs_layer2", "needs_layer2_count"),
        ("watchlist", "watchlist_count"),
    ):
        count = data.get(count_field)
        rows = data.get(bucket)
        if isinstance(count, bool) or not isinstance(count, int) or count != len(rows):
            return False
    return True


def _project_scored_candidates_feed(data: dict[str, object]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for bucket in ("needs_layer2", "watchlist", "all_scored"):
        values = data[bucket]
        if not isinstance(values, list):
            raise TypeError("validated scored bucket must be an array")
        for row in values:
            if not isinstance(row, dict):
                raise TypeError("validated scored bucket must contain objects")
            ticker = row.get("ticker")
            if not isinstance(ticker, str):
                raise TypeError("validated scored candidate ticker must be a string")
            if ticker in seen:
                continue
            seen.add(ticker)
            rows.append(row)
    rows.sort(key=lambda row: float(row["regime_adjusted_score"]), reverse=True)
    candidates: list[dict[str, object]] = []
    for row in rows[:100]:
        projected = {field: row[field] for field in _SCORED_CANDIDATE_PUBLIC_FIELDS}
        scores = row.get("scores")
        if not isinstance(scores, dict):
            raise TypeError("validated scored dimensions must be an object")
        projected["scores"] = {
            field: scores.get(field) for field in _SCORED_SCORE_PUBLIC_FIELDS
        }
        candidates.append(projected)
    return {"scan_date": data["scan_date"], "candidates": candidates}


def _project_scored_candidates_screener(
    data: dict[str, object],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for bucket in ("needs_layer2", "watchlist"):
        values = data[bucket]
        if not isinstance(values, list):
            raise TypeError("validated scored screener bucket must be an array")
        for row in values:
            if not isinstance(row, dict):
                raise TypeError("validated scored screener bucket must contain objects")
            ticker = row.get("ticker")
            if not isinstance(ticker, str):
                raise TypeError("validated screener candidate ticker must be a string")
            if ticker in seen:
                continue
            seen.add(ticker)
            rows.append(row)
    rows.sort(key=lambda row: float(row["regime_adjusted_score"]), reverse=True)

    candidates: list[dict[str, object]] = []
    for row in rows[:100]:
        projected = {
            field: row.get(field)
            for field in _SCORED_SCREENER_CANDIDATE_PUBLIC_FIELDS
        }
        scores = row.get("scores")
        if not isinstance(scores, dict):
            raise TypeError("validated scored dimensions must be an object")
        projected["scores"] = {
            field: scores.get(field) for field in _SCORED_SCORE_PUBLIC_FIELDS
        }
        technical = row.get("technical_breakdown")
        if technical is None or technical == {}:
            projected["technical_breakdown"] = None
        elif isinstance(technical, dict):
            projected["technical_breakdown"] = {
                field: technical.get(field)
                for field in _SCORED_SCREENER_TECHNICAL_PUBLIC_FIELDS
            }
        else:
            raise TypeError("validated technical breakdown must be an object")
        candidates.append(projected)

    regime = data.get("regime_context")
    if not isinstance(regime, dict):
        raise TypeError("validated regime context must be an object")
    projected_regime = {
        field: regime.get(field) for field in _SCORED_SCREENER_REGIME_PUBLIC_FIELDS
    }
    projected_regime["global_score_multiplier"] = regime.get(
        "global_score_multiplier", 1.0
    )
    projected_regime["active_themes"] = regime.get("active_themes", [])
    projected_regime["regime_warnings"] = regime.get("regime_warnings", [])
    return {
        "scan_date": data["scan_date"],
        "needs_layer2_count": data["needs_layer2_count"],
        "watchlist_count": data["watchlist_count"],
        "regime_context": projected_regime,
        "candidates": candidates,
    }


def _valid_scored_candidates_screener_source(data: dict[str, object]) -> bool:
    if set(data) not in (
        set(_SCORED_CANDIDATES_FEED_SOURCE_FIELDS),
        {*_SCORED_CANDIDATES_FEED_SOURCE_FIELDS, "generated_at"},
    ):
        return False
    if "generated_at" in data and _payload_generated_at(data) is None:
        return False
    for field in ("needs_layer2", "watchlist", "all_scored"):
        rows = data.get(field)
        if (
            not isinstance(rows, list)
            or len(rows) > 500
            or any(not _valid_scored_candidate_row(row) for row in rows)
        ):
            return False
    for bucket, count_field in (
        ("needs_layer2", "needs_layer2_count"),
        ("watchlist", "watchlist_count"),
    ):
        count = data.get(count_field)
        rows = data.get(bucket)
        if isinstance(count, bool) or not isinstance(count, int) or count != len(rows):
            return False
    try:
        projected = _project_scored_candidates_screener(data)
        ScoredCandidatesScreenerData.model_validate(projected, strict=True)
    except (KeyError, TypeError, ValueError, ValidationError):
        return False
    return True


def _valid_iv_history(data: dict[str, object], expected_ticker: str) -> bool:
    if set(data) != {"ticker", "series"} or data.get("ticker") != expected_ticker:
        return False
    series = data.get("series")
    if not isinstance(series, dict):
        return False
    for raw_date, raw_iv in series.items():
        if not _is_iso_date(raw_date):
            return False
        if isinstance(raw_iv, bool) or not isinstance(raw_iv, (int, float)):
            return False
        if not 0 < raw_iv < 10:
            return False
    return True


def _iv_history_as_of(data: dict[str, object]) -> str | None:
    series = data["series"]
    if not isinstance(series, dict):
        raise TypeError("validated IV history series must be an object")
    return max(series, default=None)


def iv_history_spec(
    ticker: str,
    directory: Path = IV_HISTORY_DIR,
) -> ArtifactSpec:
    """Build one bounded IV-history spec from a validated business identifier."""

    normalized = normalize_ticker(ticker)
    if normalized is None:
        raise ValueError("invalid ticker")
    return ArtifactSpec(
        source_id=IV_HISTORY_SOURCE_ID,
        resolver=_fixed(directory / f"{normalized}.json"),
        data_model=IvHistoryData,
        data_validator=lambda data: _valid_iv_history(data, normalized),
        as_of_extractor=_iv_history_as_of,
    )


def _valid_fund_catalog_source(data: dict[str, object]) -> bool:
    if set(data) != {"_note", "funds"}:
        return False
    note = data.get("_note")
    funds = data.get("funds")
    return isinstance(note, str) and len(note) <= 2000 and isinstance(funds, dict)


def _project_fund_catalog(data: dict[str, object]) -> dict[str, object]:
    funds = data["funds"]
    if not isinstance(funds, dict):
        raise TypeError("validated fund catalog must contain an object")
    return {"funds": funds}


def _valid_ai_updates_source(data: dict[str, object]) -> bool:
    if set(data) != {"_note", "updates"}:
        return False
    note = data.get("_note")
    updates = data.get("updates")
    return (
        isinstance(note, str)
        and len(note) <= 2000
        and isinstance(updates, list)
        and len(updates) <= 200
        and all(isinstance(item, dict) for item in updates)
    )


def _project_ai_updates(data: dict[str, object]) -> dict[str, object]:
    updates = data["updates"]
    if not isinstance(updates, list):
        raise TypeError("validated AI updates must contain an array")
    return {"updates": updates}


def _ai_updates_as_of(data: dict[str, object]) -> str | None:
    updates = data["updates"]
    if not isinstance(updates, list):
        raise TypeError("validated AI updates must contain an array")
    dates: list[str] = []
    for item in updates:
        if not isinstance(item, dict):
            raise TypeError("validated AI updates must contain object items")
        item_date = item.get("date")
        if not isinstance(item_date, str) or not _is_iso_date(item_date):
            raise TypeError("validated AI updates must contain ISO dates")
        dates.append(item_date)
    return max(dates, default=None)


def _valid_schedules_source(data: dict[str, object]) -> bool:
    if set(data) != {"_note", "schedules"}:
        return False
    note = data.get("_note")
    schedules = data.get("schedules")
    return (
        isinstance(note, str)
        and len(note) <= 2000
        and isinstance(schedules, list)
        and len(schedules) <= 100
        and all(isinstance(item, dict) for item in schedules)
    )


def _project_schedules(data: dict[str, object]) -> dict[str, object]:
    schedules = data["schedules"]
    if not isinstance(schedules, list):
        raise TypeError("validated schedules must contain an array")
    return {"schedules": schedules}


def _valid_crypto_universe_source(data: dict[str, object]) -> bool:
    if set(data) != _CRYPTO_UNIVERSE_SOURCE_FIELDS:
        return False
    fetch_error = data.get("fetch_error")
    symbols = data.get("symbols")
    universe = data.get("universe")
    added = data.get("added")
    removed = data.get("removed")
    if fetch_error is not None and (
        not isinstance(fetch_error, str) or len(fetch_error) > 4000
    ):
        return False
    if (
        not isinstance(symbols, list)
        or len(symbols) > 2000
        or any(not isinstance(symbol, str) for symbol in symbols)
        or not isinstance(universe, list)
        or len(universe) > 2000
        or any(not isinstance(item, dict) for item in universe)
        or not isinstance(added, list)
        or len(added) > 2000
        or any(not isinstance(symbol, str) for symbol in added)
        or not isinstance(removed, list)
        or len(removed) > 2000
        or any(not isinstance(symbol, str) for symbol in removed)
    ):
        return False
    universe_symbols = [item.get("symbol") for item in universe]
    return symbols == universe_symbols


def _project_crypto_universe(data: dict[str, object]) -> dict[str, object]:
    return {field: data[field] for field in _CRYPTO_UNIVERSE_PUBLIC_FIELDS}


def _crypto_universe_as_of(data: dict[str, object]) -> str | None:
    value = data["date"]
    if not isinstance(value, str):
        raise TypeError("validated Crypto Universe date must be a string")
    return value


def _valid_options_flow_feed_source(data: dict[str, object]) -> bool:
    if set(data) != _OPTIONS_FLOW_FEED_SOURCE_FIELDS:
        return False
    note = data.get("note")
    signals = data.get("signals")
    if not isinstance(note, str) or len(note) > 2000:
        return False
    if not isinstance(signals, list) or len(signals) > 200:
        return False
    for signal in signals:
        if not isinstance(signal, dict):
            return False
        if not set(_OPTIONS_FLOW_SIGNAL_FIELDS).issubset(signal):
            return False
        biggest = signal["biggest"]
        if biggest is not None and (
            not isinstance(biggest, dict)
            or not set(_OPTIONS_FLOW_BIGGEST_FIELDS).issubset(biggest)
        ):
            return False
    return True


def _project_options_flow_signal(signal: dict[str, object]) -> dict[str, object]:
    projected = {field: signal[field] for field in _OPTIONS_FLOW_SIGNAL_FIELDS}
    biggest = projected["biggest"]
    if biggest is not None:
        if not isinstance(biggest, dict):
            raise TypeError("validated options-flow biggest must be an object")
        projected["biggest"] = {
            field: biggest[field] for field in _OPTIONS_FLOW_BIGGEST_FIELDS
        }
    return projected


def _project_options_flow_feed(data: dict[str, object]) -> dict[str, object]:
    signals = data["signals"]
    if not isinstance(signals, list):
        raise TypeError("validated options-flow feed must contain an array")
    projected_signals: list[dict[str, object]] = []
    for signal in signals:
        if not isinstance(signal, dict):
            raise TypeError("validated options-flow feed must contain object items")
        projected_signals.append(_project_options_flow_signal(signal))
    projected = {field: data[field] for field in _OPTIONS_FLOW_FEED_PUBLIC_FIELDS}
    projected["signals"] = projected_signals
    return projected


def _valid_market_thesis_source(data: dict[str, object]) -> bool:
    if set(data) != _MARKET_THESIS_SOURCE_FIELDS:
        return False
    rationale = data.get("rationale")
    if not isinstance(rationale, dict) or set(rationale) != _MARKET_THESIS_RATIONALE_SOURCE_FIELDS:
        return False
    analog = rationale.get("analog")
    if analog is not None and not isinstance(analog, dict):
        return False
    missing = rationale.get("manifest_missing")
    stale = rationale.get("manifest_stale")
    events = rationale.get("manifest_events")
    if (
        not isinstance(missing, list)
        or len(missing) > 5
        or not isinstance(stale, list)
        or len(stale) > 5
        or not isinstance(events, list)
        or len(events) > 5
    ):
        return False
    for event in events:
        if (
            not isinstance(event, dict)
            or not _MARKET_THESIS_EVENT_REQUIRED_FIELDS.issubset(event)
            or not set(event).issubset(_MARKET_THESIS_EVENT_SOURCE_FIELDS)
        ):
            return False
    return True


def _project_market_thesis(data: dict[str, object]) -> dict[str, object]:
    rationale = data["rationale"]
    if not isinstance(rationale, dict):
        raise TypeError("validated Market Thesis rationale must be an object")
    analog = rationale["analog"]
    if analog is not None and not isinstance(analog, dict):
        raise TypeError("validated Market Thesis analog must be an object or null")
    events = rationale["manifest_events"]
    if not isinstance(events, list):
        raise TypeError("validated Market Thesis events must be an array")
    projected = {field: data[field] for field in _MARKET_THESIS_PUBLIC_FIELDS}
    projected["rationale"] = {
        "analog": (
            {field: analog.get(field) for field in _MARKET_THESIS_ANALOG_PUBLIC_FIELDS}
            if analog is not None
            else None
        ),
        "manifest_missing": rationale["manifest_missing"],
        "manifest_stale": rationale["manifest_stale"],
        "manifest_events": [
            {field: event.get(field) for field in _MARKET_THESIS_EVENT_PUBLIC_FIELDS}
            for event in events
            if isinstance(event, dict)
        ],
    }
    return projected


def _market_thesis_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of"]
    if not isinstance(value, str):
        raise TypeError("validated Market Thesis as_of must be a string")
    return value


def _bounded_int(value: object, *, minimum: int = 0, maximum: int = 1_000_000) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and minimum <= value <= maximum
    )


def _bounded_finite_number(
    value: object,
    *,
    minimum: float,
    maximum: float,
) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(float(value))
        and minimum <= float(value) <= maximum
    )


def _valid_market_thesis_validation_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _MARKET_THESIS_VALIDATION_SOURCE_FIELDS
        or _payload_generated_at(data) is None
        or data.get("benchmark") != "^GSPC"
        or data.get("buckets") != {"short": 20, "mid": 40, "long": 60}
        or not _bounded_finite_number(
            data.get("theta_dir"), minimum=0, maximum=1
        )
    ):
        return False
    status = data.get("validation_status")
    if (
        not isinstance(status, str)
        or len(status) > 100
        or re.fullmatch(r"(?:ok|non_publishable_[a-z0-9_]+)", status) is None
        or not isinstance(data.get("note"), str)
        or len(data["note"]) > 2_000
    ):
        return False
    counts = {
        field: data.get(field)
        for field in (
            "resolved",
            "matured",
            "reject_count",
            "invalid_count",
            "min_resolved_for_verdict",
        )
    }
    if any(
        not _bounded_int(
            value,
            minimum=1 if field == "min_resolved_for_verdict" else 0,
        )
        for field, value in counts.items()
    ):
        return False
    resolved = counts["resolved"]
    matured = counts["matured"]
    if not isinstance(resolved, int) or not isinstance(matured, int) or matured > resolved:
        return False
    invalid_records = data.get("invalid_records")
    rejected_ledgers = data.get("rejected_ledgers")
    if (
        not isinstance(invalid_records, list)
        or len(invalid_records) > 10_000
        or any(not isinstance(item, dict) for item in invalid_records)
        or not isinstance(rejected_ledgers, list)
        or len(rejected_ledgers) > 10_000
        or any(not isinstance(item, dict) for item in rejected_ledgers)
        or counts["invalid_count"] != len(invalid_records)
        or counts["reject_count"] != len(rejected_ledgers)
        or (status == "ok" and (invalid_records or rejected_ledgers))
    ):
        return False
    by_key = data.get("by_key")
    threshold = counts["min_resolved_for_verdict"]
    if not isinstance(by_key, dict) or len(by_key) > 27 or not isinstance(threshold, int):
        return False
    total_raw = 0
    total_counted = 0
    for key, row in by_key.items():
        match = _MARKET_THESIS_VALIDATION_KEY_RE.fullmatch(key) if isinstance(key, str) else None
        if (
            match is None
            or not isinstance(row, dict)
            or set(row) != _MARKET_THESIS_VALIDATION_ROW_SOURCE_FIELDS
            or row.get("direction") != match.group(1)
            or row.get("bucket") != match.group(2)
            or row.get("support_class") != match.group(3)
        ):
            return False
        raw_n = row.get("raw_N")
        counted_n = row.get("counted_N")
        hits = row.get("hits")
        if (
            not _bounded_int(raw_n, minimum=1)
            or not _bounded_int(counted_n, minimum=1)
            or not _bounded_int(hits)
            or not isinstance(raw_n, int)
            or not isinstance(counted_n, int)
            or not isinstance(hits, int)
            or counted_n > raw_n
            or hits > counted_n
        ):
            return False
        hit_rate = row.get("hit_rate")
        wilson = row.get("wilson90")
        expected_verdict = "MATURE" if counted_n >= threshold else "PROVISIONAL"
        if (
            not _bounded_finite_number(hit_rate, minimum=0, maximum=1)
            or not isclose(
                float(hit_rate),
                hits / counted_n,
                rel_tol=0,
                abs_tol=0.00005,
            )
            or not isinstance(wilson, list)
            or len(wilson) != 2
            or any(
                not _bounded_finite_number(value, minimum=0, maximum=1)
                for value in wilson
            )
            or float(wilson[0]) > float(wilson[1])
            or row.get("verdict") != expected_verdict
        ):
            return False
        total_raw += raw_n
        total_counted += counted_n
    return total_raw == matured and total_counted <= matured


def _project_market_thesis_validation(
    data: dict[str, object],
) -> dict[str, object]:
    by_key = data["by_key"]
    if not isinstance(by_key, dict):
        raise TypeError("validated Market Thesis by_key must be an object")
    return {
        field: data[field]
        for field in (
            "validation_status",
            "resolved",
            "matured",
            "min_resolved_for_verdict",
            "reject_count",
            "invalid_count",
        )
    } | {
        "by_key": {
            key: {
                field: row[field]
                for field in _MARKET_THESIS_VALIDATION_ROW_PUBLIC_FIELDS
            }
            for key, row in by_key.items()
            if isinstance(key, str) and isinstance(row, dict)
        }
    }


def _valid_market_thesis_regime_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _MARKET_THESIS_REGIME_SOURCE_FIELDS
        or _payload_generated_at(data) is None
        or data.get("benchmark") != "^GSPC"
        or data.get("vix") != "^VIX"
        or data.get("forward_windows_sessions") != [20, 40, 60]
        or not isinstance(data.get("lookback_period"), str)
        or not 1 <= len(data["lookback_period"]) <= 20
        or not isinstance(data.get("note"), str)
        or len(data["note"]) > 2_000
        or not isinstance(data.get("rules"), dict)
    ):
        return False
    for field, maximum in (
        ("correction_episodes", 10_000),
        ("regime_runs", 20_000),
        ("daily", 20_000),
    ):
        items = data.get(field)
        if (
            not isinstance(items, list)
            or len(items) > maximum
            or any(not isinstance(item, dict) for item in items)
        ):
            return False
    summary = data.get("regime_summary")
    if not isinstance(summary, dict) or set(summary) != set(_MARKET_THESIS_REGIME_NAMES):
        return False
    for regime_name in _MARKET_THESIS_REGIME_NAMES:
        regime = summary.get(regime_name)
        if not isinstance(regime, dict) or set(regime) != _MARKET_THESIS_REGIME_FIELDS:
            return False
        days = regime.get("days")
        if not _bounded_int(days, minimum=1, maximum=100_000) or not isinstance(days, int):
            return False
        for window_name in _MARKET_THESIS_REGIME_WINDOWS:
            window = regime.get(window_name)
            if (
                not isinstance(window, dict)
                or set(window) != _MARKET_THESIS_REGIME_WINDOW_SOURCE_FIELDS
            ):
                return False
            resolved = window.get("resolved")
            if (
                not _bounded_int(resolved, maximum=days)
                or any(
                    not _bounded_finite_number(
                        window.get(field), minimum=-100, maximum=100
                    )
                    for field in (
                        "mean",
                        "median",
                        "p10",
                        "worst",
                        "mean_mdd",
                        "worst_mdd",
                    )
                )
                or not _bounded_finite_number(
                    window.get("up_rate"), minimum=0, maximum=1
                )
            ):
                return False
            ci90 = window.get("ci90")
            if (
                not isinstance(ci90, list)
                or len(ci90) != 2
                or any(
                    not _bounded_finite_number(value, minimum=-100, maximum=100)
                    for value in ci90
                )
                or float(ci90[0]) > float(ci90[1])
                or float(window["worst"]) > float(window["p10"])
            ):
                return False
    return True


def _project_market_thesis_regime(data: dict[str, object]) -> dict[str, object]:
    summary = data["regime_summary"]
    if not isinstance(summary, dict):
        raise TypeError("validated Market Thesis regime summary must be an object")
    projected: dict[str, object] = {}
    for regime_name in _MARKET_THESIS_REGIME_NAMES:
        regime = summary[regime_name]
        if not isinstance(regime, dict):
            raise TypeError("validated Market Thesis regime must be an object")
        public_regime: dict[str, object] = {"days": regime["days"]}
        for window_name in _MARKET_THESIS_REGIME_WINDOWS:
            window = regime[window_name]
            if not isinstance(window, dict):
                raise TypeError("validated Market Thesis window must be an object")
            public_regime[window_name] = {
                field: window[field]
                for field in _MARKET_THESIS_REGIME_WINDOW_PUBLIC_FIELDS
            }
        projected[regime_name] = public_regime
    return {"regime_summary": projected}


def _valid_reversal_radar_source(data: dict[str, object]) -> bool:
    if set(data) != _REVERSAL_RADAR_SOURCE_FIELDS:
        return False
    candidates = data.get("candidates")
    return (
        isinstance(candidates, list)
        and len(candidates) <= 500
        and all(
            isinstance(candidate, dict) and isinstance(candidate.get("ticker"), str)
            for candidate in candidates
        )
    )


def _project_reversal_radar(data: dict[str, object]) -> dict[str, object]:
    candidates = data["candidates"]
    if not isinstance(candidates, list):
        raise TypeError("validated Reversal candidates must be an array")
    projected = {field: data[field] for field in _REVERSAL_RADAR_PUBLIC_FIELDS}
    projected["candidates"] = [
        {"ticker": candidate["ticker"]}
        for candidate in candidates
        if isinstance(candidate, dict)
    ]
    return projected


def _valid_oversold_reversal_source(data: dict[str, object]) -> bool:
    if set(data) != _OVERSOLD_REVERSAL_SOURCE_FIELDS:
        return False
    validation = data.get("validation")
    caveats = data.get("validation_caveats")
    candidates = data.get("candidates")
    return (
        isinstance(validation, dict)
        and set(_OVERSOLD_VALIDATION_PUBLIC_FIELDS).issubset(validation)
        and isinstance(caveats, list)
        and len(caveats) <= 20
        and all(isinstance(caveat, str) for caveat in caveats)
        and isinstance(candidates, list)
        and len(candidates) <= 2_000
        and all(
            isinstance(candidate, dict)
            and set(_OVERSOLD_CANDIDATE_PUBLIC_FIELDS).issubset(candidate)
            for candidate in candidates
        )
    )


def _project_oversold_reversal(data: dict[str, object]) -> dict[str, object]:
    validation = data["validation"]
    candidates = data["candidates"]
    if not isinstance(validation, dict) or not isinstance(candidates, list):
        raise TypeError("validated Oversold source has invalid nested containers")
    projected = {field: data[field] for field in _OVERSOLD_REVERSAL_PUBLIC_FIELDS}
    projected["validation"] = {
        field: validation[field] for field in _OVERSOLD_VALIDATION_PUBLIC_FIELDS
    }
    projected["candidates"] = [
        {field: candidate[field] for field in _OVERSOLD_CANDIDATE_PUBLIC_FIELDS}
        for candidate in candidates
        if isinstance(candidate, dict)
    ]
    return projected


def _valid_optional_finite(
    value: object,
    *,
    minimum: float = -1_000_000,
    maximum: float = 1_000_000,
) -> bool:
    return value is None or _bounded_finite_number(
        value,
        minimum=minimum,
        maximum=maximum,
    )


def _valid_optional_interval(
    value: object,
    *,
    minimum: float = -1_000_000,
    maximum: float = 1_000_000,
) -> bool:
    return value is None or (
        isinstance(value, list)
        and len(value) == 2
        and all(
            _bounded_finite_number(item, minimum=minimum, maximum=maximum)
            for item in value
        )
        and float(value[0]) <= float(value[1])
    )


def _valid_reversal_finite(value: object, *, minimum: float | None = None) -> bool:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not isfinite(value))
    ):
        return False
    return minimum is None or value >= minimum


def _reversal_numbers_close(left: int | float, right: int | float) -> bool:
    if left == right:
        return True
    if isinstance(left, int) and isinstance(right, int):
        return False
    try:
        return isclose(float(left), float(right), rel_tol=1e-12, abs_tol=0)
    except OverflowError:
        return False


def _valid_reversal_interval(
    value: object,
    *,
    nullable_pair: bool,
) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    if value == [None, None]:
        return nullable_pair
    if not all(_valid_reversal_finite(item) for item in value):
        return False
    return value[0] <= value[1]


def _valid_reversal_validation_tier(row: object) -> bool:
    if (
        not isinstance(row, dict)
        or set(row) != _REVERSAL_VALIDATION_TIER_SOURCE_FIELDS
    ):
        return False
    resolved = row.get("resolved")
    hits = row.get("hits")
    excess_n = row.get("excess_n")
    if (
        not _bounded_int(resolved, maximum=10_000_000)
        or not _bounded_int(hits, maximum=10_000_000)
        or not _bounded_int(excess_n, maximum=10_000_000)
        or not isinstance(resolved, int)
        or not isinstance(hits, int)
        or not isinstance(excess_n, int)
        or hits > resolved
        or excess_n > resolved
    ):
        return False
    hit_rate = row.get("hit_rate")
    if resolved == 0:
        if hit_rate is not None:
            return False
    elif (
        not _bounded_finite_number(hit_rate, minimum=0, maximum=1)
        or not isclose(
            float(hit_rate),
            hits / resolved,
            rel_tol=0,
            abs_tol=0.00005,
        )
    ):
        return False
    wilson = row.get("wilson90")
    if (
        not isinstance(wilson, list)
        or len(wilson) != 2
        or any(
            not _bounded_finite_number(item, minimum=0, maximum=1)
            for item in wilson
        )
        or float(wilson[0]) > float(wilson[1])
        or (resolved == 0 and wilson != [0.0, 1.0])
    ):
        return False

    main_fields = ("ev_horizon", "median_horizon", "equity_multiple")
    main_rate = row.get("win_rate_horizon")
    main_interval = row.get("ev_horizon_ci90")
    curve = row.get("equity_curve")
    if resolved == 0:
        if (
            any(row.get(field) is not None for field in main_fields)
            or main_rate is not None
            or main_interval != [None, None]
            or not isinstance(curve, list)
            or curve
        ):
            return False
    else:
        if (
            not _valid_reversal_finite(row.get("ev_horizon"))
            or not _valid_reversal_finite(row.get("median_horizon"))
            or not _bounded_finite_number(main_rate, minimum=0, maximum=1)
            or not _valid_reversal_interval(main_interval, nullable_pair=False)
            or not _valid_reversal_finite(
                row.get("equity_multiple"), minimum=0
            )
            or not isinstance(curve, list)
            or len(curve) != resolved
            or len(curve) > 10_000_000
        ):
            return False
        previous_date: str | None = None
        for point in curve:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not _is_iso_date(point[0])
                or not _valid_reversal_finite(point[1], minimum=0)
                or (previous_date is not None and point[0] < previous_date)
            ):
                return False
            previous_date = point[0]
        if not _reversal_numbers_close(
            curve[-1][1],
            row["equity_multiple"],
        ):
            return False

    excess_value = row.get("ev_excess_vs_spy")
    excess_rate = row.get("excess_win_rate")
    excess_interval = row.get("ev_excess_ci90")
    if excess_n == 0:
        return (
            excess_value is None
            and excess_rate is None
            and excess_interval == [None, None]
        )
    return (
        _valid_reversal_finite(excess_value)
        and _bounded_finite_number(excess_rate, minimum=0, maximum=1)
        and _valid_reversal_interval(excess_interval, nullable_pair=False)
    )


def _valid_reversal_validation_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _REVERSAL_VALIDATION_SOURCE_FIELDS
        or _payload_generated_at(data) is None
        or data.get("module") != "reversal_radar"
        or data.get("lane_id")
        != (
            "reversal_radar.v1.structure+momentum_div+options_fear_receding+"
            "sector_improving+insider+analyst"
        )
    ):
        return False
    entries = data.get("entries_accumulated")
    resolvable = data.get("price_resolvable")
    dropped = data.get("dropped_count")
    minimum = data.get("min_resolved_across_tiers")
    threshold = data.get("min_resolved_for_verdict")
    if (
        not _bounded_int(entries, maximum=10_000_000)
        or not _bounded_int(resolvable, maximum=10_000_000)
        or not _bounded_int(dropped, maximum=10_000_000)
        or not _bounded_int(minimum, maximum=10_000_000)
        or not _bounded_int(threshold, minimum=1, maximum=10_000_000)
        or not isinstance(entries, int)
        or not isinstance(resolvable, int)
        or not isinstance(dropped, int)
        or not isinstance(minimum, int)
        or not isinstance(threshold, int)
        or resolvable > entries
        or dropped != entries - resolvable
    ):
        return False
    dropped_pct = data.get("dropped_pct")
    if entries == 0:
        if dropped_pct is not None:
            return False
    elif (
        not _bounded_finite_number(dropped_pct, minimum=0, maximum=1)
        or not isclose(
            float(dropped_pct),
            round(dropped / entries, 4),
            rel_tol=0,
            abs_tol=0.00005,
        )
    ):
        return False

    by_tier = data.get("by_tier")
    if (
        not isinstance(by_tier, dict)
        or tuple(by_tier) != _REVERSAL_VALIDATION_TIERS
        or any(
            not _valid_reversal_validation_tier(by_tier[tier])
            for tier in _REVERSAL_VALIDATION_TIERS
        )
    ):
        return False
    tier_minimum = min(
        int(by_tier[tier]["resolved"])
        for tier in _REVERSAL_VALIDATION_TIERS
    )
    if any(
        int(by_tier[tier]["resolved"]) > resolvable
        for tier in _REVERSAL_VALIDATION_TIERS
    ):
        return False
    expected_verdict = (
        "MATURE" if tier_minimum >= threshold else _REVERSAL_VALIDATION_PROVISIONAL
    )
    verdict_by_tier = data.get("verdict_by_tier")
    if (
        minimum != tier_minimum
        or data.get("verdict") != expected_verdict
        or not isinstance(verdict_by_tier, dict)
        or tuple(verdict_by_tier) != _REVERSAL_VALIDATION_TIERS
        or any(
            verdict_by_tier[tier]
            != (
                "MATURE"
                if int(by_tier[tier]["resolved"]) >= threshold
                else "PROVISIONAL"
            )
            for tier in _REVERSAL_VALIDATION_TIERS
        )
    ):
        return False
    survivorship = data.get("survivorship")
    if (
        not isinstance(survivorship, dict)
        or set(survivorship) != _REVERSAL_VALIDATION_SURVIVORSHIP_FIELDS
        or type(survivorship.get("survivorship_free")) is not bool
        or not isinstance(survivorship.get("forward_universe"), str)
        or not 1 <= len(survivorship["forward_universe"]) <= 2_000
        or not isinstance(survivorship.get("caveats"), list)
        or len(survivorship["caveats"]) > 20
        or any(
            not isinstance(item, str) or len(item) > 2_000
            for item in survivorship["caveats"]
        )
    ):
        return False
    ev_caveats = data.get("ev_caveats")
    return (
        isinstance(ev_caveats, list)
        and len(ev_caveats) <= 20
        and all(isinstance(item, str) and len(item) <= 2_000 for item in ev_caveats)
        and isinstance(data.get("note"), str)
        and len(data["note"]) <= 4_000
    )


def _project_reversal_validation(data: dict[str, object]) -> dict[str, object]:
    by_tier = data["by_tier"]
    if not isinstance(by_tier, dict):
        raise TypeError("validated Reversal validation tiers must be an object")
    return {
        field: data[field]
        for field in (
            "entries_accumulated",
            "min_resolved_across_tiers",
            "min_resolved_for_verdict",
            "verdict",
        )
    } | {
        "by_tier": {
            tier: {
                field: by_tier[tier][field]
                for field in _REVERSAL_VALIDATION_TIER_PUBLIC_FIELDS
            }
            for tier in _REVERSAL_VALIDATION_TIERS
        }
    }


def _reversal_validation_generated_at(data: dict[str, object]) -> str | None:
    value = data["generated_at"]
    if not isinstance(value, str):
        raise TypeError("validated Reversal generated_at must be a string")
    return value


def _valid_oversold_validation_tier(
    row: object,
    *,
    threshold: int,
) -> bool:
    if not isinstance(row, dict) or set(row) != _OVERSOLD_VALIDATION_TIER_SOURCE_FIELDS:
        return False
    resolved = row.get("resolved")
    hits = row.get("hits")
    excess_n = row.get("excess_n")
    excess_beta_adj_n = row.get("excess_beta_adj_n")
    if (
        not _bounded_int(resolved, maximum=10_000_000)
        or not _bounded_int(hits, maximum=10_000_000)
        or not _bounded_int(excess_n, maximum=10_000_000)
        or not _bounded_int(excess_beta_adj_n, maximum=10_000_000)
        or not isinstance(resolved, int)
        or not isinstance(hits, int)
        or not isinstance(excess_n, int)
        or not isinstance(excess_beta_adj_n, int)
        or hits > resolved
        or excess_n > resolved
        or excess_beta_adj_n > resolved
    ):
        return False
    hit_rate = row.get("hit_rate")
    if resolved == 0:
        if hit_rate is not None:
            return False
    elif (
        not _bounded_finite_number(hit_rate, minimum=0, maximum=1)
        or not isclose(
            float(hit_rate),
            hits / resolved,
            rel_tol=0,
            abs_tol=0.00005,
        )
    ):
        return False
    wilson = row.get("wilson90")
    if (
        not isinstance(wilson, list)
        or len(wilson) != 2
        or any(
            not _bounded_finite_number(item, minimum=0, maximum=1)
            for item in wilson
        )
        or float(wilson[0]) > float(wilson[1])
        or (resolved == 0 and wilson != [0.0, 1.0])
    ):
        return False
    if (
        row.get("mature") is not (resolved >= threshold)
        or row.get("excess_mature") is not (excess_n >= threshold)
        or row.get("excess_beta_adj_mature")
        is not (excess_beta_adj_n >= threshold)
    ):
        return False
    bounded_main_fields = (
        "ev_horizon",
        "median_horizon",
        "ev_horizon_net",
    )
    equity_fields = (
        "equity_multiple",
        "equity_multiple_net",
    )
    main_fields = (*bounded_main_fields, *equity_fields)
    main_rate_fields = ("win_rate_horizon", "win_rate_net")
    main_interval_fields = ("ev_horizon_ci90", "ev_horizon_net_ci90")
    for field in bounded_main_fields:
        if not _valid_optional_finite(row.get(field)):
            return False
    for field in equity_fields:
        value = row.get(field)
        if value is not None and not _valid_reversal_finite(value, minimum=0):
            return False
    for field in main_rate_fields:
        if not _valid_optional_finite(row.get(field), minimum=0, maximum=1):
            return False
    for field in main_interval_fields:
        if not _valid_optional_interval(row.get(field)):
            return False
    if resolved >= threshold:
        if any(row.get(field) is None for field in (*main_fields, *main_rate_fields)):
            return False
        if any(row.get(field) is None for field in main_interval_fields):
            return False
    elif any(
        row.get(field) is not None
        for field in (*main_fields, *main_rate_fields, *main_interval_fields)
    ):
        return False
    for count, value_field, rate_field, interval_field in (
        (
            excess_n,
            "ev_excess_vs_spy",
            "excess_win_rate",
            "ev_excess_ci90",
        ),
        (
            excess_beta_adj_n,
            "ev_excess_beta_adj",
            "excess_beta_adj_win_rate",
            "ev_excess_beta_adj_ci90",
        ),
    ):
        if (
            not _valid_optional_finite(row.get(value_field))
            or not _valid_optional_finite(
                row.get(rate_field), minimum=0, maximum=1
            )
            or not _valid_optional_interval(row.get(interval_field))
        ):
            return False
        published = count >= threshold
        fields = (value_field, rate_field, interval_field)
        if published:
            if any(row.get(field) is None for field in fields):
                return False
        elif any(row.get(field) is not None for field in fields):
            return False
    curve = row.get("equity_curve")
    if not (
        isinstance(curve, list)
        and len(curve) == (resolved if resolved >= threshold else 0)
        and len(curve) <= 10_000_000
        and all(
            isinstance(point, list)
            and len(point) == 2
            and _is_iso_date(point[0])
            and _valid_reversal_finite(point[1], minimum=0)
            for point in curve
        )
    ):
        return False
    return resolved < threshold or _reversal_numbers_close(
        curve[-1][1],
        row["equity_multiple"],
    )


def _valid_oversold_validation_tiers(
    value: object,
    *,
    threshold: int,
) -> bool:
    return (
        isinstance(value, dict)
        and tuple(value) == _OVERSOLD_VALIDATION_TIERS
        and all(
            _valid_oversold_validation_tier(value[tier], threshold=threshold)
            for tier in _OVERSOLD_VALIDATION_TIERS
        )
    )


def _valid_oversold_validation_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _OVERSOLD_VALIDATION_SOURCE_FIELDS
        or _payload_generated_at(data) is None
        or data.get("module") != "coiled_base"
        or data.get("lane_id")
        != "coiled_base.v1.bb_squeeze+rsi_40_65+above_30pct_of_low"
    ):
        return False
    entries = data.get("entries_accumulated")
    resolvable = data.get("price_resolvable")
    dropped = data.get("dropped_count")
    minimum = data.get("min_resolved_across_tiers")
    threshold = data.get("min_resolved_for_verdict")
    if (
        not _bounded_int(entries, maximum=10_000_000)
        or not _bounded_int(resolvable, maximum=10_000_000)
        or not _bounded_int(dropped, maximum=10_000_000)
        or not _bounded_int(minimum, maximum=10_000_000)
        or not _bounded_int(threshold, minimum=1, maximum=10_000_000)
        or not isinstance(entries, int)
        or not isinstance(resolvable, int)
        or not isinstance(dropped, int)
        or not isinstance(minimum, int)
        or not isinstance(threshold, int)
        or resolvable > entries
        or dropped != entries - resolvable
    ):
        return False
    dropped_pct = data.get("dropped_pct")
    if entries == 0:
        dropped_pct_valid = dropped_pct is None
    else:
        dropped_pct_valid = (
            _bounded_finite_number(dropped_pct, minimum=0, maximum=1)
            and isclose(
                float(dropped_pct),
                round(dropped / entries, 4),
                rel_tol=0,
                abs_tol=0.00005,
            )
        )
    if (
        not dropped_pct_valid
        or not _bounded_finite_number(
            data.get("cost_assumption_round_trip"), minimum=0, maximum=1
        )
    ):
        return False
    by_tier = data.get("by_tier")
    if not _valid_oversold_validation_tiers(by_tier, threshold=threshold):
        return False
    if not isinstance(by_tier, dict):
        return False
    tier_minimum = min(
        int(by_tier[tier]["resolved"])
        for tier in _OVERSOLD_VALIDATION_TIERS
    )
    expected_verdict = (
        "MATURE" if tier_minimum >= threshold else _OVERSOLD_VALIDATION_PROVISIONAL
    )
    verdict_by_tier = data.get("verdict_by_tier")
    if (
        minimum != tier_minimum
        or data.get("verdict") != expected_verdict
        or not isinstance(verdict_by_tier, dict)
        or tuple(verdict_by_tier) != _OVERSOLD_VALIDATION_TIERS
        or any(
            verdict_by_tier[tier]
            != (
                "MATURE"
                if by_tier[tier]["resolved"] >= threshold
                else "PROVISIONAL"
            )
            for tier in _OVERSOLD_VALIDATION_TIERS
        )
    ):
        return False
    survivorship = data.get("survivorship")
    if (
        not isinstance(survivorship, dict)
        or set(survivorship) != _OVERSOLD_VALIDATION_SURVIVORSHIP_FIELDS
        or type(survivorship.get("survivorship_free")) is not bool
        or type(survivorship.get("universe_match")) is not bool
        or any(
            not isinstance(survivorship.get(field), str)
            or not 1 <= len(survivorship[field]) <= 2_000
            for field in ("forward_universe", "validated_universe")
        )
        or not isinstance(survivorship.get("caveats"), list)
        or len(survivorship["caveats"]) > 20
        or any(
            not isinstance(item, str) or len(item) > 2_000
            for item in survivorship["caveats"]
        )
    ):
        return False
    cohort = data.get("sp500_pit_cohort")
    if not isinstance(cohort, dict) or set(cohort) != _OVERSOLD_VALIDATION_SP500_FIELDS:
        return False
    membership = cohort.get("membership")
    if (
        cohort.get("validated_universe") != "sp500_pit"
        or type(cohort.get("universe_match")) is not bool
        or not isinstance(cohort.get("gate"), str)
        or not 1 <= len(cohort["gate"]) <= 2_000
        or not _is_iso_date(cohort.get("membership_snapshot_through"))
        or not isinstance(membership, dict)
        or set(membership) != _OVERSOLD_VALIDATION_MEMBERSHIP_FIELDS
        or any(
            not _bounded_int(membership.get(field), maximum=10_000_000)
            for field in _OVERSOLD_VALIDATION_MEMBERSHIP_FIELDS
        )
        or sum(
            int(membership[field])
            for field in _OVERSOLD_VALIDATION_MEMBERSHIP_FIELDS
        )
        != resolvable
        or not _valid_oversold_validation_tiers(
            cohort.get("by_tier"), threshold=threshold
        )
    ):
        return False
    ev_caveats = data.get("ev_caveats")
    return (
        isinstance(ev_caveats, list)
        and len(ev_caveats) <= 20
        and all(isinstance(item, str) and len(item) <= 2_000 for item in ev_caveats)
        and isinstance(data.get("note"), str)
        and len(data["note"]) <= 4_000
    )


def _project_oversold_validation(data: dict[str, object]) -> dict[str, object]:
    by_tier = data["by_tier"]
    if not isinstance(by_tier, dict):
        raise TypeError("validated Oversold validation tiers must be an object")
    return {
        field: data[field]
        for field in (
            "entries_accumulated",
            "min_resolved_across_tiers",
            "min_resolved_for_verdict",
            "verdict",
        )
    } | {
        "by_tier": {
            tier: {
                field: by_tier[tier][field]
                for field in _OVERSOLD_VALIDATION_TIER_PUBLIC_FIELDS
            }
            for tier in _OVERSOLD_VALIDATION_TIERS
        }
    }


def _oversold_validation_generated_at(data: dict[str, object]) -> str | None:
    value = data["generated_at"]
    if not isinstance(value, str):
        raise TypeError("validated Oversold generated_at must be a string")
    return value


def _valid_social_intelligence_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _SOCIAL_INTELLIGENCE_SOURCE_FIELDS
        or data.get("source") != "social_intelligence"
        or data.get("schema_version") != 1
        or data.get("market") not in {"US", "CRYPTO"}
    ):
        return False
    statuses = data.get("source_statuses")
    tickers = data.get("tickers")
    limitations = data.get("limitations")
    if (
        not isinstance(statuses, dict)
        or set(statuses) != _SOCIAL_SOURCE_STATUS_KEYS
        or any(
            not isinstance(status, dict)
            or set(status) != _SOCIAL_SOURCE_STATUS_FIELDS
            or any(not isinstance(status.get(field), str) for field in status)
            for status in statuses.values()
        )
        or not isinstance(tickers, list)
        or len(tickers) > 200
        or not isinstance(limitations, list)
        or len(limitations) > 20
        or any(not isinstance(item, str) for item in limitations)
    ):
        return False
    seen: set[object] = set()
    for row in tickers:
        if not isinstance(row, dict) or set(row) != _SOCIAL_TICKER_SOURCE_FIELDS:
            return False
        validation = row.get("platform_validation")
        labels = row.get("labels")
        if (
            not isinstance(validation, dict)
            or set(validation) != set(_SOCIAL_PLATFORM_VALIDATION_FIELDS)
            or not isinstance(labels, dict)
            or set(labels) != set(_SOCIAL_LABEL_FIELDS)
            or any(type(labels[field]) is not bool for field in _SOCIAL_LABEL_FIELDS)
            or not isinstance(row.get("heat_baseline"), dict)
            or any(
                not isinstance(row.get(field), list)
                for field in (
                    "mentioned_by",
                    "citations",
                    "discovery_sources",
                    "cost_modes",
                )
            )
        ):
            return False
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or ticker in seen:
            return False
        seen.add(ticker)
    return True


def _project_social_intelligence(data: dict[str, object]) -> dict[str, object]:
    statuses = data["source_statuses"]
    tickers = data["tickers"]
    if not isinstance(statuses, dict) or not isinstance(tickers, list):
        raise TypeError("validated social source has invalid nested containers")
    agent = statuses["agent_reach"]
    if not isinstance(agent, dict):
        raise TypeError("validated Agent Reach status must be an object")
    projected_rows: list[dict[str, object]] = []
    for row in tickers:
        if not isinstance(row, dict):
            raise TypeError("validated social tickers must contain objects")
        validation = row["platform_validation"]
        labels = row["labels"]
        if not isinstance(validation, dict) or not isinstance(labels, dict):
            raise TypeError("validated social ticker details must be objects")
        projected = {field: row[field] for field in _SOCIAL_TICKER_PUBLIC_FIELDS}
        projected["platform_validation"] = {
            field: validation[field]
            for field in _SOCIAL_PLATFORM_VALIDATION_FIELDS
        }
        projected["labels"] = {field: labels[field] for field in _SOCIAL_LABEL_FIELDS}
        projected_rows.append(projected)
    return {
        "as_of_date": data["as_of_date"],
        "generated_at": data["generated_at"],
        "market": data["market"],
        "source_statuses": {
            "agent_reach": {
                "status": agent["status"],
                "note": agent["note"],
            }
        },
        "tickers": projected_rows,
    }


def _social_intelligence_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of_date"]
    if not isinstance(value, str):
        raise TypeError("validated social as_of_date must be a string")
    return value


def _valid_theme_flow_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _THEME_FLOW_SOURCE_FIELDS
        or data.get("schema_version") != THEME_FLOW_SCHEMA_VERSION
    ):
        return False
    themes = data.get("themes")
    buckets = data.get("buckets")
    shared = data.get("shared_mega_caps")
    if (
        not isinstance(data.get("params"), dict)
        or not isinstance(data.get("bottom_fishing"), list)
        or not isinstance(themes, list)
        or not 1 <= len(themes) <= 100
        or not isinstance(buckets, dict)
        or not isinstance(shared, list)
        or len(shared) > 100
    ):
        return False
    for row in themes:
        if not isinstance(row, dict) or set(row) != _THEME_FLOW_THEME_SOURCE_FIELDS:
            return False
        reps = row.get("reps")
        if (
            not isinstance(reps, list)
            or len(reps) > 10
            or any(
                not isinstance(rep, dict)
                or set(rep) != set(_THEME_FLOW_REP_FIELDS)
                for rep in reps
            )
        ):
            return False
    return all(
        isinstance(item, dict)
        and set(item) == set(_THEME_FLOW_SHARED_CAP_FIELDS)
        for item in shared
    )


def _theme_flow_board_fingerprint(
    as_of: object,
    themes: object,
) -> str:
    def rounded(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return round(value, 6)

    rows = sorted(
        (
            str(theme.get("theme")),
            rounded(theme.get("flow_5d_norm")),
            rounded(theme.get("heat_score")),
        )
        for theme in themes if isinstance(theme, dict)
    ) if isinstance(themes, list) else []
    blob = json.dumps({"as_of": str(as_of), "rows": rows}, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _project_theme_flow(data: dict[str, object]) -> dict[str, object]:
    themes = data["themes"]
    shared = data["shared_mega_caps"]
    if not isinstance(themes, list) or not isinstance(shared, list):
        raise TypeError("validated Theme Flow source has invalid arrays")
    projected_themes: list[dict[str, object]] = []
    for row in themes:
        if not isinstance(row, dict):
            raise TypeError("validated Theme Flow themes must contain objects")
        reps = row["reps"]
        if not isinstance(reps, list):
            raise TypeError("validated Theme Flow representatives must be an array")
        projected = {field: row[field] for field in _THEME_FLOW_THEME_PUBLIC_FIELDS}
        projected["reps"] = [
            {field: rep[field] for field in _THEME_FLOW_REP_FIELDS}
            for rep in reps if isinstance(rep, dict)
        ]
        projected_themes.append(projected)
    projected_shared = [
        {field: item[field] for field in _THEME_FLOW_SHARED_CAP_FIELDS}
        for item in shared if isinstance(item, dict)
    ]
    return {
        "as_of": data["as_of"],
        "generated_at": data["generated_at"],
        "benchmark": data["benchmark"],
        "n_failed_download": data["n_failed_download"],
        "buckets": data["buckets"],
        "shared_mega_caps": projected_shared,
        "themes": projected_themes,
        "board_fingerprint": _theme_flow_board_fingerprint(
            data["as_of"], projected_themes
        ),
    }


def _theme_flow_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of"]
    if not isinstance(value, str):
        raise TypeError("validated Theme Flow as_of must be a string")
    return value


def _finite_number_or_none(value: object) -> bool:
    return value is None or (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
    )


def _valid_money_flow_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _MONEY_FLOW_SOURCE_FIELDS
        or data.get("source") != "eastmoney_push2his"
    ):
        return False
    coverage = data.get("coverage")
    rows = data.get("rows")
    if (
        not isinstance(coverage, dict)
        or set(coverage) != _MONEY_FLOW_COVERAGE_FIELDS
        or not isinstance(rows, list)
        or len(rows) > 50_000
    ):
        return False
    private_numeric_fields = (
        "close",
        "change_pct",
        "super_big_net",
        "big_net",
        "mid_net",
    )
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != _MONEY_FLOW_ROW_SOURCE_FIELDS
            or row.get("source") != "eastmoney_push2his"
            or not isinstance(row.get("secid"), str)
            or not row.get("secid")
            or not isinstance(row.get("raw_row"), dict)
            or any(not _finite_number_or_none(row.get(field)) for field in private_numeric_fields)
        ):
            return False
    try:
        MoneyFlowData.model_validate(_project_money_flow(data), strict=True)
    except (KeyError, TypeError, ValueError, ValidationError):
        return False
    return True


def _project_money_flow(data: dict[str, object]) -> dict[str, object]:
    rows = data["rows"]
    if not isinstance(rows, list):
        raise TypeError("validated Money Flow rows must be an array")
    projected = {
        field: data[field]
        for field in (
            "as_of_date",
            "generated_at",
            "source",
            "publishable",
            "coverage",
        )
    }
    projected["rows"] = [
        {field: row[field] for field in _MONEY_FLOW_ROW_PUBLIC_FIELDS}
        for row in rows
        if isinstance(row, dict)
    ]
    return projected


def _valid_sector_rotation_read(read: object) -> bool:
    if not isinstance(read, dict) or set(read) != _SECTOR_ROTATION_READ_FIELDS:
        return False
    for field in (
        "headline",
        "confidence",
        "next_rotation_thesis",
        "cycle_read",
    ):
        value = read.get(field)
        if not isinstance(value, str) or len(value) > 10_000:
            return False
    caveats = read.get("caveats")
    if (
        not isinstance(caveats, list)
        or len(caveats) > 100
        or any(not isinstance(item, str) or len(item) > 10_000 for item in caveats)
    ):
        return False
    for field in ("hot_now", "rotating_into"):
        items = read.get(field)
        if not isinstance(items, list) or len(items) > 100:
            return False
        for item in items:
            if not isinstance(item, dict) or set(item) != _SECTOR_ROTATION_READ_ITEM_FIELDS:
                return False
            if any(
                not isinstance(item.get(key), str) or len(item[key]) > 10_000
                for key in _SECTOR_ROTATION_READ_ITEM_FIELDS
            ):
                return False
    return True


def _valid_sector_rotation_source(data: dict[str, object]) -> bool:
    status = data.get("status")
    expected_fields = _SECTOR_ROTATION_BASE_SOURCE_FIELDS
    if status == "ready":
        expected_fields = expected_fields | {"read"}
    elif status != "verified_only":
        return False
    if set(data) != expected_fields:
        return False
    if status == "ready" and not _valid_sector_rotation_read(data.get("read")):
        return False
    if (
        data.get("benchmark") != "SPY"
        or not _is_iso_date(data.get("as_of"))
        or _payload_generated_at(data) is None
    ):
        return False

    macro = data.get("macro")
    if not isinstance(macro, dict) or set(macro) not in (
        frozenset(),
        _SECTOR_ROTATION_MACRO_FIELDS,
    ):
        return False
    if macro:
        if any(
            macro.get(field) not in {"above", "below", None}
            for field in ("spy_vs_50dma", "spy_vs_200dma")
        ):
            return False
        for field in ("spy_price", "vix_level"):
            value = macro.get(field)
            if value is not None and not _bounded_finite_number(
                value,
                minimum=0,
                maximum=10_000_000,
            ):
                return False

    rows = data.get("sectors")
    if not isinstance(rows, list) or not (1 <= len(rows) <= 100):
        return False
    if any(
        not isinstance(row, dict) or set(row) != _SECTOR_ROTATION_SOURCE_ROW_FIELDS
        for row in rows
    ):
        return False
    try:
        public = SectorRotationData.model_validate(
            _project_sector_rotation(data),
            strict=True,
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        return False

    leaders = data.get("leaders")
    improving = data.get("improving")
    if not isinstance(leaders, list) or not isinstance(improving, list):
        return False
    expected_leaders = [
        sector.etf for sector in public.sectors if sector.quadrant == "Leading"
    ]
    expected_improving = [
        sector.etf for sector in public.sectors if sector.quadrant == "Improving"
    ]
    return leaders == expected_leaders and improving == expected_improving


def _project_sector_rotation(data: dict[str, object]) -> dict[str, object]:
    rows = data["sectors"]
    if not isinstance(rows, list):
        raise TypeError("validated Sector Rotation sectors must be an array")
    return {
        "as_of": data["as_of"],
        "benchmark": data["benchmark"],
        "sectors": [
            {field: row[field] for field in _SECTOR_ROTATION_ROW_PUBLIC_FIELDS}
            for row in rows
            if isinstance(row, dict)
        ],
    }


def _sector_rotation_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of"]
    if not isinstance(value, str):
        raise TypeError("validated Sector Rotation as_of must be a string")
    return value


def _sector_rotation_generated_at(data: dict[str, object]) -> str | None:
    value = data["generated_at"]
    if not isinstance(value, str):
        raise TypeError("validated Sector Rotation generated_at must be a string")
    return value


def _money_flow_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of_date"]
    if not isinstance(value, str):
        raise TypeError("validated Money Flow as_of_date must be a string")
    return value


def _valid_theme_flow_analysis_source(data: dict[str, object]) -> bool:
    if (
        set(data) != _THEME_FLOW_ANALYSIS_SOURCE_FIELDS
        or data.get("status") != "ready"
        or data.get("validation_version") != THEME_FLOW_ANALYSIS_VALIDATION_VERSION
    ):
        return False
    read = data.get("read")
    if not isinstance(read, dict) or set(read) != set(_THEME_FLOW_READ_FIELDS):
        return False
    caveats = read.get("caveats")
    if (
        not isinstance(caveats, list)
        or len(caveats) > 20
        or any(not isinstance(item, str) for item in caveats)
    ):
        return False
    for field in _THEME_FLOW_READ_LIST_FIELDS:
        items = read.get(field)
        if (
            not isinstance(items, list)
            or len(items) > 20
            or any(
                not isinstance(item, dict)
                or set(item) != set(_THEME_FLOW_READ_ITEM_FIELDS)
                for item in items
            )
        ):
            return False
    return True


def _project_theme_flow_analysis(data: dict[str, object]) -> dict[str, object]:
    read = data["read"]
    if not isinstance(read, dict):
        raise TypeError("validated Theme Flow analysis read must be an object")
    projected_read = {field: read[field] for field in _THEME_FLOW_READ_FIELDS}
    for field in _THEME_FLOW_READ_LIST_FIELDS:
        items = read[field]
        if not isinstance(items, list):
            raise TypeError("validated Theme Flow read items must be arrays")
        projected_read[field] = [
            {key: item[key] for key in _THEME_FLOW_READ_ITEM_FIELDS}
            for item in items if isinstance(item, dict)
        ]
    return {
        "status": data["status"],
        "as_of": data["as_of"],
        "generated_at": data["generated_at"],
        "board_fingerprint": data["board_fingerprint"],
        "read": projected_read,
    }


def _signal_snapshot_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of_date"]
    if not isinstance(value, str):
        raise TypeError("validated signal snapshot as_of_date must be a string")
    return value


def _daily_summary_text(
    value: object,
    *,
    max_length: int,
    allow_empty: bool,
) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= max_length
        and (allow_empty or bool(value))
        and (not value or value == value.strip())
    )


def _daily_summary_number(
    value: object,
    *,
    minimum: float,
    maximum: float,
) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and minimum <= value <= maximum
    )


def _valid_daily_summary_source(data: dict[str, object]) -> bool:
    allowed_roots = (
        _DAILY_SUMMARY_BASE_FIELDS,
        _DAILY_SUMMARY_BASE_FIELDS | {"watchlist_picks"},
    )
    if frozenset(data) not in allowed_roots:
        return False
    ranked = data.get("ranked_picks")
    total = data.get("total_confirmed")
    if (
        not _is_iso_date(data.get("report_date"))
        or not _daily_summary_text(
            data.get("regime_summary"), max_length=1_000, allow_empty=False
        )
        or isinstance(total, bool)
        or not isinstance(total, int)
        or not 0 <= total <= 100
        or not isinstance(ranked, list)
        or len(ranked) > 100
        or total != len(ranked)
        or not _daily_summary_text(
            data.get("cross_candidate_commentary"),
            max_length=10_000,
            allow_empty=True,
        )
        or not _daily_summary_text(
            data.get("portfolio_notes"), max_length=10_000, allow_empty=True
        )
    ):
        return False

    tickers: list[str] = []
    for expected_rank, row in enumerate(ranked, start=1):
        if not isinstance(row, dict) or frozenset(row) != _DAILY_SUMMARY_RANKED_FIELDS:
            return False
        ticker = row.get("ticker")
        if (
            isinstance(row.get("rank"), bool)
            or row.get("rank") != expected_rank
            or not isinstance(ticker, str)
            or normalize_ticker(ticker) != ticker
            or row.get("verdict") not in {"STRONG_BUY", "BUY", "WATCHLIST"}
            or not _daily_summary_number(
                row.get("final_score"), minimum=0, maximum=100
            )
            or not _daily_summary_number(
                row.get("position_size_pct"), minimum=0, maximum=100
            )
            or any(
                not _daily_summary_text(
                    row.get(field), max_length=limit, allow_empty=True
                )
                for field, limit in (
                    ("thesis", 4_000),
                    ("entry_zone", 500),
                    ("stop_loss", 500),
                    ("key_risk", 2_000),
                )
            )
        ):
            return False
        tickers.append(ticker)
    if len(tickers) != len(set(tickers)):
        return False

    watchlist = data.get("watchlist_picks", [])
    if not isinstance(watchlist, list) or len(watchlist) > 100:
        return False
    watchlist_tickers: list[str] = []
    for row in watchlist:
        if not isinstance(row, dict) or frozenset(row) != _DAILY_SUMMARY_WATCHLIST_FIELDS:
            return False
        ticker = row.get("ticker")
        if (
            not isinstance(ticker, str)
            or normalize_ticker(ticker) != ticker
            or row.get("verdict") != "WATCHLIST"
            or not _daily_summary_number(
                row.get("score"), minimum=0, maximum=100
            )
            or not _daily_summary_text(
                row.get("note"), max_length=4_000, allow_empty=True
            )
        ):
            return False
        watchlist_tickers.append(ticker)
    if len(watchlist_tickers) != len(set(watchlist_tickers)):
        return False

    try:
        DailySummaryData.model_validate(_project_daily_summary(data), strict=True)
    except (KeyError, TypeError, ValueError, ValidationError):
        return False
    return True


def _project_daily_summary(data: dict[str, object]) -> dict[str, object]:
    rows = data["ranked_picks"]
    if not isinstance(rows, list):
        raise TypeError("validated Daily Summary ranked_picks must be an array")
    return {
        "as_of_date": data["report_date"],
        "regime_summary": data["regime_summary"],
        "candidates": [
            {"ticker": row["ticker"], "verdict": row["verdict"]}
            for row in rows
            if isinstance(row, dict)
        ],
    }


def _daily_summary_as_of(data: dict[str, object]) -> str | None:
    value = data["as_of_date"]
    if not isinstance(value, str):
        raise TypeError("validated Daily Summary as_of_date must be a string")
    return value


def _valid_playbook_validation_row(
    row: object,
    *,
    label_field: Literal["playbook", "factor_id"],
    expected_fields: frozenset[str],
    min_resolved: int,
    total_resolved: int,
) -> bool:
    if not isinstance(row, dict) or frozenset(row) != expected_fields:
        return False
    label = row.get(label_field)
    resolved = row.get("resolved")
    if (
        not _daily_summary_text(label, max_length=200, allow_empty=False)
        or not _bounded_int(resolved)
        or not isinstance(resolved, int)
        or resolved > total_resolved
    ):
        return False
    mean_return = row.get("mean_fwd_7d_return")
    hit_rate = row.get("hit_rate_7d")
    if resolved == 0:
        if mean_return is not None or hit_rate is not None:
            return False
    elif (
        not _bounded_finite_number(
            mean_return,
            minimum=-1,
            maximum=1_000_000_000_000_000_000,
        )
        or not _bounded_finite_number(hit_rate, minimum=0, maximum=1)
    ):
        return False
    expected_verdict = "validated" if resolved >= min_resolved else "exploratory"
    return row.get("verdict") == expected_verdict


def _valid_playbook_validation_source(data: dict[str, object]) -> bool:
    status = data.get("status")
    if _payload_generated_at(data) is None:
        return False
    minimum = data.get("min_resolved")
    resolved = data.get("resolved")
    playbooks = data.get("playbooks")
    factors = data.get("factors")
    if (
        not _bounded_int(minimum, minimum=1)
        or not _bounded_int(resolved)
        or not isinstance(minimum, int)
        or not isinstance(resolved, int)
        or not isinstance(playbooks, list)
        or len(playbooks) > 200
        or not isinstance(factors, list)
        or len(factors) > 500
    ):
        return False

    if status == "blocked":
        if (
            frozenset(data) != _PLAYBOOK_VALIDATION_BLOCKED_FIELDS
            or resolved != 0
            or playbooks
            or factors
            or not _daily_summary_text(
                data.get("reason"), max_length=4_000, allow_empty=False
            )
        ):
            return False
        decision_count = 0
    elif status in {"accumulating", "ready"}:
        decision_count = data.get("decision_count")
        outcome_count = data.get("outcome_count")
        if (
            frozenset(data) != _PLAYBOOK_VALIDATION_ACTIVE_FIELDS
            or not _bounded_int(decision_count)
            or not _bounded_int(outcome_count)
            or not isinstance(decision_count, int)
            or not isinstance(outcome_count, int)
            or resolved > decision_count
            or resolved > outcome_count
            or (status == "accumulating" and resolved >= minimum)
            or (status == "ready" and resolved < minimum)
        ):
            return False
    else:
        return False

    for row in playbooks:
        if not _valid_playbook_validation_row(
            row,
            label_field="playbook",
            expected_fields=_PLAYBOOK_VALIDATION_PLAYBOOK_FIELDS,
            min_resolved=minimum,
            total_resolved=resolved,
        ):
            return False
    for row in factors:
        if not _valid_playbook_validation_row(
            row,
            label_field="factor_id",
            expected_fields=_PLAYBOOK_VALIDATION_FACTOR_FIELDS,
            min_resolved=minimum,
            total_resolved=resolved,
        ):
            return False
    playbook_labels = [row["playbook"] for row in playbooks]
    factor_labels = [row["factor_id"] for row in factors]
    if (
        playbook_labels != sorted(playbook_labels)
        or len(playbook_labels) != len(set(playbook_labels))
        or factor_labels != sorted(factor_labels)
        or len(factor_labels) != len(set(factor_labels))
        or sum(int(row["resolved"]) for row in playbooks) != resolved
    ):
        return False
    try:
        PlaybookValidationData.model_validate(
            _project_playbook_validation(data),
            strict=True,
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        return False
    return True


def _project_playbook_validation(data: dict[str, object]) -> dict[str, object]:
    playbooks = data["playbooks"]
    factors = data["factors"]
    if not isinstance(playbooks, list) or not isinstance(factors, list):
        raise TypeError("validated Playbook summary rows must be arrays")
    return {
        "generated_at": data["generated_at"],
        "status": data["status"],
        "decision_count": data.get("decision_count", 0),
        "resolved": data["resolved"],
        "min_resolved": data["min_resolved"],
        "playbooks": [dict(row) for row in playbooks if isinstance(row, dict)],
        "factors": [dict(row) for row in factors if isinstance(row, dict)],
    }


def _playbook_validation_generated_at(data: dict[str, object]) -> str | None:
    value = data["generated_at"]
    if not isinstance(value, str):
        raise TypeError("validated Playbook generated_at must be a string")
    return value


def _project_continuation_validation(
    data: dict[str, object],
) -> dict[str, object]:
    rows = data["rows"]
    if not isinstance(rows, list):
        raise TypeError("validated Continuation Validation rows must be an array")
    minimum = data["min_resolved"]
    summary = data["summary"]
    if data["status"] == "blocked":
        summary = {
            "strong_continuation": 0,
            "normal_continuation": 0,
            "failed_breakout": 0,
            "unresolved": 0,
            "rows_total": 0,
            "resolved": 0,
            "min_resolved": minimum,
        }
    if not isinstance(summary, dict):
        raise TypeError("validated Continuation Validation summary must be an object")
    return {
        "generated_at": data["generated_at"],
        "status": data["status"],
        "resolved": data["resolved"],
        "min_resolved": minimum,
        "summary": dict(summary),
        "rows": [dict(row) for row in rows if isinstance(row, dict)],
    }


def _valid_continuation_validation_source(data: dict[str, object]) -> bool:
    status = data.get("status")
    if _payload_generated_at(data) is None:
        return False
    minimum = data.get("min_resolved")
    resolved = data.get("resolved")
    summary = data.get("summary")
    rows = data.get("rows")
    if (
        not _bounded_int(minimum, minimum=1)
        or not _bounded_int(resolved, maximum=5_000)
        or not isinstance(minimum, int)
        or not isinstance(resolved, int)
        or not isinstance(summary, dict)
        or not isinstance(rows, list)
        or len(rows) > 5_000
    ):
        return False
    if status == "blocked":
        if (
            frozenset(data) != _CONTINUATION_VALIDATION_BLOCKED_FIELDS
            or resolved != 0
            or summary
            or rows
            or not _daily_summary_text(
                data.get("reason"), max_length=4_000, allow_empty=False
            )
        ):
            return False
    elif status in {"accumulating", "ready"}:
        if (
            frozenset(data) != _CONTINUATION_VALIDATION_ACTIVE_FIELDS
            or not _daily_summary_text(
                data.get("note"), max_length=4_000, allow_empty=False
            )
            or any(
                not isinstance(row, dict)
                or frozenset(row) != _CONTINUATION_VALIDATION_ROW_FIELDS
                for row in rows
            )
        ):
            return False
    else:
        return False
    try:
        ContinuationValidationData.model_validate(
            _project_continuation_validation(data),
            strict=True,
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        return False
    return True


def _continuation_validation_generated_at(
    data: dict[str, object],
) -> str | None:
    value = data["generated_at"]
    if not isinstance(value, str):
        raise TypeError("validated Continuation generated_at must be a string")
    return value


def resolve_latest_daily_summary(
    directory: Path = REPORTS_DIR,
) -> ResolutionResult:
    """Select the newest exact real-date directory without older fallback."""

    try:
        root = directory.resolve(strict=True)
        candidates = [
            path
            for path in directory.iterdir()
            if _DAILY_SUMMARY_DIRECTORY_RE.fullmatch(path.name)
            and _is_iso_date(path.name)
        ]
    except FileNotFoundError:
        return ArtifactPathUnavailable("missing")
    except OSError:
        return ArtifactPathUnavailable("unreadable")
    if not candidates:
        return ArtifactPathUnavailable("missing")

    selected = max(candidates, key=lambda path: path.name)
    try:
        if selected.is_symlink() or not selected.is_dir():
            return ArtifactPathUnavailable("unreadable")
        selected_root = selected.resolve(strict=True)
        selected_root.relative_to(root)
        summary = selected / "summary.json"
        if summary.is_symlink():
            return ArtifactPathUnavailable("unreadable")
        summary.resolve(strict=False).relative_to(root)
    except (FileNotFoundError, OSError, ValueError):
        return ArtifactPathUnavailable("unreadable")
    return ResolvedArtifactPath(summary, as_of=selected.name)


def resolve_latest_market_thesis(
    directory: Path = MARKET_THESIS_DIR,
) -> ResolutionResult:
    """Resolve latest forecast by date, preferring ready on a same-day tie."""

    try:
        files = list(directory.glob("*forecast_*.json"))
    except FileNotFoundError:
        return ArtifactPathUnavailable("missing")
    except OSError:
        return ArtifactPathUnavailable("unreadable")
    if not files:
        return ArtifactPathUnavailable("missing")

    def rank(path: Path) -> tuple[str, bool]:
        match = _FORECAST_DATE_RE.search(path.name)
        as_of = match.group(1) if match else ""
        ready = not path.name.startswith("regime_only")
        return as_of, ready

    selected = max(files, key=rank)
    match = _FORECAST_DATE_RE.search(selected.name)
    return ResolvedArtifactPath(
        selected,
        as_of=match.group(1) if match else None,
    )


def resolve_latest_sector_rotation(
    directory: Path = SECTOR_ROTATION_ARCHIVE_DIR,
) -> ResolutionResult:
    """Select only the newest exact dated archive name, without older fallback."""

    try:
        candidates = []
        for path in directory.iterdir():
            match = _SECTOR_ROTATION_FILENAME_RE.fullmatch(path.name)
            if match is None or not path.is_file() or not _is_iso_date(match.group(1)):
                continue
            candidates.append((match.group(1), path))
    except FileNotFoundError:
        return ArtifactPathUnavailable("missing")
    except OSError:
        return ArtifactPathUnavailable("unreadable")
    if not candidates:
        return ArtifactPathUnavailable("missing")
    as_of, selected = max(candidates, key=lambda item: item[0])
    return ResolvedArtifactPath(selected, as_of=as_of)


_REGISTRY = {
    "candidates.ranked": ArtifactSpec(
        source_id="candidates.ranked",
        resolver=lambda: ResolvedArtifactPath(
            candidate_output_path("ranked_candidates.json")
        ),
        data_model=RankedCandidatesData,
        object_list_fields=("ranked_candidates",),
    ),
    "candidates.scored": ArtifactSpec(
        source_id="candidates.scored",
        resolver=lambda: ResolvedArtifactPath(
            candidate_output_path("scored_candidates.json")
        ),
        data_model=ScoredCandidatesData,
        object_list_fields=("all_scored",),
    ),
    RANKED_CANDIDATES_FEED_SOURCE_ID: ArtifactSpec(
        source_id=RANKED_CANDIDATES_FEED_SOURCE_ID,
        resolver=lambda: ResolvedArtifactPath(
            candidate_output_path("ranked_candidates.json")
        ),
        data_model=RankedCandidatesFeedData,
        data_validator=_valid_ranked_candidates_feed_source,
        data_projector=_project_ranked_candidates_feed,
    ),
    SCORED_CANDIDATES_FEED_SOURCE_ID: ArtifactSpec(
        source_id=SCORED_CANDIDATES_FEED_SOURCE_ID,
        resolver=lambda: ResolvedArtifactPath(
            candidate_output_path("scored_candidates.json")
        ),
        data_model=ScoredCandidatesFeedData,
        data_validator=_valid_scored_candidates_feed_source,
        data_projector=_project_scored_candidates_feed,
    ),
    SCORED_CANDIDATES_SCREENER_SOURCE_ID: ArtifactSpec(
        source_id=SCORED_CANDIDATES_SCREENER_SOURCE_ID,
        resolver=lambda: ResolvedArtifactPath(
            candidate_output_path("scored_candidates.json")
        ),
        data_model=ScoredCandidatesScreenerData,
        data_validator=_valid_scored_candidates_screener_source,
        data_projector=_project_scored_candidates_screener,
    ),
    "signals.options-flow.latest": ArtifactSpec(
        source_id="signals.options-flow.latest",
        resolver=_fixed(OPTIONS_FLOW_FILE),
        data_model=OptionsFlowData,
        object_list_fields=("signals",),
    ),
    OPTIONS_FLOW_FEED_SOURCE_ID: ArtifactSpec(
        source_id=OPTIONS_FLOW_FEED_SOURCE_ID,
        resolver=_fixed(OPTIONS_FLOW_FILE),
        data_model=OptionsFlowFeedData,
        data_validator=_valid_options_flow_feed_source,
        data_projector=_project_options_flow_feed,
    ),
    REVERSAL_RADAR_SOURCE_ID: ArtifactSpec(
        source_id=REVERSAL_RADAR_SOURCE_ID,
        resolver=_fixed(REPORTS_DIR / "reversal_radar" / "latest.json"),
        data_model=ReversalRadarData,
        data_validator=_valid_reversal_radar_source,
        data_projector=_project_reversal_radar,
        as_of_extractor=_signal_snapshot_as_of,
    ),
    REVERSAL_RADAR_VALIDATION_SOURCE_ID: ArtifactSpec(
        source_id=REVERSAL_RADAR_VALIDATION_SOURCE_ID,
        resolver=_fixed(REVERSAL_RADAR_VALIDATION_FILE),
        data_model=ReversalRadarValidationData,
        data_validator=_valid_reversal_validation_source,
        data_projector=_project_reversal_validation,
        generated_at_extractor=_reversal_validation_generated_at,
    ),
    OVERSOLD_REVERSAL_SOURCE_ID: ArtifactSpec(
        source_id=OVERSOLD_REVERSAL_SOURCE_ID,
        resolver=_fixed(REPORTS_DIR / "oversold_reversal" / "latest.json"),
        data_model=OversoldReversalData,
        data_validator=_valid_oversold_reversal_source,
        data_projector=_project_oversold_reversal,
        as_of_extractor=_signal_snapshot_as_of,
    ),
    OVERSOLD_REVERSAL_VALIDATION_SOURCE_ID: ArtifactSpec(
        source_id=OVERSOLD_REVERSAL_VALIDATION_SOURCE_ID,
        resolver=_fixed(OVERSOLD_REVERSAL_VALIDATION_FILE),
        data_model=OversoldReversalValidationData,
        data_validator=_valid_oversold_validation_source,
        data_projector=_project_oversold_validation,
        generated_at_extractor=_oversold_validation_generated_at,
    ),
    MARKET_THESIS_SOURCE_ID: ArtifactSpec(
        source_id=MARKET_THESIS_SOURCE_ID,
        resolver=resolve_latest_market_thesis,
        data_model=MarketThesisData,
        data_validator=_valid_market_thesis_source,
        data_projector=_project_market_thesis,
        as_of_extractor=_market_thesis_as_of,
    ),
    DAILY_SUMMARY_SOURCE_ID: ArtifactSpec(
        source_id=DAILY_SUMMARY_SOURCE_ID,
        resolver=resolve_latest_daily_summary,
        data_model=DailySummaryData,
        data_validator=_valid_daily_summary_source,
        data_projector=_project_daily_summary,
        as_of_extractor=_daily_summary_as_of,
        require_resolved_as_of_match=True,
    ),
    PLAYBOOK_VALIDATION_SOURCE_ID: ArtifactSpec(
        source_id=PLAYBOOK_VALIDATION_SOURCE_ID,
        resolver=_fixed(PLAYBOOK_VALIDATION_FILE),
        data_model=PlaybookValidationData,
        data_validator=_valid_playbook_validation_source,
        data_projector=_project_playbook_validation,
        generated_at_extractor=_playbook_validation_generated_at,
    ),
    CONTINUATION_VALIDATION_SOURCE_ID: ArtifactSpec(
        source_id=CONTINUATION_VALIDATION_SOURCE_ID,
        resolver=_fixed(CONTINUATION_VALIDATION_FILE),
        data_model=ContinuationValidationData,
        data_validator=_valid_continuation_validation_source,
        data_projector=_project_continuation_validation,
        generated_at_extractor=_continuation_validation_generated_at,
    ),
    MARKET_THESIS_VALIDATION_SOURCE_ID: ArtifactSpec(
        source_id=MARKET_THESIS_VALIDATION_SOURCE_ID,
        resolver=_fixed(MARKET_THESIS_VALIDATION_FILE),
        data_model=MarketThesisValidationData,
        data_validator=_valid_market_thesis_validation_source,
        data_projector=_project_market_thesis_validation,
    ),
    MARKET_THESIS_REGIME_HISTORY_SOURCE_ID: ArtifactSpec(
        source_id=MARKET_THESIS_REGIME_HISTORY_SOURCE_ID,
        resolver=_fixed(MARKET_THESIS_REGIME_HISTORY_FILE),
        data_model=MarketThesisRegimeHistoryData,
        data_validator=_valid_market_thesis_regime_source,
        data_projector=_project_market_thesis_regime,
    ),
    SOCIAL_INTELLIGENCE_SOURCE_ID: ArtifactSpec(
        source_id=SOCIAL_INTELLIGENCE_SOURCE_ID,
        resolver=_fixed(SOCIAL_INTELLIGENCE_FILE),
        data_model=SocialIntelligenceData,
        data_validator=_valid_social_intelligence_source,
        data_projector=_project_social_intelligence,
        as_of_extractor=_social_intelligence_as_of,
    ),
    THEME_FLOW_SOURCE_ID: ArtifactSpec(
        source_id=THEME_FLOW_SOURCE_ID,
        resolver=_fixed(THEME_FLOW_FILE),
        data_model=ThemeFlowData,
        data_validator=_valid_theme_flow_source,
        data_projector=_project_theme_flow,
        as_of_extractor=_theme_flow_as_of,
    ),
    THEME_FLOW_ANALYSIS_SOURCE_ID: ArtifactSpec(
        source_id=THEME_FLOW_ANALYSIS_SOURCE_ID,
        resolver=_fixed(THEME_FLOW_ANALYSIS_FILE),
        data_model=ThemeFlowAnalysisData,
        data_validator=_valid_theme_flow_analysis_source,
        data_projector=_project_theme_flow_analysis,
        as_of_extractor=_theme_flow_as_of,
    ),
    MONEY_FLOW_SOURCE_ID: ArtifactSpec(
        source_id=MONEY_FLOW_SOURCE_ID,
        resolver=_fixed(MONEY_FLOW_FILE),
        data_model=MoneyFlowData,
        data_validator=_valid_money_flow_source,
        data_projector=_project_money_flow,
        as_of_extractor=_money_flow_as_of,
    ),
    SECTOR_ROTATION_SOURCE_ID: ArtifactSpec(
        source_id=SECTOR_ROTATION_SOURCE_ID,
        resolver=resolve_latest_sector_rotation,
        data_model=SectorRotationData,
        data_validator=_valid_sector_rotation_source,
        data_projector=_project_sector_rotation,
        as_of_extractor=_sector_rotation_as_of,
        generated_at_extractor=_sector_rotation_generated_at,
    ),
    "institutions.funds": ArtifactSpec(
        source_id=FUND_CATALOG_SOURCE_ID,
        resolver=_fixed(FUND_CATALOG_FILE),
        data_model=FundCatalogData,
        data_validator=_valid_fund_catalog_source,
        data_projector=_project_fund_catalog,
    ),
    "system.ai-updates": ArtifactSpec(
        source_id=AI_UPDATES_SOURCE_ID,
        resolver=_fixed(AI_UPDATES_FILE),
        data_model=AiUpdatesData,
        data_validator=_valid_ai_updates_source,
        data_projector=_project_ai_updates,
        as_of_extractor=_ai_updates_as_of,
    ),
    "system.schedules": ArtifactSpec(
        source_id=SCHEDULES_SOURCE_ID,
        resolver=_fixed(SCHEDULES_FILE),
        data_model=SchedulesData,
        data_validator=_valid_schedules_source,
        data_projector=_project_schedules,
    ),
    CRYPTO_UNIVERSE_SOURCE_ID: ArtifactSpec(
        source_id=CRYPTO_UNIVERSE_SOURCE_ID,
        resolver=_fixed(CRYPTO_UNIVERSE_FILE),
        data_model=CryptoUniverseData,
        data_validator=_valid_crypto_universe_source,
        data_projector=_project_crypto_universe,
        as_of_extractor=_crypto_universe_as_of,
    ),
}
ARTIFACTS: Mapping[str, ArtifactSpec] = MappingProxyType(_REGISTRY)


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validated_data(
    data: dict[str, object],
    spec: ArtifactSpec,
) -> dict[str, object] | None:
    if spec.data_validator is not None:
        verdict = spec.data_validator(data)
        if type(verdict) is not bool:
            raise TypeError("artifact data validator must return bool")
        if verdict is False:
            return None
    public_data = spec.data_projector(data) if spec.data_projector is not None else data
    if not isinstance(public_data, dict):
        raise TypeError("artifact data projector must return an object")
    for field in spec.object_list_fields:
        value = public_data.get(field)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            return None
    for field in spec.string_fields:
        if not isinstance(public_data.get(field), str):
            return None
    for field in spec.date_fields:
        if not _is_iso_date(public_data.get(field)):
            return None
    try:
        spec.data_model.model_validate(public_data)
    except ValidationError:
        return None
    return public_data


def _payload_as_of(
    data: dict[str, object],
    resolved_as_of: str | None,
    as_of_extractor: AsOfExtractor | None = None,
) -> str | None:
    if as_of_extractor is not None:
        extracted = as_of_extractor(data)
        if extracted is None:
            return None
        if not _is_iso_date(extracted):
            raise ValueError("artifact as-of extractor returned a non-date")
        return extracted
    if _is_iso_date(resolved_as_of):
        return resolved_as_of
    for field in ("as_of", "as_of_date", "scan_date"):
        value = data.get(field)
        if _is_iso_date(value):
            return value
    return None


def _payload_generated_at(
    data: dict[str, object],
    generated_at_extractor: GeneratedAtExtractor | None = None,
) -> datetime | None:
    value = (
        generated_at_extractor(data)
        if generated_at_extractor is not None
        else data.get("generated_at")
    )
    if not isinstance(value, str) or not _RFC3339_DATETIME_RE.fullmatch(value):
        return None
    normalized = value.replace("t", "T")
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _meta(
    spec: ArtifactSpec,
    *,
    data: dict[str, object] | None = None,
    source_data: dict[str, object] | None = None,
    resolved_as_of: str | None = None,
) -> ArtifactMeta:
    return ArtifactMeta(
        sourceId=spec.source_id,
        asOf=_payload_as_of(
            data or {},
            resolved_as_of,
            spec.as_of_extractor if data is not None else None,
        ),
        generatedAt=_payload_generated_at(
            (
                source_data
                if spec.generated_at_extractor is not None and source_data is not None
                else (data or {})
            ),
            spec.generated_at_extractor if data is not None else None,
        ),
    )


def _unavailable(
    spec: ArtifactSpec,
    reason: Literal["missing", "invalid_json", "invalid_shape", "unreadable"],
    *,
    resolved_as_of: str | None = None,
) -> ArtifactUnavailable:
    return ArtifactUnavailable(
        available=False,
        reason=reason,
        data=None,
        meta=_meta(spec, resolved_as_of=resolved_as_of),
    )


ArtifactReadResult: TypeAlias = (
    ArtifactAvailable[dict[str, object]] | ArtifactUnavailable
)


def _fixed_meta(source_id: str) -> ArtifactMeta:
    return ArtifactMeta(sourceId=source_id, asOf=None, generatedAt=None)


def _fixed_read_unavailable(
    source_id: str,
    reason: Literal["missing", "invalid_json", "invalid_shape", "unreadable"],
) -> ArtifactUnavailable:
    return ArtifactUnavailable(
        available=False,
        reason=reason,
        data=None,
        meta=_fixed_meta(source_id),
    )


def _read_bounded_bytes(path: Path, maximum: int) -> bytes | Literal["missing", "unreadable", "invalid_shape"]:
    descriptor: int | None = None
    try:
        if path.is_symlink():
            return "unreadable"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            descriptor = None
            return "unreadable"
        handle = os.fdopen(descriptor, "rb")
        descriptor = None
        with handle:
            data = handle.read(maximum + 1)
    except FileNotFoundError:
        if descriptor is not None:
            os.close(descriptor)
        return "missing"
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        return "unreadable"
    return "invalid_shape" if len(data) > maximum else data


def _read_bounded_json_object(
    path: Path,
    maximum: int,
) -> dict[str, object] | Literal["missing", "unreadable", "invalid_shape"]:
    raw = _read_bounded_bytes(path, maximum)
    if isinstance(raw, str):
        return raw
    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid_shape"
    return payload if isinstance(payload, dict) else "invalid_shape"


def read_knowledge_graph(
    vault: Path = KNOWLEDGE_VAULT,
) -> ArtifactAvailable[KnowledgeGraphData] | ArtifactUnavailable:
    """Compile one bounded fixed vault without a second filesystem scan."""

    try:
        if vault.is_symlink():
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "unreadable")
        if not vault.exists():
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "missing")
        if not vault.is_dir():
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "unreadable")

        pending = [vault]
        markdown_paths: list[Path] = []
        directory_count = 0
        entry_count = 0
        while pending:
            directory = pending.pop()
            directory_count += 1
            if directory_count > 256:
                return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")
            children: list[Path] = []
            for child in directory.iterdir():
                entry_count += 1
                if entry_count > 2_000:
                    return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")
                if child.is_symlink():
                    return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "unreadable")
                children.append(child)
            for child in sorted(children, reverse=True):
                if child.is_dir():
                    pending.append(child)
                elif child.is_file() and child.suffix.casefold() == ".md":
                    markdown_paths.append(child)
                    if len(markdown_paths) > 500:
                        return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")
    except OSError:
        return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "unreadable")

    cards: list[knowledge_graph_engine.Card] = []
    aggregate_bytes = 0
    for path in sorted(markdown_paths, key=lambda item: item.relative_to(vault).as_posix()):
        raw = _read_bounded_bytes(path, 256 * 1024)
        if isinstance(raw, str):
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, raw)
        aggregate_bytes += len(raw)
        if aggregate_bytes > 8 * 1024 * 1024:
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")
        try:
            text = raw.decode("utf-8")
            cards.append(knowledge_graph_engine.parse_card_text(path, vault, text))
        except (UnicodeDecodeError, ValueError, OSError):
            return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")

    try:
        compiled = knowledge_graph_engine.build_graph_from_cards(cards)
        projected = {
            "nodes": [
                {
                    "id": str(node.get("id") or ""),
                    "label": str(node.get("label") or ""),
                    "type": str(node.get("type") or ""),
                    "dimension": str(node.get("dimension") or ""),
                    "horizon": str(node.get("horizon") or ""),
                    "status": str(node.get("status") or ""),
                    "blocked": node.get("blocked"),
                    "lift_exploratory": (
                        None
                        if node.get("lift_exploratory") in (None, "")
                        else float(node["lift_exploratory"])
                    ),
                    "runway_verdict": str(node.get("runway_verdict") or ""),
                    "verdict_raw": str(node.get("verdict_raw") or ""),
                }
                for node in compiled.get("nodes", [])
            ],
            "edges": [
                {key: edge.get(key) for key in ("source", "target", "type")}
                for edge in compiled.get("edges", [])
            ],
            "diagnostics": {
                "unresolved_links": [
                    {key: item.get(key) for key in ("source", "target")}
                    for item in compiled.get("diagnostics", {}).get("unresolved_links", [])
                ],
                "duplicate_ids": compiled.get("diagnostics", {}).get("duplicate_ids", []),
            },
        }
        data = KnowledgeGraphData.model_validate(projected, strict=True)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _fixed_read_unavailable(KNOWLEDGE_GRAPH_SOURCE_ID, "invalid_shape")
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_fixed_meta(KNOWLEDGE_GRAPH_SOURCE_ID),
    )


def read_theme_taxonomy(
    path: Path = THEME_TAXONOMY_FILE,
) -> ArtifactAvailable[ThemeTaxonomyData] | ArtifactUnavailable:
    payload = _read_bounded_json_object(path, 64 * 1024)
    if isinstance(payload, str):
        return _fixed_read_unavailable(THEME_TAXONOMY_SOURCE_ID, payload)
    if not set(payload).issubset({"_note", "themes"}) or not isinstance(payload.get("themes"), dict):
        return _fixed_read_unavailable(THEME_TAXONOMY_SOURCE_ID, "invalid_shape")
    try:
        data = ThemeTaxonomyData.model_validate(
            {
                "themes": [
                    {"name": name, "description": description}
                    for name, description in payload["themes"].items()
                ]
            },
            strict=True,
        )
    except (TypeError, ValidationError):
        return _fixed_read_unavailable(THEME_TAXONOMY_SOURCE_ID, "invalid_shape")
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_fixed_meta(THEME_TAXONOMY_SOURCE_ID),
    )


def read_theme_drill(
    path: Path = THEME_DRILL_FILE,
) -> ArtifactAvailable[ThemeDrillData] | ArtifactUnavailable:
    payload = _read_bounded_json_object(path, 64 * 1024)
    if isinstance(payload, str):
        return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, payload)
    if not set(payload).issubset({"_note", "themes"}):
        return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
    themes = payload.get("themes")
    if not isinstance(themes, dict) or len(themes) > 100:
        return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")

    source_names: set[str] = set()
    reverse_map: dict[str, list[str]] = {}
    for name, record in themes.items():
        if not isinstance(name, str) or name.casefold() in source_names:
            return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
        source_names.add(name.casefold())
        if not isinstance(record, dict):
            return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
        parents = record.get("parent_sector_etfs")
        if not isinstance(parents, list) or not parents or len(parents) > 11:
            return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
        if (
            any(not isinstance(parent, str) for parent in parents)
            or len(parents) != len(set(parents))
        ):
            return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
        for parent in parents:
            reverse_map.setdefault(parent, []).append(name)

    try:
        data = ThemeDrillData.model_validate(
            {
                "sectors": [
                    {"etf": etf, "themes": reverse_map[etf]}
                    for etf in sorted(reverse_map)
                ]
            },
            strict=True,
        )
    except (TypeError, ValidationError):
        return _fixed_read_unavailable(THEME_DRILL_SOURCE_ID, "invalid_shape")
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_fixed_meta(THEME_DRILL_SOURCE_ID),
    )


def read_influencer_roster(
    path: Path,
) -> ArtifactAvailable[InfluencerRosterData] | ArtifactUnavailable:
    payload = _read_bounded_json_object(path, 1024 * 1024)
    if isinstance(payload, str):
        return _fixed_read_unavailable(INFLUENCER_ROSTER_SOURCE_ID, payload)
    if not set(payload).issubset({"_note", "categories_order", "influencers"}):
        return _fixed_read_unavailable(INFLUENCER_ROSTER_SOURCE_ID, "invalid_shape")
    categories = payload.get("categories_order")
    rows = payload.get("influencers")
    if not isinstance(categories, list) or not isinstance(rows, list):
        return _fixed_read_unavailable(INFLUENCER_ROSTER_SOURCE_ID, "invalid_shape")
    ordered_categories = list(categories)
    seen_categories = {
        item.casefold() for item in ordered_categories if isinstance(item, str)
    }
    projected_rows: list[dict[str, object]] = []
    optional_fields = (
        "name",
        "note",
        "url",
        "category_source",
        "category_reason",
        "category_confidence",
        "placeholder",
    )
    for row in rows:
        if not isinstance(row, dict):
            return _fixed_read_unavailable(INFLUENCER_ROSTER_SOURCE_ID, "invalid_shape")
        projected = {
            "handle": row.get("handle"),
            "category": row.get("category"),
            "market": row.get("market"),
        }
        projected.update({key: row[key] for key in optional_fields if key in row})
        projected_rows.append(projected)
        category = row.get("category")
        if isinstance(category, str) and category.casefold() not in seen_categories:
            ordered_categories.append(category)
            seen_categories.add(category.casefold())
    try:
        data = InfluencerRosterData.model_validate(
            {"categories": ordered_categories, "influencers": projected_rows},
            strict=True,
        )
    except ValidationError:
        return _fixed_read_unavailable(INFLUENCER_ROSTER_SOURCE_ID, "invalid_shape")
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_fixed_meta(INFLUENCER_ROSTER_SOURCE_ID),
    )


def read_artifact(spec: ArtifactSpec) -> ArtifactReadResult:
    """Resolve, strictly parse, and validate one registered artifact."""

    resolved = spec.resolver()
    if isinstance(resolved, ArtifactPathUnavailable):
        return _unavailable(spec, resolved.reason)

    loaded = load_json_artifact(resolved.path)
    if isinstance(loaded, UnloadedArtifact):
        return _unavailable(
            spec,
            loaded.reason,
            resolved_as_of=resolved.as_of,
        )
    if not isinstance(loaded, LoadedArtifact) or not isinstance(loaded.data, dict):
        return _unavailable(
            spec,
            "invalid_shape",
            resolved_as_of=resolved.as_of,
        )

    source_data: dict[str, object] = loaded.data
    public_data = _validated_data(source_data, spec)
    if public_data is None:
        return _unavailable(
            spec,
            "invalid_shape",
            resolved_as_of=resolved.as_of,
        )
    if spec.require_resolved_as_of_match:
        public_as_of = _payload_as_of(
            public_data,
            None,
            spec.as_of_extractor,
        )
        if resolved.as_of is None or public_as_of != resolved.as_of:
            return _unavailable(
                spec,
                "invalid_shape",
                resolved_as_of=resolved.as_of,
            )
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=public_data,
        meta=_meta(
            spec,
            data=public_data,
            source_data=source_data,
            resolved_as_of=resolved.as_of,
        ),
    )


def _cot_meta(
    source_id: str,
    *,
    as_of: str | None = None,
    generated_at: datetime | None = None,
) -> ArtifactMeta:
    return ArtifactMeta(
        sourceId=source_id,
        asOf=as_of,
        generatedAt=generated_at,
    )


def _cot_unavailable(
    source_id: str,
    reason: Literal["missing", "invalid_json", "invalid_shape", "unreadable"],
    *,
    as_of: str | None = None,
) -> ArtifactUnavailable:
    return ArtifactUnavailable(
        available=False,
        reason=reason,
        data=None,
        meta=_cot_meta(source_id, as_of=as_of),
    )


def _cot_directory_snapshot(
    directory: Path,
) -> tuple[Path | None, Literal["missing", "unreadable"] | None]:
    """Pin a possibly generation-backed directory to one physical request snapshot."""

    try:
        if not directory.exists():
            return None, "unreadable" if directory.is_symlink() else "missing"
        snapshot = directory.resolve(strict=True)
        if not snapshot.is_dir():
            return None, "unreadable"
    except OSError:
        return None, "unreadable"
    return snapshot, None


def read_cot_catalog(
    directory: Path = COT_REPORTS_DIR,
) -> ArtifactReadResult:
    """Read a bounded newest-first catalog without exposing directory details."""

    snapshot, reason = _cot_directory_snapshot(directory)
    if snapshot is None:
        return _cot_unavailable(COT_CATALOG_SOURCE_ID, reason or "unreadable")
    try:
        entries = list(snapshot.iterdir())
    except OSError:
        return _cot_unavailable(COT_CATALOG_SOURCE_ID, "unreadable")

    report_dates: list[str] = []
    for path in entries:
        match = _COT_MARKDOWN_FILENAME_RE.fullmatch(path.name)
        if match is None:
            continue
        report_date = match.group(1)
        if not _is_iso_date(report_date):
            return _cot_unavailable(COT_CATALOG_SOURCE_ID, "invalid_shape")
        try:
            if path.is_symlink() or not path.is_file():
                return _cot_unavailable(COT_CATALOG_SOURCE_ID, "unreadable")
        except OSError:
            return _cot_unavailable(COT_CATALOG_SOURCE_ID, "unreadable")
        report_dates.append(report_date)

    if len(report_dates) > _COT_CATALOG_LIMIT:
        return _cot_unavailable(COT_CATALOG_SOURCE_ID, "invalid_shape")
    payload = {
        "reports": [
            {"report_date": report_date}
            for report_date in sorted(report_dates, reverse=True)
        ]
    }
    try:
        data = CotCatalogData.model_validate(payload, strict=True).model_dump()
    except ValidationError:
        return _cot_unavailable(COT_CATALOG_SOURCE_ID, "invalid_shape")
    as_of = data["reports"][0]["report_date"] if data["reports"] else None
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_cot_meta(COT_CATALOG_SOURCE_ID, as_of=as_of),
    )


def read_cot_report(
    report_date: str,
    directory: Path = COT_REPORTS_DIR,
) -> ArtifactReadResult:
    """Read one exact Markdown/verified pair with no cross-date fallback."""

    if not _is_iso_date(report_date):
        return _cot_unavailable(COT_DETAIL_SOURCE_ID, "invalid_shape")
    snapshot, reason = _cot_directory_snapshot(directory)
    if snapshot is None:
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, reason or "unreadable", as_of=report_date
        )
    markdown_path = snapshot / f"{report_date}.md"
    verified_path = snapshot / f"{report_date}.verified.json"
    try:
        if not markdown_path.exists() or not verified_path.exists():
            return _cot_unavailable(
                COT_DETAIL_SOURCE_ID, "missing", as_of=report_date
            )
        if (
            markdown_path.is_symlink()
            or verified_path.is_symlink()
            or not markdown_path.is_file()
            or not verified_path.is_file()
        ):
            return _cot_unavailable(
                COT_DETAIL_SOURCE_ID, "unreadable", as_of=report_date
            )
        if (
            markdown_path.stat().st_size > _COT_MARKDOWN_MAX_BYTES
            or verified_path.stat().st_size > _COT_VERIFIED_MAX_BYTES
        ):
            return _cot_unavailable(
                COT_DETAIL_SOURCE_ID, "invalid_shape", as_of=report_date
            )
        markdown = markdown_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, "invalid_shape", as_of=report_date
        )
    except OSError:
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, "unreadable", as_of=report_date
        )

    loaded = load_json_artifact(verified_path)
    if isinstance(loaded, UnloadedArtifact):
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID,
            loaded.reason,
            as_of=report_date,
        )
    if not isinstance(loaded, LoadedArtifact) or not isinstance(loaded.data, dict):
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, "invalid_shape", as_of=report_date
        )
    try:
        report = CotReportData.model_validate(
            {
                "report_date": report_date,
                "markdown": markdown,
                "verified": loaded.data,
            },
            strict=True,
        )
    except ValidationError:
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, "invalid_shape", as_of=report_date
        )
    data = report.model_dump()
    retrieved_at = report.verified.price.retrieved_at
    generated_at = _payload_generated_at({"generated_at": retrieved_at})
    if generated_at is None:
        return _cot_unavailable(
            COT_DETAIL_SOURCE_ID, "invalid_shape", as_of=report_date
        )
    return ArtifactAvailable(
        available=True,
        reason="ok",
        data=data,
        meta=_cot_meta(
            COT_DETAIL_SOURCE_ID,
            as_of=report_date,
            generated_at=generated_at,
        ),
    )
