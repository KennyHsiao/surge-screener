#!/usr/bin/env python3
"""Offline regression checks for non-MKT review fixes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import options_term  # noqa: E402
import reversal_radar_forward as rfwd  # noqa: E402
import reversal_radar_scan as rscan  # noqa: E402


def test_rotating_prescreen_slice_is_not_fixed_prefix() -> None:
    tickers = [f"T{i:02d}" for i in range(10)]
    a, ma = rscan._rotating_slice(tickers, 3, "2026-06-23")
    b, mb = rscan._rotating_slice(tickers, 3, "2026-06-24")
    assert len(a) == len(b) == 3
    assert ma["mode"] == mb["mode"] == "date_rotating_cap"
    assert a != b
    assert a != tickers[:3] or b != tickers[:3]


def test_prescreen_guard_blocks_degraded_fetch_coverage() -> None:
    reason = rscan._prescreen_guard({"attempted": 100, "price_usable": 20})
    assert reason and "coverage" in reason
    assert rscan._prescreen_guard({"attempted": 100, "price_usable": 90}) is None


def test_reversal_forward_publish_guard_blocks_resolution_collapse() -> None:
    assert rfwd._publish_guard(10, 0, {}, None)
    prev = {"price_resolvable": 100, "by_tier": {"+10%/20d": {"resolved": 80, "hits": 40, "excess_n": 70}}}
    by_tier = {"+10%/20d": {"resolved": 10, "hits": 40, "excess_n": 70}}
    reason = rfwd._publish_guard(120, 95, by_tier, prev)
    assert reason and "resolved collapsed" in reason


def test_options_term_cache_key_includes_spot() -> None:
    calls = []
    old = options_term._cached

    def fake_cached(namespace, params, ttl, compute):  # noqa: ARG001
        calls.append(params)
        return {"ok": True}

    try:
        options_term._cached = fake_cached
        options_term.term_structure("AAPL", 100.12)
        options_term.term_structure("AAPL", 101.12)
    finally:
        options_term._cached = old

    assert calls[0]["ticker"] == "AAPL"
    assert calls[0]["v"] == 3
    assert calls[0]["spot"] != calls[1]["spot"]


if __name__ == "__main__":
    tests = [
        test_rotating_prescreen_slice_is_not_fixed_prefix,
        test_prescreen_guard_blocks_degraded_fetch_coverage,
        test_reversal_forward_publish_guard_blocks_resolution_collapse,
        test_options_term_cache_key_includes_spot,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("ALL PASS")
