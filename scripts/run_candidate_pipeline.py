#!/usr/bin/env python3
"""Run candidate pipeline modes without relying on Make.

This script is the runtime entrypoint used by Streamlit.  The Makefile can stay
as a developer shortcut, but the deployed app should only need Python.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fcntl

try:
    from scripts.runtime_paths import candidate_output_path, ensure_parent
except ImportError:
    from runtime_paths import candidate_output_path, ensure_parent


REPO = Path(__file__).resolve().parent.parent
DEFAULT_STATUS_FILE = "reports/run_status/candidates-local.json"
_HELD_LOCK_PATHS: set[Path] = set()


@dataclass(frozen=True)
class PipelineStep:
    argv: list[str]
    env: dict[str, str] | None = None
    skip_if_empty_candidate_file: str | None = None


def _fmt(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _status_lock_path(status_file: str | Path) -> Path:
    path = Path(status_file)
    if not path.is_absolute():
        path = REPO / path
    return path.with_suffix(".lock")


def _candidate_path(filename: str | Path) -> str:
    return str(ensure_parent(candidate_output_path(filename)))


@contextmanager
def acquire_pipeline_lock(lock_path: str | Path):
    """Hold an exclusive process lock while one candidate pipeline is running."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    if resolved in _HELD_LOCK_PATHS:
        raise RuntimeError(f"candidate pipeline already running: {path}")

    lock_file = path.open("a+", encoding="utf-8")
    locked = False
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            lock_file.seek(0)
            owner = lock_file.read().strip()
            detail = f" ({owner})" if owner else ""
            raise RuntimeError(f"candidate pipeline already running{detail}") from e

        locked = True
        _HELD_LOCK_PATHS.add(resolved)
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(json.dumps({
            "pid": os.getpid(),
            "argv": sys.argv,
        }, ensure_ascii=False))
        lock_file.flush()
        os.fsync(lock_file.fileno())
        yield
    finally:
        if locked:
            try:
                lock_file.seek(0)
                lock_file.truncate()
                lock_file.flush()
                os.fsync(lock_file.fileno())
            except OSError:
                pass
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                _HELD_LOCK_PATHS.discard(resolved)
        lock_file.close()


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
    parser.add_argument("--money-flow-prefetch", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--money-flow-prefetch-limit", type=int, default=80)
    parser.add_argument("--candidate-limit", type=int, default=3)
    parser.add_argument("--candidate-model", default=None,
                        help="Optional Codex model; defaults to CODEX_MODEL/account setting")
    parser.add_argument("--candidate-retries", type=int, default=1)
    parser.add_argument("--candidate-deferred-retries", type=int, default=0)
    parser.add_argument(
        "--candidate-scoring-mode",
        choices=["full", "fast"],
        default="fast",
    )
    parser.add_argument("--min-score", type=int, default=65)
    parser.add_argument("--llm-score-input", default="ranked_candidates.json")
    parser.add_argument("--codex-timeout", type=int, default=180)
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
        _candidate_path("filtered_universe.json"),
    ])


def _rank_step(
    args: argparse.Namespace,
    *,
    start_status: bool,
    output: str | None = None,
    history_dir: str | None = "reports/candidate_rankings",
    options_gate_limit: int | None = None,
    disable_money_flow: bool = False,
) -> PipelineStep:
    argv = [
        sys.executable,
        "scripts/03_rank_candidates.py",
        "--input",
        _candidate_path("filtered_universe.json"),
        "--limit",
        str(int(args.rank_limit)),
        "--options-gate-limit",
        str(int(args.options_gate_limit if options_gate_limit is None else options_gate_limit)),
        "--status-file",
        args.status_file,
        "--history-dir",
        "" if history_dir is None else history_dir,
        "--output",
        output or _candidate_path("ranked_candidates.json"),
    ]
    if start_status:
        argv.append("--start-status")
    if disable_money_flow:
        argv.append("--disable-money-flow")
    return PipelineStep(argv)


def _money_flow_prefetch_rank_path() -> str:
    return str(REPO / "reports" / "run_status" / "money_flow_prefetch_ranked_candidates.json")


def _money_flow_prefetch_step(args: argparse.Namespace) -> PipelineStep:
    candidate_file = _money_flow_prefetch_rank_path()
    return PipelineStep(
        [
            sys.executable,
            "scripts/eastmoney_money_flow.py",
            "--candidate-file",
            candidate_file,
            "--candidate-limit",
            str(int(args.money_flow_prefetch_limit)),
            "--only-candidate-file",
            "--reports-dir",
            "reports",
            "--content-dir",
            "content",
        ],
        skip_if_empty_candidate_file=candidate_file,
    )


def _llm_preflight_step(args: argparse.Namespace) -> PipelineStep:
    argv = [
        sys.executable,
        "scripts/llm_client.py",
        "--provider",
        "codex",
    ]
    if args.candidate_model:
        argv.extend(["--model", args.candidate_model])
    return PipelineStep(argv)


def _llm_score_step(args: argparse.Namespace) -> PipelineStep:
    argv = [
        sys.executable,
        "scripts/02_llm_score.py",
        "--input",
        _candidate_path(args.llm_score_input),
        "--prompt",
        "system_prompts/01_surge_screener_prompt.md",
        "--min-score",
        str(int(args.min_score)),
        "--provider",
        "codex",
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
        _candidate_path("scored_candidates.json"),
        "--history-dir",
        "reports/candidate_scores",
    ]
    if args.candidate_model:
        argv.extend([
            "--model",
            args.candidate_model,
            "--layer1-model",
            args.candidate_model,
        ])
    if args.rescore_stale_llm:
        argv.append("--rescore-stale-language")
    return PipelineStep(
        argv,
        env={"CODEX_SDK_TIMEOUT": str(int(args.codex_timeout))},
    )


def build_steps(args: argparse.Namespace) -> list[PipelineStep]:
    if args.mode == "full_refresh":
        steps = [_hard_filter_step(args)]
        if args.money_flow_prefetch:
            steps.append(_rank_step(
                args,
                start_status=False,
                output=_money_flow_prefetch_rank_path(),
                history_dir=None,
                options_gate_limit=0,
                disable_money_flow=True,
            ))
            steps.append(_money_flow_prefetch_step(args))
        steps.append(_rank_step(args, start_status=False))
        return steps
    if args.mode == "rank_existing":
        steps = []
        if args.money_flow_prefetch:
            steps.append(_rank_step(
                args,
                start_status=True,
                output=_money_flow_prefetch_rank_path(),
                history_dir=None,
                options_gate_limit=0,
                disable_money_flow=True,
            ))
            steps.append(_money_flow_prefetch_step(args))
            steps.append(_rank_step(args, start_status=False))
            return steps
        return [_rank_step(args, start_status=True)]
    if args.mode == "llm_deep_check":
        return [_llm_preflight_step(args), _llm_score_step(args)]
    raise ValueError(f"unknown candidate pipeline mode: {args.mode}")


def _candidate_file_has_rows(candidate_file: str | Path) -> bool:
    try:
        with Path(candidate_file).open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    for key in ("ranked_candidates", "tickers"):
        rows = data.get(key)
        if isinstance(rows, list) and rows:
            return True
    return False


def run_step(step: PipelineStep) -> None:
    if step.skip_if_empty_candidate_file and not _candidate_file_has_rows(step.skip_if_empty_candidate_file):
        print(
            "[candidate_pipeline] skipping empty candidate prefetch: "
            f"{step.skip_if_empty_candidate_file}",
            flush=True,
        )
        return
    print(f"[candidate_pipeline] $ {shlex.join(step.argv)}", flush=True)
    env = None
    if step.env:
        env = {**os.environ, **step.env}
    subprocess.run(step.argv, cwd=REPO, env=env, check=True)


def _refresh_call(name: str, fn) -> dict[str, Any]:
    try:
        result = fn()
        return {"name": name, "status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001 - free data refresh must not hide analytics refresh.
        return {"name": name, "status": "error", "error": str(e)}


def refresh_data_artifacts(
    *,
    reports_root: str | Path | None = None,
    content_root: str | Path | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Best-effort daily data artifacts before rebuilding the analytics DB."""
    reports = Path(reports_root) if reports_root is not None else REPO / "reports"
    content = Path(content_root) if content_root is not None else REPO / "content"
    try:
        from scripts import (
            daily_bars_store,
            eastmoney_money_flow,
            industry_roles,
            trade_state,
            universe_refresh,
        )
    except ImportError:
        import daily_bars_store  # type: ignore
        import eastmoney_money_flow  # type: ignore
        import industry_roles  # type: ignore
        import trade_state  # type: ignore
        import universe_refresh  # type: ignore

    steps: list[dict[str, Any]] = []
    steps.append(_refresh_call(
        "universe",
        lambda: universe_refresh.refresh_universe(
            reports_dir=reports,
            content_dir=content,
            as_of_date=as_of_date,
        ),
    ))
    tickers = eastmoney_money_flow.collect_money_flow_tickers(
        reports_dir=reports,
        content_dir=content,
    )
    steps.append(_refresh_call(
        "daily_bars",
        lambda: daily_bars_store.refresh_daily_bars(tickers, reports_dir=reports, as_of_date=as_of_date),
    ))
    steps.append(_refresh_call(
        "money_flow",
        lambda: eastmoney_money_flow.refresh_money_flow(tickers, reports_dir=reports, as_of_date=as_of_date),
    ))
    steps.append(_refresh_call(
        "role_suggestions",
        lambda: industry_roles.generate_suggestions(
            tickers,
            content_dir=content,
            reports_dir=reports,
        ),
    ))
    if os.environ.get("SURGE_REFRESH_OPTIONS_FLOW") == "1":
        steps.append(_refresh_call(
            "options_flow",
            lambda: subprocess.run(
                [sys.executable, "scripts/options_flow_scan.py", "--universe", ",".join(tickers)],
                cwd=REPO,
                check=True,
            ),
        ))
    else:
        steps.append({"name": "options_flow", "status": "skipped", "reason": "SURGE_REFRESH_OPTIONS_FLOW not set"})
    steps.append(_refresh_call(
        "trade_state",
        lambda: trade_state.refresh_trade_state_snapshot(
            reports_dir=reports,
            content_dir=content,
            as_of_date=as_of_date,
        ),
    ))
    steps.append(_refresh_call(
        "industry_roles",
        lambda: industry_roles.refresh_role_assignment_snapshot(
            content_dir=content,
            reports_dir=reports,
            as_of_date=as_of_date,
        ),
    ))
    return {"steps": steps, "tickers": tickers}


def refresh_analytics_after_run(
    *,
    analytics_store_module=None,
    analytics_checks_module=None,
    data_refresher=None,
) -> dict[str, Any]:
    """Refresh data artifacts, DuckDB/read-model checks after candidate artifacts change."""
    try:
        from scripts import analytics_checks, analytics_store
    except ImportError:
        import analytics_checks  # type: ignore
        import analytics_store  # type: ignore

    analytics_store = analytics_store_module or analytics_store
    analytics_checks = analytics_checks_module or analytics_checks
    data_refresher = data_refresher or refresh_data_artifacts
    reports_root = REPO / "reports"
    content_root = REPO / "content"
    analytics_root = analytics_store.analytics_dir()
    checks_path = reports_root / "analytics_checks" / "latest.json"
    print("[candidate_pipeline] refreshing data artifacts", flush=True)
    data_refresh = data_refresher(
        reports_root=reports_root,
        content_root=content_root,
        as_of_date=None,
    )
    print("[candidate_pipeline] refreshing analytics store", flush=True)
    tables = analytics_store.refresh_all(
        reports_root=reports_root,
        analytics_root=analytics_root,
    )
    checks = analytics_checks.run_checks(
        analytics_root=analytics_root,
        output_path=checks_path,
    )
    print(
        "[candidate_pipeline] analytics refreshed: "
        f"candidate_rankings={tables.get('candidate_rankings', {}).get('rows', '-')}, "
        f"run_status_history={tables.get('run_status_history', {}).get('rows', '-')}, "
        f"checks={checks.get('status', '-')}",
        flush=True,
    )
    return {"data_refresh": data_refresh, "tables": tables, "checks": checks}


def _pipeline_status_writer(status_file: str | Path):
    try:
        from scripts.run_status import RunStatus
    except ImportError:
        from run_status import RunStatus  # type: ignore
    return RunStatus(status_file)


def _analytics_refresh_metrics(result: dict[str, Any]) -> dict[str, Any]:
    tables = result.get("tables") if isinstance(result.get("tables"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    return {
        "analytics_candidate_rankings": (
            tables.get("candidate_rankings", {}).get("rows")
            if isinstance(tables.get("candidate_rankings"), dict)
            else None
        ),
        "analytics_candidate_scores": (
            tables.get("candidate_scores", {}).get("rows")
            if isinstance(tables.get("candidate_scores"), dict)
            else None
        ),
        "analytics_checks_status": checks.get("status"),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        with acquire_pipeline_lock(_status_lock_path(args.status_file)):
            for step in build_steps(args):
                run_step(step)
            status = _pipeline_status_writer(args.status_file)
            try:
                status.update_stage(
                    "analytics_refresh",
                    "更新資料與 Analytics",
                    progress_pct=92,
                    message="候選已產生，正在刷新資料產物與 Analytics checks。",
                )
                analytics_result = refresh_analytics_after_run()
                status.update_stage(
                    "analytics_refresh",
                    "更新資料與 Analytics",
                    status="succeeded",
                    progress_pct=99,
                    message="資料產物與 Analytics checks 已更新。",
                    metrics=_analytics_refresh_metrics(analytics_result),
                )
                status.succeed(
                    message="候選流程與 Analytics 更新完成",
                    metrics=_analytics_refresh_metrics(analytics_result),
                )
            except Exception as e:  # noqa: BLE001 - keep failure visible in UI log.
                status.fail(
                    "analytics_refresh",
                    "更新資料與 Analytics",
                    str(e),
                )
                print(f"[candidate_pipeline] analytics refresh failed: {e}", file=sys.stderr)
                return 4
    except RuntimeError as e:
        print(f"[candidate_pipeline] {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
