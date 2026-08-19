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

# Shared subscription-only Codex client (see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.04_build_report)
    from scripts.llm_client import LLMClient


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


def _confirmed_rows(dd_data: dict) -> list[dict]:
    if not isinstance(dd_data, dict):
        raise ValueError("DD data must be an object")
    rows = dd_data.get("confirmed", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("DD confirmed must be a list of objects")
    return rows


def validate_final_report(
    report: object,
    dd_data: dict,
    *,
    expected_report_date: str | None = None,
) -> dict:
    """Require the LLM report to be an exact projection of DD-confirmed picks."""
    if not isinstance(report, dict):
        raise ValueError("final report must be an object")
    if expected_report_date is not None and report.get("report_date") != expected_report_date:
        raise ValueError(
            f"report_date must match scan date {expected_report_date!r}"
        )
    confirmed = _confirmed_rows(dd_data)
    declared_confirmed_count = dd_data.get("confirmed_count", len(confirmed))
    if (not isinstance(declared_confirmed_count, int)
            or isinstance(declared_confirmed_count, bool)
            or declared_confirmed_count != len(confirmed)):
        raise ValueError("DD confirmed_count must equal the confirmed row count")
    confirmed_tickers = [str(row.get("ticker") or "").strip().upper() for row in confirmed]
    if any(not ticker for ticker in confirmed_tickers):
        raise ValueError("DD confirmed row is missing ticker")
    if len(set(confirmed_tickers)) != len(confirmed_tickers):
        raise ValueError("DD confirmed tickers must be unique")
    for row in confirmed:
        if row.get("dd_verdict") != "CONFIRMED":
            raise ValueError("DD confirmed collection contains a non-CONFIRMED row")
        score = row.get("final_score")
        if (not isinstance(score, (int, float)) or isinstance(score, bool)
                or not 0 <= score <= 100):
            raise ValueError("DD confirmed final_score must be numeric within 0..100")

    picks = report.get("ranked_picks")
    if not isinstance(picks, list) or any(not isinstance(row, dict) for row in picks):
        raise ValueError("ranked_picks must be a list of objects")
    pick_tickers = [str(row.get("ticker") or "").strip().upper() for row in picks]
    if any(not ticker for ticker in pick_tickers):
        raise ValueError("ranked pick is missing ticker")
    if len(set(pick_tickers)) != len(pick_tickers):
        raise ValueError("ranked picks must not contain duplicate tickers")
    if set(pick_tickers) != set(confirmed_tickers):
        raise ValueError(
            "ranked picks must exactly match DD confirmed tickers: "
            f"expected={sorted(confirmed_tickers)!r} actual={sorted(pick_tickers)!r}"
        )
    total = report.get("total_confirmed")
    if not isinstance(total, int) or isinstance(total, bool) or total != len(picks):
        raise ValueError("total_confirmed must equal the ranked-pick count")
    return report


def _rows_by_ticker(rows: object) -> dict[str, dict]:
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("ticker") or "").strip().upper(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def canonicalize_final_report(
    report: dict,
    dd_data: dict,
    layer2_data: dict | None = None,
    *,
    expected_report_date: str | None = None,
) -> dict:
    """Replace critical pick fields with their producer-owned source values."""
    validate_final_report(
        report,
        dd_data,
        expected_report_date=expected_report_date,
    )
    confirmed = _rows_by_ticker(_confirmed_rows(dd_data))
    layer2 = _rows_by_ticker(
        (layer2_data or {}).get("continue_to_dd", [])
        if isinstance(layer2_data, dict) else []
    )
    canonical_picks = []

    def source_value(dd_row: dict, layer2_row: dict, key: str, default=None):
        value = dd_row.get(key)
        if value is not None and value != "":
            return value
        value = layer2_row.get(key)
        return value if value is not None and value != "" else default

    ordered_confirmed = sorted(
        confirmed.items(),
        key=lambda item: (-float(item[1]["final_score"]), item[0]),
    )
    for rank, (ticker, dd_row) in enumerate(ordered_confirmed, start=1):
        layer2_row = layer2.get(ticker, {})
        canonical = {
            "rank": rank,
            "ticker": ticker,
            "final_score": dd_row.get("final_score", 0),
            "verdict": "BUY",
            "thesis": dd_row.get("final_recommendation", ""),
            "entry_zone": source_value(
                dd_row, layer2_row, "suggested_entry_zone", ""
            ),
            "stop_loss": source_value(dd_row, layer2_row, "suggested_stop", ""),
            "position_size_pct": source_value(
                dd_row, layer2_row, "suggested_size_pct"
            ),
            "key_risk": dd_row.get("short_thesis_summary", ""),
        }
        canonical_picks.append(canonical)
    canonical_report = dict(report)
    canonical_report["ranked_picks"] = canonical_picks
    canonical_report["total_confirmed"] = len(canonical_picks)
    return canonical_report


def build_deterministic_report(
    regime_context: dict,
    dd_data: dict,
    layer2_data: dict | None = None,
) -> dict:
    """Build a no-invention fallback directly from DD-confirmed source fields."""
    confirmed = _confirmed_rows(dd_data)
    ranked_picks = []
    for index, row in enumerate(confirmed, start=1):
        ranked_picks.append({
            "rank": index,
            "ticker": str(row.get("ticker") or "").strip().upper(),
            "final_score": row.get("final_score", 0),
            "verdict": "BUY",
            "thesis": row.get("final_recommendation", ""),
            "entry_zone": row.get("suggested_entry_zone", ""),
            "stop_loss": row.get("suggested_stop", ""),
            "position_size_pct": row.get("suggested_size_pct"),
            "key_risk": row.get("short_thesis_summary", ""),
        })
    report = {
        "report_date": regime_context.get("scan_date", ""),
        "regime_summary": f"VIX {regime_context.get('vix_level', '?')}",
        "total_confirmed": len(ranked_picks),
        "ranked_picks": ranked_picks,
        "cross_candidate_commentary": "",
        "portfolio_notes": "",
    }
    return canonicalize_final_report(
        report,
        dd_data,
        layer2_data,
        expected_report_date=str(regime_context.get("scan_date", "")),
    )


def build_final_report(llm: LLMClient, regime_context: dict,
                       scored_data: dict, layer2_data: dict,
                       dd_data: dict) -> dict:
    """Use LLM to generate the final consolidated report."""
    # Merge all confirmed picks
    confirmed = dd_data.get("confirmed", [])
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
    confirmed_allowlist = [str(row.get("ticker") or "").upper() for row in confirmed]

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

## Confirmed Ticker Allowlist
{json.dumps(confirmed_allowlist)}
Only these tickers may appear in `ranked_picks`; include each exactly once.

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
    parser.add_argument("--provider", default="codex", choices=["auto", "codex"])
    parser.add_argument("--model", default=None,
                        help="Optional Codex model; defaults to CODEX_MODEL/account setting")
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
        report = canonicalize_final_report(
            report,
            dd_data,
            layer2_data,
            expected_report_date=str(regime_context.get("scan_date", "")),
        )
    except Exception as e:
        print(f"[report] LLM report generation/validation failed: {e}", file=sys.stderr)
        report = build_deterministic_report(regime_context, dd_data, layer2_data)

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
