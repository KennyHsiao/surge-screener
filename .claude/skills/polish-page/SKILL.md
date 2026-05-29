---
name: polish-page
description: Screenshot a Quant Radar dashboard page, get a UX critique, apply the fixes, and re-screenshot to verify. Use when asked to polish, improve, redesign, or fix the look/layout of a specific dashboard page (e.g. "polish the us-screener page").
disable-model-invocation: true
---

# Polish a Quant Radar page

Closes the **edit → see → critique → fix → verify** loop for one Streamlit page.
The UI is pure Python (`ui/` package, `st.*` primitives) — every fix is a
Streamlit code change, not CSS.

`$ARGUMENTS` = the page to polish, as a `url_path` (default `us-screener`):
`us-screener`, `us-options`, `us-cot`, `us-x`, `crypto-universe`,
`crypto-screener`, `crypto-x`, `influencers`, `schedules`, `ai-updates`.

## Steps

1. **Ensure the app is running** on :8501 (else launch via the `run-dashboard` skill):
   ```bash
   curl -s http://localhost:8501/_stcore/health   # -> ok
   ```

2. **Screenshot the page (before):**
   ```bash
   .venv/bin/python scripts/ui_snapshot.py --page <url_path> --out /tmp/polish_before.png
   ```
   Then Read `/tmp/polish_before.png`.

3. **Get a critique.** Delegate to the `streamlit-ux-reviewer` subagent for the same
   page (it screenshots and returns a prioritized findings table). For a quick pass you
   may critique the before-shot yourself, but prefer the subagent for thoroughness.

4. **Find the source.** The page module is in `ui/` (e.g. `us-screener` → `ui/us_screener.py`;
   the X pages share `ui/x_sentiment.py`). Read it and locate each finding's line.

5. **Apply the highest-leverage fixes first**, in priority order from the critique.
   Use Streamlit primitives only: `st.columns`, `st.container(border=True)`, `st.tabs`,
   `st.metric` delta/help, `st.dataframe`/`st.column_config`, `.streamlit/config.toml`
   theming, or scoped `st.markdown(..., unsafe_allow_html=True)`. Keep changes surgical
   and match the patterns of sibling pages.

6. **Verify (after):** Streamlit hot-reloads on save; re-screenshot and Read it:
   ```bash
   .venv/bin/python scripts/ui_snapshot.py --page <url_path> --out /tmp/polish_after.png
   ```
   Confirm each fix landed and nothing regressed. Show the before/after difference in
   your summary.

7. **Summarize** what changed (file:line), why, and the visible improvement. Note any
   findings you deliberately deferred.

## Notes

- This is a real, user-facing dashboard — don't invent data. Layout/styling only.
- If the app isn't reachable, stop and say so rather than editing blind.
- Per project convention (dev on main), each change is committed on its own with a
  descriptive message — but only commit when the user asks.
