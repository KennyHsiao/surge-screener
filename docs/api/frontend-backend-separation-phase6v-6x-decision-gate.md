# Phase 6V-6X Private-Boundary Decision Gate

- **Status:** resolved and implemented — single human operator on a private
  host; closure is recorded in `frontend-backend-separation-phase6v-6x-plan.md`
- **Date:** 2026-08-06
- **Parent:** `frontend-backend-separation-phase6s-6u-audit.md`

## Phase 6V — deployment audience

Repository evidence does not identify one safe audience. The systemd dashboard
binds `0.0.0.0:8501`; Compose publishes 8501 through the API network namespace;
the FastAPI service itself stays on `127.0.0.1:8000`. No repository-owned
reverse proxy, VPN/firewall authority, or user-login perimeter was found.

One deployment audience must be selected before design:

1. single human operator on a private host;
2. multiple authenticated humans on LAN/VPN/internet;
3. machine/workload callers only; or
4. a documented combination with separate trust zones.

## Phase 6W — identity and authorization direction

| Audience | Plausible direction | Required evidence before acceptance |
| --- | --- | --- |
| Single private operator | host/reverse-proxy authenticated session with API remaining loopback | proof of exclusive access, session boundary, CSRF behavior, secret rotation |
| Multiple humans | OIDC-capable perimeter plus backend-verified identity/roles/ownership | IdP, issuer/audience, role/resource model, logout/revocation, proxy-header trust |
| Workloads only | mTLS or workload identity with narrow service scopes | certificate/identity issuer, rotation, audience, replay protection, audit principal |

Gateway rules require asking before proposing a new auth method. Codex/X login
state is provider authentication and cannot be reused as application-user
identity or authorization.

## Phase 6X — private pilot

The user selected a single human operator on a private host. Phase 6V-6X will
therefore pilot a protected Industry Roles read projection with a separate
Streamlit-to-API service credential. Approve/reject/defer remains local until a
later plan defines revision/ETag, `If-Match`, idempotency, atomic two-resource
commit, locking, audit, backup/restore, crash recovery, and conflict UX.

This decision gate itself made no production change. The accepted scope was
implemented and verified in the successor plan; private mutations remain gated
on its Phase 6Y-7A queue.
