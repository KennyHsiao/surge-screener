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

    # Scope expands to Dim2/Dim4 once EDGAR backfill ran (8-K + insider buys).
    dims_present = {f.get("dimension") for f in all_table.get("factors", [])}
    edgar_on = bool({"Dim2", "Dim4"} & dims_present)
    scope_line = (
        "Dim1/Dim5 are from price history; Dim2 (8-K catalyst) + Dim4 (insider buying) "
        "were backfilled from SEC EDGAR and ARE in scope. Dim3 (sentiment) + Dim6 "
        "(options flow) remain out of scope (no free history — Phase 2 forward snapshots)."
        if edgar_on else
        "Only speak to Dim1/Dim5 (the other four dimensions are out of scope for this historical pass).")

    # Use the CANONICAL fail-closed gate (the same predicate report/modules/UI use),
    # so the prompt never tells the model "proposed_changes may be offered" on a run
    # the canonical gate considers blocked (e.g. survivorship-biased).
    coverage = lift.get("coverage", {})
    blocked = _is_blocked(lift)
    gate_line = (
        "*** RECOMMENDATIONS BLOCKED *** This run is a SAMPLE EXPERIMENT (coverage "
        f"{coverage.get('tickers_scanned')} / {coverage.get('intended_universe_size')} "
        "tickers). You MUST return an EMPTY proposed_changes array and set "
        "narrative_summary to state the evidence base is unrepresentative (sample "
        "coverage + survivorship bias) and NOT actionable for weight/prompt changes. "
        "You may still describe the observed lift, clearly labelled as exploratory."
        if blocked else
        "This run meets coverage; proposed_changes may be offered for HUMAN REVIEW.")

    return f"""Generate a surge-retrospective factor-validation report.

## Run scope
universe={events.get('universe')} lookback_days={events.get('lookback_days')}
tickers_scanned={events.get('tickers_scanned')} surge_events={events.get('event_count')}
control_points={lift.get('control_count')} control_design={lift.get('control_design')}
low_confidence={lift.get('low_confidence')} recommendations_blocked={blocked}
coverage={json.dumps(coverage)}
event_count_by_threshold={json.dumps(events.get('event_count_by_threshold', {}))}

## Coverage gate
{gate_line}

## Caveats from the pipeline (incorporate into the report)
{json.dumps(events.get('caveats', []), indent=2)}

## Combined factor-lift table (ALL surges, sorted by lift)
{json.dumps(_slim(all_table.get('factors', [])), indent=2)}

## Per-threshold factor-lift tables (to assess stability as the surge bar rises)
{json.dumps(per_threshold, indent=2)}

Follow the surge_retrospective skill. {scope_line} Respect support gates and the
coverage gate above. Note the control group is confirmation-trigger-matched
(failed +7% confirmations), so lift is the ex-ante edge among confirmed movers —
NOT "winners vs random". Surface coverage gaps as first-class findings.

Return ONLY a valid JSON object matching the skill's schema, then a short narrative."""


try:
    import retro_factor_lift as _rfl
    _is_blocked = _rfl.is_recommendations_blocked
except ImportError:  # pragma: no cover — fallback keeps the same fail-closed logic
    def _is_blocked(lift: dict) -> bool:
        return not (lift.get("recommendations_blocked") is False
                    and lift.get("low_confidence") is False
                    and lift.get("coverage", {}).get("sample_experiment") is False)


_BLOCKED_SUMMARY = (
    "```json\n" + json.dumps({
        "status": "BLOCKED",
        "reason": "non-representative / underpowered / survivorship-biased run — "
                  "findings are exploratory only and NOT actionable",
        "proposed_changes": [],
    }, indent=2) + "\n```\n\nThis run is gated: see the 因子驗證 tab for exploratory lift only."
)


def _sanitize_blocked(text: str):
    """On a blocked run, neutralise actionable content. Finds the report JSON whether
    it is ```json-fenced OR raw/unfenced, forces proposed_changes=[], and persists
    ONLY the sanitised JSON (dropping any free-form narrative that could carry advice).
    Returns None when no JSON object can be parsed — the caller then persists a fixed
    gate-only summary instead of raw LLM text."""
    import re
    blob = None
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        blob = m.group(1)
    else:                       # raw / unfenced: take the first {...} span
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        blob = m2.group(0) if m2 else None
    if blob is None:
        return None
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    obj["proposed_changes"] = []
    obj["_proposed_changes_suppressed"] = "blocked run — recommendations not actionable"
    return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False) + "\n```"


def _exploratory_ok(lift: dict) -> bool:
    """Exploratory LLM synthesis is allowed ONLY on a validated, well-formed run, not
    on the override BIT alone — else a stale/hand-edited artifact with
    exploratory_override:true + low_confidence:true could still invoke the LLM and
    render untrusted prose. Require the operator opt-in AND a representative + powered
    gate (low_confidence False, sample_experiment False) computed by a real
    coverage_gate (survivorship_bias present = True)."""
    cov = lift.get("coverage") or {}
    return (lift.get("exploratory_override") is True
            # must be canonically blocked AND self-report it (reject the inconsistent
            # recommendations_blocked=false + survivorship_bias=true artifact).
            and _is_blocked(lift) is True
            and lift.get("recommendations_blocked") is True
            and lift.get("low_confidence") is False
            and cov.get("sample_experiment") is False
            and cov.get("survivorship_bias") is True)


def build_report_text(lift: dict, synthesize) -> str:
    """Actionable recommendations are ALWAYS blocked (survivorship bias), so the LLM
    synthesis runs ONLY on a validated exploratory-override run — and even then its
    proposed_changes are stripped. Otherwise a deterministic gate summary is persisted
    (LLM not called, so no advice can leak through any field). `synthesize` is a 0-arg
    callable so it is never invoked unless _exploratory_ok holds."""
    if _exploratory_ok(lift):
        return _sanitize_blocked(synthesize()) or _BLOCKED_SUMMARY
    return _BLOCKED_SUMMARY


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

    # The LLM is an UNTRUSTED producer: on a blocked run it could embed actionable
    # advice in narrative_summary / coverage_gaps / factor readings, not just
    # proposed_changes. So a blocked run does NOT call the LLM at all and persists a
    # DETERMINISTIC gate-only report; the deterministic lift tables remain the only
    # (exploratory) evidence shown. Unblocked runs synthesize as before.
    blocked = _is_blocked(lift)

    def _synthesize() -> str:
        if args.no_llm:
            return ""
        print("[report] synthesizing via LLM ...")
        llm = LLMClient(provider=args.provider, model=args.model)
        return llm.chat(system=skill_prompt,
                        user=build_user_msg(events, lift), max_tokens=8192)

    report_text = build_report_text(lift, _synthesize)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Machine-readable bundle the dashboard reads (latest.json).
    latest = {
        "report_date": today,
        "universe": events.get("universe"),
        "lookback_days": events.get("lookback_days"),
        "surge_event_count": events.get("event_count"),
        "low_confidence": lift.get("low_confidence"),
        "recommendations_blocked": blocked,
        "exploratory_override": lift.get("exploratory_override") is True,
        "coverage": lift.get("coverage", {}),
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
