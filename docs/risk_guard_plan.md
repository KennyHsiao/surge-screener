# Risk Guard 風險雷達計劃書

> 目的:把 Quant Radar 既有的大盤、K 線、期權、板塊、COT、IBKR 持倉訊號整合成一個「提早降風險」頁面。第一版先用既有免費資料與本地報表,不接下單、不給投資建議,只輸出風險狀態與檢查清單。

---

## 1. 背景與問題

目前系統已經有很多單點訊號:

- `暴漲股篩選器`:SPY vs 50/200DMA、VIX、regime multiplier、市場警告。
- `期權作戰台`:GO/WAIT/AVOID、IV Rank、財報風險、VWAP、突破/量能、合約流動性。
- `期權分析`:call/put volume ratio、put/call ratio、V/OI、GEX proxy、波動率微笑/期限結構。
- `選擇權異常流`:異常 call/put volume、估權利金、V/OI,但目前免費源只能看「大量」,非逐筆 sweep。
- `熱錢板塊輪動`:RRG Leading / Weakening / Lagging / Improving。
- `COT / ES 週報`:籌碼背景驗證,但週期較慢。
- `IBKR 對帳`:真實持倉 vs screener ledger,可看策略是否脫節。

缺口是:這些訊號分散在不同頁面,沒有一個明確回答:

1. 現在是否該降低整體風險?
2. 哪些持倉或觀察名單正在轉危險?
3. 風險來自大盤、個股價格、期權、板塊、COT,還是資料不足?
4. 系統應該提醒「正常持有 / 降倉觀察 / 避開或出場」哪一種狀態?

---

## 2. 產品定位

頁面名稱:風險雷達 / Risk Guard

導覽位置:

- 美股群組,建議放在 `期權作戰台` 後、`IBKR 對帳` 前。
- URL path:`risk-guard`

核心原則:

- 唯讀,不下單。
- 先顯示資料限制,再顯示分數。
- COT 只當背景,不當主觸發。
- 第一版用明確規則,不要讓 LLM 決定風險分數。
- 輸出要能被交易者快速掃描,避免長篇敘述。

主要狀態:

- `NORMAL`:正常持有 / 低風險。
- `WATCH`:降倉觀察 / 風險升高。
- `REDUCE`:減碼或避開 / 多個風險源共振。
- `EXIT`:出場警戒 / 價格結構已破壞或期權風險極高。

顏色建議:

- NORMAL:綠。
- WATCH:黃。
- REDUCE:橘紅。
- EXIT:紅。
- DATA_GAP:灰或黃,不得誤顯示成低風險。

---

## 3. 版本路線圖總覽

### V1 - MVP:整合既有訊號的風險雷達

目標:不新增昂貴資料源,先把既有資料整合成可用頁面。

範圍:

- 新增 `scripts/risk_guard.py`
- 新增 `ui/risk_guard.py`
- 修改 `app.py` 導覽
- 讀取:
  - `scored_candidates.json`
  - `reports/reconciliation.json`
  - `reports/cot/*.verified.json`
  - `reports/sector_rotation.json`
  - `reports/options_flow/latest.json` 若存在
  - 即時 yfinance 日線與選擇權摘要,透過既有 `momentum_options.py`、`options_free.py`、`sector_flow.py`

輸出:

- 整體市場風險卡
- 持倉/自選股風險表
- 單檔風險明細
- 資料缺口提示

### V1.1 - Watchlist 與手動輸入

目標:不用 IBKR 也能用。

範圍:

- 支援 `content/us_watchlist.txt`
- 支援 UI textarea 手動輸入 ticker
- 可選來源:
  - IBKR 持倉
  - screener candidates
  - watchlist
  - 手動輸入

### V1.2 - 風險原因更細化

目標:讓使用者知道「為什麼變危險」。

範圍:

- 每檔顯示風險來源分解:
  - Market
  - Price
  - Options
  - Sector
  - COT
  - Position
  - Data Quality
- 表格支援依總風險、狀態、持倉損益、板塊象限排序。

### V2 - Portfolio Guard:持倉級風控

目標:從單檔風險擴展到整體曝險。

範圍:

- 根據 IBKR reconciliation 聚合:
  - 持倉底層
  - 合約到期日
  - 單腿/多腿
  - 未實現 P&L
  - DTE
- 顯示:
  - 近 7/14/30 天到期風險
  - 單一板塊集中度
  - 單一主題集中度
  - 未被 screener 追蹤的持倉
  - 高虧損但仍未減碼的持倉

### V2.1 - Risk Budget

目標:把風險轉成倉位建議語言。

範圍:

- 使用者設定:
  - 單檔最大虧損%
  - 單檔最大權利金曝險
  - 單板塊最大曝險
  - 期權 DTE 下限
- 輸出:
  - 符合風險預算
  - 超出預算
  - 需降曝險

注意:只顯示風險預算狀態,不自動計算下單數量。

### V3 - Options Risk Pro

目標:強化期權面提前避跌能力。

範圍:

- 免費源:
  - put/call volume ratio
  - OTM put concentration
  - IV Rank / IV percentile
  - 近月 IV backwardation
  - put skew
  - V/OI spike
- 付費源預留:
  - Unusual Whales sweeps/blocks
  - bid/ask aggressor side
  - dark pool
  - dealer gamma / GEX

輸出:

- `OPTIONS_CALM`
- `OPTIONS_HEDGING_DEMAND`
- `OPTIONS_STRESS`
- `OPTIONS_DATA_GAP`

### V4 - Backtest / Calibration

目標:驗證哪些風險規則真的能提前避開回撤。

範圍:

- 新增 `scripts/risk_guard_backtest.py`
- 對歷史資料回測:
  - 風險燈號後 5/10/20 日最大回撤
  - false positive rate
  - missed drawdown rate
  - risk score 分桶後的平均 MDD
- 對比:
  - 只看價格
  - 價格 + VIX
  - 價格 + options
  - 價格 + sector
  - all signals

輸出:

- `reports/risk_guard/backtest_summary.json`
- `reports/risk_guard/backtest_YYYY-MM-DD.md`

### V5 - Alerting / Automation

目標:每日自動掃描與推送。

範圍:

- 新增排程:
  - 收盤後掃描一次
  - 可選盤中手動刷新
- 產生:
  - `reports/risk_guard/latest.json`
  - `reports/risk_guard/YYYY-MM-DD.json`
- Telegram 推送:
  - 只推 `REDUCE` / `EXIT`
  - 不推 NORMAL
  - 合併同一標的重複訊號

### V6 - LLM Risk Brief

目標:在規則分數之上,增加一段 AI 摘要,但不讓 AI 改分數。

範圍:

- LLM 只讀取 `risk_guard/latest.json`
- 輸出:
  - 今日市場風險一句話
  - 最需要注意的 3 檔
  - 主要風險來源
  - 資料缺口
- 禁止:
  - LLM 自行查價
  - LLM 修改風險分數
  - LLM 給直接買賣指令

---

## 4. V1 詳細規格

### 4.1 新增檔案

新增:

- `scripts/risk_guard.py`
- `ui/risk_guard.py`

修改:

- `app.py`
- `docs/USER_GUIDE.md` 可後補

可選新增:

- `reports/risk_guard/latest.json`
- `reports/risk_guard/YYYY-MM-DD.json`

### 4.2 `scripts/risk_guard.py` 資料契約

核心函式:

```python
def analyze_risk(tickers: list[str], include_positions: bool = True) -> dict:
    ...
```

回傳格式:

```json
{
  "generated_at": "2026-06-06T00:00:00+00:00",
  "as_of": "2026-06-06",
  "market": {
    "status": "WATCH",
    "score": 42,
    "reasons": [],
    "regime": {},
    "cot": {}
  },
  "rows": [
    {
      "ticker": "NVDA",
      "status": "WATCH",
      "risk_score": 48,
      "market_score": 15,
      "price_score": 10,
      "options_score": 8,
      "sector_score": 10,
      "cot_score": 5,
      "position_score": 0,
      "data_quality_score": 0,
      "primary_reasons": [],
      "data_gaps": [],
      "position": {},
      "technical": {},
      "options": {},
      "sector": {}
    }
  ],
  "data_sources": {
    "regime": "scored_candidates.json",
    "cot": "reports/cot/latest verified json",
    "positions": "reports/reconciliation.json",
    "options": "yfinance_free"
  }
}
```

### 4.3 風險分數規則 V1

總分 0-100。分數越高越危險。

建議權重:

- Market:20
- Price:25
- Options:20
- Sector:15
- Position:10
- COT:5
- Data Quality:5

狀態門檻:

- `NORMAL`:0-24
- `WATCH`:25-49
- `REDUCE`:50-74
- `EXIT`:75-100

規則必須 fail-closed:

- 資料缺口不得當成 0 風險。
- 但資料缺口也不應直接變 EXIT。
- 缺資料只加到 Data Quality,並在原因中顯示。

### 4.4 Market 分數

來源:

- `scored_candidates.json["regime_context"]`
- 若缺,可用 yfinance 即時計算 SPY 50/200DMA 與 VIX。

規則:

- SPY below 50DMA:+7
- SPY below 200DMA:+10
- VIX >= 20:+5
- VIX >= 25:+8
- VIX >= 30:+12
- global_score_multiplier < 0.85:+5
- global_score_multiplier < 0.65:+8
- regime warnings 非空:+2,最高 +5

封頂 20。

### 4.5 Price 分數

來源:

- yfinance daily OHLCV
- 可復用 `scripts/momentum_options._technical`

規則:

- close < MA20:+5
- close < MA50:+8
- close < MA200:+12
- close 跌破 20 日前低:+8
- 5 日跌幅 <= -8%:+8
- 20 日跌幅 <= -15%:+8
- ATR14 擴大且 close below VWAP:+5
- gap down > 8% within 5d:+10

封頂 25。

### 4.6 Options 分數

來源:

- `scripts/options_free.analyze_options`
- `scripts/momentum_options.analyze`
- `reports/options_flow/latest.json` 若存在

規則:

- put/call volume ratio > 1.2:+5
- put/call volume ratio > 1.8:+10
- IV percentile >= 70:+5
- IV percentile >= 85:+10
- near-term IV backwardation:+5
- OTM put volume concentration:+5
- bearish unusual flow in latest report:+8
- options data unavailable:+3 到 Data Quality,不要加到 Options。

封頂 20。

### 4.7 Sector 分數

來源:

- `scripts/sector_flow.gather_sector_flow`
- `scripts/sector_flow.sector_etf_for`
- `reports/sector_rotation.json`

規則:

- sector quadrant = Weakening:+8
- sector quadrant = Lagging:+12
- sector heat_score falling or low:+3
- sector 20d excess < -5%:+5
- stock sector unknown:+2 到 Data Quality。

封頂 15。

### 4.8 COT 分數

來源:

- 最新 `reports/cot/*.verified.json`

只用於背景:

- ES Tuesday to Friday delta <= -1.5%:+2
- leveraged funds short change 明顯增加:+2
- asset manager net change 明顯轉弱:+1
- stale warning true:+2 到 Data Quality,不是 COT。

封頂 5。

### 4.9 Position 分數

來源:

- `reports/reconciliation.json`

規則:

- held_not_in_ledger:+3
- 單底層 unrealized P&L <= -10%:+4
- 單底層 unrealized P&L <= -25%:+8
- option DTE <= 14 且虧損:+5
- option DTE <= 7:+8
- 多個 legs 缺少完整資料:+2 到 Data Quality。

封頂 10。

---

## 5. V1 UI 規格

### 5.1 頁面結構

`ui/risk_guard.py`

頁首:

- 標題:`風險雷達 / Risk Guard`
- caption:`整合大盤、價格、期權、板塊、COT、持倉的唯讀風險儀表板。非投資建議。`

頂部卡片:

- Overall Status
- Market Risk Score
- High Risk Count
- Data Gap Count

Tabs:

1. `總覽`
2. `持倉 / Watchlist`
3. `單檔明細`
4. `資料來源`

### 5.2 總覽 tab

顯示:

- 市場風險狀態 chip
- SPY vs 50/200DMA
- VIX
- COT Tuesday-Friday move
- sector leaders / weakening sectors
- 今日主要風險原因 top 5

### 5.3 持倉 / Watchlist tab

資料表欄位:

- 狀態
- 代號
- 總風險
- Market
- Price
- Options
- Sector
- Position
- COT
- 主要原因
- 資料缺口

預設排序:

1. status severity desc
2. risk_score desc
3. position loss desc

### 5.4 單檔明細 tab

使用 selectbox 選 ticker。

顯示:

- 風險狀態 chip
- 分數分解 bar chart
- 價格技術資料
- 期權資料
- 板塊資料
- 持倉資料
- COT 背景
- data gaps

### 5.5 資料來源 tab

顯示:

- 每個來源是否存在
- 最後更新時間
- 目前缺口
- 對應修復指令:
  - `make cot`
  - `python scripts/options_flow_scan.py`
  - `python scripts/sector_flow.py`
  - `python scripts/ibkr_client.py reconcile`

---

## 6. Claude 實作排程

### Sprint 1 - V1 MVP

預估:1-2 天。

任務:

1. 新增 `scripts/risk_guard.py`
   - 實作 ticker 收集:
     - IBKR reconciliation holdings
     - scored candidates
     - `content/us_watchlist.txt`
   - 實作 market / price / options / sector / COT / position scoring。
   - 所有外部抓取必須 try/except,單一 ticker 失敗不能中斷。

2. 新增 `ui/risk_guard.py`
   - 做四個 tabs。
   - 用 `_shared.chip`, `_shared.metric_card`, 顏色常數。
   - 表格用 `st.dataframe`,避免 matplotlib 依賴。

3. 修改 `app.py`
   - 匯入 `risk_guard`
   - 在美股 nav 增加 `st.Page(risk_guard.render, title="風險雷達", icon="🛡", url_path="risk-guard")`

4. 基本驗證
   - `python -m py_compile scripts/risk_guard.py ui/risk_guard.py app.py`
   - `make run` 手動看頁面不崩潰。

驗收:

- 無 IBKR 檔案時頁面仍能用 watchlist/candidates。
- 無 options_flow/latest.json 時只顯示資料缺口,不崩潰。
- 至少能對 NVDA / AMD / SPY 產生風險列。
- COT 過舊時顯示 stale,但不直接觸發 EXIT。

### Sprint 2 - V1.1 / V1.2

預估:1 天。

任務:

1. UI 增加資料來源 selector:
   - IBKR 持倉
   - Screener candidates
   - Watchlist
   - Manual input

2. 單檔明細補完整 reason list。

3. 增加 `reports/risk_guard/latest.json` 寫出功能:
   - CLI:`python scripts/risk_guard.py --tickers NVDA,AMD`
   - CLI:`python scripts/risk_guard.py --from-watchlist`
   - CLI:`python scripts/risk_guard.py --output reports/risk_guard/latest.json`

驗收:

- CLI 可產 JSON。
- UI 可讀即時計算或 latest JSON。
- data gaps 明確列出,不被藏在 caption。

### Sprint 3 - V2 Portfolio Guard

預估:1-2 天。

任務:

1. 解析 IBKR option leg:
   - expiry
   - DTE
   - right
   - strike
   - qty
   - unrealized P&L

2. 增加 portfolio summary:
   - total unrealized P&L
   - options expiring <=7 / <=14 / <=30 days
   - by underlying
   - by sector

3. 增加 concentration warnings。

驗收:

- IBM/NOW/HOOD 這類多腿或虧損持倉可正確顯示。
- DTE 過短且虧損會進 WATCH/REDUCE。

### Sprint 4 - V3 Options Risk Pro

預估:2-3 天。

任務:

1. 將 `us_options.py` 中波動率微笑/期限結構邏輯抽出成可復用 helper。

2. Risk Guard 使用:
   - put skew
   - near-term backwardation
   - OTM put concentration
   - bearish flow

3. 預留 paid provider 介面:

```python
class OptionsRiskProvider:
    def get_options_risk(self, ticker: str) -> dict:
        ...
```

驗收:

- 免費源沒有資料時仍可用。
- 若 options chain 有資料,Options score 不只依 put/call ratio。

### Sprint 5 - V4 Backtest / Calibration

預估:3-5 天。

任務:

1. 新增 `scripts/risk_guard_backtest.py`
2. 以歷史 OHLCV 建構 price/market/sector 可回測特徵。
3. 暫時不回測 options,除非已有歷史 IV/OI。
4. 輸出風險分桶與後續最大回撤。

驗收:

- 能回答 `risk_score >= 50` 後 10/20 日 MDD 是否顯著變差。
- 能找出過度敏感規則。

### Sprint 6 - V5/V6 Automation + LLM Brief

預估:1-2 天。

任務:

1. 每日產生 `reports/risk_guard/latest.json`
2. Telegram 只推 REDUCE/EXIT。
3. 新增 LLM 摘要,只讀 JSON。

驗收:

- 推送不重複轟炸。
- LLM 摘要不改分數。
- 無 API key 時規則版仍正常運作。

---

## 7. 開發注意事項

- 不要把缺資料視為安全。
- 不要讓 LLM 產生或修改價格、分數、風險狀態。
- 不要引入 scipy/matplotlib。
- 優先復用:
  - `ui/_shared.py`
  - `scripts/momentum_options.py`
  - `scripts/options_free.py`
  - `scripts/sector_flow.py`
  - `scripts/cot_es.py`
- 單一 ticker 抓取失敗必須只影響該 ticker。
- UI 不應因任何來源缺檔而崩潰。
- 所有輸出都要標註「僅供訊號生成,非投資建議」。

---

## 8. 建議優先順序

第一優先:V1 + V1.1 + V1.2

理由:

- 馬上可用。
- 不需新資料費用。
- 能回答「現在是否該降風險」。
- 對既有架構侵入低。

第二優先:V2

理由:

- 真正和持倉風控連上。
- 對使用者的實際虧損控制最有價值。

第三優先:V3

理由:

- 期權資料能更早反映避險需求,但免費源有限。
- 若未來接 Unusual Whales,價值會明顯提升。

第四優先:V4

理由:

- 用歷史驗證降低假警報。
- 但需要更多時間清理資料與定義回測。

第五優先:V5/V6

理由:

- 自動化與摘要是加速使用流程,但不應早於核心分數穩定。

---

## 9. MVP Definition of Done

V1 完成標準:

- `風險雷達` 頁面出現在 Streamlit 美股導覽。
- 頁面可在缺少 IBKR、options_flow、COT 任一資料時正常顯示。
- 至少支援 watchlist/manual tickers。
- 每檔有 0-100 risk score 與 NORMAL/WATCH/REDUCE/EXIT。
- 每檔至少有 3 類風險分解:Market、Price、Sector。
- 若 options 資料可用,加入 Options 分數。
- 若 position 資料可用,加入 Position 分數。
- UI 表格可排序,單檔明細可展開。
- `python -m py_compile` 通過。
- `make run` 手動驗證頁面不崩潰。

