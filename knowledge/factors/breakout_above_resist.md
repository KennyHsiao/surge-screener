---
id: breakout_above_resist
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
status: contrarian
lift: 0.43
precision: 0.099
verdict: CONTRARIAN
validated_on: 2026-06-04
sources: []
verdict_mt: CONTRARIAN
q_value: 0.0004
---
# breakout_above_resist · 帶量突破前 20 日壓力

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

帶量突破前 20 日壓力

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.43 | 10% | CONTRARIAN | CONTRARIAN | 0.0004 |
| +30%/20d | 0.56 | 6% | NOISE | NOISE | 0.0632 |
| +40%/40d | 0.25 | 4% | CONTRARIAN | CONTRARIAN | 0.0002 |
| +50%/60d | 0.38 | 6% | CONTRARIAN | CONTRARIAN | 0.0017 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
