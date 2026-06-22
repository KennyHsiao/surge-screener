#!/usr/bin/env python3
"""Shared cached yfinance close-history fetch — first increment of the unified
fetch layer (P1a).

Dedups the SPY/VIX **market-regime** fetches that ``02_llm_score`` and
``risk_guard`` each re-fetched uncached every run (the workflow map found SPY/VIX
pulled 3–5× per day across processes, while almost every per-ticker fetch is
already wrapped in ``cache.py``). This is the one clean, *staleness-tolerant*
dedup target.

Composes ``scripts/cache.py`` (disk, short TTL). Two properties inherited from
``get_or_compute`` make it safe to drop into the regime path:
  • a cache MISS calls the compute fn directly and does NOT catch its exception,
    so a yfinance rate-limit/failure PROPAGATES to the caller exactly as before
    (callers degrade or fail as they already do); and
  • a falsy/empty result is never cached, so a transient empty fetch isn't sticky.

⚠ SCOPE BOUNDARY — read before reusing:
Use this ONLY for non-fail-closed, staleness-tolerant context (market regime).
Do NOT route the oversold / reversal / forward fail-closed paths through here.
Their ``_required_close()`` + coverage / ratchet / publish guards rely on SEEING
every fetch failure (the per-ticker ``fetch_failed`` count) so a wholly
rate-limited day fails closed (hollow-scan abort). A cache HIT would hand back
30-min-old data and MASK that outage. Those paths keep their own uncached,
backoff-guarded fetch on purpose.

Usage:
    from _yfinance import cached_closes
    spy = cached_closes("SPY", "1y")   # list[float] oldest→newest, or None
"""

from __future__ import annotations

try:
    from cache import get_or_compute
except ImportError:  # imported as scripts.<mod> from the repo root
    from scripts.cache import get_or_compute

# 30 min: regime context (SPY 50/200DMA position, VIX level) tolerates this and
# it stays well under a single trading session, so the verdict never goes stale
# within a run while still collapsing the 3–5 same-day duplicate fetches.
REGIME_TTL = 1800


def cached_closes(ticker: str, period: str, ttl: float = REGIME_TTL,
                  auto_adjust: bool = True) -> list[float] | None:
    """Close series (oldest→newest) for ``ticker`` over ``period``, cached on disk
    by ``(ticker, period, auto_adjust)`` for ``ttl`` seconds.

    Returns ``None`` when no data is available (caller degrades). A fetch failure
    RAISES — never masked — identical to calling yfinance directly, so callers'
    existing try/except degrade-paths behave unchanged.

    ``auto_adjust`` is part of the cache key on purpose: adjusted (True, the
    yfinance default used by the regime callers) and raw (False, used by
    live_factors / retro for Dim5) closes are different price scales and MUST NOT
    collide on one key.
    """
    def _compute() -> list[float] | None:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=auto_adjust)
        if hist is None or hist.empty:
            return None
        return [float(x) for x in hist["Close"].dropna().values]

    return get_or_compute(
        "regime_closes", {"ticker": ticker, "period": period, "auto_adjust": auto_adjust},
        ttl, _compute)
