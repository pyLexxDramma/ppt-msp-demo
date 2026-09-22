import { describe, expect, it } from 'vitest'
import { catalogHasTasks } from './mppCatalog'
import type { FormOptions } from './options'

const empty: FormOptions = {
  months: [],
  years: [],
  projects: [],
  tasks: [],
  units: [],
  modes: [],
}

describe('catalogHasTasks', () => {
  it('пустой справочник не открывает форму', () => {
    expect(catalogHasTasks(null)).toBe(false)
    expect(catalogHasTasks(undefined)).toBe(false)
    expect(catalogHasTasks(empty)).toBe(false)
  })

  it('есть leaf-задачи — можно выбирать наименование', () => {
    expect(
      catalogHasTasks({
        ...empty,
        tasks: [{ id: '6', name: 'Фундаменты сборные', unit: 'шт', vor: 350, vor_fact: 0, project_id: 'mpp' }],
      }),
    ).toBe(true)
  })
})
