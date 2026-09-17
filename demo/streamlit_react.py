"""Встроенный React SPA на Streamlit Cloud (без npm/uvicorn/публичного URL)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from demo.form_input import FormState, form_ready_for_recalc
from demo.payloads import prefill_payload, recalc_payload

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"

_MAX_MPP_BYTES = 40 * 1024 * 1024
_UPLOADER_KEY = "ppt_mpp_host_upload"


def dist_ready() -> bool:
    return (DIST / "index.html").is_file()


@st.cache_resource
def _component():
    return components.declare_component("ppt_msp_form", path=str(DIST))


@st.cache_data
def _prefill() -> dict:
    return prefill_payload()


def _clear_mpp_upload() -> None:
    st.session_state.pop("ppt_source_mpp", None)
    st.session_state.pop("ppt_source_mpp_name", None)
    st.session_state.pop("ppt_mpp_from_uploader", None)
    st.session_state["ppt_react_result"] = None


def _render_host_mpp_uploader() -> None:
    """Нативный uploader Streamlit — единственный надёжный путь для крупных .mpp на Cloud."""
    st.markdown(
        """
<div class="ppt-mpp-host">
  <div class="ppt-mpp-host-title">1. Исходный .mpp</div>
  <div class="ppt-mpp-host-cap">Загрузите эталонный график MS Project — затем заполните объёмы и пересчитайте.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "Исходный .mpp",
        type=["mpp"],
        key=_UPLOADER_KEY,
        label_visibility="collapsed",
        help="До 40 МБ. Без файла форма ниже заблокирована.",
    )
    if uploaded is not None:
        data = uploaded.getvalue()
        if len(data) > _MAX_MPP_BYTES:
            st.error(f"Файл больше {_MAX_MPP_BYTES // (1024 * 1024)} МБ")
            _clear_mpp_upload()
        else:
            st.session_state["ppt_source_mpp"] = data
            st.session_state["ppt_source_mpp_name"] = uploaded.name
            st.session_state["ppt_mpp_from_uploader"] = True
            st.caption(f"Загружен: **{uploaded.name}** ({len(data) // 1024} КБ)")
    elif st.session_state.get("ppt_mpp_from_uploader"):
        # Пользователь нажал «×» у uploader
        _clear_mpp_upload()


def render() -> None:
    # Не фиксируем iframe на 100vh и не гасим overflow — иначе на Cloud
    # контент React обрезается и страница не скроллится. Высоту задаёт
    # streamlitBridge.setFrameHeight → скролл у самой страницы Streamlit.
    st.markdown(
        """
<style>
  #MainMenu, footer, header[data-testid="stHeader"] { display: none; }
  .block-container {
    max-width: 1080px !important;
    padding: 0.75rem 1rem 1rem !important;
    margin: 0 auto !important;
  }
  [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
  iframe {
    border: 0 !important;
    width: 100% !important;
  }
  .ppt-mpp-host-title {
    font-weight: 700;
    font-size: 0.95rem;
    color: #0a1a2f;
    margin: 0 0 0.25rem 0;
  }
  .ppt-mpp-host-cap {
    font-size: 0.8rem;
    color: #5b6473;
    margin: 0 0 0.5rem 0;
  }
  [data-testid="stFileUploader"] {
    background: #f9fbfd;
    border: 1px solid #e4e7eb;
    border-radius: 14px;
    padding: 0.75rem 1rem;
  }
</style>
""",
        unsafe_allow_html=True,
    )

    _render_host_mpp_uploader()

    prefill = {
        **_prefill(),
        "mpp_upload": {
            "ready": "ppt_source_mpp" in st.session_state,
            "filename": st.session_state.get("ppt_source_mpp_name"),
            # React не шлёт файл через postMessage — только статус
            "host_managed": True,
        },
    }
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

    action = event.get("action")
    req_id = event.get("id")
    if not req_id or req_id == st.session_state.get("ppt_react_done_id"):
        return

    st.session_state["ppt_react_done_id"] = req_id
    st.session_state["ppt_react_request_id"] = req_id
    st.session_state["ppt_react_error"] = None

    if action == "mpp_clear":
        _clear_mpp_upload()
        st.session_state.pop(_UPLOADER_KEY, None)
        st.rerun()
        return

    # Старые chunked/base64 upload с iframe больше не используем
    if action in {"mpp_upload", "mpp_upload_start", "mpp_upload_chunk", "mpp_upload_finish"}:
        st.session_state["ppt_react_error"] = (
            "Загрузите .mpp в блоке «1. Исходный .mpp» над формой "
            "(нативный uploader Streamlit)."
        )
        st.rerun()
        return

    if action != "recalc":
        return

    try:
        state = FormState.from_dict(event.get("form") or {})
        if not form_ready_for_recalc(state):
            raise ValueError("Нужны ВОР > 0 и хотя бы одна неделя с фактом > 0")
        from demo.windows_host import (
            remote_recalc,
            resolve_windows_api_url,
            windows_api_healthy,
        )

        mpp_bytes = st.session_state.get("ppt_source_mpp")
        mpp_upload_id = event.get("mpp_upload_id")
        payload = None
        base = resolve_windows_api_url()
        if base and windows_api_healthy(base):
            try:
                payload = remote_recalc(
                    state.to_dict(),
                    mpp_bytes=mpp_bytes if isinstance(mpp_bytes, (bytes, bytearray)) else None,
                    mpp_upload_id=mpp_upload_id if isinstance(mpp_upload_id, str) else None,
                )
            except Exception:
                payload = None

        if not payload:
            payload = recalc_payload(
                state,
                mpp_bytes=mpp_bytes if isinstance(mpp_bytes, (bytes, bytearray)) else None,
            )

        if not payload.get("downloads", {}).get("mpp"):
            payload["mpp_error"] = payload.get("mpp_error") or (
                "Расчёт готов. Файл .mpp недоступен на этой машине расчёта "
                "(нужны MS Project и pywin32)."
            )

        st.session_state["ppt_react_result"] = payload
        st.session_state["ppt_react_error"] = None
    except Exception as exc:
        st.session_state["ppt_react_error"] = str(exc)
        st.session_state["ppt_react_result"] = None

    st.rerun()
