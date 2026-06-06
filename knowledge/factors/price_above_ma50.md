---
id: price_above_ma50
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: contrarian
lift: 0.52
precision: 0.117
verdict: CONTRARIAN
validated_on: 2026-06-07
sources: [jegadeesh-titman-1993-momentum]
verdict_mt: CONTRARIAN
q_value: 0.0
runway_neutral_lift: 0.9
runway_verdict: runway-artifact
---
# price_above_ma50 · 收盤 > 50 日均線

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

收盤 > 50 日均線

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.52 | 12% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.50 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.45 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.47 | 7% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| price_above_ma50 | 0.52 | 0.90 |

> ⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),原判定是固定 %-漲幅的量測產物
