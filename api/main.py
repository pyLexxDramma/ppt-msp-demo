"""FastAPI для SPA: префилл, пересчёт Mode1, скачивание .mpp."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.form_input import MONTHS_RU, FormState, form_ready_for_recalc  # noqa: E402
from demo.catalog import load_form_options  # noqa: E402
from demo.mpp_writer import project_available  # noqa: E402
from demo.payloads import agg_dict, build_recalc, prefill_payload  # noqa: E402

app = FastAPI(title="PPT-MSP Construction Volumes API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8503",
        "http://127.0.0.1:8503",
        "https://bi-analytics-msp.vercel.app",
        "https://ppt-msp-demo-2j2hmuumc5qfyah695rqqd.streamlit.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# job_id -> {csv, xml, mpp, created}
_JOBS: dict[str, dict[str, Any]] = {}


class WeekIn(BaseModel):
    plan: float | None = 0
    fact: float | None = None


class FormIn(BaseModel):
    project: str = ""
    project_id: str = ""
    period_month: int = Field(ge=0, le=11, default=6)
    period_year: int = 2026
    mode: str = "last"
    task_name: str = ""
    task_id: str = "6"
    vor: float = 0
    unit: str = ""
    prev_cumulative: float = 0
    weeks: list[WeekIn] = Field(default_factory=list)


def _to_state(body: FormIn) -> FormState:
    return FormState.from_dict(body.model_dump())


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "com_available": project_available(),
        "months": MONTHS_RU,
    }


@app.get("/api/options")
def options() -> dict[str, Any]:
    """Справочники для селектов (из sample CSV / будущего контура БД)."""
    return load_form_options()


@app.get("/api/prefill")
def prefill() -> dict[str, Any]:
    return prefill_payload()


@app.post("/api/aggregates")
def aggregates(body: FormIn) -> dict[str, Any]:
    state = _to_state(body)
    return {
        "aggregates": agg_dict(state),
        "ready": form_ready_for_recalc(state),
    }


@app.post("/api/recalc")
def recalc(body: FormIn) -> dict[str, Any]:
    state = _to_state(body)
    if not form_ready_for_recalc(state):
        raise HTTPException(
            status_code=400,
            detail="Нужны ВОР > 0 и хотя бы одна неделя с фактом > 0",
        )
    payload, files = build_recalc(state)
    _JOBS[payload["job_id"]] = {
        **files,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    if len(_JOBS) > 20:
        for k in list(_JOBS.keys())[:-20]:
            _JOBS.pop(k, None)
    return payload


def _job_file(job_id: str, kind: str) -> bytes:
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Сессия пересчёта не найдена — выполните пересчёт снова")
    data = job.get(kind)
    if not data:
        raise HTTPException(status_code=404, detail=f"Файл {kind} недоступен")
    return data


@app.get("/api/jobs/{job_id}/mpp")
def download_mpp(job_id: str) -> Response:
    data = _job_file(job_id, "mpp")
    return Response(
        content=data,
        media_type="application/vnd.ms-project",
        headers={"Content-Disposition": 'attachment; filename="msp_updated.mpp"'},
    )


@app.get("/api/jobs/{job_id}/csv")
def download_csv(job_id: str) -> Response:
    data = _job_file(job_id, "csv")
    return Response(
        content=data,
        media_type="text/csv; charset=windows-1251",
        headers={"Content-Disposition": 'attachment; filename="msp_updated.csv"'},
    )


@app.get("/api/jobs/{job_id}/xml")
def download_xml(job_id: str) -> Response:
    data = _job_file(job_id, "xml")
    return Response(
        content=data,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="msp_updated.xml"'},
    )


# SPA: после всех /api — отдача frontend/dist (npm run build)
_DIST = ROOT / "frontend" / "dist"
if _DIST.exists() and (_DIST / "index.html").exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "ppt-msp-demo API",
            "docs": "/docs",
            "hint": "Соберите UI: cd frontend && npm run build — тогда / отдаст SPA",
        }