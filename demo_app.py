"""Streamlit entrypoint. Cloud: native form only. Local Windows: React iframe."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def _is_local_machine() -> bool:
    if _flag("PPT_MSP_FORCE_IFRAME"):
        return True
    if _flag("PPT_MSP_FORCE_CLOUD") or _flag("PPT_MSP_FORCE_FORM"):
        return False
    if Path("/mount/src").exists() or Path("/home/appuser").exists():
        return False
    return sys.platform == "win32"


def _show_error(exc: BaseException) -> None:
    st.error("Ошибка запуска формы")
    st.code("".join(traceback.format_exception(exc)))


st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon=":construction:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if not _is_local_machine():
    try:
        from demo.streamlit_form import render as render_form

        render_form()
    except Exception as exc:
        _show_error(exc)
    st.stop()

try:
    from demo.streamlit_boot import bootstrap, dist_ready
    from demo.streamlit_form import render as render_form
    import streamlit.components.v1 as components

    if "ppt_msp_ui_url" not in st.session_state and "ppt_msp_use_form" not in st.session_state:
        log: list[str] = []
        try:
            with st.spinner("Подготовка UI…" if dist_ready() else "Сборка React и запуск API…"):
                st.session_state["ppt_msp_ui_url"] = bootstrap(log)
        except Exception as exc:
            st.session_state["ppt_msp_use_form"] = True
            st.session_state["ppt_msp_boot_error"] = str(exc)

    if st.session_state.get("ppt_msp_use_form"):
        render_form(cloud_note=st.session_state.get("ppt_msp_boot_error") or "")
        st.stop()

    components.iframe(st.session_state["ppt_msp_ui_url"], height=900, scrolling=True)
except Exception as exc:
    _show_error(exc)
