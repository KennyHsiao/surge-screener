#!/usr/bin/env python3
"""Write validation results back into the knowledge vault — close the loop.

Reads reports/retrospective/factor_lift.json and updates each
knowledge/factors/<factor>.md card so Obsidian shows the factor's CURRENT
validated state, linked to its papers and dimension:

  * frontmatter: lift, precision, verdict, verdict_mt, q_value, status,
    validated_on  (status = the FDR verdict, lower-cased)
  * a "## 驗證紀錄" section: one row per lift table (ALL + each threshold),
    with a clear "exploratory / survivorship-blocked" note when the run is gated.

Idempotent: only the synced frontmatter keys and the 驗證紀錄 section are
rewritten; everything else in the card (hypothesis, links, hand notes) is kept.
This is the inverse of knowledge_seed.py (which creates the cards) and the
sibling of knowledge_ingest.py (which adds papers from URLs).

CLI:  python scripts/knowledge_sync.py
      python scripts/knowledge_sync.py --lift <path/to/factor_lift.json>
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
VAULT = _ROOT / "knowledge"
_DEFAULT_LIFT = _ROOT / "reports" / "retrospective" / "factor_lift.json"

_STATUS = {"VALIDATED": "validated", "WEAK": "weak", "NOISE": "noise",
           "CONTRARIAN": "contrarian", "INSUFFICIENT": "insufficient"}
_SYNC_KEYS = ("lift", "precision", "verdict", "verdict_mt", "q_value",
              "status", "validated_on")


def _update_frontmatter(text: str, updates: dict) -> str:
    """Line-based frontmatter update: replace listed keys in place, append new
    ones, preserve every other line (incl. sources: [...]). Body untouched."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return text  # not a frontmatter card — leave it
    try:
        end = lines.index("---", 1)
    except ValueError:
        return text
    fm, body = lines[1:end], lines[end + 1:]
    seen, out = set(), []
    for ln in fm:
        k = ln.split(":", 1)[0].strip() if ":" in ln else None
        if k in updates:
            out.append(f"{k}: {updates[k]}")
            seen.add(k)
        else:
            out.append(ln)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}: {v}")
    return "\n".join(["---", *out, "---", *body])


def _replace_section(text: str, heading: str, new_block: str) -> str:
    """Replace the markdown section starting at `heading` (## ...) up to the next
    same-or-higher heading (or EOF) with new_block. Appends if not present."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == heading), None)
    if start is None:
        return text.rstrip() + "\n\n" + new_block.rstrip() + "\n"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[:start] + [new_block.rstrip(), ""] + lines[end:])


def _record_block(factor: str, per_table: list[dict], blocked: bool,
                  universe: str = "", point_in_time: bool = False,
                  delisted_gap: bool = False) -> str:
    src = f"{universe or 'factor_lift.json'}" + (" · point-in-time" if point_in_time else "")
    rows = ["## 驗證紀錄",
            f"_最後同步 {date.today().isoformat()} · 來源 `{src}`_",
            ""]
    if blocked:
        rows.append("> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,"
                    "不可作為下注依據。可行動的驗證走 forward 樣本外測試。")
        rows.append("")
    elif point_in_time:
        rows.append("> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → "
                    "可作為決策依據。"
                    + ("注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。" if delisted_gap else ""))
        rows.append("")
    rows += ["| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |",
             "|---|---|---|---|---|---|"]
    for r in per_table:
        ev = r.get("expected_value")
        ev_s = f"{ev*100:.0f}%" if isinstance(ev, (int, float)) else "—"
        rows.append(f"| {r['label']} | {r.get('lift'):.2f} | {ev_s} | "
                    f"{r.get('verdict')} | {r.get('verdict_mt', '—')} | "
                    f"{r.get('q_value', '—')} |")
    rows.append("")
    rows.append("> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。")
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lift", default=str(_DEFAULT_LIFT))
    ap.add_argument("--events", default=None,
                    help="surge_events.json the lift was built from; default = sibling of "
                         "--lift. Used to fail-closed if the lift is stale vs current events.")
    args = ap.parse_args()

    lift = json.loads(Path(args.lift).read_text(encoding="utf-8"))

    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "scripts"))
    import retro_factor_lift as _rfl

    # FAIL-CLOSED provenance (Codex review): only stamp cards from a factor_lift that (a) carries
    # its own generated_at and (b) descends from the CURRENT surge_events sitting beside it.
    # Missing/mismatched provenance ⇒ refuse, never skip — else a legacy / hand-edited / partial
    # CI artifact (fresh events + stale lift) launders itself as fresh validation.
    events_path = Path(args.events) if args.events else Path(args.lift).parent / "surge_events.json"
    if not events_path.exists():
        raise SystemExit(f"[sync] no {events_path} beside the lift to verify provenance "
                         "against — refusing (fail-closed). Pass --events.")
    events = json.loads(events_path.read_text(encoding="utf-8"))
    _rfl.assert_same_run("sync", events.get("generated_at"), factor_lift=lift)

    # validated_on = the artifact's OWN generation date (NOT today) — and FAIL CLOSED on a
    # missing/unparseable timestamp rather than silently dating a stale run to today, so a card
    # can never read as freshly validated when it wasn't (Codex review: validated_on honesty).
    _gen = lift.get("generated_at")
    try:
        validated_on = datetime.fromisoformat(_gen).date().isoformat()
    except (TypeError, ValueError):
        raise SystemExit(f"[sync] factor_lift has no parseable generated_at ({_gen!r}) — "
                         "refusing to stamp validated_on (fail-closed).")

    tables = lift.get("tables", {})
    # Canonical fail-closed gate (re-derives from safety fields incl membership_stale /
    # delisted_data_gap) — NOT the stored bit, so a stale/forged artifact can't stamp
    # cards as unblocked (Codex C-1 review #2).
    blocked = _rfl.is_recommendations_blocked(lift)
    cov = lift.get("coverage") or {}
    universe = cov.get("universe") or ""
    point_in_time = bool(cov.get("point_in_time_membership"))
    delisted_gap = bool(cov.get("delisted_data_gap"))
    if not tables:
        print("[sync] no lift tables; run retro_factor_lift first")
        return 1

    # factor -> {label: row} across every table; ALL is the headline.
    by_factor: dict[str, dict] = {}
    for label, tbl in tables.items():
        for r in tbl.get("factors", []):
            by_factor.setdefault(r["factor"], {})[label] = r

    order = ["ALL", *[l for l in tables if l != "ALL"]]
    synced, missing = 0, []
    for factor, per in by_factor.items():
        card = VAULT / "factors" / f"{factor}.md"
        if not card.exists():
            missing.append(factor)
            continue
        head = per.get("ALL") or next(iter(per.values()))
        _raw_verdict = head.get("verdict_mt") or head.get("verdict")
        if blocked:
            # A BLOCKED run is EXPLORATORY end-to-end. EVERY machine-readable field a consumer
            # might key on (verdict, verdict_mt, validated_on) must NOT read as validated — not
            # just `status` (Codex re-review: status:exploratory alongside verdict:VALIDATED +
            # validated_on still let a verdict/date-keyed query treat it as validated). Neutralise
            # the verdicts to EXPLORATORY, blank validated_on, and keep the underlying reading +
            # stats under explicitly-exploratory keys so the analysis isn't lost.
            updates = {
                "status": "exploratory",
                "blocked": True,
                "verdict": "EXPLORATORY",
                "verdict_mt": "EXPLORATORY",
                "verdict_raw": _raw_verdict,         # underlying (exploratory) reading, for reference
                # BLANK the generic numeric fields too (Codex r8): a vault/LLM/query consumer
                # that ranks by lift/precision/q_value without re-checking `blocked` must not see
                # actionable-looking numbers. Keep the raw values under explicitly-exploratory keys.
                "lift": "", "precision": "", "q_value": "",
                "lift_exploratory": head.get("lift"),
                "precision_exploratory": head.get("precision"),
                "q_value_exploratory": head.get("q_value"),
                "validated_on": "",                  # never validated → blank, NOT a date
                "exploratory_on": validated_on,
            }
        else:
            updates = {
                "status": _STATUS.get(_raw_verdict, "seed"),
                "blocked": False,
                "verdict": head.get("verdict"),
                "verdict_mt": head.get("verdict_mt"),
                "verdict_raw": "",
                "lift": head.get("lift"),
                "precision": head.get("precision"),
                "q_value": head.get("q_value"),
                "lift_exploratory": "", "precision_exploratory": "", "q_value_exploratory": "",
                "validated_on": validated_on,
                "exploratory_on": "",
            }
        per_table = [{"label": lab, **per[lab]} for lab in order if lab in per]
        text = card.read_text(encoding="utf-8")
        text = _update_frontmatter(text, updates)
        text = _replace_section(text, "## 驗證紀錄",
                                _record_block(factor, per_table, blocked, universe,
                                              point_in_time, delisted_gap))
        card.write_text(text, encoding="utf-8")
        synced += 1

    print(f"[sync] {synced} factor card(s) updated from {Path(args.lift).name}"
          + (f" · blocked={blocked}" if blocked else ""))
    if missing:
        print(f"[sync] {len(missing)} lift factor(s) had no card (run knowledge_seed): "
              + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
