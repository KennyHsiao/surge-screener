# UX-1B TEST-021 Task 1 Semantic Evidence Implementation Replacement Plan

## Document control

| Field | Value |
| --- | --- |
| Version | v0.3 |
| Status | Review candidate; implementation remains blocked until PASS |
| Date | 2026-07-21 |
| Author | Codex / Scribe |
| Parent authority | `docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md` |
| Parent SHA-256 | `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581` |
| Parent ledger SHA-256 | `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8` |
| Accepted evidence matrix | `docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-matrix-replacement.md` |
| Matrix SHA-256 | `f0bd99afeec74e8f11cd2fd49794fd244a8ac6a9c93ad60e74bbe8057fe7db5b` |
| Matrix review | Fresh iteration 3 PASS; 0 blocker, 0 high, 0 medium |
| Rejected predecessor | `2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-remediation.md` v0.3; immutable and non-authoritative |

## Outcome

Implement the accepted semantic-evidence matrix as Task 1 fail-first contract
tests and import-safe production declarations. This plan does not implement
candidate capability behavior. On completion the module remains intentionally
red:

```text
0/29 passed; 29 controlled missing-behavior failures; 0 unexpected failures
```

The new TEST-021 helpers must nevertheless prove their own fitness: a
test-owned unmutated reference twin passes; all 44 recipe-qualified Q cases,
all 15 cross-cutting M mutants, and every closed fault-table row fail at their
named oracle. Once Task 2 implements the production seams, the same helpers
switch to the production concrete functions and require the full semantic and
real-integration branches.

## Pre-implementation review result

The accepted matrix resolved the repeated blocker rather than renaming it:

- all 194 composites are frozen and exhaustive;
- all 44 recipes have one result owner and one applicable Q kill;
- `socket.socketpair()` is zero-argument;
- child execution has exact bounds and disjoint fresh PGID cleanup;
- browser production and post-exit validation are causally separate;
- no renderer/headless PID enumeration race was added;
- the observer result, parser grammar, and pre/post-reap lifecycle match the
  immutable parent;
- same-process audit/HMAC data is corroborating attempt evidence, never the
  sole semantic result authority.

No blocking issue is known at plan authoring. Any implementation divergence
from the matrix SHA above blocks execution and requires a fresh reviewed plan.

## Scope and frozen preimages

### Files that may change

| File | Allowed change |
| --- | --- |
| `scripts/ui_ux_theme_handoff.py` | Typing imports; closed Protocol/TypedDict/type-alias declarations; the exact named TEST-021 seams below, each calling `_missing` immediately |
| `scripts/test_ui_ux_theme_handoff.py` | Matrix generation/oracles, low-level recorders, reference twin, exact Q/M/fault tables, bounded child/browser/observer helpers, and TEST-021 integration |
| This plan | Planning artifact only |
| `.agents/scribe.md`, `.agents/builder.md`, `.agents/radar.md`, `.agents/PROJECT.md` | Required planning/implementation skill records |

### Frozen implementation inputs

| Artifact | SHA-256 | Size |
| --- | --- | ---: |
| `scripts/ui_ux_theme_handoff.py` | `a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6` | 23930 |
| `scripts/test_ui_ux_theme_handoff.py` | `e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee` | 675940 |
| Parent plan | `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581` | 243794 |
| Parent ledger | `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8` | 17155 |
| Accepted matrix | `f0bd99afeec74e8f11cd2fd49794fd244a8ac6a9c93ad60e74bbe8057fe7db5b` | 58086 |

The baseline test command was run on 2026-07-21 and exited `1` with the exact
controlled-red summary above. That exit is expected and is not a regression.

### Mandatory fail-closed workspace, preimage, and ignored-cache guard

Before the first source edit, recheck both target SHA-256 values and sizes from
the table above. Abort on any mismatch. Create one fresh mode-0700 directory
with `mktemp -d /private/tmp/quant-radar-test021.XXXXXX`, retain its path only
in the current implementation session as `TASK1_PRIVATE_PREIMAGE_DIR`, and copy
the two target files into it with mode 0600. Reopen both copies and require
their hashes/sizes to equal the frozen table before editing.

The private directory is a safety/verification artifact, not a project source
edit. It remains outside the workspace through changed-code review. Record its
path only in the private implementation log, never in a public receipt or
committed artifact.

Before any workspace mutation, also write a canonical baseline manifest into
that private directory. It covers every path under the workspace except
`.git/**` and these exact allowed paths:

```text
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md
.agents/scribe.md
.agents/builder.md
.agents/radar.md
.agents/PROJECT.md
```

For each included entry the canonical manifest records its relative path and
lstat type; for a regular file it also records SHA-256 of all bytes, and for a
symlink its uninterpreted link target. It never follows symlinks. This covers
tracked, untracked, ignored, and clean content alike. Recompute and compare it
after each implementation task, each verification group, and each individual
regression script. Any added, removed, type-changed, link-changed, or
byte-changed out-of-scope path is blocking; do not delete or rewrite that path
to force a match.

Privately preserve the plan and every existing allowed journal as well. At
final scope review the plan must be byte-identical to its accepted preimage;
each journal must be absent as before or consist of its exact preimage plus
only this task's append-only skill entries. Review a no-index diff for every
changed allowed journal. This is separate from the whole-workspace manifest,
which deliberately excludes the allowed paths.

Because both targets are untracked, every diff/scope review uses the private
copies:

```text
assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
```

The helper explicitly accepts only Git exit 0 (no change) or exit 1 (clean
content difference), requires empty whitespace diagnostics, and rejects every
other exit. The unified diffs must contain only plan-authorized hunks.

Before any other Python command, compute and retain an in-memory fingerprint of all
existing ignored `scripts/**/__pycache__/**` and `*.py[co]` paths plus their
hashes using `rg --files -uu scripts`, sorted under `LC_ALL=C`. Run every
Python/import/test command with `PYTHONDONTWRITEBYTECODE=1`. Recompute the exact
fingerprint after all gates; any added, removed, or changed cache path is
blocking. `py_compile` must write its two explicit `cfile` outputs only inside
`TASK1_PRIVATE_PREIMAGE_DIR`, never under `scripts/`.

### Explicitly out of scope

- Task 2 behavior in `scripts/ui_ux_theme_handoff.py`;
- lifecycle, capture, apply, publication, rollback, recovery, or UI behavior;
- the parent plan, ledger, accepted matrix, Makefile, requirements, API, UI,
  deployment, runtime, or evidence artifacts;
- new CLI tokens, environment keys, pass-FDs, stdout fields, public schemas, or
  production subprocess/browser/filesystem/network I/O;
- changing the exact 29-entry `TESTS` tuple.

The dirty worktree contains unrelated user changes. They are neither inputs nor
rollback targets.

## Exact production declaration surface

Add only `Literal`, `Protocol`, `TypeAlias`, and `TypedDict` to the existing
typing import, then add closed declarations for:

- `ProbeSocket` and `InProcessPrimitives`, with the exact method set/signatures
  in the accepted matrix, including `socketpair(self)` with no arguments;
- `ProbeChildPlan` with exactly
  `{id,argv,cwd,environment,stdin,timeoutSeconds,stdoutLimitBytes,
  stderrLimitBytes,passFds,processGroup}`;
- four raw child arms `ProbeChildSpawnDenied`, `ProbeChildCompleted`,
  `ProbeChildTimedOutOrOverflow`, and `ProbeChildSpawnFailed`, plus
  `ProbeChildExecution` as their closed union;
- `ProbeChildExecutor.execute(plan)` returning only
  `ProbeChildExecution`, never an outcome;
- `BrowserApiEvidence` with exactly
  `{apiExecutablePath,observedVersion,launched,pageCreated,pageClosed,
  contextClosed,browserClosed}`;
- `ChildProbeAssertionResult` with exactly `{outcome,execution}`;
- `BrowserBuildResult` with exactly `{outcome,browser}`.

The raw child arms share only these semantic fields:
`kind,argv,pid,processGroupId,returnCode,signal,stdout,stderr,timedOut,
overflowStream,pipesClosed,processFamily,error`. Runtime tests, not permissive
typing, enforce each arm's nullability and exact values from the accepted
matrix. Raw `error` is test/process-local and never serialized.

Add these exact named seams:

```python
def _evaluate_start_probe_assertion(
    assertion_id: str,
    context: Mapping[str, Any],
) -> dict[str, Any]: ...

def _evaluate_token_probe_assertion(
    context: Mapping[str, Any],
) -> dict[str, Any]: ...

def _evaluate_inprocess_probe_assertion(
    assertion_id: str,
    context: Mapping[str, Any],
    *,
    primitives: InProcessPrimitives,
) -> dict[str, Any]: ...

def _execute_probe_child(
    plan: ProbeChildPlan,
    *,
    syscalls: Any | None = None,
) -> ProbeChildExecution: ...

def _evaluate_child_probe_assertion(
    assertion_id: str,
    context: Mapping[str, Any],
    *,
    executor: ProbeChildExecutor,
) -> ChildProbeAssertionResult: ...

def _exercise_browser_api(
    context: Mapping[str, Any],
    *,
    playwright_factory: Callable[[], Any],
) -> BrowserApiEvidence: ...

def _build_browser_probe(
    api: BrowserApiEvidence,
    node_execution: ProbeChildExecution,
    runtime: Mapping[str, Any],
) -> BrowserBuildResult: ...

def _validate_serialized_browser_probe(
    browser: Mapping[str, Any],
    p18: Mapping[str, Any],
    runtime: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    family_receipt: Mapping[str, Any],
    *,
    raw_assertion_bytes: bytes,
    assertion_document: Mapping[str, Any],
) -> None: ...
```

The last two keyword-only inputs make the matrix's existing stdout-byte
equality gate executable; they add no public field. Each Task 1 body is exactly
one `_missing("TEST-021", "...")` call after its signature/docstring. No seam
calls another seam, reads environment, inspects argv, starts a process, imports
Playwright, touches a file/socket, or catches the missing exception.

The existing `_run_capability_probe()` remains a no-argument controlled-missing
stub and the fixed 85-byte bootstrap stays byte-identical. No new public or
private CLI token is added.

The future outer validator first requires the assertion document's exact five
keys and canonical re-encoding to equal `raw_assertion_bytes`; `browser` must
equal that document's browser leaf, and `p18` must be the single positive row
whose ID is `chromium-default-launch-page-close`. It then validates the exact
browser keys/values and profile/family inputs. It cannot accept a separately
constructed browser/P18 pair that is absent from or differs from stdout.

## Test architecture

### Three explicit arms

TEST-021 calls the same private helpers through three closed arms:

1. **Task 1 stub arm:** inspect exact declarations/signatures and require every
   named seam plus `_run_capability_probe` to raise controlled TEST-021 missing
   behavior with no I/O.
2. **Fitness arm:** run a test-owned unmutated reference twin against
   independent trace/schema oracles, then run every Q/M/fault mutant. Expected
   data and reference behavior are separate objects; no reference dispatcher
   may call `_probe_outcome_fixture`, `_probe_browser_fixture`, or the expected
   trace builder.
3. **Task 2 production arm:** when a seam no longer raises the controlled
   missing exception, invoke the production concrete seam/executor through the
   same recorders and require the complete direct and real integration gates.
   Partial implementation is failed/unexpected, never treated as Task 1 red.

Every `test_semantic_*` routine is a private helper called exactly once from
the existing TEST-021 callable. None enters `TESTS`.

### Independent expected data

Add closed test-only constants:

- `SEMANTIC_RECIPE_BY_ASSERTION`: exact 44 assertion-to-recipe map;
- `SEMANTIC_OWNER_BY_RECIPE`: exact 44 recipe-to-owner map;
- `SEMANTIC_QUALIFIED_KILL_BY_RECIPE`: exact 44 one-to-one Q map;
- `SEMANTIC_Q_CASES`, `SEMANTIC_M_CASES`, and the four closed fault tables;
- exact per-recipe primitive trace builders that return expected call tuples
  only and never execute reference behavior.

Generate the 194 composite rows from the existing capability/common/addition
constants and require exact source order, 63/131 counts, 44 recipes, one owner,
one Q case, and no optional row. No production result or parsed report may
generate expected IDs.

## Execution tasks

### Task 0 — Establish fail-closed workspace and preimage guards

**Files:** no workspace file is changed.

Run this initialization as one dedicated zsh session. `set -eu` makes every
failed check abort. The EXIT trap removes only the newly created, prefix-
guarded private directory if initialization is partial. Editing is forbidden
until the final `TASK1_GUARDS_READY=1` marker succeeds.

```sh
set -eu
export TASK1_GUARDS_READY=0
export TASK1_PRIVATE_PREIMAGE_DIR=""
trap 'rc=$?; if (( rc != 0 )) && [[ -n ${TASK1_PRIVATE_PREIMAGE_DIR:-} ]]; then case "$TASK1_PRIVATE_PREIMAGE_DIR" in /private/tmp/quant-radar-test021.*) command rm -rf -- "$TASK1_PRIVATE_PREIMAGE_DIR" ;; esac; fi' EXIT

TASK1_PRIVATE_PREIMAGE_DIR=$(mktemp -d /private/tmp/quant-radar-test021.XXXXXX)
export TASK1_PRIVATE_PREIMAGE_DIR
chmod 0700 "$TASK1_PRIVATE_PREIMAGE_DIR"

source_hash=$(shasum -a 256 scripts/ui_ux_theme_handoff.py)
test "${source_hash%% *}" = a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6
test "$(stat -f %z scripts/ui_ux_theme_handoff.py)" = 23930
test_hash=$(shasum -a 256 scripts/test_ui_ux_theme_handoff.py)
test "${test_hash%% *}" = e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee
test "$(stat -f %z scripts/test_ui_ux_theme_handoff.py)" = 675940

install -m 0600 scripts/ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py"
install -m 0600 scripts/test_ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py"
copy_hash=$(shasum -a 256 "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py")
test "${copy_hash%% *}" = a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6
test "$(stat -f %z "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py")" = 23930
copy_test_hash=$(shasum -a 256 "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py")
test "${copy_test_hash%% *}" = e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee
test "$(stat -f %z "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py")" = 675940

mkdir -m 0700 "$TASK1_PRIVATE_PREIMAGE_DIR/allowed"
install -m 0600 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
install -m 0600 .agents/scribe.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md"
install -m 0600 .agents/builder.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md"
install -m 0600 .agents/PROJECT.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md"
test ! -e .agents/radar.md
test ! -L .agents/radar.md
cmp -s docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
cmp -s .agents/scribe.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md"
cmp -s .agents/builder.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md"
cmp -s .agents/PROJECT.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md"

typeset -a TASK1_ALLOWED_PATHS
TASK1_ALLOWED_PATHS=(
  scripts/ui_ux_theme_handoff.py
  scripts/test_ui_ux_theme_handoff.py
  docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md
  .agents/scribe.md
  .agents/builder.md
  .agents/radar.md
  .agents/PROJECT.md
)

workspace_manifest() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c '
import hashlib, json, os, pathlib, stat, sys
root = pathlib.Path.cwd()
output = pathlib.Path(sys.argv[1])
excluded = frozenset(sys.argv[2:])
rows = []
for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
    current_path = pathlib.Path(current)
    rel_current = current_path.relative_to(root).as_posix()
    dirs[:] = sorted(d for d in dirs if not (rel_current == "." and d == ".git"))
    for name in sorted([*dirs, *files]):
        path = current_path / name
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        info = path.lstat()
        mode = info.st_mode
        if stat.S_ISREG(mode):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1048576), b""):
                    digest.update(chunk)
            kind, payload = "file", digest.hexdigest()
        elif stat.S_ISDIR(mode):
            kind, payload = "directory", ""
        elif stat.S_ISLNK(mode):
            kind, payload = "symlink", os.readlink(path)
        elif stat.S_ISFIFO(mode):
            kind, payload = "fifo", ""
        elif stat.S_ISSOCK(mode):
            kind, payload = "socket", ""
        elif stat.S_ISCHR(mode):
            kind, payload = "character", ""
        elif stat.S_ISBLK(mode):
            kind, payload = "block", ""
        else:
            kind, payload = "other", ""
        rows.append({"path": rel, "type": kind, "payload": payload})
rows.sort(key=lambda row: row["path"])
output.write_bytes(json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
' "$1" "${TASK1_ALLOWED_PATHS[@]}"
}

workspace_manifest "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.json"

cache_fingerprint() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c '
import hashlib, json, os, pathlib, stat
root = pathlib.Path("scripts")
rows = []
for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
    dirs.sort()
    for name in sorted([*dirs, *files]):
        path = pathlib.Path(current) / name
        rel = path.as_posix()
        if "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            continue
        info = path.lstat()
        if stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append((rel, "file", digest))
        elif stat.S_ISLNK(info.st_mode):
            rows.append((rel, "symlink", os.readlink(path)))
        elif stat.S_ISDIR(info.st_mode):
            rows.append((rel, "directory", ""))
        else:
            rows.append((rel, "other", ""))
print(hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest())
'
}

assert_workspace_unchanged() {
  workspace_manifest "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.current.json"
  cmp -s "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.json" "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.current.json"
}

assert_no_index_whitespace_clean() {
  set +e
  no_index_diagnostic=$(git diff --no-index --check "$1" "$2" 2>&1)
  no_index_rc=$?
  set -e
  test "$no_index_rc" = 0 || test "$no_index_rc" = 1
  test -z "$no_index_diagnostic"
}

show_no_index_diff() {
  set +e
  git diff --no-index -- "$1" "$2"
  no_index_rc=$?
  set -e
  test "$no_index_rc" = 0 || test "$no_index_rc" = 1
}

assert_append_only() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'import pathlib, sys; before = pathlib.Path(sys.argv[1]).read_bytes(); after = pathlib.Path(sys.argv[2]).read_bytes(); assert after.startswith(before)' "$1" "$2"
}

TASK1_CACHE_BEFORE=$(cache_fingerprint)
test -n "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
export TASK1_GUARDS_READY=1
trap - EXIT
test "$TASK1_GUARDS_READY" = 1
```

The empty cache set has a valid deterministic hash. A mismatch at any later
checkpoint blocks the task; do not remove or rewrite a pre-existing ignored
cache or any unrelated workspace path to make a comparison pass. Retain the
successful private directory through final changed-code review and rollback
eligibility checks.

After each Task 1-7 implementation stage and after each verification group,
run both exact guards before continuing:

```sh
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

The regression loops below run `assert_workspace_unchanged` after every
individual script so a persistent side effect is attributed to its producer.

### Task 1 — Lock the declaration and fail-first scope

**Files:** both scripts.

1. Add a test-only AST/signature gate describing the exact production
   declaration surface above.
2. Add the Protocol/TypedDict/type-alias declarations and controlled-missing
   seams to production.
3. Assert importing the production module and calling each seam performs no
   external I/O before raising.
4. Assert the fixed bootstrap, public/private command sets, parser/help, and
   `VERSION` remain unchanged.
5. Run compile, Python-3.10 AST, and the declaration helper.

**Focused gate:**

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_declarations()"
```

Expected: exit `0`.

### Task 2 — Install the exhaustive matrix and independent oracles

**File:** test script only.

1. Add the three exact 44-entry maps and mechanically regenerate the 194 rows.
2. Add the 44 Q rows and 15 M rows exactly as accepted; assert IDs, order,
   uniqueness, invoking helper, and kill oracle.
3. Add closed case IDs for every in-process, child, browser, and observer fault
   row.
4. Prove the expected-trace builders are not reachable from reference
   dispatchers or the future production driver.
5. Add a source check that private helper names are absent from `TESTS`.

Expected: the matrix/oracle helper passes while the full suite remains 29
controlled red.

### Task 3 — Implement START, TOKEN, and INPROC fitness

**File:** test script only.

1. Add low-level call-recording `InProcessPrimitives` and `ProbeSocket` fakes
   with strict expected call order and no result-returning methods.
2. Implement the test-owned unmutated START/TOKEN/INPROC reference twin from
   the accepted recipes.
3. Exercise P01-P06, P08-P16, and N04-N23 through direct recorders.
4. Require exact payload, timeout, flags/modes, denial exception, identity,
   cleanup, fsync, and absence semantics.
5. Run all applicable Q cases, M01-M06/M08/M09/M15, and the closed
   in-process fault table.

A constant row, attempt-only result, wrong context, wrong primitive, or
admitted-negative cleanup error must fail at its named oracle.

### Task 4 — Implement bounded CHILD fitness

**Files:** test script; production remains declarations only.

1. Add a test-owned reference concrete executor that consumes the exact
   `ProbeChildPlan` and uses injectable low-level Popen/selector/clock/waitpid/
   killpg recorders.
2. Require timeout `10`, stream limits `65536/65536`, stdin devnull, empty
   pass-FDs, `start_new_session=True`, unchanged token environment, and a fresh
   child PGID disjoint from the enclosing probe.
3. Require exact spawn-denied/completed/timeout-overflow/spawn-failed arms,
   nonblocking bounded drains, EOF, return/signal projection, TERM/KILL target,
   wait/reap parity, and empty post-reap child-PGID/token union.
4. Exercise all eight exact child argvs, their Q cases, M07/M08/M11, and the
   complete child fault table.
5. Verify a fake raw arm without a concrete low-level trace and an unbounded
   `communicate()` mutant fail.

Short-lived P07/P17 children do not require a racy outer `ps` row. Their actual
Popen/wait receipts prove the child; the outer observer proves enclosing-family
closure.

### Task 5 — Implement browser fitness without descendant enumeration

**File:** test script only.

1. Add a recording Playwright object graph and unmutated browser reference
   function.
2. Require the exact API-path read, `chromium.launch(headless=True)` with no
   executable path, one blank page, exact version, and reverse-order
   page/context/browser/owner closure.
3. Build P18/`BrowserProbe` from browser API evidence, P17 execution, and
   authenticated runtime only.
4. Validate the already serialized bytes after probe exit using the exact
   browser capability/profile's sole Node/headless exec leaves, successful P17,
   a valid family receipt, and empty final union.
5. Do not create or require a renderer/headless PID witness.
6. Run Q-P18, M10/M11, and every browser fault-table case.

The outer validator returns no outcome/browser and cannot rewrite stdout.

### Task 6 — Replace the weak test observer with the parent-exact bounded observer

**File:** test script only.

1. Replace `_sample_outer_process_table()` and its `subprocess.run` projection
   with an actual bounded `Popen` observer using exactly
   `["/bin/ps","eww","-axo",
   "pid=,uid=,pgid=,stat=,xstat=,command="]`.
2. Enforce `4194304/65536` stream limits, `2`-second execution, `0.5`-second
   direct wait, fresh observer PGID, stdin devnull, empty pass-FDs, exact
   environment, nonblocking drain, return `0`, null signal, empty stderr, and
   complete EOF.
3. Parse raw rows into the exact parent public projection:
   `{pid,uid,processGroupId,state,waitStatus,markerMatch}`. Enforce positive
   PID/PGID, unique PID order, exact state grammar, lowercase-hex xstat/base-16
   waitStatus, own observer row, and no second observer-PGID row.
4. Filter the current-UID original-PGID/exact-marker union, retain raw command
   only in test-private memory, and prove it never enters a report.
5. Enforce NOTE_EXIT/ESRCH, immediate/50-ms cadence, zombie-only pre-reap,
   stdout/stderr EOF, xstat/wait equality, one waitpid, and empty post-reap.
6. Add exact observer cleanup and detached-token `setsid()` fixtures.
7. Run Q-P08, M12-M14, and every observer fault row.

An invalid observer emits no sample and cannot satisfy browser or family
evidence.

### Task 7 — Integrate the harness into existing TEST-021

**File:** test script only.

1. Call declaration, matrix, reference fitness, Q/M, and fault-table helpers
   exactly once from `test_021_capabilities_process_families_streams_and_orphan_gate`.
2. Preserve all existing profile, sandbox, entrypoint, process-family, stream,
   negative-write, snapshot-subset, schema, and real echo-only mutant checks.
3. Update test-private observation fields to the exact bounded observer
   projection without changing any public receipt schema.
4. Preserve the current conditional production report branch. Current Task 1
   collects the named missing seams and ends with one TEST-021 controlled
   missing exception; Task 2 must pass the full production arm.
5. Assert 194 rows, 63/131 counts, no skip, six capabilities, and 29 TESTS.

**Focused fitness gate:**

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_harness_fitness()"
```

Expected: exit `0` and every unmutated twin/mutant count exact.

### Task 8 — Scope, regression, and completion review

1. Produce both private-preimage-to-target unified diffs with
   `git diff --no-index --` and compare every hunk to the allowlist above.
2. Require the plan to equal its private preimage. Require each pre-existing
   journal to retain its exact preimage as a byte prefix, review its no-index
   diff, and require any newly created `.agents/radar.md` to be a regular,
   non-symlink task journal containing no unrelated entry.
3. Reject any production AST node that is behavior rather than declarations or
   an immediate `_missing` seam.
4. Run all focused, compatibility, recovery, dependency, and diff gates below.
5. Independently review changed code for correctness, leaks, process/file
   cleanup, false-green mutants, and maintainability.
6. Fix blocker/high/medium findings and rerun all affected gates.
7. Recompute both final script SHA-256 values and sizes as the Task 1
   postimages. Record those four values, but not the private directory path, in
   the implementation row of `.agents/PROJECT.md`.
8. Recheck `TASK1_CACHE_BEFORE` and the whole-workspace manifest after the last
   review command and require exact matches.
9. Do not begin parent Task 2 until Task 1 review is PASS and the exact
   controlled-red state is restored.

**Allowed-file scope commands:**

```sh
cmp -s docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md" .agents/scribe.md
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md" .agents/builder.md
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md" .agents/PROJECT.md
test ! -L .agents/radar.md
if test -e .agents/radar.md; then test -f .agents/radar.md; fi
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md" .agents/scribe.md
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md" .agents/builder.md
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md" .agents/PROJECT.md
if test -e .agents/radar.md; then show_no_index_diff /dev/null .agents/radar.md; fi
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

Every displayed hunk is manually classified against the allowed-change table;
an append-only prefix alone is not sufficient if the appended journal content
belongs to another task.

## Acceptance criteria

### AC-T1-001 — Frozen matrix implemented exactly

The source constants regenerate 194 ordered composites, 63 positive and 131
negative, resolving to 44 unique recipes/owners and 44 one-to-one Q cases.
Every accepted matrix Q/M/fault case is present and invoked.

### AC-T1-002 — Test fitness is executable in Task 1

The unmutated reference twin passes every direct oracle. Every Q/M/fault mutant
fails only at its named semantic oracle. The focused fitness helper exits 0
even though production remains intentionally missing.

### AC-T1-003 — Production remains import-safe fail-first

Production changes contain only typing declarations and the exact immediate
TEST-021 missing seams. Import/call produces no I/O, process, environment,
browser, filesystem, socket, publication, or lifecycle side effect.

### AC-T1-004 — Child/browser/observer contracts are exact

All eight child plans are bounded and cleanup-safe; socketpair is zero-arg;
browser ownership is causal and has no renderer race; observer result/parser/
lifecycle equals the parent and cannot emit evidence on failure.

### AC-T1-005 — Aggregate remains exact

`scripts/test_ui_ux_theme_handoff.py` exits `1` only because all 29 entries
raise controlled matching missing behavior and prints exactly:

```text
0/29 passed; 29 controlled missing-behavior failures; 0 unexpected failures
```

No helper becomes a 30th test.

### AC-T1-006 — No scope drift or frozen-authority mutation

Parent, ledger, and matrix hashes/sizes remain exact. No out-of-scope file is
changed by this implementation, no unrelated dirty byte is reverted, and the
whole-workspace path/type/byte manifest matches at every required checkpoint.

## Verification commands and expected results

### Frozen inputs

```text
shasum -a 256   docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md   docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.traceability.yaml   docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-matrix-replacement.md
assert_workspace_unchanged
```

Expected: the three hashes in Document control/Scope.

### Focused semantic gates

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_declarations()"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_harness_fitness()"
set +e
TASK1_FULL_OUTPUT=$(PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_ui_ux_theme_handoff.py 2>&1)
TASK1_FULL_RC=$?
set -e
test "$TASK1_FULL_RC" = 1
test "${TASK1_FULL_OUTPUT##*$'\n'}" = '0/29 passed; 29 controlled missing-behavior failures; 0 unexpected failures'
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

Expected: first two exit 0. The full file exits 1 with exact controlled-red
summary and no unexpected failure.

### Static and compatibility gates

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'import os, py_compile; root = os.environ["TASK1_PRIVATE_PREIMAGE_DIR"]; [py_compile.compile(path, cfile=os.path.join(root, path.rsplit("/", 1)[-1] + ".pyc"), doraise=True) for path in ("scripts/ui_ux_theme_handoff.py", "scripts/test_ui_ux_theme_handoff.py")]'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), feature_version=(3,10)) for p in ('scripts/ui_ux_theme_handoff.py','scripts/test_ui_ux_theme_handoff.py')]"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pip check
assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
! rg -n '[[:blank:]]+$' scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

Expected: compile/tabnanny/AST/pip/rg/cache gates exit 0 and rg prints no lines.
The no-index helper accepts exit 1 with no diagnostic when its target changed
cleanly, or exit 0 only when the corresponding authorized file needed no
change. Any whitespace diagnostic or exit greater than 1 blocks. Ordinary Git
diff is not used as target coverage because both scripts are untracked.

### Repository regression gates

The Makefile is dirty and is not an implementation input. Run the current
recipe bodies directly from these frozen closed lists instead of invoking
`make`.

```sh
for script in scripts/test_ui_ux_isolation.py scripts/test_ui_ux_evidence.py scripts/test_ui_ux_selection_fixture.py scripts/test_ui_accessible_selection_controls.py scripts/test_ui_ux_fixtures.py scripts/test_ui_ux_snapshot_matrix.py scripts/test_ui_ux_theme.py scripts/test_ui_ux_theme_matrix.py scripts/test_ui_ux_contract.py scripts/test_dashboard_navigation.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$script" || exit $?
  assert_workspace_unchanged || exit $?
done

for script in scripts/test_artifact_loader.py scripts/test_api.py scripts/test_momentum_options.py scripts/test_risk_guard_technical.py scripts/test_industry_roles.py scripts/test_influencer_roster.py scripts/test_trade_state.py scripts/test_options_cockpit_display.py scripts/test_ui_read_api.py scripts/test_ui_ai_updates_api.py scripts/test_ui_fund_catalog_api.py scripts/test_ui_iv_history_api.py scripts/test_ui_options_flow_api.py scripts/test_ui_ux_components.py scripts/test_ui_ux1a_safety.py scripts/test_ui_ux_contract.py scripts/test_ui_ux_fixtures.py scripts/test_ui_ux_snapshot_matrix.py scripts/test_ui_ux_theme.py scripts/test_ui_ux_theme_matrix.py scripts/test_ai_chat_store.py scripts/test_candidate_controls_view.py scripts/test_sys_schedules_reflection.py scripts/test_dashboard_navigation.py scripts/test_hard_filter_yfinance.py scripts/test_candidate_pipeline_controls.py scripts/test_candidate_outcomes.py scripts/test_rank_candidates.py scripts/test_agent_reach_auth.py scripts/test_agent_reach_social_bridge.py scripts/test_social_intelligence.py scripts/test_social_intelligence_outcomes.py scripts/test_llm_score_progress.py scripts/test_run_status.py scripts/test_docker_runtime_contract.py scripts/test_claude_auth_flow.py; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$script" || exit $?
  assert_workspace_unchanged || exit $?
done

test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
```

Expected: all existing non-Task-1 suites pass. The intentional standalone
Task-1 controlled-red command is not reclassified as a repository failure.
The artifact-producing `make ui-ux1b-legacy` capture is deferred: Task 1 does
not change UI/capture behavior, and creating new workspace evidence would
violate this plan's no-evidence-artifact scope.

If a command is unavailable or fails for an unrelated pre-existing reason,
record exact output and attribution; a failure introduced by this change is
blocking.

## Diff and review gate

Before completion, review the actual diff against this plan:

- both no-index diffs start from the frozen private preimages, and every hunk
  is attributable to an allowed Task 1 change;
- production import and declaration/member/signature set exact;
- every new production function is immediate controlled missing and no I/O;
- test helpers are private and TESTS remains 29;
- matrix/Q/M/fault counts exact;
- no same-process audit stream is described or used as sole semantic proof;
- no racy descendant witness was reintroduced;
- all process/file descriptors, scratch paths, process groups, and audit pipes
  close on success and every fault;
- raw token, audit challenge, raw command, exceptions, and test-only FDs are
  absent from public report bytes;
- no public schema/argv/environment/pass-FD/CLI change;
- no unexplained scope drift.

Completion requires an independent changed-code review with zero
blocker/high/medium findings and rerun verification after every fix.

## Risk and rollback

| Risk | Blocking signal | Mitigation |
| --- | --- | --- |
| False-green reference twin | mutant passes or reference calls expected-data builder | independent trace tables, code-name reachability checks, exact kill oracle |
| Unbounded/leaked process | deadline exceeded, surviving PID/PGID/token row, open pipe | fresh disjoint groups, bounded selector, TERM/KILL/wait/post-reap assertions |
| Observer manufactures evidence | invalid ps result emits a sample | closed result/parser/lifecycle fault matrix |
| Browser race/overclaim | acceptance depends on catching renderer PID | sole-exec-leaf/API/P17/final-quiescence contract only |
| Production scope drift | any behavior/I/O beyond immediate missing seam | AST/diff allowlist and preimage comparison |
| Dirty-worktree loss | unrelated file changes or revert | patch only two scoped scripts; never reset/checkout unrelated files |
| Ignored cache drift | cache fingerprint differs after any Python gate | disable bytecode writes, redirect compile output to private directory, compare exact before/after fingerprint |
| Regression side effect | whole-workspace manifest differs after a stage or script | stop at the first producer; preserve evidence; do not erase or normalize unrelated bytes |

Rollback is allowed only while both target files still match the recorded Task
1 postimage hashes and sizes. First generate reverse no-index diffs from each
current target to its private preimage and inspect that they touch only the two
target paths. Convert those exact reverse hunks to `apply_patch` updates; do
not copy-overwrite the targets. Recompute both restored hashes/sizes and
require the frozen preimage values before declaring rollback complete. If
either current target differs from its recorded postimage, stop: later/user
work may exist and automatic rollback is forbidden.

Planning artifacts, parent/ledger/matrix, ignored caches, and unrelated dirty
worktree content are never rollback targets. No `git reset`, `git checkout`,
file deletion, or other destructive Git command is authorized.

## Traceability

| Requirement | Acceptance | Implementation tasks | Test owner |
| --- | --- | --- | --- |
| Accepted matrix exhaustive mapping | AC-T1-001 | Tasks 2, 7 | TEST-021 |
| Result-bearing primitive evidence | AC-T1-002, AC-T1-004 | Tasks 3-6 | TEST-021 |
| Fail-first production isolation | AC-T1-003, AC-T1-005 | Tasks 1, 7 | TEST-021 |
| Mutation resistance | AC-T1-002 | Tasks 2-6 | TEST-021 |
| Exact process-family union | AC-T1-004 | Tasks 4, 6 | TEST-021 |
| Frozen authority/scope | AC-T1-006 | Tasks 1, 8 | TEST-021 plus local gates |

All links remain within parent TEST-021; the immutable parent ledger is not
edited.

## Plan review gate

Implementation may begin only after an independent reviewer confirms:

- this plan implements the accepted matrix SHA without semantic drift;
- the production declaration allowlist is sufficient and no Task 2 behavior is
  required;
- reference fitness is executable while the aggregate stays controlled red;
- child/browser/observer inputs and ownership are complete and causal;
- every affected file, verification command, risk, and rollback boundary is
  explicit;
- zero blocker/high/medium finding remains.

After PASS, execute Tasks 0-8 in order. If implementation discovers a concrete
contradiction with the accepted matrix, stop and write a fresh reviewed
replacement; do not improvise around it.

## Review history

- v0.1: FAIL with one high and one medium finding. The plan did not preserve
  byte-exact preimages for the two untracked targets, had no postimage-guarded
  inverse rollback, could create ignored bytecode under `scripts/`, and relied
  on a dirty Makefile for regression commands.
- v0.2: adds verified private preimages, no-index diff/whitespace review,
  postimage-guarded inverse-patch rollback, exact ignored-cache fingerprinting,
  `PYTHONDONTWRITEBYTECODE=1`, private compile outputs, and frozen direct
  regression command lists. Iteration 2 FAIL: two high and one medium finding
  remained—the initializer was not fail-closed, unrelated dirty workspace
  bytes lacked a pre/post guard, and the private-directory variable was not
  exported for the compile child.
- v0.3: runs initialization under fail-closed `set -eu` with guarded partial-
  state cleanup and an explicit readiness marker; exports the private path;
  adds a whole-workspace path/type/byte manifest excluding only exact allowed
  files, checkpoint comparison after every stage/script, and separate allowed-
  file preimage/diff review. Independent iteration 3 review pending.
