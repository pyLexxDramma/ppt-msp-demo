"""Таблицы графика «до / после» для UI (без Streamlit/pandas)."""

from __future__ import annotations

from typing import Any

from .build_update import TaskUpdate

# Как в legacy schedule_view.YELLOW_COLS / render_schedule_table
YELLOW_COLS = [
    "ВОР",
    "ВОР_факт",
    "ВОР_остаток",
    "Ед_изм",
    "%_выполнения_ВОР",
    "Осталось_дней_прогноз",
    "Начало",
    "Окончание",
    "Заметки",
]

SCHEDULE_COLS = [
    "Ид",
    "Название",
    "Начало",
    "Окончание",
    "Предшественники",
    "Последователи",
    "ВОР",
    "ВОР_факт",
    "ВОР_остаток",
    "%_выполнения_ВОР",
    "Осталось_дней_прогноз",
    "Изменено",
    "Заметки",
]


def _cell(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _row_from_csv(r: dict[str, str]) -> dict[str, str] | None:
    tid = _cell(r, "Ид")
    name = _cell(r, "Название")
    if not tid or not name:
        return None
    return {
        "Ид": tid,
        "Название": name,
        "Начало": _cell(r, "Начало"),
        "Окончание": _cell(r, "Окончание"),
        "Предшественники": _cell(r, "Предшественники"),
        "Последователи": _cell(r, "Последователи"),
        "ВОР": _cell(r, "ВОР"),
        "ВОР_факт": _cell(r, "ВОР_факт"),
        "ВОР_остаток": _cell(r, "ВОР_остаток"),
        "%_выполнения_ВОР": _cell(r, "%_выполнения_ВОР"),
        "Осталось_дней_прогноз": _cell(r, "Осталось_дней_прогноз"),
        "Изменено": "",
        "Заметки": (_cell(r, "Заметки") or "")[:120],
    }


def build_schedule_before(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r in rows:
        row = _row_from_csv(r)
        if row:
            out.append(row)
    return out


def build_schedule_after(
    rows: list[dict[str, str]],
    updates: list[TaskUpdate],
) -> list[dict[str, str]]:
    by_id = {str(u.task_id): u for u in updates if getattr(u, "task_id", None)}
    out: list[dict[str, str]] = []
    for r in rows:
        row = _row_from_csv(r)
        if not row:
            continue
        u = by_id.get(row["Ид"])
        if not u:
            out.append(row)
            continue
        changed: list[str] = []
        for col in YELLOW_COLS:
            new_v = u.after.get(col)
            if new_v is None:
                continue
            old_v = str(row.get(col) or "").strip()
            if str(new_v).strip() != old_v:
                changed.append(col)
            if col == "Заметки":
                row[col] = str(new_v)[:120]
            else:
                row[col] = str(new_v)
        row["Изменено"] = ", ".join(changed) if changed else "да"
        out.append(row)
    return out


def schedule_tables_payload(
    rows: list[dict[str, str]],
    updates: list[TaskUpdate],
) -> dict[str, Any]:
    return {
        "schedule_before": build_schedule_before(rows),
        "schedule_after": build_schedule_after(rows, updates),
        "schedule_cols": list(SCHEDULE_COLS),
    }
