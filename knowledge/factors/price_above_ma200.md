---
id: price_above_ma200
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: long
status: contrarian
lift: 0.67
precision: 0.145
verdict: CONTRARIAN
validated_on: 2026-06-07
sources: [fama-french-1993-three-factor]
verdict_mt: CONTRARIAN
q_value: 0.0
runway_neutral_lift: 1.0
runway_verdict: runway-artifact
---
# price_above_ma200 · 收盤 > 200 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** long(3月+)

收盤 > 200 日均線

## 假說 / 文獻依據
- [[fama-french-1993-three-factor]] — 因子模型的鼻祖(市場/規模/價值)。理解『因子如何被建構與檢定』的起點。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.67 | 14% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.62 | 7% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.74 | 10% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.67 | 10% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| price_above_ma200 | 0.67 | 1.00 |

> ⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),原判定是固定 %-漲幅的量測產物
