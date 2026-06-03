#!/usr/bin/env python3
"""Self-contained tests for retro_modules' fail-closed control gating (no network).

Covers the round-3 adversarial-review finding: module lift must NOT present
per-threshold tables from a fallback or stale control baseline as valid
threshold-specific evidence. Each scenario asserts recommendations_blocked.

Run:  .venv/bin/python scripts/test_retro_modules.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _flags(rvol: bool) -> dict:
    return {"rvol_ge_2": rvol}


def _run(tmp: Path, control_features: dict) -> dict:
    """Write fixtures, run retro_modules.py, return the module_lift payload."""
    feat = {"generated_at": "G1", "features": [
        {"ticker": "AAA", "thresholds_hit": ["+30%/20d"], "flags": _flags(True)},
        {"ticker": "BBB", "thresholds_hit": ["+40%/40d"], "flags": _flags(False)},
    ]}
    # Factor lift NOT blocked by coverage, so the only gate under test is the module one.
    lift = {"coverage": {"sample_experiment": False}, "recommendations_blocked": False,
            "tables": {}}
    modules = {"modules": [{"name": "M", "factors": {"rvol_ge_2": True}}]}

    (tmp / "surge_features.json").write_text(json.dumps(feat))
    (tmp / "control_features.json").write_text(json.dumps(control_features))
    (tmp / "factor_lift.json").write_text(json.dumps(lift))
    (tmp / "modules.json").write_text(json.dumps(modules))
    out = tmp / "module_lift.json"
    r = subprocess.run(
        [sys.executable, str(HERE / "retro_modules.py"),
         "--features", str(tmp / "surge_features.json"),
         "--controls", str(tmp / "control_features.json"),
         "--lift", str(tmp / "factor_lift.json"),
         "--modules", str(tmp / "modules.json"),
         "--output", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, f"retro_modules failed: {r.stderr}"
    return json.loads(out.read_text())


def _controls(n: int, rvol: bool) -> list:
    return [{"ticker": f"C{i}", "date": "2025-01-01", "flags": _flags(rvol)} for i in range(n)]


def _full_control_file(features_gen: str = "G1") -> dict:
    return {
        "source": {"features_generated_at": features_gen},
        "controls": _controls(10, False),
        "by_threshold": {
            "+30%/20d": {"controls": _controls(10, False)},
            "+40%/40d": {"controls": _controls(10, False)},
        },
    }


def test_matched_is_not_blocked():
    """Provenance matches + every label has its own set → threshold-specific, unblocked."""
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G1"))
    assert out["control_match"] == "threshold-specific", out["control_match"]
    assert out["provenance_ok"] is True
    assert out["recommendations_blocked"] is False


def test_missing_by_threshold_blocks():
    """No by_threshold map → all-fallback baseline → blocked."""
    cf = _full_control_file("G1")
    cf.pop("by_threshold")
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf)
    assert out["control_match"] == "all-fallback", out["control_match"]
    assert out["recommendations_blocked"] is True


def test_missing_one_label_blocks():
    """Map present but missing a needed label → partial-fallback → blocked."""
    cf = _full_control_file("G1")
    cf["by_threshold"].pop("+40%/40d")
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), cf)
    assert out["control_match"] == "partial-fallback", out["control_match"]
    assert out["recommendations_blocked"] is True


def test_stale_provenance_blocks():
    """Control file from a DIFFERENT surge run (generated_at mismatch) → blocked."""
    with tempfile.TemporaryDirectory() as d:
        out = _run(Path(d), _full_control_file("G2-STALE"))
    assert out["provenance_ok"] is False
    assert out["recommendations_blocked"] is True


def main() -> int:
    tests = [test_matched_is_not_blocked, test_missing_by_threshold_blocks,
             test_missing_one_label_blocks, test_stale_provenance_blocks]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"retro_modules tests: {passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
