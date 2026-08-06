# UX-1B Task 3 Evidence API Execution Note

## Document Info

| Field | Value |
| --- | --- |
| Version | `v0.2-draft` |
| Status | Non-authoritative execution note; not an accepted plan |
| Date | 2026-07-17 |
| Author | Codex (Lens/Scribe) |
| Reviewer | UX-1B recovery implementer and evidence reviewer |
| Audience | Implementer of `scripts/ui_ux_evidence.py` and `scripts/ui_ux_browser_worker.py` |
| Governing documents | [`quant-radar-ui-v2-ux1b-recovery-architecture.md`](quant-radar-ui-v2-ux1b-recovery-architecture.md), [`2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md`](../superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md) |

This note resolves Task 3 interface ambiguity. It does not amend, replace, or
declare acceptance of either governing document. A conflict is resolved in
favor of the governing documents.

## Scope and Non-goals

In scope:

- the public Python API of `scripts/ui_ux_evidence.py`;
- finalizer-only `passed` authorization;
- canonical render-sidecar projection required before browser-worker capture;
- bounded browser-worker request and response records;
- descriptor-authenticated artifact and lifecycle behavior;
- the minimum tests and implementation order needed to make Task 3 executable.

Out of scope:

- production selector edits;
- Task 4 migration-comparator implementation beyond its interface boundary;
- runner integration, capture-stack freezing, or evidence capture;
- changes to either accepted document.

## Glossary

- **closure**: all coordinator observations required before a run may pass.
- **grant**: a process-local, one-shot authorization bound to one lifecycle and
  one validated closure.
- **canonical sidecar**: an exact-key, deterministic non-color render document.
- **staged**: child output awaiting coordinator authentication; never `passed`.
- **terminal**: one of `passed`, `failed`, `dependency_unavailable`,
  `invalid_data`, or `interrupted`.

## Normative Requirements

- **CFR-001:** Only `finalize_terminal_manifest()` may write
  `status: "passed"`.
- **CFR-002:** A caller-supplied boolean or mapping cannot authorize
  `passed`.
- **CFR-003:** Worker JSON is canonical NDJSON with exact keys, a byte
  limit per record, an exact record count, and required EOF.
- **CFR-004:** The canonical render schema and normalization execute
  before the worker is treated as implemented.
- **CFR-005:** Artifact content, identity, and digest decisions use retained
  directory and leaf descriptors. They never use `Path.resolve()` or replace
  that retained authority with a second leaf lookup. CFR-008's additional
  dirfd-relative open only proves that the current pathname still matches the
  same frozen contract while the retained content descriptor remains open.
- **CFR-006:** Every failure message persisted in evidence is redacted
  and at most `2,048` UTF-8 bytes.
- **CFR-007:** `materialize_authorized_terminal_manifest()` may return the
  exact authorized `passed` document for export comparison, but it must not
  write a manifest, consume the grant, release capture authority, or expose
  the opaque closure.
- **CFR-008:** Finalization retains one exact descriptor-authenticated artifact
  set through publication. After its last byte/inode rehash, it must resolve
  every manifest and capture path again before publication while retaining at
  most one additional leaf descriptor at a time.
- **CFR-009:** Immediately after each successful capture verification, formal
  runners must detach a deep-copied plain artifact payload for failure
  checkpointing. Opaque capture objects remain success-only authority and must
  never be serialized after a finalizer has revoked them.

## Public Python API

### Errors and constants

```python
class EvidenceContractError(RuntimeError): ...
class DependencyUnavailable(EvidenceContractError): ...
class InvalidEvidence(EvidenceContractError): ...

EVIDENCE_SCHEMA = "quant-radar-ui-ux-evidence/v1"
RENDER_SCHEMA = "quant-radar-ui-ux-render/v1"
CONTROL_CATALOG_SCHEMA = "quant-radar-ui-ux-control-catalog/v1"
WORKER_REQUEST_SCHEMA = "quant-radar-ui-ux-browser-request/v1"
WORKER_RESPONSE_SCHEMA = "quant-radar-ui-ux-browser-response/v1"

MAX_WORKER_REQUEST_BYTES = 64 * 1024
MAX_WORKER_RESPONSE_BYTES = 256 * 1024
MAX_RENDER_SIDECAR_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_AUTHENTICATED_ARTIFACT_BYTES = MAX_PNG_BYTES
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_ERROR_BYTES = 2 * 1024
```

An oversize record or artifact is `invalid_data`. The implementation must not
increase a limit dynamically. A limit change requires a reviewed document and
test update.

### Descriptor data models

```python
@dataclass(frozen=True, slots=True)
class PathComponentContract:
    name: str
    device: int
    inode: int
    owner_uid: int
    mode: int

@dataclass(frozen=True, slots=True)
class ArtifactLeafContract:
    name: str
    device: int
    inode: int
    owner_uid: int
    mode: int
    link_count: int
    size: int
    sha256: str

@dataclass(frozen=True, slots=True)
class ArtifactContract:
    relative_path: str
    parents: tuple[PathComponentContract, ...]
    leaf: ArtifactLeafContract

class AuthenticatedArtifact:
    descriptor: int
    contract: ArtifactContract
    # Context manager; closes exactly once.
```

Required functions:

```python
freeze_artifact_contract(
    root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    max_bytes: int = MAX_AUTHENTICATED_ARTIFACT_BYTES,
) -> ArtifactContract

open_authenticated_artifact(
    root_fd: int,
    contract: ArtifactContract,
) -> AuthenticatedArtifact

copy_authenticated_artifact(
    artifact: AuthenticatedArtifact,
    output_dir_fd: int,
    output_name: str,
) -> dict[str, object]

verify_capture_artifacts(
    root_fd: int,
    record: Mapping[str, object],
    *,
    expected_owner: int,
) -> dict[str, object]
```

Relative paths reject empty, absolute, backslash, `.`, `..`, empty-component,
and trailing-slash forms. Each parent opens with directory and no-follow flags.
Each parent must match its frozen device, inode, owner, type, and mode. The leaf
opens no-follow and must be an owned, one-link regular file. Copying reads from
that leaf descriptor, writes an exclusive coordinator-owned temporary leaf,
rehashes and restats the source descriptor, then atomically replaces the final
leaf. A failed recheck removes the temporary leaf and leaves no accepted output.

### Lifecycle and finalization grant

```python
class ManifestLifecycle:
    def __init__(
        self,
        output_dir_fd: int,
        manifest_name: str,
        *,
        base_document: Mapping[str, object],
    ) -> None: ...

    def start(self) -> dict[str, object]: ...
    def mark_finalizing(self, updates: Mapping[str, object]) -> dict[str, object]: ...
    def mark_terminal(
        self,
        status: Literal[
            "failed", "dependency_unavailable", "invalid_data", "interrupted"
        ],
        updates: Mapping[str, object],
    ) -> dict[str, object]: ...
    def capture_failures(self) -> ContextManager[None]: ...

class ValidatedSuccessClosure: ...
class SuccessFinalizationGrant: ...

authorize_success_closure(
    lifecycle: ManifestLifecycle,
    *,
    validated_closure: ValidatedSuccessClosure,
) -> SuccessFinalizationGrant

materialize_authorized_terminal_manifest(
    lifecycle: ManifestLifecycle,
    *,
    grant: SuccessFinalizationGrant,
) -> dict[str, object]

finalize_terminal_manifest(
    lifecycle: ManifestLifecycle,
    *,
    grant: SuccessFinalizationGrant,
) -> dict[str, object]
```

`ManifestLifecycle.mark_terminal()` must reject the string `passed`, even when
the updates contain `readyForPassed: true`. Grant issuance validates the exact
capture ID set, source start/end equality, calibration, app/browser exit and
quiescence, authenticated artifacts, provider and mutator equality, zero
prohibited counters, comparator closure, and manifest schema.

The module retains a locked process-local registry. Each registry row binds the
exact grant object identity to the lifecycle directory device/inode, run ID,
current manifest SHA-256, and canonical closure SHA-256. Finalization rejects a
copied, reconstructed, wrong-lifecycle, stale-manifest, or reused grant. The
exact registered object is consumed once before the atomic `passed` commit.
`repr(grant)` must not reveal its token.

The materializer and finalizer share one private grant/lifecycle validation
path. The materializer is repeatable while the grant remains live and returns
an independent deep copy without changing the lifecycle or manifest. The
finalizer revalidates after export, consumes the exact grant and capture
authorities exactly once, and remains the only function allowed to publish
`status: "passed"`.

The finalizer's first manifest/PNG/sidecar/supplement descriptor set remains
open until the atomic manifest replacement completes. A second current-path
pass runs only after every retained descriptor has received its final hash and
inode check. Each second-pass path is opened, fully authenticated, and closed
before the next path is opened. Publication is forbidden unless that entire
bounded pass succeeds. This preserves the retained-inode and late-rename
checks without exceeding the 256-descriptor soft limit for the exact 81-page
profile.

Formal snapshot and theme runners keep two representations after verification:
opaque `VerifiedCaptureArtifacts` for comparator/closure/finalizer authority,
and detached plain dictionaries for a terminal failure's `partialArtifacts`.
The plain snapshot is taken while provenance is live; failure handling never
re-materializes an opaque capture after finalizer cleanup.

Allowed transitions are:

```text
new -> running -> finalizing -> passed
               |            -> failed | dependency_unavailable | invalid_data | interrupted
               `-----------> failed | dependency_unavailable | invalid_data | interrupted
terminal -> no transition
```

`record_stale_nonterminal()` authenticates a bounded `running` or `finalizing`
manifest and writes a separate `stale_nonterminal` record. It never rewrites the
source manifest and never makes it referenceable.

### Success closure and comparison seams

```python
validate_success_closure(
    document: Mapping[str, object],
    *,
    lifecycle: ManifestLifecycle,
    expected_fixture_entrypoint: str,
    expected_capture_stack_digest: str,
    expected_source_digest: str,
    expected_app_origin: str,
    calibration_attestation: object,
    comparator_attestation: object,
) -> ValidatedSuccessClosure

record_stale_nonterminal(
    source_dir_fd: int,
    manifest_name: str,
    recovery_dir_fd: int,
    recovery_name: str,
    *,
    expected_owner: int,
) -> dict[str, object]

compare_control_migration(
    *,
    before_pages: Mapping[str, object],
    after_pages: Mapping[str, object],
    before_controls: Mapping[str, object],
    after_controls: Mapping[str, object],
    catalog: Mapping[str, object],
) -> dict[str, object]
```

`validate_success_closure()` returns an opaque, process-local capability. It
cannot be iterated, copied, reconstructed, or used by itself to grant
finalization. `compare_control_migration()` is also a pure Task 4 seam. The CLI
must authenticate terminal manifests and artifacts before projecting inputs to
that seam.

## Canonical Render Sidecar First

The worker must project raw DOM/AX observations into this exact top-level shape
before writing a sidecar:

```json
{
  "schemaVersion": "quant-radar-ui-ux-render/v1",
  "captureId": "knowledge-graph/mobile",
  "case": "knowledge-graph",
  "viewport": {"name": "mobile", "width": 390, "height": 844},
  "identity": {"route": "/knowledge-graph", "callable": "knowledge_graph.render"},
  "readiness": {},
  "stableState": {},
  "providerCounters": {},
  "mutatorCounters": {},
  "prohibitedCounters": {},
  "runtimeProjection": {},
  "nodes": []
}
```

Every node has exactly `id`, `parentId`, `flowScope`, `boundaryId`,
`rootSelector`, `role`, `name`, `text`, `state`, `visible`, and `bounds`.
`bounds` has exactly `x`, `y`, `width`, and `height`, normalized to integer CSS
pixels at device scale factor `1`.

Normalization is projection, not arbitrary key deletion. It omits only capture
timestamps, random request/run IDs, Playwright/backend node IDs, and raw owned
absolute paths. An allowed owned path becomes one of `$SOURCE_ROOT`,
`$APP_ROOT`, or `$BROWSER_ROOT` plus a validated relative suffix. Any other
absolute path is invalid. Content, decisions, counters, roles, names, text,
state, visibility, geometry, route, callable, case, and viewport are never
removed. Output is UTF-8 canonical JSON: sorted keys, compact separators, no
NaN/Infinity, and no trailing whitespace.

## Bounded Browser-worker Protocol

The protocol is canonical NDJSON. Each request describes exactly one capture:

```json
{
  "schemaVersion": "quant-radar-ui-ux-browser-request/v1",
  "captureId": "knowledge-graph/mobile",
  "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
  "route": "/knowledge-graph",
  "case": "knowledge-graph",
  "viewport": {"name": "mobile", "width": 390, "height": 844},
  "appOrigin": "http://127.0.0.1:43129",
  "staging": {
    "png": "staging/knowledge-graph/mobile.png",
    "renderSidecar": "staging/knowledge-graph/mobile.render.json"
  }
}
```

All keys are required and no extra key is accepted. The entrypoint is
mirror-relative and catalog-allowlisted. The origin is exact HTTP IPv4 loopback
with the assigned port and no userinfo, path, query, or fragment. Staging paths
are browser-root-relative component paths. Case, route, viewport, and capture ID
must match one frozen catalog row.

One response corresponds to one request:

```json
{
  "schemaVersion": "quant-radar-ui-ux-browser-response/v1",
  "captureId": "knowledge-graph/mobile",
  "status": "staged",
  "staging": {
    "png": "staging/knowledge-graph/mobile.png",
    "renderSidecar": "staging/knowledge-graph/mobile.render.json"
  },
  "error": null
}
```

Worker status is one of `staged`, `failed`, `dependency_unavailable`,
`invalid_data`, or `interrupted`; `passed` is forbidden. Error is `null` for
`staged`, otherwise exactly `{ "type": string, "message": string }` with the
bounded redaction rule.

The coordinator requires the exact expected response ID set, no duplicate or
extra record, and EOF after the final record. Partial UTF-8, malformed JSON,
unknown keys, oversize records, timeout, early EOF, and output after the final
record fail closed. Worker-provided paths and hashes are claims only; descriptor
authentication after browser process-group quiescence remains authoritative.

## Minimum Test Corrections Before Implementation

1. Replace the current successful
   `mark_terminal("passed", {"readyForPassed": True})` case with grant tests.
2. Add `mutatorCounters` to the valid closure and reject its drift.
3. Add exact expected capture IDs; reject duplicate, missing, and extra IDs.
4. Assert shared-boundary translation count and uniqueness, not only `deltaY`.
5. Add self-consistent invalid PNG and sidecar records whose claimed hashes
   match their invalid bytes.
6. Add request/response oversize, partial, duplicate, extra, timeout, wrong-ID,
   unknown-key, and forbidden-`passed` tests.
7. Split Task 3 lifecycle/authentication tests from Task 4 comparator tests, or
   expose an explicit Task 3-only test command.

Minimum grant scenarios:

- Given a valid finalizing lifecycle, a forged boolean pass is rejected.
- Given an issued grant, a reconstructed or `copy.copy()` grant is rejected.
- Given an issued grant, use with another lifecycle is rejected.
- Given an issued grant, exact use writes `passed` once.
- Given a consumed grant, reuse is rejected and manifest bytes remain unchanged.

## Implementation Order and Gates

1. Correct the blocking tests above; keep them red for intended reasons.
2. Add constants, exact-key validators, canonical JSON, and error redaction.
3. Implement canonical sidecar projection and its mutation tests.
4. Implement bounded worker request/response parsing and exact EOF handling.
5. Implement descriptor contracts, authenticated open/copy, and artifact decode.
6. Implement non-pass lifecycle transitions and stale recovery.
7. Implement closure validation, one-shot grants, and finalizer-only `passed`.
8. Implement the browser worker against the frozen protocol.
9. Integrate Task 3 runner seams; retain legacy no-argument mode/count behavior.
10. Only then implement Task 4 canonical and migration comparators.

Task 3 is not green until lifecycle/authentication/worker tests pass, both child
process groups are quiescent, and no test can synthesize `passed` with a mapping
or mock. Task 4 failures may remain only under a separately named Task 4 gate.

## Traceability

| Requirement | Implementation target | Minimum tests |
| --- | --- | --- |
| `CFR-001`, `CFR-002` | lifecycle, grant registry, finalizer | forged/copied/wrong-run/reuse grant cases |
| `CFR-003` | worker record parser | bounds, EOF, count, ID, schema cases |
| `CFR-004` | sidecar projector | exact keys and volatile-field mutations |
| `CFR-005` | artifact component walk and copy | symlink/swap/link/mutation cases |
| `CFR-006` | error sanitizer | secret/path redaction and 2,048-byte boundary |
| `CFR-007` | terminal materializer and grant registry | repeatable preview, no write/consume, opaque closure cases |
| `CFR-008` | terminal artifact reauthentication | 81 captures under FD 256, peak-open bound, late-inode swap |
| `CFR-009` | snapshot/theme failure checkpoints | detached-payload wiring, revocation failure, immutable terminal partials |

## Change History

| Date | Version | Change |
| --- | --- | --- |
| 2026-07-18 | `v0.2-draft` | Added grant-bound materialization, bounded final path reauthentication, and authority-independent failure checkpoints. |
| 2026-07-17 | `v0.1-draft` | Defined the minimum executable Task 3 evidence API and corrected phase order. |
