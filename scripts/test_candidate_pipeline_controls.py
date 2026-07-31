#!/usr/bin/env python3
"""Tests for Today Decision candidate-pipeline launch command construction."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_controls():
    spec = importlib.util.spec_from_file_location(
        "candidate_pipeline_controls_under_test",
        ROOT / "scripts" / "candidate_pipeline_controls.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_full_refresh_command_includes_filter_and_rank_parameters() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(
        mode="full_refresh",
        rank_limit=50,
        options_gate_limit=10,
        universe="sp1500",
        yf_batch_size=25,
        min_data_coverage=0.7,
        min_avg_dollar_vol=10_000_000,
        min_market_cap=1_000_000_000,
        min_price=10,
        max_ret_5d=25,
        max_ret_20d=55,
        earnings_exclude_days=3,
    )
    cmd = mod.build_pipeline_command(params)

    expected = [
        sys.executable,
        "--mode",
        "full_refresh",
        "--rank-limit",
        "50",
        "--options-gate-limit",
        "10",
        "--universe",
        "sp1500",
        "--yf-batch-size",
        "25",
        "--min-data-coverage",
        "0.7",
        "--min-avg-dollar-vol",
        "10000000",
        "--min-market-cap",
        "1000000000",
        "--min-price",
        "10",
        "--max-ret-5d",
        "25",
        "--max-ret-20d",
        "55",
        "--earnings-exclude-days",
        "3",
    ]
    for part in expected:
        if part not in cmd:
            raise AssertionError(cmd)
    if "make" in cmd:
        raise AssertionError(cmd)
    if not any(part.endswith("scripts/run_candidate_pipeline.py") for part in cmd):
        raise AssertionError(cmd)


def test_rank_existing_command_does_not_include_hard_filter_parameters() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="rank_existing", rank_limit=30, options_gate_limit=5)
    cmd = mod.build_pipeline_command(params)

    if "rank_existing" not in cmd:
        raise AssertionError(cmd)
    if "--rank-limit" not in cmd or "30" not in cmd:
        raise AssertionError(cmd)
    if "--options-gate-limit" not in cmd or "5" not in cmd:
        raise AssertionError(cmd)
    for forbidden in ("MIN_AVG_DOLLAR_VOL", "MIN_MARKET_CAP", "YF_BATCH_SIZE"):
        if any(part.startswith(forbidden) for part in cmd):
            raise AssertionError(cmd)
    for forbidden in ("--min-avg-dollar-vol", "--min-market-cap", "--yf-batch-size"):
        if forbidden in cmd:
            raise AssertionError(cmd)


def test_llm_deep_check_command_uses_candidate_limit() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="llm_deep_check", candidate_limit=3)
    cmd = mod.build_pipeline_command(params)

    if "llm_deep_check" not in cmd:
        raise AssertionError(cmd)
    if "--candidate-limit" not in cmd or "3" not in cmd:
        raise AssertionError(cmd)


def test_llm_deep_check_starts_codex_login_when_auth_missing() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="llm_deep_check", candidate_limit=3)
    calls = {"login": 0, "pipeline": 0}

    def fake_auth_checker() -> dict:
        return {"ok": False, "state": "unauthenticated", "message": "login needed"}

    def fake_login_starter() -> dict:
        calls["login"] += 1
        return {
            "pid": 123,
            "state": "login_started",
            "ok": False,
            "command": ["codex", "login", "--device-auth"],
            "log_path": "/tmp/codex-auth.log",
        }

    def fake_process_factory(*args, **kwargs):
        calls["pipeline"] += 1
        raise AssertionError("pipeline must wait for Codex login")

    try:
        meta = mod.launch_background(
            params,
            auth_checker=fake_auth_checker,
            login_starter=fake_login_starter,
            process_factory=fake_process_factory,
        )
    finally:
        mod.codex_auth_flow.clear_pending_request()

    if meta["mode"] != "codex_auth_login":
        raise AssertionError(meta)
    if meta["mode_label"] != "Codex 登入中":
        raise AssertionError(meta)
    if meta.get("resume_mode") != "llm_deep_check":
        raise AssertionError(meta)
    if calls != {"login": 1, "pipeline": 0}:
        raise AssertionError(calls)


def test_llm_deep_check_launches_pipeline_when_auth_ready() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="llm_deep_check", candidate_limit=4)
    launched = {}

    class FakeProcess:
        pid = 456

    def fake_auth_checker() -> dict:
        return {"ok": True, "state": "authenticated", "message": "ready"}

    def fake_login_starter() -> dict:
        raise AssertionError("login should not start when auth is ready")

    def fake_process_factory(command, **kwargs):
        launched["command"] = command
        launched["kwargs"] = kwargs
        return FakeProcess()

    with tempfile.TemporaryDirectory() as d:
        meta = mod.launch_background(
            params,
            log_path=Path(d) / "candidate.log",
            auth_checker=fake_auth_checker,
            login_starter=fake_login_starter,
            process_factory=fake_process_factory,
        )

    if meta["mode"] != "llm_deep_check" or meta["pid"] != 456:
        raise AssertionError(meta)
    if "llm_deep_check" not in launched["command"]:
        raise AssertionError(launched)


def test_background_launcher_uses_systemd_run_on_linux() -> None:
    mod = _load_controls()
    command = [sys.executable, "scripts/run_candidate_pipeline.py", "--mode", "full_refresh"]

    launcher, meta = mod._build_background_launcher(
        command,
        cwd=Path("/app/current"),
        log_path=Path("/app/shared/run_status/candidates-local.log"),
        platform="linux",
        systemd_run_path="/usr/bin/systemd-run",
        unit_name="surge-candidate-refresh-test",
    )

    if launcher[:3] != ["/usr/bin/systemd-run", "--user", "--unit=surge-candidate-refresh-test"]:
        raise AssertionError(launcher)
    if "--collect" not in launcher:
        raise AssertionError(launcher)
    if meta.get("launch_mode") != "systemd-run":
        raise AssertionError(meta)
    if meta.get("unit") != "surge-candidate-refresh-test.service":
        raise AssertionError(meta)
    joined = " ".join(launcher)
    if "exec >>/app/shared/run_status/candidates-local.log 2>&1" not in joined:
        raise AssertionError(launcher)
    if "scripts/run_candidate_pipeline.py --mode full_refresh" not in joined:
        raise AssertionError(launcher)


def test_background_launcher_falls_back_without_systemd() -> None:
    mod = _load_controls()
    command = [sys.executable, "scripts/run_candidate_pipeline.py", "--mode", "rank_existing"]

    launcher, meta = mod._build_background_launcher(
        command,
        cwd=Path("/app/current"),
        log_path=Path("/app/shared/run_status/candidates-local.log"),
        platform="darwin",
        systemd_run_path=None,
        unit_name="unused",
    )

    if launcher != command:
        raise AssertionError(launcher)
    if meta.get("launch_mode") != "popen":
        raise AssertionError(meta)


def test_pipeline_wrapper_expands_full_refresh_without_make() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    args = mod.parse_args([
        "--mode",
        "full_refresh",
        "--rank-limit",
        "12",
        "--options-gate-limit",
        "4",
    ])
    steps = mod.build_steps(args)

    if len(steps) != 4:
        raise AssertionError(steps)
    flattened = [part for step in steps for part in step.argv]
    if "make" in flattened:
        raise AssertionError(flattened)
    if "scripts/01_hard_filter.py" not in steps[0].argv:
        raise AssertionError(steps)
    if "scripts/03_rank_candidates.py" not in steps[1].argv or "--disable-money-flow" not in steps[1].argv:
        raise AssertionError(steps[1].argv)
    if "scripts/eastmoney_money_flow.py" not in steps[2].argv:
        raise AssertionError(steps[2].argv)
    if "--only-candidate-file" not in steps[2].argv:
        raise AssertionError(steps[2].argv)
    if "scripts/03_rank_candidates.py" not in steps[3].argv:
        raise AssertionError(steps)
    if "--limit" not in steps[3].argv or "12" not in steps[3].argv:
        raise AssertionError(steps[3].argv)
    if "--options-gate-limit" not in steps[3].argv or "4" not in steps[3].argv:
        raise AssertionError(steps[3].argv)


def test_pipeline_wrapper_can_disable_money_flow_prefetch() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_no_money_flow_prefetch",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    args = mod.parse_args(["--mode", "full_refresh", "--no-money-flow-prefetch"])
    steps = mod.build_steps(args)

    if len(steps) != 2:
        raise AssertionError(steps)
    flattened = [part for step in steps for part in step.argv]
    if "scripts/eastmoney_money_flow.py" in flattened:
        raise AssertionError(flattened)


def test_pipeline_wrapper_can_disable_money_flow_prefetch_for_rank_existing() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_rank_existing_no_money_flow_prefetch",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    args = mod.parse_args(["--mode", "rank_existing", "--no-money-flow-prefetch"])
    steps = mod.build_steps(args)

    if len(steps) != 1:
        raise AssertionError(steps)
    if "scripts/03_rank_candidates.py" not in steps[0].argv:
        raise AssertionError(steps[0].argv)
    if "--start-status" not in steps[0].argv:
        raise AssertionError(steps[0].argv)
    flattened = [part for step in steps for part in step.argv]
    if "scripts/eastmoney_money_flow.py" in flattened:
        raise AssertionError(flattened)


def test_money_flow_prefetch_skips_empty_ranked_candidates_file() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_empty_money_flow_prefetch",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("empty prefetch candidate file should skip subprocess")

    with tempfile.TemporaryDirectory() as d:
        candidate_file = Path(d) / "ranked_candidates.json"
        candidate_file.write_text('{"ranked_candidates": []}', encoding="utf-8")
        step = mod.PipelineStep(
            [sys.executable, "scripts/eastmoney_money_flow.py", "--candidate-file", str(candidate_file)],
            skip_if_empty_candidate_file=str(candidate_file),
        )
        old_run = mod.subprocess.run
        try:
            mod.subprocess.run = fake_run
            mod.run_step(step)
        finally:
            mod.subprocess.run = old_run

    if calls:
        raise AssertionError(calls)


def test_money_flow_prefetch_runs_for_non_empty_ranked_candidates_file() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_non_empty_money_flow_prefetch",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    with tempfile.TemporaryDirectory() as d:
        candidate_file = Path(d) / "ranked_candidates.json"
        candidate_file.write_text('{"ranked_candidates": [{"ticker": "NVDA"}]}', encoding="utf-8")
        step = mod.PipelineStep(
            [sys.executable, "scripts/eastmoney_money_flow.py", "--candidate-file", str(candidate_file)],
            skip_if_empty_candidate_file=str(candidate_file),
        )
        old_run = mod.subprocess.run
        try:
            mod.subprocess.run = fake_run
            mod.run_step(step)
        finally:
            mod.subprocess.run = old_run

    if len(calls) != 1:
        raise AssertionError(calls)


def test_pipeline_wrapper_uses_runtime_candidate_output_dir() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_runtime_paths_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod

    old = os.environ.get("SURGE_CANDIDATE_OUTPUT_DIR")
    with tempfile.TemporaryDirectory() as d:
        os.environ["SURGE_CANDIDATE_OUTPUT_DIR"] = d
        sys.modules.pop("scripts.runtime_paths", None)
        sys.modules.pop("runtime_paths", None)
        try:
            spec.loader.exec_module(mod)
            args = mod.parse_args(["--mode", "full_refresh"])
            steps = mod.build_steps(args)
        finally:
            if old is None:
                os.environ.pop("SURGE_CANDIDATE_OUTPUT_DIR", None)
            else:
                os.environ["SURGE_CANDIDATE_OUTPUT_DIR"] = old

    expected_filter = str(Path(d) / "filtered_universe.json")
    expected_ranked = str(Path(d) / "ranked_candidates.json")
    rank_steps = [step for step in steps if "scripts/03_rank_candidates.py" in step.argv]
    if len(rank_steps) != 2:
        raise AssertionError(steps)
    final_rank_step = rank_steps[-1]
    if expected_filter not in steps[0].argv or expected_filter not in final_rank_step.argv:
        raise AssertionError(steps)
    if expected_ranked not in final_rank_step.argv:
        raise AssertionError(steps)


def test_pipeline_wrapper_refreshes_analytics_after_successful_run() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_refresh_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    import tempfile

    calls = []

    def fake_run_step(step) -> None:
        calls.append(("step", step.argv))

    def fake_refresh() -> dict:
        calls.append(("refresh",))
        return {"candidate_rankings": {"rows": 1}}

    with tempfile.TemporaryDirectory() as d:
        mod.run_step = fake_run_step
        mod.refresh_analytics_after_run = fake_refresh
        code = mod.main([
            "--mode",
            "rank_existing",
            "--status-file",
            str(Path(d) / "candidates-local.json"),
        ])

    if code != 0:
        raise AssertionError(code)
    if [name for name, *_ in calls] != ["step", "step", "step", "refresh"]:
        raise AssertionError(calls)


def test_pipeline_wrapper_final_status_waits_for_analytics_refresh() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_final_status_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    import tempfile
    import json

    status_spec = importlib.util.spec_from_file_location(
        "run_status_for_final_status_test",
        ROOT / "scripts" / "run_status.py",
    )
    status_mod = importlib.util.module_from_spec(status_spec)
    assert status_spec.loader is not None
    sys.modules[status_spec.name] = status_mod
    status_spec.loader.exec_module(status_mod)

    calls = []

    def fake_run_step(step) -> None:
        calls.append("step")
        if "--status-file" not in step.argv:
            return
        status_file = step.argv[step.argv.index("--status-file") + 1]
        writer = status_mod.RunStatus(status_file)
        writer.start()
        writer.succeed(message="child step marked complete too early")

    def fake_refresh() -> dict:
        calls.append("refresh")
        return {
            "tables": {"candidate_rankings": {"rows": 5}},
            "checks": {"status": "WARN"},
        }

    with tempfile.TemporaryDirectory() as d:
        status_file = Path(d) / "candidates-local.json"
        mod.run_step = fake_run_step
        mod.refresh_analytics_after_run = fake_refresh
        code = mod.main([
            "--mode",
            "rank_existing",
            "--status-file",
            str(status_file),
        ])
        status = json.loads(status_file.read_text(encoding="utf-8"))

    if code != 0:
        raise AssertionError(code)
    if calls != ["step", "step", "step", "refresh"]:
        raise AssertionError(calls)
    if status["status"] != "succeeded":
        raise AssertionError(status)
    if status["stage"]["message"] == "child step marked complete too early":
        raise AssertionError(status)
    if "Analytics" not in status["stage"]["message"]:
        raise AssertionError(status)
    stages = {row["id"]: row for row in status.get("stages", [])}
    if stages.get("analytics_refresh", {}).get("status") != "succeeded":
        raise AssertionError(status.get("stages"))


def test_refresh_analytics_runs_data_refresh_before_store_and_checks() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_refresh_order_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    calls = []

    class FakeStore:
        @staticmethod
        def analytics_dir():
            calls.append("analytics_dir")
            return Path("/tmp/surge-analytics")

        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {"candidate_rankings": {"rows": 1}}

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {"status": "PASS"}

    def fake_data_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("data_refresh")
        return {"steps": [{"name": "universe"}, {"name": "daily_bars"}, {"name": "money_flow"}]}

    result = mod.refresh_analytics_after_run(
        analytics_store_module=FakeStore,
        analytics_checks_module=FakeChecks,
        data_refresher=fake_data_refresher,
    )

    if calls != ["analytics_dir", "data_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["data_refresh"]["steps"][0]["name"] != "universe":
        raise AssertionError(result)


def test_data_artifact_refresh_generates_role_suggestions_before_trade_state() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_role_refresh_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    calls: list[str] = []

    def fake_module(**attrs):
        module = types.ModuleType("fake")
        for name, value in attrs.items():
            setattr(module, name, value)
        return module

    fake_modules = {
        "scripts.universe_refresh": fake_module(
            refresh_universe=lambda **kwargs: calls.append("universe") or {"rows": 2},
        ),
        "scripts.eastmoney_money_flow": fake_module(
            collect_money_flow_tickers=lambda **kwargs: calls.append("collect_tickers") or ["FORM", "NVDA"],
            refresh_money_flow=lambda tickers, **kwargs: calls.append("money_flow") or {"rows": []},
        ),
        "scripts.daily_bars_store": fake_module(
            refresh_daily_bars=lambda tickers, **kwargs: calls.append("daily_bars") or {"rows": []},
        ),
        "scripts.industry_roles": fake_module(
            generate_suggestions=lambda tickers, **kwargs: calls.append("role_suggestions") or {"suggestions": []},
            refresh_role_assignment_snapshot=lambda **kwargs: calls.append("role_assignments") or {"rows": []},
        ),
        "scripts.trade_state": fake_module(
            refresh_trade_state_snapshot=lambda **kwargs: calls.append("trade_state") or {"rows": []},
        ),
    }

    old_modules = {name: sys.modules.get(name) for name in fake_modules}
    old_package = sys.modules.get("scripts")
    package = types.ModuleType("scripts")
    for full_name, module in fake_modules.items():
        setattr(package, full_name.rsplit(".", 1)[1], module)
        sys.modules[full_name] = module
    sys.modules["scripts"] = package
    try:
        result = mod.refresh_data_artifacts(
            reports_root=Path("/tmp/reports"),
            content_root=Path("/tmp/content"),
            as_of_date="2026-07-02",
        )
    finally:
        for name, previous in old_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        if old_package is None:
            sys.modules.pop("scripts", None)
        else:
            sys.modules["scripts"] = old_package

    if "role_suggestions" not in calls:
        raise AssertionError(calls)
    if calls.index("role_suggestions") > calls.index("trade_state"):
        raise AssertionError(calls)
    if "role_suggestions" not in [step["name"] for step in result["steps"]]:
        raise AssertionError(result)


def test_pipeline_lock_rejects_concurrent_runner() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_lock_under_test",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        lock_path = Path(d) / "candidates-local.lock"
        first = mod.acquire_pipeline_lock(lock_path)
        with first:
            second = mod.acquire_pipeline_lock(lock_path)
            try:
                with second:
                    raise AssertionError("second lock unexpectedly acquired")
            except RuntimeError as e:
                if "already running" not in str(e):
                    raise AssertionError(e)


def main() -> None:
    tests = [
        test_full_refresh_command_includes_filter_and_rank_parameters,
        test_rank_existing_command_does_not_include_hard_filter_parameters,
        test_llm_deep_check_command_uses_candidate_limit,
        test_llm_deep_check_starts_codex_login_when_auth_missing,
        test_llm_deep_check_launches_pipeline_when_auth_ready,
        test_background_launcher_uses_systemd_run_on_linux,
        test_background_launcher_falls_back_without_systemd,
        test_pipeline_wrapper_expands_full_refresh_without_make,
        test_pipeline_wrapper_can_disable_money_flow_prefetch,
        test_pipeline_wrapper_can_disable_money_flow_prefetch_for_rank_existing,
        test_money_flow_prefetch_skips_empty_ranked_candidates_file,
        test_money_flow_prefetch_runs_for_non_empty_ranked_candidates_file,
        test_pipeline_wrapper_uses_runtime_candidate_output_dir,
        test_pipeline_wrapper_refreshes_analytics_after_successful_run,
        test_pipeline_wrapper_final_status_waits_for_analytics_refresh,
        test_refresh_analytics_runs_data_refresh_before_store_and_checks,
        test_data_artifact_refresh_generates_role_suggestions_before_trade_state,
        test_pipeline_lock_rejects_concurrent_runner,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
