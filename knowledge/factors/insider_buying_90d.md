---
id: insider_buying_90d
node_type: factor
dimension: Dim4
subfactor: 4b Insider
horizon: mid
status: noise
lift: 0.85
precision: 0.184
verdict: NOISE
validated_on: 2026-06-04
sources: [cohen-malloy-pomorski-2012-insider]
verdict_mt: NOISE
q_value: 0.5317
---
# insider_buying_90d · 近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)

**維度** [[Dim4]] · **子因子** 4b Insider · **持有視窗** mid(2週~3月)

近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)

## 假說 / 文獻依據
- [[cohen-malloy-pomorski-2012-insider]] — 區分『慣例型』與『機會型』內部人交易,後者才有預測力 —— 精修 insider_buying_90d 的關鍵。

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.85 | 18% | NOISE | NOISE | 0.5317 |
| +30%/20d | 0.89 | 10% | NOISE | NOISE | 0.7363 |
| +40%/40d | 1.15 | 15% | NOISE | NOISE | 0.6557 |
| +50%/60d | 0.95 | 14% | NOISE | NOISE | 0.8596 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim4]]
