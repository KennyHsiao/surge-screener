# TEST-021 Task 1 zsh Guard Execution Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Implementation correction checklist |
| Version | v0.3 |
| Status | Review candidate; guard re-execution blocked until PASS |
| Date | 2026-07-21 |
| Author | Codex / Scribe |
| Audience | Maintainer and independent Task 1 reviewer |
| Corrects | Accepted Task 1 plan SHA `f8bc4ed48c7addbc2de0bfba74a104f6908d5fc28c1a528e52c11bc3e7dba639` |

## Runtime evidence and decision

The first real initialization used `zsh -f` and stopped before any source edit.
`assert_no_trailing_whitespace` declared and assigned `local status`. In zsh,
`status` is a read-only special parameter. Assignment terminated the shell with:

```text
assert_no_trailing_whitespace:6: read-only variable: status
```

The source preimages remained exact. The private partial directory remained,
which also proved an EXIT trap does not run for this zsh fatal parameter error.
Therefore the accepted plan is semantically valid but its execution wrapper is
not sufficient in the actual shell.

## Scope

This correction changes no production, test, parent, matrix, API, UI,
dependency, Makefile, or evidence artifact. It authorizes only:

- replacing helper-local `status` with non-special names such as
  `command_status` and `diff_status` in the private guard implementation;
- running initialization in a child `zsh -f` supervised by an outer clean
  `zsh -f` session;
- creating mode-0600 guard function/initialization scripts only inside the
  mode-0700 private staging directory with `apply_patch`, before a real
  preimage directory exists;
- explicit prefix-guarded cleanup by the supervisor after any child failure;
- preserving the accepted plan's hashes, commands, scope, semantics, and gates.

## Requirements

### CFR-T1-ZSH-001 — No special parameter collision

Private shell helpers MUST NOT declare or assign `status`, `pipestatus`,
`commands`, `functions`, or any other zsh special parameter. The corrected
helpers use `command_status`, `diff_status`, and `search_status` only.

### CFR-T1-ZSH-002 — Cleanup is externally supervised

The initialization child MUST run under a separate outer `zsh -f`. The outer
session captures the child's status with a checked `if`. On nonzero status, it
validates the exact `/private/tmp/quant-radar-test021-v2.*` prefix, removes only
that newly created private directory, verifies absence, and exits nonzero.

The child does not own cleanup authority. An EXIT trap may remain as a backup,
but it is not counted as the failure-path proof.

### CFR-T1-ZSH-003 — Functions persist only after success

The staging directory first contains two mode-0600 files:

- `guard-functions.zsh`: the seven-item ordered `TASK1_ALLOWED_PATHS` array,
  its exact-order assertion, and all definitions with corrected variable names;
- `guard-init.zsh`: exact accepted initialization checks and self-tests. Its
  first executable line sources `guard-functions.zsh`, then it calls the
  allowlist assertion before any hash, copy, or manifest operation.

No real preimage directory exists while external `apply_patch` prepares these
files. Any staging edit or validation failure immediately calls the common
cleanup function on the staging directory and stops.

One checked `run_real_initialization` function then creates the real directory,
installs the staged scripts, executes the child, sources the same functions in
the outer session, loads the child cache, reruns the guards, and removes
staging. Every fallible command explicitly uses `|| return $?`. The caller
captures any nonzero status, cleans the real directory, verifies absence, and
exits with that status. Only the full success path sets readiness to 1.

The rejected wrapper that creates its own directory or depends on an EXIT trap
MUST NOT be sourced or executed.

## Exact supervisor flow

```zsh
zsh -f
set -eu
export TASK1_GUARDS_READY=0

test -n "${TASK1_ACCEPTED_CORRECTION_SHA:-}"
test -n "${TASK1_ACCEPTED_CORRECTION_SIZE:-}"
correction_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-zsh-guard-execution-correction.md)
test "${correction_hash%% *}" = "$TASK1_ACCEPTED_CORRECTION_SHA"
test "$(stat -f %z docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-zsh-guard-execution-correction.md)" = "$TASK1_ACCEPTED_CORRECTION_SIZE"
primary_hash=$(shasum -a 256 docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md)
test "${primary_hash%% *}" = f8bc4ed48c7addbc2de0bfba74a104f6908d5fc28c1a528e52c11bc3e7dba639

cleanup_private_dir() {
  local cleanup_target="$1"
  case "$cleanup_target" in
    /private/tmp/quant-radar-test021-v2.*|/private/tmp/quant-radar-test021-guard-stage.*)
      command rm -rf -- "$cleanup_target" || return $?
      ;;
    *)
      print -r -- "refusing unsafe private cleanup path" >&2
      return 70
      ;;
  esac
  test ! -e "$cleanup_target" || return $?
}

# Failure drill uses the exact real-failure cleanup function before a real
# TASK1_PRIVATE_PREIMAGE_DIR exists.
export TASK1_PRIVATE_PREIMAGE_DIR=""
drill_fixture=$(mktemp -d /private/tmp/quant-radar-test021-v2.drill.XXXXXX)
chmod 0700 "$drill_fixture"
if zsh -f -c 'exit 73'; then
  drill_child_status=0
else
  drill_child_status=$?
fi
if (( drill_child_status != 0 )); then
  cleanup_private_dir "$drill_fixture"
fi
test "$drill_child_status" = 73
test ! -e "$drill_fixture"
test -z "$TASK1_PRIVATE_PREIMAGE_DIR"

TASK1_GUARD_STAGE_DIR=$(mktemp -d /private/tmp/quant-radar-test021-guard-stage.XXXXXX)
export TASK1_GUARD_STAGE_DIR
if chmod 0700 "$TASK1_GUARD_STAGE_DIR"; then
  stage_create_status=0
else
  stage_create_status=$?
fi
if (( stage_create_status != 0 )); then
  cleanup_private_dir "$TASK1_GUARD_STAGE_DIR" || exit $?
  exit "$stage_create_status"
fi

# Use apply_patch before continuing. If either edit fails, immediately run:
# cleanup_private_dir "$TASK1_GUARD_STAGE_DIR"
# No real TASK1_PRIVATE_PREIMAGE_DIR exists at that point.
if test -f "$TASK1_GUARD_STAGE_DIR/guard-functions.zsh" \
   && test -f "$TASK1_GUARD_STAGE_DIR/guard-init.zsh" \
   && chmod 0600 "$TASK1_GUARD_STAGE_DIR/guard-functions.zsh" \
   && chmod 0600 "$TASK1_GUARD_STAGE_DIR/guard-init.zsh"; then
  stage_validation_status=0
else
  stage_validation_status=$?
fi
if (( stage_validation_status != 0 )); then
  cleanup_private_dir "$TASK1_GUARD_STAGE_DIR" || exit $?
  exit "$stage_validation_status"
fi

run_real_initialization() {
  TASK1_PRIVATE_PREIMAGE_DIR=$(mktemp -d /private/tmp/quant-radar-test021-v2.XXXXXX) || return $?
  export TASK1_PRIVATE_PREIMAGE_DIR || return $?
  chmod 0700 "$TASK1_PRIVATE_PREIMAGE_DIR" || return $?
  install -m 0600 "$TASK1_GUARD_STAGE_DIR/guard-functions.zsh" "$TASK1_PRIVATE_PREIMAGE_DIR/guard-functions.zsh" || return $?
  install -m 0600 "$TASK1_GUARD_STAGE_DIR/guard-init.zsh" "$TASK1_PRIVATE_PREIMAGE_DIR/guard-init.zsh" || return $?
  test -f "$TASK1_PRIVATE_PREIMAGE_DIR/guard-functions.zsh" || return $?
  test -f "$TASK1_PRIVATE_PREIMAGE_DIR/guard-init.zsh" || return $?

  if TASK1_ACCEPTED_PLAN_SHA=f8bc4ed48c7addbc2de0bfba74a104f6908d5fc28c1a528e52c11bc3e7dba639 \
     TASK1_PRIVATE_PREIMAGE_DIR="$TASK1_PRIVATE_PREIMAGE_DIR" \
     PYTHONDONTWRITEBYTECODE=1 \
     zsh -f "$TASK1_PRIVATE_PREIMAGE_DIR/guard-init.zsh"; then
    child_status=0
  else
    child_status=$?
  fi
  (( child_status == 0 )) || return "$child_status"

  source "$TASK1_PRIVATE_PREIMAGE_DIR/guard-functions.zsh" || return $?
  assert_task1_allowed_paths || return $?
  test -f "$TASK1_PRIVATE_PREIMAGE_DIR/cache.before.sha256" || return $?
  test ! -L "$TASK1_PRIVATE_PREIMAGE_DIR/cache.before.sha256" || return $?
  TASK1_CACHE_BEFORE=$(<"$TASK1_PRIVATE_PREIMAGE_DIR/cache.before.sha256") || return $?
  export TASK1_CACHE_BEFORE || return $?
  [[ "$TASK1_CACHE_BEFORE" != *[^0-9a-f]* ]] || return 65
  test "${#TASK1_CACHE_BEFORE}" = 64 || return $?
  test "$(cache_fingerprint)" = "$TASK1_CACHE_BEFORE" || return $?
  assert_workspace_unchanged || return $?
  cleanup_private_dir "$TASK1_GUARD_STAGE_DIR" || return $?
  export TASK1_GUARDS_READY=1 || return $?
  test "$TASK1_GUARDS_READY" = 1 || return $?
}

if run_real_initialization; then
  real_init_status=0
else
  real_init_status=$?
fi

if (( real_init_status != 0 )); then
  if [[ -n "${TASK1_PRIVATE_PREIMAGE_DIR:-}" ]]; then
    failed_private_dir="$TASK1_PRIVATE_PREIMAGE_DIR"
    cleanup_private_dir "$failed_private_dir" || exit $?
  fi
  if [[ -n "${TASK1_GUARD_STAGE_DIR:-}" && -e "$TASK1_GUARD_STAGE_DIR" ]]; then
    cleanup_private_dir "$TASK1_GUARD_STAGE_DIR" || exit $?
  fi
  exit "$real_init_status"
fi

print -r -- TASK1_GUARDS_READY
```

The outer variables use no zsh special names. Cleanup authority is limited to
the exact fresh directory returned by `mktemp` in the same session.

The staged `guard-functions.zsh` begins with this complete shared state.
Neither child nor
outer defines a second allowlist:

```zsh
typeset -ga TASK1_ALLOWED_PATHS
TASK1_ALLOWED_PATHS=(
  scripts/ui_ux_theme_handoff.py
  scripts/test_ui_ux_theme_handoff.py
  docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md
  .agents/scribe.md
  .agents/builder.md
  .agents/radar.md
  .agents/PROJECT.md
)

assert_task1_allowed_paths() {
  local -a expected_paths
  local path_index
  expected_paths=(
    scripts/ui_ux_theme_handoff.py
    scripts/test_ui_ux_theme_handoff.py
    docs/superpowers/plans/2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md
    .agents/scribe.md
    .agents/builder.md
    .agents/radar.md
    .agents/PROJECT.md
  )
  test "${#TASK1_ALLOWED_PATHS[@]}" = 7 || return $?
  for path_index in {1..7}; do
    test "${TASK1_ALLOWED_PATHS[$path_index]}" = "${expected_paths[$path_index]}" || return $?
  done
}
```

The staged `guard-init.zsh` begins exactly with:

```zsh
set -eu
source "${TASK1_PRIVATE_PREIMAGE_DIR:?}/guard-functions.zsh"
assert_task1_allowed_paths
```

After the accepted initialization computes `TASK1_CACHE_BEFORE`, the child
writes that 64-character lowercase hex plus one newline to a new mode-0600
`cache.before.sha256` using `O_CREAT|O_EXCL|O_NOFOLLOW`, flushes/fsyncs it, and
reopens it before exit. The outer loads that exact child value; it does not mint
a new baseline fingerprint.

## Corrected helper pattern

Both accepted status-capturing helpers use this form:

```zsh
assert_no_trailing_whitespace() {
  local output
  local search_status
  if output=$(rg -n '[[:blank:]]+$' "$@" 2>&1); then
    search_status=0
  else
    search_status=$?
  fi
  if (( search_status == 1 )) && [[ -z "$output" ]]; then
    return 0
  fi
  [[ -z "$output" ]] || print -r -- "$output" >&2
  return 1
}

show_no_index_diff() {
  local diff_status
  if git diff --no-index -- "$1" "$2"; then
    diff_status=0
  else
    diff_status=$?
  fi
  if (( diff_status == 0 || diff_status == 1 )); then
    return 0
  fi
  return "$diff_status"
}
```

`assert_no_index_whitespace_clean` uses `diff_status` identically. No helper
changes caller shell options.

## Pre-source execution gates

Before running real initialization:

```zsh
zsh -f -c 'set -eu; f() { local command_status; command_status=0; test "$command_status" = 0; }; f'
zsh -f -c 'set -eu; f() { local search_status; search_status=1; test "$search_status" = 1; }; f'
zsh -f -c 'set -eu; f() { local diff_status; diff_status=1; test "$diff_status" = 1; }; f'
```

All exit 0. A separate private fixture forces an initialization child to exit
73; the outer supervisor uses `cleanup_private_dir`, verifies the fixture is
absent, records status 73, and continues only because this is the explicit
drill. This runs before the real directory is created. Real child failure uses
the same function and exits with the real child status.

## Acceptance criteria

### AC-T1-ZSH-001 — Reserved variable regression

Given clean zsh without user rc files, when every corrected helper assigns its
local status variable, then the shell remains alive and all three probes exit 0.

### AC-T1-ZSH-002 — Fatal child cleanup

Given a fresh private fixture and an initialization child that exits 73, when
the supervisor handles the result, then only that fixture is removed and the
supervisor reports 73. EXIT-trap behavior is not used as evidence.

### AC-T1-ZSH-003 — Real guard readiness

Given all accepted-plan authority and preimage checks, when the corrected child
initialization exits 0, then the outer session sources definitions, both the
cache and in-memory workspace comparisons pass, and readiness becomes 1.

### AC-T1-ZSH-004 — Outer failure cleanup

Given a successful child and an injected failure at each outer step from
functions source through final workspace comparison, when the checked real
initializer returns nonzero, then the caller removes both real and staging
directories, verifies absence, leaves readiness 0, and returns the injected
status.

## Verification and rollback

- Recheck the accepted plan SHA before child execution.
- Recheck this correction against externally supplied reviewed SHA and size
  before any private guard script or real directory is created.
- Recheck source preimage hashes after the failed attempt and before the new
  attempt.
- Treat the observed partial private directory as diagnostic evidence until
  this correction passes review. Then remove it with the same exact prefix and
  absence checks before creating the fresh real directory.
- If the corrected real initialization fails, the supervisor removes its own
  fresh directory and implementation remains blocked.
- No workspace rollback is needed because no production/test edit occurred.

## Traceability

| Requirement | Acceptance | Runtime owner |
| --- | --- | --- |
| CFR-T1-ZSH-001 | AC-T1-ZSH-001 | private guard helpers |
| CFR-T1-ZSH-002 | AC-T1-ZSH-002 | outer `zsh -f` supervisor |
| CFR-T1-ZSH-003 | AC-T1-ZSH-003,004 | child init plus outer session |

## Review gate

Guard re-execution requires a fresh independent PASS with zero
blocker/high/medium. After PASS, this correction and accepted plan SHA
`f8bc4ed48c7addbc2de0bfba74a104f6908d5fc28c1a528e52c11bc3e7dba639`
jointly govern Task 1 execution. Production implementation remains blocked
until AC-T1-ZSH-001..003 pass.

## Change history

- v0.1: records the real zsh special-parameter failure and replaces trap-only
  cleanup with a separately supervised child initialization.
- v0.2: makes the functions file the sole allowlist/definition owner, sources
  it in child and outer, adds exact array-order checks, an executable
  same-cleanup failure drill, child-owned cache transfer, and correction
  authority gates.
- v0.3: stages external `apply_patch` inputs before any real directory exists,
  wraps every real setup/post-child step in explicit failure propagation, and
  routes all returned failures through common real/staging cleanup.
