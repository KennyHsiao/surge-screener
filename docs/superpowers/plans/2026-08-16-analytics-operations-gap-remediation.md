# Analytics Operations Gap Remediation Plan

Status: **COMPLETED AND VERIFIED — 2026-08-16**

## Document info

| Field | Value |
|---|---|
| Type | Implementation and recovery checklist |
| Owner / approver | Repository maintainer |
| Baseline | `origin/main` at `6feb408ebfc2ed3478a3bd57796ce694381304b6` |
| Runtime evidence | 7F Analytics check at `2026-08-16T08:57:15Z`; GitHub EOD run `31847914905` |
| Safety boundary | No fabricated picks, weight changes, trades, IBKR startup, or unverified artifact promotion |

## Goal

Make EOD report publication race-safe, prevent stale market regime data from
masquerading as a fresh Risk Guard decision, and make Analytics warnings state
what is actually known. Restore only historical daily-report artifacts whose
GitHub run, commit, report date, and payload can be verified.

## Scope and acceptance criteria

### `AC-PUB-001` — report publication survives a concurrent writer

Given a report commit, modified tracked runtime outputs, untracked runtime
outputs, and a remote branch that advances before the first push, publication
must preserve only the intended report commit, obtain the remote change, and
push successfully within a bounded retry count. A failed rebase or exhausted
retry must exit non-zero. A manual run from any source ref other than
`refs/heads/main` must fail before committing so a feature branch cannot be
promoted through `HEAD:main`.

### `AC-RISK-001` — stale regime cannot control a current risk decision

`scored_candidates.json` regime context is usable only when its source date is
within the configured freshness window. A stale or unparseable source must use
the live fallback; if that also fails, Risk Guard must expose a data gap. The
report observation date must be current, while regime source and source date
remain separately visible as provenance.

### `AC-NP-001` — no-picks counts completed decisions, not elapsed weekdays

The confirmed-picks check must count successful published daily reports after
the last ledger pick and separately count successful zero-pick reports. Missing,
failed, and unpublished runs must be separate fields and remain `unknown` when
repository data cannot prove them. Calendar gaps must not inflate the no-picks
count.

### `AC-NP-002` — persistent streaks can re-notify without daily spam

No-picks receipts must deduplicate by action and bounded successful-run
milestone, not forever by last-pick date alone. Messages must say “published
zero-pick scans,” not “trading weekdays.”

### `AC-CAND-001` — bounded LLM scores carry explicit cohort provenance

Normal top-N scoring snapshots may be persisted only with an explicit bounded
cohort type, full ranked-universe count, scored cohort count, selection method,
and rank limit. Analytics must retain those fields so consumers cannot treat a
top-N cohort as an unbiased full-universe sample.

### `AC-OPT-001` — optional/manual sources do not impersonate outages

An absent reconciliation artifact must report `not_configured` and remain
non-actionable. An unchanged manual watchlist must retain its revision date but
must not be evaluated as a failed scanner refresh. Scanner-produced watchlists
remain subject to freshness checks.

### `AC-REC-001` — historical recovery is provenance-bound

Recovery may add only missing `reports/YYYY-MM-DD/` files from a retained
GitHub artifact whose run ID, source SHA, report date, and JSON payload agree.
It must exclude root runtime JSON, `latest` files, reconciliation, ledger rows,
and any pick not already present in the verified report. Existing dates are not
overwritten.

## Implementation checklist

1. Add fail-first regressions for dirty-worktree push races, stale regime
   fallback/provenance, published zero-pick counting, recurring alert buckets,
   bounded score provenance, and optional/manual source semantics.
2. Move report commit/push behavior into one testable bounded publisher and
   call it from the EOD workflow.
3. Add Risk Guard freshness validation and separate observation/source dates.
4. Persist bounded score snapshots with provenance; extend the Analytics
   export contract.
5. Replace weekday no-picks counting with daily-report evidence and explicit
   unknown run-state fields; update alert wording and deduplication.
6. Apply portfolio/watchlist lifecycle policies without touching IBKR or the
   manual watchlist file.
7. Run focused tests, complete `make test`, compile and whitespace gates, then
   compare the actual diff to this checklist and perform a fresh code review.
8. Only after all code gates pass, inspect retained GitHub artifacts and recover
   eligible historical daily-report directories as a separately reviewable
   commit. If provenance or duplicate rules fail, skip recovery and report it.

## Expected files

- `.github/workflows/surge_screener.yml`
- `scripts/publish_reports.py` and its regression test
- `scripts/risk_guard.py`, `scripts/test_risk_guard.py`
- `scripts/persist_candidate_scores.py` and its regression test
- `scripts/analytics_store.py`, `scripts/analytics_checks.py`
- `scripts/analytics_action_notify.py` and related tests
- `scripts/test_deploy_artifacts.py`, `scripts/test_analytics_store.py`,
  `scripts/test_analytics_checks.py`
- `ui/analytics_db.py`
- `docs/analytics-checks-automation.md`,
  `docs/analytics-store-data-inventory.md`,
  `docs/analytics-store-connection.md`
- verified missing `reports/YYYY-MM-DD/` files only when `AC-REC-001` passes

## Verification commands

```bash
.venv/bin/python scripts/test_publish_reports.py
.venv/bin/python scripts/test_risk_guard.py
.venv/bin/python scripts/test_candidate_score_snapshot.py
.venv/bin/python scripts/test_analytics_store.py
.venv/bin/python scripts/test_analytics_checks.py
.venv/bin/python scripts/test_analytics_action_notify.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python -m compileall -q scripts
git diff --check
make test
```

## Risks and rollback

- Publication is medium risk because the workflow writes to `main`; regression
  tests must use temporary local repositories and never a real remote.
- Risk Guard is decision-support data. Stale inputs must fail closed rather
  than be relabeled fresh.
- Persisted bounded candidate scores remain selection-biased; provenance is a
  mandatory field, not documentation-only.
- Optional-source policy changes reduce alert volume; tests must prove core
  signal readiness is unchanged.
- Historical artifacts can be stale or produced from an older source SHA.
  Recovery is additive and date-scoped, with no `latest` promotion.
- Roll back code by reverting the implementation commit. Roll back recovered
  data by reverting only the recovery commit; never delete live runtime files.

## Blocking review gate

- [x] The plan covers all five authorized roadmap items.
- [x] Affected files, focused tests, full verification, and rollback are known.
- [x] Run-state fields remain unknown when telemetry is unavailable; no state is inferred.
- [x] Bounded candidate scores cannot be mistaken for full-universe validation.
- [x] Historical recovery is additive, provenance-bound, and separated from code changes.
- [x] No unresolved credential, trade, IBKR, destructive-data, or scope blocker remains.

## Execution evidence

- Fail-first regressions reproduced the publication race, stale/malformed
  regime provenance, calendar-gap no-picks inflation, missing zero-row source
  provenance, and unbounded candidate-score ambiguity before implementation.
- The focused suites pass 155/155, `make test` exits 0, Python compilation and
  workflow YAML parsing pass, and `git diff --check` is clean.
- A fresh Analytics rebuild for 2026-08-16 classifies 14 successful published
  zero-pick scans, zero successful scans with picks, zero unclassified reports,
  and leaves missing/failed/unpublished counts unknown because repository data
  cannot prove them. It marks the absent portfolio source `not_configured` and
  the owner-maintained watchlist under a manual-revision policy.
- GitHub artifacts `9202664755` (run `31752818053`, source `17415bab...`) and
  `9238456016` (run `31847914905`, source `020edc14...`) independently verify
  the missing 2026-08-13 and 2026-08-15 report directories. Both contain zero
  confirmed picks. Existing 2026-08-12 files were not overwritten; no root
  runtime output, `latest` file, ledger row, pick, or weight was restored.
- `ui/analytics_db.py` and `docs/analytics-store-connection.md` were added to
  the expected file set because the new state/provenance contract must be
  rendered and documented consistently; this is necessary scope, not drift.
- The first closure engine timed out before a final verdict but exposed one
  valid publication-boundary issue: a manually dispatched feature ref could be
  pushed through `HEAD:main`. The publisher now rejects any workflow source ref
  other than `refs/heads/main` before it creates a commit, with a regression
  proving that the feature history remains unpromoted.
- The same partial review identified that `surge_scan` runs on a persistent
  self-hosted runner. Runtime outputs are still removed only after artifact
  upload, but the exact publisher-owned stash is now dropped on success and
  failure so repeated runs cannot accumulate hidden repository state.
- Final independent closure found no remaining blocking, high, or medium issue
  and marked intent alignment `PASS`. The Codex CLI engine remains recorded as
  unavailable because its valid commit-review invocation exceeded the 300-second
  hard limit without a final verdict; Claude was intentionally not used.
