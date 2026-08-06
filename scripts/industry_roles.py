#!/usr/bin/env python3
"""Industry-chain role taxonomy, suggestions, and review actions.

This module is intentionally UI-free. Streamlit pages use it to display and
persist review decisions, while trading pages use approved labels as overlays.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from runtime_paths import REPO
except ImportError:  # imported as scripts.industry_roles
    from scripts.runtime_paths import REPO

try:
    from scripts import industry_role_store as review_store
except ImportError:  # executed directly from the scripts directory
    import industry_role_store as review_store


TAXONOMY_FILE = "industry_roles.json"
OVERRIDES_FILE = "industry_role_overrides.json"
SUGGESTIONS_FILE = "industry_role_suggestions.json"
REVIEWED_STATUSES = {"approved", "rejected", "deferred"}
CLASSIFICATION_PENDING_ROLE = "classification_pending"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return date.today().isoformat()


def _json_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _content_dir(path: Path | str | None = None) -> Path:
    return Path(path) if path is not None else REPO / "content"


def _reports_dir(path: Path | str | None = None) -> Path:
    return Path(path) if path is not None else REPO / "reports"


def load_taxonomy(content_dir: Path | str | None = None) -> dict[str, Any]:
    payload = _read_json(_content_dir(content_dir) / TAXONOMY_FILE, {"version": 1, "roles": {}})
    roles = payload.get("roles") if isinstance(payload, dict) else {}
    return {"version": payload.get("version", 1) if isinstance(payload, dict) else 1,
            "roles": roles if isinstance(roles, dict) else {}}


def _load_legacy_overrides(content_dir: Path | str | None = None) -> dict[str, Any]:
    payload = _read_json(_content_dir(content_dir) / OVERRIDES_FILE, {"version": 1, "tickers": {}})
    tickers = payload.get("tickers") if isinstance(payload, dict) else {}
    return {"version": payload.get("version", 1) if isinstance(payload, dict) else 1,
            "tickers": tickers if isinstance(tickers, dict) else {}}


def _load_legacy_suggestions(reports_dir: Path | str | None = None) -> dict[str, Any]:
    payload = _read_json(_reports_dir(reports_dir) / SUGGESTIONS_FILE, {"generated_at": None, "suggestions": []})
    suggestions = payload.get("suggestions") if isinstance(payload, dict) else []
    return {
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "suggestions": suggestions if isinstance(suggestions, list) else [],
    }


def load_review_state(
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
) -> review_store.ReviewSnapshot:
    """Read the canonical aggregate or its side-effect-free legacy seed."""

    taxonomy = load_taxonomy(content_dir)
    return review_store.read_review_state(
        review_store.canonical_state_path(_reports_dir(reports_dir)),
        int(taxonomy.get("version", 1)),
        _load_legacy_overrides(content_dir),
        _load_legacy_suggestions(reports_dir),
    )


def load_overrides(
    content_dir: Path | str | None = None,
    *,
    reports_dir: Path | str | None = None,
) -> dict[str, Any]:
    state_path = review_store.canonical_state_path(_reports_dir(reports_dir))
    if (reports_dir is not None or content_dir is None) and (
        state_path.exists() or state_path.is_symlink()
    ):
        return load_review_state(
            content_dir=content_dir,
            reports_dir=reports_dir,
        ).overrides
    return _load_legacy_overrides(content_dir)


def load_suggestions(
    reports_dir: Path | str | None = None,
    *,
    content_dir: Path | str | None = None,
) -> dict[str, Any]:
    state_path = review_store.canonical_state_path(_reports_dir(reports_dir))
    if (content_dir is not None or reports_dir is None) and (
        state_path.exists() or state_path.is_symlink()
    ):
        return load_review_state(
            content_dir=content_dir,
            reports_dir=reports_dir,
        ).suggestions
    return _load_legacy_suggestions(reports_dir)


def load_approved_tickers(
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
) -> list[str]:
    """Return canonical-first approved tickers for fail-soft batch enrichment.

    A missing canonical state may use the revision-zero legacy seed. Once a
    canonical path exists, an invalid state returns no Industry Roles tickers
    and never falls back to stale legacy data.
    """

    try:
        overrides = load_overrides(content_dir, reports_dir=reports_dir)
    except review_store.ReviewStateError:
        return []
    tickers = overrides.get("tickers") if isinstance(overrides, dict) else None
    if not isinstance(tickers, dict):
        return []
    out: list[str] = []
    for ticker in sorted(tickers):
        normalized = str(ticker or "").upper().strip().lstrip("$")
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _load_theme_baskets(content_dir: Path | str | None = None) -> dict[str, Any]:
    return _read_json(_content_dir(content_dir) / "theme_baskets.json", {"themes": {}})


def _role_name(taxonomy: dict[str, Any], role_id: str | None) -> str | None:
    if not role_id:
        return None
    role = (taxonomy.get("roles") or {}).get(role_id) or {}
    return role.get("name") or role_id


def _role_basket_names(role: dict[str, Any]) -> list[str]:
    names = role.get("theme_baskets") or role.get("themes") or []
    return [str(name) for name in names if str(name).strip()]


def _theme_items(theme_baskets: dict[str, Any]) -> list[tuple[str, set[str]]]:
    themes = theme_baskets.get("themes") if isinstance(theme_baskets, dict) else {}
    if isinstance(themes, dict):
        out = []
        for name, cfg in themes.items():
            if isinstance(cfg, dict):
                out.append((str(name), {str(t).upper() for t in cfg.get("tickers", [])}))
        return out
    baskets = theme_baskets.get("baskets") if isinstance(theme_baskets, dict) else []
    if isinstance(baskets, list):
        return [
            (str(item.get("theme") or item.get("name") or ""), {str(t).upper() for t in item.get("tickers", [])})
            for item in baskets
            if isinstance(item, dict)
        ]
    return []


def suggest_roles(
    tickers: list[str] | tuple[str, ...] | set[str],
    *,
    taxonomy: dict[str, Any] | None = None,
    theme_baskets: dict[str, Any] | None = None,
    social: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic role suggestions from curated theme-basket evidence."""
    taxonomy = taxonomy or {"roles": {}}
    theme_baskets = theme_baskets or {"themes": {}}
    theme_map = dict(_theme_items(theme_baskets))
    out: list[dict[str, Any]] = []
    for ticker in sorted({str(t).upper().strip() for t in tickers if str(t).strip()}):
        matches: list[tuple[str, str]] = []
        for role_id, role in (taxonomy.get("roles") or {}).items():
            for basket_name in _role_basket_names(role):
                if ticker in theme_map.get(basket_name, set()):
                    matches.append((role_id, basket_name))
                    break
        if not matches:
            continue
        primary_role, basket_name = matches[0]
        secondary_roles = [role_id for role_id, _name in matches[1:]]
        evidence = [f"theme_baskets: {basket_name}"]
        if social and ticker in social:
            evidence.append("social_heat: mentioned in current social sources")
        out.append({
            "ticker": ticker,
            "suggested_primary_role": primary_role,
            "suggested_primary_role_name": _role_name(taxonomy, primary_role),
            "suggested_secondary_roles": secondary_roles,
            "confidence": 0.86 if len(matches) == 1 else 0.9,
            "evidence": evidence,
            "status": "suggested",
        })
    return out


def _pending_classification_suggestion(ticker: str) -> dict[str, Any]:
    return {
        "ticker": str(ticker).upper().strip().lstrip("$"),
        "suggested_primary_role": CLASSIFICATION_PENDING_ROLE,
        "suggested_primary_role_name": "待分類",
        "suggested_secondary_roles": [],
        "confidence": 0.0,
        "evidence": ["fallback: no taxonomy/theme match yet"],
        "status": "suggested",
    }


def _suggestion_key(suggestion: dict[str, Any]) -> tuple[str, str]:
    ticker = str(suggestion.get("ticker") or "").upper().strip()
    role = str(suggestion.get("suggested_primary_role") or "").strip()
    return ticker, role


def _merge_review_state(
    generated: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    *,
    taxonomy: dict[str, Any],
) -> list[dict[str, Any]]:
    existing_by_key = {
        _suggestion_key(item): item
        for item in existing
        if isinstance(item, dict) and all(_suggestion_key(item))
    }
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in generated:
        row = dict(item)
        key = _suggestion_key(row)
        seen.add(key)
        previous = existing_by_key.get(key)
        if previous and previous.get("status") in REVIEWED_STATUSES:
            row["status"] = previous["status"]
            for field in ("reviewed_at", "reviewed_by"):
                if previous.get(field):
                    row[field] = previous[field]
        merged.append(row)

    for item in existing:
        if not isinstance(item, dict):
            continue
        key = _suggestion_key(item)
        if key in seen or item.get("status") not in REVIEWED_STATUSES:
            continue
        row = dict(item)
        role_id = row.get("suggested_primary_role")
        row.setdefault("suggested_primary_role_name", _role_name(taxonomy, role_id))
        merged.append(row)

    return merged


def generate_suggestions(
    tickers: list[str] | tuple[str, ...] | set[str],
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
) -> dict[str, Any]:
    request = {
        "action": "generate",
        "tickers": sorted(
            {str(t).upper().strip().lstrip("$") for t in tickers if str(t).strip()}
        ),
    }
    snapshot = load_review_state(content_dir=content_dir, reports_dir=reports_dir)
    mutate_review_board_action(
        request,
        content_dir=content_dir,
        reports_dir=reports_dir,
        expected_etag=snapshot.etag,
        idempotency_key=str(uuid.uuid4()),
    )
    return load_review_state(
        content_dir=content_dir,
        reports_dir=reports_dir,
    ).suggestions


def _generate_transition(
    tickers: list[str],
    *,
    taxonomy: dict[str, Any],
    baskets: dict[str, Any],
    generated_at: str,
    overrides: dict[str, Any],
    suggestions: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    generated = suggest_roles(tickers, taxonomy=taxonomy, theme_baskets=baskets)
    generated_tickers = {
        str(item.get("ticker") or "").upper().strip() for item in generated
    }
    approved_tickers = {
        str(ticker).upper().strip().lstrip("$")
        for ticker, config in (overrides.get("tickers") or {}).items()
        if isinstance(config, dict) and config.get("primary_role")
    }
    for ticker in tickers:
        if ticker in generated_tickers or ticker in approved_tickers:
            continue
        generated.append(_pending_classification_suggestion(ticker))
    return overrides, {
        "generated_at": generated_at,
        "suggestions": _merge_review_state(
            generated,
            suggestions.get("suggestions", []),
            taxonomy=taxonomy,
        ),
    }


def _suggestion_for(ticker: str, suggestions: list[dict[str, Any]]) -> dict[str, Any] | None:
    sym = ticker.upper()
    for suggestion in suggestions:
        if str(suggestion.get("ticker") or "").upper() == sym:
            return suggestion
    return None


def resolve_role(
    ticker: str,
    *,
    taxonomy: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    suggestions: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    taxonomy = taxonomy or {"roles": {}}
    overrides = overrides or {"tickers": {}}
    sym = str(ticker).upper()
    approved = (overrides.get("tickers") or {}).get(sym)
    if isinstance(approved, dict) and approved.get("primary_role"):
        role_id = str(approved.get("primary_role"))
        return {
            "ticker": sym,
            "source": "approved",
            "status": "approved",
            "primary_role": role_id,
            "primary_role_name": _role_name(taxonomy, role_id),
            "secondary_roles": approved.get("secondary_roles") or [],
            "confidence": approved.get("confidence"),
            "display_role": _role_name(taxonomy, role_id) or role_id,
            "evidence": approved.get("evidence") or [],
        }

    suggestion_rows = suggestions.get("suggestions", []) if isinstance(suggestions, dict) else (suggestions or [])
    suggestion = _suggestion_for(sym, suggestion_rows)
    if suggestion and suggestion.get("status", "suggested") == "suggested":
        role_id = str(suggestion.get("suggested_primary_role") or "")
        role_name = suggestion.get("suggested_primary_role_name") or _role_name(taxonomy, role_id)
        source = "classification_pending" if role_id == CLASSIFICATION_PENDING_ROLE else "suggested"
        return {
            "ticker": sym,
            "source": source,
            "status": "suggested",
            "primary_role": role_id,
            "primary_role_name": role_name,
            "secondary_roles": suggestion.get("suggested_secondary_roles") or [],
            "confidence": suggestion.get("confidence"),
            "display_role": f"待審核: {role_name or role_id}",
            "evidence": suggestion.get("evidence") or [],
        }

    return {
        "ticker": sym,
        "source": "classification_pending",
        "status": "suggested",
        "primary_role": CLASSIFICATION_PENDING_ROLE,
        "primary_role_name": "待分類",
        "secondary_roles": [],
        "confidence": 0.0,
        "display_role": "待審核: 待分類",
        "evidence": ["fallback: no taxonomy/theme match yet"],
    }


def review_suggestion(
    ticker: str,
    action: str,
    *,
    primary_role: str | None = None,
    secondary_roles: list[str] | None = None,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Compatibility shell over the canonical review-state transaction."""

    normalized_action = action.lower().strip()
    request: dict[str, Any] = {
        "action": normalized_action,
        "ticker": str(ticker).upper(),
    }
    if normalized_action == "approve":
        snapshot = load_review_state(content_dir=content_dir, reports_dir=reports_dir)
        suggestion = _suggestion_for(
            str(ticker),
            snapshot.suggestions.get("suggestions", []),
        )
        role_id = primary_role or (
            suggestion.get("suggested_primary_role") if suggestion else None
        )
        request["primaryRole"] = role_id
        request["secondaryRoles"] = (
            secondary_roles
            if secondary_roles is not None
            else (suggestion.get("suggested_secondary_roles", []) if suggestion else [])
        )
    else:
        snapshot = load_review_state(content_dir=content_dir, reports_dir=reports_dir)
    mutate_review_board_action(
        request,
        content_dir=content_dir,
        reports_dir=reports_dir,
        expected_etag=snapshot.etag,
        idempotency_key=str(uuid.uuid4()),
    )
    current = load_review_state(content_dir=content_dir, reports_dir=reports_dir)
    reviewed = _suggestion_for(
        str(ticker),
        current.suggestions.get("suggestions", []),
    )
    if reviewed is None:
        raise KeyError(f"missing suggestion for {ticker}")
    return reviewed


def _review_transition(
    *,
    request: dict[str, Any],
    taxonomy: dict[str, Any],
    reviewed_at: str,
    overrides: dict[str, Any],
    suggestions: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    action = str(request.get("action") or "").lower()
    if action not in {"approve", "reject", "defer"}:
        raise ValueError(f"unsupported review action: {action}")
    ticker = str(request.get("ticker") or "").upper()
    rows = suggestions.get("suggestions", [])
    suggestion = _suggestion_for(ticker, rows)
    if suggestion is None:
        raise KeyError(f"missing suggestion for {ticker}")
    if action == "approve":
        role_id = request.get("primaryRole")
        secondary = request.get("secondaryRoles")
        known_roles = taxonomy.get("roles") or {}
        if not isinstance(role_id, str) or role_id not in known_roles:
            raise ValueError("approve requires a declared primary role")
        if not isinstance(secondary, list) or any(
            not isinstance(role, str) or role not in known_roles for role in secondary
        ):
            raise ValueError("approve requires declared secondary roles")
        if role_id in secondary or len(secondary) != len(set(secondary)):
            raise ValueError("approve roles must be distinct")
        overrides.setdefault("tickers", {})[ticker] = {
            "primary_role": role_id,
            "secondary_roles": list(secondary),
            "confidence": suggestion.get("confidence"),
            "reviewed_at": reviewed_at,
            "reviewed_by": "operator",
            "evidence": suggestion.get("evidence") or [],
        }
        suggestion["status"] = "approved"
    elif action == "reject":
        suggestion["status"] = "rejected"
    else:
        suggestion["status"] = "deferred"
    suggestion["reviewed_at"] = reviewed_at
    return overrides, suggestions


def mutate_review_board_action(
    request: dict[str, Any],
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
    state_path: Path | str | None = None,
    expected_etag: str,
    idempotency_key: str,
) -> review_store.ReviewMutation:
    """Apply one API-shaped action through the shared atomic aggregate."""

    taxonomy = load_taxonomy(content_dir)
    taxonomy_version = int(taxonomy.get("version", 1))
    action = str(request.get("action") or "").lower()
    now = _now()
    tickers = request.get("tickers")
    if action == "generate":
        if not isinstance(tickers, list) or not tickers:
            raise ValueError("generate requires tickers")
        normalized = [str(ticker).upper() for ticker in tickers]
        baskets = _load_theme_baskets(content_dir)

        def transform(
            overrides: dict[str, Any],
            suggestions: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return _generate_transition(
                normalized,
                taxonomy=taxonomy,
                baskets=baskets,
                generated_at=now,
                overrides=overrides,
                suggestions=suggestions,
            )

        ticker = None
    else:

        def transform(
            overrides: dict[str, Any],
            suggestions: dict[str, Any],
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return _review_transition(
                request=request,
                taxonomy=taxonomy,
                reviewed_at=now,
                overrides=overrides,
                suggestions=suggestions,
            )

        ticker = str(request.get("ticker") or "").upper() or None
    return review_store.mutate_review_state(
        state_path=(
            Path(state_path)
            if state_path is not None
            else review_store.canonical_state_path(_reports_dir(reports_dir))
        ),
        taxonomy_version=taxonomy_version,
        legacy_overrides=_load_legacy_overrides(content_dir),
        legacy_suggestions=_load_legacy_suggestions(reports_dir),
        expected_etag=expected_etag,
        idempotency_key=idempotency_key,
        request=request,
        action=action,
        ticker=ticker,
        transform=transform,
        now=now,
    )


def approved_rows(
    *,
    taxonomy: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    taxonomy = taxonomy or load_taxonomy()
    overrides = overrides or load_overrides()
    rows = []
    for ticker, cfg in sorted((overrides.get("tickers") or {}).items()):
        role_id = cfg.get("primary_role")
        rows.append({
            "ticker": ticker,
            "primary_role": role_id,
            "role": _role_name(taxonomy, role_id),
            "secondary_roles": ", ".join(_role_name(taxonomy, rid) or rid for rid in cfg.get("secondary_roles", [])),
            "confidence": cfg.get("confidence"),
            "reviewed_at": cfg.get("reviewed_at"),
        })
    return rows


def _assignment_row(
    *,
    as_of_date: str,
    ticker: str,
    primary_role_id: str | None,
    primary_role_name: str | None,
    secondary_role_ids: list[str],
    status: str,
    confidence: Any,
    source: str,
    evidence: list[Any],
    reviewed_at: Any,
    taxonomy_version: Any,
) -> dict[str, Any]:
    return {
        "as_of_date": as_of_date,
        "ticker": str(ticker or "").upper().lstrip("$"),
        "primary_role_id": primary_role_id,
        "primary_role_name": primary_role_name,
        "secondary_role_ids_json": _json_blob(secondary_role_ids or []),
        "status": status,
        "confidence": confidence,
        "source": source,
        "evidence_json": _json_blob(evidence or []),
        "reviewed_at": reviewed_at,
        "taxonomy_version": taxonomy_version,
    }


def build_role_assignment_snapshot(
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
    as_of_date: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build dated rows for displayable approved/suggested role assignments."""
    snapshot_date = str(as_of_date or _today())[:10]
    taxonomy = load_taxonomy(content_dir)
    overrides = load_overrides(content_dir, reports_dir=reports_dir)
    suggestions = load_suggestions(reports_dir, content_dir=content_dir)
    taxonomy_version = taxonomy.get("version", 1)
    rows: list[dict[str, Any]] = []
    approved_tickers: set[str] = set()

    for ticker, cfg in sorted((overrides.get("tickers") or {}).items()):
        if not isinstance(cfg, dict):
            continue
        role_id = cfg.get("primary_role")
        if not role_id:
            continue
        sym = str(ticker or "").upper().lstrip("$")
        approved_tickers.add(sym)
        secondary = [str(role) for role in cfg.get("secondary_roles", []) if str(role).strip()]
        rows.append(_assignment_row(
            as_of_date=snapshot_date,
            ticker=sym,
            primary_role_id=str(role_id),
            primary_role_name=_role_name(taxonomy, str(role_id)),
            secondary_role_ids=secondary,
            status="approved",
            confidence=cfg.get("confidence"),
            source="approved_override",
            evidence=cfg.get("evidence") or [],
            reviewed_at=cfg.get("reviewed_at"),
            taxonomy_version=taxonomy_version,
        ))

    for suggestion in suggestions.get("suggestions", []):
        if not isinstance(suggestion, dict):
            continue
        status = str(suggestion.get("status") or "suggested").lower()
        if status != "suggested":
            continue
        sym = str(suggestion.get("ticker") or "").upper().lstrip("$")
        if not sym or sym in approved_tickers:
            continue
        role_id = str(suggestion.get("suggested_primary_role") or "")
        if not role_id:
            continue
        secondary = [
            str(role) for role in suggestion.get("suggested_secondary_roles", [])
            if str(role).strip()
        ]
        rows.append(_assignment_row(
            as_of_date=snapshot_date,
            ticker=sym,
            primary_role_id=role_id,
            primary_role_name=suggestion.get("suggested_primary_role_name") or _role_name(taxonomy, role_id),
            secondary_role_ids=secondary,
            status="suggested",
            confidence=suggestion.get("confidence"),
            source="suggestion_engine",
            evidence=suggestion.get("evidence") or [],
            reviewed_at=suggestion.get("reviewed_at"),
            taxonomy_version=taxonomy_version,
        ))

    rows.sort(key=lambda row: (row.get("ticker") or "", row.get("status") or ""))
    return {
        "as_of_date": snapshot_date,
        "generated_at": generated_at or _now(),
        "source": "industry_roles",
        "row_count": len(rows),
        "rows": rows,
    }


def write_role_assignment_snapshot(
    snapshot: dict[str, Any],
    *,
    reports_dir: Path | str | None = None,
) -> Path:
    reports = _reports_dir(reports_dir)
    as_of = str(snapshot.get("as_of_date") or _today())[:10]
    out_dir = reports / "industry_roles"
    out = out_dir / f"{as_of}.json"
    latest = out_dir / "latest.json"
    _write_json(out, snapshot)
    _write_json(latest, snapshot)
    return out


def refresh_role_assignment_snapshot(
    *,
    content_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    snapshot = build_role_assignment_snapshot(
        content_dir=content_dir,
        reports_dir=reports_dir,
        as_of_date=as_of_date,
    )
    out = write_role_assignment_snapshot(snapshot, reports_dir=reports_dir)
    return {"path": str(out), **snapshot}


if __name__ == "__main__":
    import sys
    symbols = sys.argv[1:] or ["NVDA", "AMD", "DELL", "MU"]
    print(json.dumps(generate_suggestions(symbols), ensure_ascii=False, indent=2))
