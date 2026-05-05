# 美股暴漲股篩選 AI Agent — 部署包 (v3.1, DEoT + MACD)

> 五份文件,組成一套可以每日自動跑、收盤後推送 Telegram 的美股暴漲股雷達。  
> 預設美股,可勾選擴展到港股 / A 股 / 台股。
>
> **v3.1 變更**:技術維度新增 MACD 多時間框架金叉確認 (1d, 3 分) + 反轉型態(W 底 + RSI 多頭背離,1c),並把 MACD 零軸以下作為硬過濾(Filter 7),除非有零軸交叉或週線 RSI 背離。涵蓋「強勢延續型」與「跌深反彈型」兩種暴漲模式。
>
> **v3.0 變更**:整合 NeuroWatt 的 **Dual Engines of Thoughts (DEoT)** 多層分析架構(arxiv 2504.07872 / itrd.ai)。從 v2 的 flat scoring 升級到 **Layer 0 (Base Prompter) → Layer 1 (Breadth Pass) → Layer 2 (Engine Controller-routed Breadth or Depth) → Layer 3 (Dexter DD) → Final Response** 五層樹狀分析。Token 不再平均花在每檔候選身上,而是依訊號強弱動態分配深度。

---

## 五份文件做什麼

| 檔案 | 角色 | 放哪 |
|---|---|---|
| `01_surge_screener_prompt.md` | **Layer 0 + Layer 1** — Base Prompter(每日 regime 檢查 + 全域分數乘數)+ Breadth Pass(6 維度 100 分初評) | `daily_stock_analysis/system_prompts/` |
| `04_engine_controller_prompt.md` | **Layer 2 — Engine Controller**(NEW) — 根據 Layer 1 結果,決定每檔候選往 BREADTH(找隱藏故事)、DEPTH(專攻最強維度)或 TERMINATE(停損 token) | `daily_stock_analysis/system_prompts/` |
| `02_dexter_due_diligence_skill.md` | **Layer 3 — 深度盡調 SKILL.md** — 對通過 Layer 2 的候選跑 SEC 10-Q/8-K、Form 4 內部人、X 社群、選擇權 flow 反向驗證、做空論證 | `dexter/.dexter/skills/` |
| `03_github_actions_workflow.yml` | **每日排程** — 美東收盤後跑 5 層分析、寫報告、推 Telegram、commit reports 進 repo | `.github/workflows/` |
| `00_README.md` | 部署 checklist + 架構圖 + 成本 + 警告 | repo 根目錄 |

---

## 系統流程 (v3 — 5 層樹狀分析)

```
                       ┌─────────────────────────────┐
                       │  GitHub Actions cron (5:30PM ET)
                       └──────────────┬──────────────┘
                                      ▼
   ┌───────────────────────────────────────────────────────┐
   │ LAYER 0 — Base Prompter (每日跑一次)                   │
   │   • SPY vs 50/200 DMA 檢查                             │
   │   • VIX 區間判定                                       │
   │   • 計算 global_score_multiplier (×0.5 ~ ×1.0)         │
   │   • 識別當日 active themes                             │
   │   → 產出 regime_context (Layer 1+ 都引用)              │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────┐
   │ STAGE 1 — Hard Filter                                  │
   │   6 條硬規則,3000 → 400 檔                             │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────┐
   │ LAYER 1 — Breadth Pass (每檔候選跑一次)                 │
   │   6 維度初評 100 分制                                   │
   │   套用 regime_context 乘數                              │
   │   → 通常 400 → ~30 檔 (regime-adjusted score ≥65)       │
   │   verdict: NEEDS_LAYER_2 / WATCHLIST / REJECT          │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────┐
   │ LAYER 2 — Engine Controller (DEoT 核心)               │
   │   每檔候選獨立判斷:                                     │
   │   ┌─────────────────────────────────────────┐          │
   │   │ 訊號集中? → DEPTH (專攻最強維度,1-2 題) │          │
   │   │ 訊號分散? → BREADTH (找隱藏故事,2-3 題) │          │
   │   │ 訊號矛盾? → BREADTH (釐清誰對)         │          │
   │   │ 訊號弱?   → TERMINATE                   │          │
   │   └─────────────────────────────────────────┘          │
   │   單檔最多 2 層,6 節點                                 │
   │   → 通常 30 → ~10 檔 (signal_conclusive)               │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────┐
   │ LAYER 3 — Dexter Due Diligence (US only)             │
   │   • SEC 10-Q / 8-K 閱讀                               │
   │   • Form 4 內部人 + 13F 機構動向                       │
   │   • X 社群品質與真實性                                  │
   │   • 選擇權 flow 反向驗證 (UW MCP)                      │
   │   • 做空論證壓測 (mandatory)                            │
   │   → 通常 10 → ~5 檔 (CONFIRMED)                        │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   ┌───────────────────────────────────────────────────────┐
   │ LAYER 4 — Final Response Agent                        │
   │   合併 Layer 0~3 所有節點輸出,產出:                   │
   │   • 最終排名 + verdict (STRONG_BUY/WATCHLIST/REJECT)   │
   │   • 推理樹 (而非只有打分)                              │
   │   • 進場區、停損、建議倉位                              │
   └──────────────┬────────────────────────────────────────┘
                  ▼
        ┌─────────────────────────┐
        │ 報告 + Telegram 推送     │
        └─────────────────────────┘
```

**和 v2 (flat scoring) 的關鍵差異:**

| | v2 | v3 (DEoT) |
|---|---|---|
| 每檔候選分析深度 | 一律相同 | 依訊號強弱動態分配 |
| Token 分配 | 平均 | 集中在強訊號候選 |
| Regime 處理 | 事後乘數 | Layer 0 前置處理 |
| 輸出形式 | 打分 + 3 條原因 | 推理樹 + 跨維度發現 |
| 漏掉的情境 | 訊號分散但隱藏故事的股 | Engine Controller 的 BREADTH 會抓 |
| Token 成本(同樣 30 檔候選) | 100% baseline | ~120-140%(只有 top 候選跑深) |

DEoT 引入了「**Effective Reasoning Information Rate (ERIR)**」概念:每個分析節點如果沒產出新訊息就要終止。這讓系統不會在同一個證據上鬼打牆。

---

## 部署 checklist

### 1. Fork / clone `daily_stock_analysis`

```bash
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis
```

### 2. 把五個檔案放到對的位置

```bash
mkdir -p system_prompts skills .github/workflows
cp 01_surge_screener_prompt.md       system_prompts/
cp 04_engine_controller_prompt.md    system_prompts/
cp 02_dexter_due_diligence_skill.md  skills/
cp 03_github_actions_workflow.yml    .github/workflows/surge_screener.yml
cp 00_README.md                      README.md
```

### 3. 設定 GitHub Secrets

到 repo Settings → Secrets and variables → Actions,加入:

**LLM(至少一個):**
- `ANTHROPIC_API_KEY` — 推薦,Claude Opus 4.7 跑 prompt 1 效果最好
- `OPENAI_API_KEY` — 備援
- `DEEPSEEK_API_KEY` — 想省錢可用,品質尚可

**資料源(至少一個):**
- `POLYGON_API_KEY` — 美股價量、財報,免費 tier 足夠日線
- `FINNHUB_API_KEY` — 替代,有 8-K 推送、insider transactions

**SEC 文件:**
- `SEC_EDGAR_USER_AGENT` — 設成你的 email,免費,例: `your-name your@email.com`

**情緒源:**
- `X_BEARER_TOKEN` — X API Basic tier $200/月,或先用 free tier 跑少量
- `EXA_API_KEY` — 給 Dexter 做高品質網頁搜尋用,可選

**選擇權 flow(Dimension 6 必需,主力資金腳印):**
- `UNUSUAL_WHALES_API_KEY` — Unusual Whales,$29–99/月零售方案。**他們官方有 MCP server (`unusualwhales.com/public-api/mcp`),Claude/Dexter 可原生調用,不用包 API**。沒有此 key 時 Dimension 6 自動歸 0,系統仍會跑但會明顯漏掉主力訊號。

**通知:**
- `TELEGRAM_BOT_TOKEN` — 從 @BotFather 拿
- `TELEGRAM_CHAT_ID` — 從 @userinfobot 拿

### 4. 第一次手動跑

到 Actions 頁,選 "Daily US Surge Screener" → "Run workflow":
- markets: `US`
- universe: `sp1500`(第一次選小一點測流程)
- min_score: `65`
- run_deep_dd: `true`

跑完看 Artifacts 下載結果,確認 JSON 結構符合預期再放出 cron。

### 5. 啟用排程

預設已寫好 21:30 UTC = 5:30 PM EST,不用調。EDT 期間會晚一小時,如果在意精準,可加第二條 cron:

```yaml
- cron: '30 21 * * 1-5'  # EDT
- cron: '30 22 * * 1-5'  # EST
```

(會偶爾重複跑,把 script 寫成冪等就好。)

---

## 預期的 Telegram 報告長相

```
🎯 2026-05-05 美股暴漲股雷達 (DEoT v3)

🌡 Layer 0 — Regime
   SPY 上 50DMA / VIX 17.2 / 全域乘數 1.0
   主題:AI infra, GLP-1, 核能復興

📊 掃描:S&P 1500
✅ 通過硬篩選:412
🟢 Layer 1 過分:28
🧠 Layer 2 通過 Engine Controller:11
🔥 Layer 3 通過 Dexter DD:6

━━━━━━━━━━━━━━━━━━━━
🥇 #1  $XXXX  87 分  CONFIRMED

   📈 Layer 1 訊號:Tech 28, Catalyst 18, Options 18
   🧠 Layer 2 路徑:DEPTH (訊號集中,跳過 BREADTH)
       ↳ 驗證 VCP 樞紐:✅ 收縮符合 50% 規則,5 週基底
       ↳ 驗證 Options 開倉:✅ OI 增長中,30DTE 集中
       ↳ ERIR 高,2 節點後 SIGNAL_CONCLUSIVE
   🔍 Layer 3 DD:
       • 8-K 三天前公告 $2B 大單
       • 過去 5 日 OTM call sweeps $4.1M,全 bid-side
       • GEX 負區 + 上方 call wall = 軋空條件成熟
       • 做空論證:估值偏高但無立即觸發 → 通過
   📍 進場區:142.5–145.2 / 停損:136.0
   📦 建議倉位:3%
   ⚠️ 18 天後法說

🥈 #2  $YYYY  72 分  CONFIRMED (但已下修)

   📈 Layer 1 訊號:Tech 18, Cata 13, Opt 14, Sent 12 — 分散
   🧠 Layer 2 路徑:BREADTH (訊號分散,找隱藏故事)
       ↳ 同類股 sympathy 比對:相關性 0.7,**部分為板塊 beta**
       ↳ 法說前 12 天:符合 pre-earnings drift 模式
       ↳ 經 Engine Controller 從 STRONG → WATCHLIST
   📦 建議倉位:1.5%(下修),pre-earnings 性質非單純 alpha

━━━━━━━━━━━━━━━━━━━━

⚠️ 僅供研究,非投資建議。
```

---

## 預期成本(每月)

> v3 因為 Engine Controller 加了 Layer 2 動態深度分析,LLM 用量比 v2 多約 30-50%。但因為 Engine Controller 會主動 TERMINATE 弱訊號候選,實際增量低於想像。

| 項目 | 美股 only | 多市場 |
|---|---|---|
| GitHub Actions | $0(public repo)/ ~$0(private 含免費額度) | 同左 |
| LLM (Claude Opus,Layer 0+1+2+3+4 全跑) | ~$45–120 | ~$110–270 |
| Polygon Stocks Starter | $29 | $29 |
| **Unusual Whales(選擇權 flow,主力訊號)** | **$29–99** | **$29–99** |
| X API Basic | $200(可選,先免費 tier 跑跑看) | $200 |
| **合計** | **$105–450** | **$170–600** |

**省錢路線**: 用 DeepSeek + Finnhub 免費 tier + X 免費 tier + Unusual Whales 最低方案,每月約 $40–80。**注意:Dimension 6 (選擇權) + Engine Controller 是這套系統最有差異化的部分 — 沒有 UW 訊號就拉到平庸,沒有 Engine Controller 就沒有自適應深度,Token 會浪費在弱訊號上**。建議先跑 1–2 個月驗證能不能賺錢再升級到 Opus。

**v3 Token 節省機制(Engine Controller 內建):**
- ERIR (Effective Reasoning Information Rate) 監控 — 沒新訊息就 TERMINATE
- 訊號弱者直接停在 Layer 1
- 每檔最多 2 層、6 節點上限
- 同 30 檔候選下,實際 token 用量約 v2 的 1.2-1.4 倍而非 2-3 倍

---

## 重要警告

這套系統做的是**訊號生成**,不是投資建議。

- 任何單一訊號都可能錯,設停損、控倉位才是活下來的關鍵
- Hard filter 4 已經幫你避開法說前進場的賭博,但不要繞過它
- 大盤進入熊市(SPY 跌破 200DMA、VIX > 30)時,prompt 會自動套 0.7× 折扣,但**最聰明的做法是直接停跑這套系統**,因為熊市裡幾乎沒有持續性的暴漲股
- 任何 score 不能取代你自己看圖、看財報、看新聞的判斷

---

## 下一步建議

1. **先跑紙上模擬一個月** — 開個 Google Sheet,記每日 top 5,30 天後算命中率與平均報酬
2. **確認有 alpha 再進場** — 月勝率 < 55% 就回頭調 prompt,別硬上
3. **加上 AlphaEvo 回測** — 等資料累積夠了,把日報歷史餵進 AlphaEvo 自動找最有效的因子權重組合,迭代 prompt
4. **盤中即時版** — 等 EOD 版穩定賺錢,再升級 VPS 跑盤中爆量警報(這就需要重寫流程,prompt 邏輯可以共用)
