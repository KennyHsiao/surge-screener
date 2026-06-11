#!/usr/bin/env python3
"""Offline, deterministic tests for the resolution contract + forward scorer (design v7 §1c, P2).

No network: classify() state machine, resolve_one() maturity/look-ahead, the non-overlap walk, per-key
(direction,bucket,support_class) separation, and validate_forecast.

Run:  .venv/bin/python scripts/test_market_thesis_forward.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import market_thesis_contract as C        # noqa: E402
import market_thesis_forward as F         # noqa: E402


def _flat_gspc(n=300):
    return pd.Series(100.0, index=pd.bdate_range("2020-01-01", periods=n))


def test_classify_states():
    assert C.classify(np.linspace(100, 104, 21)) == "看多"          # ends +4%
    assert C.classify(np.linspace(100, 96, 21)) == "看空"           # ends −4%
    assert C.classify(np.full(21, 100.0)) == "盤整"                 # whole path flat
    # breached +4% intra-window but ended +1% → neither dir nor a true range → OTHER (a denominator miss)
    path = np.concatenate([np.linspace(100, 104.5, 10), np.linspace(104.5, 101, 11)])
    assert C.classify(path) == "OTHER"
    # a +2.9% drift that stayed under θ the whole way is 盤整, NOT 看多
    assert C.classify(np.linspace(100, 102.9, 21)) == "盤整"


def test_classify_rejects_bad_path():
    for bad in ([100.0], [0.0, 100.0], [np.nan, 101.0]):
        try:
            C.classify(np.asarray(bad, float)); assert False, bad
        except ValueError:
            pass


def test_resolve_maturity_and_hit():
    g = _flat_gspc()
    # 盤整 forecast on a flat path → realized 盤整 → hit
    r = F.resolve_one({"as_of": g.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                       "support_class": "analog_supported"}, g)
    assert r["matured"] and r["realized"] == "盤整" and r["hit"] is True and r["t0_pos"] == 0
    # 看多 on the same flat path → realized 盤整 ≠ 看多 → miss
    r2 = F.resolve_one({"as_of": g.index[0].date().isoformat(), "direction": "看多", "bucket": "short",
                        "support_class": "analog_supported"}, g)
    assert r2["realized"] == "盤整" and r2["hit"] is False
    # near the end → window not elapsed → not matured (no look-ahead off the series)
    r3 = F.resolve_one({"as_of": g.index[290].date().isoformat(), "direction": "盤整", "bucket": "short",
                        "support_class": "analog_supported"}, g)
    assert r3["matured"] is False and r3["realized"] is None


def test_nonoverlap_walk():
    recs = [{"as_of": f"2020-01-{d:02d}", "t0_pos": p, "hit": True}
            for d, p in [(1, 0), (2, 10), (3, 20), (4, 40)]]
    counted = F._count_nonoverlap(recs, 20)            # H=20 → keep 0, drop 10, keep 20, keep 40
    assert [r["t0_pos"] for r in counted] == [0, 20, 40]


def test_score_per_key_and_nonoverlap_and_classes():
    g = _flat_gspc()
    def fc(pos, direction, sclass):
        return {"as_of": g.index[pos].date().isoformat(), "direction": direction, "bucket": "short",
                "support_class": sclass}
    recs = [fc(0, "盤整", "analog_supported"), fc(10, "盤整", "analog_supported"),
            fc(20, "盤整", "analog_supported"), fc(40, "盤整", "analog_supported"),
            fc(0, "盤整", "event_only")]          # different support class → SEPARATE key
    s = F.score(recs, g)
    a = s["by_key"]["盤整|short|analog_supported"]
    assert a["raw_N"] == 4 and a["counted_N"] == 3 and a["hits"] == 3 and a["hit_rate"] == 1.0
    assert a["verdict"] == "PROVISIONAL"                # counted_N < MIN_RESOLVED
    e = s["by_key"]["盤整|short|event_only"]
    assert e["counted_N"] == 1                          # never pooled with analog_supported
    assert "盤整|short|regime_only" not in s["by_key"]


def test_weekend_as_of_is_invalid_not_shifted():
    # a Saturday as_of must NOT silently map to Monday's close (future info) — fail closed (P2r1)
    g = _flat_gspc()
    sat = (g.index[0] + pd.Timedelta(days=5)).date()           # _flat_gspc starts Wed 2020-01-01 → +5 = Mon? compute a real non-session day below
    # find an actual non-session calendar day inside the range
    non_session = None
    for d in pd.date_range(g.index[0], g.index[50]):
        if d not in g.index:
            non_session = d.date().isoformat(); break
    r = F.resolve_one({"as_of": non_session, "direction": "盤整", "bucket": "short",
                       "support_class": "analog_supported"}, g)
    assert r["invalid"] == "as_of_not_a_session" and r["matured"] is False
    s = F.score([{"as_of": non_session, "direction": "盤整", "bucket": "short",
                  "support_class": "analog_supported"}], g)
    assert s["matured"] == 0 and s["invalid_count"] == 1
    assert s["invalid_records"][0]["reason"] == "as_of_not_a_session"


def test_nan_mid_path_is_data_error_not_other():
    # classify must reject ANY non-finite element; resolve_one surfaces it as invalid, never a scored OTHER
    try:
        C.classify(np.array([100.0, np.nan] + [101.0] * 19)); assert False
    except ValueError:
        pass
    g = _flat_gspc(60)
    g.iloc[5] = np.nan
    r = F.resolve_one({"as_of": g.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                       "support_class": "analog_supported"}, g)
    assert r["invalid"] == "non_finite_path" and r["matured"] is False


def test_ledger_family_invariants():
    base = {"as_of": "2026-06-10", "direction": "盤整", "bucket": "mid", "benchmark": "^GSPC",
            "support_class": "regime_only", "manifest_status": "degraded"}
    # valid regime_only ledger record
    assert F.validate_ledger_record(base, "regime_only_forecast_2026-06-10.json") == []
    # an edited degraded record posing as event_only must be rejected from the regime ledger
    forged = {**base, "support_class": "event_only"}
    assert any("support_class" in e for e in
               F.validate_ledger_record(forged, "regime_only_forecast_2026-06-10.json"))
    # a forecast_* record must be manifest ready + non-regime class
    ready = {**base, "support_class": "event_only", "manifest_status": "ready"}
    assert F.validate_ledger_record(ready, "forecast_2026-06-10.json") == []
    assert any("manifest_status" in e for e in
               F.validate_ledger_record({**ready, "manifest_status": "degraded"}, "forecast_2026-06-10.json"))
    assert any("support_class" in e for e in
               F.validate_ledger_record({**ready, "support_class": "regime_only"}, "forecast_2026-06-10.json"))
    # benchmark + filename-date pinning
    assert any("benchmark" in e for e in
               F.validate_ledger_record({**ready, "benchmark": "SPY"}, "forecast_2026-06-10.json"))
    assert any("filename" in e for e in
               F.validate_ledger_record(ready, "forecast_2026-06-11.json"))


def test_validate_forecast():
    base = {"as_of": "2020-01-01", "direction": "看多", "bucket": "short", "support_class": "event_only"}
    assert C.validate_forecast(base) == []
    assert C.validate_forecast({**base, "direction": "up"})
    assert C.validate_forecast({**base, "bucket": "weekly"})
    assert C.validate_forecast({**base, "support_class": "guess"})
    assert C.validate_forecast({**base, "as_of": None})


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print(f"  ok  {t.__name__}")
    print(f"PASS — {len(tests)} offline tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
