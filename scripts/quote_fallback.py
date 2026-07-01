#!/usr/bin/env python3
"""Short-TTL US quote fallback routing.

This module is for UI reliability only. Quotes are cached briefly and are not a
first-class analytics table; any formal signal must store the price/source in
that signal's own snapshot.
"""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

try:
    import cache
    import global_stock_data as gsd
except ImportError:  # package import from app root
    from scripts import cache
    from scripts import global_stock_data as gsd


REPO = Path(__file__).resolve().parent.parent
MARKET_TTL = 60
OFF_HOURS_TTL = 900
NY = ZoneInfo("America/New_York")
UA = gsd.UA


def _ticker(value: Any) -> str:
    return str(value or "").upper().strip().removeprefix("$")


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def quote_ttl(now: datetime | None = None) -> int:
    """Return quote cache TTL: 60s during regular US hours, 15m otherwise."""
    current = now or datetime.now(NY)
    if current.tzinfo is None:
        current = current.replace(tzinfo=NY)
    ny_now = current.astimezone(NY)
    is_weekday = ny_now.weekday() < 5
    in_hours = time(9, 30) <= ny_now.time() <= time(16, 0)
    return MARKET_TTL if is_weekday and in_hours else OFF_HOURS_TTL


def _empty(ticker: str, reason: str) -> dict[str, Any]:
    return {
        "ticker": _ticker(ticker),
        "price": None,
        "currency": "USD",
        "source": "unavailable",
        "fetched_at": None,
        "stale": False,
        "status": "unavailable",
        "reason": reason,
        "fields": {},
    }


def _quote_from_payload(ticker: str, payload: dict[str, Any], source: str | None = None) -> dict[str, Any] | None:
    price = _num(payload.get("price") or payload.get("last_price") or payload.get("regularMarketPrice"))
    if price is None or price <= 0:
        return None
    return {
        "ticker": _ticker(payload.get("ticker") or ticker),
        "price": price,
        "currency": payload.get("currency") or "USD",
        "source": source or payload.get("source") or "unknown",
        "fetched_at": payload.get("fetched_at") or payload.get("timestamp"),
        "stale": False,
        "status": "ok",
        "fields": {
            "market_cap": _num(payload.get("market_cap")),
            "pe": _num(payload.get("pe")),
            "pb": _num(payload.get("pb")),
            "eps": _num(payload.get("eps")),
            "week_52_high": _num(payload.get("week_52_high") or payload.get("high_52w")),
            "week_52_low": _num(payload.get("week_52_low") or payload.get("low_52w")),
        },
    }


def _quote_from_yfinance_object(ticker: str, yf_ticker: Any) -> dict[str, Any] | None:
    if yf_ticker is None:
        return None
    payload: dict[str, Any] = {"ticker": ticker, "source": "yfinance"}
    try:
        fast = getattr(yf_ticker, "fast_info", None)
        if fast:
            getter = fast.get if hasattr(fast, "get") else lambda key, default=None: getattr(fast, key, default)
            payload.update({
                "price": getter("last_price") or getter("lastPrice") or getter("regular_market_price"),
                "market_cap": getter("market_cap") or getter("marketCap"),
                "week_52_high": getter("year_high") or getter("yearHigh"),
                "week_52_low": getter("year_low") or getter("yearLow"),
            })
    except Exception:
        pass
    try:
        info = getattr(yf_ticker, "info", None)
        if isinstance(info, dict):
            payload.setdefault("market_cap", info.get("marketCap"))
            payload["pe"] = info.get("trailingPE")
            payload["pb"] = info.get("priceToBook")
            payload["eps"] = info.get("trailingEps")
    except Exception:
        pass
    return _quote_from_payload(ticker, payload, "yfinance")


def _json_get(url: str, params: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    r = httpx.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def eastmoney_push2_quote(
    ticker: str,
    *,
    search_provider: Callable[[str], dict[str, Any]] = gsd.eastmoney_search,
    get_json: Callable[..., dict[str, Any]] = _json_get,
) -> dict[str, Any]:
    """Best-effort Eastmoney push2 single-quote fallback."""
    sym = _ticker(ticker)
    try:
        search = search_provider(sym)
        securities = search.get("securities") if isinstance(search, dict) else []
        secid = None
        for item in securities or []:
            if isinstance(item, dict) and str(item.get("ticker") or "").upper() == sym:
                secid = item.get("secid")
                break
        if not secid:
            return {"status": "unavailable", "source": "eastmoney_push2_quote", "ticker": sym}
        payload = get_json(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "secid": secid,
                "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f116,f162,f167,f168",
            },
            timeout=10,
        )
        data = (payload or {}).get("data") or {}
        price = _num(data.get("f43"))
        high = _num(data.get("f44"))
        low = _num(data.get("f45"))
        if price is not None and price > 10000:
            price = price / 100.0
        return {
            "status": "ok" if price and price > 0 else "unavailable",
            "source": "eastmoney_push2_quote",
            "ticker": sym,
            "price": price,
            "high": high,
            "low": low,
            "market_cap": _num(data.get("f116")),
            "pe": _num(data.get("f162")),
            "pb": _num(data.get("f167")),
            "eps": _num(data.get("f168")),
            "timestamp": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "unavailable", "source": "eastmoney_push2_quote", "ticker": sym, "reason": str(e)}


def _default_providers() -> dict[str, Callable[[str], dict[str, Any]]]:
    return {
        "sina": gsd.sina_us_quote,
        "tencent": gsd.tencent_us_quote,
        "eastmoney": eastmoney_push2_quote,
    }


def fetch_quote(
    ticker: str,
    *,
    yf_ticker: Any = None,
    providers: dict[str, Callable[[str], dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Fetch a quote by provider order without touching the cache."""
    sym = _ticker(ticker)
    yf_quote = _quote_from_yfinance_object(sym, yf_ticker)
    if yf_quote:
        return yf_quote

    routes = _default_providers()
    if providers:
        routes.update(providers)
    for name in ("sina", "tencent", "eastmoney"):
        provider = routes.get(name)
        if provider is None:
            continue
        try:
            payload = provider(sym)
        except Exception:
            continue
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            continue
        quote = _quote_from_payload(sym, payload)
        if quote:
            return quote
    return _empty(sym, "all quote providers unavailable")


def get_quote(
    ticker: str,
    *,
    yf_ticker: Any = None,
    providers: dict[str, Callable[[str], dict[str, Any]]] | None = None,
    now: datetime | None = None,
    use_cache: bool = True,
    cache_get_or_compute: Callable[..., Any] = cache.get_or_compute,
) -> dict[str, Any]:
    """Short-cache quote fallback for UI surfaces."""
    sym = _ticker(ticker)

    def _compute() -> dict[str, Any]:
        return fetch_quote(sym, yf_ticker=yf_ticker, providers=providers)

    if not use_cache:
        return _compute()
    return cache_get_or_compute(
        "quote_fallback",
        {"ticker": sym, "include_yfinance": yf_ticker is not None},
        quote_ttl(now),
        _compute,
        should_cache=lambda value: isinstance(value, dict) and value.get("status") == "ok",
    )


def quote_source_text(quote: dict[str, Any] | None, ttl: int | None = None) -> str:
    if not isinstance(quote, dict) or quote.get("status") != "ok":
        return "來源：quote unavailable"
    source = str(quote.get("source") or "unknown")
    label = {
        "yfinance": "yfinance",
        "sina_us_quote": "Sina fallback",
        "tencent_us_quote": "Tencent fallback",
        "eastmoney_push2_quote": "Eastmoney fallback",
    }.get(source, source)
    ttl_seconds = MARKET_TTL if ttl is None else int(ttl)
    cache_label = "1 分鐘快取" if ttl_seconds <= 60 else "15 分鐘快取"
    return f"來源：{label} · {cache_label}"


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Fetch a short-cache quote fallback")
    parser.add_argument("ticker")
    args = parser.parse_args()
    print(json.dumps(get_quote(args.ticker), ensure_ascii=False, indent=2, sort_keys=True))
