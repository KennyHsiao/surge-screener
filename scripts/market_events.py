#!/usr/bin/env python3
"""Code-owned event manifest for the 大盤行情研判 Tier-1 baseline (design v7 §1a). VERIFIED, NO WebSearch.

Events come ONLY from an allowlist of official/structured sources; the LLM may later summarize these records
but never select or invent them. Each required event has a per-type schema (required fields + freshness) so
two implementations compute the SAME `manifest_status ∈ {ready, degraded}`. `degraded` (any required event
missing/stale) ⇒ the forecaster runs in regime-only / NON-alerting mode (delivery is gated on this in P3).

Allowlist:
  CPI    fred:CPIAUCSL   {released_at, value, prior}   stale > ~45d         (surprise NULLABLE — no free
  JOBS   fred:PAYEMS     {released_at, value, prior}   stale > ~45d          verified consensus source; never faked)
  FOMC   calendar:fomc   {last_decision_at, last_rate, next_meeting_at}      stale if next_meeting_at past
         = content/fomc_calendar.json (manually curated from the official federalreserve.gov schedule)
  UST10Y yf:^TNX         {released_at=close, value, delta_1d}               stale if close older than last session
  DXY    yf:DX-Y.NYB     {released_at=close, value, delta_1d}               stale if close older than last session

NOTE: CPI/JOBS need a FRED feed (free key). Until that is wired they are MISSING ⇒ `manifest_status=degraded`
BY DEFINITION ⇒ Tier 1 is non-alerting — honest about not yet being event-driven.

CLI:  python scripts/market_events.py [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import retro_reconstruct as rr            # noqa: E402 — cached OHLCV fetch (^TNX / DXY)

FOMC_CALENDAR = REPO / "content" / "fomc_calendar.json"

EVENT_SPECS = {
    "CPI":    {"source_id": "fred:CPIAUCSL", "required": ["released_at", "value", "prior"], "max_age_days": 45},
    "JOBS":   {"source_id": "fred:PAYEMS",   "required": ["released_at", "value", "prior"], "max_age_days": 45},
    "FOMC":   {"source_id": "calendar:fomc", "required": ["last_decision_at", "last_rate", "next_meeting_at"]},
    "UST10Y": {"source_id": "yf:^TNX",       "required": ["released_at", "value", "delta_1d"], "market_close": True},
    "DXY":    {"source_id": "yf:DX-Y.NYB",   "required": ["released_at", "value", "delta_1d"], "market_close": True},
}
REQUIRED = tuple(EVENT_SPECS)             # ALL required for manifest_status == "ready"


def _nyse_holiday_calendar():
    """NYSE holiday rules (Codex stop-gate fix): the FEDERAL calendar falsely passes stale closes around
    Columbus Day / Veterans Day (NYSE OPEN on both — skipping them moved the 'previous session' a day too
    far back), and misses Good Friday (NYSE CLOSED). Build the actual NYSE set instead."""
    from pandas.tseries.holiday import (
        AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay, USMartinLutherKingJr,
        USMemorialDay, USPresidentsDay, USThanksgivingDay, nearest_workday, sunday_to_monday,
    )

    class NYSEHolidayCalendar(AbstractHolidayCalendar):
        rules = [
            # NYSE does NOT observe a Saturday New Year's on the prior Friday (Dec 31 is a year-end
            # accounting day and the market TRADES it — e.g. Fri 2021-12-31). nearest_workday would mark
            # that Friday a holiday and falsely pass a Dec-30 stale close (stop-gate). Sunday→Monday only.
            Holiday("NewYearsDay", month=1, day=1, observance=sunday_to_monday),
            USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
            Holiday("Juneteenth", month=6, day=19, start_date="2022-06-19", observance=nearest_workday),
            Holiday("IndependenceDay", month=7, day=4, observance=nearest_workday),
            USLaborDay, USThanksgivingDay,
            Holiday("Christmas", month=12, day=25, observance=nearest_workday),
        ]

    return NYSEHolidayCalendar()


# One-off NYSE closures not derivable from holiday rules (mourning days, weather). A closure missing from
# this list makes affected windows read benchmark_session_gap → non-publishable (fail-closed) until a human
# verifies and adds the date here — auditable, never silently absorbed.
SPECIAL_CLOSURES = (
    "2007-01-02",  # G.R. Ford national day of mourning
    "2012-10-29", "2012-10-30",  # Hurricane Sandy
    "2018-12-05",  # G.H.W. Bush national day of mourning
    "2025-01-09",  # J. Carter national day of mourning
)


def nyse_cbd() -> pd.offsets.CustomBusinessDay:
    """The NYSE trading-day offset: rule-based holidays + the SPECIAL_CLOSURES above."""
    return pd.offsets.CustomBusinessDay(calendar=_nyse_holiday_calendar(), holidays=list(SPECIAL_CLOSURES))


def next_session_open_utc(as_of: str) -> pd.Timestamp:
    """The NEXT NYSE session's 09:30 America/New_York open after as_of, in UTC. Used as the UPPER lock-time
    bound: a forecast 'for' as_of generated at/after the next open had access to post-t0 trading information
    (late backfill = hindsight) and must be rejected (stop-gate)."""
    nxt = (pd.Timestamp(as_of) + nyse_cbd()).date().isoformat()
    return pd.Timestamp(f"{nxt} 09:30", tz="America/New_York").tz_convert("UTC")


def last_completed_session(as_of: str) -> pd.Timestamp:
    """The last COMPLETED US trading session for a post-close evaluation at as_of (Codex P2r11): the locked
    forecast path runs AFTER the as_of close by contract, so when as_of IS a NYSE session its OWN close has
    completed and is required — accepting the prior session let one-session-stale ^TNX/DXY read ready (and a
    dropped current close silently collapsed to the prior one). Only a NON-session as_of (weekend/holiday)
    falls back to the previous session. Residual calendar mismatch errs DEGRADED, never falsely ready."""
    ts = pd.Timestamp(as_of)
    cbd = nyse_cbd()
    if ts + 0 * cbd == ts:      # as_of is itself a session → post-close ⇒ its own close must exist
        return ts
    return ts - cbd


# ── pure manifest logic (testable, no I/O) ──────────────────────────────────
def evaluate_event(etype: str, rec: dict | None, as_of: str) -> dict:
    spec = EVENT_SPECS[etype]
    base = {"type": etype, "source_id": spec["source_id"]}
    if rec is None:
        return {**base, "present": False, "fresh": False, "stale_reason": "missing"}
    missing = [f for f in spec["required"] if rec.get(f) in (None, "")]
    if missing:
        return {**base, "present": False, "fresh": False, "stale_reason": "missing_fields:" + ",".join(missing)}
    asof = pd.Timestamp(as_of)
    if etype == "FOMC":
        reason = None if pd.Timestamp(rec["next_meeting_at"]) > asof else "next_meeting_passed"
        if reason is None:
            # the calendar auto-advances past a meeting, but the rate/decision fields are hand-maintained —
            # require PROOF they were refreshed at/after the latest decision, else a stale rate reads ready (P2r1)
            ra = rec.get("rate_as_of")
            if not ra or pd.Timestamp(ra) < pd.Timestamp(rec["last_decision_at"]):
                reason = "decision_not_refreshed"
            elif pd.Timestamp(ra) > asof:
                # a backfilled/forced historical run must not see a FUTURE decision's rate as fresh —
                # the fixture stores only the LATEST rate, so any as_of before rate_as_of fails closed (P2r4)
                reason = "future_rate_as_of"
        echo = {k: rec.get(k) for k in spec["required"]}
    else:
        rel = pd.Timestamp(rec["released_at"])
        if rel > asof:                                   # look-ahead data can never be "fresh" (P2r1)
            reason = "future_released_at"
        elif spec.get("market_close"):
            min_ok = last_completed_session(as_of)
            reason = None if rel >= min_ok else f"stale_close:{rec['released_at']}<{min_ok.date()}"
        else:
            age = (asof - rel).days
            reason = None if age <= spec["max_age_days"] else f"stale:{age}d>max{spec['max_age_days']}"
        # echo ALL required fields (Codex P2r6: delta_1d was enforced as required yet dropped from the
        # emitted manifest, so downstream consumers lost a required macro-movement field even when ready)
        echo = {k: rec.get(k) for k in spec["required"]}
    return {**base, "present": True, "fresh": reason is None, "stale_reason": reason, **echo}


def compute_manifest(events_by_type: dict, as_of: str) -> dict:
    evals = [evaluate_event(t, events_by_type.get(t), as_of) for t in REQUIRED]
    ready = all(e["present"] and e["fresh"] for e in evals)
    return {"as_of": as_of, "manifest_status": "ready" if ready else "degraded",
            "missing": [e["type"] for e in evals if not e["present"]],
            "stale": [e["type"] for e in evals if e["present"] and not e["fresh"]],
            "events": evals}


# ── fetchers (I/O; each returns a record or None — never raises) ─────────────
def load_fomc(as_of: str, path: Path = FOMC_CALENDAR) -> dict | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    meetings = sorted(d.get("meetings") or [])
    asof = pd.Timestamp(as_of)
    past = [m for m in meetings if pd.Timestamp(m) <= asof]
    future = [m for m in meetings if pd.Timestamp(m) > asof]
    return {"last_decision_at": past[-1] if past else None, "last_rate": d.get("last_rate"),
            "next_meeting_at": future[0] if future else None, "source": d.get("source"),
            "rate_as_of": d.get("rate_as_of")}  # when the human last refreshed the rate/decision fields


def _yf_level(ticker: str) -> dict | None:
    df = rr._hist_auto_adjust_false(ticker, "1mo")
    if df is None or df.empty:
        return None
    s = df["Close"].dropna()
    if s.size < 2:
        return None
    idx = pd.to_datetime(s.index).tz_localize(None).normalize()
    return {"released_at": idx[-1].date().isoformat(), "value": round(float(s.iloc[-1]), 4),
            "delta_1d": round(float(s.iloc[-1] - s.iloc[-2]), 4)}


def parse_fred_observations(payload: dict, as_of: str) -> dict | None:
    """PURE point-in-time parser for FRED/ALFRED observations (Codex P2r2). The observation `date` is the
    STATISTICAL PERIOD, not when the value became knowable — using it as released_at is look-ahead (May CPI
    is published mid-June). released_at must therefore be the vintage `realtime_start` (true publication
    date); observations lacking it, or first published AFTER as_of, are excluded. Returns None (⇒ degraded)
    when no two as-of-knowable observations exist — degraded over fabricated freshness."""
    obs = []
    for o in payload.get("observations", []):
        if o.get("value") in (".", None) or not o.get("realtime_start"):
            continue
        if o["realtime_start"] > as_of:        # not yet published at as_of — look-ahead, exclude
            continue
        obs.append(o)
    # newest PERIOD first; for a repeated period keep the latest vintage known at as_of
    obs.sort(key=lambda o: (o["date"], o["realtime_start"]))
    by_period: dict[str, dict] = {o["date"]: o for o in obs}
    ordered = [by_period[d] for d in sorted(by_period, reverse=True)]
    if len(ordered) < 2:
        return None
    # SHAPE guard (Codex P2r10): with the API's default output_type=1, realtime_start is the QUERY window
    # bound, stamped IDENTICALLY across observations — not a release date. Distinct monthly periods can never
    # share an initial release date, so uniform realtime_start ⇒ wrong output_type ⇒ refuse (degraded).
    if len({o["realtime_start"] for o in ordered[:4]}) < min(len(ordered), 4):
        return None
    return {"released_at": ordered[0]["realtime_start"], "value": float(ordered[0]["value"]),
            "prior": float(ordered[1]["value"]), "surprise": None,  # surprise NULLABLE — no free consensus
            "period": ordered[0]["date"]}


def load_fred(series: str, as_of: str) -> dict | None:
    """FRED actuals (CPIAUCSL / PAYEMS) with POINT-IN-TIME vintage semantics. Needs FRED_API_KEY; without it
    returns None → manifest degraded."""
    if not os.environ.get("FRED_API_KEY"):
        return None
    try:  # pragma: no cover — only exercised when a key is present
        import httpx
        r = httpx.get("https://api.stlouisfed.org/fred/series/observations",
                      params={"series_id": series, "api_key": os.environ["FRED_API_KEY"],
                              "file_type": "json", "sort_order": "desc", "limit": 8,
                              # output_type=4 = INITIAL RELEASES: each observation's realtime_start is the
                              # date the value was FIRST published (the knowability event). The default
                              # output_type=1 stamps realtime_start from the QUERY window — not a release
                              # date (Codex P2r10); the parser's shape guard rejects that form too.
                              "output_type": 4,
                              "realtime_start": "1900-01-01", "realtime_end": as_of}, timeout=20)
        r.raise_for_status()
        return parse_fred_observations(r.json(), as_of)
    except Exception:  # noqa: BLE001
        return None


def build_manifest(as_of: str) -> dict:
    events = {"CPI": load_fred("CPIAUCSL", as_of), "JOBS": load_fred("PAYEMS", as_of), "FOMC": load_fomc(as_of),
              "UST10Y": _yf_level("^TNX"), "DXY": _yf_level("DX-Y.NYB")}
    return compute_manifest(events, as_of)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the verified event manifest + manifest_status")
    ap.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    args = ap.parse_args()
    m = build_manifest(args.as_of)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    print(f"\n[mkt-events] as_of={m['as_of']} manifest_status={m['manifest_status']} "
          f"missing={m['missing']} stale={m['stale']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
