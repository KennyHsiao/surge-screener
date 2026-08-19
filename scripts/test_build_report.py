#!/usr/bin/env python3
"""Offline tests for the final confirmed-picks report contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_report_under_test", ROOT / "scripts" / "04_build_report.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load 04_build_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def confirmed_rows() -> list[dict]:
    return [
        {
            "ticker": "AAA",
            "dd_verdict": "CONFIRMED",
            "final_score": 81,
            "final_recommendation": "可驗證的 AAA thesis",
            "suggested_entry_zone": "$10-$11",
            "suggested_stop": "$9",
            "suggested_size_pct": 1.5,
            "short_thesis_summary": "AAA risk",
        },
        {
            "ticker": "BBB",
            "dd_verdict": "CONFIRMED",
            "final_score": 77,
            "final_recommendation": "可驗證的 BBB thesis",
            "suggested_entry_zone": "$20-$21",
            "suggested_stop": "$18",
            "suggested_size_pct": 1.0,
            "short_thesis_summary": "BBB risk",
        },
    ]


def valid_report() -> dict:
    return {
        "report_date": "2026-08-17",
        "regime_summary": "neutral",
        "total_confirmed": 2,
        "ranked_picks": [
            {"rank": 1, "ticker": "AAA", "final_score": 81, "verdict": "BUY"},
            {"rank": 2, "ticker": "BBB", "final_score": 77, "verdict": "BUY"},
        ],
        "cross_candidate_commentary": "",
        "portfolio_notes": "",
    }


def test_valid_report_requires_exact_confirmed_ticker_set() -> None:
    mod = load_module()
    report = valid_report()
    validated = mod.validate_final_report(report, {"confirmed": confirmed_rows()})
    if validated is not report:
        raise AssertionError("validator should return the validated object")

    invented = valid_report()
    invented["ranked_picks"][1]["ticker"] = "FAKE"
    try:
        mod.validate_final_report(invented, {"confirmed": confirmed_rows()})
    except ValueError as exc:
        if "confirmed" not in str(exc).lower():
            raise
    else:
        raise AssertionError("invented ticker must be rejected")


def test_duplicate_or_count_mismatch_is_rejected() -> None:
    mod = load_module()
    duplicate = valid_report()
    duplicate["ranked_picks"][1]["ticker"] = "AAA"
    for report in (duplicate, {**valid_report(), "total_confirmed": 1}):
        try:
            mod.validate_final_report(report, {"confirmed": confirmed_rows()})
        except ValueError:
            pass
        else:
            raise AssertionError(report)

    malformed_dd = confirmed_rows()
    malformed_dd[0].pop("final_score")
    try:
        mod.validate_final_report(valid_report(), {"confirmed": malformed_dd})
    except ValueError as exc:
        if "final_score" not in str(exc):
            raise
    else:
        raise AssertionError("confirmed DD rows require a grounded final score")

    try:
        mod.validate_final_report(
            valid_report(),
            {"confirmed": confirmed_rows(), "confirmed_count": 1},
        )
    except ValueError as exc:
        if "confirmed_count" not in str(exc):
            raise
    else:
        raise AssertionError("declared DD confirmed_count must match source rows")

    try:
        mod.validate_final_report(valid_report(), {"confirmed": ["AAA", "BBB"]})
    except ValueError as exc:
        if "list of objects" not in str(exc):
            raise
    else:
        raise AssertionError("malformed DD rows must not be silently discarded")


def test_deterministic_fallback_uses_only_confirmed_source_values() -> None:
    mod = load_module()
    report = mod.build_deterministic_report(
        {"scan_date": "2026-08-17", "vix_level": 18},
        {"confirmed": confirmed_rows()},
    )

    if report["total_confirmed"] != 2:
        raise AssertionError(report)
    if [row["ticker"] for row in report["ranked_picks"]] != ["AAA", "BBB"]:
        raise AssertionError(report)
    first = report["ranked_picks"][0]
    if first["entry_zone"] != "$10-$11" or first["position_size_pct"] != 1.5:
        raise AssertionError(first)
    if any(row["ticker"] == "FAKE" for row in report["ranked_picks"]):
        raise AssertionError(report)


def test_canonicalization_replaces_llm_execution_values() -> None:
    mod = load_module()
    report = valid_report()
    report["ranked_picks"][0].update({
        "final_score": 999,
        "verdict": "STRONG_BUY",
        "thesis": "invented",
        "entry_zone": "$1-$2",
        "stop_loss": "$0",
        "position_size_pct": 99,
        "key_risk": "none",
    })
    canonical = mod.canonicalize_final_report(
        report,
        {"confirmed": confirmed_rows()},
        expected_report_date="2026-08-17",
    )
    first = canonical["ranked_picks"][0]
    expected = {
        "final_score": 81,
        "verdict": "BUY",
        "thesis": "可驗證的 AAA thesis",
        "entry_zone": "$10-$11",
        "stop_loss": "$9",
        "position_size_pct": 1.5,
        "key_risk": "AAA risk",
    }
    for key, value in expected.items():
        if first.get(key) != value:
            raise AssertionError((key, first))

    stale = valid_report()
    stale["report_date"] = "2026-08-16"
    try:
        mod.canonicalize_final_report(
            stale,
            {"confirmed": confirmed_rows()},
            expected_report_date="2026-08-17",
        )
    except ValueError as exc:
        if "report_date" not in str(exc):
            raise
    else:
        raise AssertionError("stale report date must fail closed")


def main() -> None:
    tests = [
        test_valid_report_requires_exact_confirmed_ticker_set,
        test_duplicate_or_count_mismatch_is_rejected,
        test_deterministic_fallback_uses_only_confirmed_source_values,
        test_canonicalization_replaces_llm_execution_values,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
