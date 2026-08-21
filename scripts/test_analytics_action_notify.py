#!/usr/bin/env python3
"""Self-contained tests for analytics action Telegram notifications."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analytics_action_notify_under_test",
        ROOT / "scripts" / "analytics_action_notify.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_report(
    path: Path,
    *,
    action: str = "TG_WARN",
    latest_pick_date: str = "2026-06-01",
    successful_zero_pick_scans: int = 5,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    threshold = 10 if action == "REVIEW_REQUIRED" else 5
    bucket = successful_zero_pick_scans // 5
    path.write_text(json.dumps({
        "as_of_date": "2026-06-08",
        "checks": [{
            "id": "performance:no_confirmed_picks_streak",
            "status": "WARN",
            "message": (
                f"No confirmed picks across {successful_zero_pick_scans} successful "
                f"published scans since {latest_pick_date}."
            ),
            "recommended_action": action,
            "value": successful_zero_pick_scans,
            "latest_pick_date": latest_pick_date,
            "notify_threshold": threshold,
            "notification_bucket": bucket,
            "run_coverage_status": "UNKNOWN",
            "scan_state_counts": {
                "successful_zero_pick": successful_zero_pick_scans,
                "successful_with_picks": 0,
                "missing": None,
                "failed": None,
                "unpublished": None,
            },
        }],
    }), encoding="utf-8")


def test_no_picks_warn_sends_once_and_writes_receipt() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "latest.json"
        receipts = root / "no_picks_alerts.json"
        _write_report(checks)
        sent: list[tuple[str, str, str, str]] = []

        def fake_sender(token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
            sent.append((token, chat_id, text, parse_mode))
            return True

        result = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="token",
            chat_id="chat",
            sender=fake_sender,
        )
        if result["status"] != "sent":
            raise AssertionError(result)
        if len(sent) != 1:
            raise AssertionError(sent)
        if "TG_WARN" not in sent[0][2] or "5" not in sent[0][2] or "UNKNOWN" not in sent[0][2]:
            raise AssertionError(sent[0][2])
        data = json.loads(receipts.read_text(encoding="utf-8"))
        if data["sent"][0]["key"] != "performance:no_confirmed_picks_streak:2026-06-01:TG_WARN:1":
            raise AssertionError(data)

        again = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="token",
            chat_id="chat",
            sender=fake_sender,
        )
        if again["status"] != "already_sent":
            raise AssertionError(again)
        if len(sent) != 1:
            raise AssertionError(sent)


def test_no_picks_review_required_has_own_receipt_key() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "latest.json"
        receipts = root / "no_picks_alerts.json"
        _write_report(checks, action="REVIEW_REQUIRED", successful_zero_pick_scans=10)
        sent: list[str] = []

        def fake_sender(token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
            sent.append(text)
            return True

        result = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="token",
            chat_id="chat",
            sender=fake_sender,
        )
        if result["status"] != "sent":
            raise AssertionError(result)
        data = json.loads(receipts.read_text(encoding="utf-8"))
        if data["sent"][0]["key"] != "performance:no_confirmed_picks_streak:2026-06-01:REVIEW_REQUIRED:2":
            raise AssertionError(data)
        if "REVIEW_REQUIRED" not in sent[0] or "10" not in sent[0]:
            raise AssertionError(sent)

        _write_report(checks, action="REVIEW_REQUIRED", successful_zero_pick_scans=15)
        repeated = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="token",
            chat_id="chat",
            sender=fake_sender,
        )
        if repeated["status"] != "sent" or len(sent) != 2:
            raise AssertionError((repeated, sent))
        updated = json.loads(receipts.read_text(encoding="utf-8"))
        if updated["sent"][-1]["key"] != "performance:no_confirmed_picks_streak:2026-06-01:REVIEW_REQUIRED:3":
            raise AssertionError(updated)


def test_missing_telegram_credentials_skip_without_receipt() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "latest.json"
        receipts = root / "no_picks_alerts.json"
        _write_report(checks)

        result = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="",
            chat_id="chat",
            sender=lambda *_args, **_kwargs: True,
        )
        if result["status"] != "missing_credentials":
            raise AssertionError(result)
        if receipts.exists():
            raise AssertionError("missing credentials must not write a receipt")


def test_ignores_unrelated_or_passed_checks() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checks = root / "latest.json"
        receipts = root / "no_picks_alerts.json"
        checks.write_text(json.dumps({
            "as_of_date": "2026-06-08",
            "checks": [{
                "id": "table:performance_ledger:latest_date",
                "status": "WARN",
                "recommended_action": "REVIEW_REQUIRED",
            }, {
                "id": "performance:no_confirmed_picks_streak",
                "status": "PASS",
                "recommended_action": "NO_ACTION",
                "value": 1,
            }],
        }), encoding="utf-8")

        result = mod.notify_from_checks(
            checks_path=checks,
            receipts_path=receipts,
            bot_token="token",
            chat_id="chat",
            sender=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected send")),
        )
        if result["status"] != "no_alert":
            raise AssertionError(result)
        if receipts.exists():
            raise AssertionError("no alert must not write a receipt")


if __name__ == "__main__":
    tests = [
        test_no_picks_warn_sends_once_and_writes_receipt,
        test_no_picks_review_required_has_own_receipt_key,
        test_missing_telegram_credentials_skip_without_receipt,
        test_ignores_unrelated_or_passed_checks,
    ]
    for test in tests:
        test()
    print(f"analytics action notify tests: {len(tests)} passed")
