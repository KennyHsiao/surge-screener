#!/usr/bin/env python3
"""Risk Guard 風險雷達 — V1 rule-based risk scoring over existing free signals.

Integrates the screener's market regime, price action, options flow, sector
rotation, COT background and IBKR positions into ONE per-ticker risk read
(0-100, higher = more dangerous) and four states NORMAL / WATCH / REDUCE / EXIT.

Design (see docs/risk_guard_plan.md):
  - Read-only, no orders, not investment advice.
  - Deterministic rules ONLY — the LLM never sets a risk score (V1).
  - fail-closed: missing data adds to Data Quality (and is surfaced), never
    silently counts as 0 risk — but a data gap alone must not force EXIT.
  - Per-ticker fetch failures are isolated (one bad ticker can't abort the scan).

This module is pipeline-level (CLI / cron / imported by ui/risk_guard.py) and does
NOT import streamlit. It reuses scripts/momentum_options, options_free, sector_flow
directly and reads the JSON artifacts by path.

Weights / caps (total 0-100):
  Market 20 · Price 25 · Options 20 · Sector 15 · Position 10 · COT 5 · DataQuality 5

CLI:
  python scripts/risk_guard.py --tickers NVDA,AMD,SPY
  python scripts/risk_guard.py --from-watchlist
  python scripts/risk_guard.py --from-candidates
  python scripts/risk_guard.py --tickers NVDA --output reports/risk_guard/latest.json
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import momentum_options as mo  # noqa: E402
import options_free  # noqa: E402
import sector_flow as sf  # noqa: E402

# ── paths ──────────────────────────────────────────────────────────────────
SCORED = REPO / "scored_candidates.json"
RECON = REPO / "reports" / "reconciliation.json"
COT_DIR = REPO / "reports" / "cot"
FLOW_LATEST = REPO / "reports" / "options_flow" / "latest.json"
WATCHLIST = REPO / "content" / "us_watchlist.txt"
OUT_DEFAULT = REPO / "reports" / "risk_guard" / "latest.json"

CAPS = {"market": 20, "price": 25, "options": 20, "sector": 15,
        "position": 10, "cot": 5, "data_quality": 5}


# ── helpers ──────────────────────────────────────────────────────────────────
def _status(score: float) -> str:
    if score >= 75:
        return "EXIT"
    if score >= 50:
        return "REDUCE"
    if score >= 25:
        return "WATCH"
    return "NORMAL"


def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None


def _read_json(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        pass
    return None


def normalize_ticker(raw: str) -> str:
    """'NASDAQ:NVDA' / '$nvda' → 'NVDA'."""
    t = (raw or "").strip().upper().lstrip("$")
    if ":" in t:  # exchange-prefixed (us_watchlist.txt style)
        t = t.split(":", 1)[1]
    return t.strip()


# ── ticker collection (V1.1) ─────────────────────────────────────────────────
def tickers_from_watchlist() -> list[str]:
    out, seen = [], set()
    try:
        for line in WATCHLIST.read_text().splitlines():
            t = normalize_ticker(line)
            if t and not line.strip().startswith("#") and t not in seen:
                seen.add(t)
                out.append(t)
    except Exception:  # noqa: BLE001
        pass
    return out


def tickers_from_candidates(scored: dict | None = None) -> list[str]:
    scored = scored if scored is not None else _read_json(SCORED)
    out, seen = [], set()
    for c in ((scored or {}).get("all_scored") or []):
        t = normalize_ticker(c.get("ticker", ""))
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def tickers_from_positions(recon: dict | None = None) -> list[str]:
    recon = recon if recon is not None else _read_json(RECON)
    out, seen = [], set()
    for bucket in ("matched", "held_not_in_ledger"):
        for pos in ((recon or {}).get(bucket) or []):
            t = normalize_ticker(pos.get("ticker", ""))
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


# ── regime / market (Market 0-20) ────────────────────────────────────────────
def _live_regime() -> dict:
    """Fallback when scored_candidates.json is absent: SPY 50/200DMA + VIX live."""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY").history(period="1y")["Close"].dropna()
        vix = yf.Ticker("^VIX").history(period="1mo")["Close"].dropna()
        px = float(spy.iloc[-1])
        ma50 = float(spy.iloc[-50:].mean()) if len(spy) >= 50 else None
        ma200 = float(spy.iloc[-200:].mean()) if len(spy) >= 200 else None
        return {
            "spy_vs_50dma": (("below" if px < ma50 else "above") if ma50 else None),
            "spy_vs_200dma": (("below" if px < ma200 else "above") if ma200 else None),
            "vix_level": (round(float(vix.iloc[-1]), 2) if len(vix) else None),
            "regime_warnings": [],
            "source": "live_yfinance",
        }
    except Exception:  # noqa: BLE001
        return {}


def load_regime() -> tuple[dict, str]:
    """(regime_context, source). Prefer scored_candidates.json; else live."""
    scored = _read_json(SCORED)
    rc = (scored or {}).get("regime_context")
    if rc:
        rc = dict(rc)
        rc.setdefault("source", "scored_candidates.json")
        return rc, "scored_candidates.json"
    return _live_regime(), "live_yfinance"


def market_component(regime: dict) -> tuple[int, list[str]]:
    s, reasons = 0, []
    if regime.get("spy_vs_50dma") == "below":
        s += 7
        reasons.append("SPY 跌破 50 日均線")
    if regime.get("spy_vs_200dma") == "below":
        s += 10
        reasons.append("SPY 跌破 200 日均線")
    vix = _num(regime.get("vix_level"))
    if vix is not None:
        if vix >= 30:
            s += 12
            reasons.append(f"VIX {vix:.0f} ≥ 30(高度恐慌)")
        elif vix >= 25:
            s += 8
            reasons.append(f"VIX {vix:.0f} ≥ 25")
        elif vix >= 20:
            s += 5
            reasons.append(f"VIX {vix:.0f} ≥ 20")
    gm = _num(regime.get("global_score_multiplier"))
    if gm is not None:
        if gm < 0.65:
            s += 8
            reasons.append(f"全域評分乘數 {gm:.2f} < 0.65")
        elif gm < 0.85:
            s += 5
            reasons.append(f"全域評分乘數 {gm:.2f} < 0.85")
    warns = regime.get("regime_warnings") or []
    if warns:
        s += min(2 * len(warns), 5)
        reasons.append(f"{len(warns)} 條 regime 警告")
    return min(s, CAPS["market"]), reasons


# ── COT background (COT 0-5, systemic) ───────────────────────────────────────
def latest_cot() -> dict | None:
    try:
        files = sorted(glob.glob(str(COT_DIR / "*.verified.json")), reverse=True)
        return _read_json(Path(files[0])) if files else None
    except Exception:  # noqa: BLE001
        return None


def cot_component(cot: dict | None) -> tuple[int, list[str], dict, bool, bool]:
    """Returns (score<=5, reasons, summary, stale, missing). COT is background only.

    NOTE: leveraged_funds / asset_manager live under the nested ``cot`` block of the
    verified JSON ({"cot": {...}, "price": {...}, "tuesday_vs_friday": {...}}); only
    tuesday_vs_friday and price are top-level."""
    if not cot:
        return 0, [], {}, False, True
    c = cot.get("cot") or {}                         # nested positioning block
    s, reasons = 0, []
    tvf = cot.get("tuesday_vs_friday") or {}
    delta_pts = _num(tvf.get("delta_points"))
    tue = _num(tvf.get("as_of_tuesday_close"))
    delta_pct = (delta_pts / tue * 100) if (delta_pts is not None and tue) else None
    if delta_pct is not None and delta_pct <= -1.5:
        s += 2
        reasons.append(f"ES 週二→週五 {delta_pct:.1f}%")
    lev = c.get("leveraged_funds") or {}
    if _num(lev.get("chg_net")) is not None and lev["chg_net"] < 0 \
            and _num(lev.get("chg_short")) and lev["chg_short"] > 0:
        s += 2
        reasons.append("槓桿基金加空(net 轉弱)")
    am = c.get("asset_manager") or {}
    if _num(am.get("chg_net")) is not None and am["chg_net"] < 0:
        s += 1
        reasons.append("資產管理人淨多單減少")
    stale = bool((cot.get("price") or {}).get("cot_stale_warning"))
    summary = {
        "as_of": c.get("as_of"),
        "delta_points": delta_pts,
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
        "leveraged_net": _num(lev.get("net")),
        "asset_manager_net": _num(am.get("net")),
        "stale": stale,
    }
    return min(s, CAPS["cot"]), reasons, summary, stale, False


# ── price / technical (Price 0-25) ───────────────────────────────────────────
def price_component(mres: dict | None, df) -> tuple[int, list[str], dict, list[str]]:
    if not mres or not mres.get("available"):
        return 0, [], {}, ["technical"]
    t = mres.get("technical") or {}
    s, reasons = 0, []
    close = _num(t.get("price"))
    for key, pts, label in (("ma20", 5, "MA20"), ("ma50", 8, "MA50"), ("ma200", 12, "MA200")):
        ma = _num(t.get(key))
        if close is not None and ma is not None and close < ma:
            s += pts
            reasons.append(f"收盤跌破 {label}")
    win_gap: list[str] = []
    try:
        if df is None or len(df) < 21:
            win_gap = ["price_window"]  # fail-closed: window rules couldn't run, surface it
        if df is not None and len(df) >= 21:
            c, o, low, high = df["Close"], df["Open"], df["Low"], df["High"]
            last = float(c.iloc[-1])
            prior_low = float(low.iloc[-21:-1].min())
            if last < prior_low:
                s += 8
                reasons.append("跌破近 20 日低點")
            if len(c) >= 6:
                r5 = (last / float(c.iloc[-6]) - 1) * 100
                if r5 <= -8:
                    s += 8
                    reasons.append(f"5 日跌幅 {r5:.0f}%")
            if len(c) >= 21:
                r20 = (last / float(c.iloc[-21]) - 1) * 100
                if r20 <= -15:
                    s += 8
                    reasons.append(f"20 日跌幅 {r20:.0f}%")
            for i in range(max(1, len(o) - 5), len(o)):  # >8% gap-down within 5d
                prev = float(c.iloc[i - 1])
                if prev > 0 and float(o.iloc[i]) < prev * 0.92:
                    s += 10
                    reasons.append("近 5 日內 >8% 跳空下跌")
                    break
            rng = (high - low).rolling(14).mean()  # range-based ATR proxy for "expanding"
            if len(rng.dropna()) >= 16:
                atr_now, atr_prev = float(rng.iloc[-1]), float(rng.iloc[-15])
                if atr_now > atr_prev * 1.1 and not t.get("price_above_vwap", True):
                    s += 5
                    reasons.append("ATR 擴大且跌破 VWAP")
    except Exception:  # noqa: BLE001 — return rules still apply if window math fails
        win_gap = ["price_window"]
    return min(s, CAPS["price"]), reasons, t, win_gap


# ── options (Options 0-20) ───────────────────────────────────────────────────
def _flow_for(ticker: str, flow: dict | None) -> dict | None:
    for sig in ((flow or {}).get("signals") or (flow or {}).get("flows") or []):
        if normalize_ticker(sig.get("ticker", "")) == ticker:
            return sig
    return None


def options_component(ticker: str, mres: dict | None, ores: dict | None,
                      flow: dict | None) -> tuple[int, list[str], dict, list[str]]:
    s, reasons, gaps = 0, [], []
    detail = {}
    if not ores or not ores.get("available"):
        gaps.append("options")
    else:
        d6a = (ores.get("details") or {}).get("6a") or {}
        pcr = _num(d6a.get("put_call_ratio"))
        detail["put_call_ratio"] = pcr
        if pcr is not None:
            if pcr > 1.8:
                s += 10
                reasons.append(f"Put/Call 量比 {pcr:.1f}(避險需求高)")
            elif pcr > 1.2:
                s += 5
                reasons.append(f"Put/Call 量比 {pcr:.1f}")
        # OTM put-volume concentration (plan §4.6): downside hedging skew
        spot = _num(ores.get("spot_price")) or _num((mres or {}).get("spot"))
        tot_put = _num(d6a.get("total_put_volume"))
        puts = ores.get("top_active_puts") or []
        if spot and tot_put and puts:
            otm_put = sum((_num(p.get("volume")) or 0) for p in puts
                          if _num(p.get("strike")) and p["strike"] < spot * 0.95)
            conc = otm_put / tot_put if tot_put else 0
            detail["otm_put_concentration"] = round(conc, 2)
            if conc > 0.4:
                s += 5
                reasons.append(f"OTM put 量集中 {conc:.0%}(下檔避險)")
        # NOTE: near-term IV backwardation (plan §4.6 / §V3) needs multi-expiry term
        # structure (not in a single free chain call) — deferred to V3 Options Risk Pro.
    iv = (mres or {}).get("iv") or {}
    ivp = _num(iv.get("iv_percentile"))
    detail["iv_percentile"] = ivp
    if ivp is not None:
        if ivp >= 85:
            s += 10
            reasons.append(f"IV 百分位 {ivp:.0f} ≥ 85")
        elif ivp >= 70:
            s += 5
            reasons.append(f"IV 百分位 {ivp:.0f} ≥ 70")
    sig = _flow_for(ticker, flow)
    if sig and str(sig.get("direction", "")).lower() == "bearish":
        s += 8
        reasons.append("異常流為偏空方向")
        detail["flow_direction"] = "bearish"
    return min(s, CAPS["options"]), reasons, detail, gaps


# ── sector (Sector 0-15) ─────────────────────────────────────────────────────
def sector_component(ticker: str, flow: dict | None) -> tuple[int, list[str], dict, list[str]]:
    try:
        etf = sf.sector_etf_for(ticker)
    except Exception:  # noqa: BLE001
        etf = None
    if not etf or not flow or not flow.get("sectors"):
        return 0, [], {}, ["sector"]
    sec = {x.get("etf"): x for x in flow["sectors"]}.get(etf)
    if not sec:
        return 0, [], {"etf": etf}, ["sector"]
    s, reasons = 0, []
    q = sec.get("quadrant")
    if q == "Lagging":
        s += 12
        reasons.append(f"板塊 {sec.get('name_zh', etf)} 落後(Lagging)")
    elif q == "Weakening":
        s += 8
        reasons.append(f"板塊 {sec.get('name_zh', etf)} 轉弱(Weakening)")
    # plan §4.7: heat falling OR low. "falling" ← RS-Momentum below the 100 pivot
    # (relative strength decelerating); "low" ← heat_score < 40.
    heat = _num(sec.get("heat_score"))
    rsm = _num(sec.get("rs_momentum"))
    if (heat is not None and heat < 40) or (rsm is not None and rsm < 100):
        s += 3
        reasons.append(f"板塊熱度低/動能轉弱(熱{heat:.0f}·RS-Mom{rsm:.0f})"
                       if heat is not None and rsm is not None else "板塊熱度低/動能轉弱")
    ex = _num(sec.get("excess_20d"))
    if ex is not None and ex < -5:
        s += 5
        reasons.append(f"板塊 20 日超額 {ex:.0f}%")
    summary = {"etf": etf, "name_zh": sec.get("name_zh"), "quadrant": q,
               "quadrant_zh": sec.get("quadrant_zh"), "heat_score": heat,
               "excess_20d": ex, "rs_ratio": _num(sec.get("rs_ratio")),
               "rs_momentum": _num(sec.get("rs_momentum"))}
    return min(s, CAPS["sector"]), reasons, summary, []


# ── position (Position 0-10) ─────────────────────────────────────────────────
def _dte(expiry: str) -> int | None:
    try:
        exp = datetime.strptime(str(expiry), "%Y%m%d").date()
        return (exp - datetime.now(timezone.utc).date()).days
    except Exception:  # noqa: BLE001
        return None


def position_component(ticker: str, recon: dict | None) -> tuple[int, list[str], dict, list[str]]:
    if not recon:
        return 0, [], {}, []
    held_set = {normalize_ticker(p.get("ticker", ""))
                for p in (recon.get("held_not_in_ledger") or [])}
    pos = None
    for bucket in ("matched", "held_not_in_ledger"):
        for p in (recon.get(bucket) or []):
            if normalize_ticker(p.get("ticker", "")) == ticker:
                pos = p
                break
        if pos:
            break
    if not pos:
        return 0, [], {}, []
    s, reasons, gaps = 0, [], []
    if ticker in held_set:
        s += 3
        reasons.append("持有但不在 ledger(未被追蹤)")
    legs = pos.get("legs") or []

    # plan §4.9: legs missing complete data → flag a position data gap (→ +DQ).
    def _incomplete(lg: dict) -> bool:
        if _num(lg.get("return_pct")) is None or _num(lg.get("unrealized_pnl")) is None:
            return True  # can't judge P&L risk for this leg
        if lg.get("secType") == "OPT" and (not lg.get("expiry") or not _num(lg.get("strike"))):
            return True  # can't judge DTE / structure for this option leg
        return False
    if any(_incomplete(lg) for lg in legs):
        gaps.append("position_data")
    rets = [_num(lg.get("return_pct")) for lg in legs if _num(lg.get("return_pct")) is not None]
    worst = min(rets) if rets else None
    if worst is not None:
        if worst <= -25:
            s += 8
            reasons.append(f"未實現虧損 {worst:.0f}%")
        elif worst <= -10:
            s += 4
            reasons.append(f"未實現虧損 {worst:.0f}%")
    opt_dtes = [(_dte(lg.get("expiry")), _num(lg.get("unrealized_pnl")))
                for lg in legs if lg.get("secType") == "OPT" and lg.get("expiry")]
    losing = (worst is not None and worst < 0)
    min_dte = min([d for d, _ in opt_dtes if d is not None], default=None)
    if min_dte is not None:
        if min_dte <= 7:
            s += 8
            reasons.append(f"選擇權 DTE {min_dte} ≤ 7")
        elif min_dte <= 14 and losing:
            s += 5
            reasons.append(f"選擇權 DTE {min_dte} ≤ 14 且虧損")
    summary = {"total_unrealized_pnl": _num(pos.get("total_unrealized_pnl")),
               "worst_leg_return_pct": worst, "min_option_dte": min_dte,
               "leg_count": len(legs), "held_not_in_ledger": ticker in held_set}
    return min(s, CAPS["position"]), reasons, summary, gaps


# ── per-ticker orchestration ─────────────────────────────────────────────────
def _score_ticker(ticker: str, regime: dict, market_score: int, market_reasons: list[str],
                  cot_score: int, cot_reasons: list[str], cot_stale: bool,
                  sector_board: dict | None, options_flow: dict | None,
                  recon: dict | None, include_positions: bool) -> dict:
    gaps: list[str] = []
    # technical + options share the momentum fetch
    try:
        mres = mo.analyze(ticker)
    except Exception:  # noqa: BLE001
        mres = None
    try:
        df = mo._daily(ticker)
    except Exception:  # noqa: BLE001
        df = None
    try:
        ores = options_free.analyze_options(ticker)
    except Exception:  # noqa: BLE001
        ores = None

    p_s, p_r, technical, p_gaps = price_component(mres, df)
    o_s, o_r, options, o_gaps = options_component(ticker, mres, ores, options_flow)
    sec_s, sec_r, sector, sec_gaps = sector_component(ticker, sector_board)
    pos_s, pos_r, position, pos_gaps = (position_component(ticker, recon)
                                        if include_positions else (0, [], {}, []))
    gaps = p_gaps + o_gaps + sec_gaps + pos_gaps

    # Data Quality (0-5, fail-closed): missing inputs add risk, surfaced as gaps.
    dq = 0
    if "technical" in gaps:
        dq += 3
    if "price_window" in gaps:      # OHLCV history too short → window rules skipped
        dq += 2
    if "options" in gaps:
        dq += 3
    if "sector" in gaps:
        dq += 2
    if "position_data" in gaps:     # legs missing complete data (plan §4.9)
        dq += 2
    if cot_stale:
        dq += 2
        gaps.append("cot_stale")
    dq = min(dq, CAPS["data_quality"])

    risk = market_score + p_s + o_s + sec_s + pos_s + cot_score + dq
    risk = max(0, min(100, risk))
    # fail-closed: if the stock's OWN core signals are missing we cannot call it
    # NORMAL (safe). Flag DATA_GAP (grey, never green) so a data hole is never read
    # as low risk — but it also doesn't force EXIT.
    n_core_missing = sum(1 for g in ("technical", "options", "sector") if g in gaps)
    core_blind = ("technical" in gaps) or n_core_missing >= 2
    status = "DATA_GAP" if core_blind else _status(risk)
    primary = (p_r + o_r + sec_r + pos_r + market_reasons + cot_reasons)[:6]
    gap_labels = {"technical": "技術資料", "price_window": "價格歷史不足",
                  "options": "選擇權資料", "sector": "板塊資料",
                  "position_data": "持倉腿資料不全", "cot_stale": "COT 過舊"}
    return {
        "ticker": ticker,
        "status": status,
        "risk_score": risk,
        "market_score": market_score,
        "price_score": p_s,
        "options_score": o_s,
        "sector_score": sec_s,
        "position_score": pos_s,
        "cot_score": cot_score,
        "data_quality_score": dq,
        "primary_reasons": primary,
        "data_gaps": [gap_labels.get(g, g) for g in dict.fromkeys(gaps)],
        "position": position,
        "technical": {k: technical.get(k) for k in
                      ("price", "ma20", "ma50", "ma200", "vwap", "atr14", "rsi14",
                       "price_above_vwap", "resistance_20d")},
        "options": options,
        "sector": sector,
    }


def analyze_risk(tickers: list[str], include_positions: bool = True) -> dict:
    """Score a list of tickers. Never raises on a single bad ticker."""
    tickers = list(dict.fromkeys(normalize_ticker(t) for t in tickers if normalize_ticker(t)))
    regime, regime_src = load_regime()
    market_score, market_reasons = market_component(regime)
    cot = latest_cot()
    cot_score, cot_reasons, cot_summary, cot_stale, cot_missing = cot_component(cot)
    try:
        flow = sf.gather_sector_flow()
    except Exception:  # noqa: BLE001
        flow = None
    options_flow = _read_json(FLOW_LATEST)
    recon = _read_json(RECON) if include_positions else None

    # systemic (scan-level) data gaps — surfaced, not hidden (fail-closed §4.3).
    # NB: reports/sector_rotation.json is the LLM read and carries NO per-sector
    # RS/quadrant, so it can't substitute for gather_sector_flow in scoring.
    systemic_gaps = []
    if cot_missing:
        systemic_gaps.append("COT 背景資料缺(reports/cot/*.verified.json)")
    if not options_flow:
        systemic_gaps.append("選擇權異常流資料缺(僅影響偏空異常流加分)")
    if not flow or not flow.get("sectors"):
        systemic_gaps.append("板塊輪動資料缺(sector_flow)")
    weakening = ([s.get("name_zh") or s.get("etf")
                  for s in (flow.get("sectors") if flow else []) or []
                  if s.get("quadrant") in ("Weakening", "Lagging")][:4]) if flow else []

    rows = []
    for t in tickers:
        try:
            rows.append(_score_ticker(t, regime, market_score, market_reasons,
                                      cot_score, cot_reasons, cot_stale,
                                      flow, options_flow, recon, include_positions))
        except Exception as e:  # noqa: BLE001 — isolate per-ticker failure
            # fail-closed: a failed analysis is NOT 0/NORMAL. Reflect the known
            # systemic risk + a full data-quality penalty, and mark DATA_GAP so it
            # can never be misread as "safe".
            dq = CAPS["data_quality"]
            rrisk = max(0, min(100, market_score + cot_score + dq))
            rows.append({"ticker": t, "status": "DATA_GAP", "risk_score": rrisk,
                         "market_score": market_score, "price_score": 0,
                         "options_score": 0, "sector_score": 0, "position_score": 0,
                         "cot_score": cot_score, "data_quality_score": dq,
                         "primary_reasons": ["個股分析失敗,無法評估個股風險"],
                         "data_gaps": [f"分析失敗:{e}"],
                         "position": {}, "technical": {}, "options": {}, "sector": {}})

    # systemic market block (0-100 standalone read = market + cot scaled).
    # fail-closed: do NOT dilute the % by a component whose data is MISSING — a
    # missing COT must not make the market look calmer than it actually is. So the
    # denominator only counts caps we actually had data for.
    sys_max = CAPS["market"] + (0 if cot_missing else CAPS["cot"])
    market_only = round((market_score + cot_score) / sys_max * 100) if sys_max else 0
    # fail-closed: if regime data is entirely unavailable, the market read is
    # DATA_GAP — never NORMAL/0 (which would falsely signal a calm market).
    regime_usable = any(regime.get(k) is not None
                        for k in ("spy_vs_50dma", "spy_vs_200dma", "vix_level"))
    market_status = _status(market_only) if regime_usable else "DATA_GAP"
    market_reasons_out = market_reasons + cot_reasons
    if not regime_usable:
        market_reasons_out = ["大盤資料暫缺,無法判定市場風險"] + market_reasons_out
    high = sum(1 for r in rows if r["status"] in ("REDUCE", "EXIT"))
    gap_ct = sum(1 for r in rows if r["data_gaps"] or r["status"] == "DATA_GAP")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": regime.get("scan_date") or datetime.now(timezone.utc).date().isoformat(),
        "market": {
            "status": market_status,
            "score": market_only,
            "reasons": market_reasons_out,
            "regime": regime,
            "cot": cot_summary,
            "weakening_sectors": weakening,
            "data_gaps": systemic_gaps,
        },
        "summary": {"count": len(rows), "high_risk": high, "data_gaps": gap_ct,
                    "systemic_gaps": len(systemic_gaps)},
        "rows": rows,
        "data_sources": {
            "regime": regime_src if regime_usable else "missing",
            "cot": "reports/cot/*.verified.json" if cot else "missing",
            "positions": "reports/reconciliation.json" if recon else "missing",
            "options_flow": "reports/options_flow/latest.json" if options_flow else "missing",
            "sector": "sector_flow.gather_sector_flow" if flow else "missing",
            "options": "yfinance_free",
        },
        "disclaimer": "僅供訊號生成,非投資建議。風險分數為規則式整合,缺資料計入資料品質、不視為低風險。",
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Risk Guard 風險雷達 — rule-based risk scan")
    ap.add_argument("--tickers", help="comma/space separated tickers")
    ap.add_argument("--from-watchlist", action="store_true", help="use content/us_watchlist.txt")
    ap.add_argument("--from-candidates", action="store_true", help="use scored_candidates.json")
    ap.add_argument("--from-positions", action="store_true", help="use reconciliation.json holdings")
    ap.add_argument("--no-positions", action="store_true", help="skip IBKR position scoring")
    ap.add_argument("--output", default=None, help="write JSON here (e.g. reports/risk_guard/latest.json)")
    args = ap.parse_args()

    tickers: list[str] = []
    if args.tickers:
        import re
        tickers += [normalize_ticker(t) for t in re.split(r"[\s,;]+", args.tickers) if t.strip()]
    if args.from_watchlist:
        tickers += tickers_from_watchlist()
    if args.from_candidates:
        tickers += tickers_from_candidates()
    if args.from_positions:
        tickers += tickers_from_positions()
    tickers = list(dict.fromkeys(t for t in tickers if t))
    if not tickers:
        tickers = ["SPY", "NVDA", "AMD"]
        print("(no tickers given — defaulting to SPY,NVDA,AMD)", file=sys.stderr)

    result = analyze_risk(tickers, include_positions=not args.no_positions)

    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
