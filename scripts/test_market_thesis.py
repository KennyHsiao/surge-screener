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
        MH._gspc_vix = lambda period, fresh=False: short    # accept the fresh kwarg (P3 r2 locked-path fetch)
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
    assert any("git pull --rebase" in ln for ln in body), body   # rebase on a lost race, then loop
    # the scorer must NOT run before the loop (re-validation is per-attempt, inside the loop only)
    assert all(not (ln == "python scripts/market_thesis_forward.py")
               for ln in code[:loop_start]), code[:loop_start]
    # CONCURRENCY guard + rebase-abort defence (Codex sweep): two overlapping market_thesis runs must
    # serialize, and a rebase conflict on the regenerated summary must abort+reset rather than wedge the loop
    # in detached-HEAD. Job-scoped concurrency (not workflow-wide) with cancel-in-progress false.
    conc = wf["jobs"]["market_thesis"].get("concurrency")
    assert conc and "market_thesis" in str(conc.get("group")) and conc.get("cancel-in-progress") is False, conc
    # WRITER-BOUND tripwire (Codex P2r32): a push trigger on the ledger paths so a non-GITHUB_TOKEN commit
    # creates a server-timestamped run the validator's in-session first-appearance check can catch. (PyYAML
    # parses the 'on:' key as the boolean True.)
    on_block = wf.get("on", wf.get(True)) or {}
    push = on_block.get("push") or {}
    paths = push.get("paths") or []
    assert paths and all("reports/market_thesis" in p for p in paths), on_block
    assert any("rebase --abort" in ln for ln in body), body
    # the conflict fallback must NOT reset --hard (stop-gate): that would drop this run's generated ledger and
    # let the loop push a summary without it. Abort-only keeps the ledger and fails the job red on exhaustion.
    assert not any("reset --hard" in ln for ln in body), body


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


def _ready_rec(support_class, analog, macro):
    return {"as_of": "2026-06-15", "direction": "看多", "bucket": "mid", "support_class": support_class,
            "manifest_status": "ready", "regime": "rally", "vix_bucket": "low",
            "rationale": {"analog": analog, "macro": macro}}


def test_render_tg_honesty_no_phantom_analog_or_macro():
    # DELIVERY honesty (P3 sweep): the digest must never state a non-existent analog ('平均 None') or a
    # value-less macro fact ('FOMC None'); it must not crash on a missing rationale key.
    # (a) event_only with an EMPTY analog block → NO 類比 line, no 'None' substring
    msg = T._render_tg(_ready_rec("event_only", {"resolved": 0, "mean": None, "worst_mdd": None}, {}))
    assert "類比" not in msg and "None" not in msg, msg
    # (b) analog_supported with a finite mean → the 類比 line IS rendered with the real mean
    msg2 = T._render_tg(_ready_rec("analog_supported", {"resolved": 30, "mean": 0.05, "worst_mdd": -0.21}, {}))
    assert "類比 mid 平均 0.05" in msg2, msg2
    # (c) macro with a value-less FOMC entry must never render 'FOMC None'
    msg3 = T._render_tg(_ready_rec("event_only", {"resolved": 0, "mean": None},
                                   {"CPI": 318.2, "FOMC": "3.50-3.75% (下次 2026-07-29)"}))
    assert "FOMC None" not in msg3 and "None" not in msg3 and "FOMC 3.50-3.75%" in msg3, msg3
    # (d) a missing rationale key must NOT crash the renderer
    bare = {k: v for k, v in _ready_rec("regime_only", {}, {}).items() if k != "rationale"}
    assert "大盤行情研判" in T._render_tg(bare)


def test_macro_summary_drops_none_and_renders_fomc():
    # _macro_summary (P3 sweep): FOMC (no scalar 'value') → its verified rate; a value-less non-FOMC event is
    # dropped (never 'X None'); a present scalar is kept; absent events are skipped.
    events = [{"type": "CPI", "present": True, "value": 318.2},
              {"type": "FOMC", "present": True, "last_rate": "3.50-3.75%", "next_meeting_at": "2026-07-29"},
              {"type": "JOBS", "present": True, "value": None},        # value-less non-FOMC → dropped
              {"type": "DXY", "present": False, "value": 99.3}]        # absent → skipped
    m = T._macro_summary(events)
    assert m["CPI"] == 318.2
    assert m["FOMC"].startswith("3.50-3.75%") and "2026-07-29" in m["FOMC"]
    assert "JOBS" not in m and "DXY" not in m
    assert all(v is not None for v in m.values())


def test_notify_committed_fail_closed_on_corrupt_ledger():
    # FAIL-CLOSED delivery (P3 sweep): a committed ledger that is corrupt JSON or lacks as_of must REFUSE
    # (return 1), never crash the notify step.
    import json as _json
    import tempfile
    saved = (T.OUT_DIR, T._notify)
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        T._notify = lambda rec: True
        (T.OUT_DIR / "forecast_2026-06-15.json").write_text("{not json", encoding="utf-8")
        (T.OUT_DIR / T.RUN_STATE).write_text(
            _json.dumps({"as_of": "2026-06-15", "file": "forecast_2026-06-15.json"}), encoding="utf-8")
        assert T.notify_committed() == 1
        # parses but lacks as_of → also refuse
        (T.OUT_DIR / "forecast_2026-06-15.json").write_text(_json.dumps({"direction": "看多"}), encoding="utf-8")
        assert T.notify_committed() == 1
        # present-but-UNPARSEABLE as_of → next_session_open_utc would raise; must REFUSE, not crash (stop-gate)
        (T.OUT_DIR / "forecast_2026-06-15.json").write_text(
            _json.dumps({"as_of": "not-a-date", "direction": "看多", "manifest_status": "ready"}), encoding="utf-8")
        assert T.notify_committed() == 1
    finally:
        T.OUT_DIR, T._notify = saved


def test_generation_failure_still_retries_committed_ready():
    # delivery recovery INDEPENDENT of data acquisition (Codex MKT-P3 r6): if build_forecast() returns None
    # (transient ^GSPC/^VIX fetch, corpus inadequacy, source-time refusal) but a committed in-window ready
    # forecast exists, main() must still bind RUN_STATE to it and retry — not exit generation_failed.
    import json as _json
    import tempfile
    import sys as _sys
    import pandas as pd
    saved = (T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv)
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        as_of = "2026-06-15"
        committed = {"as_of": as_of, "direction": "看多", "bucket": "mid", "support_class": "event_only",
                     "manifest_status": "ready", "benchmark": "^GSPC", "regime": "rally", "vix_bucket": "low",
                     "rationale": {}, "generated_at": f"{as_of}T21:00:00+00:00"}
        (T.OUT_DIR / f"forecast_{as_of}.json").write_text(_json.dumps(committed), encoding="utf-8")
        T.build_forecast = lambda period="20y": None                      # this run's generation FAILS
        T.ME.next_session_open_utc = lambda a: pd.Timestamp("2100-01-01", tz="UTC")  # committed file in-window
        _sys.argv = ["market_thesis.py"]
        assert T.main() == 0
        state = _json.loads((T.OUT_DIR / T.RUN_STATE).read_text(encoding="utf-8"))
        assert state["file"] == f"forecast_{as_of}.json" and state["reason"] == "cooldown_retry_delivery", state
        # no committed ready in-window → genuine generation failure (return 1)
        (T.OUT_DIR / f"forecast_{as_of}.json").unlink()
        assert T.main() == 1
    finally:
        T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv = saved


def test_degraded_rerun_still_retries_committed_ready():
    # family-INDEPENDENT delivery retry (Codex MKT-P3 stop-gate): a committed in-window READY
    # forecast_<as_of> must have its delivery RETRIED even when the rerun comes back DEGRADED — a later
    # FRED/YF drop must not abandon a prior ready alert. (r4 wrongly gated retry on the ready family.)
    import json as _json
    import tempfile
    import sys as _sys
    import pandas as pd
    saved = (T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv)
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        as_of = "2026-06-15"
        ready_committed = {"as_of": as_of, "direction": "看多", "bucket": "mid", "support_class": "event_only",
                           "manifest_status": "ready", "benchmark": "^GSPC", "regime": "rally",
                           "vix_bucket": "low", "rationale": {}, "generated_at": f"{as_of}T21:00:00+00:00"}
        (T.OUT_DIR / f"forecast_{as_of}.json").write_text(_json.dumps(ready_committed), encoding="utf-8")
        degraded = {"as_of": as_of, "direction": "盤整", "bucket": "mid", "support_class": "regime_only",
                    "manifest_status": "degraded", "regime": "range", "vix_bucket": "low", "rationale": {},
                    "label": "x", "generated_at": f"{as_of}T21:30:00+00:00", "_ledger": "regime_only_forecast"}
        T.build_forecast = lambda period="20y": dict(degraded)
        T.ME.next_session_open_utc = lambda a: pd.Timestamp("2100-01-01", tz="UTC")
        _sys.argv = ["market_thesis.py"]
        assert T.main() == 0
        state = _json.loads((T.OUT_DIR / T.RUN_STATE).read_text(encoding="utf-8"))
        assert state["file"] == f"forecast_{as_of}.json", state
        assert state["reason"] == "cooldown_retry_delivery", state
    finally:
        T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv = saved


def test_ready_run_not_blocked_by_recent_regime_only():
    # family-SCOPED cadence (Codex MKT-P3 r4): a recent DEGRADED regime_only ledger must NOT cooldown-skip a
    # later READY forecast (a recovered data outage must still alert). The ready forecast must be WRITTEN and
    # RUN_STATE must point at forecast_<as_of>.json, not file:null.
    import json as _json
    import tempfile
    import sys as _sys
    import pandas as pd
    saved = (T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv)
    try:
        T.OUT_DIR = Path(tempfile.mkdtemp())
        as_of = "2026-06-15"
        # a recent degraded regime_only artifact 2 days earlier (well within COOLDOWN_DAYS)
        (T.OUT_DIR / "regime_only_forecast_2026-06-13.json").write_text(
            _json.dumps({"as_of": "2026-06-13", "manifest_status": "degraded"}), encoding="utf-8")
        ready = {"as_of": as_of, "direction": "盤整", "bucket": "mid", "support_class": "event_only",
                 "manifest_status": "ready", "regime": "range", "vix_bucket": "low", "rationale": {},
                 "label": "x", "generated_at": f"{as_of}T21:00:00+00:00", "_ledger": "forecast"}
        T.build_forecast = lambda period="20y": dict(ready)
        T.ME.next_session_open_utc = lambda a: pd.Timestamp("2100-01-01", tz="UTC")
        _sys.argv = ["market_thesis.py"]
        assert T.main() == 0
        assert (T.OUT_DIR / f"forecast_{as_of}.json").exists()        # ready forecast WRITTEN, not skipped
        state = _json.loads((T.OUT_DIR / T.RUN_STATE).read_text(encoding="utf-8"))
        assert state["file"] == f"forecast_{as_of}.json", state       # delivery bound to the ready ledger
    finally:
        T.OUT_DIR, T.build_forecast, T.ME.next_session_open_utc, _sys.argv = saved


def test_build_forecast_refuses_pre_close_source():
    # SOURCE-TIME GUARD (Codex MKT-P3 r2): a run whose market-data fetch happened BEFORE the as_of close read
    # an in-progress bar; even with a post-close write it must REFUSE (no look-ahead lock). Drive it by
    # putting the as_of close in the far future so fetch_started (now) precedes it.
    import pandas as pd
    saved = (T.MH._gspc_vix, T.MH.build_daily, T.MH.corpus_inadequacy, T.MH.label_episodes,
             T.ME.session_close_utc, T.MH.retrieve_regime_analogs, T.ME.build_manifest)
    try:
        s = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-06-12", "2026-06-15"]))
        T.MH._gspc_vix = lambda period, fresh=False: (s, s)
        T.MH.build_daily = lambda period, sv=None: [{"date": "2026-06-15", "regime": "rally",
                                                     "vix_bucket": "low"}]
        T.MH.corpus_inadequacy = lambda daily, eps: None
        T.MH.label_episodes = lambda series: []
        T.ME.session_close_utc = lambda as_of: pd.Timestamp("2100-01-01", tz="UTC")   # close in the future
        assert T.build_forecast("20y") is None
        # sanity: with the close in the PAST, the guard passes (it does not false-refuse a real post-close run)
        T.ME.session_close_utc = lambda as_of: pd.Timestamp("2000-01-01", tz="UTC")
        T.MH.retrieve_regime_analogs = lambda d, r, v: {f"fwd_{T.MH.FWD[1]}d": {"status": "x"},
                                                        "bear_telemetry": {}}
        T.ME.build_manifest = lambda as_of, fresh=False: {"manifest_status": "degraded", "missing": ["CPI"],
                                                           "stale": [], "events": []}
        rec = T.build_forecast("20y")
        assert rec is not None and rec["as_of"] == "2026-06-15"
    finally:
        (T.MH._gspc_vix, T.MH.build_daily, T.MH.corpus_inadequacy, T.MH.label_episodes,
         T.ME.session_close_utc, T.MH.retrieve_regime_analogs, T.ME.build_manifest) = saved


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print(f"  ok  {t.__name__}")
    print(f"PASS — {len(tests)} offline tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
