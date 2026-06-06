---
id: recent_8k_14d
node_type: factor
dimension: Dim2
subfactor: 2a 8-K
horizon: short
status: contrarian
lift: 0.84
precision: 0.177
verdict: CONTRARIAN
validated_on: 2026-06-07
sources: [bernard-thomas-1990-pead]
verdict_mt: CONTRARIAN
q_value: 0.0216
---
# recent_8k_14d · 近 14 日內有 8-K 重大事件公告

**維度** [[Dim2]] · **子因子** 2a 8-K · **持有視窗** short(數日~2週)

近 14 日內有 8-K 重大事件公告

## 假說 / 文獻依據
- [[bernard-thomas-1990-pead]] — 盈餘公告後漂移 (PEAD):好消息後股價持續漂高數週。催化劑驅動短中線暴漲的學術核心。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.84 | 18% | CONTRARIAN | CONTRARIAN | 0.0216 |
| +30%/20d | 0.93 | 10% | NOISE | NOISE | 0.4753 |
| +40%/40d | 0.75 | 10% | CONTRARIAN | CONTRARIAN | 0.0041 |
| +50%/60d | 0.78 | 11% | CONTRARIAN | CONTRARIAN | 0.0082 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim2]]
