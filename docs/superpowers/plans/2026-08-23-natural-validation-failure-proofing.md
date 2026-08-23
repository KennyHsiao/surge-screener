# 2026-08-24 natural-validation failure-proofing plan

## Objective

Make every preventable or locally recoverable failure close before the natural
2026-08-24 EOD / 2026-08-25 post-ingestion acceptance window, without manual
workflow dispatch, synthetic reports, fabricated picks, ledger edits, weight
changes, threshold changes, or relaxed evidence rules.

The terminal acceptance contract is:

- the scheduled EOD and calendar-required Market Thesis producers succeed;
- the 2026-08-24 candidate artifact contains at least 25 fully scored rows and
  `remaining_unscored == 0`;
- every row passes the deterministic full-score/evidence-capability contract;
- `promotion_reachability_v1.unsupported_credit_count == 0` and its ticker list
  is empty;
- Theme Flow is fresh for the report date;
- post-ingestion ends `PASS` / `succeeded` after atomically promoting the report
  generation, Parquet, checks, and DuckDB;
- confirmed-picks / ledger validation remains blocked until those gates pass.

## Read-only baseline

- 7F clock is Asia/Taipei with NTP synchronized.
- 7F has 163 GiB free, 94% free inodes, 19 GiB available memory, and no swap use.
- the GitHub runner is online, idle, systemd-managed with `Restart=always`;
  API and Streamlit are healthy on their exact loopback endpoints.
- Codex subscription auth and a bounded SPY Yahoo query pass on 7F.
- all four local timers are enabled, active, and loaded without daemon-reload
  drift; their next triggers match the intended window.
- the latest post-ingestion state is 2026-08-21 `PASS` / `succeeded`; no runtime
  transaction residue was observed.
- the 2026-08-21 EOD schedule was created 17 minutes late and still completed in
  48 minutes. Observer decisions must therefore use terminal state plus the
  10:30 deadline, not nominal-clock absence.

## DEEP FMEA

Scores use severity / occurrence / detection from 1 to 10. RPN is their product.

| Failure mode | S | O | D | RPN | Detection | Prevention / recovery |
|---|---:|---:|---:|---:|---|---|
| Post-ingestion accepts shadow or unsupported nontechnical credit | 9 | 7 | 8 | 504 | deterministic artifact gate | validate every full-score row and require exact unsupported-credit zero before build |
| One transient GitHub content/API failure becomes terminal after producers pass | 8 | 5 | 6 | 240 | pending artifact-gate status with attempt evidence | bounded retry until the window deadline; malformed JSON remains terminal |
| A Yahoo batch fails, is empty, or returns only some requested tickers | 9 | 4 | 5 | 180 | existing coverage floor and batch progress | retry only missing tickers with bounded backoff; never lower coverage |
| A successful workflow publishes a malformed or incomplete candidate artifact | 9 | 3 | 7 | 189 | fixed-SHA artifact contract | reject before report/Analytics promotion and retain last known good |
| Theme Flow fails once and observer records terminal failure before systemd recovery | 8 | 4 | 5 | 160 | fresh service status and deadline | bounded `on-failure` service retries; local failure remains pending until deadline |
| Data Health or post-ingestion fails on one transient local/provider fault | 8 | 4 | 4 | 128 | systemd result and canonical run status | bounded `on-failure` retries in a 16-hour rate window; transactional Analytics keeps last known good |
| GitHub unauthenticated API rate limit is exhausted by polling | 7 | 3 | 5 | 105 | captured rate-limit headers and API errors | cache completed run jobs, retain five-minute producer polling, retry content reads rather than busy-loop |
| A newly queued scheduled run returns an empty jobs list once and stays cached forever | 9 | 3 | 7 | 189 | empty-then-terminal job-cache regression | refresh empty or incomplete job lists on every bounded poll until terminal |
| Scheduled EOD or Market Thesis is delayed | 9 | 3 | 3 | 81 | terminal job discovery inside the window | wait for the actual scheduled job until 10:30; never substitute a dispatch run |
| Self-hosted runner stops or flaps | 9 | 2 | 2 | 36 | GitHub runner API plus user-systemd state | existing five-second `Restart=always`; verify after deployment and before handoff |
| Data Health and post-ingestion contend for the Analytics writer lock | 8 | 3 | 3 | 72 | shared-lock status and transaction tests | retain one lock and rollback boundary; post-ingestion waits up to one hour |
| Lock/build/evidence persistence starts before 10:30 but records a late PASS | 10 | 2 | 7 | deadline-bound lock and persistence tests | cap the lock wait to remaining time and recheck before PASS writes and commit |
| Disk, inode, permissions, clock, DNS, or deployed-unit drift blocks persistence | 9 | 2 | 2 | 36 | 7F preflight | deploy gate plus post-deploy exact checks; do not start producers during preflight |
| PASS/status persistence fails after provisional promotion | 10 | 2 | 2 | 40 | existing fault-injection regressions and recovery journal | retain the already-deployed atomic rollback transaction unchanged |
| Generation pointer rename is not durable before the journal commit marker | 10 | 2 | 7 | 140 | directory-fsync and post-commit recovery regression | fsync the published-store directory after promotion and rollback pointer mutations |
| GitHub Actions or Yahoo has a window-long regional/global outage | 10 | 2 | 9 | 180 | deadline terminal evidence | residual external risk: fail closed and preserve last known good; do not counterfeit a natural run |

Propagation is stopped at the earliest durable boundary: failed batches do not
lower the coverage floor; malformed candidate evidence does not enter the
published generation; transient report fetches do not create terminal evidence;
failed local refreshes do not replace canonical Analytics; failed promotions or
evidence writes restore all companions under one lock.

## Implementation

1. Add fail-first candidate-artifact tests for shadow capability mode, tampered
   full-score rows, non-zero unsupported credit, and inconsistent unsupported
   ticker lists.
2. Reuse `validate_full_score_contract` in post-producer ingestion and include
   promotion reachability in the Analytics defence-in-depth gate and verdict.
3. Add a bounded artifact-preparation retry state after all producers pass.
   Retry only GitHub transport/API and unpublished-propagation failures until
   the existing 10:30 deadline. Contract failures, Analytics failures, producer
   failures, and persistence failures stay terminal and fail closed. Refresh an
   initially empty/incomplete jobs cache rather than freezing a queued run as
   permanently missing. Cap writer-lock wait and final PASS/commit checks to the
   remaining natural window. Run the synchronous Analytics build in a bounded
   child while the lock-owning parent performs journal recovery and terminal
   persistence if the wall-clock deadline expires. Fsync every `current`
   pointer mutation before allowing the journal to commit, and prove a
   successful commit is not later treated as a recoverable pending promotion.
4. Add bounded per-batch Yahoo retry for exceptions, empty results, or missing
   tickers in a partial response. Retry only the missing subset. Preserve the
   70% coverage floor, output schema, and non-threaded production default.
5. Give Data Health, Theme Flow, and post-producer ingestion at most two
   automatic retries after an explicit non-zero exit. Use a 16-hour start-limit
   interval so the first maximum-duration post start remains in the rolling
   window when systemd evaluates and blocks a fourth start. Keep their timers,
   commands, outputs, and atomic writer contracts
   unchanged. Let post-producer wait for a recovered local Theme result until
   the deadline while keeping GitHub producer failures terminal.
6. Update deployment contract tests and the post-producer operations guide.
   Record the FMEA / resilience / Builder decisions in the required journals.

## Verification

- run each changed regression in fail-first form against the pre-change source;
- run post-producer, scoring, hard-filter, deployment, transaction, Data Health,
  and Theme focused suites;
- compile changed Python, parse workflow/YAML where applicable, and run the
  repository whitespace/diff gate;
- run complete `make test` in the isolated clean worktree;
- compare the actual diff to this plan and perform a fresh blocking review;
- open a PR, merge only after checks pass, deploy through the normal workflow,
  and verify exact 7F code/unit hashes, services, timers, auth, market-data probe,
  health endpoints, old LKG identities, and absence of transaction residue;
- do not manually run EOD, Market Thesis, post-ingestion, or ledger mutation;
- observe the natural window and require exact unsupported-credit zero before
  moving to confirmed-picks / ledger.

## Rollback

Revert the merge and redeploy through the normal deployment workflow. Existing
published generations, Analytics last-known-good data, reports, picks, and ledger
remain untouched by rollback. No cleanup command may delete shared runtime data.
