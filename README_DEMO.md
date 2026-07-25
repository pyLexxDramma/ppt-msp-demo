# Демо PPT → MSP (для КП / созвона с XCA)

Полная инструкция по тесту, деплою и рекомендациям: **[GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md](GUIDE_TEST_DEPLOY_RECOMMENDATIONS.md)**.

Веб-ввод PPT-отчёта подрядчика → расчёт начала/окончания (Режим №1) → CSV/XML для MS Project → отображение на Ганте.

Формулировка КП: *«веб-ввод данных → расчёт сроков начала/окончания в MS Project по фактическим данным → отображение в дашборде»*.

## Быстрый старт

```bash
cd d:\AI_codding\Analitics\mspdash
pip install -r requirements-demo.txt
streamlit run demo_app.py --server.port 8503
```

Открыть http://localhost:8503

По умолчанию включены файлы из `sample_data/` (Ленинский / UUID `0feb8a44-…`).

## Поток в UI

1. **Загрузить** свои `.pptx` + `.csv` (опционально `.xml` / `.mpp`) — или режим «Демо-файлы».
2. **Рассчитать и подготовить файлы**.
3. **Скачать:**
   - `msp_updated.csv`
   - `msp_updated.xml` (MSPDI, собран из обновлённого графика)
   - `msp_patched.xml` — если загружали свой XML (патч Start/Finish по ID)
   - ZIP-пакет CSV+XML
   - `.mpp` — только при установленном MS Project

## Сценарии демо

| Код | Что делаем | Когда |
|-----|------------|--------|
| **C** | Скачать CSV или XML → File → Open в MS Project | Созвон / Streamlit Cloud |
| **A** | Кнопка «Сформировать .mpp» (нужны Windows + MS Project + `pywin32`) | Локальный wow |

```bash
pip install pywin32   # только для варианта A
```

## Что обновляется («жёлтые» колонки CSV)

- `Начало`, `Окончание` — по Режиму №1 и правилу старта
- `ВОР`, `Ед_изм` — из малой таблицы PPT
- `Заметки` — факт / % ВОР / прогноз дней

**Не трогаем:** базовые даты, предшественники/последователи, `% завершения` (считает Project).

## Режим №1

1. Последняя неделя отчёта с **Факт > 0**
2. `Прогноз_недель = ВОР(остаток) / Факт_за_неделю`
3. `Осталось дней = Прогноз_недель × 7`
4. `Окончание = Сегодня + ceil(дней)`

Дата «сегодня» задаётся в сайдбаре (для воспроизводимости теста: 2026-07-25).

## Структура

```
mspdash/
  demo_app.py           # Streamlit UI
  requirements-demo.txt
  README_DEMO.md
  demo/
    parse_pptx.py       # OLE Excel из PPTX
    mode1.py            # расчёт сроков
    build_update.py     # матчинг + CSV
    mpp_writer.py       # опционально COM → MPP
  sample_data/
    stroyka_demo.pptx
    msp_demo.csv
    msp_demo.mpp
```

## Импорт CSV в Project (памятка для созвона)

1. MS Project → File → Open → `msp_updated.csv`
2. Карта: Название→Name, Начало→Start, Окончание→Finish, Ид→ID, Предшественники→Predecessors…
3. Кодировка Windows-1251, разделитель `;`
4. Проверить каскад у последователей задач «Фундаменты сборные» / «Монолитная плита»
