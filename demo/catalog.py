"""Справочники формы из загруженного .mpp (COM) — без CSV как источника истины."""

from __future__ import annotations

from typing import Any

from .form_input import MONTHS_RU
from .mpp_writer import dump_mpp_rows, project_available

FALLBACK_UNITS = ["шт", "м3", "м2", "м", "т", "компл.", "п.м"]


def empty_form_options() -> dict[str, Any]:
    """Пустые справочники до загрузки .mpp."""
    year_now = 2026
    return {
        "months": MONTHS_RU,
        "years": list(range(year_now - 2, year_now + 6)),
        "projects": [],
        "tasks": [],
        "units": sorted(FALLBACK_UNITS, key=lambda u: u.lower()),
        "modes": [
            {
                "id": "last",
                "label": "По факту последней недели (Mode1)",
            }
        ],
        "source": "empty",
    }


def options_from_mpp_rows(
    rows: list[dict[str, str]],
    *,
    project_name: str = "Проект",
    project_id: str = "mpp",
) -> dict[str, Any]:
    """Собрать options из канонических строк задач (dump .mpp)."""
    projects: list[dict[str, str]] = []
    tasks: list[dict[str, Any]] = []
    units: set[str] = set(FALLBACK_UNITS)

    root_name = (project_name or "").strip() or "Проект"
    for row in rows:
        n = (row.get("Название") or "").strip()
        if n and (row.get("БЛОК") or "") == "Суммарная задача":
            root_name = n
            break

    for row in rows:
        name = (row.get("Название") or "").strip()
        block = (row.get("БЛОК") or "").strip()
        tid = str(row.get("Ид") or "").strip()
        unit = (row.get("Ед_изм") or "").strip()
        vor_raw = (row.get("ВОР") or "").strip()
        if unit:
            units.add(unit)
        if not name or block == "Суммарная задача" or not vor_raw:
            continue
        try:
            vor = float(vor_raw.replace(" ", "").replace(",", "."))
        except ValueError:
            continue
        if vor <= 0 or not tid:
            continue
        vor_fact_raw = (row.get("ВОР_факт") or "").strip()
        try:
            vor_fact = (
                float(vor_fact_raw.replace(" ", "").replace(",", "."))
                if vor_fact_raw
                else 0.0
            )
        except ValueError:
            vor_fact = 0.0
        tasks.append(
            {
                "id": tid,
                "name": name,
                "unit": unit or "шт",
                "vor": vor,
                "vor_fact": vor_fact,
                "project_id": project_id,
            }
        )

    if tasks:
        projects = [{"id": project_id, "name": root_name}]

    year_now = 2026
    return {
        "months": MONTHS_RU,
        "years": list(range(year_now - 2, year_now + 6)),
        "projects": projects,
        "tasks": tasks,
        "units": sorted(units, key=lambda u: u.lower()),
        "modes": [
            {
                "id": "last",
                "label": "По факту последней недели (Mode1)",
            }
        ],
        "source": "mpp",
    }


def load_form_options_from_mpp(mpp_bytes: bytes) -> dict[str, Any]:
    """Прочитать справочники напрямую из .mpp (нужны MS Project + pywin32)."""
    if not project_available():
        raise RuntimeError(
            "Чтение .mpp недоступно: нужны MS Project и pywin32 на хосте расчёта"
        )
    project_name, rows = dump_mpp_rows(mpp_bytes)
    return options_from_mpp_rows(rows, project_name=project_name)


def load_form_options() -> dict[str, Any]:
    """До загрузки .mpp — пустые списки задач (CSV больше не источник)."""
    return empty_form_options()
