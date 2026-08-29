# PDM Journal

## 2026-08-29 - Reconcile Current Claims Before Selecting a Boundary

**Reconciliation pattern:** Treat historical plan status, current source,
checked-in contract, tests, and runtime-facing inventory as separate evidence
sources. A route-like row in an endpoint inventory is not implementation proof
without a matching route, model, OpenAPI path, client, and test.

**Product decision:** Choose the smallest stable value slice after separating
capability families. Analytics health/readiness is a fixed protected summary;
Data Health status is a later slice because its current read path may persist a
reconciliation. Risk Guard remains deferred because its ownership and
position-bearing semantics are materially different.

**Apply when:** A mature migration program has many historical phase documents
and the next target must be selected from residual bindings without treating
every local import as a defect.
