---
id: within_25pct_of_high
node_type: factor
dimension: Dim1
subfactor: 1a Trend
horizon: mid
status: contrarian
lift: 0.63
precision: 0.341
verdict: CONTRARIAN
validated_on: 2026-06-04
sources: [jegadeesh-titman-1993-momentum, george-hwang-2004-52week-high]
verdict_mt: CONTRARIAN
q_value: 0.0
---
# within_25pct_of_high · 距 52 週高點 ≤ 25%

**維度** [[Dim1]] · **子因子** 1a Trend · **持有視窗** mid(2週~3月)

距 52 週高點 ≤ 25%

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。
- [[george-hwang-2004-52week-high]] — 貼近 52 週高點本身就是動能訊號,且預測力強過傳統動能 —— 直接對應 within_25pct_of_high。

## 驗證紀錄
_最後同步 2026-06-04 · 來源 `factor_lift.json`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.63 | 34% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.55 | 19% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.59 | 22% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.62 | 23% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim1]]
