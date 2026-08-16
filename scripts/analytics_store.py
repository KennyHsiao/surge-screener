#!/usr/bin/env python3
"""DuckDB + Parquet analytics store for historical report data.

This is an opt-in read model. Existing JSON/CSV reports stay the source of truth;
this module exports selected append/history-shaped artifacts into Parquet and
materializes DuckDB tables from those files for fast cross-date queries.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"

PERFORMANCE_LEDGER_COLUMNS = [
    "scan_date", "ticker", "verdict", "composite_score", "regime_multiplier",
    "tech_score", "catalyst_score", "sentiment_score", "inst_score",
    "sector_score", "options_score", "analyst_score", "dim1_breakdown",
    "pattern_type", "macd_state", "layer2_path", "layer2_outcome",
    "dd_verdict", "dd_short_thesis_strength", "suggested_entry_low",
    "suggested_entry_high", "suggested_stop", "suggested_size_pct",
    "fwd_3d_return", "fwd_7d_return", "fwd_14d_return", "fwd_30d_return",
    "fwd_60d_return", "hit_15pct_within_30d", "hit_30pct_within_60d",
    "max_drawdown_30d", "notes",
]

IV_HISTORY_COLUMNS = ["ticker", "as_of_date", "atm_iv", "source_file"]
OPTIONS_FLOW_SIGNAL_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "provider", "min_notional",
    "universe_size", "signal_count", "ticker", "direction", "flow_score",
    "est_notional_usd", "expiry", "max_voi", "high_voi_strikes",
    "call_put_ratio", "put_call_ratio", "total_call_vol", "total_put_vol",
    "otm_call_vol", "spot", "tags_json", "biggest_json", "raw_signal_json",
]
REVERSAL_RADAR_SIGNAL_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "universe", "universe_size",
    "scanned", "match_count", "lane_id", "exploratory", "runway_independent",
    "ticker", "signal_date", "status", "reversal_score", "data_confidence",
    "structure_score", "momentum_score", "options_score", "sector_score",
    "insider_score", "analyst_score", "primary_signals_json", "data_gaps_json",
    "lead_vs_confirm_json", "structure_json", "momentum_json", "options_json",
    "sector_json", "insider_json", "analyst_json", "pullback_json",
    "raw_candidate_json",
]
OVERSOLD_REVERSAL_SIGNAL_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "universe", "scanned",
    "attempted", "match_count", "lane_id", "exploratory",
    "runway_independent", "fetch_failed_json", "ticker", "signal_date",
    "avg_dollar_vol_m", "last_price", "rsi14", "bb_width_pct", "ma200",
    "pct_vs_ma200", "pct_from_52w_high", "raw_candidate_json",
]
MARKET_THESIS_FORECAST_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "tier", "method",
    "benchmark", "direction", "bucket", "support_class", "manifest_status",
    "regime", "vix_bucket", "label", "rationale_json", "raw_forecast_json",
]
CANDIDATE_SCORE_COLUMNS = [
    "source_file", "scan_date", "generated_at", "cohort_type",
    "ranked_universe_count", "scored_cohort_count", "selection_method",
    "rank_limit", "ranking_model", "total_candidates",
    "scored_candidates_count", "remaining_unscored", "needs_layer2_count",
    "watchlist_count", "min_score_threshold", "ticker", "verdict",
    "composite_score", "regime_adjusted_score", "technical", "catalyst",
    "sentiment", "institutional", "sector_market", "options_flow",
    "analyst", "pattern_type", "scoring_mode", "due_diligence_required",
    "data_missing_json", "raw_candidate_json",
]
CANDIDATE_RANKING_COLUMNS = [
    "source_file", "scan_date", "as_of_date", "generated_at", "universe",
    "markets", "source", "scoring_model", "total_universe",
    "passed_hard_filters", "total_candidates", "all_ranked_count",
    "rank_limit", "ranked_candidates_count", "rank_position", "ticker",
    "rank_score", "rank_bucket", "last_price", "ma50", "ma200", "ret_5d",
    "ret_20d", "avg_dollar_vol_20d", "market_cap", "macd_current",
    "macd_zero_cross_10d", "macd_golden_cross_10d",
    "rsi_bullish_divergence", "has_reversal_pattern", "technical_trend",
    "momentum_strength", "launch_signal", "liquidity_tradability",
    "overheat_risk_control", "data_quality_status", "missing_fields_json",
    "options_status", "options_momentum_verdict", "options_spread_pct",
    "options_open_interest", "options_volume", "options_iv_percentile",
    "options_iv_percentile_real", "options_earnings_status",
    "options_earnings_days_away", "options_max_call_voi",
    "options_call_put_volume_ratio", "options_total_call_volume",
    "options_total_put_volume", "options_flow_score",
    "options_data_missing_json", "options_warnings_json", "warnings_json",
    "score_weights_json", "rank_buckets_json", "options_gate_json",
    "score_components_json", "data_quality_json", "options_tradability_json",
    "raw_candidate_json",
]
CANDIDATE_OUTCOME_COLUMNS = [
    "source_file", "scan_date", "generated_at", "source", "source_rank_file",
    "rank_limit", "ticker", "rank_position", "rank_score", "rank_bucket",
    "scoring_model", "entry_price", "entry_price_date", "last_verified_at",
    "days_elapsed", "fwd_7d_return", "fwd_14d_return", "fwd_30d_return",
    "fwd_60d_return", "max_drawdown_30d", "hit_15pct_within_30d",
    "hit_30pct_within_60d", "resolved_7d", "resolved_14d",
    "resolved_30d", "resolved_60d", "raw_outcome_json",
]
CANDIDATE_OUTCOME_STRING_COLUMNS = {
    "source_file", "scan_date", "generated_at", "source", "source_rank_file",
    "ticker", "rank_bucket", "scoring_model", "entry_price_date",
    "last_verified_at", "raw_outcome_json",
}
CANDIDATE_OUTCOME_BOOL_COLUMNS = {
    "hit_15pct_within_30d", "hit_30pct_within_60d", "resolved_7d",
    "resolved_14d", "resolved_30d", "resolved_60d",
}
CANDIDATE_OUTCOME_NUMBER_COLUMNS = {
    "rank_limit", "rank_position", "rank_score", "entry_price",
    "days_elapsed", "fwd_7d_return", "fwd_14d_return", "fwd_30d_return",
    "fwd_60d_return", "max_drawdown_30d",
}
RISK_GUARD_ROW_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "market_status",
    "market_score_total", "market_reasons_json", "market_data_gaps_json",
    "summary_count", "summary_high_risk", "summary_data_gaps",
    "summary_systemic_gaps", "data_sources_json", "ticker", "status",
    "risk_score", "market_score", "price_score", "options_score",
    "sector_score", "position_score", "cot_score", "data_quality_score",
    "primary_reasons_json", "data_gaps_json", "last_price", "ma20", "ma50",
    "ma200", "vwap", "atr14", "rsi14", "price_above_vwap",
    "resistance_20d", "put_call_ratio", "iv_percentile", "sector_etf",
    "sector_name_zh", "sector_quadrant", "sector_quadrant_zh",
    "sector_heat_score", "sector_excess_20d", "sector_rs_ratio",
    "sector_rs_momentum", "position_total_unrealized_pnl",
    "position_worst_leg_return_pct", "position_min_option_dte",
    "position_leg_count", "position_held_not_in_ledger", "raw_row_json",
]
PORTFOLIO_POSITION_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "reachable",
    "position_status", "ticker", "held", "ranked", "verdict", "scan_date",
    "suggested_entry_low", "suggested_entry_high", "fwd_30d_return",
    "total_unrealized_pnl", "leg_count", "option_leg_count",
    "stock_leg_count", "min_option_dte", "earliest_expiry",
    "worst_leg_return_pct", "option_rights_json", "raw_position_json",
]
PORTFOLIO_POSITION_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "position_status", "ticker",
    "verdict", "scan_date", "earliest_expiry", "option_rights_json",
    "raw_position_json",
}
PORTFOLIO_POSITION_BOOL_COLUMNS = {"reachable", "held", "ranked"}
PORTFOLIO_POSITION_NUMBER_COLUMNS = {
    "suggested_entry_low", "suggested_entry_high", "fwd_30d_return",
    "total_unrealized_pnl", "leg_count", "option_leg_count",
    "stock_leg_count", "min_option_dte", "worst_leg_return_pct",
}
THEME_FLOW_SNAPSHOT_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "benchmark",
    "schema_version", "n_failed_download", "theme", "desc", "capital_state",
    "heat_score", "flow_5d", "flow_5d_norm", "flow_20d",
    "flow_20d_norm", "accel", "accel_norm", "ret_5d", "excess_5d",
    "rvol", "top_share", "high_concentration", "eastmoney_main_net_5d",
    "eastmoney_main_net_20d", "eastmoney_main_pct_latest",
    "money_flow_source", "money_flow_caveat", "n_total", "n_used",
    "n_failed", "shared_mega_caps_json", "parent_sector_etfs_json",
    "reps_json", "bottom_fishing_json", "buckets_json", "params_json",
    "raw_theme_json",
]
THEME_FLOW_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "benchmark", "theme",
    "desc", "capital_state", "money_flow_source", "money_flow_caveat",
    "shared_mega_caps_json",
    "parent_sector_etfs_json", "reps_json", "bottom_fishing_json",
    "buckets_json", "params_json", "raw_theme_json",
}
THEME_FLOW_BOOL_COLUMNS = {"high_concentration"}
THEME_FLOW_NUMBER_COLUMNS = {
    "schema_version", "n_failed_download", "heat_score", "flow_5d",
    "flow_5d_norm", "flow_20d", "flow_20d_norm", "accel", "accel_norm",
    "ret_5d", "excess_5d", "rvol", "top_share", "eastmoney_main_net_5d",
    "eastmoney_main_net_20d", "eastmoney_main_pct_latest", "n_total",
    "n_used", "n_failed",
}
SECTOR_ROTATION_SNAPSHOT_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "status", "benchmark",
    "etf", "name_zh", "group", "theme", "quadrant", "quadrant_zh",
    "rs_ratio", "rs_momentum", "heat_score", "ret_5d", "ret_20d",
    "ret_60d", "excess_20d", "pct_vs_ma50", "pct_vs_ma200", "rvol",
    "pct_from_52w_high", "is_leader", "is_improving", "leader_rank",
    "improving_rank", "spy_price", "spy_vs_50dma", "spy_vs_200dma",
    "vix_level", "read_confidence", "read_headline", "read_cycle_read",
    "read_next_rotation_thesis", "read_hot_now_json",
    "read_rotating_into_json", "read_caveats_json", "params_json",
    "tail_json", "raw_sector_json",
]
SECTOR_ROTATION_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "status", "benchmark",
    "etf", "name_zh", "group", "theme", "quadrant", "quadrant_zh",
    "spy_vs_50dma", "spy_vs_200dma", "read_confidence", "read_headline",
    "read_cycle_read", "read_next_rotation_thesis", "read_hot_now_json",
    "read_rotating_into_json", "read_caveats_json", "params_json",
    "tail_json", "raw_sector_json",
}
SECTOR_ROTATION_BOOL_COLUMNS = {"is_leader", "is_improving"}
SECTOR_ROTATION_NUMBER_COLUMNS = {
    "rs_ratio", "rs_momentum", "heat_score", "ret_5d", "ret_20d",
    "ret_60d", "excess_20d", "pct_vs_ma50", "pct_vs_ma200", "rvol",
    "pct_from_52w_high", "leader_rank", "improving_rank", "spy_price",
    "vix_level",
}
VALIDATION_SUMMARY_COLUMNS = [
    "source_file", "signal_source", "as_of_date", "generated_at", "module",
    "lane_id", "entries_accumulated", "price_resolvable", "dropped_count",
    "dropped_pct", "min_resolved_across_tiers", "min_resolved_for_verdict",
    "verdict", "validation_status", "mature", "resolved", "matured",
    "invalid_count", "reject_count", "benchmark", "theta_dir",
    "survivorship_free", "forward_universe", "validated_universe",
    "universe_match", "membership_snapshot_through",
    "cost_assumption_round_trip", "verdict_by_tier_json", "by_tier_json",
    "buckets_json", "survivorship_json", "sp500_pit_cohort_json",
    "ev_caveats_json", "note", "raw_summary_json",
]
VALIDATION_SUMMARY_STRING_COLUMNS = {
    "source_file", "signal_source", "as_of_date", "generated_at", "module",
    "lane_id", "verdict", "validation_status", "benchmark", "theta_dir",
    "forward_universe", "validated_universe", "membership_snapshot_through",
    "verdict_by_tier_json", "by_tier_json", "buckets_json",
    "survivorship_json", "sp500_pit_cohort_json", "ev_caveats_json", "note",
    "raw_summary_json",
}
VALIDATION_SUMMARY_BOOL_COLUMNS = {
    "mature", "survivorship_free", "universe_match",
}
VALIDATION_SUMMARY_NUMBER_COLUMNS = {
    "entries_accumulated", "price_resolvable", "dropped_count",
    "dropped_pct", "min_resolved_across_tiers", "min_resolved_for_verdict",
    "resolved", "matured", "invalid_count", "reject_count",
    "cost_assumption_round_trip",
}
DAILY_REPORT_COLUMNS = [
    "source_file", "report_date", "generated_at", "total_confirmed",
    "ranked_picks_count", "top_tickers_json", "regime_summary",
    "cross_candidate_commentary", "portfolio_notes", "ranked_picks_json",
    "raw_report_json",
]
DAILY_REPORT_STRING_COLUMNS = {
    "source_file", "report_date", "generated_at", "top_tickers_json",
    "regime_summary", "cross_candidate_commentary", "portfolio_notes",
    "ranked_picks_json", "raw_report_json",
}
DAILY_REPORT_NUMBER_COLUMNS = {"total_confirmed", "ranked_picks_count"}
WATCHLIST_SOURCE_COLUMNS = [
    "source_file", "source_group", "source_label", "scan_date",
    "generated_at", "ticker", "source_rank", "tv_symbol", "exchange",
    "location", "scan_kinds_json", "in_static_universe",
    "source_scans_json", "raw_entry_json",
]
WATCHLIST_SOURCE_STRING_COLUMNS = {
    "source_file", "source_group", "source_label", "scan_date",
    "generated_at", "ticker", "tv_symbol", "exchange", "location",
    "scan_kinds_json", "source_scans_json", "raw_entry_json",
}
WATCHLIST_SOURCE_BOOL_COLUMNS = {"in_static_universe"}
WATCHLIST_SOURCE_NUMBER_COLUMNS = {"source_rank"}
SOURCE_OBSERVATION_COLUMNS = [
    "source_id", "source_file", "availability", "source_date",
    "generated_at", "reachable", "record_count",
]
SOURCE_OBSERVATION_STRING_COLUMNS = {
    "source_id", "source_file", "availability", "source_date", "generated_at",
}
SOURCE_OBSERVATION_BOOL_COLUMNS = {"reachable"}
SOURCE_OBSERVATION_NUMBER_COLUMNS = {"record_count"}
SIGNAL_OUTCOME_COLUMNS = [
    "source_file", "signal_source", "as_of_date", "generated_at", "tier",
    "target_return_pct", "horizon_days", "resolved", "hits", "hit_rate",
    "wilson90_low", "wilson90_high", "mature", "verdict",
    "min_resolved_for_verdict", "ev_horizon", "median_horizon",
    "win_rate_horizon", "ev_excess_vs_spy", "excess_n",
    "excess_win_rate", "ev_excess_beta_adj", "raw_outcome_json",
]
RUN_STATUS_HISTORY_COLUMNS = [
    "source_file", "line_number", "run_id", "job", "status", "started_at",
    "finished_at", "updated_at", "duration_seconds", "stage_id",
    "stage_label", "stage_status", "stage_progress_pct", "stage_message",
    "rank_source_candidates", "rank_limit", "ranked_candidates",
    "options_gate_requested", "options_gate_checked", "options_usable",
    "options_watch", "options_unusable", "options_unknown",
    "scored_candidates", "remaining_candidates", "errored_candidates",
    "deferred_candidates", "needs_layer2_count", "watchlist_count",
    "rejected_count", "passed_hard_filters", "rejected", "total_tickers",
    "downloaded_tickers", "current_coverage", "data_available",
    "total_batches", "completed_batches", "candidate_limit", "scoring_mode",
    "warnings_count", "errors_count", "outputs_json", "metrics_json",
    "warnings_json", "errors_json", "raw_run_json",
]
SECURITY_MASTER_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "name",
    "exchange", "asset_type", "currency", "is_active", "cik",
    "eastmoney_secid", "sources_json", "raw_security_json",
]
SECURITY_MASTER_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "name",
    "exchange", "asset_type", "currency", "cik", "eastmoney_secid",
    "sources_json", "raw_security_json",
}
SECURITY_MASTER_BOOL_COLUMNS = {"is_active"}
SECURITY_IDENTIFIER_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "provider",
    "provider_symbol", "secid", "cik", "exchange_code", "source",
    "raw_identifier_json",
]
SECURITY_IDENTIFIER_STRING_COLUMNS = set(SECURITY_IDENTIFIER_COLUMNS)
UNIVERSE_SNAPSHOT_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "name",
    "exchange", "asset_type", "currency", "is_active", "eastmoney_secid",
    "cik", "eastmoney_total", "security_count", "sec_mapped",
    "missing_cik", "sources_json", "markets_json", "raw_security_json",
]
UNIVERSE_SNAPSHOT_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "name",
    "exchange", "asset_type", "currency", "eastmoney_secid", "cik",
    "sources_json", "markets_json", "raw_security_json",
}
UNIVERSE_SNAPSHOT_BOOL_COLUMNS = {"is_active"}
UNIVERSE_SNAPSHOT_NUMBER_COLUMNS = {
    "eastmoney_total", "security_count", "sec_mapped", "missing_cik",
}
DAILY_BAR_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "bar_date",
    "open", "high", "low", "close", "adj_close", "volume", "source",
    "is_adjusted", "source_priority", "data_quality_status", "raw_bar_json",
]
DAILY_BAR_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "bar_date",
    "source", "data_quality_status", "raw_bar_json",
}
DAILY_BAR_BOOL_COLUMNS = {"is_adjusted"}
DAILY_BAR_NUMBER_COLUMNS = {
    "open", "high", "low", "close", "adj_close", "volume", "source_priority",
}
DAILY_MONEY_FLOW_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "secid",
    "flow_date", "close", "change_pct", "main_net", "main_pct",
    "super_big_net", "big_net", "mid_net", "small_net", "source",
    "publishable", "requested", "resolved", "unavailable", "coverage_ratio",
    "raw_row_json",
]
DAILY_MONEY_FLOW_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "secid",
    "flow_date", "source", "raw_row_json",
}
DAILY_MONEY_FLOW_BOOL_COLUMNS = {"publishable"}
DAILY_MONEY_FLOW_NUMBER_COLUMNS = {
    "close", "change_pct", "main_net", "main_pct", "super_big_net",
    "big_net", "mid_net", "small_net", "requested", "resolved",
    "unavailable", "coverage_ratio",
}
TRADE_STATE_SNAPSHOT_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "price",
    "cycle", "cycle_source", "ce_trend", "ce_source", "verdict",
    "risk_level", "industry_role", "industry_role_status",
    "main_net_latest", "main_pct_latest", "atr_pct", "options_flow_score",
    "social_mentions", "reasons_json", "data_sources_json", "raw_row_json",
]
TRADE_STATE_SNAPSHOT_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "cycle",
    "cycle_source", "ce_trend", "ce_source", "verdict", "risk_level",
    "industry_role", "industry_role_status", "reasons_json",
    "data_sources_json", "raw_row_json",
}
TRADE_STATE_SNAPSHOT_NUMBER_COLUMNS = {
    "price", "main_net_latest", "main_pct_latest", "atr_pct",
    "options_flow_score", "social_mentions",
}
FUNDAMENTAL_METRIC_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker", "cik",
    "period_end", "fiscal_year", "fiscal_period", "form", "filed_at",
    "metric", "label", "value", "unit", "source", "confidence",
    "source_conflict", "conflict_json", "raw_metric_json",
]
FUNDAMENTAL_METRIC_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker", "cik",
    "period_end", "fiscal_period", "form", "filed_at", "metric", "label",
    "unit", "source", "conflict_json", "raw_metric_json",
}
FUNDAMENTAL_METRIC_BOOL_COLUMNS = {"source_conflict"}
FUNDAMENTAL_METRIC_NUMBER_COLUMNS = {"fiscal_year", "value", "confidence"}
INDUSTRY_ROLE_ASSIGNMENT_COLUMNS = [
    "source_file", "as_of_date", "generated_at", "ticker",
    "primary_role_id", "primary_role_name", "secondary_role_ids_json",
    "status", "confidence", "source", "evidence_json", "reviewed_at",
    "taxonomy_version",
]
INDUSTRY_ROLE_ASSIGNMENT_STRING_COLUMNS = {
    "source_file", "as_of_date", "generated_at", "ticker",
    "primary_role_id", "primary_role_name", "secondary_role_ids_json",
    "status", "source", "evidence_json", "reviewed_at",
}
INDUSTRY_ROLE_ASSIGNMENT_NUMBER_COLUMNS = {"confidence", "taxonomy_version"}
KNOWN_TABLES = {
    "security_master": "security_master.parquet",
    "security_identifiers": "security_identifiers.parquet",
    "universe_snapshots": "universe_snapshots.parquet",
    "daily_bars": "daily_bars.parquet",
    "daily_money_flow": "daily_money_flow.parquet",
    "performance_ledger": "performance_ledger.parquet",
    "iv_history": "iv_history.parquet",
    "options_flow_signals": "options_flow_signals.parquet",
    "reversal_radar_signals": "reversal_radar_signals.parquet",
    "oversold_reversal_signals": "oversold_reversal_signals.parquet",
    "market_thesis_forecasts": "market_thesis_forecasts.parquet",
    "candidate_scores": "candidate_scores.parquet",
    "candidate_rankings": "candidate_rankings.parquet",
    "candidate_outcomes": "candidate_outcomes.parquet",
    "risk_guard_rows": "risk_guard_rows.parquet",
    "portfolio_positions": "portfolio_positions.parquet",
    "trade_state_snapshots": "trade_state_snapshots.parquet",
    "fundamental_metrics": "fundamental_metrics.parquet",
    "industry_role_assignments": "industry_role_assignments.parquet",
    "theme_flow_snapshots": "theme_flow_snapshots.parquet",
    "sector_rotation_snapshots": "sector_rotation_snapshots.parquet",
    "validation_summaries": "validation_summaries.parquet",
    "daily_reports": "daily_reports.parquet",
    "watchlist_sources": "watchlist_sources.parquet",
    "source_observations": "source_observations.parquet",
    "signal_outcomes": "signal_outcomes.parquet",
    "run_status_history": "run_status_history.parquet",
}
_DATED_JSON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
_DATED_PARQUET_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.parquet$")
_DAILY_REPORT_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SCAN_JSON_RE = re.compile(r"^scan_\d{4}-\d{2}-\d{2}\.json$")
_FORECAST_JSON_RE = re.compile(r"^(?:regime_only_)?forecast_\d{4}-\d{2}-\d{2}\.json$")
_TIER_RE = re.compile(r"^\+(\d+(?:\.\d+)?)%/(\d+)d$")
MAX_UI_ROWS = 5000


def analytics_dir(analytics_root: str | Path | None = None) -> Path:
    """Resolve the analytics data root.

    Local runs default to reports/analytics. Deployed runs can set
    SURGE_ANALYTICS_DIR directly, or use SURGE_APP_ROOT so the store lands under
    the deployment's shared data directory.
    """
    if analytics_root is not None:
        return Path(analytics_root).expanduser().resolve()
    if os.environ.get("SURGE_ANALYTICS_DIR"):
        return Path(os.environ["SURGE_ANALYTICS_DIR"]).expanduser().resolve()
    if os.environ.get("SURGE_APP_ROOT"):
        return (Path(os.environ["SURGE_APP_ROOT"]).expanduser() / "shared" / "data").resolve()
    return (REPORTS_DIR / "analytics").resolve()


def parquet_dir(analytics_root: str | Path | None = None) -> Path:
    return analytics_dir(analytics_root) / "parquet"


def duckdb_path(analytics_root: str | Path | None = None) -> Path:
    return analytics_dir(analytics_root) / "analytics.duckdb"


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _sql_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _clamp_limit(limit: int | str | None, *, default: int = 500) -> int:
    try:
        n = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, MAX_UI_ROWS))


def _readonly_connect(analytics_root: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(duckdb_path(analytics_root)), read_only=True)


def _known_table(table_name: str) -> str:
    table = str(table_name or "").strip()
    if table not in KNOWN_TABLES:
        raise ValueError(f"Unknown analytics table: {table_name}")
    return table


def _write_parquet(df: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, out)


def _json_blob(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _metric(metrics: dict[str, Any], key: str) -> Any:
    return metrics.get(key) if isinstance(metrics, dict) else None


def _json_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _duration_seconds(started_at: Any, finished_at: Any) -> int | None:
    start = pd.to_datetime(started_at, errors="coerce", utc=True)
    finish = pd.to_datetime(finished_at, errors="coerce", utc=True)
    if pd.isna(start) or pd.isna(finish):
        return None
    seconds = (finish - start).total_seconds()
    if seconds != seconds:
        return None
    return int(round(float(seconds)))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _as_date_from_generated(data: dict[str, Any], fallback: str = "") -> str:
    for key in ("as_of_date", "as_of", "scan_date"):
        if data.get(key):
            return str(data.get(key))[:10]
    generated = str(data.get("generated_at") or "")
    if generated:
        return generated[:10]
    return fallback


def _file_mtime_date(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except OSError:
        return ""


def _file_mtime_utc(path: Path) -> str:
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.match(r"^\d{8}$", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _tier_parts(label: str) -> tuple[float | None, int | None]:
    match = _TIER_RE.match(str(label or ""))
    if not match:
        return (None, None)
    return (float(match.group(1)), int(match.group(2)))


def _json_files(src_dir: Path, pattern: re.Pattern[str]) -> list[Path]:
    if not src_dir.is_dir():
        return []
    return sorted(p for p in src_dir.glob("*.json") if pattern.match(p.name))


def _daily_report_files(reports: Path) -> list[Path]:
    if not reports.is_dir():
        return []
    return sorted(
        path / "summary.json"
        for path in reports.iterdir()
        if path.is_dir()
        and _DAILY_REPORT_DIR_RE.match(path.name)
        and (path / "summary.json").is_file()
    )


def _top_tickers(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    tickers: list[str] = []
    for item in items:
        ticker = item.get("ticker") if isinstance(item, dict) else item
        normalized = str(ticker or "").upper().strip().removeprefix("$")
        if normalized and normalized not in tickers:
            tickers.append(normalized)
    return tickers


def _daily_report_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=DAILY_REPORT_COLUMNS)
    for col in DAILY_REPORT_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in DAILY_REPORT_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _parse_watchlist_text(text: str) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for token in re.split(r"[\n,]+", text or ""):
        token = token.strip()
        if not token or token.startswith("#"):
            continue
        raw = token.upper().lstrip("$")
        parts = raw.split(":", 1)
        exchange = parts[0] if len(parts) == 2 else None
        ticker = "".join(c for c in parts[-1] if c.isalnum() or c == ".")
        if not ticker:
            continue
        out.setdefault(ticker, {
            "ticker": ticker,
            "tv_symbol": raw,
            "exchange": exchange,
        })
    return list(out.values())


def _watchlist_source_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=WATCHLIST_SOURCE_COLUMNS)
    for col in WATCHLIST_SOURCE_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in WATCHLIST_SOURCE_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in WATCHLIST_SOURCE_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _source_observation_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=SOURCE_OBSERVATION_COLUMNS)
    for col in SOURCE_OBSERVATION_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in SOURCE_OBSERVATION_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in SOURCE_OBSERVATION_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _security_master_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=SECURITY_MASTER_COLUMNS)
    for col in SECURITY_MASTER_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in SECURITY_MASTER_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    return df


def _security_identifier_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=SECURITY_IDENTIFIER_COLUMNS)
    for col in SECURITY_IDENTIFIER_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    return df


def _universe_snapshot_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=UNIVERSE_SNAPSHOT_COLUMNS)
    for col in UNIVERSE_SNAPSHOT_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in UNIVERSE_SNAPSHOT_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in UNIVERSE_SNAPSHOT_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _universe_dir(source: str | Path) -> Path:
    path = Path(source)
    return path / "universe" if (path / "universe").is_dir() else path


def _universe_files(source: str | Path) -> list[Path]:
    return _json_files(_universe_dir(source), _DATED_JSON_RE)


def _latest_universe_file(files: list[Path]) -> Path | None:
    if not files:
        return None
    return sorted(files, key=lambda p: p.stem)[-1]


def _universe_security_base(path: Path, data: dict[str, Any], security: dict[str, Any]) -> dict[str, Any]:
    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
    return {
        "source_file": path.name,
        "as_of_date": str(data.get("as_of_date") or path.stem),
        "generated_at": data.get("generated_at"),
        "ticker": str(security.get("ticker") or "").upper(),
        "name": security.get("name"),
        "exchange": security.get("exchange"),
        "asset_type": security.get("asset_type"),
        "currency": security.get("currency"),
        "is_active": security.get("is_active"),
        "eastmoney_secid": security.get("eastmoney_secid"),
        "cik": security.get("cik"),
        "eastmoney_total": coverage.get("eastmoney_total"),
        "security_count": coverage.get("security_count"),
        "sec_mapped": coverage.get("sec_mapped"),
        "missing_cik": coverage.get("missing_cik"),
        "sources_json": _json_blob(data.get("sources")),
        "markets_json": _json_blob(data.get("markets")),
        "raw_security_json": _json_blob(security),
    }


def export_universe_snapshots(
    reports_or_universe_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/universe/YYYY-MM-DD.json into security/universe tables."""
    files = _universe_files(reports_or_universe_dir)
    latest = _latest_universe_file(files)
    snapshot_rows: list[dict[str, Any]] = []
    master_rows: list[dict[str, Any]] = []
    identifier_rows: list[dict[str, Any]] = []

    for path in files:
        data = _load_json(path)
        if not data:
            continue
        securities = data.get("securities") if isinstance(data.get("securities"), list) else []
        for security in securities:
            if not isinstance(security, dict):
                continue
            base = _universe_security_base(path, data, security)
            if not base["ticker"]:
                continue
            snapshot_rows.append(base)
            if latest and path == latest:
                master_rows.append({k: base.get(k) for k in SECURITY_MASTER_COLUMNS})
                if security.get("eastmoney_secid"):
                    secid = str(security.get("eastmoney_secid"))
                    identifier_rows.append({
                        "source_file": path.name,
                        "as_of_date": base["as_of_date"],
                        "generated_at": base["generated_at"],
                        "ticker": base["ticker"],
                        "provider": "eastmoney",
                        "provider_symbol": base["ticker"],
                        "secid": secid,
                        "cik": None,
                        "exchange_code": secid.split(".", 1)[0] if "." in secid else None,
                        "source": "eastmoney_push2",
                        "raw_identifier_json": _json_blob({"secid": secid}),
                    })
                if security.get("cik"):
                    identifier_rows.append({
                        "source_file": path.name,
                        "as_of_date": base["as_of_date"],
                        "generated_at": base["generated_at"],
                        "ticker": base["ticker"],
                        "provider": "sec",
                        "provider_symbol": base["ticker"],
                        "secid": None,
                        "cik": str(security.get("cik")),
                        "exchange_code": None,
                        "source": "sec_company_tickers",
                        "raw_identifier_json": _json_blob({"cik": security.get("cik")}),
                    })

    master_df = _security_master_frame(master_rows)
    identifiers_df = _security_identifier_frame(identifier_rows)
    snapshots_df = _universe_snapshot_frame(snapshot_rows)

    master_out = parquet_dir(analytics_root) / KNOWN_TABLES["security_master"]
    identifiers_out = parquet_dir(analytics_root) / KNOWN_TABLES["security_identifiers"]
    snapshots_out = parquet_dir(analytics_root) / KNOWN_TABLES["universe_snapshots"]
    _write_parquet(master_df, master_out)
    _write_parquet(identifiers_df, identifiers_out)
    _write_parquet(snapshots_df, snapshots_out)
    if refresh:
        refresh_views(analytics_root)
    return {
        "source": str(_universe_dir(reports_or_universe_dir)),
        "path": str(snapshots_out),
        "rows": int(len(snapshots_df)),
        "security_master_rows": int(len(master_df)),
        "security_identifier_rows": int(len(identifiers_df)),
        "latest_source_file": latest.name if latest else None,
    }


def _daily_bar_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=DAILY_BAR_COLUMNS)
    for col in DAILY_BAR_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in DAILY_BAR_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in DAILY_BAR_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _daily_bars_dir(source: str | Path) -> Path:
    path = Path(source)
    candidate = path / "market_data" / "daily_bars"
    return candidate if candidate.is_dir() else path


def _daily_bar_sources(src_dir: Path) -> list[Path]:
    if not src_dir.is_dir():
        return []
    canonical = src_dir / "canonical.parquet"
    if canonical.is_file():
        return [canonical]
    return [
        path for path in sorted(src_dir.glob("*.parquet"))
        if _DATED_PARQUET_RE.fullmatch(path.name)
    ]


def _daily_bar_projection(available_columns: set[str]) -> str:
    expressions: list[str] = []
    for column in DAILY_BAR_COLUMNS:
        ident = _sql_ident(column)
        if column == "source_file":
            value = "regexp_extract(filename, '[^/]+$')"
            if column in available_columns:
                value = f"coalesce(cast({ident} as varchar), {value})"
        elif column in DAILY_BAR_STRING_COLUMNS:
            value = (
                f"cast({ident} as varchar)"
                if column in available_columns else "cast(null as varchar)"
            )
        elif column in DAILY_BAR_BOOL_COLUMNS:
            value = (
                f"try_cast({ident} as boolean)"
                if column in available_columns else "cast(null as boolean)"
            )
        else:
            value = (
                f"try_cast({ident} as double)"
                if column in available_columns else "cast(null as double)"
            )
        expressions.append(f"{value} as {ident}")
    return ",\n                ".join(expressions)


def _validate_daily_bars_export(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    *,
    expected_rows: int,
    expected_latest_bar_date: date | None,
) -> int:
    schema = con.execute(
        "describe select * from read_parquet(?)", [str(path)]
    ).fetchall()
    if [str(row[0]) for row in schema] != DAILY_BAR_COLUMNS:
        raise ValueError("daily-bars export schema mismatch")
    row = con.execute(
        """
        select
            count(*) as row_count,
            count(*) - count(distinct (ticker, bar_date)) as duplicate_count,
            count(*) filter (where ticker is null or bar_date is null) as missing_keys,
            max(try_cast(bar_date as date)) as latest_bar_date
        from read_parquet(?)
        """,
        [str(path)],
    ).fetchone()
    row_count = int(row[0])
    if row_count != expected_rows:
        raise ValueError("daily-bars export row count mismatch")
    if int(row[1]) or int(row[2]):
        raise ValueError("daily-bars export contains invalid or duplicate keys")
    if row[3] != expected_latest_bar_date:
        raise ValueError("daily-bars export freshness mismatch")
    return row_count


def _export_daily_bars_with_duckdb(
    source_paths: list[Path],
    out: Path,
) -> int:
    source_list = ", ".join(
        f"'{_sql_path(path.resolve())}'" for path in source_paths
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".daily-bars-", dir=out.parent) as temp_root:
        temp_dir = Path(temp_root)
        spill_dir = temp_dir / "spill"
        spill_dir.mkdir()
        temp_out = temp_dir / out.name
        con = duckdb.connect()
        try:
            con.execute("set memory_limit = '4GiB'")
            con.execute("set preserve_insertion_order = false")
            con.execute(f"set temp_directory = '{_sql_path(spill_dir)}'")
            source_schema = con.execute(
                f"describe select * from read_parquet("
                f"[{source_list}], union_by_name = true)"
            ).fetchall()
            available_columns = {str(row[0]) for row in source_schema}
            if not {"ticker", "bar_date"}.issubset(available_columns):
                raise ValueError("daily-bars source is missing key columns")
            as_of_order = (
                "try_cast(as_of_date as date)" if "as_of_date" in available_columns
                else "cast(null as date)"
            )
            generated_order = (
                "try_cast(generated_at as timestamptz)"
                if "generated_at" in available_columns
                else "cast(null as timestamptz)"
            )
            priority_order = (
                "try_cast(source_priority as double)"
                if "source_priority" in available_columns
                else "cast(null as double)"
            )
            source_file_order = "regexp_extract(filename, '[^/]+$')"
            if "source_file" in available_columns:
                source_file_order = (
                    "coalesce(cast(source_file as varchar), "
                    f"{source_file_order})"
                )
            source_stats = con.execute(
                f"""
                select
                    count(distinct (cast(ticker as varchar), cast(bar_date as varchar))),
                    max(try_cast(bar_date as date)),
                    count(*) filter (where ticker is null or bar_date is null)
                from read_parquet([{source_list}], union_by_name = true)
                """
            ).fetchone()
            if int(source_stats[2]):
                raise ValueError("daily-bars source contains missing keys")
            con.execute(
                f"""
                copy (
                    with normalized as (
                        select
                            {_daily_bar_projection(available_columns)},
                            row_number() over (
                                partition by cast(ticker as varchar), cast(bar_date as varchar)
                                order by
                                    {as_of_order} desc nulls last,
                                    {generated_order} desc nulls last,
                                    {priority_order} asc nulls last,
                                    {source_file_order} desc nulls last
                            ) as version_rank
                        from read_parquet(
                            [{source_list}], union_by_name = true, filename = true
                        )
                    )
                    select {', '.join(_sql_ident(column) for column in DAILY_BAR_COLUMNS)}
                    from normalized
                    where version_rank = 1
                    order by ticker, bar_date
                ) to '{_sql_path(temp_out)}' (format parquet, compression zstd)
                """
            )
            rows = _validate_daily_bars_export(
                con,
                temp_out,
                expected_rows=int(source_stats[0]),
                expected_latest_bar_date=source_stats[1],
            )
            os.replace(temp_out, out)
            return rows
        except Exception:
            raise RuntimeError("daily-bars export failed") from None
        finally:
            con.close()


def export_daily_bars(
    reports_or_bars_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export a bounded, deterministic daily-bars table for Analytics."""
    src_dir = _daily_bars_dir(reports_or_bars_dir)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["daily_bars"]
    source_paths = _daily_bar_sources(src_dir)
    if source_paths:
        row_count = _export_daily_bars_with_duckdb(source_paths, out)
    else:
        out_df = _daily_bar_frame([])
        _write_parquet(out_df, out)
        row_count = 0
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": row_count}


def _daily_money_flow_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=DAILY_MONEY_FLOW_COLUMNS)
    for col in DAILY_MONEY_FLOW_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in DAILY_MONEY_FLOW_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in DAILY_MONEY_FLOW_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _money_flow_dir(source: str | Path) -> Path:
    path = Path(source)
    candidate = path / "money_flow"
    return candidate if candidate.is_dir() else path


def export_daily_money_flow(
    reports_or_money_flow_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/money_flow/YYYY-MM-DD.json into daily_money_flow."""
    src_dir = _money_flow_dir(reports_or_money_flow_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data:
            continue
        coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
        publishable = bool(data.get("publishable"))
        money_rows = data.get("rows") if isinstance(data.get("rows"), list) else []
        for row in money_rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": str(data.get("as_of_date") or path.stem),
                "generated_at": data.get("generated_at"),
                "ticker": ticker,
                "secid": row.get("secid"),
                "flow_date": row.get("date") or row.get("flow_date"),
                "close": row.get("close"),
                "change_pct": row.get("change_pct"),
                "main_net": row.get("main_net"),
                "main_pct": row.get("main_pct"),
                "super_big_net": row.get("super_big_net"),
                "big_net": row.get("big_net"),
                "mid_net": row.get("mid_net"),
                "small_net": row.get("small_net"),
                "source": row.get("source") or data.get("source"),
                "publishable": publishable,
                "requested": coverage.get("requested"),
                "resolved": coverage.get("resolved"),
                "unavailable": coverage.get("unavailable"),
                "coverage_ratio": coverage.get("coverage_ratio"),
                "raw_row_json": _json_blob(row),
            })

    out_df = _daily_money_flow_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["daily_money_flow"]
    _write_parquet(out_df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(out_df))}


def _trade_state_snapshot_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=TRADE_STATE_SNAPSHOT_COLUMNS)
    for col in TRADE_STATE_SNAPSHOT_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in TRADE_STATE_SNAPSHOT_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _trade_state_dir(source: str | Path) -> Path:
    path = Path(source)
    candidate = path / "trade_state"
    return candidate if candidate.is_dir() else path


def export_trade_state_snapshots(
    reports_or_trade_state_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/trade_state/YYYY-MM-DD.json into trade_state_snapshots."""
    src_dir = _trade_state_dir(reports_or_trade_state_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data:
            continue
        as_of = str(data.get("as_of_date") or path.stem)
        generated_at = data.get("generated_at")
        for row in data.get("rows") if isinstance(data.get("rows"), list) else []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": str(row.get("as_of_date") or as_of),
                "generated_at": generated_at,
                "ticker": ticker,
                "price": row.get("price"),
                "cycle": row.get("cycle"),
                "cycle_source": row.get("cycle_source"),
                "ce_trend": row.get("ce_trend"),
                "ce_source": row.get("ce_source"),
                "verdict": row.get("verdict"),
                "risk_level": row.get("risk_level"),
                "industry_role": row.get("industry_role"),
                "industry_role_status": row.get("industry_role_status"),
                "main_net_latest": row.get("main_net_latest"),
                "main_pct_latest": row.get("main_pct_latest"),
                "atr_pct": row.get("atr_pct"),
                "options_flow_score": row.get("options_flow_score"),
                "social_mentions": row.get("social_mentions"),
                "reasons_json": row.get("reasons_json"),
                "data_sources_json": row.get("data_sources_json"),
                "raw_row_json": row.get("raw_row_json") or _json_blob(row),
            })

    out_df = _trade_state_snapshot_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["trade_state_snapshots"]
    _write_parquet(out_df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(out_df))}


def _fundamental_metric_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=FUNDAMENTAL_METRIC_COLUMNS)
    for col in FUNDAMENTAL_METRIC_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in FUNDAMENTAL_METRIC_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in FUNDAMENTAL_METRIC_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _fundamentals_dir(source: str | Path) -> Path:
    path = Path(source)
    candidate = path / "fundamentals"
    return candidate if candidate.is_dir() else path


def export_fundamental_metrics(
    reports_or_fundamentals_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/fundamentals/YYYY-MM-DD.json into fundamental_metrics."""
    src_dir = _fundamentals_dir(reports_or_fundamentals_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data:
            continue
        as_of = str(data.get("as_of_date") or path.stem)
        generated_at = data.get("generated_at")
        for row in data.get("rows") if isinstance(data.get("rows"), list) else []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            metric = str(row.get("metric") or "").strip()
            if not ticker or not metric:
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": str(row.get("as_of_date") or as_of),
                "generated_at": generated_at,
                "ticker": ticker,
                "cik": row.get("cik"),
                "period_end": row.get("period_end"),
                "fiscal_year": row.get("fiscal_year"),
                "fiscal_period": row.get("fiscal_period"),
                "form": row.get("form"),
                "filed_at": row.get("filed_at"),
                "metric": metric,
                "label": row.get("label"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "source": row.get("source"),
                "confidence": row.get("confidence"),
                "source_conflict": row.get("source_conflict"),
                "conflict_json": row.get("conflict_json"),
                "raw_metric_json": row.get("raw_metric_json") or _json_blob(row),
            })

    out_df = _fundamental_metric_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["fundamental_metrics"]
    _write_parquet(out_df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(out_df))}


def _industry_role_assignment_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=INDUSTRY_ROLE_ASSIGNMENT_COLUMNS)
    for col in INDUSTRY_ROLE_ASSIGNMENT_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in INDUSTRY_ROLE_ASSIGNMENT_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _industry_roles_dir(source: str | Path) -> Path:
    path = Path(source)
    candidate = path / "industry_roles"
    return candidate if candidate.is_dir() else path


def export_industry_role_assignments(
    reports_or_industry_roles_dir: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/industry_roles/YYYY-MM-DD.json into industry_role_assignments."""
    src_dir = _industry_roles_dir(reports_or_industry_roles_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data:
            continue
        as_of = str(data.get("as_of_date") or path.stem)
        generated_at = data.get("generated_at")
        for row in data.get("rows") if isinstance(data.get("rows"), list) else []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            role_id = str(row.get("primary_role_id") or "").strip()
            if not ticker or not role_id:
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": str(row.get("as_of_date") or as_of),
                "generated_at": generated_at,
                "ticker": ticker,
                "primary_role_id": role_id,
                "primary_role_name": row.get("primary_role_name"),
                "secondary_role_ids_json": row.get("secondary_role_ids_json"),
                "status": row.get("status"),
                "confidence": row.get("confidence"),
                "source": row.get("source"),
                "evidence_json": row.get("evidence_json"),
                "reviewed_at": row.get("reviewed_at"),
                "taxonomy_version": row.get("taxonomy_version"),
            })

    out_df = _industry_role_assignment_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["industry_role_assignments"]
    _write_parquet(out_df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(out_df))}


def export_performance_ledger(
    csv_path: str | Path = REPORTS_DIR / "performance_ledger.csv",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export reports/performance_ledger.csv to Parquet and refresh tables."""
    src = Path(csv_path)
    if src.is_file():
        df = pd.read_csv(src)
    else:
        df = pd.DataFrame(columns=PERFORMANCE_LEDGER_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["performance_ledger"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src), "path": str(out), "rows": int(len(df))}


def export_iv_history(
    iv_dir: str | Path = REPORTS_DIR / "iv_history",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/iv_history/*.json into one Parquet table."""
    src_dir = Path(iv_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(src_dir.glob("*.json")) if src_dir.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("series"), dict):
            continue
        ticker = str(data.get("ticker") or path.stem).upper()
        for day, value in sorted(data["series"].items()):
            try:
                iv = float(value)
            except (TypeError, ValueError):
                continue
            if iv != iv:
                continue
            rows.append({
                "ticker": ticker,
                "as_of_date": str(day),
                "atm_iv": iv,
                "source_file": path.name,
            })
    df = pd.DataFrame(rows, columns=IV_HISTORY_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["iv_history"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_options_flow_signals(
    flow_dir: str | Path = REPORTS_DIR / "options_flow",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/options_flow/YYYY-MM-DD.json signals into one table."""
    src_dir = Path(flow_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data or not isinstance(data.get("signals"), list):
            continue
        as_of = str(data.get("as_of") or path.stem)
        for signal in data["signals"]:
            if not isinstance(signal, dict):
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": as_of,
                "generated_at": data.get("generated_at"),
                "provider": signal.get("provider") or data.get("provider"),
                "min_notional": data.get("min_notional"),
                "universe_size": data.get("universe_size"),
                "signal_count": data.get("signal_count"),
                "ticker": str(signal.get("ticker") or "").upper(),
                "direction": signal.get("direction"),
                "flow_score": signal.get("flow_score"),
                "est_notional_usd": signal.get("est_notional_usd"),
                "expiry": signal.get("expiry"),
                "max_voi": signal.get("max_voi"),
                "high_voi_strikes": signal.get("high_voi_strikes"),
                "call_put_ratio": signal.get("call_put_ratio"),
                "put_call_ratio": signal.get("put_call_ratio"),
                "total_call_vol": signal.get("total_call_vol"),
                "total_put_vol": signal.get("total_put_vol"),
                "otm_call_vol": signal.get("otm_call_vol"),
                "spot": signal.get("spot"),
                "tags_json": _json_blob(signal.get("tags")),
                "biggest_json": _json_blob(signal.get("biggest")),
                "raw_signal_json": _json_blob(signal),
            })
    df = pd.DataFrame(rows, columns=OPTIONS_FLOW_SIGNAL_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["options_flow_signals"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_reversal_radar_signals(
    radar_dir: str | Path = REPORTS_DIR / "reversal_radar",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/reversal_radar/scan_*.json candidates into one table."""
    src_dir = Path(radar_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _SCAN_JSON_RE):
        data = _load_json(path)
        if not data or not isinstance(data.get("candidates"), list):
            continue
        as_of = str(data.get("as_of_date") or path.stem.removeprefix("scan_"))
        for candidate in data["candidates"]:
            if not isinstance(candidate, dict):
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": as_of,
                "generated_at": data.get("generated_at"),
                "universe": data.get("universe"),
                "universe_size": data.get("universe_size"),
                "scanned": data.get("scanned"),
                "match_count": data.get("match_count"),
                "lane_id": data.get("lane_id"),
                "exploratory": data.get("exploratory"),
                "runway_independent": data.get("runway_independent"),
                "ticker": str(candidate.get("ticker") or "").upper(),
                "signal_date": candidate.get("signal_date") or as_of,
                "status": candidate.get("status"),
                "reversal_score": candidate.get("reversal_score"),
                "data_confidence": candidate.get("data_confidence"),
                "structure_score": candidate.get("structure_score"),
                "momentum_score": candidate.get("momentum_score"),
                "options_score": candidate.get("options_score"),
                "sector_score": candidate.get("sector_score"),
                "insider_score": candidate.get("insider_score"),
                "analyst_score": candidate.get("analyst_score"),
                "primary_signals_json": _json_blob(candidate.get("primary_signals")),
                "data_gaps_json": _json_blob(candidate.get("data_gaps")),
                "lead_vs_confirm_json": _json_blob(candidate.get("lead_vs_confirm")),
                "structure_json": _json_blob(candidate.get("structure")),
                "momentum_json": _json_blob(candidate.get("momentum")),
                "options_json": _json_blob(candidate.get("options")),
                "sector_json": _json_blob(candidate.get("sector")),
                "insider_json": _json_blob(candidate.get("insider")),
                "analyst_json": _json_blob(candidate.get("analyst")),
                "pullback_json": _json_blob(candidate.get("pullback")),
                "raw_candidate_json": _json_blob(candidate),
            })
    df = pd.DataFrame(rows, columns=REVERSAL_RADAR_SIGNAL_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["reversal_radar_signals"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_oversold_reversal_signals(
    oversold_dir: str | Path = REPORTS_DIR / "oversold_reversal",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/oversold_reversal/scan_*.json candidates into one table."""
    src_dir = Path(oversold_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _SCAN_JSON_RE):
        data = _load_json(path)
        if not data or not isinstance(data.get("candidates"), list):
            continue
        as_of = str(data.get("as_of_date") or path.stem.removeprefix("scan_"))
        for candidate in data["candidates"]:
            if not isinstance(candidate, dict):
                continue
            rows.append({
                "source_file": path.name,
                "as_of_date": as_of,
                "generated_at": data.get("generated_at"),
                "universe": data.get("universe"),
                "scanned": data.get("scanned"),
                "attempted": data.get("attempted"),
                "match_count": data.get("match_count"),
                "lane_id": data.get("lane_id"),
                "exploratory": data.get("exploratory"),
                "runway_independent": data.get("runway_independent"),
                "fetch_failed_json": _json_blob(data.get("fetch_failed")),
                "ticker": str(candidate.get("ticker") or "").upper(),
                "signal_date": candidate.get("signal_date") or candidate.get("as_of") or as_of,
                "avg_dollar_vol_m": candidate.get("avg_dollar_vol_m"),
                "last_price": candidate.get("last_price"),
                "rsi14": candidate.get("rsi14"),
                "bb_width_pct": candidate.get("bb_width_pct"),
                "ma200": candidate.get("ma200"),
                "pct_vs_ma200": candidate.get("pct_vs_ma200"),
                "pct_from_52w_high": candidate.get("pct_from_52w_high"),
                "raw_candidate_json": _json_blob(candidate),
            })
    df = pd.DataFrame(rows, columns=OVERSOLD_REVERSAL_SIGNAL_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["oversold_reversal_signals"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_market_thesis_forecasts(
    thesis_dir: str | Path = REPORTS_DIR / "market_thesis",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/market_thesis/*forecast_YYYY-MM-DD.json into one table."""
    src_dir = Path(thesis_dir)
    rows: list[dict[str, Any]] = []
    for path in _json_files(src_dir, _FORECAST_JSON_RE):
        data = _load_json(path)
        if not data:
            continue
        rows.append({
            "source_file": path.name,
            "as_of_date": str(data.get("as_of") or path.stem.rsplit("_", 1)[-1]),
            "generated_at": data.get("generated_at"),
            "tier": data.get("tier"),
            "method": data.get("method"),
            "benchmark": data.get("benchmark"),
            "direction": data.get("direction"),
            "bucket": data.get("bucket"),
            "support_class": data.get("support_class"),
            "manifest_status": data.get("manifest_status"),
            "regime": data.get("regime"),
            "vix_bucket": data.get("vix_bucket"),
            "label": data.get("label"),
            "rationale_json": _json_blob(data.get("rationale")),
            "raw_forecast_json": _json_blob(data),
        })
    df = pd.DataFrame(rows, columns=MARKET_THESIS_FORECAST_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["market_thesis_forecasts"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_candidate_scores(
    scores_dir: str | Path = REPORTS_DIR / "candidate_scores",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/candidate_scores/YYYY-MM-DD.json scored candidates."""
    src_dir = Path(scores_dir)
    rows: list[dict[str, Any]] = []

    def append_rows(path: Path, *, source_file: str) -> str | None:
        data = _load_json(path)
        if not data or not isinstance(data.get("all_scored"), list):
            return None
        candidates = [row for row in data["all_scored"] if isinstance(row, dict)]
        if data.get("remaining_unscored") != 0 or not candidates:
            return None
        cohort_type = data.get("cohort_type")
        if cohort_type is None:
            provenance = {
                "cohort_type": "legacy_unknown",
                "ranked_universe_count": None,
                "scored_cohort_count": len(candidates),
                "selection_method": "unknown",
                "rank_limit": None,
                "ranking_model": data.get("ranking_model"),
            }
        else:
            universe_count = data.get("ranked_universe_count")
            scored_count = data.get("scored_cohort_count")
            rank_limit = data.get("rank_limit")
            selection_method = data.get("selection_method")
            valid_provenance = (
                cohort_type in {"bounded_top_n", "full_ranked_universe"}
                and type(universe_count) is int
                and type(scored_count) is int
                and type(rank_limit) is int
                and scored_count == len(candidates)
                and universe_count >= scored_count > 0
                and rank_limit >= scored_count
                and selection_method in {"deterministic_top_n", "all_ranked"}
                and (
                    (cohort_type == "bounded_top_n" and universe_count > scored_count)
                    or (cohort_type == "full_ranked_universe" and universe_count == scored_count)
                )
            )
            if not valid_provenance:
                return None
            provenance = {
                "cohort_type": cohort_type,
                "ranked_universe_count": universe_count,
                "scored_cohort_count": scored_count,
                "selection_method": selection_method,
                "rank_limit": rank_limit,
                "ranking_model": data.get("ranking_model"),
            }
        scan_date = str(data.get("scan_date") or path.stem)
        before = len(rows)
        for candidate in candidates:
            scores = candidate.get("scores") if isinstance(candidate.get("scores"), dict) else {}
            technical = (candidate.get("technical_breakdown")
                         if isinstance(candidate.get("technical_breakdown"), dict) else {})
            rows.append({
                "source_file": source_file,
                "scan_date": scan_date,
                "generated_at": data.get("generated_at"),
                **provenance,
                "total_candidates": data.get("total_candidates"),
                "scored_candidates_count": data.get("scored_candidates_count"),
                "remaining_unscored": data.get("remaining_unscored"),
                "needs_layer2_count": data.get("needs_layer2_count"),
                "watchlist_count": data.get("watchlist_count"),
                "min_score_threshold": data.get("min_score_threshold"),
                "ticker": str(candidate.get("ticker") or "").upper(),
                "verdict": candidate.get("verdict"),
                "composite_score": candidate.get("composite_score"),
                "regime_adjusted_score": candidate.get("regime_adjusted_score"),
                "technical": scores.get("technical"),
                "catalyst": scores.get("catalyst"),
                "sentiment": scores.get("sentiment"),
                "institutional": scores.get("institutional"),
                "sector_market": scores.get("sector_market"),
                "options_flow": scores.get("options_flow"),
                "analyst": scores.get("analyst"),
                "pattern_type": technical.get("pattern_type"),
                "scoring_mode": candidate.get("scoring_mode"),
                "due_diligence_required": candidate.get("due_diligence_required"),
                "data_missing_json": _json_blob(candidate.get("data_missing")),
                "raw_candidate_json": _json_blob(candidate),
            })
        return scan_date if len(rows) > before else None

    for path in _json_files(src_dir, _DATED_JSON_RE):
        append_rows(path, source_file=path.name)

    df = pd.DataFrame(rows, columns=CANDIDATE_SCORE_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["candidate_scores"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_candidate_rankings(
    rankings_dir: str | Path = REPORTS_DIR / "candidate_rankings",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/candidate_rankings/YYYY-MM-DD.json ranked candidates."""
    src_dir = Path(rankings_dir)
    rows: list[dict[str, Any]] = []
    seen_snapshot_dates: set[str] = set()

    def append_rows(path: Path, *, source_file: str) -> str | None:
        data = _load_json(path)
        candidates = None
        if data:
            candidates = data.get("ranked_candidates")
            if not isinstance(candidates, list):
                candidates = data.get("tickers")
        if not data or not isinstance(candidates, list):
            return None
        scan_date = str(data.get("scan_date") or data.get("as_of_date") or path.stem)[:10]
        as_of_date = str(data.get("as_of_date") or scan_date)[:10]
        for position, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            components = candidate.get("score_components")
            if not isinstance(components, dict):
                components = {}
            data_quality = candidate.get("data_quality")
            if not isinstance(data_quality, dict):
                data_quality = {}
            options = candidate.get("options_tradability")
            if not isinstance(options, dict):
                options = {}
            rows.append({
                "source_file": source_file,
                "scan_date": scan_date,
                "as_of_date": as_of_date,
                "generated_at": data.get("generated_at"),
                "universe": data.get("universe"),
                "markets": data.get("markets"),
                "source": data.get("source"),
                "scoring_model": data.get("scoring_model"),
                "total_universe": data.get("total_universe"),
                "passed_hard_filters": data.get("passed_hard_filters"),
                "total_candidates": data.get("total_candidates"),
                "all_ranked_count": data.get("all_ranked_count"),
                "rank_limit": data.get("rank_limit"),
                "ranked_candidates_count": data.get("ranked_candidates_count"),
                "rank_position": position,
                "ticker": str(candidate.get("ticker") or "").upper(),
                "rank_score": candidate.get("rank_score"),
                "rank_bucket": candidate.get("rank_bucket"),
                "last_price": candidate.get("last_price"),
                "ma50": candidate.get("ma50"),
                "ma200": candidate.get("ma200"),
                "ret_5d": candidate.get("ret_5d"),
                "ret_20d": candidate.get("ret_20d"),
                "avg_dollar_vol_20d": candidate.get("avg_dollar_vol_20d"),
                "market_cap": candidate.get("market_cap"),
                "macd_current": candidate.get("macd_current"),
                "macd_zero_cross_10d": candidate.get("macd_zero_cross_10d"),
                "macd_golden_cross_10d": candidate.get("macd_golden_cross_10d"),
                "rsi_bullish_divergence": candidate.get("rsi_bullish_divergence"),
                "has_reversal_pattern": candidate.get("has_reversal_pattern"),
                "technical_trend": components.get("technical_trend"),
                "momentum_strength": components.get("momentum_strength"),
                "launch_signal": components.get("launch_signal"),
                "liquidity_tradability": components.get("liquidity_tradability"),
                "overheat_risk_control": components.get("overheat_risk_control"),
                "data_quality_status": data_quality.get("status"),
                "missing_fields_json": _json_blob(data_quality.get("missing_fields")),
                "options_status": options.get("status"),
                "options_momentum_verdict": options.get("momentum_verdict"),
                "options_spread_pct": options.get("spread_pct"),
                "options_open_interest": options.get("open_interest"),
                "options_volume": options.get("volume"),
                "options_iv_percentile": options.get("iv_percentile"),
                "options_iv_percentile_real": options.get("iv_percentile_real"),
                "options_earnings_status": options.get("earnings_status"),
                "options_earnings_days_away": options.get("earnings_days_away"),
                "options_max_call_voi": options.get("max_call_voi"),
                "options_call_put_volume_ratio": options.get("call_put_volume_ratio"),
                "options_total_call_volume": options.get("total_call_volume"),
                "options_total_put_volume": options.get("total_put_volume"),
                "options_flow_score": options.get("flow_score"),
                "options_data_missing_json": _json_blob(options.get("data_missing")),
                "options_warnings_json": _json_blob(options.get("warnings")),
                "warnings_json": _json_blob(candidate.get("warnings")),
                "score_weights_json": _json_blob(data.get("score_weights")),
                "rank_buckets_json": _json_blob(data.get("rank_buckets")),
                "options_gate_json": _json_blob(data.get("options_gate")),
                "score_components_json": _json_blob(components),
                "data_quality_json": _json_blob(data_quality),
                "options_tradability_json": _json_blob(options),
                "raw_candidate_json": _json_blob(candidate),
            })
        return scan_date

    for path in _json_files(src_dir, _DATED_JSON_RE):
        scan_date = append_rows(path, source_file=path.name)
        if scan_date:
            seen_snapshot_dates.add(scan_date)

    latest_path = src_dir.parent.parent / "ranked_candidates.json"
    latest = _load_json(latest_path)
    if latest:
        latest_date = str(latest.get("scan_date") or latest.get("as_of_date") or "")[:10]
        if latest_date and latest_date not in seen_snapshot_dates:
            append_rows(latest_path, source_file=latest_path.name)
    df = pd.DataFrame(rows, columns=CANDIDATE_RANKING_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["candidate_rankings"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def _candidate_outcome_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=CANDIDATE_OUTCOME_COLUMNS)
    for col in CANDIDATE_OUTCOME_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in CANDIDATE_OUTCOME_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in CANDIDATE_OUTCOME_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def export_candidate_outcomes(
    outcomes_dir: str | Path = REPORTS_DIR / "candidate_outcomes",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/candidate_outcomes/YYYY-MM-DD.json paper outcomes."""
    src_dir = Path(outcomes_dir)
    rows: list[dict[str, Any]] = []

    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        outcomes = data.get("outcomes") if data else None
        if not data or not isinstance(outcomes, list):
            continue
        scan_date = str(data.get("scan_date") or path.stem)[:10]
        source_rank_file = data.get("source_rank_file") or data.get("source_file")
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            rows.append({
                "source_file": path.name,
                "scan_date": scan_date,
                "generated_at": data.get("generated_at"),
                "source": data.get("source"),
                "source_rank_file": source_rank_file,
                "rank_limit": data.get("rank_limit"),
                "ticker": str(outcome.get("ticker") or "").upper(),
                "rank_position": outcome.get("rank_position"),
                "rank_score": outcome.get("rank_score"),
                "rank_bucket": outcome.get("rank_bucket"),
                "scoring_model": outcome.get("scoring_model") or data.get("scoring_model"),
                "entry_price": outcome.get("entry_price"),
                "entry_price_date": outcome.get("entry_price_date"),
                "last_verified_at": outcome.get("last_verified_at") or data.get("last_verified_at"),
                "days_elapsed": outcome.get("days_elapsed"),
                "fwd_7d_return": outcome.get("fwd_7d_return"),
                "fwd_14d_return": outcome.get("fwd_14d_return"),
                "fwd_30d_return": outcome.get("fwd_30d_return"),
                "fwd_60d_return": outcome.get("fwd_60d_return"),
                "max_drawdown_30d": outcome.get("max_drawdown_30d"),
                "hit_15pct_within_30d": outcome.get("hit_15pct_within_30d"),
                "hit_30pct_within_60d": outcome.get("hit_30pct_within_60d"),
                "resolved_7d": outcome.get("resolved_7d"),
                "resolved_14d": outcome.get("resolved_14d"),
                "resolved_30d": outcome.get("resolved_30d"),
                "resolved_60d": outcome.get("resolved_60d"),
                "raw_outcome_json": _json_blob(outcome),
            })

    df = _candidate_outcome_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["candidate_outcomes"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def export_risk_guard_rows(
    risk_dir: str | Path = REPORTS_DIR / "risk_guard",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/risk_guard/*.json rows into one risk-action table."""
    src_dir = Path(risk_dir)
    rows: list[dict[str, Any]] = []
    seen_snapshot_dates: set[str] = set()

    def append_rows(path: Path, *, source_file: str) -> str | None:
        data = _load_json(path)
        if not data or not isinstance(data.get("rows"), list):
            return None
        as_of = _as_date_from_generated(data, fallback=path.stem)[:10]
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        for item in data["rows"]:
            if not isinstance(item, dict):
                continue
            technical = item.get("technical") if isinstance(item.get("technical"), dict) else {}
            options = item.get("options") if isinstance(item.get("options"), dict) else {}
            sector = item.get("sector") if isinstance(item.get("sector"), dict) else {}
            position = item.get("position") if isinstance(item.get("position"), dict) else {}
            rows.append({
                "source_file": source_file,
                "as_of_date": as_of,
                "generated_at": data.get("generated_at"),
                "market_status": market.get("status"),
                "market_score_total": market.get("score"),
                "market_reasons_json": _json_blob(market.get("reasons")),
                "market_data_gaps_json": _json_blob(market.get("data_gaps")),
                "summary_count": summary.get("count"),
                "summary_high_risk": summary.get("high_risk"),
                "summary_data_gaps": summary.get("data_gaps"),
                "summary_systemic_gaps": summary.get("systemic_gaps"),
                "data_sources_json": _json_blob(data.get("data_sources")),
                "ticker": str(item.get("ticker") or "").upper(),
                "status": item.get("status"),
                "risk_score": item.get("risk_score"),
                "market_score": item.get("market_score"),
                "price_score": item.get("price_score"),
                "options_score": item.get("options_score"),
                "sector_score": item.get("sector_score"),
                "position_score": item.get("position_score"),
                "cot_score": item.get("cot_score"),
                "data_quality_score": item.get("data_quality_score"),
                "primary_reasons_json": _json_blob(item.get("primary_reasons")),
                "data_gaps_json": _json_blob(item.get("data_gaps")),
                "last_price": technical.get("price"),
                "ma20": technical.get("ma20"),
                "ma50": technical.get("ma50"),
                "ma200": technical.get("ma200"),
                "vwap": technical.get("vwap"),
                "atr14": technical.get("atr14"),
                "rsi14": technical.get("rsi14"),
                "price_above_vwap": technical.get("price_above_vwap"),
                "resistance_20d": technical.get("resistance_20d"),
                "put_call_ratio": options.get("put_call_ratio"),
                "iv_percentile": options.get("iv_percentile"),
                "sector_etf": sector.get("etf"),
                "sector_name_zh": sector.get("name_zh"),
                "sector_quadrant": sector.get("quadrant"),
                "sector_quadrant_zh": sector.get("quadrant_zh"),
                "sector_heat_score": sector.get("heat_score"),
                "sector_excess_20d": sector.get("excess_20d"),
                "sector_rs_ratio": sector.get("rs_ratio"),
                "sector_rs_momentum": sector.get("rs_momentum"),
                "position_total_unrealized_pnl": position.get("total_unrealized_pnl"),
                "position_worst_leg_return_pct": position.get("worst_leg_return_pct"),
                "position_min_option_dte": position.get("min_option_dte"),
                "position_leg_count": position.get("leg_count"),
                "position_held_not_in_ledger": position.get("held_not_in_ledger"),
                "raw_row_json": _json_blob(item),
            })
        return as_of

    for path in _json_files(src_dir, _DATED_JSON_RE):
        as_of = append_rows(path, source_file=path.name)
        if as_of:
            seen_snapshot_dates.add(as_of)

    latest_path = src_dir / "latest.json"
    latest = _load_json(latest_path)
    if latest:
        latest_date = _as_date_from_generated(latest, fallback="")[:10]
        if latest_date and latest_date not in seen_snapshot_dates:
            append_rows(latest_path, source_file=latest_path.name)

    df = pd.DataFrame(rows, columns=RISK_GUARD_ROW_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["risk_guard_rows"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def _position_leg_metrics(legs: Any, as_of_date: str) -> dict[str, Any]:
    leg_rows = [
        leg for leg in legs if isinstance(leg, dict)
    ] if isinstance(legs, list) else []
    as_of = _parse_date(as_of_date)
    option_legs = []
    stock_legs = []
    returns: list[float] = []
    dtes: list[int] = []
    expiries: list[str] = []
    rights: set[str] = set()

    for leg in leg_rows:
        sec_type = str(leg.get("secType") or "").upper()
        is_option = sec_type == "OPT" or bool(leg.get("expiry") or leg.get("right"))
        if is_option:
            option_legs.append(leg)
            right = str(leg.get("right") or "").strip().upper()
            if right:
                rights.add(right)
            expiry = _parse_date(leg.get("expiry"))
            if expiry is not None:
                expiries.append(expiry.isoformat())
                if as_of is not None:
                    dtes.append((expiry - as_of).days)
        elif sec_type == "STK":
            stock_legs.append(leg)

        ret = _float_or_none(leg.get("return_pct"))
        if ret is not None:
            returns.append(ret)

    return {
        "leg_count": len(leg_rows),
        "option_leg_count": len(option_legs),
        "stock_leg_count": len(stock_legs),
        "min_option_dte": min(dtes) if dtes else None,
        "earliest_expiry": min(expiries) if expiries else None,
        "worst_leg_return_pct": min(returns) if returns else None,
        "option_rights_json": _json_blob(sorted(rights)) if rights else None,
    }


def _sanitized_position_blob(row: dict[str, Any]) -> str | None:
    sanitized = {
        k: v
        for k, v in row.items()
        if k not in {"legs", "account", "account_id", "accountId"}
    }
    return _json_blob(sanitized)


def _portfolio_positions_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=PORTFOLIO_POSITION_COLUMNS)
    for col in PORTFOLIO_POSITION_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in PORTFOLIO_POSITION_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in PORTFOLIO_POSITION_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def export_portfolio_positions(
    reconciliation_path: str | Path = REPORTS_DIR / "reconciliation.json",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Export IBKR reconciliation into one privacy-conscious row per underlying."""
    src = Path(reconciliation_path)
    data = _load_json(src)
    rows: list[dict[str, Any]] = []
    if data:
        as_of = _as_date_from_generated(data, fallback="") or _file_mtime_date(src)
        generated_at = data.get("generated_at") or _file_mtime_utc(src)
        bucket_specs = (
            ("matched", True, True),
            ("ledger_not_held", False, True),
            ("held_not_in_ledger", True, False),
        )
        for bucket, held, ranked in bucket_specs:
            bucket_rows = data.get(bucket)
            if not isinstance(bucket_rows, list):
                continue
            for item in bucket_rows:
                if not isinstance(item, dict):
                    continue
                ticker = str(item.get("ticker") or "").upper().strip()
                if not ticker:
                    continue
                metrics = _position_leg_metrics(item.get("legs"), as_of)
                rows.append({
                    "source_file": src.name,
                    "as_of_date": as_of,
                    "generated_at": generated_at,
                    "reachable": data.get("reachable"),
                    "position_status": bucket,
                    "ticker": ticker,
                    "held": held,
                    "ranked": ranked,
                    "verdict": item.get("verdict"),
                    "scan_date": item.get("scan_date"),
                    "suggested_entry_low": item.get("suggested_entry_low"),
                    "suggested_entry_high": item.get("suggested_entry_high"),
                    "fwd_30d_return": item.get("fwd_30d_return"),
                    "total_unrealized_pnl": item.get("total_unrealized_pnl"),
                    **metrics,
                    "raw_position_json": _sanitized_position_blob(item),
                })

    df = _portfolio_positions_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["portfolio_positions"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src), "path": str(out), "rows": int(len(df))}


def _theme_flow_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=THEME_FLOW_SNAPSHOT_COLUMNS)
    for col in THEME_FLOW_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in THEME_FLOW_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in THEME_FLOW_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def export_theme_flow_snapshots(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten Theme Flow snapshots into one row per theme/date."""
    reports = Path(reports_root)
    archive_dir = reports / "theme_flow_snapshots"
    latest_path = reports / "theme_flow_snapshot.json"
    rows: list[dict[str, Any]] = []
    seen_snapshot_dates: set[str] = set()

    def append_snapshot(path: Path, *, source_file: str) -> str:
        data = _load_json(path)
        if not data:
            return ""
        as_of = _as_date_from_generated(data, fallback=path.stem)
        if not as_of:
            as_of = _file_mtime_date(path)
        generated_at = data.get("generated_at") or _file_mtime_utc(path)
        themes = data.get("themes")
        if not isinstance(themes, list):
            return as_of
        for item in themes:
            if not isinstance(item, dict):
                continue
            theme = str(item.get("theme") or "").strip()
            if not theme:
                continue
            rows.append({
                "source_file": source_file,
                "as_of_date": as_of,
                "generated_at": generated_at,
                "benchmark": data.get("benchmark"),
                "schema_version": data.get("schema_version"),
                "n_failed_download": data.get("n_failed_download"),
                "theme": theme,
                "desc": item.get("desc"),
                "capital_state": item.get("capital_state"),
                "heat_score": item.get("heat_score"),
                "flow_5d": item.get("flow_5d"),
                "flow_5d_norm": item.get("flow_5d_norm"),
                "flow_20d": item.get("flow_20d"),
                "flow_20d_norm": item.get("flow_20d_norm"),
                "accel": item.get("accel"),
                "accel_norm": item.get("accel_norm"),
                "ret_5d": item.get("ret_5d"),
                "excess_5d": item.get("excess_5d"),
                "rvol": item.get("rvol"),
                "top_share": item.get("top_share"),
                "high_concentration": item.get("high_concentration"),
                "eastmoney_main_net_5d": item.get("eastmoney_main_net_5d"),
                "eastmoney_main_net_20d": item.get("eastmoney_main_net_20d"),
                "eastmoney_main_pct_latest": item.get("eastmoney_main_pct_latest"),
                "money_flow_source": item.get("money_flow_source"),
                "money_flow_caveat": item.get("money_flow_caveat"),
                "n_total": item.get("n_total"),
                "n_used": item.get("n_used"),
                "n_failed": item.get("n_failed"),
                "shared_mega_caps_json": _json_blob(data.get("shared_mega_caps")),
                "parent_sector_etfs_json": _json_blob(item.get("parent_sector_etfs")),
                "reps_json": _json_blob(item.get("reps")),
                "bottom_fishing_json": _json_blob(item.get("bottom_fishing")),
                "buckets_json": _json_blob(data.get("buckets")),
                "params_json": _json_blob(data.get("params")),
                "raw_theme_json": _json_blob(item),
            })
        return as_of

    for path in _json_files(archive_dir, _DATED_JSON_RE):
        as_of = append_snapshot(path, source_file=path.name)
        if as_of:
            seen_snapshot_dates.add(as_of)

    latest = _load_json(latest_path)
    if latest:
        latest_date = _as_date_from_generated(latest, fallback="")[:10] or _file_mtime_date(latest_path)
        if latest_date and latest_date not in seen_snapshot_dates:
            append_snapshot(latest_path, source_file=latest_path.name)

    df = _theme_flow_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["theme_flow_snapshots"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def _sector_rotation_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=SECTOR_ROTATION_SNAPSHOT_COLUMNS)
    for col in SECTOR_ROTATION_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in SECTOR_ROTATION_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in SECTOR_ROTATION_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def export_sector_rotation_snapshots(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten Sector Rotation snapshots into one row per ETF/date."""
    reports = Path(reports_root)
    archive_dir = reports / "sector_rotation_snapshots"
    latest_path = reports / "sector_rotation.json"
    rows: list[dict[str, Any]] = []
    seen_snapshot_dates: set[str] = set()

    def _upper_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            text = str(item or "").upper().strip()
            if text and text not in out:
                out.append(text)
        return out

    def append_snapshot(path: Path, *, source_file: str) -> str:
        data = _load_json(path)
        if not data:
            return ""
        as_of = _as_date_from_generated(data, fallback=path.stem)
        if not as_of:
            as_of = _file_mtime_date(path)
        generated_at = data.get("generated_at") or _file_mtime_utc(path)
        leaders = _upper_list(data.get("leaders"))
        improving = _upper_list(data.get("improving"))
        leader_rank = {etf: i + 1 for i, etf in enumerate(leaders)}
        improving_rank = {etf: i + 1 for i, etf in enumerate(improving)}
        macro = data.get("macro") if isinstance(data.get("macro"), dict) else {}
        read = data.get("read") if isinstance(data.get("read"), dict) else {}
        sectors = data.get("sectors") if isinstance(data.get("sectors"), list) else []
        seen_etfs: set[str] = set()

        def append_sector(item: dict[str, Any]) -> None:
            etf = str(item.get("etf") or "").upper().strip()
            if not etf:
                return
            is_leader = etf in leader_rank
            is_improving = etf in improving_rank
            quadrant = item.get("quadrant")
            quadrant_zh = item.get("quadrant_zh")
            if not quadrant and is_leader:
                quadrant = "Leading"
            elif not quadrant and is_improving:
                quadrant = "Improving"
            if not quadrant_zh and quadrant == "Leading":
                quadrant_zh = "領漲"
            elif not quadrant_zh and quadrant == "Improving":
                quadrant_zh = "醞釀"
            rows.append({
                "source_file": source_file,
                "as_of_date": as_of,
                "generated_at": generated_at,
                "status": data.get("status"),
                "benchmark": data.get("benchmark"),
                "etf": etf,
                "name_zh": item.get("name_zh"),
                "group": item.get("group"),
                "theme": item.get("theme"),
                "quadrant": quadrant,
                "quadrant_zh": quadrant_zh,
                "rs_ratio": item.get("rs_ratio"),
                "rs_momentum": item.get("rs_momentum"),
                "heat_score": item.get("heat_score"),
                "ret_5d": item.get("ret_5d"),
                "ret_20d": item.get("ret_20d"),
                "ret_60d": item.get("ret_60d"),
                "excess_20d": item.get("excess_20d"),
                "pct_vs_ma50": item.get("pct_vs_ma50"),
                "pct_vs_ma200": item.get("pct_vs_ma200"),
                "rvol": item.get("rvol"),
                "pct_from_52w_high": item.get("pct_from_52w_high"),
                "is_leader": is_leader,
                "is_improving": is_improving,
                "leader_rank": leader_rank.get(etf),
                "improving_rank": improving_rank.get(etf),
                "spy_price": macro.get("spy_price"),
                "spy_vs_50dma": macro.get("spy_vs_50dma"),
                "spy_vs_200dma": macro.get("spy_vs_200dma"),
                "vix_level": macro.get("vix_level"),
                "read_confidence": read.get("confidence"),
                "read_headline": read.get("headline"),
                "read_cycle_read": read.get("cycle_read"),
                "read_next_rotation_thesis": read.get("next_rotation_thesis"),
                "read_hot_now_json": _json_blob(read.get("hot_now")),
                "read_rotating_into_json": _json_blob(read.get("rotating_into")),
                "read_caveats_json": _json_blob(read.get("caveats")),
                "params_json": _json_blob(data.get("params")),
                "tail_json": _json_blob(item.get("tail")),
                "raw_sector_json": _json_blob(item),
            })
            seen_etfs.add(etf)

        for sector in sectors:
            if isinstance(sector, dict):
                append_sector(sector)
        for etf in leaders + improving:
            if etf in seen_etfs:
                continue
            append_sector({"etf": etf})
        return as_of

    for path in _json_files(archive_dir, _DATED_JSON_RE):
        as_of = append_snapshot(path, source_file=path.name)
        if as_of:
            seen_snapshot_dates.add(as_of)

    latest = _load_json(latest_path)
    if latest:
        latest_date = _as_date_from_generated(latest, fallback="")[:10] or _file_mtime_date(latest_path)
        if latest_date and latest_date not in seen_snapshot_dates:
            append_snapshot(latest_path, source_file=latest_path.name)

    df = _sector_rotation_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["sector_rotation_snapshots"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def _validation_summary_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=VALIDATION_SUMMARY_COLUMNS)
    for col in VALIDATION_SUMMARY_STRING_COLUMNS:
        df[col] = df[col].astype("string")
    for col in VALIDATION_SUMMARY_BOOL_COLUMNS:
        df[col] = df[col].astype("boolean")
    for col in VALIDATION_SUMMARY_NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def _summary_mature(data: dict[str, Any]) -> bool | None:
    status = str(data.get("validation_status") or data.get("verdict") or "").upper()
    if status.startswith("MATURE"):
        return True
    if status.startswith("PROVISIONAL"):
        return False
    min_resolved = _float_or_none(data.get("min_resolved_across_tiers"))
    min_required = _float_or_none(data.get("min_resolved_for_verdict"))
    if min_resolved is not None and min_required is not None:
        return min_resolved >= min_required
    return None


def export_validation_summaries(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten lane-level validation_summary.json files into one summary table."""
    reports = Path(reports_root)
    rows: list[dict[str, Any]] = []
    sources = {
        "options_flow": reports / "options_flow" / "validation_summary.json",
        "reversal_radar": reports / "reversal_radar" / "validation_summary.json",
        "oversold_reversal": reports / "oversold_reversal" / "validation_summary.json",
        "market_thesis": reports / "market_thesis" / "validation_summary.json",
    }
    for signal_source, path in sources.items():
        data = _load_json(path)
        if not data:
            continue
        survivorship = data.get("survivorship") if isinstance(data.get("survivorship"), dict) else {}
        sp500_pit = data.get("sp500_pit_cohort") if isinstance(data.get("sp500_pit_cohort"), dict) else {}
        as_of = _as_date_from_generated(data, fallback="")
        if not as_of:
            as_of = _file_mtime_date(path)
        rows.append({
            "source_file": str(path.relative_to(reports)) if path.is_relative_to(reports) else path.name,
            "signal_source": signal_source,
            "as_of_date": as_of,
            "generated_at": data.get("generated_at") or _file_mtime_utc(path),
            "module": data.get("module") or signal_source,
            "lane_id": data.get("lane_id"),
            "entries_accumulated": data.get("entries_accumulated"),
            "price_resolvable": data.get("price_resolvable"),
            "dropped_count": data.get("dropped_count"),
            "dropped_pct": data.get("dropped_pct"),
            "min_resolved_across_tiers": data.get("min_resolved_across_tiers"),
            "min_resolved_for_verdict": data.get("min_resolved_for_verdict"),
            "verdict": data.get("verdict"),
            "validation_status": data.get("validation_status"),
            "mature": _summary_mature(data),
            "resolved": data.get("resolved"),
            "matured": data.get("matured"),
            "invalid_count": data.get("invalid_count"),
            "reject_count": data.get("reject_count"),
            "benchmark": data.get("benchmark"),
            "theta_dir": data.get("theta_dir"),
            "survivorship_free": survivorship.get("survivorship_free"),
            "forward_universe": survivorship.get("forward_universe"),
            "validated_universe": survivorship.get("validated_universe") or sp500_pit.get("validated_universe"),
            "universe_match": survivorship.get("universe_match"),
            "membership_snapshot_through": sp500_pit.get("membership_snapshot_through"),
            "cost_assumption_round_trip": data.get("cost_assumption_round_trip"),
            "verdict_by_tier_json": _json_blob(data.get("verdict_by_tier")),
            "by_tier_json": _json_blob(data.get("by_tier")),
            "buckets_json": _json_blob(data.get("buckets")),
            "survivorship_json": _json_blob(data.get("survivorship")),
            "sp500_pit_cohort_json": _json_blob(data.get("sp500_pit_cohort")),
            "ev_caveats_json": _json_blob(data.get("ev_caveats")),
            "note": data.get("note"),
            "raw_summary_json": _json_blob(data),
        })

    df = _validation_summary_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["validation_summaries"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def export_daily_reports(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/YYYY-MM-DD/summary.json into one daily archive row."""
    reports = Path(reports_root)
    rows: list[dict[str, Any]] = []
    for path in _daily_report_files(reports):
        data = _load_json(path)
        if not data:
            continue
        ranked_picks = data.get("ranked_picks") if isinstance(data.get("ranked_picks"), list) else []
        report_date = str(data.get("report_date") or path.parent.name)[:10]
        rows.append({
            "source_file": str(path.relative_to(reports)) if path.is_relative_to(reports) else path.name,
            "report_date": report_date,
            "generated_at": data.get("generated_at") or _file_mtime_utc(path),
            "total_confirmed": data.get("total_confirmed"),
            "ranked_picks_count": len(ranked_picks),
            "top_tickers_json": _json_blob(_top_tickers(ranked_picks)),
            "regime_summary": data.get("regime_summary"),
            "cross_candidate_commentary": data.get("cross_candidate_commentary"),
            "portfolio_notes": data.get("portfolio_notes"),
            "ranked_picks_json": _json_blob(ranked_picks),
            "raw_report_json": _json_blob(data),
        })

    df = _daily_report_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["daily_reports"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def export_watchlist_sources(
    reports_root: str | Path = REPORTS_DIR,
    *,
    watchlist_text_path: str | Path | None = None,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten additive watchlist sources into one ticker/source table."""
    reports = Path(reports_root)
    rows: list[dict[str, Any]] = []

    scanner_path = reports / "watchlist.json"
    scanner = _load_json(scanner_path)
    if scanner and isinstance(scanner.get("tickers"), list):
        scan_date = str(scanner.get("scan_date") or _as_date_from_generated(scanner, fallback=""))[:10]
        if not scan_date:
            scan_date = _file_mtime_date(scanner_path)
        generated_at = scanner.get("generated_at") or _file_mtime_utc(scanner_path)
        source_group = str(scanner.get("source") or "ibkr_scanner")
        source_scans = _json_blob(scanner.get("scans"))
        for position, item in enumerate(scanner["tickers"], start=1):
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper().strip().removeprefix("$")
            if not ticker:
                continue
            rows.append({
                "source_file": scanner_path.name,
                "source_group": source_group,
                "source_label": "IBKR scanner",
                "scan_date": scan_date,
                "generated_at": generated_at,
                "ticker": ticker,
                "source_rank": position,
                "tv_symbol": None,
                "exchange": None,
                "location": scanner.get("location"),
                "scan_kinds_json": _json_blob(item.get("scan_kinds")),
                "in_static_universe": item.get("in_static_universe"),
                "source_scans_json": source_scans,
                "raw_entry_json": _json_blob(item),
            })

    text_path = Path(watchlist_text_path) if watchlist_text_path else reports.parent / "content" / "us_watchlist.txt"
    if text_path.is_file():
        try:
            text = text_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        scan_date = _file_mtime_date(text_path)
        generated_at = _file_mtime_utc(text_path)
        try:
            source_file = str(text_path.relative_to(reports.parent))
        except ValueError:
            source_file = text_path.name
        for position, item in enumerate(_parse_watchlist_text(text), start=1):
            rows.append({
                "source_file": source_file,
                "source_group": "manual_watchlist",
                "source_label": "Manual TradingView watchlist",
                "scan_date": scan_date,
                "generated_at": generated_at,
                "ticker": item.get("ticker"),
                "source_rank": position,
                "tv_symbol": item.get("tv_symbol"),
                "exchange": item.get("exchange"),
                "location": None,
                "scan_kinds_json": None,
                "in_static_universe": None,
                "source_scans_json": None,
                "raw_entry_json": _json_blob(item),
            })

    df = _watchlist_source_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["watchlist_sources"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def export_source_observations(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Persist source-run metadata even when a valid source has zero data rows."""
    reports = Path(reports_root)
    rows: list[dict[str, Any]] = []

    reconciliation_path = reports / "reconciliation.json"
    reconciliation = _load_json(reconciliation_path)
    if not reconciliation_path.is_file():
        reconciliation_availability = "not_configured"
    elif reconciliation is None:
        reconciliation_availability = "invalid"
    else:
        reconciliation_availability = "configured"
    position_count = 0
    if reconciliation:
        position_count = sum(
            len(reconciliation.get(bucket))
            for bucket in ("matched", "ledger_not_held", "held_not_in_ledger")
            if isinstance(reconciliation.get(bucket), list)
        )
    rows.append({
        "source_id": "portfolio_reconciliation",
        "source_file": reconciliation_path.name,
        "availability": reconciliation_availability,
        "source_date": (
            _as_date_from_generated(reconciliation, fallback="")
            or _file_mtime_date(reconciliation_path)
            if reconciliation else None
        ),
        "generated_at": (
            reconciliation.get("generated_at") or _file_mtime_utc(reconciliation_path)
            if reconciliation else None
        ),
        "reachable": (
            reconciliation.get("reachable")
            if reconciliation and isinstance(reconciliation.get("reachable"), bool)
            else None
        ),
        "record_count": position_count,
    })

    scanner_path = reports / "watchlist.json"
    scanner = _load_json(scanner_path)
    valid_scanner = scanner is not None and isinstance(scanner.get("tickers"), list)
    if not scanner_path.is_file():
        scanner_availability = "not_configured"
    elif not valid_scanner:
        scanner_availability = "invalid"
    else:
        scanner_availability = "configured"
    rows.append({
        "source_id": "watchlist_scanner",
        "source_file": scanner_path.name,
        "availability": scanner_availability,
        "source_date": (
            _as_date_from_generated(scanner, fallback="") or _file_mtime_date(scanner_path)
            if valid_scanner else None
        ),
        "generated_at": (
            scanner.get("generated_at") or _file_mtime_utc(scanner_path)
            if valid_scanner else None
        ),
        "reachable": None,
        "record_count": len(scanner.get("tickers", [])) if valid_scanner else 0,
    })

    df = _source_observation_frame(rows)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["source_observations"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def export_signal_outcomes(
    reports_root: str | Path = REPORTS_DIR,
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten aggregate forward-validation summaries into one outcome table.

    The source validators own price fetching and resolution semantics. This
    exporter only materializes their published tier-level outcomes for SQL/UI.
    """
    reports = Path(reports_root)
    rows: list[dict[str, Any]] = []
    sources = {
        "options_flow": reports / "options_flow" / "validation_summary.json",
        "reversal_radar": reports / "reversal_radar" / "validation_summary.json",
        "oversold_reversal": reports / "oversold_reversal" / "validation_summary.json",
    }
    for signal_source, path in sources.items():
        data = _load_json(path)
        if not data or not isinstance(data.get("by_tier"), dict):
            continue
        min_resolved = data.get("min_resolved_for_verdict")
        as_of = _as_date_from_generated(data, fallback=path.parent.name)
        for tier, outcome in sorted(data["by_tier"].items()):
            if not isinstance(outcome, dict):
                continue
            target_pct, horizon_days = _tier_parts(str(tier))
            resolved = outcome.get("resolved")
            mature = outcome.get("mature")
            if mature is None and isinstance(resolved, (int, float)) and isinstance(min_resolved, (int, float)):
                mature = resolved >= min_resolved
            wilson = outcome.get("wilson90") if isinstance(outcome.get("wilson90"), list) else []
            rows.append({
                "source_file": str(path.relative_to(reports)) if path.is_relative_to(reports) else path.name,
                "signal_source": signal_source,
                "as_of_date": as_of,
                "generated_at": data.get("generated_at"),
                "tier": tier,
                "target_return_pct": target_pct,
                "horizon_days": horizon_days,
                "resolved": resolved,
                "hits": outcome.get("hits"),
                "hit_rate": outcome.get("hit_rate"),
                "wilson90_low": wilson[0] if len(wilson) > 0 else None,
                "wilson90_high": wilson[1] if len(wilson) > 1 else None,
                "mature": mature,
                "verdict": data.get("verdict"),
                "min_resolved_for_verdict": min_resolved,
                "ev_horizon": outcome.get("ev_horizon"),
                "median_horizon": outcome.get("median_horizon"),
                "win_rate_horizon": outcome.get("win_rate_horizon"),
                "ev_excess_vs_spy": outcome.get("ev_excess_vs_spy"),
                "excess_n": outcome.get("excess_n"),
                "excess_win_rate": outcome.get("excess_win_rate"),
                "ev_excess_beta_adj": outcome.get("ev_excess_beta_adj"),
                "raw_outcome_json": _json_blob(outcome),
            })
    df = pd.DataFrame(rows, columns=SIGNAL_OUTCOME_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["signal_outcomes"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(reports), "path": str(out), "rows": int(len(df))}


def export_run_status_history(
    run_status_dir: str | Path = REPORTS_DIR / "run_status",
    *,
    analytics_root: str | Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Flatten reports/run_status/candidates-local-history.jsonl into one table."""
    src_dir = Path(run_status_dir)
    source = src_dir / "candidates-local-history.jsonl"
    rows: list[dict[str, Any]] = []
    if source.is_file():
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue
            stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
            metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
            outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
            warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
            errors = data.get("errors") if isinstance(data.get("errors"), list) else []
            rows.append({
                "source_file": source.name,
                "line_number": line_number,
                "run_id": data.get("run_id"),
                "job": data.get("job"),
                "status": data.get("status"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "updated_at": data.get("updated_at"),
                "duration_seconds": _duration_seconds(data.get("started_at"), data.get("finished_at")),
                "stage_id": stage.get("id"),
                "stage_label": stage.get("label"),
                "stage_status": stage.get("status"),
                "stage_progress_pct": stage.get("progress_pct"),
                "stage_message": stage.get("message"),
                "rank_source_candidates": _metric(metrics, "rank_source_candidates"),
                "rank_limit": _metric(metrics, "rank_limit"),
                "ranked_candidates": _metric(metrics, "ranked_candidates"),
                "options_gate_requested": _metric(metrics, "options_gate_requested"),
                "options_gate_checked": _metric(metrics, "options_gate_checked"),
                "options_usable": _metric(metrics, "options_usable"),
                "options_watch": _metric(metrics, "options_watch"),
                "options_unusable": _metric(metrics, "options_unusable"),
                "options_unknown": _metric(metrics, "options_unknown"),
                "scored_candidates": _metric(metrics, "scored_candidates"),
                "remaining_candidates": _metric(metrics, "remaining_candidates"),
                "errored_candidates": _metric(metrics, "errored_candidates"),
                "deferred_candidates": _metric(metrics, "deferred_candidates"),
                "needs_layer2_count": _metric(metrics, "needs_layer2_count"),
                "watchlist_count": _metric(metrics, "watchlist_count"),
                "rejected_count": _metric(metrics, "rejected_count"),
                "passed_hard_filters": _metric(metrics, "passed_hard_filters"),
                "rejected": _metric(metrics, "rejected"),
                "total_tickers": _metric(metrics, "total_tickers"),
                "downloaded_tickers": _metric(metrics, "downloaded_tickers"),
                "current_coverage": _metric(metrics, "current_coverage"),
                "data_available": _metric(metrics, "data_available"),
                "total_batches": _metric(metrics, "total_batches"),
                "completed_batches": _metric(metrics, "completed_batches"),
                "candidate_limit": _metric(metrics, "candidate_limit"),
                "scoring_mode": _metric(metrics, "scoring_mode"),
                "warnings_count": _json_count(warnings),
                "errors_count": _json_count(errors),
                "outputs_json": _json_blob(outputs),
                "metrics_json": _json_blob(metrics),
                "warnings_json": _json_blob(warnings),
                "errors_json": _json_blob(errors),
                "raw_run_json": _json_blob(data),
            })
    df = pd.DataFrame(rows, columns=RUN_STATUS_HISTORY_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["run_status_history"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(source), "path": str(out), "rows": int(len(df))}


def refresh_views(analytics_root: str | Path | None = None) -> dict[str, str]:
    """Create/replace DuckDB tables for every known Parquet artifact present."""
    root = analytics_dir(analytics_root)
    root.mkdir(parents=True, exist_ok=True)
    db = duckdb_path(root)
    created: dict[str, str] = {}
    con = duckdb.connect(str(db))
    try:
        con.execute("begin transaction")
        for view, filename in KNOWN_TABLES.items():
            path = parquet_dir(root) / filename
            if not path.is_file():
                continue
            existing = con.execute(
                """
                select table_type
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                """,
                [view],
            ).fetchone()
            if existing:
                drop_kind = "view" if str(existing[0]).upper() == "VIEW" else "table"
                con.execute(f"drop {drop_kind} {_sql_ident(view)}")
            con.execute(
                f"create or replace table {_sql_ident(view)} as "
                f"select * from read_parquet('{_sql_path(path)}')"
            )
            created[view] = str(path)
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    finally:
        con.close()
    return created


def query(sql: str, *, analytics_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Run a read-only DuckDB query. Returns rows as dictionaries."""
    root = analytics_dir(analytics_root)
    con = duckdb.connect(str(duckdb_path(root)), read_only=True)
    try:
        result = con.execute(sql)
        columns = [d[0] for d in (result.description or [])]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()


def table_columns(
    table_name: str,
    *,
    analytics_root: str | Path | None = None,
) -> list[str]:
    """Return column names for a known analytics table using a read-only DB connection."""
    table = _known_table(table_name)
    db = duckdb_path(analytics_root)
    if not db.is_file():
        return []
    con = _readonly_connect(analytics_root)
    try:
        return [
            str(row[0])
            for row in con.execute(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'main' and table_name = ?
                order by ordinal_position
                """,
                [table],
            ).fetchall()
        ]
    finally:
        con.close()


def readonly_catalog(analytics_root: str | Path | None = None) -> list[dict[str, Any]]:
    """List known analytics tables with row counts. Does not refresh or write the DB."""
    db = duckdb_path(analytics_root)
    if not db.is_file():
        return []
    con = _readonly_connect(analytics_root)
    try:
        rows = con.execute(
            """
            select table_name, table_type
            from information_schema.tables
            where table_schema = 'main'
            order by table_name
            """
        ).fetchall()
        catalog = []
        for name, table_type in rows:
            if name not in KNOWN_TABLES:
                continue
            try:
                row_count = int(con.execute(
                    f"select count(*) from {_sql_ident(str(name))}"
                ).fetchone()[0])
            except duckdb.Error:
                row_count = None
            cols = con.execute(
                """
                select count(*)
                from information_schema.columns
                where table_schema = 'main' and table_name = ?
                """,
                [name],
            ).fetchone()[0]
            catalog.append({
                "table_name": str(name),
                "table_type": str(table_type),
                "row_count": row_count,
                "column_count": int(cols),
            })
        return catalog
    finally:
        con.close()


def distinct_values(
    table_name: str,
    column: str,
    *,
    analytics_root: str | Path | None = None,
    limit: int = 500,
) -> list[str]:
    """Return distinct string values from a known table/column for UI filters."""
    table = _known_table(table_name)
    cols = set(table_columns(table, analytics_root=analytics_root))
    if column not in cols:
        return []
    con = _readonly_connect(analytics_root)
    try:
        rows = con.execute(
            f"select distinct {_sql_ident(column)} from {_sql_ident(table)} "
            f"where {_sql_ident(column)} is not null "
            f"order by {_sql_ident(column)} limit {_clamp_limit(limit)}"
        ).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        con.close()


def fetch_table(
    table_name: str,
    *,
    analytics_root: str | Path | None = None,
    tickers: list[str] | tuple[str, ...] | None = None,
    date_column: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    order_by: str | None = None,
    descending: bool = True,
    limit: int = 500,
) -> pd.DataFrame:
    """Read rows from a known analytics table with optional safe filters."""
    table = _known_table(table_name)
    cols = set(table_columns(table, analytics_root=analytics_root))
    if not cols:
        return pd.DataFrame()

    where: list[str] = []
    params: list[Any] = []
    if tickers and "ticker" in cols:
        normalized = [str(t).upper().strip() for t in tickers if str(t).strip()]
        if normalized:
            placeholders = ", ".join(["?"] * len(normalized))
            where.append(f"upper(ticker) in ({placeholders})")
            params.extend(normalized)
    if date_column and date_column in cols:
        if start_date:
            where.append(f"cast({_sql_ident(date_column)} as date) >= cast(? as date)")
            params.append(str(start_date))
        if end_date:
            where.append(f"cast({_sql_ident(date_column)} as date) <= cast(? as date)")
            params.append(str(end_date))

    sql = f"select * from {_sql_ident(table)}"
    if where:
        sql += " where " + " and ".join(where)
    if order_by and order_by in cols:
        sql += f" order by {_sql_ident(order_by)} {'desc' if descending else 'asc'}"
    sql += f" limit {_clamp_limit(limit)}"

    con = _readonly_connect(analytics_root)
    try:
        return con.execute(sql, params).fetchdf()
    finally:
        con.close()


def run_safe_select(
    sql: str,
    *,
    analytics_root: str | Path | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Run one read-only SELECT and cap returned rows for the UI SQL console."""
    cleaned = str(sql or "").strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if not cleaned:
        raise ValueError("SQL is empty")
    if ";" in cleaned or not cleaned.lower().startswith("select "):
        raise ValueError("Only SELECT statements are allowed")
    capped = f"select * from ({cleaned}) as analytics_query limit {_clamp_limit(limit)}"
    con = _readonly_connect(analytics_root)
    try:
        return con.execute(capped).fetchdf()
    finally:
        con.close()


def refresh_all(
    *,
    reports_root: str | Path = REPORTS_DIR,
    analytics_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    reports = Path(reports_root)
    meta = {
        "universe_snapshots": export_universe_snapshots(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "daily_bars": export_daily_bars(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "daily_money_flow": export_daily_money_flow(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "performance_ledger": export_performance_ledger(
            reports / "performance_ledger.csv",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "iv_history": export_iv_history(
            reports / "iv_history",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "options_flow_signals": export_options_flow_signals(
            reports / "options_flow",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "reversal_radar_signals": export_reversal_radar_signals(
            reports / "reversal_radar",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "oversold_reversal_signals": export_oversold_reversal_signals(
            reports / "oversold_reversal",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "market_thesis_forecasts": export_market_thesis_forecasts(
            reports / "market_thesis",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "candidate_scores": export_candidate_scores(
            reports / "candidate_scores",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "candidate_rankings": export_candidate_rankings(
            reports / "candidate_rankings",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "candidate_outcomes": export_candidate_outcomes(
            reports / "candidate_outcomes",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "risk_guard_rows": export_risk_guard_rows(
            reports / "risk_guard",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "portfolio_positions": export_portfolio_positions(
            reports / "reconciliation.json",
            analytics_root=analytics_root,
            refresh=False,
        ),
        "trade_state_snapshots": export_trade_state_snapshots(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "fundamental_metrics": export_fundamental_metrics(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "industry_role_assignments": export_industry_role_assignments(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "theme_flow_snapshots": export_theme_flow_snapshots(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "sector_rotation_snapshots": export_sector_rotation_snapshots(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "validation_summaries": export_validation_summaries(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "daily_reports": export_daily_reports(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "watchlist_sources": export_watchlist_sources(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "source_observations": export_source_observations(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "signal_outcomes": export_signal_outcomes(
            reports,
            analytics_root=analytics_root,
            refresh=False,
        ),
        "run_status_history": export_run_status_history(
            reports / "run_status",
            analytics_root=analytics_root,
            refresh=False,
        ),
    }
    refresh_views(analytics_root)
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DuckDB/Parquet analytics store")
    sub = parser.add_subparsers(dest="command", required=True)

    p_refresh = sub.add_parser("refresh", help="export known reports into Parquet")
    p_refresh.add_argument("--reports-dir", default=str(REPORTS_DIR))
    p_refresh.add_argument("--analytics-dir", default=None)

    p_query = sub.add_parser("query", help="run a SQL query against analytics tables")
    p_query.add_argument("sql")
    p_query.add_argument("--analytics-dir", default=None)

    args = parser.parse_args(argv)
    if args.command == "refresh":
        print(json.dumps(refresh_all(reports_root=args.reports_dir,
                                     analytics_root=args.analytics_dir),
                         indent=2, ensure_ascii=False))
        return 0
    if args.command == "query":
        print(json.dumps(query(args.sql, analytics_root=args.analytics_dir),
                         indent=2, ensure_ascii=False, default=str))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
