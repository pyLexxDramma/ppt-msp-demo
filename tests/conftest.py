"""Общие фикстуры: не ходить на живой Windows-туннель из unit-тестов."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_live_windows_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("demo.windows_host.remote_upload_mpp", lambda *a, **k: None)
    monkeypatch.setattr("demo.windows_host.remote_recalc", lambda *a, **k: None)
    monkeypatch.setattr("demo.windows_host.windows_api_healthy", lambda *a, **k: False)
