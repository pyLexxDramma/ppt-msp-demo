"""Общие payload для API и Streamlit React."""

from demo.form_input import FormState, sample_form_for_tests
from demo.form_pipeline import run_form_pipeline
from demo.payloads import prefill_payload, recalc_payload


def test_prefill_payload_has_form_and_options() -> None:
    data = prefill_payload()
    # пустая форма — без демо-автоподстановки
    assert data["form"]["task_id"] == ""
    assert data["form"]["vor"] == 0
    assert data["options"]["projects"]
    assert data["options"]["tasks"]
    assert data["require_mpp_upload"] is True
    assert "vor_fact" in data["options"]["tasks"][0]


def test_recalc_payload_shape() -> None:
    data = recalc_payload(sample_form_for_tests())
    assert data["job_id"]
    assert "aggregates" in data
    assert "schedule" in data
    assert "downloads" in data
    assert "update" in data
    assert "after" in data["update"]
    assert data["schedule_before"]
    assert data["schedule_after"]
    assert data["schedule_cols"]
