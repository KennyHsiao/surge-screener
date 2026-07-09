# Playbook Next Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Playbook V1 from a visible checklist overlay into automated validation, and expand the existing review center so it can separate surge events, strong continuation, and playbook validation without adding another sidebar entry.

**Architecture:** Keep Options Cockpit as the canonical decision surface. The course playbook remains an overlay that records its context, explains its source, and feeds validation artifacts; it does not replace the platform verdict. Validation is platform-owned: scheduled scripts and in-app refresh actions produce report artifacts, and the existing `復盤分析` page becomes a review / validation hub that separates lanes by validation logic: `暴漲事件復盤`, `續漲強者`, and `Playbook 驗證`.

**Tech Stack:** Python, Streamlit, local JSON/CSV reports, existing self-contained script tests.

---

## Scope

Next phase is not "add every Notion strategy". It is:

1. Confirm and deploy the corrected Playbook overlay baseline.
2. Add a Playbook Decision Ledger so every recommendation has an auditable context.
3. Add an automated Playbook Validation runner that the platform can run without manual spreadsheet work.
4. Add surge-event taxonomy so historical "big moves" are understood as objectively labeled outcomes plus testable candidate causes, not one blended explanation.
5. Add a `續漲強者` outcome lane so the platform can answer whether a ticker keeps rising after breakout / confirmation.
6. Upgrade `研究驗證 → 復盤分析` into a grouped validation hub, with clearly separated lanes for `暴漲事件復盤`, `續漲強者`, and `Playbook 驗證`.
7. Improve the UI explanation only where it reduces confusion.
8. Gate any new playbook behind explicit conditions and tests.

## Non-Negotiable Product Requirements

- Backtest and validation must be automated by the platform. The user should not need to export CSVs, manually calculate forward returns, or inspect raw JSON.
- Validation status must be visible in a fixed, findable location: sidebar `研究驗證 → 復盤分析`, then lane `暴漲事件復盤`, `續漲強者`, or `Playbook 驗證`.
- Options Cockpit must show a compact status chip or button that clearly links to the validation hub and opens the Playbook lane.
- The validation hub must not claim causal certainty. Surge and continuation explanations must be labeled as `候選原因`, `已驗證關聯`, `探索性`, or `資料不足`.
- `暴漲事件` and `續漲強者` must be separate outcome families:
  - `暴漲事件`: a realized run-up such as +30%/20d, +40%/40d, or +50%/60d from a trough / setup point.
  - `續漲強者`: after breakout / confirmation / playbook setup, forward return remains positive and drawdown remains controlled.
- UI labels must distinguish:
  - `原本決策`: Options Cockpit `GO / WAIT / AVOID`
  - `課程 Playbook`: the Notion-derived overlay recommendation
  - `驗證狀態`: automated backtest / forward-validation result
- Until sample size is mature, validation output must say `累積中` or `探索性`; it must not display as proven.

## Multi-Version Roadmap

This roadmap is intentionally broader than the first shipped implementation. Each version has a product outcome, an engineering deliverable, a validation gate, and a boundary that prevents the platform from mixing research with live decisioning too early.

### V1: Playbook Overlay Foundation

- **Purpose:** Show Notion-derived course playbooks inside Options Cockpit as an explanation layer.
- **Build:** Keep the existing five playbooks: `Swing Long Call`, `Jump Trade Long Call`, `Bull Call Spread`, `Protective Put / Swing Hedge`, `Skip / Wait`.
- **Data:** Current ticker context, cycle, IV, DTE, premium risk, holdings flag, chart fallback.
- **Validation gate:** Unit tests and UI snapshot only. No performance claims.
- **UI rule:** `GO / WAIT / AVOID` remains the primary cockpit verdict. Playbook is a compact overlay.
- **Do not do:** Do not let Notion rules override the platform decision. Missing non-critical conditions create warnings, not blocks.

### V2: Validation Hub And Decision Ledger

- **Purpose:** Make every playbook recommendation auditable and put validation in a findable location.
- **Build:** `playbook_decision_log`, `playbook_validation`, `ui/playbook_validation.py`, and `研究驗證 → 復盤分析 → Playbook 驗證`.
- **Data:** One row per evaluated playbook decision with ticker, date, cockpit verdict, playbook, factor IDs, warnings, blocks, DTE, IV, cycle source.
- **Validation gate:** No-lookahead forward outcomes, maturity gates, source freshness checks, deterministic JSON schema.
- **UI rule:** Validation appears in the review hub, not as a new sidebar page.
- **Do not do:** Do not label sample results as proven before the minimum resolved sample threshold is met.

### V3: Surge Event Taxonomy And Strong Continuation

- **Purpose:** Separate "stocks that exploded" from "stocks that kept rising after an actionable setup".
- **Build:** `surge_event_taxonomy.py`, `continuation_strength.py`, `ui/continuation_validation.py`, and three lanes in the same hub: `暴漲事件復盤`, `續漲強者`, `Playbook 驗證`.
- **Data:** Historical surge events, breakout / confirmation dates, forward returns, forward max drawdown, candidate-cause tags.
- **Validation gate:** Surge events are result labels; candidate causes are tested by lift, hit rate, mean forward return, and max drawdown.
- **UI rule:** `暴漲事件復盤` answers what happened before big moves. `續漲強者` answers whether a trade still had follow-through after confirmation.
- **Do not do:** Do not describe technical, fundamental, chip, or event tags as causal proof.

### V4: Modular Factor Library

- **Purpose:** Turn technical, sector, fundamental, chip, and event observations into reusable, versioned factor modules.
- **Build:** A factor registry with stable IDs, input requirements, point-in-time requirements, output type, and eligible validation lanes.
- **Data:** Technical OHLCV, relative strength, sector strength, earnings / estimates when timestamp-safe, institutional / options-flow snapshots when source-safe, event catalyst manifests.
- **Validation gate:** A factor cannot be used in strategy scoring unless its input timestamp, missing-data policy, and control group are explicit.
- **UI rule:** Each lane shows factors grouped by source family: `技術`, `相對強度/板塊`, `基本面`, `籌碼/資金流`, `事件`.
- **Do not do:** Do not mix slow data such as 13F with daily setup timing unless the release timestamp is modeled.

### V5: Strategy Prototype Backtesting

- **Purpose:** Promote validated factor combinations into strategy prototypes that can be backtested as entry / exit systems.
- **Build:** Strategy definition objects that combine setup factors, entry timing, exit rule, stop rule, horizon, and no-trade conditions.
- **Data:** Same factor registry plus execution assumptions: next open / next close, slippage, stop trigger, trailing logic.
- **Validation gate:** Compare strategy prototypes against baselines such as buy-and-hold from setup date, random control, and original screener candidates.
- **UI rule:** Strategy prototypes live in validation pages until proven. Options Cockpit can show `研究中` badges, not ranking boosts.
- **Do not do:** Do not call a factor module a full strategy unless entry, exit, stop, sizing, and horizon are defined.

### V6: Options Structure Validation

- **Purpose:** Validate whether option structures suggested by playbooks actually improve risk / reward versus stock-only or long-call baselines.
- **Build:** Option structure simulator for `Long Call`, `Bull Call Spread`, `Protective Put`, `Covered Call`, `Cash-Secured Put`, and later `Bear Put Spread`.
- **Data:** DTE, delta, IV rank / IV percentile, premium risk percentage, earnings date, spread width, estimated max loss / max profit.
- **Validation gate:** No options structure gets a recommendation label without DTE, IV, premium risk, and event-risk checks.
- **UI rule:** Show concise structure reason: `低 IV → long call`, `IV / premium high → spread`, `existing holding + risk cycle → hedge`.
- **Do not do:** Do not validate naked call or margin-dependent sell put until account capability and risk capacity are explicitly represented.

### V7: Portfolio And Risk Guard Validation

- **Purpose:** Move from single-ticker validation to portfolio-aware risk decisions.
- **Build:** Portfolio exposure model, sector concentration checks, per-position max loss, risk budget, hedge ratio validation, and portfolio-level drawdown reports.
- **Data:** Current holdings, cost basis, lot size, sector exposure, beta / correlation, options exposure, realized and unrealized P/L.
- **Validation gate:** Strategy recommendations that depend on existing holdings stay blocked until holdings and cost basis are available.
- **UI rule:** Portfolio-level risks appear in a compact risk strip, not inside every playbook chip.
- **Do not do:** Do not implement Stock Repair, Swing Hedge ratios, or covered-call sizing without lot-level position data.

### V8: Forward Validation Operations

- **Purpose:** Make validation a living platform workflow rather than a one-off report.
- **Build:** Scheduled runners, durable snapshots, freshness monitors, failed-run warnings, and data lineage from source artifact to UI badge.
- **Data:** Daily decisions, daily candidate snapshots, forward outcomes, artifact fingerprints, run status, sample maturity.
- **Validation gate:** Any stale or cross-run artifact fails closed and displays `封鎖` or `資料過期`.
- **UI rule:** One status language across lanes: `封鎖`, `累積中`, `探索性`, `已驗證`, `失效`.
- **Do not do:** Do not silently reuse stale validation artifacts when input snapshots changed.

### V9: Evidence-Weighted Decision Assistance

- **Purpose:** Let validated evidence influence how the platform explains and prioritizes opportunities, while preserving the original decision flow.
- **Build:** Evidence-weight layer that can add confidence, downgrade weak setups, or surface validated factor combinations.
- **Data:** Mature validation summaries from surge, continuation, playbook, strategy, options, and portfolio lanes.
- **Validation gate:** A factor or playbook must pass minimum sample size, out-of-sample / forward validation, and drawdown checks before affecting priority.
- **UI rule:** Show `驗證支持`, `驗證中`, or `驗證不支持`; never show a black-box score without the contributing evidence.
- **Do not do:** Do not auto-trade or hard-block solely from research evidence.

### V10: Advanced Data And Knowledge Network

- **Purpose:** Connect course knowledge, image-derived notes, market regime, COT, institutional, options flow, and event narratives into explainable research context.
- **Build:** Knowledge graph links from playbook rules to factor IDs, source documents, validation results, and UI explanations.
- **Data:** Notion/course source manifests, image-extracted course notes, COT, macro regime, institutional snapshots, sourced news / event manifests.
- **Validation gate:** Any external or slow-moving source must have release timestamp, freshness window, and missing-data behavior before becoming a factor.
- **UI rule:** Advanced evidence is shown as collapsible context, not first-screen clutter.
- **Do not do:** Do not make LLM narrative or unsourced event explanation part of the core score.

## Version Promotion Gates

- **From V1 to V2:** Playbook overlay is stable, compact, and does not confuse the original cockpit verdict.
- **From V2 to V3:** Decision ledger and validation hub can run without manual exports.
- **From V3 to V4:** Surge and continuation outcomes are labeled consistently enough to reuse as targets.
- **From V4 to V5:** Factor modules have stable IDs, point-in-time rules, and missing-data policy.
- **From V5 to V6:** Strategy prototypes show evidence beyond simple baseline comparisons.
- **From V6 to V7:** Options and holding-dependent strategies have position / risk inputs.
- **From V7 to V8:** Portfolio and validation artifacts can be refreshed automatically and fail closed.
- **From V8 to V9:** Forward validation has enough resolved samples to support confidence changes.
- **From V9 to V10:** Evidence layer is stable enough that advanced sources can be added without changing the decision contract.

## Files

- Modify: `scripts/trading_playbook_engine.py`  
  Add stable reason codes, confidence fields, and validation-ready factor IDs.
- Modify: `ui/options_cockpit.py`  
  Render the same compact overlay, plus a low-noise detail view for source, missing conditions, and original-vs-playbook separation.
- Create: `scripts/playbook_decision_log.py`  
  Serialize evaluated contexts and decisions into `reports/playbook_decisions/`.
- Create: `scripts/test_playbook_decision_log.py`  
  Verify ledger schema, privacy boundaries, and deterministic output.
- Create: `scripts/playbook_validation.py`  
  Automated platform runner that reads decision snapshots, joins price outcomes, computes backtest / forward-validation summaries, and writes `reports/playbook_validation/latest.json`.
- Create: `scripts/test_playbook_validation.py`  
  Verify no look-ahead, maturity gates, output schema, and fail-closed stale-source handling.
- Create: `scripts/surge_event_taxonomy.py`  
  Classify historical surge events into objective result families and sourced candidate-cause dimensions.
- Create: `scripts/test_surge_event_taxonomy.py`  
  Verify taxonomy labels are deterministic, do not imply causality, and preserve unknown / insufficient-data states.
- Create: `scripts/continuation_strength.py`  
  Classify post-breakout / post-confirmation outcomes as `strong_continuation`, `normal_continuation`, `failed_breakout`, or `unresolved`.
- Create: `scripts/test_continuation_strength.py`  
  Verify continuation thresholds, max-drawdown handling, unresolved windows, and no look-ahead.
- Create: `ui/playbook_validation.py`  
  Focused renderer for Playbook validation status, factor/playbook lift table, and unresolved sample state. Imported by `ui/retro_analysis.py`; not added as its own sidebar page.
- Create: `ui/continuation_validation.py`  
  Focused renderer for `續漲強者` outcome quality and candidate-cause breakdown. Imported by `ui/retro_analysis.py`; not added as its own sidebar page.
- Modify: `ui/retro_analysis.py`  
  Add a top-level lane selector so `暴漲事件復盤`, `續漲強者`, `Playbook 驗證`, and later strategy/flow validation are visually distinct under the same sidebar entry.
- Modify: `scripts/test_trading_playbook_engine.py`  
  Protect reason codes, factor IDs, and confidence behavior.
- Modify: `scripts/test_options_cockpit_display.py`  
  Protect UI helper behavior without importing Streamlit pages.
- Modify: `scripts/test_dashboard_navigation.py`  
  Protect that no new Playbook sidebar page is added, and that Options Cockpit hands off to the existing review / validation hub.
- Create: `docs/knowledge/trading-course/playbook-v2.md`  
  Document what V2 adds and which strategies remain blocked.

## Task 1: Confirm V1 Main And Deploy Baseline

- [ ] **Step 1: Confirm reviewed V1 is on main**

Run:

```bash
git switch main
git pull --ff-only
git log --oneline -10
```

Expected: `main` contains the Playbook overlay review-fix merge or equivalent commit.

- [ ] **Step 2: Confirm main deploy**

Run:

```bash
gh run list --workflow deploy_test_server.yml --branch main --limit 1
```

Expected: latest `Deploy Test Server` run is `success`.

## Task 2: Add Playbook Decision Ledger

- [ ] **Step 1: Write failing ledger test**

Create `scripts/test_playbook_decision_log.py` with a test that calls a new pure function:

```python
def test_decision_log_row_is_stable_and_minimal():
    from scripts import playbook_decision_log as log

    row = log.decision_row(
        context={
            "ticker": "NVDA",
            "cockpit_verdict": "WAIT",
            "cycle": "Cycle1",
            "cycle_source": "chart_fallback",
            "dte": 30,
            "iv_rank": 25.0,
        },
        decision={
            "primary_playbook": "Swing Long Call",
            "actionability": "watch",
            "structure": "單買 Call",
            "warnings": [{"id": "jump_signal_missing"}],
            "blocks": [],
            "course_sources": ["Swing Trade"],
        },
    )

    assert row == {
        "ticker": "NVDA",
        "cockpit_verdict": "WAIT",
        "primary_playbook": "Swing Long Call",
        "actionability": "watch",
        "structure": "單買 Call",
        "cycle": "Cycle1",
        "cycle_source": "chart_fallback",
        "dte": 30,
        "iv_rank": 25.0,
        "warning_ids": ["jump_signal_missing"],
        "block_ids": [],
        "course_sources": ["Swing Trade"],
    }
```

- [ ] **Step 2: Run test to verify red**

Run:

```bash
.venv/bin/python scripts/test_playbook_decision_log.py
```

Expected: import or attribute failure.

- [ ] **Step 3: Implement minimal ledger helper**

Create `scripts/playbook_decision_log.py` with `decision_row(context, decision)` and `write_snapshot(rows, out_dir="reports/playbook_decisions")`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_playbook_decision_log.py
.venv/bin/python scripts/test_trading_playbook_engine.py
.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected: all pass.

## Task 3: Add Validation-Ready Factor IDs

- [ ] **Step 1: Extend engine tests**

Add assertions in `scripts/test_trading_playbook_engine.py` that each decision exposes:

```python
assert "factor_ids" in result
assert "dte_min_21_days" in result["factor_ids"]
assert "iv_rank_low_for_long_options" in result["factor_ids"]
```

- [ ] **Step 2: Implement factor IDs**

In `scripts/trading_playbook_engine.py`, add `factor_ids` to `_result()` and populate only measurable rules:

- `dte_min_21_days`
- `iv_rank_low_for_long_options`
- `bollinger_jump_1sd_to_2sd`
- `premium_risk_pct_4`
- `cycle_1_5_6_bullish`
- `has_long_holding_for_hedge`

- [ ] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_trading_playbook_engine.py
```

Expected: all pass.

## Task 4: Add Automated Playbook Validation Runner

- [ ] **Step 1: Write failing validation runner test**

Create `scripts/test_playbook_validation.py` with deterministic fixture rows:

```python
def test_validation_summary_respects_maturity_gate():
    from scripts import playbook_validation as pv

    decisions = [
        {"ticker": "AAA", "as_of_date": "2026-01-02", "primary_playbook": "Swing Long Call",
         "factor_ids": ["dte_min_21_days"], "actionability": "actionable"},
        {"ticker": "BBB", "as_of_date": "2026-01-02", "primary_playbook": "Swing Long Call",
         "factor_ids": ["dte_min_21_days"], "actionability": "actionable"},
    ]
    outcomes = [
        {"ticker": "AAA", "as_of_date": "2026-01-02", "fwd_7d_return": 0.08, "resolved_7d": True},
        {"ticker": "BBB", "as_of_date": "2026-01-02", "fwd_7d_return": -0.03, "resolved_7d": True},
    ]

    summary = pv.summarize(decisions, outcomes, min_resolved=10)

    assert summary["status"] == "accumulating"
    assert summary["resolved"] == 2
    assert summary["min_resolved"] == 10
    assert summary["playbooks"][0]["playbook"] == "Swing Long Call"
    assert summary["playbooks"][0]["verdict"] == "exploratory"
```

- [ ] **Step 2: Run test to verify red**

Run:

```bash
.venv/bin/python scripts/test_playbook_validation.py
```

Expected: import or attribute failure.

- [ ] **Step 3: Implement validation runner**

Create `scripts/playbook_validation.py` with:

- `load_decisions(path_or_dir)`
- `resolve_forward_outcomes(decisions, horizon_days=(3, 7, 14, 30))`
- `summarize(decisions, outcomes, min_resolved=100)`
- `write_latest(summary, out="reports/playbook_validation/latest.json")`

Rules:

- No look-ahead: entry date is decision `as_of_date`; forward return starts after that date.
- If forward window is unresolved, mark `resolved_* = False`.
- If `resolved < min_resolved`, status is `accumulating`.
- If source files are missing or stale, write `status: blocked` with a human-readable reason.
- Use existing yfinance/price helper patterns only where already present; do not add a paid-data dependency.

- [ ] **Step 4: Add command-line entry**

`scripts/playbook_validation.py` should run as:

```bash
.venv/bin/python scripts/playbook_validation.py \
  --decisions reports/playbook_decisions \
  --output reports/playbook_validation/latest.json \
  --min-resolved 100
```

Expected: writes JSON summary and exits non-zero only on code/config errors, not on `accumulating` sample state.

- [ ] **Step 5: Wire automated platform refresh**

Add the validation command to one automated platform path:

- Preferred P1: existing GitHub scheduled workflow or candidate/report workflow after daily scans.
- Minimum P1: `scripts/data_source_refresh.py` or `ui/analytics_db.py` refresh action runs it and publishes `latest.json`.

Expected: a user can refresh from platform UI; CI/scheduled path can run it without manual data export.

## Task 5: Add Surge Event Taxonomy And Continuation Outcomes

- [ ] **Step 1: Write failing taxonomy tests**

Create `scripts/test_surge_event_taxonomy.py`:

```python
def test_surge_taxonomy_separates_result_from_candidate_causes() -> None:
    from scripts import surge_event_taxonomy as tax

    row = tax.classify_surge_event({
        "ticker": "NVDA",
        "thresholds_hit": ["+30%/20d", "+40%/40d"],
        "magnitude_pct": 47.0,
        "sessions_to_peak": 31,
        "gap_pct": 0.04,
        "volume_ratio_20d": 2.4,
        "rs_vs_spy_20d": 0.18,
        "sector_rs_20d": 0.11,
        "earnings_within_5d": False,
        "news_catalyst": None,
    })

    assert row["result_family"] == "multi_threshold_surge"
    assert row["price_structure"] == "trend_continuation"
    assert row["candidate_causes"] == [
        "technical_volume_expansion",
        "relative_strength_leadership",
        "sector_support",
    ]
    assert row["cause_certainty"] == "candidate_only"
```

- [ ] **Step 2: Write failing continuation tests**

Create `scripts/test_continuation_strength.py`:

```python
def test_strong_continuation_requires_return_and_controlled_drawdown() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "NVDA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": 0.18,
        "fwd_30d_max_drawdown": -0.07,
        "resolved_30d": True,
        "fwd_60d_return": 0.34,
        "fwd_60d_max_drawdown": -0.13,
        "resolved_60d": True,
    })

    assert row["continuation_label"] == "strong_continuation"
    assert row["primary_horizon"] == "30d"
    assert row["trade_value"] == "high"


def test_continuation_unresolved_window_does_not_guess() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "AAA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": None,
        "fwd_30d_max_drawdown": None,
        "resolved_30d": False,
    })

    assert row["continuation_label"] == "unresolved"
    assert row["trade_value"] == "unknown"
```

- [ ] **Step 3: Run tests to verify red**

Run:

```bash
.venv/bin/python scripts/test_surge_event_taxonomy.py
.venv/bin/python scripts/test_continuation_strength.py
```

Expected: import failures.

- [ ] **Step 4: Implement surge taxonomy**

Create `scripts/surge_event_taxonomy.py` with:

```python
def classify_surge_event(event: dict) -> dict:
    thresholds = event.get("thresholds_hit") or [event.get("threshold")]
    thresholds = [t for t in thresholds if t]
    result_family = "multi_threshold_surge" if len(thresholds) >= 2 else "single_threshold_surge"

    gap = float(event.get("gap_pct") or 0.0)
    sessions = int(event.get("sessions_to_peak") or 0)
    if gap >= 0.08:
        price_structure = "gap_impulse"
    elif sessions <= 10:
        price_structure = "fast_reversal"
    else:
        price_structure = "trend_continuation"

    candidate_causes = []
    if float(event.get("volume_ratio_20d") or 0.0) >= 1.8:
        candidate_causes.append("technical_volume_expansion")
    if float(event.get("rs_vs_spy_20d") or 0.0) >= 0.10:
        candidate_causes.append("relative_strength_leadership")
    if float(event.get("sector_rs_20d") or 0.0) >= 0.05:
        candidate_causes.append("sector_support")
    if bool(event.get("earnings_within_5d")):
        candidate_causes.append("earnings_catalyst")
    if event.get("news_catalyst"):
        candidate_causes.append("sourced_event_catalyst")

    return {
        "ticker": event.get("ticker"),
        "result_family": result_family,
        "price_structure": price_structure,
        "candidate_causes": candidate_causes or ["unknown"],
        "cause_certainty": "candidate_only",
    }
```

- [ ] **Step 5: Implement continuation classifier**

Create `scripts/continuation_strength.py` with:

```python
def classify_continuation(row: dict) -> dict:
    resolved_30 = bool(row.get("resolved_30d"))
    resolved_60 = bool(row.get("resolved_60d"))

    if not resolved_30 and not resolved_60:
        return {
            "ticker": row.get("ticker"),
            "setup_date": row.get("setup_date") or row.get("as_of_date"),
            "continuation_label": "unresolved",
            "primary_horizon": None,
            "trade_value": "unknown",
        }

    r30 = row.get("fwd_30d_return")
    dd30 = row.get("fwd_30d_max_drawdown")
    r60 = row.get("fwd_60d_return")
    dd60 = row.get("fwd_60d_max_drawdown")

    strong_30 = resolved_30 and r30 is not None and dd30 is not None and r30 >= 0.15 and dd30 >= -0.10
    strong_60 = resolved_60 and r60 is not None and dd60 is not None and r60 >= 0.30 and dd60 >= -0.15
    if strong_30:
        label, horizon, value = "strong_continuation", "30d", "high"
    elif strong_60:
        label, horizon, value = "strong_continuation", "60d", "high"
    elif resolved_30 and r30 is not None and r30 > 0:
        label, horizon, value = "normal_continuation", "30d", "medium"
    else:
        label, horizon, value = "failed_breakout", "30d" if resolved_30 else "60d", "low"

    return {
        "ticker": row.get("ticker"),
        "setup_date": row.get("setup_date") or row.get("as_of_date"),
        "continuation_label": label,
        "primary_horizon": horizon,
        "trade_value": value,
    }
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_surge_event_taxonomy.py
.venv/bin/python scripts/test_continuation_strength.py
```

Expected: all pass.

- [ ] **Step 7: Add continuation lane renderer**

Create `ui/continuation_validation.py` with `render()` that reads future `reports/retrospective/continuation_strength.json` when present and otherwise shows an empty state:

```python
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "retrospective" / "continuation_strength.json"


def render() -> None:
    st.subheader("續漲強者")
    st.caption("驗證突破或確認後是否還能續漲；原因只顯示為候選原因，不宣稱因果。")
    if not REPORT.exists():
        st.info("尚未累積續漲驗證資料。平台會用 forward return 與最大回撤自動分類 strong / normal / failed / unresolved。")
        return
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = data.get("rows") or []
    if not rows:
        st.info("續漲樣本仍在累積中。")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
```

## Task 6: Integrate Validation Lanes Into The Existing Review Hub

- [ ] **Step 1: Add navigation / IA contract tests**

In `scripts/test_dashboard_navigation.py`, add:

```python
def test_validation_lanes_live_inside_retro_analysis_hub() -> None:
    assert_contains(APP, "retro_analysis.render")
    assert_contains(APP, 'title="復盤分析"')
    assert_not_contains(APP, 'title="Playbook 驗證"')
    assert_contains(RETRO_ANALYSIS, "playbook_validation")
    assert_contains(RETRO_ANALYSIS, "continuation_validation")
    assert_contains(RETRO_ANALYSIS, "暴漲事件復盤")
    assert_contains(RETRO_ANALYSIS, "續漲強者")
    assert_contains(RETRO_ANALYSIS, "Playbook 驗證")


def test_options_cockpit_links_to_validation_hub_not_new_sidebar_page() -> None:
    assert_contains(COCKPIT, "查看 Playbook 驗證")
    assert_contains(COCKPIT, "retro-analysis")
    assert_not_contains(APP, 'url_path="playbook-validation"')
```

- [ ] **Step 2: Create focused renderer**

Create `ui/playbook_validation.py` with `render()` that reads `reports/playbook_validation/latest.json` and shows:

- top status band: `已驗證`, `探索性`, `累積中`, or `封鎖`
- last run timestamp and sample counts
- playbook-level table: playbook, resolved count, mean forward return, hit rate, verdict
- factor-level table: factor ID, resolved count, lift / return summary, maturity
- empty state that says the platform has not accumulated enough decisions yet

- [ ] **Step 3: Add lane selector to existing page**

Modify `ui/retro_analysis.py` so the existing sidebar entry remains `研究驗證 → 復盤分析`, but the page begins with a compact lane selector:

```python
lane = st.segmented_control(
    "驗證類型",
    ["暴漲事件復盤", "續漲強者", "Playbook 驗證"],
    default="暴漲事件復盤",
)
if lane == "續漲強者":
    continuation_validation.render()
    return
if lane == "Playbook 驗證":
    playbook_validation.render()
    return
```

Expected: different validation logic is separated after entering the existing review page, without adding another navigation item.

- [ ] **Step 4: Add Options Cockpit handoff**

In `ui/options_cockpit.py`, add a compact button or link beside the existing `課程 Playbook` row:

- label: `查看 Playbook 驗證`
- behavior: set session state for `validation_lane = "Playbook 驗證"` and switch to `retro-analysis` when available
- fallback: caption telling the user to open sidebar `研究驗證 → 復盤分析 → Playbook 驗證`

Expected: the validation location is discoverable from the exact place where a playbook appears.

- [ ] **Step 5: Visual check**

Run:

```bash
.venv/bin/python -m streamlit run app.py --server.port 8504 --server.headless true --browser.gatherUsageStats false
.venv/bin/python scripts/ui_snapshot.py --page retro-analysis --port 8504 --out /tmp/validation-hub.png --width 1440 --height 1100 --settle-ms 3000
.venv/bin/python scripts/ui_snapshot.py --page options-cockpit --port 8504 --out /tmp/options-playbook-link.png --width 1440 --height 1100 --settle-ms 5000
```

Expected: one sidebar entry remains; the page clearly separates `暴漲事件復盤`, `續漲強者`, and `Playbook 驗證`; Options Cockpit has a clear but compact handoff; no horizontal scroll on mobile.

## Task 7: Improve UI Explanation Without More Clutter

- [ ] **Step 1: Add display-state tests**

In `scripts/test_options_cockpit_display.py`, add helper-level tests that verify:

- compact chips stay limited to playbook, actionability, and top 2-3 warnings
- detail view exposes original cockpit verdict separately from playbook result
- missing conditions appear inside the expander only

- [ ] **Step 2: Implement helper output only**

In `ui/options_cockpit.py`, keep the first-row overlay compact. Add detail content inside existing `條件與來源` expander:

- `原本 Cockpit：GO/WAIT/AVOID`
- `課程 Overlay：Playbook + actionability`
- `資料來源：Trade State / chart fallback / reconciliation`
- `可驗證因子：factor_ids`

- [ ] **Step 3: Visual check**

Run local app and snapshot:

```bash
.venv/bin/python -m streamlit run app.py --server.port 8504 --server.headless true --browser.gatherUsageStats false
.venv/bin/python scripts/ui_snapshot.py --page options-cockpit --port 8504 --out /tmp/playbook-v2.png --width 1440 --height 1100 --settle-ms 5000
```

Expected: overlay remains one compact row; details stay collapsed; validation is reachable through the existing review hub, not buried in the expander.

## Task 8: Decide New Playbooks Only After Evidence

- [ ] **Step 1: Document candidate playbooks**

Create `docs/knowledge/trading-course/playbook-v2.md` with this order:

1. Covered Call: requires existing long stock position, resistance reference, and non-earnings window.
2. Cash-Secured Sell Put: requires cash/margin capability flag; otherwise warning only, no recommendation.
3. Bear Put Spread: requires bearish direction and no existing long-only conflict.
4. Elastic Trade: requires validated `%B` continuation logic.
5. Stock Repair: blocked until cost basis and lot quantity are available.

- [ ] **Step 2: Do not implement new recommendations yet**

Expected: V2 documentation exists, but `scripts/trading_playbook_engine.py` still recommends only the current five V1 playbooks.

## Verification

Run before claiming completion:

```bash
.venv/bin/python scripts/test_trading_playbook_engine.py
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_playbook_decision_log.py
.venv/bin/python scripts/test_playbook_validation.py
.venv/bin/python scripts/test_surge_event_taxonomy.py
.venv/bin/python scripts/test_continuation_strength.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python -m py_compile scripts/trading_playbook_engine.py ui/options_cockpit.py ui/trade_state.py ui/playbook_validation.py ui/continuation_validation.py scripts/playbook_decision_log.py scripts/playbook_validation.py scripts/surge_event_taxonomy.py scripts/continuation_strength.py
git diff --check
```

## Review Checklist

- The original `GO/WAIT/AVOID` remains visually primary.
- The playbook layer never blocks solely because of Notion guardrails.
- New fields are serializable and stable for later forward validation.
- Backtest / validation is run by platform scripts or platform UI refresh, not by manual spreadsheet work.
- `暴漲事件復盤`, `續漲強者`, and `Playbook 驗證` are visible inside `研究驗證 → 復盤分析`, and Options Cockpit links to the Playbook lane.
- Surge-event explanations are shown as candidate causes or validated associations, never as proven causal claims.
- Strong continuation is measured after setup / breakout / confirmation, not from the historical trough unless the trough was the actual setup point.
- No new strategy is recommended without explicit position, risk, and data conditions.
- UI remains compact on desktop and mobile.

## Roadmap Self-Review

### Spec Coverage

- The plan now covers the immediate Playbook validation work and the full version path from V1 through V10.
- `暴漲事件`, `續漲強者`, and `Playbook 驗證` are separated by outcome target and validation logic.
- Future playbooks are not added directly; they are gated behind evidence, position data, and risk inputs.
- Fundamental, chip, options-flow, event, COT, and macro data are included in the roadmap, but only after timestamp / freshness / missing-data rules are explicit.

### Blocking Issues

- No blocking issue is present for the roadmap itself.
- Implementation must not start beyond V2 / V3 until the previous version's promotion gate is met.
- The main execution risk is data leakage from slow or revised sources; V4 and later must enforce point-in-time timestamps before those sources influence validation.

### Risk Review

- **Decision confusion risk:** Mitigated by keeping `GO / WAIT / AVOID` primary and showing research layers as validation context.
- **UI clutter risk:** Mitigated by one sidebar entry, top-level lane selector, compact chips, and collapsed detail sections.
- **Overfitting risk:** Mitigated by control groups, baseline comparisons, forward validation, maturity gates, and a separate `探索性` state.
- **Causal-language risk:** Mitigated by labeling explanations as `候選原因` or `已驗證關聯`, never causal proof.
- **Options-risk risk:** Mitigated by blocking naked / margin-dependent structures until account capability, max loss, DTE, IV, and event-risk checks exist.
- **Portfolio-risk risk:** Mitigated by delaying hedge ratios, stock repair, covered-call sizing, and sell-put sizing until holdings, cost basis, and lot data are available.

### Scope Review

- V2 and V3 are implementation-ready in this plan.
- V4 through V10 are deliberately defined as roadmap gates, not implementation tasks inside the current branch.
- The plan should be split into separate implementation plans when work reaches V4, because factor registry, strategy backtesting, options simulation, and portfolio validation are independent subsystems.
