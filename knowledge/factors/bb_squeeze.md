---
id: bb_squeeze
node_type: factor
dimension: Dim1
subfactor: 1c Pattern
horizon: short
status: exploratory
lift: 1.63
precision: 0.293
verdict: EXPLORATORY
validated_on: 
sources: []
verdict_mt: EXPLORATORY
q_value: 0.0008
runway_neutral_lift: 1.78
runway_verdict: exploratory
runway_blocked: True
blocked: True
verdict_raw: VALIDATED
exploratory_on: 2026-06-06
---
# bb_squeeze · 布林帶擠壓(整理基底)

**維度** [[Dim1]] · **子因子** 1c Pattern · **持有視窗** short(數日~2週)

布林帶擠壓(整理基底)

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-08 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.63 | 29% | VALIDATED | VALIDATED | 0.0008 |
| +30%/20d | 1.40 | 14% | NOISE | NOISE | 0.113 |
| +40%/40d | 1.53 | 18% | VALIDATED | VALIDATED | 0.0175 |
| +50%/60d | 1.58 | 21% | VALIDATED | VALIDATED | 0.0079 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

> 🔒 此 run 為 BLOCKED(探索性)—— 下方 runway 判讀僅供參考,不可作為可行動結論。

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| bb_squeeze | 1.63 | 1.78 |

> ✅ runway-independent — ATR-中性目標下 lift 仍 >1,是真訊號
