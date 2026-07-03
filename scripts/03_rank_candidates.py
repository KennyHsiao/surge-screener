#!/usr/bin/env python3
"""Stage 2 — Deterministic candidate ranking.

Ranks hard-filtered candidates without LLM calls. Optional options-gate checks can
be applied to the top pool when a user wants chain tradability signals.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from run_status import RunStatus
except ImportError:
    from scripts.run_status import RunStatus


SCORING_MODEL = "deterministic_rank_v1"
REQUIRED_FIELDS = [
    "ticker",
    "last_price",
    "ma50",
    "ma200",
    "ret_5d",
    "ret_20d",
    "avg_dollar_vol_20d",
    "market_cap",
    "macd_current",
    "macd_zero_cross_10d",
    "macd_golden_cross_10d",
    "rsi_bullish_divergence",
    "has_reversal_pattern",
]
MONEY_FLOW_GAP_LABEL = "資金流資料缺口，不加分"
MONEY_FLOW_STALE_DAYS = 3
SCORE_WEIGHTS = {
    "technical_trend": 23,
    "momentum_strength": 18,
    "launch_signal": 17,
    "liquidity_tradability": 17,
    "overheat_risk_control": 15,
    "large_order_flow_confirmation": 10,
}


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        value = float(value)
        if value != value:
            return None
        return value
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    return bool(value)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _linear(value: float, lo: float, hi: float, max_points: float) -> float:
    if hi <= lo:
        return 0.0
    return _clamp((value - lo) / (hi - lo), 0.0, 1.0) * max_points


def _date_ord(value: Any) -> int | None:
    try:
        text = str(value or "")[:10]
        if len(text) != 10:
            return None
        return datetime.fromisoformat(text).date().toordinal()
    except Exception:
        return None


def _scale_component(raw: float, raw_max: float, target_max: float) -> float:
    if raw_max <= 0:
        return 0.0
    return round(_clamp(raw, 0.0, raw_max) / raw_max * target_max, 1)


def _latest_rows_for_ticker(rows: list[dict[str, Any]], ticker: str, window: int = 5) -> list[dict[str, Any]]:
    sym = str(ticker or "").upper().lstrip("$")
    matched = [
        row for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").upper().lstrip("$") == sym
    ]
    dated = [(row, _date_ord(row.get("date") or row.get("flow_date"))) for row in matched]
    dated = [(row, ord_value) for row, ord_value in dated if ord_value is not None]
    dated.sort(key=lambda item: item[1], reverse=True)
    return [row for row, _ in dated[:window]]


def build_money_flow_rank_context(artifact: dict[str, Any] | None, *, as_of_date: str | None = None) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {"publishable": False, "source": "proxy", "by_ticker": {}}
    publishable = bool(artifact.get("publishable"))
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    source = str(artifact.get("source") or "eastmoney_push2his")
    as_of_ord = _date_ord(as_of_date)
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("ticker") or "").upper().lstrip("$")
        if not sym:
            continue
        by_ticker.setdefault(sym, []).append(row)
    return {
        "publishable": publishable,
        "source": source,
        "as_of_ord": as_of_ord,
        "by_ticker": by_ticker,
    }


def _money_flow_evidence(row: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper().lstrip("$")
    context = context if isinstance(context, dict) else {}
    publishable = bool(context.get("publishable"))
    by_ticker = context.get("by_ticker") if isinstance(context.get("by_ticker"), dict) else {}
    rows = by_ticker.get(ticker, []) if isinstance(by_ticker, dict) else []
    latest_rows = _latest_rows_for_ticker(rows, ticker, 5)
    if not publishable or not latest_rows:
        return {
            "publishable": False,
            "source": "proxy",
            "date": None,
            "main_net_5d": None,
            "main_pct_latest": None,
            "small_net_latest": None,
            "label": MONEY_FLOW_GAP_LABEL,
        }

    latest = latest_rows[0]
    latest_ord = _date_ord(latest.get("date") or latest.get("flow_date"))
    as_of_ord = context.get("as_of_ord")
    stale = bool(as_of_ord and latest_ord and as_of_ord - latest_ord > MONEY_FLOW_STALE_DAYS)
    main_net_5d = sum(
        _num(item.get("main_net")) or 0.0
        for item in latest_rows
        if _num(item.get("main_net")) is not None
    )
    main_pct_latest = _num(latest.get("main_pct"))
    small_net_latest = _num(latest.get("small_net"))
    if stale:
        label = "資金流過期，不加分"
    elif main_net_5d > 0:
        label = "主力流入確認"
    elif small_net_latest is not None and small_net_latest > 0 and main_net_5d < 0:
        label = "散戶追價、主力流出"
    elif main_net_5d < 0:
        label = "主力流出"
    else:
        label = "資金流中性"
    return {
        "publishable": True,
        "source": context.get("source") or latest.get("source") or "eastmoney_push2his",
        "date": latest.get("date") or latest.get("flow_date"),
        "stale": stale,
        "main_net_5d": round(main_net_5d, 2),
        "main_pct_latest": main_pct_latest,
        "small_net_latest": small_net_latest,
        "label": label,
    }


def _score_large_order_flow(row: dict[str, Any], evidence: dict[str, Any]) -> float:
    if not evidence.get("publishable") or evidence.get("stale"):
        return 0.0
    adv = _num(row.get("avg_dollar_vol_20d")) or 0.0
    main_net_5d = _num(evidence.get("main_net_5d")) or 0.0
    main_pct_latest = _num(evidence.get("main_pct_latest")) or 0.0
    if adv <= 0 or main_net_5d <= 0:
        return 0.0
    ratio = main_net_5d / adv
    score = _linear(ratio, 0.0, 0.25, 7.0)
    if main_pct_latest > 0:
        score += _linear(main_pct_latest, 0.0, 5.0, 3.0)
    return _clamp(score, 0.0, SCORE_WEIGHTS["large_order_flow_confirmation"])


def _score_trend(row: dict[str, Any]) -> float:
    price = _num(row.get("last_price"))
    ma50 = _num(row.get("ma50"))
    ma200 = _num(row.get("ma200"))
    score = 0.0

    if price is not None and ma50 is not None and price > ma50:
        score += 8
    if price is not None and ma200 is not None and price > ma200:
        score += 8
    if ma50 is not None and ma200 is not None and ma50 > ma200:
        score += 5
    if price is not None and ma50:
        dist = (price / ma50 - 1) * 100
        if -3 <= dist <= 15:
            score += 4
        elif 15 < dist <= 25:
            score += 2
        elif -8 <= dist < -3:
            score += 1

    return _clamp(score, 0, 25)


def _score_momentum(row: dict[str, Any]) -> float:
    ret5 = _num(row.get("ret_5d")) or 0.0
    ret20 = _num(row.get("ret_20d")) or 0.0
    score = 0.0

    if ret20 <= 0:
        score += _linear(ret20, -10, 0, 2)
    elif ret20 <= 20:
        score += _linear(ret20, 0, 20, 10)
    elif ret20 <= 35:
        score += 10 - _linear(ret20, 20, 35, 4)
    else:
        score += 4

    if ret5 <= 0:
        score += _linear(ret5, -5, 0, 1.5)
    elif ret5 <= 8:
        score += _linear(ret5, 0, 8, 6)
    elif ret5 <= 15:
        score += 6 - _linear(ret5, 8, 15, 2)
    else:
        score += 2

    if ret5 > 0 and ret20 > 0:
        if ret5 <= ret20:
            score += 4
        else:
            score += 2

    return _clamp(score, 0, 20)


def _score_launch(row: dict[str, Any]) -> float:
    score = 0.0
    if _bool(row.get("macd_zero_cross_10d")):
        score += 7
    if _bool(row.get("macd_golden_cross_10d")):
        score += 6
    if _bool(row.get("rsi_bullish_divergence")):
        score += 4
    if _bool(row.get("has_reversal_pattern")):
        score += 3
    return _clamp(score, 0, 20)


def _score_liquidity(row: dict[str, Any]) -> float:
    dollar_vol = _num(row.get("avg_dollar_vol_20d")) or 0.0
    market_cap = _num(row.get("market_cap")) or 0.0
    score = 0.0

    if dollar_vol >= 100_000_000:
        score += 12
    elif dollar_vol >= 20_000_000:
        score += 8
    elif dollar_vol >= 5_000_000:
        score += 4

    if market_cap >= 10_000_000_000:
        score += 8
    elif market_cap >= 1_000_000_000:
        score += 5
    elif market_cap >= 300_000_000:
        score += 2

    return _clamp(score, 0, 20)


def _score_overheat_control(row: dict[str, Any]) -> float:
    ret5 = _num(row.get("ret_5d")) or 0.0
    ret20 = _num(row.get("ret_20d")) or 0.0
    price = _num(row.get("last_price"))
    ma50 = _num(row.get("ma50"))
    score = 15.0

    if ret5 > 30:
        score -= 12
    elif ret5 > 20:
        score -= 7
    elif ret5 > 10:
        score -= 3

    if ret20 > 60:
        score -= 12
    elif ret20 > 40:
        score -= 7
    elif ret20 > 25:
        score -= 3

    if price is not None and ma50:
        dist = (price / ma50 - 1) * 100
        if dist > 25:
            score -= 5
        elif dist > 15:
            score -= 2
        elif dist < -10:
            score -= 1

    if _bool(row.get("gap_down_8pct_5d")):
        score -= 5

    return _clamp(score, 0, 15)


def _rank_bucket(score: float) -> str:
    if score >= 75:
        return "priority"
    if score >= 65:
        return "candidate"
    if score >= 50:
        return "watch"
    return "low_priority"


def _data_quality(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if row.get(field) is None]
    return {
        "status": "complete" if not missing else "partial",
        "missing_fields": missing,
    }


def rank_candidate(
    row: dict[str, Any],
    *,
    as_of_date: str | None = None,
    money_flow_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a ranked row with deterministic score components."""
    money_flow = _money_flow_evidence(row, money_flow_context)
    components = {
        "technical_trend": _scale_component(_score_trend(row), 25, SCORE_WEIGHTS["technical_trend"]),
        "momentum_strength": _scale_component(_score_momentum(row), 20, SCORE_WEIGHTS["momentum_strength"]),
        "launch_signal": _scale_component(_score_launch(row), 20, SCORE_WEIGHTS["launch_signal"]),
        "liquidity_tradability": _scale_component(_score_liquidity(row), 20, SCORE_WEIGHTS["liquidity_tradability"]),
        "overheat_risk_control": _scale_component(_score_overheat_control(row), 15, SCORE_WEIGHTS["overheat_risk_control"]),
        "large_order_flow_confirmation": round(_score_large_order_flow(row, money_flow), 1),
    }
    rank_score = round(sum(components.values()), 1)
    quality = _data_quality(row)
    warnings = []
    if quality["missing_fields"]:
        warnings.append("missing hard-filter fields: " + ", ".join(quality["missing_fields"]))

    ranked = dict(row)
    ranked.update({
        "ticker": str(row.get("ticker", "")).upper(),
        "rank_score": rank_score,
        "rank_bucket": _rank_bucket(rank_score),
        "score_components": components,
        "money_flow_evidence": money_flow,
        "data_quality": quality,
        "warnings": warnings,
        "as_of_date": as_of_date or _utc_date(),
    })
    return ranked


def _default_momentum_analyzer(ticker: str) -> dict[str, Any]:
    try:
        try:
            from momentum_options import analyze
        except ImportError:
            from scripts.momentum_options import analyze
        return analyze(ticker)
    except Exception as e:  # noqa: BLE001 - options gate is advisory
        return {"available": False, "reason": str(e), "ticker": ticker}


def _default_flow_analyzer(ticker: str) -> dict[str, Any]:
    try:
        try:
            from options_free import analyze_options
        except ImportError:
            from scripts.options_free import analyze_options
        return analyze_options(ticker)
    except Exception as e:  # noqa: BLE001 - options flow is advisory
        return {"available": False, "reason": str(e), "ticker": ticker}


def classify_options_tradability(momentum: dict[str, Any],
                                 flow: dict[str, Any]) -> dict[str, Any]:
    """Summarize free-data options tradability into usable/watch/unusable/unknown."""
    momentum = momentum if isinstance(momentum, dict) else {}
    flow = flow if isinstance(flow, dict) else {}
    contract = ((momentum.get("options") or {}).get("suggested_contract") or {})
    iv = momentum.get("iv") or {}
    earnings = momentum.get("earnings") or {}
    details_6a = (flow.get("details") or {}).get("6a") or {}

    spread = _num(contract.get("spread_pct"))
    oi = int(_num(contract.get("open_interest")) or 0)
    volume = int(_num(contract.get("volume")) or 0)
    iv_percentile = _num(iv.get("iv_percentile"))
    iv_real = bool(iv.get("iv_percentile_real"))
    earnings_status = earnings.get("status")
    executable = bool(contract.get("executable"))
    liquid = bool(contract.get("liquid"))
    data_missing = list(flow.get("data_missing") or [])
    warnings = []

    if not momentum.get("available"):
        warnings.append(momentum.get("reason") or "momentum options data unavailable")
    if not flow.get("available"):
        warnings.append(flow.get("reason") or "options flow data unavailable")
    if not iv_real:
        warnings.append("IV percentile is proxy or unavailable")
    if earnings_status in (None, "unknown"):
        warnings.append("earnings date unknown")
    if not executable:
        warnings.append("no executable two-sided options quote")

    if not momentum.get("available") and not flow.get("available"):
        status = "unknown"
    elif earnings_status == "within_dte":
        status = "unusable"
    elif iv_real and iv_percentile is not None and iv_percentile >= 80:
        status = "unusable"
    elif momentum.get("verdict") == "AVOID":
        status = "unusable"
    elif executable and liquid and spread is not None and spread <= 12 and (
        iv_real and iv_percentile is not None and iv_percentile < 80
    ):
        status = "usable"
    else:
        status = "watch"

    if flow.get("available"):
        data_missing.extend(["sweeps", "blocks", "dark_pool", "bid_ask_side"])
    data_missing = sorted(set(data_missing))

    return {
        "status": status,
        "momentum_verdict": momentum.get("verdict"),
        "spread_pct": spread,
        "open_interest": oi,
        "volume": volume,
        "iv_percentile": iv_percentile,
        "iv_percentile_real": iv_real,
        "earnings_status": earnings_status,
        "earnings_days_away": earnings.get("days_away"),
        "max_call_voi": _num(details_6a.get("max_call_voi")),
        "call_put_volume_ratio": _num(details_6a.get("call_put_volume_ratio")),
        "total_call_volume": int(_num(details_6a.get("total_call_volume")) or 0),
        "total_put_volume": int(_num(details_6a.get("total_put_volume")) or 0),
        "flow_score": flow.get("total_score"),
        "data_missing": data_missing,
        "warnings": warnings,
    }


def apply_options_gate(
    ranked: list[dict[str, Any]],
    *,
    limit: int,
    momentum_analyzer: Callable[[str], dict[str, Any]] | None = None,
    flow_analyzer: Callable[[str], dict[str, Any]] | None = None,
    status: RunStatus | None = None,
) -> dict[str, int | bool]:
    """Apply options tradability checks to the first N ranked rows in-place."""
    gate_limit = max(0, int(limit or 0))
    if gate_limit <= 0:
        return {
            "enabled": False,
            "requested": 0,
            "checked": 0,
            "usable": 0,
            "watch": 0,
            "unusable": 0,
            "unknown": 0,
        }

    momentum_analyzer = momentum_analyzer or _default_momentum_analyzer
    flow_analyzer = flow_analyzer or _default_flow_analyzer
    checked_rows = ranked[:gate_limit]
    counts = {"usable": 0, "watch": 0, "unusable": 0, "unknown": 0}

    for idx, row in enumerate(checked_rows, start=1):
        ticker = row["ticker"]
        if status:
            status.update_stage(
                "options_gate",
                "檢查 options 可交易性",
                progress_pct=(idx - 1) / max(len(checked_rows), 1) * 100,
                message=f"Checking options gate {idx}/{len(checked_rows)}: {ticker}",
                metrics={
                    "options_gate_requested": gate_limit,
                    "options_gate_checked": idx - 1,
                },
            )
        gate = classify_options_tradability(momentum_analyzer(ticker), flow_analyzer(ticker))
        row["options_tradability"] = gate
        counts[gate["status"]] = counts.get(gate["status"], 0) + 1

    if status:
        status.update_stage(
            "options_gate",
            "檢查 options 可交易性",
            status="succeeded",
            progress_pct=100,
            message=f"Checked options gate for {len(checked_rows)} candidates",
            metrics={
                "options_gate_requested": gate_limit,
                "options_gate_checked": len(checked_rows),
                "options_usable": counts["usable"],
                "options_watch": counts["watch"],
                "options_unusable": counts["unusable"],
                "options_unknown": counts["unknown"],
            },
        )

    return {
        "enabled": True,
        "requested": gate_limit,
        "checked": len(checked_rows),
        **counts,
    }


def _sort_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    dollar_vol = _num(row.get("avg_dollar_vol_20d")) or 0.0
    overheat = _num((row.get("score_components") or {}).get("overheat_risk_control")) or 0.0
    return (-float(row.get("rank_score") or 0), -dollar_vol, -overheat, row.get("ticker", ""))


def build_ranked_output(
    universe: dict[str, Any],
    *,
    limit: int | None = None,
    options_gate_limit: int = 0,
    momentum_analyzer: Callable[[str], dict[str, Any]] | None = None,
    flow_analyzer: Callable[[str], dict[str, Any]] | None = None,
    money_flow_artifact: dict[str, Any] | None = None,
    money_flow_enabled: bool = True,
    status: RunStatus | None = None,
) -> dict[str, Any]:
    as_of_date = universe.get("scan_date") or _utc_date()
    candidates = [c for c in universe.get("tickers", []) or [] if isinstance(c, dict)]
    money_flow_context = build_money_flow_rank_context(money_flow_artifact, as_of_date=as_of_date) if money_flow_enabled else None
    ranked = [
        rank_candidate(c, as_of_date=as_of_date, money_flow_context=money_flow_context)
        for c in candidates
    ]
    ranked.sort(key=_sort_key)
    out_limit = int(limit) if limit else len(ranked)
    limited = ranked[:max(0, out_limit)]

    if status:
        status.update_stage(
            "rank_candidates",
            "程式排序候選",
            progress_pct=100,
            status="succeeded",
            message=f"Ranked {len(ranked)} candidates; output top {len(limited)}",
            metrics={
                "ranked_candidates": len(limited),
                "rank_limit": out_limit,
                "rank_source_candidates": len(ranked),
            },
        )

    gate_summary = apply_options_gate(
        limited,
        limit=options_gate_limit,
        momentum_analyzer=momentum_analyzer,
        flow_analyzer=flow_analyzer,
        status=status,
    )

    buckets: dict[str, int] = {}
    for row in limited:
        buckets[row["rank_bucket"]] = buckets.get(row["rank_bucket"], 0) + 1

    return {
        "scan_date": universe.get("scan_date"),
        "as_of_date": as_of_date,
        "generated_at": _utc_timestamp(),
        "universe": universe.get("universe"),
        "markets": universe.get("markets"),
        "source": "filtered_universe",
        "scoring_model": SCORING_MODEL,
        "score_weights": SCORE_WEIGHTS,
        "money_flow_scoring": {
            "enabled": money_flow_enabled,
            "source": (money_flow_context or {}).get("source") if money_flow_context else "disabled",
            "publishable": bool((money_flow_context or {}).get("publishable")) if money_flow_context else False,
        },
        "total_universe": universe.get("total_universe"),
        "passed_hard_filters": universe.get("passed_hard_filters", len(candidates)),
        "total_candidates": len(candidates),
        "all_ranked_count": len(ranked),
        "rank_limit": out_limit,
        "ranked_candidates_count": len(limited),
        "rank_buckets": buckets,
        "options_gate": gate_summary,
        "tickers": limited,
        "ranked_candidates": limited,
    }


def write_ranked_output(
    path: str | Path,
    universe: dict[str, Any],
    *,
    limit: int | None = None,
    options_gate_limit: int = 0,
    momentum_analyzer: Callable[[str], dict[str, Any]] | None = None,
    flow_analyzer: Callable[[str], dict[str, Any]] | None = None,
    money_flow_artifact: dict[str, Any] | None = None,
    money_flow_enabled: bool = True,
    status: RunStatus | None = None,
) -> dict[str, Any]:
    output = build_ranked_output(
        universe,
        limit=limit,
        options_gate_limit=options_gate_limit,
        momentum_analyzer=momentum_analyzer,
        flow_analyzer=flow_analyzer,
        money_flow_artifact=money_flow_artifact,
        money_flow_enabled=money_flow_enabled,
        status=status,
    )
    out_path = Path(path)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    tmp.replace(out_path)
    return output


def write_ranking_snapshot(output: dict[str, Any], snapshot_dir: str | Path) -> Path:
    """Write a dated candidate-ranking snapshot for analytics history."""
    day = str(output.get("scan_date") or output.get("as_of_date") or _utc_date())[:10]
    out_dir = Path(snapshot_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day}.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Deterministic ranking")
    parser.add_argument("--input", default="filtered_universe.json")
    parser.add_argument("--output", default="ranked_candidates.json")
    parser.add_argument("--history-dir", default="reports/candidate_rankings",
                        help="write dated ranking snapshot for analytics; set empty to disable")
    parser.add_argument("--limit", type=int,
                        default=int(os.environ.get("RANK_LIMIT", "50")),
                        help="write top N ranked candidates")
    parser.add_argument("--options-gate-limit", type=int,
                        default=int(os.environ.get("OPTIONS_GATE_LIMIT", "0")),
                        help="run free options tradability checks for top N; 0 disables")
    parser.add_argument("--money-flow-path", default="reports/money_flow/latest.json",
                        help="Eastmoney money-flow artifact used as bounded ranking confirmation")
    parser.add_argument("--disable-money-flow", action="store_true",
                        help="disable money-flow ranking component for pre-rank/bootstrap runs")
    parser.add_argument("--status-file",
                        help="write latest run status JSON for local UI progress")
    parser.add_argument("--start-status", action="store_true",
                        help="start a fresh status run before ranking; use for rank-only target")
    args = parser.parse_args()

    status = RunStatus(args.status_file) if args.status_file else None
    try:
        universe = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - CLI should report and fail cleanly
        if status:
            status.fail("rank_candidates", "程式排序候選", str(e))
        print(f"[rank_candidates] Failed to read {args.input}: {e}", file=sys.stderr)
        sys.exit(1)

    if status and args.start_status:
        status.start(
            metrics={
                "rank_source_candidates": len(universe.get("tickers", []) or []),
                "rank_limit": args.limit,
                "options_gate_requested": args.options_gate_limit,
            },
            outputs={
                "filtered_universe": {"path": args.input, "exists": Path(args.input).exists()},
                "ranked_candidates": {"path": args.output, "exists": Path(args.output).exists()},
                "scored_candidates": {
                    "path": "scored_candidates.json",
                    "exists": Path("scored_candidates.json").exists(),
                    "stale": True,
                },
            },
        )

    if status:
        status.update_stage(
            "rank_candidates",
            "程式排序候選",
            progress_pct=0,
            message=f"Ranking candidates from {args.input}",
            outputs={
                "filtered_universe": {"path": args.input, "exists": Path(args.input).exists()},
                "ranked_candidates": {"path": args.output, "exists": Path(args.output).exists()},
                "scored_candidates": {
                    "path": "scored_candidates.json",
                    "exists": Path("scored_candidates.json").exists(),
                    "stale": True,
                },
            },
        )

    money_flow_artifact = None
    if not args.disable_money_flow and args.money_flow_path:
        try:
            p = Path(args.money_flow_path)
            if p.is_file():
                money_flow_artifact = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            money_flow_artifact = None

    output = write_ranked_output(
        args.output,
        universe,
        limit=args.limit,
        options_gate_limit=args.options_gate_limit,
        money_flow_artifact=money_flow_artifact,
        money_flow_enabled=not args.disable_money_flow,
        status=status,
    )
    snapshot_path = write_ranking_snapshot(output, args.history_dir) if args.history_dir else None

    if status:
        status.succeed(
            message=(
                f"Ranked top {output['ranked_candidates_count']} from "
                f"{output['total_candidates']} hard-filtered candidates"
            ),
            metrics={
                "ranked_candidates": output["ranked_candidates_count"],
                "rank_limit": output["rank_limit"],
                "rank_source_candidates": output["all_ranked_count"],
                "options_gate_checked": output["options_gate"]["checked"],
            },
            outputs={
                "filtered_universe": {"path": args.input, "exists": Path(args.input).exists()},
                "ranked_candidates": {"path": args.output, "exists": True, "stale": False},
                "candidate_rankings": {
                    "path": str(snapshot_path) if snapshot_path else "",
                    "exists": bool(snapshot_path and snapshot_path.exists()),
                    "stale": False,
                },
                "scored_candidates": {
                    "path": "scored_candidates.json",
                    "exists": Path("scored_candidates.json").exists(),
                    "stale": True,
                },
            },
        )

    print(
        f"[rank_candidates] Done: ranked top {output['ranked_candidates_count']} "
        f"from {output['total_candidates']} hard-filtered candidates "
        f"→ {args.output}"
        + (f" and {snapshot_path}" if snapshot_path else "")
    )


if __name__ == "__main__":
    main()
