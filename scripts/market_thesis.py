#!/usr/bin/env python3
"""Tier-1 大盤行情研判 forecaster — code-fed DETERMINISTIC baseline (design v7, P3). No LLM, no WebSearch.

Gathers the VERIFIED base (current ^GSPC/VIX regime + History-Analysis analogs + the code-owned event
manifest), emits ONE locked `(direction, bucket, support_class)` forecast per the frozen contract, writes it
to the correct ledger, and pushes Telegram ONLY when `manifest_status == ready` (else a regime-only,
NON-alerting artifact). This is the provable baseline that Tier-2 (the agentic loop) must later BEAT in an
ablation before it ships. EXPLORATORY: direction/期程 earn no "accuracy" until market_thesis_forward matures.

Delivery (v7 §1a/1e): `degraded` ⇒ NO Telegram (forecast AND digest) + write only `regime_only_forecast_*`;
`ready` ⇒ Telegram + `forecast_*`. The two ledgers are schema-separated and scored independently.

CLI:  python scripts/market_thesis.py [--notify] [--force]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import market_thesis_contract as C       # noqa: E402 — frozen contract
import market_regime_history as MH       # noqa: E402 — corpus + analogs
import market_events as ME               # noqa: E402 — verified event manifest

OUT_DIR = REPO / "reports" / "market_thesis"
PRIMARY_BUCKET = "mid"                    # one primary bucket per forecast (40 sessions)
COOLDOWN_DAYS = 6                         # weekly cadence — skip if a forecast exists within this window


REGIMES = ("rally", "correction", "range")   # the ONLY regimes label_regime emits; anything else is malformed


def decide(regime: str, analog_block: dict | None, manifest_status: str) -> tuple[str, str, str]:
    """PURE deterministic baseline: map the VERIFIED current regime + History-Analysis analog to a locked
    (direction, bucket, support_class). Direction follows the analog's realized forward mean when the analog
    cleared its floor (analog_supported); otherwise it falls back to the regime tag (event_only / regime_only).
    A 看空 with a suppressed/insufficient analog is STILL emitted (from the regime), just not analog-backed."""
    # FAIL CLOSED on an unknown regime (Codex P2r31): the old `.get(regime, "盤整")` default silently mapped
    # ANY string to 盤整, so a malformed/hand-edited regime_only ledger with regime='typo', direction='盤整'
    # passed the validator's decide()-recompute and could pollute the regime_only denominator. The validator
    # wraps this call and turns a raise into support_semantics_unrecomputable ⇒ the bad ledger is rejected.
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r} (must be one of {REGIMES})")
    # a block earns analog_supported ONLY if it carries a USABLE analog (Codex P2r25): a finite numeric mean
    # over ≥1 resolved sample. A block like {'resolved': 0, 'mean': None} has no 'status' key but is empty —
    # admitting it to the analog_supported namespace (with direction silently falling back to the regime tag)
    # would contaminate that v7 scoring denominator with non-analog calls once the manifest turns ready.
    import math
    m = analog_block.get("mean") if analog_block else None
    analog_ok = (bool(analog_block) and "status" not in analog_block
                 and isinstance(m, (int, float)) and not isinstance(m, bool) and math.isfinite(m)
                 and (analog_block.get("resolved") or 0) > 0)
    if manifest_status == "degraded":
        sclass = "regime_only"
    elif analog_ok:
        sclass = "analog_supported"
    else:
        sclass = "event_only"

    # direction follows the analog mean ONLY inside the analog_supported namespace (Codex P2r24): design v7
    # treats support_class as a SEPARATE scoring namespace, so a regime_only (degraded) or event_only ledger
    # must derive its direction from the regime tag alone — letting the analog mean drive a regime_only call
    # would mix an analog-driven decision into the regime_only denominator (e.g. rally + a negative analog
    # mean would emit 看空/regime_only), making that family's later hit-rate measure the wrong component.
    mean = analog_block.get("mean") if sclass == "analog_supported" else None
    if mean is not None and mean >= C.THETA_DIR:
        direction = "看多"
    elif mean is not None and mean <= -C.THETA_DIR:
        direction = "看空"
    elif mean is not None:
        direction = "盤整"
    else:
        direction = {"rally": "看多", "correction": "看空", "range": "盤整"}.get(regime, "盤整")
    return direction, PRIMARY_BUCKET, sclass


def _recent_forecast(as_of: str) -> str | None:
    """Most recent ledgered forecast date within COOLDOWN_DAYS of as_of (cadence guard), or None."""
    import pandas as pd
    asof = pd.Timestamp(as_of)
    latest = None
    for pat in ("forecast_*.json", "regime_only_forecast_*.json"):
        for f in OUT_DIR.glob(pat):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            # TOLERATE malformed ledgers for cadence (Codex P2r21): a committed list/null/scalar or an
            # unparseable as_of must be SKIPPED here, not crash the generation step before the forward
            # validator runs — market_thesis_forward.py is the one that rejects + persists them in the
            # summary. Crashing here would leave the prior validation_summary as the last artifact.
            if not isinstance(d, dict):
                continue
            ad = d.get("as_of")
            if not ad:
                continue
            try:
                days = (asof - pd.Timestamp(ad)).days
            except Exception:  # noqa: BLE001
                continue
            if 0 <= days < COOLDOWN_DAYS:
                if latest is None or ad > latest:
                    latest = ad
    return latest


def _macro_summary(events: list[dict]) -> dict:
    """Human-readable macro map for the digest (P3 sweep): the scalar 'value' per PRESENT event, with FOMC —
    which carries no scalar value, only last_rate/next_meeting_at — shown as its VERIFIED rate. None-valued
    entries are dropped so the Telegram digest can never state a false macro fact (the old
    `{e['type']: e.get('value')}` emitted 'FOMC None' on every ready manifest and silently dropped the rate)."""
    out: dict = {}
    for e in events:
        if not e.get("present"):
            continue
        if e.get("type") == "FOMC":
            out["FOMC"] = f"{e.get('last_rate')} (下次 {e.get('next_meeting_at')})"
        elif e.get("value") is not None:
            out[e["type"]] = e["value"]
    return out


def _load(mod_name: str, func_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, REPO / "scripts" / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)


def build_forecast(period: str = "20y") -> dict | None:
    # SOURCE-acquisition time (Codex MKT-P3 r2): stamp BEFORE any market-data read. The ex-ante guard must
    # bind to when the DATA was acquired, not just when generated_at was written — a run that crosses the
    # close (fetches an in-progress bar pre-close, writes post-close) would otherwise lock look-ahead inputs.
    fetch_started = datetime.now(timezone.utc)
    # Fetch ONCE, FRESH (cache-bypassing) so the locked path reads FINAL post-close bars, never a same-session
    # bar another job cached pre-close. Run the SAME corpus-adequacy gate the publisher uses.
    sv = MH._gspc_vix(period, fresh=True)
    if sv is None:
        print("[mkt-thesis] no ^GSPC/^VIX history fetched — refusing to forecast", file=sys.stderr)
        return None
    daily = MH.build_daily(period, sv=sv)
    inadequate = MH.corpus_inadequacy(daily, MH.label_episodes(sv[0]))
    if inadequate:
        print(f"[mkt-thesis] corpus inadequate ({inadequate}) — refusing to forecast", file=sys.stderr)
        return None
    cur = daily[-1]
    regime, vix_bucket, as_of = cur["regime"], cur["vix_bucket"], cur["date"]
    # SOURCE-TIME GUARD (Codex MKT-P3 r2): the as_of session's close must have ALREADY PASSED when we fetched
    # — else the latest bar was in-progress (look-ahead / non-reproducible). Refuse; the pre-close/late guards
    # in main() bind the WRITE time, this binds the DATA-acquisition time.
    if fetch_started < ME.session_close_utc(as_of):
        print(f"[mkt-thesis] source acquired before the {as_of} close "
              f"({fetch_started.isoformat()} < {ME.session_close_utc(as_of).isoformat()}) — the latest bar "
              f"is in-progress; refusing to lock a look-ahead forecast.", file=sys.stderr)
        return None
    analogs = MH.retrieve_regime_analogs(daily, regime, vix_bucket)
    manifest = ME.build_manifest(as_of)
    direction, bucket, sclass = decide(regime, analogs.get(f"fwd_{MH.FWD[1]}d"), manifest["manifest_status"])
    rec = {
        "as_of": as_of, "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier": 1, "method": "deterministic_baseline", "benchmark": C.BENCHMARK,
        "direction": direction, "bucket": bucket, "support_class": sclass,
        "manifest_status": manifest["manifest_status"],
        "regime": regime, "vix_bucket": vix_bucket,
        "rationale": {
            "analog": analogs.get(f"fwd_{MH.FWD[1]}d"), "bear_telemetry": analogs.get("bear_telemetry"),
            "manifest_missing": manifest["missing"], "manifest_stale": manifest["stale"],
            "macro": _macro_summary(manifest["events"]),
            # FULL event provenance (Codex P2r19): a ready claim must carry the auditable evidence rows
            # (source_id, release/decision timestamps, freshness verdicts) — the forward validator REQUIRES
            # them on the ready family, so a ready ledger without provenance can never be scored/notified.
            "manifest_events": manifest["events"],
        },
        "label": "探索性,未驗證,非投資建議",
    }
    errs = C.validate_forecast(rec)
    if errs:
        print(f"[mkt-thesis] contract violation, refusing to write: {errs}", file=sys.stderr)
        return None
    rec["_ledger"] = "regime_only_forecast" if manifest["manifest_status"] == "degraded" else "forecast"
    return rec


def _render_tg(rec: dict) -> str:
    import math
    rationale = rec.get("rationale") or {}          # defensive (P3 sweep): a missing rationale key must not crash
    a = rationale.get("analog") or {}
    macro = rationale.get("macro") or {}
    head = (f"🧭 *大盤行情研判* · {rec['as_of']}（探索性,非投資建議）\n"
            f"研判: *{rec['direction']}* · 期程 {rec['bucket']} · {rec['support_class']}")
    ctx = f"regime {rec['regime']} / VIX {rec['vix_bucket']}"
    # render the 類比 precedent ONLY for an analog_supported forecast (P3 sweep): event_only/regime_only carry
    # an empty analog block (mean=None, no usable precedent), and the old `"mean" in a` key-presence test
    # would emit '平均 None' — presenting a NON-EXISTENT analog as forecast precedent, contradicting the
    # ledger's own classification. Mirror decide()'s usable-analog predicate (finite numeric mean).
    m = a.get("mean")
    if (rec.get("support_class") == "analog_supported" and isinstance(m, (int, float))
            and not isinstance(m, bool) and math.isfinite(m)):
        ctx += f" · 類比 {rec['bucket']} 平均 {m} (worst_mdd {a.get('worst_mdd')})"
    # skip None-valued macro entries (P3 sweep): a value-less event (e.g. FOMC, surfaced via _macro_summary)
    # must never render as 'FOMC None' — the digest may only state VERIFIED macro facts.
    mac = " · ".join(f"{k} {v}" for k, v in macro.items() if v is not None)
    return head + "\n" + ctx + (("\n" + mac) if mac else "")


def _notify(rec: dict) -> bool:
    import os
    if rec["manifest_status"] != "ready":   # delivery gate — degraded NEVER pushes (forecast or digest)
        print(f"[mkt-thesis] manifest {rec['manifest_status']} — suppress ALL Telegram (non-alerting).",
              file=sys.stderr)
        return False
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[mkt-thesis] TELEGRAM_* not set — skipping notify.", file=sys.stderr)
        return False
    try:
        return bool(_load("05_notify", "send_telegram_message")(token, chat, _render_tg(rec)))
    except Exception as e:  # noqa: BLE001
        print(f"[mkt-thesis] notify error: {e}", file=sys.stderr)
        return False


RUN_STATE = "last_run.json"   # workspace-local (gitignored): binds the notify step to THIS run's ledger


def notify_committed() -> int:
    """Send Telegram ONLY for the ledger THIS run produced (Codex P2r16) — a directory-wide 'latest ready'
    lookup could resend a STALE old forecast after a degraded/cooldown run. The generation step records its
    outcome in RUN_STATE; this step no-ops unless that exact file is a forecast_* (ready-family) ledger.
    Runs AFTER validation + durable push (P2r15), and _notify still gates on manifest_status=ready."""
    state_path = OUT_DIR / RUN_STATE
    if not state_path.exists():
        print("[mkt-thesis] notify-committed: no run state — nothing generated this run; not notifying.",
              file=sys.stderr)
        return 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    fname = state.get("file")
    if not fname or not fname.startswith("forecast_"):
        print(f"[mkt-thesis] notify-committed: this run produced {fname or state.get('reason', 'nothing')} "
              f"— degraded/skip never notifies.", file=sys.stderr)
        return 0
    path = OUT_DIR / fname
    if not path.exists():
        print(f"[mkt-thesis] notify-committed: {fname} missing on disk — refusing.", file=sys.stderr)
        return 1
    # FAIL-CLOSED load (P3 sweep): a committed ledger that is corrupt JSON or lacks as_of must REFUSE loudly
    # (return 1), never crash the notify step — the generation step's fail-closed discipline (P2r21/r22)
    # extended to delivery. The cooldown-retry branch can bind RUN_STATE to a pre-existing on-disk file, so
    # this step cannot assume a well-formed record.
    # STALENESS guard (self-sweep after Codex P2r16): a leftover local RUN_STATE (or a delayed re-run) must
    # never deliver a forecast past its lock window — after the next session opens it is no longer news.
    # FAIL-CLOSED load (P3 sweep + stop-gate): a committed ledger that is corrupt JSON, lacks as_of, OR has a
    # present-but-UNPARSEABLE as_of must REFUSE loudly (return 1), never crash the step. next_session_open_utc
    # is INSIDE the guard because validate_forecast does NOT check date canonicality, so a non-canonical as_of
    # reaches here and would raise in pd.Timestamp — the generation step's fail-closed discipline (P2r21/r22)
    # extended fully to delivery.
    import pandas as pd
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rec, dict) or not rec.get("as_of"):
            raise ValueError("not an object / missing as_of")
        as_of = rec["as_of"]
        nxt_open = ME.next_session_open_utc(as_of)        # raises on a non-canonical/unparseable as_of
    except Exception as e:  # noqa: BLE001
        print(f"[mkt-thesis] notify-committed: {fname} unparseable/invalid ({e!r}) — refusing.", file=sys.stderr)
        return 1
    if pd.Timestamp.now(tz="UTC") >= nxt_open:
        print(f"[mkt-thesis] notify-committed: {fname} is past its lock window (stale_window) — not sending.",
              file=sys.stderr)
        return 0
    sent = _notify(rec)
    print(f"[mkt-thesis] telegram: {'sent' if sent else 'FAILED'} (from committed {fname})", file=sys.stderr)
    # a READY forecast that should have been delivered but wasn't (missing secrets, send error) must fail
    # the step loudly (Codex P2r17) — never a green job over a silent delivery gap.
    return 0 if sent else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Tier-1 大盤行情研判 deterministic forecaster")
    ap.add_argument("--period", default="20y")
    ap.add_argument("--notify-only", action="store_true",
                    help="send Telegram from the existing committed ledger; do NOT generate (CI post-push step)")
    ap.add_argument("--force", action="store_true", help="ignore the weekly cadence cooldown")
    args = ap.parse_args()
    if args.notify_only:
        return notify_committed()

    rec = build_forecast(args.period)
    if rec is None:
        print("[mkt-thesis] no forecast produced", file=sys.stderr)
        return 1
    # ex-ante LOCK (contract §1c): t0 = the as_of session CLOSE, so we must never WRITE a forecast before
    # that close — the forward validator rejects such records (generated_before_close), and a pre-close run
    # could exploit intraday information. --force does NOT bypass this (it is a contract, not a cadence).
    import pandas as pd
    close_utc = pd.Timestamp(f"{rec['as_of']} 16:00", tz="America/New_York").tz_convert("UTC")
    if pd.Timestamp(rec["generated_at"]) < close_utc:
        print(f"[mkt-thesis] pre-close run ({rec['generated_at']} < close {close_utc.isoformat()}) — "
              f"refusing to write a locked forecast (ex-ante t0 contract)", file=sys.stderr)
        return 1
    nxt_open = ME.next_session_open_utc(rec["as_of"])
    if pd.Timestamp(rec["generated_at"]) >= nxt_open:
        print(f"[mkt-thesis] late run ({rec['generated_at']} ≥ next open {nxt_open.isoformat()}) — a "
              f"backfilled forecast would carry hindsight; refusing to write", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not args.force:
        recent = _recent_forecast(rec["as_of"])
        if recent:
            # DELIVERY RECOVERY (Codex P2r21): if THIS as_of already has a committed READY ledger still
            # inside its lock window, a prior run generated it but delivery may have failed (Telegram down,
            # missing secrets). Point RUN_STATE at that exact file so the post-push notify step RETRIES it —
            # notify_committed's lock-window + ready-family gates keep degraded / older / past-window
            # cooldowns suppressed, so only a still-live ready alert is ever re-sent.
            ready_path = OUT_DIR / f"forecast_{rec['as_of']}.json"
            in_window = pd.Timestamp.now(tz="UTC") < ME.next_session_open_utc(rec["as_of"])
            # only bind delivery-retry to a VALID committed ready ledger (P3 sweep): a corrupt/contract-invalid
            # pre-existing file must NOT be pointed at by RUN_STATE (it would crash or mis-deliver). Parse +
            # contract-validate first; on any failure fall through to a pure cooldown_skip and leave the bad
            # file for the forward validator to reject+persist.
            retry_ok = False
            if recent == rec["as_of"] and ready_path.exists() and in_window:
                try:
                    prev = json.loads(ready_path.read_text(encoding="utf-8"))
                    retry_ok = (isinstance(prev, dict) and prev.get("as_of") == rec["as_of"]
                                and not C.validate_forecast(prev))
                except Exception:  # noqa: BLE001
                    retry_ok = False
            if retry_ok:
                print(f"[mkt-thesis] cadence: ready forecast for {rec['as_of']} already committed and "
                      f"in-window — skip generation, RETRY delivery.", file=sys.stderr)
                (OUT_DIR / RUN_STATE).write_text(json.dumps(
                    {"as_of": rec["as_of"], "file": ready_path.name, "reason": "cooldown_retry_delivery"}),
                    encoding="utf-8")
                return 0
            print(f"[mkt-thesis] cadence: a forecast exists at {recent} (<{COOLDOWN_DAYS}d) — skip (use --force)",
                  file=sys.stderr)
            # record the skip so the post-push notify step can NEVER fall back to an older ready ledger
            (OUT_DIR / RUN_STATE).write_text(json.dumps(
                {"as_of": rec["as_of"], "file": None, "reason": "cooldown_skip"}), encoding="utf-8")
            return 0
    ledger = rec.pop("_ledger")
    path = OUT_DIR / f"{ledger}_{rec['as_of']}.json"
    # NEVER silently overwrite a MALFORMED existing ledger at this path (Codex P2r22 stop-gate): a VALID
    # same-date ledger would have been caught by the cooldown/retry branch above, so a file existing here is
    # either a --force regeneration of a valid ledger (explicit operator intent — fine to replace) or it is
    # CORRUPT. Overwriting a corrupt one would HEAL it before market_thesis_forward.py could reject+persist
    # it in validation_summary.json — hiding the corruption behind a clean run. Refuse and fail closed.
    if path.exists():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            prev_ok = isinstance(prev, dict) and prev.get("as_of") == rec["as_of"]
        except Exception:  # noqa: BLE001
            prev_ok = False
        if not prev_ok:
            print(f"[mkt-thesis] refusing to overwrite malformed existing ledger {path.name} — leaving it "
                  f"for the forward validator to reject+persist (fail-closed).", file=sys.stderr)
            return 1
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    # bind the delivery step to THIS run's exact ledger (Codex P2r16) — degraded files never notify
    (OUT_DIR / RUN_STATE).write_text(json.dumps({"as_of": rec["as_of"], "file": path.name}), encoding="utf-8")
    print(f"[mkt-thesis] {rec['as_of']} {rec['direction']}/{rec['bucket']}/{rec['support_class']} "
          f"(manifest={rec['manifest_status']}) → {path.name}")
    # NO direct send here (Codex P2r24): delivery is ONLY via --notify-only (notify_committed), which the CI
    # job runs AFTER forward validation + durable push + per-file blob==origin/main verification. An
    # immediate --notify would emit user-visible guidance from a ledger that might still fail the validator
    # or never be durably committed — bypassing the entire ex-ante/fail-closed delivery invariant.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
