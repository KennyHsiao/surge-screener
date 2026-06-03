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
_最後同步 2026-06-04 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.67 | 14% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.62 | 7% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.74 | 10% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.67 | 10% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
