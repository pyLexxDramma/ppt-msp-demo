"""
Streamlit-оболочка: только React UI.

1) Встроенный React-компонент из frontend/dist (без отдельной Streamlit-формы).
2) Если dist нет — локальный bootstrap: сборка + uvicorn + iframe на :8000.

  streamlit run demo_app.py --server.port 8503
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _show_error(exc: BaseException) -> None:
    st.error("Ошибка запуска React UI")
    st.code("".join(traceback.format_exception(exc)))


def _iframe_css() -> None:
    # Fallback-iframe на локальный SPA: один слой скролла внутри iframe.
    st.markdown(
        """
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
  .block-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
  }
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  iframe {
    display: block !important;
    width: 100% !important;
    height: 100vh !important;
    border: 0 !important;
  }
</style>
""",
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Данные по объему стройплощадок",
    page_icon="Λ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Предпочтительный путь: React как Streamlit-компонент (тот же SPA).
try:
    from demo.streamlit_react import dist_ready as react_dist_ready  # noqa: E402
    from demo.streamlit_react import render as render_react  # noqa: E402

    if react_dist_ready():
        render_react()
        st.stop()
except Exception as exc:
    # Не останавливаемся — пробуем локальный iframe-контур.
    st.session_state["ppt_msp_react_component_error"] = str(exc)

# Fallback: локальная сборка + uvicorn + iframe
from demo.streamlit_boot import bootstrap, dist_ready  # noqa: E402

_iframe_css()

if "ppt_msp_ui_url" not in st.session_state:
    log: list[str] = []
    try:
        with st.spinner(
            "Подготовка React UI…"
            if dist_ready()
            else "Сборка React и запуск API (первый старт может занять минуту)…"
        ):
            st.session_state["ppt_msp_ui_url"] = bootstrap(log)
            st.session_state["ppt_msp_boot_log"] = log
    except Exception as exc:
        _show_error(exc)
        if log:
            with st.expander("Лог подготовки"):
                st.code("\n".join(log))
        st.info(
            "Нужны Node.js/npm и `pip install -r requirements-demo.txt`. "
            "Либо положите готовый `frontend/dist` и перезапустите.\n\n"
            "`streamlit run demo_app.py --server.port 8503`"
        )
        st.stop()

components.iframe(st.session_state["ppt_msp_ui_url"], height=900, scrolling=True)
