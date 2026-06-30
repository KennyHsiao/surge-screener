#!/usr/bin/env python3
"""Deterministic paper-outcome tracker for ranked candidates.

This is a no-LLM validation path. It reads dated deterministic ranking snapshots
from reports/candidate_rankings/, tracks top-N candidates as paper entries, and
updates forward returns as 7/14/30/60D windows mature.
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
HORIZONS = (7, 14, 30, 60)

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


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        if out != out:
            return None
        return out
    except (TypeError, ValueError):
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
    target_ts = pd.Timestamp(target)
    as_of_ts = pd.Timestamp(as_of)
    window = prices[(prices.index >= target_ts) & (prices.index <= as_of_ts)]
    if window.empty:
        return None
    return float(window.iloc[0])


def _window_prices(prices: pd.Series, start: date, end: date, as_of: date) -> pd.Series:
    if prices.empty:
        return pd.Series(dtype="float64")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(min(end, as_of))
    return prices[(prices.index > start_ts) & (prices.index <= end_ts)]


def _compute_outcome_fields(
    *,
    scan_date: str,
    as_of_date: str,
    entry_price: float,
    prices: pd.Series,
) -> dict[str, Any]:
    scan = _date(scan_date)
    as_of = _date(as_of_date)
    if scan is None or as_of is None or entry_price <= 0:
        return {}

    out: dict[str, Any] = {"days_elapsed": max(0, (as_of - scan).days)}
    for days in HORIZONS:
        key = f"fwd_{days}d_return"
        resolved_key = f"resolved_{days}d"
        target = scan + timedelta(days=days)
        price = _price_on_or_after(prices, target, as_of) if as_of >= target else None
        out[resolved_key] = price is not None
        out[key] = round((price / entry_price - 1) * 100, 2) if price is not None else None

    prices_30d = _window_prices(prices, scan, scan + timedelta(days=30), as_of)
    if not prices_30d.empty:
        out["max_drawdown_30d"] = round((float(prices_30d.min()) / entry_price - 1) * 100, 2)
        out["hit_15pct_within_30d"] = bool(float(prices_30d.max()) >= entry_price * 1.15)
    else:
        out["max_drawdown_30d"] = None
        out["hit_15pct_within_30d"] = False

    prices_60d = _window_prices(prices, scan, scan + timedelta(days=60), as_of)
    out["hit_30pct_within_60d"] = (
        bool(float(prices_60d.max()) >= entry_price * 1.30) if not prices_60d.empty else False
    )
    return out


def _needs_price_update(row: dict[str, Any], scan_date: str, as_of_date: str) -> bool:
    scan = _date(scan_date)
    as_of = _date(as_of_date)
    if scan is None or as_of is None:
        return False
    for days in HORIZONS:
        if as_of >= scan + timedelta(days=days) and not bool(row.get(f"resolved_{days}d")):
            return True
    if as_of >= scan + timedelta(days=30) and row.get("max_drawdown_30d") in (None, ""):
        return True
    return False


def _rank_rows(data: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = data.get("ranked_candidates")
    if not isinstance(rows, list):
        rows = data.get("tickers")
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:max(0, int(limit))] if isinstance(row, dict)]


def _existing_rows(path: Path) -> dict[str, dict[str, Any]]:
    data = _load_json(path)
    rows = data.get("outcomes") if data else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            ticker = str(row.get("ticker") or "").upper().strip()
            if ticker:
                out[ticker] = dict(row)
    return out


def _existing_outcomes(path: Path) -> list[dict[str, Any]]:
    data = _load_json(path)
    rows = data.get("outcomes") if data else None
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _build_row(
    *,
    scan_date: str,
    as_of_date: str,
    rank_position: int,
    ranked: dict[str, Any],
    existing: dict[str, Any],
    scoring_model: str | None,
    price_loader: PriceLoader,
) -> dict[str, Any]:
    ticker = str(ranked.get("ticker") or existing.get("ticker") or "").upper().strip()
    row = dict(existing)
    entry_price = _num(row.get("entry_price")) or _num(ranked.get("last_price"))
    row.update({
        "scan_date": scan_date,
        "ticker": ticker,
        "rank_position": rank_position,
        "rank_score": ranked.get("rank_score", row.get("rank_score")),
        "rank_bucket": ranked.get("rank_bucket", row.get("rank_bucket")),
        "scoring_model": scoring_model or row.get("scoring_model"),
        "entry_price": entry_price,
        "entry_price_date": row.get("entry_price_date") or scan_date,
    })
    scan = _date(scan_date)
    as_of = _date(as_of_date)
    row["days_elapsed"] = max(0, (as_of - scan).days) if scan and as_of else row.get("days_elapsed")
    for days in HORIZONS:
        row.setdefault(f"resolved_{days}d", False)
        row.setdefault(f"fwd_{days}d_return", None)
    row.setdefault("max_drawdown_30d", None)
    row.setdefault("hit_15pct_within_30d", False)
    row.setdefault("hit_30pct_within_60d", False)
    if not ticker or entry_price is None:
        return row
    if not _needs_price_update(row, scan_date, as_of_date):
        if "last_verified_at" not in row:
            row["last_verified_at"] = None
        return row

    row["last_verified_at"] = _utc_timestamp()
    prices = _normalise_prices(price_loader(ticker, scan_date, as_of_date))
    row.update(_compute_outcome_fields(
        scan_date=scan_date,
        as_of_date=as_of_date,
        entry_price=float(entry_price),
        prices=prices,
    ))
    return row


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


def update_outcomes(
    *,
    rankings_dir: str | Path = REPORTS_DIR / "candidate_rankings",
    outcomes_dir: str | Path = REPORTS_DIR / "candidate_outcomes",
    as_of_date: str | None = None,
    limit: int = 50,
    price_loader: PriceLoader | None = None,
) -> dict[str, Any]:
    """Create/update paper outcomes for deterministic candidate rankings."""
    rankings = Path(rankings_dir)
    outcomes = Path(outcomes_dir)
    outcomes.mkdir(parents=True, exist_ok=True)
    verify_date = str(as_of_date or _utc_date())[:10]
    loader = price_loader or yfinance_price_loader

    files_written = 0
    rows_written = 0
    for path in _json_files(rankings):
        data = _load_json(path)
        if not data:
            continue
        scan_date = str(data.get("scan_date") or data.get("as_of_date") or path.stem)[:10]
        ranked_rows = _rank_rows(data, limit)
        if not ranked_rows:
            continue

        out_path = outcomes / f"{scan_date}.json"
        existing_by_ticker = _existing_rows(out_path)
        output_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for position, ranked in enumerate(ranked_rows, start=1):
            ticker = str(ranked.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            seen.add(ticker)
            output_rows.append(_build_row(
                scan_date=scan_date,
                as_of_date=verify_date,
                rank_position=position,
                ranked=ranked,
                existing=existing_by_ticker.get(ticker, {}),
                scoring_model=data.get("scoring_model"),
                price_loader=loader,
            ))
        for ticker, old_row in sorted(
            existing_by_ticker.items(),
            key=lambda item: (int(_num(item[1].get("rank_position")) or 999_999), item[0]),
        ):
            if ticker not in seen:
                output_rows.append(old_row)

        if out_path.is_file() and _existing_outcomes(out_path) == output_rows:
            continue

        payload = {
            "scan_date": scan_date,
            "generated_at": _utc_timestamp(),
            "last_verified_at": _utc_timestamp(),
            "source": "candidate_rankings",
            "source_rank_file": f"candidate_rankings/{path.name}",
            "rank_limit": int(limit),
            "scoring_model": data.get("scoring_model"),
            "outcomes": output_rows,
        }
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
                       encoding="utf-8")
        tmp.replace(out_path)
        files_written += 1
        rows_written += len(output_rows)

    return {
        "rankings_dir": str(rankings),
        "outcomes_dir": str(outcomes),
        "as_of_date": verify_date,
        "files_written": files_written,
        "rows": rows_written,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Track no-LLM candidate paper outcomes")
    parser.add_argument("--rankings-dir", default=str(REPORTS_DIR / "candidate_rankings"))
    parser.add_argument("--outcomes-dir", default=str(REPORTS_DIR / "candidate_outcomes"))
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    summary = update_outcomes(
        rankings_dir=args.rankings_dir,
        outcomes_dir=args.outcomes_dir,
        as_of_date=args.as_of_date,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
