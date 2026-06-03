---
id: recent_8k_14d
node_type: factor
dimension: Dim2
subfactor: 2a 8-K
horizon: short
status: noise
lift: 0.91
precision: 0.428
verdict: NOISE
validated_on: 2026-06-04
sources: [bernard-thomas-1990-pead]
verdict_mt: NOISE
q_value: 1.0
---
# recent_8k_14d · 近 14 日內有 8-K 重大事件公告

**維度** [[Dim2]] · **子因子** 2a 8-K · **持有視窗** short(數日~2週)

近 14 日內有 8-K 重大事件公告

## 假說 / 文獻依據
- [[bernard-thomas-1990-pead]] — 盈餘公告後漂移 (PEAD):好消息後股價持續漂高數週。催化劑驅動短中線暴漲的學術核心。

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.91 | 43% | NOISE | NOISE | 1.0 |
| +30%/20d | 1.03 | 30% | NOISE | NOISE | 0.6072 |
| +40%/40d | 0.87 | 29% | CONTRARIAN | CONTRARIAN | 1.0 |
| +50%/60d | 0.88 | 30% | CONTRARIAN | CONTRARIAN | 1.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim2]]
