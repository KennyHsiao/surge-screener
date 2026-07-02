#!/usr/bin/env python3
"""
Stage 8 — Monthly Self-Reflection
Loads the self-reflection skill, reads performance_ledger.csv for last 30/60/90 days,
computes baseline metrics, dimension predictive power, and asks LLM to synthesize
a reflection report with recommended prompt changes.
Outputs reports/reflections/YYYY-MM.md.
"""

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Shared LLM client (claude_agent / anthropic / openai / deepseek; see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.08_self_reflection)
    from scripts.llm_client import LLMClient


def load_ledger(ledger_path: str, lookback_days: int) -> pd.DataFrame:
    """Load ledger CSV and filter to lookback window."""
    df = pd.read_csv(ledger_path)
    df["scan_date"] = pd.to_datetime(df["scan_date"])

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    df = df[df["scan_date"] >= cutoff].copy()

    # Convert numeric columns
    numeric_cols = [
        "composite_score", "tech_score", "catalyst_score", "sentiment_score",
        "inst_score", "sector_score", "options_score", "analyst_score",
        "fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
        "fwd_30d_return", "fwd_60d_return", "max_drawdown_30d",
        "suggested_size_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def compute_baseline_metrics(df: pd.DataFrame) -> dict:
    """Step 1: Compute baseline hit rates and return metrics."""
    total = len(df)
    if total == 0:
        return {"total_picks": 0, "error": "No data in lookback window"}

    metrics = {"total_picks": total}

    # Hit rates
    if "hit_15pct_within_30d" in df.columns:
        hits_15 = df["hit_15pct_within_30d"].apply(
            lambda x: str(x).lower() == "true"
        )
        metrics["hit_15pct_30d_rate"] = round(hits_15.mean(), 3)

    if "hit_30pct_within_60d" in df.columns:
        hits_30 = df["hit_30pct_within_60d"].apply(
            lambda x: str(x).lower() == "true"
        )
        metrics["hit_30pct_60d_rate"] = round(hits_30.mean(), 3)

    # Average forward returns
    for col in ["fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
                "fwd_30d_return", "fwd_60d_return"]:
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                metrics[f"avg_{col}"] = round(valid.mean(), 2)
                metrics[f"median_{col}"] = round(valid.median(), 2)

    # Max drawdown stats
    if "max_drawdown_30d" in df.columns:
        dd = df["max_drawdown_30d"].dropna()
        if len(dd) > 0:
            metrics["avg_max_drawdown_30d"] = round(dd.mean(), 2)

    # Hit rate by score band
    if "composite_score" in df.columns and "fwd_30d_return" in df.columns:
        bands = {}
        for low, high, label in [(65, 69, "65-69"), (70, 74, "70-74"),
                                  (75, 79, "75-79"), (80, 84, "80-84"),
                                  (85, 100, "85+")]:
            band_df = df[(df["composite_score"] >= low) &
                         (df["composite_score"] <= high)]
            if len(band_df) > 0:
                avg_ret = band_df["fwd_30d_return"].dropna().mean()
                bands[label] = {
                    "count": len(band_df),
                    "avg_30d_return": round(avg_ret, 2) if not np.isnan(avg_ret) else None,
                }
        metrics["score_bands"] = bands

    return metrics


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _spearmanr(x: pd.Series, y: pd.Series) -> tuple[float, float | None]:
    """Return Spearman rank correlation and an approximate two-sided p-value."""
    ranks = pd.DataFrame({
        "x": x.rank(method="average"),
        "y": y.rank(method="average"),
    })
    corr = ranks["x"].corr(ranks["y"])
    if pd.isna(corr):
        return (float("nan"), None)

    corr = float(corr)
    n = len(ranks)
    if n <= 2:
        return (corr, None)
    if abs(corr) >= 1.0:
        return (corr, 0.0)

    # Normal approximation is sufficient for the report's directional audit.
    t_stat = corr * math.sqrt((n - 2) / max(1e-12, 1 - corr * corr))
    pval = 2 * (1 - _normal_cdf(abs(t_stat)))
    return (corr, pval)


def compute_dimension_correlations(df: pd.DataFrame) -> list[dict]:
    """Step 2: Compute Spearman correlation of each dimension vs 30d return."""
    dim_cols = {
        "technical": "tech_score",
        "catalyst": "catalyst_score",
        "sentiment": "sentiment_score",
        "institutional": "inst_score",
        "sector_market": "sector_score",
        "options_flow": "options_score",
        "analyst": "analyst_score",
    }

    results = []
    fwd_col = "fwd_30d_return"

    if fwd_col not in df.columns:
        return results

    for dim_name, col_name in dim_cols.items():
        if col_name not in df.columns:
            continue

        valid = df[[col_name, fwd_col]].dropna()
        if len(valid) < 5:
            results.append({
                "dimension": dim_name,
                "avg_score": None,
                "correlation": None,
                "p_value": None,
                "verdict": "INSUFFICIENT_DATA",
            })
            continue

        avg_score = round(valid[col_name].mean(), 1)
        corr, pval = _spearmanr(valid[col_name], valid[fwd_col])

        if abs(corr) < 0.1:
            verdict = "NO_SIGNAL_INVESTIGATE"
        elif corr < -0.1:
            verdict = "NEGATIVE_MISLEADING"
        elif corr > 0.3:
            verdict = "STRONG_KEEP"
        else:
            verdict = "KEEP"

        results.append({
            "dimension": dim_name,
            "avg_score": avg_score,
            "correlation": round(corr, 3),
            "p_value": round(pval, 4) if pval is not None else None,
            "verdict": verdict,
        })

    return results


def compute_pattern_analysis(df: pd.DataFrame) -> list[dict]:
    """Step 4: Pattern-type subgroup analysis."""
    if "pattern_type" not in df.columns or "fwd_30d_return" not in df.columns:
        return []

    results = []
    for pattern, group in df.groupby("pattern_type"):
        if pd.isna(pattern) or str(pattern).strip() == "":
            continue
        valid = group["fwd_30d_return"].dropna()
        hit_30_60 = group["hit_30pct_within_60d"].apply(
            lambda x: str(x).lower() == "true"
        ) if "hit_30pct_within_60d" in group.columns else pd.Series(dtype=bool)

        results.append({
            "pattern": str(pattern),
            "count": len(group),
            "avg_30d_return": round(valid.mean(), 2) if len(valid) > 0 else None,
            "hit_30pct_60d_rate": round(hit_30_60.mean(), 3) if len(hit_30_60) > 0 else None,
        })

    return sorted(results, key=lambda x: x.get("avg_30d_return") or 0, reverse=True)


def compute_layer2_audit(df: pd.DataFrame) -> dict:
    """Step 5: Engine Controller decision audit."""
    if "layer2_path" not in df.columns:
        return {"available": False}

    result = {"available": True}
    paths = df["layer2_path"].dropna()
    if paths.empty:
        return {"available": False}

    # Count decision types
    breadth_count = paths.str.contains("BREADTH", case=False, na=False).sum()
    depth_count = paths.str.contains("DEPTH", case=False, na=False).sum()
    terminate_count = paths.str.contains("TERMINATE", case=False, na=False).sum()

    result["breadth_count"] = int(breadth_count)
    result["depth_count"] = int(depth_count)
    result["terminate_count"] = int(terminate_count)

    return result


def generate_reflection_report(llm: LLMClient, skill_prompt: str,
                               metrics: dict, dim_corr: list,
                               pattern_analysis: list,
                               layer2_audit: dict,
                               df: pd.DataFrame,
                               lookback_days: int) -> str:
    """Use LLM to synthesize the full reflection report."""
    # Find worst losses for explicit analysis
    worst_losses = []
    if "fwd_30d_return" in df.columns:
        losses = df.nsmallest(3, "fwd_30d_return")
        for _, row in losses.iterrows():
            worst_losses.append({
                "ticker": row.get("ticker", "?"),
                "scan_date": str(row.get("scan_date", "")),
                "composite_score": row.get("composite_score", "?"),
                "fwd_30d_return": row.get("fwd_30d_return", "?"),
                "pattern_type": row.get("pattern_type", "?"),
            })

    user_msg = f"""Generate a monthly self-reflection report based on the following data.

## Lookback Period
{lookback_days} days, {metrics.get('total_picks', 0)} total picks

## Baseline Metrics
{json.dumps(metrics, indent=2, default=str)}

## Dimension Predictive Power (Spearman Correlation vs 30d Return)
{json.dumps(dim_corr, indent=2)}

## Pattern-Type Analysis
{json.dumps(pattern_analysis, indent=2)}

## Engine Controller (Layer 2) Audit
{json.dumps(layer2_audit, indent=2)}

## Worst 3 Losses (must analyze)
{json.dumps(worst_losses, indent=2, default=str)}

Follow the self-reflection skill workflow (Steps 1-7).
Output the full reflection report as structured JSON matching the schema in the skill document.
Then also provide a narrative summary section.

IMPORTANT: Do not auto-modify prompts. Output is a report for human review.
Be honest about small sample sizes — flag if <50 picks.

Return ONLY a valid JSON object matching the schema from the skill document."""

    resp = llm.chat(system=skill_prompt, user=user_msg, max_tokens=8192)
    return resp


def main():
    parser = argparse.ArgumentParser(description="Stage 8: Self Reflection")
    parser.add_argument("--skill", required=True,
                        help="Path to self_reflection_skill.md")
    parser.add_argument("--ledger", required=True,
                        help="Path to performance_ledger.csv")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--output", required=True,
                        help="Output path for reflection report")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    parser.add_argument("--model", default="claude-opus-4-8")
    args = parser.parse_args()

    if not Path(args.ledger).exists():
        print(f"[reflection] Ledger not found: {args.ledger}", file=sys.stderr)
        sys.exit(1)

    skill_prompt = Path(args.skill).read_text(encoding="utf-8")

    # Load and analyze data
    print(f"[reflection] Loading ledger (lookback={args.lookback_days}d) ...")
    df = load_ledger(args.ledger, args.lookback_days)

    if df.empty:
        print("[reflection] No data in lookback window, skipping.")
        # Write minimal report
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            f"# Monthly Reflection — {datetime.utcnow().strftime('%Y-%m')}\n\n"
            f"No data available for the last {args.lookback_days} days.\n"
        )
        return

    print(f"[reflection] {len(df)} picks in lookback window")

    # Compute all metrics
    metrics = compute_baseline_metrics(df)
    dim_corr = compute_dimension_correlations(df)
    pattern_analysis = compute_pattern_analysis(df)
    layer2_audit = compute_layer2_audit(df)

    # Generate report via LLM
    print("[reflection] Generating reflection report via LLM ...")
    llm = LLMClient(provider=args.provider, model=args.model)
    report_text = generate_reflection_report(
        llm, skill_prompt, metrics, dim_corr, pattern_analysis,
        layer2_audit, df, args.lookback_days,
    )

    # Write output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Write as markdown with the JSON report embedded
    header = (
        f"# Monthly Self-Reflection Report — "
        f"{datetime.utcnow().strftime('%Y-%m')}\n\n"
        f"Generated: {datetime.utcnow().isoformat()}\n"
        f"Lookback: {args.lookback_days} days\n"
        f"Total picks analyzed: {metrics.get('total_picks', 0)}\n\n"
        f"---\n\n"
    )

    # Add computed metrics summary
    metrics_md = "## Pre-computed Metrics\n\n"
    metrics_md += f"```json\n{json.dumps(metrics, indent=2, default=str)}\n```\n\n"
    metrics_md += "## Dimension Correlations\n\n"
    metrics_md += f"```json\n{json.dumps(dim_corr, indent=2)}\n```\n\n"
    metrics_md += "## Pattern Analysis\n\n"
    metrics_md += f"```json\n{json.dumps(pattern_analysis, indent=2)}\n```\n\n"
    metrics_md += "---\n\n## LLM Reflection\n\n"

    with open(args.output, "w") as f:
        f.write(header + metrics_md + report_text)

    print(f"[reflection] Done → {args.output}")


if __name__ == "__main__":
    main()
