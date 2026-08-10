#!/usr/bin/env python3
"""Self-contained tests for strong continuation outcome labels.

Run:  .venv/bin/python scripts/test_continuation_strength.py
"""

from __future__ import annotations

from datetime import date, timedelta
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_strong_continuation_requires_return_and_controlled_drawdown() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "NVDA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": 0.18,
        "fwd_30d_max_drawdown": -0.07,
        "resolved_30d": True,
        "fwd_60d_return": 0.34,
        "fwd_60d_max_drawdown": -0.13,
        "resolved_60d": True,
    })

    assert row["continuation_label"] == "strong_continuation"
    assert row["primary_horizon"] == "30d"
    assert row["trade_value"] == "high"


def test_continuation_unresolved_window_does_not_guess() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "AAA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": None,
        "fwd_30d_max_drawdown": None,
        "resolved_30d": False,
    })

    assert row["continuation_label"] == "unresolved"
    assert row["trade_value"] == "unknown"


def test_build_report_uses_observe_date_and_daily_bars_without_lookahead() -> None:
    from scripts import continuation_strength as cont

    features = [
        {
            "ticker": "AAA",
            "surge_start": "2026-01-02",
            "observe_date": "2026-01-05",
            "thresholds_hit": ["+30%/20d"],
            "magnitude_pct": 42.0,
            "flags": {"rvol_ge_2": True, "rel_strength_vs_spy": True},
        },
        {
            "ticker": "BBB",
            "surge_start": "2026-01-02",
            "observe_date": "2026-01-05",
            "thresholds_hit": ["+30%/20d"],
            "magnitude_pct": 31.0,
            "flags": {"bb_squeeze": True},
        },
    ]
    bars = []
    start = date(2026, 1, 5)
    for idx in range(0, 65):
        close = 100.0
        if idx == 5:
            close = 95.0
        if idx == 30:
            close = 118.0
        if idx == 60:
            close = 134.0
        bars.append({
            "ticker": "AAA",
            "bar_date": (start + timedelta(days=idx)).isoformat(),
            "close": close,
            "adj_close": close,
        })
    for idx in range(0, 10):
        bars.append({
            "ticker": "BBB",
            "bar_date": (start + timedelta(days=idx)).isoformat(),
            "close": 100.0 + idx,
            "adj_close": 100.0 + idx,
        })

    report = cont.build_report(features=features, daily_bars=bars, min_resolved=2)

    assert report["status"] == "accumulating"
    assert report["resolved"] == 1
    assert report["summary"]["strong_continuation"] == 1
    assert report["summary"]["unresolved"] == 1
    first = report["rows"][0]
    assert first["setup_date"] == "2026-01-05"
    assert first["fwd_30d_return"] == 0.18
    assert first["fwd_30d_max_drawdown"] == -0.05
    assert first["continuation_label"] == "strong_continuation"
    assert first["candidate_causes"] == [
        "technical_volume_expansion",
        "relative_strength_leadership",
    ]


def test_build_report_blocks_when_daily_bars_are_missing() -> None:
    from scripts import continuation_strength as cont

    report = cont.build_report(
        features=[{"ticker": "AAA", "observe_date": "2026-01-05"}],
        daily_bars=[],
        min_resolved=1,
    )

    assert report["status"] == "blocked"
    assert "daily bars" in report["reason"]
    assert report["rows"] == []


def test_daily_bar_duplicates_do_not_shift_forward_horizon() -> None:
    from scripts import continuation_strength as cont

    start = date(2026, 1, 5)
    bars = [
        {"ticker": "AAA", "bar_date": start.isoformat(), "close": 99.0, "adj_close": 99.0},
        {"ticker": "AAA", "bar_date": start.isoformat(), "close": 100.0, "adj_close": 100.0},
    ]
    for idx in range(1, 31):
        close = 118.0 if idx == 30 else 100.0
        bars.append({
            "ticker": "AAA",
            "bar_date": (start + timedelta(days=idx)).isoformat(),
            "close": close,
            "adj_close": close,
        })

    report = cont.build_report(
        features=[{"ticker": "AAA", "observe_date": start.isoformat()}],
        daily_bars=bars,
        min_resolved=1,
    )

    assert report["rows"][0]["fwd_30d_return"] == 0.18


def test_load_daily_bars_uses_only_first_authoritative_source() -> None:
    from scripts import continuation_strength as cont

    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        raw = reports / "market_data" / "daily_bars"
        analytics = root / "analytics"
        raw.mkdir(parents=True)
        (analytics / "parquet").mkdir(parents=True)
        explicit = root / "explicit.parquet"
        pd.DataFrame([{"ticker": "EXPLICIT", "bar_date": "2026-01-01", "close": 1.0}]).to_parquet(explicit)
        pd.DataFrame([{"ticker": "ANALYTICS", "bar_date": "2026-01-01", "close": 2.0}]).to_parquet(
            analytics / "parquet" / "daily_bars.parquet"
        )
        pd.DataFrame([{"ticker": "RAW", "bar_date": "2026-01-01", "close": 3.0}]).to_parquet(
            raw / "2026-01-01.parquet"
        )

        rows = cont.load_daily_bars(reports_dir=reports, analytics_dir=analytics, bars_path=explicit)

    assert [row["ticker"] for row in rows] == ["EXPLICIT"]


def test_load_daily_bars_falls_back_to_latest_raw_snapshot_only() -> None:
    from scripts import continuation_strength as cont

    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        raw = reports / "market_data" / "daily_bars"
        raw.mkdir(parents=True)
        pd.DataFrame([{"ticker": "OLD", "bar_date": "2026-01-01", "close": 1.0}]).to_parquet(
            raw / "2026-01-01.parquet"
        )
        pd.DataFrame([{"ticker": "NEW", "bar_date": "2026-01-02", "close": 2.0}]).to_parquet(
            raw / "2026-01-02.parquet"
        )

        rows = cont.load_daily_bars(reports_dir=reports)

    assert [row["ticker"] for row in rows] == ["NEW"]


def test_load_daily_bars_prefers_raw_canonical_over_dated_fallback() -> None:
    from scripts import continuation_strength as cont

    with TemporaryDirectory() as td:
        reports = Path(td) / "reports"
        raw = reports / "market_data" / "daily_bars"
        raw.mkdir(parents=True)
        pd.DataFrame([{"ticker": "CANON", "bar_date": "2026-01-01", "close": 1.0}]).to_parquet(
            raw / "canonical.parquet"
        )
        pd.DataFrame([{"ticker": "DATED", "bar_date": "2026-01-02", "close": 2.0}]).to_parquet(
            raw / "2026-01-02.parquet"
        )

        rows = cont.load_daily_bars(reports_dir=reports)

    assert [row["ticker"] for row in rows] == ["CANON"]


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
