---
id: rel_strength_vs_spy
node_type: factor
dimension: Dim5
subfactor: 5a Sector RS
horizon: mid
status: contrarian
lift: 0.61
precision: 0.134
verdict: CONTRARIAN
validated_on: 2026-06-06
sources: [jegadeesh-titman-1993-momentum, moskowitz-grinblatt-1999-industry-momentum]
verdict_mt: CONTRARIAN
q_value: 0.0
runway_neutral_lift: 0.91
runway_verdict: runway-artifact
---
# rel_strength_vs_spy · 20 日報酬 > SPY(相對強度,板塊代理)

**維度** [[Dim5]] · **子因子** 5a Sector RS · **持有視窗** mid(2週~3月)

20 日報酬 > SPY(相對強度,板塊代理)

## 假說 / 文獻依據
- [[jegadeesh-titman-1993-momentum]] — 動能因子的奠基論文:過去 3-12 月贏家持續贏。中期動能的學術源頭。
- [[moskowitz-grinblatt-1999-industry-momentum]] — 產業/板塊動能解釋了大半的個股動能 —— 對應 Dim5 板塊相對強度與熱錢輪動。

## 驗證紀錄
_最後同步 2026-06-07 · 來源 `sp500_pit · point-in-time`_

> 🔒 **探索性**:此 retro 仍受倖存者偏差封鎖,以下數字僅供造假說/方向參考,不可作為下注依據。可行動的驗證走 forward 樣本外測試。

| 門檻 | lift | 命中率(樣本內) | 判定 | 判定(FDR) | q |
|---|---|---|---|---|---|
| ALL | 0.61 | 13% | CONTRARIAN | CONTRARIAN | 0.0 |
| +30%/20d | 0.58 | 6% | CONTRARIAN | CONTRARIAN | 0.0 |
| +40%/40d | 0.58 | 8% | CONTRARIAN | CONTRARIAN | 0.0 |
| +50%/60d | 0.55 | 8% | CONTRARIAN | CONTRARIAN | 0.0 |

> 命中率受樣本暴漲:控制比例影響,**非真實基率**;跨因子比較請以 lift 為準。

## 相關
- 維度樞紐:[[Dim5]]

## Runway 中性檢定(ATR-normalized)
_來源 `sp500_pit` · 中性目標 = 前向漲幅 ≥ 8.1 ATR_

| 指標 | %-目標 lift | ATR-中性 lift |
|---|---|---|
| rel_strength_vs_spy | 0.61 | 0.91 |

> ⚠️ runway 假象 — ATR-中性下 lift≈1(無預測力),原判定是固定 %-漲幅的量測產物
