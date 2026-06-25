# Candidate Ranking Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 將候選股流程改成「程式先篩、程式先排、LLM 只做少量深查」，避免 800+ 檔逐檔 LLM 評分造成 timeout 與成本浪費。

**Architecture:** 保留既有 hard filter 作為第一層粗篩，新增 deterministic ranker 產生 `rank_score 0-100` 與 top 30-50 candidate pool。LLM scoring 改為可選深查，只處理 ranked pool 中少量標的，不再是主要排序來源。

**Tech Stack:** Python scripts, yfinance/free options data, existing JSON artifacts, Makefile, Streamlit UI status file.

---

## Summary

`make candidates-local` 改為：

1. `scripts/01_hard_filter.py`: 市場/流動性/基本風險粗篩。
2. `scripts/03_rank_candidates.py`: 程式計算 `rank_score`。
3. 輸出 `ranked_candidates.json`: 預設 top 50。
4. `OPTIONS_GATE_LIMIT > 0` 時，對 top N 做 free options tradability gate。
5. `make candidates-score-local` 才做 optional LLM deep check。

---

## Key Changes

- [x] 新增 deterministic ranker，輸入 `filtered_universe.json`，輸出 `ranked_candidates.json`。
- [x] `rank_score 0-100` 權重：技術趨勢 25、動能強度 20、啟動訊號 20、流動性/可交易性 20、過熱風險控制 15。
- [x] Top 50 = candidate pool，Top 30 = 優先人工/期權檢查池，Top 10-20 = optional LLM deep check。
- [x] 新增可選 options gate，標記 `usable` / `watch` / `unusable` / `unknown`。
- [x] `make candidates-local` 預設不跑 LLM；新增 `make candidates-rank-local`；保留 `make candidates-score-local`。
- [x] 今日決策頁優先顯示 `ranked_candidates.json`，舊 `scored_candidates.json` 保留為 fallback。

---

## Test Plan

- [x] `scripts/test_rank_candidates.py`
- [x] `scripts/test_run_status.py`
- [x] `scripts/test_dashboard_navigation.py`
- [x] `scripts/test_hard_filter_yfinance.py`
- [x] `make test`

---

## Assumptions

- 第一版 ranker 先取代大量 LLM 排序瓶頸，不宣稱是最終 alpha model。
- LLM 不再負責主排序，只負責少量 deep check、風險解釋、催化摘要。
- Free options data 無法完整判斷 sweeps、blocks、dark pool、bid/ask side，缺口會寫進 `data_missing`。
- Retrospective factor/module lift 先作為後續優化討論，不直接併入 v1 rank score。
