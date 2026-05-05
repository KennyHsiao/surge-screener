#!/usr/bin/env python3
"""
Stage 7 — Verify Forward Returns
For each past pick in performance_ledger.csv, fill in forward returns:
  fwd_3d, fwd_7d, fwd_14d, fwd_30d, fwd_60d
Mark hit_15pct_within_30d and hit_30pct_within_60d flags.
Compute max_drawdown_30d.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def get_price_data(ticker: str, start_date: str, end_date: str,
                   provider: str = "polygon") -> pd.Series | None:
    """Fetch daily close prices for a ticker in a date range."""
    if provider == "polygon":
        return _fetch_polygon(ticker, start_date, end_date)
    else:
        return _fetch_yfinance(ticker, start_date, end_date)


def _fetch_polygon(ticker: str, start_date: str, end_date: str) -> pd.Series | None:
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        return _fetch_yfinance(ticker, start_date, end_date)

    import httpx
    try:
        resp = httpx.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day"
            f"/{start_date}/{end_date}",
            params={"adjusted": "true", "sort": "asc", "apiKey": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                dates = [datetime.fromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d")
                         for r in results]
                closes = [r["c"] for r in results]
                return pd.Series(closes, index=pd.to_datetime(dates))
    except Exception as e:
        print(f"[verify] Polygon error for {ticker}: {e}", file=sys.stderr)

    return _fetch_yfinance(ticker, start_date, end_date)


def _fetch_yfinance(ticker: str, start_date: str, end_date: str) -> pd.Series | None:
    import yfinance as yf
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if not df.empty:
            return df["Close"].squeeze()
    except Exception:
        pass
    return None


def compute_forward_returns(entry_price: float, prices: pd.Series,
                            scan_date: str) -> dict:
    """Compute forward returns and hit flags from price series."""
    scan_dt = pd.Timestamp(scan_date)
    result = {}

    # Forward returns at specific horizons
    for days, key in [(3, "fwd_3d_return"), (7, "fwd_7d_return"),
                      (14, "fwd_14d_return"), (30, "fwd_30d_return"),
                      (60, "fwd_60d_return")]:
        target_date = scan_dt + timedelta(days=days)
        # Find closest available date
        available = prices[prices.index >= target_date]
        if not available.empty:
            fwd_price = float(available.iloc[0])
            result[key] = round((fwd_price / entry_price - 1) * 100, 2)
        else:
            # Check if we have enough data up to the last available date
            if not prices.empty and prices.index[-1] >= target_date - timedelta(days=5):
                fwd_price = float(prices.iloc[-1])
                result[key] = round((fwd_price / entry_price - 1) * 100, 2)

    # Hit flags
    if "fwd_30d_return" not in result:
        # Not enough data yet for 30d
        pass
    else:
        # Check if +15% was hit within 30 days
        prices_30d = prices[(prices.index > scan_dt) &
                            (prices.index <= scan_dt + timedelta(days=30))]
        if not prices_30d.empty:
            max_30d = float(prices_30d.max())
            result["hit_15pct_within_30d"] = (max_30d / entry_price - 1) >= 0.15

    if "fwd_60d_return" not in result:
        pass
    else:
        prices_60d = prices[(prices.index > scan_dt) &
                            (prices.index <= scan_dt + timedelta(days=60))]
        if not prices_60d.empty:
            max_60d = float(prices_60d.max())
            result["hit_30pct_within_60d"] = (max_60d / entry_price - 1) >= 0.30

    # Max drawdown within 30 days
    prices_30d = prices[(prices.index > scan_dt) &
                        (prices.index <= scan_dt + timedelta(days=30))]
    if not prices_30d.empty:
        min_price = float(prices_30d.min())
        result["max_drawdown_30d"] = round((min_price / entry_price - 1) * 100, 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Stage 7: Verify Returns")
    parser.add_argument("--ledger", required=True,
                        help="Path to performance_ledger.csv")
    parser.add_argument("--provider", default="polygon",
                        choices=["polygon", "yfinance"])
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"[verify] Ledger not found: {args.ledger}", file=sys.stderr)
        sys.exit(1)

    # Read ledger
    rows = []
    with open(ledger_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    if not rows:
        print("[verify] Ledger is empty")
        return

    updated_count = 0
    today = datetime.utcnow()

    for row in rows:
        scan_date = row.get("scan_date", "")
        ticker = row.get("ticker", "")
        if not scan_date or not ticker:
            continue

        # Skip if all forward returns already filled
        if (row.get("fwd_3d_return") and row.get("fwd_7d_return")
                and row.get("fwd_14d_return") and row.get("fwd_30d_return")
                and row.get("fwd_60d_return")):
            continue

        scan_dt = datetime.strptime(scan_date, "%Y-%m-%d")
        days_since = (today - scan_dt).days

        # Need at least 3 days of data
        if days_since < 3:
            continue

        # Determine entry price (use suggested_entry_low or fetch close on scan_date)
        entry_price_str = row.get("suggested_entry_low", "")
        entry_price = None
        if entry_price_str:
            try:
                entry_price = float(entry_price_str)
            except (ValueError, TypeError):
                pass

        # Fetch price data
        end_date = min(scan_dt + timedelta(days=70), today)
        prices = get_price_data(
            ticker,
            scan_date,
            end_date.strftime("%Y-%m-%d"),
            provider=args.provider,
        )

        if prices is None or prices.empty:
            continue

        # If no entry price, use close on scan date
        if entry_price is None or entry_price <= 0:
            scan_prices = prices[prices.index <= pd.Timestamp(scan_date) + timedelta(days=1)]
            if not scan_prices.empty:
                entry_price = float(scan_prices.iloc[0])
            else:
                entry_price = float(prices.iloc[0])

        # Compute forward returns
        fwd = compute_forward_returns(entry_price, prices, scan_date)

        # Update row with computed values
        changed = False
        for key in ["fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
                     "fwd_30d_return", "fwd_60d_return", "max_drawdown_30d"]:
            if key in fwd and not row.get(key):
                row[key] = fwd[key]
                changed = True

        for key in ["hit_15pct_within_30d", "hit_30pct_within_60d"]:
            if key in fwd and not row.get(key):
                row[key] = str(fwd[key])
                changed = True

        if changed:
            updated_count += 1

    # Write updated ledger
    with open(ledger_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[verify] Updated {updated_count} rows in {args.ledger}")


if __name__ == "__main__":
    main()
