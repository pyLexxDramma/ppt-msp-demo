"""FastAPI для SPA: префилл, пересчёт Mode1, скачивание .mpp."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.form_input import MONTHS_RU, FormState, form_ready_for_recalc  # noqa: E402
from demo.catalog import (  # noqa: E402
    catalog_has_tasks,
    empty_form_options,
    load_form_options,
    options_from_mpp_rows,
)
from demo.mpp_writer import dump_mpp_rows, project_available  # noqa: E402
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
    allow_origin_regex=r"https://.*\.(streamlit\.app|vercel\.app)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# job_id -> {csv, xml, mpp, created}
_JOBS: dict[str, dict[str, Any]] = {}
# upload_id -> raw .mpp bytes (временное хранилище для демо)
_UPLOADS: dict[str, bytes] = {}
# upload_id -> {rows, options, filename}
_UPLOAD_META: dict[str, dict[str, Any]] = {}
_MAX_MPP_BYTES = 40 * 1024 * 1024


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
    month_plan: float | None = None
    month_fact: float | None = None
    weeks: list[WeekIn] = Field(default_factory=list)
    mpp_upload_id: str | None = None


def _to_state(body: FormIn) -> FormState:
    data = body.model_dump()
    data.pop("mpp_upload_id", None)
    return FormState.from_dict(data)


def _resolve_mpp_bytes(upload_id: str | None) -> bytes | None:
    if not upload_id:
        return None
    data = _UPLOADS.get(upload_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Исходный .mpp не найден — загрузите файл снова",
        )
    return data


def _prune_uploads(keep: int = 10) -> None:
    if len(_UPLOADS) <= keep:
        return
    for key in list(_UPLOADS.keys())[:-keep]:
        _UPLOADS.pop(key, None)
        _UPLOAD_META.pop(key, None)


def _inspect_via_windows_api(data: bytes, filename: str) -> dict[str, Any] | None:
    """На Mac/CI без COM — взять справочник с Windows-хоста (тот же /api/mpp/upload)."""
    from demo.windows_host import remote_upload_mpp

    remote = remote_upload_mpp(data, filename=filename)
    if not remote:
        return None
    options = remote.get("options") if isinstance(remote.get("options"), dict) else None
    if not catalog_has_tasks(options):
        return {
            "options": empty_form_options(),
            "com_available": False,
            "warning": remote.get("warning")
            or "Windows API не вернул leaf-задачи с ВОР (Text13) из .mpp.",
        }
    return {
        "options": options,
        "rows": remote.get("rows") or [],
        "com_available": False,
        "remote_upload_id": remote.get("upload_id"),
        "warning": remote.get("warning"),
    }


def _inspect_uploaded_mpp(data: bytes, filename: str) -> dict[str, Any]:
    """Прочитать справочник из .mpp: COM локально, иначе Windows API."""
    if not project_available():
        proxied = _inspect_via_windows_api(data, filename)
        if proxied:
            return proxied
        return {
            "options": empty_form_options(),
            "com_available": False,
            "warning": "Чтение задач из .mpp нужно на хосте с MS Project (Windows API).",
        }
    try:
        project_name, rows = dump_mpp_rows(data)
        options = options_from_mpp_rows(rows, project_name=project_name or Path(filename).stem)
        return {
            "options": options,
            "rows": rows,
            "com_available": True,
            "warning": None if catalog_has_tasks(options) else "В .mpp не найдены leaf-задачи с ВОР (Text13).",
        }
    except Exception as e:
        proxied = _inspect_via_windows_api(data, filename)
        if proxied and catalog_has_tasks(proxied.get("options")):
            proxied["warning"] = proxied.get("warning") or f"Локальный COM не прочитал файл, взяли Windows API. {e}"
            return proxied
        return {
            "options": empty_form_options(),
            "com_available": True,
            "warning": f"Не удалось прочитать .mpp: {e}",
        }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "com_available": project_available(),
        "months": MONTHS_RU,
    }


@app.get("/api/options")
def options() -> dict[str, Any]:
    """Справочники до загрузки .mpp — пустые; после upload смотрите ответ upload."""
    return load_form_options()


@app.get("/api/prefill")
def prefill() -> dict[str, Any]:
    return prefill_payload()


@app.post("/api/mpp/upload")
async def upload_mpp(file: UploadFile = File(...)) -> dict[str, Any]:
    """Загрузка исходного .mpp + справочник задач из файла (COM на Windows)."""
    name = (file.filename or "").strip()
    if not name.lower().endswith(".mpp"):
        raise HTTPException(status_code=400, detail="Нужен файл с расширением .mpp")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > _MAX_MPP_BYTES:
        raise HTTPException(status_code=400, detail="Файл .mpp слишком большой (лимит 40 МБ)")
    upload_id = str(uuid.uuid4())
    _UPLOADS[upload_id] = data
    inspected = _inspect_uploaded_mpp(data, name)
    _UPLOAD_META[upload_id] = {
        "filename": name,
        "options": inspected["options"],
        "rows": inspected.get("rows") or [],
    }
    _prune_uploads()
    return {
        "upload_id": upload_id,
        "filename": name,
        "size": len(data),
        "options": inspected["options"],
        "com_available": inspected["com_available"],
        "warning": inspected.get("warning"),
        "source": "mpp",
    }


@app.get("/api/mpp/{upload_id}/options")
def mpp_options(upload_id: str) -> dict[str, Any]:
    meta = _UPLOAD_META.get(upload_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Загрузка не найдена — загрузите .mpp снова")
    return {
        "upload_id": upload_id,
        "filename": meta.get("filename"),
        "options": meta.get("options") or empty_form_options(),
        "source": "mpp",
    }


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
    mpp_bytes = _resolve_mpp_bytes(body.mpp_upload_id)
    etalon_rows = None
    if body.mpp_upload_id and body.mpp_upload_id in _UPLOAD_META:
        etalon_rows = _UPLOAD_META[body.mpp_upload_id].get("rows") or None
    payload, files = build_recalc(state, mpp_bytes=mpp_bytes, etalon_rows=etalon_rows)
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
