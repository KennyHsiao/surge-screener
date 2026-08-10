#!/usr/bin/env python3
"""Build and classify post-setup continuation-strength validation reports."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent


def _repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _date_key(value: Any) -> str | None:
    raw = str(value or "")[:10]
    if not raw:
        return None
    try:
        datetime.fromisoformat(raw)
    except ValueError:
        return None
    return raw


def _json_rows(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get(key) or payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def load_features(path: str | Path) -> list[dict[str, Any]]:
    source = _repo_path(path)
    if not source.exists():
        raise FileNotFoundError(f"continuation features not found: {source}")
    return _json_rows(json.loads(source.read_text(encoding="utf-8")), "features")


def _read_parquet_rows(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    import pandas as pd

    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    return [row for row in df.to_dict("records") if isinstance(row, dict)]


def load_daily_bars(
    *,
    reports_dir: str | Path | None = None,
    analytics_dir: str | Path | None = None,
    bars_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Load normalized daily-bar rows from known platform artifact locations."""
    candidates: list[Path] = []
    if bars_path is not None:
        candidates.append(_repo_path(bars_path))
    if analytics_dir is not None:
        candidates.append(Path(analytics_dir) / "parquet" / "daily_bars.parquet")
    reports = Path(reports_dir) if reports_dir is not None else REPO / "reports"
    candidates.append(reports / "analytics" / "parquet" / "daily_bars.parquet")

    seen_files: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen_files:
            continue
        seen_files.add(candidate)
        rows = _read_parquet_rows(candidate)
        if rows is not None:
            return rows

    bars_dir = reports / "market_data" / "daily_bars"
    if bars_dir.is_dir():
        raw_candidates = [bars_dir / "canonical.parquet"]
        raw_candidates.extend(sorted(bars_dir.glob("????-??-??.parquet"), reverse=True))
        for path in raw_candidates:
            rows = _read_parquet_rows(path.resolve())
            if rows is not None:
                return rows
    return []


def _candidate_causes(feature: dict[str, Any]) -> list[str]:
    flags = feature.get("flags") if isinstance(feature.get("flags"), dict) else {}
    causes: list[str] = []
    if flags.get("rvol_ge_2") or flags.get("breakout_above_resist"):
        causes.append("technical_volume_expansion")
    if flags.get("rel_strength_vs_spy"):
        causes.append("relative_strength_leadership")
    if flags.get("bb_squeeze") or flags.get("low_rv_base"):
        causes.append("technical_compression_base")
    if flags.get("macd_positive") or flags.get("macd_golden_cross_10d"):
        causes.append("technical_momentum_confirm")
    if flags.get("price_above_ma200") or flags.get("ma_stack_50_150_200"):
        causes.append("trend_quality")
    if flags.get("market_regime_ok"):
        causes.append("market_regime_support")
    return causes or ["unknown"]


def _bar_groups(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        bar_date = _date_key(row.get("bar_date") or row.get("date") or row.get("Date"))
        close = _num(row.get("adj_close"))
        if close is None:
            close = _num(row.get("close") or row.get("Close"))
        if not ticker or bar_date is None or close is None or close <= 0:
            continue
        grouped.setdefault(ticker, {})[bar_date] = float(close)
    for ticker in list(grouped):
        grouped[ticker] = dict(sorted(grouped[ticker].items()))
    return {
        ticker: list(dated.items())
        for ticker, dated in grouped.items()
    }


def _forward_metrics(
    feature: dict[str, Any],
    grouped_bars: dict[str, list[tuple[str, float]]],
    *,
    horizons: tuple[int, ...] = (30, 60),
) -> dict[str, Any]:
    ticker = str(feature.get("ticker") or "").upper().strip()
    setup_date = _date_key(
        feature.get("observe_date")
        or feature.get("setup_date")
        or feature.get("as_of_date")
        or feature.get("surge_start")
    )
    out: dict[str, Any] = {
        "ticker": ticker,
        "setup_date": setup_date,
    }
    for horizon in horizons:
        out[f"resolved_{horizon}d"] = False
        out[f"fwd_{horizon}d_return"] = None
        out[f"fwd_{horizon}d_max_drawdown"] = None

    bars = grouped_bars.get(ticker) or []
    if not ticker or setup_date is None or not bars:
        return out

    entry_idx = next((idx for idx, (bar_date, _) in enumerate(bars) if bar_date >= setup_date), None)
    if entry_idx is None:
        return out

    entry = bars[entry_idx][1]
    if entry <= 0:
        return out

    for horizon in horizons:
        target_idx = entry_idx + horizon
        if target_idx >= len(bars):
            continue
        window = [close for _, close in bars[entry_idx + 1:target_idx + 1]]
        if not window:
            continue
        out[f"resolved_{horizon}d"] = True
        out[f"fwd_{horizon}d_return"] = round(window[-1] / entry - 1.0, 6)
        out[f"fwd_{horizon}d_max_drawdown"] = round(min(close / entry - 1.0 for close in window), 6)
    return out


def classify_continuation(row: dict[str, Any]) -> dict[str, Any]:
    resolved_30 = bool(row.get("resolved_30d"))
    resolved_60 = bool(row.get("resolved_60d"))

    if not resolved_30 and not resolved_60:
        return {
            "ticker": row.get("ticker"),
            "setup_date": row.get("setup_date") or row.get("as_of_date"),
            "continuation_label": "unresolved",
            "primary_horizon": None,
            "trade_value": "unknown",
        }

    r30 = row.get("fwd_30d_return")
    dd30 = row.get("fwd_30d_max_drawdown")
    r60 = row.get("fwd_60d_return")
    dd60 = row.get("fwd_60d_max_drawdown")

    strong_30 = (
        resolved_30
        and r30 is not None
        and dd30 is not None
        and float(r30) >= 0.15
        and float(dd30) >= -0.10
    )
    strong_60 = (
        resolved_60
        and r60 is not None
        and dd60 is not None
        and float(r60) >= 0.30
        and float(dd60) >= -0.15
    )
    if strong_30:
        label, horizon, value = "strong_continuation", "30d", "high"
    elif strong_60:
        label, horizon, value = "strong_continuation", "60d", "high"
    elif resolved_30 and r30 is not None and float(r30) > 0:
        label, horizon, value = "normal_continuation", "30d", "medium"
    else:
        label, horizon, value = "failed_breakout", "30d" if resolved_30 else "60d", "low"

    return {
        "ticker": row.get("ticker"),
        "setup_date": row.get("setup_date") or row.get("as_of_date"),
        "continuation_label": label,
        "primary_horizon": horizon,
        "trade_value": value,
    }


def build_report(
    *,
    features: list[dict[str, Any]],
    daily_bars: list[dict[str, Any]],
    min_resolved: int = 30,
    horizons: tuple[int, ...] = (30, 60),
) -> dict[str, Any]:
    if not features:
        return {
            "generated_at": _now_iso(),
            "status": "blocked",
            "reason": "continuation features are missing",
            "resolved": 0,
            "min_resolved": int(min_resolved),
            "summary": {},
            "rows": [],
        }
    grouped = _bar_groups(daily_bars)
    if not grouped:
        return {
            "generated_at": _now_iso(),
            "status": "blocked",
            "reason": "daily bars are missing or unreadable",
            "resolved": 0,
            "min_resolved": int(min_resolved),
            "summary": {},
            "rows": [],
        }

    rows: list[dict[str, Any]] = []
    for feature in features:
        metrics = _forward_metrics(feature, grouped, horizons=horizons)
        classified = classify_continuation(metrics)
        row = {
            "ticker": metrics.get("ticker"),
            "setup_date": metrics.get("setup_date"),
            "surge_start": feature.get("surge_start"),
            "thresholds_hit": feature.get("thresholds_hit") or [],
            "magnitude_pct": feature.get("magnitude_pct"),
            "candidate_causes": _candidate_causes(feature),
            "cause_certainty": "candidate_only",
            "measurement_source": "daily_bars",
            **metrics,
            **classified,
        }
        rows.append(row)

    counts = Counter(str(row.get("continuation_label") or "unknown") for row in rows)
    resolved = sum(1 for row in rows if row.get("continuation_label") != "unresolved")
    summary = {
        "strong_continuation": int(counts.get("strong_continuation", 0)),
        "normal_continuation": int(counts.get("normal_continuation", 0)),
        "failed_breakout": int(counts.get("failed_breakout", 0)),
        "unresolved": int(counts.get("unresolved", 0)),
        "rows_total": len(rows),
        "resolved": resolved,
        "min_resolved": int(min_resolved),
    }
    return {
        "generated_at": _now_iso(),
        "status": "accumulating" if resolved < min_resolved else "ready",
        "resolved": resolved,
        "min_resolved": int(min_resolved),
        "summary": summary,
        "rows": rows,
        "note": (
            "Continuation strength is measured from observe_date/setup_date using forward "
            "returns and max drawdown. Candidate causes are labels for analysis, not causal proof."
        ),
    }


def write_report(report: dict[str, Any], output: str | Path) -> Path:
    path = _repo_path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_report(
    *,
    features: str | Path = "reports/retrospective/surge_features.json",
    output: str | Path = "reports/retrospective/continuation_strength.json",
    reports_dir: str | Path | None = None,
    analytics_dir: str | Path | None = None,
    bars_path: str | Path | None = None,
    min_resolved: int = 30,
) -> dict[str, Any]:
    try:
        feature_rows = load_features(features)
        bars = load_daily_bars(
            reports_dir=reports_dir,
            analytics_dir=analytics_dir,
            bars_path=bars_path,
        )
        report = build_report(
            features=feature_rows,
            daily_bars=bars,
            min_resolved=min_resolved,
        )
    except FileNotFoundError as exc:
        report = {
            "generated_at": _now_iso(),
            "status": "blocked",
            "reason": str(exc),
            "resolved": 0,
            "min_resolved": int(min_resolved),
            "summary": {},
            "rows": [],
        }
    write_report(report, output)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strong-continuation validation report")
    parser.add_argument("--features", default="reports/retrospective/surge_features.json")
    parser.add_argument("--output", default="reports/retrospective/continuation_strength.json")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--analytics-dir", default=None)
    parser.add_argument("--bars", default=None, help="explicit daily_bars parquet path")
    parser.add_argument("--min-resolved", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_report(
            features=args.features,
            output=args.output,
            reports_dir=args.reports_dir,
            analytics_dir=args.analytics_dir,
            bars_path=args.bars,
            min_resolved=args.min_resolved,
        )
    except Exception as exc:  # noqa: BLE001 - unexpected code/config failures should be visible.
        print(f"[continuation_strength] error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "status={status} resolved={resolved}/{min_resolved}".format(
                status=report.get("status"),
                resolved=report.get("resolved"),
                min_resolved=report.get("min_resolved"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
