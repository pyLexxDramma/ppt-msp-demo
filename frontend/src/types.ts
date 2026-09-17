export const WEEKS_COUNT = 5

export const MONTHS_RU = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
] as const

export type WeekRow = {
  plan: number | null
  fact: number | null
}

export type FormState = {
  project: string
  project_id: string
  period_month: number
  period_year: number
  mode: string
  task_name: string
  task_id: string
  vor: number
  unit: string
  prev_cumulative: number
  weeks: WeekRow[]
}

export type WeekAgg = {
  dev: number | null
  cum: number | null
}

export type Aggregates = {
  plan_total: number
  fact_total: number
  month_cum: number
  done: number
  remaining: number
  pct_done: number
  vor: number
  rows: WeekAgg[]
}

export type ScheduleRow = Record<string, string>

export type RecalcResult = {
  job_id: string
  status: 'progress' | 'done' | 'over' | string
  aggregates: Aggregates
  schedule: {
    start?: string | null
    finish?: string | null
    start_rule?: string
    finish_rule?: string
    remaining_days_ceil?: number | null
    mode1?: {
      last_week?: number | null
      fact_period?: number | null
      forecast_weeks?: number | null
      remaining_days_ceil?: number | null
    }
  }
  mode1: Record<string, unknown>
  today: string
  com_available: boolean
  mpp_error: string | null
  downloads: {
    mpp: boolean
  }
  mpp_b64?: string | null
  update: {
    task_id: string
    name: string
    before?: Record<string, string>
    after: Record<string, string>
  }
  /** Полный график до пересчёта (legacy-таблицы). */
  schedule_before?: ScheduleRow[]
  /** Полный график после пересчёта. */
  schedule_after?: ScheduleRow[]
  schedule_cols?: string[]
}

export function defaultForm(): FormState {
  return {
    project: 'ЖК Ленинский',
    project_id: '0feb8a44-a0f4-11ef-af7f-0050560219d5',
    period_month: 6,
    period_year: 2026,
    mode: 'last',
    task_name: 'Фундаменты сборные',
    task_id: '6',
    vor: 350,
    unit: 'шт',
    prev_cumulative: 0,
    weeks: [
      { plan: 20, fact: 10 },
      { plan: 20, fact: 30 },
      { plan: 20, fact: 0 },
      { plan: 20, fact: 15 },
      { plan: 20, fact: null },
    ],
  }
}
