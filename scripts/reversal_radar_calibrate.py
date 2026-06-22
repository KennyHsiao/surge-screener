#!/usr/bin/env python3
"""反轉雷達 per-signal CALIBRATION — which reversal signals actually precede a bounce?

This is the "improve accuracy over time" loop for the PURE-RULES reversal radar (no LLM):
forward validation (reversal_radar_forward.py) measures whether a TURNING+ read pays off in
aggregate; THIS breaks that down BY SIGNAL so a human can see which flags carry predictive
weight and which are noise, then hand-tune reversal_radar.py's thresholds/weights. It NEVER
auto-tunes (same never-auto-tune / fail-closed discipline as retro_factor_lift).

Method (kept in lock-step with the forward harness — reuses its EXACT resolution so the
numbers can't drift): read this lane's dated scan_*.json (REVERSAL_LANE_ID), keep the FULL
candidate (its per-dimension detail flags), de-dupe each (ticker, signal_date), resolve every
entry forward with reversal_radar_forward._resolve / TIERS, then for each SIGNAL split the
RESOLVED entries into fired-vs-not and compare the TOUCH hit-rate (Wilson) + mean hold-to-
window-end return. "lift" = hit_rate(fired) − hit_rate(not). A signal is only called
PREDICTIVE when its fired sample clears MIN_CELL AND its Wilson lower bound beats the tier
base rate (conservative); otherwise NOISE or INSUFFICIENT.

Honesty: inherits every forward caveat (current-membership survivorship, delisted drops,
optimistic TOUCH, gross EV, bootstrap CI). Per-signal cells are SMALL early on, so the
whole report is PROVISIONAL until the forward sample matures (MIN_RESOLVED per tier) — it is a
hypothesis generator for human review, NOT an actionable signal and NOT an auto-tuner.

CLI:  python scripts/reversal_radar_calibrate.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import retro_factor_lift as rfl          # noqa: E402 — Wilson interval (shared)
import reversal_radar as _rr             # noqa: E402 — json_default
import reversal_radar_forward as _fwd    # noqa: E402 — EXACT forward resolution (in sync)
from reversal_radar_scan import REVERSAL_LANE_ID  # noqa: E402

OUT_DIR = REPO / "reports" / "reversal_radar"
MIN_CELL = 30  # min RESOLVED fired entries before a per-signal verdict is anything but INSUFFICIENT


def _n(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# Signal predicates over a candidate's PERSISTED detail dicts (see reversal_radar.*_component).
# Only flags that actually survive into scan_*.json are testable here; score-only contributors
# (ma_reclaim / snapback / RSI-band) are NOT individually recoverable — noted in the report.
SIGNALS: list[tuple[str, object]] = [
    ("structure.bb_squeeze",        lambda c: c.get("structure", {}).get("bb_squeeze") is True),
    ("structure.rsi_40_65",         lambda c: c.get("structure", {}).get("rsi_40_65") is True),
    ("structure.above_30pct_low",   lambda c: c.get("structure", {}).get("above_30pct_of_low") is True),
    ("momentum.rsi_bull_div",       lambda c: bool(c.get("momentum", {}).get("rsi_bull_div"))),
    ("momentum.macd_bull_div",      lambda c: bool(c.get("momentum", {}).get("macd_bull_div"))),
    ("momentum.macd_golden_10d",    lambda c: bool(c.get("momentum", {}).get("macd_golden_10d"))),
    ("options.backwardation",       lambda c: bool(c.get("options", {}).get("backwardation"))),
    ("options.put_skew>=0.10",      lambda c: (_n(c.get("options", {}).get("put_skew")) or 0) >= 0.10),
    ("options.cpr>=1.2",            lambda c: (_n(c.get("options", {}).get("call_put_volume_ratio")) or 0) >= 1.2),
    ("options.iv_pct>=70",          lambda c: (_n(c.get("options", {}).get("iv_percentile")) or 0) >= 70),
    ("sector.Improving",            lambda c: c.get("sector", {}).get("quadrant") == "Improving"),
    ("sector.rs_momentum>100",      lambda c: (_n(c.get("sector", {}).get("rs_momentum")) or 0) > 100),
    ("insider.buying",              lambda c: c.get("insider", {}).get("net_direction") == "buying"),
    ("analyst.net_up_revisions>0",  lambda c: (c.get("analyst", {}).get("net_up_revisions") or 0) > 0),
    ("analyst.upside_pct>=25",      lambda c: (_n(c.get("analyst", {}).get("upside_pct")) or 0) >= 25),
    ("tier>=TURNING",               lambda c: c.get("status") in ("REVERSAL", "TURNING")),
    ("tier=REVERSAL",               lambda c: c.get("status") == "REVERSAL"),
]


def _collect_full() -> list[dict]:
    """One FULL candidate per (ticker, signal_date), ONLY this reversal lane's snapshots
    (REVERSAL_LANE_ID) so attribution never mixes rule versions. Keeps the per-dimension
    detail dicts (unlike forward._collect_entries which keeps only ticker/date/score)."""
    seen: dict[tuple, dict] = {}
    for f in sorted(OUT_DIR.glob("scan_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("lane_id") != REVERSAL_LANE_ID:
            continue
        for c in d.get("candidates", []):
            if not c.get("ticker"):
                continue
            sdate = c.get("signal_date") or d.get("as_of_date")
            key = (c["ticker"], sdate)
            cand = dict(c)
            cand["entry_date"] = sdate
            if key not in seen or (sdate or "") < (seen[key].get("entry_date") or ""):
                seen[key] = cand
    return list(seen.values())


def _resolve_full(cand: dict) -> dict | None:
    """Attach the forward per-tier outcome to the FULL candidate, via the forward harness's
    EXACT resolver (so hit/horizon definitions never drift). Returns None if unresolvable."""
    r = _fwd._resolve({"ticker": cand["ticker"], "entry_date": cand.get("entry_date")})
    if r is None:
        return None
    cand = dict(cand)
    cand["tiers"] = r["tiers"]
    return cand


def _cell(rows: list[dict], label: str, pred) -> dict:
    """Fired-vs-not TOUCH hit-rate + mean horizon return for ONE tier among RESOLVED rows."""
    res = [r for r in rows if r["tiers"][label]["resolved"]]
    fired = [r for r in res if pred(r)]
    notf = [r for r in res if not pred(r)]

    def _rate(group):
        n = len(group)
        h = sum(1 for r in group if r["tiers"][label]["hit"])
        lo, hi = rfl._wilson(h, n) if n else (0.0, 1.0)
        hz = [r["tiers"][label]["horizon_return"] for r in group
              if r["tiers"][label]["horizon_return"] is not None]
        return {"n": n, "hits": h, "hit_rate": round(h / n, 4) if n else None,
                "wilson90": [round(lo, 4), round(hi, 4)],
                "mean_horizon": round(sum(hz) / len(hz), 4) if hz else None}

    f, nf = _rate(fired), _rate(notf)
    base_rate = (sum(1 for r in res if r["tiers"][label]["hit"]) / len(res)) if res else None
    lift = (f["hit_rate"] - nf["hit_rate"]) if (f["hit_rate"] is not None and nf["hit_rate"] is not None) else None
    if f["n"] < MIN_CELL:
        verdict = "INSUFFICIENT"
    elif base_rate is not None and f["wilson90"][0] > base_rate and (lift or 0) > 0:
        verdict = "PREDICTIVE"
    else:
        verdict = "NOISE"
    return {"fired": f, "not_fired": nf, "base_rate": round(base_rate, 4) if base_rate is not None else None,
            "lift": round(lift, 4) if lift is not None else None, "verdict": verdict}


def _markdown(payload: dict) -> str:
    L = [f"# 反轉雷達 因子校準 (per-signal forward lift)",
         "",
         f"- 產生時間: `{payload['generated_at']}`",
         f"- lane: `{payload['lane_id']}`",
         f"- 累積進場: **{payload['entries_accumulated']}** · 可結算: **{payload['price_resolvable']}** "
         f"(drop {payload['dropped_pct']})",
         f"- 總體判讀: **{payload['verdict']}** "
         f"(每 tier 需 ≥{payload['min_resolved_for_verdict']} 結算才 MATURE)",
         "",
         "> 探索性、非投資建議、**不自動調參**。每個 signal cell 需 "
         f"≥{MIN_CELL} 個已結算 fired 樣本才給判定;PREDICTIVE = fired 的 Wilson 下界 > 該 tier 基準命中率。",
         "> 未持久化、無法在此歸因的訊號: structure.ma_reclaim / structure.snapback / momentum.rsi-band。",
         ""]
    for label, _p, _w in _fwd.TIERS:
        t = payload["by_tier"][label]
        L.append(f"## {label}  ·  結算 {t['resolved']} 檔  ·  基準命中率 "
                 f"{t['base_hit_rate'] if t['base_hit_rate'] is not None else '—'}  ·  [{t['tier_verdict']}]")
        L.append("")
        L.append("| signal | fired n | fired 命中率 (Wilson90) | not-fired 命中率 | lift | 判定 |")
        L.append("|---|---:|---|---:|---:|---|")
        for sig in t["signals"]:
            c = sig["cell"]
            fr = c["fired"]
            fr_rate = f"{fr['hit_rate']} ({fr['wilson90'][0]}–{fr['wilson90'][1]})" if fr["hit_rate"] is not None else "—"
            nf_rate = c["not_fired"]["hit_rate"] if c["not_fired"]["hit_rate"] is not None else "—"
            L.append(f"| `{sig['signal']}` | {fr['n']} | {fr_rate} | {nf_rate} | "
                     f"{c['lift'] if c['lift'] is not None else '—'} | {c['verdict']} |")
        L.append("")
    L.append("---")
    L.append("**如何使用**: 連續多月 PREDICTIVE 的訊號 → 在 reversal_radar.py 加重;持續 NOISE(lift≤0)→ "
             "降權或移除門檻。改任何規則就 bump `REVERSAL_LANE_ID`,讓 forward / 本表從新版重新累積。")
    return "\n".join(L)


def main() -> int:
    entries = _collect_full()
    resolved = [r for r in (_resolve_full(e) for e in entries) if r is not None]
    dropped = len(entries) - len(resolved)
    dropped_pct = round(dropped / len(entries), 4) if entries else None

    by_tier: dict[str, dict] = {}
    for label, _p, _w in _fwd.TIERS:
        res = [r for r in resolved if r["tiers"][label]["resolved"]]
        base = (sum(1 for r in res if r["tiers"][label]["hit"]) / len(res)) if res else None
        sigs = [{"signal": name, "cell": _cell(resolved, label, pred)} for name, pred in SIGNALS]
        by_tier[label] = {
            "resolved": len(res),
            "base_hit_rate": round(base, 4) if base is not None else None,
            "tier_verdict": "MATURE" if len(res) >= _fwd.MIN_RESOLVED else "PROVISIONAL",
            "signals": sigs,
        }
    min_resolved = min((t["resolved"] for t in by_tier.values()), default=0)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "reversal_radar_calibrate", "lane_id": REVERSAL_LANE_ID,
        "entries_accumulated": len(entries), "price_resolvable": len(resolved),
        "dropped_count": dropped, "dropped_pct": dropped_pct,
        "min_resolved_across_tiers": min_resolved, "min_resolved_for_verdict": _fwd.MIN_RESOLVED,
        "min_cell_for_signal_verdict": MIN_CELL,
        "verdict": ("PROVISIONAL — per-signal cells indicative only, below maturity"
                    if min_resolved < _fwd.MIN_RESOLVED else "MATURE"),
        "caveats": [
            "Inherits all reversal_radar_forward caveats (survivorship, delisted drops, "
            "optimistic TOUCH, gross EV, bootstrap CI).",
            "Per-signal cells are SMALL early — a PREDICTIVE flag on <~50 samples is a hypothesis.",
            "NEVER auto-tunes; human reads this and hand-adjusts reversal_radar.py.",
            "Score-only contributors (ma_reclaim/snapback/RSI-band) are not persisted → not attributed.",
        ],
        "note": "per-signal forward lift for the PURE-RULES reversal radar; the monthly "
                "calibration step of the accuracy loop. Bump REVERSAL_LANE_ID on any rule change.",
        "by_tier": by_tier,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "calibration.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=_rr.json_default), encoding="utf-8")
    (OUT_DIR / "calibration.md").write_text(_markdown(payload), encoding="utf-8")
    print(f"[reversal-cal] {len(entries)} entries, {len(resolved)} resolvable, "
          f"{dropped} dropped ({dropped_pct}) → {payload['verdict']}")
    for label, _p, _w in _fwd.TIERS:
        t = by_tier[label]
        pred = sum(1 for s in t["signals"] if s["cell"]["verdict"] == "PREDICTIVE")
        print(f"  {label} [{t['tier_verdict']}]: resolved {t['resolved']}, base "
              f"{t['base_hit_rate']}, PREDICTIVE signals {pred}/{len(t['signals'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
