# Quant Radar UX-1B Sequence 20 Prerequisite Live-Authority Baseline Correction

## Document Control

| Field | Value |
|---|---|
| Type | Prerequisite correction implementation plan |
| Version | `1.1-reviewed` |
| Status | `REVIEWED — ready for exact-byte acceptance; no implementation authority yet` |
| Date | 2026-07-31 |
| Author | Scribe |
| Reviewer | Judge independent local review, then repository maintainer |
| Audience | Maintainer, implementation agent, formal-state reviewer |
| Sequence effect | No new formal sequence; prerequisite to amending Sequence 20 |
| Blocked successor | Sequence 20 post-W0 lifecycle-test correction |
| Sibling ledger | Same basename with `.traceability.yaml` |

## Purpose and Ordered Handoff

The accepted Codex/API migration and other retained live-worktree changes are
not disposable. They moved dependency, fixture, UI-auth, and runtime bytes
after earlier UX-1B sequences had recorded exact live authority. A fresh
coordinator run now reports:

```text
135/176 passed
0 controlled missing-behavior failures
41 unexpected failures
```

Seven failures are the already-planned Sequence 20 targets:

```text
TEST-200 TEST-202 TEST-203 TEST-206 TEST-207 TEST-208 TEST-209
```

The other 34 failures must be corrected first. This prerequisite has one
observable completion state:

```text
169/176 passed
0 controlled missing-behavior failures
7 unexpected failures
```

The seven unexpected IDs must be exactly the Sequence 20 set above, with no
workspace-guard failure. Reaching that state does not authorize Sequence 20
implementation. The required order is:

1. accept this reviewed prerequisite plan and ledger by exact bytes;
2. implement and verify only the 34-failure correction;
3. freeze the resulting seven-only live baseline;
4. amend the blocked Sequence 20 plan and ledger with the final bytes,
   prerequisite lineage, package geometry, and verification evidence;
5. independently review and accept that amendment;
6. only then begin Sequence 20 source implementation.

This plan creates no authorization candidate and grants no bootstrap,
preflight, review-publication, capture, comparison, handoff, or theme-root
write authority.

## Exact Entry State

### Bound live inputs

| Path | SHA-256 | Size | Mode | Disposition |
|---|---|---:|---:|---|
| `requirements.txt` | `1ab5cc81e8e3aab7a3b48b80449087ddf250d22b12b1a8b9b4f5e46b0e790138` | 351 | `0644` | Preserve; accepted Codex/API dependency state |
| `scripts/ui_ux_inventory.py` | `a73d6f6df1c05918d53ec80ef1f640b61d54e6ff1eebf053bd0490671d84edbf` | 58246 | `0644` | Planned narrow parser hardening |
| `scripts/ui_ux_fixtures.py` | `41ca99117039d2005dbee9fae1ed99d899ebccbc68e444afd96ffce1642cf537` | 143239 | `0644` | Preserve; bind as current snapshot-subset input |
| `scripts/ui_ux_evidence.py` | `4835c2e73c46274c77c232166d2e48ec0ccef49542a9a9dd2811b0d5b6ed39c9` | 417548 | `0644` | Preserve; exact historical validator source |
| `scripts/ui_ux_theme_handoff.py` | `6619c9e436f861c3507605e586e7225232c9f2250044496839a743884c250371` | 1930716 | `0644` | Planned history/live authority split |
| `scripts/test_ui_ux_theme_handoff.py` | `61897c377422e6bcf9b50f513ff6afe8db9e3882ee1f10b8a4a2845e9d382142` | 1290498 | `0644` | Planned lifecycle-aware test correction |
| `Makefile` | `b8aebb969a1fe869a83e9193228f0e7aabb1b63a53616c59000ff4b973b61736` | 73790 | `0644` | Preserve in this prerequisite |
| `ui/us_cot.py` | `e5f153faf3fa028f14ffbac67e640d01b8035135697bb21221c861f73d755c40` | 12651 | `0644` | Preserve; inventory regression input |
| `ui/x_sentiment.py` | `163d27607861e0ac1f8026152474594b90010b2da6a131b5a046ed534bdedf0c` | 40741 | `0644` | Preserve; inventory regression input |

Before implementation, all nine entry records must be rehashed. Any mismatch
blocks execution and requires plan amendment; an implementer must not silently
rebase constants or fixtures.

### Immutable historical inputs

| Role | Exact authority |
|---|---|
| Theme-batch requirements preimage | `.claude/ui_snapshots/ux1b/rollback-source/requirements.txt`, SHA-256 `123fd3ee1559a93cf1e30efcf327dd93f6e8604cfa1a6a13487d6de6f3da7d16`, 426 bytes, mode `0644` |
| Sequence 8 runtime identity | `/private/tmp/qr-ux1b-s8` as stored in accepted history; the ephemeral directory is currently absent |
| Sequence 12 runtime profile | Stored tree SHA-256 `9f697d177212f83313b6680892d0b722f1fc874a73e609138354fdab77915b75` and the accepted metadata record |
| Sequence 13 capture-stack file | `docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json`, SHA-256 `a6dc1f4b97e727f7b641b845004e61b0a773b8a247af7ae6ddc38bac6c5b95c7`, 5429 bytes, mode `0600` |
| Sequence 13 historical fixture member | `scripts/ui_ux_fixtures.py`, SHA-256 `afb269fab1de91a8376d4ac1c61df7d7dff96ca31c03a2e6acea36f1e546cd43`, 143247 bytes, stored mode `0644` |

The current `.venv` diagnostic tree SHA-256 observed during planning is
`89632bf339f3b93b17e0211e1698ca47ffb92895c783a74480e42a8830f424f5`.
It is deliberately not new authority: a virtual environment is mutable, and
refreshing an old exact pin to whatever exists today would repeat the same
lifecycle defect.

### Blocked Sequence 20 records

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence20-post-w0-lifecycle-test-correction-continuation.md` | `055efe92c49801a8f68c98735c03e4fee4f6c67cdd6f88a0195d4c07842489f6` | 55737 | `0644` |
| Same basename with `.traceability.yaml` | `6b0b5ca6764df34e996ed6874f90aabadec711a6e37c9ae242bcddf6f689a91c` | 19064 | `0644` |

Those files remain unchanged during correction phases P0–P6. Their
`APPROVE_BLOCKED` disposition remains correct until the seven-only baseline
and reviewed amendment both exist.

## Failure Inventory and Root Cause

The 34 failures form six bounded clusters.

| Cluster | Test IDs | Count | First observed failure | Root cause |
|---|---|---:|---|---|
| `BLC-A` | `005,006,013,026,033,034,035` | 7 | `theme-batch live preimage differs: requirements.txt` | Legacy Sequence 8 behavior tests replay an old operation against the migrated live dependency file instead of a lifecycle-scoped source fixture. |
| `BLC-B` | `017` | 1 | `TB-SCRATCH-007-CLASSIFICATION` returns `internal_exception` | `_constant_categories()` passes the regex literal `https://[^\s\x1b]+` to `urlsplit()`, whose bracket validation raises `ValueError`. |
| `BLC-C` | `021` | 1 | `snapshot subset protected source is unauthenticated: scripts/ui_ux_fixtures.py` | Current candidate closure still pins the pre-migration fixture member while the retained current fixture changed by eight bytes. |
| `BLC-D` | `081,084,096,098,099,100,101,102,103` | 9 | `Sequence 8 runtime root is unavailable` | Later historical importers re-read an intentionally ephemeral Sequence 8 runtime directory instead of authenticating its stored receipt. |
| `BLC-E` | `121,158,164,178,183,184,186,187,189,195,196` | 11 | `Sequence 12 current runtime authority differs` | Sequence 13-and-later history/replay paths still treat the old `.venv` inode/tree as current live authority. |
| `BLC-F` | `136,148,149,150,151` | 5 | `capture-stack member bytes or metadata changed` | Sequence 13's accepted embedded stack is now historical, but Sequence 14 paths rehash its member declarations against migrated live files. |

Counts are closed: `7 + 1 + 1 + 9 + 11 + 5 = 34`.

These are lifecycle-boundary failures, not permission to weaken exact
authentication. Historical import must continue authenticating retained
bytes and semantic relationships; live operations must continue rejecting
drift.

## Decision Summary

1. Preserve every concurrent migration change and every accepted formal
   artifact. Do not reset, checkout, delete, regenerate, or overwrite them.
2. Split historical import from live reauthentication. Historical paths
   validate retained records and embedded receipts without touching
   ephemeral/current resources; live paths continue to rehash current bytes
   and fail closed on drift.
3. Keep the original theme-batch preimage hash immutable. Only the seven
   lifecycle tests receive a narrow, exact migrated-live source fixture.
4. Treat URL-looking regex literals as analyzable strings, not valid URLs.
   Malformed literal URLs must not crash inventory; real valid URLs retain
   URL/host/port classification.
5. Update only the current snapshot-subset closure entry for
   `scripts/ui_ux_fixtures.py`. Do not modify the Sequence 13 capture-stack
   member declaration or its file.
6. Add no coordinator IDs and reclassify no exception as a controlled
   missing-behavior result. The denominator remains exactly 176.
7. Stop at the seven-only baseline. Sequence 20 amendment and implementation
   are a separately reviewed continuation.

## Scope

### Files allowed to change during correction implementation (P0–P6)

- `scripts/ui_ux_inventory.py`
- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- this plan and its sibling traceability ledger only for review corrections
- `.agents/scribe.md`, `.agents/judge.md`, and one task row in
  `.agents/PROJECT.md`

### Successor documentation scope after P6

This prerequisite's acceptance does not authorize editing the blocked
Sequence 20 records. After P6 has passed implementation review, a new
maintainer instruction may open a documentation-only continuation whose
write scope is exactly:

- the blocked Sequence 20 plan;
- its sibling Sequence 20 traceability ledger;
- review/project journals.

That continuation must first rehash the final P6 baseline, then amend and
review the two Sequence 20 records. It cannot edit source, tests, formal
artifacts, or create an authorization candidate. Sequence 20 implementation
still requires exact acceptance of the reviewed amended plan and ledger.

### Protected read-only inputs

- `requirements.txt`
- `scripts/ui_ux_fixtures.py`
- `scripts/ui_ux_evidence.py`
- `Makefile`
- `ui/us_cot.py`
- `ui/x_sentiment.py`
- every `.claude/ui_snapshots/ux1b/**` artifact
- every `docs/ui-ux/**` formal artifact
- all Sequence 1–20 accepted or blocked plans, ledgers, and authorizations
- API, Streamlit page, provider, deployment, workflow, and data-pipeline code

### Explicitly out of scope

- editing the seven Sequence 20 target tests
- adding `TEST-210` or any later coordinator test
- changing the accepted Codex/API migration behavior
- dependency installation or lock regeneration
- recreating `/private/tmp/qr-ux1b-s8`
- rebinding Sequence 12 to the current `.venv`
- rebuilding Sequence 13 capture-stack JSON from current files
- formal bootstrap/preflight/publication/capture/comparison writes
- git cleanup or unrelated worktree normalization

## Requirements

### `REQ-023` — Restore the exact seven-only Sequence 20 entry baseline

Correct all and only the 34 non-Sequence 20 failures while preserving
current migration behavior, immutable formal history, and the original seven
Sequence 20 failures.

### `CFR-117` — Theme-batch historical/live source separation

The seven `BLC-A` tests must run their legacy transition matrices under a
narrow exact source fixture that binds the current migrated requirements
record without changing `THEME_BATCH_PREIMAGE_SHA256`. TEST-005 must also
prove that the immutable rollback requirements record still has the original
SHA-256, size, and mode. The fixture must restore all patched state even when
a test raises.

### `CFR-118` — Total inventory parsing for string constants

`_constant_categories()` must be total for every Python string constant.
A value beginning with `http://` or `https://` that is not a syntactically
valid URL may retain the coarse `url` category, but must not raise and must
not invent host or port claims. Valid URL behavior is unchanged. TEST-017
must explicitly cover both migrated regex literals and a valid URL.

### `CFR-119` — Current snapshot-subset closure

The current candidate closure must bind
`scripts/ui_ux_fixtures.py` to SHA-256
`41ca99117039d2005dbee9fae1ed99d899ebccbc68e444afd96ffce1642cf537`
and 143239 bytes. Sequence 13's stored member record remains the historical
`afb269...`/143247 record. TEST-021 must prove current-candidate success and
one-byte fixture drift rejection.

### `CFR-120` — Sequence 8 history import without runtime resurrection

Refactor Sequence 8 predecessor validation into a common exact artifact core
and two explicit policies:

- live reauthentication retains the empty runtime-root check;
- historical import authenticates the stored runtime receipt and exact
  accepted artifacts but performs no `is_dir`, `walk`, `lstat`, or read below
  `/private/tmp/qr-ux1b-s8`.

Every Sequence 9-and-later call site that consumes Sequence 8 only as
retained lineage must use the history policy, including later root-candidate
reconstruction. The only production live-policy allowlist remains the two
fresh Sequence 9 operation builders
`_build_continuation_preflight_value()` and
`_bootstrap_continuation()`. Tests must prove the live policy still rejects
the absent runtime, the history policy succeeds without runtime filesystem
calls, and every `_reauthenticate_sequence8_predecessor()` call site is
classified into that closed allowlist or migrated.

### `CFR-121` — Sequence 12 stored runtime receipt

Add a history importer that derives the exact Sequence 12 runtime profile
from an authenticated retained preflight/authority record. It must compare
the entire stored profile to `SEQUENCE12_CURRENT_RUNTIME_PROFILE` as
historical data without reading the current `.venv`.

Every Sequence 13-and-later call site currently invoking live Sequence 12
runtime reauthentication must accept or obtain that stored receipt
explicitly; there is no later live-call exception because those phases
consume the runtime only as retained lineage. The original live
`_reauthenticate_sequence12_runtime()` remains fail-closed and TEST-121 must
prove it rejects the migrated current `.venv`. No current tree digest may be
copied into an old authority constant.

### `CFR-122` — Sequence 13 embedded capture-stack history

Add a Sequence 13 history importer, preferably by extracting a shared pure
embedded-stack validator from the existing Sequence 14 legacy importer. It
must authenticate:

- the exact Sequence 13 stack file record and canonical JSON;
- nine sorted unique member declarations and their stored metadata;
- exact base/capture/root-expansion digests;
- the registered control catalog and worker catalog;
- stable reopening of the stack file.

It must not call `_capture_stack_records()`, open any declared live member,
or compare stored members to current live bytes. Every downstream call site
that consumes the accepted Sequence 13 stack uses this history importer,
including superseded Sequence 13 replay helpers and Sequence 14-and-later
history paths. The existing live Sequence 13 reauthenticator remains
available only as an explicit drift guard and must still reject current
member drift. All call sites must be enumerated before and after the edit;
none may remain accidentally live.

### `CFR-123` — Exact failure-budget and compatibility gate

No correction is complete until the full coordinator reports exactly
`169/176`, zero controlled failures, seven unexpected failures with the exact
Sequence 20 IDs, and no workspace-guard failure. Fail-soft artifact-loader
tests must remain exactly `14/14`; API tests must remain exactly `44/44`.
Syntax checks, inventory/UX contract tests, and current Codex migration
contract tests must remain green.

## Design and Implementation Checklist

### Phase P0 — Preflight and fail-first preservation

- [ ] `IMPL-182`: Rehash all bound live inputs and verify protected formal
  paths have not changed.
- [ ] `IMPL-183`: Run or reuse a same-byte fresh coordinator reproduction and
  assert the exact 34+7 partition before editing.
- [ ] `IMPL-184`: Record a protected-path fingerprint for every out-of-scope
  input named above.

Blocking condition: any entry hash mismatch, any new test ID, or any formal
path write stops implementation.

### Phase P1 — Inventory and current closure

- [ ] `IMPL-185`: In `scripts/ui_ux_inventory.py`, catch `ValueError` from URL
  splitting before accessing hostname/port; preserve coarse safe taint.
- [ ] `IMPL-186`: Extend TEST-017 with malformed URL-regex and valid
  URL/host/port assertions, then verify all seven scratch checks pass.
- [ ] `IMPL-187`: Update only the `scripts/ui_ux_fixtures.py` entry in
  `SNAPSHOT_SUBSET_CLOSURE`; extend TEST-021 to reject a one-byte candidate
  mutation.

Expected checkpoint: `BLC-B` and `BLC-C` are green; no other failure count
may increase.

### Phase P2 — Theme-batch lifecycle fixture

- [ ] `IMPL-188`: Replace the broad `_with_current_runtime_fixture` naming
  and behavior with an explicit legacy Sequence 8 fixture (or a narrower
  composed helper) that binds the exact current requirements record only
  for `BLC-A`.
- [ ] `IMPL-189`: Add immutable rollback-record assertions and restoration
  checks. Do not alter the production preimage constant.
- [ ] `IMPL-190`: Apply the fixture only to
  TEST-005/006/013/026/033/034/035; retain all existing crash, collision,
  descriptor, and fail-closed assertions.

Expected checkpoint: all nine `BLC-A/B/C` tests are green.

### Phase P3 — Sequence 8 runtime history

- [ ] `IMPL-191`: Extract the exact Sequence 8 artifact validation core and
  implement disjoint live and historical runtime policies.
- [ ] `IMPL-192`: Audit every Sequence 8 predecessor call site. Route all
  retained-lineage consumers through the history policy, including both
  later root-candidate builders; retain live policy only in the exact
  two-function fresh-operation allowlist.
- [ ] `IMPL-193`: Update TEST-081/084/096/098/099/100/101/102/103 to prove
  stored-receipt success, zero ephemeral-root reads, mutation rejection, and
  retained live failure.

Expected checkpoint: all nine `BLC-D` tests are green.

### Phase P4 — Sequence 12 runtime lifecycle

- [ ] `IMPL-194`: Implement the exact stored-runtime importer and explicit
  receipt injection seam.
- [ ] `IMPL-195`: Enumerate and replace every Sequence 13-and-later call to
  live `.venv` reauthentication with the stored receipt. Keep the original
  live function only for the direct fail-closed guard; no downstream
  builder/importer remains on it.
- [ ] `IMPL-196`: Make TEST-121 lifecycle-aware and update the ten later
  disposable lifecycle tests without weakening create-once, atomicity,
  descriptor, prefix, or mutation coverage.

Expected checkpoint: all eleven `BLC-E` tests are green. A current `.venv`
rehash during historical import is a blocking defect even if tests pass.

### Phase P5 — Sequence 13 capture-stack lifecycle

- [ ] `IMPL-197`: Extract or add the pure embedded capture-stack history
  validator and stable-reopen guard.
- [ ] `IMPL-198`: Enumerate every live Sequence 13 stack call site and route
  every retained-lineage/replay consumer through the history importer while
  retaining the live helper only for direct drift rejection.
- [ ] `IMPL-199`: Update TEST-136/148/149/150/151 with zero-live-member-read,
  stored-member mutation, catalog mutation, and live-drift assertions.

Expected checkpoint: all five `BLC-F` tests are green.

### Phase P6 — Full closure and diff audit

- [ ] `IMPL-200`: Run the exact coordinator and assert the seven-only result.
- [ ] `IMPL-201`: Run focused compatibility checks listed below.
- [ ] `IMPL-202`: Compare the diff to this file list; revert or explain any
  unexplained scope drift without touching user-owned unrelated changes.
- [ ] `IMPL-203`: Rehash every protected input and prove no formal namespace
  leaf changed.
- [ ] `IMPL-204`: Review changed code for runtime errors, weakened
  authentication, un-restored patches, hidden current filesystem reads, and
  missing negative tests; fix blocking findings and rerun all gates.

### Post-P6 successor workflow — not authorized by this plan

After returning the reviewed P6 evidence, the next documentation-only
continuation must:

1. freeze final SHA-256, size, and mode for Makefile, requirements, fixtures,
   inventory, evidence, handoff source, and test;
2. amend the existing Sequence 20 plan and ledger: remove the
   overlapping-drift blocker, import this exact prerequisite lineage, record
   the seven-only baseline, update affected-file authority, and recalculate
   package/projection/descriptor geometry from unique exact paths;
3. independently review the amendment and resolve all blocking findings;
4. obtain exact maintainer acceptance of the amended Sequence 20 plan/ledger
   before beginning Sequence 20 implementation.

This successor is documentation/review work only. It requires the distinct
scope-opening instruction described above and does not authorize a Sequence
20 candidate or formal write.

## Test Specification

### Positive scenarios

| ID | Requirement | Given / When | Expected result |
|---|---|---|---|
| `SC-AC-BLC-002-HP-001` | `CFR-117` | Given original historical preimage plus the exact migrated-live test fixture, when legacy crash matrices run | Seven `BLC-A` tests pass and production preimage remains unchanged |
| `SC-AC-BLC-003-HP-001` | `CFR-118` | Given a migrated login regex constant, when inventory taint analysis runs | It returns a bounded category set without raising |
| `SC-AC-BLC-004-HP-001` | `CFR-119` | Given exact current fixture bytes, when candidate subset authentication runs | TEST-021 passes |
| `SC-AC-BLC-005-HP-001` | `CFR-120` | Given exact retained Sequence 8 records and absent runtime root, when a later history importer runs | It succeeds with zero runtime-root reads |
| `SC-AC-BLC-006-HP-001` | `CFR-121` | Given exact retained Sequence 12 runtime receipt and migrated `.venv`, when later lifecycle fixtures run | They use stored authority and succeed |
| `SC-AC-BLC-007-HP-001` | `CFR-122` | Given exact Sequence 13 embedded stack and changed live member bytes, when historical import runs | Stored semantics authenticate without live-member reads |
| `SC-AC-BLC-001-HP-001` | `REQ-023`,`CFR-123` | Given all six clusters corrected, when the coordinator runs | Exact seven-only `169/176` baseline |
| `SC-AC-BLC-008-HP-001` | `CFR-123` | Given the implementation diff, when protected inputs are rehashed | Every out-of-scope input remains byte-exact |

### Negative and boundary scenarios

| ID | Requirement | Mutation / boundary | Expected result |
|---|---|---|---|
| `SC-AC-BLC-002-NP-001` | `CFR-117` | Original rollback record or exact migrated requirements fixture drifts | Fail before legacy transition; patch state restored |
| `SC-AC-BLC-003-BP-001` | `CFR-118` | Valid URL with hostname and explicit port | URL, host, and port categories remain present |
| `SC-AC-BLC-003-NP-001` | `CFR-118` | Bracketed regex/non-URL text reaches `urlsplit` | No exception and no fabricated host/port |
| `SC-AC-BLC-004-NP-001` | `CFR-119` | One byte of candidate fixture differs | Candidate subset fails before execution |
| `SC-AC-BLC-005-NP-001` | `CFR-120` | Stored Sequence 8 receipt or accepted artifact differs | Historical import fails closed without runtime reads or writes |
| `SC-AC-BLC-006-NP-001` | `CFR-121` | Stored runtime profile differs | Historical import fails; no fallback to current `.venv` |
| `SC-AC-BLC-006-BP-001` | `CFR-121` | Old live reauthentication observes current migrated `.venv` | It remains a deliberate contract violation |
| `SC-AC-BLC-007-NP-001` | `CFR-122` | Stack file/member declaration/catalog/digest changes | Historical import fails before live-member access |
| `SC-AC-BLC-007-BP-001` | `CFR-122` | Live Sequence 13 reauthentication sees migrated fixture bytes | It remains a deliberate drift rejection |
| `SC-AC-BLC-001-NP-001` | `CFR-123` | Any non-target failure remains or any Sequence 20 target turns green | Prerequisite gate fails; do not amend Sequence 20 |
| `SC-AC-BLC-008-NP-001` | `CFR-123` | Any protected input or formal path changes | Correction is rejected as scope drift |

## Acceptance Criteria

### `AC-BLC-001` — Exact seven-only baseline

All 34 listed IDs pass, no unlisted coordinator behavior changes, and a fresh
full run reports the exact `169/176` result and seven-ID set.

### `AC-BLC-002` — Theme-batch lifecycle fixture

The seven `BLC-A` tests pass under the exact scoped fixture while original
historical preimage authority remains unchanged and independently verified.

### `AC-BLC-003` — Inventory parser totality

Migrated URL regex constants do not crash analysis, while valid URL
classification retains its prior URL/host/port semantics.

### `AC-BLC-004` — Current snapshot closure

The current fixture is authenticated by exact bytes and a one-byte candidate
mutation fails before execution; historical Sequence 13 membership is
unchanged.

### `AC-BLC-005` — Sequence 8 history/live separation

Later history import succeeds without ephemeral-root reads, and the old live
reauthenticator still rejects the absent root.

### `AC-BLC-006` — Sequence 12 history/live separation

Later history/replay uses the exact stored receipt without current `.venv`
reads, and old live reauthentication still rejects current drift.

### `AC-BLC-007` — Sequence 13 history/live separation

Embedded historical stack semantics authenticate without member reads, and
the live reauthenticator still rejects changed member bytes.

### `AC-BLC-008` — Concurrent migration preservation

Requirements, fixtures, Makefile, UI login flows, evidence source, API
behavior, and Codex migration behavior remain byte-exact except for the three
explicit implementation files.

## Verification Commands

Run from repository root with the protected-path fingerprint checked before
and after:

```bash
.venv/bin/python -B -m py_compile \
  scripts/ui_ux_inventory.py \
  scripts/ui_ux_theme_handoff.py \
  scripts/test_ui_ux_theme_handoff.py

.venv/bin/python -B scripts/test_ui_ux_contract.py
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_codex_auth_flow.py
.venv/bin/python -B scripts/test_llm_client_codex.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
```

For the coordinator, retain the complete output and mechanically assert:

- denominator `176`;
- passed `169`;
- controlled missing-behavior failures `0`;
- unexpected failures `7`;
- unexpected ID set exactly
  `{200,202,203,206,207,208,209}`;
- no `WORKSPACE-GUARD` line.

For compatibility gates, retain the summaries and mechanically assert
artifact-loader `14/14` and API `44/44`; do not accept a zero exit status with
fewer registered tests.

If a verification command cannot run, report it as unresolved. A skipped
relevant command is not equivalent to a pass.

## Risk Controls and Rollback

- Apply small patches in cluster order and run the affected IDs after each
  cluster. Do not mask a failure by broad exception catching.
- Historical importers may trust only authenticated retained bytes, never
  arbitrary in-memory fixtures supplied by public callers.
- Optional injected receipts are private test/replay seams and must be
  validated exactly before use.
- Every `patch.object`/`patch.dict` scope must be a context manager with a
  restoration assertion.
- Do not use the current `.venv` tree digest as a stable constant.
- Do not change the Sequence 13 stack file to match current fixture bytes.
- If fixing one root cause reveals a latent non-Sequence 20 failure, classify
  it against these requirements. If it needs another file or authority
  model, stop and amend this plan rather than expanding scope silently.
- Rollback of this prerequisite is limited to its three implementation files.
  Formal artifacts and concurrent user changes are never rollback targets.

## Review Gates

Before implementation, Judge must confirm:

- the six clusters and 34-ID count are exact;
- no protected live migration input is scheduled for modification;
- history paths authenticate retained bytes rather than accepting unchecked
  fixtures;
- old live paths remain fail-closed;
- the test denominator remains 176;
- the correction stops at P6 and the separately scoped Sequence 20
  amendment/acceptance boundary is explicit.

Any likely runtime error, weakened authentication, protected-file write,
unbounded scope, or inability to verify the seven-only gate is blocking.

## Review Result

Judge verdict: `APPROVE`.

- The first independent review found two blockers: three non-reciprocal
  implementation edges and a contradiction between protected Sequence 20
  records and the former in-package amendment phase.
- The ledger edges were corrected to exact `28/28` bidirectional
  implementation links.
- The amendment work was removed from this implementation package; the
  correction now stops at P6 and requires a new narrowly scoped maintainer
  instruction before the successor documentation continuation.
- Re-review found no remaining MEDIUM-or-higher blocker and confirmed exact
  `19/19` bidirectional scenario links, 34 unique non-target IDs, six closed
  failure clusters, denominator 176, artifact-loader cardinality 14, and API
  cardinality 44.
- The Claude reviewer runtime was unavailable because the local CLI is not
  logged in. The Codex reviewer runtime did not emit a verdict within its
  bounded window and was terminated. No findings were invented for either
  unavailable engine.

This review approves the plan design only. Implementation remains blocked
until the repository maintainer accepts the final plan and ledger by exact
SHA-256, byte size, and mode.

## Handoff

When reviewed and accepted, hand this prerequisite to the implementation
agent. The implementation agent must stop after P6 and return the exact diff
and verification evidence for review. A new maintainer instruction may then
open the narrowly scoped Sequence 20 documentation amendment. No part of
this document is a formal-state execution authorization.
