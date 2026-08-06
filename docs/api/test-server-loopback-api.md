# Test-Server Loopback API Operator Guide

| Field | Value |
| --- | --- |
| Status | Implementation guide; live rollout pending normal `main` deployment |
| Owner | Surge Screener maintainers |
| Reviewer | Test-server deployment maintainer |
| Audience | Maintainers operating the test-server API |
| Related plan | `docs/superpowers/plans/2026-07-14-fastapi-test-server-phase2a.md` |
| Related contract | `docs/api/quant-radar-v1.openapi.yaml` |

## Scope

Phase 2A runs the read-only FastAPI service on the test server at
`127.0.0.1:8000`. Operators may access it through an SSH local forward. The
service is not a LAN or public endpoint.

This guide covers rollout verification, tunnel access, health and artifact
requests, diagnostics, and rollback. Direct LAN access, reverse proxies, TLS,
authentication, CORS, and rate limiting remain outside Phase 2A.

## Authorization and prerequisites

Only a maintainer with access to the `antigravity` SSH host and the test
server's user-level systemd session may perform these procedures. The
workstation must have SSH and `curl`; post-deploy LAN verification also uses
`nc`.

All procedures are read-only except the rollback commands. The access and
verification commands are safe to repeat.

## Rollout

Phase 2A rolls out through the normal `main` deployment. Merge or push the
reviewed repository change to `main` and let the existing **Deploy Test
Server** workflow run `scripts/deploy_test_server.sh`. Do not install or expose
the API manually as part of a routine rollout.

The deploy must report success only after the API is active, its listener is
owned by the systemd `MainPID`, and `/healthz` matches the exact contract. The
API gate runs before the existing Streamlit restart and health gate.

## Access through an SSH tunnel

On the workstation, open the local forward and leave the process running:

```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:18000:127.0.0.1:8000 antigravity
```

In a second workstation terminal, check the forwarded API:

```bash
curl --noproxy '*' -fsS http://127.0.0.1:18000/healthz
```

Expected body:

```json
{"status":"ok","apiVersion":"v1"}
```

The health endpoint describes the API process. Missing, malformed, or
half-written optional artifacts do not make process health fail.

For example, read the ranked-candidates artifact through the same tunnel:

```bash
curl --noproxy '*' -fsS http://127.0.0.1:18000/api/v1/candidates/ranked
```

A present valid artifact returns HTTP 200 with `available: true`. A missing or
malformed artifact also returns HTTP 200, but with `available: false`,
`data: null`, and a stable fail-soft reason. Stop the tunnel with `Ctrl-C` when
finished.

## Post-deploy verification

Run the following checks after the normal `main` deployment finishes.

### 1. Check service state and health

Log in to the server:

```bash
ssh antigravity
```

Then run:

```bash
systemctl --user is-enabled --quiet surge-screener-api.service
systemctl --user is-active --quiet surge-screener-api.service
systemctl --user status surge-screener-api --no-pager
curl -fsS http://127.0.0.1:8000/healthz
```

Both systemd checks must exit zero. The health response must be exactly the JSON
object shown above.

### 2. Correlate the listener with the service process

Still on the server, record the systemd process and inspect port 8000:

```bash
main_pid="$(systemctl --user show --property=MainPID --value surge-screener-api.service)"
test "$main_pid" -gt 0
printf 'MainPID=%s\n' "$main_pid"
ss -H -ltnp 'sport = :8000'
```

Pass only when `ss` prints one listener, its local address is exactly
`127.0.0.1:8000`, and its `pid=` value equals `MainPID`. A missing, duplicate,
wildcard, IPv6, or differently owned listener fails the rollout check.

### 3. Confirm the LAN path remains closed

From a separate workstation on the same LAN, run this negative probe:

```bash
TEST_SERVER_LAN_IP=172.16.204.117
if nc -z -w 3 "$TEST_SERVER_LAN_IP" 8000; then
  echo "FAIL: API port is reachable over the LAN" >&2
  exit 1
else
  echo "PASS: API port is not reachable over the LAN"
fi
```

The probe must fail to connect. If it succeeds, treat the rollout as unsafe,
stop verification, capture the diagnostics below, and roll back.

### 4. Confirm tunneled access

Return to the workstation, establish the documented SSH tunnel, and repeat the
forwarded health request. This check must return the exact health body while
the LAN probe remains unsuccessful.

## Diagnostics

Run these commands on the test server:

```bash
systemctl --user status surge-screener-api --no-pager
journalctl --user -u surge-screener-api -n 160 --no-pager
systemctl --user show surge-screener-api.service \
  --property=ActiveState,SubState,MainPID,ExecMainStatus
ss -H -ltnp 'sport = :8000'
```

If a normal deployment fails its API gate, use the same status, journal, and
listener output to distinguish startup failure, a zero `MainPID`, an incorrect
listener owner, or a health-contract mismatch. Do not change the bind address
to bypass a failed check.

## Rollback

Rollback is appropriate when the service cannot pass its exact health or
listener gates, or when the LAN negative probe unexpectedly connects. On the
test server, stop and remove the user unit:

```bash
systemctl --user disable --now surge-screener-api.service
rm -f "$HOME/.config/systemd/user/surge-screener-api.service"
systemctl --user daemon-reload
systemctl --user reset-failed
```

Then revert the Phase 2A repository change and roll that revert out through the
normal `main` deployment. Finally, verify that the existing Streamlit service
remains healthy:

```bash
systemctl --user is-active --quiet surge-screener.service
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Phase 2A does not change artifact writers or stored artifact data, so rollback
does not require a data migration or restoration.

## Success criteria

- The normal `main` deployment completes successfully.
- `surge-screener-api.service` is enabled and active with a nonzero `MainPID`.
- The sole port 8000 listener is `127.0.0.1:8000` and belongs to that `MainPID`.
- `/healthz` returns the exact Phase 2A health object.
- The documented SSH tunnel reaches the API.
- The LAN negative probe cannot connect.

If any criterion fails, the rollout is incomplete. Keep the service loopback-only
and escalate to the test-server deployment maintainer with the status, journal,
and listener output.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-07-14 | Initial Phase 2A loopback API operator guide |
