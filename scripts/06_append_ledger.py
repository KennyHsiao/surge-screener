#!/usr/bin/env python3
"""
Stage 6 — Append today's CONFIRMED picks to reports/performance_ledger.csv.
Forward returns will be filled in by the verify_returns job over coming days.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path


LEDGER_COLUMNS = [
    "scan_date", "ticker", "verdict", "composite_score", "regime_multiplier",
    "tech_score", "catalyst_score", "sentiment_score", "inst_score",
    "sector_score", "options_score",
    "dim1_breakdown", "pattern_type", "macd_state",
    "layer2_path", "layer2_outcome",
    "dd_verdict", "dd_short_thesis_strength",
    "suggested_entry_low", "suggested_entry_high", "suggested_stop",
    "suggested_size_pct",
    "fwd_3d_return", "fwd_7d_return", "fwd_14d_return",
    "fwd_30d_return", "fwd_60d_return",
    "hit_15pct_within_30d", "hit_30pct_within_60d",
    "max_drawdown_30d",
    "notes",
]


def parse_entry_zone(entry_zone: str | None) -> tuple[str, str]:
    """Parse 'low – high' entry zone string into two values."""
    if not entry_zone:
        return ("", "")
    parts = entry_zone.replace("–", "-").replace("—", "-").split("-")
    if len(parts) >= 2:
        return (parts[0].strip().replace("$", ""),
                parts[1].strip().replace("$", ""))
    return (entry_zone.strip().replace("$", ""), "")


def extract_picks_from_report(report_path: str) -> list[dict]:
    """Extract pick data from the summary.json report."""
    with open(report_path) as f:
        data = json.load(f)

    picks = []
    scan_date = data.get("report_date", datetime.utcnow().strftime("%Y-%m-%d"))

    for pick in data.get("ranked_picks", []):
        entry_low, entry_high = parse_entry_zone(pick.get("entry_zone"))
        stop = pick.get("stop_loss", "")
        if isinstance(stop, str):
            stop = stop.split("(")[0].strip().replace("$", "")

        row = {
            "scan_date": scan_date,
            "ticker": pick.get("ticker", ""),
            "verdict": pick.get("verdict", ""),
            "composite_score": pick.get("final_score", ""),
            "regime_multiplier": "",
            "tech_score": "",
            "catalyst_score": "",
            "sentiment_score": "",
            "inst_score": "",
            "sector_score": "",
            "options_score": "",
            "dim1_breakdown": "",
            "pattern_type": "",
            "macd_state": "",
            "layer2_path": "",
            "layer2_outcome": "",
            "dd_verdict": pick.get("verdict", ""),
            "dd_short_thesis_strength": "",
            "suggested_entry_low": entry_low,
            "suggested_entry_high": entry_high,
            "suggested_stop": stop,
            "suggested_size_pct": pick.get("position_size_pct", ""),
            "fwd_3d_return": "",
            "fwd_7d_return": "",
            "fwd_14d_return": "",
            "fwd_30d_return": "",
            "fwd_60d_return": "",
            "hit_15pct_within_30d": "",
            "hit_30pct_within_60d": "",
            "max_drawdown_30d": "",
            "notes": pick.get("key_risk", ""),
        }
        picks.append(row)

    return picks


def append_to_ledger(ledger_path: str, picks: list[dict]):
    """Append picks to the ledger CSV, creating it if needed."""
    ledger = Path(ledger_path)
    file_exists = ledger.exists() and ledger.stat().st_size > 0

    # Check for duplicates
    existing_keys = set()
    if file_exists:
        with open(ledger, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row.get('scan_date', '')}_{row.get('ticker', '')}"
                existing_keys.add(key)

    new_picks = []
    for pick in picks:
        key = f"{pick['scan_date']}_{pick['ticker']}"
        if key not in existing_keys:
            new_picks.append(pick)

    if not new_picks:
        print("[ledger] No new picks to add (all duplicates)")
        return

    with open(ledger, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for pick in new_picks:
            writer.writerow(pick)

    print(f"[ledger] Appended {len(new_picks)} picks to {ledger_path}")


def main():
    parser = argparse.ArgumentParser(description="Stage 6: Append to Ledger")
    parser.add_argument("--report", required=True, help="Path to summary.json")
    parser.add_argument("--ledger", default="reports/performance_ledger.csv")
    args = parser.parse_args()

    if not Path(args.report).exists():
        print(f"[ledger] Report not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    # Ensure ledger directory exists
    Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)

    picks = extract_picks_from_report(args.report)
    if not picks:
        print("[ledger] No picks found in report")
        return

    append_to_ledger(args.ledger, picks)


if __name__ == "__main__":
    main()
