#!/usr/bin/env python3
"""Self-contained tests for options-flow forward validation."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent


def _load_forward():
    spec = importlib.util.spec_from_file_location(
        "options_flow_forward_under_test",
        ROOT / "scripts" / "options_flow_forward.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_evaluate_entry_scores_bullish_and_bearish_directions() -> None:
    mod = _load_forward()

    bullish_close = np.array([100.0] + [101.0] * 9 + [106.0] + [107.0] * 30)
    bullish = mod.evaluate_entry(bullish_close, "bullish")

    if not bullish["+5%/10d"]["resolved"] or not bullish["+5%/10d"]["hit"]:
        raise AssertionError(bullish)
    if round(float(bullish["+5%/10d"]["horizon_return"]), 4) != 0.06:
        raise AssertionError(bullish)

    bearish_close = np.array([100.0] + [99.0] * 4 + [94.0] + [92.0] * 35)
    bearish = mod.evaluate_entry(bearish_close, "bearish")

    if not bearish["+5%/10d"]["resolved"] or not bearish["+5%/10d"]["hit"]:
        raise AssertionError(bearish)
    if round(float(bearish["+5%/10d"]["horizon_return"]), 4) != 0.08:
        raise AssertionError(bearish)


def test_run_writes_validation_summary_from_dated_snapshots_only() -> None:
    mod = _load_forward()
    with tempfile.TemporaryDirectory() as d:
        flow_dir = Path(d) / "options_flow"
        flow_dir.mkdir()
        dated_payload = {
            "as_of": "2026-01-02",
            "generated_at": "2026-01-02T22:00:00Z",
            "signals": [
                {"ticker": "BULL", "direction": "bullish", "flow_score": 91},
                {"ticker": "BEAR", "direction": "bearish", "flow_score": 87},
            ],
        }
        (flow_dir / "2026-01-02.json").write_text(json.dumps(dated_payload), encoding="utf-8")
        (flow_dir / "latest.json").write_text(
            json.dumps({"as_of": "2026-01-03", "signals": [{"ticker": "SHOULD_NOT_LOAD"}]}),
            encoding="utf-8",
        )

        loaded: list[str] = []

        def fake_price_loader(ticker: str, entry_date: str):
            loaded.append(ticker)
            index = pd.date_range(entry_date, periods=45, freq="D")
            if ticker == "BULL":
                close = [100.0] + [101.0] * 9 + [106.0] + [108.0] * 34
            elif ticker == "BEAR":
                close = [100.0] + [99.0] * 4 + [94.0] + [92.0] * 39
            else:
                raise AssertionError(f"unexpected ticker loaded: {ticker}")
            return pd.Series(close[:45], index=index)

        output = flow_dir / "validation_summary.json"
        payload = mod.run(flow_dir=flow_dir, output=output, price_loader=fake_price_loader)

        if sorted(loaded) != ["BEAR", "BULL"]:
            raise AssertionError(loaded)
        if payload["entries_accumulated"] != 2 or payload["price_resolvable"] != 2:
            raise AssertionError(payload)
        tier = payload["by_tier"]["+5%/10d"]
        if tier["resolved"] != 2 or tier["hits"] != 2 or tier["hit_rate"] != 1.0:
            raise AssertionError(tier)
        if not output.is_file():
            raise AssertionError("validation summary was not written")


if __name__ == "__main__":
    test_evaluate_entry_scores_bullish_and_bearish_directions()
    test_run_writes_validation_summary_from_dated_snapshots_only()
    print("options_flow_forward tests passed")
