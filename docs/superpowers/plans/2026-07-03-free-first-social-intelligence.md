# Free-First Social Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free-first social intelligence layer that discovers social tickers, attaches free StockTwits/ApeWisdom heat baselines, validates against platform signals, snapshots the result, and tracks forward outcomes without making paid X/Grok access a core success condition.

**Architecture:** Add a self-contained `scripts/social_intelligence.py` aggregator that normalizes social discovery rows, fetches free heat baselines, records source status/cost boundaries, and writes both dated snapshots and the legacy `reports/x_influencer_picks.json` quick-pick artifact. Add a separate `scripts/social_intelligence_outcomes.py` tracker so social-discovered tickers are measured independently from deterministic platform candidates. Keep existing paid `scripts/x_influencers.py` as an optional input, not the free core.

**Tech Stack:** Python 3.11, existing JSON artifact model under `reports/`, Streamlit UI modules, current self-contained `scripts/test_*.py` test style.

---

## Final Scope Decisions

- V1 sources:
  - X/Grok x_search output from `scripts/x_influencers.py`: `paid_optional`.
  - Agent Reach local adapter: optional local fallback, `auth_required` when configured, `unavailable/degraded` otherwise.
  - StockTwits: free per-ticker retail sentiment validation.
  - ApeWisdom: free Reddit/WSB crowd heat baseline.
- X official API, xAI API, full X mention count, and automated Grok analysis remain paid optional.
- X/Grok subscription usage is allowed only as manual research assistance:
  - UI can provide copy-to-Grok prompts.
  - Manual Grok results can be pasted later as research notes.
  - Subscription usage must not replace `XAI_API_KEY`, `X_BEARER_TOKEN`, or an automated pipeline API.
- Do not vendor or copy Agent Reach internals into this repo.
- Social outcomes must write to `reports/social_intelligence_outcomes/`, never `reports/candidate_outcomes/`.

## File Structure

- Create `scripts/social_intelligence.py`
  - Source status/cost metadata.
  - Agent Reach optional adapter.
  - Snapshot builder and writer.
  - Legacy quick-pick compatibility writer.

- Create `scripts/social_intelligence_outcomes.py`
  - Forward return tracker for social snapshot rows.
  - SPY comparison and source/handle hit-rate summary.

- Create `scripts/test_social_intelligence.py`
  - Snapshot and source degradation tests.

- Create `scripts/test_social_intelligence_outcomes.py`
  - Forward return and isolation tests.

- Modify `ui/x_sentiment.py`
  - Free-first source status panel.
  - Limitations and paid-enhancement section.
  - Prefer new social snapshot, fallback to legacy quick-pick artifact.

- Modify `ui/options_cockpit.py`
  - Social quick-pick labels for X Mentioned, Agent Reach, Retail Heat, Crowded, Early Signal, Paid Data Needed.

- Modify tests:
  - `scripts/test_options_cockpit_display.py`
  - `scripts/test_dashboard_navigation.py`
  - `scripts/test_docker_runtime_contract.py` baseline static contract repair.

- Modify `Makefile`
  - Add social intelligence tests and candidate outcome baseline to `make test`.

- Optional docs:
  - `docs/USER_GUIDE.md`
  - `docs/options_trader_function_audit.md`

## Task 1: Social Snapshot Aggregator

**Files:**
- Create: `scripts/test_social_intelligence.py`
- Create: `scripts/social_intelligence.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:
- Missing X keys and missing Agent Reach return source statuses, not exceptions.
- Agent Reach timeout returns `status="degraded"`.
- A legacy X influencer pick plus fake StockTwits/ApeWisdom data produces one normalized snapshot row with `cost_mode` metadata.
- If one free sentiment source is unavailable, the other still contributes a baseline.
- Snapshot writer writes:
  - `reports/social_intelligence/YYYY-MM-DD.json`
  - `reports/social_intelligence/latest.json`
  - `reports/x_influencer_picks.json`

- [ ] **Step 2: Verify RED**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence.py
```

Expected: FAIL because `scripts/social_intelligence.py` does not exist yet.

- [ ] **Step 3: Implement minimal aggregator**

Implement:
- `source_statuses(env=None, agent_reach_command=None)`.
- `fetch_agent_reach(command=None, timeout=10, runner=None)`.
- `build_social_snapshot(...)`.
- `write_social_snapshot(...)`.
- `write_legacy_quickpick(...)`.
- CLI flags for `--market`, `--as-of-date`, `--reports-dir`, `--x-picks-path`, `--candidate-file`, `--options-flow-path`, `--agent-reach-command`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence.py
```

Expected: all tests pass.

## Task 2: Social Outcome Tracker

**Files:**
- Create: `scripts/test_social_intelligence_outcomes.py`
- Create: `scripts/social_intelligence_outcomes.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:
- Social snapshots generate `reports/social_intelligence_outcomes/YYYY-MM-DD.json`.
- 7/14/30D returns are computed from an injected price loader.
- SPY returns and social excess returns are included.
- Source/handle hit-rate summary is present.
- No file is written under `reports/candidate_outcomes/`.

- [ ] **Step 2: Verify RED**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence_outcomes.py
```

Expected: FAIL because `scripts/social_intelligence_outcomes.py` does not exist yet.

- [ ] **Step 3: Implement minimal tracker**

Implement:
- `update_social_outcomes(snapshot_dir, outcomes_dir, as_of_date=None, price_loader=None)`.
- yfinance price loader for live CLI use.
- CLI flags for `--snapshot-dir`, `--outcomes-dir`, `--as-of-date`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence_outcomes.py
```

Expected: all tests pass.

## Task 3: UI Source Status And Paid Boundary

**Files:**
- Modify: `ui/x_sentiment.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Write failing static UI tests**

Extend navigation/static tests to assert `ui/x_sentiment.py` contains:
- `Free-first social intelligence`.
- `source_statuses`.
- `付費增強 / 下次優化`.
- `X/Grok subscription`.
- `manual_grok_prompt`.
- `reports/social_intelligence/latest.json`.

- [ ] **Step 2: Verify RED**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL until UI text and helpers exist.

- [ ] **Step 3: Implement UI changes**

Add:
- Source status chips for X official API, xAI Grok, Agent Reach, StockTwits, ApeWisdom.
- Copy-to-Grok manual research prompt area.
- Paid-enhancement section explaining X official API, xAI API, full mention counts, and automated Grok analysis.
- Snapshot loader preference: `reports/social_intelligence/latest.json`, fallback `reports/x_influencer_picks.json`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: all dashboard static tests pass.

## Task 4: Cockpit Quick-Pick Labels

**Files:**
- Modify: `ui/options_cockpit.py`
- Modify: `scripts/test_options_cockpit_display.py`

- [ ] **Step 1: Write failing display tests**

Add a helper-level test that passes a social snapshot row with:
- X mentioned.
- Agent Reach.
- Retail heat.
- Crowded.
- Early signal.
- Paid data needed.

Assert the generated label contains the exact user-facing labels.

- [ ] **Step 2: Verify RED**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected: FAIL until the quick-pick helper exists.

- [ ] **Step 3: Implement quick-pick helper and adoption**

Add:
- `_social_quickpick_label(row)`.
- New snapshot ingestion from `reports/social_intelligence/latest.json`.
- Legacy fallback remains intact.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected: all options cockpit display tests pass.

## Task 5: Baseline Contract Repair And Regression Wiring

**Files:**
- Modify: `scripts/test_docker_runtime_contract.py`
- Modify: `Makefile`
- Modify: `docs/USER_GUIDE.md`
- Modify: `docs/options_trader_function_audit.md`

- [ ] **Step 1: Repair pre-existing docker static contract failure**

Update `scripts/test_docker_runtime_contract.py` to include `ui/_candidate_controls.py` in the concatenated text checked by `test_claude_auth_flow_is_explicit_and_resumeable()`. This matches the current refactor where the `登入後自動接續` copy already lives in `_candidate_controls.py`.

- [ ] **Step 2: Add regression tests to `make test`**

Add:
- `scripts/test_candidate_outcomes.py`
- `scripts/test_social_intelligence.py`
- `scripts/test_social_intelligence_outcomes.py`

- [ ] **Step 3: Update docs**

Update docs to state:
- X 社群情緒 is now free-first social intelligence.
- xAI/Grok and official X API are paid optional.
- X/Grok subscription is manual research assistance only, not an automated API.

## Task 6: Final Verification

**Files:** all changed files.

- [ ] **Step 1: Run focused tests**

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_social_intelligence_outcomes.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_options_cockpit_display.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_dashboard_navigation.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_docker_runtime_contract.py
```

- [ ] **Step 2: Run broader regression**

```bash
make test PY=/Users/ken/Workspace/AI/surge-screener/.venv/bin/python
```

- [ ] **Step 3: Diff review**

Compare actual diff against this plan. Fix unexplained scope drift or explain any necessary divergence.

## Plan Self-Review

- Spec coverage: covers free-first source boundaries, Agent Reach degraded behavior, paid X/Grok positioning, social snapshots, legacy quick-pick compatibility, social outcome validation, UI source status, cockpit labels, and tests.
- Placeholder scan: no TBD/TODO/fill-later placeholders remain.
- Risk areas: live StockTwits/ApeWisdom network calls can fail, so tests use injected gatherers and production code isolates each source. Agent Reach command shape is unknown, so V1 supports a generic local JSON command and degrades if unavailable.
