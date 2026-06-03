---
id: bb_squeeze
node_type: factor
dimension: Dim1
subfactor: 1c Pattern
horizon: short
status: weak
lift: 1.32
precision: 0.521
verdict: WEAK
validated_on: 2026-06-04
sources: []
verdict_mt: WEAK
q_value: 0.0
---
# bb_squeeze · 布林帶擠壓(整理基底)

**維度** [[Dim1]] · **子因子** 1c Pattern · **持有視窗** short(數日~2週)

布林帶擠壓(整理基底)

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.32 | 52% | WEAK | WEAK | 0.0 |
| +30%/20d | 1.15 | 32% | NOISE | NOISE | 0.2027 |
| +40%/40d | 1.26 | 38% | WEAK | WEAK | 0.0072 |
| +50%/60d | 1.21 | 37% | WEAK | WEAK | 0.0425 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
