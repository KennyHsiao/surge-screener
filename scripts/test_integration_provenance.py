#!/usr/bin/env python3
"""End-to-end provenance-chain test (Codex + integration re-review).

test_provenance.py exercises assert_same_run in isolation; this pins the FULL chain
surge_events → surge_features → control_features → factor_lift → module_lift →
runway_neutral → lane_runway: every derived artifact must descend from the same
surge_events run, and tampering ANY single link must be caught fail-closed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_factor_lift as rfl

GEN = "2026-06-06T16:38:51+00:00"
STALE = "2099-01-01T00:00:00+00:00"
# every DERIVED artifact in the pipeline (surge_events is the root: it carries generated_at).
DERIVED = ["surge_features", "control_features", "factor_lift",
           "module_lift", "runway_neutral", "lane_runway"]


def _chain(gen=GEN):
    return {name: {"source": {"events_generated_at": gen}} for name in DERIVED}


def test_consistent_chain_passes():
    rfl.assert_same_run("chain", GEN, **_chain())   # no raise


def test_any_single_stale_link_fails_closed():
    """Tampering ANY one artifact's fingerprint must break the chain — caught, not silent."""
    for stale in DERIVED:
        arts = _chain()
        arts[stale] = {"source": {"events_generated_at": STALE}}
        try:
            rfl.assert_same_run("chain", GEN, **arts)
            assert False, f"stale {stale} should have failed the chain"
        except SystemExit:
            pass


def test_missing_fingerprint_on_any_link_fails_closed():
    for missing in DERIVED:
        arts = _chain()
        arts[missing] = {}     # no source.events_generated_at
        try:
            rfl.assert_same_run("chain", GEN, **arts)
            assert False, f"missing-provenance {missing} should have failed"
        except SystemExit:
            pass


def test_root_events_missing_fails_closed():
    """No surge_events generated_at to anchor the chain ⇒ refuse everything."""
    try:
        rfl.assert_same_run("chain", None, **_chain())
        assert False, "missing root fingerprint should fail"
    except SystemExit:
        pass


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all integration-provenance tests passed")
