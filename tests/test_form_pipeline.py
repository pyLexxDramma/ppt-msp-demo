"""Пайплайн формы без COM: TaskUpdate, статус, mpp_error."""

from __future__ import annotations

from demo.form_input import FormState, WeekRow, sample_form_for_tests
from demo.form_pipeline import run_form_pipeline


def test_pipeline_builds_update_and_schedule() -> None:
    state = sample_form_for_tests()
    pipe = run_form_pipeline(state, write_mpp=True, write_csv_xml=False)
    assert pipe.update.task_id == state.task_id
    assert pipe.update.after.get("ВОР")
    assert pipe.update.after.get("Начало") or pipe.schedule.get("start")
    assert pipe.schedule.get("mode1", {}).get("last_week") == 4
    assert pipe.status in {"progress", "done", "over"}
    assert "before" in pipe.update.__dataclass_fields__ or pipe.update.before is not None


def test_pipeline_mpp_unavailable_message_without_com() -> None:
    state = sample_form_for_tests()
    pipe = run_form_pipeline(state, write_mpp=True, write_csv_xml=False)
    if pipe.com_available and pipe.mpp_bytes:
        # На Windows+Project файл может появиться — это тоже OK
        assert pipe.mpp_error is None
        return
    assert pipe.mpp_bytes is None
    assert pipe.mpp_error is not None
    assert "mpp" in pipe.mpp_error.lower()
    assert "mac" not in pipe.mpp_error.lower()
    assert "xml" not in pipe.mpp_error.lower()


def test_pipeline_over_status() -> None:
    state = sample_form_for_tests()
    state.vor = 30
    state.prev_cumulative = 20
    state.weeks = [
        WeekRow(10, 20),
        WeekRow(10, None),
        WeekRow(10, None),
        WeekRow(10, None),
        WeekRow(10, None),
    ]
    pipe = run_form_pipeline(state, write_mpp=False, write_csv_xml=False)
    assert pipe.status == "over"
    assert pipe.aggregates.remaining < 0
