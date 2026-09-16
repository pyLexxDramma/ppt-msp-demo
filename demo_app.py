"""
Streamlit-оболочка: тот же React UI, что и SPA (1:1).

При старте сам собирает frontend/dist (если нет) и поднимает uvicorn,
если API на PPT_MSP_UI_URL / http://127.0.0.1:8000 ещё не отвечает.

  streamlit run demo_app.py --server.port 8503

На Streamlit Cloud iframe на 127.0.0.1 из браузера не работает —
нужен публичный PPT_MSP_UI_URL (например Vercel + API).
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.streamlit_boot import bootstrap, dist_ready  # noqa: E402

st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon="Λ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
  html, body, [data-testid="stAppViewContainer"],
  [data-testid="stAppViewContainer"] > .main,
  [data-testid="stMain"],
  .main .block-container,
  [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"] {
    height: 100% !important;
    max-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
  }
  .block-container {
    max-width: 100% !important;
  }
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  iframe {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    border: 0 !important;
    z-index: 1000;
  }
</style>
""",
    unsafe_allow_html=True,
)

if "ppt_msp_ui_url" not in st.session_state:
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
        st.error(str(exc))
        if log:
            with st.expander("Лог подготовки"):
                st.code("\n".join(log))
        st.stop()

components.iframe(st.session_state["ppt_msp_ui_url"], height=900, scrolling=True)
