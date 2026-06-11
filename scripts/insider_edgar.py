#!/usr/bin/env python3
"""Daily insider net-buy from SEC EDGAR Form-4 (open-market P/S only).

The FREE daily-fresh upgrade over yfinance's 6-month insider aggregate. yfinance
gives one smoothed 6-month "net shares" number (and it folds in grants/splits);
this reads the actual Form-4 ownership XMLs and counts ONLY open-market
transactions — code P (purchase, +) and S (sale, −) — summed as signed shares ×
price over a rolling `days` window. That is the real conviction signal: insiders
spending/realising their own cash on the open market, ~2 trading days fresh.

Per ticker: ticker → CIK → recent submissions feed → Form-4 filings in the window
→ fetch each ownership XML → parse nonDerivativeTransaction (P/S) → aggregate $.
Reuses the EDGAR plumbing (CIK map, throttled descriptive-UA fetch) from
scripts/retro_edgar_backfill — same etiquette (SEC_EDGAR_USER_AGENT env, <10/s
throttle). NEVER raises (None on any failure); cached 1 day per (ticker, window).

NOTE: EDGAR is rate-limited (<10/s) and fetched SERIALLY here — a per-ticker call
is a handful of requests, but sweeping a 250-name board cold takes minutes (then
1-day cached). yfinance stays the fast default overlay; this is the deep/daily source.

CLI:  python scripts/insider_edgar.py NVDA MU --days 30
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

# Reuse the EDGAR plumbing (CIK map + throttled descriptive-UA fetch). These are
# import-safe (no side effects at import; CLI is under __main__).
try:
    from retro_edgar_backfill import _cik_for, _get
except ImportError:  # imported as scripts.insider_edgar
    from scripts.retro_edgar_backfill import _cik_for, _get

# Open-market transaction codes that carry conviction: P = purchase, S = sale.
# Everything else (A grant/award, M option exercise, F tax-withholding, G gift, …)
# is NOT a discretionary open-market trade and is excluded.
_OPEN_MARKET = {"P", "S"}


def _cached(namespace: str, params, ttl: float, compute):
    """Best-effort disk cache; falls back to plain compute(). Copied from sector_flow."""
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


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def _recent_form4(cik: str, days: int):
    """[{accession, doc, date}] Form-4 filings in the last `days` (recent block only).

    Only the submissions "recent" block is read (one request) — Form-4s from the
    last few days are always there; we never need the deep archive files. Returns
    None on fetch failure (so the caller fails closed, not with a partial list)."""
    try:
        sub = _get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    except Exception:
        return None
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    out = []
    for i, f in enumerate(forms):
        if f != "4":
            continue
        d = dates[i] if i < len(dates) else None
        if not d or d < cutoff:
            continue
        out.append({"accession": accs[i] if i < len(accs) else None,
                    "doc": docs[i] if i < len(docs) else None, "date": d})
    return out


def _form4_xml_url(cik: str, accession: str, doc: str) -> str | None:
    """Raw ownership-XML URL. `doc` from the feed is often the XSLT-rendered HTML
    path (e.g. 'xslF345X06/wf-form4_123.xml') — strip the rendering prefix to the
    bare XML filename."""
    if not accession or not doc:
        return None
    acc = accession.replace("-", "")
    raw = doc.split("/")[-1]
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{raw}"


def _parse_form4(xml_text: str):
    """(net_usd, n_buy, n_sell) from one Form-4, or None if the XML won't parse.

    Open-market P (+) / S (−) only. Namespace-agnostic ({*}) ElementTree match
    (SEC XML carries namespaces). Sign from the transaction code, NOT acquired/
    disposed (a P is always a buy). Unparseable XML returns None — NOT (0,0,0) —
    so the caller fails the ticker closed instead of recording "no transactions"."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return None
    net = 0.0
    n_buy = n_sell = 0
    for ndt in root.findall(".//{*}nonDerivativeTransaction"):
        def g(tag):  # transactionCode is direct text
            e = ndt.find(f".//{{*}}{tag}")
            return e.text.strip() if (e is not None and e.text) else None

        def g_val(tag):  # amounts are NESTED: <tag><value>N</value></tag>
            e = ndt.find(f".//{{*}}{tag}/{{*}}value")
            if e is None:
                e = ndt.find(f".//{{*}}{tag}")
            return e.text.strip() if (e is not None and e.text) else None
        code = g("transactionCode")
        if code not in _OPEN_MARKET:
            continue
        shares = _num(g_val("transactionShares"))
        price = _num(g_val("transactionPricePerShare"))
        if shares is None or price is None:
            continue
        value = shares * price
        if code == "P":
            net += value
            n_buy += 1
        else:  # "S"
            net -= value
            n_sell += 1
    return net, n_buy, n_sell


def _compute(ticker: str, days: int) -> dict | None:
    cik = _cik_for(ticker)
    if not cik:
        return None
    filings = _recent_form4(cik, days)
    if filings is None:
        return None
    net = 0.0
    n_buy = n_sell = n_txn = 0
    for f in filings:
        # FAIL-CLOSED: a Form-4 we can't locate/fetch/parse is NOT "no transactions"
        # — skipping it could flip the net sign and get cached for a day. Any
        # failure fails the whole ticker (None is never cached → transient SEC
        # errors self-heal on the next call). (Codex TF-1 H2 fix.)
        url = _form4_xml_url(cik, f["accession"], f["doc"])
        if not url:
            return None
        try:
            xml = _get(url).text
        except Exception:
            return None
        parsed = _parse_form4(xml)
        if parsed is None:
            return None
        v, b, s = parsed
        net += v
        n_buy += b
        n_sell += s
        n_txn += b + s
    return {"ticker": ticker.upper(), "cik": cik, "window_days": days,
            "net_usd": round(net, 0), "n_buy": n_buy, "n_sell": n_sell,
            "n_txn": n_txn, "n_filings": len(filings),
            "as_of": date.today().isoformat()}


def insider_net_edgar(ticker: str, days: int = 30) -> dict | None:
    """Daily Form-4 open-market insider net-buy ($) over `days`, or None. Cached 1d.

    Never raises. {ticker, net_usd, n_buy, n_sell, n_txn, n_filings, window_days,
    as_of} — net_usd>0 = insiders net-BOUGHT on the open market in the window."""
    if not ticker:
        return None
    try:
        return _cached("insider_edgar", {"t": ticker.upper(), "d": int(days), "v": 3},
                       86400, lambda: _compute(ticker, int(days)))
    except Exception:
        return None


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser(description="EDGAR Form-4 daily insider net-buy")
    ap.add_argument("tickers", nargs="*", default=["NVDA"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    results = {t: insider_net_edgar(t, args.days) for t in (args.tickers or ["NVDA"])}
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"Form-4 open-market net-buy (last {args.days}d):")
        for t, r in results.items():
            if not r:
                print(f"  {t:6} —  (no CIK / unreachable)")
                continue
            net_m = r["net_usd"] / 1e6
            print(f"  {t:6} net=${net_m:+.1f}M  {r['n_buy']}P/{r['n_sell']}S  "
                  f"({r['n_filings']} Form-4s)")
