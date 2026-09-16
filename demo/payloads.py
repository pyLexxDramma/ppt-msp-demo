"""Общие JSON-ответы для FastAPI и встроенного React на Streamlit Cloud."""

from __future__ import annotations

import base64
import uuid
from typing import Any

from demo.catalog import load_form_options
from demo.form_input import (
    MONTHS_RU,
    FormState,
    compute_aggregates,
    form_ready_for_recalc,
)
from demo.form_pipeline import run_form_pipeline, silent_prefill_from_csv
from demo.mpp_writer import project_available


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
    state = silent_prefill_from_csv(FormState())
    return {
        "form": state.to_dict(),
        "aggregates": agg_dict(state),
        "ready": form_ready_for_recalc(state),
        "com_available": project_available(),
        "months": MONTHS_RU,
        "options": load_form_options(),
    }


def build_recalc(
    state: FormState, *, write_mpp: bool | None = None
) -> tuple[dict[str, Any], dict[str, bytes | None]]:
    if write_mpp is None:
        write_mpp = project_available()
    pipe = run_form_pipeline(state, write_mpp=write_mpp)
    job_id = str(uuid.uuid4())
    m1 = pipe.schedule.get("mode1") or {}
    mpp_error = (
        "Расчёт готов. Файл .mpp недоступен на этой машине расчёта "
        "(нужны MS Project и pywin32)."
        if pipe.mpp_error and not pipe.mpp_bytes
        else pipe.mpp_error
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
        "mpp_b64": (
            base64.b64encode(pipe.mpp_bytes).decode("ascii") if pipe.mpp_bytes else None
        ),
        "update": {
            "task_id": pipe.update.task_id,
            "name": pipe.update.name,
            "before": pipe.update.before,
            "after": pipe.update.after,
        },
    }
    files = {"csv": pipe.csv_bytes, "xml": pipe.xml_bytes, "mpp": pipe.mpp_bytes}
    return payload, files


def recalc_payload(state: FormState, *, write_mpp: bool | None = None) -> dict[str, Any]:
    payload, _ = build_recalc(state, write_mpp=write_mpp)
    return payload
