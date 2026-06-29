#!/usr/bin/env python3
"""DuckDB + Parquet analytics store for historical report data.

This is an opt-in read model. Existing JSON/CSV reports stay the source of truth;
this module exports selected append/history-shaped artifacts into Parquet and
creates DuckDB views over those files for fast cross-date queries.
"""

from __future__ import annotations

import argparse
import json
import os
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
KNOWN_VIEWS = {
    "performance_ledger": "performance_ledger.parquet",
    "iv_history": "iv_history.parquet",
}


def analytics_dir(analytics_root: str | Path | None = None) -> Path:
    """Resolve the analytics data root.

    Local runs default to reports/analytics. Deployed runs can set
    SURGE_ANALYTICS_DIR directly, or use SURGE_APP_ROOT so the store lands under
    the deployment's shared data directory.
    """
    if analytics_root is not None:
        return Path(analytics_root).expanduser()
    if os.environ.get("SURGE_ANALYTICS_DIR"):
        return Path(os.environ["SURGE_ANALYTICS_DIR"]).expanduser()
    if os.environ.get("SURGE_APP_ROOT"):
        return Path(os.environ["SURGE_APP_ROOT"]).expanduser() / "shared" / "data"
    return REPORTS_DIR / "analytics"


def parquet_dir(analytics_root: str | Path | None = None) -> Path:
    return analytics_dir(analytics_root) / "parquet"


def duckdb_path(analytics_root: str | Path | None = None) -> Path:
    return analytics_dir(analytics_root) / "analytics.duckdb"


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _write_parquet(df: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, out)


def export_performance_ledger(
    csv_path: str | Path = REPORTS_DIR / "performance_ledger.csv",
    *,
    analytics_root: str | Path | None = None,
) -> dict[str, Any]:
    """Export reports/performance_ledger.csv to Parquet and refresh views."""
    src = Path(csv_path)
    if src.is_file():
        df = pd.read_csv(src)
    else:
        df = pd.DataFrame(columns=PERFORMANCE_LEDGER_COLUMNS)
    out = parquet_dir(analytics_root) / KNOWN_VIEWS["performance_ledger"]
    _write_parquet(df, out)
    refresh_views(analytics_root)
    return {"source": str(src), "path": str(out), "rows": int(len(df))}


def export_iv_history(
    iv_dir: str | Path = REPORTS_DIR / "iv_history",
    *,
    analytics_root: str | Path | None = None,
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
    out = parquet_dir(analytics_root) / KNOWN_VIEWS["iv_history"]
    _write_parquet(df, out)
    refresh_views(analytics_root)
    return {"source": str(src_dir), "path": str(out), "rows": int(len(df))}


def refresh_views(analytics_root: str | Path | None = None) -> dict[str, str]:
    """Create/replace DuckDB views for every known Parquet artifact present."""
    root = analytics_dir(analytics_root)
    root.mkdir(parents=True, exist_ok=True)
    db = duckdb_path(root)
    created: dict[str, str] = {}
    con = duckdb.connect(str(db))
    try:
        for view, filename in KNOWN_VIEWS.items():
            path = parquet_dir(root) / filename
            if not path.is_file():
                continue
            con.execute(
                f"create or replace view {view} as "
                f"select * from read_parquet('{_sql_path(path)}')"
            )
            created[view] = str(path)
    finally:
        con.close()
    return created


def query(sql: str, *, analytics_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Run a DuckDB query after refreshing views. Returns rows as dictionaries."""
    root = analytics_dir(analytics_root)
    refresh_views(root)
    con = duckdb.connect(str(duckdb_path(root)), read_only=True)
    try:
        result = con.execute(sql)
        columns = [d[0] for d in (result.description or [])]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()


def refresh_all(
    *,
    reports_root: str | Path = REPORTS_DIR,
    analytics_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    reports = Path(reports_root)
    return {
        "performance_ledger": export_performance_ledger(
            reports / "performance_ledger.csv",
            analytics_root=analytics_root,
        ),
        "iv_history": export_iv_history(
            reports / "iv_history",
            analytics_root=analytics_root,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DuckDB/Parquet analytics store")
    sub = parser.add_subparsers(dest="command", required=True)

    p_refresh = sub.add_parser("refresh", help="export known reports into Parquet")
    p_refresh.add_argument("--reports-dir", default=str(REPORTS_DIR))
    p_refresh.add_argument("--analytics-dir", default=None)

    p_query = sub.add_parser("query", help="run a SQL query against analytics views")
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
