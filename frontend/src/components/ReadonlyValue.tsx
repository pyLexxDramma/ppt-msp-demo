type Props = {
  value: string | number | null | undefined
  className?: string
  empty?: string
  'aria-label'?: string
}

/** Значение из графика / расчёта — не поле ввода. */
export function ReadonlyValue({
  value,
  className,
  empty = '—',
  'aria-label': ariaLabel,
}: Props) {
  const emptyValue = value === null || value === undefined || value === ''
  const text = emptyValue ? empty : String(value)
  return (
    <div
      className={`readonly-value${emptyValue ? ' is-empty' : ''}${className ? ` ${className}` : ''}`}
      aria-label={ariaLabel}
    >
      <span className="readonly-value-text">{text}</span>
    </div>
  )
}
