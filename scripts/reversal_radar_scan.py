#!/usr/bin/env python3
"""反轉雷達 discovery scan — rank beaten-down names by leading reversal conviction.

Thin wrapper over reversal_radar.analyze_reversal (which fetches sector-flow + COT ONCE
for the whole list and loops internally, so this is NOT a per-ticker re-fetch loop).
Universe defaults to the coiled-base lane's already-daily-scanned candidates
(reports/oversold_reversal/latest.json — already beaten-down + liquidity-floored);
`--universe sp1500` is the heavier fallback (note the latency).

Writes reports/reversal_radar/latest.json + scan_<as_of>.json with a VERSIONED lane_id so
forward validation never mixes rule changes. EXPLORATORY (reversal factors not yet
runway-validated) — this is a discovery list, NOT investment advice.

CLI:
    python scripts/reversal_radar_scan.py                 # coiled-base universe
    python scripts/reversal_radar_scan.py --limit 30
    python scripts/reversal_radar_scan.py --universe sp1500 --limit 100
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import reversal_radar as rr  # noqa: E402

OUT_DIR = REPO / "reports" / "reversal_radar"
# Bump when any dimension / threshold changes so forward validation never mixes rules.
REVERSAL_LANE_ID = "reversal_radar.v1.structure+momentum_div+options_fear_receding+sector_improving+insider+analyst"
_CANDIDATE_TIERS = ("REVERSAL", "TURNING", "STABILIZING")


def _sp1500_universe() -> list[str]:
    """Heavier fallback universe via 01_hard_filter (note: scoring 1500 live is slow)."""
    try:
        spec = importlib.util.spec_from_file_location(
            "hard_filter", REPO / "scripts" / "01_hard_filter.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        uni = mod.load_universe("sp1500", "US")
        return [rr.rg.normalize_ticker(t.get("ticker") if isinstance(t, dict) else t)
                for t in uni]
    except Exception:  # noqa: BLE001
        return []


def _prescreen(tickers: list[str], cap: int = 400) -> list[str]:
    """Cheap df-ONLY filter (no options/sector/insider/analyst): keep names that are
    BEATEN-DOWN (below MA200 or ≥20% off the 52w high) AND show ≥1 early reversal technical
    sign (RSI/MACD divergence, MACD golden cross, capitulation, MA-reclaim, snap-back, or RSI
    just exiting oversold). One yfinance fetch per name; bounded by `cap`. This is what makes
    the discovery scan actually surface 'down-then-turning' names (coiled bases score ~0)."""
    import momentum_options as mo
    import reversal_signals as rsig
    keep = []
    for t in tickers[:cap]:
        try:
            df = mo._daily(t)
            if df is None or len(df) < 60:
                continue
            tech = mo._technical(df)
            close = df["Close"].to_numpy(float)
            px, ma200 = tech.get("price"), tech.get("ma200")
            hi52 = float(close[-252:].max()) if len(close) else None
            beaten = bool((ma200 and px and px < ma200) or (hi52 and px and px <= hi52 * 0.80))
            if not beaten:
                continue
            s = rsig.all_signals(df)
            rsi = tech.get("rsi14")
            early = bool(s["rsi_divergence"].get("bullish_divergence")
                         or s["macd"].get("golden_cross_10d") or s["macd"].get("bullish_divergence")
                         or s["capitulation"].get("capitulation") or s["ma_reclaim"].get("reclaim_ma20")
                         or s["snapback"].get("snapback") or (rsi is not None and 30 <= rsi <= 45))
            if early:
                keep.append(t)
        except Exception:  # noqa: BLE001
            continue
    return keep


def scan(universe: str = "coiled_base", limit: int | None = None,
         prescreen_cap: int = 400) -> dict:
    if universe == "beaten_down":
        tickers = _prescreen(_sp1500_universe(), cap=prescreen_cap)
        uni_label = "beaten_down_prescreen"
    elif universe == "sp1500":
        tickers = _sp1500_universe()
        uni_label = "sp1500"
    else:
        tickers = rr.tickers_from_beaten_down()
        uni_label = "coiled_base_candidates"
    tickers = [t for t in dict.fromkeys(tickers) if t]
    if limit:
        tickers = tickers[:limit]

    as_of = datetime.now(timezone.utc).date().isoformat()
    if not tickers:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "as_of_date": as_of,
                "lane_id": REVERSAL_LANE_ID, "universe": uni_label, "scanned": 0,
                "match_count": 0, "exploratory": True, "candidates": [],
                "note": "無宇宙(coiled-base latest.json 不存在?先跑 oversold_reversal_scan.py 或用 --universe sp1500)。"}

    res = rr.analyze_reversal(tickers, require_pullback=True)
    rows = res.get("rows") or []
    cands = [r for r in rows if r.get("status") in _CANDIDATE_TIERS]
    cands.sort(key=lambda r: (-(r.get("reversal_score") or 0), -(r.get("data_confidence") or 0)))
    for r in cands:
        r["signal_date"] = as_of            # for forward-validation de-dupe (lane pattern)

    return {
        "generated_at": res.get("generated_at"), "as_of_date": as_of,
        "lane_id": REVERSAL_LANE_ID, "universe": uni_label,
        "scanned": len(tickers), "match_count": len(cands),
        "exploratory": True, "exploratory_gate": res.get("exploratory_gate"),
        "runway_independent": False,
        "cot_confirmation": res.get("cot_confirmation"),
        "improving_sectors": (res.get("market") or {}).get("improving_sectors"),
        "candidates": cands,
        "note": "探索性:依領先反轉信念排序;反轉因子尚未驗證,以前向命中率(reversal_radar_forward)驗證後才談可行動。",
        "disclaimer": res.get("disclaimer"),
    }


_TIER_RANK = {"REVERSAL": 3, "TURNING": 2, "STABILIZING": 1}
_TIER_EMOJI = {"REVERSAL": "🟢", "TURNING": "🟦", "STABILIZING": "🟡"}


def _load(mod_name: str, func_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, REPO / "scripts" / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)


def _notify(out: dict, min_tier: str = "TURNING", top: int = 12) -> bool:
    """Push TURNING+ reversal candidates to Telegram (reuses 05_notify.send_telegram_message).
    Marks 共現 (also high-risk/falling per Risk Guard) + 搶在COT前. Silent-skip if creds absent;
    a notify glitch NEVER fails the scan (the JSON is already written)."""
    import os
    floor = _TIER_RANK.get(min_tier, 2)
    cands = [c for c in (out.get("candidates") or []) if _TIER_RANK.get(c.get("status"), 0) >= floor]
    if not cands:
        print(f"[reversal_radar] no {min_tier}+ candidates — skipping notify.", file=sys.stderr)
        return False
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[reversal_radar] TELEGRAM_* not set — skipping notify.", file=sys.stderr)
        return False
    conf = {}
    try:  # confluence = a candidate Risk Guard also flags REDUCE/EXIT (was falling)
        import risk_guard
        rr = risk_guard.analyze_risk([c["ticker"] for c in cands], include_positions=False)
        conf = {row["ticker"]: row.get("status") for row in (rr.get("rows") or [])}
    except Exception:  # noqa: BLE001
        conf = {}
    head = (f"↩ *反轉雷達* · {datetime.now(timezone.utc):%Y-%m-%d}"
            f"（{min_tier} 以上 {len(cands)} 檔 · 探索性,非投資建議）")
    lines = [head]
    for c in cands[:top]:
        t = c["ticker"]
        lv = c.get("lead_vs_confirm") or {}
        tags = []
        if conf.get(t) in ("REDUCE", "EXIT"):
            tags.append("🔴共現(曾高風險下跌)")
        if lv.get("front_run"):
            tags.append("✅搶在COT前")
        sig = " · ".join((c.get("primary_signals") or [])[:2])
        line = f"{_TIER_EMOJI.get(c['status'], '')} *${t}* {c['status']} {c.get('reversal_score')}"
        if tags:
            line += "　" + " · ".join(tags)
        if sig:
            line += f"\n{sig}"
        lines.append(line)
    try:
        send = _load("05_notify", "send_telegram_message")
        return bool(send(token, chat, "\n\n".join(lines)))
    except Exception as e:  # noqa: BLE001
        print(f"[reversal_radar] notify error: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="反轉雷達 discovery scan")
    ap.add_argument("--universe", default="coiled_base",
                    choices=["coiled_base", "beaten_down", "sp1500"],
                    help="beaten_down = df-only pre-screen of sp1500 for down-then-turning names")
    ap.add_argument("--prescreen-cap", type=int, default=400, help="max sp1500 names to pre-screen")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output", default=str(OUT_DIR / "latest.json"))
    ap.add_argument("--notify", action="store_true", help="push TURNING+ candidates to Telegram")
    ap.add_argument("--notify-min", default="TURNING",
                    choices=["STABILIZING", "TURNING", "REVERSAL"])
    args = ap.parse_args()

    out = scan(universe=args.universe, limit=args.limit, prescreen_cap=args.prescreen_cap)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = Path(args.output)
    payload = json.dumps(out, ensure_ascii=False, indent=2, default=rr.json_default)
    latest.write_text(payload, encoding="utf-8")
    dated = OUT_DIR / f"scan_{out['as_of_date']}.json"
    dated.write_text(payload, encoding="utf-8")
    print(f"wrote {latest}\nwrote {dated}\nscanned={out['scanned']} matched={out['match_count']}")
    for c in out["candidates"][:12]:
        print(f"  {c['ticker']:6s} {c['status']:11s} {c['reversal_score']:3d}  "
              f"front_run={(c.get('lead_vs_confirm') or {}).get('front_run')}")
    if args.notify:
        try:  # JSON already persisted — a notify glitch must not fail the scan
            ok = _notify(out, args.notify_min)
        except Exception as e:  # noqa: BLE001
            print(f"[reversal_radar] notify failed (scan already written): {e}", file=sys.stderr)
            ok = False
        print(f"[reversal_radar] telegram: {'sent' if ok else 'skipped/failed'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
