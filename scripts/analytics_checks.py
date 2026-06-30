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
    "performance_ledger": "scan_date",
    "iv_history": "as_of_date",
    "options_flow_signals": "as_of_date",
    "reversal_radar_signals": "as_of_date",
    "oversold_reversal_signals": "as_of_date",
    "market_thesis_forecasts": "as_of_date",
    "candidate_scores": "scan_date",
    "candidate_rankings": "scan_date",
    "risk_guard_rows": "as_of_date",
    "signal_outcomes": "as_of_date",
    "run_status_history": "started_at",
}
MATURITY_TABLES = {
    "candidate_scores",
    "candidate_rankings",
    "risk_guard_rows",
    "signal_outcomes",
    "run_status_history",
}
SIGNAL_TABLES = (
    "options_flow_signals",
    "reversal_radar_signals",
    "oversold_reversal_signals",
)
ACTION_RANK = {
    "NO_ACTION": 0,
    "WATCHLIST_UPGRADE": 1,
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
    return item


def _query(sql: str, *, analytics_root: Path) -> list[dict[str, Any]]:
    return analytics_store.query(sql, analytics_root=analytics_root)


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
        if table not in catalog:
            checks.append(_check(
                f"table:{table}:exists",
                "BLOCK",
                f"{table} is missing from analytics DuckDB.",
                table=table,
                recommended_action="BLOCK_TODAY_SIGNALS",
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
        empty_status = "WARN" if table in MATURITY_TABLES else "BLOCK"
        empty_action = "REVIEW_REQUIRED" if table in MATURITY_TABLES else "BLOCK_TODAY_SIGNALS"
        checks.append(_check(
            f"table:{table}:row_count",
            "PASS" if row_count > 0 else empty_status,
            f"{table} has {row_count:,} rows.",
            table=table,
            value=row_count,
            threshold="> 0",
            recommended_action="NO_ACTION" if row_count > 0 else empty_action,
        ))
        if row_count <= 0:
            continue

        latest_row = _query(
            f"select cast(max(try_cast({analytics_store._sql_ident(date_col)} as date)) as varchar) "
            f"as latest_date from {analytics_store._sql_ident(table)}",
            analytics_root=analytics_root,
        )[0]
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
            message = f"{table} latest date is {latest.isoformat()} ({age_days} days old)."
        else:
            status = "WARN"
            action = "REVIEW_REQUIRED"
            message = f"{table} latest date is stale: {latest.isoformat()} ({age_days} days old)."
        checks.append(_check(
            f"table:{table}:latest_date",
            status,
            message,
            table=table,
            value=latest.isoformat(),
            threshold=f"<= {max_staleness_days} days old",
            recommended_action=action,
        ))

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
            "PASS" if latest_rows == 0 else "BLOCK",
            f"{table} has {latest_rows} rows from latest.json.",
            table=table,
            value=latest_rows,
            threshold="= 0",
            recommended_action="NO_ACTION" if latest_rows == 0 else "BLOCK_TODAY_SIGNALS",
        ))

    return checks


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
            "status": "BLOCK",
            "recommended_action": "BLOCK_TODAY_SIGNALS",
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
            else f"Performance sample has {count:,} rows; keep signal weighting review-only until {min_rows:,}+ rows."
        ),
        "rows": count,
        "min_rows": min_rows,
        "avg_fwd_30d_return": row.get("avg_fwd_30d_return"),
        "hit_15pct_within_30d_rate": row.get("hit_15pct_within_30d_rate"),
    }


def _next_actions(
    *,
    status: str,
    recommended_action: str,
    checks: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    performance: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if status == "BLOCK":
        actions.append({
            "action": "BLOCK_TODAY_SIGNALS",
            "reason": "One or more required analytics tables failed hard checks.",
            "requires_human": False,
        })
    for check in checks:
        if check.get("status") == "WARN":
            actions.append({
                "action": check.get("recommended_action", "REVIEW_REQUIRED"),
                "reason": check.get("message"),
                "requires_human": True,
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
    result = {
        "generated_at": _utc_now(),
        "analytics_root": str(root),
        "duckdb_path": str(db_path),
        "as_of_date": check_date.isoformat(),
        "status": status,
        "recommended_action": recommended_action,
        "summary": _summary(checks),
        "checks": checks,
        "signals": signals,
        "performance": performance,
        "next_actions": [],
    }
    result["next_actions"] = _next_actions(
        status=status,
        recommended_action=recommended_action,
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
