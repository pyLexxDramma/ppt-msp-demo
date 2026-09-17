import { describe, expect, it } from 'vitest'
import {
  FORMULAS,
  MPP_FIELDS_UNCHANGED,
  MPP_FIELDS_UPDATED,
  allFormulaIds,
  formulaById,
} from './calcHelp'
import { computeAggregates, formReady } from './formLogic'
import { sampleFormForTests } from './types'

describe('calcHelp catalog', () => {
  it('contains all expected formula ids', () => {
    const ids = allFormulaIds()
    expect(ids).toContain('prev_cum')
    expect(ids).toContain('remaining')
    expect(ids).toContain('finish')
    expect(ids).toContain('fact_period')
    expect(FORMULAS.every((f) => f.formula && f.detail)).toBe(true)
  })

  it('lists MPP updated and unchanged fields', () => {
    expect(MPP_FIELDS_UPDATED.length).toBeGreaterThanOrEqual(8)
    expect(MPP_FIELDS_UNCHANGED.length).toBeGreaterThanOrEqual(4)
    expect(MPP_FIELDS_UPDATED.some((f) => f.projectField === 'Text13')).toBe(true)
    expect(MPP_FIELDS_UNCHANGED.some((f) => f.projectField.includes('Baseline'))).toBe(true)
  })

  it('contains month deviation formula', () => {
    expect(formulaById('month_deviation')?.formula).toContain('план')
  })
})

describe('formLogic aggregates', () => {
  it('matches Mode1 input volumes for sample form', () => {
    const agg = computeAggregates(sampleFormForTests())
    expect(agg.fact_total).toBe(55)
    expect(agg.done).toBe(55)
    expect(agg.remaining).toBe(295)
    expect(formReady(sampleFormForTests())).toBe(true)
  })
})
