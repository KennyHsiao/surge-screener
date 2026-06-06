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


def scan(universe: str = "coiled_base", limit: int | None = None) -> dict:
    if universe == "sp1500":
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


def main() -> int:
    ap = argparse.ArgumentParser(description="反轉雷達 discovery scan")
    ap.add_argument("--universe", default="coiled_base", choices=["coiled_base", "sp1500"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output", default=str(OUT_DIR / "latest.json"))
    args = ap.parse_args()

    out = scan(universe=args.universe, limit=args.limit)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = Path(args.output)
    latest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    dated = OUT_DIR / f"scan_{out['as_of_date']}.json"
    dated.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {latest}\nwrote {dated}\nscanned={out['scanned']} matched={out['match_count']}")
    for c in out["candidates"][:12]:
        print(f"  {c['ticker']:6s} {c['status']:11s} {c['reversal_score']:3d}  "
              f"front_run={(c.get('lead_vs_confirm') or {}).get('front_run')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
