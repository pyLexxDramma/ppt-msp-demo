"""Публичный Windows-хост с MS Project: URL и вызов /api/recalc."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
LOCAL_URL_FILE = ROOT / "sample_data" / "windows_api_url.txt"
GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/pyLexxDramma/ppt-msp-demo/"
    "main/sample_data/windows_api_url.txt"
)


def _clean(url: str | None) -> str | None:
    text = (url or "").strip().rstrip("/")
    if not text.startswith("https://"):
        return None
    if "example.invalid" in text:
        return None
    return text


def _from_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        return _clean(line)
    return None


def resolve_windows_api_url() -> str | None:
    env = _clean(os.environ.get("PPT_MSP_MPP_API"))
    if env:
        return env
    try:
        import streamlit as st

        env = _clean(str(st.secrets.get("PPT_MSP_MPP_API", "") or ""))
        if env:
            return env
    except Exception:
        pass
    local = _from_file(LOCAL_URL_FILE)
    if local:
        return local
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(GITHUB_RAW_URL)
            if resp.status_code < 400:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    found = _clean(line)
                    if found:
                        return found
    except Exception:
        pass
    return None


def windows_api_healthy(base: str | None = None, timeout: float = 4.0) -> bool:
    url = base or resolve_windows_api_url()
    if not url:
        return False
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{url}/api/health")
            data = resp.json() if resp.status_code < 400 else {}
            return bool(data.get("ok"))
    except Exception:
        return False


def remote_recalc(state_dict: dict[str, Any], timeout: float = 180.0) -> dict[str, Any] | None:
    base = resolve_windows_api_url()
    if not base:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{base}/api/recalc", json=state_dict)
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("job_id")
            if data.get("downloads", {}).get("mpp") and job_id:
                file_resp = client.get(f"{base}/api/jobs/{job_id}/mpp")
                file_resp.raise_for_status()
                data["mpp_b64"] = base64.b64encode(file_resp.content).decode("ascii")
            return data
    except Exception:
        return None


def pipe_from_remote(data: dict[str, Any]) -> SimpleNamespace:
    agg = data.get("aggregates") or {}
    upd = data.get("update") or {}
    mpp = None
    raw = data.get("mpp_b64")
    if raw:
        mpp = base64.b64decode(raw)
    return SimpleNamespace(
        schedule=data.get("schedule") or {},
        status=data.get("status") or "progress",
        aggregates=SimpleNamespace(
            done=agg.get("done"),
            vor=agg.get("vor"),
            remaining=agg.get("remaining"),
            plan_total=agg.get("plan_total"),
            fact_total=agg.get("fact_total"),
            month_cum=agg.get("month_cum"),
            pct_done=agg.get("pct_done"),
        ),
        update=SimpleNamespace(
            task_id=upd.get("task_id"),
            name=upd.get("name"),
            before=upd.get("before") or {},
            after=upd.get("after") or {},
        ),
        today=data.get("today"),
        mpp_bytes=mpp,
        mpp_error=data.get("mpp_error"),
        com_available=data.get("com_available"),
    )
