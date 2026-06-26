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
PY_OVERRIDE = f"PY={sys.executable}"

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


def build_make_command(params: CandidateRunParams) -> list[str]:
    """Build the non-shell argv for the requested local candidate action."""
    if params.mode == "full_refresh":
        return [
            "make",
            "candidates-local",
            PY_OVERRIDE,
            f"RANK_LIMIT={int(params.rank_limit)}",
            f"OPTIONS_GATE_LIMIT={int(params.options_gate_limit)}",
            f"UNIVERSE={params.universe}",
            f"YF_BATCH_SIZE={int(params.yf_batch_size)}",
            f"MIN_DATA_COVERAGE={_fmt(params.min_data_coverage)}",
            f"MIN_AVG_DOLLAR_VOL={int(params.min_avg_dollar_vol)}",
            f"MIN_MARKET_CAP={int(params.min_market_cap)}",
            f"MIN_PRICE={_fmt(params.min_price)}",
            f"MAX_RET_5D={_fmt(params.max_ret_5d)}",
            f"MAX_RET_20D={_fmt(params.max_ret_20d)}",
            f"EARNINGS_EXCLUDE_DAYS={int(params.earnings_exclude_days)}",
        ]
    if params.mode == "rank_existing":
        return [
            "make",
            "candidates-rank-local",
            PY_OVERRIDE,
            f"RANK_LIMIT={int(params.rank_limit)}",
            f"OPTIONS_GATE_LIMIT={int(params.options_gate_limit)}",
        ]
    if params.mode == "llm_deep_check":
        return [
            "make",
            "candidates-score-local",
            PY_OVERRIDE,
            f"CANDIDATE_LIMIT={int(params.candidate_limit)}",
            "RESCORE_STALE_LLM=1",
        ]
    raise ValueError(f"unknown candidate run mode: {params.mode}")


def launch_background(params: CandidateRunParams, *, cwd: Path = REPO,
                      log_path: Path = LOG_PATH) -> dict:
    """Start a local candidate pipeline process and return launch metadata."""
    command = build_make_command(params)
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
