#!/usr/bin/env python3
"""Self-contained tests for playbook decision ledger rows.

Run:  .venv/bin/python scripts/test_playbook_decision_log.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_decision_log_row_is_stable_and_minimal() -> None:
    from scripts import playbook_decision_log as log

    row = log.decision_row(
        context={
            "ticker": "NVDA",
            "cockpit_verdict": "WAIT",
            "cycle": "Cycle1",
            "cycle_source": "chart_fallback",
            "dte": 30,
            "iv_rank": 25.0,
        },
        decision={
            "primary_playbook": "Swing Long Call",
            "actionability": "watch",
            "structure": "單買 Call",
            "warnings": [{"id": "jump_signal_missing"}],
            "blocks": [],
            "course_sources": ["Swing Trade"],
        },
    )

    assert row == {
        "ticker": "NVDA",
        "cockpit_verdict": "WAIT",
        "primary_playbook": "Swing Long Call",
        "actionability": "watch",
        "structure": "單買 Call",
        "cycle": "Cycle1",
        "cycle_source": "chart_fallback",
        "dte": 30,
        "iv_rank": 25.0,
        "warning_ids": ["jump_signal_missing"],
        "block_ids": [],
        "course_sources": ["Swing Trade"],
    }


def test_decision_log_preserves_validation_fields_when_available() -> None:
    from scripts import playbook_decision_log as log

    row = log.decision_row(
        context={
            "ticker": "NVDA",
            "as_of_date": "2026-07-09",
            "cockpit_verdict": "GO",
            "cycle": "Cycle1",
            "cycle_source": "trade_state",
            "dte": 30,
            "iv_rank": 25.0,
        },
        decision={
            "primary_playbook": "Swing Long Call",
            "actionability": "actionable",
            "structure": "單買 Call",
            "warnings": [],
            "blocks": [],
            "course_sources": ["Swing Trade"],
            "factor_ids": ["dte_min_21_days", "iv_rank_low_for_long_options"],
        },
    )

    assert row["as_of_date"] == "2026-07-09", row
    assert row["factor_ids"] == ["dte_min_21_days", "iv_rank_low_for_long_options"], row


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
