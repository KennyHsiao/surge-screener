#!/usr/bin/env python3
"""
Stage 2.5 — Engine Controller (Layer 2, DEoT routing)
For each candidate flagged NEEDS_LAYER_2:
  - Engine Controller decides BREADTH / DEPTH / TERMINATE
  - Execute the chosen action (additional LLM call)
  - Loop max 2 layers, max 6 nodes per candidate
  - Track Effective Reasoning Information Rate (ERIR)
Outputs layer2_results.json — tree-structured analysis per candidate.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Shared subscription-only Codex client (see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.025_engine_controller)
    from scripts.llm_client import LLMClient


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines)
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end])
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("No JSON found")
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace_start : i + 1])
    raise ValueError("Malformed JSON")


# ---------------------------------------------------------------------------
# Engine Controller Decision
# ---------------------------------------------------------------------------

def make_controller_decision(llm: LLMClient, controller_prompt: str,
                             candidate: dict, layer: int,
                             previous_nodes: list[dict]) -> dict:
    """Ask the Engine Controller to decide BREADTH / DEPTH / TERMINATE."""
    scores = candidate.get("scores", {})
    prev_summary = ""
    if previous_nodes:
        prev_summary = "\n".join(
            f"Layer {n['layer']}: {n['decision']} — {n.get('summary', '')}"
            for n in previous_nodes
        )

    user_msg = f"""## Candidate for Engine Controller Decision

Ticker: {candidate['ticker']}
Current Layer: {layer}
Composite Score: {candidate.get('composite_score', 0)}
Regime Adjusted Score: {candidate.get('regime_adjusted_score', 0)}

Dimension Scores:
- Technical: {scores.get('technical', 0)}/30
- Catalyst: {scores.get('catalyst', 0)}/16
- Sentiment: {scores.get('sentiment', 0)}/13
- Institutional: {scores.get('institutional', 0)}/10
- Sector/Market: {scores.get('sector_market', 0)}/3
- Options Flow: {scores.get('options_flow', 0)}/20
- Analyst Consensus: {scores.get('analyst', 0)}/8

Key Signals: {json.dumps(candidate.get('key_signals', []))}
Key Risks: {json.dumps(candidate.get('key_risks', []))}
Pattern Type: {candidate.get('technical_breakdown', {}).get('pattern_type', 'unknown')}
MACD State: {candidate.get('technical_breakdown', {}).get('macd_state', 'unknown')}

Previous Analysis Nodes:
{prev_summary if prev_summary else "None — this is the first decision."}

Based on the Engine Controller decision framework, decide: BREADTH, DEPTH, or TERMINATE.

Return ONLY a valid JSON object:
{{
  "ticker": "{candidate['ticker']}",
  "current_layer": {layer},
  "decision": "DEPTH | BREADTH | TERMINATE",
  "reasoning": "<string>",
  "action_spec": {{
    "type": "depth | breadth",
    "target_dimensions": ["<dim>", ...],
    "questions": ["<question>", ...]
  }},
  "expected_information_gain": "<string>",
  "termination_reason": null
}}

For TERMINATE, set action_spec to null and provide termination_reason as one of:
ERIR_LOW, LAYER_MAX, SIGNAL_CONCLUSIVE, SIGNAL_REJECTED"""

    resp = llm.chat(system=controller_prompt, user=user_msg, max_tokens=4096)
    return _extract_json(resp)


def execute_action(llm: LLMClient, candidate: dict, decision: dict,
                   regime_context: dict) -> dict:
    """Execute the BREADTH or DEPTH action decided by the controller."""
    action = decision.get("action_spec")
    if not action:
        return {"summary": "TERMINATED", "new_findings": []}

    action_type = action.get("type", "breadth")
    questions = action.get("questions", action.get("aspects", []))

    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        q_text = "\n".join(
            f"- {q.get('question', q.get('name', str(q)))}" for q in questions
        )
    else:
        q_text = "\n".join(f"- {q}" for q in questions)

    user_msg = f"""Perform a {action_type.upper()} analysis for {candidate['ticker']}.

## Current Scores
{json.dumps(candidate.get('scores', {}), indent=2)}

## Regime Context
{json.dumps(regime_context, indent=2)}

## Questions to Investigate
{q_text}

Investigate these questions and return ONLY a valid JSON object:
{{
  "ticker": "{candidate['ticker']}",
  "action_type": "{action_type}",
  "findings": [
    {{
      "question": "<original question>",
      "answer": "<your finding>",
      "impact_on_verdict": "POSITIVE | NEGATIVE | NEUTRAL",
      "score_adjustment": {{"dimension": "<dim>", "delta": <int>}}
    }}
  ],
  "summary": "<1-2 sentence summary of new information found>",
  "erir_assessment": "HIGH | MEDIUM | LOW",
  "recommended_next": "CONTINUE | TERMINATE",
  "updated_verdict": "NEEDS_LAYER_2 | WATCHLIST | REJECT"
}}"""

    system = (
        "You are a senior equity analyst performing deep investigation. "
        "Be specific and factual. If you cannot verify a claim, say so."
    )

    resp = llm.chat(system=system, user=user_msg, max_tokens=4096)
    return _extract_json(resp)


# ---------------------------------------------------------------------------
# Main loop per candidate
# ---------------------------------------------------------------------------

def process_candidate(llm: LLMClient, controller_prompt: str,
                      candidate: dict, regime_context: dict,
                      max_layers: int = 2, max_nodes: int = 6) -> dict:
    """Run the Engine Controller loop for a single candidate."""
    nodes = []
    total_nodes = 0
    current_candidate = dict(candidate)

    for layer in range(1, max_layers + 1):
        if total_nodes >= max_nodes:
            nodes.append({
                "layer": layer,
                "decision": "TERMINATE",
                "termination_reason": "NODE_BUDGET_EXHAUSTED",
                "summary": f"Reached {max_nodes} node limit",
            })
            break

        # Ask controller for decision
        try:
            decision = make_controller_decision(
                llm, controller_prompt, current_candidate, layer, nodes
            )
        except Exception as e:
            print(f"  [engine] Controller error for {candidate['ticker']}: {e}",
                  file=sys.stderr)
            decision = {
                "decision": "TERMINATE",
                "termination_reason": "ERROR",
                "reasoning": str(e),
            }

        nodes.append({
            "layer": layer,
            "decision": decision.get("decision", "TERMINATE"),
            "reasoning": decision.get("reasoning", ""),
            "action_spec": decision.get("action_spec"),
            "termination_reason": decision.get("termination_reason"),
        })
        total_nodes += 1

        if decision.get("decision") == "TERMINATE":
            break

        # Execute the action
        try:
            action_result = execute_action(llm, current_candidate, decision,
                                           regime_context)
            nodes[-1]["action_result"] = action_result
            nodes[-1]["summary"] = action_result.get("summary", "")
            total_nodes += 1

            # Apply score adjustments
            for finding in action_result.get("findings", []):
                adj = finding.get("score_adjustment", {})
                dim = adj.get("dimension", "")
                delta = adj.get("delta", 0)
                if dim and delta and "scores" in current_candidate:
                    old = current_candidate["scores"].get(dim, 0)
                    current_candidate["scores"][dim] = max(0, old + delta)

            # Recalculate composite
            if "scores" in current_candidate:
                current_candidate["composite_score"] = sum(
                    current_candidate["scores"].values()
                )
                mult = regime_context.get("global_score_multiplier", 1.0)
                current_candidate["regime_adjusted_score"] = round(
                    current_candidate["composite_score"] * mult, 1
                )

            # Check ERIR
            erir = action_result.get("erir_assessment", "LOW")
            if erir == "LOW":
                nodes.append({
                    "layer": layer,
                    "decision": "TERMINATE",
                    "termination_reason": "ERIR_LOW",
                    "summary": "Low information gain — stopping",
                })
                total_nodes += 1
                break

        except Exception as e:
            print(f"  [engine] Action error for {candidate['ticker']}: {e}",
                  file=sys.stderr)
            nodes[-1]["action_error"] = str(e)

        # Rate limiting
        time.sleep(0.5)

    # Determine final verdict
    final_score = current_candidate.get("regime_adjusted_score",
                                        candidate.get("regime_adjusted_score", 0))
    if final_score >= 65:
        final_verdict = "CONTINUE_TO_DD"
    elif final_score >= 50:
        final_verdict = "WATCHLIST"
    else:
        final_verdict = "REJECT"

    # Check if any node explicitly rejected
    for n in nodes:
        ar = n.get("action_result", {})
        if ar.get("updated_verdict") == "REJECT":
            final_verdict = "REJECT"
            break

    return {
        "ticker": candidate["ticker"],
        "original_score": candidate.get("composite_score", 0),
        "original_adjusted_score": candidate.get("regime_adjusted_score", 0),
        "final_score": current_candidate.get("composite_score", 0),
        "final_adjusted_score": final_score,
        "final_verdict": final_verdict,
        "scores": current_candidate.get("scores", candidate.get("scores", {})),
        "layer2_path": " → ".join(n.get("decision", "?") for n in nodes),
        "analysis_tree": nodes,
        "total_nodes": total_nodes,
        "key_signals": current_candidate.get("key_signals",
                                             candidate.get("key_signals", [])),
        "key_risks": current_candidate.get("key_risks",
                                           candidate.get("key_risks", [])),
        "suggested_entry_zone": candidate.get("suggested_entry_zone"),
        "suggested_stop": candidate.get("suggested_stop"),
        "suggested_size_pct": candidate.get("suggested_size_pct"),
        "technical_breakdown": candidate.get("technical_breakdown", {}),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage 2.5: Engine Controller")
    parser.add_argument("--input", required=True, help="scored_candidates.json")
    parser.add_argument("--controller-prompt", required=True,
                        help="Path to engine controller prompt .md")
    parser.add_argument("--max-layers", type=int, default=2)
    parser.add_argument("--max-nodes-per-candidate", type=int, default=6)
    parser.add_argument("--provider", default="codex", choices=["auto", "codex"])
    parser.add_argument("--model", default=None,
                        help="Optional Codex model; defaults to CODEX_MODEL/account setting")
    parser.add_argument("--output", default="layer2_results.json")
    args = parser.parse_args()

    with open(args.input) as f:
        scored_data = json.load(f)

    controller_prompt = Path(args.controller_prompt).read_text(encoding="utf-8")
    llm = LLMClient(provider=args.provider, model=args.model)

    regime_context = scored_data.get("regime_context", {})
    candidates = scored_data.get("needs_layer2", [])

    print(f"[engine] Processing {len(candidates)} candidates through Engine Controller ...")

    results = []
    for i, cand in enumerate(candidates):
        ticker = cand["ticker"]
        print(f"  [{i+1}/{len(candidates)}] {ticker} "
              f"(score={cand.get('regime_adjusted_score', 0)}) ...")

        result = process_candidate(
            llm, controller_prompt, cand, regime_context,
            max_layers=args.max_layers, max_nodes=args.max_nodes_per_candidate,
        )
        results.append(result)
        print(f"    → {result['final_verdict']} "
              f"(path: {result['layer2_path']}, nodes: {result['total_nodes']})")

    # Separate by verdict
    continue_dd = [r for r in results if r["final_verdict"] == "CONTINUE_TO_DD"]
    watchlist = [r for r in results if r["final_verdict"] == "WATCHLIST"]
    rejected = [r for r in results if r["final_verdict"] == "REJECT"]

    output = {
        "scan_date": regime_context.get("scan_date", ""),
        "regime_context": regime_context,
        "input_count": len(candidates),
        "continue_to_dd_count": len(continue_dd),
        "watchlist_count": len(watchlist),
        "rejected_count": len(rejected),
        "continue_to_dd": continue_dd,
        "watchlist": watchlist,
        "rejected": rejected,
        "all_results": results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[engine] Done: {len(continue_dd)} → DD, "
          f"{len(watchlist)} WATCHLIST, {len(rejected)} REJECT → {args.output}")


if __name__ == "__main__":
    main()
