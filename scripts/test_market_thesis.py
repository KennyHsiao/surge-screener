#!/usr/bin/env python3
"""Offline tests for the Tier-1 deterministic forecaster decision (design v7, P3). No network.

Run:  .venv/bin/python scripts/test_market_thesis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import market_thesis as T            # noqa: E402
import market_thesis_contract as C   # noqa: E402


def test_degraded_forces_regime_only():
    d, b, s = T.decide("rally", {"mean": 0.05}, "degraded")
    assert s == "regime_only" and b == "mid"


def test_analog_supported_direction_from_mean():
    assert T.decide("range", {"mean": 0.05}, "ready") == ("看多", "mid", "analog_supported")
    assert T.decide("range", {"mean": -0.05}, "ready") == ("看空", "mid", "analog_supported")
    assert T.decide("range", {"mean": 0.01}, "ready") == ("盤整", "mid", "analog_supported")


def test_suppressed_bearish_still_forecasts_from_regime():
    # a correction whose bearish analog is fail-closed → NOT analog-backed, but the 看空 is still emitted
    d, b, s = T.decide("correction", {"status": "insufficient_bearish_analogs"}, "ready")
    assert d == "看空" and s == "event_only"


def test_no_analog_uses_regime_fallback():
    assert T.decide("rally", None, "ready") == ("看多", "mid", "event_only")
    assert T.decide("correction", None, "ready") == ("看空", "mid", "event_only")
    assert T.decide("range", None, "ready") == ("盤整", "mid", "event_only")


def test_build_forecast_refuses_inadequate_corpus():
    # the forecast path must run the SAME adequacy gate as the publisher: a short bull-only fetch ⇒ None.
    import numpy as np
    import pandas as pd
    import market_regime_history as MH
    vals = list(np.linspace(100, 130, 320))                       # ~15 months, no 10% drawdown
    idx = pd.bdate_range("2025-01-01", periods=len(vals))
    short = (pd.Series(vals, index=idx), pd.Series(15.0, index=idx))
    saved = MH._gspc_vix
    try:
        MH._gspc_vix = lambda period: short
        assert T.build_forecast("20y") is None
    finally:
        MH._gspc_vix = saved


def test_decision_is_contract_valid():
    d, b, s = T.decide("rally", {"mean": 0.04}, "ready")
    assert C.validate_forecast({"as_of": "2026-06-10", "direction": d, "bucket": b, "support_class": s}) == []


def test_notify_committed_bound_to_current_run():
    # delivery is bound to THIS run's exact ledger via RUN_STATE (P2r16): a stale older ready forecast must
    # NEVER be resent after a degraded or cooldown-skipped run.
    import json as _json
    import tempfile
    import pandas as pd
    saved_out, saved_notify = T.OUT_DIR, T._notify
    saved_open = T.ME.next_session_open_utc
    sent = []
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        T._notify = lambda rec: sent.append(rec) or True
        # deterministic lock windows regardless of the real date: 06-15 is live, 06-08 is long past
        T.ME.next_session_open_utc = lambda a: (pd.Timestamp("2100-01-01", tz="UTC")
                                                if a == "2026-06-15" else pd.Timestamp("2000-01-01", tz="UTC"))
        # no run state at all → nothing sent
        assert T.notify_committed() == 0 and sent == []
        # PRIOR ready ledger exists, but THIS run was degraded (regime_only) → nothing sent (the r16 attack)
        (T.OUT_DIR / "forecast_2026-06-08.json").write_text(_json.dumps(
            {"as_of": "2026-06-08", "direction": "看多", "bucket": "mid", "support_class": "event_only",
             "manifest_status": "ready", "regime": "rally", "vix_bucket": "normal",
             "rationale": {}, "label": "x"}), encoding="utf-8")
        (T.OUT_DIR / T.RUN_STATE).write_text(_json.dumps(
            {"as_of": "2026-06-15", "file": "regime_only_forecast_2026-06-15.json"}), encoding="utf-8")
        assert T.notify_committed() == 0 and sent == []
        # cooldown skip (file: None) → nothing sent
        (T.OUT_DIR / T.RUN_STATE).write_text(_json.dumps(
            {"as_of": "2026-06-15", "file": None, "reason": "cooldown_skip"}), encoding="utf-8")
        assert T.notify_committed() == 0 and sent == []
        # a leftover state pointing at an OLD ready ledger (past its lock window) → stale_window, no send
        (T.OUT_DIR / T.RUN_STATE).write_text(_json.dumps(
            {"as_of": "2026-06-08", "file": "forecast_2026-06-08.json"}), encoding="utf-8")
        assert T.notify_committed() == 0 and sent == []
        # THIS run produced a ready ledger → exactly that record is sent
        (T.OUT_DIR / "forecast_2026-06-15.json").write_text(_json.dumps(
            {"as_of": "2026-06-15", "direction": "盤整", "bucket": "mid", "support_class": "event_only",
             "manifest_status": "ready", "regime": "range", "vix_bucket": "normal",
             "rationale": {}, "label": "x"}), encoding="utf-8")
        (T.OUT_DIR / T.RUN_STATE).write_text(_json.dumps(
            {"as_of": "2026-06-15", "file": "forecast_2026-06-15.json"}), encoding="utf-8")
        assert T.notify_committed() == 0 and len(sent) == 1 and sent[0]["as_of"] == "2026-06-15"
        # ready send FAILURE (secrets missing / API error) must fail the step, not exit green (P2r17)
        T._notify = lambda rec: False
        assert T.notify_committed() == 1 and len(sent) == 1
        T._notify = lambda rec: sent.append(rec) or True
        # run state points at a forecast file that is MISSING on disk → hard failure (exit 1), no send
        (T.OUT_DIR / "forecast_2026-06-15.json").unlink()
        assert T.notify_committed() == 1 and len(sent) == 1
    finally:
        T.OUT_DIR, T._notify = saved_out, saved_notify
        T.ME.next_session_open_utc = saved_open


def test_ci_job_sync_ordering_pinned():
    # STRUCTURAL pin (Codex P2r18+r19): in the market_thesis CI job — the ONLY git pull/rebase precedes
    # generation; the scorer is a standalone unmasked command; exactly one bare `git push` with no retry
    # loop and no later pull. Line-based assertions (not fragile exact-string search).
    import yaml
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "surge_screener.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["market_thesis"]["steps"]
    lines = [ln.strip() for st in steps for ln in (st.get("run") or "").splitlines()]
    code = [ln for ln in lines if ln and not ln.startswith("#")]
    gen = next(i for i, ln in enumerate(code) if ln == "python scripts/market_thesis.py")
    # all sync commands precede generation; none after
    sync = [i for i, ln in enumerate(code) if ln.startswith("git pull") or ln.startswith("git rebase")]
    assert sync and all(i < gen for i in sync), (sync, gen)
    # the scorer is standalone and unmasked (no ||, no &&, no retry wrapper)
    fwd = [ln for ln in code if "market_thesis_forward.py" in ln]
    assert fwd == ["python scripts/market_thesis_forward.py"], fwd
    # exactly one push; bare (no loop/condition on the same line); and no sync command anywhere after it
    pushes = [i for i, ln in enumerate(code) if "git push" in ln]
    assert len(pushes) == 1 and code[pushes[0]] == "git push", [code[i] for i in pushes]
    assert all(i < pushes[0] for i in sync)
    # no loop construct wrapping a push anywhere in the job
    assert not any(("for " in ln or "while " in ln) and "push" in ln for ln in code)


def test_recent_forecast_tolerates_malformed_ledgers():
    # cadence guard must SKIP malformed committed ledgers, never crash generation (Codex P2r21) — the
    # forward validator is what rejects+persists them; a crash here would orphan the prior summary.
    import json as _json
    import tempfile
    saved = T.OUT_DIR
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        (T.OUT_DIR / "forecast_2026-06-10.json").write_text("[1,2,3]", encoding="utf-8")        # a list
        (T.OUT_DIR / "forecast_2026-06-11.json").write_text("null", encoding="utf-8")            # null
        (T.OUT_DIR / "forecast_2026-06-12.json").write_text(
            _json.dumps({"as_of": "not-a-date"}), encoding="utf-8")                              # bad date
        (T.OUT_DIR / "forecast_bad.json").write_text("{not json", encoding="utf-8")             # unreadable
        assert T._recent_forecast("2026-06-15") is None                                          # no crash
        # a VALID ledger among the junk is still found
        (T.OUT_DIR / "forecast_2026-06-14.json").write_text(
            _json.dumps({"as_of": "2026-06-14"}), encoding="utf-8")
        assert T._recent_forecast("2026-06-15") == "2026-06-14"
    finally:
        T.OUT_DIR = saved


def test_cooldown_retries_delivery_for_in_window_ready_ledger():
    # DELIVERY RECOVERY (Codex P2r21): a CI rerun after a committed ready ledger whose notify failed must
    # RETRY delivery, not no-op. main() must point RUN_STATE at that exact in-window ready file.
    import json as _json
    import tempfile
    import sys as _sys
    import pandas as pd
    saved = (T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv)
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        as_of = "2026-06-15"
        rec = {"as_of": as_of, "direction": "盤整", "bucket": "mid", "support_class": "event_only",
               "manifest_status": "ready", "regime": "range", "vix_bucket": "normal", "rationale": {},
               "label": "x", "generated_at": f"{as_of}T21:00:00+00:00", "_ledger": "forecast"}
        T.build_forecast = lambda period="20y": dict(rec)
        T.ME.next_session_open_utc = lambda a: pd.Timestamp("2100-01-01", tz="UTC")   # always in-window
        # a ready ledger for THIS as_of already committed by a prior run (delivery may have failed)
        (T.OUT_DIR / f"forecast_{as_of}.json").write_text(
            _json.dumps({k: v for k, v in rec.items() if k != "_ledger"}), encoding="utf-8")
        _sys.argv = ["market_thesis.py"]
        assert T.main() == 0
        state = _json.loads((T.OUT_DIR / T.RUN_STATE).read_text(encoding="utf-8"))
        assert state["file"] == f"forecast_{as_of}.json", state
        assert state["reason"] == "cooldown_retry_delivery", state
        # contrast: an OLDER within-cooldown ledger (different as_of) → pure skip, file:None (no resend)
        T.build_forecast = lambda period="20y": {**dict(rec), "as_of": "2026-06-16",
                                                 "generated_at": "2026-06-16T21:00:00+00:00"}
        assert T.main() == 0
        state2 = _json.loads((T.OUT_DIR / T.RUN_STATE).read_text(encoding="utf-8"))
        assert state2["file"] is None and state2["reason"] == "cooldown_skip", state2
    finally:
        T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv = saved


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print(f"  ok  {t.__name__}")
    print(f"PASS — {len(tests)} offline tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
