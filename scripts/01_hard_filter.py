#!/usr/bin/env python3
"""
Stage 1 — Hard Filter
Pulls universe tickers, applies the 7 hard filters from the screener prompt.
Outputs filtered_universe.json — typically ~1500 (sp1500 default) → a few hundred
tickers (the optional russell3000 path starts from ~3000).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from run_status import RunStatus

REPO = Path(__file__).resolve().parent.parent
YF_CACHE_DIR = REPO / "reports" / ".cache" / "yfinance"
DEFAULT_FILTER_RULES = {
    "max_ret_5d": 30.0,
    "max_ret_20d": 60.0,
    "min_avg_dollar_vol": 5_000_000.0,
    "min_market_cap": 300_000_000.0,
    "min_price": 5.0,
    "earnings_exclude_days": 2,
}


def _configure_yfinance_cache() -> None:
    """Keep yfinance's SQLite cookie/timezone cache inside the repo.

    On locked-down local runs the default macOS/Linux user cache directory may be
    unwritable, which causes peewee `OperationalError: unable to open database file`.
    The repo cache is writable in this project and keeps the failure local.
    """
    try:
        YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = getattr(yf, "cache", None)
        setter = getattr(cache, "set_cache_location", None)
        if callable(setter):
            setter(str(YF_CACHE_DIR))
    except Exception as e:  # noqa: BLE001 - cache must never break the scan
        print(f"[hard_filter] yfinance cache setup skipped: {e}", file=sys.stderr)


_configure_yfinance_cache()


# ---------------------------------------------------------------------------
# Universe loaders
# ---------------------------------------------------------------------------

def _read_html_with_headers(url: str) -> list[pd.DataFrame]:
    """pd.read_html with a browser-like User-Agent to avoid 403."""
    import io
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36"),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    return pd.read_html(io.StringIO(html))


def _get_sp1500_tickers() -> list[str]:
    """S&P 1500 = S&P 500 + S&P 400 + S&P 600."""
    tables = _read_html_with_headers(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    sp500 = list(tables[0]["Symbol"].str.replace(".", "-", regex=False))
    try:
        t400 = _read_html_with_headers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
        sp400 = list(t400[0]["Symbol"].str.replace(".", "-", regex=False))
    except Exception:
        sp400 = []
    try:
        t600 = _read_html_with_headers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies")
        sp600 = list(t600[0]["Symbol"].str.replace(".", "-", regex=False))
    except Exception:
        sp600 = []
    return sorted(set(sp500 + sp400 + sp600))


def _get_russell3000_tickers() -> list[str]:
    """Fall back to S&P 1500 if Russell 3000 list unavailable."""
    try:
        url = "https://en.wikipedia.org/wiki/Russell_3000_Index"
        tables = _read_html_with_headers(url)
        for t in tables:
            if "Ticker" in t.columns:
                return sorted(t["Ticker"].dropna().tolist())
    except Exception:
        pass
    return _get_sp1500_tickers()


def _get_nasdaq_tickers() -> list[str]:
    tables = _read_html_with_headers("https://en.wikipedia.org/wiki/Nasdaq-100")
    for t in tables:
        if "Ticker" in t.columns:
            return sorted(t["Ticker"].str.replace(".", "-", regex=False).tolist())
        if "Symbol" in t.columns:
            return sorted(t["Symbol"].str.replace(".", "-", regex=False).tolist())
    return []


def load_universe(universe: str, markets: str) -> list[str]:
    """Return list of tickers for the requested universe."""
    if universe == "custom":
        raw = os.environ.get("STOCKS", "")
        return [t.strip() for t in raw.split(",") if t.strip()]

    loaders = {
        "sp1500": _get_sp1500_tickers,
        "russell3000": _get_russell3000_tickers,
        "nasdaq_only": _get_nasdaq_tickers,
    }
    loader = loaders.get(universe, _get_sp1500_tickers)
    tickers = loader()
    print(f"[hard_filter] Loaded {len(tickers)} tickers for universe={universe}")
    return tickers


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

def fetch_batch_data(tickers: list[str], period: str = "6mo", *,
                     batch_size: int = 25, threads: bool = False,
                     progress_callback=None) -> dict[str, pd.DataFrame]:
    """Download OHLCV history for a batch of tickers via yfinance."""
    result = {}
    batch_size = max(1, int(batch_size or 1))
    total_batches = max(1, (len(tickers) + batch_size - 1) // batch_size)
    for batch_no, i in enumerate(range(0, len(tickers), batch_size), start=1):
        batch = tickers[i : i + batch_size]
        try:
            # Download without group_by — returns MultiIndex (Price, Ticker)
            data = yf.download(batch, period=period,
                               threads=threads, progress=False)
            if data.empty:
                continue

            if len(batch) == 1:
                ticker = batch[0]
                # Single ticker: flatten MultiIndex if present
                df = data.copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    result[ticker] = df
            else:
                # Multi ticker: columns are (Price, Ticker) MultiIndex
                for ticker in batch:
                    try:
                        # Extract per-ticker data using xs
                        df = data.xs(ticker, level=1, axis=1).dropna(how="all")
                        if not df.empty:
                            result[ticker] = df
                    except (KeyError, TypeError):
                        pass
        except Exception as e:
            print(f"[hard_filter] Batch download error: {e}", file=sys.stderr)
        event = {
            "completed_batches": batch_no,
            "total_batches": total_batches,
            "batch_size": batch_size,
            "batch": batch,
            "downloaded_tickers": len(result),
        }
        print(
            f"[hard_filter] Downloaded batch {batch_no}/{total_batches} "
            f"({len(result)}/{len(tickers)} tickers with data)",
            flush=True,
        )
        if progress_callback:
            progress_callback(event)
    return result


def _coverage_ok(total: int, available: int, min_coverage: float) -> bool:
    """True when the yfinance batch result is broad enough to trust downstream."""
    if total <= 0:
        return False
    return (available / total) >= min_coverage


def compute_indicators(df: pd.DataFrame) -> dict | None:
    """Compute indicators needed for hard filters from OHLCV DataFrame."""
    if df is None or len(df) < 50:
        return None

    close = df["Close"].values.flatten() if hasattr(df["Close"], "values") else df["Close"].to_numpy()
    volume = df["Volume"].values.flatten() if hasattr(df["Volume"], "values") else df["Volume"].to_numpy()
    high = df["High"].values.flatten() if hasattr(df["High"], "values") else df["High"].to_numpy()
    low = df["Low"].values.flatten() if hasattr(df["Low"], "values") else df["Low"].to_numpy()

    if len(close) < 50:
        return None

    last_price = float(close[-1])
    if last_price <= 0 or np.isnan(last_price):
        return None

    # Moving averages
    ma200 = float(np.mean(close[-200:])) if len(close) >= 200 else None
    ma50 = float(np.mean(close[-50:]))

    # Returns
    ret_5d = (close[-1] / close[-6] - 1) * 100 if len(close) >= 6 else 0
    ret_20d = (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0

    # Average daily dollar volume (20d)
    avg_vol_20 = float(np.mean(volume[-20:]))
    avg_dollar_vol = avg_vol_20 * last_price

    # Chandelier Exit inputs from underlying OHLCV.
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    atr14 = float(np.mean(tr[-14:])) if len(tr) >= 14 else None
    resistance_20d = float(np.max(high[-21:-1])) if len(high) >= 21 else None
    support_20d = float(np.min(low[-21:-1])) if len(low) >= 21 else None
    highest_high_22d = float(np.max(high[-22:])) if len(high) >= 22 else None
    lowest_low_22d = float(np.min(low[-22:])) if len(low) >= 22 else None

    # Gap-down check: any day in last 5 where close < prev_low by >8%
    gap_down = False
    for i in range(-5, 0):
        if abs(i) < len(close) and abs(i + 1) <= len(low):
            idx = len(close) + i
            idx_prev = idx - 1
            if idx_prev >= 0:
                prev_low_val = float(low[idx_prev])
                if prev_low_val > 0:
                    drop = (float(close[idx]) - prev_low_val) / prev_low_val
                    if drop < -0.08:
                        gap_down = True
                        break

    # MACD (12, 26, 9) daily
    def ema(data, span):
        s = pd.Series(data)
        return s.ewm(span=span, adjust=False).mean().values

    if len(close) >= 35:
        ema12 = ema(close, 12)
        ema26 = ema(close, 26)
        macd_line = ema12 - ema26
        signal_line = ema(macd_line, 9)
        macd_current = float(macd_line[-1])

        # Check for zero-line cross in last 10 days
        macd_zero_cross_10d = False
        lookback = min(10, len(macd_line) - 1)
        for j in range(1, lookback + 1):
            if macd_line[-j] >= 0 and macd_line[-j - 1] < 0:
                macd_zero_cross_10d = True
                break

        # Check for MACD golden cross in last 10 days
        macd_golden_cross_10d = False
        for j in range(1, lookback + 1):
            if macd_line[-j] > signal_line[-j] and macd_line[-j - 1] <= signal_line[-j - 1]:
                macd_golden_cross_10d = True
                break
    else:
        macd_current = 0
        macd_zero_cross_10d = False
        macd_golden_cross_10d = False

    # RSI (14) for divergence check (simplified)
    if len(close) >= 60:
        delta = np.diff(close[-61:])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).ewm(span=14, adjust=False).mean().values
        avg_loss = pd.Series(loss).ewm(span=14, adjust=False).mean().values
        rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
        rsi = 100 - 100 / (1 + rs)
        # Simplified bullish divergence: price made lower low in last 60d but RSI made higher low
        price_lows = []
        rsi_lows = []
        for k in range(10, len(close[-60:]) - 1):
            c = close[-60 + k]
            if k > 0 and k < len(close[-60:]) - 1:
                if close[-60 + k] < close[-60 + k - 1] and close[-60 + k] < close[-60 + k + 1]:
                    price_lows.append((k, c))
                    if k < len(rsi):
                        rsi_lows.append((k, rsi[k]))
        rsi_bullish_divergence = False
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            if price_lows[-1][1] < price_lows[-2][1] and rsi_lows[-1][1] > rsi_lows[-2][1]:
                rsi_bullish_divergence = True
    else:
        rsi_bullish_divergence = False

    # W-bottom detection (simplified): two troughs within 20% of each other in last 60 days
    w_bottom = False
    if len(close) >= 60:
        lows_60d = close[-60:]
        mid = len(lows_60d) // 2
        first_half_min = float(np.min(lows_60d[:mid]))
        second_half_min = float(np.min(lows_60d[mid:]))
        if first_half_min > 0:
            trough_diff = abs(first_half_min - second_half_min) / first_half_min
            if trough_diff < 0.15:
                peak_between = float(np.max(lows_60d[mid - 5 : mid + 5]))
                if peak_between > max(first_half_min, second_half_min) * 1.03:
                    w_bottom = True

    # Reversal pattern (W-bottom or inverse H&S with RSI divergence)
    has_reversal_pattern = (w_bottom and rsi_bullish_divergence)

    return {
        "last_price": last_price,
        "ma200": ma200,
        "ma50": ma50,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "avg_dollar_vol_20d": avg_dollar_vol,
        "atr14": atr14,
        "resistance_20d": resistance_20d,
        "support_20d": support_20d,
        "highest_high_22d": highest_high_22d,
        "lowest_low_22d": lowest_low_22d,
        "gap_down_8pct_5d": gap_down,
        "macd_current": macd_current,
        "macd_zero_cross_10d": macd_zero_cross_10d,
        "macd_golden_cross_10d": macd_golden_cross_10d,
        "rsi_bullish_divergence": rsi_bullish_divergence,
        "has_reversal_pattern": has_reversal_pattern,
    }


# ---------------------------------------------------------------------------
# Hard Filters (7 rules)
# ---------------------------------------------------------------------------

def apply_hard_filters(ticker: str, ind: dict, info: dict,
                       *, rules: dict | None = None) -> tuple[bool, str]:
    """
    Apply 7 hard filters. Returns (passed, reject_reason).
    """
    rules = dict(DEFAULT_FILTER_RULES if rules is None else rules)
    market_cap = info.get("marketCap") or 0

    # Filter 1: Already extended — up >30% in 5d or >60% in 20d
    if ind["ret_5d"] > rules["max_ret_5d"]:
        return False, f"Already extended: +{ind['ret_5d']:.1f}% in 5 days"
    if ind["ret_20d"] > rules["max_ret_20d"]:
        return False, f"Already extended: +{ind['ret_20d']:.1f}% in 20 days"

    # Filter 2: Liquidity floor — 20d avg dollar volume < $5M
    if ind["avg_dollar_vol_20d"] < rules["min_avg_dollar_vol"]:
        return False, f"Low liquidity: ${ind['avg_dollar_vol_20d']/1e6:.1f}M avg daily"

    # Filter 3: Penny territory — market cap < $300M or price < $5
    if market_cap < rules["min_market_cap"]:
        return False, f"Market cap too small: ${market_cap/1e6:.0f}M"
    if ind["last_price"] < rules["min_price"]:
        return False, f"Price too low: ${ind['last_price']:.2f}"

    # Filter 4: Earnings within 2 trading days
    # (checked via yfinance earnings date if available)
    earnings_date = info.get("earningsTimestamp")
    if earnings_date:
        try:
            if isinstance(earnings_date, (int, float)):
                ed = datetime.fromtimestamp(earnings_date)
            else:
                ed = pd.Timestamp(earnings_date).to_pydatetime()
            days_to_earnings = (ed - datetime.now()).days
            if 0 <= days_to_earnings <= rules["earnings_exclude_days"]:
                return False, f"Earnings in {days_to_earnings} days"
        except Exception:
            pass

    # Filter 5: Below 200DMA (unless reversal pattern)
    if ind["ma200"] is not None:
        if ind["last_price"] < ind["ma200"] and not ind["has_reversal_pattern"]:
            return False, "Below 200DMA without reversal pattern"

    # Filter 6: Gap-down >8% in last 5 days
    if ind["gap_down_8pct_5d"]:
        return False, "Recent gap-down >8% in last 5 days"

    # Filter 7: MACD below zero AND no zero-line cross in 10d AND no RSI divergence
    if (ind["macd_current"] < 0
            and not ind["macd_zero_cross_10d"]
            and not ind["rsi_bullish_divergence"]):
        return False, "MACD below zero with no cross or divergence"

    return True, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage 1: Hard Filter")
    parser.add_argument("--markets", default="US")
    parser.add_argument("--universe", default="sp1500",
                        choices=["sp1500", "russell3000", "nasdaq_only", "custom"])
    parser.add_argument("--output", default="filtered_universe.json")
    parser.add_argument("--batch-size", type=int,
                        default=int(os.environ.get("YF_BATCH_SIZE", "25")),
                        help="tickers per yfinance batch; lower is slower but more stable")
    parser.add_argument("--yf-threads", action="store_true",
                        help="enable yfinance threaded downloads (faster, less stable locally)")
    parser.add_argument("--min-data-coverage", type=float,
                        default=float(os.environ.get("MIN_DATA_COVERAGE", "0.70")),
                        help="abort before writing output if available/total is below this")
    parser.add_argument("--min-avg-dollar-vol", type=float,
                        default=float(os.environ.get(
                            "MIN_AVG_DOLLAR_VOL",
                            str(DEFAULT_FILTER_RULES["min_avg_dollar_vol"]),
                        )),
                        help="reject candidates below this 20d average dollar volume")
    parser.add_argument("--min-market-cap", type=float,
                        default=float(os.environ.get(
                            "MIN_MARKET_CAP",
                            str(DEFAULT_FILTER_RULES["min_market_cap"]),
                        )),
                        help="reject candidates below this market cap")
    parser.add_argument("--min-price", type=float,
                        default=float(os.environ.get(
                            "MIN_PRICE",
                            str(DEFAULT_FILTER_RULES["min_price"]),
                        )),
                        help="reject candidates below this price")
    parser.add_argument("--max-ret-5d", type=float,
                        default=float(os.environ.get(
                            "MAX_RET_5D",
                            str(DEFAULT_FILTER_RULES["max_ret_5d"]),
                        )),
                        help="reject candidates above this 5d return percent")
    parser.add_argument("--max-ret-20d", type=float,
                        default=float(os.environ.get(
                            "MAX_RET_20D",
                            str(DEFAULT_FILTER_RULES["max_ret_20d"]),
                        )),
                        help="reject candidates above this 20d return percent")
    parser.add_argument("--earnings-exclude-days", type=int,
                        default=int(os.environ.get(
                            "EARNINGS_EXCLUDE_DAYS",
                            str(DEFAULT_FILTER_RULES["earnings_exclude_days"]),
                        )),
                        help="reject candidates with earnings within this many days")
    parser.add_argument("--status-file",
                        help="write latest run status JSON for local UI progress")
    args = parser.parse_args()
    filter_rules = {
        "max_ret_5d": args.max_ret_5d,
        "max_ret_20d": args.max_ret_20d,
        "min_avg_dollar_vol": args.min_avg_dollar_vol,
        "min_market_cap": args.min_market_cap,
        "min_price": args.min_price,
        "earnings_exclude_days": args.earnings_exclude_days,
    }

    tickers = load_universe(args.universe, args.markets)
    if not tickers:
        print("[hard_filter] No tickers loaded, exiting.", file=sys.stderr)
        sys.exit(1)

    status = RunStatus(args.status_file) if args.status_file else None
    if status:
        status.start(
            metrics={
                "universe": args.universe,
                "total_tickers": len(tickers),
                "batch_size": args.batch_size,
                "min_data_coverage": args.min_data_coverage,
                "filter_rules": filter_rules,
            },
            outputs={
                "filtered_universe": {"path": args.output, "exists": Path(args.output).exists()},
                "ranked_candidates": {
                    "path": "ranked_candidates.json",
                    "exists": Path("ranked_candidates.json").exists(),
                    "stale": True,
                },
                "scored_candidates": {
                    "path": "scored_candidates.json",
                    "exists": Path("scored_candidates.json").exists(),
                    "stale": True,
                },
            },
        )

    print(f"[hard_filter] Fetching data for {len(tickers)} tickers ...")
    def _batch_progress(event):
        if not status:
            return
        total_batches = event["total_batches"]
        pct = event["completed_batches"] / total_batches * 100
        downloaded = event["downloaded_tickers"]
        status.update_stage(
            "hard_filter.fetch_ohlcv",
            "抓取 yfinance OHLCV",
            progress_pct=pct,
            message=f"Downloading batch {event['completed_batches']}/{total_batches}",
            metrics={
                "total_batches": total_batches,
                "completed_batches": event["completed_batches"],
                "downloaded_tickers": downloaded,
                "current_coverage": downloaded / len(tickers),
            },
        )

    ohlcv = fetch_batch_data(
        tickers, period="1y", batch_size=args.batch_size, threads=args.yf_threads,
        progress_callback=_batch_progress)
    print(f"[hard_filter] Got data for {len(ohlcv)} tickers")
    if status:
        status.update_stage(
            "hard_filter.fetch_ohlcv",
            "抓取 yfinance OHLCV",
            status="succeeded",
            progress_pct=100,
            message=f"Got data for {len(ohlcv)} tickers",
            metrics={
                "data_available": len(ohlcv),
                "current_coverage": len(ohlcv) / len(tickers),
            },
        )
    if not _coverage_ok(len(tickers), len(ohlcv), args.min_data_coverage):
        coverage = len(ohlcv) / len(tickers)
        if status:
            status.fail(
                "hard_filter.fetch_ohlcv",
                "抓取 yfinance OHLCV",
                f"yfinance coverage {len(ohlcv)}/{len(tickers)} below floor "
                f"{args.min_data_coverage:.0%}; not writing output",
                metrics={
                    "data_available": len(ohlcv),
                    "current_coverage": coverage,
                },
            )
        print(
            f"[hard_filter] ABORT: yfinance coverage {len(ohlcv)}/{len(tickers)} "
            f"({coverage:.1%}) below floor {args.min_data_coverage:.0%}; "
            "not writing output. Retry later, reduce batch size, or check Yahoo/DNS/cache.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Fetch basic info (market cap, earnings date) in batches
    ticker_infos: dict[str, dict] = {}
    info_total = max(1, len(ohlcv))
    for idx, t in enumerate(ohlcv, start=1):
        try:
            tk = yf.Ticker(t)
            fast = tk.fast_info
            info = {
                "marketCap": getattr(fast, "market_cap", None),
            }
            # Try to get earnings date
            try:
                cal = tk.calendar
                if cal is not None and isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed and len(ed) > 0:
                        info["earningsTimestamp"] = ed[0]
            except Exception:
                pass
            ticker_infos[t] = info
        except Exception:
            ticker_infos[t] = {}
        if status and (idx == info_total or idx % 10 == 0):
            status.update_stage(
                "hard_filter.info",
                "補 market cap / earnings",
                progress_pct=idx / info_total * 100,
                message=f"Fetched info {idx}/{info_total}",
                metrics={"info_tickers": idx},
            )

    # Apply hard filters
    passed = []
    rejected = []
    filter_total = max(1, len(ohlcv))
    for idx, (ticker, df) in enumerate(ohlcv.items(), start=1):
        ind = compute_indicators(df)
        if ind is None:
            rejected.append({"ticker": ticker, "verdict": "REJECT",
                             "reason": "Insufficient data"})
            continue

        info = ticker_infos.get(ticker, {})
        ok, reason = apply_hard_filters(ticker, ind, info, rules=filter_rules)
        if ok:
            passed.append({
                "ticker": ticker,
                "last_price": round(ind["last_price"], 2),
                "ma50": round(ind["ma50"], 2) if ind["ma50"] else None,
                "ma200": round(ind["ma200"], 2) if ind["ma200"] else None,
                "ret_5d": round(ind["ret_5d"], 2),
                "ret_20d": round(ind["ret_20d"], 2),
                "avg_dollar_vol_20d": round(ind["avg_dollar_vol_20d"]),
                "atr14": round(ind["atr14"], 2) if ind["atr14"] else None,
                "resistance_20d": round(ind["resistance_20d"], 2) if ind["resistance_20d"] else None,
                "support_20d": round(ind["support_20d"], 2) if ind["support_20d"] else None,
                "highest_high_22d": round(ind["highest_high_22d"], 2) if ind["highest_high_22d"] else None,
                "lowest_low_22d": round(ind["lowest_low_22d"], 2) if ind["lowest_low_22d"] else None,
                "market_cap": info.get("marketCap"),
                "macd_current": round(ind["macd_current"], 4),
                "macd_zero_cross_10d": ind["macd_zero_cross_10d"],
                "macd_golden_cross_10d": ind["macd_golden_cross_10d"],
                "rsi_bullish_divergence": ind["rsi_bullish_divergence"],
                "has_reversal_pattern": ind["has_reversal_pattern"],
            })
        else:
            rejected.append({"ticker": ticker, "verdict": "REJECT", "reason": reason})
        if status and (idx == filter_total or idx % 25 == 0):
            status.update_stage(
                "hard_filter.apply_filters",
                "套用硬篩選",
                progress_pct=idx / filter_total * 100,
                message=f"Applied filters {idx}/{filter_total}",
                metrics={
                    "filter_tickers": idx,
                    "passed_hard_filters": len(passed),
                    "rejected": len(rejected),
                },
            )

    output = {
        "scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "universe": args.universe,
        "markets": args.markets,
        "total_universe": len(tickers),
        "data_available": len(ohlcv),
        "passed_hard_filters": len(passed),
        "rejected": len(rejected),
        "filter_rules": filter_rules,
        "tickers": passed,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    if status:
        status.update_stage(
            "hard_filter.apply_filters",
            "套用硬篩選",
            status="succeeded",
            progress_pct=100,
            message=f"{len(passed)} passed / {len(rejected)} rejected",
            metrics={
                "data_available": len(ohlcv),
                "passed_hard_filters": len(passed),
                "rejected": len(rejected),
            },
            outputs={
                "filtered_universe": {"path": args.output, "exists": True},
                "ranked_candidates": {
                    "path": "ranked_candidates.json",
                    "exists": Path("ranked_candidates.json").exists(),
                    "stale": True,
                },
                "scored_candidates": {
                    "path": "scored_candidates.json",
                    "exists": Path("scored_candidates.json").exists(),
                    "stale": True,
                },
            },
        )

    print(f"[hard_filter] Done: {len(passed)} passed / {len(rejected)} rejected → {args.output}")


if __name__ == "__main__":
    main()
