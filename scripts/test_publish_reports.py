#!/usr/bin/env python3
"""Regression tests for bounded report publication after a push race."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "publish_reports_under_test", ROOT / "scripts" / "publish_reports.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("scripts/publish_reports.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _configure(repo: Path) -> None:
    _git(repo, "config", "user.name", "test-bot")
    _git(repo, "config", "user.email", "test@example.invalid")


def test_publish_reports_rebases_with_dirty_runtime_outputs() -> None:
    publisher = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remote = root / "remote.git"
        seed = root / "seed"
        worker = root / "worker"
        concurrent = root / "concurrent"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "clone", str(remote), str(seed)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _configure(seed)
        (seed / "reports").mkdir()
        (seed / "reports" / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        (seed / "filtered_universe.json").write_text("baseline\n", encoding="utf-8")
        _git(seed, "add", "reports", "filtered_universe.json")
        _git(seed, "commit", "-m", "seed")
        _git(seed, "branch", "-M", "main")
        _git(seed, "push", "-u", "origin", "main")
        _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        for target in (worker, concurrent):
            subprocess.run(["git", "clone", str(remote), str(target)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _configure(target)

        (worker / "filtered_universe.json").write_text(
            "pre-existing stash\n", encoding="utf-8",
        )
        _git(worker, "stash", "push", "-m", "pre-existing operator stash")
        pre_existing_stash = _git(worker, "rev-parse", "refs/stash")
        report = worker / "reports" / "2026-08-15" / "summary.json"
        report.parent.mkdir()
        report.write_text('{"total_confirmed": 0}\n', encoding="utf-8")
        (worker / "filtered_universe.json").write_text("runtime-only\n", encoding="utf-8")
        (worker / "ranked_candidates.json").write_text("runtime-only\n", encoding="utf-8")

        (concurrent / "reports" / "concurrent.txt").write_text("remote\n", encoding="utf-8")
        _git(concurrent, "add", "reports/concurrent.txt")
        _git(concurrent, "commit", "-m", "concurrent report")
        _git(concurrent, "push")

        result = publisher.publish_reports(
            repo=worker,
            remote="origin",
            branch="main",
            message="report: 2026-08-15",
            attempts=3,
            allow_runtime_stash=True,
        )

        if result["status"] != "pushed" or result["attempts"] != 2:
            raise AssertionError(result)
        verify = root / "verify"
        subprocess.run(["git", "clone", str(remote), str(verify)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not (verify / "reports" / "2026-08-15" / "summary.json").is_file():
            raise AssertionError("daily report was not published")
        if not (verify / "reports" / "concurrent.txt").is_file():
            raise AssertionError("concurrent remote update was lost")
        if (verify / "filtered_universe.json").read_text() != "baseline\n":
            raise AssertionError("tracked runtime output leaked into report commit")
        if (verify / "ranked_candidates.json").exists():
            raise AssertionError("untracked runtime output leaked into report commit")
        if _git(worker, "rev-parse", "refs/stash") != pre_existing_stash:
            raise AssertionError("publisher removed or replaced a pre-existing stash")
        stash_lines = _git(worker, "stash", "list").splitlines()
        if len(stash_lines) != 1 or "pre-existing operator stash" not in stash_lines[0]:
            raise AssertionError(f"publisher-owned runtime stash leaked: {stash_lines}")


def test_publish_reports_refuses_to_stash_local_changes_by_default() -> None:
    publisher = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        subprocess.run(["git", "init", str(repo)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _configure(repo)
        (repo / "reports").mkdir()
        (repo / "reports" / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        (repo / "runtime.json").write_text("baseline\n", encoding="utf-8")
        _git(repo, "add", "reports", "runtime.json")
        _git(repo, "commit", "-m", "seed")
        baseline = _git(repo, "rev-parse", "HEAD")

        (repo / "reports" / "new.txt").write_text("report\n", encoding="utf-8")
        (repo / "runtime.json").write_text("local change\n", encoding="utf-8")
        try:
            publisher.publish_reports(repo=repo, message="report: unsafe")
        except RuntimeError as exc:
            if "refusing to stash local changes" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("publisher unexpectedly stashed local changes")

        if _git(repo, "rev-parse", "HEAD") != baseline:
            raise AssertionError("publisher committed before enforcing the local-safety gate")
        if (repo / "runtime.json").read_text(encoding="utf-8") != "local change\n":
            raise AssertionError("publisher changed the local runtime file")


def test_publish_reports_refuses_a_feature_source_ref_before_commit() -> None:
    publisher = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", str(repo)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _configure(repo)
        (repo / "reports").mkdir()
        (repo / "reports" / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        _git(repo, "add", "reports/baseline.txt")
        _git(repo, "commit", "-m", "feature code")
        baseline = _git(repo, "rev-parse", "HEAD")
        (repo / "reports" / "new.txt").write_text("report\n", encoding="utf-8")

        try:
            publisher.publish_reports(
                repo=repo,
                branch="main",
                message="report: unsafe feature ref",
                source_ref="refs/heads/feature/manual-run",
            )
        except RuntimeError as exc:
            if "workflow source must be 'refs/heads/main'" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("publisher unexpectedly promoted a feature ref to main")

        if _git(repo, "rev-parse", "HEAD") != baseline:
            raise AssertionError("publisher committed before enforcing the source-ref gate")


def test_publish_reports_aborts_and_fails_on_rebase_conflict() -> None:
    publisher = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remote = root / "remote.git"
        seed = root / "seed"
        worker = root / "worker"
        concurrent = root / "concurrent"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "clone", str(remote), str(seed)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _configure(seed)
        (seed / "reports").mkdir()
        (seed / "reports" / "shared.txt").write_text("baseline\n", encoding="utf-8")
        (seed / "runtime.json").write_text("baseline\n", encoding="utf-8")
        _git(seed, "add", "reports/shared.txt", "runtime.json")
        _git(seed, "commit", "-m", "seed")
        _git(seed, "branch", "-M", "main")
        _git(seed, "push", "-u", "origin", "main")
        _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        for target in (worker, concurrent):
            subprocess.run(["git", "clone", str(remote), str(target)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _configure(target)

        (worker / "reports" / "shared.txt").write_text("worker\n", encoding="utf-8")
        (worker / "runtime.json").write_text("runtime-only\n", encoding="utf-8")
        (concurrent / "reports" / "shared.txt").write_text("remote\n", encoding="utf-8")
        _git(concurrent, "add", "reports/shared.txt")
        _git(concurrent, "commit", "-m", "concurrent report")
        _git(concurrent, "push")

        try:
            publisher.publish_reports(
                repo=worker,
                message="report: conflict",
                attempts=3,
                allow_runtime_stash=True,
            )
        except RuntimeError as exc:
            if "git rebase failed after push race" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("publisher unexpectedly resolved a report conflict")

        if _git(worker, "status", "--porcelain"):
            raise AssertionError("publisher left the worktree dirty after rebase abort")
        if _git(worker, "stash", "list"):
            raise AssertionError("publisher-owned runtime stash leaked after a failed push")


if __name__ == "__main__":
    test_publish_reports_rebases_with_dirty_runtime_outputs()
    test_publish_reports_refuses_to_stash_local_changes_by_default()
    test_publish_reports_refuses_a_feature_source_ref_before_commit()
    test_publish_reports_aborts_and_fails_on_rebase_conflict()
    print("publish reports tests: 4 passed")
