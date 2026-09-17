import type { FormState } from './types'
import type { FormOptions } from './options'
import { WEEKS_COUNT } from './types'

export type FieldErrors = Record<string, string>

function isNum(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v) && Number.isFinite(v)
}

/** Строгая валидация формы относительно справочника MPP/CSV. */
export function validateForm(form: FormState, options: FormOptions | null): FieldErrors {
  const err: FieldErrors = {}
  const projects = options?.projects ?? []
  const tasks = options?.tasks ?? []
  const units = options?.units ?? []
  const years = options?.years ?? []

  if (!form.project.trim()) {
    err.project = 'Выберите объект'
  } else if (projects.length && !projects.some((p) => p.name === form.project || p.id === form.project_id)) {
    err.project = 'Объект должен быть из справочника графика'
  }

  if (!form.project_id.trim()) {
    err.project_id = 'ID проекта обязателен'
  } else if (projects.length && !projects.some((p) => p.id === form.project_id)) {
    err.project_id = 'ID проекта не найден в справочнике'
  }

  if (form.period_month < 0 || form.period_month > 11) {
    err.period_month = 'Выберите месяц отчёта'
  }

  if (!form.period_year || (years.length && !years.includes(form.period_year))) {
    err.period_year = 'Выберите год'
  }

  if (!form.task_name.trim()) {
    err.task_name = 'Выберите наименование работ'
  } else if (tasks.length && !tasks.some((t) => t.name === form.task_name)) {
    err.task_name = 'Работа должна быть из справочника MPP'
  }

  if (!form.task_id.trim()) {
    err.task_id = 'Ид задачи обязателен'
  } else if (tasks.length && !tasks.some((t) => t.id === form.task_id)) {
    err.task_id = 'Ид задачи не найден в справочнике'
  } else if (!/^\d+$/.test(form.task_id.trim())) {
    err.task_id = 'Ид задачи — целое число (ID в Project)'
  }

  if (!isNum(form.vor) || form.vor < 0) {
    err.vor = 'ВОР — число ≥ 0'
  } else if (form.vor === 0) {
    err.vor = 'ВОР должен быть больше 0'
  }

  if (!form.unit.trim()) {
    err.unit = 'Выберите единицу измерения'
  } else if (units.length && !units.includes(form.unit)) {
    err.unit = 'Ед.изм. из справочника графика'
  }

  if (!isNum(form.prev_cumulative) || form.prev_cumulative < 0) {
    err.prev_cumulative = 'Число ≥ 0'
  }

  if (form.month_plan === null || form.month_plan === undefined || Number.isNaN(Number(form.month_plan))) {
    err.month_plan = 'Укажите план на месяц (число ≥ 0)'
  } else if (Number(form.month_plan) < 0) {
    err.month_plan = 'План на месяц: число ≥ 0'
  }

  if (form.month_fact === null || form.month_fact === undefined || Number.isNaN(Number(form.month_fact))) {
    err.month_fact = 'Укажите факт за месяц (число ≥ 0)'
  } else if (Number(form.month_fact) < 0) {
    err.month_fact = 'Факт за месяц: число ≥ 0'
  }

  let hasPositiveFact = false
  if (form.month_fact !== null && form.month_fact !== undefined && Number(form.month_fact) > 0) {
    hasPositiveFact = true
  }
  for (let i = 0; i < WEEKS_COUNT; i++) {
    const w = form.weeks[i] ?? { plan: 0, fact: null }
    const planKey = `week_plan_${i}`
    const factKey = `week_fact_${i}`
    if (w.plan === null || w.plan === undefined || Number.isNaN(Number(w.plan)) || Number(w.plan) < 0) {
      err[planKey] = 'План: число ≥ 0'
    }
    if (w.fact !== null && w.fact !== undefined) {
      if (Number.isNaN(Number(w.fact)) || Number(w.fact) < 0) {
        err[factKey] = 'Факт: число ≥ 0 или пусто'
      } else if (Number(w.fact) > 0) {
        hasPositiveFact = true
      }
    }
  }
  if (!hasPositiveFact) {
    err.weeks_fact = 'Нужен факт за месяц > 0 или хотя бы одна неделя с фактом > 0'
  }

  return err
}

export function formIsValid(errors: FieldErrors): boolean {
  return Object.keys(errors).length === 0
}
