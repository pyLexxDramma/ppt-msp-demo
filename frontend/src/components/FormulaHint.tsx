import type { FormulaItem } from '../calcHelp'

type Props = {
  item: FormulaItem
  compact?: boolean
}

/** Справка по формуле — всегда видна (без скрытия). */
export function FormulaHint({ item, compact }: Props) {
  return (
    <div className={`formula-hint always-open${compact ? ' compact' : ''}`}>
      <p className="formula-line">
        <b>{item.title}:</b> <code>{item.formula}</code>
      </p>
      <p className="formula-detail">{item.detail}</p>
    </div>
  )
}
