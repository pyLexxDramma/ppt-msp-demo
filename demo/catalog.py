"""Справочники полей из sample CSV (прокси данных MPP / будущей БД)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .build_update import load_msp_csv
from .form_input import MONTHS_RU
from .form_pipeline import SAMPLE_CSV

# Типичные единицы из графиков СМР (дополняют CSV)
FALLBACK_UNITS = ["шт", "м3", "м2", "м", "т", "компл.", "п.м"]


def load_form_options(csv_path: Path | None = None) -> dict[str, Any]:
    """Опции для селектов формы: проекты, задачи, ед.изм., годы."""
    path = csv_path or SAMPLE_CSV
    projects: list[dict[str, str]] = []
    tasks: list[dict[str, Any]] = []
    units: set[str] = set(FALLBACK_UNITS)
    project_ids: set[str] = set()

    if path.exists():
        _, rows = load_msp_csv(path)
        for row in rows:
            name = (row.get("Название") or "").strip()
            block = (row.get("БЛОК") or "").strip()
            tid = str(row.get("Ид") or "").strip()
            pid = (row.get("ID_проекта") or "").strip()
            unit = (row.get("Ед_изм") or "").strip()
            vor_raw = (row.get("ВОР") or "").strip()

            if pid:
                project_ids.add(pid)
            if unit:
                units.add(unit)

            # leaf-задачи с ВОР — как в матчинге
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
                    "project_id": pid,
                }
            )

        # объекты: уникальные ID + человекочитаемое имя из суммарной/корня
        root_name = "ЖК Ленинский"
        for row in rows:
            n = (row.get("Название") or "").strip()
            if n and (row.get("БЛОК") or "") == "Суммарная задача":
                root_name = n
                break
        for pid in sorted(project_ids):
            projects.append({"id": pid, "name": root_name})

    if not projects:
        projects = [
            {
                "id": "0feb8a44-a0f4-11ef-af7f-0050560219d5",
                "name": "ЖК Ленинский",
            }
        ]
    if not tasks:
        tasks = [
            {
                "id": "6",
                "name": "Фундаменты сборные",
                "unit": "шт",
                "vor": 350.0,
                "vor_fact": 0.0,
                "project_id": projects[0]["id"],
            }
        ]

    # Leaf-строки CSV часто без ID_проекта — берём единственный/первый объект
    default_pid = projects[0]["id"]
    for t in tasks:
        if not t.get("project_id"):
            t["project_id"] = default_pid

    year_now = 2026
    years = list(range(year_now - 2, year_now + 6))

    return {
        "months": MONTHS_RU,
        "years": years,
        "projects": projects,
        "tasks": tasks,
        "units": sorted(units, key=lambda u: u.lower()),
        "modes": [
            {
                "id": "last",
                "label": "По факту последней недели (Mode1)",
            }
        ],
    }
