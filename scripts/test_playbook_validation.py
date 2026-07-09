#!/usr/bin/env python3
"""Self-contained tests for automated playbook validation.

Run:  .venv/bin/python scripts/test_playbook_validation.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_validation_summary_respects_maturity_gate() -> None:
    from scripts import playbook_validation as pv

    decisions = [
        {
            "ticker": "AAA",
            "as_of_date": "2026-01-02",
            "primary_playbook": "Swing Long Call",
            "factor_ids": ["dte_min_21_days"],
            "actionability": "actionable",
        },
        {
            "ticker": "BBB",
            "as_of_date": "2026-01-02",
            "primary_playbook": "Swing Long Call",
            "factor_ids": ["dte_min_21_days"],
            "actionability": "actionable",
        },
    ]
    outcomes = [
        {"ticker": "AAA", "as_of_date": "2026-01-02", "fwd_7d_return": 0.08, "resolved_7d": True},
        {"ticker": "BBB", "as_of_date": "2026-01-02", "fwd_7d_return": -0.03, "resolved_7d": True},
    ]

    summary = pv.summarize(decisions, outcomes, min_resolved=10)

    assert summary["status"] == "accumulating"
    assert summary["resolved"] == 2
    assert summary["min_resolved"] == 10
    assert summary["playbooks"][0]["playbook"] == "Swing Long Call"
    assert summary["playbooks"][0]["verdict"] == "exploratory"


def test_missing_decision_source_writes_blocked_latest() -> None:
    from scripts import playbook_validation as pv

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        out = root / "latest.json"
        summary = pv.run_validation(decisions=root / "missing", output=out, min_resolved=10)

        assert summary["status"] == "blocked", summary
        assert "decision" in summary["reason"].lower(), summary
        assert out.exists(), out


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
