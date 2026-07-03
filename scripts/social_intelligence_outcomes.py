#!/usr/bin/env python3
"""Forward-return tracker for social intelligence snapshots.

This intentionally writes to reports/social_intelligence_outcomes/ so social
discovery validation never pollutes deterministic candidate outcomes.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
DATED_JSON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
HORIZONS = (7, 14, 30)

PriceLoader = Callable[[str, str, str], pd.Series | pd.DataFrame | None]


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _json_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.json") if DATED_JSON_RE.match(p.name))


def _normalise_prices(data: pd.Series | pd.DataFrame | None) -> pd.Series:
    if data is None:
        return pd.Series(dtype="float64")
    if isinstance(data, pd.DataFrame):
        if "Close" in data.columns:
            series = data["Close"]
        elif "Adj Close" in data.columns:
            series = data["Adj Close"]
        else:
            series = data.iloc[:, 0] if not data.empty else pd.Series(dtype="float64")
    else:
        series = data
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return pd.Series(dtype="float64")
    series.index = pd.to_datetime(series.index, errors="coerce").normalize()
    series = series[~series.index.isna()]
    return series.sort_index()


def _price_on_or_after(prices: pd.Series, target: date, as_of: date) -> float | None:
    if prices.empty:
        return None
    window = prices[
        (prices.index >= pd.Timestamp(target))
        & (prices.index <= pd.Timestamp(as_of))
    ]
    return float(window.iloc[0]) if not window.empty else None


def _return_at(prices: pd.Series, *, entry: float, scan: date, as_of: date, days: int) -> tuple[bool, float | None]:
    target = scan + timedelta(days=days)
    if as_of < target or entry <= 0:
        return False, None
    px = _price_on_or_after(prices, target, as_of)
    return (px is not None), (round((px / entry - 1) * 100, 2) if px is not None else None)


def yfinance_price_loader(ticker: str, start_date: str, end_date: str) -> pd.Series | None:
    import yfinance as yf

    end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        df = yf.download(ticker, start=start_date, end=end, progress=False, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df["Close"]


def _entry_price(prices: pd.Series, scan: date, as_of: date) -> float | None:
    return _price_on_or_after(prices, scan, as_of)


def _build_row(
    *,
    scan_date: str,
    as_of_date: str,
    social: dict[str, Any],
    spy_prices: pd.Series,
    price_loader: PriceLoader,
) -> dict[str, Any] | None:
    ticker = str(social.get("ticker") or "").upper().strip()
    scan = _date(scan_date)
    as_of = _date(as_of_date)
    if not ticker or scan is None or as_of is None:
        return None
    prices = _normalise_prices(price_loader(ticker, scan_date, as_of_date))
    entry = _entry_price(prices, scan, as_of)
    spy_entry = _entry_price(spy_prices, scan, as_of)
    if entry is None:
        return {
            "scan_date": scan_date,
            "ticker": ticker,
            "entry_price": None,
            "mentioned_by": social.get("mentioned_by") or [],
            "discovery_sources": social.get("discovery_sources") or [],
            "labels": social.get("labels") or {},
        }

    out: dict[str, Any] = {
        "scan_date": scan_date,
        "ticker": ticker,
        "entry_price": round(float(entry), 4),
        "mentioned_by": social.get("mentioned_by") or [],
        "discovery_sources": social.get("discovery_sources") or [],
        "platform_validation": social.get("platform_validation") or {},
        "labels": social.get("labels") or {},
        "last_verified_at": _utc_timestamp(),
    }
    for days in HORIZONS:
        resolved, ret = _return_at(prices, entry=float(entry), scan=scan, as_of=as_of, days=days)
        out[f"resolved_{days}d"] = resolved
        out[f"fwd_{days}d_return"] = ret
        spy_resolved, spy_ret = (
            _return_at(spy_prices, entry=float(spy_entry), scan=scan, as_of=as_of, days=days)
            if spy_entry is not None else (False, None)
        )
        out[f"spy_resolved_{days}d"] = spy_resolved
        out[f"spy_fwd_{days}d_return"] = spy_ret
        out[f"excess_vs_spy_{days}d"] = (
            round(ret - spy_ret, 2) if ret is not None and spy_ret is not None else None
        )
    return out


def _source_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    handles: dict[str, dict[str, int]] = {}
    sources: dict[str, dict[str, int]] = {}
    for row in rows:
        hit7 = bool((row.get("fwd_7d_return") or 0) > 0)
        for handle in row.get("mentioned_by") or []:
            rec = handles.setdefault(str(handle), {"count": 0, "hit_7d": 0})
            rec["count"] += 1
            rec["hit_7d"] += 1 if hit7 else 0
        for source in row.get("discovery_sources") or []:
            rec = sources.setdefault(str(source), {"count": 0, "hit_7d": 0})
            rec["count"] += 1
            rec["hit_7d"] += 1 if hit7 else 0
    return {"handles": handles, "sources": sources}


def update_social_outcomes(
    *,
    snapshot_dir: str | Path = REPORTS_DIR / "social_intelligence",
    outcomes_dir: str | Path = REPORTS_DIR / "social_intelligence_outcomes",
    as_of_date: str | None = None,
    price_loader: PriceLoader | None = None,
) -> dict[str, Any]:
    snapshots = Path(snapshot_dir)
    outcomes = Path(outcomes_dir)
    outcomes.mkdir(parents=True, exist_ok=True)
    verify_date = str(as_of_date or _utc_date())[:10]
    loader = price_loader or yfinance_price_loader

    files_written = 0
    rows_written = 0
    for path in _json_files(snapshots):
        data = _load_json(path)
        if not data:
            continue
        scan_date = str(data.get("as_of_date") or path.stem)[:10]
        tickers = [row for row in data.get("tickers", []) if isinstance(row, dict)]
        if not tickers:
            continue
        spy_prices = _normalise_prices(loader("SPY", scan_date, verify_date))
        output_rows = [
            row for row in (
                _build_row(
                    scan_date=scan_date,
                    as_of_date=verify_date,
                    social=social,
                    spy_prices=spy_prices,
                    price_loader=loader,
                )
                for social in tickers
            )
            if row is not None
        ]
        payload = {
            "scan_date": scan_date,
            "generated_at": _utc_timestamp(),
            "last_verified_at": _utc_timestamp(),
            "source": "social_intelligence",
            "source_snapshot_file": f"social_intelligence/{path.name}",
            "as_of_date": verify_date,
            "outcomes": output_rows,
            "source_stats": _source_stats(output_rows),
        }
        out_path = outcomes / f"{scan_date}.json"
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
                       encoding="utf-8")
        tmp.replace(out_path)
        files_written += 1
        rows_written += len(output_rows)

    return {
        "snapshot_dir": str(snapshots),
        "outcomes_dir": str(outcomes),
        "as_of_date": verify_date,
        "files_written": files_written,
        "rows": rows_written,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Track social intelligence paper outcomes")
    parser.add_argument("--snapshot-dir", default=str(REPORTS_DIR / "social_intelligence"))
    parser.add_argument("--outcomes-dir", default=str(REPORTS_DIR / "social_intelligence_outcomes"))
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    print(json.dumps(update_social_outcomes(
        snapshot_dir=args.snapshot_dir,
        outcomes_dir=args.outcomes_dir,
        as_of_date=args.as_of_date,
    ), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
