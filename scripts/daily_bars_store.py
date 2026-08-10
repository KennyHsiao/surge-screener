#!/usr/bin/env python3
"""Build daily OHLCV bar artifacts for analytics and validation.

Yahoo adjusted bars stay the preferred return-calculation source. Sina daily
bars are a long-history/fallback source and are used to cross-check latest close
before publishing Yahoo as primary.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd
import duckdb

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
sys.path.insert(0, str(REPO / "scripts"))

try:
    import global_stock_data as gsd
except ImportError:  # imported as scripts.daily_bars_store
    from scripts import global_stock_data as gsd


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
DAILY_BAR_FLOAT_COLUMNS = {"open", "high", "low", "close", "adj_close"}
DAILY_BAR_INTEGER_COLUMNS = {"volume", "source_priority"}
DAILY_BAR_BUSINESS_COLUMNS = [
    "open", "high", "low", "close", "adj_close", "volume", "source",
    "is_adjusted", "source_priority", "data_quality_status",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _int(value: Any) -> int | None:
    n = _num(value)
    return None if n is None else int(n)


def _bar_date(row: dict[str, Any]) -> str | None:
    return str(row.get("date") or row.get("bar_date") or row.get("Date") or "")[:10] or None


def _raw_blob(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)


def _normalize_bars(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
        if not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()
        return df.to_dict("records")
    if isinstance(rows, dict) and isinstance(rows.get("bars"), list):
        return [r for r in rows["bars"] if isinstance(r, dict)]
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def _latest_close(rows: list[dict[str, Any]]) -> float | None:
    dated = [(str(_bar_date(r) or ""), _num(r.get("close") or r.get("Close"))) for r in rows]
    dated = [(d, c) for d, c in dated if d and c is not None]
    if not dated:
        return None
    return sorted(dated, key=lambda x: x[0])[-1][1]


def compare_latest_close(yahoo_close: float | None, sina_close: float | None) -> str:
    if yahoo_close is None:
        return "fallback"
    if sina_close is None:
        return "ok"
    if yahoo_close == 0:
        return "mismatch_blocked"
    diff_pct = abs(yahoo_close - sina_close) / abs(yahoo_close) * 100.0
    if diff_pct < 1.0:
        return "ok"
    if diff_pct <= 3.0:
        return "mismatch_warning"
    return "mismatch_blocked"


def _row(
    *,
    as_of_date: str,
    generated_at: str,
    ticker: str,
    source: str,
    source_priority: int,
    is_adjusted: bool,
    data_quality_status: str,
    raw: dict[str, Any],
) -> dict[str, Any] | None:
    bar_date = _bar_date(raw)
    if not bar_date:
        return None
    return {
        "source_file": f"{as_of_date}.parquet",
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "ticker": ticker.upper(),
        "bar_date": bar_date,
        "open": _num(raw.get("open") or raw.get("Open")),
        "high": _num(raw.get("high") or raw.get("High")),
        "low": _num(raw.get("low") or raw.get("Low")),
        "close": _num(raw.get("close") or raw.get("Close")),
        "adj_close": _num(raw.get("adj_close") or raw.get("Adj Close") or raw.get("AdjClose")),
        "volume": _int(raw.get("volume") or raw.get("Volume")),
        "source": source,
        "is_adjusted": is_adjusted,
        "source_priority": source_priority,
        "data_quality_status": data_quality_status,
        "raw_bar_json": _raw_blob(raw),
    }


def _yfinance_bars(ticker: str, period: str = "20y") -> list[dict[str, Any]]:
    import yfinance as yf

    df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if df is None or df.empty:
        return []
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date.astype("string")
    return df.to_dict("records")


def _sina_bars(ticker: str) -> list[dict[str, Any]]:
    out = gsd.sina_us_daily_bars(ticker, num=6000)
    return out.get("bars") if isinstance(out.get("bars"), list) else []


def build_daily_bars_rows(
    tickers: Iterable[str],
    *,
    as_of_date: str | None = None,
    generated_at: str | None = None,
    yahoo_fetcher: Callable[[str], Any] = _yfinance_bars,
    sina_fetcher: Callable[[str], Any] = _sina_bars,
) -> list[dict[str, Any]]:
    as_of = as_of_date or _today()
    generated = generated_at or _now_iso()
    rows: list[dict[str, Any]] = []

    for ticker_raw in tickers:
        ticker = str(ticker_raw or "").upper().strip().removeprefix("$")
        if not ticker:
            continue
        try:
            yahoo_rows = _normalize_bars(yahoo_fetcher(ticker))
        except Exception:
            yahoo_rows = []
        try:
            sina_rows = _normalize_bars(sina_fetcher(ticker))
        except Exception:
            sina_rows = []

        status = compare_latest_close(_latest_close(yahoo_rows), _latest_close(sina_rows))
        if yahoo_rows and status != "mismatch_blocked":
            for raw in yahoo_rows:
                row = _row(
                    as_of_date=as_of,
                    generated_at=generated,
                    ticker=ticker,
                    source="yfinance",
                    source_priority=1,
                    is_adjusted=True,
                    data_quality_status=status,
                    raw=raw,
                )
                if row:
                    rows.append(row)
            continue

        fallback_status = "mismatch_blocked" if yahoo_rows else "fallback"
        for raw in sina_rows:
            row = _row(
                as_of_date=as_of,
                generated_at=generated,
                ticker=ticker,
                source="sina_us_daily_bars",
                source_priority=2,
                is_adjusted=False,
                data_quality_status=fallback_status,
                raw=raw,
            )
            if row:
                row["adj_close"] = None
                rows.append(row)
    return rows


def _daily_bar_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=DAILY_BAR_COLUMNS)
    for column in DAILY_BAR_STRING_COLUMNS:
        df[column] = df[column].astype("string")
    for column in DAILY_BAR_BOOL_COLUMNS:
        df[column] = df[column].astype("boolean")
    for column in DAILY_BAR_FLOAT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("float64")
    for column in DAILY_BAR_INTEGER_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    return df


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _column_list(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return ", ".join(f'{prefix}"{column}"' for column in DAILY_BAR_COLUMNS)


def _incoming_cte(path: Path) -> str:
    return f"""
        incoming as (
            select {_column_list()}
            from read_parquet('{_sql_path(path)}')
            qualify row_number() over (
                partition by ticker, bar_date
                order by
                    try_cast(as_of_date as date) desc nulls last,
                    try_cast(generated_at as timestamptz) desc nulls last,
                    source_priority asc nulls last,
                    source_file desc nulls last
            ) = 1
        )
    """


def _copy_daily_bar_query(
    con: duckdb.DuckDBPyConnection,
    query: str,
    out: Path,
) -> None:
    con.execute(
        f"copy ({query}) to '{_sql_path(out)}' "
        "(format parquet, compression zstd)"
    )


def _validate_daily_bar_store_file(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    *,
    expected_rows: int | None = None,
) -> int:
    schema = con.execute(
        "describe select * from read_parquet(?)", [str(path)]
    ).fetchall()
    if [str(row[0]) for row in schema] != DAILY_BAR_COLUMNS:
        raise ValueError("daily-bars store schema mismatch")
    stats = con.execute(
        """
        select count(*),
               count(*) - count(distinct (ticker, bar_date)),
               count(*) filter (where ticker is null or bar_date is null)
        from read_parquet(?)
        """,
        [str(path)],
    ).fetchone()
    rows = int(stats[0])
    if int(stats[1]) or int(stats[2]):
        raise ValueError("daily-bars store contains invalid or duplicate keys")
    if expected_rows is not None and rows != expected_rows:
        raise ValueError("daily-bars store row count mismatch")
    return rows


def _replace_daily_bars_canonical(source: Path, target: Path) -> None:
    os.replace(source, target)


def _legacy_daily_bars_seed(bars_dir: Path, temp_dir: Path) -> Path | None:
    if not any(bars_dir.glob("????-??-??.parquet")):
        return None
    try:
        from scripts import analytics_store
    except ImportError:
        import analytics_store  # type: ignore

    result = analytics_store.export_daily_bars(
        bars_dir,
        analytics_root=temp_dir / "legacy-seed",
        refresh=False,
    )
    return Path(result["path"])


def _write_daily_bars_store(
    rows: list[dict[str, Any]],
    *,
    reports_dir: str | Path,
    as_of_date: str,
) -> tuple[Path, int, int]:
    bars_dir = Path(reports_dir) / "market_data" / "daily_bars"
    bars_dir.mkdir(parents=True, exist_ok=True)
    delta_out = bars_dir / f"{as_of_date}.parquet"
    canonical_out = bars_dir / "canonical.parquet"
    lock_path = bars_dir / ".daily-bars.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix=".daily-bars-", dir=bars_dir) as temp_root:
            temp_dir = Path(temp_root)
            incoming_path = temp_dir / "incoming.parquet"
            delta_temp = temp_dir / "delta.parquet"
            canonical_temp = temp_dir / "canonical.parquet"
            _daily_bar_frame(rows).to_parquet(incoming_path, index=False)
            previous_path = canonical_out if canonical_out.is_file() else None
            if previous_path is None:
                previous_path = _legacy_daily_bars_seed(bars_dir, temp_dir)
            con = duckdb.connect()
            try:
                con.execute("set memory_limit = '4GiB'")
                con.execute("set preserve_insertion_order = false")
                spill_dir = temp_dir / "spill"
                spill_dir.mkdir()
                con.execute(f"set temp_directory = '{_sql_path(spill_dir)}'")
                incoming_rows = _validate_daily_bar_store_file(con, incoming_path)
                incoming = _incoming_cte(incoming_path)
                if previous_path is None:
                    seed_query = f"""
                        with {incoming}
                        select {_column_list()} from incoming
                        order by ticker, bar_date
                    """
                    _copy_daily_bar_query(con, seed_query, delta_temp)
                    _copy_daily_bar_query(con, seed_query, canonical_temp)
                    expected_canonical_rows = incoming_rows
                else:
                    previous_rows = _validate_daily_bar_store_file(con, previous_path)
                    expected_canonical_rows = int(con.execute(
                        f"""
                        with {incoming}
                        select count(*) from incoming i
                        where not exists (
                            select 1 from read_parquet(?) p
                            where p.ticker = i.ticker and p.bar_date = i.bar_date
                        )
                        """,
                        [str(previous_path)],
                    ).fetchone()[0]) + previous_rows
                    canonical_query = f"""
                        with {incoming},
                        previous as (select * from read_parquet('{_sql_path(previous_path)}'))
                        select {_column_list()} from (
                            select {_column_list('i')} from incoming i
                            union all
                            select {_column_list('p')} from previous p
                            where not exists (
                                select 1 from incoming i
                                where i.ticker = p.ticker and i.bar_date = p.bar_date
                            )
                        ) merged
                        order by ticker, bar_date
                    """
                    changed = " or ".join(
                        f'i."{column}" is distinct from p."{column}"'
                        for column in DAILY_BAR_BUSINESS_COLUMNS
                    )
                    existing_delta = ""
                    existing_union = ""
                    if delta_out.is_file():
                        _validate_daily_bar_store_file(con, delta_out)
                        existing_delta = (
                            ", existing_delta as (select * from read_parquet("
                            f"'{_sql_path(delta_out)}'))"
                        )
                        existing_union = (
                            " union all select " + _column_list("e")
                            + ", 1 as origin from existing_delta e"
                        )
                    delta_query = f"""
                        with {incoming},
                        previous as (select * from read_parquet('{_sql_path(previous_path)}')),
                        changed as (
                            select {_column_list('i')} from incoming i
                            left join previous p
                              on p.ticker = i.ticker and p.bar_date = i.bar_date
                            where p.ticker is null or {changed}
                        )
                        {existing_delta},
                        delta_candidates as (
                            select {_column_list('c')}, 0 as origin from changed c
                            {existing_union}
                        )
                        select {_column_list()} from delta_candidates
                        qualify row_number() over (
                            partition by ticker, bar_date order by origin
                        ) = 1
                        order by ticker, bar_date
                    """
                    _copy_daily_bar_query(con, delta_query, delta_temp)
                    _copy_daily_bar_query(con, canonical_query, canonical_temp)
                delta_rows = _validate_daily_bar_store_file(con, delta_temp)
                canonical_rows = _validate_daily_bar_store_file(
                    con, canonical_temp, expected_rows=expected_canonical_rows
                )
            finally:
                con.close()
            os.replace(delta_temp, delta_out)
            _replace_daily_bars_canonical(canonical_temp, canonical_out)
            return delta_out, delta_rows, canonical_rows


def write_daily_bars_snapshot(
    rows: list[dict[str, Any]],
    *,
    reports_dir: str | Path = REPORTS_DIR,
    as_of_date: str | None = None,
) -> Path:
    as_of = as_of_date or (str(rows[0].get("as_of_date"))[:10] if rows else _today())
    out, _, _ = _write_daily_bars_store(
        rows, reports_dir=reports_dir, as_of_date=as_of
    )
    return out


def refresh_daily_bars(
    tickers: Iterable[str],
    *,
    reports_dir: str | Path = REPORTS_DIR,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    rows = build_daily_bars_rows(tickers, as_of_date=as_of_date)
    path = write_daily_bars_snapshot(rows, reports_dir=reports_dir, as_of_date=as_of_date)
    return {"path": str(path), "rows": len(rows), "tickers": sorted({r["ticker"] for r in rows})}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh daily OHLCV bar artifact")
    parser.add_argument("--tickers", required=True, help="comma-separated ticker list")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args(argv)
    tickers = [x.strip() for x in args.tickers.split(",") if x.strip()]
    print(json.dumps(refresh_daily_bars(
        tickers,
        reports_dir=args.reports_dir,
        as_of_date=args.as_of_date,
    ), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
