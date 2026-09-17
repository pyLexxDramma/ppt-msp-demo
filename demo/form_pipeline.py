"""Пайплайн: форма → TaskUpdate → .mpp (COM). CSV не источник эталона."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .build_update import TaskUpdate, apply_updates_to_csv
from .form_input import FormAggregates, FormState, run_mode1_for_form, status_for_aggregates
from .mpp_writer import apply_updates_to_mpp, dump_mpp_rows, project_available
from .schedule_tables import build_schedule_after, build_schedule_before
from .xml_export import rows_to_mspdi_xml

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_data"
SAMPLE_MPP = SAMPLE_DIR / "msp_0feb8a44-a0f4-11ef-af7f-0050560219d5.mpp"
DEFAULT_TASK_ID = "6"


def _fmt_date(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d.%m.%y")


def _num_str(v: float | int | None) -> str:
    if v is None:
        return ""
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)


def _pct_int(v: float | int | None) -> str:
    if v is None:
        return ""
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return ""


def find_row_by_id(rows: list[dict[str, str]], task_id: str) -> dict[str, str] | None:
    tid = str(task_id).strip()
    for row in rows:
        if str(row.get("Ид") or "").strip() == tid:
            return row
    return None


# совместимость со старыми импортами
find_csv_row_by_id = find_row_by_id


def prev_cumulative_from_row(row: dict[str, str] | None) -> float | None:
    """Накоплено до периода = ВОР_факт из эталона .mpp (пусто → 0)."""
    if row is None:
        return None
    raw = str(row.get("ВОР_факт") or "").strip()
    if not raw:
        return 0.0
    try:
        return float(raw.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def build_task_update(
    state: FormState,
    *,
    before_row: dict[str, str] | None = None,
) -> tuple[TaskUpdate, FormAggregates, dict[str, Any]]:
    """Собрать один TaskUpdate из формы + Mode1 (без PPT)."""
    result = run_mode1_for_form(state)
    agg: FormAggregates = result["aggregates"]
    schedule: dict[str, Any] = result["schedule"]
    report = result["report"]

    start_d = date.fromisoformat(schedule["start"]) if schedule.get("start") else None
    finish_d = date.fromisoformat(schedule["finish"]) if schedule.get("finish") else None

    before = {
        "ВОР": (before_row or {}).get("ВОР") or "",
        "ВОР_факт": (before_row or {}).get("ВОР_факт") or "",
        "ВОР_остаток": (before_row or {}).get("ВОР_остаток") or "",
        "Ед_изм": (before_row or {}).get("Ед_изм") or "",
        "%_выполнения_ВОР": (before_row or {}).get("%_выполнения_ВОР") or "",
        "Осталось_дней_прогноз": (before_row or {}).get("Осталось_дней_прогноз") or "",
        "Начало": (before_row or {}).get("Начало") or "",
        "Окончание": (before_row or {}).get("Окончание") or "",
        "Процент_завершения": (before_row or {}).get("Процент_завершения") or "",
        "Заметки": (before_row or {}).get("Заметки") or "",
    }

    note_bits = [
        f"Форма: Всего={agg.vor} Выполнено={agg.done} Остаток={agg.remaining} {state.unit}",
        f"%ВОР={agg.pct_done:.2f}%",
        f"Mode1 осталось дн≈{schedule.get('remaining_days_ceil')}",
        schedule.get("finish_rule") or "",
    ]
    note = " | ".join(x for x in note_bits if x)

    after = dict(before)
    after["ВОР"] = _num_str(agg.vor)
    after["ВОР_факт"] = _num_str(agg.done)
    after["ВОР_остаток"] = _num_str(agg.remaining)
    if state.unit:
        after["Ед_изм"] = state.unit
    after["%_выполнения_ВОР"] = _pct_int(agg.pct_done)
    if schedule.get("remaining_days_ceil") is not None:
        after["Осталось_дней_прогноз"] = str(int(schedule["remaining_days_ceil"]))
    if start_d:
        after["Начало"] = _fmt_date(start_d)
    if finish_d:
        after["Окончание"] = _fmt_date(finish_d)
    after["Заметки"] = note

    update = TaskUpdate(
        task_id=str(state.task_id).strip(),
        name=state.task_name,
        match_score=1.0,
        ppt_title=state.task_name,
        before=before,
        after=after,
        schedule=schedule,
        ppt=report.to_dict(),
        notes=[
            schedule.get("start_rule") or "",
            schedule.get("finish_rule") or "",
            "Источник: веб-форма",
        ],
    )
    return update, agg, result


@dataclass
class PipelineResult:
    update: TaskUpdate
    aggregates: FormAggregates
    schedule: dict[str, Any]
    status: str
    today: date
    csv_bytes: bytes | None = None
    xml_bytes: bytes | None = None
    mpp_bytes: bytes | None = None
    mpp_error: str | None = None
    com_available: bool = False
    schedule_before: list[dict[str, str]] | None = None
    schedule_after: list[dict[str, str]] | None = None


def run_form_pipeline(
    state: FormState,
    *,
    mpp_path: Path | None = None,
    mpp_bytes: bytes | None = None,
    write_mpp: bool = True,
    write_csv_xml: bool = False,
    etalon_rows: list[dict[str, str]] | None = None,
) -> PipelineResult:
    """Пересчёт Mode1 + запись MPP. Эталон задач — из .mpp (COM dump), не из CSV."""
    mpp_p = mpp_path or SAMPLE_MPP
    source = mpp_bytes
    if source is None and mpp_p.exists():
        source = mpp_p.read_bytes()

    before_row: dict[str, str] | None = None
    rows: list[dict[str, str]] = list(etalon_rows or [])
    read_error: str | None = None

    if not rows and source and project_available():
        try:
            _pname, rows = dump_mpp_rows(source)
        except Exception as e:
            read_error = f"Не удалось прочитать эталон из .mpp: {e}"
            rows = []

    if rows:
        before_row = find_row_by_id(rows, state.task_id)
        pc = prev_cumulative_from_row(before_row) if before_row is not None else None
        if pc is not None:
            state.prev_cumulative = pc

    update, agg, result = build_task_update(state, before_row=before_row)
    updates = [update]

    schedule_before = build_schedule_before(rows) if rows else []
    schedule_after = build_schedule_after(rows, updates) if rows else []

    csv_bytes = None
    xml_bytes = None
    if write_csv_xml and rows:
        fieldnames = list(rows[0].keys())
        csv_bytes = apply_updates_to_csv(fieldnames, rows, updates)
        xml_bytes = rows_to_mspdi_xml(rows, updates, project_name=state.project or "msp_updated")

    com_ok = project_available()
    out_mpp: bytes | None = None
    mpp_error = read_error
    if write_mpp:
        if not com_ok:
            mpp_error = mpp_error or (
                "Расчёт готов. Файл .mpp недоступен на этой машине расчёта "
                "(нужны MS Project и pywin32)."
            )
        elif not source:
            mpp_error = mpp_error or "Нет исходного .mpp: загрузите файл в форму."
        else:
            try:
                out_mpp = apply_updates_to_mpp(source, updates)
            except Exception as e:
                mpp_error = f"Ошибка записи .mpp через COM: {e}"

    return PipelineResult(
        update=update,
        aggregates=agg,
        schedule=result["schedule"],
        status=status_for_aggregates(agg),
        today=result["today"],
        csv_bytes=csv_bytes,
        xml_bytes=xml_bytes,
        mpp_bytes=out_mpp,
        mpp_error=mpp_error,
        com_available=com_ok,
        schedule_before=schedule_before,
        schedule_after=schedule_after,
    )
