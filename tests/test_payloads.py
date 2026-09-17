"""Общие payload для API и Streamlit React."""

from demo.form_input import sample_form_for_tests
from demo.payloads import prefill_payload, recalc_payload


def test_prefill_payload_has_form_and_empty_options() -> None:
    data = prefill_payload()
    assert data["form"]["task_id"] == ""
    assert data["form"]["vor"] == 0
    assert data["options"]["tasks"] == []
    assert data["options"]["projects"] == []
    assert data["require_mpp_upload"] is True


def test_recalc_payload_shape() -> None:
    data = recalc_payload(sample_form_for_tests())
    assert data["job_id"]
    assert "aggregates" in data
    assert "schedule" in data
    assert "downloads" in data
    assert "update" in data
    assert "after" in data["update"]
    assert isinstance(data.get("schedule_before"), list)
    assert isinstance(data.get("schedule_after"), list)
    assert data["schedule_cols"]
