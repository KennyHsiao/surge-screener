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


def _universe_mismatch(lift: dict, events: dict):
    """Return (lift_universe, events_universe) when they DISAGREE — fail-closed on ANY
    asymmetry, including one side missing the field — else None. Equal-and-both-absent
    (legacy↔legacy) passes. PURE / unit-testable (adversarial review: the old guard
    short-circuited on a falsy universe, letting a field-less artifact slip past)."""
    lu = (lift.get("coverage") or {}).get("universe") or lift.get("universe")
    eu = events.get("universe")
    return (lu, eu) if lu != eu else None


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
except ImportError:  # pragma: no cover — if the canonical gate can't be imported we
    # cannot validate the run, so fail CLOSED: treat every run as blocked.
    def _is_blocked(lift: dict) -> bool:
        return True


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
    """Branch on the canonical gate (Codex C-1 review #4 — keep the report body consistent
    with recommendations_blocked):
      * gate OPEN (legitimately unblocked: point-in-time, not stale, no delisted gap, powered)
        → run the FULL synthesis and let proposed_changes through for human review.
      * gate BLOCKED + validated exploratory-override → LLM runs but proposed_changes stripped.
      * gate BLOCKED otherwise → deterministic blocked summary, LLM never called.
    `synthesize` is a 0-arg callable, invoked only in the first two cases."""
    if not _is_blocked(lift):
        return synthesize() or _BLOCKED_SUMMARY
    if _exploratory_ok(lift):
        return _sanitize_blocked(synthesize()) or _BLOCKED_SUMMARY
    return _BLOCKED_SUMMARY


def main() -> int:
    ap = argparse.ArgumentParser(description="Surge Retrospective — LLM report")
    ap.add_argument("--skill", default=str(REPO / "skills" / "08_surge_retrospective_skill.md"))
    ap.add_argument("--events", default=None,
                    help="surge_events.json; default = sibling of --lift (same dataset dir)")
    ap.add_argument("--lift", default=str(OUT_DIR / "factor_lift.json"))
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--no-llm", action="store_true",
                    help="write the latest.json bundle without calling the LLM")
    args = ap.parse_args()

    lift_path = Path(args.lift)
    # Derive the events file from the SAME dataset dir as --lift unless explicitly
    # overridden, so a caller that points --lift at reports/retrospective/sp500_pit/ can't
    # accidentally pair a dataset's lift with the ROOT surge_events.json — that would stamp
    # latest.json with the wrong universe / event_count (Codex C-1 r3 path-regression hint).
    events_path = Path(args.events) if args.events else lift_path.parent / "surge_events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    lift = json.loads(lift_path.read_text(encoding="utf-8"))
    # Fail-closed consistency guard: the lift's recorded universe must match the events it is
    # reported against. A mismatch means the dataset wiring is wrong; refuse rather than emit a
    # mislabelled report (the dashboard trusts latest.json's universe/event_count verbatim).
    mismatch = _universe_mismatch(lift, events)
    if mismatch is not None:
        raise SystemExit(
            f"[report] dataset mismatch: lift universe={mismatch[0]!r} but "
            f"events universe={mismatch[1]!r} ({events_path}). "
            "Pass --events and --lift from the same dataset dir.")
    # Same-universe is NOT enough (Codex review): a STALE factor_lift from the same universe
    # paired with a FRESH surge_events would stamp latest.json with event_count/universe from
    # one run and lift_tables from another. Require the lift to descend from THESE events.
    try:
        import retro_factor_lift as _rfl
        _rfl.assert_same_run("report", events.get("generated_at"), factor_lift=lift)
    except ImportError:  # pragma: no cover — without the canonical helper, fail closed
        raise SystemExit("[report] cannot import retro_factor_lift to verify provenance — "
                         "refusing (fail-closed).")
    # Events-adjacency is NOT enough (Codex r9): surge_features can be REBUILT under the same
    # events (EDGAR backfill bumps surge_features.generated_at), so a rerun that refreshes
    # surge_features but leaves factor_lift stale would still publish latest.json from obsolete
    # lift tables. Require the lift to descend from the CURRENT surge_features too.
    _features_path = lift_path.parent / "surge_features.json"
    if not _features_path.exists():
        raise SystemExit(f"[report] no {_features_path} to verify the lift's features-adjacency "
                         "— refusing (fail-closed).")
    _sf_gen = json.loads(_features_path.read_text(encoding="utf-8")).get("generated_at")
    _rfl.assert_features_fresh("report", _sf_gen, factor_lift=lift)
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
        # Same-run fingerprint (Codex round-4): the UI-facing bundle (llm_report + lift_tables)
        # must be artifact-testable for same-run consistency, like every other hop — so a stale
        # latest.json can be detected instead of silently rendered.
        "source": {
            "events_generated_at": events.get("generated_at"),
            "factor_lift_generated_at": lift.get("generated_at"),
        },
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
    # Write where the dataset lives (e.g. reports/retrospective/sp500_pit/) so the UI's
    # dataset switch finds the matching latest.json — not always the root (Codex #3).
    out_dir = Path(args.lift).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

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
    md_path = out_dir / f"{today}_retro.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"[report] → {md_path} + {out_dir / 'latest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
