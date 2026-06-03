---
id: bb_squeeze
node_type: factor
dimension: Dim1
subfactor: 1c Pattern
horizon: short
status: validated
lift: 1.69
precision: 0.301
verdict: VALIDATED
validated_on: 2026-06-04
sources: []
verdict_mt: VALIDATED
q_value: 0.0003
---
# bb_squeeze · 布林帶擠壓(整理基底)

**維度** [[Dim1]] · **子因子** 1c Pattern · **持有視窗** short(數日~2週)

布林帶擠壓(整理基底)

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.69 | 30% | VALIDATED | VALIDATED | 0.0003 |
| +30%/20d | 1.53 | 15% | VALIDATED | VALIDATED | 0.0361 |
| +40%/40d | 1.56 | 18% | VALIDATED | VALIDATED | 0.0127 |
| +50%/60d | 1.58 | 20% | VALIDATED | VALIDATED | 0.0083 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
