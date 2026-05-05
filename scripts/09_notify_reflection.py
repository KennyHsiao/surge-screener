#!/usr/bin/env python3
"""
Stage 9 — Push monthly reflection summary to Telegram.
Reads the reflection report and sends a condensed version via Telegram.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send message to Telegram, splitting if needed."""
    max_len = 4096
    chunks = []

    if len(text) <= max_len:
        chunks = [text]
    else:
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
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"[notify_reflection] Error: {resp.status_code}", file=sys.stderr)
                success = False
        except Exception as e:
            print(f"[notify_reflection] Send error: {e}", file=sys.stderr)
            success = False

    return success


def extract_summary(report_path: str) -> str:
    """Extract key metrics from reflection report for Telegram."""
    content = Path(report_path).read_text(encoding="utf-8")

    lines = [
        "📊 Monthly Self-Reflection Report",
        "",
    ]

    # Extract header info
    for line in content.split("\n"):
        if line.startswith("Lookback:") or line.startswith("Total picks"):
            lines.append(line)

    lines.append("")

    # Try to extract JSON metrics
    json_blocks = re.findall(r"```json\n(.*?)\n```", content, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)

            # Baseline metrics
            if "total_picks" in data:
                lines.append("📈 Baseline Metrics:")
                if "hit_15pct_30d_rate" in data:
                    lines.append(f"  Hit +15% in 30d: {data['hit_15pct_30d_rate']*100:.1f}%")
                if "hit_30pct_60d_rate" in data:
                    lines.append(f"  Hit +30% in 60d: {data['hit_30pct_60d_rate']*100:.1f}%")
                if "avg_fwd_30d_return" in data:
                    lines.append(f"  Avg 30d return: {data['avg_fwd_30d_return']:.1f}%")
                if "avg_max_drawdown_30d" in data:
                    lines.append(f"  Avg max DD 30d: {data['avg_max_drawdown_30d']:.1f}%")
                lines.append("")

            # Dimension correlations
            if isinstance(data, list) and data and "dimension" in data[0]:
                lines.append("🎯 Dimension Health:")
                for dim in data:
                    corr = dim.get("correlation")
                    v = dim.get("verdict", "?")
                    name = dim.get("dimension", "?")
                    if corr is not None:
                        emoji = "✅" if v in ("KEEP", "STRONG_KEEP") else "⚠️"
                        lines.append(f"  {emoji} {name}: r={corr:.3f} ({v})")
                lines.append("")

            # Pattern analysis
            if isinstance(data, list) and data and "pattern" in data[0]:
                lines.append("📊 Pattern Performance:")
                for p in data[:5]:
                    lines.append(
                        f"  {p['pattern']}: n={p['count']}, "
                        f"avg 30d={p.get('avg_30d_return', '?')}%"
                    )
                lines.append("")

        except (json.JSONDecodeError, TypeError):
            continue

    # Extract LLM narrative if present
    llm_section = content.split("## LLM Reflection")
    if len(llm_section) > 1:
        narrative = llm_section[1].strip()
        # Try to find narrative_summary in JSON
        try:
            json_match = re.search(r"\{.*\}", narrative, re.DOTALL)
            if json_match:
                report_json = json.loads(json_match.group())
                if "narrative_summary" in report_json:
                    lines.append("📝 Summary:")
                    lines.append(report_json["narrative_summary"][:500])
                if "proposed_prompt_changes" in report_json:
                    changes = report_json["proposed_prompt_changes"]
                    if changes:
                        lines.append("")
                        lines.append(f"🔧 {len(changes)} prompt changes proposed — review in repo")
        except (json.JSONDecodeError, TypeError):
            # Just include first 300 chars of narrative
            lines.append("📝 See full report in repo for details.")

    lines.append("")
    lines.append("Full report committed to reports/reflections/")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Stage 9: Notify Reflection to Telegram")
    parser.add_argument("--report", required=True, help="Path to reflection .md")
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[notify_reflection] Telegram credentials not set, skipping.",
              file=sys.stderr)
        sys.exit(0)

    if not Path(args.report).exists():
        print(f"[notify_reflection] Report not found: {args.report}",
              file=sys.stderr)
        sys.exit(1)

    text = extract_summary(args.report)
    ok = send_telegram_message(bot_token, chat_id, text)

    if ok:
        print(f"[notify_reflection] Sent to Telegram ({len(text)} chars)")
    else:
        print("[notify_reflection] Failed to send", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
