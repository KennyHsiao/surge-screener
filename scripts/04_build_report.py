#!/usr/bin/env python3
"""
Stage 4 — Final Response Agent (Layer 4) + Report Generation
Consolidates Layer 0/1/2/3 outputs into:
  - Ranked final picks with reasoning trees
  - Suggested entry/stop/size per pick
  - Cross-candidate market commentary
Writes reports/YYYY-MM-DD/ folder with summary.md, summary.json, full.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic


class LLMClient:
    def __init__(self, provider: str = "anthropic", model: str = "claude-opus-4-7"):
        self.provider = provider
        self.model = model
        if provider == "anthropic":
            self.client = anthropic.Anthropic()

    def chat(self, system: str, user: str, max_tokens: int = 8192) -> str:
        if self.provider == "anthropic":
            msg = self.client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text
        raise NotImplementedError(f"Provider {self.provider} not implemented here")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("```"):
                text = "\n".join(lines[1:i])
                break
    brace = text.find("{")
    if brace == -1:
        raise ValueError("No JSON found")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace : i + 1])
    raise ValueError("Malformed JSON")


def _build_layer2_summary(layer2_data: dict) -> list[dict]:
    return [
        {
            "ticker": r["ticker"],
            "path": r.get("layer2_path", ""),
            "final_score": r.get("final_adjusted_score", 0),
            "key_signals": r.get("key_signals", []),
            "key_risks": r.get("key_risks", []),
            "entry": r.get("suggested_entry_zone"),
            "stop": r.get("suggested_stop"),
            "size": r.get("suggested_size_pct"),
        }
        for r in layer2_data.get("continue_to_dd", [])
    ]


def build_final_report(llm: LLMClient, regime_context: dict,
                       scored_data: dict, layer2_data: dict,
                       dd_data: dict) -> dict:
    """Use LLM to generate the final consolidated report."""
    # Merge all confirmed picks
    confirmed = dd_data.get("confirmed", [])
    downgraded = dd_data.get("downgraded", [])

    # Build concise summaries for the LLM
    picks_summary = []
    for pick in confirmed:
        picks_summary.append({
            "ticker": pick["ticker"],
            "dd_verdict": "CONFIRMED",
            "final_score": pick.get("final_score", 0),
            "short_thesis": pick.get("short_thesis_summary", ""),
            "recommendation": pick.get("final_recommendation", ""),
        })
    for pick in downgraded:
        picks_summary.append({
            "ticker": pick["ticker"],
            "dd_verdict": "DOWNGRADED",
            "final_score": pick.get("final_score", 0),
            "short_thesis": pick.get("short_thesis_summary", ""),
        })

    user_msg = f"""Generate the final daily surge screener report.

## Regime Context
{json.dumps(regime_context, indent=2)}

## Pipeline Statistics
- Universe scanned: {scored_data.get('universe_size', 0)}
- Passed hard filters: {scored_data.get('passed_hard_filters', 0)}
- Passed Layer 1 (>=65): {scored_data.get('needs_layer2_count', 0)}
- Passed Layer 2 (Engine Controller): {layer2_data.get('continue_to_dd_count', 0)}
- Confirmed by DD: {dd_data.get('confirmed_count', 0)}
- Downgraded by DD: {dd_data.get('downgraded_count', 0)}

## Confirmed Picks (DD passed)
{json.dumps(picks_summary, indent=2, default=str)}

## Layer 2 Analysis Trees
{json.dumps(_build_layer2_summary(layer2_data), indent=2, default=str)}

Generate a final ranking of CONFIRMED picks with:
1. Final rank and score
2. 2-3 sentence thesis summary
3. Entry zone, stop loss, position size
4. Cross-candidate commentary (are these picks correlated? theme overlap?)

Return ONLY a valid JSON object:
{{
  "report_date": "{regime_context.get('scan_date', '')}",
  "regime_summary": "<1 sentence>",
  "total_confirmed": <int>,
  "ranked_picks": [
    {{
      "rank": 1,
      "ticker": "<str>",
      "final_score": <int>,
      "verdict": "STRONG_BUY | BUY | WATCHLIST",
      "thesis": "<2-3 sentences>",
      "entry_zone": "<str>",
      "stop_loss": "<str>",
      "position_size_pct": <float>,
      "key_risk": "<str>"
    }}
  ],
  "cross_candidate_commentary": "<str>",
  "portfolio_notes": "<str — correlation warnings, concentration risk, etc.>"
}}"""

    system = (
        "You are the Final Response Agent for a US stock surge screener. "
        "Consolidate multi-layer analysis into an actionable, ranked report. "
        "Be direct and concise. This is signal generation, not investment advice."
    )

    resp = llm.chat(system=system, user=user_msg, max_tokens=6144)
    return _extract_json(resp)


def generate_summary_markdown(report: dict, regime_context: dict,
                              scored_data: dict, layer2_data: dict,
                              dd_data: dict) -> str:
    """Generate the Telegram-friendly markdown summary."""
    scan_date = report.get("report_date", "")
    vix = regime_context.get("vix_level", "?")
    mult = regime_context.get("global_score_multiplier", 1.0)
    spy50 = regime_context.get("spy_vs_50dma", "?")
    themes = ", ".join(regime_context.get("active_themes", [])[:3])

    lines = [
        f"# {scan_date} US Surge Screener Report (DEoT v3.2)",
        "",
        "## Regime",
        f"- SPY vs 50DMA: {spy50} | VIX: {vix} | Multiplier: {mult}",
        f"- Themes: {themes}",
        "",
        "## Pipeline",
        f"- Universe: {scored_data.get('universe_size', '?')}",
        f"- Hard filter passed: {scored_data.get('passed_hard_filters', '?')}",
        f"- Layer 1 passed: {scored_data.get('needs_layer2_count', '?')}",
        f"- Layer 2 passed: {layer2_data.get('continue_to_dd_count', '?')}",
        f"- DD confirmed: {dd_data.get('confirmed_count', '?')}",
        "",
        "## Ranked Picks",
        "",
    ]

    for pick in report.get("ranked_picks", []):
        rank = pick.get("rank", "?")
        ticker = pick.get("ticker", "?")
        score = pick.get("final_score", "?")
        verdict = pick.get("verdict", "?")
        thesis = pick.get("thesis", "")
        entry = pick.get("entry_zone", "?")
        stop = pick.get("stop_loss", "?")
        size = pick.get("position_size_pct", "?")
        risk = pick.get("key_risk", "")

        lines.extend([
            f"### #{rank} ${ticker} — {score} pts — {verdict}",
            f"**Thesis:** {thesis}",
            f"- Entry: {entry} | Stop: {stop} | Size: {size}%",
            f"- Key risk: {risk}",
            "",
        ])

    commentary = report.get("cross_candidate_commentary", "")
    if commentary:
        lines.extend(["## Commentary", commentary, ""])

    notes = report.get("portfolio_notes", "")
    if notes:
        lines.extend(["## Portfolio Notes", notes, ""])

    lines.append("---")
    lines.append("*Signal generation only. Not investment advice.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Stage 4: Build Report")
    parser.add_argument("--regime", help="layer2_results.json (for regime context)")
    parser.add_argument("--screener", required=True, help="scored_candidates.json")
    parser.add_argument("--layer2", required=True, help="layer2_results.json")
    parser.add_argument("--dd", required=True, help="dd_results.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--model", default="claude-opus-4-7")
    args = parser.parse_args()

    # Load all inputs
    with open(args.screener) as f:
        scored_data = json.load(f)
    with open(args.layer2) as f:
        layer2_data = json.load(f)

    dd_data = {"confirmed": [], "downgraded": [], "rejected": [],
               "confirmed_count": 0, "downgraded_count": 0, "rejected_count": 0}
    if os.path.exists(args.dd):
        with open(args.dd) as f:
            dd_data = json.load(f)

    regime_context = layer2_data.get("regime_context",
                                     scored_data.get("regime_context", {}))

    # Create output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate final report via LLM
    print("[report] Generating final report (Layer 4) ...")
    llm = LLMClient(provider=args.provider, model=args.model)

    try:
        report = build_final_report(llm, regime_context, scored_data,
                                    layer2_data, dd_data)
    except Exception as e:
        print(f"[report] LLM report generation failed: {e}", file=sys.stderr)
        # Fallback: build report from raw data
        confirmed = dd_data.get("confirmed", [])
        report = {
            "report_date": regime_context.get("scan_date", ""),
            "regime_summary": f"VIX {regime_context.get('vix_level', '?')}",
            "total_confirmed": len(confirmed),
            "ranked_picks": [
                {
                    "rank": i + 1,
                    "ticker": c["ticker"],
                    "final_score": c.get("final_score", 0),
                    "verdict": "BUY" if c.get("dd_verdict") == "CONFIRMED" else "WATCHLIST",
                    "thesis": c.get("final_recommendation", ""),
                    "entry_zone": "See layer2 data",
                    "stop_loss": "See layer2 data",
                    "position_size_pct": 2.0,
                    "key_risk": c.get("short_thesis_summary", ""),
                }
                for i, c in enumerate(confirmed)
            ],
            "cross_candidate_commentary": "",
            "portfolio_notes": "",
        }

    # Generate markdown summary
    summary_md = generate_summary_markdown(report, regime_context,
                                           scored_data, layer2_data, dd_data)

    # Write outputs
    with open(out_dir / "summary.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    with open(out_dir / "summary.md", "w") as f:
        f.write(summary_md)

    # Full data dump for backtesting
    full_data = {
        "regime_context": regime_context,
        "scored_data": scored_data,
        "layer2_data": layer2_data,
        "dd_data": dd_data,
        "final_report": report,
    }
    with open(out_dir / "full.json", "w") as f:
        json.dump(full_data, f, indent=2, default=str)

    print(f"[report] Done → {out_dir}/")
    print(f"  summary.json: {len(report.get('ranked_picks', []))} ranked picks")
    print(f"  summary.md: Telegram-ready markdown")
    print(f"  full.json: Complete data dump")


if __name__ == "__main__":
    main()
