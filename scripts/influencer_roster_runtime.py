"""Runtime path helpers for the editable X influencer roster.

The repository keeps content/influencers.json as the seed/default roster. Runtime
edits should live outside replaceable release directories so Docker rebuilds and
test-server deployments do not erase user-maintained handles.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROSTER_PATH = REPO_ROOT / "content" / "influencers.json"
ROSTER_ENV = "SURGE_INFLUENCERS_PATH"


def seed_roster_file(path: str | Path, *, default_path: str | Path = DEFAULT_ROSTER_PATH) -> Path:
    """Create a missing runtime roster from the repository seed roster."""

    dst = Path(path).expanduser()
    if dst.exists() or dst.is_symlink():
        return dst

    dst.parent.mkdir(parents=True, exist_ok=True)
    src = Path(default_path).expanduser()
    if src.exists():
        shutil.copyfile(src, dst)
    else:
        dst.write_text(
            json.dumps({"categories_order": [], "influencers": []}, indent=2) + "\n",
            encoding="utf-8",
        )
    return dst


def resolve_roster_path(
    *,
    env: Mapping[str, str] | None = None,
    default_path: str | Path = DEFAULT_ROSTER_PATH,
    seed: bool = True,
) -> Path:
    """Return the editable roster path, seeding runtime storage when configured."""

    runtime_env = os.environ if env is None else env
    configured = str(runtime_env.get(ROSTER_ENV) or "").strip()
    if configured:
        path = Path(os.path.expandvars(configured)).expanduser()
        return seed_roster_file(path, default_path=default_path) if seed else path

    app_root = str(runtime_env.get("SURGE_APP_ROOT") or "").strip()
    if app_root:
        path = Path(os.path.expandvars(app_root)).expanduser() / "shared" / "content" / "influencers.json"
        return seed_roster_file(path, default_path=default_path) if seed else path

    return Path(default_path).expanduser()
