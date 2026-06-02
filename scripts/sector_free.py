#!/usr/bin/env python3
"""Free GICS sector / industry via yfinance + a TradingView-watchlist parser.

The screener pipeline carries no sector field; this fills it on demand so the
"自選股分類" page can group an arbitrary watchlist by 板塊. Pure data fetch
(verified-data-to-AI): yfinance Ticker.info already exposes sector/industry.

`gather_sector(ticker)` NEVER raises — returns None on any failure (matches
scripts/fundamentals_free.py). Cached 7 days (GICS sector is near-static).

CLI:  python scripts/sector_free.py NVDA SOXL MU
"""

from __future__ import annotations

import re
from pathlib import Path


def _cached(namespace: str, params, ttl: float, compute):
    """Best-effort disk cache; falls back to plain compute() if unavailable."""
    try:
        try:
            from cache import get_or_compute
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cache", Path(__file__).parent / "cache.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            get_or_compute = mod.get_or_compute
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def parse_tv_watchlist(text: str) -> list[dict]:
    """Parse a TradingView export / pasted list into ordered, de-duped items.

    TradingView exports are plain text: one ``EXCHANGE:SYMBOL`` per line (or
    comma-joined), with optional ``###Section,`` headers. Returns
    ``[{"ticker": "NVDA", "tv_symbol": "NASDAQ:NVDA"}, ...]`` — ``ticker`` is the
    bare symbol (exchange stripped) for merging/sector/theme; ``tv_symbol`` keeps
    the original exchange-qualified form for an exact round-trip on export.
    """
    out: dict[str, str] = {}
    for tok in re.split(r"[\n,]+", text or ""):
        tok = tok.strip()
        if not tok or tok.startswith("###"):  # skip blanks + TV section headers
            continue
        raw = tok.upper().lstrip("$")
        ticker = "".join(c for c in raw.split(":")[-1] if c.isalnum() or c == ".")
        if not ticker:
            continue
        out.setdefault(ticker, raw)  # first occurrence's tv_symbol wins
    return [{"ticker": t, "tv_symbol": tv} for t, tv in out.items()]


# yfinance exchange codes that mean "NASDAQ-listed" (Global Select / Global /
# Capital Market). fullExchangeName ("NasdaqGS" …) is a backup check.
_NASDAQ_CODES = {"NMS", "NGM", "NCM", "NSD", "NAS", "NASDAQ"}


def _compute_sector(ticker: str) -> dict | None:
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None
    exch = (info.get("exchange") or "").upper()
    full = (info.get("fullExchangeName") or "").upper()
    sector, industry = info.get("sector"), info.get("industry")
    cap = info.get("marketCap")
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    avg_vol = (info.get("averageDailyVolume3Month") or info.get("averageVolume")
               or info.get("averageDailyVolume10Day"))
    # Unresolvable ticker (typo / delisted) → None so callers can drop it.
    if not (sector or industry or exch or full or cap):
        return None
    return {
        "ticker": ticker.upper(),
        "sector": sector,
        "industry": industry,
        "sector_key": info.get("sectorKey"),
        "industry_key": info.get("industryKey"),
        "exchange": exch or None,
        "full_exchange": info.get("fullExchangeName"),
        "is_nasdaq": exch in _NASDAQ_CODES or "NASDAQ" in full,
        # importance / liquidity (exchange-agnostic) — same .info call, free.
        "market_cap": cap,
        "price": price,
        "avg_volume": avg_vol,
        "avg_dollar_volume": (price * avg_vol) if (price and avg_vol) else None,
        "source": "yfinance_free",
    }


def gather_sector(ticker: str) -> dict | None:
    """{ticker, sector, industry, sector_key, industry_key} or None. Cached 7d."""
    return _cached("sector", {"ticker": ticker.upper()}, 604800,
                   lambda: _compute_sector(ticker))


def gather_sectors(tickers) -> dict[str, dict]:
    """Batch: {TICKER: sector_dict} for tickers that resolve (cache makes repeats
    instant). Missing/unclassified tickers are simply absent from the result."""
    out = {}
    for t in tickers:
        d = gather_sector(t)
        if d:
            out[d["ticker"]] = d
    return out


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(gather_sector(t), indent=2, ensure_ascii=False))
