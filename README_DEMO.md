# Демо: форма объёмов → Mode1 → MS Project

Полная инструкция: **[GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md](GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md)**.  
Чеклист показа заказчику: **[DEMO_SHOW.md](DEMO_SHOW.md)**.

Веб-форма ввода плана/факта по неделям → расчёт начала/окончания (**Режим №1**) → обновление sample `.mpp` через COM (Windows + MS Project) и скачивание файла для Project.

## UI

Единственный UI — **React SPA** (`frontend/`).  
**Streamlit** (`demo_app.py`) — оболочка: тот же React (компонент из `frontend/dist` или iframe на локальный API). Отдельной Streamlit-формы нет.

## Запуск через Streamlit

Нужны Python и (для первой сборки) Node.js/npm. Если `frontend/dist` уже есть — Node не обязателен:

```bash
cd ppt-msp-demo
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements-demo.txt
streamlit run demo_app.py --server.port 8503
```

Открыть: **http://localhost:8503**

При отсутствии `frontend/dist` Streamlit сам соберёт SPA и при необходимости поднимет uvicorn на `:8000`.

## Запуск React + API отдельно (разработка)

```bash
cd ppt-msp-demo
source .venv/bin/activate   # или .venv\Scripts\activate на Windows
pip install -r requirements-demo.txt

# терминал 1 — API
uvicorn api.main:app --reload --port 8000

# терминал 2 — SPA
cd frontend
npm install
npm run dev
```

Открыть: **http://localhost:5173**  
API docs: **http://localhost:8000/docs**  
Vite проксирует `/api` → `http://127.0.0.1:8000`.

### Прозрачность расчётов

Под заголовком — раскрывающийся блок (по умолчанию **свёрнут**): что меняется в `.mpp` и свод формул Mode1.

## Sample-данные

- `sample_data/msp_*.mpp` — эталонный график (локально / на Windows-хосте)
- `sample_data/msp_demo.csv` — **устаревший** прокси; в продуктовом пути **не используется**

Источник истины — **только `.mpp`**. Справочник задач / ВОР / ВОР_факт читаются через MS Project COM на Windows API при `POST /api/mpp/upload`.

Сценарий: **загрузить `.mpp` → выбрать задачу (UID/ВОР/накоплено из файла) → план/факт → пересчитать → скачать `.mpp`**.  
До загрузки форма заблокирована; без живого Windows API с Project каталог из файла недоступен.

## Поток в UI

1. Загрузить исходный `.mpp` (пункт 1) — подтянутся объекты/работы из файла.
2. Выбрать наименование работ; ID, ВОР и «накоплено до периода» (`Text15` / ВОР_факт) подставятся read-only.
3. Заполнить план/факт по неделям.
4. **Сохранить и пересчитать** (Mode1) → скачать обновлённый `.mpp`.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/options` | пустые справочники до upload |
| GET | `/api/prefill` | пустая форма + пустые options |
| POST | `/api/mpp/upload` | загрузка `.mpp` + `options` из COM |
| GET | `/api/mpp/{id}/options` | справочник по upload_id |
| POST | `/api/recalc` | Mode1 + запись `.mpp` |
| GET | `/api/jobs/{id}/mpp` | скачивание `.mpp` |

Канонический вход/выход продукта — **только `.mpp`**.

## Режим №1

1. Последняя неделя с **Факт > 0**
2. `остаток / факт × 7` → `ceil` → окончание
3. **Сегодня** = последний день месяца отчёта
4. Отклонение на форме: **Факт − План**; недели без факта в накопитель не входят

## Структура

```
ppt-msp-demo/
  api/main.py              # FastAPI
  frontend/                # React + TS (Vite) — единственный UI
  demo_app.py              # Streamlit-оболочка (React)
  demo/streamlit_react.py  # React как Streamlit-компонент
  demo/streamlit_boot.py   # локальный bootstrap dist + uvicorn
  demo/payloads.py
  demo/form_input.py
  demo/form_pipeline.py
  demo/mode1.py
  demo/mpp_writer.py
  demo/catalog.py
  sample_data/
  tests/
  DEMO_SHOW.md
```

## Тесты (без COM)

```bash
# Python (Mode1, форма, пайплайн, API)
pip install -r requirements-demo.txt
python -m pytest tests/ -q

# Frontend (валидация, агрегаты, calcHelp)
cd frontend && npm test
```

COM/MS Project на CI не требуется: логика Mode1 и API покрыты без записи `.mpp`. Запись `.mpp` — ручной smoke на Windows (см. `DEMO_SHOW.md`).
