import { useEffect, useRef } from 'react'
import { isStreamlitComponent, syncHeight } from '../streamlitBridge'
import type { ScheduleRow } from '../types'

const DEFAULT_COLS = [
  'Ид',
  'Название',
  'Начало',
  'Окончание',
  'Предшественники',
  'Последователи',
  'ВОР',
  'ВОР_факт',
  'ВОР_остаток',
  '%_выполнения_ВОР',
  'Осталось_дней_прогноз',
  'Изменено',
  'Заметки',
] as const

type Props = {
  title: string
  rows: ScheduleRow[]
  cols?: string[]
  highlightChanged?: boolean
}

function visibleCols(rows: ScheduleRow[], cols: string[]): string[] {
  if (!rows.length) return cols
  return cols.filter(
    (c) => rows.some((r) => (r[c] ?? '') !== '') || c === 'Ид' || c === 'Название',
  )
}

export function ScheduleTable({ title, rows, cols, highlightChanged = false }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const columns = visibleCols(rows, cols?.length ? cols : [...DEFAULT_COLS])

  useEffect(() => {
    if (!isStreamlitComponent()) return
    syncHeight()
    const t = window.setTimeout(syncHeight, 50)
    return () => window.clearTimeout(t)
  }, [rows, columns.length])

  useEffect(() => {
    if (!highlightChanged || !wrapRef.current) return
    const changed = wrapRef.current.querySelector('tr.is-changed')
    changed?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [highlightChanged, rows])

  if (!rows.length) {
    return (
      <div className="schedule-table-block">
        <div className="schedule-table-title">{title}</div>
        <p className="schedule-table-empty">Нет строк графика.</p>
      </div>
    )
  }

  return (
    <div className="schedule-table-block">
      <div className="schedule-table-title">{title}</div>
      <div className="schedule-table-wrap" ref={wrapRef}>
        <table className="schedule-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const changed = Boolean(row['Изменено']?.trim())
              return (
                <tr
                  key={`${row['Ид']}-${row['Название']}`}
                  className={highlightChanged && changed ? 'is-changed' : undefined}
                >
                  {columns.map((c) => (
                    <td key={c}>{row[c] ?? ''}</td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
