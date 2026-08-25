#!/usr/bin/env python3
"""Create durable, run-bound evidence for the Stage 7 ledger verifier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "stage7_verdict_v1"
FORWARD_VALUE_FIELDS = (
    "fwd_3d_return",
    "fwd_7d_return",
    "fwd_14d_return",
    "fwd_30d_return",
    "fwd_60d_return",
    "max_drawdown_30d",
)
FORWARD_BOOL_FIELDS = (
    "hit_15pct_within_30d",
    "hit_30pct_within_60d",
)
FORWARD_FIELDS = (*FORWARD_VALUE_FIELDS, *FORWARD_BOOL_FIELDS)
REQUIRED_LEDGER_FIELDS = ("scan_date", "ticker", *FORWARD_FIELDS)
UPDATE_PATTERN = re.compile(r"\[verify\] Updated (\d+) rows in ")
PUBLISH_PATHS = [
    "reports/performance_ledger.csv",
    "reports/analytics_checks/no_picks_alerts.json",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def _file_hashes(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    payload = path.read_bytes()
    return {
        "exists": True,
        "path": str(path),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _row_key(row: dict[str, str]) -> str:
    return f"{row.get('scan_date', '')}|{row.get('ticker', '').strip().upper()}"


def snapshot_ledger(path: str | Path) -> dict[str, Any]:
    ledger = Path(path)
    result = _file_hashes(ledger)
    if not result["exists"]:
        result.update({"fieldnames": [], "row_count": 0, "rows": []})
        return result

    with ledger.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    keys = [_row_key(row) for row in rows]
    key_counts = Counter(keys)
    result.update({
        "fieldnames": fieldnames,
        "row_count": len(rows),
        "missing_required_fields": sorted(set(REQUIRED_LEDGER_FIELDS) - set(fieldnames)),
        "invalid_keys": sorted(
            key for key, row in zip(keys, rows)
            if not str(row.get("scan_date") or "").strip()
            or not str(row.get("ticker") or "").strip()
        ),
        "duplicate_keys": sorted(key for key, count in key_counts.items() if count > 1),
        "blank_forward_cells": sum(
            1 for row in rows for field in FORWARD_FIELDS if not str(row.get(field) or "").strip()
        ),
        "rows_with_blank_forward_fields": sum(
            1 for row in rows if any(not str(row.get(field) or "").strip() for field in FORWARD_FIELDS)
        ),
    })
    result["rows"] = rows
    return result


def snapshot_receipt(path: str | Path) -> dict[str, Any]:
    receipt = Path(path)
    result = _file_hashes(receipt)
    data: dict[str, Any] | None = None
    parse_error: str | None = None
    if result["exists"]:
        try:
            loaded = json.loads(receipt.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
            else:
                parse_error = "receipt root must be an object"
        except (OSError, json.JSONDecodeError) as exc:
            parse_error = str(exc)
    sent = data.get("sent", []) if isinstance(data, dict) else []
    result.update({
        "parse_error": parse_error,
        "sent_count": len(sent) if isinstance(sent, list) else None,
    })
    result["data"] = data
    return result


def capture_baseline(
    *, ledger: str | Path, receipt: str | Path, output: str | Path, run_id: str,
    run_attempt: str, head_sha: str, event_name: str, schedule: str,
) -> dict[str, Any]:
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "phase": "baseline",
        "captured_at": _utc_now(),
        "run": {
            "id": str(run_id),
            "attempt": str(run_attempt),
            "head_sha": str(head_sha),
            "event_name": str(event_name),
            "schedule": str(schedule),
        },
        "ledger": snapshot_ledger(ledger),
        "receipt": snapshot_receipt(receipt),
    }
    errors = []
    if not re.fullmatch(r"[0-9a-f]{40}", str(head_sha)):
        errors.append("run head_sha must be a 40-character lowercase Git SHA")
    if not baseline["ledger"]["exists"]:
        errors.append("performance ledger is missing at run head")
    if baseline["ledger"].get("missing_required_fields"):
        errors.append("performance ledger is missing required fields")
    if baseline["ledger"].get("invalid_keys"):
        errors.append("performance ledger contains blank scan_date or ticker keys")
    if baseline["ledger"]["duplicate_keys"]:
        errors.append("performance ledger contains duplicate scan_date+ticker keys")
    if baseline["receipt"].get("parse_error"):
        errors.append(f"receipt is invalid: {baseline['receipt']['parse_error']}")
    baseline["errors"] = errors
    _atomic_write_json(output, baseline)
    if errors:
        raise RuntimeError("; ".join(errors))
    return baseline


def _valid_forward_value(field: str, value: str) -> bool:
    if field in FORWARD_BOOL_FIELDS:
        return value in {"True", "False", "true", "false"}
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def compare_ledgers(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    changed_cells: list[dict[str, str]] = []
    if not after.get("exists"):
        errors.append("performance ledger disappeared")
        return {"errors": errors, "changed_cells": changed_cells, "appended_keys": []}
    if before.get("fieldnames") != after.get("fieldnames"):
        errors.append("performance ledger header changed")
    if after.get("missing_required_fields"):
        errors.append("performance ledger is missing required fields")
    if after.get("invalid_keys"):
        errors.append("performance ledger contains blank scan_date or ticker keys")
    if after.get("duplicate_keys"):
        errors.append("performance ledger contains duplicate scan_date+ticker keys")

    before_rows = before.get("rows") if isinstance(before.get("rows"), list) else []
    after_rows = after.get("rows") if isinstance(after.get("rows"), list) else []
    before_keys = [_row_key(row) for row in before_rows]
    after_keys = [_row_key(row) for row in after_rows]
    before_set = set(before_keys)
    after_by_key = {_row_key(row): row for row in after_rows}
    retained_order = [key for key in after_keys if key in before_set]
    if retained_order != before_keys:
        errors.append("pre-existing ledger keys were removed, duplicated, or reordered")

    for row in before_rows:
        key = _row_key(row)
        current = after_by_key.get(key)
        if current is None:
            continue
        for field in before.get("fieldnames", []):
            old = str(row.get(field) or "")
            new = str(current.get(field) or "")
            if old == new:
                continue
            if field not in FORWARD_FIELDS:
                errors.append(f"{key}: protected field {field} changed")
            elif old:
                errors.append(f"{key}: previously committed {field} was overwritten")
            elif not _valid_forward_value(field, new):
                errors.append(f"{key}: new {field} value is invalid")
            else:
                changed_cells.append({"key": key, "field": field, "value": new})

    return {
        "errors": sorted(set(errors)),
        "changed_cells": changed_cells,
        "appended_keys": [key for key in after_keys if key not in before_set],
    }


def compare_receipts(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    before_data = before.get("data")
    after_data = after.get("data")
    if before.get("exists") and not after.get("exists"):
        errors.append("no-picks receipt disappeared")
        return {"errors": errors, "appended_keys": []}
    if after.get("parse_error"):
        errors.append(f"no-picks receipt is invalid: {after['parse_error']}")
        return {"errors": errors, "appended_keys": []}
    if before_data is None and after_data is None:
        return {"errors": errors, "appended_keys": []}
    if not isinstance(after_data, dict):
        errors.append("no-picks receipt root is not an object")
        return {"errors": errors, "appended_keys": []}

    old = before_data if isinstance(before_data, dict) else {"sent": []}
    old_sent = old.get("sent", [])
    new_sent = after_data.get("sent", [])
    if not isinstance(old_sent, list) or not isinstance(new_sent, list):
        errors.append("no-picks receipt sent field must remain a list")
        return {"errors": errors, "appended_keys": []}
    if new_sent[: len(old_sent)] != old_sent:
        errors.append("existing no-picks receipt entries changed or were reordered")
    if after_data.get("schema_version") != old.get("schema_version", 1):
        errors.append("no-picks receipt schema_version changed")
    keys = [
        str(item.get("key") or "").strip()
        for item in new_sent if isinstance(item, dict)
    ]
    if len(keys) != len(new_sent) or not all(keys) or len(keys) != len(set(keys)):
        errors.append("no-picks receipt contains missing or duplicate keys")
    for key, value in old.items():
        if key not in {"sent", "updated_at"} and after_data.get(key) != value:
            errors.append(f"no-picks receipt protected field {key} changed")
    if len(new_sent) == len(old_sent) and after_data != old:
        errors.append("no-picks receipt changed without an appended notification")
    return {
        "errors": sorted(set(errors)),
        "appended_keys": keys[len(old_sent):],
    }


def _load_optional_json(path: str | Path) -> dict[str, Any] | None:
    source = Path(path)
    if not source.is_file():
        return None
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _updated_row_count(comparison: dict[str, Any]) -> int:
    return len({item["key"] for item in comparison.get("changed_cells", [])})


def _update_count(path: str | Path) -> int | None:
    log = Path(path)
    if not log.is_file():
        return None
    matches = UPDATE_PATTERN.findall(log.read_text(encoding="utf-8", errors="replace"))
    return int(matches[-1]) if matches else None


def _analytics_summary(path: str | Path) -> dict[str, Any]:
    loaded = _load_optional_json(path)
    if loaded is None:
        raise ValueError("job-local Analytics checks are missing or invalid")
    return {
        "scope": "github_runner_ephemeral",
        "authoritative_for_7f": False,
        "as_of_date": loaded.get("as_of_date"),
        "status": loaded.get("status"),
        "summary": loaded.get("summary"),
        "today_signal_readiness": loaded.get("today_signal_readiness"),
        "warning_codes": loaded.get("warning_codes"),
    }


def _state(
    *, integrity_errors: list[str], step_failures: list[str],
    evidence_errors: list[str], updated: bool, ready: bool,
) -> str:
    if integrity_errors:
        return "FAIL_LEDGER_INTEGRITY"
    if step_failures:
        return "FAIL_JOB"
    if evidence_errors:
        return "FAIL_EVIDENCE"
    return ("READY_" if ready else "PASS_") + ("UPDATED" if updated else "NOOP")


def _assess(
    *, baseline: dict[str, Any], ledger: str | Path, receipt: str | Path,
    verify_log: str | Path, step_outcomes: dict[str, str], allow_appends: bool,
) -> dict[str, Any]:
    current_ledger = snapshot_ledger(ledger)
    current_receipt = snapshot_receipt(receipt)
    ledger_comparison = compare_ledgers(baseline.get("ledger", {}), current_ledger)
    receipt_comparison = compare_receipts(baseline.get("receipt", {}), current_receipt)
    update_count = _update_count(verify_log)
    evidence_errors = list(baseline.get("errors") or [])
    if baseline.get("schema_version") != SCHEMA_VERSION or baseline.get("phase") != "baseline":
        evidence_errors.append("Stage 7 baseline schema or phase is invalid")
    if step_outcomes.get("verify_returns") == "success" and update_count is None:
        evidence_errors.append("verify_returns succeeded without an Updated N rows marker")
    if update_count is not None and update_count != _updated_row_count(ledger_comparison):
        evidence_errors.append(
            "verify_returns update count does not match the run-head ledger comparison"
        )
    integrity_errors = ledger_comparison["errors"] + receipt_comparison["errors"]
    if ledger_comparison["appended_keys"] and not allow_appends:
        integrity_errors.append("Stage 7 introduced new ledger rows before publication")
    return {
        "ledger": current_ledger,
        "receipt": current_receipt,
        "ledger_comparison": ledger_comparison,
        "receipt_comparison": receipt_comparison,
        "verify_updated_rows": update_count,
        "step_outcomes": step_outcomes,
        "step_failures": [name for name, value in step_outcomes.items() if value != "success"],
        "integrity_errors": integrity_errors,
        "evidence_errors": evidence_errors,
        "updated": bool(
            ledger_comparison["changed_cells"] or receipt_comparison["appended_keys"]
        ),
    }


def prepublish_gate(
    *, baseline_path: str | Path, ledger: str | Path, receipt: str | Path,
    verify_log: str | Path, checks: str | Path, verify_outcome: str,
    analytics_outcome: str, output: str | Path,
) -> tuple[dict[str, Any], int]:
    baseline = _load_optional_json(baseline_path)
    if baseline is None:
        result = {
            "schema_version": SCHEMA_VERSION,
            "state": "FAIL_EVIDENCE",
            "checked_at": _utc_now(),
            "errors": ["Stage 7 baseline evidence is missing or invalid"],
        }
        _atomic_write_json(output, result)
        return result, 1

    assessment = _assess(
        baseline=baseline,
        ledger=ledger,
        receipt=receipt,
        verify_log=verify_log,
        step_outcomes={"verify_returns": verify_outcome, "analytics": analytics_outcome},
        allow_appends=False,
    )
    try:
        analytics = _analytics_summary(checks)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        analytics = None
        assessment["evidence_errors"].append(str(exc))
    state = _state(
        integrity_errors=assessment["integrity_errors"],
        step_failures=assessment["step_failures"],
        evidence_errors=assessment["evidence_errors"],
        updated=assessment["updated"],
        ready=True,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "checked_at": _utc_now(),
        "run": baseline.get("run", {}),
        "verify_updated_rows": assessment["verify_updated_rows"],
        "ledger_comparison": assessment["ledger_comparison"],
        "receipt_comparison": assessment["receipt_comparison"],
        "analytics": analytics,
        "errors": (
            assessment["integrity_errors"]
            + assessment["step_failures"]
            + assessment["evidence_errors"]
        ),
    }
    _atomic_write_json(output, result)
    return result, 0 if state.startswith("READY_") else 1


def finalize_verdict(
    *, baseline_path: str | Path, ledger: str | Path, receipt: str | Path,
    verify_log: str | Path, gate_result: str | Path, publish_result: str | Path,
    verify_outcome: str, analytics_outcome: str, publish_outcome: str,
    gate_outcome: str, result_head_sha: str, output: str | Path,
) -> tuple[dict[str, Any], int]:
    baseline = _load_optional_json(baseline_path)
    if baseline is None:
        verdict = {
            "schema_version": SCHEMA_VERSION,
            "state": "FAIL_EVIDENCE",
            "completed_at": _utc_now(),
            "errors": ["Stage 7 baseline evidence is missing or invalid"],
        }
        _atomic_write_json(output, verdict)
        return verdict, 1

    step_outcomes = {
        "verify_returns": verify_outcome,
        "analytics": analytics_outcome,
        "prepublish_gate": gate_outcome,
        "publish": publish_outcome,
    }
    assessment = _assess(
        baseline=baseline,
        ledger=ledger,
        receipt=receipt,
        verify_log=verify_log,
        step_outcomes=step_outcomes,
        allow_appends=True,
    )
    gate = _load_optional_json(gate_result)
    publish = _load_optional_json(publish_result)
    if gate_outcome == "success" and not gate:
        assessment["evidence_errors"].append("pre-publish gate succeeded without a result")
    if gate and not str(gate.get("state") or "").startswith("READY_"):
        assessment["evidence_errors"].append("pre-publish gate result is not ready")
    if publish_outcome == "success" and not publish:
        assessment["evidence_errors"].append("publisher succeeded without a structured result")
    if publish and publish.get("status") not in {"nothing_to_commit", "pushed"}:
        assessment["evidence_errors"].append("publisher returned an unknown status")
    if publish and publish.get("paths") != PUBLISH_PATHS:
        assessment["evidence_errors"].append("publisher result does not match the Stage 7 allowlist")
    publish_attempts = 0
    if publish:
        try:
            publish_attempts = int(publish.get("attempts", 0))
        except (TypeError, ValueError):
            assessment["evidence_errors"].append("publisher attempts is not an integer")
    if not re.fullmatch(r"[0-9a-f]{40}", result_head_sha):
        assessment["evidence_errors"].append("result head is not a valid Git SHA")
    if publish and publish.get("status") == "pushed":
        if publish.get("commit") != result_head_sha:
            assessment["evidence_errors"].append("publisher commit does not match the result head")
    state = _state(
        integrity_errors=assessment["integrity_errors"],
        step_failures=assessment["step_failures"],
        evidence_errors=assessment["evidence_errors"],
        updated=assessment["updated"],
        ready=False,
    )

    before_ledger = dict(baseline.get("ledger", {}))
    before_receipt = dict(baseline.get("receipt", {}))
    after_ledger = assessment["ledger"]
    after_receipt = assessment["receipt"]
    for item in (before_ledger, before_receipt, after_ledger, after_receipt):
        item.pop("rows", None)
        item.pop("data", None)
    verdict = {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "completed_at": _utc_now(),
        "run": baseline.get("run", {}),
        "result_head_sha": result_head_sha,
        "step_outcomes": step_outcomes,
        "verify_updated_rows": assessment["verify_updated_rows"],
        "publisher": publish,
        "coverage": {
            "run_head_bound": bool(baseline.get("run", {}).get("head_sha")),
            "natural_schedule": baseline.get("run", {}).get("event_name") == "schedule",
            "natural_noop_observed": state == "PASS_NOOP",
            "positive_update_observed": bool(assessment["ledger_comparison"]["changed_cells"]),
            "receipt_update_observed": bool(assessment["receipt_comparison"]["appended_keys"]),
            "concurrent_appends_observed": bool(assessment["ledger_comparison"]["appended_keys"]),
            "push_observed": bool(publish and publish.get("status") == "pushed"),
            "push_race_observed": bool(publish and publish_attempts > 1),
        },
        "ledger": {
            "before": before_ledger,
            "after": after_ledger,
            "comparison": assessment["ledger_comparison"],
        },
        "receipt": {
            "before": before_receipt,
            "after": after_receipt,
            "comparison": assessment["receipt_comparison"],
        },
        "analytics": (gate or {}).get("analytics") or {
            "scope": "github_runner_ephemeral",
            "authoritative_for_7f": False,
            "capture_missing": True,
        },
        "errors": (
            assessment["step_failures"]
            + assessment["integrity_errors"]
            + assessment["evidence_errors"]
        ),
    }
    _atomic_write_json(output, verdict)
    return verdict, 0 if state.startswith("PASS_") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Stage 7 validation evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def require(subparser: argparse.ArgumentParser, *names: str) -> None:
        for name in names:
            subparser.add_argument(f"--{name.replace('_', '-')}", required=True)

    baseline = subparsers.add_parser("baseline")
    require(baseline, "ledger", "receipt", "output", "run_id", "run_attempt",
            "head_sha", "event_name")
    baseline.add_argument("--schedule", default="")

    gate = subparsers.add_parser("gate")
    require(gate, "baseline", "ledger", "receipt", "verify_log", "checks",
            "verify_outcome", "analytics_outcome", "output")

    finalize = subparsers.add_parser("finalize")
    require(finalize, "baseline", "ledger", "receipt", "verify_log", "gate_result",
            "publish_result", "verify_outcome", "analytics_outcome", "publish_outcome",
            "gate_outcome", "result_head_sha", "output")

    args = parser.parse_args(argv)
    if args.command == "baseline":
        capture_baseline(
            ledger=args.ledger,
            receipt=args.receipt,
            output=args.output,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            head_sha=args.head_sha,
            event_name=args.event_name,
            schedule=args.schedule,
        )
        return 0
    if args.command == "gate":
        result, return_code = prepublish_gate(
            baseline_path=args.baseline,
            ledger=args.ledger,
            receipt=args.receipt,
            verify_log=args.verify_log,
            checks=args.checks,
            verify_outcome=args.verify_outcome,
            analytics_outcome=args.analytics_outcome,
            output=args.output,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return return_code
    verdict, return_code = finalize_verdict(
        baseline_path=args.baseline,
        ledger=args.ledger,
        receipt=args.receipt,
        verify_log=args.verify_log,
        gate_result=args.gate_result,
        publish_result=args.publish_result,
        verify_outcome=args.verify_outcome,
        analytics_outcome=args.analytics_outcome,
        publish_outcome=args.publish_outcome,
        gate_outcome=args.gate_outcome,
        result_head_sha=args.result_head_sha,
        output=args.output,
    )
    print(json.dumps(verdict, indent=2, ensure_ascii=False, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
