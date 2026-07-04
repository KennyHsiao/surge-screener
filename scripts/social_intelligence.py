#!/usr/bin/env python3
"""Free-first social intelligence snapshot builder.

The core contract is deliberately conservative: paid X/Grok sources may discover
tickers, but the snapshot remains useful without paid credentials by attaching
free StockTwits/ApeWisdom heat baselines and explicit source status metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
SOCIAL_DIR_NAME = "social_intelligence"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SentimentGatherer = Callable[[str], dict[str, Any]]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_json(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper().lstrip("$")


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        if out != out:
            return None
        return out
    except (TypeError, ValueError):
        return None


def source_statuses(
    *,
    env: dict[str, str] | None = None,
    agent_reach_command: str | list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return source capability and cost boundaries without touching the network."""
    env = env if env is not None else dict(os.environ)
    agent_configured = bool(agent_reach_command or env.get("AGENT_REACH_COMMAND"))
    return {
        "xai_grok": {
            "label": "xAI Grok x_search",
            "cost_mode": "paid_optional",
            "status": "available" if env.get("XAI_API_KEY") else "unavailable",
            "note": "Requires xAI developer API key; X/Grok subscription is not an API.",
        },
        "x_official_api": {
            "label": "X official API",
            "cost_mode": "paid_optional",
            "status": "available" if env.get("X_BEARER_TOKEN") else "unavailable",
            "note": "Only used for paid/manual raw post lookup, not the free core.",
        },
        "agent_reach": {
            "label": "Agent Reach",
            "cost_mode": "auth_required",
            "status": "configured" if agent_configured else "unavailable",
            "note": "Optional local adapter; missing login/install degrades the snapshot.",
        },
        "stocktwits": {
            "label": "StockTwits",
            "cost_mode": "free",
            "status": "available",
            "note": "Per-ticker retail sentiment validation; not market-wide discovery.",
        },
        "apewisdom": {
            "label": "ApeWisdom",
            "cost_mode": "free",
            "status": "available",
            "note": "Reddit/WSB crowd heat baseline; not an early-signal source.",
        },
    }


def _command_parts(command: str | list[str] | None) -> list[str]:
    if not command:
        return []
    return [str(x) for x in command] if isinstance(command, list) else shlex.split(str(command))


def fetch_agent_reach(
    *,
    command: str | list[str] | None = None,
    timeout: float = 30,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Run an optional local Agent Reach command and normalize failures.

    The command is expected to print JSON with either `tickers` or `rows`. Unknown
    shapes are treated as degraded instead of crashing the caller.
    """
    argv = _command_parts(command or os.environ.get("AGENT_REACH_COMMAND"))
    if not argv:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "unavailable",
            "tickers": [],
            "note": "Agent Reach command not configured",
        }
    try:
        if runner is None:
            result = subprocess.run(
                argv,
                timeout=timeout,
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            result = runner(argv, timeout)
    except subprocess.TimeoutExpired:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": "Agent Reach timed out",
        }
    except FileNotFoundError:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "unavailable",
            "tickers": [],
            "note": "Agent Reach command not installed",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": f"Agent Reach failed: {type(exc).__name__}",
        }

    returncode = int(getattr(result, "returncode", 0) or 0)
    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    if returncode != 0:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": stderr[:240] or f"Agent Reach exited {returncode}",
        }
    try:
        payload = json.loads(stdout)
    except Exception:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": "Agent Reach returned non-JSON output",
        }
    rows = _as_list(payload.get("tickers")) or _as_list(payload.get("rows"))
    status = str(payload.get("status") or "available")
    return {
        "source": "agent_reach",
        "cost_mode": payload.get("cost_mode") or "auth_required",
        "status": status if status in {"available", "degraded", "unavailable"} else "available",
        "tickers": rows,
        "note": payload.get("note"),
        "raw": payload,
    }


def _ranked_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("ranked_candidates")
    if not isinstance(rows, list):
        rows = payload.get("tickers")
    out: dict[str, dict[str, Any]] = {}
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        sym = _ticker(row.get("ticker") or row.get("symbol"))
        if sym:
            out[sym] = row
    return out


def _options_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in _as_list(payload.get("signals")):
        if not isinstance(row, dict):
            continue
        sym = _ticker(row.get("ticker") or row.get("symbol"))
        if sym:
            out[sym] = row
    return out


def _blank_heat(source: str) -> dict[str, Any]:
    return {"source": source, "status": "unavailable", "cost_mode": "free"}


def _heat_baseline(sentiment: dict[str, Any] | None) -> dict[str, Any]:
    sentiment = sentiment if isinstance(sentiment, dict) else {}
    st = sentiment.get("stocktwits")
    aw = sentiment.get("reddit_apewisdom")
    stocktwits = (
        {"source": "stocktwits", "status": "available", "cost_mode": "free", **st}
        if isinstance(st, dict) else _blank_heat("stocktwits")
    )
    apewisdom = (
        {"source": "apewisdom", "status": "available", "cost_mode": "free", **aw}
        if isinstance(aw, dict) else _blank_heat("apewisdom")
    )
    return {"stocktwits": stocktwits, "apewisdom": apewisdom}


def _is_crowded(heat: dict[str, Any]) -> bool:
    st = heat.get("stocktwits") or {}
    aw = heat.get("apewisdom") or {}
    total = _num(st.get("total_messages")) or 0.0
    mentions = _num(aw.get("mentions")) or 0.0
    return bool(aw.get("in_top_mentions") or mentions >= 100 or total >= 50)


def _has_retail_heat(heat: dict[str, Any]) -> bool:
    st = heat.get("stocktwits") or {}
    aw = heat.get("apewisdom") or {}
    return bool((_num(st.get("total_messages")) or 0.0) >= 10 or (_num(aw.get("mentions")) or 0.0) >= 25)


def _platform_validation(
    ticker: str,
    ranked: dict[str, dict[str, Any]],
    options: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rank_row = ranked.get(ticker) or {}
    option_row = options.get(ticker) or {}
    return {
        "in_ranked_candidates": bool(rank_row),
        "rank_score": rank_row.get("rank_score"),
        "rank_bucket": rank_row.get("rank_bucket"),
        "last_price": rank_row.get("last_price") or rank_row.get("price"),
        "options_flow_score": option_row.get("flow_score"),
        "options_direction": option_row.get("direction"),
    }


def _add_discovery(
    agg: dict[str, dict[str, Any]],
    *,
    ticker: str,
    source: str,
    cost_mode: str,
    mentioned_by: list[Any] | None = None,
    citations: list[Any] | None = None,
    note: Any = "",
    skew: Any = "",
    conviction: Any = "",
) -> None:
    sym = _ticker(ticker)
    if not sym:
        return
    row = agg.setdefault(sym, {
        "ticker": sym,
        "mentioned_by": [],
        "citations": [],
        "notes": [],
        "discovery_sources": [],
        "cost_modes": [],
        "skews": [],
        "convictions": [],
    })
    for handle in mentioned_by or []:
        text = str(handle or "").strip().lstrip("@")
        if text and text not in row["mentioned_by"]:
            row["mentioned_by"].append(text)
    for cite in citations or []:
        text = str(cite or "").strip()
        if text and text not in row["citations"]:
            row["citations"].append(text)
    if note:
        row["notes"].append(str(note))
    if source not in row["discovery_sources"]:
        row["discovery_sources"].append(source)
    if cost_mode not in row["cost_modes"]:
        row["cost_modes"].append(cost_mode)
    if skew:
        row["skews"].append(str(skew))
    if conviction:
        row["convictions"].append(str(conviction))


def _collect_x_picks(agg: dict[str, dict[str, Any]], x_picks: dict[str, Any] | None) -> None:
    if not isinstance(x_picks, dict):
        return
    citations = _as_list(x_picks.get("citations"))
    for row in _as_list(x_picks.get("tickers")):
        if not isinstance(row, dict):
            continue
        _add_discovery(
            agg,
            ticker=row.get("symbol") or row.get("ticker"),
            source="x_influencer_picks",
            cost_mode="paid_optional",
            mentioned_by=_as_list(row.get("mentioned_by")),
            citations=citations,
            note=row.get("note", ""),
            skew=row.get("skew", ""),
            conviction=row.get("conviction", ""),
        )


def _collect_agent_reach(agg: dict[str, dict[str, Any]], agent_reach: dict[str, Any] | None) -> None:
    if not isinstance(agent_reach, dict) or agent_reach.get("status") != "available":
        return
    for row in _as_list(agent_reach.get("tickers")):
        if not isinstance(row, dict):
            continue
        _add_discovery(
            agg,
            ticker=row.get("ticker") or row.get("symbol"),
            source="agent_reach",
            cost_mode=str(agent_reach.get("cost_mode") or "auth_required"),
            mentioned_by=_as_list(row.get("mentioned_by") or row.get("authors")),
            citations=_as_list(row.get("citations") or row.get("urls")),
            note=row.get("note", ""),
            skew=row.get("skew", ""),
            conviction=row.get("conviction", ""),
        )


def _sentiment_for(ticker: str, gatherer: SentimentGatherer) -> dict[str, Any] | None:
    try:
        data = gatherer(ticker)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _row_from_aggregate(
    base: dict[str, Any],
    *,
    sentiment: dict[str, Any] | None,
    ranked: dict[str, dict[str, Any]],
    options: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    heat = _heat_baseline(sentiment)
    validation = _platform_validation(base["ticker"], ranked, options)
    crowded = _is_crowded(heat)
    platform_supported = bool(
        validation.get("in_ranked_candidates")
        or (_num(validation.get("options_flow_score")) or 0.0) > 0
    )
    labels = {
        "x_mentioned": "x_influencer_picks" in base["discovery_sources"],
        "agent_reach": "agent_reach" in base["discovery_sources"],
        "retail_heat": _has_retail_heat(heat),
        "crowded": crowded,
        "early_signal": bool(base["discovery_sources"] and platform_supported and not crowded),
        "paid_data_needed": "paid_optional" in base["cost_modes"],
    }
    return {
        "ticker": base["ticker"],
        "mentioned_by": base["mentioned_by"],
        "citations": base["citations"],
        "discovery_sources": base["discovery_sources"],
        "cost_modes": base["cost_modes"],
        "skew": base["skews"][0] if base["skews"] else None,
        "conviction": base["convictions"][0] if base["convictions"] else None,
        "note": base["notes"][0] if base["notes"] else "",
        "heat_baseline": heat,
        "platform_validation": validation,
        "labels": labels,
    }


def _snapshot_source_statuses(
    *,
    agent_reach: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    statuses = source_statuses(env=env)
    if isinstance(agent_reach, dict):
        current = statuses.get("agent_reach", {})
        statuses["agent_reach"] = {
            **current,
            "status": agent_reach.get("status") or current.get("status"),
            "cost_mode": agent_reach.get("cost_mode") or current.get("cost_mode"),
            "note": agent_reach.get("note") or current.get("note"),
        }
    return statuses


def build_social_snapshot(
    *,
    x_picks: dict[str, Any] | None = None,
    agent_reach: dict[str, Any] | None = None,
    sentiment_gatherer: SentimentGatherer | None = None,
    ranked_candidates: dict[str, Any] | None = None,
    options_flow: dict[str, Any] | None = None,
    as_of_date: str | None = None,
    market: str | None = None,
) -> dict[str, Any]:
    """Build the in-memory social intelligence snapshot."""
    if sentiment_gatherer is None:
        try:
            from scripts.sentiment_free import gather_free_sentiment
        except ImportError:
            from sentiment_free import gather_free_sentiment

        sentiment_gatherer = gather_free_sentiment
    as_of = str(as_of_date or _today())[:10]
    agg: dict[str, dict[str, Any]] = {}
    _collect_x_picks(agg, x_picks)
    _collect_agent_reach(agg, agent_reach)
    ranked = _ranked_map(ranked_candidates)
    options = _options_map(options_flow)

    rows = [
        _row_from_aggregate(
            base,
            sentiment=_sentiment_for(sym, sentiment_gatherer),
            ranked=ranked,
            options=options,
        )
        for sym, base in sorted(agg.items())
    ]
    rows.sort(key=lambda r: (
        not bool((r.get("labels") or {}).get("early_signal")),
        -len(r.get("mentioned_by") or []),
        r.get("ticker") or "",
    ))
    return {
        "as_of_date": as_of,
        "generated_at": _utc_timestamp(),
        "source": "social_intelligence",
        "schema_version": 1,
        "market": market,
        "source_statuses": _snapshot_source_statuses(agent_reach=agent_reach),
        "tickers": rows,
        "limitations": [
            "StockTwits validates single-ticker retail sentiment; it is not market-wide discovery.",
            "ApeWisdom is a crowd heat baseline, not an early-signal source.",
            "X/Grok subscription is manual research assistance only; automation requires xAI API.",
        ],
    }


def _legacy_badges(labels: dict[str, Any]) -> list[str]:
    pairs = [
        ("x_mentioned", "X Mentioned"),
        ("agent_reach", "Agent Reach"),
        ("retail_heat", "Retail Heat"),
        ("crowded", "Crowded"),
        ("early_signal", "Early Signal"),
        ("paid_data_needed", "Paid Data Needed"),
    ]
    return [label for key, label in pairs if labels.get(key)]


def legacy_quickpick_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = []
    citations = []
    for row in _as_list(snapshot.get("tickers")):
        if not isinstance(row, dict):
            continue
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        citations.extend(c for c in _as_list(row.get("citations")) if c)
        rows.append({
            "symbol": row.get("ticker"),
            "mentioned_by": row.get("mentioned_by") or [],
            "count": len(row.get("mentioned_by") or []),
            "skew": row.get("skew") or "neutral",
            "conviction": row.get("conviction"),
            "note": row.get("note") or "",
            "badges": _legacy_badges(labels),
            "labels": labels,
        })
    return {
        "source": "social_intelligence",
        "market": snapshot.get("market"),
        "window": snapshot.get("as_of_date"),
        "generated_at": snapshot.get("generated_at"),
        "tickers": rows,
        "citations": sorted({str(c) for c in citations}),
    }


def write_legacy_quickpick(snapshot: dict[str, Any], *, reports_dir: str | Path = REPORTS_DIR) -> Path:
    path = Path(reports_dir) / "x_influencer_picks.json"
    _write_json(path, legacy_quickpick_payload(snapshot))
    return path


def write_social_snapshot(snapshot: dict[str, Any], *, reports_dir: str | Path = REPORTS_DIR) -> dict[str, str]:
    reports = Path(reports_dir)
    out_dir = reports / SOCIAL_DIR_NAME
    as_of = str(snapshot.get("as_of_date") or _today())[:10]
    dated = out_dir / f"{as_of}.json"
    latest = out_dir / "latest.json"
    _write_json(dated, snapshot)
    _write_json(latest, snapshot)
    legacy = write_legacy_quickpick(snapshot, reports_dir=reports)
    return {"snapshot_path": str(dated), "latest_path": str(latest), "legacy_path": str(legacy)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build free-first social intelligence snapshot")
    parser.add_argument("--market", default="US")
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--x-picks-path", default=str(REPORTS_DIR / "x_influencer_picks.json"))
    parser.add_argument("--candidate-file", default=str(REPO / "ranked_candidates.json"))
    parser.add_argument("--options-flow-path", default=str(REPORTS_DIR / "options_flow" / "latest.json"))
    parser.add_argument("--agent-reach-command", default="")
    parser.add_argument(
        "--agent-reach-timeout",
        type=float,
        default=float(os.environ.get("AGENT_REACH_TIMEOUT") or 30),
    )
    args = parser.parse_args()

    agent_command = args.agent_reach_command or os.environ.get("AGENT_REACH_COMMAND")
    agent = fetch_agent_reach(command=agent_command, timeout=args.agent_reach_timeout) if agent_command else None
    snapshot = build_social_snapshot(
        x_picks=_load_json(args.x_picks_path),
        agent_reach=agent,
        ranked_candidates=_load_json(args.candidate_file),
        options_flow=_load_json(args.options_flow_path),
        as_of_date=args.as_of_date,
        market=args.market,
    )
    print(json.dumps(write_social_snapshot(snapshot, reports_dir=args.reports_dir),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
