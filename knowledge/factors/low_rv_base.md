---
id: low_rv_base
node_type: factor
dimension: Dim1
subfactor: Vol base
horizon: mid
status: contrarian
lift: 0.51
precision: 0.294
verdict: CONTRARIAN
validated_on: 2026-06-04
sources: []
verdict_mt: CONTRARIAN
q_value: 1.0
---
# low_rv_base · 已實現波動百分位 ≤ 30(低波基底)

**維度** [[Dim1]] · **子因子** Vol base · **持有視窗** mid(2週~3月)

已實現波動百分位 ≤ 30(低波基底)

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.51 | 29% | CONTRARIAN | CONTRARIAN | 1.0 |
| +30%/20d | 0.41 | 14% | CONTRARIAN | CONTRARIAN | 1.0 |
| +40%/40d | 0.47 | 18% | CONTRARIAN | CONTRARIAN | 1.0 |
| +50%/60d | 0.47 | 18% | CONTRARIAN | CONTRARIAN | 1.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
