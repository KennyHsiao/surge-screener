#!/usr/bin/env python3
"""Surge Retrospective — Stage B: reconstruct pre-surge features.

For every surge event from retro_surge_label, rebuild the SAME price/volume
technical setup the live screener scores — but as of T0 (the day before lift-off).
That means feeding the indicator engine a history slice ending at T0, exactly the
data the screener would have had in hand at that moment.

We reuse the live engine's indicator math (momentum_options._technical /
_realized_vol_percentile) so reconstructed features can't drift from production,
and add the few sub-factors that engine lacks (MA150, MACD, 52-week distance,
relative strength + market regime) with small numpy helpers. Each event becomes a
row of boolean factor flags, every flag tagged with the rubric sub-factor it maps
to (Dim1 Technical / Dim5 Sector-Market) so the lift stage and the report can
speak in the screener's own dimensions.

Only Dim1/Dim5 are reconstructable from free history. Dim2/3/4/6 (catalyst,
sentiment, institutional, options flow) are NOT retroactively free — they are the
job of Phase 1.5 (EDGAR backfill) and Phase 2 (forward snapshots).

History uses auto_adjust=False to match momentum_options._daily; magnitude in the
label stage used adjusted Close. Both are intentional (see plan).

CLI:
    python scripts/retro_reconstruct.py
    python scripts/retro_reconstruct.py --events reports/retrospective/surge_events.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

import momentum_options as mo  # noqa: E402 — reuse the live indicator engine

# Each factor flag → (dimension, rubric sub-factor, human description). The lift
# stage and report group by these so recommendations land on real rubric weights.
FACTOR_DEFS = {
    "price_above_ma200":     ("Dim1", "1a Trend", "收盤 > 200 日均線"),
    "ma_stack_50_150_200":   ("Dim1", "1a Trend", "50 > 150 > 200 日均線多頭排列"),
    "price_above_ma50":      ("Dim1", "1a Trend", "收盤 > 50 日均線"),
    "within_25pct_of_high":  ("Dim1", "1a Trend", "距 52 週高點 ≤ 25%"),
    "above_30pct_of_low":    ("Dim1", "1a Trend", "距 52 週低點 ≥ 30%"),
    "rvol_ge_2":             ("Dim1", "1b Volume", "相對量能 ≥ 2×"),
    "breakout_above_resist": ("Dim1", "1b Volume", "帶量突破前 20 日壓力"),
    "bb_squeeze":            ("Dim1", "1c Pattern", "布林帶擠壓(整理基底)"),
    "rsi_40_65":             ("Dim1", "1c Pattern", "RSI 在 40-65(健康動能,非超買)"),
    "macd_positive":         ("Dim1", "1d MACD", "MACD 線 ≥ 0"),
    "macd_golden_cross_10d": ("Dim1", "1d MACD", "近 10 日 MACD 黃金交叉"),
    "price_above_vwap":      ("Dim1", "1b Volume", "收盤 > 20 日 VWAP"),
    "low_rv_base":           ("Dim1", "Vol base", "已實現波動百分位 ≤ 30(低波基底)"),
    "rel_strength_vs_spy":   ("Dim5", "5a Sector RS", "20 日報酬 > SPY(相對強度,板塊代理)"),
    "market_regime_ok":      ("Dim5", "5b Regime", "SPY > 50 日線 且 VIX < 25"),
}


def _factor_horizons() -> dict:
    """factor key -> horizon (short/mid/long) from config/factor_meta.json.

    Decoupled metadata so the holding-window tag flows into factor_defs — and
    thus into every lift JSON, the UI, and the knowledge vault — without touching
    the factor math. Missing file / key degrades to None (UI just hides it)."""
    try:
        meta = json.loads((REPO / "config" / "factor_meta.json").read_text(encoding="utf-8"))
        return {k: v.get("horizon") for k, v in (meta.get("factors") or {}).items()}
    except Exception:
        return {}


FACTOR_HORIZONS = _factor_horizons()


def _ema(a: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(a, dtype=float)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = alpha * a[i] + (1 - alpha) * out[i - 1]
    return out


def _macd_flags(close: np.ndarray) -> tuple:
    """(macd_positive, golden_cross_within_10d). None if too little data."""
    if len(close) < 35:
        return None, None
    line = _ema(close, 12) - _ema(close, 26)
    signal = _ema(line, 9)
    positive = bool(line[-1] >= 0)
    cross = False
    for i in range(max(1, len(line) - 10), len(line)):
        if line[i - 1] <= signal[i - 1] and line[i] > signal[i]:
            cross = True
            break
    return positive, cross


def _ret_20d(close: np.ndarray) -> float | None:
    return float(close[-1] / close[-21] - 1.0) if len(close) >= 21 else None


def _observe_date(df: pd.DataFrame, trough: pd.Timestamp,
                  confirm_pct: float, max_offset: int) -> pd.Timestamp:
    """The realistic screener-entry day: first session ≥ confirm_pct above the
    trough, within max_offset sessions. We measure features HERE, not at the
    literal bottom — the screener never buys the exact low; it acts early in a
    move once momentum confirms. Falls back to trough+3 sessions if the move
    never reaches confirm_pct that fast (rare)."""
    fwd = df[df.index >= trough]
    if len(fwd) < 2:
        return trough
    base = float(fwd["Close"].iloc[0])
    window = fwd.iloc[1:max_offset + 1]
    hit = window[window["Close"] >= base * (1.0 + confirm_pct)]
    if not hit.empty:
        return hit.index[0]
    return fwd.index[min(3, len(fwd) - 1)]


def confirmation_days(df: pd.DataFrame, confirm_pct: float = 0.07,
                      max_offset: int = 12, min_gap: int = 20) -> list:
    """Every "confirmation trigger" day across a ticker's history: a session that
    is ≥ confirm_pct above a low within the prior max_offset sessions — the SAME
    +X%-off-the-trough trigger _observe_date fires for surge positives.

    The control group is built from these (the ones that did NOT go on to surge),
    so the lift compares like-with-like: "given a confirmation move, what separates
    future surgers from fizzlers?" — not "an early winning move vs a random day".
    De-overlapped by min_gap so one bounce yields one trigger. Returns timestamps.
    """
    import numpy as np
    close = df["Close"].to_numpy(dtype=float)
    dates = df.index
    n = len(close)
    out = []
    i = 0
    while i < n - 1:
        hi = min(i + max_offset, n - 1)
        seg = close[i + 1:hi + 1]
        if seg.size and close[i] > 0:
            rel = np.argmax(seg >= close[i] * (1.0 + confirm_pct))
            # argmax returns 0 both for "match at 0" and "no match"; disambiguate.
            if seg[rel] >= close[i] * (1.0 + confirm_pct):
                j = i + 1 + int(rel)
                out.append(dates[j])
                i = j + min_gap
                continue
        i += 1
    return out


def reconstruct_flags(df: pd.DataFrame, spy_close: pd.Series,
                      vix_close: pd.Series, t0: pd.Timestamp) -> dict | None:
    """Boolean factor flags as of T0 from an auto_adjust=False history slice."""
    sl = df[df.index <= t0]
    if len(sl) < 60:
        return None
    tech = mo._technical(sl)
    rv, rv_pct = mo._realized_vol_percentile(sl)
    close = sl["Close"].to_numpy(dtype=float)
    px = float(close[-1])

    ma50, ma200 = tech.get("ma50"), tech.get("ma200")
    ma150 = float(np.mean(close[-150:])) if len(close) >= 150 else None
    hi52 = float(np.max(close[-252:])) if len(close) >= 60 else None
    lo52 = float(np.min(close[-252:])) if len(close) >= 60 else None
    macd_pos, macd_cross = _macd_flags(close)
    rsi = tech.get("rsi14")

    # SPY / VIX as of T0 for Dim5.
    spy_sl = spy_close[spy_close.index <= t0]
    vix_sl = vix_close[vix_close.index <= t0]
    rel_strength = market_regime = None
    if len(spy_sl) >= 51:
        spy = spy_sl.to_numpy(dtype=float)
        spy_ret20 = float(spy[-1] / spy[-21] - 1.0)
        spy_ma50 = float(np.mean(spy[-50:]))
        stock_ret20 = _ret_20d(close)
        if stock_ret20 is not None:
            rel_strength = bool(stock_ret20 > spy_ret20)
        spy_above_50 = spy[-1] > spy_ma50
        vix_ok = bool(vix_sl.iloc[-1] < 25) if len(vix_sl) else None
        if vix_ok is not None:
            market_regime = bool(spy_above_50 and vix_ok)

    def _b(v):
        return bool(v) if v is not None else None

    return {
        "price_above_ma200":     _b(ma200 and px > ma200),
        "ma_stack_50_150_200":   _b(ma50 and ma150 and ma200 and ma50 > ma150 > ma200),
        "price_above_ma50":      _b(ma50 and px > ma50),
        "within_25pct_of_high":  _b(hi52 and px >= 0.75 * hi52),
        "above_30pct_of_low":    _b(lo52 and px >= 1.30 * lo52),
        "rvol_ge_2":             _b(tech.get("rvol") is not None and tech["rvol"] >= 2.0),
        "breakout_above_resist": _b(tech.get("breakout_above_resistance")),
        "bb_squeeze":            _b(tech.get("bb_squeeze")),
        "rsi_40_65":             _b(rsi is not None and 40 <= rsi <= 65),
        "macd_positive":         macd_pos,
        "macd_golden_cross_10d": macd_cross,
        "price_above_vwap":      _b(tech.get("price_above_vwap")),
        "low_rv_base":           _b(rv_pct is not None and rv_pct <= 30),
        "rel_strength_vs_spy":   rel_strength,
        "market_regime_ok":      market_regime,
    }


def _hist_auto_adjust_false(ticker: str, period: str = "4y"):
    """Per-ticker OHLCV matching momentum_options._daily (auto_adjust=False).

    RETRIES transient failures and CACHES the result (TTL 6h) so a network blip can't
    silently drop a ticker AND so re-runs within a day use the SAME data — the control
    pool re-fetches the whole universe per run, and without caching network jitter
    would yield a different control set each time (non-reproducible lift)."""
    import time
    import yfinance as yf

    def _fetch():
        last_exc = None
        for attempt in range(3):
            try:
                df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
                if df is not None and not df.empty:
                    # JSON-serializable for the cache (ISO dates + columns).
                    return df.reset_index().to_json(orient="split", date_format="iso")
            except Exception as e:  # noqa: BLE001 — transient yfinance/network
                last_exc = e
            time.sleep(0.4 * (attempt + 1))
        if last_exc:
            print(f"[reconstruct] fetch failed for {ticker}: {last_exc}", file=sys.stderr)
        return None

    blob = _cached("retro_ohlcv", {"ticker": ticker, "period": period},
                   ttl=6 * 3600, compute=_fetch)
    if not blob:
        return None
    try:
        import io
        df = pd.read_json(io.StringIO(blob), orient="split")  # pandas 3.0: needs file-like
        return df.set_index(df.columns[0]) if len(df.columns) else None
    except Exception as e:
        print(f"[reconstruct] cache decode failed for {ticker}: {e}", file=sys.stderr)
        return None


def _cached(namespace, params, ttl, compute):
    """Best-effort cache.py shim (falls back to plain compute)."""
    try:
        from cache import get_or_compute
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cache", Path(__file__).parent / "cache.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        get_or_compute = mod.get_or_compute
    try:
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — reconstruct features")
    ap.add_argument("--events", default=str(OUT_DIR / "surge_events.json"))
    ap.add_argument("--output", default=str(OUT_DIR / "surge_features.json"))
    ap.add_argument("--period", default="4y",
                    help="yfinance lookback per ticker (must exceed lookback + 1y warmup)")
    ap.add_argument("--confirm-pct", type=float, default=0.07,
                    help="observe features the first day price is this far above the trough")
    ap.add_argument("--max-offset", type=int, default=12,
                    help="cap on sessions after the trough for the confirmation day")
    args = ap.parse_args()

    events_payload = json.loads(Path(args.events).read_text(encoding="utf-8"))
    events = events_payload.get("events", [])
    if not events:
        print("[reconstruct] no events", file=sys.stderr)
        return 1

    # SPY + VIX once for the Dim5 flags.
    import yfinance as yf
    spy_close = yf.Ticker("SPY").history(period=args.period,
                                          auto_adjust=False)["Close"].dropna()
    vix_close = yf.Ticker("^VIX").history(period=args.period)["Close"].dropna()
    # Make indexes tz-naive dates so comparisons with parsed t0 line up.
    spy_close.index = pd.to_datetime(spy_close.index).tz_localize(None).normalize()
    vix_close.index = pd.to_datetime(vix_close.index).tz_localize(None).normalize()

    tickers = sorted({e["ticker"] for e in events})
    hist: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = _hist_auto_adjust_false(t, args.period)
        if df is not None:
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            hist[t] = df
    print(f"[reconstruct] history for {len(hist)}/{len(tickers)} tickers")

    rows: list[dict] = []
    skipped = 0
    for e in events:
        df = hist.get(e["ticker"])
        if df is None:
            skipped += 1
            continue
        trough = pd.Timestamp(e["surge_start"])
        observe = _observe_date(df, trough, args.confirm_pct, args.max_offset)
        flags = reconstruct_flags(df, spy_close, vix_close, observe)
        if flags is None:
            skipped += 1
            continue
        rows.append({
            "ticker": e["ticker"],
            # tolerate the legacy singular `threshold` so an old-schema
            # surge_events.json still reconstructs without a KeyError.
            "thresholds_hit": (e.get("thresholds_hit")
                               or ([e["threshold"]] if e.get("threshold") else [])),
            "surge_start": e["surge_start"],
            "observe_date": observe.strftime("%Y-%m-%d"),
            "magnitude_pct": e["magnitude_pct"],
            "flags": flags,
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # Same-source fingerprint: which surge_events run these features were built from,
        # so retro_factor_lift can verify the WHOLE chain (events → features → controls)
        # is consistent, not just features↔controls.
        "source": {
            "events_generated_at": events_payload.get("generated_at"),
            "universe": events_payload.get("universe"),
            "lookback_days": events_payload.get("lookback_days"),
        },
        # Reconstruction params at the top level (not only buried in the prose string),
        # so the observation point is machine-readable / reproducible.
        "confirm_pct": args.confirm_pct,
        "max_offset": args.max_offset,
        "flag_states_note": "factor flags are tri-state True/False/None; None = "
                            "insufficient data and is IGNORED by the lift engine "
                            "(never counted as 'not present').",
        "factor_defs": {k: {"dimension": d, "subfactor": s, "desc": desc,
                            "horizon": FACTOR_HORIZONS.get(k)}
                        for k, (d, s, desc) in FACTOR_DEFS.items()},
        "feature_count": len(rows),
        "skipped": skipped,
        "observation": f"features measured at the confirmation day (first session "
                       f"≥ {args.confirm_pct:.0%} above the trough, ≤ {args.max_offset} "
                       f"sessions) — the realistic momentum-screener entry, not the literal bottom.",
        "scope_note": "Only Dim1/Dim5 are free-reconstructable historically; "
                      "Dim2/3/4/6 require Phase 1.5 (EDGAR) / Phase 2 (forward snapshots).",
        "features": rows,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[reconstruct] {len(rows)} feature rows ({skipped} skipped) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
