---
id: price_above_ma200
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: long
status: seed
lift: 
precision: 
verdict: 
validated_on: 
sources: [fama-french-1993-three-factor]
---
# price_above_ma200 · 收盤 > 200 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** long(3月+)

收盤 > 200 日均線

## 假說 / 文獻依據
- [[fama-french-1993-three-factor]] — 因子模型的鼻祖(市場/規模/價值)。理解『因子如何被建構與檢定』的起點。

## 驗證紀錄
_(由 `knowledge_sync.py` 從 factor_lift.json / forward_factor_lift.json 寫回:lift / precision / verdict)_

## 相關
- 維度樞紐:[[Dim1]]
