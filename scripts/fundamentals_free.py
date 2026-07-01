#!/usr/bin/env python3
"""Free fundamentals / key ratios via yfinance.

Replicates (with a free source) the *capabilities* of Dexter's paid
Financial-Datasets key-ratios/fundamentals tools, so the scoring pipeline and
Layer-3 DD can analyze real valuation/profitability/growth/leverage numbers
instead of guessing them. Pure data fetch — the LLM never sources these itself
(verified-data-to-AI principle).

`gather_fundamentals(ticker)` NEVER raises: it returns None on any failure so a
flaky/free source can't abort a scoring run (matches scripts/02_llm_score.py's
fetch_* helpers and scripts/sentiment_free.py).

CLI:  python scripts/fundamentals_free.py NVDA MU
"""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


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


def _num(x):
    """Coerce to float or None; tolerate None/NaN/strings."""
    try:
        if x is None:
            return None
        f = float(x)
        return None if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _pct(x):
    """yfinance margins/growth come as fractions (0.23) — present as % rounded."""
    v = _num(x)
    return None if v is None else round(v * 100, 1)


def load_official_metrics(
    ticker: str,
    *,
    reports_dir: str | Path | None = None,
    limit: int = 24,
) -> list[dict]:
    """Read latest normalized SEC/Eastmoney metrics for one ticker if present."""
    sym = str(ticker or "").upper().lstrip("$")
    if not sym:
        return []
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    path = reports / "fundamentals" / "latest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("rows") if isinstance(data, dict) else []
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker") or "").upper().lstrip("$") != sym:
            continue
        out.append({
            "period_end": row.get("period_end"),
            "metric": row.get("metric"),
            "label": row.get("label"),
            "value": row.get("value"),
            "unit": row.get("unit"),
            "source": row.get("source"),
            "confidence": row.get("confidence"),
            "source_conflict": bool(row.get("source_conflict")),
        })
    out.sort(key=lambda r: (str(r.get("period_end") or ""), str(r.get("source") or "")), reverse=True)
    return out[: max(0, int(limit))]


def gather_fundamentals(ticker: str) -> dict | None:
    """Curated free fundamentals snapshot for one ticker, or None on failure.

    Cached for 6h (fundamentals change slowly; avoids re-fetching per pipeline
    pass and per dashboard interaction)."""
    # "v" bumps when the output schema changes so stale cached entries (which would
    # silently lack a new field) are invalidated. v3 = official_metrics fallback.
    return _cached("fundamentals", {"ticker": ticker.upper(), "v": 3}, 21600,
                   lambda: _compute_fundamentals(ticker))


def _official_metrics_snapshot(ticker: str) -> dict | None:
    official_metrics = load_official_metrics(ticker)
    if not official_metrics:
        return None
    return {
        "ticker": ticker.upper(),
        "source": "fundamental_metrics",
        "official_metrics": official_metrics,
    }


def _compute_fundamentals(ticker: str) -> dict | None:
    official_snapshot = _official_metrics_snapshot(ticker)
    try:
        import yfinance as yf
    except ImportError:
        return official_snapshot

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return official_snapshot
    if not info:
        return official_snapshot

    out = {
        "ticker": ticker.upper(),
        "source": "yfinance_free",
        "sector": info.get("sector"),  # GICS sector → SPDR ETF for Dimension 5 rotation
        "valuation": {
            "market_cap": _num(info.get("marketCap")),
            "trailing_pe": _num(info.get("trailingPE")),
            "forward_pe": _num(info.get("forwardPE")),
            "price_to_book": _num(info.get("priceToBook")),
            "price_to_sales": _num(info.get("priceToSalesTrailing12Months")),
            "peg_ratio": _num(info.get("pegRatio") or info.get("trailingPegRatio")),
            "ev_to_ebitda": _num(info.get("enterpriseToEbitda")),
        },
        "profitability_pct": {
            "gross_margin": _pct(info.get("grossMargins")),
            "operating_margin": _pct(info.get("operatingMargins")),
            "profit_margin": _pct(info.get("profitMargins")),
            "return_on_equity": _pct(info.get("returnOnEquity")),
            "return_on_assets": _pct(info.get("returnOnAssets")),
        },
        "growth_pct": {
            "revenue_growth": _pct(info.get("revenueGrowth")),
            "earnings_growth": _pct(info.get("earningsGrowth")),
            "earnings_q_growth_yoy": _pct(info.get("earningsQuarterlyGrowth")),
        },
        "health": {
            "debt_to_equity": _num(info.get("debtToEquity")),
            "current_ratio": _num(info.get("currentRatio")),
            "quick_ratio": _num(info.get("quickRatio")),
            "free_cashflow": _num(info.get("freeCashflow")),
            "total_cash": _num(info.get("totalCash")),
            "total_debt": _num(info.get("totalDebt")),
        },
        "estimates": {
            "recommendation": info.get("recommendationKey"),
            "num_analysts": _num(info.get("numberOfAnalystOpinions")),
            "target_mean_price": _num(info.get("targetMeanPrice")),
        },
    }
    if official_snapshot:
        out["official_metrics"] = official_snapshot["official_metrics"]
    # Drop sub-dicts that are entirely empty so the LLM context stays clean.
    out = {k: v for k, v in out.items()
           if not isinstance(v, dict) or any(x is not None for x in v.values())}
    return out


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(gather_fundamentals(t), indent=2, ensure_ascii=False))
