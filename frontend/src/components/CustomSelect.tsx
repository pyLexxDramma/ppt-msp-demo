import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { SelectOption } from '../options'
import { placeSelectMenu, type MenuPlacement } from './placeSelectMenu'

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

/** Кастомный селект в стиле макета CONALL. Список — портал, чтобы не обрезался сеткой/fieldset. */
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
  const [menuPos, setMenuPos] = useState<MenuPlacement | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()
  const selected = options.find((o) => o.value === value)

  const updateMenuPos = () => {
    const el = triggerRef.current
    if (!el) return
    setMenuPos(
      placeSelectMenu(el.getBoundingClientRect(), {
        width: window.innerWidth,
        height: window.innerHeight,
      }),
    )
  }

  useLayoutEffect(() => {
    if (!open) {
      setMenuPos(null)
      return
    }
    updateMenuPos()
    window.addEventListener('resize', updateMenuPos)
    window.addEventListener('scroll', updateMenuPos, true)
    return () => {
      window.removeEventListener('resize', updateMenuPos)
      window.removeEventListener('scroll', updateMenuPos, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (rootRef.current?.contains(t) || listRef.current?.contains(t)) return
      setOpen(false)
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

  const choose = (next: string) => {
    onChange(next)
    setOpen(false)
  }

  const list =
    open && menuPos ? (
      <ul
        className="cselect-list is-portal"
        id={listId}
        role="listbox"
        ref={listRef}
        style={{
          top: menuPos.top,
          left: menuPos.left,
          width: menuPos.width,
          maxHeight: menuPos.maxHeight,
        }}
      >
        {options.length === 0 ? (
          <li role="option" aria-selected="false" aria-disabled="true">
            <span className="cselect-option is-empty">Нет значений для выбора</span>
          </li>
        ) : (
          options.map((o) => (
            <li key={o.value} role="option" aria-selected={o.value === value}>
              <button
                type="button"
                className={`cselect-option${o.value === value ? ' selected' : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(o.value)
                }}
              >
                {o.label}
              </button>
            </li>
          ))
        )}
      </ul>
    ) : null

  return (
    <div
      className={`cselect${open ? ' open' : ''}${invalid ? ' invalid' : ''}${disabled ? ' disabled' : ''}`}
      ref={rootRef}
    >
      <button
        type="button"
        id={id}
        ref={triggerRef}
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
      {list ? createPortal(list, document.body) : null}
    </div>
  )
}
