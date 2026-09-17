"""Общие payload для API и Streamlit React."""

from demo.form_input import FormState
from demo.payloads import prefill_payload, recalc_payload


def test_prefill_payload_has_form_and_options() -> None:
    data = prefill_payload()
    assert data["form"]["task_id"]
    assert data["options"]["projects"]
    assert data["options"]["tasks"]
    # накоплено до периода из эталона (ВОР_факт); в sample Id6 = 205
    assert data["form"]["prev_cumulative"] == 205
    assert "vor_fact" in data["options"]["tasks"][0]


def test_recalc_payload_shape() -> None:
    data = recalc_payload(FormState())
    assert data["job_id"]
    assert "aggregates" in data
    assert "schedule" in data
    assert "downloads" in data
    assert "update" in data
    assert "after" in data["update"]
    assert data["schedule_before"]
    assert data["schedule_after"]
    assert data["schedule_cols"]
