"""
Streamlit-оболочка: тот же React UI, что и SPA (1:1).

Нужен запущенный FastAPI со собранным frontend/dist:

  cd frontend && npm run build
  uvicorn api.main:app --reload --port 8000
  streamlit run demo_app.py --server.port 8503

URL UI: PPT_MSP_UI_URL (по умолчанию http://127.0.0.1:8000).
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "frontend" / "dist"
DEFAULT_UI = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon="Λ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ui_url = (os.environ.get("PPT_MSP_UI_URL") or DEFAULT_UI).rstrip("/")

# Один скролл: гасим прокрутку Streamlit, iframe на весь экран.
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
  /* сам iframe со SPA — единственный слой прокрутки */
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

if not DIST.is_dir() or not any(DIST.iterdir()):
    st.error(
        "Нет сборки React (`frontend/dist`). Выполните:\n\n"
        "`cd frontend && npm install && npm run build`\n\n"
        "Затем запустите API:\n\n"
        "`uvicorn api.main:app --reload --port 8000`"
    )
    st.stop()

components.iframe(ui_url, height=900, scrolling=True)
