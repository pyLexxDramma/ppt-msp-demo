"""Встроенный React SPA на Streamlit Cloud (без npm/uvicorn/публичного URL)."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from demo.form_input import FormState, form_ready_for_recalc
from demo.payloads import prefill_payload, recalc_payload

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"

_MAX_MPP_BYTES = 40 * 1024 * 1024


def dist_ready() -> bool:
    return (DIST / "index.html").is_file()


@st.cache_resource
def _component():
    return components.declare_component("ppt_msp_form", path=str(DIST))


@st.cache_data
def _prefill() -> dict:
    return prefill_payload()


def _handle_mpp_chunk(event: dict) -> None:
    batch = str(event.get("batch") or event.get("id") or "")
    try:
        index = int(event.get("index") or 0)
        total = int(event.get("total") or 0)
    except (TypeError, ValueError):
        st.session_state["ppt_react_error"] = "Повреждённый кусок .mpp"
        return
    raw = event.get("data")
    name = str(event.get("filename") or "source.mpp")
    if not batch or not isinstance(raw, str) or total < 1:
        st.session_state["ppt_react_error"] = "Некорректная загрузка .mpp"
        return
    try:
        part = base64.b64decode(raw)
    except Exception:
        st.session_state["ppt_react_error"] = "Не удалось прочитать кусок .mpp"
        return
    store = st.session_state.setdefault("ppt_mpp_chunk_store", {})
    if store.get("batch") != batch:
        store.clear()
        store["batch"] = batch
        store["parts"] = {}
        store["total"] = total
        store["filename"] = name
    store["parts"][index] = part
    if len(store["parts"]) < total:
        return
    data = b"".join(store["parts"][i] for i in range(total))
    st.session_state.pop("ppt_mpp_chunk_store", None)
    if len(data) > _MAX_MPP_BYTES:
        st.session_state["ppt_react_error"] = f"Файл больше {_MAX_MPP_BYTES // (1024 * 1024)} МБ"
        return
    st.session_state["ppt_source_mpp"] = data
    st.session_state["ppt_source_mpp_name"] = name
    from demo.windows_host import remote_upload_mpp

    info = remote_upload_mpp(data, filename=name)
    if info:
        st.session_state["ppt_mpp_upload_id"] = info.get("upload_id")
        st.session_state["ppt_mpp_options"] = info.get("options")
        st.session_state["ppt_mpp_warning"] = info.get("warning")
        st.session_state["ppt_react_error"] = None
    else:
        st.session_state["ppt_mpp_upload_id"] = None
        st.session_state["ppt_mpp_options"] = None
        st.session_state["ppt_mpp_warning"] = (
            "Файл принят в Cloud, но Windows API не ответил. Проверьте туннель."
        )


def _clear_mpp_upload() -> None:
    st.session_state.pop("ppt_source_mpp", None)
    st.session_state.pop("ppt_source_mpp_name", None)
    st.session_state["ppt_react_result"] = None


def render() -> None:
    # Не фиксируем iframe на 100vh и не гасим overflow — иначе на Cloud
    # контент React обрезается и страница не скроллится. Высоту задаёт
    # streamlitBridge.setFrameHeight → скролл у самой страницы Streamlit.
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
    border: 0 !important;
    width: 100% !important;
  }
</style>
""",
        unsafe_allow_html=True,
    )

    prefill = {**_prefill()}
    mpp_opts = st.session_state.get("ppt_mpp_options")
    if isinstance(mpp_opts, dict) and mpp_opts:
        prefill["options"] = mpp_opts
    prefill["mpp_upload"] = {
        "ready": "ppt_source_mpp" in st.session_state,
        "filename": st.session_state.get("ppt_source_mpp_name"),
        "upload_id": st.session_state.get("ppt_mpp_upload_id"),
        "options": mpp_opts,
        "warning": st.session_state.get("ppt_mpp_warning"),
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
        st.session_state.pop("ppt_mpp_upload_id", None)
        st.session_state.pop("ppt_mpp_options", None)
        st.session_state.pop("ppt_mpp_warning", None)
        st.session_state.pop("ppt_mpp_chunk_store", None)
        st.rerun()
        return

    if action == "mpp_chunk":
        _handle_mpp_chunk(event)
        st.rerun()
        return

    if action != "recalc":
        return

    try:
        # Файл из React (выбран в пункте 1, передан вместе с пересчётом)
        raw_b64 = event.get("mpp_b64")
        if isinstance(raw_b64, str) and raw_b64:
            data = base64.b64decode(raw_b64)
            if len(data) > _MAX_MPP_BYTES:
                raise ValueError(f"Файл больше {_MAX_MPP_BYTES // (1024 * 1024)} МБ")
            st.session_state["ppt_source_mpp"] = data
            st.session_state["ppt_source_mpp_name"] = str(
                event.get("mpp_filename") or "source.mpp"
            )

        state = FormState.from_dict(event.get("form") or {})
        if not form_ready_for_recalc(state):
            raise ValueError("Нужны ВОР > 0 и хотя бы одна неделя с фактом > 0")
        from demo.windows_host import (
            remote_recalc,
            resolve_windows_api_url,
            windows_api_healthy,
        )

        mpp_bytes = st.session_state.get("ppt_source_mpp")
        mpp_upload_id = event.get("mpp_upload_id") or st.session_state.get("ppt_mpp_upload_id")
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
