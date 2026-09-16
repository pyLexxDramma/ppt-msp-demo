import { describe, expect, it } from 'vitest'
import type { FormOptions } from './options'
import { defaultForm } from './types'
import { formIsValid, validateForm } from './validation'

const options: FormOptions = {
  months: [],
  years: [2025, 2026, 2027],
  projects: [{ id: '0feb8a44-a0f4-11ef-af7f-0050560219d5', name: 'ЖК Ленинский' }],
  tasks: [
    {
      id: '6',
      name: 'Фундаменты сборные',
      unit: 'шт',
      vor: 350,
      project_id: '0feb8a44-a0f4-11ef-af7f-0050560219d5',
    },
  ],
  units: ['шт', 'м3'],
  modes: [{ id: 'last', label: 'По факту последней недели' }],
}

describe('validateForm', () => {
  it('принимает корректный префилл', () => {
    const err = validateForm(defaultForm(), options)
    expect(formIsValid(err)).toBe(true)
  })

  it('требует объект и задачу из справочника', () => {
    const form = defaultForm()
    form.project = 'Чужой объект'
    form.project_id = 'unknown'
    form.task_name = 'Нет такой'
    form.task_id = '999'
    const err = validateForm(form, options)
    expect(err.project).toBeTruthy()
    expect(err.project_id).toBeTruthy()
    expect(err.task_name).toBeTruthy()
    expect(err.task_id).toBeTruthy()
  })

  it('год только из списка', () => {
    const form = defaultForm()
    form.period_year = 1999
    const err = validateForm(form, options)
    expect(err.period_year).toBeTruthy()
  })

  it('ВОР > 0 и хотя бы один факт > 0', () => {
    const form = defaultForm()
    form.vor = 0
    form.weeks = form.weeks.map((w) => ({ ...w, fact: null }))
    const err = validateForm(form, options)
    expect(err.vor).toBeTruthy()
    expect(err.weeks_fact).toBeTruthy()
  })

  it('ед.изм. из справочника', () => {
    const form = defaultForm()
    form.unit = 'кг'
    const err = validateForm(form, options)
    expect(err.unit).toBeTruthy()
  })
})
