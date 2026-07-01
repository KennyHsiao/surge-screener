#!/usr/bin/env python3
"""Self-contained tests for fundamentals_free report overlays.

Run:  .venv/bin/python scripts/test_fundamentals_free.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "fundamentals_free_under_test",
        ROOT / "scripts" / "fundamentals_free.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_load_official_metrics_filters_latest_snapshot_by_ticker() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        reports = Path(d) / "reports"
        fundamentals = reports / "fundamentals"
        fundamentals.mkdir(parents=True)
        (fundamentals / "latest.json").write_text(json.dumps({
            "rows": [
                {
                    "ticker": "AAPL",
                    "period_end": "2026-03-28",
                    "metric": "revenue",
                    "label": "Revenue",
                    "value": 95359000000,
                    "unit": "USD",
                    "source": "sec_companyfacts",
                    "confidence": 95,
                    "source_conflict": False,
                },
                {
                    "ticker": "MSFT",
                    "period_end": "2026-03-31",
                    "metric": "revenue",
                    "label": "Revenue",
                    "value": 70000000000,
                    "unit": "USD",
                    "source": "sec_companyfacts",
                    "confidence": 95,
                    "source_conflict": False,
                },
            ],
        }), encoding="utf-8")

        rows = mod.load_official_metrics("aapl", reports_dir=reports)

    if len(rows) != 1:
        raise AssertionError(rows)
    if rows[0]["metric"] != "revenue" or rows[0]["source"] != "sec_companyfacts":
        raise AssertionError(rows)


def test_compute_fundamentals_returns_official_metrics_when_yfinance_fails() -> None:
    mod = _load_module()
    fake_yfinance = types.ModuleType("yfinance")

    class BrokenTicker:
        @property
        def info(self):
            raise RuntimeError("yfinance unavailable")

    fake_yfinance.Ticker = lambda _ticker: BrokenTicker()
    old_yfinance = sys.modules.get("yfinance")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        reports = root / "reports"
        fundamentals = reports / "fundamentals"
        fundamentals.mkdir(parents=True)
        (fundamentals / "latest.json").write_text(json.dumps({
            "rows": [{
                "ticker": "AAPL",
                "period_end": "2026-03-28",
                "metric": "revenue",
                "label": "Revenue",
                "value": 95359000000,
                "unit": "USD",
                "source": "sec_companyfacts",
                "confidence": 95,
                "source_conflict": False,
            }],
        }), encoding="utf-8")
        sys.modules["yfinance"] = fake_yfinance
        old_repo = mod.REPO
        mod.REPO = root
        try:
            out = mod._compute_fundamentals("AAPL")
        finally:
            mod.REPO = old_repo
            if old_yfinance is None:
                sys.modules.pop("yfinance", None)
            else:
                sys.modules["yfinance"] = old_yfinance

    if not out:
        raise AssertionError(out)
    if out["source"] != "fundamental_metrics":
        raise AssertionError(out)
    if out["official_metrics"][0]["metric"] != "revenue":
        raise AssertionError(out)


def main() -> int:
    tests = [
        test_load_official_metrics_filters_latest_snapshot_by_ticker,
        test_compute_fundamentals_returns_official_metrics_when_yfinance_fails,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - self-contained test runner
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failures:
        print(f"\n{failures}/{len(tests)} failed")
        return 1
    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
