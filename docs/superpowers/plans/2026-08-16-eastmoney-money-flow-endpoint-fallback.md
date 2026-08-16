# Eastmoney Money Flow Endpoint Fallback Plan

Status: **ACCEPTED FOR IMPLEMENTATION — authorized 2026-08-16**

## Document info

| Field | Value |
|---|---|
| Type | Implementation checklist |
| Version | v0.1 |
| Owner / approver | Repository maintainer |
| Author / implementer | Codex |
| Audience | Maintainers and release reviewers |
| Baseline | `origin/main` at `64c6f7433e780a2f1641bf3c93eacd92d4279fb9` |
| Related operations | `docs/analytics-checks-automation.md` |

## Goal

Restore publishable Eastmoney money-flow collection when the primary
`push2his.eastmoney.com` route closes connections from cloud or test-server
egress. Preserve the current fail-soft behavior when every route is unavailable.

## Evidence

- The 2026-08-15 Data Health run completed, but requested `214` tickers and
  resolved `0`; Analytics reported `MONEY_FLOW_UNPUBLISHABLE`.
- The committed 2026-08-14 hosted-run artifact requested `213` and resolved
  `0`. Most daily runs since 2026-07-03 resolved `0` or `1`; only 2026-07-22
  reached publishable coverage.
- A read-only probe on the 7F test server reproduced an EOF from
  `push2his.eastmoney.com` for AAPL, NVDA, MSFT, and BRK.B.
- The same server returned a schema-compatible AAPL row from
  `push2delay.eastmoney.com` at the identical API path and parameters.

## Scope

- Add the delayed Eastmoney hostname as a bounded fallback for the existing
  daily money-flow adapter.
- Try the fallback after a transport/HTTP failure or an empty parsed response.
- Return the first non-empty normalized response.
- Preserve the existing normalized source identifiers and artifact schema.
- Add deterministic adapter tests for primary success, transport fallback,
  empty-response fallback, and all-routes-unavailable behavior.
- Verify a representative live sample from the 7F test server before any
  production artifact refresh.

## Non-goals

- No ranking, scoring, API, UI, coverage-threshold, timer, or deployment-topology
  change.
- No synthetic, cached, or cross-date rows may be used to inflate coverage.
- No automatic trade, strategy-weight, watchlist, or portfolio mutation.
- No dependency or credential change.
- No removal or rewriting of historical money-flow artifacts.

## Requirements and acceptance criteria

- `REQ-001`: Money-flow collection must use a compatible Eastmoney route when
  the primary route is unavailable, without weakening fail-closed publication.
- `CFR-001`: The fallback must remain bounded to two known HTTPS endpoints and
  must not change the public artifact contract.

### `AC-MFF-001` — Primary route remains preferred

Given a non-empty primary response, when the adapter fetches one ticker, then it
returns the normalized primary rows and does not call the delayed route.

### `AC-MFF-002` — Failed or empty primary response falls back

Given either a primary request exception or a parsed primary response with no
rows, when the adapter fetches one ticker, then it tries the delayed route and
returns its non-empty normalized rows.

### `AC-MFF-003` — Complete outage remains fail-soft

Given both routes fail or return no rows, when the adapter fetches one ticker,
then it returns an unavailable or empty normalized result. The caller must not
publish fabricated rows.

### `AC-MFF-004` — Runtime route is usable

Given the deployed code and a bounded representative ticker sample on the 7F
test server, when collection runs, then at least `70%` of requested tickers
resolve, every row retains `source=eastmoney_push2his`, and the public API/UI
health checks remain successful.

## Implementation checklist

### `IMPL-001` — Fail-first adapter tests

- Modify `scripts/test_global_stock_data.py`.
- Add call-order assertions for primary-only and both fallback paths.
- Add an all-routes-fail assertion that proves the adapter does not raise.
- `TEST-001`: run `scripts/test_global_stock_data.py` before implementation and
  require the new scenarios to fail for the missing fallback.

### `IMPL-002` — Bounded endpoint fallback

- Modify `scripts/global_stock_data.py`.
- Define the two exact HTTPS endpoints in deterministic preference order.
- Parse each response before deciding whether to continue.
- Preserve `eastmoney_push2his_fflow`, `secid`, and existing row fields.
- `TEST-002`: rerun `scripts/test_global_stock_data.py` and
  `scripts/test_eastmoney_money_flow.py`.

### `IMPL-003` — Regression and runtime verification

- Run Analytics checks, Money Flow consumers, API artifact tests, compileall,
  whitespace checks, and complete `make test`.
- On the 7F test server, use a temporary reports directory for a bounded sample.
- Require sample coverage `>= 0.70` before any formal artifact refresh.
- After merge/deploy, refresh the formal Money Flow artifact once and rebuild
  Analytics checks. Abort if coverage is below `0.70`.
- `TEST-003`: verify formal artifact `publishable=true`, coverage `>= 0.70`,
  Analytics no longer emits `MONEY_FLOW_UNPUBLISHABLE`, and API/UI health pass.

## Verification commands

```bash
.venv/bin/python scripts/test_global_stock_data.py
.venv/bin/python scripts/test_eastmoney_money_flow.py
.venv/bin/python scripts/test_analytics_checks.py
.venv/bin/python scripts/test_ui_money_flow_api.py
.venv/bin/python scripts/test_rank_candidates.py
.venv/bin/python -m compileall -q api scripts ui
git diff --check
make test
```

If a listed test filename is absent, replace it with the repository's exact
Money Flow API test entry and record the substitution before implementation.

## Traceability

| Requirement | Acceptance criteria | Implementation | Tests |
|---|---|---|---|
| `REQ-001` | `AC-MFF-001`, `AC-MFF-002`, `AC-MFF-003`, `AC-MFF-004` | `IMPL-001`, `IMPL-002`, `IMPL-003` | `TEST-001`, `TEST-002`, `TEST-003` |
| `CFR-001` | `AC-MFF-001`, `AC-MFF-003`, `AC-MFF-004` | `IMPL-002`, `IMPL-003` | `TEST-002`, `TEST-003` |

## Risks and rollback

- The delayed endpoint is an external best-effort route. A compatible live
  sample is necessary but does not guarantee future availability.
- Falling back per ticker can add one failed request before each successful
  delayed request. Existing service timeouts remain authoritative; elapsed time
  must stay inside the current systemd/GitHub job windows.
- Roll back by reverting the feature commit and redeploying. Historical runtime
  artifacts must not be deleted or rewritten during rollback.

## Blocking review gate

- [x] The plan covers the observed Data Health failure without changing signal
  policy or public contracts.
- [x] Exact affected files, tests, runtime probe, abort conditions, and rollback
  are known.
- [x] The fallback route returns the same parsed row schema on the 7F host.
- [x] No unresolved data-integrity, credential, destructive-action, or scope
  blocker remains.

## Success metrics

- Deterministic adapter and consumer tests: `100%` pass.
- Complete `make test`: exit `0`.
- Bounded and formal 7F samples: coverage `>= 70%`, fabricated rows `0`.
- `MONEY_FLOW_UNPUBLISHABLE`: absent after formal refresh.
- Unexplained implementation scope drift: `0` files.

## Change history

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-16 | Initial evidence-grounded fallback plan. |
| v1.0 | 2026-08-16 | Accepted after a 10/10 live delayed-route probe completed in 24.08 seconds. |

## Next handoff

After the blocking review passes, hand this plan to implementation and verify
the actual diff against `IMPL-001` through `IMPL-003` before release.
