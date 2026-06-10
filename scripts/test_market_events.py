#!/usr/bin/env python3
"""Offline, deterministic tests for the event manifest (design v7 §1a, P2c). No network.

Exercises the per-type freshness rules, compute_manifest ready/degraded, the FOMC fixture loader, and that
FRED actuals fail closed (→ degraded) without a key.

Run:  .venv/bin/python scripts/test_market_events.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import market_events as E  # noqa: E402

ASOF = "2026-06-10"


def _fresh_market(etype, days_old=1):
    d = (__import__("pandas").Timestamp(ASOF) - __import__("pandas").Timedelta(days=days_old)).date().isoformat()
    return {"released_at": d, "value": 4.3, "delta_1d": 0.02}


def _fresh_fred(days_old=10):
    d = (__import__("pandas").Timestamp(ASOF) - __import__("pandas").Timedelta(days=days_old)).date().isoformat()
    return {"released_at": d, "value": 315.0, "prior": 314.0, "surprise": None}


def test_evaluate_missing_and_fields():
    assert E.evaluate_event("CPI", None, ASOF)["stale_reason"] == "missing"
    bad = E.evaluate_event("CPI", {"released_at": "2026-06-01", "value": 1}, ASOF)  # no prior
    assert bad["present"] is False and bad["stale_reason"].startswith("missing_fields:prior")


def test_evaluate_freshness_age():
    assert E.evaluate_event("UST10Y", _fresh_market("UST10Y", 2), ASOF)["fresh"] is True
    stale = E.evaluate_event("UST10Y", _fresh_market("UST10Y", 10), ASOF)
    assert stale["present"] is True and stale["fresh"] is False and stale["stale_reason"].startswith("stale:")


def test_evaluate_fomc_next_meeting():
    fut = {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-17"}
    assert E.evaluate_event("FOMC", fut, ASOF)["fresh"] is True
    past = {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-01"}
    assert E.evaluate_event("FOMC", past, ASOF)["stale_reason"] == "next_meeting_passed"


def test_compute_manifest_ready_vs_degraded():
    full = {"CPI": _fresh_fred(), "JOBS": _fresh_fred(), "UST10Y": _fresh_market("UST10Y"),
            "DXY": _fresh_market("DXY"),
            "FOMC": {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-17"}}
    assert E.compute_manifest(full, ASOF)["manifest_status"] == "ready"
    degraded = E.compute_manifest({**full, "CPI": None}, ASOF)
    assert degraded["manifest_status"] == "degraded" and degraded["missing"] == ["CPI"]


def test_fomc_fixture_loads_and_picks_neighbours():
    rec = E.load_fomc(ASOF)
    assert rec["last_decision_at"] == "2026-04-29" and rec["next_meeting_at"] == "2026-06-17"
    # beyond the last known meeting → no next → missing field → not present
    beyond = E.load_fomc("2027-06-01")
    assert beyond["next_meeting_at"] is None
    assert E.evaluate_event("FOMC", beyond, "2027-06-01")["present"] is False


def test_fred_fails_closed_without_key():
    saved = os.environ.pop("FRED_API_KEY", None)
    try:
        assert E.load_fred("CPIAUCSL") is None     # no key ⇒ missing ⇒ manifest degraded by definition
    finally:
        if saved is not None:
            os.environ["FRED_API_KEY"] = saved


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print(f"  ok  {t.__name__}")
    print(f"PASS — {len(tests)} offline tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
