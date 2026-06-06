---
id: material_8k_14d
node_type: factor
dimension: Dim2
subfactor: 2a 8-K
horizon: short
status: contrarian
lift: 0.7
precision: 0.153
verdict: CONTRARIAN
validated_on: 2026-06-07
sources: [bernard-thomas-1990-pead]
verdict_mt: CONTRARIAN
q_value: 0.0002
---
# material_8k_14d · 近 14 日內有『材料型』8-K(併購/財報/重大協議/Reg FD/重大事件;排除常規如高管異動、附件)

**維度** [[Dim2]] · **子因子** 2a 8-K · **持有視窗** short(數日~2週)

近 14 日內有『材料型』8-K(併購/財報/重大協議/Reg FD/重大事件;排除常規如高管異動、附件)

## 假說 / 文獻依據
- [[bernard-thomas-1990-pead]] — 盈餘公告後漂移 (PEAD):好消息後股價持續漂高數週。催化劑驅動短中線暴漲的學術核心。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.70 | 15% | CONTRARIAN | CONTRARIAN | 0.0002 |
| +30%/20d | 0.72 | 8% | CONTRARIAN | CONTRARIAN | 0.0088 |
| +40%/40d | 0.61 | 8% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.65 | 10% | CONTRARIAN | CONTRARIAN | 0.0002 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim2]]
