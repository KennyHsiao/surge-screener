#!/usr/bin/env python3
"""Deterministic AST inventory for Quant Radar's Streamlit UI contract.

The module deliberately does not import Streamlit or any production UI module.
It treats ``app.py`` and ``ui/**/*.py`` as source contracts and emits only
repository-relative metadata; rendered strings and source payloads are never
included in the report.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


VERSION = "0.2.0"
SCHEMA_VERSION = "quant-radar-ui-ux-contract/v2"

# UX-0 remains immutable historical evidence.  These are the only fields that
# are expected to remain equal when a later safety phase intentionally removes
# or replaces unsafe presentation sites.
UX0_COMPATIBILITY_FIELDS = (
    "pages",
    "navigation",
    "same_session_routes",
    "handoffs",
    "source_roots",
)

EXPECTED_GROUPS = ("今日決策", "市場背景", "研究驗證", "資料維護", "幣圈")
EXPECTED_PAGE_COUNT = 27
EXPECTED_DEFAULT_KEY = "today-decision"
EXPECTED_ROUTE_TARGETS = (
    "analytics-db",
    "ibkr-reconcile",
    "knowledge-graph",
    "market-thesis",
    "options-cockpit",
    "options-flow",
    "radar",
    "retro-analysis",
    "stock-checkup",
    "theme-flow",
    "trade-state",
    "us-cot",
    "us-screener",
)

_UI_SINKS = {"error", "warning", "info", "write", "markdown", "caption", "expander"}
_COLLECTION_SINKS = {"append", "extend", "update"}
_PERSISTENCE_SINKS = {"write_text", "write_bytes", "write", "dump", "dumps"}
_SECRET_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]+|api[_-]?key|access[_-]?token|secret|password|credential|cookie)",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"^(?:/|~/|[A-Za-z]:[\\/])")


class InventoryError(ValueError):
    """Stable validation failure suitable for a CLI error message."""


def canonical_json(value: Any) -> str:
    """Return the stable, UTF-8-friendly JSON representation used by ``--json``."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse(source: str, relative_path: str) -> ast.Module:
    try:
        return ast.parse(source, filename=relative_path, type_comments=True)
    except SyntaxError as exc:
        line = exc.lineno if exc.lineno is not None else "?"
        raise InventoryError(
            f"{relative_path}: invalid Python at line {line}: {exc.msg}"
        ) from None


def _qualname(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualname(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _string_literal(node: ast.AST | None, context: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise InventoryError(f"{context} must be a string literal")


def _bool_literal(node: ast.AST | None, context: str) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    raise InventoryError(f"{context} must be a boolean literal")


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for item in call.keywords:
        if item.arg == name:
            return item.value
    return None


def _call_argument(call: ast.Call, position: int, keyword: str) -> ast.AST | None:
    if len(call.args) > position:
        return call.args[position]
    return _keyword(call, keyword)


def _expression_name(node: ast.AST) -> str:
    name = _qualname(node)
    if name:
        return name
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise InventoryError(f"source path must be repository-relative: {normalized}")
    return path.as_posix()


class _ContextIndex(ast.NodeVisitor):
    """Map every visited node to its enclosing class/function name."""

    def __init__(self) -> None:
        self.context: dict[int, str] = {}
        self._stack: list[str] = []

    def _record(self, node: ast.AST) -> None:
        self.context[id(node)] = ".".join(self._stack) if self._stack else "<module>"

    def generic_visit(self, node: ast.AST) -> None:
        self._record(node)
        super().generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node)
        self._stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node)
        self._stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]


def _context_index(tree: ast.Module) -> dict[int, str]:
    visitor = _ContextIndex()
    visitor.visit(tree)
    return visitor.context


def _find_nav_dict(tree: ast.Module) -> ast.Dict:
    matches: list[ast.Dict] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "nav" for target in statement.targets):
                if not isinstance(statement.value, ast.Dict):
                    raise InventoryError("app.py nav must be a dictionary literal")
                matches.append(statement.value)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "nav"
        ):
            if not isinstance(statement.value, ast.Dict):
                raise InventoryError("app.py nav must be a dictionary literal")
            matches.append(statement.value)
    if len(matches) != 1:
        raise InventoryError(f"app.py must define exactly one nav dictionary; found {len(matches)}")
    return matches[0]


def _parse_pages(tree: ast.Module) -> tuple[list[dict[str, Any]], list[str]]:
    nav = _find_nav_dict(tree)
    pages: list[dict[str, Any]] = []
    groups: list[str] = []

    for key, value in zip(nav.keys, nav.values):
        group = _string_literal(key, "app.py nav group")
        if group in groups:
            raise InventoryError(f"duplicate nav group: {group}")
        groups.append(group)
        if not isinstance(value, (ast.List, ast.Tuple)):
            raise InventoryError(f"app.py nav group {group!r} must contain a page list")
        for item in value.elts:
            if not isinstance(item, ast.Call) or _qualname(item.func) != "st.Page":
                raise InventoryError(f"app.py nav group {group!r} contains a non-st.Page entry")
            if not item.args:
                raise InventoryError("st.Page must include its page callable")
            values = {keyword.arg: keyword.value for keyword in item.keywords if keyword.arg}
            if any(keyword.arg is None for keyword in item.keywords):
                raise InventoryError("st.Page does not support dynamic **kwargs in the inventory")
            title = _string_literal(values.get("title"), "st.Page title")
            icon = _string_literal(values.get("icon"), "st.Page icon")
            url_path = _string_literal(values.get("url_path"), "st.Page url_path")
            if not url_path or url_path.startswith("/"):
                raise InventoryError(f"invalid st.Page url_path: {url_path!r}")
            default_node = values.get("default")
            default = False if default_node is None else _bool_literal(default_node, "st.Page default")
            pages.append(
                {
                    "callable": _expression_name(item.args[0]),
                    "default": default,
                    "file": "app.py",
                    "group": group,
                    "icon": icon,
                    "registry_key": url_path,
                    "review_line": item.lineno,
                    "route": "/" if default else f"/{url_path}",
                    "title": title,
                    "url_path": url_path,
                }
            )

    if len(groups) != len(EXPECTED_GROUPS):
        raise InventoryError(
            f"expected {len(EXPECTED_GROUPS)} nav groups, found {len(groups)}"
        )
    if tuple(groups) != EXPECTED_GROUPS:
        raise InventoryError(f"nav groups changed: expected {list(EXPECTED_GROUPS)!r}")
    if len(pages) != EXPECTED_PAGE_COUNT:
        raise InventoryError(f"expected {EXPECTED_PAGE_COUNT} st.Page definitions, found {len(pages)}")

    registry_keys = [page["registry_key"] for page in pages]
    duplicate_keys = sorted({key for key in registry_keys if registry_keys.count(key) > 1})
    if duplicate_keys:
        raise InventoryError(f"duplicate page url_path values: {duplicate_keys}")
    defaults = [page for page in pages if page["default"]]
    if len(defaults) != 1:
        raise InventoryError(f"expected exactly one default page, found {len(defaults)}")
    if defaults[0]["registry_key"] != EXPECTED_DEFAULT_KEY:
        raise InventoryError(
            f"default registry key must remain {EXPECTED_DEFAULT_KEY!r}"
        )
    bookmarks = [page for page in pages if not page["default"]]
    if len(bookmarks) != EXPECTED_PAGE_COUNT - 1:
        raise InventoryError("expected exactly 26 non-default bookmark routes")
    return pages, groups


def _assignment_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _validate_registry_wiring(tree: ast.Module) -> dict[str, Any]:
    parents = _parent_index(tree)
    updates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _qualname(node.func) == "_shared.PAGE_REGISTRY.update"
    ]
    if len(updates) != 1:
        raise InventoryError(
            "app.py must contain exactly one _shared.PAGE_REGISTRY.update call"
        )
    update = updates[0]
    update_statement = parents.get(id(update))
    if not (
        isinstance(update_statement, ast.Expr)
        and isinstance(parents.get(id(update_statement)), ast.Module)
    ):
        raise InventoryError("PAGE_REGISTRY.update must execute at module scope")
    if len(update.args) != 1 or update.keywords or not isinstance(update.args[0], ast.DictComp):
        raise InventoryError("PAGE_REGISTRY.update must receive the exact nav comprehension")
    comprehension = update.args[0]
    if len(comprehension.generators) != 2:
        raise InventoryError("PAGE_REGISTRY.update comprehension must have both nav loops")
    outer, inner = comprehension.generators
    outer_name = _assignment_name(outer.target)
    inner_name = _assignment_name(inner.target)
    outer_iter = outer.iter
    if (
        not outer_name
        or not isinstance(outer_iter, ast.Call)
        or _qualname(outer_iter.func) != "nav.values"
        or outer_iter.args
        or outer_iter.keywords
        or outer.ifs
    ):
        raise InventoryError("PAGE_REGISTRY.update outer loop must derive from nav.values()")
    if (
        not inner_name
        or not isinstance(inner.iter, ast.Name)
        or inner.iter.id != outer_name
        or inner.ifs
    ):
        raise InventoryError("PAGE_REGISTRY.update inner loop must iterate the nav page lists")
    key = comprehension.key
    if not (
        isinstance(key, ast.Attribute)
        and key.attr == "url_path"
        and isinstance(key.value, ast.Name)
        and key.value.id == inner_name
    ):
        raise InventoryError("PAGE_REGISTRY.update key must be p.url_path")
    if not isinstance(comprehension.value, ast.Name) or comprehension.value.id != inner_name:
        raise InventoryError("PAGE_REGISTRY.update value must be the same page p")

    navigation_assignments: list[tuple[ast.Assign | ast.AnnAssign, ast.Call, str]] = []
    for node in ast.walk(tree):
        value: ast.AST | None = None
        target: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            value, target = node.value, node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            value, target = node.value, node.target
        if isinstance(value, ast.Call) and _qualname(value.func) == "st.navigation":
            target_name = _assignment_name(target) if target is not None else None
            if target_name is None:
                raise InventoryError("st.navigation(nav) result must be assigned to a page variable")
            navigation_assignments.append((node, value, target_name))
    if len(navigation_assignments) != 1:
        raise InventoryError("app.py must contain exactly one assigned st.navigation(nav) call")
    navigation_node, navigation_call, selected_name = navigation_assignments[0]
    if not isinstance(parents.get(id(navigation_node)), ast.Module):
        raise InventoryError("st.navigation(nav) must execute at module scope")
    if (
        len(navigation_call.args) != 1
        or navigation_call.keywords
        or not isinstance(navigation_call.args[0], ast.Name)
        or navigation_call.args[0].id != "nav"
    ):
        raise InventoryError("st.navigation(nav) must receive the exact nav dictionary")

    run_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _qualname(node.func) == f"{selected_name}.run"
        and not node.args
        and not node.keywords
    ]
    if len(run_calls) != 1:
        raise InventoryError(f"selected page {selected_name} must be invoked once through .run()")
    run_call = run_calls[0]
    run_statement = parents.get(id(run_call))
    if not (
        isinstance(run_statement, ast.Expr)
        and isinstance(parents.get(id(run_statement)), ast.Module)
    ):
        raise InventoryError("selected page .run() must execute at module scope")
    if not (update.lineno < navigation_node.lineno < run_call.lineno):
        raise InventoryError(
            "PAGE_REGISTRY.update -> st.navigation(nav) -> selected page .run() order changed"
        )
    return {
        "navigation_variable": selected_name,
        "registry_update": True,
        "selected_page_run": True,
        "source": "nav",
    }


def _parent_index(tree: ast.Module) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _enclosing_guard_name(node: ast.AST, parents: Mapping[int, ast.AST]) -> str | None:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, ast.If) and isinstance(current.test, ast.Name):
            return current.test.id
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            break
    return None


def _ticker_action_table(
    tree: ast.Module, context: Mapping[int, str]
) -> list[dict[str, Any]]:
    parents = _parent_index(tree)
    actions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if context.get(id(node)) != "ticker_action_buttons":
            continue
        if _qualname(node.func) != "actions.append" or len(node.args) != 1:
            continue
        value = node.args[0]
        if not isinstance(value, (ast.Tuple, ast.List)) or len(value.elts) < 3:
            raise InventoryError("ticker_action_buttons action must be a literal tuple")
        target = _string_literal(value.elts[1], "ticker action page target")
        state_key = _string_literal(value.elts[2], "ticker action state key")
        include_flag = _enclosing_guard_name(node, parents)
        if not include_flag or not include_flag.startswith("include_"):
            raise InventoryError("ticker action must be guarded by a literal include_* flag")
        actions.append(
            {
                "include_flag": include_flag,
                "line": node.lineno,
                "state_key": state_key,
                "target": target,
            }
        )
    if not actions:
        raise InventoryError("ticker_action_buttons tuple table was not found")
    return sorted(actions, key=lambda item: (item["line"], item["target"]))


def _validate_ticker_action_helper(
    tree: ast.Module, context: Mapping[int, str]
) -> tuple[str, str]:
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and context.get(id(node)) == "ticker_action_buttons"
        and isinstance(node.iter, ast.Call)
        and _qualname(node.iter.func) == "zip"
        and any(isinstance(argument, ast.Name) and argument.id == "actions" for argument in node.iter.args)
    ]
    if len(loops) != 1:
        raise InventoryError(
            "ticker_action_buttons must have one zip loop over its action table"
        )
    target = loops[0].target
    if not (
        isinstance(target, (ast.Tuple, ast.List))
        and len(target.elts) == 2
        and isinstance(target.elts[1], (ast.Tuple, ast.List))
        and len(target.elts[1].elts) >= 3
    ):
        raise InventoryError("ticker_action_buttons loop must unpack page and state_key")
    action_target = target.elts[1]
    page_variable = _assignment_name(action_target.elts[1])
    state_key_variable = _assignment_name(action_target.elts[2])
    if not page_variable or not state_key_variable:
        raise InventoryError("ticker_action_buttons loop must bind page and state_key names")

    state_writes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if context.get(id(node)) != "ticker_action_buttons":
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for write_target in targets:
            if not (
                isinstance(write_target, ast.Subscript)
                and _qualname(write_target.value) == "st.session_state"
                and isinstance(write_target.slice, ast.Name)
                and write_target.slice.id == state_key_variable
            ):
                continue
            if isinstance(value, ast.Name) and value.id == "sym":
                state_writes.append(node)
    if len(state_writes) != 1:
        raise InventoryError(
            "ticker_action_buttons must retain its st.session_state[state_key] write"
        )
    return page_variable, state_key_variable


def _literal_route_argument(
    call: ast.Call, position: int, keyword: str, label: str
) -> str:
    value = _call_argument(call, position, keyword)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value.strip("/")
    raise InventoryError(f"dynamic {label} expression is unsupported")


def _scan_routes(
    trees: Mapping[str, ast.Module], page_keys: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    shared_tree = trees.get("ui/_shared.py")
    if shared_tree is None:
        raise InventoryError("ui/_shared.py is required for same-session route inventory")
    contexts = {path: _context_index(tree) for path, tree in trees.items()}
    actions = _ticker_action_table(shared_tree, contexts["ui/_shared.py"])
    ticker_page_variable, _ticker_state_key_variable = _validate_ticker_action_helper(
        shared_tree, contexts["ui/_shared.py"]
    )
    sites: list[dict[str, Any]] = []
    registry_dispatcher = False
    jump_dispatcher = False
    ticker_dispatcher = False
    ticker_call_count = 0

    for path, tree in sorted(trees.items()):
        context = contexts[path]
        calls = sorted(
            (node for node in ast.walk(tree) if isinstance(node, ast.Call)),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for call in calls:
            called = _qualname(call.func)
            function = context.get(id(call), "<module>")
            if called == "_shared.switch_page":
                argument = _call_argument(call, 0, "url_path")
                if (
                    path == "ui/today_decision.py"
                    and function.endswith("_jump")
                    and isinstance(argument, ast.Name)
                    and argument.id == "page"
                ):
                    jump_dispatcher = True
                    continue
                target = _literal_route_argument(call, 0, "url_path", "switch_page target")
                sites.append(
                    {
                        "file": path,
                        "form": "direct",
                        "function": function,
                        "review_line": call.lineno,
                        "target": target,
                    }
                )
            elif called == "switch_page" and path == "ui/_shared.py":
                argument = _call_argument(call, 0, "url_path")
                if (
                    function.endswith("ticker_action_buttons")
                    and isinstance(argument, ast.Name)
                    and argument.id == ticker_page_variable
                ):
                    ticker_dispatcher = True
                else:
                    raise InventoryError("dynamic switch_page target expression is unsupported")
            elif (
                called == "st.switch_page"
                and path == "ui/_shared.py"
                and function == "switch_page"
            ):
                argument = _call_argument(call, 0, "page")
                if isinstance(argument, ast.Name) and argument.id == "page":
                    registry_dispatcher = True
                else:
                    raise InventoryError(
                        "_shared.switch_page must dispatch its registered page object"
                    )
            elif called == "switch_page" or called.endswith(".switch_page"):
                raise InventoryError(f"unsupported switch_page call form: {called}")
            elif called == "_jump" and path == "ui/today_decision.py":
                target = _literal_route_argument(call, 1, "page", "_jump page")
                sites.append(
                    {
                        "file": path,
                        "form": "jump_helper",
                        "function": function,
                        "review_line": call.lineno,
                        "target": target,
                    }
                )
            elif called == "_jump" or called.endswith("._jump"):
                raise InventoryError(f"unsupported _jump call form: {called}")
            elif called == "_shared.ticker_action_buttons":
                ticker_call_count += 1
                keyword_values = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
                if any(keyword.arg is None for keyword in call.keywords):
                    raise InventoryError("ticker_action_buttons does not support dynamic **kwargs")
                for action in actions:
                    enabled_node = keyword_values.get(action["include_flag"])
                    enabled = (
                        True
                        if enabled_node is None
                        else _bool_literal(enabled_node, action["include_flag"])
                    )
                    if enabled:
                        sites.append(
                            {
                                "file": path,
                                "form": "ticker_action_buttons",
                                "function": function,
                                "review_line": call.lineno,
                                "state_key": action["state_key"],
                                "target": action["target"],
                            }
                        )

    if not registry_dispatcher:
        raise InventoryError(
            "_shared.switch_page no longer delegates its registered page through st.switch_page"
        )
    if not jump_dispatcher:
        raise InventoryError("today_decision._jump no longer delegates through _shared.switch_page(page)")
    if not ticker_dispatcher:
        raise InventoryError("ticker_action_buttons no longer delegates through switch_page(page)")
    if ticker_call_count == 0:
        raise InventoryError("ticker_action_buttons has no callers to expand")

    targets = sorted({site["target"] for site in sites})
    unresolved = sorted(set(targets) - page_keys)
    if unresolved:
        raise InventoryError(f"same-session target does not resolve: {unresolved[0]}")
    if tuple(targets) != EXPECTED_ROUTE_TARGETS:
        missing = sorted(set(EXPECTED_ROUTE_TARGETS) - set(targets))
        added = sorted(set(targets) - set(EXPECTED_ROUTE_TARGETS))
        raise InventoryError(
            f"same-session target set changed; missing={missing}, added={added}"
        )
    sites.sort(key=lambda item: (item["file"], item["review_line"], item["form"], item["target"]))
    route_contract = {
        "forms": sorted({site["form"] for site in sites}),
        "sites": sites,
        "targets": targets,
    }
    return route_contract, actions


def _session_subscript_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Subscript) or _qualname(node.value) != "st.session_state":
        return None
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return None


def _assignment_targets(node: ast.AST) -> Iterable[ast.AST]:
    if isinstance(node, ast.Assign):
        return node.targets
    if isinstance(node, ast.AnnAssign):
        return (node.target,)
    if isinstance(node, ast.AugAssign):
        return (node.target,)
    if isinstance(node, ast.NamedExpr):
        return (node.target,)
    return ()


def _scan_session_accesses(
    trees: Mapping[str, ast.Module], actions: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    accesses: list[dict[str, Any]] = []
    for path, tree in sorted(trees.items()):
        context = _context_index(tree)
        for node in ast.walk(tree):
            for target in _assignment_targets(node):
                key = _session_subscript_key(target)
                if key is not None:
                    accesses.append(
                        {
                            "file": path,
                            "function": context.get(id(node), "<module>"),
                            "operation": "write",
                            "origin": "source",
                            "review_line": node.lineno,
                            "key": key,
                        }
                    )
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                key = _session_subscript_key(node)
                if key is not None:
                    accesses.append(
                        {
                            "file": path,
                            "function": context.get(id(node), "<module>"),
                            "operation": "get",
                            "origin": "source",
                            "review_line": node.lineno,
                            "key": key,
                        }
                    )
            if isinstance(node, ast.Call):
                called = _qualname(node.func)
                if called in {"st.session_state.get", "st.session_state.pop"}:
                    key_node = _call_argument(node, 0, "key")
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        accesses.append(
                            {
                                "file": path,
                                "function": context.get(id(node), "<module>"),
                                "operation": called.rsplit(".", 1)[-1],
                                "origin": "source",
                                "review_line": node.lineno,
                                "key": key_node.value,
                            }
                        )
    for action in actions:
        accesses.append(
            {
                "file": "ui/_shared.py",
                "function": "ticker_action_buttons",
                "operation": "write",
                "origin": "expanded_action_table",
                "review_line": action["line"],
                "key": action["state_key"],
            }
        )
    accesses.sort(
        key=lambda item: (
            item["file"],
            item["review_line"],
            item["key"],
            item["operation"],
            item["origin"],
        )
    )
    return accesses


_HANDOFF_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "stock_checkup",
        "target": "stock-checkup",
        "keys": (
            ("checkup_ticker", "sticky", "write", "get", "ui/stock_checkup.py", False),
            ("checkup_handoff", "one_shot", "write", "pop", "ui/stock_checkup.py", False),
        ),
    },
    {
        "name": "options_cockpit",
        "target": "options-cockpit",
        "keys": (
            ("cockpit_ticker", "sticky", "write", "get", "ui/options_cockpit.py", False),
        ),
    },
    {
        "name": "radar",
        "target": "radar",
        "keys": (
            ("radar_handoff", "one_shot", "write", "pop", "ui/radar.py", False),
        ),
    },
    {
        "name": "retro_analysis",
        "target": "retro-analysis",
        "keys": (
            ("validation_lane", "one_shot", "write", "pop", "ui/retro_analysis.py", False),
            (
                "retro_validation_lane",
                "sticky",
                "write",
                "get",
                "ui/retro_analysis.py",
                True,
            ),
        ),
    },
    {
        "name": "theme_flow",
        "target": "theme-flow",
        "keys": (
            (
                "theme_flow_focus_sector",
                "sticky_until_clear",
                "write",
                "get",
                "ui/theme_flow.py",
                False,
            ),
        ),
    },
)


def _build_handoffs(accesses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for handoff_spec in _HANDOFF_SPECS:
        keys: list[dict[str, Any]] = []
        for (
            key_name,
            lifecycle,
            producer_operation,
            consumer_operation,
            consumer_file,
            producer_may_be_consumer,
        ) in handoff_spec["keys"]:
            key_accesses = [dict(item) for item in accesses if item["key"] == key_name]
            producer_sites = [
                item
                for item in key_accesses
                if item["operation"] == producer_operation
                and (producer_may_be_consumer or item["file"] != consumer_file)
            ]
            consumer_sites = [
                item
                for item in key_accesses
                if item["operation"] == consumer_operation and item["file"] == consumer_file
            ]
            if not producer_sites:
                raise InventoryError(
                    f"handoff {key_name} lost producer {producer_operation} semantics"
                )
            if not consumer_sites:
                raise InventoryError(
                    f"handoff {key_name} lost consumer {consumer_operation} semantics"
                )
            if lifecycle == "sticky_until_clear" and not any(
                item["operation"] == "pop" and item["file"] == consumer_file
                for item in key_accesses
            ):
                raise InventoryError(f"handoff {key_name} lost explicit clear/pop semantics")
            keys.append(
                {
                    "accesses": key_accesses,
                    "consumer_operation": consumer_operation,
                    "consumer_sites": consumer_sites,
                    "key": key_name,
                    "lifecycle": lifecycle,
                    "producer_operation": producer_operation,
                    "producer_sites": producer_sites,
                }
            )
        result.append(
            {
                "keys": keys,
                "name": handoff_spec["name"],
                "target": handoff_spec["target"],
            }
        )
    return result


def _expression_category(node: ast.AST) -> str:
    categories = {
        ast.BinOp: "binary",
        ast.Call: "call",
        ast.Constant: "constant",
        ast.Dict: "dict",
        ast.JoinedStr: "f_string",
        ast.List: "list",
        ast.Name: "name",
        ast.Set: "set",
        ast.Subscript: "subscript",
        ast.Tuple: "tuple",
    }
    for node_type, label in categories.items():
        if isinstance(node, node_type):
            return label
    name = type(node).__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _is_static_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_static_expression(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_static_expression(key)) and _is_static_expression(value)
            for key, value in zip(node.keys, node.values)
        )
    if isinstance(node, ast.BinOp):
        return _is_static_expression(node.left) and _is_static_expression(node.right)
    if isinstance(node, ast.JoinedStr):
        return all(isinstance(value, ast.Constant) for value in node.values)
    return False


def _fingerprint(node: ast.AST) -> str:
    payload = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unsafe_expression(call: ast.Call) -> ast.AST:
    if call.args:
        return call.args[0]
    for name in ("body", "text", "label"):
        value = _keyword(call, name)
        if value is not None:
            return value
    return ast.Constant(value=None)


def _scan_unsafe_tree(
    tree: ast.Module, relative_path: str, context: Mapping[int, str]
) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    calls = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Call)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for call in calls:
        unsafe = _keyword(call, "unsafe_allow_html")
        if not (isinstance(unsafe, ast.Constant) and unsafe.value is True):
            continue
        expression = _unsafe_expression(call)
        raw.append(
            {
                "call_kind": _qualname(call.func) or type(call.func).__name__,
                "expression_category": _expression_category(expression),
                "file": relative_path,
                "fingerprint": _fingerprint(expression),
                "function": context.get(id(call), "<module>"),
                "review_line": call.lineno,
                "static": _is_static_expression(expression),
            }
        )

    occurrences: defaultdict[tuple[str, ...], int] = defaultdict(int)
    for item in raw:
        key = (
            item["file"],
            item["function"],
            item["call_kind"],
            item["expression_category"],
            item["fingerprint"],
        )
        occurrences[key] += 1
        item["occurrence"] = occurrences[key]
        item["site_id"] = "|".join((*key, str(item["occurrence"])))
    return raw


def _name_categories(name: str) -> set[str]:
    lowered = name.lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", lowered) if token}
    categories: set[str] = set()
    if tokens & {"exc", "exception", "error", "errors", "err"} or lowered.endswith("error"):
        categories.add("exception")
    if tokens & {"path", "paths", "dir", "directory", "filepath", "filename", "file"}:
        categories.add("path")
    if tokens & {"url", "uri", "endpoint"}:
        categories.add("url")
    if tokens & {"host", "hostname"}:
        categories.add("host")
    if "port" in tokens:
        categories.add("port")
    if "profile" in tokens:
        categories.add("profile")
    if tokens & {"token", "secret", "password", "credential", "cookie", "apikey", "auth"}:
        categories.add("secret")
    if tokens & {"pid", "processid", "process_id"}:
        categories.add("pid")
    if tokens & {"log", "logs", "tail", "stderr", "stdout", "command", "cmd"}:
        categories.add("log")
    return categories


def _constant_categories(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    categories: set[str] = set()
    if _SECRET_RE.search(value):
        categories.add("secret")
    if _PATH_RE.search(value):
        categories.add("path")
    if re.search(r"\bprofile\b", value, re.IGNORECASE):
        categories.add("profile")
    if re.search(r"\bpid\b", value, re.IGNORECASE):
        categories.add("pid")
    if re.search(r"\b(?:log|stderr|stdout)\b", value, re.IGNORECASE):
        categories.add("log")
    if re.match(r"^https?://", value, re.IGNORECASE):
        categories.add("url")
        try:
            split = urlsplit(value)
            hostname = split.hostname
            port = split.port
        except ValueError:
            return categories
        if hostname:
            categories.add("host")
        if port is not None:
            categories.add("port")
    return categories


def _expr_taint(node: ast.AST | None, environment: Mapping[str, set[str]]) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        return set(environment.get(node.id, set())) | _name_categories(node.id)
    if isinstance(node, ast.Constant):
        return _constant_categories(node.value)
    if isinstance(node, ast.Attribute):
        return _expr_taint(node.value, environment) | _name_categories(node.attr)
    if isinstance(node, ast.Subscript):
        categories = _expr_taint(node.value, environment)
        categories |= _expr_taint(node.slice, environment)
        return categories
    if isinstance(node, ast.JoinedStr):
        categories: set[str] = set()
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                categories |= _expr_taint(value.value, environment)
            else:
                categories |= _expr_taint(value, environment)
        if categories:
            categories.add("f_string")
        return categories
    if isinstance(node, ast.Dict):
        categories: set[str] = set()
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                key_categories = _name_categories(key.value)
                categories |= key_categories
                if "exception" in key_categories:
                    categories.add("payload_error")
            categories |= _expr_taint(value, environment)
        return categories
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        categories: set[str] = set()
        for item in node.elts:
            categories |= _expr_taint(item, environment)
        return categories
    if isinstance(node, ast.Call):
        categories = _expr_taint(node.func.value, environment) if isinstance(node.func, ast.Attribute) else set()
        for argument in node.args:
            categories |= _expr_taint(argument, environment)
        for keyword in node.keywords:
            categories |= _expr_taint(keyword.value, environment)
        called = _qualname(node.func)
        last = called.rsplit(".", 1)[-1]
        if last in {"Path", "PurePath", "resolve", "absolute"}:
            categories.add("path")
        if last == "str" and "exception" in categories:
            categories.add("exception_string")
        return categories
    categories: set[str] = set()
    for child in ast.iter_child_nodes(node):
        categories |= _expr_taint(child, environment)
    return categories


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in target.elts:
            names.extend(_target_names(item))
        return names
    return []


def _scope_nodes(statements: Sequence[ast.stmt]) -> list[ast.AST]:
    result: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(statements))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        result.append(node)
        children = list(ast.iter_child_nodes(node))
        for child in reversed(children):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            stack.append(child)
    return result


def _scopes(tree: ast.Module) -> list[tuple[str, Sequence[ast.stmt], list[str]]]:
    scopes: list[tuple[str, Sequence[ast.stmt], list[str]]] = [("<module>", tree.body, [])]

    def visit(statements: Sequence[ast.stmt], prefix: list[str]) -> None:
        for statement in statements:
            if isinstance(statement, ast.ClassDef):
                visit(statement.body, [*prefix, statement.name])
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = ".".join([*prefix, statement.name])
                arguments = [argument.arg for argument in statement.args.posonlyargs]
                arguments += [argument.arg for argument in statement.args.args]
                arguments += [argument.arg for argument in statement.args.kwonlyargs]
                if statement.args.vararg:
                    arguments.append(statement.args.vararg.arg)
                if statement.args.kwarg:
                    arguments.append(statement.args.kwarg.arg)
                scopes.append((name, statement.body, arguments))
                visit(statement.body, [*prefix, statement.name])

    visit(tree.body, [])
    return scopes


def _scope_environment(nodes: Sequence[ast.AST], arguments: Sequence[str]) -> dict[str, set[str]]:
    environment: dict[str, set[str]] = {
        name: _name_categories(name) for name in arguments if _name_categories(name)
    }
    for node in nodes:
        if isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
            environment.setdefault(node.name, set()).add("exception")

    for _iteration in range(max(1, len(nodes) + 1)):
        changed = False
        for node in nodes:
            value: ast.AST | None = None
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                value, targets = node.value, list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.AugAssign):
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                value, targets = node.iter, [node.target]
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                value, targets = node.context_expr, [node.optional_vars]
            if value is None or not targets:
                continue
            categories = _expr_taint(value, environment)
            for target in targets:
                for name in _target_names(target):
                    propagated = categories | _name_categories(name)
                    current = environment.setdefault(name, set())
                    before = len(current)
                    current |= propagated
                    changed = changed or len(current) != before
        if not changed:
            break
    return environment


def _diagnostic_record(
    relative_path: str,
    function: str,
    node: ast.AST,
    sink: str,
    categories: set[str],
) -> dict[str, Any]:
    return {
        "categories": sorted(categories),
        "file": relative_path,
        "fingerprint": _fingerprint(node),
        "function": function,
        "review_line": getattr(node, "lineno", 0),
        "sink": sink,
    }


def _scan_diagnostic_tree(tree: ast.Module, relative_path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for function, statements, arguments in _scopes(tree):
        nodes = _scope_nodes(statements)
        environment = _scope_environment(nodes, arguments)
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                value = getattr(node, "value", None)
                categories = _expr_taint(value, environment)
                if categories and any(
                    _session_subscript_key(target) is not None
                    for target in _assignment_targets(node)
                ):
                    records.append(
                        _diagnostic_record(
                            relative_path,
                            function,
                            node,
                            "session_state.write",
                            categories,
                        )
                    )
            if not isinstance(node, ast.Call):
                continue
            called = _qualname(node.func)
            last = called.rsplit(".", 1)[-1]
            sink: str | None = None
            categories: set[str] = set()

            # These are direct user-surface payload sinks, not generic method
            # names.  ``st.code`` and ``st.json`` can expose arbitrary artifact
            # bodies even when lexical taint cannot infer a sensitive name.
            # Download buttons are keyed to their data argument so a harmless
            # label or filename cannot hide an unreviewed payload.
            if called in {"st.code", "st.json"}:
                payload = _call_argument(node, 0, "body")
                categories = _expr_taint(payload, environment)
                categories.add("user_surface_payload")
                sink = called
            elif last == "download_button":
                payload = _call_argument(node, 1, "data")
                categories = _expr_taint(payload, environment)
                categories.add("download_payload")
                sink = f"{called or last}.data"
            else:
                for argument in node.args:
                    categories |= _expr_taint(argument, environment)
                for keyword in node.keywords:
                    categories |= _expr_taint(keyword.value, environment)
                if called == "st.session_state.update":
                    sink = "session_state.write"
                elif last in _UI_SINKS:
                    sink = called or last
                elif last in _COLLECTION_SINKS:
                    sink = f"collection.{last}"
                elif last in _PERSISTENCE_SINKS:
                    sink = f"persistence.{last}"
                elif any(part in last.lower() for part in ("save", "persist", "store")):
                    sink = f"persistence.{last}"

            if not categories:
                continue
            if sink is not None:
                records.append(
                    _diagnostic_record(relative_path, function, node, sink, categories)
                )

    records.sort(
        key=lambda item: (
            item["file"], item["review_line"], item["function"], item["sink"], item["fingerprint"]
        )
    )
    occurrences: defaultdict[tuple[str, ...], int] = defaultdict(int)
    for item in records:
        key = (item["file"], item["function"], item["sink"], item["fingerprint"])
        occurrences[key] += 1
        item["occurrence"] = occurrences[key]
        item["site_id"] = "|".join((*key, str(item["occurrence"])))
    return records


def scan_ui_source(source: str, relative_path: str) -> dict[str, list[dict[str, Any]]]:
    """Scan one source string without importing it.

    This public seam exists for mutation tests and future scanner fixtures.
    """

    safe_path = _safe_relative_path(relative_path)
    tree = _parse(source, safe_path)
    context = _context_index(tree)
    return {
        "diagnostics": _scan_diagnostic_tree(tree, safe_path),
        "unsafe_html": _scan_unsafe_tree(tree, safe_path, context),
    }


def analyze_sources(app_source: str, ui_sources: Mapping[str, str]) -> dict[str, Any]:
    """Build and validate the complete contract from in-memory source strings."""

    normalized_sources: dict[str, str] = {}
    for path, source in ui_sources.items():
        safe_path = _safe_relative_path(str(path))
        if not safe_path.startswith("ui/") or not safe_path.endswith(".py"):
            raise InventoryError(f"UI source is outside ui/**/*.py: {safe_path}")
        if safe_path in normalized_sources:
            raise InventoryError(f"duplicate UI source path: {safe_path}")
        normalized_sources[safe_path] = source
    if not normalized_sources:
        raise InventoryError("no ui/**/*.py sources found")

    app_tree = _parse(app_source, "app.py")
    trees = {path: _parse(source, path) for path, source in sorted(normalized_sources.items())}
    pages, groups = _parse_pages(app_tree)
    wiring = _validate_registry_wiring(app_tree)
    page_keys = {page["registry_key"] for page in pages}
    routes, actions = _scan_routes(trees, page_keys)
    accesses = _scan_session_accesses(trees, actions)
    handoffs = _build_handoffs(accesses)

    unsafe_html = _scan_unsafe_tree(app_tree, "app.py", _context_index(app_tree))
    diagnostics = _scan_diagnostic_tree(app_tree, "app.py")
    for path, tree in sorted(trees.items()):
        context = _context_index(tree)
        unsafe_html.extend(_scan_unsafe_tree(tree, path, context))
        diagnostics.extend(_scan_diagnostic_tree(tree, path))
    unsafe_html.sort(key=lambda item: (item["file"], item["review_line"], item["site_id"]))
    diagnostics.sort(key=lambda item: (item["file"], item["review_line"], item["site_id"]))
    site_ids = [item["site_id"] for item in unsafe_html]
    if len(site_ids) != len(set(site_ids)):
        raise InventoryError("unsafe HTML semantic site IDs are not unique")
    diagnostic_ids = [item["site_id"] for item in diagnostics]
    if len(diagnostic_ids) != len(set(diagnostic_ids)):
        raise InventoryError("diagnostic semantic site IDs are not unique")
    if not unsafe_html:
        raise InventoryError("unsafe HTML inventory is unexpectedly empty")
    if not diagnostics:
        raise InventoryError("diagnostic inventory is unexpectedly empty")

    bookmarks = sorted(page["route"] for page in pages if not page["default"])
    return {
        "diagnostics": diagnostics,
        "handoffs": handoffs,
        "navigation": {
            "bookmark_routes": bookmarks,
            "default_registry_key": EXPECTED_DEFAULT_KEY,
            "groups": groups,
            "registry_wiring": wiring,
            "root_route": "/",
        },
        "pages": pages,
        "same_session_routes": routes,
        "schema_version": SCHEMA_VERSION,
        "source_roots": ["app.py", "ui/**/*.py"],
        "unsafe_html": unsafe_html,
    }


def build_inventory(root: Path | str | None = None) -> dict[str, Any]:
    """Read the fixed source roots and return a validated repository inventory."""

    repository = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    repository = repository.resolve()
    app_path = repository / "app.py"
    ui_root = repository / "ui"
    try:
        app_source = app_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InventoryError(f"cannot read app.py: {exc.strerror or type(exc).__name__}") from None
    try:
        ui_paths = sorted(ui_root.rglob("*.py"))
        ui_sources = {
            path.relative_to(repository).as_posix(): path.read_text(encoding="utf-8")
            for path in ui_paths
        }
    except (OSError, ValueError) as exc:
        detail = exc.strerror if isinstance(exc, OSError) else str(exc)
        raise InventoryError(f"cannot read ui/**/*.py: {detail or type(exc).__name__}") from None
    return analyze_sources(app_source, ui_sources)


def baseline_contract(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return the location-free portion that is equality-pinned in UX-0.

    ``review_line`` remains useful when a human inspects a fresh inventory, but
    line movement alone is not a UI contract change.  Everything else in the
    reviewed inventory is retained so additions, removals, or semantic changes
    require an intentional baseline update.
    """

    required = (
        "diagnostics",
        "handoffs",
        "navigation",
        "pages",
        "same_session_routes",
        "schema_version",
        "source_roots",
        "unsafe_html",
    )
    missing = [key for key in required if key not in result]
    if missing:
        raise InventoryError("inventory missing baseline keys: " + ", ".join(missing))

    def location_free(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): location_free(item)
                for key, item in value.items()
                if key != "review_line"
            }
        if isinstance(value, list):
            return [location_free(item) for item in value]
        return value

    contract = {key: location_free(result[key]) for key in required}

    # Source order is meaningful for pages/groups because it is the visible
    # navigation order.  Scanner findings and handoff access sites are sets,
    # however, so canonicalize them after removing review-only locations.
    contract["unsafe_html"] = sorted(
        contract["unsafe_html"], key=lambda item: item["site_id"]
    )
    contract["diagnostics"] = sorted(
        contract["diagnostics"], key=lambda item: item["site_id"]
    )
    routes = contract["same_session_routes"]
    routes["forms"] = sorted(routes["forms"])
    routes["targets"] = sorted(routes["targets"])
    routes["sites"] = sorted(routes["sites"], key=canonical_json)
    for handoff in contract["handoffs"]:
        handoff["keys"] = sorted(handoff["keys"], key=lambda item: item["key"])
        for key_contract in handoff["keys"]:
            for collection in ("accesses", "consumer_sites", "producer_sites"):
                key_contract[collection] = sorted(
                    key_contract[collection], key=canonical_json
                )
    contract["handoffs"] = sorted(
        contract["handoffs"], key=lambda item: (item["name"], item["target"])
    )
    contract["source_roots"] = sorted(contract["source_roots"])
    return contract


def compatibility_contract(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the UX-0 fields intentionally protected across safety phases."""

    contract = baseline_contract(result)
    return {key: contract[key] for key in UX0_COMPATIBILITY_FIELDS}


def contract_sha256(result: Mapping[str, Any]) -> str:
    """Return the canonical digest used by versioned post-UX-0 contracts."""

    payload = canonical_json(baseline_contract(result)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_classified_unsafe_sites(
    result: Mapping[str, Any], classified_site_ids: Iterable[str]
) -> None:
    """Fail closed when current unsafe HTML is absent from an accepted ledger."""

    known = {str(site_id) for site_id in classified_site_ids}
    current = {
        str(item.get("site_id"))
        for item in result.get("unsafe_html", [])
        if isinstance(item, Mapping) and item.get("site_id")
    }
    missing = current - known
    if missing:
        raise InventoryError(
            f"new unclassified unsafe HTML sites found: {len(missing)}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory Quant Radar's static Streamlit UI contract without importing the app.",
        epilog=(
            "Examples:\n"
            "  ui_ux_inventory.py\n"
            "  ui_ux_inventory.py --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="write canonical machine-readable JSON to stdout",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ui_ux_inventory {VERSION}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_inventory()
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # Defensive CLI boundary: never leak source/runtime payloads.
        print(
            f"error: unexpected inventory failure ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    try:
        if args.json:
            print(canonical_json(result))
        else:
            print("Quant Radar UI/UX contract inventory")
            print(f"Pages: {len(result['pages'])} in {len(result['navigation']['groups'])} groups")
            print(f"Same-session targets: {len(result['same_session_routes']['targets'])}")
            print(f"Handoff contracts: {len(result['handoffs'])}")
            print(f"Unsafe HTML sites: {len(result['unsafe_html'])}")
            print(f"Diagnostic candidates: {len(result['diagnostics'])}")
        return 0
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
