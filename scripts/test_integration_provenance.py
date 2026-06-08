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


import json

_PIT = Path(__file__).resolve().parent.parent / "reports" / "retrospective" / "sp500_pit"
# Derived artifacts the COMMITTED chain must carry source.events_generated_at on, all matching
# surge_events.generated_at. A synthetic test (above) can't catch a shipped artifact that was
# fixed in generator code but never regenerated — this loads the real files (Codex re-review).
_ARTIFACTS = ["surge_features.json", "control_features.json", "factor_lift.json",
              "module_lift.json", "runway_neutral.json", "lane_runway.json", "latest.json"]


# control_features.json is a 27MB regenerable dump that is .gitignored (NOT committed); its
# provenance is validated at RUNTIME by assert_same_run in retro_modules + the runway checks.
# The committed-chain test covers only the TRACKED artifacts — requiring control_features made
# the test pass only on a dirty workspace and FAIL on a clean checkout (Codex round-5).
_COMMITTED = [a for a in _ARTIFACTS if a != "control_features.json"]


def test_committed_sp500_pit_chain_is_same_run():
    ev = _PIT / "surge_events.json"
    if not ev.exists():
        print("  (skip committed-chain test — no sp500_pit artifacts present)")
        return
    expected = json.loads(ev.read_text(encoding="utf-8")).get("generated_at")
    arts = {}
    for name in _COMMITTED:
        p = _PIT / name
        assert p.exists(), f"committed chain missing {name}"
        arts[name] = json.loads(p.read_text(encoding="utf-8"))
    # fails fail-closed if ANY committed artifact lacks or mismatches the fingerprint
    rfl.assert_same_run("committed-chain", expected, **arts)


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all integration-provenance tests passed")
