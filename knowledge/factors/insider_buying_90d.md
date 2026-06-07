---
id: insider_buying_90d
node_type: factor
dimension: Dim4
subfactor: 4b Insider
horizon: mid
status: noise
lift: 0.89
precision: 0.186
verdict: NOISE
validated_on: 2026-06-06
sources: [cohen-malloy-pomorski-2012-insider]
verdict_mt: NOISE
q_value: 0.6434
---
# insider_buying_90d · 近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)

**維度** [[Dim4]] · **子因子** 4b Insider · **持有視窗** mid(2週~3月)

近 90 日 ≥2 筆內部人公開市場買進 (Form 4 code P)

## 假說 / 文獻依據
- [[cohen-malloy-pomorski-2012-insider]] — 區分『慣例型』與『機會型』內部人交易,後者才有預測力 —— 精修 insider_buying_90d 的關鍵。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.89 | 19% | NOISE | NOISE | 0.6434 |
| +30%/20d | 0.94 | 10% | NOISE | NOISE | 0.8656 |
| +40%/40d | 1.20 | 15% | NOISE | NOISE | 0.553 |
| +50%/60d | 0.98 | 14% | NOISE | NOISE | 0.9575 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim4]]
