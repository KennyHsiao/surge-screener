#!/usr/bin/env python3
"""
Stage 5 — Push daily summary to Telegram.
Reads the summary.md report and sends it via Telegram Bot API.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def send_telegram_message(bot_token: str, chat_id: str, text: str,
                          parse_mode: str = "Markdown") -> bool:
    """Send a message via Telegram Bot API. Split if too long."""
    max_len = 4096
    chunks = []

    if len(text) <= max_len:
        chunks = [text]
    else:
        # Split on double newlines to preserve formatting
        parts = text.split("\n\n")
        current = ""
        for part in parts:
            if len(current) + len(part) + 2 > max_len:
                if current:
                    chunks.append(current)
                current = part
            else:
                current = current + "\n\n" + part if current else part
        if current:
            chunks.append(current)

    success = True
    for chunk in chunks:
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"[notify] Telegram API error: {resp.status_code} {resp.text}",
                      file=sys.stderr)
                # Retry without parse_mode if Markdown fails
                resp2 = httpx.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )
                if resp2.status_code != 200:
                    success = False
        except Exception as e:
            print(f"[notify] Send error: {e}", file=sys.stderr)
            success = False

    return success


def format_report_for_telegram(report_path: str, max_tickers: int = 5) -> str:
    """Read report and format for Telegram."""
    path = Path(report_path)

    if path.suffix == ".md":
        text = path.read_text(encoding="utf-8")
        # Truncate if needed — keep header + top N picks
        lines = text.split("\n")
        result_lines = []
        pick_count = 0
        for line in lines:
            result_lines.append(line)
            if line.startswith("### #"):
                pick_count += 1
                if pick_count > max_tickers:
                    result_lines.append(
                        f"\n... and more. See full report in repo."
                    )
                    break
        # Add footer sections if we didn't truncate
        if pick_count <= max_tickers:
            return text
        return "\n".join(result_lines)

    elif path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)

        picks = data.get("ranked_picks", [])[:max_tickers]
        lines = [
            f"📊 {data.get('report_date', '')} Surge Screener",
            f"Regime: {data.get('regime_summary', '')}",
            f"Confirmed: {data.get('total_confirmed', 0)} picks",
            "",
        ]
        for p in picks:
            lines.append(
                f"#{p['rank']} ${p['ticker']} {p['final_score']}pts "
                f"{p['verdict']}\n  {p.get('thesis', '')[:100]}"
            )
        return "\n".join(lines)

    else:
        return path.read_text(encoding="utf-8")[:4000]


def main():
    parser = argparse.ArgumentParser(description="Stage 5: Telegram Notify")
    parser.add_argument("--report", required=True, help="Path to summary.md or .json")
    parser.add_argument("--max-tickers", type=int, default=5)
    parser.add_argument("--include-charts", type=str, default="false")
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[notify] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping.",
              file=sys.stderr)
        sys.exit(0)

    if not Path(args.report).exists():
        print(f"[notify] Report file not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    text = format_report_for_telegram(args.report, args.max_tickers)
    ok = send_telegram_message(bot_token, chat_id, text)

    if ok:
        print(f"[notify] Sent report to Telegram ({len(text)} chars)")
    else:
        print("[notify] Failed to send some messages", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
