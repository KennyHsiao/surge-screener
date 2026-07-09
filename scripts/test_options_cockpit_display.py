#!/usr/bin/env python3
"""Self-contained display-state tests for Options Cockpit UI helpers.

Run:  .venv/bin/python scripts/test_options_cockpit_display.py
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with redirect_stderr(io.StringIO()):
    from ui import options_cockpit as oc  # noqa: E402


def _sample_cockpit() -> oc.CockpitData:
    idx = pd.bdate_range("2026-07-01", periods=3)
    chart = pd.DataFrame(
        {
            "Open": [99.0, 100.0, 100.5],
            "High": [101.0, 102.0, 102.5],
            "Low": [98.5, 99.5, 100.0],
            "Close": [100.0, 101.0, 100.0],
            "Volume": [1_000_000, 1_100_000, 1_200_000],
        },
        index=idx,
    )
    return oc.CockpitData(
        ticker="TEST",
        spot=100.0,
        day_change_pct=0.0,
        regime="neutral",
        verdict="WAIT",
        verdict_reasons=[],
        trend="震盪",
        rvol=None,
        above_vwap=True,
        breakout=False,
        resistance_20d=105.0,
        cp_vol_ratio=None,
        put_call_ratio=None,
        atm_iv=0.40,
        iv_rank=25.0,
        iv_percentile=25.0,
        realized_vol=0.30,
        iv_rank_source="iv_history",
        iv_rank_accumulating=False,
        iv_rank_n_days=80,
        earnings_date=None,
        earnings_days_away=None,
        earnings_within_dte=False,
        chart=chart,
        iv_history=pd.DataFrame(columns=["date", "iv"]),
        chain=pd.DataFrame({"strike": [105.0, 115.0], "call_vol": [1000, 800]}),
        contract=oc.Contract(
            strike=105.0,
            expiry="2026-08-01",
            dte=30,
            delta=0.35,
            gamma=0.04,
            theta=-0.05,
            vega=0.08,
            mid_premium=2.0,
            iv=0.40,
            volume=1000,
            open_interest=5000,
            spread_pct=5.0,
            executable=True,
            in_sweet_spot=True,
        ),
        checklist={},
        is_demo=False,
        quote_source="test",
        quote_source_label="來源：test",
    )


def _near(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def test_single_iv_snapshot_uses_marker_and_accumulating_copy() -> None:
    iv_history = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01"]),
        "iv": [0.498],
    })

    state = oc._iv_history_display_state(
        iv_history,
        atm_iv=None,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=1,
        iv_rank_accumulating=True,
        is_demo=False,
    )

    assert state["show_section"] is True, state
    assert state["trace_mode"] == "lines+markers", state
    assert state["current_iv_pct"] == 49.8, state
    assert "快照累積中" in state["caption"], state
    assert "n=1d" in state["caption"], state


def test_missing_iv_history_still_surfaces_current_atm_iv() -> None:
    state = oc._iv_history_display_state(
        pd.DataFrame(columns=["date", "iv"]),
        atm_iv=0.5123,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=0,
        iv_rank_accumulating=True,
        is_demo=False,
    )

    assert state["show_section"] is True, state
    assert state["trace_mode"] is None, state
    assert state["current_iv_pct"] == 51.23, state
    assert "尚無 iv_history 快照" in state["caption"], state


def test_strategy_greeks_are_aggregated_in_contract_units() -> None:
    d = _sample_cockpit()
    legs = [{"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40}]
    state = oc._strategy_greeks(d, legs, 0.40)
    expected = oc._ana.bs_call_greeks(100.0, 105.0, 30 / 365, oc._RISK_FREE, 0.40)

    assert _near(state["net_delta"], expected["delta"]), state
    assert _near(state["delta_shares"], expected["delta"] * 100), state
    assert _near(state["gamma_per_dollar"], expected["gamma"] * 100), state
    assert _near(state["theta_day_dollars"], expected["theta"] * 100), state
    assert _near(state["vega_1iv_dollars"], expected["vega"] * 100), state


def test_bull_call_spread_reduces_greeks_exposure_vs_long_call() -> None:
    d = _sample_cockpit()
    long_call = [{"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40}]
    spread = [
        {"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40},
        {"K": 115.0, "qty": -1, "prem": 0.8, "iv": 0.40},
    ]

    long_state = oc._strategy_greeks(d, long_call, 0.40)
    spread_state = oc._strategy_greeks(d, spread, 0.40)

    assert 0 < spread_state["net_delta"] < long_state["net_delta"], spread_state
    assert abs(spread_state["theta_day_dollars"]) < abs(long_state["theta_day_dollars"]), spread_state
    assert abs(spread_state["vega_1iv_dollars"]) < abs(long_state["vega_1iv_dollars"]), spread_state


def test_payoff_stats_use_exact_strategy_formulas() -> None:
    d = _sample_cockpit()
    long_call = [{"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40}]
    spread = [
        {"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40},
        {"K": 115.0, "qty": -1, "prem": 0.8, "iv": 0.40},
    ]

    long_stats = oc._payoff_stats(d, long_call)
    spread_stats = oc._payoff_stats(d, spread)

    assert long_stats["max_loss"] == -200.0, long_stats
    assert long_stats["max_profit"] is None, long_stats
    assert long_stats["breakeven"] == 107.0, long_stats
    assert spread_stats["net_debit"] == 1.2, spread_stats
    assert spread_stats["max_loss"] == -120.0, spread_stats
    assert spread_stats["max_profit"] == 880.0, spread_stats
    assert spread_stats["breakeven"] == 106.2, spread_stats


def test_payoff_figure_contains_selected_and_expiry_payoff_traces() -> None:
    d = _sample_cockpit()
    legs = [{"K": 105.0, "qty": 1, "prem": 2.0, "iv": 0.40}]

    fig = oc._payoff_fig(d, days_left=15, iv=0.40, legs=legs, breakeven=107.0)
    trace_names = [getattr(trace, "name", "") for trace in fig.data]
    annotations = [getattr(ann, "text", "") for ann in fig.layout.annotations]

    assert "選定天數 P/L" in trace_names, trace_names
    assert "到期 P/L" in trace_names, trace_names
    assert any("現價" in str(text) for text in annotations), annotations
    assert any("損益兩平" in str(text) for text in annotations), annotations


def test_chain_microstructure_summary_identifies_pain_and_walls() -> None:
    d = _sample_cockpit()
    d.chain = pd.DataFrame({
        "strike": [95.0, 100.0, 105.0],
        "call_oi": [50, 100, 300],
        "put_oi": [300, 120, 20],
        "call_vol": [500, 600, 900],
        "put_vol": [800, 400, 100],
    })

    state = oc._chain_microstructure_summary(d)

    assert state["max_pain_strike"] == 100.0, state
    assert state["call_wall_strike"] == 105.0, state
    assert state["put_wall_strike"] == 95.0, state
    assert state["total_call_oi"] == 450, state
    assert state["total_put_oi"] == 440, state
    assert round(state["put_call_oi_ratio"], 2) == 0.98, state
    assert state["near_atm_call_oi"] == 450, state
    assert state["near_atm_put_oi"] == 440, state


def test_playbook_context_uses_cockpit_and_trade_state_without_refetching() -> None:
    d = _sample_cockpit()
    d.verdict = "GO"
    d.trend = "上升"
    d.iv_rank = 65.0
    d.contract.dte = 14

    ctx = oc._playbook_context_from_cockpit(
        d,
        trade_state_row={"cycle": "Cycle1", "ce_trend": "bullish", "risk_status": "NORMAL"},
    )
    decision = oc._evaluate_playbook_overlay(d, trade_state_row={"cycle": "Cycle1", "ce_trend": "bullish"})

    assert ctx["ticker"] == "TEST", ctx
    assert ctx["cockpit_verdict"] == "GO", ctx
    assert ctx["cycle"] == "Cycle1", ctx
    assert ctx["dte"] == 14, ctx
    assert ctx["contract_payoffable"] is True, ctx
    assert ctx["contract_executable"] is True, ctx
    assert isinstance(ctx["bollinger_1sd_to_2sd"], bool), ctx
    assert decision["primary_playbook"] == "Bull Call Spread", decision
    assert "dte_under_21" in {w["id"] for w in decision["warnings"]}, decision


def test_playbook_context_falls_back_to_chart_cycle_when_trade_state_missing() -> None:
    d = _sample_cockpit()
    idx = pd.bdate_range("2026-01-01", periods=80)
    close = [100 + i for i in range(80)]
    d.chart = pd.DataFrame({
        "Open": close,
        "High": [v + 1 for v in close],
        "Low": [v - 1 for v in close],
        "Close": close,
        "Volume": [1_000_000] * 80,
    }, index=idx)

    ctx = oc._playbook_context_from_cockpit(d, trade_state_row=None)

    assert ctx["cycle"] == "Cycle1", ctx
    assert ctx["cycle_source"] == "chart_fallback", ctx


def test_cycle_fallback_keeps_all_six_filter_values_available() -> None:
    assert oc._cycle_filter_options() == ["Cycle1", "Cycle2", "Cycle3", "Cycle4", "Cycle5", "Cycle6"]


def test_holding_detection_reads_reconciliation_buckets() -> None:
    recon = {
        "matched": [],
        "held_not_in_ledger": [
            {"ticker": "NVDA", "legs": [{"secType": "STK", "qty": 10}]},
            {"ticker": "TSLA", "legs": [{"secType": "OPT", "qty": -1}]},
        ],
    }

    assert oc._has_long_holding_for_ticker("NVDA", recon) is True
    assert oc._has_long_holding_for_ticker("TSLA", recon) is False
    assert oc._has_long_holding_for_ticker("AAPL", recon) is False


def test_preferred_structure_follows_playbook_recommendation() -> None:
    spread = {"structure": "Bull Call Spread"}
    long_call = {"structure": "單買 Call"}

    assert oc._preferred_structure_for_playbook(spread) == "牛市買權價差"
    assert oc._preferred_structure_for_playbook(long_call) == "單買 Call"


def test_playbook_compact_items_limit_warning_chips() -> None:
    decision = {
        "primary_playbook": "Swing Long Call",
        "actionability": "actionable",
        "warnings": [
            {"id": "dte_under_21", "label": "DTE < 21", "severity": "warn"},
            {"id": "iv_source_proxy", "label": "IV proxy", "severity": "warn"},
            {"id": "cycle_missing", "label": "Cycle missing", "severity": "warn"},
            {"id": "jump_signal_missing", "label": "Jump missing", "severity": "warn"},
        ],
        "blocks": [],
    }

    chips, overflow = oc._playbook_compact_items(decision, max_warnings=2)

    assert [item[0] for item in chips] == ["Swing Long Call", "可執行", "DTE < 21", "IV proxy"], chips
    assert overflow == 2, overflow


def test_playbook_detail_state_keeps_source_and_factor_details_collapsed() -> None:
    decision = {
        "primary_playbook": "Swing Long Call",
        "actionability": "watch",
        "factor_ids": ["dte_min_21_days", "iv_rank_low_for_long_options"],
        "warnings": [{"id": "jump_signal_missing", "label": "Jump missing"}],
        "blocks": [],
        "course_sources": ["Swing Trade", "風控"],
    }

    state = oc._playbook_detail_state(
        decision,
        cockpit_verdict="WAIT",
        cycle_source="chart_fallback",
    )

    assert state["cockpit_verdict"] == "WAIT", state
    assert state["overlay"] == "Swing Long Call / watch", state
    assert state["cycle_source"] == "chart_fallback", state
    assert state["factor_ids"] == ["dte_min_21_days", "iv_rank_low_for_long_options"], state
    assert state["missing_conditions"] == ["jump_signal_missing"], state


def test_money_flow_signal_formats_publishable_artifact() -> None:
    from ui import options_cockpit as oc
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "rows": [
            {"ticker": "NVDA", "date": "2026-07-03", "main_net": 2_000_000.0, "main_pct": 4.2, "small_net": -500_000.0, "source": "eastmoney_push2his"}
        ],
    }

    signal = oc._money_flow_confirmation_signal("NVDA", artifact)

    if signal["state"] != "positive":
        raise AssertionError(signal)
    if signal["label"] != "主力流入確認":
        raise AssertionError(signal)
    if signal["source"] != "eastmoney_push2his":
        raise AssertionError(signal)


def test_money_flow_signal_fails_closed_when_stale() -> None:
    from ui import options_cockpit as oc
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-10",
        "rows": [
            {"ticker": "NVDA", "date": "2026-07-03", "main_net": 2_000_000.0, "main_pct": 4.2, "small_net": -500_000.0}
        ],
    }

    signal = oc._money_flow_confirmation_signal("NVDA", artifact)

    if signal["state"] != "unknown":
        raise AssertionError(signal)
    if "過期" not in signal["label"]:
        raise AssertionError(signal)


def test_money_flow_signal_ignores_future_only_rows() -> None:
    from ui import options_cockpit as oc
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "NVDA", "date": "2026-07-04", "main_net": 2_000_000.0, "main_pct": 4.2, "small_net": -500_000.0}
        ],
    }

    signal = oc._money_flow_confirmation_signal("NVDA", artifact)

    if signal["state"] != "unknown":
        raise AssertionError(signal)
    if signal["label"] != "無個股資金流":
        raise AssertionError(signal)


def test_insider_confirmation_signal_formats_edgar_net_buy() -> None:
    from ui import options_cockpit as oc

    signal = oc._insider_confirmation_signal({
        "ticker": "NVDA",
        "net_usd": 1_250_000.0,
        "n_buy": 3,
        "n_sell": 1,
        "n_txn": 4,
        "window_days": 30,
        "as_of": "2026-07-03",
    })

    if signal["state"] != "positive":
        raise AssertionError(signal)
    if "$1.25M" not in signal["value"]:
        raise AssertionError(signal)
    if signal["label"] != "內部人淨買":
        raise AssertionError(signal)


def test_social_quickpick_label_surfaces_free_first_badges() -> None:
    from ui import options_cockpit as oc

    label = oc._social_quickpick_label({
        "ticker": "NVDA",
        "mentioned_by": ["alpha", "beta"],
        "labels": {
            "x_mentioned": True,
            "agent_reach": True,
            "retail_heat": True,
            "crowded": True,
            "early_signal": True,
            "paid_data_needed": True,
        },
    })

    for needle in [
        "X Mentioned",
        "Agent Reach",
        "Retail Heat",
        "Crowded",
        "Early Signal",
        "Paid Data Needed",
    ]:
        if needle not in label:
            raise AssertionError(label)


def main() -> None:
    tests = [
        test_single_iv_snapshot_uses_marker_and_accumulating_copy,
        test_missing_iv_history_still_surfaces_current_atm_iv,
        test_strategy_greeks_are_aggregated_in_contract_units,
        test_bull_call_spread_reduces_greeks_exposure_vs_long_call,
        test_payoff_stats_use_exact_strategy_formulas,
        test_payoff_figure_contains_selected_and_expiry_payoff_traces,
        test_chain_microstructure_summary_identifies_pain_and_walls,
        test_playbook_context_uses_cockpit_and_trade_state_without_refetching,
        test_playbook_context_falls_back_to_chart_cycle_when_trade_state_missing,
        test_cycle_fallback_keeps_all_six_filter_values_available,
        test_holding_detection_reads_reconciliation_buckets,
        test_preferred_structure_follows_playbook_recommendation,
        test_playbook_compact_items_limit_warning_chips,
        test_playbook_detail_state_keeps_source_and_factor_details_collapsed,
        test_money_flow_signal_formats_publishable_artifact,
        test_money_flow_signal_fails_closed_when_stale,
        test_money_flow_signal_ignores_future_only_rows,
        test_insider_confirmation_signal_formats_edgar_net_buy,
        test_social_quickpick_label_surfaces_free_first_badges,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failures:
        raise SystemExit(1)
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
