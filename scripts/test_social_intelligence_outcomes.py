#!/usr/bin/env python3
"""Self-contained tests for social intelligence forward outcomes."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "social_intelligence_outcomes_under_test",
        ROOT / "scripts" / "social_intelligence_outcomes.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_snapshot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "as_of_date": "2026-06-24",
        "generated_at": "2026-06-24T22:00:00Z",
        "source": "social_intelligence",
        "tickers": [
            {
                "ticker": "NVDA",
                "mentioned_by": ["alpha"],
                "discovery_sources": ["x_influencer_picks"],
                "platform_validation": {"in_ranked_candidates": True, "rank_score": 82.0},
                "labels": {"early_signal": True, "crowded": False},
            }
        ],
    }), encoding="utf-8")


def test_update_social_outcomes_writes_separate_forward_returns_and_spy_comparison() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        snapshot_dir = root / "reports" / "social_intelligence"
        outcomes_dir = root / "reports" / "social_intelligence_outcomes"
        _write_snapshot(snapshot_dir / "2026-06-24.json")

        loaded: list[str] = []

        def fake_loader(ticker: str, start_date: str, end_date: str):
            loaded.append(f"{ticker}:{start_date}:{end_date}")
            index = pd.to_datetime(["2026-06-24", "2026-07-01", "2026-07-08"])
            if ticker == "NVDA":
                return pd.Series([100.0, 112.5, 120.0], index=index)
            if ticker == "SPY":
                return pd.Series([500.0, 510.0, 515.0], index=index)
            raise AssertionError(ticker)

        summary = mod.update_social_outcomes(
            snapshot_dir=snapshot_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-09",
            price_loader=fake_loader,
        )

        out_path = outcomes_dir / "2026-06-24.json"
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        row = payload["outcomes"][0]
        if summary["files_written"] != 1 or summary["rows"] != 1:
            raise AssertionError(summary)
        if sorted(item.split(":")[0] for item in loaded) != ["NVDA", "SPY"]:
            raise AssertionError(loaded)
        if row["fwd_7d_return"] != 12.5:
            raise AssertionError(row)
        if row["spy_fwd_7d_return"] != 2.0:
            raise AssertionError(row)
        if row["excess_vs_spy_7d"] != 10.5:
            raise AssertionError(row)
        if row["fwd_14d_return"] != 20.0:
            raise AssertionError(row)
        if row["resolved_30d"] is not False:
            raise AssertionError(row)
        if payload["source_stats"]["handles"]["alpha"]["hit_7d"] != 1:
            raise AssertionError(payload)
        if (root / "reports" / "candidate_outcomes").exists():
            raise AssertionError("social outcomes must not pollute candidate_outcomes")


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
