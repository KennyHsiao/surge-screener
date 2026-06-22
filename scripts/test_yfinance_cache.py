#!/usr/bin/env python3
"""Self-contained tests for _yfinance.cached_closes (no network).

A fake `yfinance` module is injected into sys.modules so we exercise the real
cache.py composition without hitting the network. Covers the three properties
the regime dedup relies on:
  • cache MISS computes, HIT (within TTL) does NOT recompute — the dedup win;
  • a fetch failure PROPAGATES (never masked) — fail-closed callers stay correct;
  • an empty/None fetch is NOT cached (not sticky) and not counted as a hit.

Uses an isolated CACHE_DIR via the repo's reports/.cache with a unique ticker so
it never collides with real cached data. Run:
    .venv/bin/python scripts/test_yfinance_cache.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd  # noqa: E402

# ── Inject a fake yfinance whose call count + behaviour we control ───────────
_CALLS = {"n": 0}
_MODE = {"v": "ok"}  # "ok" | "raise" | "empty"


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period=None, **kw):
        _CALLS["n"] += 1
        if _MODE["v"] == "raise":
            raise RuntimeError("YFRateLimitError (simulated)")
        if _MODE["v"] == "empty":
            return pd.DataFrame()
        # 210 ascending closes so 50/200DMA slices are exercised downstream.
        return pd.DataFrame({"Close": [100.0 + i for i in range(210)]})


_fake = types.ModuleType("yfinance")
_fake.Ticker = _FakeTicker
sys.modules["yfinance"] = _fake

import _yfinance as yfc  # noqa: E402


# Unique tickers per test so disk-cache entries never collide across runs.
def _u(tag: str) -> str:
    return f"__TEST_{tag}__"


def test_miss_then_hit_dedup():
    t = _u("HIT")
    _CALLS["n"] = 0
    _MODE["v"] = "ok"
    a = yfc.cached_closes(t, "1y", ttl=300)
    b = yfc.cached_closes(t, "1y", ttl=300)
    assert a == b and a is not None and len(a) == 210, "both calls return same series"
    assert _CALLS["n"] == 1, f"HIT must not recompute (got {_CALLS['n']} fetches)"


def test_failure_propagates():
    t = _u("RAISE")
    _CALLS["n"] = 0
    _MODE["v"] = "raise"
    raised = False
    try:
        yfc.cached_closes(t, "1y", ttl=300)
    except RuntimeError:
        raised = True
    assert raised, "a fetch failure must PROPAGATE, never be masked by the cache"


def test_empty_not_cached():
    t = _u("EMPTY")
    _CALLS["n"] = 0
    _MODE["v"] = "empty"
    r1 = yfc.cached_closes(t, "1y", ttl=300)
    r2 = yfc.cached_closes(t, "1y", ttl=300)
    assert r1 is None and r2 is None, "empty fetch returns None"
    assert _CALLS["n"] == 2, f"None must NOT be cached (got {_CALLS['n']} fetches, expected 2)"


def main() -> int:
    tests = [test_miss_then_hit_dedup, test_failure_propagates, test_empty_not_cached]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
