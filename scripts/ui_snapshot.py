#!/usr/bin/env python3
"""Screenshot one Quant Radar page for visual UI/UX review.

Streamlit renders over a websocket, so `curl /` and headless-Chrome
`--virtual-time-budget` only capture the loading skeleton. This drives the
running app with Playwright, waits for a real element (the sidebar nav, not the
skeleton), lets plotly paint, then saves a full-page PNG.

It does NOT launch Streamlit — start the app first (see the run-dashboard skill
or `streamlit run app.py`). If the app isn't reachable it exits non-zero with a
clear message so callers (hooks, the polish-page skill) can no-op gracefully.

Usage:
    .venv/bin/python scripts/ui_snapshot.py --page us-screener --out /tmp/x.png
    .venv/bin/python scripts/ui_snapshot.py            # home page -> ./ui_snapshot.png

Page url_paths come from app.py's st.navigation(): us-screener, us-options,
us-cot, us-x, crypto-universe, crypto-screener, crypto-x, influencers,
schedules, ai-updates. Empty/"" = the default landing page.

`us-screener` is st.navigation's default=True page, which Streamlit serves at
root "/" — requesting its explicit "/us-screener" url_path flashes a "Page not
found" dialog. We normalize it (and "") to root so callers can pass either form
safely.
"""

from __future__ import annotations

import argparse
import sys

# The default=True page in app.py (served at "/", not at its url_path).
DEFAULT_PAGE = "us-screener"


def snapshot(page: str, out: str, port: int, width: int, height: int,
             settle_ms: int) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("✗ playwright not installed in this interpreter. Run:\n"
              "  .venv/bin/pip install playwright && "
              ".venv/bin/python -m playwright install chromium", file=sys.stderr)
        return 2

    # Normalize the default page (and empty) to root to avoid the "Page not
    # found" flash on its explicit url_path.
    if page.strip("/").lower() in ("", DEFAULT_PAGE):
        page = ""
    url = f"http://localhost:{port}/{page.lstrip('/')}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page(viewport={"width": width, "height": height})
            pg.goto(url, wait_until="networkidle", timeout=30000)
            # Wait for the real app chrome, not the loading skeleton.
            pg.wait_for_selector('[data-testid="stSidebarNav"]', timeout=20000)
            pg.wait_for_timeout(settle_ms)  # let plotly/charts paint
            pg.screenshot(path=out, full_page=True)
            title = pg.title()
            browser.close()
    except Exception as e:  # connection refused, timeout, etc.
        print(f"✗ could not render {url}: {type(e).__name__}: {e}\n"
              "  Is the app running? Start it first "
              "(streamlit run app.py --server.port "
              f"{port}).", file=sys.stderr)
        return 1

    print(f"✓ {title} @ {url}\n  saved: {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Screenshot a Quant Radar page.")
    ap.add_argument("--page", default="", help="url_path, e.g. us-screener (empty=home)")
    ap.add_argument("--out", default="ui_snapshot.png", help="output PNG path")
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--width", type=int, default=1500)
    ap.add_argument("--height", type=int, default=1600)
    ap.add_argument("--settle-ms", type=int, default=2500,
                    help="wait after load for charts to paint")
    args = ap.parse_args()
    return snapshot(args.page, args.out, args.port, args.width, args.height,
                    args.settle_ms)


if __name__ == "__main__":
    sys.exit(main())
