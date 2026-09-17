"""Таблицы графика до/после пересчёта."""

from __future__ import annotations

from demo.build_update import TaskUpdate
from demo.form_input import FormState, sample_form_for_tests
from demo.form_pipeline import run_form_pipeline
from demo.schedule_tables import build_schedule_after, build_schedule_before


def test_schedule_tables_mark_changed_task() -> None:
    before = [
        {
            "Ид": "6",
            "Название": "Фундаменты сборные",
            "Начало": "01.06.26",
            "Окончание": "15.06.26",
            "ВОР": "350",
            "ВОР_факт": "100",
            "ВОР_остаток": "250",
            "%_выполнения_ВОР": "29",
            "Осталось_дней_прогноз": "10",
            "Заметки": "",
        },
        {
            "Ид": "8",
            "Название": "Плита",
            "Начало": "20.06.26",
            "Окончание": "30.06.26",
            "ВОР": "100",
        },
    ]
    upd = TaskUpdate(
        task_id="6",
        name="Фундаменты сборные",
        match_score=1.0,
        ppt_title="Фундаменты сборные",
        before={"Начало": "01.06.26", "Окончание": "15.06.26", "ВОР": "350"},
        after={
            "Начало": "01.06.26",
            "Окончание": "01.10.26",
            "ВОР": "350",
            "ВОР_факт": "205",
            "ВОР_остаток": "145",
            "%_выполнения_ВОР": "59",
            "Осталось_дней_прогноз": "42",
            "Заметки": "Форма: тест",
        },
        schedule={},
        ppt={},
        notes=[],
    )
    before_rows = build_schedule_before(before)
    after_rows = build_schedule_after(before, [upd])
    assert len(before_rows) == 2
    assert before_rows[0]["Изменено"] == ""
    assert after_rows[0]["Окончание"] == "01.10.26"
    assert "Окончание" in after_rows[0]["Изменено"]
    assert after_rows[1]["Изменено"] == ""


def test_pipeline_includes_schedule_tables() -> None:
    """Без COM/.mpp таблицы эталона пустые; с etalon_rows — заполняются."""
    state = sample_form_for_tests()
    rows = [
        {
            "Ид": "6",
            "Название": "Фундаменты сборные",
            "Начало": "01.06.26",
            "Окончание": "15.06.26",
            "ВОР": "350",
            "ВОР_факт": "205",
            "ВОР_остаток": "145",
            "Ед_изм": "шт",
            "%_выполнения_ВОР": "59",
            "Осталось_дней_прогноз": "",
            "Заметки": "",
            "БЛОК": "Задача",
        }
    ]
    pipe = run_form_pipeline(state, write_mpp=False, write_csv_xml=False, etalon_rows=rows)
    assert pipe.schedule_before
    assert pipe.schedule_after
    hit = next(r for r in pipe.schedule_after if r["Ид"] == state.task_id)
    assert hit["Изменено"]


def test_pipeline_overrides_prev_cumulative_from_mpp_rows() -> None:
    """Ручной prev_cumulative игнорируется — берём ВОР_факт из строк .mpp."""
    state = sample_form_for_tests()
    state.prev_cumulative = 999
    rows = [
        {
            "Ид": "6",
            "Название": "Фундаменты сборные",
            "ВОР": "350",
            "ВОР_факт": "205",
            "Ед_изм": "шт",
            "БЛОК": "Задача",
        }
    ]
    pipe = run_form_pipeline(state, write_mpp=False, write_csv_xml=False, etalon_rows=rows)
    assert state.prev_cumulative == 205
    assert pipe.aggregates.done == 205 + pipe.aggregates.fact_total
