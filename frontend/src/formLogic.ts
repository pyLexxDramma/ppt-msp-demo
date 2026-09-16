import type { Aggregates, FormState } from './types'
import { WEEKS_COUNT } from './types'

export function computeAggregates(state: FormState): Aggregates {
  let planTotal = 0
  let factTotal = 0
  let cum: number | null = null
  let lastCum = 0
  const rows: Aggregates['rows'] = []

  for (let i = 0; i < WEEKS_COUNT; i++) {
    const w = state.weeks[i] ?? { plan: 0, fact: null }
    const planV = Number(w.plan) || 0
    planTotal += planV
    if (w.fact === null || w.fact === undefined || Number.isNaN(Number(w.fact))) {
      rows.push({ dev: null, cum: null })
      continue
    }
    const f = Number(w.fact)
    factTotal += f
    const dev = f - planV
    const rowCum: number = (cum === null ? 0 : cum) + dev
    cum = rowCum
    lastCum = rowCum
    rows.push({ dev, cum: rowCum })
  }

  const vor = Number(state.vor) || 0
  const done = (Number(state.prev_cumulative) || 0) + factTotal
  const remaining = vor - done
  const pct_done = vor ? (done / vor) * 100 : 0

  return {
    plan_total: planTotal,
    fact_total: factTotal,
    month_cum: lastCum,
    done,
    remaining,
    pct_done,
    vor,
    rows,
  }
}

export function formReady(state: FormState): boolean {
  if ((Number(state.vor) || 0) <= 0) return false
  return state.weeks.some((w) => w.fact !== null && w.fact !== undefined && Number(w.fact) > 0)
}

export function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return Number(n).toLocaleString('ru-RU', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function periodLabel(state: FormState, months: readonly string[]): string {
  const idx = Math.max(0, Math.min(11, state.period_month))
  return `${months[idx]} ${state.period_year}`
}

export function signedFmt(n: number | null): { text: string; cls: string } {
  if (n === null || n === undefined) return { text: '—', cls: '' }
  const text = `${n > 0 ? '+' : ''}${fmt(n)}`
  const cls = n >= 0 ? 'pos' : 'neg'
  return { text, cls }
}
