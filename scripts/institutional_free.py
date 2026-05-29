#!/usr/bin/env python3
"""Free institutional ownership + insider activity (Dimension 4 / 籌碼).

Fills surge-screener's weakest-sourced dimension. Replicates the *capability* of
Dexter's paid Financial-Datasets 13F + Form-4 tools using a FREE source:
yfinance, which aggregates the same SEC filings (13F institutional holdings and
Form-4 insider transactions) via Yahoo. (Direct SEC EDGAR submissions/XML parsing
is a possible future fallback, but yfinance is materially simpler and covers the
need.) Pure data fetch → fed to the LLM; the model never sources it itself
(verified-data-to-AI principle).

`gather_institutional(ticker)` NEVER raises — returns None on failure so a flaky
free source can't abort a scoring run (matches the other fetch_* helpers).

CLI:  python scripts/institutional_free.py NVDA
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
    try:
        if x is None:
            return None
        f = float(x)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _pct(frac):
    """Fraction (0.7078) -> percent (70.8)."""
    v = _num(frac)
    return None if v is None else round(v * 100, 1)


def gather_institutional(ticker: str) -> dict | None:
    """Cached 6h (13F/insider data updates infrequently)."""
    return _cached("institutional", {"ticker": ticker.upper()}, 21600,
                   lambda: _compute_institutional(ticker))


def _compute_institutional(ticker: str) -> dict | None:
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        return None

    try:
        tk = yf.Ticker(ticker)
    except Exception:
        return None

    out: dict = {"ticker": ticker.upper(), "source": "yfinance_free"}
    got_any = False

    # ── Ownership split (insiders vs institutions) ──
    try:
        mh = tk.major_holders
        if mh is not None and not mh.empty and "Value" in mh.columns:
            v = mh["Value"]
            out["ownership_pct"] = {
                "insiders_held": _pct(v.get("insidersPercentHeld")),
                "institutions_held": _pct(v.get("institutionsPercentHeld")),
                "institutions_float_held": _pct(v.get("institutionsFloatPercentHeld")),
            }
            got_any = True
    except Exception:
        pass

    # ── Top institutional holders (13F-derived) ──
    try:
        ih = tk.institutional_holders
        if ih is not None and not ih.empty:
            top = []
            for _, r in ih.head(5).iterrows():
                top.append({
                    "holder": str(r.get("Holder", "")),
                    "pct_held": _pct(r.get("pctHeld")),
                    "value": _num(r.get("Value")),
                    "pct_change": _pct(r.get("pctChange")),
                })
            if top:
                out["top_institutional_holders"] = top
                got_any = True
    except Exception:
        pass

    # ── Insider activity, last 6 months (Form-4-derived) ──
    try:
        ip = tk.insider_purchases
        if ip is not None and not ip.empty:
            label_col = ip.columns[0]
            d = {str(r[label_col]): r for _, r in ip.iterrows()}

            def _row(key, field):
                for k, r in d.items():
                    if key in k:
                        return _num(r.get(field))
                return None

            buys = _row("Purchases", "Shares")
            sells = _row("Sales", "Shares")
            net = _row("Net Shares", "Shares")
            out["insider_6m"] = {
                "purchase_shares": buys,
                "purchase_trans": _row("Purchases", "Trans"),
                "sale_shares": sells,
                "sale_trans": _row("Sales", "Trans"),
                "net_shares": net,
                "net_direction": (
                    "buying" if (net or 0) > 0 else
                    "selling" if (net or 0) < 0 else "neutral"),
            }
            got_any = True
    except Exception:
        pass

    # ── A few most-recent insider transactions for color ──
    try:
        it = tk.insider_transactions
        if it is not None and not it.empty:
            recent = []
            for _, r in it.head(5).iterrows():
                # The "Transaction" column is often blank; the human-readable
                # description (e.g. "Sale at price 171.97 - 177.51") is in "Text".
                desc = str(r.get("Text", "") or r.get("Transaction", "")).strip()
                recent.append({
                    "insider": str(r.get("Insider", "")),
                    "position": str(r.get("Position", "")),
                    "transaction": desc,
                    "shares": _num(r.get("Shares")),
                    "date": str(r.get("Start Date", "")).split(" ")[0],
                })
            if recent:
                out["recent_insider_transactions"] = recent
                got_any = True
    except Exception:
        pass

    return out if got_any else None


if __name__ == "__main__":
    import json
    import sys
    for t in (sys.argv[1:] or ["NVDA"]):
        print(f"=== {t} ===")
        print(json.dumps(gather_institutional(t), indent=2, ensure_ascii=False, default=str))
