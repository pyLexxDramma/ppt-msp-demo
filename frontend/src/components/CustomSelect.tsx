import { useEffect, useId, useRef, useState } from 'react'
import type { SelectOption } from '../options'

type Props = {
  id?: string
  value: string
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  invalid?: boolean
  onChange: (value: string) => void
  'aria-label'?: string
}

/** Кастомный селект в стиле макета CONALL. */
export function CustomSelect({
  id,
  value,
  options,
  placeholder = 'Выберите…',
  disabled,
  invalid,
  onChange,
  'aria-label': ariaLabel,
}: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div
      className={`cselect${open ? ' open' : ''}${invalid ? ' invalid' : ''}${disabled ? ' disabled' : ''}`}
      ref={rootRef}
    >
      <button
        type="button"
        id={id}
        className="cselect-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel}
        aria-invalid={invalid || undefined}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <span className={selected ? 'cselect-value' : 'cselect-placeholder'}>
          {selected ? selected.label : placeholder}
        </span>
        <span className="cselect-chevron" aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <ul className="cselect-list" id={listId} role="listbox">
          {options.map((o) => (
            <li key={o.value} role="option" aria-selected={o.value === value}>
              <button
                type="button"
                className={`cselect-option${o.value === value ? ' selected' : ''}`}
                onClick={() => {
                  onChange(o.value)
                  setOpen(false)
                }}
              >
                {o.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
