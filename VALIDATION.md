# 免費資料驗證報告 (2026-05-24)

> 本次以「**程式抓已驗證的真實資料 → 餵 LLM 判斷**」為原則,在**完全不使用付費 API key** 的情況下,把整條篩選管線從頭跑通一次,確認哪些階段免費可行、哪些必須付費。LLM 判斷由 Claude 在 session 內代跑(尚未接 API key)。

---

## 一句話結論

**免費資料足以產出「一份排序過的觀察名單」,但不足以跨過 Layer 2 門檻產出「值得深度盡調的 actionable 標的」** —— 缺的那一步,正是付費資料(催化新聞 + 籌碼 + 完整期權 flow)的價值所在。

---

## 驗證範圍與方法

- **股票池**:NASDAQ-100(101 檔)
- **資料源(全免費,無 key)**:
  - 價量 / 趨勢 / MACD / RSI → `yfinance`(`scripts/01_hard_filter.py`)
  - 社群情緒 → StockTwits + Reddit/ApeWisdom(`scripts/sentiment_free.py`)
  - 期權 → yfinance 期權鏈(`scripts/options_free.py`)
- **LLM 判斷**:Claude(session 內代跑),依 `system_prompts/01_surge_screener_prompt.md` 的 6 維度評分表 + StockTwits 偏多校準

---

## 各階段可行性 + 成本

| 階段 | 免費可行? | 本次實測結果 | 要做到 actionable 需要 |
|---|---|---|---|
| **Stage 1 硬篩選** | ✅ 完全 | 101 → **47 檔通過**(7 條硬規則) | 免費即可 |
| **Layer 1 6維度評分** | ✅ 部分(~70/100 分) | 47 檔全評分、可排序;最高 50(MCHP) | 催化(20)+ 籌碼(10)需付費 |
| **Layer 2 引擎控制器** | ❌ | **47 檔全部 TERMINATE(資料不足)** | 必須有催化/籌碼才能過 65 門檻 |
| **Layer 3 深度盡調** | ❌ | 無合格輸入 | SEC API + UW flow |
| **Layer 4 報告** | ❌ | 無確認標的 | 同上 |

**月成本參考(若補上付費資料)**:Polygon Stocks Starter $29 / Unusual Whales $29–99 / LLM(Opus 約 $0.01–0.03 每檔每輪、DeepSeek 近乎免費)。

---

## 免費資料的能力邊界(本次最關鍵的發現)

6 維度評分表共 100 分,免費只能填 **~70 分**:

| 維度 | 滿分 | 免費資料 | 狀態 |
|---|---|---|---|
| 技術 | 30 | yfinance | ✅ |
| 催化 | 20 | 需新聞/財報 API | ❌ data_missing |
| 情緒 | 15 | StockTwits + ApeWisdom | ✅ |
| 籌碼 | 10 | 需 13F/Form4 API | ❌ data_missing |
| 板塊 | 5 | 主題判斷 | ✅ |
| 期權 | 20 | yfinance 免費鏈 | ✅(較粗) |

→ 最高約 70 分,實測落在 **22–50**。Layer 2 門檻是 **regime-adjusted ≥ 65**,**沒有任何一檔達到**。因此引擎控制器對每檔的結論都是:
> 「技術+期權強,但**缺催化(為什麼是現在?)+ 籌碼(智錢進了沒?)**,無法確認暴漲觸發 → TERMINATE,維持觀察。」

**這不是系統壞掉,是它誠實地拒絕在資訊不足時給出 actionable 推薦。**

---

## LLM 判斷產出的真實洞察(AI 判斷的價值)

即使只有部分資料,AI 判斷仍抓到幾個人工易忽略的點:

1. **同樣大漲,要分「追高 vs 健康整理」** —— MU 20日 +51% 但 5日僅 +3.6%(冷卻中),比 5日 +18% 的 QCOM 是更好的進場點。
2. **跨訊號修正** —— MELI 技術面最弱(跌破均線),但免費期權部位最強(8/11),AI 把它從「該淘汰」拉回「反彈博弈」。
3. **全市場 Reddit 提及動能轉負**(QCOM −82%、MU −65%…)→ 都是延續行情,**沒有新鮮社群暴量**,情緒維度全面該降權(StockTwits 預設偏多,需校準)。

---

## 資料來源路由建議(免費 vs Grok/付費)

「按目的分配資源」是正確方向:

| 需求 | 來源 | 費用 | 理由 |
|---|---|---|---|
| 美股零售情緒 | StockTwits + ApeWisdom | 免費 | 夠用、可持續、官方端點 |
| **幣圈情緒** | **Grok**(xAI API) | 付費 | 幣圈討論在 X,不在 StockTwits |
| **追蹤特定 X 博主/KOL** | **Grok**(`allowed_x_handles`) | 付費 | StockTwits 根本做不到 |
| 催化 / 籌碼 / 完整期權 | Polygon / Unusual Whales | 付費 | Layer 2 過關的關鍵 30 分 |

**重點**:沒有「免費 + 授權 + 正確」的 X 資料管道(免費爬蟲 snscrape/Nitter 已死、違反 ToS)。要 X 原生資料只能走付費 Grok;Grok 回的是合成摘要,須要求附上引用貼文以可稽核,且即時搜尋不可重現(要快照存檔)。

---

## 核心原則:verified data → AI(反幻覺)

程式負責抓**已驗證的真實資料**,LLM 只在這些資料上判斷,**不自己搜尋或猜測價格**。本次全程遵守:所有分數都基於 yfinance/StockTwits/ApeWisdom 的真實回傳,缺資料的維度一律標 `data_missing` 並給 0,絕不編造。

---

## 本次新增 / 修改的程式

- **新增** `scripts/sentiment_free.py` — 免費情緒模組(StockTwits + ApeWisdom),已強化處理畸形/錯誤的 200 回應(來源隔離、不偽造 low-buzz)
- **修改** `scripts/02_llm_score.py` — 將免費情緒接進 Dimension 3,附偏多校準提示;`fetch_free_sentiment` 永不拋例外、不中斷評分
- **POC(獨立,不影響管線)**:`poc_grok_x_sentiment.py`(Grok x_search)、`poc_sentiment_judgment.py`(AI 判斷層)、`poc_free_sentiment.py`(已被 `sentiment_free.py` 取代,可刪)
- **新增** `.claude/skills/run-dashboard/SKILL.md` — 本地啟動 dashboard 的已驗證步驟

---

## 待辦 / 下一步決策

1. **要不要付費資料?** —— 這是「觀察名單」升級成「actionable 推薦」的唯一缺口。建議先補 **Polygon($29)**(催化)+ **Unusual Whales($29)**(籌碼/期權),Layer 2 才會有合格輸入。
2. **LLM 自動化** —— 目前由 Claude 代跑驗證。要排程自動跑,需接 API key(先 DeepSeek 驗證、確認賺錢再上 Opus)。
3. **幣圈 / X 博主追蹤** —— 等決定付費,再加 `sentiment_grok.py`(同 `gather_sentiment` 介面,呼叫端依美股/幣圈路由)。
4. **金鑰安全** —— session 中曾貼過一把 xAI key,**請至 console.x.ai 撤銷重發**。

---

⚠️ 僅供訊號生成,非投資建議。
