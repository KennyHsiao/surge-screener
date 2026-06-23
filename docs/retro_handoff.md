# 暴漲股復盤 · Retro Provenance / 因子驗證 — 交接文件

> **狀態快照**:2026-06-03 · 整理給接手端,讓其自行處理後續。
> **範圍**:`scripts/retro_*.py` + `ui/retro_analysis.py` + `config/retro_modules.json` + `surge_screener.yml` 的 retro 排程。
> **本文件為只讀分析產物,不含未討論的程式變更。**

---

## 一、源頭思路(要解決什麼)

評分器(七維 rubric)是**往前看**預測未來,但沒人知道它每個子因子**到底有沒有真實預測力**。這條工作把日篩選器**反過來跑**:

> 回頭找市場上「真的暴漲過」的股票(ground truth)→ 回到起漲前那一刻 → 量測哪些子因子當時真存在 → 判定每個因子是 `VALIDATED / WEAK / NOISE / CONTRARIAN` → 回饋校正權重與 prompt。

三句設計哲學:

1. **不是「贏家 vs 隨機日」,而是「like-with-like 硬負樣本」** — 對照組是同樣觸發 +7% 確認動作、但後來啞火沒爆發的 fizzler;`lift = P(因子|暴漲) / P(因子|對照)`,量的是「確認動能股裡的事前 edge」。
2. **量測點在確認日(observe_date)而非谷底(T0)** — 真實動能篩選器不會買在最低點,避免 look-ahead。
3. **全鏈共用同一套 lift 引擎**(`retro_factor_lift.compute_lift`,純 numpy、1000 次 bootstrap 90% CI) — 歷史腿/模組腿/前向腿三方一字不差,杜絕「換條較鬆統計讓結果好看」。

> **最大未解結構限制:survivorship bias** — 只取「當前」指數成分,已下市暴漲股 + 暴漲後才入選者全缺席。**不假裝解決**,寫進 caveats 並讓閘門預設封鎖。

---

## 二、方向(貫穿全鏈的設計原則)

1. **verified-data→AI 不臆測**:code 先抓可驗證歷史真值重建旗標,再把算好的 lift 餵 LLM;LLM 永不查價/猜數(反幻覺)。
2. **fail-closed 從嚴把關**:canonical 閘門 `retro_factor_lift.py:58 is_recommendations_blocked` — 三條件(`recommendations_blocked / low_confidence / sample_experiment`)**皆明確為 False** 才解鎖;缺值 / null / 不一致一律封鎖。報告端 `_sanitize_blocked` 連 LLM 真吐建議也清空 `proposed_changes`;UI 用 `is not False` 雙重封鎖。
3. **逐門檻(per-threshold)對照**:+30%/20d、+40%/40d、+50%/60d 各用**自己的 window** 判硬負樣本(第 40 天才到 +30% 不算 +30%/20d surge,故是該 tier 合法負樣本),control set 持久化到 `control_features.json.by_threshold`,讓單因子表與模組表用**完全相同的逐門檻 baseline**。
4. **來源溯源 provenance**:`control_features.json` 與 `factor_lift.json` 都帶 `source = {features_generated_at, events_generated_at, ...}`,下游用 `src.features_generated_at == feat.generated_at` 比對,拒絕把不同 surge run 的 stale / mismatched 對照配對。
5. **三態旗標(True / False / None)**:資料不足判 None 被 lift 引擎忽略,絕不把缺資料偽造成「不吻合」污染分母。
6. **範圍誠實**:只有 Dim1 技術 / Dim5 板塊能免費歷史回溯;Dim2 催化 / Dim4 機構靠 SEC EDGAR 免費回填;**Dim3 情緒 / Dim6 期權流沒有免費歷史**,只能靠 Phase-2 每日 append-only 快照累積 60–90 天後前向驗證。

---

## 三、已完成(端到端跑通)

- **Phase-1 歷史腿全鏈打通**:`label → reconstruct → edgar_backfill → factor_lift → modules → report`。`reports/retrospective/` 下 `factor_lift.json` / `control_features.json`(含 `by_threshold`)/ `module_lift.json` / `latest.json` 時間戳一致(2026-06-03)= 整鏈打通。
- **Stage A `retro_surge_label.py`**:逆運算日篩選器,一個物理漲勢 = 一筆事件(`thresholds_hit` 陣列、de-overlap 靠 `i = peak_idx+1`);實測 44 事件 / `{+30%/20d:19, +40%/40d:27, +50%/60d:30}`。
- **Stage B `retro_reconstruct.py`**:在 `observe_date`(確認日,非谷底)量 15 個 Dim1/Dim5 布林旗標,重用 live 引擎 `momentum_options._technical` 數學確保口徑一致;實測 44 列 / skipped 0;已多出 EDGAR 回填的 `recent_8k_14d` / `insider_buying_90d`。
- **Stage C `retro_factor_lift.py`**:like-with-like 硬負樣本、逐門檻 `by_threshold`、純 numpy 1000 次 bootstrap 90% CI、雙臂 verdict(`MIN_KNOWN=5` + CI 須整段同側)、canonical gate `is_recommendations_blocked`(L58)。
- **模組腿 `retro_modules.py`**:交易者原型(Minervini 延續 / 帶量突破 / 超賣反轉 / 健康動能軟 3-of-4 / 事件籌碼 EDGAR)降維成單一 boolean factor 塞回同一 `compute_lift`;三態 `module_match`、provenance 雙核對、fail-closed `gate_blocked`;`test_retro_modules.py` 覆蓋六種封鎖情境。
- **呈現層 `retro_report.py`(Stage D)+ `ui/retro_analysis.py`**:生產端 `_sanitize_blocked`(blocked 時清空建議)+ 呈現端 fail-closed banner;UI 模組分頁紅框正確。
- **排程已接線**(`.github/workflows/surge_screener.yml`):月度 `retrospective` job(cron / `workflow_dispatch manual_job=retrospective`)+ 每日 EOD Stage 6.6 `retro_snapshot.py` 產前向快照 + 每日 `verify_returns` 回填報酬。
- **schema 向後相容遷移完成**:`threshold → thresholds_hit`,producers / consumers / UI 全部容忍舊單數欄位(本 session 的 gate 修復鏈)。

---

## 四、還剩下什麼(交接重點,依優先序)

### 🔴 P0 — 不做就拿不到任何可用結論

| 項目 | 為什麼 | 在哪 |
|---|---|---|
| **把前向腿(Phase-2)真的跑起來累積快照** | `forward_snapshots.csv` / `forward_factor_lift.json` **本地皆不存在 = 0 筆**。Dim3 情緒 / Dim6 期權流**唯一**的驗證途徑;不開始累積 = 這兩維永遠卡在「累積中 0 筆」 | `retro_snapshot.py` + yml Stage 6.6(L216-224);產物 `reports/retrospective/forward_snapshots.csv` |
| **歷史腿跑成全宇宙 sp1500 滿掃** | 現在 `coverage_ratio = 0.027`(只掃 40/1500)→ 判 `sample_experiment`、`recommendations_blocked=True`,**現有因子驗證頁只是探索性、不可下結論**。⚠️ `coverage.intended_universe` 實際是 `None`,閘門分母可疑,先確認有正確帶入 | `retro_factor_lift.py` coverage_gate;CI 跑滿宇宙 |

### 🟠 P1 — 正確性 / 一致性清理

| 項目 | 為什麼 | 在哪 |
|---|---|---|
| 死碼 / 未落地:`min_pct`(算了沒用)、`fwd_max_gain`(存了沒進 lift) | 若原意是用來過濾「差一點就 surge」的邊界 control 以提升負樣本純度,**該意圖尚未實作**;否則應刪 | `retro_factor_lift.py` L330、L175-189 |
| 統一閘門:report 內聯重複的 gate 改呼叫 canonical | `retro_report.py` 已 import `is_recommendations_blocked` 但 L63-65 / L110-113 仍各自內聯重寫三條件;日後改 canonical 定義極易漏改 → 閘門不一致 | `retro_report.py` |
| UI 呈現**真實**封鎖原因 | UI 完全沒引用 `provenance_ok / control_match / partial-fallback`;封鎖有生效但使用者只看到泛用「樣本實驗」紅框 — 當 coverage 夠但對照過期 / 部分回退時,訊息與真因不符 | `ui/retro_analysis.py` `_modules_tab` / `_coverage_banner` |
| 修 ALL 列 `control_baseline` 誤標 | L157 硬編 `'threshold-specific'`,但 ALL 實際用頂層 `controls`(any-surge baseline),語意應標 `'all'`;下游只讀該欄會被誤導 | `retro_modules.py` L157 |
| config 校驗 | 不驗證 `retro_modules.json` 的 factors key 是否存在 → 打錯字該條恆 None、整個模組**靜默跳過無警告**;module 重名靜默覆蓋;`min_factors` 越界恆 True/False | `retro_modules.py` + `config/retro_modules.json` |

### 🟡 P2 — 韌性 / 基礎建設

| 項目 | 為什麼 | 在哪 |
|---|---|---|
| 資料抓取加快取 / 重試 / 失敗告警 | 全直接打 yfinance、無重試無快取;批次失敗只 print stderr 後 continue,`tickers_scanned` **悄悄縮水不報警**;control pool 對全宇宙逐檔重抓 → 規模化大量重複 + 可重現性差(網路抖動 → 不同次跑出不同事件集) | label / reconstruct / `_build_control_pool` / `rr._hist_auto_adjust_false` |
| schema 補關鍵參數 + 同源指紋 | `confirm_pct / max_offset` 沒回寫頂層(只在 `observation` 字串裡);兩階段各自 `generated_at`,沒記「features 基於哪個 events 檔(hash/時間)」→ 無法保證同源;三態 None 語意未文件化(下游當 False 會低估命中率) | `retro_reconstruct.py` / `retro_surge_label.py` 輸出 schema |

---

## 五、交接注意事項(坑,務必先讀)

- **Survivorship bias 是方法論硬限制不是 bug**:labeler 只取「當前」指數成分,已下市暴漲股 + 暴漲後才入選者全缺席,會系統性高估正向因子命中率。`survivorship_bias` 永遠 True 且預設封鎖;`--allow-survivorship-biased` 只是「承認偏誤」**不是「修偏誤」**;真修需 point-in-time 成分歷史(目前沒有)。所有 unblocked run 嚴格說仍非完全可行動證據。
- **非 point-in-time 成員 = 隱性 look-ahead**:即使解了下市問題,沒有歷史成分快照仍無法在 `surge_start` 當下用「那時的成員」掃描。
- **口徑陷阱**:`magnitude` 與 `surge_events.json` 的 `trough_price / peak_price` 是 `auto_adjust=True`(乾淨除權息),Stage B 重建特徵用 `auto_adjust=False`(對齊 live 引擎)— 刻意併用,但大除權 / 分割時價位口徑不一致,**別把 events 價位當「未調整實際成交價」**。
- **兩條腿 lift 口徑不等價**:Phase-1 歷史腿 = confirmation-trigger 硬負樣本;Phase-2 前向腿 = 同快照集內 surger vs 非 surger + cohort 中位數二值化(無倖存者偏差但定義不同)。**解讀結論必須分清是哪條腿產的**。
- **閘門縱深不足**:provenance 不符時 `retro_modules` 只印 WARNING 不 return,仍跑完整 lift 並把每個 tier 表的 `control_baseline` 標成 `threshold-specific`,只有頂層 gate 反映封鎖。**一律以頂層 canonical gate / `recommendations_blocked` 為準**,別只看個別表的 `control_baseline`。
- **時間缺口**:`retro_forward_lift` 預設 `--min-age-days 60`、需 ≥10 筆可解析快照才跑(<10 只寫 accumulating stub),`low_confidence` 門檻 `surgers < 20`。從今天起每日快照,**到「有前向結論」最少還差數個月**。前向腿 provider 是 yfinance,歷史腿 verify 用 polygon。
- **可重現性脆弱**:`factor_lift` 同一個 `rng`(SEED=42)依序餵多張表 / 多因子的 bootstrap → 整體可重現,但每張表 / 因子的 CI 非獨立子流;日後改 factor 數量或表順序,所有後續 CI 會位移,難以對 diff。
- `_factor_breakdown` 永遠用全體 surgers(非該門檻子集),UI「暴漲前達成率」固定是 ALL 集合的數字,與 radio 選的門檻不一致(易誤讀)。
- **效能**:`_ema` 用純 Python for 迴圈逐點遞迴,規模化(russell3000)時是效能風險(非正確性問題)。

---

## 附:關鍵檔案地圖

| 角色 | 檔案 |
|---|---|
| Stage A 事件標記 | `scripts/retro_surge_label.py` → `reports/retrospective/surge_events.json` |
| Stage B 旗標重建 | `scripts/retro_reconstruct.py` → `surge_features.json`(重用 `scripts/momentum_options.py`) |
| Stage C 因子 lift + 對照組 + provenance | `scripts/retro_factor_lift.py` → `factor_lift.json` / `control_features.json`;canonical gate `is_recommendations_blocked`(L58) |
| 模組驗證 | `scripts/retro_modules.py` + `config/retro_modules.json` → `module_lift.json`;測試 `test_retro_modules.py` |
| 前向驗證(Phase-2) | `scripts/retro_snapshot.py`(每日快照)+ retro_forward_lift → `forward_snapshots.csv` / `forward_factor_lift.json` |
| 呈現層 | `scripts/retro_report.py`(LLM 報告)+ `ui/retro_analysis.py`(儀表板)→ `latest.json` / `*_retro.md` |
| 排程 | `.github/workflows/surge_screener.yml`(月度 retrospective + 每日 Stage 6.6 快照 + 每日 verify_returns) |
