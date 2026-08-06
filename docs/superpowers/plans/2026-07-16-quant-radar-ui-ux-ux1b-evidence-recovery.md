# Quant Radar UI/UX UX-1B — Evidence Recovery and Accessible Selection Controls

## Document Info

| Field | Value |
| --- | --- |
| Type | Executable, test-first recovery plan |
| Version | v0.3-accepted |
| Status | Accepted after independent review iteration 3; Task 0 is authorized |
| Date | 2026-07-16 |
| Decision | `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-architecture.md` |
| Parent | `docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b.md` v0.3-accepted |
| Parent SHA-256 | `48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7` |
| Direction | Option A — Calm Decision Cockpit |
| Audience | Maintainer, implementer, accessibility reviewer, evidence reviewer |

## Outcome

Repair UX-1B's evidence boundary before trusting its 27-page matrix, replace
all eleven production segmented selectors with accessible required controls,
and freeze a trustworthy canonical pre-theme baseline. The accepted semantic
theme is still applied only after this recovery plan passes.

This plan does not redesign page layout, change routes, alter provider logic,
modify decisions, add network behavior, or remove fail-soft artifact loading.
Missing, partially written, and malformed JSON must continue to degrade to the
same empty/default UI states rather than crash FastAPI or Streamlit.

## Relationship to the Accepted UX-1B Plan

The accepted parent plan remains byte-immutable. This recovery plan:

- **supersedes** R1B-02's isolation mechanism and Tasks 1, 2, 4, 5, and 6 where
  they rely on one child sandbox, Python guards as a boundary, path-only
  authentication, or metadata-only comparisons;
- **supersedes** the assumption that segmented controls may remain as semantic
  evidence for selected state;
- **retains** the frozen 27-page projection, route identities, provider/mutator
  contracts, Option A palette, semantic roles, non-goals, and rollback rules;
- **retains but reorders** the parent Task 3 theme change after the recovery
  baseline and selection migration;
- **expands** the temporarily editable production-page set to the exact nine
  files listed below, only for the eleven selector replacements and their
  state normalization.

If the two plans conflict, this document governs evidence isolation, artifact
authentication, manifest lifecycle, render comparison, selector semantics, and
execution order. Everything else remains governed by the accepted parent.

### Explicit parent acceptance-criteria amendments

The recovery would be completion-impossible if the following parent criteria
were read without these authorized, narrow exceptions:

- **UX1B-AC-003:** exact identity/counter/source/evidence equality remains
  required within every phase. Across the control migration, only the formal
  eleven-root semantic and boundary-translation rules in this plan apply.
- **UX1B-AC-004:** the selected-control gallery no longer requires synthetic
  segmented-button state. Horizontal radio and selectbox native/AX state replace
  that case; all other computed-style, contrast, owner-set, focus, link, and
  signal requirements remain.
- **UX1B-AC-007:** no provider, API, route, decision, artifact, or data behavior
  may change. The sole page/session/layout exception is the exact eleven
  selector hunks and their declared state normalization in the exact nine files
  below, plus the formally measured induced vertical translation.
- **UX1B-AC-008:** every intentional selector and induced layout difference is
  human-reviewed. Geometry is exact except for the executable boundary
  translation rule; the later theme-only pre/post comparison remains exact.

These amendments do not edit or rewrite the accepted parent document.

## Pre-implementation Gate

### User request coverage

| Request | Plan coverage | Gate |
| --- | --- | --- |
| Preserve API/Streamlit fail-soft reads | No loader or endpoint semantics are changed; fail-soft regressions remain required checks | COVERED |
| Repair UX-1B evidence weaknesses | Tasks 1–5 provide OS isolation, descriptor authentication, terminal lifecycle, and rendered-output comparison | COVERED |
| Replace all production segmented controls now | Tasks 6–8 migrate all 11 controls, behavior-test them, and verify AX/mobile behavior | COVERED |
| Continue to the next UI/UX phase only when review passes | Task 9 freezes the canonical pre-theme gate; parent theme work remains blocked before then | COVERED |

### Known blocking findings and resolution

| Finding | Resolution in this plan | Status before execution |
| --- | --- | --- |
| Inherited descriptors can expose production data | `close_fds=True`, empty `pass_fds`, descriptor negative calibration | Specified; red test required |
| Python file/socket guards are bypassable | Separate calibrated OS sandboxes; Python guards telemetry only | Specified; red test required |
| Browser and app need incompatible privileges | Separate app/browser profiles and writable roots | Specified; red test required |
| Screenshot mutation can pass | Authenticated PNG plus canonical render sidecar and mutation tests | Specified; red test required |
| Path authentication has TOCTOU gaps | `openat`/`O_NOFOLLOW`-style descriptor authentication and recheck | Specified; red test required |
| Manifest may pass before final checks | Monotonic lifecycle; `passed` is final coordinator-only atomic write | Specified; red test required |
| Post-theme failure may omit evidence | Terminal failure manifest with authenticated partial evidence | Specified; red test required |
| 11 selectors can leave `None` and lack desired semantics | 10 native radios plus 1 selectbox, state sanitation, AX/keyboard gates | Specified; behavior test required |
| Selector migration invalidates theme-only equality | Separate pre-control and canonical pre-theme baselines | Specified |
| Seatbelt/Chromium compatibility may vary | Mandatory per-run positive/negative calibration; fail closed | Specified; runtime gate required |

No unresolved design blocker remains in v0.3 after three independent review
iterations. Task 0 may proceed; later tasks remain gated in sequence.

## Scope and File Ownership

### New files

- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-architecture.md`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json`
- `scripts/ui_ux_isolation.py`
- `scripts/ui_ux_evidence.py`
- `scripts/ui_ux_browser_worker.py`
- `scripts/ui_ux_selection_fixture_app.py`
- `scripts/test_ui_ux_isolation.py`
- `scripts/test_ui_ux_evidence.py`
- `scripts/test_ui_ux_selection_fixture.py`
- `scripts/test_ui_accessible_selection_controls.py`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`

### Existing evidence/tooling files that may change

- `Makefile`
- `scripts/ui_ux_fixtures.py`
- `scripts/ui_ux_fixture_app.py`
- `scripts/ui_ux_snapshot_matrix.py`
- `scripts/ui_ux_theme_fixture_app.py`
- `scripts/ui_ux_theme_matrix.py`
- `scripts/test_ui_ux_fixtures.py`
- `scripts/test_ui_ux_snapshot_matrix.py`
- `scripts/test_ui_ux_theme.py`
- `scripts/test_ui_ux_theme_matrix.py`
- `scripts/test_dashboard_navigation.py`
- `scripts/test_ui_ux_contract.py`

### Exact production selector files that may change

- `ui/risk_guard.py`
- `ui/institutions.py`
- `ui/options_cockpit.py`
- `ui/radar.py`
- `ui/knowledge_graph.py`
- `ui/ai_chat.py`
- `ui/retro_analysis.py`
- `ui/analytics_db.py`
- `ui/stock_checkup.py`

Within those nine files, only selector option declarations, pre-widget session
normalization, the widget calls, and directly stale comments/docstrings may
change. Existing unrelated dirty edits are user-owned and must be preserved.
`ui/ai_chat.py` is already modified; patch only the mode initialization and
selector lines identified by the prechange record.

### Protected until the parent theme task resumes

- `.streamlit/config.toml`
- `app.py`
- `requirements.txt`
- `ui/_design.py`
- `ui/_shared.py`
- `ui/_components.py`

The absent theme-contract path is recorded as `exists: false` in the prechange
record and is created atomically only in Task 9. The prechange record never
contains its own hash; every other planned-created path is recorded as
`exists: false` with no SHA until it exists.

The recovery does not use Streamlit's newer `width=` radio/selectbox argument,
because `requirements.txt` still allows versions before that API. Runtime
browser evidence must use and record Streamlit 1.57.0; dependency pinning stays
inside the parent theme batch.

## Frozen Selector Contract

| File | Key | Options source | Widget | Invalid/`None` default | Special invariant |
| --- | --- | --- | --- | --- | --- |
| `ui/risk_guard.py` | `rg_source` | `手動輸入`, `Watchlist`, `Screener 候選`, `IBKR 持倉` | horizontal radio | `Watchlist` | source/run-key behavior unchanged |
| `ui/institutions.py` | `inst_view` | `機構持股 · 股票 → 誰持有它`, `機構持倉 · 機構 → 它持有什麼` | horizontal radio | `機構持股 · 股票 → 誰持有它` | only chosen provider executes |
| `ui/options_cockpit.py` | `cockpit_price_view_{ticker}` | `快照圖 + 預期波動錐`, `互動圖 (TradingView)` | horizontal radio | `快照圖 + 預期波動錐` | dynamic per-ticker memory retained; focused ticker is `NVDA` |
| `ui/radar.py` | `radar_source` | `手動輸入`, `Watchlist`, `Screener 候選`, `反轉候選(掃描)`, `IBKR 持倉` | horizontal radio | `手動輸入` | handoff forces manual and clears stale results |
| `ui/radar.py` | `radar_view` | `全部`, `風險警示`, `反轉候選`, `兩者共現` | horizontal radio | `全部` | table filtering unchanged |
| `ui/knowledge_graph.py` | `kg_view_mode` | `星雲圖`, `驗證泳道` | horizontal radio | `星雲圖` | `None` must no longer fall into swimlane |
| `ui/knowledge_graph.py` | `kg_label_mode` | `核心`, `因子`, `全部`, `無` | horizontal radio | `核心` | graph data/figure branches unchanged |
| `ui/ai_chat.py` | `ai_chat_mode` | `快速問答`, `深度研究` | horizontal radio | `快速問答` | provider and saved payload unchanged |
| `ui/retro_analysis.py` | `retro_validation_lane` | `暴漲事件復盤`, `續漲強者`, `Playbook 驗證` | horizontal radio | `暴漲事件復盤` | one-shot `validation_lane` order retained |
| `ui/analytics_db.py` | `adb_table` | current sorted catalog | selectbox | first current table | empty catalog retains info/return; stale table never reaches query functions |
| `ui/stock_checkup.py` | `checkup_mode` | `單檔`, `批次` | horizontal radio | `單檔` | handoff forces single before branch |

Radio construction follows one pattern:

```python
options = (...)
if st.session_state.get(key) not in options:
    st.session_state[key] = default
value = owner.radio(
    label,
    options,
    index=None,
    key=key,
    horizontal=True,
    # preserve existing label_visibility/help exactly
)
```

`index=None` does not create a blank state because a legal session value is
seeded first. It avoids giving Streamlit competing widget-default and session
defaults. Analytics performs its existing empty-catalog `st.info` and `return`
before any indexing or normalization. With a non-empty catalog it normalizes
`adb_table` and constructs the selectbox with `index=None`; missing, malformed,
empty, stale, and valid-catalog cases are all tested.

Every production selector target must measure at least 24 by 24 CSS pixels at
320, 390, 768, and 1440 widths. A 44 by 44 target is preferred but is not a
blocking WCAG 2.2 AA threshold.

## Evidence Contract

### Process topology

```text
trusted coordinator
  |- owned source mirror (read-only)
  |- app child / app Seatbelt profile
  |    |- fixture writable root
  |    `- exact loopback listener
  |- browser child / browser Seatbelt profile
  |    |- Chromium process tree
  |    |- capture staging root
  |    `- exact loopback outbound to app
  `- descriptor-authenticated final evidence + terminal manifest
```

### Source mirror allowlist

The mirror includes only the Python source/configuration required by the real
app and deterministic fixtures. It excludes, at minimum:

- `.git`, `.claude`, `.agents`, `.env*`, credentials, keys, sockets, caches;
- `data`, `reports`, database files, candidate/chat/vault runtime roots;
- prior screenshots, manifests, backups, and recovery evidence;
- symlinks, hard links, FIFOs, devices, and files outside the workspace.

The mirror builder rejects rather than follows an unexpected file kind. The
prechange record freezes the exact include/exclude policy and source digest.

### App profile

Must allow:

- read-only mirror reads and an explicit read-only runtime allowlist for the
  current Python executable, `.venv` packages, system libraries, fonts, and
  browser cache paths required by the calibrated process; allowing the whole
  original workspace is forbidden;
- writes below its fixture, Streamlit-home, and temporary roots;
- binding/listening/accepting on the one assigned loopback port.

Must deny:

- source-mirror writes;
- original-workspace production data/report/evidence reads and writes;
- all fork/exec and undeclared process operations;
- all outbound network, including the app's own port;
- any other listener or inherited descriptor use.

### Browser profile

Must allow:

- Chromium/Node runtime reads from the explicit calibrated executable,
  `.venv`, system-library, font, and Playwright-browser-cache allowlist, plus
  process descendants;
- capture/cache/tmp writes below its own root;
- outbound loopback only to the assigned app port.

Must deny:

- original-workspace production data/report/evidence reads;
- app fixture-state and coordinator final-evidence reads/writes;
- any other network destination or port;
- writes outside its owned capture/cache/tmp root.

### Manifest lifecycle and statuses

- `running`: initial coordinator-owned manifest, no success claim.
- `finalizing`: children stopped; closure checks underway.
- terminal: exactly one of `passed`, `failed`, `dependency_unavailable`,
  `invalid_data`, or `interrupted`.

Every write is atomic. Only a terminal manifest may be referenced by a theme
contract. `passed` requires all expected captures, source start/end equality,
successful calibration, child exit success, authenticated artifacts, exact
provider/mutator counters, zero prohibited access, comparator closure, and
schema validation.

Catchable signals/exceptions checkpoint a terminal status. `SIGKILL`, host
failure, and power loss may leave `running` or `finalizing`; those manifests are
permanently unreferenceable. Before a new run, the coordinator detects stale
nonterminal owned runs and records a separate recovery classification without
mutating them into passed evidence.

### Descriptor authentication

The coordinator opens the run root before children start and keeps that
directory descriptor as the only namespace anchor. Artifact paths must be
relative and contain no empty, absolute, `.` or `..` components. Every
intermediate component is opened relative to the previous authenticated
descriptor with directory plus no-follow semantics and checked for expected
device, owner, type, and mode. The leaf is opened no-follow relative to its
authenticated parent and must be an owned, one-link regular file.

Only after the complete browser process group is quiescent does the coordinator
hash and copy from that same leaf descriptor, then recheck device, inode, link
count, size, and hash through the still-open descriptor. Final evidence and
manifest replacements are written relative to coordinator-only output
directory descriptors. No security decision is made from `Path.resolve()` or a
second pathname lookup.

### Frozen capture stack and selector comparator

Before pre-control capture, freeze `captureStackDigest` over the fixture apps,
fixture/state catalog, interaction catalog, case/control-root catalog,
coordinator runners, browser worker, evidence module, and isolation module.
That digest must be identical for the pre-control focused/page runs and the
post-control focused/canonical-pretheme runs. Test files and production selector
files are separately hashed and are not part of that stack digest.

The focused profile contains nine real-render cases and 36 captures:

| Case | Stable roots |
| --- | --- |
| `risk-guard-controls` | `.st-key-rg_source` |
| `institutions-controls` | `.st-key-inst_view` |
| `options-cockpit-controls` | `.st-key-cockpit_price_view_NVDA` |
| `radar-controls` | `.st-key-radar_source`, `.st-key-radar_view` |
| `knowledge-graph-controls` | `.st-key-kg_view_mode`, `.st-key-kg_label_mode` |
| `ai-chat-settings-controls` | `.st-key-ai_chat_mode` |
| `retro-controls` | `.st-key-retro_validation_lane` |
| `analytics-controls` | `.st-key-adb_table` |
| `stock-checkup-controls` | `.st-key-checkup_mode` |

The full-page comparator freezes a second variant catalog for every affected
27-page case. The root string is reusable, but the flow and boundary anchors
are resolved and frozen independently in the real full-page DOM:

| Full-page case | Stable roots |
| --- | --- |
| `stock-checkup` | `.st-key-checkup_mode` |
| `options-cockpit` | `.st-key-cockpit_price_view_NVDA` |
| `radar` | `.st-key-radar_source`, `.st-key-radar_view` |
| `retro-analysis` | `.st-key-retro_validation_lane` |
| `analytics-db` | `.st-key-adb_table` |
| `knowledge-graph` | `.st-key-kg_view_mode`, `.st-key-kg_label_mode` |
| `institutions` | `.st-key-inst_view` |

Risk Guard has no full-page route and AI Chat settings remain closed in the
27-page profile, so they are compared only in the focused profile. If either
root appears in a full-page sidecar, or any changed full-page root is absent
from this catalog, comparison fails as an unmapped affected root rather than
silently accepting or requiring impossible exact equality.

Each variant freezes one stable flow scope and one layout boundary per unique
row or block. Descendants of the eleven roots may change semantics and geometry,
subject to the replacement AX contract. A layout boundary may change height.
Every other node must retain DOM/AX order, role, name, text, state, x, width,
and height. Its only allowed y change is the cumulative height delta of unique
preceding boundaries in the same flow scope. Shared boundaries are counted
once; nodes before a boundary or in another scope keep exact y. Relative gaps,
non-overlap, clipping, and viewport overflow are checked independently. Any
unmapped, sibling, excessive, nonuniform, or cross-scope shift fails.

### Required adversarial cases

Tests must prove rejection of:

- inherited production-data descriptor;
- raw file, closure-captured file, and closure-captured SQLite reads;
- raw socket and `_socket` MRO paths;
- undeclared listener and undeclared loopback/external outbound connection;
- leaf and intermediate-ancestor symlink, hard-link, rename-swap,
  parent-directory swap, and raced ancestor replacement;
- child-written final manifest or baseline evidence;
- screenshot byte mutation, dimension mutation, and render-sidecar mutation;
- a source change while a child is alive;
- browser/app nonzero or signaled exit;
- missing, malformed, partial, duplicate, or extra capture records;
- catchable finalization interruption and post-theme failure;
- stale `running`/`finalizing` recovery after simulated uncatchable termination;
- unauthorized sibling changes and excessive/nonuniform y translations;
- an affected full-page root with no variant-catalog mapping.

## Execution Tasks

### Task 0 — Accept the recovery specification and freeze prechange state

**Files:**

- Review `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-architecture.md`
- Review this plan
- Create `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json`
- Create `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json`
- Create an owned rollback bundle below
  `.claude/ui_snapshots/ux1b/recovery/prechange-bundle-<id>/`

**Steps:**

1. Independently review this plan for request coverage, affected files,
   verification completeness, destructive behavior, runtime feasibility,
   selector state compatibility, and scope drift.
2. Resolve every blocking issue in the documents. If the same blocker remains
   after three review iterations, stop and report it.
3. Mark the ADR `Accepted` and this plan `v0.3-accepted` only after review
   iteration 3 has no blocker. This gate passed on 2026-07-16.
4. Record SHA-256 for the accepted parent plan, ADR, accepted recovery plan,
   all protected files, all nine selector files, and all evidence files listed
   above. Record the dirty-worktree paths without adopting their ownership.
   Do not hash the prechange record itself. Record every not-yet-created path,
   including the theme contract, as `exists: false` with no SHA.
5. Record the installed Python, Streamlit, Playwright, Chromium, Darwin, and
   `sandbox-exec` identities and the source-mirror policy.
6. Build the rollback bundle before any implementation write. For each existing
   tooling/document file, store exact prechange bytes and SHA-256; whole-file
   restoration is authorized only when the live file exactly matches the
   recorded plan-produced posthash. For the nine dirty-sensitive production
   files, store exact context-anchored preimage bytes for the eleven selector/
   normalization/comment hunks, their surrounding anchors, and before hashes;
   rollback applies only a hunk whose live bytes match its recorded postimage
   exactly and refuses on any surrounding or concurrent drift. For every
   planned-created file, record owner, intended path, and later posthash;
   deletion is allowed only when all three still match. Hash and descriptor-
   authenticate the bundle manifest from the rollback JSON.
7. Recompute hashes immediately before every later task that writes a frozen
   file. A mismatch not caused by this plan stops that task.

**Gate:** accepted documents, a valid prechange record, and an authenticated
restorable rollback bundle; otherwise stop.

### Task 1 — Add red isolation and lifecycle contracts

**Files:**

- Create `scripts/test_ui_ux_isolation.py`
- Create `scripts/test_ui_ux_evidence.py`
- Modify `scripts/test_ui_ux_snapshot_matrix.py`
- Modify `scripts/test_ui_ux_theme_matrix.py`

**Steps:**

1. Write source-mirror tests for allowlisted regular files, new inodes,
   read-only permissions, stable digest, excluded runtime roots, and rejection
   of symlinks/hard links/special files.
2. Write child-spawn tests requiring `close_fds=True`, no `pass_fds`, an
   allowlisted environment, owned stdio, and no secret/workspace path leakage.
3. Encode the complete app/browser positive and negative calibration matrix.
4. Add the adversarial descriptor, raw file/socket, closure/SQLite, fork/exec,
   port, and path-swap cases.
5. Add manifest state-machine tests. Assert no code path writes `passed` before
   final closure; catchable failures produce one terminal manifest; simulated
   `SIGKILL`/host loss leaves an unreferenceable stale nonterminal that the next
   run classifies separately.
6. Add run-root-dirfd component-walk authentication, intermediate-ancestor
   race, and screenshot/sidecar mutation tests.
7. Run the new tests and record that they fail for the intended missing
   implementations, not for syntax/import mistakes.

**Red command:**

```bash
.venv/bin/python scripts/test_ui_ux_isolation.py
.venv/bin/python scripts/test_ui_ux_evidence.py
```

**Gate:** all intended assertions are red and categorized; no production file
has changed.

### Task 2 — Implement source mirror, dual profiles, and calibration

**Files:**

- Create `scripts/ui_ux_isolation.py`
- Modify the Task 1 tests

**Steps:**

1. Implement run-owned root creation using mode `0700` directories and
   collision-safe names.
2. Implement descriptor-safe source mirroring, exclusion checks, copy hashing,
   inode/link verification, read-only finalization, and mirror authentication.
3. Implement explicit environment and file-descriptor construction for child
   processes.
4. Generate independent, minimal app and browser Seatbelt profiles using the
   assigned roots and exact port. Do not interpolate unescaped user input.
5. Implement per-run calibration helpers and structured results. Calibration
   must test real child profiles, not a looser test profile.
6. Make unsupported platforms and missing dependencies fail closed with
   `dependency_unavailable`.
7. Pass all Task 1 isolation tests and rerun the existing runner tests.

**Gate:** all allow probes pass, all deny probes fail with the expected class,
and Chromium launches inside the browser profile without broadening the app
profile.

### Task 3 — Implement the browser worker and authenticated evidence protocol

**Files:**

- Create `scripts/ui_ux_evidence.py`
- Create `scripts/ui_ux_browser_worker.py`
- Modify `scripts/ui_ux_snapshot_matrix.py`
- Modify `scripts/ui_ux_theme_matrix.py`
- Modify their tests

**Steps:**

1. Define a versioned, bounded JSON request/response schema. Requests contain
   only mirror-relative fixture entrypoint, exact route/case, viewport, app
   origin, and owned staging paths.
2. Move Playwright/Chromium capture execution into the browser child. It writes
   staged PNG and canonical render sidecar files, never the final manifest.
3. Launch the real Streamlit fixture application in the app profile from
   `SOURCE_ROOT`; retain route identity and provider/mutator instrumentation.
4. After browser process-group quiescence, authenticate child result files by
   walking every component from the retained run-root dirfd, copy/hash/recheck
   through the same leaf descriptor, and write through coordinator-only output
   dirfds.
5. Record PNG SHA-256, decoded dimensions, sidecar SHA-256/schema, process exit,
   calibration, exact port, and source-mirror digest.
6. Implement the monotonic manifest state machine. Move every success decision
   to one final coordinator function.
7. Preserve terminal evidence on exceptions, interrupts, dependency failures,
   and post-theme failures without leaking paths, tokens, or secrets.
8. Prove with tests that a child cannot write or replace final evidence.

**Gate:** all lifecycle/authentication tests pass and the no-argument UX-0 plus
UX-1A profiles retain their existing public mode/count contracts.

### Task 4 — Add canonical render comparison and harden theme authentication

**Files:**

- Modify `scripts/ui_ux_evidence.py`
- Modify `scripts/ui_ux_snapshot_matrix.py`
- Modify `scripts/ui_ux_theme_matrix.py`
- Modify associated tests

**Steps:**

1. Canonicalize accessible roles/names/states, visible text, normalized
   geometry, viewport, route/callable identity, and stable application state.
2. Define the exact volatile-field allowlist. Timestamps, random IDs, absolute
   owned paths, and browser-internal node IDs may be removed; content,
   decisions, provider counts, visibility, and geometry may not.
3. Require exact canonical-sidecar equality for the later pre/post-theme pair.
4. For the control-migration pair, resolve every frozen `(case, session key,
   .st-key-* root, flow scope, layout boundary)` identity. Permit semantic and
   child-geometry differences only under the eleven roots. Permit boundary
   height changes and only the cumulative, unique-boundary y-translation for
   later nodes in the same flow scope. Require exact order/role/name/text/state/
   x/width/height, exact y elsewhere, exact relative gaps, and no overflow or
   overlap. Emit every allowed delta for human review.
5. Authenticate the referenced pre-theme manifest and every artifact again at
   finalization by descriptor. Reject symlink, rename, inode, link-count, size,
   or hash drift.
6. Add mutation tests for one byte, one pixel/dimension, one semantic state,
   one geometry field, one provider count, one unauthorized sibling/subtree,
   an excessive/nonuniform y shift, a double-counted shared row, and a
   cross-flow shift.

**Gate:** every allowed theme-only difference passes; every non-color or
unauthorized migration mutation fails.

### Task 5 — Integrate the dual sandbox into both UX-1B runners

**Files:**

- Modify `scripts/ui_ux_fixtures.py`
- Modify `scripts/ui_ux_fixture_app.py`
- Create `scripts/ui_ux_selection_fixture_app.py`
- Modify `scripts/ui_ux_snapshot_matrix.py`
- Modify `scripts/ui_ux_theme_fixture_app.py`
- Modify `scripts/ui_ux_theme_matrix.py`
- Create `scripts/test_ui_ux_selection_fixture.py`
- Modify all focused fixture/runner/theme test files
- Modify `Makefile`

**Steps:**

1. Replace direct child/browser launch paths in the UX-1B profiles with the
   new coordinator helpers. Keep legacy UX-0 and UX-1A modes compatible.
2. Split every old `ROOT` use into explicit `WORKSPACE_ROOT`, `SOURCE_ROOT`,
   fixture root, browser root, staging root, or final evidence root.
3. Ensure fixtures receive only mirror/owned paths and cannot refer back to the
   original workspace. Keep exact provider/mutator counters.
4. Finalize every phase-neutral render state before baseline capture:
   seed two owned Analytics catalog tables and deterministic
   `_columns`/`_tickers`/`_fetch_table` results while retaining the empty-catalog
   fail-soft case; seed Radar risk/reversal/run-key state so `radar_view`
   renders; expand AI settings in its focused interaction; and make the
   institution locator accept the pre-control button or post-control radio
   without changing the selected business state.
5. Add profile `ux1b-selection-controls` and the dedicated selection fixture
   entrypoint. It invokes the real production `render()` callables for the nine
   frozen cases, including direct Risk Guard, and exposes the exact eleven
   root/flow/boundary identities at desktop, tablet, mobile, and 320x844.
6. Replace the theme fixture's synthetic `segmented` case/oracle with
   `radio_horizontal` and add `selectbox` now, before `captureStackDigest` is
   frozen. Unit-test their contract, but do not run the semantic-color gallery
   until the parent Task 3 has installed the accepted tokens/CSS.
7. Freeze `captureStackDigest` over the exact capture-stack files and contracts.
   Atomically create
   `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json` with schema
   `quant-radar-ui-ux-ux1b-capture-stack/v1`, every member path/SHA-256, both
   focused/full-page root-flow-boundary catalogs, and the aggregate digest.
   From this point through Task 9, any capture-stack byte change is a blocker.
8. Add exact Make targets without changing the default target:
   `ui-ux1b-recovery-tests`, `ui-ux1b-recovery-precontrol`,
   `ui-ux1b-recovery-postcontrol`, and
   `ui-ux1b-recovery-verify-migration`. The last three require one explicitly
   set and reused `UX1B_RECOVERY_ID`; their commands are frozen under
   Verification Commands.
9. Run all focused runner/fixture/theme tests plus compile checks.
10. Run one full-page and all nine focused cases at 390x844 as a real-profile
    smoke matrix before the baseline gate.

**Gate:** focused tests and smoke evidence pass using the real dual profiles;
all render-affecting fixture/interaction work is complete; the capture-stack
digest is frozen; no pass is synthesized by mocks.

### Task 6 — Capture the trustworthy pre-control baseline

**Files:**

- Create run evidence below `.claude/ui_snapshots/ux1b/recovery/`
- Create/update `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`

**Steps:**

1. Recheck protected/source hashes and require Streamlit 1.57.0.
2. Set and record one immutable `UX1B_RECOVERY_ID`, then run
   `make ui-ux1b-recovery-precontrol UX1B_RECOVERY_ID=<id>`. This captures all
   frozen 27 routes at 1440x900, 768x1024, and 390x844 plus the nine focused
   cases at 1440x900, 768x1024, 390x844, and 320x844.
3. Require exactly 81 passed page records and 36 passed focused-control records,
   exact eleven root identities, exact route/callable identities, exact
   counters, zero prohibited access, clean child exits, source start/end
   equality, and authenticated PNG/sidecar artifacts.
4. Independently reopen and verify both terminal manifests and all 234
   PNG/sidecar artifacts from coordinator-owned dirfds.
5. Freeze both manifest SHA-256 values, `captureStackDigest`, and the exact nine
   production selector-file hashes in the recovery document. Do not alter
   production code if this gate fails.

**Gate:** authenticated pre-control pages 81/81 and controls 36/36 under one
capture-stack digest. Otherwise fix tooling/fixtures and repeat Task 6; do not
proceed to selector migration.

### Task 7 — Add red selector behavior and accessibility tests

**Files:**

- Create `scripts/test_ui_accessible_selection_controls.py`
- Modify only test files; capture-stack, fixture, runner, interaction, and
  production bytes are frozen after Task 6

**Steps:**

1. Add an AST gate requiring zero `.segmented_control(...)` calls in
   `app.py` and `ui/**/*.py` after migration and exactly the frozen 11 calls
   before migration.
2. Add per-key tests for missing, `None`, invalid/stale, and legal existing
   values. Require the declared default and preservation of legal state;
   specifically `rg_source=None` or invalid must become `Watchlist`.
3. Add downstream branch tests for all four Risk Guard sources, manual-field
   visibility, IBKR include-position behavior, and run-key invalidation: a
   matching key retains prior results, while changed source/tickers/include
   clears `rg_result`, `rg_detail_pick`, and `rg_run_key`. Also test institution
   provider exclusivity; both Options chart branches with `NVDA` and a second
   ticker to prove per-ticker state isolation; Radar handoff/filter; Knowledge
   Graph figures; Retro one-shot lane; AI provider/save payload; Analytics DB
   table/query; and Stock Checkup handoff/batch behavior.
4. Cover Analytics missing/malformed/empty catalog without indexing, plus
   `None`, stale, valid-first, and valid-second-table state. Require the second
   table to reach `_columns` and `_fetch_table` exactly.
5. Assert the already-frozen focused browser contract requires, in post-control
   phase, accessible radiogroup/combobox names, exact option labels, one checked
   radio, roving tab stop, ArrowLeft/ArrowRight/Space, selectbox keyboard
   operation, 24x24 minimum targets, and no overflow/overlap/clipping.
6. Confirm all intended tests fail because the eleven production calls are
   still segmented, not because a fixture/capture-stack byte changed.

**Gate:** tests fail only because the old segmented widgets remain.

### Task 8 — Migrate all eleven production controls

**Files:**

- Modify the exact nine production selector files

**Steps:**

1. Recheck each target file against the prechange hash. For dirty files,
   compare the exact target hunk and preserve every unrelated byte.
2. Apply the frozen session normalization and replacement widget for each key.
   Preserve option order, keys, label visibility, help, handoff order, provider
   calls, returns, and downstream branches.
3. Update the Institutions docstring to describe a required radio choice.
4. Run selector behavior tests after each logical group, then all focused tests.
5. Run a post-control 390x844 focused smoke capture with the frozen capture
   stack. Native checked state is
   accepted via the input/AX property; a literal `aria-checked` attribute is
   not required.
6. If any replacement requires a different widget or option/state contract,
   stop. Author a separately versioned amendment and prechange revision, run a
   new blocking review, and recapture pre-control evidence. Never edit this
   accepted plan or the frozen capture stack in place.

**Gate:** zero production segmented calls, all focused behavior tests and the
390px real smoke pass, exactly the nine selector files changed, and no unrelated
production or capture-stack diff exists.

### Task 9 — Capture and freeze the canonical pre-theme baseline

**Files:**

- Create run evidence below `.claude/ui_snapshots/ux1b/recovery/`
- Update `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`
- Create `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` atomically

**Steps:**

1. Compare actual production and tooling diffs against Tasks 1–8. Revert or
   explain any scope drift; never overwrite user-owned work.
2. Perform a fresh code review for bugs, regressions, missing tests,
   maintainability, fail-soft behavior, and security-boundary mistakes. Fix all
   blocking findings.
3. With the exact Task 6 run ID, run
   `make ui-ux1b-recovery-postcontrol UX1B_RECOVERY_ID=<same-id>`. This captures the
   focused controls 36/36 and the full pages 81/81 as canonical pre-theme.
4. Run `make ui-ux1b-recovery-verify-migration
   UX1B_RECOVERY_ID=<same-id>`. Compare pre/post focused manifests and pre-control/
   canonical page manifests using the formal root/boundary translation rules.
   Human-review every allowed selector/layout difference and require exact
   content, state, counters, and capture-stack equality elsewhere.
5. Independently descriptor-verify all four terminal manifests and their
   artifacts. Require 36/36 focused plus 81/81 canonical pre-theme, then freeze
   their hashes and post-control production source hashes.
6. Run the complete automated, historical UX-0/UX-1A, hash, and fail-soft
   verification set below. The semantic-color gallery target
   `ui-ux1b-theme-states` remains deferred until parent Task 3 installs the
   accepted tokens/CSS; only its unit contract is run in recovery.
7. After every prior check passes, reauthenticate all four manifests, the
   migration report, source hashes, rollback bundle, and capture-stack contract.
   As the final coordinator-owned success write, atomically create the parent
   theme contract with the canonical pre-theme manifest relative path/SHA-256,
   capture-stack digest, source projection, and recovery comparison report
   path/SHA-256. It must not refer to pre-control or nonterminal evidence. On
   any earlier failure the contract remains absent; no pending-looking file is
   published.
8. Only after that final write, declare the recovery complete and resume the
   parent UX-1B Task 3 semantic-theme batch.

**Gate:** focused post-control 36/36, canonical pre-theme 81/81, accepted formal
migration comparison, atomic authenticated theme contract, and all verification
checks. A failure blocks parent theme work.

## Verification Commands

Task 5 adds these exact Make recipes. `UX1B_RECOVERY_ID` has no default and each
capture/verify target begins with `test -n "$(UX1B_RECOVERY_ID)"` so separate
invocations cannot silently select different runs:

```make
UX1B_RECOVERY_ID ?=

ui-ux1b-recovery-tests:
	$(PY) scripts/test_ui_ux_isolation.py
	$(PY) scripts/test_ui_ux_evidence.py
	$(PY) scripts/test_ui_ux_selection_fixture.py
	$(PY) scripts/test_ui_accessible_selection_controls.py
	$(PY) scripts/test_ui_ux_fixtures.py
	$(PY) scripts/test_ui_ux_snapshot_matrix.py
	$(PY) scripts/test_ui_ux_theme.py
	$(PY) scripts/test_ui_ux_theme_matrix.py
	$(PY) scripts/test_ui_ux_contract.py
	$(PY) scripts/test_dashboard_navigation.py

ui-ux1b-recovery-precontrol:
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-full-pages --phase precontrol --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/precontrol-pages-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-selection-controls --phase precontrol --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/precontrol-controls-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/precontrol-pages-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-full-pages --expected-phase precontrol --expected-count 81 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/precontrol-controls-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-selection-controls --expected-phase precontrol --expected-count 36 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json

ui-ux1b-recovery-postcontrol:
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-selection-controls --phase postcontrol --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/postcontrol-controls-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-full-pages --phase pretheme --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/canonical-pretheme-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/postcontrol-controls-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-selection-controls --expected-phase postcontrol --expected-count 36 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/canonical-pretheme-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-full-pages --expected-phase pretheme --expected-count 81 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json

ui-ux1b-recovery-verify-migration:
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) scripts/ui_ux_evidence.py compare-control-migration \
		--before-pages .claude/ui_snapshots/ux1b/recovery/precontrol-pages-$(UX1B_RECOVERY_ID)/manifest.json \
		--after-pages .claude/ui_snapshots/ux1b/recovery/canonical-pretheme-$(UX1B_RECOVERY_ID)/manifest.json \
		--before-controls .claude/ui_snapshots/ux1b/recovery/precontrol-controls-$(UX1B_RECOVERY_ID)/manifest.json \
		--after-controls .claude/ui_snapshots/ux1b/recovery/postcontrol-controls-$(UX1B_RECOVERY_ID)/manifest.json \
		--out .claude/ui_snapshots/ux1b/recovery/control-migration-$(UX1B_RECOVERY_ID).json
```

`ui-ux1b-recovery-tests` runs the focused Python test commands below. The
capture targets additionally invoke `ui_ux_evidence.py verify-manifest` for
each output with the exact phase and expected count (`81` or `36`) before
returning success. The migration verifier atomically writes a terminal report
and exits nonzero on any unauthenticated manifest/artifact, capture-stack drift,
unmapped difference, or geometry-rule failure.

Run from the repository root with the existing virtual environment:

```bash
UX1B_RECOVERY_ID=20260716T000000Z
make ui-ux1b-recovery-tests
make ui-ux1b-recovery-precontrol UX1B_RECOVERY_ID="$UX1B_RECOVERY_ID"
# Task 8 changes only the exact nine production selector files.
make ui-ux1b-recovery-postcontrol UX1B_RECOVERY_ID="$UX1B_RECOVERY_ID"
make ui-ux1b-recovery-verify-migration UX1B_RECOVERY_ID="$UX1B_RECOVERY_ID"

.venv/bin/python -m py_compile \
  scripts/ui_ux_isolation.py \
  scripts/ui_ux_evidence.py \
  scripts/ui_ux_browser_worker.py \
  scripts/ui_ux_fixtures.py \
  scripts/ui_ux_fixture_app.py \
  scripts/ui_ux_selection_fixture_app.py \
  scripts/ui_ux_snapshot_matrix.py \
  scripts/ui_ux_theme_fixture_app.py \
  scripts/ui_ux_theme_matrix.py \
  ui/risk_guard.py ui/institutions.py ui/options_cockpit.py ui/radar.py \
  ui/knowledge_graph.py ui/ai_chat.py ui/retro_analysis.py \
  ui/analytics_db.py ui/stock_checkup.py

.venv/bin/python scripts/test_ui_ux_isolation.py
.venv/bin/python scripts/test_ui_ux_evidence.py
.venv/bin/python scripts/test_ui_ux_selection_fixture.py
.venv/bin/python scripts/test_ui_accessible_selection_controls.py
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/test_ui_ux_theme.py
.venv/bin/python scripts/test_ui_ux_theme_matrix.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_ui_ux1a_safety.py
.venv/bin/python scripts/test_ui_ux_components.py
.venv/bin/python scripts/test_artifact_loader.py
.venv/bin/python scripts/test_api.py

make test
make ui-ux1b-legacy UX1B_RUN_ID="recovery-$UX1B_RECOVERY_ID"

.venv/bin/python -m compileall -q api scripts ui
.venv/bin/pip check

.venv/bin/python - <<'PY'
import ast
from pathlib import Path

for root in (Path("api"), Path("scripts"), Path("ui")):
    for path in root.rglob("*.py"):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )
PY

.venv/bin/python scripts/ui_ux_evidence.py verify-prechange \
  --contract docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json \
  --require-parent-sha 48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7 \
  --verify-protected --verify-historical

.venv/bin/python scripts/ui_ux_evidence.py verify-scope \
  --contract docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json \
  --allow-selector-files \
  ui/risk_guard.py ui/institutions.py ui/options_cockpit.py ui/radar.py \
  ui/knowledge_graph.py ui/ai_chat.py ui/retro_analysis.py \
  ui/analytics_db.py ui/stock_checkup.py

git diff --check
rg -n "segmented_control" app.py ui
```

The final `rg` command must return no matches. The historical target must still
produce UX-0 21/21 and UX-1A 20/20 terminal manifests whose protected artifact
hashes pass `verify-prechange`. The semantic-color browser gallery is not run
here because its accepted CSS does not exist until parent Task 3; its Python
contract tests do run. Mock-only tests cannot satisfy Tasks 6, 8, or 9.

## Risk Controls and Rollback

- Never delete or rewrite the accepted parent plan or historical evidence.
- Never run a destructive Git command. Restore only run-owned artifacts or
  exact plan-owned hunks after compare-and-swap hash checks.
- A selector rollback touches only the exact eleven production hunks in the
  nine production files. Each live hunk must match its recorded postimage; it
  restores the context-anchored preimage and must not restore a whole dirty
  production file.
- Theme fixture/oracle files belong to the tooling rollback, never selector
  rollback. Tooling whole-file restoration requires live bytes to match the
  recorded plan posthash and uses the authenticated prechange bundle; created
  files may be removed only under exact path/owner/posthash checks.
- Once pre-control evidence is retained, capture-stack tooling is immutable.
  Rolling it back invalidates and quarantines those manifests rather than
  continuing to reference them.
- The parent four-file theme rollback boundary remains unchanged and is not
  exercised during this recovery.
- Production JSON/API loaders and their fail-soft semantics are protected. Any
  new crash on missing, partial, malformed, or wrong-shaped artifacts is a
  blocking regression.
- Network access remains denied for evidence. No browser login, external
  service, provider refresh, or production write is authorized.

## Completion Definition

Do not claim completion unless:

1. the accepted plan and ADR hashes match the prechange record;
2. the dual sandbox calibrates and all adversarial tests pass;
3. pre-control and canonical pre-theme pages are authenticated 81/81, and the
   focused pre/post control matrices are authenticated 36/36;
4. `captureStackDigest` is unchanged and the migration comparator reports
   differences only under the eleven reviewed roots and the formal unique-
   boundary y-translation rule;
5. all eleven production segmented calls are gone;
6. behavior, AX, keyboard, and mobile-layout gates pass;
7. the theme gallery contract/fixture covers horizontal radio and selectbox
   without synthetic segmented semantics, while its semantic-color browser run
   remains correctly gated on parent Task 3;
8. fail-soft artifact/API tests pass;
9. actual diff matches the accepted plan and no unrelated dirty edit is
   overwritten;
10. a final changed-code review has no blocking finding;
11. every unavailable check is explicitly reported rather than implied to pass.

At that point, and only then, continue with the parent UX-1B semantic-theme
Task 3.
