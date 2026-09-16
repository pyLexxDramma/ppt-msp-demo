"""
Streamlit-оболочка: показывает тот же React UI, что и SPA.

Нужен запущенный FastAPI со собранным frontend/dist:

  cd frontend && npm run build
  uvicorn api.main:app --reload --port 8000
  streamlit run demo_app.py --server.port 8503

URL UI задаётся PPT_MSP_UI_URL (по умолчанию http://127.0.0.1:8000).
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

st.markdown(
    """
<style>
  #MainMenu {visibility: hidden;}
  header {visibility: hidden;}
  footer {visibility: hidden;}
  [data-testid="stSidebar"] {display: none;}
  .block-container {
    padding: 0 !important;
    max-width: 100% !important;
  }
  div[data-testid="stAppViewContainer"] > .main {
    padding: 0;
  }
  .stApp { background: #eef2f5; }
</style>
""",
    unsafe_allow_html=True,
)

dist_ok = DIST.exists() and (DIST / "index.html").exists()

if not dist_ok:
    st.error(
        "Не найден собранный UI (`frontend/dist`). "
        "Соберите SPA: `cd frontend && npm run build`, затем запустите API: "
        "`uvicorn api.main:app --port 8000`."
    )
    st.code(
        "cd frontend && npm run build\n"
        "uvicorn api.main:app --reload --port 8000\n"
        "streamlit run demo_app.py --server.port 8503",
        language="bash",
    )
    st.stop()

st.caption(f"UI: {ui_url} · тот же React SPA, что и локально на Vite")
components.iframe(ui_url, height=1400, scrolling=True)
