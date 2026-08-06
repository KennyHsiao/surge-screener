#!/usr/bin/env python3
"""Phase 6S-6U public-read convergence and private-boundary guard."""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from pathlib import Path

import test_ui_backend_boundary as boundary


ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
AUDIT = ROOT / "docs/api/frontend-backend-separation-phase6s-6u-audit.md"
IO_CALLS = frozenset(
    {
        "connect",
        "glob",
        "iterdir",
        "open",
        "read_bytes",
        "read_text",
        "rglob",
        "write_bytes",
        "write_text",
    }
)


@dataclass(frozen=True)
class SeparationInventory:
    direct_bindings: int
    direct_modules: int
    shared_importers: int
    load_json_modules: int
    load_json_calls: int
    direct_io_modules: int
    direct_io_calls: int


POST_6R_CEILING = SeparationInventory(
    direct_bindings=61,
    direct_modules=20,
    shared_importers=30,
    load_json_modules=14,
    load_json_calls=20,
    direct_io_modules=10,
    direct_io_calls=19,
)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _imports_shared(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "ui._shared" for alias in node.names)
    if not isinstance(node, ast.ImportFrom):
        return False
    if node.level == 1:
        return any(alias.name == "_shared" for alias in node.names)
    if node.level != 0:
        return False
    return node.module == "ui._shared" or (
        node.module == "ui" and any(alias.name == "_shared" for alias in node.names)
    )


def _inventory(ui_dir: Path = UI_DIR) -> SeparationInventory:
    script_bindings: set[tuple[str, str]] = set()
    script_modules: set[str] = set()
    shared_importers: set[str] = set()
    load_json_modules: set[str] = set()
    direct_io_modules: set[str] = set()
    load_json_calls = 0
    direct_io_calls = 0

    for path in sorted(ui_dir.glob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )
        imports = boundary._script_imports(path)
        if imports:
            script_bindings.update(imports)
            script_modules.add(relative)
        for node in ast.walk(tree):
            if _imports_shared(node):
                shared_importers.add(relative)
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "load_json":
                load_json_calls += 1
                load_json_modules.add(relative)
            if name in IO_CALLS:
                direct_io_calls += 1
                direct_io_modules.add(relative)

    return SeparationInventory(
        direct_bindings=len(script_bindings),
        direct_modules=len(script_modules),
        shared_importers=len(shared_importers),
        load_json_modules=len(load_json_modules),
        load_json_calls=load_json_calls,
        direct_io_modules=len(direct_io_modules),
        direct_io_calls=direct_io_calls,
    )


def _assert_not_above(
    actual: SeparationInventory,
    ceiling: SeparationInventory = POST_6R_CEILING,
) -> None:
    growth = {
        field.name: (getattr(actual, field.name), getattr(ceiling, field.name))
        for field in fields(SeparationInventory)
        if getattr(actual, field.name) > getattr(ceiling, field.name)
    }
    if growth:
        raise AssertionError(f"frontend/backend residual inventory grew: {growth}")


def test_post_6r_inventory_is_reproducible_and_can_only_shrink() -> None:
    actual = _inventory()
    _assert_not_above(actual)
    if actual.direct_bindings != len(boundary.LEGACY_SCRIPT_IMPORTS):
        raise AssertionError(
            "summary inventory and exact backend allowlist disagree: "
            f"{actual.direct_bindings} != {len(boundary.LEGACY_SCRIPT_IMPORTS)}"
        )


def test_convergence_guard_accepts_shrinkage_and_rejects_growth() -> None:
    smaller = SeparationInventory(*(value - 1 for value in POST_6R_CEILING.__dict__.values()))
    _assert_not_above(smaller)
    larger = SeparationInventory(
        direct_bindings=POST_6R_CEILING.direct_bindings + 1,
        direct_modules=POST_6R_CEILING.direct_modules,
        shared_importers=POST_6R_CEILING.shared_importers,
        load_json_modules=POST_6R_CEILING.load_json_modules,
        load_json_calls=POST_6R_CEILING.load_json_calls,
        direct_io_modules=POST_6R_CEILING.direct_io_modules,
        direct_io_calls=POST_6R_CEILING.direct_io_calls,
    )
    try:
        _assert_not_above(larger)
    except AssertionError:
        pass
    else:
        raise AssertionError("convergence guard accepted inventory growth")


def test_retained_families_and_private_entry_gate_are_documented() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    required = (
        "Private account and decision state",
        "Operational controls and diagnostics",
        "Live providers",
        "Writable review and session state",
        "Unstable or compatibility-only sources",
        "paths/globs",
        "SQL",
        "credentials",
        "logs/prompts/chat sessions",
        "provider execution",
        "job controls",
        "writes",
        "deployment audience",
        "identity",
        "authorization",
        "revision/ETag",
        "If-Match",
        "idempotency",
        "atomic",
        "crash recovery",
        "BLOCKED",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise AssertionError(f"convergence/private-boundary audit is incomplete: {missing}")


def test_api_slice_and_deployment_topology_receipts_stay_converged() -> None:
    inventory = (ROOT / "docs/api/fastapi-endpoint-artifact-inventory.md").read_text(
        encoding="utf-8"
    )
    guide = (ROOT / "docs/USER_GUIDE.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    api_service = (ROOT / "deploy/surge-screener-api.service").read_text(encoding="utf-8")
    app_service = (ROOT / "deploy/surge-screener.service").read_text(encoding="utf-8")
    if "fifty-four migrated API-only Streamlit slices" not in inventory:
        raise AssertionError("endpoint inventory lost the 54-slice receipt")
    if "五十四個 API-only" not in guide:
        raise AssertionError("user guide lost the 54-slice receipt")
    if "version: 1.23.0-draft" not in spec:
        raise AssertionError("private pilot API contract version drifted")
    if 'network_mode: "service:api"' not in compose:
        raise AssertionError("Compose no longer shares the loopback API network namespace")
    if "--host 127.0.0.1 --port 8000" not in api_service:
        raise AssertionError("systemd API is no longer fixed to loopback")
    if "Requires=surge-screener-api.service" not in app_service:
        raise AssertionError("Streamlit no longer requires the API service")


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    main()
