#!/usr/bin/env python3
"""反轉雷達 / Reversal Radar — V1 leading bottoming/reversal score (inverse of Risk Guard).

Risk Guard answers "should I de-risk a held name?" (downside). Reversal Radar answers
"is this BEATEN-DOWN name bottoming/reversing, so I can enter near a low BEFORE lagging
signals (esp. COT) confirm?" Leans on LEADING indicators; COT is a SEPARATE lagging
confirmation that is NEVER added to the score (front-run it). Signal-only, NOT advice.

Mirrors scripts/risk_guard.py (pipeline-level, no streamlit, reuses fetch modules, per-
ticker try/except). Reuses risk_guard's ticker collectors / normalize_ticker / latest_cot.

Honesty (load-bearing):
  - BEATEN-DOWN precondition: only score names confirmed in a pullback/downtrend; else
    status N/A "非回檔中,不適用" (NOT a data gap, NOT a reversal reading).
  - INVERSE fail-closed: missing data NEVER fabricates a high reversal/entry reading →
    DATA_GAP (grey) + a data_confidence penalty; per-ticker except → score 0.
  - EXPLORATORY: the reversal factors are NOT runway-validated (same survivorship gap as
    the coiled-base lane) → the top REVERSAL tier is labelled exploratory/non-advice and
    inherits retro_factor_lift.is_recommendations_blocked.

Leading score 0-100 dimensions/caps: 結構22 / 動能22 / 期權18 / 板塊14 / 內部人12 / 分析師12.

CLI:
  python scripts/reversal_radar.py --tickers INTC,PYPL
  python scripts/reversal_radar.py --from-beaten-down --limit 10 --output reports/reversal_radar/latest.json
  python scripts/reversal_radar.py --tickers NVDA --no-require-pullback
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import momentum_options as mo  # noqa: E402
import options_free  # noqa: E402
import options_term  # noqa: E402
import reversal_signals as rsig  # noqa: E402
import risk_guard as rg  # noqa: E402 — reuse normalize_ticker / collectors / latest_cot / _num / _read_json
import sector_flow as sf  # noqa: E402

OVERSOLD_LATEST = REPO / "reports" / "oversold_reversal" / "latest.json"
PIT_DIR = REPO / "reports" / "retrospective" / "sp500_pit"
OUT_DEFAULT = REPO / "reports" / "reversal_radar" / "latest.json"

CAPS = {"structure": 22, "momentum": 22, "options": 18,
        "sector": 14, "insider": 12, "analyst": 12}     # leading total = 100 (no COT)
_CORE = ("structure", "momentum", "options", "sector")  # cores whose absence blinds the read

PULLBACK_HIGH_PCT = 20.0    # ≥20% off the 52w high
DD_PCT = 15.0               # ≥15% drawdown from the recent (~120d) peak

_num = rg._num


def _status(score: float) -> str:
    if score >= 70:
        return "REVERSAL"
    if score >= 45:
        return "TURNING"
    if score >= 25:
        return "STABILIZING"
    return "NONE"


# ── ticker collection (reuse risk_guard + a beaten-down source) ──────────────
def tickers_from_beaten_down() -> list[str]:
    data = rg._read_json(OVERSOLD_LATEST) or {}
    out, seen = [], set()
    for c in (data.get("candidates") or []):
        t = rg.normalize_ticker(c.get("ticker", ""))
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ── exploratory gate (inherited; reversal factors not runway-validated) ───────
def exploratory_gate() -> dict:
    """Reversal factors are NOT runway-validated (same survivorship gap as the lane), so
    the radar is ALWAYS exploratory. We additionally surface the canonical fail-closed
    source gate for transparency. Never raises."""
    source_blocked = True
    try:
        import retro_factor_lift as rfl
        fl = json.loads((PIT_DIR / "factor_lift.json").read_text(encoding="utf-8"))
        source_blocked = rfl.is_recommendations_blocked(fl)
    except Exception:  # noqa: BLE001
        source_blocked = True
    return {"blocked": True, "runway_independent_actionable": False,
            "source_blocked": bool(source_blocked),
            "reason": "反轉因子尚未 runway 驗證(同 coiled-base lane 的倖存者偏誤);頂層僅探索性,非建議。",
            "caveats": ["反轉分數為規則式領先訊號整合,未經前向/runway 驗證 → 探索性。",
                        "以前向命中率(reversal_radar_forward)驗證後才談可行動。"]}


# ── beaten-down precondition ──────────────────────────────────────────────────
def _pullback_state(tech: dict, df) -> dict:
    px = _num(tech.get("price"))
    ma200 = _num(tech.get("ma200"))
    pct_from_high = dd = None
    try:
        close = df["Close"].to_numpy(float)
        if len(close) and px:
            hi52 = float(close[-252:].max())
            pct_from_high = (px / hi52 - 1) * 100 if hi52 else None
            peak = float(close[-120:].max()) if len(close) >= 2 else None
            dd = (px / peak - 1) * 100 if peak else None
    except Exception:  # noqa: BLE001
        pass
    beaten = bool((ma200 and px and px < ma200)
                  or (pct_from_high is not None and pct_from_high <= -PULLBACK_HIGH_PCT)
                  or (dd is not None and dd <= -DD_PCT))
    return {"beaten_down": beaten, "below_ma200": bool(ma200 and px and px < ma200),
            "pct_from_52w_high": round(pct_from_high, 1) if pct_from_high is not None else None,
            "drawdown_120d": round(dd, 1) if dd is not None else None}


# ── leading dimension scorers ────────────────────────────────────────────────
def structure_component(tech, df, sigs) -> tuple:
    s, reasons, detail = 0, [], {}
    px, rsi = _num(tech.get("price")), _num(tech.get("rsi14"))
    bb_squeeze = bool(tech.get("bb_squeeze"))
    rsi_40_65 = rsi is not None and 40 <= rsi <= 65
    above_30 = None
    try:
        close = df["Close"].to_numpy(float)
        lo52 = float(close[-252:].min()) if len(close) else None
        above_30 = bool(px and lo52 and px >= 1.30 * lo52)
    except Exception:  # noqa: BLE001
        above_30 = None
    detail.update(bb_squeeze=bb_squeeze, rsi_40_65=rsi_40_65, above_30pct_of_low=above_30)
    if bb_squeeze and rsi_40_65 and above_30:
        s += 10
        reasons.append("coiled-base 三旗(壓縮+RSI40-65+離低≥30%)")
    elif bb_squeeze and rsi_40_65:
        s += 6
        reasons.append("壓縮基底 + RSI 健康(已驗證對)")
    rec = sigs.get("ma_reclaim") or {}
    if rec.get("reclaim_ma20"):
        s += 5
        reasons.append("重新站上 MA20")
    elif rec.get("reclaim_ma50"):
        s += 3
        reasons.append("重新站上 MA50")
    snap = sigs.get("snapback") or {}
    if snap.get("snapback"):
        s += 5
        reasons.append("跌破下軌後收回(均值回歸)")
    return min(s, CAPS["structure"]), reasons, detail, []


def momentum_component(tech, sigs) -> tuple:
    s, reasons, detail = 0, [], {}
    rd = sigs.get("rsi_divergence") or {}
    md = sigs.get("macd") or {}
    detail.update(rsi_bull_div=rd.get("bullish_divergence"),
                  macd_bull_div=md.get("bullish_divergence"),
                  macd_golden_10d=md.get("golden_cross_10d"))
    if rd.get("bullish_divergence"):
        s += 8
        reasons.append("RSI 多頭背離")
    if md.get("bullish_divergence"):
        s += 6
        reasons.append("MACD 柱狀背離")
    if md.get("golden_cross_10d"):
        s += 5
        reasons.append("MACD 近 10 日黃金交叉")
    rsi = _num(tech.get("rsi14"))
    if rsi is not None and 30 <= rsi <= 45:
        s += 5
        reasons.append(f"RSI {rsi:.0f} 脫離超賣(早期回升)")
    return min(s, CAPS["momentum"]), reasons, detail, []


def options_component(ticker, mres, ores, ts) -> tuple:
    """INVERSE read of risk_guard's options: peak-fear RECEDING is bullish-contrarian."""
    s, reasons, detail, gaps = 0, [], {}, []
    iv = (mres or {}).get("iv") or {}
    ivp = _num(iv.get("iv_percentile"))
    detail["iv_percentile"] = ivp
    have_chain = bool(ores and ores.get("available"))
    have_ts = bool(ts)
    if not have_chain and not have_ts and ivp is None:
        gaps.append("options")
        return 0, reasons, detail, gaps
    if ts:
        detail.update(backwardation=ts.get("backwardation"), put_skew=ts.get("put_skew"))
        if ts.get("backwardation") and (ivp is not None and ivp >= 60):
            s += 6
            reasons.append("近月 IV 倒掛 + IV 偏高(恐慌前端,常見洗底)")
        sk = _num(ts.get("put_skew"))
        if sk is not None and sk >= 0.10:
            s += 4
            reasons.append("Put skew 偏陡(避險過度,反向偏多)")
    if have_chain:
        d6a = (ores.get("details") or {}).get("6a") or {}
        cpr = _num(d6a.get("call_put_volume_ratio"))
        detail["call_put_volume_ratio"] = cpr
        if cpr is not None and cpr >= 1.2:
            s += 5
            reasons.append(f"Call 買盤升溫(C/P 量比 {cpr:.1f})")
    if ivp is not None and ivp >= 70:
        s += 3
        reasons.append(f"IV 百分位 {ivp:.0f}(恐慌洗盤背景)")
    return min(s, CAPS["options"]), reasons, detail, gaps


def sector_component(ticker, flow) -> tuple:
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
    if q == "Improving":
        s += 10
        reasons.append(f"板塊 {sec.get('name_zh', etf)} 轉入(醞釀,最早領先)")
    rsm = _num(sec.get("rs_momentum"))
    if rsm is not None and rsm > 100:
        s += 4
        reasons.append("板塊相對動能 > 100(加速)")
    detail = {"etf": etf, "name_zh": sec.get("name_zh"), "quadrant": q,
              "quadrant_zh": sec.get("quadrant_zh"), "rs_ratio": _num(sec.get("rs_ratio")),
              "rs_momentum": rsm, "heat_score": _num(sec.get("heat_score"))}
    return min(s, CAPS["sector"]), reasons, detail, []


def insider_component(ticker, inst) -> tuple:
    if not inst:
        return 0, [], {}, ["insider"]
    ins = inst.get("insider_6m") or {}
    s, reasons = 0, []
    nd = ins.get("net_direction")
    net = _num(ins.get("net_shares"))
    if nd == "buying":
        s += 8
        reasons.append("內部人 6 月淨買進")
        if net is not None and net > 0 and _num(ins.get("purchase_trans")):
            s += 4
            reasons.append("內部人買進量能顯著")
    return min(s, CAPS["insider"]), reasons, {"net_direction": nd, "net_shares": net}, []


def analyst_component(ticker, av) -> tuple:
    if not av:
        return 0, [], {}, ["analyst"]
    s, reasons = 0, []
    rev = av.get("estimate_revisions") or {}
    up = sum((_num(r.get("up_last_30d")) or 0) for r in rev.values() if isinstance(r, dict))
    down = sum((_num(r.get("down_last_30d")) or 0) for r in rev.values() if isinstance(r, dict))
    if up > down:
        s += 6
        reasons.append(f"分析師近 30 日淨上修({int(up)}↑/{int(down)}↓)")
    acts = av.get("recent_actions") or []
    if any(str(a.get("action", "")).endswith("up") or a.get("pt_action") == "up" for a in acts):
        s += 4
        reasons.append("近期升評 / 上調目標價")
    upside = _num((av.get("price_targets") or {}).get("upside_pct"))
    if upside is not None and upside >= 25:
        s += 2
        reasons.append(f"分析師目標上行 {upside:.0f}%")
    return min(s, CAPS["analyst"]), reasons, {"net_up_revisions": int(up - down), "upside_pct": upside}, []


# ── COT — SEPARATE lagging confirmation (NEVER added to the score) ────────────
def cot_confirmation(cot: dict | None) -> dict:
    if not cot:
        return {"available": False,
                "note": "COT 為落後訊號;領先分數不等它。此處僅作事後確認。"}
    c = cot.get("cot") or {}
    lev, am = c.get("leveraged_funds") or {}, c.get("asset_manager") or {}
    tvf = cot.get("tuesday_vs_friday") or {}
    delta_pts, tue = _num(tvf.get("delta_points")), _num(tvf.get("as_of_tuesday_close"))
    lev_long = _num(lev.get("chg_net")) is not None and lev["chg_net"] > 0
    am_long = _num(am.get("chg_net")) is not None and am["chg_net"] > 0
    return {"available": True, "as_of": c.get("as_of"),
            "stale": bool((cot.get("price") or {}).get("cot_stale_warning")),
            "leveraged_funds_turning_long": bool(lev_long),
            "asset_manager_turning_long": bool(am_long),
            "es_week_delta_pct": (round(delta_pts / tue * 100, 2)
                                  if (delta_pts is not None and tue) else None),
            "confirms_reversal": bool(lev_long or am_long),
            "note": "COT 落後;領先分數不等它。若 COT 也轉多 = 慢錢跟上(事後確認)。"}


# ── per-ticker orchestration ─────────────────────────────────────────────────
def _score_ticker(ticker, flow, cot_confirms, require_pullback) -> dict:
    base = {"ticker": ticker, "reversal_score": 0, "data_confidence": 100,
            "structure_score": 0, "momentum_score": 0, "options_score": 0,
            "sector_score": 0, "insider_score": 0, "analyst_score": 0,
            "primary_signals": [], "data_gaps": [], "lead_vs_confirm": {},
            "structure": {}, "momentum": {}, "options": {}, "sector": {},
            "insider": {}, "analyst": {}, "pullback": {}}
    try:
        mres = mo.analyze(ticker)
    except Exception:  # noqa: BLE001
        mres = None
    if not mres or not mres.get("available"):
        return {**base, "status": "DATA_GAP", "data_confidence": 0,
                "data_gaps": ["技術資料"], "primary_signals": ["技術資料不可用,無法判定"]}
    tech = mres.get("technical") or {}
    try:
        df = mo._daily(ticker)
    except Exception:  # noqa: BLE001
        df = None

    pull = _pullback_state(tech, df)
    base["pullback"] = pull
    if require_pullback and not pull["beaten_down"]:
        return {**base, "status": "N/A",
                "primary_signals": ["非回檔中,不適用(僅對下跌一段的股票評反轉)"]}

    sigs = rsig.all_signals(df) if df is not None else {}
    try:
        ores = options_free.analyze_options(ticker)
    except Exception:  # noqa: BLE001
        ores = None
    spot = _num((ores or {}).get("spot_price")) or _num(mres.get("spot"))
    try:
        ts = options_term.term_structure(ticker, spot)
    except Exception:  # noqa: BLE001
        ts = None
    try:
        from institutional_free import gather_institutional
        inst = gather_institutional(ticker)
    except Exception:  # noqa: BLE001
        inst = None
    try:
        from analyst_free import gather_analyst_views
        av = gather_analyst_views(ticker)
    except Exception:  # noqa: BLE001
        av = None

    st_s, st_r, st_d, st_g = structure_component(tech, df, sigs)
    mo_s, mo_r, mo_d, mo_g = momentum_component(tech, sigs)
    op_s, op_r, op_d, op_g = options_component(ticker, mres, ores, ts)
    se_s, se_r, se_d, se_g = sector_component(ticker, flow)
    in_s, in_r, in_d, in_g = insider_component(ticker, inst)
    an_s, an_r, an_d, an_g = analyst_component(ticker, av)

    gaps = st_g + mo_g + op_g + se_g + in_g + an_g
    score = st_s + mo_s + op_s + se_s + in_s + an_s
    score = max(0, min(100, score))

    # INVERSE fail-closed: missing CORE evidence must never read as a strong reversal.
    n_core_missing = sum(1 for g in _CORE if g in gaps)
    confidence = max(0, 100 - 25 * n_core_missing - 8 * (len(gaps) - n_core_missing))
    core_blind = ("structure" in gaps) or n_core_missing >= 2
    status = "DATA_GAP" if core_blind else _status(score)

    primary = (st_r + mo_r + op_r + se_r + in_r + an_r)[:6]
    gap_label = {"structure": "結構", "momentum": "動能", "options": "選擇權",
                 "sector": "板塊", "insider": "內部人", "analyst": "分析師"}
    return {**base, "status": status, "reversal_score": score, "data_confidence": confidence,
            "structure_score": st_s, "momentum_score": mo_s, "options_score": op_s,
            "sector_score": se_s, "insider_score": in_s, "analyst_score": an_s,
            "primary_signals": primary,
            "data_gaps": [gap_label.get(g, g) for g in dict.fromkeys(gaps)],
            "lead_vs_confirm": {"leading_score": score, "cot_confirms": bool(cot_confirms),
                                "front_run": bool(score >= 45 and not cot_confirms)},
            "structure": st_d, "momentum": mo_d, "options": op_d, "sector": se_d,
            "insider": in_d, "analyst": an_d, "pullback": pull}


def analyze_reversal(tickers: list[str], require_pullback: bool = True) -> dict:
    tickers = list(dict.fromkeys(rg.normalize_ticker(t) for t in tickers if rg.normalize_ticker(t)))
    try:
        flow = sf.gather_sector_flow()
    except Exception:  # noqa: BLE001
        flow = None
    cot = rg.latest_cot()
    cotc = cot_confirmation(cot)
    rows = []
    for t in tickers:
        try:
            rows.append(_score_ticker(t, flow, cotc.get("confirms_reversal"), require_pullback))
        except Exception as e:  # noqa: BLE001 — isolate; failure → lowest conviction, never high
            rows.append({"ticker": t, "status": "DATA_GAP", "reversal_score": 0,
                         "data_confidence": 0, "data_gaps": [f"分析失敗:{e}"],
                         "primary_signals": ["個股分析失敗"], "lead_vs_confirm": {}})

    scored = [r for r in rows if r["status"] in ("REVERSAL", "TURNING", "STABILIZING")]
    improving = ([s.get("name_zh") or s.get("etf")
                  for s in (flow.get("sectors") if flow else []) or []
                  if s.get("quadrant") == "Improving"][:6]) if flow else []
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "exploratory": True,
        "exploratory_gate": exploratory_gate(),
        "market": {"improving_sectors": improving},
        "cot_confirmation": cotc,
        "summary": {"count": len(rows),
                    "reversal_or_turning": sum(1 for r in rows if r["status"] in ("REVERSAL", "TURNING")),
                    "data_gaps": sum(1 for r in rows if r.get("data_gaps") or r["status"] == "DATA_GAP"),
                    "front_run": sum(1 for r in rows if (r.get("lead_vs_confirm") or {}).get("front_run"))},
        "rows": rows,
        "data_sources": {"technical": "momentum_options/yfinance_free",
                         "reversal_signals": "reversal_signals.py",
                         "options": "options_free + options_term",
                         "sector": "sector_flow.gather_sector_flow" if flow else "missing",
                         "insider": "institutional_free", "analyst": "analyst_free",
                         "cot": "reports/cot/*.verified.json" if cot else "missing"},
        "disclaimer": "僅供訊號生成,非投資建議。反轉分數為規則式整合『領先』訊號,缺資料計入低信心、"
                      "絕不視為已反轉。COT 為落後確認,不納入領先分數。反轉因子尚未驗證 → 探索性。",
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="反轉雷達 / Reversal Radar — leading reversal scan")
    ap.add_argument("--tickers")
    ap.add_argument("--from-beaten-down", action="store_true", help="use oversold_reversal/latest.json candidates")
    ap.add_argument("--from-candidates", action="store_true")
    ap.add_argument("--from-watchlist", action="store_true")
    ap.add_argument("--no-require-pullback", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    tickers: list[str] = []
    if args.tickers:
        import re
        tickers += [rg.normalize_ticker(t) for t in re.split(r"[\s,;]+", args.tickers) if t.strip()]
    if args.from_beaten_down:
        tickers += tickers_from_beaten_down()
    if args.from_candidates:
        tickers += rg.tickers_from_candidates()
    if args.from_watchlist:
        tickers += rg.tickers_from_watchlist()
    tickers = list(dict.fromkeys(t for t in tickers if t))
    if args.limit:
        tickers = tickers[:args.limit]
    if not tickers:
        tickers = ["INTC", "PYPL", "NKE"]
        print("(no tickers given — defaulting to INTC,PYPL,NKE)", file=sys.stderr)

    res = analyze_reversal(tickers, require_pullback=not args.no_require_pullback)
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
