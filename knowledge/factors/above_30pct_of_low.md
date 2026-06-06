---
id: above_30pct_of_low
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: noise
lift: 1.14
precision: 0.225
verdict: NOISE
validated_on: 2026-06-07
sources: []
verdict_mt: NOISE
q_value: 0.0328
runway_neutral_lift: 1.3
runway_verdict: genuine
---
# above_30pct_of_low · 距 52 週低點 ≥ 30%

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

距 52 週低點 ≥ 30%

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> ✅ **已解除封鎖**:point-in-time 成份股(無倖存者偏差)、樣本充足 → 可作為決策依據。注意 ⚠️ `delisted_data_gap`:深度下市成份股缺免費歷史,殘餘小缺口。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.14 | 22% | NOISE | NOISE | 0.0328 |
| +30%/20d | 1.09 | 11% | NOISE | NOISE | 0.3032 |
| +40%/40d | 1.26 | 15% | WEAK | WEAK | 0.0011 |
| +50%/60d | 1.17 | 16% | WEAK | WEAK | 0.0238 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| above_30pct_of_low | 1.14 | 1.30 |

> ✅ runway-independent — ATR-中性目標下 lift 仍 >1,是真訊號
