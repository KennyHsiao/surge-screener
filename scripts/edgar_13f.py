#!/usr/bin/env python3
"""Free per-FUND 13F holdings via SEC EDGAR (what an investment manager HOLDS).

Complements scripts/institutional_free.py (which is the inverse: who holds a given
STOCK). Here we take an institution → its latest 13F-HR information table → the
list of equity positions it reported. 100% free: EDGAR is public; only a polite
User-Agent is needed (SEC_EDGAR_USER_AGENT, same as scripts/03_deep_dd.py).

Caveats surfaced to the UI: 13F is QUARTERLY with a ~45-day reporting lag (you see
last quarter-end, filed up to 45 days later); it lists CUSIP + issuer name but NO
ticker (ticker mapping is best-effort / omitted); values are $-thousands before
2023, whole-$ after (normalised here). Never raises — returns None on failure.

CLI:  python scripts/edgar_13f.py "Berkshire Hathaway (Buffett)"
      python scripts/edgar_13f.py 1067983
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

_FUNDS_FILE = Path(__file__).resolve().parent.parent / "content" / "funds.json"
# SEC requires a UA that looks like "Name email" — a bare URL gets a 403.
# Env override (SEC_EDGAR_USER_AGENT) is preferred; the default is email-format.
_UA = (os.environ.get("SEC_EDGAR_USER_AGENT")
       or "surge-screener research admin@surge-screener.app")


def _cached(namespace: str, params, ttl: float, compute):
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
        return float(str(x).replace(",", "")) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_funds() -> dict:
    """{display_name: {cik, note}} curated whale list from content/funds.json."""
    try:
        return (json.loads(_FUNDS_FILE.read_text(encoding="utf-8")) or {}).get("funds", {}) or {}
    except Exception:
        return {}


def _get(url: str, as_json: bool = False):
    import httpx
    r = httpx.get(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"},
                  timeout=25, follow_redirects=True)
    r.raise_for_status()
    return r.json() if as_json else r.text


def _latest_13f(cik: int) -> dict | None:
    """Newest 13F-HR (or /A) from the submissions feed: accession + dates."""
    sub = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", as_json=True)
    rec = sub.get("filings", {}).get("recent", {})
    forms, accs = rec.get("form", []), rec.get("accessionNumber", [])
    fdates, rdates = rec.get("filingDate", []), rec.get("reportDate", [])
    for i, f in enumerate(forms):
        if f in ("13F-HR", "13F-HR/A"):  # HR = holdings report (NT = notice, no table)
            return {"name": sub.get("name"), "accession": accs[i], "form": f,
                    "filing_date": fdates[i], "report_date": rdates[i]}
    return None


def _info_table_urls(cik: int, accession: str):
    """Yield candidate information-table .xml URLs in the filing (cover doc last)."""
    nod = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nod}"
    idx = _get(f"{base}/index.json", as_json=True)
    xmls = [it.get("name", "") for it in idx.get("directory", {}).get("item", [])
            if it.get("name", "").lower().endswith(".xml")]
    # the info table is the non-cover .xml; prefer names hinting "infotable"/"table"
    cands = [n for n in xmls if "primary_doc" not in n.lower()] or xmls
    cands.sort(key=lambda n: (not any(k in n.lower().replace("_", "")
                                      for k in ("infotable", "table", "13f")), n))
    for n in cands:
        yield f"{base}/{n}"


def _parse_info_table(xml_text: str) -> list[dict]:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)  # {*} = namespace-agnostic match
    rows = []
    for it in root.findall(".//{*}infoTable"):
        def g(tag):
            e = it.find(f".//{{*}}{tag}")
            return e.text.strip() if (e is not None and e.text) else None
        rows.append({"issuer": g("nameOfIssuer"), "class": g("titleOfClass"),
                     "cusip": g("cusip"), "value": _num(g("value")),
                     "shares": _num(g("sshPrnamt")), "put_call": g("putCall")})
    return rows


def _compute_13f(cik: int, display: str) -> dict | None:
    meta = _latest_13f(cik)
    if not meta:
        return None
    rows = []
    for url in _info_table_urls(cik, meta["accession"]):
        try:
            rows = _parse_info_table(_get(url))
            if rows:
                break
        except Exception:
            continue

    # value units: filings made on/after 2023-01-03 report whole $, earlier $-thousands
    mult = 1 if meta["filing_date"] >= "2023-01-03" else 1000
    agg: dict = {}
    for r in rows:
        key = (r["issuer"], r["cusip"], r["put_call"])
        a = agg.setdefault(key, {"issuer": r["issuer"], "cusip": r["cusip"],
                                 "put_call": r["put_call"], "value": 0.0, "shares": 0.0})
        a["value"] += (r["value"] or 0) * mult
        a["shares"] += (r["shares"] or 0)
    holdings = sorted(agg.values(), key=lambda h: h["value"], reverse=True)
    total = sum(h["value"] for h in holdings) or 1.0
    for h in holdings:
        h["pct"] = round(h["value"] / total * 100, 2)

    lag = None
    try:
        y, m, d = map(int, meta["report_date"].split("-"))
        lag = (date.today() - date(y, m, d)).days
    except Exception:
        pass
    return {"fund": meta["name"] or display, "cik": cik, "form": meta["form"],
            "report_date": meta["report_date"], "filing_date": meta["filing_date"],
            "lag_days": lag, "total_value": total, "holdings_count": len(holdings),
            "holdings": holdings, "source": "sec_edgar_13f"}


def get_13f(name_or_cik) -> dict | None:
    """Latest 13F holdings for a fund name (in content/funds.json) or a raw CIK.
    Cached 1 day (13F changes quarterly). None on failure."""
    funds = load_funds()
    if str(name_or_cik).strip().isdigit():
        cik, display = int(str(name_or_cik).strip()), str(name_or_cik)
    elif name_or_cik in funds:
        cik, display = int(funds[name_or_cik].get("cik")), name_or_cik
    else:
        return None
    return _cached("edgar13f", {"cik": cik}, 86400, lambda: _compute_13f(cik, display))


if __name__ == "__main__":
    import sys
    arg = " ".join(sys.argv[1:]) or "Berkshire Hathaway (Buffett)"
    d = get_13f(arg)
    if not d:
        print("none"); raise SystemExit(1)
    print(f"{d['fund']} (CIK {d['cik']}) · {d['form']} · 截至 {d['report_date']} "
          f"(申報 {d['filing_date']}, 延遲 {d['lag_days']}d) · {d['holdings_count']} 檔 · "
          f"總值 ${d['total_value']/1e9:.1f}B")
    for h in d["holdings"][:15]:
        print(f"  {h['pct']:5.2f}%  ${h['value']/1e9:6.2f}B  {h['issuer']}"
              + (f"  [{h['put_call']}]" if h.get('put_call') else ""))
