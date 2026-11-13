// Pure logic of the tile canvas: grid extent, snapping a drag to whole grid units, collisions, and the staged positions (nothing is stored
// until the user commits). Cells keep their size: only x and y are ever edited (a cell's size is derived from its configs).
export interface Cell { cell_index: number; element_id: string; x: number; y: number; w: number; h: number; min_w: number; min_h: number; max_w: number; max_h: number; flags: string[] }
export interface Pos { x: number; y: number }
export type Staged = Record<number, Pos>

/** Columns and rows of the canvas: the composition's preset size when it has one, else the extent of its cells (including staged positions). */
export function extent(cells: Cell[], preset: { w: number; h: number } | null, staged: Staged = {}) {
  let w = preset?.w ?? 0, h = preset?.h ?? 0
  for (const c of cells) {
    const p = pos(c, staged)
    w = Math.max(w, p.x + c.w); h = Math.max(h, p.y + c.h)
  }
  return { cols: Math.max(w, 1), rows: Math.max(h, 1) }
}

export const pos = (c: Cell, staged: Staged): Pos => staged[c.cell_index] ?? { x: c.x, y: c.y }
/** Locked cells and cells the game places itself (x or y of -1) cannot be moved. */
export const movable = (c: Cell) => !c.flags.includes('locked') && c.x >= 0 && c.y >= 0

/** A drag of (dxPx, dyPx) pixels from `from` at `unit` pixels per grid unit, snapped to whole units and kept inside [0, cols-w] x [0, rows-h]. */
export function snap(c: Cell, from: Pos, dxPx: number, dyPx: number, unit: number, cols: number, rows: number): Pos {
  const clamp = (v: number, hi: number) => Math.max(0, Math.min(hi, v))
  return { x: clamp(from.x + Math.round(dxPx / unit), Math.max(0, cols - c.w)), y: clamp(from.y + Math.round(dyPx / unit), Math.max(0, rows - c.h)) }
}

const overlap = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
/** Cell indexes that overlap another cell at the staged positions (overlap may be intended layering; it only needs a confirm). */
export function collisions(cells: Cell[], staged: Staged): number[] {
  const rects = cells.map((c) => ({ i: c.cell_index, ...pos(c, staged), w: c.w, h: c.h }))
  const out = new Set<number>()
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) if (overlap(rects[i], rects[j])) { out.add(rects[i].i); out.add(rects[j].i) }
  return [...out].sort((a, b) => a - b)
}

/** The cells whose staged position differs from the stored one. */
export const dirty = (cells: Cell[], staged: Staged) => cells.filter((c) => staged[c.cell_index] && (staged[c.cell_index].x !== c.x || staged[c.cell_index].y !== c.y)).map((c) => c.cell_index)

export function stage(s: Staged, c: Cell, p: Pos): Staged {
  const next = { ...s }
  if (p.x === c.x && p.y === c.y) delete next[c.cell_index]; else next[c.cell_index] = p
  return next
}

/** One placement.add edit per moved cell, in an order that never has to confirm more than needed: the call list for a commit. */
export function commitEdits(composition: string, cells: Cell[], staged: Staged) {
  return dirty(cells, staged).map((i) => {
    const c = cells.find((x) => x.cell_index === i)!
    return { composition, cell_index: i, geometry: { x: staged[i].x, y: staged[i].y, w: c.w, h: c.h }, note: 'moved in the tile canvas' }
  })
}
