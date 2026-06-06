#!/usr/bin/env python3
"""Risk Guard V4 — backtest / calibration of the rule-based risk score.

Question this answers (plan §V4): do higher risk scores actually PRECEDE bigger
drawdowns, and which config (price-only vs price+VIX) separates risk best — so we can
spot over-sensitive rules instead of trusting the score blindly.

Method (point-in-time, no look-ahead):
  - Pull ~2y daily OHLCV per ticker + SPY + ^VIX (yfinance).
  - At each historical date t, recompute the PRICE (0-25) and MARKET (0-20) subscores
    from data available UP TO t only, mirroring scripts/risk_guard.py's documented
    rules. Then measure the forward max drawdown over the next 5 / 10 / 20 trading days
    (min future low vs close[t]).
  - Bucket observations by score band and report mean forward MDD per band, plus a
    false-positive rate (high score, no drawdown) and missed-drawdown rate (low score,
    big drawdown) for the price+VIX config.

Scope: ONLY price + market are backtested. Options (no historical IV/OI) and sector RRG
(live-only) are NOT backtested — and the intraday VWAP leg of the price rule is dropped
(daily bars have no VWAP). These limitations are recorded in the output.

NEVER trades, NEVER advises — calibration only.

CLI:
  python scripts/risk_guard_backtest.py
  python scripts/risk_guard_backtest.py --tickers NVDA,AMD,TSLA --period 3y --output reports/risk_guard/backtest_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO / "reports" / "risk_guard" / "backtest_summary.json"

DEFAULT_UNIVERSE = ["NVDA", "AMD", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AVGO", "MU"]
HORIZONS = (5, 10, 20)
# score bands on the SAME 0-? component scale as risk_guard (market 0-20 + price 0-25)
BANDS = [(0, 9), (10, 19), (20, 29), (30, 99)]


def _market_score_row(spy_close, spy_ma50, spy_ma200, vix) -> int:
    s = 0
    if spy_ma50 == spy_ma50 and spy_close < spy_ma50:
        s += 7
    if spy_ma200 == spy_ma200 and spy_close < spy_ma200:
        s += 10
    if vix == vix:  # not NaN
        if vix >= 30:
            s += 12
        elif vix >= 25:
            s += 8
        elif vix >= 20:
            s += 5
    return min(s, 20)


def _price_features(df):
    """Vectorised PIT price features (mirrors risk_guard.price_component's df rules,
    minus the intraday-VWAP leg which daily bars can't support)."""
    import numpy as np
    c, o, low, high = df["Close"], df["Open"], df["Low"], df["High"]
    feat = df.copy()
    feat["ma20"] = c.rolling(20).mean()
    feat["ma50"] = c.rolling(50).mean()
    feat["ma200"] = c.rolling(200).mean()
    feat["low20_prior"] = low.shift(1).rolling(20).min()      # lowest low of prior 20d
    feat["ret5"] = c.pct_change(5) * 100
    feat["ret20"] = c.pct_change(20) * 100
    gap_down = (o < c.shift(1) * 0.92)                        # >8% gap down vs prev close
    feat["gap5"] = gap_down.rolling(5).max().astype(float)    # any gap-down in last 5d
    feat["_c"], feat["_low"] = c, low
    return feat


def _price_score_row(r) -> int:
    s = 0
    close = r["_c"]
    if r["ma20"] == r["ma20"] and close < r["ma20"]:
        s += 5
    if r["ma50"] == r["ma50"] and close < r["ma50"]:
        s += 8
    if r["ma200"] == r["ma200"] and close < r["ma200"]:
        s += 12
    if r["low20_prior"] == r["low20_prior"] and close < r["low20_prior"]:
        s += 8
    if r["ret5"] == r["ret5"] and r["ret5"] <= -8:
        s += 8
    if r["ret20"] == r["ret20"] and r["ret20"] <= -15:
        s += 8
    if r["gap5"] == 1.0:
        s += 10
    return min(s, 25)


def _band(score: int) -> str:
    for lo, hi in BANDS:
        if lo <= score <= hi:
            return f"{lo}-{hi}" if hi < 99 else f"{lo}+"
    return "?"


def backtest(tickers: list[str], period: str = "2y") -> dict:
    import numpy as np
    import yfinance as yf

    spy = yf.Ticker("SPY").history(period=period)
    vix = yf.Ticker("^VIX").history(period=period)
    if spy.empty:
        return {"status": "no_data", "reason": "SPY history unavailable"}
    spy_close = spy["Close"]
    spy_ma50 = spy_close.rolling(50).mean()
    spy_ma200 = spy_close.rolling(200).mean()
    vix_close = vix["Close"] if not vix.empty else None

    obs = []   # each: {ticker, date, price, market, mdd_5/10/20}
    used = []
    for t in tickers:
        try:
            df = yf.Ticker(t).history(period=period)
        except Exception:  # noqa: BLE001
            continue
        if df is None or len(df) < 220:
            continue
        used.append(t)
        feat = _price_features(df)
        # align market series to this ticker's dates
        sma50 = spy_ma50.reindex(df.index, method="ffill")
        sma200 = spy_ma200.reindex(df.index, method="ffill")
        sclose = spy_close.reindex(df.index, method="ffill")
        vx = (vix_close.reindex(df.index, method="ffill") if vix_close is not None else None)
        lows = df["Low"].values
        closes = df["Close"].values
        n = len(df)
        for i in range(200, n - max(HORIZONS)):
            r = feat.iloc[i]
            p = _price_score_row(r)
            m = _market_score_row(float(sclose.iloc[i]), float(sma50.iloc[i]),
                                  float(sma200.iloc[i]),
                                  float(vx.iloc[i]) if vx is not None else float("nan"))
            c0 = closes[i]
            if not c0 or c0 != c0:
                continue
            row = {"ticker": t, "price": p, "market": m}
            for h in HORIZONS:
                fwd_low = lows[i + 1:i + 1 + h].min()
                row[f"mdd{h}"] = round((fwd_low / c0 - 1) * 100, 2)
            obs.append(row)

    if not obs:
        return {"status": "no_data", "reason": "no observations built"}

    def _summarise(score_key):
        bands = {}
        for o in obs:
            b = _band(o[score_key])
            d = bands.setdefault(b, {"n": 0, **{f"mdd{h}": [] for h in HORIZONS}})
            d["n"] += 1
            for h in HORIZONS:
                d[f"mdd{h}"].append(o[f"mdd{h}"])
        out = []
        for lo, hi in BANDS:
            b = f"{lo}-{hi}" if hi < 99 else f"{lo}+"
            d = bands.get(b)
            if not d:
                continue
            row = {"band": b, "n": d["n"]}
            for h in HORIZONS:
                vals = d[f"mdd{h}"]
                row[f"mean_mdd{h}"] = round(sum(vals) / len(vals), 2) if vals else None
            out.append(row)
        return out

    # combined (price+market) score per obs for the price+VIX config
    for o in obs:
        o["combined"] = o["price"] + o["market"]
    price_only = _summarise("price")
    price_vix = _summarise("combined")

    # false-positive (high score, no real drawdown) + missed-drawdown (low score, big drop)
    HIGH, LOW = 25, 10
    high_obs = [o for o in obs if o["combined"] >= HIGH]
    low_obs = [o for o in obs if o["combined"] < LOW]
    fp = (sum(1 for o in high_obs if o["mdd20"] > -5) / len(high_obs)) if high_obs else None
    missed = (sum(1 for o in low_obs if o["mdd20"] <= -10) / len(low_obs)) if low_obs else None

    def _spread(summary):
        if len(summary) < 2:
            return None
        return round((summary[0]["mean_mdd20"] or 0) - (summary[-1]["mean_mdd20"] or 0), 2)

    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "universe": used,
        "n_observations": len(obs),
        "horizons": list(HORIZONS),
        "configs": {
            "price_only": {"bands": price_only,
                           "low_minus_high_band_mdd20": _spread(price_only)},
            "price_vix": {"bands": price_vix,
                          "low_minus_high_band_mdd20": _spread(price_vix),
                          "false_positive_rate_high>=%d" % HIGH: (round(fp, 3) if fp is not None else None),
                          "missed_drawdown_rate_low<%d" % LOW: (round(missed, 3) if missed is not None else None)},
        },
        "notes": [
            "Point-in-time: each score uses only data up to date t (no look-ahead).",
            "Options (no historical IV/OI) and sector RRG (live-only) are NOT backtested.",
            "The intraday-VWAP leg of the price rule is dropped (daily bars have no VWAP).",
            "Score scale = market(0-20)+price(0-25); bands are on that scale, not the live 0-100.",
            "false_positive = high score but forward-20d MDD shallower than -5%; "
            "missed_drawdown = low score but forward-20d MDD <= -10%.",
        ],
    }


def _markdown(res: dict) -> str:
    if res.get("status") != "ok":
        return f"# Risk Guard Backtest\n\nstatus: {res.get('status')} — {res.get('reason','')}\n"
    L = [f"# Risk Guard Backtest — {res['generated_at'][:10]}",
         f"\nPeriod `{res['period']}` · universe {', '.join(res['universe'])} · "
         f"{res['n_observations']:,} observations\n"]
    for cfg, label in (("price_only", "Price only (0-25)"), ("price_vix", "Price + VIX/market (0-45)")):
        c = res["configs"][cfg]
        L.append(f"\n## {label}\n")
        L.append("| score band | n | mean MDD 5d | 10d | 20d |")
        L.append("|---|---:|---:|---:|---:|")
        for b in c["bands"]:
            L.append(f"| {b['band']} | {b['n']:,} | {b['mean_mdd5']}% | {b['mean_mdd10']}% | {b['mean_mdd20']}% |")
        L.append(f"\nlow−high band spread (20d MDD): **{c.get('low_minus_high_band_mdd20')}%** "
                 "(more POSITIVE = the highest-score band saw deeper forward drawdowns than "
                 "the lowest — i.e. the score is actually discriminating)")
        for k, v in c.items():
            if k.startswith("false_positive") or k.startswith("missed_drawdown"):
                L.append(f"\n- {k}: **{v}**")
    L.append("\n## Notes\n")
    L += [f"- {n}" for n in res["notes"]]
    L.append("\n_僅供訊號校準,非投資建議。_")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Risk Guard backtest / calibration")
    ap.add_argument("--tickers", help="comma/space separated (default: a liquid mega-cap set)")
    ap.add_argument("--period", default="2y")
    ap.add_argument("--output", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    if args.tickers:
        import re
        tickers = [t.strip().upper().lstrip("$") for t in re.split(r"[\s,;]+", args.tickers) if t.strip()]
    else:
        tickers = DEFAULT_UNIVERSE
    res = backtest(tickers, period=args.period)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    md = out.with_suffix(".md") if out.suffix == ".json" else out.parent / "backtest_summary.md"
    md.write_text(_markdown(res), encoding="utf-8")
    print(f"wrote {out}\nwrote {md}\nstatus={res.get('status')} obs={res.get('n_observations')}")
    if res.get("status") == "ok":
        print(json.dumps(res["configs"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
