"""Встроенный React SPA на Streamlit Cloud (без npm/uvicorn/публичного URL)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from demo.form_input import FormState, form_ready_for_recalc
from demo.payloads import prefill_payload, recalc_payload

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"


def dist_ready() -> bool:
    return (DIST / "index.html").is_file()


@st.cache_resource
def _component():
    return components.declare_component("ppt_msp_form", path=str(DIST))


@st.cache_data
def _prefill() -> dict:
    return prefill_payload()


def render() -> None:
    st.markdown(
        """
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
  html, body, [data-testid="stAppViewContainer"],
  [data-testid="stAppViewContainer"] > .main, [data-testid="stMain"],
  .main .block-container, [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"] {
    height: 100% !important; max-height: 100vh !important;
    margin: 0 !important; padding: 0 !important; overflow: hidden !important;
  }
  .block-container { max-width: 100% !important; padding: 0 !important; }
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  iframe {
    position: fixed !important; inset: 0 !important;
    width: 100vw !important; height: 100vh !important;
    border: 0 !important; z-index: 1000;
  }
</style>
""",
        unsafe_allow_html=True,
    )

    prefill = _prefill()
    result = st.session_state.get("ppt_react_result")
    error = st.session_state.get("ppt_react_error")
    request_id = st.session_state.get("ppt_react_request_id")

    event = _component()(
        prefill=prefill,
        result=result,
        error=error,
        request_id=request_id,
        key="ppt_msp_react",
    )

    if not event or not isinstance(event, dict):
        return
    if event.get("action") != "recalc":
        return

    req_id = event.get("id")
    if not req_id or req_id == st.session_state.get("ppt_react_done_id"):
        return

    st.session_state["ppt_react_done_id"] = req_id
    st.session_state["ppt_react_request_id"] = req_id
    st.session_state["ppt_react_error"] = None

    try:
        state = FormState.from_dict(event.get("form") or {})
        if not form_ready_for_recalc(state):
            raise ValueError("Нужны ВОР > 0 и хотя бы одна неделя с фактом > 0")
        st.session_state["ppt_react_result"] = recalc_payload(state)
    except Exception as exc:
        st.session_state["ppt_react_error"] = str(exc)
        st.session_state["ppt_react_result"] = None

    st.rerun()
