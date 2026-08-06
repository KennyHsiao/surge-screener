# Phase 2E Uvicorn Log Boundary Remediation Plan

**Status:** Implemented, verified, and independently reviewed

**Goal:** Keep unexpected schedules callback defects sanitized in both the HTTP
response and the real Uvicorn stderr/journal stream.

## Finding

The application-level `Exception` handler returns the intended RFC 9457 problem,
but Starlette's outer server-error middleware re-raises the handled exception.
Uvicorn therefore logs the original traceback and exception message after sending
the sanitized response. The existing `TestClient` assertion covers only the
structured application logger and cannot detect this runtime log leak.

This is a blocking completion finding for Phase 2E because callback exceptions can
contain source values, resolved paths, or other operational detail.

## Scope

### Modify

- `scripts/test_api.py`
  - Add a real-Uvicorn regression that injects a schedules resolver exception with
    a secret sentinel, requests the fixed route, and captures combined server logs.
- `api/main.py`
  - Catch unexpected downstream HTTP exceptions inside the existing loopback
    middleware, log only route template and exception type, and return the existing
    sanitized problem without re-raising to Uvicorn.
- `docs/superpowers/plans/2026-07-15-fastapi-schedules-phase2e.md`
  - Record the fresh-review finding and its remediation evidence.
- `.agents/PROJECT.md`, `.agents/judge.md`, and `.agents/builder.md`
  - Record the review and implementation result.

### Do not modify

- Routes, registry entries, DTOs, checked-in OpenAPI, source artifacts, result
  readers, deployment units, CORS, loopback policy, or dependency versions.

## Acceptance Criteria

- A real Uvicorn process serving an injected schedules resolver defect returns the
  exact HTTP 500 `application/problem+json` body and `Cache-Control: no-store`.
- Combined Uvicorn stdout/stderr contains the safe `unhandled API error` event but
  contains neither the injected sentinel nor a traceback.
- The application structured log still contains only the matched route template
  and exception class; it contains no exception message or source value.
- Expected artifact states remain HTTP 200 unavailable envelopes.
- `scripts/test_api.py`, the loader tests, `make test`, compile checks, and
  `git diff --check` pass.

## Execution

1. Add the real-Uvicorn regression and run it against the current implementation;
   retain the failing sentinel/traceback evidence.
2. Move the unexpected-exception conversion into the existing loopback middleware
   and remove the catch-all application exception handler.
3. Run the focused regression, the complete API suite, then the repository gates.
4. Compare the diff to this plan and independently review the changed boundary.

## Risk Review

- **Middleware order:** Use the already-outer loopback user middleware instead of
  adding another ordering-dependent middleware layer.
- **Accidental exception swallowing:** Catch only downstream HTTP request failures;
  lifespan/startup failures remain outside this middleware. The API has no streaming
  responses, so all route defects occur before response start.
- **Diagnostic loss:** Preserve the safe route template and exception type in the
  application log while intentionally omitting traceback and exception text.
- **Scope drift:** No runtime/deploy logging configuration is changed; the fix stays
  inside the application exception boundary.

## Pre-Implementation Gate

The affected files, verification path, and risk areas are known. The remediation
does not change the public contract and has no unresolved blocking issue.

## Completion Evidence

- The real-Uvicorn regression failed before the fix with the injected sentinel and
  full traceback present in combined server logs, then passed after the middleware
  change with the exact sanitized HTTP response and safe log event.
- `scripts/test_api.py`: 36/36 passed.
- `scripts/test_artifact_loader.py`: 14/14 passed.
- `scripts/test_dashboard_navigation.py`: 45/45 passed.
- Compile checks and `git diff --check` passed.
- Two independent post-fix reviews passed. Repeated real-Uvicorn runs (5x, 10x,
  and with `ResourceWarning` promoted to an error) remained clean with no child
  process or socket leak. A startup-sentinel probe confirmed lifespan exceptions
  still propagate outside the HTTP middleware.
