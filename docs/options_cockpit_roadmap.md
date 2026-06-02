# 期權作戰台 — UI/UX Roadmap

決策座艙(`ui/options_cockpit.py`)的設計藍圖。來源:9-agent 研究(TOS / tastytrade /
OptionStrat / Market Chameleon / IBKR 的 UI/UX 慣例)綜合 + 把關。

**北極星**:期權面應收斂成**一個可信的盤前決策座艙**,由上而下照交易者決策順序
讀:判定 → IV 環境 → 流動性 → 合約 → 互動損益圖(POP + 預期波動錐)→ 財報否決。
唯讀、不下單、只 GO/WAIT/AVOID;每個機率都標註為估計;IV Rank 未滿 ~40 天降級為
「累積中」;OI 在免費源回傳 0 時隱藏。

---

## ✅ 已完成(本次)

- 新增 `ui/options_cockpit.py` 期權作戰台,版面照交易者讀盤順序。
- 損益圖 / Greeks / POP / 預期波動錐 = 自帶 Black–Scholes 真算(`math.erf`+numpy,無 scipy）。
- `_live_provider` 接真資料:`momentum_options.analyze` + `options_free.analyze_options`
  + `iv_history.iv_percentile` + `momentum_options._chart_data`;`_load_cockpit` 先試真、
  失敗退回 `_demo_provider`。
- 防呆:無甜蜜點合約 → 空狀態;`theta/vega/premium=None` → `_f` 格式化;
  IV Rank 未滿 40 天 → 「累積中 n=NN」灰階儀表。
- 財報在 DTE 內 → 全寬 `st.error` 否決橫幅。
- **整併**:`動能期權` 頁退役(從 `app.py` nav 移除);其引擎 `scripts/momentum_options.py`
  仍是資料源。`期權分析`(`us_options.py`)保留作「鏈微結構」明細頁。

種子 IV 歷史(真實 IV Rank 可用):`NVDA AMD TSLA ARM MU`。其餘代號 IV Rank 顯示「累積中」。

---

## ~~P0~~ ✅ 已完成 — `scripts/options_analytics.py` 共用數學模組

**原問題**:兩套 BS(引擎 `momentum_options.bs_call_greeks` scalar vs 作戰台
`_bs_call/_ncdf/_prob_of_profit/_expected_move` vectorized)會漂移。
**結果**:新增 `scripts/options_analytics.py`(`R_FREE` / `ncdf`(polymorphic)/ `npdf` /
`bs_call_greeks` / `bs_call_value` / `prob_of_profit` / `expected_move`,`math.erf`+numpy,無 scipy)。
- `momentum_options.bs_call_greeks = _ana.bs_call_greeks`(引擎);作戰台 `_bs_call/_ncdf/...` 全 alias 到同模組。
- 引擎與 UI 在 app 內**綁同一個 module 實例**(`mo._ana is oc._ana == scripts.options_analytics`);CLI/測試走 flat-import fallback。
- `test_momentum_options.py` 新增 3 測:`is`-identity 單一來源、scalar↔vector CDF 一致、
  `bs_call_value` 的有限差分 delta = `bs_call_greeks` 的解析 delta(損益圖與 checklist Greeks 可證一致)。**10/10 通過**。
- 零行為變化:CDF 位元相同;demo 數字不變;引擎 Greeks 逐字搬移。

---

## P1 — 應做

### 2. `期權分析`(us_options.py)修正倒置的版面
現在開頭就是四張 raw 量能卡、無判定/IV 錨點。改為頂部加:
- 偏多/中性/偏空 **chip**(由 `call_put_volume_ratio`/`put_call_ratio`+regime 推導)
- IV Rank **chip**(`iv_history.iv_percentile(ticker)`,未滿 40 天顯示「累積中 n=NN」)

放在 `r1=st.columns(4)` 之前,中間 `st.divider()`。純重排既有區塊。

### 3. `_chip` / `_metric` 提升到 `ui/_shared.py`
作戰台已寫好乾淨的 `_chip(text,color)` 與 `_metric(...)`。搬到 `_shared` 成
`chip`/`metric_card`,三頁共用;`us_options` 的 inline `_card` 與灰字 flag 改用之。

### 4. 色票集中到 `ui/_shared.py`
把作戰台的 `_GREEN/_RED/_ACCENT/...` 常數搬進 `_shared`,取代 `us_options`/`momentum_options`
的 `#00CC96/#EF553B/#636EFA` 字面值。**保留 `ACCENT=#ef4444` 只給 AVOID/primary**,
損益負值用獨立的 `LOSS` 紅;多空配 ▲/▼。新增色盲友善的單色序列 `HEAT_SEQ`(藍→青,非綠↔紅)。

### 5. 多標的 IV/flow 分流表(强化候選排行)
把 `us_options`(與 `momentum_options` scan)的排行 tab 升級成可排序網格:
`代號 | 綜合 | 判定(狀態條) | options_flow | IV-Rank | 距財報 | IV sparkline`,
預設依 判定→IV-Rank 排序。資料來自 `scored_candidates.json` + `iv_history`
(只有 5 個種子代號有真 sparkline,其餘「累積中」)。
**做法**:`st.column_config.LineChartColumn`(st 1.57 已有)畫近 30 筆 IV;判定上色用
`Styler.apply`(**禁用** `background_gradient`,見約束)。

---

## P2 — 擴充

### 6. 策略選單(單買 Call / 牛市買權價差)
`st.selectbox('結構',['單買 Call','牛市買權價差'])` 餵 `_payoff_fig`;把它一般化成
**多腿**:到期曲線 = 各腿內在值加總,today 曲線 = 各腿 BS 加總;顯示 POP/最大獲利/最大虧損。
空頭腿由同一條鏈取 ~Δ0.20。**只做 2 種結構**(單用戶、延遲資料),不移植 50 種策略目錄。
**做法**:`_payoff_fig(d,days)` → `_payoff_fig(d,days,legs)`;`legs` 預設
`[{'strike':K,'qty':+1}]`;breakeven 用 `np.where(np.diff(np.sign(pl)))` 偵測。

### 7. 鏈量熱圖(us_options 替代視圖)
`go.Heatmap`/`px.imshow`(strikes × [call_vol, put_vol, call_oi])藏在
`st.radio(['長條','熱圖'])` 後,spot 用 annotation line,色階用 `HEAT_SEQ`。牆/釘讀法更好。

### 8. 波動率微笑 / 期限結構(on-demand)
按鈕觸發,拉 2-3 個到期:IV-vs-strike(前月微笑/偏斜,clip ~10-40Δ)與 ATM-IV-vs-DTE,
放 `st.tabs(['波動率微笑','期限結構'])`,丟掉 NaN。put skew = 下檔恐懼;近月 backwardation =
事件被定價——單一 ATM IV 看不出。標 on-demand 因免費源多到期拉取慢。

---

## ⚠️ 環境技術約束(務必遵守)

- **沒有 matplotlib** → `Styler.background_gradient` 會 `ImportError`。表格漸層改用
  `Styler.apply` 或 `st.column_config.ProgressColumn`/`BarChartColumn`。
- **不要加 scipy**;BS/常態 CDF 用 `math.erf`(已有)。
- numpy 2.4 / pandas 3.0 / streamlit 1.57(`.venv`)。`use_container_width` 仍可用但已標 deprecated
  (全 repo 一致),未來統一改 `width=` 再一次處理。
- 免費 yfinance 延遲 ~15 分、盤中 OI 常為 0 → EOD 波段定位,OI 面板在 0 時隱藏。

---

## 整併後的期權面 IA

| 頁面 | 角色 |
|---|---|
| 🎯 期權作戰台 | **主**:盤前單名決策(判定/方向/波動/圖/合約/損益/清單) |
| 🧮 期權分析 | 鏈微結構明細(量分佈/最活躍/熱圖/微笑)+ 多標的分流表 |
| ~~🚀 動能期權~~ | 已退役(引擎保留為資料源) |
