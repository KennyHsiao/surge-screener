# Industry Role Review Design

## Goal

Add platform-operated industry-chain role classification so tickers can be grouped by current supply-chain role, reviewed in the UI, and reused by the 交易狀態 page without manually editing JSON.

## Product Answer

Yes: suggestions and approvals should happen inside the platform. The user should not need to edit `content/theme_baskets.json`, `content/themes.json`, or future role-map files by hand for normal workflow.

The platform will show AI/system suggestions in a review queue. The user can accept, reject, edit, or defer each suggestion. Only approved classifications are used as stable labels in trading pages.

## Scope

This design adds a first version of an industry-chain role system focused on US equities and AI/semiconductor/robotics-style role mapping.

In scope:

- A curated role taxonomy with stable role ids, names, descriptions, examples, and parent themes.
- A role classification engine that merges existing evidence from `theme_baskets.json`, ranked candidates, risk artifacts, watchlists, and optional LLM classifications.
- A review artifact for suggested changes.
- A Streamlit review page where the user can approve, reject, edit, or defer suggestions.
- Integration into `交易狀態` so rows can show approved industry-chain roles.

Out of scope for v1:

- Fully autonomous taxonomy mutation.
- Automatic overwriting of `theme_baskets.json`.
- Paid data feeds.
- Real-time web crawling.
- Treating social mentions as authoritative classification.

## Classification Principles

The system separates three concepts:

- `role`: what the company does in the supply chain, such as `HBM / Memory`, `AI Server / ODM`, or `Semi Equipment`.
- `theme`: broader investment theme, such as `AI infrastructure` or `Physical AI`.
- `social_heat`: which tickers or roles are being discussed right now.

Social data can raise review priority, but it must not directly approve classifications.

## Data Files

### `content/industry_roles.json`

Curated taxonomy. Example shape:

```json
{
  "version": 1,
  "roles": {
    "hbm_memory": {
      "name": "HBM / Memory",
      "parent_theme": "AI infrastructure",
      "desc": "HBM, DRAM, NAND, storage and memory bottleneck exposure",
      "examples": ["MU", "WDC", "STX"],
      "keywords": ["HBM", "DRAM", "NAND", "memory", "storage"]
    }
  }
}
```

### `content/industry_role_overrides.json`

Approved user decisions. This is the authoritative role map used by trading pages.

```json
{
  "version": 1,
  "tickers": {
    "MU": {
      "primary_role": "hbm_memory",
      "secondary_roles": ["dram_nand"],
      "confidence": 0.95,
      "reviewed_at": "2026-07-01T12:00:00Z",
      "reviewed_by": "platform"
    }
  }
}
```

### `reports/industry_role_suggestions.json`

Generated suggestions and review queue.

```json
{
  "generated_at": "2026-07-01T12:00:00Z",
  "suggestions": [
    {
      "ticker": "DELL",
      "suggested_primary_role": "ai_server_odm",
      "suggested_secondary_roles": ["datacenter_infrastructure"],
      "confidence": 0.84,
      "evidence": [
        "theme_baskets: AI 伺服器 / ODM",
        "company_profile: servers and infrastructure",
        "social_heat: mentioned in AI infra cluster"
      ],
      "status": "suggested"
    }
  ]
}
```

## Engine Behavior

The role engine ranks evidence in this order:

1. User-approved override from `industry_role_overrides.json`.
2. Exact membership in `content/theme_baskets.json`.
3. Existing sector/industry hints from `sector_free`.
4. Optional LLM result constrained to `industry_roles.json` role ids.
5. Social mentions as priority and freshness only.

The engine returns:

- `primary_role`
- `secondary_roles`
- `confidence`
- `source`: `approved`, `suggested`, or `unclassified`
- `evidence`

Trading pages should show approved roles first. Suggested roles can be shown only with an explicit `待審核` label.

## Review Page

Add a page named `產業鏈分類` under `資料維護`.

The page has three surfaces:

1. Summary cards:
   - pending suggestions
   - approved tickers
   - low-confidence suggestions
   - stale approved roles

2. Review table:
   - ticker
   - current approved role
   - suggested primary role
   - confidence
   - evidence
   - action buttons: approve, reject, edit, defer

3. Approved role map:
   - search by ticker or role
   - filter by parent theme
   - show tickers grouped by role

Actions are local file writes only. No orders, no broker actions, no external mutation.

## Trading Page Integration

`交易狀態` should add a compact column:

```text
產業鏈角色
```

Each row displays the approved primary role, such as:

```text
AI Server / ODM
HBM / Memory
Semi Equipment
Physical AI / Robotics
```

If only a suggestion exists, display:

```text
待審核: AI Server / ODM
```

If no role exists:

```text
未分類
```

## UX Rules

- Review actions must be explicit buttons.
- The page should not require JSON editing.
- Evidence must be visible before approval.
- Suggested changes must not silently affect approved role labels.
- The interface should be dense and table-first, matching an operational trading tool rather than a marketing page.

## Testing

Add self-contained script tests for:

- taxonomy loading
- deterministic role suggestion from `theme_baskets.json`
- approved override precedence over suggestions
- review action persistence
- `交易狀態` rows include role labels
- navigation contains the new review page

## Risks

- LLM classifications can drift. Mitigation: constrain to known role ids and require review for changes.
- Taxonomy can become stale. Mitigation: role suggestions can include `new_role_candidate` evidence but must not auto-create roles.
- Social heat can bias classifications. Mitigation: social evidence changes priority only, not final role assignment.
