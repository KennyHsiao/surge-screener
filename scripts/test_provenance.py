#!/usr/bin/env python3
"""Offline tests for the cross-component provenance guard (Codex + integration review).

`retro_factor_lift.assert_same_run` is the single fail-closed predicate every consumer uses
to refuse a stale / mismatched / unprovenanced artifact. Pin its fail-closed behaviour so a
refactor can't silently let a different-run artifact through.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_factor_lift as rfl

GEN = "2026-06-06T16:38:51+00:00"


def _art(fp):
    return {"source": {"events_generated_at": fp}}


def test_same_run_passes():
    rfl.assert_same_run("t", GEN, features=_art(GEN), controls=_art(GEN))  # no raise


def test_mismatch_raises():
    try:
        rfl.assert_same_run("t", GEN, controls=_art("2099-01-01T00:00:00+00:00"))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_missing_source_raises():
    try:
        rfl.assert_same_run("t", GEN, controls={})   # no source.events_generated_at
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_missing_expected_raises():
    """No surge_events generated_at to verify against ⇒ fail-closed (can't confirm anything)."""
    try:
        rfl.assert_same_run("t", None, controls=_art(GEN))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_events_fingerprint():
    assert rfl.events_fingerprint(_art(GEN)) == GEN
    assert rfl.events_fingerprint({}) is None


FGEN = "2026-06-06T17:00:00+00:00"


def _feat_art(ffp):
    return {"source": {"features_generated_at": ffp}}


def test_features_fresh_passes_on_match():
    rfl.assert_features_fresh("t", FGEN, factor_lift=_feat_art(FGEN))   # no raise


def test_features_stale_raises():
    """Same events but a lift built from an OLDER surge_features generation ⇒ fail-closed."""
    try:
        rfl.assert_features_fresh("t", FGEN, factor_lift=_feat_art("F-OLD"))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_features_missing_raises():
    try:
        rfl.assert_features_fresh("t", FGEN, factor_lift={})
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_features_missing_expected_raises():
    try:
        rfl.assert_features_fresh("t", None, factor_lift=_feat_art(FGEN))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def _ev(pit=True, stale=False, delisted=False):
    return {"point_in_time_membership": pit, "membership_stale": stale, "delisted_data_gap": delisted}


def _unblocked_meta():
    return {"recommendations_blocked": False, "low_confidence": False,
            "coverage": {"sample_experiment": False, "survivorship_bias": False,
                         "membership_stale": False, "delisted_data_gap": False}}


def test_events_implied_block():
    """surge_events independently imply blocked unless PIT-proven + not stale + no delisted gap."""
    assert rfl.events_implied_block(_ev(pit=True, stale=False, delisted=False)) is False
    assert rfl.events_implied_block(_ev(pit=False)) is True                 # current-member
    assert rfl.events_implied_block(_ev(pit=True, stale=True)) is True      # stale snapshot
    assert rfl.events_implied_block(_ev(pit=True, delisted=True)) is True   # delisted gap
    assert rfl.events_implied_block({}) is True                            # missing ⇒ block
    assert rfl.events_implied_block(None) is True
    # MISSING safety fields must fail CLOSED (Codex r18 stop-review): a forged events that sets
    # point_in_time_membership=True but OMITS membership_stale/delisted_data_gap must NOT pass.
    assert rfl.events_implied_block({"point_in_time_membership": True}) is True
    assert rfl.events_implied_block(
        {"point_in_time_membership": True, "membership_stale": False}) is True   # delisted absent
    assert rfl.events_implied_block(
        {"point_in_time_membership": True, "delisted_data_gap": False}) is True   # stale absent
    # only ALL THREE explicitly safe unblocks
    assert rfl.events_implied_block(
        {"point_in_time_membership": True, "membership_stale": False,
         "delisted_data_gap": False}) is False


def test_assert_coverage_authoritative_forge():
    """Codex r18 forge: coverage self-reports UNBLOCKED but events imply blocked ⇒ raise."""
    try:
        rfl.assert_coverage_authoritative("t", _unblocked_meta(), _ev(pit=False))  # events block
        assert False, "expected SystemExit on coverage↔events disagreement"
    except SystemExit:
        pass
    # delisted gap in events while coverage claims clean ⇒ raise
    try:
        rfl.assert_coverage_authoritative("t", _unblocked_meta(), _ev(pit=True, delisted=True))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_assert_coverage_authoritative_consistent_passes():
    """A legit unblocked run (events prove PIT + clean) passes; a blocked run (both agree) passes."""
    rfl.assert_coverage_authoritative("t", _unblocked_meta(), _ev(pit=True))   # no raise
    blocked_meta = {"recommendations_blocked": True, "coverage": {"survivorship_bias": True}}
    rfl.assert_coverage_authoritative("t", blocked_meta, _ev(pit=False))       # both block, no raise


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all provenance tests passed")
