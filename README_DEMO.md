# Демо: форма объёмов → Mode1 → MS Project

Полная инструкция: **[GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md](GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md)**.  
Чеклист показа заказчику: **[DEMO_SHOW.md](DEMO_SHOW.md)**.

Веб-форма ввода плана/факта по неделям → расчёт начала/окончания (**Режим №1**) → обновление sample `.mpp` через COM (Windows + MS Project) и скачивание файла для Project.

## Два UI (параллельно)

| UI | Назначение |
|----|------------|
| **React SPA** `frontend/` | Продуктовый UI (кастомные селекты, тосты, MVP) → деплой на **Vercel** |
| **Streamlit** `demo_app.py` | Оболочка: **тот же React UI** в iframe (1:1) |

Оба ходят в один FastAPI (`api/main.py` + пайплайн `demo/`).

## Быстрый старт: React + FastAPI

```bash
cd ppt-msp-demo
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

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

Для продакшен-фронта: сборка `frontend/` на **Vercel**; API (`uvicorn`) — отдельно (для `.mpp` — Windows + Project). В SPA задайте URL API (CORS на бэкенде).

### Прозрачность расчётов

Под заголовком — раскрывающийся блок (по умолчанию **свёрнут**): что меняется в `.mpp` и свод формул Mode1.

## Streamlit = тот же React UI

Достаточно одного процесса — при старте Streamlit **сам** соберёт `frontend/dist` (если нет) и поднимет uvicorn на `:8000`:

```bash
cd ppt-msp-demo
source .venv/bin/activate
pip install -r requirements-demo.txt
streamlit run demo_app.py --server.port 8503
```

Открыть **http://localhost:8503**. Нужны Node.js/npm (для первой сборки SPA).

URL iframe: `PPT_MSP_UI_URL` (по умолчанию `http://127.0.0.1:8000`).

**Streamlit Community Cloud:** iframe на `127.0.0.1` из браузера пользователя не работает. Либо публичный `PPT_MSP_UI_URL` (Vercel SPA + API), либо продуктовый деплой без Streamlit-оболочки. `packages.txt` ставит Node для сборки на Cloud, но без публичного UI URL этого мало.

## Sample-данные

- `sample_data/msp_0feb8a44-a0f4-11ef-af7f-0050560219d5.mpp` (локально, в `.gitignore`)
- `sample_data/msp_demo.csv` — скрытый префилл задачи Id 6 и справочник селектов

## Поток в UI

1. Выбрать объект, месяц/год, наименование работ (селекты); ID проекта/задачи и ВОР подставляются из графика.
2. Заполнить план/факт по неделям и накоплено до периода.
3. **Сохранить и пересчитать** (Mode1).
4. Скачать обновлённый **`.mpp`** (на машине с MS Project + pywin32).

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/options` | справочники для селектов |
| GET | `/api/prefill` | префилл формы из sample CSV |
| POST | `/api/aggregates` | агрегаты (опционально) |
| POST | `/api/recalc` | Mode1 + подготовка `.mpp` |
| GET | `/api/jobs/{id}/mpp` | скачивание `.mpp` |

Канонический выход продукта в UI — **только `.mpp`**. CSV/XML могут генерироваться внутри пайплайна для отладки, но не предлагаются в SPA.

## Режим №1

1. Последняя неделя с **Факт > 0**
2. `остаток / факт × 7` → `ceil` → окончание
3. **Сегодня** = последний день месяца отчёта
4. Отклонение на форме: **Факт − План**; недели без факта в накопитель не входят

## Структура

```
ppt-msp-demo/
  api/main.py              # FastAPI
  frontend/                # React + TS (Vite)
  demo_app.py              # Streamlit (демо)
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
