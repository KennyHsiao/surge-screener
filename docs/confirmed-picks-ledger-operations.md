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
A verified pattern with zero volume points caps technical at 10. When technical
is below 12, sentiment at 12 or above caps composite at 50 and options flow at
15 or above caps it at 55; the regime multiplier is applied only afterward.
Two missing whole scoring dimensions prevent promotion to Layer 2, and an LLM
WATCHLIST/REJECT risk veto cannot be promoted during normalization. The bearish
options veto is also carried as a structured identifier, but may be set only
when the source proves the exact sweep or aggressive bid-side condition; a free
chain's aggregate put/call ratio alone is insufficient. Each applied rule records
its exact before/after values in `score_adjustments`, while individual
`technical:<input>` gaps do not count as a missing whole dimension.
This enforcement does not change any weight or threshold; it prevents a model
response from crediting a fact that the producer marked missing or bypassing an
existing critical cap.

The Stage 2 workflow gate and offline mutation tests execute the same pure score
contract validator. It rejects incomplete evidence, non-finite evidence,
non-deterministic technical-score provenance, score totals that do not match
their component breakdown, incorrect cap arithmetic, a permissive verdict, or
score-adjustment provenance that differs from the deterministic reconstruction.

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
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_stage7_evidence.py
```

Stage 7 reports `PASS_UPDATED` when either blank forward-return cells are
filled or the no-picks notifier appends an allowlisted receipt. A receipt-only
publication does not claim a ledger return update: `positive_update_observed`
remains false while `receipt_update_observed` is true. `PASS_NOOP` means that
neither allowlisted artifact had an accepted semantic mutation; the ordinary
no-op path is additionally expected to keep both files byte-stable.

After deployment, verify the 7F hashes, loaded timers, and service readiness
against main. Do not manually rerun Data Health or a producer while preserving
the natural-observation boundary. The next scheduled Data Health and natural
EOD are the first authoritative observations of the new evidence and ledger
outcome. Acceptance requires complete evidence and truthful terminal state; it
does not require a non-zero pick count.

The first authoritative natural observation completed on 2026-08-20
Asia/Taipei. Release status, artifact hashes, terminal timestamps, traceability,
and zero-pick ledger evidence are recorded in
`docs/confirmed-picks-ledger-release-evidence-2026-08-20.md`.

The separate Stage 7 natural scheduled observation completed with
`PASS_NOOP` on 2026-08-20 Asia/Taipei. Its run-head binding, byte-stable ledger
and alert receipt, terminal artifact hashes, authority boundary, and regression
coverage are certified in
`docs/stage7-natural-validation-release-evidence-2026-08-21.md`.
