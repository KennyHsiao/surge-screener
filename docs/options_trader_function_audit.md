# Quant Radar 功能盤點與收斂藍圖

> 視角:美股期權波段交易者。範圍:目前工作區的 `audit-options-trader-function-map` 分支,依 `app.py` 實際導覽與 `.github/workflows/surge_screener.yml` 實際排程盤點。日期:2026-06-24。

## 1. 結論

這個專案現在不是單純的暴漲股篩選器,而是一套「機會發現 -> 單檔驗證 -> 期權結構決策 -> 持倉風控 -> 事後驗證」的唯讀交易決策系統。對美股期權波段交易者而言,核心應收斂成一條主流程:

1. **先判斷能不能出手**:大盤行情研判、COT、雷達的大盤/風險讀法。
2. **再找標的**:暴漲股篩選器、選擇權異常流、板塊/主題輪動。
3. **用個股總覽做單名研究樞紐**:交易面、期權面、板塊面、基本面、分析師、機構一次看完。
4. **用期權作戰台做最後交易決策**:GO/WAIT/AVOID、方向、IV、合約、損益圖、進場清單。
5. **用雷達與 IBKR 對帳管理持倉**:風險升高時先降曝險,反轉/蓄勢只當探索性 watchlist。
6. **用復盤與知識網路調整系統,不是當日下單**:它們是研究與權重校準工具。

目前最大問題不是資料不夠,而是**主導覽同時混了交易、研究、系統維護、探索性骨架**,讓使用者每天必須自己判斷哪些頁面該看、哪些只是背景。建議先做主流程收斂,不要先刪管線。

## 2. 當前頁面地圖

`app.py` 目前註冊 **24 個入口**:今日決策 7、市場背景 5、研究驗證 5、資料維護 4、幣圈 3。導覽已依本文件的主流程收斂落地,不再使用舊的「美股 / 幣圈 / 系統」三群組。

| 群組 | 頁面 | 目前定位 | 對期權波段交易者的等級 |
|---|---|---|---|
| 今日決策 | 今日決策 | 市場閘門、候選、異常流、風控、驗證的聚合首頁 | 核心每日 |
| 今日決策 | 暴漲股篩選器 | 每日候選來源、DEoT 管線總覽 | 核心每日 |
| 今日決策 | 選擇權異常流 | EOD 期權量異常排行 | 核心發現 |
| 今日決策 | 個股總覽 | 單名研究樞紐,嵌多個子視圖 | 核心樞紐 |
| 今日決策 | 期權作戰台 | 單名期權交易決策座艙 | 核心每日 |
| 今日決策 | 雷達 (風險＋反轉) | 風險、反轉、蓄勢三讀 | 核心風控,部分探索 |
| 今日決策 | IBKR 對帳 | Screener vs 真實持倉、風險速覽 | 持倉風控 |
| 市場背景 | 熱錢板塊輪動 | 板塊 RRG、候選所在板塊 | 每週/背景 |
| 市場背景 | 主題資金流 | 窄主題價量 proxy + Form-4 overlay | 每週/背景 |
| 市場背景 | COT / ES 週報 | 每週慢錢籌碼背景 | 每週/背景 |
| 市場背景 | 大盤行情研判 | Tier-1 大盤方向與 forward 驗證 | 背景,探索 |
| 市場背景 | X 社群情緒 | 單帳號/關鍵字 + 博主雷達 | 事件/情緒輔助 |
| 研究驗證 | 復盤分析 | 因子與模組 lift 驗證 | 研究/調權重 |
| 研究驗證 | 知識網路 | 因子、維度、文獻關係圖 | 研究/治理 |
| 研究驗證 | 期權分析 | 期權鏈微結構與 IV 細節 | 交易前確認 |
| 研究驗證 | 分析師評級 | 賣方共識、目標價、修正 | 輔助確認 |
| 研究驗證 | 機構面板 | 股票持有人與 13F 大戶持倉 | 研究輔助 |
| 資料維護 | 自選股分類 | TV/IBKR 清單分類 | 資料維護 |
| 資料維護 | 關注博主 | X roster 管理 | 系統維護 |
| 資料維護 | 排程與結果 | 排程與最近產物檢查 | 系統維護 |
| 資料維護 | AI 重點更新 | 手動內容 feed | 系統/內容 |
| 幣圈 | 幣種清單 | Binance USDT 永續清單與增減 | 非美股核心 |
| 幣圈 | 幣圈篩選 | 骨架,上游未接完整評分 | 可隱藏/實驗 |
| 幣圈 | X 社群情緒 | 幣圈版 X 分析 | 非美股核心 |
| 系統 | 關注博主 | X roster 管理 | 系統維護 |
| 系統 | 排程與結果 | 排程 registry 與最近產物 | 系統維護 |
| 系統 | AI 重點更新 | 手動維護 feed | 系統/內容 |

## 3. 建議使用順序

### 3.1 每日收盤後到隔日開盤前

1. **大盤閘門**:先看大盤行情研判、COT/ES 週報與雷達的大盤風險。若 VIX、SPY 位置、COT 或市場 thesis 顯示風險升高,當天所有候選只降級為觀察。
2. **候選來源**:看暴漲股篩選器的 confirmed/watchlist,再看選擇權異常流 top names。這兩頁是主要 alpha 入口。
3. **板塊與主題確認**:用熱錢板塊輪動和主題資金流判斷候選是否站在市場正在買的地方。這一步只做加分/扣分,不單獨產生交易。
4. **單名研究**:把候選送到個股總覽。先看因子體檢、期權作戰台嵌入、期權分析嵌入,再看基本面/分析師/機構。
5. **交易決策**:只在期權作戰台做最後決策。GO 才考慮下單;WAIT 進 watchlist;AVOID 不交易。
6. **風險掃描**:若已有持倉或準備加碼,看雷達與 IBKR 對帳。REDUCE/EXIT 優先於任何新進場訊號。

### 3.2 每週

1. COT / ES 週報:判斷慢錢籌碼與指數背景。
2. 熱錢板塊輪動、主題資金流:更新本週主線。
3. 大盤行情研判:只讀為探索性 forecast,不要把未成熟 hit-rate 當準確率。
4. 自選股分類:整理 TradingView、IBKR、手動 watchlist。

### 3.3 每月或策略調整時

1. 復盤分析:看哪些因子/模組有 lift、哪些是 noise/contrarian。
2. 知識網路:追溯某個因子背後的維度、文獻與驗證狀態。
3. 月度 self-reflection 與 performance ledger:決定是否調整 prompt、權重、硬濾網。

## 4. 功能與模組對照

### 4.1 機會發現

| 功能 | UI | 主要 scripts | 主要 artifacts | 使用時機 | 收斂判斷 |
|---|---|---|---|---|---|
| 暴漲股篩選 | `ui/us_screener.py` | `01_hard_filter.py`, `03_rank_candidates.py`, `02_llm_score.py`, `025_engine_controller.py`, `03_deep_dd.py`, `04_build_report.py` | `filtered_universe.json`, `ranked_candidates.json`, `scored_candidates.json`, `layer2_results.json`, `dd_results.json`, `reports/YYYY-MM-DD/summary.json` | 每日 EOD 找方向性候選 | 保留為主入口 |
| 選擇權異常流 | `ui/options_flow.py` | `options_flow_scan.py`, `options_free.py` | `reports/options_flow/latest.json`, dated JSON | 找期權量異常與高 V/OI 標的 | 保留為第二候選來源 |
| 板塊輪動 | `ui/sector_rotation.py` | `sector_flow.py`, `sector_rotation.py` | live cache, `reports/sector_rotation.json` 若存在 | 確認候選是否在 hot/improving sector | 保留,但放背景/每週 |
| 主題資金流 | `ui/theme_flow.py` | `theme_flow.py`, `theme_rotation.py`, `insider_edgar.py` | `content/theme_baskets.json`, `reports/theme_flow.json` | 確認窄主題與內部人 overlay | 保留,但不得接評分直到驗證完成 |
| X 社群情緒 / Free-first social intelligence | `ui/x_sentiment.py` | `social_intelligence.py`, `sentiment_free.py`, `x_analysis.py`, `x_influencers.py`, `social_intelligence_outcomes.py` | `reports/social_intelligence/latest.json`, `reports/social_intelligence/YYYY-MM-DD.json`, `reports/social_intelligence_outcomes/YYYY-MM-DD.json`, `reports/x_influencer_picks.json`, runtime influencer roster seeded from `content/influencers.json` | 社群發現 tickers + StockTwits/ApeWisdom 免費熱度基線 + 平台驗證 + 後續成效追蹤 | 輔助; Agent Reach 可跑免費本機 discovery，博主 LLM 研究走 Codex ChatGPT 訂閱，X API 是 paid optional |

### 4.2 單名驗證與期權決策

| 功能 | UI | 主要 scripts | 主要 artifacts | 使用時機 | 收斂判斷 |
|---|---|---|---|---|---|
| 個股總覽 | `ui/stock_checkup.py` | `live_factors.py`, `fundamentals_free.py`, `fundamentals_read.py`, plus embedded views | `reports/retrospective/factor_lift.json`, on-demand fundamentals | 單名研究樞紐 | 保留並升為核心入口 |
| 期權作戰台 | `ui/options_cockpit.py` | `momentum_options.py`, `options_free.py`, `options_analytics.py`, `iv_history.py` | `reports/iv_history/*.json`, `scored_candidates.json`, `reports/options_flow/latest.json` | 最後 GO/WAIT/AVOID 與合約選擇 | 保留為期權主頁 |
| 期權分析 | `ui/us_options.py` | `options_free.py`, `options_analytics.py`, `iv_history.py` | `reports/iv_history/*.json`, `scored_candidates.json` | 需要看鏈分佈、V/OI、GEX proxy、微笑/期限結構時 | 保留獨立明細頁,但主流程由作戰台進入 |
| 分析師評級 | `ui/analyst_views.py` | `analyst_free.py` | yfinance cache, `scored_candidates.json` | 檢查共識與 EPS 修正是否支撐 | 降級為輔助,個股總覽已可滿足主要需求 |
| 機構面板 | `ui/institutions.py`, `institutional_holdings.py`, `institution_portfolio.py` | `institutional_free.py`, `edgar_13f.py` | `content/funds.json`, yfinance/EDGAR cache | 看股票誰持有、基金持倉 | 降級為研究,不放每日流程 |

### 4.3 風控與持倉

| 功能 | UI | 主要 scripts | 主要 artifacts | 使用時機 | 收斂判斷 |
|---|---|---|---|---|---|
| 雷達 | `ui/radar.py`, embedded `ui/risk_guard.py`, `ui/oversold_reversal_lane.py` | `risk_guard.py`, `reversal_radar.py`, `reversal_radar_scan.py`, `oversold_reversal_scan.py` | `reports/reversal_radar/latest.json`, `reports/oversold_reversal/latest.json`, `reports/reconciliation.json` | 持倉風險、下跌後反轉、安靜蓄勢 | 保留,但反轉/蓄勢明確標探索 |
| IBKR 對帳 | `ui/ibkr_reconcile.py` | `ibkr_client.py`, reuse radar/risk_guard | `reports/reconciliation.json` | 真實持倉 vs 系統候選,持倉風險速覽 | 保留為持倉頁 |
| 自選股分類 | `ui/watchlist_categorize.py` | `sector_free.py`, `theme_classify.py`, `ibkr_client.py` | `content/us_watchlist.txt`, `content/themes.json`, `reports/watchlist.json` | 管理觀察清單、分類匯出 | 移到系統/維護區更合理 |

### 4.4 研究、驗證、治理

| 功能 | UI | 主要 scripts | 主要 artifacts | 使用時機 | 收斂判斷 |
|---|---|---|---|---|---|
| 復盤分析 | `ui/retro_analysis.py` | `retro_surge_label.py`, `retro_reconstruct.py`, `retro_edgar_backfill.py`, `retro_factor_lift.py`, `retro_modules.py`, `retro_report.py`, `retro_forward_lift.py` | `reports/retrospective/**` | 每月檢查因子與模組有效性 | 保留,但不可放每日交易決策 |
| 知識網路 | `ui/knowledge_graph.py` | `knowledge_graph.py`, `knowledge_sync.py`, `knowledge_runway_sync.py`, `knowledge_seed.py` | `knowledge/**` | 看因子、維度、文獻、驗證狀態關係 | 保留為研究治理 |
| 大盤行情研判 | `ui/market_thesis.py` | `market_thesis.py`, `market_thesis_forward.py`, `market_events.py`, `market_thesis_contract.py` | `reports/market_thesis/**`, `content/fomc_calendar.json` | 每週大盤方向背景 | 保留,但標探索/未成熟 |
| COT / ES 週報 | `ui/us_cot.py` | `cot_es.py` | `reports/cot/*.md`, `*.verified.json` | 每週慢錢籌碼背景 | 保留為背景 |
| 排程與結果 | `ui/sys_schedules.py` | reads content/report files | `content/schedules.json`, reports folders | 確認 pipeline 是否有產物 | 系統維護 |
| 關注博主 | `ui/influencers.py` | none directly; feeds `x_influencers.py` | runtime influencer roster seeded from `content/influencers.json` | 維護 X roster | 系統維護 |
| AI 重點更新 | `ui/sys_ai_updates.py` | none | `content/ai_updates.json` | 手動內容 feed | 可留系統區,不進交易流程 |

### 4.5 非美股核心

| 功能 | UI | 主要 scripts | 主要 artifacts | 使用時機 | 收斂判斷 |
|---|---|---|---|---|---|
| 幣種清單 | `ui/crypto_universe.py` | `crypto_universe.py` | `reports/crypto/universe_latest.json`, TV watchlist | 幣圈 watchlist 維護 | 非美股期權核心,保留在幣圈 |
| 幣圈篩選 | `ui/crypto_screener.py` | 尚未接完整 pipeline | future `crypto_scored.json` | 目前只是計畫骨架 | 建議隱藏或標實驗 |
| 幣圈 X 情緒 | `ui/x_sentiment.py` with `CRYPTO` | `x_analysis.py`, `x_influencers.py` | runtime influencer roster seeded from `content/influencers.json` | 幣圈情緒 | 非美股核心 |

## 5. 排程與資料流

| Job | Cron / manual job | 目的 | 主要產物 | 對交易流程的角色 |
|---|---|---|---|---|
| `surge_scan` | weekday 22:30 UTC / `screener` | 全套暴漲股篩選與通知 | `filtered_universe.json`, `scored_candidates.json`, reports/date, ledger, IV snapshots | 每日候選主來源 |
| `candidates-local` | manual local / Makefile | 本機 hard filter + deterministic rank,預設不跑 LLM | `filtered_universe.json`, `ranked_candidates.json` | 快速補首頁候選;不等同 Layer 2/3 盡調完成 |
| `candidates-rank-local` | manual local / Makefile | 只重排既有 hard-filter 結果 | `ranked_candidates.json` | 已有 `filtered_universe.json` 時快速刷新 top 30-50 |
| `candidates-score-local` | manual local / Makefile | 可選 Codex SDK deep check 少量 ranked candidates | `scored_candidates.json` | 補敘事/催化/風險摘要,不再作為主排序瓶頸 |
| `verify_returns` | weekday 13:00 UTC | 回填已發佈 picks 的 forward returns | `reports/performance_ledger.csv` | 事後驗證 |
| `monthly_reflection` | monthly day 1 | 月度自我審計 | `reports/reflections/YYYY-MM.md` | prompt/策略調整 |
| `monthly_retrospective` | monthly day 15 | 歷史復盤、PIT 資料集、知識同步 | `reports/retrospective/**`, `knowledge/**` | 因子驗證與治理 |
| `crypto_universe` | daily 00:30 UTC / `crypto` | Binance USDT 永續清單 | `reports/crypto/**` | 非美股核心 |
| `cot_es` | Friday 23:00 UTC / `cot` | COT/ES 週報 | `reports/cot/**` | 每週背景 |
| `options_flow_scan` | weekday 22:00 UTC / `options_flow` | EOD 異常期權量掃描 | `reports/options_flow/**` | 候選來源 |
| `reversal_radar` | weekday 22:45 UTC / `reversal` | beaten-down 反轉掃描與 forward | `reports/reversal_radar/**` | 探索性反轉 watchlist |
| `oversold_lane` | weekday 23:15 UTC / `oversold_lane` | 壓縮基底 lane 與 forward EV | `reports/oversold_reversal/**` | 探索性蓄勢 watchlist |
| `market_thesis` | Monday 23:00 UTC / `market_thesis` | 大盤方向與 forward scoring | `reports/market_thesis/**` | 每週背景,探索性 |

## 6. 哪些好用、哪些多餘

### 6.1 好用且應放在前面

1. **期權作戰台**:最貼近交易者下單前問題。只要資料可用,它回答「可不可以做、做什麼方向、買哪種合約、風險多少」。
2. **暴漲股篩選器**:候選生成主引擎,且有 Layer 0-3 的透明度。
3. **選擇權異常流**:對期權交易者特別有價值,因為它不是一般股票篩選器能看到的 flow/volume 異常。
4. **個股總覽**:正確定位應是樞紐,不是又一個獨立分析頁。它減少來回切頁。
5. **雷達 + IBKR 對帳**:風控要高於新進場訊號。這兩頁應接在作戰台之後。

### 6.2 有用但不該打擾每日決策

1. **分析師評級**:可確認估值與修正方向,但對 1-8 週期權波段不是第一優先。放在個股總覽或研究區即可。
2. **機構面板**:13F 有延遲,更適合研究背景,不是短期進出依據。
3. **COT / ES 週報**:有用,但頻率是週級,不該每日反覆檢查。
4. **復盤分析 / 知識網路**:用來校準系統,不是拿來直接決定今天買哪張 call。
5. **大盤行情研判**:保留,但目前仍是探索性,不應呈現成高信心 forecast。

### 6.3 目前多餘或應降級

1. **幣圈篩選**:目前是骨架。若主產品是美股期權,它應移到實驗/幣圈區,甚至可從預設導覽隱藏。
2. **AI 重點更新**:是內容 feed,不是交易模組。保留在系統區即可。
3. **自選股分類**:是資料維護功能。交易者每日流程只需要結果,不用每天看分類工具。
4. **獨立分析師/機構頁**:功能本身有用,但主需求已可在個股總覽滿足。獨立頁可留給深查,不應排在主交易路徑中段。

## 7. 建議導覽收斂

### 7.1 已落地主導覽

主流程已改成:

1. **今日決策**
   - 大盤/風險總覽
   - 暴漲股篩選器
   - 選擇權異常流
   - 個股總覽
   - 期權作戰台
   - IBKR 對帳
2. **市場背景**
   - 熱錢板塊輪動
   - 主題資金流
   - COT / ES 週報
   - 大盤行情研判
   - X 社群情緒
3. **研究驗證**
   - 復盤分析
   - 知識網路
   - 分析師評級
   - 機構面板
4. **資料維護**
   - 自選股分類
   - 關注博主
   - 排程與結果
   - AI 重點更新
5. **幣圈**
   - 幣種清單
   - 幣圈篩選(實驗)
   - X 社群情緒

### 7.2 如果要真正減頁

| 建議 | 原需求如何被滿足 | 風險 |
|---|---|---|
| 隱藏 `幣圈篩選` 預設入口 | 幣圈資料仍可從 `幣種清單` 與幣圈 X 看;等 `crypto_scored.json` 上線再恢復 | 低 |
| 將 `分析師評級` 降為個股總覽內的深查入口 | `個股總覽` 已嵌分析師資料;獨立頁保留給批量排行 | 低 |
| 將 `機構面板` 降為個股總覽內的深查入口 | `個股總覽` 已嵌股票->機構;獨立頁保留給 13F 大戶反查 | 中 |
| 將 `自選股分類` 移到系統/資料維護 | 交易流程不受影響;watchlist 仍餵雷達與作戰台 | 低 |
| 保留 `期權分析` 獨立頁,但主路徑從作戰台/個股總覽進入 | 作戰台提供決策,期權分析提供鏈微結構;不破壞既有 roadmap | 低 |

不建議現在刪 `期權分析`:`docs/options_cockpit_roadmap.md` 已鎖定它是鏈微結構明細頁,不是作戰台的重複品。也不建議合併 reversal/oversold 後端,因為它們各自有 forward 驗證統計,合併會污染樣本。

## 8. 擴充優先級

### P1: 先把主流程變短（已落地）

1. 做一個「今日決策」首頁或 tab,聚合:
   - 大盤 regime / market thesis 狀態
   - screener top picks
   - options flow top picks
   - radar REDUCE/EXIT
   - IBKR 持倉警示
2. 導覽重分組,把研究與系統頁移出主交易路徑。
3. 所有候選表統一提供三個動作:個股總覽、期權作戰台、雷達。

落地狀態（2026-06-24）:`ui/today_decision.py` 已成為預設首頁,`app.py` 已重排為「今日決策 / 市場背景 / 研究驗證 / 資料維護 / 幣圈」,候選表跳轉已收斂到 `_shared.ticker_action_buttons()` 的三動作。

補資料入口（2026-07-30）:`make candidates-local` 使用 hard filter + deterministic rank,輸出 `filtered_universe.json` 與 `ranked_candidates.json`,預設不呼叫 LLM。`make candidates-score-local` 明確用 Codex SDK / ChatGPT 訂閱額度,對 ranked pool 做少量 deep check；可用 `CANDIDATE_MODEL` 覆寫帳號預設模型。今日決策頁提供本機篩選控制台,可調 `RANK_LIMIT`、`OPTIONS_GATE_LIMIT` 與 hard-filter 門檻,並讀 `candidates-local-history.jsonl` 顯示每次篩選紀錄。Layer 2/3 仍需另外跑 `025_engine_controller.py` / `03_deep_dd.py` / `04_build_report.py`。

### P2: 把探索性訊號的信任邊界做清楚（進行中）

1. 反轉、壓縮基底、大盤行情研判全部顯示成熟度:sample count、forward N、是否 actionable。
2. 主流程只允許 validated 或 risk-control 訊號改變交易狀態;exploratory 只能進 watchlist。
3. 復盤/知識網路同步顯示 factor status,避免使用者把 seed/noise 因子當成交易依據。

落地狀態（2026-06-24）:今日決策首頁已新增「信任邊界」段落,讀取 `reports/market_thesis/validation_summary.json`、`reports/reversal_radar/validation_summary.json`、`reports/oversold_reversal/validation_summary.json`,直接顯示成熟度與 `背景-only` / `觀察-only`。P2 尚未完成的部分是復盤與知識網路的 factor status 同步。

### P3: 減少維護面

1. 對同一 ticker 的 live yfinance 抓取統一走 `scripts/_yfinance.py` 或現有 cache 層,優先處理 SPY/VIX/sector 重複抓取。
2. 把 content 管理頁集中在系統區,不要和交易頁混排。
3. 對骨架頁加 feature flag 或「實驗」標記,避免使用者以為已可用。

## 9. 交易者判讀規則

1. **作戰台 AVOID > 所有 bullish 訊號**:如果 IV、財報、流動性或 regime 不合格,不要用篩選器分數硬做。
2. **風控頁 REDUCE/EXIT > 新進場**:持倉風險升高時,先處理曝險。
3. **異常流只證明有人交易,不證明方向正確**:必須搭配技術、IV、成交價差與事件風險。
4. **分析師/機構是確認,不是觸發**:它們有延遲或偏慢,不要取代價格與期權鏈。
5. **探索性頁面只產生問題,不產生答案**:反轉、蓄勢、大盤 thesis 未成熟前,應該問「值得追蹤嗎」,不是「應該買嗎」。

## 10. 下一步實作建議

如果要從這份盤點繼續改版,建議接續兩個小 PR:

1. **P2 factor status PR**:在復盤分析與知識網路同步顯示 factor status,把 seed/noise/blocked 因子明確阻止成交易依據。
2. **P3 維護面 PR**:收斂 yfinance/cache 與骨架頁 feature flag,減少資料維護與交易流程混排。

這樣可以在已完成的 P1 主流程上,繼續提高交易者對訊號成熟度與可行動性的判讀品質。

## 11. Forward sample 成熟規則

Forward sample 不是把歷史資料手動塞進去就算成熟。成熟需要三件事同時成立:每天或每週先產生鎖定快照、等待指定 forward window 走完、再由 forward harness 用真實後續價格結算。人工補一筆或改 JSON 不能手動補成熟,只會製造假信心。

| 模組 | 快照來源 | 成熟窗口 | 正式門檻 | 目前狀態 | 合理判讀 |
|---|---|---|---|---|---|
| 反轉雷達 | `reports/reversal_radar/scan_*.json` | `+10%/20d`, `+15%/40d`, `+20%/60d` | `MIN_RESOLVED=100` per tier,以 `min_resolved_across_tiers` 判定 | 976 entries,但 min resolved 0/100 | 只能觀察,不可交易化 |
| 壓縮基底 | `reports/oversold_reversal/scan_*.json` | `+30%/20d`, `+40%/40d`, `+50%/60d` | `MIN_RESOLVED=100` per tier,以 `min_resolved_across_tiers` 判定 | 876 entries,但 min resolved 0/100;PIT membership 多數 unknown | 只能觀察,且需補 PIT membership |
| 大盤 thesis | `reports/market_thesis/*forecast_*.json` | short/mid/long = 20/40/60 sessions | `MIN_RESOLVED=100` 且按 `(direction,bucket,support_class)` 非重疊計數 | resolved 1,matured 0/100 | 背景-only,不可發警報 |

時間估算要用「可結算筆數」而不是 raw entries。反轉/壓縮基底如果每日穩定產生新快照,第一批 20d tier 約 1 個月後開始結算,40d 約 2 個月,60d 約 3 個月;要達 100 resolved/tier,在每日有足夠候選且資料不掉線的情況下,通常至少 3 個月以上才可能看到 60d tier 成熟。大盤 thesis 是每週且非重疊計數,目前門檻非常保守;若維持 `MIN_RESOLVED=100` 和 20/40/60 session 非重疊算法,成熟會是多年尺度,短期只能當背景。
