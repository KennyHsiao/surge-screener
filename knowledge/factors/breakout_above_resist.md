---
id: breakout_above_resist
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
status: noise
lift: 0.92
precision: 0.432
verdict: NOISE
validated_on: 2026-06-04
sources: []
verdict_mt: NOISE
q_value: 1.0
---
# breakout_above_resist · 帶量突破前 20 日壓力

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

帶量突破前 20 日壓力

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.92 | 43% | NOISE | NOISE | 1.0 |
| +30%/20d | 1.17 | 33% | NOISE | NOISE | 0.2448 |
| +40%/40d | 0.71 | 25% | CONTRARIAN | CONTRARIAN | 1.0 |
| +50%/60d | 0.70 | 25% | CONTRARIAN | CONTRARIAN | 1.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
