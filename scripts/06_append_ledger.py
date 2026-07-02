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
    "sector_score", "options_score", "analyst_score",
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


def _ticker_key(value) -> str:
    return str(value or "").strip().upper()


def _compact_json(value) -> str:
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_sibling_full_report(report_path: str | Path) -> dict:
    full_path = Path(report_path).with_name("full.json")
    if not full_path.exists():
        return {}
    try:
        with open(full_path) as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _index_rows_by_ticker(container: dict, row_keys: tuple[str, ...]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    if not isinstance(container, dict):
        return indexed
    for row_key in row_keys:
        rows = container.get(row_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ticker = _ticker_key(row.get("ticker"))
            if ticker and ticker not in indexed:
                indexed[ticker] = row
    return indexed


def _full_report_indexes(full_data: dict) -> dict[str, dict[str, dict]]:
    if not isinstance(full_data, dict):
        full_data = {}
    return {
        "scored": _index_rows_by_ticker(
            full_data.get("scored_data", {}),
            ("all_scored", "needs_layer2", "watchlist", "rejected"),
        ),
        "layer2": _index_rows_by_ticker(
            full_data.get("layer2_data", {}),
            ("all_results", "continue_to_dd", "watchlist", "rejected"),
        ),
        "dd": _index_rows_by_ticker(
            full_data.get("dd_data", {}),
            ("all_dd_results", "confirmed", "downgraded", "rejected"),
        ),
    }


def _first_value(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return ""


def _first_mapping(*values) -> dict:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _enrich_row_from_full_report(row: dict, full_data: dict,
                                 indexes: dict[str, dict[str, dict]]) -> dict:
    ticker = _ticker_key(row.get("ticker"))
    scored = indexes.get("scored", {}).get(ticker, {})
    layer2 = indexes.get("layer2", {}).get(ticker, {})
    dd = indexes.get("dd", {}).get(ticker, {})

    scores = _first_mapping(
        scored.get("scores") if isinstance(scored.get("scores"), dict) else None,
        layer2.get("scores") if isinstance(layer2.get("scores"), dict) else None,
        dd.get("scores") if isinstance(dd.get("scores"), dict) else None,
    )

    technical = _first_mapping(
        scored.get("technical_breakdown")
        if isinstance(scored.get("technical_breakdown"), dict) else None,
        layer2.get("technical_breakdown")
        if isinstance(layer2.get("technical_breakdown"), dict) else None,
        dd.get("technical_breakdown")
        if isinstance(dd.get("technical_breakdown"), dict) else None,
    )

    regime = full_data.get("regime_context", {})
    if not isinstance(regime, dict):
        regime = {}

    row.update({
        "regime_multiplier": _first_value(
            row.get("regime_multiplier"),
            regime.get("global_score_multiplier"),
        ),
        "tech_score": _first_value(row.get("tech_score"), scores.get("technical")),
        "catalyst_score": _first_value(row.get("catalyst_score"), scores.get("catalyst")),
        "sentiment_score": _first_value(row.get("sentiment_score"), scores.get("sentiment")),
        "inst_score": _first_value(row.get("inst_score"), scores.get("institutional")),
        "sector_score": _first_value(row.get("sector_score"), scores.get("sector_market")),
        "options_score": _first_value(row.get("options_score"), scores.get("options_flow")),
        "analyst_score": _first_value(row.get("analyst_score"), scores.get("analyst")),
        "dim1_breakdown": _first_value(row.get("dim1_breakdown"), _compact_json(technical)),
        "pattern_type": _first_value(
            row.get("pattern_type"),
            technical.get("pattern_type"),
            scored.get("pattern_type"),
        ),
        "macd_state": _first_value(
            row.get("macd_state"),
            technical.get("macd_state"),
            scored.get("macd_state"),
        ),
        "layer2_path": _first_value(row.get("layer2_path"), layer2.get("layer2_path")),
        "layer2_outcome": _first_value(
            row.get("layer2_outcome"),
            layer2.get("final_verdict"),
            layer2.get("layer2_outcome"),
            layer2.get("verdict"),
        ),
        "dd_verdict": _first_value(dd.get("dd_verdict"), row.get("dd_verdict")),
        "dd_short_thesis_strength": _first_value(
            row.get("dd_short_thesis_strength"),
            dd.get("short_thesis_strength"),
        ),
    })
    return row


def extract_picks_from_report(report_path: str) -> list[dict]:
    """Extract pick data from the summary.json report."""
    with open(report_path) as f:
        data = json.load(f)

    picks = []
    scan_date = data.get("report_date", datetime.utcnow().strftime("%Y-%m-%d"))
    full_data = _load_sibling_full_report(report_path)
    full_indexes = _full_report_indexes(full_data)

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
            "analyst_score": "",
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
        row = _enrich_row_from_full_report(row, full_data, full_indexes)
        picks.append(row)

    return picks


def append_to_ledger(ledger_path: str, picks: list[dict]):
    """Append picks to the ledger CSV, creating it if needed.

    If the on-disk header predates a LEDGER_COLUMNS change (e.g. a newly added
    dimension column like analyst_score), the file is MIGRATED in place —
    rewritten with the current columns, back-filling missing fields as "" — so a
    plain append can't write rows wider than the header and corrupt the CSV.
    Every row is also normalised to exactly LEDGER_COLUMNS, so an unexpected
    extra key in a pick can't raise or misalign either."""
    ledger = Path(ledger_path)
    file_exists = ledger.exists() and ledger.stat().st_size > 0

    # Read existing header + rows (for dedup and possible migration).
    existing_rows: list[dict] = []
    existing_header: list[str] | None = None
    existing_keys = set()
    if file_exists:
        with open(ledger, "r", newline="") as f:
            reader = csv.DictReader(f)
            existing_header = reader.fieldnames
            for row in reader:
                existing_rows.append(row)
                existing_keys.add(f"{row.get('scan_date', '')}_{row.get('ticker', '')}")

    new_picks = [p for p in picks
                 if f"{p['scan_date']}_{p['ticker']}" not in existing_keys]

    header_changed = file_exists and existing_header != LEDGER_COLUMNS

    if not new_picks and not header_changed:
        print("[ledger] No new picks to add (all duplicates)")
        return

    def _norm(row: dict) -> dict:
        return {c: row.get(c, "") for c in LEDGER_COLUMNS}

    if header_changed:
        # One-time schema migration: rewrite the whole file with current columns,
        # back-filling any newly-added column as "" for the historical rows.
        with open(ledger, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(_norm(row))
            for pick in new_picks:
                writer.writerow(_norm(pick))
        print(f"[ledger] Migrated ledger schema; appended {len(new_picks)} picks "
              f"to {ledger_path}")
        return

    with open(ledger, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for pick in new_picks:
            writer.writerow(_norm(pick))

    print(f"[ledger] Appended {len(new_picks)} picks to {ledger_path}")

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
