"""Bootstrap для Streamlit: сборка SPA и подъём FastAPI при необходимости."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
DEFAULT_API = "http://127.0.0.1:8000"


def dist_ready() -> bool:
    return (DIST / "index.html").is_file()


def api_base() -> str:
    return (os.environ.get("PPT_MSP_UI_URL") or DEFAULT_API).rstrip("/")


def api_healthy(base: str | None = None, timeout: float = 1.5) -> bool:
    url = f"{(base or api_base())}/api/prefill"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ensure_frontend_build(log: list[str] | None = None) -> None:
    """Собирает frontend/dist, если нет index.html."""
    messages = log if log is not None else []
    if dist_ready():
        messages.append("SPA уже собран (frontend/dist).")
        return

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "Нет npm/Node.js — нечего собрать frontend/dist. "
            "Установите Node.js или соберите SPA заранее: cd frontend && npm run build"
        )

    messages.append("Установка зависимостей frontend (npm install)…")
    install = subprocess.run(
        [npm, "install"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=False,
    )
    if install.returncode != 0:
        raise RuntimeError(
            "npm install не удался:\n"
            + (install.stderr or install.stdout or "")[-2000:]
        )

    messages.append("Сборка SPA (npm run build)…")
    build = subprocess.run(
        [npm, "run", "build"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=False,
    )
    if build.returncode != 0 or not dist_ready():
        raise RuntimeError(
            "npm run build не удался:\n" + (build.stderr or build.stdout or "")[-2000:]
        )
    messages.append("Сборка SPA готова.")


def ensure_api(log: list[str] | None = None, wait_s: float = 20.0) -> str:
    """
    Если API недоступен и UI указывает на localhost — поднимает uvicorn в фоне.
    Возвращает базовый URL UI/API.
    """
    messages = log if log is not None else []
    base = api_base()

    if api_healthy(base):
        messages.append(f"API уже отвечает: {base}")
        return base

    local = base.startswith("http://127.0.0.1") or base.startswith("http://localhost")
    if not local:
        raise RuntimeError(
            f"API недоступен по {base}. "
            "Задайте PPT_MSP_UI_URL на локальный адрес API "
            "(по умолчанию http://127.0.0.1:8000) или освободите порт 8000."
        )

    if not dist_ready():
        raise RuntimeError("Нет frontend/dist — сначала ensure_frontend_build().")

    port = 8000
    try:
        from urllib.parse import urlparse

        parsed = urlparse(base)
        if parsed.port:
            port = parsed.port
    except Exception:
        port = 8000

    messages.append(f"Запуск uvicorn на порту {port}…")
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + wait_s
    while time.time() < deadline:
        if api_healthy(base):
            messages.append(f"API поднят: {base}")
            return base
        time.sleep(0.4)

    raise RuntimeError(
        f"uvicorn не ответил за {wait_s:.0f} с по адресу {base}. "
        "Проверьте порт и зависимости: pip install -r requirements-demo.txt"
    )


def bootstrap(log: list[str] | None = None) -> str:
    """Сборка SPA + API. Возвращает URL для iframe."""
    ensure_frontend_build(log)
    return ensure_api(log)
