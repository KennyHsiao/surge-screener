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


_EV_GEN = "EV-FIXTURE"      # the fingerprints the fixture siblings (written in main) carry
_SF_GEN = "SF-FIXTURE"


def _lift(factors, *, blocked=True, source=True, floor=0.0):
    """Minimal factor_lift.json-shaped payload + canonical gate fields. By default it descends
    from the fixture siblings (source=True) and records a numeric liquidity floor, so
    lift_provenance_ok passes — tests that probe the provenance gate flip source/floor."""
    # Unblocked coverage must satisfy the FULL canonical gate (Codex C-1): all four safety fields
    # explicitly False, else is_recommendations_blocked fails closed (the prior fixture omitted
    # membership_stale / delisted_data_gap, so this test was silently asserting a blocked run).
    cov = ({"sample_experiment": True, "survivorship_bias": True} if blocked
           else {"sample_experiment": False, "survivorship_bias": False,
                 "membership_stale": False, "delisted_data_gap": False})
    if floor is not None:
        cov["liquidity_filter"] = {"min_dollar_vol": floor}
    gate = ({"recommendations_blocked": True, "low_confidence": True}
            if blocked else {"recommendations_blocked": False, "low_confidence": False})
    out = {**gate, "coverage": cov, "tables": {"ALL": {"factors": factors}}}
    if source:
        out["source"] = {"events_generated_at": _EV_GEN, "features_generated_at": _SF_GEN}
    return out


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


def test_stale_or_floorless_lift_blocks():
    """Codex r15: an unblocked-gate lift must STILL block the band when its provenance fails —
    cross-run source, or an absent liquidity floor (unknown cohort). Defends live_factors against
    weighting live flags on a stale/forged/floor-less lift."""
    # mismatched source (cross-run) → blocked even though the gate says unblocked; provenance_ok
    # False marks it GARBAGE so the batch UI suppresses the band (Codex r20).
    stale = _lift(_FACTORS, blocked=False)
    stale["source"] = {"events_generated_at": "OTHER-RUN", "features_generated_at": _SF_GEN}
    _s = L.score_surge({"a": True}, stale)
    assert _s["blocked"] is True and _s["provenance_ok"] is False
    # absent liquidity floor → blocked + provenance_ok False
    floorless = _lift(_FACTORS, blocked=False, floor=None)
    _f = L.score_surge({"a": True}, floorless)
    assert _f["blocked"] is True and _f["provenance_ok"] is False
    # missing source entirely → blocked + provenance_ok False
    nosrc = _lift(_FACTORS, blocked=False, source=False)
    assert L.score_surge({"a": True}, nosrc)["provenance_ok"] is False
    # a fresh, same-run, floored lift is provenance_ok True (directional band shows in batch)
    assert L.score_surge({"a": True}, _lift(_FACTORS, blocked=False))["provenance_ok"] is True
    # GARBAGE lift zeroes EVERY lift-derived field at the source (Codex r20 round-3) — no match
    # counts / band / score can leak to any surface (incl. the batch triage table).
    g = L.score_surge({"a": True, "b": True, "c": True}, stale)   # would be high band if trusted
    assert g["band_level"] == 0 and g["score"] == 0.0
    assert g["n_matched"] == 0 and g["n_validated"] == 0
    assert g["matched"] == [] and g["unmatched"] == [] and g["insufficient"] == []


def test_forged_safe_coverage_locks():
    """Codex r20 round-5: a same-run, floored lift whose coverage self-reports UNBLOCKED while the
    AUTHORITATIVE surge_events imply blocked (the r18 forge class) must be GARBAGE — locked
    zero-field result with provenance_ok False — never a directional band with real counts."""
    import json as _json
    import tempfile
    forged = _lift(_FACTORS, blocked=False)         # coverage all-safe + recommendations_blocked F
    real_ev = L.EVENTS_PATH
    try:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "surge_events.json").write_text(_json.dumps({
                "generated_at": _EV_GEN,             # same-run token still matches (forge keeps it)
                "point_in_time_membership": True,
                "membership_stale": True,            # …but events say BLOCKED
                "delisted_data_gap": True}))
            L.EVENTS_PATH = d / "surge_events.json"
            r = L.score_surge({"a": True, "b": True, "c": True}, forged)
    finally:
        L.EVENTS_PATH = real_ev
    assert r["provenance_ok"] is False and r["blocked"] is True
    assert r["band_level"] == 0 and r["score"] == 0.0
    assert r["n_matched"] == 0 and r["matched"] == []


def test_malformed_lift_does_not_crash():
    """Codex r20 round-4: a garbage lift with schema drift (string lift/support) must return the
    LOCKED result without traversing tables (provenance gate FIRST), not raise; and a provenanced
    lift with a malformed row treats it as zero weight rather than crashing the page."""
    bad = _lift([{"factor": "a", "lift": "3.0x", "verdict": "VALIDATED", "support": "lots"}],
                blocked=False, source=False)            # no source → garbage → early lock
    g = L.score_surge({"a": True}, bad)
    assert g["provenance_ok"] is False and g["blocked"] is True
    assert g["n_matched"] == 0 and g["score"] == 0.0    # zeroed, and no TypeError raised
    ok = _lift([{"factor": "a", "dimension": "D", "subfactor": "s", "desc": "d",
                 "lift": "3.0x", "verdict": "VALIDATED", "support": "lots"}], blocked=False)
    r = L.score_surge({"a": True}, ok)                  # provenanced + malformed row → weight 0
    assert r["provenance_ok"] is True and r["score"] == 0.0


def test_score_surge_none_flags():
    assert L.score_surge(None, _lift(_FACTORS)) is None


def test_match_archetypes_smoke():
    all_true = {k: True for k in rr.FACTOR_DEFS}
    arch = L.match_archetypes(all_true)
    assert isinstance(arch, list) and len(arch) >= 1
    assert all("name" in a for a in arch)
    assert L.match_archetypes({k: None for k in rr.FACTOR_DEFS}) == []


def main() -> int:
    import json
    import tempfile
    tests = [test_factor_weight_bounds, test_band_discriminates,
             test_none_excluded_from_denominator, test_blocked_inherits_canonical_gate,
             test_stale_or_floorless_lift_blocks, test_forged_safe_coverage_locks,
             test_malformed_lift_does_not_crash,
             test_score_surge_none_flags, test_match_archetypes_smoke]
    passed = 0
    # Point live_factors at FIXTURE siblings whose generated_at matches _lift's source, so the
    # r15 provenance gate passes by default; the dedicated test flips source/floor to break it.
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # unblocked point-in-time run (Codex r18 authoritative gate): events must PROVE PIT + not
        # stale + no delisted gap, else events_implied_block force-blocks the band.
        (d / "surge_events.json").write_text(json.dumps({
            "generated_at": _EV_GEN, "point_in_time_membership": True,
            "membership_stale": False, "delisted_data_gap": False}))
        (d / "surge_features.json").write_text(json.dumps({"generated_at": _SF_GEN}))
        L.EVENTS_PATH, L.FEATURES_PATH = d / "surge_events.json", d / "surge_features.json"
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
