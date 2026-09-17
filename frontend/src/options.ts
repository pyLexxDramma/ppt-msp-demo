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
}

export const FIELD_HELP: Record<string, string> = {
  project: 'Выбор объекта из справочника графика (в бою — из БД). Текст, список значений MPP/БД.',
  project_id: 'UUID / ID проекта из графика. Заполняется автоматически при выборе объекта.',
  period_month: 'Месяц отчёта: целое 0–11 (январь–декабрь).',
  period_year: 'Год отчёта: целое число из списка (календарный год).',
  mode: 'Режим прогноза Mode1: по факту последней недели. Остальные режимы — следующий этап.',
  task_name: 'Наименование работ — leaf-задача с ВОР из графика MPP (в бою — из БД).',
  task_id: 'Ид задачи MS Project (числовой ID). Заполняется автоматически при выборе работ.',
  vor: 'ВОР — плановый объём из графика (read-only). Меняется при выборе наименования работ.',
  unit: 'Единица измерения из справочника (шт, м3, м2…).',
  prev_cumulative:
    'Накоплено до периода = ВОР_факт из эталона графика (read-only). Не редактируется в форме.',
  week_plan: 'План за неделю: число ≥ 0.',
  week_fact: 'Факт за неделю: пусто или число ≥ 0. Для пересчёта нужна хотя бы одна неделя с фактом > 0.',
}
