#!/usr/bin/env python3
"""Agent Reach -> social_intelligence JSON bridge.

Runs twitter-cli with credentials loaded from Agent Reach's persistent config
(`~/.agent-reach/config.yaml`) so surge-screener can use the optional local
fallback without manually passing cookies each time.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path.home() / ".agent-reach" / "config.yaml"
DEFAULT_INFLUENCERS = REPO / "content" / "influencers.json"

Runner = Callable[..., subprocess.CompletedProcess[str]]

TICKER_RE = re.compile(
    r"(?<![A-Za-z0-9_$])\$([A-Za-z][A-Za-z0-9]{0,5})(?![A-Za-z0-9_])"
    r"|(?<![A-Za-z0-9_$])([A-Z]{2,5})(?![A-Za-z0-9_])"
)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
BLOCKED_WORDS = {
    "AI", "ALL", "AND", "ARE", "ATH", "BUY", "CALL", "CEO", "CFO", "CPI",
    "DAY", "DTE", "ETF", "FED", "FOMC", "GDP", "HOD", "IPO", "IV", "LOL",
    "LOW", "MACD", "NASDAQ", "NEWS", "NYSE", "OPEN", "OR", "PUT",
    "RSI", "SEC", "SELL", "THE", "THIS", "USD", "VIX", "VWAP", "X",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _simple_yaml(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        value = value.strip().strip("'\"")
        if key.strip():
            out[key.strip()] = value
    return out


def load_agent_reach_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg_path = Path(path).expanduser()
    if not cfg_path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return _simple_yaml(cfg_path)


def load_credentials(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = env if env is not None else os.environ
    auth = env.get("TWITTER_AUTH_TOKEN") or env.get("AUTH_TOKEN")
    ct0 = env.get("TWITTER_CT0") or env.get("CT0")
    if auth and ct0:
        return {"auth_token": auth, "ct0": ct0}

    cfg = load_agent_reach_config(config_path)
    auth = str(cfg.get("twitter_auth_token") or "").strip()
    ct0 = str(cfg.get("twitter_ct0") or "").strip()
    return {"auth_token": auth, "ct0": ct0} if auth and ct0 else {}


def run_twitter(
    args: list[str],
    *,
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    child_env = dict(env if env is not None else os.environ)
    child_env["TWITTER_AUTH_TOKEN"] = credentials["auth_token"]
    child_env["TWITTER_CT0"] = credentials["ct0"]
    call = runner or subprocess.run
    return call(
        [twitter_bin, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=child_env,
    )


def _handles_from_file(path: str | Path, *, market: str | None, limit: int) -> list[str]:
    data = _load_json(Path(path))
    rows = data.get("influencers", []) if isinstance(data, dict) else []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if market and str(row.get("market") or "").upper() != market.upper():
            continue
        handle = str(row.get("handle") or "").strip().lstrip("@")
        key = handle.lower()
        if handle and key not in seen:
            seen.add(key)
            out.append(handle)
        if len(out) >= limit:
            break
    return out


def _normalise_handle(handle: str) -> str:
    return str(handle or "").strip().lstrip("@")


def _extract_urls(text: str) -> list[str]:
    out: list[str] = []
    for raw in URL_RE.findall(text or ""):
        url = raw.rstrip(".,;")
        if url and url not in out:
            out.append(url)
    return out


def _extract_tickers(text: str) -> list[str]:
    out: list[str] = []
    for match in TICKER_RE.finditer(text or ""):
        raw = match.group(1) or match.group(2) or ""
        ticker = raw.upper().lstrip("$")
        if not ticker or ticker in BLOCKED_WORDS:
            continue
        if len(ticker) == 1 and f"${ticker}" not in text:
            continue
        if ticker not in out:
            out.append(ticker)
    return out


def _add_ticker(
    agg: dict[str, dict[str, Any]],
    *,
    ticker: str,
    handle: str,
    citations: list[str],
) -> None:
    row = agg.setdefault(ticker, {
        "ticker": ticker,
        "mentioned_by": [],
        "citations": [],
        "note": "Agent Reach twitter-cli user-posts match",
    })
    if handle and handle not in row["mentioned_by"]:
        row["mentioned_by"].append(handle)
    for url in citations:
        if url not in row["citations"]:
            row["citations"].append(url)


def build_agent_reach_payload(
    *,
    handles: list[str],
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    limit_per_handle: int = 20,
    timeout: float = 30,
) -> dict[str, Any]:
    if not credentials.get("auth_token") or not credentials.get("ct0"):
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }
    if not handles:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": "No handles configured for Agent Reach bridge",
        }

    agg: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for handle in [_normalise_handle(h) for h in handles if _normalise_handle(h)]:
        result = run_twitter(
            ["user-posts", f"@{handle}", "-n", str(limit_per_handle)],
            credentials=credentials,
            twitter_bin=twitter_bin,
            runner=runner,
            env=env,
            timeout=timeout,
        )
        text = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode != 0:
            failures.append(f"@{handle}: {text.strip()[:160]}")
            continue
        citations = _extract_urls(text)
        for ticker in _extract_tickers(text):
            _add_ticker(agg, ticker=ticker, handle=handle, citations=citations)

    rows = sorted(
        agg.values(),
        key=lambda row: (-len(row.get("mentioned_by") or []), row.get("ticker") or ""),
    )
    status = "available" if rows or len(failures) < len(handles) else "degraded"
    payload: dict[str, Any] = {
        "source": "agent_reach",
        "cost_mode": "auth_required",
        "status": status,
        "tickers": rows,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "raw": {"handles": handles, "failures": failures[:5]},
    }
    if failures and not rows:
        payload["note"] = "; ".join(failures[:2])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Agent Reach/twitter-cli into social JSON")
    parser.add_argument("--market", default="US")
    parser.add_argument("--handles", default="", help="Comma-separated X handles; defaults to content/influencers.json")
    parser.add_argument("--influencers-path", default=str(DEFAULT_INFLUENCERS))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--twitter-bin", default="twitter")
    parser.add_argument("--max-handles", type=int, default=8)
    parser.add_argument("--limit-per-handle", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()

    handles = [
        _normalise_handle(h)
        for h in args.handles.split(",")
        if _normalise_handle(h)
    ]
    if not handles:
        handles = _handles_from_file(args.influencers_path, market=args.market, limit=args.max_handles)

    payload = build_agent_reach_payload(
        handles=handles[:max(args.max_handles, 0)],
        credentials=load_credentials(config_path=args.config),
        twitter_bin=args.twitter_bin,
        limit_per_handle=max(args.limit_per_handle, 1),
        timeout=args.timeout,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
