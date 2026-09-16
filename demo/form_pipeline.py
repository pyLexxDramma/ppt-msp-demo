"""Пайплайн: форма → TaskUpdate → sample MPP (COM) + опционально CSV/XML."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .build_update import TaskUpdate, apply_updates_to_csv, load_msp_csv
from .form_input import FormAggregates, FormState, run_mode1_for_form, status_for_aggregates
from .mpp_writer import apply_updates_to_mpp, project_available
from .xml_export import rows_to_mspdi_xml

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_data"
SAMPLE_CSV = SAMPLE_DIR / "msp_demo.csv"
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


def find_csv_row_by_id(rows: list[dict[str, str]], task_id: str) -> dict[str, str] | None:
    tid = str(task_id).strip()
    for row in rows:
        if str(row.get("Ид") or "").strip() == tid:
            return row
    return None


def silent_prefill_from_csv(
    state: FormState | None = None,
    *,
    csv_path: Path | None = None,
    task_id: str = DEFAULT_TASK_ID,
) -> FormState:
    """Префилл названия/ВОР/ед.изм. из sample CSV (скрыто, без UI upload)."""
    base = state or FormState()
    path = csv_path or SAMPLE_CSV
    if not path.exists():
        base.task_id = task_id
        return base
    try:
        _, rows = load_msp_csv(path)
    except Exception:
        base.task_id = task_id
        return base
    row = find_csv_row_by_id(rows, task_id)
    if not row:
        base.task_id = task_id
        return base
    base.task_id = task_id
    name = (row.get("Название") or "").strip()
    if name:
        base.task_name = name
    try:
        vor = float(str(row.get("ВОР") or "0").replace(" ", "").replace(",", "."))
        if vor > 0:
            base.vor = vor
    except ValueError:
        pass
    unit = (row.get("Ед_изм") or "").strip()
    if unit:
        base.unit = unit
    pid = (row.get("ID_проекта") or "").strip()
    if pid:
        base.project_id = pid
    return base


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


def run_form_pipeline(
    state: FormState,
    *,
    csv_path: Path | None = None,
    mpp_path: Path | None = None,
    write_mpp: bool = True,
    write_csv_xml: bool = True,
) -> PipelineResult:
    """Пересчёт Mode1 + запись sample MPP (если COM) + опционально CSV/XML."""
    csv_p = csv_path or SAMPLE_CSV
    mpp_p = mpp_path or SAMPLE_MPP

    before_row: dict[str, str] | None = None
    fieldnames: list[str] = []
    rows: list[dict[str, str]] = []
    if csv_p.exists():
        fieldnames, rows = load_msp_csv(csv_p)
        before_row = find_csv_row_by_id(rows, state.task_id)

    update, agg, result = build_task_update(state, before_row=before_row)
    updates = [update]

    csv_bytes = None
    xml_bytes = None
    if write_csv_xml and rows and fieldnames:
        csv_bytes = apply_updates_to_csv(fieldnames, rows, updates)
        xml_bytes = rows_to_mspdi_xml(rows, updates, project_name=state.project or "msp_updated")

    com_ok = project_available()
    mpp_bytes = None
    mpp_error = None
    if write_mpp:
        if not com_ok:
            mpp_error = (
                "Расчёт готов. Файл .mpp недоступен на этой машине расчёта "
                "(нужны MS Project и pywin32)."
            )
        elif not mpp_p.exists():
            mpp_error = f"Не найден sample .mpp: {mpp_p.name}. Положите файл в sample_data/."
        else:
            try:
                mpp_bytes = apply_updates_to_mpp(mpp_p.read_bytes(), updates)
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
        mpp_bytes=mpp_bytes,
        mpp_error=mpp_error,
        com_available=com_ok,
    )
