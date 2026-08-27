#!/usr/bin/env python3
"""Ingest Git-published reports after their real producers reach terminal states."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import multiprocessing
import os
import re
import shutil
import tempfile
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as wall_time, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from scripts import analytics_refresh_transaction, promotion_reachability, scoring_contract
    from scripts.natural_validation_observer import (
        GitHubApiError,
        GitHubClient,
        TAIPEI,
        UTC,
        ValidationWindow,
        evaluate_theme,
        parse_timestamp,
        read_json,
        systemd_show,
        validation_window,
    )
except ImportError:
    import analytics_refresh_transaction  # type: ignore
    import promotion_reachability  # type: ignore
    import scoring_contract  # type: ignore
    from natural_validation_observer import (  # type: ignore
        GitHubApiError,
        GitHubClient,
        TAIPEI,
        UTC,
        ValidationWindow,
        evaluate_theme,
        parse_timestamp,
        read_json,
        systemd_show,
        validation_window,
    )


THEME_UNIT = "surge-theme-flow-refresh.service"
POST_INGESTION_SCHEMA_VERSION = 2
SELECTED_CHECK_IDS = (
    "table:candidate_scores:row_count",
    "table:candidate_scores:latest_date",
    "table:market_thesis_forecasts:latest_date",
    "table:daily_reports:latest_date",
    "table:portfolio_positions:row_count",
    "table:risk_guard_rows:latest_date",
    "performance:no_confirmed_picks_streak",
    "candidate_scores:promotion_reachability",
)


class UnpublishedArtifactError(RuntimeError):
    """A successful producer did not publish a required report artifact."""


class ArtifactContractError(RuntimeError):
    """A downloaded report does not satisfy its immutable contract."""


class ProducerFailure(RuntimeError):
    """A required producer reached a non-success terminal state."""


class ValidationDeadlineExceeded(RuntimeError):
    """The natural-validation deadline passed before durable success."""


class AnalyticsWorkerError(RuntimeError):
    """A bounded Analytics worker failed before provisional success."""


@dataclass(frozen=True)
class ArtifactSpec:
    relative_path: str
    kind: str


@dataclass(frozen=True)
class PreparedReportGeneration:
    store: Path
    generation: Path
    previous_generation: Path | None
    manifest: dict[str, Any]


def iso_utc(value: datetime | None = None) -> str:
    current = (value or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def remaining_window_seconds(deadline: datetime, *, now: datetime | None = None) -> float:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    return (deadline.astimezone(UTC) - current).total_seconds()


def observation_timing(
    window: ValidationWindow,
    *,
    now: datetime,
    producer_state: str,
) -> dict[str, Any]:
    """Classify SLA timeliness separately from eventual data recovery."""
    current = now.astimezone(UTC)
    sla = window.deadline.astimezone(UTC)
    recovery = window.recovery_deadline.astimezone(UTC)
    missed = current >= sla
    if producer_state == "FAIL" or current >= recovery:
        action = "FAIL"
        state = "FAILED"
    elif producer_state == "PASS":
        action = "PROCEED"
        state = "RECOVERED_LATE" if missed else "ON_TIME"
    else:
        action = "WAIT"
        state = "WAITING_LATE" if missed else "PENDING"
    return {
        "action": action,
        "evidence": {
            "state": state,
            "sla_deadline": iso_utc(sla),
            "recovery_deadline": iso_utc(recovery),
            "deadline_missed_at": iso_utc(sla) if missed else None,
            "completed_at": iso_utc(current) if action != "WAIT" else None,
        },
    }


def unknown_timeliness() -> dict[str, Any]:
    return {
        "state": "UNKNOWN",
        "sla_deadline": None,
        "recovery_deadline": None,
        "deadline_missed_at": None,
        "completed_at": None,
    }


def bounded_lock_timeout(
    deadline: datetime,
    configured_seconds: float,
    *,
    now: datetime | None = None,
) -> float:
    remaining = remaining_window_seconds(deadline, now=now)
    if remaining <= 0:
        raise ValidationDeadlineExceeded(
            "natural-validation deadline passed before Analytics lock acquisition"
        )
    return min(float(configured_seconds), remaining)


def require_before_deadline(deadline: datetime, *, stage: str) -> None:
    if remaining_window_seconds(deadline) <= 0:
        raise ValidationDeadlineExceeded(
            f"natural-validation deadline passed before {stage}"
        )


def observer_sleep(seconds: float) -> None:
    time.sleep(seconds)


def sha256_file(path: str | Path) -> str:
    return analytics_refresh_transaction.sha256_file(path)


def required_artifacts(report_date: date) -> list[ArtifactSpec]:
    day = report_date.isoformat()
    artifacts = [
        ArtifactSpec(f"reports/{day}/summary.json", "daily_summary"),
        ArtifactSpec(f"reports/candidate_scores/{day}.json", "candidate_scores"),
    ]
    if report_date.weekday() == 0:
        artifacts.append(ArtifactSpec(
            f"reports/market_thesis/regime_only_forecast_{day}.json",
            "market_thesis",
        ))
    return artifacts


def validate_daily_summary(payload: dict[str, Any], report_date: date) -> dict[str, Any]:
    picks = payload.get("ranked_picks")
    confirmed = payload.get("total_confirmed")
    if payload.get("report_date") != report_date.isoformat():
        raise ArtifactContractError("daily summary report_date is incorrect")
    if type(confirmed) is not int or confirmed < 0:
        raise ArtifactContractError("daily summary total_confirmed is invalid")
    if not isinstance(picks, list) or len(picks) != confirmed:
        raise ArtifactContractError("daily summary confirmed-pick count is inconsistent")
    return {
        "report_date": report_date.isoformat(),
        "total_confirmed": confirmed,
        "outcome": "successful_zero_pick" if confirmed == 0 else "successful_with_picks",
    }


def validate_candidate_scores(payload: dict[str, Any], report_date: date) -> dict[str, Any]:
    cohort = payload.get("all_scored")
    cohort_count = payload.get("scored_cohort_count")
    universe_count = payload.get("ranked_universe_count")
    rank_limit = payload.get("rank_limit")
    if str(payload.get("scan_date") or "")[:10] != report_date.isoformat():
        raise ArtifactContractError("candidate snapshot scan_date is incorrect")
    if payload.get("cohort_type") not in {"bounded_top_n", "full_ranked_universe"}:
        raise ArtifactContractError("candidate snapshot cohort_type is invalid")
    if payload.get("selection_method") not in {"deterministic_top_n", "all_ranked"}:
        raise ArtifactContractError("candidate snapshot selection_method is invalid")
    valid = (
        type(cohort_count) is int
        and cohort_count >= 25
        and type(universe_count) is int
        and universe_count >= cohort_count
        and type(rank_limit) is int
        and rank_limit >= cohort_count
        and isinstance(cohort, list)
        and len(cohort) == cohort_count
        and payload.get("remaining_unscored") == 0
    )
    if not valid:
        raise ArtifactContractError("candidate snapshot cohort is incomplete or inconsistent")
    tickers = [row.get("ticker") for row in cohort if isinstance(row, dict)]
    if (
        len(tickers) != cohort_count
        or any(not isinstance(ticker, str) or not ticker.strip() for ticker in tickers)
        or len(set(tickers)) != cohort_count
    ):
        raise ArtifactContractError("candidate snapshot tickers are invalid or duplicated")
    regime = payload.get("regime_context")
    contract_failures = []
    for row in cohort:
        valid_row, errors = scoring_contract.validate_full_score_contract(row, regime)
        if not valid_row:
            contract_failures.append(
                f"{row.get('ticker')}: {', '.join(errors[:2])}"
            )
    if contract_failures:
        raise ArtifactContractError(
            "candidate full-score contract failed: " + "; ".join(contract_failures[:3])
        )
    multiplier = regime.get("global_score_multiplier") if isinstance(regime, dict) else None
    expected_reachability = promotion_reachability.summarize_run(
        cohort,
        multiplier=multiplier,
        total_candidates=cohort_count,
    )
    reachability = payload.get("promotion_reachability_v1")
    if (
        not isinstance(reachability, dict)
        or reachability != expected_reachability
        or reachability.get("state") not in {"reachable", "not_reachable"}
        or reachability.get("unsupported_credit_count") != 0
        or reachability.get("unsupported_credit_tickers") != []
    ):
        if (
            isinstance(reachability, dict)
            and reachability.get("unsupported_credit_count") == 0
            and reachability.get("unsupported_credit_tickers") == []
        ):
            raise ArtifactContractError("candidate promotion reachability contract is invalid")
        raise ArtifactContractError("candidate snapshot contains unsupported credit")
    return {
        "scan_date": report_date.isoformat(),
        "scored_cohort_count": cohort_count,
        "ranked_universe_count": universe_count,
        "remaining_unscored": 0,
        "full_score_contract_validated": cohort_count,
        "unsupported_credit_count": 0,
        "unsupported_credit_tickers": [],
    }


def validate_market_thesis(payload: dict[str, Any], report_date: date) -> dict[str, Any]:
    if str(payload.get("as_of") or "")[:10] != report_date.isoformat():
        raise ArtifactContractError("Market Thesis as_of is incorrect")
    if not payload.get("generated_at") or not payload.get("method"):
        raise ArtifactContractError("Market Thesis provenance is incomplete")
    return {
        "as_of": report_date.isoformat(),
        "generated_at": payload.get("generated_at"),
        "method": payload.get("method"),
        "manifest_status": payload.get("manifest_status"),
    }


def validate_artifact(
    spec: ArtifactSpec,
    payload: dict[str, Any],
    report_date: date,
) -> dict[str, Any]:
    validators: dict[str, Callable[[dict[str, Any], date], dict[str, Any]]] = {
        "daily_summary": validate_daily_summary,
        "candidate_scores": validate_candidate_scores,
        "market_thesis": validate_market_thesis,
    }
    try:
        validator = validators[spec.kind]
    except KeyError:
        raise ArtifactContractError(f"unsupported artifact kind: {spec.kind}") from None
    return validator(payload, report_date)


def _decode_github_content(payload: Any, relative_path: str) -> tuple[bytes, str | None]:
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise UnpublishedArtifactError(f"required artifact is unpublished: {relative_path}")
    try:
        encoded = "".join(str(payload.get("content") or "").split())
        raw = base64.b64decode(encoded, validate=True)
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactContractError(f"artifact is not valid UTF-8 JSON: {relative_path}") from exc
    if not isinstance(parsed, dict):
        raise ArtifactContractError(f"artifact JSON root is not an object: {relative_path}")
    return raw, str(payload.get("sha")) if payload.get("sha") else None


def _atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
    )


def _safe_current_generation(store: Path, generations: Path) -> Path | None:
    current = store / "current"
    if not current.is_symlink():
        return None
    resolved = current.resolve()
    try:
        resolved.relative_to(generations.resolve())
    except ValueError:
        raise RuntimeError("published-report current link escapes generations") from None
    return resolved if resolved.is_dir() else None


def _switch_current(store: Path, generation: Path) -> None:
    temporary = store / f".current-{uuid.uuid4().hex}.tmp"
    relative_target = generation.relative_to(store)
    temporary.symlink_to(relative_target, target_is_directory=True)
    try:
        os.replace(temporary, store / "current")
        _fsync_directory(store)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def resolve_main_sha(client: Any) -> str:
    commit = client.get("commits/main")
    source_sha = str(commit.get("sha") or "") if isinstance(commit, dict) else ""
    if re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise UnpublishedArtifactError("remote main did not resolve to an immutable SHA")
    return source_sha


def prepare_published_reports(
    *,
    client: Any,
    store_root: str | Path,
    report_date: date,
    producer_evidence: dict[str, Any],
    source_sha: str | None = None,
) -> PreparedReportGeneration:
    """Validate and finalize an immutable generation without moving current."""
    source_sha = source_sha or resolve_main_sha(client)
    if re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise UnpublishedArtifactError("source SHA is not immutable")

    store = Path(store_root).resolve()
    generations = store / "generations"
    generations.mkdir(parents=True, exist_ok=True)
    os.chmod(store, 0o700)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=generations))
    try:
        current = _safe_current_generation(store, generations)
        if current is not None:
            shutil.rmtree(staging)
            shutil.copytree(current, staging, copy_function=os.link)
        artifact_evidence: list[dict[str, Any]] = []
        for spec in required_artifacts(report_date):
            encoded_path = urllib.parse.quote(spec.relative_path, safe="/")
            try:
                response = client.get(f"contents/{encoded_path}", {"ref": source_sha})
            except (GitHubApiError, KeyError) as exc:
                raise UnpublishedArtifactError(
                    f"required artifact is unpublished: {spec.relative_path}"
                ) from exc
            raw, blob_sha = _decode_github_content(response, spec.relative_path)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ArtifactContractError(f"invalid JSON: {spec.relative_path}") from exc
            contract = validate_artifact(spec, payload, report_date)
            destination = staging / spec.relative_path
            _atomic_write_bytes(destination, raw)
            artifact_evidence.append({
                "relative_path": spec.relative_path,
                "kind": spec.kind,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "git_blob_sha": blob_sha,
                "contract": contract,
            })
        manifest = {
            "schema_version": 1,
            "generated_at": iso_utc(),
            "report_date": report_date.isoformat(),
            "source_ref": "main",
            "source_sha": source_sha,
            "producers": producer_evidence,
            "artifacts": artifact_evidence,
        }
        final = generations / f"{report_date.isoformat()}-{source_sha[:12]}-{uuid.uuid4().hex[:8]}"
        manifest["generation_id"] = final.name
        atomic_write_json(staging / "manifest.json", manifest)
        os.replace(staging, final)
        _fsync_directory(generations)
        return PreparedReportGeneration(
            store=store,
            generation=final,
            previous_generation=current,
            manifest=manifest,
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def promote_prepared_generation(prepared: PreparedReportGeneration) -> Callable[[], None]:
    """Move current to a prepared generation and return its exact rollback."""
    generations = prepared.store / "generations"
    active = _safe_current_generation(prepared.store, generations)
    if active != prepared.previous_generation:
        raise RuntimeError("published-report current changed after generation preparation")
    if not prepared.generation.is_dir():
        raise RuntimeError("prepared published-report generation is missing")
    _switch_current(prepared.store, prepared.generation)

    def rollback() -> None:
        current = _safe_current_generation(prepared.store, generations)
        if current != prepared.generation:
            raise RuntimeError("published-report current changed before companion rollback")
        if prepared.previous_generation is not None:
            _switch_current(prepared.store, prepared.previous_generation)
        else:
            (prepared.store / "current").unlink()
            _fsync_directory(prepared.store)

    return rollback


def classify_producer_state(
    *,
    run: dict[str, Any] | None,
    job: dict[str, Any] | None,
    artifact_present: bool | None,
) -> str:
    if run is None or job is None:
        return "missing"
    if run.get("status") != "completed" or job.get("status") != "completed":
        return "running"
    if run.get("conclusion") != "success" or job.get("conclusion") != "success":
        return "failed"
    if artifact_present is False:
        return "unpublished"
    return "succeeded"


def _find_check(checks: dict[str, Any], check_id: str) -> dict[str, Any]:
    rows = checks.get("checks") if isinstance(checks.get("checks"), list) else []
    return next(
        (item for item in rows if isinstance(item, dict) and item.get("id") == check_id),
        {},
    )


def validate_post_ingestion_checks(
    checks: dict[str, Any],
    _tables: dict[str, Any],
    *,
    report_date: date,
    candidate_count: int,
    daily_outcome: str,
) -> None:
    expected = report_date.isoformat()
    reasons: list[str] = []
    summary = checks.get("summary") if isinstance(checks.get("summary"), dict) else {}
    if summary.get("block") != 0:
        reasons.append("Analytics contains BLOCK findings")
    candidate_rows = _find_check(checks, "table:candidate_scores:row_count")
    if candidate_rows.get("status") != "PASS" or not isinstance(candidate_rows.get("value"), int):
        reasons.append("candidate score row-count check is absent or not PASS")
    elif candidate_rows["value"] < candidate_count:
        reasons.append("candidate score cohort was not fully ingested")
    if _find_check(checks, "table:candidate_scores:latest_date").get("value") != expected:
        reasons.append("candidate score latest date does not match the producer report")
    if _find_check(checks, "table:daily_reports:latest_date").get("value") != expected:
        reasons.append("daily report latest date does not match the producer report")
    if report_date.weekday() == 0:
        thesis = _find_check(checks, "table:market_thesis_forecasts:latest_date")
        if thesis.get("value") != expected:
            reasons.append("Market Thesis latest date does not match the weekly producer")
    portfolio = _find_check(checks, "table:portfolio_positions:row_count")
    if portfolio.get("status") != "PASS":
        reasons.append("portfolio availability is not PASS")
    risk_guard = _find_check(checks, "table:risk_guard_rows:latest_date")
    risk_date = str(risk_guard.get("value") or "")[:10]
    if risk_guard.get("status") != "PASS" or risk_date < expected:
        reasons.append("Risk Guard latest date is stale or not PASS")
    no_picks = _find_check(checks, "performance:no_confirmed_picks_streak")
    counts = no_picks.get("scan_state_counts") if isinstance(no_picks.get("scan_state_counts"), dict) else {}
    if no_picks.get("latest_report_date") != expected:
        reasons.append("no-picks telemetry did not absorb the latest report")
    if counts.get("published_unclassified") != 0:
        reasons.append("a published EOD outcome remains unclassified")
    if daily_outcome == "successful_zero_pick" and not isinstance(counts.get("successful_zero_pick"), int):
        reasons.append("successful zero-pick state is not counted explicitly")
    reachability = _find_check(checks, "candidate_scores:promotion_reachability")
    if reachability.get("unsupported_credit_count") != 0:
        reasons.append("candidate promotion contains unsupported credit")
    reachability_contract_valid = (
        reachability.get("status") in {"PASS", "WARN"}
        and reachability.get("code") != "PROMOTION_REACHABILITY_UNKNOWN"
        and reachability.get("latest_scan_date") == expected
        and reachability.get("reachability_state") in {"reachable", "not_reachable"}
        and reachability.get("candidate_rows") == candidate_count
        and reachability.get("contract_rows") == candidate_count
        and reachability.get("scored_cohort_count") == candidate_count
        and reachability.get("diagnostic_schema") == "promotion_reachability_v1"
        and reachability.get("diagnostic_mode") == "shadow"
        and reachability.get("authoritative_for_promotion") is False
    )
    if not reachability_contract_valid:
        reasons.append("Analytics promotion reachability contract is incomplete or stale")
    if reasons:
        raise analytics_refresh_transaction.AnalyticsGateError("; ".join(reasons))


def build_post_ingestion_verdict(
    *,
    state: str,
    report_date: date,
    manifest: dict[str, Any],
    refresh: dict[str, Any],
    reasons: list[str] | None = None,
    timeliness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = refresh.get("checks") if isinstance(refresh.get("checks"), dict) else {}
    check_rows = checks.get("checks") if isinstance(checks.get("checks"), list) else []
    selected = [
        item for item in check_rows
        if isinstance(item, dict) and item.get("id") in SELECTED_CHECK_IDS
    ]
    return {
        "schema_version": POST_INGESTION_SCHEMA_VERSION,
        "captured_at": iso_utc(),
        "state": state,
        "reasons": list(reasons or []),
        "report_date": report_date.isoformat(),
        "source_sha": manifest.get("source_sha"),
        "producers": manifest.get("producers", {}),
        "artifacts": manifest.get("artifacts", []),
        "analytics_summary": checks.get("summary"),
        "analytics_status": checks.get("status"),
        "analytics_checks": selected,
        "database": refresh.get("database", {}),
        "promoted_at": refresh.get("promoted_at"),
        "timeliness": dict(timeliness or unknown_timeliness()),
    }


def build_transaction_recovery_context(
    *,
    prepared: PreparedReportGeneration,
    report_date: date,
    verdict_path: Path,
    status_path: Path,
    timeliness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize enough state to recover after an uncatchable process exit."""
    failure = build_post_ingestion_verdict(
        state="FAIL",
        report_date=report_date,
        manifest=prepared.manifest,
        refresh={},
        reasons=["abandoned Analytics transaction recovered after process interruption"],
        timeliness=timeliness,
    )
    return {
        "companion": {
            "kind": "symlink",
            "pointer": str(prepared.store / "current"),
            "previous_target": (
                str(prepared.previous_generation)
                if prepared.previous_generation is not None
                else None
            ),
            "promoted_target": str(prepared.generation),
        },
        "failure_writes": [
            {"path": str(verdict_path), "payload": failure},
            {"path": str(status_path), "payload": {**failure, "status": "failed"}},
        ],
    }


def _job_evidence(run: dict[str, Any] | None, job: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "run_id": (run or {}).get("id"),
        "run_status": (run or {}).get("status"),
        "run_conclusion": (run or {}).get("conclusion"),
        "run_url": (run or {}).get("html_url"),
        "run_created_at": (run or {}).get("created_at"),
        "job_id": (job or {}).get("id"),
        "job_name": (job or {}).get("name"),
        "job_status": (job or {}).get("status"),
        "conclusion": (job or {}).get("conclusion"),
        "job_started_at": (job or {}).get("started_at"),
        "job_completed_at": (job or {}).get("completed_at"),
    }


def _discover_job(
    *,
    client: GitHubClient,
    runs: list[dict[str, Any]],
    job_cache: dict[int, list[dict[str, Any]]],
    refreshed_run_ids: set[int],
    job_name: str,
    lower: datetime,
    upper: datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidates: list[dict[str, Any]] = []
    for run in runs:
        created = parse_timestamp(run.get("created_at"))
        if created is not None and lower <= created <= upper:
            candidates.append(run)
    candidates.sort(key=lambda item: str(item.get("created_at") or ""))
    for run in candidates:
        run_id = run.get("id")
        if not isinstance(run_id, int):
            continue
        jobs = job_cache.get(run_id)
        needs_refresh = (
            not jobs
            or any(item.get("status") != "completed" for item in jobs)
        )
        if needs_refresh and run_id not in refreshed_run_ids:
            payload = client.get(f"actions/runs/{run_id}/jobs", {"per_page": "100"})
            raw = payload.get("jobs", []) if isinstance(payload, dict) else []
            jobs = [item for item in raw if isinstance(item, dict)]
            job_cache[run_id] = jobs
            refreshed_run_ids.add(run_id)
        jobs = jobs or []
        for job in jobs:
            if job.get("name") == job_name and job.get("conclusion") != "skipped":
                return run, job
    return None, None


def capture_producer_states(
    *,
    client: GitHubClient,
    window: ValidationWindow,
    app_root: Path,
    job_cache: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    payload = client.get(
        "actions/workflows/surge_screener.yml/runs",
        {"event": "schedule", "per_page": "30"},
    )
    raw_runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    runs = [item for item in raw_runs if isinstance(item, dict)]
    refreshed_run_ids: set[int] = set()
    upper = window.recovery_deadline.astimezone(UTC)
    eod_run, eod_job = _discover_job(
        client=client,
        runs=runs,
        job_cache=job_cache,
        refreshed_run_ids=refreshed_run_ids,
        job_name="surge_scan",
        lower=window.eod_due.astimezone(UTC) - timedelta(minutes=20),
        upper=upper,
    )
    market_run = market_job = None
    if window.report_date.weekday() == 0:
        market_due = datetime.combine(window.report_date, wall_time(23, 0), UTC)
        market_run, market_job = _discover_job(
            client=client,
            runs=runs,
            job_cache=job_cache,
            refreshed_run_ids=refreshed_run_ids,
            job_name="market_thesis",
            lower=market_due - timedelta(minutes=20),
            upper=upper,
        )
    theme_status = read_json(app_root / "shared/run_status/theme-flow-refresh_board.json")
    theme_snapshot = read_json(app_root / "shared/theme_flow_snapshot.json")
    theme_gate = evaluate_theme(
        window,
        status=theme_status,
        unit=systemd_show(THEME_UNIT),
        snapshot=theme_snapshot,
    )
    return {
        "eod": {"run": eod_run, "job": eod_job},
        "market_thesis": {"run": market_run, "job": market_job},
        "theme_flow": {"gate": theme_gate, "status": theme_status},
    }


def evaluate_producer_readiness(
    window: ValidationWindow,
    producers: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    pending: list[str] = []
    evidence: dict[str, Any] = {}
    for name in ("eod", "market_thesis"):
        if name == "market_thesis" and window.report_date.weekday() != 0:
            continue
        item = producers.get(name) if isinstance(producers.get(name), dict) else {}
        run = item.get("run") if isinstance(item.get("run"), dict) else None
        job = item.get("job") if isinstance(item.get("job"), dict) else None
        state = classify_producer_state(run=run, job=job, artifact_present=None)
        evidence[name] = {"state": state, **_job_evidence(run, job)}
        if state in {"missing", "running"}:
            pending.append(f"{name} producer is {state}")
        elif state == "failed":
            reasons.append(f"{name} producer failed")
    theme = producers.get("theme_flow") if isinstance(producers.get("theme_flow"), dict) else {}
    theme_gate = theme.get("gate") if isinstance(theme.get("gate"), dict) else {}
    evidence["theme_flow"] = theme_gate
    if theme_gate.get("state") != "PASS":
        pending.extend(theme_gate.get("reasons") or ["Theme Flow is pending"])
    state = "FAIL" if reasons else ("PENDING" if pending else "PASS")
    return {"state": state, "reasons": reasons or pending, "evidence": evidence}


def _manifest_contract(manifest: dict[str, Any], kind: str) -> dict[str, Any]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    for item in artifacts:
        if isinstance(item, dict) and item.get("kind") == kind:
            return item.get("contract") if isinstance(item.get("contract"), dict) else {}
    return {}


def _runtime_producer_evidence(readiness: dict[str, Any]) -> dict[str, Any]:
    evidence = readiness.get("evidence") if isinstance(readiness.get("evidence"), dict) else {}
    result: dict[str, Any] = {}
    for name in ("eod", "market_thesis"):
        if name in evidence:
            result[name] = evidence[name]
    theme = evidence.get("theme_flow") if isinstance(evidence.get("theme_flow"), dict) else {}
    result["theme_flow"] = {
        "state": theme.get("state"),
        "unit": THEME_UNIT,
        "status": (theme.get("evidence") or {}).get("status"),
        "snapshot": (theme.get("evidence") or {}).get("snapshot"),
    }
    return result


def _provisional_analytics_worker(
    sender: Any,
    *,
    app_root: Path,
    prepared: PreparedReportGeneration,
    report_date: date,
    candidate_count: int,
    daily_outcome: str,
    verdict_path: Path,
    status_path: Path,
    timeliness: dict[str, Any] | None = None,
) -> None:
    """Build and provisionally promote in a killable child process."""
    try:
        validator = lambda checks, tables: validate_post_ingestion_checks(
            checks,
            tables,
            report_date=report_date,
            candidate_count=candidate_count,
            daily_outcome=daily_outcome,
        )
        transaction = (
            analytics_refresh_transaction.staged_analytics_refresh_transaction_locked(
                reports_root=app_root / "current/reports",
                published_reports_root=prepared.generation / "reports",
                analytics_root=app_root / "shared/data",
                checks_output=app_root / "shared/analytics_checks/latest.json",
                gate_validator=validator,
                promote_companion=lambda: promote_prepared_generation(prepared),
                recovery_context=build_transaction_recovery_context(
                    prepared=prepared,
                    report_date=report_date,
                    verdict_path=verdict_path,
                    status_path=status_path,
                    timeliness=timeliness,
                ),
            )
        )
        refresh = transaction.evidence
        checks = refresh.get("checks") if isinstance(refresh.get("checks"), dict) else {}
        rows = checks.get("checks") if isinstance(checks.get("checks"), list) else []
        projected_refresh = {
            "checks": {
                "status": checks.get("status"),
                "summary": checks.get("summary"),
                "checks": [
                    item for item in rows
                    if isinstance(item, dict) and item.get("id") in SELECTED_CHECK_IDS
                ],
            },
            "database": refresh.get("database", {}),
            "promoted_at": refresh.get("promoted_at"),
        }
        sender.send({
            "state": "READY",
            "refresh": projected_refresh,
            "backup": str(transaction.analytics_promotion.backup),
        })
    except BaseException as exc:  # noqa: BLE001 - parent terminalizes worker failures.
        try:
            sender.send({
                "state": "FAIL",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        sender.close()


def run_bounded_analytics_worker(
    *,
    app_root: Path,
    prepared: PreparedReportGeneration,
    report_date: date,
    candidate_count: int,
    daily_outcome: str,
    verdict_path: Path,
    status_path: Path,
    deadline: datetime,
    timeliness: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    """Return provisional evidence before deadline or terminate the worker."""
    require_before_deadline(deadline, stage="Analytics worker start")
    context = multiprocessing.get_context("fork")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_provisional_analytics_worker,
        kwargs={
            "sender": sender,
            "app_root": app_root,
            "prepared": prepared,
            "report_date": report_date,
            "candidate_count": candidate_count,
            "daily_outcome": daily_outcome,
            "verdict_path": verdict_path,
            "status_path": status_path,
            "timeliness": dict(timeliness or unknown_timeliness()),
        },
        name="surge-post-producer-analytics",
    )
    process.start()
    sender.close()
    remaining = max(0.0, remaining_window_seconds(deadline))
    process.join(remaining)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        receiver.close()
        raise ValidationDeadlineExceeded(
            "natural-validation deadline passed during Analytics build"
        )
    message = receiver.recv() if receiver.poll() else None
    receiver.close()
    if not isinstance(message, dict) or message.get("state") != "READY":
        if isinstance(message, dict):
            detail = f"{message.get('error_type')}: {message.get('error')}"
        else:
            detail = f"worker exit code {process.exitcode} without result"
        raise AnalyticsWorkerError(detail)
    refresh = message.get("refresh")
    backup = message.get("backup")
    if not isinstance(refresh, dict) or not isinstance(backup, str):
        raise AnalyticsWorkerError("worker returned an invalid provisional result")
    return refresh, Path(backup)


def run_observer(args: argparse.Namespace) -> int:
    local_date = date.fromisoformat(args.window_date)
    window = validation_window(local_date)
    app_root = Path(args.app_root).resolve()
    store = Path(args.published_store).resolve()
    status_path = Path(args.status_file).resolve()
    verdict_path = Path(args.verdict_file).resolve()
    shared_lock = app_root / "shared/locks/analytics-refresh.lock"
    timing = observation_timing(
        window,
        now=datetime.now(UTC),
        producer_state="PENDING",
    )
    try:
        with analytics_refresh_transaction.analytics_writer_lock(
            shared_lock,
            timeout_seconds=args.lock_timeout_seconds,
        ):
            recovered = analytics_refresh_transaction.recover_pending_analytics_promotions_locked(
                app_root / "shared/data"
            )
            recovered_failure = any(
                item.get("failure_evidence_published") for item in recovered
            )
            if recovered_failure:
                verdict = read_json(verdict_path)
                recovery_timing = observation_timing(
                    window,
                    now=datetime.now(UTC),
                    producer_state="FAIL",
                )["evidence"]
                verdict["schema_version"] = POST_INGESTION_SCHEMA_VERSION
                verdict["captured_at"] = iso_utc()
                verdict["timeliness"] = recovery_timing
                atomic_write_json(verdict_path, verdict)
                atomic_write_json(status_path, {**verdict, "status": "failed"})
    except Exception as exc:  # noqa: BLE001 - recovery failures use the canonical terminal schema.
        failure_timing = observation_timing(
            window,
            now=datetime.now(UTC),
            producer_state="FAIL",
        )
        verdict = build_post_ingestion_verdict(
            state="FAIL",
            report_date=window.report_date,
            manifest={},
            refresh={},
            reasons=[f"crash recovery failed: {type(exc).__name__}: {exc}"],
            timeliness=failure_timing["evidence"],
        )
        atomic_write_json(verdict_path, verdict)
        atomic_write_json(status_path, {**verdict, "status": "failed"})
        print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
        return 1
    if recovered_failure:
        verdict = read_json(verdict_path)
        print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
        return 1

    client = GitHubClient(args.repository)
    job_cache: dict[int, list[dict[str, Any]]] = {}
    while True:
        try:
            producers = capture_producer_states(
                client=client,
                window=window,
                app_root=app_root,
                job_cache=job_cache,
            )
            readiness = evaluate_producer_readiness(window, producers)
        except GitHubApiError as exc:
            readiness = {"state": "PENDING", "reasons": [str(exc)], "evidence": {}}
        now = datetime.now(UTC)
        timing = observation_timing(
            window,
            now=now,
            producer_state=str(readiness.get("state") or "PENDING"),
        )
        status = {
            "schema_version": POST_INGESTION_SCHEMA_VERSION,
            "updated_at": iso_utc(now),
            "status": (
                "late_waiting"
                if timing["evidence"]["state"] == "WAITING_LATE"
                else "running" if readiness["state"] == "PENDING"
                else readiness["state"].lower()
            ),
            "window_date": local_date.isoformat(),
            "report_date": window.report_date.isoformat(),
            "producer_gate": readiness,
            "timeliness": timing["evidence"],
        }
        atomic_write_json(status_path, status)
        if readiness["state"] == "FAIL":
            verdict = build_post_ingestion_verdict(
                state="FAIL",
                report_date=window.report_date,
                manifest={"producers": _runtime_producer_evidence(readiness)},
                refresh={},
                reasons=list(readiness.get("reasons") or ["producer gate failed"]),
                timeliness=timing["evidence"],
            )
            atomic_write_json(verdict_path, verdict)
            atomic_write_json(status_path, {**verdict, "status": "failed", "producer_gate": readiness})
            return 1
        if timing["action"] == "PROCEED":
            break
        if timing["action"] == "FAIL":
            readiness = {
                **readiness,
                "state": "FAIL",
                "reasons": [
                    *(readiness.get("reasons") or []),
                    "producer gate remained pending at late-recovery deadline",
                ],
            }
            verdict = build_post_ingestion_verdict(
                state="FAIL",
                report_date=window.report_date,
                manifest={"producers": _runtime_producer_evidence(readiness)},
                refresh={},
                reasons=list(readiness["reasons"]),
                timeliness=timing["evidence"],
            )
            atomic_write_json(verdict_path, verdict)
            atomic_write_json(status_path, {**verdict, "status": "failed", "producer_gate": readiness})
            return 1
        remaining = remaining_window_seconds(window.recovery_deadline, now=now)
        observer_sleep(min(args.poll_seconds, max(0.0, remaining)))

    manifest: dict[str, Any] = {"producers": _runtime_producer_evidence(readiness)}
    refresh: dict[str, Any] = {}
    source_sha: str | None = None
    artifact_attempt = 0
    while True:
        artifact_attempt += 1
        try:
            with analytics_refresh_transaction.analytics_writer_lock(
                shared_lock,
                timeout_seconds=bounded_lock_timeout(
                    window.recovery_deadline,
                    args.lock_timeout_seconds,
                ),
            ):
                require_before_deadline(
                    window.recovery_deadline,
                    stage="artifact preparation",
                )
                if source_sha is None:
                    source_sha = resolve_main_sha(client)
                prepared = prepare_published_reports(
                    client=client,
                    store_root=store,
                    report_date=window.report_date,
                    producer_evidence=_runtime_producer_evidence(readiness),
                    source_sha=source_sha,
                )
                manifest = prepared.manifest
                candidate_contract = _manifest_contract(manifest, "candidate_scores")
                daily_contract = _manifest_contract(manifest, "daily_summary")
                try:
                    refresh, backup = run_bounded_analytics_worker(
                        app_root=app_root,
                        prepared=prepared,
                        report_date=window.report_date,
                        candidate_count=int(
                            candidate_contract.get("scored_cohort_count") or 0
                        ),
                        daily_outcome=str(daily_contract.get("outcome") or ""),
                        verdict_path=verdict_path,
                        status_path=status_path,
                        deadline=window.recovery_deadline,
                        timeliness=timing["evidence"],
                    )
                    final_timing = observation_timing(
                        window,
                        now=datetime.now(UTC),
                        producer_state="PASS",
                    )
                    require_before_deadline(
                        window.recovery_deadline,
                        stage="PASS verdict persistence",
                    )
                    verdict = build_post_ingestion_verdict(
                        state="PASS",
                        report_date=window.report_date,
                        manifest=manifest,
                        refresh=refresh,
                        timeliness=final_timing["evidence"],
                    )
                    atomic_write_json(verdict_path, verdict)
                    atomic_write_json(status_path, {**verdict, "status": "succeeded"})
                    require_before_deadline(
                        window.recovery_deadline,
                        stage="transaction commit",
                    )
                    analytics_refresh_transaction.commit_pending_analytics_promotion_locked(
                        app_root / "shared/data",
                        backup,
                    )
                except Exception as analytics_exc:  # noqa: BLE001 - recover under this lock.
                    try:
                        analytics_refresh_transaction.recover_pending_analytics_promotions_locked(
                            app_root / "shared/data"
                        )
                    except Exception as recovery_exc:  # noqa: BLE001 - retain both causes.
                        analytics_exc = RuntimeError(
                            "Analytics worker failed and recovery was incomplete: "
                            f"{type(analytics_exc).__name__}: {analytics_exc}; "
                            f"{type(recovery_exc).__name__}: {recovery_exc}"
                        )
                    failure = build_post_ingestion_verdict(
                        state="FAIL",
                        report_date=window.report_date,
                        manifest=manifest,
                        refresh=refresh,
                        reasons=[f"{type(analytics_exc).__name__}: {analytics_exc}"],
                        timeliness=observation_timing(
                            window,
                            now=datetime.now(UTC),
                            producer_state="FAIL",
                        )["evidence"],
                    )
                    atomic_write_json(verdict_path, failure)
                    atomic_write_json(status_path, {**failure, "status": "failed"})
                    print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
                    return 1
            print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
            return 0
        except (
            GitHubApiError,
            UnpublishedArtifactError,
            analytics_refresh_transaction.AnalyticsWriterLockTimeout,
        ) as exc:
            now = datetime.now(UTC)
            timing = observation_timing(
                window,
                now=now,
                producer_state="PENDING",
            )
            remaining = remaining_window_seconds(window.recovery_deadline, now=now)
            if remaining <= 0:
                terminal_error: Exception = exc
                break
            try:
                atomic_write_json(status_path, {
                    "schema_version": POST_INGESTION_SCHEMA_VERSION,
                    "updated_at": iso_utc(now),
                    "status": (
                        "late_waiting"
                        if timing["evidence"]["state"] == "WAITING_LATE"
                        else "running"
                    ),
                    "window_date": local_date.isoformat(),
                    "report_date": window.report_date.isoformat(),
                    "producer_gate": readiness,
                    "timeliness": timing["evidence"],
                    "artifact_gate": {
                        "state": "PENDING",
                        "attempt": artifact_attempt,
                        "reasons": [f"{type(exc).__name__}: {exc}"],
                    },
                })
            except Exception as status_exc:  # noqa: BLE001 - terminalized below.
                terminal_error = RuntimeError(
                    "artifact retry status persistence failed: "
                    f"{type(status_exc).__name__}: {status_exc}"
                )
                break
            observer_sleep(min(args.artifact_retry_seconds, remaining))
        except Exception as exc:  # noqa: BLE001 - canonical terminal failure below.
            terminal_error = exc
            break

    verdict = build_post_ingestion_verdict(
        state="FAIL",
        report_date=window.report_date,
        manifest=manifest,
        refresh=refresh,
        reasons=[f"{type(terminal_error).__name__}: {terminal_error}"],
        timeliness=observation_timing(
            window,
            now=datetime.now(UTC),
            producer_state="FAIL",
        )["evidence"],
    )
    atomic_write_json(verdict_path, verdict)
    atomic_write_json(status_path, {**verdict, "status": "failed"})
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 1


def main(argv: list[str] | None = None) -> int:
    default_root = Path(os.environ.get("SURGE_APP_ROOT", "/home/kenny/apps/surge-screener"))
    parser = argparse.ArgumentParser(description="Post-producer report ingestion and Analytics refresh")
    parser.add_argument("--window-date", default=datetime.now(TAIPEI).date().isoformat())
    parser.add_argument("--app-root", default=str(default_root))
    parser.add_argument("--repository", default="KennyHsiao/surge-screener")
    parser.add_argument("--published-store", default=str(default_root / "shared/published_reports"))
    parser.add_argument("--status-file", default=str(default_root / "shared/run_status/post-producer-analytics.json"))
    parser.add_argument("--verdict-file", default=str(default_root / "shared/post_ingestion/latest.json"))
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--artifact-retry-seconds", type=int, default=60)
    parser.add_argument("--lock-timeout-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    date.fromisoformat(args.window_date)
    if args.poll_seconds < 30:
        parser.error("--poll-seconds must be at least 30")
    if args.artifact_retry_seconds < 30:
        parser.error("--artifact-retry-seconds must be at least 30")
    if args.lock_timeout_seconds < 1:
        parser.error("--lock-timeout-seconds must be positive")
    return run_observer(args)


if __name__ == "__main__":
    raise SystemExit(main())
