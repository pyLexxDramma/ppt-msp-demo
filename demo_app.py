"""Streamlit entrypoint.

Cloud: React с Vercel в iframe (PPT_MSP_UI_URL).
Локально Windows: React + API на этой машине (для .mpp через COM).
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PUBLIC_UI = "https://bi-analytics-msp.vercel.app"


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


def _public_ui_url() -> str | None:
    url = (os.environ.get("PPT_MSP_UI_URL") or "").strip().rstrip("/")
    if not url:
        try:
            url = str(st.secrets.get("PPT_MSP_UI_URL", "")).strip().rstrip("/")
        except Exception:
            url = ""
    if not url:
        url = DEFAULT_PUBLIC_UI
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return None
    return url


def _show_error(exc: BaseException) -> None:
    st.error("Ошибка запуска формы")
    st.code("".join(traceback.format_exception(exc)))


def _show_iframe(url: str) -> None:
    import streamlit.components.v1 as components

    st.markdown(
        """
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
  html, body, [data-testid="stAppViewContainer"],
  [data-testid="stAppViewContainer"] > .main, [data-testid="stMain"],
  .main .block-container, [data-testid="stVerticalBlock"] {
    height: 100% !important; max-height: 100vh !important;
    margin: 0 !important; padding: 0 !important; overflow: hidden !important;
  }
  .block-container { max-width: 100% !important; }
  iframe {
    position: fixed !important; inset: 0 !important;
    width: 100vw !important; height: 100vh !important;
    border: 0 !important; z-index: 1000;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    components.iframe(url, height=900, scrolling=True)


st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon=":construction:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Локальное демо .mpp на Windows (скрипт с рабочего стола)
if _flag("PPT_MSP_LOCAL_MPP"):
    from demo.streamlit_form import render as render_form

    render_form()
    st.stop()

public_ui = _public_ui_url()

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
        try:
            with st.spinner("Подготовка UI…" if dist_ready() else "Сборка React и запуск API…"):
                st.session_state["ppt_msp_ui_url"] = bootstrap([])
        except Exception as exc:
            st.session_state["ppt_msp_use_form"] = True
            st.session_state["ppt_msp_boot_error"] = str(exc)

    if st.session_state.get("ppt_msp_use_form"):
        render_form(cloud_note=st.session_state.get("ppt_msp_boot_error") or "")
        st.stop()

    components.iframe(st.session_state["ppt_msp_ui_url"], height=900, scrolling=True)
except Exception as exc:
    _show_error(exc)
