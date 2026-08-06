# UX-1B TEST-021 Task 1 Fail-Closed Implementation Replacement

## Document information

| Field | Value |
| --- | --- |
| Type | Implementation checklist |
| Version | v0.2 |
| Status | Review candidate; implementation blocked until PASS |
| Date | 2026-07-21 |
| Author | Codex / Scribe |
| Audience | Maintainer, Builder, Radar, independent reviewer |
| Reviewer / approver | Independent Task 1 scope reviewer |
| Supersedes | `2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-implementation-replacement.md` v0.3; rejected and immutable |

## Authority and dependencies

| Artifact | SHA-256 | Size |
| --- | --- | ---: |
| Parent plan | `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581` | 243794 |
| Parent ledger | `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8` | 17155 |
| Accepted semantic matrix | `f0bd99afeec74e8f11cd2fd49794fd244a8ac6a9c93ad60e74bbe8057fe7db5b` | 58086 |
| Production preimage | `a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6` | 23930 |
| Test preimage | `e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee` | 675940 |
| Rejected predecessor | `f5babfbec00ff33137b9cd202c6f317f7c11f0caf0e37252178cb61596353c3e` | 43503 |

The parent and accepted matrix are normative. The rejected predecessor is
historical review evidence only. It grants no implementation authority.

## Goal and success metrics

Implement parent Task 1 as import-safe production declarations plus a
mutation-resistant TEST-021 fail-first harness. Task 2 behavior remains absent.

Success is binary:

- all 194 matrix rows exist in source order: 63 positive and 131 negative;
- all 44 recipes have one owner and one applicable Q kill;
- all 15 M mutants and every closed fault row fail at their named oracle;
- the test-owned unmutated reference twin passes;
- production adds only closed typing declarations and immediate TEST-021
  `_missing` seams with no I/O;
- the aggregate remains exactly 29 controlled missing failures and zero
  unexpected failures;
- every guard, focused, static, regression, scope, and independent review gate
  passes without changing an out-of-scope workspace byte.

## Scope

### Allowed implementation files

| Path | Allowed change |
| --- | --- |
| `scripts/ui_ux_theme_handoff.py` | Typing imports, accepted closed declarations, eight exact immediate-missing seams |
| `scripts/test_ui_ux_theme_handoff.py` | TEST-021 matrix/oracles/reference twin/mutants/faults and bounded test helpers |
| This plan | Planning artifact; immutable after review PASS |
| `.agents/scribe.md` | Append-only planning insight |
| `.agents/builder.md` | Append-only implementation insight |
| `.agents/radar.md` | Append-only test insight; may be newly created |
| `.agents/PROJECT.md` | Append-only activity rows |

### Non-goals

- no Task 2 capability implementation;
- no public CLI, argv, environment, pass-FD, stdout, schema, API, UI, runtime,
  dependency, Makefile, capture, publication, recovery, or deployment change;
- no new test outside existing TEST-021 and no 30th `TESTS` entry;
- no mutation, cleanup, normalization, or rollback of unrelated dirty files;
- no renderer/headless descendant enumeration witness;
- no same-interpreter HMAC/audit value as sole result authority.

## Glossary

| Term | Meaning |
| --- | --- |
| Preimage | Exact target bytes before Task 1 edits |
| Postimage | Exact target bytes after accepted Task 1 edits |
| Workspace baseline | Canonical path/type/content snapshot excluding only allowed files |
| Fail-closed | Any command, traversal, parse, or comparison error produces failure |
| Controlled red | `ThemeHandoffNotImplemented` with the matching TEST ID |
| Q mutant | One recipe-qualified semantic mutation |
| M mutant | Cross-cutting semantic mutation from the accepted matrix |

## Requirements

### REQ-T1-001 — Semantic matrix fidelity

The implementation MUST reproduce the accepted matrix SHA exactly by meaning:
194 ordered composites, 44 recipes/owners/Q kills, 15 M mutants, and all closed
fault tables. Matrix content is not regenerated from production output.

### REQ-T1-002 — Fail-first production surface

Production MUST add only these accepted declarations:

- `ProbeSocket`, `InProcessPrimitives` with zero-argument `socketpair()`;
- `ProbeChildPlan` and the four raw child arms;
- `ProbeChildExecution` closed union and raw-only `ProbeChildExecutor`;
- `BrowserApiEvidence`, `ChildProbeAssertionResult`, `BrowserBuildResult`;
- `_evaluate_start_probe_assertion`;
- `_evaluate_token_probe_assertion`;
- `_evaluate_inprocess_probe_assertion`;
- `_execute_probe_child`;
- `_evaluate_child_probe_assertion`;
- `_exercise_browser_api`;
- `_build_browser_probe`;
- `_validate_serialized_browser_probe`.

Every new production seam immediately calls `_missing("TEST-021", ...)`. It
MUST NOT read state, catch the missing exception, call another seam, or perform
process, socket, file, browser, environment, network, or publication I/O.

### CFR-T1-001 — Workspace integrity

Before implementation, a stable canonical baseline MUST cover every workspace
path except `.git/**` and the seven exact allowed paths. Every included regular
file is represented by path, lstat type, and SHA-256 bytes. Every symlink uses
its uninterpreted target and is never followed. Every directory and special
file records path and lstat type.

The baseline MUST be recomputed twice before edits and both copies MUST match.
Every later comparison computes the current manifest in memory. It MUST NOT
read a reusable current-manifest file.

### CFR-T1-002 — Command failures remain failures

Every shell guard MUST explicitly propagate child failure with `|| return $?`
or a checked status branch. It MUST remain fail-closed even when a caller puts
the function in an `if`, `!`, `&&`, or `||` context that suppresses zsh
`ERR_EXIT`.

`os.walk` MUST use an `onerror` callback that raises. Missing roots, read
errors, hash races, malformed baselines, unexpected path types, and comparison
differences MUST fail.

### CFR-T1-003 — Verification isolation

Every Python invocation uses `PYTHONDONTWRITEBYTECODE=1`. Explicit compile
outputs go only to the private directory. The ignored Python-cache fingerprint
and whole-workspace baseline MUST match after every task, verification group,
and individual regression script.

The dirty Makefile is not a runtime input. Regression scripts run from the
closed lists in this plan.

## Fail-closed guard design

Run guard initialization in one dedicated zsh session. Do not edit until
`TASK1_GUARDS_READY` equals `1`.

```zsh
set -eu
export TASK1_GUARDS_READY=0
export TASK1_PRIVATE_PREIMAGE_DIR=""
trap 'rc=$?; if (( rc != 0 )) && [[ -n ${TASK1_PRIVATE_PREIMAGE_DIR:-} ]]; then case "$TASK1_PRIVATE_PREIMAGE_DIR" in /private/tmp/quant-radar-test021-v2.*) command rm -rf -- "$TASK1_PRIVATE_PREIMAGE_DIR" ;; esac; fi' EXIT

TASK1_PRIVATE_PREIMAGE_DIR=$(mktemp -d /private/tmp/quant-radar-test021-v2.XXXXXX)
export TASK1_PRIVATE_PREIMAGE_DIR
chmod 0700 "$TASK1_PRIVATE_PREIMAGE_DIR"

typeset -a TASK1_ALLOWED_PATHS
TASK1_ALLOWED_PATHS=(
  scripts/ui_ux_theme_handoff.py
  scripts/test_ui_ux_theme_handoff.py
  docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md
  .agents/scribe.md
  .agents/builder.md
  .agents/radar.md
  .agents/PROJECT.md
)

workspace_guard() {
  local mode="$1"
  local baseline="$2"
  local root="${3:-$PWD}"
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c '
import hashlib, json, os, pathlib, stat, sys

mode, baseline_arg, root_arg, *excluded_args = sys.argv[1:]
baseline = pathlib.Path(baseline_arg)
root = pathlib.Path(root_arg).resolve(strict=True)
if not root.is_dir():
    raise NotADirectoryError(root)
excluded = frozenset(excluded_args)

def raise_walk(error):
    raise error

def collect():
    rows = []
    for current, dirs, files in os.walk(
        root, topdown=True, onerror=raise_walk, followlinks=False
    ):
        current_path = pathlib.Path(current)
        rel_current = current_path.relative_to(root).as_posix()
        dirs[:] = sorted(
            name
            for name in dirs
            if not (rel_current == "." and name == ".git")
        )
        for name in sorted([*dirs, *files]):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if rel in excluded:
                continue
            before = path.lstat()
            file_type = stat.S_IFMT(before.st_mode)
            if stat.S_ISREG(before.st_mode):
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1048576), b""):
                        digest.update(chunk)
                payload = digest.hexdigest()
                kind = "file"
            elif stat.S_ISDIR(before.st_mode):
                kind, payload = "directory", ""
            elif stat.S_ISLNK(before.st_mode):
                kind, payload = "symlink", os.readlink(path)
            elif stat.S_ISFIFO(before.st_mode):
                kind, payload = "fifo", ""
            elif stat.S_ISSOCK(before.st_mode):
                kind, payload = "socket", ""
            elif stat.S_ISCHR(before.st_mode):
                kind, payload = "character", ""
            elif stat.S_ISBLK(before.st_mode):
                kind, payload = "block", ""
            else:
                raise RuntimeError(f"unsupported workspace path type: {rel}")
            after = path.lstat()
            stable = (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_size,
                before.st_mtime_ns,
            ) == (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_size,
                after.st_mtime_ns,
            )
            if not stable or stat.S_IFMT(after.st_mode) != file_type:
                raise RuntimeError(f"workspace path changed while hashing: {rel}")
            rows.append({"path": rel, "type": kind, "payload": payload})
    rows.sort(key=lambda row: row["path"])
    return rows

rows = collect()
encoded = json.dumps(
    rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True
).encode("utf-8") + b"\n"

if mode == "write":
    descriptor = os.open(
        baseline, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
elif mode == "compare":
    expected = baseline.read_bytes()
    if encoded != expected:
        raise AssertionError("workspace path/type/byte manifest changed")
else:
    raise ValueError(f"unknown workspace guard mode: {mode}")
' "$mode" "$baseline" "$root" "${TASK1_ALLOWED_PATHS[@]}" || return $?
}

assert_workspace_unchanged() {
  workspace_guard compare "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.json" || return $?
}

assert_no_trailing_whitespace() {
  local output
  local status
  if output=$(rg -n '[[:blank:]]+$' "$@" 2>&1); then
    status=0
  else
    status=$?
  fi
  if (( status == 1 )) && [[ -z "$output" ]]; then
    return 0
  fi
  [[ -z "$output" ]] || print -r -- "$output" >&2
  return 1
}

assert_no_index_whitespace_clean() {
  local output
  local status
  if output=$(git diff --no-index --check "$1" "$2" 2>&1); then
    status=0
  else
    status=$?
  fi
  if (( status == 0 || status == 1 )) && [[ -z "$output" ]]; then
    return 0
  fi
  [[ -z "$output" ]] || print -r -- "$output" >&2
  return 1
}

show_no_index_diff() {
  local status
  if git diff --no-index -- "$1" "$2"; then
    status=0
  else
    status=$?
  fi
  if (( status == 0 || status == 1 )); then
    return 0
  fi
  return "$status"
}

assert_append_only() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c '
import pathlib, sys
before = pathlib.Path(sys.argv[1]).read_bytes()
after = pathlib.Path(sys.argv[2]).read_bytes()
if not after.startswith(before):
    raise AssertionError("allowed journal is not append-only")
' "$1" "$2" || return $?
}

cache_fingerprint() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c '
import hashlib, json, os, pathlib, stat

root = pathlib.Path("scripts").resolve(strict=True)

def raise_walk(error):
    raise error

rows = []
for current, dirs, files in os.walk(
    root, topdown=True, onerror=raise_walk, followlinks=False
):
    dirs.sort()
    for name in sorted([*dirs, *files]):
        path = pathlib.Path(current) / name
        rel = path.relative_to(root).as_posix()
        if "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            continue
        info = path.lstat()
        if stat.S_ISREG(info.st_mode):
            payload = hashlib.sha256(path.read_bytes()).hexdigest()
            kind = "file"
        elif stat.S_ISDIR(info.st_mode):
            kind, payload = "directory", ""
        elif stat.S_ISLNK(info.st_mode):
            kind, payload = "symlink", os.readlink(path)
        else:
            raise RuntimeError(f"unsupported cache path type: {rel}")
        rows.append({"path": rel, "type": kind, "payload": payload})
encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
print(hashlib.sha256(encoded).hexdigest())
' || return $?
}
```

Every function has an explicit failure return. `assert_workspace_unchanged`
does not consume a `workspace.current.json`, so a traversal failure cannot fall
through to a stale comparison.

## Pre-implementation checklist

- [ ] `IMPL-T1-000`: Recheck all five authority/preimage hashes and sizes.
- [ ] `IMPL-T1-001`: Copy both target preimages, this accepted plan, and each
  existing allowed journal into the mode-0700 private directory using mode
  0600; record `.agents/radar.md` absence if still absent.
- [ ] `IMPL-T1-002`: Run `workspace_guard write` twice to two fresh files,
  require byte equality, rename the first to `workspace.before.json`, and
  retain the second as independent baseline evidence.
- [ ] `IMPL-T1-003`: Compute a deterministic path/type/byte fingerprint for
  `scripts/**/__pycache__/**`, `*.pyc`, and `*.pyo` as
  `TASK1_CACHE_BEFORE`.
- [ ] `IMPL-T1-004`: Prove `assert_workspace_unchanged` returns the injected
  nonzero status when a subshell override of `workspace_guard` returns `73`.
- [ ] `IMPL-T1-005`: Prove `workspace_guard write` rejects a nonexistent root
  and creates no baseline.
- [ ] `IMPL-T1-006`: Prove `assert_no_trailing_whitespace` passes clean input,
  rejects trailing whitespace, and rejects `rg` status 2 from a missing path.
- [ ] `IMPL-T1-007`: Set `TASK1_GUARDS_READY=1`, remove the initialization
  EXIT trap, and require the marker before the first edit.

Any failed item blocks implementation. Partial private initialization is
cleaned only by the prefix-guarded EXIT trap. Successful private evidence is
retained through review and rollback eligibility checks.

Use these exact initialization checks after defining the guard functions:

```zsh
parent_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md)
test "${parent_hash%% *}" = 3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581
test "$(stat -f %z docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md)" = 243794
ledger_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.traceability.yaml)
test "${ledger_hash%% *}" = 47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8
test "$(stat -f %z docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.traceability.yaml)" = 17155
matrix_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-matrix-replacement.md)
test "${matrix_hash%% *}" = f0bd99afeec74e8f11cd2fd49794fd244a8ac6a9c93ad60e74bbe8057fe7db5b
test "$(stat -f %z docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-matrix-replacement.md)" = 58086

production_hash=$(shasum -a 256 scripts/ui_ux_theme_handoff.py)
test "${production_hash%% *}" = a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6
test "$(stat -f %z scripts/ui_ux_theme_handoff.py)" = 23930
test_hash=$(shasum -a 256 scripts/test_ui_ux_theme_handoff.py)
test "${test_hash%% *}" = e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee
test "$(stat -f %z scripts/test_ui_ux_theme_handoff.py)" = 675940

test -n "${TASK1_ACCEPTED_PLAN_SHA:-}"
accepted_plan_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md)
test "${accepted_plan_hash%% *}" = "$TASK1_ACCEPTED_PLAN_SHA"

mkdir -m 0700 "$TASK1_PRIVATE_PREIMAGE_DIR/allowed"
install -m 0600 scripts/ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py"
install -m 0600 scripts/test_ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py"
install -m 0600 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
install -m 0600 .agents/scribe.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md"
install -m 0600 .agents/builder.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md"
install -m 0600 .agents/PROJECT.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md"
test ! -e .agents/radar.md
test ! -L .agents/radar.md
cmp -s scripts/ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py"
cmp -s scripts/test_ui_ux_theme_handoff.py "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py"
cmp -s docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
cmp -s .agents/scribe.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md"
cmp -s .agents/builder.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md"
cmp -s .agents/PROJECT.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md"

workspace_guard write "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.a.json"
workspace_guard write "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.b.json"
cmp -s "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.a.json" "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.b.json"
mv "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.a.json" "$TASK1_PRIVATE_PREIMAGE_DIR/workspace.before.json"

TASK1_CACHE_BEFORE=$(cache_fingerprint)
test -n "$TASK1_CACHE_BEFORE"

(
  workspace_guard() { return 73; }
  if assert_workspace_unchanged; then
    injected_status=0
  else
    injected_status=$?
  fi
  test "$injected_status" = 73
)

if workspace_guard write "$TASK1_PRIVATE_PREIMAGE_DIR/should-not-exist.json" "$TASK1_PRIVATE_PREIMAGE_DIR/no-such-root"; then
  missing_root_status=0
else
  missing_root_status=$?
fi
test "$missing_root_status" != 0
test ! -e "$TASK1_PRIVATE_PREIMAGE_DIR/should-not-exist.json"

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'import os, pathlib; root = pathlib.Path(os.environ["TASK1_PRIVATE_PREIMAGE_DIR"]); (root / "clean.txt").write_bytes(b"clean\n"); (root / "trailing.txt").write_bytes(b"bad \n")'
assert_no_trailing_whitespace "$TASK1_PRIVATE_PREIMAGE_DIR/clean.txt"
if assert_no_trailing_whitespace "$TASK1_PRIVATE_PREIMAGE_DIR/trailing.txt"; then
  trailing_status=0
else
  trailing_status=$?
fi
if assert_no_trailing_whitespace "$TASK1_PRIVATE_PREIMAGE_DIR/missing.txt"; then
  missing_search_status=0
else
  missing_search_status=$?
fi
test "$trailing_status" = 1
test "$missing_search_status" = 1

assert_workspace_unchanged
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
export TASK1_GUARDS_READY=1
trap - EXIT
test "$TASK1_GUARDS_READY" = 1
```

## Implementation checklist

### IMPL-T1-010 — Production declarations

- [ ] Add only `Literal`, `Protocol`, `TypeAlias`, and `TypedDict` typing needs.
- [ ] Add the accepted closed Protocol/TypedDict/type-alias declarations.
- [ ] Add all eight exact seams with matrix signatures and immediate `_missing`.
- [ ] Keep `_run_capability_probe()` and the 85-byte bootstrap unchanged.
- [ ] AST-check that no new seam contains behavior or I/O.
- [ ] Run cache and workspace guards.

### IMPL-T1-020 — Matrix and independent oracles

- [ ] Generate the 194 exact rows from existing capability/addition constants.
- [ ] Add exact recipe, owner, Q, M, and closed-fault tables.
- [ ] Keep expected IDs/traces independent of production and reference output.
- [ ] Prove all private helpers are absent from `TESTS`.
- [ ] Run cache and workspace guards.

### IMPL-T1-030 — START, TOKEN, and INPROC fitness

- [ ] Add recording primitives with exact call order and no outcome methods.
- [ ] Add the test-owned unmutated reference twin.
- [ ] Exercise P01-P06, P08-P16, N04-N23, applicable Q cases, required M
  mutants, and the closed in-process fault table.
- [ ] Run cache and workspace guards.

### IMPL-T1-040 — Bounded CHILD fitness

- [ ] Implement test-owned raw executor with injectable low-level recorders.
- [ ] Enforce 10 seconds, 65536-byte streams, devnull stdin, empty pass-FDs,
  `start_new_session=True`, unchanged token, disjoint fresh child PGID,
  bounded nonblocking drain, TERM/KILL/wait, and empty final union.
- [ ] Exercise all eight child argvs, Q cases, M07/M08/M11, and all child faults.
- [ ] Run cache and workspace guards.

### IMPL-T1-050 — Browser fitness

- [ ] Require Playwright default executable, `launch(headless=True)` with no
  executable path, one blank page, exact version, and reverse closure.
- [ ] Build P18/BrowserProbe only from API evidence, P17 execution, and runtime.
- [ ] Validate immutable stdout bytes after exit against the sole exec leaf,
  valid family receipt, and final quiescence without renderer enumeration.
- [ ] Exercise Q-P18, M10/M11, and every browser fault.
- [ ] Run cache and workspace guards.

### IMPL-T1-060 — Parent-exact observer fitness

- [ ] Use exact argv `/bin/ps eww -axo
  pid=,uid=,pgid=,stat=,xstat=,command=` through bounded `Popen`.
- [ ] Enforce parent stream/time/wait/group/env/EOF/result/parser grammar.
- [ ] Enforce marker plus original-PGID union and NOTE_EXIT/ESRCH lifecycle.
- [ ] Exercise Q-P08, M12-M14, and every observer fault.
- [ ] Run cache and workspace guards.

### IMPL-T1-070 — Existing TEST-021 integration

- [ ] Invoke declaration, matrix, reference, Q/M, and fault helpers once.
- [ ] Preserve every existing TEST-021 branch and conditional production arm.
- [ ] Collect named missing seams and emit one controlled TEST-021 red.
- [ ] Require 194 rows, 63/131, six capabilities, 29 `TESTS`, and zero skip.
- [ ] Run cache and workspace guards.

## Verification checklist

Every Python command below is bytecode-disabled. The intentional aggregate red
is captured in a checked `if` branch without changing caller shell options.

```zsh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_declarations()"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "from scripts import test_ui_ux_theme_handoff as t; t._assert_test021_semantic_harness_fitness()"

if TASK1_FULL_OUTPUT=$(PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_ui_ux_theme_handoff.py 2>&1); then
  TASK1_FULL_RC=0
else
  TASK1_FULL_RC=$?
fi
test "$TASK1_FULL_RC" = 1
test "${TASK1_FULL_OUTPUT##*$'\n'}" = '0/29 passed; 29 controlled missing-behavior failures; 0 unexpected failures'

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'import os, py_compile; root = os.environ["TASK1_PRIVATE_PREIMAGE_DIR"]; [py_compile.compile(path, cfile=os.path.join(root, path.rsplit("/", 1)[-1] + ".pyc"), doraise=True) for path in ("scripts/ui_ux_theme_handoff.py", "scripts/test_ui_ux_theme_handoff.py")]'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), feature_version=(3,10)) for p in ('scripts/ui_ux_theme_handoff.py','scripts/test_ui_ux_theme_handoff.py')]"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pip check

assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
assert_no_index_whitespace_clean "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
assert_no_trailing_whitespace scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

### Closed regression lists

Do not invoke the dirty Makefile. Run each script, then run
`assert_workspace_unchanged` as a simple command under `set -e`.

```zsh
typeset -a TASK1_RECOVERY_SCRIPTS
TASK1_RECOVERY_SCRIPTS=(
  scripts/test_ui_ux_isolation.py
  scripts/test_ui_ux_evidence.py
  scripts/test_ui_ux_selection_fixture.py
  scripts/test_ui_accessible_selection_controls.py
  scripts/test_ui_ux_fixtures.py
  scripts/test_ui_ux_snapshot_matrix.py
  scripts/test_ui_ux_theme.py
  scripts/test_ui_ux_theme_matrix.py
  scripts/test_ui_ux_contract.py
  scripts/test_dashboard_navigation.py
)
for script in "${TASK1_RECOVERY_SCRIPTS[@]}"; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$script" || exit $?
  assert_workspace_unchanged
done

typeset -a TASK1_REPOSITORY_SCRIPTS
TASK1_REPOSITORY_SCRIPTS=(
  scripts/test_artifact_loader.py scripts/test_api.py
  scripts/test_momentum_options.py scripts/test_risk_guard_technical.py
  scripts/test_industry_roles.py scripts/test_influencer_roster.py
  scripts/test_trade_state.py scripts/test_options_cockpit_display.py
  scripts/test_ui_read_api.py scripts/test_ui_ai_updates_api.py
  scripts/test_ui_fund_catalog_api.py scripts/test_ui_iv_history_api.py
  scripts/test_ui_options_flow_api.py scripts/test_ui_ux_components.py
  scripts/test_ui_ux1a_safety.py scripts/test_ui_ux_contract.py
  scripts/test_ui_ux_fixtures.py scripts/test_ui_ux_snapshot_matrix.py
  scripts/test_ui_ux_theme.py scripts/test_ui_ux_theme_matrix.py
  scripts/test_ai_chat_store.py scripts/test_candidate_controls_view.py
  scripts/test_sys_schedules_reflection.py scripts/test_dashboard_navigation.py
  scripts/test_hard_filter_yfinance.py scripts/test_candidate_pipeline_controls.py
  scripts/test_candidate_outcomes.py scripts/test_rank_candidates.py
  scripts/test_agent_reach_auth.py scripts/test_agent_reach_social_bridge.py
  scripts/test_social_intelligence.py scripts/test_social_intelligence_outcomes.py
  scripts/test_llm_score_progress.py scripts/test_run_status.py
  scripts/test_docker_runtime_contract.py scripts/test_claude_auth_flow.py
)
for script in "${TASK1_REPOSITORY_SCRIPTS[@]}"; do
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$script" || exit $?
  assert_workspace_unchanged
done
test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
```

## Acceptance scenarios

### AC-T1-001 — Guard failure cannot reuse stale state

Given an existing valid baseline, when manifest traversal is forced to return
status 73 before comparison, then `assert_workspace_unchanged` returns 73 and
does not perform a stale-file comparison.

### AC-T1-002 — Traversal errors block

Given a nonexistent or unreadable root, when `workspace_guard write` runs,
then it exits nonzero, creates no accepted baseline, and readiness stays 0.

### AC-T1-003 — Search errors are not clean results

Given a clean target, a trailing-whitespace target, and a missing target, when
the whitespace helper runs, then only the clean target returns success. Status
0 with matches, status 2, and nonempty diagnostics all fail.

### AC-T1-004 — Task 1 remains fail-first

Given the completed Task 1 diff, when the focused helpers and aggregate run,
then the helpers pass and the aggregate ends with exactly `0/29`, 29
controlled missing failures, and zero unexpected failures.

### AC-T1-005 — No scope drift

Given the stable pre-edit workspace baseline, when any implementation task or
regression script completes, then the in-memory current manifest equals the
baseline and all allowed-file diffs contain only reviewed Task 1 changes.

## Scope review and rollback

Run these exact final allowed-file gates. `show_no_index_diff` converts Git's
normal difference status 1 to success but preserves every operational error.

```zsh
cmp -s docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/plan.md"
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md" .agents/scribe.md
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md" .agents/builder.md
assert_append_only "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md" .agents/PROJECT.md
test ! -L .agents/radar.md
if test -e .agents/radar.md; then
  test -f .agents/radar.md
  test -s .agents/radar.md
  rg -q '^## 2026-07-21 - ' .agents/radar.md
  rg -q '^\*\*Insight:\*\* ' .agents/radar.md
  rg -q '^\*\*Apply when:\*\* ' .agents/radar.md
fi

show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/ui_ux_theme_handoff.py" scripts/ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/test_ui_ux_theme_handoff.py" scripts/test_ui_ux_theme_handoff.py
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/scribe.md" .agents/scribe.md
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/builder.md" .agents/builder.md
show_no_index_diff "$TASK1_PRIVATE_PREIMAGE_DIR/allowed/PROJECT.md" .agents/PROJECT.md
if test -e .agents/radar.md; then
  show_no_index_diff /dev/null .agents/radar.md
fi

test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE"
assert_workspace_unchanged
```

Ordinary Git does not cover the two untracked targets. Manually classify every
displayed hunk against the allowed-change table. The accepted plan must have no
diff. Existing journals may only append entries for this logical Task 1 work.
A new `radar.md` may contain only this task's valid journal entry; the format
checks alone do not replace manual classification.

After all gates, record both target postimage hashes and sizes. Rollback is
allowed only while both current targets exactly equal those postimages. Build
reverse no-index diffs with `show_no_index_diff` from current targets to private
preimages, inspect them, and apply only those exact reverse hunks with
`apply_patch`. Then require both
frozen preimage hashes/sizes. Do not copy-overwrite, delete, reset, checkout, or
touch another dirty path.

## Risk register

| Risk | Blocking signal | Control |
| --- | --- | --- |
| Stale manifest false pass | guard reads reusable current file | compare fresh in-memory bytes directly |
| Suppressed zsh ERR_EXIT | nested command fails in conditional context | explicit `|| return $?` in every guard |
| Silent traversal omission | `os.walk` read error | raising `onerror` callback |
| Search tool failure mislabeled clean | `rg` status greater than 1 | exact status-1-and-empty acceptance |
| Dirty workspace damage | path/type/byte baseline mismatch | checkpoint after every stage and script |
| False-green semantic twin | mutant passes or expected data reused | independent oracles and named kill owner |
| Process leak | live PID/PGID/token, open pipe, missed reap | accepted bounded child/observer fault matrix |
| Task 2 scope drift | production behavior or I/O appears | AST allowlist and immediate-missing rule |

## Traceability

| Requirement | Acceptance | Implementation | Test owner |
| --- | --- | --- | --- |
| REQ-T1-001 | AC-T1-004 | IMPL-T1-020..070 | TEST-021 |
| REQ-T1-002 | AC-T1-004 | IMPL-T1-010,070 | TEST-021 |
| CFR-T1-001 | AC-T1-001,002,005 | IMPL-T1-000..007 | local guard gates |
| CFR-T1-002 | AC-T1-001,002,003 | IMPL-T1-004..006 | local guard gates |
| CFR-T1-003 | AC-T1-005 | all tasks and verification | local regression gates |

## Review gate

Implementation starts only after a fresh reviewer checks the exact plan bytes
and reports zero blocker/high/medium findings. This is fresh review cycle 1;
the rejected predecessor's three iterations do not carry into this replacement.

After implementation, compare actual diffs to this plan, run independent code
review, fix all blocker/high/medium findings, rerun affected gates, and only
then begin the parent plan's next task.

## Change history

- v0.1: fresh replacement. Removes reusable current manifests, adds explicit
  failure propagation, raising traversal errors, exact `rg` status handling,
  executable guard self-tests, stable double baseline, and closed regressions.
- v0.2: review iteration 1 remediation. Removes all helper-local shell-option
  toggles, uses conditional status capture, adds parent/ledger/matrix hash and
  size gates, and adds checked unified-diff plus exact allowed-file review.
