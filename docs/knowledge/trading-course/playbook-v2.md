# Playbook V2 Candidate Strategy Gates

Playbook V2 does not add new recommendations directly. It documents which
course strategies can become platform playbooks later, and what evidence or
position data must exist before they can affect the cockpit.

## Current Recommendation Set

The engine still recommends only the V1 set:

1. Swing Long Call
2. Jump Trade Long Call
3. Bull Call Spread
4. Protective Put / Swing Hedge
5. Skip / Wait

## Candidate Playbooks

| Candidate | Required data before activation | V2 status |
|---|---|---|
| Covered Call | Existing long stock position, lot quantity, resistance reference, non-earnings window | Documented only |
| Cash-Secured Sell Put | Cash or margin capability flag, max assignment size, OTM delta reference | Warning only; no recommendation |
| Bear Put Spread | Bearish direction, risk regime support, no conflict with existing long-only thesis | Documented only |
| Elastic Trade | Validated `%B` continuation and Bollinger persistence logic | Blocked pending validation |
| Stock Repair | Cost basis, lot quantity, unrealized loss, option chain liquidity | Blocked pending portfolio model |

## Activation Rules

- A new playbook must have explicit entry, warning, block, and validation factor IDs.
- Holding-dependent playbooks must stay blocked until position data is available.
- Margin-dependent playbooks must stay blocked until account capability is represented.
- Any high-risk undefined-loss structure stays blocked by default.
- Course guardrails remain warnings unless the platform risk model marks them unsafe.

## Validation Path

1. Record V1 and V2 candidate decisions in the Playbook Decision Ledger.
2. Run `scripts/playbook_validation.py` through Data Health refresh.
3. Keep results in `累積中` or `探索性` until the minimum resolved sample threshold is met.
4. Only mature evidence can become `驗證支持`; it must not override `GO / WAIT / AVOID`.
