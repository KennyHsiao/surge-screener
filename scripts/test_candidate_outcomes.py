#!/usr/bin/env python3
"""Self-contained tests for deterministic candidate paper outcomes."""

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
        "candidate_outcomes_under_test",
        ROOT / "scripts" / "candidate_outcomes.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_ranking(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "scan_date": "2026-06-24",
        "generated_at": "2026-06-24T22:30:00Z",
        "source": "filtered_universe",
        "scoring_model": "deterministic_rank_v1",
        "rank_limit": 2,
        "ranked_candidates": [
            {
                "ticker": "NVDA",
                "rank_score": 91.4,
                "rank_bucket": "priority",
                "last_price": 150.0,
            },
            {
                "ticker": "AMD",
                "rank_score": 72.2,
                "rank_bucket": "watch",
                "last_price": 100.0,
            },
        ],
    }), encoding="utf-8")


def test_update_writes_candidate_outcomes_from_ranking_snapshot() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rankings_dir = tmp / "reports" / "candidate_rankings"
        outcomes_dir = tmp / "reports" / "candidate_outcomes"
        _write_ranking(rankings_dir / "2026-06-24.json")

        loaded: list[str] = []

        def fake_loader(ticker: str, start_date: str, end_date: str):
            loaded.append(f"{ticker}:{start_date}:{end_date}")
            index = pd.to_datetime([
                "2026-06-24", "2026-06-25", "2026-06-30", "2026-07-01", "2026-07-02"
            ])
            if ticker == "NVDA":
                close = [150.0, 148.0, 160.0, 168.75, 166.0]
            elif ticker == "AMD":
                close = [100.0, 99.0, 97.0, 96.0, 95.0]
            else:
                raise AssertionError(f"unexpected ticker: {ticker}")
            return pd.Series(close, index=index)

        summary = mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-02",
            limit=2,
            price_loader=fake_loader,
        )
        payload = json.loads((outcomes_dir / "2026-06-24.json").read_text(encoding="utf-8"))

        if summary["rows"] != 2 or summary["files_written"] != 1:
            raise AssertionError(summary)
        if sorted(item.split(":")[0] for item in loaded) != ["AMD", "NVDA"]:
            raise AssertionError(loaded)
        rows = {row["ticker"]: row for row in payload["outcomes"]}
        if rows["NVDA"]["rank_position"] != 1 or rows["NVDA"]["resolved_7d"] is not True:
            raise AssertionError(rows)
        if rows["NVDA"]["fwd_7d_return"] != 12.5:
            raise AssertionError(rows)
        if rows["NVDA"]["max_drawdown_30d"] != -1.33:
            raise AssertionError(rows)
        if rows["AMD"]["fwd_7d_return"] != -4.0:
            raise AssertionError(rows)
        if rows["NVDA"]["resolved_14d"] is not False:
            raise AssertionError(rows)


def test_update_is_idempotent_for_same_scan_date_and_ticker() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rankings_dir = tmp / "reports" / "candidate_rankings"
        outcomes_dir = tmp / "reports" / "candidate_outcomes"
        _write_ranking(rankings_dir / "2026-06-24.json")

        def fake_loader(ticker: str, start_date: str, end_date: str):
            index = pd.to_datetime(["2026-06-24", "2026-07-01", "2026-07-02"])
            base = 150.0 if ticker == "NVDA" else 100.0
            return pd.Series([base, base * 1.1, base * 1.2], index=index)

        for _ in range(2):
            mod.update_outcomes(
                rankings_dir=rankings_dir,
                outcomes_dir=outcomes_dir,
                as_of_date="2026-07-02",
                limit=2,
                price_loader=fake_loader,
            )
        payload = json.loads((outcomes_dir / "2026-06-24.json").read_text(encoding="utf-8"))
        keys = [(row["scan_date"], row["ticker"]) for row in payload["outcomes"]]

        if keys != [("2026-06-24", "NVDA"), ("2026-06-24", "AMD")]:
            raise AssertionError(payload)


def test_update_replaces_same_day_candidate_set_on_rerun() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rankings_dir = tmp / "reports" / "candidate_rankings"
        outcomes_dir = tmp / "reports" / "candidate_outcomes"
        ranking_path = rankings_dir / "2026-06-24.json"
        _write_ranking(ranking_path)

        def fake_loader(ticker: str, start_date: str, end_date: str):
            index = pd.to_datetime(["2026-06-24", "2026-07-01", "2026-07-02"])
            base = 150.0 if ticker == "NVDA" else 100.0
            return pd.Series([base, base * 1.1, base * 1.2], index=index)

        mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-02",
            limit=2,
            price_loader=fake_loader,
        )
        ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
        ranking["ranked_candidates"] = [
            {
                "ticker": "NVDA",
                "rank_score": 93.0,
                "rank_bucket": "priority",
                "last_price": 150.0,
            }
        ]
        ranking_path.write_text(json.dumps(ranking), encoding="utf-8")

        mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-02",
            limit=2,
            price_loader=fake_loader,
        )
        payload = json.loads((outcomes_dir / "2026-06-24.json").read_text(encoding="utf-8"))
        tickers = [row["ticker"] for row in payload["outcomes"]]

        if tickers != ["NVDA"]:
            raise AssertionError(payload)


def test_update_does_not_rewrite_when_no_horizon_changes() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rankings_dir = tmp / "reports" / "candidate_rankings"
        outcomes_dir = tmp / "reports" / "candidate_outcomes"
        _write_ranking(rankings_dir / "2026-06-24.json")
        counter = {"n": 0}

        def fake_timestamp() -> str:
            counter["n"] += 1
            return f"2026-07-02T00:00:{counter['n']:02d}Z"

        mod._utc_timestamp = fake_timestamp

        def fake_loader(ticker: str, start_date: str, end_date: str):
            index = pd.to_datetime(["2026-06-24", "2026-07-01", "2026-07-02"])
            base = 150.0 if ticker == "NVDA" else 100.0
            return pd.Series([base, base * 1.1, base * 1.2], index=index)

        first = mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-02",
            limit=2,
            price_loader=fake_loader,
        )
        path = outcomes_dir / "2026-06-24.json"
        before = path.read_text(encoding="utf-8")
        second = mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-07-02",
            limit=2,
            price_loader=fake_loader,
        )
        after = path.read_text(encoding="utf-8")

        if first["files_written"] != 1:
            raise AssertionError(first)
        if second["files_written"] != 0:
            raise AssertionError(second)
        if before != after:
            raise AssertionError("outcome file changed without a matured horizon")


def test_update_skips_price_loader_before_first_horizon_is_due() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rankings_dir = tmp / "reports" / "candidate_rankings"
        outcomes_dir = tmp / "reports" / "candidate_outcomes"
        _write_ranking(rankings_dir / "2026-06-24.json")
        calls: list[str] = []

        def fake_loader(ticker: str, start_date: str, end_date: str):
            calls.append(ticker)
            raise AssertionError("price loader should not run before 7D is due")

        summary = mod.update_outcomes(
            rankings_dir=rankings_dir,
            outcomes_dir=outcomes_dir,
            as_of_date="2026-06-26",
            limit=2,
            price_loader=fake_loader,
        )
        payload = json.loads((outcomes_dir / "2026-06-24.json").read_text(encoding="utf-8"))

        if calls:
            raise AssertionError(calls)
        if summary["rows"] != 2:
            raise AssertionError(summary)
        if any(row["resolved_7d"] for row in payload["outcomes"]):
            raise AssertionError(payload)


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
    sys.exit(main())
