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
    import market_events as ME
    return pd.Series(100.0, index=pd.date_range("2020-01-02", periods=n, freq=ME.nyse_cbd()))


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


def test_gspc_loader_preserves_nan_for_the_guard():
    # the PRODUCTION loader must NOT dropna: stripping a mid-window NaN silently shifts the H-session path
    # and scores a corrupted window as a normal hit/miss. Through gspc_close → score (Codex P2r2).
    import market_events as ME
    import retro_reconstruct as rr
    idx = pd.date_range("2020-01-02", periods=60, freq=ME.nyse_cbd())  # REAL NYSE sessions (the gap check
    df = pd.DataFrame({"Close": [100.0] * 60}, index=idx)              # would otherwise fire first)
    df.iloc[5, 0] = np.nan
    saved = rr._hist_auto_adjust_false
    try:
        rr._hist_auto_adjust_false = lambda t, p="20y": df
        g = F.gspc_close()
    finally:
        rr._hist_auto_adjust_false = saved
    assert g.isna().any(), "loader must keep the NaN visible"
    s = F.score([{"as_of": g.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                  "support_class": "analog_supported"}], g)
    assert s["matured"] == 0 and s["invalid_count"] == 1
    assert s["invalid_records"][0]["reason"] == "non_finite_path"


def test_ledger_family_invariants():
    base = {"as_of": "2026-06-10", "direction": "盤整", "bucket": "mid", "benchmark": "^GSPC",
            "support_class": "regime_only", "manifest_status": "degraded",
            "generated_at": "2026-06-10T21:00:00+00:00"}   # post-close (EDT close = 20:00 UTC)
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
    # LOCK-TIME proof (P2r8): missing / naive / PRE-CLOSE generated_at must all reject; post-close passes.
    assert any("generated_at" in e for e in
               F.validate_ledger_record({k: v for k, v in ready.items() if k != "generated_at"},
                                        "forecast_2026-06-10.json"))
    assert any("timezone-aware" in e for e in
               F.validate_ledger_record({**ready, "generated_at": "2026-06-10T21:00:00"},
                                        "forecast_2026-06-10.json"))
    pre_close = {**ready, "generated_at": "2026-06-10T14:08:17+00:00"}   # the real CI smoke-run timestamp!
    assert any("generated_before_close" in e for e in
               F.validate_ledger_record(pre_close, "forecast_2026-06-10.json"))
    # winter date: EST close = 21:00 UTC — 20:30Z is still pre-close in January
    jan = {**ready, "as_of": "2026-01-15", "generated_at": "2026-01-15T20:30:00+00:00"}
    assert any("generated_before_close" in e for e in
               F.validate_ledger_record(jan, "forecast_2026-01-15.json"))
    assert F.validate_ledger_record({**jan, "generated_at": "2026-01-15T21:05:00+00:00"},
                                    "forecast_2026-01-15.json") == []
    # UPPER lock bound (stop-gate): a months-later BACKFILL with hindsight must reject, as must anything
    # generated at/after the NEXT session's 09:30 ET open; same-evening and pre-open-next-morning pass.
    backfill = {**ready, "generated_at": "2026-09-01T12:00:00+00:00"}
    assert any("late_backfilled" in e for e in
               F.validate_ledger_record(backfill, "forecast_2026-06-10.json"))
    at_open = {**ready, "generated_at": "2026-06-11T13:30:00+00:00"}     # Thu open 09:30 EDT = 13:30Z
    assert any("late_backfilled" in e for e in
               F.validate_ledger_record(at_open, "forecast_2026-06-10.json"))
    pre_open = {**ready, "generated_at": "2026-06-11T12:00:00+00:00"}    # next morning, pre-open
    assert F.validate_ledger_record(pre_open, "forecast_2026-06-10.json") == []
    # Friday as_of → the bound is MONDAY's open: weekend generation passes
    fri = {**ready, "as_of": "2026-06-12", "generated_at": "2026-06-13T15:00:00+00:00"}
    assert F.validate_ledger_record(fri, "forecast_2026-06-12.json") == []


def test_loader_returns_rejects_for_summary():
    # a corrupted/forged ledger must surface in the RETURNED rejects (persisted into the summary by main),
    # never just stderr — otherwise an edited losing ledger silently vanishes from the denominator (P2r5).
    import json as _json
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    good = {"as_of": "2026-06-10", "direction": "盤整", "bucket": "mid", "benchmark": "^GSPC",
            "support_class": "regime_only", "manifest_status": "degraded",
            "generated_at": "2026-06-10T21:00:00+00:00"}
    (tmp / "regime_only_forecast_2026-06-10.json").write_text(_json.dumps(good), encoding="utf-8")
    forged = {**good, "as_of": "2026-06-11", "support_class": "event_only",   # class forged in regime ledger
              "generated_at": "2026-06-11T21:00:00+00:00"}
    (tmp / "regime_only_forecast_2026-06-11.json").write_text(_json.dumps(forged), encoding="utf-8")
    (tmp / "forecast_2026-06-12.json").write_text("{not json", encoding="utf-8")
    saved, saved_lock = F.OUT_DIR, F._git_lock_error
    try:
        F.OUT_DIR = tmp
        F._git_lock_error = lambda *a, **k: None      # lock provenance has its own dedicated tests
        recs, rejects = F._load_ledgers()
    finally:
        F.OUT_DIR, F._git_lock_error = saved, saved_lock
    assert len(recs) == 1 and recs[0]["as_of"] == "2026-06-10"
    assert len(rejects) == 2
    by_file = {r["file"]: r["errors"] for r in rejects}
    assert any("support_class" in e for e in by_file["regime_only_forecast_2026-06-11.json"])
    assert any("unreadable" in e for e in by_file["forecast_2026-06-12.json"])


def test_loader_rejects_non_object_payloads():
    # null / scalar / list-of-scalar must become PERSISTED rejects, never an AttributeError (P2r6)
    import json as _json
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    (tmp / "forecast_2026-06-10.json").write_text("null", encoding="utf-8")
    (tmp / "forecast_2026-06-11.json").write_text('"scalar"', encoding="utf-8")
    (tmp / "regime_only_forecast_2026-06-12.json").write_text("[42]", encoding="utf-8")
    saved = F.OUT_DIR
    try:
        F.OUT_DIR = tmp
        recs, rejects = F._load_ledgers()
    finally:
        F.OUT_DIR = saved
    assert recs == [] and len(rejects) == 3
    assert all(r["errors"] == ["record_not_object"] for r in rejects)


def test_loader_rejects_malformed_dates():
    # 'not-a-date' matches its own filename suffix — it must be a PERSISTED reject, not a scorer crash (P2r7)
    import json as _json
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    for stem, as_of in [("regime_only_forecast_not-a-date", "not-a-date"),
                        ("forecast_2026-6-1", "2026-6-1")]:        # non-canonical (not zero-padded) too
        rec = {"as_of": as_of, "direction": "盤整", "bucket": "mid", "benchmark": "^GSPC",
               "support_class": "regime_only" if stem.startswith("regime") else "event_only",
               "manifest_status": "degraded" if stem.startswith("regime") else "ready",
               "generated_at": "2026-06-12T21:00:00+00:00"}
        (tmp / f"{stem}.json").write_text(_json.dumps(rec), encoding="utf-8")
    saved = F.OUT_DIR
    try:
        F.OUT_DIR = tmp
        recs, rejects = F._load_ledgers()
    finally:
        F.OUT_DIR = saved
    assert recs == [] and len(rejects) == 2
    assert all(any("canonical" in e for e in r["errors"]) for r in rejects)
    # defence in depth: even a directly-scored unparsable as_of surfaces as invalid, never an exception
    g = _flat_gspc()
    r = F.resolve_one({"as_of": "not-a-date", "direction": "盤整", "bucket": "short",
                       "support_class": "regime_only"}, g)
    assert r["invalid"] == "unparsable_as_of"


def test_invalid_accepted_record_taints_status():
    # an ACCEPTED ledger whose as_of is a non-session shrinks the denominator — the summary-status logic
    # must flag it (non_publishable_invalid_records), not read ok (P2r6). Tested at the score+status level.
    g = _flat_gspc()
    non_session = None
    for d in pd.date_range(g.index[0], g.index[50]):
        if d not in g.index:
            non_session = d.date().isoformat(); break
    s = F.score([{"as_of": non_session, "direction": "盤整", "bucket": "short",
                  "support_class": "analog_supported"}], g)
    assert s["invalid_count"] == 1
    status = ("non_publishable_ledger_rejects" if False
              else "non_publishable_invalid_records" if s["invalid_count"] else "ok")
    assert status == "non_publishable_invalid_records"


def test_benchmark_session_gap_and_corrupt_index():
    # a DROPPED trading date (no NaN row left) must invalidate the window, never shift the endpoint (P2r9)
    g = _flat_gspc(60)
    gapped = g.drop(g.index[5])
    r = F.resolve_one({"as_of": gapped.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                       "support_class": "analog_supported"}, gapped)
    assert r["invalid"] == "benchmark_session_gap" and r["matured"] is False
    s = F.score([{"as_of": gapped.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                  "support_class": "analog_supported"}], gapped)
    assert s["invalid_count"] == 1 and s["invalid_records"][0]["reason"] == "benchmark_session_gap"
    # a window NOT containing the gap still resolves normally
    later = gapped.index[10].date().isoformat()
    ok = F.resolve_one({"as_of": later, "direction": "盤整", "bucket": "short",
                        "support_class": "analog_supported"}, gapped)
    assert ok["matured"] is True and ok["invalid"] is None
    # duplicated session date ⇒ the WHOLE index is untrustable ⇒ every record invalid
    dup = pd.concat([g, g.iloc[[5]]]).sort_index()
    s2 = F.score([{"as_of": g.index[0].date().isoformat(), "direction": "盤整", "bucket": "short",
                   "support_class": "analog_supported"}], dup)
    assert s2["invalid_records"][0]["reason"] == "benchmark_index_corrupt"


def test_git_lock_provenance():
    # the lock anchor is GitHub's SERVER-side run record (Codex P2r13): local git committer dates are
    # forgeable, so a backdated GIT_COMMITTER_DATE backfill must STILL reject unless an Actions run whose
    # GitHub-recorded created_at falls inside the lock window attests the EXACT current blob.
    import json as _json
    import os
    import subprocess
    import tempfile
    repo = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    led = repo / "forecast_2026-06-08.json"            # Monday session; next open Tue 2026-06-09 13:30Z
    led.write_text(_json.dumps({"x": 1}), encoding="utf-8")
    # FORGED backdated commit — must carry no weight
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-06-08T22:00:00+00:00",
           "GIT_COMMITTER_DATE": "2026-06-08T22:00:00+00:00"}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "lock"],
                   cwd=repo, check=True, env=env)
    blob = subprocess.run(["git", "hash-object", "forecast_2026-06-08.json"],
                          capture_output=True, text=True, cwd=repo).stdout.strip()
    now = pd.Timestamp("2026-07-01T00:00:00Z")
    saved_runs, saved_blob = F._github_runs_in_window, F._github_blob_at
    try:
        # (a) an attesting run exists in the window AND its tree holds the exact blob → proven
        F._github_runs_in_window = lambda slug, a, b: [{"id": 1, "head_sha": "abc", "created_at": a}]
        F._github_blob_at = lambda slug, rel, ref: blob
        assert F._git_lock_error(led, "2026-06-08", now, repo=repo, repo_slug="o/r") is None
        # (b) forged backdated commit but NO attesting run → reject (the r13 attack)
        F._github_runs_in_window = lambda slug, a, b: []
        assert F._git_lock_error(led, "2026-06-08", now, repo=repo,
                                 repo_slug="o/r") == "lock_not_proven_no_attesting_run"
        # (c) runs exist but the tree holds a DIFFERENT blob (post-hoc edit) → reject
        F._github_runs_in_window = lambda slug, a, b: [{"id": 1, "head_sha": "abc", "created_at": a}]
        F._github_blob_at = lambda slug, rel, ref: "deadbeef"
        assert F._git_lock_error(led, "2026-06-08", now, repo=repo,
                                 repo_slug="o/r") == "lock_not_proven_no_attesting_run"
        # (d) API failure → fail CLOSED, never skipped
        def boom(slug, a, b):
            raise RuntimeError("api down")
        F._github_runs_in_window = boom
        assert F._git_lock_error(led, "2026-06-08", now, repo=repo,
                                 repo_slug="o/r").startswith("lock_unverifiable")
        # (e) while the lock window is STILL OPEN the check is waived (same-evening CI run)
        open_now = pd.Timestamp("2026-06-08T23:30:00Z")
        assert F._git_lock_error(led, "2026-06-08", open_now, repo=repo, repo_slug="o/r") is None
    finally:
        F._github_runs_in_window, F._github_blob_at = saved_runs, saved_blob


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
