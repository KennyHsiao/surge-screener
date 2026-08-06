#!/usr/bin/env python3
"""Offline tests for the Sequence 8 host-awake execution gate."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_awake_gate as gate  # noqa: E402


PMSET_READY = (
    b"Now drawing from 'AC Power'\n"
    b" -InternalBattery-0 (id=1234567)\t80%; AC attached; not charging present: true\n"
)
IOREG_OPEN = (
    b"+-o AppleSmartBattery  <class AppleSmartBattery, id 0x100000abc, registered, matched, active, busy 0 (0 ms), retain 8>\n"
    b'    "AppleClamshellState" = No\n'
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def raises_gate(callable_: Callable[[], object], fragment: str) -> None:
    try:
        callable_()
    except gate.AwakeGateError as exc:
        require(fragment in str(exc), f"wrong gate error: {exc}")
        return
    raise AssertionError("awake gate accepted an invalid value")


def test_ready_probes_are_parsed_without_identifier_disclosure() -> None:
    power = gate.parse_pmset_battery(PMSET_READY)
    clamshell = gate.parse_ioreg_clamshell(IOREG_OPEN)
    require(
        power == {"batteryPercent": 80, "powerSource": "AC Power"},
        "power projection differs",
    )
    require(clamshell == {"clamshellOpen": True}, "clamshell projection differs")
    require("1234567" not in json.dumps(power), "battery identifier leaked")


def test_power_probe_fails_closed_for_unsafe_or_ambiguous_states() -> None:
    mutations = (
        (PMSET_READY.replace(b"AC Power", b"Battery Power", 1), "AC Power"),
        (PMSET_READY.replace(b"80%", b"49%"), "50%"),
        (PMSET_READY.replace(b"AC attached", b"discharging"), "AC attached"),
        (PMSET_READY + PMSET_READY.splitlines()[1] + b"\n", "exactly one"),
        (PMSET_READY.replace(b"80%", b"101%"), "percentage"),
        (PMSET_READY + b"\x00", "NUL"),
        (b"\xff", "UTF-8"),
        (b"x" * (gate.MAX_PMSET_BYTES + 1), "output limit"),
    )
    for value, fragment in mutations:
        raises_gate(
            lambda value=value: gate.parse_pmset_battery(value),
            fragment,
        )


def test_clamshell_probe_requires_one_explicit_open_state() -> None:
    for value, fragment in (
        (IOREG_OPEN.replace(b"No", b"Yes"), "closed"),
        (IOREG_OPEN + b'    "AppleClamshellState" = No\n', "exactly one"),
        (b"", "exactly one"),
        (IOREG_OPEN + b"\x00", "NUL"),
        (b"\xff", "UTF-8"),
        (b"x" * (gate.MAX_IOREG_BYTES + 1), "output limit"),
    ):
        raises_gate(
            lambda value=value: gate.parse_ioreg_clamshell(value),
            fragment,
        )


def test_probe_runner_has_exact_argv_timeout_and_bounded_streams() -> None:
    completed = subprocess.CompletedProcess(
        ("/usr/bin/pmset", "-g", "batt"),
        0,
        stdout=PMSET_READY,
        stderr=b"",
    )
    with patch("scripts.ui_ux_awake_gate.subprocess.run", return_value=completed) as run:
        value = gate.run_probe(
            ("/usr/bin/pmset", "-g", "batt"),
            output_limit=gate.MAX_PMSET_BYTES,
        )
    require(value == PMSET_READY, "probe result differs")
    require(
        run.call_args.kwargs
        == {
            "check": False,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": gate.PROBE_TIMEOUT_SECONDS,
            "env": gate.PROBE_ENV,
        },
        "probe subprocess policy differs",
    )
    for result, fragment in (
        (
            subprocess.CompletedProcess(("/usr/bin/x",), 1, stdout=b"", stderr=b"secret"),
            "failed",
        ),
        (
            subprocess.CompletedProcess(
                ("/usr/bin/x",),
                0,
                stdout=b"x" * (gate.MAX_PMSET_BYTES + 1),
                stderr=b"",
            ),
            "output limit",
        ),
        (
            subprocess.CompletedProcess(
                ("/usr/bin/x",),
                0,
                stdout=b"",
                stderr=b"x" * (gate.MAX_PMSET_BYTES + 1),
            ),
            "output limit",
        ),
    ):
        with patch("scripts.ui_ux_awake_gate.subprocess.run", return_value=result):
            raises_gate(
                lambda: gate.run_probe(
                    ("/usr/bin/x",),
                    output_limit=gate.MAX_PMSET_BYTES,
                ),
                fragment,
            )
    with patch(
        "scripts.ui_ux_awake_gate.subprocess.run",
        side_effect=subprocess.TimeoutExpired(("/usr/bin/x",), 2),
    ):
        raises_gate(
            lambda: gate.run_probe(
                ("/usr/bin/x",),
                output_limit=gate.MAX_PMSET_BYTES,
            ),
            "timed out",
        )


def test_system_tools_are_exact_root_owned_nonwritable_executables() -> None:
    for path in gate.SYSTEM_TOOL_PATHS:
        gate.validate_system_tool(path)
    raises_gate(lambda: gate.validate_system_tool(Path("/does/not/exist")), "unavailable")
    with tempfile.NamedTemporaryFile() as untrusted:
        os.chmod(untrusted.name, 0o755)
        raises_gate(
            lambda: gate.validate_system_tool(Path(untrusted.name)),
            "unsafe",
        )


def test_non_darwin_and_failed_gate_leave_all_sequence8_paths_absent() -> None:
    future = (
        ROOT / ".claude/ui_snapshots/ux1b/sequence8-canary-20260725T080000Z",
        ROOT / "docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq8.json",
        ROOT / "docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq8.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260725T081000Z",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/capture-intent-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/capture-terminal-20260725T080000Z.json",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260725T080000Z",
        ROOT / ".claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260725T080000Z",
        Path("/private/tmp/qr-ux1b-s8"),
    )
    require(
        all(not os.path.lexists(path) for path in future),
        "Sequence 8 future namespace was not initially absent",
    )
    with (
        patch("scripts.ui_ux_awake_gate.sys.platform", "linux"),
        patch("scripts.ui_ux_awake_gate.validate_system_tool") as validate,
    ):
        raises_gate(gate.check_host_awake, "Darwin")
    validate.assert_not_called()
    with (
        patch(
            "scripts.ui_ux_awake_gate.check_host_awake",
            side_effect=gate.AwakeGateError("battery must be at least 50%"),
        ),
        patch("scripts.ui_ux_awake_gate.os.execve") as execve,
        patch("sys.stderr", io.StringIO()),
    ):
        code = gate.main(
            (
                "exec",
                "--",
                str(ROOT / ".venv/bin/python"),
                "-B",
                "scripts/ui_ux_snapshot_matrix.py",
            )
        )
    require(code == gate.EXIT_NOT_READY, "failed gate exit differs")
    execve.assert_not_called()
    require(
        all(not os.path.lexists(path) for path in future),
        "failed awake gate created a Sequence 8 namespace",
    )
    require(
        not tuple(Path("/private/tmp").glob("qr-ux1b-c8.*")),
        "failed awake gate created a canary runtime root",
    )


def test_check_revalidates_tools_then_exact_host_probes() -> None:
    calls: list[tuple[str, ...]] = []

    def probe(argv: tuple[str, ...], *, output_limit: int) -> bytes:
        calls.append(argv)
        if argv == ("/usr/bin/pmset", "-g", "batt"):
            require(output_limit == gate.MAX_PMSET_BYTES, "pmset limit differs")
            return PMSET_READY
        if argv == (
            "/usr/sbin/ioreg",
            "-r",
            "-k",
            "AppleClamshellState",
            "-d",
            "4",
        ):
            require(output_limit == gate.MAX_IOREG_BYTES, "ioreg limit differs")
            return IOREG_OPEN
        raise AssertionError(f"unexpected probe: {argv!r}")

    with patch("scripts.ui_ux_awake_gate.validate_system_tool") as validate:
        result = gate.check_host_awake(run=probe)
    require(
        [call.args[0] for call in validate.call_args_list]
        == list(gate.SYSTEM_TOOL_PATHS),
        "system tool validation order differs",
    )
    require(
        calls
        == [
            ("/usr/bin/pmset", "-g", "batt"),
            (
                "/usr/sbin/ioreg",
                "-r",
                "-k",
                "AppleClamshellState",
                "-d",
                "4",
            ),
        ],
        "host probe order differs",
    )
    require(
        result
        == {
            "batteryPercent": 80,
            "clamshellOpen": True,
            "powerSource": "AC Power",
            "schemaVersion": "quant-radar-ui-ux-awake-gate/v1",
            "status": "ready",
        },
        "ready receipt differs",
    )


def test_exec_rechecks_host_and_delegates_exactly_to_caffeinate() -> None:
    checks: list[bool] = []
    execs: list[tuple[str, tuple[str, ...], dict[str, str]]] = []

    def check() -> dict[str, object]:
        checks.append(True)
        return {"status": "ready"}

    def execve(path: str, argv: tuple[str, ...], env: dict[str, str]) -> None:
        execs.append((path, argv, env))
        raise RuntimeError("exec sentinel")

    command = (str(ROOT / ".venv/bin/python"), "-B", "scripts/test_ui_ux_theme.py")
    with patch.dict(os.environ, {"SEQUENCE8_TEST": "1"}, clear=True):
        try:
            gate.exec_under_caffeinate(command, check=check, execve=execve)
        except RuntimeError as exc:
            require(str(exc) == "exec sentinel", "wrong exec sentinel")
        else:
            raise AssertionError("exec test did not reach sentinel")
    require(checks == [True], "host was not rechecked exactly once")
    require(
        execs
        == [
            (
                "/usr/bin/caffeinate",
                (
                    "/usr/bin/caffeinate",
                    "-dimsu",
                    *command,
                ),
                {"SEQUENCE8_TEST": "1"},
            )
        ],
        "caffeinate delegation differs",
    )


def test_exec_command_boundary_rejects_ambiguous_or_malformed_commands() -> None:
    for command, fragment in (
        ((), "required"),
        (("python",), "absolute or workspace"),
        (("../python",), "absolute or workspace"),
        (("/bin/echo\x00x",), "NUL"),
        (("/bin/echo", "x\x00y"), "NUL"),
    ):
        raises_gate(
            lambda command=command: gate.exec_under_caffeinate(
                command,
                check=lambda: {"status": "ready"},
                execve=lambda *_: None,
            ),
            fragment,
        )


def test_cli_check_json_and_failure_output_are_canonical_and_sanitized() -> None:
    ready = {
        "batteryPercent": 80,
        "clamshellOpen": True,
        "powerSource": "AC Power",
        "schemaVersion": "quant-radar-ui-ux-awake-gate/v1",
        "status": "ready",
    }
    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch("scripts.ui_ux_awake_gate.check_host_awake", return_value=ready),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
    ):
        code = gate.main(("check", "--json"))
    require(code == 0, "ready CLI failed")
    require(
        stdout.getvalue()
        == json.dumps(ready, sort_keys=True, separators=(",", ":")) + "\n",
        "ready JSON is not canonical",
    )
    require(stderr.getvalue() == "", "ready CLI wrote stderr")

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch(
            "scripts.ui_ux_awake_gate.check_host_awake",
            side_effect=gate.AwakeGateError("host state unavailable"),
        ),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
    ):
        code = gate.main(("check", "--json"))
    require(code == gate.EXIT_NOT_READY, "failure CLI exit differs")
    require(stdout.getvalue() == "", "failure CLI wrote stdout")
    require(
        stderr.getvalue() == "awake gate: host state unavailable\n",
        "failure output differs",
    )


def main() -> int:
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_")
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS all {len(tests)} Sequence 8 awake-gate tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
