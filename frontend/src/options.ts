export type SelectOption = {
  value: string
  label: string
}

export type TaskOption = {
  id: string
  name: string
  unit: string
  vor: number
  /** ВОР_факт из эталона = накоплено до периода */
  vor_fact: number
  project_id: string
}

export type ProjectOption = {
  id: string
  name: string
}

export type FormOptions = {
  months: string[]
  years: number[]
  projects: ProjectOption[]
  tasks: TaskOption[]
  units: string[]
  modes: { id: string; label: string }[]
  source?: string
}

export const FIELD_HELP: Record<string, string> = {
  project: 'Выбор объекта из справочника графика (в бою — из БД). Текст, список значений MPP/БД.',
  project_id: 'UUID / ID проекта из графика. Заполняется автоматически при выборе объекта.',
  period_month: 'Месяц отчёта: целое 0–11 (январь–декабрь).',
  period_year: 'Год отчёта: целое число из списка (календарный год).',
  mode: 'Режим расчёта прогноза. Сейчас доступен Mode1 (по факту последней недели); остальные режимы появятся в списке.',
  task_name: 'Наименование работ — leaf-задача с ВОР из загруженного .mpp.',
  task_id: 'Ид задачи MS Project. Подставляется из .mpp при выборе работ.',
  vor: 'ВОР — плановый объём из .mpp (Text13), read-only.',
  unit: 'Единица измерения из .mpp (Text14) по выбранной задаче, read-only.',
  prev_cumulative:
    'Накоплено до периода = ВОР_факт из .mpp (Text15), read-only.',
  month_plan: 'План на месяц = сумма планов по неделям. Считается автоматически.',
  month_fact: 'Факт за месяц = сумма введённых фактов по неделям. Считается автоматически.',
  month_deviation: 'Отклонение за месяц = План − Факт (считается автоматически).',
  week_plan: 'План за неделю: число ≥ 0.',
  week_fact: 'Факт за неделю: пусто или число ≥ 0. Для Mode1 нужна хотя бы одна неделя с фактом > 0.',
}
