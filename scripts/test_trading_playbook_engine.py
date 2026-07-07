#!/usr/bin/env python3
"""Self-contained tests for the course playbook overlay.

Run:  .venv/bin/python scripts/test_trading_playbook_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from scripts import trading_playbook_engine as pbe  # noqa: E402
except ImportError as exc:  # TDD red: module does not exist yet.
    pbe = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _engine():
    assert pbe is not None, f"missing trading_playbook_engine: {IMPORT_ERROR}"
    return pbe


def _ctx(**overrides) -> dict:
    base = {
        "ticker": "NVDA",
        "cockpit_verdict": "GO",
        "direction_bias": "bullish",
        "trend": "上升",
        "above_vwap": True,
        "breakout": True,
        "cycle": "Cycle1",
        "ce_trend": "bullish",
        "risk_status": "NORMAL",
        "dte": 28,
        "iv_rank": 25.0,
        "iv_percentile": 25.0,
        "iv_rank_source": "iv_history",
        "earnings_within_dte": False,
        "earnings_days_away": 45,
        "contract_payoffable": True,
        "contract_executable": True,
        "contract_spread_pct": 5.0,
        "bollinger_1sd_to_2sd": False,
        "beyond_2sd": False,
        "has_long_holding": False,
        "requested_structure": None,
    }
    base.update(overrides)
    return base


def _ids(items: list[dict]) -> set[str]:
    return {str(item.get("id")) for item in items}


def test_dte_under_21_is_warning_not_block() -> None:
    result = _engine().evaluate_context(_ctx(dte=14))

    assert result["primary_playbook"] == "Swing Long Call", result
    assert result["actionability"] == "actionable", result
    assert "dte_under_21" in _ids(result["warnings"]), result
    assert "dte_under_21" not in _ids(result["blocks"]), result


def test_cockpit_avoid_hard_blocks_to_skip() -> None:
    result = _engine().evaluate_context(_ctx(cockpit_verdict="AVOID"))

    assert result["primary_playbook"] == "Skip / Wait", result
    assert result["actionability"] == "skip", result
    assert "cockpit_avoid" in _ids(result["blocks"]), result


def test_reduce_blocks_new_long_but_allows_existing_holding_hedge() -> None:
    result = _engine().evaluate_context(_ctx(risk_status="REDUCE", has_long_holding=True))

    assert result["primary_playbook"] == "Protective Put / Swing Hedge", result
    assert result["actionability"] == "hedge_only", result
    assert "risk_reduce_exit_new_long" in _ids(result["blocks"]), result


def test_high_iv_prefers_bull_call_spread_not_skip() -> None:
    result = _engine().evaluate_context(_ctx(iv_rank=68.0, iv_percentile=68.0))

    assert result["primary_playbook"] == "Bull Call Spread", result
    assert result["actionability"] == "actionable", result
    assert result["structure"] == "Bull Call Spread", result
    assert "iv_elevated" in _ids(result["warnings"]), result
    assert not result["blocks"], result


def test_jump_requires_bollinger_acceleration_and_falls_back_to_swing() -> None:
    fallback = _engine().evaluate_context(_ctx(bollinger_1sd_to_2sd=False))
    jump = _engine().evaluate_context(_ctx(bollinger_1sd_to_2sd=True, beyond_2sd=False))

    assert fallback["primary_playbook"] == "Swing Long Call", fallback
    assert "jump_signal_missing" in _ids(fallback["warnings"]), fallback
    assert jump["primary_playbook"] == "Jump Trade Long Call", jump
    assert jump["actionability"] == "actionable", jump


def test_missing_cycle_is_warning_not_block_when_cockpit_is_bullish_go() -> None:
    result = _engine().evaluate_context(_ctx(cycle=None))

    assert result["primary_playbook"] == "Swing Long Call", result
    assert "cycle_missing" in _ids(result["warnings"]), result
    assert not result["blocks"], result


def test_unknown_string_flags_are_data_gaps_not_truthy_blocks() -> None:
    result = _engine().evaluate_context(_ctx(earnings_within_dte="unknown"))

    assert result["primary_playbook"] == "Swing Long Call", result
    assert "earnings_unknown" in _ids(result["warnings"]), result
    assert "earnings_within_dte" not in _ids(result["blocks"]), result


def test_naked_call_is_never_recommended() -> None:
    result = _engine().evaluate_context(_ctx(requested_structure="Naked Call"))

    assert result["primary_playbook"] == "Skip / Wait", result
    assert result["actionability"] == "skip", result
    assert "naked_call_prohibited" in _ids(result["blocks"]), result


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
