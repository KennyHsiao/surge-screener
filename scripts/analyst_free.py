#!/usr/bin/env python3
"""Free professional analyst views via yfinance (Dimension 7 / 分析師共識).

Sell-side analyst consensus is a high-quality external signal class distinct
from news/event catalysts: rating distribution, dated upgrades/downgrades,
price targets vs spot, and forward EPS/revenue estimate revisions. yfinance
aggregates these (Yahoo's analyst feeds) for free, so the scoring pipeline can
ground a dedicated analyst dimension on verified numbers instead of letting the
LLM guess them (verified-data-to-AI principle).

`gather_analyst_views(ticker)` NEVER raises — returns None on failure so a flaky
free source can't abort a scoring run (matches the other *_free.py gatherers and
scripts/02_llm_score.py's fetch_* helpers). Each sub-block is isolated, so one
failing feed doesn't lose the others (got_any pattern, like institutional_free).

CLI:  python scripts/analyst_free.py NVDA AMD
"""

from __future__ import annotations

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


def _num(x):
    """Coerce to float or None; tolerate None/NaN/strings."""
    try:
        if x is None:
            return None
        f = float(x)
        return None if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _pct(frac):
    """Fraction (0.23) -> percent (23.0)."""
    v = _num(frac)
    return None if v is None else round(v * 100, 1)


def gather_analyst_views(ticker: str) -> dict | None:
    """Professional analyst consensus snapshot for one ticker, or None.

    Cached 6h — ratings/targets/estimates update infrequently, so this avoids
    re-fetching per pipeline pass and per dashboard interaction."""
    return _cached("analyst_views", {"ticker": ticker.upper()}, 21600,
                   lambda: _compute_analyst_views(ticker))


def _compute_analyst_views(ticker: str) -> dict | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        tk = yf.Ticker(ticker)
    except Exception:
        return None

    out: dict = {"ticker": ticker.upper(), "source": "yfinance_free"}
    got_any = False

    # ── Consensus rating (info-level summary) ──
    try:
        info = tk.info or {}
        consensus = {
            "recommendation": info.get("recommendationKey"),
            "num_analysts": _num(info.get("numberOfAnalystOpinions")),
            "mean_rating_score": _num(info.get("recommendationMean")),  # 1=strongBuy..5=strongSell
        }
        if any(v is not None for v in consensus.values()):
            out["consensus"] = consensus
            got_any = True
    except Exception:
        pass

    # ── Rating distribution (recommendations_summary, most-recent row 0m) ──
    try:
        rs = tk.recommendations_summary
        if rs is not None and not rs.empty:
            r = rs.iloc[0]  # row 0 = "0m" (current month)
            dist = {
                "strong_buy": _num(r.get("strongBuy")),
                "buy": _num(r.get("buy")),
                "hold": _num(r.get("hold")),
                "sell": _num(r.get("sell")),
                "strong_sell": _num(r.get("strongSell")),
            }
            if any(v is not None for v in dist.values()):
                out["rating_distribution"] = dist
                got_any = True
    except Exception:
        pass

    # ── Price targets vs spot (analyst_price_targets is a dict with current) ──
    try:
        pt = tk.analyst_price_targets or {}
        spot = _num(pt.get("current"))
        mean = _num(pt.get("mean"))
        upside = (round((mean - spot) / spot * 100, 1)
                  if spot and mean and spot > 0 else None)
        targets = {
            "spot": spot,
            "high": _num(pt.get("high")),
            "low": _num(pt.get("low")),
            "mean": mean,
            "median": _num(pt.get("median")),
            "upside_pct": upside,
        }
        if any(v is not None for v in targets.values()):
            out["price_targets"] = targets
            got_any = True
    except Exception:
        pass

    # ── Recent rating actions (upgrades_downgrades, dated, newest first) ──
    try:
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            ud = ud.sort_index(ascending=False)
            actions = []
            for idx, r in ud.head(8).iterrows():
                actions.append({
                    "date": str(idx).split(" ")[0],
                    "firm": str(r.get("Firm", "")),
                    "action": str(r.get("Action", "")),
                    "from_grade": str(r.get("FromGrade", "") or ""),
                    "to_grade": str(r.get("ToGrade", "") or ""),
                    "pt_action": str(r.get("priceTargetAction", "") or ""),
                    "pt_current": _num(r.get("currentPriceTarget")),
                    "pt_prior": _num(r.get("priorPriceTarget")),
                })
            if actions:
                out["recent_actions"] = actions
                got_any = True
    except Exception:
        pass

    # ── Forward estimate revisions (earnings_estimate + eps_revisions) ──
    try:
        ee = tk.earnings_estimate
        er = tk.eps_revisions
        revisions = {}
        if ee is not None and not ee.empty:
            for period, label in (("0q", "eps_curr_q"), ("+1q", "eps_next_q"),
                                   ("0y", "eps_curr_year"), ("+1y", "eps_next_year")):
                if period in ee.index:
                    row = ee.loc[period]
                    rev = {
                        "avg": _num(row.get("avg")),
                        "num_analysts": _num(row.get("numberOfAnalysts")),
                        "growth_pct": _pct(row.get("growth")),
                    }
                    if er is not None and not er.empty and period in er.index:
                        erow = er.loc[period]
                        rev["up_last_30d"] = _num(erow.get("upLast30days"))
                        rev["down_last_30d"] = _num(erow.get("downLast30days"))
                    revisions[label] = rev
        if revisions:
            out["estimate_revisions"] = revisions
            got_any = True
    except Exception:
        pass

    return out if got_any else None


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(gather_analyst_views(t), indent=2,
                         ensure_ascii=False, default=str))
