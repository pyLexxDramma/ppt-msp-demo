type Props = {
  htmlFor?: string
  label: string
  help: string
  error?: string
  children: React.ReactNode
  className?: string
  /** Поле для ручного ввода — визуально выделено. */
  editable?: boolean
}

/** Подпись поля + иконка i с подсказкой типа данных + ошибка. */
export function FieldLabel({ htmlFor, label, help, error, children, className, editable }: Props) {
  return (
    <div
      className={`field-wrap${editable ? ' is-editable' : ''}${error ? ' has-error' : ''}${
        className ? ` ${className}` : ''
      }`}
    >
      <div className="field-label-row">
        <label htmlFor={htmlFor}>
          {label}
          {editable ? <span className="field-edit-mark" aria-hidden>*</span> : null}
        </label>
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
