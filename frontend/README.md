# Frontend: данные по объёму стройплощадок

React + TypeScript + Vite SPA для MVP Mode1. API: FastAPI (`../api/main.py`).

## Запуск

См. корневой [`../README_DEMO.md`](../README_DEMO.md). Кратко:

```bash
# из корня ppt-msp-demo — API
uvicorn api.main:app --reload --port 8000

# из frontend/
npm install
npm run dev
```

Прокси `/api` → `http://127.0.0.1:8000` (см. `vite.config.ts`).

## Тесты

```bash
npm test
```

Покрывают: `validation`, `formLogic` (агрегаты/накопитель), `calcHelp` (формулы и поля MPP).
