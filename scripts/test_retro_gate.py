#!/usr/bin/env python3
"""Regression: the canonical gate (retro_factor_lift.is_recommendations_blocked) is
FAIL-CLOSED. It must re-derive the decision from the safety fields — never trust a
stored recommendations_blocked=False alone — so a stale/delisted/hand-edited artifact
cannot fail open (Codex C-1 review)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_factor_lift as rfl


def _meta(**cov):
    base = {"sample_experiment": False, "survivorship_bias": False,
            "membership_stale": False, "delisted_data_gap": False}
    base.update(cov)
    return {"recommendations_blocked": False, "low_confidence": False, "coverage": base}


def test_clean_point_in_time_unblocks():
    assert rfl.is_recommendations_blocked(_meta()) is False


def test_delisted_gap_blocks_even_if_stored_unblocked():
    assert rfl.is_recommendations_blocked(_meta(delisted_data_gap=True)) is True


def test_stale_membership_blocks_even_if_stored_unblocked():
    assert rfl.is_recommendations_blocked(_meta(membership_stale=True)) is True


def test_survivorship_blocks():
    assert rfl.is_recommendations_blocked(_meta(survivorship_bias=True)) is True


def test_stored_blocked_blocks():
    m = _meta()
    m["recommendations_blocked"] = True
    assert rfl.is_recommendations_blocked(m) is True


def test_missing_safety_fields_fail_closed():
    assert rfl.is_recommendations_blocked({"recommendations_blocked": False}) is True


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all canonical-gate fail-closed tests passed")
