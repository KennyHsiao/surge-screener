---
name: run-dashboard
description: Launch the Surge Screener Streamlit dashboard (app.py) locally and verify it renders. Use when asked to run, start, preview, or screenshot the dashboard / UI / app.
---

# Run the Surge Screener dashboard

`app.py` is a Streamlit dashboard that reads the pipeline's JSON outputs and the
committed `reports/` data. This is the verified local launch path.

## Prerequisites

- **Python 3.10+ required.** `app.py` uses `dict | None` annotations. The macOS
  system Python is 3.9 and will fail. Use 3.11 to match the GitHub Actions workflow.
- `streamlit` and `plotly` are **NOT in `requirements.txt`** (only `pandas` is).
  Install them explicitly. The dashboard needs just these three packages — not the
  full pipeline requirements (anthropic, yfinance, etc.).

## Setup (once)

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python streamlit plotly pandas
```

`.venv/` is already gitignored.

## Launch

```bash
.venv/bin/streamlit run app.py \
  --server.headless true --server.port 8501 \
  --browser.gatherUsageStats false > /tmp/streamlit_surge.log 2>&1 &
```

Open http://localhost:8501

## Verify it actually rendered (don't just trust the launch)

```bash
curl -s http://localhost:8501/_stcore/health   # -> "ok"
```

Streamlit renders content over a websocket, so a plain `curl /` returns only the
loading skeleton, and a Chrome `--screenshot` with `--virtual-time-budget` captures
the skeleton too. To get a real screenshot, drive it with Playwright and wait for an
actual element:

```bash
uv pip install --python .venv/bin/python playwright
.venv/bin/python -m playwright install chromium
```

```python
# /tmp/drive_surge.py
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    pg = p.chromium.launch().new_page(viewport={"width": 1500, "height": 1600})
    pg.goto("http://localhost:8501/", wait_until="networkidle", timeout=30000)
    pg.wait_for_selector('button[role="tab"]', timeout=20000)  # not the skeleton
    pg.wait_for_timeout(2500)                                   # let plotly paint
    pg.screenshot(path="/tmp/surge.png", full_page=True)
```

## What you'll see

- 6 tabs: Regime, Pipeline, Candidates, Layer 2 Analysis, DD Results, Performance.
- **Performance** and the report section show real data — the committed
  `reports/2026-05-05/` and `reports/performance_ledger.csv` (the MU pick).
- Regime / Pipeline / Candidates / Layer 2 / DD show "No data — run the pipeline
  first" because their intermediate JSON files (`scored_candidates.json`,
  `layer2_results.json`, `dd_results.json`, `filtered_universe.json`) are gitignored
  and absent locally. Populating them requires running the pipeline scripts, which
  need API keys and cost money.
