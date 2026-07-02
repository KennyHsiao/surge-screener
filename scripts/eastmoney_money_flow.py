#!/usr/bin/env python3
"""Build curated Eastmoney daily money-flow artifacts.

The provider adapter returns normalized rows for one Eastmoney ``secid``. This
module resolves platform tickers to secids, records coverage, and writes a
publishable flag so downstream scoring can fail closed when coverage is weak.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import global_stock_data as gsd
except ImportError:  # imported as scripts.eastmoney_money_flow
    from scripts import global_stock_data as gsd


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
MIN_COVERAGE = 0.70


def _today() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _dedupe_tickers(tickers: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    out: list[str] = []
    for value in tickers:
        normalized = _ticker(value)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


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
    normalized = _ticker(value)
    if normalized and normalized not in out:
        out.append(normalized)


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


def collect_money_flow_tickers(
    *,
    reports_dir: str | Path = REPORTS_DIR,
    content_dir: str | Path | None = None,
    extra_tickers: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[str]:
    """Collect target tickers from platform candidate/watchlist/theme sources."""
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

    _collect_tickers_from_value(_load_json(reports / "watchlist.json"), out)
    _collect_tickers_from_value(_load_json(content / "industry_role_overrides.json"), out)
    _collect_tickers_from_value(_load_json(content / "theme_baskets.json"), out)
    return out


def load_latest_universe_secid_map(reports_dir: str | Path = REPORTS_DIR) -> dict[str, str]:
    """Load ticker -> Eastmoney secid from the latest universe artifact."""
    universe_dir = Path(reports_dir) / "universe"
    if not universe_dir.is_dir():
        return {}
    files = sorted(
        path for path in universe_dir.glob("*.json")
        if len(path.stem) == 10 and path.stem.count("-") == 2
    )
    if not files:
        return {}
    data = _load_json(files[-1])
    securities = data.get("securities") if isinstance(data, dict) else None
    if not isinstance(securities, list):
        return {}
    out: dict[str, str] = {}
    for security in securities:
        if not isinstance(security, dict):
            continue
        ticker = _ticker(security.get("ticker"))
        secid = str(security.get("eastmoney_secid") or "").strip()
        if ticker and secid:
            out[ticker] = secid
    return out


def resolve_eastmoney_secid(
    ticker: str,
    *,
    search_fetcher: Callable[..., dict[str, Any]] = gsd.eastmoney_search,
) -> str | None:
    """Resolve one US ticker to an Eastmoney secid via search."""
    sym = _ticker(ticker)
    if not sym:
        return None
    try:
        payload = search_fetcher(sym, count=10)
    except Exception:
        return None
    securities = payload.get("securities") if isinstance(payload, dict) else None
    if not isinstance(securities, list):
        return None
    for security in securities:
        if not isinstance(security, dict):
            continue
        if _ticker(security.get("ticker") or security.get("code")) != sym:
            continue
        secid = str(security.get("secid") or "").strip()
        if secid:
            return secid
    return None


def build_money_flow_snapshot(
    tickers: list[str] | tuple[str, ...] | set[str],
    *,
    secid_map: dict[str, str] | None = None,
    as_of_date: str | None = None,
    generated_at: str | None = None,
    flow_fetcher: Callable[..., dict[str, Any]] = gsd.eastmoney_money_flow,
    secid_resolver: Callable[..., dict[str, Any]] | None = gsd.eastmoney_search,
    min_coverage: float = MIN_COVERAGE,
    limit: int = 120,
) -> dict[str, Any]:
    """Build a money-flow snapshot for a ticker set."""
    requested_tickers = _dedupe_tickers(tickers)
    secids = {str(k).upper(): str(v) for k, v in (secid_map or {}).items() if v}
    rows: list[dict[str, Any]] = []
    resolved_tickers = 0

    for ticker in requested_tickers:
        secid = secids.get(ticker)
        if not secid and secid_resolver is not None:
            secid = resolve_eastmoney_secid(ticker, search_fetcher=secid_resolver)
            if secid:
                secids[ticker] = secid
        if not secid:
            continue
        try:
            payload = flow_fetcher(secid, limit=limit)
        except Exception:
            payload = {"status": "unavailable", "rows": []}
        payload_rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(payload_rows, list) or not payload_rows:
            continue
        resolved_tickers += 1
        for row in payload_rows:
            if not isinstance(row, dict):
                continue
            rows.append({
                "ticker": ticker,
                "secid": secid,
                "date": row.get("date"),
                "close": _num(row.get("close")),
                "change_pct": _num(row.get("change_pct")),
                "main_net": _num(row.get("main_net")),
                "main_pct": _num(row.get("main_pct")),
                "super_big_net": _num(row.get("super_big_net")),
                "big_net": _num(row.get("big_net")),
                "mid_net": _num(row.get("mid_net")),
                "small_net": _num(row.get("small_net")),
                "source": "eastmoney_push2his",
                "raw_row": row,
            })

    requested = len(requested_tickers)
    unavailable = max(0, requested - resolved_tickers)
    coverage_ratio = (resolved_tickers / requested) if requested else 0.0
    return {
        "as_of_date": as_of_date or _today(),
        "generated_at": generated_at or _now_iso(),
        "source": "eastmoney_push2his",
        "publishable": bool(requested and coverage_ratio >= min_coverage),
        "coverage": {
            "requested": requested,
            "resolved": resolved_tickers,
            "unavailable": unavailable,
            "coverage_ratio": coverage_ratio,
            "min_coverage": min_coverage,
        },
        "rows": rows,
    }


def write_money_flow_snapshot(
    snapshot: dict[str, Any],
    *,
    reports_dir: str | Path = REPORTS_DIR,
) -> Path:
    """Write dated and latest money-flow JSON artifacts."""
    as_of_date = str(snapshot.get("as_of_date") or _today())[:10]
    out_dir = Path(reports_dir) / "money_flow"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{as_of_date}.json"
    latest = out_dir / "latest.json"
    body = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(tmp, out)
    latest_tmp = latest.with_suffix(latest.suffix + ".tmp")
    latest_tmp.write_text(body + "\n", encoding="utf-8")
    os.replace(latest_tmp, latest)
    return out


def refresh_money_flow(
    tickers: list[str] | tuple[str, ...] | set[str],
    *,
    reports_dir: str | Path = REPORTS_DIR,
    secid_map: dict[str, str] | None = None,
    as_of_date: str | None = None,
    min_coverage: float = MIN_COVERAGE,
    limit: int = 120,
) -> dict[str, Any]:
    resolved_map = secid_map if secid_map is not None else load_latest_universe_secid_map(reports_dir)
    snapshot = build_money_flow_snapshot(
        tickers,
        secid_map=resolved_map,
        as_of_date=as_of_date,
        min_coverage=min_coverage,
        limit=limit,
    )
    out = write_money_flow_snapshot(snapshot, reports_dir=reports_dir)
    return {"path": str(out), **snapshot}


def _parse_tickers(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Eastmoney money-flow artifact")
    parser.add_argument("--tickers", default="", help="Comma-separated tickers, e.g. AAPL,NVDA")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--content-dir", default=str(REPO / "content"))
    parser.add_argument("--as-of-date")
    parser.add_argument("--min-coverage", type=float, default=MIN_COVERAGE)
    parser.add_argument("--limit", type=int, default=120)
    args = parser.parse_args(argv)
    tickers = collect_money_flow_tickers(
        reports_dir=args.reports_dir,
        content_dir=args.content_dir,
        extra_tickers=_parse_tickers(args.tickers),
    )
    if not tickers:
        print(json.dumps({"status": "unavailable", "reason": "no tickers collected"}, ensure_ascii=False))
        return 1

    meta = refresh_money_flow(
        tickers,
        reports_dir=args.reports_dir,
        as_of_date=args.as_of_date,
        min_coverage=args.min_coverage,
        limit=args.limit,
    )
    print(json.dumps({
        "path": meta["path"],
        "publishable": meta["publishable"],
        "coverage": meta["coverage"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
