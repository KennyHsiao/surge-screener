# UX-1B Evidence Recovery and Accessible Selection Architecture

## Status

| Field | Value |
| --- | --- |
| Decision | ADR-UX1B-R1 |
| Status | Accepted after three independent blocking-review iterations |
| Date | 2026-07-16 |
| Scope | UX-1B evidence isolation, evidence authentication, and selection-control semantics |
| Supersedes | The execution mechanisms in UX-1B R1B-02 and Tasks 1, 2, 4, 5, and 6 |
| Preserves | UX-1B product direction, palette, route inventory, fail-soft runtime behavior, and the four-file theme rollback boundary |

## Context

The accepted UX-1B plan correctly requires a deterministic 27-page by
3-viewport baseline before production theme changes. Its first implementation,
however, treated Python monkeypatches and one process sandbox as if they formed
an enforceable evidence boundary. Review and adversarial probes found several
ways for a compromised or accidentally incomplete fixture to bypass those
claims:

- a pre-opened file descriptor could read production data;
- raw `_socket` and inherited socket paths bypassed the Python socket guard;
- closure-captured file and SQLite callables bypassed monkeypatches;
- the browser and app required incompatible filesystem and process privileges;
- a screenshot could change without failing the structural comparator;
- a failed post-theme run could omit final evidence;
- path authentication had time-of-check/time-of-use gaps;
- the manifest could expose an intermediate `passed` state before final checks.

The same review found eleven production uses of `st.segmented_control`. In the
installed Streamlit 1.57 runtime these are visually button-like, while the
application uses all eleven as required one-of-N choices. Because
`required=False` is the API default, users can clear the selection and leave
`None` in session state. That produces inconsistent downstream fallbacks and
does not provide a stable native radio/select semantic for accessibility.

No production theme change is authorized while either evidence integrity or
selection semantics is unresolved.

## Decision

### 1. Use a trusted coordinator with two least-privilege children

The snapshot and theme runners remain trusted coordinators. They alone may
write final evidence, manifests, and authenticated contracts. They create an
owned run root and launch two separately sandboxed process trees:

1. **App child** — runs the real Streamlit application against deterministic
   fixtures in a read-only source mirror. It can write only its fixture state
   and Streamlit scratch roots. It cannot fork or execute another process, read
   production runtime roots, or make outbound connections. It may bind and
   accept only the coordinator-assigned loopback application port.
2. **Browser child** — runs Playwright and Chromium. It can read the source and
   browser runtime files needed to launch, write only its capture/scratch root,
   and connect only to the exact loopback application port. It cannot read the
   production workspace data roots, baseline evidence, final manifest, or app
   fixture state.

The coordinator receives bounded JSON records from owned files or pipes, checks
them, and copies authenticated artifacts into the final evidence directory.
Neither child can mark a run passed.

### 2. Split workspace identity from executable source identity

`WORKSPACE_ROOT` always names the original repository and is used only by the
trusted coordinator for source hashing and final evidence. `SOURCE_ROOT` names
the immutable run-owned mirror used by both children.

The mirror is created under a coordinator-owned temporary root, preferably
`/private/tmp` on Darwin. It contains only allowlisted source, configuration,
and test-fixture files. It excludes data, reports, credentials, caches,
existing evidence, sockets, device files, symlinks, and hard links. Every
copied regular file is opened without following symlinks, copied to a newly
created inode, hashed, and then made read-only. The mirror manifest is checked
against the coordinator's frozen source digest before either child starts.

Child process creation uses `close_fds=True` and an empty `pass_fds` set. Only
owned standard streams are inherited. Environment variables are constructed
from an allowlist; secrets and production paths are not forwarded.

### 3. Treat Python guards as telemetry, not the security boundary

Existing Python file, socket, subprocess, and provider counters remain useful
for route-level assertions. They do not establish isolation. On Darwin the
mandatory boundary is a calibrated Seatbelt profile launched with
`/usr/bin/sandbox-exec`. Every run performs positive and negative probes inside
both profiles before opening the application:

- allowed owned source and scratch operations succeed;
- production file reads, symlink traversal, inherited descriptors, process
  fork/exec, and undeclared network fail;
- the app can bind only its assigned port and cannot connect outward;
- the browser can start Chromium and connect only to the assigned app port.

Any missing tool, calibration mismatch, or unexpected allow/deny result is
`dependency_unavailable` or `failed`; it is never converted to a passed or
not-applicable result. Non-Darwin platforms fail the UX-1B evidence target
closed until an equivalent isolation backend is explicitly implemented.

### 4. Authenticate artifacts by descriptor and finalize once

The coordinator authenticates every child artifact with descriptor-based
operations anchored to a run-root directory descriptor that it opened before
either child started:

- reject absolute paths, `..`, empty path components, and unexpected names;
- walk every relative directory component from that fixed run-root descriptor
  with `openat(..., O_DIRECTORY | O_NOFOLLOW)` semantics and verify expected
  device, owner, type, and mode at every level;
- open the leaf relative to the authenticated parent descriptor with
  `O_NOFOLLOW`, never by resolving a fresh pathname;
- require an owned regular file with one link and an expected relative name;
- record device, inode, size, and SHA-256 from the open descriptor;
- copy from that same descriptor into a newly created coordinator-owned file;
- recheck source metadata and hash through that same descriptor before
  accepting it.

Authentication starts only after the browser process group is quiescent.
Coordinator output directories and the terminal manifest are also created and
replaced relative to coordinator-only directory descriptors. Intermediate
ancestor symlinks, rename swaps, directory swaps, and leaf swaps are therefore
rejected rather than followed.

The manifest lifecycle is monotonic:

`running -> finalizing -> passed | failed | dependency_unavailable | invalid_data | interrupted`

`passed` is written exactly once, by the coordinator, as the final atomic
manifest replacement after source re-authentication, artifact validation,
counter closure, comparator closure, and manifest-schema validation. A
catchable post-theme failure or interruption still writes a terminal failure
manifest with authenticated partial evidence and a bounded error; it can never
leave an earlier passed manifest behind. `SIGKILL`, host failure, and power loss
cannot be caught and may leave `running` or `finalizing`; those states are never
referenceable as evidence and the next coordinator run classifies the stale
run before starting new work.

### 5. Compare rendered output, not only metadata

Each capture records and authenticates:

- PNG bytes, SHA-256, dimensions, and decoded image validity;
- a canonical non-color render sidecar containing route identity, viewport,
  readiness, semantic roles and accessible names, normalized element geometry,
  visibility, text, and stable application state;
- provider/mutator counters and runtime-root projection.

For the later theme-only comparison, the pre-theme and post-theme canonical
non-color sidecars must be byte-equivalent after explicit volatile-field
normalization. PNG bytes are expected to differ because color changes; their
dimensions and decode contracts must remain valid. Screenshot mutation and
sidecar mutation are separate adversarial tests and both must fail.

### 6. Replace all eleven production segmented controls before freezing the baseline

Ten fixed, short one-of-N selectors become native `st.radio` widgets with
`horizontal=True`. The Analytics DB table picker becomes `st.selectbox`
because its dynamic catalog can contain up to 27 entries. Keys, option order,
labels, help text, handoff behavior, and downstream branches are preserved.

| Session key | Page | Replacement | Required default |
| --- | --- | --- | --- |
| `rg_source` | Risk Guard | horizontal radio | `Watchlist` |
| `inst_view` | Institutions | horizontal radio | first institution view |
| `cockpit_price_view_{ticker}` | Options Cockpit | horizontal radio | snapshot chart |
| `radar_source` | Radar | horizontal radio | manual input |
| `radar_view` | Radar | horizontal radio | all results |
| `kg_view_mode` | Knowledge Graph | horizontal radio | nebula view |
| `kg_label_mode` | Knowledge Graph | horizontal radio | core labels |
| `ai_chat_mode` | AI Chat | horizontal radio | quick mode |
| `retro_validation_lane` | Retro Analysis | horizontal radio | surge review |
| `adb_table` | Analytics DB | selectbox | first current catalog table |
| `checkup_mode` | Stock Checkup | horizontal radio | single-stock mode |

Before constructing a replacement widget, the page normalizes missing,
`None`, and stale values to the declared default. A legal existing value is
preserved. Where a one-shot handoff is present, the handoff is consumed in the
same order as today and may intentionally force the declared mode. Radio
construction uses the existing session value as the single source of truth so
Streamlit does not emit a default/session-state conflict warning.

This intentionally removes the deselected state. It is compatible with the
existing product contract because every downstream branch already treats the
selector as required and falls back to a default. The browser oracle requires
native/AX checked semantics, not a literal `aria-checked` HTML attribute.

The theme gallery removes the synthetic segmented-control contract and adds a
horizontal-radio case plus a selectbox case. Oracles require accessible group
names, exact option labels, one checked radio, roving tab stop, arrow-key
selection, combobox semantics, focus visibility, and measured contrast. Every
interactive target must measure at least 24 by 24 CSS pixels at every captured
viewport; 44 by 44 remains the preferred, non-blocking target.

### 7. Establish a controlled migration boundary before the theme boundary

Changing segmented controls into radios/selectboxes is an intentional semantic
and geometric change, so it cannot occur between the canonical pre-theme and
post-theme manifests whose non-color render sidecars must match exactly.

Before either boundary is captured, every render-affecting fixture and capture
interaction is finalized. That includes a two-table owned Analytics catalog,
seeded Radar results that expose `radar_view`, an expanded AI settings case,
and dual-compatible locators. The digest of the fixture apps, case catalog,
interaction catalog, runner, browser worker, evidence module, and isolation
module is frozen as `captureStackDigest` and must remain identical across the
control migration.

Execution therefore has two paired evidence sets:

1. capture a trustworthy **pre-control** 81/81 page baseline plus a 9-case by
   4-viewport (36-capture) focused-control baseline after the isolation backend
   and capture stack are fixed;
2. change only the exact nine production selector files, then capture a 36/36
   focused-control result and a new 81/81 **canonical pre-theme** page result;
3. compare both pairs under the formal selector-migration rules below and
   freeze the canonical pre-theme manifests;
4. apply the accepted theme batch and compare its post-theme sidecars exactly
   against that canonical pre-theme baseline.

The focused cases are Risk Guard, Institutions, Options Cockpit with ticker
`NVDA`, Radar with deterministic results, Knowledge Graph, expanded AI Chat
settings, Retro Analysis, Analytics DB with two tables, and Stock Checkup. They
cover all eleven stable widget roots at 1440x900, 768x1024, 390x844, and
320x844. Risk Guard uses a dedicated fixture entrypoint that calls its real
`render()` function because it is not in the frozen 27-page navigation.

The migration comparator freezes every control as
`(case, session key, .st-key-* root, layout boundary)`. Semantic or child
geometry differences are allowed only beneath those eleven widget roots.
Outside those roots, DOM/AX order, role, accessible name, text, state,
x-position, width, and height are exact. A layout boundary containing a changed
root may change height. For each later node in the same stable flow scope, the
only permitted y-coordinate change is the cumulative sum of preceding unique
boundary height deltas; shared rows such as the two Knowledge Graph controls
are counted once. Relative gaps must remain exact, and overlap, clipping, or
viewport overflow always fails. Nodes before the boundary and nodes in other
flow scopes retain exact y-coordinates.

All content, provider counts, decisions, routes, and geometry outside the
formal boundary translation remain exact across the control migration.

## Alternatives Considered

### Keep the existing segmented controls and defer accessibility

Rejected by the maintainer. It leaves a known inconsistent `None` state and
button-like semantics in the production UI.

### Upgrade Streamlit and keep segmented controls

Rejected for this recovery. It expands the runtime dependency and visual
regression scope without proving that the component exposes the desired native
one-of-N behavior. A framework upgrade may be planned independently later.

### Put app and browser in one sandbox

Rejected. Chromium requires process execution and broader runtime-file access,
while the application must deny process creation. Combining them forces the
application into the browser's larger privilege set.

### Rely on monkeypatches, network routing, or Python audit hooks

Rejected as the primary boundary because raw callables, closure-captured
objects, inherited descriptors, and native extensions can bypass them. They
remain defense-in-depth telemetry.

### Run the complete workflow in Docker

Deferred. Docker is not installed in the current environment and installing or
operating a new privileged runtime is outside the accepted scope. A later
portable backend may implement the same coordinator/child contract.

## Consequences

Positive consequences:

- evidence claims are grounded in an OS-enforced, calibrated boundary;
- the app and browser receive only the privileges each needs;
- screenshots and semantic render data are authenticated independently;
- a failure cannot accidentally leave a passed manifest;
- all production mode/view/source selectors have consistent required state and
  keyboard/screen-reader behavior;
- the later theme comparison has a clean, exact non-color baseline.

Costs and constraints:

- UX-1B evidence is Darwin-only until an equivalent backend exists;
- the runner is split into coordinator and child responsibilities;
- one extra 81-capture pre-control baseline is required;
- the eleven control migrations need focused behavior and mobile-layout gates;
- no production theme edit can proceed until recovery and canonical pre-theme
  gates pass.

## Acceptance Criteria

This decision may be marked Accepted only when the implementation plan names
all affected files, red tests, negative probes, evidence phases, rollback
boundaries, and exact verification commands, and an independent review finds no
blocking issue. Implementation is complete only when all recovery gates pass;
unsupported or unavailable checks must be reported and must not be described as
passing.
