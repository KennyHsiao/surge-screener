#!/usr/bin/env python3
"""Offline tests for Risk Guard report persistence helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_risk_guard():
    spec = importlib.util.spec_from_file_location(
        "risk_guard_under_test",
        ROOT / "scripts" / "risk_guard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_write_report_writes_latest_and_dated_snapshot() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "reports" / "risk_guard" / "latest.json"
        payload = {
            "as_of": "2026-06-05",
            "generated_at": "2026-06-05T22:00:00Z",
            "rows": [{"ticker": "NVDA", "status": "REDUCE", "risk_score": 55}],
        }

        paths = risk_guard.write_report(payload, out)

        latest = json.loads(out.read_text(encoding="utf-8"))
        snapshot_path = out.with_name("2026-06-05.json")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if latest != payload or snapshot != payload:
            raise AssertionError((latest, snapshot))
        if paths.get("latest") != str(out) or paths.get("snapshot") != str(snapshot_path):
            raise AssertionError(paths)


def test_write_report_uses_generated_date_when_as_of_missing() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "latest.json"
        payload = {
            "generated_at": "2026-06-06T01:23:45Z",
            "rows": [],
        }

        paths = risk_guard.write_report(payload, out)

        if not out.with_name("2026-06-06.json").is_file():
            raise AssertionError(paths)


def test_load_regime_falls_back_when_scored_context_is_stale() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        scored = Path(d) / "scored_candidates.json"
        scored.write_text(json.dumps({
            "scan_date": "2026-06-30",
            "regime_context": {
                "spy_vs_50dma": "above",
                "spy_vs_200dma": "above",
                "vix_level": 16.0,
            },
        }), encoding="utf-8")
        risk_guard.SCORED = scored
        risk_guard._live_regime = lambda: {
            "spy_vs_50dma": "below",
            "spy_vs_200dma": "above",
            "vix_level": 24.0,
            "source": "live_yfinance",
        }

        regime, source = risk_guard.load_regime(
            today=date(2026, 8, 16), max_age_days=3,
        )

        if source != "live_yfinance" or regime.get("vix_level") != 24.0:
            raise AssertionError((source, regime))
        if regime.get("observed_on") != "2026-08-16":
            raise AssertionError(regime)
        if regime.get("source_as_of") is not None:
            raise AssertionError(regime)
        if regime.get("fallback_reason") != "stale_scored_regime":
            raise AssertionError(regime)


def test_malformed_explicit_regime_date_cannot_fall_through_to_newer_date() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        scored = Path(d) / "scored_candidates.json"
        scored.write_text(json.dumps({
            "scan_date": "2026-08-16",
            "regime_context": {
                "source_as_of": "not-a-date",
                "spy_vs_50dma": "above",
                "vix_level": 12.0,
            },
        }), encoding="utf-8")
        risk_guard.SCORED = scored
        risk_guard._live_regime = lambda: {}

        regime, source = risk_guard.load_regime(today=date(2026, 8, 16))

        if source != "live_yfinance":
            raise AssertionError((source, regime))
        if regime.get("fallback_reason") != "invalid_scored_regime_date":
            raise AssertionError(regime)
        if any(regime.get(key) is not None for key in ("spy_vs_50dma", "vix_level")):
            raise AssertionError(regime)


def test_analysis_observation_date_is_not_regime_source_date() -> None:
    risk_guard = _load_risk_guard()
    risk_guard.load_regime = lambda: ({
        "scan_date": "2026-06-30",
        "source_as_of": "2026-06-30",
        "spy_vs_50dma": "above",
        "spy_vs_200dma": "above",
        "vix_level": 16.0,
    }, "scored_candidates.json")
    risk_guard.latest_cot = lambda: None
    risk_guard.sf.gather_sector_flow = lambda: {"sectors": []}
    risk_guard._read_json = lambda _path: None

    result = risk_guard.analyze_risk([])

    expected_today = datetime.now(timezone.utc).date().isoformat()
    if result.get("as_of") != expected_today:
        raise AssertionError(result)
    if result.get("data_sources", {}).get("regime_as_of") != "2026-06-30":
        raise AssertionError(result.get("data_sources"))


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
