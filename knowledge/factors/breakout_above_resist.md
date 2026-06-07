---
id: breakout_above_resist
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
status: contrarian
lift: 0.46
precision: 0.104
verdict: CONTRARIAN
validated_on: 2026-06-06
sources: []
verdict_mt: CONTRARIAN
q_value: 0.0008
---
# breakout_above_resist · 帶量突破前 20 日壓力

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

帶量突破前 20 日壓力

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.46 | 10% | CONTRARIAN | CONTRARIAN | 0.0008 |
| +30%/20d | 0.61 | 7% | NOISE | NOISE | 0.1105 |
| +40%/40d | 0.25 | 4% | CONTRARIAN | CONTRARIAN | 0.0002 |
| +50%/60d | 0.38 | 6% | CONTRARIAN | CONTRARIAN | 0.0015 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
