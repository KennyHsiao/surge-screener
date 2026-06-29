#!/usr/bin/env python3
"""UI label guard: the insider overlay must be attributed to the SELECTED source.

EDGAR is open-market Form-4 P/S over the last 30 days; yfinance is a 6-month
aggregate. Rendering EDGAR values under the 6-month wording is a false
provenance/window claim on real-money data (Codex TF-1 r15). These check the
pure label helper that the leaderboard column + detail line derive from.

Run:  .venv/bin/python scripts/test_theme_flow_ui_labels.py
(needs streamlit, which the dashboard venv has; emits a harmless no-runtime warning.)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_insider_labels_match_source():
    from ui import theme_flow as tfui
    hdr_e, help_e, phrase_e, tail_e = tfui._insider_labels("edgar")
    # EDGAR mode must say 30 days / Form-4 P/S, NEVER the 6-month wording.
    for s in (hdr_e, help_e, phrase_e, tail_e):
        assert "6 個月" not in s and "6M" not in s, s
    assert "30" in hdr_e and "30" in phrase_e
    assert "P/S" in help_e or "P/S" in phrase_e

    hdr_y, _, phrase_y, _ = tfui._insider_labels("yfinance")
    assert "6M" in hdr_y and "6 個月" in phrase_y

    # Unknown/None (e.g. the always-yfinance LLM read path) defaults to 6-month.
    assert tfui._insider_labels(None) == tfui._insider_labels("yfinance")


def test_heat_help_explains_adjusted_heat_components():
    from ui import theme_flow as tfui
    help_text = getattr(tfui, "_HEAT_HELP", "")
    assert "原始熱度" in help_text
    assert "訊號品質" in help_text
    assert "廣度" in help_text
    assert "集中度" in help_text


def test_insider_overlay_defaults_on():
    from ui import theme_flow as tfui
    assert tfui.DEFAULT_SHOW_INSIDER is True


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            t()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
