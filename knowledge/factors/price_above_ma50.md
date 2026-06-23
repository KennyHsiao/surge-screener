---
id: price_above_ma50
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: exploratory
lift: 
precision: 
verdict: EXPLORATORY
validated_on: 
sources: [jegadeesh-titman-1993-momentum]
verdict_mt: EXPLORATORY
q_value: 
runway_neutral_lift: 
runway_verdict: exploratory
runway_blocked: True
blocked: True
verdict_raw: CONTRARIAN
exploratory_on: 2026-06-06
lift_exploratory: 0.52
precision_exploratory: 0.117
q_value_exploratory: 0.0
runway_neutral_lift_exploratory: 0.9
tags: [kg/block/blocked, kg/dim/Dim1, kg/horizon/mid, kg/runway/exploratory, kg/status/exploratory, kg/type/factor]
---
# price_above_ma50 · 收盤 > 50 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

收盤 > 50 日均線

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。

## 驗證紀錄
_最後同步 2026-06-23 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.52 | 12% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.50 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.45 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.47 | 7% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

> 🔒 此 run 為 BLOCKED(探索性)—— 下方 runway 判讀僅供參考,不可作為可行動結論。

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| price_above_ma50 | 0.52 | 0.90 |

> ⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),原判定是固定 %-漲幅的量測產物
