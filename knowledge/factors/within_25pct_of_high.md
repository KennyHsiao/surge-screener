---
id: within_25pct_of_high
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: seed
lift: 
precision: 
verdict: 
validated_on: 
sources: [jegadeesh-titman-1993-momentum, george-hwang-2004-52week-high]
---
# within_25pct_of_high · 距 52 週高點 ≤ 25%

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

距 52 週高點 ≤ 25%

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。
- [[george-hwang-2004-52week-high]] — 貼近 52 週高點本身就是動能訊號,且預測力強過傳統動能 —— 直接對應 within_25pct_of_high。

## 驗證紀錄
_(由 `knowledge_sync.py` 從 factor_lift.json / forward_factor_lift.json 寫回:lift / precision / verdict)_

## 相關
- 維度樞紐:[[Dim1]]
