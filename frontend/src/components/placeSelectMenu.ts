export type RectLike = {
  top: number
  left: number
  bottom: number
  width: number
  height: number
}

export type ViewportLike = {
  width: number
  height: number
}

export type MenuPlacement = {
  top: number
  left: number
  width: number
  maxHeight: number
}

const GAP = 4
const EDGE = 8
const DEFAULT_MAX_HEIGHT = 280
const DEFAULT_MIN_WIDTH = 280

/** Позиция выпадающего списка: не уже поля, не вылезает за экран, при нехватке места снизу — вверх. */
export function placeSelectMenu(
  trigger: RectLike,
  viewport: ViewportLike,
  opts?: { minWidth?: number; maxWidth?: number; maxHeight?: number },
): MenuPlacement {
  const minWidth = opts?.minWidth ?? DEFAULT_MIN_WIDTH
  const maxWidth = opts?.maxWidth ?? Math.min(520, Math.max(EDGE * 2, viewport.width - EDGE * 2))
  const width = Math.min(maxWidth, Math.max(trigger.width, minWidth, 0))
  let left = trigger.left
  if (left + width > viewport.width - EDGE) {
    left = Math.max(EDGE, viewport.width - EDGE - width)
  }
  if (left < EDGE) left = EDGE

  const spaceBelow = viewport.height - trigger.bottom - GAP - EDGE
  const spaceAbove = trigger.top - GAP - EDGE
  const cap = opts?.maxHeight ?? DEFAULT_MAX_HEIGHT
  const openUp = spaceBelow < 140 && spaceAbove > spaceBelow
  const avail = openUp ? spaceAbove : spaceBelow
  const maxHeight = Math.max(96, Math.min(cap, avail))
  const top = openUp ? Math.max(EDGE, trigger.top - GAP - maxHeight) : trigger.bottom + GAP
  return { top, left, width, maxHeight }
}
