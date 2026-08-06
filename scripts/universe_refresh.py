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

try:
    import industry_roles
except ImportError:  # imported as scripts.universe_refresh
    from scripts import industry_roles


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


def _company_for(ticker: str, cik_map: dict[str, Any]) -> str | None:
    item = cik_map.get(ticker)
    if not isinstance(item, dict):
        return None
    return item.get("company") or item.get("title") or item.get("name")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_dated_json(src_dir: Path) -> Path | None:
    if not src_dir.is_dir():
        return None
    files = sorted(
        path for path in src_dir.glob("*.json")
        if len(path.stem) == 10 and path.stem.count("-") == 2
    )
    return files[-1] if files else None


def _append_ticker(out: list[str], value: Any) -> None:
    ticker = _normal_ticker(value)
    if ticker and ticker not in out:
        out.append(ticker)


def _collect_tickers_from_value(value: Any, out: list[str], *, allow_scalar: bool = False) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"ticker", "symbol"}:
                _append_ticker(out, child)
            elif key == "tickers":
                if isinstance(child, dict):
                    for ticker in child:
                        _append_ticker(out, ticker)
                else:
                    _collect_tickers_from_value(child, out, allow_scalar=True)
            else:
                _collect_tickers_from_value(child, out)
    elif isinstance(value, list):
        for item in value:
            _collect_tickers_from_value(item, out, allow_scalar=allow_scalar)
    elif allow_scalar and isinstance(value, str):
        _append_ticker(out, value)


def collect_platform_fallback_tickers(
    *,
    reports_dir: str | Path = REPORTS_DIR,
    content_dir: str | Path | None = None,
    extra_tickers: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[str]:
    """Collect platform tickers for a fallback universe when provider lists are empty."""
    reports = Path(reports_dir)
    content = Path(content_dir) if content_dir is not None else REPO / "content"
    out: list[str] = []
    for ticker in extra_tickers or []:
        _append_ticker(out, ticker)

    ranking_path = _latest_dated_json(reports / "candidate_rankings")
    if ranking_path:
        _collect_tickers_from_value(_load_json(ranking_path), out)
    ranked_fallback = reports.parent / "ranked_candidates.json"
    if ranked_fallback.is_file():
        _collect_tickers_from_value(_load_json(ranked_fallback), out)
    filtered_fallback = reports.parent / "filtered_universe.json"
    if filtered_fallback.is_file():
        _collect_tickers_from_value(_load_json(filtered_fallback), out)

    _collect_tickers_from_value(_load_json(reports / "watchlist.json"), out)
    for ticker in industry_roles.load_approved_tickers(
        content_dir=content,
        reports_dir=reports,
    ):
        _append_ticker(out, ticker)
    _collect_tickers_from_value(_load_json(content / "theme_baskets.json"), out)
    return out


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
    fallback_tickers: list[str] | tuple[str, ...] | set[str] | None = None,
    fallback_secid_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a dated universe artifact dict without writing files."""
    as_of = as_of_date or _today()
    generated = generated_at or _now_iso()
    market_cfg = markets or MARKETS
    cik_lookup = cik_map if cik_map is not None else _cik_map()
    fallback_secids = {str(k).upper(): str(v) for k, v in (fallback_secid_map or {}).items() if v}

    by_ticker: dict[str, dict[str, Any]] = {}
    eastmoney_total = 0
    fallback_total = 0
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

    for ticker in fallback_tickers or []:
        sym = _normal_ticker(ticker)
        if not sym or sym in by_ticker:
            continue
        cik = _cik_for(sym, cik_lookup)
        by_ticker[sym] = {
            "ticker": sym,
            "name": _company_for(sym, cik_lookup),
            "exchange": "US_UNKNOWN",
            "asset_type": "stock",
            "currency": "USD",
            "eastmoney_secid": fallback_secids.get(sym),
            "cik": cik,
            "is_active": True,
            "source_status": "platform_fallback",
            "sources": ["platform_fallback"] + (["sec_company_tickers"] if cik else []),
        }
        fallback_total += 1

    securities = [by_ticker[t] for t in sorted(by_ticker)]
    sec_mapped = sum(1 for row in securities if row.get("cik"))
    sources = ["eastmoney_push2", "sec_company_tickers"]
    if fallback_total:
        sources.append("platform_fallback")
    return {
        "as_of_date": as_of,
        "generated_at": generated,
        "sources": sources,
        "markets": list(market_cfg.values()),
        "securities": securities,
        "coverage": {
            "eastmoney_total": eastmoney_total,
            "fallback_total": fallback_total,
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
    content_dir: str | Path | None = None,
    as_of_date: str | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    fallback_tickers = collect_platform_fallback_tickers(
        reports_dir=reports_dir,
        content_dir=content_dir,
    )
    snapshot = build_universe_snapshot(
        as_of_date=as_of_date,
        page_size=page_size,
        fallback_tickers=fallback_tickers,
    )
    path = write_universe_snapshot(snapshot, reports_dir=reports_dir)
    return {"path": str(path), "rows": len(snapshot.get("securities") or []),
            "coverage": snapshot.get("coverage") or {}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh US universe artifacts")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--content-dir", default=str(REPO / "content"))
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args(argv)
    print(json.dumps(refresh_universe(
        reports_dir=args.reports_dir,
        content_dir=args.content_dir,
        as_of_date=args.as_of_date,
        page_size=args.page_size,
    ), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
