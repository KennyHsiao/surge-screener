#!/usr/bin/env python3
"""Focused contracts for Phase 5C Schedules Crypto Universe adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import CryptoUniverseData, ScheduleEntry  # noqa: E402
from ui import _components, _read_api, sys_schedules  # noqa: E402


def _snapshot(*, populated: bool = True) -> CryptoUniverseData:
    universe = (
        [
            {
                "symbol": "BTCUSDT",
                "base": "BTC",
                "tv_symbol": "BINANCE:BTCUSDT.P",
                "onboard_date": "2019-09-25",
            }
        ]
        if populated
        else []
    )
    return CryptoUniverseData.model_validate(
        {
            "date": "2026-08-03",
            "source": "binance_fapi_exchangeInfo",
            "source_status": "live",
            "stale": False,
            "stale_source_date": None,
            "count": len(universe),
            "universe": universe,
            "added": ["BTCUSDT"] if populated else [],
            "removed": ["ETHUSDT"] if populated else [],
            "compared_to": "2026-08-02" if populated else None,
        },
        strict=True,
    )


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"幣種清單 {identifier}",
            "category": "幣圈",
            "cron": "30 0 * * *",
            "cron_note": "每天",
            "description": "Binance USDT 永續清單",
            "result_type": "crypto_universe",
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_and_available_empty_are_authoritative() -> None:
    available = _read_api.CryptoUniverseApiAvailable(_snapshot())
    with patch(
        "ui.sys_schedules._read_api.load_crypto_universe",
        return_value=available,
    ) as loader:
        content, reason = sys_schedules._latest_crypto_result()
    if loader.call_count != 1 or reason is not None or content is None:
        raise AssertionError((loader.call_count, content, reason))
    for expected in ("USDT 永續:**1** 檔", "2026-08-03", "➕1 / ➖1", "對比 2026-08-02"):
        if expected not in content:
            raise AssertionError(content)

    empty = _read_api.CryptoUniverseApiAvailable(_snapshot(populated=False))
    with patch("ui.sys_schedules._read_api.load_crypto_universe", return_value=empty):
        content, reason = sys_schedules._latest_crypto_result()
    if reason is not None or content is None:
        raise AssertionError((content, reason))
    for expected in ("USDT 永續:**0** 檔", "➕0 / ➖0", "對比 無"):
        if expected not in content:
            raise AssertionError(content)


def test_unavailable_failures_and_unexpected_results_are_safe() -> None:
    outcomes: tuple[object, ...] = (
        *(
            _read_api.CryptoUniverseApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.CryptoUniverseApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
        object(),
    )
    for outcome in outcomes:
        with patch("ui.sys_schedules._read_api.load_crypto_universe", return_value=outcome):
            content, reason = sys_schedules._latest_crypto_result()
        if content is None:
            raise AssertionError((outcome, content, reason))
        if isinstance(outcome, _read_api.CryptoUniverseApiUnavailable):
            expected, expected_reason = "幣種清單資料目前無法使用", outcome.reason
        elif isinstance(outcome, _read_api.CryptoUniverseApiFailure):
            expected, expected_reason = "幣種清單服務目前無法使用", outcome.reason
        else:
            expected, expected_reason = "幣種清單服務目前無法使用", "invalid_envelope"
        if expected not in content or reason != expected_reason:
            raise AssertionError((outcome, content, reason))
        if expected_reason in content:
            raise AssertionError(content)


def test_duplicate_visible_cards_reuse_one_crypto_result() -> None:
    state = sys_schedules.ScheduleRegistryState(
        "api_available",
        (_schedule("crypto_a"), _schedule("crypto_b")),
        None,
    )
    outcome = _read_api.CryptoUniverseApiAvailable(_snapshot())
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch(
            "ui.sys_schedules._read_api.load_crypto_universe",
            return_value=outcome,
        ) as loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if loader.call_count != 1:
        raise AssertionError(f"Crypto Universe request count: {loader.call_count}")
    if _app_text(app).count("USDT 永續:**1** 檔") != 2:
        raise AssertionError(_app_text(app))


def test_source_has_one_fixed_client_no_local_fallback_and_python310_ast() -> None:
    path = ROOT / "ui" / "sys_schedules.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    result = functions["_latest_crypto_result"]
    if result.count("load_crypto_universe()") != 1:
        raise AssertionError("Schedules must load one fixed Crypto Universe snapshot")
    for forbidden in (
        'REPORTS_DIR / "crypto" / "universe_latest.json"',
        "_shared.load_json",
    ):
        if forbidden in result:
            raise AssertionError(f"Schedules retained Crypto fallback: {forbidden}")
    render = functions["render"]
    if '"crypto_universe"' not in render or "result_cache" not in render:
        raise AssertionError("Schedules does not reuse Crypto results by result type")


def main() -> None:
    tests = (
        test_available_and_available_empty_are_authoritative,
        test_unavailable_failures_and_unexpected_results_are_safe,
        test_duplicate_visible_cards_reuse_one_crypto_result,
        test_source_has_one_fixed_client_no_local_fallback_and_python310_ast,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
