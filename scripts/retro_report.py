#!/usr/bin/env python3
"""Surge Retrospective — Stage D: LLM synthesis & recommendations.

Mirrors 08_self_reflection.py's structure (pre-compute stats → stuff JSON into a
user message → LLM returns a human-review report), but feeds the GROUND-TRUTH
factor-lift tables instead of the screener's own picks, and explicitly does NOT
import scipy (the .venv has none — 08's scipy import would crash here).

Turns the numeric lift tables into a report that names which Dim1/Dim5 sub-factors
are validated / noise / contrarian and proposes weight + prompt changes mapped back
to system_prompts/01_surge_screener_prompt.md — all for human review, never
auto-applied (matches the system's read-only / human-decides philosophy).

CLI:
    python scripts/retro_report.py --provider auto
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "retrospective"
sys.path.insert(0, str(REPO / "scripts"))

try:
    from llm_client import LLMClient
except ImportError:  # package context
    from scripts.llm_client import LLMClient


def build_user_msg(events: dict, lift: dict) -> str:
    """Compact the lift tables + event summary into the synthesis prompt."""
    all_table = lift["tables"].get("ALL", {})
    # Trim each factor row to the fields the model needs to reason.
    def _slim(factors):
        return [{k: f[k] for k in (
            "factor", "dimension", "subfactor", "desc", "p_surge", "p_control",
            "lift", "lift_ci90", "precision_lift", "support", "verdict")}
            for f in factors]

    per_threshold = {label: _slim(tbl["factors"])
                     for label, tbl in lift["tables"].items() if label != "ALL"}

    return f"""Generate a surge-retrospective factor-validation report.

## Run scope
universe={events.get('universe')} lookback_days={events.get('lookback_days')}
tickers_scanned={events.get('tickers_scanned')} surge_events={events.get('event_count')}
control_points={lift.get('control_count')} low_confidence={lift.get('low_confidence')}
event_count_by_threshold={json.dumps(events.get('event_count_by_threshold', {}))}

## Caveats from the pipeline (incorporate into the report)
{json.dumps(events.get('caveats', []), indent=2)}

## Combined factor-lift table (ALL surges, sorted by lift)
{json.dumps(_slim(all_table.get('factors', [])), indent=2)}

## Per-threshold factor-lift tables (to assess stability as the surge bar rises)
{json.dumps(per_threshold, indent=2)}

Follow the surge_retrospective skill. Only speak to Dim1/Dim5 (the other four
dimensions are out of scope for this historical pass). Respect support gates.
Surface coverage gaps as first-class findings.

Return ONLY a valid JSON object matching the skill's schema, then a short narrative."""


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — LLM report")
    ap.add_argument("--skill", default=str(REPO / "skills" / "08_surge_retrospective_skill.md"))
    ap.add_argument("--events", default=str(OUT_DIR / "surge_events.json"))
    ap.add_argument("--lift", default=str(OUT_DIR / "factor_lift.json"))
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--no-llm", action="store_true",
                    help="write the latest.json bundle without calling the LLM")
    args = ap.parse_args()

    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    lift = json.loads(Path(args.lift).read_text(encoding="utf-8"))
    skill_prompt = Path(args.skill).read_text(encoding="utf-8")

    report_text = ""
    if not args.no_llm:
        print("[report] synthesizing via LLM ...")
        llm = LLMClient(provider=args.provider, model=args.model)
        report_text = llm.chat(system=skill_prompt,
                               user=build_user_msg(events, lift), max_tokens=8192)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Machine-readable bundle the dashboard reads (latest.json).
    latest = {
        "report_date": today,
        "universe": events.get("universe"),
        "lookback_days": events.get("lookback_days"),
        "surge_event_count": events.get("event_count"),
        "low_confidence": lift.get("low_confidence"),
        "llm_report": report_text,
        "lift_tables": lift.get("tables", {}),
    }
    (OUT_DIR / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

    # Human-readable markdown.
    md = (
        f"# 暴漲股復盤 — Surge Retrospective ({today})\n\n"
        f"Universe: {events.get('universe')} · Lookback: {events.get('lookback_days')}d · "
        f"Surge events: {events.get('event_count')} · "
        f"Controls: {lift.get('control_count')} · "
        f"Low-confidence: {lift.get('low_confidence')}\n\n"
        f"> Scope: only **Dim1 (Technical) + Dim5 (Sector/Market)** validated here. "
        f"Recommendations are **for human review — never auto-applied.**\n\n"
        f"## Pre-computed combined lift table\n\n"
        f"```json\n{json.dumps([{k: f[k] for k in ('factor','subfactor','lift','support','verdict')} for f in lift['tables'].get('ALL', {}).get('factors', [])], indent=2)}\n```\n\n"
        f"---\n\n## LLM synthesis\n\n{report_text or '(skipped — run without --no-llm)'}\n"
    )
    md_path = OUT_DIR / f"{today}_retro.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"[report] → {md_path} + latest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
