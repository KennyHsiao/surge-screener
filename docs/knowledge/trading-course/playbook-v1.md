# Trading Course Playbook Overlay V1

V1 將 Notion 課程內容接成 Options Cockpit 的交易前檢查 overlay。它不改原本
GO / WAIT / AVOID，不改 surge screener 權重，也不把課程規則直接當成模型信號。

## Severity Policy

| Severity | 用法 |
| --- | --- |
| `block` | 只用於平台原本硬風控或明確禁止策略，例如 cockpit AVOID、Risk Guard REDUCE/EXIT 新開多頭、財報在 DTE 內、Naked Call。 |
| `warn` | 課程 guardrail 或資料缺口，例如 DTE < 21、IV 偏高、IV proxy、Cycle 缺口、Jump 訊號未觸發。Warning 不直接封鎖交易。 |
| `info` | 顯示來源或補充說明，不影響 playbook。 |

`DTE < 21` 來自 Notion「至少 3 週 DTE」原則；平台原本 momentum-options 目標窗是 10-25 DTE，所以 V1 僅警示，不 block。

## V1 Playbooks

| Playbook | 強制條件 | Warning，不 block | 輸出行為 |
| --- | --- | --- | --- |
| Swing Long Call | 無平台 block；方向偏多；Cycle 為 Cycle1 / Cycle5 / Cycle6，或 Cycle 缺口但 cockpit 是 bullish GO。 | DTE < 21、IV 偏高、IV proxy、財報未知、Cycle 缺口、合約流動性/Payoff 缺口、Jump 未觸發。 | cockpit GO 顯示可執行；cockpit WAIT 顯示觀察。 |
| Jump Trade Long Call | Swing 趨勢成立；Bollinger 出現 1σ -> 2σ 加速段；價格未超過 2σ 過熱。 | DTE < 21、IV 偏高、加速資料不足、合約流動性/Payoff 缺口。 | 只有加速段成立才推薦 Jump；否則 fallback Swing / Wait。 |
| Bull Call Spread | 多頭 setup 成立；IV Rank / Percentile >= 60，或單買 Call 風險偏貴。 | DTE < 21、short leg 流動性不足、IV 仍可能壓縮利潤。 | 作為 Long Call 的降風險替代結構。 |
| Protective Put / Swing Hedge | 已有多頭持倉；Risk Guard WATCH / REDUCE / EXIT，或 Cycle 進入風險區。 | 成本、股數、hedge ratio 缺失；IV 偏高；DTE < 21。 | V1 只顯示 hedge-only 說明，不計算精準比例。 |
| Skip / Wait | cockpit AVOID、Naked Call、缺 ticker、財報在 DTE 內、Risk Guard REDUCE/EXIT 且沒有 hedge context。 | 只有型態、只有 RSI、趨勢未確認、資料缺口。 | block 才 Skip；只有 warning 時顯示 Wait。 |

## Source Mapping

- Swing / Cycle: Swing Trade, Cycle 1-6, multi-timeframe MACD.
- Jump: Jump Trade, Bollinger 1σ -> 2σ acceleration.
- Bull Call Spread: Options strategy library, IV high or premium too expensive.
- Hedge: Protective Put, Swing Hedge, risk-cycle protection.
- Guardrails: DTE >= 21, low IV preferred for long options, 1 ATR / 3 ATR risk framing, naked-call fail-closed.
