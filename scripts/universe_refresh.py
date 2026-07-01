#!/usr/bin/env python3
"""Build daily US security-universe artifacts.

The artifact is the write source for analytics-store exports. It combines
Eastmoney market/security identifiers with SEC ticker→CIK mappings, but keeps
all network calls injectable so tests can stay offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
sys.path.insert(0, str(REPO / "scripts"))

try:
    import global_stock_data as gsd
except ImportError:  # imported as scripts.universe_refresh
    from scripts import global_stock_data as gsd

try:
    from retro_edgar_backfill import _cik_map
except ImportError:  # imported as scripts.universe_refresh
    from scripts.retro_edgar_backfill import _cik_map


MARKETS = {
    "us_nasdaq": "NASDAQ",
    "us_nyse": "NYSE",
    "us_etf": "US_OTHER",
}
MARKET_ASSET_TYPE = {
    "us_nasdaq": "stock",
    "us_nyse": "stock",
    "us_etf": "other",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _normal_ticker(value: Any) -> str:
    return str(value or "").upper().strip().removeprefix("$")


def _asset_type(row: dict[str, Any], market: str) -> str:
    text = str(row.get("security_type") or row.get("asset_type") or "").lower()
    if "etf" in text or "基金" in text:
        return "etf"
    return MARKET_ASSET_TYPE.get(market, "stock")


def _cik_for(ticker: str, cik_map: dict[str, Any]) -> str | None:
    item = cik_map.get(ticker)
    if isinstance(item, dict):
        raw = item.get("cik") or item.get("cik_str")
    else:
        raw = item
    if raw is None or raw == "":
        return None
    try:
        return f"{int(raw):010d}"
    except (TypeError, ValueError):
        text = str(raw).strip()
        return text.zfill(10) if text.isdigit() else text


def _market_rows(
    market: str,
    *,
    market_list_fetcher: Callable[..., dict[str, Any]],
    page_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        data = market_list_fetcher(market=market, page=page, page_size=page_size)
        if data.get("status") != "ok":
            break
        stocks = data.get("stocks") or []
        if not isinstance(stocks, list) or not stocks:
            break
        rows.extend([r for r in stocks if isinstance(r, dict)])
        total = int(data.get("total") or len(rows))
        if len(rows) >= total or len(stocks) < page_size:
            break
        page += 1
    return rows


def build_universe_snapshot(
    *,
    as_of_date: str | None = None,
    generated_at: str | None = None,
    market_list_fetcher: Callable[..., dict[str, Any]] = gsd.eastmoney_market_list,
    cik_map: dict[str, Any] | None = None,
    markets: dict[str, str] | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    """Return a dated universe artifact dict without writing files."""
    as_of = as_of_date or _today()
    generated = generated_at or _now_iso()
    market_cfg = markets or MARKETS
    cik_lookup = cik_map if cik_map is not None else _cik_map()

    by_ticker: dict[str, dict[str, Any]] = {}
    eastmoney_total = 0
    for market_key, exchange in market_cfg.items():
        for row in _market_rows(
            market_key,
            market_list_fetcher=market_list_fetcher,
            page_size=page_size,
        ):
            ticker = _normal_ticker(row.get("ticker") or row.get("code"))
            if not ticker:
                continue
            eastmoney_total += 1
            existing = by_ticker.get(ticker, {})
            cik = _cik_for(ticker, cik_lookup)
            merged = {
                "ticker": ticker,
                "name": row.get("name") or existing.get("name"),
                "exchange": row.get("market") or exchange,
                "asset_type": _asset_type(row, market_key),
                "currency": "USD" if market_key.startswith("us_") else None,
                "eastmoney_secid": row.get("secid") or existing.get("eastmoney_secid"),
                "cik": cik,
                "is_active": True,
                "sources": ["eastmoney_push2"] + (["sec_company_tickers"] if cik else []),
            }
            by_ticker[ticker] = {**existing, **merged}

    securities = [by_ticker[t] for t in sorted(by_ticker)]
    sec_mapped = sum(1 for row in securities if row.get("cik"))
    return {
        "as_of_date": as_of,
        "generated_at": generated,
        "sources": ["eastmoney_push2", "sec_company_tickers"],
        "markets": list(market_cfg.values()),
        "securities": securities,
        "coverage": {
            "eastmoney_total": eastmoney_total,
            "security_count": len(securities),
            "sec_mapped": sec_mapped,
            "missing_cik": len(securities) - sec_mapped,
        },
    }


def write_universe_snapshot(snapshot: dict[str, Any],
                            reports_dir: str | Path = REPORTS_DIR) -> Path:
    as_of = str(snapshot.get("as_of_date") or _today())[:10]
    out = Path(reports_dir) / "universe" / f"{as_of}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    tmp.replace(out)
    return out


def refresh_universe(
    *,
    reports_dir: str | Path = REPORTS_DIR,
    as_of_date: str | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    snapshot = build_universe_snapshot(as_of_date=as_of_date, page_size=page_size)
    path = write_universe_snapshot(snapshot, reports_dir=reports_dir)
    return {"path": str(path), "rows": len(snapshot.get("securities") or []),
            "coverage": snapshot.get("coverage") or {}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh US universe artifacts")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args(argv)
    print(json.dumps(refresh_universe(
        reports_dir=args.reports_dir,
        as_of_date=args.as_of_date,
        page_size=args.page_size,
    ), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
