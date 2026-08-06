# UX-1B Task 1 Semantic Evidence Remediation Plan

## Document Info

| Field | Value |
| --- | --- |
| Version | v0.3 |
| Status | Review candidate — reviewer PASS accepts these exact bytes; otherwise blocked |
| Date | 2026-07-21 |
| Author | Codex / Scribe |
| Audience | Quant Radar maintainers, implementers, independent reviewers |
| Reviewer | Independent changed-code reviewer |
| Parent authority | `2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md` |
| Parent SHA-256 | `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581` |
| Parent ledger SHA-256 | `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8` |

## Purpose

Close the final Task 1 `TEST-021` blockers without changing the accepted parent
contract. The current test-owned HMAC stream proves that operations were
attempted, but not that their required results occurred. The current outer
process sample also follows only the original PGID and can miss a token-bearing
descendant after `setsid()`.

This document is an implementation checklist and test specification. It grants
no lifecycle, capture, publication, rollback, or Task 2 authority.

## Scope

In scope:

- Add injected syscall and Playwright operation seams whose direct unit tests
  prove the required semantics for all 194 capability outcomes.
- Prove that the fixed runner consumes those seams and cannot replace their
  results with a constant assertion document.
- Sample the exact marker-plus-PGID process-family union required by the parent
  plan.
- Add pacifier and detached-descendant mutants that must be rejected.
- Preserve the Task 1 fail-first result: 29 controlled missing-behavior
  failures and zero unexpected failures.

Out of scope:

- Implementing any Task 2 behavior in `scripts/ui_ux_theme_handoff.py`; only
  import-safe fail-first seam declarations may be added.
- Editing the accepted parent plan, its ledger, recovery authority, UI code,
  Makefile, dependencies, or runtime configuration.
- Changing the production capability-probe argv, stdout schema, environment,
  `passFds:[]`, or process-control contract.

## Frozen Inputs and Affected Files

Frozen and read-only:

- Parent plan and ledger at the hashes above.

Authenticated preimage:

- `scripts/ui_ux_theme_handoff.py` starts at SHA-256
  `a99f577c3f4b629b953502b12e48b29f19619029791681c38dbf4c89b48defe6`.
  Its only permitted changes are adding the closed Protocol declarations and
  named Task 1 fail-first seams below. Both seams still raise
  `ThemeHandoffNotImplemented("TEST-021", ...)` without I/O.

Implementation scope:

- `scripts/test_ui_ux_theme_handoff.py`
- `scripts/ui_ux_theme_handoff.py`, limited to those declarations.

Documentation/log scope:

- This new plan.
- `.agents/scribe.md` and `.agents/PROJECT.md` only for required skill records.

## Requirements

### REQ-SE-001 — Result-bearing operation evidence

For every expected positive or negative `ProbeOutcome`, a direct test MUST
exercise an operation seam with injected syscall/API dependencies and prove
the complete return, exception, cleanup, and payload semantics. A pre-call
Python audit event and a matching child-reported row are insufficient.

### CFR-SE-001 — Closed mutation-resistant oracle

Tests MUST cover both the operation seams and their consumption by the fixed
runner. A seam that returns expected fields without performing its required
dependency calls, or a runner that ignores a seam result and emits constant
JSON, MUST fail. The existing anonymous-pipe HMAC stream remains bounded proof
of process identity and attempted operations; it is not described as an
independent result oracle against arbitrary code executing in the same Python
interpreter.

### REQ-SE-002 — Exact process-family union

The outer observer MUST use the parent plan's exact `/bin/ps eww` projection.
During execution and at closure it MUST classify same-UID rows matching either
the original PGID or the exact raw-token marker. Passed closure requires both
sets empty.

### REQ-SE-003 — Browser semantic evidence

The browser operation seam MUST be directly tested with an injected Playwright
object graph that records API executable path, default launch without
`executable_path`, launched browser version, page creation, and
page/context/browser closure. A real integration run MUST additionally observe
the headless-shell, renderer, and final marker-plus-PGID quiescence.

### CFR-SE-002 — Test transparency and production isolation

Injected dependencies exist only in direct unit tests. The fixed private
bootstrap MUST use real dependencies and keep its production execution plan,
argv, environment, stdout schema, and `passFds:[]` unchanged. Test-only audit
descriptors remain disclosed in the private observation and absent from every
serialized receipt.

### CFR-SE-003 — Fail-first and workspace safety

The verifier implementation MUST remain fail-first. Tests MUST use owned
scratch paths, bound timeouts, and deterministic cleanup. No real lifecycle
output or existing production/UI file may change.

## Design

### 1. Architecture decision: three-layer correctness oracle

The test suite does not treat code inside the candidate interpreter as a
cryptographic trust boundary. Arbitrary hostile introspection of authenticated,
reviewed candidate source is outside this test's threat model. The required
fitness function instead combines three independent failure surfaces:

1. Direct white-box operation tests inject recording syscall, subprocess, and
   Playwright dependencies into named fail-first seams.
2. Runner-dependency mutations prove `_run_capability_probe()` consumes every
   seam result and serializes it, rather than emitting expected constants.
3. A real Darwin Seatbelt run proves the integrated profile, process, import,
   executable, network, browser-process, and quiescence behavior.

Considered alternatives:

| Option | Decision | Reason |
| --- | --- | --- |
| Same-interpreter secret wrappers | Rejected | Candidate introspection can recover closures/globals, bypass wrappers, and restore identities before `atexit`. |
| Parent-owned TCP/file endpoints | Rejected | It would no longer prove the parent contract's endpoints-inside-probe and exact candidate file operations. |
| Privileged kernel tracing | Rejected | It requires unavailable root/EndpointSecurity/DTrace authority and is not a portable repository test. |
| Injectable seams plus dependency mutations and real integration | Selected | It is deterministic, fail-first, mutation-resistant for reviewed source, and preserves the production runtime contract. |

Consequence: this suite proves implementation correctness under authenticated
source review; it does not claim to sandbox malicious Python from its own
interpreter. The existing HMAC audit channel remains useful for process
identity and attempt evidence, not semantic result authority.

### 2. Closed operation seams and outcome recipes

Add import-safe structural declarations for three closed Protocols:

- `ProbeSocket` exposes only `bind`, `listen`, `getsockname`, `accept`,
  `connect`, `sendall`, `sendto`, `recv`, `recvfrom`, `settimeout`, and `close`;
- `ProbeChild` exposes only `pid`, `returncode`, `communicate`, `poll`, `wait`,
  `terminate`, and `kill`;
- `ProbeOperations` exposes only `import_module`, `open`, `read`, `write`,
  `fstat`, `lstat`, `close`, `unlink`, `fsync`, `listdir`, `scandir`, `socket`,
  `socketpair`, `getaddrinfo`, `popen`, and `killpg`.

The Protocol method signatures mirror the corresponding Python primitive and
use explicit keyword-only timeout, byte-limit, environment, cwd, stdin, and
process-group arguments where applicable. No method may return a
`ProbeOutcome`, browser receipt, assertion ID, or other high-level pass/fail
facade. Tests inspect the exact Protocol member set and signatures and reject
extra members.

The declarations are exactly this structural surface; `PathLike` values are
normalized in the dispatcher context before a dependency call:

```python
class ProbeSocket(Protocol):
    def bind(self, address: Any, /) -> None: ...
    def listen(self, backlog: int = 128, /) -> None: ...
    def getsockname(self) -> Any: ...
    def accept(self) -> tuple["ProbeSocket", Any]: ...
    def connect(self, address: Any, /) -> None: ...
    def sendall(self, data: bytes, flags: int = 0, /) -> None: ...
    def sendto(self, data: bytes, address: Any, /) -> int: ...
    def recv(self, bufsize: int, flags: int = 0, /) -> bytes: ...
    def recvfrom(self, bufsize: int, flags: int = 0, /) -> tuple[bytes, Any]: ...
    def settimeout(self, value: float | None, /) -> None: ...
    def close(self) -> None: ...

class ProbeChild(Protocol):
    pid: int
    returncode: int | None
    def communicate(
        self, input: bytes | None = None, timeout: float | None = None
    ) -> tuple[bytes, bytes]: ...
    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...

class ProbeOperations(Protocol):
    def import_module(self, name: str, package: str | None = None) -> Any: ...
    def open(self, path: str, flags: int, mode: int = 0o777) -> int: ...
    def read(self, fd: int, size: int) -> bytes: ...
    def write(self, fd: int, data: bytes) -> int: ...
    def fstat(self, fd: int) -> Any: ...
    def lstat(self, path: str) -> Any: ...
    def close(self, fd: int) -> None: ...
    def unlink(self, path: str) -> None: ...
    def fsync(self, fd: int) -> None: ...
    def listdir(self, path: str) -> list[str]: ...
    def scandir(self, path: str) -> Any: ...
    def socket(self, family: int, type: int, proto: int = 0) -> ProbeSocket: ...
    def socketpair(
        self, family: int, type: int, proto: int = 0
    ) -> tuple[ProbeSocket, ProbeSocket]: ...
    def getaddrinfo(
        self, host: str, port: int, family: int, type: int
    ) -> list[Any]: ...
    def popen(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        environment: Mapping[str, str],
        stdin: str,
        stdout: str,
        stderr: str,
        pass_fds: tuple[int, ...],
        close_fds: bool,
        start_new_session: bool,
    ) -> ProbeChild: ...
    def killpg(self, pgid: int, signal_number: int) -> None: ...
```

Add import-safe fail-first declarations for:

- `_evaluate_probe_assertion(assertion_id: str, context: Mapping[str, Any], *,
  operations: ProbeOperations) -> dict[str, Any]`, the sole non-browser assertion
  dispatcher;
- `_evaluate_browser_probe(context: Mapping[str, Any], *,
  playwright_factory: Callable[[], Any], operations: ProbeOperations) ->
  dict[str, Any]`,
  the sole browser dispatcher;
- the existing `_run_capability_probe()`, which keeps its fixed no-argument
  bootstrap and, once implemented in Task 2, must call the two dispatchers with
  a concrete primitive adapter.

In Task 1 the two new dispatcher declarations immediately raise the existing
controlled `ThemeHandoffNotImplemented("TEST-021", ...)`. They perform no I/O
and do not add a public or private CLI token.

Task 1 adds the complete tests now but does not claim the current missing
runner consumes missing seams. The test harness has three explicit arms:

1. Current stub: exact signatures are present; calling either seam or the
   runner yields only the controlled TEST-021 missing behavior.
2. Synthetic mutant modules: implemented pacifier/constant runners are loaded,
   their dispatcher globals are replaced with distinct sentinel callables,
   and their stdout/status must reflect those sentinel results. Missing seams,
   correct-but-unused seams, and constant output are rejected during Task 1.
3. Task 2 implementation: when the production runner no longer raises the
   missing behavior, the same recorder and sentinel matrices become mandatory
   and must pass before TEST-021 can pass.

The future production bootstrap supplies a concrete primitive adapter. Direct
tests supply Protocol-conforming recorders and verify exact calls/results. The
dispatcher has one closed recipe per assertion ID:

- identity/import/read positives verify exact launcher/prefix/module origins
  and successful bounded opens/reads;
- private and candidate write positives require absent-leaf create, exact
  payload write, fsync, close, nofollow reopen/read equality, CAS unlink,
  parent fsync, and verified absence;
- TCP positives require listener bind/listen, client connect, accept, nonempty
  payload send/receive equality, requested address family, and closure;
- UDP positive requires IPv4 bind followed by a bounded empty receive ending
  in the expected timeout;
- socketpair requires a returned pair, data transfer equality, and closure;
- child positives require exact executable/argv, return `0`, null signal, and
  bounded exact output where specified;
- every denial requires the exact attempted dependency call and an allowed
  exception class/code;
- unexpectedly admitted negative writes require the existing no-write/CAS
  cleanup recipe and remain failed;
- browser requires every fact in REQ-SE-003.

Table-driven direct tests enumerate all 63 positive and 131 negative composite
rows. A dependency recorder rejects any missing, extra, reordered, or wrong
call. Separate runner mutations replace one seam result at a time with a
distinct failed sentinel and require the canonical stdout row and aggregate
status to change accordingly. An echo-only runner, a correct-but-unused seam,
or a seam that reports success without its dependency trace therefore fails.

### 3. Exact marker-plus-PGID observer

Replace the test sampler with the parent plan's exact argv:

```text
/bin/ps eww -axo pid=,uid=,pgid=,stat=,xstat=,command=
```

Each sample is a distinct directly owned observer with stdin `devnull`, stdout
limit `4194304`, stderr limit `65536`, execution timeout `2`, direct-child wait
timeout `0.5`, a fresh observer PGID, empty pass-FDs, nonblocking bounded
stdout/stderr drain, and environment exactly
`PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `LANG=C`, `LC_ALL=C`. Parse `pid`, `uid`,
`pgid`, `stat`, `xstat`, and the remaining command field. The observer's own PID
and fresh PGID MUST be present in raw output; its observer PGID MUST contain
exactly that one row. Any second row in the observer PGID invalidates the
sample. The owned observer row is then excluded from the runner family before
classification. For the current UID, classify a remaining row as family-owned
when either:

- `pgid == original_pgid`; or
- its command field contains the exact literal-space-bounded
  `QUANT_RADAR_UX1B_PROCESS_TOKEN=<raw-token>` marker.

Raw command bytes and the raw token stay in test-private memory and MUST NOT
enter the candidate report. Store only normalized private test observations.
Final closure requires zero rows in the union, including detached marker-only
rows whose PGID differs from the original group.

The controller registers the owned runner PID with
`EVFILT_PROC/NOTE_EXIT` immediately after spawn. The registration result is one
closed arm:

- success: exactly one matching `NOTE_EXIT` MUST be received and consumed
  before `pre_reap`; a missing, mismatched, or second event fails;
- `ESRCH`: an immediate valid sample MUST contain that same unreaped owned PID
  as a zombie; PID reuse is impossible while it remains the owned unreaped
  child. This arm consumes no event.

No other registration result is accepted. The controller takes the first
sample immediately after registration. It then uses the same nonblocking
selector turn as stdout/stderr and starts another observer after every
at-most-50-ms monotonic wait while the runner is live. After the accepted exit
arm, it starts the exact 25-second settlement bound, samples immediately, and
samples after each at-most-50-ms wait.

The first decisive `pre_reap` sample MUST contain exactly the owned zombie
leader and no other filtered PGID/marker row, with both runner stdout/stderr
at EOF without error and no latched overflow. The leader `xstat` MUST match
`[0-9a-f]+` and decode as base 16. Only then may one bounded `waitpid` reap the
exact owned PID. The wait status MUST equal decoded `xstat`; exactly one of
`WIFEXITED` or `WIFSIGNALED` MUST hold and must project to the observed return
code or signal. A fresh `post_reap` sample must then contain an empty
marker-plus-PGID union. Early reap, sampling only after reap, or an empty final
union without the complete `pre_reap` chain fails. Sampling stops at the
applicable deadline.

Observer timeout, output overflow, nonempty stderr, parse error, missing own
row, wait/reap mismatch, or missing EOF invalidates the sample. Its disjoint
cleanup may issue exactly one `killpg(observer_pid, SIGKILL)` to the observer's
fresh PGID, followed by the exact bounded wait/pipe closure rules in the parent
plan. It never targets the runner PGID, marker PID, or detached marker PGID and
never converts a failed sample into evidence.

### 4. Browser seam and integration evidence

Directly call the browser operation seam with a recording Playwright object
graph. The recorder requires, in order:

- `chromium.executable_path` equals the authenticated API path;
- `chromium.launch(headless=True)` omitted `executable_path`;
- returned browser version equals the frozen expected version;
- one page was created and page, context, and browser were closed;
- the authenticated Node `--version` child completed successfully;
- page, context, and browser close each complete exactly once.

Then the real Seatbelt integration requires outer samples to observe the
authenticated default headless-shell leaf and a renderer, and requires the
final marker-plus-PGID union to be empty. A runner-dependency mutation replaces
the browser seam result with a distinct failure and requires stdout/browser and
aggregate status to reflect that failure.

Calling Chromium directly, reporting fields without API calls, skipping page
creation, or omitting any close operation MUST fail.

## Acceptance Criteria

### AC-SE-001 — Operation pacifier rejection

Given a mutant dispatcher that performs only bind/connect/open/remove attempts
or returns expected fields without completing payload, timeout, read-back,
fsync, or cleanup semantics, when the direct dependency-recorder matrix and
runner-consumption mutation run, then TEST-021 rejects it.

### AC-SE-002 — Browser pacifier rejection

Given a mutant browser dispatcher that directly launches the authenticated
headless shell/renderer or returns a complete successful `BrowserProbe`, when
the Playwright recorder and runner-consumption mutation run, then TEST-021
rejects it unless every API/path/version/page/close interaction exists.

### AC-SE-003 — Detached marker descendant rejection

Given a child that forks, calls `setsid()`, closes inherited streams, retains
the raw process token, and outlives the leader, when the original PGID becomes
empty, then TEST-021 still observes the marker-only row and rejects quiescence.
The fixture exits naturally within a bounded cleanup window.

### AC-SE-004 — Audit forgery and seam-bypass rejection

Given echo-only, invalid-FD-frame, replay, broken-HMAC, correct-but-unused seam,
constant-result dispatcher, or runner-result replacement mutants, when the
audit, direct operation, and dependency-consumption tests run, then every
mutant is rejected before its reported outcomes can count.

### AC-SE-005 — Known-good real probe acceptance

Given Task 2's future compliant probe implementation, when all six profiles run
under real Darwin Seatbelt, then exactly 194 result recipes, browser semantics,
and the marker-plus-PGID closure pass without optional skips.

### AC-SE-006 — Task 1 fail-first preservation

Given the current Task 1 production stub, when the complete test module runs,
then the result is exactly 29 controlled `ThemeHandoffNotImplemented` failures,
zero unexpected failures, and no production/workspace mutation.

## Implementation Checklist

- [ ] `IMPL-SE-001` Add the three closed Protocols and two exact import-safe
  fail-first dispatcher seams to the production stub. Links: REQ-SE-001,
  REQ-SE-003, CFR-SE-003.
- [ ] `IMPL-SE-002` Add table-driven dependency recorders and exact per-ID
  recipes covering all 194 composite rows. Links: REQ-SE-001, CFR-SE-001.
- [ ] `IMPL-SE-003` Add the Playwright object-graph recorder and browser
  dispatcher/runner-consumption mutations. Link: REQ-SE-003.
- [ ] `IMPL-SE-004` Replace outer sampling and closure checks with the exact
  same-UID marker-plus-PGID union. Link: REQ-SE-002.
- [ ] `IMPL-SE-005` Add operation-pacifier, browser-pacifier, seam-bypass,
  constant-result, and detached-marker mutants. Links: AC-SE-001 through
  AC-SE-004.
- [ ] `IMPL-SE-006` Prove production changes are declarations only and retain
  production argv/environment/stdout/`passFds:[]`. Links: CFR-SE-002,
  CFR-SE-003.
- [ ] `IMPL-SE-007` Run the full verification and independent review gates.
  Links: AC-SE-005, AC-SE-006.

## Verification Commands and Expected Results

1. Compile and compatibility:

   ```text
   .venv/bin/python -m py_compile scripts/ui_ux_theme_handoff.py
   .venv/bin/python -m py_compile scripts/test_ui_ux_theme_handoff.py
   .venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py
   .venv/bin/python -m tabnanny scripts/test_ui_ux_theme_handoff.py
   /opt/homebrew/bin/python3.12 -c "import ast,pathlib; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8'), feature_version=(3,10)) for path in ('scripts/ui_ux_theme_handoff.py','scripts/test_ui_ux_theme_handoff.py')]"
   ```

   Expected: all exit `0`.

2. Fail-first suite:

   ```text
   .venv/bin/python scripts/test_ui_ux_theme_handoff.py
   ```

   Expected: `0/29 passed; 29 controlled missing-behavior failures; 0
   unexpected failures`.

3. Direct semantic and real Darwin mutants:

   - Echo-only mutant rejected.
   - Invalid anonymous-pipe frame mutant rejected.
   - Every non-browser dispatcher recipe has an exact dependency trace and
     return/exception mutation coverage.
   - Operation-pacifier and constant-result dispatcher mutants rejected.
   - Browser-pacifier and correct-but-unused browser seam mutants rejected.
   - Runner-result replacement mutant rejected.
   - Detached marker-only descendant rejected and naturally quiesces within
     the fixture cleanup deadline.

4. Frozen/scope checks:

   - Parent plan and ledger hashes and sizes remain exact.
   - Production diff contains only the three Protocols, their typing import,
     and two named fail-first declarations; it remains import-safe/no-I/O.
   - No changed runtime, UI, Makefile, dependency, recovery, or lifecycle
     evidence file is attributable to this remediation.

5. Review:

   - Independent reviewer checks every issue found before severity filtering.
   - Zero blocker/high/medium findings.
   - Re-run all relevant gates after any review fix.

## Risk and Rollback

| Risk | Mitigation | Blocking signal |
| --- | --- | --- |
| Recorder overfits call spelling | Test success, denial, mismatch, cleanup, and ordering mutations for every recipe | A pacifier or wrong-result mutant passes |
| Runner bypasses a correct seam | Replace each seam result with a distinct sentinel and require exact stdout/status propagation | Output stays constant |
| Audit stream exposes secrets | HMAC challenge and raw token remain private; report serialization scans | Challenge/token appears in report bytes |
| Observer misses detached child | Exact `ps eww` token marker plus PGID union | Detached mutant passes |
| Test leaves a process/file | Natural bounded fixture exit and post-test absence checks | Any surviving PID/path |
| Scope drifts into Task 2 | Production AST/diff permits only three Protocols, one typing import, and two `_missing` declarations | Any new behavior or I/O appears |

Rollback restores the authenticated production preimage and removes only the
new test changes from `scripts/test_ui_ux_theme_handoff.py`. The parent plan,
ledger, recovery authority, and lifecycle evidence are never rollback targets.

## Traceability Matrix

| Requirement | Acceptance criteria | Implementation | Test target |
| --- | --- | --- | --- |
| REQ-SE-001 | AC-SE-001, AC-SE-004, AC-SE-005 | IMPL-SE-001, IMPL-SE-002, IMPL-SE-005 | TEST-021 |
| CFR-SE-001 | AC-SE-004 | IMPL-SE-001, IMPL-SE-005 | TEST-021 |
| REQ-SE-002 | AC-SE-003, AC-SE-005 | IMPL-SE-004, IMPL-SE-005 | TEST-021 |
| REQ-SE-003 | AC-SE-002, AC-SE-005 | IMPL-SE-003, IMPL-SE-005 | TEST-021 |
| CFR-SE-002 | AC-SE-004, AC-SE-006 | IMPL-SE-001, IMPL-SE-006 | TEST-021 |
| CFR-SE-003 | AC-SE-003, AC-SE-006 | IMPL-SE-005, IMPL-SE-006, IMPL-SE-007 | TEST-021 |

Forward and backward traceability are complete within this supplement. The
canonical parent ledger remains immutable because no parent requirement or
accepted implementation mapping changes.

## Review Gate and Next Handoff

Implementation may begin only after an independent review confirms:

- the plan rejects semantic pacifiers rather than merely adding more pre-call
  events;
- detached token descendants cannot disappear by changing PGID;
- browser evidence proves API semantics, not only process presence;
- the chosen three-layer oracle rejects the named mutation model without
  claiming an impossible same-interpreter security boundary;
- the affected-file and verification scopes are complete.

After a passing review, hand off to Builder/Radar for implementation. After
implementation, compare the actual change to this plan, fix blocking review
findings, rerun every gate, and only then resume parent Task 2.

## Change History

| Version | Date | Change |
| --- | --- | --- |
| v0.3 | 2026-07-21 | Closed the primitive dependency Protocol, separated current-stub and synthetic/future runner mutation arms, and completed NOTE_EXIT/ESRCH/pre-reap/xstat/wait/post-reap observer ordering. |
| v0.2 | 2026-07-21 | Rejected same-process result wrappers; selected injected operation seams plus runner-consumption mutations and specified the exact observer lifecycle. |
| v0.1 | 2026-07-21 | Initial focused remediation for the third-review semantic evidence and detached process-family blockers. |
