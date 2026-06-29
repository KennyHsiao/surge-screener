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
    "source_file", "scan_date", "generated_at", "total_candidates",
    "scored_candidates_count", "remaining_unscored", "needs_layer2_count",
    "watchlist_count", "min_score_threshold", "ticker", "verdict",
    "composite_score", "regime_adjusted_score", "technical", "catalyst",
    "sentiment", "institutional", "sector_market", "options_flow",
    "analyst", "pattern_type", "scoring_mode", "due_diligence_required",
    "data_missing_json", "raw_candidate_json",
]
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
KNOWN_TABLES = {
    "performance_ledger": "performance_ledger.parquet",
    "iv_history": "iv_history.parquet",
    "options_flow_signals": "options_flow_signals.parquet",
    "reversal_radar_signals": "reversal_radar_signals.parquet",
    "oversold_reversal_signals": "oversold_reversal_signals.parquet",
    "market_thesis_forecasts": "market_thesis_forecasts.parquet",
    "candidate_scores": "candidate_scores.parquet",
    "signal_outcomes": "signal_outcomes.parquet",
    "run_status_history": "run_status_history.parquet",
}
_DATED_JSON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
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


def _tier_parts(label: str) -> tuple[float | None, int | None]:
    match = _TIER_RE.match(str(label or ""))
    if not match:
        return (None, None)
    return (float(match.group(1)), int(match.group(2)))


def _json_files(src_dir: Path, pattern: re.Pattern[str]) -> list[Path]:
    if not src_dir.is_dir():
        return []
    return sorted(p for p in src_dir.glob("*.json") if pattern.match(p.name))


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
    for path in _json_files(src_dir, _DATED_JSON_RE):
        data = _load_json(path)
        if not data or not isinstance(data.get("all_scored"), list):
            continue
        scan_date = str(data.get("scan_date") or path.stem)
        for candidate in data["all_scored"]:
            if not isinstance(candidate, dict):
                continue
            scores = candidate.get("scores") if isinstance(candidate.get("scores"), dict) else {}
            technical = (candidate.get("technical_breakdown")
                         if isinstance(candidate.get("technical_breakdown"), dict) else {})
            rows.append({
                "source_file": path.name,
                "scan_date": scan_date,
                "generated_at": data.get("generated_at"),
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
    df = pd.DataFrame(rows, columns=CANDIDATE_SCORE_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_TABLES["candidate_scores"]
    _write_parquet(df, out)
    if refresh:
        refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


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
