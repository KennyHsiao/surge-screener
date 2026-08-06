# Phase 6S-6U Public-Read Convergence Closure

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6s-6u-plan.md`

## Scope and confidence

This audit closes the fixed public presentation-read stage. It parses every
`ui/*.py` module, reconciles the exact shrinking allowlist, checks deployment
ownership, and defines the entry gate for a later private or writable boundary.
It does not add an endpoint, increment the API version or slice count, or change
production API/UI/provider/writer/deployment behavior.

Confidence is **high** for the static source and repository topology findings.
Runtime network exposure outside this repository (firewall, reverse proxy,
VPN, or hosting access policy) is unknown and is therefore not inferred.

## Phase 6S — post-6R baseline

The reproducible post-6R baseline is:

| Measure | Current | Convergence ceiling | Evidence |
| --- | ---: | ---: | --- |
| Direct `scripts.*` bindings | 61 | 61 | AST scan and `LEGACY_SCRIPT_IMPORTS` |
| UI modules with a direct binding | 20 | 20 | AST scan of `ui/*.py` |
| UI modules importing `_shared` | 30 | 30 | relative-import AST scan |
| UI modules calling `load_json` | 14 / 20 calls | 14 / 20 calls | call AST scan |
| UI modules with direct filesystem/database-style calls | 10 / 19 calls | 10 / 19 calls | `open/read/write/glob/iterdir/connect` AST scan |
| Accepted API-only presentation slices | 54 | 54 | endpoint inventory and user guide |

The 61 direct bindings remain distributed as follows. Counts are unique
allowlisted symbols, not dynamic call counts.

| UI module | Count | Retained boundary family |
| --- | ---: | --- |
| `_candidate_controls.py` | 6 | Operational controls and diagnostics |
| `_shared.py` | 7 | compatibility reads, private aggregates, and Live providers |
| `ai_chat.py` | 2 | Writable review and session state; private model context |
| `analytics_db.py` | 7 | private database/diagnostics/provider controls |
| `ibkr_reconcile.py` | 1 | Private account and decision state plus broker capability |
| `industry_roles.py` | 1 | Writable review and session state; multi-file mutation |
| `influencers.py` | 3 | provider and editable roster behavior |
| `institution_portfolio.py` | 1 | Live providers: SEC EDGAR |
| `institutional_holdings.py` | 1 | Live providers: holdings lookup |
| `momentum_options.py` | 1 | provider cache policy |
| `options_cockpit.py` | 8 | private trade state, providers, and strategy recording |
| `options_flow.py` | 1 | Live providers: ticker drill |
| `sector_rotation.py` | 1 | private/local AI generation; fixed drill already migrated |
| `theme_flow.py` | 3 | providers, refresh, and mutation controls |
| `today_decision.py` | 2 | quote provider and Private account and decision state |
| `trade_state.py` | 1 | private cross-source decision aggregate |
| `us_cot.py` | 2 | auth, provider, generation, and operational log |
| `us_options.py` | 3 | Live providers: IV/options data |
| `watchlist_categorize.py` | 3 | private IBKR data, providers, and direct writes |
| `x_sentiment.py` | 7 | credentials/auth, providers, analysis, and writers |

The retained transitive/local families are intentionally classified as:

1. **Private account and decision state** — reconciliation, positions,
   watchlists, ledger, Risk Guard, Trade State, and account-bearing aggregates.
2. **Operational controls and diagnostics** — commands, PIDs, run status,
   auth state, refresh/rebuild controls, errors, and service diagnostics.
3. **Live providers** — yfinance, options, quote, EDGAR, IBKR, COT, social,
   analyst, theme, sector, and model execution.
4. **Writable review and session state** — Industry Roles, roster edits,
   watchlists, AI chat sessions, approvals, deletes, and generated reports.
5. **Unstable or compatibility-only sources** — missing producer/schema,
   N+1 local IV grids, legacy X picks, and broad retrospective raw bundles.

What was not found: no second stable, fixed, bounded public presentation read
that can move without identity, concurrency, producer, or new-contract work.
Static analysis cannot prove external firewall/proxy policy or runtime provider
side effects, so those claims remain outside this audit.

## Phase 6T — convergence guard

`scripts/test_ui_separation_convergence.py` is the summary guard. It:

- enforces ceilings rather than exact summary counts, so later migrations may
  shrink the inventory while any growth fails;
- delegates exact `scripts.*` symbol parsing to
  `test_ui_backend_boundary.py`, which remains the authoritative allowlist;
- self-tests that a smaller synthetic inventory passes and a larger one fails;
- checks the five retained-family classifications and explicit deny families;
- freezes the 54-slice/OpenAPI `1.21.0-draft` receipts and the current
  loopback API + Streamlit/API service dependency topology.

The guard does not encode private DTOs or future endpoints. It therefore cannot
turn a deferred private source into an accidental public contract.

Explicitly denied without a separately accepted authenticated design:
paths/globs, arbitrary SQL or tables, positions/account records, credentials,
environment values, logs/prompts/chat sessions, provider execution, job controls,
approval/reconcile/refresh actions, and writes.

## Phase 6U — private-boundary entry criteria

Before any private read or mutation plan can be accepted, all of these inputs
must be explicit:

### Identity and authorization

1. **deployment audience:** single operator on a private host, trusted LAN/VPN,
   internet-facing users, or machine/service callers;
2. **identity:** which human, OS process, workload, or device is the principal;
3. authentication lifecycle: login/bootstrap, expiry, revocation, rotation,
   logout, failure behavior, and secret storage;
4. **authorization:** roles, resource ownership, object-level checks, action
   scope, and default-deny behavior;
5. browser boundary: cookie/session policy, CSRF defense, CORS allowlist,
   origin/Host/proxy trust, and session fixation protection;
6. audit policy: actor/action/resource/result, redaction, retention, access,
   and correlation without recording secrets or private payloads.

### Revisioned mutation and recovery

1. stable resource IDs and a canonical **revision/ETag**;
2. conditional mutation through `If-Match`, with explicit stale-write conflict
   behavior and no last-write-wins fallback;
3. an **idempotency** key and replay result for every non-safe action;
4. one **atomic** commit across all affected files or one transactional store;
5. bounded lock/lease ownership and timeout behavior;
6. temp-file cleanup, interrupted-commit detection, and **crash recovery**;
7. append-only audit event, backup/restore proof, and operator conflict UX.

### Candidate ranking after the gate

| Candidate | Value | Blocking prerequisites | Earliest pilot verdict |
| --- | --- | --- | --- |
| Industry Roles review | Narrow approve/reject/defer workflow | identity/authorization, two-file atomicity, ETag/If-Match, idempotency, audit/recovery | Best first mutation candidate after decisions |
| AI chat sessions | Clear per-session resources | user ownership, retention/delete policy, model-context privacy, audit redaction | Defer |
| Watchlist/reconciliation | High user value | financial-data authorization, broker/provider isolation, atomic writes | High-risk; defer |
| Analytics/Data Health | Operational value | fixed capability allowlist, admin role, query/resource limits, audit | Admin-only; defer |
| Trade State/Risk Guard | Decision value | position redaction, ownership, freshness, reconciliation semantics | High-risk; defer |

No private candidate is selected by this audit. That is a material product and
security decision, not an implementation default.

## Blocking review and verdict

- **Iteration 1:** rejected treating every residual binding as a separation
  defect. The retained-family map distinguishes public presentation, private,
  provider, operational, mutation, and unstable/compatibility behavior.
- **Iteration 2:** rejected an exact-count-only guard because it would block
  legitimate shrinkage. Ceilings reject growth; the separate allowlist remains
  exact symbol authority.
- **Iteration 3:** reviewed a Phase 6V-6X private pilot. The repository exposes
  Streamlit on `0.0.0.0:8501` in systemd and maps port 8501 in Compose, while
  FastAPI has only loopback peer/Host enforcement and no reusable user identity
  or object authorization middleware. External proxy/firewall policy is not in
  the repository. Selecting an auth method by assumption is therefore
  **BLOCKED** pending the deployment-audience and identity direction.

Verdict: **PASS** for Phase 6S-6U audit/static closure. **BLOCKED** for Phase
6V-6X production/private implementation until the user supplies the material
identity/authorization choice.

## Verification receipt

Passed: convergence guard 4/4, exact backend boundary 23/23, navigation 66/66,
deployment 18/18, Docker 11/11, UX contract 19/19, Python 3.10
AST/compile/tabnanny/static checks, documentation checks, `git diff --check`,
and complete `make test` with exit code 0. No production API/UI, provider,
writer, source, dependency, deployment, API version, or slice-count change was
made in this audit batch.
