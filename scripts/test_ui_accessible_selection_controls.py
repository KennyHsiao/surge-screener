#!/usr/bin/env python3
"""Red/green behavior and accessibility gates for the UX-1B selector migration.

The default invocation is a normal test run: it is intentionally red while the
eleven frozen ``segmented_control`` calls remain and becomes green only after
Task 8 migrates all ten radios plus the Analytics selectbox and hardens that
table selector's wrong-shaped-catalog boundary.  The
``--expect-legacy-red`` mode is a Task 7 authoring gate: infrastructure and
downstream behavior must pass, and only the exact migration tests may fail.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_browser_worker as browser_worker  # noqa: E402
from scripts import ui_ux_evidence as evidence  # noqa: E402
from ui import (  # noqa: E402
    ai_chat,
    analytics_db,
    institutions,
    knowledge_graph,
    options_cockpit,
    radar,
    retro_analysis,
    risk_guard,
    stock_checkup,
)


CAPTURE_STACK_PATH = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json"
)
CAPTURE_STACK_SHA256 = (
    "a6dc1f4b97e727f7b641b845004e61b0a773b8a247af7ae6ddc38bac6c5b95c7"
)
SEQUENCE12_CAPTURE_STACK_PATH = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq12.json"
)
SEQUENCE12_CAPTURE_STACK_SHA256 = (
    "6e625cbb4d3e9b14e24dfc10a359d3047dbda59f00ff441e5449c5169ac6bf90"
)
LEGACY_CAPTURE_STACK_PATH = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json"
)
LEGACY_CAPTURE_STACK_SHA256 = (
    "8b354ec6d7f84e4bfbd96c098ffd1dae2db0d90f7f9cf86d168bc8a9298df820"
)
SELECTOR_DELTA_PATH = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-task8-selector-delta.json"
)
SELECTOR_DELTA_SHA256 = (
    "5b3ec3e04f4bee41e89072f52a38bdff3dc30abe937fad43ceebba6e6a7d5f24"
)
SELECTOR_DELTA_SIZE = 20_423
SELECTOR_DELTA_SCHEMA = "quant-radar-ui-ux-ux1b-task8-selector-delta/v1"
SELECTOR_DELTA_CREATED_AT = "2026-07-19T14:25:40Z"
SELECTOR_DELTA_MAX_BYTES = 128 * 1024
RECOVERY_ROLLBACK_PATH = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json"
)


@dataclass(frozen=True)
class SelectorContract:
    path: str
    key: str
    options: tuple[str, ...]
    default: str
    replacement: str
    label: str
    label_visibility: str | None = None
    help_text: str | None = None


SELECTORS = (
    SelectorContract(
        "ui/risk_guard.py",
        "rg_source",
        ("手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"),
        "Watchlist",
        "radio",
        "來源",
    ),
    SelectorContract(
        "ui/institutions.py",
        "inst_view",
        (
            "機構持股 · 股票 → 誰持有它",
            "機構持倉 · 機構 → 它持有什麼",
        ),
        "機構持股 · 股票 → 誰持有它",
        "radio",
        "檢視",
        label_visibility="collapsed",
    ),
    SelectorContract(
        "ui/options_cockpit.py",
        "cockpit_price_view_{}",
        ("快照圖 + 預期波動錐", "互動圖 (TradingView)"),
        "快照圖 + 預期波動錐",
        "radio",
        "圖表模式",
        label_visibility="collapsed",
    ),
    SelectorContract(
        "ui/radar.py",
        "radar_source",
        ("手動輸入", "Watchlist", "Screener 候選", "反轉候選(掃描)", "IBKR 持倉"),
        "手動輸入",
        "radio",
        "來源",
    ),
    SelectorContract(
        "ui/radar.py",
        "radar_view",
        ("全部", "風險警示", "反轉候選", "兩者共現"),
        "全部",
        "radio",
        "顯示",
        label_visibility="collapsed",
    ),
    SelectorContract(
        "ui/knowledge_graph.py",
        "kg_view_mode",
        ("星雲圖", "驗證泳道"),
        "星雲圖",
        "radio",
        "視圖",
    ),
    SelectorContract(
        "ui/knowledge_graph.py",
        "kg_label_mode",
        ("核心", "因子", "全部", "無"),
        "核心",
        "radio",
        "標籤",
    ),
    SelectorContract(
        "ui/ai_chat.py",
        "ai_chat_mode",
        ("快速問答", "深度研究"),
        "快速問答",
        "radio",
        "模式",
        help_text="快速問答不查網路；深度研究可用受限 web search/fetch。",
    ),
    SelectorContract(
        "ui/retro_analysis.py",
        "retro_validation_lane",
        ("暴漲事件復盤", "續漲強者", "Playbook 驗證"),
        "暴漲事件復盤",
        "radio",
        "驗證類型",
    ),
    SelectorContract(
        "ui/analytics_db.py",
        "adb_table",
        ("candidate_rankings", "iv_history"),
        "candidate_rankings",
        "selectbox",
        "資料表",
    ),
    SelectorContract(
        "ui/stock_checkup.py",
        "checkup_mode",
        ("單檔", "批次"),
        "單檔",
        "radio",
        "模式",
        label_visibility="collapsed",
    ),
)

EXPECTED_LEGACY = tuple(sorted((item.path, item.key) for item in SELECTORS))

SELECTOR_DELTA_OWNER = {"uid": 501, "gid": 20}
SELECTOR_DELTA_CONTROL_CATALOG = (
    "rg_source",
    "inst_view",
    "cockpit_price_view_NVDA",
    "radar_source",
    "radar_view",
    "kg_view_mode",
    "kg_label_mode",
    "ai_chat_mode",
    "retro_validation_lane",
    "adb_table",
    "checkup_mode",
)
SELECTOR_DELTA_FILE_ORACLES = (
    (
        "ui/risk_guard.py",
        "2e81f16c9e828bbf5a58613b847e0dd0a9de32375e4aeba2e2ea17d7ee194e83",
        19_820,
        "fb90a5d352c5aa1952d10fce0c56da25e2f09769ee644be8366a2ea93a8c2bee",
        19_960,
    ),
    (
        "ui/institutions.py",
        "a02481a9f5aa9cc2137d5f919c7db6d6a51bd649991082ab443c6e22360d7361",
        1_433,
        "de32f082a44c5f3428f75875cf7f2e4224d696b09b8cccb102bc46bed39edf87",
        1_469,
    ),
    (
        "ui/options_cockpit.py",
        "9b7e918f0b5c0b69041f26603f50db2c1fccac929c94e25bb1602d2e694d1a2f",
        80_104,
        "9c8f131d6c5edd369e2f0f316a8821fc32419d405df7c29141d84624767ec9e5",
        80_272,
    ),
    (
        "ui/radar.py",
        "4428b8ab47ce51421f8bb4f0ec47365f10ff8b97208606cf2cd42d6ac650979a",
        15_554,
        "917a329ea8a8297cc29bed1f892c2133ce5934d643469b97df36ffe9216fcd1c",
        15_763,
    ),
    (
        "ui/knowledge_graph.py",
        "22c293b7e28fd6fc9d0ed5ea4a1adebaa277e5d7c4201d0166a1ef4759c82bf6",
        26_285,
        "01a412f7287405d2f201fb6ed7a4cfc4a882170b44300ae6bfe202b2ff8e0acd",
        26_640,
    ),
    (
        "ui/ai_chat.py",
        "b838db07fe125e061a39e7249d1a42611562e8cd32bf8a0420574bd4267f28d2",
        23_226,
        "2b1c5739d87e604da17f217b99010426b7873a83223062be4c2b5e8c151b92a2",
        23_450,
    ),
    (
        "ui/retro_analysis.py",
        "2fb1b58b774e3c9154bc2bf25254fbe321aa19ca981bd657c5261f29f881f604",
        36_853,
        "5030e678eb5fbafe06b96f9ced93d53bb98908d45ffcb7384f7c8c216ccc6a5e",
        36_917,
    ),
    (
        "ui/analytics_db.py",
        "a63c08fcbf888620c9f9440d9219b40d412825068bf36020a1346c127cfffa58",
        43_963,
        "9475fb3c8614ed8e102c2619c325562025768445c45d5f625f0ad54d71467fe7",
        44_382,
    ),
    (
        "ui/stock_checkup.py",
        "68e448fd012ff5ffbc988b8f5f7a4dc96acb264cdea8b28134ce9c0476777d97",
        25_701,
        "1f38b26fd3ae137b4929bc0ac4dd8441f4a0bf38994a83696517ea66df7b4e45",
        25_768,
    ),
)
SELECTOR_DELTA_SPAN_CATALOG = (
    ("rg-source-widget", "ui/risk_guard.py", ("rg_source",)),
    ("inst-view-docs", "ui/institutions.py", ("inst_view",)),
    ("inst-view-widget", "ui/institutions.py", ("inst_view",)),
    (
        "cockpit-price-view-widget",
        "ui/options_cockpit.py",
        ("cockpit_price_view_NVDA",),
    ),
    ("radar-source-widget", "ui/radar.py", ("radar_source",)),
    ("radar-view-widget", "ui/radar.py", ("radar_view",)),
    (
        "knowledge-graph-widgets",
        "ui/knowledge_graph.py",
        ("kg_view_mode", "kg_label_mode"),
    ),
    ("ai-chat-mode-widget", "ui/ai_chat.py", ("ai_chat_mode",)),
    ("retro-lane-widget", "ui/retro_analysis.py", ("retro_validation_lane",)),
    ("analytics-table-widget", "ui/analytics_db.py", ("adb_table",)),
    ("stock-checkup-mode-widget", "ui/stock_checkup.py", ("checkup_mode",)),
)
SELECTOR_DELTA_AUTHORITIES = {
    "acceptedAmendment": {
        "path": "docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-hidden-radio-label-remediation.md",
        "sha256": "c87484d7bb017fa9b0514ac20dcb4e24e8a933afaf16d6494946205af8b89cfe",
        "size": 37_960,
    },
    "parentRecoveryPlan": {
        "path": "docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md",
        "sha256": "c31b42e33d388a53f22b399fe259ef6fd74e206d3a4f5f9775492c8e55a39837",
        "size": 48_453,
    },
    "prechangeContract": {
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json",
        "sha256": "13d67dec94b51868fd54734d029123975d559fb513a211b8096eb63b59475101",
        "size": 12_780,
    },
    "prechangeArchive": {
        "path": ".claude/ui_snapshots/ux1b/recovery/prechange-bundle-20260716T145533Z/prechange-files.tar",
        "sha256": "1101b22382420192369fb804d46bda6614a5bf5b6905bb760b700c8a668cdcf1",
        "size": 1_182_208,
        "mode": 0o600,
        "uid": 501,
        "gid": 20,
        "nlink": 1,
    },
    "prechangeManifest": {
        "path": ".claude/ui_snapshots/ux1b/recovery/prechange-bundle-20260716T145533Z/bundle-manifest.json",
        "sha256": "bde4b6db456c213c2f52fbb9122e3602dc589e35fa7614663e3d8dd84c9be4cc",
        "size": 6_367,
        "mode": 0o600,
        "uid": 501,
        "gid": 20,
        "nlink": 1,
    },
}
SELECTOR_DELTA_TRANSITION_POLICY = {
    "allowedStates": ["all-legacy", "all-migrated"],
    "preflight": (
        "Authenticate all nine whole-file hashes, all eleven exact spans, "
        "both anchors, and uniform state before writing."
    ),
    "application": (
        "Apply all eleven anchored spans in one multi-file apply_patch transaction."
    ),
    "wholeFileReplacementAllowed": False,
    "mixedStateAllowed": False,
    "failurePolicy": (
        "Prove zero partial writes; if mixed, repair forward once to "
        "all-migrated and stop."
    ),
}
MISSING = object()


class ExpectedMigrationDelta(AssertionError):
    """A reviewed red-state delta that Task 8 is explicitly meant to remove."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        items: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.category = category
        self.items = tuple(items)


class SelectorDeltaContractError(AssertionError):
    """The authenticated Task 8 selector delta failed closed."""


class _ColumnConfig:
    def __getattr__(self, name: str) -> Callable[..., dict[str, Any]]:
        return lambda *args, **kwargs: {
            "kind": name,
            "args": args,
            "kwargs": kwargs,
        }


class _Owner:
    def __init__(self, root: "FakeStreamlit") -> None:
        self._root = root

    def __enter__(self) -> "_Owner":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._root, name)


class FakeStreamlit:
    """Small fail-closed Streamlit model for selector and branch behavior."""

    def __init__(
        self,
        state: Mapping[str, Any] | None = None,
        *,
        button_values: Mapping[str, bool] | None = None,
    ) -> None:
        self.session_state: dict[str, Any] = dict(state or {})
        self.button_values = dict(button_values or {})
        self.widget_calls: list[dict[str, Any]] = []
        self.text_inputs: list[str | None] = []
        self.frames: list[Any] = []
        self.figures: list[Any] = []
        self.messages: list[tuple[str, str]] = []
        self.column_config = _ColumnConfig()
        self.context = SimpleNamespace(url="")
        self.query_params: dict[str, str] = {}

    def _owner(self) -> _Owner:
        return _Owner(self)

    def columns(self, spec: int | Sequence[Any], **_kwargs: Any) -> list[_Owner]:
        count = spec if isinstance(spec, int) else len(spec)
        return [self._owner() for _index in range(count)]

    def tabs(self, labels: Sequence[str]) -> list[_Owner]:
        return [self._owner() for _label in labels]

    def container(self, **_kwargs: Any) -> _Owner:
        return self._owner()

    def expander(self, *_args: Any, **_kwargs: Any) -> _Owner:
        return self._owner()

    def form(self, *_args: Any, **_kwargs: Any) -> _Owner:
        return self._owner()

    def spinner(self, *_args: Any, **_kwargs: Any) -> _Owner:
        return self._owner()

    def chat_message(self, *_args: Any, **_kwargs: Any) -> _Owner:
        return self._owner()

    def empty(self) -> _Owner:
        return self._owner()

    def progress(self, *_args: Any, **_kwargs: Any) -> _Owner:
        return self._owner()

    def _widget(
        self,
        method: str,
        label: str,
        options: Sequence[Any],
        *,
        key: str | None,
        default: Any = MISSING,
        index: int | None = 0,
        **kwargs: Any,
    ) -> Any:
        values = tuple(options)
        if key is not None and key in self.session_state:
            selected = self.session_state[key]
        elif default is not MISSING:
            selected = default
        elif index is None:
            selected = None
        elif values:
            selected = values[index or 0]
        else:
            selected = None
        if key is not None and key not in self.session_state:
            self.session_state[key] = selected
        self.widget_calls.append(
            {
                "method": method,
                "label": label,
                "options": values,
                "key": key,
                "default": default,
                "index": index,
                "kwargs": dict(kwargs),
                "selected": selected,
            }
        )
        return selected

    def segmented_control(
        self,
        label: str,
        options: Sequence[Any],
        *,
        default: Any = MISSING,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._widget(
            "segmented_control",
            label,
            options,
            key=key,
            default=default,
            index=None,
            **kwargs,
        )

    def radio(
        self,
        label: str,
        options: Sequence[Any],
        *,
        index: int | None = 0,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._widget(
            "radio", label, options, key=key, index=index, **kwargs
        )

    def selectbox(
        self,
        label: str,
        options: Sequence[Any],
        *,
        index: int | None = 0,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._widget(
            "selectbox", label, options, key=key, index=index, **kwargs
        )

    def multiselect(
        self,
        label: str,
        options: Sequence[Any],
        *,
        default: Sequence[Any] | None = None,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._widget(
            "multiselect",
            label,
            options,
            key=key,
            default=list(default or []),
            index=None,
            **kwargs,
        )

    def _value_widget(
        self,
        method: str,
        label: str,
        value: Any,
        *,
        key: str | None,
        **kwargs: Any,
    ) -> Any:
        return self._widget(
            method,
            label,
            (value,),
            key=key,
            default=value,
            index=None,
            **kwargs,
        )

    def text_input(
        self,
        label: str,
        value: str = "",
        *,
        key: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.text_inputs.append(key)
        selected = self._value_widget(
            "text_input", label, value, key=key, **kwargs
        )
        return str(selected or "")

    def text_area(
        self,
        label: str,
        value: str = "",
        *,
        key: str | None = None,
        **kwargs: Any,
    ) -> str:
        selected = self._value_widget(
            "text_area", label, value, key=key, **kwargs
        )
        return str(selected or "")

    def toggle(
        self,
        label: str,
        value: bool = False,
        *,
        key: str | None = None,
        **kwargs: Any,
    ) -> bool:
        return bool(
            self._value_widget("toggle", label, value, key=key, **kwargs)
        )

    def checkbox(
        self,
        label: str,
        value: bool = False,
        *,
        key: str | None = None,
        **kwargs: Any,
    ) -> bool:
        return bool(
            self._value_widget("checkbox", label, value, key=key, **kwargs)
        )

    def slider(
        self,
        label: str,
        *,
        value: Any = None,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._value_widget("slider", label, value, key=key, **kwargs)

    def button(self, _label: str, *, key: str | None = None, **_kwargs: Any) -> bool:
        return bool(self.button_values.get(str(key), False))

    def form_submit_button(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def dataframe(self, value: Any, **_kwargs: Any) -> None:
        self.frames.append(value)

    def plotly_chart(self, value: Any, **_kwargs: Any) -> None:
        self.figures.append(value)

    def download_button(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def metric(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def rerun(self) -> None:
        raise AssertionError("unexpected Streamlit rerun")

    def _message(self, method: str, value: Any) -> None:
        self.messages.append((method, str(value)))

    def header(self, value: Any, **_kwargs: Any) -> None:
        self._message("header", value)

    def title(self, value: Any, **_kwargs: Any) -> None:
        self._message("title", value)

    def subheader(self, value: Any, **_kwargs: Any) -> None:
        self._message("subheader", value)

    def caption(self, value: Any, **_kwargs: Any) -> None:
        self._message("caption", value)

    def markdown(self, value: Any, **_kwargs: Any) -> None:
        self._message("markdown", value)

    def info(self, value: Any, **_kwargs: Any) -> None:
        self._message("info", value)

    def warning(self, value: Any, **_kwargs: Any) -> None:
        self._message("warning", value)

    def success(self, value: Any, **_kwargs: Any) -> None:
        self._message("success", value)

    def error(self, value: Any, **_kwargs: Any) -> None:
        self._message("error", value)

    def divider(self) -> None:
        return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selector_delta_fail(message: str) -> None:
    raise SelectorDeltaContractError(message)


def _selector_delta_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        _selector_delta_fail(f"{label} must be a string-keyed mapping")
    return value


def _selector_delta_exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    observed = set(value)
    if observed != expected:
        _selector_delta_fail(
            f"{label} keys differ: missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def _selector_delta_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _selector_delta_json_equal(observed: object, expected: object) -> bool:
    try:
        return evidence._canonical_json_bytes(
            observed
        ) == evidence._canonical_json_bytes(expected)
    except evidence.EvidenceContractError as exc:
        raise SelectorDeltaContractError(
            f"selector delta value is not canonical JSON: {exc}"
        ) from exc


def _read_authenticated_selector_artifact(
    root_fd: int,
    relative_path: str,
    *,
    maximum: int,
) -> tuple[bytes, dict[str, int | str]]:
    try:
        contract = evidence.freeze_artifact_contract(
            root_fd,
            relative_path,
            expected_owner=os.getuid(),
            max_bytes=maximum,
        )
        with evidence.open_authenticated_artifact(root_fd, contract) as artifact:
            raw, digest, observed = evidence._hash_descriptor(
                artifact.descriptor,
                maximum=maximum,
            )
    except evidence.EvidenceContractError as exc:
        raise SelectorDeltaContractError(
            f"could not authenticate {relative_path}: {exc}"
        ) from exc
    mode = stat.S_IMODE(observed.st_mode)
    if (
        not stat.S_ISREG(observed.st_mode)
        or observed.st_uid != os.getuid()
        or observed.st_gid != os.getgid()
        or observed.st_nlink != 1
        or mode & 0o022
    ):
        _selector_delta_fail(
            f"{relative_path} must be an owned, one-link, non-writable regular file"
        )
    return raw, {
        "sha256": digest,
        "size": observed.st_size,
        "mode": mode,
        "uid": observed.st_uid,
        "gid": observed.st_gid,
        "nlink": observed.st_nlink,
    }


def _decode_selector_json(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = evidence._decode_json_bytes(
            raw,
            maximum=max(len(raw), 1),
            label=label,
        )
    except evidence.EvidenceContractError as exc:
        raise SelectorDeltaContractError(f"{label} is invalid: {exc}") from exc
    return _selector_delta_mapping(value, label)


def _require_canonical_selector_delta_bytes(
    raw: bytes, value: Mapping[str, Any]
) -> None:
    try:
        canonical = evidence._canonical_json_bytes(value)
    except evidence.EvidenceContractError as exc:
        raise SelectorDeltaContractError(
            f"selector delta cannot be canonically encoded: {exc}"
        ) from exc
    if raw != canonical:
        _selector_delta_fail("selector delta bytes are not canonical JSON")


def _validate_selector_delta_document(
    value: object,
) -> tuple[Mapping[str, Any], ...]:
    document = _selector_delta_mapping(value, "selector delta")
    _selector_delta_exact_keys(
        document,
        {
            "schemaVersion",
            "createdAt",
            "owner",
            "authorities",
            "transitionPolicy",
            "controlCatalog",
            "files",
        },
        "selector delta",
    )
    if (
        document["schemaVersion"] != SELECTOR_DELTA_SCHEMA
        or document["createdAt"] != SELECTOR_DELTA_CREATED_AT
        or not _selector_delta_json_equal(document["owner"], SELECTOR_DELTA_OWNER)
        or not _selector_delta_json_equal(
            document["authorities"], SELECTOR_DELTA_AUTHORITIES
        )
        or not _selector_delta_json_equal(
            document["transitionPolicy"], SELECTOR_DELTA_TRANSITION_POLICY
        )
        or not _selector_delta_json_equal(
            document["controlCatalog"], list(SELECTOR_DELTA_CONTROL_CATALOG)
        )
    ):
        _selector_delta_fail("selector delta frozen metadata differs")

    files = document["files"]
    if not isinstance(files, list) or len(files) != len(SELECTOR_DELTA_FILE_ORACLES):
        _selector_delta_fail("selector delta must contain exactly nine files")
    expected_files = {
        path: (legacy_sha, legacy_size, migrated_sha, migrated_size)
        for path, legacy_sha, legacy_size, migrated_sha, migrated_size
        in SELECTOR_DELTA_FILE_ORACLES
    }
    if [item.get("path") if isinstance(item, Mapping) else None for item in files] != [
        row[0] for row in SELECTOR_DELTA_FILE_ORACLES
    ]:
        _selector_delta_fail("selector delta file order or paths differ")

    observed_spans: list[tuple[str, str, tuple[str, ...]]] = []
    observed_keys: set[str] = set()
    normalized_files: list[Mapping[str, Any]] = []
    for index, raw_file in enumerate(files):
        file_record = _selector_delta_mapping(raw_file, f"selector file {index}")
        _selector_delta_exact_keys(
            file_record,
            {
                "path",
                "legacySha256",
                "legacySize",
                "migratedSha256",
                "migratedSize",
                "spans",
            },
            f"selector file {index}",
        )
        path = file_record["path"]
        if not isinstance(path, str) or path not in expected_files:
            _selector_delta_fail(f"selector file {index} path differs")
        expected = expected_files[path]
        observed_oracle = (
            file_record["legacySha256"],
            file_record["legacySize"],
            file_record["migratedSha256"],
            file_record["migratedSize"],
        )
        if not _selector_delta_json_equal(observed_oracle, expected):
            _selector_delta_fail(f"selector file oracle differs: {path}")
        spans = file_record["spans"]
        if not isinstance(spans, list) or not spans:
            _selector_delta_fail(f"selector file has no spans: {path}")
        for span_index, raw_span in enumerate(spans):
            label = f"selector span {path}:{span_index}"
            span = _selector_delta_mapping(raw_span, label)
            _selector_delta_exact_keys(
                span,
                {
                    "spanId",
                    "sessionKeys",
                    "anchorBefore",
                    "anchorBeforeSha256",
                    "anchorAfter",
                    "anchorAfterSha256",
                    "legacyStartLine",
                    "legacyEndLineExclusive",
                    "migratedStartLine",
                    "migratedEndLineExclusive",
                    "legacyText",
                    "legacySha256",
                    "migratedText",
                    "migratedSha256",
                },
                label,
            )
            session_keys = span["sessionKeys"]
            if not isinstance(span["spanId"], str) or not isinstance(
                session_keys, list
            ) or not session_keys or not all(
                isinstance(key, str) for key in session_keys
            ):
                _selector_delta_fail(f"{label} identity differs")
            if len(session_keys) != len(set(session_keys)):
                _selector_delta_fail(f"{label} repeats a session key")
            observed_spans.append((span["spanId"], path, tuple(session_keys)))
            observed_keys.update(session_keys)
            for prefix in ("anchorBefore", "anchorAfter", "legacy", "migrated"):
                text_key = f"{prefix}Text" if prefix in {"legacy", "migrated"} else prefix
                hash_key = f"{prefix}Sha256"
                text = span[text_key]
                if (
                    not isinstance(text, str)
                    or not text
                    or _selector_delta_sha256(text.encode("utf-8")) != span[hash_key]
                ):
                    _selector_delta_fail(f"{label} {prefix} bytes differ")
            for state in ("legacy", "migrated"):
                start = span[f"{state}StartLine"]
                end = span[f"{state}EndLineExclusive"]
                if (
                    not isinstance(start, int)
                    or isinstance(start, bool)
                    or not isinstance(end, int)
                    or isinstance(end, bool)
                    or start < 1
                    or end <= start
                ):
                    _selector_delta_fail(f"{label} {state} line range differs")
        normalized_files.append(file_record)

    if tuple(observed_spans) != SELECTOR_DELTA_SPAN_CATALOG:
        _selector_delta_fail("selector delta 11-span catalog differs")
    if observed_keys != set(SELECTOR_DELTA_CONTROL_CATALOG):
        _selector_delta_fail("selector delta session-key union differs")
    return tuple(normalized_files)


def _transform_selector_delta_file(
    file_record: Mapping[str, Any], raw: bytes
) -> tuple[str, bytes]:
    digest = _selector_delta_sha256(raw)
    if (
        digest == file_record["legacySha256"]
        and len(raw) == file_record["legacySize"]
    ):
        state, other = "legacy", "migrated"
    elif (
        digest == file_record["migratedSha256"]
        and len(raw) == file_record["migratedSize"]
    ):
        state, other = "migrated", "legacy"
    else:
        _selector_delta_fail(f"unknown whole-file state: {file_record['path']}")

    replacements: list[tuple[int, int, bytes]] = []
    for span in file_record["spans"]:
        before = span["anchorBefore"].encode("utf-8")
        after = span["anchorAfter"].encode("utf-8")
        active = span[f"{state}Text"].encode("utf-8")
        replacement = span[f"{other}Text"].encode("utf-8")
        sequence = before + active + after
        if raw.count(before) != 1 or raw.count(after) != 1 or raw.count(sequence) != 1:
            _selector_delta_fail(
                f"{file_record['path']}:{span['spanId']} anchor or span differs"
            )
        sequence_start = raw.index(sequence)
        start = sequence_start + len(before)
        end = start + len(active)
        if raw[start:end] != active:
            _selector_delta_fail(
                f"{file_record['path']}:{span['spanId']} active bytes differ"
            )
        start_line = raw[:start].count(b"\n") + 1
        end_line = raw[:end].count(b"\n") + 1
        if (
            start_line != span[f"{state}StartLine"]
            or end_line != span[f"{state}EndLineExclusive"]
        ):
            _selector_delta_fail(
                f"{file_record['path']}:{span['spanId']} line coordinates differ"
            )
        replacements.append((start, end, replacement))

    ordered = sorted(replacements)
    if any(first[1] > second[0] for first, second in zip(ordered, ordered[1:])):
        _selector_delta_fail(f"overlapping selector spans: {file_record['path']}")
    projected = raw
    for start, end, replacement in reversed(ordered):
        projected = projected[:start] + replacement + projected[end:]
    if (
        _selector_delta_sha256(projected) != file_record[f"{other}Sha256"]
        or len(projected) != file_record[f"{other}Size"]
    ):
        _selector_delta_fail(
            f"selector projection does not reconstruct {other}: {file_record['path']}"
        )
    return state, projected


def _validate_selector_delta_workspace(
    document: object,
    live_files: Mapping[str, bytes],
) -> tuple[str, dict[str, bytes]]:
    files = _validate_selector_delta_document(document)
    expected_paths = {record["path"] for record in files}
    if set(live_files) != expected_paths:
        _selector_delta_fail("selector workspace paths differ")
    states: set[str] = set()
    projected: dict[str, bytes] = {}
    for file_record in files:
        path = file_record["path"]
        raw = live_files[path]
        if not isinstance(raw, bytes):
            _selector_delta_fail(f"selector workspace value is not bytes: {path}")
        state, opposite = _transform_selector_delta_file(file_record, raw)
        reverse_state, roundtrip = _transform_selector_delta_file(
            file_record, opposite
        )
        if reverse_state == state or roundtrip != raw:
            _selector_delta_fail(f"selector delta is not bidirectional: {path}")
        states.add(state)
        projected[path] = opposite
    if len(states) != 1:
        _selector_delta_fail(f"mixed selector workspace state: {sorted(states)}")
    state = next(iter(states))
    return f"all-{state}", projected


def _validate_selector_delta_pointer(
    rollback_value: object,
    delta_identity: Mapping[str, int | str],
) -> None:
    rollback = _selector_delta_mapping(rollback_value, "recovery rollback")
    production = _selector_delta_mapping(
        rollback.get("productionRollback"), "production rollback"
    )
    expected_paths = [row[0] for row in SELECTOR_DELTA_FILE_ORACLES]
    expected_pointer = {
        "schemaVersion": SELECTOR_DELTA_SCHEMA,
        "path": SELECTOR_DELTA_PATH.as_posix(),
        "sha256": SELECTOR_DELTA_SHA256,
        "size": SELECTOR_DELTA_SIZE,
        "uid": SELECTOR_DELTA_OWNER["uid"],
        "gid": SELECTOR_DELTA_OWNER["gid"],
        "mode": 0o600,
        "nlink": 1,
    }
    if not _selector_delta_json_equal(production.get("allowedFiles"), expected_paths):
        _selector_delta_fail("recovery rollback allowed files differ")
    if not _selector_delta_json_equal(
        production.get("postimages"), expected_pointer
    ):
        _selector_delta_fail("recovery rollback selector-delta pointer differs")
    if dict(delta_identity) != {
        key: expected_pointer[key]
        for key in ("sha256", "size", "uid", "gid", "mode", "nlink")
    }:
        _selector_delta_fail("selector delta descriptor identity differs")


def _authenticated_selector_delta_inputs() -> tuple[
    Mapping[str, Any],
    dict[str, bytes],
    dict[str, bytes],
    Mapping[str, Any],
    dict[str, int | str],
]:
    root_fd = os.open(ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        delta_raw, delta_identity = _read_authenticated_selector_artifact(
            root_fd,
            SELECTOR_DELTA_PATH.as_posix(),
            maximum=SELECTOR_DELTA_MAX_BYTES,
        )
        if (
            len(delta_raw) != SELECTOR_DELTA_SIZE
            or _selector_delta_sha256(delta_raw) != SELECTOR_DELTA_SHA256
        ):
            _selector_delta_fail("selector delta fixed identity differs")
        document = _decode_selector_json(delta_raw, "selector delta")
        _require_canonical_selector_delta_bytes(delta_raw, document)
        _validate_selector_delta_document(document)

        authority_raw: dict[str, bytes] = {}
        for name, pointer in SELECTOR_DELTA_AUTHORITIES.items():
            raw, identity = _read_authenticated_selector_artifact(
                root_fd,
                str(pointer["path"]),
                maximum=int(pointer["size"]),
            )
            expected_identity = {
                key: pointer[key]
                for key in ("sha256", "size", "mode", "uid", "gid", "nlink")
                if key in pointer
            }
            observed_identity = {
                key: identity[key]
                for key in expected_identity
            }
            if observed_identity != expected_identity:
                _selector_delta_fail(f"selector delta authority differs: {name}")
            authority_raw[name] = raw

        prechange = _decode_selector_json(
            authority_raw["prechangeContract"], "prechange contract"
        )
        rows = prechange.get("productionSelectorFiles")
        if not isinstance(rows, list):
            _selector_delta_fail("prechange selector oracle is missing")
        legacy_oracle = {
            row.get("path"): row.get("sha256")
            for row in rows
            if isinstance(row, Mapping)
        }
        expected_legacy = {
            path: legacy_sha
            for path, legacy_sha, _legacy_size, _migrated_sha, _migrated_size
            in SELECTOR_DELTA_FILE_ORACLES
        }
        if legacy_oracle != expected_legacy:
            _selector_delta_fail("prechange selector hashes differ")

        manifest = _decode_selector_json(
            authority_raw["prechangeManifest"], "prechange bundle manifest"
        )
        archive_pointer = SELECTOR_DELTA_AUTHORITIES["prechangeArchive"]
        if not _selector_delta_json_equal(
            manifest.get("owner"), SELECTOR_DELTA_OWNER
        ) or not _selector_delta_json_equal(
            manifest.get("archive"),
            {
                "path": Path(str(archive_pointer["path"])).name,
                "sha256": archive_pointer["sha256"],
                "size": archive_pointer["size"],
                "mode": "0600",
            },
        ):
            _selector_delta_fail("prechange bundle manifest binding differs")

        legacy_files: dict[str, bytes] = {}
        archive_buffer = io.BytesIO(authority_raw["prechangeArchive"])
        with tarfile.open(fileobj=archive_buffer, mode="r:") as bundle:
            members = bundle.getmembers()
            for path, legacy_sha, legacy_size, _migrated_sha, _migrated_size in (
                SELECTOR_DELTA_FILE_ORACLES
            ):
                matching = [member for member in members if member.name == path]
                if len(matching) != 1 or not matching[0].isfile():
                    _selector_delta_fail(f"prechange archive member differs: {path}")
                extracted = bundle.extractfile(matching[0])
                if extracted is None:
                    _selector_delta_fail(f"prechange archive member unreadable: {path}")
                raw = extracted.read()
                if len(raw) != legacy_size or _selector_delta_sha256(raw) != legacy_sha:
                    _selector_delta_fail(f"prechange archive bytes differ: {path}")
                legacy_files[path] = raw

        live_files: dict[str, bytes] = {}
        for path, _legacy_sha, _legacy_size, _migrated_sha, migrated_size in (
            SELECTOR_DELTA_FILE_ORACLES
        ):
            raw, _identity = _read_authenticated_selector_artifact(
                root_fd,
                path,
                maximum=max(migrated_size, 128 * 1024),
            )
            live_files[path] = raw

        rollback_raw, _rollback_identity = _read_authenticated_selector_artifact(
            root_fd,
            RECOVERY_ROLLBACK_PATH.as_posix(),
            maximum=128 * 1024,
        )
        rollback = _decode_selector_json(rollback_raw, "recovery rollback")
    finally:
        os.close(root_fd)
    return document, live_files, legacy_files, rollback, delta_identity


def _requires_selector_delta_error(action: Callable[[], object]) -> None:
    try:
        action()
    except SelectorDeltaContractError:
        return
    raise AssertionError("selector delta mutation did not fail closed")


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def _key_value(node: ast.AST, constants: Mapping[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                pieces.append("{}")
            else:
                return None
        return "".join(pieces)
    return None


def _legacy_inventory() -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    paths = (ROOT / "app.py", *(ROOT / "ui").rglob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constants = _module_constants(tree)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "segmented_control"
            ):
                continue
            key_node = next(
                (item.value for item in node.keywords if item.arg == "key"), None
            )
            key = _key_value(key_node, constants) if key_node is not None else None
            if key is None:
                raise AssertionError(
                    f"unresolved segmented_control key at {path.relative_to(ROOT)}:{node.lineno}"
                )
            found.append((path.relative_to(ROOT).as_posix(), key))
    return tuple(sorted(found))


def _selector(key: str) -> SelectorContract:
    return next(item for item in SELECTORS if item.key == key)


def _seed(key: str, value: Any) -> dict[str, Any]:
    return {} if value is MISSING else {key: value}


def _state_cases(contract: SelectorContract) -> tuple[tuple[Any, str], ...]:
    return (
        (MISSING, contract.default),
        (None, contract.default),
        ("__stale_selector_value__", contract.default),
        *((option, option) for option in contract.options),
    )


def _calls_for(fake: FakeStreamlit, key: str) -> list[dict[str, Any]]:
    return [row for row in fake.widget_calls if row["key"] == key]


def _assert_state_matrix(
    contract: SelectorContract,
    runner: Callable[[Any], FakeStreamlit],
    *,
    postcheck: Callable[[FakeStreamlit, str], Sequence[str]] | None = None,
) -> None:
    migration_deltas: list[str] = []
    blocking_errors: list[str] = []
    runtime_key = (
        "cockpit_price_view_NVDA"
        if contract.key == "cockpit_price_view_{}"
        else contract.key
    )
    for supplied, expected in _state_cases(contract):
        label = "missing" if supplied is MISSING else repr(supplied)
        try:
            fake = runner(supplied)
            calls = _calls_for(fake, runtime_key)
            if len(calls) != 1:
                blocking_errors.append(f"{label}: widget calls={calls!r}")
                continue
            call = calls[0]
            legacy = call["method"] == "segmented_control"

            def migration_or_blocking(message: str) -> None:
                target = migration_deltas if legacy else blocking_errors
                target.append(f"{label}: {message}")

            observed = fake.session_state.get(runtime_key, MISSING)
            if observed != expected:
                migration_or_blocking(
                    f"state={observed!r}, expected={expected!r}"
                )
            if call["selected"] != expected:
                migration_or_blocking(
                    f"selected={call['selected']!r}, expected={expected!r}"
                )
            if call["method"] != contract.replacement:
                migration_or_blocking(
                    f"widget={call['method']}, expected={contract.replacement}"
                )
            if call["options"] != contract.options:
                blocking_errors.append(f"{label}: options={call['options']!r}")
            if call["label"] != contract.label:
                blocking_errors.append(f"{label}: widget label={call['label']!r}")
            if call["kwargs"].get("label_visibility") != contract.label_visibility:
                blocking_errors.append(
                    f"{label}: label_visibility="
                    f"{call['kwargs'].get('label_visibility')!r}"
                )
            if call["kwargs"].get("help") != contract.help_text:
                blocking_errors.append(
                    f"{label}: help={call['kwargs'].get('help')!r}"
                )
            allowed_kwargs = {"label_visibility", "help"}
            if contract.replacement == "radio":
                allowed_kwargs.add("horizontal")
            extras = sorted(set(call["kwargs"]) - allowed_kwargs)
            if extras:
                blocking_errors.append(f"{label}: unsupported kwargs={extras!r}")
            if contract.replacement == "radio":
                if call["index"] is not None:
                    migration_or_blocking("radio index must be None")
                if call["kwargs"].get("horizontal") is not True:
                    migration_or_blocking("radio must be horizontal")
            elif call["index"] is not None:
                migration_or_blocking("selectbox index must be None")
            if postcheck is not None:
                for message in postcheck(fake, expected):
                    migration_or_blocking(message)
        except Exception as exc:  # noqa: BLE001 - classify, never bless implicitly
            blocking_errors.append(f"{label}: {type(exc).__name__}: {exc}")
    if blocking_errors:
        raise AssertionError(
            f"{runtime_key}: blocking: " + "; ".join(blocking_errors)
        )
    if migration_deltas:
        raise ExpectedMigrationDelta(
            f"{runtime_key}: " + "; ".join(migration_deltas),
            category="selector",
            items=(runtime_key,),
        )


def _run_risk_guard(value: Any) -> FakeStreamlit:
    contract = _selector("rg_source")
    fake = FakeStreamlit(_seed(contract.key, value))
    with (
        patch.object(risk_guard, "st", fake),
        patch.object(risk_guard, "_collect", return_value=(["NVDA"], False)),
        patch.object(risk_guard, "_load_scheduled_risk_snapshot", return_value=None),
    ):
        risk_guard.render()
    return fake


def _run_institutions(value: Any) -> FakeStreamlit:
    contract = _selector("inst_view")
    fake = FakeStreamlit(_seed(contract.key, value))
    calls: list[str] = []
    class Views(dict[str, Callable[..., None]]):
        def __missing__(self, _key: str) -> Callable[..., None]:
            return lambda **_kwargs: None

    views = Views(
        {
            contract.options[0]: lambda **_kwargs: calls.append(contract.options[0]),
            contract.options[1]: lambda **_kwargs: calls.append(contract.options[1]),
        }
    )
    with patch.object(institutions, "st", fake), patch.object(
        institutions, "_VIEWS", views
    ):
        institutions.render()
    fake.provider_calls = calls  # type: ignore[attr-defined]
    return fake


def _run_options(value: Any, *, ticker: str = "NVDA") -> FakeStreamlit:
    key = f"cockpit_price_view_{ticker}"
    fake = FakeStreamlit(_seed(key, value))
    calls: list[tuple[str, str]] = []
    data = SimpleNamespace(ticker=ticker)
    with (
        patch.object(options_cockpit, "st", fake),
        patch.object(
            options_cockpit,
            "_price_fig",
            side_effect=lambda _data: calls.append(("snapshot", ticker)) or "snapshot",
        ),
        patch.object(
            options_cockpit._shared,
            "tradingview_chart",
            side_effect=lambda selected, **_kwargs: calls.append(
                ("interactive", selected)
            ),
        ),
    ):
        options_cockpit._render_price_chart(data)
    fake.branch_calls = calls  # type: ignore[attr-defined]
    return fake


def _run_radar_source(value: Any) -> FakeStreamlit:
    contract = _selector("radar_source")
    state = _seed(contract.key, value)
    state["radar_manual"] = "NVDA"
    fake = FakeStreamlit(state)
    with patch.object(radar, "st", fake), patch.object(
        radar, "_collect", return_value=(["NVDA"], False)
    ):
        radar._render_dual_read()
    return fake


def _radar_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "代號": "BOTH",
                "風險": "🔴 EXIT",
                "風險分": 90,
                "反轉": "🟢 REVERSAL",
                "反轉分": 80,
                "信心": 0.9,
                "搶在COT前": "✅",
                "共現": "🔴",
                "主要訊號": "x",
                "_rrank": 4,
                "_vrank": 4,
                "_conf": 1,
            },
            {
                "代號": "RISK",
                "風險": "🟠 REDUCE",
                "風險分": 70,
                "反轉": "— NORMAL",
                "反轉分": 10,
                "信心": 0.8,
                "搶在COT前": "",
                "共現": "",
                "主要訊號": "y",
                "_rrank": 3,
                "_vrank": 0,
                "_conf": 0,
            },
            {
                "代號": "REV",
                "風險": "🟢 NORMAL",
                "風險分": 10,
                "反轉": "🟡 TURNING",
                "反轉分": 60,
                "信心": 0.7,
                "搶在COT前": "",
                "共現": "",
                "主要訊號": "z",
                "_rrank": 0,
                "_vrank": 3,
                "_conf": 0,
            },
        ]
    )


def _run_radar_view(value: Any) -> FakeStreamlit:
    contract = _selector("radar_view")
    state = {
        "radar_source": "手動輸入",
        "radar_manual": "NVDA",
        "radar_inc_pos": False,
        "radar_risk": {"summary": {}, "rows": []},
        "radar_rev": {"summary": {}, "rows": []},
        "radar_run_key": ("手動輸入", ("NVDA",), False),
        **_seed(contract.key, value),
    }
    fake = FakeStreamlit(state)
    rendered: list[str] = []
    with (
        patch.object(radar, "st", fake),
        patch.object(radar, "_collect", return_value=(["NVDA"], False)),
        patch.object(radar, "_dual_df", return_value=_radar_frame()),
        patch.object(radar._shared, "metric_card", return_value=None),
        patch.object(
            radar,
            "_render_table",
            side_effect=lambda _df, selected: rendered.append(selected),
        ),
        patch.object(radar, "_render_detail", return_value=None),
        patch.object(radar.rgui, "_tab_portfolio", return_value=None),
        patch.object(radar, "_render_sources", return_value=None),
    ):
        radar._render_dual_read()
    fake.branch_calls = rendered  # type: ignore[attr-defined]
    return fake


def _graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "factor-a",
                "type": "factor",
                "dimension": "Dim1",
                "status": "validated",
                "label": "Factor A",
                "blocked": False,
                "horizon": "",
                "lift_exploratory": None,
                "runway_verdict": "",
                "verdict_raw": "VALIDATED",
            }
        ],
        "edges": [],
        "diagnostics": {"unresolved_links": [], "duplicate_ids": []},
    }


def _run_knowledge_graph(
    key: str, value: Any, *, other: str | None = None
) -> FakeStreamlit:
    state = _seed(key, value)
    if key == "kg_view_mode":
        state["kg_label_mode"] = other or "核心"
    else:
        state["kg_view_mode"] = other or "星雲圖"
    fake = FakeStreamlit(state)
    calls: list[tuple[str, Any]] = []
    graph = _graph()
    with (
        patch.object(knowledge_graph, "st", fake),
        patch.object(
            knowledge_graph,
            "_load_graph",
            return_value=graph,
        ),
        patch.object(
            knowledge_graph,
            "_filtered_graph",
            return_value=(graph["nodes"], graph["edges"]),
        ),
        patch.object(
            knowledge_graph,
            "_nebula_figure",
            side_effect=lambda _nodes, _edges, label, _opacity, _focus: calls.append(
                ("nebula", label)
            )
            or "nebula",
        ),
        patch.object(
            knowledge_graph,
            "_figure",
            side_effect=lambda _nodes, _edges: calls.append(("lanes", None))
            or "lanes",
        ),
        patch.object(knowledge_graph, "_node_table", return_value=pd.DataFrame()),
        patch.object(knowledge_graph._shared, "metric_card", return_value=None),
        patch.object(knowledge_graph._shared, "chips_row", return_value=None),
    ):
        knowledge_graph.render()
    fake.branch_calls = calls  # type: ignore[attr-defined]
    return fake


def _run_ai(value: Any) -> FakeStreamlit:
    contract = _selector("ai_chat_mode")
    fake = FakeStreamlit(_seed(contract.key, value))
    with (
        patch.object(ai_chat, "st", fake),
        patch.object(ai_chat, "_render_queued_event", return_value=None),
        patch.object(ai_chat, "_render_messages", return_value=None),
        patch.object(ai_chat, "_save_if_needed", return_value=True),
        patch.object(ai_chat, "_render_context_controls", return_value=None),
        patch.object(ai_chat, "_render_history", return_value=None),
    ):
        ai_chat._init_state()
        ai_chat._render_panel(Path("/owned/chat"))
    return fake


def _run_retro(value: Any) -> FakeStreamlit:
    contract = _selector("retro_validation_lane")
    fake = FakeStreamlit(_seed(contract.key, value))
    calls: list[str] = []
    with (
        patch.object(retro_analysis, "st", fake),
        patch.object(retro_analysis, "_dataset_options", return_value=[]),
        patch.object(retro_analysis, "_load", return_value={}),
        patch.object(
            retro_analysis.continuation_validation,
            "render",
            side_effect=lambda: calls.append("continuation"),
        ),
        patch.object(
            retro_analysis.playbook_validation,
            "render",
            side_effect=lambda: calls.append("playbook"),
        ),
    ):
        retro_analysis.render()
    fake.branch_calls = calls  # type: ignore[attr-defined]
    return fake


def _run_analytics(
    value: Any,
    *,
    catalog: Any = MISSING,
) -> FakeStreamlit:
    contract = _selector("adb_table")
    fake = FakeStreamlit(_seed(contract.key, value))
    rows = (
        [
            {"table_name": "candidate_rankings"},
            {"table_name": "iv_history"},
        ]
        if catalog is MISSING
        else catalog
    )
    calls: list[tuple[str, str]] = []
    with (
        patch.object(analytics_db, "st", fake),
        patch.object(
            analytics_db,
            "_columns",
            side_effect=lambda _root, table: calls.append(("columns", table))
            or ["ticker", "as_of_date"],
        ),
        patch.object(analytics_db, "_tickers", return_value=[]),
        patch.object(
            analytics_db,
            "_fetch_table",
            side_effect=lambda _root, table, *_args: calls.append(("fetch", table))
            or pd.DataFrame(),
        ),
    ):
        analytics_db._table_browser("/owned/analytics", rows)
    fake.branch_calls = calls  # type: ignore[attr-defined]
    return fake


def _run_stock(value: Any, *, handoff: str | None = None) -> FakeStreamlit:
    contract = _selector("checkup_mode")
    state = _seed(contract.key, value)
    state["checkup_ticker_input"] = "NVDA"
    if handoff is not None:
        state["checkup_handoff"] = handoff
    fake = FakeStreamlit(state)
    calls: list[tuple[str, str | None]] = []
    with (
        patch.object(stock_checkup, "st", fake),
        patch.object(
            stock_checkup,
            "_render_single",
            side_effect=lambda ticker: calls.append(("single", ticker)),
        ),
        patch.object(
            stock_checkup,
            "_render_batch",
            side_effect=lambda: calls.append(("batch", None)),
        ),
    ):
        stock_checkup.render()
    fake.branch_calls = calls  # type: ignore[attr-defined]
    return fake


def _valid_control_evidence(identity: Mapping[str, Any]) -> dict[str, Any]:
    contracts = {
        row["case"]: row["controls"] for row in evidence.focused_control_contract_rows()
    }[str(identity["case"])]
    viewport_width = int(identity["viewport"]["width"])
    viewport_height = int(identity["viewport"]["height"])
    root_width = viewport_width - 40
    controls: list[dict[str, Any]] = []
    for contract in contracts:
        options = list(contract["optionLabels"])
        selected = str(contract["selectedLabel"])
        replacement = str(contract["replacementWidget"])
        target_labels = [selected] if replacement == "selectbox" else options
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
        if replacement == "radio_horizontal":
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
        controls.append(
            {
                "sessionKey": contract["sessionKey"],
                "rootSelector": contract["rootSelector"],
                "widget": replacement,
                "accessibleName": contract["accessibleName"],
                "optionLabels": options,
                "auxiliaryButtons": list(contract["auxiliaryButtons"]),
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
                    "targetOverlapTolerance": 0.5,
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
        "case": identity["case"],
        "projection": "accessible-required",
        "controls": controls,
    }


def _requires_contract_error(
    candidate: dict[str, Any], identity: Mapping[str, Any]
) -> None:
    try:
        evidence._validate_focused_control_evidence(
            candidate,
            expected_case=str(identity["case"]),
            expected_viewport=identity["viewport"],
        )
    except evidence.EvidenceContractError:
        return
    raise AssertionError("trusted AX validator accepted a forged projection")


def test_capture_stack_and_trusted_ax_preflight() -> None:
    if (
        _sha256(ROOT / LEGACY_CAPTURE_STACK_PATH)
        != LEGACY_CAPTURE_STACK_SHA256
    ):
        raise AssertionError("legacy capture-stack SHA changed")
    if _sha256(ROOT / CAPTURE_STACK_PATH) != CAPTURE_STACK_SHA256:
        raise AssertionError("Sequence 13 capture-stack SHA changed")
    if (
        _sha256(ROOT / SEQUENCE12_CAPTURE_STACK_PATH)
        != SEQUENCE12_CAPTURE_STACK_SHA256
    ):
        raise AssertionError("Sequence 12 capture-stack history changed")
    contract = json.loads((ROOT / CAPTURE_STACK_PATH).read_text(encoding="utf-8"))
    members = contract.get("members")
    if not isinstance(members, list) or len(members) != 9:
        raise AssertionError("capture stack must contain exactly nine members")
    for member in members:
        path = ROOT / str(member["path"])
        stat = path.stat()
        if (
            not path.is_file()
            or stat.st_size != member["size"]
            or (stat.st_mode & 0o777) != member["mode"]
            or _sha256(path) != member["sha256"]
        ):
            raise AssertionError(f"capture-stack member drift: {member['path']}")
    worker_rows = browser_worker.worker_control_contract_rows()
    trusted_rows = evidence.focused_control_contract_rows()
    if worker_rows != trusted_rows:
        raise AssertionError("worker/trusted AX catalogs differ")
    controls = [control for row in trusted_rows for control in row["controls"]]
    if (
        len(trusted_rows) != 9
        or len(controls) != 11
        or len({control["sessionKey"] for control in controls}) != 11
        or sum(control["replacementWidget"] == "radio_horizontal" for control in controls)
        != 10
        or sum(control["replacementWidget"] == "selectbox" for control in controls)
        != 1
    ):
        raise AssertionError("trusted AX catalog shape differs")
    expected_catalog = {
        (
            "cockpit_price_view_NVDA"
            if contract.key == "cockpit_price_view_{}"
            else contract.key
        ): {
            "accessibleName": contract.label,
            "optionLabels": contract.options,
            "replacementWidget": (
                "radio_horizontal"
                if contract.replacement == "radio"
                else "selectbox"
            ),
        }
        for contract in SELECTORS
    }
    observed_catalog = {
        control["sessionKey"]: {
            "accessibleName": control["accessibleName"],
            "optionLabels": tuple(control["optionLabels"]),
            "replacementWidget": control["replacementWidget"],
        }
        for control in controls
    }
    if observed_catalog != expected_catalog:
        raise AssertionError("selector and trusted AX contracts differ")


def test_selector_delta_contract_and_uniform_workspace() -> None:
    document, live_files, legacy_files, rollback, delta_identity = (
        _authenticated_selector_delta_inputs()
    )
    _validate_selector_delta_pointer(rollback, delta_identity)

    legacy_state, migrated_files = _validate_selector_delta_workspace(
        document, legacy_files
    )
    migrated_state, roundtrip_legacy = _validate_selector_delta_workspace(
        document, migrated_files
    )
    if (
        legacy_state != "all-legacy"
        or migrated_state != "all-migrated"
        or roundtrip_legacy != legacy_files
    ):
        raise AssertionError("selector delta bidirectional oracle differs")

    live_state, projected_live = _validate_selector_delta_workspace(
        document, live_files
    )
    expected_live = legacy_files if live_state == "all-legacy" else migrated_files
    expected_projection = (
        migrated_files if live_state == "all-legacy" else legacy_files
    )
    if live_files != expected_live or projected_live != expected_projection:
        raise AssertionError("live selector workspace does not equal a frozen state")


def test_selector_delta_rejects_contract_mutations() -> None:
    document, live_files, _legacy_files, rollback, delta_identity = (
        _authenticated_selector_delta_inputs()
    )
    _validate_selector_delta_pointer(rollback, delta_identity)
    _live_state, opposite_files = _validate_selector_delta_workspace(
        document, live_files
    )

    canonical_raw = evidence._canonical_json_bytes(document)
    _requires_selector_delta_error(
        lambda: _require_canonical_selector_delta_bytes(
            canonical_raw + b"\n", document
        )
    )

    extra_root = copy.deepcopy(document)
    extra_root["unexpected"] = True
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(extra_root)
    )

    numeric_boolean = copy.deepcopy(document)
    numeric_boolean["transitionPolicy"]["wholeFileReplacementAllowed"] = 0
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(numeric_boolean)
    )

    boolean_integer = copy.deepcopy(document)
    boolean_integer["authorities"]["prechangeArchive"]["nlink"] = True
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(boolean_integer)
    )

    missing_file = copy.deepcopy(document)
    missing_file["files"].pop()
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(missing_file)
    )

    whole_hash = copy.deepcopy(document)
    whole_hash["files"][0]["migratedSha256"] = "0" * 64
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(whole_hash)
    )

    duplicate_span = copy.deepcopy(document)
    duplicate_span["files"][1]["spans"][1]["spanId"] = (
        duplicate_span["files"][1]["spans"][0]["spanId"]
    )
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_document(duplicate_span)
    )

    changed_span = copy.deepcopy(document)
    span = changed_span["files"][0]["spans"][0]
    span["migratedText"] += " "
    span["migratedSha256"] = _selector_delta_sha256(
        span["migratedText"].encode("utf-8")
    )
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_workspace(changed_span, live_files)
    )

    changed_anchor = copy.deepcopy(document)
    span = changed_anchor["files"][0]["spans"][0]
    span["anchorBefore"] += " "
    span["anchorBeforeSha256"] = _selector_delta_sha256(
        span["anchorBefore"].encode("utf-8")
    )
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_workspace(changed_anchor, live_files)
    )

    wrong_line = copy.deepcopy(document)
    wrong_line["files"][0]["spans"][0]["migratedStartLine"] += 1
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_workspace(wrong_line, live_files)
    )

    corrupt_file = dict(live_files)
    first_path = SELECTOR_DELTA_FILE_ORACLES[0][0]
    corrupt_file[first_path] = b"!" + corrupt_file[first_path][1:]
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_workspace(document, corrupt_file)
    )

    mixed_files = dict(live_files)
    mixed_files[first_path] = opposite_files[first_path]
    _requires_selector_delta_error(
        lambda: _validate_selector_delta_workspace(document, mixed_files)
    )

    for key, replacement in (
        ("path", "docs/ui-ux/forged-selector-delta.json"),
        ("sha256", "f" * 64),
        ("size", SELECTOR_DELTA_SIZE + 1),
        ("nlink", True),
    ):
        forged_rollback = copy.deepcopy(rollback)
        forged_rollback["productionRollback"]["postimages"][key] = replacement
        _requires_selector_delta_error(
            lambda candidate=forged_rollback: _validate_selector_delta_pointer(
                candidate, delta_identity
            )
        )


def test_trusted_ax_keyboard_target_and_layout_rejection() -> None:
    profiles = evidence.worker_capture_profile_rows(
        "scripts/ui_ux_selection_fixture_app.py"
    )
    identities = [
        next(
            row
            for row in profiles
            if row["case"] == case and row["viewport"]["name"] == "narrow"
        )
        for case in ("knowledge-graph-controls", "analytics-controls")
    ]
    for identity in identities:
        valid = _valid_control_evidence(identity)
        normalized = evidence._validate_focused_control_evidence(
            valid,
            expected_case=identity["case"],
            expected_viewport=identity["viewport"],
        )
        if normalized != valid:
            raise AssertionError("valid trusted AX projection was not canonical")

        mutations: list[Callable[[dict[str, Any]], None]] = [
            lambda value: value["controls"][0].__setitem__("accessibleName", "forged"),
            lambda value: value["controls"][0]["optionLabels"].reverse(),
            lambda value: value["controls"][0]["targets"][0].__setitem__(
                "height", 23.999
            ),
            lambda value: value["controls"][0]["targets"][0].__setitem__(
                "width", 23.999
            ),
            lambda value: value["controls"][0]["layout"].__setitem__(
                "rootClipping", True
            ),
            lambda value: value["controls"][0]["layout"].__setitem__(
                "targetClipping", True
            ),
            lambda value: value["controls"][0]["layout"].__setitem__(
                "targetOverlap", True
            ),
            lambda value: value["controls"][0]["layout"].__setitem__(
                "documentHorizontalOverflow", True
            ),
            lambda value: value["controls"][0]["layout"].__setitem__(
                "rootHorizontalOverflow", True
            ),
        ]
        if identity["case"] == "knowledge-graph-controls":
            mutations.extend(
                (
                    lambda value: value["controls"][0]["checkedLabels"].append(
                        "驗證泳道"
                    ),
                    lambda value: value["controls"][0]["tabSequenceLabels"].append(
                        "驗證泳道"
                    ),
                    lambda value: value["controls"][0].__setitem__(
                        "afterArrowRight", "星雲圖"
                    ),
                    lambda value: value["controls"][0].__setitem__(
                        "afterArrowLeft", "驗證泳道"
                    ),
                    lambda value: value["controls"][0].__setitem__(
                        "afterSpace", None
                    ),
                )
            )
        else:
            mutations.extend(
                (
                    lambda value: value["controls"][0].__setitem__(
                        "afterArrowDown", "candidate_rankings"
                    ),
                    lambda value: value["controls"][0].__setitem__(
                        "afterArrowUp", "iv_history"
                    ),
                )
            )
        for mutate in mutations:
            candidate = copy.deepcopy(valid)
            mutate(candidate)
            _requires_contract_error(candidate, identity)


def test_ast_requires_zero_segmented_controls() -> None:
    observed = _legacy_inventory()
    unexpected = sorted(set(observed) - set(EXPECTED_LEGACY))
    if unexpected:
        raise AssertionError(f"unreviewed segmented controls: {unexpected}")
    if observed:
        raise ExpectedMigrationDelta(
            f"legacy segmented controls remain ({len(observed)}/11): {observed}",
            category="selector",
            items=tuple(key for _path, key in observed),
        )
    raw_tokens = []
    for path in (ROOT / "app.py", *(ROOT / "ui").rglob("*.py")):
        count = path.read_text(encoding="utf-8").count("segmented_control")
        if count:
            raw_tokens.append((path.relative_to(ROOT).as_posix(), count))
    if raw_tokens:
        raise AssertionError(f"raw segmented_control tokens remain: {raw_tokens}")


def test_migrated_risk_guard_state_contract() -> None:
    _assert_state_matrix(_selector("rg_source"), _run_risk_guard)


def test_migrated_institutions_state_contract() -> None:
    _assert_state_matrix(_selector("inst_view"), _run_institutions)


def test_migrated_options_state_contract() -> None:
    _assert_state_matrix(_selector("cockpit_price_view_{}"), _run_options)


def test_migrated_radar_source_state_contract() -> None:
    _assert_state_matrix(_selector("radar_source"), _run_radar_source)


def test_migrated_radar_view_state_contract() -> None:
    _assert_state_matrix(_selector("radar_view"), _run_radar_view)


def test_migrated_knowledge_graph_view_state_contract() -> None:
    _assert_state_matrix(
        _selector("kg_view_mode"),
        lambda value: _run_knowledge_graph("kg_view_mode", value),
    )


def test_migrated_knowledge_graph_label_state_contract() -> None:
    _assert_state_matrix(
        _selector("kg_label_mode"),
        lambda value: _run_knowledge_graph("kg_label_mode", value),
    )


def test_migrated_ai_chat_state_contract() -> None:
    _assert_state_matrix(_selector("ai_chat_mode"), _run_ai)


def test_migrated_retro_state_contract() -> None:
    _assert_state_matrix(_selector("retro_validation_lane"), _run_retro)


def test_migrated_analytics_state_contract() -> None:
    def query_path(fake: FakeStreamlit, expected: str) -> Sequence[str]:
        wanted = [("columns", expected), ("fetch", expected)]
        observed = getattr(fake, "branch_calls", [])
        return () if observed == wanted else (f"query path={observed!r}, expected={wanted!r}",)

    _assert_state_matrix(
        _selector("adb_table"),
        _run_analytics,
        postcheck=query_path,
    )


def test_analytics_missing_and_empty_catalog_fail_soft() -> None:
    errors: list[str] = []
    for name, catalog in (("missing-mapping", {}), ("empty-list", [])):
        try:
            fake = _run_analytics(MISSING, catalog=catalog)
            if _calls_for(fake, "adb_table"):
                errors.append(f"{name}: selector was indexed")
            if getattr(fake, "branch_calls", []):
                errors.append(f"{name}: query functions ran")
            if not any(kind == "info" for kind, _text in fake.messages):
                errors.append(f"{name}: fail-soft info missing")
        except Exception as exc:  # noqa: BLE001 - aggregate malformed catalogs
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    if errors:
        raise AssertionError("analytics empty catalog: " + "; ".join(errors))


def test_migrated_analytics_wrong_shaped_catalog_fail_soft() -> None:
    cases = (
        ("none", None),
        ("row-mapping", {"table_name": "candidate_rankings"}),
        ("missing-table-row", [{}]),
        ("non-row", [None]),
    )
    expected_baseline = {
        "none": "TypeError",
        "row-mapping": "TypeError",
        "missing-table-row": "KeyError",
        "non-row": "TypeError",
    }
    observed_failures: dict[str, str] = {}
    blocking_errors: list[str] = []
    for name, catalog in cases:
        try:
            fake = _run_analytics(MISSING, catalog=catalog)
        except (KeyError, TypeError) as exc:
            observed_failures[name] = type(exc).__name__
            continue
        except Exception as exc:  # noqa: BLE001 - unexpected failures are blocking
            blocking_errors.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if _calls_for(fake, "adb_table"):
            blocking_errors.append(f"{name}: selector was indexed")
        if getattr(fake, "branch_calls", []):
            blocking_errors.append(f"{name}: query functions ran")
        if not any(kind == "info" for kind, _text in fake.messages):
            blocking_errors.append(f"{name}: fail-soft info missing")
    unexpected = {
        name: error
        for name, error in observed_failures.items()
        if expected_baseline.get(name) != error
    }
    if blocking_errors or unexpected:
        raise AssertionError(
            "analytics malformed catalog: "
            + "; ".join(
                (*blocking_errors, f"unexpected failures={unexpected!r}")
            )
        )
    if observed_failures:
        if _legacy_inventory() == EXPECTED_LEGACY and observed_failures != expected_baseline:
            raise AssertionError(
                "authorized baseline malformed failures differ: "
                f"{observed_failures!r}"
            )
        raise ExpectedMigrationDelta(
            f"wrong-shaped Analytics catalogs still crash: {observed_failures!r}",
            category="analytics_catalog",
            items=tuple(sorted(observed_failures)),
        )


def test_migrated_stock_checkup_state_contract() -> None:
    _assert_state_matrix(_selector("checkup_mode"), _run_stock)


def test_risk_guard_sources_and_run_key_invalidation() -> None:
    source_rows = {
        "手動輸入": (("MANUAL",), False, True),
        "Watchlist": (("WATCH",), False, False),
        "Screener 候選": (("SCREEN",), False, False),
        "IBKR 持倉": (("IBKR",), True, False),
    }
    for source, (tickers, provider_positions, manual_visible) in source_rows.items():
        fake = FakeStreamlit(
            {"rg_source": source, "rg_manual": "MANUAL", "rg_inc_pos": source == "IBKR 持倉"},
            button_values={"rg_run": True},
        )
        analyses: list[tuple[tuple[str, ...], bool]] = []

        def collect(selected: str, _manual: str) -> tuple[list[str], bool]:
            if selected != source:
                raise AssertionError((selected, source))
            return list(tickers), provider_positions

        with (
            patch.object(risk_guard, "st", fake),
            patch.object(risk_guard, "_collect", side_effect=collect),
            patch.object(risk_guard, "_load_scheduled_risk_snapshot", return_value=None),
            patch.object(
                risk_guard,
                "_analyze",
                side_effect=lambda selected, include: analyses.append(
                    (tuple(selected), bool(include))
                )
                or None,
            ),
        ):
            risk_guard.render()
        if ("rg_manual" in fake.text_inputs) is not manual_visible:
            raise AssertionError(f"manual visibility differs for {source}")
        if analyses != [(tickers, source == "IBKR 持倉" or provider_positions)]:
            raise AssertionError((source, analyses))

    matching = {
        "rg_source": "Watchlist",
        "rg_result": {"rows": []},
        "rg_detail_pick": "NVDA",
        "rg_run_key": ("Watchlist", ("NVDA",), False),
    }
    retained = {
        key: copy.deepcopy(matching[key])
        for key in ("rg_result", "rg_detail_pick", "rg_run_key")
    }
    fake = FakeStreamlit(matching)
    with (
        patch.object(risk_guard, "st", fake),
        patch.object(risk_guard, "_collect", return_value=(["NVDA"], False)),
        patch.object(risk_guard, "_load_scheduled_risk_snapshot", return_value=None),
        patch.object(risk_guard, "_tab_overview", return_value=None),
        patch.object(risk_guard, "_tab_table", return_value=None),
        patch.object(risk_guard, "_tab_portfolio", return_value=None),
        patch.object(risk_guard, "_tab_detail", return_value=None),
        patch.object(risk_guard, "_tab_sources", return_value=None),
        patch.object(risk_guard._shared, "metric_card", return_value=None),
    ):
        risk_guard.render()
    for key, expected in retained.items():
        if fake.session_state.get(key, MISSING) != expected:
            raise AssertionError(
                f"matching run key changed {key}: {fake.session_state.get(key)!r}"
            )

    changed_axes = {
        "source": ("手動輸入", ("NVDA",), False),
        "tickers": ("Watchlist", ("OLD",), False),
        "include": ("Watchlist", ("NVDA",), True),
    }
    for axis, previous_run_key in changed_axes.items():
        changed = dict(matching)
        changed["rg_run_key"] = previous_run_key
        fake = FakeStreamlit(changed)
        with (
            patch.object(risk_guard, "st", fake),
            patch.object(risk_guard, "_collect", return_value=(["NVDA"], False)),
            patch.object(
                risk_guard,
                "_load_scheduled_risk_snapshot",
                return_value=None,
            ),
        ):
            risk_guard.render()
        for key in ("rg_result", "rg_detail_pick", "rg_run_key"):
            if key in fake.session_state:
                raise AssertionError(f"{axis} drift retained {key}")


def test_institution_provider_exclusivity() -> None:
    for selected in _selector("inst_view").options:
        fake = _run_institutions(selected)
        if getattr(fake, "provider_calls", []) != [selected]:
            raise AssertionError((selected, getattr(fake, "provider_calls", [])))


def test_options_per_ticker_branch_isolation() -> None:
    nvda = _run_options("快照圖 + 預期波動錐", ticker="NVDA")
    amd = _run_options("互動圖 (TradingView)", ticker="AMD")
    if getattr(nvda, "branch_calls", []) != [("snapshot", "NVDA")]:
        raise AssertionError(nvda.branch_calls)  # type: ignore[attr-defined]
    if getattr(amd, "branch_calls", []) != [("interactive", "AMD")]:
        raise AssertionError(amd.branch_calls)  # type: ignore[attr-defined]
    if "cockpit_price_view_AMD" in nvda.session_state:
        raise AssertionError("NVDA state leaked into AMD")
    if "cockpit_price_view_NVDA" in amd.session_state:
        raise AssertionError("AMD state leaked into NVDA")

    shared = FakeStreamlit(
        {
            "cockpit_price_view_NVDA": "快照圖 + 預期波動錐",
            "cockpit_price_view_AMD": "互動圖 (TradingView)",
        }
    )
    shared_calls: list[tuple[str, str]] = []
    with (
        patch.object(options_cockpit, "st", shared),
        patch.object(
            options_cockpit,
            "_price_fig",
            side_effect=lambda data: shared_calls.append(
                ("snapshot", data.ticker)
            )
            or "snapshot",
        ),
        patch.object(
            options_cockpit._shared,
            "tradingview_chart",
            side_effect=lambda ticker, **_kwargs: shared_calls.append(
                ("interactive", ticker)
            ),
        ),
    ):
        options_cockpit._render_price_chart(SimpleNamespace(ticker="NVDA"))
        options_cockpit._render_price_chart(SimpleNamespace(ticker="AMD"))
    if shared_calls != [("snapshot", "NVDA"), ("interactive", "AMD")]:
        raise AssertionError(shared_calls)
    if (
        shared.session_state.get("cockpit_price_view_NVDA")
        != "快照圖 + 預期波動錐"
        or shared.session_state.get("cockpit_price_view_AMD")
        != "互動圖 (TradingView)"
    ):
        raise AssertionError("per-ticker states did not remain isolated")


def test_radar_handoff_and_all_filters() -> None:
    fake = FakeStreamlit(
        {
            "radar_handoff": "TSLA",
            "radar_source": "IBKR 持倉",
            "radar_manual": "OLD",
            "radar_risk": {"rows": []},
            "radar_rev": {"rows": []},
            "radar_detail_pick": "OLD",
            "radar_run_key": ("IBKR 持倉", ("OLD",), True),
        }
    )
    with patch.object(radar, "st", fake), patch.object(
        radar, "_collect", return_value=(["TSLA"], False)
    ):
        radar._render_dual_read()
    if fake.session_state.get("radar_source") != "手動輸入":
        raise AssertionError("handoff did not force manual source")
    if fake.session_state.get("radar_manual") != "TSLA":
        raise AssertionError("handoff ticker was not consumed")
    for key in ("radar_risk", "radar_rev", "radar_detail_pick", "radar_run_key"):
        if key in fake.session_state:
            raise AssertionError(f"handoff retained stale {key}")

    expected = {
        "全部": {"BOTH", "RISK", "REV"},
        "風險警示": {"BOTH", "RISK"},
        "反轉候選": {"BOTH", "REV"},
        "兩者共現": {"BOTH"},
    }
    for view, tickers in expected.items():
        out = FakeStreamlit()
        with patch.object(radar, "st", out):
            radar._render_table(_radar_frame(), view)
        if len(out.frames) != 1:
            raise AssertionError((view, len(out.frames)))
        frame = getattr(out.frames[0], "data", out.frames[0])
        if set(frame["代號"].tolist()) != tickers:
            raise AssertionError((view, frame["代號"].tolist()))


def test_knowledge_graph_figure_branches() -> None:
    nebula = _run_knowledge_graph("kg_view_mode", "星雲圖", other="全部")
    lanes = _run_knowledge_graph("kg_view_mode", "驗證泳道", other="核心")
    if getattr(nebula, "branch_calls", []) != [("nebula", "全部")]:
        raise AssertionError(nebula.branch_calls)  # type: ignore[attr-defined]
    if getattr(lanes, "branch_calls", []) != [("lanes", None)]:
        raise AssertionError(lanes.branch_calls)  # type: ignore[attr-defined]


def test_retro_one_shot_lane_dispatch() -> None:
    continuation = _run_retro("續漲強者")
    playbook = _run_retro("Playbook 驗證")
    handoff = FakeStreamlit(
        {
            "validation_lane": "續漲強者",
            "retro_validation_lane": "Playbook 驗證",
        }
    )
    handoff_calls: list[str] = []
    with (
        patch.object(retro_analysis, "st", handoff),
        patch.object(
            retro_analysis.continuation_validation,
            "render",
            side_effect=lambda: handoff_calls.append("continuation"),
        ),
        patch.object(
            retro_analysis.playbook_validation,
            "render",
            side_effect=lambda: handoff_calls.append("playbook"),
        ),
    ):
        retro_analysis.render()
    if continuation.branch_calls != ["continuation"]:  # type: ignore[attr-defined]
        raise AssertionError(continuation.branch_calls)  # type: ignore[attr-defined]
    if playbook.branch_calls != ["playbook"]:  # type: ignore[attr-defined]
        raise AssertionError(playbook.branch_calls)  # type: ignore[attr-defined]
    if handoff_calls != ["continuation"] or "validation_lane" in handoff.session_state:
        raise AssertionError((handoff_calls, handoff.session_state))


def test_ai_provider_and_saved_payload() -> None:
    fake = FakeStreamlit()
    answers: list[dict[str, Any]] = []
    saves: list[dict[str, Any]] = []
    context_attachment = {
        "page_path": "stock-checkup",
        "page_title": "個股總覽",
        "ticker": "NVDA",
        "summary": "stable",
        "sources": ["fixture"],
    }
    with (
        patch.object(ai_chat, "st", fake),
        patch.object(
            ai_chat.ai_chat_assistant,
            "answer_chat",
            side_effect=lambda question, **kwargs: answers.append(
                {"question": question, **kwargs}
            )
            or "answer",
        ),
        patch.object(
            ai_chat.ai_chat_store,
            "save_chat",
            side_effect=lambda payload, _root: saves.append(copy.deepcopy(payload))
            or {"id": "chat-1", "title": "Saved"},
        ),
        patch.object(ai_chat, "_rerun_panel", return_value=None),
    ):
        ai_chat._init_state()
        fake.session_state[ai_chat._MODE] = "深度研究"
        fake.session_state[ai_chat._SAVE] = True
        fake.session_state[ai_chat._CONTEXT] = copy.deepcopy(context_attachment)
        ai_chat._handle_submit("question", Path("/owned/chat"))
    if answers != [
        {
            "question": "question",
            "history": [],
            "mode": "深度研究",
            "context_attachment": context_attachment,
        }
    ]:
        raise AssertionError(answers)
    expected_messages = [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]
    if saves != [
        {
            "id": "",
            "title": "",
            "mode": "深度研究",
            "messages": expected_messages,
            "context_attachment": context_attachment,
        }
    ]:
        raise AssertionError(saves)


def test_analytics_second_table_reaches_exact_query_functions() -> None:
    first = _run_analytics("candidate_rankings")
    second = _run_analytics("iv_history")
    if first.branch_calls != [  # type: ignore[attr-defined]
        ("columns", "candidate_rankings"),
        ("fetch", "candidate_rankings"),
    ]:
        raise AssertionError(first.branch_calls)  # type: ignore[attr-defined]
    if second.branch_calls != [  # type: ignore[attr-defined]
        ("columns", "iv_history"),
        ("fetch", "iv_history"),
    ]:
        raise AssertionError(second.branch_calls)  # type: ignore[attr-defined]


def test_stock_checkup_handoff_and_batch_dispatch() -> None:
    handoff = _run_stock("批次", handoff="TSLA")
    batch = _run_stock("批次")
    if handoff.session_state.get("checkup_mode") != "單檔":
        raise AssertionError("handoff did not force single mode")
    if handoff.branch_calls != [("single", "TSLA")]:  # type: ignore[attr-defined]
        raise AssertionError(handoff.branch_calls)  # type: ignore[attr-defined]
    if batch.branch_calls != [("batch", None)]:  # type: ignore[attr-defined]
        raise AssertionError(batch.branch_calls)  # type: ignore[attr-defined]


HARD_TESTS = (
    test_capture_stack_and_trusted_ax_preflight,
    test_selector_delta_contract_and_uniform_workspace,
    test_selector_delta_rejects_contract_mutations,
    test_trusted_ax_keyboard_target_and_layout_rejection,
    test_risk_guard_sources_and_run_key_invalidation,
    test_institution_provider_exclusivity,
    test_options_per_ticker_branch_isolation,
    test_radar_handoff_and_all_filters,
    test_knowledge_graph_figure_branches,
    test_retro_one_shot_lane_dispatch,
    test_ai_provider_and_saved_payload,
    test_analytics_missing_and_empty_catalog_fail_soft,
    test_analytics_second_table_reaches_exact_query_functions,
    test_stock_checkup_handoff_and_batch_dispatch,
)

RED_TESTS = (
    test_ast_requires_zero_segmented_controls,
    test_migrated_risk_guard_state_contract,
    test_migrated_institutions_state_contract,
    test_migrated_options_state_contract,
    test_migrated_radar_source_state_contract,
    test_migrated_radar_view_state_contract,
    test_migrated_knowledge_graph_view_state_contract,
    test_migrated_knowledge_graph_label_state_contract,
    test_migrated_ai_chat_state_contract,
    test_migrated_retro_state_contract,
    test_migrated_analytics_state_contract,
    test_migrated_analytics_wrong_shaped_catalog_fail_soft,
    test_migrated_stock_checkup_state_contract,
)


def _run_tests(
    tests: Sequence[Callable[[], None]],
) -> tuple[list[str], dict[str, Exception]]:
    passed: list[str] = []
    failed: dict[str, Exception] = {}
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - standalone aggregate runner
            failed[test.__name__] = exc
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            passed.append(test.__name__)
            print(f"PASS {test.__name__}")
    return passed, failed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expect-legacy-red",
        action="store_true",
        help=(
            "Task 7 gate: require exact 11-selector red, the reviewed Analytics "
            "catalog red, and green hard checks"
        ),
    )
    args = parser.parse_args(argv)

    hard_passed, hard_failed = _run_tests(HARD_TESTS)
    red_passed, red_failed = _run_tests(RED_TESTS)
    if args.expect_legacy_red:
        inventory = _legacy_inventory()
        expected_failures = {test.__name__ for test in RED_TESTS}
        if hard_failed:
            print(f"BLOCKED: hard checks failed: {sorted(hard_failed)}")
            return 1
        if inventory != EXPECTED_LEGACY:
            print(f"BLOCKED: legacy inventory differs: {inventory}")
            return 1
        if set(red_failed) != expected_failures or red_passed:
            print(
                "BLOCKED: expected every migration test to be red; "
                f"passed={red_passed}, failed={sorted(red_failed)}"
            )
            return 1
        unclassified = {
            name: type(exc).__name__
            for name, exc in red_failed.items()
            if not isinstance(exc, ExpectedMigrationDelta)
        }
        if unclassified:
            print(f"BLOCKED: unclassified red failures: {unclassified}")
            return 1
        catalog_failure = red_failed[
            test_migrated_analytics_wrong_shaped_catalog_fail_soft.__name__
        ]
        if not (
            isinstance(catalog_failure, ExpectedMigrationDelta)
            and catalog_failure.category == "analytics_catalog"
            and set(catalog_failure.items)
            == {"none", "row-mapping", "missing-table-row", "non-row"}
        ):
            print("BLOCKED: Analytics catalog red differs from reviewed baseline")
            return 1
        wrong_categories = {
            name: exc.category
            for name, exc in red_failed.items()
            if name
            != test_migrated_analytics_wrong_shaped_catalog_fail_soft.__name__
            and isinstance(exc, ExpectedMigrationDelta)
            and exc.category != "selector"
        }
        if wrong_categories:
            print(f"BLOCKED: selector red categories differ: {wrong_categories}")
            return 1
        ast_failure = red_failed[test_ast_requires_zero_segmented_controls.__name__]
        expected_ast_items = {contract.key for contract in SELECTORS}
        if not (
            isinstance(ast_failure, ExpectedMigrationDelta)
            and set(ast_failure.items) == expected_ast_items
        ):
            print("BLOCKED: AST red does not cover the exact selector catalog")
            return 1
        state_test_names = {
            test.__name__
            for test in RED_TESTS
            if test
            not in (
                test_ast_requires_zero_segmented_controls,
                test_migrated_analytics_wrong_shaped_catalog_fail_soft,
            )
        }
        state_items = [
            item
            for name, exc in red_failed.items()
            if name in state_test_names
            and isinstance(exc, ExpectedMigrationDelta)
            for item in exc.items
        ]
        expected_state_items = [
            (
                "cockpit_price_view_NVDA"
                if contract.key == "cockpit_price_view_{}"
                else contract.key
            )
            for contract in SELECTORS
        ]
        if sorted(state_items) != sorted(expected_state_items):
            print(
                "BLOCKED: selector state red coverage differs: "
                f"observed={state_items}, expected={expected_state_items}"
            )
            return 1
        print(
            f"EXPECTED RED: {len(inventory)}/11 frozen segmented controls remain; "
            "4 wrong-shaped Analytics catalogs still crash; "
            f"{len(hard_passed)}/{len(HARD_TESTS)} hard checks passed"
        )
        return 0

    failures = {**hard_failed, **red_failed}
    if failures:
        print(
            f"FAIL: {len(hard_passed) + len(red_passed)} passed, "
            f"{len(failures)} failed"
        )
        return 1
    print(f"PASS: {len(HARD_TESTS) + len(RED_TESTS)} selector/AX tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
