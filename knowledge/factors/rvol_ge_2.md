---
id: rvol_ge_2
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
status: validated
lift: 1.63
precision: 0.574
verdict: VALIDATED
validated_on: 2026-06-04
sources: []
verdict_mt: VALIDATED
q_value: 0.0
---
# rvol_ge_2 · 相對量能 ≥ 2×

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

相對量能 ≥ 2×

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.63 | 57% | VALIDATED | VALIDATED | 0.0 |
| +30%/20d | 1.92 | 45% | VALIDATED | VALIDATED | 0.0 |
| +40%/40d | 1.56 | 43% | VALIDATED | VALIDATED | 0.0 |
| +50%/60d | 1.45 | 41% | WEAK | WEAK | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
