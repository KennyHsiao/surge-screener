#!/usr/bin/env python3
"""Tests for Today Decision candidate-pipeline launch command construction."""

from __future__ import annotations

import importlib.util
import sys
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
    cmd = mod.build_make_command(params)

    expected = [
        "candidates-local",
        "RANK_LIMIT=50",
        "OPTIONS_GATE_LIMIT=10",
        "UNIVERSE=sp1500",
        "YF_BATCH_SIZE=25",
        "MIN_DATA_COVERAGE=0.7",
        "MIN_AVG_DOLLAR_VOL=10000000",
        "MIN_MARKET_CAP=1000000000",
        "MIN_PRICE=10",
        "MAX_RET_5D=25",
        "MAX_RET_20D=55",
        "EARNINGS_EXCLUDE_DAYS=3",
    ]
    for part in expected:
        if part not in cmd:
            raise AssertionError(cmd)


def test_rank_existing_command_does_not_include_hard_filter_parameters() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="rank_existing", rank_limit=30, options_gate_limit=5)
    cmd = mod.build_make_command(params)

    if "candidates-rank-local" not in cmd:
        raise AssertionError(cmd)
    if "RANK_LIMIT=30" not in cmd or "OPTIONS_GATE_LIMIT=5" not in cmd:
        raise AssertionError(cmd)
    for forbidden in ("MIN_AVG_DOLLAR_VOL", "MIN_MARKET_CAP", "YF_BATCH_SIZE"):
        if any(part.startswith(forbidden) for part in cmd):
            raise AssertionError(cmd)


def test_llm_deep_check_command_uses_candidate_limit() -> None:
    mod = _load_controls()
    params = mod.CandidateRunParams(mode="llm_deep_check", candidate_limit=3)
    cmd = mod.build_make_command(params)

    if "candidates-score-local" not in cmd:
        raise AssertionError(cmd)
    if "CANDIDATE_LIMIT=3" not in cmd:
        raise AssertionError(cmd)
    if "RESCORE_STALE_LLM=1" not in cmd:
        raise AssertionError(cmd)


def main() -> None:
    tests = [
        test_full_refresh_command_includes_filter_and_rank_parameters,
        test_rank_existing_command_does_not_include_hard_filter_parameters,
        test_llm_deep_check_command_uses_candidate_limit,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
