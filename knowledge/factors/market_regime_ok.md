---
id: market_regime_ok
node_type: factor
dimension: Dim5
subfactor: 5b Regime
horizon: long
status: contrarian
lift: 0.78
precision: 0.391
verdict: CONTRARIAN
validated_on: 2026-06-04
sources: []
verdict_mt: CONTRARIAN
q_value: 0.0
---
# market_regime_ok · SPY > 50 日線 且 VIX < 25

**維度** [[Dim5]] · **子因子** 5b Regime · **持有視窗** long(3月+)

SPY > 50 日線 且 VIX < 25

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.78 | 39% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.75 | 24% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.70 | 25% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.71 | 26% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim5]]
