---
name: ui-feature
description: Fulfil a visual/UI requirement for the Quant Radar Streamlit dashboard via a 2-agent team (implementer ⇄ UX reviewer) so the user never has to QA pixels. Use AUTOMATICALLY whenever the user asks to add / change / fix / redesign the visual design, styling, colour, layout, spacing, or readability of a dashboard page or section — e.g. "colour the P&L green/red like IBKR", "this table is hard to read", "redesign the 博主雷達 tab", "make the holdings not need expanding". NOT for data/logic/pipeline changes.
---

# /ui-feature — requirement-driven UI agent team

The user states a visual requirement; a two-agent team builds and design-reviews it
to completion so the user does **not** have to inspect pixels or run a QA loop.

`$ARGUMENTS` (or, when auto-invoked, the user's request) = the visual requirement
in plain language, optionally naming a page/`url_path`.

## The team

- **`streamlit-ux-implementer`** (hands) — edits `ui/*.py` with Streamlit
  primitives + `ui/_shared.py` colour tokens.
- **`streamlit-ux-reviewer`** (eyes) — critiques the live page from a **real
  screenshot** and returns prioritized findings (read-only).

You are the orchestrator. **Let the reviewer be the quality gate — do not hand-QA
the result yourself.**

## Loop

1. **Ensure the app is running** on :8501; if `curl -s http://localhost:8501/_stcore/health`
   isn't `ok`, launch it via the `run-dashboard` skill. From the requirement, decide
   the target `url_path`(s) (e.g. reconciliation → `ibkr-reconcile`, X radar → `us-x`).
2. **Implement (round N):** spawn **`streamlit-ux-implementer`** with the requirement
   (round 1) or the reviewer's findings (later rounds). It edits `ui/*.py`, syntax-checks,
   and returns changed files + affected `url_path`(s). Streamlit hot-reloads on save.
3. **Review:** spawn **`streamlit-ux-reviewer`** for the affected `url_path`(s). It
   screenshots the live page and returns a prioritized findings table.
4. **Iterate:** if the reviewer reports any **high/medium** findings **and** round < 3,
   go back to step 2 feeding it those findings. Stop when the reviewer has no
   high/medium findings (design accepted) or after **3 rounds** (then report any
   leftover low-priority items rather than looping forever).
5. **Report:** show a concise before/after, what changed (`file:line`) and why, and the
   reviewer's final verdict. **Commit only if the user asks** (project convention:
   dev on main, one descriptive commit per change).

## Orchestration

- **Under ultracode** (or for thoroughness): run the loop as a **Workflow** — each
  round is `implementer` then `reviewer` (sequential, never parallel: the review must
  see the implemented state). Pipe the reviewer's findings into the next round's
  implementer prompt. Stop on a clean review or 3 rounds.
- **Otherwise:** spawn the two subagents in sequence with the **Agent** tool, relaying
  the reviewer's findings to the implementer each round.

## Guardrails

- Streamlit primitives only (no CSS/React); reuse `ui/_shared.py` tokens; TWS colour
  convention (green = profit/up, red = loss/down).
- Never invent data — layout/styling only; keep edits surgical and idiomatic to
  sibling pages; tolerate missing/partial JSON so styling can't crash a page.
- If the app isn't reachable, **stop and say so** — never edit the UI blind.
