# 反轉雷達 因子校準 (per-signal forward lift)

- 產生時間: `2026-06-08T03:36:17.134215+00:00`
- lane: `reversal_radar.v1.structure+momentum_div+options_fear_receding+sector_improving+insider+analyst`
- 累積進場: **96** · 可結算: **0** (drop 1.0)
- 總體判讀: **PROVISIONAL — per-signal cells indicative only, below maturity** (每 tier 需 ≥100 結算才 MATURE)

> 探索性、非投資建議、**不自動調參**。每個 signal cell 需 ≥30 個已結算 fired 樣本才給判定;PREDICTIVE = fired 的 Wilson 下界 > 該 tier 基準命中率。
> 未持久化、無法在此歸因的訊號: structure.ma_reclaim / structure.snapback / momentum.rsi-band。

## +10%/20d  ·  結算 0 檔  ·  基準命中率 —  ·  [PROVISIONAL]

| signal | fired n | fired 命中率 (Wilson90) | not-fired 命中率 | lift | 判定 |
|---|---:|---|---:|---:|---|
| `structure.bb_squeeze` | 0 | — | — | — | INSUFFICIENT |
| `structure.rsi_40_65` | 0 | — | — | — | INSUFFICIENT |
| `structure.above_30pct_low` | 0 | — | — | — | INSUFFICIENT |
| `momentum.rsi_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_golden_10d` | 0 | — | — | — | INSUFFICIENT |
| `options.backwardation` | 0 | — | — | — | INSUFFICIENT |
| `options.put_skew>=0.10` | 0 | — | — | — | INSUFFICIENT |
| `options.cpr>=1.2` | 0 | — | — | — | INSUFFICIENT |
| `options.iv_pct>=70` | 0 | — | — | — | INSUFFICIENT |
| `sector.Improving` | 0 | — | — | — | INSUFFICIENT |
| `sector.rs_momentum>100` | 0 | — | — | — | INSUFFICIENT |
| `insider.buying` | 0 | — | — | — | INSUFFICIENT |
| `analyst.net_up_revisions>0` | 0 | — | — | — | INSUFFICIENT |
| `analyst.upside_pct>=25` | 0 | — | — | — | INSUFFICIENT |
| `tier>=TURNING` | 0 | — | — | — | INSUFFICIENT |
| `tier=REVERSAL` | 0 | — | — | — | INSUFFICIENT |

## +15%/40d  ·  結算 0 檔  ·  基準命中率 —  ·  [PROVISIONAL]

| signal | fired n | fired 命中率 (Wilson90) | not-fired 命中率 | lift | 判定 |
|---|---:|---|---:|---:|---|
| `structure.bb_squeeze` | 0 | — | — | — | INSUFFICIENT |
| `structure.rsi_40_65` | 0 | — | — | — | INSUFFICIENT |
| `structure.above_30pct_low` | 0 | — | — | — | INSUFFICIENT |
| `momentum.rsi_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_golden_10d` | 0 | — | — | — | INSUFFICIENT |
| `options.backwardation` | 0 | — | — | — | INSUFFICIENT |
| `options.put_skew>=0.10` | 0 | — | — | — | INSUFFICIENT |
| `options.cpr>=1.2` | 0 | — | — | — | INSUFFICIENT |
| `options.iv_pct>=70` | 0 | — | — | — | INSUFFICIENT |
| `sector.Improving` | 0 | — | — | — | INSUFFICIENT |
| `sector.rs_momentum>100` | 0 | — | — | — | INSUFFICIENT |
| `insider.buying` | 0 | — | — | — | INSUFFICIENT |
| `analyst.net_up_revisions>0` | 0 | — | — | — | INSUFFICIENT |
| `analyst.upside_pct>=25` | 0 | — | — | — | INSUFFICIENT |
| `tier>=TURNING` | 0 | — | — | — | INSUFFICIENT |
| `tier=REVERSAL` | 0 | — | — | — | INSUFFICIENT |

## +20%/60d  ·  結算 0 檔  ·  基準命中率 —  ·  [PROVISIONAL]

| signal | fired n | fired 命中率 (Wilson90) | not-fired 命中率 | lift | 判定 |
|---|---:|---|---:|---:|---|
| `structure.bb_squeeze` | 0 | — | — | — | INSUFFICIENT |
| `structure.rsi_40_65` | 0 | — | — | — | INSUFFICIENT |
| `structure.above_30pct_low` | 0 | — | — | — | INSUFFICIENT |
| `momentum.rsi_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_bull_div` | 0 | — | — | — | INSUFFICIENT |
| `momentum.macd_golden_10d` | 0 | — | — | — | INSUFFICIENT |
| `options.backwardation` | 0 | — | — | — | INSUFFICIENT |
| `options.put_skew>=0.10` | 0 | — | — | — | INSUFFICIENT |
| `options.cpr>=1.2` | 0 | — | — | — | INSUFFICIENT |
| `options.iv_pct>=70` | 0 | — | — | — | INSUFFICIENT |
| `sector.Improving` | 0 | — | — | — | INSUFFICIENT |
| `sector.rs_momentum>100` | 0 | — | — | — | INSUFFICIENT |
| `insider.buying` | 0 | — | — | — | INSUFFICIENT |
| `analyst.net_up_revisions>0` | 0 | — | — | — | INSUFFICIENT |
| `analyst.upside_pct>=25` | 0 | — | — | — | INSUFFICIENT |
| `tier>=TURNING` | 0 | — | — | — | INSUFFICIENT |
| `tier=REVERSAL` | 0 | — | — | — | INSUFFICIENT |

---
**如何使用**: 連續多月 PREDICTIVE 的訊號 → 在 reversal_radar.py 加重;持續 NOISE(lift≤0)→ 降權或移除門檻。改任何規則就 bump `REVERSAL_LANE_ID`,讓 forward / 本表從新版重新累積。