#!/usr/bin/env python3
"""Commit reports and push them through a bounded clean-worktree rebase loop."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result


def _stash_runtime_outputs(repo: Path) -> bool:
    if not _git(repo, "status", "--porcelain").stdout.strip():
        return False
    _git(repo, "stash", "push", "--include-untracked", "--message",
         "surge-runtime-before-report-push")
    remaining = _git(repo, "status", "--porcelain").stdout.strip()
    if remaining:
        raise RuntimeError(f"worktree remains dirty before rebase: {remaining}")
    return True


def _runtime_outputs_present(repo: Path) -> bool:
    if _git(repo, "diff", "--quiet", check=False).returncode:
        return True
    return bool(_git(repo, "ls-files", "--others", "--exclude-standard").stdout.strip())


def publish_reports(
    *,
    repo: str | Path = ".",
    remote: str = "origin",
    branch: str = "main",
    message: str,
    attempts: int = 3,
    allow_runtime_stash: bool = False,
) -> dict[str, Any]:
    root = Path(repo).resolve()
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    _git(root, "config", "user.name", "surge-screener-bot")
    _git(root, "config", "user.email", "bot@users.noreply.github.com")
    _git(root, "add", "reports/")
    if _git(root, "diff", "--staged", "--quiet", check=False).returncode == 0:
        return {"status": "nothing_to_commit", "attempts": 0, "runtime_stashed": False}

    staged_paths = _git(root, "diff", "--staged", "--name-only").stdout.splitlines()
    unexpected_staged = [path for path in staged_paths if not path.startswith("reports/")]
    if unexpected_staged:
        raise RuntimeError(
            "refusing to publish with staged paths outside reports/: "
            + ", ".join(unexpected_staged)
        )
    if _runtime_outputs_present(root) and not allow_runtime_stash:
        raise RuntimeError(
            "refusing to stash local changes; --ephemeral-runner is required "
            "for disposable CI runtime outputs"
        )

    _git(root, "commit", "-m", message)
    runtime_stashed = _stash_runtime_outputs(root)

    for attempt in range(1, attempts + 1):
        pushed = _git(root, "push", remote, f"HEAD:{branch}", check=False)
        if pushed.returncode == 0:
            return {
                "status": "pushed",
                "attempts": attempt,
                "runtime_stashed": runtime_stashed,
                "commit": _git(root, "rev-parse", "HEAD").stdout.strip(),
            }
        if attempt == attempts:
            detail = (pushed.stderr or pushed.stdout).strip()
            raise RuntimeError(f"git push failed after {attempts} attempts: {detail}")
        _git(root, "fetch", remote, branch)
        rebased = _git(root, "rebase", "FETCH_HEAD", check=False)
        if rebased.returncode:
            _git(root, "rebase", "--abort", check=False)
            detail = (rebased.stderr or rebased.stdout).strip()
            raise RuntimeError(f"git rebase failed after push race: {detail}")
    raise AssertionError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish generated reports safely")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", required=True)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--ephemeral-runner",
        action="store_true",
        help="allow runtime-only changes to be stashed and left on a disposable CI runner",
    )
    args = parser.parse_args(argv)
    result = publish_reports(
        repo=args.repo,
        remote=args.remote,
        branch=args.branch,
        message=args.message,
        attempts=args.attempts,
        allow_runtime_stash=args.ephemeral_runner,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
