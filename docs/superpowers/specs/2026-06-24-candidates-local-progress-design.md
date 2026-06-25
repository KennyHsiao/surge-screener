# Candidates Local Progress Design

## Goal

Expose progress for `make candidates-local` so a user can tell whether the local candidate refresh is running, stalled, failed, or complete.

## Scope

This design adds a single machine-readable status file:

```text
reports/run_status/candidates-local.json
```

The CLI pipeline writes the file. Streamlit reads the file. Streamlit does not start, stop, or manage the shell process.

## Status Contract

The status file is a JSON object with these stable top-level fields:

- `run_id`: unique id for this run, based on job name and UTC start time.
- `job`: fixed string, `candidates-local`.
- `status`: one of `running`, `succeeded`, or `failed`.
- `started_at`, `updated_at`, `finished_at`: ISO UTC timestamps; `finished_at` is present only after completion.
- `pid`: process id of the script writing the status, when available.
- `stage`: current stage summary for simple UI rendering.
- `stages`: ordered list of known stages and their current states.
- `metrics`: numeric counters suitable for progress text.
- `outputs`: generated artifact paths and existence/staleness state.
- `warnings`: non-fatal warnings.
- `errors`: fatal errors or stage failures.

The minimal running shape is:

```json
{
  "run_id": "candidates-local-2026-06-24T12:09:27Z",
  "job": "candidates-local",
  "status": "running",
  "started_at": "2026-06-24T12:09:27Z",
  "updated_at": "2026-06-24T12:14:03Z",
  "pid": 84231,
  "stage": {
    "id": "hard_filter.fetch_ohlcv",
    "label": "抓取 yfinance OHLCV",
    "status": "running",
    "progress_pct": 42.6,
    "message": "Downloading batch 26/61"
  },
  "metrics": {
    "universe": "sp1500",
    "total_tickers": 1503,
    "batch_size": 25,
    "total_batches": 61,
    "completed_batches": 26,
    "downloaded_tickers": 632,
    "min_data_coverage": 0.7,
    "current_coverage": 0.4205,
    "candidate_limit": 25,
    "scored_candidates": 0
  },
  "outputs": {
    "filtered_universe": {"path": "filtered_universe.json", "exists": false},
    "scored_candidates": {"path": "scored_candidates.json", "exists": true, "stale": true}
  },
  "warnings": [],
  "errors": []
}
```

## Stages

The initial implementation covers the stages that `make candidates-local` runs today:

1. `preflight`: Claude SDK credentials check. This stage is reported by the Makefile wrapper only as complete or skipped because it runs before `01_hard_filter.py`.
2. `hard_filter.fetch_ohlcv`: yfinance OHLCV batch downloads.
3. `hard_filter.info`: per-ticker `fast_info` and calendar metadata.
4. `hard_filter.apply_filters`: indicator computation and hard-filter application.
5. `llm_score.regime`: regime context calculation.
6. `llm_score.candidates`: Layer-1 LLM scoring.
7. `done`: terminal success.

The first pass may write stages from `01_hard_filter.py` and `02_llm_score.py` independently to the same status file. The latest writer updates its own current stage and preserves earlier output/metrics where practical.

## UI Behavior

The UI reads `reports/run_status/candidates-local.json` and renders a compact read-only panel in 今日決策 and/or 排程與結果:

- If `status == running`, show `stage.label`, `stage.message`, and `stage.progress_pct` in a progress bar.
- If `status == succeeded`, show completion time and generated artifacts.
- If `status == failed`, show the failed stage and error message.
- If the file is missing, show no active local refresh.
- If `updated_at` is old while `status == running`, mark it as possibly stale instead of claiming the process is still alive.

## Error Handling

The writer must update the status file before exiting on known failures, including yfinance coverage below the floor. Unhandled exceptions should still leave the previous status file visible; the UI treats a stale `running` file as possibly interrupted.

## Testing

Tests should cover:

- `01_hard_filter.py` writes batch progress when a status path is provided.
- Coverage failure writes `status: failed`.
- Successful hard-filter completion writes output metrics.
- UI helper renders a stale/running/succeeded/failed summary from representative JSON without invoking shell commands.
