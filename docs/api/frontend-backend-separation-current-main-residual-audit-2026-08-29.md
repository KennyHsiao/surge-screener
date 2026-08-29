# Frontend/Backend Separation — Current-Main Residual Boundary Audit

## Document Info

| Field | Value |
|---|---|
| Version | v0.1 |
| Status | `AUDIT COMPLETE — TARGET SELECTED; IMPLEMENTATION NOT STARTED` |
| Baseline | `main@8e5e37ab1a252080f5066e4104cb5c5ce99d0fe3` |
| Date | 2026-08-29 |
| Owner / approver | Repository maintainer |
| Audience | Maintainers, API/UI engineers, security reviewers, and 7F operators |
| Selected target plan | `docs/superpowers/plans/2026-08-29-frontend-backend-analytics-data-health.md` |

## Audit Question and Scope

Reconcile the latest main after the public-read and Industry Roles private API
work, identify which residual UI/backend bindings are intentional, and select
the next bounded target. The maintainer explicitly excluded Risk Guard from the
first target and selected the more stable Analytics/Data Health family.

This is a repository/static audit. It does not claim external firewall, reverse
proxy, VPN, secret rotation, or 7F runtime facts that cannot be proved from the
repository. It changes no API, UI, data, provider, workflow, deployment, report,
pick, ledger, score, threshold, or schedule.

## Sources and Reconciliation Method

The audit triangulated:

- the Phase 6S-6U closure and endpoint/artifact inventory;
- current AST convergence and exact backend-boundary guards;
- current FastAPI routes, OpenAPI `1.23.0-draft`, models, and protected
  Industry Roles implementation;
- current UI direct imports, file/database reads, operational controls, and
  private API client;
- repository PR/issue state; no open issue supplies a conflicting target or
  acceptance contract.

Current focused checks pass:

- `scripts/test_ui_separation_convergence.py`: 4/4;
- `scripts/test_ui_backend_boundary.py`: 23/23.

## Status Matrix

| Capability | Current state | Confidence | Evidence / caveat |
|---|---|---|---|
| 54 accepted public presentation slices | Done | High | Endpoint inventory, clients, OpenAPI, and convergence guard. |
| Protected Industry Roles board/actions | Done | High | Bearer + loopback, fixed aggregate, ETag/idempotency and retirement records. The remaining UI import is not another broad state migration target. |
| Residual-boundary classification | Done for current main | High | Exact 61-symbol allowlist and retained-family inventory reproduced. |
| Analytics health summary API | Not started | High | No route, model, client, OpenAPI path, or route test exists. |
| Data Health terminal summary API | Not started | High | UI reads local run status; one Analytics read path can reconcile and persist interrupted state. |
| Risk Guard private boundary | Deferred by decision | High | Position redaction, ownership, freshness and reconciliation semantics remain unresolved. |

## Reproduced Current Baseline

| Measure | Current value | Existing ceiling |
|---|---:|---:|
| Direct `scripts.*` bindings | 61 | 61 |
| UI modules with a direct binding | 20 | 20 |
| UI modules importing `_shared` | 30 | 30 |
| UI `load_json` modules / calls | 14 / 20 | 14 / 20 |
| UI filesystem/database modules / calls | 10 / 19 | 10 / 19 |
| Accepted API-only presentation slices | 54 | 54 |

The direct-binding distribution remains `_candidate_controls` 6, `_shared` 7,
`ai_chat` 2, `analytics_db` 7, `ibkr_reconcile` 1, `industry_roles` 1,
`influencers` 3, `institution_portfolio` 1, `institutional_holdings` 1,
`momentum_options` 1, `options_cockpit` 8, `options_flow` 1,
`sector_rotation` 1, `theme_flow` 3, `today_decision` 2, `trade_state` 1,
`us_cot` 2, `us_options` 3, `watchlist_categorize` 3, and `x_sentiment` 7.

The residuals still belong to five intentional families: private account and
decision state, operational controls/diagnostics, live providers, writable
review/session state, and unstable/compatibility sources. The count is a
convergence ceiling, not a requirement to make every binding HTTP-backed.

## Documentation Drift Found

`docs/api/fastapi-endpoint-artifact-inventory.md` listed
`GET /api/v1/system/analytics-health` among endpoint candidates, while another
row correctly said Analytics health/status remained local/Internal. Current
source and generated/checked-in OpenAPI contain no such route. This audit
corrects the inventory to label Analytics as a **planned protected target**, not
an implemented public endpoint.

The Phase 6S-6U audit also freezes historical OpenAPI `1.21.0-draft`; current
main is `1.23.0-draft` because of later protected Industry Roles phases. The old
audit remains valid historical evidence for its 2026-08-06 checkpoint, not a
current route-surface receipt.

## Candidate Review

| Candidate | Stable bounded source | Security / semantic blockers | Verdict |
|---|---|---|---|
| Analytics health summary | Fixed `reports/analytics_checks/latest.json` | Must redact paths, raw checks/messages, ticker signals/evidence, performance details and operational actions | **Selected first slice** |
| Data Health terminal status | Fixed `reports/run_status/data-health-refresh.json` | Current Analytics UI read can persist an interrupted-status reconciliation; GET must be pure | Follow-up after side-effect ownership is separated |
| AI Chat sessions | No stable public ownership contract | Identity, ownership, retention/delete and model-context privacy | Defer |
| Watchlist / IBKR reconciliation | Private financial/account state | Authorization, provider isolation, concurrency and atomic writes | High risk; defer |
| Trade State / Risk Guard | Position-bearing decision state | Redaction, ownership, freshness and reconciliation | Explicitly not selected |
| Live providers / scheduler controls | Provider and mutation behavior | Credentials, rate limits, job authorization, audit and side effects | Not a normal read migration |

## Selected Boundary

The first implementation slice is a protected, loopback-only, bearer-authenticated
**Analytics health/readiness summary** derived from the fixed latest checks
artifact. It is an admin presentation DTO, not a public data endpoint.

Allowed initial projection:

- generated/as-of time and a non-path source identifier;
- overall status and recommended action from closed enums;
- exact PASS/WARN/BLOCK counts;
- bounded today-signal readiness status, publication boolean, recommended
  action, and bounded warning/block identifiers or counts;
- bounded warning codes needed to explain the summary.

Explicitly denied:

- `analytics_root`, `duckdb_path`, filesystem paths, environment values,
  credentials, logs, PIDs, commands, raw SQL, tables, refresh capability;
- raw check messages/values/thresholds, signal tickers/evidence, provider
  payloads, performance returns, and detailed next-action reasons;
- fallback to the migrated local summary after valid unavailable or client
  failure;
- any GET-time write, reconciliation, provider call, rebuild, or refresh.

The raw DuckDB catalog, table browser, safe SQL runner, detailed local checks,
refresh controls, and Data Health terminal state remain existing local/admin
siblings in this first slice. Therefore this first slice intentionally does not
promise an immediate reduction of the 61 direct-import ceiling; it creates a
strict private presentation boundary before a later convergence phase.

## Follow-Up Data Health Slice

Data Health status can be considered only after status ownership is explicit.
`ui/analytics_db.py` currently turns stale running state into interrupted state
and writes it back while loading. A future read endpoint must either consume a
producer-owned terminal record or use a pure projection that never persists.
It must not move PID checks, commands, logs, service controls, or refresh actions
into an ordinary GET.

## Decision and Next Handoff

The first target is Analytics health/readiness summary. Risk Guard remains out
of scope. No material target-choice blocker remains; the linked implementation
plan defines the contract, tests, rollout, rollback, and the separate Data
Health follow-up gate.

## Reviewers and Change History

Required reviewers: repository maintainer, API/security reviewer, UI reviewer,
and 7F operator for the later deployment receipt.

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-29 | Reproduced current residual baseline, corrected endpoint drift, and selected protected Analytics health summary. |

## Glossary

- **Presentation slice:** one bounded consumer read migrated to a strict API
  contract; it does not imply the entire page is API-only.
- **Protected read:** a fixed no-side-effect endpoint requiring the existing
  private workload credential and loopback peer/Host checks.
- **Pure projection:** deterministic validation/redaction that cannot write,
  invoke a provider, start a process, or repair source state.
