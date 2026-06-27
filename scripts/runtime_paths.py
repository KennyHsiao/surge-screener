#!/usr/bin/env python3
"""Runtime path helpers shared by CLI scripts and Streamlit UI."""

from __future__ import annotations

import os
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
RUNTIME_DIR = Path(os.environ.get("SURGE_RUNTIME_DIR", str(REPO))).expanduser()
CANDIDATE_OUTPUT_DIR = Path(
    os.environ.get("SURGE_CANDIDATE_OUTPUT_DIR", str(RUNTIME_DIR))
).expanduser()


def candidate_output_path(filename: str | Path) -> Path:
    """Return the path for generated candidate artifacts.

    Local runs default to the repo root for backward compatibility. Docker sets
    SURGE_CANDIDATE_OUTPUT_DIR to a mounted volume so these artifacts survive
    container recreation.
    """
    path = Path(filename).expanduser()
    if path.is_absolute():
        return path
    if len(path.parts) == 1:
        return CANDIDATE_OUTPUT_DIR / path
    return REPO / path


def ensure_parent(path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
