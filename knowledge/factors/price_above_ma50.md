---
id: price_above_ma50
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: seed
lift: 
precision: 
verdict: 
validated_on: 
sources: [jegadeesh-titman-1993-momentum]
---
# price_above_ma50 · 收盤 > 50 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

收盤 > 50 日均線

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。

## 驗證紀錄
_(由 `knowledge_sync.py` 從 factor_lift.json / forward_factor_lift.json 寫回:lift / precision / verdict)_

## 相關
- 維度樞紐:[[Dim1]]
