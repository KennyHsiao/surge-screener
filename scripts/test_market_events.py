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
    assert stale["present"] is True and stale["fresh"] is False and stale["stale_reason"].startswith("stale_close:")
    # a close several SESSIONS old must be stale even though it is within 4 calendar days (P2r1)
    multi = E.evaluate_event("UST10Y", _fresh_market("UST10Y", 4), ASOF)   # 4 calendar days ≈ 3-4 sessions
    assert multi["fresh"] is False and multi["stale_reason"].startswith("stale_close:")
    # FUTURE data can never be fresh (look-ahead)
    fut = E.evaluate_event("UST10Y", _fresh_market("UST10Y", -3), ASOF)
    assert fut["fresh"] is False and fut["stale_reason"] == "future_released_at"
    fut_cpi = E.evaluate_event("CPI", {**_fresh_fred(), "released_at": "2026-06-20"}, ASOF)
    assert fut_cpi["fresh"] is False and fut_cpi["stale_reason"] == "future_released_at"


def test_evaluate_fomc_next_meeting():
    fut = {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-17",
           "rate_as_of": "2026-05-01"}
    assert E.evaluate_event("FOMC", fut, ASOF)["fresh"] is True
    past = {**fut, "next_meeting_at": "2026-06-01"}
    assert E.evaluate_event("FOMC", past, ASOF)["stale_reason"] == "next_meeting_passed"
    # calendar advanced past a decision but the hand-maintained rate was NOT refreshed → stale (P2r1)
    unrefreshed = {"last_decision_at": "2026-06-17", "last_rate": "x", "next_meeting_at": "2026-07-29",
                   "rate_as_of": "2026-06-01"}
    assert E.evaluate_event("FOMC", unrefreshed, "2026-06-18")["stale_reason"] == "decision_not_refreshed"
    refreshed = {**unrefreshed, "rate_as_of": "2026-06-17"}
    assert E.evaluate_event("FOMC", refreshed, "2026-06-18")["fresh"] is True
    no_field = {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-17"}
    assert E.evaluate_event("FOMC", no_field, ASOF)["stale_reason"] == "decision_not_refreshed"


def test_compute_manifest_ready_vs_degraded():
    full = {"CPI": _fresh_fred(), "JOBS": _fresh_fred(), "UST10Y": _fresh_market("UST10Y"),
            "DXY": _fresh_market("DXY"),
            "FOMC": {"last_decision_at": "2026-04-29", "last_rate": "x", "next_meeting_at": "2026-06-17",
                     "rate_as_of": "2026-05-01"}}
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


def test_fred_point_in_time_vintage():
    # the observation DATE is the statistical period, NOT the release — released_at must be the vintage
    # realtime_start, and a value not yet published at as_of must be excluded (Codex P2r2 look-ahead).
    payload = {"observations": [
        {"date": "2026-05-01", "value": "316.0", "realtime_start": "2026-06-15"},  # May CPI, published Jun 15
        {"date": "2026-04-01", "value": "315.0", "realtime_start": "2026-05-13"},
        {"date": "2026-03-01", "value": "314.0", "realtime_start": "2026-04-10"},
    ]}
    # as_of BEFORE the May release: the May value is NOT knowable → latest = April, released Mai 13
    rec = E.parse_fred_observations(payload, "2026-06-10")
    assert rec["period"] == "2026-04-01" and rec["released_at"] == "2026-05-13"
    assert rec["value"] == 315.0 and rec["prior"] == 314.0
    # as_of AFTER the May release: May becomes the latest, with its TRUE release date
    rec2 = E.parse_fred_observations(payload, "2026-06-16")
    assert rec2["period"] == "2026-05-01" and rec2["released_at"] == "2026-06-15"
    # an observation missing realtime_start can never be used
    assert E.parse_fred_observations({"observations": [
        {"date": "2026-05-01", "value": "316.0"}, {"date": "2026-04-01", "value": "315.0"}]}, "2026-06-16") is None
    # fewer than two knowable observations → None (degraded over fabricated freshness)
    assert E.parse_fred_observations({"observations": payload["observations"][:1]}, "2026-06-16") is None


def test_fred_fails_closed_without_key():
    saved = os.environ.pop("FRED_API_KEY", None)
    try:
        assert E.load_fred("CPIAUCSL", ASOF) is None  # no key ⇒ missing ⇒ manifest degraded by definition
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
