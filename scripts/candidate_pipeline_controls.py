#!/usr/bin/env python3
"""Helpers for launching the local candidate pipeline from Streamlit.

The UI builds argv lists, not shell strings, so user-adjustable numeric
parameters cannot accidentally become shell syntax.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

try:
    from scripts import codex_auth_flow
except ImportError:
    import codex_auth_flow


REPO = Path(__file__).resolve().parent.parent
LOG_PATH = REPO / "reports" / "run_status" / "candidates-local.log"
PIPELINE_SCRIPT = REPO / "scripts" / "run_candidate_pipeline.py"

RunMode = Literal["full_refresh", "rank_existing", "llm_deep_check"]
RUN_MODE_LABELS = {
    "full_refresh": "完整刷新",
    "rank_existing": "只重排",
    "llm_deep_check": "少量 LLM",
}
_AUTO_SYSTEMD_RUN = object()
_RUNTIME_ENV_KEYS = (
    "SURGE_APP_ROOT",
    "SURGE_RUNTIME_DIR",
    "SURGE_ANALYTICS_DIR",
    "SURGE_CANDIDATE_OUTPUT_DIR",
    "CODEX_HOME",
    "PATH",
    "PYTHONPATH",
)


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


def _utc_unit_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _service_managed_runtime() -> bool:
    return bool(
        os.environ.get("INVOCATION_ID")
        or os.environ.get("SYSTEMD_EXEC_PID")
        or os.environ.get("SURGE_FORCE_SYSTEMD_RUN") == "1"
    )


def _runtime_env_args() -> list[str]:
    env = ["PYTHONUNBUFFERED=1"]
    for key in _RUNTIME_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env.append(f"{key}={value}")
    return env


def _build_background_launcher(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    platform: str | None = None,
    systemd_run_path: str | None | object = _AUTO_SYSTEMD_RUN,
    unit_name: str | None = None,
) -> tuple[list[str], dict]:
    """Wrap a long-running refresh so it can survive Streamlit service restarts."""
    current_platform = platform or sys.platform
    explicit_systemd_path = systemd_run_path is not _AUTO_SYSTEMD_RUN
    resolved_systemd_path = (
        shutil.which("systemd-run")
        if systemd_run_path is _AUTO_SYSTEMD_RUN
        else systemd_run_path
    )
    use_systemd = (
        current_platform.startswith("linux")
        and bool(resolved_systemd_path)
        and (explicit_systemd_path or _service_managed_runtime())
    )
    if not use_systemd:
        return command, {"launch_mode": "popen"}

    unit = unit_name or f"surge-candidate-refresh-{_utc_unit_suffix()}"
    unit_display = unit if unit.endswith(".service") else f"{unit}.service"
    script = (
        f"cd {shlex.quote(str(cwd))} || exit; "
        f"exec >>{shlex.quote(str(log_path))} 2>&1; "
        f"exec {shlex.join(command)}"
    )
    launcher = [
        str(resolved_systemd_path),
        "--user",
        f"--unit={unit.removesuffix('.service')}",
        "--collect",
        "/usr/bin/env",
        *_runtime_env_args(),
        "bash",
        "-lc",
        script,
    ]
    return launcher, {"launch_mode": "systemd-run", "unit": unit_display}


def _start_pipeline_background(
    params: CandidateRunParams,
    *,
    cwd: Path = REPO,
    log_path: Path = LOG_PATH,
    process_factory=subprocess.Popen,
) -> dict:
    command = build_pipeline_command(params)
    launcher, launch_meta = _build_background_launcher(command, cwd=cwd, log_path=log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = process_factory(
            launcher,
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
        "launcher": launcher,
        "log_path": str(log_path),
        **launch_meta,
    }


def read_pending_codex_request() -> dict | None:
    return codex_auth_flow.read_pending_request()


def refresh_codex_auth_status() -> dict:
    return codex_auth_flow.refresh_status()


def resume_pending_codex_run(
    *,
    cwd: Path = REPO,
    log_path: Path = LOG_PATH,
    auth_checker=codex_auth_flow.refresh_status,
    process_factory=subprocess.Popen,
) -> dict | None:
    pending = codex_auth_flow.read_pending_request()
    if not isinstance(pending, dict):
        return None
    auth = auth_checker()
    if not auth.get("ok"):
        return None
    raw_params = pending.get("params")
    if not isinstance(raw_params, dict):
        codex_auth_flow.clear_pending_request()
        return None
    params = CandidateRunParams(**raw_params)
    meta = _start_pipeline_background(
        params,
        cwd=cwd,
        log_path=log_path,
        process_factory=process_factory,
    )
    codex_auth_flow.clear_pending_request()
    return meta


def launch_background(
    params: CandidateRunParams,
    *,
    cwd: Path = REPO,
    log_path: Path = LOG_PATH,
    auth_checker=codex_auth_flow.refresh_status,
    login_starter=codex_auth_flow.start_login,
    process_factory=subprocess.Popen,
) -> dict:
    """Start a local candidate pipeline process and return launch metadata."""
    if params.mode == "llm_deep_check":
        auth = auth_checker()
        if not auth.get("ok"):
            codex_auth_flow.write_pending_request(asdict(params))
            login = login_starter()
            return {
                "pid": login.get("pid"),
                "mode": "codex_auth_login",
                "mode_label": "Codex 登入中",
                "resume_mode": params.mode,
                "command": login.get("command", []),
                "log_path": login.get("log_path", str(codex_auth_flow.AUTH_LOG_PATH)),
                "auth_status": login,
                "pending_path": str(codex_auth_flow.PENDING_REQUEST_PATH),
            }
    return _start_pipeline_background(
        params,
        cwd=cwd,
        log_path=log_path,
        process_factory=process_factory,
    )
