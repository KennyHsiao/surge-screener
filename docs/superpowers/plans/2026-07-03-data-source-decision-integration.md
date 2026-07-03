# Data Source Decision Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the already-collected Eastmoney money-flow and SEC EDGAR Form-4 data in the trader-facing decision surfaces without overstating data quality or slowing the normal refresh path.

**Architecture:** Keep the existing artifact-first model. Candidate ranking consumes a publishable/fresh `reports/money_flow/latest.json` artifact as a bounded confirmation component; the pipeline performs a fast top-N money-flow prefetch before final ranking so ranking is not forced to depend on stale artifacts. Options Cockpit shows Eastmoney and EDGAR as evidence/confirmation, not as hard GO/WAIT gates.

**Tech Stack:** Python 3.11, Streamlit, JSON artifacts under `reports/`, existing self-contained `scripts/test_*.py` tests, GitHub Actions scheduled/manual jobs.

---

## Scope And Review Decisions

### In Scope

- Add Eastmoney large-order money-flow evidence to `03_rank_candidates.py`.
- Keep rank score bounded at 100 and publish score weights explicitly.
- Refresh money-flow for a bounded top-N pre-rank candidate set during candidate pipeline, not during deployment.
- Display Eastmoney money-flow and EDGAR Form-4 insider confirmation in Options Cockpit.
- Preserve current `trade_state` behavior: money-flow evidence may explain context, but must not directly change `signal`.
- Keep all missing/stale source states fail-closed and visible.

### Out Of Scope For This Plan

- FRED/VIX term-structure expansion. FRED is already partially implemented in `scripts/market_events.py`; it needs a separate market-regime plan.
- Short-interest implementation. The repo currently has prompt text for short interest, but no concrete `shortPercentOfFloat` ingestion path.
- Replacing IV Rank with Sina HV. HV/realized-vol is useful context, but true IV Rank stays based on accumulated implied-vol snapshots in `scripts/iv_history.py`.
- Auto-loading EDGAR on every Options Cockpit page render. EDGAR is serial/rate-limited and should remain on-demand or cached.

### Blocking Review

- **Freshness blocker:** Ranking cannot rely on `reports/money_flow/latest.json` after the post-run Analytics refresh, because that happens after ranking. This plan fixes it with a bounded pre-rank money-flow pass.
- **Runtime blocker:** A full source refresh can be slow; this plan fetches money flow only for pre-ranked top-N candidates, not daily bars/universe/role suggestions.
- **Semantics blocker:** Eastmoney `main_net` is not SEC institutional holdings. UI and score names must say `large_order_flow` or `money_flow_confirmation`, not `institutional_flow`.
- **Decision blocker:** EDGAR Form-4 and Eastmoney flow are sparse/secondary confirmation signals. They must not become hard gates until forward tests prove lift.

---

## File Structure

- Modify `scripts/03_rank_candidates.py`
  - Add money-flow context loading and scoring helpers.
  - Add a bounded `large_order_flow_confirmation` score component.
  - Add CLI flags to enable/disable money-flow scoring and choose the artifact path.

- Modify `scripts/eastmoney_money_flow.py`
  - Add candidate-file ticker collection for ranked/filtered candidate JSON.
  - Add CLI flags for bounded top-N candidate refresh.

- Modify `scripts/run_candidate_pipeline.py`
  - Add fast money-flow prefetch between hard filter and final rank.
  - Keep deployment/source refresh unrelated to this path.

- Modify `ui/options_cockpit.py`
  - Add artifact-backed Eastmoney confirmation.
  - Add on-demand EDGAR Form-4 confirmation panel.

- Modify tests:
  - `scripts/test_rank_candidates.py`
  - `scripts/test_eastmoney_money_flow.py`
  - `scripts/test_candidate_pipeline_controls.py`
  - `scripts/test_options_cockpit_display.py`
  - `scripts/test_dashboard_navigation.py`

- Optional docs update:
  - `docs/system_panorama.md`
  - `docs/options_cockpit_roadmap.md`

---

### Task 1: Add Money-Flow Scoring To Candidate Ranking

**Files:**
- Modify: `scripts/03_rank_candidates.py`
- Modify: `scripts/test_rank_candidates.py`

- [ ] **Step 1: Add failing tests for publishable positive money flow**

Append this test to `scripts/test_rank_candidates.py` before `main()`:

```python
def test_money_flow_component_rewards_publishable_large_order_inflow() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-01", "main_net": 500_000.0, "main_pct": 2.5, "small_net": -50_000.0, "source": "eastmoney_push2his"},
            {"ticker": "AAPL", "date": "2026-07-02", "main_net": 600_000.0, "main_pct": 3.0, "small_net": -60_000.0, "source": "eastmoney_push2his"},
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 700_000.0, "main_pct": 3.4, "small_net": -70_000.0, "source": "eastmoney_push2his"},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-03")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-03", money_flow_context=context)

    component = ranked["score_components"]["large_order_flow_confirmation"]
    if component <= 0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["source"] != "eastmoney_push2his":
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["main_net_5d"] != 1_800_000.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["label"] != "主力流入確認":
        raise AssertionError(ranked)
```

Add the new test to the explicit `tests = [...]` list in `main()`.

- [ ] **Step 2: Add failing tests for fail-closed missing/unpublishable money flow**

Append this test to `scripts/test_rank_candidates.py` before `main()`:

```python
def test_money_flow_component_fails_closed_when_artifact_not_publishable() -> None:
    mod = _load_ranker()
    row = _base_candidate("AAPL", avg_dollar_vol_20d=10_000_000)
    artifact = {
        "publishable": False,
        "source": "eastmoney_push2his",
        "as_of_date": "2026-07-03",
        "rows": [
            {"ticker": "AAPL", "date": "2026-07-03", "main_net": 10_000_000.0, "main_pct": 9.9},
        ],
    }
    context = mod.build_money_flow_rank_context(artifact, as_of_date="2026-07-03")

    ranked = mod.rank_candidate(row, as_of_date="2026-07-03", money_flow_context=context)

    if ranked["score_components"]["large_order_flow_confirmation"] != 0.0:
        raise AssertionError(ranked)
    if ranked["money_flow_evidence"]["publishable"] is not False:
        raise AssertionError(ranked)
    if "資料缺口" not in ranked["money_flow_evidence"]["label"]:
        raise AssertionError(ranked)
```

Add the new test to the explicit `tests = [...]` list in `main()`.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
.venv/bin/python scripts/test_rank_candidates.py
```

Expected: FAIL because `build_money_flow_rank_context` and the `large_order_flow_confirmation` component do not exist yet.

- [ ] **Step 4: Implement money-flow context helpers**

In `scripts/03_rank_candidates.py`, add these constants after `REQUIRED_FIELDS`:

```python
MONEY_FLOW_GAP_LABEL = "資金流資料缺口，不加分"
MONEY_FLOW_STALE_DAYS = 3
SCORE_WEIGHTS = {
    "technical_trend": 23,
    "momentum_strength": 18,
    "launch_signal": 17,
    "liquidity_tradability": 17,
    "overheat_risk_control": 15,
    "large_order_flow_confirmation": 10,
}
```

Add these helpers after `_linear()`:

```python
def _date_ord(value: Any) -> int | None:
    try:
        text = str(value or "")[:10]
        if len(text) != 10:
            return None
        return datetime.fromisoformat(text).date().toordinal()
    except Exception:
        return None


def _scale_component(raw: float, raw_max: float, target_max: float) -> float:
    if raw_max <= 0:
        return 0.0
    return round(_clamp(raw, 0.0, raw_max) / raw_max * target_max, 1)


def _latest_rows_for_ticker(rows: list[dict[str, Any]], ticker: str, window: int = 5) -> list[dict[str, Any]]:
    sym = str(ticker or "").upper().lstrip("$")
    matched = [
        row for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").upper().lstrip("$") == sym
    ]
    dated = [(row, _date_ord(row.get("date") or row.get("flow_date"))) for row in matched]
    dated = [(row, ord_value) for row, ord_value in dated if ord_value is not None]
    dated.sort(key=lambda item: item[1], reverse=True)
    return [row for row, _ in dated[:window]]


def build_money_flow_rank_context(artifact: dict[str, Any] | None, *, as_of_date: str | None = None) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {"publishable": False, "source": "proxy", "by_ticker": {}}
    publishable = bool(artifact.get("publishable"))
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    source = str(artifact.get("source") or "eastmoney_push2his")
    as_of_ord = _date_ord(as_of_date)
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("ticker") or "").upper().lstrip("$")
        if not sym:
            continue
        by_ticker.setdefault(sym, []).append(row)
    return {
        "publishable": publishable,
        "source": source,
        "as_of_ord": as_of_ord,
        "by_ticker": by_ticker,
    }


def _money_flow_evidence(row: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper().lstrip("$")
    context = context if isinstance(context, dict) else {}
    publishable = bool(context.get("publishable"))
    by_ticker = context.get("by_ticker") if isinstance(context.get("by_ticker"), dict) else {}
    rows = by_ticker.get(ticker, []) if isinstance(by_ticker, dict) else []
    latest_rows = _latest_rows_for_ticker(rows, ticker, 5)
    if not publishable or not latest_rows:
        return {
            "publishable": False,
            "source": "proxy",
            "date": None,
            "main_net_5d": None,
            "main_pct_latest": None,
            "small_net_latest": None,
            "label": MONEY_FLOW_GAP_LABEL,
        }

    latest = latest_rows[0]
    latest_ord = _date_ord(latest.get("date") or latest.get("flow_date"))
    as_of_ord = context.get("as_of_ord")
    stale = bool(as_of_ord and latest_ord and as_of_ord - latest_ord > MONEY_FLOW_STALE_DAYS)
    main_net_5d = sum(
        _num(item.get("main_net")) or 0.0
        for item in latest_rows
        if _num(item.get("main_net")) is not None
    )
    main_pct_latest = _num(latest.get("main_pct"))
    small_net_latest = _num(latest.get("small_net"))
    if stale:
        label = "資金流過期，不加分"
    elif main_net_5d > 0:
        label = "主力流入確認"
    elif small_net_latest is not None and small_net_latest > 0 and main_net_5d < 0:
        label = "散戶追價、主力流出"
    elif main_net_5d < 0:
        label = "主力流出"
    else:
        label = "資金流中性"
    return {
        "publishable": True,
        "source": context.get("source") or latest.get("source") or "eastmoney_push2his",
        "date": latest.get("date") or latest.get("flow_date"),
        "stale": stale,
        "main_net_5d": round(main_net_5d, 2),
        "main_pct_latest": main_pct_latest,
        "small_net_latest": small_net_latest,
        "label": label,
    }


def _score_large_order_flow(row: dict[str, Any], evidence: dict[str, Any]) -> float:
    if not evidence.get("publishable") or evidence.get("stale"):
        return 0.0
    adv = _num(row.get("avg_dollar_vol_20d")) or 0.0
    main_net_5d = _num(evidence.get("main_net_5d")) or 0.0
    main_pct_latest = _num(evidence.get("main_pct_latest")) or 0.0
    if adv <= 0 or main_net_5d <= 0:
        return 0.0
    ratio = main_net_5d / adv
    score = _linear(ratio, 0.0, 0.25, 7.0)
    if main_pct_latest > 0:
        score += _linear(main_pct_latest, 0.0, 5.0, 3.0)
    return _clamp(score, 0.0, SCORE_WEIGHTS["large_order_flow_confirmation"])
```

- [ ] **Step 5: Wire the component into `rank_candidate`**

Change the signature:

```python
def rank_candidate(
    row: dict[str, Any],
    *,
    as_of_date: str | None = None,
    money_flow_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Replace the `components = {...}` block with:

```python
    money_flow = _money_flow_evidence(row, money_flow_context)
    components = {
        "technical_trend": _scale_component(_score_trend(row), 25, SCORE_WEIGHTS["technical_trend"]),
        "momentum_strength": _scale_component(_score_momentum(row), 20, SCORE_WEIGHTS["momentum_strength"]),
        "launch_signal": _scale_component(_score_launch(row), 20, SCORE_WEIGHTS["launch_signal"]),
        "liquidity_tradability": _scale_component(_score_liquidity(row), 20, SCORE_WEIGHTS["liquidity_tradability"]),
        "overheat_risk_control": _scale_component(_score_overheat_control(row), 15, SCORE_WEIGHTS["overheat_risk_control"]),
        "large_order_flow_confirmation": round(_score_large_order_flow(row, money_flow), 1),
    }
```

Add `money_flow_evidence` to the `ranked.update({...})` dict:

```python
        "money_flow_evidence": money_flow,
```

- [ ] **Step 6: Update `build_ranked_output` to accept injected artifact/context**

Change the signature:

```python
def build_ranked_output(
    universe: dict[str, Any],
    *,
    limit: int | None = None,
    options_gate_limit: int = 0,
    momentum_analyzer: Callable[[str], dict[str, Any]] | None = None,
    flow_analyzer: Callable[[str], dict[str, Any]] | None = None,
    money_flow_artifact: dict[str, Any] | None = None,
    money_flow_enabled: bool = True,
    status: RunStatus | None = None,
) -> dict[str, Any]:
```

Before ranking, add:

```python
    money_flow_context = build_money_flow_rank_context(money_flow_artifact, as_of_date=as_of_date) if money_flow_enabled else None
```

Change ranking construction:

```python
    ranked = [
        rank_candidate(c, as_of_date=as_of_date, money_flow_context=money_flow_context)
        for c in candidates
    ]
```

Replace the `score_weights` dict in the output with:

```python
        "score_weights": SCORE_WEIGHTS,
        "money_flow_scoring": {
            "enabled": money_flow_enabled,
            "source": (money_flow_context or {}).get("source") if money_flow_context else "disabled",
            "publishable": bool((money_flow_context or {}).get("publishable")) if money_flow_context else False,
        },
```

- [ ] **Step 7: Add CLI artifact loading**

In `main()`, add parser args:

```python
    parser.add_argument("--money-flow-path", default="reports/money_flow/latest.json",
                        help="Eastmoney money-flow artifact used as bounded ranking confirmation")
    parser.add_argument("--disable-money-flow", action="store_true",
                        help="disable money-flow ranking component for pre-rank/bootstrap runs")
```

Before `write_ranked_output(...)`, add:

```python
    money_flow_artifact = None
    if not args.disable_money_flow and args.money_flow_path:
        try:
            p = Path(args.money_flow_path)
            if p.is_file():
                money_flow_artifact = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            money_flow_artifact = None
```

Update `write_ranked_output(...)` signature so it accepts the new ranking inputs:

```python
def write_ranked_output(
    path: str | Path,
    universe: dict[str, Any],
    *,
    limit: int | None = None,
    options_gate_limit: int = 0,
    momentum_analyzer: Callable[[str], dict[str, Any]] | None = None,
    flow_analyzer: Callable[[str], dict[str, Any]] | None = None,
    money_flow_artifact: dict[str, Any] | None = None,
    money_flow_enabled: bool = True,
    status: RunStatus | None = None,
) -> dict[str, Any]:
```

Pass these into `build_ranked_output(...)` inside `write_ranked_output(...)`:

```python
        money_flow_artifact=money_flow_artifact,
        money_flow_enabled=money_flow_enabled,
```

Then pass the CLI-loaded values into `write_ranked_output(...)` from `main()`:

```python
        money_flow_artifact=money_flow_artifact,
        money_flow_enabled=not args.disable_money_flow,
```

- [ ] **Step 8: Run ranking tests**

Run:

```bash
.venv/bin/python scripts/test_rank_candidates.py
```

Expected: all tests pass; `test_rank_score_components_are_bounded_and_sorted` still sees every row score between 0 and 100 and component totals matching `rank_score`.

- [ ] **Step 9: Commit**

```bash
git add scripts/03_rank_candidates.py scripts/test_rank_candidates.py
git commit -m "rank: add Eastmoney money-flow confirmation score"
```

---

### Task 2: Add Candidate-File Ticker Collection For Money-Flow Refresh

**Files:**
- Modify: `scripts/eastmoney_money_flow.py`
- Modify: `scripts/test_eastmoney_money_flow.py`

- [ ] **Step 1: Add failing test for candidate-file collection**

Append this test to `scripts/test_eastmoney_money_flow.py` before `main()`:

```python
def test_collect_candidate_file_tickers_respects_rank_order_and_limit():
    with TemporaryDirectory() as td:
        path = Path(td) / "ranked_candidates.json"
        path.write_text(json.dumps({
            "ranked_candidates": [
                {"ticker": "NVDA"},
                {"ticker": "$AMD"},
                {"ticker": "NVDA"},
                {"symbol": "MU"},
            ]
        }), encoding="utf-8")

        tickers = emf.collect_candidate_file_tickers(path, limit=2)

    assert tickers == ["NVDA", "AMD"], tickers
```

Add it to the explicit `tests = [...]` list.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python scripts/test_eastmoney_money_flow.py
```

Expected: FAIL because `collect_candidate_file_tickers` does not exist.

- [ ] **Step 3: Implement candidate-file collection**

In `scripts/eastmoney_money_flow.py`, add after `_collect_tickers_from_value(...)`:

```python
def collect_candidate_file_tickers(path: str | Path, *, limit: int | None = None) -> list[str]:
    data = _load_json(Path(path))
    rows = []
    if isinstance(data, dict):
        for key in ("ranked_candidates", "tickers"):
            value = data.get(key)
            if isinstance(value, list):
                rows = value
                break
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        _append_ticker(out, row.get("ticker") or row.get("symbol"))
        if limit and len(out) >= limit:
            break
    return out
```

- [ ] **Step 4: Add CLI flags**

In `main()`, add parser args:

```python
    parser.add_argument("--candidate-file", default="",
                        help="ranked/filtered candidate JSON to use as a bounded ticker source")
    parser.add_argument("--candidate-limit", type=int, default=0,
                        help="max tickers to collect from --candidate-file; 0 means no limit")
    parser.add_argument("--only-candidate-file", action="store_true",
                        help="use only --candidate-file tickers instead of all platform sources")
```

Replace ticker collection in `main()` with:

```python
    candidate_tickers = collect_candidate_file_tickers(
        args.candidate_file,
        limit=args.candidate_limit or None,
    ) if args.candidate_file else []
    if args.only_candidate_file:
        tickers = _dedupe_tickers([*candidate_tickers, *_parse_tickers(args.tickers)])
    else:
        tickers = collect_money_flow_tickers(
            reports_dir=args.reports_dir,
            content_dir=args.content_dir,
            extra_tickers=[*candidate_tickers, *_parse_tickers(args.tickers)],
        )
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python scripts/test_eastmoney_money_flow.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/eastmoney_money_flow.py scripts/test_eastmoney_money_flow.py
git commit -m "data: collect money-flow tickers from candidate files"
```

---

### Task 3: Add Fast Pre-Rank Money-Flow Prefetch To Candidate Pipeline

**Files:**
- Modify: `scripts/run_candidate_pipeline.py`
- Modify: `scripts/test_candidate_pipeline_controls.py`

- [ ] **Step 1: Update failing pipeline wrapper expectation**

In `scripts/test_candidate_pipeline_controls.py`, update `test_pipeline_wrapper_expands_full_refresh_without_make`:

```python
    if len(steps) != 4:
        raise AssertionError(steps)
```

Then add these assertions after the existing hard-filter assertion:

```python
    if "scripts/03_rank_candidates.py" not in steps[1].argv or "--disable-money-flow" not in steps[1].argv:
        raise AssertionError(steps[1].argv)
    if "scripts/eastmoney_money_flow.py" not in steps[2].argv:
        raise AssertionError(steps[2].argv)
    if "--only-candidate-file" not in steps[2].argv:
        raise AssertionError(steps[2].argv)
    if "scripts/03_rank_candidates.py" not in steps[3].argv:
        raise AssertionError(steps[3].argv)
```

Change later rank assertions from `steps[1]` to `steps[3]`.

- [ ] **Step 2: Add test for disabling prefetch**

Append to `scripts/test_candidate_pipeline_controls.py`:

```python
def test_pipeline_wrapper_can_disable_money_flow_prefetch() -> None:
    spec = importlib.util.spec_from_file_location(
        "run_candidate_pipeline_no_money_flow_prefetch",
        ROOT / "scripts" / "run_candidate_pipeline.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    args = mod.parse_args(["--mode", "full_refresh", "--no-money-flow-prefetch"])
    steps = mod.build_steps(args)

    if len(steps) != 2:
        raise AssertionError(steps)
    flattened = [part for step in steps for part in step.argv]
    if "scripts/eastmoney_money_flow.py" in flattened:
        raise AssertionError(flattened)
```

The file auto-discovers tests with names starting `test_`, so no explicit list update is needed.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
.venv/bin/python scripts/test_candidate_pipeline_controls.py
```

Expected: FAIL because pipeline still has only hard-filter and rank steps.

- [ ] **Step 4: Add CLI controls**

In `parse_args()`, add:

```python
    parser.add_argument("--money-flow-prefetch", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--money-flow-prefetch-limit", type=int, default=80)
```

- [ ] **Step 5: Generalize `_rank_step`**

Change `_rank_step` signature:

```python
def _rank_step(
    args: argparse.Namespace,
    *,
    start_status: bool,
    output: str | None = None,
    history_dir: str | None = "reports/candidate_rankings",
    options_gate_limit: int | None = None,
    disable_money_flow: bool = False,
) -> PipelineStep:
```

Change the output/history/options values in the argv construction:

```python
        "--options-gate-limit",
        str(int(args.options_gate_limit if options_gate_limit is None else options_gate_limit)),
```

```python
        "--history-dir",
        "" if history_dir is None else history_dir,
        "--output",
        output or _candidate_path("ranked_candidates.json"),
```

Before returning, add:

```python
    if disable_money_flow:
        argv.append("--disable-money-flow")
```

- [ ] **Step 6: Add money-flow prefetch step**

Add after `_rank_step(...)`:

```python
def _money_flow_prefetch_rank_path() -> str:
    return str(REPO / "reports" / "run_status" / "money_flow_prefetch_ranked_candidates.json")


def _money_flow_prefetch_step(args: argparse.Namespace) -> PipelineStep:
    return PipelineStep([
        sys.executable,
        "scripts/eastmoney_money_flow.py",
        "--candidate-file",
        _money_flow_prefetch_rank_path(),
        "--candidate-limit",
        str(int(args.money_flow_prefetch_limit)),
        "--only-candidate-file",
        "--reports-dir",
        "reports",
        "--content-dir",
        "content",
    ])
```

- [ ] **Step 7: Wire two-pass full refresh/rank_existing**

Replace `build_steps()` with:

```python
def build_steps(args: argparse.Namespace) -> list[PipelineStep]:
    if args.mode == "full_refresh":
        steps = [_hard_filter_step(args)]
        if args.money_flow_prefetch:
            steps.append(_rank_step(
                args,
                start_status=False,
                output=_money_flow_prefetch_rank_path(),
                history_dir=None,
                options_gate_limit=0,
                disable_money_flow=True,
            ))
            steps.append(_money_flow_prefetch_step(args))
        steps.append(_rank_step(args, start_status=False))
        return steps
    if args.mode == "rank_existing":
        steps = []
        if args.money_flow_prefetch:
            steps.append(_rank_step(
                args,
                start_status=True,
                output=_money_flow_prefetch_rank_path(),
                history_dir=None,
                options_gate_limit=0,
                disable_money_flow=True,
            ))
            steps.append(_money_flow_prefetch_step(args))
            steps.append(_rank_step(args, start_status=False))
            return steps
        return [_rank_step(args, start_status=True)]
    if args.mode == "llm_deep_check":
        return [_llm_preflight_step(args), _llm_score_step(args)]
    raise ValueError(f"unknown candidate pipeline mode: {args.mode}")
```

- [ ] **Step 8: Run tests**

Run:

```bash
.venv/bin/python scripts/test_candidate_pipeline_controls.py
```

Expected: all tests pass. If runtime-path tests assume exact step indexes, update them to identify steps by script name instead of positional index.

- [ ] **Step 9: Commit**

```bash
git add scripts/run_candidate_pipeline.py scripts/test_candidate_pipeline_controls.py
git commit -m "pipeline: prefetch bounded money-flow before ranking"
```

---

### Task 4: Add Options Cockpit External Confirmation Panel

**Files:**
- Modify: `ui/options_cockpit.py`
- Modify: `scripts/test_options_cockpit_display.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Add failing pure helper tests**

In `scripts/test_options_cockpit_display.py`, append before `main()`:

```python
def test_money_flow_signal_formats_publishable_artifact() -> None:
    from ui import options_cockpit as oc
    artifact = {
        "publishable": True,
        "source": "eastmoney_push2his",
        "rows": [
            {"ticker": "NVDA", "date": "2026-07-03", "main_net": 2_000_000.0, "main_pct": 4.2, "small_net": -500_000.0, "source": "eastmoney_push2his"}
        ],
    }

    signal = oc._money_flow_confirmation_signal("NVDA", artifact)

    if signal["state"] != "positive":
        raise AssertionError(signal)
    if signal["label"] != "主力流入確認":
        raise AssertionError(signal)
    if signal["source"] != "eastmoney_push2his":
        raise AssertionError(signal)
```

Also append:

```python
def test_insider_confirmation_signal_formats_edgar_net_buy() -> None:
    from ui import options_cockpit as oc

    signal = oc._insider_confirmation_signal({
        "ticker": "NVDA",
        "net_usd": 1_250_000.0,
        "n_buy": 3,
        "n_sell": 1,
        "n_txn": 4,
        "window_days": 30,
        "as_of": "2026-07-03",
    })

    if signal["state"] != "positive":
        raise AssertionError(signal)
    if "$1.25M" not in signal["value"]:
        raise AssertionError(signal)
    if signal["label"] != "內部人淨買":
        raise AssertionError(signal)
```

Add both tests to the explicit `tests = [...]` list.

- [ ] **Step 2: Add dashboard text test**

In `scripts/test_dashboard_navigation.py`, add to `test_options_cockpit_contract_panel_is_tradeability_first`:

```python
    assert_contains(COCKPIT, "def _render_external_confirmation")
    assert_contains(COCKPIT, "外部確認")
    assert_contains(COCKPIT, "載入 EDGAR Form-4")
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL because helper functions and panel do not exist.

- [ ] **Step 4: Add money-flow helper functions**

In `ui/options_cockpit.py`, add `import json` with the existing standard-library imports:

```python
import hashlib
import json
import math
import sys
```

Then add after `_quote_source_chip(...)`:

```python
def _short_money(value: float | None) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(float(value))
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:.0f}"


def _money_flow_confirmation_signal(ticker: str, artifact: dict | None) -> dict:
    if not isinstance(artifact, dict) or not artifact.get("publishable"):
        return {
            "state": "unknown",
            "label": "資金流資料缺口",
            "value": "—",
            "source": "proxy",
            "caveat": "東財資金流未達可發布覆蓋率或尚未刷新。",
        }
    rows = artifact.get("rows") if isinstance(artifact.get("rows"), list) else []
    sym = str(ticker or "").upper().lstrip("$")
    matched = [
        row for row in rows
        if isinstance(row, dict) and str(row.get("ticker") or "").upper().lstrip("$") == sym
    ]
    matched.sort(key=lambda row: str(row.get("date") or row.get("flow_date") or ""), reverse=True)
    if not matched:
        return {
            "state": "unknown",
            "label": "無個股資金流",
            "value": "—",
            "source": artifact.get("source") or "eastmoney_push2his",
            "caveat": "此 ticker 未在最新 money-flow artifact 中。",
        }
    latest = matched[0]
    main_net = _to_float(latest.get("main_net"))
    main_pct = _to_float(latest.get("main_pct"))
    small_net = _to_float(latest.get("small_net"))
    if main_net is not None and main_net > 0:
        label, state = "主力流入確認", "positive"
    elif small_net is not None and small_net > 0 and main_net is not None and main_net < 0:
        label, state = "散戶追價、主力流出", "negative"
    elif main_net is not None and main_net < 0:
        label, state = "主力流出", "negative"
    else:
        label, state = "資金流中性", "neutral"
    pct = f" ({main_pct:+.1f}%)" if isinstance(main_pct, (int, float)) else ""
    return {
        "state": state,
        "label": label,
        "value": f"{_short_money(main_net)}{pct}",
        "source": latest.get("source") or artifact.get("source") or "eastmoney_push2his",
        "date": latest.get("date") or latest.get("flow_date"),
        "caveat": "東財資金流模型；非 SEC 機構持倉、非逐筆券商真實買賣。",
    }


def _insider_confirmation_signal(data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {
            "state": "unknown",
            "label": "EDGAR 未載入",
            "value": "—",
            "source": "sec_edgar_form4",
            "caveat": "按需載入，避免 SEC 冷快取拖慢頁面。",
        }
    net_usd = _to_float(data.get("net_usd"))
    if net_usd is not None and net_usd > 0:
        label, state = "內部人淨買", "positive"
    elif net_usd is not None and net_usd < 0:
        label, state = "內部人淨賣", "negative"
    else:
        label, state = "內部人中性/無交易", "neutral"
    return {
        "state": state,
        "label": label,
        "value": _short_money(net_usd),
        "source": "sec_edgar_form4",
        "date": data.get("as_of"),
        "caveat": f"近 {int(data.get('window_days') or 30)} 日 open-market Form-4 P/S；交易數 {int(data.get('n_txn') or 0)}。",
    }
```

- [ ] **Step 5: Add artifact loader and render function**

Add after `_insider_confirmation_signal(...)`:

```python
def _load_money_flow_artifact(path: Path | None = None) -> dict | None:
    path = path or (Path(__file__).resolve().parent.parent / "reports" / "money_flow" / "latest.json")
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except Exception:
        return None


def _render_signal_card(container, signal: dict) -> None:
    state = signal.get("state")
    color = _GREEN if state == "positive" else _RED if state == "negative" else _MUTED
    container.markdown(f"**{signal.get('label', '—')}**")
    container.markdown(f"<span style='font-size:1.2rem;font-weight:800;color:{color}'>{signal.get('value', '—')}</span>", unsafe_allow_html=True)
    meta = " · ".join(str(x) for x in [signal.get("source"), signal.get("date")] if x)
    if meta:
        container.caption(meta)
    if signal.get("caveat"):
        container.caption(signal["caveat"])


def _render_external_confirmation(d: CockpitData) -> None:
    st.markdown("#### 外部確認")
    c1, c2 = st.columns(2)
    mf_signal = _money_flow_confirmation_signal(d.ticker, _load_money_flow_artifact())
    _render_signal_card(c1, mf_signal)
    if c2.button("載入 EDGAR Form-4", key=f"edgar_form4_{d.ticker}"):
        try:
            from scripts import insider_edgar
        except ImportError:
            import insider_edgar  # type: ignore
        with st.spinner("讀取 SEC EDGAR Form-4..."):
            signal = _insider_confirmation_signal(insider_edgar.insider_net_edgar(d.ticker, 30))
        _render_signal_card(c2, signal)
    else:
        _render_signal_card(c2, _insider_confirmation_signal(None))
```

- [ ] **Step 6: Call the panel in both render paths**

In both render paths, place after `_render_direction_vol(d)`: `render_for(ticker)` and `render()`.

```python
    _render_external_confirmation(d)
```

- [ ] **Step 7: Run tests**

Run:

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add ui/options_cockpit.py scripts/test_options_cockpit_display.py scripts/test_dashboard_navigation.py
git commit -m "ui: show external confirmation in options cockpit"
```

---

### Task 5: Documentation And Guardrail Updates

**Files:**
- Modify: `docs/system_panorama.md`
- Modify: `docs/options_cockpit_roadmap.md`

- [ ] **Step 1: Update data-source semantics**

In `docs/system_panorama.md`, add a note near the data-source overview:

```markdown
### Decision-Grade Source Semantics

- Eastmoney `main_net` is labeled as large-order money-flow confirmation, not SEC institutional ownership.
- SEC EDGAR Form-4 is insider open-market evidence and remains sparse/on-demand in trader UI.
- Sina historical bars support realized-vol/HV context; they do not replace true IV Rank from `reports/iv_history`.
- LLM providers are analysis layers, not primary market-data sources.
```

- [ ] **Step 2: Update Options Cockpit roadmap**

In `docs/options_cockpit_roadmap.md`, add:

```markdown
## External Confirmation Layer

The cockpit shows Eastmoney money-flow and SEC EDGAR Form-4 as confirmation evidence.
These signals do not hard-gate GO/WAIT because coverage, freshness, and event sparsity vary by ticker.
Eastmoney is labeled as large-order flow; EDGAR is loaded on demand to avoid SEC cold-cache latency.
```

- [ ] **Step 3: Run docs-adjacent tests**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docs/system_panorama.md docs/options_cockpit_roadmap.md
git commit -m "docs: clarify decision-grade data source semantics"
```

---

### Task 6: End-To-End Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_rank_candidates.py
.venv/bin/python scripts/test_eastmoney_money_flow.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_trade_state_snapshots.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: all pass.

- [ ] **Step 2: Run source-refresh contract tests**

Run:

```bash
.venv/bin/python scripts/test_data_source_refresh.py
.venv/bin/python scripts/test_analytics_store.py
.venv/bin/python scripts/test_analytics_checks.py
```

Expected: all pass. If `test_analytics_store.py` is slow, record runtime and failures exactly.

- [ ] **Step 3: Run a local no-network pipeline shape check**

Run:

```bash
.venv/bin/python - <<'PY'
import importlib.util
from pathlib import Path

root = Path.cwd()
spec = importlib.util.spec_from_file_location("p", root / "scripts" / "run_candidate_pipeline.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
args = mod.parse_args(["--mode", "full_refresh", "--money-flow-prefetch-limit", "5", "--options-gate-limit", "0"])
for idx, step in enumerate(mod.build_steps(args), 1):
    print(idx, " ".join(step.argv))
PY
```

Expected: four steps:

1. `scripts/01_hard_filter.py`
2. `scripts/03_rank_candidates.py ... --disable-money-flow ...`
3. `scripts/eastmoney_money_flow.py ... --only-candidate-file ...`
4. `scripts/03_rank_candidates.py ...`

- [ ] **Step 4: Compare diff against plan**

Run:

```bash
git diff --stat
git diff -- scripts/03_rank_candidates.py scripts/eastmoney_money_flow.py scripts/run_candidate_pipeline.py ui/options_cockpit.py
```

Expected: changes match Tasks 1-5 only. No unrelated report artifacts are staged.

- [ ] **Step 5: Final commit if not already committed task-by-task**

If task commits were not created individually, run:

```bash
git add scripts/03_rank_candidates.py scripts/test_rank_candidates.py scripts/eastmoney_money_flow.py scripts/test_eastmoney_money_flow.py scripts/run_candidate_pipeline.py scripts/test_candidate_pipeline_controls.py ui/options_cockpit.py scripts/test_options_cockpit_display.py scripts/test_dashboard_navigation.py docs/system_panorama.md docs/options_cockpit_roadmap.md
git commit -m "feat: integrate decision-grade money-flow and insider evidence"
```

---

## Final Review

### Spec Coverage

- Eastmoney money-flow is used in individual candidate ranking: Task 1.
- Ranking does not depend on stale post-run source refresh: Task 3.
- Options Cockpit gets money-flow and EDGAR evidence: Task 4.
- EDGAR remains on-demand and not a hard gate: Task 4.
- IV Rank/HV semantics are kept separate: Scope and docs in Task 5.
- FRED/VIX/short interest are explicitly deferred: Scope section.

### Remaining Risks

- Eastmoney endpoint coverage for US tickers may vary. Ranking score must stay bounded and fail-closed.
- Two-pass ranking changes the pipeline shape; UI status may need minor wording if users notice an extra pre-rank step.
- Importing `ui/options_cockpit.py` tests depends on Streamlit/Plotly being installed, which is already required by `requirements.txt`.

### Recommendation

Proceed with Tasks 1-4 as one implementation branch. Task 5 can be done in the same branch if docs are expected to ship with the feature; otherwise keep it as a small follow-up commit.
