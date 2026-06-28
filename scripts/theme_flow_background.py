#!/usr/bin/env python3
"""Detached worker for theme-flow refresh and AI read generation."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
for p in (REPO, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from scripts import theme_flow_controls as controls
except ImportError:
    import theme_flow_controls as controls  # type: ignore


def _run_refresh_board() -> dict:
    try:
        from scripts import theme_flow
    except ImportError:
        import theme_flow  # type: ignore
    flow = theme_flow.gather_theme_flow()
    if not flow or not flow.get("themes"):
        raise RuntimeError("theme flow refresh returned no usable themes")
    controls.write_snapshot(flow)
    return {
        "as_of": flow.get("as_of"),
        "themes": len(flow.get("themes") or []),
        "snapshot_path": str(controls.SNAPSHOT_PATH),
    }


def _run_ai_read() -> dict:
    try:
        from scripts import theme_rotation
    except ImportError:
        import theme_rotation  # type: ignore
    result = theme_rotation.generate_theme_flow_read()
    if not isinstance(result, dict) or result.get("status") != "ready":
        raise RuntimeError(str((result or {}).get("error") or (result or {}).get("status") or "AI read failed"))
    return {
        "status": result.get("status"),
        "as_of": result.get("as_of"),
        "output_path": str(getattr(theme_rotation, "OUT", "")),
    }


def run(mode: controls.RunMode) -> int:
    controls.write_status(mode, "running")
    try:
        if mode == "refresh_board":
            result = _run_refresh_board()
        elif mode == "ai_read":
            result = _run_ai_read()
        else:
            raise ValueError(f"unknown mode: {mode}")
        controls.write_status(mode, "ready", result=result)
        print(f"{mode}: ready {result}", flush=True)
        return 0
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        controls.write_status(mode, "failed", error=str(e))
        return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=tuple(controls.MODE_LABELS), required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.mode)


if __name__ == "__main__":
    sys.exit(main())
