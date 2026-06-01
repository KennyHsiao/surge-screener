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

import os
from contextlib import contextmanager
from pathlib import Path

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
    return written


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
        tickers = rest or ["NVDA"]
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

    if cmd == "scan":
        kind = rest[0] if rest else "gainers"
        syms = scan(kind)
        print(f"{kind}: {syms}")
        return 0

    print(__doc__)
    print("commands: ping | backfill-iv [TICKERS...] | positions | pnl | "
          "scan [gainers|hot_volume|high_iv|most_active]")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
