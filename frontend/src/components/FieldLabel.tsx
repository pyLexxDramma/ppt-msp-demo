type Props = {
  htmlFor?: string
  label: string
  help: string
  error?: string
  children: React.ReactNode
  className?: string
}

/** Подпись поля + иконка i с подсказкой типа данных + ошибка. */
export function FieldLabel({ htmlFor, label, help, error, children, className }: Props) {
  return (
    <div className={`field-wrap${error ? ' has-error' : ''}${className ? ` ${className}` : ''}`}>
      <div className="field-label-row">
        <label htmlFor={htmlFor}>{label}</label>
        <span className="info-tip" tabIndex={0} aria-label={help}>
          i
          <span className="info-tip-bubble" role="tooltip">
            {help}
          </span>
        </span>
      </div>
      {children}
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  )
}
