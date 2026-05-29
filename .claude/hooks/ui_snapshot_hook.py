#!/usr/bin/env python3
"""PostToolUse hook: after editing a UI file, refresh a screenshot of that page.

Wired in .claude/settings.json on Edit|Write. Reads the hook payload from stdin,
and if the edited file is app.py or a ui/ page module AND the Streamlit app is
reachable on :8501, it launches scripts/ui_snapshot.py in the BACKGROUND (so the
edit isn't blocked by a ~4s render) and writes the PNG to .claude/ui_snapshots/<page>.png. If the app isn't running,
it no-ops silently.

The render runs synchronously (with a timeout) and the hook reports the REAL
outcome — it only prints success after confirming the PNG was actually written,
so it can't claim a snapshot that doesn't exist. The trade-off is a few seconds
added to a UI-file edit while the app is up; that's exactly when you want the
fresh render anyway.

This closes the edit -> see loop: every UI tweak drops a fresh render you (and
Claude) can open, instead of guessing at the result.
"""

import json
import os
import subprocess
import sys
import urllib.request

PORT = 8501
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ui/<module>.py -> page url_path. Modules not listed (or app.py) fall back to the
# landing page, which always renders. Keep in sync with app.py's st.navigation().
PAGE_MAP = {
    # us_screener is st.navigation's default=True page, served at root "/".
    # Hitting its explicit "/us-screener" url_path flashes a "Page not found"
    # dialog, so preview it at root.
    "us_screener": "",
    "us_options": "us-options",
    "us_cot": "us-cot",
    "crypto_universe": "crypto-universe",
    "crypto_screener": "crypto-screener",
    "influencers": "influencers",
    "sys_schedules": "schedules",
    "sys_ai_updates": "ai-updates",
    "x_sentiment": "us-x",  # shared page; preview the US instance
}


def edited_path(payload: dict) -> str:
    ti = payload.get("tool_input") or {}
    return ti.get("file_path") or ti.get("path") or ""


def app_is_up() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{PORT}/_stcore/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never block edits on a malformed payload

    path = edited_path(payload)
    if not path.endswith(".py"):
        return 0
    # Match by path components, not relpath-against-ROOT: macOS is case-insensitive
    # but Python string compares aren't, so an "AI" vs "ai" prefix would break a
    # relpath check. The edited file is in scope iff it's app.py or lives under a
    # `ui/` directory.
    base = os.path.basename(path)
    parts = os.path.normpath(path).split(os.sep)
    is_ui = base == "app.py" or "ui" in parts[:-1]
    if not is_ui or base in ("__init__.py", "_shared.py"):
        return 0
    if not app_is_up():
        return 0  # nothing to screenshot; stay quiet

    module = os.path.splitext(os.path.basename(path))[0]
    page = PAGE_MAP.get(module, "")
    out_dir = os.path.join(ROOT, ".claude", "ui_snapshots")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{page or 'home'}.png")

    venv_py = os.path.join(ROOT, ".venv", "bin", "python")
    py = venv_py if os.path.exists(venv_py) else sys.executable
    label = page or "home"
    # Run synchronously and verify: only claim success if the PNG actually lands.
    # A detached background launch would let us print "done" before the render
    # could fail (app drops after the health check, playwright errors, timeout),
    # silently claiming a screenshot that never exists.
    try:
        before = os.path.getmtime(out) if os.path.exists(out) else 0
        proc = subprocess.run(
            [py, os.path.join(ROOT, "scripts", "ui_snapshot.py"),
             "--page", page, "--out", out, "--port", str(PORT),
             "--settle-ms", "1200"],
            capture_output=True, text=True, timeout=45,
        )
    except subprocess.TimeoutExpired:
        print(f"⚠️ UI snapshot timed out (page: {label}); no fresh screenshot written")
        return 0
    fresh = os.path.exists(out) and os.path.getmtime(out) > before
    if proc.returncode == 0 and fresh:
        print(f"📸 UI snapshot updated → .claude/ui_snapshots/{label}.png")
    else:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        why = tail[-1] if tail else f"exit {proc.returncode}, no new file"
        print(f"⚠️ UI snapshot NOT updated (page: {label}): {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
