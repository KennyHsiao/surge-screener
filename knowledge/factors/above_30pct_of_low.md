---
id: above_30pct_of_low
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: weak
lift: 1.18
precision: 0.493
verdict: WEAK
validated_on: 2026-06-04
sources: []
verdict_mt: WEAK
q_value: 0.0
---
# above_30pct_of_low · 距 52 週低點 ≥ 30%

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

距 52 週低點 ≥ 30%

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.18 | 49% | WEAK | WEAK | 0.0 |
| +30%/20d | 1.09 | 31% | NOISE | NOISE | 0.034 |
| +40%/40d | 1.16 | 36% | WEAK | WEAK | 0.0 |
| +50%/60d | 1.18 | 36% | WEAK | WEAK | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
