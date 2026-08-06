# Phase 7E-7F Operating Evidence and Consumer Attestation Plan

Status: prerequisite publication explicitly authorized on 2026-08-06;
publication verification is in progress. No deployment, production-state
mutation, or external-consumer attestation has yet been performed.

## Authorized publication prerequisite

The owner authorized the recommended publish-before-evidence sequence. The
publication unit is the exact locally passing application/test tree needed by
the accumulated frontend/backend separation work, not every untracked file in
the workspace.

Include modified tracked application/configuration files plus the new `api/`,
`clients/`, API service unit, runtime/test scripts, UI support modules, API
plans/contracts, and UI/UX contract artifacts required by the registered full
test suite. Keep the tracked project activity ledger. Explicitly exclude
untracked skill journals, generated runtime report snapshots, the unrelated
trading-course source/notes, and the standalone Codex team guide. Scan the
selected paths for credentials and verify the committed tree in a fresh
detached worktree so omitted local files cannot make tests pass accidentally.

Publish the feature branch first, open a draft PR against `main`, require the
exact PR head to pass the complete suite, then merge through GitHub and verify
the resulting `origin/main` contains the same reviewed tree. Do not force-push,
commit credentials/runtime outputs, or run the deployment from the dirty local
working directory.

## Prior-phase review

Phase 7B-7D still matches its accepted plan. The focused store 10/10, admin
4/4, retirement 3/3, Money Flow 9/9, Universe 6/6, and deployment 18/18 suites
pass, and `git diff --check` is clean. The canonical runtime state remains
absent in the local workspace. No new implementation blocker or regression was
found in the previous phase.

## Objective and evidence boundary

- **Phase 7E — operating-window evidence:** publish the reviewed Phase 7B-7D
  build through the normal `main` deployment, prove API/UI service health,
  capture canonical/export/backup state at both ends of one complete 24-hour
  operating window containing at least one scheduled refresh, and complete a
  restore drill only in an isolated temporary copy.
- **Phase 7F — external-consumer attestation:** inspect the deployed user's
  systemd units/timers, crontab, container definitions, and application paths
  for repository-external readers or writers of the two legacy filenames;
  record each owner and disposition, including an explicit owner attestation
  when the result is `none`.

Out of scope: deploying an unpublished or dirty worktree, writing production
state during the restore drill, exposing credentials or command environments,
claiming evidence retroactively, archiving or deleting legacy files, changing
public/private API contracts, and Phase 7G archive design.

## Source and runtime preconditions

1. The complete reviewed frontend/backend separation stack, including
   `scripts/industry_role_store.py`, `scripts/industry_role_admin.py`, and the
   Phase 7D gate, is committed and merged to `origin/main`.
2. The exact target `main` SHA passes the complete repository test suite.
3. The private host is reachable either through the documented SSH route or an
   independently reviewed, read-only evidence workflow. The normal deployment
   workflow's self-hosted runner being online is not equivalent to operator
   access.
4. The deployment owner records the exact release SHA and operating-window
   start time before the first runtime observation.

These preconditions are fail-closed. A workflow dispatch against a `main` SHA
that lacks Phase 7B-7D is not a partial Phase 7E execution.

## Impact analysis

### Vertical map

- L0: GitHub `main` deployment workflow, the deployed release, shared
  `reports/industry_roles` state, and the two evidence documents.
- L1: API and Streamlit systemd services, refresh services/timers,
  `scripts/industry_role_admin.py`, and legacy export/backup artifacts.
- L2: Money Flow and Universe scheduled outputs, deployment health gates, and
  the Phase 7D retirement decision.
- L3: any repository-external script or operator process discovered by the
  host inventory. Its disposition is evidence, not assumed migration scope.

The change crosses GitHub, the private deployment host, API/UI services,
schedulers, and shared filesystem state. No runtime contract changes are
planned. The expected repository surface is 3-5 evidence/documentation files;
runtime actions affect one deployment and read one shared state directory.

### Horizontal consistency

- Deployment must use `.github/workflows/deploy_test_server.yml` and
  `scripts/deploy_test_server.sh`, matching the existing main-only rollout.
- Runtime inspection reuses the strict machine-readable admin CLI; no second
  parser or automatic dual-writer is introduced.
- Restore verification uses a fresh `mktemp -d` copy and never passes
  production paths to `restore-backup --apply`.
- Consumer inventory records paths and ownership without copying environment
  values, tokens, private command lines, or file contents into evidence.

### Risk score

`scope 7*0.30 + breaking 2*0.25 + pattern 2*0.20 + coverage 4*0.15 +
reversibility 4*0.10 = 4.0/10`, medium. The principal risks are deploying the
wrong source authority, mutating production during a drill, incomplete host
inventory, and treating an elapsed clock as proof without scheduled activity.
The main-only source gate, temporary-copy drill, start/end observations, and
explicit owner attestation are required mitigations.

## Execution plan after preconditions pass

### Phase 7E

1. Re-run the full suite on the exact intended `main` SHA and record the SHA.
2. Dispatch the normal Deploy Test Server workflow for that SHA. Require the
   deployment job, API service gate, and Streamlit gate to pass.
3. Capture start evidence: service active states, `/healthz`, admin
   `status --require-canonical`, `export-legacy` preview, backup status, and
   absence of a pending/invalid export. Do not record the bearer credential.
4. Copy taxonomy, canonical state, backup, and compatibility files into a
   private temporary directory. Run restore preview there, apply with the exact
   previewed ETag, reopen it, verify predicted revision/ETag, and remove only
   that explicit temporary directory.
5. Observe 24 hours including at least one scheduled refresh. Record relevant
   service/timer results and any Industry Roles state/export transitions.
6. Capture the same status and health evidence at the end. Any service failure,
   invalid canonical/backup, pending export, or unexplained revision change
   fails Phase 7E and retains `HOLD`.
7. Write `docs/api/industry-role-operating-window-evidence.md` with timestamps,
   release SHA, redacted commands/results, restore-drill result, and verdict.

### Phase 7F

1. Search repository production code with the existing static retirement gate.
2. On the deployed host, inspect user systemd service/timer definitions,
   `crontab -l`, active application/container configuration, and bounded
   application roots for the exact legacy filenames. Do not scan or publish
   credential contents.
3. For every match outside the deployed repository, record owner, executable or
   path, read/write behavior, schedule, migration status, and keep/archive
   disposition.
4. The single deployment owner signs a dated `none found` attestation if the
   bounded inventory finds no external consumer. Absence of a signed result is
   `unknown`, not `none`.
5. Write `docs/api/industry-role-external-consumer-attestation.md` and update the
   Phase 7D gate. Phase 7F passes only when every match has a disposition and
   the owner attestation is explicit.

## Verification matrix

1. Phase 7B-7D focused tests and complete `make test` pass on the deployed SHA.
2. GitHub deployment run conclusion is success and records the same SHA.
3. API/UI service gates and `/healthz` pass at both window boundaries.
4. Start/end admin JSON is schema-valid, canonical is valid, and export is
   neither pending nor invalid.
5. Temporary restore apply exactly matches preview and production state hashes
   remain unchanged by the drill.
6. At least one scheduled refresh occurs inside the timestamped 24-hour window.
7. Static repository owner set remains exact; bounded host inventory and signed
   owner attestation cover all external consumers or explicitly state none.
8. Retirement remains `HOLD` until all Phase 7E and 7F evidence is complete.

## Rollback and abort criteria

Abort immediately if the workflow checks out a different SHA, deployment
health fails, canonical state is invalid, export is pending, the drill resolves
to a production path, or an unknown writer is found. Do not repair evidence by
editing runtime files. Redeploy the last known-good main SHA through the same
workflow when service rollback is required, preserve the shared canonical and
backup state for incident review, and keep both legacy files supported.

## Blocking-issue review

- **Iteration 1 — source authority and reachability:** local `HEAD` and local
  `main` are `a426ed1`, while current `origin/main` is `e72bf6e`; SSH to
  `antigravity` timed out. Resolution attempt: fetch remote main and inspect the
  documented deployment authority without changing the worktree.
- **Iteration 2 — workflow alternative:** the self-hosted runner is online, but
  `origin/main` does not contain the Industry Roles store, admin CLI, or
  retirement gate. Dispatching it would deploy an older build. Resolution
  attempt: reject stale workflow deployment and evaluate manual deployment.
- **Iteration 3 — manual/evidence alternative:** the current feature worktree
  contains a large accumulated set of modified and untracked user files.
  `rsync --delete` from it would bypass the main-only rollout, mix unrelated
  scope, and make release provenance unverifiable. Without host access, the
  operating window and external-consumer inventory also cannot be observed.
  Resolution: stop before execution; do not invent evidence or attest `none`.

The same blocker remains after three reviews. Verdict: **NO-GO until the
reviewed stack is published to `origin/main` and the private host is reachable
for evidence collection.**

## Following queue

- **Phase 7G — recoverable archive proposal:** only after 7E and 7F pass,
  specify archive destination, permissions, retention, verification, and
  rollback. It still does not authorize deletion.
- **Phase 7H — archive canary and rollback drill:** after separate acceptance,
  validate a copied archive against the committed manifest while leaving live
  compatibility files untouched.
- **Phase 7I — final retirement decision:** use dated 7E-7H evidence for a new
  `READY`/`HOLD` review; any destructive action requires separate authority.
