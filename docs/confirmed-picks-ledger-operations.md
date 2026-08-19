# Confirmed Picks and Performance Ledger Operations

## What constitutes success

An EOD run is valid when the bounded candidate cohort is fully scored from a
valid evidence contract, the final report contains only DD-confirmed tickers,
and report publication completes. A valid run may produce zero confirmed picks.
Zero picks must not create, backfill, or otherwise modify the performance ledger.

This pipeline never relaxes the 65/72 score thresholds, score weights, or DD
confirmation rules to manufacture an outcome.

## Technical evidence

Each full-scored row contains `technical_evidence_v1`, derived from the same
one-year auto-adjusted yfinance OHLCV snapshot used by the hard filter. The
contract records the source, as-of date, history length, and either a value or a
missing reason for every required input.

The same-scan `RS Rating` is the percentile of trailing one-year return across
the data-covered universe. The evidence records its method and universe sample
size. Daily and weekly MACD values are deterministic. The current RSI divergence
detector is daily-only, so weekly RSI divergence is explicitly missing. VCP,
cup-with-handle, flat base, bull flag, higher-high/higher-low, inverse
head-and-shoulders, and W-bottom neckline confirmation also remain missing until
validated deterministic detectors exist. Missing inputs receive zero credit.

Stage 2 deterministically reapplies the existing 10-point trend, 8-point volume,
9-point pattern, and 3-point MACD rubric to that evidence. It replaces the LLM's
technical breakdown and technical score, then recomputes the composite score.
This enforcement does not change any weight or threshold; it prevents a model
response from crediting a fact that the producer marked missing.

The Stage 2 workflow gate rejects incomplete evidence, non-finite evidence,
non-deterministic technical-score provenance, or score totals that do not match
their component breakdown even when the LLM response is otherwise well formed.

## Final report guard

The final report must contain exactly the unique ticker set in
`dd_data.confirmed`, use the scan date, and report the matching count. An invalid
LLM report falls back to a deterministic report. Ticker, final score, verdict,
thesis, entry, stop, position size, and key risk are projected from DD/Layer 2
source rows; the final-report model cannot introduce an unconfirmed ticker or
replace these critical values.

## Ledger writer guarantees

Both `scripts/06_append_ledger.py` and `scripts/07_verify_returns.py` use the
same `performance_ledger.csv.lock`. Writes create and fsync a complete temporary
CSV in the ledger directory, atomically replace the target, then fsync the
directory. The lock file is runtime-only and ignored by Git.

Stage 7 fetches prices outside the lock, then reacquires the lock and merges only
previously blank return cells into a fresh read. Rows appended while price data
was being fetched are therefore retained. GitHub Actions also serializes the EOD
and forward-return jobs with the non-cancelling
`surge-screener-performance-ledger` concurrency group because filesystem locks
cannot cross runners.

## Verification

Run the focused offline checks:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_hard_filter_yfinance.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_llm_score_progress.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_build_report.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_append_ledger.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_verify_returns.py
```

After deployment, verify the 7F hashes against main and rerun Data Health. The
next natural EOD is the first authoritative observation of the new evidence and
ledger outcome. Acceptance requires complete evidence and truthful terminal
state; it does not require a non-zero pick count.
