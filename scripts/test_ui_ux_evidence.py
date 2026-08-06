#!/usr/bin/env python3
"""Red contracts for authenticated UX-1B evidence and migration comparison.

The implementation module is intentionally introduced after this test.  Run with::

    .venv/bin/python scripts/test_ui_ux_evidence.py
"""

from __future__ import annotations

import base64
import argparse
import copy
import gc
import hashlib
import http.server
import io
import inspect
import json
import math
import os
import re
import resource
import stat
import subprocess
import struct
import sys
import tempfile
import threading
import time
import types
import urllib.parse
import zlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Callable
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_evidence as evidence  # noqa: E402
from scripts import ui_ux_isolation as isolation  # noqa: E402


OWNER = os.getuid()
STACK_DIGEST = "c" * 64
SOURCE_DIGEST = "d" * 64
APP_PORT = 43123
APP_ORIGIN = f"http://127.0.0.1:{APP_PORT}"
WORKER_REQUEST_SCHEMA = "quant-radar-ui-ux-browser-request/v1"
WORKER_RESPONSE_SCHEMA = "quant-radar-ui-ux-browser-response/v1"
RENDER_SCHEMA = "quant-radar-ui-ux-render/v1"
REQUEST_ID = "knowledge-graph-controls/mobile"
PNG_STAGE_PATH = "captures/knowledge-graph-controls/mobile.png"
SIDECAR_STAGE_PATH = "captures/knowledge-graph-controls/mobile.render.json"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class _LineInterleavingNetwork(Mapping[str, object]):
    """Return valid entry values once, then forged values on any reread."""

    def __init__(self) -> None:
        self._reads = {"appOrigin": 0, "appPort": 0}

    def __getitem__(self, key: str) -> object:
        self._reads[key] += 1
        if self._reads[key] == 1:
            return APP_ORIGIN if key == "appOrigin" else APP_PORT
        return "http://127.0.0.1:9" if key == "appOrigin" else 9

    def __iter__(self) -> Iterator[str]:
        return iter(("appOrigin", "appPort"))

    def __len__(self) -> int:
        return 2


def _png_rgba(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", checksum)
        )

    row = b"\x00" + bytes(rgba) * width
    raw = row * height
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


_VIEWPORT_PNG_CACHE: dict[tuple[int, int], bytes] = {}


def _viewport_png(viewport: Mapping[str, object]) -> bytes:
    width = int(viewport["width"])
    height = int(viewport["height"])
    key = (width, height)
    if key not in _VIEWPORT_PNG_CACHE:
        _VIEWPORT_PNG_CACHE[key] = _png_rgba(
            width,
            height,
            (16, 24, 40, 255),
        )
    return _VIEWPORT_PNG_CACHE[key]


def _png_overexpanded_1x1() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", checksum)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 1_000_000))
        + chunk(b"IEND", b"")
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(type(value).__name__)
    return value


def _raises(
    expected: type[BaseException], callback: Callable[[], object]
) -> BaseException:
    try:
        callback()
    except expected as exc:
        return exc
    except BaseException as exc:  # noqa: BLE001
        raise AssertionError(
            f"expected {expected.__name__}, got {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"expected {expected.__name__}")


def _root_fd(path: Path) -> int:
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY)


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _json_line(document: dict) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _valid_worker_request() -> dict:
    return {
        "schemaVersion": WORKER_REQUEST_SCHEMA,
        "requestId": REQUEST_ID,
        "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
        "case": "knowledge-graph-controls",
        "route": "/__selection__/knowledge-graph",
        "viewport": {"name": "mobile", "width": 390, "height": 844},
        "appOrigin": APP_ORIGIN,
        "staging": {
            "png": PNG_STAGE_PATH,
            "renderSidecar": SIDECAR_STAGE_PATH,
        },
    }


def _valid_worker_response() -> dict:
    return {
        "schemaVersion": WORKER_RESPONSE_SCHEMA,
        "requestId": REQUEST_ID,
        "status": "staged",
        "artifacts": {
            "png": PNG_STAGE_PATH,
            "renderSidecar": SIDECAR_STAGE_PATH,
        },
    }


def _full_render_sidecar(*, run_suffix: str = "a") -> dict:
    owned_root = f"/private/tmp/quant-radar-owned-{run_suffix}"
    return {
        "schemaVersion": RENDER_SCHEMA,
        "identity": {
            "case": "knowledge-graph-controls",
            "route": "/__selection__/knowledge-graph",
            "callable": "knowledge_graph.render",
        },
        "viewport": {"name": "mobile", "width": 390, "height": 844},
        "readiness": {
            "ready": True,
            "marker": "quant-radar-fixture-ready",
        },
        "nodes": [
            {
                "id": "stable-node-0",
                "browserNodeId": f"browser-internal-{run_suffix}",
                "parentId": None,
                "flowScope": "main",
                "boundaryId": None,
                "rootSelector": None,
                "role": "heading",
                "name": "Knowledge Graph",
                "text": "Knowledge Graph",
                "state": {"expanded": False},
                "visible": True,
                "bounds": {"x": 20, "y": 20, "width": 300, "height": 30},
            },
            {
                "id": "stable-node-1",
                "browserNodeId": f"browser-group-{run_suffix}",
                "parentId": "mode-row",
                "flowScope": "main",
                "boundaryId": "mode-row",
                "rootSelector": ".st-key-kg_view_mode",
                "role": "radiogroup",
                "name": "視圖",
                "text": "",
                "state": {},
                "visible": True,
                "bounds": {"x": 20, "y": 60, "width": 165, "height": 40},
            },
            {
                "id": "stable-node-2",
                "browserNodeId": f"browser-radio-{run_suffix}",
                "parentId": "stable-node-1",
                "flowScope": "main",
                "boundaryId": "mode-row",
                "rootSelector": None,
                "role": "radio",
                "name": "星雲圖",
                "text": "星雲圖",
                "state": {"checked": True, "tabIndex": 0},
                "visible": True,
                "bounds": {"x": 20, "y": 64, "width": 70, "height": 24},
            },
            {
                "id": "stable-node-3",
                "browserNodeId": f"browser-label-{run_suffix}",
                "parentId": "mode-row",
                "flowScope": "main",
                "boundaryId": "mode-row",
                "rootSelector": ".st-key-kg_label_mode",
                "role": "radiogroup",
                "name": "標籤",
                "text": "",
                "state": {},
                "visible": True,
                "bounds": {"x": 205, "y": 60, "width": 165, "height": 40},
            },
            {
                "id": "mode-row",
                "browserNodeId": f"browser-boundary-{run_suffix}",
                "parentId": None,
                "flowScope": "main",
                "boundaryId": "mode-row",
                "rootSelector": None,
                "role": "group",
                "name": "模式控制列",
                "text": "",
                "state": {},
                "visible": True,
                "bounds": {"x": 20, "y": 60, "width": 350, "height": 40},
            },
        ],
        "stableState": {
            "view": "星雲圖",
            "labels": "核心",
            "decision": "fixture-stable",
        },
        "providerCounters": {"fixture.graph.load": 1},
        "mutatorCounters": {"fixture.graph.mutate": 0},
        "runtimeProjection": {
            "sourceRoot": f"{owned_root}/source",
            "browserScratchRoot": f"{owned_root}/browser",
        },
        "capturedAt": (
            "2026-07-17T00:00:01Z"
            if run_suffix == "b"
            else "2026-07-17T00:00:00Z"
        ),
        "runId": f"run-{run_suffix}",
    }


def _focused_control_evidence(identity_row: dict, *, accessible: bool) -> dict:
    by_case = {
        row["case"]: row["controls"]
        for row in evidence.focused_control_contract_rows()
    }
    controls = by_case[identity_row["case"]]
    viewport_width = int(identity_row["viewport"]["width"])
    viewport_height = int(identity_row["viewport"]["height"])
    root_width = viewport_width - 40
    rows = []
    for control in controls:
        options = list(control["optionLabels"])
        selected = control["selectedLabel"]
        replacement = control["replacementWidget"]
        widget = replacement if accessible else "segmented_control"
        target_labels = (
            [selected] if accessible and replacement == "selectbox" else options
        )
        target_width = root_width / len(target_labels)
        targets = [
            {
                "label": label,
                "x": round(20 + index * target_width, 3),
                "y": 64.0,
                "width": round(target_width, 3),
                "height": 24.0,
            }
            for index, label in enumerate(target_labels)
        ]
        selected_index = options.index(selected)
        if not accessible:
            semantics = {
                "role": "group",
                "optionRole": "button",
                "checkedLabels": [selected],
                "tabSequenceLabels": [],
                "afterArrowRight": None,
                "afterArrowLeft": None,
                "afterSpace": None,
                "afterArrowDown": None,
                "afterArrowUp": None,
                "selectionBasis": "segmented-buttons/one-active",
            }
        elif replacement == "radio_horizontal":
            semantics = {
                "role": "radiogroup",
                "optionRole": "radio",
                "checkedLabels": [selected],
                "tabSequenceLabels": [selected],
                "afterArrowRight": options[(selected_index + 1) % len(options)],
                "afterArrowLeft": selected,
                "afterSpace": selected,
                "afterArrowDown": None,
                "afterArrowUp": None,
                "selectionBasis": "native-radio/one-checked/roving-tabstop/keyboard",
            }
        else:
            semantics = {
                "role": "combobox",
                "optionRole": "option",
                "checkedLabels": [],
                "tabSequenceLabels": [],
                "afterArrowRight": None,
                "afterArrowLeft": None,
                "afterSpace": None,
                "afterArrowDown": options[1],
                "afterArrowUp": selected,
                "selectionBasis": "combobox/exact-option-order/keyboard/restore",
            }
        rows.append(
            {
                "sessionKey": control["sessionKey"],
                "rootSelector": control["rootSelector"],
                "widget": widget,
                "accessibleName": control["accessibleName"],
                "optionLabels": options,
                "auxiliaryButtons": list(control["auxiliaryButtons"]),
                "selectedLabel": selected,
                "targets": targets,
                "layout": {
                    "rootRect": {
                        "x": 20.0,
                        "y": 60.0,
                        "width": float(root_width),
                        "height": 40.0,
                    },
                    "viewportWidth": viewport_width,
                    "viewportHeight": viewport_height,
                    "targetOverlapTolerance": 0.5 if accessible else 1.0,
                    "documentClientWidth": viewport_width,
                    "documentScrollWidth": viewport_width,
                    "rootClientWidth": root_width,
                    "rootScrollWidth": root_width,
                    "rootClipping": False,
                    "targetClipping": False,
                    "targetOverlap": False,
                    "documentHorizontalOverflow": False,
                    "rootHorizontalOverflow": False,
                },
                **semantics,
            }
        )
    return {
        "schemaVersion": evidence.FOCUSED_CONTROL_EVIDENCE_SCHEMA,
        "case": identity_row["case"],
        "projection": (
            "accessible-required" if accessible else "legacy-segmented"
        ),
        "controls": rows,
    }


def _focused_control_evidence_v2(identity_row: dict) -> dict:
    value = _focused_control_evidence(identity_row, accessible=True)
    viewport = {
        "width": identity_row["viewport"]["width"],
        "height": identity_row["viewport"]["height"],
    }
    value["schemaVersion"] = evidence.FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA
    value["screenshotBinding"] = {
        "schemaVersion": evidence.FOCUSED_SCREENSHOT_BINDING_SCHEMA,
        "mode": "viewport",
        "viewport": viewport,
        "roots": [
            {
                "rootSelector": control["rootSelector"],
                "rect": copy.deepcopy(control["layout"]["rootRect"]),
            }
            for control in value["controls"]
        ],
        "scrollEntries": [
            {
                "rootSelector": control["rootSelector"],
                "chainIndex": 0,
                "left": 0.0,
                "top": 0.0,
                "clientWidth": float(viewport["width"]),
                "clientHeight": float(viewport["height"]),
                "scrollWidth": float(viewport["width"]),
                "scrollHeight": float(viewport["height"]),
            }
            for control in value["controls"]
        ],
        "prePostExact": True,
    }
    return value


def _focused_control_evidence_v3(
    identity_row: dict,
    *,
    root_selector: str,
) -> dict:
    value = _focused_control_evidence_v2(identity_row)
    value["schemaVersion"] = evidence.FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA
    value["controls"] = [
        control
        for control in value["controls"]
        if control["rootSelector"] == root_selector
    ]
    value["screenshotBinding"]["roots"] = [
        root
        for root in value["screenshotBinding"]["roots"]
        if root["rootSelector"] == root_selector
    ]
    value["screenshotBinding"]["scrollEntries"] = [
        entry
        for entry in value["screenshotBinding"]["scrollEntries"]
        if entry["rootSelector"] == root_selector
    ]
    return value


def test_worker_request_response_schema_is_exact_and_bounded() -> None:
    allowed_paths = frozenset((PNG_STAGE_PATH, SIDECAR_STAGE_PATH))
    maximum = evidence.MAX_WORKER_JSON_BYTES
    if not isinstance(maximum, int) or not 1024 <= maximum <= 4 * 1024 * 1024:
        raise AssertionError(f"unsafe worker JSON bound: {maximum!r}")

    request = _valid_worker_request()
    decoded_request = evidence.decode_worker_request(
        _json_line(request),
        expected_origin=APP_ORIGIN,
        allowed_staging_paths=allowed_paths,
    )
    if decoded_request != request:
        raise AssertionError(decoded_request)
    catalog_summary = evidence.worker_capture_catalog_summary()
    if catalog_summary.get("totalRows") != 120 or (
        catalog_summary.get("fullPageRows"),
        catalog_summary.get("focusedRows"),
        catalog_summary.get("themeRows"),
    ) != (81, 36, 3):
        raise AssertionError(catalog_summary)

    request_mutations: tuple[Callable[[dict], None], ...] = (
        lambda value: value.__setitem__("schemaVersion", "unknown/v9"),
        lambda value: value.pop("requestId"),
        lambda value: value.__setitem__("unexpected", True),
        lambda value: value.__setitem__("fixtureEntrypoint", "/tmp/fixture.py"),
        lambda value: value.__setitem__("fixtureEntrypoint", "../fixture.py"),
        lambda value: value.__setitem__(
            "fixtureEntrypoint", "scripts/ui_ux_fixture_app.py"
        ),
        lambda value: value.__setitem__("appOrigin", "http://127.0.0.1:43124"),
        lambda value: value.__setitem__(
            "appOrigin", f"http://user:secret@127.0.0.1:{APP_PORT}"
        ),
        lambda value: value["viewport"].__setitem__("width", True),
        lambda value: value["staging"].__setitem__(
            "png", "../final/manifest.json"
        ),
        lambda value: value["staging"].__setitem__(
            "renderSidecar", "/private/tmp/final/manifest.json"
        ),
        lambda value: (
            value.__setitem__("case", "invented-controls"),
            value.__setitem__("requestId", "invented-controls/mobile"),
            value.__setitem__("route", "/__selection__/invented"),
        ),
        lambda value: value["viewport"].__setitem__("height", 666),
        lambda value: value.__setitem__("route", "//knowledge-graph"),
        lambda value: value.__setitem__("route", "/a/../knowledge-graph"),
        lambda value: value.__setitem__("route", "/knowledge\\graph"),
        lambda value: value.__setitem__("route", "/knowledge-graph\n"),
    )
    for mutate in request_mutations:
        candidate = copy.deepcopy(request)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.decode_worker_request(
                _json_line(candidate),
                expected_origin=APP_ORIGIN,
                allowed_staging_paths=allowed_paths,
            ),
        )

    duplicate_key = _json_line(request).replace(
        f'"requestId":"{REQUEST_ID}"'.encode("utf-8"),
        (
            f'"requestId":"{REQUEST_ID}",'
            f'"requestId":"{REQUEST_ID}"'
        ).encode("utf-8"),
        1,
    )
    malformed_records = (
        _json_line(request).rstrip(b"\n"),
        _json_line(request) + _json_line(request),
        duplicate_key,
        b"{\"schemaVersion\":",
        b"x" * (maximum + 1),
    )
    for raw in malformed_records:
        _raises(
            evidence.EvidenceContractError,
            lambda raw=raw: evidence.decode_worker_request(
                raw,
                expected_origin=APP_ORIGIN,
                allowed_staging_paths=allowed_paths,
            ),
        )

    response = _valid_worker_response()
    decoded_response = evidence.decode_worker_response(
        _json_line(response),
        expected_request_id=REQUEST_ID,
        allowed_artifact_paths=allowed_paths,
    )
    if decoded_response != response:
        raise AssertionError(decoded_response)

    response_mutations: tuple[Callable[[dict], None], ...] = (
        lambda value: value.__setitem__("schemaVersion", "unknown/v9"),
        lambda value: value.pop("schemaVersion"),
        lambda value: value.pop("requestId"),
        lambda value: value.pop("status"),
        lambda value: value.__setitem__("requestId", "another/request"),
        lambda value: value.__setitem__("status", "passed"),
        lambda value: value.__setitem__("unexpected", True),
        lambda value: value["artifacts"].__setitem__(
            "png", "../final/manifest.json"
        ),
        lambda value: value["artifacts"].__setitem__(
            "renderSidecar", "manifest.json"
        ),
    )
    for mutate in response_mutations:
        candidate = copy.deepcopy(response)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.decode_worker_response(
                _json_line(candidate),
                expected_request_id=REQUEST_ID,
                allowed_artifact_paths=allowed_paths,
            ),
        )

    duplicate_response_key = _json_line(response).replace(
        f'"requestId":"{REQUEST_ID}"'.encode("utf-8"),
        (
            f'"requestId":"{REQUEST_ID}",'
            f'"requestId":"{REQUEST_ID}"'
        ).encode("utf-8"),
        1,
    )
    for raw in (
        _json_line(response).rstrip(b"\n"),
        _json_line(response) + _json_line(response),
        duplicate_response_key,
        b"x" * (maximum + 1),
    ):
        _raises(
            evidence.EvidenceContractError,
            lambda raw=raw: evidence.decode_worker_response(
                raw,
                expected_request_id=REQUEST_ID,
                allowed_artifact_paths=allowed_paths,
            ),
        )


def test_root_capture_expansion_and_v2_protocol_are_exact() -> None:
    rows = evidence.root_capture_expansion_rows()
    raw = evidence._canonical_json_bytes(rows)
    if (
        len(rows) != 44
        or len({row["logicalCaptureId"] for row in rows}) != 36
        or len({row["rootCaptureId"] for row in rows}) != 44
        or len(raw) != 16_576
        or _sha256(raw)
        != "13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca"
    ):
        raise AssertionError((len(rows), len(raw), _sha256(raw)))

    radar = [
        row
        for row in rows
        if row["logicalCaptureId"] == "radar-controls/mobile"
    ]
    if [row["rootOrdinal"] for row in radar] != [1, 2]:
        raise AssertionError(radar)
    root_outputs = []
    allowed: set[str] = set()
    for row in radar:
        base = (
            f'staging/{row["case"]}/{row["viewport"]["name"]}/'
            f'root-{row["rootOrdinal"]:02d}'
        )
        staging = {
            "png": f"{base}/capture.png",
            "renderSidecar": f"{base}/render.json",
        }
        allowed.update(staging.values())
        root_outputs.append(
            {
                "rootCaptureId": row["rootCaptureId"],
                "rootOrdinal": row["rootOrdinal"],
                "rootSelector": row["rootSelector"],
                "staging": staging,
            }
        )
    request = {
        "schemaVersion": evidence.WORKER_REQUEST_V2_SCHEMA,
        "requestId": "radar-controls/mobile",
        "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
        "case": "radar-controls",
        "route": "/__selection__/radar",
        "viewport": {"name": "mobile", "width": 390, "height": 844},
        "appOrigin": APP_ORIGIN,
        "rootOutputs": root_outputs,
    }
    if evidence.decode_worker_request(
        _json_line(request),
        expected_origin=APP_ORIGIN,
        allowed_staging_paths=frozenset(allowed),
    ) != request:
        raise AssertionError("v2 request did not round-trip")

    response = {
        "schemaVersion": evidence.WORKER_RESPONSE_V2_SCHEMA,
        "requestId": request["requestId"],
        "status": "staged",
        "rootArtifacts": [
            {
                "rootCaptureId": row["rootCaptureId"],
                "logicalCaptureId": row["logicalCaptureId"],
                "rootOrdinal": row["rootOrdinal"],
                "rootSelector": row["rootSelector"],
                "png": output["staging"]["png"],
                "renderSidecar": output["staging"]["renderSidecar"],
            }
            for row, output in zip(radar, root_outputs, strict=True)
        ],
    }
    if evidence.decode_worker_response(
        _json_line(response),
        expected_request_id=request["requestId"],
        allowed_artifact_paths=frozenset(allowed),
    ) != response:
        raise AssertionError("v2 response did not round-trip")

    for mutation in (
        lambda value: value["rootOutputs"].reverse(),
        lambda value: value["rootOutputs"][0].__setitem__(
            "rootSelector", ".st-key-radar_view"
        ),
        lambda value: value["rootOutputs"].pop(),
        lambda value: value["rootOutputs"][1]["staging"].__setitem__(
            "png", value["rootOutputs"][0]["staging"]["png"]
        ),
    ):
        candidate = copy.deepcopy(request)
        mutation(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.decode_worker_request(
                _json_line(candidate),
                expected_origin=APP_ORIGIN,
                allowed_staging_paths=frozenset(allowed),
            ),
        )

    command = evidence.build_browser_worker_command(
        sys.executable,
        "scripts/ui_ux_browser_worker.py",
        expected_origin=APP_ORIGIN,
        expected_request_id=request["requestId"],
        allowed_staging_paths=tuple(allowed),
    )
    if command.count("--allow-staging-path") != 4:
        raise AssertionError(command)


def test_coordinator_copy_cannot_replace_final_outputs() -> None:
    for destination_kind in ("regular", "symlink", "hardlink"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            output = Path(temp) / "final"
            root.mkdir()
            output.mkdir()
            _write(root / "stage" / "capture.bin", b"authenticated")
            sentinel = _write(output / "sentinel.bin", b"FINAL-MUST-NOT-CHANGE")
            destination = output / "accepted.bin"
            if destination_kind == "regular":
                destination.write_bytes(b"EXISTING-FINAL")
            elif destination_kind == "symlink":
                destination.symlink_to(sentinel.name)
            else:
                os.link(sentinel, destination)
            before_sentinel = sentinel.read_bytes()
            before_destination = os.lstat(destination)
            run_fd = _root_fd(root)
            out_fd = _root_fd(output)
            try:
                contract = evidence.freeze_artifact_contract(
                    run_fd, "stage/capture.bin", expected_owner=OWNER
                )
                with evidence.open_authenticated_artifact(run_fd, contract) as artifact:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: evidence.copy_authenticated_artifact(
                            artifact, out_fd, "accepted.bin"
                        ),
                    )
            finally:
                os.close(out_fd)
                os.close(run_fd)
            if sentinel.read_bytes() != before_sentinel:
                raise AssertionError("existing final sentinel was modified")
            after_destination = os.lstat(destination)
            if (after_destination.st_dev, after_destination.st_ino) != (
                before_destination.st_dev,
                before_destination.st_ino,
            ):
                raise AssertionError("existing final destination was replaced")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "run"
        output = Path(temp) / "final"
        root.mkdir()
        output.mkdir()
        _write(root / "stage" / "capture.bin", b"authenticated")
        run_fd = _root_fd(root)
        out_fd = _root_fd(output)
        try:
            contract = evidence.freeze_artifact_contract(
                run_fd, "stage/capture.bin", expected_owner=OWNER
            )
            with evidence.open_authenticated_artifact(run_fd, contract) as artifact:
                for unsafe in (
                    "../escape.bin",
                    "nested/../../escape.bin",
                    str(Path(temp) / "absolute-escape.bin"),
                ):
                    _raises(
                        evidence.EvidenceContractError,
                        lambda unsafe=unsafe: evidence.copy_authenticated_artifact(
                            artifact, out_fd, unsafe
                        ),
                    )
        finally:
            os.close(out_fd)
            os.close(run_fd)
        if (Path(temp) / "escape.bin").exists() or (
            Path(temp) / "absolute-escape.bin"
        ).exists():
            raise AssertionError("unsafe final output escaped the coordinator root")


def test_component_walk_rejects_unsafe_paths_and_symlinks() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write(root / "stage" / "nested" / "capture.bin", b"safe")
        os.symlink("capture.bin", root / "stage" / "nested" / "leaf-link")
        os.symlink("nested", root / "stage" / "dir-link")
        fd = _root_fd(root)
        try:
            for relative in (
                "",
                "/capture.bin",
                "../capture.bin",
                "stage/../capture.bin",
                "stage/./capture.bin",
                "stage//capture.bin",
                "stage/nested/",
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda relative=relative: evidence.freeze_artifact_contract(
                        fd, relative, expected_owner=OWNER
                    ),
                )
            for relative in ("stage/nested/leaf-link", "stage/dir-link/capture.bin"):
                _raises(
                    evidence.EvidenceContractError,
                    lambda relative=relative: evidence.freeze_artifact_contract(
                        fd, relative, expected_owner=OWNER
                    ),
                )
        finally:
            os.close(fd)


def test_component_walk_rejects_ancestor_leaf_and_mode_swaps() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write(root / "stage" / "nested" / "capture.bin", b"safe")
        fd = _root_fd(root)
        try:
            contract = evidence.freeze_artifact_contract(
                fd, "stage/nested/capture.bin", expected_owner=OWNER
            )
            original_stage = (root / "stage").stat(follow_symlinks=False)
            stage_mode = original_stage.st_mode & 0o777
            nested_mode = (root / "stage" / "nested").stat(
                follow_symlinks=False
            ).st_mode & 0o777
            leaf_mode = (root / "stage" / "nested" / "capture.bin").stat(
                follow_symlinks=False
            ).st_mode & 0o777
            (root / "stage").rename(root / "stage-old")
            replacement = _write(
                root / "stage" / "nested" / "capture.bin", b"safe"
            )
            os.chmod(root / "stage", stage_mode)
            os.chmod(root / "stage" / "nested", nested_mode)
            os.chmod(replacement, leaf_mode)
            replacement_stage = (root / "stage").stat(follow_symlinks=False)
            if replacement_stage.st_ino == original_stage.st_ino:
                raise AssertionError("ancestor-swap fixture reused the original inode")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.open_authenticated_artifact(fd, contract),
            )
        finally:
            os.close(fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        leaf = _write(root / "stage" / "capture.bin", b"safe")
        fd = _root_fd(root)
        try:
            contract = evidence.freeze_artifact_contract(
                fd, "stage/capture.bin", expected_owner=OWNER
            )
            original_leaf = leaf.stat(follow_symlinks=False)
            leaf_mode = original_leaf.st_mode & 0o777
            leaf.rename(root / "stage" / "old.bin")
            replacement = _write(root / "stage" / "capture.bin", b"safe")
            os.chmod(replacement, leaf_mode)
            replacement_leaf = replacement.stat(follow_symlinks=False)
            if replacement_leaf.st_ino == original_leaf.st_ino:
                raise AssertionError("leaf-swap fixture reused the original inode")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.open_authenticated_artifact(fd, contract),
            )
        finally:
            os.close(fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write(root / "stage" / "capture.bin", b"safe")
        fd = _root_fd(root)
        try:
            contract = evidence.freeze_artifact_contract(
                fd, "stage/capture.bin", expected_owner=OWNER
            )
            stage = root / "stage"
            original_mode = stage.stat().st_mode & 0o777
            changed_mode = original_mode ^ 0o040
            if changed_mode == original_mode:
                raise AssertionError("mode-swap fixture did not change mode")
            os.chmod(stage, changed_mode)
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.open_authenticated_artifact(fd, contract),
            )
        finally:
            os.close(fd)


def test_leaf_must_be_owned_one_link_regular_file() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        regular = _write(root / "regular.bin", b"safe")
        os.link(regular, root / "hard-link.bin")
        (root / "directory-leaf").mkdir()
        os.mkfifo(root / "fifo-leaf")
        fd = _root_fd(root)
        try:
            for relative in ("regular.bin", "directory-leaf", "fifo-leaf"):
                _raises(
                    evidence.EvidenceContractError,
                    lambda relative=relative: evidence.freeze_artifact_contract(
                        fd, relative, expected_owner=OWNER
                    ),
                )
            _write(root / "owned.bin", b"safe")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.freeze_artifact_contract(
                    fd, "owned.bin", expected_owner=OWNER + 1
                ),
            )
        finally:
            os.close(fd)


def test_copy_uses_authenticated_fd_and_rechecks_that_inode() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "run"
        output = Path(temp) / "final"
        root.mkdir()
        output.mkdir()
        leaf = _write(root / "stage" / "capture.bin", b"alpha")
        run_fd = _root_fd(root)
        out_fd = _root_fd(output)
        try:
            contract = evidence.freeze_artifact_contract(
                run_fd, "stage/capture.bin", expected_owner=OWNER
            )
            with evidence.open_authenticated_artifact(run_fd, contract) as artifact:
                leaf.rename(root / "stage" / "original.bin")
                leaf.write_bytes(b"evil!")
                record = evidence.copy_authenticated_artifact(
                    artifact, out_fd, "accepted.bin"
                )
            if (output / "accepted.bin").read_bytes() != b"alpha":
                raise AssertionError("copy followed a replacement pathname")
            if record["sha256"] != _sha256(b"alpha") or record["size"] != 5:
                raise AssertionError(record)
        finally:
            os.close(out_fd)
            os.close(run_fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "run"
        output = Path(temp) / "final"
        root.mkdir()
        output.mkdir()
        leaf = _write(root / "stage" / "capture.bin", b"alpha")
        run_fd = _root_fd(root)
        out_fd = _root_fd(output)
        try:
            contract = evidence.freeze_artifact_contract(
                run_fd, "stage/capture.bin", expected_owner=OWNER
            )
            with evidence.open_authenticated_artifact(run_fd, contract) as artifact:
                leaf.write_bytes(b"bravo")
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.copy_authenticated_artifact(
                        artifact, out_fd, "rejected.bin"
                    ),
                )
            if (output / "rejected.bin").exists():
                raise AssertionError("mutated artifact left an accepted copy")
        finally:
            os.close(out_fd)
            os.close(run_fd)


def _new_lifecycle(directory: Path, *, mode: str = "ux1b-full-pages"):
    fd = _root_fd(directory)
    lifecycle = evidence.ManifestLifecycle(
        fd,
        "manifest.json",
        base_document={
            "schemaVersion": "quant-radar-ui-ux-evidence/v1",
            "mode": mode,
            "runId": "run-1",
        },
    )
    return fd, lifecycle


def test_manifest_passed_is_final_only_and_terminal_is_immutable() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        capture_root = root / "capture"
        capture_root.mkdir()
        fixture_entrypoint = "scripts/ui_ux_theme_fixture_app.py"
        fd, lifecycle = _new_lifecycle(root, mode="ux1b-theme")
        try:
            authenticated_captures = _verified_profile_captures(
                capture_root,
                fixture_entrypoint=fixture_entrypoint,
                run_root_fd=fd,
            )
            process_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )
            lifecycle.start()
            if _read_json(root / "manifest.json")["status"] != "running":
                raise AssertionError("initial status is not running")
            running_inode = (root / "manifest.json").stat(
                follow_symlinks=False
            ).st_ino
            _raises(
                evidence.EvidenceContractError,
                lambda: lifecycle.mark_terminal("passed", {"readyForPassed": True}),
            )
            if _read_json(root / "manifest.json")["status"] != "running":
                raise AssertionError("early passed changed the manifest")
            lifecycle.mark_finalizing({"childrenQuiescent": True})
            if _read_json(root / "manifest.json")["status"] != "finalizing":
                raise AssertionError("finalization was not checkpointed")
            finalizing_inode = (root / "manifest.json").stat(
                follow_symlinks=False
            ).st_ino
            if finalizing_inode == running_inode:
                raise AssertionError("manifest checkpoint was rewritten in place")
            bypass_before = (root / "manifest.json").read_bytes()
            if "_FINALIZER_TOKEN" in vars(evidence):
                raise AssertionError("module-global passed bearer still exists")
            if "_finalizer_token" in inspect.signature(
                evidence.ManifestLifecycle._transition
            ).parameters:
                raise AssertionError("passed bearer remains in the transition API")
            _raises(
                evidence.EvidenceContractError,
                lambda: lifecycle._transition("passed", {"forged": True}),
            )
            if (root / "manifest.json").read_bytes() != bypass_before:
                raise AssertionError("private transition bypass mutated the manifest")
            _raises(
                evidence.EvidenceContractError,
                lambda: lifecycle.mark_terminal("passed", {"readyForPassed": True}),
            )
            calibration_attestation, comparator_attestation = (
                _mint_operational_attestations()
            )
            closure_document = _valid_success_closure(
                authenticated_captures, process_proofs
            )
            closure_document["network"] = _LineInterleavingNetwork()
            closure = evidence.validate_success_closure(
                closure_document,
                lifecycle=lifecycle,
                expected_fixture_entrypoint=fixture_entrypoint,
                expected_capture_stack_digest=_complete_control_catalog()[
                    "captureStackDigest"
                ],
                expected_source_digest=SOURCE_DIGEST,
                expected_app_origin=APP_ORIGIN,
                calibration_attestation=calibration_attestation,
                comparator_attestation=comparator_attestation,
            )
            if not isinstance(closure, evidence.ValidatedSuccessClosure):
                raise AssertionError(type(closure).__name__)
            other_root = root / "other-lifecycle"
            other_root.mkdir()
            other_fd, other_lifecycle = _new_lifecycle(
                other_root, mode="ux1b-theme"
            )
            try:
                other_lifecycle.start()
                other_lifecycle.mark_finalizing({"childrenQuiescent": True})
                other_before = (other_root / "manifest.json").read_bytes()
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.authorize_success_closure(
                        other_lifecycle,
                        validated_closure=closure,
                    ),
                )
                if (other_root / "manifest.json").read_bytes() != other_before:
                    raise AssertionError("cross-run closure mutated another manifest")
                grant = evidence.authorize_success_closure(
                    lifecycle,
                    validated_closure=closure,
                )
                if not isinstance(grant, evidence.SuccessFinalizationGrant):
                    raise AssertionError(type(grant).__name__)
                preview_checkpoint = (root / "manifest.json").read_bytes()
                preview_one = evidence.materialize_authorized_terminal_manifest(
                    lifecycle,
                    grant=grant,
                )
                preview_two = evidence.materialize_authorized_terminal_manifest(
                    lifecycle,
                    grant=grant,
                )
                if (
                    preview_one != preview_two
                    or preview_one is preview_two
                    or preview_one.get("status") != "passed"
                    or lifecycle.state != "finalizing"
                    or (root / "manifest.json").read_bytes() != preview_checkpoint
                ):
                    raise AssertionError("authorized terminal preview mutated authority")
                preview_one["network"]["appPort"] = APP_PORT + 1
                if evidence.materialize_authorized_terminal_manifest(
                    lifecycle,
                    grant=grant,
                ) != preview_two:
                    raise AssertionError("terminal preview exposed its stored snapshot")
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.materialize_authorized_terminal_manifest(
                        lifecycle,
                        grant={"readyForPassed": True},
                    ),
                )
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.materialize_authorized_terminal_manifest(
                        other_lifecycle,
                        grant=grant,
                    ),
                )
                if (other_root / "manifest.json").read_bytes() != other_before:
                    raise AssertionError("cross-run preview mutated another manifest")
                _raises(
                    AttributeError,
                    lambda: setattr(lifecycle, "manifest_name", "redirect.json"),
                )
                _raises(
                    AttributeError,
                    lambda: setattr(
                        lifecycle,
                        "output_dir_fd",
                        other_lifecycle._output_dir_fd,
                    ),
                )
                original_manifest_name = lifecycle._manifest_name
                lifecycle._manifest_name = "redirect.json"
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.finalize_terminal_manifest(
                        lifecycle,
                        grant=grant,
                    ),
                )
                lifecycle._manifest_name = original_manifest_name
                if (root / "redirect.json").exists():
                    raise AssertionError("mutable manifest name redirected pass output")
                original_output_descriptor = lifecycle._output_dir_fd
                lifecycle._output_dir_fd = other_lifecycle._output_dir_fd
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.finalize_terminal_manifest(
                        lifecycle,
                        grant=grant,
                    ),
                )
                lifecycle._output_dir_fd = original_output_descriptor
                original_manifest_contract = lifecycle._contract
                lifecycle._contract = other_lifecycle._contract
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.finalize_terminal_manifest(
                        lifecycle,
                        grant=grant,
                    ),
                )
                lifecycle._contract = original_manifest_contract
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.finalize_terminal_manifest(
                        lifecycle,
                        grant={"readyForPassed": True},
                    ),
                )
                try:
                    copied_grant = copy.copy(grant)
                except (TypeError, evidence.EvidenceContractError):
                    copied_grant = None
                if copied_grant is grant:
                    raise AssertionError(
                        "finalization grant copy returned original object"
                    )
                if copied_grant is not None:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: evidence.finalize_terminal_manifest(
                            lifecycle,
                            grant=copied_grant,
                        ),
                    )
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.finalize_terminal_manifest(
                        other_lifecycle,
                        grant=grant,
                    ),
                )
                if (other_root / "manifest.json").read_bytes() != other_before:
                    raise AssertionError("wrong-lifecycle grant mutated another manifest")
            finally:
                os.close(other_fd)
            evidence.finalize_terminal_manifest(
                lifecycle,
                grant=grant,
            )
            passed = (root / "manifest.json").read_bytes()
            if json.loads(passed)["status"] != "passed":
                raise AssertionError("final status is not passed")
            if json.loads(passed).get("network") != {
                "appOrigin": APP_ORIGIN,
                "appPort": APP_PORT,
            }:
                raise AssertionError("passed manifest reread the mutable network mapping")
            passed_stat = (root / "manifest.json").stat(follow_symlinks=False)
            if passed_stat.st_ino == finalizing_inode or passed_stat.st_nlink != 1:
                raise AssertionError("terminal manifest was not atomically replaced")
            _raises(
                evidence.EvidenceContractError,
                lambda: lifecycle.mark_terminal("failed", {"error": "late"}),
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.finalize_terminal_manifest(
                    lifecycle,
                    grant=grant,
                ),
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.materialize_authorized_terminal_manifest(
                    lifecycle,
                    grant=grant,
                ),
            )
            if (root / "manifest.json").read_bytes() != passed:
                raise AssertionError("terminal manifest was rewritten after grant reuse")
        finally:
            os.close(fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        external_fd, lifecycle = _new_lifecycle(root)
        os.close(external_fd)
        lifecycle.start()
        lifecycle.mark_terminal("failed", {"reason": "owned-descriptor-check"})
        if _read_json(root / "manifest.json")["status"] != "failed":
            raise AssertionError("lifecycle did not retain its own output descriptor")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fd, lifecycle = _new_lifecycle(root)
        original_fsync = evidence.os.fsync

        def fail_start_directory_fsync(descriptor: int) -> None:
            if descriptor == lifecycle._output_dir_fd:
                raise OSError(5, "injected start directory fsync failure")
            original_fsync(descriptor)

        try:
            with mock.patch.object(
                evidence.os,
                "fsync",
                side_effect=fail_start_directory_fsync,
            ):
                _raises(evidence.ManifestDurabilityUncertain, lifecycle.start)
            if (
                lifecycle.state != "running"
                or _read_json(root / "manifest.json")["status"] != "running"
            ):
                raise AssertionError("start fsync failure split manifest state")
            lifecycle.mark_terminal("failed", {"reason": "start-fsync-uncertain"})
        finally:
            os.close(fd)

    fixture_entrypoint = "scripts/ui_ux_theme_fixture_app.py"
    for mutation in (
        "bytes",
        "inode",
        "supplement-bytes",
        "supplement-inode",
        "supplement-symlink",
        "supplement-ancestor",
        "late-inode",
        "durability",
    ):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture_root = root / "captures"
            capture_root.mkdir()
            fd, lifecycle = _new_lifecycle(root, mode="ux1b-theme")
            try:
                authenticated_captures = _verified_profile_captures(
                    capture_root,
                    fixture_entrypoint=fixture_entrypoint,
                    run_root_fd=fd,
                )
                partial_artifact_payloads = [
                    copy.deepcopy(dict(capture))
                    for capture in authenticated_captures.values()
                ]
                process_proofs = _quiescent_profile_processes(
                    fixture_entrypoint=fixture_entrypoint
                )
                lifecycle.start()
                lifecycle.mark_finalizing({"childrenQuiescent": True})
                calibration, comparator = _mint_operational_attestations()
                closure = evidence.validate_success_closure(
                    _valid_success_closure(
                        authenticated_captures,
                        process_proofs,
                    ),
                    lifecycle=lifecycle,
                    expected_fixture_entrypoint=fixture_entrypoint,
                    expected_capture_stack_digest=_complete_control_catalog()[
                        "captureStackDigest"
                    ],
                    expected_source_digest=SOURCE_DIGEST,
                    expected_app_origin=APP_ORIGIN,
                    calibration_attestation=calibration,
                    comparator_attestation=comparator,
                )
                grant = evidence.authorize_success_closure(
                    lifecycle,
                    validated_closure=closure,
                )
                target = capture_root / "0" / "capture.png"
                supplement = capture_root / "0" / "canvas.png"
                if mutation == "bytes":
                    target.write_bytes(PNG_1X1[:-1] + b"X")
                elif mutation == "inode":
                    prior = target.with_name("capture.prior.png")
                    target.rename(prior)
                    target.write_bytes(PNG_1X1)
                elif mutation == "supplement-bytes":
                    raw = supplement.read_bytes()
                    supplement.write_bytes(raw[:-1] + bytes((raw[-1] ^ 1,)))
                elif mutation == "supplement-inode":
                    raw = supplement.read_bytes()
                    supplement.rename(supplement.with_name("canvas.prior.png"))
                    supplement.write_bytes(raw)
                elif mutation == "supplement-symlink":
                    prior = supplement.with_name("canvas.prior.png")
                    supplement.rename(prior)
                    supplement.symlink_to(prior.name)
                elif mutation == "supplement-ancestor":
                    capture_directory = capture_root / "0"
                    capture_directory.rename(capture_root / "0-prior")
                    capture_directory.mkdir()
                before = (root / "manifest.json").read_bytes()
                if mutation == "durability":
                    original_fsync = evidence.os.fsync

                    def fail_directory_fsync(descriptor: int) -> None:
                        if descriptor == lifecycle._output_dir_fd:
                            raise OSError(5, "injected directory fsync failure")
                        original_fsync(descriptor)

                    with mock.patch.object(
                        evidence.os,
                        "fsync",
                        side_effect=fail_directory_fsync,
                    ):
                        _raises(
                            evidence.ManifestDurabilityUncertain,
                            lambda: evidence.finalize_terminal_manifest(
                                lifecycle,
                                grant=grant,
                            ),
                        )
                    if (
                        _read_json(root / "manifest.json")["status"] != "passed"
                        or lifecycle.state != "passed"
                        or id(grant) in evidence._SUCCESS_GRANTS
                        or any(
                            id(capture) in evidence._VERIFIED_CAPTURES
                            for capture in authenticated_captures.values()
                        )
                    ):
                        raise AssertionError(
                            "post-publication fsync failure split manifest state"
                        )
                    continue
                if mutation == "late-inode":
                    original_rehash = evidence._rehash_retained_artifact
                    rehash_calls = 0
                    expected_calls = 1 + sum(
                        2
                        + len(
                            capture.get("supplementalArtifacts", ())
                        )
                        for capture in authenticated_captures.values()
                    )

                    def rehash_then_swap(artifact: object) -> None:
                        nonlocal rehash_calls
                        original_rehash(artifact)
                        rehash_calls += 1
                        if rehash_calls == expected_calls:
                            target.rename(
                                target.with_name("capture.late.prior.png")
                            )
                            target.write_bytes(b"forged-after-final-rehash")

                    with mock.patch.object(
                        evidence,
                        "_rehash_retained_artifact",
                        side_effect=rehash_then_swap,
                    ):
                        _raises(
                            evidence.EvidenceContractError,
                            lambda: evidence.finalize_terminal_manifest(
                                lifecycle,
                                grant=grant,
                            ),
                        )
                    if rehash_calls != expected_calls:
                        raise AssertionError(
                            "late inode swap did not run after the last retained hash"
                        )
                else:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: evidence.finalize_terminal_manifest(
                            lifecycle,
                            grant=grant,
                        ),
                    )
                if (
                    (root / "manifest.json").read_bytes() != before
                    or _read_json(root / "manifest.json")["status"]
                    != "finalizing"
                ):
                    raise AssertionError(
                        f"{mutation} mutation published a passed manifest"
                    )
                if id(grant) in evidence._SUCCESS_GRANTS or any(
                    id(capture) in evidence._VERIFIED_CAPTURES
                    for capture in authenticated_captures.values()
                ):
                    raise AssertionError(
                        "failed capture reauthentication retained finalization authority"
                    )
                if mutation == "bytes":
                    lifecycle.mark_terminal(
                        "invalid_data",
                        {
                            "reason": "capture-bytes-changed",
                            "partialArtifacts": partial_artifact_payloads,
                        },
                    )
                    terminal_raw = (root / "manifest.json").read_bytes()
                    partial_artifact_payloads[0]["png"]["path"] = (
                        "mutated-after-terminalization.png"
                    )
                    if (root / "manifest.json").read_bytes() != terminal_raw:
                        raise AssertionError(
                            "terminal partial artifact payload remained caller-owned"
                        )
                    terminal_text = terminal_raw.decode("utf-8")
                    if any(
                        forbidden in terminal_text
                        for forbidden in (
                            str(root),
                            "authorityToken",
                            "descriptor",
                            "mutated-after-terminalization.png",
                        )
                    ):
                        raise AssertionError(
                            "terminal partial artifacts exposed private provenance"
                        )
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: lifecycle.mark_terminal(
                            "failed", {"reason": "second-terminal"}
                        ),
                    )
                else:
                    lifecycle.mark_terminal(
                        "invalid_data",
                        {"reason": f"capture-{mutation}-changed"},
                    )
            finally:
                os.close(fd)


def test_full_page_finalizer_succeeds_under_256_fd_soft_limit() -> None:
    fixture_entrypoint = "scripts/ui_ux_fixture_app.py"
    stack_digest = _complete_control_catalog()["captureStackDigest"]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        capture_root = root / "captures"
        capture_root.mkdir()
        fd, lifecycle = _new_lifecycle(root)
        authenticated_captures: dict[str, object] = {}
        original_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        limit_changed = False
        try:
            authenticated_captures = _verified_profile_captures(
                capture_root,
                fixture_entrypoint=fixture_entrypoint,
                run_root_fd=fd,
            )
            if len(authenticated_captures) != 81:
                raise AssertionError("full-page FD regression lacks 81 captures")
            process_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )
            lifecycle.start()
            lifecycle.mark_finalizing(
                {"childrenQuiescent": True, "capturedCount": 81}
            )

            calibration_report = {
                "schemaVersion": "quant-radar-ui-ux-isolation-calibration/v1",
                "passed": True,
                "profileSha256": "a" * 64,
            }
            with mock.patch.object(
                evidence.isolation,
                "validate_live_calibration_provenance",
                autospec=True,
                return_value="a" * 64,
            ):
                calibration = evidence.mint_calibration_attestation(
                    calibration_report
                )
            comparator = evidence.mint_comparator_attestation(
                evidence.validate_live_capture_profile(
                    tuple(authenticated_captures.values()),
                    fixture_entrypoint=fixture_entrypoint,
                    capture_stack_digest=stack_digest,
                )
            )
            closure = evidence.validate_success_closure(
                _valid_success_closure(authenticated_captures, process_proofs),
                lifecycle=lifecycle,
                expected_fixture_entrypoint=fixture_entrypoint,
                expected_capture_stack_digest=stack_digest,
                expected_source_digest=SOURCE_DIGEST,
                expected_app_origin=APP_ORIGIN,
                calibration_attestation=calibration,
                comparator_attestation=comparator,
            )
            grant = evidence.authorize_success_closure(
                lifecycle,
                validated_closure=closure,
            )

            expected_retained_leaves = 1 + 81 * 2
            original_open = evidence.open_authenticated_artifact
            original_close = evidence.AuthenticatedArtifact.close
            live_artifacts: set[int] = set()
            open_calls = 0
            peak_live = 0

            def tracked_open(root_fd, contract):
                nonlocal open_calls, peak_live
                artifact = original_open(root_fd, contract)
                open_calls += 1
                live_artifacts.add(id(artifact))
                peak_live = max(peak_live, len(live_artifacts))
                return artifact

            def tracked_close(artifact) -> None:
                try:
                    original_close(artifact)
                finally:
                    live_artifacts.discard(id(artifact))

            hard_limit = original_limit[1]
            if hard_limit != resource.RLIM_INFINITY and hard_limit < 256:
                raise AssertionError("process hard FD limit is below 256")
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (256, hard_limit),
            )
            limit_changed = True
            try:
                with (
                    mock.patch.object(
                        evidence,
                        "open_authenticated_artifact",
                        side_effect=tracked_open,
                    ),
                    mock.patch.object(
                        evidence.AuthenticatedArtifact,
                        "close",
                        new=tracked_close,
                    ),
                ):
                    passed = evidence.finalize_terminal_manifest(
                        lifecycle,
                        grant=grant,
                    )
            finally:
                resource.setrlimit(resource.RLIMIT_NOFILE, original_limit)
                limit_changed = False

            if passed.get("status") != "passed" or len(passed["captures"]) != 81:
                raise AssertionError("full-page finalizer did not publish 81 captures")
            # One manifest open validates the grant-bound finalizing checkpoint;
            # the two exact leaf sets are the retained and current-path passes.
            expected_open_calls = 1 + expected_retained_leaves * 2
            if open_calls != expected_open_calls:
                raise AssertionError(
                    f"finalizer opened {open_calls} leaves instead of "
                    f"{expected_open_calls}"
                )
            if peak_live > expected_retained_leaves + 1 or live_artifacts:
                raise AssertionError(
                    f"finalizer retained an unbounded second set: peak={peak_live}, "
                    f"live={len(live_artifacts)}"
                )
            if id(grant) in evidence._SUCCESS_GRANTS or any(
                id(capture) in evidence._VERIFIED_CAPTURES
                for capture in authenticated_captures.values()
            ):
                raise AssertionError("successful finalization retained authority")
        finally:
            if limit_changed:
                resource.setrlimit(resource.RLIMIT_NOFILE, original_limit)
            if lifecycle.state in {"running", "finalizing"}:
                lifecycle.mark_terminal(
                    "failed", {"reason": "fd-regression-cleanup"}
                )
            for capture in authenticated_captures.values():
                try:
                    capture.close()
                except evidence.EvidenceContractError:
                    pass
            os.close(fd)


def test_root_capture_lifecycle_is_exact_36_44_88_89() -> None:
    fixture_entrypoint = "scripts/ui_ux_selection_fixture_app.py"
    stack_digest = _complete_control_catalog()["captureStackDigest"]
    identity_by_logical = {
        f'{row["case"]}/{row["viewport"]["name"]}': row
        for row in evidence.worker_capture_profile_rows(
            fixture_entrypoint
        )
    }
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fd = _root_fd(root)
        lifecycle = evidence.ManifestLifecycle(
            fd,
            "manifest.json",
            base_document={
                "schemaVersion": evidence.EVIDENCE_SCHEMA,
                "mode": "ux1b-selection-controls",
                "phase": "postcontrol",
                "runId": "run-1",
                "fixtureEntrypoint": fixture_entrypoint,
                "expectedCaptureCount": 44,
                "plannedLogicalRequests": 36,
                "plannedRootCaptures": 44,
                "completedLogicalRequests": 0,
                "completedRootCaptures": 0,
                "rootExpansionSha256": (
                    evidence.ROOT_CAPTURE_EXPANSION_SHA256
                ),
            },
        )
        captures: dict[str, object] = {}
        raw_root_sidecars: list[object] = []
        try:
            captures = _verified_root_profile_captures(
                root,
                run_root_fd=fd,
                raw_sidecars=raw_root_sidecars,
            )
            if len(captures) != 44:
                raise AssertionError(len(captures))
            logical_discovery = (
                evidence.adapt_root_raw_sidecars_for_control_discovery(
                    raw_root_sidecars
                )
            )
            if len(logical_discovery) != 36:
                raise AssertionError(len(logical_discovery))
            observed_logical_ids = {
                (
                    payload["identityRow"]["case"]
                    + "/"
                    + payload["identityRow"]["viewport"]["name"]
                )
                for payload in (
                    evidence._registered_raw_sidecar_payload(sidecar)
                    for sidecar in logical_discovery
                )
            }
            if observed_logical_ids != set(identity_by_logical):
                raise AssertionError(observed_logical_ids)
            semantic_by_logical: dict[str, bytes] = {}
            logical_provider_counts: dict[str, int] = {}
            for root_row in evidence.root_capture_expansion_rows():
                render_path = (
                    root
                    / "captures"
                    / root_row["rootCaptureId"]
                    / "render.json"
                )
                document = json.loads(render_path.read_bytes())
                semantic_raw = evidence._canonical_json_bytes(
                    document["caseSemanticProjection"]
                )
                logical_id = root_row["logicalCaptureId"]
                prior = semantic_by_logical.setdefault(
                    logical_id,
                    semantic_raw,
                )
                if prior != semantic_raw:
                    raise AssertionError(
                        "final sibling semantic projections differ"
                    )
                logical_provider_counts.setdefault(
                    logical_id,
                    document["providerCounters"]["fixture.graph.load"],
                )
                if (
                    document["counterProvenance"]["captureId"]
                    != logical_id
                    or document["caseSemanticProjection"][
                        "counterProvenance"
                    ]
                    != document["counterProvenance"]
                ):
                    raise AssertionError(
                        "root sidecar counter provenance differs"
                    )
            if (
                len(semantic_by_logical) != 36
                or sum(logical_provider_counts.values()) != 36
            ):
                raise AssertionError(
                    (len(semantic_by_logical), logical_provider_counts)
                )

            process_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )
            lifecycle.start()
            lifecycle.mark_finalizing(
                {
                    "childrenQuiescent": True,
                    "capturedCount": 44,
                    "completedLogicalRequests": 36,
                    "completedRootCaptures": 44,
                }
            )
            calibration_report = {
                "schemaVersion": (
                    "quant-radar-ui-ux-isolation-calibration/v1"
                ),
                "passed": True,
                "profileSha256": "a" * 64,
            }
            with mock.patch.object(
                evidence.isolation,
                "validate_live_calibration_provenance",
                autospec=True,
                return_value="a" * 64,
            ):
                calibration = evidence.mint_calibration_attestation(
                    calibration_report
                )
            comparator_report = evidence.validate_live_capture_profile(
                tuple(captures.values()),
                fixture_entrypoint=fixture_entrypoint,
                capture_stack_digest=stack_digest,
            )
            if (
                comparator_report["kind"]
                != "live-root-capture-profile"
                or comparator_report["captureCount"] != 44
                or comparator_report["logicalCaptureCount"] != 36
            ):
                raise AssertionError(comparator_report)
            comparator = evidence.mint_comparator_attestation(
                comparator_report
            )
            closure_document = _valid_success_closure(
                captures,
                process_proofs,
            )
            closure_document["providerCounters"] = {
                "expected": {"fixture.graph.load": 36},
                "actual": {"fixture.graph.load": 36},
            }
            closure = evidence.validate_success_closure(
                closure_document,
                lifecycle=lifecycle,
                expected_fixture_entrypoint=fixture_entrypoint,
                expected_capture_stack_digest=stack_digest,
                expected_source_digest=SOURCE_DIGEST,
                expected_app_origin=APP_ORIGIN,
                calibration_attestation=calibration,
                comparator_attestation=comparator,
            )
            grant = evidence.authorize_success_closure(
                lifecycle,
                validated_closure=closure,
            )
            passed = evidence.finalize_terminal_manifest(
                lifecycle,
                grant=grant,
            )
            if (
                passed["status"] != "passed"
                or passed["plannedLogicalRequests"] != 36
                or passed["plannedRootCaptures"] != 44
                or passed["completedLogicalRequests"] != 36
                or passed["completedRootCaptures"] != 44
                or passed["capturedCount"] != 44
                or len(passed["captures"]) != 44
            ):
                raise AssertionError(passed)
            leaves = [
                path
                for path in root.rglob("*")
                if path.is_file()
            ]
            if len(leaves) != 89:
                raise AssertionError(
                    f"root manifest bundle has {len(leaves)} leaves"
                )
            manifest_raw = (root / "manifest.json").read_bytes()
            bundle_contract = evidence.freeze_manifest_bundle_contract(
                fd,
                "manifest.json",
                expected_owner=OWNER,
                expected_manifest_sha256=_sha256(manifest_raw),
            )
            reopened = evidence.reauthenticate_manifest_bundle(
                fd,
                bundle_contract,
            )
            if len(reopened.captures) != 44:
                raise AssertionError(len(reopened.captures))
            adapted, root_audit = (
                evidence.adapt_root_capture_bundle_for_legacy_migration(
                    reopened,
                    oracle_capture_stack_digest="f" * 64,
                )
            )
            adapted_document = (
                evidence._migration_document_from_authenticated_bundle(
                    adapted,
                    fixture_entrypoint=fixture_entrypoint,
                    expected_mode="ux1b-selection-controls",
                    expected_phase="postcontrol",
                    label="adapted root controls",
                )
            )
            _, adapted_captures = evidence._migration_manifest(
                adapted_document,
                expected_mode="ux1b-selection-controls",
                label="adapted root controls",
            )
            evidence._validate_migration_profile(
                adapted_captures,
                fixture_entrypoint=fixture_entrypoint,
                label="adapted root controls",
            )
            if (
                len(adapted_captures) != 36
                or root_audit["logicalCaptureCount"] != 36
                or root_audit["rootCaptureCount"] != 44
                or root_audit["logicalCounterClaims"] != 36
                or root_audit["passedRootCaptures"] != 44
                or root_audit["unboundRootCaptures"] != 0
                or root_audit["exactPrePostProjections"] != 88
                or len(root_audit["roots"]) != 44
            ):
                raise AssertionError(root_audit)
            for logical_capture_id, after_capture in adapted_captures.items():
                before_capture = copy.deepcopy(after_capture)
                identity_row = identity_by_logical[logical_capture_id]
                before_capture["nodes"] = _matrix_render_nodes(
                    identity_row,
                    after=False,
                )
                before_capture["stableState"] = _matrix_stable_state(
                    identity_row,
                    after=False,
                )
                before_capture["controlEvidence"] = (
                    _focused_control_evidence(
                        identity_row,
                        accessible=False,
                    )
                )
                roots = evidence._catalog_roots_for_case(
                    _migration_catalog()["focusedCases"],
                    before_capture["case"],
                    label="focusedCases",
                )
                evidence._compare_capture_migration(
                    before_capture,
                    after_capture,
                    roots,
                )
        finally:
            if lifecycle.state in {"running", "finalizing"}:
                lifecycle.mark_terminal(
                    "failed",
                    {"reason": "root-lifecycle-test-cleanup"},
                )
            for capture in captures.values():
                try:
                    capture.close()
                except evidence.EvidenceContractError:
                    pass
            os.close(fd)


def test_catchable_failures_checkpoint_one_terminal_status() -> None:
    cases: tuple[tuple[type[BaseException], str, str], ...] = (
        (RuntimeError, "boom", "failed"),
        (evidence.DependencyUnavailable, "missing browser", "dependency_unavailable"),
        (evidence.InvalidEvidence, "bad capture", "invalid_data"),
        (KeyboardInterrupt, "stop", "interrupted"),
    )
    for exception_type, message, expected_status in cases:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fd, lifecycle = _new_lifecycle(root)
            try:
                lifecycle.start()

                def raise_failure() -> None:
                    with lifecycle.capture_failures():
                        raise exception_type(message)

                _raises(exception_type, raise_failure)
                document = _read_json(root / "manifest.json")
                if document["status"] != expected_status:
                    raise AssertionError((expected_status, document))
                if document.get("error", {}).get("type") != exception_type.__name__:
                    raise AssertionError(document)
                before = (root / "manifest.json").read_bytes()
                _raises(
                    evidence.EvidenceContractError,
                    lambda: lifecycle.mark_finalizing({}),
                )
                if (root / "manifest.json").read_bytes() != before:
                    raise AssertionError("catchable terminal was rewritten")
            finally:
                os.close(fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        capture_root = root / "capture"
        capture_root.mkdir()
        record = _capture_record(capture_root)
        capture_fd = _root_fd(capture_root)
        fd, lifecycle = _new_lifecycle(root)
        token = "TOP-SECRET-TERMINAL-TOKEN"
        try:
            authenticated_capture = evidence.verify_capture_artifacts(
                capture_fd,
                record,
                expected_owner=OWNER,
                run_root_fd=fd,
            )
            lifecycle.start()
            lifecycle.mark_finalizing({"childrenQuiescent": True})

            def raise_finalization_failure() -> None:
                with lifecycle.capture_failures(
                    partial_artifacts=(authenticated_capture,),
                    secrets=(token,),
                    private_roots=(root,),
                ):
                    raise RuntimeError(f"{token} {root} " + "x" * 100_000)

            _raises(RuntimeError, raise_finalization_failure)
            document = _read_json(root / "manifest.json")
            if document["status"] != "failed":
                raise AssertionError(document)
            encoded = json.dumps(document, ensure_ascii=False, sort_keys=True)
            if token in encoded or str(root) in encoded:
                raise AssertionError("terminal diagnostics leaked a secret or private path")
            error_bytes = json.dumps(
                document.get("error", {}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(error_bytes) > evidence.MAX_MANIFEST_ERROR_BYTES:
                raise AssertionError("terminal error exceeded its byte bound")
            partial = document.get("partialArtifacts")
            if not isinstance(partial, list) or len(partial) != 1:
                raise AssertionError(document)
        finally:
            os.close(capture_fd)
            os.close(fd)

    long_type = type("X" * 4_096, (RuntimeError,), {})
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fd, lifecycle = _new_lifecycle(root)
        try:
            lifecycle.start()

            def raise_long_type() -> None:
                with lifecycle.capture_failures():
                    raise long_type("")

            _raises(long_type, raise_long_type)
            document = _read_json(root / "manifest.json")
            error_raw = json.dumps(
                document["error"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(error_raw) > evidence.MAX_MANIFEST_ERROR_BYTES:
                raise AssertionError("long exception type exceeded terminal bound")
        finally:
            os.close(fd)


def test_stale_nonterminal_is_classified_without_rewriting_source() -> None:
    identity = {
        "schemaVersion": evidence.EVIDENCE_SCHEMA,
        "mode": "ux1b-full-pages",
        "phase": "precontrol",
        "runId": f"ux1b-{'a' * 24}",
        "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
        "expectedCaptureCount": 81,
    }
    for source_status in ("running", "finalizing"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            recovery = Path(temp) / "recovery"
            root.mkdir()
            recovery.mkdir()
            fd = _root_fd(root)
            lifecycle = evidence.ManifestLifecycle(
                fd,
                "manifest.json",
                base_document=identity,
            )
            recovery_fd = _root_fd(recovery)
            try:
                lifecycle.start()
                if source_status == "finalizing":
                    lifecycle.mark_finalizing({"childrenQuiescent": True})
                original = (root / "manifest.json").read_bytes()
                original_stat = (root / "manifest.json").stat(follow_symlinks=False)
                record = evidence.record_stale_nonterminal(
                    fd,
                    "manifest.json",
                    recovery_fd,
                    f"{source_status}.json",
                    expected_owner=OWNER,
                )
                repeated = evidence.record_stale_nonterminal(
                    fd,
                    "manifest.json",
                    recovery_fd,
                    f"{source_status}.json",
                    expected_owner=OWNER,
                )
                if repeated != record:
                    raise AssertionError("same stale source was not idempotent")
                if (root / "manifest.json").read_bytes() != original:
                    raise AssertionError("stale source manifest was mutated")
                observed_stat = (root / "manifest.json").stat(follow_symlinks=False)
                if (observed_stat.st_dev, observed_stat.st_ino) != (
                    original_stat.st_dev,
                    original_stat.st_ino,
                ):
                    raise AssertionError("stale source manifest inode changed")
                if record["status"] != "stale_nonterminal":
                    raise AssertionError(record)
                if record["sourceStatus"] != source_status or record["referenceable"]:
                    raise AssertionError(record)
                for key, value in identity.items():
                    if record[key] != value:
                        raise AssertionError((key, record))
                if record["sourceManifest"] != {
                    "path": "manifest.json",
                    "sha256": _sha256(original),
                    "size": len(original),
                }:
                    raise AssertionError(record)
                if _read_json(recovery / f"{source_status}.json") != record:
                    raise AssertionError("recovery record differs from return value")
                recovery_raw = (recovery / f"{source_status}.json").read_bytes()
                other_root = Path(temp) / "other-run"
                other_root.mkdir()
                other_document = {
                    **identity,
                    "runId": f"ux1b-{'c' * 24}",
                    "status": source_status,
                }
                _write(other_root / "manifest.json", _json_line(other_document))
                other_fd = _root_fd(other_root)
                try:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: evidence.record_stale_nonterminal(
                            other_fd,
                            "manifest.json",
                            recovery_fd,
                            f"{source_status}.json",
                            expected_owner=OWNER,
                        ),
                    )
                finally:
                    os.close(other_fd)
                if (recovery / f"{source_status}.json").read_bytes() != recovery_raw:
                    raise AssertionError("different stale source replaced recovery record")
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.verify_referenceable_manifest(
                        fd,
                        "manifest.json",
                        expected_owner=OWNER,
                        require_passed=True,
                    ),
                )
            finally:
                os.close(recovery_fd)
                os.close(fd)


def test_stale_nonterminal_accepts_full_page_posttheme_identity() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "run"
        recovery = Path(temp) / "recovery"
        root.mkdir()
        recovery.mkdir()
        source = {
            "schemaVersion": evidence.EVIDENCE_SCHEMA,
            "mode": "ux1b-full-pages",
            "phase": "posttheme",
            "runId": f"ux1b-{'d' * 24}",
            "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
            "expectedCaptureCount": 81,
            "status": "running",
        }
        _write(root / "manifest.json", _json_line(source))
        source_fd = _root_fd(root)
        recovery_fd = _root_fd(recovery)
        try:
            record = evidence.record_stale_nonterminal(
                source_fd,
                "manifest.json",
                recovery_fd,
                "posttheme.json",
                expected_owner=OWNER,
            )
        finally:
            os.close(recovery_fd)
            os.close(source_fd)
        if record["phase"] != "posttheme" or record["expectedCaptureCount"] != 81:
            raise AssertionError(record)


def test_stale_nonterminal_rejects_noncanonical_or_forged_identity() -> None:
    valid = {
        "schemaVersion": evidence.EVIDENCE_SCHEMA,
        "mode": "ux1b-full-pages",
        "phase": "precontrol",
        "runId": f"ux1b-{'b' * 24}",
        "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
        "expectedCaptureCount": 81,
        "status": "running",
    }
    mutations: tuple[tuple[str, Callable[[dict], None]], ...] = (
        ("schema", lambda value: value.__setitem__("schemaVersion", "unknown/v9")),
        ("mode", lambda value: value.__setitem__("mode", "ux1b-selection-controls")),
        ("phase", lambda value: value.__setitem__("phase", "postcontrol")),
        ("run-id", lambda value: value.__setitem__("runId", "run-1")),
        (
            "fixture",
            lambda value: value.__setitem__(
                "fixtureEntrypoint", "scripts/ui_ux_selection_fixture_app.py"
            ),
        ),
        ("count", lambda value: value.__setitem__("expectedCaptureCount", 36)),
        ("bool-count", lambda value: value.__setitem__("expectedCaptureCount", True)),
        ("missing-phase", lambda value: value.pop("phase")),
    )
    candidates: list[tuple[str, bytes]] = []
    for label, mutate in mutations:
        document = copy.deepcopy(valid)
        mutate(document)
        candidates.append((label, _json_line(document)))
    candidates.append(
        (
            "noncanonical",
            json.dumps(valid, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    )

    for label, raw in candidates:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            recovery = Path(temp) / "recovery"
            root.mkdir()
            recovery.mkdir()
            source = _write(root / "manifest.json", raw)
            source_fd = _root_fd(root)
            recovery_fd = _root_fd(recovery)
            before = source.read_bytes()
            before_stat = source.stat(follow_symlinks=False)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.record_stale_nonterminal(
                        source_fd,
                        "manifest.json",
                        recovery_fd,
                        f"{label}.json",
                        expected_owner=OWNER,
                    ),
                )
            finally:
                os.close(recovery_fd)
                os.close(source_fd)
            after_stat = source.stat(follow_symlinks=False)
            if source.read_bytes() != before or (
                after_stat.st_dev,
                after_stat.st_ino,
            ) != (before_stat.st_dev, before_stat.st_ino):
                raise AssertionError(f"rejected stale source changed: {label}")
            if list(recovery.iterdir()):
                raise AssertionError(f"rejected stale source was classified: {label}")


def _capture_record(root: Path, *, identity_row: dict | None = None) -> dict:
    if identity_row is None:
        identity_row = evidence.validate_worker_capture_identity(
            _valid_worker_request()
        )
    theme_fixture = None
    if identity_row["case"] == "theme-gallery":
        from scripts.test_ui_ux_theme_matrix import _rich_theme_worker_fixture

        theme_fixture = _rich_theme_worker_fixture(
            identity_row["viewport"]["name"]
        )
    png_raw = (
        theme_fixture["png"]
        if theme_fixture is not None
        else _viewport_png(identity_row["viewport"])
    )
    png = _write(root / "capture.png", png_raw)
    sidecar_document = (
        copy.deepcopy(theme_fixture["sidecar"])
        if theme_fixture is not None
        else _full_render_sidecar()
    )
    sidecar_document["identity"] = {
        "case": identity_row["case"],
        "route": identity_row["route"],
        "callable": identity_row["callable"],
    }
    sidecar_document["viewport"] = copy.deepcopy(identity_row["viewport"])
    sidecar_document["readiness"] = {
        "ready": True,
        "marker": identity_row["readiness"]["text"],
    }
    if theme_fixture is None:
        sidecar_document["nodes"] = _matrix_render_nodes(identity_row, after=True)
        sidecar_document["stableState"] = _matrix_stable_state(
            identity_row, after=True
        )
    sidecar_document["providerCounters"] = {}
    sidecar_document["mutatorCounters"] = {}
    source_runtime = "/private/tmp/quant-radar-owned-a-source"
    browser_runtime = "/private/tmp/quant-radar-owned-a-browser"
    sidecar_document["runtimeProjection"] = {
        "sourceRoot": source_runtime,
        "browserScratchRoot": browser_runtime,
    }
    if (
        identity_row["fixtureEntrypoint"]
        == "scripts/ui_ux_selection_fixture_app.py"
    ):
        sidecar_document["controlEvidence"] = _focused_control_evidence(
            identity_row, accessible=True
        )
    capture_id = f'{identity_row["case"]}/{identity_row["viewport"]["name"]}'
    profile_rows = evidence.worker_capture_profile_rows(
        identity_row["fixtureEntrypoint"]
    )
    counter_document = {
        "schemaVersion": evidence.COUNTER_DOCUMENT_SCHEMA,
        "fixtureRevision": evidence.COUNTER_DOCUMENT_REVISION,
        "contractSchema": evidence.COUNTER_CONTRACT_SCHEMA,
        "captures": {
            f'{row["case"]}/{row["viewport"]["name"]}': {
                "counts": {
                    "fixture.graph.load": 1,
                },
                "blockedNetwork": [],
                "identity": {
                    "selectedRegistryKey": row["registryKey"],
                    "realCallable": row["callable"],
                    "resolvedOwnedPaths": {"runtime": str(root)},
                },
            }
            for row in profile_rows
        },
        "bootstrapBlockedNetwork": [],
    }
    raw_sidecar = evidence.canonicalize_worker_render_sidecar(
        sidecar_document,
        owned_roots=(source_runtime, browser_runtime),
    )
    _write(root / "capture.raw.render.json", raw_sidecar)
    _write(root / "fixture-calls.json", _json_line(counter_document))
    root_fd = _root_fd(root)
    try:
        authenticated_raw = evidence.authenticate_raw_render_sidecar(
            root_fd,
            "capture.raw.render.json",
            expected_owner=OWNER,
            identity_row=identity_row,
        )
        authenticated_counters = evidence.authenticate_counter_bundle(
            root_fd,
            "fixture-calls.json",
            expected_owner=OWNER,
            expected_captures={
                f'{row["case"]}/{row["viewport"]["name"]}': {
                    "identityRow": row,
                    "positiveCounters": {"fixture.graph.load": 1},
                    "zeroCounters": ("mutator.fixture.graph.mutate",),
                    "ownedPaths": {"runtime": str(root)},
                }
                for row in profile_rows
            },
        )
    finally:
        os.close(root_fd)
    sidecar_raw = evidence.finalize_render_sidecar(
        authenticated_raw,
        authenticated_counters=authenticated_counters,
        capture_id=capture_id,
    )
    sidecar = _write(root / "capture.render.json", sidecar_raw)
    png_dimensions = (
        theme_fixture["sidecar"]["stableState"]["themeEvidence"]["fullPage"]
        if theme_fixture is not None
        else identity_row["viewport"]
    )
    return {
        "png": {
            "path": png.name,
            "sha256": _sha256(png_raw),
            "size": len(png_raw),
            "width": png_dimensions["width"],
            "height": png_dimensions["height"],
        },
        "renderSidecar": {
            "path": sidecar.name,
            "sha256": _sha256(sidecar_raw),
            "size": len(sidecar_raw),
            "schemaVersion": "quant-radar-ui-ux-render/v1",
        },
    }


def _publish_theme_supplements(root: Path, record: dict) -> list[dict]:
    sidecar = json.loads((root / record["renderSidecar"]["path"]).read_bytes())
    rich = sidecar["stableState"]["themeEvidence"]
    root_fd = _root_fd(root)
    try:
        parent_contract = evidence.freeze_artifact_contract(
            root_fd,
            record["png"]["path"],
            expected_owner=OWNER,
            max_bytes=evidence.MAX_PNG_BYTES,
        )
        with evidence.open_authenticated_artifact(
            root_fd,
            parent_contract,
        ) as parent:
            return [
                evidence.publish_derived_artifact(
                    parent,
                    root_fd,
                    expected_owner=OWNER,
                    artifact_id=surface["name"],
                    output_name=f'{surface["name"]}.png',
                    crop=surface["geometry"]["crop"],
                    theme_evidence_sha256=rich["sha256"],
                )
                for surface in rich["surfaces"]
            ]
    finally:
        os.close(root_fd)


def test_theme_supplements_are_exact_descriptor_derived_crops() -> None:
    row = evidence.worker_capture_profile_rows(
        "scripts/ui_ux_theme_fixture_app.py"
    )[0]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        record = _capture_record(root, identity_row=row)
        supplements = _publish_theme_supplements(root, record)
        fd = _root_fd(root)
        try:
            verified = evidence.verify_capture_artifacts(
                fd,
                record,
                expected_owner=OWNER,
                run_root_fd=fd,
                supplemental_artifacts=supplements,
            )
        finally:
            os.close(fd)
        if [row["id"] for row in verified["supplementalArtifacts"]] != [
            "canvas",
            "panel",
            "elevated",
        ]:
            raise AssertionError(verified)
        verified.close()

        sidecar_document = json.loads(
            (root / record["renderSidecar"]["path"]).read_bytes()
        )
        full_page = sidecar_document["stableState"]["themeEvidence"]["fullPage"]
        evidence._require_png_matches_render_viewport(
            (full_page["width"], full_page["height"]),
            sidecar_document,
            label="theme exact full page",
        )
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence._require_png_matches_render_viewport(
                (full_page["width"], full_page["height"] + 1),
                sidecar_document,
                label="theme oversized full page",
            ),
        )

        for label, mutate in (
            ("missing", lambda rows: rows.pop()),
            ("extra", lambda rows: rows.append(copy.deepcopy(rows[-1]))),
            ("order", lambda rows: rows.reverse()),
            (
                "parent-source",
                lambda rows: rows[0]["source"].__setitem__(
                    "parentPngSha256", "f" * 64
                ),
            ),
            (
                "theme-source",
                lambda rows: rows[0]["source"].__setitem__(
                    "themeEvidenceSha256", "f" * 64
                ),
            ),
            (
                "crop-source",
                lambda rows: rows[0]["source"]["crop"].__setitem__("x", 1),
            ),
        ):
            candidate = copy.deepcopy(supplements)
            mutate(candidate)
            fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda candidate=candidate: evidence.verify_capture_artifacts(
                        fd,
                        record,
                        expected_owner=OWNER,
                        run_root_fd=fd,
                        supplemental_artifacts=candidate,
                    ),
                )
            finally:
                os.close(fd)


def test_theme_crop_pixels_reject_palette_apng_and_forged_parent_authority() -> None:
    from PIL import Image

    def palette_png(color: tuple[int, int, int]) -> bytes:
        image = Image.new("P", (1, 1))
        image.putdata((0,))
        image.putpalette([*color, *(0 for _ in range(255 * 3))])
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    red = palette_png((255, 0, 0))
    blue = palette_png((0, 0, 255))
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._require_exact_png_crop(
            red,
            blue,
            {"x": 0, "y": 0, "width": 1, "height": 1},
            label="palette crop",
        ),
    )

    first = Image.new("RGBA", (1, 1), (255, 0, 0, 255))
    second = Image.new("RGBA", (1, 1), (0, 0, 255, 255))
    output = io.BytesIO()
    first.save(
        output,
        format="PNG",
        save_all=True,
        append_images=(second,),
        duration=10,
        loop=0,
    )
    apng = output.getvalue()
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._require_exact_png_crop(
            apng,
            _png_rgba(1, 1, (255, 0, 0, 255)),
            {"x": 0, "y": 0, "width": 1, "height": 1},
            label="animated parent",
        ),
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        parent_raw = _png_rgba(2, 1, (16, 24, 40, 255))
        parent_path = _write(root / "parent.png", parent_raw)
        root_fd = _root_fd(root)
        contract = evidence.freeze_artifact_contract(
            root_fd,
            "parent.png",
            expected_owner=OWNER,
            max_bytes=evidence.MAX_PNG_BYTES,
        )
        forged = object.__new__(evidence.AuthenticatedArtifact)
        forged.descriptor = os.open(parent_path, os.O_RDONLY)
        forged.contract = contract
        forged._closed = False
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.publish_derived_artifact(
                    forged,
                    root_fd,
                    expected_owner=OWNER,
                    artifact_id="canvas",
                    output_name="forged.png",
                    crop={"x": 0, "y": 0, "width": 1, "height": 1},
                    theme_evidence_sha256="a" * 64,
                ),
            )
        finally:
            os.close(forged.descriptor)

        with evidence.open_authenticated_artifact(root_fd, contract) as parent:
            original_publish = evidence._exclusive_write_at

            def mutate_same_inode_then_publish(
                directory_fd: int, name: str, raw: bytes
            ) -> None:
                mutated = parent_raw[:-1] + bytes((parent_raw[-1] ^ 1,))
                parent_path.write_bytes(mutated)
                if parent_path.stat(follow_symlinks=False).st_ino != contract.leaf.inode:
                    raise AssertionError("same-inode mutation replaced the parent")
                original_publish(directory_fd, name, raw)

            with mock.patch.object(
                evidence,
                "_exclusive_write_at",
                side_effect=mutate_same_inode_then_publish,
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.publish_derived_artifact(
                        parent,
                        root_fd,
                        expected_owner=OWNER,
                        artifact_id="canvas",
                        output_name="mutated.png",
                        crop={"x": 0, "y": 0, "width": 1, "height": 1},
                        theme_evidence_sha256="a" * 64,
                    ),
                )
        os.close(root_fd)


def test_atomic_new_leaf_publication_is_complete_or_absent_under_faults() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        root_fd = _root_fd(root)
        raw = b"complete-evidence-payload"
        try:
            def partial_write(descriptor: int, payload: bytes) -> None:
                os.write(descriptor, payload[:3])
                raise OSError(5, "injected partial write")

            with mock.patch.object(
                evidence,
                "_write_all",
                side_effect=partial_write,
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence._exclusive_write_at(root_fd, "partial.bin", raw),
                )
            if (root / "partial.bin").exists():
                raise AssertionError("partial publication exposed an incomplete leaf")

            original_unlink = evidence.os.unlink
            cleanup_calls = 0

            def fail_first_link_cleanup(
                name: str, *, dir_fd: int | None = None
            ) -> None:
                nonlocal cleanup_calls
                if name.startswith(".cleanup.bin.") and cleanup_calls == 0:
                    cleanup_calls += 1
                    raise OSError(5, "injected link cleanup failure")
                original_unlink(name, dir_fd=dir_fd)

            with mock.patch.object(
                evidence.os,
                "unlink",
                side_effect=fail_first_link_cleanup,
            ):
                _raises(
                    evidence.ManifestDurabilityUncertain,
                    lambda: evidence._exclusive_write_at(root_fd, "cleanup.bin", raw),
                )
            if (root / "cleanup.bin").read_bytes() != raw:
                raise AssertionError("link-cleanup fault exposed incomplete bytes")

            original_fsync = evidence.os.fsync

            def fail_directory_fsync(descriptor: int) -> None:
                if descriptor == root_fd:
                    raise OSError(5, "injected directory fsync failure")
                original_fsync(descriptor)

            with mock.patch.object(
                evidence.os,
                "fsync",
                side_effect=fail_directory_fsync,
            ):
                _raises(
                    evidence.ManifestDurabilityUncertain,
                    lambda: evidence._exclusive_write_at(root_fd, "fsync.bin", raw),
                )
            if (root / "fsync.bin").read_bytes() != raw:
                raise AssertionError("directory-fsync fault exposed incomplete bytes")

            evidence._exclusive_write_at(root_fd, "existing.bin", b"first")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence._exclusive_write_at(
                    root_fd, "existing.bin", b"replacement"
                ),
            )
            if (root / "existing.bin").read_bytes() != b"first":
                raise AssertionError("no-replace publication overwrote an existing leaf")
            leftovers = [path.name for path in root.iterdir() if path.name.startswith(".")]
            if leftovers:
                raise AssertionError(f"atomic publication left temporary files: {leftovers}")
        finally:
            os.close(root_fd)


def test_theme_counter_bundle_is_complete_exact_and_nonempty() -> None:
    from scripts import ui_ux_fixtures as fixtures
    from scripts import ui_ux_theme_matrix as theme_matrix

    rows = evidence.worker_capture_profile_rows(
        "scripts/ui_ux_theme_fixture_app.py"
    )
    with tempfile.TemporaryDirectory() as temp:
        app_root = Path(temp)
        (app_root / "fixture-root" / "theme-gallery").mkdir(parents=True)
        expected = theme_matrix._theme_counter_expectations(rows, app_root=app_root)
        captures = {}
        for capture_id, contract in expected.items():
            identity_row = contract["identityRow"]
            captures[capture_id] = {
                "counts": dict(fixtures.THEME_COUNTER_CONTRACT["positive"]),
                "blockedNetwork": [],
                "identity": {
                    "selectedRegistryKey": identity_row["registryKey"],
                    "realCallable": identity_row["callable"],
                    "resolvedOwnedPaths": copy.deepcopy(contract["ownedPaths"]),
                },
            }
        document = {
            "schemaVersion": evidence.COUNTER_DOCUMENT_SCHEMA,
            "fixtureRevision": evidence.COUNTER_DOCUMENT_REVISION,
            "contractSchema": evidence.COUNTER_CONTRACT_SCHEMA,
            "captures": captures,
            "bootstrapBlockedNetwork": [],
        }
        _write(app_root / "fixture-calls.json", _json_line(document))
        app_fd = _root_fd(app_root)
        try:
            bundle = evidence.authenticate_counter_bundle(
                app_fd,
                "fixture-calls.json",
                expected_owner=OWNER,
                expected_captures=expected,
            )
        finally:
            os.close(app_fd)
        if (
            bundle["completeMatrix"] is not True
            or bundle["profileEntrypoint"]
            != "scripts/ui_ux_theme_fixture_app.py"
            or set(bundle["captures"]) != {
                "theme-gallery/desktop",
                "theme-gallery/tablet",
                "theme-gallery/mobile",
            }
        ):
            raise AssertionError(bundle)
        for capture in bundle["captures"].values():
            if capture["providerCounters"] != {"theme.gallery.render": 1}:
                raise AssertionError(capture)
            if not capture["mutatorCounters"] or any(
                capture["mutatorCounters"].values()
            ):
                raise AssertionError("theme mutator zero contract is incomplete")


def test_descriptor_counter_enrichment_is_required_and_exact() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mobile_request = _valid_worker_request()
        desktop_request = copy.deepcopy(mobile_request)
        desktop_request["requestId"] = "knowledge-graph-controls/desktop"
        desktop_request["viewport"] = {
            "name": "desktop",
            "width": 1440,
            "height": 900,
        }
        mobile_identity = evidence.validate_worker_capture_identity(mobile_request)
        desktop_identity = evidence.validate_worker_capture_identity(desktop_request)
        mobile_id = mobile_request["requestId"]
        desktop_id = desktop_request["requestId"]
        source_runtime = "/private/tmp/quant-radar-owned-a-source"
        browser_runtime = "/private/tmp/quant-radar-owned-a-browser"
        profile_rows = evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )

        def raw_sidecar(identity_row: dict) -> dict:
            value = _full_render_sidecar()
            value["identity"] = {
                "case": identity_row["case"],
                "route": identity_row["route"],
                "callable": identity_row["callable"],
            }
            value["viewport"] = copy.deepcopy(identity_row["viewport"])
            value["readiness"] = {
                "ready": True,
                "marker": identity_row["readiness"]["text"],
            }
            value["providerCounters"] = {}
            value["mutatorCounters"] = {}
            value["runtimeProjection"] = {
                "sourceRoot": source_runtime,
                "browserScratchRoot": browser_runtime,
            }
            value["controlEvidence"] = _focused_control_evidence(
                identity_row, accessible=True
            )
            return value

        raw_mobile = raw_sidecar(mobile_identity)
        raw_desktop = raw_sidecar(desktop_identity)
        raw_mobile_bytes = evidence.canonicalize_worker_render_sidecar(
            raw_mobile, owned_roots=(source_runtime, browser_runtime)
        )
        raw_desktop_bytes = evidence.canonicalize_worker_render_sidecar(
            raw_desktop, owned_roots=(source_runtime, browser_runtime)
        )
        mobile_png = _viewport_png(mobile_identity["viewport"])
        _write(root / "capture.png", mobile_png)
        _write(root / "capture.raw.render.json", raw_mobile_bytes)
        _write(root / "capture.desktop.raw.render.json", raw_desktop_bytes)
        _write(root / "capture.render.json", raw_mobile_bytes)
        raw_record = {
            "png": {
                "path": "capture.png",
                "sha256": _sha256(mobile_png),
                "size": len(mobile_png),
                "width": mobile_identity["viewport"]["width"],
                "height": mobile_identity["viewport"]["height"],
            },
            "renderSidecar": {
                "path": "capture.render.json",
                "sha256": _sha256(raw_mobile_bytes),
                "size": len(raw_mobile_bytes),
                "schemaVersion": RENDER_SCHEMA,
            },
        }
        root_fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.verify_capture_artifacts(
                    root_fd,
                    raw_record,
                    expected_owner=OWNER,
                    run_root_fd=root_fd,
                ),
            )
        finally:
            os.close(root_fd)

        def counter_bucket(identity_row: dict) -> dict:
            # The fixture intentionally omits counters whose observed value is
            # zero.  The coordinator materializes those declared zero values.
            return {
                "counts": {"fixture.graph.load": 1},
                "blockedNetwork": [],
                "identity": {
                    "selectedRegistryKey": identity_row["registryKey"],
                    "realCallable": identity_row["callable"],
                    "resolvedOwnedPaths": {"runtime": str(root)},
                },
            }

        def counter_document() -> dict:
            return {
                "schemaVersion": evidence.COUNTER_DOCUMENT_SCHEMA,
                "fixtureRevision": evidence.COUNTER_DOCUMENT_REVISION,
                "contractSchema": evidence.COUNTER_CONTRACT_SCHEMA,
                "captures": {
                    f'{row["case"]}/{row["viewport"]["name"]}': counter_bucket(row)
                    for row in profile_rows
                },
                "bootstrapBlockedNetwork": [],
            }

        expected_captures = {
            f'{row["case"]}/{row["viewport"]["name"]}': {
                "identityRow": row,
                "positiveCounters": {"fixture.graph.load": 1},
                "zeroCounters": ("mutator.fixture.graph.mutate",),
                "ownedPaths": {"runtime": str(root)},
            }
            for row in profile_rows
        }

        _write(root / "fixture-calls.json", _json_line(counter_document()))
        root_fd = _root_fd(root)
        try:
            authenticated_raw = evidence.authenticate_raw_render_sidecar(
                root_fd,
                "capture.raw.render.json",
                expected_owner=OWNER,
                identity_row=mobile_identity,
            )
            authenticated_desktop_raw = evidence.authenticate_raw_render_sidecar(
                root_fd,
                "capture.desktop.raw.render.json",
                expected_owner=OWNER,
                identity_row=desktop_identity,
            )
            authenticated = evidence.authenticate_counter_bundle(
                root_fd,
                "fixture-calls.json",
                expected_owner=OWNER,
                expected_captures=expected_captures,
            )
        finally:
            os.close(root_fd)
        if not isinstance(authenticated, evidence.AuthenticatedCounterBundle):
            raise AssertionError(type(authenticated).__name__)
        if authenticated["completeMatrix"] is not True:
            raise AssertionError("frozen focused profile was not recognized as complete")
        if not isinstance(
            authenticated_raw, evidence.AuthenticatedRawRenderSidecar
        ) or not isinstance(
            authenticated_desktop_raw, evidence.AuthenticatedRawRenderSidecar
        ):
            raise AssertionError("raw descriptor authentication was not opaque")

        forged = object.__new__(evidence.AuthenticatedCounterBundle)
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.finalize_render_sidecar(
                authenticated_raw,
                authenticated_counters=forged,
                capture_id=mobile_id,
            ),
        )
        forged_raw = object.__new__(evidence.AuthenticatedRawRenderSidecar)
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.finalize_render_sidecar(
                forged_raw,
                authenticated_counters=authenticated,
                capture_id=mobile_id,
            ),
        )
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.finalize_render_sidecar(
                raw_mobile,
                authenticated_counters=authenticated,
                capture_id=mobile_id,
            ),
        )
        final_bytes = evidence.finalize_render_sidecar(
            authenticated_raw,
            authenticated_counters=authenticated,
            capture_id=mobile_id,
        )
        final_document = json.loads(final_bytes)
        if final_document["providerCounters"] != {"fixture.graph.load": 1}:
            raise AssertionError(final_document)
        if final_document["mutatorCounters"] != {
            "mutator.fixture.graph.mutate": 0
        }:
            raise AssertionError(final_document)
        if "counterProvenance" not in final_document:
            raise AssertionError(final_document)
        desktop_final = json.loads(
            evidence.finalize_render_sidecar(
                authenticated_desktop_raw,
                authenticated_counters=authenticated,
                capture_id=desktop_id,
            )
        )
        if desktop_final["viewport"]["name"] != "desktop":
            raise AssertionError(desktop_final)
        _write(root / "capture.render.json", final_bytes)
        final_record = copy.deepcopy(raw_record)
        final_record["renderSidecar"]["sha256"] = _sha256(final_bytes)
        final_record["renderSidecar"]["size"] = len(final_bytes)
        root_fd = _root_fd(root)
        try:
            verified = evidence.verify_capture_artifacts(
                root_fd,
                final_record,
                expected_owner=OWNER,
                run_root_fd=root_fd,
            )
        finally:
            os.close(root_fd)
        if not isinstance(verified, evidence.VerifiedCaptureArtifacts):
            raise AssertionError(type(verified).__name__)

        nonempty_raw = copy.deepcopy(raw_mobile)
        nonempty_raw["providerCounters"] = {"forged": 1}
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.canonicalize_worker_render_sidecar(
                nonempty_raw,
                owned_roots=("/private/tmp/quant-radar-owned-a",),
            ),
        )

        canonical_raw_document = json.loads(raw_mobile_bytes)

        def swap_runtime_roles(value: dict) -> None:
            runtime = value["runtimeProjection"]
            runtime["sourceRoot"], runtime["browserScratchRoot"] = (
                runtime["browserScratchRoot"],
                runtime["sourceRoot"],
            )

        def unknown_runtime_role(value: dict) -> None:
            value["runtimeProjection"]["sourceRoot"] = "$OWNED_ROOT_9"

        def missing_runtime_role(value: dict) -> None:
            value["runtimeProjection"].pop("browserScratchRoot")

        def extra_runtime_role(value: dict) -> None:
            value["runtimeProjection"]["appRoot"] = "$OWNED_ROOT_2"

        def wrong_readiness(value: dict) -> None:
            value["readiness"]["marker"] = "forged-ready"

        for index, mutate in enumerate(
            (
                swap_runtime_roles,
                unknown_runtime_role,
                missing_runtime_role,
                extra_runtime_role,
                wrong_readiness,
            )
        ):
            candidate = copy.deepcopy(canonical_raw_document)
            mutate(candidate)
            candidate_bytes = evidence.canonicalize_worker_render_sidecar(
                candidate, owned_roots=()
            )
            name = f"invalid-runtime-{index}.render.json"
            _write(root / name, candidate_bytes)
            root_fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda name=name: evidence.authenticate_raw_render_sidecar(
                        root_fd,
                        name,
                        expected_owner=OWNER,
                        identity_row=mobile_identity,
                    ),
                )
            finally:
                os.close(root_fd)

        # A legacy single-capture grant can still be read for compatibility,
        # but it cannot authorize final-sidecar creation.
        legacy_document = counter_document()
        legacy_document["captures"] = {
            mobile_id: legacy_document["captures"][mobile_id]
        }
        _write(root / "legacy-counter.json", _json_line(legacy_document))
        root_fd = _root_fd(root)
        try:
            legacy = evidence.authenticate_counter_document(
                root_fd,
                "legacy-counter.json",
                expected_owner=OWNER,
                expected_capture_id=mobile_id,
                identity_row=mobile_identity,
                expected_positive_counters={"fixture.graph.load": 1},
                expected_zero_counters=("mutator.fixture.graph.mutate",),
                expected_owned_paths={"runtime": str(root)},
            )
        finally:
            os.close(root_fd)
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.finalize_render_sidecar(
                authenticated_raw,
                authenticated_counters=legacy,
                capture_id=mobile_id,
            ),
        )

        for index, capture_ids in enumerate(
            ((mobile_id,), (mobile_id, desktop_id))
        ):
            partial_document = counter_document()
            partial_document["captures"] = {
                capture_id: partial_document["captures"][capture_id]
                for capture_id in capture_ids
            }
            partial_expected = {
                capture_id: expected_captures[capture_id]
                for capture_id in capture_ids
            }
            name = f"partial-counter-{index}.json"
            _write(root / name, _json_line(partial_document))
            root_fd = _root_fd(root)
            try:
                partial = evidence.authenticate_counter_bundle(
                    root_fd,
                    name,
                    expected_owner=OWNER,
                    expected_captures=partial_expected,
                )
            finally:
                os.close(root_fd)
            if partial["completeMatrix"] is not False:
                raise AssertionError("partial profile claimed matrix completeness")
            _raises(
                evidence.EvidenceContractError,
                lambda partial=partial: evidence.finalize_render_sidecar(
                    authenticated_raw,
                    authenticated_counters=partial,
                    capture_id=mobile_id,
                ),
            )

        theme_identity = evidence.worker_capture_profile_rows(
            "scripts/ui_ux_theme_fixture_app.py"
        )[0]
        theme_id = f'{theme_identity["case"]}/{theme_identity["viewport"]["name"]}'
        mixed_document = counter_document()
        mixed_document["captures"] = {
            mobile_id: mixed_document["captures"][mobile_id],
            theme_id: counter_bucket(theme_identity),
        }
        mixed_expected = {
            mobile_id: expected_captures[mobile_id],
            theme_id: {
                "identityRow": theme_identity,
                "positiveCounters": {"fixture.graph.load": 1},
                "zeroCounters": ("mutator.fixture.graph.mutate",),
                "ownedPaths": {"runtime": str(root)},
            },
        }
        _write(root / "mixed-counter.json", _json_line(mixed_document))
        root_fd = _root_fd(root)
        try:
            mixed = evidence.authenticate_counter_bundle(
                root_fd,
                "mixed-counter.json",
                expected_owner=OWNER,
                expected_captures=mixed_expected,
            )
        finally:
            os.close(root_fd)
        if mixed["completeMatrix"] is not False:
            raise AssertionError("mixed entrypoints claimed matrix completeness")
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.finalize_render_sidecar(
                authenticated_raw,
                authenticated_counters=mixed,
                capture_id=mobile_id,
            ),
        )

        mutations: tuple[Callable[[dict], None], ...] = (
            lambda value: value.__setitem__("schemaVersion", 2),
            lambda value: value.__setitem__("fixtureRevision", "unknown"),
            lambda value: value.__setitem__("contractSchema", 2),
            lambda value: value["captures"].pop(desktop_id),
            lambda value: value["captures"].__setitem__("undeclared", {}),
            lambda value: value["captures"][mobile_id]["counts"].__setitem__(
                "fixture.graph.load", 2
            ),
            lambda value: value["captures"][mobile_id]["counts"].__setitem__(
                "mutator.fixture.graph.mutate", 1
            ),
            lambda value: value["captures"][mobile_id]["counts"].__setitem__(
                "undeclared.counter", 1
            ),
            lambda value: value["bootstrapBlockedNetwork"].append(
                {"kind": "connect", "target": "blocked"}
            ),
            lambda value: value["captures"][mobile_id]["blockedNetwork"].append(
                {"kind": "connect", "target": "blocked"}
            ),
            lambda value: value["captures"][mobile_id]["identity"].__setitem__(
                "selectedRegistryKey", "invented"
            ),
            lambda value: value["captures"][mobile_id]["identity"].__setitem__(
                "realCallable", "invented.render"
            ),
            lambda value: value["captures"][mobile_id]["identity"][
                "resolvedOwnedPaths"
            ].__setitem__("runtime", "/private/tmp/invented"),
        )
        for index, mutate in enumerate(mutations):
            candidate = counter_document()
            mutate(candidate)
            name = f"invalid-counter-{index}.json"
            _write(root / name, _json_line(candidate))
            root_fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda name=name: evidence.authenticate_counter_bundle(
                        root_fd,
                        name,
                        expected_owner=OWNER,
                        expected_captures=expected_captures,
                    ),
                )
            finally:
                os.close(root_fd)

        duplicate_bucket = json.dumps(
            counter_document()["captures"][mobile_id],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        quoted_mobile_id = json.dumps(mobile_id)
        duplicate_raw = (
            "{"
            f'"schemaVersion":{evidence.COUNTER_DOCUMENT_SCHEMA},'
            f'"fixtureRevision":{json.dumps(evidence.COUNTER_DOCUMENT_REVISION)},'
            f'"contractSchema":{evidence.COUNTER_CONTRACT_SCHEMA},'
            f'"captures":{{{quoted_mobile_id}:{duplicate_bucket},'
            f'{quoted_mobile_id}:{duplicate_bucket}}},'
            '"bootstrapBlockedNetwork":[]}'
            "\n"
        ).encode("utf-8")
        _write(root / "duplicate-counter.json", duplicate_raw)
        root_fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_counter_bundle(
                    root_fd,
                    "duplicate-counter.json",
                    expected_owner=OWNER,
                    expected_captures=expected_captures,
                ),
            )
        finally:
            os.close(root_fd)

        forged_identity = copy.deepcopy(mobile_identity)
        forged_identity["rootSelectors"] = (".st-key-invented",)
        forged_expected = copy.deepcopy(expected_captures)
        forged_expected[mobile_id]["identityRow"] = forged_identity
        root_fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_counter_bundle(
                    root_fd,
                    "fixture-calls.json",
                    expected_owner=OWNER,
                    expected_captures=forged_expected,
                ),
            )
        finally:
            os.close(root_fd)


def test_canonical_sidecar_strips_only_explicit_volatile_paths() -> None:
    before = _full_render_sidecar(run_suffix="a")
    after = _full_render_sidecar(run_suffix="b")
    before_root = "/private/tmp/quant-radar-owned-a"
    after_root = "/private/tmp/quant-radar-owned-b"
    before_bytes = evidence.canonicalize_render_sidecar(
        before, owned_roots=(before_root,)
    )
    after_bytes = evidence.canonicalize_render_sidecar(after, owned_roots=(after_root,))
    if before_bytes != after_bytes:
        raise AssertionError("allowed volatile render fields changed canonical bytes")
    canonical = json.loads(before_bytes)
    if canonical["identity"] != before["identity"]:
        raise AssertionError(canonical)
    if canonical["providerCounters"] != before["providerCounters"]:
        raise AssertionError(canonical)
    encoded = before_bytes.decode("utf-8")
    for volatile in (
        before_root,
        before["capturedAt"],
        before["runId"],
        before["nodes"][0]["browserNodeId"],
    ):
        if volatile in encoded:
            raise AssertionError(f"volatile value remained canonical: {volatile}")

    reordered = dict(reversed(tuple(before.items())))
    if evidence.canonicalize_render_sidecar(
        reordered, owned_roots=(before_root,)
    ) != before_bytes:
        raise AssertionError("mapping insertion order changed canonical bytes")

    semantic_mutations: tuple[Callable[[dict], None], ...] = (
        lambda value: value["identity"].__setitem__("route", "/changed"),
        lambda value: value["identity"].__setitem__("callable", "changed.render"),
        lambda value: value["viewport"].__setitem__("width", 391),
        lambda value: value["readiness"].__setitem__("ready", False),
        lambda value: value["nodes"][0].__setitem__("role", "paragraph"),
        lambda value: value["nodes"][0].__setitem__("name", "Changed"),
        lambda value: value["nodes"][0].__setitem__(
            "text", "2026-07-17T00:00:00Z"
        ),
        lambda value: value["nodes"][0]["state"].__setitem__("expanded", True),
        lambda value: value["nodes"][0].__setitem__("visible", False),
        lambda value: value["nodes"][0]["bounds"].__setitem__("x", 21),
        lambda value: value["stableState"].__setitem__("decision", "changed"),
        lambda value: value["providerCounters"].__setitem__(
            "fixture.graph.load", 2
        ),
        lambda value: value["mutatorCounters"].__setitem__(
            "fixture.graph.mutate", 1
        ),
        lambda value: value["nodes"].reverse(),
    )
    for mutate in semantic_mutations:
        candidate = copy.deepcopy(before)
        mutate(candidate)
        try:
            candidate_bytes = evidence.canonicalize_render_sidecar(
                candidate, owned_roots=(before_root,)
            )
        except evidence.EvidenceContractError:
            continue
        if candidate_bytes == before_bytes:
            raise AssertionError(f"semantic mutation was stripped: {mutate!r}")

    invalid_mutations: tuple[Callable[[dict], None], ...] = (
        lambda value: value.pop("identity"),
        lambda value: value.__setitem__("unexpected", True),
        lambda value: value["nodes"][0]["bounds"].__setitem__("x", math.nan),
        lambda value: value["nodes"][0]["bounds"].__setitem__("width", math.inf),
        lambda value: value["viewport"].__setitem__("width", True),
    )
    for mutate in invalid_mutations:
        candidate = copy.deepcopy(before)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.canonicalize_render_sidecar(
                candidate, owned_roots=(before_root,)
            ),
        )

    role_before = copy.deepcopy(before)
    role_after = copy.deepcopy(after)
    role_before["runtimeProjection"] = {
        "sourceRoot": "/private/tmp/source-a",
        "browserScratchRoot": "/private/tmp/browser-a",
    }
    role_after["runtimeProjection"] = {
        "sourceRoot": "/private/tmp/source-b",
        "browserScratchRoot": "/private/tmp/browser-b",
    }
    role_before_bytes = evidence.canonicalize_render_sidecar(
        role_before,
        owned_roots=("/private/tmp/source-a", "/private/tmp/browser-a"),
    )
    role_after_bytes = evidence.canonicalize_render_sidecar(
        role_after,
        owned_roots=("/private/tmp/source-b", "/private/tmp/browser-b"),
    )
    if role_before_bytes != role_after_bytes:
        raise AssertionError("equivalent runtime roles did not canonicalize equally")
    swapped_roles = copy.deepcopy(role_before)
    swapped_roles["runtimeProjection"] = {
        "sourceRoot": "/private/tmp/browser-a",
        "browserScratchRoot": "/private/tmp/source-a",
    }
    swapped_bytes = evidence.canonicalize_render_sidecar(
        swapped_roles,
        owned_roots=("/private/tmp/source-a", "/private/tmp/browser-a"),
    )
    if swapped_bytes == role_before_bytes:
        raise AssertionError("swapped source/browser roles were erased")
    unknown_boundary = copy.deepcopy(before)
    unknown_boundary["nodes"][2]["boundaryId"] = "missing-boundary"
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.canonicalize_render_sidecar(
            unknown_boundary, owned_roots=(before_root,)
        ),
    )


def test_png_and_render_sidecar_are_independently_authenticated() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        record = _capture_record(root)
        fd = _root_fd(root)
        try:
            verified = evidence.verify_capture_artifacts(
                fd,
                record,
                expected_owner=OWNER,
                run_root_fd=fd,
            )
        finally:
            os.close(fd)
        if not isinstance(verified, evidence.VerifiedCaptureArtifacts):
            raise AssertionError(type(verified).__name__)
        if verified["png"]["sha256"] != record["png"]["sha256"]:
            raise AssertionError(verified)
        if (verified["png"]["width"], verified["png"]["height"]) != (390, 844):
            raise AssertionError(verified)
        if verified["renderSidecar"]["sha256"] != record["renderSidecar"]["sha256"]:
            raise AssertionError(verified)
        verified.close()
        if id(verified) in evidence._VERIFIED_CAPTURES:
            raise AssertionError("closed capture authority remained registered")
        registry_size = len(evidence._VERIFIED_CAPTURES)

        def verify_and_drop() -> None:
            dropped = evidence.verify_capture_artifacts(
                capacity_fd,
                record,
                expected_owner=OWNER,
                run_root_fd=capacity_fd,
            )
            if id(dropped) not in evidence._VERIFIED_CAPTURES:
                raise AssertionError("verified capture authority was not registered")

        capacity_fd = _root_fd(root)
        try:
            verify_and_drop()
            gc.collect()
            if len(evidence._VERIFIED_CAPTURES) != registry_size:
                raise AssertionError("dropped capture authority was not reclaimed")
        finally:
            os.close(capacity_fd)
        capacity_fd = _root_fd(root)
        try:
            with mock.patch.object(
                evidence,
                "MAX_VERIFIED_CAPTURE_AUTHORITIES",
                len(evidence._VERIFIED_CAPTURES),
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.verify_capture_artifacts(
                        capacity_fd,
                        record,
                        expected_owner=OWNER,
                        run_root_fd=capacity_fd,
                    ),
                )
        finally:
            os.close(capacity_fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        record = _capture_record(root)
        (root / "capture.png").write_bytes(PNG_1X1)
        record["png"].update(
            {
                "sha256": _sha256(PNG_1X1),
                "size": len(PNG_1X1),
                "width": 1,
                "height": 1,
            }
        )
        fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.verify_capture_artifacts(
                    fd,
                    record,
                    expected_owner=OWNER,
                    run_root_fd=fd,
                ),
            )
        finally:
            os.close(fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        artifact_root = root / "artifacts"
        unrelated_run_root = root / "other-run"
        artifact_root.mkdir()
        unrelated_run_root.mkdir()
        record = _capture_record(artifact_root)
        artifact_fd = _root_fd(artifact_root)
        unrelated_fd = _root_fd(unrelated_run_root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.verify_capture_artifacts(
                    artifact_fd,
                    record,
                    expected_owner=OWNER,
                    run_root_fd=unrelated_fd,
                ),
            )
        finally:
            os.close(unrelated_fd)
            os.close(artifact_fd)

    mutations = (
        "png-bytes",
        "png-dimensions",
        "sidecar-bytes",
        "sidecar-schema-with-current-digest",
        "invalid-png-with-current-digest",
    )
    for mutation in mutations:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = _capture_record(root)
            if mutation == "png-bytes":
                (root / "capture.png").write_bytes(PNG_1X1[:-1] + b"X")
            elif mutation == "png-dimensions":
                record["png"]["width"] = 2
            elif mutation == "sidecar-bytes":
                (root / "capture.render.json").write_text("{}", encoding="utf-8")
            elif mutation == "sidecar-schema-with-current-digest":
                invalid_raw = _json_line({"schemaVersion": RENDER_SCHEMA}).rstrip(
                    b"\n"
                )
                (root / "capture.render.json").write_bytes(invalid_raw)
                record["renderSidecar"]["sha256"] = _sha256(invalid_raw)
                record["renderSidecar"]["size"] = len(invalid_raw)
            else:
                invalid_png = b"not-a-decoded-png"
                (root / "capture.png").write_bytes(invalid_png)
                record["png"]["sha256"] = _sha256(invalid_png)
                record["png"]["size"] = len(invalid_png)
            fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.verify_capture_artifacts(
                        fd,
                        record,
                        expected_owner=OWNER,
                        run_root_fd=fd,
                    ),
                )
            finally:
                os.close(fd)


def _write_manifest_bundle(root: Path) -> tuple[dict, bytes]:
    artifact_root = root / "artifacts"
    record = _capture_record(artifact_root)
    record["png"]["path"] = "artifacts/capture.png"
    record["renderSidecar"]["path"] = "artifacts/capture.render.json"
    document = {
        "schemaVersion": "quant-radar-ui-ux-evidence/v1",
        "status": "passed",
        "mode": "ux1b-selection-controls",
        "runId": "bundle-run",
        "captureStackDigest": STACK_DIGEST,
        "sourceDigestStart": SOURCE_DIGEST,
        "sourceDigestEnd": SOURCE_DIGEST,
        "captures": [
            {
                "id": "knowledge-graph-controls/mobile",
                "status": "passed",
                "artifacts": record,
            }
        ],
    }
    raw = _json_line(document)
    _write(root / "manifest.json", raw)
    return document, raw


def test_manifest_bundle_is_descriptor_reauthenticated_at_finalization() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        expected_document, manifest_raw = _write_manifest_bundle(root)
        fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.freeze_manifest_bundle_contract(
                    fd, "manifest.json", expected_owner=OWNER
                ),
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.freeze_manifest_bundle_contract(
                    fd,
                    "manifest.json",
                    expected_owner=OWNER,
                    expected_manifest_sha256="0" * 64,
                ),
            )
            # Simulate a new process: the external manifest hash remains the
            # trust anchor, while the prior finalizer registry does not.
            with evidence._FINALIZED_RENDER_SIDECARS_LOCK:
                evidence._FINALIZED_RENDER_SIDECARS.clear()
            contract = evidence.freeze_manifest_bundle_contract(
                fd,
                "manifest.json",
                expected_owner=OWNER,
                expected_manifest_sha256=_sha256(manifest_raw),
            )
            if not isinstance(contract, evidence.ManifestBundleContract):
                raise AssertionError(type(contract).__name__)
            authenticated = evidence.reauthenticate_manifest_bundle(fd, contract)
            if not isinstance(authenticated, evidence.AuthenticatedManifestBundle):
                raise AssertionError(type(authenticated).__name__)
            if authenticated.manifest != expected_document:
                raise AssertionError(authenticated.manifest)
        finally:
            os.close(fd)

    for mutation in ("capture-id", "duplicate-artifact-path"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document, _raw = _write_manifest_bundle(root)
            if mutation == "capture-id":
                document["captures"][0]["id"] = "forged/mobile"
            else:
                duplicate = copy.deepcopy(document["captures"][0])
                duplicate["id"] = "duplicate/mobile"
                document["captures"].append(duplicate)
            mutated_raw = _json_line(document)
            _write(root / "manifest.json", mutated_raw)
            fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.freeze_manifest_bundle_contract(
                        fd,
                        "manifest.json",
                        expected_owner=OWNER,
                        expected_manifest_sha256=_sha256(mutated_raw),
                    ),
                )
            finally:
                os.close(fd)

    mutations = (
        "manifest-same-byte-inode",
        "artifact-same-byte-inode",
        "artifact-ancestor-same-byte-inode",
        "artifact-symlink",
        "artifact-hardlink",
        "artifact-hash",
    )
    for mutation in mutations:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _document, manifest_raw = _write_manifest_bundle(root)
            fd = _root_fd(root)
            try:
                contract = evidence.freeze_manifest_bundle_contract(
                    fd,
                    "manifest.json",
                    expected_owner=OWNER,
                    expected_manifest_sha256=_sha256(manifest_raw),
                )
                if mutation == "manifest-same-byte-inode":
                    manifest = root / "manifest.json"
                    mode = manifest.stat(follow_symlinks=False).st_mode & 0o777
                    original = manifest.stat(follow_symlinks=False).st_ino
                    manifest.rename(root / "manifest-old.json")
                    _write(manifest, manifest_raw)
                    os.chmod(manifest, mode)
                    if manifest.stat(follow_symlinks=False).st_ino == original:
                        raise AssertionError("manifest fixture reused inode")
                elif mutation == "artifact-same-byte-inode":
                    png = root / "artifacts" / "capture.png"
                    raw = png.read_bytes()
                    mode = png.stat(follow_symlinks=False).st_mode & 0o777
                    original = png.stat(follow_symlinks=False).st_ino
                    png.rename(root / "artifacts" / "capture-old.png")
                    _write(png, raw)
                    os.chmod(png, mode)
                    if png.stat(follow_symlinks=False).st_ino == original:
                        raise AssertionError("artifact fixture reused inode")
                elif mutation == "artifact-ancestor-same-byte-inode":
                    artifacts = root / "artifacts"
                    png_raw = (artifacts / "capture.png").read_bytes()
                    sidecar_raw = (artifacts / "capture.render.json").read_bytes()
                    directory_mode = artifacts.stat(follow_symlinks=False).st_mode & 0o777
                    original = artifacts.stat(follow_symlinks=False).st_ino
                    artifacts.rename(root / "artifacts-old")
                    artifacts.mkdir()
                    os.chmod(artifacts, directory_mode)
                    _write(artifacts / "capture.png", png_raw)
                    _write(artifacts / "capture.render.json", sidecar_raw)
                    if artifacts.stat(follow_symlinks=False).st_ino == original:
                        raise AssertionError("artifact ancestor fixture reused inode")
                elif mutation == "artifact-symlink":
                    png = root / "artifacts" / "capture.png"
                    png.rename(root / "artifacts" / "capture-old.png")
                    png.symlink_to("capture-old.png")
                elif mutation == "artifact-hardlink":
                    png = root / "artifacts" / "capture.png"
                    os.link(png, root / "artifacts" / "capture-hardlink.png")
                else:
                    png = root / "artifacts" / "capture.png"
                    raw = bytearray(png.read_bytes())
                    raw[-1] ^= 0x01
                    png.write_bytes(bytes(raw))
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.reauthenticate_manifest_bundle(fd, contract),
                )
            finally:
                os.close(fd)


def test_theme_pair_requires_exact_canonical_sidecars_and_valid_dimensions() -> None:
    before = _full_render_sidecar(run_suffix="a")
    after = _full_render_sidecar(run_suffix="b")
    before_png = _png_rgba(1, 1, (255, 0, 0, 255))
    after_png = _png_rgba(1, 1, (0, 0, 255, 255))
    report = evidence.compare_theme_render_pair(
        before_sidecar=before,
        after_sidecar=after,
        before_png=before_png,
        after_png=after_png,
        before_owned_roots=("/private/tmp/quant-radar-owned-a",),
        after_owned_roots=("/private/tmp/quant-radar-owned-b",),
    )
    if report.get("status") != "passed":
        raise AssertionError(report)
    if report.get("canonicalSidecarsEqual") is not True:
        raise AssertionError(report)
    if report.get("pngBytesDiffer") is not True:
        raise AssertionError(report)
    if report.get("dimensions") != {"width": 1, "height": 1}:
        raise AssertionError(report)

    semantic_mutations: tuple[Callable[[dict], None], ...] = (
        lambda value: value["nodes"][2]["state"].__setitem__("checked", False),
        lambda value: value["nodes"][2]["bounds"].__setitem__("width", 71),
        lambda value: value["providerCounters"].__setitem__(
            "fixture.graph.load", 2
        ),
        lambda value: value["stableState"].__setitem__("decision", "changed"),
    )
    for mutate in semantic_mutations:
        candidate = copy.deepcopy(after)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.compare_theme_render_pair(
                before_sidecar=before,
                after_sidecar=candidate,
                before_png=before_png,
                after_png=after_png,
                before_owned_roots=("/private/tmp/quant-radar-owned-a",),
                after_owned_roots=("/private/tmp/quant-radar-owned-b",),
            ),
        )

    for invalid_after_png in (
        b"not-a-png",
        _png_rgba(2, 1, (0, 0, 255, 255)),
        _png_overexpanded_1x1(),
    ):
        _raises(
            evidence.EvidenceContractError,
            lambda invalid_after_png=invalid_after_png: evidence.compare_theme_render_pair(
                before_sidecar=before,
                after_sidecar=after,
                before_png=before_png,
                after_png=invalid_after_png,
                before_owned_roots=("/private/tmp/quant-radar-owned-a",),
                after_owned_roots=("/private/tmp/quant-radar-owned-b",),
            ),
        )


def _mint_operational_attestations():
    live_calibration_report = {
        "schemaVersion": "quant-radar-ui-ux-isolation-calibration/v1",
        "passed": True,
        "profileSha256": "a" * 64,
    }
    with mock.patch.object(
        evidence.isolation,
        "validate_live_calibration_provenance",
        autospec=True,
        return_value="a" * 64,
    ) as validate_live:
        calibration = evidence.mint_calibration_attestation(
            live_calibration_report
        )
        validate_live.assert_called_once_with(live_calibration_report)
    if not isinstance(calibration, evidence.CalibrationAttestation):
        raise AssertionError(type(calibration).__name__)

    comparator_report = evidence.validate_baseline_evidence(
        _authenticate_migration_manifest(
            _migration_manifest(mode="ux1b-theme", after=False)
        ),
        fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
    )
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.mint_comparator_attestation(
            copy.deepcopy(comparator_report)
        ),
    )
    comparator = evidence.mint_comparator_attestation(comparator_report)
    if not isinstance(comparator, evidence.ComparatorAttestation):
        raise AssertionError(type(comparator).__name__)
    return calibration, comparator


def _verified_profile_captures(
    root: Path, *, fixture_entrypoint: str, run_root_fd: int
) -> dict[str, object]:
    result: dict[str, object] = {}
    for index, row in enumerate(
        evidence.worker_capture_profile_rows(fixture_entrypoint)
    ):
        capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
        capture_root = root / str(index)
        capture_root.mkdir(parents=True)
        record = _capture_record(capture_root, identity_row=row)
        supplements = (
            _publish_theme_supplements(capture_root, record)
            if row["case"] == "theme-gallery"
            else ()
        )
        root_fd = _root_fd(capture_root)
        try:
            result[capture_id] = evidence.verify_capture_artifacts(
                root_fd,
                record,
                expected_owner=OWNER,
                run_root_fd=run_root_fd,
                supplemental_artifacts=supplements,
            )
        finally:
            os.close(root_fd)
    return result


def _verified_root_profile_captures(
    root: Path,
    *,
    run_root_fd: int,
    raw_sidecars: list[object] | None = None,
) -> dict[str, object]:
    fixture_entrypoint = "scripts/ui_ux_selection_fixture_app.py"
    identity_rows = evidence.worker_capture_profile_rows(
        fixture_entrypoint
    )
    identity_by_logical = {
        f'{row["case"]}/{row["viewport"]["name"]}': row
        for row in identity_rows
    }
    counter_document = {
        "schemaVersion": evidence.COUNTER_DOCUMENT_SCHEMA,
        "fixtureRevision": evidence.COUNTER_DOCUMENT_REVISION,
        "contractSchema": evidence.COUNTER_CONTRACT_SCHEMA,
        "captures": {
            logical_id: {
                "counts": {"fixture.graph.load": 1},
                "blockedNetwork": [],
                "identity": {
                    "selectedRegistryKey": row["registryKey"],
                    "realCallable": row["callable"],
                    "resolvedOwnedPaths": {"runtime": str(root)},
                },
            }
            for logical_id, row in identity_by_logical.items()
        },
        "bootstrapBlockedNetwork": [],
    }
    _write(root / "fixture-calls.json", _json_line(counter_document))
    root_fd = _root_fd(root)
    try:
        counters = evidence.authenticate_counter_bundle(
            root_fd,
            "fixture-calls.json",
            expected_owner=OWNER,
            expected_captures={
                logical_id: {
                    "identityRow": row,
                    "positiveCounters": {"fixture.graph.load": 1},
                    "zeroCounters": ("mutator.fixture.graph.mutate",),
                    "ownedPaths": {"runtime": str(root)},
                }
                for logical_id, row in identity_by_logical.items()
            },
        )
    finally:
        os.close(root_fd)

    source_runtime = "/private/tmp/quant-radar-root-source"
    browser_runtime = "/private/tmp/quant-radar-root-browser"
    result: dict[str, object] = {}
    for root_row in evidence.root_capture_expansion_rows():
        logical_id = root_row["logicalCaptureId"]
        identity = identity_by_logical[logical_id]
        capture_root = root / "captures"
        for component in root_row["rootCaptureId"].split("/"):
            capture_root /= component
        capture_root.mkdir(parents=True)
        png_raw = _viewport_png(identity["viewport"])
        _write(capture_root / "capture.png", png_raw)

        semantic_nodes = _matrix_render_nodes(identity, after=True)
        outer_nodes = copy.deepcopy(semantic_nodes)
        focused = _focused_control_evidence_v3(
            identity,
            root_selector=root_row["rootSelector"],
        )
        root_rect = focused["controls"][0]["layout"]["rootRect"]
        for node in outer_nodes:
            if node["rootSelector"] == root_row["rootSelector"]:
                node["bounds"] = {
                    key: int(value)
                    for key, value in root_rect.items()
                }
        stable_state = _matrix_stable_state(identity, after=True)
        runtime_projection = {
            "sourceRoot": source_runtime,
            "browserScratchRoot": browser_runtime,
        }
        sidecar_document = {
            "schemaVersion": evidence.RENDER_V2_SCHEMA,
            "identity": {
                "case": identity["case"],
                "route": identity["route"],
                "callable": identity["callable"],
            },
            "viewport": copy.deepcopy(identity["viewport"]),
            "readiness": {
                "ready": True,
                "marker": identity["readiness"]["text"],
            },
            "nodes": outer_nodes,
            "stableState": copy.deepcopy(stable_state),
            "providerCounters": {},
            "mutatorCounters": {},
            "runtimeProjection": runtime_projection,
            "counterProvenance": None,
            "rootCapture": {
                key: copy.deepcopy(root_row[key])
                for key in (
                    "logicalCaptureId",
                    "rootCaptureId",
                    "rootOrdinal",
                    "rootSelector",
                )
            }
            | {
                "rootExpansionSha256": (
                    evidence.ROOT_CAPTURE_EXPANSION_SHA256
                )
            },
            "controlEvidence": focused,
            "caseSemanticProjection": {
                "schemaVersion": (
                    evidence.CASE_SEMANTIC_PROJECTION_SCHEMA
                ),
                "identity": {
                    key: copy.deepcopy(root_row[key])
                    for key in (
                        "fixtureEntrypoint",
                        "logicalCaptureId",
                        "case",
                        "route",
                        "callable",
                        "viewport",
                    )
                },
                "readiness": {
                    "ready": True,
                    "marker": identity["readiness"]["text"],
                },
                "nodes": semantic_nodes,
                "stableState": copy.deepcopy(stable_state),
                "providerCounters": {},
                "mutatorCounters": {},
                "runtimeProjection": runtime_projection,
                "counterProvenance": None,
                "controlEvidence": _focused_control_evidence(
                    identity,
                    accessible=True,
                ),
            },
        }
        raw = evidence.canonicalize_worker_render_sidecar(
            sidecar_document,
            owned_roots=(source_runtime, browser_runtime),
        )
        _write(capture_root / "raw.render.json", raw)
        capture_root_fd = _root_fd(capture_root)
        try:
            authenticated_raw = evidence.authenticate_raw_render_sidecar(
                capture_root_fd,
                "raw.render.json",
                expected_owner=OWNER,
                identity_row=identity,
            )
            if raw_sidecars is not None:
                raw_sidecars.append(authenticated_raw)
            final_raw = evidence.finalize_render_sidecar(
                authenticated_raw,
                authenticated_counters=counters,
                capture_id=logical_id,
            )
            _write(capture_root / "render.json", final_raw)
            (capture_root / "raw.render.json").unlink()
            record = {
                "png": {
                    "path": "capture.png",
                    "sha256": _sha256(png_raw),
                    "size": len(png_raw),
                    "width": identity["viewport"]["width"],
                    "height": identity["viewport"]["height"],
                },
                "renderSidecar": {
                    "path": "render.json",
                    "sha256": _sha256(final_raw),
                    "size": len(final_raw),
                    "schemaVersion": evidence.RENDER_V2_SCHEMA,
                },
            }
            result[root_row["rootCaptureId"]] = (
                evidence.verify_capture_artifacts(
                    capture_root_fd,
                    record,
                    expected_owner=OWNER,
                    run_root_fd=run_root_fd,
                )
            )
        finally:
            os.close(capture_root_fd)
    (root / "fixture-calls.json").unlink()
    return result


def _spawn_test_process_family(
    *, session_id: str, role: str, process_id: str
) -> subprocess.Popen[bytes]:
    process_token = isolation._new_process_token()
    identity = isolation._ProcessFamilyIdentity(
        session_id=session_id,
        process_id=process_id,
        process_token=process_token,
        role=role,
        launch_identity_sha256=hashlib.sha256(
            f"{session_id}\0{role}\0{process_id}\0{process_token}".encode("utf-8")
        ).hexdigest(),
        owner_uid=OWNER,
    )
    registration = isolation._reserve_process_family(identity)
    environment = dict(os.environ)
    environment[isolation.PROCESS_TOKEN_ENV_KEY] = process_token
    try:
        process = subprocess.Popen(
            (sys.executable, "-c", "import time; time.sleep(0.05)"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            close_fds=True,
            pass_fds=(),
            start_new_session=True,
        )
    except BaseException:
        isolation._release_reserved_process_family(registration)
        raise
    try:
        isolation._attach_process_family(registration, process)
    except BaseException:
        try:
            isolation._cleanup_unregistered_process(process, registration)
        finally:
            isolation._release_process_family(registration)
        raise
    return process


def _quiescent_profile_processes(
    *, fixture_entrypoint: str, session_id: str = "run-1"
) -> dict[str, object]:
    profile_names = {
        "scripts/ui_ux_fixture_app.py": "full-pages",
        "scripts/ui_ux_selection_fixture_app.py": "selection-controls",
        "scripts/ui_ux_theme_fixture_app.py": "theme",
    }
    capture_ids = sorted(
        f'{row["case"]}/{row["viewport"]["name"]}'
        for row in evidence.worker_capture_profile_rows(fixture_entrypoint)
    )
    assignments = [
        ("app", f'app/{profile_names[fixture_entrypoint]}')
    ] + [("browser", capture_id) for capture_id in capture_ids]
    processes: list[tuple[object, str, str]] = []
    try:
        for role, capture_id in assignments:
            process = _spawn_test_process_family(
                session_id=session_id,
                role=role,
                process_id=capture_id,
            )
            processes.append((process, role, capture_id))
        proofs = {
            capture_id: isolation.wait_for_clean_owned_process_group_exit(
                process,
                timeout=3.0,
            )
            for process, role, capture_id in processes
        }
    finally:
        for process, _role, _capture_id in processes:
            if process.poll() is None:
                isolation.terminate_owned_process_group(process)
    app_id = f'app/{profile_names[fixture_entrypoint]}'
    return {
        "app": proofs[app_id],
        "browsers": {capture_id: proofs[capture_id] for capture_id in capture_ids},
    }


def _valid_success_closure(
    authenticated_captures: dict[str, object],
    process_proofs: dict[str, object],
) -> dict:
    return {
        "status": "finalizing",
        "captureStackDigest": _complete_control_catalog()["captureStackDigest"],
        "sourceDigestStart": SOURCE_DIGEST,
        "sourceDigestEnd": SOURCE_DIGEST,
        "captures": [
            {
                "id": capture_id,
                "status": "passed",
                "artifacts": authenticated_capture,
            }
            for capture_id, authenticated_capture in authenticated_captures.items()
        ],
        "providerCounters": {
            "expected": {"fixture.graph.load": 1},
            "actual": {"fixture.graph.load": 1},
        },
        "mutatorCounters": {
            "expected": {"fixture.graph.mutate": 0},
            "actual": {"fixture.graph.mutate": 0},
        },
        "prohibitedCounters": {
            "production.read": 0,
            "production.write": 0,
            "network.outbound": 0,
        },
        "processes": {
            "app": process_proofs["app"],
            "browsers": dict(process_proofs["browsers"]),
        },
        "network": {"appOrigin": APP_ORIGIN, "appPort": APP_PORT},
    }


def test_success_closure_rejects_source_counter_capture_and_process_failures() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        capture_root = root / "captures"
        capture_root.mkdir()
        fixture_entrypoint = "scripts/ui_ux_theme_fixture_app.py"
        fd, lifecycle = _new_lifecycle(root, mode="ux1b-theme")
        try:
            lifecycle.start()
            lifecycle.mark_finalizing({"childrenQuiescent": True})
            authenticated_captures = _verified_profile_captures(
                capture_root,
                fixture_entrypoint=fixture_entrypoint,
                run_root_fd=fd,
            )
            calibration_attestation, comparator_attestation = (
                _mint_operational_attestations()
            )
            process_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )

            def validate(candidate: Mapping[str, object]):
                return evidence.validate_success_closure(
                    candidate,
                    lifecycle=lifecycle,
                    expected_fixture_entrypoint=fixture_entrypoint,
                    expected_capture_stack_digest=_complete_control_catalog()[
                        "captureStackDigest"
                    ],
                    expected_source_digest=SOURCE_DIGEST,
                    expected_app_origin=APP_ORIGIN,
                    calibration_attestation=calibration_attestation,
                    comparator_attestation=comparator_attestation,
                )

            valid = _valid_success_closure(authenticated_captures, process_proofs)
            result = validate(valid)
            if not isinstance(result, evidence.ValidatedSuccessClosure):
                raise AssertionError(type(result).__name__)
            closure_ids_after_first = set(evidence._VALIDATED_CLOSURES)
            _raises(evidence.EvidenceContractError, lambda: validate(valid))
            if set(evidence._VALIDATED_CLOSURES) != closure_ids_after_first:
                raise AssertionError("replayed process proofs registered a closure")

            invalid_process_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )

            forged_capture = object.__new__(evidence.VerifiedCaptureArtifacts)
            mutations: list[Callable[[dict], None]] = [
                lambda value: value.__setitem__("sourceDigestEnd", "e" * 64),
                lambda value: value["providerCounters"]["actual"].__setitem__(
                    "fixture.graph.load", 2
                ),
                lambda value: value["providerCounters"]["actual"].__setitem__(
                    "unexpected.provider", 1
                ),
                lambda value: value["providerCounters"]["actual"].clear(),
                lambda value: value["mutatorCounters"]["actual"].__setitem__(
                    "fixture.graph.mutate", 1
                ),
                lambda value: value["mutatorCounters"]["actual"].clear(),
                lambda value: value["prohibitedCounters"].__setitem__(
                    "production.read", 1
                ),
                lambda value: value["prohibitedCounters"].pop("production.write"),
                lambda value: value["captures"][0].__setitem__("status", "failed"),
                lambda value: value["captures"].clear(),
                lambda value: value["captures"].append(value["captures"][0]),
                lambda value: value["captures"][0].__setitem__(
                    "id", "unexpected/mobile"
                ),
                lambda value: value["captures"][0].__setitem__(
                    "artifacts", forged_capture
                ),
                lambda value: value["processes"]["browsers"].pop(
                    next(iter(value["processes"]["browsers"]))
                ),
                lambda value: value["processes"]["browsers"].__setitem__(
                    "unexpected/mobile",
                    next(iter(value["processes"]["browsers"].values())),
                ),
                lambda value: value["processes"].__setitem__(
                    "app", next(iter(value["processes"]["browsers"].values()))
                ),
                lambda value: value["processes"].__setitem__(
                    "app", {"returnCode": 0, "signal": None, "quiescent": True}
                ),
                lambda value: value["network"].__setitem__(
                    "appOrigin", "http://127.0.0.1:43124"
                ),
                lambda value: value["network"].__setitem__("appPort", APP_PORT + 1),
                lambda value: value.__setitem__("captureStackDigest", "f" * 64),
            ]
            for mutate in mutations:
                candidate = _valid_success_closure(
                    authenticated_captures, invalid_process_proofs
                )
                mutate(candidate)
                _raises(
                    evidence.EvidenceContractError,
                    lambda candidate=candidate: validate(candidate),
                )

            forged_calibration = object.__new__(evidence.CalibrationAttestation)
            forged_comparator = object.__new__(evidence.ComparatorAttestation)
            invalid_attestation_pairs = (
                ({"passed": True}, comparator_attestation),
                ("coordinator-calibration-report", comparator_attestation),
                (forged_calibration, comparator_attestation),
                (calibration_attestation, {"closed": True}),
                (calibration_attestation, "coordinator-comparator-report"),
                (calibration_attestation, forged_comparator),
            )
            for invalid_calibration, invalid_comparator in invalid_attestation_pairs:
                _raises(
                    evidence.EvidenceContractError,
                    lambda invalid_calibration=invalid_calibration, invalid_comparator=invalid_comparator: evidence.validate_success_closure(
                        _valid_success_closure(
                            authenticated_captures, invalid_process_proofs
                        ),
                        lifecycle=lifecycle,
                        expected_fixture_entrypoint=fixture_entrypoint,
                        expected_capture_stack_digest=_complete_control_catalog()[
                            "captureStackDigest"
                        ],
                        expected_source_digest=SOURCE_DIGEST,
                        expected_app_origin=APP_ORIGIN,
                        calibration_attestation=invalid_calibration,
                        comparator_attestation=invalid_comparator,
                    ),
                )

            for attestation, other, is_calibration in (
                (calibration_attestation, comparator_attestation, True),
                (comparator_attestation, calibration_attestation, False),
            ):
                try:
                    copied = copy.copy(attestation)
                except (TypeError, evidence.EvidenceContractError):
                    continue
                if copied is attestation:
                    raise AssertionError("opaque attestation copy returned original object")
                invalid_calibration = copied if is_calibration else other
                invalid_comparator = other if is_calibration else copied
                _raises(
                    evidence.EvidenceContractError,
                    lambda invalid_calibration=invalid_calibration, invalid_comparator=invalid_comparator: evidence.validate_success_closure(
                        _valid_success_closure(
                            authenticated_captures, invalid_process_proofs
                        ),
                        lifecycle=lifecycle,
                        expected_fixture_entrypoint=fixture_entrypoint,
                        expected_capture_stack_digest=_complete_control_catalog()[
                            "captureStackDigest"
                        ],
                        expected_source_digest=SOURCE_DIGEST,
                        expected_app_origin=APP_ORIGIN,
                        calibration_attestation=invalid_calibration,
                        comparator_attestation=invalid_comparator,
                    ),
                )

            foreign_root = root / "foreign-run"
            foreign_root.mkdir()
            foreign_capture_root = foreign_root / "captures"
            foreign_capture_root.mkdir()
            foreign_fd = _root_fd(foreign_root)
            try:
                foreign_captures = _verified_profile_captures(
                    foreign_capture_root,
                    fixture_entrypoint=fixture_entrypoint,
                    run_root_fd=foreign_fd,
                )
            finally:
                os.close(foreign_fd)
            _raises(
                evidence.EvidenceContractError,
                lambda: validate(
                    _valid_success_closure(
                        foreign_captures, invalid_process_proofs
                    )
                ),
            )

            abandoned_closure = validate(
                _valid_success_closure(
                    authenticated_captures, invalid_process_proofs
                )
            )
            if not isinstance(
                abandoned_closure,
                evidence.ValidatedSuccessClosure,
            ):
                raise AssertionError("unused process proofs did not remain valid")
            abandoned_closure_id = id(abandoned_closure)
            del abandoned_closure
            gc.collect()
            if abandoned_closure_id in evidence._VALIDATED_CLOSURES:
                raise AssertionError("abandoned validated closure was not reclaimed")

            mid_failure_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )
            mid_failure = _valid_success_closure(
                authenticated_captures, mid_failure_proofs
            )
            mid_ids = sorted(mid_failure["processes"]["browsers"])
            if len(mid_ids) < 2:
                raise AssertionError("mid-consume regression needs two browser proofs")
            mid_failure["processes"]["browsers"][mid_ids[1]] = (
                mid_failure["processes"]["browsers"][mid_ids[0]]
            )
            closure_ids_before_mid_failure = set(evidence._VALIDATED_CLOSURES)
            _raises(
                evidence.EvidenceContractError,
                lambda: validate(mid_failure),
            )
            if set(evidence._VALIDATED_CLOSURES) != closure_ids_before_mid_failure:
                raise AssertionError("partial proof consumption registered a closure")
            for capture_id in mid_ids[1:]:
                isolation.consume_quiescent_process_exit_provenance(
                    mid_failure_proofs["browsers"][capture_id],
                    expected_session_id="run-1",
                    expected_role="browser",
                    expected_process_id=capture_id,
                )

            racing_proofs = _quiescent_profile_processes(
                fixture_entrypoint=fixture_entrypoint
            )
            racing_document = _valid_success_closure(
                authenticated_captures, racing_proofs
            )
            barrier = threading.Barrier(3)
            racing_results: list[object] = []
            racing_lock = threading.Lock()

            def validate_racing_closure() -> None:
                barrier.wait()
                try:
                    outcome: object = validate(racing_document)
                except BaseException as exc:
                    outcome = exc
                with racing_lock:
                    racing_results.append(outcome)

            closure_ids_before_race = set(evidence._VALIDATED_CLOSURES)
            threads = [
                threading.Thread(target=validate_racing_closure) for _index in range(2)
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5.0)
            if any(thread.is_alive() for thread in threads):
                raise AssertionError("concurrent success-closure validation hung")
            successes = [
                value
                for value in racing_results
                if isinstance(value, evidence.ValidatedSuccessClosure)
            ]
            failures = [
                value
                for value in racing_results
                if isinstance(value, evidence.EvidenceContractError)
            ]
            if len(successes) != 1 or len(failures) != 1:
                raise AssertionError(racing_results)
            if len(set(evidence._VALIDATED_CLOSURES) - closure_ids_before_race) != 1:
                raise AssertionError("concurrent proof consume minted multiple closures")
            grant = evidence.authorize_success_closure(
                lifecycle,
                validated_closure=result,
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authorize_success_closure(
                    lifecycle,
                    validated_closure=successes[0],
                ),
            )
            grant_id = id(grant)
            del grant
            gc.collect()
            if grant_id in evidence._SUCCESS_GRANTS or any(
                id(capture) in evidence._VERIFIED_CAPTURES
                for capture in authenticated_captures.values()
            ):
                raise AssertionError("abandoned grant retained capture authority")
            lifecycle.mark_terminal(
                "failed",
                {"reason": "authority-reservation-regression-complete"},
            )
            for capture in foreign_captures.values():
                capture.close()
        finally:
            os.close(fd)


def _node(
    node_id: str,
    *,
    parent_id: str | None,
    flow: str,
    boundary: str | None,
    root_selector: str | None,
    role: str,
    name: str,
    text: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict:
    return {
        "id": node_id,
        "parentId": parent_id,
        "flowScope": flow,
        "boundaryId": boundary,
        "rootSelector": root_selector,
        "role": role,
        "name": name,
        "text": text,
        "state": {},
        "visible": True,
        "bounds": {"x": x, "y": y, "width": width, "height": height},
    }


def _render_nodes(prefix: str, *, after: bool) -> list[dict]:
    boundary = f"{prefix}-mode-row"
    delta = 24 if after else 0
    nodes = [
        _node(
            f"{prefix}-title",
            parent_id=None,
            flow="main",
            boundary=None,
            root_selector=None,
            role="heading",
            name="Knowledge Graph",
            text="Knowledge Graph",
            x=20,
            y=20,
            width=300,
            height=30,
        ),
        _node(
            boundary,
            parent_id=None,
            flow="main",
            boundary=boundary,
            root_selector=None,
            role="group",
            name="controls-row",
            text="",
            x=20,
            y=60,
            width=350,
            height=64 if after else 40,
        ),
        _node(
            f"{prefix}-view-root",
            parent_id=boundary,
            flow="main",
            boundary=boundary,
            root_selector=".st-key-kg_view_mode",
            role="radiogroup" if after else "group",
            name="視圖",
            text="",
            x=20,
            y=60,
            width=165,
            height=64 if after else 40,
        ),
        _node(
            f"{prefix}-label-root",
            parent_id=boundary,
            flow="main",
            boundary=boundary,
            root_selector=".st-key-kg_label_mode",
            role="radiogroup",
            name="標籤",
            text="",
            x=205,
            y=60,
            width=165,
            height=64 if after else 40,
        ),
    ]
    boundary_note = _node(
        f"{prefix}-boundary-note",
        parent_id=boundary,
        flow="main",
        boundary=boundary,
        root_selector=None,
        role="note",
        name="Stable boundary metadata",
        text="Stable boundary metadata",
        x=20,
        y=60,
        width=0,
        height=0,
    )
    boundary_note["visible"] = False
    nodes.append(boundary_note)
    if after:
        nodes.extend(
            [
                _node(
                    f"{prefix}-view-radio",
                    parent_id=f"{prefix}-view-root",
                    flow="main",
                    boundary=boundary,
                    root_selector=None,
                    role="radio",
                    name="星雲圖",
                    text="星雲圖",
                    x=24,
                    y=64,
                    width=70,
                    height=24,
                ),
                _node(
                    f"{prefix}-label-radio",
                    parent_id=f"{prefix}-label-root",
                    flow="main",
                    boundary=boundary,
                    root_selector=None,
                    role="radio",
                    name="核心",
                    text="核心",
                    x=209,
                    y=64,
                    width=60,
                    height=24,
                ),
            ]
        )
        nodes[-2]["state"] = {"checked": True, "tabIndex": 0}
        nodes[-1]["state"] = {"checked": True, "tabIndex": 0}
    else:
        nodes.extend(
            [
                _node(
                    f"{prefix}-view-button",
                    parent_id=f"{prefix}-view-root",
                    flow="main",
                    boundary=boundary,
                    root_selector=None,
                    role="button",
                    name="星雲圖",
                    text="星雲圖",
                    x=24,
                    y=64,
                    width=70,
                    height=24,
                ),
                _node(
                    f"{prefix}-label-button",
                    parent_id=f"{prefix}-label-root",
                    flow="main",
                    boundary=boundary,
                    root_selector=None,
                    role="button",
                    name="核心",
                    text="核心",
                    x=209,
                    y=64,
                    width=60,
                    height=24,
                ),
            ]
        )
    nodes.extend(
        [
            _node(
                f"{prefix}-body-1",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="paragraph",
                name="Summary",
                text="Stable summary",
                x=20,
                y=120 + delta,
                width=350,
                height=30,
            ),
            _node(
                f"{prefix}-body-2",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="table",
                name="Results",
                text="Stable results",
                x=20,
                y=170 + delta,
                width=350,
                height=100,
            ),
            _node(
                f"{prefix}-sidebar",
                parent_id=None,
                flow="sidebar",
                boundary=None,
                root_selector=None,
                role="navigation",
                name="Navigation",
                text="Menu",
                x=0,
                y=0,
                width=15,
                height=300,
            ),
        ]
    )
    return nodes


def _matrix_prefix(row: dict) -> str:
    if row["case"] == "knowledge-graph":
        return "page"
    if row["case"] == "knowledge-graph-controls":
        return "focused"
    return row["case"].replace("-controls", "")


def _matrix_root_id(prefix: str, session_key: str) -> str:
    if session_key == "kg_view_mode":
        return f"{prefix}-view-root"
    if session_key == "kg_label_mode":
        return f"{prefix}-label-root"
    return f"{prefix}-{session_key}-root"


def _matrix_child_id(prefix: str, session_key: str, *, after: bool) -> str:
    suffix = "radio" if after else "button"
    if session_key == "kg_view_mode":
        return f"{prefix}-view-{suffix}"
    if session_key == "kg_label_mode":
        return f"{prefix}-label-{suffix}"
    return f"{prefix}-{session_key}-{suffix}"


def _test_dom_boundary(case: str) -> str:
    digest = hashlib.sha256(f"/main/{case}/controls".encode("utf-8")).hexdigest()
    return f"dom-{digest[:20]}"


def _matrix_render_nodes(row: dict, *, after: bool) -> list[dict]:
    prefix = _matrix_prefix(row)
    selectors = tuple(row["rootSelectors"])
    if not selectors:
        return [
            _node(
                f"{prefix}-title",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="heading",
                name=row["case"],
                text=row["case"],
                x=20,
                y=20,
                width=300,
                height=30,
            ),
            _node(
                f"{prefix}-body-1",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="paragraph",
                name="Summary",
                text="Stable summary",
                x=20,
                y=120,
                width=350,
                height=30,
            ),
        ]

    boundary = _test_dom_boundary(row["case"])
    delta = 24 if after else 0
    available_width = min(350, row["viewport"]["width"] - 40)
    nodes = [
        _node(
            f"{prefix}-title",
            parent_id=None,
            flow="main",
            boundary=None,
            root_selector=None,
            role="heading",
            name=row["case"],
            text=row["case"],
            x=20,
            y=20,
            width=300,
            height=30,
        ),
        _node(
            boundary,
            parent_id=None,
            flow="main",
            boundary=boundary,
            root_selector=None,
            role="group",
            name="controls-row",
            text="",
            x=20,
            y=60,
            width=available_width,
            height=64 if after else 40,
        ),
    ]
    width = (
        available_width
        if len(selectors) == 1
        else (available_width - 20) // 2
    )
    for index, selector in enumerate(selectors):
        session_key = selector.removeprefix(".st-key-")
        root_id = _matrix_root_id(prefix, session_key)
        root_height = 64 if after and index == 0 else 40
        x = 20 if index == 0 else 40 + width
        nodes.append(
            _node(
                root_id,
                parent_id=boundary,
                flow="main",
                boundary=boundary,
                root_selector=selector,
                role="radiogroup" if after else "group",
                name=session_key,
                text="",
                x=x,
                y=60,
                width=width,
                height=root_height,
            )
        )
    boundary_note = _node(
        f"{prefix}-boundary-note",
        parent_id=boundary,
        flow="main",
        boundary=boundary,
        root_selector=None,
        role="note",
        name="Stable boundary metadata",
        text="Stable boundary metadata",
        x=20,
        y=60,
        width=0,
        height=0,
    )
    boundary_note["visible"] = False
    nodes.append(boundary_note)
    for index, selector in enumerate(selectors):
        session_key = selector.removeprefix(".st-key-")
        root_id = _matrix_root_id(prefix, session_key)
        child = _node(
            _matrix_child_id(prefix, session_key, after=after),
            parent_id=root_id,
            flow="main",
            boundary=boundary,
            root_selector=None,
            role="radio" if after else "button",
            name=session_key,
            text=session_key,
            x=24 if index == 0 else 44 + width,
            y=64,
            width=70,
            height=24,
        )
        if after:
            child["state"] = {"checked": True, "tabIndex": 0}
        nodes.append(child)
    nodes.extend(
        [
            _node(
                f"{prefix}-body-1",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="paragraph",
                name="Summary",
                text="Stable summary",
                x=20,
                y=120 + delta,
                width=350,
                height=30,
            ),
            _node(
                f"{prefix}-body-2",
                parent_id=None,
                flow="main",
                boundary=None,
                root_selector=None,
                role="table",
                name="Results",
                text="Stable results",
                x=20,
                y=170 + delta,
                width=350,
                height=100,
            ),
            _node(
                f"{prefix}-sidebar",
                parent_id=None,
                flow="sidebar",
                boundary=None,
                root_selector=None,
                role="navigation",
                name="Navigation",
                text="Menu",
                x=0,
                y=0,
                width=15,
                height=300,
            ),
        ]
    )
    return nodes


def _matrix_stable_state(row: dict, *, after: bool) -> dict:
    prefix = _matrix_prefix(row)
    controls = {
        _matrix_child_id(
            prefix, selector.removeprefix(".st-key-"), after=after
        ): {"semantic": "migrated" if after else "legacy"}
        for selector in row["rootSelectors"]
    }
    controls[f"{prefix}-stable-filter"] = {"selected": False}
    return {
        "view": "stable",
        "labels": "stable",
        "controls": controls,
    }


def _migration_manifest(
    *, mode: str, after: bool, phase: str | None = None
) -> dict:
    fixture_entrypoint = {
        "ux1b-full-pages": "scripts/ui_ux_fixture_app.py",
        "ux1b-selection-controls": "scripts/ui_ux_selection_fixture_app.py",
        "ux1b-theme": "scripts/ui_ux_theme_fixture_app.py",
    }[mode]
    rows = evidence.worker_capture_profile_rows(fixture_entrypoint)
    captures = []
    for row in rows:
        capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
        captures.append(
            {
                "id": capture_id,
                "case": row["case"],
                "viewport": copy.deepcopy(row["viewport"]),
                "identity": {
                    "route": row["route"],
                    "callable": row["callable"],
                },
                "providerCounters": {"fixture.graph.load": 1},
                "mutatorCounters": {"mutator.fixture.graph.mutate": 0},
                "stableState": _matrix_stable_state(row, after=after),
                "controlEvidence": (
                    _focused_control_evidence(row, accessible=after)
                    if mode == "ux1b-selection-controls"
                    else None
                ),
                "render": {"nodes": _matrix_render_nodes(row, after=after)},
            }
        )
    if phase is None:
        phase = {
            "ux1b-full-pages": "pretheme" if after else "precontrol",
            "ux1b-selection-controls": "postcontrol" if after else "precontrol",
            "ux1b-theme": "pretheme",
        }[mode]
    return {
        "status": "passed",
        "mode": mode,
        "phase": phase,
        "captureStackDigest": _complete_control_catalog()["captureStackDigest"],
        "sourceDigestStart": SOURCE_DIGEST,
        "sourceDigestEnd": SOURCE_DIGEST,
        "captures": captures,
    }


def _migration_catalog() -> dict:
    return _complete_control_catalog()


FOCUSED_CONTROL_ROOTS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "risk-guard-controls": (
        ("rg_source", ".st-key-rg_source", "main", "risk-guard-controls-primary-control"),
    ),
    "institutions-controls": (
        ("inst_view", ".st-key-inst_view", "main", "institutions-controls-primary-control"),
    ),
    "options-cockpit-controls": (
        (
            "cockpit_price_view_NVDA",
            ".st-key-cockpit_price_view_NVDA",
            "main",
            "options-cockpit-controls-primary-control",
        ),
    ),
    "radar-controls": (
        ("radar_source", ".st-key-radar_source", "main", "radar-controls-primary-control"),
        ("radar_view", ".st-key-radar_view", "main", "radar-controls-primary-control"),
    ),
    "knowledge-graph-controls": (
        ("kg_view_mode", ".st-key-kg_view_mode", "main", "knowledge-graph-controls-mode-row"),
        ("kg_label_mode", ".st-key-kg_label_mode", "main", "knowledge-graph-controls-mode-row"),
    ),
    "ai-chat-settings-controls": (
        ("ai_chat_mode", ".st-key-ai_chat_mode", "main", "ai-chat-settings-controls-primary-control"),
    ),
    "retro-controls": (
        ("retro_validation_lane", ".st-key-retro_validation_lane", "main", "retro-controls-primary-control"),
    ),
    "analytics-controls": (
        ("adb_table", ".st-key-adb_table", "main", "analytics-controls-primary-control"),
    ),
    "stock-checkup-controls": (
        ("checkup_mode", ".st-key-checkup_mode", "main", "stock-checkup-controls-primary-control"),
    ),
}
FULL_PAGE_CONTROL_ROOTS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "stock-checkup": (
        ("checkup_mode", ".st-key-checkup_mode", "main", "stock-checkup-primary-control"),
    ),
    "options-cockpit": (
        (
            "cockpit_price_view_NVDA",
            ".st-key-cockpit_price_view_NVDA",
            "main",
            "options-cockpit-primary-control",
        ),
    ),
    "radar": (
        ("radar_source", ".st-key-radar_source", "main", "radar-primary-control"),
        ("radar_view", ".st-key-radar_view", "main", "radar-primary-control"),
    ),
    "retro-analysis": (
        ("retro_validation_lane", ".st-key-retro_validation_lane", "main", "retro-analysis-primary-control"),
    ),
    "analytics-db": (
        ("adb_table", ".st-key-adb_table", "main", "analytics-db-primary-control"),
    ),
    "knowledge-graph": (
        ("kg_view_mode", ".st-key-kg_view_mode", "main", "knowledge-graph-mode-row"),
        ("kg_label_mode", ".st-key-kg_label_mode", "main", "knowledge-graph-mode-row"),
    ),
    "institutions": (
        ("inst_view", ".st-key-inst_view", "main", "institutions-primary-control"),
    ),
}
CONTROL_VIEWPORTS = (
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
    ("narrow", 320, 844),
)


def _control_root_identities(
    source: dict[str, tuple[tuple[str, str, str, str], ...]]
) -> dict[str, tuple[tuple[str, str], ...]]:
    return {
        case: tuple((session_key, selector) for session_key, selector, _flow, _boundary in roots)
        for case, roots in source.items()
    }


FOCUSED_CONTROL_IDENTITIES = _control_root_identities(FOCUSED_CONTROL_ROOTS)
FULL_PAGE_CONTROL_IDENTITIES = _control_root_identities(FULL_PAGE_CONTROL_ROOTS)


def _complete_control_catalog() -> dict:
    def cases(
        source: dict[str, tuple[tuple[str, str, str, str], ...]]
    ) -> dict:
        result: dict[str, dict] = {}
        for case, roots in source.items():
            result[case] = {
                "roots": [
                    {
                        "sessionKey": session_key,
                        "rootSelector": selector,
                        "flowScope": "main",
                        "boundaryId": _test_dom_boundary(case),
                    }
                    for session_key, selector, flow_scope, boundary_id in roots
                ]
            }
        return result

    document = {
        "schemaVersion": "quant-radar-ui-ux-control-catalog/v1",
        "baseCaptureStackDigest": STACK_DIGEST,
        "captureStackDigest": "0" * 64,
        "viewports": [
            {"name": name, "width": width, "height": height}
            for name, width, height in CONTROL_VIEWPORTS
        ],
        "focusedCases": cases(FOCUSED_CONTROL_ROOTS),
        "fullPageCases": cases(FULL_PAGE_CONTROL_ROOTS),
    }
    document["captureStackDigest"] = evidence.control_catalog_digest(document)
    return document


def _discovery_raw_sidecar(row: dict) -> dict:
    document = {
        "schemaVersion": RENDER_SCHEMA,
        "identity": {
            "case": row["case"],
            "route": row["route"],
            "callable": row["callable"],
        },
        "viewport": copy.deepcopy(row["viewport"]),
        "readiness": {"ready": True, "marker": row["readiness"]["text"]},
        "nodes": _matrix_render_nodes(row, after=False),
        "stableState": _matrix_stable_state(row, after=False),
        "providerCounters": {},
        "mutatorCounters": {},
        "runtimeProjection": {
            "sourceRoot": "/private/tmp/ux1b-discovery-source",
            "browserScratchRoot": "/private/tmp/ux1b-discovery-browser",
        },
    }
    if (
        row["fixtureEntrypoint"]
        == "scripts/ui_ux_selection_fixture_app.py"
    ):
        document["controlEvidence"] = _focused_control_evidence(
            row, accessible=False
        )
    return document


def _authenticate_discovery_matrix(
    root: Path,
) -> tuple[list[object], list[dict]]:
    rows = [
        row
        for entrypoint in (
            "scripts/ui_ux_fixture_app.py",
            "scripts/ui_ux_selection_fixture_app.py",
        )
        for row in evidence.worker_capture_profile_rows(entrypoint)
        if row["rootSelectors"]
    ]
    root_fd = _root_fd(root)
    attestations: list[object] = []
    try:
        for index, row in enumerate(rows):
            raw = evidence.canonicalize_worker_render_sidecar(
                _discovery_raw_sidecar(row),
                owned_roots=(
                    "/private/tmp/ux1b-discovery-source",
                    "/private/tmp/ux1b-discovery-browser",
                ),
            )
            name = f"discovery/{index}.render.json"
            _write(root / name, raw)
            attestations.append(
                evidence.authenticate_raw_render_sidecar(
                    root_fd,
                    name,
                    expected_owner=OWNER,
                    identity_row=row,
                )
            )
    finally:
        os.close(root_fd)
    return attestations, rows


def test_control_catalog_is_complete_and_exact() -> None:
    catalog = _complete_control_catalog()
    summary = evidence.validate_control_catalog(
        catalog,
        expected_focused_roots=FOCUSED_CONTROL_IDENTITIES,
        expected_full_page_roots=FULL_PAGE_CONTROL_IDENTITIES,
        expected_viewports=CONTROL_VIEWPORTS,
        expected_base_capture_stack_digest=STACK_DIGEST,
    )
    if summary != {
        "focusedCaseCount": 9,
        "fullPageCaseCount": 7,
        "stableRootCount": 11,
        "viewportCount": 4,
    }:
        raise AssertionError(summary)

    def remove_focused_case(value: dict) -> None:
        value["focusedCases"].pop("risk-guard-controls")

    def remove_root(value: dict) -> None:
        value["focusedCases"]["radar-controls"]["roots"].pop()

    def add_unknown_root(value: dict) -> None:
        value["focusedCases"]["radar-controls"]["roots"].append(
            {
                "sessionKey": "unknown",
                "rootSelector": ".st-key-unknown",
                "flowScope": "main",
                "boundaryId": "radar-controls-primary-control",
            }
        )

    def duplicate_root(value: dict) -> None:
        roots = value["focusedCases"]["radar-controls"]["roots"]
        roots.append(copy.deepcopy(roots[0]))

    def remove_viewport(value: dict) -> None:
        value["viewports"].pop()

    def mutate_flow(value: dict) -> None:
        value["focusedCases"]["radar-controls"]["roots"][0][
            "flowScope"
        ] = "sidebar"

    def mutate_boundary(value: dict) -> None:
        value["fullPageCases"]["knowledge-graph"]["roots"][0][
            "boundaryId"
        ] = "dom-forged"

    for mutate in (
        remove_focused_case,
        remove_root,
        add_unknown_root,
        duplicate_root,
        remove_viewport,
        mutate_flow,
        mutate_boundary,
    ):
        candidate = _complete_control_catalog()
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.validate_control_catalog(
                candidate,
                expected_focused_roots=FOCUSED_CONTROL_IDENTITIES,
                expected_full_page_roots=FULL_PAGE_CONTROL_IDENTITIES,
                expected_viewports=CONTROL_VIEWPORTS,
                expected_base_capture_stack_digest=STACK_DIGEST,
            ),
        )

    with tempfile.TemporaryDirectory() as temp:
        substitution_root = Path(temp)
        catalog_path = substitution_root / "control-catalog.json"
        trusted = _complete_control_catalog()
        trusted_raw = _json_line(trusted).rstrip(b"\n")
        trusted_sha256 = _sha256(trusted_raw)
        _write(catalog_path, trusted_raw)
        root_fd = _root_fd(substitution_root)
        try:
            authenticated = evidence.authenticate_control_catalog(
                root_fd,
                "control-catalog.json",
                expected_owner=OWNER,
                expected_base_capture_stack_digest=STACK_DIGEST,
                expected_capture_stack_digest=trusted["captureStackDigest"],
                expected_catalog_sha256=trusted_sha256,
            )
            if not isinstance(authenticated, evidence.AuthenticatedControlCatalog):
                raise AssertionError(type(authenticated).__name__)
        finally:
            os.close(root_fd)

        forged = copy.deepcopy(trusted)
        forged_base_digest = "b" * 64
        forged["baseCaptureStackDigest"] = forged_base_digest
        forged["captureStackDigest"] = evidence.control_catalog_digest(forged)
        evidence.validate_control_catalog(
            forged,
            expected_focused_roots=FOCUSED_CONTROL_IDENTITIES,
            expected_full_page_roots=FULL_PAGE_CONTROL_IDENTITIES,
            expected_viewports=CONTROL_VIEWPORTS,
            expected_base_capture_stack_digest=forged_base_digest,
        )
        forged_raw = _json_line(forged).rstrip(b"\n")
        forged_sha256 = _sha256(forged_raw)
        subprocess.run(
            (
                sys.executable,
                "-c",
                "import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(bytes.fromhex(sys.argv[2]))",
                str(catalog_path),
                forged_raw.hex(),
            ),
            check=True,
        )
        root_fd = _root_fd(substitution_root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_control_catalog(
                    root_fd,
                    "control-catalog.json",
                    expected_owner=OWNER,
                    expected_base_capture_stack_digest=forged_base_digest,
                    expected_capture_stack_digest=forged["captureStackDigest"],
                    expected_catalog_sha256=trusted_sha256,
                ),
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_control_catalog(
                    root_fd,
                    "control-catalog.json",
                    expected_owner=OWNER,
                    expected_base_capture_stack_digest=forged_base_digest,
                    expected_capture_stack_digest=trusted["captureStackDigest"],
                    expected_catalog_sha256=forged_sha256,
                ),
            )
            forged_authenticated = evidence.authenticate_control_catalog(
                root_fd,
                "control-catalog.json",
                expected_owner=OWNER,
                expected_base_capture_stack_digest=forged_base_digest,
                expected_capture_stack_digest=forged["captureStackDigest"],
                expected_catalog_sha256=forged_sha256,
            )
            if not isinstance(
                forged_authenticated, evidence.AuthenticatedControlCatalog
            ):
                raise AssertionError("well-formed substituted catalog was not valid")
        finally:
            os.close(root_fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        discovery, rows = _authenticate_discovery_matrix(root)
        if len(discovery) != 57:
            raise AssertionError(len(discovery))
        authenticated = evidence.derive_control_catalog(
            discovery, base_capture_stack_digest=STACK_DIGEST
        )
        if not isinstance(authenticated, evidence.AuthenticatedControlCatalog):
            raise AssertionError(type(authenticated).__name__)
        if {key: authenticated[key] for key in authenticated} != catalog:
            raise AssertionError("derived catalog differs from complete matrix")
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.derive_control_catalog(
                discovery[:-1], base_capture_stack_digest=STACK_DIGEST
            ),
        )
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.derive_control_catalog(
                discovery + [discovery[0]],
                base_capture_stack_digest=STACK_DIGEST,
            ),
        )

        mutation_index = next(
            index
            for index, row in enumerate(rows)
            if row["case"] == "knowledge-graph"
            and row["viewport"]["name"] == "mobile"
        )
        mutated_document = _discovery_raw_sidecar(rows[mutation_index])
        old_boundary = _test_dom_boundary("knowledge-graph")
        new_boundary = "dom-viewport-variant"
        for node in mutated_document["nodes"]:
            if node["id"] == old_boundary:
                node["id"] = new_boundary
            if node["parentId"] == old_boundary:
                node["parentId"] = new_boundary
            if node["boundaryId"] == old_boundary:
                node["boundaryId"] = new_boundary
        mutated_raw = evidence.canonicalize_worker_render_sidecar(
            mutated_document,
            owned_roots=(
                "/private/tmp/ux1b-discovery-source",
                "/private/tmp/ux1b-discovery-browser",
            ),
        )
        _write(root / "discovery/variant.render.json", mutated_raw)
        root_fd = _root_fd(root)
        try:
            variant = evidence.authenticate_raw_render_sidecar(
                root_fd,
                "discovery/variant.render.json",
                expected_owner=OWNER,
                identity_row=rows[mutation_index],
            )
        finally:
            os.close(root_fd)
        variant_matrix = list(discovery)
        variant_matrix[mutation_index] = variant
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.derive_control_catalog(
                variant_matrix, base_capture_stack_digest=STACK_DIGEST
            ),
        )


def _migration_inputs() -> dict[str, dict]:
    return {
        "before_pages": _migration_manifest(mode="ux1b-full-pages", after=False),
        "after_pages": _migration_manifest(mode="ux1b-full-pages", after=True),
        "before_controls": _migration_manifest(
            mode="ux1b-selection-controls", after=False
        ),
        "after_controls": _migration_manifest(
            mode="ux1b-selection-controls", after=True
        ),
        "catalog": _migration_catalog(),
    }


def _authenticate_migration_manifest(document: dict) -> object:
    fixture_entrypoint = {
        "ux1b-full-pages": "scripts/ui_ux_fixture_app.py",
        "ux1b-selection-controls": "scripts/ui_ux_selection_fixture_app.py",
        "ux1b-theme": "scripts/ui_ux_theme_fixture_app.py",
    }[document["mode"]]
    frozen_rows = {
        f'{row["case"]}/{row["viewport"]["name"]}': row
        for row in evidence.worker_capture_profile_rows(fixture_entrypoint)
    }
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        manifest_captures = []
        for index, capture in enumerate(document["captures"]):
            capture_id = capture["id"]
            if capture_id not in frozen_rows:
                raise evidence.EvidenceContractError(
                    "test migration capture is outside the frozen profile"
                )
            frozen = frozen_rows[capture_id]
            if document["mode"] == "ux1b-theme":
                capture_root = root / "captures" / str(index)
                capture_root.mkdir(parents=True)
                record = _capture_record(capture_root, identity_row=frozen)
                supplements = _publish_theme_supplements(capture_root, record)
                prefix = capture_root.relative_to(root).as_posix()
                artifacts = copy.deepcopy(record)
                artifacts["png"]["path"] = (
                    f'{prefix}/{artifacts["png"]["path"]}'
                )
                artifacts["renderSidecar"]["path"] = (
                    f'{prefix}/{artifacts["renderSidecar"]["path"]}'
                )
                for supplement in supplements:
                    supplement["path"] = f'{prefix}/{supplement["path"]}'
                artifacts["supplementalArtifacts"] = supplements
                manifest_captures.append(
                    {
                        "id": capture_id,
                        "status": "passed",
                        "artifacts": artifacts,
                    }
                )
                continue
            sidecar = {
                "schemaVersion": RENDER_SCHEMA,
                "identity": {
                    "case": capture["case"],
                    "route": capture["identity"]["route"],
                    "callable": capture["identity"]["callable"],
                },
                "viewport": copy.deepcopy(capture["viewport"]),
                "readiness": {"ready": True, "marker": "matrix-ready"},
                "nodes": copy.deepcopy(capture["render"]["nodes"]),
                "stableState": copy.deepcopy(capture["stableState"]),
                "providerCounters": copy.deepcopy(capture["providerCounters"]),
                "mutatorCounters": copy.deepcopy(capture["mutatorCounters"]),
                "runtimeProjection": {
                    "sourceRoot": "$OWNED_ROOT_0",
                    "browserScratchRoot": "$OWNED_ROOT_1",
                },
                "counterProvenance": {
                    "schemaVersion": "quant-radar-ui-ux-counter-enrichment/v1",
                    "counterDocumentSha256": "a" * 64,
                    "captureId": capture_id,
                    "registryKey": frozen["registryKey"],
                },
            }
            if capture["controlEvidence"] is not None:
                sidecar["controlEvidence"] = copy.deepcopy(
                    capture["controlEvidence"]
                )
            sidecar_raw = evidence.canonicalize_render_sidecar(
                sidecar, owned_roots=()
            )
            png_raw = _viewport_png(capture["viewport"])
            png_path = f"captures/{index}.png"
            sidecar_path = f"captures/{index}.render.json"
            _write(root / png_path, png_raw)
            _write(root / sidecar_path, sidecar_raw)
            manifest_captures.append(
                {
                    "id": capture_id,
                    "status": "passed",
                    "artifacts": {
                        "png": {
                            "path": png_path,
                            "sha256": _sha256(png_raw),
                            "size": len(png_raw),
                            "width": capture["viewport"]["width"],
                            "height": capture["viewport"]["height"],
                        },
                        "renderSidecar": {
                            "path": sidecar_path,
                            "sha256": _sha256(sidecar_raw),
                            "size": len(sidecar_raw),
                            "schemaVersion": RENDER_SCHEMA,
                        },
                    },
                }
            )
        manifest = {
            "schemaVersion": "quant-radar-ui-ux-evidence/v1",
            "status": "passed",
            "mode": document["mode"],
            "phase": document["phase"],
            "runId": f'matrix-{document["mode"]}',
            "captureStackDigest": document["captureStackDigest"],
            "sourceDigestStart": document["sourceDigestStart"],
            "sourceDigestEnd": document["sourceDigestEnd"],
            "captures": manifest_captures,
        }
        manifest_raw = _json_line(manifest)
        _write(root / "manifest.json", manifest_raw)
        root_fd = _root_fd(root)
        try:
            contract = evidence.freeze_manifest_bundle_contract(
                root_fd,
                "manifest.json",
                expected_owner=OWNER,
                expected_manifest_sha256=_sha256(manifest_raw),
            )
            return evidence.reauthenticate_manifest_bundle(root_fd, contract)
        finally:
            os.close(root_fd)


def _authenticate_control_catalog_document(
    document: dict,
    *,
    expected_capture_stack_digest: str | None = None,
    expected_catalog_sha256: str | None = None,
) -> object:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        raw = _json_line(document).rstrip(b"\n")
        trusted_raw = _json_line(_complete_control_catalog()).rstrip(b"\n")
        _write(root / "control-catalog.json", raw)
        root_fd = _root_fd(root)
        try:
            return evidence.authenticate_control_catalog(
                root_fd,
                "control-catalog.json",
                expected_owner=OWNER,
                expected_base_capture_stack_digest=STACK_DIGEST,
                expected_capture_stack_digest=(
                    expected_capture_stack_digest
                    or _complete_control_catalog()["captureStackDigest"]
                ),
                expected_catalog_sha256=(
                    expected_catalog_sha256 or _sha256(trusted_raw)
                ),
            )
        finally:
            os.close(root_fd)


def _compare(inputs: dict[str, dict]) -> dict:
    return evidence.compare_control_migration(
        before_pages=_authenticate_migration_manifest(inputs["before_pages"]),
        after_pages=_authenticate_migration_manifest(inputs["after_pages"]),
        before_controls=_authenticate_migration_manifest(inputs["before_controls"]),
        after_controls=_authenticate_migration_manifest(inputs["after_controls"]),
        catalog=_authenticate_control_catalog_document(inputs["catalog"]),
    )


def _find_node(manifest: dict, node_id: str) -> dict:
    for capture in manifest["captures"]:
        for node in capture["render"]["nodes"]:
            if node["id"] == node_id:
                return node
    raise AssertionError(node_id)


def _find_capture_with_node(manifest: dict, node_id: str) -> dict:
    for capture in manifest["captures"]:
        if any(node["id"] == node_id for node in capture["render"]["nodes"]):
            return capture
    raise AssertionError(node_id)


def test_migration_comparator_accepts_shared_boundary_translation_once() -> None:
    report = _compare(_migration_inputs())
    if report.get("status") != "passed":
        raise AssertionError(report)
    if report.get("comparedCaptures") != 117:
        raise AssertionError(report)
    if report.get("captureStackDigest") != _complete_control_catalog()[
        "captureStackDigest"
    ]:
        raise AssertionError(report)
    translations = report.get("allowedBoundaryTranslations")
    if not isinstance(translations, list) or len(translations) != 57:
        raise AssertionError(report)
    observed = {
        (
            item.get("case"),
            item.get("captureId"),
            item.get("flowScope"),
            item.get("boundaryId"),
            item.get("deltaY"),
        )
        for item in translations
    }
    expected = {
        (
            "knowledge-graph",
            "knowledge-graph/mobile",
            "main",
            _test_dom_boundary("knowledge-graph"),
            24,
        ),
        (
            "knowledge-graph-controls",
            "knowledge-graph-controls/mobile",
            "main",
            _test_dom_boundary("knowledge-graph-controls"),
            24,
        ),
    }
    if not expected.issubset(observed):
        raise AssertionError(translations)
    comparator = evidence.mint_comparator_attestation(report)
    if not isinstance(comparator, evidence.ComparatorAttestation):
        raise AssertionError(type(comparator).__name__)
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.mint_comparator_attestation(copy.deepcopy(report)),
    )

    raced_report = _compare(_migration_inputs())
    registered_snapshot = copy.deepcopy(raced_report)
    started = threading.Event()
    race_result: list[object] = []

    def mint_during_mutation() -> None:
        started.set()
        try:
            race_result.append(evidence.mint_comparator_attestation(raced_report))
        except BaseException as exc:
            race_result.append(exc)

    with evidence._COMPARATOR_REPORTS_LOCK:
        mint_thread = threading.Thread(target=mint_during_mutation)
        mint_thread.start()
        if not started.wait(timeout=1.0):
            raise AssertionError("comparator mint race did not reach its lock")
        raced_report["status"] = "failed"
        raced_report["coveredProfiles"] = []
        raced_report["captureStackDigest"] = "e" * 64
    mint_thread.join(timeout=2.0)
    if mint_thread.is_alive():
        raise AssertionError("comparator mint race did not finish")
    if len(race_result) != 1 or not isinstance(
        race_result[0], evidence.ComparatorAttestation
    ):
        raise AssertionError(race_result)
    if evidence._attestation_digest(
        race_result[0], calibration=False
    ) != hashlib.sha256(
        evidence._canonical_json_bytes(registered_snapshot)
    ).hexdigest():
        raise AssertionError("comparator attestation did not bind the registered snapshot")
    if evidence._comparator_attestation_profile_binding(race_result[0]) != (
        tuple(registered_snapshot["coveredProfiles"]),
        registered_snapshot["captureStackDigest"],
    ):
        raise AssertionError("comparator attestation profile binding raced")
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.mint_comparator_attestation(raced_report),
    )

    below_fold = _migration_inputs()
    for key in ("before_controls", "after_controls"):
        capture = _find_capture_with_node(below_fold[key], "focused-body-1")
        for node in capture["render"]["nodes"]:
            if (
                node["id"] == _test_dom_boundary("knowledge-graph-controls")
                or node["id"].startswith("focused-")
                and node["id"] != "focused-title"
            ):
                node["bounds"]["y"] += 1_000
    below_fold_report = _compare(below_fold)
    if below_fold_report.get("status") != "passed":
        raise AssertionError(below_fold_report)

    genuine_outer_ancestor = _migration_inputs()
    boundary_id = _test_dom_boundary("knowledge-graph-controls")
    for key in ("before_controls", "after_controls"):
        _find_node(genuine_outer_ancestor[key], boundary_id)["parentId"] = (
            "focused-title"
        )
        _find_node(genuine_outer_ancestor[key], "focused-title")["bounds"] = {
            "x": 20,
            "y": 20,
            "width": 350,
            "height": 104,
        }
    genuine_outer_report = _compare(genuine_outer_ancestor)
    if genuine_outer_report.get("status") != "passed":
        raise AssertionError(genuine_outer_report)

    baseline_bundle = _authenticate_migration_manifest(
        _migration_inputs()["before_pages"]
    )
    baseline_report = evidence.validate_baseline_evidence(
        baseline_bundle,
        fixture_entrypoint="scripts/ui_ux_fixture_app.py",
    )
    if baseline_report.get("captureCount") != 81:
        raise AssertionError(baseline_report)
    baseline_attestation = evidence.mint_comparator_attestation(baseline_report)
    if not isinstance(baseline_attestation, evidence.ComparatorAttestation):
        raise AssertionError(type(baseline_attestation).__name__)

    plain_inputs = _migration_inputs()
    authenticated_catalog = _authenticate_control_catalog_document(
        plain_inputs["catalog"]
    )
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.compare_control_migration(
            before_pages=plain_inputs["before_pages"],
            after_pages=plain_inputs["after_pages"],
            before_controls=plain_inputs["before_controls"],
            after_controls=plain_inputs["after_controls"],
            catalog=authenticated_catalog,
        ),
    )
    forged_bundle = object.__new__(evidence.AuthenticatedManifestBundle)
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.compare_control_migration(
            before_pages=forged_bundle,
            after_pages=plain_inputs["after_pages"],
            before_controls=plain_inputs["before_controls"],
            after_controls=plain_inputs["after_controls"],
            catalog=authenticated_catalog,
        ),
    )
    forged_catalog = object.__new__(evidence.AuthenticatedControlCatalog)
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence.compare_control_migration(
            before_pages=forged_bundle,
            after_pages=forged_bundle,
            before_controls=forged_bundle,
            after_controls=forged_bundle,
            catalog=forged_catalog,
        ),
    )


def test_migration_comparator_rejects_unauthorized_and_unmapped_changes() -> None:
    def unauthorized_sibling(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-body-1")["text"] = "Changed"

    def nonuniform_translation(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-body-2")["bounds"]["y"] -= 1

    def excessive_shared_boundary_translation(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-body-1")["bounds"]["y"] += 24
        _find_node(inputs["after_controls"], "focused-body-2")["bounds"]["y"] += 24

    def node_before_boundary_moves(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-title")["bounds"]["y"] += 24

    def unauthorized_boundary_subtree(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-boundary-note")["text"] = (
            "Changed"
        )

    def semantic_state_drift(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-body-1")["state"][
            "selected"
        ] = True

    def stable_geometry_drift(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-body-1")["bounds"]["x"] += 1

    def stable_role_name_drift(inputs: dict[str, dict]) -> None:
        node = _find_node(inputs["after_controls"], "focused-body-1")
        node["role"] = "heading"
        node["name"] = "Changed"

    def stable_dom_order_drift(inputs: dict[str, dict]) -> None:
        nodes = _find_capture_with_node(
            inputs["after_controls"], "focused-body-1"
        )["render"]["nodes"]
        first = next(i for i, node in enumerate(nodes) if node["id"] == "focused-body-1")
        second = next(i for i, node in enumerate(nodes) if node["id"] == "focused-body-2")
        nodes[first], nodes[second] = nodes[second], nodes[first]

    def allowed_subtree_clips_root(inputs: dict[str, dict]) -> None:
        node = _find_node(inputs["after_controls"], "focused-view-radio")
        node["bounds"]["x"] = 170
        node["bounds"]["width"] = 70

    def allowed_subtrees_overlap(inputs: dict[str, dict]) -> None:
        node = _find_node(inputs["after_controls"], "focused-view-radio")
        node["bounds"]["x"] = 209

    def allowed_subtree_overflows_viewport(inputs: dict[str, dict]) -> None:
        node = _find_node(inputs["after_controls"], "focused-view-radio")
        node["bounds"]["x"] = 380
        node["bounds"]["width"] = 70

    def allowed_root_overlaps_stable_sibling(inputs: dict[str, dict]) -> None:
        boundary_id = _test_dom_boundary("knowledge-graph-controls")
        for key in ("before_controls", "after_controls"):
            _find_node(inputs[key], boundary_id)["bounds"]["height"] = 64
            _find_node(inputs[key], "focused-view-root")["bounds"]["height"] = 64
            sibling = _find_node(inputs[key], "focused-body-1")
            sibling["bounds"]["y"] = 105
            sibling["bounds"]["height"] = 10
        _find_node(inputs["after_controls"], "focused-body-2")["bounds"]["y"] = 170

    def ordinary_boundary_child_is_clipped(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            node = _find_node(inputs[key], "focused-boundary-note")
            node["visible"] = True
            node["bounds"] = {"x": 10, "y": 65, "width": 5, "height": 5}

    def ordinary_boundary_child_omits_boundary(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            node = _find_node(inputs[key], "focused-boundary-note")
            node["boundaryId"] = None
            node["visible"] = True
            node["bounds"] = {"x": 10, "y": 65, "width": 5, "height": 5}

    def catalog_boundary_is_not_actual_ancestor(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            for node_id in (
                "focused-view-root",
                "focused-label-root",
                "focused-boundary-note",
            ):
                _find_node(inputs[key], node_id)["parentId"] = "focused-title"
            _find_node(inputs[key], "focused-title")["bounds"] = {
                "x": 20,
                "y": 20,
                "width": 350,
                "height": 104,
            }

    def catalog_boundary_clips_visible_outer_ancestor(
        inputs: dict[str, dict],
    ) -> None:
        boundary_id = _test_dom_boundary("knowledge-graph-controls")
        for key in ("before_controls", "after_controls"):
            boundary = _find_node(inputs[key], boundary_id)
            boundary["parentId"] = "focused-title"
            boundary["bounds"]["x"] = 0
            boundary["bounds"]["width"] = 390
            _find_node(inputs[key], "focused-title")["bounds"] = {
                "x": 20,
                "y": 20,
                "width": 350,
                "height": 104,
            }

    def cross_flow_overlap_with_allowed_root(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            ordinary = _find_node(inputs[key], "focused-boundary-note")
            ordinary["visible"] = True
            ordinary["flowScope"] = "forged-flow"
            ordinary["bounds"] = copy.deepcopy(
                _find_node(inputs[key], "focused-view-root")["bounds"]
            )

    def forged_nonancestor_boundary_skips_translation(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            _find_node(inputs[key], "focused-body-2")["boundaryId"] = (
                "focused-title"
            )
        _find_node(inputs["after_controls"], "focused-body-2")["bounds"]["y"] = 170

    def forged_flow_scope_skips_translation(inputs: dict[str, dict]) -> None:
        for key in ("before_controls", "after_controls"):
            _find_node(inputs[key], "focused-body-2")["flowScope"] = (
                "forged-flow"
            )
        _find_node(inputs["after_controls"], "focused-body-2")["bounds"]["y"] = 170

    def cross_flow_translation(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-sidebar")["bounds"]["y"] += 24

    def unmapped_full_page_root(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_pages"], "page-label-root")["rootSelector"] = (
            ".st-key-unmapped"
        )

    def provider_drift(inputs: dict[str, dict]) -> None:
        inputs["after_pages"]["captures"][0]["providerCounters"]["fixture.graph.load"] = 2

    def capture_stack_drift(inputs: dict[str, dict]) -> None:
        inputs["after_controls"]["captureStackDigest"] = "e" * 64

    def migration_phase_drift(inputs: dict[str, dict]) -> None:
        inputs["after_pages"]["phase"] = "posttheme"

    def stable_state_sibling_drift(inputs: dict[str, dict]) -> None:
        capture = _find_capture_with_node(
            inputs["after_controls"], "focused-body-1"
        )
        capture["stableState"]["controls"]["focused-stable-filter"][
            "selected"
        ] = True

    def mutator_drift(inputs: dict[str, dict]) -> None:
        capture = _find_capture_with_node(
            inputs["after_controls"], "focused-body-1"
        )
        capture["mutatorCounters"]["mutator.fixture.graph.mutate"] = 1

    def unknown_boundary_reference(inputs: dict[str, dict]) -> None:
        _find_node(inputs["after_controls"], "focused-view-radio")[
            "boundaryId"
        ] = "dom-missing"

    def recomputed_catalog_boundary_drift(inputs: dict[str, dict]) -> None:
        inputs["catalog"]["focusedCases"]["knowledge-graph-controls"][
            "roots"
        ][0]["boundaryId"] = "dom-recomputed-forgery"
        inputs["catalog"]["captureStackDigest"] = evidence.control_catalog_digest(
            inputs["catalog"]
        )
        for key in (
            "before_pages",
            "after_pages",
            "before_controls",
            "after_controls",
        ):
            inputs[key]["captureStackDigest"] = inputs["catalog"][
                "captureStackDigest"
            ]

    def recomputed_catalog_flow_drift(inputs: dict[str, dict]) -> None:
        inputs["catalog"]["focusedCases"]["knowledge-graph-controls"][
            "roots"
        ][0]["flowScope"] = "sidebar"
        inputs["catalog"]["captureStackDigest"] = evidence.control_catalog_digest(
            inputs["catalog"]
        )
        for key in (
            "before_pages",
            "after_pages",
            "before_controls",
            "after_controls",
        ):
            inputs[key]["captureStackDigest"] = inputs["catalog"][
                "captureStackDigest"
            ]

    def missing_capture(inputs: dict[str, dict]) -> None:
        inputs["after_controls"]["captures"].pop()

    for mutate in (
        unauthorized_sibling,
        nonuniform_translation,
        excessive_shared_boundary_translation,
        node_before_boundary_moves,
        unauthorized_boundary_subtree,
        semantic_state_drift,
        stable_geometry_drift,
        stable_role_name_drift,
        stable_dom_order_drift,
        allowed_subtree_clips_root,
        allowed_subtrees_overlap,
        allowed_subtree_overflows_viewport,
        allowed_root_overlaps_stable_sibling,
        ordinary_boundary_child_is_clipped,
        ordinary_boundary_child_omits_boundary,
        catalog_boundary_is_not_actual_ancestor,
        catalog_boundary_clips_visible_outer_ancestor,
        cross_flow_overlap_with_allowed_root,
        forged_nonancestor_boundary_skips_translation,
        forged_flow_scope_skips_translation,
        cross_flow_translation,
        unmapped_full_page_root,
        provider_drift,
        capture_stack_drift,
        migration_phase_drift,
        stable_state_sibling_drift,
        mutator_drift,
        unknown_boundary_reference,
        recomputed_catalog_boundary_drift,
        recomputed_catalog_flow_drift,
        missing_capture,
    ):
        inputs = _migration_inputs()
        mutate(inputs)
        error = _raises(
            evidence.EvidenceContractError,
            lambda inputs=inputs: _compare(inputs),
        )
        if (
            mutate is catalog_boundary_clips_visible_outer_ancestor
            and "shared boundary clips its visible ancestor" not in str(error)
        ):
            raise AssertionError(error)


def test_focused_control_contract_is_exact_and_mutation_closed() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    worker_rows = browser_worker.worker_control_contract_rows()
    trusted_rows = evidence.focused_control_contract_rows()
    if worker_rows != trusted_rows:
        raise AssertionError("browser and trusted focused control catalogs differ")
    controls = [control for row in trusted_rows for control in row["controls"]]
    if (
        len(trusted_rows) != 9
        or len(controls) != 11
        or len({control["rootSelector"] for control in controls}) != 11
        or sum(control["replacementWidget"] == "radio_horizontal" for control in controls)
        != 10
        or sum(control["replacementWidget"] == "selectbox" for control in controls)
        != 1
    ):
        raise AssertionError(trusted_rows)
    auxiliary_catalog = [
        (row["case"], control["sessionKey"], control["auxiliaryButtons"])
        for row in trusted_rows
        for control in row["controls"]
        if control["auxiliaryButtons"]
    ]
    if auxiliary_catalog != [
        ("ai-chat-settings-controls", "ai_chat_mode", ("Help for 模式",))
    ]:
        raise AssertionError(auxiliary_catalog)

    identity = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == "knowledge-graph-controls"
        and row["viewport"]["name"] == "mobile"
    )
    valid = _focused_control_evidence(identity, accessible=True)
    normalized = evidence._validate_focused_control_evidence(
        valid,
        expected_case=identity["case"],
        expected_viewport=identity["viewport"],
    )
    if normalized != valid:
        raise AssertionError("valid focused evidence was not canonical")

    legacy_shared_border = _focused_control_evidence(identity, accessible=False)
    legacy_targets = legacy_shared_border["controls"][0]["targets"]
    legacy_targets[1]["x"] = (
        legacy_targets[0]["x"] + legacy_targets[0]["width"] - 1.0
    )
    evidence._validate_focused_control_evidence(
        legacy_shared_border,
        expected_case=identity["case"],
        expected_viewport=identity["viewport"],
    )
    excessive_legacy_overlap = copy.deepcopy(legacy_shared_border)
    excessive_legacy_overlap["controls"][0]["targets"][1]["x"] -= 0.001
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._validate_focused_control_evidence(
            excessive_legacy_overlap,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
        ),
    )

    accessible_shared_border = _focused_control_evidence(identity, accessible=True)
    accessible_targets = accessible_shared_border["controls"][0]["targets"]
    accessible_targets[1]["x"] = (
        accessible_targets[0]["x"] + accessible_targets[0]["width"] - 0.5
    )
    evidence._validate_focused_control_evidence(
        accessible_shared_border,
        expected_case=identity["case"],
        expected_viewport=identity["viewport"],
    )
    excessive_accessible_overlap = copy.deepcopy(accessible_shared_border)
    excessive_accessible_overlap["controls"][0]["targets"][1]["x"] -= 0.001
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._validate_focused_control_evidence(
            excessive_accessible_overlap,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
        ),
    )

    def remove_control(value: dict) -> None:
        value["controls"].pop()

    def wrong_name(value: dict) -> None:
        value["controls"][0]["accessibleName"] = "forged"

    def wrong_option(value: dict) -> None:
        value["controls"][0]["optionLabels"][0] = "forged"

    def wrong_auxiliary_button(value: dict) -> None:
        value["controls"][0]["auxiliaryButtons"].append("forged")

    def wrong_overlap_tolerance(value: dict) -> None:
        value["controls"][0]["layout"]["targetOverlapTolerance"] = 1.0

    def two_checked(value: dict) -> None:
        value["controls"][0]["checkedLabels"].append("驗證泳道")

    def zero_checked(value: dict) -> None:
        value["controls"][0]["checkedLabels"].clear()

    def second_tab_stop(value: dict) -> None:
        value["controls"][0]["tabSequenceLabels"].append("驗證泳道")

    def wrong_arrow(value: dict) -> None:
        value["controls"][0]["afterArrowRight"] = "星雲圖"

    def wrong_arrow_left(value: dict) -> None:
        value["controls"][0]["afterArrowLeft"] = "驗證泳道"

    def wrong_space(value: dict) -> None:
        value["controls"][0]["afterSpace"] = None

    def small_target(value: dict) -> None:
        value["controls"][0]["targets"][0]["height"] = 23.999

    def clipped_target(value: dict) -> None:
        value["controls"][0]["targets"][0]["x"] = -4

    def coherently_below_viewport(value: dict) -> None:
        delta = float(identity["viewport"]["height"])
        value["controls"][0]["layout"]["rootRect"]["y"] += delta
        for target in value["controls"][0]["targets"]:
            target["y"] += delta

    def coherently_left_of_viewport(value: dict) -> None:
        delta = -float(identity["viewport"]["width"])
        value["controls"][0]["layout"]["rootRect"]["x"] += delta
        for target in value["controls"][0]["targets"]:
            target["x"] += delta

    def impossible_scroll_widths(value: dict) -> None:
        layout = value["controls"][0]["layout"]
        layout["documentScrollWidth"] = layout["documentClientWidth"] - 1
        layout["rootScrollWidth"] = layout["rootClientWidth"] - 1

    def document_horizontal_overflow(value: dict) -> None:
        layout = value["controls"][0]["layout"]
        layout["documentScrollWidth"] = layout["documentClientWidth"] + 2

    def root_horizontal_overflow(value: dict) -> None:
        layout = value["controls"][0]["layout"]
        layout["rootScrollWidth"] = layout["rootClientWidth"] + 2

    def reported_overflow_flag(value: dict) -> None:
        value["controls"][0]["layout"]["targetClipping"] = True

    def overlapping_targets(value: dict) -> None:
        first = value["controls"][0]["targets"][0]
        value["controls"][0]["targets"][1]["x"] = first["x"]

    def extra_option(value: dict) -> None:
        value["controls"][0]["optionLabels"].append("forged")

    def reordered_options(value: dict) -> None:
        value["controls"][0]["optionLabels"].reverse()

    def mixed_projection(value: dict) -> None:
        value["controls"][1]["widget"] = "segmented_control"

    for mutate in (
        remove_control,
        wrong_name,
        wrong_option,
        wrong_auxiliary_button,
        wrong_overlap_tolerance,
        extra_option,
        reordered_options,
        two_checked,
        zero_checked,
        second_tab_stop,
        wrong_arrow,
        wrong_arrow_left,
        wrong_space,
        small_target,
        clipped_target,
        coherently_below_viewport,
        coherently_left_of_viewport,
        impossible_scroll_widths,
        document_horizontal_overflow,
        root_horizontal_overflow,
        reported_overflow_flag,
        overlapping_targets,
        mixed_projection,
    ):
        candidate = copy.deepcopy(valid)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence._validate_focused_control_evidence(
                candidate,
                expected_case=identity["case"],
                expected_viewport=identity["viewport"],
            ),
        )

    analytics = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == "analytics-controls"
        and row["viewport"]["name"] == "mobile"
    )
    invalid_restore = _focused_control_evidence(analytics, accessible=True)
    invalid_restore["controls"][0]["afterArrowUp"] = "iv_history"
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._validate_focused_control_evidence(
            invalid_restore,
            expected_case=analytics["case"],
            expected_viewport=analytics["viewport"],
        ),
    )

    phase_drift = _migration_inputs()
    capture = phase_drift["after_controls"]["captures"][0]
    capture_identity = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == capture["case"]
        and row["viewport"] == capture["viewport"]
    )
    capture["controlEvidence"] = _focused_control_evidence(
        capture_identity, accessible=False
    )
    _raises(evidence.EvidenceContractError, lambda: _compare(phase_drift))

    focused_payload = _focused_control_evidence(identity, accessible=True)
    for fixture_entrypoint in (
        "scripts/ui_ux_fixture_app.py",
        "scripts/ui_ux_theme_fixture_app.py",
    ):
        nonfocused_identity = evidence.worker_capture_profile_rows(
            fixture_entrypoint
        )[0]
        nonfocused = _full_render_sidecar()
        nonfocused["identity"] = {
            "case": nonfocused_identity["case"],
            "route": nonfocused_identity["route"],
            "callable": nonfocused_identity["callable"],
        }
        nonfocused["viewport"] = copy.deepcopy(nonfocused_identity["viewport"])
        nonfocused["controlEvidence"] = copy.deepcopy(focused_payload)
        _raises(
            evidence.EvidenceContractError,
            lambda nonfocused=nonfocused: evidence.canonicalize_render_sidecar(
                nonfocused,
                owned_roots=("/private/tmp/quant-radar-owned-a",),
            ),
        )


def test_focused_overlap_boundaries_are_exact_and_mirrored() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    horizontal = {"x": 80.0, "y": 64.0, "width": 197.359, "height": 24.0}
    vertical = {"x": 80.0, "y": 80.0, "width": 24.0, "height": 197.359}
    cases = (
        (
            "institutions-horizontal-1.000",
            horizontal,
            {"x": 276.359, "y": 64.0, "width": 197.359, "height": 24.0},
            1.0,
            False,
        ),
        (
            "institutions-horizontal-1.001",
            horizontal,
            {"x": 276.358, "y": 64.0, "width": 197.359, "height": 24.0},
            1.0,
            True,
        ),
        (
            "institutions-vertical-1.000",
            vertical,
            {"x": 80.0, "y": 276.359, "width": 24.0, "height": 197.359},
            1.0,
            False,
        ),
        (
            "institutions-vertical-1.001",
            vertical,
            {"x": 80.0, "y": 276.358, "width": 24.0, "height": 197.359},
            1.0,
            True,
        ),
        (
            "accessible-horizontal-0.500",
            horizontal,
            {"x": 276.859, "y": 64.0, "width": 197.359, "height": 24.0},
            0.5,
            False,
        ),
        (
            "accessible-horizontal-0.501",
            horizontal,
            {"x": 276.858, "y": 64.0, "width": 197.359, "height": 24.0},
            0.5,
            True,
        ),
        (
            "disjoint-horizontal-axis",
            horizontal,
            {"x": 400.0, "y": 64.0, "width": 24.0, "height": 24.0},
            1.0,
            False,
        ),
        (
            "disjoint-vertical-axis",
            horizontal,
            {"x": 80.0, "y": 120.0, "width": 197.359, "height": 24.0},
            1.0,
            False,
        ),
    )
    mismatches: list[str] = []
    for layer, overlap in (
        ("worker", browser_worker._rects_overlap),
        ("trusted", evidence._focused_rects_overlap),
    ):
        for name, first, second, tolerance, expected in cases:
            observed = overlap(first, second, tolerance=tolerance)
            if observed is not expected:
                mismatches.append(
                    f"{layer}:{name} expected {expected}, got {observed}"
                )

    identity = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == "institutions-controls"
        and row["viewport"]["name"] == "desktop"
    )
    fractional = _focused_control_evidence(identity, accessible=False)
    targets = fractional["controls"][0]["targets"]
    targets[0].update(horizontal)
    targets[1].update(
        {"x": 276.359, "y": 64.0, "width": 197.359, "height": 24.0}
    )
    try:
        evidence._validate_focused_control_evidence(
            fractional,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
        )
    except evidence.EvidenceContractError as exc:
        mismatches.append(
            f"trusted-integrated:institutions-horizontal-1.000 rejected: {exc}"
        )

    forged = copy.deepcopy(fractional)
    forged["controls"][0]["targets"][1]["x"] = 276.3586
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._validate_focused_control_evidence(
            forged,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
        ),
    )
    if mismatches:
        raise AssertionError("exact-decimal geometry mismatch: " + "; ".join(mismatches))


def test_focused_screenshot_binding_v2_is_exact_and_mutation_closed() -> None:
    identities = evidence.worker_capture_profile_rows(
        "scripts/ui_ux_selection_fixture_app.py"
    )
    identity = next(
        row
        for row in identities
        if row["case"] == "radar-controls"
        and row["viewport"]["name"] == "mobile"
    )
    valid = _focused_control_evidence_v2(identity)
    normalized = evidence._validate_focused_control_evidence(
        valid,
        expected_case=identity["case"],
        expected_viewport=identity["viewport"],
        require_screenshot_binding=True,
    )
    if normalized != valid:
        raise AssertionError("valid focused screenshot binding was not canonical")

    legacy = _focused_control_evidence(identity, accessible=True)
    evidence._validate_focused_control_evidence(
        legacy,
        expected_case=identity["case"],
        expected_viewport=identity["viewport"],
    )
    _raises(
        evidence.EvidenceContractError,
        lambda: evidence._validate_focused_control_evidence(
            legacy,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
            require_screenshot_binding=True,
        ),
    )

    def wrong_mode(value: dict) -> None:
        value["screenshotBinding"]["mode"] = "full-page"

    def wrong_viewport(value: dict) -> None:
        value["screenshotBinding"]["viewport"]["height"] += 1

    def reordered_roots(value: dict) -> None:
        value["screenshotBinding"]["roots"].reverse()

    def cross_bound_root(value: dict) -> None:
        value["screenshotBinding"]["roots"][0]["rect"] = copy.deepcopy(
            value["screenshotBinding"]["roots"][1]["rect"]
        )
        value["screenshotBinding"]["roots"][0]["rect"]["x"] += 1

    def missing_scroll_chain(value: dict) -> None:
        selector = value["controls"][0]["rootSelector"]
        value["screenshotBinding"]["scrollEntries"] = [
            row
            for row in value["screenshotBinding"]["scrollEntries"]
            if row["rootSelector"] != selector
        ]

    def nonconsecutive_scroll_chain(value: dict) -> None:
        value["screenshotBinding"]["scrollEntries"][0]["chainIndex"] = 1

    def negative_scroll_metric(value: dict) -> None:
        value["screenshotBinding"]["scrollEntries"][0]["top"] = -0.001

    def impossible_scroll_relation(value: dict) -> None:
        row = value["screenshotBinding"]["scrollEntries"][0]
        row["scrollHeight"] = row["clientHeight"] - 1

    def target_outside_viewport(value: dict) -> None:
        value["controls"][0]["targets"][0]["y"] = (
            value["screenshotBinding"]["viewport"]["height"] + 2
        )

    for mutate in (
        wrong_mode,
        wrong_viewport,
        reordered_roots,
        cross_bound_root,
        missing_scroll_chain,
        nonconsecutive_scroll_chain,
        negative_scroll_metric,
        impossible_scroll_relation,
        target_outside_viewport,
    ):
        candidate = copy.deepcopy(valid)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence._validate_focused_control_evidence(
                candidate,
                expected_case=identity["case"],
                expected_viewport=identity["viewport"],
                require_screenshot_binding=True,
            ),
        )


def test_root_render_v2_and_case_semantic_projection_are_closed() -> None:
    identity = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == "knowledge-graph-controls"
        and row["viewport"]["name"] == "mobile"
    )
    root_row = next(
        row
        for row in evidence.root_capture_expansion_rows()
        if row["rootCaptureId"]
        == "knowledge-graph-controls/mobile/root-01"
    )
    base = _full_render_sidecar(run_suffix="v2")
    base["providerCounters"] = {}
    base["mutatorCounters"] = {}
    case_controls = _focused_control_evidence(identity, accessible=True)
    root_controls = _focused_control_evidence_v3(
        identity,
        root_selector=root_row["rootSelector"],
    )
    root_rect = root_controls["controls"][0]["layout"]["rootRect"]
    for node in base["nodes"]:
        if node["rootSelector"] == root_row["rootSelector"]:
            node["bounds"] = {
                key: int(value)
                for key, value in root_rect.items()
            }
    document = {
        "schemaVersion": evidence.RENDER_V2_SCHEMA,
        "identity": copy.deepcopy(base["identity"]),
        "viewport": copy.deepcopy(base["viewport"]),
        "readiness": copy.deepcopy(base["readiness"]),
        "nodes": copy.deepcopy(base["nodes"]),
        "stableState": copy.deepcopy(base["stableState"]),
        "providerCounters": {},
        "mutatorCounters": {},
        "runtimeProjection": copy.deepcopy(base["runtimeProjection"]),
        "counterProvenance": None,
        "rootCapture": {
            key: copy.deepcopy(root_row[key])
            for key in (
                "logicalCaptureId",
                "rootCaptureId",
                "rootOrdinal",
                "rootSelector",
            )
        }
        | {
            "rootExpansionSha256": evidence.ROOT_CAPTURE_EXPANSION_SHA256,
        },
        "controlEvidence": root_controls,
        "caseSemanticProjection": {
            "schemaVersion": evidence.CASE_SEMANTIC_PROJECTION_SCHEMA,
            "identity": {
                key: copy.deepcopy(root_row[key])
                for key in (
                    "fixtureEntrypoint",
                    "logicalCaptureId",
                    "case",
                    "route",
                    "callable",
                    "viewport",
                )
            },
            "readiness": copy.deepcopy(base["readiness"]),
            "nodes": copy.deepcopy(base["nodes"]),
            "stableState": copy.deepcopy(base["stableState"]),
            "providerCounters": {},
            "mutatorCounters": {},
            "runtimeProjection": copy.deepcopy(base["runtimeProjection"]),
            "counterProvenance": None,
            "controlEvidence": case_controls,
        },
    }
    raw = evidence.canonicalize_worker_render_sidecar(
        document,
        owned_roots=("/private/tmp/quant-radar-owned-v2/source", "/private/tmp/quant-radar-owned-v2/browser"),
    )
    normalized = json.loads(raw)
    if (
        normalized["schemaVersion"] != evidence.RENDER_V2_SCHEMA
        or len(normalized["controlEvidence"]["controls"]) != 1
        or len(
            normalized["caseSemanticProjection"]["controlEvidence"]["controls"]
        )
        != 2
    ):
        raise AssertionError(normalized)

    for mutate in (
        lambda value: value["rootCapture"].__setitem__(
            "rootSelector", ".st-key-kg_label_mode"
        ),
        lambda value: value["controlEvidence"]["controls"].append(
            copy.deepcopy(value["controlEvidence"]["controls"][0])
        ),
        lambda value: value["caseSemanticProjection"].__setitem__(
            "counterProvenance", {}
        ),
        lambda value: value.__setitem__("unexpected", True),
    ):
        candidate = copy.deepcopy(document)
        mutate(candidate)
        _raises(
            evidence.EvidenceContractError,
            lambda candidate=candidate: evidence.canonicalize_worker_render_sidecar(
                candidate,
                owned_roots=(
                    "/private/tmp/quant-radar-owned-v2/source",
                    "/private/tmp/quant-radar-owned-v2/browser",
                ),
            ),
        )


def test_real_chromium_focused_screenshot_binding_is_pre_post_exact() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = next(
        row
        for row in evidence.worker_capture_profile_rows(
            "scripts/ui_ux_selection_fixture_app.py"
        )
        if row["case"] == "analytics-controls"
        and row["viewport"]["name"] == "mobile"
    )
    selector = identity["rootSelectors"][0]
    if not selector.startswith("."):
        raise AssertionError(selector)
    root_class = selector[1:]
    source = _focused_control_evidence(identity, accessible=True)
    viewport = identity["viewport"]
    html = f"""
<!doctype html>
<style>
  html, body {{ margin: 0; width: 100%; }}
  .spacer {{ height: 1400px; }}
  .{root_class} {{
    box-sizing: border-box;
    width: calc(100% - 40px);
    height: 64px;
    margin: 0 20px 900px;
    padding: 10px;
    background: #182033;
  }}
  [data-baseweb="select"] {{
    box-sizing: border-box;
    display: block;
    width: 100%;
    height: 44px;
    background: #26324a;
  }}
</style>
<div class="spacer"></div>
<div class="{root_class}">
  <div data-baseweb="select" role="combobox" aria-label="資料表"></div>
</div>
"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={
                "width": viewport["width"],
                "height": viewport["height"],
            }
        )
        try:
            page.set_content(html, wait_until="load")
            prepared, before, specs = (
                browser_worker._prepare_focused_screenshot_evidence(
                    page,
                    source,
                    timeout_ms=5_000,
                )
            )
            projection_contract = {
                "rootSelectors": [selector],
                "affectedRootSelectors": [selector],
            }
            nodes_before = browser_worker._project_nodes(
                page.evaluate(
                    browser_worker._DOM_PROJECTION_SCRIPT,
                    projection_contract,
                ),
                expected_root_selectors=(selector,),
            )
            screenshot = page.screenshot(
                full_page=False,
                animations="disabled",
                caret="hide",
            )
            after = browser_worker._focused_screenshot_snapshot(page, specs)
            nodes_after = browser_worker._project_nodes(
                page.evaluate(
                    browser_worker._DOM_PROJECTION_SCRIPT,
                    projection_contract,
                ),
                expected_root_selectors=(selector,),
            )
            if before != after or nodes_before != nodes_after:
                raise AssertionError("focused screenshot state changed across capture")
            if browser_worker._png_dimensions(screenshot) != (
                viewport["width"],
                viewport["height"],
            ):
                raise AssertionError("focused screenshot is not viewport-sized")
            validated = evidence._validate_focused_control_evidence(
                prepared,
                expected_case=identity["case"],
                expected_viewport=identity["viewport"],
                require_screenshot_binding=True,
            )
            if validated != prepared:
                raise AssertionError("real Chromium binding was not canonical")
            evidence._validate_focused_screenshot_binding_nodes(
                validated,
                nodes_before,
            )
            root = validated["screenshotBinding"]["roots"][0]["rect"]
            target = validated["controls"][0]["targets"][0]
            if (
                root["y"] < -1
                or root["y"] + root["height"] > viewport["height"] + 1
                or target["y"] < -1
                or target["y"] + target["height"] > viewport["height"] + 1
            ):
                raise AssertionError("focused Analytics evidence is outside viewport")
        finally:
            page.close()
            browser.close()


class _SemanticMutationPage:
    """Schedule deterministic DOM flickers only between semantic observations."""

    def __init__(self, delegate: object, schedule_script: str) -> None:
        self.delegate = delegate
        self.schedule_script = schedule_script
        self.scheduled_count = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self.delegate, name)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        if self.delegate.evaluate(self.schedule_script) is True:
            self.scheduled_count += 1
        self.delegate.wait_for_timeout(timeout_ms)


def test_focused_semantic_snapshot_is_atomic_stable_and_non_mutating() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    contract = browser_worker._FOCUSED_CONTROL_CONTRACTS[
        "risk-guard-controls"
    ][0]
    snapshot = {
        "buttonNames": ["手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"],
        "radiogroupCount": 1,
        "radiogroupNames": ["button group"],
        "primaryGroupCount": 1,
        "primaryOptionLabels": ["手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"],
        "primaryKinds": [
            "segmented_control",
            "segmented_controlActive",
            "segmented_control",
            "segmented_control",
        ],
        "radioCount": 0,
        "radioLabels": [],
        "checkedRadioLabels": [],
        "comboboxCount": 0,
        "comboboxNames": [],
        "selectRootCount": 0,
        "selectText": "",
    }

    class Root:
        def __init__(self) -> None:
            self.evaluate_calls: list[tuple[str, int | None]] = []

        def evaluate(
            self, script: str, *, timeout: int | None = None
        ) -> dict[str, object]:
            self.evaluate_calls.append((script, timeout))
            return copy.deepcopy(snapshot)

    class Page:
        def __init__(self) -> None:
            self.waits: list[int] = []

        def wait_for_timeout(self, timeout_ms: int) -> None:
            self.waits.append(timeout_ms)

    root = Root()
    projection, _fingerprint = browser_worker._focused_projection_snapshot(
        root, contract, observation_timeout_ms=250
    )
    if projection != "legacy-segmented" or len(root.evaluate_calls) != 1:
        raise AssertionError((projection, root.evaluate_calls))
    if root.evaluate_calls[0] != (
        browser_worker._FOCUSED_SEMANTIC_SNAPSHOT_SCRIPT,
        250,
    ):
        raise AssertionError("semantic snapshot was not one authenticated evaluate")

    root = Root()
    page = Page()
    projection = browser_worker._wait_for_focused_projection(
        page,
        root,
        contract,
        timeout_ms=1_000,
        expected_projection="legacy-segmented",
    )
    if (
        projection != "legacy-segmented"
        or len(root.evaluate_calls) != 2
        or len(page.waits) != 1
    ):
        raise AssertionError((projection, root.evaluate_calls, page.waits))

    script = browser_worker._FOCUSED_SEMANTIC_SNAPSHOT_SCRIPT
    forbidden_calls = (
        "click(",
        ".click(",
        "press(",
        ".press(",
        "dispatchEvent(",
        "setAttribute(",
        "removeAttribute(",
        "appendChild(",
    )
    present = [token for token in forbidden_calls if token in script]
    assignment = re.search(
        r"\b(?:checked|textContent|innerText)\s*=(?!=)", script
    )
    if present or assignment is not None:
        raise AssertionError((present, assignment.group(0) if assignment else None))


def _assert_hidden_native_radio_fixture(
    page: object,
    root_selector: str,
    option_labels: tuple[str, ...],
    *,
    timeout_ms: int = 1_000,
) -> None:
    root = page.locator(root_selector)
    if root.count() != 1 or not root.is_visible():
        raise AssertionError("hidden-radio fixture root is not uniquely visible")
    groups = root.get_by_role("radiogroup")
    if groups.count() != 1 or not groups.is_visible():
        raise AssertionError("hidden-radio fixture group is not uniquely visible")
    if groups.get_by_role("radio").count() != len(option_labels):
        raise AssertionError("hidden-radio fixture semantic count differs")
    for option_label in option_labels:
        radio = groups.get_by_role("radio", name=option_label, exact=True)
        if radio.count() != 1 or radio.is_visible():
            raise AssertionError((option_label, radio.count(), radio.is_visible()))
        wrapping_label = radio.locator("xpath=ancestor::label[1]")
        if (
            wrapping_label.count() != 1
            or not wrapping_label.is_visible()
            or not radio.evaluate(
                "node => !!node.labels && node.labels.length === 1 && "
                "node.labels[0] === node.closest('label') && "
                "node.labels[0].control === node"
            )
        ):
            raise AssertionError(f"{option_label!r} has no unique visible wrapping label")
        box = wrapping_label.bounding_box()
        if (
            not isinstance(box, dict)
            or float(box.get("width", 0)) < 24
            or float(box.get("height", 0)) < 24
        ):
            raise AssertionError((option_label, box))
        wrapping_label.click(trial=True, timeout=timeout_ms)


def test_real_chromium_focused_semantic_readiness_waits_for_exact_stability() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "risk-guard-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "risk-guard-controls",
            "route": "/__selection__/risk-guard",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    contract = browser_worker._FOCUSED_CONTROL_CONTRACTS[
        "risk-guard-controls"
    ][0]
    legacy_html = """
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-rg_source{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [role=radiogroup]{display:flex;width:350px;height:32px}
      [role=radiogroup] button{display:block;width:82px;height:24px}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="risk-guard-controls/mobile"
         data-render-generation="1">risk-guard-controls</div>
    <div class="st-key-rg_source" data-testid="stElementContainer">
      <div role="radiogroup" aria-label="button group">
        <button aria-label="" kind="segmented_control">手動輸入</button>
        <button aria-label="" kind="segmented_controlActive">Watchlist</button>
        <button aria-label="" kind="segmented_control">Screener 候選</button>
        <button aria-label="" kind="segmented_control">IBKR 持倉</button>
      </div>
    </div>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                legacy_html
                + """
                <script>
                  setTimeout(() => {
                    document.querySelector('[role=radiogroup]').setAttribute(
                      'data-baseweb', 'button-group'
                    );
                  }, 100);
                </script>
                """
            )
            delayed = browser_worker._collect_focused_control_evidence(
                page, identity, timeout_ms=1_000
            )
            if delayed["projection"] != "legacy-segmented":
                raise AssertionError(delayed)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(legacy_html)
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=150
                ),
            )
            page.close()

            legacy_exact = legacy_html.replace(
                '<div role="radiogroup"',
                '<div data-baseweb="button-group" role="radiogroup"',
            )
            legacy_without_active = legacy_exact.replace(
                'kind="segmented_controlActive"', 'kind="segmented_control"'
            )
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                legacy_without_active
                + """
                <script>
                  setTimeout(() => {
                    const buttons = document.querySelectorAll('[role=radiogroup] button');
                    buttons[1].setAttribute('kind', 'segmented_controlActive');
                  }, 100);
                </script>
                """
            )
            delayed = browser_worker._collect_focused_control_evidence(
                page, identity, timeout_ms=1_000
            )
            if delayed["controls"][0]["checkedLabels"] != ["Watchlist"]:
                raise AssertionError(delayed)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(legacy_without_active)
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=150
                ),
            )
            page.close()

            radio_html = """
            <style>
              html,body{margin:0;width:390px;overflow-x:hidden}
              .st-key-rg_source{position:absolute;left:20px;top:60px;width:350px;height:40px}
              [role=radiogroup]{display:flex;gap:4px;width:350px;height:32px}
              [role=radiogroup] label{position:relative;display:inline-flex;align-items:center;width:82px;height:24px}
              [role=radiogroup] input[type=radio]{position:absolute;width:0;height:0;margin:0;padding:0;border:0;clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;opacity:0}
            </style>
            <div id="ux1b-selection-ready" data-capture-id="risk-guard-controls/mobile"
                 data-render-generation="1">risk-guard-controls</div>
            <div class="st-key-rg_source">
              <div role="radiogroup" aria-label="來源">
                <label><input type="radio" name="source" value="Watchlist">Watchlist</label>
                <label><input type="radio" name="source" value="手動輸入" checked>手動輸入</label>
                <label><input type="radio" name="source" value="Screener 候選">Screener 候選</label>
                <label><input type="radio" name="source" value="IBKR 持倉">IBKR 持倉</label>
              </div>
            </div>
            __RADIO_READY__
            """
            radio_ready_script = """
            <script>
              setTimeout(() => {
                const group = document.querySelector('[role=radiogroup]');
                const labels = Array.from(group.querySelectorAll('label'));
                const byText = new Map(labels.map(label => [label.innerText.trim(), label]));
                for (const text of ['手動輸入', 'Watchlist', 'Screener 候選', 'IBKR 持倉']) {
                  group.appendChild(byText.get(text));
                }
                for (const input of group.querySelectorAll('input')) input.checked = false;
                byText.get('Watchlist').querySelector('input').checked = true;
              }, 100);
            </script>
            """
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                radio_html.replace("__RADIO_READY__", radio_ready_script)
            )
            _assert_hidden_native_radio_fixture(
                page,
                ".st-key-rg_source",
                ("Watchlist", "手動輸入", "Screener 候選", "IBKR 持倉"),
            )
            delayed = browser_worker._collect_focused_control_evidence(
                page, identity, timeout_ms=1_000
            )
            radio = delayed["controls"][0]
            if (
                radio["optionLabels"]
                != ["手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"]
                or radio["checkedLabels"] != ["Watchlist"]
                or radio["afterArrowRight"] != "Screener 候選"
            ):
                raise AssertionError(delayed)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(radio_html.replace("__RADIO_READY__", ""))
            page.evaluate(
                """
                () => {
                  const group = document.querySelector('[role=radiogroup]');
                  const labels = Array.from(group.querySelectorAll('label'));
                  const byText = new Map(labels.map(label => [label.innerText.trim(), label]));
                  for (const text of ['手動輸入', 'Watchlist', 'Screener 候選', 'IBKR 持倉']) {
                    group.appendChild(byText.get(text));
                  }
                  for (const input of group.querySelectorAll('input')) input.checked = false;
                  byText.get('Watchlist').querySelector('input').checked = true;
                  group.dataset.semanticStage = 'exact-once';
                }
                """
            )
            mutation_page = _SemanticMutationPage(
                page,
                """
                () => {
                  const group = document.querySelector('[role=radiogroup]');
                  if (group.dataset.flickerScheduled === 'true') return false;
                  group.dataset.flickerScheduled = 'true';
                  const labels = Array.from(group.querySelectorAll('label'));
                  const byText = new Map(labels.map(label => [label.innerText.trim(), label]));
                  setTimeout(() => {
                    for (const input of group.querySelectorAll('input')) input.checked = false;
                    byText.get('手動輸入').querySelector('input').checked = true;
                    group.appendChild(byText.get('手動輸入'));
                    group.dataset.semanticStage = 'partial';
                  }, 0);
                  setTimeout(() => {
                    for (const text of ['手動輸入', 'Watchlist', 'Screener 候選', 'IBKR 持倉']) {
                      group.appendChild(byText.get(text));
                    }
                    for (const input of group.querySelectorAll('input')) input.checked = false;
                    byText.get('Watchlist').querySelector('input').checked = true;
                    group.dataset.semanticStage = 'stable';
                  }, 120);
                  return true;
                }
                """,
            )
            flicker_record = browser_worker._collect_focused_control_evidence(
                mutation_page, identity, timeout_ms=1_000
            )
            if (
                mutation_page.scheduled_count != 1
                or page.locator('[role=radiogroup]').get_attribute(
                    "data-semantic-stage"
                )
                != "stable"
                or flicker_record["controls"][0]["checkedLabels"]
                != ["Watchlist"]
            ):
                raise AssertionError((mutation_page.scheduled_count, flicker_record))
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(radio_html.replace("__RADIO_READY__", ""))
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=150
                ),
            )
            page.close()

            analytics_identity = evidence.validate_worker_capture_identity(
                {
                    "requestId": "analytics-controls/mobile",
                    "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
                    "case": "analytics-controls",
                    "route": "/__selection__/analytics-db",
                    "viewport": {"name": "mobile", "width": 390, "height": 844},
                }
            )
            selectbox_html = """
            <!doctype html>
            <style>
              html,body{margin:0;width:390px;overflow-x:hidden}
              .st-key-adb_table{position:absolute;left:20px;top:60px;width:350px;height:40px}
              [data-baseweb=select]{width:350px;height:32px}
              [data-baseweb=icon]{width:20px;height:20px}
              [role=combobox]{box-sizing:border-box;width:350px;height:32px;padding:4px}
              [data-testid=stSelectboxVirtualDropdown]{position:absolute;left:20px;top:96px;width:350px}
              [role=option]{box-sizing:border-box;width:350px;height:28px;padding:4px}
            </style>
            <div id="ux1b-selection-ready" data-capture-id="analytics-controls/mobile"
                 data-render-generation="1">analytics-controls</div>
            <div class="st-key-adb_table">
              <div data-baseweb="select">
                <span data-selected>loading</span>
                <input role="combobox" aria-label="Selected candidate_rankings. 資料表"
                       aria-expanded="false" aria-haspopup="listbox"
                       aria-autocomplete="list" tabindex="0" value="">
                <svg data-baseweb="icon" title="Clear value" viewBox="0 0 24 24"
                     aria-label="Clear value" role="button"><title>Clear value</title><path></path></svg>
              </div>
            </div>
            <script>
              const labels = ['candidate_rankings', 'iv_history'];
              const combobox = document.querySelector('[role=combobox]');
              const selectedValue = document.querySelector('[data-selected]');
              const marker = document.querySelector('#ux1b-selection-ready');
              let selected = 0;
              let highlighted = 0;
              let open = false;
              let activePopover = null;
              __SELECTBOX_READY__
              function closeListbox() {
                activePopover?.remove();
                activePopover = null;
                combobox.setAttribute('aria-expanded', 'false');
                combobox.removeAttribute('aria-controls');
                combobox.removeAttribute('aria-activedescendant');
                open = false;
              }
              function renderListbox() {
                const wasOpen = open;
                activePopover?.remove();
                const popover = document.createElement('div');
                popover.setAttribute('data-baseweb', 'popover');
                const listbox = document.createElement('ul');
                listbox.setAttribute('data-testid', 'stSelectboxVirtualDropdown');
                for (let index = 0; index < labels.length; index += 1) {
                  const option = document.createElement('li');
                  option.id = `synthetic-option-${index}`;
                  option.setAttribute('role', 'option');
                  option.setAttribute('aria-disabled', 'false');
                  option.setAttribute('aria-selected', String(index === highlighted));
                  option.textContent = labels[index];
                  listbox.appendChild(option);
                }
                popover.appendChild(listbox);
                document.body.appendChild(popover);
                activePopover = popover;
                combobox.setAttribute('aria-expanded', 'true');
                combobox.setAttribute('aria-controls', 'synthetic-table-list');
                if (wasOpen) {
                  combobox.setAttribute(
                    'aria-activedescendant', listbox.children[highlighted].id
                  );
                } else {
                  combobox.removeAttribute('aria-activedescendant');
                }
                open = true;
              }
              combobox.addEventListener('keydown', event => {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  if (!open) highlighted = selected;
                  else highlighted = (highlighted + 1) % labels.length;
                  renderListbox();
                } else if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  if (!open) highlighted = selected;
                  else highlighted = (highlighted - 1 + labels.length) % labels.length;
                  renderListbox();
                } else if (event.key === 'Escape' && open) {
                  event.preventDefault();
                  closeListbox();
                } else if (event.key === 'Enter' && open) {
                  event.preventDefault();
                  selected = highlighted;
                  selectedValue.textContent = labels[selected];
                  combobox.setAttribute(
                    'aria-label', `Selected ${labels[selected]}. 資料表`
                  );
                  closeListbox();
                  marker.dataset.renderGeneration = String(
                    Number(marker.dataset.renderGeneration) + 1
                  );
                }
              });
            </script>
            """
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                selectbox_html.replace(
                    "__SELECTBOX_READY__",
                    "setTimeout(() => { selectedValue.textContent = labels[0]; }, 100);",
                )
            )
            delayed = browser_worker._collect_focused_control_evidence(
                page, analytics_identity, timeout_ms=2_000
            )
            selectbox = delayed["controls"][0]
            if (
                selectbox["selectedLabel"] != "candidate_rankings"
                or selectbox["afterArrowDown"] != "iv_history"
                or selectbox["afterArrowUp"] != "candidate_rankings"
            ):
                raise AssertionError(delayed)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                selectbox_html.replace("loading", "candidate_rankings").replace(
                    "__SELECTBOX_READY__", ""
                )
            )
            page.locator(".st-key-adb_table").evaluate(
                "root => { root.dataset.semanticStage = 'exact-once'; }"
            )
            mutation_page = _SemanticMutationPage(
                page,
                """
                () => {
                  const root = document.querySelector('.st-key-adb_table');
                  if (root.dataset.flickerScheduled === 'true') return false;
                  root.dataset.flickerScheduled = 'true';
                  const selectedValue = root.querySelector('[data-selected]');
                  setTimeout(() => {
                    selectedValue.textContent = 'patching';
                    root.dataset.semanticStage = 'partial';
                  }, 0);
                  setTimeout(() => {
                    selectedValue.textContent = 'candidate_rankings';
                    root.dataset.semanticStage = 'stable';
                  }, 120);
                  return true;
                }
                """,
            )
            flicker_record = browser_worker._collect_focused_control_evidence(
                mutation_page, analytics_identity, timeout_ms=2_000
            )
            if (
                mutation_page.scheduled_count != 1
                or page.locator(".st-key-adb_table").get_attribute(
                    "data-semantic-stage"
                )
                != "stable"
                or flicker_record["controls"][0]["selectedLabel"]
                != "candidate_rankings"
            ):
                raise AssertionError((mutation_page.scheduled_count, flicker_record))
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                selectbox_html.replace("__SELECTBOX_READY__", "")
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, analytics_identity, timeout_ms=150
                ),
            )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                legacy_exact
            )
            page.evaluate(
                "document.documentElement.dataset.semanticStage = 'flicker'"
            )

            mutation_page = _SemanticMutationPage(
                page,
                """
                () => {
                  if (document.documentElement.dataset.flickerScheduled === 'true') {
                    return false;
                  }
                  document.documentElement.dataset.flickerScheduled = 'true';
                  const root = document.querySelector('.st-key-rg_source');
                  const primary = root.querySelector('[role=radiogroup]');
                  const buttons = Array.from(primary.querySelectorAll('button'));
                  setTimeout(() => {
                    primary.removeAttribute('data-baseweb');
                    buttons[0].setAttribute('kind', 'segmented_controlActive');
                    buttons[1].setAttribute('kind', 'segmented_control');
                    document.documentElement.dataset.semanticStage = 'partial';
                  }, 0);
                  setTimeout(() => {
                    primary.setAttribute('data-baseweb', 'button-group');
                    buttons[0].setAttribute('kind', 'segmented_control');
                    buttons[1].setAttribute('kind', 'segmented_controlActive');
                    document.documentElement.dataset.semanticStage = 'stable';
                  }, 120);
                  return true;
                }
                """,
            )
            projection = browser_worker._wait_for_focused_projection(
                mutation_page,
                page.locator(".st-key-rg_source"),
                contract,
                timeout_ms=1_000,
            )
            semantic_stage = page.evaluate(
                "document.documentElement.dataset.semanticStage"
            )
            if (
                projection != "legacy-segmented"
                or mutation_page.scheduled_count != 1
                or semantic_stage != "stable"
            ):
                raise AssertionError(
                    "focused semantic readiness accepted a one-observation exact flicker"
                )
        finally:
            browser.close()


_FOCUSED_SCROLL_LAYOUT_HTML = """<!doctype html>
<style>
  html,body{margin:0;width:390px;min-height:844px;overflow-x:hidden}
  #document-spacer{height:900px}
  #outer{width:390px;height:844px;overflow:auto}
  #outer-content{box-sizing:border-box;width:920px;height:1650px;padding-top:650px}
  #inner{margin-left:10px;width:370px;height:600px;overflow:auto}
  #inner-content{position:relative;width:900px;height:1700px}
  #spacer{height:920px}
  .st-key-layout_probe{position:relative;margin-left:32px;width:165px;height:60px}
  .target-label{position:absolute;top:28px;left:0;width:90px;height:32px}
  .target-label.second{left:20px}
  .target{display:block;box-sizing:border-box;width:76px;height:32px;padding:0}
</style>
<div id="generation" data-render-generation="1"></div>
<div id="document-spacer"></div>
<div id="outer"><div id="outer-content"><div id="inner"><div id="inner-content">
  <div id="spacer"></div>
  <div class="st-key-layout_probe" data-testid="stElementContainer">
    <label class="target-label"><button class="target">one</button></label>
    <label class="target-label second"><button class="target">two</button></label>
  </div>
</div></div></div></div>
"""


def _prepare_focused_scroll_layout(
    page: object,
    *,
    root_height: int = 60,
    root_left: int = 32,
    two_targets: bool = False,
    behavior: str = "none",
    unresolved_font: bool = False,
    precondition_growth: bool = False,
) -> None:
    page.set_content(_FOCUSED_SCROLL_LAYOUT_HTML)
    page.evaluate(
        """
        ({rootHeight,rootLeft,twoTargets}) => {
          const root=document.querySelector('.st-key-layout_probe');
          root.style.height=`${rootHeight}px`;
          root.style.marginLeft=`${rootLeft}px`;
          for (const label of root.querySelectorAll('.target-label')) {
            label.style.top=`${Math.max(0, rootHeight - 32)}px`;
          }
          if (!twoTargets) root.querySelector('.target-label.second').remove();
          const outer=document.querySelector('#outer');
          const inner=document.querySelector('#inner');
          const scrolling=document.scrollingElement;
          outer.scrollLeft=3; outer.scrollTop=11;
          inner.scrollLeft=5; inner.scrollTop=17;
          scrolling.scrollTop=13;
        }
        """,
        {
            "rootHeight": root_height,
            "rootLeft": root_left,
            "twoTargets": two_targets,
        },
    )
    page.wait_for_function(
        """
        () => {
          const outer=document.querySelector('#outer');
          const inner=document.querySelector('#inner');
          return document.scrollingElement.scrollTop===13 &&
            outer.scrollLeft===3 && outer.scrollTop===11 &&
            inner.scrollLeft===5 && inner.scrollTop===17;
        }
        """,
        timeout=1_000,
    )
    page.evaluate(
        """
        () => {
          const html=document.documentElement;
          const scrolling=document.scrollingElement;
          const outer=document.querySelector('#outer');
          const inner=document.querySelector('#inner');
          document.addEventListener('scroll', () => {
            if (scrolling.scrollTop !== 13) html.dataset.documentAuditScrolled='true';
          }, true);
          outer.addEventListener('scroll', () => {
            if (outer.scrollLeft !== 3 || outer.scrollTop !== 11) {
              html.dataset.outerAuditScrolled='true';
            }
          });
          inner.addEventListener('scroll', () => {
            if (inner.scrollLeft !== 5 || inner.scrollTop !== 17) {
              html.dataset.innerAuditScrolled='true';
            }
          });
        }
        """
    )
    if behavior in {"transient", "perpetual"}:
        page.evaluate(
            """
            behavior => {
              const inner=document.querySelector('#inner');
              const root=document.querySelector('.st-key-layout_probe');
              let started=false;
              inner.addEventListener('scroll', () => {
                if (started || inner.scrollTop <= 17) return;
                started=true;
                root.dataset.motionStarted='true';
                if (behavior === 'perpetual') {
                  root.animate(
                    [{transform:'translateY(0px)'},{transform:'translateY(120px)'}],
                    {duration:10_000,iterations:Infinity}
                  );
                  return;
                }
                let frame=4;
                const settle=() => {
                  if (frame > 0) {
                    root.style.transform=`translateY(${frame--}px)`;
                    requestAnimationFrame(settle);
                    return;
                  }
                  root.style.transform='none';
                  root.dataset.motionSettled='true';
                };
                requestAnimationFrame(settle);
              });
            }
            """,
            behavior,
        )
    elif behavior == "replace-on-restore":
        page.evaluate(
            """
            () => {
              const inner=document.querySelector('#inner');
              let auditSeen=false;
              const observe=() => {
                if (!inner.isConnected) return;
                if (inner.scrollTop > 17) auditSeen=true;
                if (auditSeen && inner.scrollTop === 17) {
                  document.documentElement.dataset.ancestorReplaced='true';
                  inner.replaceWith(inner.cloneNode(true));
                  return;
                }
                requestAnimationFrame(observe);
              };
              requestAnimationFrame(observe);
            }
            """
        )
    if precondition_growth:
        page.evaluate(
            """
            () => {
              const ready=new Promise(resolve => setTimeout(() => {
                document.querySelector('#outer-content').style.height='1750px';
                document.documentElement.dataset.preconditionGrowth='true';
                requestAnimationFrame(() => requestAnimationFrame(resolve));
              }, 80));
              const fontSet={status:'loaded',ready};
              Object.defineProperty(document, 'fonts', {
                configurable:true,
                get() { return fontSet; }
              });
            }
            """
        )
    elif unresolved_font:
        page.evaluate(
            """
            () => {
              const pending=new Promise(resolve => setTimeout(resolve, 5_000));
              Object.defineProperty(document, 'fonts', {
                configurable:true,
                get() {
                  const root=document.documentElement;
                  root.dataset.fontReads=String(Number(root.dataset.fontReads || 0) + 1);
                  return {status:'loaded',ready:pending};
                }
              });
            }
            """
        )


def _focused_scroll_layout_state(page: object) -> dict[str, object]:
    return page.evaluate(
        """
        () => {
          const rounded=node => {
            const rect=node.getBoundingClientRect();
            return Object.fromEntries(
              ['x','y','width','height'].map(key => [key, Math.round(rect[key]*1000)/1000])
            );
          };
          const scrolling=document.scrollingElement;
          const outer=document.querySelector('#outer');
          const inner=document.querySelector('#inner');
          const root=document.querySelector('.st-key-layout_probe');
          return {
            offsets: {
              window:[window.scrollX,window.scrollY],
              document:[scrolling.scrollLeft,scrolling.scrollTop],
              outer:[outer.scrollLeft,outer.scrollTop],
              inner:[inner.scrollLeft,inner.scrollTop]
            },
            root:rounded(root),
            targets:Array.from(root.querySelectorAll('.target')).map(rounded),
            document:[
              document.documentElement.clientWidth,
              document.documentElement.scrollWidth,
              document.documentElement.clientHeight,
              document.documentElement.scrollHeight
            ],
            generation:document.querySelector('#generation').dataset.renderGeneration
          };
        }
        """
    )


def _focused_projection_root_bounds(browser_worker: object, page: object) -> dict:
    rows = page.evaluate(
        browser_worker._DOM_PROJECTION_SCRIPT,
        {
            "rootSelectors": [".st-key-layout_probe"],
            "affectedRootSelectors": [".st-key-layout_probe"],
        },
    )
    roots = [row for row in rows if row.get("rootSelector") == ".st-key-layout_probe"]
    if len(roots) != 1:
        raise AssertionError(roots)
    return roots[0]["bounds"]


def _focused_scroll_position_and_generation(
    state: Mapping[str, object],
) -> dict[str, object]:
    return {
        "offsets": copy.deepcopy(state["offsets"]),
        "generation": state["generation"],
    }


def _call_focused_layout(
    browser_worker: object,
    page: object,
    *,
    timeout_ms: int,
    closest_label: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    root = page.locator(".st-key-layout_probe")
    kwargs: dict[str, object] = {
        "viewport_width": 390,
        "viewport_height": 844,
        "target_overlap_tolerance": 0.5 if closest_label else 1.0,
        "closest_label": closest_label,
    }
    # The accepted implementation adds this parameter.  Omitting it against
    # the pre-fix worker makes the fail-first signal the actual clipping bug,
    # rather than an incidental signature TypeError.
    if "timeout_ms" in inspect.signature(
        browser_worker._focused_control_layout
    ).parameters:
        kwargs["timeout_ms"] = timeout_ms
    return browser_worker._focused_control_layout(
        page,
        root,
        tuple(
            (f"target-{index}", locator)
            for index, locator in enumerate(root.locator(".target").all())
        ),
        **kwargs,
    )


def test_real_chromium_focused_layout_temporarily_scrolls_and_restores() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    audit_y: list[float] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for root_height, closest_label in ((40, False), (64, True)):
                page = browser.new_page(viewport={"width": 390, "height": 844})
                _prepare_focused_scroll_layout(page, root_height=root_height)
                before = _focused_scroll_layout_state(page)
                before_projection = _focused_projection_root_bounds(
                    browser_worker, page
                )
                targets, layout = _call_focused_layout(
                    browser_worker,
                    page,
                    timeout_ms=1_000,
                    closest_label=closest_label,
                )
                after = _focused_scroll_layout_state(page)
                after_projection = _focused_projection_root_bounds(browser_worker, page)
                if before != after:
                    raise AssertionError((before, after))
                if {
                    key: before_projection[key] for key in ("x", "y", "width")
                } != {
                    key: after_projection[key] for key in ("x", "y", "width")
                }:
                    raise AssertionError((before_projection, after_projection))
                failed = [
                    key
                    for key in (
                        "rootClipping",
                        "targetClipping",
                        "targetOverlap",
                        "documentHorizontalOverflow",
                        "rootHorizontalOverflow",
                    )
                    if layout[key]
                ]
                if failed or len(targets) != 1:
                    raise AssertionError((failed, targets, layout))
                if any(
                    page.locator("html").get_attribute(name) != "true"
                    for name in (
                        "data-document-audit-scrolled",
                        "data-outer-audit-scrolled",
                        "data-inner-audit-scrolled",
                    )
                ):
                    raise AssertionError("document and nested scrollers were not audited")
                audit_y.append(float(layout["rootRect"]["y"]))
                page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            _prepare_focused_scroll_layout(page, behavior="transient")
            before = _focused_scroll_layout_state(page)
            _call_focused_layout(browser_worker, page, timeout_ms=1_000)
            if (
                page.locator(".st-key-layout_probe").get_attribute(
                    "data-motion-settled"
                )
                != "true"
                or _focused_scroll_layout_state(page) != before
            ):
                raise AssertionError("transient focused geometry was not settled/restored")
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            _prepare_focused_scroll_layout(page, precondition_growth=True)
            before = _focused_scroll_layout_state(page)
            _call_focused_layout(browser_worker, page, timeout_ms=1_000)
            if (
                page.locator("html").get_attribute("data-precondition-growth")
                != "true"
                or _focused_scroll_layout_state(page) != before
            ):
                raise AssertionError(
                    "valid prerequisite geometry growth was not stabilized/restored"
                )
            page.close()
        finally:
            browser.close()
    if len(audit_y) != 2 or audit_y[0] == audit_y[1]:
        raise AssertionError(("different root heights shared audit y", audit_y))


def test_real_chromium_focused_layout_failures_restore_and_stay_bounded() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for case, options in (
                ("horizontal", {"root_left": 500}),
                ("too-tall", {"root_height": 900}),
                ("perpetual", {"behavior": "perpetual"}),
            ):
                page = browser.new_page(viewport={"width": 390, "height": 844})
                _prepare_focused_scroll_layout(page, **options)
                before = _focused_scroll_layout_state(page)
                horizontal_audit_offsets: list[list[int]] = []

                def invoke_layout() -> object:
                    if case != "horizontal":
                        return _call_focused_layout(
                            browser_worker, page, timeout_ms=400
                        )
                    original_restore = browser_worker._restore_focused_scroll

                    def observe_horizontal_restore(
                        state_handle: object, *, horizontal_only: bool
                    ) -> None:
                        if horizontal_only:
                            horizontal_audit_offsets.append(
                                page.evaluate(
                                    """
                                    () => [
                                      document.querySelector('#outer').scrollLeft,
                                      document.querySelector('#inner').scrollLeft
                                    ]
                                    """
                                )
                            )
                        original_restore(
                            state_handle, horizontal_only=horizontal_only
                        )

                    with mock.patch.object(
                        browser_worker,
                        "_restore_focused_scroll",
                        side_effect=observe_horizontal_restore,
                    ):
                        return _call_focused_layout(
                            browser_worker, page, timeout_ms=400
                        )

                started = time.monotonic()
                failure = _raises(
                    browser_worker.WorkerBootstrapError,
                    invoke_layout,
                )
                elapsed = time.monotonic() - started
                after = _focused_scroll_layout_state(page)
                restored = (
                    _focused_scroll_position_and_generation(after)
                    == _focused_scroll_position_and_generation(before)
                    if case == "perpetual"
                    else after == before
                )
                if not restored or elapsed >= 2.0:
                    raise AssertionError(
                        (
                            case,
                            elapsed,
                            before,
                            after,
                        )
                    )
                expected_message = (
                    "focused control geometry did not stabilize"
                    if case == "perpetual"
                    else "focused control layout contract failed"
                )
                if str(failure) != expected_message:
                    raise AssertionError((case, failure))
                if any(
                    page.locator("html").get_attribute(name) != "true"
                    for name in (
                        "data-document-audit-scrolled",
                        "data-outer-audit-scrolled",
                        "data-inner-audit-scrolled",
                    )
                ):
                    raise AssertionError((case, "audit scroll did not run"))
                if case == "horizontal" and (
                    len(horizontal_audit_offsets) != 1
                    or horizontal_audit_offsets[0] == [3, 5]
                ):
                    raise AssertionError(
                        ("horizontal audit scroll did not run", horizontal_audit_offsets)
                    )
                if case == "perpetual" and (
                    page.locator(".st-key-layout_probe").get_attribute(
                        "data-motion-started"
                    )
                    != "true"
                ):
                    raise AssertionError("perpetual geometry audit never started")
                page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            _prepare_focused_scroll_layout(page, behavior="replace-on-restore")
            restore_only = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: _call_focused_layout(browser_worker, page, timeout_ms=1_000),
            )
            if (
                "restor" not in str(restore_only).lower()
                or page.locator("html").get_attribute("data-ancestor-replaced") != "true"
            ):
                raise AssertionError(
                    ("restore-only replacement was not rejected", restore_only)
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            _prepare_focused_scroll_layout(
                page, two_targets=True, behavior="replace-on-restore"
            )
            primary = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: _call_focused_layout(browser_worker, page, timeout_ms=1_000),
            )
            chained = primary.__cause__ or primary.__context__
            if (
                str(primary) != "focused control layout contract failed"
                or chained is None
                or "restor" not in str(chained).lower()
            ):
                raise AssertionError(
                    ("primary/restoration failure precedence changed", primary, chained)
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            _prepare_focused_scroll_layout(page, unresolved_font=True)
            before = _focused_scroll_layout_state(page)
            started = time.monotonic()
            font_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: _call_focused_layout(browser_worker, page, timeout_ms=400),
            )
            elapsed = time.monotonic() - started
            font_reads = page.locator("html").get_attribute("data-font-reads")
            if (
                font_reads is None
                or int(font_reads) < 1
                or _focused_scroll_position_and_generation(
                    _focused_scroll_layout_state(page)
                )
                != _focused_scroll_position_and_generation(before)
                or elapsed >= 2.0
            ):
                raise AssertionError(("font wait was not bounded/restored", font_reads, elapsed))
            if str(font_failure) != "focused control fonts did not stabilize":
                raise AssertionError(("font readiness failure differs", font_failure))
            if any(
                page.locator("html").get_attribute(name) is not None
                for name in (
                    "data-document-audit-scrolled",
                    "data-outer-audit-scrolled",
                    "data-inner-audit-scrolled",
                )
            ):
                raise AssertionError("font timeout reached the audit scroll")
            page.close()
        finally:
            browser.close()


def test_real_chromium_radio_audit_preserves_native_keys_without_rerender() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "risk-guard-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "risk-guard-controls",
            "route": "/__selection__/risk-guard",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    html = """
    <!doctype html>
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-rg_source{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [role=radiogroup]{display:flex;gap:4px;width:350px;height:32px}
      [role=radiogroup] label{position:relative;display:inline-flex;align-items:center;width:82px;height:24px}
      [role=radiogroup] input[type=radio]{position:absolute;width:0;height:0;margin:0;padding:0;border:0;clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;opacity:0}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="risk-guard-controls/mobile"
         data-render-generation="1">risk-guard-controls</div>
    <div class="st-key-rg_source">
      <div role="radiogroup" aria-label="來源">
        <label><input type="radio" name="source" value="手動輸入">手動輸入</label>
        <label><input type="radio" name="source" value="Watchlist" checked>Watchlist</label>
        <label><input type="radio" name="source" value="Screener 候選">Screener 候選</label>
        <label><input type="radio" name="source" value="IBKR 持倉">IBKR 持倉</label>
      </div>
    </div>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            _assert_hidden_native_radio_fixture(
                page,
                ".st-key-rg_source",
                ("手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"),
            )
            record = browser_worker._radio_control_evidence(
                page,
                identity,
                browser_worker._FOCUSED_CONTROL_CONTRACTS[
                    "risk-guard-controls"
                ][0],
                timeout_ms=5_000,
            )
        finally:
            browser.close()
    expected = _focused_control_evidence(identity, accessible=True)["controls"][0]
    for key in (
        "widget",
        "role",
        "accessibleName",
        "optionRole",
        "optionLabels",
        "auxiliaryButtons",
        "selectedLabel",
        "checkedLabels",
        "tabSequenceLabels",
        "afterArrowRight",
        "afterArrowLeft",
        "afterSpace",
        "selectionBasis",
    ):
        if record[key] != expected[key]:
            raise AssertionError((key, record[key], expected[key]))
    if any(
        target["width"] < 24 or target["height"] < 24
        for target in record["targets"]
    ):
        raise AssertionError(record["targets"])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            root = page.locator(".st-key-rg_source")
            group_html = root.locator('[role="radiogroup"]').evaluate(
                "node => node.outerHTML"
            )
            root.locator('[role="radiogroup"]').evaluate("node => node.remove()")
            page.evaluate(
                "({html}) => setTimeout(() => document.querySelector('.st-key-rg_source').insertAdjacentHTML('beforeend', html), 100)",
                {"html": group_html},
            )
            delayed = browser_worker._collect_focused_control_evidence(
                page, identity, timeout_ms=5_000
            )
            if delayed["projection"] != "accessible-required":
                raise AssertionError(delayed)
        finally:
            browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator(".st-key-rg_source").evaluate("node => node.replaceChildren()")
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=100
                ),
            )
        finally:
            browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator(".st-key-rg_source").evaluate(
                "element => element.insertAdjacentHTML("
                "'beforeend', '<button aria-label=\"help\">?</button>')"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=5_000
                ),
            )
        finally:
            browser.close()

    ai_identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "ai-chat-settings-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "ai-chat-settings-controls",
            "route": "/__selection__/ai-chat-settings",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    ai_html = """
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-ai_chat_mode{position:absolute;left:20px;top:60px;width:350px;height:64px}
      [data-testid=stWidgetLabel]{display:block;height:20px}
      [data-testid=stTooltipIcon],[data-testid=stTooltipHoverTarget]{display:inline-block}
      [data-testid=stTooltipHoverTarget] button{display:block;width:16px;height:16px;padding:0}
      [role=radiogroup]{display:flex;gap:4px;width:350px;height:32px}
      [role=radiogroup] label{position:relative;display:inline-flex;align-items:center;width:90px;height:24px}
      [role=radiogroup] input[type=radio]{position:absolute;width:0;height:0;margin:0;padding:0;border:0;clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;opacity:0}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="ai-chat-settings-controls/mobile"
         data-render-generation="1">ai-chat-settings-controls</div>
    <div class="st-key-ai_chat_mode" data-testid="stElementContainer">
      <label data-testid="stWidgetLabel">
        <span data-testid="stMarkdownContainer">模式</span>
        <span data-testid="stTooltipIcon"><span data-testid="stTooltipHoverTarget">
          <button type="button" aria-label="Help for 模式"><svg aria-hidden="true" focusable="false"></svg></button>
        </span></span>
      </label>
      <div role="radiogroup" aria-label="模式">
        <label><input type="radio" name="mode" value="快速問答" checked>快速問答</label>
        <label><input type="radio" name="mode" value="深度研究">深度研究</label>
      </div>
    </div>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(ai_html)
            _assert_hidden_native_radio_fixture(
                page,
                ".st-key-ai_chat_mode",
                ("快速問答", "深度研究"),
            )
            with_help = browser_worker._collect_focused_control_evidence(
                page, ai_identity, timeout_ms=5_000
            )
            if (
                with_help["projection"] != "accessible-required"
                or with_help["controls"][0]["auxiliaryButtons"]
                != ["Help for 模式"]
            ):
                raise AssertionError(with_help)
        finally:
            browser.close()

    for mutation in (
        "node => node.setAttribute('aria-label', 'Help')",
        "node => node.parentElement.removeAttribute('data-testid')",
        "node => node.closest('[data-testid=stTooltipIcon]').removeAttribute('data-testid')",
        "node => node.closest('[data-testid=stWidgetLabel]').replaceWith(node)",
        "node => node.closest('[data-testid=stWidgetLabel]').querySelector('[data-testid=stMarkdownContainer]').textContent='錯誤'",
        "node => node.closest('.st-key-ai_chat_mode').insertAdjacentHTML('beforeend', '<button aria-label=\"uncontracted destructive action\">!</button>')",
        "node => node.closest('.st-key-ai_chat_mode').insertAdjacentHTML('beforeend', '<div role=\"radiogroup\" aria-label=\"forged\"></div>')",
        "node => { const group=node.closest('.st-key-ai_chat_mode').querySelector('[role=radiogroup]'); group.parentElement.appendChild(group.lastElementChild); }",
    ):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.set_content(ai_html)
                page.get_by_role("button", name="Help for 模式", exact=True).evaluate(
                    mutation
                )
                _raises(
                    browser_worker.WorkerBootstrapError,
                    lambda: browser_worker._collect_focused_control_evidence(
                        page, ai_identity, timeout_ms=5_000
                    ),
                )
            finally:
                browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator(".st-key-rg_source").evaluate(
                "element => element.insertAdjacentHTML('beforeend', "
                "'<button>手動輸入</button><button>Watchlist</button>' +"
                "'<button>Screener 候選</button><button>IBKR 持倉</button>')"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=5_000
                ),
            )
        finally:
            browser.close()

    legacy_html = """
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-rg_source{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [data-baseweb=button-group]{display:flex;width:350px;height:32px}
      [data-baseweb=button-group] button{display:block;width:82px;height:24px}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="risk-guard-controls/mobile"
         data-render-generation="1">risk-guard-controls</div>
    <div class="st-key-rg_source" data-testid="stElementContainer">
      <div data-baseweb="button-group" role="radiogroup" aria-label="button group">
        <button kind="segmented_control">手動輸入</button>
        <button kind="segmented_controlActive">Watchlist</button>
        <button kind="segmented_control">Screener 候選</button>
        <button kind="segmented_control">IBKR 持倉</button>
      </div>
    </div>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(legacy_html)
            legacy_record = browser_worker._collect_focused_control_evidence(
                page, identity, timeout_ms=5_000
            )
            if legacy_record["projection"] != "legacy-segmented":
                raise AssertionError(legacy_record)
        finally:
            browser.close()

    for mutation in (
        "root => root.querySelector('[data-baseweb=button-group]').removeAttribute('data-baseweb')",
        "root => root.insertAdjacentHTML('beforeend', '<div role=\"radiogroup\" aria-label=\"forged\"></div>')",
        "root => root.appendChild(root.querySelector('[data-baseweb=button-group]').lastElementChild)",
        "root => root.insertAdjacentHTML('beforeend', '<input type=\"radio\" aria-label=\"Watchlist\" style=\"display:none\">')",
        "root => root.insertAdjacentHTML('beforeend', '<div data-baseweb=\"select\" style=\"display:none\"><input role=\"combobox\"></div>')",
    ):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.set_content(legacy_html)
                page.locator(".st-key-rg_source").evaluate(mutation)
                _raises(
                    browser_worker.WorkerBootstrapError,
                    lambda: browser_worker._collect_focused_control_evidence(
                        page, identity, timeout_ms=5_000
                    ),
                )
            finally:
                browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator('[role="radiogroup"]').evaluate(
                "element => element.insertBefore("
                "element.lastElementChild, element.firstElementChild)"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page,
                    identity,
                    browser_worker._FOCUSED_CONTROL_CONTRACTS[
                        "risk-guard-controls"
                    ][0],
                    timeout_ms=5_000,
                ),
            )
        finally:
            browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator('[role="radiogroup"]').evaluate(
                "element => element.insertAdjacentHTML("
                "'beforeend', '<a href=\"#\">extra focus target</a>')"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page,
                    identity,
                    browser_worker._FOCUSED_CONTROL_CONTRACTS[
                        "risk-guard-controls"
                    ][0],
                    timeout_ms=5_000,
                ),
            )
        finally:
            browser.close()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.locator('[role="radiogroup"]').evaluate(
                "element => element.insertAdjacentHTML("
                "'afterbegin', '<a href=\"#\">extra predecessor target</a>')"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page,
                    identity,
                    browser_worker._FOCUSED_CONTROL_CONTRACTS[
                        "risk-guard-controls"
                    ][0],
                    timeout_ms=5_000,
                ),
            )
        finally:
            browser.close()


def _hidden_radio_action_fixture() -> str:
    return """
    <!doctype html>
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-rg_source{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [role=radiogroup]{display:flex;gap:4px;width:350px;height:32px}
      [role=radiogroup] label{position:relative;display:inline-flex;align-items:center;width:82px;height:24px}
      [role=radiogroup] input[type=radio]{position:absolute;width:0;height:0;margin:0;padding:0;border:0;clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;opacity:0}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="risk-guard-controls/mobile"
         data-render-generation="1">risk-guard-controls</div>
    <div class="st-key-rg_source">
      <div role="radiogroup" aria-label="來源">
        <label><input type="radio" name="source" value="手動輸入">手動輸入</label>
        <label><input type="radio" name="source" value="Watchlist" checked>Watchlist</label>
        <label><input type="radio" name="source" value="Screener 候選">Screener 候選</label>
        <label><input type="radio" name="source" value="IBKR 持倉">IBKR 持倉</label>
      </div>
    </div>
    """


def test_real_chromium_hidden_radio_labels_are_semantic_and_actionable() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "risk-guard-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "risk-guard-controls",
            "route": "/__selection__/risk-guard",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    contract = browser_worker._FOCUSED_CONTROL_CONTRACTS["risk-guard-controls"][0]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_hidden_radio_action_fixture())
            _assert_hidden_native_radio_fixture(
                page,
                ".st-key-rg_source",
                ("手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"),
            )
            page.locator("body").evaluate(
                "node => node.insertAdjacentHTML('beforeend', '<form><input type=\"radio\" name=\"source\" value=\"other-form\"></form>')"
            )
            record = browser_worker._radio_control_evidence(
                page, identity, contract, timeout_ms=500
            )
            if record["checkedLabels"] != ["Watchlist"]:
                raise AssertionError(record)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(
                _hidden_radio_action_fixture().replace(
                    'name="source"', 'name=""'
                )
            )
            empty_name_radio = page.locator(
                '.st-key-rg_source input[value="Watchlist"]'
            )
            empty_name_label = browser_worker._validated_radio_label(
                empty_name_radio,
                root_selector=".st-key-rg_source",
                expected_label="Watchlist",
                expected_option_count=4,
                timeout_ms=500,
            )
            if (
                empty_name_radio.get_attribute("name") != ""
                or empty_name_label.count() != 1
                or not empty_name_label.is_visible()
            ):
                raise AssertionError("explicitly empty Streamlit radio name was rejected")
            page.locator("body").evaluate(
                "node => node.insertAdjacentHTML('beforeend', "
                "'<input type=\"radio\" name=\"\" value=\"unrelated\">')"
            )
            browser_worker._validated_radio_label(
                empty_name_radio,
                root_selector=".st-key-rg_source",
                expected_label="Watchlist",
                expected_option_count=4,
                timeout_ms=500,
            )
            page.locator(".st-key-rg_source").evaluate(
                "node => node.insertAdjacentHTML('beforeend', "
                "'<input type=\"radio\" name=\"\" value=\"forged\">')"
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._validated_radio_label(
                    empty_name_radio,
                    root_selector=".st-key-rg_source",
                    expected_label="Watchlist",
                    expected_option_count=4,
                    timeout_ms=500,
                ),
            )
        finally:
            browser.close()


def test_real_chromium_hidden_radio_labels_fail_closed_independently() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "risk-guard-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "risk-guard-controls",
            "route": "/__selection__/risk-guard",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    contract = browser_worker._FOCUSED_CONTROL_CONTRACTS["risk-guard-controls"][0]
    mutations = (
        (
            "missing-association",
            "node => { const label=node.closest('label'); label.replaceWith(node, document.createTextNode('Watchlist')); node.setAttribute('aria-label','Watchlist'); }",
        ),
        (
            "multiple-associations",
            "node => { node.id='duplicate-label-target'; node.closest('[role=radiogroup]').insertAdjacentHTML('beforeend','<label for=\"duplicate-label-target\">shadow</label>'); }",
        ),
        (
            "mismatched-label",
            "node => { node.setAttribute('aria-label','Watchlist'); node.closest('label').lastChild.textContent='錯誤'; }",
        ),
        (
            "non-wrapping-label",
            "node => { const label=node.closest('label'); node.id='external-label-target'; label.replaceWith(node); node.insertAdjacentHTML('afterend','<label for=\"external-label-target\">Watchlist</label>'); }",
        ),
        (
            "zero-size-label",
            "node => { const label=node.closest('label'); Object.assign(label.style,{position:'absolute',display:'block',width:'0px',height:'0px',minWidth:'0px',minHeight:'0px',padding:'0',border:'0',overflow:'hidden',fontSize:'0px'}); }",
        ),
        (
            "transparent-label",
            "node => { node.closest('label').style.opacity='0'; }",
        ),
        ("disabled", "node => node.disabled=true"),
        ("inert", "node => node.closest('label').inert=true"),
        ("aria-disabled", "node => node.closest('label').setAttribute('aria-disabled','true')"),
        ("label-pointer-events-none", "node => node.closest('label').style.pointerEvents='none'"),
        ("input-pointer-events-none", "node => node.style.pointerEvents='none'"),
        (
            "missing-native-name-attributes",
            "node => node.closest('[role=radiogroup]').querySelectorAll('input[type=radio]').forEach(candidate => candidate.removeAttribute('name'))",
        ),
        (
            "mixed-native-names",
            "node => node.setAttribute('name','different-source')",
        ),
        (
            "occluded",
            "node => { const box=node.closest('label').getBoundingClientRect(); const cover=document.createElement('div'); cover.id='cover'; Object.assign(cover.style,{position:'fixed',left:box.left+'px',top:box.top+'px',width:box.width+'px',height:box.height+'px',zIndex:'9999',background:'black'}); document.body.appendChild(cover); }",
        ),
        ("out-of-group", "node => node.closest('.st-key-rg_source').appendChild(node.closest('label'))"),
        ("out-of-root", "node => document.body.appendChild(node.closest('label'))"),
        (
            "external-native-group-member",
            "node => document.body.insertAdjacentHTML('beforeend','<input type=\"radio\" name=\"source\" value=\"outside\">')",
        ),
        (
            "internal-hidden-native-group-member",
            "node => node.closest('[role=radiogroup]').insertAdjacentHTML('beforeend','<input type=\"radio\" name=\"source\" value=\"hidden-extra\" style=\"display:none\">')",
        ),
        (
            "hidden-legacy-primary",
            "node => node.closest('.st-key-rg_source').insertAdjacentHTML('beforeend','<div data-baseweb=\"button-group\" role=\"radiogroup\" style=\"display:none\"><button>forged</button></div>')",
        ),
        ("duplicate-choice", "node => node.closest('[role=radiogroup]').appendChild(node.closest('label').cloneNode(true))"),
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            unexpected: list[tuple[str, str, str]] = []
            for label, mutation in mutations:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                try:
                    page.set_content(_hidden_radio_action_fixture())
                    radio = page.locator('.st-key-rg_source input[value="Watchlist"]')
                    if radio.count() != 1 or radio.is_visible():
                        raise AssertionError((label, radio.count(), radio.is_visible()))
                    radio.evaluate(mutation)
                    try:
                        failure = _raises(
                            browser_worker.WorkerBootstrapError,
                            lambda: browser_worker._radio_control_evidence(
                                page, identity, contract, timeout_ms=500
                            ),
                        )
                        if not str(failure):
                            raise AssertionError((label, failure))
                    except BaseException as exc:  # noqa: BLE001
                        unexpected.append((label, type(exc).__name__, str(exc)))
                finally:
                    page.close()
            if unexpected:
                raise AssertionError(unexpected)
        finally:
            browser.close()


def test_real_chromium_radio_audit_rejects_pre_guard_rerender_and_restores_initial_scroll() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "risk-guard-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "risk-guard-controls",
            "route": "/__selection__/risk-guard",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    contract = browser_worker._FOCUSED_CONTROL_CONTRACTS["risk-guard-controls"][0]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_hidden_radio_action_fixture())
            page.locator(
                '.st-key-rg_source input[value="Watchlist"]'
            ).evaluate(
                """
                node => node.addEventListener('keydown', event => {
                  if (event.key !== 'Tab') return;
                  const marker = document.querySelector('#ux1b-selection-ready');
                  marker.dataset.renderGeneration = String(
                    Number(marker.dataset.renderGeneration) + 1
                  );
                })
                """
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page, identity, contract, timeout_ms=500
                ),
            )
            if (
                page.locator("#ux1b-selection-ready").get_attribute(
                    "data-render-generation"
                )
                == "1"
            ):
                raise AssertionError("Tab rerender mutation did not execute")
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_hidden_radio_action_fixture())
            page.locator(
                '.st-key-rg_source input[value="Watchlist"]'
            ).evaluate(
                """
                node => node.addEventListener('focus', () => {
                  const marker = document.querySelector('#ux1b-selection-ready');
                  marker.dataset.renderGeneration = String(
                    Number(marker.dataset.renderGeneration) + 1
                  );
                }, {once:true})
                """
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page, identity, contract, timeout_ms=500
                ),
            )
            if (
                page.locator("#ux1b-selection-ready").get_attribute(
                    "data-render-generation"
                )
                == "1"
            ):
                raise AssertionError("focus rerender mutation did not execute")
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_hidden_radio_action_fixture())
            selected_radio = page.locator(
                '.st-key-rg_source input[value="Watchlist"]'
            )
            selected_radio.evaluate(
                """
                node => node.addEventListener('focus', () => {
                  node.id = 'focus-association-target';
                  node.closest('[role=radiogroup]').insertAdjacentHTML(
                    'beforeend',
                    '<label for="focus-association-target" style="display:none">shadow</label>'
                  );
                }, {once:true})
                """
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._radio_control_evidence(
                    page, identity, contract, timeout_ms=500
                ),
            )
            if selected_radio.evaluate("node => node.labels.length") != 2:
                raise AssertionError("focus association mutation did not execute")
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            below_fold = _hidden_radio_action_fixture().replace(
                "html,body{margin:0;width:390px;overflow-x:hidden}",
                "html,body{margin:0;width:390px;min-height:1800px;overflow-x:hidden}",
            ).replace(
                "top:60px",
                "top:1200px",
            )
            page.set_content(below_fold)
            before = page.evaluate(
                "() => ({x:window.scrollX,y:window.scrollY})"
            )
            record = browser_worker._radio_control_evidence(
                page, identity, contract, timeout_ms=1_000
            )
            after = page.evaluate(
                "() => ({x:window.scrollX,y:window.scrollY})"
            )
            if before != {"x": 0, "y": 0} or after != before:
                raise AssertionError((before, after, record["layout"]))
            page.close()
        finally:
            browser.close()


def test_real_chromium_ai_hidden_labels_reacquire_after_subtree_replacement() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "ai-chat-settings-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "ai-chat-settings-controls",
            "route": "/__selection__/ai-chat-settings",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    html = """
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      #panel{display:none}
      .st-key-ai_chat_mode{position:absolute;left:20px;top:80px;width:350px;height:40px}
      [role=radiogroup]{display:flex;gap:4px;width:350px;height:32px}
      [role=radiogroup] label{position:relative;display:inline-flex;align-items:center;width:90px;height:24px}
      [role=radiogroup] input[type=radio]{position:absolute;width:0;height:0;margin:0;padding:0;border:0;clip:rect(0 0 0 0);clip-path:inset(50%);overflow:hidden;opacity:0}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="ai-chat-settings-controls/mobile"
         data-render-generation="1">ai-chat-settings-controls</div>
    <button id="launcher" type="button">AI</button>
    <section id="panel"><div>AI 對話</div><button id="settings" type="button">設定與歷史</button><div id="mount"></div></section>
    <script>
      window.actionAudit={labelPointerdowns:0,inputPointerdowns:0,labelClicks:[],nativeInputClicks:[],changes:[],rendered:[]};
      let generation=1;
      const marker=document.querySelector('#ux1b-selection-ready');
      const bump=()=>marker.dataset.renderGeneration=String(++generation);
      const renderMode=selected=>{
        const version=window.actionAudit.rendered.length+1;
        document.querySelector('#mount').innerHTML=`<div class="st-key-ai_chat_mode" data-version="${version}"><div role="radiogroup" aria-label="模式" data-version="${version}"><label data-choice="快速問答"><input type="radio" name="mode" value="快速問答" ${selected==='快速問答'?'checked':''}>快速問答</label><label data-choice="深度研究"><input type="radio" name="mode" value="深度研究" ${selected==='深度研究'?'checked':''}>深度研究</label></div></div>`;
        window.actionAudit.rendered.push(version);
      };
      document.querySelector('#launcher').addEventListener('click',()=>{document.querySelector('#panel').style.display='block';bump();});
      document.querySelector('#settings').addEventListener('click',()=>renderMode('快速問答'));
      document.addEventListener('pointerdown',event=>{
        if (!event.target.closest('.st-key-ai_chat_mode')) return;
        if (event.target.matches('input[type=radio]')) window.actionAudit.inputPointerdowns++;
        else if (event.target.closest('label[data-choice]')) window.actionAudit.labelPointerdowns++;
      },true);
      document.addEventListener('click',event=>{
        if (!event.target.closest('.st-key-ai_chat_mode')) return;
        if (event.target.matches('input[type=radio]')) {
          window.actionAudit.nativeInputClicks.push(event.target.value);
          return;
        }
        const label=event.target.closest('label[data-choice]');
        if (!label) return;
        window.actionAudit.labelClicks.push(label.dataset.choice);
      },true);
      document.addEventListener('change',event=>{
        if (!event.target.matches('.st-key-ai_chat_mode input[type=radio]')) return;
        window.actionAudit.changes.push(event.target.value);
        renderMode(event.target.value);
        bump();
      },true);
    </script>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            record = browser_worker._perform_capture_interaction(
                page, identity, timeout_ms=2_000
            )
            root = page.locator(".st-key-ai_chat_mode")
            group = root.get_by_role("radiogroup", name="模式", exact=True)
            quick = group.get_by_role("radio", name="快速問答", exact=True)
            quick_label = quick.locator("xpath=ancestor::label[1]")
            audit = page.evaluate("() => window.actionAudit")
            if (
                record is None
                or root.count() != 1
                or root.get_attribute("data-version") != "3"
                or group.get_attribute("data-version") != "3"
                or quick.count() != 1
                or quick.is_visible()
                or not quick.is_checked()
                or quick_label.count() != 1
                or not quick_label.is_visible()
                or audit
                != {
                    "labelPointerdowns": 2,
                    "inputPointerdowns": 0,
                    "labelClicks": ["深度研究", "快速問答"],
                    "nativeInputClicks": ["深度研究", "快速問答"],
                    "changes": ["深度研究", "快速問答"],
                    "rendered": [1, 2, 3],
                }
            ):
                raise AssertionError((record, audit))
        finally:
            browser.close()


def test_real_chromium_selectbox_audit_selects_and_restores_after_rerender() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "analytics-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "analytics-controls",
            "route": "/__selection__/analytics-db",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    html = """
    <!doctype html>
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-adb_table{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [data-baseweb=select]{width:350px;height:32px}
      [data-baseweb=icon]{width:20px;height:20px}
      [role=combobox]{box-sizing:border-box;width:350px;height:32px;padding:4px}
      [data-testid=stSelectboxVirtualDropdown]{position:absolute;left:20px;top:96px;width:350px}
      [role=option]{box-sizing:border-box;width:350px;height:28px;padding:4px}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="analytics-controls/mobile"
         data-render-generation="1">analytics-controls</div>
    <div class="st-key-adb_table">
      <div data-baseweb="select">
        <span data-selected>candidate_rankings</span>
        <input role="combobox" aria-label="Selected candidate_rankings. 資料表"
               aria-expanded="false" aria-haspopup="listbox"
               aria-autocomplete="list" tabindex="0" value="">
        <svg data-baseweb="icon" title="Clear value" viewBox="0 0 24 24"
             aria-label="Clear value" role="button"><title>Clear value</title><path></path></svg>
      </div>
    </div>
    <script>
      const labels = ['candidate_rankings', 'iv_history'];
      const combobox = document.querySelector('[role=combobox]');
      const selectedValue = document.querySelector('[data-selected]');
      const marker = document.querySelector('#ux1b-selection-ready');
      let selected = 0;
      let highlighted = 0;
      let open = false;
      let activePopover = null;
      function closeListbox() {
        activePopover?.remove();
        activePopover = null;
        combobox.setAttribute('aria-expanded', 'false');
        combobox.removeAttribute('aria-controls');
        open = false;
      }
      function renderListbox() {
        const wasOpen = open;
        activePopover?.remove();
        const popover = document.createElement('div');
        popover.setAttribute('data-baseweb', 'popover');
        const listbox = document.createElement('ul');
        listbox.setAttribute('data-testid', 'stSelectboxVirtualDropdown');
        window.popupRenderCount = (window.popupRenderCount || 0) + 1;
        for (let index = 0; index < labels.length; index += 1) {
          const option = document.createElement('li');
          option.id = `synthetic-option-${window.popupRenderCount}-${index}`;
          option.setAttribute('role', 'option');
          option.setAttribute('aria-disabled', 'false');
          option.setAttribute('aria-selected', String(index === highlighted));
          option.textContent = labels[index];
          listbox.appendChild(option);
        }
        popover.appendChild(listbox);
        document.body.appendChild(popover);
        activePopover = popover;
        window.popupMutation?.(popover, listbox);
        combobox.setAttribute('aria-expanded', 'true');
        combobox.setAttribute('aria-controls', 'synthetic-table-list');
        if (wasOpen) {
          combobox.setAttribute(
            'aria-activedescendant', listbox.children[highlighted].id
          );
        }
        open = true;
      }
      combobox.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          if (!open) {
            highlighted = selected;
          } else {
            highlighted = (highlighted + 1) % labels.length;
          }
          renderListbox();
        } else if (event.key === 'ArrowUp') {
          event.preventDefault();
          if (!open) {
            highlighted = selected;
          } else {
            highlighted = (highlighted - 1 + labels.length) % labels.length;
          }
          renderListbox();
        } else if (event.key === 'Escape' && open) {
          event.preventDefault();
          closeListbox();
        } else if (event.key === 'Enter' && open) {
          event.preventDefault();
          selected = highlighted;
          selectedValue.textContent = labels[selected];
          combobox.setAttribute(
            'aria-label', `Selected ${labels[selected]}. 資料表`
          );
          closeListbox();
          marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 1
          );
        }
      });
    </script>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            record = browser_worker._selectbox_control_evidence(
                page,
                identity,
                browser_worker._FOCUSED_CONTROL_CONTRACTS[
                    "analytics-controls"
                ][0],
                timeout_ms=5_000,
            )
            generation = page.locator("#ux1b-selection-ready").get_attribute(
                "data-render-generation"
            )
            page.close()

            for label, mutation in (
                (
                    "missing-clear",
                    "root => root.querySelector('[aria-label=\"Clear value\"]').remove()",
                ),
                (
                    "renamed-clear",
                    "root => root.querySelector('[aria-label=\"Clear value\"]').setAttribute('aria-label','Reset')",
                ),
                (
                    "duplicate-clear",
                    "root => { const button=root.querySelector('[aria-label=\"Clear value\"]'); button.parentElement.appendChild(button.cloneNode(true)); }",
                ),
                (
                    "detached-clear",
                    "root => document.body.appendChild(root.querySelector('[aria-label=\"Clear value\"]'))",
                ),
                (
                    "aria-disabled-clear",
                    "root => root.querySelector('[aria-label=\"Clear value\"]').setAttribute('aria-disabled','true')",
                ),
                (
                    "transparent-clear",
                    "root => root.querySelector('[aria-label=\"Clear value\"]').style.opacity='0'",
                ),
                (
                    "extra-button",
                    "root => root.insertAdjacentHTML('beforeend','<button type=\"button\" aria-label=\"forged\">!</button>')",
                ),
                (
                    "wrong-selected-name",
                    "root => root.querySelector('[role=combobox]').setAttribute('aria-label','資料表')",
                ),
                (
                    "not-tab-reachable",
                    "root => root.querySelector('[role=combobox]').tabIndex=-1",
                ),
                (
                    "readonly-combobox",
                    "root => root.querySelector('[role=combobox]').readOnly=true",
                ),
                (
                    "aria-readonly-combobox",
                    "root => root.querySelector('[role=combobox]').setAttribute('aria-readonly','true')",
                ),
                (
                    "required-combobox",
                    "root => root.querySelector('[role=combobox]').required=true",
                ),
                (
                    "aria-required-combobox",
                    "root => root.querySelector('[role=combobox]').setAttribute('aria-required','true')",
                ),
                (
                    "aria-invalid-combobox",
                    "root => root.querySelector('[role=combobox]').setAttribute('aria-invalid','true')",
                ),
                (
                    "contenteditable-combobox",
                    "root => root.querySelector('[role=combobox]').setAttribute('contenteditable','true')",
                ),
                (
                    "preexisting-popup",
                    "root => document.body.insertAdjacentHTML('beforeend','<div data-baseweb=\"popover\"><ul data-testid=\"stSelectboxVirtualDropdown\"></ul></div>')",
                ),
                (
                    "hidden-legacy-primary",
                    "root => root.insertAdjacentHTML('beforeend','<div data-baseweb=\"button-group\" role=\"radiogroup\" style=\"display:none\"><button>candidate_rankings</button></div>')",
                ),
            ):
                page = browser.new_page(viewport={"width": 390, "height": 844})
                try:
                    page.set_content(html)
                    page.locator(".st-key-adb_table").evaluate(mutation)
                    failure = _raises(
                        browser_worker.WorkerBootstrapError,
                        lambda: browser_worker._collect_focused_control_evidence(
                            page, identity, timeout_ms=300
                        ),
                    )
                    if not str(failure):
                        raise AssertionError((label, failure))
                finally:
                    page.close()

            for label, popup_mutation in (
                (
                    "popup-role-listbox",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.setAttribute('role','listbox'); }",
                ),
                (
                    "popup-wrong-identity",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.setAttribute('data-testid','forged-dropdown'); }",
                ),
                (
                    "popup-without-baseweb-popover",
                    "() => { window.popupMutation = (popover, _listbox) => popover.removeAttribute('data-baseweb'); }",
                ),
                (
                    "popup-duplicate-option-ids",
                    "() => { window.popupMutation = (_popover, listbox) => { listbox.lastElementChild.id=listbox.firstElementChild.id; }; }",
                ),
                (
                    "popup-missing-option-id",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.firstElementChild.removeAttribute('id'); }",
                ),
                (
                    "popup-disabled-option",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.firstElementChild.setAttribute('aria-disabled','true'); }",
                ),
                (
                    "popup-forged-option-aria-label",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').setAttribute('aria-label','Forged'); }",
                ),
                (
                    "popup-forged-option-aria-labelledby",
                    "() => { window.popupMutation = (_popover, listbox) => { document.body.insertAdjacentHTML('beforeend','<span id=forged-option-label>Forged</span>'); listbox.querySelector('[aria-selected=true]').setAttribute('aria-labelledby','forged-option-label'); }; }",
                ),
                (
                    "popup-tab-reachable-option",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').tabIndex=0; }",
                ),
                (
                    "popup-nested-option-button",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').insertAdjacentHTML('beforeend','<button type=button aria-label=Forged></button>'); }",
                ),
                (
                    "popup-nested-option-tab-stop",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').insertAdjacentHTML('beforeend','<span tabindex=0></span>'); }",
                ),
                (
                    "popup-hidden-option-name",
                    "() => { window.popupMutation = (_popover, listbox) => { const option=listbox.querySelector('[aria-selected=true]'); option.innerHTML=`<span aria-hidden=true>${option.textContent}</span>`; }; }",
                ),
                (
                    "popup-forged-option-alt-name",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').insertAdjacentHTML('beforeend','<img alt=Forged>'); }",
                ),
                (
                    "popup-transparent-selected-option",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').style.opacity='0'; }",
                ),
                (
                    "popup-inert-selected-option",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').setAttribute('inert',''); }",
                ),
                (
                    "popup-pointer-disabled-selected-option",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.querySelector('[aria-selected=true]').style.pointerEvents='none'; }",
                ),
                (
                    "popup-non-li-option",
                    "() => { window.popupMutation = (_popover, listbox) => { const source=listbox.firstElementChild; const forged=document.createElement('div'); for (const attr of source.attributes) forged.setAttribute(attr.name,attr.value); forged.textContent=source.textContent; source.replaceWith(forged); }; }",
                ),
                (
                    "popup-multiple-selected-options",
                    "() => { window.popupMutation = (_popover, listbox) => listbox.lastElementChild.setAttribute('aria-selected','true'); }",
                ),
                (
                    "popup-wrong-single-selected-option",
                    "() => { window.popupMutation = (_popover, listbox) => { listbox.firstElementChild.setAttribute('aria-selected','false'); listbox.lastElementChild.setAttribute('aria-selected','true'); }; }",
                ),
                (
                    "popup-second-render-role-listbox",
                    "() => { window.popupMutation = (_popover, listbox) => { if (window.popupRenderCount === 2) listbox.setAttribute('role','listbox'); }; }",
                ),
                (
                    "popup-second-render-readonly-combobox",
                    "() => { window.popupMutation = () => { if (window.popupRenderCount === 2) document.querySelector('[role=combobox]').setAttribute('aria-readonly','true'); }; }",
                ),
                (
                    "popup-duplicate-baseweb-popover",
                    "() => { window.popupMutation = (popover, _listbox) => popover.insertAdjacentHTML('beforeend','<div data-baseweb=\"popover\"></div>'); }",
                ),
            ):
                page = browser.new_page(viewport={"width": 390, "height": 844})
                try:
                    page.set_content(html)
                    page.evaluate(popup_mutation)
                    failure = _raises(
                        browser_worker.WorkerBootstrapError,
                        lambda: browser_worker._collect_focused_control_evidence(
                            page, identity, timeout_ms=300
                        ),
                    )
                    cleanup_state = page.evaluate(
                        """
                        () => ({
                          expanded: document.querySelector('[role=combobox]')
                            .getAttribute('aria-expanded'),
                          controls: document.querySelector('[role=combobox]')
                            .getAttribute('aria-controls'),
                          popovers: document.querySelectorAll(
                            '[data-baseweb=popover]'
                          ).length,
                          dropdowns: document.querySelectorAll(
                            '[data-testid=stSelectboxVirtualDropdown]'
                          ).length
                        })
                        """
                    )
                    if (
                        not str(failure)
                        or "failed-open" in str(failure)
                        or cleanup_state
                        != {
                            "expanded": "false",
                            "controls": None,
                            "popovers": 0,
                            "dropdowns": 0,
                        }
                    ):
                        raise AssertionError((label, failure, cleanup_state))
                finally:
                    page.close()

            race_html = html.replace(
                """marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 1
          );""",
                """marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration)
          );""",
            )
            if race_html == html:
                raise AssertionError("selectbox commit generation fixture did not mutate")
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(race_html)
            page.evaluate(
                """
                () => {
                  window.popupMutation = (_popover, listbox) => {
                    if (window.popupRenderCount !== 1) return;
                    listbox.style.opacity = '0';
                    setTimeout(() => {
                      const marker = document.querySelector(
                        '#ux1b-selection-ready'
                      );
                      marker.dataset.renderGeneration = String(
                        Number(marker.dataset.renderGeneration) + 1
                      );
                      listbox.style.opacity = '1';
                    }, 50);
                  };
                }
                """
            )
            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=1_000
                ),
            )
            race_state = page.evaluate(
                """
                () => ({
                  generation: document.querySelector('#ux1b-selection-ready')
                    .dataset.renderGeneration,
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  controls: document.querySelector('[role=combobox]')
                    .getAttribute('aria-controls'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length
                })
                """
            )
            if race_state != {
                "generation": "2",
                "expanded": "false",
                "controls": None,
                "popovers": 0,
            }:
                raise AssertionError(race_state)
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(race_html)
            page.evaluate(
                """
                () => {
                  window.enterCount = 0;
                  const combobox = document.querySelector('[role=combobox]');
                  combobox.addEventListener('keydown', event => {
                    if (event.key === 'Enter') window.enterCount += 1;
                  }, {capture: true});
                  window.popupMutation = (_popover, _listbox) => {
                    if (window.popupRenderCount !== 2) return;
                    setTimeout(() => {
                      const marker = document.querySelector(
                        '#ux1b-selection-ready'
                      );
                      marker.dataset.renderGeneration = String(
                        Number(marker.dataset.renderGeneration) + 1
                      );
                    }, 150);
                  };
                }
                """
            )
            delayed_navigation_started = time.monotonic()
            delayed_navigation_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=1_500
                ),
            )
            delayed_navigation_elapsed = (
                time.monotonic() - delayed_navigation_started
            )
            delayed_navigation_state = page.evaluate(
                """
                () => ({
                  generation: document.querySelector('#ux1b-selection-ready')
                    .dataset.renderGeneration,
                  enterCount: window.enterCount,
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  controls: document.querySelector('[role=combobox]')
                    .getAttribute('aria-controls'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length,
                  x: window.scrollX,
                  y: window.scrollY
                })
                """
            )
            if (
                "navigation rerendered before commit"
                not in str(delayed_navigation_failure)
                or delayed_navigation_elapsed >= 1.5
                or delayed_navigation_state
                != {
                    "generation": "2",
                    "enterCount": 0,
                    "expanded": "false",
                    "controls": None,
                    "popovers": 0,
                    "dropdowns": 0,
                    "x": 0,
                    "y": 0,
                }
            ):
                raise AssertionError(
                    (
                        delayed_navigation_failure,
                        delayed_navigation_elapsed,
                        delayed_navigation_state,
                    )
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.evaluate(
                """
                () => {
                  window.enterCount = 0;
                  const combobox = document.querySelector('[role=combobox]');
                  combobox.addEventListener('keydown', event => {
                    if (event.key === 'Enter') window.enterCount += 1;
                  }, {capture: true});
                  window.popupMutation = (_popover, listbox) => {
                    if (window.popupRenderCount !== 2) return;
                    setTimeout(() => {
                      const option = listbox.querySelector(
                        '[aria-selected=true]'
                      );
                      option.innerHTML =
                        `<span aria-hidden=true>${option.textContent}</span>`;
                    }, 100);
                  };
                }
                """
            )
            delayed_name_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=1_500
                ),
            )
            delayed_name_state = page.evaluate(
                """
                () => ({
                  generation: document.querySelector('#ux1b-selection-ready')
                    .dataset.renderGeneration,
                  enterCount: window.enterCount,
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length
                })
                """
            )
            if (
                "precommit popup state differs"
                not in str(delayed_name_failure)
                or delayed_name_state
                != {
                    "generation": "1",
                    "enterCount": 0,
                    "expanded": "false",
                    "popovers": 0,
                    "dropdowns": 0,
                }
            ):
                raise AssertionError(
                    (delayed_name_failure, delayed_name_state)
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.evaluate(
                """
                () => {
                  window.enterCount = 0;
                  const combobox = document.querySelector('[role=combobox]');
                  combobox.addEventListener('keydown', event => {
                    if (event.key === 'Enter') window.enterCount += 1;
                  }, {capture: true});
                  window.popupMutation = (popover, listbox) => {
                    if (window.popupRenderCount !== 2) return;
                    for (const option of listbox.querySelectorAll('[role=option]')) {
                      option.classList.add('late-forged-option-name');
                    }
                    setTimeout(() => {
                      popover.insertAdjacentHTML(
                        'beforeend',
                        '<style>.late-forged-option-name::after{content:"Forged"}</style>'
                      );
                    }, 100);
                  };
                }
                """
            )
            delayed_css_name_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=1_500
                ),
            )
            delayed_css_name_state = page.evaluate(
                """
                () => ({
                  generation: document.querySelector('#ux1b-selection-ready')
                    .dataset.renderGeneration,
                  enterCount: window.enterCount,
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length
                })
                """
            )
            if (
                "option accessible name differs"
                not in str(delayed_css_name_failure)
                or delayed_css_name_state
                != {
                    "generation": "1",
                    "enterCount": 0,
                    "expanded": "false",
                    "popovers": 0,
                    "dropdowns": 0,
                }
            ):
                raise AssertionError(
                    (delayed_css_name_failure, delayed_css_name_state)
                )
            page.close()

            double_commit_html = html.replace(
                """marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 1
          );""",
                """marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 2
          );""",
            )
            if double_commit_html == html:
                raise AssertionError(
                    "selectbox double-commit generation fixture did not mutate"
                )
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(double_commit_html)
            page.evaluate(
                """
                () => {
                  window.enterCount = 0;
                  document.querySelector('[role=combobox]').addEventListener(
                    'keydown',
                    event => {
                      if (event.key === 'Enter') window.enterCount += 1;
                    },
                    {capture: true}
                  );
                }
                """
            )
            double_commit_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=2_000
                ),
            )
            double_commit_state = page.evaluate(
                """
                () => ({
                  generation: document.querySelector('#ux1b-selection-ready')
                    .dataset.renderGeneration,
                  enterCount: window.enterCount,
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  controls: document.querySelector('[role=combobox]')
                    .getAttribute('aria-controls'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length
                })
                """
            )
            if (
                "commit generation is not exact"
                not in str(double_commit_failure)
                or double_commit_state
                != {
                    "generation": "3",
                    "enterCount": 1,
                    "expanded": "false",
                    "controls": None,
                    "popovers": 0,
                    "dropdowns": 0,
                }
            ):
                raise AssertionError(
                    (double_commit_failure, double_commit_state)
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.evaluate(
                """
                () => {
                  window.popupMutation = (_popover, listbox) => {
                    if (window.popupRenderCount === 2) {
                      listbox.style.opacity = '0';
                    }
                  };
                }
                """
            )
            timeout_cleanup_started = time.monotonic()
            timeout_cleanup_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=500
                ),
            )
            timeout_cleanup_elapsed = time.monotonic() - timeout_cleanup_started
            timeout_cleanup_state = page.evaluate(
                """
                () => ({
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  controls: document.querySelector('[role=combobox]')
                    .getAttribute('aria-controls'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length,
                  x: window.scrollX,
                  y: window.scrollY
                })
                """
            )
            if (
                "dropdown signature" not in str(timeout_cleanup_failure)
                or "popup cleanup" in str(timeout_cleanup_failure)
                or timeout_cleanup_elapsed >= 1.0
                or timeout_cleanup_state
                != {
                    "expanded": "false",
                    "controls": None,
                    "popovers": 0,
                    "dropdowns": 0,
                    "x": 0,
                    "y": 0,
                }
            ):
                raise AssertionError(
                    (
                        timeout_cleanup_failure,
                        timeout_cleanup_elapsed,
                        timeout_cleanup_state,
                    )
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)
            page.evaluate(
                """
                () => {
                  window.popupMutation = (_popover, listbox) => {
                    if (window.popupRenderCount === 1) {
                      listbox.style.opacity = '0';
                    }
                  };
                  document.querySelector('[role=combobox]').addEventListener(
                    'keydown',
                    event => {
                      if (event.key !== 'Escape') return;
                      event.preventDefault();
                      event.stopImmediatePropagation();
                    },
                    {capture: true}
                  );
                }
                """
            )
            hostile_cleanup_started = time.monotonic()
            hostile_cleanup_failure = _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._collect_focused_control_evidence(
                    page, identity, timeout_ms=600
                ),
            )
            hostile_cleanup_elapsed = time.monotonic() - hostile_cleanup_started
            hostile_cleanup_state = page.evaluate(
                """
                () => ({
                  expanded: document.querySelector('[role=combobox]')
                    .getAttribute('aria-expanded'),
                  popovers: document.querySelectorAll(
                    '[data-baseweb=popover]'
                  ).length,
                  dropdowns: document.querySelectorAll(
                    '[data-testid=stSelectboxVirtualDropdown]'
                  ).length
                })
                """
            )
            if (
                "dropdown signature" not in str(hostile_cleanup_failure)
                or hostile_cleanup_elapsed >= 0.9
                or hostile_cleanup_state
                != {
                    "expanded": "true",
                    "popovers": 1,
                    "dropdowns": 1,
                }
            ):
                raise AssertionError(
                    (
                        hostile_cleanup_failure,
                        hostile_cleanup_elapsed,
                        hostile_cleanup_state,
                    )
                )
            page.close()

            page = browser.new_page(viewport={"width": 390, "height": 844})
            below_fold = html.replace(
                "html,body{margin:0;width:390px;overflow-x:hidden}",
                "html,body{margin:0;width:390px;min-height:1800px;overflow-x:hidden}",
            ).replace("top:60px", "top:1200px", 1)
            page.set_content(below_fold)
            before = page.evaluate("() => ({x:window.scrollX,y:window.scrollY})")
            below_fold_record = browser_worker._selectbox_control_evidence(
                page,
                identity,
                browser_worker._FOCUSED_CONTROL_CONTRACTS[
                    "analytics-controls"
                ][0],
                timeout_ms=5_000,
            )
            after = page.evaluate("() => ({x:window.scrollX,y:window.scrollY})")
            if before != {"x": 0, "y": 0} or after != before:
                raise AssertionError((before, after, below_fold_record["layout"]))
            page.close()
        finally:
            browser.close()
    expected = _focused_control_evidence(identity, accessible=True)["controls"][0]
    for key in (
        "widget",
        "role",
        "accessibleName",
        "optionRole",
        "optionLabels",
        "auxiliaryButtons",
        "selectedLabel",
        "afterArrowDown",
        "afterArrowUp",
        "selectionBasis",
    ):
        if record[key] != expected[key]:
            raise AssertionError((key, record[key], expected[key]))
    if generation != "3" or any(
        target["width"] < 24 or target["height"] < 24
        for target in record["targets"]
    ):
        raise AssertionError((generation, record["targets"]))


def test_real_chromium_rerendering_scroll_audit_rejects_root_chain_replacement() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    html = """
    <!doctype html>
    <style>
      html,body{margin:0;width:390px;height:844px}
      #a,#b{width:390px;height:300px;overflow:auto}
      .root{width:350px;height:40px}
    </style>
    <div id="a"><div class="root">root</div></div><div id="b"></div>
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(html)

            def move_root(
                _audit_deadline: float,
                _cleanup_deadline: float,
            ) -> dict[str, bool]:
                page.locator("#b").evaluate(
                    "target => target.appendChild(document.querySelector('.root'))"
                )
                return {"moved": True}

            _raises(
                browser_worker.WorkerBootstrapError,
                lambda: browser_worker._focused_rerendering_scroll_audit(
                    page,
                    page.locator(".root"),
                    move_root,
                    timeout_ms=500,
                ),
            )
            state = page.evaluate(
                """
                () => ({
                  parent: document.querySelector('.root').parentElement.id,
                  x: window.scrollX,
                  y: window.scrollY
                })
                """
            )
            if state != {"parent": "b", "x": 0, "y": 0}:
                raise AssertionError(state)
        finally:
            browser.close()


def test_real_chromium_analytics_semantic_readiness_commits_once() -> None:
    from playwright.sync_api import sync_playwright
    from scripts import ui_ux_browser_worker as browser_worker

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "analytics-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "analytics-controls",
            "route": "/__selection__/analytics-db",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    legacy_html = """
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-adb_table{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [data-baseweb=button-group]{display:flex;gap:4px;width:350px;height:32px}
      [data-baseweb=button-group] button{display:block;width:170px;height:24px}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="analytics-controls/mobile"
         data-render-generation="1">analytics-controls</div>
    <div class="st-key-adb_table" data-testid="stElementContainer">
      <div data-baseweb="button-group" role="radiogroup" aria-label="button group">
        <button aria-label="" kind="segmented_controlActive">candidate_rankings</button>
        <button aria-label="" kind="segmented_control">iv_history</button>
      </div>
    </div>
    <script>
      const marker = document.querySelector('#ux1b-selection-ready');
      const buttons = Array.from(document.querySelectorAll('[role=radiogroup] button'));
      window.commitCounts = {candidate_rankings: 0, iv_history: 0};
      for (const button of buttons) {
        button.addEventListener('click', () => {
          const committed = button.innerText.trim();
          window.commitCounts[committed] += 1;
          marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 1
          );
          for (const candidate of buttons) {
            candidate.setAttribute(
              'kind',
              candidate === button ? 'segmented_controlActive' : 'segmented_control'
            );
          }
        });
      }
    </script>
    """
    selectbox_html = """
    <!doctype html>
    <style>
      html,body{margin:0;width:390px;overflow-x:hidden}
      .st-key-adb_table{position:absolute;left:20px;top:60px;width:350px;height:40px}
      [data-baseweb=select]{width:350px;height:32px}
      [data-baseweb=icon]{width:20px;height:20px}
      [role=combobox]{box-sizing:border-box;width:350px;height:32px;padding:4px}
      [data-testid=stSelectboxVirtualDropdown]{position:absolute;left:20px;top:96px;width:350px}
      [role=option]{box-sizing:border-box;width:350px;height:28px;padding:4px}
    </style>
    <div id="ux1b-selection-ready" data-capture-id="analytics-controls/mobile"
         data-render-generation="1">analytics-controls</div>
    <div class="st-key-adb_table">
      <div data-baseweb="select">
        <span data-selected>candidate_rankings</span>
        <input role="combobox" aria-label="Selected candidate_rankings. 資料表"
               aria-expanded="false" aria-haspopup="listbox"
               aria-autocomplete="list" tabindex="0" value="">
        <svg data-baseweb="icon" title="Clear value" viewBox="0 0 24 24"
             aria-label="Clear value" role="button"><title>Clear value</title><path></path></svg>
      </div>
    </div>
    <script>
      const labels = ['candidate_rankings', 'iv_history'];
      const combobox = document.querySelector('[role=combobox]');
      const selectedValue = document.querySelector('[data-selected]');
      const marker = document.querySelector('#ux1b-selection-ready');
      let selected = 0;
      let highlighted = 0;
      let open = false;
      let activePopover = null;
      window.commitCounts = {candidate_rankings: 0, iv_history: 0};
      function closeListbox() {
        activePopover?.remove();
        activePopover = null;
        combobox.setAttribute('aria-expanded', 'false');
        combobox.removeAttribute('aria-controls');
        combobox.removeAttribute('aria-activedescendant');
        open = false;
      }
      function renderListbox() {
        const wasOpen = open;
        activePopover?.remove();
        const popover = document.createElement('div');
        popover.setAttribute('data-baseweb', 'popover');
        const listbox = document.createElement('ul');
        listbox.setAttribute('data-testid', 'stSelectboxVirtualDropdown');
        for (let index = 0; index < labels.length; index += 1) {
          const option = document.createElement('li');
          option.id = `synthetic-option-${index}`;
          option.setAttribute('role', 'option');
          option.setAttribute('aria-disabled', 'false');
          option.setAttribute('aria-selected', String(index === highlighted));
          option.textContent = labels[index];
          listbox.appendChild(option);
        }
        popover.appendChild(listbox);
        document.body.appendChild(popover);
        activePopover = popover;
        combobox.setAttribute('aria-expanded', 'true');
        combobox.setAttribute('aria-controls', 'synthetic-table-list');
        if (wasOpen) {
          combobox.setAttribute(
            'aria-activedescendant', listbox.children[highlighted].id
          );
        } else {
          combobox.removeAttribute('aria-activedescendant');
        }
        open = true;
      }
      combobox.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          if (!open) highlighted = selected;
          else highlighted = (highlighted + 1) % labels.length;
          renderListbox();
        } else if (event.key === 'ArrowUp') {
          event.preventDefault();
          if (!open) highlighted = selected;
          else highlighted = (highlighted - 1 + labels.length) % labels.length;
          renderListbox();
        } else if (event.key === 'Escape' && open) {
          event.preventDefault();
          closeListbox();
        } else if (event.key === 'Enter' && open) {
          event.preventDefault();
          selected = highlighted;
          const committed = labels[selected];
          window.commitCounts[committed] += 1;
          closeListbox();
          selectedValue.textContent = committed;
          combobox.setAttribute(
            'aria-label', `Selected ${committed}. 資料表`
          );
          marker.dataset.renderGeneration = String(
            Number(marker.dataset.renderGeneration) + 1
          );
        }
      });
    </script>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for html, expected_projection, schedule_script in (
                (
                    legacy_html,
                    "legacy-segmented",
                    """
                    () => {
                      const marker = document.querySelector('#ux1b-selection-ready');
                      const generation = marker.dataset.renderGeneration;
                      const root = document.querySelector('.st-key-adb_table');
                      const key = `flicker${generation}`;
                      if (!['2', '3'].includes(generation) || root.dataset[key] === 'true') {
                        return false;
                      }
                      root.dataset[key] = 'true';
                      const buttons = Array.from(root.querySelectorAll('button'));
                      const committed = buttons.find(
                        button => button.getAttribute('kind') === 'segmented_controlActive'
                      ).innerText.trim();
                      setTimeout(() => {
                        for (const button of buttons) {
                          button.setAttribute('kind', 'segmented_control');
                        }
                        root.dataset.semanticStage = `${generation}-partial`;
                      }, 0);
                      setTimeout(() => {
                        for (const button of buttons) {
                          button.setAttribute(
                            'kind',
                            button.innerText.trim() === committed
                              ? 'segmented_controlActive'
                              : 'segmented_control'
                          );
                        }
                        root.dataset.semanticStage = `${generation}-stable`;
                      }, 120);
                      return true;
                    }
                    """,
                ),
                (
                    selectbox_html,
                    "accessible-required",
                    """
                    () => {
                      const marker = document.querySelector('#ux1b-selection-ready');
                      const generation = marker.dataset.renderGeneration;
                      const root = document.querySelector('.st-key-adb_table');
                      const key = `flicker${generation}`;
                      if (!['2', '3'].includes(generation) || root.dataset[key] === 'true') {
                        return false;
                      }
                      root.dataset[key] = 'true';
                      const selectedValue = root.querySelector('[data-selected]');
                      const committed = selectedValue.innerText.trim();
                      setTimeout(() => {
                        selectedValue.textContent = 'patching';
                        root.dataset.semanticStage = `${generation}-partial`;
                      }, 0);
                      setTimeout(() => {
                        selectedValue.textContent = committed;
                        root.dataset.semanticStage = `${generation}-stable`;
                      }, 120);
                      return true;
                    }
                    """,
                ),
            ):
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.set_content(html)
                mutation_page = _SemanticMutationPage(page, schedule_script)
                record = browser_worker._collect_focused_control_evidence(
                    mutation_page,
                    identity,
                    timeout_ms=(
                        2_500
                        if expected_projection == "accessible-required"
                        else 1_500
                    ),
                )
                state = page.evaluate(
                    """
                    () => ({
                      generation: document.querySelector('#ux1b-selection-ready')
                        .dataset.renderGeneration,
                      commits: window.commitCounts,
                      flickers: [
                        document.querySelector('.st-key-adb_table').dataset.flicker2,
                        document.querySelector('.st-key-adb_table').dataset.flicker3
                      ],
                      semanticStage: document.querySelector('.st-key-adb_table')
                        .dataset.semanticStage,
                      selected: (
                        document.querySelector('[kind=segmented_controlActive]') ||
                        document.querySelector('[data-selected]')
                      )?.innerText.trim()
                    })
                    """
                )
                if (
                    record["projection"] != expected_projection
                    or mutation_page.scheduled_count != 2
                    or state
                    != {
                        "generation": "3",
                        "commits": {"candidate_rankings": 1, "iv_history": 1},
                        "flickers": ["true", "true"],
                        "semanticStage": "3-stable",
                        "selected": "candidate_rankings",
                    }
                ):
                    raise AssertionError(
                        (record, mutation_page.scheduled_count, state)
                    )
                page.close()
        finally:
            browser.close()


def test_capture_stack_digest_is_descriptor_authenticated() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write(root / "stack/a.py", b"A = 1\n")
        _write(root / "stack/b.py", b"B = 2\n")
        digest = evidence.capture_stack_digest(
            ("stack/a.py", "stack/b.py"), root=root
        )
        reversed_digest = evidence.capture_stack_digest(
            ("stack/b.py", "stack/a.py"), root=root
        )
        if digest != reversed_digest or len(digest) != 64:
            raise AssertionError("capture-stack digest is not deterministic")

        (root / "leaf-link.py").symlink_to("stack/a.py")
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.capture_stack_digest(("leaf-link.py",), root=root),
        )
        (root / "alias").symlink_to("stack", target_is_directory=True)
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.capture_stack_digest(("alias/a.py",), root=root),
        )

        original_freeze = evidence.freeze_artifact_contract
        swapped = False

        def freeze_then_swap(
            root_fd: int,
            relative_path: str,
            **kwargs: object,
        ) -> object:
            nonlocal swapped
            contract = original_freeze(root_fd, relative_path, **kwargs)
            if relative_path == "stack/a.py" and not swapped:
                swapped = True
                (root / "stack").rename(root / "stack-old")
                (root / "stack").mkdir()
                _write(root / "stack/a.py", b"A = 1\n")
                _write(root / "stack/b.py", b"B = 2\n")
            return contract

        with mock.patch.object(
            evidence,
            "freeze_artifact_contract",
            side_effect=freeze_then_swap,
        ):
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.capture_stack_digest(("stack/a.py",), root=root),
            )

        root_alias = root.parent / f"{root.name}-alias"
        root_alias.symlink_to(root, target_is_directory=True)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.capture_stack_digest(
                    ("stack/a.py",), root=root_alias
                ),
            )
        finally:
            root_alias.unlink()


def test_browser_worker_focused_interaction_catalog_is_exact_and_dual_compatible() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    rows = browser_worker.worker_interaction_catalog_rows()
    expected_cases = {
        "risk-guard-controls": ("none", (".st-key-rg_source",)),
        "institutions-controls": (
            "select-institution-portfolio",
            (".st-key-inst_view",),
        ),
        "options-cockpit-controls": (
            "none",
            (".st-key-cockpit_price_view_NVDA",),
        ),
        "radar-controls": (
            "none",
            (".st-key-radar_source", ".st-key-radar_view"),
        ),
        "knowledge-graph-controls": (
            "none",
            (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
        ),
        "ai-chat-settings-controls": (
            "open-ai-chat-settings",
            (".st-key-ai_chat_mode",),
        ),
        "retro-controls": ("none", (".st-key-retro_validation_lane",)),
        "analytics-controls": ("none", (".st-key-adb_table",)),
        "stock-checkup-controls": ("none", (".st-key-checkup_mode",)),
    }
    expected_ids = {
        "risk-guard-controls": "ux1b-focused/risk-guard-controls/ready/v1",
        "institutions-controls": (
            "ux1b-focused/institutions-controls/select-portfolio/v1"
        ),
        "options-cockpit-controls": (
            "ux1b-focused/options-cockpit-controls/ready/v1"
        ),
        "radar-controls": "ux1b-focused/radar-controls/ready/v1",
        "knowledge-graph-controls": (
            "ux1b-focused/knowledge-graph-controls/ready/v1"
        ),
        "ai-chat-settings-controls": (
            "ux1b-focused/ai-chat-settings-controls/open-settings/v1"
        ),
        "retro-controls": "ux1b-focused/retro-controls/ready/v1",
        "analytics-controls": "ux1b-focused/analytics-controls/ready/v1",
        "stock-checkup-controls": (
            "ux1b-focused/stock-checkup-controls/ready/v1"
        ),
    }
    expected_states = {
        "institutions-controls": "機構持倉 · 機構 → 它持有什麼",
        "ai-chat-settings-controls": "快速問答",
    }
    if len(rows) != 9 or {row["case"] for row in rows} != set(expected_cases):
        raise AssertionError(rows)
    if len({row["interactionId"] for row in rows}) != len(rows):
        raise AssertionError("focused interaction IDs must be unique")
    if any(
        set(row)
        != {
            "schemaVersion",
            "case",
            "interactionId",
            "action",
            "rootSelectors",
            "selectedBusinessState",
        }
        or row["schemaVersion"]
        != "quant-radar-ui-ux-focused-interaction/v1"
        or (row["action"], tuple(row["rootSelectors"]))
        != expected_cases[row["case"]]
        or row["interactionId"] != expected_ids[row["case"]]
        or row["selectedBusinessState"] != expected_states.get(row["case"])
        for row in rows
    ):
        raise AssertionError(rows)
    all_roots = [selector for row in rows for selector in row["rootSelectors"]]
    if len(all_roots) != 11 or len(set(all_roots)) != 11:
        raise AssertionError(all_roots)

    class Locator:
        def __init__(
            self,
            page: "Page",
            kind: str,
            name: str,
            *,
            exact: bool = True,
        ) -> None:
            self.page = page
            self.kind = kind
            self.name = name
            self.exact = exact

        @property
        def first(self) -> "Locator":
            return self

        def count(self) -> int:
            if self.kind == "selector":
                if self.name == "#ux1b-selection-ready":
                    return 1
                return int(self.name in self.page.visible_selectors)
            if self.kind == "raw-radio-projection":
                if self.name == ".st-key-inst_view":
                    return 2 if self.page.institution_choice_role == "radio" else 0
                if self.name == ".st-key-ai_chat_mode":
                    return 2 if self.page.ai_choice_role == "radio" else 0
                raise AssertionError((self.kind, self.name))
            if self.kind == "raw-select-projection":
                return 0
            if self.kind == "text":
                return int(
                    self.name == "AI 對話" and self.page.ai_open
                    or self.name == "某機構 →" and self.page.institution_selected
                    or self.name == "設定與歷史" and self.page.ai_open
                    or self.name in ("快速問答", "深度研究")
                    and self.page.settings_open
                    or self.name == "機構持倉 · 機構 → 它持有什麼"
                    and ".st-key-inst_view" in self.page.visible_selectors
                )
            if self.kind == "label" and self.name in (
                "快速問答",
                "深度研究",
                "機構持倉 · 機構 → 它持有什麼",
            ):
                return int(
                    self.page.ai_choice_role == "radio" and self.page.settings_open
                    if self.name in ("快速問答", "深度研究")
                    else self.page.institution_choice_role == "radio"
                )
            if self.name == "AI":
                return int(self.kind == "button" and not self.page.ai_open)
            if self.name == "設定與歷史":
                return 0
            if self.name in ("快速問答", "深度研究"):
                return int(self.kind == self.page.ai_choice_role and self.page.settings_open)
            if self.name == "機構持倉 · 機構 → 它持有什麼":
                return int(self.kind == self.page.institution_choice_role)
            return 0

        def wait_for(self, *, state: str, timeout: int) -> None:
            allowed_state = (
                state == "visible" and self.is_visible()
                or state == "attached"
                and self.kind == "selector"
                and self.name == "#ux1b-selection-ready"
                and self.count() == 1
            )
            if not allowed_state or timeout != 30_000:
                raise AssertionError((self.kind, self.name, state, timeout, self.count()))

        def click(self, *, timeout: int, trial: bool = False) -> None:
            if timeout != 30_000 or self.count() != 1:
                raise AssertionError((self.kind, self.name, timeout, self.count()))
            if self.kind == "radio":
                raise AssertionError("hidden semantic radio must never be clicked")
            operation = "trial" if trial else "click"
            self.page.calls.append((operation, self.kind, self.name))
            if trial:
                return
            if self.name == "AI":
                self.page.ai_open = True
                self.page.selection_generation += 2
            elif self.name == "設定與歷史":
                self.page.settings_open = True
                self.page.visible_selectors.add(".st-key-ai_chat_mode")
            elif self.name == "快速問答":
                self.page.ai_selected_state = "快速問答"
                self.page.selection_generation += 1
            elif self.name == "深度研究":
                self.page.ai_selected_state = "深度研究"
                self.page.selection_generation += 1
            elif self.name == "機構持倉 · 機構 → 它持有什麼":
                self.page.institution_selected = True
                self.page.selection_generation += 1

        def get_by_role(self, role: str, *, name: str, exact: bool) -> "Locator":
            if not exact or self.kind != "selector":
                raise AssertionError((self.kind, role, name, exact))
            return Locator(self.page, role, name)

        def locator(self, selector: str) -> "Locator":
            if self.kind == "radio" and selector == "xpath=ancestor::label[1]":
                return Locator(self.page, "label", self.name)
            if self.kind == "selector" and selector == (
                'input[type="radio"], [role="radio"]'
            ):
                return Locator(
                    self.page,
                    "raw-radio-projection",
                    self.name,
                )
            if self.kind == "selector" and selector == (
                '[data-baseweb="select"], [role="combobox"]'
            ):
                return Locator(
                    self.page,
                    "raw-select-projection",
                    self.name,
                )
            raise AssertionError((self.kind, self.name, selector))

        def evaluate(self, _script: str, _argument: object = None) -> bool:
            if self.kind != "radio":
                raise AssertionError((self.kind, self.name))
            return True

        def bounding_box(self) -> dict[str, float] | None:
            if self.kind != "label" or self.count() != 1:
                return None
            return {"x": 0.0, "y": 0.0, "width": 90.0, "height": 24.0}

        def get_attribute(self, name: str) -> str | None:
            if (
                self.kind == "selector"
                and self.name == "#ux1b-selection-ready"
            ):
                if name == "data-capture-id":
                    return self.page.capture_id
                if name == "data-render-generation":
                    self.page.generation_reads += 1
                    return str(self.page.selection_generation)
            if name != "kind" or self.kind != "button":
                return None
            if self.name in ("快速問答", "深度研究"):
                return (
                    "segmented_controlActive"
                    if self.page.ai_selected_state == self.name
                    else "segmented_control"
                )
            if (
                self.name == "機構持倉 · 機構 → 它持有什麼"
                and self.page.institution_selected
            ):
                return "segmented_controlActive"
            return "segmented_control"

        def is_checked(self) -> bool:
            if self.kind != "radio":
                raise AssertionError("is_checked is radio-only")
            return (
                self.name in ("快速問答", "深度研究")
                and self.page.ai_selected_state == self.name
                or self.name == "機構持倉 · 機構 → 它持有什麼"
                and self.page.institution_selected
            )

        def is_visible(self) -> bool:
            if self.kind == "radio":
                return False
            return self.count() == 1

    class Page:
        def __init__(
            self,
            *,
            institution_role: str,
            ai_role: str,
            capture_id: str = "radar-controls/mobile",
            institution_selected: bool = False,
            ai_selected: bool = False,
        ) -> None:
            self.institution_choice_role = institution_role
            self.ai_choice_role = ai_role
            self.capture_id = capture_id
            self.ai_open = False
            self.settings_open = False
            self.institution_selected = institution_selected
            self.ai_selected_state = "快速問答" if ai_selected else None
            self.selection_generation = 1
            self.generation_reads = 0
            self.visible_selectors = {".st-key-inst_view"}
            self.calls: list[tuple[str, str, str]] = []

        def get_by_role(self, role: str, *, name: str, exact: bool) -> Locator:
            if not exact:
                raise AssertionError("worker role locators must be exact")
            return Locator(self, role, name)

        def get_by_text(self, text: str, *, exact: bool) -> Locator:
            return Locator(self, "text", text, exact=exact)

        def locator(self, selector: str) -> Locator:
            return Locator(self, "selector", selector)

        @staticmethod
        def wait_for_timeout(_timeout: int) -> None:
            return None

    for role in ("button", "radio"):
        institution_identity = evidence.validate_worker_capture_identity(
            {
                "requestId": "institutions-controls/mobile",
                "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
                "case": "institutions-controls",
                "route": "/__selection__/institutions",
                "viewport": {"name": "mobile", "width": 390, "height": 844},
            }
        )
        institution_page = Page(
            institution_role=role,
            ai_role=role,
            capture_id="institutions-controls/mobile",
        )
        institution_record = browser_worker._perform_capture_interaction(
            institution_page,
            institution_identity,
            timeout_ms=30_000,
        )
        if institution_record != {
            "schemaVersion": "quant-radar-ui-ux-focused-interaction/v1",
            "interactionId": (
                "ux1b-focused/institutions-controls/select-portfolio/v1"
            ),
            "action": "select-institution-portfolio",
            "completed": True,
            "selectedBusinessState": "機構持倉 · 機構 → 它持有什麼",
        }:
            raise AssertionError(institution_record)
        expected_institution_calls = (
            [("click", "button", "機構持倉 · 機構 → 它持有什麼")]
            if role == "button"
            else [
                ("trial", "label", "機構持倉 · 機構 → 它持有什麼"),
                ("click", "label", "機構持倉 · 機構 → 它持有什麼"),
            ]
        )
        if (
            institution_page.calls != expected_institution_calls
            or institution_page.selection_generation != 2
            or institution_page.generation_reads < 2
        ):
            raise AssertionError(
                (
                    institution_page.calls,
                    institution_page.selection_generation,
                    institution_page.generation_reads,
                )
            )

        ai_identity = evidence.validate_worker_capture_identity(
            {
                "requestId": "ai-chat-settings-controls/mobile",
                "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
                "case": "ai-chat-settings-controls",
                "route": "/__selection__/ai-chat-settings",
                "viewport": {"name": "mobile", "width": 390, "height": 844},
            }
        )
        ai_page = Page(
            institution_role=role,
            ai_role=role,
            capture_id="ai-chat-settings-controls/mobile",
        )
        ai_record = browser_worker._perform_capture_interaction(
            ai_page,
            ai_identity,
            timeout_ms=30_000,
        )
        if ai_record != {
            "schemaVersion": "quant-radar-ui-ux-focused-interaction/v1",
            "interactionId": (
                "ux1b-focused/ai-chat-settings-controls/open-settings/v1"
            ),
            "action": "open-ai-chat-settings",
            "completed": True,
            "selectedBusinessState": "快速問答",
        }:
            raise AssertionError(ai_record)
        expected_ai_choice_calls = (
            [("click", "button", "深度研究"), ("click", "button", "快速問答")]
            if role == "button"
            else [
                ("trial", "label", "深度研究"),
                ("click", "label", "深度研究"),
                ("trial", "label", "快速問答"),
                ("click", "label", "快速問答"),
            ]
        )
        expected_ai_calls = [
            ("click", "button", "AI"),
            ("click", "text", "設定與歷史"),
            *expected_ai_choice_calls,
        ]
        if (
            ai_page.calls != expected_ai_calls
            or ai_page.selection_generation != 5
            or ai_page.generation_reads < 5
        ):
            raise AssertionError(
                (ai_page.calls, ai_page.selection_generation, ai_page.generation_reads)
            )

        ai_already_selected = Page(
            institution_role=role,
            ai_role=role,
            capture_id="ai-chat-settings-controls/mobile",
            ai_selected=True,
        )
        preserved_ai_record = browser_worker._perform_capture_interaction(
            ai_already_selected,
            ai_identity,
            timeout_ms=30_000,
        )
        if (
            preserved_ai_record != ai_record
            or ai_already_selected.ai_selected_state != "快速問答"
            or ai_already_selected.calls != expected_ai_calls
            or ai_already_selected.selection_generation != 5
            or ai_already_selected.generation_reads < 5
        ):
            raise AssertionError(
                (
                    preserved_ai_record,
                    ai_already_selected.ai_selected_state,
                    ai_already_selected.calls,
                    ai_already_selected.selection_generation,
                    ai_already_selected.generation_reads,
                )
            )

        already_selected = Page(
            institution_role=role,
            ai_role=role,
            capture_id="institutions-controls/mobile",
            institution_selected=True,
        )
        preserved_record = browser_worker._perform_capture_interaction(
            already_selected,
            institution_identity,
            timeout_ms=30_000,
        )
        if (
            preserved_record != institution_record
            or already_selected.institution_selected is not True
            or already_selected.calls
        ):
            raise AssertionError(
                (preserved_record, already_selected.institution_selected, already_selected.calls)
            )

    malformed = evidence.validate_worker_capture_identity(
        {
            "requestId": "radar-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "radar-controls",
            "route": "/__selection__/radar",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    malformed["rootSelectors"] = (".st-key-radar_source",)
    _raises(
        browser_worker.WorkerBootstrapError,
        lambda: browser_worker._perform_capture_interaction(
            Page(institution_role="button", ai_role="button"),
            malformed,
            timeout_ms=30_000,
        ),
    )


def test_selection_completion_generation_is_exact_and_monotonic() -> None:
    from scripts import ui_ux_browser_worker as browser_worker
    from scripts import ui_ux_evidence as evidence

    identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "ai-chat-settings-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "ai-chat-settings-controls",
            "route": "/__selection__/ai-chat-settings",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )

    class Marker:
        def __init__(self, page: "Page") -> None:
            self.page = page

        def wait_for(self, *, state: str, timeout: int) -> None:
            if state != "attached" or timeout <= 0 or self.page.count != 1:
                raise browser_worker.WorkerBootstrapError("marker unavailable")

        def count(self) -> int:
            return self.page.count

        def get_attribute(self, name: str) -> str | None:
            if name == "data-capture-id":
                return self.page.capture_id
            if name == "data-render-generation":
                return self.page.generations[self.page.index]
            return None

    class Page:
        def __init__(
            self,
            generations: list[str],
            *,
            capture_id: str = "ai-chat-settings-controls/mobile",
            count: int = 1,
        ) -> None:
            self.generations = generations
            self.capture_id = capture_id
            self.count = count
            self.index = 0
            self.waits = 0

        def locator(self, selector: str) -> Marker:
            if selector != "#ux1b-selection-ready":
                raise AssertionError(selector)
            return Marker(self)

        def wait_for_timeout(self, timeout: int) -> None:
            if not 1 <= timeout <= 50:
                raise AssertionError(timeout)
            self.waits += 1
            if self.index + 1 < len(self.generations):
                self.index += 1

    assert browser_worker._selection_render_generation(
        Page(["7"]),
        identity,
        timeout_ms=30_000,
    ) == 7
    delayed = Page(["3", "3", "4"])
    assert browser_worker._wait_for_selection_render_after(
        delayed,
        identity,
        3,
        timeout_ms=30_000,
    ) == 4
    assert delayed.waits == 2

    rejected_pages = (
        Page(["1"], capture_id="analytics-controls/mobile"),
        Page(["1"], count=0),
        Page(["1"], count=2),
        *(Page([value]) for value in ("0", "01", "1000001", "", None)),
    )
    for page in rejected_pages:
        _raises(
            browser_worker.WorkerBootstrapError,
            lambda page=page: browser_worker._selection_render_generation(
                page,
                identity,
                timeout_ms=30_000,
            ),
        )

    regressed = Page(["3", "2"])
    _raises(
        browser_worker.WorkerBootstrapError,
        lambda: browser_worker._wait_for_selection_render_after(
            regressed,
            identity,
            3,
            timeout_ms=30_000,
        ),
    )
    stalled = Page(["3"])
    with mock.patch.object(browser_worker.time, "monotonic", side_effect=(0.0, 2.0)):
        _raises(
            browser_worker.WorkerBootstrapError,
            lambda: browser_worker._wait_for_selection_render_after(
                stalled,
                identity,
                3,
                timeout_ms=1_000,
            ),
        )


def test_browser_worker_streamlit_404_console_correlation_is_order_independent() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    origin = browser_worker._parse_exact_origin("http://127.0.0.1:8501")
    route = "/analytics-db"
    host_url = "http://127.0.0.1:8501/analytics-db/_stcore/host-config"
    health_url = "http://127.0.0.1:8501/analytics-db/_stcore/health"

    class Response:
        def __init__(
            self, url: str, status: object = 404, method: object = "GET"
        ) -> None:
            self.url = url
            self.status = status
            self.request = types.SimpleNamespace(method=method)

    class Console:
        type = "error"
        text = browser_worker._BENIGN_STREAMLIT_404_CONSOLE_TEXT

        def __init__(
            self,
            url: str,
            *,
            text: str | None = None,
            line: int = 0,
            column: int = 0,
            legacy_line: int | None = None,
            legacy_column: int | None = None,
        ) -> None:
            self.location = {
                "url": url,
                "line": line if legacy_line is None else legacy_line,
                "column": column if legacy_column is None else legacy_column,
                "lineNumber": line,
                "columnNumber": column,
            }
            if text is not None:
                self.text = text

    no_events = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    no_events.assert_complete()

    response_only = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    for url in (host_url, health_url):
        if not response_only.observe_response(Response(url)):
            raise AssertionError(f"exact response rejected: {url}")
    response_only.assert_complete()

    response_then_console = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    for url in (host_url, health_url):
        if not response_then_console.observe_response(Response(url)):
            raise AssertionError(f"exact response rejected: {url}")
        if not response_then_console.observe_console(Console(url)):
            raise AssertionError(f"exact console rejected: {url}")
    response_then_console.assert_complete()

    console_then_response = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    for url in (host_url, health_url):
        if not console_then_response.observe_console(Console(url)):
            raise AssertionError(f"exact console-first event rejected: {url}")
        if not console_then_response.observe_response(Response(url)):
            raise AssertionError(f"exact response-after-console rejected: {url}")
    console_then_response.assert_complete()

    interleaved = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    if not interleaved.observe_console(Console(host_url)):
        raise AssertionError("host-config console-first event rejected")
    if not interleaved.observe_response(Response(health_url)):
        raise AssertionError("health response rejected")
    if not interleaved.observe_console(Console(health_url)):
        raise AssertionError("health console rejected")
    if not interleaved.observe_response(Response(host_url)):
        raise AssertionError("host-config response rejected")
    interleaved.assert_complete()

    duplicate_response = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    if not duplicate_response.observe_response(Response(host_url)):
        raise AssertionError("first exact response rejected")
    if duplicate_response.observe_response(Response(host_url)):
        raise AssertionError("duplicate exact response was accepted")
    if not duplicate_response.observe_console(Console(host_url)):
        raise AssertionError("one-shot response could not be consumed")
    duplicate_response.assert_complete()

    duplicate_console = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    if not duplicate_console.observe_response(Response(host_url)):
        raise AssertionError("exact response rejected")
    if not duplicate_console.observe_console(Console(host_url)):
        raise AssertionError("exact console rejected")
    if duplicate_console.observe_console(Console(host_url)):
        raise AssertionError("duplicate exact console was accepted")
    duplicate_console.assert_complete()

    console_only = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    if not console_only.observe_console(Console(host_url)):
        raise AssertionError("exact console-first event rejected")
    _raises(browser_worker.WorkerBootstrapError, console_only.assert_complete)

    invalid_console_cases = (
        Console("http://127.0.0.1:8501/other/_stcore/host-config"),
        Console(host_url, text="Failed to load resource: 404"),
        Console(host_url, line=1),
        Console(host_url, column=1),
        Console(host_url, legacy_line=1),
        Console(host_url, legacy_column=1),
    )
    missing_alias = Console(host_url)
    missing_alias.location.pop("line")
    extra_location_key = Console(host_url)
    extra_location_key.location["source"] = "network"
    invalid_console_cases += (missing_alias, extra_location_key)
    for candidate in invalid_console_cases:
        tracker = browser_worker._BenignStreamlit404Correlation(
            origin=origin, route=route
        )
        if not tracker.observe_response(Response(host_url)):
            raise AssertionError("exact response rejected")
        if tracker.observe_console(candidate):
            raise AssertionError("wrong URL/text/location console was accepted")
        tracker.assert_complete()

    console_without_exact_response = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    if console_without_exact_response.observe_response(Response(host_url, status=500)):
        raise AssertionError("500 response was accepted as a benign probe")
    if not console_without_exact_response.observe_console(Console(host_url)):
        raise AssertionError("exact console-first event rejected")
    _raises(
        browser_worker.WorkerBootstrapError,
        console_without_exact_response.assert_complete,
    )

    unpaired = browser_worker._BenignStreamlit404Correlation(
        origin=origin, route=route
    )
    for invalid_status in (500, 404.5, "404", True, False):
        if unpaired.observe_response(Response(host_url, status=invalid_status)):
            raise AssertionError(f"non-exact 404 response was accepted: {invalid_status!r}")
    if unpaired.observe_response(Response(host_url, method="POST")):
        raise AssertionError("POST route probe response was accepted")
    if unpaired.observe_response(
        Response("http://127.0.0.1:8502/analytics-db/_stcore/host-config")
    ):
        raise AssertionError("wrong-origin response was accepted")
    for invalid_url in (
        "https://127.0.0.1:8501/analytics-db/_stcore/host-config",
        "http://user@127.0.0.1:8501/analytics-db/_stcore/host-config",
        "http://127.0.0.1:8501/other/_stcore/host-config",
        host_url + "?probe=1",
        host_url + "#probe",
    ):
        if unpaired.observe_response(Response(invalid_url)):
            raise AssertionError(f"non-exact probe URL was accepted: {invalid_url}")


def _worker_smoke_html(
    case: str,
    *,
    extra_root: bool = False,
    delayed_root_ms: int = 0,
) -> bytes:
    if case == "knowledge-graph":
        extra = (
            '<div class="st-key-ai_chat_mode">unexpected affected root</div>'
            if extra_root
            else ""
        )
        body = (
            '<h1>知識網路</h1>'
            '<div data-testid="stHorizontalBlock">'
            '<div class="st-key-kg_view_mode" role="radiogroup" aria-label="視圖">'
            '<button role="radio" aria-checked="true">星雲圖</button></div>'
            '<div class="st-key-kg_label_mode" role="radiogroup" aria-label="標籤">'
            '<button role="radio" aria-checked="true">核心</button></div>'
            f"</div>{extra}"
        )
    elif case == "stock-checkup":
        root_markup = (
            '<div data-testid="stElementContainer" class="st-key-checkup_mode" '
            'role="radiogroup" aria-label="模式"><button>單檔</button></div>'
        )
        body = '<h2>個股總覽</h2>'
        if delayed_root_ms:
            body += (
                "<script>setTimeout(() => document.querySelector('main')"
                f".insertAdjacentHTML('beforeend', {json.dumps(root_markup)}), "
                f"{delayed_root_ms});</script>"
            )
        else:
            body += root_markup
    else:  # pragma: no cover - helper has a closed local catalog.
        raise AssertionError(case)
    completion = (
        '<span id="ux1b-full-page-render-complete" style="display:none">'
        f"{case}/mobile</span>"
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "html,body{margin:0;min-height:100%;background:#111;color:#fff}"
        "main{padding:24px}[data-testid=stHorizontalBlock]{display:flex;gap:12px}"
        "[class*=st-key-]{padding:8px}</style></head><body>"
        f'<main data-testid="stMainBlockContainer">{body}{completion}</main>'
        "</body></html>"
    ).encode("utf-8")


def test_full_page_worker_waits_for_post_app_completion_marker() -> None:
    from scripts import ui_ux_browser_worker as browser_worker

    fixture_source = (ROOT / "scripts" / "ui_ux_fixture_app.py").read_text(
        encoding="utf-8"
    )
    marker_id = browser_worker.FULL_PAGE_COMPLETION_MARKER_ID
    if (
        marker_id not in fixture_source
        or fixture_source.index("runpy.run_path")
        >= fixture_source.index("st.markdown")
    ):
        raise AssertionError("full-page completion marker must follow the real app")

    class Marker:
        def __init__(self, text: str, count: int = 1) -> None:
            self.text = text
            self.total = count
            self.waits: list[tuple[str, int]] = []

        def wait_for(self, *, state: str, timeout: int) -> None:
            self.waits.append((state, timeout))

        def count(self) -> int:
            return self.total

        def inner_text(self) -> str:
            return self.text

    class Page:
        def __init__(self, marker: Marker) -> None:
            self.marker = marker
            self.selectors: list[str] = []

        def locator(self, selector: str) -> Marker:
            self.selectors.append(selector)
            return self.marker

    request = {
        "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
        "requestId": "stock-checkup/mobile",
    }
    page = Page(Marker("stock-checkup/mobile"))
    browser_worker._wait_for_full_page_completion(page, request, timeout_ms=1234)
    if page.selectors != [f"#{marker_id}"] or page.marker.waits != [
        ("attached", 1234)
    ]:
        raise AssertionError("full-page completion marker was not awaited exactly")

    selection_page = Page(Marker("unused"))
    browser_worker._wait_for_full_page_completion(
        selection_page,
        {
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "requestId": "stock-checkup-controls/mobile",
        },
        timeout_ms=1234,
    )
    if selection_page.selectors:
        raise AssertionError("focused fixture received the full-page-only gate")

    for marker in (Marker("wrong/mobile"), Marker("stock-checkup/mobile", count=2)):
        _raises(
            browser_worker.WorkerBootstrapError,
            lambda marker=marker: browser_worker._wait_for_full_page_completion(
                Page(marker), request, timeout_ms=1234
            ),
        )


def test_full_page_worker_waits_for_unique_catalog_roots() -> None:
    from scripts import ui_ux_browser_worker as browser_worker
    from scripts import ui_ux_evidence as evidence

    class Root:
        def __init__(self, count: int = 1) -> None:
            self.total = count
            self.waits: list[tuple[str, int]] = []

        @property
        def first(self) -> "Root":
            return self

        def wait_for(self, *, state: str, timeout: int) -> None:
            self.waits.append((state, timeout))

        def count(self) -> int:
            return self.total

    class Page:
        def __init__(self, roots: dict[str, Root]) -> None:
            self.roots = roots
            self.selectors: list[str] = []

        def locator(self, selector: str) -> Root:
            self.selectors.append(selector)
            return self.roots[selector]

    stock_identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "stock-checkup/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
            "case": "stock-checkup",
            "route": "/stock-checkup",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    stock_root = Root()
    stock_page = Page({".st-key-checkup_mode": stock_root})
    browser_worker._wait_for_full_page_catalog_roots(
        stock_page,
        stock_identity,
        timeout_ms=1234,
    )
    if stock_page.selectors != [".st-key-checkup_mode"] or stock_root.waits != [
        ("visible", 1234)
    ]:
        raise AssertionError("full-page catalog root was not awaited exactly")

    duplicate_page = Page({".st-key-checkup_mode": Root(count=2)})
    _raises(
        browser_worker.WorkerBootstrapError,
        lambda: browser_worker._wait_for_full_page_catalog_roots(
            duplicate_page,
            stock_identity,
            timeout_ms=1234,
        ),
    )
    absent_page = Page({".st-key-checkup_mode": Root(count=0)})
    _raises(
        browser_worker.WorkerBootstrapError,
        lambda: browser_worker._wait_for_full_page_catalog_roots(
            absent_page,
            stock_identity,
            timeout_ms=1234,
        ),
    )

    empty_identity = dict(stock_identity)
    empty_identity["rootSelectors"] = ()
    empty_page = Page({})
    browser_worker._wait_for_full_page_catalog_roots(
        empty_page,
        empty_identity,
        timeout_ms=1234,
    )
    if empty_page.selectors:
        raise AssertionError("empty full-page root catalog was not a no-op")

    focused_identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "ai-chat-settings-controls/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
            "case": "ai-chat-settings-controls",
            "route": "/__selection__/ai-chat-settings",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    focused_page = Page({})
    browser_worker._wait_for_full_page_catalog_roots(
        focused_page,
        focused_identity,
        timeout_ms=1234,
    )
    if focused_page.selectors:
        raise AssertionError("focused roots were awaited before their interaction")

    theme_identity = evidence.validate_worker_capture_identity(
        {
            "requestId": "theme-gallery/mobile",
            "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
            "case": "theme-gallery",
            "route": "/",
            "viewport": {"name": "mobile", "width": 390, "height": 844},
        }
    )
    theme_page = Page({})
    browser_worker._wait_for_full_page_catalog_roots(
        theme_page,
        theme_identity,
        timeout_ms=1234,
    )
    if theme_page.selectors:
        raise AssertionError("theme fixture received the production full-page root gate")

    unknown_identity = dict(theme_identity)
    unknown_identity["fixtureEntrypoint"] = "scripts/invented_fixture.py"
    _raises(
        browser_worker.WorkerBootstrapError,
        lambda: browser_worker._wait_for_full_page_catalog_roots(
            Page({}),
            unknown_identity,
            timeout_ms=1234,
        ),
    )


def _mode_0700(path: Path) -> Path:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


def test_real_mirror_chromium_worker_raw_stage_smoke() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except (ImportError, ModuleNotFoundError):
        print("  DEPENDENCY_UNAVAILABLE Playwright is not installed")
        return

    from scripts import ui_ux_browser_worker as browser_worker
    from scripts import ui_ux_isolation as isolation

    knowledge_request_base = {
        "requestId": "knowledge-graph/mobile",
        "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
        "case": "knowledge-graph",
        "route": "/knowledge-graph",
        "viewport": {"name": "mobile", "width": 390, "height": 844},
    }
    knowledge_identity = evidence.validate_worker_capture_identity(
        knowledge_request_base
    )
    affected = tuple(knowledge_identity["affectedRootSelectors"])
    all_root_markup = []
    for index, selector in enumerate(affected):
        all_root_markup.append(
            f'<div data-testid="stElementContainer" class="{selector[1:]}" '
            f'role="radiogroup" aria-label="root-{index}"><button>item-{index}</button></div>'
        )
    direct_html = (
        '<main data-testid="stMainBlockContainer">'
        '<div data-testid="stHorizontalBlock">'
        + "".join(all_root_markup[:4])
        + "</div>"
        + "".join(all_root_markup[4:])
        + '<div class="st-key-unrelated">unrelated</div></main>'
    )
    try:
        with sync_playwright() as playwright:
            browser_executable = playwright.chromium.executable_path
            if not Path(browser_executable).is_file():
                print("  DEPENDENCY_UNAVAILABLE Chromium executable is missing")
                return
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.set_content(direct_html)
                raw_nodes = page.evaluate(
                    browser_worker._DOM_PROJECTION_SCRIPT,
                    {
                        "rootSelectors": list(affected),
                        "affectedRootSelectors": list(affected),
                    },
                )
                nodes = browser_worker._project_nodes(
                    raw_nodes,
                    expected_root_selectors=affected,
                )
            finally:
                browser.close()
    except Exception as exc:
        if type(exc).__name__ in {"ExecutableDoesntExistError"}:
            print("  DEPENDENCY_UNAVAILABLE Chromium cannot launch")
            return
        raise
    roots = [node for node in nodes if node["rootSelector"] is not None]
    by_id = {node["id"]: node for node in nodes}
    if (
        len(roots) != 11
        or len({node["rootSelector"] for node in roots}) != 11
        or set(node["rootSelector"] for node in roots) != set(affected)
        or any(node["boundaryId"] not in by_id for node in roots)
        or any(
            by_id[node["boundaryId"]]["flowScope"] != node["flowScope"]
            for node in roots
        )
    ):
        raise AssertionError("all affected roots need unique resolvable boundaries")

    with tempfile.TemporaryDirectory(prefix="ux1b-worker-smoke-") as raw:
        base = Path(raw)
        mirror = isolation.build_source_mirror(
            workspace_root=ROOT,
            run_root=base / "mirror",
            policy=isolation.SourceMirrorPolicy(
                include=(
                    "scripts/ui_ux_browser_worker.py",
                    "scripts/ui_ux_evidence.py",
                    "scripts/ui_ux_isolation.py",
                    "scripts/ui_ux_fixture_app.py",
                ),
                exclude=(),
            ),
        )
        browser_root = _mode_0700(base / "browser")
        browser_home = _mode_0700(browser_root / "home")
        rejected_root = _mode_0700(base / "rejected-browser")
        rejected_home = _mode_0700(rejected_root / "home")
        pages = {
            "/knowledge-graph": _worker_smoke_html("knowledge-graph"),
            "/stock-checkup": _worker_smoke_html(
                "stock-checkup", delayed_root_ms=750
            ),
        }

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib callback name.
                body = pages.get(urllib.parse.urlsplit(self.path).path)
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"

        requests = (
            {
                "schemaVersion": WORKER_REQUEST_SCHEMA,
                **knowledge_request_base,
                "appOrigin": origin,
                "staging": {
                    "png": "captures/knowledge-graph/mobile.png",
                    "renderSidecar": "captures/knowledge-graph/mobile.render.json",
                },
            },
            {
                "schemaVersion": WORKER_REQUEST_SCHEMA,
                "requestId": "stock-checkup/mobile",
                "fixtureEntrypoint": "scripts/ui_ux_fixture_app.py",
                "case": "stock-checkup",
                "route": "/stock-checkup",
                "viewport": {"name": "mobile", "width": 390, "height": 844},
                "appOrigin": origin,
                "staging": {
                    "png": "captures/stock-checkup/mobile.png",
                    "renderSidecar": "captures/stock-checkup/mobile.render.json",
                },
            },
        )

        def run_worker(request: dict, home: Path):
            staging_paths = tuple(request["staging"].values())
            command = evidence.build_browser_worker_command(
                sys.executable,
                "scripts/ui_ux_browser_worker.py",
                expected_origin=origin,
                expected_request_id=request["requestId"],
                allowed_staging_paths=staging_paths,
                browser_executable=browser_executable,
                timeout_ms=30_000,
            )
            environment = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "TZ": "UTC",
                "SOURCE_ROOT": str(mirror.source_root),
                "HOME": str(home),
                "QUANT_RADAR_UX1B_ROLE": "browser",
                "VIRTUAL_ENV": str(ROOT / ".venv"),
            }
            completed = subprocess.run(
                command,
                cwd=mirror.source_root,
                env=environment,
                input=_json_line(request),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            response = evidence.decode_worker_response(
                completed.stdout,
                expected_request_id=request["requestId"],
                allowed_artifact_paths=set(staging_paths),
            )
            return completed, response

        completed_rows = []
        try:
            for request in requests:
                completed, response = run_worker(request, browser_home)
                if (
                    completed.returncode != 0
                    or completed.stderr != b""
                    or response["status"] != "staged"
                ):
                    raise AssertionError(
                        (completed.returncode, completed.stderr, response)
                    )
                completed_rows.append((completed, response))

            pages["/knowledge-graph"] = _worker_smoke_html(
                "knowledge-graph", extra_root=True
            )
            rejected_request = copy.deepcopy(requests[0])
            rejected_request["staging"] = {
                "png": "rejected/knowledge-graph.png",
                "renderSidecar": "rejected/knowledge-graph.render.json",
            }
            rejected, rejected_response = run_worker(rejected_request, rejected_home)
            if (
                rejected.returncode != 65
                or rejected.stderr != b""
                or rejected_response["status"] != "invalid_data"
                or any(
                    (rejected_root / path).exists()
                    for path in rejected_request["staging"].values()
                )
            ):
                raise AssertionError(
                    (rejected.returncode, rejected.stderr, rejected_response)
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
        if server_thread.is_alive():
            raise AssertionError("smoke app server did not quiesce")

        browser_fd = _root_fd(browser_root)
        try:
            identities = {
                request["requestId"]: evidence.validate_worker_capture_identity(
                    request
                )
                for request in requests
            }
            raw_sidecars = {
                request["requestId"]: evidence.authenticate_raw_render_sidecar(
                    browser_fd,
                    request["staging"]["renderSidecar"],
                    expected_owner=OWNER,
                    identity_row=identities[request["requestId"]],
                )
                for request in requests
            }
        finally:
            os.close(browser_fd)

        for request in requests:
            capture_id = request["requestId"]
            identity = identities[capture_id]
            authenticated = raw_sidecars[capture_id]
            if not isinstance(
                authenticated, evidence.AuthenticatedRawRenderSidecar
            ):
                raise AssertionError(type(authenticated).__name__)

            raw_bytes = (
                browser_root / request["staging"]["renderSidecar"]
            ).read_bytes()
            raw_document = json.loads(raw_bytes)
            png = (browser_root / request["staging"]["png"]).read_bytes()
            if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
                raise AssertionError("worker did not stage a PNG")
            width, height = struct.unpack(">II", png[16:24])
            roots = [
                node
                for node in raw_document["nodes"]
                if node["rootSelector"] is not None
            ]
            by_id = {node["id"]: node for node in raw_document["nodes"]}
            if (
                authenticated["document"] != raw_document
                or raw_document["identity"]
                != {
                    "case": identity["case"],
                    "route": identity["route"],
                    "callable": identity["callable"],
                }
                or raw_document["viewport"] != identity["viewport"]
                or raw_document["readiness"]
                != {"ready": True, "marker": identity["readiness"]["text"]}
                or raw_document["providerCounters"] != {}
                or raw_document["mutatorCounters"] != {}
                or "counterProvenance" in raw_document
                or width != 390
                or height < 844
                or len(roots) != len(identity["rootSelectors"])
                or len({node["rootSelector"] for node in roots}) != len(roots)
                or set(node["rootSelector"] for node in roots)
                != set(identity["rootSelectors"])
                or any(node["boundaryId"] not in by_id for node in roots)
                or any(node["id"] == node["boundaryId"] for node in roots)
                or any(
                    by_id[node["boundaryId"]]["flowScope"] != node["flowScope"]
                    for node in roots
                )
            ):
                raise AssertionError(raw_document)
        if any(completed.stderr for completed, _response in completed_rows):
            raise AssertionError("worker emitted stderr during the raw-stage smoke")


def test_theme_worker_rich_raw_sidecar_auth_is_exact_and_mutation_closed() -> None:
    from scripts.test_ui_ux_theme_matrix import _rich_theme_worker_fixture

    fixture = _rich_theme_worker_fixture()
    request = fixture["request"]
    identity = evidence.validate_worker_capture_identity(request)
    if evidence.THEME_WORKER_EVIDENCE_SCHEMA != fixture["sidecar"]["stableState"][
        "themeEvidence"
    ]["schemaVersion"]:
        raise AssertionError("theme evidence schema constants diverged")

    def refresh_digest(sidecar: dict) -> None:
        theme = sidecar["stableState"]["themeEvidence"]
        theme["sha256"] = hashlib.sha256(
            json.dumps(
                {key: value for key, value in theme.items() if key != "sha256"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    mutations: list[tuple[str, Callable[[dict], None]]] = [
        (
            "digest",
            lambda sidecar: sidecar["stableState"]["themeEvidence"].__setitem__(
                "sha256", "0" * 64
            ),
        ),
        (
            "crop",
            lambda sidecar: sidecar["stableState"]["themeEvidence"]["surfaces"][
                1
            ]["geometry"]["crop"].__setitem__("y", 0),
        ),
        (
            "semantics",
            lambda sidecar: sidecar["stableState"]["themeEvidence"]["surfaces"][
                0
            ]["states"]["selectedControls"]["radio_horizontal"]["semantics"].__setitem__(
                "checkedLabels", ["其他項"]
            ),
        ),
        (
            "focus",
            lambda sidecar: sidecar["stableState"]["themeEvidence"]["surfaces"][
                0
            ]["states"]["focus"]["primary"]["samples"]["top"].__setitem__(
                "ring", [0, 0, 0]
            ),
        ),
    ]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        valid_raw = evidence.canonicalize_worker_render_sidecar(
            fixture["sidecar"], owned_roots=()
        )
        _write(root / "theme-valid.render.json", valid_raw)
        root_fd = _root_fd(root)
        try:
            authenticated = evidence.authenticate_raw_render_sidecar(
                root_fd,
                "theme-valid.render.json",
                expected_owner=OWNER,
                identity_row=identity,
            )
        finally:
            os.close(root_fd)
        if authenticated["document"] != fixture["sidecar"]:
            raise AssertionError("authenticated theme sidecar differs")

        for name, mutate in mutations:
            candidate = copy.deepcopy(fixture["sidecar"])
            mutate(candidate)
            if name != "digest":
                refresh_digest(candidate)
            raw = evidence.canonicalize_worker_render_sidecar(
                candidate, owned_roots=()
            )
            relative = f"theme-{name}.render.json"
            _write(root / relative, raw)
            root_fd = _root_fd(root)
            try:
                _raises(
                    evidence.EvidenceContractError,
                    lambda relative=relative: evidence.authenticate_raw_render_sidecar(
                        root_fd,
                        relative,
                        expected_owner=OWNER,
                        identity_row=identity,
                    ),
                )
            finally:
                os.close(root_fd)

        non_theme_request = _valid_worker_request()
        non_theme_identity = evidence.validate_worker_capture_identity(
            non_theme_request
        )
        injected = _discovery_raw_sidecar(non_theme_identity)
        injected["stableState"]["themeEvidence"] = copy.deepcopy(
            fixture["sidecar"]["stableState"]["themeEvidence"]
        )
        injected_raw = evidence.canonicalize_worker_render_sidecar(
            injected,
            owned_roots=(
                "/private/tmp/ux1b-discovery-source",
                "/private/tmp/ux1b-discovery-browser",
            ),
        )
        _write(root / "non-theme-injected.render.json", injected_raw)
        root_fd = _root_fd(root)
        try:
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_raw_render_sidecar(
                    root_fd,
                    "non-theme-injected.render.json",
                    expected_owner=OWNER,
                    identity_row=non_theme_identity,
                ),
            )
        finally:
            os.close(root_fd)


def _new_capture_stack_contract(root: Path) -> dict:
    stack_paths = evidence.CAPTURE_STACK_MEMBERS
    for index, relative in enumerate(stack_paths):
        _write(
            root / relative,
            f"capture_stack_member = {index}\n".encode("utf-8"),
        )

    return _capture_stack_contract_for_live_root(root)


def _capture_stack_contract_for_live_root(root: Path) -> dict:
    stack_paths = evidence.CAPTURE_STACK_MEMBERS
    base_digest = evidence.capture_stack_digest(stack_paths, root=root.resolve())
    catalog = _complete_control_catalog()
    catalog["baseCaptureStackDigest"] = base_digest
    catalog["captureStackDigest"] = evidence.control_catalog_digest(catalog)
    authenticated_catalog = evidence._mint_control_catalog(catalog)
    return evidence.build_capture_stack_contract(
        stack_paths,
        root=root.resolve(),
        control_catalog=authenticated_catalog,
    )


def _private_test_leaf(path: Path, raw: bytes) -> Path:
    _write(path, raw)
    path.chmod(0o600)
    return path


def _leaf_snapshot(path: Path) -> tuple[tuple[int, ...], tuple[str, object]]:
    observed = os.lstat(path)
    identity = (
        observed.st_dev,
        observed.st_ino,
        observed.st_uid,
        stat.S_IMODE(observed.st_mode),
        observed.st_nlink,
        observed.st_size,
    )
    payload: tuple[str, object]
    if stat.S_ISLNK(observed.st_mode):
        payload = ("symlink", os.readlink(path))
    else:
        payload = ("bytes", path.read_bytes())
    return identity, payload


class _CaptureStackRotationFixture:
    canonical_name = "capture-stack.json"

    def __enter__(self) -> _CaptureStackRotationFixture:
        self._temp = tempfile.TemporaryDirectory(prefix="ux1b-rotation-test-")
        self.root = Path(self._temp.name)
        self.canonical_dir = self.root / "canonical"
        self.archive_dir = self.root / "archive"
        self.canonical_dir.mkdir(mode=0o700)
        self.archive_dir.mkdir(mode=0o700)
        self.workspace_fd = _root_fd(self.root)
        self.canonical_fd = _root_fd(self.canonical_dir)
        self.archive_fd = _root_fd(self.archive_dir)
        try:
            self.old_document = _new_capture_stack_contract(self.root)
            self.old_raw = evidence._canonical_json_bytes(self.old_document)
            self.old_sha256 = _sha256(self.old_raw)
            evidence.publish_capture_stack_contract(
                self.canonical_fd,
                self.canonical_name,
                self.old_document,
                workspace_root_fd=self.workspace_fd,
            )
            self.expected_existing_contract = evidence.freeze_artifact_contract(
                self.canonical_fd,
                self.canonical_name,
                expected_owner=OWNER,
                max_bytes=evidence.MAX_CONTROL_CATALOG_BYTES,
            )
            if self.expected_existing_contract.leaf.sha256 != self.old_sha256:
                raise AssertionError("frozen old capture-stack digest differs")

            changed = self.root / evidence.CAPTURE_STACK_MEMBERS[0]
            changed.write_bytes(changed.read_bytes() + b"rotation = True\n")
            self.new_document = _capture_stack_contract_for_live_root(self.root)
            self.new_raw = evidence._canonical_json_bytes(self.new_document)
            self.new_sha256 = _sha256(self.new_raw)
            if self.new_sha256 == self.old_sha256:
                raise AssertionError("rotation fixture did not change contract bytes")
            self.archive_name = (
                f"superseded-capture-stack-{self.old_sha256}.json"
            )
            self.archive_path = self.archive_dir / self.archive_name
            self.canonical_path = self.canonical_dir / self.canonical_name
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        for descriptor_name in ("archive_fd", "canonical_fd", "workspace_fd"):
            descriptor = getattr(self, descriptor_name, -1)
            if descriptor >= 0:
                os.close(descriptor)
                setattr(self, descriptor_name, -1)
        self._temp.cleanup()

    def rotate(
        self,
        *,
        expected_existing_contract: object | None = None,
        expected_existing_sha256: str | None = None,
    ) -> dict[str, object]:
        return evidence.rotate_capture_stack_contract(
            self.canonical_fd,
            self.canonical_name,
            self.new_document,
            expected_existing_contract=(
                self.expected_existing_contract
                if expected_existing_contract is None
                else expected_existing_contract
            ),
            expected_existing_sha256=(
                self.old_sha256
                if expected_existing_sha256 is None
                else expected_existing_sha256
            ),
            archive_dir_fd=self.archive_fd,
            archive_name=self.archive_name,
            workspace_root_fd=self.workspace_fd,
        )


def _rotation_temporary_paths(
    fixture: _CaptureStackRotationFixture,
) -> tuple[Path, ...]:
    return tuple(
        path
        for directory in (fixture.canonical_dir, fixture.archive_dir)
        for path in directory.iterdir()
        if path.name.startswith(".") or path.name.endswith(".tmp")
    )


def _expected_rotation_receipt(
    fixture: _CaptureStackRotationFixture,
) -> dict[str, object]:
    return {
        "path": fixture.canonical_name,
        "sha256": fixture.new_sha256,
        "size": len(fixture.new_raw),
        "captureStackDigest": fixture.new_document["captureStackDigest"],
        "previousSha256": fixture.old_sha256,
        "archiveName": fixture.archive_name,
        "archiveSha256": fixture.old_sha256,
        "archiveSize": len(fixture.old_raw),
    }


def _assert_complete_rotation(
    fixture: _CaptureStackRotationFixture,
    receipt: Mapping[str, object] | None,
) -> None:
    if receipt is not None and dict(receipt) != _expected_rotation_receipt(fixture):
        raise AssertionError(receipt)
    authenticated, _catalog, sha256 = evidence.authenticate_capture_stack_contract(
        fixture.canonical_fd,
        fixture.canonical_name,
        workspace_root_fd=fixture.workspace_fd,
        expected_owner=OWNER,
        expected_sha256=fixture.new_sha256,
    )
    if authenticated != fixture.new_document or sha256 != fixture.new_sha256:
        raise AssertionError("rotated canonical contract did not reopen exactly")

    archive_contract = evidence.freeze_artifact_contract(
        fixture.archive_fd,
        fixture.archive_name,
        expected_owner=OWNER,
        max_bytes=evidence.MAX_CONTROL_CATALOG_BYTES,
    )
    with evidence.open_authenticated_artifact(
        fixture.archive_fd, archive_contract
    ) as artifact:
        archive_raw, archive_sha256, _observed = evidence._hash_descriptor(
            artifact.descriptor,
            maximum=evidence.MAX_CONTROL_CATALOG_BYTES,
        )
    if (
        archive_raw != fixture.old_raw
        or archive_sha256 != fixture.old_sha256
        or archive_contract.leaf.mode != 0o600
        or archive_contract.leaf.link_count != 1
        or archive_contract.leaf.inode
        == fixture.expected_existing_contract.leaf.inode
    ):
        raise AssertionError("old capture-stack archive is not an exact byte copy")

    canonical_observed = os.stat(
        fixture.canonical_name,
        dir_fd=fixture.canonical_fd,
        follow_symlinks=False,
    )
    if (
        not stat.S_ISREG(canonical_observed.st_mode)
        or canonical_observed.st_nlink != 1
        or canonical_observed.st_ino
        == fixture.expected_existing_contract.leaf.inode
        or fixture.canonical_path.read_bytes() != fixture.new_raw
    ):
        raise AssertionError("rotated canonical identity or bytes differ")
    temporary_paths = _rotation_temporary_paths(fixture)
    if temporary_paths:
        raise AssertionError(f"rotation leaked temporary paths: {temporary_paths}")


def test_capture_stack_rotation_archives_old_and_reopens_new_exactly() -> None:
    with _CaptureStackRotationFixture() as fixture:
        old_inode = fixture.expected_existing_contract.leaf.inode
        receipt = fixture.rotate()

        if old_inode == os.lstat(fixture.archive_path).st_ino:
            raise AssertionError("rotation hard-linked the old canonical into archive")
        _assert_complete_rotation(fixture, receipt)


def test_capture_stack_rotation_rejects_stale_authority_before_writes() -> None:
    for mutation in ("wrong-sha", "same-bytes-different-inode"):
        with _CaptureStackRotationFixture() as fixture:
            expected_sha256 = fixture.old_sha256
            if mutation == "wrong-sha":
                expected_sha256 = "0" * 64
            else:
                replacement = fixture.canonical_dir / ".same-bytes-replacement"
                _private_test_leaf(replacement, fixture.old_raw)
                os.replace(replacement, fixture.canonical_path)
                if (
                    os.lstat(fixture.canonical_path).st_ino
                    == fixture.expected_existing_contract.leaf.inode
                ):
                    raise AssertionError("test failed to install a different inode")
            canonical_before = _leaf_snapshot(fixture.canonical_path)

            with (
                mock.patch.object(evidence, "_write_all", wraps=evidence._write_all) as write_spy,
                mock.patch.object(evidence.os, "replace", wraps=os.replace) as replace_spy,
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda: fixture.rotate(
                        expected_existing_sha256=expected_sha256,
                    ),
                )

            if write_spy.call_count != 0 or replace_spy.call_count != 0:
                raise AssertionError(
                    f"{mutation} reached archive/temp publication: "
                    f"writes={write_spy.call_count}, replaces={replace_spy.call_count}"
                )
            if _leaf_snapshot(fixture.canonical_path) != canonical_before:
                raise AssertionError(f"{mutation} changed the visible canonical leaf")
            if os.path.lexists(fixture.archive_path):
                raise AssertionError(f"{mutation} created an archive")
            if _rotation_temporary_paths(fixture):
                raise AssertionError(f"{mutation} leaked a temporary leaf")


def test_capture_stack_rotation_reuses_only_exact_archive() -> None:
    with _CaptureStackRotationFixture() as fixture:
        _private_test_leaf(fixture.archive_path, fixture.old_raw)
        archive_before = _leaf_snapshot(fixture.archive_path)
        receipt = fixture.rotate()
        if _leaf_snapshot(fixture.archive_path) != archive_before:
            raise AssertionError("exact preexisting archive was replaced")
        _assert_complete_rotation(fixture, receipt)

    for mutation in ("wrong-bytes", "symlink", "multiple-links"):
        with _CaptureStackRotationFixture() as fixture:
            if mutation == "wrong-bytes":
                _private_test_leaf(fixture.archive_path, b"wrong archive bytes")
            elif mutation == "symlink":
                target = _private_test_leaf(
                    fixture.archive_dir / "archive-target.json",
                    fixture.old_raw,
                )
                os.symlink(target.name, fixture.archive_path)
            else:
                _private_test_leaf(fixture.archive_path, fixture.old_raw)
                os.link(
                    fixture.archive_path,
                    fixture.archive_dir / "archive-second-link.json",
                )
            canonical_before = _leaf_snapshot(fixture.canonical_path)
            archive_before = _leaf_snapshot(fixture.archive_path)

            with mock.patch.object(
                evidence.os, "replace", wraps=os.replace
            ) as replace_spy:
                _raises(evidence.EvidenceContractError, fixture.rotate)

            if replace_spy.call_count != 0:
                raise AssertionError(f"{mutation} archive reached canonical replace")
            if _leaf_snapshot(fixture.canonical_path) != canonical_before:
                raise AssertionError(f"{mutation} archive changed canonical bytes")
            if _leaf_snapshot(fixture.archive_path) != archive_before:
                raise AssertionError(f"{mutation} archive was rewritten")
            if _rotation_temporary_paths(fixture):
                raise AssertionError(f"{mutation} archive leaked a temporary leaf")


def test_capture_stack_rotation_reuse_reconfirms_archive_directory_durability() -> None:
    with _CaptureStackRotationFixture() as fixture:
        original_fsync = evidence.os.fsync
        archive_identity = os.fstat(fixture.archive_fd)
        archive_fsync_attempts = 0

        def fail_archive_directory_fsync(descriptor: int) -> None:
            nonlocal archive_fsync_attempts
            observed = os.fstat(descriptor)
            if (
                stat.S_ISDIR(observed.st_mode)
                and (observed.st_dev, observed.st_ino)
                == (archive_identity.st_dev, archive_identity.st_ino)
            ):
                archive_fsync_attempts += 1
                raise OSError(5, "injected archive directory fsync failure")
            original_fsync(descriptor)

        canonical_before = _leaf_snapshot(fixture.canonical_path)
        with mock.patch.object(
            evidence.os,
            "fsync",
            side_effect=fail_archive_directory_fsync,
        ):
            _raises(evidence.EvidenceContractError, fixture.rotate)
            if not os.path.lexists(fixture.archive_path):
                raise AssertionError("first archive durability fault exposed no archive")
            _raises(evidence.EvidenceContractError, fixture.rotate)

        if archive_fsync_attempts != 2:
            raise AssertionError(
                "archive reuse did not retry directory durability: "
                f"{archive_fsync_attempts} attempts"
            )
        if _leaf_snapshot(fixture.canonical_path) != canonical_before:
            raise AssertionError("archive durability retry replaced the canonical leaf")
        if _rotation_temporary_paths(fixture):
            raise AssertionError("archive durability retry leaked a temporary leaf")


def _precommit_rotation_fault(
    fixture: _CaptureStackRotationFixture,
    fault: str,
) -> object:
    if fault in {"archive-write", "new-write"}:
        return mock.patch.object(
            evidence,
            "_write_all",
            side_effect=OSError(5, f"injected {fault} failure"),
        )
    if fault in {"archive-file-fsync", "new-file-fsync"}:
        original_fsync = evidence.os.fsync

        def fail_regular_file_fsync(descriptor: int) -> None:
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError(5, f"injected {fault} failure")
            original_fsync(descriptor)

        return mock.patch.object(
            evidence.os,
            "fsync",
            side_effect=fail_regular_file_fsync,
        )
    if fault == "archive-link":
        return mock.patch.object(
            evidence.os,
            "link",
            side_effect=OSError(5, "injected archive link failure"),
        )
    if fault == "archive-directory-fsync":
        original_fsync = evidence.os.fsync
        archive_identity = os.fstat(fixture.archive_fd)

        def fail_archive_directory_fsync(descriptor: int) -> None:
            observed = os.fstat(descriptor)
            if (
                stat.S_ISDIR(observed.st_mode)
                and (observed.st_dev, observed.st_ino)
                == (archive_identity.st_dev, archive_identity.st_ino)
            ):
                raise OSError(5, "injected archive directory fsync failure")
            original_fsync(descriptor)

        return mock.patch.object(
            evidence.os,
            "fsync",
            side_effect=fail_archive_directory_fsync,
        )
    if fault == "precommit-revalidate":
        original_validate = evidence.validate_capture_stack_contract
        calls = 0

        def fail_second_validation(*args: object, **kwargs: object) -> dict:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise evidence.EvidenceContractError(
                    "injected precommit revalidation failure"
                )
            return original_validate(*args, **kwargs)

        return mock.patch.object(
            evidence,
            "validate_capture_stack_contract",
            side_effect=fail_second_validation,
        )
    if fault == "canonical-path-reauth":
        original_open_leaf = evidence._open_leaf_at
        canonical_opens = 0

        def fail_second_canonical_open(directory_fd: int, name: str) -> int:
            nonlocal canonical_opens
            if name == fixture.canonical_name:
                canonical_opens += 1
                if canonical_opens == 2:
                    raise evidence.EvidenceContractError(
                        "injected canonical path reauthentication failure"
                    )
            return original_open_leaf(directory_fd, name)

        return mock.patch.object(
            evidence,
            "_open_leaf_at",
            side_effect=fail_second_canonical_open,
        )
    if fault == "replace":
        return mock.patch.object(
            evidence.os,
            "replace",
            side_effect=OSError(5, "injected canonical replace failure"),
        )
    raise AssertionError(f"unknown rotation fault: {fault}")


def test_capture_stack_rotation_precommit_faults_preserve_old_canonical() -> None:
    fault_names = (
        "archive-write",
        "archive-file-fsync",
        "archive-link",
        "archive-directory-fsync",
        "new-write",
        "new-file-fsync",
        "precommit-revalidate",
        "canonical-path-reauth",
        "replace",
    )
    faults_with_existing_archive = frozenset(
        {
            "new-write",
            "new-file-fsync",
            "precommit-revalidate",
            "canonical-path-reauth",
            "replace",
        }
    )
    for fault in fault_names:
        with _CaptureStackRotationFixture() as fixture:
            if fault in faults_with_existing_archive:
                _private_test_leaf(fixture.archive_path, fixture.old_raw)
            canonical_before = _leaf_snapshot(fixture.canonical_path)
            injected = _precommit_rotation_fault(fixture, fault)

            with injected:
                _raises(evidence.EvidenceContractError, fixture.rotate)

            if _leaf_snapshot(fixture.canonical_path) != canonical_before:
                raise AssertionError(f"{fault} changed old canonical identity/bytes")
            if os.path.lexists(fixture.archive_path):
                archive = _leaf_snapshot(fixture.archive_path)
                if archive[1] != ("bytes", fixture.old_raw):
                    raise AssertionError(f"{fault} exposed a non-exact old archive")
            temporary_paths = _rotation_temporary_paths(fixture)
            if temporary_paths:
                raise AssertionError(f"{fault} leaked temporary paths: {temporary_paths}")


def test_capture_stack_rotation_postreplace_faults_are_uncertain() -> None:
    with _CaptureStackRotationFixture() as fixture:
        original_replace = evidence.os.replace
        committed = False

        def replace_then_raise(*args: object, **kwargs: object) -> None:
            nonlocal committed
            original_replace(*args, **kwargs)
            committed = True
            raise OSError(5, "injected ambiguous canonical replace failure")

        with mock.patch.object(
            evidence.os,
            "replace",
            side_effect=replace_then_raise,
        ):
            _raises(evidence.ManifestDurabilityUncertain, fixture.rotate)
        if not committed:
            raise AssertionError("ambiguous replace fault fired before commit")
        _assert_complete_rotation(fixture, None)

    with _CaptureStackRotationFixture() as fixture:
        original_fsync = evidence.os.fsync
        canonical_identity = os.fstat(fixture.canonical_fd)

        def fail_canonical_directory_fsync(descriptor: int) -> None:
            observed = os.fstat(descriptor)
            if (
                stat.S_ISDIR(observed.st_mode)
                and (observed.st_dev, observed.st_ino)
                == (canonical_identity.st_dev, canonical_identity.st_ino)
            ):
                raise OSError(5, "injected canonical directory fsync failure")
            original_fsync(descriptor)

        with mock.patch.object(
            evidence.os,
            "fsync",
            side_effect=fail_canonical_directory_fsync,
        ):
            _raises(evidence.ManifestDurabilityUncertain, fixture.rotate)
        _assert_complete_rotation(fixture, None)

    with _CaptureStackRotationFixture() as fixture:
        original_replace = evidence.os.replace
        original_open_leaf = evidence._open_leaf_at
        replaced = False

        def replace_then_mark(*args: object, **kwargs: object) -> None:
            nonlocal replaced
            original_replace(*args, **kwargs)
            replaced = True

        def fail_canonical_reopen(directory_fd: int, name: str) -> int:
            if replaced and name == fixture.canonical_name:
                raise evidence.EvidenceContractError(
                    "injected post-replace canonical reopen failure"
                )
            return original_open_leaf(directory_fd, name)

        with (
            mock.patch.object(
                evidence.os,
                "replace",
                side_effect=replace_then_mark,
            ),
            mock.patch.object(
                evidence,
                "_open_leaf_at",
                side_effect=fail_canonical_reopen,
            ),
        ):
            _raises(evidence.ManifestDurabilityUncertain, fixture.rotate)
        if not replaced:
            raise AssertionError("post-replace reopen fault fired before commit")
        _assert_complete_rotation(fixture, None)


def test_capture_stack_rotation_concurrent_callers_have_one_winner() -> None:
    with _CaptureStackRotationFixture() as fixture:
        result_lock = threading.Lock()
        successes: list[dict[str, object]] = []
        failures: list[BaseException] = []
        caller_a_inside = threading.Event()
        release_caller_a = threading.Event()
        loser_crossed_lock = threading.Event()
        original_open_authenticated = evidence.open_authenticated_artifact
        original_replace = evidence.os.replace

        def hold_caller_a_after_lock(
            directory_fd: int,
            contract: evidence.ArtifactContract,
        ) -> object:
            thread_name = threading.current_thread().name
            is_old_canonical = (
                contract.relative_path == fixture.canonical_name
                and contract.leaf.inode
                == fixture.expected_existing_contract.leaf.inode
            )
            if is_old_canonical and thread_name == "rotation-caller-a":
                if not caller_a_inside.is_set():
                    caller_a_inside.set()
                    if not release_caller_a.wait(timeout=10):
                        raise AssertionError("caller A lock hold timed out")
            elif is_old_canonical and thread_name in {
                "rotation-caller-b",
                "rotation-caller-c",
                "rotation-caller-d",
            }:
                loser_crossed_lock.set()
                raise evidence.EvidenceContractError(
                    f"{thread_name} crossed the held rotation lock"
                )
            return original_open_authenticated(directory_fd, contract)

        def rotate() -> None:
            canonical_fd = os.dup(fixture.canonical_fd)
            archive_fd = os.dup(fixture.archive_fd)
            workspace_fd = os.dup(fixture.workspace_fd)
            try:
                result = evidence.rotate_capture_stack_contract(
                    canonical_fd,
                    fixture.canonical_name,
                    fixture.new_document,
                    expected_existing_contract=fixture.expected_existing_contract,
                    expected_existing_sha256=fixture.old_sha256,
                    archive_dir_fd=archive_fd,
                    archive_name=fixture.archive_name,
                    workspace_root_fd=workspace_fd,
                )
                with result_lock:
                    successes.append(result)
            except BaseException as exc:  # noqa: BLE001
                with result_lock:
                    failures.append(exc)
            finally:
                os.close(workspace_fd)
                os.close(archive_fd)
                os.close(canonical_fd)

        caller_a = threading.Thread(
            target=rotate,
            name="rotation-caller-a",
            daemon=True,
        )
        losers = tuple(
            threading.Thread(
                target=rotate,
                name=f"rotation-caller-{suffix}",
                daemon=True,
            )
            for suffix in ("b", "c", "d")
        )
        with (
            mock.patch.object(
                evidence,
                "open_authenticated_artifact",
                side_effect=hold_caller_a_after_lock,
            ),
            mock.patch.object(
                evidence.os,
                "replace",
                wraps=original_replace,
            ) as replace_spy,
        ):
            caller_a.start()
            if not caller_a_inside.wait(timeout=5):
                release_caller_a.set()
                caller_a.join(timeout=5)
                raise AssertionError("caller A never entered the locked section")
            for loser in losers:
                loser.start()
            for loser in losers:
                loser.join(timeout=5)
            loser_blocked = any(loser.is_alive() for loser in losers)
            release_caller_a.set()
            caller_a.join(timeout=15)
            for loser in losers:
                loser.join(timeout=5)

        if caller_a.is_alive() or any(loser.is_alive() for loser in losers):
            raise AssertionError("concurrent rotation callers did not quiesce")
        if loser_blocked:
            raise AssertionError(
                "a losing caller blocked instead of failing the nonblocking lock"
            )
        if loser_crossed_lock.is_set():
            raise AssertionError(
                "a losing caller entered caller A's locked critical section"
            )
        if len(successes) != 1 or len(failures) != 3:
            raise AssertionError((successes, failures))
        if not all(
            isinstance(exc, evidence.EvidenceContractError) for exc in failures
        ):
            raise AssertionError([type(exc).__name__ for exc in failures])
        if replace_spy.call_count != 1:
            raise AssertionError(
                f"concurrent rotation replaced {replace_spy.call_count} times"
            )
        _assert_complete_rotation(fixture, successes[0])


def test_capture_stack_publication_fails_closed_before_link() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        root_fd = _root_fd(root)
        original_fsync = evidence.os.fsync

        def fail_file_fsync(descriptor: int) -> None:
            if descriptor != root_fd:
                raise OSError(5, "injected capture-stack file fsync failure")
            original_fsync(descriptor)

        failures = (
            (
                "write-failure.json",
                mock.patch.object(
                    evidence,
                    "_write_all",
                    side_effect=OSError(5, "injected capture-stack write failure"),
                ),
            ),
            (
                "file-fsync-failure.json",
                mock.patch.object(evidence.os, "fsync", side_effect=fail_file_fsync),
            ),
            (
                "link-failure.json",
                mock.patch.object(
                    evidence.os,
                    "link",
                    side_effect=OSError(5, "injected capture-stack link failure"),
                ),
            ),
        )
        try:
            for output_name, injected in failures:
                with injected:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda output_name=output_name: evidence.publish_capture_stack_contract(
                            root_fd,
                            output_name,
                            contract,
                            workspace_root=root.resolve(),
                        ),
                    )
                if (root / output_name).exists():
                    raise AssertionError(f"pre-link failure published {output_name}")
                if any(path.name.startswith(f".{output_name}.") for path in root.iterdir()):
                    raise AssertionError(f"pre-link failure leaked temp for {output_name}")

            sentinel = root / "capture-stack.json"
            sentinel.write_bytes(b"existing-contract")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.publish_capture_stack_contract(
                    root_fd,
                    sentinel.name,
                    contract,
                    workspace_root=root.resolve(),
                ),
            )
            if sentinel.read_bytes() != b"existing-contract":
                raise AssertionError("preexisting capture-stack output was replaced")
        finally:
            os.close(root_fd)


def test_capture_stack_post_link_durability_is_reopenable() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        root_fd = _root_fd(root)
        original_fsync = evidence.os.fsync

        def fail_directory_fsync(descriptor: int) -> None:
            if descriptor == root_fd:
                raise OSError(5, "injected capture-stack directory fsync failure")
            original_fsync(descriptor)

        try:
            with mock.patch.object(
                evidence.os,
                "fsync",
                side_effect=fail_directory_fsync,
            ):
                _raises(
                    evidence.ManifestDurabilityUncertain,
                    lambda: evidence.publish_capture_stack_contract(
                        root_fd,
                        "capture-stack.json",
                        contract,
                        workspace_root=root.resolve(),
                    ),
                )
            raw = (root / "capture-stack.json").read_bytes()
            expected_raw = evidence._canonical_json_bytes(contract)
            if raw != expected_raw:
                raise AssertionError("durability-uncertain contract is incomplete")
            reopened, _catalog, sha256 = evidence.authenticate_capture_stack_contract(
                root_fd,
                "capture-stack.json",
                workspace_root=root.resolve(),
                expected_owner=OWNER,
                expected_sha256=_sha256(expected_raw),
            )
            if reopened != contract or sha256 != _sha256(expected_raw):
                raise AssertionError("durability-uncertain contract did not reopen")
            if any(path.name.startswith(".capture-stack.json.") for path in root.iterdir()):
                raise AssertionError("durability-uncertain publication leaked its temp link")
        finally:
            os.close(root_fd)


def test_capture_stack_link_cleanup_fault_keeps_uncertain_classification() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        root_fd = _root_fd(root)
        original_unlink = evidence.os.unlink

        def fail_temporary_unlink(
            path: str | bytes,
            *,
            dir_fd: int | None = None,
        ) -> None:
            if os.fsdecode(path).startswith(".capture-stack.json."):
                raise OSError(5, "injected capture-stack temp unlink failure")
            original_unlink(path, dir_fd=dir_fd)

        try:
            with mock.patch.object(
                evidence.os,
                "unlink",
                side_effect=fail_temporary_unlink,
            ):
                _raises(
                    evidence.ManifestDurabilityUncertain,
                    lambda: evidence.publish_capture_stack_contract(
                        root_fd,
                        "capture-stack.json",
                        contract,
                        workspace_root=root.resolve(),
                    ),
                )
            expected_raw = evidence._canonical_json_bytes(contract)
            if (root / "capture-stack.json").read_bytes() != expected_raw:
                raise AssertionError("link-cleanup fault left incomplete final bytes")
            temporary_links = tuple(
                path
                for path in root.iterdir()
                if path.name.startswith(".capture-stack.json.")
            )
            if len(temporary_links) != 1:
                raise AssertionError(temporary_links)
            temporary_links[0].unlink()
            reopened, _catalog, sha256 = evidence.authenticate_capture_stack_contract(
                root_fd,
                "capture-stack.json",
                workspace_root=root.resolve(),
                expected_owner=OWNER,
                expected_sha256=_sha256(expected_raw),
            )
            if reopened != contract or sha256 != _sha256(expected_raw):
                raise AssertionError("cleaned link-cleanup fault did not reopen")
        finally:
            os.close(root_fd)


def test_capture_stack_concurrent_publication_has_one_winner() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        root_fd = _root_fd(root)
        barrier = threading.Barrier(4)
        successes: list[dict] = []
        failures: list[BaseException] = []
        result_lock = threading.Lock()

        def publish() -> None:
            worker_fd = os.dup(root_fd)
            try:
                barrier.wait()
                result = evidence.publish_capture_stack_contract(
                    worker_fd,
                    "capture-stack.json",
                    contract,
                    workspace_root=root.resolve(),
                )
                with result_lock:
                    successes.append(result)
            except BaseException as exc:  # noqa: BLE001
                with result_lock:
                    failures.append(exc)
            finally:
                os.close(worker_fd)

        threads = [threading.Thread(target=publish) for _ in range(4)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if len(successes) != 1 or len(failures) != 3:
                raise AssertionError((successes, failures))
            if not all(
                isinstance(exc, evidence.EvidenceContractError) for exc in failures
            ):
                raise AssertionError([type(exc).__name__ for exc in failures])
            reopened, _catalog, sha256 = evidence.authenticate_capture_stack_contract(
                root_fd,
                "capture-stack.json",
                workspace_root=root.resolve(),
                expected_owner=OWNER,
                expected_sha256=successes[0]["sha256"],
            )
            if reopened != contract or sha256 != successes[0]["sha256"]:
                raise AssertionError("concurrent winner did not publish exact bytes")
        finally:
            os.close(root_fd)


def test_live_profile_and_capture_stack_contract_are_exact() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        stack_paths = evidence.CAPTURE_STACK_MEMBERS
        for index, relative in enumerate(stack_paths):
            _write(
                root / relative,
                f"capture_stack_member = {index}\n".encode("utf-8"),
            )
        base_digest = evidence.capture_stack_digest(
            stack_paths, root=root.resolve()
        )
        catalog = _complete_control_catalog()
        catalog["baseCaptureStackDigest"] = base_digest
        catalog["captureStackDigest"] = evidence.control_catalog_digest(catalog)
        authenticated_catalog = evidence._mint_control_catalog(catalog)
        contract = evidence.build_capture_stack_contract(
            stack_paths,
            root=root.resolve(),
            control_catalog=authenticated_catalog,
        )
        if (
            contract["schemaVersion"] != evidence.CAPTURE_STACK_SCHEMA
            or contract["baseCaptureStackDigest"] != base_digest
            or contract["captureStackDigest"] != catalog["captureStackDigest"]
            or tuple(member["path"] for member in contract["members"])
            != tuple(sorted(stack_paths))
        ):
            raise AssertionError(contract)
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.build_capture_stack_contract(
                stack_paths[:-1],
                root=root.resolve(),
                control_catalog=authenticated_catalog,
            ),
        )
        _write(root / "scripts/extra_capture.py", b"extra = True\n")
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.build_capture_stack_contract(
                (*stack_paths, "scripts/extra_capture.py"),
                root=root.resolve(),
                control_catalog=authenticated_catalog,
            ),
        )
        output_fd = _root_fd(root)
        try:
            published = evidence.publish_capture_stack_contract(
                output_fd,
                "capture-stack.json",
                contract,
                workspace_root=root.resolve(),
            )
            reopened, reopened_catalog, sha256 = (
                evidence.authenticate_capture_stack_contract(
                    output_fd,
                    "capture-stack.json",
                    workspace_root=root.resolve(),
                    expected_owner=OWNER,
                    expected_sha256=published["sha256"],
                )
            )
        finally:
            os.close(output_fd)
        if (
            reopened != contract
            or reopened_catalog["captureStackDigest"]
            != contract["captureStackDigest"]
            or sha256 != published["sha256"]
        ):
            raise AssertionError((reopened, sha256, published))
        implementation = root / stack_paths[0]
        implementation.write_text("capture_stack_member = 'changed'\n", encoding="utf-8")
        _raises(
            evidence.EvidenceContractError,
            lambda: evidence.validate_capture_stack_contract(
                contract, root=root.resolve()
            ),
        )

    with tempfile.TemporaryDirectory() as temp:
        run_root = Path(temp)
        capture_root = run_root / "captures"
        capture_root.mkdir()
        run_fd = _root_fd(run_root)
        try:
            captures = _verified_profile_captures(
                capture_root,
                fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
                run_root_fd=run_fd,
            )
            report = evidence.validate_live_capture_profile(
                tuple(captures.values()),
                fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
                capture_stack_digest=_complete_control_catalog()[
                    "captureStackDigest"
                ],
            )
            if report.get("captureCount") != 3:
                raise AssertionError(report)
            attestation = evidence.mint_comparator_attestation(report)
            if not isinstance(attestation, evidence.ComparatorAttestation):
                raise AssertionError(type(attestation).__name__)
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.validate_live_capture_profile(
                    tuple(list(captures.values())[:-1]),
                    fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
                    capture_stack_digest=_complete_control_catalog()[
                        "captureStackDigest"
                    ],
                ),
            )
        finally:
            os.close(run_fd)

    parser = evidence.build_cli_parser()
    parsed = parser.parse_args(
        [
            "verify-manifest",
            "--manifest",
            "manifest.json",
            "--expected-mode",
            "ux1b-full-pages",
            "--expected-phase",
            "precontrol",
            "--expected-count",
            "81",
        ]
    )
    if parsed.expected_count != 81 or parsed.command != "verify-manifest":
        raise AssertionError(parsed)


def _make_cli_contract_workspace(root: Path) -> dict[str, object]:
    def make_file(relative: str, raw: bytes) -> dict[str, object]:
        path = _write(root / relative, raw)
        return {
            "path": relative,
            "sha256": _sha256(path.read_bytes()),
        }

    accepted = {
        "parentPlan": make_file("accepted/parent.md", b"parent\n"),
        "recoveryArchitecture": make_file("accepted/architecture.md", b"architecture\n"),
        "recoveryPlan": make_file("accepted/recovery.md", b"recovery\n"),
    }
    protected = [
        make_file(f"protected/file-{index}.txt", f"protected-{index}\n".encode())
        for index in range(6)
    ]
    selectors = [
        make_file(f"ui/selector-{index}.py", f"selector_{index} = True\n".encode())
        for index in range(9)
    ]
    tooling = [
        make_file(f"tooling/file-{index}.py", f"tooling_{index} = True\n".encode())
        for index in range(12)
    ]
    archive_raw = b"authenticated rollback archive\n"
    archive = make_file("bundle/prechange-files.tar", archive_raw)
    archive["size"] = len(archive_raw)
    owner = {"uid": os.getuid(), "gid": os.getgid()}
    bundle_manifest = {
        "schemaVersion": "quant-radar-ui-ux-ux1b-recovery-bundle/v1",
        "createdAt": "2026-07-16T14:55:33Z",
        "owner": owner,
        "archive": {
            "mode": "0644",
            "path": "prechange-files.tar",
            "sha256": archive["sha256"],
            "size": archive["size"],
        },
        "restorePolicy": {
            "createdFileDelete": "exact path + owner + posthash",
            "production": "exact anchored hunk",
            "tooling": "exact live posthash",
        },
        "productionControlRecords": [],
    }
    manifest_raw = json.dumps(bundle_manifest, sort_keys=True).encode()
    manifest = make_file("bundle/bundle-manifest.json", manifest_raw)
    manifest["size"] = len(manifest_raw)
    contract = {
        "schemaVersion": "quant-radar-ui-ux-ux1b-recovery-prechange/v1",
        "capturedAt": "2026-07-16T14:55:33Z",
        "workspaceRoot": str(root),
        "acceptedDocuments": accepted,
        "runtime": {
            "chromium": {"executable": "/owned/chromium", "version": "1"},
            "darwin": "26.5",
            "platform": "test",
            "playwright": "1.60.0",
            "python": {"executable": sys.executable, "version": "3.11"},
            "sandboxExec": {"path": "/usr/bin/sandbox-exec", "smokeExitCode": 0},
            "streamlit": "1.57.0",
        },
        "sourceMirrorPolicy": {
            "schemaVersion": "quant-radar-ui-ux-ux1b-source-mirror/v1",
            "include": ["scripts/**/*.py"],
            "exclude": [".git/**"],
            "fileKinds": ["new-inode regular files only"],
            "forbidden": ["symlink"],
        },
        "protectedFiles": protected,
        "productionSelectorFiles": selectors,
        "existingToolingFiles": tooling,
        "plannedCreatedFiles": [
            {"existsAtSnapshot": False, "path": f"planned/file-{index}.txt"}
            for index in range(12)
        ],
        "rollbackBundle": {
            "archive": archive,
            "manifest": manifest,
            "owner": owner,
        },
        "dirtyWorktree": {
            "porcelainV1NulSha256": "a" * 64,
            "policy": "do not adopt unrelated bytes",
            "entries": [" M user-owned.txt"],
        },
        "selfHash": None,
    }
    contract_path = _write(
        root / "recovery/prechange.json",
        json.dumps(contract, sort_keys=True).encode(),
    )
    return {
        "contract": contract,
        "contractPath": contract_path.relative_to(root),
        "parentSha256": accepted["parentPlan"]["sha256"],
        "selectorPaths": [row["path"] for row in selectors],
        "protectedPaths": [row["path"] for row in protected],
    }


def _verify_temp_prechange(root: Path, fixture: Mapping[str, object]) -> dict:
    with mock.patch.object(evidence, "_DEFAULT_WORKSPACE_ROOT", root):
        return evidence._verify_prechange_command(
            argparse.Namespace(
                contract=Path(fixture["contractPath"]),
                require_parent_sha=fixture["parentSha256"],
                verify_protected=True,
                verify_historical=True,
            )
        )


def _verify_temp_scope(
    root: Path, fixture: Mapping[str, object], allowed: list[str]
) -> dict:
    with mock.patch.object(evidence, "_DEFAULT_WORKSPACE_ROOT", root):
        return evidence._verify_scope_command(
            argparse.Namespace(
                contract=Path(fixture["contractPath"]),
                allow_selector_files=[Path(path) for path in allowed],
            )
        )


def test_direct_script_cli_and_prechange_scope_gates() -> None:
    parent_sha = "48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7"
    selector_paths = [
        "ui/risk_guard.py",
        "ui/institutions.py",
        "ui/options_cockpit.py",
        "ui/radar.py",
        "ui/knowledge_graph.py",
        "ui/ai_chat.py",
        "ui/retro_analysis.py",
        "ui/analytics_db.py",
        "ui/stock_checkup.py",
    ]
    commands = (
        [sys.executable, "scripts/ui_ux_evidence.py", "--help"],
        [
            sys.executable,
            "scripts/ui_ux_evidence.py",
            "verify-prechange",
            "--contract",
            "docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json",
            "--require-parent-sha",
            parent_sha,
            "--verify-protected",
            "--verify-historical",
        ],
        [
            sys.executable,
            "scripts/ui_ux_evidence.py",
            "verify-scope",
            "--contract",
            "docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json",
            "--allow-selector-files",
            *selector_paths,
        ],
    )
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0 or b"ModuleNotFoundError" in completed.stderr:
            raise AssertionError((command, completed.returncode, completed.stderr))
    for raw in (commands[1], commands[2]):
        completed = subprocess.run(raw, cwd=ROOT, capture_output=True, check=False)
        if json.loads(completed.stdout)["status"] != "passed":
            raise AssertionError(completed.stdout)


def test_prechange_cli_rejects_schema_hash_owner_and_namespace_drift() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fixture = _make_cli_contract_workspace(root)
        if _verify_temp_prechange(root, fixture)["status"] != "passed":
            raise AssertionError("valid prechange fixture was rejected")
        contract_path = root / fixture["contractPath"]
        original_contract = contract_path.read_bytes()
        malformed = json.loads(original_contract)
        malformed["unexpected"] = True
        contract_path.write_text(json.dumps(malformed, sort_keys=True), encoding="utf-8")
        _raises(evidence.EvidenceContractError, lambda: _verify_temp_prechange(root, fixture))
        contract_path.write_bytes(original_contract)

        wrong_parent = copy.deepcopy(fixture)
        wrong_parent["parentSha256"] = "f" * 64
        _raises(evidence.EvidenceContractError, lambda: _verify_temp_prechange(root, wrong_parent))
        for relative in (
            "accepted/parent.md",
            "accepted/recovery.md",
            fixture["protectedPaths"][0],
            "bundle/prechange-files.tar",
            "bundle/bundle-manifest.json",
        ):
            path = root / relative
            original = path.read_bytes()
            path.write_bytes(original + b"drift")
            _raises(
                evidence.EvidenceContractError,
                lambda: _verify_temp_prechange(root, fixture),
            )
            path.write_bytes(original)

        unsafe = root / fixture["protectedPaths"][0]
        unsafe.chmod(0o666)
        _raises(evidence.EvidenceContractError, lambda: _verify_temp_prechange(root, fixture))
        unsafe.chmod(0o644)

        parent = root / "accepted/parent.md"
        original_parent = parent.read_bytes()
        parent.unlink()
        parent.symlink_to(root / "accepted/recovery.md")
        _raises(evidence.EvidenceContractError, lambda: _verify_temp_prechange(root, fixture))
        parent.unlink()
        parent.write_bytes(original_parent)

        original_protected = evidence._verify_protected_files

        def replace_accepted_namespace(*args: object, **kwargs: object) -> object:
            accepted = root / "accepted"
            accepted.rename(root / "accepted-old")
            accepted.mkdir()
            return original_protected(*args, **kwargs)

        with mock.patch.object(
            evidence,
            "_verify_protected_files",
            side_effect=replace_accepted_namespace,
        ):
            _raises(
                evidence.EvidenceContractError,
                lambda: _verify_temp_prechange(root, fixture),
            )


def test_scope_cli_requires_exact_nine_safe_selector_files() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fixture = _make_cli_contract_workspace(root)
        selectors = list(fixture["selectorPaths"])
        changed_path = root / selectors[0]
        changed_path.write_bytes(b"selector changed under authorized Task 8\n")
        result = _verify_temp_scope(root, fixture, selectors)
        if result["selectorFileCount"] != 9 or result["changedSelectorFiles"] != [selectors[0]]:
            raise AssertionError(result)
        extra = _write(root / "ui/not-a-selector.py", b"extra = True\n")
        for allowed in (
            selectors[:-1],
            [*selectors, str(extra.relative_to(root))],
            [*selectors[:-1], fixture["protectedPaths"][0]],
            [*selectors, selectors[0]],
        ):
            _raises(
                evidence.EvidenceContractError,
                lambda allowed=allowed: _verify_temp_scope(root, fixture, allowed),
            )
        changed_path.unlink()
        changed_path.symlink_to(root / selectors[1])
        _raises(
            evidence.EvidenceContractError,
            lambda: _verify_temp_scope(root, fixture, selectors),
        )


def test_capture_stack_fd_authority_and_prelink_rehash_are_closed() -> None:
    with tempfile.TemporaryDirectory() as temp:
        parent = Path(temp)
        workspace = parent / "workspace"
        workspace.mkdir()
        contract = _new_capture_stack_contract(workspace)
        raw = evidence._canonical_json_bytes(contract)
        _write(workspace / "capture-stack.json", raw)
        workspace_fd = _root_fd(workspace)
        try:
            path_digest = evidence.capture_stack_digest(
                evidence.CAPTURE_STACK_MEMBERS, root=workspace.resolve()
            )
            fd_digest = evidence.capture_stack_digest(
                evidence.CAPTURE_STACK_MEMBERS, root_fd=workspace_fd
            )
            if path_digest != fd_digest:
                raise AssertionError((path_digest, fd_digest))
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.capture_stack_digest(evidence.CAPTURE_STACK_MEMBERS),
            )
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.capture_stack_digest(
                    evidence.CAPTURE_STACK_MEMBERS,
                    root=workspace.resolve(),
                    root_fd=workspace_fd,
                ),
            )

            detached = parent / "detached"
            workspace.rename(detached)
            replacement = parent / "workspace"
            replacement.mkdir()
            _new_capture_stack_contract(replacement)
            _write(replacement / "capture-stack.json", raw)
            (detached / evidence.CAPTURE_STACK_MEMBERS[0]).write_bytes(b"old fd drift\n")
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence.authenticate_capture_stack_contract(
                    workspace_fd,
                    "capture-stack.json",
                    workspace_root_fd=workspace_fd,
                    expected_owner=OWNER,
                ),
            )
            os.fstat(workspace_fd)
        finally:
            os.close(workspace_fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        contract_path = _write(
            root / "capture-stack.json", evidence._canonical_json_bytes(contract)
        )
        root_fd = _root_fd(root)
        original_validate = evidence.validate_capture_stack_contract

        def validate_then_replace(*args: object, **kwargs: object) -> dict[str, object]:
            validated = original_validate(*args, **kwargs)
            replacement = root / ".replacement-contract.json"
            replacement.write_bytes(b"{}")
            os.replace(replacement, contract_path)
            return validated

        try:
            with mock.patch.object(
                evidence,
                "validate_capture_stack_contract",
                side_effect=validate_then_replace,
            ):
                _raises(
                    evidence.EvidenceContractError,
                    lambda: evidence.authenticate_capture_stack_contract(
                        root_fd,
                        "capture-stack.json",
                        workspace_root_fd=root_fd,
                        expected_owner=OWNER,
                    ),
                )
        finally:
            os.close(root_fd)

    with tempfile.TemporaryDirectory() as temp:
        parent = Path(temp)
        workspace = parent / "workspace"
        workspace.mkdir()
        contract = _new_capture_stack_contract(workspace)
        raw = evidence._canonical_json_bytes(contract)
        _write(workspace / "capture-stack.json", raw)
        workspace_fd = _root_fd(workspace)
        try:
            workspace.rename(parent / "detached")
            replacement = parent / "workspace"
            replacement.mkdir()
            _new_capture_stack_contract(replacement)
            (replacement / evidence.CAPTURE_STACK_MEMBERS[0]).write_bytes(
                b"replacement drift\n"
            )
            authenticated, _catalog, _sha = evidence.authenticate_capture_stack_contract(
                workspace_fd,
                "capture-stack.json",
                workspace_root_fd=workspace_fd,
                expected_owner=OWNER,
            )
            if authenticated != contract:
                raise AssertionError("retained workspace fd consulted replacement pathname")
        finally:
            os.close(workspace_fd)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        contract = _new_capture_stack_contract(root)
        root_fd = _root_fd(root)
        original_write_all = evidence._write_all
        mutated = False

        def write_then_mutate(descriptor: int, raw_bytes: bytes) -> None:
            nonlocal mutated
            original_write_all(descriptor, raw_bytes)
            if not mutated:
                mutated = True
                (root / evidence.CAPTURE_STACK_MEMBERS[0]).write_bytes(b"late drift\n")

        try:
            with mock.patch.object(evidence, "_write_all", side_effect=write_then_mutate):
                with mock.patch.object(evidence.os, "link", wraps=os.link) as link_spy:
                    _raises(
                        evidence.EvidenceContractError,
                        lambda: evidence.publish_capture_stack_contract(
                            root_fd,
                            "capture-stack.json",
                            contract,
                            workspace_root_fd=root_fd,
                        ),
                    )
                    if link_spy.call_count != 0:
                        raise AssertionError("capture-stack final leaf linked before rehash")
            if (root / "capture-stack.json").exists():
                raise AssertionError("failed pre-link rehash published a final leaf")
            if any(path.name.startswith(".capture-stack.json.") for path in root.iterdir()):
                raise AssertionError("failed pre-link rehash leaked a temporary leaf")
        finally:
            os.close(root_fd)

    command = evidence.build_browser_worker_command(
        sys.executable,
        "scripts/ui_ux_browser_worker.py",
        expected_origin=APP_ORIGIN,
        expected_request_id=REQUEST_ID,
        allowed_staging_paths=(PNG_STAGE_PATH, SIDECAR_STAGE_PATH),
        browser_executable="/owned/chromium",
    )
    if command.count("--browser-executable") != 1:
        raise AssertionError(command)


def test_sequence13_v2_publication_claim_uses_finalized_schema() -> None:
    """TEST-130: publication derives its claim from exact finalized bytes."""

    root_row = next(
        row
        for row in evidence.root_capture_expansion_rows()
        if row["rootCaptureId"] == "ai-chat-settings-controls/desktop/root-01"
    )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        run_fd = _root_fd(root)
        captures: dict[str, object] = {}
        try:
            with mock.patch.object(
                evidence,
                "root_capture_expansion_rows",
                return_value=(root_row,),
            ):
                captures = _verified_root_profile_captures(
                    root,
                    run_root_fd=run_fd,
                )
            verified = captures[root_row["rootCaptureId"]]
            sidecar_claim = verified["renderSidecar"]
            sidecar_raw = (root / sidecar_claim["path"]).read_bytes()
            staging = root / "staging"
            output = root / "published"
            staging.mkdir()
            output.mkdir()
            (staging / "capture.png").write_bytes(
                _viewport_png({"width": 1440, "height": 900})
            )
            staging_fd = _root_fd(staging)
            output_fd = _root_fd(output)
            try:
                with mock.patch.object(
                    evidence,
                    "finalize_render_sidecar",
                    return_value=sidecar_raw,
                ):
                    record = evidence.publish_finalized_capture(
                        staging_fd,
                        output_fd,
                        expected_owner=OWNER,
                        staged_png_path="capture.png",
                        authenticated_raw_sidecar=object(),
                        authenticated_counters=object(),
                        capture_id=root_row["logicalCaptureId"],
                    )
            finally:
                os.close(output_fd)
                os.close(staging_fd)
            if (
                record["renderSidecar"]["schemaVersion"]
                != evidence.RENDER_V2_SCHEMA
            ):
                raise AssertionError(record)
        finally:
            for capture in captures.values():
                capture.close()
            os.close(run_fd)


def test_sequence13_manifest_reopen_preserves_v1_and_v2_schema() -> None:
    """TEST-131/132: reopen preserves schema and rejects a false claim."""

    root_row = next(
        row
        for row in evidence.root_capture_expansion_rows()
        if row["rootCaptureId"] == "ai-chat-settings-controls/desktop/root-01"
    )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        run_fd = _root_fd(root)
        captures: dict[str, object] = {}
        try:
            with mock.patch.object(
                evidence,
                "root_capture_expansion_rows",
                return_value=(root_row,),
            ):
                captures = _verified_root_profile_captures(
                    root,
                    run_root_fd=run_fd,
                )
            verified = captures[root_row["rootCaptureId"]]
            png_claim = copy.deepcopy(verified["png"])
            sidecar_claim = copy.deepcopy(verified["renderSidecar"])
            png_raw = (root / png_claim["path"]).read_bytes()
            sidecar_raw = (root / sidecar_claim["path"]).read_bytes()
            artifacts, document = evidence._validate_open_capture_bytes(
                png_raw,
                sidecar_raw,
                {
                    "png": png_claim,
                    "renderSidecar": sidecar_claim,
                },
            )
            if (
                document["schemaVersion"] != evidence.RENDER_V2_SCHEMA
                or artifacts["renderSidecar"]["schemaVersion"]
                != evidence.RENDER_V2_SCHEMA
            ):
                raise AssertionError(artifacts)
            false_record = {
                "png": png_claim,
                "renderSidecar": sidecar_claim
                | {"schemaVersion": evidence.RENDER_SCHEMA},
            }
            _raises(
                evidence.EvidenceContractError,
                lambda: evidence._validate_open_capture_bytes(
                    png_raw,
                    sidecar_raw,
                    false_record,
                ),
            )

            legacy_root = root / "legacy"
            legacy_root.mkdir()
            legacy_record = _capture_record(legacy_root)
            legacy_artifacts, legacy_document = (
                evidence._validate_open_capture_bytes(
                    (legacy_root / legacy_record["png"]["path"]).read_bytes(),
                    (
                        legacy_root
                        / legacy_record["renderSidecar"]["path"]
                    ).read_bytes(),
                    legacy_record,
                )
            )
            if (
                legacy_document["schemaVersion"] != evidence.RENDER_SCHEMA
                or legacy_artifacts["renderSidecar"]["schemaVersion"]
                != evidence.RENDER_SCHEMA
            ):
                raise AssertionError(legacy_artifacts)
        finally:
            for capture in captures.values():
                capture.close()
            os.close(run_fd)


def main() -> None:
    tests = [
        test_worker_request_response_schema_is_exact_and_bounded,
        test_root_capture_expansion_and_v2_protocol_are_exact,
        test_coordinator_copy_cannot_replace_final_outputs,
        test_component_walk_rejects_unsafe_paths_and_symlinks,
        test_component_walk_rejects_ancestor_leaf_and_mode_swaps,
        test_leaf_must_be_owned_one_link_regular_file,
        test_copy_uses_authenticated_fd_and_rechecks_that_inode,
        test_manifest_passed_is_final_only_and_terminal_is_immutable,
        test_full_page_finalizer_succeeds_under_256_fd_soft_limit,
        test_root_capture_lifecycle_is_exact_36_44_88_89,
        test_catchable_failures_checkpoint_one_terminal_status,
        test_stale_nonterminal_is_classified_without_rewriting_source,
        test_stale_nonterminal_accepts_full_page_posttheme_identity,
        test_stale_nonterminal_rejects_noncanonical_or_forged_identity,
        test_theme_counter_bundle_is_complete_exact_and_nonempty,
        test_descriptor_counter_enrichment_is_required_and_exact,
        test_canonical_sidecar_strips_only_explicit_volatile_paths,
        test_png_and_render_sidecar_are_independently_authenticated,
        test_theme_supplements_are_exact_descriptor_derived_crops,
        test_theme_crop_pixels_reject_palette_apng_and_forged_parent_authority,
        test_atomic_new_leaf_publication_is_complete_or_absent_under_faults,
        test_manifest_bundle_is_descriptor_reauthenticated_at_finalization,
        test_theme_pair_requires_exact_canonical_sidecars_and_valid_dimensions,
        test_success_closure_rejects_source_counter_capture_and_process_failures,
        test_control_catalog_is_complete_and_exact,
        test_migration_comparator_accepts_shared_boundary_translation_once,
        test_migration_comparator_rejects_unauthorized_and_unmapped_changes,
        test_focused_control_contract_is_exact_and_mutation_closed,
        test_focused_overlap_boundaries_are_exact_and_mirrored,
        test_focused_screenshot_binding_v2_is_exact_and_mutation_closed,
        test_root_render_v2_and_case_semantic_projection_are_closed,
        test_real_chromium_focused_screenshot_binding_is_pre_post_exact,
        test_focused_semantic_snapshot_is_atomic_stable_and_non_mutating,
        test_real_chromium_focused_semantic_readiness_waits_for_exact_stability,
        test_real_chromium_focused_layout_temporarily_scrolls_and_restores,
        test_real_chromium_focused_layout_failures_restore_and_stay_bounded,
        test_real_chromium_radio_audit_preserves_native_keys_without_rerender,
        test_real_chromium_hidden_radio_labels_are_semantic_and_actionable,
        test_real_chromium_hidden_radio_labels_fail_closed_independently,
        test_real_chromium_radio_audit_rejects_pre_guard_rerender_and_restores_initial_scroll,
        test_real_chromium_ai_hidden_labels_reacquire_after_subtree_replacement,
        test_real_chromium_selectbox_audit_selects_and_restores_after_rerender,
        test_real_chromium_rerendering_scroll_audit_rejects_root_chain_replacement,
        test_real_chromium_analytics_semantic_readiness_commits_once,
        test_capture_stack_digest_is_descriptor_authenticated,
        test_theme_worker_rich_raw_sidecar_auth_is_exact_and_mutation_closed,
        test_capture_stack_rotation_archives_old_and_reopens_new_exactly,
        test_capture_stack_rotation_rejects_stale_authority_before_writes,
        test_capture_stack_rotation_reuses_only_exact_archive,
        test_capture_stack_rotation_reuse_reconfirms_archive_directory_durability,
        test_capture_stack_rotation_precommit_faults_preserve_old_canonical,
        test_capture_stack_rotation_postreplace_faults_are_uncertain,
        test_capture_stack_rotation_concurrent_callers_have_one_winner,
        test_capture_stack_publication_fails_closed_before_link,
        test_capture_stack_post_link_durability_is_reopenable,
        test_capture_stack_link_cleanup_fault_keeps_uncertain_classification,
        test_capture_stack_concurrent_publication_has_one_winner,
        test_live_profile_and_capture_stack_contract_are_exact,
        test_direct_script_cli_and_prechange_scope_gates,
        test_prechange_cli_rejects_schema_hash_owner_and_namespace_drift,
        test_scope_cli_requires_exact_nine_safe_selector_files,
        test_capture_stack_fd_authority_and_prelink_rehash_are_closed,
        test_sequence13_v2_publication_claim_uses_finalized_schema,
        test_sequence13_manifest_reopen_preserves_v1_and_v2_schema,
        test_browser_worker_focused_interaction_catalog_is_exact_and_dual_compatible,
        test_selection_completion_generation_is_exact_and_monotonic,
        test_browser_worker_streamlit_404_console_correlation_is_order_independent,
        test_full_page_worker_waits_for_post_app_completion_marker,
        test_full_page_worker_waits_for_unique_catalog_roots,
        test_real_mirror_chromium_worker_raw_stage_smoke,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
