#!/usr/bin/env python3
"""Owned UX-0 Streamlit entrypoint; production continues to run ``app.py``."""

from __future__ import annotations

import html
import runpy
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# This import is intentionally safe before Streamlit: ui_ux_fixtures has only
# stdlib imports at module load.  Bootstrap must succeed before app code starts.
from scripts import ui_ux_fixtures as fixtures  # noqa: E402

try:
    environment = fixtures.bootstrap_fixture_environment()
except fixtures.FixtureConfigurationError as exc:
    raise SystemExit(str(exc)) from None
if environment.source_root is not None and environment.source_root != SOURCE_ROOT:
    raise SystemExit("UX-1B fixture SOURCE_ROOT differs from its executable mirror")

import streamlit as st  # noqa: E402

fixtures.install_navigation_proxy(st)
capture_id = fixtures._capture_from_query_params(st)
runpy.run_path(str(SOURCE_ROOT / "app.py"), run_name="__quant_radar_real_app__")
st.markdown(
    '<span id="ux1b-full-page-render-complete" aria-hidden="true" '
    f'style="display:none">{html.escape(capture_id)}</span>',
    unsafe_allow_html=True,
)
