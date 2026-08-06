#!/usr/bin/env python3
"""Owned UX-1B semantic-state gallery; it is never a production route."""

from __future__ import annotations

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

from ui import _design  # noqa: E402


SURFACE_STYLES = """
<style>
.st-key-ux1b_surface_canvas,
.st-key-ux1b_surface_panel,
.st-key-ux1b_surface_elevated {
  border: 1px solid #394154;
  border-radius: 8px;
  margin-block: 1rem;
  padding: 24px;
}
.st-key-ux1b_surface_canvas { background: #0e1117; }
.st-key-ux1b_surface_panel { background: #1a1f2b; }
.st-key-ux1b_surface_elevated { background: #232938; }
.ux1b-signal-sample {
  border: 1px solid currentColor;
  border-radius: 999px;
  display: inline-flex;
  font-weight: 700;
  gap: .35rem;
  margin: .25rem .5rem .25rem 0;
  padding: .25rem .6rem;
}
.ux1b-avoid { color: #ef4444; }
.ux1b-bearish { color: #ef553b; }
</style>
"""

SURFACES = (
    ("canvas", "Canvas · #0e1117"),
    ("panel", "Panel · #1a1f2b"),
    ("elevated", "Elevated · #232938"),
)


def _owner(surface: str, case: str):
    return st.container(key=f"ux1b_owner_{surface}_{case}")


def _render_surface(surface: str, label: str) -> None:
    with st.container(key=f"ux1b_surface_{surface}"):
        st.header(label)

        with _owner(surface, "primary"):
            st.button("主要操作", type="primary", key=f"ux1b_{surface}_primary")

        with _owner(surface, "form_submit"):
            with st.form(f"ux1b_{surface}_form"):
                st.text_input("固定輸入", value="UX-1B", key=f"ux1b_{surface}_input")
                st.form_submit_button("送出表單", type="primary")

        with _owner(surface, "download"):
            st.download_button(
                "下載固定資料",
                data=b"ux1b\n",
                file_name="ux1b.txt",
                mime="text/plain",
                type="primary",
                key=f"ux1b_{surface}_download",
            )

        with _owner(surface, "link_button"):
            st.link_button(
                "開啟本頁",
                url="#ux1b-local-anchor",
                type="primary",
                key=f"ux1b_{surface}_link_button",
            )

        with _owner(surface, "tertiary"):
            st.button(
                "次要文字操作",
                type="tertiary",
                key=f"ux1b_{surface}_tertiary",
            )

        with _owner(surface, "disabled"):
            st.button(
                "停用操作",
                type="primary",
                disabled=True,
                key=f"ux1b_{surface}_disabled",
            )

        with _owner(surface, "tabs"):
            first, second = st.tabs(["已選分頁", "其他分頁"])
            with first:
                st.caption("分頁狀態以文字與底線共同表示。")
            with second:
                st.caption("固定第二分頁。")

        with _owner(surface, "markdown_link"):
            st.markdown("[有底線的本頁連結](#ux1b-local-anchor)")

        with _owner(surface, "checkbox"):
            st.checkbox("核取方塊標籤", value=True, key=f"ux1b_{surface}_checkbox")

        with _owner(surface, "radio"):
            st.radio(
                "單選標籤",
                options=("已選項", "其他項"),
                index=0,
                key=f"ux1b_{surface}_radio",
            )

        with _owner(surface, "toggle"):
            st.toggle("切換標籤", value=True, key=f"ux1b_{surface}_toggle")

        with _owner(surface, "slider"):
            st.slider(
                "滑桿標籤",
                min_value=0,
                max_value=100,
                value=60,
                key=f"ux1b_{surface}_slider",
            )

        with _owner(surface, "radio_horizontal"):
            st.radio(
                "水平單選標籤",
                options=("已選項", "其他項"),
                index=0,
                key=f"ux1b_{surface}_radio_horizontal",
                horizontal=True,
            )

        with _owner(surface, "selectbox"):
            st.selectbox(
                "下拉選單標籤",
                options=("已選項", "其他項"),
                index=0,
                key=f"ux1b_{surface}_selectbox",
            )

        with _owner(surface, "alerts"):
            st.info("ℹ️ 資訊狀態：固定說明文字")
            st.success("✅ 成功狀態：固定說明文字")
            st.warning("⚠️ 警告狀態：固定說明文字")
            st.error("⛔ 錯誤狀態：固定說明文字")

        with _owner(surface, "signals"):
            st.markdown(
                '<span class="ux1b-signal-sample ux1b-avoid">⛔ AVOID 避免</span>'
                '<span class="ux1b-signal-sample ux1b-bearish">▼ Bearish 看跌</span>',
                unsafe_allow_html=True,
            )


st.set_page_config(page_title="Quant Radar UX-1B Theme States", layout="wide")
st.markdown(SURFACE_STYLES, unsafe_allow_html=True)
theme_builder = getattr(_design, "build_global_theme_css", None)
if callable(theme_builder):
    st.markdown(theme_builder(), unsafe_allow_html=True)
else:
    raise RuntimeError("UX-1B theme CSS builder is unavailable")
st.title("UX-1B Semantic Theme State Gallery")
st.caption("Fixture-only · deterministic · no provider or production artifact access")
st.markdown('<span id="ux1b-local-anchor"></span>', unsafe_allow_html=True)

for surface_name, surface_label in SURFACES:
    _render_surface(surface_name, surface_label)

fixtures.record_theme_gallery_render(st)
st.markdown(
    '<span id="ux1b-theme-ready" data-owner-count="48" '
    'aria-hidden="true">ux1b-theme-ready</span>',
    unsafe_allow_html=True,
)
