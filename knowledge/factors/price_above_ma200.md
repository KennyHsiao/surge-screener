---
id: price_above_ma200
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: long
status: contrarian
lift: 0.75
precision: 0.379
verdict: CONTRARIAN
validated_on: 2026-06-04
sources: [fama-french-1993-three-factor]
verdict_mt: CONTRARIAN
q_value: 0.0
---
# price_above_ma200 · 收盤 > 200 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** long(3月+)

收盤 > 200 日均線

## 假說 / 文獻依據
- [[fama-french-1993-three-factor]] — 因子模型的鼻祖(市場/規模/價值)。理解『因子如何被建構與檢定』的起點。

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.75 | 38% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.68 | 22% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.73 | 26% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.74 | 26% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
