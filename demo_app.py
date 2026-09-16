"""
Streamlit entrypoint.

Локально (Windows): React в iframe, при необходимости сборка + uvicorn.
Streamlit Cloud / Linux: только нативная форма. Custom component и uvicorn
на Cloud роняют приложение («Error running app» / «Oh no»).
"""

from __future__ import annotations

import os
import sys
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
    for key in ("STREAMLIT_SHARE", "STREAMLIT_RUNTIME_ENVIRONMENT"):
        val = (os.environ.get(key) or "").lower()
        if val in {"1", "true", "cloud", "sharing"}:
            return False
    return sys.platform == "win32"


def _iframe_url() -> str | None:
    url = (os.environ.get("PPT_MSP_IFRAME_URL") or os.environ.get("PPT_MSP_UI_URL") or "").strip().rstrip("/")
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return url if _is_local_machine() else None
    return url or None


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
    page_icon="Λ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

local = _is_local_machine()
public_ui = _iframe_url()

if public_ui and not (public_ui.startswith("http://127.0.0.1") or public_ui.startswith("http://localhost")):
    _show_iframe(public_ui)
    st.stop()

if not local:
    from demo.streamlit_form import render as render_form  # noqa: E402

    render_form()
    st.stop()

if public_ui:
    _show_iframe(public_ui)
    st.stop()

from demo.streamlit_boot import bootstrap, dist_ready  # noqa: E402
from demo.streamlit_form import render as render_form  # noqa: E402

if "ppt_msp_ui_url" not in st.session_state and "ppt_msp_use_form" not in st.session_state:
    log: list[str] = []
    try:
        with st.spinner(
            "Подготовка UI…"
            if dist_ready()
            else "Сборка React и запуск API (первый старт может занять минуту)…"
        ):
            st.session_state["ppt_msp_ui_url"] = bootstrap(log)
            st.session_state["ppt_msp_boot_log"] = log
    except Exception as exc:
        st.session_state["ppt_msp_use_form"] = True
        st.session_state["ppt_msp_boot_error"] = str(exc)
        st.session_state["ppt_msp_boot_log"] = log

if st.session_state.get("ppt_msp_use_form"):
    render_form(
        cloud_note=(
            "React iframe недоступен, показана Streamlit-форма. "
            f"{st.session_state.get('ppt_msp_boot_error') or ''}"
        )
    )
    st.stop()

_show_iframe(st.session_state["ppt_msp_ui_url"])
