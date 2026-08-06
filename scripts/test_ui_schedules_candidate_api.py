#!/usr/bin/env python3
"""Focused contracts for Phase 4G Schedules candidate-refresh adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import MoneyFlowData, RankedCandidatesFeedData, ScheduleEntry  # noqa: E402
from ui import _components, _read_api, sys_schedules  # noqa: E402


def _feed(*tickers: str) -> RankedCandidatesFeedData:
    return RankedCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-01",
            "generated_at": "2026-08-01T02:03:04+00:00",
            "candidates": [
                {
                    "ticker": ticker,
                    "rank_score": 90.0 - index,
                    "last_price": 100.0,
                    "rank_bucket": "priority",
                    "ret_5d": 3.0,
                    "ret_20d": 8.0,
                    "score_components": {
                        "technical_trend": 20.0,
                        "momentum_strength": 18.0,
                        "launch_signal": 17.0,
                        "liquidity_tradability": 19.0,
                        "overheat_risk_control": 16.0,
                    },
                    "options_tradability": None,
                    "warnings": [],
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
    )


def _money_flow(*, publishable: bool = True) -> MoneyFlowData:
    rows = (
        [
            {
                "ticker": "NVDA",
                "date": "2026-08-01",
                "main_net": 1_000_000.0,
                "main_pct": 2.0,
                "small_net": -500_000.0,
                "source": "eastmoney_push2his",
            }
        ]
        if publishable
        else []
    )
    return MoneyFlowData.model_validate(
        {
            "as_of_date": "2026-08-01",
            "generated_at": "2026-08-01T02:03:04+00:00",
            "source": "eastmoney_push2his",
            "publishable": publishable,
            "coverage": {
                "requested": 1 if publishable else 0,
                "resolved": 1 if publishable else 0,
                "unavailable": 0,
                "coverage_ratio": 1.0 if publishable else 0.0,
                "min_coverage": 0.7,
            },
            "rows": rows,
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"候選刷新 {identifier}",
            "category": "系統",
            "cron": "0 1 * * *",
            "cron_note": "每天",
            "description": "候選排名與資金流摘要",
            "result_type": "candidate_refresh",
        },
        strict=True,
    )


def test_available_and_available_empty_are_authoritative() -> None:
    available = _read_api.RankedCandidatesApiAvailable(_feed("NVDA", "AMD"))
    with (
        patch("ui.sys_schedules._read_api.load_ranked_candidates", return_value=available),
        patch(
            "ui.sys_schedules._read_api.load_money_flow",
            return_value=_read_api.MoneyFlowApiAvailable(_money_flow()),
        ),
    ):
        content, reason = sys_schedules._latest_candidate_refresh_result()
    if reason is not None or content is None:
        raise AssertionError((content, reason))
    for expected in ("排名 **2** 檔", "前 5:NVDA, AMD", "資金流:可發布"):
        if expected not in content:
            raise AssertionError(content)

    empty = _read_api.RankedCandidatesApiAvailable(_feed())
    with (
        patch("ui.sys_schedules._read_api.load_ranked_candidates", return_value=empty),
        patch(
            "ui.sys_schedules._read_api.load_money_flow",
            return_value=_read_api.MoneyFlowApiAvailable(_money_flow(publishable=False)),
        ),
    ):
        content, reason = sys_schedules._latest_candidate_refresh_result()
    if content is None or reason is not None or "未達門檻" not in content:
        raise AssertionError((content, reason))


def test_unavailable_and_failures_preserve_money_flow_partial_output() -> None:
    outcomes: tuple[_read_api.RankedCandidatesApiResult, ...] = (
        *(
            _read_api.RankedCandidatesApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.RankedCandidatesApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with (
            patch(
                "ui.sys_schedules._read_api.load_ranked_candidates",
                return_value=outcome,
            ),
            patch(
                "ui.sys_schedules._read_api.load_money_flow",
                return_value=_read_api.MoneyFlowApiAvailable(_money_flow()),
            ),
        ):
            content, reason = sys_schedules._latest_candidate_refresh_result()
        if reason != outcome.reason:
            raise AssertionError((outcome, reason))
        if content is None or "資金流:可發布" not in content:
            raise AssertionError((outcome, content))
        if "排名 **0**" in content:
            raise AssertionError("a failed ranked request was rendered as valid empty")


def test_money_flow_unavailable_and_failures_preserve_ranked_partial_output() -> None:
    ranked = _read_api.RankedCandidatesApiAvailable(_feed("NVDA", "AMD"))
    outcomes: tuple[_read_api.MoneyFlowApiResult, ...] = (
        *(
            _read_api.MoneyFlowApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.MoneyFlowApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with (
            patch(
                "ui.sys_schedules._read_api.load_ranked_candidates",
                return_value=ranked,
            ),
            patch("ui.sys_schedules._read_api.load_money_flow", return_value=outcome),
        ):
            content, reason = sys_schedules._latest_candidate_refresh_result()
        if reason != outcome.reason or content is None:
            raise AssertionError((outcome, content, reason))
        if "排名 **2** 檔" not in content or "前 5:NVDA, AMD" not in content:
            raise AssertionError((outcome, content))
        expected = (
            "資金流:資料目前無法使用"
            if isinstance(outcome, _read_api.MoneyFlowApiUnavailable)
            else "資金流:服務目前無法使用"
        )
        if expected not in content or outcome.reason in content:
            raise AssertionError((outcome, content))


def test_duplicate_visible_cards_reuse_one_ranked_result_and_render_partial_state() -> None:
    state = sys_schedules.ScheduleRegistryState(
        "api_available",
        (_schedule("candidate_a"), _schedule("candidate_b")),
        None,
    )
    outcome = _read_api.RankedCandidatesApiFailure("transport_error")
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch(
            "ui.sys_schedules._read_api.load_ranked_candidates",
            return_value=outcome,
        ) as ranked_loader,
        patch(
            "ui.sys_schedules._read_api.load_money_flow",
            return_value=_read_api.MoneyFlowApiAvailable(_money_flow()),
        ) as money_loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if ranked_loader.call_count != 1:
        raise AssertionError(f"ranked request count: {ranked_loader.call_count}")
    if money_loader.call_count != 1:
        raise AssertionError(f"Money Flow request count: {money_loader.call_count}")
    rendered = _app_text(app)
    if "連線暫時失敗" not in rendered or rendered.count("資金流:可發布") != 2:
        raise AssertionError(rendered)


def test_source_has_no_local_ranked_fallback_and_is_python310_compatible() -> None:
    path = ROOT / "ui" / "sys_schedules.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_latest_candidate_refresh_result"
    )
    segment = ast.get_source_segment(source, function) or ""
    if 'candidate_output_path("ranked_candidates.json")' in segment:
        raise AssertionError("Schedules candidate summary retained local ranked fallback")
    if segment.count("load_ranked_candidates()") != 1:
        raise AssertionError("Schedules candidate summary must load one fixed ranked feed")
    if 'REPORTS_DIR / "money_flow" / "latest.json"' in segment:
        raise AssertionError("Schedules candidate summary retained local Money Flow read")
    if segment.count("load_money_flow()") != 1:
        raise AssertionError("Schedules candidate summary must load one fixed Money Flow feed")


def main() -> None:
    tests = (
        test_available_and_available_empty_are_authoritative,
        test_unavailable_and_failures_preserve_money_flow_partial_output,
        test_money_flow_unavailable_and_failures_preserve_ranked_partial_output,
        test_duplicate_visible_cards_reuse_one_ranked_result_and_render_partial_state,
        test_source_has_no_local_ranked_fallback_and_is_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
