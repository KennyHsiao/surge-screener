---
id: rvol_ge_2
node_type: factor
dimension: Dim1
subfactor: 1b Volume
horizon: short
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
verdict_raw: WEAK
exploratory_on: 2026-06-06
lift_exploratory: 1.38
precision_exploratory: 0.261
q_value_exploratory: 0.0125
runway_neutral_lift_exploratory: 0.66
---
# rvol_ge_2 · 相對量能 ≥ 2×

**維度** [[Dim1]] · **子因子** 1b Volume · **持有視窗** short(數日~2週)

相對量能 ≥ 2×

## 假說 / 文獻依據
- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)

## 驗證紀錄
_最後同步 2026-06-08 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 1.38 | 26% | WEAK | WEAK | 0.0125 |
| +30%/20d | 1.40 | 14% | NOISE | NOISE | 0.0603 |
| +40%/40d | 1.17 | 14% | NOISE | NOISE | 0.3805 |
| +50%/60d | 1.45 | 19% | WEAK | WEAK | 0.0119 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

> 🔒 此 run 為 BLOCKED(探索性)—— 下方 runway 判讀僅供參考,不可作為可行動結論。

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| rvol_ge_2 | 1.38 | 0.66 |

> ⚠️ 大半是 runway 假象 — ATR-中性下 lift 跌破 1,原本的正向 lift 主要來自『便宜股容易達 +X%』
