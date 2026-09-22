"""Справочники формы из строк .mpp (без CSV)."""

from __future__ import annotations

from demo.catalog import catalog_has_tasks, empty_form_options, options_from_mpp_rows


def test_catalog_has_tasks() -> None:
    assert catalog_has_tasks(None) is False
    assert catalog_has_tasks(empty_form_options()) is False
    assert catalog_has_tasks({"tasks": []}) is False
    assert catalog_has_tasks({"tasks": [{"id": "6", "name": "Фундаменты сборные"}]}) is True


def test_empty_form_options() -> None:
    opts = empty_form_options()
    assert opts["projects"] == []
    assert opts["tasks"] == []
    assert opts["units"]
    assert opts["years"]
    assert opts["source"] == "empty"


def test_options_from_mpp_rows() -> None:
    rows = [
        {
            "Ид": "1",
            "Название": "ЖК Тест",
            "БЛОК": "Суммарная задача",
            "ВОР": "",
            "ВОР_факт": "",
            "Ед_изм": "",
        },
        {
            "Ид": "6",
            "Название": "Фундаменты сборные",
            "БЛОК": "Задача",
            "ВОР": "350",
            "ВОР_факт": "205",
            "Ед_изм": "шт",
        },
    ]
    opts = options_from_mpp_rows(rows, project_name="ЖК Тест")
    assert opts["source"] == "mpp"
    assert opts["projects"][0]["name"] == "ЖК Тест"
    task = next(t for t in opts["tasks"] if t["id"] == "6")
    assert task["vor"] == 350.0
    assert task["vor_fact"] == 205.0
    assert task["unit"] == "шт"
