#!/usr/bin/env python3
"""Small adapters for the global-stock-data free US-market endpoints.

This module normalizes provider responses only. It does not decide persistence,
ranking, or UI behavior. Callers should treat these endpoints as best-effort
free data and persist only curated artifacts with source/as-of metadata.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import httpx


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

EASTMONEY_MARKETS = {
    "us_nasdaq": "m:105",
    "us_nyse": "m:106",
    "us_etf": "m:107",
    "hk": "m:116",
}
EASTMONEY_MARKET_NAMES = {
    "105": "NASDAQ",
    "106": "NYSE",
    "107": "US_OTHER",
    "116": "HK",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty(source: str, reason: str, **extra) -> dict[str, Any]:
    return {"source": source, "fetched_at": _now_iso(), "status": "unavailable",
            "reason": reason, **extra}


def _ok(source: str, **extra) -> dict[str, Any]:
    return {"source": source, "fetched_at": _now_iso(), "status": "ok", **extra}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "--", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return None if n is None else int(n)


def _json_get(url: str, params: dict[str, Any] | None = None,
              headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any]:
    r = httpx.get(url, params=params, headers=headers or {"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _text_get(url: str, params: dict[str, Any] | None = None,
              headers: dict[str, str] | None = None, timeout: int = 15,
              encoding: str | None = None) -> str:
    r = httpx.get(url, params=params, headers=headers or {"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    if encoding:
        r.encoding = encoding
    return r.text


def _diff_items(diff: Any) -> list[dict[str, Any]]:
    if isinstance(diff, dict):
        diff = list(diff.values())
    if not isinstance(diff, list):
        return []
    return [x for x in diff if isinstance(x, dict)]


def _with_raw(out: dict[str, Any], raw: Any, include_raw: bool) -> dict[str, Any]:
    if include_raw:
        out["raw"] = raw
    return out


def parse_eastmoney_search_payload(payload: dict[str, Any],
                                   include_raw: bool = False) -> dict[str, Any]:
    rows = (((payload or {}).get("QuotationCodeTable") or {}).get("Data") or [])
    securities: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mkt = str(row.get("MktNum") or "")
        if mkt not in EASTMONEY_MARKET_NAMES:
            continue
        code = str(row.get("Code") or "").strip().upper()
        if not code:
            continue
        securities.append({
            "ticker": code,
            "code": code,
            "name": row.get("Name"),
            "mkt_num": int(mkt),
            "market_name": EASTMONEY_MARKET_NAMES[mkt],
            "secid": f"{mkt}.{code}",
            "security_type": row.get("SecurityTypeName"),
        })
    out = _ok("eastmoney_search", count=len(securities), securities=securities)
    return _with_raw(out, payload, include_raw)


def eastmoney_search(keyword: str, count: int = 10, include_raw: bool = False,
                     get_json: Callable[..., dict[str, Any]] = _json_get) -> dict[str, Any]:
    try:
        payload = get_json(
            "https://searchapi.eastmoney.com/api/suggest/get",
            params={
                "input": keyword,
                "type": 14,
                "token": "D43BF722C8E33BDC906FB84D85E326E8",
                "count": count,
            },
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001 - provider adapter must never raise
        return _empty("eastmoney_search", str(e), keyword=keyword)
    return parse_eastmoney_search_payload(payload, include_raw=include_raw)


def parse_eastmoney_market_list_payload(payload: dict[str, Any],
                                        market: str = "us_nasdaq",
                                        include_raw: bool = False) -> dict[str, Any]:
    data = (payload or {}).get("data") or {}
    diff = _diff_items(data.get("diff"))
    stocks: list[dict[str, Any]] = []
    for item in diff:
        code = str(item.get("f12") or "").strip().upper()
        if not code:
            continue
        market_code = None
        fs = EASTMONEY_MARKETS.get(market, market)
        if fs.startswith("m:"):
            market_code = fs.split(":", 1)[1]
        stocks.append({
            "ticker": code,
            "code": code,
            "name": item.get("f14"),
            "market": EASTMONEY_MARKET_NAMES.get(str(market_code), str(market)),
            "secid": f"{market_code}.{code}" if market_code else None,
            "price": _num(item.get("f2")),
            "change_pct": (_num(item.get("f3")) / 100.0 if _num(item.get("f3")) is not None else None),
            "change_amount": _num(item.get("f4")),
            "volume": _num(item.get("f5")),
            "amount": _num(item.get("f6")),
            "amplitude": (_num(item.get("f7")) / 100.0 if _num(item.get("f7")) is not None else None),
            "high": _num(item.get("f15")),
            "low": _num(item.get("f16")),
            "open": _num(item.get("f17")),
            "prev_close": _num(item.get("f18")),
        })
    out = _ok("eastmoney_push2_clist", market=market, total=int(data.get("total") or 0),
              count=len(stocks), stocks=stocks)
    return _with_raw(out, payload, include_raw)


def eastmoney_market_list(market: str = "us_nasdaq", page: int = 1, page_size: int = 100,
                          sort_field: str = "f3", sort_desc: bool = True,
                          include_raw: bool = False,
                          get_json: Callable[..., dict[str, Any]] = _json_get) -> dict[str, Any]:
    fs = EASTMONEY_MARKETS.get(market, market)
    try:
        payload = get_json(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "fs": fs,
                "fields": "f2,f3,f4,f5,f6,f7,f12,f14,f15,f16,f17,f18",
                "pn": page,
                "pz": page_size,
                "fid": sort_field,
                "po": 1 if sort_desc else 0,
            },
            timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        return _empty("eastmoney_push2_clist", str(e), market=market)
    return parse_eastmoney_market_list_payload(payload, market=market, include_raw=include_raw)


def parse_eastmoney_money_flow_payload(payload: dict[str, Any],
                                       include_raw: bool = False) -> dict[str, Any]:
    data = (payload or {}).get("data") or {}
    rows: list[dict[str, Any]] = []
    for line in data.get("klines") or []:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        row = {
            "date": parts[0],
            "main_net": _num(parts[1]),
            "small_net": _num(parts[2]),
            "mid_net": _num(parts[3]),
            "big_net": _num(parts[4]),
            "super_big_net": _num(parts[5]),
            "main_pct": _num(parts[6]) if len(parts) > 6 else None,
        }
        rows.append(row)
    out = _ok("eastmoney_push2his_fflow", count=len(rows), rows=rows)
    return _with_raw(out, payload, include_raw)


def eastmoney_money_flow(secid: str, limit: int = 120, include_raw: bool = False,
                         get_json: Callable[..., dict[str, Any]] = _json_get) -> dict[str, Any]:
    try:
        payload = get_json(
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
            params={
                "secid": secid,
                "klt": 101,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "lmt": limit,
            },
            timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        return _empty("eastmoney_push2his_fflow", str(e), secid=secid)
    out = parse_eastmoney_money_flow_payload(payload, include_raw=include_raw)
    out["secid"] = secid
    return out


def _quoted_payload(text: str) -> str | None:
    match = re.search(r'"(.*)"', text or "", flags=re.S)
    return match.group(1) if match else None


def parse_sina_us_quote_text(text: str, include_raw: bool = False) -> dict[str, Any]:
    payload = _quoted_payload(text)
    if not payload:
        return _empty("sina_us_quote", "missing quoted payload")
    fields = payload.split(",")
    if len(fields) < 30:
        return _empty("sina_us_quote", "insufficient field count", field_count=len(fields))
    out = _ok(
        "sina_us_quote",
        name=fields[0],
        price=_num(fields[1]),
        change_pct=_num(fields[2]),
        timestamp=fields[3],
        prev_close=_num(fields[26]),
        open=_num(fields[5]),
        high=_num(fields[6]),
        low=_num(fields[7]),
        volume=_num(fields[10]),
        high_52w=_num(fields[8]),
        low_52w=_num(fields[9]),
        market_cap=_num(fields[12]),
        eps=_num(fields[13]),
        pe=_num(fields[14]),
    )
    return _with_raw(out, text, include_raw)


def sina_us_quote(ticker: str, include_raw: bool = False,
                  get_text: Callable[..., str] = _text_get) -> dict[str, Any]:
    try:
        text = get_text(
            f"https://hq.sinajs.cn/list=gb_{ticker.lower()}",
            headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": UA},
            timeout=10,
            encoding="gbk",
        )
    except Exception as e:  # noqa: BLE001
        return _empty("sina_us_quote", str(e), ticker=ticker.upper())
    out = parse_sina_us_quote_text(text, include_raw=include_raw)
    out["ticker"] = ticker.upper()
    return out


def parse_tencent_us_quote_text(text: str, include_raw: bool = False) -> dict[str, Any]:
    payload = _quoted_payload(text)
    if not payload:
        return _empty("tencent_us_quote", "missing quoted payload")
    fields = payload.split("~")
    if len(fields) < 57:
        return _empty("tencent_us_quote", "insufficient field count", field_count=len(fields))
    out = _ok(
        "tencent_us_quote",
        name=fields[1],
        name_en=fields[27],
        price=_num(fields[3]),
        prev_close=_num(fields[4]),
        open=_num(fields[5]),
        volume=_int(fields[6]),
        high=_num(fields[33]),
        low=_num(fields[34]),
        high_52w=_num(fields[35]),
        low_52w=_num(fields[36]),
        change_pct=_num(fields[32]),
        market_cap=_num(fields[44]),
        pe=_num(fields[53]),
        pb=_num(fields[56]),
        timestamp=fields[30],
    )
    return _with_raw(out, text, include_raw)


def tencent_us_quote(ticker: str, include_raw: bool = False,
                     get_text: Callable[..., str] = _text_get) -> dict[str, Any]:
    try:
        text = get_text(f"https://qt.gtimg.cn/q=us{ticker.upper()}", timeout=10, encoding="gbk")
    except Exception as e:  # noqa: BLE001
        return _empty("tencent_us_quote", str(e), ticker=ticker.upper())
    out = parse_tencent_us_quote_text(text, include_raw=include_raw)
    out["ticker"] = ticker.upper()
    return out


def parse_sina_us_daily_bars_text(text: str, include_raw: bool = False) -> dict[str, Any]:
    match = re.search(r"\((\[.*\])\)", text or "", flags=re.S)
    if not match:
        return _empty("sina_us_daily_bars", "missing jsonp payload")
    try:
        items = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        return _empty("sina_us_daily_bars", f"invalid jsonp payload: {e}")
    bars = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        bars.append({
            "date": item.get("d"),
            "open": _num(item.get("o")),
            "high": _num(item.get("h")),
            "low": _num(item.get("l")),
            "close": _num(item.get("c")),
            "volume": _int(item.get("v")),
        })
    out = _ok("sina_us_daily_bars", count=len(bars), bars=bars)
    return _with_raw(out, text, include_raw)


def sina_us_daily_bars(ticker: str, start: str | None = None, end: str | None = None,
                       num: int = 120, include_raw: bool = False,
                       get_text: Callable[..., str] = _text_get) -> dict[str, Any]:
    params = {"symbol": ticker.upper(), "num": num}
    url = "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var/US_MinKService.getDailyK"
    try:
        text = get_text(
            url,
            params=params,
            headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": UA},
            timeout=15,
        )
    except Exception as e:  # noqa: BLE001
        return _empty("sina_us_daily_bars", str(e), ticker=ticker.upper())
    out = parse_sina_us_daily_bars_text(text, include_raw=include_raw)
    bars = out.get("bars") or []
    if start:
        bars = [b for b in bars if str(b.get("date") or "") >= start]
    if end:
        bars = [b for b in bars if str(b.get("date") or "") <= end]
    out["ticker"] = ticker.upper()
    out["bars"] = bars
    out["count"] = len(bars)
    return out


def debug_url(url: str, params: dict[str, Any]) -> str:
    """Return a URL string for logs/tests without performing network I/O."""
    return f"{url}?{urlencode(params)}"
