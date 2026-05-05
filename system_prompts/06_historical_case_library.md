# Historical Surge Case Library — Few-Shot Exemplars

> 用途:在 Layer 1 Breadth Pass 與 Layer 2 Engine Controller 開頭注入這份案例庫,讓 LLM 看過「教科書級暴漲股長什麼樣」,提升 pattern matching 精度。

> 使用方式:這份檔案會被 prompt loader 自動載入,作為 system prompt 的 **few-shot examples** 區塊出現,告訴 LLM:「這就是真實成功與失敗的 surge candidate 模樣」。

> 維護:每月 self-reflection 跑完後,把該月真實命中且漲幅 ≥30% 的案例加入,把 false positive 案例加入 Anti-Examples。讓 case library 持續累積。

---

## 使用協議(餵給 LLM 看)

當你在 Layer 1 評估一檔候選時,先在心裡比對這份案例庫:

- **這檔候選的 6 維度訊號組合接近哪個歷史成功 case?** → 該 case 的事後報酬可作為期望值參考
- **訊號組合接近哪個歷史失敗 case?** → 啟動警戒,額外驗證
- **訊號組合不像任何一個 case?** → 不一定是壞事,可能是新型態,但要在輸出註明 "novel_pattern: true"

不要機械式套用過去 case。每個 case 都有時代背景、利率環境、產業週期,直接複製不會精準 — 但 pattern shape 是會重複的。

---

## ✅ Successful Surge Cases (Educational Examples)

### Case S-001 — NVDA, May 2023(AI 元年突破型)

```yaml
ticker: NVDA
breakout_date: 2023-05-25
trigger_event: FY24 Q1 earnings + GTC keynote 後 6 週
forward_60d_return: +37%
forward_180d_return: +95%
pattern_classification: continuation_VCP_with_catalyst

signals_at_breakout:
  technical:
    trend_template_passed: 8/8
    minervini_clean: yes
    pattern: VCP_3_contractions_breaking_neckline
    volume_today: 3.2x_20day_avg
    macd: daily_cross_5d_ago + weekly_histogram_strong
    rs_rating: 96
  
  catalyst:
    8k_filed_within_14d: yes (Q1 earnings beat — revenue 19% above consensus)
    eps_surprise: +43%
    revenue_surprise: +19%
    analyst_upgrades_14d: 18 banks raised PT, average +35%
  
  sentiment:
    x_velocity: 5.2x_baseline
    x_bullish_pct: 78%
    smart_money_chatter: yes — Cathie Wood, multiple credible analysts
  
  institutional:
    13f_net_buying: yes (last quarter)
    form4_insider: 0 buyers (negative_score, but offset by other dims)
    short_interest: 2.1% (low)
  
  options_flow:
    call_put_ratio: 3.8
    largest_sweep: $12M premium, 30DTE OTM calls, all bid-side
    dark_pool_5d: heavy_accumulation
    gex_regime: deeply_negative_with_call_wall_30pct_above
  
  sector_market:
    sector_rs: top_decile
    spy_above_50dma: yes
    vix: 17.8

composite_score_v3.1: ~92
verdict: STRONG_BUY (confirmed)

key_lesson: |
  **這是教科書級的「五合一共振」**。技術突破 + 重大催化 + 機構下注 + 情緒爆發 + 選擇權異常,
  五個維度全亮綠燈,且都是同一個故事(AI 推論需求爆發)。當你看到類似組合,規模可以加大。
  注意:選擇權 GEX 已經是 deeply negative + call wall 高聳 = 軋空條件成熟,這是預示「進場後加速」的關鍵。
```

### Case S-002 — AVGO, Jun 2024(機構默默累積型)

```yaml
ticker: AVGO
breakout_date: 2024-06-13
trigger_event: F2Q earnings + AI revenue 揭露
forward_60d_return: +44%
forward_120d_return: +62%
pattern_classification: stealth_accumulation_into_catalyst

signals_at_breakout:
  technical:
    trend_template_passed: 7/8
    pattern: cup_with_handle_breakout
    volume: 2.5x_20day
    macd: zero_line_above_already, recent_golden_cross
    rs_rating: 88

  catalyst:
    8k: AI revenue guide raised
    eps_surprise: +6% (modest)
    revenue_surprise: +5% (modest — surprise wasn't huge)
    
  sentiment:
    x_velocity: 1.8x_baseline (relatively quiet — this is the tell)
    x_bullish_pct: 62%
    smart_money_chatter: 主流尚未反應,小圈子在傳

  institutional:
    13f_net_buying: yes — Coatue, Tiger initiated
    form4_insider: 1 buyer ($800K)
    short_interest: 4%

  options_flow:
    call_put_ratio: 2.2
    multiple_blocks: $1-3M premium each, opening positions, 60-90DTE
    dark_pool: persistent_accumulation_3_weeks

  sector_market:
    sector_rs: top_quintile
    spy: above_50dma
    vix: 13

composite_score_v3.1: ~78
verdict: STRONG_BUY (confirmed via DD)

key_lesson: |
  **「沉默的累積」型暴漲**。情緒分數偏低(只 1.8x velocity)是好事,代表機構搶在散戶之前。
  關鍵訊號是選擇權的 multiple blocks 持續累積 + 暗池 3 週累積 + 13F 高品質基金初次建倉。
  這種 case 容易被「情緒驅動」的 agent 漏掉,但 v3.1 的 6a/6b/6c 應該抓到。
  **規則:當 sentiment 弱但 institutional + options flow 強,反而是高 conviction 訊號**。
```

### Case S-003 — MSTR, Nov 2024(主題共振型)

```yaml
ticker: MSTR
breakout_date: 2024-11-08
trigger_event: BTC 突破 $80K + 公司加碼買入 + 選舉後制度傳聞
forward_30d_return: +148%
forward_60d_return: +127%
pattern_classification: theme_amplifier_with_reflexivity

signals_at_breakout:
  technical:
    trend_template_passed: 8/8
    pattern: VCP_into_breakout, 6 month base
    volume: 4.1x
    macd: aligned_multi_timeframe

  catalyst:
    8k: company announced additional BTC purchase ($X.X B)
    earnings_momentum: positive but secondary

  sentiment:
    x_velocity: 8.5x_baseline (extreme)
    x_bullish_pct: 84%
    smart_money_chatter: heavy

  institutional:
    13f: dominated by passive ETF growth
    short_interest: 21% — 軋空燃料

  options_flow:
    call_put_ratio: 5.6
    sweeps: $40M+ in week prior, all opening, OTM calls
    iv: very high but bid-side flow continuing
    gex: deeply negative

  sector_market:
    crypto_proxy: yes — BTC reflexivity
    market_regime: bull, post-election rally

composite_score_v3.1: ~95 (近滿分)
verdict: STRONG_BUY

key_lesson: |
  **主題共振型**:BTC 漲 → MSTR 漲 → MSTR 加碼買 BTC → BTC 再漲 (reflexive flywheel)。
  這種 case 風險也高 — 反身性反過來時跌得也兇。
  **進場規則:這類 case 確認倉位要小**(建議倉位 < 2%),因為 IV 已經高 + 容易戴帽子。
  系統若給高分,Engine Controller 應該在 DEPTH 階段問「IV 是否已經高到限制 risk-reward?」
```

### Case S-004 — TSLA, Mar 2020(跌深反彈型)

```yaml
ticker: TSLA
breakout_date: 2020-03-23 (general market bottom)
forward_180d_return: +405%
pattern_classification: oversold_reversal_with_divergence

signals_at_breakout:
  technical:
    trend_template_passed: 2/8 (still below 200DMA — survives via Hard Filter 5 exception)
    pattern: w_bottom_with_RSI_bullish_divergence (price LL, weekly RSI HL)
    volume: 2.0x
    macd: daily_below_zero BUT just_crossed_zero_line + weekly_divergence
    rs_rating: 65 (decent, not great)

  catalyst:
    macro: Fed unprecedented stimulus, lockdown narrative reversal
    company: production data resilient

  sentiment:
    x_velocity: 4.2x
    bullish_pct: 60%

  institutional:
    13f: ARK and others adding into weakness
    insider: insiders holding, no selling

  options_flow:
    call_buying_resumed_after_capitulation
    gex: flipping from positive to negative

  sector_market:
    market: post-capitulation bounce
    vix: 60+ → 50 (still elevated but falling)

composite_score_v3.1: ~62 (mid-tier — survives but not high conviction at face value)
verdict: WATCHLIST → upgraded after Layer 2 BREADTH found macro pivot

key_lesson: |
  **這是 v3 系統最容易漏掉的 case**。Trend Template 只過 2/8,VIX > 30,
  composite 分數只 62 — 沒到 65 門檻。但 v3.1 的反轉型態 (1c, +5–7 pts) 加上
  MACD 零軸交叉(1d, +2 pts)+ 週線背離把它救起來了。
  **Engine Controller 應該用 BREADTH 模式問:這是個股 alpha 還是大盤反彈帶飛?**
  → BREADTH 找到「macro 政策大轉彎」這個跨個股的因子 → 該股反而值得進場。
  **規則:VIX > 30 + 反轉型態 + macro pivot = 倉位放大,因為 risk-reward 極佳**。
```

### Case S-005 — GME, Jan 2021(異常案例,留作警惕)

```yaml
ticker: GME
breakout_date: 2021-01-13
forward_30d_return: +1500% peak, 但後 30d -75%
pattern_classification: anomalous_short_squeeze

signals_at_breakout:
  technical: 
    trend_template_passed: 0/8
    pattern: undefined — chaotic
    volume: 50x

  catalyst:
    fundamental: weak (struggling retailer)
    8k: nothing material
    
  sentiment:
    x_velocity: 100x+ (off-the-charts)
    reddit_wsb: dominant
    smart_money: notably_absent (Citron, Melvin shorting)

  institutional:
    13f: minimal
    insider: nothing
    short_interest: 140% of float (extreme)

  options_flow:
    call_buying: extreme
    gamma_squeeze: developing

  sector_market:
    sector_rs: bottom_decile
    market: bull

composite_score_v3.1: ~30 (FAIL)
verdict: REJECTED (correctly — this is gambling, not investing)

key_lesson: |
  **系統正確拒絕這個 case**。雖然 GME 後來漲了 1500%,但:
  1. 沒有任何 fundamental 支撐
  2. Smart money 站在反方
  3. 純 sentiment + 軋空驅動,沒有可重複的 alpha
  4. 後 30 天 -75% — 真正進得去的人大多虧錢
  **規則:當 sentiment 100x baseline 但 institutional + smart money 缺席,這是 pump 不是 alpha**。
  系統不該假裝能抓這種 case。它的時間軸與風險特性與 surge candidate 不同。
```

---

## ❌ Anti-Examples (False Positives — 高分但失敗)

### Case A-001 — XYZ Inc, Mar 2024(假突破型)

```yaml
breakout_date: 2024-03-15
forward_60d_return: -12%
why_it_fooled_the_system:
  - Pattern looked like VCP (9 pts)
  - Volume 2.5x (8 pts)
  - 8-K filed 5 days before (8 pts)
  - But: catalyst was ambiguous (PR-style "expanding partnership" announcement, no real $$$)
  - X velocity was inorganic — concentrated in a few accounts <90 days old (Layer 3 should have caught)
  - Form 4: insider SELLING in week prior (system scored it 0, should have penalized)
post_mortem:
  - Hard Filter 7 should consider extending to detect inorganic sentiment patterns
  - Insider selling clustering should be a soft penalty, not just 0 pts
  - Catalyst quality scoring needs sub-criteria (genuine revenue impact vs. PR fluff)
```

### Case A-002 — ABC Corp, Sept 2024(板塊 beta 偽裝個股 alpha)

```yaml
breakout_date: 2024-09-10
forward_60d_return: +8% (vs sector ETF +12%)
why_it_fooled_the_system:
  - Composite scored 74 (mid-tier confirm)
  - But almost all gain was sector beta (correlation 0.92 with sector ETF)
  - No idiosyncratic alpha
  - Dexter DD missed the sympathy-play question
post_mortem:
  - Engine Controller's BREADTH question "is this sympathy?" was triggered but answered weakly
  - Add explicit sector-correlation calc as part of Layer 0.5 enrichment
```

---

## 維護協議

每月 1 號跑 self-reflection 後,LLM 應追加新案例:

- 真實命中且 ≥30% 在 60 天內 → 加入 Successful Cases
- 系統推薦但失敗 → 加入 Anti-Examples + 寫 post-mortem
- 系統 reject 但事後大漲(false negative) → 加入「missed_winners」區段(本檔未列出,但機制保留)

每 6 個月做一次大整理,合併重複的 pattern,只保留最具教學價值的 30–50 個 case。

---

## 引用方式(prompt 內注入)

在 Layer 1 prompt 中加入:

```
## REFERENCE — Historical Surge Case Library

You have access to a curated library of historical surge stocks
(see attached `06_historical_case_library.md`).

Before scoring each candidate, briefly compare its 6-dimension signal
profile to the case library. Note in the output:

- "similar_to_case": "S-001" (if there's a clear analog)
- "expected_return_band_per_analog": "+25 to +50%"
- "anti_example_warning": "matches A-001 pattern" (if false positive risk)

Do NOT use case library to override scoring math — use it for context
and risk calibration only.
```
