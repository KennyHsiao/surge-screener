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


def _fmt(x) -> str:
    return f"{x:.2f}" if isinstance(x, (int, float)) else "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runway", default=str(_ROOT / "reports" / "retrospective"
                                            / "sp500_pit" / "runway_neutral.json"))
    ap.add_argument("--lift", default=None,
                    help="factor_lift.json for the canonical gate + provenance; "
                         "default = sibling of --runway.")
    args = ap.parse_args()

    runway_path = Path(args.runway)
    data = json.loads(runway_path.read_text(encoding="utf-8"))

    # FAIL-CLOSED provenance + CANONICAL GATE (Codex + integration review). This side-channel
    # previously had NEITHER, so a stale/blocked runway_neutral could stamp a machine-readable
    # `runway_verdict: genuine` into cards (split-brain vs the factor_lift verdict). Now: the
    # runway result MUST descend from the same run as the sibling factor_lift / surge_events,
    # and on a BLOCKED run the verdict is written as exploratory, never actionable.
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "scripts"))
    import retro_factor_lift as _rfl
    lift_path = Path(args.lift) if args.lift else runway_path.parent / "factor_lift.json"
    events_path = runway_path.parent / "surge_events.json"
    if not (lift_path.exists() and events_path.exists()):
        raise SystemExit(f"[runway-sync] need {lift_path.name} + {events_path.name} beside the "
                         "runway file to verify provenance + the blocked gate (fail-closed).")
    lift_art = json.loads(lift_path.read_text(encoding="utf-8"))
    events_gen = json.loads(events_path.read_text(encoding="utf-8")).get("generated_at")
    _rfl.assert_same_run("runway-sync", events_gen, factor_lift=lift_art)
    runway_fp = (data.get("source") or {}).get("events_generated_at")
    if runway_fp != events_gen:
        raise SystemExit(f"[runway-sync] runway_neutral is from a DIFFERENT run "
                         f"({runway_fp} != {events_gen}) — re-run retro_runway_neutral_check "
                         "against the current pools (fail-closed).")
    # FEATURES adjacency anchored to the CURRENT surge_features (Codex r10): comparing
    # runway.features == lift.features only proves they agree with EACH OTHER — two stale
    # downstream artifacts (both F-OLD) would pass after surge_features is rebuilt to F-NEW.
    # Anchor to the sibling surge_features.generated_at and require BOTH to descend from it.
    features_path = runway_path.parent / "surge_features.json"
    if not features_path.exists():
        raise SystemExit(f"[runway-sync] no {features_path.name} to anchor features-adjacency "
                         "(fail-closed).")
    sf_gen = json.loads(features_path.read_text(encoding="utf-8")).get("generated_at")
    _rfl.assert_features_fresh("runway-sync", sf_gen, factor_lift=lift_art, runway_neutral=data)
    # LIQUIDITY-FLOOR adjacency (Codex r12): the runway numbers must come from the same liquidity
    # cohort as the gate — the floor doesn't change events/features, so a floor-0 runway could
    # otherwise be stamped beside a floor>0 factor_lift. Missing/mismatch ⇒ fail closed.
    # STRICT (Codex r14): both floors must be PRESENT + numeric — a missing floor must not
    # default to 0, else a floor-less factor_lift/runway passes as unfiltered.
    _fl_floor = _rfl.strict_floor(lift_art, "coverage", "liquidity_filter", "min_dollar_vol")
    _rn_floor = _rfl.strict_floor(data, "source", "min_dollar_vol")
    if _fl_floor is None or _rn_floor is None or _rn_floor != _fl_floor:
        raise SystemExit(f"[runway-sync] liquidity floor mismatch/absent: runway {_rn_floor} vs "
                         f"factor_lift {_fl_floor} — different/unknown liquidity cohort (fail-closed).")
    blocked = _rfl.is_recommendations_blocked(lift_art)

    lift = data.get("lift", {})
    run_dir = data.get("run_dir", "?")
    thr = data.get("atr_move_threshold")
    thr_s = f"{thr:.1f}" if isinstance(thr, (int, float)) else "—"

    updated, missing = 0, []
    for fac, r in lift.items():
        card = VAULT / f"{fac}.md"
        if not card.exists():
            missing.append(fac)
            continue
        o, n = r.get("orig_lift"), r.get("neutral_lift")
        reading, note = _verdict(n)
        # On a BLOCKED run the runway reading is EXPLORATORY only — write `exploratory` to the
        # machine-readable verdict (never `genuine`), keep the raw reading visible in the prose
        # under a 🔒 caveat, and carry the gate as runway_blocked.
        fm_verdict = "exploratory" if blocked else reading
        text = card.read_text(encoding="utf-8")
        _n_round = round(n, 2) if isinstance(n, (int, float)) else ""
        text = ks._update_frontmatter(text, {
            # blocked ⇒ blank the numeric runway lift too (Codex r8: a ranking consumer must not
            # see actionable numbers); keep it under an explicitly-exploratory key.
            "runway_neutral_lift": ("" if blocked else _n_round),
            "runway_neutral_lift_exploratory": (_n_round if blocked else ""),
            "runway_verdict": fm_verdict,
            "runway_blocked": blocked,
        })
        caveat = ("> 🔒 此 run 為 BLOCKED(探索性)—— 下方 runway 判讀僅供參考,不可作為可行動結論。\n\n"
                  if blocked else "")
        block = (
            "## Runway 中性檢定(ATR-normalized)\n"
            f"_來源 `{Path(run_dir).name}` · 中性目標 = 前向漲幅 ≥ {thr_s} ATR_\n\n"
            f"{caveat}"
            f"| 指標 | %-目標 lift | ATR-中性 lift |\n|---|---|---|\n"
            f"| {fac} | {_fmt(o)} | {_fmt(n)} |\n\n"
            f"> {note}\n"
        )
        text = ks._replace_section(text, "## Runway 中性檢定(ATR-normalized)", block)
        card.write_text(text, encoding="utf-8")
        updated += 1
        print(f"  {fac:22s} %={_fmt(o)} ATR={_fmt(n):>5} -> {fm_verdict}"
              + (" [blocked]" if blocked else ""))

    print(f"[runway-sync] {updated} card(s) stamped from {Path(args.runway).name} "
          f"(blocked={blocked})")
    if missing:
        print(f"[runway-sync] no card for: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
