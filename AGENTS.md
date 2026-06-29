# AGENTS.md

## Workflow Policy

Use Superpowers skills when they apply. Do not duplicate their full procedures here.

For multi-step planning:
- Use `superpowers:writing-plans` when creating a written implementation plan.
- Before implementation, review the plan for blocking issues.
- Blocking issues must be resolved before execution.
- If the same blocker remains after 3 review iterations, stop and report it.

For executing an existing plan:
- Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when applicable.
- Follow the accepted plan unless a concrete reason requires divergence.

## Local Gates

Before implementation:
- Confirm the accepted plan covers the user request.
- Confirm affected files, verification steps, and risk areas are known.
- Do not execute if the plan has unresolved blocking issues.

After implementation:
- Compare the actual diff against the accepted plan.
- Fix unexplained scope drift, or explain why the divergence was necessary.
- Review the changed code for bugs, regressions, missing tests, and maintainability issues.
- Fix blocking findings before final response.

Before claiming completion:
- Use `superpowers:verification-before-completion`.
- Run the most relevant available checks.
- Report any checks that could not be run.

## Blocking Issues

Blocking issues include:
- the plan or implementation does not satisfy the user request
- likely runtime errors
- data loss, destructive side effects, or credential exposure
- changes outside the requested scope
- risky behavior without verification
- failing tests caused by the current change

## Small Tasks

For read-only questions, command output requests, or tiny edits, a formal written plan is not required. Still verify the result before final response.
