#!/usr/bin/env python3
"""Resolve a producer report date from its logical GitHub schedule slot."""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping


EOD_SCHEDULE = "30 22 * * 1-5"
EOD_SLOT_UTC = time(22, 30)
MAX_SCHEDULE_DELAY = timedelta(hours=18)


def _previous_weekday(value: date) -> date:
    current = value
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def resolve_report_date(*, schedule: str | None, started_at: datetime) -> date:
    """Return the immutable UTC report date for a supported producer event."""
    if started_at.tzinfo is None:
        raise ValueError("started_at must include a timezone")
    started = started_at.astimezone(timezone.utc)
    normalized_schedule = str(schedule or "").strip()
    if not normalized_schedule:
        return started.date()
    if normalized_schedule != EOD_SCHEDULE:
        raise ValueError(f"unsupported schedule: {normalized_schedule!r}")

    slot_date = started.date()
    if started.timetz().replace(tzinfo=None) < EOD_SLOT_UTC:
        slot_date -= timedelta(days=1)
    slot_date = _previous_weekday(slot_date)
    scheduled_at = datetime.combine(slot_date, EOD_SLOT_UTC, timezone.utc)
    delay = started - scheduled_at
    if delay < timedelta(0) or delay > MAX_SCHEDULE_DELAY:
        raise ValueError(
            "scheduled EOD start is outside the supported 18-hour recovery window"
        )
    return slot_date


def runtime_report_date(
    *,
    environment: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> date:
    """Return a validated job-scoped override or the current UTC date."""
    values = os.environ if environment is None else environment
    override = str(values.get("SURGE_REPORT_DATE") or "").strip()
    if override:
        try:
            return date.fromisoformat(override)
        except ValueError as exc:
            raise ValueError(f"invalid SURGE_REPORT_DATE: {override!r}") from exc
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    return current.astimezone(timezone.utc).date()


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid started_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("started_at must include a timezone")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", default="")
    parser.add_argument("--started-at", required=True)
    args = parser.parse_args(argv)
    report_date = resolve_report_date(
        schedule=args.schedule,
        started_at=parse_timestamp(args.started_at),
    )
    print(report_date.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
