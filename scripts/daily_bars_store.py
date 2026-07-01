#!/usr/bin/env python3
"""Build daily OHLCV bar artifacts for analytics and validation.

Yahoo adjusted bars stay the preferred return-calculation source. Sina daily
bars are a long-history/fallback source and are used to cross-check latest close
before publishing Yahoo as primary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

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


def write_daily_bars_snapshot(
    rows: list[dict[str, Any]],
    *,
    reports_dir: str | Path = REPORTS_DIR,
    as_of_date: str | None = None,
) -> Path:
    as_of = as_of_date or (str(rows[0].get("as_of_date"))[:10] if rows else _today())
    out = Path(reports_dir) / "market_data" / "daily_bars" / f"{as_of}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=DAILY_BAR_COLUMNS)
    tmp = out.with_suffix(out.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(out)
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
