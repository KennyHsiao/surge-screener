#!/usr/bin/env python3
"""Focused tests for framework-neutral fail-soft artifact loading."""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.artifact_loader import ArtifactAvailable, ArtifactUnavailable, load_json_artifact


def _path(tmp: str, raw: bytes) -> Path:
    path = Path(tmp) / "artifact.json"
    path.write_bytes(raw)
    return path


def test_valid_object_is_available() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = load_json_artifact(_path(tmp, b'{"rows": [{"ticker": "AAPL"}]}'))

    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if result.reason != "ok" or result.data != {"rows": [{"ticker": "AAPL"}]}:
        raise AssertionError(result)


def test_missing_file_is_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = load_json_artifact(Path(tmp) / "missing.json")

    if not isinstance(result, ArtifactUnavailable) or result.reason != "missing":
        raise AssertionError(result)


def test_malformed_and_invalid_utf8_are_invalid_json() -> None:
    fixtures = [b"", b'{"rows":', b"\xff\xfe"]
    with tempfile.TemporaryDirectory() as tmp:
        for raw in fixtures:
            result = load_json_artifact(_path(tmp, raw))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_json":
                raise AssertionError((raw, result))


def test_strict_mode_rejects_every_non_finite_number() -> None:
    fixtures = [
        b'{"value": NaN}',
        b'{"value": Infinity}',
        b'{"value": -Infinity}',
        b'{"value": 1e999}',
        b'{"value": -1e999}',
        b'{"nested": [1, 1e999]}',
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for raw in fixtures:
            result = load_json_artifact(_path(tmp, raw))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_json":
                raise AssertionError((raw, result))


def test_strict_mode_rejects_lone_unicode_surrogates() -> None:
    fixtures = [
        br'{"value": "\ud800"}',
        br'{"nested": [{"value": "\udfff"}]}',
        br'{"\ud800": "unsafe key"}',
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for raw in fixtures:
            result = load_json_artifact(_path(tmp, raw))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_json":
                raise AssertionError((raw, result))

        compatible = load_json_artifact(
            _path(tmp, br'{"value": "\ud800"}'),
            require_object=False,
            reject_non_finite=False,
        )
    if not isinstance(compatible, ArtifactAvailable):
        raise AssertionError(type(compatible).__name__)
    if not isinstance(compatible.data, dict):
        raise AssertionError(type(compatible.data).__name__)
    if ord(compatible.data["value"]) != 0xD800:
        raise AssertionError("compatibility mode changed lone-surrogate parsing")


def test_compatibility_mode_keeps_python_json_semantics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        nan_result = load_json_artifact(
            _path(tmp, b'{"value": NaN}'),
            require_object=False,
            reject_non_finite=False,
        )
        overflow_result = load_json_artifact(
            _path(tmp, b'{"value": 1e999}'),
            require_object=False,
            reject_non_finite=False,
        )

    if not isinstance(nan_result, ArtifactAvailable):
        raise AssertionError(nan_result)
    if not isinstance(nan_result.data, dict) or not math.isnan(nan_result.data["value"]):
        raise AssertionError(nan_result)
    if not isinstance(overflow_result, ArtifactAvailable):
        raise AssertionError(overflow_result)
    if not isinstance(overflow_result.data, dict) or not math.isinf(overflow_result.data["value"]):
        raise AssertionError(overflow_result)


def test_strict_object_mode_rejects_other_json_roots() -> None:
    fixtures = [b"[]", b'"text"', b"42", b"true", b"null"]
    with tempfile.TemporaryDirectory() as tmp:
        for raw in fixtures:
            result = load_json_artifact(_path(tmp, raw))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((raw, result))


def test_compatibility_mode_returns_other_json_roots() -> None:
    fixtures = [(b"[]", []), (b'"text"', "text"), (b"42", 42), (b"true", True), (b"null", None)]
    with tempfile.TemporaryDirectory() as tmp:
        for raw, expected in fixtures:
            result = load_json_artifact(
                _path(tmp, raw),
                require_object=False,
                reject_non_finite=False,
            )
            if not isinstance(result, ArtifactAvailable) or result.data != expected:
                raise AssertionError((raw, result))


def test_expected_os_error_is_unreadable() -> None:
    with patch("scripts.artifact_loader.Path.read_text", side_effect=PermissionError("private")):
        result = load_json_artifact("ignored.json")

    if not isinstance(result, ArtifactUnavailable) or result.reason != "unreadable":
        raise AssertionError(result)

    invalid_path = load_json_artifact("invalid\0path.json")
    if not isinstance(invalid_path, ArtifactUnavailable) or invalid_path.reason != "unreadable":
        raise AssertionError(invalid_path)


def test_unexpected_error_is_not_swallowed() -> None:
    try:
        with patch("scripts.artifact_loader.Path.read_text", side_effect=RuntimeError("bug")):
            load_json_artifact("ignored.json")
    except RuntimeError as exc:
        if str(exc) != "bug":
            raise
    else:
        raise AssertionError("unexpected RuntimeError was swallowed")


def test_next_read_recovers_after_partial_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _path(tmp, b'{"rows":')
        first = load_json_artifact(path)
        path.write_text('{"rows": []}', encoding="utf-8")
        second = load_json_artifact(path)

    if not isinstance(first, ArtifactUnavailable) or first.reason != "invalid_json":
        raise AssertionError(first)
    if not isinstance(second, ArtifactAvailable) or second.data != {"rows": []}:
        raise AssertionError(second)


def test_streamlit_wrapper_preserves_json_compatibility() -> None:
    from ui import _shared

    fixtures = [(b"[]", []), (b'"text"', "text"), (b"42", 42), (b"true", True), (b"null", None)]
    with tempfile.TemporaryDirectory() as tmp:
        for raw, expected in fixtures:
            _shared.load_json.clear()
            actual = _shared.load_json(str(_path(tmp, raw)))
            if actual != expected:
                raise AssertionError((raw, actual))

        _shared.load_json.clear()
        nan_value = _shared.load_json(str(_path(tmp, b'{"value": NaN}')))
        if not isinstance(nan_value, dict) or not math.isnan(nan_value["value"]):
            raise AssertionError(nan_value)

        _shared.load_json.clear()
        if _shared.load_json(str(Path(tmp) / "missing.json")) is not None:
            raise AssertionError("missing Streamlit artifact should return None")

        _shared.load_json.clear()
        if _shared.load_json("invalid\0path.json") is not None:
            raise AssertionError("invalid Streamlit path should remain fail-soft")


def test_streamlit_wrapper_clear_reloads_changed_file() -> None:
    from ui import _shared

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cached.json"
        path.write_text('{"value": "A"}', encoding="utf-8")
        _shared.load_json.clear()
        first = _shared.load_json(str(path))
        path.write_text('{"value": "B"}', encoding="utf-8")
        cached = _shared.load_json(str(path))
        _shared.load_json.clear()
        refreshed = _shared.load_json(str(path))

    if first != {"value": "A"} or cached != {"value": "A"}:
        raise AssertionError((first, cached))
    if refreshed != {"value": "B"}:
        raise AssertionError(refreshed)


def test_streamlit_wrapper_delegates_to_pure_loader() -> None:
    from ui import _shared

    _shared.load_json.clear()
    with patch.object(
        _shared,
        "load_json_artifact",
        return_value=ArtifactAvailable({"delegated": True}),
    ) as delegated:
        actual = _shared.load_json("does-not-need-to-exist.json")

    if actual != {"delegated": True}:
        raise AssertionError(actual)
    delegated.assert_called_once_with(
        "does-not-need-to-exist.json",
        require_object=False,
        reject_non_finite=False,
    )


def main() -> None:
    tests = [
        test_valid_object_is_available,
        test_missing_file_is_fail_soft,
        test_malformed_and_invalid_utf8_are_invalid_json,
        test_strict_mode_rejects_every_non_finite_number,
        test_strict_mode_rejects_lone_unicode_surrogates,
        test_compatibility_mode_keeps_python_json_semantics,
        test_strict_object_mode_rejects_other_json_roots,
        test_compatibility_mode_returns_other_json_roots,
        test_expected_os_error_is_unreadable,
        test_unexpected_error_is_not_swallowed,
        test_next_read_recovers_after_partial_write,
        test_streamlit_wrapper_preserves_json_compatibility,
        test_streamlit_wrapper_clear_reloads_changed_file,
        test_streamlit_wrapper_delegates_to_pure_loader,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
