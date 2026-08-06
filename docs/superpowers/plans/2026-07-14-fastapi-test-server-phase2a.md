# FastAPI Test-Server Phase 2A Implementation Checklist

## Document Info

| Field | Value |
| --- | --- |
| Version | v1.6 |
| Status | Implemented and independently reviewed; live rollout pending normal `main` deployment |
| Author | Codex |
| Reviewer | Independent implementation and security reviewers |
| Audience | Maintainers of the test-server deployment |
| Related design | `docs/superpowers/plans/2026-07-14-fastapi-read-api.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |

## Goal

Deploy the existing fail-soft FastAPI process on the test server as a second
user-level systemd service without creating a new network exposure.

## Scope

In scope:

- Install and manage `surge-screener-api.service` through the existing deploy script.
- Bind Uvicorn only to `127.0.0.1:8000`.
- Validate the exact `/healthz` JSON contract during deployment.
- Use a testable exact-health validator and sequential API-first deployment gates.
- Read candidate artifacts from the existing shared candidate directory.
- Document SSH-tunnel access, diagnostics, and rollback.

Out of scope:

- LAN or public API access, `0.0.0.0`, Docker ports, Nginx, TLS, or VPN.
- Authentication, authorization, rate limiting, or CORS.
- Endpoint, response, artifact registry, or OpenAPI changes.
- Loading `.env`, Claude, Agent Reach, IBKR, or provider credentials.
- Manually changing the live server before the repository change is deployed.

## Requirements

- `REQ-201`: Every existing test-server deploy MUST install, enable, restart,
  and health-check the API service independently of Streamlit.
- `REQ-202`: Operators MUST be able to reach the loopback API through an SSH
  local-forward without changing the service bind address.
- `CFR-201`: Uvicorn MUST bind only to `127.0.0.1:8000`; API middleware and
  OpenAPI MUST remain loopback-only.
- `CFR-202`: The API process MUST start through `/usr/bin/env -i` with an exact
  allowlist: `HOME=/nonexistent`, `LANG=C.UTF-8`, `PATH=/usr/bin:/bin`,
  `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`, and the shared
  `SURGE_CANDIDATE_OUTPUT_DIR`. No other inherited value may reach Python.
- `CFR-203`: The service MUST restart on failure, avoid proxy/server/access-log
  trust surfaces, and set `NoNewPrivileges=true`, `PrivateTmp=true`,
  `ProtectSystem=strict`, `ProtectHome=read-only`, `RestrictSUIDSGID=true`,
  `LockPersonality=true`, an empty `CapabilityBoundingSet`, `UMask=0077`, and
  `RestrictAddressFamilies=AF_UNIX AF_INET`. It MUST use one worker,
  `Restart=on-failure`, `RestartSec=5`, and `TimeoutStopSec=15`.
- `CFR-204`: Missing or malformed artifacts MUST NOT affect process health or
  alter the Phase 1 fail-soft response contract.

## Acceptance Criteria

- `AC-P2A-001`: Given the unit template, when its `ExecStart` is inspected,
  then it contains `--host 127.0.0.1 --port 8000`, `--no-proxy-headers`,
  `--no-server-header`, `--no-access-log`, and `--workers 1`, and contains no
  alternate host, wildcard, file-descriptor, or Unix-socket bind.
- `AC-P2A-002`: Given the API unit, when its active directives are parsed, then
  `ExecStart` begins with `/usr/bin/env -i`; its assignments are an exact safe
  allowlist; and it contains no `EnvironmentFile`, `PassEnvironment`, systemd
  credential directive, Claude, Agent Reach, IBKR, chat, or provider setting.
- `AC-P2A-003`: Given a deploy, when both services restart, then Streamlit must
  pass its existing health check and API `/healthz` must return exactly
  `{"status":"ok","apiVersion":"v1"}` before deployment succeeds.
- `AC-P2A-004`: Given missing API artifacts, when `/healthz` is requested, then
  the service still returns HTTP 200 with the exact health payload.
- `AC-P2A-005`: Given a deployed main revision and a workstation SSH tunnel,
  when the operator requests the forwarded `/healthz`, then the request reaches
  the remote loopback service while LAN-address port 8000 remains unreachable.
- `AC-P2A-006`: Given any failed API install, reload, enable, restart, active-unit,
  MainPID, listener-ownership, or health check, when deployment exits, then it
  reports the API unit status and journal and returns nonzero.
- `AC-P2A-007`: Given the server's systemd 249, when the unit is verified, then
  every required hardening directive is accepted; successful rollout additionally
  proves the service starts with those directives active.
- `AC-P2A-008`: Given the API is unhealthy, when a deploy runs, then the existing
  Streamlit process is not restarted; API success is required before Streamlit
  restart, and Streamlit success is required before the script exits zero.

## Affected Files

Create:

- `deploy/surge-screener-api.service`
- `scripts/api_health_check.py`
- `scripts/deploy_service_gate.sh`
- `docs/api/test-server-loopback-api.md`
- `.agents/gear.md`

Modify:

- `scripts/deploy_test_server.sh`
- `scripts/test_deploy_artifacts.py`
- `.agents/gateway.md`
- `.agents/scribe.md`
- `.agents/builder.md`
- `.agents/PROJECT.md`

Do not modify:

- `api/`, `docs/api/quant-radar-v1.openapi.yaml`, `Dockerfile`,
  `docker-compose.yml`, or `.github/workflows/`.

## Implementation Checklist

### Tests First

- [x] `TEST-201` -> `AC-P2A-001`, `AC-P2A-002`, `AC-P2A-007`: parse the active
  systemd directives and tokenized `ExecStart`; reject wildcard, IPv6, FD, UDS,
  inherited-environment, credential, and missing-hardening alternatives.
- [x] `TEST-202` -> `AC-P2A-003`, `AC-P2A-006`, `AC-P2A-008`: test semantic
  exact-health variants; assert active/nonzero-MainPID checks, API-first ordering,
  listener PID ownership, lifecycle diagnostics, no early zero exit, and both
  services as success gates. A stale exact-health responder with another PID
  must fail and must not allow Streamlit restart.
- [x] Execute the service gate with stubbed lifecycle commands. Cover install,
  reload, enable, restart, inactive unit, zero/changed MainPID, stale listener,
  redirect/wrong health, Streamlit failure, and both-success paths.
- [x] `TEST-203` -> `AC-P2A-005`: add operator-document contract assertions.
- [x] Run `scripts/test_deploy_artifacts.py` and observe the new tests fail.

### Implementation

- [x] `IMPL-201` -> `AC-P2A-001`, `AC-P2A-002`, `AC-P2A-007`: add the hardened,
  clean-environment API unit with an exact loopback Uvicorn command.
- [x] `IMPL-202` -> `AC-P2A-003`, `AC-P2A-006`: install, enable, restart, and
  independently check the API service from the deploy script. Validate exact JSON
  through a pure helper, require active/nonzero MainPID, prove the sole
  `127.0.0.1:8000` listener belongs to that MainPID, then restart Streamlit.
- [x] Keep lifecycle orchestration in a standalone shell gate so failure paths
  can be executed with command stubs without running the full rsync/data deploy.
- [x] `IMPL-203` -> `AC-P2A-005`: document SSH tunnel, status, logs, and rollback.
- [x] Preserve the existing Streamlit health behavior and refresh timers.

### Verification

- [x] `bash -n scripts/deploy_test_server.sh scripts/deploy_service_gate.sh`
- [x] `.venv/bin/python scripts/test_deploy_artifacts.py`
- [x] `.venv/bin/python scripts/test_artifact_loader.py`
- [x] `.venv/bin/python scripts/test_api.py`
- [x] `.venv/bin/python scripts/test_dashboard_navigation.py`
- [x] `.venv/bin/python scripts/test_docker_runtime_contract.py`
- [x] `.venv/bin/python -m pip check`
- [x] `make test`
- [x] Validate the unit with test-server systemd 249 using a temporary file.
- [x] Start the tokenized unit Uvicorn command locally with an empty candidate
  directory; verify exact `/healthz` plus fail-soft ranked/scored responses.
- [x] Confirm a listener check reports only `127.0.0.1:<test-port>`.
- [x] `git diff --check`
- [x] Compare the actual diff with this affected-file list.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Accidental LAN exposure | Static unit test plus listener smoke test |
| API starts with deployment secrets | `/usr/bin/env -i`, exact allowlist, directive-aware tests |
| False-positive health | Parse and compare exact JSON from `/healthz` |
| API failure hidden by Streamlit success | Separate retry loop and API-specific diagnostics |
| Artifact files missing during deploy | Health remains process-only; endpoint behavior stays fail-soft |
| Unsupported systemd directive | Verify the unit against the server's systemd 249 before completion |

## Rollback

1. Run `systemctl --user disable --now surge-screener-api.service`.
2. Remove `$HOME/.config/systemd/user/surge-screener-api.service`, then run
   `systemctl --user daemon-reload` and `systemctl --user reset-failed`.
3. Revert the Phase 2A repository changes and redeploy the prior revision.
4. Verify Streamlit health. Phase 2A changes no data or artifact writers.

## Traceability

| Requirement | Acceptance | Test | Implementation |
| --- | --- | --- | --- |
| `REQ-201` | `AC-P2A-003`, `AC-P2A-006`, `AC-P2A-008` | `TEST-202` | `IMPL-202` |
| `REQ-202` | `AC-P2A-005` | `TEST-203` | `IMPL-203` |
| `CFR-201` | `AC-P2A-001` | `TEST-201` | `IMPL-201` |
| `CFR-202` | `AC-P2A-002` | `TEST-201` | `IMPL-201` |
| `CFR-203` | `AC-P2A-001`, `AC-P2A-006`, `AC-P2A-007`, `AC-P2A-008` | `TEST-201`, `TEST-202` | `IMPL-201`, `IMPL-202` |
| `CFR-204` | `AC-P2A-004` | Existing API tests | Existing Phase 1 implementation |

## Pre-Implementation Review

- User-selected boundary: **Phase 2A accepted**.
- Affected files, tests, rollback, and risk areas: **defined**.
- API/OpenAPI contract change: **none**.
- Live-server mutation before repository deployment: **none**.
- Repository-completion gate: static contracts, local process smoke, regression
  checks, and remote systemd syntax verification.
- Post-deployment gate: enabled/active unit, nonzero MainPID, exact remote health,
  listener owned by MainPID only on `127.0.0.1:8000`, exact remote health,
  working SSH forward, and failed LAN probe.
- Rollout is not complete until the post-deployment gate runs after an authorized
  main deployment; repository implementation may complete before that gate.
- Blocking issues: **none after two correction iterations**.
- Independent plan, test/security, and systemd 249 verdicts: **PASS**.

## Post-Implementation Review

- Actual Phase 2A files match the affected-file list; `.agents/builder.md` is
  included because the required implementation skill journal recorded the gate design.
- Independent deployment, security, and mutation-test reviews: **PASS**.
- Redirect, stale-listener, wrong-health, PID-transition, lifecycle-failure,
  retry, Streamlit fallback, section-placement, credential, wrapper-wiring, and
  early-success mutants are covered by executable or exact contract tests.
- Repository completion gates: **PASS**.
- Authorized live rollout has not been performed. Enabled/active service state,
  active systemd hardening, SSH forwarding, and the failed LAN probe remain the
  documented post-deployment gates.
- Blocking findings: **none**.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-07-14 | Initial Phase 2A checklist after user acceptance |
| v1.1 | 2026-07-14 | Added clean environment, exact hardening, lifecycle failure, rollback, and post-deploy gates |
| v1.2 | 2026-07-14 | Correlated exact health with the systemd MainPID listener |
| v1.3 | 2026-07-14 | Recorded final blocker-free implementation gate |
| v1.4 | 2026-07-14 | Added executable lifecycle harness, redirect rejection, and PID transition checks after implementation review |
| v1.5 | 2026-07-14 | Added retry, fallback, section-aware, credential, and unique-success-exit tests after mutation review |
| v1.6 | 2026-07-14 | Locked the complete CLI/helper/wrapper production wiring and recorded final PASS reviews |
