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
    # CONFLICT (Codex P2r24): degraded ⇒ regime_only namespace ⇒ direction from the REGIME tag ONLY, never
    # from the analog mean — a rally regime with a strongly NEGATIVE analog mean must still emit 看多 (from
    # the regime), not 看空 (from the analog). Otherwise an analog-driven call pollutes the regime_only family.
    d2, _, s2 = T.decide("rally", {"mean": -0.20}, "degraded")
    assert s2 == "regime_only" and d2 == "看多", (d2, s2)
    # and a 'range' regime degraded with a positive analog mean → 盤整 from regime, not 看多 from analog
    d3, _, s3 = T.decide("range", {"mean": 0.20}, "degraded")
    assert s3 == "regime_only" and d3 == "盤整", (d3, s3)


def test_analog_supported_direction_from_mean():
    # realistic analog blocks carry resolved>0 (Codex P2r25 — a usable analog, not just a bare mean)
    assert T.decide("range", {"resolved": 8, "mean": 0.05}, "ready") == ("看多", "mid", "analog_supported")
    assert T.decide("range", {"resolved": 8, "mean": -0.05}, "ready") == ("看空", "mid", "analog_supported")
    assert T.decide("range", {"resolved": 8, "mean": 0.01}, "ready") == ("盤整", "mid", "analog_supported")


def test_empty_analog_block_is_event_only_not_analog_supported():
    # a block with no 'status' but no USABLE analog (Codex P2r25) must NOT enter analog_supported — it
    # falls back to event_only with a regime-tag direction, keeping the analog namespace clean.
    for bad in ({"resolved": 0, "mean": None}, {"resolved": 0, "mean": float("nan")},
                {"resolved": 5, "mean": None}, {"mean": 0.05}):   # 4th: no 'resolved' ⇒ not usable
        _, _, s = T.decide("rally", bad, "ready")
        assert s == "event_only", (bad, s)
    # a genuinely usable analog still earns analog_supported
    assert T.decide("range", {"resolved": 5, "mean": 0.05}, "ready")[2] == "analog_supported"


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
    # STRUCTURAL pin (Codex P2r18/r19/r22/r27/r29) for the market_thesis CI job:
    #  - the INITIAL sync precedes generation (one tree to generate on, r18);
    #  - the scorer is unmasked (no '|| true', r14);
    #  - gen_rc/val_rc are captured and a nonzero rc fails closed (r22);
    #  - the generator rc is exported so a generation failure forces a red summary (r27);
    #  - the validation summary is staged UNCONDITIONALLY and the whole-dir add is guarded (r22);
    #  - the push lives in a RETRY loop that RE-VALIDATES (runs the scorer) before each push, so the pushed
    #    tree is always the validated tree (r17) AND the red summary is durable under a push race (r29).
    import yaml
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "surge_screener.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["market_thesis"]["steps"]
    lines = [ln.strip() for st in steps for ln in (st.get("run") or "").splitlines()]
    code = [ln for ln in lines if ln and not ln.startswith("#")]
    gen = next(i for i, ln in enumerate(code) if ln == "python scripts/market_thesis.py")
    # the INITIAL sync precedes generation
    sync = [i for i, ln in enumerate(code) if ln.startswith("git pull") or ln.startswith("git rebase")]
    assert sync and min(sync) < gen, (sync, gen)
    # scorer unmasked + gen-rc plumbed
    assert not any("|| true" in ln for ln in code)
    assert any(ln == "gen_rc=$?" for ln in code) and any(ln == "val_rc=$?" for ln in code), code
    assert any('"$val_rc" -ne 0' in ln for ln in code), code
    assert any(ln == "export MKT_THESIS_GEN_RC=$gen_rc" for ln in code), code
    # summary staged unconditionally; whole-dir add guarded behind the clean-rc check and after the summary add
    summ = next(i for i, ln in enumerate(code) if ln == "git add reports/market_thesis/validation_summary.json")
    famadd = next(i for i, ln in enumerate(code) if ln == "git add reports/market_thesis/")
    guard = next(i for i, ln in enumerate(code) if '"$gen_rc" -eq 0' in ln and '"$val_rc" -eq 0' in ln)
    assert summ < guard < famadd, (summ, guard, famadd)
    # the push lives inside a for-loop that RE-VALIDATES before pushing (r17+r29): locate the loop body and
    # assert it contains BOTH a scorer invocation and a git push, scorer BEFORE push, plus a rebase on failure.
    loop_start = next(i for i, ln in enumerate(code) if ln.startswith("for ") and "attempt" in ln)
    loop_end = next(i for i, ln in enumerate(code) if i > loop_start and ln == "done")
    body = code[loop_start:loop_end]
    fwd_in = next(j for j, ln in enumerate(body) if ln == "python scripts/market_thesis_forward.py")
    push_in = next(j for j, ln in enumerate(body) if "git push" in ln)
    assert fwd_in < push_in, body                      # re-validate, THEN push (validated tree == pushed tree)
    assert any(ln.startswith("git pull --rebase") for ln in body), body   # rebase on a lost race, then loop
    # the scorer must NOT run before the loop (re-validation is per-attempt, inside the loop only)
    assert all(not (ln == "python scripts/market_thesis_forward.py")
               for ln in code[:loop_start]), code[:loop_start]


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


def test_generation_refuses_to_heal_malformed_current_ledger():
    # CORRUPTION must SURVIVE to the forward validator (Codex P2r22 stop-gate): generation must not
    # silently overwrite a malformed existing forecast_<as_of>.json — that would heal it before the
    # fail-closed validator could reject+persist it. Cadence already skipped it (malformed), so without a
    # valid same-date ledger generation reaches the write path and must REFUSE (exit 1), file untouched.
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
        T.ME.next_session_open_utc = lambda a: pd.Timestamp("2100-01-01", tz="UTC")
        (T.OUT_DIR / f"forecast_{as_of}.json").write_text("[1,2,3]", encoding="utf-8")   # corrupt, same date
        _sys.argv = ["market_thesis.py"]
        assert T.main() == 1
        # left intact (NOT healed) — the forward validator is the gate that records it as a reject
        assert (T.OUT_DIR / f"forecast_{as_of}.json").read_text(encoding="utf-8") == "[1,2,3]"
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
