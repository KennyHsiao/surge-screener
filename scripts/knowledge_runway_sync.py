#!/usr/bin/env python3
"""Stamp each factor card with the runway-NEUTRAL verdict (the confound-corrected truth).

retro_runway_neutral_check.py re-scores every factor under an ATR-normalized surge
target, removing the %-runway advantage of cheap/volatile stocks. A factor whose lift
holds >1 under that target is a GENUINE, runway-independent signal; one that collapses
toward 1.0 (or below) was a measurement artifact. This writes that verdict back into
knowledge/factors/<f>.md so the vault stops over-claiming the %-target verdicts.

Reads runway_neutral.json (from `retro_runway_neutral_check.py --json`). Read-only
elsewhere. Reuses knowledge_sync's idempotent frontmatter/section editors.

CLI: python scripts/knowledge_runway_sync.py [--runway reports/retrospective/sp500_pit/runway_neutral.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import knowledge_sync as ks  # reuse _update_frontmatter / _replace_section

_ROOT = Path(__file__).resolve().parent.parent
VAULT = _ROOT / "knowledge" / "factors"


def _verdict(neutral: float | None) -> tuple[str, str]:
    """(short status, human note) from the ATR-neutral lift."""
    if neutral is None:
        return "unknown", "ATR-neutral lift 無法計算(樣本不足)"
    if neutral >= 1.15:
        return "genuine", "✅ runway-independent — ATR-中性目標下 lift 仍 >1,是真訊號"
    if neutral < 0.85:
        return "runway-artifact", ("⚠️ 大半是 runway 假象 — ATR-中性下 lift 跌破 1,"
                                   "原本的正向 lift 主要來自『便宜股容易達 +X%』")
    return "runway-artifact", ("⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),"
                               "原判定是固定 %-漲幅的量測產物")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runway", default=str(_ROOT / "reports" / "retrospective"
                                            / "sp500_pit" / "runway_neutral.json"))
    args = ap.parse_args()

    data = json.loads(Path(args.runway).read_text(encoding="utf-8"))
    lift = data.get("lift", {})
    run_dir = data.get("run_dir", "?")
    thr = data.get("atr_move_threshold")

    updated, missing = 0, []
    for fac, r in lift.items():
        card = VAULT / f"{fac}.md"
        if not card.exists():
            missing.append(fac)
            continue
        o, n = r.get("orig_lift"), r.get("neutral_lift")
        status, note = _verdict(n)
        text = card.read_text(encoding="utf-8")
        text = ks._update_frontmatter(text, {
            "runway_neutral_lift": (round(n, 2) if isinstance(n, (int, float)) else ""),
            "runway_verdict": status,
        })
        block = (
            "## Runway 中性檢定(ATR-normalized)\n"
            f"_來源 `{Path(run_dir).name}` · 中性目標 = 前向漲幅 ≥ {thr:.1f} ATR_\n\n"
            f"| 指標 | %-目標 lift | ATR-中性 lift |\n|---|---|---|\n"
            f"| {fac} | {o:.2f} | {('%.2f' % n) if isinstance(n,(int,float)) else '—'} |\n\n"
            f"> {note}\n"
        )
        text = ks._replace_section(text, "## Runway 中性檢定(ATR-normalized)", block)
        card.write_text(text, encoding="utf-8")
        updated += 1
        print(f"  {fac:22s} %={o:.2f} ATR={('%.2f'%n) if isinstance(n,(int,float)) else '—':>5} -> {status}")

    print(f"[runway-sync] {updated} card(s) stamped from {Path(args.runway).name}")
    if missing:
        print(f"[runway-sync] no card for: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
