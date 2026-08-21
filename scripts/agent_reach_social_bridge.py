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
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts import influencer_roster_runtime, social_ticker_contract
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import influencer_roster_runtime  # type: ignore
    import social_ticker_contract  # type: ignore


REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path.home() / ".agent-reach" / "config.yaml"
DEFAULT_INFLUENCERS = influencer_roster_runtime.resolve_roster_path()
DEFAULT_UNIVERSE_DIR = REPO / "reports" / "universe"

Runner = Callable[..., subprocess.CompletedProcess[str]]

TICKER_RE = re.compile(
    r"(?<![A-Za-z0-9_$])\$([A-Za-z][A-Za-z0-9]{0,5})(?![A-Za-z0-9_])"
    r"|(?<![A-Za-z0-9_$])([A-Z]{2,5})(?![A-Za-z0-9_])"
)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
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

    cfg = load_agent_reach_config(env.get("AGENT_REACH_CONFIG") or config_path)
    auth = str(cfg.get("twitter_auth_token") or "").strip()
    ct0 = str(cfg.get("twitter_ct0") or "").strip()
    return {"auth_token": auth, "ct0": ct0} if auth and ct0 else {}


def resolve_twitter_bin(
    twitter_bin: str | None = None,
    *,
    env: dict[str, str] | None = None,
) -> str:
    env = env if env is not None else os.environ
    return str(twitter_bin or env.get("AGENT_REACH_TWITTER_BIN") or "twitter").strip() or "twitter"


def twitter_bin_available(
    twitter_bin: str | None = None,
    *,
    env: dict[str, str] | None = None,
) -> bool:
    binary = resolve_twitter_bin(twitter_bin, env=env)
    expanded = Path(binary).expanduser()
    if os.sep in binary or (os.altsep and os.altsep in binary):
        return expanded.is_file() and os.access(expanded, os.X_OK)
    search_path = env.get("PATH", "") if env is not None else None
    return shutil.which(binary, path=search_path) is not None


def _twitter_missing_payload(
    *,
    handle: str | None = None,
    twitter_bin: str | None = None,
) -> dict[str, Any]:
    note = (
        "Agent Reach twitter-cli missing: "
        f"`{twitter_bin or 'twitter'}` is not installed or not in PATH"
    )
    payload: dict[str, Any] = {
        "source": "agent_reach",
        "cost_mode": "auth_required",
        "status": "degraded",
        "auth_status": "configured",
        "tool_status": "missing",
        "note": note,
    }
    if handle is not None:
        payload.update({
            "handle": handle,
            "url": f"https://x.com/{handle}" if handle else "",
            "posts": [],
        })
    else:
        payload["tickers"] = []
    return payload


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
    binary = resolve_twitter_bin(twitter_bin, env=child_env)
    return call(
        [binary, *args],
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


def _extract_ticker_evidence(
    text: str,
    *,
    known_tickers: set[str],
) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for match in TICKER_RE.finditer(text or ""):
        raw = match.group(1) or match.group(2) or ""
        ticker = raw.upper().lstrip("$")
        explicit_cashtag = match.group(1) is not None
        known_universe_symbol = ticker in known_tickers
        if not ticker:
            continue
        if not explicit_cashtag and not known_universe_symbol:
            continue
        if len(ticker) == 1 and not explicit_cashtag:
            continue
        evidence = out.setdefault(ticker, {
            "explicit_cashtag": False,
            "known_universe_symbol": False,
        })
        evidence["explicit_cashtag"] = bool(
            evidence["explicit_cashtag"] or explicit_cashtag
        )
        evidence["known_universe_symbol"] = bool(
            evidence["known_universe_symbol"] or known_universe_symbol
        )
    return out


def _extract_tickers(text: str, *, known_tickers: set[str] | None = None) -> list[str]:
    return list(_extract_ticker_evidence(text, known_tickers=known_tickers or set()))


def _add_ticker(
    agg: dict[str, dict[str, Any]],
    *,
    ticker: str,
    handle: str,
    citations: list[str],
    ticker_evidence: dict[str, bool],
) -> None:
    row = agg.setdefault(ticker, {
        "ticker": ticker,
        "mentioned_by": [],
        "citations": [],
        "note": "Agent Reach twitter-cli user-posts match",
        "ticker_evidence": {
            "explicit_cashtag": False,
            "known_universe_symbol": False,
        },
    })
    if handle and handle not in row["mentioned_by"]:
        row["mentioned_by"].append(handle)
    for url in citations:
        if url not in row["citations"]:
            row["citations"].append(url)
    for key in ("explicit_cashtag", "known_universe_symbol"):
        row["ticker_evidence"][key] = bool(
            row["ticker_evidence"][key] or ticker_evidence.get(key)
        )


def build_agent_reach_payload(
    *,
    handles: list[str],
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    limit_per_handle: int = 20,
    timeout: float = 30,
    known_tickers: set[str] | None = None,
    universe_dir: str | Path = DEFAULT_UNIVERSE_DIR,
) -> dict[str, Any]:
    resolved_twitter_bin = resolve_twitter_bin(twitter_bin, env=env)
    if not credentials.get("auth_token") or not credentials.get("ct0"):
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "missing",
            "tool_status": "unknown",
            "tickers": [],
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }
    if runner is None and not twitter_bin_available(resolved_twitter_bin, env=env):
        return _twitter_missing_payload(twitter_bin=resolved_twitter_bin)
    if not handles:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "available",
            "tickers": [],
            "note": "No handles configured for Agent Reach bridge",
        }

    known = (
        {social_ticker_contract.normalize_ticker(ticker) for ticker in known_tickers}
        if known_tickers is not None
        else social_ticker_contract.load_known_tickers(universe_dir)
    )
    known.discard("")
    agg: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for handle in [_normalise_handle(h) for h in handles if _normalise_handle(h)]:
        try:
            result = run_twitter(
                ["user-posts", f"@{handle}", "-n", str(limit_per_handle)],
                credentials=credentials,
                twitter_bin=resolved_twitter_bin,
                runner=runner,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"@{handle}: timed out after {timeout:g}s")
            continue
        if result.returncode != 0:
            text = (result.stdout or "") + "\n" + (result.stderr or "")
            failures.append(f"@{handle}: {text.strip()[:160]}")
            continue
        tweet_text = result.stdout or ""
        citations = _extract_urls(tweet_text)
        for ticker, evidence in _extract_ticker_evidence(
            tweet_text,
            known_tickers=known,
        ).items():
            _add_ticker(
                agg,
                ticker=ticker,
                handle=handle,
                citations=citations,
                ticker_evidence=evidence,
            )

    rows = sorted(
        agg.values(),
        key=lambda row: (-len(row.get("mentioned_by") or []), row.get("ticker") or ""),
    )
    status = "available" if rows or len(failures) < len(handles) else "degraded"
    payload: dict[str, Any] = {
        "source": "agent_reach",
        "cost_mode": "auth_required",
        "status": status,
        "auth_status": "configured",
        "tool_status": "available",
        "tickers": rows,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "raw": {
            "handles": handles,
            "failures": failures[:5],
            "known_ticker_count": len(known),
        },
    }
    if failures and not rows:
        payload["note"] = "; ".join(failures[:2])
    return payload


def _normalise_post_row(row: dict[str, Any], *, handle: str) -> dict[str, Any] | None:
    text = str(
        row.get("text")
        or row.get("full_text")
        or row.get("content")
        or row.get("body")
        or ""
    ).strip()
    if not text:
        return None
    metrics = row.get("public_metrics") if isinstance(row.get("public_metrics"), dict) else {}
    url = str(row.get("url") or row.get("permalink") or "").strip()
    if not url:
        urls = _extract_urls(text)
        url = urls[0] if urls else ""
    return {
        "author": f"@{handle}",
        "text": text,
        "created_at": str(row.get("created_at") or row.get("date") or "").strip(),
        "url": url,
        "likes": int(row.get("likes") or row.get("like_count") or metrics.get("like_count") or 0),
        "retweets": int(
            row.get("retweets") or row.get("retweet_count") or metrics.get("retweet_count") or 0
        ),
    }


def _posts_from_json(data: Any, *, handle: str, limit: int) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = (
            data.get("posts")
            or data.get("tweets")
            or data.get("data")
            or data.get("items")
            or []
        )
    else:
        rows = []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post = _normalise_post_row(row, handle=handle)
        if post:
            out.append(post)
        if len(out) >= limit:
            break
    return out


def _posts_from_text(text: str, *, handle: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        urls = _extract_urls(raw)
        out.append({
            "author": f"@{handle}",
            "text": raw,
            "created_at": "",
            "url": urls[0] if urls else "",
            "likes": 0,
            "retweets": 0,
        })
        if len(out) >= limit:
            break
    return out


def _normalise_posts_output(text: str, *, handle: str, limit: int) -> list[dict[str, Any]]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
    except Exception:
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(stripped)
        except Exception:
            return _posts_from_text(stripped, handle=handle, limit=limit)
    posts = _posts_from_json(data, handle=handle, limit=limit)
    return posts or _posts_from_text(stripped, handle=handle, limit=limit)


def _parse_structured_output(text: str) -> Any:
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except Exception:
        try:
            import yaml  # type: ignore

            return yaml.safe_load(stripped)
        except Exception:
            return None


def _nested_dicts(data: Any, *, max_depth: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def visit(value: Any, depth: int) -> None:
        if depth < 0 or not isinstance(value, dict):
            return
        out.append(value)
        for key in ("user", "profile", "data", "result", "legacy", "core", "author"):
            child = value.get(key)
            if isinstance(child, dict):
                visit(child, depth - 1)

    visit(data, max_depth)
    return out


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            text = str(value).strip()
            if text:
                return text
    return ""


def _normalise_profile_output(text: str, *, handle: str) -> dict[str, Any]:
    data = _parse_structured_output(text)
    if data is None:
        return {}
    for row in _nested_dicts(data):
        screen_name = _first_text(row, (
            "screenName", "screen_name", "username", "userName", "handle",
        ))
        name = _first_text(row, ("name", "displayName", "display_name"))
        bio = _first_text(row, ("bio", "description", "profileDescription"))
        if not (screen_name or name or bio):
            continue
        clean_handle = _normalise_handle(screen_name or handle)
        profile_url = f"https://x.com/{clean_handle}" if clean_handle else ""
        website_url = _first_text(row, ("websiteUrl", "website_url", "url"))
        return {
            "handle": clean_handle,
            "name": name,
            "description": bio,
            "bio": bio,
            "url": profile_url or website_url,
            "website_url": website_url if website_url != profile_url else "",
        }
    return {}


def fetch_user_profile_payload(
    handle: str,
    *,
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 10,
) -> dict[str, Any]:
    handle = _normalise_handle(handle)
    resolved_twitter_bin = resolve_twitter_bin(twitter_bin, env=env)
    base = {
        "source": "agent_reach",
        "cost_mode": "auth_required",
        "handle": handle,
        "name": "",
        "description": "",
        "bio": "",
        "url": f"https://x.com/{handle}" if handle else "",
    }
    if not credentials.get("auth_token") or not credentials.get("ct0"):
        return {
            **base,
            "status": "degraded",
            "auth_status": "missing",
            "tool_status": "unknown",
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }
    if not handle:
        return {
            **base,
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "unknown",
            "note": "Missing X handle",
        }
    if runner is None and not twitter_bin_available(resolved_twitter_bin, env=env):
        payload = _twitter_missing_payload(handle=handle, twitter_bin=resolved_twitter_bin)
        payload.update({k: base[k] for k in ("name", "description", "bio")})
        return payload

    try:
        result = run_twitter(
            ["user", f"@{handle}", "--json"],
            credentials=credentials,
            twitter_bin=resolved_twitter_bin,
            runner=runner,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            **base,
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "available",
            "note": f"@{handle}: timed out after {timeout:g}s",
        }

    combined = (result.stdout or "").strip() or (result.stderr or "").strip()
    if result.returncode != 0:
        return {
            **base,
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "available",
            "note": combined[:240] or f"Agent Reach exited {result.returncode}",
        }

    profile = _normalise_profile_output(result.stdout or "", handle=handle)
    if not profile:
        return {
            **base,
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "available",
            "note": "Agent Reach returned no profile data for this handle",
        }
    return {
        **base,
        **profile,
        "status": "available",
        "auth_status": "configured",
        "tool_status": "available",
        "note": "",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def _tweet_rows_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = (
            data.get("tweets")
            or data.get("posts")
            or data.get("data")
            or data.get("items")
            or []
        )
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _author_from_tweet(row: dict[str, Any]) -> dict[str, str]:
    candidates = []
    for key in ("author", "user", "profile"):
        value = row.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    candidates.append(row)
    for candidate in candidates:
        handle = _first_text(candidate, (
            "screenName", "screen_name", "username", "userName", "handle",
        ))
        name = _first_text(candidate, ("name", "displayName", "display_name"))
        if handle or name:
            clean_handle = _normalise_handle(handle)
            return {
                "handle": clean_handle,
                "name": name,
                "url": f"https://x.com/{clean_handle}" if clean_handle else "",
            }
    return {"handle": "", "name": "", "url": ""}


def _author_match_score(query: str, author: dict[str, str]) -> float:
    q = str(query or "").strip().lower()
    if not q:
        return 0.0
    handle = author.get("handle", "").lower()
    name = author.get("name", "").lower()
    if name == q:
        return 3.0
    if handle == q:
        return 2.5
    if q in name:
        return 2.0
    if q in handle:
        return 1.5
    return 0.0


def search_account_payload(
    query: str,
    *,
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    limit: int = 8,
    timeout: float = 10,
) -> dict[str, Any]:
    q = str(query or "").strip()
    resolved_twitter_bin = resolve_twitter_bin(twitter_bin, env=env)
    base = {
        "source": "agent_reach_search",
        "cost_mode": "auth_required",
        "status": "degraded",
        "handle": "",
        "name": "",
        "url": "",
        "description": "",
        "bio": "",
    }
    if not q:
        return {**base, "auth_status": "configured", "tool_status": "unknown", "note": "Missing search query"}
    if not credentials.get("auth_token") or not credentials.get("ct0"):
        return {
            **base,
            "auth_status": "missing",
            "tool_status": "unknown",
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }
    if runner is None and not twitter_bin_available(resolved_twitter_bin, env=env):
        payload = _twitter_missing_payload(twitter_bin=resolved_twitter_bin)
        payload.update(base)
        payload["tool_status"] = "missing"
        return payload

    try:
        result = run_twitter(
            ["search", q, "--json", "-n", str(max(1, min(limit, 20)))],
            credentials=credentials,
            twitter_bin=resolved_twitter_bin,
            runner=runner,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            **base,
            "auth_status": "configured",
            "tool_status": "available",
            "note": f"search timed out after {timeout:g}s",
        }

    combined = (result.stdout or "").strip() or (result.stderr or "").strip()
    if result.returncode != 0:
        return {
            **base,
            "auth_status": "configured",
            "tool_status": "available",
            "note": combined[:240] or f"Agent Reach exited {result.returncode}",
        }

    data = _parse_structured_output(result.stdout or "")
    authors = [_author_from_tweet(row) for row in _tweet_rows_from_json(data)]
    authors = [a for a in authors if a.get("handle")]
    authors.sort(key=lambda a: (-_author_match_score(q, a), a.get("handle", "").lower()))
    if not authors or _author_match_score(q, authors[0]) <= 0:
        return {
            **base,
            "auth_status": "configured",
            "tool_status": "available",
            "note": "Agent Reach search returned no matching account authors",
        }
    best = authors[0]
    return {
        **base,
        **best,
        "status": "available",
        "auth_status": "configured",
        "tool_status": "available",
        "note": "matched account from recent X search authors",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def fetch_user_posts_payload(
    handle: str,
    *,
    credentials: dict[str, str],
    twitter_bin: str = "twitter",
    runner: Runner | None = None,
    env: dict[str, str] | None = None,
    limit: int = 5,
    timeout: float = 10,
) -> dict[str, Any]:
    handle = _normalise_handle(handle)
    resolved_twitter_bin = resolve_twitter_bin(twitter_bin, env=env)
    if not credentials.get("auth_token") or not credentials.get("ct0"):
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "missing",
            "tool_status": "unknown",
            "handle": handle,
            "url": f"https://x.com/{handle}" if handle else "",
            "posts": [],
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }
    if not handle:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "unknown",
            "handle": "",
            "url": "",
            "posts": [],
            "note": "Missing X handle",
        }
    if runner is None and not twitter_bin_available(resolved_twitter_bin, env=env):
        return _twitter_missing_payload(handle=handle, twitter_bin=resolved_twitter_bin)

    result = run_twitter(
        ["user-posts", f"@{handle}", "-n", str(max(1, min(limit, 20)))],
        credentials=credentials,
        twitter_bin=resolved_twitter_bin,
        runner=runner,
        env=env,
        timeout=timeout,
    )
    combined = (result.stdout or "").strip() or (result.stderr or "").strip()
    if result.returncode != 0:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "available",
            "handle": handle,
            "url": f"https://x.com/{handle}",
            "posts": [],
            "note": combined[:240] or f"Agent Reach exited {result.returncode}",
        }

    posts = _normalise_posts_output(result.stdout or "", handle=handle, limit=limit)
    return {
        "source": "agent_reach",
        "cost_mode": "auth_required",
        "status": "available" if posts else "degraded",
        "auth_status": "configured",
        "tool_status": "available",
        "handle": handle,
        "url": f"https://x.com/{handle}",
        "posts": posts,
        "note": "" if posts else "Agent Reach returned no posts for this handle",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Agent Reach/twitter-cli into social JSON")
    parser.add_argument("--market", default="US")
    parser.add_argument("--handles", default="", help="Comma-separated X handles; defaults to the editable influencer roster")
    parser.add_argument("--influencers-path", default=str(DEFAULT_INFLUENCERS))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--twitter-bin", default="")
    parser.add_argument("--max-handles", type=int, default=8)
    parser.add_argument("--limit-per-handle", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--universe-dir", default=str(DEFAULT_UNIVERSE_DIR))
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
        twitter_bin=resolve_twitter_bin(args.twitter_bin or None),
        limit_per_handle=max(args.limit_per_handle, 1),
        timeout=args.timeout,
        universe_dir=args.universe_dir,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
