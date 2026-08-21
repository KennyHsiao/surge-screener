#!/usr/bin/env python3
"""Automated health checks and follow-up actions for the analytics DuckDB store."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import analytics_store
except ImportError:  # pragma: no cover - direct script execution from scripts/.
    import analytics_store  # type: ignore


REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO / "reports" / "analytics_checks" / "latest.json"
DATE_COLUMNS = {
    "universe_snapshots": "as_of_date",
    "daily_bars": "bar_date",
    "daily_money_flow": "flow_date",
    "performance_ledger": "scan_date",
    "iv_history": "as_of_date",
    "options_flow_signals": "as_of_date",
    "reversal_radar_signals": "as_of_date",
    "oversold_reversal_signals": "as_of_date",
    "market_thesis_forecasts": "as_of_date",
    "candidate_scores": "scan_date",
    "candidate_rankings": "scan_date",
    "candidate_outcomes": "scan_date",
    "risk_guard_rows": "as_of_date",
    "portfolio_positions": "as_of_date",
    "trade_state_snapshots": "as_of_date",
    "theme_flow_snapshots": "as_of_date",
    "sector_rotation_snapshots": "as_of_date",
    "validation_summaries": "as_of_date",
    "daily_reports": "report_date",
    "watchlist_sources": "scan_date",
    "signal_outcomes": "as_of_date",
    "run_status_history": "started_at",
}
SIGNAL_TABLES = (
    "options_flow_signals",
    "reversal_radar_signals",
    "oversold_reversal_signals",
)
TODAY_SIGNAL_CORE_TABLES = {"candidate_rankings"}
ACTION_RANK = {
    "NO_ACTION": 0,
    "WATCHLIST_UPGRADE": 1,
    "TG_WARN": 1,
    "REVIEW_REQUIRED": 2,
    "DOWNGRADE_SIGNAL": 3,
    "BLOCK_TODAY_SIGNALS": 4,
}
STATUS_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    if value:
        return date.fromisoformat(str(value))
    return date.today()


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _check(
    check_id: str,
    status: str,
    message: str,
    *,
    table: str | None = None,
    value: Any = None,
    threshold: str | None = None,
    recommended_action: str = "NO_ACTION",
    code: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": check_id,
        "status": status,
        "message": message,
        "recommended_action": recommended_action,
    }
    if table is not None:
        item["table"] = table
    if value is not None:
        item["value"] = value
    if threshold is not None:
        item["threshold"] = threshold
    if code is not None:
        item["code"] = code
    return item


def _query(sql: str, *, analytics_root: Path) -> list[dict[str, Any]]:
    return analytics_store.query(sql, analytics_root=analytics_root)


def _source_observation(
    source_id: str, *, catalog: dict[str, str], analytics_root: Path,
) -> dict[str, Any] | None:
    if source_id not in {"portfolio_reconciliation", "watchlist_scanner"}:
        raise ValueError(f"unsupported source observation: {source_id}")
    if "source_observations" not in catalog:
        return None
    rows = _query(
        "select availability, source_date, generated_at, reachable, record_count "
        "from source_observations where source_id = "
        f"'{source_id}'",
        analytics_root=analytics_root,
    )
    return rows[0] if rows else None


def _overall_status(checks: list[dict[str, Any]], performance: dict[str, Any]) -> str:
    statuses = [str(c.get("status") or "PASS") for c in checks]
    statuses.append(str(performance.get("status") or "PASS"))
    return max(statuses, key=lambda s: STATUS_RANK.get(s, 0))


def _overall_action(
    checks: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    performance: dict[str, Any],
) -> str:
    actions = [str(c.get("recommended_action") or "NO_ACTION") for c in checks]
    actions.extend(str(s.get("recommended_action") or "NO_ACTION") for s in signals)
    actions.append(str(performance.get("recommended_action") or "NO_ACTION"))
    return max(actions, key=lambda a: ACTION_RANK.get(a, 0))


def _summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "checks_total": len(checks),
        "pass": sum(1 for c in checks if c.get("status") == "PASS"),
        "warn": sum(1 for c in checks if c.get("status") == "WARN"),
        "block": sum(1 for c in checks if c.get("status") == "BLOCK"),
    }


def _empty_table_message(table: str, row_count: int) -> str:
    if table == "portfolio_positions" and row_count <= 0:
        return (
            "portfolio_positions is optional and not configured; no reconciliation "
            "artifact is present. Configure IBKR Gateway/TWS and run "
            "`python scripts/ibkr_client.py reconcile` only when position analytics are required."
        )
    return f"{table} has {row_count:,} rows."


def _latest_date_message(table: str, latest: date, age_days: int, *, stale: bool) -> str:
    if stale and table == "performance_ledger":
        return (
            f"performance_ledger latest date is stale: {latest.isoformat()} ({age_days} days old). "
            "New rows require confirmed picks from a daily report; "
            "`python scripts/06_append_ledger.py` appends ranked picks, and "
            "`python scripts/07_verify_returns.py` fills 7/14/30/60D returns as windows mature."
        )
    if stale:
        return f"{table} latest date is stale: {latest.isoformat()} ({age_days} days old)."
    return f"{table} latest date is {latest.isoformat()} ({age_days} days old)."


def _table_health_checks(
    *,
    analytics_root: Path,
    today: date,
    max_staleness_days: int,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    catalog_rows = _query(
        """
        select table_name, table_type
        from information_schema.tables
        where table_schema = 'main'
        """,
        analytics_root=analytics_root,
    )
    catalog = {str(row["table_name"]): str(row["table_type"]) for row in catalog_rows}

    for table, date_col in DATE_COLUMNS.items():
        is_today_signal_core = table in TODAY_SIGNAL_CORE_TABLES
        if table not in catalog:
            missing_status = "BLOCK" if is_today_signal_core else "WARN"
            missing_action = "BLOCK_TODAY_SIGNALS" if is_today_signal_core else "REVIEW_REQUIRED"
            checks.append(_check(
                f"table:{table}:exists",
                missing_status,
                f"{table} is missing from analytics DuckDB.",
                table=table,
                recommended_action=missing_action,
            ))
            continue

        checks.append(_check(
            f"table:{table}:exists",
            "PASS",
            f"{table} exists as {catalog[table]}.",
            table=table,
            value=catalog[table],
        ))
        count_row = _query(f"select count(*) as rows from {analytics_store._sql_ident(table)}",
                           analytics_root=analytics_root)[0]
        row_count = int(count_row.get("rows") or 0)
        empty_status = "BLOCK" if is_today_signal_core else "WARN"
        empty_action = "BLOCK_TODAY_SIGNALS" if is_today_signal_core else "REVIEW_REQUIRED"
        portfolio_observation = (
            _source_observation(
                "portfolio_reconciliation", catalog=catalog, analytics_root=analytics_root,
            )
            if table == "portfolio_positions" else None
        )
        scanner_observation = (
            _source_observation(
                "watchlist_scanner", catalog=catalog, analytics_root=analytics_root,
            )
            if table == "watchlist_sources" else None
        )
        source_availability = str((portfolio_observation or {}).get("availability") or "unknown")
        optional_not_configured = (
            table == "portfolio_positions"
            and row_count <= 0
            and source_availability == "not_configured"
        )
        optional_configured_empty = (
            table == "portfolio_positions"
            and row_count <= 0
            and source_availability == "configured"
            and (portfolio_observation or {}).get("reachable") is not False
        )
        portfolio_source_problem = (
            table == "portfolio_positions"
            and (
                source_availability in {"invalid", "unknown"}
                or (portfolio_observation or {}).get("reachable") is False
            )
        )
        scanner_configured_empty = (
            table == "watchlist_sources"
            and row_count <= 0
            and str((scanner_observation or {}).get("availability")) == "configured"
        )
        if optional_not_configured:
            row_message = _empty_table_message(table, row_count)
        elif optional_configured_empty:
            row_message = (
                "portfolio reconciliation is configured and contains zero position rows; "
                "this is an observed empty portfolio, not a missing source."
            )
        elif portfolio_source_problem:
            row_message = (
                "portfolio reconciliation is configured but invalid, unreachable, or its "
                "source observation is unavailable."
            )
        elif scanner_configured_empty:
            row_message = (
                "watchlist scanner completed with zero ticker rows; scanner provenance and "
                "freshness remain available from source_observations."
            )
        else:
            row_message = _empty_table_message(table, row_count)
        row_pass = (
            (row_count > 0 and not portfolio_source_problem)
            or optional_not_configured
            or optional_configured_empty
            or scanner_configured_empty
        )
        row_check = _check(
            f"table:{table}:row_count",
            "PASS" if row_pass else empty_status,
            row_message,
            table=table,
            value=row_count,
            threshold=(
                "optional; >= 0"
                if optional_not_configured or optional_configured_empty
                else "> 0 or a configured empty scanner run"
                if scanner_configured_empty
                else "> 0"
            ),
            recommended_action=(
                "NO_ACTION" if row_pass else empty_action
            ),
            code="OPTIONAL_SOURCE_NOT_CONFIGURED" if optional_not_configured else None,
        )
        if optional_not_configured:
            row_check["availability"] = "not_configured"
            row_check["optional"] = True
        elif optional_configured_empty:
            row_check["availability"] = "configured_empty"
            row_check["optional"] = True
        elif scanner_configured_empty:
            row_check["availability"] = "configured_empty"
        elif portfolio_source_problem:
            row_check["availability"] = source_availability
        checks.append(row_check)
        scanner_requires_status = (
            table == "watchlist_sources"
            and str((scanner_observation or {}).get("availability")) == "invalid"
        )
        if (
            row_count <= 0
            and not optional_configured_empty
            and not scanner_configured_empty
            and not scanner_requires_status
        ):
            continue

        freshness_policy = None
        if table == "portfolio_positions" and optional_configured_empty:
            freshness_policy = "reconciliation_observation"
            latest_row = {"latest_date": (portfolio_observation or {}).get("source_date")}
        elif table == "watchlist_sources":
            scanner_availability = str(
                (scanner_observation or {}).get("availability") or "unknown"
            )
            if scanner_availability == "invalid":
                item = _check(
                    "table:watchlist_sources:latest_date",
                    "WARN",
                    "watchlist scanner artifact is present but invalid; freshness is unknown.",
                    table=table,
                    value="unknown",
                    threshold=f"<= {max_staleness_days} days old",
                    recommended_action="REVIEW_REQUIRED",
                    code="WATCHLIST_SCANNER_INVALID",
                )
                item["freshness_policy"] = "scanner_refresh"
                checks.append(item)
                continue
            if scanner_availability == "configured":
                freshness_policy = "scanner_refresh"
                latest_row = {"latest_date": scanner_observation.get("source_date")}
            else:
                latest_row = _query(
                    "select cast(max(try_cast(scan_date as date)) as varchar) as latest_date "
                    "from watchlist_sources",
                    analytics_root=analytics_root,
                )[0]
                latest = _date(latest_row.get("latest_date"))
                manual_ok = latest is not None and latest <= today
                item = _check(
                    "table:watchlist_sources:latest_date",
                    "PASS" if manual_ok else "WARN",
                    (
                        "watchlist_sources contains only an owner-maintained manual list; "
                        f"its latest revision is {(latest.isoformat() if latest else 'unknown')} "
                        + (
                            "and is not evaluated as a scanner refresh."
                            if manual_ok
                            else "but its revision date is missing or in the future."
                        )
                    ),
                    table=table,
                    value=latest.isoformat() if latest else "unknown",
                    threshold="manual revision; no scanner TTL",
                    recommended_action="NO_ACTION" if manual_ok else "REVIEW_REQUIRED",
                )
                item["freshness_policy"] = "manual_revision"
                checks.append(item)
                continue
        else:
            latest_sql = (
                f"select cast(max(try_cast({analytics_store._sql_ident(date_col)} as date)) as varchar) "
                f"as latest_date from {analytics_store._sql_ident(table)}"
            )
            latest_row = _query(latest_sql, analytics_root=analytics_root)[0]
        latest = _date(latest_row.get("latest_date"))
        if latest is None:
            checks.append(_check(
                f"table:{table}:latest_date",
                "WARN",
                f"{table} has rows but no parseable {date_col}.",
                table=table,
                recommended_action="REVIEW_REQUIRED",
            ))
            continue
        age_days = (today - latest).days
        if age_days < 0:
            status = "WARN"
            action = "REVIEW_REQUIRED"
            message = f"{table} latest date {latest.isoformat()} is in the future."
        elif age_days <= max_staleness_days:
            status = "PASS"
            action = "NO_ACTION"
            message = _latest_date_message(table, latest, age_days, stale=False)
        else:
            status = "WARN"
            action = "REVIEW_REQUIRED"
            message = _latest_date_message(table, latest, age_days, stale=True)
        latest_check = _check(
            f"table:{table}:latest_date",
            status,
            message,
            table=table,
            value=latest.isoformat(),
            threshold=f"<= {max_staleness_days} days old",
            recommended_action=action,
        )
        if freshness_policy:
            latest_check["freshness_policy"] = freshness_policy
        checks.append(latest_check)

    for table in SIGNAL_TABLES:
        if table not in catalog:
            continue
        rows = _query(
            f"select count(*) as rows from {analytics_store._sql_ident(table)} "
            "where source_file = 'latest.json'",
            analytics_root=analytics_root,
        )[0]
        latest_rows = int(rows.get("rows") or 0)
        checks.append(_check(
            f"table:{table}:no_latest_source",
            "PASS" if latest_rows == 0 else "WARN",
            f"{table} has {latest_rows} rows from latest.json.",
            table=table,
            value=latest_rows,
            threshold="= 0",
            recommended_action="NO_ACTION" if latest_rows == 0 else "REVIEW_REQUIRED",
        ))

    return checks


def _latest_table_date(*, table: str, date_col: str, analytics_root: Path) -> date | None:
    rows = _query(
        f"select cast(max(try_cast({analytics_store._sql_ident(date_col)} as date)) as varchar) "
        f"as latest_date from {analytics_store._sql_ident(table)}",
        analytics_root=analytics_root,
    )
    return _date((rows[0] if rows else {}).get("latest_date"))


def _fresh_data_check(
    *,
    table: str,
    date_col: str,
    check_id: str,
    today: date,
    analytics_root: Path,
    max_age_days: int,
    code: str,
) -> dict[str, Any] | None:
    try:
        latest = _latest_table_date(table=table, date_col=date_col, analytics_root=analytics_root)
    except Exception:
        return None
    if latest is None:
        return _check(
            check_id,
            "WARN",
            f"{table} has no parseable {date_col} for data-source freshness.",
            table=table,
            recommended_action="REVIEW_REQUIRED",
            code=code,
        )
    age_days = (today - latest).days
    if age_days < 0:
        return _check(
            check_id,
            "WARN",
            f"{table} latest date {latest.isoformat()} is in the future.",
            table=table,
            value=latest.isoformat(),
            recommended_action="REVIEW_REQUIRED",
            code=code,
        )
    return _check(
        check_id,
        "PASS" if age_days <= max_age_days else "WARN",
        (
            f"{table} latest data-source date is {latest.isoformat()} ({age_days} days old)."
            if age_days <= max_age_days
            else f"{table} latest data-source date is stale: {latest.isoformat()} ({age_days} days old)."
        ),
        table=table,
        value=latest.isoformat(),
        threshold=f"<= {max_age_days} days old",
        recommended_action="NO_ACTION" if age_days <= max_age_days else "REVIEW_REQUIRED",
        code=None if age_days <= max_age_days else code,
    )


def _money_flow_coverage_check(*, analytics_root: Path, min_coverage: float = 0.70) -> dict[str, Any] | None:
    try:
        rows = _query(
            """
            with latest as (
              select max(try_cast(as_of_date as date)) as as_of
              from daily_money_flow
            )
            select
              max(try_cast(coverage_ratio as double)) as coverage_ratio,
              max(case when coalesce(publishable, false) then 1 else 0 end) as publishable
            from daily_money_flow, latest
            where try_cast(as_of_date as date) = latest.as_of
            """,
            analytics_root=analytics_root,
        )
    except Exception:
        return None
    row = rows[0] if rows else {}
    coverage = row.get("coverage_ratio")
    try:
        coverage_value = float(coverage)
    except (TypeError, ValueError):
        coverage_value = 0.0
    publishable = bool(row.get("publishable"))
    ok = coverage_value >= min_coverage and publishable
    return _check(
        "data:daily_money_flow:coverage",
        "PASS" if ok else "WARN",
        (
            f"daily_money_flow latest coverage is {coverage_value:.0%} and publishable."
            if ok
            else f"daily_money_flow latest coverage is {coverage_value:.0%}; keep Eastmoney money flow review-only."
        ),
        table="daily_money_flow",
        value=round(coverage_value, 4),
        threshold=f">= {min_coverage:.0%} and publishable",
        recommended_action="NO_ACTION" if ok else "REVIEW_REQUIRED",
        code=None if ok else "MONEY_FLOW_UNPUBLISHABLE",
    )


def _trade_state_role_tag_check(*, analytics_root: Path) -> dict[str, Any] | None:
    try:
        rows = _query(
            """
            with latest as (
              select max(try_cast(as_of_date as date)) as as_of
              from trade_state_snapshots
            )
            select
              count(*) as total,
              sum(case
                    when coalesce(industry_role, '') = ''
                      or industry_role = '未分類'
                      or coalesce(industry_role_status, '') = 'unclassified'
                    then 1 else 0
                  end) as missing
            from trade_state_snapshots, latest
            where try_cast(as_of_date as date) = latest.as_of
            """,
            analytics_root=analytics_root,
        )
    except Exception:
        return None
    row = rows[0] if rows else {}
    total = int(row.get("total") or 0)
    missing = int(row.get("missing") or 0)
    ok = total > 0 and missing == 0
    return _check(
        "data:trade_state_snapshots:role_tags",
        "PASS" if ok else "WARN",
        (
            f"trade_state_snapshots latest rows all have role tags ({total:,} rows)."
            if ok
            else f"trade_state_snapshots latest rows missing role tags: {missing:,}/{total:,}."
        ),
        table="trade_state_snapshots",
        value={"total": total, "missing": missing},
        threshold="missing = 0",
        recommended_action="NO_ACTION" if ok else "REVIEW_REQUIRED",
        code=None if ok else "ROLE_TAG_MISSING",
    )


def _data_quality_checks(*, analytics_root: Path, today: date) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in (
        _fresh_data_check(
            table="universe_snapshots",
            date_col="as_of_date",
            check_id="data:universe_snapshots:freshness",
            today=today,
            analytics_root=analytics_root,
            max_age_days=3,
            code="UNIVERSE_REFRESH_FAILED",
        ),
        _fresh_data_check(
            table="daily_bars",
            date_col="bar_date",
            check_id="data:daily_bars:freshness",
            today=today,
            analytics_root=analytics_root,
            max_age_days=3,
            code="DATA_SOURCE_STALE",
        ),
        _money_flow_coverage_check(analytics_root=analytics_root),
        _trade_state_role_tag_check(analytics_root=analytics_root),
    ):
        if item is not None:
            checks.append(item)
    return checks


def _no_confirmed_picks_check(*, analytics_root: Path, today: date) -> dict[str, Any] | None:
    try:
        rows = _query(
            """
            select cast(max(try_cast(scan_date as date)) as varchar) as latest_pick_date
            from performance_ledger
            """,
            analytics_root=analytics_root,
        )
    except Exception:
        return None
    latest = _date((rows[0] if rows else {}).get("latest_pick_date"))
    if latest is None:
        return None
    try:
        report_rows = _query(
            f"""
            select
              count(*) as published_scans,
              sum(case when try_cast(total_confirmed as double) = 0
                       then 1 else 0 end) as successful_zero_pick,
              sum(case when try_cast(total_confirmed as double) > 0
                       then 1 else 0 end) as successful_with_picks,
              sum(case when try_cast(total_confirmed as double) is null
                            or try_cast(total_confirmed as double) < 0
                       then 1 else 0 end) as published_unclassified,
              cast(max(case when try_cast(total_confirmed as double) > 0
                            then try_cast(report_date as date) end) as varchar)
                       as latest_report_pick_date,
              cast(max(try_cast(report_date as date)) as varchar) as latest_report_date
            from daily_reports
            where try_cast(report_date as date) > cast('{latest.isoformat()}' as date)
              and try_cast(report_date as date) <= cast('{today.isoformat()}' as date)
            """,
            analytics_root=analytics_root,
        )
    except Exception:
        return None
    report_row = report_rows[0] if report_rows else {}
    published = int(report_row.get("published_scans") or 0)
    zero_pick_scans = int(report_row.get("successful_zero_pick") or 0)
    scans_with_picks = int(report_row.get("successful_with_picks") or 0)
    unclassified_reports = int(report_row.get("published_unclassified") or 0)
    state_counts = {
        "successful_zero_pick": zero_pick_scans,
        "successful_with_picks": scans_with_picks,
        "published_unclassified": unclassified_reports,
        "missing": None,
        "failed": None,
        "unpublished": None,
    }

    def with_run_evidence(item: dict[str, Any]) -> dict[str, Any]:
        item["latest_pick_date"] = latest.isoformat()
        item["latest_report_date"] = report_row.get("latest_report_date")
        item["published_scans_since_pick"] = published
        item["scan_state_counts"] = state_counts
        item["run_coverage_status"] = "UNKNOWN"
        item["notification_bucket"] = zero_pick_scans // 5
        return item

    coverage_note = (
        f" {unclassified_reports} published reports have unclassified outcomes."
        if unclassified_reports else ""
    ) + " Missing, failed, and unpublished run counts are unknown without EOD run telemetry."
    if scans_with_picks:
        return with_run_evidence(_check(
            "performance:ledger_report_sync",
            "WARN",
            (
                f"{scans_with_picks} published reports contain confirmed picks after the "
                f"latest ledger date {latest.isoformat()} (latest report pick: "
                f"{report_row.get('latest_report_pick_date') or 'unknown'}). Reconcile the "
                "ledger/report mismatch before evaluating a no-picks streak."
            ),
            table="performance_ledger",
            value=scans_with_picks,
            threshold="0 published reports with picks after latest ledger date",
            recommended_action="REVIEW_REQUIRED",
            code="PERFORMANCE_LEDGER_REPORT_MISMATCH",
        ))
    if zero_pick_scans >= 10:
        item = _check(
            "performance:no_confirmed_picks_streak",
            "WARN",
            (
                f"No confirmed picks across {zero_pick_scans} successful published scans "
                f"since {latest.isoformat()}. Send TG REVIEW_REQUIRED and review screener "
                f"strictness, data freshness, and market regime.{coverage_note}"
            ),
            table="performance_ledger",
            value=zero_pick_scans,
            threshold=">= 10 successful published scans",
            recommended_action="REVIEW_REQUIRED",
        )
        item["notify_threshold"] = 10
        return with_run_evidence(item)
    if zero_pick_scans >= 5:
        item = _check(
            "performance:no_confirmed_picks_streak",
            "WARN",
            (
                f"No confirmed picks across {zero_pick_scans} successful published scans "
                f"since {latest.isoformat()}. Send TG WARN; keep monitoring before changing "
                f"scoring weights.{coverage_note}"
            ),
            table="performance_ledger",
            value=zero_pick_scans,
            threshold=">= 5 successful published scans",
            recommended_action="TG_WARN",
        )
        item["notify_threshold"] = 5
        return with_run_evidence(item)
    return with_run_evidence(_check(
        "performance:no_confirmed_picks_streak",
        "PASS",
        (
            f"{zero_pick_scans} successful published scans have zero confirmed picks "
            f"since {latest.isoformat()}.{coverage_note}"
        ),
        table="performance_ledger",
        value=zero_pick_scans,
        threshold="< 5 successful published scans",
    ))


def _repeat_signals(
    *,
    analytics_root: Path,
    today: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    since_expr = f"cast('{today.isoformat()}' as date) - ({int(lookback_days)} * interval '1 day')"

    specs = [
        {
            "table": "options_flow_signals",
            "category": "options_flow_repeats",
            "score": "flow_score",
            "action": "WATCHLIST_UPGRADE",
            "message": "Options flow repeated inside the lookback window.",
            "extra": "sum(coalesce(try_cast(est_notional_usd as double), 0)) as total_notional_usd",
        },
        {
            "table": "reversal_radar_signals",
            "category": "reversal_radar_repeats",
            "score": "reversal_score",
            "action": "REVIEW_REQUIRED",
            "message": "Reversal radar repeated; keep human review because this lane is exploratory.",
            "extra": "sum(case when coalesce(exploratory, false) then 1 else 0 end) as exploratory_rows",
        },
        {
            "table": "oversold_reversal_signals",
            "category": "oversold_reversal_repeats",
            "score": "rsi14",
            "action": "REVIEW_REQUIRED",
            "message": "Oversold reversal repeated; keep as review-only confirmation.",
            "extra": "avg(try_cast(rsi14 as double)) as avg_rsi14",
        },
        {
            "table": "risk_guard_rows",
            "category": "risk_guard_repeats",
            "score": "risk_score",
            "action": "REVIEW_REQUIRED",
            "message": "Risk Guard reduce/exit warning repeated; review exposure before adding risk.",
            "extra": (
                "sum(case when upper(coalesce(status, '')) in ('REDUCE', 'EXIT') "
                "then 1 else 0 end) as high_risk_rows"
            ),
            "where": "and upper(coalesce(status, '')) in ('REDUCE', 'EXIT')",
        },
    ]
    for spec in specs:
        table = spec["table"]
        try:
            rows = _query(
                f"""
                select
                  ticker,
                  count(*) as rows_seen,
                  count(distinct as_of_date) as days_seen,
                  cast(min(try_cast(as_of_date as date)) as varchar) as first_seen,
                  cast(max(try_cast(as_of_date as date)) as varchar) as last_seen,
                  max(try_cast({analytics_store._sql_ident(spec["score"])} as double)) as max_score,
                  {spec["extra"]}
                from {analytics_store._sql_ident(table)}
                where coalesce(ticker, '') <> ''
                  and try_cast(as_of_date as date) >= {since_expr}
                  {spec.get("where", "")}
                group by ticker
                having count(distinct as_of_date) >= 2
                order by days_seen desc, max_score desc nulls last, ticker
                limit 25
                """,
                analytics_root=analytics_root,
            )
        except Exception:
            continue
        for row in rows:
            signals.append({
                "category": spec["category"],
                "ticker": str(row.get("ticker") or "").upper(),
                "status": "PASS",
                "recommended_action": spec["action"],
                "message": spec["message"],
                "evidence": {
                    "lookback_days": lookback_days,
                    "rows_seen": int(row.get("rows_seen") or 0),
                    "days_seen": int(row.get("days_seen") or 0),
                    "first_seen": row.get("first_seen"),
                    "last_seen": row.get("last_seen"),
                    "max_score": row.get("max_score"),
                    **{
                        k: v
                        for k, v in row.items()
                        if k not in {"ticker", "rows_seen", "days_seen", "first_seen", "last_seen", "max_score"}
                    },
                },
            })
    return signals


def _performance_check(
    *,
    analytics_root: Path,
    min_rows: int,
) -> dict[str, Any]:
    try:
        rows = _query(
            """
            select
              count(*) as rows,
              avg(try_cast(fwd_30d_return as double)) as avg_fwd_30d_return,
              avg(case
                    when lower(cast(hit_15pct_within_30d as varchar)) in ('true', '1', 'yes')
                    then 1.0
                    when lower(cast(hit_15pct_within_30d as varchar)) in ('false', '0', 'no')
                    then 0.0
                    else null
                  end) as hit_15pct_within_30d_rate
            from performance_ledger
            """,
            analytics_root=analytics_root,
        )
    except Exception as e:  # noqa: BLE001
        return {
            "status": "WARN",
            "recommended_action": "REVIEW_REQUIRED",
            "message": f"performance_ledger is unreadable: {e}",
            "rows": 0,
            "min_rows": min_rows,
        }
    row = rows[0] if rows else {}
    count = int(row.get("rows") or 0)
    status = "PASS" if count >= min_rows else "WARN"
    return {
        "status": status,
        "recommended_action": "NO_ACTION" if status == "PASS" else "REVIEW_REQUIRED",
        "message": (
            "Performance sample is large enough for routine validation."
            if status == "PASS"
            else (
                f"Performance sample has {count:,} rows; keep signal weighting review-only until "
                f"{min_rows:,}+ rows. At 100+ rows of raw samples, review preliminary trend only; "
                "consider scoring-weight changes only after 100+ resolved 30D outcomes. "
                "Do not draw strong medium-term conclusions before 60D outcomes mature."
            )
        ),
        "rows": count,
        "min_rows": min_rows,
        "avg_fwd_30d_return": row.get("avg_fwd_30d_return"),
        "hit_15pct_within_30d_rate": row.get("hit_15pct_within_30d_rate"),
    }


def _next_actions(
    *,
    recommended_action: str,
    today_signal_readiness: dict[str, Any],
    checks: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    performance: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if today_signal_readiness.get("can_publish") is False:
        actions.append({
            "action": "BLOCK_TODAY_SIGNALS",
            "reason": today_signal_readiness.get("message"),
            "requires_human": False,
        })
    for check in checks:
        if check.get("status") == "WARN":
            action = check.get("recommended_action", "REVIEW_REQUIRED")
            actions.append({
                "action": action,
                "reason": check.get("message"),
                "requires_human": action != "TG_WARN",
            })
    if performance.get("status") == "WARN":
        actions.append({
            "action": performance.get("recommended_action", "REVIEW_REQUIRED"),
            "reason": performance.get("message"),
            "requires_human": True,
        })
    for signal in signals[:10]:
        actions.append({
            "action": signal.get("recommended_action", "NO_ACTION"),
            "reason": f"{signal.get('ticker')} {signal.get('message')}",
            "requires_human": signal.get("recommended_action") != "WATCHLIST_UPGRADE",
        })
    if not actions:
        actions.append({
            "action": recommended_action,
            "reason": "Analytics DB checks passed without follow-up items.",
            "requires_human": False,
        })
    return actions


def _is_today_signal_blocker(check: dict[str, Any]) -> bool:
    if check.get("status") != "BLOCK":
        return False
    check_id = str(check.get("id") or "")
    if check_id in {"db:exists", "db:readable"}:
        return True
    for table in TODAY_SIGNAL_CORE_TABLES:
        if check_id in {
            f"table:{table}:exists",
            f"table:{table}:row_count",
        }:
            return True
    return False


def _today_signal_readiness(
    checks: list[dict[str, Any]],
    performance: dict[str, Any],
) -> dict[str, Any]:
    blocking = [str(item.get("id")) for item in checks if _is_today_signal_blocker(item)]
    warnings = [
        str(item.get("id"))
        for item in checks
        if item.get("status") == "WARN" and str(item.get("id")) not in blocking
    ]
    if performance.get("status") == "WARN":
        warnings.append("performance:validation")
    if blocking:
        return {
            "can_publish": False,
            "status": "BLOCK",
            "recommended_action": "BLOCK_TODAY_SIGNALS",
            "message": (
                "今日訊號核心資料缺失，暫停發布；"
                "請先重新產生候選排序，或重建 Analytics DB 後再檢查。"
            ),
            "blocking_check_ids": blocking,
            "warning_check_ids": warnings,
        }
    if warnings:
        return {
            "can_publish": True,
            "status": "WARN",
            "recommended_action": "REVIEW_REQUIRED",
            "message": "今日訊號可發布，但部分增強資料或驗證資料需人工檢查。",
            "blocking_check_ids": [],
            "warning_check_ids": warnings,
        }
    return {
        "can_publish": True,
        "status": "PASS",
        "recommended_action": "NO_ACTION",
        "message": "今日訊號可發布；核心資料與資料健康檢查通過。",
        "blocking_check_ids": [],
        "warning_check_ids": [],
    }


def _warning_codes(checks: list[dict[str, Any]]) -> list[str]:
    codes = {
        str(item.get("code"))
        for item in checks
        if item.get("code") and item.get("status") != "PASS"
    }
    return sorted(codes)


def _write_output(result: dict[str, Any], output_path: str | Path | None) -> None:
    path = Path(output_path or DEFAULT_OUTPUT).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def run_checks(
    *,
    analytics_root: str | Path | None = None,
    output_path: str | Path | None = None,
    today: str | date | None = None,
    max_staleness_days: int = 7,
    signal_lookback_days: int = 14,
    min_performance_rows: int = 20,
) -> dict[str, Any]:
    """Run analytics checks, publish JSON, and return the result."""
    root = analytics_store.analytics_dir(analytics_root)
    check_date = _today(today)
    db_path = analytics_store.duckdb_path(root)
    checks: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    if not db_path.is_file():
        checks.append(_check(
            "db:exists",
            "BLOCK",
            f"Analytics DuckDB file is missing: {db_path}",
            value=str(db_path),
            recommended_action="BLOCK_TODAY_SIGNALS",
        ))
        performance = {
            "status": "BLOCK",
            "recommended_action": "BLOCK_TODAY_SIGNALS",
            "message": "Performance validation cannot run because the DuckDB file is missing.",
            "rows": 0,
            "min_rows": min_performance_rows,
        }
    else:
        checks.append(_check(
            "db:exists",
            "PASS",
            f"Analytics DuckDB file exists: {db_path}",
            value=str(db_path),
        ))
        try:
            checks.extend(_table_health_checks(
                analytics_root=root,
                today=check_date,
                max_staleness_days=max_staleness_days,
            ))
            checks.extend(_data_quality_checks(
                analytics_root=root,
                today=check_date,
            ))
            no_picks_check = _no_confirmed_picks_check(
                analytics_root=root,
                today=check_date,
            )
            if no_picks_check:
                checks.append(no_picks_check)
            signals = _repeat_signals(
                analytics_root=root,
                today=check_date,
                lookback_days=signal_lookback_days,
            )
            performance = _performance_check(
                analytics_root=root,
                min_rows=min_performance_rows,
            )
        except Exception as e:  # noqa: BLE001
            checks.append(_check(
                "db:readable",
                "BLOCK",
                f"Analytics DuckDB checks failed: {e}",
                value=str(db_path),
                recommended_action="BLOCK_TODAY_SIGNALS",
            ))
            performance = {
                "status": "BLOCK",
                "recommended_action": "BLOCK_TODAY_SIGNALS",
                "message": "Performance validation cannot run because the DuckDB checks failed.",
                "rows": 0,
                "min_rows": min_performance_rows,
            }

    status = _overall_status(checks, performance)
    recommended_action = _overall_action(checks, signals, performance)
    today_signal_readiness = _today_signal_readiness(checks, performance)
    result = {
        "generated_at": _utc_now(),
        "analytics_root": str(root),
        "duckdb_path": str(db_path),
        "as_of_date": check_date.isoformat(),
        "status": status,
        "recommended_action": recommended_action,
        "today_signal_readiness": today_signal_readiness,
        "summary": _summary(checks),
        "checks": checks,
        "warning_codes": _warning_codes(checks),
        "signals": signals,
        "performance": performance,
        "next_actions": [],
    }
    result["next_actions"] = _next_actions(
        recommended_action=recommended_action,
        today_signal_readiness=today_signal_readiness,
        checks=checks,
        signals=signals,
        performance=performance,
    )
    _write_output(result, output_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run automated analytics DB checks")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run checks and write latest JSON")
    p_run.add_argument("--analytics-dir", default=None)
    p_run.add_argument("--output", default=str(DEFAULT_OUTPUT))
    p_run.add_argument("--today", default=None)
    p_run.add_argument("--max-staleness-days", type=int, default=7)
    p_run.add_argument("--signal-lookback-days", type=int, default=14)
    p_run.add_argument("--min-performance-rows", type=int, default=20)
    p_run.add_argument("--allow-block", action="store_true",
                       help="write BLOCK reports without returning a failing exit code")

    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_checks(
            analytics_root=args.analytics_dir,
            output_path=args.output,
            today=args.today,
            max_staleness_days=args.max_staleness_days,
            signal_lookback_days=args.signal_lookback_days,
            min_performance_rows=args.min_performance_rows,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True, default=str))
        return 0 if args.allow_block or result["status"] != "BLOCK" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
