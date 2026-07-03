"""Shared cache TTL policy for UI-facing data loaders.

The constants are intentionally small and explicit. Fail-closed scanners,
backtests, and forward-validation jobs should keep their own freshness rules
instead of importing these UI cache defaults.
"""

from __future__ import annotations


HOT_TTL_SECONDS = 60
WARM_TTL_SECONDS = 15 * 60
COLD_TTL_SECONDS = 6 * 60 * 60
