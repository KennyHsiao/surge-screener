#!/usr/bin/env python3
"""Phase 7D no-delete Industry Roles legacy retirement gate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LEGACY_NAMES = {
    "industry_role_overrides.json",
    "industry_role_suggestions.json",
}
ALLOWED_PRODUCTION_OWNERS = {
    "api/main.py",
    "scripts/industry_role_admin.py",
    "scripts/industry_roles.py",
}
RETIREMENT_DOC = ROOT / "docs/api/industry-role-legacy-retirement-gate.md"
DECISION_DOC = ROOT / "docs/api/industry-role-retirement-decision.md"


def _production_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in ("api", "clients", "scripts", "ui"):
        for path in (ROOT / directory).glob("*.py"):
            if path.name.startswith("test_") or path.name.startswith("ui_ux_"):
                continue
            files.append(path)
    return files


def test_legacy_filenames_have_only_declared_compatibility_owners() -> None:
    owners: set[str] = set()
    for path in _production_python_files():
        source = path.read_text(encoding="utf-8")
        if any(name in source for name in LEGACY_NAMES):
            owners.add(str(path.relative_to(ROOT)))
    assert owners == ALLOWED_PRODUCTION_OWNERS, owners


def test_converged_consumers_do_not_import_or_read_legacy_role_files() -> None:
    for relative in (
        "scripts/eastmoney_money_flow.py",
        "scripts/universe_refresh.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "load_approved_tickers" in source, relative
        assert not any(name in source for name in LEGACY_NAMES), relative


def test_retirement_gate_is_ready_decision_only_and_implements_no_deletion() -> None:
    text = RETIREMENT_DOC.read_text(encoding="utf-8")
    decision = DECISION_DOC.read_text(encoding="utf-8")
    assert "Current verdict: **READY**" in text
    assert "Decision record: `industry-role-retirement-decision.md`" in text
    assert "`2026-08-11T15:27:42Z`" in text
    assert "`READY` does not authorize" in text
    assert "Status | `READY — DECISION RECORD ONLY`" in decision
    assert "Evidence release: 4d5812726bd245e55046368f42fd738a88f80cb7" in decision
    assert "does not authorize archive, move, rewrite" in decision
    guide = (ROOT / "docs/USER_GUIDE.md").read_text(encoding="utf-8")
    inventory = (ROOT / "docs/api/fastapi-endpoint-artifact-inventory.md").read_text(encoding="utf-8")
    assert "dated Phase 7I evidence decision gate 為 `READY`" in guide
    assert "dated Phase 7I evidence decision is `READY`" in inventory
    admin_source = (ROOT / "scripts/industry_role_admin.py").read_text(encoding="utf-8")
    assert '"retirement": {"verdict": "HOLD"}' in admin_source
    for destructive in (".unlink(", "os.remove(", "os.unlink(", "shutil.rmtree("):
        assert destructive not in admin_source, destructive


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
