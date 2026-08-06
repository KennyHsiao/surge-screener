#!/usr/bin/env python3
"""Framework-neutral, fail-soft JSON artifact loading."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
UnavailableReason: TypeAlias = Literal[
    "missing",
    "invalid_json",
    "invalid_shape",
    "unreadable",
]


@dataclass(frozen=True, slots=True)
class ArtifactAvailable:
    """A parsed JSON value that passed the requested root validation."""

    data: JsonValue
    available: Literal[True] = field(default=True, init=False)
    reason: Literal["ok"] = field(default="ok", init=False)


@dataclass(frozen=True, slots=True)
class ArtifactUnavailable:
    """An expected artifact read/parse/shape failure."""

    reason: UnavailableReason
    available: Literal[False] = field(default=False, init=False)
    data: None = field(default=None, init=False)


LoadResult: TypeAlias = ArtifactAvailable | ArtifactUnavailable


def _reject_constant(value: str) -> float:
    raise ValueError(f"non-finite JSON constant: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _contains_lone_surrogate(value: JsonValue) -> bool:
    """Return whether a parsed value cannot be encoded as valid UTF-8."""

    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return any(_contains_lone_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_lone_surrogate(key) or _contains_lone_surrogate(item)
            for key, item in value.items()
        )
    return False


def load_json_artifact(
    path: str | Path,
    *,
    require_object: bool = True,
    reject_non_finite: bool = True,
) -> LoadResult:
    """Read one JSON artifact without raising for expected data failures.

    API callers use the strict defaults. Streamlit's compatibility wrapper sets
    both options to ``False`` so it retains the existing ``json.load`` behavior.
    Unexpected programming errors are intentionally not caught.
    """

    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ArtifactUnavailable("missing")
    except UnicodeError:
        return ArtifactUnavailable("invalid_json")
    except ValueError:
        return ArtifactUnavailable("unreadable")
    except OSError:
        return ArtifactUnavailable("unreadable")

    try:
        if reject_non_finite:
            data: JsonValue = json.loads(
                raw,
                parse_constant=_reject_constant,
                parse_float=_finite_float,
            )
        else:
            data = json.loads(raw)
        if reject_non_finite and _contains_lone_surrogate(data):
            raise ValueError("JSON contains a lone Unicode surrogate")
    except (ValueError, RecursionError):
        return ArtifactUnavailable("invalid_json")

    if require_object and not isinstance(data, dict):
        return ArtifactUnavailable("invalid_shape")
    return ArtifactAvailable(data)
