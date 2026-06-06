#!/usr/bin/env python3
"""Audit whether the (time-stale) S&P 500 membership snapshot actually contaminates
a point-in-time surge sample — turning a blunt 90-day "is_stale" block into a
measured, per-sample verdict.

sp500_membership.is_stale() blocks any PIT run whose vendored snapshot is older
than STALE_MAX_AGE_DAYS, because a stale snapshot silently misses index add/drops.
That is the right CONSERVATIVE default. But "old" ≠ "wrong for THIS sample": the
only way staleness biases a surge event is

  a missed DROP (snapshot still thinks the name is a member) on a ticker that
  SURGED *after* its real drop date (which is necessarily after the snapshot).

(A missed ADD can only cause the name to be EXCLUDED from the PIT universe — the
safe direction — so it never contaminates.) This tool fetches an INDEPENDENT
current member list, diffs it against the snapshot, and counts how many surge
events are actually at risk. Output → membership_audit.json + a verdict.

Read-only. Does NOT change the gate; it produces the evidence a human/gate can use.

CLI:
  python scripts/sp500_membership_audit.py \
      --events reports/retrospective/sp500_pit/surge_events.json --as-of 2026-06-06
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

# Independent current-constituents sources (NOT the fja05680 snapshot we're auditing).
_CURRENT_SOURCES = [
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
]
# A run is "audit-clean" only if at-risk events are at/below this share of the sample.
CONTAMINATION_TOLERANCE = 0.01  # ≤1% of events


def _norm(t: str) -> str:
    return (t or "").strip().upper().replace(".", "-")


def _fetch_current() -> tuple[set, str | None]:
    import httpx
    for url in _CURRENT_SOURCES:
        try:
            r = httpx.get(url, timeout=20, follow_redirects=True)
            r.raise_for_status()
            out = set()
            for row in csv.DictReader(io.StringIO(r.text)):
                sym = _norm(row.get("Symbol") or row.get("symbol") or "")
                if sym:
                    out.add(sym)
            if out:
                return out, url
        except Exception:
            continue
    return set(), None


def audit(events_path: str, as_of: str) -> dict:
    """Audit the surge events on disk (CLI / standalone use)."""
    ev = json.loads(Path(events_path).read_text(encoding="utf-8"))
    return audit_events(ev.get("events", []), as_of)


def audit_events(events: list, as_of: str) -> dict:
    """Audit an in-memory surge-event list (used by retro_surge_label to clear a
    time-stale snapshot when the current-list cross-check shows ≤tolerance at-risk)."""
    import sp500_membership as m
    snap = {_norm(t) for t in m.members_on(as_of)}
    current, src = _fetch_current()
    snap_through = m.SNAPSHOT_THROUGH

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of,
        "snapshot_through": snap_through,
        "snapshot_age_days": m.snapshot_age_days(as_of),
        "is_stale_time_based": m.is_stale(as_of),
        "current_source": src,
        "snapshot_member_count": len(snap),
        "current_member_count": len(current),
    }
    if not current:
        result.update({"audit_ran": False,
                       "note": "could not fetch an independent current member list; "
                               "cannot audit — fail closed (treat as stale)."})
        return result

    adds_missed = sorted(current - snap)   # joined after snapshot → snapshot EXCLUDES (safe)
    drops_missed = sorted(snap - current)  # dropped after snapshot → snapshot over-INCLUDES (risk)

    surge_tickers = {_norm(e.get("ticker")) for e in events}
    affected = sorted(set(drops_missed) & surge_tickers)  # only missed-drops can contaminate

    # At-risk events: on a missed-drop ticker AND surged AFTER the snapshot date
    # (a pre-snapshot surge was correctly a member at the time, regardless of a later drop).
    at_risk = [
        {"ticker": _norm(e.get("ticker")), "surge_start": e.get("surge_start"),
         "peak_date": e.get("peak_date"), "magnitude_pct": e.get("magnitude_pct")}
        for e in events
        if _norm(e.get("ticker")) in set(drops_missed)
        and (e.get("surge_start") or "") > snap_through
    ]
    ratio = round(len(at_risk) / len(events), 4) if events else 0.0
    clean = len(at_risk) / max(len(events), 1) <= CONTAMINATION_TOLERANCE

    result.update({
        "audit_ran": True,
        "adds_missed": adds_missed,            # informational (these EXCLUDE, never contaminate)
        "drops_missed": drops_missed,
        "surge_sample_events": len(events),
        "surge_sample_tickers": len(surge_tickers),
        "affected_tickers_in_sample": affected,
        "at_risk_events": at_risk,
        "at_risk_event_count": len(at_risk),
        "contamination_ratio": ratio,
        "tolerance": CONTAMINATION_TOLERANCE,
        "audit_clean": bool(clean),
        "note": (f"{len(adds_missed)} missed adds (safe: excluded), {len(drops_missed)} missed "
                 f"drops; only {len(affected)} touch the sample, {len(at_risk)} event(s) "
                 f"({ratio:.2%}) actually at risk. "
                 + ("AUDIT-CLEAN — staleness does not materially bias this sample; the at-risk "
                    "event(s) can be excluded to make it provably clean."
                    if clean else
                    "NOT clean — at-risk events exceed tolerance; keep blocked.")),
    })
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(_ROOT / "reports" / "retrospective"
                                            / "sp500_pit" / "surge_events.json"))
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--output", default=str(_ROOT / "reports" / "retrospective"
                                            / "sp500_pit" / "membership_audit.json"))
    args = ap.parse_args()

    res = audit(args.events, args.as_of)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"snapshot_through={res['snapshot_through']} age={res.get('snapshot_age_days')}d "
          f"(time-based stale={res.get('is_stale_time_based')})")
    if res.get("audit_ran"):
        print(f"missed adds (safe/excluded): {len(res['adds_missed'])} · "
              f"missed drops: {len(res['drops_missed'])}")
        print(f"affected tickers in sample: {res['affected_tickers_in_sample'] or 'NONE'}")
        print(f"at-risk events: {res['at_risk_event_count']}/{res['surge_sample_events']} "
              f"({res['contamination_ratio']:.2%}) → audit_clean={res['audit_clean']}")
        for e in res["at_risk_events"]:
            print(f"    ⚠ {e['ticker']} surge {e['surge_start']} (+{e['magnitude_pct']}%)")
    print(f"→ {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
