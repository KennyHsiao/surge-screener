#!/usr/bin/env python3
"""Behavioral tests for the shadow-only promotion reachability contract."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    path = ROOT / "scripts" / "promotion_reachability.py"
    spec = importlib.util.spec_from_file_location("promotion_reachability_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _manifest(mod, maxima: dict[str, float | None]) -> dict:
    return {
        "schema_version": mod.CAPABILITY_SCHEMA_VERSION,
        "mode": "shadow",
        "authoritative_for_scoring": False,
        "dimensions": {
            name: {
                "limit": mod.SCORE_LIMITS[name],
                "max_supported_score": maxima[name],
                "sources": ["test_fixture"],
                "missing_reasons": (
                    [] if maxima[name] == mod.SCORE_LIMITS[name]
                    else ["fixture_capability_limit"]
                ),
            }
            for name in mod.SCORE_LIMITS
        },
    }


def _row(mod, scores: dict[str, float], *, mode: str = "full") -> dict:
    return {
        "ticker": "TEST",
        "scores": dict(scores),
        "scoring_mode": mode,
        "composite_score": sum(scores.values()),
        "regime_adjusted_score": sum(scores.values()),
        "verdict": "WATCHLIST",
        "due_diligence_required": False,
    }


def _split_total(mod, total: int) -> dict[str, float]:
    remaining = total
    out: dict[str, float] = {}
    for name, limit in mod.SCORE_LIMITS.items():
        out[name] = min(limit, remaining)
        remaining -= int(out[name])
    assert remaining == 0
    return out


def test_exact_64_65_boundaries() -> None:
    mod = _load_module()
    scores = {name: 0 for name in mod.SCORE_LIMITS}
    row = _row(mod, scores)

    below = mod.build_candidate_diagnostic(row, _manifest(mod, _split_total(mod, 64)), 1.0)
    at = mod.build_candidate_diagnostic(row, _manifest(mod, _split_total(mod, 65)), 1.0)

    assert below["state"] == "not_reachable"
    assert below["adjusted_ceiling"] == 64
    assert below["threshold"] == 65
    assert at["state"] == "reachable"
    assert at["adjusted_ceiling"] == 65


def test_adjusted_ceiling_uses_production_verdict_rounding() -> None:
    mod = _load_module()
    scores = {name: 0 for name in mod.SCORE_LIMITS}
    row = _row(mod, scores)
    maxima = _split_total(mod, 64)
    maxima["institutional"] += 0.96

    diagnostic = mod.build_candidate_diagnostic(row, _manifest(mod, maxima), 1.0)

    assert diagnostic["evidence_ceiling"] == 64.96
    assert diagnostic["adjusted_ceiling"] == 65
    assert diagnostic["state"] == "reachable"


def test_technical_ceiling_applies_existing_no_volume_cap() -> None:
    mod = _load_module()
    inputs = {
        key: {"status": "available", "value": False}
        for key in mod.TECHNICAL_INPUTS
    }
    for key in ("volume_ratio_20d", "close_position", "price_change_1d"):
        inputs[key] = {"status": "missing", "reason": "source_unavailable"}
    for key in mod.UNSUPPORTED_TECHNICAL_PATTERNS:
        inputs[key] = {"status": "missing", "reason": "detector_not_implemented"}
    manifest = mod.build_layer1_capabilities(
        technical_evidence={"schema_version": "technical_evidence_v1", "inputs": inputs},
        news=[],
        options_flow=None,
        sentiment=None,
        fundamentals=None,
        institutional=None,
        sector=None,
        analyst=None,
        regime_context=None,
    )

    assert manifest["dimensions"]["technical"]["max_supported_score"] == 10


def test_composite_ceiling_maximizes_around_cross_dimension_caps() -> None:
    mod = _load_module()
    maxima = {
        "technical": 10,
        "catalyst": 16,
        "sentiment": 13,
        "institutional": 10,
        "sector_market": 3,
        "options_flow": 20,
        "analyst": 8,
    }
    row = _row(mod, {name: 0 for name in mod.SCORE_LIMITS})

    diagnostic = mod.build_candidate_diagnostic(row, _manifest(mod, maxima), 1.0)

    assert diagnostic["evidence_ceiling"] == 73.98
    assert diagnostic["ceiling_score_vector"]["sentiment"] == 11.99
    assert diagnostic["ceiling_score_vector"]["options_flow"] == 14.99
    assert diagnostic["ceiling_adjustments"] == []
    assert diagnostic["state"] == "reachable"


def test_low_regime_existing_threshold_is_reported_unreachable() -> None:
    mod = _load_module()
    full = {name: float(limit) for name, limit in mod.SCORE_LIMITS.items()}
    row = _row(mod, {name: 0 for name in mod.SCORE_LIMITS})

    diagnostic = mod.build_candidate_diagnostic(row, _manifest(mod, full), 0.7)

    assert diagnostic["threshold"] == 72
    assert diagnostic["evidence_ceiling"] == 100
    assert diagnostic["adjusted_ceiling"] == 70
    assert diagnostic["state"] == "not_reachable"


def test_current_free_sources_have_a_below_threshold_ceiling() -> None:
    mod = _load_module()
    technical_inputs = {
        key: {"status": "available", "value": False}
        for key in mod.TECHNICAL_INPUTS
    }
    for key in mod.UNSUPPORTED_TECHNICAL_PATTERNS:
        technical_inputs[key] = {"status": "missing", "reason": "detector_not_implemented"}
    technical = {"schema_version": "technical_evidence_v1", "inputs": technical_inputs}
    capabilities = mod.build_layer1_capabilities(
        technical_evidence=technical,
        news=[],
        options_flow={
            "source": "yfinance_free",
            "options_analysis": {"available": True, "max_possible": 11},
        },
        sentiment={"sources_available": ["stocktwits", "reddit"]},
        fundamentals={"source": "yfinance_free", "sector": "Technology"},
        institutional={
            "source": "yfinance_free",
            "top_institutional_holders": [{"pct_change": 1.2}],
            "insider_6m": {"purchase_shares": 1000, "purchase_trans": 2},
        },
        sector={
            "candidate_sector": {"quadrant": "Leading"},
            "as_of": "2026-08-20",
        },
        analyst={
            "rating_distribution": {"buy": 8},
            "price_targets": {"upside_pct": 20},
            "recent_actions": [{"date": "2026-08-01", "action": "up"}],
            "estimate_revisions": {"eps_curr_q": {"up_last_30d": 2}},
        },
        regime_context={"spy_vs_50dma": "above", "vix_level": 18},
        source_configuration={"polygon_news": False, "unusual_whales": False},
    )
    row = _row(mod, {name: 0 for name in mod.SCORE_LIMITS})
    diagnostic = mod.build_candidate_diagnostic(row, capabilities, 1.0)

    assert diagnostic["state"] == "not_reachable"
    assert diagnostic["adjusted_ceiling"] < diagnostic["threshold"] == 65
    assert capabilities["dimensions"]["catalyst"]["max_supported_score"] == 0
    assert "layer1_sec_8k_contract_unavailable" in capabilities["dimensions"]["catalyst"]["missing_reasons"]
    assert capabilities["dimensions"]["sentiment"]["max_supported_score"] == 3
    assert capabilities["dimensions"]["options_flow"]["max_supported_score"] == 11


def test_unsupported_credit_is_reported_without_mutation() -> None:
    mod = _load_module()
    scores = {name: 0 for name in mod.SCORE_LIMITS}
    scores["sentiment"] = 5
    row = _row(mod, scores)
    before = copy.deepcopy(row)
    maxima = {name: float(limit) for name, limit in mod.SCORE_LIMITS.items()}
    maxima["sentiment"] = 3

    diagnostic = mod.build_candidate_diagnostic(row, _manifest(mod, maxima), 1.0)

    assert row == before
    assert diagnostic["unsupported_credit"] == [{
        "dimension": "sentiment",
        "awarded_score": 5,
        "max_supported_score": 3,
        "delta": 2,
    }]


def test_unknown_inputs_fail_closed() -> None:
    mod = _load_module()
    zeros = {name: 0 for name in mod.SCORE_LIMITS}
    valid = _manifest(mod, {name: float(limit) for name, limit in mod.SCORE_LIMITS.items()})
    malformed = copy.deepcopy(valid)
    malformed["dimensions"]["technical"]["max_supported_score"] = 31

    assert mod.build_candidate_diagnostic(_row(mod, zeros), None, 1.0)["state"] == "unknown"
    assert mod.build_candidate_diagnostic(_row(mod, zeros), malformed, 1.0)["state"] == "unknown"
    assert mod.build_candidate_diagnostic(_row(mod, zeros, mode="fast"), valid, 1.0)["state"] == "unknown"

    diagnosed = _row(mod, zeros)
    diagnosed["promotion_reachability"] = mod.build_candidate_diagnostic(diagnosed, valid, 1.0)
    partial = mod.summarize_run([diagnosed], multiplier=1.0, total_candidates=2)
    assert partial["state"] == "unknown"
    assert partial["unknown_reasons"] == ["incomplete_cohort"]


def test_complete_run_summarizes_candidate_evidence() -> None:
    mod = _load_module()
    zeros = {name: 0 for name in mod.SCORE_LIMITS}
    maxima = _split_total(mod, 64)
    manifest = _manifest(mod, maxima)
    rows = []
    for ticker in ("AAA", "BBB"):
        row = _row(mod, zeros)
        row["ticker"] = ticker
        row["promotion_reachability"] = mod.build_candidate_diagnostic(row, manifest, 1.0)
        rows.append(row)

    summary = mod.summarize_run(rows, multiplier=1.0, total_candidates=2)

    assert summary["schema_version"] == mod.RUN_SCHEMA_VERSION
    assert summary["state"] == "not_reachable"
    assert summary["candidate_count"] == 2
    assert summary["diagnosed_candidate_count"] == 2
    assert summary["candidate_adjusted_ceiling_max"] == 64
    assert summary["unsupported_credit_count"] == 0
    assert summary["authoritative_for_promotion"] is False


def test_shadow_core_has_no_io_or_trading_writer_dependency() -> None:
    source = (ROOT / "scripts" / "promotion_reachability.py").read_text(encoding="utf-8")
    forbidden = (
        "httpx",
        "requests",
        "subprocess",
        "os.environ",
        "performance_ledger",
        "06_append_ledger",
        "publish_reports",
        ".write_text(",
        "open(",
    )
    found = [token for token in forbidden if token in source]
    assert found == []


def test_shadow_faults_fail_soft_to_unknown() -> None:
    mod = _load_module()
    zeros = {name: 0 for name in mod.SCORE_LIMITS}
    row = _row(mod, zeros)

    original_capabilities = mod.build_layer1_capabilities
    original_candidate = mod.build_candidate_diagnostic
    original_summary = mod.summarize_run
    try:
        mod.build_layer1_capabilities = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("secret detail"))
        capabilities = mod.safe_build_layer1_capabilities()
        assert all(
            item["max_supported_score"] is None
            for item in capabilities["dimensions"].values()
        )
        assert "secret detail" not in str(capabilities)

        mod.build_candidate_diagnostic = lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))
        candidate = mod.safe_build_candidate_diagnostic(row, capabilities, 1.0)
        assert candidate["state"] == "unknown"
        assert candidate["unknown_reasons"] == ["shadow_candidate_diagnostic_error"]

        mod.summarize_run = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        summary = mod.safe_summarize_run([row], multiplier=1.0, total_candidates=1)
        assert summary["state"] == "unknown"
        assert summary["unknown_reasons"] == ["shadow_run_summary_error"]
    finally:
        mod.build_layer1_capabilities = original_capabilities
        mod.build_candidate_diagnostic = original_candidate
        mod.summarize_run = original_summary


def main() -> None:
    tests = [
        test_exact_64_65_boundaries,
        test_adjusted_ceiling_uses_production_verdict_rounding,
        test_technical_ceiling_applies_existing_no_volume_cap,
        test_composite_ceiling_maximizes_around_cross_dimension_caps,
        test_low_regime_existing_threshold_is_reported_unreachable,
        test_current_free_sources_have_a_below_threshold_ceiling,
        test_unsupported_credit_is_reported_without_mutation,
        test_unknown_inputs_fail_closed,
        test_complete_run_summarizes_candidate_evidence,
        test_shadow_core_has_no_io_or_trading_writer_dependency,
        test_shadow_faults_fail_soft_to_unknown,
    ]
    for test in tests:
        test()
    print(f"promotion reachability tests passed ({len(tests)})")


if __name__ == "__main__":
    main()
