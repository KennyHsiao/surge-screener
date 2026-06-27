# Test Server Auto Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add push-to-main deployment from GitHub Actions to `172.16.204.117`, serving Streamlit at `http://172.16.204.117:8501`.

**Architecture:** A GitHub self-hosted runner on the test server runs the deploy job locally after pushes to `main`. The script syncs the checked-out commit to `/home/kenny/apps/surge-screener/current`, keeps the venv and shared data under `/home/kenny/apps/surge-screener`, and manages the app with a user-level systemd service.

**Tech Stack:** GitHub Actions, SSH, Bash, Python venv, Streamlit, systemd user service, DuckDB, PyArrow.

---

### Task 1: Add Deploy Artifact Tests

**Files:**
- Create: `scripts/test_deploy_artifacts.py`

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
"""Offline checks for test-server deployment artifacts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_workflow() -> None:
    workflow = read(".github/workflows/deploy_test_server.yml")
    require("branches: [main]" in workflow, "deploy workflow must run on main pushes")
    require("self-hosted" in workflow, "workflow must use a self-hosted runner")
    require("surge-screener-test" in workflow, "workflow must target the test-server runner label")
    require("scripts/deploy_test_server.sh" in workflow, "workflow must run deploy script")


def test_deploy_script() -> None:
    script = read("scripts/deploy_test_server.sh")
    require("set -euo pipefail" in script, "deploy script must use strict shell mode")
    require("rsync -a --delete" in script, "deploy script must sync the checked-out commit")
    require("python3 -m venv" in script, "deploy script must create a venv")
    require("requirements.txt" in script, "deploy script must install project requirements")
    require("systemctl --user restart surge-screener" in script, "deploy script must restart user service")
    require("http://127.0.0.1:${APP_PORT}" in script, "deploy script must health check local Streamlit")


def test_service_template() -> None:
    service = read("deploy/surge-screener.service")
    require("WorkingDirectory=%h/apps/surge-screener/current" in service, "service must run from deployed checkout")
    require("--server.address 0.0.0.0" in service, "service must bind to private-network interfaces")
    require("--server.port 8501" in service, "service must use port 8501")
    require("Restart=on-failure" in service, "service must restart on failure")


def test_requirements_include_analytics_deps() -> None:
    req = read("requirements.txt")
    require("duckdb" in req, "requirements must include duckdb")
    require("pyarrow" in req, "requirements must include pyarrow")


if __name__ == "__main__":
    tests = [
        test_workflow,
        test_deploy_script,
        test_service_template,
        test_requirements_include_analytics_deps,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python scripts/test_deploy_artifacts.py`

Expected: FAIL with `FileNotFoundError` for `.github/workflows/deploy_test_server.yml`.

### Task 2: Add Deployment Artifacts

**Files:**
- Create: `.github/workflows/deploy_test_server.yml`
- Create: `scripts/deploy_test_server.sh`
- Create: `deploy/surge-screener.service`
- Modify: `requirements.txt`

- [ ] **Step 1: Add GitHub Actions workflow**

Create `.github/workflows/deploy_test_server.yml` with a push-to-main deployment job that runs on `[self-hosted, linux, x64, surge-screener-test]`, checks out the pushed commit, and runs `scripts/deploy_test_server.sh` locally on the test server.

- [ ] **Step 2: Add remote deploy script**

Create `scripts/deploy_test_server.sh` with strict shell mode, defaults for `/home/kenny/apps/surge-screener`, `8501`, and `surge-screener`, source checkout detection from `GITHUB_WORKSPACE`, `rsync -a --delete` deployment into `current`, venv creation, dependency install, service template installation, user systemd restart, and curl-based health check.

- [ ] **Step 3: Add service template**

Create `deploy/surge-screener.service` that starts:

```bash
%h/apps/surge-screener/.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

- [ ] **Step 4: Add analytics dependencies**

Append these lines to `requirements.txt`:

```text
duckdb>=1.0.0
pyarrow>=15.0.0
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python scripts/test_deploy_artifacts.py`

Expected: `deploy artifact tests: 4 passed`.

### Task 3: Bootstrap Test Server Service

**Files:**
- Remote path: `/home/kenny/apps/surge-screener/current`
- Remote path: `/home/kenny/.config/systemd/user/surge-screener.service`

- [ ] **Step 1: Sync current repo and run deploy script over SSH**

Run from local checkout:

```bash
ssh antigravity 'mkdir -p /tmp/surge-screener-bootstrap'
rsync -a --delete --exclude .git --exclude .venv ./ antigravity:/tmp/surge-screener-bootstrap/
ssh antigravity 'cd /tmp/surge-screener-bootstrap && chmod +x scripts/deploy_test_server.sh && ./scripts/deploy_test_server.sh'
```

Expected: script finishes after printing a successful health check.

- [ ] **Step 2: Verify service**

Run:

```bash
ssh antigravity 'systemctl --user status surge-screener --no-pager'
```

Expected: status includes `Active: active (running)`.

- [ ] **Step 3: Verify browser URL**

Run:

```bash
curl -I http://172.16.204.117:8501
```

Expected: HTTP response from Streamlit.

### Task 4: Commit And Push

**Files:**
- `.github/workflows/deploy_test_server.yml`
- `deploy/surge-screener.service`
- `docs/superpowers/plans/2026-06-26-test-server-auto-deploy.md`
- `docs/superpowers/specs/2026-06-26-test-server-auto-deploy-design.md`
- `requirements.txt`
- `scripts/deploy_test_server.sh`
- `scripts/test_deploy_artifacts.py`

- [ ] **Step 1: Review diff**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 2: Run verification**

Run: `.venv/bin/python scripts/test_deploy_artifacts.py`

Expected: `deploy artifact tests: 4 passed`.

- [ ] **Step 3: Commit**

Run:

```bash
git add .github/workflows/deploy_test_server.yml deploy/surge-screener.service docs/superpowers/plans/2026-06-26-test-server-auto-deploy.md docs/superpowers/specs/2026-06-26-test-server-auto-deploy-design.md requirements.txt scripts/deploy_test_server.sh scripts/test_deploy_artifacts.py
git commit -m "chore: add test server auto deploy"
```

- [ ] **Step 4: Push**

Run: `git push origin main`

Expected: GitHub receives the commit and starts the deploy workflow if a self-hosted runner is registered and online.

### Task 5: Post-Push Validation

**Files:**
- Remote service journal
- GitHub Actions run logs
- Self-hosted runner registration status

- [ ] **Step 1: Check remote service after Actions deploy**

Run:

```bash
ssh antigravity 'systemctl --user status surge-screener --no-pager'
```

Expected: status includes `Active: active (running)`.

- [ ] **Step 2: Check private-network URL**

Run:

```bash
curl -I http://172.16.204.117:8501
```

Expected: HTTP response from Streamlit.

- [ ] **Step 3: Check deploy logs if service is not reachable**

Run:

```bash
ssh antigravity 'journalctl --user -u surge-screener -n 120 --no-pager'
```

Expected: logs show Streamlit startup details or the concrete runtime error to fix.

- [ ] **Step 4: Register self-hosted runner if workflow stays queued**

Use GitHub repository settings to create a Linux x64 self-hosted runner registration token, then run the GitHub-provided commands on `172.16.204.117` as `kenny` under `/home/kenny/actions-runner` with the label `surge-screener-test`.
