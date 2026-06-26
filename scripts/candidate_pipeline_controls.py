#!/usr/bin/env python3
"""Helpers for launching the local candidate pipeline from Streamlit.

The UI builds argv lists, not shell strings, so user-adjustable numeric
parameters cannot accidentally become shell syntax.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


REPO = Path(__file__).resolve().parent.parent
LOG_PATH = REPO / "reports" / "run_status" / "candidates-local.log"
PIPELINE_SCRIPT = REPO / "scripts" / "run_candidate_pipeline.py"

RunMode = Literal["full_refresh", "rank_existing", "llm_deep_check"]
RUN_MODE_LABELS = {
    "full_refresh": "完整刷新",
    "rank_existing": "只重排",
    "llm_deep_check": "少量 LLM",
}


@dataclass(frozen=True)
class CandidateRunParams:
    mode: RunMode
    rank_limit: int = 50
    options_gate_limit: int = 10
    candidate_limit: int = 3
    universe: str = "sp1500"
    yf_batch_size: int = 25
    min_data_coverage: float = 0.70
    min_avg_dollar_vol: int = 5_000_000
    min_market_cap: int = 300_000_000
    min_price: float = 5.0
    max_ret_5d: float = 30.0
    max_ret_20d: float = 60.0
    earnings_exclude_days: int = 2


def _fmt(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_pipeline_command(params: CandidateRunParams) -> list[str]:
    """Build the non-shell argv for the requested local candidate action."""
    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--mode",
        params.mode,
    ]
    if params.mode == "full_refresh":
        command.extend([
            "--rank-limit",
            str(int(params.rank_limit)),
            "--options-gate-limit",
            str(int(params.options_gate_limit)),
            "--universe",
            params.universe,
            "--yf-batch-size",
            str(int(params.yf_batch_size)),
            "--min-data-coverage",
            _fmt(params.min_data_coverage),
            "--min-avg-dollar-vol",
            str(int(params.min_avg_dollar_vol)),
            "--min-market-cap",
            str(int(params.min_market_cap)),
            "--min-price",
            _fmt(params.min_price),
            "--max-ret-5d",
            _fmt(params.max_ret_5d),
            "--max-ret-20d",
            _fmt(params.max_ret_20d),
            "--earnings-exclude-days",
            str(int(params.earnings_exclude_days)),
        ])
        return command
    if params.mode == "rank_existing":
        command.extend([
            "--rank-limit",
            str(int(params.rank_limit)),
            "--options-gate-limit",
            str(int(params.options_gate_limit)),
        ])
        return command
    if params.mode == "llm_deep_check":
        command.extend([
            "--candidate-limit",
            str(int(params.candidate_limit)),
        ])
        return command
    raise ValueError(f"unknown candidate run mode: {params.mode}")


def launch_background(params: CandidateRunParams, *, cwd: Path = REPO,
                      log_path: Path = LOG_PATH) -> dict:
    """Start a local candidate pipeline process and return launch metadata."""
    command = build_pipeline_command(params)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return {
        "pid": proc.pid,
        "mode": params.mode,
        "mode_label": RUN_MODE_LABELS.get(params.mode, params.mode),
        "command": command,
        "log_path": str(log_path),
    }
