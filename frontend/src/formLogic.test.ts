import { describe, expect, it } from 'vitest'
import { computeAggregates, formReady, signedFmt } from './formLogic'
import { defaultForm, type FormState } from './types'

function weeks(...facts: Array<number | null>): FormState['weeks'] {
  return facts.map((fact) => ({ plan: 20, fact }))
}

describe('formLogic cumulative deviation', () => {
  it('пропускает недели без факта в накопителе', () => {
    const form = defaultForm()
    form.prev_cumulative = 0
    form.weeks = weeks(10, null, 0, 15, null)
    const agg = computeAggregates(form)
    expect(agg.rows[0].dev).toBe(-10)
    expect(agg.rows[1].dev).toBeNull()
    expect(agg.rows[1].cum).toBeNull()
    expect(agg.rows[2].cum).toBe(-10 + -20)
    expect(agg.fact_total).toBe(25)
    expect(agg.month_cum).toBe(-10 + -20 + -5)
  })

  it('отличает пустой факт от нуля в готовности', () => {
    const empty = defaultForm()
    empty.weeks = weeks(null, null, null, null, null)
    expect(formReady(empty)).toBe(false)

    const zeroOnly = defaultForm()
    zeroOnly.weeks = weeks(0, 0, 0, 0, 0)
    expect(formReady(zeroOnly)).toBe(false)

    const ok = defaultForm()
    ok.weeks = weeks(null, 5, null, null, null)
    expect(formReady(ok)).toBe(true)
  })

  it('signedFmt для null даёт прочерк', () => {
    expect(signedFmt(null).text).toBe('—')
    expect(signedFmt(10).text).toContain('+')
    expect(signedFmt(-5).cls).toBe('neg')
  })
})
