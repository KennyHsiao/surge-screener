#!/usr/bin/env python3
"""Fail-closed observer for the 2026-08-18 natural validation window.

The observer is read-only outside its dedicated output directory.  It waits for
actual producer terminal states instead of assuming GitHub cron jobs start at
their nominal wall-clock minute.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as wall_time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


UTC = timezone.utc
TAIPEI = ZoneInfo("Asia/Taipei")
TERMINAL_STATES = {"PASS", "FAIL"}
DATA_HEALTH_UNIT = "surge-data-health-refresh.service"
DATA_HEALTH_TIMER = "surge-data-health-refresh.timer"
THEME_UNIT = "surge-theme-flow-refresh.service"
THEME_TIMER = "surge-theme-flow-refresh.timer"
RUNNER_UNIT = "github-actions-runner-surge-screener.service"


@dataclass(frozen=True)
class ValidationWindow:
    local_date: date
    data_health_due: datetime
    eod_due: datetime
    theme_due: datetime
    deadline: datetime
    recovery_deadline: datetime
    report_date: date


def validation_window(local_date: date) -> ValidationWindow:
    def local(hour: int, minute: int) -> datetime:
        return datetime.combine(local_date, wall_time(hour, minute), TAIPEI)

    eod_due = local(6, 30)
    return ValidationWindow(
        local_date=local_date,
        data_health_due=local(6, 15),
        eod_due=eod_due,
        theme_due=local(7, 45),
        deadline=local(10, 30),
        recovery_deadline=local(16, 30),
        report_date=eod_due.astimezone(UTC).date(),
    )


def iso_utc(value: datetime | None = None) -> str:
    current = (value or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def gate(state: str, reasons: list[str], evidence: dict[str, Any]) -> dict[str, Any]:
    if state not in {"PASS", "FAIL", "PENDING"}:
        raise ValueError(f"invalid gate state: {state}")
    return {"state": state, "reasons": reasons, "evidence": evidence}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_evidence(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": type(exc).__name__}
    return {
        "path": str(path),
        "exists": True,
        "size": len(data),
        "mtime_ns": stat.st_mtime_ns,
        "mtime": iso_utc(datetime.fromtimestamp(stat.st_mtime, UTC)),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def run_command(args: list[str], *, timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"rc": None, "stdout": "", "stderr": type(exc).__name__}
    return {
        "rc": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def parse_key_values(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key] = value
    return result


def systemd_show(unit: str) -> dict[str, Any]:
    properties = (
        "Id", "ActiveState", "SubState", "Result", "ExecMainStatus",
        "ActiveEnterTimestamp", "InactiveEnterTimestamp", "NextElapseUSecRealtime",
        "FragmentPath", "NeedDaemonReload",
    )
    command = run_command(
        ["systemctl", "--user", "show", unit]
        + [item for name in properties for item in ("--property", name)]
    )
    payload: dict[str, Any] = {
        "command_rc": command["rc"],
        **parse_key_values(str(command["stdout"])),
    }
    if command["stderr"]:
        payload["command_error"] = command["stderr"]
    return payload


def unit_enabled_active(unit: str) -> dict[str, Any]:
    enabled = run_command(["systemctl", "--user", "is-enabled", unit])
    active = run_command(["systemctl", "--user", "is-active", unit])
    return {
        "enabled": enabled["stdout"],
        "enabled_rc": enabled["rc"],
        "active": active["stdout"],
        "active_rc": active["rc"],
        "show": systemd_show(unit),
    }


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, repository: str, *, timeout: int = 30) -> None:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
            raise ValueError("repository must be OWNER/REPO")
        self.repository = repository
        self.timeout = timeout
        self.rate_limit: dict[str, Any] = {}

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        query = "?" + urllib.parse.urlencode(params) if params else ""
        url = f"https://api.github.com/repos/{self.repository}/{path.lstrip('/')}{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "surge-natural-validation-observer",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.rate_limit = {
                    "limit": response.headers.get("X-RateLimit-Limit"),
                    "remaining": response.headers.get("X-RateLimit-Remaining"),
                    "reset": response.headers.get("X-RateLimit-Reset"),
                }
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise GitHubApiError(f"GitHub API {exc.code} for {path}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GitHubApiError(f"GitHub API failed for {path}: {type(exc).__name__}") from exc


def github_json_file(client: GitHubClient, path: str, *, ref: str = "main") -> dict[str, Any]:
    encoded_path = urllib.parse.quote(path, safe="/")
    payload = client.get(f"contents/{encoded_path}", {"ref": ref})
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return {}
    try:
        encoded = "".join(str(payload.get("content") or "").split())
        decoded = base64.b64decode(encoded, validate=True)
        parsed = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def find_check(payload: dict[str, Any], check_id: str) -> dict[str, Any]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return next(
        (item for item in checks if isinstance(item, dict) and item.get("id") == check_id),
        {},
    )


def evaluate_preflight(
    *,
    app_root: Path,
    expected_hashes: dict[str, str],
    systemd: dict[str, dict[str, Any]],
    clock: dict[str, str],
    disk: dict[str, int],
    github_ok: bool,
    github_error: str | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    fatal = False
    hash_evidence: dict[str, Any] = {}
    current = app_root / "current"
    for relative, expected in sorted(expected_hashes.items()):
        evidence = file_evidence(current / relative)
        evidence["expected_sha256"] = expected
        evidence["matches"] = evidence.get("sha256") == expected
        hash_evidence[relative] = evidence
        if not evidence["matches"]:
            fatal = True
            reasons.append(f"deployed hash mismatch: {relative}")
    for timer in (DATA_HEALTH_TIMER, THEME_TIMER):
        info = systemd.get(timer, {})
        if info.get("enabled") != "enabled" or info.get("active") != "active":
            reasons.append(f"timer is not enabled and active: {timer}")
    runner = systemd.get(RUNNER_UNIT, {})
    if runner.get("active") != "active":
        reasons.append("self-hosted GitHub runner service is not active")
    if clock.get("Timezone") != "Asia/Taipei" or clock.get("NTPSynchronized") != "yes":
        reasons.append("host timezone or NTP synchronization is invalid")
    if disk.get("free_bytes", 0) < 5 * 1024**3 or disk.get("free_inodes", 0) < 10_000:
        reasons.append("host disk or inode reserve is below the validation floor")
    if not github_ok:
        reasons.append(github_error or "GitHub API is not reachable")
    loaded_units: dict[str, Any] = {}
    for unit in (DATA_HEALTH_UNIT, DATA_HEALTH_TIMER, THEME_UNIT, THEME_TIMER):
        show = systemd.get(unit, {}).get("show", {})
        fragment = Path(str(show.get("FragmentPath") or ""))
        installed = file_evidence(fragment)
        template = file_evidence(current / "deploy" / unit)
        matches = (
            installed.get("sha256") == template.get("sha256")
            and show.get("NeedDaemonReload") == "no"
        )
        loaded_units[unit] = {
            "installed": installed,
            "template": template,
            "need_daemon_reload": show.get("NeedDaemonReload"),
            "matches": matches,
        }
        if not matches:
            fatal = True
            reasons.append(f"loaded systemd unit differs from deployed template: {unit}")
    evidence = {
        "hashes": hash_evidence,
        "systemd": systemd,
        "loaded_units": loaded_units,
        "clock": clock,
        "disk": disk,
        "github_api_ok": github_ok,
        "github_error": github_error,
    }
    if fatal:
        return gate("FAIL", reasons, evidence)
    return gate("PASS" if not reasons else "PENDING", reasons, evidence)


def evaluate_data_health(
    window: ValidationWindow,
    *,
    status: dict[str, Any],
    unit: dict[str, Any],
    analytics: dict[str, Any],
    db_evidence: dict[str, Any],
    risk_guard: dict[str, Any],
) -> dict[str, Any]:
    due = window.data_health_due.astimezone(UTC) - timedelta(minutes=2)
    started = parse_timestamp(status.get("started_at"))
    evidence_check_ids = (
        "table:candidate_scores:row_count",
        "table:candidate_scores:latest_date",
        "table:market_thesis_forecasts:latest_date",
        "table:daily_reports:latest_date",
        "table:portfolio_positions:row_count",
        "table:risk_guard_rows:latest_date",
        "performance:no_confirmed_picks_streak",
    )
    evidence = {
        "status": status,
        "unit": unit,
        "analytics": {
            key: analytics.get(key)
            for key in ("generated_at", "as_of_date", "status", "summary", "today_signal_readiness")
        },
        "selected_checks": [
            item for check_id in evidence_check_ids
            if (item := find_check(analytics, check_id))
        ],
        "db": db_evidence,
        "risk_guard": {
            "generated_at": risk_guard.get("generated_at"),
            "as_of": risk_guard.get("as_of"),
            "summary": risk_guard.get("summary"),
            "data_sources": risk_guard.get("data_sources"),
        },
    }
    if started is None or started < due:
        return gate("PENDING", ["fresh Data Health invocation not observed"], evidence)
    if status.get("status") not in {"succeeded", "failed"}:
        return gate("PENDING", ["Data Health has not reached a terminal status"], evidence)
    reasons: list[str] = []
    if status.get("status") != "succeeded" or status.get("finished_at") is None:
        reasons.append("Data Health status is not a successful terminal")
    if unit.get("ActiveState") == "active":
        return gate("PENDING", ["Data Health systemd unit is still active"], evidence)
    if unit.get("Result") != "success" or str(unit.get("ExecMainStatus")) != "0":
        reasons.append("Data Health systemd result is not success/0")
    metrics = status.get("metrics") if isinstance(status.get("metrics"), dict) else {}
    if metrics.get("blockers") != 0 or metrics.get("today_signal_can_publish") is not True:
        reasons.append("Data Health reports blockers or non-publishable signals")
    generated = parse_timestamp(analytics.get("generated_at"))
    if generated is None or generated < started:
        reasons.append("Analytics generated_at is stale relative to Data Health")
    if analytics.get("as_of_date") != window.local_date.isoformat():
        reasons.append("Analytics as_of_date does not match the Taipei window date")
    summary = analytics.get("summary") if isinstance(analytics.get("summary"), dict) else {}
    readiness = (
        analytics.get("today_signal_readiness")
        if isinstance(analytics.get("today_signal_readiness"), dict) else {}
    )
    if summary.get("block") != 0 or readiness.get("can_publish") is not True:
        reasons.append("fresh Analytics checks are blocked or non-publishable")
    db_mtime = parse_timestamp(db_evidence.get("mtime"))
    if db_mtime is None or db_mtime < started:
        reasons.append("Analytics DuckDB mtime is stale relative to Data Health")

    daily = find_check(analytics, "table:daily_reports:latest_date")
    if parse_date(daily.get("value")) is None or parse_date(daily.get("value")) < date(2026, 8, 15):
        reasons.append("latest published daily report is older than 2026-08-15")
    portfolio = find_check(analytics, "table:portfolio_positions:row_count")
    if portfolio.get("status") != "PASS" or portfolio.get("availability") != "not_configured":
        reasons.append("absent portfolio source is not classified as not_configured")
    no_picks = find_check(analytics, "performance:no_confirmed_picks_streak")
    counts = no_picks.get("scan_state_counts") if isinstance(no_picks.get("scan_state_counts"), dict) else {}
    if not isinstance(counts.get("successful_zero_pick"), int) or counts["successful_zero_pick"] < 14:
        reasons.append("successful published zero-pick count is below 14")
    if counts.get("published_unclassified") != 0:
        reasons.append("published EOD reports contain unclassified outcomes")
    if any(counts.get(key) is not None for key in ("missing", "failed", "unpublished")):
        reasons.append("unknown EOD run-state counts were inferred without telemetry")

    sources = risk_guard.get("data_sources") if isinstance(risk_guard.get("data_sources"), dict) else {}
    expected_report_date = window.report_date.isoformat()
    risk_generated = parse_timestamp(risk_guard.get("generated_at"))
    observed = parse_date(sources.get("regime_observed_on"))
    source_date_raw = sources.get("regime_as_of")
    source_date = parse_date(source_date_raw)
    fallback_reason = sources.get("regime_fallback_reason")
    if risk_guard.get("as_of") != expected_report_date:
        reasons.append("Risk Guard observation date is not the expected UTC business date")
    if risk_generated is None or risk_generated < started:
        reasons.append("Risk Guard generated_at is stale relative to Data Health")
    if sources.get("regime") in {None, "", "missing"}:
        reasons.append("Risk Guard regime source is missing")
    if observed != window.report_date:
        reasons.append("Risk Guard regime observation provenance is not current")
    if source_date_raw not in (None, "") and source_date is None:
        reasons.append("Risk Guard regime source date is malformed")
    if source_date is None and fallback_reason not in {
        "stale_scored_regime", "missing_scored_regime", "invalid_scored_regime_date",
    }:
        reasons.append("Risk Guard missing source date has no explicit fallback provenance")
    if source_date is not None and observed is not None and source_date > observed:
        reasons.append("Risk Guard regime source date is later than its observation date")
    return gate("FAIL" if reasons else "PASS", reasons, evidence)


def evaluate_theme(
    window: ValidationWindow,
    *,
    status: dict[str, Any],
    unit: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    due = window.theme_due.astimezone(UTC) - timedelta(minutes=2)
    finished = parse_timestamp(status.get("finished_at") or status.get("updated_at"))
    evidence = {
        "status": status,
        "unit": unit,
        "snapshot": {
            "as_of": snapshot.get("as_of"),
            "generated_at": snapshot.get("generated_at"),
            "theme_count": len(snapshot.get("themes", [])) if isinstance(snapshot.get("themes"), list) else None,
        },
    }
    if finished is None or finished < due:
        return gate("PENDING", ["fresh Theme Flow invocation not observed"], evidence)
    if unit.get("ActiveState") == "active":
        return gate("PENDING", ["Theme Flow systemd unit is still active"], evidence)
    reasons: list[str] = []
    if status.get("status") != "ready":
        reasons.append("Theme Flow status is not ready")
    if unit.get("Result") != "success" or str(unit.get("ExecMainStatus")) != "0":
        reasons.append("Theme Flow systemd result is not success/0")
    result = status.get("result") if isinstance(status.get("result"), dict) else {}
    themes = snapshot.get("themes")
    if not isinstance(themes, list) or not themes or result.get("themes") != len(themes):
        reasons.append("Theme Flow snapshot is empty or disagrees with status")
    if parse_date(snapshot.get("as_of")) != window.report_date:
        reasons.append("Theme Flow snapshot date is not the expected UTC business date")
    generated = parse_timestamp(snapshot.get("generated_at"))
    if generated is None or generated < due:
        reasons.append("Theme Flow snapshot generated_at is stale")
    return gate("FAIL" if reasons else "PASS", reasons, evidence)


def select_eod_run(
    window: ValidationWindow,
    runs: list[dict[str, Any]],
    jobs_for_run: Callable[[int], list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    lower = window.eod_due.astimezone(UTC) - timedelta(minutes=20)
    upper = window.deadline.astimezone(UTC)
    candidates = []
    for run in runs:
        created = parse_timestamp(run.get("created_at"))
        if created is not None and lower <= created <= upper:
            candidates.append(run)
    candidates.sort(key=lambda item: str(item.get("created_at") or ""))
    for run in candidates:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            continue
        for job in jobs_for_run(run_id):
            if job.get("name") == "surge_scan" and job.get("conclusion") != "skipped":
                return run, job
    return None, None


def evaluate_eod(
    window: ValidationWindow,
    *,
    run: dict[str, Any] | None,
    job: dict[str, Any] | None,
    required_base_sha: str,
    ancestry_status: str | None,
    summary: dict[str, Any] | None = None,
    candidate_snapshot: dict[str, Any] | None = None,
    report_commits: list[dict[str, Any]] | None = None,
    candidate_commits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence = {
        "run": {
            key: (run or {}).get(key)
            for key in ("id", "status", "conclusion", "created_at", "updated_at", "head_sha", "html_url")
        },
        "job": {
            key: (job or {}).get(key)
            for key in ("id", "name", "status", "conclusion", "started_at", "completed_at")
        },
        "required_base_sha": required_base_sha,
        "ancestry_status": ancestry_status,
    }
    if run is None or job is None:
        return gate("PENDING", ["scheduled EOD surge_scan run not observed"], evidence)
    if run.get("status") != "completed" or job.get("status") != "completed":
        return gate("PENDING", ["scheduled EOD surge_scan is not terminal"], evidence)
    reasons: list[str] = []
    if run.get("conclusion") != "success" or job.get("conclusion") != "success":
        reasons.append("scheduled EOD surge_scan did not succeed")
    if ancestry_status not in {"ahead", "identical"}:
        reasons.append("EOD head does not contain the required remediation revision")
    summary = summary or {}
    candidate_snapshot = candidate_snapshot or {}
    report_date = window.report_date.isoformat()
    picks = summary.get("ranked_picks")
    confirmed = summary.get("total_confirmed")
    if summary.get("report_date") != report_date:
        reasons.append("published EOD report date is incorrect")
    if type(confirmed) is not int or confirmed < 0 or not isinstance(picks, list) or len(picks) != confirmed:
        reasons.append("published EOD confirmed-pick contract is invalid")
    cohort = candidate_snapshot.get("all_scored")
    cohort_count = candidate_snapshot.get("scored_cohort_count")
    universe_count = candidate_snapshot.get("ranked_universe_count")
    rank_limit = candidate_snapshot.get("rank_limit")
    if str(candidate_snapshot.get("scan_date") or "")[:10] != report_date:
        reasons.append("candidate snapshot scan date is incorrect")
    if candidate_snapshot.get("cohort_type") not in {"bounded_top_n", "full_ranked_universe"}:
        reasons.append("candidate snapshot cohort type is missing")
    if candidate_snapshot.get("selection_method") not in {"deterministic_top_n", "all_ranked"}:
        reasons.append("candidate snapshot selection method is missing")
    if (
        type(cohort_count) is not int or cohort_count <= 0
        or type(universe_count) is not int or universe_count < cohort_count
        or type(rank_limit) is not int or rank_limit < cohort_count
        or not isinstance(cohort, list) or len(cohort) != cohort_count
        or candidate_snapshot.get("remaining_unscored") != 0
    ):
        reasons.append("candidate snapshot cohort counts are incomplete or inconsistent")
    if not report_commits:
        reasons.append("no post-run commit found for the EOD report path")
    if not candidate_commits:
        reasons.append("no post-run commit found for the candidate snapshot path")
    evidence["report"] = {
        "report_date": summary.get("report_date"),
        "total_confirmed": confirmed,
        "ranked_pick_count": len(picks) if isinstance(picks, list) else None,
        "post_run_commits": len(report_commits or []),
    }
    evidence["candidate_snapshot"] = {
        "scan_date": candidate_snapshot.get("scan_date"),
        "cohort_type": candidate_snapshot.get("cohort_type"),
        "ranked_universe_count": universe_count,
        "scored_cohort_count": cohort_count,
        "selection_method": candidate_snapshot.get("selection_method"),
        "rank_limit": rank_limit,
        "remaining_unscored": candidate_snapshot.get("remaining_unscored"),
        "post_run_commits": len(candidate_commits or []),
    }
    return gate("FAIL" if reasons else "PASS", reasons, evidence)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def append_timeline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def clock_evidence() -> dict[str, str]:
    result = run_command(["timedatectl", "show", "--property=Timezone", "--property=NTPSynchronized"])
    return parse_key_values(str(result["stdout"]))


def disk_evidence(path: Path) -> dict[str, int]:
    usage = shutil.disk_usage(path)
    stat = os.statvfs(path)
    return {
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "free_inodes": stat.f_favail,
        "total_inodes": stat.f_files,
    }


def capture_preflight(
    *, app_root: Path, expected_hashes: dict[str, str], client: GitHubClient,
    required_base_sha: str, github_verified: bool | None = None,
) -> dict[str, Any]:
    systemd = {
        unit: unit_enabled_active(unit)
        for unit in (
            DATA_HEALTH_UNIT, DATA_HEALTH_TIMER, THEME_UNIT, THEME_TIMER, RUNNER_UNIT,
        )
    }
    github_ok = github_verified is True
    github_error = None
    if github_verified is None:
        try:
            commit = client.get(f"commits/{required_base_sha}")
            github_ok = isinstance(commit, dict) and commit.get("sha") == required_base_sha
        except GitHubApiError as exc:
            github_error = str(exc)
    return evaluate_preflight(
        app_root=app_root,
        expected_hashes=expected_hashes,
        systemd=systemd,
        clock=clock_evidence(),
        disk=disk_evidence(app_root),
        github_ok=github_ok,
        github_error=github_error,
    )


def github_commits_for_path(
    client: GitHubClient, path: str, *, since: str,
) -> list[dict[str, Any]]:
    payload = client.get("commits", {"path": path, "since": since, "per_page": "10"})
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def observe(args: argparse.Namespace) -> int:
    window = validation_window(date.fromisoformat(args.window_date))
    app_root = Path(args.app_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, 0o700)
    lock_path = output_dir / "observer.lock"
    expected_hashes = dict(item.split("=", 1) for item in args.expected_hash)
    client = GitHubClient(args.repository)
    observer_evidence = file_evidence(Path(__file__).resolve())
    eod_run: dict[str, Any] | None = None
    eod_job: dict[str, Any] | None = None
    eod_gate_cache: dict[str, Any] | None = None
    job_cache: dict[int, list[dict[str, Any]]] = {}
    last_api_error: str | None = None

    with lock_path.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another natural validation observer is already running")

        preflight = capture_preflight(
            app_root=app_root,
            expected_hashes=expected_hashes,
            client=client,
            required_base_sha=args.required_base_sha,
        )
        github_preflight_verified = preflight["evidence"].get("github_api_ok") is True
        if args.preflight_only:
            payload = {
                "captured_at": iso_utc(),
                "window": {
                    "local_date": window.local_date.isoformat(),
                    "data_health_due": window.data_health_due.isoformat(),
                    "eod_due": window.eod_due.isoformat(),
                    "theme_due": window.theme_due.isoformat(),
                    "deadline": window.deadline.isoformat(),
                    "report_date": window.report_date.isoformat(),
                },
                "observer": observer_evidence,
                "gate": preflight,
                "github_rate_limit": client.rate_limit,
            }
            atomic_write_json(output_dir / "preflight.json", payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0 if preflight["state"] == "PASS" else 1

        while True:
            now = datetime.now(UTC)
            preflight = capture_preflight(
                app_root=app_root,
                expected_hashes=expected_hashes,
                client=client,
                required_base_sha=args.required_base_sha,
                github_verified=True if github_preflight_verified else None,
            )
            github_preflight_verified = (
                github_preflight_verified
                or preflight["evidence"].get("github_api_ok") is True
            )
            data_health = evaluate_data_health(
                window,
                status=read_json(app_root / "shared/run_status/data-health-refresh.json"),
                unit=systemd_show(DATA_HEALTH_UNIT),
                analytics=read_json(app_root / "shared/analytics_checks/latest.json"),
                db_evidence=file_evidence(app_root / "shared/data/analytics.duckdb"),
                risk_guard=read_json(app_root / "current/reports/risk_guard/latest.json"),
            )
            theme = evaluate_theme(
                window,
                status=read_json(app_root / "shared/run_status/theme-flow-refresh_board.json"),
                unit=systemd_show(THEME_UNIT),
                snapshot=read_json(app_root / "shared/theme_flow_snapshot.json"),
            )

            try:
                if eod_gate_cache is not None:
                    last_api_error = None
                elif eod_run is None:
                    run_payload = client.get(
                        "actions/workflows/surge_screener.yml/runs",
                        {"event": "schedule", "per_page": "30"},
                    )
                    runs = run_payload.get("workflow_runs", []) if isinstance(run_payload, dict) else []

                    def jobs_for_run(run_id: int) -> list[dict[str, Any]]:
                        if run_id not in job_cache:
                            payload = client.get(f"actions/runs/{run_id}/jobs", {"per_page": "100"})
                            raw = payload.get("jobs", []) if isinstance(payload, dict) else []
                            jobs = [item for item in raw if isinstance(item, dict)]
                            if jobs:
                                job_cache[run_id] = jobs
                            return jobs
                        return job_cache[run_id]

                    eod_run, eod_job = select_eod_run(window, runs, jobs_for_run)
                else:
                    refreshed = client.get(f"actions/runs/{eod_run['id']}")
                    if isinstance(refreshed, dict):
                        eod_run = refreshed
                    jobs_payload = client.get(f"actions/runs/{eod_run['id']}/jobs", {"per_page": "100"})
                    jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
                    eod_job = next(
                        (item for item in jobs if isinstance(item, dict) and item.get("name") == "surge_scan"),
                        eod_job,
                    )
                last_api_error = None
            except GitHubApiError as exc:
                last_api_error = str(exc)

            ancestry = None
            summary = None
            candidate = None
            report_commits = None
            candidate_commits = None
            if eod_gate_cache is not None:
                eod = eod_gate_cache
            elif eod_run and eod_job and eod_run.get("status") == "completed":
                try:
                    head = str(eod_run.get("head_sha") or "")
                    compare = client.get(f"compare/{args.required_base_sha}...{head}")
                    ancestry = compare.get("status") if isinstance(compare, dict) else None
                    report_path = f"reports/{window.report_date.isoformat()}/summary.json"
                    candidate_path = f"reports/candidate_scores/{window.report_date.isoformat()}.json"
                    summary = github_json_file(client, report_path)
                    candidate = github_json_file(client, candidate_path)
                    since = str(eod_run.get("created_at") or iso_utc(now))
                    report_commits = github_commits_for_path(client, report_path, since=since)
                    candidate_commits = github_commits_for_path(client, candidate_path, since=since)
                    last_api_error = None
                except GitHubApiError as exc:
                    last_api_error = str(exc)
                eod = evaluate_eod(
                    window,
                    run=eod_run,
                    job=eod_job,
                    required_base_sha=args.required_base_sha,
                    ancestry_status=ancestry,
                    summary=summary,
                    candidate_snapshot=candidate,
                    report_commits=report_commits,
                    candidate_commits=candidate_commits,
                )
                if last_api_error:
                    eod["evidence"]["github_api_error"] = last_api_error
                elif eod["state"] in TERMINAL_STATES:
                    eod_gate_cache = eod
            else:
                eod = evaluate_eod(
                    window,
                    run=eod_run,
                    job=eod_job,
                    required_base_sha=args.required_base_sha,
                    ancestry_status=ancestry,
                )
                if last_api_error:
                    eod["evidence"]["github_api_error"] = last_api_error

            gates = {
                "preflight": preflight,
                "data_health": data_health,
                "eod": eod,
                "theme_flow": theme,
            }
            deadline_reached = now >= window.deadline.astimezone(UTC)
            if deadline_reached:
                for name, item in gates.items():
                    if item["state"] == "PENDING":
                        item["state"] = "FAIL"
                        item["reasons"].append(f"{name} remained pending at the validation deadline")
            states = [item["state"] for item in gates.values()]
            all_terminal = all(state in TERMINAL_STATES for state in states)
            verdict = "PASS" if states and all(state == "PASS" for state in states) else (
                "FAIL" if all_terminal else "PENDING"
            )
            snapshot = {
                "schema_version": 1,
                "captured_at": iso_utc(now),
                "window": {
                    "local_date": window.local_date.isoformat(),
                    "data_health_due": window.data_health_due.isoformat(),
                    "eod_due": window.eod_due.isoformat(),
                    "theme_due": window.theme_due.isoformat(),
                    "deadline": window.deadline.isoformat(),
                    "report_date": window.report_date.isoformat(),
                },
                "required_base_sha": args.required_base_sha,
                "observer": observer_evidence,
                "github_rate_limit": client.rate_limit,
                "gates": gates,
                "verdict": verdict,
            }
            atomic_write_json(output_dir / "latest.json", snapshot)
            append_timeline(output_dir / "timeline.jsonl", snapshot)
            if all_terminal:
                atomic_write_json(output_dir / "verdict.json", snapshot)
                print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
                return 0 if verdict == "PASS" else 1
            time.sleep(args.poll_seconds)


def parse_expected_hash(value: str) -> str:
    path, separator, sha = value.partition("=")
    if not separator or not path or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise argparse.ArgumentTypeError("expected hash must be relative/path=<64 lowercase hex>")
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise argparse.ArgumentTypeError("expected hash path must stay inside current/")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Observe a natural validation window")
    parser.add_argument("--window-date", required=True, help="Asia/Taipei date, YYYY-MM-DD")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--app-root", default=os.environ.get("SURGE_APP_ROOT", "/home/kenny/apps/surge-screener"))
    parser.add_argument("--repository", default="KennyHsiao/surge-screener")
    parser.add_argument("--required-base-sha", required=True)
    parser.add_argument("--expected-hash", action="append", default=[], type=parse_expected_hash)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    date.fromisoformat(args.window_date)
    if re.fullmatch(r"[0-9a-f]{40}", args.required_base_sha) is None:
        parser.error("--required-base-sha must be a full lowercase commit SHA")
    if not args.expected_hash:
        parser.error("at least one --expected-hash is required")
    if args.poll_seconds < 30:
        parser.error("--poll-seconds must be at least 30")
    return observe(args)


if __name__ == "__main__":
    raise SystemExit(main())
