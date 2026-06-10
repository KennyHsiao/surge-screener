#!/usr/bin/env python3
"""Theme money-flow board — narrow-theme capital flow via a free price×volume proxy.

A US-side port of the Taiwan 法人淨買超 "資金流" rotation idea. The TW market has
free per-stock institutional net-buy data; US does NOT. So this estimates buying
pressure from free OHLCV with the **Chaikin money-flow DOLLAR** proxy and is
labelled honestly everywhere as a PROXY, never real institutional net-buy (the
same honesty rule as 選擇權異常流: free data is price×volume, not the aggressor side).

Per bar, signed dollar flow:
    mfm_t = ((close-low) - (high-close)) / (high-low)      # ∈ [-1,1], 0 when high==low
    mfv_t = mfm_t * close * volume                          # signed dollars
Each ticker's daily mfv is winsorised to ±K_WINSOR·ADV20 (one gap/earnings bar
can't dominate; the multiplier is bounded but close×volume is not), then a theme's
constituents are dollar-additively SUMMED into one per-day series D_t. From the
SAME D_t:
    flow_5d   = D_t.tail(5).sum  (min 4 valid)      → X (近5日淨流向)
    accel     = mean(last5) - mean(prior5)          → Y (流向加速度)
    flow_20d  = D_t.tail(20).sum (min 15 valid)     → bubble size (近20日累計)
All three are normalised by the basket's ADV20 (cross-theme comparability); the
raw signed dollars are kept for hover/table. Returns use Adj Close (split-safe);
mfv uses raw OHLCV (auto_adjust=False) so the $ notional is honest.

`gather_theme_flow()` NEVER raises — None on total failure; each ticker AND each
theme is isolated so one bad symbol/basket can't lose the rest. Cached 1h. Pure
numpy/pandas (the .venv has no scipy). Baskets are hand-curated in
content/theme_baskets.json. The verified board feeds the LLM read in
scripts/theme_rotation.py (verified-data-to-AI).

CLI:  python scripts/theme_flow.py [--json]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_BASKETS_FILE = REPO / "content" / "theme_baskets.json"

BENCHMARK = "SPY"
PERIOD = "1y"                 # longest window is 20 bars + ADV20 + warmup — 1y is ample
CHUNK_SIZE = 120             # symbols per yf.download call (chunked so a partial fail is local)
ADV_FLOOR = 5_000_000.0      # $5M ADV20 illiquidity floor — thinner names excluded from a basket
K_WINSOR = 3.0               # clip each ticker's daily mfv to ±K_WINSOR·ADV20 (outlier-bar guard)
# Neutral deadband on flow_5d_norm. Because flow_5d_norm = (5-day net signed $) ÷
# ADV20 is dimensionless, this is an ABSOLUTE, scale-stable threshold (a percentile-
# of-magnitudes deadband is sample-fragile: when all themes flow strongly it would
# mislabel strong flows as neutral). 0.30 ≈ net 5-day flow under ~⅓ of one day's
# turnover → genuinely flat. Tunable.
EPS_X = 0.30
MIN_USED = 3                 # a theme needs ≥ this many usable constituents to be shown
MIN_COVERAGE = 0.5           # suppress a theme if usable/(curated−illiquid) drops below this
# The 11 SPDR GICS sectors — the only keys rotation_summary().by_etf exposes, so a
# basket's curated parent_sector_etfs must be a subset of these (thematic ETFs aren't there).
SPDR_SECTORS = {"XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"}

# Heat = weighted blend of cross-sectional percentile ranks (0-100). flow_5d_norm &
# flow_20d_norm are collinear (both net-flow magnitude/direction) so their COMBINED
# weight is held to 0.50 to avoid double-counting (mirrors sector_flow's rs_ratio/
# excess_20d cap); accel_norm (is it speeding up) + rvol (real volume) carry the rest.
THEME_HEAT_WEIGHTS = {"flow_5d_norm": 0.25, "flow_20d_norm": 0.25,
                      "accel_norm": 0.30, "rvol": 0.20}

# Honest, proxy-only capital-state labels. NOTE: deliberately NOT the TW app's
# 主力/法人 wording — we have no real net-buy data; those terms live only in the caveat.
STATE_INFLOW_ACC = "加速流入(推估)"
STATE_INFLOW_SLOW = "流入趨緩"
STATE_NEUTRAL = "中性"
STATE_OUTFLOW = "流出(推估)"
STATES = (STATE_INFLOW_ACC, STATE_INFLOW_SLOW, STATE_NEUTRAL, STATE_OUTFLOW)


def _cached(namespace: str, params, ttl: float, compute):
    """Best-effort disk cache; falls back to plain compute() if unavailable.

    Copied verbatim from scripts/sector_flow.py — the cache is never load-bearing
    for correctness, so any failure degrades to a direct compute()."""
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


def _baskets_fingerprint() -> str:
    """mtime+size of theme_baskets.json, folded into the cache key so a hand-edit
    of the baskets auto-busts the 1h disk cache."""
    try:
        st = _BASKETS_FILE.stat()
        return f"{int(st.st_mtime)}:{st.st_size}"
    except Exception:
        return "missing"


def load_baskets() -> dict[str, dict]:
    """{theme_name: {"desc","tickers","reps_hint","parent_sector_etfs"}} from
    content/theme_baskets.json. Structured (not a bare ticker list) because
    reps_hint / parent_sector_etfs are needed downstream. {} on any failure so
    gather degrades to None rather than crashing.

    Curated `parent_sector_etfs` are validated to the 11 SPDR keys (invalid values
    dropped); the universe is the curated tickers themselves (NOT intersected with
    the surge-filtered sp1500 survivors, which would selection-bias the board bullish)."""
    try:
        import json
        raw = json.loads(_BASKETS_FILE.read_text(encoding="utf-8")) or {}
        themes = raw.get("themes", {}) or {}
        out: dict[str, dict] = {}
        for name, rec in themes.items():
            if not isinstance(rec, dict):
                continue
            tickers = [str(t).upper().strip() for t in (rec.get("tickers") or [])
                       if str(t).strip()]
            tickers = list(dict.fromkeys(tickers))  # dedupe, keep order
            if not tickers:
                continue
            parents = [p for p in (rec.get("parent_sector_etfs") or [])
                       if p in SPDR_SECTORS]
            reps_hint = [str(t).upper().strip() for t in (rec.get("reps_hint") or [])
                         if str(t).strip()]
            out[str(name)] = {
                "desc": str(rec.get("desc") or ""),
                "tickers": tickers,
                "reps_hint": reps_hint,
                "parent_sector_etfs": parents,
            }
        return out
    except Exception:
        return {}


def _money_flow_volume(high, low, close, volume):
    """Per-bar signed dollar money-flow volume (the proxy primitive).

    mfm = ((C-L)-(H-C))/(H-L) ∈ [-1,1] is the Chaikin money-flow multiplier (where
    the close sits in the day's range — near +1 if it closes on the high). mfv =
    mfm × C × V is dollar-denominated so big caps dominate like real flow. mfm is
    0 when H==L (div-by-zero guard); NaN bars are preserved (never zero-filled)."""
    import numpy as np
    rng = (high - low)
    mfm = ((close - low) - (high - close)) / rng.where(rng > 0)
    mfm = mfm.where(rng > 0, 0.0)          # flat bar → no directional pressure, not NaN
    return mfm * close * volume


def _capital_state(flow_5d_norm: float, accel_norm: float, eps_x: float) -> str:
    """4-bucket capital state (honest proxy labels), the 2×2 analog of _quadrant.

    Classified on the ADV-NORMALISED flow (a raw-dollar deadband isn't comparable
    across themes of different ADV). The neutral deadband eps_x is set
    cross-sectionally per run; the inflow-acc/slow split uses the sign of accel."""
    if flow_5d_norm is None or flow_5d_norm != flow_5d_norm:
        return STATE_NEUTRAL
    if abs(flow_5d_norm) <= eps_x:
        return STATE_NEUTRAL
    if flow_5d_norm < 0:
        return STATE_OUTFLOW
    # inflow: split by acceleration sign (None accel → treat as not-accelerating)
    if accel_norm is not None and accel_norm == accel_norm and accel_norm >= 0:
        return STATE_INFLOW_ACC
    return STATE_INFLOW_SLOW


def gather_theme_flow() -> dict | None:
    """Theme money-flow snapshot, or None on failure. Cached 1h.

    The basket-file fingerprint is in the cache params so editing the curated
    baskets self-invalidates the cache."""
    return _cached("theme_flow", {"v": 2, "baskets": _baskets_fingerprint()},
                   3600, _compute_theme_flow)


def _per_ticker(field_frames: dict, t: str) -> dict | None:
    """Compute one ticker's winsorised mfv series + ADV20 + ret_5d, or None.

    Isolated in try/except by the caller; here we just fail-closed (None) on any
    insufficiency so a thin/garbage symbol is dropped, never silently zeroed."""
    import numpy as np
    try:
        hi = field_frames["High"].get(t)
        lo = field_frames["Low"].get(t)
        cl = field_frames["Close"].get(t)
        adj = field_frames["Adj Close"].get(t)
        vol = field_frames["Volume"].get(t)
        if any(x is None for x in (hi, lo, cl, vol)):
            return None
        dollar_vol = (cl * vol).dropna()
        if len(dollar_vol) < 15:           # ADV20 needs a near-complete window
            return None
        adv20 = float(dollar_vol.tail(20).mean())
        if not np.isfinite(adv20) or adv20 < ADV_FLOOR:
            return None                    # illiquid → excluded from the basket
        mfv = _money_flow_volume(hi, lo, cl, vol)
        clip = K_WINSOR * adv20
        mfv = mfv.clip(lower=-clip, upper=clip)   # outlier-bar winsorisation
        # ret_5d from Adj Close (split/div-safe); raw close would fake crash/rebound.
        ret_5d = None
        a = adj.dropna() if adj is not None else cl.dropna()
        if len(a) >= 6 and float(a.iloc[-6]) > 0:
            ret_5d = (float(a.iloc[-1]) / float(a.iloc[-6]) - 1.0) * 100.0
        last_dollar_vol = None
        if len(dollar_vol):
            last_dollar_vol = float(dollar_vol.iloc[-1])
        return {"mfv": mfv, "adv20": adv20, "ret_5d": ret_5d,
                "last_dollar_vol": last_dollar_vol}
    except Exception:
        return None


def _compute_theme_flow() -> dict | None:
  try:
    try:
        import logging
        import numpy as np
        import pandas as pd
        import yfinance as yf
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # quiet delisted-symbol noise
    except ImportError:
        return None

    baskets = load_baskets()
    if not baskets:
        return None

    union = sorted({t for b in baskets.values() for t in b["tickers"]})
    if not union:
        return None

    # ── Chunked download. SPY is added to EVERY chunk so each chunk has ≥2 tickers
    # (guarantees a MultiIndex frame) and to anchor a benchmark; a failed chunk is
    # counted in `failed`, not silently dropped. ───────────────────────────────────
    FIELDS = ("High", "Low", "Close", "Adj Close", "Volume")
    field_lists: dict[str, list] = {f: [] for f in FIELDS}
    present: set[str] = set()
    failed: set[str] = set()
    for i in range(0, len(union), CHUNK_SIZE):
        chunk = union[i:i + CHUNK_SIZE]
        req = list(dict.fromkeys(chunk + [BENCHMARK]))
        try:
            d = yf.download(req, period=PERIOD, auto_adjust=False,
                            threads=True, progress=False, group_by="column")
        except Exception:
            failed.update(chunk)
            continue
        if d is None or d.empty or not isinstance(d.columns, pd.MultiIndex):
            failed.update(chunk)
            continue
        lvl0 = set(d.columns.get_level_values(0))
        got = set(d["Close"].columns) if "Close" in lvl0 else set()
        failed.update(t for t in chunk if t not in got)
        present.update(t for t in chunk if t in got)
        for fld in FIELDS:
            if fld in lvl0:
                field_lists[fld].append(d[fld])
    # Combine chunks per field; SPY recurs in every chunk so drop duplicate columns.
    field_frames: dict[str, "pd.DataFrame"] = {}
    for fld, lst in field_lists.items():
        if not lst:
            continue
        fr = pd.concat(lst, axis=1)
        field_frames[fld] = fr.loc[:, ~fr.columns.duplicated()]
    if "Close" not in field_frames or not present:
        return None

    # ── Per-ticker proxy (isolated). SPY included so its ret_5d anchors excess_5d. ──
    tinfo: dict[str, dict] = {}
    have = set(field_frames["Close"].columns)
    for t in present | ({BENCHMARK} if BENCHMARK in have else set()):
        info = _per_ticker(field_frames, t)
        if info is not None:
            tinfo[t] = info

    # ── Per-theme aggregation (isolated). ──────────────────────────────────────────
    spy_ret5 = None
    if BENCHMARK in tinfo:
        spy_ret5 = tinfo[BENCHMARK].get("ret_5d")
    rows: list[dict] = []
    member_count: dict[str, int] = {}   # cross-theme: how many themes a ticker is in
    for name, b in baskets.items():
        try:
            constituents = b["tickers"]
            n_total = len(constituents)
            n_failed = sum(1 for t in constituents if t in failed)
            used = [t for t in constituents if t in tinfo]
            n_used = len(used)
            # measurable = curated minus those excluded for illiquidity/insufficiency
            # but still successfully downloaded; coverage guards a chunk-outage bias.
            measurable = [t for t in constituents if t not in failed]
            cov = (n_used / len(measurable)) if measurable else 0.0
            if n_used < MIN_USED or cov < MIN_COVERAGE:
                continue
            for t in used:
                member_count[t] = member_count.get(t, 0) + 1

            mfv_df = pd.DataFrame({t: tinfo[t]["mfv"] for t in used}).sort_index()
            d_t = mfv_df.sum(axis=1, min_count=1)        # all-NaN day → NaN, not 0
            flow_20d = float(d_t.tail(20).sum(min_count=15)) if d_t.tail(20).count() >= 15 else None
            flow_5d = float(d_t.tail(5).sum(min_count=4)) if d_t.tail(5).count() >= 4 else None
            recent5, prior5 = d_t.tail(5), d_t.iloc[-10:-5]
            accel = (float(recent5.mean()) - float(prior5.mean())) \
                if recent5.count() >= 4 and prior5.count() >= 4 else None
            if flow_5d is None or flow_20d is None:
                continue

            theme_adv20 = float(sum(tinfo[t]["adv20"] for t in used))
            if theme_adv20 <= 0:
                continue
            flow_5d_norm = flow_5d / theme_adv20
            flow_20d_norm = flow_20d / theme_adv20
            accel_norm = (accel / theme_adv20) if accel is not None else None
            last_dv = sum(tinfo[t]["last_dollar_vol"] for t in used
                          if tinfo[t]["last_dollar_vol"] is not None)
            rvol = (last_dv / theme_adv20) if theme_adv20 else None

            # theme 5d return = ADV-weighted mean of constituent ret_5d
            wnum = wden = 0.0
            for t in used:
                r, w = tinfo[t]["ret_5d"], tinfo[t]["adv20"]
                if r is not None and r == r:
                    wnum += r * w
                    wden += w
            ret_5d = (wnum / wden) if wden else None

            # 代表股 + intra-theme concentration, both by 20d cumulative flow.
            per_flow20 = {}
            for t in used:
                s = tinfo[t]["mfv"]
                v = float(s.tail(20).sum(min_count=15)) if s.tail(20).count() >= 15 else None
                if v is not None:
                    per_flow20[t] = v
            total_abs = sum(abs(v) for v in per_flow20.values())
            top_share = (max(abs(v) for v in per_flow20.values()) / total_abs) \
                if per_flow20 and total_abs > 0 else None
            ranked = sorted(per_flow20, key=lambda t: per_flow20[t], reverse=True)
            rep_tickers = ranked[:3] or b["reps_hint"][:3] or used[:3]
            reps = [{"ticker": t, "flow_20d": round(per_flow20.get(t, 0.0), 0),
                     "flow_5d": round(float(tinfo[t]["mfv"].tail(5).sum(min_count=4)), 0)
                     if tinfo[t]["mfv"].tail(5).count() >= 4 else None,
                     "ret_5d": (round(tinfo[t]["ret_5d"], 1)
                                if tinfo[t]["ret_5d"] is not None else None)}
                    for t in rep_tickers]

            rows.append({
                "theme": name,
                "desc": b["desc"],
                "parent_sector_etfs": b["parent_sector_etfs"],
                "flow_5d": round(flow_5d, 0), "flow_20d": round(flow_20d, 0),
                "accel": round(accel, 0) if accel is not None else None,
                "flow_5d_norm": round(flow_5d_norm, 4),
                "flow_20d_norm": round(flow_20d_norm, 4),
                "accel_norm": round(accel_norm, 4) if accel_norm is not None else None,
                "rvol": round(rvol, 2) if rvol is not None else None,
                "ret_5d": round(ret_5d, 1) if ret_5d is not None else None,
                "excess_5d": round(ret_5d - spy_ret5, 1)
                if (ret_5d is not None and spy_ret5 is not None) else None,
                "top_share": round(top_share, 2) if top_share is not None else None,
                "high_concentration": bool(top_share is not None and top_share >= 0.6),
                "n_used": n_used, "n_total": n_total, "n_failed": n_failed,
                "reps": reps,
            })
        except Exception:  # noqa: BLE001 — one bad basket never aborts the rest
            continue

    if not rows:
        return None

    # ── Cross-sectional: heat blend, capital state, 抄底. ───────────────────────────
    eps_x = EPS_X  # absolute, scale-stable deadband (flow_5d_norm is dimensionless)

    def _rank(values):
        arr = np.array([v if v is not None else np.nan for v in values], dtype=float)
        return (pd.Series(arr).rank(pct=True) * 100).to_numpy()  # NaN stays NaN

    ranks = {k: _rank([r.get(k) for r in rows]) for k in THEME_HEAT_WEIGHTS}
    for i, r in enumerate(rows):
        num = den = 0.0
        for k, w in THEME_HEAT_WEIGHTS.items():
            v = ranks[k][i]
            if v == v:
                num += w * float(v)
                den += w
        r["heat_score"] = round(num / den, 1) if den else None
        r["capital_state"] = _capital_state(r["flow_5d_norm"], r.get("accel_norm"), eps_x)
        # 抄底: price down (5d) but proxy-flow IN — accumulation into weakness.
        r["bottom_fishing"] = bool(r.get("ret_5d") is not None and r["ret_5d"] < 0
                                   and r["flow_5d_norm"] > eps_x)

    rows.sort(key=lambda r: (r["heat_score"] if r["heat_score"] is not None else -1),
              reverse=True)

    # Cross-theme overlap: mega-caps shared across many baskets aren't independent.
    shared = sorted(({"ticker": t, "themes": n} for t, n in member_count.items() if n >= 3),
                    key=lambda d: d["themes"], reverse=True)

    from datetime import datetime, timezone
    as_of = None
    try:
        as_of = str(field_frames["Close"].dropna(how="all").index[-1].date())
    except Exception:
        pass
    buckets = {s: [r["theme"] for r in rows if r["capital_state"] == s] for s in STATES}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": BENCHMARK,
        "as_of": as_of,
        "params": {"period": PERIOD, "adv_floor": ADV_FLOOR, "k_winsor": K_WINSOR,
                   "eps_x": eps_x, "heat_weights": THEME_HEAT_WEIGHTS,
                   "min_used": MIN_USED},
        "themes": rows,
        "buckets": buckets,
        "bottom_fishing": [r["theme"] for r in rows if r["bottom_fishing"]],
        "shared_mega_caps": shared,
        "n_failed_download": len(failed),
    }
  except Exception:  # noqa: BLE001 — gather_theme_flow() must never raise
    return None


def theme_flow_summary() -> dict | None:
    """Compact snapshot for the (optional, Phase-2) scoring pipeline — verified
    numbers only, mirroring sector_flow.rotation_summary(). Kept light/ASCII-ish so
    downstream prompts stay lean. None when unavailable."""
    flow = gather_theme_flow()
    if not flow:
        return None
    by_theme = {r["theme"]: {
        "state": r["capital_state"], "flow_5d_norm": r["flow_5d_norm"],
        "accel_norm": r.get("accel_norm"), "flow_20d_norm": r["flow_20d_norm"],
        "heat": r.get("heat_score"), "bottom_fishing": r["bottom_fishing"],
        "reps": [x["ticker"] for x in r["reps"]],
        "parents": r["parent_sector_etfs"],
    } for r in flow["themes"]}
    return {
        "as_of": flow.get("as_of"),
        "accelerating": flow["buckets"].get(STATE_INFLOW_ACC, []),
        "outflowing": flow["buckets"].get(STATE_OUTFLOW, []),
        "bottom_fishing": flow.get("bottom_fishing", []),
        "by_theme": by_theme,
    }


def _fmt_m(v) -> str:
    """Format a raw-dollar value as a compact $M/$B string for the CLI."""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"{v/1e9:+.1f}B"
    return f"{v/1e6:+.0f}M"


if __name__ == "__main__":
    import json
    out = gather_theme_flow()
    if not out:
        print("no data (check content/theme_baskets.json exists + yfinance reachable)")
        sys.exit(1)
    print(f"as_of={out['as_of']}  benchmark={out['benchmark']}  "
          f"themes={len(out['themes'])}  download_failed={out['n_failed_download']}")
    for s in STATES:
        names = out["buckets"].get(s, [])
        print(f"  {s}: {len(names)}  {names[:6]}")
    if out["bottom_fishing"]:
        print(f"  🪝 抄底(跌勢仍流入): {out['bottom_fishing']}")
    if out["shared_mega_caps"]:
        print("  ⚠ 跨主題共用龍頭(非獨立訊號): "
              + ", ".join(f"{d['ticker']}×{d['themes']}" for d in out["shared_mega_caps"][:8]))
    print(f"\n{'主題':<22}{'狀態':<14}{'熱度':>5}{'5d流向':>9}{'加速':>9}"
          f"{'20d累計':>10}{'5d%':>7}{'集中':>6}{'用量':>7}  代表股")
    for r in out["themes"]:
        print(f"{r['theme'][:20]:<22}{r['capital_state']:<14}"
              f"{(r['heat_score'] if r['heat_score'] is not None else 0):>5.0f}"
              f"{_fmt_m(r['flow_5d']):>9}{_fmt_m(r['accel']):>9}{_fmt_m(r['flow_20d']):>10}"
              f"{(r['ret_5d'] if r['ret_5d'] is not None else 0):>7.1f}"
              f"{(r['top_share'] if r['top_share'] is not None else 0):>6.2f}"
              f"{r['n_used']}/{r['n_total']:<5}  "
              + ",".join(x['ticker'] for x in r['reps']))
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2, ensure_ascii=False))
