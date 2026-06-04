---
id: rvol_ge_2
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
status: weak
lift: 1.36
precision: 0.258
verdict: WEAK
validated_on: 2026-06-04
sources: []
verdict_mt: WEAK
q_value: 0.0183
---
# rvol_ge_2 · 相對量能 ≥ 2×

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

相對量能 ≥ 2×

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.36 | 26% | WEAK | WEAK | 0.0183 |
| +30%/20d | 1.36 | 14% | NOISE | NOISE | 0.0896 |
| +40%/40d | 1.17 | 14% | NOISE | NOISE | 0.3857 |
| +50%/60d | 1.45 | 19% | WEAK | WEAK | 0.0112 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
