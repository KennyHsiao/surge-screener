# Confirmed-Picks Evidence and Ledger Integrity Plan

## Document Info

| Field | Value |
|---|---|
| Version | v0.2 |
| Status | Implemented and locally verified; release verification pending |
| Author | Codex |
| Reviewer | Pre-implementation blocker review |
| Audience | surge-screener maintainers and operators |
| Prerequisite | `main@f5b79bd`, 7F Data Health 72 PASS / 2 WARN / 0 BLOCK |

## Goal

Make the confirmed-picks path evidence-complete and the performance ledger
lossless without manufacturing picks or changing any scoring weight, threshold,
or DD confirmation rule.

## Scope

In scope:

- versioned technical evidence derived from the Stage 1 adjusted OHLCV snapshot;
- explicit provenance or an explicit missing reason for every technical input;
- deterministic validation of the full-scoring evidence contract;
- a confirmed-ticker allowlist on the final LLM report;
- shared locking, idempotent merge, fsync, and atomic replacement for both ledger writers;
- GitHub Actions serialization for the two performance-ledger writer jobs;
- terminal timestamp compatibility (`finished_at` and `completed_at`);
- offline regression tests and 7F deployment verification.

Out of scope:

- changing 65/72 thresholds, score weights, rank weights, or DD rules;
- backfilling or inventing historical picks;
- guaranteeing that a valid market day produces a pick;
- heuristic claims for VCP, cup-with-handle, flat base, bull flag, or inverse
  head-and-shoulders when the producer has no validated detector;
- shortening the Data Health source-refresh runtime in this change.

## Evidence Semantics

- Price/volume source: the same one-year, auto-adjusted yfinance OHLCV snapshot
  used by Stage 1. No second per-candidate market fetch is introduced.
- `RS Rating`: percentile rank of each ticker's trailing return across the
  data-covered universe in the same scan; the evidence records method, sample
  size, first/last observation, and as-of date.
- `200DMA trending up for one month`: current 200-session mean compared with
  the 200-session mean 21 trading sessions earlier.
- `weekly MACD histogram rising`: calendar-week last closes, MACD(12,26,9),
  current histogram positive and greater than the preceding completed value.
- Unsupported continuation/reversal pattern classifiers are recorded as
  missing and score zero. The LLM is instructed not to infer them.

## Requirements

- `REQ-CPL-001`: Every full-scored candidate MUST carry
  `technical_evidence_v1` with a source, as-of date, input values, and explicit
  missing reasons.
- `REQ-CPL-002`: Stage 2 MUST fail closed when a candidate's technical evidence
  contract is incomplete or malformed.
- `REQ-CPL-003`: Missing technical inputs MUST not be guessed or credited.
- `REQ-CPL-004`: Final report picks MUST be a unique subset of DD-confirmed
  tickers and `total_confirmed` MUST equal the actual ranked-pick count.
- `REQ-CPL-005`: Invalid LLM report output MUST fall back to a deterministic
  report built only from DD-confirmed rows.
- `REQ-CPL-006`: Stage 6 append and Stage 7 return updates MUST use the same
  ledger lock and atomic fsynced replacement.
- `REQ-CPL-007`: A concurrent append during return calculation MUST be retained;
  duplicate `(scan_date,ticker)` rows MUST not be created.
- `REQ-CPL-008`: A pre-replace or replace failure MUST preserve the exact prior
  ledger bytes.
- `REQ-CPL-009`: GitHub-hosted ledger writers MUST be serialized across workflow
  runs because local file locks do not cross runners.
- `REQ-CPL-010`: Successful and failed terminal statuses MUST expose both
  `finished_at` and `completed_at` with the same value.

## Implementation Checklist

- [x] `IMPL-CPL-001`: Extend Stage 1 indicators and attach versioned technical evidence.
- [x] `IMPL-CPL-002`: Assign same-scan universe RS percentiles before filtering output.
- [x] `IMPL-CPL-003`: Validate evidence in Stage 2, attach it to scored rows, and
  strengthen the workflow gate.
- [x] `IMPL-CPL-004`: Deterministically recompute the existing technical rubric,
  validate/fallback the final report, and restrict it to DD-confirmed tickers.
- [x] `IMPL-CPL-005`: Add a shared atomic ledger store and migrate Stage 6 to it.
- [x] `IMPL-CPL-006`: Change Stage 7 to compute outside the lock, then merge under
  lock into the latest ledger before atomic replacement.
- [x] `IMPL-CPL-007`: Add a shared Actions concurrency group to `surge_scan` and
  `verify_returns`.
- [x] `IMPL-CPL-008`: Add `completed_at` terminal timestamp compatibility.
- [ ] `IMPL-CPL-009`: Update operator documentation and release evidence.
  Operator documentation is complete; PR, deployment, 7F, and natural-EOD
  evidence remain release gates.

## Test Specification

| Test ID | Requirement | Verification |
|---|---|---|
| `TEST-CPL-001` | `REQ-CPL-001/003` | Synthetic 230-session OHLCV produces MA/52-week/volume/daily+weekly MACD evidence and explicit unsupported-pattern gaps. |
| `TEST-CPL-002` | `REQ-CPL-001` | Same-scan cross-sectional returns receive deterministic RS percentiles and sample provenance. |
| `TEST-CPL-003` | `REQ-CPL-002` | Missing evidence key fails validation; explicit missing reason passes. |
| `TEST-CPL-004` | `REQ-CPL-003` | Full-score prompt requires zero credit for unsupported/missing inputs. |
| `TEST-CPL-005` | `REQ-CPL-004/005` | LLM-invented, duplicate, or count-mismatched pick is rejected and deterministic fallback contains confirmed rows only. |
| `TEST-CPL-006` | `REQ-CPL-006/007` | Parallel Stage 6 writers retain both distinct picks and deduplicate the same key. |
| `TEST-CPL-007` | `REQ-CPL-006/008` | Injected atomic replace failure preserves exact ledger bytes and leaves no temp file. |
| `TEST-CPL-008` | `REQ-CPL-007` | Stage 7 merge retains a row appended after its initial snapshot. |
| `TEST-CPL-009` | `REQ-CPL-009` | Workflow contract gives both writer jobs the same non-cancelling concurrency group. |
| `TEST-CPL-010` | `REQ-CPL-010` | Success, failure, and interrupted history contain equal terminal timestamps. |

## Acceptance Criteria

- Full EOD validation rejects any row without valid technical evidence.
- No final report can contain a ticker absent from `dd_data.confirmed`.
- No-picks remains a valid zero-row outcome and leaves the ledger unchanged.
- Concurrent/injected-failure ledger tests preserve all committed rows and exact
  last-known-good bytes.
- The complete local test suite passes without network access.
- After merge/deploy, 7F hashes match main and Data Health remains at least
  72 PASS / 2 WARN / 0 BLOCK.
- A later natural EOD run is used to observe evidence completeness and ledger
  outcome; zero picks does not fail acceptance.

## Risks and Rollback

- Evidence math drift: formulas are versioned and tested against synthetic data.
- Short history: fail closed with per-input missing reasons; do not substitute zero.
- Lock contention: bounded local wait with an actionable failure; Actions writers
  are serialized before runner allocation.
- Atomic-write failure: retain the original ledger and clean the temporary file.
- Rollback: revert the change; no historical ledger rows are rewritten during deployment.

## Verification Commands

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_hard_filter_yfinance.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_llm_score_progress.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_build_report.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_append_ledger.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_verify_returns.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_run_status.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_deploy_artifacts.py
make PY=/Users/ken/Workspace/AI/surge-screener/.venv/bin/python test
```

## Blocker Review

- User intent and non-fabrication boundary: PASS.
- Evidence source and RS semantics are explicit: PASS.
- Unsupported pattern behavior is fail-closed: PASS.
- Both ledger writers and cross-run serialization are covered: PASS.
- Affected files, rollback, and offline verification are known: PASS.
- Unresolved blocking questions: none.

## Post-implementation Review

- Resolved: a trailing yfinance row with settled OHLC but missing volume could
  previously make the liquidity comparison fail open through `NaN`. The filter
  now rejects incomplete 20-session volume history.
- Resolved: prompt instructions alone could not guarantee that an LLM awarded
  zero points to missing technical inputs. Stage 2 now recomputes Dimension 1
  from producer evidence using the unchanged 10/8/9/3 rubric and recomputes the
  composite total.
- Resolved: malformed non-object DD rows could be silently dropped before final
  report validation. They now fail closed.
- Actual diff versus accepted scope: aligned. Deterministic scoring enforcement
  is a required hardening of `REQ-CPL-003`, not a change to scoring weights,
  thresholds, or DD policy.

## Change History

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-18 | Accepted implementation plan after blocker review. |
| v0.2 | 2026-08-19 | Implemented, added fail-closed review fixes, and completed focused local verification. |
