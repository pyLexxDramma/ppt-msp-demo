"""
Streamlit entrypoint.

Локально: React SPA в iframe (автосборка dist + uvicorn при необходимости).
Streamlit Cloud: нативная форма (без npm/uvicorn) — иначе Cloud падает с «Oh no».

Публичный React на Cloud: секрет/env PPT_MSP_UI_URL=https://ваш-spa-или-api
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _is_streamlit_cloud() -> bool:
    if os.environ.get("PPT_MSP_FORCE_FORM", "").lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("PPT_MSP_FORCE_IFRAME", "").lower() in {"1", "true", "yes"}:
        return False
    # Community Cloud mounts app under /mount/src
    if Path("/mount/src").exists():
        return True
    # Streamlit Cloud / Snowflake runtime hints
    for key in ("STREAMLIT_SHARE", "STREAMLIT_RUNTIME_ENVIRONMENT"):
        val = (os.environ.get(key) or "").lower()
        if val in {"1", "true", "cloud", "sharing"}:
            return True
    return False


def _public_ui_url() -> str | None:
    url = (os.environ.get("PPT_MSP_UI_URL") or "").strip().rstrip("/")
    if not url:
        try:
            url = str(st.secrets.get("PPT_MSP_UI_URL", "")).strip().rstrip("/")
        except Exception:
            url = ""
    if not url:
        return None
    if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        return None
    return url


st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon="Λ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

cloud = _is_streamlit_cloud()
public_ui = _public_ui_url()

# Cloud + публичный SPA URL → iframe без локального bootstrap
if public_ui:
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
    components.iframe(public_ui, height=900, scrolling=True)
    st.stop()

# Cloud без публичного URL → стабильная нативная форма (без npm/uvicorn)
if cloud:
    from demo.streamlit_form import render  # noqa: E402

    render(
        cloud_note=(
            "Streamlit Cloud: показана нативная форма (без iframe). "
            "Пиксель-в-пиксель React UI здесь недоступен — iframe на 127.0.0.1 "
            "из браузера не работает. Для React задайте секрет PPT_MSP_UI_URL "
            "на публичный SPA/API или открывайте демо локально."
        )
    )
    st.stop()

# Локально: bootstrap React + uvicorn, при сбое — форма
from demo.streamlit_boot import bootstrap, dist_ready  # noqa: E402
from demo.streamlit_form import render as render_form  # noqa: E402
import streamlit.components.v1 as components

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
  .block-container { max-width: 100% !important; }
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
components.iframe(st.session_state["ppt_msp_ui_url"], height=900, scrolling=True)
