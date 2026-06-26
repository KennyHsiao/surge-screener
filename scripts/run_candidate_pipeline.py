#!/usr/bin/env python3
"""Run candidate pipeline modes without relying on Make.

This script is the runtime entrypoint used by Streamlit.  The Makefile can stay
as a developer shortcut, but the deployed app should only need Python.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_STATUS_FILE = "reports/run_status/candidates-local.json"


@dataclass(frozen=True)
class PipelineStep:
    argv: list[str]
    env: dict[str, str] | None = None


def _fmt(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local candidate pipeline modes")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["full_refresh", "rank_existing", "llm_deep_check"],
    )
    parser.add_argument("--status-file", default=DEFAULT_STATUS_FILE)
    parser.add_argument("--markets", default="US")
    parser.add_argument(
        "--universe",
        default="sp1500",
        choices=["sp1500", "russell3000", "nasdaq_only", "custom"],
    )
    parser.add_argument("--yf-batch-size", type=int, default=25)
    parser.add_argument("--min-data-coverage", type=float, default=0.70)
    parser.add_argument("--min-avg-dollar-vol", type=int, default=5_000_000)
    parser.add_argument("--min-market-cap", type=int, default=300_000_000)
    parser.add_argument("--min-price", type=float, default=5.0)
    parser.add_argument("--max-ret-5d", type=float, default=30.0)
    parser.add_argument("--max-ret-20d", type=float, default=60.0)
    parser.add_argument("--earnings-exclude-days", type=int, default=2)
    parser.add_argument("--rank-limit", type=int, default=50)
    parser.add_argument("--options-gate-limit", type=int, default=10)
    parser.add_argument("--candidate-limit", type=int, default=3)
    parser.add_argument("--candidate-model", default="claude-sonnet-4-6")
    parser.add_argument("--candidate-retries", type=int, default=1)
    parser.add_argument("--candidate-deferred-retries", type=int, default=0)
    parser.add_argument(
        "--candidate-scoring-mode",
        choices=["full", "fast"],
        default="fast",
    )
    parser.add_argument("--min-score", type=int, default=65)
    parser.add_argument("--llm-score-input", default="ranked_candidates.json")
    parser.add_argument("--claude-agent-timeout", type=int, default=180)
    parser.add_argument(
        "--rescore-stale-llm",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser.parse_args(argv)


def _hard_filter_step(args: argparse.Namespace) -> PipelineStep:
    return PipelineStep([
        sys.executable,
        "scripts/01_hard_filter.py",
        "--markets",
        args.markets,
        "--universe",
        args.universe,
        "--batch-size",
        str(args.yf_batch_size),
        "--min-data-coverage",
        _fmt(args.min_data_coverage),
        "--min-avg-dollar-vol",
        str(int(args.min_avg_dollar_vol)),
        "--min-market-cap",
        str(int(args.min_market_cap)),
        "--min-price",
        _fmt(args.min_price),
        "--max-ret-5d",
        _fmt(args.max_ret_5d),
        "--max-ret-20d",
        _fmt(args.max_ret_20d),
        "--earnings-exclude-days",
        str(int(args.earnings_exclude_days)),
        "--status-file",
        args.status_file,
        "--output",
        "filtered_universe.json",
    ])


def _rank_step(args: argparse.Namespace, *, start_status: bool) -> PipelineStep:
    argv = [
        sys.executable,
        "scripts/03_rank_candidates.py",
        "--input",
        "filtered_universe.json",
        "--limit",
        str(int(args.rank_limit)),
        "--options-gate-limit",
        str(int(args.options_gate_limit)),
        "--status-file",
        args.status_file,
        "--output",
        "ranked_candidates.json",
    ]
    if start_status:
        argv.append("--start-status")
    return PipelineStep(argv)


def _llm_preflight_step(args: argparse.Namespace) -> PipelineStep:
    return PipelineStep([
        sys.executable,
        "scripts/llm_client.py",
        "--provider",
        "claude_agent",
        "--model",
        args.candidate_model,
    ])


def _llm_score_step(args: argparse.Namespace) -> PipelineStep:
    argv = [
        sys.executable,
        "scripts/02_llm_score.py",
        "--input",
        args.llm_score_input,
        "--prompt",
        "system_prompts/01_surge_screener_prompt.md",
        "--min-score",
        str(int(args.min_score)),
        "--provider",
        "claude_agent",
        "--model",
        args.candidate_model,
        "--layer1-model",
        args.candidate_model,
        "--limit",
        str(int(args.candidate_limit)),
        "--candidate-retries",
        str(int(args.candidate_retries)),
        "--deferred-retries",
        str(int(args.candidate_deferred_retries)),
        "--scoring-mode",
        args.candidate_scoring_mode,
        "--status-file",
        args.status_file,
        "--resume",
        "--output",
        "scored_candidates.json",
    ]
    if args.rescore_stale_llm:
        argv.append("--rescore-stale-language")
    return PipelineStep(
        argv,
        env={"CLAUDE_AGENT_TIMEOUT": str(int(args.claude_agent_timeout))},
    )


def build_steps(args: argparse.Namespace) -> list[PipelineStep]:
    if args.mode == "full_refresh":
        return [_hard_filter_step(args), _rank_step(args, start_status=False)]
    if args.mode == "rank_existing":
        return [_rank_step(args, start_status=True)]
    if args.mode == "llm_deep_check":
        return [_llm_preflight_step(args), _llm_score_step(args)]
    raise ValueError(f"unknown candidate pipeline mode: {args.mode}")


def run_step(step: PipelineStep) -> None:
    print(f"[candidate_pipeline] $ {shlex.join(step.argv)}", flush=True)
    env = None
    if step.env:
        env = {**os.environ, **step.env}
    subprocess.run(step.argv, cwd=REPO, env=env, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for step in build_steps(args):
        run_step(step)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
