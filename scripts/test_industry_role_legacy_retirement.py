#!/usr/bin/env python3
"""R3 no-delete Industry Roles legacy retirement gate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LEGACY_NAMES = {
    "industry_role_overrides.json",
    "industry_role_suggestions.json",
}
ALLOWED_PRODUCTION_OWNERS: set[str] = set()
RETIRED_EXPORT_SYMBOLS = {
    "EXPORT_MANIFEST_FILE",
    "LegacyExport",
    "export_status",
    "legacy_export_manifest_path",
    "export_review_state_to_legacy",
    "export-legacy",
    "review-state.export.json",
}
RETIREMENT_DOC = ROOT / "docs/api/industry-role-legacy-retirement-gate.md"
DECISION_DOC = ROOT / "docs/api/industry-role-retirement-decision.md"
CONTINUITY_DOC = ROOT / "docs/api/industry-role-retirement-continuity-2026-08-12.md"


def _production_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in ("api", "clients", "scripts", "ui"):
        for path in (ROOT / directory).rglob("*.py"):
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
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert not any(name in ignore for name in LEGACY_NAMES), ignore


def test_export_surface_is_absent_from_production_python() -> None:
    matches: dict[str, list[str]] = {}
    for path in _production_python_files():
        source = path.read_text(encoding="utf-8")
        found = sorted(symbol for symbol in RETIRED_EXPORT_SYMBOLS if symbol in source)
        if found:
            matches[str(path.relative_to(ROOT))] = found
    assert matches == {}, matches


def test_converged_consumers_do_not_import_or_read_legacy_role_files() -> None:
    for relative in (
        "scripts/eastmoney_money_flow.py",
        "scripts/universe_refresh.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "load_approved_tickers" in source, relative
        assert not any(name in source for name in LEGACY_NAMES), relative

    for relative in (
        "api/industry_roles.py",
        "api/main.py",
        "scripts/industry_role_store.py",
        "scripts/industry_roles.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert not any(name in source for name in LEGACY_NAMES), relative
    api_main = (ROOT / "api/main.py").read_text(encoding="utf-8")
    assert "industry_role_overrides_path" not in api_main
    assert "industry_role_suggestions_path" not in api_main


def test_r3_retirement_is_authorized_bounded_and_non_destructive() -> None:
    text = RETIREMENT_DOC.read_text(encoding="utf-8")
    decision = DECISION_DOC.read_text(encoding="utf-8")
    continuity = CONTINUITY_DOC.read_text(encoding="utf-8")
    assert "Current verdict: **R3 RETIRED**" in text
    assert "Decision record: `industry-role-retirement-decision.md`" in text
    assert "`2026-08-11T15:27:42Z`" in text
    assert "R3 does not authorize" in text
    assert "Status | `R3 AUTHORIZED — NO DELETE`" in decision
    assert "Evidence release: 4d5812726bd245e55046368f42fd738a88f80cb7" in decision
    assert "`v1.3`" in decision
    assert "824f5465fc97c74a5cbea8f493f427b2541df565" in decision
    assert "Status: **PASS — OWNER-ATTESTED READ-ONLY RECHECK**" in continuity
    assert "`2026-08-12T13:23:00Z`" in continuity
    assert "none found" in continuity
    assert "industry-role-retirement-r2-evidence-2026-08-15.md" in text
    assert "Automatic runtime reads are retired in R1" in text
    assert "explicit emergency export is retired in R3" in " ".join(text.split())
    assert "does not authorize archive, move, rewrite" in decision
    guide = (ROOT / "docs/USER_GUIDE.md").read_text(encoding="utf-8")
    inventory = (ROOT / "docs/api/fastapi-endpoint-artifact-inventory.md").read_text(encoding="utf-8")
    assert "dated Phase 7I evidence decision gate 為 `READY`" in guide
    assert "自動 legacy fallback 已由 R1 移除" in guide
    assert "R3 已移除 `export-legacy`" in guide
    assert "dated Phase 7I evidence decision is `READY`" in inventory
    assert "automatic legacy reads are retired" in inventory.lower()
    assert "R3 removes the explicit export" in inventory
    admin_source = (ROOT / "scripts/industry_role_admin.py").read_text(encoding="utf-8")
    assert '"retirement"' not in admin_source
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
