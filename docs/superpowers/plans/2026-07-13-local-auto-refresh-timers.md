# Local Auto-Refresh Timers Implementation Plan

**Goal:** Ensure the test server refreshes every unattended-safe dataset automatically without depending on a user opening a page or pressing a refresh button.

**Root cause:** The deployed server has no user-level systemd timers. GitHub Actions contains schedule declarations, but the application host itself only runs the Streamlit service. Theme Flow and Data Health status files therefore advance only after a UI/manual launch, and candidate refresh delivery depends on a delayed external schedule plus a follow-up deploy.

**Architecture:** Install three user-level systemd oneshot services and persistent timers on the test server. Use explicit `Asia/Taipei` calendar expressions, serialize each job by systemd unit identity, retain the candidate pipeline's process lock, and stagger post-close source/health work before Theme Flow. The deploy script owns unit installation and activation so every release repairs missing or disabled timers.

## Schedule Contract

| Job | Local schedule | Purpose | Overlap policy |
| --- | --- | --- | --- |
| Candidate full refresh | Monday-Friday 20:30 Asia/Taipei | Premarket hard filter, ranking, options gate, source artifacts, Analytics checks | Skip duplicate start while the oneshot unit is active; pipeline file lock also blocks UI overlap |
| Data Health | Tuesday-Saturday 06:15 Asia/Taipei | Post-close core sources plus fundamentals, sector rotation, social intelligence/outcomes, IV history, Risk Guard, Analytics DB and checks | Skip duplicate start while the oneshot unit is active |
| Theme Flow | Tuesday-Saturday 07:45 Asia/Taipei | Refresh Theme Flow capital snapshot after the expanded Data Health run | Skip duplicate start while the oneshot unit is active |

All timers use `Persistent=true`, so a powered-off server catches up the last missed calendar event when its user manager returns. Calendar evaluation uses the IANA timezone `Asia/Taipei`; Taiwan has no DST transition, while the 06:15 post-close schedule remains after both US daylight and standard-time closes.

## Refresh Inventory

| Dataset | Decision | Reason |
| --- | --- | --- |
| Candidate hard filter/ranking/options gate | Local timer | Deterministic and required before opening Today Decision |
| Universe, daily bars, money flow, trade state, industry roles | Data Health timer | Existing unattended-safe core source refresh |
| Fundamental metrics for current top candidates | Data Health timer | Missing on server; free/official sources and bounded to top 10 |
| Sector rotation verified snapshot | Data Health timer | Stale since 2026-07-01; deterministic, no paid LLM needed |
| Social intelligence and forward outcomes | Data Health timer | Stale since 2026-07-09; free-first path degrades cleanly without paid APIs |
| ATM IV history for current top candidates | Data Health timer | Time-series value depends on daily accumulation |
| Risk Guard for watchlist/current candidates | Data Health timer | Stale since 2026-06-30; deterministic and read-only |
| Theme Flow capital snapshot | Dedicated local timer | Required market-context page; run after core money-flow refresh |
| Options flow, reversal radar, oversold lane, candidate outcomes, return verification, crypto, COT, reports/retrospectives | Existing GitHub timers | Already automated with canonical writers and some notification side effects; duplicating locally would create conflicting output/alerts |
| IBKR reconciliation | Human-gated | Requires a live authenticated Gateway/TWS session |
| Paid LLM sector/theme/fundamental narratives | Human-gated | Cost-bearing interpretation, not source-data freshness |
| Strategy approvals, role approvals, influencer roster edits | Human-gated | Governance/mutation actions, not data ingestion |

## Files

- Create `deploy/surge-candidate-refresh.service` and `.timer`.
- Create `deploy/surge-data-health-refresh.service` and `.timer`.
- Create `deploy/surge-theme-flow-refresh.service` and `.timer`.
- Modify `scripts/deploy_test_server.sh` to install, enable, and validate all timer units.
- Modify `scripts/data_source_refresh.py` to optionally run the bounded unattended supplemental refresh stages before rebuilding Analytics.
- Modify `scripts/social_intelligence.py` and `scripts/snapshot_iv.py` to expose reusable refresh functions for the scheduled orchestrator.
- Modify `ui/_candidate_controls.py` to use a one-hour stale threshold, matching observed full-refresh duration.
- Modify `ui/_shared.py` and `ui/risk_guard.py` so the sector and Risk Guard pages read scheduled snapshots immediately on open.
- Modify `scripts/test_deploy_artifacts.py` to assert unit commands, timezone, persistence, activation, and timer verification.
- Modify `scripts/test_candidate_controls_view.py` to cover the longer-running Analytics stage.
- Modify `content/schedules.json` so the platform schedule registry includes local Theme Flow and expanded Data Health jobs.
- Modify `ui/sys_schedules.py` so those schedules render their real persisted results and the page no longer describes the registry as proposal-only.
- Modify `.agents/PROJECT.md` to record the production scheduling decision.

## Verification

1. Run `scripts/test_deploy_artifacts.py`.
2. Run `scripts/test_candidate_controls_view.py`.
3. Run candidate pipeline control, Theme Flow background, Data Health refresh, and Docker runtime contract tests.
4. Run `bash -n scripts/deploy_test_server.sh` and parse every new unit with `systemd-analyze verify` when available.
5. Review `git diff --check` and the scoped diff against this plan.
6. Deploy through the existing test-server path, then verify `systemctl --user list-timers --all`, each timer's enabled/active state, and the Streamlit health endpoint.

## Risk Review

- **Provider rate limits:** Expanded post-close Data Health and Theme Flow are separated by 90 minutes. Candidate refresh remains on the existing premarket cadence. Supplemental fundamental/IV work is bounded to the top 10 candidates.
- **Concurrent manual runs:** Candidate refresh retains its cross-process lock. systemd prevents two instances of the same scheduled service. Manual Data Health and Theme Flow launches remain uncommon and their status files expose any collision; adding a shared cross-entry lock is outside this scoped deployment fix unless testing demonstrates overlap.
- **Long-running status:** The observed candidate refresh completed in about 40 minutes but was marked failed after 10 minutes without a status write during the Analytics phase. Raising the UI interruption threshold to one hour removes the false terminal state while still detecting abandoned runs.
- **Initial activation:** Enabling persistent timers does not run all three heavy jobs concurrently. Deployment verifies installation; the normal calendar cadence takes over immediately, and a controlled one-time refresh can be started after deployment verification.

## Plan Review

- Covers the original three paths and the expanded unattended-safe data inventory: yes.
- Affected files and ownership boundaries known: yes.
- Verification steps known: yes.
- Blocking issues: none.
