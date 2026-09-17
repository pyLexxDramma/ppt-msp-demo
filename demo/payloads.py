"""Общие JSON-ответы для FastAPI и встроенного React на Streamlit Cloud."""

from __future__ import annotations

import uuid
from typing import Any

from demo.catalog import empty_form_options
from demo.form_input import (
    MONTHS_RU,
    FormState,
    compute_aggregates,
    form_ready_for_recalc,
)
from demo.form_pipeline import run_form_pipeline
from demo.mpp_writer import project_available
from demo.schedule_tables import SCHEDULE_COLS


def agg_dict(state: FormState) -> dict[str, Any]:
    agg = compute_aggregates(state)
    return {
        "plan_total": agg.plan_total,
        "fact_total": agg.fact_total,
        "month_cum": agg.month_cum,
        "done": agg.done,
        "remaining": agg.remaining,
        "pct_done": agg.pct_done,
        "vor": agg.vor,
        "rows": [{"dev": r.dev, "cum": r.cum} for r in agg.rows],
    }


def prefill_payload() -> dict[str, Any]:
    """Пустая форма. Справочник задач появится после загрузки .mpp."""
    from demo.form_input import empty_form

    state = empty_form()
    return {
        "form": state.to_dict(),
        "aggregates": agg_dict(state),
        "ready": False,
        "com_available": project_available(),
        "months": MONTHS_RU,
        "options": empty_form_options(),
        "require_mpp_upload": True,
    }


def build_recalc(
    state: FormState,
    *,
    write_mpp: bool | None = None,
    mpp_bytes: bytes | None = None,
    etalon_rows: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, bytes | None]]:
    if write_mpp is None:
        write_mpp = project_available()
    pipe = run_form_pipeline(
        state,
        write_mpp=write_mpp,
        mpp_bytes=mpp_bytes,
        etalon_rows=etalon_rows,
        write_csv_xml=False,
    )
    job_id = str(uuid.uuid4())
    m1 = pipe.schedule.get("mode1") or {}
    mpp_error = pipe.mpp_error
    if pipe.mpp_bytes is None and not pipe.com_available:
        mpp_error = mpp_error or (
            "Расчёт готов. Файл .mpp недоступен на этой машине расчёта "
            "(нужны MS Project и pywin32)."
        )
    payload = {
        "job_id": job_id,
        "status": pipe.status,
        "aggregates": agg_dict(state),
        "schedule": pipe.schedule,
        "mode1": m1,
        "today": pipe.today.isoformat(),
        "com_available": pipe.com_available,
        "mpp_error": mpp_error,
        "downloads": {"mpp": pipe.mpp_bytes is not None},
        "mpp_b64": None,
        "update": {
            "task_id": pipe.update.task_id,
            "name": pipe.update.name,
            "before": pipe.update.before,
            "after": pipe.update.after,
        },
        "schedule_before": pipe.schedule_before or [],
        "schedule_after": pipe.schedule_after or [],
        "schedule_cols": list(SCHEDULE_COLS),
        "source_mpp": "upload" if mpp_bytes else "sample",
    }
    files = {"csv": pipe.csv_bytes, "xml": pipe.xml_bytes, "mpp": pipe.mpp_bytes}
    return payload, files


def recalc_payload(
    state: FormState,
    *,
    write_mpp: bool | None = None,
    mpp_bytes: bytes | None = None,
    etalon_rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    payload, _ = build_recalc(
        state,
        write_mpp=write_mpp,
        mpp_bytes=mpp_bytes,
        etalon_rows=etalon_rows,
    )
    return payload
