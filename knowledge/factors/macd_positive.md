---
id: macd_positive
node_type: factor
dimension: Dim1
subfactor: 1d MACD
horizon: mid
status: contrarian
lift: 0.42
precision: 0.096
verdict: CONTRARIAN
validated_on: 2026-06-06
sources: []
verdict_mt: CONTRARIAN
q_value: 0.0
runway_neutral_lift: 0.86
runway_verdict: runway-artifact
---
# macd_positive · MACD 線 ≥ 0

**維度** [[Dim1]] · **子因子** 1d MACD · **持有視窗** mid(2週~3月)

MACD 線 ≥ 0

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.42 | 10% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.36 | 4% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.35 | 5% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.40 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| macd_positive | 0.42 | 0.86 |

> ⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),原判定是固定 %-漲幅的量測產物
