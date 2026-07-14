#!/usr/bin/env python3
"""Self-contained tests for free-first social intelligence snapshots."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "social_intelligence_under_test",
        ROOT / "scripts" / "social_intelligence.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _x_picks() -> dict:
    return {
        "source": "x_influencers",
        "market": "US",
        "window": "2026-07-01..2026-07-03",
        "generated_at": "2026-07-03T12:00:00Z",
        "citations": ["https://x.com/alpha/status/1"],
        "tickers": [
            {
                "symbol": "NVDA",
                "mentioned_by": ["alpha", "beta"],
                "count": 2,
                "skew": "bullish",
                "conviction": "high",
                "note": "AI infra bottleneck mention",
            }
        ],
    }


def _ranked() -> dict:
    return {
        "scan_date": "2026-07-03",
        "ranked_candidates": [
            {"ticker": "NVDA", "rank_score": 82.5, "rank_bucket": "priority", "last_price": 150.0}
        ],
    }


def _options_flow() -> dict:
    return {
        "as_of_date": "2026-07-03",
        "signals": [
            {"ticker": "NVDA", "direction": "bullish", "flow_score": 78.0}
        ],
    }


def test_source_statuses_mark_paid_and_missing_sources_without_keys() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        env = {
            "AGENT_REACH_CONFIG": str(root / "missing-config.yaml"),
            "AGENT_REACH_TWITTER_BIN": str(root / "missing-twitter"),
        }

        statuses = mod.source_statuses(env=env, agent_reach_command=None)

    if statuses["xai_grok"]["cost_mode"] != "paid_optional":
        raise AssertionError(statuses)
    if statuses["xai_grok"]["status"] != "unavailable":
        raise AssertionError(statuses)
    if statuses["x_official_api"]["cost_mode"] != "paid_optional":
        raise AssertionError(statuses)
    if statuses["agent_reach"]["status"] != "unavailable":
        raise AssertionError(statuses)
    if statuses["stocktwits"]["cost_mode"] != "free":
        raise AssertionError(statuses)
    if statuses["apewisdom"]["cost_mode"] != "free":
        raise AssertionError(statuses)


def test_source_statuses_degrades_when_cookie_configured_but_twitter_cli_missing() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        config = root / "config.yaml"
        config.write_text(
            "twitter_auth_token: auth-secret\n"
            "twitter_ct0: csrf-secret\n",
            encoding="utf-8",
        )
        statuses = mod.source_statuses(
            env={
                "AGENT_REACH_CONFIG": str(config),
                "AGENT_REACH_TWITTER_BIN": str(root / "missing-twitter"),
            },
            agent_reach_command=None,
        )

    agent = statuses["agent_reach"]
    if agent["status"] != "degraded":
        raise AssertionError(statuses)
    if "twitter-cli" not in agent.get("note", ""):
        raise AssertionError(statuses)


def test_agent_reach_timeout_degrades_without_raising() -> None:
    mod = _load_module()

    def timeout_runner(argv, timeout):  # noqa: ANN001
        raise subprocess.TimeoutExpired(argv, timeout)

    result = mod.fetch_agent_reach(
        command=["agent-reach", "search", "AI infra"],
        timeout=0.01,
        runner=timeout_runner,
    )

    if result["status"] != "degraded":
        raise AssertionError(result)
    if result["cost_mode"] != "auth_required":
        raise AssertionError(result)


def test_agent_reach_preserves_bridge_degraded_status() -> None:
    mod = _load_module()

    def degraded_runner(argv, timeout):  # noqa: ANN001
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({
                "status": "degraded",
                "cost_mode": "auth_required",
                "tickers": [],
                "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
            }),
            stderr="",
        )

    result = mod.fetch_agent_reach(
        command=["agent-reach-bridge"],
        runner=degraded_runner,
    )

    if result["status"] != "degraded":
        raise AssertionError(result)
    if "twitter_auth_token" not in result["note"]:
        raise AssertionError(result)


def test_agent_reach_default_timeout_matches_bounded_bridge_budget() -> None:
    mod = _load_module()
    seen = {}

    def available_runner(argv, timeout):  # noqa: ANN001
        seen["timeout"] = timeout
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"status": "available", "cost_mode": "auth_required", "tickers": []}),
            stderr="",
        )

    result = mod.fetch_agent_reach(
        command=["agent-reach-bridge"],
        runner=available_runner,
    )

    if result["status"] != "available":
        raise AssertionError(result)
    if seen["timeout"] != 60:
        raise AssertionError(seen)


def test_builtin_agent_reach_bridge_command_is_bounded_for_ui_refresh() -> None:
    mod = _load_module()

    command = mod._default_agent_reach_command("US")

    if "--max-handles" not in command or command[command.index("--max-handles") + 1] != "8":
        raise AssertionError(command)
    if "--limit-per-handle" not in command or command[command.index("--limit-per-handle") + 1] != "5":
        raise AssertionError(command)


def test_cli_uses_agent_reach_command_from_environment() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        command = root / "fake_agent_reach.py"
        reports = root / "reports"
        command.write_text(
            "import json\n"
            "print(json.dumps({'tickers': [{'ticker': 'NVDA', 'mentioned_by': ['alpha']}]}))\n",
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "AGENT_REACH_COMMAND": f"{sys.executable} {command}",
        }

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "social_intelligence.py"),
                "--market", "US",
                "--reports-dir", str(reports),
                "--x-picks-path", str(root / "missing-x-picks.json"),
                "--candidate-file", str(root / "missing-ranked.json"),
                "--options-flow-path", str(root / "missing-flow.json"),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=20,
        )

        if result.returncode != 0:
            raise AssertionError(result.stderr)
        snapshot = json.loads((reports / "social_intelligence" / "latest.json").read_text(
            encoding="utf-8"
        ))
        if snapshot["source_statuses"]["agent_reach"]["status"] != "available":
            raise AssertionError(snapshot)
        if snapshot["tickers"][0]["ticker"] != "NVDA":
            raise AssertionError(snapshot)


def test_cli_uses_builtin_agent_reach_bridge_without_environment_command() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        reports = root / "reports"
        config = root / "config.yaml"
        twitter = root / "twitter"
        config.write_text(
            "twitter_auth_token: auth-secret\n"
            "twitter_ct0: csrf-secret\n",
            encoding="utf-8",
        )
        twitter.write_text(
            "#!/usr/bin/env python3\n"
            "print('Watching $NVDA from bridge https://x.com/alpha/status/1')\n",
            encoding="utf-8",
        )
        twitter.chmod(0o755)
        env = {
            **os.environ,
            "AGENT_REACH_CONFIG": str(config),
            "AGENT_REACH_TWITTER_BIN": str(twitter),
        }
        env.pop("AGENT_REACH_COMMAND", None)

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "social_intelligence.py"),
                "--market", "US",
                "--reports-dir", str(reports),
                "--x-picks-path", str(root / "missing-x-picks.json"),
                "--candidate-file", str(root / "missing-ranked.json"),
                "--options-flow-path", str(root / "missing-flow.json"),
                "--agent-reach-timeout", "5",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=20,
        )

        if result.returncode != 0:
            raise AssertionError(result.stderr)
        snapshot = json.loads((reports / "social_intelligence" / "latest.json").read_text(
            encoding="utf-8"
        ))
        if snapshot["source_statuses"]["agent_reach"]["status"] != "available":
            raise AssertionError(snapshot)
        tickers = {row["ticker"] for row in snapshot["tickers"]}
        if "NVDA" not in tickers:
            raise AssertionError(snapshot)


def test_snapshot_combines_paid_discovery_with_free_heat_and_platform_validation() -> None:
    mod = _load_module()

    def fake_sentiment(ticker: str) -> dict:
        if ticker != "NVDA":
            raise AssertionError(ticker)
        return {
            "ticker": "NVDA",
            "stocktwits": {
                "total_messages": 12,
                "bullish": 5,
                "bearish": 2,
                "net_sentiment": 0.43,
            },
            "reddit_apewisdom": {
                "in_top_mentions": False,
                "rank": None,
                "mentions": 0,
                "note": "not in ApeWisdom top-100 by Reddit mentions (low buzz)",
            },
            "sources_available": ["stocktwits", "reddit_apewisdom"],
        }

    snapshot = mod.build_social_snapshot(
        x_picks=_x_picks(),
        agent_reach=None,
        sentiment_gatherer=fake_sentiment,
        ranked_candidates=_ranked(),
        options_flow=_options_flow(),
        as_of_date="2026-07-03",
        market="US",
    )

    rows = snapshot["tickers"]
    if len(rows) != 1:
        raise AssertionError(snapshot)
    row = rows[0]
    if row["ticker"] != "NVDA":
        raise AssertionError(row)
    if row["mentioned_by"] != ["alpha", "beta"]:
        raise AssertionError(row)
    if row["heat_baseline"]["stocktwits"]["status"] != "available":
        raise AssertionError(row)
    if row["heat_baseline"]["apewisdom"]["status"] != "available":
        raise AssertionError(row)
    if row["platform_validation"]["in_ranked_candidates"] is not True:
        raise AssertionError(row)
    if row["platform_validation"]["options_flow_score"] != 78.0:
        raise AssertionError(row)
    if row["labels"]["early_signal"] is not True:
        raise AssertionError(row)
    if row["labels"]["crowded"] is not False:
        raise AssertionError(row)
    if row["labels"]["paid_data_needed"] is not True:
        raise AssertionError(row)
    if "paid_optional" not in row["cost_modes"]:
        raise AssertionError(row)


def test_snapshot_does_not_reingest_own_legacy_quickpick() -> None:
    mod = _load_module()
    legacy = {
        "source": "social_intelligence",
        "tickers": [
            {
                "symbol": "NVDA",
                "mentioned_by": ["old"],
                "note": "stale generated quick-pick",
            }
        ],
    }

    def fail_sentiment(ticker: str) -> dict:
        raise AssertionError(ticker)

    snapshot = mod.build_social_snapshot(
        x_picks=legacy,
        agent_reach=None,
        sentiment_gatherer=fail_sentiment,
        as_of_date="2026-07-03",
        market="US",
    )

    if snapshot["tickers"] != []:
        raise AssertionError(snapshot)


def test_snapshot_records_agent_reach_degraded_status() -> None:
    mod = _load_module()

    snapshot = mod.build_social_snapshot(
        x_picks=None,
        agent_reach={
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "tickers": [],
            "note": "Agent Reach timed out",
        },
        sentiment_gatherer=lambda ticker: {},
        as_of_date="2026-07-03",
        market="US",
    )

    status = snapshot["source_statuses"]["agent_reach"]
    if status["status"] != "degraded":
        raise AssertionError(snapshot)
    if status["note"] != "Agent Reach timed out":
        raise AssertionError(snapshot)


def test_snapshot_keeps_apewisdom_baseline_when_stocktwits_is_unavailable() -> None:
    mod = _load_module()

    x_picks = _x_picks()
    x_picks["tickers"] = [{"symbol": "AMD", "mentioned_by": ["alpha"], "count": 1}]

    def fake_sentiment(ticker: str) -> dict:
        return {
            "ticker": ticker,
            "stocktwits": None,
            "reddit_apewisdom": {
                "in_top_mentions": True,
                "rank": 8,
                "mentions": 120,
                "mention_change_pct": 40.0,
            },
            "sources_available": ["reddit_apewisdom"],
        }

    snapshot = mod.build_social_snapshot(
        x_picks=x_picks,
        sentiment_gatherer=fake_sentiment,
        as_of_date="2026-07-03",
        market="US",
    )

    row = snapshot["tickers"][0]
    if row["heat_baseline"]["stocktwits"]["status"] != "unavailable":
        raise AssertionError(row)
    if row["heat_baseline"]["apewisdom"]["mentions"] != 120:
        raise AssertionError(row)
    if row["labels"]["crowded"] is not True:
        raise AssertionError(row)


def test_write_snapshot_writes_dated_latest_and_legacy_quickpick() -> None:
    mod = _load_module()

    def fake_sentiment(ticker: str) -> dict:
        return {
            "ticker": ticker,
            "stocktwits": {"total_messages": 4, "bullish": 1, "bearish": 0},
            "reddit_apewisdom": {"in_top_mentions": False, "mentions": 0},
            "sources_available": ["stocktwits", "reddit_apewisdom"],
        }

    with tempfile.TemporaryDirectory() as d:
        reports = Path(d) / "reports"
        snapshot = mod.build_social_snapshot(
            x_picks=_x_picks(),
            sentiment_gatherer=fake_sentiment,
            ranked_candidates=_ranked(),
            options_flow=_options_flow(),
            as_of_date="2026-07-03",
            market="US",
        )

        result = mod.write_social_snapshot(snapshot, reports_dir=reports)

        dated = reports / "social_intelligence" / "2026-07-03.json"
        latest = reports / "social_intelligence" / "latest.json"
        legacy = reports / "x_influencer_picks.json"
        if result["snapshot_path"] != str(dated):
            raise AssertionError(result)
        if not dated.is_file() or not latest.is_file() or not legacy.is_file():
            raise AssertionError([dated.exists(), latest.exists(), legacy.exists()])
        legacy_payload = json.loads(legacy.read_text(encoding="utf-8"))
        if legacy_payload["tickers"][0]["symbol"] != "NVDA":
            raise AssertionError(legacy_payload)
        if "Early Signal" not in legacy_payload["tickers"][0]["badges"]:
            raise AssertionError(legacy_payload)


def test_write_snapshot_preserves_shared_quickpick_symlink() -> None:
    mod = _load_module()
    snapshot = {
        "market": "US",
        "as_of_date": "2026-07-13",
        "generated_at": "2026-07-13T12:00:00Z",
        "tickers": [],
    }

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        reports = root / "current" / "reports"
        shared = root / "shared"
        reports.mkdir(parents=True)
        shared.mkdir()
        quickpick = reports / "x_influencer_picks.json"
        target = shared / "x_influencer_picks.json"
        quickpick.symlink_to(target)

        mod.write_social_snapshot(snapshot, reports_dir=reports)

        if not quickpick.is_symlink():
            raise AssertionError("scheduled social write replaced the shared-file symlink")
        payload = json.loads(target.read_text(encoding="utf-8"))
        if payload.get("source") != "social_intelligence":
            raise AssertionError(payload)


def test_legacy_quickpick_payload_skips_malformed_rows() -> None:
    mod = _load_module()

    payload = mod.legacy_quickpick_payload({
        "market": "US",
        "as_of_date": "2026-07-03",
        "generated_at": "2026-07-03T12:00:00Z",
        "tickers": [
            None,
            {
                "ticker": "NVDA",
                "mentioned_by": ["alpha"],
                "citations": ["https://x.com/alpha/status/1"],
                "labels": {"early_signal": True},
            },
        ],
    })

    if len(payload["tickers"]) != 1:
        raise AssertionError(payload)
    if payload["tickers"][0]["symbol"] != "NVDA":
        raise AssertionError(payload)
    if payload["citations"] != ["https://x.com/alpha/status/1"]:
        raise AssertionError(payload)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
