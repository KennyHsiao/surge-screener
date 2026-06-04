---
node_type: moc
title: 因子知識網絡 — Map of Content
---
# 因子知識網絡 (MOC)

復盤分析的因子↔文獻↔驗證知識網絡。用 Obsidian 開啟此資料夾即可看 graph。

## 維度樞紐
- [[Dim1]] — 技術面 (Technical)
- [[Dim2]] — 催化劑 / 事件 (Catalyst)
- [[Dim3]] — 情緒 (Sentiment)
- [[Dim4]] — 機構 / 內部人籌碼 (Institutional)
- [[Dim5]] — 板塊 / 市場環境 (Sector & Regime)
- [[Dim6]] — 選擇權流 (Options Flow)
- [[Dim7]] — 分析師共識 (Analyst)

## 因子(依持有視窗)

**short(數日~2週)**
- [[rvol_ge_2]] — 相對量能 ≥ 2×
- [[breakout_above_resist]] — 帶量突破前 20 日壓力
- [[bb_squeeze]] — 布林帶擠壓(整理基底)
- [[macd_golden_cross_10d]] — 近 10 日 MACD 黃金交叉
- [[price_above_vwap]] — 收盤 > 20 日 VWAP
- [[recent_8k_14d]] — 近 14 日內有 8-K(任意,含常規)
- [[material_8k_14d]] — 近 14 日內有『材料型』8-K(併購/財報/重大協議/Reg FD/重大事件;排除常規如高管異動、附件)

**mid(2週~3月)**
- [[price_above_ma50]] — 收盤 > 50 日均線
- [[within_25pct_of_high]] — 距 52 週高點 ≤ 25%
- [[above_30pct_of_low]] — 距 52 週低點 ≥ 30%
- [[rsi_40_65]] — RSI 在 40-65(健康動能,非超買)
- [[macd_positive]] — MACD 線 ≥ 0
- [[low_rv_base]] — 已實現波動百分位 ≤ 30(低波基底)
- [[rel_strength_vs_spy]] — 20 日報酬 > SPY(相對強度,板塊代理)
- [[insider_buying_90d]] — 近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)

**long(3月+)**
- [[price_above_ma200]] — 收盤 > 200 日均線
- [[ma_stack_50_150_200]] — 50 > 150 > 200 日均線多頭排列
- [[market_regime_ok]] — SPY > 50 日線 且 VIX < 25

## 文獻
- [[jegadeesh-titman-1993-momentum]] — Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency (1993)
- [[george-hwang-2004-52week-high]] — The 52-Week High and Momentum Investing (2004)
- [[bernard-thomas-1990-pead]] — Evidence that Stock Prices Do Not Fully Reflect the Implications of Current Earnings for Future Earnings (1990)
- [[pan-poteshman-2006-option-volume]] — The Information in Option Volume for Future Stock Prices (2006)
- [[cremers-weinbaum-2010-putcall-parity]] — Deviations from Put-Call Parity and Stock Return Predictability (2010)
- [[cohen-malloy-pomorski-2012-insider]] — Decoding Inside Information (2012)
- [[baker-wurgler-2006-sentiment]] — Investor Sentiment and the Cross-Section of Stock Returns (2006)
- [[moskowitz-grinblatt-1999-industry-momentum]] — Do Industries Explain Momentum? (1999)
- [[fama-french-1993-three-factor]] — Common Risk Factors in the Returns on Stocks and Bonds (1993)
- [[harvey-liu-zhu-2016-cross-section]] — ... and the Cross-Section of Expected Returns (2016)
- [[mclean-pontiff-2016-decay]] — Does Academic Research Destroy Stock Return Predictability? (2016)
- [[hou-xue-zhang-2020-replicating-anomalies]] — Replicating Anomalies (2020)
- [[jensen-kelly-pedersen-2023-replication]] — Is There a Replication Crisis in Finance? (2023)
- [[chen-zimmermann-2021-open-source]] — Open Source Cross-Sectional Asset Pricing (2021)
- [[feng-giglio-xiu-2020-taming-factor-zoo]] — Taming the Factor Zoo: A Test of New Factors (2020)
- [[gu-kelly-xiu-2020-ml-asset-pricing]] — Empirical Asset Pricing via Machine Learning (2020)

---
_由 `scripts/knowledge_seed.py` 產生;`knowledge_ingest.py` 新增文獻、`knowledge_sync.py` 回寫驗證結果。_
