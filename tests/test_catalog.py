"""Справочники формы из sample CSV."""

from __future__ import annotations

from demo.catalog import load_form_options


def test_load_form_options_has_core_lists() -> None:
    opts = load_form_options()
    assert opts["projects"]
    assert opts["tasks"]
    assert opts["units"]
    assert opts["years"]
    assert any(t["id"] == "6" for t in opts["tasks"]) or opts["tasks"]
    assert "шт" in opts["units"]


def test_task_option_shape() -> None:
    opts = load_form_options()
    task = opts["tasks"][0]
    assert "id" in task and "name" in task and "unit" in task
    assert "vor" in task and "project_id" in task
