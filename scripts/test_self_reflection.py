#!/usr/bin/env python3
"""Offline tests for monthly self-reflection helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "self_reflection_under_test",
        ROOT / "scripts" / "08_self_reflection.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load 08_self_reflection.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_dimension_correlations_do_not_require_scipy() -> None:
    module = load_module()
    df = pd.DataFrame(
        {
            "tech_score": [1, 2, 3, 4, 5],
            "catalyst_score": [5, 4, 3, 2, 1],
            "fwd_30d_return": [10, 20, 30, 40, 50],
        }
    )

    rows = module.compute_dimension_correlations(df)
    by_dim = {row["dimension"]: row for row in rows}

    require(by_dim["technical"]["correlation"] == 1.0,
            "technical score should have perfect positive Spearman correlation")
    require(by_dim["technical"]["verdict"] == "STRONG_KEEP",
            "technical perfect positive correlation should be STRONG_KEEP")
    require(by_dim["catalyst"]["correlation"] == -1.0,
            "catalyst score should have perfect negative Spearman correlation")
    require(by_dim["catalyst"]["verdict"] == "NEGATIVE_MISLEADING",
            "catalyst perfect negative correlation should be NEGATIVE_MISLEADING")


def main() -> None:
    tests = [
        test_dimension_correlations_do_not_require_scipy,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
