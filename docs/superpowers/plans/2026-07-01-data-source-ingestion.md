# Data Source Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the high-value US stock data sources from `global-stock-data` into the platform in phases, persist only the data that improves trading decisions, historical validation, and UI reliability.

**Architecture:** Keep external data fetching behind small provider adapters. Keep JSON/Parquet reports as the write artifacts and materialize first-class analytics tables through the existing `scripts/analytics_store.py` DuckDB read model. Do not replace yfinance globally; add Eastmoney/Sina/Tencent as routed sources for universe, money flow, long-history bars, and quote fallback.

**Tech Stack:** Python, requests/httpx, pandas, Parquet, DuckDB, existing report folders under `reports/`, existing Streamlit UI modules, self-contained script tests.

---

## Source-To-DB Decision Matrix

| Data | Persist? | First-class table? | Why it helps the platform | Refresh cadence |
| --- | --- | --- | --- | --- |
| Eastmoney full US universe/search/secid | Yes | Yes: `security_master`, `security_identifiers`, `universe_snapshots` | Better ticker coverage, ETF/common-stock classification, stable search, fewer Yahoo-only misses | Daily pre-market or after close |
| SEC ticker to CIK mapping | Yes | Yes: `security_identifiers` | Required by 8-K, Form 4, 10-Q/10-K, XBRL | Weekly cache; refresh on miss |
| Daily OHLCV from Yahoo/Sina | Yes | Yes: `daily_bars` | Cycle, CE, Risk Guard, backtests, validation, long-history analogs | Daily after close; targeted historical backfill |
| Eastmoney daily money flow | Yes | Yes: `daily_money_flow` | Upgrades theme flow and trade state from price-volume proxy to source-defined fund-flow evidence | Daily after close for watchlist/candidates/theme tickers |
| IV snapshots | Yes | Already yes: `iv_history` | yfinance has no historical IV; platform must accumulate it | Daily snapshot; optional intraday |
| Options flow signals | Yes | Already yes: `options_flow_signals` | Repeated flow and forward validation | Per scan |
| Full options chain | Partially | Not in phase 1; table only for selected summaries | Full chain is large; store summaries/selected strikes before all-expiry archival | On-demand snapshot for selected tickers |
| Cycle/CE/trade state snapshots | Yes | Yes: `trade_state_snapshots` | Reconstruct why a ticker was holding/take-profit/stop-loss at a date | Daily for watchlist/candidates/holdings |
| Theme/industry role tags | Yes | Yes: `industry_role_assignments` | Query tags everywhere there is a ticker; audit review changes | On review action and daily export |
| SEC filings/Form 4 | Yes | Yes: `sec_filings`, `insider_transactions` | Catalyst and insider conviction evidence; official source | Daily for watchlist/candidates |
| SEC XBRL metrics | Yes | Yes: `fundamental_metrics` | Official historical fundamentals for DD and factor testing | Quarterly plus on-demand |
| Eastmoney GMAININDICATOR / three statements | Yes, curated metrics first | Yes: `fundamental_metrics` with source field | Adds translated/curated metrics and trend display; not primary truth over SEC | Quarterly plus on-demand |
| Realtime quote fallback | Cache only | No | UI reliability; no long-term analytics value unless used in a decision snapshot | 1-5 minute cache |
| Search autocomplete raw responses | Cache only | No | Re-fetchable UI convenience data | 1 day cache |
| Raw news content | No raw content | Metadata only if needed | Licensing risk; store URL/publisher/time/sentiment, not full text | On-demand |

## Phase 0: Provider Adapter And Source Contract

**Files:**
- Create: `scripts/global_stock_data.py`
- Create: `scripts/test_global_stock_data.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Define provider response contracts**

Create `scripts/global_stock_data.py` with pure parsing helpers and network wrappers for:
- `eastmoney_search(keyword, count=10)`
- `eastmoney_market_list(market, page=1, page_size=100)`
- `eastmoney_money_flow(secid, limit=120)`
- `sina_us_daily_bars(ticker, start=None, end=None)`
- `sina_us_quote(ticker)`
- `tencent_us_quote(ticker)`

Every returned dict must include:
- `source`
- `fetched_at`
- `status`
- provider-specific `raw` only when explicitly requested by a `include_raw=False` argument.

- [x] **Step 2: Write adapter tests with fake HTTP**

Create `scripts/test_global_stock_data.py` with fixture JSON/text strings for one response per endpoint. Tests must verify:
- unknown/malformed provider responses return `status="unavailable"` instead of raising
- Eastmoney `diff` works when it is a list and when it is a dict keyed by row number
- money flow rows parse into date, close, main_net, super_big_net, big_net, mid_net, small_net, main_pct
- quote fallback normalizes price, market_cap, pe, pb, eps, timestamp where available

Run:
```bash
.venv/bin/python scripts/test_global_stock_data.py
```

Expected:
```text
global stock data adapter tests passed
```

- [x] **Step 3: Document data-source boundaries**

Update `docs/analytics-store-data-inventory.md` with a section named `External Market Data Sources`:
- Eastmoney: universe, search, money flow, GMAIN
- Sina: long daily bars, quote fallback
- Tencent: quote fallback
- Yahoo/yfinance: options, analyst, existing fundamentals, adjusted OHLCV
- SEC: filings, CIK, XBRL

Add the rule: "Raw provider responses are not first-class analytics data unless a stable query pattern exists."

## Phase 1: Universe And Identifier Store

**Files:**
- Create: `scripts/universe_refresh.py`
- Create: `scripts/test_universe_refresh.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Build daily universe artifact**

Create `scripts/universe_refresh.py`.

Inputs:
- Eastmoney NASDAQ: `m:105`
- Eastmoney NYSE: `m:106`
- Eastmoney US ETF/other: `m:107`
- SEC `company_tickers.json` from existing `_cik_for` plumbing

Output:
- `reports/universe/YYYY-MM-DD.json`

Artifact shape:
```json
{
  "as_of_date": "2026-07-01",
  "generated_at": "2026-07-01T00:00:00Z",
  "sources": ["eastmoney_push2", "sec_company_tickers"],
  "markets": ["NASDAQ", "NYSE", "US_OTHER"],
  "securities": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "exchange": "NASDAQ",
      "asset_type": "stock",
      "eastmoney_secid": "105.AAPL",
      "cik": "0000320193",
      "is_active": true
    }
  ],
  "coverage": {
    "eastmoney_total": 0,
    "sec_mapped": 0,
    "missing_cik": 0
  }
}
```

- [x] **Step 2: Add analytics tables**

Modify `scripts/analytics_store.py`:
- Add `SECURITY_MASTER_COLUMNS`
- Add `SECURITY_IDENTIFIER_COLUMNS`
- Add `UNIVERSE_SNAPSHOT_COLUMNS`
- Add `KNOWN_TABLES` entries:
  - `security_master`
  - `security_identifiers`
  - `universe_snapshots`
- Add `export_universe_snapshots(reports_dir, analytics_root=None)`
- Add this exporter to `refresh_all()`

Table grains:
- `security_master`: one ticker per latest universe export
- `security_identifiers`: one ticker/provider identifier per latest universe export
- `universe_snapshots`: one ticker per universe date

- [x] **Step 3: Test universe export**

Extend `scripts/test_analytics_store.py` with a temp `reports/universe/2026-07-01.json`.

Assert:
- `security_master` contains AAPL once
- `security_identifiers` contains Eastmoney secid and SEC CIK rows
- `universe_snapshots` contains the snapshot date and source coverage

Run:
```bash
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
analytics store tests: all passed
```

## Phase 2: Daily Bars Store For Backtests, Cycle, CE, And Risk Guard

**Files:**
- Create: `scripts/daily_bars_store.py`
- Create: `scripts/test_daily_bars_store.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Define daily-bar source policy**

Implement `scripts/daily_bars_store.py` with:
- Yahoo/yfinance adjusted OHLCV as primary for return calculations
- Sina daily bars as long-history fallback and cross-check source
- `is_adjusted` flag
- `source_priority` value
- `data_quality_status`: `ok`, `fallback`, `mismatch`, `unavailable`

Output:
- `reports/market_data/daily_bars/YYYY-MM-DD.parquet`

Columns:
```text
as_of_date
ticker
bar_date
open
high
low
close
adj_close
volume
source
is_adjusted
data_quality_status
```

- [x] **Step 2: Add cross-source validation**

In `scripts/daily_bars_store.py`, compare latest close from Yahoo and Sina when both exist.

Rules:
- absolute close difference under 1%: `ok`
- 1%-3%: `mismatch_warning`
- above 3%: `mismatch_blocked`

Do not publish a bar as primary when it is `mismatch_blocked`.

- [x] **Step 3: Export `daily_bars` to DuckDB**

Modify `scripts/analytics_store.py`:
- Add `DAILY_BAR_COLUMNS`
- Add `daily_bars` to `KNOWN_TABLES`
- Add `export_daily_bars(reports_dir, analytics_root=None)`
- Add table to `refresh_all()`

Query patterns to support:
- `ticker + bar_date range`
- `bar_date + source`
- `ticker + source + data_quality_status`

- [x] **Step 4: Test daily bars**

Create tests that write a small Parquet fixture under `reports/market_data/daily_bars/`.

Assert DuckDB can query:
```sql
select ticker, count(*) as bars
from daily_bars
where ticker = 'AAPL'
group by ticker
```

Run:
```bash
.venv/bin/python scripts/test_daily_bars_store.py
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
daily bars store tests passed
analytics store tests: all passed
```

## Phase 3: Eastmoney Money Flow Store

**Files:**
- Create: `scripts/eastmoney_money_flow.py`
- Create: `scripts/test_eastmoney_money_flow.py`
- Modify: `scripts/theme_flow.py`
- Modify: `scripts/trade_state.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Build money-flow fetcher**

Create `scripts/eastmoney_money_flow.py`.

Inputs:
- tickers from latest candidate rankings
- tickers from watchlist sources
- tickers from approved industry/theme roles
- optional `--tickers AAPL,NVDA`

Output:
- `reports/money_flow/YYYY-MM-DD.json`

Artifact shape:
```json
{
  "as_of_date": "2026-07-01",
  "generated_at": "2026-07-01T00:00:00Z",
  "source": "eastmoney_push2his",
  "coverage": {"requested": 0, "resolved": 0, "unavailable": 0},
  "rows": [
    {
      "ticker": "AAPL",
      "date": "2026-06-30",
      "close": 0.0,
      "change_pct": 0.0,
      "main_net": 0.0,
      "main_pct": 0.0,
      "super_big_net": 0.0,
      "big_net": 0.0,
      "mid_net": 0.0,
      "small_net": 0.0,
      "source": "eastmoney_push2his"
    }
  ]
}
```

- [x] **Step 2: Fail closed on poor coverage**

Rules:
- if `resolved / requested < 0.70`, write the artifact with `publishable=false`
- UI must show a data-gap badge and keep current proxy behavior
- only use Eastmoney money flow in scores when `publishable=true`

- [x] **Step 3: Export `daily_money_flow` to DuckDB**

Modify `scripts/analytics_store.py`:
- Add `DAILY_MONEY_FLOW_COLUMNS`
- Add `daily_money_flow` to `KNOWN_TABLES`
- Add `export_daily_money_flow(reports_dir, analytics_root=None)`
- Add table to `refresh_all()`

Columns:
```text
source_file
as_of_date
generated_at
ticker
flow_date
close
change_pct
main_net
main_pct
super_big_net
big_net
mid_net
small_net
source
publishable
raw_row_json
```

- [x] **Step 4: Wire into theme flow as evidence, not replacement**

Modify `scripts/theme_flow.py`:
- Keep existing yfinance price-volume proxy as fallback
- Add optional Eastmoney overlay when `reports/money_flow/latest.json` or dated artifact is publishable
- Add output fields:
  - `eastmoney_main_net_5d`
  - `eastmoney_main_net_20d`
  - `eastmoney_main_pct_latest`
  - `money_flow_source`
  - `money_flow_caveat`

UI label must say:
```text
東財資金流模型；非 SEC 機構持倉、非逐筆券商真實買賣。
```

- [x] **Step 5: Wire into trade state**

Modify `scripts/trade_state.py`:
- Add a money-flow evidence block to each ticker row
- Do not change final verdict solely from money flow in this phase
- Add reasons like:
  - `主力流入支持持有`
  - `上漲但主力流出，追價風險`
  - `小單流入、主力流出，偏散戶追價`

- [x] **Step 6: Test money flow**

Run:
```bash
.venv/bin/python scripts/test_eastmoney_money_flow.py
.venv/bin/python scripts/test_theme_flow.py
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
all tests passed
```

## Phase 4: Quote Fallback Without DB Pollution

**Files:**
- Create: `scripts/quote_fallback.py`
- Create: `scripts/test_quote_fallback.py`
- Modify: `ui/stock_checkup.py`
- Modify: `ui/today_decision.py`
- Modify: `ui/options_cockpit.py`

- [x] **Step 1: Implement routed quote fallback**

Create `scripts/quote_fallback.py`.

Provider order:
1. yfinance when current page already has a yfinance object
2. Sina quote
3. Tencent quote
4. Eastmoney push2 quote

Return shape:
```json
{
  "ticker": "AAPL",
  "price": 0.0,
  "currency": "USD",
  "source": "sina_us_quote",
  "fetched_at": "2026-07-01T00:00:00Z",
  "stale": false,
  "fields": {
    "market_cap": 0.0,
    "pe": 0.0,
    "pb": 0.0,
    "eps": 0.0,
    "week_52_high": 0.0,
    "week_52_low": 0.0
  }
}
```

- [x] **Step 2: Cache only**

Use existing `scripts/cache.py`.

TTL:
- market hours: 60 seconds
- outside market hours: 15 minutes

Do not add a quote table to DuckDB in this phase. If a quote is used to generate a formal signal, that signal table must store the price and source inside the signal snapshot.

- [x] **Step 3: UI adoption**

Modify:
- `ui/stock_checkup.py`: price card fallback
- `ui/today_decision.py`: ticker price display fallback
- `ui/options_cockpit.py`: underlying spot fallback when yfinance quote fails

Show source chip:
```text
來源：Sina fallback · 1 分鐘快取
```

- [x] **Step 4: Test fallback ordering**

Run:
```bash
.venv/bin/python scripts/test_quote_fallback.py
```

Expected:
```text
quote fallback tests passed
```

## Phase 5: Trade-State Snapshot Store

**Files:**
- Modify: `scripts/trade_state.py`
- Create: `scripts/test_trade_state_snapshots.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Persist daily trade-state snapshots**

Modify `scripts/trade_state.py` to write:
- `reports/trade_state/YYYY-MM-DD.json`

Rows include:
```text
as_of_date
ticker
price
cycle
cycle_source
ce_trend
ce_source
verdict
risk_level
industry_role
industry_role_status
main_net_latest
main_pct_latest
atr_pct
options_flow_score
social_mentions
reasons_json
data_sources_json
raw_row_json
```

- [x] **Step 2: Export `trade_state_snapshots`**

Modify `scripts/analytics_store.py`:
- Add `TRADE_STATE_SNAPSHOT_COLUMNS`
- Add `trade_state_snapshots` to `KNOWN_TABLES`
- Add `export_trade_state_snapshots(reports_dir, analytics_root=None)`
- Add table to `refresh_all()`

Use scalar columns for common filters:
- `ticker`
- `as_of_date`
- `cycle`
- `ce_trend`
- `verdict`
- `industry_role`

- [x] **Step 3: Test snapshot export**

Run:
```bash
.venv/bin/python scripts/test_trade_state_snapshots.py
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
trade state snapshot tests passed
analytics store tests: all passed
```

## Phase 6: Fundamentals And SEC Metrics Store

**Files:**
- Create: `scripts/fundamental_metrics_store.py`
- Create: `scripts/test_fundamental_metrics_store.py`
- Modify: `scripts/fundamentals_free.py`
- Modify: `scripts/03_deep_dd.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Add official SEC metrics first**

Create `scripts/fundamental_metrics_store.py`.

Fetch from SEC companyfacts for mapped CIKs:
- revenue
- net income
- diluted EPS
- total assets
- total liabilities
- stockholders equity
- operating cash flow
- R&D expense
- share repurchases

Output:
- `reports/fundamentals/YYYY-MM-DD.json`

Rows:
```text
as_of_date
ticker
cik
period_end
fiscal_year
fiscal_period
form
filed_at
metric
label
value
unit
source
confidence
```

- [x] **Step 2: Add Eastmoney metrics as secondary source**

Add Eastmoney GMAININDICATOR only after SEC output exists.

Store:
- ROE
- ROA
- EPS
- gross margin
- asset-liability ratio

Rules:
- source must be `eastmoney_gmainindicator`
- confidence must be lower than SEC when both exist
- UI must show source conflict when SEC and Eastmoney disagree materially

- [x] **Step 3: Export `fundamental_metrics`**

Modify `scripts/analytics_store.py`:
- Add `FUNDAMENTAL_METRIC_COLUMNS`
- Add `fundamental_metrics` to `KNOWN_TABLES`
- Add `export_fundamental_metrics(reports_dir, analytics_root=None)`
- Add table to `refresh_all()`

Do not model a 200-column financial-statement table. Use long-form metric rows to avoid a wide sparse table.

- [x] **Step 4: Test metrics**

Run:
```bash
.venv/bin/python scripts/test_fundamental_metrics_store.py
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
fundamental metrics store tests passed
analytics store tests: all passed
```

## Phase 7: Industry Role And Theme Tag Analytics Export

**Files:**
- Modify: `scripts/industry_roles.py`
- Create: `scripts/test_industry_role_analytics.py`
- Modify: `scripts/analytics_store.py`
- Modify: `scripts/test_analytics_store.py`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Export approved and suggested role rows**

Modify `scripts/industry_roles.py` to write:
- `reports/industry_roles/YYYY-MM-DD.json`

Rows include:
```text
as_of_date
ticker
primary_role_id
primary_role_name
secondary_role_ids_json
status
confidence
source
evidence_json
reviewed_at
taxonomy_version
```

- [x] **Step 2: Add `industry_role_assignments` table**

Modify `scripts/analytics_store.py`:
- Add `INDUSTRY_ROLE_ASSIGNMENT_COLUMNS`
- Add `industry_role_assignments` to `KNOWN_TABLES`
- Add `export_industry_role_assignments(reports_dir, analytics_root=None)`
- Add table to `refresh_all()`

- [x] **Step 3: Test role export**

Run:
```bash
.venv/bin/python scripts/test_industry_role_analytics.py
.venv/bin/python scripts/test_analytics_store.py
```

Expected:
```text
industry role analytics tests passed
analytics store tests: all passed
```

## Phase 8: Operational Refresh, Data Quality, And UI Gates

**Files:**
- Modify: `scripts/run_candidate_pipeline.py`
- Modify: `scripts/analytics_checks.py`
- Modify: `scripts/test_analytics_checks.py`
- Modify: `docs/analytics-checks-automation.md`
- Modify: `docs/analytics-store-data-inventory.md`

- [x] **Step 1: Add refresh stages**

Modify `scripts/run_candidate_pipeline.py` so the daily data refresh runs in this order:
1. universe refresh
2. daily bars refresh
3. money flow refresh
4. IV/options snapshots
5. trade-state snapshot
6. analytics store refresh
7. analytics checks

- [x] **Step 2: Add data-quality gates**

Modify `scripts/analytics_checks.py` with checks:
- universe snapshot exists for current trading date or previous trading date
- daily bars latest date is not stale
- daily money flow coverage is at least 70% for requested tickers
- IV history row count is nonzero for watchlist option names
- trade-state snapshot includes role tag for every ticker row

- [x] **Step 3: Add UI warnings**

Update the checks output so UI can show:
- `DATA_SOURCE_STALE`
- `MONEY_FLOW_UNPUBLISHABLE`
- `QUOTE_FALLBACK_ACTIVE`
- `UNIVERSE_REFRESH_FAILED`
- `ROLE_TAG_MISSING`

- [x] **Step 4: Verify full pipeline**

Run:
```bash
.venv/bin/python scripts/test_global_stock_data.py
.venv/bin/python scripts/test_universe_refresh.py
.venv/bin/python scripts/test_daily_bars_store.py
.venv/bin/python scripts/test_eastmoney_money_flow.py
.venv/bin/python scripts/test_quote_fallback.py
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_analytics_store.py
.venv/bin/python scripts/test_analytics_checks.py
git diff --check
```

Expected:
```text
all tests passed
```

## Implementation Order And Commit Boundaries

1. Commit 1: provider adapter and tests.
2. Commit 2: universe refresh and analytics export.
3. Commit 3: daily bars store and analytics export.
4. Commit 4: Eastmoney money flow and UI evidence overlay.
5. Commit 5: quote fallback cache and UI source chips.
6. Commit 6: trade-state snapshot table.
7. Commit 7: SEC/Eastmoney fundamental metrics table.
8. Commit 8: industry-role analytics export.
9. Commit 9: pipeline scheduling and analytics data-quality gates.

## Risk Controls

- Do not call Eastmoney/Sina/Tencent endpoints directly from Streamlit render paths except cached quote fallback.
- Do not score with Eastmoney money flow until coverage and staleness checks pass.
- Do not store raw news content.
- Do not store all intraday quotes.
- Do not replace yfinance options with this source set.
- Do not treat Eastmoney money flow as institutional buying.
- Do not mix adjusted and unadjusted bars without `is_adjusted`.
- Do not create wide financial statement tables; use long-form `fundamental_metrics`.

## Acceptance Criteria

- Every ticker shown in core trading pages can resolve a security identifier row.
- Universe refresh can populate NASDAQ, NYSE, and US ETF/other rows.
- `daily_money_flow` has queryable history for candidate/watchlist/theme tickers and exposes coverage status.
- Trade-state snapshots preserve cycle, CE, verdict, role tag, and data-source provenance.
- Analytics DB refresh materializes all new tables without requiring live provider access.
- UI uses source chips and data-quality warnings when fallback or stale data is active.
- Existing yfinance-based options, IV, and candidate scoring behavior remains available when new providers fail.

## Self-Review

- Spec coverage: The plan covers phased data-source ingestion, DB persistence decisions, trading-page impact, refresh cadence, and risk controls.
- Placeholder scan: No task depends on an undefined future decision; optional all-expiry options-chain archival is intentionally excluded from phase 1.
- Type consistency: Table names and artifact paths are consistent across source-to-DB matrix, task files, and acceptance criteria.
