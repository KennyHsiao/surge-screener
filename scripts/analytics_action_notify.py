#!/usr/bin/env python3
"""Send Telegram notifications for automated analytics follow-up actions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
DEFAULT_CHECKS = REPO / "reports" / "analytics_checks" / "latest.json"
DEFAULT_RECEIPTS = REPO / "reports" / "analytics_checks" / "no_picks_alerts.json"
NO_PICKS_CHECK_ID = "performance:no_confirmed_picks_streak"
NOTIFY_ACTIONS = {"TG_WARN", "REVIEW_REQUIRED"}
Sender = Callable[[str, str, str, str], bool]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_sender() -> Sender:
    notify_path = Path(__file__).resolve().with_name("05_notify.py")
    spec = importlib.util.spec_from_file_location("surge_telegram_notify", notify_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Telegram notifier from {notify_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.send_telegram_message


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_receipts(path: str | Path) -> dict[str, Any]:
    receipt_path = Path(path)
    if not receipt_path.exists():
        return {"schema_version": 1, "sent": []}
    data = _read_json(receipt_path)
    if "sent" not in data or not isinstance(data["sent"], list):
        data["sent"] = []
    data.setdefault("schema_version", 1)
    return data


def _write_receipts(path: str | Path, data: dict[str, Any]) -> None:
    receipt_path = Path(path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(receipt_path)


def _parse_latest_pick_date(message: Any) -> str | None:
    match = re.search(r"\bsince\s+(\d{4}-\d{2}-\d{2})\b", str(message or ""))
    return match.group(1) if match else None


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _select_no_picks_alert(report: dict[str, Any]) -> dict[str, Any] | None:
    for check in report.get("checks", []):
        if check.get("id") != NO_PICKS_CHECK_ID:
            continue
        action = str(check.get("recommended_action") or "NO_ACTION")
        if check.get("status") == "PASS" or action not in NOTIFY_ACTIONS:
            return None
        latest_pick_date = (
            check.get("latest_pick_date")
            or _parse_latest_pick_date(check.get("message"))
            or "unknown"
        )
        threshold = _int_value(
            check.get("notify_threshold"),
            10 if action == "REVIEW_REQUIRED" else 5,
        )
        trading_days = _int_value(check.get("value"))
        key = f"{NO_PICKS_CHECK_ID}:{latest_pick_date}:{action}"
        return {
            "key": key,
            "check_id": NO_PICKS_CHECK_ID,
            "action": action,
            "as_of_date": report.get("as_of_date"),
            "latest_pick_date": latest_pick_date,
            "trading_days": trading_days,
            "threshold": threshold,
            "message": check.get("message"),
        }
    return None


def _format_message(alert: dict[str, Any]) -> str:
    next_step = (
        "Review screener strictness, data freshness, and market regime before changing weights."
        if alert["action"] == "REVIEW_REQUIRED"
        else "Keep monitoring; do not change scoring weights from this alert alone."
    )
    return "\n".join([
        "Analytics DB no-picks alert",
        f"Action: {alert['action']}",
        f"As of: {alert.get('as_of_date') or 'unknown'}",
        f"Latest confirmed pick: {alert['latest_pick_date']}",
        f"Trading weekdays without confirmed picks: {alert['trading_days']}",
        f"Threshold: {alert['threshold']}",
        f"Next: {next_step}",
    ])


def notify_from_checks(
    *,
    checks_path: str | Path = DEFAULT_CHECKS,
    receipts_path: str | Path = DEFAULT_RECEIPTS,
    bot_token: str | None = None,
    chat_id: str | None = None,
    sender: Sender | None = None,
) -> dict[str, Any]:
    """Send the no-picks Telegram alert from analytics checks, once per streak level."""
    report = _read_json(checks_path)
    alert = _select_no_picks_alert(report)
    if alert is None:
        return {"status": "no_alert"}

    bot_token = bot_token if bot_token is not None else os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return {"status": "missing_credentials", "alert": alert}

    receipts = _read_receipts(receipts_path)
    sent_keys = {str(item.get("key")) for item in receipts.get("sent", [])}
    if alert["key"] in sent_keys:
        return {"status": "already_sent", "alert": alert}

    send = sender or _load_sender()
    text = _format_message(alert)
    if not send(bot_token, chat_id, text, "Markdown"):
        return {"status": "send_failed", "alert": alert}

    receipts["updated_at"] = _utc_now()
    receipts["sent"].append({
        "key": alert["key"],
        "check_id": alert["check_id"],
        "action": alert["action"],
        "as_of_date": alert.get("as_of_date"),
        "latest_pick_date": alert["latest_pick_date"],
        "trading_days": alert["trading_days"],
        "threshold": alert["threshold"],
        "sent_at": receipts["updated_at"],
    })
    _write_receipts(receipts_path, receipts)
    return {"status": "sent", "alert": alert}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send analytics action Telegram notifications")
    parser.add_argument("--checks", default=str(DEFAULT_CHECKS))
    parser.add_argument("--receipts", default=str(DEFAULT_RECEIPTS))
    args = parser.parse_args(argv)

    result = notify_from_checks(checks_path=args.checks, receipts_path=args.receipts)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if result["status"] == "send_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
