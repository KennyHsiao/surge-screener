# UX-1B TEST-021 Semantic Evidence Matrix — Fresh Replacement

## Document control

| Field | Value |
| --- | --- |
| Version | v0.3 |
| Status | Review candidate; no implementation authority |
| Date | 2026-07-21 |
| Authoring methods | Matrix exhaustive enumeration + Scribe test specification |
| Parent plan | `docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md` |
| Parent SHA-256 | `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581` |
| Parent ledger SHA-256 | `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8` |
| Matrix source | `scripts/test_ui_ux_theme_handoff.py` |
| Matrix-source SHA-256 | `e4d04d7761483ff1989c39cd7d051e2e95ea0dcd63014886f1642c26de3d3fee` |
| Rejected predecessor | `2026-07-21-quant-radar-ui-ux-ux1b-task1-semantic-evidence-remediation.md` v0.3; immutable and not an authority |

## Purpose and decision gate

This artifact resolves the repeated TEST-021 planning blocker before a new
Task 1 implementation plan is written. It assigns every one of the closed 194
capability/outcome composites to one semantic recipe, one result owner, an
independent integration observation, and a named mutant that must be killed.

A reviewer PASS on these exact bytes permits authoring a new replacement plan.
It does not permit editing production code or implementing Task 1. Any
unmapped composite, overlapping result owner, high-level dependency that can
return a finished `ProbeOutcome`, unbounded child execution, or optional
integration skip is blocking.

## Coverage accounting

### Axes and combination method

| Axis | Closed values |
| --- | --- |
| Capability | Six exact `CAPABILITIES` keys from the matrix source |
| Polarity | `positive` or `negative` |
| Assertion | Ordered common IDs plus that capability's ordered additions |
| Result owner | `START`, `INPROC`, `CHILD`, `TOKEN`, or `BROWSER-FINAL` |
| Proof layer | Direct primitive trace, bounded child receipt, real Seatbelt integration, consumer propagation, mutant rejection |
| Mutant | Cross-cutting `M01` through `M15` plus one recipe-qualified `Q-*` kill per recipe |

This is not a Cartesian product of six capabilities and all 44 unique
assertions. The parent contract defines a closed presence relation. Matrix
reduction is forbidden because TEST-021 expressly requires every composite.

| Metric | Value |
| --- | ---: |
| Original required composites | 194 |
| Positive composites | 63 |
| Negative composites | 131 |
| Optimized composites | 194 |
| Reduction | 0% |
| Closed-set coverage guarantee | 100% |
| Unique semantic recipes | 44 |
| Optional or skipped rows | 0 |

The final table is mechanically derived from `CAPABILITIES`,
`COMMON_POSITIVE`, `COMMON_NEGATIVE`, `PROBE_POSITIVE_ADDITIONS`, and
`PROBE_NEGATIVE_ADDITIONS` at the source hash above. Review or implementation
must fail if regenerating from those constants changes any row, order, count,
polarity, or recipe mapping.

## Trust boundary and proof rule

TEST-021 proves correctness of authenticated, reviewed source; it does not
claim that an arbitrary hostile Python program can be cryptographically
isolated from other code in its own interpreter. Same-process HMAC or audit
frames are attempt and identity evidence only. They are never the sole
authority for a successful or denied semantic result.

A composite passes only when all layers assigned by its recipe agree:

1. A direct test drives a named dispatcher through low-level recording
   dependencies and verifies required calls, returns, exceptions, payloads,
   ordering, and cleanup.
2. A consumer mutation replaces that dispatcher's raw result with a distinct
   sentinel and proves the final canonical assertion document and aggregate
   status change. Correct-but-unused seams and constant output fail.
3. A real Darwin Seatbelt probe exercises the exact capability. Its bounded
   process result, authenticated attempt stream, and external process-family
   observation agree with the direct semantic recipe.
4. The recipe's primary mutant and all applicable cross-cutting mutants fail.

A dispatcher may construct a `ProbeOutcome`. A dependency adapter, socket,
child executor, Playwright recorder, or process observer may not return one.
They return raw facts only.

The final outcome projection remains the frozen parent contract. A passed
positive INPROC/START/TOKEN/BROWSER row is
`succeeded/succeeded`, has null error fields and `null/null`
return/signal. A passed positive CHILD row is `succeeded/succeeded`, has null
error fields and `0/null`. A passed negative non-child row is `denied/denied`,
has the recipe's allowed OS error and `null/null`. A passed negative CHILD row
is `denied/denied`, has the spawn denial's allowed OS error and the frozen
child-form `0/null` projection. That last `0` is a report-form discriminator,
not a fabricated spawned-child exit; the raw `spawn_denied` arm still has no
PID or process return code. Any internal inconsistency projects to
`actualOutcome:"failed"`, `passed:false`, and the exact parent `ProbeFailure`
arm instead of being normalized into a pass.

The parent's earlier generic denial sentence says `null/null`, while its later
child-form paragraph and the frozen TEST-021/TEST-029 oracle specialize all
eight child-form IDs to `0/null`; the matrix applies that later, narrower rule.
This precedence is explicit so implementation cannot choose whichever arm is
convenient. Changing child denials to `null/null` would require a reviewed
parent-contract replacement, not a Task 1 edit.

## Exact ownership and dependency contracts

### INPROC primitive boundary

`InProcessPrimitives` is the only injected boundary for filesystem, import,
and socket recipes. Its closed members mirror primitives and may not expose an
assertion ID, expected outcome, pass/fail value, `ProbeOutcome`, `BrowserProbe`,
or generic command runner:

```python
class ProbeSocket(Protocol):
    def bind(self, address: Any, /) -> None: ...
    def listen(self, backlog: int = 1, /) -> None: ...
    def getsockname(self) -> Any: ...
    def accept(self) -> tuple["ProbeSocket", Any]: ...
    def connect(self, address: Any, /) -> None: ...
    def sendall(self, data: bytes, flags: int = 0, /) -> None: ...
    def sendto(self, data: bytes, address: Any, /) -> int: ...
    def recv(self, bufsize: int, flags: int = 0, /) -> bytes: ...
    def recvfrom(self, bufsize: int, flags: int = 0, /) -> tuple[bytes, Any]: ...
    def settimeout(self, value: float | None, /) -> None: ...
    def close(self) -> None: ...

class InProcessPrimitives(Protocol):
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
    def socketpair(self) -> tuple[ProbeSocket, ProbeSocket]: ...
    def getaddrinfo(
        self, host: str, port: int, family: int, type: int
    ) -> list[Any]: ...
```

The concrete `socketpair` adapter must invoke `socket.socketpair()` with zero
positional and zero keyword arguments. The recorder stores the raw empty
argument tuple. Passing `AF_UNIX`, `SOCK_STREAM`, `proto=0`, or any other
explicit default fails `P12/M09`.

`_evaluate_inprocess_probe_assertion(assertion_id, context, *,
primitives)` accepts only the INPROC IDs named below. Unknown, START, CHILD,
TOKEN, or BROWSER IDs fail before any primitive call. Exceptions remain raw
until the dispatcher classifies them.

### CHILD bounded execution boundary

The eight child-form IDs are owned only by
`_evaluate_child_probe_assertion(assertion_id, context, *, executor)`.
`executor` accepts a closed `ProbeChildPlan` and returns raw
`ProbeChildExecution`; neither type contains `expectedOutcome`, `passed`, or a
`ProbeOutcome`.

Every plan has exact fields:

```text
{id, argv, cwd, environment, stdin:"devnull",
 timeoutSeconds:10, stdoutLimitBytes:65536, stderrLimitBytes:65536,
 passFds:[], processGroup:"fresh_child"}
```

The executable and argv are recipe-owned. Environment and cwd equal the
authenticated probe context. No raw process token is added or removed by the
child dispatcher. The executor uses actual `subprocess.Popen` with
`stdin=DEVNULL`, `stdout=PIPE`, `stderr=PIPE`, `close_fds=True`,
`pass_fds=()`, and `start_new_session=True`. The resulting PID is the fresh
child PGID; the unchanged raw token makes this detached group part of the
outer marker-plus-PGID union. The executor uses the parent plan's nonblocking
bounded selector/supervisor with this disjoint child PGID, so timeout cleanup
can never signal the enclosing probe PGID. It may return only one closed raw
arm:

- `spawn_denied`: no PID, empty streams, one raw allowed OS exception;
- `completed`: owned PID/fresh PGID, exact argv, nonnegative return code or positive
  signal projection, bounded streams, `timedOut:false`, no overflow, closed
  pipes, and an empty post-reap token/child-PGID union;
- `timed_out` or `output_overflow`: owned PID plus the exact bounded
  TERM/KILL/closure receipt;
- `spawn_failed`: no PID, empty streams, a non-policy error.

A negative exec that unexpectedly spawns is supervised to closure and becomes
`unexpected_success`; it never becomes a denial. Timeout or stream overflow
becomes a failed outcome. Direct executor tests cover spawn, denial, partial
streams, timeout, overflow, signal, TERM, KILL, EOF, wait/reap matching, and
process-family closure. TERM and KILL target only the authenticated fresh child
PGID. Real integration additionally binds the attempt to the audit stream and
the concrete executor's owned PID/PGID/wait receipt. The outer observer must
observe the enclosing probe family and prove final marker-plus-PGID closure;
it need not race to sample a short-lived P07/P17 child before that child exits.
If such a child is sampled, its row must classify through the token union, but
absence of that optional intermediate row cannot manufacture or invalidate the
executor's result.

Acceptance tests call the production concrete executor. They replace only its
low-level `subprocess.Popen`, selector, monotonic clock, `waitpid`, and
`killpg` dependencies with call-recording primitives, then require the exact
spawn/supervision trace above. Supplying a fake `ProbeChildExecution` is allowed
only in the separate consumer-sentinel test and can prove propagation, never
executor correctness. A concrete executor that returns a plausible raw arm
without the recorded low-level trace fails M07.

The fixed child argvs are:

| Recipe | Exact argv |
| --- | --- |
| P07 | `[VENV_LAUNCHER,"-B","-c","pass"]` |
| P17 | `[PLAYWRIGHT_NODE,"--version"]` |
| N01 | `["/usr/bin/true"]` |
| N02 | `["/usr/bin/sandbox-exec","-p","(version 1)\n(allow default)","/usr/bin/true"]` |
| N03 | `["/bin/ps","-p",str(PROBE_PID)]` |
| N24 | `[PLAYWRIGHT_NODE,"--version"]` |
| N25 | `[HEADLESS_SHELL,"--version"]` |
| N26 | `[CHROMIUM_APP,"--version"]` |

`VENV_LAUNCHER`, `PLAYWRIGHT_NODE`, `HEADLESS_SHELL`, and `CHROMIUM_APP` are
the authenticated exact paths/hashes from the runtime receipt. P07 requires
empty stdout/stderr. P17 requires return `0`, null signal, empty stderr, and
stdout byte-equality with a separately authenticated preflight
`PLAYWRIGHT_NODE --version` receipt. Every child denial accepts only
`PermissionError|OSError` with `EPERM|EACCES` from the spawn operation.

### START and TOKEN ownership

START owns only P01 and P02. The outer coordinator supplies an authenticated
launch header containing the exact `sys.executable`, `sys.prefix`, argv[0],
runtime bindings, spawned PID, and initial PGID. The bootstrap compares
`sys.executable` and `sys.prefix` to those bound values. A same-process audit
header corroborates identity but cannot replace the coordinator-owned spawn
and executable hash receipts.

TOKEN owns only P08. It requires initial environment value
`QUANT_RADAR_UX1B_PROCESS_TOKEN` to match `^ux1b_[0-9a-f]{64}$`, its SHA-256
to equal `TokenProcessFamilyPlan.tokenSha256`, its launch value to equal the
coordinator-held raw token, and the raw token to be absent from every public
receipt. Final family closure is owned by the external observer, not P08.

### BROWSER API and final ownership

`_exercise_browser_api(context, *, playwright_factory)` returns raw
`BrowserApiEvidence` only:

```text
{apiExecutablePath, observedVersion, launched, pageCreated,
 pageClosed, contextClosed, browserClosed}
```

It must call, in order: create/start the injected Playwright owner; read
`chromium.executable_path`; call `chromium.launch(headless=True)` with no
`executable_path` key and no positional executable; create exactly one blank
page through the returned browser; read `browser.version`; close that page,
its context, the browser, and the Playwright owner exactly once. Cleanup is
attempted in reverse acquisition order on every failure and incomplete cleanup
is a failed raw result.

Browser ownership is one causally ordered two-stage chain. Probe-side
`_build_browser_probe(api, node_execution, runtime)` is a pure consumer and the
only producer of P18 plus the serialized `BrowserProbe`; P17 is not created or
duplicated there. It requires:

- API executable path equals authenticated `RuntimeReceipt.chromium.executablePath`;
- observed version equals the authenticated Chromium version;
- `chromium.launch` used the default path contract above;
- all three API lifecycle booleans are true;
- P17's completed Node execution is successful and its executable SHA matches.

It projects the exact parent `BrowserProbe` keys
`{apiExecutablePath,defaultExecutablePath,expectedVersion,observedVersion,
defaultExecutableMatchesCandidateLeaf,defaultExecutableSha256,nodeSha256,
launched,pageCreated,closed,childrenQuiescent}`. `defaultExecutablePath` and
its hash come from the authenticated runtime, not from the API recorder.
`nodeSha256` comes from the P17 plan/preflight binding. Probe-side
`childrenQuiescent:true` means the P17 fresh child group is quiescent and all
Playwright close calls returned; it is a claim awaiting outer corroboration,
not final family authority. The P18 `ProbeOutcome` is in-process and therefore
has `returnCode:null` and `signal:null`.

Only after the probe exits, outer
`_validate_serialized_browser_probe(browser, p18, runtime, execution_plan,
family_receipt)` may accept that already serialized claim. It returns no
`ProbeOutcome` or `BrowserProbe` and may not modify or re-encode the probe
document. Acceptance requires exact byte equality between stdout and parsed
receipt fields; the authenticated browser capability/profile with exactly the
Playwright Node and default headless-shell exec leaves; successful P17; the
directly proved default Playwright launch/page/version/close chain; a valid
outer `/bin/ps` process-family receipt; and an empty final marker-plus-PGID
union. Together these prove execution under the sole allowed browser leaf and
final quiescence without claiming descendant enumeration.

No headless-shell or renderer PID witness is mandatory or produced. A
short-lived renderer may start and exit between two valid at-most-50-ms
samples; treating that race as failure would exceed the parent contract. Thus
the producer cannot know future outer closure, while the outer validator cannot
manufacture a better browser result after exit. `BROWSER-FINAL` names this
single producer-then-validator acceptance chain, not two competing outcome
owners.

The browser acceptance test likewise calls the production browser API
function with a recording Playwright object graph. A prebuilt
`BrowserApiEvidence` may be injected only into builder consumer-sentinel and
schema-fault tests; it cannot satisfy the API-interaction proof by itself.
Separate outer-validator tests mutate stdout equality, exact browser
capability/profile/exec-leaf authority, receipt closure, and every BrowserProbe
leaf.

## Mandatory external observer

Each sample executes exactly:

```text
/bin/ps eww -axo pid=,uid=,pgid=,stat=,xstat=,command=
```

It is a distinct directly owned child with stdin `devnull`, stdout limit
`4194304`, stderr limit `65536`, execution timeout `2`, direct-child wait
timeout `0.5`, fresh observer PGID, empty pass-FDs, nonblocking bounded drain,
and environment exactly
`PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `LANG=C`, `LC_ALL=C`.

A sample is usable only if return code is exactly `0`, signal is null,
`timedOut:false`, overflow is null, stderr is empty, stdout is within its cap,
and every row parses into exactly `pid,uid,pgid,stat,xstat,command`. PIDs must
be positive and unique; normalized rows are sorted by PID; `uid` is
nonnegative; `pgid` is positive; `stat` matches exactly
`[IRSTUZ][+<>AELNSsVWX]{0,15}`; `xstat` matches `[0-9a-f]+` and decodes in base
16 to a nonnegative exact integer; `command` is nonempty. The observer's own
positive PID/PGID row must be present, and that fresh PGID must contain exactly
that row. The observer row is removed only after those checks.

The public projection is exactly
`{pid,uid,processGroupId,state,waitStatus,markerMatch}`: `processGroupId` is
the positive parsed `pgid`, `state` is the validated `stat`, `waitStatus` is
the decoded `xstat`, and `markerMatch` is the exact marker-regex result. Raw
`command`, raw `stat`, and raw `xstat` never enter the public row.

For current-UID remaining rows, family membership is the union of original
PGID equality and a literal-space-bounded exact
`QUANT_RADAR_UX1B_PROCESS_TOKEN=<raw-token>` marker. Raw command bytes and the
raw token never enter a public receipt. The NOTE_EXIT/ESRCH registration,
first immediate sample, at-most-50-ms sampling cadence, decisive zombie-only
`pre_reap` sample, stdout/stderr EOF, base-16 xstat/wait-status equality,
single owned waitpid, and empty `post_reap` union are mandatory exactly as in
the parent plan. A detached marker-bearing `setsid()` descendant remains in
the union. Observer failure emits no sample and cannot become evidence.

## Recipe catalog

Legend:

- Owner `S` = START, `I` = INPROC, `C` = CHILD, `T` = TOKEN,
  `B` = BROWSER-FINAL.
- Layers `D` = direct primitive/API recorder, `X` = bounded executor,
  `R` = real Darwin Seatbelt, `A` = authenticated attempt corroboration,
  `O` = external observer, `U` = consumer/serialization mutation.
- Every recipe also requires exact `ProbeOutcome` schema/form and its listed
  recipe-qualified kill case. M01-M15 remain separate cross-cutting mutants.

### Positive recipes

| ID | Assertion | Owner | Required semantic result | Layers | Qualified kill |
| --- | --- | --- | --- | --- | --- |
| P01 | venv-launcher-identity | S | `sys.executable` and argv[0] equal the authenticated launcher spelling and executable receipt | D,R,A,U | Q-P01 |
| P02 | venv-prefix-identity | S | `sys.prefix` equals the authenticated live venv root | D,R,A,U | Q-P02 |
| P03 | venv-package-imports | I | import FastAPI, Streamlit, Playwright; each origin is under authenticated live venv and hash/closure checks pass | D,R,A,U | Q-P03 |
| P04 | candidate-source-read | I | exact candidate Makefile open `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, regular identity, bounded full read/hash, close | D,R,A,U | Q-P04 |
| P05 | private-environment-read-write | I | in each of five private roots: absent canary create, exact payload write, fsync, close, nofollow reopen/read equality, close, CAS unlink, parent fsync, verified absence | D,R,A,U | Q-P05 |
| P06 | base-system-runtime-read | I | authenticated base runtime and at least one bound system-runtime leaf each complete bounded identity/read/hash/close | D,R,A,U | Q-P06 |
| P07 | resolved-python-child-exec | C | exact P07 plan completes return 0/null, empty streams, closed pipes, quiescent fresh child PGID/token union | X,R,A,O,U | Q-P07 |
| P08 | process-family-token-binding | T | initial raw-token grammar/value/hash match and zero public serialization; observer later closes the marker/PGID union | D,R,O,U | Q-P08 |
| P09 | tcp-ipv4-roundtrip | I | AF_INET listener bind 127.0.0.1:0/listen, AF_INET client connect, accept, nonempty marker transfer/equality, close all endpoints | D,R,A,U | Q-P09 |
| P10 | tcp-ipv6-roundtrip | I | P09 with AF_INET6 and ::1; no skip | D,R,A,U | Q-P10 |
| P11 | udp-ipv4-bind-recv-timeout | I | AF_INET/SOCK_DGRAM bind 127.0.0.1:0, bounded timeout set, empty recv ends in expected socket timeout, close | D,R,A,U | Q-P11 |
| P12 | unix-socketpair-default | I | zero-argument `socketpair()`, nonempty marker transfer/equality, both endpoints closed | D,R,A,U | Q-P12 |
| P13 | candidate-run-status-write-read-remove | I | capability-namespaced absent leaf under exact run-status target performs full P05 single-root recipe | D,R,A,U | Q-P13 |
| P14 | candidate-ux1b-write-read-remove | I | capability-namespaced absent leaf under exact UX1B target performs full P05 single-root recipe | D,R,A,U | Q-P14 |
| P15 | candidate-ui-write-read-remove | I | capability-namespaced absent leaf under exact candidate UI target performs full P05 single-root recipe | D,R,A,U | Q-P15 |
| P16 | unix-path-bind-listen-close | I | AF_UNIX/SOCK_STREAM absent private-TMP path bind/listen(1)/close, same-inode unlink, parent fsync, verified absence | D,R,A,U | Q-P16 |
| P17 | playwright-node-exec | C | exact P17 plan completes 0/null; stderr empty; stdout equals authenticated preflight bytes; executable hash exact | X,R,A,O,U | Q-P17 |
| P18 | chromium-default-launch-page-close | B | probe builds exact API/P17 BrowserProbe and P18; outer validator accepts unchanged bytes only under exact sole-leaf browser profile with valid family receipt and empty final union | D,X,R,O,U | Q-P18 |

### Negative recipes

For N04-N13 and N15-N23, an accepted denial is only the raw attempted
primitive raising `PermissionError|OSError` with `EPERM|EACCES`. N14 alone
accepts `gaierror` with `EAI_AGAIN|EAI_FAIL|EAI_NONAME` and no address result.
Child denial rules are defined above. Merely constructing those fields fails
M08.

| ID | Assertion | Owner | Exact attempted operation and result | Layers | Qualified kill |
| --- | --- | --- | --- | --- | --- |
| N01 | unknown-true-exec-denied | C | exact N01 plan; spawn denied; no child | X,R,A,O,U | Q-N01 |
| N02 | nested-sandbox-exec-denied | C | exact N02 plan; spawn denied; no child | X,R,A,O,U | Q-N02 |
| N03 | ps-exec-denied | C | exact N03 plan; spawn denied; no child | X,R,A,O,U | Q-N03 |
| N04 | live-source-read-denied | I | open authenticated live Makefile for bounded read; denial before bytes | D,R,A,U | Q-N04 |
| N05 | outside-allowlist-read-denied | I | open exact coordinator-owned canary for bounded read; denial; canary remains identity/byte exact | D,R,A,U | Q-N05 |
| N06 | real-ssh-list-denied | I | exact `listdir("/Users/ken/.ssh")`; denial; no names emitted | D,R,A,U | Q-N06 |
| N07 | playwright-cache-list-denied | I | exact cache-root listdir; denial; no names emitted | D,R,A,U | Q-N07 |
| N08 | live-source-write-open-denied | I | existing live Makefile open exact `O_WRONLY|O_NOFOLLOW|O_CLOEXEC`; no write-family call | D,R,A,U | Q-N08 |
| N09 | candidate-root-write-denied | I | absent direct-child open exact `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`, mode 0600; no write | D,R,A,U | Q-N09 |
| N10 | live-venv-pyvenv-write-open-denied | I | existing pyvenv.cfg follows N08 | D,R,A,U | Q-N10 |
| N11 | headless-shell-write-open-denied | I | authenticated headless-shell leaf follows N08 | D,R,A,U | Q-N11 |
| N12 | external-tcp-denied | I | AF_INET/SOCK_STREAM connect exactly 203.0.113.1:9; denial; close | D,R,A,U | Q-N12 |
| N13 | external-udp-denied | I | AF_INET/SOCK_DGRAM sendto nonempty marker exactly 1.1.1.1:53; denial; close | D,R,A,U | Q-N13 |
| N14 | dns-resolution-denied | I | getaddrinfo exactly example.com:53 with AF_UNSPEC/SOCK_DGRAM; accepted gaierror; no result | D,R,A,U | Q-N14 |
| N15 | tcp-ipv4-bind-denied | I | AF_INET/SOCK_STREAM bind 127.0.0.1:0; denial; close | D,R,A,U | Q-N15 |
| N16 | tcp-ipv6-bind-denied | I | AF_INET6/SOCK_STREAM bind ::1:0; denial; close | D,R,A,U | Q-N16 |
| N17 | udp-ipv4-bind-denied | I | AF_INET/SOCK_DGRAM bind 127.0.0.1:0; denial; close | D,R,A,U | Q-N17 |
| N18 | udp-ipv6-bind-denied | I | AF_INET6/SOCK_DGRAM bind ::1:0; denial; close | D,R,A,U | Q-N18 |
| N19 | unix-bind-denied | I | AF_UNIX/SOCK_STREAM bind capability-namespaced private-TMP path; denial; close; if admitted, same-inode unlink/parent fsync/verified absence and fail | D,R,A,U | Q-N19 |
| N20 | udp-loopback-outbound-denied | I | AF_INET/SOCK_DGRAM sendto nonempty marker 127.0.0.1:9; denial; close | D,R,A,U | Q-N20 |
| N21 | candidate-run-status-write-denied | I | absent capability-namespaced run-status leaf follows N09 | D,R,A,U | Q-N21 |
| N22 | candidate-ux1b-write-denied | I | absent capability-namespaced UX1B leaf follows N09 | D,R,A,U | Q-N22 |
| N23 | candidate-ui-write-denied | I | absent capability-namespaced candidate-UI leaf follows N09 | D,R,A,U | Q-N23 |
| N24 | playwright-node-exec-denied | C | exact N24 plan; spawn denied; no child | X,R,A,O,U | Q-N24 |
| N25 | headless-shell-exec-denied | C | exact N25 plan; spawn denied; if admitted supervise to closure and fail | X,R,A,O,U | Q-N25 |
| N26 | chromium-app-exec-denied | C | exact N26 plan; spawn denied while P18 default headless launch succeeds | X,R,A,O,U | Q-N26 |

For N08/N10/N11, unexpected admission retains the descriptor, verifies
`fstat` identity against the authenticated target and the coordinator's
separate retained read authority, closes without any write-family syscall, and
returns failed. For N09/N21/N22/N23, unexpected admission closes without
writing, CAS-unlinks only the exact created inode, fsyncs the parent, verifies
absence, and returns failed. Swap, unlink, fsync, or absence-verification
uncertainty never deletes a foreign inode and remains failed.

## Recipe-qualified kill matrix

`test_semantic_recipe_mutant_matrix` executes all 44 rows below. Its failure
message includes the Q ID, the unmutated twin must pass first, and the mutated
twin must fail at the stated oracle. These Q cases are what the recipe tables
and therefore all 194 composites inherit. None is satisfied by a mutant for a
different recipe or owner.

Every `test_semantic_*` name in this artifact is a private helper invoked
exactly once from the existing TEST-021 callable. None is added to `TESTS` or
changes the exact 29-test aggregate/count/order.

| Q ID | Exact mutation or fault | Required kill oracle |
| --- | --- | --- |
| Q-P01 | bootstrap substitutes `/usr/bin/python3` for authenticated `sys.executable` | START launcher equality fails |
| Q-P02 | bootstrap substitutes the live-venv parent for `sys.prefix` | START prefix equality fails |
| Q-P03 | dispatcher skips Playwright import while importing FastAPI/Streamlit | exact three-package import/origin set fails |
| Q-P04 | candidate Makefile open omits `O_NOFOLLOW` | exact P04 open flags fail |
| Q-P05 | dispatcher omits the private-data-root canary cycle | exact five-root ordered trace fails |
| Q-P06 | dispatcher reads base runtime but omits system-runtime leaf | two-class runtime read trace fails |
| Q-P07 | concrete child result returns code 1 for exact P07 argv | P07 must project failed `nonzero_exit` |
| Q-P08 | bootstrap hashes a one-byte-different raw token | TOKEN plan/hash equality fails and no pass row is emitted |
| Q-P09 | accepted TCP endpoint receives bytes different from sent marker | payload equality requires failed `wrong_payload` |
| Q-P10 | dispatcher silently returns success without creating AF_INET6 endpoints | exact IPv6 trace is absent |
| Q-P11 | UDP recv returns one byte but dispatcher treats it as the required timeout | bounded-empty-receive oracle fails |
| Q-P12 | concrete adapter calls `socketpair(AF_UNIX,SOCK_STREAM)` | zero-argument tuple/map oracle fails |
| Q-P13 | cleanup omits run-status parent fsync | full positive-write cleanup trace fails |
| Q-P14 | create targets candidate UI instead of candidate UX1B root | authenticated target-path equality fails |
| Q-P15 | dispatcher writes candidate UI payload but skips nofollow reopen/readback | payload readback trace fails |
| Q-P16 | Unix listener closes but leaves its pathname | same-inode unlink/fsync/absence oracle fails |
| Q-P17 | exact Node child returns stdout differing by one byte from preflight | P17 must project failed `wrong_payload` |
| Q-P18 | browser API omits context close while all other calls succeed | BrowserApiEvidence cleanup and P18 acceptance fail |
| Q-N01 | dispatcher returns EPERM without executing exact `/usr/bin/true` plan | CHILD concrete-spawn trace is absent |
| Q-N02 | nested-sandbox plan omits fixed `-p` profile arguments | exact N02 argv equality fails |
| Q-N03 | ps plan omits `-p PROBE_PID` | exact N03 argv equality fails |
| Q-N04 | read denial targets candidate Makefile instead of live Makefile | authenticated live target equality fails |
| Q-N05 | read denial targets a sibling rather than exact canary | canary path/unchanged identity oracle fails |
| Q-N06 | list denial targets `/Users/ken` instead of `/Users/ken/.ssh` | exact listdir path fails |
| Q-N07 | list denial targets the Playwright cache parent | exact cache-root path fails |
| Q-N08 | existing live Makefile open adds `O_TRUNC` | exact safe existing-leaf flags and zero-write rule fail |
| Q-N09 | absent candidate-root open omits `O_EXCL` | exact absent-leaf flags/mode fail |
| Q-N10 | existing write probe targets live-venv root instead of `pyvenv.cfg` | exact authenticated target fails |
| Q-N11 | existing write probe targets Chromium app instead of headless-shell leaf | exact authenticated target fails |
| Q-N12 | TCP connect targets `203.0.113.2:9` | exact TEST-NET-3 endpoint fails |
| Q-N13 | UDP sendto uses an empty payload | nonempty marker and exact endpoint oracle fails |
| Q-N14 | getaddrinfo resolves `example.org` | exact host/port/family/type tuple fails |
| Q-N15 | bind uses AF_INET6 while reporting IPv4 denial | exact socket family/address trace fails |
| Q-N16 | bind uses AF_INET while reporting IPv6 denial | exact socket family/address trace fails |
| Q-N17 | bind uses AF_INET/SOCK_STREAM while reporting UDPv4 denial | exact socket type trace fails |
| Q-N18 | bind uses AF_INET6/SOCK_STREAM while reporting UDPv6 denial | exact socket type trace fails |
| Q-N19 | dispatcher substitutes file open for AF_UNIX bind | required Unix socket bind exception trace is absent |
| Q-N20 | sendto targets `1.1.1.1:53` instead of loopback | exact loopback endpoint fails |
| Q-N21 | absent write probe targets candidate root instead of run-status root | authenticated target-root equality fails |
| Q-N22 | absent write probe targets candidate UI instead of UX1B root | authenticated target-root equality fails |
| Q-N23 | absent write probe targets candidate UX1B instead of UI root | authenticated target-root equality fails |
| Q-N24 | denied child plan uses headless shell instead of authenticated Node | exact executable/hash/argv equality fails |
| Q-N25 | denied headless-shell plan omits `--version` | exact N25 argv equality fails |
| Q-N26 | dispatcher returns EPERM without attempting authenticated Chromium app | CHILD concrete-spawn trace is absent |

## Deterministic mutant catalog

Each ID below is one exact implemented mutation, not a disjunction or label for
choosing an easy example. The named test invokes the mutant directly and must
fail at the named oracle. The harness first proves the unmutated twin passes;
syntax/import/schema damage before the named oracle does not count as a kill.

| ID | Exact mutation or injected fault | Exact invoking test | Required kill oracle |
| --- | --- | --- | --- |
| M01 | P09 dispatcher returns the canonical successful row without calling `socket` | `test_semantic_mutant_m01_constant_outcome` | INPROC trace is empty instead of the exact P09 trace |
| M02 | P09 performs bind/connect then returns success without accept/send/recv | `test_semantic_mutant_m02_attempt_only` | required accept and payload-equality events are absent |
| M03 | runner receives a failed P09 sentinel but serializes the original successful P09 row | `test_semantic_mutant_m03_unused_result` | canonical stdout must contain the sentinel row and aggregate `passed:false` |
| M04 | P04 opens candidate Makefile with `O_RDONLY` but omits `O_NOFOLLOW|O_CLOEXEC` | `test_semantic_mutant_m04_wrong_flags` | exact open-flag equality fails |
| M05 | P09 receives a wrong marker payload but returns success | `test_semantic_mutant_m05_wrong_payload` | byte-equality oracle requires failed `wrong_payload` |
| M06 | P13 unlinks the correct leaf but omits parent-directory fsync | `test_semantic_mutant_m06_missing_fsync` | exact cleanup trace lacks final parent fsync |
| M07 | P17 child executor uses blocking `communicate()` without selector, timeout, or 65536-byte caps | `test_semantic_mutant_m07_unbounded_child` | bounded executor trace lacks deadline/cap/selector events |
| M08 | N15 returns `PermissionError/EPERM` fields without calling socket bind | `test_semantic_mutant_m08_forged_denial` | denial requires the recorded AF_INET bind exception |
| M09 | P12 calls `socketpair(AF_UNIX, SOCK_STREAM)` | `test_semantic_mutant_m09_explicit_socketpair_defaults` | concrete socketpair argument tuple/map must both be empty |
| M10 | browser API calls `chromium.launch(headless=True, executable_path=API_PATH)` | `test_semantic_mutant_m10_explicit_browser_path` | launch kwargs must be exactly `{headless:True}` |
| M11 | browser builder copies authenticated `nodeSha256` but ignores a failed P17 sentinel | `test_semantic_mutant_m11_ignored_node_result` | P18/BrowserProbe must become failed/not accepted |
| M12 | family filter uses original PGID only while a token-bearing fixture calls `setsid()` | `test_semantic_mutant_m12_pgid_only_filter` | detached marker PID must remain in the filtered union |
| M13 | audit parser accepts one duplicated prior sequence/HMAC frame | `test_semantic_mutant_m13_replayed_audit_frame` | exact next-sequence/previous-digest check rejects replay |
| M14 | observer parser accepts raw row `pgid=0,stat=?` and emits a sample | `test_semantic_mutant_m14_malformed_process_row` | positive-PGID and exact-state grammar both reject the sample |
| M15 | admitted N09 leaf is identity-swapped and cleanup unlinks the foreign replacement | `test_semantic_mutant_m15_foreign_unlink` | CAS identity mismatch permits zero unlink and outcome remains failed |

The canonical mutants do not replace the complete deterministic fault tables:

| Exact test | Required injected cases; every case has an unmutated passing twin and a named trace/schema oracle |
| --- | --- |
| `test_semantic_inprocess_fault_matrix` | for P03/P04/P05/P06/P09/P10/P11/P12/P13/P14/P15/P16 and each N04-N23 recipe: each required primitive individually missing, one adjacent pair reordered, one extra primitive, every exact flag/mode/family/address/path changed, short write/read, wrong/empty payload, admitted denial, wrong exception/code, close failure, unlink failure, fsync failure, identity swap, and absence-check failure where applicable |
| `test_semantic_child_fault_matrix` | each of eight exact argvs changed; spawn denial, spawn failure, nonzero, signal, partial stdout/stderr, timeout, stdout overflow, stderr overflow, wrong PID/PGID, missing EOF, wait mismatch, TERM race, KILL race, surviving token row, and fake raw arm without a concrete Popen trace |
| `test_semantic_browser_fault_matrix` | wrong API path/version; explicit executable; direct process launch; missing/duplicate/reordered page/context/browser/owner close; no page; failed/ignored P17; wrong Node hash/output; wrong capability/profile/exec-leaf set or digest; invalid family receipt; nonquiescent final union; stdout/receipt mismatch; optional skip |
| `test_semantic_observer_fault_matrix` | observer nonzero, signal, timeout, either overflow, nonempty stderr, missing EOF, bad field count/type, duplicate/unsorted PID, zero PGID, invalid state, invalid xstat, missing own row, extra observer-PGID row, marker boundary false positive/negative, NOTE_EXIT count/kind mismatch, bad ESRCH fallback, premature reap, xstat/wait mismatch, and nonempty post-reap union |

Every listed case is a separate table row with a stable case ID in the test
failure message. A loop that silently omits a case, an expected-failure marker,
or a broad `except` that treats any failure as a mutant kill fails the harness.

## Closed 194-composite matrix

Each row inherits the result owner, proof layers, exact operation, and one
recipe-qualified Q kill from its recipe. `position` is one-based within that
capability's positive or negative array. M01-M15 are additional cross-cutting
mutants and are not implicitly inherited by unrelated recipes.

| # | Capability | Polarity | Position | Assertion | Recipe |
| ---: | --- | --- | ---: | --- | --- |
| 001 | candidate-basic-v1 | positive | 1 | venv-launcher-identity | P01 |
| 002 | candidate-basic-v1 | positive | 2 | venv-prefix-identity | P02 |
| 003 | candidate-basic-v1 | positive | 3 | venv-package-imports | P03 |
| 004 | candidate-basic-v1 | positive | 4 | candidate-source-read | P04 |
| 005 | candidate-basic-v1 | positive | 5 | private-environment-read-write | P05 |
| 006 | candidate-basic-v1 | positive | 6 | base-system-runtime-read | P06 |
| 007 | candidate-basic-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 008 | candidate-basic-v1 | positive | 8 | process-family-token-binding | P08 |
| 009 | candidate-basic-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 010 | candidate-basic-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 011 | candidate-basic-v1 | negative | 3 | ps-exec-denied | N03 |
| 012 | candidate-basic-v1 | negative | 4 | live-source-read-denied | N04 |
| 013 | candidate-basic-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 014 | candidate-basic-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 015 | candidate-basic-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 016 | candidate-basic-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 017 | candidate-basic-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 018 | candidate-basic-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 019 | candidate-basic-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 020 | candidate-basic-v1 | negative | 12 | external-tcp-denied | N12 |
| 021 | candidate-basic-v1 | negative | 13 | external-udp-denied | N13 |
| 022 | candidate-basic-v1 | negative | 14 | dns-resolution-denied | N14 |
| 023 | candidate-basic-v1 | negative | 15 | tcp-ipv4-bind-denied | N15 |
| 024 | candidate-basic-v1 | negative | 16 | tcp-ipv6-bind-denied | N16 |
| 025 | candidate-basic-v1 | negative | 17 | udp-ipv4-bind-denied | N17 |
| 026 | candidate-basic-v1 | negative | 18 | udp-ipv6-bind-denied | N18 |
| 027 | candidate-basic-v1 | negative | 19 | unix-bind-denied | N19 |
| 028 | candidate-basic-v1 | negative | 20 | candidate-run-status-write-denied | N21 |
| 029 | candidate-basic-v1 | negative | 21 | candidate-ux1b-write-denied | N22 |
| 030 | candidate-basic-v1 | negative | 22 | candidate-ui-write-denied | N23 |
| 031 | candidate-basic-v1 | negative | 23 | playwright-node-exec-denied | N24 |
| 032 | candidate-basic-v1 | negative | 24 | headless-shell-exec-denied | N25 |
| 033 | candidate-browser-tcp-unix-ux1b-v1 | positive | 1 | venv-launcher-identity | P01 |
| 034 | candidate-browser-tcp-unix-ux1b-v1 | positive | 2 | venv-prefix-identity | P02 |
| 035 | candidate-browser-tcp-unix-ux1b-v1 | positive | 3 | venv-package-imports | P03 |
| 036 | candidate-browser-tcp-unix-ux1b-v1 | positive | 4 | candidate-source-read | P04 |
| 037 | candidate-browser-tcp-unix-ux1b-v1 | positive | 5 | private-environment-read-write | P05 |
| 038 | candidate-browser-tcp-unix-ux1b-v1 | positive | 6 | base-system-runtime-read | P06 |
| 039 | candidate-browser-tcp-unix-ux1b-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 040 | candidate-browser-tcp-unix-ux1b-v1 | positive | 8 | process-family-token-binding | P08 |
| 041 | candidate-browser-tcp-unix-ux1b-v1 | positive | 9 | tcp-ipv4-roundtrip | P09 |
| 042 | candidate-browser-tcp-unix-ux1b-v1 | positive | 10 | tcp-ipv6-roundtrip | P10 |
| 043 | candidate-browser-tcp-unix-ux1b-v1 | positive | 11 | unix-path-bind-listen-close | P16 |
| 044 | candidate-browser-tcp-unix-ux1b-v1 | positive | 12 | candidate-ux1b-write-read-remove | P14 |
| 045 | candidate-browser-tcp-unix-ux1b-v1 | positive | 13 | candidate-ui-write-read-remove | P15 |
| 046 | candidate-browser-tcp-unix-ux1b-v1 | positive | 14 | playwright-node-exec | P17 |
| 047 | candidate-browser-tcp-unix-ux1b-v1 | positive | 15 | chromium-default-launch-page-close | P18 |
| 048 | candidate-browser-tcp-unix-ux1b-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 049 | candidate-browser-tcp-unix-ux1b-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 050 | candidate-browser-tcp-unix-ux1b-v1 | negative | 3 | ps-exec-denied | N03 |
| 051 | candidate-browser-tcp-unix-ux1b-v1 | negative | 4 | live-source-read-denied | N04 |
| 052 | candidate-browser-tcp-unix-ux1b-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 053 | candidate-browser-tcp-unix-ux1b-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 054 | candidate-browser-tcp-unix-ux1b-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 055 | candidate-browser-tcp-unix-ux1b-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 056 | candidate-browser-tcp-unix-ux1b-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 057 | candidate-browser-tcp-unix-ux1b-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 058 | candidate-browser-tcp-unix-ux1b-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 059 | candidate-browser-tcp-unix-ux1b-v1 | negative | 12 | external-tcp-denied | N12 |
| 060 | candidate-browser-tcp-unix-ux1b-v1 | negative | 13 | external-udp-denied | N13 |
| 061 | candidate-browser-tcp-unix-ux1b-v1 | negative | 14 | dns-resolution-denied | N14 |
| 062 | candidate-browser-tcp-unix-ux1b-v1 | negative | 15 | udp-ipv4-bind-denied | N17 |
| 063 | candidate-browser-tcp-unix-ux1b-v1 | negative | 16 | udp-ipv6-bind-denied | N18 |
| 064 | candidate-browser-tcp-unix-ux1b-v1 | negative | 17 | candidate-run-status-write-denied | N21 |
| 065 | candidate-browser-tcp-unix-ux1b-v1 | negative | 18 | chromium-app-exec-denied | N26 |
| 066 | candidate-tcp-loopback-ux1b-v1 | positive | 1 | venv-launcher-identity | P01 |
| 067 | candidate-tcp-loopback-ux1b-v1 | positive | 2 | venv-prefix-identity | P02 |
| 068 | candidate-tcp-loopback-ux1b-v1 | positive | 3 | venv-package-imports | P03 |
| 069 | candidate-tcp-loopback-ux1b-v1 | positive | 4 | candidate-source-read | P04 |
| 070 | candidate-tcp-loopback-ux1b-v1 | positive | 5 | private-environment-read-write | P05 |
| 071 | candidate-tcp-loopback-ux1b-v1 | positive | 6 | base-system-runtime-read | P06 |
| 072 | candidate-tcp-loopback-ux1b-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 073 | candidate-tcp-loopback-ux1b-v1 | positive | 8 | process-family-token-binding | P08 |
| 074 | candidate-tcp-loopback-ux1b-v1 | positive | 9 | tcp-ipv4-roundtrip | P09 |
| 075 | candidate-tcp-loopback-ux1b-v1 | positive | 10 | tcp-ipv6-roundtrip | P10 |
| 076 | candidate-tcp-loopback-ux1b-v1 | positive | 11 | candidate-ux1b-write-read-remove | P14 |
| 077 | candidate-tcp-loopback-ux1b-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 078 | candidate-tcp-loopback-ux1b-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 079 | candidate-tcp-loopback-ux1b-v1 | negative | 3 | ps-exec-denied | N03 |
| 080 | candidate-tcp-loopback-ux1b-v1 | negative | 4 | live-source-read-denied | N04 |
| 081 | candidate-tcp-loopback-ux1b-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 082 | candidate-tcp-loopback-ux1b-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 083 | candidate-tcp-loopback-ux1b-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 084 | candidate-tcp-loopback-ux1b-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 085 | candidate-tcp-loopback-ux1b-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 086 | candidate-tcp-loopback-ux1b-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 087 | candidate-tcp-loopback-ux1b-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 088 | candidate-tcp-loopback-ux1b-v1 | negative | 12 | external-tcp-denied | N12 |
| 089 | candidate-tcp-loopback-ux1b-v1 | negative | 13 | external-udp-denied | N13 |
| 090 | candidate-tcp-loopback-ux1b-v1 | negative | 14 | dns-resolution-denied | N14 |
| 091 | candidate-tcp-loopback-ux1b-v1 | negative | 15 | udp-ipv4-bind-denied | N17 |
| 092 | candidate-tcp-loopback-ux1b-v1 | negative | 16 | udp-ipv6-bind-denied | N18 |
| 093 | candidate-tcp-loopback-ux1b-v1 | negative | 17 | unix-bind-denied | N19 |
| 094 | candidate-tcp-loopback-ux1b-v1 | negative | 18 | candidate-run-status-write-denied | N21 |
| 095 | candidate-tcp-loopback-ux1b-v1 | negative | 19 | candidate-ui-write-denied | N23 |
| 096 | candidate-tcp-loopback-ux1b-v1 | negative | 20 | playwright-node-exec-denied | N24 |
| 097 | candidate-tcp-loopback-ux1b-v1 | negative | 21 | headless-shell-exec-denied | N25 |
| 098 | candidate-tcp-loopback-v1 | positive | 1 | venv-launcher-identity | P01 |
| 099 | candidate-tcp-loopback-v1 | positive | 2 | venv-prefix-identity | P02 |
| 100 | candidate-tcp-loopback-v1 | positive | 3 | venv-package-imports | P03 |
| 101 | candidate-tcp-loopback-v1 | positive | 4 | candidate-source-read | P04 |
| 102 | candidate-tcp-loopback-v1 | positive | 5 | private-environment-read-write | P05 |
| 103 | candidate-tcp-loopback-v1 | positive | 6 | base-system-runtime-read | P06 |
| 104 | candidate-tcp-loopback-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 105 | candidate-tcp-loopback-v1 | positive | 8 | process-family-token-binding | P08 |
| 106 | candidate-tcp-loopback-v1 | positive | 9 | tcp-ipv4-roundtrip | P09 |
| 107 | candidate-tcp-loopback-v1 | positive | 10 | tcp-ipv6-roundtrip | P10 |
| 108 | candidate-tcp-loopback-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 109 | candidate-tcp-loopback-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 110 | candidate-tcp-loopback-v1 | negative | 3 | ps-exec-denied | N03 |
| 111 | candidate-tcp-loopback-v1 | negative | 4 | live-source-read-denied | N04 |
| 112 | candidate-tcp-loopback-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 113 | candidate-tcp-loopback-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 114 | candidate-tcp-loopback-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 115 | candidate-tcp-loopback-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 116 | candidate-tcp-loopback-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 117 | candidate-tcp-loopback-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 118 | candidate-tcp-loopback-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 119 | candidate-tcp-loopback-v1 | negative | 12 | external-tcp-denied | N12 |
| 120 | candidate-tcp-loopback-v1 | negative | 13 | external-udp-denied | N13 |
| 121 | candidate-tcp-loopback-v1 | negative | 14 | dns-resolution-denied | N14 |
| 122 | candidate-tcp-loopback-v1 | negative | 15 | udp-ipv4-bind-denied | N17 |
| 123 | candidate-tcp-loopback-v1 | negative | 16 | udp-ipv6-bind-denied | N18 |
| 124 | candidate-tcp-loopback-v1 | negative | 17 | unix-bind-denied | N19 |
| 125 | candidate-tcp-loopback-v1 | negative | 18 | candidate-run-status-write-denied | N21 |
| 126 | candidate-tcp-loopback-v1 | negative | 19 | candidate-ux1b-write-denied | N22 |
| 127 | candidate-tcp-loopback-v1 | negative | 20 | candidate-ui-write-denied | N23 |
| 128 | candidate-tcp-loopback-v1 | negative | 21 | playwright-node-exec-denied | N24 |
| 129 | candidate-tcp-loopback-v1 | negative | 22 | headless-shell-exec-denied | N25 |
| 130 | candidate-udp-bind-v1 | positive | 1 | venv-launcher-identity | P01 |
| 131 | candidate-udp-bind-v1 | positive | 2 | venv-prefix-identity | P02 |
| 132 | candidate-udp-bind-v1 | positive | 3 | venv-package-imports | P03 |
| 133 | candidate-udp-bind-v1 | positive | 4 | candidate-source-read | P04 |
| 134 | candidate-udp-bind-v1 | positive | 5 | private-environment-read-write | P05 |
| 135 | candidate-udp-bind-v1 | positive | 6 | base-system-runtime-read | P06 |
| 136 | candidate-udp-bind-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 137 | candidate-udp-bind-v1 | positive | 8 | process-family-token-binding | P08 |
| 138 | candidate-udp-bind-v1 | positive | 9 | udp-ipv4-bind-recv-timeout | P11 |
| 139 | candidate-udp-bind-v1 | positive | 10 | unix-socketpair-default | P12 |
| 140 | candidate-udp-bind-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 141 | candidate-udp-bind-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 142 | candidate-udp-bind-v1 | negative | 3 | ps-exec-denied | N03 |
| 143 | candidate-udp-bind-v1 | negative | 4 | live-source-read-denied | N04 |
| 144 | candidate-udp-bind-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 145 | candidate-udp-bind-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 146 | candidate-udp-bind-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 147 | candidate-udp-bind-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 148 | candidate-udp-bind-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 149 | candidate-udp-bind-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 150 | candidate-udp-bind-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 151 | candidate-udp-bind-v1 | negative | 12 | external-tcp-denied | N12 |
| 152 | candidate-udp-bind-v1 | negative | 13 | external-udp-denied | N13 |
| 153 | candidate-udp-bind-v1 | negative | 14 | dns-resolution-denied | N14 |
| 154 | candidate-udp-bind-v1 | negative | 15 | tcp-ipv4-bind-denied | N15 |
| 155 | candidate-udp-bind-v1 | negative | 16 | tcp-ipv6-bind-denied | N16 |
| 156 | candidate-udp-bind-v1 | negative | 17 | unix-bind-denied | N19 |
| 157 | candidate-udp-bind-v1 | negative | 18 | udp-loopback-outbound-denied | N20 |
| 158 | candidate-udp-bind-v1 | negative | 19 | candidate-run-status-write-denied | N21 |
| 159 | candidate-udp-bind-v1 | negative | 20 | candidate-ux1b-write-denied | N22 |
| 160 | candidate-udp-bind-v1 | negative | 21 | candidate-ui-write-denied | N23 |
| 161 | candidate-udp-bind-v1 | negative | 22 | playwright-node-exec-denied | N24 |
| 162 | candidate-udp-bind-v1 | negative | 23 | headless-shell-exec-denied | N25 |
| 163 | candidate-write-run-status-v1 | positive | 1 | venv-launcher-identity | P01 |
| 164 | candidate-write-run-status-v1 | positive | 2 | venv-prefix-identity | P02 |
| 165 | candidate-write-run-status-v1 | positive | 3 | venv-package-imports | P03 |
| 166 | candidate-write-run-status-v1 | positive | 4 | candidate-source-read | P04 |
| 167 | candidate-write-run-status-v1 | positive | 5 | private-environment-read-write | P05 |
| 168 | candidate-write-run-status-v1 | positive | 6 | base-system-runtime-read | P06 |
| 169 | candidate-write-run-status-v1 | positive | 7 | resolved-python-child-exec | P07 |
| 170 | candidate-write-run-status-v1 | positive | 8 | process-family-token-binding | P08 |
| 171 | candidate-write-run-status-v1 | positive | 9 | candidate-run-status-write-read-remove | P13 |
| 172 | candidate-write-run-status-v1 | negative | 1 | unknown-true-exec-denied | N01 |
| 173 | candidate-write-run-status-v1 | negative | 2 | nested-sandbox-exec-denied | N02 |
| 174 | candidate-write-run-status-v1 | negative | 3 | ps-exec-denied | N03 |
| 175 | candidate-write-run-status-v1 | negative | 4 | live-source-read-denied | N04 |
| 176 | candidate-write-run-status-v1 | negative | 5 | outside-allowlist-read-denied | N05 |
| 177 | candidate-write-run-status-v1 | negative | 6 | real-ssh-list-denied | N06 |
| 178 | candidate-write-run-status-v1 | negative | 7 | playwright-cache-list-denied | N07 |
| 179 | candidate-write-run-status-v1 | negative | 8 | live-source-write-open-denied | N08 |
| 180 | candidate-write-run-status-v1 | negative | 9 | candidate-root-write-denied | N09 |
| 181 | candidate-write-run-status-v1 | negative | 10 | live-venv-pyvenv-write-open-denied | N10 |
| 182 | candidate-write-run-status-v1 | negative | 11 | headless-shell-write-open-denied | N11 |
| 183 | candidate-write-run-status-v1 | negative | 12 | external-tcp-denied | N12 |
| 184 | candidate-write-run-status-v1 | negative | 13 | external-udp-denied | N13 |
| 185 | candidate-write-run-status-v1 | negative | 14 | dns-resolution-denied | N14 |
| 186 | candidate-write-run-status-v1 | negative | 15 | tcp-ipv4-bind-denied | N15 |
| 187 | candidate-write-run-status-v1 | negative | 16 | tcp-ipv6-bind-denied | N16 |
| 188 | candidate-write-run-status-v1 | negative | 17 | udp-ipv4-bind-denied | N17 |
| 189 | candidate-write-run-status-v1 | negative | 18 | udp-ipv6-bind-denied | N18 |
| 190 | candidate-write-run-status-v1 | negative | 19 | unix-bind-denied | N19 |
| 191 | candidate-write-run-status-v1 | negative | 20 | candidate-ux1b-write-denied | N22 |
| 192 | candidate-write-run-status-v1 | negative | 21 | candidate-ui-write-denied | N23 |
| 193 | candidate-write-run-status-v1 | negative | 22 | playwright-node-exec-denied | N24 |
| 194 | candidate-write-run-status-v1 | negative | 23 | headless-shell-exec-denied | N25 |

## Acceptance criteria

### AC-SEM-001 — Exact exhaustive mapping

Regeneration at the frozen matrix-source hash yields exactly the 194 rows above:
63 positive, 131 negative, same order, with no unknown or unmapped assertion.
Every row resolves to exactly one recipe and one owner.

### AC-SEM-002 — No result-returning dependency

Static inspection proves no primitive adapter, socket, child executor,
Playwright recorder, or observer can return `ProbeOutcome`, `BrowserProbe`,
expected polarity, or a pass/fail flag. Only dispatchers/finalizers construct
outcomes, and consumer mutants prove their returned raw facts are used.

### AC-SEM-003 — Bounded child evidence

All eight child IDs use the exact bounded plan/result union. Direct actual
`Popen` fault tests and real Seatbelt integrations prove return/signal,
stream, timeout, PID/PGID, wait/reap, and closure facts. Any unbounded or
forged child result fails.

### AC-SEM-004 — Exact zero-argument socketpair

P12 records and requires an empty positional tuple and empty keyword map at the
concrete `socket.socketpair()` call, then proves payload equality and both
closes. Explicit defaults fail.

### AC-SEM-005 — Browser ownership is disjoint and complete

P17 belongs only to CHILD. Browser API evidence contains neither Node nor
quiescence fields. BROWSER-FINAL is the sole producer-then-validator chain for
P18 and final `BrowserProbe`: the probe builds the serialized claim from API,
P17, and runtime facts; after probe exit the coordinator must accept those
unchanged bytes only under the authenticated browser capability/profile's sole
browser exec leaf, a valid process-family receipt, and empty final family
union. It does not require racy descendant enumeration. Neither stage can
perform the other's job.

### AC-SEM-006 — Observer failure cannot become evidence

A `ps` sample with any invalid process result, stream, row, own-row, xstat,
NOTE_EXIT, pre-reap, wait, or post-reap condition emits no observation and
causes TEST-021 to fail. Marker-only detached descendants remain visible.

### AC-SEM-007 — Fail-first and scope preservation

The future Task 1 replacement may add only import-safe Protocol/TypedDict
declarations and named controlled-missing seams to production; no behavior or
I/O. The tests and synthetic mutants become complete now, while the current
suite remains exactly 29 controlled TEST-021 missing-behavior failures and zero
unexpected failures.

## Review checklist

A reviewer must report all findings before severity filtering and explicitly
answer:

- Does every composite resolve to exactly one non-overlapping owner?
- Can any high-level fake return a finished successful/denied outcome without
  exercising its low-level recipe?
- Are child timeout, stdout/stderr caps, PID/PGID, wait/reap, and cleanup exact?
- Is `socketpair()` provably zero-argument?
- Are Node, Chromium API, sole-leaf profile authority, final quiescence, P18,
  and `BrowserProbe` owned exactly once without racy descendant enumeration?
- Can a nonzero/signaled/partial/malformed `ps` result count as evidence?
- Does each named mutant have a deterministic kill path?
- Does the matrix preserve the parent contract without changing production
  execution argv/environment/stdout/`passFds:[]`?

PASS requires zero blocker/high/medium findings. A finding is fixed in this
fresh artifact and rereviewed; the rejected predecessor remains unchanged.

## Review history

| Version | Result | Findings resolved |
| --- | --- | --- |
| v0.1 | FAIL — 2 High, 1 Medium | Added exact private browser-process witness derivation/validator input; strengthened processGroupId/state/public-row projection to the parent grammar; replaced broad mutant labels with exact mutation, invoking test, kill oracle, and closed fault tables. |
| v0.2 | FAIL — 1 High, 1 Medium | Removed the unsynchronized renderer/headless PID witness and restored parent sole-exec-leaf plus final-quiescence evidence; added one exact recipe-qualified Q mutation/oracle for every one of the 44 recipes. |
| v0.3 | Pending fresh review | Current candidate. |
