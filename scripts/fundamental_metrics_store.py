#!/usr/bin/env python3
"""Normalize official/secondary fundamental metrics into long-form snapshots."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"

SEC_CONFIDENCE = 95
EASTMONEY_CONFIDENCE = 70

SEC_METRICS: dict[str, dict[str, Any]] = {
    "revenue": {
        "label": "Revenue",
        "concepts": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    },
    "net_income": {"label": "Net Income", "concepts": ("NetIncomeLoss",)},
    "diluted_eps": {"label": "Diluted EPS", "concepts": ("EarningsPerShareDiluted",)},
    "total_assets": {"label": "Total Assets", "concepts": ("Assets",)},
    "total_liabilities": {"label": "Total Liabilities", "concepts": ("Liabilities",)},
    "stockholders_equity": {
        "label": "Stockholders' Equity",
        "concepts": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    },
    "operating_cash_flow": {
        "label": "Operating Cash Flow",
        "concepts": ("NetCashProvidedByUsedInOperatingActivities",),
    },
    "research_and_development": {
        "label": "Research and Development",
        "concepts": ("ResearchAndDevelopmentExpense",),
    },
    "share_repurchases": {
        "label": "Share Repurchases",
        "concepts": ("PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"),
    },
}

EASTMONEY_METRICS: dict[str, dict[str, Any]] = {
    "eps": {
        "label": "EPS",
        "unit": "per_share",
        "fields": ("BASIC_EPS", "EPSJB", "EPS", "basic_eps", "eps"),
    },
    "return_on_equity": {
        "label": "Return on Equity",
        "unit": "percent",
        "fields": ("ROEJQ", "ROE", "JQROE", "return_on_equity"),
    },
    "return_on_assets": {
        "label": "Return on Assets",
        "unit": "percent",
        "fields": ("ROA", "ROAJQ", "return_on_assets"),
    },
    "gross_margin": {
        "label": "Gross Margin",
        "unit": "percent",
        "fields": ("GROSS_PROFIT_RATIO", "GROSSPROFIT_MARGIN", "gross_margin"),
    },
    "asset_liability_ratio": {
        "label": "Asset-Liability Ratio",
        "unit": "percent",
        "fields": ("ASSET_LIAB_RATIO", "DEBT_ASSET_RATIO", "asset_liability_ratio"),
    },
}


def _today() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "--", "None", "nan"}:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return None if out != out else out


def _int_or_none(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _json_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _date_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if text else None


def _normalize_cik(cik: Any) -> str | None:
    text = str(cik or "").strip()
    if not text:
        return None
    try:
        return f"{int(text):010d}"
    except ValueError:
        return text.zfill(10) if text.isdigit() else text


def _base_row(*, as_of_date: str, ticker: str, cik: str | None) -> dict[str, Any]:
    return {
        "as_of_date": as_of_date,
        "ticker": ticker.upper().lstrip("$"),
        "cik": _normalize_cik(cik),
        "source_conflict": False,
        "conflict_json": None,
    }


def rows_from_sec_companyfacts(
    ticker: str,
    cik: str,
    payload: dict[str, Any] | None,
    *,
    as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    """Extract selected SEC XBRL companyfacts into long-form metric rows."""
    if not isinstance(payload, dict):
        return []
    facts = payload.get("facts") if isinstance(payload.get("facts"), dict) else {}
    us_gaap = facts.get("us-gaap") if isinstance(facts.get("us-gaap"), dict) else {}
    snapshot_date = str(as_of_date or _today())[:10]
    rows: list[dict[str, Any]] = []

    for metric, config in SEC_METRICS.items():
        concept_data = None
        concept_name = None
        for concept in config["concepts"]:
            candidate = us_gaap.get(concept)
            if isinstance(candidate, dict):
                concept_data = candidate
                concept_name = concept
                break
        if not concept_data:
            continue
        label = concept_data.get("label") or config["label"]
        units = concept_data.get("units") if isinstance(concept_data.get("units"), dict) else {}
        for unit, facts_for_unit in units.items():
            if not isinstance(facts_for_unit, list):
                continue
            for fact in facts_for_unit:
                if not isinstance(fact, dict):
                    continue
                value = _num(fact.get("val"))
                if value is None:
                    continue
                row = _base_row(as_of_date=snapshot_date, ticker=ticker, cik=cik)
                row.update({
                    "period_end": _date_text(fact.get("end")),
                    "fiscal_year": _int_or_none(fact.get("fy")),
                    "fiscal_period": fact.get("fp"),
                    "form": fact.get("form"),
                    "filed_at": _date_text(fact.get("filed")),
                    "metric": metric,
                    "label": label,
                    "value": value,
                    "unit": unit,
                    "source": "sec_companyfacts",
                    "confidence": SEC_CONFIDENCE,
                    "raw_metric_json": _json_blob({**fact, "concept": concept_name}),
                })
                rows.append(row)
    return rows


def _eastmoney_items(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    candidates: list[Any] = [
        ((payload.get("result") or {}).get("data") if isinstance(payload.get("result"), dict) else None),
        (payload.get("data") or {}).get("diff") if isinstance(payload.get("data"), dict) else None,
        payload.get("data"),
        payload.get("result"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = list(candidate.values())
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _first_value(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in row and row.get(field) not in (None, "", "-", "--"):
            return row.get(field)
    return None


def rows_from_eastmoney_gmainindicator(
    ticker: str,
    payload: dict[str, Any] | None,
    *,
    as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    """Extract curated Eastmoney GMAININDICATOR rows as secondary metrics."""
    snapshot_date = str(as_of_date or _today())[:10]
    rows: list[dict[str, Any]] = []
    for item in _eastmoney_items(payload):
        period_end = _date_text(
            item.get("REPORT_DATE")
            or item.get("END_DATE")
            or item.get("report_date")
            or item.get("date")
        )
        fiscal_year = _int_or_none(item.get("REPORT_YEAR")) or (
            int(period_end[:4]) if period_end and period_end[:4].isdigit() else None
        )
        fiscal_period = item.get("REPORT_PERIOD") or item.get("REPORT_TYPE") or item.get("REPORT_NAME")
        for metric, config in EASTMONEY_METRICS.items():
            value = _num(_first_value(item, config["fields"]))
            if value is None:
                continue
            row = _base_row(as_of_date=snapshot_date, ticker=ticker, cik=None)
            row.update({
                "period_end": period_end,
                "fiscal_year": fiscal_year,
                "fiscal_period": fiscal_period,
                "form": None,
                "filed_at": None,
                "metric": metric,
                "label": config["label"],
                "value": value,
                "unit": config["unit"],
                "source": "eastmoney_gmainindicator",
                "confidence": EASTMONEY_CONFIDENCE,
                "raw_metric_json": _json_blob(item),
            })
            rows.append(row)
    return rows


def mark_source_conflicts(rows: list[dict[str, Any]], *, threshold_pct: float = 10.0) -> list[dict[str, Any]]:
    """Mark material same-period/source metric disagreements for UI review."""
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("ticker") or ""),
            str(row.get("period_end") or ""),
            str(row.get("metric") or ""),
        )
        by_key.setdefault(key, []).append(row)

    for group in by_key.values():
        if len({row.get("source") for row in group}) < 2:
            continue
        sec_values = [
            _num(row.get("value"))
            for row in group
            if row.get("source") == "sec_companyfacts" and _num(row.get("value")) is not None
        ]
        if not sec_values:
            continue
        base = sec_values[0]
        if base in (None, 0):
            continue
        for row in group:
            value = _num(row.get("value"))
            if value is None:
                continue
            diff_pct = abs(value - base) / abs(base) * 100
            if diff_pct >= threshold_pct:
                row["source_conflict"] = True
                row["conflict_json"] = _json_blob({
                    "sec_value": base,
                    "row_value": value,
                    "diff_pct": round(diff_pct, 2),
                    "threshold_pct": threshold_pct,
                })
    return rows


def build_fundamental_metrics_snapshot(
    ticker_ciks: dict[str, str | None],
    *,
    sec_fetcher: Callable[[str], dict[str, Any] | None] | None = None,
    eastmoney_fetcher: Callable[[str], dict[str, Any] | None] | None = None,
    as_of_date: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a fundamentals snapshot from injected or live providers."""
    snapshot_date = str(as_of_date or _today())[:10]
    rows: list[dict[str, Any]] = []
    for ticker, cik in sorted((ticker_ciks or {}).items()):
        sym = str(ticker or "").upper().lstrip("$")
        normalized_cik = _normalize_cik(cik)
        if not sym or not normalized_cik:
            continue
        sec_rows: list[dict[str, Any]] = []
        if sec_fetcher:
            sec_rows = rows_from_sec_companyfacts(
                sym,
                normalized_cik,
                sec_fetcher(normalized_cik),
                as_of_date=snapshot_date,
            )
            rows.extend(sec_rows)
        if eastmoney_fetcher and sec_rows:
            rows.extend(rows_from_eastmoney_gmainindicator(
                sym,
                eastmoney_fetcher(sym),
                as_of_date=snapshot_date,
            ))
    mark_source_conflicts(rows)
    return {
        "as_of_date": snapshot_date,
        "generated_at": generated_at or _now_iso(),
        "source": "fundamental_metrics",
        "row_count": len(rows),
        "rows": rows,
    }


def write_fundamental_metrics_snapshot(
    snapshot: dict[str, Any],
    *,
    reports_dir: str | Path | None = None,
) -> Path:
    reports = Path(reports_dir) if reports_dir is not None else REPORTS_DIR
    as_of = str(snapshot.get("as_of_date") or _today())[:10]
    out_dir = reports / "fundamentals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{as_of}.json"
    latest = out_dir / "latest.json"
    body = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(tmp, out)
    latest_tmp = latest.with_suffix(latest.suffix + ".tmp")
    latest_tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(latest_tmp, latest)
    return out


def _sec_get_json(url: str, *, headers: dict[str, str], timeout: int = 20) -> dict[str, Any]:
    import httpx
    response = httpx.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_sec_companyfacts(cik: str, get_json: Callable[..., dict[str, Any]] = _sec_get_json) -> dict[str, Any] | None:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT") or os.environ.get("EDGAR_USER_AGENT")
    if not user_agent:
        return None
    normalized = _normalize_cik(cik)
    if not normalized:
        return None
    try:
        return get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json",
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=20,
        )
    except Exception:
        return None


def _eastmoney_secucode(ticker: str, secid: str | None = None) -> str:
    sym = ticker.upper().lstrip("$")
    if secid:
        prefix = str(secid).split(".", 1)[0]
        if prefix == "105":
            return f"{sym}.O"
        if prefix == "106":
            return f"{sym}.N"
    return f"{sym}.O"


def _eastmoney_get_json(url: str, *, params: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    import httpx
    response = httpx.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_eastmoney_gmainindicator(
    ticker: str,
    *,
    secid: str | None = None,
    get_json: Callable[..., dict[str, Any]] = _eastmoney_get_json,
) -> dict[str, Any] | None:
    secucode = _eastmoney_secucode(ticker, secid=secid)
    columns = ",".join([
        "SECURITY_CODE",
        "SECUCODE",
        "SECURITY_NAME_ABBR",
        "REPORT_DATE",
        "REPORT_YEAR",
        "REPORT_PERIOD",
        "REPORT_TYPE",
        "BASIC_EPS",
        "ROEJQ",
        "ROA",
        "GROSS_PROFIT_RATIO",
        "ASSET_LIAB_RATIO",
    ])
    try:
        return get_json(
            "https://datacenter.eastmoney.com/securities/api/data/v1/get",
            params={
                "reportName": "RPT_F10_FINANCE_GMAININDICATOR",
                "columns": columns,
                "filter": f'(SECUCODE="{secucode}")',
                "pageNumber": 1,
                "pageSize": 8,
                "sortTypes": -1,
                "sortColumns": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            },
            timeout=15,
        )
    except Exception:
        return None


def _latest_universe_file(reports_dir: Path) -> Path | None:
    universe_dir = reports_dir / "universe"
    if not universe_dir.is_dir():
        return None
    files = sorted(path for path in universe_dir.glob("*.json") if len(path.stem) == 10)
    return files[-1] if files else None


def load_universe_ciks(reports_dir: str | Path | None = None, tickers: list[str] | None = None) -> dict[str, str | None]:
    reports = Path(reports_dir) if reports_dir is not None else REPORTS_DIR
    path = _latest_universe_file(reports)
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    wanted = {t.upper().lstrip("$") for t in tickers or []}
    out: dict[str, str | None] = {}
    securities = data.get("securities") if isinstance(data.get("securities"), list) else []
    for security in securities:
        if not isinstance(security, dict):
            continue
        sym = str(security.get("ticker") or "").upper().lstrip("$")
        if not sym or (wanted and sym not in wanted):
            continue
        out[sym] = _normalize_cik(security.get("cik"))
    return out


def load_universe_secids(reports_dir: str | Path | None = None, tickers: list[str] | None = None) -> dict[str, str | None]:
    reports = Path(reports_dir) if reports_dir is not None else REPORTS_DIR
    path = _latest_universe_file(reports)
    if not path:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    wanted = {t.upper().lstrip("$") for t in tickers or []}
    out: dict[str, str | None] = {}
    securities = data.get("securities") if isinstance(data.get("securities"), list) else []
    for security in securities:
        if not isinstance(security, dict):
            continue
        sym = str(security.get("ticker") or "").upper().lstrip("$")
        if not sym or (wanted and sym not in wanted):
            continue
        out[sym] = str(security.get("eastmoney_secid") or "").strip() or None
    return out


def refresh_fundamental_metrics(
    *,
    tickers: list[str] | None = None,
    ticker_ciks: dict[str, str | None] | None = None,
    reports_dir: str | Path | None = None,
    as_of_date: str | None = None,
    include_eastmoney: bool = True,
    sec_fetcher: Callable[[str], dict[str, Any] | None] | None = None,
    eastmoney_fetcher: Callable[..., dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    reports = Path(reports_dir) if reports_dir is not None else REPORTS_DIR
    mapping = ticker_ciks or load_universe_ciks(reports, tickers=tickers)
    secids = load_universe_secids(reports, tickers=tickers)
    sec_source = sec_fetcher or fetch_sec_companyfacts
    eastmoney_source = eastmoney_fetcher or fetch_eastmoney_gmainindicator

    def _eastmoney_for(ticker: str) -> dict[str, Any] | None:
        try:
            return eastmoney_source(ticker, secid=secids.get(str(ticker).upper()))
        except TypeError:
            return eastmoney_source(ticker)

    snapshot = build_fundamental_metrics_snapshot(
        mapping,
        sec_fetcher=sec_source,
        eastmoney_fetcher=(_eastmoney_for if include_eastmoney else None),
        as_of_date=as_of_date,
    )
    out = write_fundamental_metrics_snapshot(snapshot, reports_dir=reports)
    return {"path": str(out), **snapshot}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write reports/fundamentals/YYYY-MM-DD.json")
    parser.add_argument("tickers", nargs="*", help="optional tickers; defaults to latest universe with CIKs")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--as-of-date")
    parser.add_argument("--no-eastmoney", action="store_true")
    args = parser.parse_args(argv)
    result = refresh_fundamental_metrics(
        tickers=args.tickers or None,
        reports_dir=args.reports_dir,
        as_of_date=args.as_of_date,
        include_eastmoney=not args.no_eastmoney,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
