#!/usr/bin/env python3
"""Automated forward validation for course playbook decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO = Path(__file__).resolve().parent.parent


def _repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO / p


def _json_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def load_decisions(path_or_dir: str | Path) -> list[dict[str, Any]]:
    """Load decision rows from a JSON file or a directory of JSON snapshots."""
    path = _repo_path(path_or_dir)
    if not path.exists():
        raise FileNotFoundError(f"decision source not found: {path}")

    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    rows: list[dict[str, Any]] = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        for row in _json_rows(payload):
            enriched = dict(row)
            enriched.setdefault("snapshot_file", str(file))
            rows.append(enriched)
    return rows


def _as_date(value: Any) -> datetime | None:
    try:
        if not value:
            return None
        return datetime.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolve_forward_outcomes(
    decisions: list[dict[str, Any]],
    horizon_days: tuple[int, ...] = (3, 7, 14, 30),
) -> list[dict[str, Any]]:
    """Resolve forward returns from yfinance daily closes.

    Entry uses the decision day's close; each forward return uses the close after
    N later sessions. If the full window is unavailable, that horizon is marked
    unresolved instead of guessed.
    """
    import yfinance as yf

    outcomes: list[dict[str, Any]] = []
    for decision in decisions:
        ticker = str(decision.get("ticker") or "").upper()
        as_of_date = str(decision.get("as_of_date") or "")[:10]
        start_dt = _as_date(as_of_date)
        if not ticker or start_dt is None:
            row = {"ticker": ticker, "as_of_date": as_of_date}
            for horizon in horizon_days:
                row[f"resolved_{horizon}d"] = False
                row[f"fwd_{horizon}d_return"] = None
            outcomes.append(row)
            continue

        end_dt = start_dt + timedelta(days=max(horizon_days) * 3 + 10)
        df = yf.download(
            ticker,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        row = {"ticker": ticker, "as_of_date": as_of_date}
        if df is None or df.empty or "Close" not in df:
            for horizon in horizon_days:
                row[f"resolved_{horizon}d"] = False
                row[f"fwd_{horizon}d_return"] = None
            outcomes.append(row)
            continue

        close = df["Close"].dropna()
        if close.empty:
            for horizon in horizon_days:
                row[f"resolved_{horizon}d"] = False
                row[f"fwd_{horizon}d_return"] = None
            outcomes.append(row)
            continue

        entry = float(close.iloc[0])
        for horizon in horizon_days:
            if entry > 0 and len(close) > horizon:
                row[f"resolved_{horizon}d"] = True
                row[f"fwd_{horizon}d_return"] = round(float(close.iloc[horizon]) / entry - 1.0, 6)
            else:
                row[f"resolved_{horizon}d"] = False
                row[f"fwd_{horizon}d_return"] = None
        outcomes.append(row)
    return outcomes


def _join_outcomes(
    decisions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by_key = {
        (str(row.get("ticker") or "").upper(), str(row.get("as_of_date") or "")[:10]): row
        for row in outcomes
    }
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for decision in decisions:
        key = (
            str(decision.get("ticker") or "").upper(),
            str(decision.get("as_of_date") or "")[:10],
        )
        outcome = by_key.get(key)
        if outcome is not None:
            pairs.append((decision, outcome))
    return pairs


def _verdict(count: int, min_resolved: int) -> str:
    return "exploratory" if count < min_resolved else "validated"


def _summary_rows(
    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    *,
    label_key: str,
    min_resolved: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, pairs in sorted(groups.items()):
        resolved = [
            outcome for _, outcome in pairs
            if outcome.get("resolved_7d") is True and outcome.get("fwd_7d_return") is not None
        ]
        returns = [float(row["fwd_7d_return"]) for row in resolved]
        rows.append({
            label_key: label,
            "resolved": len(resolved),
            "mean_fwd_7d_return": round(mean(returns), 6) if returns else None,
            "hit_rate_7d": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else None,
            "verdict": _verdict(len(resolved), min_resolved),
        })
    return rows


def summarize(
    decisions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    min_resolved: int = 100,
) -> dict[str, Any]:
    pairs = _join_outcomes(decisions, outcomes)
    resolved = [
        (decision, outcome) for decision, outcome in pairs
        if outcome.get("resolved_7d") is True and outcome.get("fwd_7d_return") is not None
    ]

    by_playbook: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    by_factor: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for decision, outcome in pairs:
        playbook = str(decision.get("primary_playbook") or "Unknown")
        by_playbook[playbook].append((decision, outcome))
        for fid in decision.get("factor_ids") or []:
            by_factor[str(fid)].append((decision, outcome))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "accumulating" if len(resolved) < min_resolved else "ready",
        "resolved": len(resolved),
        "min_resolved": int(min_resolved),
        "decision_count": len(decisions),
        "outcome_count": len(outcomes),
        "playbooks": _summary_rows(by_playbook, label_key="playbook", min_resolved=min_resolved),
        "factors": _summary_rows(by_factor, label_key="factor_id", min_resolved=min_resolved),
    }


def write_latest(summary: dict[str, Any], out: str | Path = "reports/playbook_validation/latest.json") -> Path:
    path = _repo_path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_validation(
    *,
    decisions: str | Path = "reports/playbook_decisions",
    output: str | Path = "reports/playbook_validation/latest.json",
    min_resolved: int = 100,
) -> dict[str, Any]:
    try:
        rows = load_decisions(decisions)
    except FileNotFoundError as exc:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "blocked",
            "reason": str(exc),
            "resolved": 0,
            "min_resolved": int(min_resolved),
            "playbooks": [],
            "factors": [],
        }
        write_latest(summary, output)
        return summary

    outcomes = resolve_forward_outcomes(rows)
    summary = summarize(rows, outcomes, min_resolved=min_resolved)
    write_latest(summary, output)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate course playbook decisions")
    parser.add_argument("--decisions", default="reports/playbook_decisions")
    parser.add_argument("--output", default="reports/playbook_validation/latest.json")
    parser.add_argument("--min-resolved", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="print full JSON summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_validation(
            decisions=args.decisions,
            output=args.output,
            min_resolved=args.min_resolved,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should fail on code/config errors.
        print(f"[playbook_validation] error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            "status={status} resolved={resolved}/{min_resolved}".format(
                status=summary.get("status"),
                resolved=summary.get("resolved"),
                min_resolved=summary.get("min_resolved"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
