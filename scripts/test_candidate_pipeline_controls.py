#!/usr/bin/env python3
"""Tests for Today Decision candidate-pipeline launch command construction."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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


def test_llm_deep_check_starts_claude_login_when_auth_missing() -> None:
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
            "command": ["claude", "auth", "login"],
            "log_path": "/tmp/claude-auth.log",
        }

    def fake_process_factory(*args, **kwargs):
        calls["pipeline"] += 1
        raise AssertionError("pipeline must wait for Claude login")

    try:
        meta = mod.launch_background(
            params,
            auth_checker=fake_auth_checker,
            login_starter=fake_login_starter,
            process_factory=fake_process_factory,
        )
    finally:
        mod.claude_auth_flow.clear_pending_request()

    if meta["mode"] != "claude_auth_login":
        raise AssertionError(meta)
    if meta["mode_label"] != "Claude 登入中":
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

    if len(steps) != 2:
        raise AssertionError(steps)
    flattened = [part for step in steps for part in step.argv]
    if "make" in flattened:
        raise AssertionError(flattened)
    if "scripts/01_hard_filter.py" not in steps[0].argv:
        raise AssertionError(steps)
    if "scripts/03_rank_candidates.py" not in steps[1].argv:
        raise AssertionError(steps)
    if "--limit" not in steps[1].argv or "12" not in steps[1].argv:
        raise AssertionError(steps[1].argv)
    if "--options-gate-limit" not in steps[1].argv or "4" not in steps[1].argv:
        raise AssertionError(steps[1].argv)


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
    if expected_filter not in steps[0].argv or expected_filter not in steps[1].argv:
        raise AssertionError(steps)
    if expected_ranked not in steps[1].argv:
        raise AssertionError(steps)


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
        test_llm_deep_check_starts_claude_login_when_auth_missing,
        test_llm_deep_check_launches_pipeline_when_auth_ready,
        test_pipeline_wrapper_expands_full_refresh_without_make,
        test_pipeline_wrapper_uses_runtime_candidate_output_dir,
        test_pipeline_lock_rejects_concurrent_runner,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
