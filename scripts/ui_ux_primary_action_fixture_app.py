#!/usr/bin/env python3
"""Fixture-only gallery for every UX-1B primary-action state boundary."""

from __future__ import annotations

import streamlit as st

from ui import _design


SURFACE_CSS = """
<style>
.st-key-ux1b_primary_canvas,
.st-key-ux1b_primary_panel,
.st-key-ux1b_primary_elevated {
  border: 1px solid #394154;
  border-radius: 8px;
  margin-block: 1rem;
  padding: 24px;
}
.st-key-ux1b_primary_canvas { background: #0e1117; }
.st-key-ux1b_primary_panel { background: #1a1f2b; }
.st-key-ux1b_primary_elevated { background: #232938; }
</style>
"""

SURFACES = (
    ("canvas", "Canvas"),
    ("panel", "Panel"),
    ("elevated", "Elevated"),
)


def _render_surface(surface: str, label: str) -> None:
    with st.container(key=f"ux1b_primary_{surface}"):
        st.subheader(label)
        st.button(
            f"{surface} focus primary",
            type="primary",
            key=f"ux1b_primary_focus_{surface}",
        )
        with st.form(f"ux1b_form_focus_{surface}"):
            st.form_submit_button(f"{surface} focus form", type="primary")
        st.download_button(
            f"{surface} focus download",
            data=b"ux1b\n",
            file_name="ux1b.txt",
            type="primary",
            key=f"ux1b_download_focus_{surface}",
        )
        st.link_button(
            f"{surface} focus link",
            url="#ux1b-primary-action-fixture",
            type="primary",
            key=f"ux1b_link_focus_{surface}",
        )

        st.button(
            f"{surface} disabled primary",
            type="primary",
            disabled=True,
            key=f"ux1b_primary_disabled_{surface}",
        )
        with st.form(f"ux1b_form_disabled_{surface}"):
            st.form_submit_button(
                f"{surface} disabled form",
                type="primary",
                disabled=True,
            )
        st.download_button(
            f"{surface} disabled download",
            data=b"ux1b\n",
            file_name="ux1b.txt",
            type="primary",
            disabled=True,
            key=f"ux1b_download_disabled_{surface}",
        )
        st.link_button(
            f"{surface} disabled link",
            url="#ux1b-primary-action-fixture",
            type="primary",
            disabled=True,
            key=f"ux1b_link_disabled_{surface}",
        )
        st.checkbox(
            f"{surface} disabled checked checkbox",
            value=True,
            disabled=True,
            key=f"ux1b_checkbox_checked_disabled_{surface}",
        )
        st.toggle(
            f"{surface} disabled checked toggle",
            value=True,
            disabled=True,
            key=f"ux1b_toggle_checked_disabled_{surface}",
        )
        st.radio(
            f"{surface} disabled checked radio",
            options=("Selected", "Other"),
            index=0,
            disabled=True,
            key=f"ux1b_radio_checked_disabled_{surface}",
        )


st.set_page_config(page_title="UX-1B Primary Action States", layout="wide")
st.html(_design.build_global_theme_css())
st.html(SURFACE_CSS)
st.title("UX-1B Primary Action State Fixture")
for surface_name, surface_label in SURFACES:
    _render_surface(surface_name, surface_label)
st.markdown('<span id="ux1b-primary-action-fixture"></span>', unsafe_allow_html=True)
