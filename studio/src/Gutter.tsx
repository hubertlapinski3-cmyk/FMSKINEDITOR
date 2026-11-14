import { useCallback, useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type CSSProperties } from 'react'

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** A size that is remembered between runs. Storage can be missing or throw (private window, blocked site data): the size then just is not remembered. */
export function useStoredSize(key: string, def: number, min: number, max: number): [number, (v: number) => void] {
  const [v, setV] = useState(() => {
    try { const n = Number(localStorage.getItem(key)); if (localStorage.getItem(key) !== null && Number.isFinite(n)) return clamp(n, min, max) } catch { /* not remembered */ }
    return def
  })
  const set = useCallback((n: number) => {
    const c = clamp(Math.round(n), min, max)
    setV(c)
    try { localStorage.setItem(key, String(c)) } catch { /* not remembered */ }
  }, [key, min, max])
  return [v, set]
}

interface GutterProps {
  /** 'x' resizes a width (a vertical bar), 'y' a height (a horizontal bar). */
  axis: 'x' | 'y'
  value: number
  min: number
  max: number
  def: number
  onChange: (v: number) => void
  label: string
  /** The pane being sized sits after the bar (a bottom panel, a right pane): dragging towards it makes the pane smaller. */
  invert?: boolean
  /** Sits in the normal flow between two panes (a flex row); without it the bar is positioned over a grid boundary by the caller's style. */
  inflow?: boolean
  style?: CSSProperties
}

/** A draggable, keyboard-operable divider (role "separator"): mouse drag, arrow keys (Shift = 5x), Home/End for the limits, double-click or Enter to reset. */
export default function Gutter({ axis, value, min, max, def, onChange, label, invert, inflow, style }: GutterProps) {
  const [drag, setDrag] = useState(false)
  const start = useRef({ pos: 0, val: 0 })
  const cleanup = useRef<() => void>(() => {})
  useEffect(() => () => cleanup.current(), [])

  const down = (e: React.MouseEvent) => {
    e.preventDefault()
    start.current = { pos: axis === 'x' ? e.clientX : e.clientY, val: value }
    setDrag(true)
    const prevCursor = document.body.style.cursor, prevSelect = document.body.style.userSelect
    document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
    const move = (ev: MouseEvent) => {
      const delta = ((axis === 'x' ? ev.clientX : ev.clientY) - start.current.pos) * (invert ? -1 : 1)
      onChange(clamp(start.current.val + delta, min, max))
    }
    const up = () => { cleanup.current() }
    cleanup.current = () => {
      window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up)
      document.body.style.cursor = prevCursor; document.body.style.userSelect = prevSelect
      setDrag(false); cleanup.current = () => {}
    }
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
  }

  const key = (e: ReactKeyboardEvent) => {
    const step = (e.shiftKey ? 50 : 10) * (invert ? -1 : 1)
    const dec = axis === 'x' ? 'ArrowLeft' : 'ArrowUp', inc = axis === 'x' ? 'ArrowRight' : 'ArrowDown'
    if (e.key === dec) onChange(clamp(value - step, min, max))
    else if (e.key === inc) onChange(clamp(value + step, min, max))
    else if (e.key === 'Home') onChange(min)
    else if (e.key === 'End') onChange(max)
    else if (e.key === 'Enter') onChange(def)
    else return
    e.preventDefault()
  }

  return <div role="separator" tabIndex={0} aria-label={label} aria-orientation={axis === 'x' ? 'vertical' : 'horizontal'} aria-valuenow={value} aria-valuemin={min} aria-valuemax={max}
    title={label + ' (drag, arrow keys, double-click resets)'} className={`gutter ${axis}${inflow ? ' inflow' : ''}${drag ? ' dragging' : ''}`} style={style}
    onMouseDown={down} onDoubleClick={() => onChange(def)} onKeyDown={key} />
}
