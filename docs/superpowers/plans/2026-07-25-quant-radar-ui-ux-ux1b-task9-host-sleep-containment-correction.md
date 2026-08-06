# Quant Radar UX-1B Task 9 Host-Sleep Containment Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | 1.0 |
| Status | Accepted; blocking-issue review passed |
| Authorization | Maintainer accepted Sequence 8 |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `8` |
| Recovery ID | `20260725T080000Z` |
| Tier ID | `20260725T081000Z` |
| Superseded active package | Sequence 7 Chromium path-budget correction |
| Imported predecessor | Sequence 7 plan, ledger, failed disposable canary manifest, and exact formal absences |
| Related plan | `docs/superpowers/plans/2026-07-25-quant-radar-ui-ux-ux1b-task9-chromium-path-budget-correction.md` |
| Related ledger | `docs/superpowers/plans/2026-07-25-quant-radar-ui-ux-ux1b-task9-host-sleep-containment-correction.traceability.yaml` |

## Context

Sequence 7 corrected the deterministic Chromium singleton-path failure from
Sequence 6. Its implementation and compatibility gates passed:

- the handoff contract suite passed `43 / 43`;
- the complete recovery target passed;
- the selected artifact-loader, FastAPI, and Streamlit fail-soft suites
  passed;
- Python 3.10 AST, `tabnanny`, dependency, and whitespace gates passed;
- package, authority, live, mirror, and supplemental cardinalities matched
  `30`, `50`, `315`, `268`, and `54`;
- the formal modeled paths were exactly `231` and `228` bytes; and
- the production-shaped canary model was exactly `237` bytes.

The single Sequence 7 disposable canary began and successfully launched a
series of Chromium captures. The host then entered low-power sleep before the
matrix completed. On wake, the bounded child deadline was already expired, so
the matrix atomically published a failed manifest with `0 / 0` in the public
summary and no final run receipt.

Sequence 7 explicitly says a failed canary blocks Tier 0 and MUST NOT be
rerun. Therefore:

- the Sequence 7 canary is not retried;
- Sequence 7 Tier 0 is not bootstrapped;
- recovery ID `20260725T010000Z` is retired without a formal intent;
- no Sequence 7 record grants migration or theme authority; and
- a new accepted sequence is required before another canary or formal action.

## Immutable Sequence 7 failure record

### Retained artifacts

| Artifact | SHA-256 | Size | Inode |
| --- | --- | ---: | ---: |
| Sequence 7 plan | `527f918a312d939b5171bb66303b116f62cf684c2c015f895198d3f68a9d376f` | 28262 | 13143966 |
| Sequence 7 ledger | `c1d26f5dcf6a059a80e1f9f49b312e6dce1391307d995bd1843c503ba2374e7d` | 3912 | 13144231 |
| Failed canary manifest | `cf27088f57c7735790920ad7acc645bce95a26a9fef76c4a2b92e396bb532f5a` | 340 | 13461432 |

The failed manifest path is:

```text
.claude/ui_snapshots/ux1b/sequence7-canary-20260725T010000Z/manifest.json
```

Its exact canonical bytes are:

```json
{"error":{"message":"UX-1B isolation contract: bounded child output timed out","type":"IsolationContractError"},"expectedCaptureCount":81,"fixtureEntrypoint":"scripts/ui_ux_fixture_app.py","mode":"ux1b-full-pages","phase":"pretheme","runId":"ux1b-ed76b0e0e801871080b2c805","schemaVersion":"quant-radar-ui-ux-evidence/v1","status":"failed"}
```

The manifest is mode `0600`, UID `501`, GID `0`, and a one-link regular file.
The disposable `/private/tmp/qr-ux1b-c7.*` runtime root was removed
bottom-up and is absent.

### Exact external interruption evidence

The local power-management log records:

```text
2026-07-25 06:57:19 +0800 Sleep Entering Sleep state due to 'Low Power Sleep':TCPKeepAlive=inactive Using Batt (Charge:1%) 11331 secs
2026-07-25 10:06:10 +0800 Wake Wake from Hibernate [CDNVA] : due to acattach rtc/UserActivity Assertion Using AC (Charge:1%) 29 secs
```

The canary output directory was created at `2026-07-25 06:50:54 +0800`.
Google Chrome for Testing created repeated capture power assertions between
`06:53` and `06:56`, immediately before the recorded low-power sleep. The
failed manifest was published at `10:06:10`, the wake time.

This establishes a causal host suspension, not a deterministic path-budget
failure:

1. Chromium had already launched before sleep.
2. The host slept for `11,331` seconds at `1%` battery.
3. The bounded child deadline expired across hibernation.
4. The wake and failed-manifest timestamps are the same second.
5. Ten post-incident process-table observations completed in
   `0.0331`–`0.0389` seconds, ruling out a stable two-second `/bin/ps`
   bottleneck.

### Exact formal absences

Sequence 7 never reached Tier 0. The following remain absent:

- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq7.json`;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq7.json`;
- `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260725T011000Z/`;
- `.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260725T010000Z.json`;
- all five Sequence 7 Task 9 lifecycle JSON leaves;
- `postcontrol-controls-20260725T010000Z/`;
- `canonical-pretheme-20260725T010000Z/`; and
- `/private/tmp/qr-ux1b-s7`.

The three retained records, all formal absences, and the absent runtime root
MUST remain exact. They MUST NOT be edited, deleted, renamed, relinked,
truncated, reconciled, or recreated.

## Problem statement

The capture workflow correctly fails closed when monotonic deadlines expire,
but the accepted execution plan did not establish a host-power precondition
or hold an explicit macOS sleep-prevention assertion around the long-running
canary and formal capture commands.

This is an execution-environment containment gap. It is not permission to:

- extend security timeouts;
- retry failed identifiers;
- weaken process quiescence;
- change the frozen capture stack;
- treat sleep as a passed capture; or
- suppress a real browser failure.

## Scope

### In scope

- Add a small, independently tested Darwin host-awake gate.
- Require exact AC-power, battery, open-clamshell, and `caffeinate`
  availability before a long capture.
- Execute the gate and `/usr/bin/caffeinate -dimsu` in one wrapper without a
  shell or an ambient command rewrite.
- Preserve the wrapped command's exit code.
- Use a new Sequence 8 canary namespace and formal recovery namespace.
- Import and stat-check the exact Sequence 7 failure record.
- Preserve the Sequence 7 short runtime path and path-budget oracle.
- Run one new production-shaped canary only after all new gates pass.
- Run Tier 0, fresh preflight verification, and one formal Task 9 command only
  after the new canary passes.

### Non-goals

- Do not rerun or delete the Sequence 7 canary.
- Do not bootstrap or reconcile Sequence 7.
- Do not change any of the nine capture-stack members.
- Do not change the `253`-byte isolation limit or the `16`-byte margin.
- Do not lengthen browser, calibration, process-table, or cleanup timeouts.
- Do not mutate FastAPI, Streamlit, artifact-loader, provider, writer, or
  fail-soft behavior.
- Do not alter macOS global power settings or call `sudo pmset`.
- Do not claim `caffeinate` can override critical-battery shutdown.

## Fixed Sequence 8 namespace

```text
Recovery ID: 20260725T080000Z
Tier ID:     20260725T081000Z
Runtime:     /private/tmp/qr-ux1b-s8
Canary root: /private/tmp/qr-ux1b-c8.XXXXX
Canary out:  .claude/ui_snapshots/ux1b/sequence8-canary-20260725T080000Z/
```

The formal modeled postcontrol and pretheme socket paths remain exactly `231`
and `228` bytes. A five-character canary suffix produces exactly `237` bytes.

## Host-awake design

### New gate

Add `scripts/ui_ux_awake_gate.py` with two commands:

```text
check --json
exec -- <absolute-or-workspace-command> [arguments...]
```

The gate is Darwin-only and invokes only these exact tools:

```text
/usr/bin/pmset -g batt
/usr/sbin/ioreg -r -k AppleClamshellState -d 4
/usr/bin/caffeinate -dimsu <command...>
```

Tool discovery does not use `PATH`. Probes run without a shell, with bounded
two-second deadlines and bounded stdout/stderr.

The parsed state MUST prove:

- power source is exactly `AC Power`;
- exactly one internal-battery percentage is present;
- battery is at least `50%`;
- AC is attached;
- `AppleClamshellState` is exactly `No`;
- `/usr/bin/caffeinate` is an owned executable regular file; and
- the requested command is nonempty, contains no NUL, and is not a shell
  string.

`check --json` emits a bounded sanitized record. It contains no serial number,
hardware identifier, command environment, home path, or raw `ioreg` dump.

`exec` performs the same check and immediately replaces itself with:

```text
/usr/bin/caffeinate -dimsu <command...>
```

using `os.execve`. There is no check-to-exec subprocess gap, no shell
interpolation, and no retry. The wrapped command remains responsible for its
existing lifecycle, failure, and cleanup behavior.

### Why both power gates are needed

`caffeinate -s` is effective only on AC power. It cannot manufacture energy or
override a critical-battery shutdown. The explicit `>= 50%`, AC-attached, and
open-clamshell checks prevent the exact Sequence 7 incident; `-dimsu` then
holds the standard macOS display, idle-system, disk, system, and user-active
assertions for the command duration.

### Fail-closed behavior

Any malformed, missing, ambiguous, timed-out, non-Darwin, low-battery,
battery-powered, closed-clamshell, or unavailable-caffeinate state exits
before `execve` and before any canary or formal namespace is created.

The wrapper does not reinterpret the wrapped command's result. A browser
failure remains a browser failure and is not retried.

## Requirements

### `REQ-008` — long captures require a verified awake host

No Sequence 8 canary or formal Task 9 capture may launch unless the exact host
power gate passes immediately before an exec-bound `caffeinate` assertion.

### `CFR-021` — immutable Sequence 7 closure

The exact Sequence 7 plan, ledger, failed canary manifest, formal absences,
retired recovery ID, and removed disposable runtime root are imported without
mutation or retry.

### `CFR-022` — deterministic power-state parser

The gate accepts only exact AC, battery, and clamshell state; malformed or
ambiguous tool output fails closed without exposing raw host data.

### `CFR-023` — gapless sleep assertion

The accepted host state and the wrapped command are joined by `os.execve` to
the exact system `caffeinate` binary. No shell, retry loop, timeout extension,
or global power mutation is allowed.

### `CFR-024` — compatibility and path preservation

The Sequence 7 path-budget fix, capture stack, security timeouts, process
quiescence, and all API/Streamlit fail-soft behavior remain exact.

### `CFR-025` — one-shot Sequence 8 closure

One new canary may run under the new namespace. Only a passed `81 / 81`
manifest, clean runtime removal, and quiescent processes permit Sequence 8
Tier 0. The formal command then runs at most once and must close with a passed
or revoked terminal.

## Acceptance criteria

### `AC-SEQ8-001` — predecessor import

Sequence 8 imports the three exact retained Sequence 7 records, verifies their
SHA-256, size, inode, mode, and regular-file identity, proves every formal
absence, and proves both Sequence 7 runtime roots are absent.

### `AC-SEQ8-002` — power parser closure

Exact AC power, a battery percentage of at least `50`, attached AC, and open
clamshell pass. Battery power, `49%`, missing/duplicate batteries, malformed
percentages, ambiguous sources, closed clamshell, missing tools, timeouts, and
oversized output all fail.

### `AC-SEQ8-003` — gapless caffeinate exec

The `exec` command revalidates the host and calls `os.execve` exactly once with
`/usr/bin/caffeinate`, flags `-dimsu`, and the unchanged argv. It never invokes
a shell and never returns on success.

### `AC-SEQ8-004` — no pre-gate side effects

Every host-gate failure leaves the new canary, Tier 0, lifecycle, formal
runtime, and output namespaces absent.

### `AC-SEQ8-005` — unchanged security and fail-soft contracts

All capture-stack digests, path counts, timeouts, source policies, process
gates, API tests, Streamlit tests, and artifact-loader tests remain exact.

### `AC-SEQ8-006` — production-shaped canary

With AC power, battery at least `50%`, open clamshell, exact `237`-byte model,
and the exec-bound assertion, the one Sequence 8 canary passes `81 / 81`,
publishes a canonical disposable manifest, removes its private runtime root,
and leaves no owned process.

### `AC-SEQ8-007` — formal one-shot

After the canary and all formal preflight gates pass, one wrapped formal Task
9 command runs. Success publishes a passed terminal. A typed runner failure
publishes a revoked terminal and preserves the original public exit.

## Affected files

### Planned source changes

- `scripts/ui_ux_awake_gate.py`
- `scripts/test_ui_ux_awake_gate.py`
- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `Makefile`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`

### Plan, traceability, and journals

- this plan;
- `docs/superpowers/plans/2026-07-25-quant-radar-ui-ux-ux1b-task9-host-sleep-containment-correction.traceability.yaml`;
- `.agents/scribe.md`;
- `.agents/builder.md`; and
- `.agents/PROJECT.md`.

### Explicitly unchanged

All nine members named by
`docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json`, including:

- `scripts/ui_ux_snapshot_matrix.py`;
- `scripts/ui_ux_isolation.py`;
- `scripts/ui_ux_browser_worker.py`;
- `scripts/ui_ux_evidence.py`; and
- the fixture and theme-matrix members.

## Closed cardinalities

Adding the Sequence 8 plan/ledger, retaining the Sequence 7 plan/ledger,
importing its failed canary manifest, and adding two new source files yields:

| Set | Exact count |
| --- | ---: |
| Authorization package records | `33` |
| Tier 0 authority records | `53` |
| Tier 0 live records | `320` |
| Source mirror records | `270` |
| Supplemental source records | `57` |
| Capture-stack members | `9` |

These counts are acceptance gates, not estimates.

## Implementation checklist

- [ ] `IMPL-040`: Freeze Sequence 7 plan, ledger, failed canary manifest, and
  formal absences as exact imported authorities.
- [ ] `IMPL-041`: Add the pure, bounded AC/battery/clamshell parser.
- [ ] `IMPL-042`: Add the exact `check --json` CLI.
- [ ] `IMPL-043`: Add the revalidating `exec` path and exact
  `/usr/bin/caffeinate -dimsu` `os.execve` boundary.
- [ ] `IMPL-044`: Move the authorization package and all future namespaces to
  Sequence 8 while preserving the Sequence 7 path-budget implementation.
- [ ] `IMPL-045`: Add red-first host-state, argv, side-effect, predecessor,
  cardinality, and mutation tests.
- [ ] `IMPL-046`: Run all recovery, fail-soft, syntax, dependency, whitespace,
  capture-stack, path, process, and power-state gates.
- [ ] `IMPL-047`: Run the new wrapped canary once, then Tier 0, fresh preflight,
  and one wrapped formal command only if every prior gate passes.

## Test specification

| Test | Verifies |
| --- | --- |
| `TEST-058` | Exact Sequence 7 retained records and absences are immutable. |
| `TEST-059` | Exact AC/`>=50%`/attached/open state passes. |
| `TEST-060` | Every malformed, ambiguous, low-power, battery, and closed-lid mutation fails. |
| `TEST-061` | Tool timeouts, nonzero exits, oversized output, and unsafe tool identity fail. |
| `TEST-062` | `exec` rechecks and calls exact `caffeinate -dimsu` argv once without a shell. |
| `TEST-063` | Host-gate failure creates no canary, Tier 0, lifecycle, or runtime path. |
| `TEST-064` | Counts are exactly package `33`, authority `53`, live `320`, mirror `270`, supplemental `57`. |
| `TEST-065` | Capture-stack, path-budget, process, and fail-soft compatibility gates remain exact. |
| `TEST-066` | One wrapped canary passes `81 / 81`; one wrapped formal command closes terminally. |

## Commands and gates

Before any canary or formal publication:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_awake_gate.py
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run the selected API and Streamlit fail-soft suites, Python 3.10 AST,
`tabnanny`, `pip check`, `git diff --check`, exact predecessor stats,
authorization and traceability validation, closed cardinalities, capture-stack
digests, future absences, runtime-root absence, and process quiescence.

The new one-shot canary is:

```bash
set -euo pipefail
canary_root="$(mktemp -d /private/tmp/qr-ux1b-c8.XXXXX)"
canary_epoch="${canary_root}/20260725T080000Z"
canary_stage="${canary_epoch}/postcontrol"
canary_tmp="${canary_stage}/tmp"
trap 'rmdir "$canary_tmp" "$canary_stage" "$canary_epoch" "$canary_root"' EXIT
mkdir -m 0700 "$canary_epoch" "$canary_stage" "$canary_tmp"
TMPDIR="$canary_tmp" TMP="$canary_tmp" TEMP="$canary_tmp" \
  .venv/bin/python -B scripts/ui_ux_awake_gate.py exec -- \
    .venv/bin/python -B scripts/ui_ux_snapshot_matrix.py \
      --profile ux1b-full-pages \
      --phase pretheme \
      --browser chromium \
      --out-dir .claude/ui_snapshots/ux1b/sequence8-canary-20260725T080000Z \
      --no-prompt \
      --json
```

Before this command, the independent path oracle MUST prove exactly `237`
bytes, the host gate MUST pass, and both the output and canary root glob MUST
be absent.

Only after a canonical `81 / 81` passed canary, clean runtime removal, and
process quiescence:

```bash
.venv/bin/python -B scripts/ui_ux_awake_gate.py exec -- \
  /usr/bin/make ui-ux1b-theme-handoff-bootstrap \
    UX1B_RECOVERY_ID=20260725T080000Z
.venv/bin/python -B scripts/ui_ux_awake_gate.py exec -- \
  /usr/bin/make ui-ux1b-theme-handoff-preflight \
    UX1B_RECOVERY_ID=20260725T080000Z
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-preflight \
  --recovery-id 20260725T080000Z --json
.venv/bin/python -B scripts/ui_ux_awake_gate.py exec -- \
  /usr/bin/make ui-ux1b-recovery-postcontrol \
    UX1B_RECOVERY_ID=20260725T080000Z \
    UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260725T080000Z.json
```

The last command is the only authorized formal Task 9 capture invocation for
Sequence 8.

## Failure policy

- Sequence 7 is immutable and never retried.
- A host gate failure creates no new namespace and may be run again after the
  host condition changes because no canary or recovery attempt began.
- Once the Sequence 8 canary output directory is created, that canary is
  one-shot. A failed manifest blocks Tier 0 and is not retried.
- Any committed Sequence 8 intent burns recovery ID `20260725T080000Z`.
- A formal runner failure must publish a revoked terminal and is not retried.
- A terminal-publication failure requires a new accepted correction and ID.
- No failed, revoked, retired, or disposable record grants forward authority.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| AC is removed after the check | Gate and assertion are joined by `execve`; require `>=50%`; do not claim protection from deliberate unplugging. |
| The lid is closed during capture | Require open clamshell and `-d`; operator must keep the lid open for the one-shot window. |
| `caffeinate` masks a browser hang | It changes only host sleep assertions; all existing browser deadlines remain exact. |
| Wrapper changes command semantics | Exact argv tests, no shell, `os.execve`, and preserved command exit status. |
| Historical failure is lost | Import exact digest, size, inode, mode, canonical bytes, and formal absences. |
| Counts drift | Enforce `33 / 53 / 320 / 270 / 57` in red-first tests. |

## Rollback

- Before Sequence 8 Tier 0, rollback removes only uncommitted Sequence 8 code
  and authorization changes.
- Rollback preserves every Sequence 1–7 artifact and all unrelated dirty
  worktree changes.
- After Tier 0, Sequence 8 evidence is immutable; any correction requires a
  new sequence and recovery ID.
- The failed Sequence 7 canary is never deleted during rollback.

## Blocking-issue review

### Review iteration 1

- **Finding:** `caffeinate` cannot prevent a critical-battery sleep.
- **Resolution:** Require exact AC attachment and at least `50%` battery before
  exec; retain ordinary browser deadlines.
- **Status:** Closed.

### Review iteration 2

- **Finding:** A separate check command leaves a race before the assertion.
- **Resolution:** Revalidate inside `exec` and immediately `os.execve` the
  exact `/usr/bin/caffeinate` command without a shell.
- **Status:** Closed.

### Review iteration 3

- **Finding:** System-sleep assertions do not authorize closed-lid operation.
- **Resolution:** Require `AppleClamshellState = No`, document the open-lid
  operator invariant, and do not alter global power settings.
- **Status:** Closed.

### Review iteration 4

- **Finding:** Reusing the Sequence 7 canary or recovery ID would violate its
  no-retry policy and erase causal evidence.
- **Resolution:** Freeze the exact failure, use Sequence 8 IDs and namespaces,
  and import Sequence 7 only as non-forward authority.
- **Status:** Closed.

### Review iteration 5

- **Finding:** Adding two source files changes both mirror and live counts.
- **Resolution:** Close the counts at package `33`, authority `53`, live
  `320`, mirror `270`, and supplemental `57`.
- **Status:** Closed.

No unresolved blocking issue remains in the proposed plan. Maintainer
acceptance is still required before implementation.

## Review checklist

- [x] The actual Sequence 7 failure is preserved exactly.
- [x] The external sleep cause is supported by local power logs.
- [x] Sequence 7 is not retried or bootstrapped.
- [x] The new host gate fails before side effects.
- [x] No security timeout or capture-stack member changes.
- [x] The check-to-assertion gap is closed with `execve`.
- [x] The new namespaces are disjoint.
- [x] Cardinalities include both new source files and predecessor evidence.
- [x] Rollback preserves unrelated and historical state.
- [x] Repository maintainer accepts Sequence 8.
- [ ] Implementation and red-first tests pass.
- [ ] New canary passes `81 / 81`.
- [ ] Fresh preflight reopens before the formal one-shot.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-07-25 | Accepted by the repository maintainer after the host-power, no-retry, namespace, and cardinality blockers were closed. |
| 0.9 | 2026-07-25 | Proposed after the Sequence 7 canary was interrupted by a logged 1%-battery hibernation; five distinct blocking reviews closed power, race, clamshell, no-retry, and cardinality gaps. |
