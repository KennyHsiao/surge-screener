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
    # Same events is NOT enough (Codex round-7): a stale module_lift/latest rebuilt from OLDER
    # features/lift against the SAME events would pass assert_same_run. Check the derived-from
    # adjacency links too — each artifact must be built from the CURRENT upstream artifact.
    tag = dataset_dir.name or "root"
    sf = arts.get("surge_features.json") or {}
    sf_gen = sf.get("generated_at")
    # An EDGAR-backfilled feature set mutated its rows (Dim2/Dim4) — generated_at must have moved
    # to (at least) the EDGAR mutation time, else the freshness token is stale despite mutation
    # (Codex r10).
    if sf.get("edgar_backfilled") and sf.get("generated_at_edgar"):
        assert sf_gen >= sf.get("generated_at_edgar"), \
            f"{tag}: EDGAR-backfilled surge_features generated_at {sf_gen} predates the EDGAR " \
            f"mutation {sf.get('generated_at_edgar')} (stale freshness token)"
    fl = arts.get("factor_lift.json")
    ml = arts.get("module_lift.json")
    lt = arts.get("latest.json")
    if fl is not None and sf_gen is not None:
        assert (fl.get("source") or {}).get("features_generated_at") == sf_gen, \
            f"{tag}: factor_lift not built from the current surge_features"
    if ml is not None and sf_gen is not None:
        assert (ml.get("source") or {}).get("features_generated_at") == sf_gen, \
            f"{tag}: module_lift not built from the current surge_features"
    if lt is not None and fl is not None:
        assert (lt.get("source") or {}).get("factor_lift_generated_at") == fl.get("generated_at"), \
            f"{tag}: latest not built from the current factor_lift"
    # latest must ALSO carry the features token (Codex r16) so a rebuilt-features+stale-lift run is
    # detectable — chaining latest→factor_lift alone misses it.
    if lt is not None and sf_gen is not None:
        assert (lt.get("source") or {}).get("features_generated_at") == sf_gen, \
            f"{tag}: latest not built from the current surge_features"
    # STRICT liquidity-floor presence (Codex r14): factor_lift MUST record the effective floor,
    # and every dependent artifact MUST carry a matching source.min_dollar_vol (no default-to-0).
    if fl is not None:
        fl_floor = rfl.strict_floor(fl, "coverage", "liquidity_filter", "min_dollar_vol")
        assert fl_floor is not None, \
            f"{tag}: factor_lift missing coverage.liquidity_filter.min_dollar_vol (floor not recorded)"
        for rname in ("runway_neutral.json", "lane_runway.json", "module_lift.json"):
            art = arts.get(rname)
            if art is not None:
                af = rfl.strict_floor(art, "source", "min_dollar_vol")
                assert af is not None and af == fl_floor, \
                    f"{tag}: {rname} liquidity floor {af} != factor_lift floor {fl_floor}"
        for rname in ("runway_neutral.json", "lane_runway.json"):
            rn = arts.get(rname)
            if rn is not None and sf_gen is not None:
                assert (rn.get("source") or {}).get("features_generated_at") == sf_gen, \
                    f"{tag}: {rname} not built from the current surge_features"
    return len(arts)


def test_committed_chains_are_same_run():
    """EVERY committed retrospective dataset (root sp1500 + sp500_pit): each present tracked
    artifact must carry source.events_generated_at matching its surge_events (Codex round-6 —
    the root module_lift was unprovenanced and the sp500_pit-only test missed it)."""
    checked = sum(1 for d in (_RETRO, _RETRO / "sp500_pit")
                  if _check_committed_chain(d) is not None)
    if checked == 0:
        print("  (skip committed-chain test — no retrospective chains present)")


def _stale_features_fixtures(d: Path):
    """A dataset where factor_lift descends from the SAME events but an OLDER surge_features
    generation than the current surge_features (the EDGAR-rebuild scenario, Codex r9)."""
    import subprocess  # noqa: F401 (imported by callers)
    gen = "2026-06-06T00:00:00+00:00"
    (d / "surge_events.json").write_text(json.dumps({"generated_at": gen, "universe": "sp500_pit"}))
    (d / "surge_features.json").write_text(json.dumps({
        "generated_at": "F-NEW", "source": {"events_generated_at": gen},
        "factor_defs": {}, "features": []}))
    (d / "factor_lift.json").write_text(json.dumps({
        "generated_at": gen, "universe": "sp500_pit",
        "source": {"events_generated_at": gen, "features_generated_at": "F-OLD"},  # STALE
        "coverage": {"universe": "sp500_pit"}, "tables": {}}))
    return gen


def test_retro_report_rejects_stale_features():
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        _stale_features_fixtures(dd)
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_report.py"),
             "--lift", str(dd / "factor_lift.json"), "--no-llm"],
            capture_output=True, text=True)
        assert r.returncode != 0, f"expected refusal: {r.stdout}{r.stderr}"
        assert "features-adjacency" in r.stderr or "stale" in r.stderr, r.stderr


def test_retro_report_rejects_floorless_lift():
    """Codex r15: a factor_lift that passes same-run + features-fresh but LACKS
    coverage.liquidity_filter.min_dollar_vol (unknown liquidity cohort) must NOT be republished
    into latest.json — retro_report fails closed (no default-to-zero floor)."""
    import subprocess
    import tempfile
    gen, sf = "2026-06-06T00:00:00+00:00", "F-NEW"
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        (dd / "surge_events.json").write_text(json.dumps({"generated_at": gen, "universe": "sp500_pit"}))
        (dd / "surge_features.json").write_text(json.dumps({
            "generated_at": sf, "source": {"events_generated_at": gen},
            "factor_defs": {}, "features": []}))
        (dd / "factor_lift.json").write_text(json.dumps({
            "generated_at": gen, "universe": "sp500_pit",
            "source": {"events_generated_at": gen, "features_generated_at": sf},
            "coverage": {"universe": "sp500_pit"}, "tables": {}}))   # NO liquidity_filter
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_report.py"),
             "--lift", str(dd / "factor_lift.json"), "--no-llm"],
            capture_output=True, text=True)
        assert r.returncode != 0, f"expected refusal: {r.stdout}{r.stderr}"
        assert "min_dollar_vol" in r.stderr or "liquidity" in r.stderr, r.stderr


def test_knowledge_sync_rejects_stale_features():
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        _stale_features_fixtures(dd)
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "knowledge_sync.py"),
             "--lift", str(dd / "factor_lift.json"), "--events", str(dd / "surge_events.json")],
            capture_output=True, text=True)
        assert r.returncode != 0, f"expected refusal: {r.stdout}{r.stderr}"
        assert "features-adjacency" in r.stderr or "stale" in r.stderr, r.stderr


def test_retro_report_stamps_latest_features_token():
    """Codex r16: retro_report must write source.features_generated_at into latest.json so a
    rebuilt-features + stale-lift run is detectable (chaining latest→factor_lift alone misses it)."""
    import subprocess
    import tempfile
    gen, sf = "2026-06-06T00:00:00+00:00", "F-NEW"
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        (dd / "surge_events.json").write_text(json.dumps(
            {"generated_at": gen, "universe": "sp500_pit", "event_count": 0}))
        (dd / "surge_features.json").write_text(json.dumps({
            "generated_at": sf, "source": {"events_generated_at": gen}, "factor_defs": {}, "features": []}))
        (dd / "factor_lift.json").write_text(json.dumps({
            "generated_at": gen, "universe": "sp500_pit",
            "source": {"events_generated_at": gen, "features_generated_at": sf},
            "coverage": {"universe": "sp500_pit", "liquidity_filter": {"min_dollar_vol": 0.0}},
            "recommendations_blocked": True, "low_confidence": True, "tables": {}}))
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "retro_report.py"),
             "--lift", str(dd / "factor_lift.json"), "--no-llm"],
            capture_output=True, text=True)
        assert r.returncode == 0, f"{r.stdout}{r.stderr}"
        latest = json.loads((dd / "latest.json").read_text())
        assert (latest.get("source") or {}).get("features_generated_at") == sf, latest.get("source")


def test_knowledge_sync_rejects_floorless_lift():
    """Codex r15: knowledge_sync must refuse to stamp cards from a factor_lift that passes
    same-run + features-fresh but LACKS coverage.liquidity_filter.min_dollar_vol (cohort unknown)."""
    import subprocess
    import tempfile
    gen, sf = "2026-06-06T00:00:00+00:00", "F-NEW"
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        (dd / "surge_events.json").write_text(json.dumps({"generated_at": gen, "universe": "sp500_pit"}))
        (dd / "surge_features.json").write_text(json.dumps({
            "generated_at": sf, "source": {"events_generated_at": gen}, "factor_defs": {}, "features": []}))
        (dd / "factor_lift.json").write_text(json.dumps({
            "generated_at": gen, "universe": "sp500_pit",
            "source": {"events_generated_at": gen, "features_generated_at": sf},
            "coverage": {"universe": "sp500_pit"}, "tables": {}}))   # NO liquidity_filter
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "knowledge_sync.py"),
             "--lift", str(dd / "factor_lift.json"), "--events", str(dd / "surge_events.json")],
            capture_output=True, text=True)
        assert r.returncode != 0, f"expected refusal: {r.stdout}{r.stderr}"
        assert "min_dollar_vol" in r.stderr or "liquidity" in r.stderr, r.stderr


def test_oversold_rejects_refreshed_events_stale_downstream():
    """oversold _load_validation must stay BLOCKED when surge_events is refreshed but the
    surge_features/factor_lift/lane_runway trio is stale (they agree with each other on the OLD
    events, but none descends from the current surge_events) — Codex r11."""
    import tempfile
    import oversold_reversal_scan as o
    E1, E2, F = "2026-06-06T00:00:00+00:00", "2026-06-09T00:00:00+00:00", "2026-06-06T00:01:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(json.dumps({"generated_at": E2}))   # REFRESHED
        (d / "surge_features.json").write_text(json.dumps({
            "generated_at": F, "source": {"events_generated_at": E1}}))           # stale (E1)
        (d / "factor_lift.json").write_text(json.dumps({
            "source": {"events_generated_at": E1, "features_generated_at": F},
            "coverage": {}, "recommendations_blocked": True}))
        (d / "lane_runway.json").write_text(json.dumps({
            "source": {"events_generated_at": E1, "features_generated_at": F},
            "atr_move_threshold": 1.2,
            "signals": {o._TRIPLE_KEY: {"pct_lift": 2.0, "atr_neutral_lift": 1.5,
                                        "support": 99, "neutral_support": 99}}}))
        orig = o._VAL_DIR
        try:
            o._VAL_DIR = d
            v = o._load_validation("sp500")
        finally:
            o._VAL_DIR = orig
        assert v["source_provenance_ok"] is False, v
        assert v["source_blocked"] is True
        assert v["runway_independent_actionable"] is False


def test_oversold_rejects_liquidity_floor_mismatch():
    """oversold must stay BLOCKED when lane_runway was built at a different liquidity floor than
    factor_lift (same events+features, different cohort) — Codex r12."""
    import tempfile
    import oversold_reversal_scan as o
    E, F = "2026-06-06T00:00:00+00:00", "2026-06-06T00:01:00+00:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "surge_events.json").write_text(json.dumps({"generated_at": E}))
        (d / "surge_features.json").write_text(json.dumps({
            "generated_at": F, "source": {"events_generated_at": E}}))
        (d / "factor_lift.json").write_text(json.dumps({
            "source": {"events_generated_at": E, "features_generated_at": F},
            "coverage": {"liquidity_filter": {"min_dollar_vol": 1_000_000.0}},  # floor 1M
            "recommendations_blocked": True}))
        (d / "lane_runway.json").write_text(json.dumps({
            "source": {"events_generated_at": E, "features_generated_at": F, "min_dollar_vol": 0.0},  # floor 0
            "atr_move_threshold": 1.2,
            "signals": {o._TRIPLE_KEY: {"pct_lift": 2.0, "atr_neutral_lift": 1.5,
                                        "support": 99, "neutral_support": 99}}}))
        orig = o._VAL_DIR
        try:
            o._VAL_DIR = d
            v = o._load_validation("sp500")
        finally:
            o._VAL_DIR = orig
        assert v["source_provenance_ok"] is False, v
        assert v["source_blocked"] is True


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all integration-provenance tests passed")
