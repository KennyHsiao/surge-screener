# 美股暴漲股 AI Agent — Master Overview (v3.2)

> 一頁看完整套系統。詳細內容看各別檔案。  
> 最後更新:v3.2(自我驗證 + 歷史案例學習)  
> 📌 全系統功能地圖 / 資料流 / 優化路線圖:[docs/system_panorama.md](docs/system_panorama.md)
> 🎯 美股期權波段交易者的使用順序 / 功能模組對照 / 收斂藍圖:[docs/options_trader_function_audit.md](docs/options_trader_function_audit.md)

---

## 七份檔案 — 一句話說清楚每個檔案的職責

| # | 檔案 | 一句話用途 | Layer |
|---|---|---|---|
| **00** | `README.md` | 部署 checklist、架構圖、成本、警告 | — |
| **01** | `surge_screener_prompt.md` | 每日 regime 檢查 + 6 維度初評打分 | 0 + 1 |
| **04** | `engine_controller_prompt.md` | 為每檔候選決定 BREADTH / DEPTH / TERMINATE | 2 |
| **02** | `dexter_due_diligence_skill.md` | SEC 10-Q/8-K + Form 4 + UW flow + 做空論證 | 3 |
| **05** | `self_reflection_skill.md` | **每月自我審計勝率,挑出系統錯在哪**(NEW v3.2) | 5 |
| **06** | `historical_case_library.md` | **餵 LLM 看歷史暴漲股長什麼樣**(NEW v3.2) | Few-shot |
| **03** | `github_actions_workflow.yml` | 三組 cron:每日篩選 / 每日驗證 / 每月反思 | 全層 |

---

## 自我進化迴路 (v3.2 NEW)

```
每日 EOD 篩選 ──────► 推薦 top 5 ──────► 寫入 ledger (含完整訊號快照)
       ▲                                          │
       │                                          ▼
       │                                Forward returns 累積
       │                                  (3d/7d/14d/30d/60d)
       │                                          │
       │                                          ▼
       │                                     Hit/Miss 標記
       │                                          │
       │                                          ▼
       │                            ┌──────────────────────────┐
       │                            │ 每月 1 號 Self-Reflection │
       │                            │ • 計算各維度預測力相關度    │
       │                            │ • 識別 false positive 模式 │
       │                            │ • 識別 false negative 模式 │
       │                            │ • 提出 prompt 調整建議      │
       │                            │ • 把成功 case 加進案例庫    │
       │                            └──────────┬───────────────┘
       │                                       │
       │                                       ▼
       │                          推送月報告到 Telegram
       │                                       │
       │                                       ▼
       │                     **人類** review 建議,決定是否套用
       │                                       │
       └───── 套用後 prompt 更新 ◄─────────────┘
```

**為什麼建議是給人類 review,不自動套用?**

DEoT 論文中的 Plan Validation 三層檢查思想,這裡也適用 — 自動套用 = prompt drift 風險。LLM 容易在小樣本上過擬合:看到上個月 sentiment 沒效果就說「砍掉 sentiment」,但其實只是那個月剛好是事件驅動行情。讓人類做最後 gatekeeper,系統才不會慢慢走歪。

```
17:30 ET cron → GitHub Actions 啟動
        │
        ▼
  ┌─────────────────────────────────────────────────┐
  │ LAYER 0 — Base Prompter(每日跑 1 次)            │
  │   檔案: 01_surge_screener_prompt.md             │
  │   產出: regime_context (含 global_multiplier)   │
  │   • SPY vs 50/200 DMA                          │
  │   • VIX 區間                                    │
  │   • 全域分數乘數 0.5 ~ 1.0                      │
  │   • 當日 active themes                          │
  └─────────────┬───────────────────────────────────┘
                ▼
  ┌─────────────────────────────────────────────────┐
  │ STAGE 1 — Hard Filter (Python 跑,非 LLM)       │
  │   7 條規則,通常 3000 → 400 檔                   │
  │   • 已漲多 / 流動性 / 雞蛋水餃 / 法說前 / 趨勢   │
  │   • 跳空下殺 / MACD 零軸風險(NEW v3.1)         │
  └─────────────┬───────────────────────────────────┘
                ▼
  ┌─────────────────────────────────────────────────┐
  │ LAYER 1 — Breadth Pass(每檔候選跑 1 次)        │
  │   檔案: 01_surge_screener_prompt.md             │
  │   6 維度 100 分制 × global_multiplier            │
  │   通常 400 → ~30 檔(≥65 分)                    │
  └─────────────┬───────────────────────────────────┘
                ▼
  ┌─────────────────────────────────────────────────┐
  │ LAYER 2 — Engine Controller(每檔可跑 1-2 次)   │
  │   檔案: 04_engine_controller_prompt.md          │
  │   依訊號分布動態路由:                           │
  │   • 集中 → DEPTH(專攻最強維度,1-2 題)         │
  │   • 分散 → BREADTH(找隱藏故事,2-3 題)         │
  │   • 矛盾 → BREADTH(釐清誰對)                  │
  │   • 弱   → TERMINATE                           │
  │   ERIR 監控,沒新訊息就停                        │
  │   單檔最多 2 層、6 節點                          │
  │   通常 30 → ~10 檔                              │
  └─────────────┬───────────────────────────────────┘
                ▼
  ┌─────────────────────────────────────────────────┐
  │ LAYER 3 — Dexter Due Diligence(US only)       │
  │   檔案: 02_dexter_due_diligence_skill.md        │
  │   • SEC 10-Q / 8-K 閱讀                        │
  │   • Form 4 內部人 + 13F 機構動向                │
  │   • X 社群品質與真實性                          │
  │   • Unusual Whales flow 反向驗證                │
  │   • 做空論證壓測 (mandatory)                    │
  │   通常 10 → ~5 檔 CONFIRMED                    │
  └─────────────┬───────────────────────────────────┘
                ▼
  ┌─────────────────────────────────────────────────┐
  │ LAYER 4 — Final Response Agent                 │
  │   合併 Layer 0~3 所有節點                       │
  │   產出最終排名 + 推理樹 + 進場區/停損/倉位      │
  └─────────────┬───────────────────────────────────┘
                ▼
        Telegram 推送 + commit reports/ to repo
```

---

## 100 分評分結構(v3.1 確認版)

| 維度 | 分數 | 子項 |
|---|---|---|
| **1. 技術** | **30** | 1a Trend Template 10 + 1b Volume 8 + 1c Pattern(續勢/反轉)9 + 1d MACD MTF 3 |
| **2. 催化** | **20** | 2a 8-K 重大事件 8 + 2b 財報動能 8 + 2c 分析師 4 |
| **3. 情緒** | **15** | 3a X 聲量 8 + 3b Reddit/ST 4 + 3c 智錢 3 |
| **4. 籌碼** | **10** | 4a 13F 4 + 4b Form 4 4 + 4c 軋空潛力 2 |
| **5. 板塊** | **5** | 5a Sector RS 3 + 5b Market Regime 2 |
| **6. 選擇權** | **20** | 6a UOA 8 + 6b Sweeps 6 + 6c 暗池 3 + 6d GEX 3 |
| **合計** | **100** | × global_multiplier (0.5–1.0,熊市自動降權) |

**Hard Filters (6 條,任一觸發即 reject):**
1. 已漲多(5 日 >30% 或 20 日 >60%)
2. 流動性(20 日均額 < $5M)
3. 雞蛋水餃(市值 < $300M 或股價 < $5)
4. 法說會 2 天內
5. 跌破 200DMA(除非有反轉型態 + 背離)
6. **MACD 零軸下無交叉、無背離(v3.1 新增)**

**Risk Warnings (保留候選,但扣分/標示):**
- 5 日內收盤跌破前日低點 >8%: 技術風險警告,不單獨作為 hard reject

---

## 必備 API Key 清單

| Key | 用途 | 月費 | 必需? |
|---|---|---|---|
| Codex ChatGPT 登入 | 全平台 LLM(Codex SDK)| 已含在 ChatGPT 方案,受額度限制 | ✅ |
| `POLYGON_API_KEY` | 美股價量 + 財報 + 新聞 | $29 | ✅ |
| `UNUSUAL_WHALES_API_KEY` | 選擇權 flow + 暗池 + GEX | $29–99 | ✅(Dim 6 命脈)|
| `SEC_EDGAR_USER_AGENT` | SEC 文件閱讀(放 email) | 免費 | ✅ |
| `X_BEARER_TOKEN` | 社群情緒 | $200 / 免費 tier | ⚠️ 可後加 |
| `FINNHUB_API_KEY` | Polygon 備援(8-K 推送)| 免費 tier | ❌ |
| `EXA_API_KEY` | Dexter web search | 免費 tier 夠 | ❌ |
| `TELEGRAM_BOT_TOKEN` + `CHAT_ID` | 推播 | 免費 | ✅ |

---

## 每月成本(v3.2,真實估算)

> v3.2 新增的 verify_returns 是純 Python(免費),self-reflection 每月只跑 1 次(成本可忽略)。**v3.2 對 v3.1 的成本增量幾乎為零**。

### 標配方案(推薦,品質最佳)

| 項目 | 月費 | 備註 |
|---|---|---|
| GitHub Actions | **$0** | 三組 cron 都在免費額度內 |
| Codex SDK / ChatGPT 訂閱(LLM) | **依既有 ChatGPT 方案** | EOD 篩選 + 月度反思,受訂閱額度限制 |
| Polygon Stocks Starter | **$29** | 含價量 + 財報 + 新聞 + verify_returns 用 |
| Unusual Whales(零售方案) | **$29–99** | $29 入門夠用 |
| SEC EDGAR | $0 | 免費 |
| Telegram | $0 | 免費 |
| **小計(無 X API)** | **$103–250** | 一般使用約 $150 |
| X API Basic(可選) | $200 | Dim 3a 進階用,初期可用免費 tier |
| **完整方案合計** | **$303–450** | |

### 訂閱額度控制

大量 breadth scan 會快速消耗 ChatGPT 訂閱額度;請保留候選上限、分批
resume 與 Engine Controller 的 TERMINATE 機制。系統不再提供 DeepSeek、
Anthropic 或 OpenAI API-key 備援,避免無意間產生額外 LLM 帳單。

### 為什麼 v3 比 v2 多 30–50% LLM 成本?

因為加了 Layer 2 動態深度分析,每檔候選平均多 1–2 次 LLM 呼叫。但 Engine Controller 的 ERIR 機制會主動 TERMINATE 弱訊號,所以實際增量不到 50%。**這是值得的成本** — 讓你錢花在強訊號候選上,而不是平均浪費在所有候選身上。

### 一個重要觀念:**現在系統會自己告訴你它賺不賺錢**

v3.2 之前,你需要自己拉 spreadsheet 算勝率。v3.2 之後,**系統每月 1 號自動推 Telegram 給你看完整勝率報告**:

- 各維度預測力(Spearman 相關度)
- 各 score band 命中率
- 哪些 pattern 在 over-/under-rated
- Engine Controller 決策後悔率
- Dexter DD 是否真的加值

這比手動更可靠,也比靠感覺判斷更不會 self-deceive。但**重點是:跑滿 30 天不要中途放棄**,小樣本下任何結論都不可靠。

---

## 部署 Checklist(15 分鐘上手)

```bash
# 1. Fork 主骨架
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 2. 放檔案
mkdir -p system_prompts skills .github/workflows reports/reflections
cp 01_surge_screener_prompt.md       system_prompts/
cp 04_engine_controller_prompt.md    system_prompts/
cp 06_historical_case_library.md     system_prompts/
cp 02_dexter_due_diligence_skill.md  skills/
cp 05_self_reflection_skill.md       skills/
cp 03_github_actions_workflow.yml    .github/workflows/surge_screener.yml
cp 00_README.md                      README.md

# 3. 設 Secrets(GitHub repo Settings → Secrets and variables → Actions)
# LLM:在 trusted self-hosted runner 執行 codex login(ChatGPT subscription)
# Secrets:POLYGON_API_KEY, UNUSUAL_WHALES_API_KEY,
#         SEC_EDGAR_USER_AGENT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# 4. 第一次手動跑(Actions 頁 → Run workflow)
#    universe: sp1500 / min_score: 65 / run_deep_dd: true

# 5. 確認 artifacts 跑出 4 個 JSON + reports/ 後,啟用排程 cron
git push origin main

# 6. 第一個月底會自動跑 self_reflection,推月度報告到 Telegram
```

---

## 已知局限(誠實標記)

1. **EOD only** — 系統是收盤後跑,盤中即時警報需升級 VPS 自架
2. **缺即時新聞流** — Polygon News 已在訂閱裡但目前未串(Layer 0.5 是後續可加項)
3. **缺地緣政治偵測** — 只透過 VIX 間接反映,沒有專屬模組
4. **多市場品質遞減** — 美股 > 港股 > A 股 > 台股(LLM 中文新聞分析弱於英文)
5. **熊市表現會差** — global_multiplier 雖會降權,但**最理性的做法是熊市直接停跑**
6. **沒有自動下單** — 故意設計成只推訊號不下單,讓人類做最後判斷

---

## 接下來最該做的事(優先級排序)

1. **部署 + 紙上模擬 30 天** — 別跳過這步
2. **記錄 Engine Controller 決策審計** — 看 BREADTH/DEPTH 路由是否合理
3. **回測歷史資料** — 把每日 reports/ 累積後丟進 AlphaEvo(姊妹專案)做因子權重最佳化
4. **加 Layer 0.5 News Sweep**(可選) — 用 Polygon News API,免錢
5. **加重大新聞獨立警報通道**(可選) — 持倉保護,高 ROI
6. **多市場擴展** — 美股穩定後再開港 / A / 台

---

⚠️ **重要免責:** 這套系統做的是**訊號生成**,不是投資建議。所有交易決策由你負責。市場有風險,系統會犯錯。
