# Social Ticker Provenance and Outcome Eligibility Plan

## Document Info

| Field | Value |
|---|---|
| Version | v0.4 |
| Status | Release verified on 2026-08-20 |
| Date | 2026-08-19 |
| Trigger | 7F Data Health fetched English words such as `THAT`, `TO`, and `WHY` as securities |

## Goal

Stop unverified uppercase prose from entering new social-intelligence snapshots or
triggering repeated market-data requests, while retaining legitimate cashtags,
independently verified symbols, and already price-verified legacy outcomes.

## Scope

- Record whether Agent Reach found an explicit cashtag or an unprefixed uppercase token.
- Accept unprefixed Agent Reach tokens only when they occur in the accumulated local US
  universe; accept explicit cashtags with their provenance intact.
- Parse successful tweet content from stdout only, not diagnostic stderr.
- Preserve ticker evidence in social-intelligence snapshots.
- Before loading prices for a snapshot row, require market-identity evidence from local
  universe membership, independent platform validation, or a previously positive
  market-data entry price. Cashtag or curated-mention provenance alone is insufficient.
- Record bounded skipped-ticker evidence and counts instead of silently dropping rows.

Out of scope:

- rewriting historical social-intelligence source snapshots;
- manufacturing or backfilling picks;
- changing scoring weights, thresholds, DD rules, or ledger semantics;
- treating a failed quote request as proof that a symbol can never be valid.

## Requirements

- `REQ-STC-001`: prose-only uppercase tokens outside the local universe MUST NOT enter a
  new Agent Reach ticker payload.
- `REQ-STC-002`: explicit cashtags MUST retain explicit provenance through the social
  snapshot.
- `REQ-STC-003`: diagnostic stderr MUST NOT be scanned for tickers.
- `REQ-STC-004`: legacy rows without independent symbol evidence MUST NOT call the price
  loader repeatedly.
- `REQ-STC-005`: a legacy row with a prior positive entry price MUST remain eligible.
- `REQ-STC-006`: skipped rows MUST be observable through bounded reasoned evidence and
  aggregate counts.
- `REQ-STC-007`: an explicit cashtag without independent market-identity evidence MUST
  remain visible in the source snapshot but MUST NOT call the outcome price loader.

## Affected Files

- `scripts/social_ticker_contract.py` (shared pure provenance and eligibility rules)
- `scripts/agent_reach_social_bridge.py`
- `scripts/social_intelligence.py`
- `scripts/social_intelligence_outcomes.py`
- `scripts/test_agent_reach_social_bridge.py`
- `scripts/test_social_intelligence.py`
- `scripts/test_social_intelligence_outcomes.py`
- relevant project/review journals

## Verification

1. Add fail-first tests for prose tokens, stderr-only tokens, provenance propagation,
   legacy unverified skip, prior-price retention, and bounded skip receipts.
2. Run the three focused social-intelligence test files.
3. Run deploy artifact checks, compile checks, `git diff --check`, and the complete suite.
4. Review the diff for scope drift and data-loss behavior.
5. PR, merge, deploy, verify 7F hashes/services, and rerun Data Health.
6. Confirm invalid prose no longer produces quote requests and Analytics remains
   72 PASS / 2 WARN / 0 BLOCK (or investigate any changed count before acceptance).

## Risks and Rollback

- False negatives for off-universe unprefixed symbols: require an explicit cashtag or an
  independent validation source; never guess from prose.
- Historical legitimate off-universe rows: retain them when a prior outcome already has
  a positive market-data entry price.
- Universe staleness: union dated local universe snapshots, rather than relying only on
  the latest partially covered refresh.
- Rollback is a code revert; source snapshots and the performance ledger are not mutated.

## Blocker Review

- User intent and non-fabrication boundary: PASS.
- Affected files and verification commands are known: PASS.
- Historical source snapshots remain immutable: PASS.
- Existing market-verified legacy outcomes have an explicit retention path: PASS.
- Unknown symbols fail closed with observable evidence: PASS.
- Unresolved blocking issues: none.

## Post-implementation Review

- Resolved: relying on a static uppercase-word blocklist admitted new prose and
  excluded legitimate word-like tickers. Unprefixed tokens now require accumulated
  local-universe membership; explicit cashtags retain separate provenance.
- Resolved: successful command stderr was previously scanned as tweet content. Only
  stdout can now produce tickers or citations.
- Resolved: a transient quote failure could erase a prior positive entry price and
  make a legitimate off-universe legacy row permanently ineligible. The exact prior
  outcome is now retained with an explicit unavailable status.
- Review amendment: 7F proved that explicit cashtags can still name non-US or
  provider-incompatible symbols (`SHKY`, `IQE`, `LPK`, `SIVE`, `VIX`). Cashtag
  provenance remains useful discovery evidence but is no longer sufficient market
  identity for an outcome quote request.
- Actual diff remains within the accepted scope. No picks, scoring, ledger, API,
  database, credential, or schedule behavior changed.

## Release Verification

- PR #30 and the market-identity amendment PR #31 merged and deployed; final
  deployment run `32215547957` succeeded at `main@9e97408`.
- The final 7F Data Health run completed with 72 PASS / 2 WARN / 0 BLOCK.
- `SHKY`, `IQE`, `LPK`, `SIVE`, and `VIX` were retained as source provenance
  but skipped with `cashtag_unverified`; none reached the outcome price loader.
- All remaining quote warnings were provenance-resolved: `JNPR` and `CYBR`
  were absent from social snapshots, while `NSA` was a known-universe symbol.
- API and Streamlit remained healthy, and deployed contract/test hashes matched
  `origin/main`.

## Change History

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-19 | Accepted plan after blocker review. |
| v0.2 | 2026-08-19 | Implemented provenance/eligibility contract and closed the last-known-good review finding. |
| v0.3 | 2026-08-19 | Added fail-closed market-identity amendment after the first 7F post-fix run. |
| v0.4 | 2026-08-20 | Closed final deployment, 7F Data Health, skip-receipt, quote-provenance, and service-health gates. |
