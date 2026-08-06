#!/usr/bin/env python3
"""Fail-closed host-awake gate for bounded UX-1B browser captures.

Sequence 8 permits a capture command to start only while the Mac is on AC
power, has adequate charge, and has an open clamshell.  The command is then
replaced by the system ``caffeinate`` executable so the inhibition lifetime is
exactly the child-command lifetime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, NoReturn, Sequence


SCHEMA_VERSION = "quant-radar-ui-ux-awake-gate/v1"
EXIT_USAGE = 2
EXIT_NOT_READY = 3
MINIMUM_BATTERY_PERCENT = 50
PROBE_TIMEOUT_SECONDS = 2
MAX_PMSET_BYTES = 16 * 1024
MAX_IOREG_BYTES = 64 * 1024
CAFFEINATE_PATH = Path("/usr/bin/caffeinate")
PMSET_PATH = Path("/usr/bin/pmset")
IOREG_PATH = Path("/usr/sbin/ioreg")
SYSTEM_TOOL_PATHS = (CAFFEINATE_PATH, PMSET_PATH, IOREG_PATH)
PROBE_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C",
    "LC_ALL": "C",
}
_BATTERY_LINE = re.compile(
    r"^ -InternalBattery-[0-9]+ \(id=[0-9]+\)\t"
    r"(?P<percent>[0-9]{1,3})%;(?P<state>[^\r\n]*)$",
    re.MULTILINE,
)
_CLAMSHELL_LINE = re.compile(
    r'^[ \t|]*"AppleClamshellState"[ \t]*=[ \t]*(?P<state>Yes|No)[ \t]*$',
    re.MULTILINE,
)


class AwakeGateError(RuntimeError):
    """The local host state cannot safely authorize a capture."""


ProbeRunner = Callable[..., bytes]
HostChecker = Callable[[], Mapping[str, object]]
Execve = Callable[[str, tuple[str, ...], dict[str, str]], NoReturn]


def _decode_probe_output(data: bytes, *, output_limit: int) -> str:
    if not isinstance(data, bytes):
        raise AwakeGateError("probe output type is invalid")
    if len(data) > output_limit:
        raise AwakeGateError("probe output limit exceeded")
    if b"\x00" in data:
        raise AwakeGateError("probe output contains NUL")
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AwakeGateError("probe output is not UTF-8") from exc


def parse_pmset_battery(data: bytes) -> dict[str, object]:
    """Project the exact safe subset of ``pmset -g batt`` output."""

    text = _decode_probe_output(data, output_limit=MAX_PMSET_BYTES)
    lines = text.splitlines()
    if not lines or lines[0] != "Now drawing from 'AC Power'":
        raise AwakeGateError("host is not drawing from AC Power")
    matches = list(_BATTERY_LINE.finditer(text))
    if len(matches) != 1:
        raise AwakeGateError("pmset must report exactly one internal battery")
    match = matches[0]
    percent = int(match.group("percent"))
    if percent > 100:
        raise AwakeGateError("battery percentage is invalid")
    if percent < MINIMUM_BATTERY_PERCENT:
        raise AwakeGateError(
            f"battery must be at least {MINIMUM_BATTERY_PERCENT}%"
        )
    state = match.group("state")
    if "AC attached" not in {
        item.strip() for item in state.split(";")
    }:
        raise AwakeGateError("battery does not report AC attached")
    return {
        "batteryPercent": percent,
        "powerSource": "AC Power",
    }


def parse_ioreg_clamshell(data: bytes) -> dict[str, object]:
    """Project the exact safe subset of the clamshell registry output."""

    text = _decode_probe_output(data, output_limit=MAX_IOREG_BYTES)
    matches = list(_CLAMSHELL_LINE.finditer(text))
    if len(matches) != 1:
        raise AwakeGateError(
            "ioreg must report exactly one AppleClamshellState"
        )
    if matches[0].group("state") != "No":
        raise AwakeGateError("host clamshell is closed")
    return {"clamshellOpen": True}


def validate_system_tool(path: Path) -> None:
    """Require one immutable-looking Apple system executable identity."""

    if not isinstance(path, Path) or not path.is_absolute():
        raise AwakeGateError("system tool path is invalid")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise AwakeGateError("required system tool is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_mode & 0o022
        or not metadata.st_mode & 0o111
        or path.is_symlink()
    ):
        raise AwakeGateError("required system tool identity is unsafe")


def run_probe(
    argv: tuple[str, ...],
    *,
    output_limit: int,
) -> bytes:
    """Run one fixed, non-interactive system probe with bounded output."""

    if (
        not isinstance(argv, tuple)
        or not argv
        or any(not isinstance(value, str) or "\x00" in value for value in argv)
        or not Path(argv[0]).is_absolute()
        or type(output_limit) is not int
        or output_limit < 1
    ):
        raise AwakeGateError("probe invocation is invalid")
    try:
        completed = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=PROBE_TIMEOUT_SECONDS,
            env=PROBE_ENV,
        )
    except subprocess.TimeoutExpired as exc:
        raise AwakeGateError("host-state probe timed out") from exc
    except OSError as exc:
        raise AwakeGateError("host-state probe is unavailable") from exc
    if completed.returncode != 0:
        raise AwakeGateError("host-state probe failed")
    if (
        len(completed.stdout) > output_limit
        or len(completed.stderr) > output_limit
    ):
        raise AwakeGateError("probe output limit exceeded")
    return completed.stdout


def check_host_awake(
    *,
    run: ProbeRunner = run_probe,
) -> dict[str, object]:
    """Revalidate trusted tools and return a minimal ready receipt."""

    if sys.platform != "darwin":
        raise AwakeGateError("host awake gate requires Darwin")
    for path in SYSTEM_TOOL_PATHS:
        validate_system_tool(path)
    power = parse_pmset_battery(
        run(
            (str(PMSET_PATH), "-g", "batt"),
            output_limit=MAX_PMSET_BYTES,
        )
    )
    clamshell = parse_ioreg_clamshell(
        run(
            (
                str(IOREG_PATH),
                "-r",
                "-k",
                "AppleClamshellState",
                "-d",
                "4",
            ),
            output_limit=MAX_IOREG_BYTES,
        )
    )
    return {
        "batteryPercent": power["batteryPercent"],
        "clamshellOpen": clamshell["clamshellOpen"],
        "powerSource": power["powerSource"],
        "schemaVersion": SCHEMA_VERSION,
        "status": "ready",
    }


def _validate_command(command: Sequence[str]) -> tuple[str, ...]:
    if (
        isinstance(command, (str, bytes))
        or not isinstance(command, Sequence)
        or not command
    ):
        raise AwakeGateError("capture command is required")
    values = tuple(command)
    if any(
        not isinstance(value, str)
        or not value
        or "\x00" in value
        for value in values
    ):
        raise AwakeGateError("capture command contains NUL or empty arguments")
    executable = values[0]
    if not os.path.isabs(executable):
        pure = PurePosixPath(executable)
        if (
            "/" not in executable
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise AwakeGateError(
                "capture executable must be absolute or workspace-relative"
            )
    return values


def exec_under_caffeinate(
    command: Sequence[str],
    *,
    check: HostChecker | None = None,
    execve: Execve | None = None,
) -> NoReturn:
    """Recheck host readiness and atomically delegate to ``caffeinate``."""

    values = _validate_command(command)
    host_check = check_host_awake if check is None else check
    execute = os.execve if execve is None else execve
    host_check()
    environment = dict(os.environ)
    argv = (str(CAFFEINATE_PATH), "-dimsu", *values)
    execute(str(CAFFEINATE_PATH), argv, environment)
    raise AwakeGateError("caffeinate exec unexpectedly returned")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sequence 8 host-awake execution gate",
    )
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--json", action="store_true")
    exec_parser = subparsers.add_parser("exec")
    exec_parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command_name == "check":
            receipt = check_host_awake()
            if args.json:
                print(
                    json.dumps(
                        receipt,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            else:
                print("ready")
            return 0
        command = tuple(args.command)
        if command[:1] == ("--",):
            command = command[1:]
        exec_under_caffeinate(command)
    except AwakeGateError as exc:
        print(f"awake gate: {exc}", file=sys.stderr)
        return EXIT_NOT_READY
    raise AwakeGateError("unreachable command state")


if __name__ == "__main__":
    raise SystemExit(main())
