/** Справочник формул и полей MPP — единый источник для UI и тестов. */

export type FormulaItem = {
  id: string
  title: string
  formula: string
  detail: string
}

export type MppFieldItem = {
  label: string
  projectField: string
  note: string
}

/** Расчётные величины на форме (клиент + Mode1 на сервере). */
export const FORMULAS: FormulaItem[] = [
  {
    id: 'month_plan',
    title: 'План на месяц',
    formula: 'Σ план[нед. 1…5]',
    detail: 'Сумма планов по пяти неделям. Поле только для чтения.',
  },
  {
    id: 'month_fact',
    title: 'Факт за месяц',
    formula: 'Σ факт[нед.], где факт задан',
    detail: 'Сумма введённых фактов по неделям. Пустая неделя в сумму не входит. Поле только для чтения.',
  },
  {
    id: 'month_deviation',
    title: 'Отклонение за месяц',
    formula: 'план − факт',
    detail: 'Считается автоматически из сумм плана и факта по неделям. Без недельного факта — «—».',
  },
  {
    id: 'plan_total',
    title: 'Итог плана (недели)',
    formula: 'Σ план[нед. 1…5]',
    detail: 'Та же сумма, что и «План на месяц».',
  },
  {
    id: 'fact_total',
    title: 'Итог факта (недели)',
    formula: 'Σ факт[нед.], где факт задан',
    detail: 'Та же сумма, что и «Факт за месяц».',
  },
  {
    id: 'deviation',
    title: 'Отклонение за неделю',
    formula: 'факт − план',
    detail:
      'Если факт не введён — ячейка «—». Знак «+» = опережение плана, «−» = отставание.',
  },
  {
    id: 'cum_dev',
    title: 'Отклонение накопительно',
    formula: 'сумма отклонений только по неделям с фактом',
    detail:
      'Недели без факта пропускаются и не обнуляют накопитель. Итог в бейдже зоны = последнее ненулевое накопительное значение.',
  },
  {
    id: 'prev_cum',
    title: 'Накоплено до периода',
    formula: 'ВОР_факт из загруженного .mpp (Text15)',
    detail:
      'Read-only: берётся из графика по выбранной задаче. Пустое значение в эталоне = 0.',
  },
  {
    id: 'done',
    title: 'Факт накопленный с начала',
    formula: 'накоплено_до_периода + Σ факт_месяца',
    detail:
      'Накоплено до периода — из .mpp (Text15 / ВОР_факт). Плюс факт текущего отчётного месяца из формы.',
  },
  {
    id: 'remaining',
    title: 'Остаток до ВОР',
    formula: 'ВОР − факт_накопленный_с_начала',
    detail: 'ВОР — плановый объём работ по задаче. Отрицательный остаток = превышение ВОР.',
  },
  {
    id: 'pct_vor',
    title: '% выполнения ВОР',
    formula: '(факт_накопленный / ВОР) × 100',
    detail: 'Пишется в MPP (Number1). При ВОР = 0 процент считается 0.',
  },
  {
    id: 'today',
    title: 'Дата «сегодня» для прогноза',
    formula: 'последний календарный день месяца отчёта',
    detail:
      'Отдельного поля «сегодня» нет: берётся конец выбранных месяца и года (например, июль 2026 → 2026-07-31).',
  },
  {
    id: 'fact_period',
    title: 'Факт за период (Mode1)',
    formula: 'факт последней недели, где факт > 0',
    detail:
      'Недели с фактом = 0 пропускаются. Если ни одной недели с фактом > 0 — Mode1 неприменим.',
  },
  {
    id: 'forecast_weeks',
    title: 'Прогноз недель',
    formula: 'остаток / факт_периода',
    detail: 'При остатке = 0 прогноз = 0 (работа завершена). При факте_периода ≤ 0 расчёт не выполняется.',
  },
  {
    id: 'remaining_days',
    title: 'Осталось дней (прогноз)',
    formula: 'ceil(прогноз_недель × 7)',
    detail: 'Округление вверх до целых дней. В MPP уходит в Number2.',
  },
  {
    id: 'finish',
    title: 'Окончание (прогноз)',
    formula: 'сегодня + ceil(остаток / факт_периода × 7) дней',
    detail:
      'Режим №1. Если всего выполнено (остаток = 0) — особые правила даты в schedule (пн крайней недели с прогрессом).',
  },
  {
    id: 'start',
    title: 'Начало (факт/расчёт)',
    formula: 'понедельник первой недели отчётного месяца с фактом > 0',
    detail:
      'Без помесячной истории: старт = пн N-й недели периода, где N — первая неделя с фактом > 0.',
  },
  {
    id: 'status',
    title: 'Статус',
    formula: 'done > ВОР → превышение; done ≥ ВОР → завершено; иначе в работе',
    detail: 'Сравнивается факт накопленный с начала и ВОР.',
  },
]

/** Поля .mpp / Project, которые меняем при пересчёте. */
export const MPP_FIELDS_UPDATED: MppFieldItem[] = [
  { label: 'ВОР', projectField: 'Text13', note: 'Плановый объём из формы' },
  { label: 'ВОР_факт', projectField: 'Text15', note: 'Факт накопленный с начала' },
  { label: 'ВОР_остаток', projectField: 'Text16', note: 'Остаток до ВОР' },
  { label: 'Ед_изм', projectField: 'Text14', note: 'Единица измерения' },
  { label: '%_выполнения_ВОР', projectField: 'Number1', note: '(факт/ВОР)×100' },
  {
    label: 'Осталось_дней_прогноз',
    projectField: 'Number2',
    note: 'ceil(остаток/факт_недели×7)',
  },
  { label: 'Начало', projectField: 'Start', note: 'Расчёт Mode1 (пн первой недели с фактом)' },
  { label: 'Окончание', projectField: 'Finish', note: 'Расчёт Mode1 (сегодня + дни прогноза)' },
  { label: 'Заметки', projectField: 'Notes', note: 'Краткий след расчёта (объёмы, правило Mode1)' },
]

/** Поля .mpp, которые не трогаем. */
export const MPP_FIELDS_UNCHANGED: MppFieldItem[] = [
  { label: 'Базовое начало / окончание', projectField: 'BaselineStart / BaselineFinish', note: 'База графика' },
  { label: 'Базовая длительность', projectField: 'BaselineDuration', note: 'Не пересчитываем' },
  { label: 'Предшественники / последователи', projectField: 'Predecessors / Successors', note: 'Связи задач' },
  { label: '% завершения MSP', projectField: 'PercentComplete', note: 'Не пишем (кроме аварийного снятия 100% при остатке > 0)' },
  { label: 'ActualStart / ActualFinish', projectField: 'Actual*', note: 'По умолчанию не записываем' },
  { label: 'Остальные задачи графика', projectField: '—', note: 'Обновляется только задача с Ид из формы' },
]

export function formulaById(id: string): FormulaItem | undefined {
  return FORMULAS.find((f) => f.id === id)
}

export function allFormulaIds(): string[] {
  return FORMULAS.map((f) => f.id)
}
