#!/usr/bin/env python3
"""Point-in-time S&P 500 membership — free survivorship-bias correction.

The surge retrospective scans CURRENT index members, which contaminates the result
two ways: (1) names that surged and only THEN joined the index (e.g. APP joined
2025-09-22, HOOD 2025-09-22, SNDK 2025-11-28, CVNA 2025-12-22 — all after their big
moves) inflate the "already in an uptrend" factors; (2) delisted surgers are absent.

This module fixes direction (1) — the dominant bias for the momentum factors — using
free historical membership with add/drop dates from fja05680/sp500
(data/sp500_ticker_start_end.csv: one row per ticker, start_date + end_date, empty
end = still a member). Direction (2) CANNOT be fixed free: yfinance only serves
current-listing history, so fully-delisted members have no price data to reconstruct.
Callers that apply point-in-time membership should record `delisted_data_gap=True`.

S&P MidCap 400 / SmallCap 600 have NO free point-in-time source — only S&P 500 here.

CLI:
    python scripts/sp500_membership.py 2025-08-01 NVDA APP   # was-member checks
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_CSV = REPO / "data" / "sp500_ticker_start_end.csv"

# The vendored snapshot's last membership change (MRSH add). Beyond this date the
# data is blind to newer index changes — callers should treat dates after it as
# best-effort and ideally refresh the CSV from the upstream repo.
SNAPSHOT_THROUGH = "2026-01-14"

STALE_MAX_AGE_DAYS = 90  # beyond this the snapshot is too old to trust for actionable use

_INTERVALS: dict[str, list[tuple[str, str]]] | None = None


def snapshot_age_days(as_of: str) -> int:
    """Days between SNAPSHOT_THROUGH and the YYYY-MM-DD `as_of` (e.g. the run date)."""
    a = date.fromisoformat(SNAPSHOT_THROUGH)
    b = date.fromisoformat(as_of)
    return (b - a).days


def is_stale(as_of: str, max_age: int = STALE_MAX_AGE_DAYS) -> bool:
    """True if the vendored membership snapshot is too old as of `as_of`. A stale snapshot
    silently misses index additions/drops after SNAPSHOT_THROUGH, biasing the universe —
    so a stale point-in-time run must NOT be treated as actionable (see retro_factor_lift)."""
    return snapshot_age_days(as_of) > max_age


def _yf(ticker: str) -> str:
    """fja05680 uses dotted class shares (BRK.B); yfinance uses BRK-B."""
    return ticker.strip().upper().replace(".", "-")


def _load() -> dict[str, list[tuple[str, str]]]:
    """ticker -> list of (start_date, end_date) membership intervals (end '' = open)."""
    global _INTERVALS
    if _INTERVALS is not None:
        return _INTERVALS
    out: dict[str, list[tuple[str, str]]] = {}
    with _CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = _yf(row["ticker"])
            start = (row.get("start_date") or "").strip()
            end = (row.get("end_date") or "").strip()
            if not start:
                continue
            out.setdefault(t, []).append((start, end))
    _INTERVALS = out
    return out


def was_member(ticker: str, on: str) -> bool:
    """True if `ticker` (yfinance form) was an S&P 500 member on the YYYY-MM-DD `on`.

    A ticker can have multiple membership stints (added, dropped, re-added); any
    interval that brackets `on` counts. end_date '' means still a member.
    """
    t = _yf(ticker)
    for start, end in _load().get(t, []):
        if start <= on and (end == "" or on <= end):
            return True
    return False


def members_on(on: str) -> set[str]:
    """Set of S&P 500 members (yfinance form) on the YYYY-MM-DD `on`."""
    return {t for t, ivals in _load().items()
            for (start, end) in ivals
            if start <= on and (end == "" or on <= end)}


def universe_in_window(start: str, end: str) -> set[str]:
    """Every ticker that was a member at ANY point in [start, end] — the population to
    FETCH so no member is missed, then filter per-event with was_member()."""
    out: set[str] = set()
    for t, ivals in _load().items():
        for (s, e) in ivals:
            if s <= end and (e == "" or e >= start):
                out.add(t)
                break
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: sp500_membership.py YYYY-MM-DD TICKER [TICKER ...]")
        return 2
    on = sys.argv[1]
    print(f"members on {on}: {len(members_on(on))} (snapshot through {SNAPSHOT_THROUGH})")
    for t in sys.argv[2:]:
        print(f"  {t}: {'MEMBER' if was_member(t, on) else 'not a member'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
