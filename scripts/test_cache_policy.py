#!/usr/bin/env python3
"""Static checks for shared cache TTL policy."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import cache_policy  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_ttl_policy_documents_three_cache_temperatures() -> None:
    require(cache_policy.HOT_TTL_SECONDS == 60, "hot cache should be one minute")
    require(cache_policy.WARM_TTL_SECONDS == 900, "warm cache should preserve existing 15m UI behavior")
    require(cache_policy.COLD_TTL_SECONDS == 21600, "cold cache should preserve existing 6h research behavior")


def test_momentum_options_uses_shared_warm_ttl() -> None:
    text = (ROOT / "ui" / "momentum_options.py").read_text(encoding="utf-8")
    require("from scripts import cache_policy" in text, "momentum_options should import cache_policy")
    require("ttl=cache_policy.WARM_TTL_SECONDS" in text, "chart cache should use warm TTL constant")
    require("ttl=900" not in text, "chart cache should not hard-code 900 seconds")


def main() -> None:
    tests = [
        test_ttl_policy_documents_three_cache_temperatures,
        test_momentum_options_uses_shared_warm_ttl,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
