---
id: above_30pct_of_low
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: exploratory
lift: 
precision: 
verdict: EXPLORATORY
validated_on: 
sources: []
verdict_mt: EXPLORATORY
q_value: 
runway_neutral_lift: 
runway_verdict: exploratory
runway_blocked: True
blocked: True
verdict_raw: NOISE
exploratory_on: 2026-06-06
lift_exploratory: 1.14
precision_exploratory: 0.225
q_value_exploratory: 0.037
runway_neutral_lift_exploratory: 1.29
tags: [kg/block/blocked, kg/dim/Dim1, kg/horizon/mid, kg/runway/exploratory, kg/status/exploratory, kg/type/factor]
---
# above_30pct_of_low · 距 52 週低點 ≥ 30%

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

距 52 週低點 ≥ 30%

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-23 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.14 | 22% | NOISE | NOISE | 0.037 |
| +30%/20d | 1.09 | 11% | NOISE | NOISE | 0.3032 |
| +40%/40d | 1.26 | 15% | WEAK | WEAK | 0.0011 |
| +50%/60d | 1.17 | 16% | WEAK | WEAK | 0.028 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

> 🔒 此 run 為 BLOCKED(探索性)—— 下方 runway 判讀僅供參考,不可作為可行動結論。

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| above_30pct_of_low | 1.14 | 1.29 |

> ✅ runway-independent — ATR-中性目標下 lift 仍 >1,是真訊號
