# Codex SDK LLM Migration Plan

## Document Info

| Field | Value |
| --- | --- |
| Status | Implemented; focused verification complete |
| Branch | `main` |
| Strategy | Branch by Abstraction |
| SDK baseline | `openai-codex 0.144.4` |
| Authentication | Existing Codex ChatGPT login only |

## Goal

Route every runtime LLM operation through the official Codex Python SDK and the
signed-in ChatGPT subscription entitlement. Remove Anthropic, Claude Agent SDK,
OpenAI API-key, and DeepSeek execution paths from the platform. Preserve the
existing business-facing `LLMClient.chat()` contract so prompts, parsers, scoring,
reporting, and storage behavior do not need a risky rewrite.

## Current State and Scope

The shared `scripts/llm_client.py` adapter is used by the screener, controller,
deep due diligence, report builder, self-reflection, retrospective, COT report,
theme/sector analysis, fundamentals, knowledge ingestion, social summaries,
X analysis, and Streamlit AI chat. The repository also contains:

- Claude-specific login/resume helpers and three Streamlit authentication UIs.
- A direct xAI/Grok developer-API call for X influencer research.
- CLI provider choices and Claude model defaults in runtime scripts and Makefile.
- GitHub Actions LLM jobs that inject paid API keys and run on ephemeral runners.
- Docker, systemd, and deployment setup that installs and persists Claude CLI.
- Contract tests and user documentation that enforce the old behavior.

## Architecture Decision

Keep `LLMClient` as the compatibility boundary and replace all backends with one
`codex` provider:

- `LLMClient.chat()` starts an ephemeral Codex thread with the existing system
  prompt as developer instructions, read-only sandboxing, denied approval
  escalation, web search disabled, and shell/hooks/apps/remote-plugin/multi-agent
  features disabled.
- `LLMClient.chat_agentic()` uses the same Codex SDK boundary with cached web
  search enabled, while keeping shell execution disabled and filesystem
  read-only.
- Both paths run from an isolated temporary working directory so repository
  instructions and files are not part of the LLM component's context.
- Model selection is optional. When no `CODEX_MODEL` or explicit `--model` is
  supplied, the signed-in Codex account's configured default is used. No guessed
  model name is hard-coded.
- Authentication preflight calls the SDK account endpoint and accepts only a
  ChatGPT account. API-key authentication is rejected so usage cannot silently
  switch to metered Platform billing.
- The server login flow uses `codex login --device-auth`; its persisted
  `CODEX_HOME` is shared by the SDK.

## Implementation Tasks

1. Replace `scripts/llm_client.py` with the Codex SDK adapter, typed errors,
   retry behavior, output caps, subscription-only account validation, and
   injectable SDK factories for offline tests.
2. Rename the Claude auth helper/test to Codex equivalents and update candidate,
   COT, social-summary, and UI resume flows.
3. Change every LLM CLI provider choice and default model to Codex/default;
   update Makefile and runtime labels without changing deterministic jobs.
4. Replace old dependencies with `openai-codex`, persist `CODEX_HOME`, remove the
   Claude/Node install path, and update Docker/systemd/deploy contracts.
5. Move only GitHub Actions jobs that actually call LLMs to the existing trusted
   self-hosted runner and remove LLM API-key injection/provider flags. Keep
   deterministic jobs on GitHub-hosted runners.
6. Update focused tests, deployment contracts, static repository scans, and user
   documentation.
7. Replace the remaining xAI/Grok X-influencer and sentiment POC calls with
   Codex SDK web research; retain Agent Reach and X API only as data sources.
8. Keep application deployment separate from source/Analytics recomputation.
   Long refreshes remain explicit opt-ins or scheduled data-service work, and
   remove the redundant deploy schedule because report pushes already deploy.

## Verification

- Offline unit tests for Codex account validation, prompt/thread options,
  output caps, retries, agentic web configuration, and login state transitions.
- Existing chat, candidate-control, dashboard, deployment, Docker, LLM scoring,
  social-summary, COT, and workflow contract tests.
- `compileall` for changed Python modules and shell syntax checks for deployment
  scripts.
- Repository scan proving no runtime Anthropic/Claude/OpenAI/DeepSeek LLM backend,
  provider choice, model default, or paid LLM API-key injection remains.
- A minimal authenticated Codex SDK smoke call using the current ChatGPT login.
- GitHub Actions run-timing review proving the former deploy delay came from
  source/Analytics refresh work, then deployment contracts proving both are
  skipped by default and time-bounded when explicitly enabled.

## Risk and Rollback

- A ChatGPT subscription has usage limits and is unsuitable for unbounded batch
  fan-out. Existing candidate limits, retries, delays, and resume behavior remain
  in place.
- GitHub-hosted runners cannot safely reuse a local ChatGPT session; LLM jobs
  therefore require the trusted self-hosted runner to have completed
  `codex login --device-auth`.
- Codex is an agent runtime, not a token-completion API. Read-only sandboxing,
  denied escalation, disabled web search for ordinary calls, ephemeral threads,
  and explicit no-tool instructions minimize side effects.
- Rollback is localized to the compatibility adapter, auth helper, and runtime
  configuration. Business data formats and deterministic scoring code are not
  migrated.

## Blocking Review

Review 1 found no unresolved blocker:

- The requested branch is active.
- The installed Python version satisfies the SDK.
- The official wheel and exact API signatures were inspected.
- Existing overlapping user edits can be preserved with targeted patches.
- A trusted self-hosted runner already exists for subscription-authenticated
  scheduled work.

Review 2 found and resolved two runtime-only issues:

- Official runtime validation rejected the mock-tested `agents.enabled` thread
  object. The implementation now uses supported feature flags and a real SDK
  smoke call verifies the thread configuration.
- The X influencer radar still called xAI directly. The inventory was expanded
  and that final LLM path now uses the same Codex adapter.

The deploy timing audit of Actions run `30504645386` showed checkout took about
four seconds and dependency handling about thirteen seconds; source refresh then
ran for five minutes before timing out, followed by an Analytics rebuild that ran
about 18.5 minutes and exited 137. Deployment now skips those data jobs by
default and preserves the last good Analytics DB.

## Verification Results

- The authenticated SDK preflight recognized a ChatGPT subscription account
  (`prolite`), and real ordinary-chat plus web-research smoke calls completed.
- Focused migration, UI, Docker, deployment, candidate, scoring, social, and
  storage suites passed 216 checks in total.
- The final focused rerun passed Codex adapter 7/7, Codex X research 2/2, and
  Agent Reach credential-isolation 8/8.
- Python compilation, deploy shell syntax, all workflow YAML parsing,
  Makefile dry runs, repository provider scans, and `git diff --check` passed.
- `scripts/test_ui_ux_contract.py` remains a known separate UX-1B lifecycle
  gate: its pending frozen baseline intentionally asserts the pre-migration
  `requirements.txt` and authentication UI byte hashes. It cannot pass while
  accepting this SDK migration, so its user-owned baseline/evidence was left
  untouched for the existing Sequence-20 prerequisite work.

The implementation matches the accepted scope. The publication commit contains
only the Codex migration, its focused tests/documentation, and the deploy-speed
changes; unrelated API/UX work remains outside the staged diff in the existing
dirty `main` worktree.
