#!/usr/bin/env python3
"""Optional local IBKR enrichment for the screener.

The CI screening pipeline stays 100% free (yfinance). This module is an
*opt-in, local-only* enrichment layer: when a TWS / IB Gateway is reachable it
pulls higher-quality data IBKR has and yfinance does not, and otherwise it stays
out of the way so callers transparently fall back to the free path.

Covers three jobs (see the CLI at the bottom):
  1. IV/Greeks  -- backfill real historical implied vol into the iv_history
                   store (yfinance gives only *today's* IV), plus live model
                   Greeks for an option contract.
  2. Account    -- positions / P&L for ledger reconciliation.
  3. Universe   -- IBKR market scanner (top gainers, hot volume, high IV) as a
                   dynamic candidate source.

Design rules (matching iv_history.py / options_free.py):
  * Never raises on a connection/data hiccup -- returns safe empty defaults so a
    flaky Gateway can't break a run.
  * ib_async is imported lazily, so importing this module never fails even when
    the optional dependency is absent (CI never installs it).
  * Connects ``readonly=True`` by default -- this is a data layer; it must not be
    able to place orders.

Setup (local):
  pip install -r requirements-ibkr.txt
  # In TWS/Gateway: Configure > API > Settings > Enable ActiveX and Socket Clients
  # Default ports: TWS paper 7497 / live 7496 ; Gateway paper 4002 / live 4001
  export IBKR_PORT=7497   # optional; auto-detected among common ports otherwise
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Common API ports, tried in order when IBKR_PORT is unset.
# TWS paper, Gateway paper, TWS live, Gateway live.
_DEFAULT_PORTS = (7497, 4002, 7496, 4001)
_DEFAULT_HOST = os.environ.get("IBKR_HOST", "127.0.0.1")
_DEFAULT_CLIENT_ID = int(os.environ.get("IBKR_CLIENT_ID", "17"))
_CONNECT_TIMEOUT = float(os.environ.get("IBKR_TIMEOUT", "6"))


def available() -> bool:
    """True if the optional ib_async dependency is importable. Cheap; no I/O."""
    try:
        import ib_async  # noqa: F401
        return True
    except Exception:
        return False


def _ports_to_try() -> tuple[int, ...]:
    env = os.environ.get("IBKR_PORT")
    if env:
        try:
            return (int(env),)
        except ValueError:
            pass
    return _DEFAULT_PORTS


@contextmanager
def connect(readonly: bool = True, client_id: int | None = None):
    """Yield a connected IB handle, or ``None`` if no Gateway is reachable.

    Always yields (never raises) so callers can simply::

        with connect() as ib:
            if ib is None:
                ... fall back to the free path ...
            else:
                ... use IBKR ...

    Disconnects on exit. ``readonly=True`` (default) blocks order placement.
    """
    if not available():
        yield None
        return

    from ib_async import IB

    ib = IB()
    host = _DEFAULT_HOST
    cid = client_id if client_id is not None else _DEFAULT_CLIENT_ID
    connected = False
    try:
        for port in _ports_to_try():
            try:
                ib.connect(host, port, clientId=cid,
                           timeout=_CONNECT_TIMEOUT, readonly=readonly)
                connected = True
                break
            except Exception:
                # try the next candidate port
                try:
                    ib.disconnect()
                except Exception:
                    pass
        yield ib if connected else None
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 1. IV / Greeks
# --------------------------------------------------------------------------- #

def _iv_history_mod():
    """Load scripts/iv_history.py whether run as a script or imported."""
    try:
        import iv_history as m  # type: ignore
        return m
    except Exception:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "iv_history", Path(__file__).resolve().parent / "iv_history.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m


def historical_iv(ib, ticker: str, duration: str = "1 Y") -> list[tuple[str, float]]:
    """Daily ATM implied-vol series for ``ticker`` as [(YYYY-MM-DD, iv), ...].

    Uses IBKR's OPTION_IMPLIED_VOLATILITY historical measure on the underlying.
    Returns [] on any failure.
    """
    if ib is None:
        return []
    try:
        from ib_async import Stock
        contract = Stock(ticker.upper(), "SMART", "USD")
        ib.qualifyContracts(contract)
        bars = ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting="1 day", whatToShow="OPTION_IMPLIED_VOLATILITY",
            useRTH=True, formatDate=1)
        out = []
        for b in bars or []:
            iv = float(getattr(b, "close", 0) or 0)
            if 0.0 < iv < 10.0:  # same sanity guard as iv_history.record_iv
                out.append((str(b.date)[:10], round(iv, 4)))
        return out
    except Exception:
        return []


def backfill_iv_history(tickers: list[str], duration: str = "1 Y") -> dict[str, int]:
    """Pull real historical IV from IBKR and write it into the iv_history store.

    This is the high-value win: yfinance can't give IV history, so iv_history.py
    otherwise has to accumulate one snapshot/day for ~40 days before IV
    percentile/rank become meaningful. A single backfill makes them real *today*
    -- momentum_options.py already prefers iv_history over its realized-vol proxy,
    so nothing downstream needs to change.

    Returns {ticker: days_written}.
    """
    ivh = _iv_history_mod()
    written: dict[str, int] = {}
    with connect() as ib:
        if ib is None:
            return written
        for t in tickers:
            series = historical_iv(ib, t, duration)
            for day, iv in series:
                ivh.record_iv(t, iv, day=day)
            written[t.upper()] = len(series)
            ib.sleep(0.3)  # be gentle on IBKR historical-data pacing
    return written


def _universe_tickers(source: str | None = None,
                      include_ledger: bool = True,
                      include_store: bool = True) -> list[str]:
    """Resolve the ticker list to backfill.

    Deliberately NOT the full ~773-name hard-filter universe -- IBKR throttles
    historical-data requests (~60 / 10 min), so backfilling everything is
    impractical and pointless. The useful set is what we actually track: the
    ledger's picks plus tickers already in the iv_history store. A ``source``
    JSON path overrides this (a plain list, or the filtered_universe shape with a
    ``tickers`` list of {ticker: ...} dicts).
    """
    seen: dict[str, None] = {}  # ordered de-dupe

    def add(t):
        t = (t or "").strip().upper().lstrip("$")
        if t and t not in seen:
            seen[t] = None

    if source:
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            rows = data.get("tickers", data) if isinstance(data, dict) else data
            for r in rows:
                add(r.get("ticker") if isinstance(r, dict) else r)
        except Exception:
            pass
        return list(seen)

    if include_ledger:
        led = _ROOT / "reports" / "performance_ledger.csv"
        try:
            import csv
            with open(led, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    add(row.get("ticker"))
        except Exception:
            pass
    if include_store:
        store = _ROOT / "reports" / "iv_history"
        try:
            for p in store.glob("*.json"):
                add(p.stem)
        except Exception:
            pass
    return list(seen)


def option_greeks(ib, ticker: str, expiry: str, strike: float,
                  right: str = "C") -> dict:
    """Live model Greeks for one option (delta/gamma/vega/theta/impliedVol).

    expiry is YYYYMMDD. Uses delayed-frozen data (type 3) so it works without a
    real-time market-data subscription. Returns {} on failure.
    """
    if ib is None:
        return {}
    try:
        from ib_async import Option
        ib.reqMarketDataType(3)  # delayed-frozen: no live subscription needed
        opt = Option(ticker.upper(), expiry, float(strike),
                     right.upper(), "SMART")
        ib.qualifyContracts(opt)
        tk = ib.reqMktData(opt, "", False, False)
        ib.sleep(2)  # let model greeks populate
        g = getattr(tk, "modelGreeks", None)
        if not g:
            return {}
        return {
            "impliedVol": getattr(g, "impliedVol", None),
            "delta": getattr(g, "delta", None),
            "gamma": getattr(g, "gamma", None),
            "vega": getattr(g, "vega", None),
            "theta": getattr(g, "theta", None),
            "undPrice": getattr(g, "undPrice", None),
        }
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# 2. Account: positions / P&L for ledger reconciliation
# --------------------------------------------------------------------------- #

def positions() -> list[dict]:
    """Current account positions as normalized dicts. [] if unreachable."""
    with connect() as ib:
        if ib is None:
            return []
        try:
            ib.reqMarketDataType(3)
            out = []
            for p in ib.positions():
                c = p.contract
                out.append({
                    "account": p.account,
                    "symbol": c.symbol,
                    "secType": c.secType,
                    "right": getattr(c, "right", "") or "",
                    "strike": getattr(c, "strike", 0) or 0,
                    "expiry": getattr(c, "lastTradeDateOrContractMonth", "") or "",
                    "position": p.position,
                    "avgCost": p.avgCost,
                })
            return out
        except Exception:
            return []


def pnl() -> list[dict]:
    """Per-account realized/unrealized P&L. [] if unreachable."""
    with connect() as ib:
        if ib is None:
            return []
        try:
            out = []
            for acct in ib.managedAccounts():
                pl = ib.reqPnL(acct)
                ib.sleep(1.5)  # P&L streams in after subscribe
                out.append({
                    "account": acct,
                    "dailyPnL": getattr(pl, "dailyPnL", None),
                    "unrealizedPnL": getattr(pl, "unrealizedPnL", None),
                    "realizedPnL": getattr(pl, "realizedPnL", None),
                })
            return out
        except Exception:
            return []


def _portfolio_items(ib) -> list[dict]:
    """Live portfolio rows w/ market price + P&L (stocks: per-share avgCost)."""
    try:
        ib.reqMarketDataType(3)
        items = ib.portfolio()
        if not items:
            ib.sleep(1.5)  # account update may not have arrived yet
            items = ib.portfolio()
        out = []
        for it in items:
            c = it.contract
            out.append({
                "symbol": c.symbol,            # underlying for options
                "secType": c.secType,
                "right": getattr(c, "right", "") or "",
                "strike": getattr(c, "strike", 0) or 0,
                "expiry": getattr(c, "lastTradeDateOrContractMonth", "") or "",
                "position": it.position,
                "avgCost": it.averageCost,     # per-contract cost (premium x100)
                "marketPrice": it.marketPrice,
                "marketValue": it.marketValue,
                "unrealizedPnL": it.unrealizedPNL,
                "realizedPnL": it.realizedPNL,
            })
        return out
    except Exception:
        return []


def _load_ledger_rows(ledger_path: str | None) -> list[dict]:
    import csv
    p = Path(ledger_path) if ledger_path else (
        _ROOT / "reports" / "performance_ledger.csv")
    try:
        with open(p, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _leg(p: dict) -> dict:
    """Normalize one portfolio row into a display leg with return %."""
    avg = _f(p.get("avgCost")) or 0
    qty = _f(p.get("position")) or 0
    upnl = _f(p.get("unrealizedPnL"))
    cost_basis = avg * abs(qty)
    ret = round(upnl / cost_basis * 100, 1) if (upnl is not None and cost_basis) else None
    label = p["secType"]
    if p["secType"] == "OPT":
        label = f"{p['expiry'][:8]} {p['strike']:g}{p['right']}"
    return {
        "secType": p["secType"], "label": label,
        "right": p.get("right"), "strike": p.get("strike"),
        "expiry": p.get("expiry"), "qty": qty,
        "avg_cost": round(avg, 2), "market_price": p.get("marketPrice"),
        "return_pct": ret, "unrealized_pnl": upnl,
    }


def reconcile(ledger_path: str | None = None) -> dict:
    """Read-only reconciliation: screener picks vs. your real IBKR positions/P&L.

    Options-aware: this is a momentum-OPTIONS workflow, so holdings are grouped by
    *underlying* (the screener picks the stock; you buy calls on it). Each ledger
    pick is matched to the option/stock legs you actually hold on that underlying,
    with per-leg return and unrealized P&L. Pure read -- never places, modifies, or
    cancels anything. Also surfaces ledger picks with no position, and underlyings
    you hold that the screener never flagged. Safe empty result if no Gateway.
    """
    rows = _load_ledger_rows(ledger_path)
    ledger_by_tkr = {(r.get("ticker") or "").upper(): r for r in rows}

    result = {"matched": [], "ledger_not_held": [],
              "held_not_in_ledger": [], "reachable": False}

    with connect() as ib:
        if ib is None:
            return result
        result["reachable"] = True
        port = _portfolio_items(ib)

    # group every holding by underlying symbol
    by_underlying: dict[str, list[dict]] = {}
    for p in port:
        by_underlying.setdefault(p["symbol"].upper(), []).append(p)

    def pack(sym, legs):
        legs = [_leg(p) for p in legs]
        total = sum(l["unrealized_pnl"] or 0 for l in legs)
        return legs, round(total, 2)

    for tkr, r in ledger_by_tkr.items():
        legs_raw = by_underlying.get(tkr)
        if not legs_raw:
            result["ledger_not_held"].append({
                "ticker": tkr, "verdict": r.get("verdict"),
                "scan_date": r.get("scan_date"),
                "suggested_entry_low": _f(r.get("suggested_entry_low")),
                "suggested_entry_high": _f(r.get("suggested_entry_high")),
            })
            continue
        legs, total = pack(tkr, legs_raw)
        result["matched"].append({
            "ticker": tkr, "verdict": r.get("verdict"),
            "scan_date": r.get("scan_date"),
            "suggested_entry_low": _f(r.get("suggested_entry_low")),
            "suggested_entry_high": _f(r.get("suggested_entry_high")),
            "fwd_30d_return": _f(r.get("fwd_30d_return")),
            "legs": legs, "total_unrealized_pnl": total,
        })

    for sym, legs_raw in by_underlying.items():
        if sym not in ledger_by_tkr:
            legs, total = pack(sym, legs_raw)
            result["held_not_in_ledger"].append({
                "ticker": sym, "legs": legs, "total_unrealized_pnl": total,
            })
    return result


# --------------------------------------------------------------------------- #
# 3. Universe: IBKR market scanner
# --------------------------------------------------------------------------- #

# Useful US-equity scan codes for a momentum/surge screener.
SCAN_CODES = {
    "gainers": "TOP_PERC_GAIN",
    "hot_volume": "HOT_BY_VOLUME",
    "high_iv": "HIGH_OPT_IMP_VOLAT",
    "most_active": "MOST_ACTIVE",
}


def scan(kind: str = "gainers", count: int = 25,
         location: str = "STK.US.MAJOR") -> list[str]:
    """Return up to ``count`` ticker symbols from an IBKR market scan.

    ``kind`` is one of SCAN_CODES (or a raw IBKR scanCode). [] if unreachable.
    """
    scan_code = SCAN_CODES.get(kind, kind)
    with connect() as ib:
        if ib is None:
            return []
        try:
            from ib_async import ScannerSubscription
            sub = ScannerSubscription(
                instrument="STK", locationCode=location,
                scanCode=scan_code, numberOfRows=int(count))
            rows = ib.reqScannerData(sub, [])
            syms = []
            for r in rows or []:
                try:
                    syms.append(r.contractDetails.contract.symbol)
                except Exception:
                    continue
            return syms[:count]
        except Exception:
            return []


# --------------------------------------------------------------------------- #
# CLI smoke tests (run with a Gateway up)
# --------------------------------------------------------------------------- #

def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "ping"
    rest = argv[1:]

    if not available():
        print("ib_async not installed. pip install -r requirements-ibkr.txt")
        return 2

    if cmd == "ping":
        with connect() as ib:
            if ib is None:
                print("No IBKR Gateway/TWS reachable on "
                      f"{_DEFAULT_HOST}:{_ports_to_try()}. "
                      "Start TWS/Gateway with the API enabled.")
                return 1
            print(f"Connected. serverVersion={ib.client.serverVersion()} "
                  f"accounts={ib.managedAccounts()}")
        return 0

    if cmd == "backfill-iv":
        # flags: --universe (ledger+store), --file PATH, --max N; else explicit tickers
        max_n = 60
        src = None
        use_universe = False
        explicit = []
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--universe":
                use_universe = True
            elif a == "--file":
                i += 1
                src = rest[i] if i < len(rest) else None
            elif a == "--max":
                i += 1
                max_n = int(rest[i]) if i < len(rest) else max_n
            else:
                explicit.append(a)
            i += 1

        if use_universe or src:
            tickers = _universe_tickers(src)
        else:
            tickers = explicit or ["NVDA"]
        if len(tickers) > max_n:
            print(f"NOTE: {len(tickers)} tickers requested; capping at "
                  f"--max {max_n} to respect IBKR pacing "
                  f"(skipping {len(tickers) - max_n}). Raise with --max N.")
            tickers = tickers[:max_n]
        print(f"backfilling IV for {len(tickers)} tickers: {tickers}")
        res = backfill_iv_history(tickers)
        if not res:
            print("No Gateway reachable -- nothing written.")
            return 1
        for t, n in res.items():
            print(f"{t}: wrote {n} days of real IV into iv_history store")
        return 0

    if cmd == "positions":
        for p in positions():
            print(p)
        return 0

    if cmd == "pnl":
        for p in pnl():
            print(p)
        return 0

    if cmd == "reconcile":
        ledger = None
        if "--ledger" in rest:
            j = rest.index("--ledger")
            ledger = rest[j + 1] if j + 1 < len(rest) else None
        rec = reconcile(ledger)
        if not rec["reachable"]:
            print("No Gateway reachable -- cannot reconcile.")
            return 1
        _print_reconcile(rec)
        out = _ROOT / "reports" / "reconciliation.json"
        try:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            print(f"\nwrote {out}")
        except Exception:
            pass
        return 0

    if cmd == "scan":
        kind = rest[0] if rest else "gainers"
        syms = scan(kind)
        print(f"{kind}: {syms}")
        return 0

    print(__doc__)
    print("commands: ping | backfill-iv [TICKERS... | --universe | --file PATH] "
          "[--max N] | positions | pnl | reconcile [--ledger PATH] | "
          "scan [gainers|hot_volume|high_iv|most_active]")
    return 0


def _fmt_legs(legs: list[dict]) -> str:
    parts = []
    for l in legs:
        ret = f"{l['return_pct']:+.1f}%" if l["return_pct"] is not None else "-"
        pnl = f"${l['unrealized_pnl']:+.0f}" if l["unrealized_pnl"] is not None else "-"
        parts.append(f"{l['qty']:g}x {l['label']} ({ret}, {pnl})")
    return "; ".join(parts)


def _print_reconcile(rec: dict) -> None:
    """Pretty-print an options-aware reconciliation: predicted vs. actual."""
    m = rec["matched"]
    print(f"\n=== 對帳: screener 預測 vs 你的真實持倉 (按底層分組) ===")
    print(f"\n[在 ledger 且你持有] {len(m)} 檔")
    for r in m:
        zone = (f"建議區 {r['suggested_entry_low']}-{r['suggested_entry_high']}"
                if r["suggested_entry_low"] is not None else "")
        print(f"  {r['ticker']} ({r.get('verdict') or '-'}, {r.get('scan_date')}) "
              f"{zone}  合計未實現 ${r['total_unrealized_pnl']:+.0f}")
        print(f"     legs: {_fmt_legs(r['legs'])}")

    nh = rec["ledger_not_held"]
    print(f"\n[screener 有建議、你未持有] {len(nh)} 檔: "
          f"{[r['ticker'] for r in nh]}")

    ext = rec["held_not_in_ledger"]
    print(f"\n[你持有、screener 未追蹤] {len(ext)} 檔")
    for r in sorted(ext, key=lambda x: x["total_unrealized_pnl"], reverse=True):
        print(f"  {r['ticker']}  合計未實現 ${r['total_unrealized_pnl']:+.0f}")
        print(f"     legs: {_fmt_legs(r['legs'])}")


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
