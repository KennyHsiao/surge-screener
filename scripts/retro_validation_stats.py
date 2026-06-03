#!/usr/bin/env python3
"""Shared validation statistics for the surge-retrospective lift engine.

Pure-stdlib (the .venv has NO scipy — see retro_factor_lift's note). Two pieces:

  * two_proportion_p — one-sided p-value for H1: P(factor|surger) > P(factor|control),
    a normal-approx two-proportion z-test. Feeds the multiple-testing correction.
  * benjamini_hochberg — BH false-discovery-rate q-values across a FAMILY of factors.

Why this exists (the factor-zoo lesson): when you test ~17 factors per table, some
will clear a single-test bar by chance. Harvey-Liu-Zhu (2016) argue the t-bar must
rise with the number of tests; BH-FDR is the standard control. We DON'T overwrite
the existing Wilson-interval verdict — we add q_value + verdict_mt alongside it, so
a factor that looks VALIDATED on its own but fails FDR across the family is demoted.
See knowledge/papers/harvey-liu-zhu-2016-cross-section.md.
"""

from __future__ import annotations

import math

FDR_ALPHA = 0.10  # target false-discovery rate for the multiple-testing gate


def ncdf(x: float) -> float:
    """Standard normal CDF via erf (no scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def two_proportion_p(t_s: int, n_s: int, t_c: int, n_c: int) -> float:
    """One-sided p-value for H1: surge-rate > control-rate (pooled-variance z-test).

    t_* = true count, n_* = known count in each arm. Returns 1.0 (no evidence) when
    either arm is empty or the pooled variance is degenerate and the diff is non-positive.
    """
    if n_s <= 0 or n_c <= 0:
        return 1.0
    p_s, p_c = t_s / n_s, t_c / n_c
    p_pool = (t_s + t_c) / (n_s + n_c)
    var = p_pool * (1.0 - p_pool) * (1.0 / n_s + 1.0 / n_c)
    if var <= 0.0:                      # p_pool is 0 or 1 → no variance
        return 0.0 if p_s > p_c else 1.0
    z = (p_s - p_c) / math.sqrt(var)
    return 1.0 - ncdf(z)               # upper-tail: small p ⇒ surge-rate genuinely higher


def benjamini_hochberg(pvals: list[float], alpha: float = FDR_ALPHA) -> tuple[list[float], list[bool]]:
    """BH step-up FDR. Returns (q_values, reject) aligned to the input order.

    q_value = the smallest FDR at which this hypothesis is rejected (monotone via the
    standard step-up enforcement). reject[i] is q_values[i] <= alpha.
    """
    m = len(pvals)
    if m == 0:
        return [], []
    order = sorted(range(m), key=lambda i: pvals[i])   # ascending p
    q = [1.0] * m
    running_min = 1.0
    for rank in range(m - 1, -1, -1):                  # step up from largest p
        i = order[rank]
        val = pvals[i] * m / (rank + 1)
        running_min = min(running_min, val)
        q[i] = min(running_min, 1.0)
    return q, [q[i] <= alpha for i in range(m)]


def mt_verdict(verdict: str, q_value: float | None, alpha: float = FDR_ALPHA) -> str:
    """Multiple-testing-aware verdict: demote POSITIVE calls that fail FDR by one notch.

    A factor that is VALIDATED / WEAK on its own Wilson interval but whose q_value
    exceeds alpha (doesn't survive the family-wide FDR control) is likely a multiple-
    testing artifact, so it steps down. Non-positive verdicts pass through unchanged.
    """
    survives = q_value is not None and q_value <= alpha
    if verdict == "VALIDATED":
        return "VALIDATED" if survives else "WEAK"
    if verdict == "WEAK":
        return "WEAK" if survives else "NOISE"
    return verdict
