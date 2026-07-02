#!/usr/bin/env python3
"""Offline tests for schedules-page reflection helpers."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_extract_llm_reflection_json_from_markdown_block() -> None:
    from ui import sys_schedules

    markdown = """# Monthly Self-Reflection

## Pre-computed Metrics

```json
{"total_picks": 1}
```

## LLM Reflection

{
  "sample_size_warning": {"message": "Only one pick."},
  "narrative_summary": "This is a status check.",
  "data_quality_flags": ["pattern_type missing"],
  "proposed_prompt_changes": [
    {"suggested_change": "Fix ledger logging", "user_action_required": true}
  ]
}

"""

    data = sys_schedules._extract_llm_reflection_json(markdown)

    require(isinstance(data, dict), "reflection JSON should parse")
    require(data["sample_size_warning"]["message"] == "Only one pick.",
            "sample warning should be preserved")
    require(data["data_quality_flags"] == ["pattern_type missing"],
            "data quality flags should be preserved")
    require(data["proposed_prompt_changes"][0]["user_action_required"] is True,
            "proposed actions should be preserved")


def test_extract_llm_reflection_json_returns_none_for_missing_block() -> None:
    from ui import sys_schedules

    require(sys_schedules._extract_llm_reflection_json("# No reflection") is None,
            "missing reflection section should return None")


def main() -> None:
    tests = [
        test_extract_llm_reflection_json_from_markdown_block,
        test_extract_llm_reflection_json_returns_none_for_missing_block,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
