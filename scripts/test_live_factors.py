#!/usr/bin/env python3
"""Self-contained tests for live_factors scoring/band/gate (no network).

Exercises score_surge with a hand-built factor_lift-shaped payload so CI never
touches yfinance. Asserts: band discriminates by matched-factor coverage, None is
excluded from the denominator, and the directional band inherits the canonical
fail-closed gate (is_recommendations_blocked).

Run:  .venv/bin/python scripts/test_live_factors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import live_factors as L  # noqa: E402
import retro_reconstruct as rr  # noqa: E402


def _lift(factors, *, blocked=True):
    """Minimal factor_lift.json-shaped payload + canonical gate fields."""
    gate = ({"recommendations_blocked": True, "low_confidence": True,
             "coverage": {"sample_experiment": True, "survivorship_bias": True}}
            if blocked else
            {"recommendations_blocked": False, "low_confidence": False,
             "coverage": {"sample_experiment": False, "survivorship_bias": False}})
    return {**gate, "tables": {"ALL": {"factors": factors}}}


_FACTORS = [
    {"factor": "a", "dimension": "Dim1", "subfactor": "1a", "desc": "A",
     "lift": 3.0, "verdict": "VALIDATED", "support": 30},
    {"factor": "b", "dimension": "Dim1", "subfactor": "1b", "desc": "B",
     "lift": 1.0, "verdict": "NOISE", "support": 20},
    {"factor": "c", "dimension": "Dim5", "subfactor": "5a", "desc": "C",
     "lift": 0.5, "verdict": "CONTRARIAN", "support": 15},
]


def test_factor_weight_bounds():
    assert L._factor_weight({"lift": None, "support": 10}) == 0.0
    assert L._factor_weight({"lift": 0, "support": 10}) == 0.0
    assert L._factor_weight({"lift": 3.0, "support": 30}) > 0
    assert (L._factor_weight({"lift": 2.0, "support": 100})
            > L._factor_weight({"lift": 2.0, "support": 2}))  # support shrinkage
    assert L._factor_weight({"lift": 999, "support": 10 ** 9}) <= (1.0 + L._LIFT_CAP) + 1e-9


def test_band_discriminates():
    lift = _lift(_FACTORS)
    hi = L.score_surge({"a": True, "b": True, "c": True}, lift)
    half = L.score_surge({"a": True, "b": False, "c": False}, lift)
    lo = L.score_surge({"a": False, "b": False, "c": False}, lift)
    assert hi["band_level"] >= half["band_level"] >= lo["band_level"]
    assert hi["score"] >= half["score"] >= lo["score"] == 0.0
    assert hi["n_matched"] == 3 and lo["n_matched"] == 0
    assert hi["n_validated"] == 3


def test_none_excluded_from_denominator():
    lift = _lift(_FACTORS)
    with_false = L.score_surge({"a": True, "b": False, "c": False}, lift)
    with_none = L.score_surge({"a": True, "b": False, "c": None}, lift)
    assert any(e["factor"] == "c" for e in with_none["insufficient"])
    assert with_none["score"] >= with_false["score"]  # unknown not penalised into denom


def test_blocked_inherits_canonical_gate():
    assert L.score_surge({"a": True}, _lift(_FACTORS, blocked=True))["blocked"] is True
    assert L.score_surge({"a": True}, _lift(_FACTORS, blocked=False))["blocked"] is False


def test_score_surge_none_flags():
    assert L.score_surge(None, _lift(_FACTORS)) is None


def test_match_archetypes_smoke():
    all_true = {k: True for k in rr.FACTOR_DEFS}
    arch = L.match_archetypes(all_true)
    assert isinstance(arch, list) and len(arch) >= 1
    assert all("name" in a for a in arch)
    assert L.match_archetypes({k: None for k in rr.FACTOR_DEFS}) == []


def main() -> int:
    tests = [test_factor_weight_bounds, test_band_discriminates,
             test_none_excluded_from_denominator, test_blocked_inherits_canonical_gate,
             test_score_surge_none_flags, test_match_archetypes_smoke]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"live_factors tests: {passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
