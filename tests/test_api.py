"""API FastAPI: prefill/options/recalc/download (без COM)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _valid_body() -> dict:
    return {
        "project": "ЖК Ленинский",
        "project_id": "0feb8a44-a0f4-11ef-af7f-0050560219d5",
        "period_month": 6,
        "period_year": 2026,
        "mode": "last",
        "task_name": "Фундаменты сборные",
        "task_id": "6",
        "vor": 350,
        "unit": "шт",
        "prev_cumulative": 150,
        "weeks": [
            {"plan": 20, "fact": 10},
            {"plan": 20, "fact": 30},
            {"plan": 20, "fact": 0},
            {"plan": 20, "fact": 15},
            {"plan": 20, "fact": None},
        ],
    }


def test_health_and_options() -> None:
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["ok"] is True
    o = client.get("/api/options")
    assert o.status_code == 200
    data = o.json()
    assert data["months"] and data["years"] and data["units"]
    assert data["tasks"] == []


def test_prefill() -> None:
    r = client.get("/api/prefill")
    assert r.status_code == 200
    data = r.json()
    assert "form" in data and "options" in data
    assert data["form"]["task_id"] == ""
    assert data.get("require_mpp_upload") is True


def test_recalc_400_without_fact() -> None:
    body = _valid_body()
    body["weeks"] = [{"plan": 10, "fact": None} for _ in range(5)]
    r = client.post("/api/recalc", json=body)
    assert r.status_code == 400


def test_recalc_ok_shape() -> None:
    r = client.post("/api/recalc", json=_valid_body())
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"]
    assert "aggregates" in data
    assert "schedule" in data
    assert "downloads" in data and "mpp" in data["downloads"]
    assert "update" in data
    assert "after" in data["update"]
    assert "before" in data["update"]
    assert isinstance(data.get("schedule_before"), list)
    assert isinstance(data.get("schedule_after"), list)
    # без загруженного .mpp таблицы эталона могут быть пустыми
    if data["schedule_after"]:
        changed = [r for r in data["schedule_after"] if r.get("Ид") == "6"]
        assert changed and changed[0].get("Изменено")
    if data["downloads"]["mpp"]:
        assert data["mpp_error"] in (None, "")
    else:
        assert data["mpp_error"]
        assert "xml" not in data["mpp_error"].lower()


def test_download_mpp_404_unknown_job() -> None:
    r = client.get("/api/jobs/does-not-exist/mpp")
    assert r.status_code == 404


def test_download_mpp_when_available() -> None:
    recalc = client.post("/api/recalc", json=_valid_body())
    assert recalc.status_code == 200
    data = recalc.json()
    job_id = data["job_id"]
    r = client.get(f"/api/jobs/{job_id}/mpp")
    if data["downloads"]["mpp"]:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/")
        assert len(r.content) > 0
    else:
        assert r.status_code == 404


def test_mpp_upload_and_recalc_accepts_upload_id() -> None:
    sample = Path(__file__).resolve().parent.parent / "sample_data" / "msp_0feb8a44-a0f4-11ef-af7f-0050560219d5.mpp"
    if not sample.is_file():
        # без sample .mpp — хотя бы валидация формата
        bad = client.post(
            "/api/mpp/upload",
            files={"file": ("note.txt", b"not-mpp", "text/plain")},
        )
        assert bad.status_code == 400
        return
    up = client.post(
        "/api/mpp/upload",
        files={"file": ("source.mpp", sample.read_bytes(), "application/octet-stream")},
    )
    assert up.status_code == 200
    upload_id = up.json()["upload_id"]
    assert upload_id
    body = _valid_body()
    body["mpp_upload_id"] = upload_id
    r = client.post("/api/recalc", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("source_mpp") == "upload"
