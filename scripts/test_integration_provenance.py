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

_RETRO = Path(__file__).resolve().parent.parent / "reports" / "retrospective"
# Derived artifacts the COMMITTED chain must carry source.events_generated_at on, all matching
# surge_events.generated_at. A synthetic test (above) can't catch a shipped artifact that was
# fixed in generator code but never regenerated — the committed-chain test loads the real files.
_ARTIFACTS = ["surge_features.json", "control_features.json", "factor_lift.json",
              "module_lift.json", "runway_neutral.json", "lane_runway.json", "latest.json"]


# control_features.json is a 27MB regenerable dump that is .gitignored (NOT committed); its
# provenance is validated at RUNTIME by assert_same_run in retro_modules + the runway checks.
# The committed-chain test covers only the TRACKED artifacts — requiring control_features made
# the test pass only on a dirty workspace and FAIL on a clean checkout (Codex round-5).
_COMMITTED = [a for a in _ARTIFACTS if a != "control_features.json"]


def _check_committed_chain(dataset_dir: Path):
    """assert_same_run over the committed artifacts PRESENT in one dataset dir (datasets differ:
    the root sp1500 chain has no runway/lane). Returns the count checked, or None if the dir has
    no surge_events. Fails fail-closed if any present artifact lacks/mismatches the fingerprint."""
    ev = dataset_dir / "surge_events.json"
    if not ev.exists():
        return None
    expected = json.loads(ev.read_text(encoding="utf-8")).get("generated_at")
    arts = {name: json.loads((dataset_dir / name).read_text(encoding="utf-8"))
            for name in _COMMITTED if (dataset_dir / name).exists()}
    rfl.assert_same_run(f"committed-chain:{dataset_dir.name or 'root'}", expected, **arts)
    return len(arts)


def test_committed_chains_are_same_run():
    """EVERY committed retrospective dataset (root sp1500 + sp500_pit): each present tracked
    artifact must carry source.events_generated_at matching its surge_events (Codex round-6 —
    the root module_lift was unprovenanced and the sp500_pit-only test missed it)."""
    checked = sum(1 for d in (_RETRO, _RETRO / "sp500_pit")
                  if _check_committed_chain(d) is not None)
    if checked == 0:
        print("  (skip committed-chain test — no retrospective chains present)")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all integration-provenance tests passed")
