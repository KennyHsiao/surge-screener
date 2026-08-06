#!/usr/bin/env python3
"""Focused API/client/page contracts for Phase 4E Reversal/Oversold snapshots."""

from __future__ import annotations

import ast
import copy
import json
import sys
import tempfile
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import ARTIFACTS, ArtifactSpec, ResolvedArtifactPath, read_artifact  # noqa: E402
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    OversoldReversalData,
    OversoldReversalValidationData,
    ReversalRadarData,
    ReversalRadarValidationData,
)
from ui import _read_api, oversold_reversal_lane, radar  # noqa: E402


REVERSAL_SOURCE_ID = "signals.reversal-radar.latest"
OVERSOLD_SOURCE_ID = "signals.oversold-reversal.latest"
OVERSOLD_VALIDATION_SOURCE_ID = "signals.oversold-reversal.validation"
REVERSAL_VALIDATION_SOURCE_ID = "signals.reversal-radar.validation"
REVERSAL_ROUTE = "/api/v1/signals/reversal-radar/latest"
REVERSAL_VALIDATION_ROUTE = "/api/v1/signals/reversal-radar/validation"
OVERSOLD_ROUTE = "/api/v1/signals/oversold-reversal/latest"
OVERSOLD_VALIDATION_ROUTE = "/api/v1/signals/oversold-reversal/validation"
REVERSAL_URL = f"http://127.0.0.1:8000{REVERSAL_ROUTE}"
OVERSOLD_URL = f"http://127.0.0.1:8000{OVERSOLD_ROUTE}"
OVERSOLD_VALIDATION_URL = f"http://127.0.0.1:8000{OVERSOLD_VALIDATION_ROUTE}"
REVERSAL_VALIDATION_URL = f"http://127.0.0.1:8000{REVERSAL_VALIDATION_ROUTE}"
REVERSAL_PUBLIC_FIELDS = {
    "as_of_date",
    "generated_at",
    "lane_id",
    "universe",
    "match_count",
    "candidates",
}
OVERSOLD_PUBLIC_FIELDS = {
    "as_of_date",
    "generated_at",
    "lane_id",
    "universe",
    "runway_independent",
    "match_count",
    "scanned",
    "definition",
    "validation",
    "validation_caveats",
    "candidates",
    "note",
}
OVERSOLD_CANDIDATE_FIELDS = {
    "ticker",
    "last_price",
    "rsi14",
    "bb_width_pct",
    "pct_vs_ma200",
    "pct_from_52w_high",
    "avg_dollar_vol_m",
}
OVERSOLD_VALIDATION_FIELDS = {
    "entries_accumulated",
    "min_resolved_across_tiers",
    "min_resolved_for_verdict",
    "verdict",
    "by_tier",
}
OVERSOLD_VALIDATION_TIER_FIELDS = {
    "resolved",
    "hits",
    "hit_rate",
    "wilson90",
}
OVERSOLD_VALIDATION_TIERS = ("+30%/20d", "+40%/40d", "+50%/60d")
REVERSAL_VALIDATION_FIELDS = {
    "entries_accumulated",
    "min_resolved_across_tiers",
    "min_resolved_for_verdict",
    "verdict",
    "by_tier",
}
REVERSAL_VALIDATION_TIER_FIELDS = {
    "resolved",
    "hits",
    "hit_rate",
    "wilson90",
}
REVERSAL_VALIDATION_TIERS = ("+10%/20d", "+15%/40d", "+20%/60d")


def _reversal_source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of_date": "2026-08-01",
        "generated_at": "2026-08-01T03:04:05.123456+00:00",
        "lane_id": "reversal_radar.v1.structure+momentum",
        "universe": "beaten_down_prescreen",
        "universe_size": 1500,
        "scanned": 2,
        "match_count": 2,
        "improving_sectors": ["Technology"],
        "prescreen": {"source": "coiled_base"},
        "candidates": [
            {
                "ticker": "NVDA",
                "reversal_score": 72,
                "data_confidence": 100,
                "analyst": {"net_up_revisions": 3},
                "insider": {"net_direction": "buying"},
            },
            {
                "ticker": "AMD",
                "reversal_score": 65,
                "data_confidence": 90,
                "options": {"iv_percentile": 0.8},
            },
        ],
        "exploratory": True,
        "runway_independent": False,
        "exploratory_gate": {"blocked": True, "reason": "forward validation"},
        "cot_confirmation": {"note": "lagging confirmation"},
        "disclaimer": "not investment advice",
        "note": "backend-only source detail",
    }
    payload.update(overrides)
    return payload


def _oversold_source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "module": "oversold_reversal",
        "lane_id": "coiled_base.v1.bb_squeeze+rsi_40_65",
        "definition": "壓縮基底 + 健康動能",
        "primary_signal": "bb_squeeze+rsi_40_65",
        "runway_independent": False,
        "runway_note": "private source detail",
        "exploratory": True,
        "as_of_date": "2026-08-01",
        "generated_at": "2026-08-01T04:05:06.123456+00:00",
        "universe": "sp1500",
        "liquidity_filter": {"min_avg_dollar_vol_m": 5},
        "attempted": 2,
        "scanned": 2,
        "fetch_failed": 0,
        "short_history": 0,
        "stale_history": 0,
        "match_count": 2,
        "validation": {
            "signal": "bb_squeeze+rsi_40_65",
            "pct_lift": 3.19,
            "atr_neutral_lift": 3.19,
            "support": 35,
            "source": "lane_runway.json",
            "source_blocked": True,
        },
        "validation_caveats": ["來源 stale", "跨宇宙尚未驗證"],
        "candidates": [
            {
                "ticker": "NVDA",
                "as_of": "2026-08-01",
                "signal_date": "2026-08-01",
                "last_price": 100.0,
                "rsi14": 52.0,
                "bb_width_pct": 1.2,
                "ma200": 90.0,
                "pct_vs_ma200": 11.1,
                "pct_from_52w_high": -10.0,
                "avg_dollar_vol_m": 2500.0,
            },
            {
                "ticker": "AMD",
                "as_of": "2026-08-01",
                "signal_date": "2026-08-01",
                "last_price": 80.0,
                "rsi14": 48.0,
                "bb_width_pct": 2.5,
                "ma200": 85.0,
                "pct_vs_ma200": -5.9,
                "pct_from_52w_high": -20.0,
                "avg_dollar_vol_m": 1500.0,
            },
        ],
        "note": "EXPLORATORY — 前向驗證、不自動評分。",
    }
    payload.update(overrides)
    return payload


def _reversal_public() -> dict[str, object]:
    source = _reversal_source()
    return {
        "as_of_date": source["as_of_date"],
        "generated_at": source["generated_at"],
        "lane_id": source["lane_id"],
        "universe": source["universe"],
        "match_count": source["match_count"],
        "candidates": [{"ticker": "NVDA"}, {"ticker": "AMD"}],
    }


def _oversold_public() -> dict[str, object]:
    source = _oversold_source()
    candidates = source["candidates"]
    if not isinstance(candidates, list):
        raise AssertionError(candidates)
    return {
        key: source[key]
        for key in OVERSOLD_PUBLIC_FIELDS
        if key not in {"validation", "candidates"}
    } | {
        "validation": {
            "pct_lift": 3.19,
            "atr_neutral_lift": 3.19,
            "support": 35,
        },
        "candidates": [
            {key: item[key] for key in OVERSOLD_CANDIDATE_FIELDS}
            for item in candidates
            if isinstance(item, dict)
        ],
    }


def _oversold_validation_source() -> dict[str, object]:
    payload = json.loads(
        (ROOT / "reports" / "oversold_reversal" / "validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


def _reversal_validation_source() -> dict[str, object]:
    payload = json.loads(
        (ROOT / "reports" / "reversal_radar" / "validation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


def _zero_reversal_validation_tier() -> dict[str, object]:
    return {
        "resolved": 0,
        "hits": 0,
        "hit_rate": None,
        "wilson90": [0.0, 1.0],
        "ev_horizon": None,
        "median_horizon": None,
        "win_rate_horizon": None,
        "ev_horizon_ci90": [None, None],
        "ev_excess_vs_spy": None,
        "excess_n": 0,
        "excess_win_rate": None,
        "ev_excess_ci90": [None, None],
        "equity_multiple": None,
        "equity_curve": [],
    }


def _reversal_validation_public() -> dict[str, object]:
    source = _reversal_validation_source()
    by_tier = source["by_tier"]
    if not isinstance(by_tier, dict):
        raise AssertionError(by_tier)
    return {
        key: source[key]
        for key in REVERSAL_VALIDATION_FIELDS
        if key != "by_tier"
    } | {
        "by_tier": {
            key: {
                field: row[field]
                for field in REVERSAL_VALIDATION_TIER_FIELDS
            }
            for key, row in by_tier.items()
            if isinstance(row, dict)
        }
    }


def _oversold_validation_public() -> dict[str, object]:
    source = _oversold_validation_source()
    by_tier = source["by_tier"]
    if not isinstance(by_tier, dict):
        raise AssertionError(by_tier)
    return {
        key: source[key]
        for key in OVERSOLD_VALIDATION_FIELDS
        if key != "by_tier"
    } | {
        "by_tier": {
            key: {
                field: row[field]
                for field in OVERSOLD_VALIDATION_TIER_FIELDS
            }
            for key, row in by_tier.items()
            if isinstance(row, dict)
        }
    }


def _envelope(
    source_id: str,
    data: dict[str, object] | None,
    *,
    available: bool = True,
    reason: str = "ok",
    as_of: str | None = "2026-08-01",
    generated_at: str | None,
) -> dict[str, object]:
    return {
        "available": available,
        "reason": reason,
        "data": data if available else None,
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(source_id: str, path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[source_id],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def _http_response(payload: object, **overrides: object) -> httpx.Response:
    options: dict[str, object] = {
        "status_code": 200,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "content": json.dumps(payload).encode("utf-8"),
    }
    options.update(overrides)
    return httpx.Response(**options)


def test_reversal_registry_projects_only_unique_ticker_references() -> None:
    spec = ARTIFACTS[REVERSAL_SOURCE_ID]
    if spec.data_model is not ReversalRadarData or spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)
    with tempfile.TemporaryDirectory() as tmp:
        result = read_artifact(
            _spec(REVERSAL_SOURCE_ID, _write(Path(tmp) / "latest.json", _reversal_source()))
        )
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != REVERSAL_PUBLIC_FIELDS:
        raise AssertionError(result.data)
    if result.data["candidates"] != [{"ticker": "NVDA"}, {"ticker": "AMD"}]:
        raise AssertionError(result.data)
    rendered = json.dumps(result.data)
    for private in ("analyst", "insider", "options", "reversal_score", "data_confidence"):
        if private in rendered:
            raise AssertionError((private, rendered))

    invalid = _reversal_source()
    invalid["candidates"] = [
        *invalid["candidates"],  # type: ignore[list-item]
        {"ticker": "NVDA"},
    ]
    invalid["match_count"] = 3
    with tempfile.TemporaryDirectory() as tmp:
        bad = read_artifact(
            _spec(REVERSAL_SOURCE_ID, _write(Path(tmp) / "latest.json", invalid))
        )
    if not isinstance(bad, ArtifactUnavailable) or bad.reason != "invalid_shape":
        raise AssertionError(bad)


def test_oversold_registry_projects_exact_display_fields_and_invariants() -> None:
    spec = ARTIFACTS[OVERSOLD_SOURCE_ID]
    if spec.data_model is not OversoldReversalData or spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)
    with tempfile.TemporaryDirectory() as tmp:
        result = read_artifact(
            _spec(OVERSOLD_SOURCE_ID, _write(Path(tmp) / "latest.json", _oversold_source()))
        )
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != OVERSOLD_PUBLIC_FIELDS:
        raise AssertionError(result.data)
    if set(result.data["validation"]) != {"pct_lift", "atr_neutral_lift", "support"}:
        raise AssertionError(result.data["validation"])
    if any(set(item) != OVERSOLD_CANDIDATE_FIELDS for item in result.data["candidates"]):
        raise AssertionError(result.data["candidates"])
    rendered = json.dumps(result.data)
    for private in ("source_blocked", "liquidity_filter", "signal_date"):
        if private in rendered:
            raise AssertionError((private, rendered))

    unsorted = _oversold_source()
    unsorted["candidates"] = list(reversed(unsorted["candidates"]))  # type: ignore[arg-type]
    with tempfile.TemporaryDirectory() as tmp:
        bad = read_artifact(
            _spec(OVERSOLD_SOURCE_ID, _write(Path(tmp) / "latest.json", unsorted))
        )
    if not isinstance(bad, ArtifactUnavailable) or bad.reason != "invalid_shape":
        raise AssertionError(bad)


def test_oversold_validation_registry_projects_real_artifact_and_rejects_drift() -> None:
    spec = ARTIFACTS[OVERSOLD_VALIDATION_SOURCE_ID]
    if (
        spec.data_model is not OversoldReversalValidationData
        or spec.data_validator is None
        or spec.data_projector is None
        or spec.generated_at_extractor is None
    ):
        raise AssertionError(spec)
    result = read_artifact(spec)
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != OVERSOLD_VALIDATION_FIELDS:
        raise AssertionError(result.data)
    if tuple(result.data["by_tier"]) != OVERSOLD_VALIDATION_TIERS:
        raise AssertionError(result.data["by_tier"])
    if any(
        set(row) != OVERSOLD_VALIDATION_TIER_FIELDS
        for row in result.data["by_tier"].values()
    ):
        raise AssertionError(result.data["by_tier"])
    rendered = json.dumps(result.data, ensure_ascii=False)
    for private in (
        "price_resolvable",
        "dropped_count",
        "verdict_by_tier",
        "survivorship",
        "sp500_pit_cohort",
        "equity_curve",
        "ev_horizon",
        "cost_assumption_round_trip",
        "note",
    ):
        if private in rendered:
            raise AssertionError((private, rendered))
    if result.meta.as_of is not None or result.meta.generated_at is None:
        raise AssertionError(result.meta)

    source = _oversold_validation_source()
    provisional = copy.deepcopy(source)
    provisional_row = provisional["by_tier"]["+30%/20d"]  # type: ignore[index]
    provisional_row.update(  # type: ignore[union-attr]
        {
            "resolved": 1,
            "hits": 0,
            "hit_rate": 0.0,
            "wilson90": [0.0, 1.0],
            "mature": False,
            "excess_mature": False,
            "excess_beta_adj_mature": False,
            "ev_horizon": None,
            "median_horizon": None,
            "win_rate_horizon": None,
            "ev_horizon_ci90": None,
            "ev_horizon_net": None,
            "win_rate_net": None,
            "ev_horizon_net_ci90": None,
            "ev_excess_vs_spy": None,
            "excess_n": 0,
            "excess_win_rate": None,
            "ev_excess_ci90": None,
            "ev_excess_beta_adj": None,
            "excess_beta_adj_n": 0,
            "excess_beta_adj_win_rate": None,
            "ev_excess_beta_adj_ci90": None,
            "equity_multiple": None,
            "equity_multiple_net": None,
            "equity_curve": [],
        }
    )
    provisional["verdict_by_tier"]["+30%/20d"] = "PROVISIONAL"  # type: ignore[index]
    with tempfile.TemporaryDirectory() as tmp:
        provisional_result = read_artifact(
            _spec(
                OVERSOLD_VALIDATION_SOURCE_ID,
                _write(Path(tmp) / "provisional.json", provisional),
            )
        )
    if not isinstance(provisional_result, ArtifactAvailable):
        raise AssertionError(provisional_result)

    invalid_sources: list[dict[str, object]] = []
    extra_root = copy.deepcopy(source)
    extra_root["unexpected"] = True
    invalid_sources.append(extra_root)
    bad_counts = copy.deepcopy(source)
    bad_counts["price_resolvable"] = bad_counts["entries_accumulated"] + 1
    invalid_sources.append(bad_counts)
    bad_tier = copy.deepcopy(source)
    bad_tier["by_tier"]["+30%/20d"]["hits"] = (  # type: ignore[index]
        bad_tier["by_tier"]["+30%/20d"]["resolved"] + 1  # type: ignore[index]
    )
    invalid_sources.append(bad_tier)
    bad_order = copy.deepcopy(source)
    tiers = bad_order["by_tier"]
    bad_order["by_tier"] = {  # type: ignore[index]
        key: tiers[key]  # type: ignore[index]
        for key in reversed(OVERSOLD_VALIDATION_TIERS)
    }
    invalid_sources.append(bad_order)
    bad_verdict = copy.deepcopy(source)
    bad_verdict["verdict"] = "PROVISIONAL"
    invalid_sources.append(bad_verdict)

    with tempfile.TemporaryDirectory() as tmp:
        for index, invalid in enumerate(invalid_sources):
            failed = read_artifact(
                _spec(
                    OVERSOLD_VALIDATION_SOURCE_ID,
                    _write(Path(tmp) / f"invalid-{index}.json", invalid),
                )
            )
            if not isinstance(failed, ArtifactUnavailable) or failed.reason != "invalid_shape":
                raise AssertionError((index, failed))


def test_reversal_validation_registry_follows_legacy_producer_semantics() -> None:
    spec = ARTIFACTS[REVERSAL_VALIDATION_SOURCE_ID]
    if (
        spec.data_model is not ReversalRadarValidationData
        or spec.data_validator is None
        or spec.data_projector is None
        or spec.generated_at_extractor is None
    ):
        raise AssertionError(spec)
    result = read_artifact(spec)
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != REVERSAL_VALIDATION_FIELDS:
        raise AssertionError(result.data)
    if tuple(result.data["by_tier"]) != REVERSAL_VALIDATION_TIERS:
        raise AssertionError(result.data["by_tier"])
    if any(
        set(row) != REVERSAL_VALIDATION_TIER_FIELDS
        for row in result.data["by_tier"].values()
    ):
        raise AssertionError(result.data["by_tier"])
    rendered = json.dumps(result.data, ensure_ascii=False)
    for private in (
        "price_resolvable",
        "dropped_count",
        "verdict_by_tier",
        "survivorship",
        "equity_curve",
        "equity_multiple",
        "ev_horizon",
        "ev_excess_vs_spy",
        "note",
    ):
        if private in rendered:
            raise AssertionError((private, rendered))
    if result.meta.as_of is not None or result.meta.generated_at is None:
        raise AssertionError(result.meta)

    source = _reversal_validation_source()
    first_row = source["by_tier"]["+10%/20d"]  # type: ignore[index]
    if not isinstance(first_row, dict) or first_row["equity_multiple"] < 1e20:
        raise AssertionError("real large finite Reversal equity was not exercised")

    zero = copy.deepcopy(source)
    zero_row = _zero_reversal_validation_tier()
    for tier in REVERSAL_VALIDATION_TIERS:
        zero["by_tier"][tier] = copy.deepcopy(zero_row)  # type: ignore[index]
        zero["verdict_by_tier"][tier] = "PROVISIONAL"  # type: ignore[index]
    zero.update(
        {
            "entries_accumulated": 0,
            "price_resolvable": 0,
            "dropped_count": 0,
            "dropped_pct": None,
            "min_resolved_across_tiers": 0,
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
        }
    )

    mature = copy.deepcopy(source)
    for tier in REVERSAL_VALIDATION_TIERS:
        mature["by_tier"][tier] = copy.deepcopy(first_row)  # type: ignore[index]
        mature["verdict_by_tier"][tier] = "MATURE"  # type: ignore[index]
    mature["min_resolved_across_tiers"] = first_row["resolved"]
    mature["verdict"] = "MATURE"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, valid in (("zero", zero), ("mature", mature)):
            accepted = read_artifact(
                _spec(
                    REVERSAL_VALIDATION_SOURCE_ID,
                    _write(root / f"{name}.json", valid),
                )
            )
            if not isinstance(accepted, ArtifactAvailable):
                raise AssertionError((name, accepted))

        invalid_sources = []
        extra = copy.deepcopy(source)
        extra["unexpected"] = True
        invalid_sources.append(extra)
        bad_verdict = copy.deepcopy(source)
        bad_verdict["verdict"] = "MATURE"
        invalid_sources.append(bad_verdict)
        bad_curve = copy.deepcopy(source)
        curve = bad_curve["by_tier"]["+10%/20d"]["equity_curve"]  # type: ignore[index]
        curve[0][0] = "9999-12-31"  # type: ignore[index]
        invalid_sources.append(bad_curve)
        negative_equity = copy.deepcopy(source)
        negative_equity["by_tier"]["+10%/20d"]["equity_multiple"] = -1.0  # type: ignore[index]
        invalid_sources.append(negative_equity)
        zero_with_published_interval = copy.deepcopy(zero)
        zero_with_published_interval["by_tier"]["+15%/40d"][  # type: ignore[index]
            "ev_horizon_ci90"
        ] = [0.0, 0.0]
        invalid_sources.append(zero_with_published_interval)
        for index, invalid in enumerate(invalid_sources):
            failed = read_artifact(
                _spec(
                    REVERSAL_VALIDATION_SOURCE_ID,
                    _write(root / f"reversal-invalid-{index}.json", invalid),
                )
            )
            if not isinstance(failed, ArtifactUnavailable) or failed.reason != "invalid_shape":
                raise AssertionError((index, failed))


def test_fixed_routes_return_strict_projections_without_private_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = dict(ARTIFACTS)
        registry[REVERSAL_SOURCE_ID] = _spec(
            REVERSAL_SOURCE_ID,
            _write(root / "reversal.json", _reversal_source()),
        )
        registry[OVERSOLD_SOURCE_ID] = _spec(
            OVERSOLD_SOURCE_ID,
            _write(root / "oversold.json", _oversold_source()),
        )
        registry[OVERSOLD_VALIDATION_SOURCE_ID] = _spec(
            OVERSOLD_VALIDATION_SOURCE_ID,
            ROOT / "reports" / "oversold_reversal" / "validation_summary.json",
        )
        registry[REVERSAL_VALIDATION_SOURCE_ID] = _spec(
            REVERSAL_VALIDATION_SOURCE_ID,
            ROOT / "reports" / "reversal_radar" / "validation_summary.json",
        )
        with _client(registry) as client:
            reversal = client.get(REVERSAL_ROUTE)
            oversold = client.get(OVERSOLD_ROUTE)
            validation = client.get(OVERSOLD_VALIDATION_ROUTE)
            reversal_validation = client.get(REVERSAL_VALIDATION_ROUTE)
    for response, expected in (
        (reversal, REVERSAL_PUBLIC_FIELDS),
        (oversold, OVERSOLD_PUBLIC_FIELDS),
    ):
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise AssertionError((response.status_code, response.text))
        if set(response.json()["data"]) != expected:
            raise AssertionError(response.json())
    if validation.status_code != 200 or validation.headers.get("cache-control") != "no-store":
        raise AssertionError((validation.status_code, validation.text))
    body = validation.json()
    if set(body["data"]) != OVERSOLD_VALIDATION_FIELDS:
        raise AssertionError(body)
    if body["meta"]["sourceId"] != OVERSOLD_VALIDATION_SOURCE_ID:
        raise AssertionError(body)
    if body["meta"]["asOf"] is not None or body["meta"]["generatedAt"] is None:
        raise AssertionError(body)
    if (
        reversal_validation.status_code != 200
        or reversal_validation.headers.get("cache-control") != "no-store"
    ):
        raise AssertionError(
            (reversal_validation.status_code, reversal_validation.text)
        )
    reversal_body = reversal_validation.json()
    if set(reversal_body["data"]) != REVERSAL_VALIDATION_FIELDS:
        raise AssertionError(reversal_body)
    if reversal_body["meta"]["sourceId"] != REVERSAL_VALIDATION_SOURCE_ID:
        raise AssertionError(reversal_body)
    if (
        reversal_body["meta"]["asOf"] is not None
        or reversal_body["meta"]["generatedAt"] is None
    ):
        raise AssertionError(reversal_body)
    with _client(registry) as client:
        paths = client.get("/openapi.json").json()["paths"]
    operations = (
        (paths[OVERSOLD_VALIDATION_ROUTE]["get"], "getOversoldReversalValidation"),
        (paths[REVERSAL_VALIDATION_ROUTE]["get"], "getReversalRadarValidation"),
    )
    for operation, operation_id in operations:
        if (
            operation["operationId"] != operation_id
            or operation.get("parameters") not in (None, [])
        ):
            raise AssertionError(operation)


def test_fixed_clients_validate_urls_provenance_unavailable_and_caps() -> None:
    seen: list[httpx.Request] = []
    payloads = {
        REVERSAL_URL: _envelope(
            REVERSAL_SOURCE_ID,
            _reversal_public(),
            generated_at="2026-08-01T03:04:05.123456+00:00",
        ),
        OVERSOLD_URL: _envelope(
            OVERSOLD_SOURCE_ID,
            _oversold_public(),
            generated_at="2026-08-01T04:05:06.123456+00:00",
        ),
        OVERSOLD_VALIDATION_URL: _envelope(
            OVERSOLD_VALIDATION_SOURCE_ID,
            _oversold_validation_public(),
            as_of=None,
            generated_at=_oversold_validation_source()["generated_at"],
        ),
        REVERSAL_VALIDATION_URL: _envelope(
            REVERSAL_VALIDATION_SOURCE_ID,
            _reversal_validation_public(),
            as_of=None,
            generated_at=_reversal_validation_source()["generated_at"],
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _http_response(payloads[str(request.url)])

    transport = httpx.MockTransport(handler)
    reversal = _read_api.load_reversal_radar(transport=transport)
    oversold = _read_api.load_oversold_reversal(transport=transport)
    validation = _read_api.load_oversold_reversal_validation(transport=transport)
    reversal_validation = _read_api.load_reversal_radar_validation(
        transport=transport
    )
    if not isinstance(reversal, _read_api.ReversalRadarApiAvailable):
        raise AssertionError(reversal)
    if not isinstance(oversold, _read_api.OversoldReversalApiAvailable):
        raise AssertionError(oversold)
    if not isinstance(validation, _read_api.OversoldReversalValidationApiAvailable):
        raise AssertionError(validation)
    if not isinstance(
        reversal_validation,
        _read_api.ReversalRadarValidationApiAvailable,
    ):
        raise AssertionError(reversal_validation)
    if [str(request.url) for request in seen] != [
        REVERSAL_URL,
        OVERSOLD_URL,
        OVERSOLD_VALIDATION_URL,
        REVERSAL_VALIDATION_URL,
    ]:
        raise AssertionError(seen)

    unavailable_payload = _envelope(
        REVERSAL_SOURCE_ID,
        None,
        available=False,
        reason="missing",
        as_of=None,
        generated_at=None,
    )
    unavailable = _read_api.load_reversal_radar(
        transport=httpx.MockTransport(lambda _request: _http_response(unavailable_payload))
    )
    if unavailable != _read_api.ReversalRadarApiUnavailable("missing"):
        raise AssertionError(unavailable)

    wrong_meta = _envelope(
        OVERSOLD_SOURCE_ID,
        _oversold_public(),
        as_of="2026-07-31",
        generated_at="2026-08-01T04:05:06.123456+00:00",
    )
    failure = _read_api.load_oversold_reversal(
        transport=httpx.MockTransport(lambda _request: _http_response(wrong_meta))
    )
    if failure != _read_api.OversoldReversalApiFailure("invalid_envelope"):
        raise AssertionError(failure)

    invalid_validation_meta = _envelope(
        OVERSOLD_VALIDATION_SOURCE_ID,
        _oversold_validation_public(),
        as_of="2026-08-01",
        generated_at=_oversold_validation_source()["generated_at"],
    )
    validation_failure = _read_api.load_oversold_reversal_validation(
        transport=httpx.MockTransport(
            lambda _request: _http_response(invalid_validation_meta)
        )
    )
    if validation_failure != _read_api.OversoldReversalValidationApiFailure(
        "invalid_envelope"
    ):
        raise AssertionError(validation_failure)

    invalid_reversal_validation_meta = _envelope(
        REVERSAL_VALIDATION_SOURCE_ID,
        _reversal_validation_public(),
        as_of="2026-08-01",
        generated_at=_reversal_validation_source()["generated_at"],
    )
    reversal_validation_failure = _read_api.load_reversal_radar_validation(
        transport=httpx.MockTransport(
            lambda _request: _http_response(invalid_reversal_validation_meta)
        )
    )
    if reversal_validation_failure != _read_api.ReversalRadarValidationApiFailure(
        "invalid_envelope"
    ):
        raise AssertionError(reversal_validation_failure)

    for loader, failure_type, cap in (
        (
            _read_api.load_reversal_radar,
            _read_api.ReversalRadarApiFailure,
            _read_api._REVERSAL_RADAR_MAX_RESPONSE_BYTES,
        ),
        (
            _read_api.load_oversold_reversal,
            _read_api.OversoldReversalApiFailure,
            _read_api._OVERSOLD_REVERSAL_MAX_RESPONSE_BYTES,
        ),
        (
            _read_api.load_oversold_reversal_validation,
            _read_api.OversoldReversalValidationApiFailure,
            _read_api._OVERSOLD_REVERSAL_VALIDATION_MAX_RESPONSE_BYTES,
        ),
        (
            _read_api.load_reversal_radar_validation,
            _read_api.ReversalRadarValidationApiFailure,
            _read_api._REVERSAL_RADAR_VALIDATION_MAX_RESPONSE_BYTES,
        ),
    ):
        oversized = httpx.Response(
            200,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            content=b"x" * (cap + 1),
        )
        result = loader(transport=httpx.MockTransport(lambda _request: oversized))
        if result != failure_type("response_too_large"):
            raise AssertionError(result)


def test_radar_discovery_is_api_only_while_live_computation_is_preserved() -> None:
    snapshot = ReversalRadarData.model_validate(_reversal_public())
    with patch(
        "ui.radar._read_api.load_reversal_radar",
        return_value=_read_api.ReversalRadarApiAvailable(snapshot),
    ):
        if radar._beaten_down_tickers() != ["NVDA", "AMD"]:
            raise AssertionError(radar._beaten_down_tickers())
    with patch(
        "ui.radar._read_api.load_reversal_radar",
        return_value=_read_api.ReversalRadarApiFailure("transport_error"),
    ), patch(
        "ui.radar._shared.load_json",
        side_effect=AssertionError("Radar attempted a local latest fallback"),
    ):
        if radar._beaten_down_tickers() != []:
            raise AssertionError(radar._beaten_down_tickers())

    source = (ROOT / "ui" / "radar.py").read_text(encoding="utf-8")
    if "import reversal_radar" not in source or "rgui._analyze" not in source:
        raise AssertionError("live Radar/Risk Guard compute was removed")
    tree = ast.parse(source, filename="ui/radar.py", feature_version=(3, 10))
    loader = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_beaten_down_tickers"
    )
    loader_source = ast.get_source_segment(source, loader) or ""
    if "_read_api.load_reversal_radar()" not in loader_source or "load_json" in loader_source:
        raise AssertionError(loader_source)


def test_oversold_latest_and_forward_validation_are_api_only() -> None:
    snapshot = OversoldReversalData.model_validate(_oversold_public())
    with patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal",
        return_value=_read_api.OversoldReversalApiAvailable(snapshot),
    ):
        loaded = oversold_reversal_lane._load_latest()
    if loaded is None or loaded.get("match_count") != 2:
        raise AssertionError(loaded)

    for result in (
        _read_api.OversoldReversalApiUnavailable("missing"),
        _read_api.OversoldReversalApiFailure("transport_error"),
    ):
        with patch(
            "ui.oversold_reversal_lane._read_api.load_oversold_reversal",
            return_value=result,
        ), patch(
            "ui.oversold_reversal_lane._shared.load_json",
            side_effect=AssertionError("Oversold attempted a local latest fallback"),
        ):
            if oversold_reversal_lane._load_latest() is not None:
                raise AssertionError(result)

    source = (ROOT / "ui" / "oversold_reversal_lane.py").read_text(encoding="utf-8")
    if "_read_api.load_oversold_reversal()" not in source:
        raise AssertionError(source)
    if "validation_summary.json" in source or "load_json" in source:
        raise AssertionError("Oversold forward validation retained a local read")
    if source.count("_read_api.load_oversold_reversal_validation()") != 1:
        raise AssertionError(source)

    wrapper = "from ui.oversold_reversal_lane import render\nrender()\n"
    validation = OversoldReversalValidationData.model_validate(
        _oversold_validation_public()
    )
    with patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal",
        return_value=_read_api.OversoldReversalApiAvailable(snapshot),
    ) as latest_loader, patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal_validation",
        return_value=_read_api.OversoldReversalValidationApiAvailable(validation),
    ) as validation_loader:
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if (
        app.exception
        or len(app.dataframe) < 2
        or latest_loader.call_count != 1
        or validation_loader.call_count != 1
    ):
        raise AssertionError(
            (
                app.exception,
                len(app.dataframe),
                latest_loader.call_count,
                validation_loader.call_count,
            )
        )

    embedded_wrapper = (
        "from ui.oversold_reversal_lane import render\n"
        "render(embedded=True)\n"
    )
    with patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal",
        return_value=_read_api.OversoldReversalApiAvailable(snapshot),
    ) as embedded_latest_loader, patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal_validation",
        return_value=_read_api.OversoldReversalValidationApiAvailable(validation),
    ) as embedded_validation_loader:
        embedded_app = AppTest.from_string(
            embedded_wrapper, default_timeout=10
        ).run()
    if (
        embedded_app.exception
        or embedded_latest_loader.call_count != 1
        or embedded_validation_loader.call_count != 1
    ):
        raise AssertionError(
            (
                embedded_app.exception,
                embedded_latest_loader.call_count,
                embedded_validation_loader.call_count,
            )
        )

    with patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal",
        return_value=_read_api.OversoldReversalApiUnavailable("missing"),
    ) as unavailable_latest_loader, patch(
        "ui.oversold_reversal_lane._read_api.load_oversold_reversal_validation",
        side_effect=AssertionError(
            "validation was loaded after latest became unavailable"
        ),
    ) as unavailable_validation_loader:
        unavailable_app = AppTest.from_string(wrapper, default_timeout=10).run()
    if (
        unavailable_app.exception
        or unavailable_latest_loader.call_count != 1
        or unavailable_validation_loader.call_count != 0
    ):
        raise AssertionError(
            (
                unavailable_app.exception,
                unavailable_latest_loader.call_count,
                unavailable_validation_loader.call_count,
            )
        )

    failures = (
        _read_api.OversoldReversalValidationApiUnavailable("missing"),
        *(
            _read_api.OversoldReversalValidationApiFailure(reason)
            for reason in (
                "transport_error",
                "deadline_exceeded",
                "http_status",
                "invalid_media_type",
                "invalid_cache_control",
                "response_too_large",
                "invalid_envelope",
            )
        ),
    )
    validation_wrapper = (
        "from ui.oversold_reversal_lane import _render_forward_validation\n"
        "_render_forward_validation()\n"
    )
    for result in failures:
        with patch(
            "ui.oversold_reversal_lane._read_api.load_oversold_reversal_validation",
            return_value=result,
        ) as loader, patch(
            "ui.oversold_reversal_lane._shared.load_json",
            side_effect=AssertionError("Oversold validation attempted local fallback"),
        ):
            failure_app = AppTest.from_string(
                validation_wrapper, default_timeout=10
            ).run()
        if failure_app.exception or loader.call_count != 1:
            raise AssertionError((result, failure_app.exception, loader.call_count))
        text = "\n".join(str(item.value) for item in failure_app.caption)
        if "API 暫無前向驗證摘要" not in text or result.reason in text:
            raise AssertionError((result, text))


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    reversal = ReversalRadarData.model_validate(_reversal_public())
    oversold = OversoldReversalData.model_validate(_oversold_public())
    validation = OversoldReversalValidationData.model_validate(
        _oversold_validation_public()
    )
    reversal_validation = ReversalRadarValidationData.model_validate(
        _reversal_validation_public()
    )
    outcomes = (
        (_read_api.ReversalRadarApiAvailable(reversal), "snapshot", reversal),
        (_read_api.ReversalRadarApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.OversoldReversalApiAvailable(oversold), "snapshot", oversold),
        (_read_api.OversoldReversalApiFailure("transport_error"), "reason", "http_status"),
        (
            _read_api.OversoldReversalValidationApiAvailable(validation),
            "summary",
            validation,
        ),
        (
            _read_api.OversoldReversalValidationApiUnavailable("missing"),
            "reason",
            "unreadable",
        ),
        (
            _read_api.OversoldReversalValidationApiFailure("transport_error"),
            "reason",
            "http_status",
        ),
        (
            _read_api.ReversalRadarValidationApiAvailable(reversal_validation),
            "summary",
            reversal_validation,
        ),
        (
            _read_api.ReversalRadarValidationApiUnavailable("missing"),
            "reason",
            "unreadable",
        ),
        (
            _read_api.ReversalRadarValidationApiFailure("transport_error"),
            "reason",
            "http_status",
        ),
    )
    for outcome, field, value in outcomes:
        try:
            setattr(outcome, field, value)
        except FrozenInstanceError:
            continue
        raise AssertionError(outcome)
    for relative in (
        "api/models.py",
        "api/artifacts.py",
        "api/main.py",
        "ui/_read_api.py",
        "ui/radar.py",
        "ui/oversold_reversal_lane.py",
        "scripts/test_ui_reversal_snapshots_api.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


def main() -> None:
    tests = [
        test_reversal_registry_projects_only_unique_ticker_references,
        test_oversold_registry_projects_exact_display_fields_and_invariants,
        test_oversold_validation_registry_projects_real_artifact_and_rejects_drift,
        test_reversal_validation_registry_follows_legacy_producer_semantics,
        test_fixed_routes_return_strict_projections_without_private_fields,
        test_fixed_clients_validate_urls_provenance_unavailable_and_caps,
        test_radar_discovery_is_api_only_while_live_computation_is_preserved,
        test_oversold_latest_and_forward_validation_are_api_only,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
