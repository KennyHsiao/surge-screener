#!/usr/bin/env python3
"""Surge Retrospective — Phase 1.5: backfill Dim2/Dim4 from SEC EDGAR.

Dim2 (catalyst) and Dim4 (institutional) can't be reconstructed from price history
— BUT the SEC filings that drive them ARE free and fully historical via EDGAR.
This adds two ground-truth flags to each surge event (and, symmetrically, to the
control group inside retro_factor_lift), measured as of the same observation day:

  - recent_8k_14d  (Dim2 2a): a material 8-K was filed within 14 days before the
    observation day — the kind of catalyst the screener rewards.
  - insider_buying_90d (Dim4 4b): ≥2 Form-4 open-market PURCHASES (transaction
    code "P") in the 90 days before — insiders buying their own stock.

13F (institutional accumulation) is per-FUND, not per-company, so it can't be
queried by ticker without aggregating every fund's holdings — out of scope here.

EDGAR etiquette: a descriptive User-Agent is required (SEC_EDGAR_USER_AGENT env,
matching scripts/03_deep_dd.py) and requests are throttled < 10/s. Everything is
cached (cache.py) so re-runs and the control-group pass are cheap.

CLI:
    SEC_EDGAR_USER_AGENT="you you@example.com" python scripts/retro_edgar_backfill.py
    ... --limit 12                       # backfill only the first N events (dev)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

from cache import get_or_compute  # noqa: E402

_UA = os.environ.get("SEC_EDGAR_USER_AGENT") or "surge-screener-retro research@example.com"
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}
_THROTTLE = 0.12  # seconds between SEC requests (< 10/s)

EDGAR_FACTOR_DEFS = {
    "recent_8k_14d":     ("Dim2", "2a 8-K", "近 14 日內有 8-K 重大事件公告"),
    "insider_buying_90d": ("Dim4", "4b Insider", "近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)"),
}


def _get(url: str):
    import httpx
    time.sleep(_THROTTLE)
    r = httpx.get(url, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    return r


def _cik_map() -> dict:
    """ticker (upper) → zero-padded 10-digit CIK, from SEC's master list."""
    def _fetch():
        data = _get("https://www.sec.gov/files/company_tickers.json").json()
        return {row["ticker"].upper(): f"{int(row['cik_str']):010d}"
                for row in data.values()}
    return get_or_compute("edgar_cikmap", {"v": 1}, ttl=7 * 86400, compute=_fetch)


def _cik_for(ticker: str) -> str | None:
    try:
        m = _cik_map()
    except Exception:
        return None  # CIK map unreachable → unknown ticker → edgar_flags returns None
    for cand in (ticker.upper(), ticker.upper().replace("-", ""),
                 ticker.upper().replace("-", ".")):
        if cand in m:
            return m[cand]
    return None


def _company_filings(cik: str):
    """All filings (form, date, accession, primaryDocument), recent + archives.

    Returns None on ANY fetch failure (main submissions OR a needed archive file).
    A partial list must never be returned/cached: for an event 2+ years old the
    relevant 90-day window lives in an archive file (not "recent"), so a silently
    dropped archive would undercount Form-4s/8-Ks and persist wrong-False flags.
    None is not cached (should_cache below) → retried next run; edgar_flags maps it
    to {None, None} (unknown), never a confirmed False.
    """
    def _fetch():
        rows: list[dict] = []

        def _absorb(recent: dict):
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            for i in range(len(forms)):
                rows.append({
                    "form": forms[i],
                    "date": dates[i] if i < len(dates) else None,
                    "accession": accs[i] if i < len(accs) else None,
                    "doc": docs[i] if i < len(docs) else None,
                })

        try:
            sub = _get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
        except Exception:
            return None
        filings = sub.get("filings", {})
        _absorb(filings.get("recent", {}))
        # Older filings live in separate archive files (>~1yr / >1000 filings back).
        # If a NEEDED archive fails, the list is incomplete — fail the whole fetch
        # rather than return/persist a partial set.
        for f in filings.get("files", []):
            name = f.get("name")
            if not name:
                continue
            try:
                _absorb(_get(f"https://data.sec.gov/submissions/{name}").json())
            except Exception:
                return None
        return rows
    return get_or_compute("edgar_filings", {"cik": cik, "cv": 2}, ttl=2 * 86400,
                          compute=_fetch, should_cache=lambda v: v is not None)


def _is_purchase(cik: str, accession: str, doc: str) -> bool | None:
    """True/False if a Form-4 is / isn't an open-market PURCHASE (code P); None if
    the doc couldn't be fetched (so the caller can treat it as UNKNOWN, not False).

    The submissions `primaryDocument` for a Form 4 is the XSLT-rendered HTML
    (``xslF345X06/<name>.xml``) which has NO raw tags — the machine-readable XML
    is the same file WITHOUT that prefix at the accession root. We fetch the raw
    XML and look for code P. The result is cached (negatives too) so each Form 4
    is fetched at most once, ever."""
    if not accession or not doc:
        return False
    acc_nodash = accession.replace("-", "")
    raw_doc = doc.split("/")[-1]  # strip xslF345X06/ rendering prefix → raw XML

    def _fetch():
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
               f"{acc_nodash}/{raw_doc}")
        try:
            text = _get(url).text
        except Exception:
            return None  # fetch FAILED — unknown, not "not a purchase" (see below)
        return "<transactionCode>P</transactionCode>" in text
    # Cache only a real determination (True/False), NEVER a fetch failure (None):
    # persisting None-as-False would record a real insider buy as "no purchase" for
    # 30 days. None isn't cached → it's retried next run; the caller treats None as
    # UNKNOWN (it can flip insider_buying_90d to None, not a confirmed False).
    #
    # cv=2 versions the cache KEY. The pre-fix code cached failures as False under
    # the unversioned key; bumping the version makes this fixed code ignore every
    # one of those poisoned entries (they live under the old key and are never read
    # again) WITHOUT needing a manual cache wipe — reproducible on CI / any machine.
    return get_or_compute("edgar_form4", {"cik": cik, "acc": accession, "cv": 2},
                          ttl=30 * 86400, compute=_fetch,
                          should_cache=lambda v: v is not None)


def _safe_date(d: str):
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def edgar_flags(ticker: str, as_of: str) -> dict:
    """{recent_8k_14d, insider_buying_90d} as of `as_of` (YYYY-MM-DD).

    8-K detection is free (filing dates only). Insider detection needs to read each
    Form-4 doc — so we fetch ONLY the Form 4s whose filingDate falls in the 90-day
    window before `as_of`, not every Form 4 the company ever filed. With per-
    accession caching (negatives included) overlapping windows reuse fetched docs,
    so this scales to a full S&P-1500 run where each ticker has few query dates.

    Values are bool, or None — when the CIK is unknown, EDGAR is unreachable, or
    (for insider_buying_90d) a Form-4 doc fetch failed and left the ≥2-buy question
    unresolved. The lift stage skips None flags as insufficient data, so a transient
    failure never becomes a confirmed-False persisted into surge_features.json.
    """
    cik = _cik_for(ticker)
    if not cik:
        return {"recent_8k_14d": None, "insider_buying_90d": None}
    try:
        filings = _company_filings(cik)
    except Exception:
        filings = []
    if not filings:
        return {"recent_8k_14d": None, "insider_buying_90d": None}

    asof = datetime.strptime(as_of, "%Y-%m-%d").date()
    lo_8k, lo_f4 = asof - timedelta(days=14), asof - timedelta(days=90)
    has_8k = False
    purchases = 0   # confirmed open-market buys
    unknown = 0     # in-window Form 4s whose doc couldn't be fetched
    for f in filings:
        fd = _safe_date(f.get("date"))
        if not fd:
            continue
        if f.get("form") == "8-K" and lo_8k <= fd <= asof:
            has_8k = True
        elif f.get("form") == "4" and lo_f4 <= fd <= asof:
            res = _is_purchase(cik, f.get("accession"), f.get("doc"))
            if res is None:
                unknown += 1
            elif res:
                purchases += 1

    # Resolve insider_buying_90d (threshold: ≥2 confirmed buys) as a TRI-STATE so a
    # fetch failure never persists as a confirmed False in surge_features.json:
    #   ≥2 confirmed                       → True  (failures can't lower it)
    #   <2 confirmed but could still reach → None  (unknowns might be buys)
    #   <2 even if every unknown were a buy → False (definitive)
    if purchases >= 2:
        insider = True
    elif purchases + unknown >= 2:
        insider = None
    else:
        insider = False
    return {"recent_8k_14d": has_8k, "insider_buying_90d": insider}


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — EDGAR backfill")
    ap.add_argument("--features", default=str(OUT_DIR / "surge_features.json"))
    ap.add_argument("--limit", type=int, default=0, help="cap events (0 = all)")
    args = ap.parse_args()

    feat = json.loads(Path(args.features).read_text(encoding="utf-8"))
    rows = feat["features"]
    todo = rows[:args.limit] if args.limit else rows
    print(f"[edgar] backfilling {len(todo)}/{len(rows)} events (UA={_UA!r})")

    done = 0
    for r in todo:
        asof = r.get("observe_date") or r["surge_start"]
        flags = edgar_flags(r["ticker"], asof)
        r["flags"].update(flags)
        done += 1
        if done % 20 == 0:
            print(f"[edgar]   {done}/{len(todo)}")

    feat["factor_defs"].update({k: {"dimension": d, "subfactor": s, "desc": desc}
                                for k, (d, s, desc) in EDGAR_FACTOR_DEFS.items()})
    feat["edgar_backfilled"] = True
    feat["edgar_note"] = ("Dim2 8-K + Dim4 Form-4 insider buys backfilled from SEC "
                          "EDGAR (free historical). 13F is per-fund, not per-ticker — excluded.")
    feat["generated_at_edgar"] = datetime.now(timezone.utc).isoformat()
    Path(args.features).write_text(json.dumps(feat, indent=2), encoding="utf-8")
    print(f"[edgar] backfilled {done} events → {args.features}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
