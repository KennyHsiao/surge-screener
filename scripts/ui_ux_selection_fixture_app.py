#!/usr/bin/env python3
"""Dedicated real-render Streamlit entrypoint for UX-1B selector evidence."""

from __future__ import annotations

import html
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts import ui_ux_fixtures as fixtures  # noqa: E402

try:
    environment = fixtures.bootstrap_fixture_environment()
except fixtures.FixtureConfigurationError as exc:
    raise SystemExit(str(exc)) from None
if environment.source_root is not None and environment.source_root != SOURCE_ROOT:
    raise SystemExit("UX-1B fixture SOURCE_ROOT differs from its executable mirror")

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Quant Radar UX-1B Selection Controls",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

case_name = fixtures.selection_case_from_url(str(st.context.url))
capture_id = fixtures._capture_from_query_params(st)
generation_key = "_quant_radar_ux1b_selection_render_generation"
previous_generation = st.session_state.get(generation_key, 0)
if (
    type(previous_generation) is not int
    or previous_generation < 0
    or previous_generation >= 1_000_000
):
    raise SystemExit("UX-1B selection render generation is invalid")
render_generation = previous_generation + 1
st.session_state[generation_key] = render_generation
fixtures.render_selection_case(case_name, capture_id)
st.markdown(
    (
        '<span id="ux1b-selection-ready" aria-hidden="true" '
        'style="display:none" '
        f'data-capture-id="{html.escape(capture_id, quote=True)}" '
        f'data-render-generation="{render_generation}">'
        f'{html.escape(case_name)}</span>'
    ),
    unsafe_allow_html=True,
)
