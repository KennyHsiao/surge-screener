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


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all provenance tests passed")
